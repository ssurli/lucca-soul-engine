-- Schema del Marketplace (Postgres) — Neon (`sslmode=require`, cloud) o
-- Postgres locale (Docker sul PC fisso): stesso schema nei due profili,
-- nessun `if local/cloud` (CLAUDE.md). Colonne speculari a `Booking` e
-- `CommissionRecord` (docs/DATA_CONTRACTS.md §5).
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come lo schema di Urban
-- Memory (`services/urban-memory/sql/00_memory_schema.sql`) e il seed del
-- grafo (`services/graph/cypher/`, CLAUDE.md — Aura Free si mette in pausa e
-- viene cancellata dopo 30 giorni di inattività: nessun dato vive solo lì).
-- Solo `CREATE ... IF NOT EXISTS`, nessun `DROP`: applicato da
-- `marketplace.migrate.migrate(dsn)` / `python -m marketplace.migrate`.

CREATE TABLE IF NOT EXISTS booking (
    id            TEXT PRIMARY KEY,
    person_id     TEXT NOT NULL,        -- pseudonimo, mai PII
    experience_id TEXT NOT NULL,
    quando        TIMESTAMPTZ NOT NULL,
    stato         TEXT NOT NULL DEFAULT 'richiesta',
    -- Snapshot congelato al momento della richiesta (docs/DATA_CONTRACTS.md
    -- §5): NON segue il listino corrente dell'ExperienceNode, che può
    -- cambiare dopo che la Booking è stata creata.
    prezzo_eur    DOUBLE PRECISION NOT NULL,
    creato_il     TIMESTAMPTZ NOT NULL,

    -- Difesa in profondità (stesso principio dei CHECK in
    -- 00_memory_schema.sql): `marketplace.service` già vincola questi valori
    -- prima di arrivare qui; i CHECK ribadiscono il vincolo A LIVELLO DB,
    -- nel caso di un bug applicativo futuro o di un INSERT diretto.
    CONSTRAINT booking_stato_check CHECK (stato IN ('richiesta', 'confermata', 'annullata')),
    CONSTRAINT booking_prezzo_check CHECK (prezzo_eur >= 0)
);

-- Query più frequenti: prenotazioni di una persona, prenotazioni di
-- un'esperienza (es. per un futuro calendario di disponibilità, fuori scope
-- in questa wave).
CREATE INDEX IF NOT EXISTS booking_person_idx ON booking (person_id);
CREATE INDEX IF NOT EXISTS booking_experience_idx ON booking (experience_id);

-- `booking_id` è CHIAVE PRIMARIA (non solo FK): al massimo UNA
-- CommissionRecord per prenotazione. Vincolo non negoziabile
-- (ethics-guardian, docs/DATA_CONTRACTS.md §5): la commissione è un dato
-- CONTABILE registrato SOLO dopo la conferma (`marketplace.service.
-- confirm_booking`), mai un input di scoring. Questo UNIQUE a livello DB è
-- difesa in profondità contro una doppia registrazione, non la garanzia
-- primaria (quella sta nel servizio, che verifica `get_commission` prima di
-- registrare una seconda volta).
CREATE TABLE IF NOT EXISTS commission_record (
    booking_id    TEXT PRIMARY KEY REFERENCES booking (id),
    importo_eur   DOUBLE PRECISION NOT NULL,
    percentuale   DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    registrata_il TIMESTAMPTZ NOT NULL,

    CONSTRAINT commission_record_importo_check CHECK (importo_eur >= 0),
    CONSTRAINT commission_record_percentuale_check CHECK (percentuale >= 0 AND percentuale <= 1)
);
