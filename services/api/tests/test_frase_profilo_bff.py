"""Frase del profilo via BFF (ondata 2b, compito 4).

Sul BFF isolato (stesso schema di `test_golden_lucca.py`), la richiesta del
caso golden `demo|curioso|pioggia-15` (usata solo come input: il golden non si
legge come atteso qui): la prima tappa è SOSTITUITA per la pioggia e il suo
`reason` porta, in quest'ordine, "Sostituita per la pioggia." e la frase del
profilo; nessun'altra tappa la porta. Un profilo con la sola curiosità 0.35
("Un po'") non produce alcuna frase del profilo in composizione.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
SOSTITUITA = "Sostituita per la pioggia."
CURIOSO = "Hai voglia di perderti e lasciarti sorprendere."
FRASI_PROFILO = (
    "È pensata anche per chi viaggia con bambini.",
    "Rispetta il bisogno di un percorso accessibile.",
    "Cerchi silenzio e raccoglimento.",
    "Ami i luoghi vivi, con musica e movimento.",
    "Ti lasci conquistare dalla bellezza.",
    "Preferisci le storie che un luogo racconta.",
    "Hai voglia di perderti e lasciarti sorprendere.",
    "Preferisci un percorso chiaro, senza troppe sorprese.",
)


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
    casi: dict[str, Any] = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    richiesta: dict[str, Any] = casi[chiave]["richiesta"]
    return richiesta


def _conta_profilo(reason: str) -> int:
    return sum(reason.count(f) for f in FRASI_PROFILO)


def _conta_ovunque(reason: str) -> int:
    """Come `_conta_profilo`, ma riconosce la frase anche a meta' testo
    (minuscola, senza punto): i `reason` del formato vecchio la intrecciano."""
    testo = reason.lower()
    return sum(testo.count(f.lower().rstrip(".")) for f in FRASI_PROFILO)


def test_demo_curioso_pioggia_prima_tappa_sostituita_con_frase(client: TestClient) -> None:
    resp = client.post("/itinerary/adapt", json=_richiesta("demo|curioso|pioggia-15"))
    assert resp.status_code == 200, resp.text
    stops = resp.json()["stops"]
    prima = stops[0]
    assert prima["esito_adattamento"] == "sostituita", prima
    reason: str = prima["reason"]
    assert SOSTITUITA in reason and CURIOSO in reason, reason
    assert reason.index(SOSTITUITA) < reason.index(CURIOSO), reason
    assert reason.startswith(f"{SOSTITUITA} {CURIOSO} "), reason
    assert _conta_profilo(reason) == 1
    assert all(_conta_profilo(s["reason"]) == 0 for s in stops[1:]), [
        s["reason"] for s in stops[1:]
    ]


def test_un_po_di_curiosita_nessuna_frase_del_profilo(client: TestClient) -> None:
    richiesta = _richiesta("demo|curioso|pioggia-15")
    profilo = {
        "curiosita": 0.35, "contemplazione": 0.5, "arte": 0.5, "con_bambini": False,
        "accessibilita_richiesta": False, "tempo_disponibile_min": 240,
    }
    corpo = {"person_id": "p", "profile": profilo, "signal": richiesta["signal"],
             "luoghi_gia_visti": []}
    resp = client.post("/itinerary", json=corpo)
    assert resp.status_code == 200, resp.text
    stops = resp.json()["stops"]
    assert stops
    assert all(_conta_profilo(s["reason"]) == 0 for s in stops), [s["reason"] for s in stops]
    # E adattando lo stesso itinerario con quel profilo: ancora nessuna frase.
    adatta = client.post(
        "/itinerary/adapt",
        json={"itinerary": resp.json(), "signal": richiesta["signal"], "profile": profilo},
    )
    assert adatta.status_code == 200, adatta.text
    assert all(_conta_profilo(s["reason"]) == 0 for s in adatta.json()["stops"])


def test_adapt_profilo_bambini_mura_frase_al_massimo_una_volta(client: TestClient) -> None:
    """Richiesta VECCHIA del golden: le tappe ricevute portano gia' la frase dei
    bambini (conservata per contratto sulle non toccate). La prima tappa
    sostituita non ne aggiunge un'altra."""
    richiesta = _richiesta("adapt-profilo|con-bambini|mura-affollate")
    resp = client.post("/itinerary/adapt", json=richiesta)
    assert resp.status_code == 200, resp.text
    stops = resp.json()["stops"]
    assert stops[0]["esito_adattamento"] == "sostituita", stops[0]
    ricevuti = {s["experience_id"]: s["reason"] for s in richiesta["itinerary"]["stops"]}
    for s in stops:
        if s["esito_adattamento"] == "non_toccata":
            assert s["reason"] == ricevuti[s["experience_id"]]
    assert _conta_profilo(stops[0]["reason"]) == 0, stops[0]["reason"]
    # Su TUTTE le stops, anche a meta' frase (formato vecchio): al massimo una volta.
    totale = sum(_conta_ovunque(s["reason"]) for s in stops)
    assert totale <= 1, [s["reason"] for s in stops]
