"""Lucca Soul Lab — Engine: Urban Memory (`services/urban-memory`).

Il fossato difendibile del progetto: contenuto che nessun concorrente può
acquisire dall'esterno, perché nasce solo dalla partecipazione. Non è un
archivio da riempire una volta con un progetto finanziato: CRESCE CON L'USO
— ogni esperienza vissuta può generare un `MemoryContribution` (un
racconto, la foto di una bottega, un mestiere, una ricetta, una parola in
dialetto). Il conferimento resta leggero e contestuale, mai un modulo
burocratico (CLAUDE.md).

Regole non negoziabili, applicate in un solo punto verificabile
(`urban_memory.service`, mai bypassabile scrivendo direttamente su un
repository):

- `consenso` deve essere `True` per persistere — nessuna eccezione;
- `licenza` è sempre tracciata ed esplicita (es. "CC-BY-SA-4.0");
- `contributor_id` è uno pseudonimo obbligatorio, mai PII;
- `curato` parte sempre `False`: la pubblicazione richiede revisione umana;
- il servizio non logga mai il contenuto di un contributo.

Uso tipico::

    from urban_memory import (
        InMemoryMemoryRepository,
        submit_contribution, curate_contribution, contributions_for_place,
        ConsentRequiredError, LicenseRequiredError,
    )

    repo = InMemoryMemoryRepository()
    submit_contribution(repo, contribution)          # richiede consenso+licenza
    curate_contribution(repo, contribution.id)         # revisione umana
    contributions_for_place(repo, "bottega-liuteria-1")  # solo curati

Persistenza reale (Neon in cloud o Postgres locale — mai `if local/cloud`,
solo `DATABASE_URL`). Una tantum, applica la migrazione idempotente
(`python -m urban_memory.migrate`), poi::

    from urban_memory import PostgresMemoryRepository

    repo = PostgresMemoryRepository.from_env()  # legge DATABASE_URL
    submit_contribution(repo, contribution)      # persiste DAVVERO

Ogni contributo si aggancia inoltre al Knowledge Graph: `urban_memory.
graph_link.riguarda_to_cypher`/`riguarda_check_cypher` producono query pure
(`(:Memoria)-[:RIGUARDA]->(...)`); `link_to_graph`/`Neo4jMemoryLinker` le
eseguono davvero contro Neo4j (Aura o locale), ATOMICAMENTE: se un id in
`riguarda` non esiste nel grafo, `MemoryLinkError` lo nomina e NESSUN nodo
`:Memoria` orfano viene creato.
"""

from __future__ import annotations

from .graph_link import (
    MEMORY_LINK_CHECK_QUERY_PATH,
    MEMORY_LINK_WRITE_QUERY_PATH,
    MemoryLinkError,
    Neo4jMemoryLinker,
    link_to_graph,
    riguarda_check_cypher,
    riguarda_to_cypher,
)
from .migrate import SCHEMA_PATH, migrate
from .repository import (
    InMemoryMemoryRepository,
    MemoryRepository,
    MemoryStorageError,
    PostgresMemoryRepository,
)
from .service import (
    ConsentRequiredError,
    LicenseRequiredError,
    PseudonymRequiredError,
    UrbanMemoryError,
    contributions_for_place,
    curate_contribution,
    pending_contributions,
    publish_pending,
    submit_contribution,
)

__all__ = [
    "MemoryRepository",
    "InMemoryMemoryRepository",
    "PostgresMemoryRepository",
    "MemoryStorageError",
    "UrbanMemoryError",
    "ConsentRequiredError",
    "LicenseRequiredError",
    "PseudonymRequiredError",
    "submit_contribution",
    "curate_contribution",
    "publish_pending",
    "pending_contributions",
    "contributions_for_place",
    "riguarda_to_cypher",
    "riguarda_check_cypher",
    "MEMORY_LINK_CHECK_QUERY_PATH",
    "MEMORY_LINK_WRITE_QUERY_PATH",
    "MemoryLinkError",
    "link_to_graph",
    "Neo4jMemoryLinker",
    "migrate",
    "SCHEMA_PATH",
]
