"""Errori INFRASTRUTTURALI dell'Urban Knowledge Graph.

`GraphUnavailableError` significa "il Knowledge Graph non risponde": Aura in
pausa (scenario NORMALE, vedi CLAUDE.md), rete o DNS assenti, credenziali
non valide, sessione scaduta, cluster in failover. NON è un errore di
dominio e NON copre bug di programmazione (TypeError, KeyError, Cypher
sintatticamente errato): quelli devono emergere come tali.

Il messaggio è fisso e privo di dettagli del DSN (URI, host, username,
password): la causa originale del driver resta ispezionabile via
`__cause__`, ma non va mai loggata/serializzata verso il client.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from neo4j.exceptions import AuthError, DriverError, ResultError, TransientError

__all__ = ["GraphUnavailableError", "translate_driver_errors"]


class GraphUnavailableError(Exception):
    """Il Knowledge Graph (Neo4j/Aura) non è raggiungibile o non risponde."""

    def __init__(self, message: str = "Knowledge Graph non disponibile.") -> None:
        super().__init__(message)


# Perimetro: errori di connettività/sessione/autenticazione/transienti.
# `ResultError` (uso scorretto del risultato) e gli altri `ClientError`
# (es. CypherSyntaxError) sono bug di programmazione: NON si convertono.
_UNAVAILABLE = (DriverError, AuthError, TransientError)


@contextmanager
def translate_driver_errors() -> Iterator[None]:
    """Converte gli errori di infrastruttura del driver in
    `GraphUnavailableError` (incatenata con `from exc`)."""
    try:
        yield
    except ResultError:
        raise
    except _UNAVAILABLE as exc:
        raise GraphUnavailableError() from exc
