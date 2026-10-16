"""Disclosure partner unica e ultima anche su `reason` arrivati dal client
(wave "adattamento", correzione della doppia disclosure).

Regola: `_con_disclosure` sostituisce l'ULTIMA frase del `reason` che inizia
con "Offerta da " con l'attribuzione del candidato corrente del grafo; se il
candidato non ha più attribuzione la frase è tolta; senza frase "Offerta da "
l'attribuzione si aggiunge in coda. Le tappe senza candidato (stub) restano
intatte.
"""

from __future__ import annotations

from datetime import datetime, time

from contracts import (
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
)
from experience_engine import adapt_itinerary
from experience_engine.engine import _con_disclosure
from graph.seed_lucca import VOCABOLARIO

ATTRIBUZIONE_NUOVA = "Offerta da Pasticceria (esempio dimostrativo)."
#: Formato e nome precedenti a f90f601.
ATTRIBUZIONE_VECCHIA = "Offerta da Pasticceria Storica del Buccellato, bottega di pasticceria."
FRASE_PIOGGIA = (
    "Con la pioggia non c'è un'alternativa al coperto compatibile con questo percorso "
    "e con il tempo a disposizione: la tappa resta in programma."
)


def _cand(
    id_: str = "exp-dolce", *, attribuzione: str | None, al_chiuso: bool = True
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
            durata_min=30, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Piazza {id_}",
        connessioni=[],
        attribuzione=attribuzione,
    )


def _conta(reason: str) -> int:
    return reason.count("Offerta da ")


# ---------------------------------------------------------------------------
# _con_disclosure: i quattro casi della regola
# ---------------------------------------------------------------------------


def test_a_attribuzione_vecchia_sostituita_dalla_corrente() -> None:
    reason = f"Il buccellato racconta la città. {ATTRIBUZIONE_VECCHIA}"
    out = _con_disclosure(reason, _cand(attribuzione=ATTRIBUZIONE_NUOVA))
    assert out == f"Il buccellato racconta la città. {ATTRIBUZIONE_NUOVA}"
    assert _conta(out) == 1
    assert "Buccellato, bottega" not in out


def test_a_bis_formato_dimostrativo_vecchio_sostituito() -> None:
    vecchia = "Offerta da Pasticceria, bottega di pasticceria (esempio dimostrativo)."
    out = _con_disclosure(f"Motivo. {vecchia}", _cand(attribuzione=ATTRIBUZIONE_NUOVA))
    assert out == f"Motivo. {ATTRIBUZIONE_NUOVA}"
    assert _conta(out) == 1


def test_b_formato_nuovo_invariato_e_idempotente() -> None:
    cand = _cand(attribuzione=ATTRIBUZIONE_NUOVA)
    reason = f"Il buccellato racconta la città. {ATTRIBUZIONE_NUOVA}"
    una = _con_disclosure(reason, cand)
    due = _con_disclosure(una, cand)
    assert una == reason
    assert due == reason


def test_b_bis_sostituzione_idempotente() -> None:
    cand = _cand(attribuzione=ATTRIBUZIONE_NUOVA)
    una = _con_disclosure(f"Motivo. {ATTRIBUZIONE_VECCHIA}", cand)
    assert _con_disclosure(una, cand) == una


def test_c_senza_attribuzione_nel_reason_aggiunta_in_coda() -> None:
    out = _con_disclosure("Il buccellato racconta la città", _cand(attribuzione=ATTRIBUZIONE_NUOVA))
    assert out == f"Il buccellato racconta la città. {ATTRIBUZIONE_NUOVA}"
    assert _conta(out) == 1


def test_d_candidato_senza_partner_frase_rimossa_resto_intatto() -> None:
    reason = f"Il buccellato racconta la città. {ATTRIBUZIONE_VECCHIA}"
    out = _con_disclosure(reason, _cand(attribuzione=None))
    assert out == "Il buccellato racconta la città."
    assert _conta(out) == 0


def test_d_bis_frase_rimossa_anche_se_non_ultima() -> None:
    reason = f"Prima frase. {ATTRIBUZIONE_VECCHIA} Seconda frase."
    out = _con_disclosure(reason, _cand(attribuzione=None))
    assert out == "Prima frase. Seconda frase."


