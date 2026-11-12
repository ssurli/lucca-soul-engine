"""`ItineraryStop.causa_adattamento` scritto dal motore, coerente col `reason`.

- sola pioggia -> "pioggia"; sola folla -> "affollamento"; pioggia + folla sulla
  stessa tappa all'aperto -> "pioggia" (sia SOSTITUITA sia MANTENUTA);
- tappa non toccata -> None;
- il valore ricevuto nella richiesta non sopravvive (ricalcolato sempre);
- per OGNI caso causa e `reason` concordano: la frase del reason e' quella della
  stessa causa (costruita con le funzioni/costanti del motore e di rag).
"""

from __future__ import annotations

from datetime import datetime, time

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
from experience_engine.engine import _FRASE_MANTENUTA_PIOGGIA, _frase_esito
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import adapt_reason, compose_reason

FOLLA = 0.75
PROFILO = EmotionalProfile(
    curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
    tempo_disponibile_min=600,
)
ORA = time(9, 0)
SOSTITUITA = EsitoAdattamento.SOSTITUITA
MANTENUTA = EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
NON_TOCCATA = EsitoAdattamento.NON_TOCCATA


def _segnale(meteo: str = "sereno", folla: dict[str, float] | None = None) -> Signal:
    return Signal(
        meteo=meteo,  # type: ignore[arg-type]
        affollamento=folla or {}, stanchezza=0.0, ora=ORA,
    )


def _cand(id_: str, place: str, *, al_chiuso: bool) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=place, temi=[],
            durata_min=30, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Piazza {place}",
        connessioni=[],
    )


def _itinerario(ids: list[str], **stop_extra: object) -> Itinerary:
    stops = [
        ItineraryStop(
            experience_id=id_, arrivo=time(9 + i, 0), durata_min=30,
            reason="Motivo originale.", **stop_extra,  # type: ignore[arg-type]
        )
        for i, id_ in enumerate(ids)
    ]
    return Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))


