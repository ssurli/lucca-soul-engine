"""Orari di apertura valutati all'ARRIVO della tappa (filtro duro 6).

Il filtro non guarda piu' `signal.ora` ma l'istante in cui il visitatore
ARRIVA alla tappa, e l'intero intervallo [arrivo, arrivo + durata] deve cadere
in una fascia del giorno. Solo API pubbliche: `compose_itinerary` e
`adapt_itinerary`. Esperienze costruite qui con `orari_apertura` espliciti;
lunedi' 2026-06-15 (`LUNEDI`) rende noto il giorno. `distanza_m=0` azzera i
trasferimenti, cosi' gli arrivi sono somme di durate.

Quattro gruppi:
1. composizione: la tappa chiusa in uno slot salta, resta tra i rimanenti e
   puo' entrare in uno slot successivo (anche nel ramo della diversificazione);
2. adattamento, sostituzioni: il sostituto e' valutato all'arrivo che avra'
   in posizione i (ricalcolato), non a `signal.ora`;
3. adattamento, taglio `TAGLIATA_ORARIO` (passo 4), timeline e cascata;
4. non regressione: senza `data` o senza orari il motore non filtra nulla
   (questi test passano IDENTICI col motore di prima).
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
    rientra_in_orario,
)
from experience_engine import adapt_itinerary, compose_itinerary
from graph.seed_lucca import VOCABOLARIO as VOCABOLARIO_LUCCA
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

LUNEDI = date(2026, 6, 15)  # weekday() == 0
MARTEDI = date(2026, 6, 16)

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)

FRASE_ORARIO = (
    "Tolta: all'ora in cui ci arriveresti il luogo è chiuso, "
    "o chiude prima della fine della visita."
)


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _orari(*fasce: tuple[str, str], giorno: int = 0) -> list[FasciaApertura]:
    return [
        FasciaApertura(giorno_settimana=giorno, apertura=_t(a), chiusura=_t(c))
        for a, c in fasce
    ]


def _cand(
    id_: str,
    *,
    durata: int = 30,
    orari: list[FasciaApertura] | None = None,
    al_chiuso: bool = True,
    temi: tuple[str, ...] = ("arte",),
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=f"luogo-{id_}", temi=list(temi),
            durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
            orari_apertura=orari or [],
        ),
        place_nome=f"Luogo {id_}",
        connessioni=['Evoca il tema "Arte".'],
        distanza_m=0,
    )


def _senza_orari(cands: list[GraphCandidate]) -> list[GraphCandidate]:
    return [
        c.model_copy(update={"experience": c.experience.model_copy(update={"orari_apertura": []})})
        for c in cands
    ]


def _segnale(
    ora: str,
    *,
    data: date | None = LUNEDI,
    meteo: Literal["sereno", "pioggia"] = "sereno",
    stanchezza: float = 0.0,
) -> Signal:
    return Signal(
        meteo=meteo, affollamento={}, stanchezza=stanchezza, ora=_t(ora), data=data,
    )


def _profilo(tempo: int = 200) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=tempo,
    )


def _componi(
    cands: list[GraphCandidate],
    punti: dict[str, float],
    ora: str,
    *,
    tempo: int = 200,
    data: date | None = LUNEDI,
) -> Itinerary:
    """Composizione con ordine per score CONTROLLATO (`score_fn` iniettata)."""
    ctx = VisitorContext(person_id="p", profile=_profilo(tempo), signal=_segnale(ora, data=data))
    return compose_itinerary(
        ctx, cands, compose_reason,
        score_fn=lambda c, _p, _s: punti[c.experience.id],
        vocabolario=VOC,
    )


def _ids(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops]


def _arrivi(it: Itinerary) -> dict[str, time]:
    return {s.experience_id: s.arrivo for s in it.stops}


# ===========================================================================
# 1. Composizione
# ===========================================================================


@pytest.mark.parametrize(
    ("durata_b", "entra"),
    [(10, True), (11, False), (40, False)],
    ids=["finisce-alle-12-esatte", "un-minuto-oltre", "arrivo-11-50-fine-12-30"],
)
def test_compose_non_entra_se_finirebbe_oltre_la_chiusura(durata_b: int, entra: bool) -> None:
    """B aperta solo 09:00-12:00. A (30 min) occupa 11:20-11:50, quindi B
    ARRIVA alle 11:50. A 11:50 con durata 40 finirebbe alle 12:30."""
    a = _cand("a", temi=("arte",))
    b = _cand("b", durata=durata_b, orari=_orari(("09:00", "12:00")), temi=("verde",))
    it = _componi([a, b], {"a": 0.9, "b": 0.8}, "11:20")
    if entra:
        assert _ids(it) == ["a", "b"]
        assert _arrivi(it)["b"] == time(11, 50)
    else:
        assert "b" not in _ids(it), f"B chiusa all'arrivo (11:50) ma presente: {_arrivi(it)}"
        assert _ids(it) == ["a"]


def test_compose_fascia_pomeridiana_entra_se_arriva_dopo_apertura() -> None:
    """B aperta 15:00-17:00. Composizione alle 14:30 con A di 30 minuti: B
    arriva alle 15:00. Controllata all'ora del segnale (14:30) sarebbe chiusa."""
    a = _cand("a", temi=("arte",))
    b = _cand("b", orari=_orari(("15:00", "17:00")), temi=("verde",))
    it = _componi([a, b], {"a": 0.9, "b": 0.8}, "14:30")
    assert _ids(it) == ["a", "b"]
    assert _arrivi(it)["b"] == time(15, 0)


