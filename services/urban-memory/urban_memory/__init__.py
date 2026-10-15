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

CLI e strumenti operativi NON sono riesposti dalla radice (così `python -m
urban_memory.<modulo>` parte senza warning): importali dal sottomodulo —
`urban_memory.migrate` (`migrate`, `SCHEMA_PATH`, `SCHEMA_PATHS`),
`urban_memory.audit` (`audit`), `urban_memory.link` (`link_memory`,
`controprova`).

`MemoryRepository.get(memory_id)` rilegge un contributo per id (`None` se
assente); `list_curated()` rilegge TUTTI i contributi `curato=True`, su
qualunque place. `urban_memory.link.link_memory` (`python -m urban_memory.link`) usa `get` per
riagganciare al grafo IL DATO REALMENTE PERSISTITO, mai un oggetto
ricostruito in memoria — è lo strumento dedicato a verificare (e
rieseguire) SOLO l'aggancio, a valle di `urban_memory.verify`. `urban_memory.link.controprova`
dimostra che il linker rifiuta DAVVERO un target inesistente, senza toccare
Postgres.

La validazione dell'esistenza dei target sta ALLA CURATELA, non al
conferimento (decisione architetturale, bug reale corretto: un contributo
con un id inesistente nel grafo era arrivato a `curato=True`): `curate_
contribution`/`publish_pending` accettano un `target_checker` — tipicamente
`Neo4jMemoryLinker.targets_mancanti`, o il context manager `target_checker_
from_env()` — e sollevano `InvalidTargetsError` (nominando gli id mancanti,
senza toccare il repository) se il grafo non li conosce ancora.
`python -m urban_memory.audit` scova, su Neon+Aura, i contributi curati
PRIMA di questa correzione che sono rimasti con target invalidi.

