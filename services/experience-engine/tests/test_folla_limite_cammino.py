"""Limite al cammino aggiunto da una sostituzione per AFFOLLAMENTO (correzione 2).

Regola: `rules.AUMENTO_CAMMINO_MAX_AFFOLLAMENTO_M` (int, metri). Per una
sostituzione causata dall'AFFOLLAMENTO (tappa all'aperto su luogo > 0.7 e NON
toccata dalla pioggia) il sostituto e' ammesso solo se

    aumento = d(prec, sost) + d(sost, succ) - d(prec, orig) - d(orig, succ) <= costante

con d = `contracts.distanza_a_piedi_m` e i punti di `engine._progressione`.
- Un segmento con un estremo senza punto vale 0, sia nei termini vecchi sia nei
  nuovi (regola esistente di `_metri_ordine`: coppia con una tappa senza punto
  non conta).
- Prima tappa: nessun termine "prec". Ultima: nessun termine "succ".
- Nessun candidato nel limite -> la tappa resta `MANTENUTA_SENZA_ALTERNATIVA`.
- PRECEDENZA DELLA PIOGGIA: se la tappa e' toccata dalla pioggia (meteo
  pioggia e `al_chiuso=False`) vale la regola della pioggia e il limite NON si
  applica, anche se il luogo e' affollato.

Geometria: piano con x metri verso est e y verso nord; i punti stanno su una
linea (y = 0) salvo i "lontani", spostati di 2000 m a nord.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Punto,
    Signal,
    distanza_a_piedi_m,
)
from experience_engine import adapt_itinerary
from experience_engine import engine as motore
from experience_engine import rules as regole
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import adapt_reason, compose_reason

NOME = "AUMENTO_CAMMINO_MAX_AFFOLLAMENTO_M"
FOLLA = 0.75
PROFILO = EmotionalProfile(
    curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
    tempo_disponibile_min=600,
)
TEMA = "tema-x"
LIMITE = 300  # metri, valore di prova (monkeypatch)


def punto(x: float, y: float = 0.0) -> Punto:
    return Punto(lat=43.84 + y / 111_000, lon=10.50 + x / 80_300)


def _nodo(
    id_: str, pos: Punto | None, *, place: str | None = None, al_chiuso: bool = False,
    temi: list[str] | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=place or f"luogo-{id_}",
            temi=temi or [], durata_min=30, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Luogo {id_}",
        connessioni=[],
        punti_arrivo=[pos] if pos is not None else [],
    )


def _itinerario(ids: list[str]) -> Itinerary:
    stops = [
        ItineraryStop(
            experience_id=id_, arrivo=time(9 + i, 0), durata_min=30, reason="Motivo originale.",
        )
        for i, id_ in enumerate(ids)
    ]
    return Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))


def _segnale(
    meteo: Literal["sereno", "pioggia"] = "sereno",
    affollati: tuple[str, ...] = ("luogo-orig",),
) -> Signal:
    return Signal(
        meteo=meteo,
        affollamento={p: FOLLA for p in affollati},
        stanchezza=0.0,
        ora=time(9, 0),
    )


def _d(a: Punto | None, b: Punto | None) -> int:
    """Segmento con un estremo senza punto = 0 (regola di `_metri_ordine`)."""
    if a is None or b is None:
        return 0
    return distanza_a_piedi_m(a, b)


def _aumento(
    prec: Punto | None, orig: Punto | None, succ: Punto | None, sost: Punto | None,
    *, ha_prec: bool = True, ha_succ: bool = True,
) -> int:
    nuovi = (_d(prec, sost) if ha_prec else 0) + (_d(sost, succ) if ha_succ else 0)
    vecchi = (_d(prec, orig) if ha_prec else 0) + (_d(orig, succ) if ha_succ else 0)
    return nuovi - vecchi


def _adatta(
    ids: list[str], segnale: Signal, candidati: list[GraphCandidate]
) -> Itinerary:
    return adapt_itinerary(
        _itinerario(ids), segnale, candidati, PROFILO, compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )


def _imposta(monkeypatch: pytest.MonkeyPatch, valore: int) -> None:
    # raising=False: se la costante non esiste ancora il test deve fallire per
    # il COMPORTAMENTO (il motore la ignora), non per un AttributeError opaco.
    monkeypatch.setattr(motore, NOME, valore, raising=False)


# Scenario base: prec(0) - orig(500, all'aperto, affollata) - succ(1000).
PREC = punto(0)
ORIG = punto(500)
SUCC = punto(1000)
VICINO = punto(550)
LONTANO = punto(500, 2000)


def _scenario(
    extra: list[GraphCandidate], *, meteo: Literal["sereno", "pioggia"] = "sereno"
) -> Itinerary:
    base = [
        _nodo("prec", PREC, al_chiuso=True),
        _nodo("orig", ORIG, al_chiuso=False, temi=[TEMA]),
        _nodo("succ", SUCC, al_chiuso=True),
    ]
    return _adatta(["prec", "orig", "succ"], _segnale(meteo), [*base, *extra])


# --- la costante -------------------------------------------------------------


def test_la_costante_esiste_in_rules_ed_e_un_int_positivo() -> None:
    valore = getattr(regole, NOME, None)
    assert valore is not None, f"manca rules.{NOME}"
    assert isinstance(valore, int) and not isinstance(valore, bool)
    assert valore > 0


def test_il_motore_espone_il_nome_globale_per_il_monkeypatch() -> None:
    assert hasattr(motore, NOME), f"engine deve importare {NOME} come nome globale"
    assert getattr(motore, NOME) == getattr(regole, NOME, None)


def test_scenario_guardia_le_distanze_sono_quelle_attese() -> None:
    assert _aumento(PREC, ORIG, SUCC, VICINO) <= LIMITE
    assert _aumento(PREC, ORIG, SUCC, LONTANO) > LIMITE


# --- sostituto vicino / lontano ----------------------------------------------


def test_sostituto_vicino_nel_limite_e_ammesso(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposta(monkeypatch, LIMITE)
    r = _scenario([_nodo("vicino", VICINO)])
    assert [s.experience_id for s in r.stops] == ["prec", "vicino", "succ"]
    assert r.stops[1].esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_sostituto_lontano_scartato_a_favore_di_uno_nel_limite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il lontano ha il tema in comune con la tappa tolta (preferenza forte) ma
    sfora il limite: vince il vicino anche se di tema peggiore."""
    _imposta(monkeypatch, LIMITE)
    lontano = _nodo("lontano", LONTANO, temi=[TEMA])
    vicino = _nodo("vicino", VICINO, temi=[])
    r = _scenario([lontano, vicino])
    assert [s.experience_id for s in r.stops] == ["prec", "vicino", "succ"]


