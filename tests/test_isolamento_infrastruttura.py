"""Isolamento dei test dall'infrastruttura reale (Neon/Aura).

Prova che il conftest di radice funziona: nessuna variabile di infrastruttura
nell'ambiente, nessun `.env` visibile ai lettori, getter su Seed/InMemory, e la
logica di skip del marker `reale`.
"""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

RADICE = Path(__file__).resolve().parents[1]

VARIABILI = (
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
)


@pytest.mark.parametrize("nome", VARIABILI)
def test_variabile_di_infrastruttura_assente_dall_ambiente(nome: str) -> None:
    assert nome not in os.environ


def test_lettori_neo4j_senza_argomenti_non_trovano_nulla() -> None:
    from graph.env import load_neo4j_config
    from urban_memory._env import neo4j_config_from_env

    with pytest.raises(ValueError):
        load_neo4j_config()
    with pytest.raises(ValueError):
        neo4j_config_from_env()


MODULI_DB = ["urban_memory._env", "intelligence_index._env", "marketplace._env", "recommender._env"]


@pytest.mark.parametrize("modulo", MODULI_DB)
def test_lettori_database_url_senza_argomenti_non_trovano_nulla(modulo: str) -> None:
    with pytest.raises(ValueError):
        importlib.import_module(modulo).database_url_from_env()


def test_city_seed_da_env_non_legge_il_env_reale() -> None:
    from graph.env import city_seed_da_env

    assert city_seed_da_env() is None or "CITY_SEED" in os.environ


@pytest.mark.parametrize("modulo", ["graph.env", *MODULI_DB])
def test_repo_root_sostituito_senza_env(modulo: str) -> None:
    cartella = importlib.import_module(modulo)._repo_root()
    assert not (cartella / ".env").exists()


def test_settings_senza_infrastruttura() -> None:
    from api.settings import ENV_FILE, get_settings

    assert not ENV_FILE.exists()
    impostazioni = get_settings()
    assert impostazioni.neo4j_uri is None
    assert impostazioni.database_url is None


def test_getter_di_deps_scelgono_seed_e_inmemory() -> None:
    from api import deps
    from graph.source import Neo4jCandidateSource, SeedCandidateSource

    sorgente = deps.get_candidate_source()
    assert isinstance(sorgente, SeedCandidateSource)
    assert not isinstance(sorgente, Neo4jCandidateSource)
    assert type(deps.get_memory_repository()).__name__.startswith("InMemory")
    assert type(deps.get_booking_repository()).__name__.startswith("InMemory")
    assert type(deps.get_event_repository()).__name__.startswith("InMemory")
    assert type(deps.get_segnale_repository()).__name__.startswith("InMemory")
    assert type(deps.get_traccia_repository()).__name__.startswith("InMemory")
    assert deps.get_place_link_writer() is None
    assert deps.get_evento_reader() is None


def test_le_cache_sono_svuotate_tra_i_test_a() -> None:
    from api.settings import get_settings

    get_settings()
    assert get_settings.cache_info().currsize == 1


def test_le_cache_sono_svuotate_tra_i_test_b() -> None:
    from api.settings import get_settings

    assert get_settings.cache_info().currsize == 0


# --- marker `reale`: logica di skip eseguita davvero in un pytest figlio ----------

TEST_FIGLIO = '''
import os
import pytest

@pytest.mark.reale
def test_reale():
    assert os.environ.get("DATABASE_URL") == "postgresql://finto/db"
    from api.settings import ENV_FILE
    assert ENV_FILE.name == ".env"

def test_normale():
    assert "DATABASE_URL" not in os.environ
'''


def _figlio(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, **ambiente: str | None
) -> pytest.RunResult:
    shutil.copy(RADICE / "conftest.py", pytester.path / "conftest.py")
    pytester.makepyfile(test_figlio=TEST_FIGLIO)
    for chiave in ("CI", "LSL_TEST_REALE"):
        monkeypatch.delenv(chiave, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://finto/db")
    for chiave, valore in ambiente.items():
        if valore is None:
            monkeypatch.delenv(chiave, raising=False)
        else:
            monkeypatch.setenv(chiave, valore)
    return pytester.runpytest_subprocess("-rs", "-p", "no:cacheprovider")


def test_marker_reale_saltato_senza_variabile(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    risultato = _figlio(pytester, monkeypatch)
    risultato.assert_outcomes(passed=1, skipped=1)
    risultato.stdout.fnmatch_lines(["*impostare LSL_TEST_REALE=1*"])


def test_marker_reale_saltato_in_ci_anche_con_la_variabile(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    risultato = _figlio(pytester, monkeypatch, LSL_TEST_REALE="1", CI="true")
    risultato.assert_outcomes(passed=1, skipped=1)
    risultato.stdout.fnmatch_lines(["*mai eseguito in CI*"])


def test_marker_reale_eseguito_con_variabile_fuori_ci_e_ripristina_ambiente(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    risultato = _figlio(pytester, monkeypatch, LSL_TEST_REALE="1")
    # test_reale vede DATABASE_URL originale; test_normale (senza marker) no.
    risultato.assert_outcomes(passed=2)
