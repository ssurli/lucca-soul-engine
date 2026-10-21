-- Schema dello SCARTO ESPLICITO dei contributi non curati — Neon
-- (`sslmode=require`) o Postgres locale: stesso schema nei due profili,
-- nessun `if local/cloud` (CLAUDE.md). Applicato AUTOMATICAMENTE da
-- `urban_memory.migrate.migrate(dsn)` (`SCHEMA_PATHS` raccoglie ogni
-- `sql/*_schema.sql`, dopo `00_memory_schema.sql` che crea la tabella).
--
-- PERCHE' ESISTE: un contributo non curato poteva solo restare pending per
-- sempre, indistinguibile da "nessuno l'ha ancora guardato"
-- (`docs/STATE_MACHINE.md`). Lo scarto e' una decisione esplicita, con un
-- motivo, e NON cancella nulla: la riga resta (mai DELETE), ma sparisce da
-- `list_pending`/`list_curated`/`get_curated` e quindi dall'Urban
-- Intelligence Index. Ammesso solo per i NON curati (`curato = false`): i
-- curati restano senza rifiuto. La regola vive in
-- `PostgresMemoryRepository.scarta`; il futuro campo `dimostrativo` dovra'
-- riusare la stessa esclusione (`scartato_il IS NULL`) nelle letture.
--
-- IDEMPOTENTE: solo `ADD COLUMN IF NOT EXISTS`, nessun `DROP`.

ALTER TABLE memory_contribution ADD COLUMN IF NOT EXISTS scartato_il TIMESTAMPTZ;
ALTER TABLE memory_contribution ADD COLUMN IF NOT EXISTS motivo_scarto TEXT;
