"""Selezione delle sorgenti reali — STESSO pattern già in uso in
`services/api/api/deps.py` (Wave 1+): nessun `if local/cloud` nel codice
chiamante, solo presenza delle variabili d'ambiente attese
(`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` per il grafo, `DATABASE_URL`
per Postgres). La scelta è duplicata QUI, non importata da
`services/api` (che DIPENDE dai servizi, mai il contrario) né da
`services/graph`/`services/urban-memory` (che non decidono da sé, vedi i
loro moduli — nessuno dei due ha un proprio `deps.py`): è la STESSA
convenzione già seguita da `recommender._env`/`urban_memory._env` (ognuno
con la propria copia minimale, deliberatamente non centralizzata).

SOLO costruttori, MAI logica di calcolo: `intelligence_index.index.
calcola_index` non importa MAI questo modulo (riceve tutto per iniezione,
stesso principio di `recommender.costruisci_score_fn`) — resta testabile
senza alcun database. Questo modulo esiste per comodità di chi cablerà
l'endpoint dashboard (`api-engineer`, fuori dal perimetro di questa wave):
un `import intelligence_index.deps` gli evita di riscrivere la stessa
selezione una terza volta.
"""

from __future__ import annotations

from functools import lru_cache

from graph.metrics import GraphMetricsSource, Neo4jMetricsSource, SeedMetricsSource
from graph.registro import carica_dataset
from graph.source import CandidateSource, Neo4jCandidateSource, SeedCandidateSource
from urban_memory import (
    InMemoryMemoryRepository,
    MemoryRepository,
    MemoryStorageError,
    PostgresMemoryRepository,
)

from ._env import merged_env
from .repository import (
    BehaviorEventSource,
    InMemoryBehaviorEventSource,
    PostgresBehaviorEventSource,
)

__all__ = [
    "get_candidate_source",
    "get_metrics_source",
    "get_event_source",
    "get_memory_repository",
]


def _credenziali_neo4j(env: dict[str, str]) -> tuple[str, str, str, str] | None:
    """`(uri, username, password, database)` se URI + username + password
    sono TUTTI presenti nel `.env` unito all'ambiente, altrimenti `None` —
    stesso criterio di `api.deps.get_candidate_source` (evita di rompere
    l'avvio quando la configurazione è parziale)."""
    uri = env.get("NEO4J_URI")
    username = env.get("NEO4J_USERNAME")
    password = env.get("NEO4J_PASSWORD")
    if not (uri and username and password):
        return None
    return uri, username, password, env.get("NEO4J_DATABASE") or "neo4j"


@lru_cache
def get_candidate_source() -> CandidateSource:
    """Sceglie la fonte del catalogo di esperienze (usata da
    `intelligence_index.catalogo.esperienze_per_id`) in base al `.env`, una
    volta sola. Senza credenziali Neo4j ricade sul seed del dataset scelto da
    `CITY_SEED` (letto dallo stesso `merged_env()`); `CITY_SEED` invalido ->
    `ValueError` leggibile, mai un degrado silenzioso."""
    env = merged_env()
    # Validato PRIMA del ramo: un CITY_SEED invalido fallisce in ogni profilo.
    dataset = carica_dataset(env.get("CITY_SEED"))
    credenziali = _credenziali_neo4j(env)
    if credenziali is None:
        return SeedCandidateSource(dataset)
    uri, username, password, database = credenziali
    return Neo4jCandidateSource.from_credentials(
        uri=uri, username=username, password=password, database=database
    )


@lru_cache
def get_metrics_source() -> GraphMetricsSource:
    """Sceglie la fonte di `grado_semantico`/`non_connected_place_pairs` in
    base al `.env`, una volta sola — stesso criterio di presenza (e stessa
    risoluzione di `CITY_SEED`) di `get_candidate_source` sopra."""
    env = merged_env()
    # Validato PRIMA del ramo: un CITY_SEED invalido fallisce in ogni profilo.
    dataset = carica_dataset(env.get("CITY_SEED"))
    credenziali = _credenziali_neo4j(env)
    if credenziali is None:
        return SeedMetricsSource(dataset)
    uri, username, password, database = credenziali
    return Neo4jMetricsSource.from_credentials(
        uri=uri, username=username, password=password, database=database
    )


@lru_cache
def get_event_source() -> BehaviorEventSource:
    """Sceglie la sorgente di `BehaviorEvent` grezzi in base al `.env`, una
    volta sola — stesso pattern di `api.deps.get_event_repository`, ma per
    la lettura di reporting (`events_in_period`), non per la scrittura
    (`POST /events`, che resta `recommender.BehaviorEventRepository`)."""
    env = merged_env()
    if env.get("DATABASE_URL"):
        try:
            return PostgresBehaviorEventSource(env["DATABASE_URL"])
        except ValueError:
            raise
    return InMemoryBehaviorEventSource()


@lru_cache
def get_memory_repository() -> MemoryRepository:
    """Sceglie il repository di Urban Memory in base al `.env`, una volta
    sola — stesso pattern di `api.deps.get_memory_repository`. Qui è usato
    SOLO in lettura (`list_curated()`, per `contributi_memoria`): la
    scrittura (`POST /memory`) resta responsabilità esclusiva del BFF."""
    env = merged_env()
    if env.get("DATABASE_URL"):
        try:
            return PostgresMemoryRepository(env["DATABASE_URL"])
        except MemoryStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise MemoryStorageError(
                "impossibile inizializzare la lettura di Urban Memory"
            ) from exc
    return InMemoryMemoryRepository()
