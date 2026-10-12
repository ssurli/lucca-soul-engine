-- Schema del LEDGER delle promozioni (Fase 3, `python -m
-- urban_memory.curatela_pattern`) — Neon (`sslmode=require`) o Postgres
-- locale: stesso schema nei due profili, nessun `if local/cloud` (CLAUDE.md).
--
-- `pattern_promosso` — log PERMANENTE, APPEND-ONLY di ogni atto di
-- promozione di un pattern a `:Evento`. Applicato AUTOMATICAMENTE da
-- `urban_memory.migrate.migrate(dsn)` (`SCHEMA_PATHS` raccoglie ogni
-- `sql/*_schema.sql`).
--
-- PERCHE' ESISTE: la decisione di promozione (chi, quando, cadenza) viveva
-- SOLO nel grafo. Aura Free viene cancellata dopo 30 giorni di inattivita'
-- (osservato): CLAUDE.md vieta che un dato viva solo su Aura. Qui Postgres e'
-- la FONTE DI VERITA' della decisione, il grafo ne e' la PROIEZIONE;
-- `python -m urban_memory.ripristina_eventi` ricostruisce gli `:Evento`.
--
-- Stile `pattern_frenato` (03_freno_schema.sql): NESSUN `UNIQUE` sul pattern,
-- nessun UPDATE/DELETE — una ripromozione/ricalcolo dello stesso pattern e'
-- un atto NUOVO (una riga nuova). Al ripristino: riga PIU' RECENTE per
-- cadenza/temi/ricalcolo, riga PRIMA per promosso_da/promosso_il (stessa
-- semantica ON CREATE/ON MATCH di `cypher/50_promozione_evento_write.cypher`).
--
-- IDEMPOTENTE: solo `CREATE ... IF NOT EXISTS`, nessun `DROP`.

CREATE TABLE IF NOT EXISTS pattern_promosso (
    id             TEXT PRIMARY KEY,
    -- Id DETERMINISTICO (`promozione_evento.evento_id_per_pattern`), non unico.
    evento_id      TEXT NOT NULL,
    place_id       TEXT NOT NULL,
    -- Insieme di temi CANONICO (ordinato alfabeticamente).
    temi           TEXT[] NOT NULL DEFAULT '{}',
    cadenza_giorni DOUBLE PRECISION NOT NULL,
    -- Pseudonimo del Promotore — mai PII (come `pattern_cestinato.promotore`).
    promotore      TEXT NOT NULL,
    promosso_il    TIMESTAMPTZ NOT NULL,

    CONSTRAINT pattern_promosso_promotore_check CHECK (char_length(promotore) >= 1),
    CONSTRAINT pattern_promosso_cadenza_check CHECK (cadenza_giorni > 0)
);

CREATE INDEX IF NOT EXISTS pattern_promosso_evento_id_idx
    ON pattern_promosso (evento_id);
