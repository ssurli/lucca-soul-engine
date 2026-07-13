"""Contract test dell'endpoint `/health` del BFF (`services/api`).

`/health` non richiede alcun database attivo (Wave 0 è offline): niente
Neo4j, niente Postgres, niente Docker. Se `services/api` non è ancora
installabile al momento del run, questi test vengono saltati esplicitamente
(vedi `pytest.importorskip` sotto) invece di far fallire l'intera suite: la
Wave 0 procede in parallelo su `packages/contracts` e `services/api`.
"""

from __future__ import annotations

from typing import Any

import pytest

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)

TestClient = fastapi_testclient.TestClient


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


def test_health_status_200(client: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_status_ok(client: Any) -> None:
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"


def test_health_non_richiede_database(client: Any) -> None:
    # Nessun mock di Neo4j/Postgres nel setup di questo test: se /health
    # richiedesse una connessione reale, questa suite fallirebbe già qui
    # (siamo offline, senza docker compose up).
    response = client.get("/health")
    assert response.status_code == 200
