"""Lucca Soul Lab — Engine: Recommender ML (`services/recommender`), Wave 3b.

Impara l'ALGORITMO dai comportamenti storici (`BehaviorEvent`:
view/stop/photo/booking/review/skip/memory_contrib), non il modello
linguistico. Import name del pacchetto: `recommender` (nome distribuzione:
`lucca-recommender`).

Vincolo non negoziabile di questa wave (prescrizione ethics-guardian):
la funzione obiettivo non è la pertinenza misurata sui dati storici (che
rifletterebbe l'overtourism ESISTENTE), ma la pertinenza VINCOLATA a
distribuzione dei flussi. `costruisci_score_fn` (`recommender.ranking`)
produce una funzione compatibile con `experience_engine.engine.ScoreFn`, da
iniettare come `score_fn` in `compose_itinerary` (lo fa il BFF): riusa
`experience_engine.rules.calcola_score` per la pertinenza di base (mai
duplicata) e la PENALIZZA (mai premia) con due termini indipendenti sul
luogo fisico (`place_id`, non la singola esperienza): la quota storica di
concentrazione REALE (`BehaviorEvent`, con smoothing di Laplace) e la quota
strutturale di dominio per PERTINENZA DI CONTENUTO su un insieme fisso di
profili archetipo (nessun dato storico) — vedi `recommender.ranking` per la
diagnosi che ha reso necessario il secondo termine.

Questo pacchetto:
- NON importa `services/graph` né `services/api`: la mappa
  `experience_id -> place_id` si costruisce SOLO dai `GraphCandidate` di
  QUESTA richiesta, mai da un join/import del grafo.
- Importa da `experience_engine` SOLO `rules.calcola_score` — mai altro.
- Non legge mai campi commerciali (`Partner`, `prezzo_eur`,
  `partner_abbonamento_attivo`, `prenotabile`) né segnali di notorietà
  esterna (rating/recensioni di provider terzi) né dati di Urban Memory /
  Urban Intelligence Index: vedi il README, sezione "Cosa NON è una
  feature, e perché".

Uso tipico (il BFF cablerà questo passaggio)::

    from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn
    from experience_engine import compose_itinerary

    repo = InMemoryBehaviorEventRepository()
    # ... repo.record(evento) per ogni BehaviorEvent osservato ...

    score_fn = costruisci_score_fn(repo, candidati_correnti=candidates, vocabolario=vocabolario)
    # `vocabolario`: dataset della citta' scelto da CITY_SEED (lo passa il BFF)
    itinerario = compose_itinerary(
        ctx, candidates, compose_reason, score_fn, vocabolario=vocabolario
    )

Persistenza reale (Neon in cloud o Postgres locale — mai `if local/cloud`,
solo `DATABASE_URL`). Una tantum, applica la migrazione idempotente
(`python -m recommender.migrate`), poi::

    from recommender import PostgresBehaviorEventRepository

    repo = PostgresBehaviorEventRepository.from_env()  # legge DATABASE_URL
"""

from __future__ import annotations

from .features import PESI_TIPO
from .migrate import SCHEMA_PATH, migrate
from .ranking import (
    ALPHA_LAPLACE,
    ARCHETIPI_STRUTTURALI,
    LIMITE_PESO_COMBINATO_MAX,
    PESO_STORICO_DEFAULT,
    PESO_STRUTTURA_DEFAULT,
    SEGNALE_NEUTRO_STRUTTURALE,
    SOGLIA_MINIMA_EVENTI_MAPPABILI,
    ScoreFn,
    costruisci_score_fn,
)
from .repository import (
    BehaviorEventRepository,
    InMemoryBehaviorEventRepository,
    PostgresBehaviorEventRepository,
    RecommenderStorageError,
)

__all__ = [
    "BehaviorEventRepository",
    "InMemoryBehaviorEventRepository",
    "PostgresBehaviorEventRepository",
    "RecommenderStorageError",
    "PESI_TIPO",
    "ScoreFn",
    "PESO_STORICO_DEFAULT",
    "PESO_STRUTTURA_DEFAULT",
    "LIMITE_PESO_COMBINATO_MAX",
    "SOGLIA_MINIMA_EVENTI_MAPPABILI",
    "ALPHA_LAPLACE",
    "ARCHETIPI_STRUTTURALI",
    "SEGNALE_NEUTRO_STRUTTURALE",
    "costruisci_score_fn",
    "migrate",
    "SCHEMA_PATH",
]
