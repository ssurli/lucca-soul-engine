"""Contract test dei campi dell'ondata 3 (`packages/contracts`).

Rete di sicurezza sui tipi condivisi nuovi: `Punto`, `ItineraryStop.punto_arrivo`,
`ExperienceNode.punti_arrivo` / `fonte_orari`, `GraphCandidate.punti_arrivo`,
`Curiosita.fonte_pubblica` e le funzioni di distanza di `contracts.punti`.
Se un campo cambia nome, perde il default (retrocompatibilita' delle richieste
vecchie) o allarga i vincoli, questi test si rompono PRIMA di un servizio a valle.

Non "aggiustare" un modello per far passare questi test: segnalare a `contract-keeper`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import contracts
import pytest
from contracts import (
    COEFFICIENTE_PERCORSO_PIEDI,
    Curiosita,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Punto,
    distanza_a_piedi_m,
    distanza_linea_aria_m,
    punto_piu_vicino,
)
from pydantic import ValidationError

DUOMO = Punto(lat=43.8408, lon=10.5053)
SAN_MICHELE = Punto(lat=43.8423, lon=10.5019)


def _esperienza(**extra: object) -> ExperienceNode:
    return ExperienceNode.model_validate(
        {
            "id": "exp-x", "titolo": "X", "place_id": "p", "temi": [], "durata_min": 30,
            "al_chiuso": True, "accessibile": True, "alimenta_memoria": False, **extra,
        }
    )


@pytest.mark.parametrize(("lat", "lon"), [(90, 180), (-90, -180), (0, 0), (43.84, 10.5)])
def test_punto_estremi_ammessi(lat: float, lon: float) -> None:
    p = Punto(lat=lat, lon=lon)
    assert (p.lat, p.lon) == (lat, lon)


@pytest.mark.parametrize(
    ("lat", "lon"), [(90.0001, 0), (-90.0001, 0), (0, 180.0001), (0, -180.0001)]
)
def test_punto_fuori_intervallo_rifiutato(lat: float, lon: float) -> None:
    with pytest.raises(ValidationError):
        Punto(lat=lat, lon=lon)


def test_punto_campo_mancante_rifiutato() -> None:
    with pytest.raises(ValidationError):
        Punto.model_validate({"lat": 43.0})


def test_punto_arrivo_della_tappa_default_none_e_round_trip() -> None:
    tappa = ItineraryStop(
        experience_id="exp-x", titolo="X", arrivo="10:00:00", durata_min=30, reason="r",
    )
    assert tappa.punto_arrivo is None
    assert tappa.model_dump(mode="json")["punto_arrivo"] is None
    con = tappa.model_copy(update={"punto_arrivo": DUOMO})
    dopo = ItineraryStop.model_validate(con.model_dump(mode="json"))
    assert dopo.punto_arrivo == DUOMO
    it = Itinerary(person_id="p", stops=[con], generated_at=datetime(2026, 12, 12, tzinfo=UTC))
    assert Itinerary.model_validate_json(it.model_dump_json()).stops[0].punto_arrivo == DUOMO


def test_esperienza_retrocompatibile_senza_punti_ne_fonte_orari() -> None:
    e = _esperienza()
    assert e.punti_arrivo == []
    assert e.fonte_orari is None
    e2 = _esperienza(punti_arrivo=[{"lat": 43.84, "lon": 10.5}], fonte_orari="sito del Comune")
    assert e2.punti_arrivo == [Punto(lat=43.84, lon=10.5)]
    assert e2.fonte_orari == "sito del Comune"


def test_candidato_del_grafo_punti_arrivo_default_vuoto() -> None:
    campo = GraphCandidate.model_fields["punti_arrivo"]
    assert campo.default == []
    assert campo.annotation == list[Punto]


def test_curiosita_fonte_pubblica_default_false_e_serializzata() -> None:
    c = Curiosita(testo="Un fatto.", tipo="fatto", fonte="dato del committente")
    assert c.fonte_pubblica is False  # il default NASCONDE la fonte (scelta prudente)
    assert c.model_dump(mode="json")["fonte_pubblica"] is False
    vecchia = Curiosita.model_validate({"testo": "x", "tipo": "fatto", "fonte": "f"})
    assert vecchia.fonte_pubblica is False
    pubblica = Curiosita(testo="Un fatto.", tipo="fatto", fonte="Comune", fonte_pubblica=True)
    assert Curiosita.model_validate(pubblica.model_dump(mode="json")).fonte_pubblica is True


def test_distanze_funzioni_pure() -> None:
    assert distanza_linea_aria_m(DUOMO, DUOMO) == 0.0
    assert distanza_a_piedi_m(DUOMO, DUOMO) == 0
    ab = distanza_linea_aria_m(DUOMO, SAN_MICHELE)
    assert ab == pytest.approx(distanza_linea_aria_m(SAN_MICHELE, DUOMO))
    piedi = distanza_a_piedi_m(DUOMO, SAN_MICHELE)
    assert piedi % 10 == 0
    assert abs(piedi - ab * COEFFICIENTE_PERCORSO_PIEDI) <= 5 + 1e-9


def test_arrotondamento_ai_10_m_half_up_esplicito(monkeypatch: pytest.MonkeyPatch) -> None:
    """25 m -> 30 (half up), non 20 (il `round()` di Python arrotonda al pari)."""
    from contracts import punti

    monkeypatch.setattr(punti, "COEFFICIENTE_PERCORSO_PIEDI", 1.0)
    for aria, atteso in ((25.0, 30), (35.0, 40), (24.99, 20), (4.99, 0), (5.0, 10)):
        monkeypatch.setattr(punti, "distanza_linea_aria_m", lambda a, b, d=aria: d)
        assert punti.distanza_a_piedi_m(DUOMO, SAN_MICHELE) == atteso, aria


def test_punto_piu_vicino_parita_vince_il_primo_e_lista_vuota() -> None:
    assert punto_piu_vicino(DUOMO, []) is None
    gemello = Punto(lat=SAN_MICHELE.lat, lon=SAN_MICHELE.lon)
    lontano = Punto(lat=44.5, lon=11.0)
    assert punto_piu_vicino(DUOMO, [lontano, SAN_MICHELE, gemello]) is SAN_MICHELE
    assert punto_piu_vicino(DUOMO, [gemello, SAN_MICHELE]) is gemello


def test_i_nomi_nuovi_sono_esportati_da_contracts() -> None:
    for nome in (
        "Punto", "COEFFICIENTE_PERCORSO_PIEDI", "distanza_a_piedi_m",
        "distanza_linea_aria_m", "punto_piu_vicino",
    ):
        assert hasattr(contracts, nome), nome
        assert nome in contracts.__all__, nome
