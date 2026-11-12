"""L'affollamento in adattamento colpisce SOLO le esperienze all'aperto (correzione 1).

Regola: l'affollamento (> `SOGLIA_AFFOLLAMENTO_ADATTAMENTO` = 0.7) tocca solo
esperienze con `al_chiuso=False`, sia per la tappa da riscrivere
(`adapt_itinerary`) sia per il divieto sul sostituto (`_migliore_alternativa`):
una sala al chiuso in un luogo affollato non peggiora la calca in strada.

NON cambia il filtro duro di composizione (`rules.passa_filtri_statici`,
`>= SOGLIA_AFFOLLAMENTO_CRITICO` = 0.8): a 0.95 anche un'esperienza al chiuso e'
esclusa come sostituto. E' voluto: oltre la soglia critica il luogo non va
caricato di nuove visite, a prescindere da dove si svolgono.
Il valore che l'app usera' per la folla e' 0.75 (tra le due soglie).
"""

from __future__ import annotations

from datetime import datetime, time

from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
)
from experience_engine import adapt_itinerary
from experience_engine.engine import _migliore_alternativa
from experience_engine.rules import SOGLIA_AFFOLLAMENTO_ADATTAMENTO, SOGLIA_AFFOLLAMENTO_CRITICO
from graph.registro import carica_dataset
from graph.seed_lucca import VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

FOLLA = 0.75
PROFILO = EmotionalProfile(
    curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
    tempo_disponibile_min=600,
)
ORA = time(9, 0)


def _sereno(affollamento: dict[str, float]) -> Signal:
    return Signal(meteo="sereno", affollamento=affollamento, stanchezza=0.0, ora=ORA)


def _pioggia(affollamento: dict[str, float]) -> Signal:
    return Signal(meteo="pioggia", affollamento=affollamento, stanchezza=0.0, ora=ORA)


def _nodo(
    id_: str, place: str, *, al_chiuso: bool, temi: list[str] | None = None
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=place, temi=temi or [],
            durata_min=30, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome=f"Luogo {place}",
        connessioni=[],
    )


def _itinerario(ids: list[str]) -> Itinerary:
    stops = [
        ItineraryStop(
            experience_id=id_, arrivo=time(9 + 1 * i, 0), durata_min=30,
            reason="Motivo originale.",
        )
        for i, id_ in enumerate(ids)
    ]
    return Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))