def test_compose_fascia_pomeridiana_budget_insufficiente_resta_fuori() -> None:
    """Il budget resta un vincolo a parte: aperta ma non ci sta -> fuori."""
    a = _cand("a", temi=("arte",))
    b = _cand("b", orari=_orari(("15:00", "17:00")), temi=("verde",))
    it = _componi([a, b], {"a": 0.9, "b": 0.8}, "14:30", tempo=50)
    assert _ids(it) == ["a"]


def test_compose_fascia_pomeridiana_fino_alla_chiusura_esatta() -> None:
    """Arrivo 15:00, durata 120 -> 17:00 esatte: ammessa. 121: no."""
    a = _cand("a", temi=("arte",))
    ok = _componi(
        [a, _cand("b", durata=120, orari=_orari(("15:00", "17:00")), temi=("verde",))],
        {"a": 0.9, "b": 0.8}, "14:30",
    )
    assert _ids(ok) == ["a", "b"]
    no = _componi(
        [a, _cand("b", durata=121, orari=_orari(("15:00", "17:00")), temi=("verde",))],
        {"a": 0.9, "b": 0.8}, "14:30",
    )
    assert _ids(no) == ["a"]


def test_compose_giorno_sbagliato_resta_chiusa() -> None:
    """Fascia del martedi' non apre il lunedi'; apre il martedi'."""
    a = _cand("a", temi=("arte",))
    b = _cand("b", orari=_orari(("09:00", "18:00"), giorno=1), temi=("verde",))
    assert _ids(_componi([a, b], {"a": 0.9, "b": 0.8}, "10:00", data=LUNEDI)) == ["a"]
    assert _ids(_componi([a, b], {"a": 0.9, "b": 0.8}, "10:00", data=MARTEDI)) == ["a", "b"]


def test_compose_chiuso_nel_primo_slot_entra_in_uno_successivo() -> None:
    """B ha lo score piu' alto ma e' chiusa nel primo slot (14:00, apre alle
    15:00): salta, RESTA tra i rimanenti, e dopo A (14:00-15:00) entra alle
    15:00. Lo score non scavalca il filtro, e il filtro non cancella B per
    sempre."""
    a = _cand("a", durata=60, temi=("arte",))
    b = _cand("b", orari=_orari(("15:00", "17:00")), temi=("verde",))
    it = _componi([a, b], {"a": 0.5, "b": 0.9}, "14:00")
    assert _ids(it) == ["a", "b"]
    assert _arrivi(it) == {"a": time(14, 0), "b": time(15, 0)}


