"""Conftest di RADICE: isolamento dei test dall'infrastruttura reale (Neon/Aura).

Vale per ENTRAMBE le invocazioni della CI (`pytest` e `pytest services/...`):
un conftest in `tests/` non verrebbe caricato nella seconda.

Prima della collection (`pytest_configure`, quindi prima che `api.main` venga
importato e chiami `get_settings()`):

- le variabili di infrastruttura vengono tolte da `os.environ` (e salvate);
- il `.env` reale non e' visibile a nessuno dei SEI lettori: `api.settings.ENV_FILE`
  punta a un file inesistente e `_repo_root` dei cinque moduli `_env`/`env` punta
  a una cartella temporanea senza `.env`.

Cosi', anche con un `.env` reale sul disco, i getter di `api.deps` scelgono
Seed/InMemory e nessun test scrive su Neon o Aura.

Un test che DEVE parlare con l'infrastruttura reale si marca `@pytest.mark.reale`:
viene saltato salvo `LSL_TEST_REALE=1`, e sempre saltato se e' impostata `CI`.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

VARIABILI_INFRASTRUTTURA = (
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",  # rag/reasons.py chiama l'API Anthropic se la chiave c'e'
)

# Moduli che cablano `_repo_root() / ".env"`.
MODULI_REPO_ROOT = (
    "graph.env",
    "urban_memory._env",
    "intelligence_index._env",
    "marketplace._env",
    "recommender._env",
)

# Moduli con getter `lru_cache` da svuotare (solo se gia' importati).
MODULI_CON_CACHE = ("api.settings", "api.deps", "intelligence_index.deps")

_stato: dict[str, Any] = {}


def _svuota_cache() -> None:
    for nome in MODULI_CON_CACHE:
        modulo = sys.modules.get(nome)
        if modulo is None:
            continue
        for oggetto in vars(modulo).values():
            svuota = getattr(oggetto, "cache_clear", None)
            if callable(svuota):
                svuota()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "reale: test che usa l'infrastruttura reale (Neon/Aura); saltato salvo "
        "LSL_TEST_REALE=1 e mai eseguito in CI",
    )

    originali_env = {k: os.environ[k] for k in VARIABILI_INFRASTRUTTURA if k in os.environ}
    for chiave in VARIABILI_INFRASTRUTTURA:
        os.environ.pop(chiave, None)

    senza_env = Path(tempfile.mkdtemp(prefix="lsl-senza-env-"))
    api_settings = importlib.import_module("api.settings")
    originale_env_file = api_settings.ENV_FILE
    api_settings.ENV_FILE = senza_env / ".env"  # inesistente

    originali_repo_root: dict[str, Callable[[], Path]] = {}
    for nome in MODULI_REPO_ROOT:
        modulo = importlib.import_module(nome)
        originali_repo_root[nome] = modulo._repo_root
        modulo._repo_root = lambda _d=senza_env: _d

    _stato.update(
        env=originali_env,
        env_file=originale_env_file,
        repo_root=originali_repo_root,
        senza_env=senza_env,
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    cartella = _stato.get("senza_env")
    if cartella is not None:
        shutil.rmtree(cartella, ignore_errors=True)


def _reale_abilitato() -> tuple[bool, str]:
    if os.environ.get("CI"):
        return False, "test reale: mai eseguito in CI (variabile CI impostata)"
    if os.environ.get("LSL_TEST_REALE") != "1":
        return False, "test reale: impostare LSL_TEST_REALE=1 per eseguirlo (usa Neon/Aura)"
    return True, ""


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("reale") is None:
        return
    abilitato, motivo = _reale_abilitato()
    if not abilitato:
        pytest.skip(motivo)


@pytest.fixture(autouse=True)
def _isolamento_infrastruttura(request: pytest.FixtureRequest) -> Iterator[None]:
    """Svuota le cache prima e dopo ogni test; per i test `reale` abilitati
    ripristina ambiente e percorsi `.env` originali (solo per quel test)."""
    _svuota_cache()
    if request.node.get_closest_marker("reale") is None or not _reale_abilitato()[0]:
        yield
        _svuota_cache()
        return

    with pytest.MonkeyPatch.context() as mp:
        for chiave, valore in _stato["env"].items():
            mp.setenv(chiave, valore)
        mp.setattr(sys.modules["api.settings"], "ENV_FILE", _stato["env_file"])
        for nome, funzione in _stato["repo_root"].items():
            mp.setattr(sys.modules[nome], "_repo_root", funzione)
        _svuota_cache()
        yield
    _svuota_cache()
