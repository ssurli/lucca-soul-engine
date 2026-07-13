"""Dipendenze del BFF: selezione della fonte dei candidati del grafo.

Il codice non sa MAI se `NEO4J_URI` punta ad Aura (`neo4j+s://`) o a Neo4j
Community locale (`bolt://`): legge solo se le credenziali sono presenti nel
`.env`. Se configurate, usa `Neo4jCandidateSource`; altrimenti ricade sul
seed versionato (`SeedCandidateSource`) — lo stesso dataset canonico, mai un
dataset diverso a seconda del profilo (cloud/locale).

L'istanza è creata una sola volta (`lru_cache`): aprire un driver Neo4j a
ogni richiesta sarebbe costoso e inutile.
"""

from __future__ import annotations

from functools import lru_cache

from graph.source import CandidateSource, Neo4jCandidateSource, SeedCandidateSource

from api.settings import get_settings

__all__ = ["get_candidate_source"]


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
