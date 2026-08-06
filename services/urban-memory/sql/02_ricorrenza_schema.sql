-- Schema del rilevamento cadenza + cestino permanente dei pattern (Fase 3,
-- promozione di un pattern ricorrente a `:Evento`, comando `python -m
-- urban_memory.curatela_pattern`) — Neon (`sslmode=require`, cloud) o
-- Postgres locale: stesso schema nei due profili, nessun `if local/cloud`
-- (CLAUDE.md).
--
-- DUE aggiunte, sullo stesso `traccia_luogo`/schema precedente
-- (`01_fluttuante_schema.sql`), non un file a sé senza motivo:
--
-- 1. Un indice nuovo su `traccia_luogo`, a supporto dell'aggregazione per
--    PATTERN (place_id + temi) — `TracciaRepository.pattern_ricorrenti`,
--    la lettura che il comando di curatela esegue a ogni rilevamento.
-- 2. `pattern_cestinato` — il cestino PERMANENTE (v1) dei pattern rifiutati
--    dal Promotore: append-only, mai un UPDATE/DELETE, stesso principio di
--    `traccia_luogo`.
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come gli altri schemi di
-- questo servizio (CLAUDE.md — Aura Free si mette in pausa/viene cancellata
-- dopo inattività: nessun dato vive solo lì). Solo `CREATE ... IF NOT
-- EXISTS`, nessun `DROP`.

-- ---------------------------------------------------------------------------
-- 1. Indice per l'aggregazione per pattern (place_id + temi).
--
-- `pattern_ricorrenti` raggruppa per (place_id, insieme-di-temi-CANONICO):
-- la canonicalizzazione (ordinamento alfabetico dei temi) avviene IN QUERY
-- (Postgres non ammette una sotto-query dentro un'espressione di indice, e
-- non esiste una funzione IMMUTABLE nativa di "array ordinato" da usare in
-- un indice funzionale senza scriverne una custom — prematuro per questa
-- wave). Questo indice composito su (place_id, temi) accelera comunque il
-- caso dominante: occorrenze CONSECUTIVE dello stesso segnale ricorrente,
-- che arrivano tipicamente con i temi nello STESSO ordine (stesso segnale
-- risottomesso con gli stessi `--tema`, `urban_memory.submit_signal`) — e in
-- ogni caso evita una scansione completa non filtrata, che l'indice
-- esistente (`traccia_luogo_place_id_idx`, solo su place_id) non copre per
-- il raggruppamento successivo sui temi. Un indice funzionale sull'array
-- ordinato è rimandato a quando il volume reale del pilota lo richieda.
CREATE INDEX IF NOT EXISTS traccia_luogo_place_id_temi_idx
    ON traccia_luogo (place_id, temi);

-- ---------------------------------------------------------------------------
-- 2. pattern_cestinato — il cestino permanente (v1). Si cestina il PATTERN
--    (place_id + insieme di temi), non la singola candidata-del-momento:
--    `UNIQUE(place_id, temi)` impedisce una seconda riga per lo stesso
--    pattern (idempotenza applicativa, vedi
--    `PatternCestinatoRepository.cestina`) — un pattern cestinato resta
--    cestinato PER SEMPRE anche se accumula nuove occorrenze nel ledger
--    dopo il rifiuto: altrimenti il cestino non servirebbe a nulla.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pattern_cestinato (
    id             TEXT PRIMARY KEY,
    place_id       TEXT NOT NULL,
    -- Canonico: ordinato alfabeticamente in APPLICAZIONE prima dell'INSERT
    -- (stessa canonicalizzazione di `traccia_repository.PatternAggregato`)
    -- — così l'uguaglianza di array a livello DB (UNIQUE, WHERE temi = ...)
    -- identifica correttamente lo STESSO insieme di temi indipendentemente
    -- dall'ordine con cui sono arrivati dal segnale originale.
    temi           TEXT[] NOT NULL DEFAULT '{}',
    -- Registrato ma NON usato per guidare alcuna logica in questa v1: serve
    -- solo a raccogliere dati per un task futuro (motivi ricorrenti di
    -- rifiuto). Facoltativo di proposito.
    motivo         TEXT,
    -- Pseudonimo del Promotore che ha deciso — mai PII, stessa disciplina di
    -- `MemoryContribution.contributor_id`.
    promotore      TEXT NOT NULL,
    cestinato_il   TIMESTAMPTZ NOT NULL,

    CONSTRAINT pattern_cestinato_promotore_check CHECK (char_length(promotore) >= 1),
    CONSTRAINT pattern_cestinato_place_temi_unique UNIQUE (place_id, temi)
);