"Curato tira aggancio" (`docs/ENGINE_INVARIANTS.md` §11-B): `curate_
contribution`/`publish_pending` accettano ANCHE un `linker` (tipicamente
`Neo4jMemoryLinker.link`) — se fornito, l'aggancio al grafo è innescato
AUTOMATICAMENTE subito dopo `curato=True`, nella stessa chiamata, per
ENTRAMBI i repository. `MemoryContribution.stato_aggancio` (`contracts.
MemoryLinkState`) registra l'esito: `AGGANCIATO`, o `AGGANCIO_FALLITO` — uno
stato di ATTESA RECUPERABILE (in questo repository sempre di causa
infrastrutturale: l'invariante A esclude un target sparito), mai un vicolo
cieco: `retry_link_contribution(repo, memory_id, linker=...)` riprova più
tardi, quando il grafo torna raggiungibile.
"""

from __future__ import annotations

from .canale_fluttuante import (
    DURATA_MASSIMA_SEGNALE_MIN,
    PlaceLinkWriter,
    SegnaleDurataEccessivaError,
    persist_signal,
    sweep_and_fetch_active,
)
from .cestino_repository import (
    CestinoStorageError,
    InMemoryPatternCestinatoRepository,
    PatternCestinato,
    PatternCestinatoRepository,
    PostgresPatternCestinatoRepository,
)
from .freno_repository import (
    FrenoStorageError,
    InMemoryPatternFrenatoRepository,
    PatternFrenato,
    PatternFrenatoRepository,
    PostgresPatternFrenatoRepository,
)
from .graph_link import (
    MEMORY_LINK_CHECK_QUERY_PATH,
    MEMORY_LINK_WRITE_QUERY_PATH,
    MemoryLinkError,
    Neo4jMemoryLinker,
    link_to_graph,
    riguarda_check_cypher,
    riguarda_to_cypher,
    target_checker_from_env,
)
from .luogo_traccia_link import (
    LUOGO_TRACCIA_WRITE_QUERY_PATH,
    LuogoTracciaLinkError,
    Neo4jLuogoTracciaLinker,
    scrivi_ultima_traccia,
    ultima_traccia_cypher,
)
from .promozione_evento import (
    PROMOZIONE_EVENTO_WRITE_QUERY_PATH,
    Neo4jPromozioneWriter,
    PromozioneEventoError,
    evento_id_per_pattern,
    promozione_evento_cypher,
    scrivi_evento_promosso,
)
from .repository import (
    InMemoryMemoryRepository,
    MemoryRepository,
    MemoryStorageError,
    PostgresMemoryRepository,
)
from .ricorrenza import (
    N_MINIMO_OCCORRENZE,
    TOLLERANZA_REGOLARITA,
    PatternCandidato,
    rileva_candidati,
)
from .segnale_repository import (
    InMemorySegnaleFluttuanteRepository,
    PostgresSegnaleFluttuanteRepository,
    SegnaleFluttuanteRepository,
    SegnaleStorageError,
)
from .service import (
    ConsentRequiredError,
    InvalidTargetsError,
    LicenseRequiredError,
    PseudonymRequiredError,
    UrbanMemoryError,
    contributions_for_place,
    curate_contribution,
    pending_contributions,
    publish_pending,
    retry_link_contribution,
    submit_contribution,
)
from .traccia_repository import (
    InMemoryTracciaRepository,
    PatternAggregato,
    PostgresTracciaRepository,
    Traccia,
    TracciaRepository,
    TracciaStorageError,
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
    "InvalidTargetsError",
    "submit_contribution",
    "curate_contribution",
    "publish_pending",
    "retry_link_contribution",
    "pending_contributions",
    "contributions_for_place",
    "riguarda_to_cypher",
    "riguarda_check_cypher",
    "MEMORY_LINK_CHECK_QUERY_PATH",
    "MEMORY_LINK_WRITE_QUERY_PATH",
    "MemoryLinkError",
    "link_to_graph",
    "Neo4jMemoryLinker",
    "target_checker_from_env",
    # Canale fluttuante persistente (Fase 3, docs/PROMOZIONE_TRACCIA.md)
    "SegnaleFluttuanteRepository",
    "InMemorySegnaleFluttuanteRepository",
    "PostgresSegnaleFluttuanteRepository",
    "SegnaleStorageError",
    "Traccia",
    "TracciaRepository",
    "InMemoryTracciaRepository",
    "PostgresTracciaRepository",
    "TracciaStorageError",
    "PatternAggregato",
    "PlaceLinkWriter",
    "persist_signal",
    "DURATA_MASSIMA_SEGNALE_MIN",
    "SegnaleDurataEccessivaError",
    "sweep_and_fetch_active",
    "LUOGO_TRACCIA_WRITE_QUERY_PATH",
    "ultima_traccia_cypher",
    "LuogoTracciaLinkError",
    "scrivi_ultima_traccia",
    "Neo4jLuogoTracciaLinker",
    # Rilevamento cadenza + promozione a :Evento + cestino permanente
    # (Fase 3, curatela umana via `python -m urban_memory.curatela_pattern`)
    "PatternCestinato",
    "PatternCestinatoRepository",
    "InMemoryPatternCestinatoRepository",
    "PostgresPatternCestinatoRepository",
    "CestinoStorageError",
    "N_MINIMO_OCCORRENZE",
    "TOLLERANZA_REGOLARITA",
    "PatternCandidato",
    "rileva_candidati",
    "PROMOZIONE_EVENTO_WRITE_QUERY_PATH",
    "evento_id_per_pattern",
    "promozione_evento_cypher",
    "PromozioneEventoError",
    "scrivi_evento_promosso",
    "Neo4jPromozioneWriter",
    # Freno di emergenza (Fase 3, docs/STATE_MACHINE.md §4-bis(b),
    # `python -m urban_memory.freno_pattern tira|rilascia`). Il log
    # (`PatternFrenatoRepository`) è esportato qui — stesso principio di
    # `PatternCestinatoRepository` sopra; `Neo4jFrenoClient`/`tira_freno`/
    # `rilascia_freno` restano NON riesportati (vivono solo in
    # `urban_memory.freno_pattern`, importati dal sottomodulo direttamente
    # da chi li usa — stesso principio di `Neo4jFrizioneClient`, vedi
    # `services/api/api/deps.py`).
    "PatternFrenato",
    "PatternFrenatoRepository",
    "InMemoryPatternFrenatoRepository",
    "PostgresPatternFrenatoRepository",
    "FrenoStorageError",
]