def test_nessun_sostituto_nel_limite_mantenuta_senza_alternativa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _imposta(monkeypatch, LIMITE)
    r = _scenario([_nodo("lontano", LONTANO, temi=[TEMA])])
    assert [s.experience_id for s in r.stops] == ["prec", "orig", "succ"]
    assert r.stops[1].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert r.stops[1].reason.strip()


def test_il_limite_e_inclusivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """aumento == costante e' ammesso; costante = aumento - 1 no."""
    cand = _nodo("lontano", LONTANO)
    aumento = _aumento(PREC, ORIG, SUCC, LONTANO)
    assert aumento > 0
    _imposta(monkeypatch, aumento)
    assert _scenario([cand]).stops[1].experience_id == "lontano"
    _imposta(monkeypatch, aumento - 1)
    assert _scenario([cand]).stops[1].experience_id == "orig"


# --- precedenza della pioggia -------------------------------------------------


def test_pioggia_e_folla_sulla_stessa_tappa_il_limite_non_si_applica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La tappa e' all'aperto, in un luogo affollato E sotto la pioggia: vale la
    regola della pioggia (solo al chiuso, nessun limite al cammino). Il sostituto
    lontano al chiuso e' ammesso anche se sfora la costante."""
    _imposta(monkeypatch, LIMITE)
    lontano_chiuso = _nodo("lontano", LONTANO, al_chiuso=True)
    assert _aumento(PREC, ORIG, SUCC, LONTANO) > LIMITE
    r = _scenario([lontano_chiuso], meteo="pioggia")
    assert [s.experience_id for s in r.stops] == ["prec", "lontano", "succ"]
    assert r.stops[1].esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_pioggia_senza_folla_il_limite_non_si_applica_nemmeno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _imposta(monkeypatch, LIMITE)
    base = [
        _nodo("prec", PREC, al_chiuso=True),
        _nodo("orig", ORIG, al_chiuso=False),
        _nodo("succ", SUCC, al_chiuso=True),
        _nodo("lontano", LONTANO, al_chiuso=True),
    ]
    r = _adatta(["prec", "orig", "succ"], _segnale("pioggia", affollati=()), base)
    assert r.stops[1].experience_id == "lontano"


