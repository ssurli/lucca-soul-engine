"""Lucca Soul Lab — Engine: pacchetto dei contratti dati condivisi.

Single source of truth (Pydantic v2), allineato a `docs/DATA_CONTRACTS.md`.
Uso: `from contracts import Itinerary, VisitorContext, ...`
"""

from .models import (
    AdaptRequest,
    BehaviorEvent,
    EmotionalProfile,
    ExperienceCandidate,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    OnboardingAnswer,
    OnboardingRequest,
    PersonKind,
    Signal,
    UrbanIntelligenceIndex,
    VisitorContext,
)

__all__ = [
    "AdaptRequest",
    "BehaviorEvent",
    "EmotionalProfile",
    "ExperienceCandidate",
    "ExperienceNode",
    "GraphCandidate",
    "Itinerary",
    "ItineraryStop",
    "MemoryContribution",
    "MemoryKind",
    "OnboardingAnswer",
    "OnboardingRequest",
    "PersonKind",
    "Signal",
    "UrbanIntelligenceIndex",
    "VisitorContext",
]

