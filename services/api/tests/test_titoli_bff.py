"""`titolo` delle tappe attraverso il BFF (ondata 2a, compito 3).

Via HTTP (`POST /itinerary`, `POST /itinerary/adapt`), sullo stesso BFF isolato
di `test_golden_lucca.py` (seed della citta', repository in-memory, nessuna
credenziale, `adesso` fisso):

- il BFF non perde `titolo`: ogni tappa e ogni tappa esclusa della risposta ha
  il titolo del catalogo (`ExperienceNode.titolo`);
- nessuna stringa `exp-` (prefisso degli id del seed) compare in `titolo` ne' in
  `reason`: l'app non deve mai mostrare un id.

Le richieste sono quelle del golden (`golden/lucca_itinerari.json`), usate SOLO
come input: l'`atteso` non e' letto (quello e' il compito di `test_golden_lucca.py`).
Piu' un andata e ritorno: la risposta di `/itinerary` rimandata a `/itinerary/adapt`.
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
from graph.seed_lucca import ESPERIENZE  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
CATALOGO = {e.id: e.titolo for e in ESPERIENZE}


def _casi() -> dict[str, Any]:
    casi: dict[str, Any] = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return casi


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato, stesso schema di `test_golden_lucca.py`."""
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


def _voci(risposta: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [("stop", s) for s in risposta["stops"]] + [
        ("esclusa", t) for t in risposta["tappe_escluse"]
    ]


def _errori_titolo(risposta: dict[str, Any]) -> list[str]:
    errori: list[str] = []
    for tipo, voce in _voci(risposta):
        eid = voce["experience_id"]
        if "titolo" not in voce:
            errori.append(f"{tipo} {eid}: campo titolo assente")
        elif voce["titolo"] != CATALOGO.get(eid):
            errori.append(f"{tipo} {eid}: titolo {voce['titolo']!r} != {CATALOGO.get(eid)!r}")
    return errori


def _errori_exp(risposta: dict[str, Any]) -> list[str]:
    errori: list[str] = []
    for tipo, voce in _voci(risposta):
        for campo in ("titolo", "reason"):
            valore = voce.get(campo) or ""
            if "exp-" in valore:
                errori.append(f"{tipo} {voce['experience_id']}.{campo}: {valore!r}")
    return errori


@pytest.mark.parametrize("chiave", sorted(_casi()))
def test_titolo_dal_catalogo_e_nessun_id_esposto(client: TestClient, chiave: str) -> None:
    caso = _casi()[chiave]
    risposta = _post(client, caso["tipo"], caso["richiesta"])
    assert not _errori_titolo(risposta), (chiave, _errori_titolo(risposta))
    assert not _errori_exp(risposta), (chiave, _errori_exp(risposta))


@pytest.mark.parametrize(
    "chiave", sorted(k for k, c in _casi().items() if c["tipo"] == "compose")
)
def test_andata_e_ritorno_compose_poi_adapt(client: TestClient, chiave: str) -> None:
    """La risposta di `/itinerary` (con `titolo`) rimandata a `/itinerary/adapt`
    con pioggia e stanchezza: il titolo non si perde e resta quello del catalogo."""
    richiesta = _casi()[chiave]["richiesta"]
    composto = _post(client, "compose", richiesta)
    segnale = {**richiesta["signal"], "meteo": "pioggia", "stanchezza": 0.9}
    adattato = _post(
        client, "adapt",
        {"itinerary": composto, "signal": segnale, "profile": richiesta["profile"]},
    )
    for risposta in (composto, adattato):
        assert not _errori_titolo(risposta), (chiave, _errori_titolo(risposta))
        assert not _errori_exp(risposta), (chiave, _errori_exp(risposta))


def test_le_guardie_scattano() -> None:
    """Doppio negativo: i controlli falliscono su una risposta rotta."""
    rotta = {
        "stops": [{"experience_id": "exp-bici-mura", "titolo": "exp-bici-mura",
                   "reason": "Vai a exp-bici-mura."}],
        "tappe_escluse": [{"experience_id": "exp-bici-mura", "reason": "x"}],
    }
    assert len(_errori_titolo(rotta)) == 2
    assert len(_errori_exp(rotta)) == 2


def test_il_golden_esercita_le_escluse(client: TestClient) -> None:
    """Le asserzioni sulle escluse non sono vuote."""
    escluse = sum(
        len(_post(client, c["tipo"], c["richiesta"])["tappe_escluse"]) for c in _casi().values()
    )
    assert escluse > 0