def _adatta(ids: list[str], segnale: Signal, candidati: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(
        _itinerario(ids), segnale, candidati, PROFILO, compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )


def _migliore(
    candidati: list[GraphCandidate], segnale: Signal, *, solo_al_chiuso: bool = False,
    esclusi: set[str] | None = None,
) -> str | None:
    alt = _migliore_alternativa(
        candidates=candidati,
        signal=segnale,
        profile=PROFILO,
        esclusi=esclusi or set(),
        richiede_accessibile=False,
        solo_al_chiuso=solo_al_chiuso,
        max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
        arrivo_di=lambda _c: segnale.ora,
        vocabolario=VOCABOLARIO,
        prezzo_tolta=0.0,
        temi_tolta=[],
    )
    return None if alt is None else alt.experience.id


def test_la_folla_di_prova_sta_tra_le_due_soglie() -> None:
    assert SOGLIA_AFFOLLAMENTO_ADATTAMENTO < FOLLA < SOGLIA_AFFOLLAMENTO_CRITICO


# --- tappa da riscrivere -----------------------------------------------------


def test_tappa_al_chiuso_su_luogo_affollato_resta_non_toccata() -> None:
    chiusa = _nodo("chiusa", "p-chiuso", al_chiuso=True)
    alternativa = _nodo("alt", "p-altro", al_chiuso=True)
    r = _adatta(["chiusa"], _sereno({"p-chiuso": FOLLA}), [chiusa, alternativa])
    (stop,) = r.stops
    assert stop.experience_id == "chiusa"
    assert stop.esito_adattamento == EsitoAdattamento.NON_TOCCATA
    assert r.adattato_da_segnale is False


def test_tappa_all_aperto_su_luogo_affollato_viene_riscritta() -> None:
    aperta = _nodo("aperta", "p-aperto", al_chiuso=False)
    alternativa = _nodo("alt", "p-altro", al_chiuso=False)
    r = _adatta(["aperta"], _sereno({"p-aperto": FOLLA}), [aperta, alternativa])
    (stop,) = r.stops
    assert stop.experience_id == "alt"
    assert stop.esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_tappa_all_aperto_su_luogo_affollato_senza_alternativa_mai_non_toccata() -> None:
    aperta = _nodo("aperta", "p-aperto", al_chiuso=False)
    r = _adatta(["aperta"], _sereno({"p-aperto": FOLLA}), [aperta])
    (stop,) = r.stops
    assert stop.experience_id == "aperta"
    assert stop.esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


# --- divieto sul sostituto ---------------------------------------------------


def test_sostituto_al_chiuso_su_luogo_affollato_e_ammesso() -> None:
    chiuso = _nodo("chiuso", "p-folla", al_chiuso=True)
    assert _migliore([chiuso], _sereno({"p-folla": FOLLA})) == "chiuso"


def test_sostituto_all_aperto_su_luogo_affollato_non_e_ammesso() -> None:
    aperto = _nodo("aperto", "p-folla", al_chiuso=False)
    assert _migliore([aperto], _sereno({"p-folla": FOLLA})) is None


def test_adapt_sostituisce_con_un_chiuso_in_luogo_affollato_e_scarta_l_aperto() -> None:
    aperta = _nodo("aperta", "p-aperto", al_chiuso=False)
    chiuso_folla = _nodo("chiuso-folla", "p-folla", al_chiuso=True)
    aperto_folla = _nodo("aperto-folla", "p-folla2", al_chiuso=False)
    segnale = _sereno({"p-aperto": FOLLA, "p-folla": FOLLA, "p-folla2": FOLLA})
    r = _adatta(["aperta"], segnale, [aperta, chiuso_folla, aperto_folla])
    (stop,) = r.stops
    assert stop.experience_id == "chiuso-folla"
    assert stop.esito_adattamento == EsitoAdattamento.SOSTITUITA


# --- pioggia + folla su San Michele in Foro (dataset del seed) ---------------


def _seed() -> dict[str, GraphCandidate]:
    ctx = VisitorContext(person_id="p", profile=PROFILO, signal=_pioggia({}))
    candidati = SeedCandidateSource(carica_dataset(None)).candidates(ctx)
    return {c.experience.id: c for c in candidati}


def test_seed_i_due_nodi_di_san_michele_hanno_il_flag_atteso() -> None:
    """Guardia dello scenario: se il seed cambia, questo test lo dice."""
    seed = _seed()
    facciata = seed["exp-facciata-san-michele"].experience
    interno = seed["exp-interno-san-michele"].experience
    assert facciata.place_id == interno.place_id == "san-michele-in-foro"
    assert facciata.al_chiuso is False
    assert interno.al_chiuso is True


def test_seed_pioggia_e_folla_l_interno_sostituisce_la_facciata() -> None:
    seed = _seed()
    facciata = seed["exp-facciata-san-michele"]
    interno = seed["exp-interno-san-michele"]
    segnale = _pioggia({"san-michele-in-foro": FOLLA})
    # Il sostituto ammesso: l'interno (al chiuso) e' il migliore quando e' l'unico.
    assert _migliore([interno], segnale, solo_al_chiuso=True) == interno.experience.id
    # E la facciata, all'aperto, no: sotto la pioggia come per la folla.
    assert _migliore([facciata], segnale, solo_al_chiuso=True) is None
    r = _adatta(
        ["exp-facciata-san-michele"], segnale, [facciata, interno],
    )
    (stop,) = r.stops
    assert stop.experience_id == "exp-interno-san-michele"
    assert stop.esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_seed_pioggia_e_folla_la_facciata_non_resta_all_aperto() -> None:
    """Con tutto il seed come candidati la facciata e' sostituita da una tappa
    AL CHIUSO (la pioggia da sola lo impone); la folla non cambia questa regola."""
    seed = _seed()
    segnale = _pioggia({"san-michele-in-foro": FOLLA})
    r = _adatta(["exp-facciata-san-michele"], segnale, list(seed.values()))
    (stop,) = r.stops
    assert stop.experience_id != "exp-facciata-san-michele"
    assert stop.esito_adattamento == EsitoAdattamento.SOSTITUITA
    assert seed[stop.experience_id].experience.al_chiuso is True


def test_seed_a_095_l_interno_resta_escluso_filtro_duro_invariato() -> None:
    """VOLUTO: a 0.95 (>= soglia critica 0.8) `rules.passa_filtri_statici` esclude
    anche l'esperienza al chiuso. La correzione tocca solo la fascia 0.7-0.8."""
    seed = _seed()
    facciata = seed["exp-facciata-san-michele"]
    interno = seed["exp-interno-san-michele"]
    segnale = _pioggia({"san-michele-in-foro": 0.95})
    assert _migliore([interno], segnale, solo_al_chiuso=True) is None
    r = _adatta(["exp-facciata-san-michele"], segnale, [facciata, interno])
    (stop,) = r.stops
    assert stop.experience_id == "exp-facciata-san-michele"
    assert stop.esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