def _adatta(it: Itinerary, segnale: Signal, candidati: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(
        it, segnale, candidati, PROFILO, compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )


def _dice_pioggia(stop: ItineraryStop) -> bool:
    sostituita = adapt_reason("", "la pioggia").rstrip(".")  # "Sostituita per la pioggia"
    return stop.reason.startswith(sostituita) or _FRASE_MANTENUTA_PIOGGIA in stop.reason


def _dice_affollamento(stop: ItineraryStop, cand: GraphCandidate | None) -> bool:
    if stop.reason.startswith("Sostituita per l'affollamento"):
        return True
    if cand is None:
        return False
    frase = _frase_esito(
        MANTENUTA, motivo="affollamento", luogo=cand.place_nome, articolo=cand.place_articolo
    )
    return frase is not None and frase in stop.reason


def _verifica_concordanza(
    stop: ItineraryStop, causa: str | None, cand_originale: GraphCandidate | None = None
) -> None:
    """Causa e reason dicono la stessa cosa (e non l'altra)."""
    assert stop.causa_adattamento == causa
    if causa == "pioggia":
        assert _dice_pioggia(stop), stop.reason
        assert not _dice_affollamento(stop, cand_originale), stop.reason
        assert "molta gente" not in stop.reason
    elif causa == "affollamento":
        assert _dice_affollamento(stop, cand_originale), stop.reason
        assert not _dice_pioggia(stop), stop.reason
    else:
        assert not stop.reason.startswith("Sostituita per")
        assert not _dice_pioggia(stop)
        assert "molta gente" not in stop.reason


# --- sostituita ----------------------------------------------------------------


def test_sola_pioggia_sostituita_causa_pioggia() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    alt = _cand("alt", "p-y", al_chiuso=True)
    r = _adatta(_itinerario(["orig"]), _segnale("pioggia"), [orig, alt])
    (stop,) = r.stops
    assert stop.experience_id == "alt" and stop.esito_adattamento == SOSTITUITA
    _verifica_concordanza(stop, "pioggia", orig)


def test_sola_folla_sostituita_causa_affollamento() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    alt = _cand("alt", "p-y", al_chiuso=False)
    r = _adatta(_itinerario(["orig"]), _segnale(folla={"p-x": FOLLA}), [orig, alt])
    (stop,) = r.stops
    assert stop.experience_id == "alt" and stop.esito_adattamento == SOSTITUITA
    _verifica_concordanza(stop, "affollamento", orig)


def test_pioggia_e_folla_sostituita_causa_pioggia() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    alt = _cand("alt", "p-y", al_chiuso=True)
    r = _adatta(_itinerario(["orig"]), _segnale("pioggia", {"p-x": FOLLA}), [orig, alt])
    (stop,) = r.stops
    assert stop.experience_id == "alt" and stop.esito_adattamento == SOSTITUITA
    _verifica_concordanza(stop, "pioggia", orig)


# --- mantenuta senza alternativa -------------------------------------------------


def test_mantenuta_per_pioggia_causa_pioggia() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    r = _adatta(_itinerario(["orig"]), _segnale("pioggia"), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == MANTENUTA
    _verifica_concordanza(stop, "pioggia", orig)


def test_mantenuta_per_folla_causa_affollamento() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    r = _adatta(_itinerario(["orig"]), _segnale(folla={"p-x": FOLLA}), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == MANTENUTA
    _verifica_concordanza(stop, "affollamento", orig)


def test_pioggia_e_folla_mantenuta_causa_pioggia() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    r = _adatta(_itinerario(["orig"]), _segnale("pioggia", {"p-x": FOLLA}), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == MANTENUTA
    _verifica_concordanza(stop, "pioggia", orig)


# --- non toccata ------------------------------------------------------------------


@pytest.mark.parametrize("al_chiuso", [True, False])
def test_tappa_non_toccata_senza_causa(al_chiuso: bool) -> None:
    orig = _cand("orig", "p-x", al_chiuso=al_chiuso)
    r = _adatta(_itinerario(["orig"]), _segnale(), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == NON_TOCCATA
    _verifica_concordanza(stop, None)


def test_al_chiuso_con_folla_non_toccata() -> None:
    orig = _cand("orig", "p-x", al_chiuso=True)
    r = _adatta(_itinerario(["orig"]), _segnale(folla={"p-x": FOLLA}), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == NON_TOCCATA
    _verifica_concordanza(stop, None)


def test_itinerario_misto_causa_per_tappa() -> None:
    aperta_folla = _cand("a", "p-a", al_chiuso=False)
    chiusa = _cand("b", "p-b", al_chiuso=True)
    alt = _cand("alt", "p-alt", al_chiuso=False)
    r = _adatta(
        _itinerario(["a", "b"]), _segnale(folla={"p-a": FOLLA}), [aperta_folla, chiusa, alt]
    )
    per_id = {s.experience_id: s for s in r.stops}
    _verifica_concordanza(per_id["alt"], "affollamento", aperta_folla)
    _verifica_concordanza(per_id["b"], None)


# --- il valore della richiesta non sopravvive --------------------------------------


def test_causa_in_ingresso_su_tappa_non_piu_toccata_non_sopravvive() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    it = _itinerario(["orig"], esito_adattamento=SOSTITUITA, causa_adattamento="affollamento")
    assert it.stops[0].causa_adattamento == "affollamento"  # il contratto la accetta
    r = _adatta(it, _segnale(), [orig])  # segnale che non la tocca
    (stop,) = r.stops
    assert stop.esito_adattamento == NON_TOCCATA
    _verifica_concordanza(stop, None)


def test_causa_in_ingresso_diversa_viene_ricalcolata() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    it = _itinerario(["orig"], esito_adattamento=MANTENUTA, causa_adattamento="affollamento")
    r = _adatta(it, _segnale("pioggia"), [orig])
    (stop,) = r.stops
    assert stop.esito_adattamento == MANTENUTA
    _verifica_concordanza(stop, "pioggia", orig)


def test_secondo_adattamento_ricalcola_la_causa() -> None:
    orig = _cand("orig", "p-x", al_chiuso=False)
    alt = _cand("alt", "p-y", al_chiuso=True)
    primo = _adatta(_itinerario(["orig"]), _segnale("pioggia"), [orig, alt])
    assert primo.stops[0].causa_adattamento == "pioggia"
    secondo = _adatta(primo, _segnale(), [orig, alt])
    (stop,) = secondo.stops
    assert stop.causa_adattamento is None
    assert stop.esito_adattamento == NON_TOCCATA
