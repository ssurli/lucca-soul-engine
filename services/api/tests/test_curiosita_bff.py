"""Curiosita' dei luoghi attraverso il BFF (ondata 2a, compito 5).

Via HTTP (`POST /itinerary`, `POST /itinerary/adapt`), sullo stesso BFF isolato
di `test_titoli_bff.py` (seed della citta', repository in-memory, nessuna
credenziale, `adesso` fisso):

- il BFF non perde `curiosita`: ogni tappa da esperienza del catalogo porta le
  curiosita' del SUO luogo nel seed; ogni altra tappa una lista vuota;
- il `reason` non le contiene (l'app le mostra sotto il motivo);
- andata e ritorno: la risposta di `/itinerary` rimandata a `/itinerary/adapt`
  con curiosita' iniettate dal client su una tappa nota torna con quelle del
  catalogo.

Le richieste sono quelle del golden (`golden/lucca_itinerari.json`), usate SOLO
come input. L'invarianza dei punteggi resta compito di `test_golden_punteggi`.
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
from graph.seed_lucca import ESPERIENZE, LUOGHI  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
_PER_LUOGO = {
    luogo.id: [c.model_dump(mode="json") for c in luogo.curiosita] for luogo in LUOGHI
}
#: experience_id -> curiosita' attese (JSON), dal luogo dell'esperienza nel seed.
ATTESE = {e.id: _PER_LUOGO.get(e.place_id, []) for e in ESPERIENZE}
INIETTATA = {"testo": "Testo inventato dal client.", "tipo": "fatto", "fonte": "client"}


def _casi() -> dict[str, Any]:
    casi: dict[str, Any] = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return casi


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato, stesso schema di `test_titoli_bff.py`."""
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


def _post(client: TestClient, tipo: str, corpo: dict[str, Any]) -> dict[str, Any]:
    percorso = "/itinerary" if tipo == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=corpo)
    assert resp.status_code == 200, resp.text
    risposta: dict[str, Any] = resp.json()
    return risposta


def _errori(risposta: dict[str, Any]) -> list[str]:
    errori: list[str] = []
    for stop in risposta["stops"]:
        eid = stop["experience_id"]
        if "curiosita" not in stop:
            errori.append(f"{eid}: campo curiosita assente")
            continue
        attese = ATTESE.get(eid, [])
        if stop["curiosita"] != attese:
            errori.append(f"{eid}: curiosita {stop['curiosita']!r} != {attese!r}")
        for c in stop["curiosita"]:
            if c["testo"] in stop["reason"]:
                errori.append(f"{eid}: curiosita ripetuta nel reason")
    return errori


@pytest.mark.parametrize("chiave", sorted(_casi()))
def test_curiosita_del_luogo_nella_risposta(client: TestClient, chiave: str) -> None:
    caso = _casi()[chiave]
    risposta = _post(client, caso["tipo"], caso["richiesta"])
    assert not _errori(risposta), (chiave, _errori(risposta))


@pytest.mark.parametrize(
    "chiave", sorted(k for k, c in _casi().items() if c["tipo"] == "compose")
)
def test_andata_e_ritorno_il_client_non_inietta_curiosita(
    client: TestClient, chiave: str
) -> None:
    richiesta = _casi()[chiave]["richiesta"]
    composto = _post(client, "compose", richiesta)
    # Il client manda indietro l'itinerario con una curiosita' sua su ogni
    # tappa nota (e senza quelle vere).
    for stop in composto["stops"]:
        if stop["experience_id"] in ATTESE:
            stop["curiosita"] = [INIETTATA]
    for segnale in (
        richiesta["signal"],
        {**richiesta["signal"], "meteo": "pioggia", "stanchezza": 0.9},
    ):
        adattato = _post(
            client, "adapt",
            {"itinerary": composto, "signal": segnale, "profile": richiesta["profile"]},
        )
        assert not _errori(adattato), (chiave, _errori(adattato))


def test_il_golden_esercita_tappe_con_curiosita(client: TestClient) -> None:
    """Le asserzioni non sono vuote: almeno una tappa della risposta ne ha."""
    con = sum(
        1
        for c in _casi().values()
        for s in _post(client, c["tipo"], c["richiesta"])["stops"]
        if s["curiosita"]
    )
    assert con > 0


def test_la_guardia_scatta() -> None:
    """Doppio negativo: il controllo fallisce su una risposta rotta."""
    eid = next(e for e, attese in ATTESE.items() if attese)
    rotta = {
        "stops": [
            {"experience_id": eid, "reason": "x"},
            {"experience_id": eid, "reason": "x", "curiosita": [INIETTATA]},
            {"experience_id": eid, "reason": ATTESE[eid][0]["testo"],
             "curiosita": ATTESE[eid]},
        ]
    }
    assert len(_errori(rotta)) == 3