def test_compose_chiusa_in_ogni_slot_non_entra_mai() -> None:
    a = _cand("a", durata=60, temi=("arte",))
    c = _cand("c", durata=60, temi=("musica",))
    b = _cand("b", orari=_orari(("09:00", "12:00")), temi=("verde",))
    it = _componi([a, b, c], {"a": 0.5, "b": 0.9, "c": 0.4}, "14:00")
    assert _ids(it) == ["a", "c"]


def _quartetto(c_orari: list[FasciaApertura] | None) -> list[GraphCandidate]:
    return [
        _cand("a", temi=("arte",)),
        _cand("b", temi=("arte",)),
        _cand("c", temi=("verde",), orari=c_orari),
        _cand("d", temi=("musica",)),
    ]


PUNTI_QUARTETTO = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6}


def test_compose_diversificazione_controllo_senza_orari_sceglie_il_tema_diverso() -> None:
    """Controllo: senza orari, dopo A (arte) il migliore B ripete il tema,
    quindi la diversificazione prende C (verde)."""
    it = _componi(_quartetto(None), PUNTI_QUARTETTO, "10:00")
    assert _ids(it)[:2] == ["a", "c"]


def test_compose_diversificazione_salta_il_chiuso_e_lo_riprende_dopo() -> None:
    """Stessa scena, ma C e' aperta solo 10:40-12:00. Nel secondo slot (arrivo
    10:30) C e' chiusa: la diversificazione NON puo' sceglierla e prende D
    (musica). Resta tra i rimanenti e nel quarto slot (arrivo 11:30, fino
    alle 12:00) entra. Il motore di prima la escludeva del tutto, perche'
    chiusa alle 10:00."""
    it = _componi(_quartetto(_orari(("10:40", "12:00"))), PUNTI_QUARTETTO, "10:00")
    assert _ids(it) == ["a", "d", "b", "c"]
    assert _arrivi(it)["c"] == time(11, 30)


def test_compose_ogni_tappa_restituita_e_aperta_al_suo_arrivo() -> None:
    """Proprieta': qualunque sia l'insieme, ogni tappa con orari e' aperta per
    [arrivo, arrivo + durata] nel suo giorno."""
    cands = [
        _cand("a", durata=45, orari=_orari(("09:00", "12:00"), ("15:00", "18:00"))),
        _cand("b", durata=60, orari=_orari(("10:00", "11:30")), temi=("verde",)),
        _cand("c", durata=30, orari=_orari(("11:00", "13:00")), temi=("musica",)),
        _cand("d", durata=50, temi=("silenzio",)),
        _cand("e", durata=40, orari=_orari(("12:30", "14:00")), temi=("arte", "verde")),
    ]
    punti = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6, "e": 0.5}
    per_id = {c.experience.id: c.experience for c in cands}
    for ora in ("08:30", "09:30", "10:15", "11:45", "13:00"):
        it = _componi(cands, punti, ora, tempo=300)
        for s in it.stops:
            e = per_id[s.experience_id]
            assert rientra_in_orario(
                e.orari_apertura, 0, s.arrivo, durata_min=e.durata_min
            ), f"{s.experience_id} chiusa a {s.arrivo} (composizione alle {ora})"
            assert s.reason


# ===========================================================================
# Costruzione di itinerari ricevuti per l'adattamento
# ===========================================================================


def _tappa(id_: str, arrivo: str, durata: int) -> ItineraryStop:
    return ItineraryStop(
        experience_id=id_, arrivo=_t(arrivo), durata_min=durata,
        reason=f"Motivo di {id_}.",
    )


