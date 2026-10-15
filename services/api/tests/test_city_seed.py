"""`get_candidate_source` sceglie il dataset della città da `CITY_SEED` tramite
`api.settings.Settings` (nessuna seconda lettura del `.env`).

Isolamento: `Settings` legge `.env` con path RELATIVO al cwd, quindi i test
fanno chdir in una directory vuota (il `.env` reale del repo non viene mai
letto) e rimuovono dall'ambiente le variabili NEO4J_* / CITY_SEED per forzare
il ramo di fallback sul dataset.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from api import deps
from api.settings import get_settings
from graph.dataset import DatasetCitta
from graph.registro import carica_dataset
from graph.source import SeedCandidateSource


@pytest.fixture(autouse=True)
def ambiente_isolato(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)  # nessun .env nel cwd
    for var in (
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "NEO4J_DATABASE",
        "CITY_SEED",
    ):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    deps.get_candidate_source.cache_clear()
    yield
    get_settings.cache_clear()
    deps.get_candidate_source.cache_clear()


def test_senza_city_seed_usa_il_dataset_predefinito() -> None:
    assert get_settings().city_seed is None
    source = deps.get_candidate_source()
    assert isinstance(source, SeedCandidateSource)
    predefinito = carica_dataset(None)
    assert source._esperienze == predefinito.esperienze


def test_city_seed_invalido_fallisce_in_modo_leggibile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CITY_SEED", "nessuna-citta")
    get_settings.cache_clear()
    deps.get_candidate_source.cache_clear()
    with pytest.raises(ValueError, match="nessuna_citta"):
        deps.get_candidate_source()


def test_city_seed_passa_per_settings_al_registro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visti: list[str | None] = []

    def spia(nome: str | None) -> DatasetCitta:
        visti.append(nome)
        return carica_dataset(None)

    monkeypatch.setattr(deps, "carica_dataset", spia)
    monkeypatch.setenv("CITY_SEED", "qualche-slug")
    get_settings.cache_clear()
    deps.get_candidate_source.cache_clear()
    deps.get_candidate_source()
    assert visti == ["qualche-slug"]


def test_city_seed_invalido_fallisce_anche_con_credenziali_neo4j(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def non_deve_essere_chiamato(*args: object, **kwargs: object) -> object:
        raise AssertionError("nessuna connessione Neo4j con CITY_SEED invalido")

    monkeypatch.setattr(
        deps.Neo4jCandidateSource, "from_credentials", non_deve_essere_chiamato
    )
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://finto.invalid")
    monkeypatch.setenv("NEO4J_USERNAME", "finto")
    monkeypatch.setenv("NEO4J_PASSWORD", "finto")
    monkeypatch.setenv("CITY_SEED", "nessuna-citta")
    get_settings.cache_clear()
    deps.get_candidate_source.cache_clear()
    with pytest.raises(ValueError, match="nessuna_citta"):
        deps.get_candidate_source()
