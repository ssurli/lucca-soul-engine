-- Schema degli eventi comportamentali (`BehaviorEvent`, Recommender) —
-- Postgres. Neon (`sslmode=require`, cloud) o Postgres locale (Docker sul PC
-- fisso): stesso schema nei due profili, nessun `if local/cloud` (CLAUDE.md).
--
-- `BehaviorEvent` (packages/contracts/contracts/models.py) NON ha un campo
-- `id`: qui la tabella usa una chiave surrogata (`id BIGSERIAL`), perché
-- l'evento in sé è privo di identità naturale (due eventi identici in
-- persona/tipo/esperienza/istante sono comunque due righe distinte).
-- `ricevuto_il` è il timestamp SERVER (quando l'evento è arrivato a questo
-- servizio), distinto da `ts` (quando l'evento è avvenuto lato client):
-- utile per capire ritardi di ingestion senza confondere le due nozioni.
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come lo schema di
-- Marketplace (`services/marketplace/sql/00_marketplace_schema.sql`) e di
-- Urban Memory. Solo `CREATE ... IF NOT EXISTS`, nessun `DROP`: applicato da
-- `recommender.migrate.migrate(dsn)` / `python -m recommender.migrate`.

CREATE TABLE IF NOT EXISTS behavior_event (
    id            BIGSERIAL PRIMARY KEY,
    person_id     TEXT NOT NULL,        -- pseudonimo, mai PII
    tipo          TEXT NOT NULL,
    experience_id TEXT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,               -- quando l'evento è avvenuto
    ricevuto_il   TIMESTAMPTZ NOT NULL DEFAULT now(),  -- quando è arrivato al server

    -- Coerente col `Literal` di `BehaviorEvent.tipo` (docs/DATA_CONTRACTS.md
    -- §6): difesa in profondità, oltre alla validazione Pydantic a monte.
    CONSTRAINT behavior_event_tipo_check CHECK (
        tipo IN ('view', 'stop', 'photo', 'booking', 'review', 'skip', 'memory_contrib')
    )
);

-- Query più frequenti: aggregazione per esperienza (il cuore della feature
-- di ranking, `recommender.repository.conteggio_per_esperienza`), e lookup
-- per tipo/persona per diagnostica e futura Urban Intelligence Index.
CREATE INDEX IF NOT EXISTS behavior_event_experience_idx ON behavior_event (experience_id);
CREATE INDEX IF NOT EXISTS behavior_event_tipo_idx ON behavior_event (tipo);
CREATE INDEX IF NOT EXISTS behavior_event_person_idx ON behavior_event (person_id);