def _itin(stops: list[ItineraryStop], *, budget: int | None = 600) -> Itinerary:
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 6, 15, 9, 0),
        tempo_disponibile_min=budget, tempo_effettivo_min=budget,
    )


def _adatta(it: Itinerary, signal: Signal, cands: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(
        it, signal, cands, None, compose_reason, adapt_reason, vocabolario=VOC
    )


def _esiti(it: Itinerary) -> dict[str, EsitoAdattamento | None]:
    return {s.experience_id: s.esito_adattamento for s in it.stops}


def _escluse(it: Itinerary) -> list[tuple[str, EsitoAdattamento]]:
    return [(t.experience_id, t.esito) for t in it.tappe_escluse]


# ===========================================================================
# 2. Adattamento: il sostituto e' valutato all'arrivo
# ===========================================================================

PIOGGIA_13_30 = _segnale("13:30", meteo="pioggia")
CHIUSO_12_15 = _orari(("08:00", "12:00"), ("15:00", "18:00"))


def test_adapt_pioggia_sostituto_chiuso_alle_13_30_non_e_ammesso() -> None:
    """Spec: luogo al chiuso aperto 08-12 e 15-18, pioggia alle 13:30 -> NON
    e' un sostituto ammesso: la tappa resta, senza alternativa."""
    t = _cand("t", al_chiuso=False)
    s = _cand("s", orari=CHIUSO_12_15)
    out = _adatta(_itin([_tappa("t", "13:30", 30)]), PIOGGIA_13_30, [t, s])
    assert _ids(out) == ["t"]
    assert _esiti(out) == {"t": EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA}
    assert out.tappe_escluse == []


def test_adapt_pioggia_con_un_altro_sostituto_aperto_vince_quello() -> None:
    """Il chiuso 12-15 e' piu' affine per tema (preferenza forte) ma e'
    chiuso: vince l'altro, aperto."""
    t = _cand("t", al_chiuso=False, temi=("arte",))
    chiuso = _cand("a-chiuso", orari=CHIUSO_12_15, temi=("arte",))
    aperto = _cand("z-aperto", temi=("verde",))
    out = _adatta(_itin([_tappa("t", "13:30", 30)]), PIOGGIA_13_30, [t, chiuso, aperto])
    assert _ids(out) == ["z-aperto"]
    assert _esiti(out) == {"z-aperto": EsitoAdattamento.SOSTITUITA}


def test_adapt_pioggia_il_sostituto_deve_chiudere_dopo_la_fine_della_visita() -> None:
    """Aperto 13:00-14:00 e quindi aperto alle 13:30, ma la visita (45 min)
    finirebbe alle 14:15: non e' ammesso. Controllato solo all'ora del
    segnale, il motore di prima lo sceglieva."""
    t = _cand("t", al_chiuso=False, temi=("arte",))
    corto = _cand("a-corto", durata=45, orari=_orari(("13:00", "14:00")), temi=("arte",))
    aperto = _cand("z-aperto", temi=("verde",))
    out = _adatta(_itin([_tappa("t", "13:30", 30)]), PIOGGIA_13_30, [t, corto, aperto])
    assert _ids(out) == ["z-aperto"]


def test_adapt_sostituto_in_posizione_successiva_e_valutato_all_arrivo_ricalcolato() -> None:
    """X (90 min) occupa 13:30-15:00; T e' la seconda tappa e il sostituto S
    ARRIVERA' alle 15:00. S e' aperto solo 15:00-18:00: chiuso a signal.ora
    (13:30) ma aperto al suo arrivo -> ammesso."""
    x = _cand("x", durata=90, temi=("silenzio",))
    t = _cand("t", al_chiuso=False)
    s = _cand("s", orari=_orari(("15:00", "18:00")))
    it = _itin([_tappa("x", "13:30", 90), _tappa("t", "15:00", 30)])
    out = _adatta(it, PIOGGIA_13_30, [x, t, s])
    assert _ids(out) == ["x", "s"]
    assert _esiti(out)["s"] is EsitoAdattamento.SOSTITUITA
    assert _arrivi(out)["s"] == time(15, 0)


def test_adapt_sostituto_aperto_al_segnale_ma_chiuso_all_arrivo_ricalcolato() -> None:
    """Specchio del precedente: S e' aperto 13:00-14:30 (aperto a 13:30) ma
    arriverebbe alle 15:00, chiuso -> non ammesso."""
    x = _cand("x", durata=90, temi=("silenzio",))
    t = _cand("t", al_chiuso=False)
    s = _cand("s", orari=_orari(("13:00", "14:30")))
    it = _itin([_tappa("x", "13:30", 90), _tappa("t", "15:00", 30)])
    out = _adatta(it, PIOGGIA_13_30, [x, t, s])
    assert _ids(out) == ["x", "t"]
    assert _esiti(out)["t"] is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


# ===========================================================================
# 3. Adattamento: taglio TAGLIATA_ORARIO
# ===========================================================================


def test_adapt_tappa_non_toccata_che_slitta_fuori_orario_esce() -> None:
    """T (all'aperto, 30 min) e' sostituita da S di 90 minuti: U, NON toccata
    dal segnale, slitta da 14:00 a 15:00. Aperta 13:00-15:00 con durata 30
    finirebbe alle 15:30: esce con TAGLIATA_ORARIO."""
    t = _cand("t", al_chiuso=False)
    s = _cand("s", durata=90, temi=("verde",))
    u = _cand("u", orari=_orari(("13:00", "15:00")), temi=("musica",))
    it = _itin([_tappa("t", "13:30", 30), _tappa("u", "14:00", 30)])
    out = _adatta(it, PIOGGIA_13_30, [t, s, u])
    assert _ids(out) == ["s"]
    assert _esiti(out) == {"s": EsitoAdattamento.SOSTITUITA}
    assert _escluse(out) == [("u", EsitoAdattamento.TAGLIATA_ORARIO)]
    assert out.tappe_escluse[0].reason == FRASE_ORARIO
    assert out.adattato_da_segnale is True


def test_adapt_nulla_cambiato_tappa_chiusa_all_arrivo_ricevuto_esce() -> None:
    """Segnale sereno, nessuna sostituzione: V e' chiusa al suo arrivo
    ricevuto (16:00, aperta solo 09-12) e dunque esce; W resta. Il motore di
    prima non la toccava."""
    v = _cand("v", orari=_orari(("09:00", "12:00")))
    w = _cand("w", temi=("verde",))
    it = _itin([_tappa("v", "16:00", 30), _tappa("w", "16:30", 30)])
    out = _adatta(it, _segnale("16:00"), [v, w])
    assert _escluse(out) == [("v", EsitoAdattamento.TAGLIATA_ORARIO)]
    assert out.tappe_escluse[0].reason == FRASE_ORARIO
    assert out.adattato_da_segnale is True
    assert _ids(out) == ["w"]
    assert _arrivi(out)["w"] == time(16, 0)  # arrivi ricalcolati da signal.ora
    assert _esiti(out)["w"] is EsitoAdattamento.NON_TOCCATA


def test_adapt_nulla_cambiato_tutto_aperto_agli_arrivi_ricevuti_non_tocca_nulla() -> None:
    """Se ogni tappa e' aperta al suo arrivo RICEVUTO, nulla cambia, anche se
    `signal.ora` (13:00) cadrebbe fuori dalla fascia: gli arrivi restano
    quelli ricevuti e il flag resta spento. Non regressione."""
    v = _cand("v", orari=_orari(("09:00", "12:00")))
    it = _itin([_tappa("v", "10:00", 30)])
    out = _adatta(it, _segnale("13:00"), [v])
    assert _ids(out) == ["v"]
    assert _arrivi(out)["v"] == time(10, 0)
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False


def test_adapt_tappa_stub_non_e_mai_tagliata_per_orario_e_conta_nella_timeline() -> None:
    """Una tappa il cui id non e' tra i candidati (fluttuante) non ha orari:
    non esce mai. Conta pero' nella timeline: dopo la sostituzione di T la
    stub (60 min) sposta U oltre la chiusura (12:00)."""
    t = _cand("t", al_chiuso=False)
    s = _cand("s", temi=("verde",))
    u = _cand("u", orari=_orari(("09:00", "12:00")), temi=("musica",))
    it = _itin([
        _tappa("t", "10:00", 30),
        _tappa("fluttuante-violinista", "10:30", 60),
        _tappa("u", "11:30", 30),
    ])
    out = _adatta(it, _segnale("10:00", meteo="pioggia"), [t, s, u])
    assert _ids(out) == ["s", "fluttuante-violinista"]
    # stub ha trasferimento stimato di default (10 min): 10:30 + 10.
    assert _arrivi(out)["fluttuante-violinista"] == time(10, 40)
    assert _escluse(out) == [("u", EsitoAdattamento.TAGLIATA_ORARIO)]


def test_adapt_stub_isolata_mai_tagliata() -> None:
    it = _itin([_tappa("fluttuante-x", "03:00", 30)], budget=None)
    out = _adatta(it, _segnale("03:00"), [_cand("zz", orari=_orari(("09:00", "10:00")))])
    assert _ids(out) == ["fluttuante-x"]
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False


def test_adapt_cascata_dopo_sostituzione_le_successive_sono_rivalutate_senza_la_tolta() -> None:
    """T (30) -> S (60 min), 10:00-11:00. U1 (aperta 10:00-10:45) arriverebbe
    alle 11:00: esce. U2 (aperta 11:00-11:45, 30 min) con U1 arriverebbe alle
    11:30 (chiusa), ma U1 e' stata tolta: arriva alle 11:00 e resta."""
    t = _cand("t", al_chiuso=False)
    s = _cand("s", durata=60, temi=("verde",))
    u1 = _cand("u1", orari=_orari(("10:00", "10:45")), temi=("musica",))
    u2 = _cand("u2", orari=_orari(("11:00", "11:45")), temi=("silenzio",))
    it = _itin([_tappa("t", "10:00", 30), _tappa("u1", "10:30", 30), _tappa("u2", "11:00", 30)])
    out = _adatta(it, _segnale("10:00", meteo="pioggia"), [t, s, u1, u2])
    assert _ids(out) == ["s", "u2"]
    assert _arrivi(out)["u2"] == time(11, 0)
    assert _escluse(out) == [("u1", EsitoAdattamento.TAGLIATA_ORARIO)]


def test_adapt_cascata_nulla_cambiato_togliere_una_tappa_anticipa_e_rivaluta() -> None:
    """Sereno. X chiusa al suo arrivo ricevuto (10:00, aperta 08-09): esce.
    Y (aperta 10:00-11:00) anticipa da 10:30 a 10:00, aperta, resta. W
    (aperta 10:45-11:30, ricevuta alle 11:00, aperta) anticipa a 10:30:
    chiusa al nuovo arrivo -> esce. Un controllo solo sugli arrivi ricevuti
    la terrebbe."""
    x = _cand("x", orari=_orari(("08:00", "09:00")))
    y = _cand("y", orari=_orari(("10:00", "11:00")), temi=("verde",))
    w = _cand("w", orari=_orari(("10:45", "11:30")), temi=("musica",))
    it = _itin([_tappa("x", "10:00", 30), _tappa("y", "10:30", 30), _tappa("w", "11:00", 30)])
    out = _adatta(it, _segnale("10:00"), [x, y, w])
    assert _ids(out) == ["y"]
    assert _arrivi(out)["y"] == time(10, 0)
    assert sorted(_escluse(out)) == [
        ("w", EsitoAdattamento.TAGLIATA_ORARIO),
        ("x", EsitoAdattamento.TAGLIATA_ORARIO),
    ]
    assert out.adattato_da_segnale is True


def test_adapt_sostituta_tagliata_per_orario_riporta_l_id_della_tappa_originale() -> None:
    """X (prima tappa, aperta 08-09) e' chiusa alle 10:00 e esce; T (all'aperto,
    pioggia) e' sostituita da S, scelta quando X c'era (S arrivava alle
    10:30, aperta 10:30-11:30). Tolta X, S arriva alle 10:00: chiusa, esce. In
    `tappe_escluse` finisce la tappa che il visitatore aveva (t), non s."""
    x = _cand("x", orari=_orari(("08:00", "09:00")))
    t = _cand("t", al_chiuso=False)
    s = _cand("s", orari=_orari(("10:30", "11:30")), temi=("verde",))
    it = _itin([
        _tappa("x", "10:00", 30),
        _tappa("t", "10:30", 30),
        _tappa("fluttuante-z", "11:00", 30),
    ])
    out = _adatta(it, _segnale("10:00", meteo="pioggia"), [x, t, s])
    assert sorted(_escluse(out)) == [
        ("t", EsitoAdattamento.TAGLIATA_ORARIO),
        ("x", EsitoAdattamento.TAGLIATA_ORARIO),
    ]
    assert _ids(out) == ["fluttuante-z"]
    assert all(t_.reason == FRASE_ORARIO for t_ in out.tappe_escluse)


def test_adapt_taglio_per_orario_accende_il_flag_e_rigenera_il_reason_canonico() -> None:
    """Un `reason` libero arrivato dal client in `tappe_escluse` non
    sopravvive; quello del taglio per orario e' il testo del motore."""
    v = _cand("v", orari=_orari(("09:00", "12:00")))
    it = _itin([_tappa("v", "16:00", 30), _tappa("fluttuante-a", "16:30", 30)])
    out = _adatta(it, _segnale("16:00"), [v])
    assert out.adattato_da_segnale is True
    assert [(t.experience_id, t.esito, t.reason) for t in out.tappe_escluse] == [
        ("v", EsitoAdattamento.TAGLIATA_ORARIO, FRASE_ORARIO)
    ]
    # secondo adattamento, sereno: la voce si conserva (si accumula).
    out2 = _adatta(out, _segnale("16:00"), [v])
    assert _escluse(out2) == [("v", EsitoAdattamento.TAGLIATA_ORARIO)]


# ===========================================================================
# 4. Non regressione: senza data o senza orari il motore non filtra
#    (questi test devono PASSARE identici col motore di prima)
# ===========================================================================


def test_nonreg_compose_senza_data_ignora_gli_orari_dichiarati() -> None:
    b = _cand("b", durata=40, orari=_orari(("09:00", "12:00")), temi=("verde",))
    a = _cand("a")
    cands = [a, b]
    punti = {"a": 0.9, "b": 0.8}
    senza_data = _componi(cands, punti, "11:20", data=None)
    assert _ids(senza_data) == ["a", "b"]
    riferimento = _componi(_senza_orari(cands), punti, "11:20", data=None)
    assert [(s.experience_id, s.arrivo, s.durata_min) for s in senza_data.stops] == [
        (s.experience_id, s.arrivo, s.durata_min) for s in riferimento.stops
    ]
    assert [s.reason for s in senza_data.stops] == [s.reason for s in riferimento.stops]


def test_nonreg_compose_con_data_ma_senza_orari_e_identico_a_senza_data() -> None:
    cands = [
        _cand("a", temi=("arte",)), _cand("b", temi=("arte",)),
        _cand("c", temi=("verde",)), _cand("d", durata=45, temi=("musica",)),
    ]
    punti = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6}
    con = _componi(cands, punti, "11:20", data=LUNEDI)
    senza = _componi(cands, punti, "11:20", data=None)
    assert _ids(con) == _ids(senza) == ["a", "c", "b", "d"]
    assert [(s.arrivo, s.reason) for s in con.stops] == [(s.arrivo, s.reason) for s in senza.stops]


