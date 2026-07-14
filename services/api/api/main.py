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

Wave 2 aggiunge la Urban Memory (il fossato):
- `POST /memory` delega a `urban_memory.service.submit_contribution`, che
  applica in un solo punto i vincoli non negoziabili (consenso, licenza,
  pseudonimo, `curato` sempre forzato a `False` alla creazione — vedi
  `docs/DATA_CONTRACTS.md` §4 e §7);
- `GET /memory/{place_id}` delega a
  `urban_memory.service.contributions_for_place`, che espone SOLO i
  contributi curati (`curato=True`).
- Le violazioni dei vincoli (`urban_memory.UrbanMemoryError` e sottoclassi)
  sono mappate a un 422 esplicativo in italiano da
  `urban_memory_error_handler`, mai a un 500: è colpa della richiesta.
- Gli errori INFRASTRUTTURALI di storage (`urban_memory.MemoryStorageError`,
  sollevata da `PostgresMemoryRepository` quando Postgres/Neon non risponde
  o la migrazione non è applicata — NON una sottoclasse di
  `UrbanMemoryError`) sono mappati a un **503** da
  `memory_storage_error_handler`, mai a un 500 opaco e mai con dettagli
  interni del DB/DSN nel corpo o nei log: è colpa del server, non della
  richiesta.

`/health` non richiede alcun database attivo. Gli errori di validazione dei
payload sono lasciati alla gestione 422 di default di FastAPI/Pydantic.
Nessun PII: `person_id`/`contributor_id` sono pseudonimi e non compaiono mai
nei log applicativi; il contenuto di un `MemoryContribution` (`testo`,
`media_uri`) non viene MAI loggato, né qui né in `urban_memory.service`.
"""

from __future__ import annotations

from typing import Annotated

import contracts
from contracts import (
    AdaptRequest,
    EmotionalProfile,
    Itinerary,
    MemoryContribution,
    OnboardingRequest,
    VisitorContext,
)
from experience_engine.engine import adapt_itinerary, compose_itinerary
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rag.onboarding import profile_from_answers
from rag.reasons import adapt_reason, compose_reason
from urban_memory import (
    MemoryRepository,
    MemoryStorageError,
    UrbanMemoryError,
    contributions_for_place,
    submit_contribution,
)

from api import __version__
from api.deps import get_candidate_source, get_memory_repository
from api.settings import get_settings

app = FastAPI(title="Lucca Soul — BFF")

# Iniezione FastAPI standard (`Annotated[..., Depends(...)]`, non
# `= Depends(...)` in default d'argomento: quella forma è flaggata da
# ruff/bugbear B008). Definito una volta qui perché usato da entrambi gli
# endpoint `/memory*`: consente a un test di sostituire il repository con
# `app.dependency_overrides[get_memory_repository] = ...` senza toccare
# `api.deps` o la configurazione reale.
_MemoryRepositoryDep = Annotated[MemoryRepository, Depends(get_memory_repository)]


@app.exception_handler(UrbanMemoryError)
def urban_memory_error_handler(request: Request, exc: UrbanMemoryError) -> JSONResponse:
    """Mappa i vincoli non negoziabili della Urban Memory (consenso,
    licenza, pseudonimo — sollevati da `urban_memory.service`, un solo
    punto verificabile) a un 422 esplicativo in italiano, MAI un 500: chi
    conferisce deve sapere esattamente cosa manca (utile per un conferimento
    leggero e contestuale, vedi CLAUDE.md).

    Il messaggio dell'eccezione (`str(exc)`) descrive SOLO il vincolo
    violato, mai il contenuto del contributo (`testo`, `media_uri`,
    `contributor_id`): niente PII finisce in una risposta HTTP né in un log.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": f"conferimento rifiutato: {exc}"},
    )


@app.exception_handler(MemoryStorageError)
def memory_storage_error_handler(request: Request, exc: MemoryStorageError) -> JSONResponse:
    """Mappa un fallimento INFRASTRUTTURALE di storage della Urban Memory
    (`urban_memory.MemoryStorageError` — connessione a Postgres/Neon
    irraggiungibile, migrazione non applicata, query fallita) a un **503
    Service Unavailable**, MAI a un 500 opaco: chi chiama sa che è un
    problema temporaneo del server, non un errore nel proprio conferimento
    (quello è un 422, gestito da `urban_memory_error_handler`).

    Il corpo della risposta è un messaggio italiano generico e fisso: NON
    include mai `str(exc)` né altro dettaglio interno (DSN, host, credenziali,
    stack del driver). Per lo stesso motivo l'eccezione non viene loggata qui
    con il suo messaggio: nessun log applicativo di questo BFF espone
    dettagli infrastrutturali o PII."""
    return JSONResponse(
        status_code=503,
        content={"detail": "memoria temporaneamente non disponibile: riprova più tardi"},
    )


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


@app.post("/memory", response_model=MemoryContribution, status_code=201)
def submit_memory_contribution(
    contribution: MemoryContribution,
    repo: _MemoryRepositoryDep,
) -> MemoryContribution:
    """Conferimento alla Urban Memory (contratto §7, `docs/DATA_CONTRACTS.md`).

    Delega TUTTI i vincoli non negoziabili — consenso, licenza, pseudonimo,
    `curato` forzato a `False` alla creazione — a
    `urban_memory.service.submit_contribution`: un solo punto verificabile,
    mai duplicato qui. Le violazioni di dominio sollevano `UrbanMemoryError`
    (o una sottoclasse), mappata a 422 da `urban_memory_error_handler`. Un
    fallimento INFRASTRUTTURALE dello storage (`MemoryStorageError`,
    sollevata da `PostgresMemoryRepository` quando configurata via
    `DATABASE_URL`) è mappato a 503 da `memory_storage_error_handler`. Mai
    un 500 opaco in nessuno dei due casi. Il repository arriva via `Depends`
    (`api.deps.get_memory_repository`, `InMemoryMemoryRepository` finché
    `DATABASE_URL` non è configurato) invece di essere chiamato
    direttamente: così un test può sostituirlo con
    `app.dependency_overrides` senza toccare la configurazione reale;
    questo endpoint non tocca mai lo storage direttamente.

    Non logga MAI il contributo: né `testo`, né `media_uri`, né
    `contributor_id`."""
    return submit_contribution(repo, contribution)


@app.get("/memory/{place_id}", response_model=list[MemoryContribution])
def memory_for_place(
    place_id: str,
    repo: _MemoryRepositoryDep,
) -> list[MemoryContribution]:
    """Contributi CURATI (`curato=True`) che riguardano `place_id`
    (contratto §7). Delega a `urban_memory.service.contributions_for_place`,
    che passa SEMPRE da `get_curated`: un contributo appena conferito e non
    ancora revisionato da un umano non compare mai qui, indipendentemente
    da come è stato conferito. Un fallimento di storage risponde 503 (vedi
    `submit_memory_contribution`), mai un 500."""
    return contributions_for_place(repo, place_id)


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
