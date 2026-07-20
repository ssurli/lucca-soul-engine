"""Test di `intelligence_index.repository` — `InMemoryBehaviorEventSource`
(percorso principale dei test) e verifiche STATICHE di
`PostgresBehaviorEventSource` (nessun Postgres reale in questo ambiente,
stesso approccio di `services/graph/tests/test_source.py` per
`Neo4jCandidateSource`: import, struttura del `Protocol`, DSN passato al
costruttore)."""

from __future__ import annotations

from datetime import UTC, datetime

from contracts import BehaviorEvent
from intelligence_index.repository import (
    BehaviorEventSource,
    InMemoryBehaviorEventSource,
    PostgresBehaviorEventSource,
)


def _evento(person_id: str, ts: datetime) -> BehaviorEvent:
    return BehaviorEvent(person_id=person_id, tipo="stop", experience_id="e1", ts=ts)


def test_in_memory_implementa_il_protocollo() -> None:
    source: BehaviorEventSource = InMemoryBehaviorEventSource()
    assert hasattr(source, "events_in_period")


def test_in_memory_filtra_per_intervallo_semi_aperto() -> None:
    source = InMemoryBehaviorEventSource()
    source.record(_evento("p1", datetime(2026, 6, 30, 23, 59, tzinfo=UTC)))  # PRIMA del periodo
    source.record(_evento("p2", datetime(2026, 7, 1, 0, 0, tzinfo=UTC)))  # inizio esatto: dentro
    source.record(_evento("p3", datetime(2026, 7, 15, tzinfo=UTC)))  # dentro
    source.record(_evento("p4", datetime(2026, 8, 1, 0, 0, tzinfo=UTC)))  # esattamente fine: FUORI

    inizio = datetime(2026, 7, 1, tzinfo=UTC)
    fine = datetime(2026, 8, 1, tzinfo=UTC)
    risultato = source.events_in_period(inizio, fine)

    assert {evento.person_id for evento in risultato} == {"p2", "p3"}


def test_in_memory_costruita_gia_popolata() -> None:
    eventi = [_evento("p1", datetime(2026, 7, 5, tzinfo=UTC))]
    source = InMemoryBehaviorEventSource(eventi)
    risultato = source.events_in_period(
        datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)
    )
    assert len(risultato) == 1


def test_in_memory_vuota_di_default() -> None:
    source = InMemoryBehaviorEventSource()
    risultato = source.events_in_period(
        datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)
    )
    assert risultato == []


# ---------------------------------------------------------------------------
# PostgresBehaviorEventSource — solo test statici (nessun Postgres reale in
# questo ambiente)
# ---------------------------------------------------------------------------


def test_postgres_source_e_importabile_e_implementa_il_protocollo() -> None:
    source: BehaviorEventSource = PostgresBehaviorEventSource.__new__(PostgresBehaviorEventSource)
    assert hasattr(source, "events_in_period")


def test_postgres_source_prende_il_dsn_dal_costruttore() -> None:
    source = PostgresBehaviorEventSource("postgresql://esempio/db")
    assert source._dsn == "postgresql://esempio/db"
