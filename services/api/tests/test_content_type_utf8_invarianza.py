"""Il charset UTF-8 cambia SOLO il content-type: corpo, status e header extra
restano quelli di prima (valori attesi verificati eseguendo main 579a261)."""

from __future__ import annotations

from typing import Any

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
graph = pytest.importorskip("graph")
fastapi = pytest.importorskip("fastapi")

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
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceVuota())
    return TestClient(api_main.app, raise_server_exceptions=False)


def test_corpo_404_rotta_inesistente(client: Any) -> None:
    r = client.get("/rotta-inesistente")
    assert (r.status_code, r.content) == (404, b'{"detail":"Not Found"}')


def test_corpo_405_e_header_allow_conservato(client: Any) -> None:
    r = client.get("/itinerary")
    assert (r.status_code, r.content) == (405, b'{"detail":"Method Not Allowed"}')
    assert r.headers["allow"] == "POST"
    assert r.headers["content-type"] == ATTESO


def test_corpo_422_json_malformato(client: Any) -> None:
    r = client.post(
        "/itinerary", content="{non json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "json_invalid"
    assert r.json()["detail"][0]["loc"] == ["body", 1]


def test_corpo_422_validazione(client: Any) -> None:
    r = client.post("/itinerary", json={"person_id": "x"})
    assert r.status_code == 422
    assert {d["type"] for d in r.json()["detail"]} == {"missing"}
    assert r.json()["detail"][0]["loc"][0] == "body"


def test_header_extra_httpexception_conservati(client: Any) -> None:
    @api_main.app.get("/_test_hdr_utf8")
    def _p() -> None:
        raise fastapi.HTTPException(
            status_code=418, detail="tè", headers={"X-Foo": "bar", "WWW-Authenticate": "Bearer"}
        )

    try:
        r = client.get("/_test_hdr_utf8")
    finally:
        api_main.app.router.routes.pop()
    assert r.status_code == 418
    assert r.headers["x-foo"] == "bar"
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.headers["content-type"] == ATTESO
    assert r.content == b'{"detail":"t\xc3\xa8"}'


def test_cors_conservato_su_errore_dashboard(client: Any) -> None:
    r = client.get(
        "/dashboard/index", params={"periodo": "non-un-periodo"}, headers={"origin": "null"}
    )
    assert r.status_code == 422
    assert r.headers["access-control-allow-origin"] == "*"
    assert r.headers["content-type"] == ATTESO


def test_preflight_cors_invariato(client: Any) -> None:
    r = client.options(
        "/dashboard/index",
        headers={"origin": "null", "access-control-request-method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "*"
    assert r.headers["access-control-allow-methods"] == "GET"
    assert "content-type" not in r.headers


def test_booking_esperienza_inesistente_corpo_e_charset(client: Any) -> None:
    r = client.post(
        "/booking",
        json={"person_id": "p", "experience_id": "nope", "quando": "2026-09-01T10:00:00+00:00"},
    )
    assert r.status_code == 404
    assert r.json() == {"detail": "esperienza id='nope' non trovata"}
    assert r.headers["content-type"] == ATTESO


def test_corpo_503_grafo_invariato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _SourceGiu())
    c = TestClient(api_main.app, raise_server_exceptions=False)
    body = {
        "person_id": "t",
        "profile": {
            "curiosita": 0.7,
            "contemplazione": 0.5,
            "arte": 0.6,
            "con_bambini": False,
            "tempo_disponibile_min": 120,
        },
        "signal": {"meteo": "sereno", "affollamento": {}, "stanchezza": 0.0, "ora": "10:00:00"},
    }
    r = c.post("/itinerary", json=body)
    assert r.status_code == 503
    assert r.json() == {
        "detail": "conoscenza della città temporaneamente non disponibile: riprova più tardi"
    }
