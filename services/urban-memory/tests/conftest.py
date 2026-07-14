"""Fixture condivise per i test di Urban Memory."""

from __future__ import annotations

from datetime import datetime

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind


@pytest.fixture
def valid_contribution_factory():
    """Factory di un `MemoryContribution` valido (consenso=True, licenza
    tracciata, pseudonimo non vuoto, curato=False): il caso "felice" di
    partenza per i test che poi violano un singolo vincolo alla volta."""

    def _build(**overrides: object) -> MemoryContribution:
        defaults: dict[str, object] = {
            "id": "mem-001",
            "kind": MemoryKind.RACCONTO,
            "testo": "Il racconto di una bottega di liuteria a Lucca.",
            "media_uri": None,
            "riguarda": ["bottega-liuteria-1"],
            "contributor_id": "nonna-lucia",
            "contributor_kind": PersonKind.CITTADINO,
            "esperienza_id": None,
            "consenso": True,
            "licenza": "CC-BY-SA-4.0",
            "creato_il": datetime(2026, 7, 14, 10, 0),
            "curato": False,
        }
        defaults.update(overrides)
        return MemoryContribution(**defaults)

    return _build
