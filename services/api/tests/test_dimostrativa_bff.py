"""`ItineraryStop.dimostrativa` via HTTP del BFF (seed di Lucca, in-memory).

Una risposta reale di `POST /itinerary` con una tappa di bottega porta
`"dimostrativa": true` su quella e false sulle altre; il round-trip
`/itinerary` -> `/itinerary/adapt` conserva il valore (ricalcolato dal grafo,
non dalla richiesta).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import ESPERIENZE  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
BOTTEGHE = {e.id for e in ESPERIENZE if e.partner_id is not None}

# Caso naturale: famiglia con bambini sul seed di Lucca include la pasticceria.
PROFILO_BAMBINI: dict[str, Any] = {
    "curiosita": 0.6, "contemplazione": 0.3, "arte": 0.3, "con_bambini": True,
    "tempo_disponibile_min": 240, "accessibilita_richiesta": False,
}


def _segnale(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0,
        "ora": "10:00:00", "data": "2026-12-12", "eventi_attivi": [],
    }
    base.update(kw)
    return base


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fonte = SeedCandidateSource()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(api_main, "get_adesso", lambda: ADESSO_FISSO)
    return TestClient(api_main.app)


def _componi(client: TestClient) -> dict[str, Any]:
    resp = client.post(
        "/itinerary",
        json={
            "person_id": "t-dimostrativa", "profile": PROFILO_BAMBINI,
            "signal": _segnale(), "luoghi_gia_visti": [],
        },
    )
    assert resp.status_code == 200, resp.text
    out: dict[str, Any] = resp.json()
    return out


def _flag(itin: dict[str, Any]) -> dict[str, bool]:
    return {s["experience_id"]: s["dimostrativa"] for s in itin["stops"]}


def test_compose_porta_true_sulla_bottega_e_false_sulle_altre(client: TestClient) -> None:
    itin = _componi(client)
    flag = _flag(itin)
    di_bottega = [i for i in flag if i in BOTTEGHE]
    assert di_bottega, "nessuna tappa di bottega: il test non esercita nulla"
    assert len(flag) > len(di_bottega), "serve almeno una tappa non di bottega"
    for s in itin["stops"]:
        assert s["dimostrativa"] is (s["experience_id"] in BOTTEGHE), s["experience_id"]


def test_roundtrip_compose_adapt_conserva_true_sulla_bottega(client: TestClient) -> None:
    itin = _componi(client)
    assert any(v for v in _flag(itin).values())
    for sig in (_segnale(), _segnale(meteo="pioggia"), _segnale(stanchezza=0.9)):
        resp = client.post("/itinerary/adapt", json={"itinerary": itin, "signal": sig})
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert any(s["experience_id"] in BOTTEGHE for s in out["stops"]), sig
        for s in out["stops"]:
            assert s["dimostrativa"] is (s["experience_id"] in BOTTEGHE), s["experience_id"]


def test_adapt_ignora_il_valore_inviato_dal_client(client: TestClient) -> None:
    itin = _componi(client)
    falso = {
        **itin,
        "stops": [{**s, "dimostrativa": not s["dimostrativa"]} for s in itin["stops"]],
    }
    for sig in (_segnale(), _segnale(meteo="pioggia")):
        resp = client.post("/itinerary/adapt", json={"itinerary": falso, "signal": sig})
        assert resp.status_code == 200, resp.text
        for s in resp.json()["stops"]:
            assert s["dimostrativa"] is (s["experience_id"] in BOTTEGHE), s["experience_id"]
