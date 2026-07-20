"""Test di `intelligence_index.deps` — la scelta Seed/Neo4j e In-Memory/
Postgres, in base al `.env`.

NON basta pulire `os.environ` (`monkeypatch.delenv`): questo repo ha un
`.env` REALE alla radice, con `NEO4J_URI`/`DATABASE_URL` configurati (Neon +
Aura di sviluppo) — `merged_env()` (`intelligence_index._env`) legge SEMPRE
quel file, indipendentemente da `os.environ`. Testare l'assenza cancellando
solo le variabili di processo darebbe un falso verde in locale e un vero
rosso in CI (dove il file non esiste): stessa trappola già documentata in
`services/api/tests/test_booking.py` ("in un ambiente con `.env` che ha
`NEO4J_URI` configurato, quel default [...] monkeypatch.setattr(...)").
Si monkeypatcha quindi `deps.merged_env` stesso, non l'ambiente."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from graph.metrics import Neo4jMetricsSource, SeedMetricsSource
from graph.source import Neo4jCandidateSource, SeedCandidateSource
from intelligence_index import deps
from intelligence_index.repository import InMemoryBehaviorEventSource, PostgresBehaviorEventSource
from urban_memory import InMemoryMemoryRepository, PostgresMemoryRepository


@pytest.fixture(autouse=True)
def _pulisci_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`get_*` sono `@lru_cache`: senza pulizia, il primo test che le chiama
    "congela" il risultato per tutti i test successivi."""
    for funzione in (
        deps.get_candidate_source,
        deps.get_metrics_source,
        deps.get_event_source,
        deps.get_memory_repository,
    ):
        funzione.cache_clear()
    yield
    for funzione in (
        deps.get_candidate_source,
        deps.get_metrics_source,
        deps.get_event_source,
        deps.get_memory_repository,
    ):
        funzione.cache_clear()


def _forza_ambiente_vuoto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "merged_env", lambda: {})


def _forza_ambiente_configurato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deps,
        "merged_env",
        lambda: {
            "NEO4J_URI": "neo4j+s://esempio.databases.neo4j.io",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password-di-prova",
            "NEO4J_DATABASE": "neo4j",
            "DATABASE_URL": "postgresql://esempio/db?sslmode=require",
        },
    )


# ---------------------------------------------------------------------------
# Ambiente VUOTO: ricade sui percorsi locali/in-memory
# ---------------------------------------------------------------------------


def test_get_candidate_source_ricade_sul_seed_senza_neo4j_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_vuoto(monkeypatch)
    assert isinstance(deps.get_candidate_source(), SeedCandidateSource)


def test_get_metrics_source_ricade_sul_seed_senza_neo4j_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_vuoto(monkeypatch)
    assert isinstance(deps.get_metrics_source(), SeedMetricsSource)


def test_get_event_source_ricade_su_in_memory_senza_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_vuoto(monkeypatch)
    assert isinstance(deps.get_event_source(), InMemoryBehaviorEventSource)


def test_get_memory_repository_ricade_su_in_memory_senza_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_vuoto(monkeypatch)
    assert isinstance(deps.get_memory_repository(), InMemoryMemoryRepository)


def test_get_candidate_source_e_una_singleton_cacheata(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_ambiente_vuoto(monkeypatch)
    assert deps.get_candidate_source() is deps.get_candidate_source()


# ---------------------------------------------------------------------------
# Ambiente CONFIGURATO: sceglie Neo4j/Postgres (nessuna connessione reale
# tentata alla sola costruzione — stesso comportamento documentato in
# `graph.source.Neo4jCandidateSource`/`recommender.PostgresBehaviorEventRepository`)
# ---------------------------------------------------------------------------


def test_get_candidate_source_sceglie_neo4j_con_credenziali_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_configurato(monkeypatch)
    source = deps.get_candidate_source()
    try:
        assert isinstance(source, Neo4jCandidateSource)
    finally:
        source.close()  # nessuna connessione reale tentata, ma chiude il driver aperto qui


def test_get_metrics_source_sceglie_neo4j_con_credenziali_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_configurato(monkeypatch)
    source = deps.get_metrics_source()
    try:
        assert isinstance(source, Neo4jMetricsSource)
    finally:
        source.close()


def test_get_event_source_sceglie_postgres_con_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_configurato(monkeypatch)
    assert isinstance(deps.get_event_source(), PostgresBehaviorEventSource)


def test_get_memory_repository_sceglie_postgres_con_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forza_ambiente_configurato(monkeypatch)
    assert isinstance(deps.get_memory_repository(), PostgresMemoryRepository)
