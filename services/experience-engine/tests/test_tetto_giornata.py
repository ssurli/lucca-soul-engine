"""Tetto della giornata (wave "adattamento", decisione di prodotto 1).

Un itinerario è una sessione nella stessa giornata: nessuna tappa finisce
oltre le 24:00.
- composizione: budget effettivo = min(dichiarato, minuti alla mezzanotte da
  `signal.ora`), per la selezione e per le due code; le tappe che non entrano
  per il tetto NON vanno in `tappe_escluse`;
- adattamento: le tappe che con gli arrivi ricalcolati da `signal.ora`
  finirebbero oltre le 24:00 escono e vanno in `tappe_escluse` con esito
  `TAGLIATA_TETTO_GIORNATA`, anche se l'itinerario non ha budget.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
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
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

FRASE_TETTO = "Non c'è più tempo oggi per questa tappa: la giornata finisce a mezzanotte."


def _minuti(t: time) -> int:
    return t.hour * 60 + t.minute


def _verifica_entro_mezzanotte(it: Itinerary, ora_inizio: time) -> None:
    """Ogni tappa arriva dopo l'inizio (nessun riavvolgimento a 00:00) e
    finisce entro le 24:00."""
    fine_prec = _minuti(ora_inizio)
    for s in it.stops:
        arrivo = _minuti(s.arrivo)
        assert arrivo >= fine_prec, f"riavvolto oltre mezzanotte: {s.experience_id} {s.arrivo}"
        assert arrivo + s.durata_min <= 24 * 60, f"oltre le 24:00: {s.experience_id} {s.arrivo}"
        fine_prec = arrivo + s.durata_min


def _profilo(tempo: int) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=tempo,
    )


def _compose_seed(ora: time, tempo: int) -> Itinerary:
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora)
    ctx = VisitorContext(person_id="p", profile=_profilo(tempo), signal=signal)
    cands = SeedCandidateSource().candidates(ctx)
    return compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)


# ---------------------------------------------------------------------------
# Composizione
# ---------------------------------------------------------------------------


def test_compose_alle_22_con_240_minuti_si_ferma_a_mezzanotte() -> None:
    it = _compose_seed(time(22, 0), 240)
    assert it.stops, "almeno una tappa entra in 120 minuti"
    _verifica_entro_mezzanotte(it, time(22, 0))
    assert it.tempo_disponibile_min == 240
    assert it.tempo_effettivo_min == 120
    assert it.tappe_escluse == []  # in composizione nulla è "escluso": mai proposto
    assert it.adattato_da_segnale is False
    assert all(s.esito_adattamento is None for s in it.stops)


def test_compose_non_vacuita_lo_stesso_budget_di_giorno_supera_120_minuti() -> None:
    """Senza tetto lo stesso profilo usa più di 120 minuti: il taglio delle
    22:00 è dovuto al tetto, non a un itinerario già corto."""
    giorno = _compose_seed(time(10, 0), 240)
    sera = _compose_seed(time(22, 0), 240)
    fine_giorno = _minuti(giorno.stops[-1].arrivo) + giorno.stops[-1].durata_min
    assert fine_giorno - _minuti(time(10, 0)) > 120
    assert giorno.tempo_effettivo_min == 240
    assert len(sera.stops) < len(giorno.stops)


def test_compose_budget_dichiarato_minore_del_tetto_resta_il_dichiarato() -> None:
    it = _compose_seed(time(10, 0), 90)
    assert it.tempo_disponibile_min == 90
    assert it.tempo_effettivo_min == 90


def test_compose_budget_zero_itinerario_senza_budget() -> None:
    """`EmotionalProfile` ammette 0, `Itinerary.tempo_disponibile_min` no (gt=0):
    l'itinerario resta senza budget invece di fallire la validazione."""
    it = _compose_seed(time(10, 0), 0)
    assert it.stops == []
    assert it.tempo_disponibile_min is None
    assert it.tempo_effettivo_min is None


# --- Le due code rispettano il tetto ----------------------------------------

_ULTIMA = date(2026, 3, 2)
_DATA_VISITA = _ULTIMA + timedelta(days=7)


def _candidato(durata: int) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id="exp-a", titolo="Tappa A", place_id="luogo-a", temi=["arte"],
            durata_min=durata, al_chiuso=True, accessibile=True,
        ),
        place_nome="Luogo A",
        connessioni=['Evoca il tema "Arte".'],
    )


def _fluttuante(id_: str) -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id=id_, descrizione="un violinista suona in piazza", temi=["musica"],
        place_id="luogo-a", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _evento() -> EventoPromosso:
    return EventoPromosso(
        id="evento-luogo-a-musica", place_id="luogo-a", temi=["musica"],
        ultima_occorrenza=_ULTIMA, cadenza_giorni=7.0,
    )


def _compose_code(ora: time, tempo: int, fluttuanti: list[SegnaleFluttuante]) -> Itinerary:
    profilo = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=tempo,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora,
        data=_DATA_VISITA, eventi_attivi=fluttuanti,
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=signal)
    return compose_itinerary(
        ctx, [_candidato(60)], compose_reason, eventi_promossi=[_evento()],
        vocabolario=VOCABOLARIO,
    )


