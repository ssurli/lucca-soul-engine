"""`GraphUnavailableError`: gli errori di infrastruttura del driver Neo4j
diventano un errore tipizzato SENZA dettagli del DSN; i bug no. Driver finto,
nessuna connessione reale."""

from __future__ import annotations

from datetime import time
from typing import Any

import pytest
from contracts import EmotionalProfile, Signal, VisitorContext
from graph import GraphUnavailableError
from graph.metrics import Neo4jMetricsSource
from graph.source import Neo4jCandidateSource
from neo4j.exceptions import (
    AuthError,
    CypherSyntaxError,
    ServiceUnavailable,
    SessionExpired,
)

SECRET_URI = "neo4j+s://abc123.databases.neo4j.io"
SECRET_USER = "utente-segreto"
SECRET_PWD = "password-segreta"


class _Session:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def run(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._exc


class _Driver:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def session(self, **_kwargs: Any) -> _Session:
        return _Session(self._exc)

    def close(self) -> None:
        return None


def _ctx() -> VisitorContext:
    return VisitorContext(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.5,
            contemplazione=0.5,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=120,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
    )


@pytest.mark.parametrize(
    "exc",
    [
        ServiceUnavailable(f"Failed to DNS resolve address {SECRET_URI}:7687"),
        SessionExpired(f"Session expired for {SECRET_USER}"),
        AuthError(f"bad credentials {SECRET_USER}/{SECRET_PWD}"),
    ],
)
def test_candidates_converte_errori_infrastrutturali(exc: BaseException) -> None:
    source = Neo4jCandidateSource(_Driver(exc))  # type: ignore[arg-type]
    with pytest.raises(GraphUnavailableError) as info:
        source.candidates(_ctx())
    assert info.value.__cause__ is exc
    messaggio = str(info.value)
    for segreto in (SECRET_URI, "abc123", SECRET_USER, SECRET_PWD, "DNS"):
        assert segreto not in messaggio


def test_metrics_converte_errori_infrastrutturali() -> None:
    exc = ServiceUnavailable(f"unreachable {SECRET_URI}")
    source = Neo4jMetricsSource(_Driver(exc))  # type: ignore[arg-type]
    with pytest.raises(GraphUnavailableError) as g:
        source.grado_semantico()
    assert g.value.__cause__ is exc
    with pytest.raises(GraphUnavailableError):
        source.non_connected_place_pairs()


def test_bug_di_programmazione_non_convertiti() -> None:
    source = Neo4jCandidateSource(_Driver(TypeError("bug")))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        source.candidates(_ctx())
    source = Neo4jCandidateSource(_Driver(KeyError("x")))  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        source.candidates(_ctx())
    source = Neo4jCandidateSource(_Driver(CypherSyntaxError("sintassi")))  # type: ignore[arg-type]
    with pytest.raises(CypherSyntaxError):
        source.candidates(_ctx())


def test_graph_unavailable_non_e_errore_di_dominio_builtin() -> None:
    assert not issubclass(GraphUnavailableError, (TypeError, KeyError, ValueError))
