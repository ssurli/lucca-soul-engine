-- Schema di Urban Memory (Postgres) — Neon (`sslmode=require`, cloud) o
-- Postgres locale (Docker sul PC fisso): stesso schema nei due profili,
-- nessun `if local/cloud` (CLAUDE.md). Colonne speculari a
-- `MemoryContribution` (docs/DATA_CONTRACTS.md §4).
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come il seed del grafo
-- (`services/graph/cypher/`, CLAUDE.md — Aura Free si mette in pausa e viene
-- cancellata dopo 30 giorni di inattività: nessun dato vive solo lì). Solo
-- `CREATE ... IF NOT EXISTS`, nessun `DROP`: applicato da
-- `urban_memory.migrate.migrate(dsn)` / `python -m urban_memory.migrate`.
--
-- DIFESA IN PROFONDITÀ (non negoziabile, CLAUDE.md e
-- docs/DATA_CONTRACTS.md §4): `urban_memory.service.submit_contribution` già
-- rifiuta un contributo senza consenso o senza licenza PRIMA di arrivare
-- qui. I due CHECK sotto ribadiscono lo stesso vincolo A LIVELLO DB: nemmeno
-- un INSERT diretto (un bug applicativo futuro, uno script una tantum, un
-- accesso non passato da `urban_memory.service`) può persistere un
-- contributo senza consenso esplicito o senza licenza tracciata. Sono
-- vincoli INLINE nel `CREATE TABLE IF NOT EXISTS`: se la tabella esiste già,
-- l'istruzione è un no-op completo (compresi i CHECK, già presenti dalla
-- prima esecuzione) — idempotente senza bisogno di `ALTER TABLE ... ADD
-- CONSTRAINT IF NOT EXISTS` (sintassi che Postgres non supporta per i CHECK).

CREATE TABLE IF NOT EXISTS memory_contribution (
    id                TEXT PRIMARY KEY,
    kind              TEXT NOT NULL,
    testo             TEXT,
    media_uri         TEXT,
    riguarda          TEXT[] NOT NULL DEFAULT '{}',
    contributor_id    TEXT NOT NULL,       -- pseudonimo, mai PII
    contributor_kind  TEXT NOT NULL,
    esperienza_id     TEXT,
    consenso          BOOLEAN NOT NULL,
    licenza           TEXT NOT NULL,
    creato_il         TIMESTAMPTZ NOT NULL,
    curato            BOOLEAN NOT NULL DEFAULT FALSE,

    -- Nessuna eccezione (docs/DATA_CONTRACTS.md §4): un contributo senza
    -- consenso non deve poter persistere, nemmeno per un bug futuro nel
    -- livello applicativo.
    CONSTRAINT memory_contribution_consenso_check CHECK (consenso = true),

    -- Un contributo senza licenza chiara è un debito legale, non un asset.
    CONSTRAINT memory_contribution_licenza_check CHECK (char_length(licenza) >= 1)
);

-- `get_curated(place_id)` (curato=True e place_id in riguarda) è la query
-- più frequente: indice mirato su entrambi gli accessi.
CREATE INDEX IF NOT EXISTS memory_contribution_curato_idx
    ON memory_contribution (curato);

CREATE INDEX IF NOT EXISTS memory_contribution_riguarda_gin_idx
    ON memory_contribution USING GIN (riguarda);
