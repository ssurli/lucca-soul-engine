"""`ExperienceNode.sospesa`: interruttore di PRESENZA, primo dei filtri duri statici.

Un'esperienza sospesa (chiusura stagionale, restauro) esiste nel grafo ma non
si propone MAI: ne' in composizione ne' come sostituto in adattamento,
qualunque cosa dicano orari, score o tema. Vale per ogni candidato, a
prescindere da `orari_apertura` (che dicono QUANDO e' aperta nella settimana,
non SE lo e' in questo periodo).

Scelta del committente (documentata in `docs/LIMITI.md`): le tappe MANTENUTE da
`adapt_itinerary` NON ripassano i filtri statici; il test dedicato la fissa.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    FasciaApertura,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
    VocabolarioTemi,
)
from experience_engine import adapt_itinerary, compose_itinerary
from experience_engine.rules import passa_filtri_duri, passa_filtri_statici
from rag.reasons import adapt_reason, compose_reason

LUNEDI = date(2026, 6, 15)

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)

TUTTO_IL_GIORNO = [
    FasciaApertura(giorno_settimana=0, apertura=time(0, 0), chiusura=time(23, 59))
]


def _cand(
    id_: str,
    *,
    sospesa: bool = False,
    orari: list[FasciaApertura] | None = None,
    al_chiuso: bool = True,
    temi: tuple[str, ...] = ("arte",),
    durata: int = 30,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=f"luogo-{id_}", temi=list(temi),
            durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
            orari_apertura=orari or [], sospesa=sospesa,
        ),
        place_nome=f"Luogo {id_}",
        connessioni=['Evoca il tema "Arte".'],
        distanza_m=0,
    )


def _profilo(tempo: int = 200) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=tempo,
    )


def _segnale(
    *,
    meteo: Literal["sereno", "pioggia"] = "sereno",
    affollamento: dict[str, float] | None = None,
    data: date | None = None,
) -> Signal:
    return Signal(
        meteo=meteo, affollamento=affollamento or {}, stanchezza=0.0,
        ora=time(10, 0), data=data,
    )


def _ids(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops]


# ===========================================================================
# 1. Filtri duri
# ===========================================================================


@pytest.mark.parametrize("sospesa", [False, True])
def test_filtri_statici_e_duri_rifiutano_la_sospesa(sospesa: bool) -> None:
    c = _cand("x", sospesa=sospesa)
    atteso = not sospesa
    assert passa_filtri_statici(c, _profilo(), _segnale(), []) is atteso
    assert passa_filtri_duri(c, _profilo(), _segnale(), [], arrivo=time(10, 0)) is atteso


def test_sospesa_rifiutata_anche_con_orari_che_la_darebbero_aperta() -> None:
    c = _cand("x", sospesa=True, orari=TUTTO_IL_GIORNO)
    sig = _segnale(data=LUNEDI)
    assert passa_filtri_duri(
        c.model_copy(update={"experience": c.experience.model_copy(update={"sospesa": False})}),
        _profilo(), sig, [], arrivo=time(10, 0),
    )
    assert not passa_filtri_statici(c, _profilo(), sig, [])
    assert not passa_filtri_duri(c, _profilo(), sig, [], arrivo=time(10, 0))


# ===========================================================================
# 2. Composizione
# ===========================================================================


@pytest.mark.parametrize("orari", [None, TUTTO_IL_GIORNO], ids=["orari-vuoti", "orari-aperta"])
def test_compose_non_include_mai_la_sospesa_anche_se_top(
    orari: list[FasciaApertura] | None,
) -> None:
    top = _cand("top", sospesa=True, orari=orari)
    altre = [_cand("b", temi=("verde",)), _cand("c", temi=("musica",))]
    punti = {"top": 0.99, "b": 0.5, "c": 0.4}
    ctx = VisitorContext(person_id="p", profile=_profilo(), signal=_segnale(data=LUNEDI))

    controllo = compose_itinerary(
        ctx, [top.model_copy(update={"experience": top.experience.model_copy(
            update={"sospesa": False})}), *altre],
        compose_reason, score_fn=lambda c, _p, _s: punti[c.experience.id], vocabolario=VOC,
    )
    assert _ids(controllo)[0] == "top"  # senza sospensione sarebbe la prima

    it = compose_itinerary(
        ctx, [top, *altre], compose_reason,
        score_fn=lambda c, _p, _s: punti[c.experience.id], vocabolario=VOC,
    )
    assert "top" not in _ids(it)
    assert _ids(it) == ["b", "c"]


# ===========================================================================
# 3-4. Adattamento
# ===========================================================================


def _tappa(id_: str, arrivo: str, durata: int = 30) -> ItineraryStop:
    h, m = arrivo.split(":")
    return ItineraryStop(
        experience_id=id_, arrivo=time(int(h), int(m)), durata_min=durata,
        reason=f"Motivo di {id_}.",
    )


def _itin(stops: list[ItineraryStop]) -> Itinerary:
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 6, 15, 9, 0),
        tempo_disponibile_min=600, tempo_effettivo_min=600,
    )


def _adatta(it: Itinerary, signal: Signal, cands: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(it, signal, cands, None, compose_reason, adapt_reason, vocabolario=VOC)


@pytest.mark.parametrize("sospesa", [False, True])
def test_adapt_pioggia_il_sostituto_ideale_sospeso_non_e_scelto(sospesa: bool) -> None:
    t = _cand("t", al_chiuso=False, temi=("arte",))
    ideale = _cand("a-ideale", sospesa=sospesa, al_chiuso=True, temi=("arte",))
    altro = _cand("z-altro", al_chiuso=True, temi=("verde",))
    out = _adatta(_itin([_tappa("t", "10:00")]), _segnale(meteo="pioggia"), [t, ideale, altro])
    assert _ids(out) == (["z-altro"] if sospesa else ["a-ideale"])


def test_adapt_pioggia_senza_altri_sostituti_la_sospesa_non_entra() -> None:
    t = _cand("t", al_chiuso=False)
    sospesa = _cand("s", sospesa=True, orari=TUTTO_IL_GIORNO)
    out = _adatta(
        _itin([_tappa("t", "10:00")]), _segnale(meteo="pioggia", data=LUNEDI), [t, sospesa]
    )
    assert _ids(out) == ["t"]
    assert out.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


@pytest.mark.parametrize("sospesa", [False, True])
def test_adapt_affollamento_il_sostituto_ideale_sospeso_non_e_scelto(sospesa: bool) -> None:
    t = _cand("t", temi=("arte",))
    ideale = _cand("a-ideale", sospesa=sospesa, temi=("arte",))
    altro = _cand("z-altro", temi=("verde",))
    sig = _segnale(affollamento={"luogo-t": 0.75})
    out = _adatta(_itin([_tappa("t", "10:00")]), sig, [t, ideale, altro])
    assert _ids(out) == (["z-altro"] if sospesa else ["a-ideale"])


def test_adapt_tappa_mantenuta_gia_sospesa_resta_scelta_del_committente() -> None:
    """NON e' un bug: le tappe mantenute non ripassano i filtri statici
    (docs/LIMITI.md). Un itinerario con x, poi sospesa, adattato per un segnale
    che non tocca x (pioggia, x al chiuso) la conserva; il sostituto di t sceglie
    invece fra le non sospese."""
    x = _cand("x", sospesa=True, al_chiuso=True, temi=("silenzio",))
    t = _cand("t", al_chiuso=False)
    s = _cand("s", temi=("verde",))
    out = _adatta(
        _itin([_tappa("x", "10:00"), _tappa("t", "10:30")]), _segnale(meteo="pioggia"),
        [x, t, s],
    )
    assert _ids(out) == ["x", "s"]
    assert out.stops[0].esito_adattamento is EsitoAdattamento.NON_TOCCATA
