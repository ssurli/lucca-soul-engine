"""Trasferimento tra tappe consecutive dai punti di arrivo (ondata 3, compito 4).

Il trasferimento verso una tappa dipende dalla tappa PRECEDENTE:
`stima_trasferimento_min(distanza_a_piedi_m(punto precedente, punto scelto))`
se entrambe hanno un punto, altrimenti `TEMPO_TRASFERIMENTO_DEFAULT_MIN`. Il
punto di arrivo della tappa (`ItineraryStop.punto_arrivo`): prima tappa -> il
primo di `punti_arrivo`; poi il più vicino al punto della precedente; se la
precedente non ha un punto, il primo. `distanza_m` (distanza dal luogo già
visitato) non entra più nel trasferimento.

Coordinate vere dal dataset di Lucca (`graph.seed_lucca.DATASET`): Duomo ->
San Michele = 362 m in linea d'aria, 470 m a piedi, 6 minuti.

In fondo la guardia AST sugli ORDINAMENTI del motore: le coordinate decidono
tempo e link, mai l'ordine per affinità.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from collections.abc import Callable
from datetime import UTC, datetime, time
from pathlib import Path

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
    VisitorContext,
    VocabolarioTemi,
    distanza_a_piedi_m,
    distanza_linea_aria_m,
)
from experience_engine import adapt_itinerary, compose_itinerary
from experience_engine import engine as motore
from experience_engine.rules import TEMPO_TRASFERIMENTO_DEFAULT_MIN, stima_trasferimento_min
from graph.seed_lucca import DATASET

sys.path.insert(0, str(Path(__file__).parent))
from test_scoring_non_legge_punti import letture_posizione  # noqa: E402

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)

_LUOGHI = {lg.id: lg for lg in DATASET.luoghi}
_ESPERIENZE = {e.id: e for e in DATASET.esperienze}


def _punto_luogo(place_id: str) -> Punto:
    punto = _LUOGHI[place_id].punto
    assert punto is not None, place_id
    return punto


DUOMO = _punto_luogo("duomo-san-martino")
SAN_MICHELE = _punto_luogo("san-michele-in-foro")
NAPOLEONE = _punto_luogo("piazza-napoleone")
SAN_FREDIANO = _punto_luogo("san-frediano")
ORTO = _punto_luogo("orto-botanico")
RAMPE_MURA = list(_ESPERIENZE["exp-passeggiata-mura"].punti_arrivo)
PUNTI_TRAMONTO = list(_ESPERIENZE["exp-tramonto-baluardo"].punti_arrivo)

ORA = time(10, 0)


def _cand(
    id_: str,
    punti: list[Punto],
    *,
    durata: int = 30,
    al_chiuso: bool = True,
    distanza_m: int | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=f"luogo-{id_}", temi=["arte"],
            durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Luogo {id_}",
        connessioni=[],
        punti_arrivo=punti,
        distanza_m=distanza_m,
    )


def _componi(cands: list[GraphCandidate], minuti: int = 600) -> Itinerary:
    """Ordine imposto da uno score per posizione nella lista (il primo vince)."""
    punteggi = {c.experience.id: 1.0 - i / 100 for i, c in enumerate(cands)}
    ctx = VisitorContext(
        person_id="p",
        profile=EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
            tempo_disponibile_min=minuti,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA),
    )
    return compose_itinerary(
        ctx, cands, score_fn=lambda c, _p, _s: punteggi[c.experience.id], vocabolario=VOC
    )


def _minuti(t: time) -> int:
    return t.hour * 60 + t.minute


def _piu_vicino_a_mano(rif: Punto, punti: list[Punto]) -> int:
    """Indice del punto più vicino, calcolato qui senza `punto_piu_vicino`."""
    distanze = [distanza_linea_aria_m(rif, p) for p in punti]
    return distanze.index(min(distanze))


# --- I numeri del caso Duomo -> San Michele -----------------------------------


def test_duomo_san_michele_362_m_in_linea_d_aria_470_a_piedi_6_minuti() -> None:
    assert round(distanza_linea_aria_m(DUOMO, SAN_MICHELE)) == 362
    assert distanza_a_piedi_m(DUOMO, SAN_MICHELE) == 470
    assert stima_trasferimento_min(470) == 6


def test_trasferimento_reale_tra_due_tappe_con_punto() -> None:
    it = _componi([_cand("duomo", [DUOMO], durata=35), _cand("michele", [SAN_MICHELE])])
    primo, secondo = it.stops
    assert primo.arrivo == ORA
    assert _minuti(secondo.arrivo) == _minuti(ORA) + 35 + 6
    assert primo.punto_arrivo == DUOMO
    assert secondo.punto_arrivo == SAN_MICHELE


def test_distanza_m_non_entra_piu_nel_trasferimento() -> None:
    """`distanza_m` (dal luogo GIÀ VISITATO) enorme o nulla: stesso arrivo."""
    lontano = _componi([_cand("a", [DUOMO]), _cand("b", [SAN_MICHELE], distanza_m=5000)])
    zero = _componi([_cand("a", [DUOMO]), _cand("b", [SAN_MICHELE], distanza_m=0)])
    assert lontano.stops[1].arrivo == zero.stops[1].arrivo
    assert _minuti(zero.stops[1].arrivo) == _minuti(ORA) + 30 + 6


# --- Fallback: una delle due tappe senza punto (bottega) -----------------------


@pytest.mark.parametrize(
    ("punti_a", "punti_b"),
    [([DUOMO], []), ([], [SAN_MICHELE]), ([], [])],
    ids=["seconda-bottega", "prima-bottega", "entrambe-senza"],
)
def test_senza_punto_vale_la_stima_prudente(punti_a: list[Punto], punti_b: list[Punto]) -> None:
    it = _componi([_cand("a", punti_a), _cand("b", punti_b)])
    assert _minuti(it.stops[1].arrivo) == _minuti(ORA) + 30 + TEMPO_TRASFERIMENTO_DEFAULT_MIN
    assert it.stops[0].punto_arrivo == (punti_a[0] if punti_a else None)
    # Precedente senza punto -> il primo della lista; nessun punto -> None.
    assert it.stops[1].punto_arrivo == (punti_b[0] if punti_b else None)


def test_la_bottega_non_ha_punto_e_la_tappa_dopo_prende_il_primo() -> None:
    it = _componi(
        [_cand("a", [DUOMO]), _cand("bottega", []), _cand("mura", RAMPE_MURA, al_chiuso=False)]
    )
    assert [s.punto_arrivo for s in it.stops] == [DUOMO, None, RAMPE_MURA[0]]
    assert _minuti(it.stops[2].arrivo) == _minuti(ORA) + 2 * (30 + TEMPO_TRASFERIMENTO_DEFAULT_MIN)


# --- Scelta del punto: prima tappa = primo; poi il più vicino alla precedente ---


def test_prima_tappa_e_il_primo_della_lista() -> None:
    it = _componi([_cand("mura", RAMPE_MURA, al_chiuso=False), _cand("b", [NAPOLEONE])])
    assert it.stops[0].punto_arrivo == RAMPE_MURA[0]
    assert it.stops[0].arrivo == ORA


@pytest.mark.parametrize(
    ("precedente", "punti"),
    [(NAPOLEONE, RAMPE_MURA), (SAN_FREDIANO, RAMPE_MURA), (DUOMO, PUNTI_TRAMONTO)],
    ids=["napoleone-mura", "san-frediano-mura", "duomo-tramonto"],
)
def test_tappa_successiva_al_punto_piu_vicino_alla_precedente(
    precedente: Punto, punti: list[Punto]
) -> None:
    assert len(punti) >= 5
    atteso = punti[_piu_vicino_a_mano(precedente, punti)]
    it = _componi([_cand("prima", [precedente]), _cand("dopo", punti, al_chiuso=False)])
    assert it.stops[1].punto_arrivo == atteso
    minuti = stima_trasferimento_min(distanza_a_piedi_m(precedente, atteso))
    assert _minuti(it.stops[1].arrivo) == _minuti(ORA) + 30 + minuti


def test_almeno_un_caso_sceglie_un_punto_diverso_dal_primo() -> None:
    """Il caso non è banale: da San Frediano la rampa più vicina non è la prima."""
    assert _piu_vicino_a_mano(SAN_FREDIANO, RAMPE_MURA) != 0


# --- Budget: lo stesso conteggio della progressione -----------------------------


def test_il_budget_conta_i_trasferimenti_reali() -> None:
    """35 + 6 + 30 = 71: entra in 71 minuti, non in 70 (con la stima prudente
    di 10 minuti servirebbero 75)."""
    cands = [_cand("duomo", [DUOMO], durata=35), _cand("michele", [SAN_MICHELE])]
    assert [s.experience_id for s in _componi(cands, minuti=71).stops] == ["duomo", "michele"]
    assert [s.experience_id for s in _componi(cands, minuti=70).stops] == ["duomo"]


# --- Adattamento ----------------------------------------------------------------


def _stop(c: GraphCandidate, arrivo: time, punto: Punto | None = None) -> ItineraryStop:
    return ItineraryStop(
        experience_id=c.experience.id, arrivo=arrivo, durata_min=c.experience.durata_min,
        reason="Motivo.", punto_arrivo=punto,
    )


def test_sostituzione_cambia_il_trasferimento_della_successiva() -> None:
    """X (all'aperto, al Duomo) sostituita per pioggia da Z (al chiuso,
    all'Orto botanico): Y (San Michele) arriva da Z, non più da X."""
    x = _cand("x", [DUOMO], al_chiuso=False)
    y = _cand("y", [SAN_MICHELE])
    z = _cand("z", [ORTO])
    prima = 30 + stima_trasferimento_min(distanza_a_piedi_m(DUOMO, SAN_MICHELE))
    it = Itinerary(
        person_id="p",
        stops=[_stop(x, ORA, DUOMO), _stop(y, time(10, prima), SAN_MICHELE)],
        generated_at="2026-06-15T10:00:00",
    )
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=ORA)
    ad = adapt_itinerary(it, pioggia, [x, y, z], vocabolario=VOC)
    assert [s.experience_id for s in ad.stops] == ["z", "y"]
    assert ad.stops[0].esito_adattamento is EsitoAdattamento.SOSTITUITA
    dopo = 30 + stima_trasferimento_min(distanza_a_piedi_m(ORTO, SAN_MICHELE))
    assert dopo > prima
    assert _minuti(ad.stops[1].arrivo) == _minuti(ORA) + dopo
    assert [s.punto_arrivo for s in ad.stops] == [ORTO, SAN_MICHELE]


