-- Schema del canale fluttuante persistente (Fase 3, `docs/PROMOZIONE_TRACCIA.md`) —
-- Neon (`sslmode=require`, cloud) o Postgres locale (Docker sul PC fisso): stesso
-- schema nei due profili, nessun `if local/cloud` (CLAUDE.md).
--
-- DUE tabelle, una quarta corsia accanto a memory_contribution/booking/behavior_event
-- (`docs/PROMOZIONE_TRACCIA.md` §1: "non è un evento comportamentale... non è un
-- contributo di memoria... non è una prenotazione"), non un'aggiunta dentro
-- `00_memory_schema.sql`:
--
-- 1. `segnale_fluttuante` — colonne speculari a `contracts.SegnaleFluttuante`
--    (docs/DATA_CONTRACTS.md), la tabella-segnale del canale persistente.
-- 2. `traccia_luogo` — il ledger APPEND-ONLY depositato quando un segnale transita
--    attivo -> expired (Strada B: `creato_il` timbrato dal SERVER all'istante dello
--    sweep, MAI letto dal segnale — `SegnaleFluttuante` non porta un proprio
--    timestamp di creazione). Anagrafica MINIMA: place_id, temi[], creato_il —
--    NIENTE contributor_id/PII/testo libero, stessa disciplina di
--    `memory_contribution` per i campi sensibili.
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come il seed del grafo e
-- `00_memory_schema.sql` (CLAUDE.md — Aura Free si mette in pausa e viene cancellata
-- dopo 30 giorni di inattività: nessun dato vive solo lì). Solo
-- `CREATE ... IF NOT EXISTS`, nessun `DROP`.

-- ---------------------------------------------------------------------------
-- 1. segnale_fluttuante — "un violinista suona in piazza": vive ORA, ha una
--    scadenza ASSOLUTA (`valido_fino`), transita attivo -> expired in lettura
--    (sweep pigro, mai un job schedulato — vedi `urban_memory.canale_fluttuante`).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS segnale_fluttuante (
    id                TEXT PRIMARY KEY,
    descrizione       TEXT NOT NULL,
    temi              TEXT[] NOT NULL DEFAULT '{}',
    place_id          TEXT NOT NULL,
    non_commerciale   BOOLEAN NOT NULL,
    valido_fino       TIMESTAMPTZ NOT NULL,
    stato             TEXT NOT NULL DEFAULT 'attivo',

    -- Difesa in profondità (stesso principio dei CHECK di memory_contribution):
    -- i vincoli che `packages/contracts.SegnaleFluttuante` già impone a livello
    -- Pydantic sono ribaditi qui, a livello DB, contro un INSERT diretto che
    -- scavalchi `urban_memory.canale_fluttuante.persist_signal`.
    CONSTRAINT segnale_fluttuante_stato_check CHECK (stato IN ('attivo', 'expired')),
    CONSTRAINT segnale_fluttuante_descrizione_check CHECK (char_length(descrizione) >= 1),
    CONSTRAINT segnale_fluttuante_temi_check CHECK (array_length(temi, 1) >= 1)
);

-- Query dominanti sul lato-lettura (`urban_memory.canale_fluttuante.
-- sweep_and_fetch_active`, invocato da `POST /itinerary` PRIMA di
-- `compose_itinerary`): sweep (`stato='attivo' AND valido_fino <= now`) e fetch
-- (`stato='attivo' AND valido_fino > now`) — stesso indice composito serve
-- entrambe.
CREATE INDEX IF NOT EXISTS segnale_fluttuante_stato_valido_fino_idx
    ON segnale_fluttuante (stato, valido_fino);

-- ---------------------------------------------------------------------------
-- 2. traccia_luogo — il ledger, append-only, place-anchored (mai occurrence-
--    anchored: docs/PROMOZIONE_TRACCIA.md §1). Chiave surrogata (`id`, generata
--    dall'applicazione — stesso principio di `behavior_event`): nessuna chiave
--    naturale, due tracce identiche in place_id/temi/istante restano due
--    passaggi distinti.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS traccia_luogo (
    id                TEXT PRIMARY KEY,
    -- Riferimento al segnale che ha depositato questa traccia — NON una FK
    -- verso il grafo (Neo4j e Postgres restano store separati, nessuna
    -- transazione condivisa, stesso limite già accettato per
    -- `memory_contribution.riguarda`). UNIQUE: difesa in profondità
    -- dell'IDEMPOTENZA load-bearing (un segnale deposita AL PIÙ una traccia —
    -- la guardia primaria è la transizione atomica attivo->expired in
    -- `segnale_fluttuante`, questo vincolo la ribadisce a livello DB contro un
    -- bug applicativo futuro che chiamasse `deposita` due volte sullo stesso
    -- segnale).
    segnale_id        TEXT NOT NULL UNIQUE,
    place_id          TEXT NOT NULL,
    temi              TEXT[] NOT NULL DEFAULT '{}',
    creato_il         TIMESTAMPTZ NOT NULL
);

-- "Indice per aggregazione-per-luogo (place_id): è la query che conta — tutte
-- le tracce di questo place_id — mai una traversata Neo4j" (docs/
-- PROMOZIONE_TRACCIA.md §1).
CREATE INDEX IF NOT EXISTS traccia_luogo_place_id_idx
    ON traccia_luogo (place_id);
