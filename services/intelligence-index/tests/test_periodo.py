"""Test di `intelligence_index.periodo.intervallo_periodo`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from intelligence_index.periodo import intervallo_periodo


def test_mese_ordinario() -> None:
    inizio, fine = intervallo_periodo("2026-07")
    assert inizio == datetime(2026, 7, 1, tzinfo=UTC)
    assert fine == datetime(2026, 8, 1, tzinfo=UTC)


def test_dicembre_passa_allanno_successivo() -> None:
    inizio, fine = intervallo_periodo("2026-12")
    assert inizio == datetime(2026, 12, 1, tzinfo=UTC)
    assert fine == datetime(2027, 1, 1, tzinfo=UTC)


def test_gennaio() -> None:
    inizio, fine = intervallo_periodo("2027-01")
    assert inizio == datetime(2027, 1, 1, tzinfo=UTC)
    assert fine == datetime(2027, 2, 1, tzinfo=UTC)


def test_intervallo_semi_aperto_utc() -> None:
    inizio, fine = intervallo_periodo("2026-02")
    assert inizio.tzinfo is UTC
    assert fine.tzinfo is UTC
    assert inizio < fine


@pytest.mark.parametrize("periodo_invalido", ["2026", "2026-13", "2026-00", "luglio-2026", ""])
def test_formato_invalido_solleva(periodo_invalido: str) -> None:
    with pytest.raises(ValueError):
        intervallo_periodo(periodo_invalido)
