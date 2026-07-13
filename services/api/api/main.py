"""Lucca Soul Lab — BFF (Backend For Frontend).

Unico ingresso per l'app Flutter: gli endpoint applicativi orchestrano i
servizi interni (`graph`, `rag`, `experience_engine`) e riusano SEMPRE gli
schemi di `packages/contracts` — nessuno di questi endpoint ridefinisce un
campo, lo importa.

Wave 1 aggiunge la pipeline completa di raccomandazione:
- `POST /session/onboarding` delega a `rag.onboarding.profile_from_answers`;
- `POST /itinerary` prende i candidati dalla `CandidateSource` (vedi
  `api.deps`) e chiama `experience_engine.engine.compose_itinerary`,
  iniettando `rag.reasons.compose_reason` per la spiegabilità obbligatoria;
- `POST /itinerary/adapt` fa lo stesso con `adapt_itinerary` e
  `rag.reasons.adapt_reason`.

`/health` non richiede alcun database attivo. Gli errori di validazione dei
payload sono lasciati alla gestione 422 di default di FastAPI/Pydantic.
Nessun PII: `person_id` è pseudonimo, e non compare mai nei log applicativi.
"""

from __future__ import annotations

import contracts
from contracts import (
    AdaptRequest,
    EmotionalProfile,
    Itinerary,
    OnboardingRequest,
    VisitorContext,
)
from experience_engine.engine import adapt_itinerary, compose_itinerary
from fastapi import FastAPI
from pydantic import BaseModel
from rag.onboarding import profile_from_answers
from rag.reasons import adapt_reason, compose_reason

from api import __version__
from api.deps import get_candidate_source
from api.settings import get_settings

app = FastAPI(title="Lucca Soul — BFF")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ContractsVersionResponse(BaseModel):
    """Conferma che il BFF importa gli schemi da `packages/contracts`
    (single source of truth) invece di ridefinirli localmente."""

    package: str
    types: list[str]
    example_type: str = VisitorContext.__name__


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="lucca-soul-bff",
        version=__version__,
    )


@app.get("/contracts/version", response_model=ContractsVersionResponse)
def contracts_version() -> ContractsVersionResponse:
    return ContractsVersionResponse(
        package=contracts.__name__,
        types=sorted(contracts.__all__),
    )


@app.post("/session/onboarding", response_model=EmotionalProfile)
def session_onboarding(request: OnboardingRequest) -> EmotionalProfile:
    """Onboarding conversazionale -> `EmotionalProfile`.

    L'LLM/parsing dialoga, non decide: la lettura del profilo è interamente
    delegata a `rag.onboarding.profile_from_answers` (deterministica,
    testabile offline, mai un'eccezione su testo "strano")."""
    return profile_from_answers(request)


@app.post("/itinerary", response_model=Itinerary)
def create_itinerary(ctx: VisitorContext) -> Itinerary:
    """Compone un `Itinerary` per il `VisitorContext` dato.

    I candidati arrivano dalla `CandidateSource` configurata (seed o Neo4j,
    vedi `api.deps.get_candidate_source`); la scelta e i vincoli etici
    restano interamente dell'AI Experience Engine, l'unico che decide."""
    source = get_candidate_source()
    candidates = source.candidates(ctx)
    return compose_itinerary(ctx, candidates, reason_fn=compose_reason)


@app.post("/itinerary/adapt", response_model=Itinerary)
def adapt_itinerary_endpoint(request: AdaptRequest) -> Itinerary:
    """Riscrive SOLO ciò che il nuovo `Signal` tocca (pioggia, affollamento,
    stanchezza). `AdaptRequest` non trasporta il profilo: i candidati sono
    interrogati con un profilo neutro (serve solo a costruire il
    `VisitorContext` richiesto dalla `CandidateSource`, non introduce
    preferenze); l'Experience Engine riceve `profile=None` e applica la
    stessa regola conservativa già testata (una tappa accessibile resta
    sostituita solo da una accessibile)."""
    source = get_candidate_source()
    ctx = VisitorContext(
        person_id=request.itinerary.person_id,
        profile=_profilo_neutro_per_candidati(),
        signal=request.signal,
    )
    candidates = source.candidates(ctx)
    return adapt_itinerary(
        request.itinerary,
        request.signal,
        candidates,
        profile=None,
        reason_fn=compose_reason,
        adapt_reason_fn=adapt_reason,
    )


def _profilo_neutro_per_candidati() -> EmotionalProfile:
    """Profilo neutro usato SOLO per costruire il `VisitorContext` richiesto
    da `CandidateSource.candidates` in `/itinerary/adapt`, dove `AdaptRequest`
    non trasporta un profilo. Non influenza la scelta: `SeedCandidateSource`
    e `Neo4jCandidateSource` derivano le connessioni proposte dai luoghi già
    visti, non dal profilo."""
    return EmotionalProfile(
        curiosita=0.5,
        contemplazione=0.5,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=0,
    )


# Impronta esplicita: le Settings vengono lette a import-time per fallire
# in modo leggibile se la configurazione è malformata, ma nessuna variabile
# è obbligatoria (vedi api/settings.py).
get_settings()