# --- tappe e sostituti senza punto; prima e ultima tappa ----------------------


def test_tappa_da_sostituire_senza_punto_i_suoi_segmenti_valgono_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La tappa tolta non ha punto: d(prec, orig) e d(orig, succ) valgono 0
    (regola di `_metri_ordine`), quindi l'aumento e' d(prec, sost) + d(sost, succ)
    per intero. Un candidato sulla linea costa comunque ~ d(prec, succ)."""
    sost = punto(500)
    aumento = _aumento(PREC, None, SUCC, sost)
    assert aumento == _d(PREC, sost) + _d(sost, SUCC) > 0
    base = [
        _nodo("prec", PREC, al_chiuso=True),
        _nodo("orig", None, al_chiuso=False),
        _nodo("succ", SUCC, al_chiuso=True),
        _nodo("sost", sost),
    ]
    _imposta(monkeypatch, aumento)
    r = _adatta(["prec", "orig", "succ"], _segnale(), base)
    assert r.stops[1].experience_id == "sost"
    _imposta(monkeypatch, aumento - 1)
    r = _adatta(["prec", "orig", "succ"], _segnale(), base)
    assert r.stops[1].experience_id == "orig"
    assert r.stops[1].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


def test_sostituto_senza_punto_i_suoi_segmenti_valgono_zero_ed_e_ammesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il sostituto non ha punto: d(prec, sost) e d(sost, succ) valgono 0, quindi
    l'aumento e' -(d(prec, orig) + d(orig, succ)) <= 0, ammesso con qualunque
    costante positiva."""
    assert _aumento(PREC, ORIG, SUCC, None) < 0
    _imposta(monkeypatch, 1)
    r = _scenario([_nodo("senza-punto", None)])
    assert r.stops[1].experience_id == "senza-punto"
    assert r.stops[1].esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_prima_tappa_nessun_termine_prec(monkeypatch: pytest.MonkeyPatch) -> None:
    """orig e' la prima tappa: aumento = d(sost, succ) - d(orig, succ)."""
    orig = punto(0)
    succ = punto(1000)
    vicino = punto(100)  # piu' vicino a succ: aumento negativo
    lontano = punto(-2000)
    assert _aumento(None, orig, succ, vicino, ha_prec=False) < 0
    aumento_lontano = _aumento(None, orig, succ, lontano, ha_prec=False)
    assert aumento_lontano > LIMITE
    _imposta(monkeypatch, LIMITE)
    base = [
        _nodo("orig", orig, al_chiuso=False, temi=[TEMA]),
        _nodo("succ", succ, al_chiuso=True),
    ]
    sol = _adatta(
        ["orig", "succ"], _segnale(),
        [*base, _nodo("lontano", lontano, temi=[TEMA]), _nodo("vicino", vicino)],
    )
    assert [s.experience_id for s in sol.stops] == ["vicino", "succ"]
    solo_lontano = _adatta(["orig", "succ"], _segnale(), [*base, _nodo("lontano", lontano)])
    assert solo_lontano.stops[0].experience_id == "orig"
    assert solo_lontano.stops[0].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


def test_ultima_tappa_nessun_termine_succ(monkeypatch: pytest.MonkeyPatch) -> None:
    """orig e' l'ultima tappa: aumento = d(prec, sost) - d(prec, orig)."""
    prec = punto(0)
    orig = punto(500)
    vicino = punto(450)
    lontano = punto(500, 2000)
    assert _aumento(prec, orig, None, vicino, ha_succ=False) <= LIMITE
    assert _aumento(prec, orig, None, lontano, ha_succ=False) > LIMITE
    _imposta(monkeypatch, LIMITE)
    base = [
        _nodo("prec", prec, al_chiuso=True),
        _nodo("orig", orig, al_chiuso=False, temi=[TEMA]),
    ]
    r = _adatta(
        ["prec", "orig"], _segnale(),
        [*base, _nodo("lontano", lontano, temi=[TEMA]), _nodo("vicino", vicino)],
    )
    assert [s.experience_id for s in r.stops] == ["prec", "vicino"]
    solo = _adatta(["prec", "orig"], _segnale(), [*base, _nodo("lontano", lontano)])
    assert solo.stops[1].experience_id == "orig"
    assert solo.stops[1].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
