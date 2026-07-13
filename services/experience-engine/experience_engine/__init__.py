"""Lucca Soul Lab — Engine: AI Experience Engine (il "brevetto").

L'UNICO componente che DECIDE. Combina i candidati che il grafo PROPONE, i
`Signal` del mondo e i vincoli etici in un `Itinerary` spiegabile, e lo
riscrive quando il mondo cambia. Dipende SOLO dai contratti: grafo e RAG sono
iniettati dal BFF.

Uso: `from experience_engine import compose_itinerary, adapt_itinerary`.
"""

from .engine import (
    AdaptReasonFn,
    ReasonFn,
    adapt_itinerary,
    compose_itinerary,
)

__all__ = [
    "compose_itinerary",
    "adapt_itinerary",
    "ReasonFn",
    "AdaptReasonFn",
]
