"""Dipendenze del BFF: selezione della fonte dei candidati del grafo e del
repository di Urban Memory.

Il codice non sa MAI se `NEO4J_URI` punta ad Aura (`neo4j+s://`) o a Neo4j
Community locale (`bolt://`): legge solo se le credenziali sono presenti nel
`.env`. Se configurate, usa `Neo4jCandidateSource`; altrimenti ricade sul
seed versionato (`SeedCandidateSource`) — lo stesso dataset canonico, mai un
dataset diverso a seconda del profilo (cloud/locale).

L'istanza è creata una sola volta (`lru_cache`): aprire un driver Neo4j a
ogni richiesta sarebbe costoso e inutile. Stesso pattern per
`get_memory_repository` (Urban Memory, Wave 2).
"""

from __future__ import annotations

from functools import lru_cache

from graph.source import CandidateSource, Neo4jCandidateSource, SeedCandidateSource
from urban_memory import (
    InMemoryMemoryRepository,
    MemoryRepository,
    MemoryStorageError,
    PostgresMemoryRepository,
)

from api.settings import get_settings

__all__ = ["get_candidate_source", "get_memory_repository"]


@lru_cache
def get_candidate_source() -> CandidateSource:
    """Sceglie la fonte dei candidati in base al `.env`, una volta sola.

    `Neo4jCandidateSource` richiede URI + username + password; se anche solo
    una delle tre manca, il BFF non tenta la connessione e ricade sul seed
    (evita di rompere l'avvio quando la configurazione è parziale).
    """
    settings = get_settings()
    if settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password:
        return Neo4jCandidateSource.from_credentials(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database or "neo4j",
        )
    return SeedCandidateSource()


@lru_cache
def get_memory_repository() -> MemoryRepository:
    """Sceglie il repository di Urban Memory in base al `.env`, una volta
    sola — stesso pattern di `get_candidate_source`: nessun `if
    local/cloud`, solo presenza di `DATABASE_URL`.

    Se `DATABASE_URL` è configurato usa `PostgresMemoryRepository` (Neon in
    cloud o Postgres locale — stesso codice nei due profili, cambia solo il
    DSN): persiste DAVVERO, con connessione lazy per operazione (nessun
    tentativo di rete qui, all'istanziazione — va bene costruirla anche a
    database non ancora raggiungibile o migrazione non ancora applicata: il
    fallimento emerge alla prima operazione reale su `/memory`, non qui).
    Altrimenti ricade su `InMemoryMemoryRepository` (in-process, non
    persiste tra riavvii — è il percorso verificato dallo smoke test di
    questo servizio quando `DATABASE_URL` non è impostato).

    Ogni errore infrastrutturale di storage (connessione, credenziali,
    query fallita) è responsabilità esclusiva di
    `urban_memory.repository.PostgresMemoryRepository`, che lo mappa già in
    `MemoryStorageError` — mai lasciato propagare come eccezione psycopg
    grezza. Questa funzione non implementa NESSUNA logica di database: si
    limita ad avvolgere in `MemoryStorageError` anche un eventuale
    fallimento della sola costruzione (`from_env()`, che legge
    `DATABASE_URL` e può sollevare `ValueError` se la variabile risulta
    assente qui pur essendo vista come presente da `api.settings.Settings`
    — stesso `.env`, letture indipendenti), così che
    `api.main.memory_storage_error_handler` (503, mai un 500 opaco) catturi
    ANCHE questo caso, non solo i fallimenti nelle operazioni successive.
    """
    settings = get_settings()
    if settings.database_url:
        try:
            return PostgresMemoryRepository.from_env()
        except MemoryStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise MemoryStorageError(
                "impossibile inizializzare la persistenza di Urban Memory"
            ) from exc
    return InMemoryMemoryRepository()
