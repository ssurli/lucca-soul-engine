"""Lucca Soul Lab — Engine: servizio RAG (`services/rag`).

Onboarding conversazionale -> `EmotionalProfile` e generazione del `reason`.
L'LLM dialoga, non decide: qui non c'è alcuna scelta di tappe (quella è
dell'AI Experience Engine). Il percorso principale è deterministico e non
richiede alcuna chiave API; l'arricchimento via LLM è opzionale.
"""

from __future__ import annotations

from rag.onboarding import DOMANDE, DOMANDE_BY_ID, Domanda, profile_from_answers
from rag.reasons import adapt_reason, compose_reason, enrich_with_llm

__all__ = [
    "Domanda",
    "DOMANDE",
    "DOMANDE_BY_ID",
    "profile_from_answers",
    "compose_reason",
    "adapt_reason",
    "enrich_with_llm",
]
