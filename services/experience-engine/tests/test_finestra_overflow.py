"""Regressione: proiezione dell'occorrenza attesa NON rappresentabile come `date`.

`Signal.data` arriva dal client. Con una data vicina a `date.max`/`date.min`
o una cadenza degenere, `ultima_occorrenza + k*cadenza` puo' uscire
dall'intervallo di `date` (o `delta / cadenza` esplodere a `inf`): prima del
fix questo sollevava `OverflowError` fuori dal try del BFF -> 500 provocabile
da un client. Ora e' FAIL-CLOSED: l'evento e' fuori finestra, nessuna
eccezione, nessuna data inventata (nessun clamp a `date.max`).

Date FISSE ovunque (mai `date.today()`).
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    Signal,
    VisitorContext,
)
from experience_engine import compose_itinerary, rules
from graph.seed_lucca import VOCABOLARIO
from pydantic import ValidationError
from rag.reasons import compose_reason

ULTIMA = date(2026, 3, 2)

#: Ultima occorrenza 28 giorni prima di `date.max`, cadenza 30: in aritmetica
#: float la visita a `date.max` dista 2 giorni dall'occorrenza attesa (k=1),
#: dentro la finestra (+-4,5) — ma l'occorrenza cade a `date.max + 2`, non
#: rappresentabile. E' il caso che prima faceva comparire l'evento e poi
#: esplodere nel `reason`.
ULTIMA_A_FINE_CALENDARIO = date.max - timedelta(days=28)


def _evento(
    cadenza: float, ultima: date = ULTIMA, *, id_: str = "evento-luogo-fisso-musica"
) -> EventoPromosso:
    return EventoPromosso(
        id=id_,
        place_id="luogo-fisso",
        temi=["musica"],
        ultima_occorrenza=ultima,
        cadenza_giorni=cadenza,
    )


def _profilo() -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.1,
        contemplazione=0.1,
        arte=0.9,
        con_bambini=False,
        tempo_disponibile_min=200,
    )


def _candidato() -> GraphCandidate:
    esperienza = ExperienceNode(
        id="exp-fisso",
        titolo="Facciata Barocca",
        place_id="luogo-fisso",
        temi=["arte"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Piazza Fissa", connessioni=['Evoca il tema "Arte".']
    )


def _compose(eventi: list[EventoPromosso], data: date | None) -> Itinerary:
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=data)
    ctx = VisitorContext(person_id="p", profile=_profilo(), signal=signal)
    return compose_itinerary(
        ctx, [_candidato()], compose_reason, eventi_promossi=eventi, vocabolario=VOCABOLARIO,
    )


# (cadenza, ultima_occorrenza, data_visita) — tutti con proiezione NON
# rappresentabile come `date`.
CASI_NON_RAPPRESENTABILI = [
    pytest.param(30.0, ULTIMA_A_FINE_CALENDARIO, date.max, id="date.max-float-in-finestra"),
    pytest.param(7.0, ULTIMA, date.max, id="date.max"),
    pytest.param(7.0, date.max, date.min, id="date.min-ultima-a-date.max"),
    pytest.param(1e300, ULTIMA, ULTIMA, id="cadenza-enorme"),
    pytest.param(float("inf"), ULTIMA, ULTIMA, id="cadenza-infinita"),  # solo funzioni pure
    pytest.param(5e-324, ULTIMA, date.max, id="cadenza-minima-rapporto-inf"),
]


@pytest.mark.parametrize(("cadenza", "ultima", "visita"), CASI_NON_RAPPRESENTABILI)
def test_proiezione_non_rappresentabile_e_none(cadenza: float, ultima: date, visita: date) -> None:
    assert rules.proiezione_occorrenza_attesa(ultima, cadenza, visita) is None


# Il contratto (`cadenza_giorni`: gt=0, allow_inf_nan=False) rifiuta inf/nan:
# un `EventoPromosso` con cadenza infinita NON e' costruibile. I test che
# costruiscono l'evento usano quindi solo i casi rappresentabili nel contratto.
CASI_COSTRUIBILI = [p for p in CASI_NON_RAPPRESENTABILI if p.id != "cadenza-infinita"]


@pytest.mark.parametrize("cadenza", [float("inf"), float("-inf"), float("nan")])
def test_contratto_rifiuta_cadenza_non_finita(cadenza: float) -> None:
    with pytest.raises(ValidationError):
        _evento(cadenza)


def test_difesa_del_motore_con_cadenza_infinita_resta_fail_closed() -> None:
    # Difesa in profondita': anche chiamando direttamente le funzioni pure
    # (aggirando il contratto) inf non solleva e l'evento e' fuori finestra.
    inf = float("inf")
    assert rules.proiezione_occorrenza_attesa(ULTIMA, inf, ULTIMA) is None
    assert rules.evento_in_finestra(ULTIMA, inf, ULTIMA) is False


@pytest.mark.parametrize(("cadenza", "ultima", "visita"), CASI_COSTRUIBILI)
def test_fuori_finestra_e_nessun_evento(cadenza: float, ultima: date, visita: date) -> None:
    evento = _evento(cadenza, ultima)
    assert rules.evento_in_finestra(ultima, cadenza, visita) is False
    assert rules.eventi_promossi_pertinenti(
        [evento], _profilo(), visita, vocabolario=VOCABOLARIO,
    ) == []


@pytest.mark.parametrize(("cadenza", "ultima", "visita"), CASI_COSTRUIBILI)
def test_compose_itinerary_non_solleva(cadenza: float, ultima: date, visita: date) -> None:
    it = _compose([_evento(cadenza, ultima)], visita)
    assert [s.experience_id for s in it.stops] == ["exp-fisso"]
    assert all(s.reason.strip() for s in it.stops)


def test_date_min_con_ultima_normale_nessun_evento_nessuna_eccezione() -> None:
    # Proiezione rappresentabile (k=1), ma la visita e' lontanissima: fuori.
    assert rules.evento_in_finestra(ULTIMA, 7.0, date.min) is False
    it = _compose([_evento(7.0)], date.min)
    assert [s.experience_id for s in it.stops] == ["exp-fisso"]


def test_giorno_occorrenza_attesa_non_inventa_date() -> None:
    # Fuori dalla precondizione (evento in finestra) non restituisce mai un
    # clamp a `date.max`: errore esplicito.
    with pytest.raises(ValueError):
        rules.giorno_occorrenza_attesa(ULTIMA_A_FINE_CALENDARIO, 30.0, date.max)


def test_vicino_a_date_max_ma_rappresentabile_resta_in_finestra() -> None:
    # Controllo che il fix non sia un "fuori tutto vicino al bordo": se
    # l'occorrenza attesa cade esattamente a `date.max`, l'evento compare.
    ultima = date.max - timedelta(days=30)
    assert rules.proiezione_occorrenza_attesa(ultima, 30.0, date.max) == date.max
    assert rules.evento_in_finestra(ultima, 30.0, date.max) is True
    it = _compose([_evento(30.0, ultima)], date.max)
    assert [s.experience_id for s in it.stops] == ["exp-fisso", "evento-luogo-fisso-musica"]
