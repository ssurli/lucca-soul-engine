"""Il vocabolario attraversa il motore END-TO-END.

Stesso input (candidati, profilo, segnale), due vocabolari INVENTATI nel test
che invertono quale tema e' "arte" e quale "contemplativo": l'ordine delle
tappe di `compose_itinerary` (score_fn di default) e la scelta
dell'alternativa in `adapt_itinerary` (`_migliore_alternativa`) devono
cambiare. Se il parametro non fosse inoltrato fino in fondo, o il motore
leggesse un vocabolario cablato, l'ordine sarebbe lo stesso.
"""

from __future__ import annotations

from datetime import time
from typing import Literal

from contracts import (
    EmotionalProfile,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    Signal,
    VisitorContext,
    VocabolarioTemi,
)
from experience_engine import adapt_itinerary, compose_itinerary

_VOC_A = VocabolarioTemi(
    contemplativi=frozenset({"tema-x"}),
    arte=frozenset({"tema-y"}),
    insoliti=frozenset(),
    verde=frozenset(),
    bambini="piccoli-inventati",
)
#: Stessi temi, ruoli scambiati.
_VOC_B = VocabolarioTemi(
    contemplativi=frozenset({"tema-y"}),
    arte=frozenset({"tema-x"}),
    insoliti=frozenset(),
    verde=frozenset(),
    bambini="piccoli-inventati",
)


def _cand(id_: str, place: str, temi: list[str], *, al_chiuso: bool = True) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Esperienza {id_}", place_id=place, temi=temi,
            durata_min=40, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Luogo {place}",
        connessioni=[],
    )


def _segnale(meteo: Literal["sereno", "pioggia", "caldo"] = "sereno") -> Signal:
    return Signal(meteo=meteo, affollamento={}, stanchezza=0.0, ora=time(10, 0))


def _ctx(profile: EmotionalProfile, signal: Signal) -> VisitorContext:
    return VisitorContext(person_id="visitatore-test", profile=profile, signal=signal)


def _ordine(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops]


def test_compose_ordine_diverso_con_vocabolari_diversi() -> None:
    # Due temi uguali per candidato -> affinita' piena (1.0) sul gruppo giusto.
    # Profilo: contemplazione molto piu' forte dell'arte (W_* a parte, il
    # vincitore e' quello i cui temi cadono nel gruppo contemplativi).
    candidati = [
        _cand("exp-x", "luogo-1", ["tema-x", "tema-x"]),
        _cand("exp-y", "luogo-2", ["tema-y", "tema-y"]),
    ]
    profilo = EmotionalProfile(
        curiosita=0.0, contemplazione=1.0, arte=0.0, con_bambini=False,
        tempo_disponibile_min=40,
    )
    ctx = _ctx(profilo, _segnale())

    con_a = compose_itinerary(ctx, candidati, vocabolario=_VOC_A)
    con_b = compose_itinerary(ctx, candidati, vocabolario=_VOC_B)

    assert _ordine(con_a) == ["exp-x"]
    assert _ordine(con_b) == ["exp-y"]


def test_compose_budget_largo_ordine_invertito() -> None:
    candidati = [
        _cand("exp-x", "luogo-1", ["tema-x", "tema-x"]),
        _cand("exp-y", "luogo-2", ["tema-y", "tema-y"]),
    ]
    profilo = EmotionalProfile(
        curiosita=0.0, contemplazione=1.0, arte=0.0, con_bambini=False,
        tempo_disponibile_min=240,
    )
    ctx = _ctx(profilo, _segnale())
    ordine_a = _ordine(compose_itinerary(ctx, candidati, vocabolario=_VOC_A))
    ordine_b = _ordine(compose_itinerary(ctx, candidati, vocabolario=_VOC_B))
    assert sorted(ordine_a) == sorted(ordine_b) == ["exp-x", "exp-y"]
    assert ordine_a[0] == "exp-x"
    assert ordine_b[0] == "exp-y"


def test_adapt_alternativa_segue_il_vocabolario() -> None:
    """Pioggia: la tappa all'aperto e' sostituita dalla migliore alternativa
    al chiuso; QUALE sia dipende dal vocabolario (`_migliore_alternativa`)."""
    aperto = _cand("exp-aperto", "luogo-0", ["tema-z"], al_chiuso=False)
    alt_x = _cand("exp-x", "luogo-1", ["tema-x", "tema-x"])
    alt_y = _cand("exp-y", "luogo-2", ["tema-y", "tema-y"])
    candidati = [aperto, alt_x, alt_y]
    profilo = EmotionalProfile(
        curiosita=0.0, contemplazione=1.0, arte=0.0, con_bambini=False,
        tempo_disponibile_min=40,
    )

    # Itinerario di partenza identico per entrambi: una sola tappa all'aperto.
    base = compose_itinerary(
        _ctx(profilo, _segnale()), [aperto], vocabolario=_VOC_A
    )
    assert _ordine(base) == ["exp-aperto"]

    pioggia = _segnale("pioggia")
    adattato_a = adapt_itinerary(base, pioggia, candidati, profilo, vocabolario=_VOC_A)
    adattato_b = adapt_itinerary(base, pioggia, candidati, profilo, vocabolario=_VOC_B)

    assert adattato_a.adattato_da_segnale and adattato_b.adattato_da_segnale
    assert _ordine(adattato_a) == ["exp-x"]
    assert _ordine(adattato_b) == ["exp-y"]
