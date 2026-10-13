"""BFF `POST /itinerary`: il giorno ricavato da `signal.data` e' applicato.

Il body porta SOLO `signal.data` (come l'app Flutter, mai `giorno_settimana`):
`Signal` ricava `giorno_settimana = data.weekday()` e il filtro duro sugli
orari di apertura esclude chi e' chiuso quel giorno. Prima del cambio, con
solo `data`, il candidato aperto solo il lunedi sarebbe comparso anche di
martedi. Candidati finti con orari (il grafo oggi non ne dichiara).
Date FISSE: 2026-03-02 lunedi, 2026-03-03 martedi."""

from __future__ import annotations

from datetime import time
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from fastapi.testclient import TestClient  # noqa: E402

ID = "exp-bff-solo-lunedi"


class _Source:
    def __init__(self, candidates: list[Any]) -> None:
        self._c = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        self.ultimo_ctx = ctx
        return self._c


class _NessunEvento:
    def eventi_ricorrenti(self) -> list[Any]:
        return []


class _Traccia:
    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[Any]:
        return []


def _candidato() -> Any:
    e = contracts.ExperienceNode(
        id=ID, titolo="Museo del Lunedi", place_id="piazza-anfiteatro", temi=["arte"],
        durata_min=30, al_chiuso=True, accessibile=True,
        orari_apertura=[
            contracts.FasciaApertura(
                giorno_settimana=0, apertura=time(9, 0), chiusura=time(13, 0)
            )
        ],
    )
    return contracts.GraphCandidate(
        experience=e, place_nome="Museo", connessioni=['Evoca il tema "Arte".']
    )


def _body(data: str) -> dict[str, Any]:
    return {
        "person_id": "turista-giorno-da-data",
        "profile": {
            "curiosita": 0.3, "contemplazione": 0.2, "arte": 0.9,
            "con_bambini": False, "tempo_disponibile_min": 200,
        },
        # SOLO `data`: nessun giorno_settimana nel body.
        "signal": {
            "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0,
            "ora": "10:00:00", "eventi_attivi": [], "data": data,
        },
    }


def _post(monkeypatch: pytest.MonkeyPatch, data: str) -> tuple[list[str], _Source]:
    source = _Source([_candidato()])
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: source)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: _NessunEvento())
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: _Traccia())
    resp = TestClient(api_main.app).post("/itinerary", json=_body(data))
    assert resp.status_code == 200, resp.text
    return [s["experience_id"] for s in resp.json()["stops"]], source


def test_bff_solo_data_martedi_esclude_candidato_aperto_solo_il_lunedi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids, _ = _post(monkeypatch, "2026-03-03")
    assert ID not in ids


def test_bff_solo_data_lunedi_include_candidato_aperto_il_lunedi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids, _ = _post(monkeypatch, "2026-03-02")
    assert ID in ids


def test_bff_il_signal_ricevuto_ha_giorno_settimana_valorizzato(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source = _post(monkeypatch, "2026-03-03")
    assert source.ultimo_ctx.signal.giorno_settimana == 1
