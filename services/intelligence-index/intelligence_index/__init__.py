"""Lucca Soul Lab — Engine: Urban Intelligence Index (`services/intelligence-index`), Wave 4.

Gli indicatori — misura la salute CULTURALE della città, non solo quella
economica o infrastrutturale (CLAUDE.md). Import name del pacchetto:
`intelligence_index` (nome distribuzione: `lucca-intelligence-index`).

Calcola `contracts.UrbanIntelligenceIndex` per un periodo (`"YYYY-MM"`), a
partire SOLO da: `BehaviorEvent` (già persistiti da `recommender`), il
grafo (`grado_semantico`, snapshot `VICINO`, catalogo esperienze — via
`services/graph`) e Urban Memory (TUTTI i `MemoryContribution` del periodo,
indipendentemente da `curato` — via `services/urban-memory`, vedi
`intelligence_index.indicatori.contributi_memoria`). MAI dati
commerciali/partner, MAI click, conversioni o ricavi pubblicitari come input
(vedi il README del servizio).

Due regole non negoziabili, applicate in un solo punto verificabile:

- **Aggregazione e non re-identificazione** (`intelligence_index.soglia`):
  ogni indicatore richiede almeno `SOGLIA_MINIMA_PERSONE` (k=10) `person_id`
  distinti prima di essere pubblicato — sotto soglia,
  `calcola_index` solleva `DatiInsufficientiError`, mai un numero fabbricato.
- **`distribuzione_flussi` è l'indicatore che ci giudica** — misura
  DIRETTAMENTE l'overtourism (`intelligence_index.distribuzione`), la
  STESSA formula già usata come criterio di accettazione del Recommender
  (Wave 3b, `tests/test_integration_wave3b.py`): un'unica fonte di verità.

Uso tipico, offline (nessun database — la funzione pura di calcolo)::

    from intelligence_index import calcola_index
    from intelligence_index.catalogo import esperienze_per_id
    from graph.source import SeedCandidateSource
    from graph.metrics import SeedMetricsSource

    fonte_candidati = SeedCandidateSource()
    fonte_metriche = SeedMetricsSource()
    catalogo = esperienze_per_id(fonte_candidati)
    grado = fonte_metriche.grado_semantico()
    non_connesse, _ = fonte_metriche.non_connected_place_pairs(at=...)  # inizio periodo

    indice = calcola_index(
        periodo="2026-07",
        eventi=[...],                       # BehaviorEvent, es. da un repository
        esperienze_per_id=catalogo,
        grado_semantico=grado,
        n_luoghi_disponibili=len(grado),
        non_connesse_a_inizio_periodo=non_connesse,
        itinerari_periodo=[],               # buco nei dati noto, vedi README
        memorie=[...],                      # TUTTI i MemoryContribution del periodo
    )

Persistenza reale (Neon in cloud o Postgres locale — mai `if local/cloud`,
solo `DATABASE_URL`), via `intelligence_index.deps` (STESSO pattern di
`api.deps`, duplicato localmente per comodità di chi cablerà l'endpoint
dashboard in una wave successiva)::

    from intelligence_index import deps

    eventi = deps.get_event_source().events_in_period(inizio, fine)
    repo_memoria = deps.get_memory_repository()
    # "memorie" = TUTTI i contributi del periodo, non solo curato=True
    # (NEGOZIATA col committente — vedi indicatori.contributi_memoria):
    # unione di list_pending() e list_curated(), non un metodo dedicato.
    memorie = repo_memoria.list_pending() + repo_memoria.list_curated()
"""

from __future__ import annotations

from .catalogo import CONTESTO_NEUTRO_CATALOGO, esperienze_per_id
from .dashboard import celle_flusso, indice_per_dashboard
from .distribuzione import distribuzione_flussi
from .index import calcola_index
from .periodo import intervallo_periodo
from .repository import (
    BehaviorEventSource,
    IndexStorageError,
    InMemoryBehaviorEventSource,
    PostgresBehaviorEventSource,
)
from .soglia import (
    SOGLIA_MINIMA_PERSONE,
    DatiInsufficientiError,
    persone_sufficienti,
    richiedi_soglia,
    valore_se_soglia,
)

__all__ = [
    "calcola_index",
    "indice_per_dashboard",
    "celle_flusso",
    "intervallo_periodo",
    "distribuzione_flussi",
    "esperienze_per_id",
    "CONTESTO_NEUTRO_CATALOGO",
    "SOGLIA_MINIMA_PERSONE",
    "DatiInsufficientiError",
    "persone_sufficienti",
    "richiedi_soglia",
    "valore_se_soglia",
    "BehaviorEventSource",
    "InMemoryBehaviorEventSource",
    "PostgresBehaviorEventSource",
    "IndexStorageError",
]
