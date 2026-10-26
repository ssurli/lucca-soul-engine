"""Accessibilità sulle tappe in coda (ondata 4, compito 5-quater).

Regola del committente: con `accessibilita_richiesta=True` NESSUNA tappa
fluttuante e NESSUN evento promosso entra (né `SegnaleFluttuante` né
`EventoPromosso` portano `accessibile`: fail-closed). Senza, comportamento
invariato. Ogni caso accessibile ha il gemello non accessibile con gli stessi
identici input, per dimostrare che il caso vuoto non è vuoto per altri motivi.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

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
from experience_engine import compose_itinerary, rules
from graph.seed_lucca import VOCABOLARIO
from rag.reasons import compose_reason

ULTIMA = date(2026, 3, 2)
DATA_VISITA = date(2026, 3, 9)  # ULTIMA + 7 giorni: in finestra con cadenza 7


def _profilo(accessibile: bool) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200, accessibilita_richiesta=accessibile,
    )


def _candidato() -> GraphCandidate:
    esperienza = ExperienceNode(
        id="exp-fisso", titolo="Facciata Barocca", place_id="luogo-fisso",
        temi=["arte"], durata_min=30, al_chiuso=False, accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Piazza Fissa", connessioni=['Evoca il tema "Arte".']
    )


def _segnale() -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza",
        temi=["musica"], place_id="luogo-fisso", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _evento() -> EventoPromosso:
    return EventoPromosso(
        id="evento-luogo-fisso-musica", place_id="luogo-fisso", temi=["musica"],
        ultima_occorrenza=ULTIMA, cadenza_giorni=7.0,
    )


def _compose(accessibile: bool, *, segnale: bool, evento: bool):
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        data=DATA_VISITA, eventi_attivi=[_segnale()] if segnale else [],
    )
    ctx = VisitorContext(person_id="p", profile=_profilo(accessibile), signal=signal)
    return compose_itinerary(
        ctx, [_candidato()], compose_reason,
        eventi_promossi=[_evento()] if evento else [],
        vocabolario=VOCABOLARIO,
    )


def _ids(it: Itinerary) -> list[str]:
    return [s.experience_id for s in it.stops]


def test_accessibile_nessuna_tappa_in_coda_e_permanenti_invariate() -> None:
    con_coda = _compose(True, segnale=True, evento=True)
    senza_coda = _compose(True, segnale=False, evento=False)
    assert _ids(con_coda) == ["exp-fisso"]
    assert con_coda.stops == senza_coda.stops  # permanenti identiche al caso senza segnale/evento


def test_non_accessibile_stesso_caso_tappa_fluttuante_e_evento_entrano() -> None:
    it = _compose(False, segnale=True, evento=True)
    ids = _ids(it)
    assert ids[0] == "exp-fisso"
    assert "fluttuante-violinista-1" in ids
    assert "evento-luogo-fisso-musica" in ids
    assert all(s.reason for s in it.stops)
    # le permanenti restano quelle del caso senza coda
    assert it.stops[0] == _compose(False, segnale=False, evento=False).stops[0]


def test_solo_segnale_accessibile_vs_non_accessibile() -> None:
    assert _ids(_compose(True, segnale=True, evento=False)) == ["exp-fisso"]
    assert "fluttuante-violinista-1" in _ids(_compose(False, segnale=True, evento=False))


def test_solo_evento_accessibile_vs_non_accessibile() -> None:
    assert _ids(_compose(True, segnale=False, evento=True)) == ["exp-fisso"]
    assert "evento-luogo-fisso-musica" in _ids(_compose(False, segnale=False, evento=True))


def test_funzioni_pure_segnali_fluttuanti() -> None:
    segnale = _segnale()
    assert rules.segnali_fluttuanti_pertinenti(
        [segnale], _profilo(True), vocabolario=VOCABOLARIO
    ) == []
    assert rules.segnali_fluttuanti_pertinenti(
        [segnale], _profilo(False), vocabolario=VOCABOLARIO
    ) == [segnale]


def test_funzioni_pure_eventi_promossi() -> None:
    evento = _evento()
    assert rules.eventi_promossi_pertinenti(
        [evento], _profilo(True), DATA_VISITA, vocabolario=VOCABOLARIO
    ) == []
    assert rules.eventi_promossi_pertinenti(
        [evento], _profilo(False), DATA_VISITA, vocabolario=VOCABOLARIO
    ) == [evento]
