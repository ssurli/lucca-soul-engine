-- Schema del freno di emergenza (docs/STATE_MACHINE.md §4-bis(b), Fase 3,
-- override di sicurezza manuale su un `:Evento` promosso — comando
-- `python -m urban_memory.freno_pattern tira|rilascia`) — Neon
-- (`sslmode=require`, cloud) o Postgres locale: stesso schema nei due
-- profili, nessun `if local/cloud` (CLAUDE.md).
--
-- `pattern_frenato` — log PERMANENTE di ogni tiro/rilascio del freno.
-- Applicato AUTOMATICAMENTE da `urban_memory.migrate.migrate(dsn)`
-- (`SCHEMA_PATHS` raccoglie ogni `sql/*_schema.sql`, in ordine di prefisso
-- numerico: nessuna registrazione manuale separata serve).
--
-- IDEMPOTENTE e rieseguibile da zero in un comando, come gli altri schemi di
-- questo servizio (CLAUDE.md — Aura Free si mette in pausa/viene cancellata
-- dopo inattività: nessun dato vive solo lì). Solo `CREATE ... IF NOT
-- EXISTS`, nessun `DROP`.
--
-- A DIFFERENZA di `pattern_cestinato` (02_ricorrenza_schema.sql): NESSUN
-- vincolo `UNIQUE`. Il freno è RIPETIBILE nel tempo — tirare e rilasciare
-- più volte lo stesso `evento_id` è un uso normale e previsto: ogni azione
-- è una riga nuova, mai un upsert, non c'è nulla con cui una seconda riga
-- potrebbe confliggere.

CREATE TABLE IF NOT EXISTS pattern_frenato (
    id             TEXT PRIMARY KEY,
    evento_id      TEXT NOT NULL,
    -- Contesto/audit facoltativo (l'operatore può conoscere il pattern
    -- tramite place_id+temi invece dell'id tecnico dell'evento, vedi
    -- `urban_memory.freno_pattern`) — stessa forma di `pattern_cestinato`.
    place_id       TEXT,
    temi           TEXT[] NOT NULL DEFAULT '{}',
    azione         TEXT NOT NULL,
    -- Pseudonimo di chi ha agito — mai PII, stessa disciplina di
    -- `pattern_cestinato.promotore`/`MemoryContribution.contributor_id`.
    attore         TEXT NOT NULL,
    -- Nullable a livello DB: l'obbligatorietà su un TIRO è applicativa,
    -- verificata da `urban_memory.freno_pattern.tira_freno` PRIMA di
    -- arrivare qui (stesso principio di `MemoryContribution.consenso` vs
    -- `pattern_cestinato.motivo` — validazione applicativa come gate). Il
    -- CHECK sotto è un BACKSTOP a livello DB, coerente con lo stile già
    -- usato per `memory_contribution_consenso_check`
    -- (`00_memory_schema.sql`): nemmeno un INSERT diretto che bypassi
    -- `tira_freno` può persistere un tiro senza motivazione.
    motivazione    TEXT,
    quando         TIMESTAMPTZ NOT NULL,

    CONSTRAINT pattern_frenato_azione_check CHECK (azione IN ('tirato', 'rilasciato')),
    CONSTRAINT pattern_frenato_attore_check CHECK (char_length(attore) >= 1),
    CONSTRAINT pattern_frenato_motivazione_check
        CHECK (azione <> 'tirato' OR (motivazione IS NOT NULL AND char_length(motivazione) >= 1))
);

-- `per_evento(evento_id)` (audit di un singolo pattern) è l'accesso mirato
-- più frequente oltre l'INSERT.
CREATE INDEX IF NOT EXISTS pattern_frenato_evento_id_idx
    ON pattern_frenato (evento_id);
