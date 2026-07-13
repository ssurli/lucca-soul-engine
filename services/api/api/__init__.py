"""Lucca Soul Lab — Engine: BFF (Backend For Frontend).

Unico ingresso per l'app Flutter: il BFF chiama i servizi interni
(experience-engine, graph, rag, recommender). L'app non tocca mai i
servizi diretti.

Wave 0: solo fondamenta (`/health`). Gli endpoint applicativi
(`/session/onboarding`, `/itinerary`, `/itinerary/adapt`, `/events`,
`/dashboard/flows`) arrivano nelle wave successive del BUILD_PLAN.
"""

__version__ = "0.1.0"
