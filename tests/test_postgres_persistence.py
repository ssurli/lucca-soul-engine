"""Test di integrazione — Wave 2 (completamento persistenza): criterio del
committente END-TO-END su Postgres VERO (non un mock).

GATED: usa il cluster Postgres 16 EFFIMERO già scritto per
`services/urban-memory/tests/conftest.py` (fixture `pg_dsn`, riesportata da
`tests/conftest.py` — vedi lì per i dettagli, non duplicata qui). Se questo
ambiente non può avviare Postgres 16 (binari assenti, o pytest gira come
root senza un utente `postgres`/`sudo` per delegargli l'avvio), il test è
SALTATO (`pytest.skip`), non fallito: la CI resta verde anche su un runner
senza Postgres.

Criterio verificato: `migrate` -> `submit_contribution` -> `curate_contribution`
-> una NUOVA `PostgresMemoryRepository`, istanziata sullo STESSO DSN ma come
oggetto Python distinto (nessuno stato in RAM condiviso con la prima),
ritrova il contributo curato. Dimostra che la memoria sopravvive a un
"riavvio" del processo che la scrive, non solo di quello che la legge — il
fossato del progetto (CLAUDE.md) non può vivere solo in RAM.

Se questo test fallisce, il bug è in `services/urban-memory` (repository,
migrazione o schema SQL), non nel test: non "aggiustare" l'asserzione per
farla passare, segnala il bug al subagent competente.
"""

from __future__ import annotations

from datetime import datetime

from contracts import MemoryContribution
from urban_memory.migrate import migrate
from urban_memory.repository import PostgresMemoryRepository
from urban_memory.service import curate_contribution, submit_contribution


def test_migrate_submit_curate_sopravvive_a_nuova_istanza_dello_stesso_dsn(
    pg_dsn: str,
) -> None:
    place_id = "bottega-w2-pg-e2e"
    memory_id = "mem-w2-pg-e2e"

    # 1. Migrazione idempotente dello schema (sql/00_memory_schema.sql).
    migrate(pg_dsn)

    # 2. Submit tramite il servizio (applica i vincoli non negoziabili),
    #    con la PRIMA istanza del repository sul DSN.
    repo_scrittore = PostgresMemoryRepository(pg_dsn)
    contributo = MemoryContribution(
        id=memory_id,
        kind="racconto",
        testo="Il racconto di una bottega di liuteria, persistito davvero.",
        riguarda=[place_id],
        contributor_id="pseudonimo-e2e",
        contributor_kind="cittadino",
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 14, 10, 0),
    )
    persistito = submit_contribution(repo_scrittore, contributo)
    assert persistito.curato is False

    # 3. Curatela (revisione umana), sempre con la stessa istanza.
    curato = curate_contribution(repo_scrittore, memory_id)
    assert curato.curato is True

    # 4. "Riavvio": una NUOVA istanza di PostgresMemoryRepository, stesso
    #    DSN, nessuno stato Python condiviso con `repo_scrittore` — dimostra
    #    che il dato vive nel database, non nell'oggetto Python.
    repo_lettore = PostgresMemoryRepository(pg_dsn)
    pubblicati = repo_lettore.get_curated(place_id)

    assert any(c.id == memory_id for c in pubblicati), (
        f"il contributo curato non è stato ritrovato da una nuova istanza "
        f"di PostgresMemoryRepository sullo stesso DSN: {pubblicati}"
    )
    trovato = next(c for c in pubblicati if c.id == memory_id)
    assert trovato.testo == contributo.testo
    assert trovato.licenza == "CC-BY-SA-4.0"
    assert trovato.consenso is True


def test_migrate_e_idempotente(pg_dsn: str) -> None:
    """`migrate` è rieseguibile da zero senza errori (CLAUDE.md: il seed/lo
    schema devono poter essere applicati di nuovo in un comando solo)."""
    migrate(pg_dsn)
    migrate(pg_dsn)  # seconda esecuzione: non deve sollevare


def test_contributo_non_curato_non_compare_dopo_riavvio(pg_dsn: str) -> None:
    """Stesso criterio del test principale, ma verifica anche il lato
    negativo: un contributo NON curato non deve comparire in `get_curated`
    nemmeno da una nuova istanza — la curatela prima della pubblicazione
    (CLAUDE.md) non è un effetto collaterale della sola persistenza."""
    place_id = "bottega-w2-pg-non-curato"
    memory_id = "mem-w2-pg-non-curato"

    migrate(pg_dsn)
    repo_scrittore = PostgresMemoryRepository(pg_dsn)
    contributo = MemoryContribution(
        id=memory_id,
        kind="fotografia",
        riguarda=[place_id],
        contributor_id="pseudonimo-e2e-2",
        contributor_kind="turista",
        consenso=True,
        licenza="CC-BY-4.0",
        creato_il=datetime(2026, 7, 14, 11, 0),
    )
    submit_contribution(repo_scrittore, contributo)  # MAI curato

    repo_lettore = PostgresMemoryRepository(pg_dsn)
    pubblicati = repo_lettore.get_curated(place_id)
    assert not any(c.id == memory_id for c in pubblicati)

    in_attesa = repo_lettore.list_pending()
    assert any(c.id == memory_id for c in in_attesa)