def test_il_budget_della_sostituzione_conta_il_trasferimento_della_successiva() -> None:
    """Budget 65. Il sostituto "a-lontana" (Orto botanico) vincerebbe a parità
    di score per id, ma il trasferimento da lei verso Y (San Michele) porta il
    totale oltre 65; "b-vicina" (stesso punto di Y) dà 30 + 0 + 30 = 60. Il
    sostituto ammesso è quello per cui ANCHE il trasferimento della tappa
    SUCCESSIVA sta nel budget."""
    x = _cand("x", [DUOMO], al_chiuso=False)
    y = _cand("y", [SAN_MICHELE])
    lontana = _cand("a-lontana", [ORTO])  # vince a parità di score
    vicina = _cand("b-vicina", [SAN_MICHELE])
    da_lontana = stima_trasferimento_min(
        distanza_a_piedi_m(ORTO, SAN_MICHELE)
    )
    assert 30 + da_lontana + 30 > 65 >= 60
    it = Itinerary(
        person_id="p",
        stops=[_stop(x, ORA, DUOMO), _stop(y, time(10, 36), SAN_MICHELE)],
        generated_at="2026-06-15T10:00:00",
        tempo_disponibile_min=65,
        tempo_effettivo_min=65,
    )
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=ORA)
    ad = adapt_itinerary(it, pioggia, [x, y, lontana, vicina], vocabolario=VOC)
    assert [s.experience_id for s in ad.stops] == ["b-vicina", "y"]
    assert ad.stops[1].arrivo == time(10, 30)


