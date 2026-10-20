"""`ExperienceNode.sospesa`: interruttore di PRESENZA, primo dei filtri duri statici.

Un'esperienza sospesa (chiusura stagionale, restauro) esiste nel grafo ma non
si propone MAI: ne' in composizione ne' come sostituto in adattamento,
qualunque cosa dicano orari, score o tema. Vale per ogni candidato, a
prescindere da `orari_apertura` (che dicono QUANDO e' aperta nella settimana,
non SE lo e' in questo periodo).

Ondata 1b-2 (cambio voluto del committente): le tappe MANTENUTE da
`adapt_itinerary` ripassano la sospensione al passo 4; una tappa sospesa esce
in `tappe_escluse` con `TAGLIATA_SOSPESA` (gli altri filtri statici no).
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
    TappaEsclusa,
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


FRASE_SOSPESA = "Tolta: in questo periodo il luogo è chiuso."
FUORI_ORARIO = [FasciaApertura(giorno_settimana=0, apertura=time(6, 0), chiusura=time(7, 0))]


def _esclusa(out: Itinerary, id_: str) -> list[TappaEsclusa]:
    return [t for t in out.tappe_escluse if t.experience_id == id_]


def test_adapt_tappa_mantenuta_sospesa_esce_con_tagliata_sospesa() -> None:
    """Riscritto (era `..._resta_scelta_del_committente`): il vecchio test
    fissava che una tappa mantenuta, poi sospesa, restasse NON_TOCCATA. Il
    committente ha cambiato apposta il comportamento (ondata 1b-2): ora esce."""
    x = _cand("x", sospesa=True, al_chiuso=True, temi=("silenzio",))
    t = _cand("t", al_chiuso=False)
    s = _cand("s", temi=("verde",))
    out = _adatta(
        _itin([_tappa("x", "10:00"), _tappa("t", "10:30")]), _segnale(meteo="pioggia"),
        [x, t, s],
    )
    assert _ids(out) == ["s"]
    (e,) = _esclusa(out, "x")
    assert e.esito is EsitoAdattamento.TAGLIATA_SOSPESA
    assert e.reason == FRASE_SOSPESA
    assert out.adattato_da_segnale is True


def test_adapt_sospesa_con_segnale_neutro_esce_e_accende_adattato() -> None:
    x = _cand("x", sospesa=True)
    y = _cand("y", temi=("verde",))
    out = _adatta(_itin([_tappa("x", "10:00"), _tappa("y", "10:30")]), _segnale(), [x, y])
    assert _ids(out) == ["y"]
    (e,) = _esclusa(out, "x")
    assert (e.esito, e.reason) == (EsitoAdattamento.TAGLIATA_SOSPESA, FRASE_SOSPESA)
    assert out.adattato_da_segnale is True


def test_adapt_sospesa_e_fuori_orario_esce_come_sospesa() -> None:
    x = _cand("x", sospesa=True, orari=FUORI_ORARIO)
    y = _cand("y", temi=("verde",))
    out = _adatta(
        _itin([_tappa("x", "10:00"), _tappa("y", "10:30")]), _segnale(data=LUNEDI), [x, y]
    )
    (e,) = _esclusa(out, "x")
    assert e.esito is EsitoAdattamento.TAGLIATA_SOSPESA
    assert all(t.esito is not EsitoAdattamento.TAGLIATA_ORARIO for t in out.tappe_escluse)


def test_adapt_fuori_orario_non_sospesa_resta_tagliata_orario() -> None:
    """Controllo: l'esito per orario non e' stato rimpiazzato."""
    x = _cand("x", orari=FUORI_ORARIO)
    y = _cand("y", temi=("verde",))
    out = _adatta(
        _itin([_tappa("x", "10:00"), _tappa("y", "10:30")]), _segnale(data=LUNEDI), [x, y]
    )
    (e,) = _esclusa(out, "x")
    assert e.esito is EsitoAdattamento.TAGLIATA_ORARIO


def test_adapt_stub_senza_candidato_non_esce_mai() -> None:
    """Una tappa senza candidato (esperienza non piu' tra i candidati) e' uno
    stub: non ha `sospesa` e non esce a questo passo."""
    x = _cand("x", sospesa=True)
    out = _adatta(_itin([_tappa("fantasma", "10:00"), _tappa("x", "10:30")]), _segnale(), [x])
    assert _ids(out) == ["fantasma"]
    assert _esclusa(out, "fantasma") == []
    assert [t.experience_id for t in out.tappe_escluse] == ["x"]


def test_adapt_solo_stub_non_cambia_nulla() -> None:
    out = _adatta(_itin([_tappa("fantasma", "10:00")]), _segnale(), [])
    assert _ids(out) == ["fantasma"]
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False


def test_adapt_sospesa_ricevuta_con_reason_alterato_torna_canonica() -> None:
    y = _cand("y", temi=("verde",))
    it = _itin([_tappa("y", "10:00")]).model_copy(update={"tappe_escluse": [
        TappaEsclusa(
            experience_id="vecchia", esito=EsitoAdattamento.TAGLIATA_SOSPESA,
            reason="testo manomesso dal client",
        )
    ]})
    out = _adatta(it, _segnale(), [y])
    (e,) = _esclusa(out, "vecchia")
    assert e.esito is EsitoAdattamento.TAGLIATA_SOSPESA
    assert e.reason == FRASE_SOSPESA


def test_adapt_senza_sospese_identico_a_prima() -> None:
    a = _cand("a")
    b = _cand("b", temi=("verde",))
    it = _itin([_tappa("a", "10:00"), _tappa("b", "10:30")])
    out = _adatta(it, _segnale(), [a, b])
    assert _ids(out) == ["a", "b"]
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False
    assert [s.arrivo for s in out.stops] == [s.arrivo for s in it.stops]
    assert all(s.esito_adattamento is EsitoAdattamento.NON_TOCCATA for s in out.stops)


def test_adapt_dopo_sospesa_gli_arrivi_non_avanzano_e_restano_nel_tetto() -> None:
    cands = [
        _cand("a", durata=60), _cand("x", sospesa=True, durata=60),
        _cand("b", temi=("verde",), durata=60), _cand("c", temi=("musica",), durata=60),
    ]
    it = _itin([
        _tappa("a", "21:00", 60), _tappa("x", "22:00", 60),
        _tappa("b", "23:00", 60), _tappa("c", "23:30", 60),
    ])
    sig = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(21, 0))
    out = _adatta(it, sig, cands)
    assert "x" not in _ids(out)
    assert _esclusa(out, "x")[0].esito is EsitoAdattamento.TAGLIATA_SOSPESA
    ricevuti = {s.experience_id: s.arrivo for s in it.stops}
    for s in out.stops:
        assert s.arrivo <= ricevuti[s.experience_id]  # mai in avanti
        assert s.arrivo.hour * 60 + s.arrivo.minute + s.durata_min <= 24 * 60
    # b, subito dopo a, parte alla fine di a: anticipata, non spostata in avanti.
    assert {s.experience_id: s.arrivo for s in out.stops}["b"] == time(22, 0)
