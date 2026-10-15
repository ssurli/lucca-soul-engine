"""`Settings` legge il `.env` ancorato alla radice del repo, non al cwd."""

from __future__ import annotations

from pathlib import Path

import pytest
from api import settings as api_settings
from api.settings import get_settings


@pytest.fixture(autouse=True)
def _cache() -> object:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_env_file_predefinito_e_la_radice_del_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    # Il conftest di radice ripunta `ENV_FILE` a un file inesistente (isolamento
    # dall'infrastruttura reale): il default del codice e' `RADICE_REPO / ".env"`.
    predefinito = api_settings.RADICE_REPO / ".env"
    radice = predefinito.parent
    assert predefinito.name == ".env"
    assert (radice / "CLAUDE.md").is_file()
    assert (radice / "services").is_dir()
    assert predefinito.is_absolute()


def test_stessi_valori_da_cwd_diversi(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = tmp_path / "radice" / ".env"
    env.parent.mkdir()
    env.write_text("CITY_SEED=valore-test\nCITY_TZ=Europe/Rome\n", encoding="utf-8")
    monkeypatch.setattr(api_settings, "ENV_FILE", env)
    monkeypatch.delenv("CITY_SEED", raising=False)
    monkeypatch.delenv("CITY_TZ", raising=False)

    repo = api_settings.RADICE_REPO
    monkeypatch.chdir(repo)
    a = get_settings()
    get_settings.cache_clear()
    altro = tmp_path / "altro"
    altro.mkdir()
    monkeypatch.chdir(altro)
    b = get_settings()

    assert (a.city_seed, a.city_tz) == ("valore-test", "Europe/Rome")
    assert (b.city_seed, b.city_tz) == (a.city_seed, a.city_tz)


def test_ambiente_di_processo_ha_precedenza_sul_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text("CITY_SEED=dal-file\n", encoding="utf-8")
    monkeypatch.setattr(api_settings, "ENV_FILE", env)
    monkeypatch.setenv("CITY_SEED", "da-ambiente")
    assert get_settings().city_seed == "da-ambiente"