def test_adattamento_senza_cambi_conserva_gli_arrivi_e_scrive_il_punto() -> None:
    """Itinerario vecchio senza `punto_arrivo`: nessun cambio, arrivi ricevuti
    invariati, punto di arrivo ricalcolato dal catalogo."""
    a = _cand("a", [NAPOLEONE])
    mura = _cand("mura", RAMPE_MURA)
    it = Itinerary(
        person_id="p",
        stops=[_stop(a, ORA), _stop(mura, time(10, 40))],
        generated_at="2026-06-15T10:00:00",
    )
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA)
    ad = adapt_itinerary(it, sereno, [a, mura], vocabolario=VOC)
    assert ad.adattato_da_segnale is False
    assert [s.arrivo for s in ad.stops] == [ORA, time(10, 40)]
    atteso = RAMPE_MURA[_piu_vicino_a_mano(NAPOLEONE, RAMPE_MURA)]
    assert [s.punto_arrivo for s in ad.stops] == [NAPOLEONE, atteso]


def test_tappa_non_piu_nel_catalogo_stima_prudente_e_punto_ricevuto() -> None:
    """Una tappa la cui esperienza non è più tra i candidati (stub) conserva il
    `punto_arrivo` ricevuto ma non entra nelle distanze: trasferimento verso di
    lei e verso la successiva = stima prudente."""
    x = _cand("x", [DUOMO], al_chiuso=False)
    z = _cand("z", [SAN_FREDIANO])
    y = _cand("y", [SAN_MICHELE])
    sparita = _cand("sparita", [NAPOLEONE], durata=20)
    it = Itinerary(
        person_id="p",
        stops=[
            _stop(x, ORA, DUOMO),
            _stop(sparita, time(10, 40), NAPOLEONE),
            _stop(y, time(11, 10), SAN_MICHELE),
        ],
        generated_at="2026-06-15T10:00:00",
    )
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=ORA)
    ad = adapt_itinerary(it, pioggia, [x, y, z], vocabolario=VOC)
    assert [s.experience_id for s in ad.stops] == ["z", "sparita", "y"]
    assert [s.punto_arrivo for s in ad.stops] == [SAN_FREDIANO, NAPOLEONE, SAN_MICHELE]
    d = TEMPO_TRASFERIMENTO_DEFAULT_MIN
    assert [_minuti(s.arrivo) for s in ad.stops] == [
        _minuti(ORA),
        _minuti(ORA) + 30 + d,
        _minuti(ORA) + 30 + d + 20 + d,
    ]


