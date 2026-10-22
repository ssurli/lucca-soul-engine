"""`ItineraryStop.punto_arrivo` nella risposta del BFF isolato (ondata 3, compito 4).

Stessa fixture di `test_golden_lucca.py` (seed versionato, repository in
memoria, orologio fisso, nessuna credenziale) e stesse richieste del golden
(`demo|con-bambini|sereno-10`, `feriale|con-bambini|sereno-10`), che
contengono botteghe dimostrative. Il motore decide il punto, l'app costruisce
solo il link: ogni tappa con punti di arrivo nel catalogo ne porta uno (la
prima il primo della lista, le altre il più vicino alla precedente); le
botteghe dimostrative no. Il golden NON è letto per l'`atteso`: solo per la
richiesta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from contracts import Punto, VisitorContext, punto_piu_vicino  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import DATASET  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)  # come test_golden_lucca.py
CASI = ["demo|con-bambini|sereno-10", "feriale|con-bambini|sereno-10"]


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


def _richiesta(chiave: str) -> dict[str, Any]:
    casi = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    caso = casi[chiave]
    assert caso["tipo"] == "compose", chiave
    richiesta: dict[str, Any] = caso["richiesta"]
    return richiesta


def _botteghe_dimostrative() -> set[str]:
    fittizie = {b.id for b in DATASET.botteghe if b.fittizio}
    return {e.id for e in DATASET.esperienze if e.partner_id in fittizie}


def _punti_catalogo() -> dict[str, list[Punto]]:
    return {
        c.experience.id: c.punti_arrivo
        for c in SeedCandidateSource().candidates(
            VisitorContext.model_validate(_richiesta(CASI[0]))
        )
    }


def _punto(valore: dict[str, Any] | None) -> Punto | None:
    return None if valore is None else Punto.model_validate(valore)


@pytest.mark.parametrize("chiave", CASI)
def test_punto_arrivo_presente_e_assente_sulle_botteghe(client: TestClient, chiave: str) -> None:
    resp = client.post("/itinerary", json=_richiesta(chiave))
    assert resp.status_code == 200, resp.text
    stops = resp.json()["stops"]
    botteghe = _botteghe_dimostrative()
    catalogo = _punti_catalogo()
    ids = [s["experience_id"] for s in stops]
    assert botteghe & set(ids), f"precondizione: {chiave} senza bottega ({ids})"
    precedente: Punto | None = None
    for i, s in enumerate(stops):
        assert "punto_arrivo" in s, s["experience_id"]
        punto = _punto(s["punto_arrivo"])
        punti = catalogo[s["experience_id"]]
        if s["experience_id"] in botteghe:
            assert punti == [] and punto is None, s["experience_id"]
        elif i == 0 or precedente is None:
            assert punto == punti[0], s["experience_id"]
        else:
            assert punto == punto_piu_vicino(precedente, punti), s["experience_id"]
        precedente = punto
    assert any(_punto(s["punto_arrivo"]) is not None for s in stops)


def test_punto_arrivo_sopravvive_all_andata_e_ritorno_con_adapt(client: TestClient) -> None:
    richiesta = _richiesta(CASI[0])
    itinerario = client.post("/itinerary", json=richiesta).json()
    resp = client.post(
        "/itinerary/adapt",
        json={
            "itinerary": itinerario,
            "signal": richiesta["signal"],
            "profile": richiesta["profile"],
        },
    )
    assert resp.status_code == 200, resp.text
    adattato = resp.json()
    assert [s["punto_arrivo"] for s in adattato["stops"]] == [
        s["punto_arrivo"] for s in itinerario["stops"]
    ]
