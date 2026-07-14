"""Conftest condiviso per `tests/`.

Carica (senza duplicare né modificare) le fixture Postgres effimere già
scritte per `services/urban-memory/tests/conftest.py` — un cluster Postgres
16 vero, usa e getta, con `pytest.skip` automatico se i binari non sono
disponibili in questo ambiente. Le riusiamo qui per
`tests/test_postgres_persistence.py`, che verifica il criterio del
committente END-TO-END attraverso il BFF/servizio, non solo a livello del
singolo servizio (già coperto da `services/urban-memory/tests/`).

Si carica il file per path con `importlib` (non un `import conftest`
qualunque, né una manipolazione di `sys.path`) per evitare qualunque
collisione di nome di modulo con il conftest che pytest stesso importa per
questa stessa cartella (`tests/conftest.py` è anch'esso, dal punto di vista
di pytest, un modulo chiamato "conftest").
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_URBAN_MEMORY_CONFTEST = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "urban-memory"
    / "tests"
    / "conftest.py"
)

_spec = importlib.util.spec_from_file_location(
    "_urban_memory_tests_conftest", _URBAN_MEMORY_CONFTEST
)
assert _spec is not None and _spec.loader is not None
_urban_memory_conftest = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _urban_memory_conftest
_spec.loader.exec_module(_urban_memory_conftest)

# Re-esportate come fixture di QUESTA cartella: pytest riconosce come
# fixture qualunque nome, in un conftest.py o in un modulo di test, il cui
# valore è decorato con `@pytest.fixture` — indipendentemente da dove sia
# stato definito in origine.
postgres_cluster = _urban_memory_conftest.postgres_cluster
pg_dsn = _urban_memory_conftest.pg_dsn
pg_repo = _urban_memory_conftest.pg_repo
valid_contribution_factory = _urban_memory_conftest.valid_contribution_factory

__all__ = ["postgres_cluster", "pg_dsn", "pg_repo", "valid_contribution_factory"]
