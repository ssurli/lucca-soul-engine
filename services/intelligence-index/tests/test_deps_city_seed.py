"""`intelligence_index.deps`: i fallback seed usano il dataset di `CITY_SEED`,
letto dallo STESSO `merged_env()` delle credenziali.

L'ambiente è isolato monkeypatchando `deps.merged_env` (il repo ha un `.env`
reale: pulire `os.environ` non basterebbe, vedi `test_deps.py`)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from graph.registro import carica_dataset
from graph.source import SeedCandidateSource
from intelligence_index import deps


@pytest.fixture(autouse=True)
def _pulisci_cache() -> Iterator[None]:
    deps.get_candidate_source.cache_clear()
    deps.get_metrics_source.cache_clear()
    yield
    deps.get_candidate_source.cache_clear()
    deps.get_metrics_source.cache_clear()


def _env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    monkeypatch.setattr(deps, "merged_env", lambda: env)


def test_city_seed_assente_usa_il_dataset_predefinito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, {})
    fonte = deps.get_candidate_source()
    assert isinstance(fonte, SeedCandidateSource)
    assert list(fonte._esperienze) == list(carica_dataset(None).esperienze)
    assert deps.get_metrics_source().grado_semantico()


def test_city_seed_esplicito_equivale_al_predefinito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nome = carica_dataset(None).nome
    _env(monkeypatch, {"CITY_SEED": nome})
    assert isinstance(deps.get_candidate_source(), SeedCandidateSource)


@pytest.mark.parametrize("valore", ["Non Valido!", "../x", "citta-inesistente-xyz"])
def test_city_seed_invalido_solleva_value_error(
    monkeypatch: pytest.MonkeyPatch, valore: str
) -> None:
    _env(monkeypatch, {"CITY_SEED": valore})
    with pytest.raises(ValueError, match="CITY_SEED"):
        deps.get_candidate_source()
    with pytest.raises(ValueError, match="CITY_SEED"):
        deps.get_metrics_source()


def _vieta_connessioni(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no(*_a: object, **_k: object) -> None:
        raise AssertionError("connessione Neo4j aperta con CITY_SEED invalido")

    monkeypatch.setattr(deps.Neo4jCandidateSource, "from_credentials", _no)
    monkeypatch.setattr(deps.Neo4jMetricsSource, "from_credentials", _no)


def test_city_seed_invalido_fallisce_anche_con_credenziali_neo4j(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _vieta_connessioni(monkeypatch)
    _env(
        monkeypatch,
        {
            "NEO4J_URI": "neo4j+s://finto.invalid",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
            "CITY_SEED": "Non Valido!",
        },
    )
    with pytest.raises(ValueError, match="CITY_SEED"):
        deps.get_candidate_source()
    with pytest.raises(ValueError, match="CITY_SEED"):
        deps.get_metrics_source()
