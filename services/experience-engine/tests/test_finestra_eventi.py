"""Finestra temporale degli `:Evento` promossi (gate del motore) - puri.

Date FISSE ovunque (mai `date.today()`): i test non dipendono dal giorno in
cui girano. Vocabolario: `ultima_occorrenza` + k*cadenza (k intero >= 1) e
finestra = FRAZIONE_FINESTRA_CADENZA * cadenza, bordo incluso.

Copre: (a) dentro compare, (b) fuori no, (c) data assente -> nessun evento
(fail-closed), (d) la finestra scala con la cadenza, (e) bordo incluso / appena
fuori (anche float), (f) proiezione a k>1, tie deterministico, visita
anteriore -> k=1, (j) invarianti (in coda, nessuna sostituzione, budget,
score invariato).
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Signal,
    VisitorContext,
)
from experience_engine import compose_itinerary, rules
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import compose_reason

ULTIMA = date(2026, 3, 2)  # lunedi


def _giorni(n: int) -> date:
    return ULTIMA + timedelta(days=n)


def _evento(cadenza: float, *, id_: str = "evento-luogo-fisso-musica", temi=None) -> EventoPromosso:
    return EventoPromosso(
        id=id_, place_id="luogo-fisso", temi=temi or ["musica"],
        ultima_occorrenza=ULTIMA, cadenza_giorni=cadenza,
    )


def _profilo(tempo: int = 200) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=tempo,
    )


def _candidato(durata_min: int = 30) -> GraphCandidate:
    esperienza = ExperienceNode(
        id="exp-fisso", titolo="Facciata Barocca", place_id="luogo-fisso",
        temi=["arte"], durata_min=durata_min, al_chiuso=False, accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Piazza Fissa", connessioni=['Evoca il tema "Arte".']
    )


def _signal(data: date | None) -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=data)


def _compose(eventi, data: date | None, tempo: int = 200, candidati=None):
    ctx = VisitorContext(person_id="p", profile=_profilo(tempo), signal=_signal(data))
    return compose_itinerary(
        ctx,
        candidati or [_candidato()],
        compose_reason,
        eventi_promossi=eventi,
        vocabolario=VOCABOLARIO,
    )


# --- (a) dentro / (b) fuori / (c) data assente (end-to-end nel motore) ------


def test_a_evento_in_finestra_compare() -> None:
    evento = _evento(7.0)
    it = _compose([evento], _giorni(7))
    assert [s.experience_id for s in it.stops] == ["exp-fisso", evento.id]


def test_b_evento_fuori_finestra_non_compare() -> None:
    it = _compose([_evento(7.0)], _giorni(10))  # 3 giorni dall'occorrenza, finestra 1,05
    assert [s.experience_id for s in it.stops] == ["exp-fisso"]


def test_c_data_assente_nessun_evento_fail_closed() -> None:
    # Stesso evento che in (a) compare: e' SOLO l'assenza di data a escluderlo.
    assert len(_compose([_evento(7.0)], _giorni(7)).stops) == 2
    it = _compose([_evento(7.0)], None)
    assert [s.experience_id for s in it.stops] == ["exp-fisso"]
    assert rules.eventi_promossi_pertinenti(
        [_evento(7.0)], _profilo(), None, vocabolario=VOCABOLARIO,
    ) == []


# --- (d) la finestra scala con la cadenza -----------------------------------


def test_d_stesso_scarto_dentro_per_mensile_fuori_per_settimanale() -> None:
    # Scarto di 3 giorni dall'occorrenza attesa in entrambi i casi.
    assert rules.evento_in_finestra(ULTIMA, 30.0, _giorni(27)) is True  # finestra 4,5
    assert rules.evento_in_finestra(ULTIMA, 30.0, _giorni(33)) is True
    assert rules.evento_in_finestra(ULTIMA, 7.0, _giorni(4)) is False  # finestra 1,05
    assert rules.evento_in_finestra(ULTIMA, 7.0, _giorni(10)) is False

    profilo = _profilo()
    mensile = rules.eventi_promossi_pertinenti(
        [_evento(30.0)], profilo, _giorni(27), vocabolario=VOCABOLARIO,
    )
    settimanale = rules.eventi_promossi_pertinenti(
        [_evento(7.0)], profilo, _giorni(4), vocabolario=VOCABOLARIO,
    )
    assert len(mensile) == 1 and settimanale == []


# --- (e) bordo ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("cadenza", "delta", "atteso"),
    [
        (20.0, 23, True),  # semi-ampiezza 3,0: bordo ESATTO incluso
        (20.0, 17, True),  # bordo esatto dal lato basso
        (20.0, 24, False),  # appena fuori (4 > 3)
        (20.0, 16, False),
        (7.0, 8, True),  # 1 <= 1,05
        (7.0, 9, False),  # 2 > 1,05
        (7.0, 6, True),
        (7.0, 5, False),
    ],
)
def test_e_bordo_incluso_appena_fuori_escluso(cadenza: float, delta: int, atteso: bool) -> None:
    assert rules.evento_in_finestra(ULTIMA, cadenza, _giorni(delta)) is atteso


def test_e_bordo_float_distanza_esatta_uno_e_dentro() -> None:
    # cadenza 20/3: semi-ampiezza = 0,15*20/3 = 1,0 (in reale); k=3 -> 20 giorni.
    cadenza = 20 / 3
    # delta 21: distanza 1,0 esatta (in aritmetica reale) -> DENTRO nonostante il float.
    assert rules.evento_in_finestra(ULTIMA, cadenza, _giorni(21)) is True
    assert rules.evento_in_finestra(ULTIMA, cadenza, _giorni(19)) is True
    # distanza 2 -> fuori
    assert rules.evento_in_finestra(ULTIMA, cadenza, _giorni(22)) is False
    assert rules.evento_in_finestra(ULTIMA, cadenza, _giorni(18)) is False


# --- (f) proiezione, tie, visita anteriore ----------------------------------


def test_f_occorrenza_saltata_proiettata_a_k_maggiore_di_uno() -> None:
    # Ultima 15 giorni fa, settimanale: la 1a attesa (giorno 7) e' saltata;
    # l'occorrenza piu' vicina e' k=2 (giorno 14), a 1 giorno -> in finestra.
    visita = _giorni(15)
    assert rules.occorrenza_attesa_giorni(ULTIMA, 7.0, visita) == 14.0
    assert rules.giorno_occorrenza_attesa(ULTIMA, 7.0, visita) == _giorni(14)
    assert rules.evento_in_finestra(ULTIMA, 7.0, visita) is True
    # k=2 e non solo k=1: senza proiezione giorno 15 sarebbe fuori (8 giorni da 7).
    assert _compose([_evento(7.0)], visita).stops[-1].experience_id == _evento(7.0).id


def test_f_tie_floor_ceil_vince_il_k_minore_deterministico() -> None:
    # cadenza 10, delta 15: k=1 (10) e k=2 (20) a pari distanza 5.
    assert rules.occorrenza_attesa_giorni(ULTIMA, 10.0, _giorni(15)) == 10.0
    assert rules.occorrenza_attesa_giorni(ULTIMA, 10.0, _giorni(25)) == 20.0
    for _ in range(3):  # ripetibile
        assert rules.occorrenza_attesa_giorni(ULTIMA, 10.0, _giorni(15)) == 10.0


@pytest.mark.parametrize("delta", [0, -1, -5, -40])
def test_f_visita_stesso_giorno_o_prima_dellultima_usa_k1(delta: int) -> None:
    assert rules.occorrenza_attesa_giorni(ULTIMA, 7.0, _giorni(delta)) == 7.0
    assert rules.giorno_occorrenza_attesa(ULTIMA, 7.0, _giorni(delta)) == _giorni(7)
    # la visita e' a >= 7 giorni dall'occorrenza attesa: fuori finestra (settimanale)
    assert rules.evento_in_finestra(ULTIMA, 7.0, _giorni(delta)) is False


# --- (j) invarianti ----------------------------------------------------------


def test_j_in_coda_mai_sostituzione_budget_e_score_invariato() -> None:
    cand = _candidato()
    profilo = _profilo(tempo=60)  # 30 + (10 trasf. + 15) = 55 <= 60; il 2o evento (80) no
    data = _giorni(7)
    ctx = VisitorContext(person_id="p", profile=profilo, signal=_signal(data))
    eventi = [
        _evento(7.0, id_="evento-a"),
        _evento(7.0, id_="evento-b", temi=["musica", "liuteria"]),
    ]

    score_prima = rules.calcola_score(cand, profilo, ctx.signal, vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        ctx, [cand], compose_reason, eventi_promossi=eventi, vocabolario=VOCABOLARIO,
    )
    senza = compose_itinerary(ctx, [cand], compose_reason, vocabolario=VOCABOLARIO)
    score_dopo = rules.calcola_score(cand, profilo, ctx.signal, vocabolario=VOCABOLARIO)

    assert score_prima == score_dopo  # bit-identico, `==` voluto

    # in coda: il prefisso e' l'itinerario senza eventi, intatto
    n = len(senza.stops)
    assert [s.model_dump() for s in con.stops[:n]] == [s.model_dump() for s in senza.stops]
    extra = con.stops[n:]
    assert extra, "l'evento in finestra deve essere aggiunto"
    assert all(s.experience_id.startswith("evento-") for s in extra)
    # nessuna sostituzione: tutte le tappe reali ci sono ancora
    assert [s.experience_id for s in con.stops if not s.experience_id.startswith("evento-")] == [
        s.experience_id for s in senza.stops
    ]
    # budget rispettato, mai forzato
    assert sum(s.durata_min for s in con.stops) <= profilo.tempo_disponibile_min
    assert [s.experience_id for s in extra] == ["evento-a"]
    assert all(s.reason.strip() for s in con.stops)


def test_j_score_invariato_con_e_senza_eventi_in_finestra() -> None:
    cand = _candidato()
    profilo = _profilo()
    sig = _signal(_giorni(7))
    prima = rules.calcola_score(cand, profilo, sig, vocabolario=VOCABOLARIO)
    _compose([_evento(7.0)], _giorni(7))
    assert rules.calcola_score(cand, profilo, sig, vocabolario=VOCABOLARIO) == prima
