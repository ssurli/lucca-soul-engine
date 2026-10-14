"""`Signal.giorno_settimana` DERIVATO da `Signal.data` - test comportamentali.

Cambio di contratto: se il client manda solo `data`, `Signal` ricava
`giorno_settimana = data.weekday()`. Effetto: il filtro duro 5 sugli orari di
apertura (`rientra_in_orario`) si accende anche per un client che manda solo
`data` (l'app Flutter), sia in composizione (`passa_filtri_duri`) sia in
adattamento (`_migliore_alternativa`).

PRIMA del cambio, con SOLO `data`, `giorno_settimana` restava `None` e
`rientra_in_orario` non escludeva nulla: l'esperienza aperta solo il lunedi
sarebbe stata INCLUSA anche in un martedi. Questi test fissano il nuovo
comportamento (esclusa di martedi) e gli invarianti (nessun dato -> nessuna
esclusione; la finestra eventi non dipende dal giorno).

Date FISSE (mai date.today()): 2026-03-02 e' un lunedi, 2026-03-03 un martedi.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, time

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    FasciaApertura,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary, rules
from rag.reasons import adapt_reason, compose_reason

LUNEDI = date(2026, 3, 2)
MARTEDI = date(2026, 3, 3)
ORA = time(10, 0)  # dentro la fascia 09:00-13:00


def _profilo(tempo: int = 200) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=tempo,
    )


def _solo_lunedi(id_: str = "exp-solo-lunedi", al_chiuso: bool = True) -> GraphCandidate:
    esperienza = ExperienceNode(
        id=id_, titolo="Museo del Lunedi", place_id=f"luogo-{id_}", temi=["arte"],
        durata_min=30, al_chiuso=al_chiuso, accessibile=True,
        orari_apertura=[
            FasciaApertura(giorno_settimana=0, apertura=time(9, 0), chiusura=time(13, 0))
        ],
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Museo", connessioni=['Evoca il tema "Arte".']
    )


def _ids(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops]


def _compose(signal: Signal, candidati: list[GraphCandidate]) -> Itinerary:
    ctx = VisitorContext(person_id="p", profile=_profilo(), signal=signal)
    return compose_itinerary(ctx, candidati, compose_reason)


def _signal(**kw) -> Signal:
    base = dict(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA)
    base.update(kw)
    return Signal(**base)


# --- il contratto deriva il giorno ------------------------------------------


def test_signal_con_solo_data_ricava_giorno_settimana() -> None:
    assert _signal(data=LUNEDI).giorno_settimana == 0
    assert _signal(data=MARTEDI).giorno_settimana == 1


def test_signal_incoerente_data_giorno_resta_errore() -> None:
    with pytest.raises(ValueError):
        _signal(data=LUNEDI, giorno_settimana=3)


# --- 1. compose_itinerary ----------------------------------------------------


def test_compose_solo_data_martedi_esclude_esperienza_aperta_solo_il_lunedi() -> None:
    """Con SOLO `data` = martedi e ora dentro la fascia del lunedi, l'esperienza
    e' esclusa. Prima del cambio (giorno None) sarebbe stata INCLUSA."""
    it = _compose(_signal(data=MARTEDI), [_solo_lunedi()])
    assert "exp-solo-lunedi" not in _ids(it)


def test_compose_solo_data_lunedi_include_esperienza_aperta_il_lunedi() -> None:
    it = _compose(_signal(data=LUNEDI), [_solo_lunedi()])
    assert "exp-solo-lunedi" in _ids(it)


def test_compose_solo_data_equivale_a_giorno_esplicito() -> None:
    c = [_solo_lunedi()]
    assert _ids(_compose(_signal(data=MARTEDI), c)) == _ids(
        _compose(_signal(data=MARTEDI, giorno_settimana=1), c)
    )
    assert _ids(_compose(_signal(data=LUNEDI), c)) == _ids(
        _compose(_signal(data=LUNEDI, giorno_settimana=0), c)
    )