def test_nonreg_compose_seed_con_data_identico_a_senza_data() -> None:
    """Seed spogliato degli orari: se nessuna esperienza dichiara orari, la data
    non cambia nulla. (Il seed reale ora dichiara orari: vedi `_senza_orari`.)"""
    out = []
    for data in (None, LUNEDI):
        signal = _segnale("10:00", data=data)
        ctx = VisitorContext(person_id="p", profile=_profilo(240), signal=signal)
        cands = _senza_orari(SeedCandidateSource().candidates(ctx))
        it = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO_LUCCA)
        out.append([(s.experience_id, s.arrivo, s.durata_min, s.reason) for s in it.stops])
    assert out[0] == out[1]
    assert out[0], "il seed deve produrre tappe"


def test_nonreg_adapt_senza_data_ignora_gli_orari_dichiarati() -> None:
    """Senza data: ne' taglio per orario ne' esclusione del sostituto chiuso."""
    v = _cand("v", orari=_orari(("09:00", "12:00")))
    it = _itin([_tappa("v", "16:00", 30)])
    out = _adatta(it, _segnale("16:00", data=None), [v])
    assert _ids(out) == ["v"]
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False

    t = _cand("t", al_chiuso=False)
    s = _cand("s", orari=CHIUSO_12_15)
    out2 = _adatta(
        _itin([_tappa("t", "13:30", 30)]), _segnale("13:30", data=None, meteo="pioggia"), [t, s]
    )
    assert _ids(out2) == ["s"]
    assert _esiti(out2) == {"s": EsitoAdattamento.SOSTITUITA}


