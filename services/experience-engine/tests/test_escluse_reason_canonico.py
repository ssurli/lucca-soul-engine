"""Il `reason` delle tappe escluse è SEMPRE quello del motore (gate etico,
wave "adattamento", punto 3).

Le `tappe_escluse` arrivano dal client dentro l'itinerario da adattare: il
loro `reason` è testo libero. Il motore lo rigenera dall'esito con l'unica
funzione delle frasi, sia quando l'adattamento cambia l'itinerario sia quando
non cambia nulla. Deduplicazione e ordine restano quelli di prima.
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
    TappaEsclusa,
)
from experience_engine import adapt_itinerary
from graph.seed_lucca import VOCABOLARIO

FRASE_STANCHEZZA = "Tolta per la stanchezza: meglio una giornata più leggera."
FRASE_TETTO = "Non c'è più tempo oggi per questa tappa: la giornata finisce a mezzanotte."
TESTO_CLIENT = "testo del client"


def _cand(id_: str, durata: int = 60) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
            durata_min=durata, al_chiuso=True, accessibile=True,
        ),
        place_nome=f"Piazza {id_}",
        connessioni=[],
    )


def _itinerario(ids: list[str], escluse: list[TappaEsclusa]) -> Itinerary:
    stops: list[ItineraryStop] = []
    minuti = 10 * 60
    for i, id_ in enumerate(ids):
        if i > 0:
            minuti += 10
        stops.append(
            ItineraryStop(
                experience_id=id_, arrivo=time(minuti // 60, minuti % 60),
                durata_min=60, reason="Motivo originale.",
            )
        )
        minuti += 60
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=300, tempo_effettivo_min=300, tappe_escluse=escluse,
    )


def _escluse_dal_client() -> list[TappaEsclusa]:
    return [
        TappaEsclusa(
            experience_id="z-stanca", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA,
            reason=TESTO_CLIENT,
        ),
        TappaEsclusa(
            experience_id="z-tardi", esito=EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
            reason="Sponsorizzata: compra qui!",
        ),
    ]


def test_adattamento_senza_cambiamenti_rigenera_il_reason_delle_escluse() -> None:
    cands = [_cand("t0"), _cand("t1")]
    it = _itinerario(["t0", "t1"], _escluse_dal_client())
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, cands, None, vocabolario=VOCABOLARIO)

    # Nessuna sostituzione né taglio: solo tappe non toccate.
    assert r.adattato_da_segnale is False
    assert all(s.esito_adattamento is EsitoAdattamento.NON_TOCCATA for s in r.stops)
    # Ordine e voci invariati, testo del motore.
    assert r.tappe_escluse == [
        TappaEsclusa(
            experience_id="z-stanca", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA,
            reason=FRASE_STANCHEZZA,
        ),
        TappaEsclusa(
            experience_id="z-tardi", esito=EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
            reason=FRASE_TETTO,
        ),
    ]


def test_adattamento_con_taglio_rigenera_anche_le_escluse_ricevute() -> None:
    cands = [_cand(f"t{i}") for i in range(3)]
    it = _itinerario(["t0", "t1", "t2"], _escluse_dal_client())
    stanco = Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0))

    r = adapt_itinerary(it, stanco, cands, None, vocabolario=VOCABOLARIO)

    assert r.adattato_da_segnale is True
    assert [s.experience_id for s in r.stops] == ["t0", "t1"]
    # Precedenti in testa nell'ordine ricevuto, la nuova in fondo.
    assert [(t.experience_id, t.esito, t.reason) for t in r.tappe_escluse] == [
        ("z-stanca", EsitoAdattamento.TAGLIATA_STANCHEZZA, FRASE_STANCHEZZA),
        ("z-tardi", EsitoAdattamento.TAGLIATA_TETTO_GIORNATA, FRASE_TETTO),
        ("t2", EsitoAdattamento.TAGLIATA_STANCHEZZA, FRASE_STANCHEZZA),
    ]
    assert all(TESTO_CLIENT not in t.reason for t in r.tappe_escluse)


def test_duplicato_ricevuto_resta_una_voce_col_reason_del_motore() -> None:
    cands = [_cand("t0")]
    doppie = [
        TappaEsclusa(
            experience_id="z", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA, reason="primo",
        ),
        TappaEsclusa(
            experience_id="z", esito=EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
            reason=TESTO_CLIENT,
        ),
    ]
    it = _itinerario(["t0"], doppie)
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, sereno, cands, None, vocabolario=VOCABOLARIO)

    # Vince la più recente (deduplicazione invariata), testo rigenerato.
    assert r.tappe_escluse == [
        TappaEsclusa(
            experience_id="z", esito=EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
            reason=FRASE_TETTO,
        )
    ]
