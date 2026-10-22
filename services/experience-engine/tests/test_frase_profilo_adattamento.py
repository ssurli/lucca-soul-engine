"""Frase del profilo in adattamento e tratto netto nel fallback (ondata 2b, compito 4).

- `_tratto_dominante_fallback` (motore, senza RAG) segue la STESSA regola di
  `rag.reasons._tratto_dominante`: un tratto 0..1 conta solo se >= 0.7 o
  <= 0.2 (limiti inclusi), nessun tratto netto = nessuna frase.
- In adattamento la frase del profilo compare al massimo una volta, sulla
  PRIMA tappa del risultato quando è `SOSTITUITA`:
  "Sostituita per la pioggia. <Frase profilo>. <resto del motivo>".
  Una prima tappa `NON_TOCCATA` conserva il `reason` ricevuto (anche se è
  diventata prima perché l'originale è stata tagliata); una
  `MANTENUTA_SENZA_ALTERNATIVA` conserva il suo e aggiunge solo la frase di
  esito. Senza profilo nella richiesta, nessuna frase.
"""

from __future__ import annotations

from datetime import datetime, time
from itertools import product

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
)
from experience_engine import adapt_itinerary
from experience_engine.engine import (
    _FRASI_PROFILO_FALLBACK,
    ReasonFn,
    _tratto_dominante_fallback,
)
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import _tratto_dominante, adapt_reason, compose_reason

CURIOSO = "Hai voglia di perderti e lasciarti sorprendere."
PIOGGIA = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0))
REASON_FNS: list[tuple[str, ReasonFn | None]] = [("fallback", None), ("rag", compose_reason)]


def _profilo(
    curiosita: float = 0.5,
    contemplazione: float = 0.5,
    arte: float = 0.5,
    *,
    bambini: bool = False,
    accessibile: bool = False,
) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=curiosita, contemplazione=contemplazione, arte=arte,
        con_bambini=bambini, accessibilita_richiesta=accessibile,
        tempo_disponibile_min=240,
    )


# ---------------------------------------------------------------------------
# Tratto netto: fallback del motore == RAG
# ---------------------------------------------------------------------------


def test_fallback_un_po_di_curiosita_nessuna_frase() -> None:
    assert _tratto_dominante_fallback(_profilo(curiosita=0.35)) is None


def test_fallback_curiosita_alta() -> None:
    assert _tratto_dominante_fallback(_profilo(curiosita=0.75)) == (
        "hai voglia di perderti e lasciarti sorprendere"
    )


@pytest.mark.parametrize(
    ("valore", "netto"),
    [(0.7, True), (0.69, False), (0.2, True), (0.21, False),
     (0.1 * 7, True), (1 - 0.8, True), (0.7 - 1e-6, False), (0.2 + 1e-6, False)],
)
def test_fallback_limiti(valore: float, netto: bool) -> None:
    assert (_tratto_dominante_fallback(_profilo(curiosita=valore)) is not None) is netto


def test_fallback_identico_alla_rag_su_una_griglia_con_i_limiti() -> None:
    valori = (0.0, 0.1, 0.2, 0.21, 0.35, 0.5, 0.65, 0.69, 0.7, 0.75, 0.9, 1.0)
    for cur, con, arte, bambini, accessibile in product(
        valori, valori, valori, (False, True), (False, True)
    ):
        p = _profilo(cur, con, arte, bambini=bambini, accessibile=accessibile)
        assert _tratto_dominante_fallback(p) == _tratto_dominante(p), p


def test_elenco_frasi_profilo_del_motore_completo() -> None:
    """`_FRASI_PROFILO_FALLBACK` (usato per riconoscere una frase già
    presente) contiene ESATTAMENTE le frasi che la RAG può produrre."""
    valori = (0.0, 0.2, 0.5, 0.8, 1.0)
    prodotte = {
        _tratto_dominante(_profilo(cur, con, arte, bambini=b, accessibile=a))
        for cur, con, arte, b, a in product(valori, valori, valori, (False, True), (False, True))
    } - {None}
    assert prodotte == set(_FRASI_PROFILO_FALLBACK)
    assert len(_FRASI_PROFILO_FALLBACK) == 8


