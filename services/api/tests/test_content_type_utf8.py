"""Ogni risposta JSON del BFF dichiara `charset=utf-8` (client PowerShell 5.1).

Dipendenze isolate in-process (monkeypatch di `api.main.*`): nessuna rete,
nessuna credenziale. Il corpo non cambia (lo coprono i golden)."""

from __future__ import annotations

from typing import Any

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
graph = pytest.importorskip("graph")

TestClient = fastapi_testclient.TestClient
ATTESO = "application/json; charset=utf-8"


class _SourceVuota:
    def candidates(self, ctx: Any) -> list[Any]:
        return []


class _SourceGiu:
    def candidates(self, ctx: Any) -> list[Any]:
        raise graph.GraphUnavailableError()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    from recommender import InMemoryBehaviorEventRepository

    eventi = InMemoryBehaviorEventRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceVuota())
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    return TestClient(api_main.app, raise_server_exceptions=False)


def _signal() -> dict[str, Any]:
    return {"meteo": "sereno", "affollamento": {}, "stanchezza": 0.0, "ora": "10:00:00"}


def _ctx() -> dict[str, Any]:
    return {
        "person_id": "turista-charset",
        "profile": {
            "curiosita": 0.7,
            "contemplazione": 0.5,
            "arte": 0.6,
            "con_bambini": False,
            "tempo_disponibile_min": 120,
        },
        "signal": _signal(),
    }


def test_health(client: Any) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"] == ATTESO


def test_itinerary(client: Any) -> None:
    r = client.post("/itinerary", json=_ctx())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == ATTESO


def test_itinerary_adapt(client: Any) -> None:
    body = {
        "itinerary": {
            "person_id": "turista-charset",
            "stops": [],
            "generated_at": "2026-08-01T10:00:00+00:00",
        },
        "signal": _signal(),
    }
    r = client.post("/itinerary/adapt", json=body)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == ATTESO


def test_validazione_422(client: Any) -> None:
    r = client.post("/itinerary", json={"person_id": "x"})
    assert r.status_code == 422
    assert r.headers["content-type"] == ATTESO


def test_http_exception(client: Any) -> None:
    r = client.get("/dashboard/index", params={"periodo": "non-un-periodo"})
    assert r.status_code == 422
    assert r.headers["content-type"] == ATTESO


def test_404_rotta_inesistente(client: Any) -> None:
    r = client.get("/rotta-inesistente")
    assert r.status_code == 404
    assert r.headers["content-type"] == ATTESO


def test_422_json_malformato(client: Any) -> None:
    r = client.post(
        "/itinerary", content="{non json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422
    assert r.headers["content-type"] == ATTESO


def test_handler_di_dominio_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceGiu())
    c = TestClient(api_main.app, raise_server_exceptions=False)
    r = c.post("/itinerary", json=_ctx())
    assert r.status_code == 503
    assert r.headers["content-type"] == ATTESO
    assert "città" in r.json()["detail"]