def test_senza_attribuzione_e_senza_frase_reason_identico() -> None:
    reason = "Il buccellato racconta la città"
    assert _con_disclosure(reason, _cand(attribuzione=None)) == reason


# ---------------------------------------------------------------------------
# Via adapt_itinerary
# ---------------------------------------------------------------------------


def _itinerario(reason: str, id_: str = "exp-dolce") -> Itinerary:
    return Itinerary(
        person_id="p",
        stops=[ItineraryStop(experience_id=id_, arrivo=time(10, 0), durata_min=30, reason=reason)],
        generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=100,
        tempo_effettivo_min=100,
    )


def test_adapt_mantenuta_senza_alternativa_esito_prima_disclosure_unica_ultima() -> None:
    cand = _cand(attribuzione=ATTRIBUZIONE_NUOVA, al_chiuso=False)
    it = _itinerario(f"Il buccellato racconta la città. {ATTRIBUZIONE_VECCHIA}")
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, pioggia, [cand], None, vocabolario=VOCABOLARIO)

    reason = r.stops[0].reason
    assert r.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert reason == (
        f"Il buccellato racconta la città. {FRASE_PIOGGIA} {ATTRIBUZIONE_NUOVA}"
    )
    assert _conta(reason) == 1
    assert reason.index(FRASE_PIOGGIA) < reason.index(ATTRIBUZIONE_NUOVA)

    # Secondo adattamento sullo stesso esito: nulla si duplica.
    r2 = adapt_itinerary(r, pioggia, [cand], None, vocabolario=VOCABOLARIO)
    assert r2.stops[0].reason == reason


def test_adapt_non_toccata_attribuzione_vecchia_sostituita() -> None:
    cand = _cand(attribuzione=ATTRIBUZIONE_NUOVA)
    it = _itinerario(f"Motivo. {ATTRIBUZIONE_VECCHIA}")
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, [cand], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert r.stops[0].reason == f"Motivo. {ATTRIBUZIONE_NUOVA}"


def test_adapt_partner_non_piu_presente_frase_rimossa() -> None:
    cand = _cand(attribuzione=None)
    it = _itinerario(f"Motivo. {ATTRIBUZIONE_VECCHIA}")
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, [cand], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].reason == "Motivo."


def test_adapt_reason_solo_disclosure_senza_partner_ricomposto_non_vuoto() -> None:
    cand = _cand(attribuzione=None)
    it = _itinerario(ATTRIBUZIONE_VECCHIA)
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, [cand], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].reason.strip()
    assert _conta(r.stops[0].reason) == 0


def test_adapt_tappa_senza_candidato_resta_intatta() -> None:
    """Stub (esperienza non restituita dalla sorgente): non si riscrive al
    buio, nemmeno la disclosure vecchia."""
    reason = f"Motivo. {ATTRIBUZIONE_VECCHIA}"
    it = _itinerario(reason, id_="exp-sconosciuta")
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, [], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].reason == reason


def test_adapt_tappa_senza_candidato_intatta_anche_con_arrivi_ricalcolati() -> None:
    """Percorso `_ricostruisci_stops` (c'è una sostituzione): lo stub resta
    intatto."""
    reason_stub = f"Motivo stub. {ATTRIBUZIONE_VECCHIA}"
    aperta = _cand("exp-aperta", attribuzione=None, al_chiuso=False)
    chiusa = _cand("exp-chiusa", attribuzione=None, al_chiuso=True)
    it = Itinerary(
        person_id="p",
        stops=[
            ItineraryStop(
                experience_id="exp-aperta", arrivo=time(10, 0), durata_min=30, reason="A."
            ),
            ItineraryStop(
                experience_id="exp-sconosciuta", arrivo=time(10, 40), durata_min=30,
                reason=reason_stub,
            ),
        ],
        generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=200,
        tempo_effettivo_min=200,
    )
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, pioggia, [aperta, chiusa], None, vocabolario=VOCABOLARIO)

    assert r.adattato_da_segnale is True
    assert [s.experience_id for s in r.stops] == ["exp-chiusa", "exp-sconosciuta"]
    assert r.stops[1].reason == reason_stub
