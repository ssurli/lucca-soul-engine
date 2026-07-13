"""Lucca Soul Lab — Engine: pacchetto dei contratti dati condivisi.

Single source of truth (Pydantic v2), allineato a `docs/DATA_CONTRACTS.md`.
Uso: `from contracts import Itinerary, VisitorContext, ...`
"""

from .models import (
    BehaviorEvent,
    EmotionalProfile,
    ExperienceCandidate,
    ExperienceNode,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    PersonKind,
    Signal,
    UrbanIntelligenceIndex,
    VisitorContext,
)

__all__ = [
    "BehaviorEvent",
    "EmotionalProfile",
    "ExperienceCandidate",
    "ExperienceNode",
    "Itinerary",
    "ItineraryStop",
    "MemoryContribution",
    "MemoryKind",
    "PersonKind",
    "Signal",
    "UrbanIntelligenceIndex",
    "VisitorContext",
]

