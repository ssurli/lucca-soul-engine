"""BFF: `Signal.istante` (UTC) diventa ora, data e giorno in `CITY_TZ`.

Un solo helper (`_normalizza_segnale`) su `POST /itinerary` e
`POST /itinerary/adapt`. I test intercettano il segnale che ARRIVA al motore
(`compose_itinerary` / `adapt_itinerary` di `api.main`) e alla sorgente dei
candidati. Il fuso e' iniettato con `monkeypatch` di `get_city_tz`, come in
`test_eventi_promossi.py`: nessun .env della macchina. Date FISSE.
"""

from __future__ import annotations

import logging
from datetime import date, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
api_deps = pytest.importorskip("api.deps", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from fastapi.testclient import TestClient  # noqa: E402

ROMA = ZoneInfo("Europe/Rome")
PERSON_ID = "turista-istante-bff-riservato"


class _Source:
    def __init__(self, candidates: list[Any]) -> None:
        self._c = candidates
        self.segnali: list[Any] = []

    def candidates(self, ctx: Any) -> list[Any]:
        self.segnali.append(ctx.signal)
        return self._c


class _NessunEvento:
    def eventi_ricorrenti(self) -> list[Any]:
        return []


class _Traccia:
    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[Any]:
        return []


def _candidato(orari: list[Any] | None = None) -> Any:
    e = contracts.ExperienceNode(
        id="exp-istante", titolo="Museo", place_id="piazza-anfiteatro", temi=["arte"],
        durata_min=30, al_chiuso=True, accessibile=True, orari_apertura=orari or [],
    )
    return contracts.GraphCandidate(
        experience=e, place_nome="Museo", connessioni=['Evoca il tema "Arte".'], distanza_m=0
    )


class _Spia:
    """Cattura il segnale che arriva al motore, poi delega al motore vero."""

    def __init__(self) -> None:
        self.segnali: list[Any] = []


def _setup(
    monkeypatch: pytest.MonkeyPatch, *, tz: Any = ROMA, candidati: list[Any] | None = None
) -> tuple[_Source, _Spia]:
    source = _Source(candidati if candidati is not None else [_candidato()])
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: source)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: _NessunEvento())
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: _Traccia())
    monkeypatch.setattr(api_main, "get_city_tz", lambda: tz)
    spia = _Spia()
    compose_vero = api_main.compose_itinerary
    adapt_vero = api_main.adapt_itinerary

    def compose(ctx: Any, *a: Any, **k: Any) -> Any:
        spia.segnali.append(ctx.signal)
        return compose_vero(ctx, *a, **k)

    def adapt(itinerary: Any, signal: Any, *a: Any, **k: Any) -> Any:
        spia.segnali.append(signal)
        return adapt_vero(itinerary, signal, *a, **k)

    monkeypatch.setattr(api_main, "compose_itinerary", compose)
    monkeypatch.setattr(api_main, "adapt_itinerary", adapt)
    return source, spia


def _signal(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0,
        "ora": "10:00:00", "eventi_attivi": [], "data": "2026-06-15",
    }
    base.update(extra)
    return base


def _corpo_itinerary(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "person_id": PERSON_ID,
        "profile": {
            "curiosita": 0.3, "contemplazione": 0.2, "arte": 0.9,
            "con_bambini": False, "tempo_disponibile_min": 200,
        },
        "signal": signal,
    }


def _corpo_adapt(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "itinerary": {
            "person_id": PERSON_ID,
            "stops": [{
                "experience_id": "exp-istante", "arrivo": "10:00:00",
                "durata_min": 30, "reason": "Perche e coerente con te.",
            }],
            "generated_at": "2026-06-15T09:00:00",
        },
        "signal": signal,
    }


ENDPOINT = pytest.mark.parametrize(
    ("percorso", "corpo"),
    [("/itinerary", _corpo_itinerary), ("/itinerary/adapt", _corpo_adapt)],
    ids=["itinerary", "adapt"],
)


@ENDPOINT
def test_istante_a_cavallo_della_mezzanotte_locale(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any
) -> None:
    """2026-12-11T23:30Z con Europe/Rome (UTC+1) = 00:30 del 12 dicembre,
    sabato (5). Il dispositivo diceva 10:00 dell'11."""
    source, spia = _setup(monkeypatch)
    resp = TestClient(api_main.app).post(
        percorso, json=corpo(_signal(istante="2026-12-11T23:30:00Z", data="2026-12-11"))
    )
    assert resp.status_code == 200, resp.text
    for s in (spia.segnali[0], source.segnali[0]):
        assert s.data == date(2026, 12, 12)
        assert s.giorno_settimana == 5
        assert s.ora == time(0, 30)


@ENDPOINT
def test_istante_discordante_dal_dispositivo_vince_l_istante(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any
) -> None:
    """Il client manda lunedi' 15 giugno 10:00 (coerente: giorno 0) ma
    l'istante dice martedi' 16 giugno 08:07 a Roma (06:07Z). Nessun 422."""
    source, spia = _setup(monkeypatch)
    resp = TestClient(api_main.app).post(
        percorso,
        json=corpo(_signal(istante="2026-06-16T06:07:00Z", giorno_settimana=0)),
    )
    assert resp.status_code == 200, resp.text
    s = spia.segnali[0]
    assert (s.data, s.giorno_settimana, s.ora) == (date(2026, 6, 16), 1, time(8, 7))
    assert source.segnali[0].giorno_settimana == 1


