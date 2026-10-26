"""BFF - accessibilità sulle tappe in coda (ondata 4, compito 5-quater).

`POST /itinerary` con un segnale fluttuante ATTIVO e pertinente e un `:Evento`
promosso ATTIVO in finestra: con `accessibilita_richiesta=True` nessuna tappa
in coda; con `False` (stessi identici input) entrambe. Ambiente isolato
in-memory, stesso stile di `test_fluttuante.py`/`test_eventi_promossi.py`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
contracts = pytest.importorskip("contracts")
urban_memory = pytest.importorskip("urban_memory")
frizione_pattern = pytest.importorskip("urban_memory.frizione_pattern")

TestClient = fastapi_testclient.TestClient
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
SegnaleFluttuante = contracts.SegnaleFluttuante
EventoRicorrente = frizione_pattern.EventoRicorrente

PLACE_ID_SEED = "piazza-anfiteatro"
ULTIMA_OCCORRENZA_UTC = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
DATA_IN_FINESTRA = "2026-04-01"  # ultima occorrenza + cadenza 30


class _FakeCandidateSource:
    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


class _FakeEventoReader:
    def __init__(self, eventi: list[Any]) -> None:
        self._eventi = eventi

    def eventi_ricorrenti(self) -> list[Any]:
        return self._eventi


class _FakeTraccia:
    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        return [ULTIMA_OCCORRENZA_UTC]

    def list_for_place(self, place_id: str) -> list[Any]:
        return []


def _candidato() -> Any:
    esperienza = ExperienceNode(
        id="exp-accessibilita-test-fisso", titolo="Facciata Barocca", place_id=PLACE_ID_SEED,
        temi=["arte"], durata_min=30, al_chiuso=False, accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Piazza Fissa di Test",
        connessioni=['Evoca il tema "Arte".'],
    )


def _ctx(accessibile: bool) -> dict[str, Any]:
    return {
        "person_id": "turista-accessibilita-coda",
        "profile": {
            "curiosita": 0.3, "contemplazione": 0.2, "arte": 0.9, "con_bambini": False,
            "tempo_disponibile_min": 200, "accessibilita_richiesta": accessibile,
        },
        "signal": {
            "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0, "ora": "10:00:00",
            "eventi_attivi": [], "data": DATA_IN_FINESTRA,
        },
    }


def _post(monkeypatch: pytest.MonkeyPatch, accessibile: bool) -> list[str]:
    segnale_repo = urban_memory.InMemorySegnaleFluttuanteRepository()
    segnale_repo.persist(
        SegnaleFluttuante(
            id="violinista-accessibilita", descrizione="Un violinista suona in piazza",
            temi=["musica"], place_id=PLACE_ID_SEED, non_commerciale=True,
            valido_fino=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    evento = EventoRicorrente(
        evento_id="evento-accessibilita-test", place_id=PLACE_ID_SEED, temi=("musica",),
        stato="attivo", cadenza_giorni=30.0,
    )
    source = _FakeCandidateSource([_candidato()])
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnale_repo)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: _FakeTraccia())
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: source)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: _FakeEventoReader([evento]))
    monkeypatch.setattr(api_main, "get_city_tz", lambda: ZoneInfo("Europe/Rome"))
    resp = TestClient(api_main.app).post("/itinerary", json=_ctx(accessibile))
    assert resp.status_code == 200, resp.text
    return [s["experience_id"] for s in resp.json()["stops"]]


def test_bff_non_accessibile_coda_presente(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = _post(monkeypatch, False)
    assert "exp-accessibilita-test-fisso" in ids
    assert "fluttuante-violinista-accessibilita" in ids
    assert "evento-accessibilita-test" in ids


def test_bff_accessibile_nessuna_tappa_in_coda(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = _post(monkeypatch, True)
    assert ids == ["exp-accessibilita-test-fisso"], ids