def test_tappe_fluttuanti_senza_punto_e_stima_prudente() -> None:
    from contracts import SegnaleFluttuante

    segnale = SegnaleFluttuante(
        id="violino", place_id="luogo-a", temi=["arte"], descrizione="Un violinista",
        non_commerciale=True, valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    ctx = VisitorContext(
        person_id="p",
        profile=EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
            tempo_disponibile_min=600,
        ),
        signal=Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA, eventi_attivi=[segnale]
        ),
    )
    it = compose_itinerary(ctx, [_cand("a", [DUOMO])], vocabolario=VOC)
    assert [s.experience_id for s in it.stops] == ["a", "fluttuante-violino"]
    assert it.stops[1].punto_arrivo is None
    assert _minuti(it.stops[1].arrivo) == _minuti(ORA) + 30 + TEMPO_TRASFERIMENTO_DEFAULT_MIN


# --- Guardia AST: le coordinate non decidono l'ORDINE ---------------------------


def _chiavi_di_ordinamento(fn: Callable[..., object]) -> list[ast.AST]:
    albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    chiavi: list[ast.AST] = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Call):
            for kw in nodo.keywords:
                if kw.arg == "key":
                    chiavi.append(kw.value)
    return chiavi


def test_ordinamenti_del_motore_non_leggono_le_coordinate() -> None:
    """`_ordina_per_score` per intero e le chiavi di ordinamento di
    `_migliore_alternativa`: nessuna lettura di posizione (punti, distanze a
    piedi, punto più vicino, progressione dei trasferimenti)."""
    sorgente = textwrap.dedent(inspect.getsource(motore._ordina_per_score))
    assert letture_posizione(ast.parse(sorgente)) == []
    chiavi = _chiavi_di_ordinamento(motore._migliore_alternativa)
    assert chiavi, "perimetro della guardia incompleto"
    for chiave in chiavi:
        assert letture_posizione(chiave) == [], ast.unparse(chiave)
        nomi = {n.id for n in ast.walk(chiave) if isinstance(n, ast.Name)}
        nomi |= {n.attr for n in ast.walk(chiave) if isinstance(n, ast.Attribute)}
        assert not nomi & {"_passo", "_progressione", "_arrivo_in_posizione"}, nomi


# --- Frase «A … m da …, già visitato»: stessa distanza a piedi -------------------


def test_frase_gia_visitato_con_la_distanza_dai_punti() -> None:
    """Dal Duomo già visitato a San Michele: 470 m a piedi (non i 300 dell'arco
    VICINO), sia nel `reason` della RAG sia nel fallback del motore."""
    from graph.source import SeedCandidateSource
    from rag.reasons import compose_reason

    ctx = VisitorContext(
        person_id="p",
        profile=EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
            tempo_disponibile_min=180,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA),
        luoghi_gia_visti=["duomo-san-martino"],
    )
    facciata = next(
        c
        for c in SeedCandidateSource().candidates(ctx)
        if c.experience.id == "exp-facciata-san-michele"
    )
    frase = "A 470 m dal Duomo di San Martino, già visitato."
    assert facciata.distanza_m == distanza_a_piedi_m(DUOMO, SAN_MICHELE) == 470
    assert compose_reason(facciata, ctx.profile, [], prima_tappa=False).endswith(frase)
    assert motore._fallback_reason(facciata, ctx.profile, [], prima_tappa=False).endswith(frase)