def test_nonreg_adapt_con_data_ma_senza_orari_non_taglia_per_orario() -> None:
    """Esperienze senza orari (il seed oggi): con data, nessun taglio per
    orario, arrivi ricevuti conservati. Lo stesso scenario del taglio, spogliato
    degli orari."""
    cands = _senza_orari([
        _cand("v"), _cand("w", temi=("verde",)),
    ])
    it = _itin([_tappa("v", "16:00", 30), _tappa("w", "16:30", 30)])
    out = _adatta(it, _segnale("16:00"), cands)
    assert _ids(out) == ["v", "w"]
    assert out.tappe_escluse == []
    assert out.adattato_da_segnale is False
    assert [s.arrivo for s in out.stops] == [time(16, 0), time(16, 30)]

    # con una sostituzione per pioggia, sempre senza orari
    t = _cand("t", al_chiuso=False)
    s = _cand("s", durata=90, temi=("verde",))
    u = _cand("u", temi=("musica",))
    it2 = _itin([_tappa("t", "13:30", 30), _tappa("u", "14:00", 30)])
    out2 = _adatta(it2, PIOGGIA_13_30, [t, s, u])
    assert _ids(out2) == ["s", "u"]
    assert out2.tappe_escluse == []
    assert _arrivi(out2)["u"] == time(15, 0)


def test_nonreg_adapt_seed_con_data_identico_a_senza_data() -> None:
    """Seed spogliato degli orari: la data non cambia l'adattamento."""
    outs = []
    for data in (None, LUNEDI):
        signal = _segnale("10:00", data=data)
        ctx = VisitorContext(person_id="p", profile=_profilo(240), signal=signal)
        cands = _senza_orari(SeedCandidateSource().candidates(ctx))
        base = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO_LUCCA)
        pioggia = _segnale("10:00", data=data, meteo="pioggia")
        it = adapt_itinerary(
            base, pioggia, cands, None, compose_reason, adapt_reason,
            vocabolario=VOCABOLARIO_LUCCA,
        )
        outs.append((
            [(s.experience_id, s.arrivo, s.esito_adattamento, s.reason) for s in it.stops],
            [(t.experience_id, t.esito, t.reason) for t in it.tappe_escluse],
            it.adattato_da_segnale,
        ))
    assert outs[0] == outs[1]
