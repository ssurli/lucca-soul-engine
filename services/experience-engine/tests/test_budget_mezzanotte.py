"""Budget di tempo oltre la mezzanotte (regressione).

Le tappe in coda (segnali fluttuanti, eventi promossi) ricalcolano il budget
usato da `stops[-1].arrivo`. Se l'ultima tappa permanente arriva DOPO le 00:00
il calcolo sul solo `time` (senza data) diventa negativo e le tappe in coda
vengono aggiunte oltre `profile.tempo_disponibile_min`.

Il totale (durate + trasferimenti) e' ricostruito qui con `datetime` e rollover
di giorno, indipendentemente dall'aritmetica del motore.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
)
from experience_engine import compose_itinerary
from experience_engine.rules import (
    DURATA_TAPPA_EVENTO_MIN,
    DURATA_TAPPA_FLUTTUANTE_MIN,
    TEMPO_TRASFERIMENTO_DEFAULT_MIN,
)
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import compose_reason

ORA_INIZIO = time(20, 0)
TEMPO_DISPONIBILE = 300
ULTIMA = date(2026, 3, 2)
DATA_VISITA = ULTIMA + timedelta(days=7)  # dentro la finestra (cadenza 7)

# Durate: 120 + (10+120) + (10+40) = 300 esatti. La terza tappa arriva alle 00:20.
_DURATE = {"exp-a": 120, "exp-b": 120, "exp-c": 40}


def _profilo() -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=TEMPO_DISPONIBILE,
    )


def _candidati() -> list[GraphCandidate]:
    return [
        GraphCandidate(
            experience=ExperienceNode(
                id=id_, titolo=f"Tappa {id_}", place_id=f"luogo-{id_}", temi=["arte"],
                durata_min=durata, al_chiuso=True, accessibile=True,
            ),
            place_nome=f"Luogo {id_}",
            connessioni=['Evoca il tema "Arte".'],
        )
        for id_, durata in _DURATE.items()
    ]


def _fluttuante() -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza", temi=["musica"],
        place_id="luogo-exp-a", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _evento() -> EventoPromosso:
    return EventoPromosso(
        id="evento-luogo-exp-a-musica", place_id="luogo-exp-a", temi=["musica"],
        ultima_occorrenza=ULTIMA, cadenza_giorni=7.0,
    )


def _compose(*, fluttuanti: list[SegnaleFluttuante], eventi: list[EventoPromosso]) -> Itinerary:
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA_INIZIO,
        data=DATA_VISITA, eventi_attivi=fluttuanti,
    )
    ctx = VisitorContext(person_id="p", profile=_profilo(), signal=signal)
    return compose_itinerary(
        ctx, _candidati(), compose_reason, eventi_promossi=eventi, vocabolario=VOCABOLARIO,
    )


def _minuti_totali_indipendenti(it: Itinerary, ora_inizio: time) -> int:
    """Durate + trasferimenti, ricostruiti con datetime e rollover di giorno."""
    giorno = date(2000, 1, 1)
    fine_prec: datetime | None = None
    totale = 0
    for stop in it.stops:
        arrivo = datetime.combine(giorno, stop.arrivo)
        if fine_prec is None:
            assert stop.arrivo == ora_inizio, "la prima tappa parte da signal.ora"
        else:
            while arrivo < fine_prec:
                arrivo += timedelta(days=1)
            totale += int((arrivo - fine_prec).total_seconds() // 60)
        totale += stop.durata_min
        fine_prec = arrivo + timedelta(minutes=stop.durata_min)
    return totale


def _verifica_scenario_attraversa_mezzanotte(it: Itinerary, n_in_coda: int) -> None:
    permanenti = [s for s in it.stops if s.experience_id in _DURATE]
    assert [s.experience_id for s in permanenti] == ["exp-a", "exp-b", "exp-c"]
    # Sanita': l'ultima tappa permanente arriva dopo la mezzanotte (orario < ora_inizio).
    assert permanenti[-1].arrivo < ORA_INIZIO
    assert permanenti[-1].arrivo == time(0, 20)
    # Sanita': il budget residuo e' minore del costo di una tappa in coda.
    usati = _minuti_totali_indipendenti(Itinerary(
        person_id="p", stops=permanenti, generated_at=it.generated_at,
        adattato_da_segnale=False,
    ), ORA_INIZIO)
    residuo = TEMPO_DISPONIBILE - usati
    assert residuo < TEMPO_TRASFERIMENTO_DEFAULT_MIN + min(
        DURATA_TAPPA_FLUTTUANTE_MIN, DURATA_TAPPA_EVENTO_MIN
    )
    assert len(it.stops) - len(permanenti) == n_in_coda


def test_fluttuante_non_sfora_il_budget_oltre_mezzanotte() -> None:
    it = _compose(fluttuanti=[_fluttuante()], eventi=[])
    _verifica_scenario_attraversa_mezzanotte(it, n_in_coda=len(it.stops) - 3)
    totale = _minuti_totali_indipendenti(it, ORA_INIZIO)
    assert totale <= TEMPO_DISPONIBILE, (
        f"budget sforato: {totale} min > {TEMPO_DISPONIBILE} "
        f"({[(s.experience_id, s.arrivo, s.durata_min) for s in it.stops]})"
    )


def test_evento_promosso_non_sfora_il_budget_oltre_mezzanotte() -> None:
    it = _compose(fluttuanti=[], eventi=[_evento()])
    _verifica_scenario_attraversa_mezzanotte(it, n_in_coda=len(it.stops) - 3)
    totale = _minuti_totali_indipendenti(it, ORA_INIZIO)
    assert totale <= TEMPO_DISPONIBILE, (
        f"budget sforato: {totale} min > {TEMPO_DISPONIBILE} "
        f"({[(s.experience_id, s.arrivo, s.durata_min) for s in it.stops]})"
    )


# ---------------------------------------------------------------------------
# Budget CONDIVISO tra le due code (fluttuante poi evento) e equivalenza
# senza mezzanotte. Costo di ogni tappa in coda = trasferimento (10) + 15 = 25.
# Permanenti = 300 min esatti.
# ---------------------------------------------------------------------------

_COSTO_CODA = TEMPO_TRASFERIMENTO_DEFAULT_MIN + DURATA_TAPPA_FLUTTUANTE_MIN
_PERMANENTI_MIN = sum(_DURATE.values()) + 2 * TEMPO_TRASFERIMENTO_DEFAULT_MIN  # 300


def _compose_con(ora: time, tempo: int, *, con_fluttuante: bool, con_evento: bool) -> Itinerary:
    profilo = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=tempo,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora,
        data=DATA_VISITA, eventi_attivi=[_fluttuante()] if con_fluttuante else [],
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=signal)
    return compose_itinerary(
        ctx, _candidati(), compose_reason,
        eventi_promossi=[_evento()] if con_evento else [], vocabolario=VOCABOLARIO,
    )


def _ids_coda(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops if s.experience_id not in _DURATE]


def test_budget_condiviso_dopo_mezzanotte_una_sola_coda_entra() -> None:
    # Residuo 49 dopo le permanenti: entra il fluttuante (25), l'evento no (50 > 49).
    tempo = _PERMANENTI_MIN + 2 * _COSTO_CODA - 1
    it = _compose_con(ORA_INIZIO, tempo, con_fluttuante=True, con_evento=True)
    assert [s.experience_id for s in it.stops if s.experience_id in _DURATE] == list(_DURATE)
    assert [s for s in it.stops if s.experience_id in _DURATE][-1].arrivo == time(0, 20)
    assert _ids_coda(it) == ["fluttuante-violinista-1"]
    assert _minuti_totali_indipendenti(it, ORA_INIZIO) <= tempo


def test_budget_condiviso_dopo_mezzanotte_entrambe_le_code_al_limite() -> None:
    # Residuo esatto 50: entrano entrambe, fluttuante prima dell'evento.
    tempo = _PERMANENTI_MIN + 2 * _COSTO_CODA
    it = _compose_con(ORA_INIZIO, tempo, con_fluttuante=True, con_evento=True)
    assert _ids_coda(it) == ["fluttuante-violinista-1", _evento().id]
    assert _minuti_totali_indipendenti(it, ORA_INIZIO) == tempo


def test_budget_condiviso_dopo_mezzanotte_nessuna_coda_sotto_il_costo() -> None:
    tempo = _PERMANENTI_MIN + _COSTO_CODA - 1
    it = _compose_con(ORA_INIZIO, tempo, con_fluttuante=True, con_evento=True)
    assert _ids_coda(it) == []
    assert _minuti_totali_indipendenti(it, ORA_INIZIO) <= tempo


def test_senza_mezzanotte_equivalenza_stesse_code_a_budget_giusto_e_limite() -> None:
    # Partenza alle 09:00: nessun rollover, stesso comportamento atteso.
    ora = time(9, 0)
    casi = {
        _PERMANENTI_MIN + _COSTO_CODA - 1: [],
        _PERMANENTI_MIN + _COSTO_CODA: ["fluttuante-violinista-1"],
        _PERMANENTI_MIN + 2 * _COSTO_CODA - 1: ["fluttuante-violinista-1"],
        _PERMANENTI_MIN + 2 * _COSTO_CODA: ["fluttuante-violinista-1", _evento().id],
        _PERMANENTI_MIN + 3 * _COSTO_CODA: ["fluttuante-violinista-1", _evento().id],
    }
    for tempo, attese in casi.items():
        it = _compose_con(ora, tempo, con_fluttuante=True, con_evento=True)
        permanenti = [s for s in it.stops if s.experience_id in _DURATE]
        assert permanenti[-1].arrivo == time(13, 20)  # nessuna mezzanotte
        assert _ids_coda(it) == attese, f"tempo={tempo}"
        assert _minuti_totali_indipendenti(it, ora) <= tempo


def test_senza_mezzanotte_singole_code_al_limite() -> None:
    ora = time(9, 0)
    tempo = _PERMANENTI_MIN + _COSTO_CODA
    assert _ids_coda(_compose_con(ora, tempo, con_fluttuante=True, con_evento=False)) == [
        "fluttuante-violinista-1"
    ]
    assert _ids_coda(_compose_con(ora, tempo, con_fluttuante=False, con_evento=True)) == [
        _evento().id
    ]
    assert _ids_coda(_compose_con(ora, tempo - 1, con_fluttuante=False, con_evento=True)) == []


# ---------------------------------------------------------------------------
# Non-vacuita': le tappe in coda SONO pertinenti e, con budget ampio, compaiono.
# Senza questi, i test di sforamento passerebbero anche se la coda fosse vuota.
# ---------------------------------------------------------------------------


def test_scenario_fluttuante_ed_evento_sono_pertinenti() -> None:
    from experience_engine.rules import eventi_promossi_pertinenti, segnali_fluttuanti_pertinenti

    assert segnali_fluttuanti_pertinenti(
        [_fluttuante()], _profilo(), vocabolario=VOCABOLARIO
    ) != []
    assert eventi_promossi_pertinenti(
        [_evento()], _profilo(), DATA_VISITA, vocabolario=VOCABOLARIO
    ) != []


def test_controllo_budget_ampio_dopo_mezzanotte_le_code_compaiono() -> None:
    tempo = _PERMANENTI_MIN + 2 * _COSTO_CODA + 50  # 350
    it = _compose_con(ORA_INIZIO, tempo, con_fluttuante=True, con_evento=True)
    permanenti = [s for s in it.stops if s.experience_id in _DURATE]
    assert permanenti[-1].arrivo == time(0, 20)
    assert _ids_coda(it) == ["fluttuante-violinista-1", _evento().id]
    assert _minuti_totali_indipendenti(it, ORA_INIZIO) <= tempo