# ---------------------------------------------------------------------------
# Adattamento: frase sulla prima tappa SOSTITUITA
# ---------------------------------------------------------------------------


def _cand(
    id_: str, *, al_chiuso: bool, temi: tuple[str, ...] = ("storia",), sospesa: bool = False,
    racconti: tuple[str, ...] = (),
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=list(temi),
            durata_min=30, al_chiuso=al_chiuso, accessibile=True, sospesa=sospesa,
        ),
        place_nome=f"Luogo {id_}",
        connessioni=[],
        temi_etichette=["storia"],
        racconti=list(racconti),
        distanza_m=0,
    )


def _itinerario(*ids: str) -> Itinerary:
    return Itinerary(
        person_id="p",
        stops=[
            ItineraryStop(
                experience_id=eid, arrivo=time(10 + i, 0), durata_min=30,
                reason=f"Motivo ricevuto {eid}.",
            )
            for i, eid in enumerate(ids)
        ],
        generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=240,
        tempo_effettivo_min=240,
    )


def _conta(reason: str, frase: str = CURIOSO) -> int:
    return reason.count(frase)


@pytest.mark.parametrize(("nome_fn", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
def test_prima_tappa_sostituita_porta_la_frase_dopo_sostituita(
    nome_fn: str, reason_fn: ReasonFn | None
) -> None:
    aperta = _cand("aperta", al_chiuso=False)
    chiusa = _cand("chiusa", al_chiuso=True)
    adapt_fn = adapt_reason if reason_fn is not None else None
    it = adapt_itinerary(
        _itinerario("aperta"), PIOGGIA, [aperta, chiusa], _profilo(curiosita=0.75),
        reason_fn, adapt_fn, vocabolario=VOCABOLARIO,
    )
    prima = it.stops[0]
    assert prima.experience_id == "chiusa"
    assert prima.esito_adattamento is EsitoAdattamento.SOSTITUITA
    assert prima.reason == (
        f"Sostituita per la pioggia. {CURIOSO} Temi: storia. Al chiuso."
    )


@pytest.mark.parametrize(("nome_fn", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
def test_senza_profilo_o_senza_tratto_netto_nessuna_frase(
    nome_fn: str, reason_fn: ReasonFn | None
) -> None:
    aperta = _cand("aperta", al_chiuso=False)
    chiusa = _cand("chiusa", al_chiuso=True)
    adapt_fn = adapt_reason if reason_fn is not None else None
    for profilo in (None, _profilo(curiosita=0.35)):
        it = adapt_itinerary(
            _itinerario("aperta"), PIOGGIA, [aperta, chiusa], profilo,
            reason_fn, adapt_fn, vocabolario=VOCABOLARIO,
        )
        assert it.stops[0].reason == "Sostituita per la pioggia. Temi: storia. Al chiuso."


def test_solo_la_prima_sostituita_porta_la_frase() -> None:
    cands = [
        _cand("a1", al_chiuso=False), _cand("a2", al_chiuso=False),
        _cand("c1", al_chiuso=True), _cand("c2", al_chiuso=True),
    ]
    it = adapt_itinerary(
        _itinerario("a1", "a2"), PIOGGIA, cands, _profilo(curiosita=0.75),
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    assert [s.esito_adattamento for s in it.stops] == [EsitoAdattamento.SOSTITUITA] * 2
    assert _conta(it.stops[0].reason) == 1
    assert _conta(it.stops[1].reason) == 0
    assert it.stops[1].reason.startswith("Sostituita per la pioggia. Temi:")


def test_prima_non_toccata_conserva_il_reason() -> None:
    """Prima tappa al chiuso (non toccata) e seconda sostituita: nessuna frase
    aggiunta da nessuna parte."""
    cands = [_cand("chiusa", al_chiuso=True), _cand("aperta", al_chiuso=False),
             _cand("alt", al_chiuso=True)]
    it = adapt_itinerary(
        _itinerario("chiusa", "aperta"), PIOGGIA, cands, _profilo(curiosita=0.75),
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    assert it.stops[0].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert it.stops[0].reason == "Motivo ricevuto chiusa."
    assert it.stops[1].esito_adattamento is EsitoAdattamento.SOSTITUITA
    assert all(_conta(s.reason) == 0 for s in it.stops)


def test_non_toccata_diventata_prima_dopo_un_taglio_conserva_il_reason() -> None:
    """L'originale prima tappa è sospesa (tagliata al passo 4): la non toccata
    che diventa prima conserva il suo `reason`, nessuna frase del profilo."""
    cands = [_cand("sospesa", al_chiuso=True, sospesa=True), _cand("chiusa", al_chiuso=True)]
    it = adapt_itinerary(
        _itinerario("sospesa", "chiusa"), PIOGGIA, cands, _profilo(curiosita=0.75),
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    assert [s.experience_id for s in it.stops] == ["chiusa"]
    assert it.stops[0].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert it.stops[0].reason == "Motivo ricevuto chiusa."


def test_sostituita_diventata_prima_dopo_un_taglio_porta_la_frase() -> None:
    cands = [_cand("sospesa", al_chiuso=True, sospesa=True), _cand("aperta", al_chiuso=False),
             _cand("alt", al_chiuso=True)]
    it = adapt_itinerary(
        _itinerario("sospesa", "aperta"), PIOGGIA, cands, _profilo(curiosita=0.75),
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    assert [s.experience_id for s in it.stops] == ["alt"]
    assert it.stops[0].reason == f"Sostituita per la pioggia. {CURIOSO} Temi: storia. Al chiuso."


def test_prima_mantenuta_senza_alternativa_non_riceve_la_frase() -> None:
    it = adapt_itinerary(
        _itinerario("aperta"), PIOGGIA, [_cand("aperta", al_chiuso=False)],
        _profilo(curiosita=0.75), compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    s = it.stops[0]
    assert s.esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert s.reason.startswith("Motivo ricevuto aperta. ")
    assert _conta(s.reason) == 0


def test_la_frase_non_si_ripete_se_il_motivo_la_contiene_gia() -> None:
    """Un racconto che coincide con la frase del profilo: il motivo con la
    frase la ripeterebbe; il motore la lascia una volta sola."""
    racconto = "hai voglia di perderti e lasciarti sorprendere"
    cands = [_cand("aperta", al_chiuso=False),
             _cand("chiusa", al_chiuso=True, racconti=(racconto,))]
    it = adapt_itinerary(
        _itinerario("aperta"), PIOGGIA, cands, _profilo(curiosita=0.75),
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    assert _conta(it.stops[0].reason) == 1, it.stops[0].reason


@pytest.mark.parametrize(
    "frase_altrui",
    ["È pensata anche per chi viaggia con bambini.", CURIOSO,
     "Preferisci un percorso chiaro, senza troppe sorprese."],
)
def test_nessuna_frase_se_un_altra_tappa_ne_porta_gia_una(frase_altrui: str) -> None:
    """Una tappa non toccata conserva un `reason` ricevuto con una frase del
    profilo (anche di un ALTRO profilo): la prima sostituita non ne aggiunge
    un'altra, e la non toccata resta intatta."""
    cands = [_cand("aperta", al_chiuso=False), _cand("chiusa", al_chiuso=True),
             _cand("alt", al_chiuso=True)]
    base = _itinerario("aperta", "chiusa")
    ricevuto = f"{frase_altrui} Motivo ricevuto chiusa."
    base = base.model_copy(update={"stops": [
        base.stops[0], base.stops[1].model_copy(update={"reason": ricevuto}),
    ]})
    it = adapt_itinerary(
        base, PIOGGIA, cands, _profilo(curiosita=0.75), compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )
    assert it.stops[0].esito_adattamento is EsitoAdattamento.SOSTITUITA
    assert it.stops[0].reason == "Sostituita per la pioggia. Temi: storia. Al chiuso."
    assert it.stops[1].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert it.stops[1].reason == ricevuto
