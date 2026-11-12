"""`ItineraryStop.dimostrativa`: sola presentazione, copiata dal candidato corrente.

- composizione: True solo per la tappa di una bottega dimostrativa; tappe
  fluttuanti ed eventi promossi False;
- adattamento: il valore e' RICALCOLATO dal candidato corrente (sia nel ramo
  senza cambi sia in quello con ricostruzione), mai preso dalla richiesta;
  uno stub (candidato sconosciuto) e' False; una tappa sostituita prende il
  valore del sostituto.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import compose_reason

SABATO = date(2026, 12, 12)


def _sereno() -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=SABATO)


def _pioggia() -> Signal:
    return Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=SABATO)


def _cand(id_: str, *, dimostrativo: bool = False, al_chiuso: bool = True) -> GraphCandidate:
    esperienza = ExperienceNode(
        id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
        durata_min=60, al_chiuso=al_chiuso, accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome=f"Piazza {id_}", connessioni=[],
        partner_dimostrativo=dimostrativo,
    )


def _stop(id_: str, arrivo: time, *, dimostrativa: bool = False) -> ItineraryStop:
    return ItineraryStop(
        experience_id=id_, arrivo=arrivo, durata_min=60, reason="Motivo originale.",
        dimostrativa=dimostrativa,
    )


def _itinerario(stops: list[ItineraryStop]) -> Itinerary:
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=300, tempo_effettivo_min=300,
    )


def _per_id(it: Itinerary) -> dict[str, bool]:
    return {s.experience_id: s.dimostrativa for s in it.stops}


def _adatta(it: Itinerary, signal: Signal, cands: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(it, signal, cands, None, vocabolario=VOCABOLARIO)


# ---------------------------------------------------------------------------
# Composizione
# ---------------------------------------------------------------------------


def test_composizione_bottega_true_tappa_normale_false() -> None:
    profilo = EmotionalProfile(
        curiosita=0.9, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=300,
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=_sereno())
    cands = [_cand("normale"), _cand("bottega", dimostrativo=True)]
    it = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)
    assert _per_id(it) == {"normale": False, "bottega": True}


def test_composizione_fluttuante_ed_evento_promosso_false() -> None:
    esperienza = ExperienceNode(
        id="exp-arte", titolo="Una visita d'arte", place_id="luogo-fisso",
        temi=["arte", "musica", "storia"], durata_min=30, al_chiuso=True, accessibile=True,
    )
    cand = GraphCandidate(
        experience=esperienza, place_nome="Piazza fissa", connessioni=[],
        partner_dimostrativo=True,
    )
    fluttuante = SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza",
        temi=["musica"], place_id="luogo-fisso", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    evento = EventoPromosso(
        id="evento-luogo-fisso-musica", place_id="luogo-fisso", temi=["musica"],
        ultima_occorrenza=date(2026, 12, 5), cadenza_giorni=7.0,
    )
    profilo = EmotionalProfile(
        curiosita=0.9, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=300,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        data=SABATO, eventi_attivi=[fluttuante],
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=signal)
    it = compose_itinerary(
        ctx, [cand], compose_reason, eventi_promossi=[evento], vocabolario=VOCABOLARIO
    )
    assert _per_id(it) == {
        "exp-arte": True,
        "fluttuante-violinista-1": False,
        "evento-luogo-fisso-musica": False,
    }
    # In adattamento fluttuante ed evento restano stub (False); la tappa fissa
    # e' ricalcolata dal candidato.
    r = adapt_itinerary(it, _sereno(), [cand], profilo, vocabolario=VOCABOLARIO)
    assert _per_id(r) == _per_id(it)


# ---------------------------------------------------------------------------
# Adattamento: mai dalla richiesta
# ---------------------------------------------------------------------------


def test_adattamento_senza_cambi_richiesta_falsa_su_bottega_esce_true() -> None:
    cands = [_cand("t0"), _cand("bottega", dimostrativo=True)]
    it = _itinerario([_stop("t0", time(10, 0)), _stop("bottega", time(11, 10))])  # False
    r = _adatta(it, _sereno(), cands)
    assert r.adattato_da_segnale is False  # ramo model_copy
    assert _per_id(r) == {"t0": False, "bottega": True}


def test_adattamento_senza_cambi_true_falso_su_tappa_normale_esce_false() -> None:
    cands = [_cand("t0"), _cand("bottega", dimostrativo=True)]
    it = _itinerario([
        _stop("t0", time(10, 0), dimostrativa=True),
        _stop("bottega", time(11, 10), dimostrativa=True),
    ])
    r = _adatta(it, _sereno(), cands)
    assert r.adattato_da_segnale is False
    assert _per_id(r) == {"t0": False, "bottega": True}


def test_adattamento_con_ricostruzione_richiesta_falsa_su_bottega_esce_true() -> None:
    """Pioggia su `aperta` (all'aperto) -> sostituita da `alt`; la bottega, nello
    stesso itinerario, e' ricostruita e deve uscire True anche se arrivata False."""
    cands = [
        _cand("aperta", al_chiuso=False), _cand("alt"),
        _cand("bottega", dimostrativo=True),
    ]
    it = _itinerario([_stop("aperta", time(10, 0)), _stop("bottega", time(11, 10))])
    r = _adatta(it, _pioggia(), cands)
    assert r.adattato_da_segnale is True  # ramo _ricostruisci_stops
    per_id = _per_id(r)
    assert "aperta" not in per_id
    assert per_id["bottega"] is True


def test_adattamento_con_ricostruzione_true_falso_su_tappa_normale_esce_false() -> None:
    cands = [_cand("aperta", al_chiuso=False), _cand("alt"), _cand("t1")]
    it = _itinerario([
        _stop("aperta", time(10, 0), dimostrativa=True),
        _stop("t1", time(11, 10), dimostrativa=True),
    ])
    r = _adatta(it, _pioggia(), cands)
    assert r.adattato_da_segnale is True
    assert set(_per_id(r).values()) == {False}


def test_tappa_sostituita_prende_il_valore_del_sostituto() -> None:
    cands = [_cand("aperta", al_chiuso=False), _cand("alt-bottega", dimostrativo=True)]
    it = _itinerario([_stop("aperta", time(10, 0), dimostrativa=False)])
    r = _adatta(it, _pioggia(), cands)
    assert _per_id(r) == {"alt-bottega": True}
    # Specularmente: la bottega all'aperto sostituita da un candidato normale -> False.
    cands2 = [_cand("aperta-b", dimostrativo=True, al_chiuso=False), _cand("alt")]
    it2 = _itinerario([_stop("aperta-b", time(10, 0), dimostrativa=True)])
    r2 = _adatta(it2, _pioggia(), cands2)
    assert _per_id(r2) == {"alt": False}


def test_stub_sconosciuto_con_true_esce_false_in_entrambi_i_rami() -> None:
    cands = [_cand("t0")]
    it = _itinerario([
        _stop("t0", time(10, 0)),
        _stop("ignota-1", time(11, 10), dimostrativa=True),
    ])
    r = _adatta(it, _sereno(), cands)
    assert r.adattato_da_segnale is False
    assert _per_id(r) == {"t0": False, "ignota-1": False}

    cands2 = [_cand("t0", al_chiuso=False), _cand("alt")]
    r2 = _adatta(it, _pioggia(), cands2)
    assert r2.adattato_da_segnale is True
    assert _per_id(r2) == {"alt": False, "ignota-1": False}
