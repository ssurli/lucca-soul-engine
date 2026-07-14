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
from urban_memory import InMemoryMemoryRepository, MemoryRepository, PostgresMemoryRepository

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

    ATTENZIONE (Wave 2): `PostgresMemoryRepository` è predisposta ma NON
    ancora implementata (`urban_memory.repository` — ogni metodo solleva
    `NotImplementedError`: nessun database è raggiungibile da lì in questa
    wave). Finché resta uno stub, configurare `DATABASE_URL` fa scegliere
    `PostgresMemoryRepository` e `/memory` e `/memory/{place_id}` falliscono
    con un errore esplicito (mai un dato silenziosamente perso). In Wave 2
    offline (nessun `DATABASE_URL`) si usa sempre `InMemoryMemoryRepository`:
    è il percorso verificato dallo smoke test di questo servizio. La
    sostituzione arriva quando `PostgresMemoryRepository` sarà implementata,
    senza cambiare questa funzione.
    """
    settings = get_settings()
    if settings.database_url:
        return PostgresMemoryRepository.from_env()
    return InMemoryMemoryRepository()