# --- 2. nessun dato -> nessuna esclusione (invariato) -----------------------


def test_compose_senza_data_ne_giorno_non_esclude_per_giorno() -> None:
    signal = _signal()
    assert signal.giorno_settimana is None and signal.data is None
    assert "exp-solo-lunedi" in _ids(_compose(signal, [_solo_lunedi()]))


# --- 3. adapt_itinerary ------------------------------------------------------


def _adatta_pioggia(data: date) -> Itinerary:
    originale = ExperienceNode(
        id="exp-originale", titolo="Passeggiata", place_id="luogo-a", temi=[],
        durata_min=30, al_chiuso=False, accessibile=True,
    )
    candidati = [
        GraphCandidate(experience=originale, place_nome="A", connessioni=[]),
        _solo_lunedi(id_="exp-alt-lunedi", al_chiuso=True),
    ]
    itinerario = Itinerary(
        person_id="p",
        stops=[ItineraryStop(experience_id="exp-originale", arrivo=ORA, durata_min=30,
                             reason="motivo iniziale")],
        generated_at=datetime(2026, 3, 1, 9, 0),
    )
    return adapt_itinerary(
        itinerario, _signal(meteo="pioggia", data=data), candidati, _profilo(),
        reason_fn=compose_reason, adapt_reason_fn=adapt_reason,
    )


def test_adapt_alternativa_chiusa_nel_giorno_ricavato_da_data_non_e_usata() -> None:
    """Pioggia di martedi (solo `data`): l'unica alternativa al chiuso e' aperta
    solo il lunedi -> nessuna sostituzione, tappa originale intatta. Prima del
    cambio sarebbe stata sostituita."""
    risultato = _adatta_pioggia(MARTEDI)
    assert _ids(risultato) == ["exp-originale"]
    assert risultato.adattato_da_segnale is False


def test_adapt_alternativa_aperta_nel_giorno_ricavato_da_data_e_usata() -> None:
    risultato = _adatta_pioggia(LUNEDI)
    assert _ids(risultato) == ["exp-alt-lunedi"]
    assert risultato.adattato_da_segnale is True


# --- 5. nessuna interazione con la finestra eventi --------------------------


def test_finestra_eventi_non_dipende_da_giorno_settimana() -> None:
    """La finestra usa `data`, non `giorno_settimana`: la firma di
    `evento_in_finestra` non ha alcun parametro giorno, e un evento in finestra
    compare identico che il giorno sia ricavato o esplicito."""
    assert "giorno" not in " ".join(inspect.signature(rules.evento_in_finestra).parameters)

    # ultima occorrenza lunedi 2026-03-02, cadenza 1 giorno -> martedi in finestra.
    evento = EventoPromosso(
        id="evento-luogo-evt-musica", place_id="luogo-evt", temi=["musica"],
        ultima_occorrenza=LUNEDI, cadenza_giorni=1.0,
    )
    base = ExperienceNode(
        id="exp-aperta-sempre", titolo="Facciata", place_id="luogo-evt", temi=["arte"],
        durata_min=30, al_chiuso=False, accessibile=True,
    )
    c = [
        GraphCandidate(
            experience=base, place_nome="Piazza", connessioni=['Evoca il tema "Arte".']
        )
    ]

    def _con(signal: Signal) -> list[str]:
        ctx = VisitorContext(person_id="p", profile=_profilo(), signal=signal)
        return _ids(compose_itinerary(ctx, c, compose_reason, eventi_promossi=[evento]))

    derivato = _con(_signal(data=MARTEDI))
    esplicito = _con(_signal(data=MARTEDI, giorno_settimana=1))
    assert derivato == esplicito
    assert evento.id in derivato
    # senza data l'evento resta fail-closed, a prescindere dal giorno
    assert evento.id not in _con(_signal(giorno_settimana=1))
