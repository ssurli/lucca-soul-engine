"""Catalogo di `ExperienceNode` (`experience_id -> place_id`/`durata_min`).

Quasi ogni indicatore (`tempo_medio_esperienza_min`, `attivazione_locale`,
`distribuzione_flussi`, `nuovi_percorsi`) ha bisogno di risalire da un
`BehaviorEvent.experience_id`/`ItineraryStop.experience_id` al `place_id`
fisico o alla `durata_min` dell'esperienza — un `BehaviorEvent` non porta
questi campi (per costruzione: deve restare aggregabile e anonimo, vedi
`docs/DATA_CONTRACTS.md` §6).

NESSUNA fonte nuova: si ottiene chiamando
`graph.source.CandidateSource.candidates(ctx)` con un CONTESTO NEUTRO —
stesso principio del `SEGNALE_NEUTRO_STRUTTURALE` di
`recommender.ranking` — perché sia `SeedCandidateSource` sia
`Neo4jCandidateSource` restituiscono TUTTE le esperienze del grafo quando
`ctx.luoghi_gia_visti` è vuoto (nessun filtro applicato: vedi
`cypher/10_candidates.cypher`, `$vicino_a IS NULL` disattiva l'unico filtro
che dipende dal contesto). Il profilo/segnale del contesto non influenza in
alcun modo QUALI esperienze vengono restituite: li usa solo per arricchire
`connessioni`/`distanza_m` (narrazione), campi che questo modulo non legge.
"""

from __future__ import annotations

from datetime import time

from contracts import EmotionalProfile, ExperienceNode, Signal, VisitorContext
from graph.source import CandidateSource

__all__ = ["CONTESTO_NEUTRO_CATALOGO", "esperienze_per_id"]

#: Pseudonimo TECNICO (mai una persona reale): identifica solo la richiesta
#: interna usata per enumerare il catalogo, non un visitatore. Coerente con
#: "person_id è uno pseudonimo" (CLAUDE.md) — questo non è nemmeno lo
#: pseudonimo di una persona, ma di un processo di sistema.
_PERSON_ID_CATALOGO = "intelligence-index-catalogo"

#: Contesto NEUTRO: profilo/segnale a metà scala, nessun luogo già visto.
#: Non influenza l'insieme di esperienze restituito (vedi docstring di
#: modulo) — i valori scelti sono arbitrari MA fissi e documentati, per
#: rendere il catalogo deterministico e riproducibile.
CONTESTO_NEUTRO_CATALOGO = VisitorContext(
    person_id=_PERSON_ID_CATALOGO,
    profile=EmotionalProfile(
        curiosita=0.5,
        contemplazione=0.5,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=0,
    ),
    signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(12, 0)),
    luoghi_gia_visti=[],
)


def esperienze_per_id(candidate_source: CandidateSource) -> dict[str, ExperienceNode]:
    """Tutte le `ExperienceNode` del grafo, indicizzate per `id`.

    Una sola chiamata a `candidate_source.candidates(...)` (Seed o Neo4j,
    stessa interfaccia): nessuna query duplicata, nessuna seconda fonte di
    verità sul catalogo delle esperienze.
    """
    candidati = candidate_source.candidates(CONTESTO_NEUTRO_CATALOGO)
    return {candidato.experience.id: candidato.experience for candidato in candidati}
