"""Taglio per stanchezza: il prefisso il cui tempo è il più vicino ai 2/3.

Regola (`_taglia_per_stanchezza`, ondata 3, compito 1):
- `limite` = int(2/3 * somma delle durate dell'itinerario RICEVUTO);
- il tempo è sommato sulle durate delle tappe correnti (dopo le sostituzioni);
- la tappa successiva resta se il totale che la include è strettamente più
  vicino al limite di quello che la esclude; a parità si esclude;
- al primo escluso ci si ferma (prefisso);
- almeno una tappa resta sempre, anche se da sola supera il limite.
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
from experience_engine.engine import _CandidatoConReason, _taglia_per_stanchezza
from graph.seed_lucca import VOCABOLARIO


def _cand(id_: str, durata: int) -> _CandidatoConReason:
    return _CandidatoConReason(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
            durata_min=durata, al_chiuso=True, accessibile=True,
        ),
        place_nome=f"Piazza {id_}",
        connessioni=[],
        id_originale=id_,
    )


def _itinerario(stops: list[tuple[str, int]]) -> Itinerary:
    out: list[ItineraryStop] = []
    minuti = 10 * 60
    for i, (id_, durata) in enumerate(stops):
        if i > 0:
            minuti += 10
        out.append(
            ItineraryStop(
                experience_id=id_, arrivo=time(minuti // 60, minuti % 60),
                durata_min=durata, reason="Motivo originale.",
            )
        )
        minuti += durata
    return Itinerary(person_id="p", stops=out, generated_at=datetime(2026, 1, 1))


def _ids(cands: list[_CandidatoConReason]) -> list[str]:
    return [c.experience.id for c in cands]


def test_caso_reale_curioso_pioggia_e_stanchezza_tiene_tre_tappe() -> None:
    # Durate del caso verificato: itinerario ricevuto 25+30+40+35 = 130,
    # limite int(86.67) = 86. La prima tappa è già sostituita (20 min): il
    # limite resta sulle durate RICEVUTE, il tempo sulle correnti.
    ricevuto = _itinerario([("facciata", 25), ("frediano", 30), ("reparata", 40), ("duomo", 35)])
    correnti = [_cand("interno", 20), _cand("frediano", 30), _cand("reparata", 40),
                _cand("duomo", 35)]
    # 20 -> 50 -> 90 (|4| < |36|: resta) -> 125 (|39| >= |4|: fuori).
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["interno", "frediano", "reparata"]


def test_limite_sulle_durate_ricevute_non_sulle_correnti() -> None:
    # Ricevuto 60+60+60 = 180 -> limite 120. Correnti piu' corte (sostituzioni
    # da 30): 30, 60, 90 si avvicinano tutte a 120 -> restano tutte e tre.
    # Se il limite fosse sulle correnti (90 -> 60) la terza uscirebbe.
    ricevuto = _itinerario([("a", 60), ("b", 60), ("c", 60)])
    correnti = [_cand("a2", 30), _cand("b2", 30), _cand("c2", 30)]
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["a2", "b2", "c2"]


def test_parita_di_distanza_esclude() -> None:
    # Ricevuto 30+30+30 = 90 -> limite 60. Tempo 40 (prima tappa); la
    # seconda da 40 porta a 80: |80-60| = 20 = |40-60| -> esclusa.
    ricevuto = _itinerario([("a", 30), ("b", 30), ("c", 30)])
    correnti = [_cand("a", 40), _cand("b", 40), _cand("c", 10)]
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["a"]


def test_una_sola_tappa_resta() -> None:
    # Una tappa da 60: limite 40; da sola sarebbe a distanza 20, senza a 40.
    ricevuto = _itinerario([("a", 60)])
    assert _ids(_taglia_per_stanchezza(ricevuto, [_cand("a", 60)])) == ["a"]
    # Tappa da 1 minuto: limite 0, la regola la escluderebbe (|1| >= |0|):
    # resta comunque, almeno una tappa.
    ricevuto_breve = _itinerario([("b", 1)])
    assert _ids(_taglia_per_stanchezza(ricevuto_breve, [_cand("b", 1)])) == ["b"]


def test_prima_tappa_che_da_sola_supera_il_limite_resta_da_sola() -> None:
    # Ricevuto 30+30+30 = 90 -> limite 60. La prima corrente (sostituita) dura
    # 150: oltre il doppio del limite, la regola la escluderebbe (|150-60| = 90
    # >= |0-60| = 60), ma almeno una tappa resta: e solo lei.
    ricevuto = _itinerario([("a", 30), ("b", 30), ("c", 30)])
    correnti = [_cand("lunga", 150), _cand("b", 5), _cand("c", 5)]
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["lunga"]
    # Oltre il limite ma entro il doppio: la regola stessa la tiene (|100-60|
    # = 40 < 60), le successive allontanano ancora -> fuori.
    correnti = [_cand("lunga", 100), _cand("b", 5), _cand("c", 5)]
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["lunga"]


def test_prefisso_mai_salta_una_tappa_per_tenerne_una_dopo() -> None:
    # Ricevuto 40+40+40 = 120 -> limite 80. Seconda tappa troppo lunga
    # (40 -> 160: |80| >= |40|): esclusa; la terza da 30 porterebbe il
    # totale a 70 (piu' vicino a 80 di 40) ma dopo il primo escluso non
    # entra mai.
    ricevuto = _itinerario([("a", 40), ("b", 40), ("c", 40)])
    correnti = [_cand("a", 40), _cand("lunga", 120), _cand("corta", 30)]
    assert _ids(_taglia_per_stanchezza(ricevuto, correnti)) == ["a"]


def test_via_adapt_itinerary_esclusa_solo_la_coda() -> None:
    cands = [
        GraphCandidate(experience=c.experience, place_nome=c.place_nome, connessioni=[])
        for c in (_cand(i, d) for i, d in [("t0", 20), ("t1", 30), ("t2", 40), ("t3", 35)])
    ]
    ricevuto = _itinerario([("t0", 25), ("t1", 30), ("t2", 40), ("t3", 35)])
    stanco = Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0))
    r = adapt_itinerary(ricevuto, stanco, cands, None, vocabolario=VOCABOLARIO)
    # Ricevuto 130 -> limite 86; correnti (durate dei candidati) 20, 50, 90.
    assert [s.experience_id for s in r.stops] == ["t0", "t1", "t2"]
    assert [(t.experience_id, t.esito) for t in r.tappe_escluse] == [
        ("t3", EsitoAdattamento.TAGLIATA_STANCHEZZA),
    ]
    assert r.adattato_da_segnale is True