@ENDPOINT
def test_senza_istante_il_segnale_e_invariato(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any
) -> None:
    _, spia = _setup(monkeypatch)
    body = _signal(ora="14:35:20")
    atteso = contracts.Signal.model_validate(body)
    resp = TestClient(api_main.app).post(percorso, json=corpo(body))
    assert resp.status_code == 200, resp.text
    assert spia.segnali[0] == atteso
    assert spia.segnali[0].istante is None
    assert spia.segnali[0].ora == time(14, 35, 20)  # secondi NON toccati senza istante


@ENDPOINT
def test_city_tz_assente_usa_il_client_e_avvisa_senza_pii(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, percorso: str, corpo: Any
) -> None:
    source, spia = _setup(monkeypatch, tz=None)
    body = _signal(istante="2026-12-11T23:30:00Z")
    with caplog.at_level(logging.WARNING):
        resp = TestClient(api_main.app).post(percorso, json=corpo(body))
    assert resp.status_code == 200, resp.text
    s = spia.segnali[0]
    assert (s.data, s.ora, s.giorno_settimana) == (date(2026, 6, 15), time(10, 0), 0)
    assert source.segnali[0].ora == time(10, 0)
    avvisi = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "CITY_TZ" in r.getMessage() and "istante" in r.getMessage().lower() for r in avvisi
    ), caplog.text
    assert PERSON_ID not in caplog.text
    assert "2026-12-11" not in caplog.text  # nemmeno l'istante del visitatore


def test_city_tz_non_valido_da_settings_e_fail_closed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Il vero `get_city_tz` con un fuso che non esiste: None -> 200."""
    _, spia = _setup(monkeypatch)
    monkeypatch.setattr(api_main, "get_city_tz", api_deps.get_city_tz)
    reali = api_deps.get_settings()
    finte = reali.model_copy(update={"city_tz": "Non/Esiste"})
    monkeypatch.setattr(api_deps, "get_settings", lambda: finte)
    with caplog.at_level(logging.WARNING):
        resp = TestClient(api_main.app).post(
            "/itinerary", json=_corpo_itinerary(_signal(istante="2026-12-11T23:30:00Z"))
        )
    assert resp.status_code == 200, resp.text
    assert spia.segnali[0].ora == time(10, 0)
    assert PERSON_ID not in caplog.text


@ENDPOINT
def test_i_secondi_sono_azzerati(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any
) -> None:
    _, spia = _setup(monkeypatch)
    resp = TestClient(api_main.app).post(
        percorso, json=corpo(_signal(istante="2026-06-15T08:07:45.123456Z"))
    )
    assert resp.status_code == 200, resp.text
    assert spia.segnali[0].ora == time(10, 7, 0, 0)  # 08:07Z = 10:07 CEST


@ENDPOINT
def test_istante_naive_e_422(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any
) -> None:
    _, spia = _setup(monkeypatch)
    resp = TestClient(api_main.app).post(
        percorso, json=corpo(_signal(istante="2026-06-15T08:07:45"))
    )
    assert resp.status_code == 422
    assert spia.segnali == []


@pytest.mark.parametrize(
    ("istante", "data", "giorno", "ora"),
    [
        # CEST (UTC+2) fino alle 01:00Z del 25 ottobre 2026
        ("2026-10-24T22:30:00Z", date(2026, 10, 25), 6, time(0, 30)),
        ("2026-10-25T00:30:00Z", date(2026, 10, 25), 6, time(2, 30)),  # 02:30 CEST
        # dopo il cambio, CET (UTC+1): 01:30Z = 02:30 CET (seconda occorrenza)
        ("2026-10-25T01:30:00Z", date(2026, 10, 25), 6, time(2, 30)),
        ("2026-10-25T02:00:00Z", date(2026, 10, 25), 6, time(3, 0)),
        # mezzanotte locale dopo il cambio: 23:30Z = 00:30 CET del 26 (lunedi')
        ("2026-10-25T23:30:00Z", date(2026, 10, 26), 0, time(0, 30)),
        # offset esplicito nell'ingresso: 2026-06-15T23:30-05:00 = 04:30Z del 16
        ("2026-06-15T23:30:00-05:00", date(2026, 6, 16), 1, time(6, 30)),
    ],
)
@ENDPOINT
def test_cambio_d_ora_e_offset_espliciti(
    monkeypatch: pytest.MonkeyPatch, percorso: str, corpo: Any,
    istante: str, data: date, giorno: int, ora: time,
) -> None:
    _, spia = _setup(monkeypatch)
    resp = TestClient(api_main.app).post(percorso, json=corpo(_signal(istante=istante)))
    assert resp.status_code == 200, resp.text
    s = spia.segnali[0]
    assert (s.data, s.giorno_settimana, s.ora) == (data, giorno, ora)


def test_istante_governa_davvero_il_filtro_orari(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aperto solo il sabato 09:00-12:00. Il dispositivo dice lunedi' 10:00
    (chiuso), l'istante dice sabato 12 dicembre 10:00 a Roma (09:00Z): il
    candidato compare. Senza istante, no."""
    sabato = [contracts.FasciaApertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(12, 0)
    )]
    _setup(monkeypatch, candidati=[_candidato(sabato)])
    client = TestClient(api_main.app)
    con = client.post(
        "/itinerary", json=_corpo_itinerary(_signal(istante="2026-12-12T09:00:00Z"))
    )
    senza = client.post("/itinerary", json=_corpo_itinerary(_signal()))
    assert [s["experience_id"] for s in con.json()["stops"]] == ["exp-istante"]
    assert senza.json()["stops"] == []
