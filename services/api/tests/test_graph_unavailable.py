"""Grafo irraggiungibile -> 503 con messaggio fisso, mai 500 né dettagli del DSN.

Fonti finte in-process (monkeypatch di `api.main.*`): nessuna rete."""

from __future__ import annotations

from typing import Any

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
graph = pytest.importorskip("graph")

TestClient = fastapi_testclient.TestClient
MESSAGGIO = "conoscenza della città temporaneamente non disponibile: riprova più tardi"
VIETATI = ("neo4j", "bolt", "databases.neo4j.io", "password", "secret-host")


class _SourceGiu:
    def candidates(self, ctx: Any) -> list[Any]:
        raise graph.GraphUnavailableError() from ConnectionError(
            "bolt://secret-host.databases.neo4j.io password=hunter2"
        )


class _MetricsGiu:
    def grado_semantico(self) -> dict[str, int]:
        raise graph.GraphUnavailableError()

    def non_connected_place_pairs(self, at: Any = None) -> Any:
        raise graph.GraphUnavailableError()


class _SourceVuota:
    def candidates(self, ctx: Any) -> list[Any]:
        return []


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceGiu())
    monkeypatch.setattr(api_main, "get_metrics_source", lambda: _MetricsGiu())
    return TestClient(api_main.app, raise_server_exceptions=False)


def _signal() -> dict[str, Any]:
    return {"meteo": "sereno", "affollamento": {}, "stanchezza": 0.0, "ora": "10:00:00"}


def _ctx() -> dict[str, Any]:
    return {
        "person_id": "turista-grafo-giu",
        "profile": {
            "curiosita": 0.7,
            "contemplazione": 0.5,
            "arte": 0.6,
            "con_bambini": False,
            "tempo_disponibile_min": 120,
        },
        "signal": _signal(),
    }


def _verifica(resp: Any) -> None:
    assert resp.status_code == 503
    assert resp.json() == {"detail": MESSAGGIO}
    testo = resp.text.lower()
    for vietato in VIETATI:
        assert vietato not in testo


def test_itinerary_503(client: Any) -> None:
    _verifica(client.post("/itinerary", json=_ctx()))


def test_adapt_503(client: Any) -> None:
    body = {
        "itinerary": {
            "person_id": "turista-grafo-giu",
            "stops": [],
            "generated_at": "2026-08-01T10:00:00+00:00",
        },
        "signal": _signal(),
    }
    _verifica(client.post("/itinerary/adapt", json=body))


def test_booking_503(client: Any) -> None:
    body = {
        "person_id": "turista-grafo-giu",
        "experience_id": "exp-x",
        "quando": "2026-08-01T10:00:00+00:00",
    }
    _verifica(client.post("/booking", json=body))


def test_dashboard_index_503(client: Any) -> None:
    _verifica(client.get("/dashboard/index", params={"periodo": "2026-08"}))


def test_dashboard_flows_503(client: Any) -> None:
    _verifica(client.get("/dashboard/flows", params={"periodo": "2026-08"}))


def test_dashboard_con_catalogo_su_ma_metriche_giu_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anche con `candidates()` funzionante, `grado_semantico()` giù -> 503."""
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceVuota())
    monkeypatch.setattr(api_main, "get_metrics_source", lambda: _MetricsGiu())
    c = TestClient(api_main.app, raise_server_exceptions=False)
    _verifica(c.get("/dashboard/flows", params={"periodo": "2026-08"}))
