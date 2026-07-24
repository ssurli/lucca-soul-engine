"""Lucca Soul Lab — Engine: pacchetto dei contratti dati condivisi.

Single source of truth (Pydantic v2), allineato a `docs/DATA_CONTRACTS.md`.
Uso: `from contracts import Itinerary, VisitorContext, ...`
"""

from .models import (
    AdaptRequest,
    BehaviorEvent,
    Booking,
    BookingRequest,
    BookingStatus,
    CommissionRecord,
    DashboardFlowsResponse,
    DashboardIndexResponse,
    EmotionalProfile,
    ExperienceCandidate,
    ExperienceNode,
    FasciaApertura,
    FlowCell,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    OnboardingAnswer,
    OnboardingRequest,
    Partner,
    PersonKind,
    Signal,
    UrbanIntelligenceIndex,
    VisitorContext,
    rientra_in_orario,
)

__all__ = [
    "AdaptRequest",
    "BehaviorEvent",
    "Booking",
    "BookingRequest",
    "BookingStatus",
    "CommissionRecord",
    "DashboardFlowsResponse",
    "DashboardIndexResponse",
    "EmotionalProfile",
    "ExperienceCandidate",
    "ExperienceNode",
    "FasciaApertura",
    "FlowCell",
    "GraphCandidate",
    "Itinerary",
    "ItineraryStop",
    "MemoryContribution",
    "MemoryKind",
    "OnboardingAnswer",
    "OnboardingRequest",
    "Partner",
    "PersonKind",
    "Signal",
    "UrbanIntelligenceIndex",
    "VisitorContext",
    "rientra_in_orario",
]