def test_code_fluttuanti_ed_eventi_rispettano_il_tetto() -> None:
    """22:00, budget 240, tetto 120. Permanente 60, poi fluttuante 1 (+25 =
    85), fluttuante 2 (+25 = 110), evento (+25 = 135 > 120): l'evento resta
    fuori SOLO per il tetto (il budget dichiarato lo ammetterebbe)."""
    fl = [_fluttuante("v1"), _fluttuante("v2")]
    sera = _compose_code(time(22, 0), 240, fl)
    assert [s.experience_id for s in sera.stops] == [
        "exp-a", "fluttuante-v1", "fluttuante-v2",
    ]
    _verifica_entro_mezzanotte(sera, time(22, 0))
    assert sera.tempo_effettivo_min == 120
    # Controllo: di giorno, con lo stesso budget, l'evento entra.
    giorno = _compose_code(time(10, 0), 240, fl)
    assert [s.experience_id for s in giorno.stops][-1] == "evento-luogo-a-musica"


def test_code_al_confine_finiscono_esattamente_a_mezzanotte() -> None:
    """Tetto 110 (22:10): permanente 60 + due fluttuanti = 110, l'ultima
    tappa finisce alle 24:00 esatte (ammesso)."""
    it = _compose_code(time(22, 10), 240, [_fluttuante("v1"), _fluttuante("v2")])
    assert [s.experience_id for s in it.stops] == ["exp-a", "fluttuante-v1", "fluttuante-v2"]
    _verifica_entro_mezzanotte(it, time(22, 10))
    ultima = it.stops[-1]
    assert _minuti(ultima.arrivo) + ultima.durata_min == 24 * 60


# ---------------------------------------------------------------------------
# Adattamento
# ---------------------------------------------------------------------------


def test_adapt_tardi_taglia_le_tappe_oltre_mezzanotte() -> None:
    base = _compose_seed(time(10, 0), 240)
    assert len(base.stops) >= 3
    ctx = VisitorContext(
        person_id="p", profile=_profilo(240),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    cands = SeedCandidateSource().candidates(ctx)
    tardi = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(22, 0))

    adattato = adapt_itinerary(
        base, tardi, cands, None, compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )

    _verifica_entro_mezzanotte(adattato, time(22, 0))
    assert adattato.stops[0].arrivo == time(22, 0)  # arrivi ricalcolati da signal.ora
    assert adattato.adattato_da_segnale is True
    rimaste = [s.experience_id for s in adattato.stops]
    tolte = [t.experience_id for t in adattato.tappe_escluse]
    assert tolte, "qualche tappa deve uscire per il tetto"
    assert rimaste + tolte == [s.experience_id for s in base.stops]  # coda, ordine intatto
    for t in adattato.tappe_escluse:
        assert t.esito is EsitoAdattamento.TAGLIATA_TETTO_GIORNATA
        assert t.reason == FRASE_TETTO
    assert all(s.esito_adattamento is EsitoAdattamento.NON_TOCCATA for s in adattato.stops)
    # Il budget è ricopiato invariato.
    assert adattato.tempo_disponibile_min == 240
    assert adattato.tempo_effettivo_min == 240


def test_adapt_tetto_vale_anche_senza_budget() -> None:
    stops = [
        ItineraryStop(experience_id=f"x-{i}", arrivo=time(10, 0), durata_min=50, reason="motivo.")
        for i in range(4)
    ]
    it = Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))
    assert it.tempo_effettivo_min is None
    # 23:00: 60 minuti. x-0 (50) entra; x-1 (10 + 50) no.
    tardi = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(23, 0))
    adattato = adapt_itinerary(it, tardi, [], None, vocabolario=VOCABOLARIO)
    assert [s.experience_id for s in adattato.stops] == ["x-0"]
    assert [(t.experience_id, t.esito) for t in adattato.tappe_escluse] == [
        ("x-1", EsitoAdattamento.TAGLIATA_TETTO_GIORNATA),
        ("x-2", EsitoAdattamento.TAGLIATA_TETTO_GIORNATA),
        ("x-3", EsitoAdattamento.TAGLIATA_TETTO_GIORNATA),
    ]
    assert adattato.adattato_da_segnale is True
    assert adattato.tempo_disponibile_min is None
    assert adattato.tempo_effettivo_min is None


def test_adapt_nessun_taglio_se_tutto_sta_nella_giornata() -> None:
    stops = [
        ItineraryStop(experience_id="x-0", arrivo=time(10, 0), durata_min=50, reason="motivo.")
    ]
    it = Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))
    # 23:10: 50 minuti esatti, la tappa finisce alle 24:00.
    segnale = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(23, 10))
    adattato = adapt_itinerary(it, segnale, [], None, vocabolario=VOCABOLARIO)
    assert adattato.tappe_escluse == []
    assert adattato.adattato_da_segnale is False
    assert adattato.stops[0].arrivo == time(10, 0)  # nulla tagliato: arrivi invariati
