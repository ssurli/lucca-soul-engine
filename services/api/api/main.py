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

Wave 3a aggiunge il Marketplace (`docs/DATA_CONTRACTS.md` §5), un solo
endpoint in questo BFF:
- `POST /booking` delega a `marketplace.service.request_booking`. `prezzo_eur`
  e `prenotabile` NON arrivano mai dal chiamante (`BookingRequest` non li
  contiene, di proposito): questo endpoint li legge dal candidato corrente
  della `CandidateSource` (stesso profilo neutro di
  `_profilo_neutro_per_candidati`, usato SOLO per costruire il
  `VisitorContext` richiesto — non introduce preferenze). Se
  `request.experience_id` non è tra i candidati -> **404** (risorsa
  inesistente, non un vincolo di dominio). Le violazioni di dominio
  (`marketplace.MarketplaceError` e sottoclassi, es. `prenotabile=False`)
  sono mappate a 422 da `marketplace_error_handler`; un fallimento
  INFRASTRUTTURALE di storage (`marketplace.MarketplaceStorageError`) è
  mappato a 503 da `marketplace_storage_error_handler`. Mai un 500 opaco.
  `confirm_booking` esiste nel service layer ma non è esposto da questo BFF
  in questa wave (fuori scope).

Wave 3b aggiunge il Recommender ML (`docs/DATA_CONTRACTS.md` §6/§8):
- `POST /events` (202, non 201: non crea una risorsa interrogabile, solo un
  segnale comportamentale accodato) riceve un `BehaviorEvent` e lo persiste
  con `repo.record(evento)` (`api.deps.get_event_repository`). Un fallimento
  INFRASTRUTTURALE di storage (`recommender.RecommenderStorageError`) è
  mappato a 503 da `event_storage_error_handler`, stesso stile di
  `memory_storage_error_handler`/`marketplace_storage_error_handler`.
- `POST /itinerary` costruisce ORA anche uno `score_fn` da
  `recommender.costruisci_score_fn(get_event_repository(), candidates)` e lo
  passa a `compose_itinerary` per il reranking (pertinenza vincolata a
  distribuzione dei flussi, vedi `services/recommender/README.md`). A
  differenza di `/events` — dove lo storage È la richiesta — qui lo storico
  comportamentale è un ARRICCHIMENTO OPZIONALE del ranking: un fallimento del
  recommender (storage irraggiungibile o qualunque altro errore) non deve
  MAI far fallire `/itinerary`, quindi viene catturato e l'endpoint ricade su
  `score_fn=None` (il ranking deterministico `calcola_score`, identico al
  comportamento pre-Wave-3b) — vedi il commento in `create_itinerary`.

Fase 3 aggiunge la fondazione del canale fluttuante persistente
(`docs/PROMOZIONE_TRACCIA.md`): `POST /itinerary` ORA popola
`ctx.signal.eventi_attivi` lato SERVER, PRIMA di chiamare
`compose_itinerary` — `urban_memory.canale_fluttuante.
sweep_and_fetch_active(get_segnale_repository(), get_traccia_repository(),
place_link_writer=get_place_link_writer())` spazza (lazy, globale) i segnali
scaduti, deposita una traccia per ciascuno (ledger append-only,
`services/urban-memory`) e aggiorna `:Luogo.ultima_traccia_il` (Neo4j,
best-effort), poi fetcha gli attivi rimasti. Il valore ritornato SOVRASCRIVE
SEMPRE `eventi_attivi` mandato dal client nel body — proprietà di
SICUREZZA: un client non può iniettare segnali fluttuanti falsi in una
composizione. Stesso "cattura e degrada" del Recommender sopra: un
fallimento dello store (Postgres o, per la proprietà derivata, Neo4j) NON fa
mai fallire `/itinerary` — `eventi_attivi` resta vuoto, mai un 503. Il
motore (`experience_engine.engine.compose_itinerary`) resta INVARIATO: legge
solo `ctx.signal.eventi_attivi`, non sa nulla dello storage che lo popola.

Wave 4 aggiunge la dashboard dell'Urban Intelligence Index
(`docs/DATA_CONTRACTS.md` §7/§8), due soli endpoint `GET`, entrambi wrapper
PURI attorno agli adattatori già pronti in `intelligence_index.dashboard`
(`indice_per_dashboard`/`celle_flusso`) — nessuna logica di calcolo nuova
qui, solo assemblaggio dei parametri iniettati:
- `GET /dashboard/index?periodo=YYYY-MM` -> `DashboardIndexResponse`.
- `GET /dashboard/flows?periodo=YYYY-MM&giorno=YYYY-MM-DD&ora=0..23` ->
  `DashboardFlowsResponse`.

`periodo` è SEMPRE obbligatorio (nessun default nascosto: chi guarda la
dashboard deve essere esplicito su quale mese); `giorno`/`ora` sono opzionali
(`ora` vincolato `ge=0, le=23` anche a livello di query, non solo nel
modello Pydantic — un 422 leggibile PRIMA ancora di costruire il payload).
Entrambi rispondono SEMPRE 200: "dato insufficiente per privacy" (soglia
k=10, `intelligence_index.soglia`) è uno stato legittimo della risposta
(`disponibile: bool`), mai un errore HTTP — coerente con la spiegabilità
obbligatoria (CLAUDE.md), il client distingue "nessun dato" da "errore"
solo leggendo il campo, mai leggendo lo status code.

Le fonti (`intelligence_index.deps.get_metrics_source`/`get_event_source`
per il grafo/gli eventi, `api.deps.get_candidate_source`/
`get_memory_repository` — GLI STESSI già usati da `/itinerary`/`/memory`,
non una seconda selezione) sono chiamate DIRETTAMENTE nel corpo di questi
due endpoint, mai tramite `Depends` nella firma — stesso motivo di
`get_candidate_source()` in `create_itinerary`: sono selettori di sorgente,
non il contenuto della richiesta. Un fallimento INFRASTRUTTURALE di lettura
(`intelligence_index.IndexStorageError` da Postgres/Neon,
`urban_memory.MemoryStorageError` da Urban Memory) è mappato a 503 da
`index_storage_error_handler`/`memory_storage_error_handler`, mai a un 500
opaco. `DatiInsufficientiError` (soglia k=10 sull'intero periodo) non arriva
mai fin qui: `indice_per_dashboard` la cattura già internamente e la
traduce in `disponibile=False`.

`/health` non richiede alcun database attivo. Gli errori di validazione dei
payload sono lasciati alla gestione 422 di default di FastAPI/Pydantic.
Nessun PII: `person_id`/`contributor_id` sono pseudonimi e non compaiono mai
nei log applicativi; il contenuto di un `MemoryContribution` (`testo`,
`media_uri`) non viene MAI loggato, né qui né in `urban_memory.service`.
"""

from __future__ import annotations

from datetime import date, time
from typing import Annotated

import contracts
import marketplace
import recommender
from contracts import (
    AdaptRequest,
    BehaviorEvent,
    Booking,
    BookingRequest,
    DashboardFlowsResponse,
    DashboardIndexResponse,
    EmotionalProfile,
    EventoPromosso,
    Itinerary,
    MemoryContribution,
    OnboardingRequest,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
)
from experience_engine.engine import adapt_itinerary, compose_itinerary
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from intelligence_index import IndexStorageError
from intelligence_index.catalogo import esperienze_per_id as indice_esperienze_per_id
from intelligence_index.dashboard import celle_flusso, indice_per_dashboard
from intelligence_index.deps import get_event_source, get_metrics_source
from intelligence_index.periodo import intervallo_periodo
from pydantic import BaseModel
from rag.onboarding import profile_from_answers
from rag.reasons import adapt_reason, compose_reason
from urban_memory import (
    MemoryRepository,
    MemoryStorageError,
    UrbanMemoryError,
    contributions_for_place,
    submit_contribution,
    sweep_and_fetch_active,
)

from api import __version__
from api.deps import (
    get_booking_repository,
    get_candidate_source,
    get_event_repository,
    get_evento_reader,
    get_memory_repository,
    get_place_link_writer,
    get_segnale_repository,
    get_traccia_repository,
)
from api.settings import get_settings

app = FastAPI(title="Lucca Soul — BFF")


# MODIFICA DI POSTURA DI SICUREZZA (non un dettaglio estetico — vedi
# docs/LIMITI.md): CORS aperto, ma ristretto al minimo indispensabile su
# TRE assi contemporaneamente, non solo uno:
#   1. SOLO `GET` (mai `POST /memory`, `POST /booking`, `POST /events`,
#      `POST /session/onboarding`, `POST /itinerary*`: quelli restano
#      IRRAGGIUNGIBILI da una pagina web di origine diversa, wildcard o no);
#   2. SOLO i path `/dashboard/*` (NON `/memory/{place_id}`, non `/health`,
#      non `/contracts/version`: `fastapi.middleware.cors.CORSMiddleware` di
#      libreria si applica all'INTERA app, senza scoping per path — per
#      questo qui c'è un middleware scritto a mano, non quello di libreria);
#   3. Serve a UN SOLO consumatore concreto: `scripts/dashboard_viewer.html`,
#      una pagina statica senza build aperta con un doppio clic da `file://`
#      (quindi origin "null" per il browser) mentre il BFF gira in locale.
#
# Un browser applica CORS SOLO alle richieste che parte lui stesso: questo
# non ha alcun effetto sull'app Flutter (client HTTP nativo, non un
# browser) né su chiamate server-to-server. `GET /dashboard/*` espone solo
# dati già aggregati e gated a k=10 (mai PII): allargarne la lettura a un
# client locale non introduce, DI PER SÉ, una superficie nuova di privacy.
#
# NON è comunque un `*` da lasciare dimenticato: `allow_origins="*"` va bene
# per uno strumento locale, MAI per un deploy pubblico del BFF — il giorno
# in cui questo servizio finisce online, l'origine va ristretta a domini
# specifici (o il middleware rimosso, se il viewer HTML non serve più in
# quel contesto). Vedi `docs/LIMITI.md` per il dettaglio.
_DASHBOARD_PATH_PREFIX = "/dashboard/"


@app.middleware("http")
async def dashboard_readonly_cors(request: Request, call_next):  # type: ignore[no-untyped-def]
    is_dashboard_path = request.url.path.startswith(_DASHBOARD_PATH_PREFIX)

    # Preflight CORS (`OPTIONS`) per una GET verso `/dashboard/*`: risposto
    # direttamente qui, PRIMA di raggiungere qualunque route — un browser lo
    # manda per verificare il permesso prima della richiesta vera.
    if (
        request.method == "OPTIONS"
        and is_dashboard_path
        and request.headers.get("access-control-request-method", "").upper() == "GET"
    ):
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "*",
            },
        )

    response = await call_next(request)

    # Intestazione CORS aggiunta SOLO su una GET reale verso `/dashboard/*`:
    # ogni altro path/metodo (incluso un domani nuovo endpoint GET non
    # ancora previsto oggi) resta SENZA questa intestazione per costruzione,
    # non per disciplina di chi aggiunge un endpoint in futuro.
    if request.method == "GET" and is_dashboard_path:
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# Iniezione FastAPI standard (`Annotated[..., Depends(...)]`, non
# `= Depends(...)` in default d'argomento: quella forma è flaggata da
# ruff/bugbear B008). Definito una volta qui perché usato da entrambi gli
# endpoint `/memory*`: consente a un test di sostituire il repository con
# `app.dependency_overrides[get_memory_repository] = ...` senza toccare
# `api.deps` o la configurazione reale.
_MemoryRepositoryDep = Annotated[MemoryRepository, Depends(get_memory_repository)]

# Stesso pattern per `POST /booking` (Wave 3a): un test sostituisce il
# repository del Marketplace con `app.dependency_overrides` senza toccare
# `api.deps` o la configurazione reale.
_BookingRepositoryDep = Annotated[
    marketplace.BookingRepository, Depends(get_booking_repository)
]

# Stesso pattern per `POST /events` (Wave 3b): un test sostituisce il
# repository degli eventi comportamentali con `app.dependency_overrides`
# senza toccare `api.deps` o la configurazione reale.
_EventRepositoryDep = Annotated[
    recommender.BehaviorEventRepository, Depends(get_event_repository)
]


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


@app.exception_handler(marketplace.MarketplaceError)
def marketplace_error_handler(
    request: Request, exc: marketplace.MarketplaceError
) -> JSONResponse:
    """Mappa i vincoli non negoziabili del Marketplace (`ExperienceNotBookableError`,
    `BookingNotFoundError`, `InvalidBookingStateError` — sollevati da
    `marketplace.service`, un solo punto verificabile) a un 422 esplicativo in
    italiano, MAI un 500: stesso stile di `urban_memory_error_handler`."""
    return JSONResponse(
        status_code=422,
        content={"detail": f"prenotazione rifiutata: {exc}"},
    )


@app.exception_handler(marketplace.MarketplaceStorageError)
def marketplace_storage_error_handler(
    request: Request, exc: marketplace.MarketplaceStorageError
) -> JSONResponse:
    """Mappa un fallimento INFRASTRUTTURALE di storage del Marketplace
    (`marketplace.MarketplaceStorageError` — connessione a Postgres/Neon
    irraggiungibile, migrazione non applicata, query fallita) a un **503
    Service Unavailable**, MAI a un 500 opaco: stesso stile di
    `memory_storage_error_handler`. Il corpo è un messaggio italiano generico
    e fisso: NON include mai `str(exc)` né altro dettaglio interno (DSN,
    host, credenziali, stack del driver)."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": "prenotazioni temporaneamente non disponibili: riprova più tardi"
        },
    )


@app.exception_handler(recommender.RecommenderStorageError)
def event_storage_error_handler(
    request: Request, exc: recommender.RecommenderStorageError
) -> JSONResponse:
    """Mappa un fallimento INFRASTRUTTURALE di storage del Recommender
    (`recommender.RecommenderStorageError` — connessione a Postgres/Neon
    irraggiungibile, migrazione non applicata, query fallita) a un **503
    Service Unavailable**, MAI a un 500 opaco: stesso stile di
    `memory_storage_error_handler`/`marketplace_storage_error_handler`.

    Questo handler copre SOLO `POST /events`, dove la persistenza dell'evento
    È la richiesta. Non copre `POST /itinerary`: lì un fallimento dello
    stesso repository è catturato direttamente in `create_itinerary` e non
    arriva mai fin qui (vedi il commento in quella funzione per il perché di
    una strategia diversa). Il corpo è un messaggio italiano generico e
    fisso: NON include mai `str(exc)` né altro dettaglio interno (DSN, host,
    credenziali, stack del driver)."""
    return JSONResponse(
        status_code=503,
        content={"detail": "eventi temporaneamente non disponibili: riprova più tardi"},
    )


@app.exception_handler(IndexStorageError)
def index_storage_error_handler(request: Request, exc: IndexStorageError) -> JSONResponse:
    """Mappa un fallimento INFRASTRUTTURALE di lettura dell'Urban Intelligence
    Index (`intelligence_index.IndexStorageError` — lettura di `behavior_event`
    da Postgres/Neon irraggiungibile o query fallita, sollevata da
    `PostgresBehaviorEventSource.events_in_period`) a un **503 Service
    Unavailable**, MAI a un 500 opaco: stesso stile di
    `memory_storage_error_handler`/`marketplace_storage_error_handler`/
    `event_storage_error_handler`.

    Copre `GET /dashboard/index` e `GET /dashboard/flows`: entrambi leggono
    `get_event_source().events_in_period(...)` direttamente nel corpo
    dell'endpoint (non tramite `Depends`), quindi un suo fallimento propaga
    fino a qui, dove viene mappato invece di risalire grezzo. NON è
    `intelligence_index.DatiInsufficientiError` (quello è un vincolo di
    dominio/privacy — sotto la soglia k=10 — già catturato internamente da
    `intelligence_index.dashboard.indice_per_dashboard`, non arriva mai fin
    qui). Il corpo della risposta è un messaggio italiano generico e fisso:
    NON include mai `str(exc)` né altro dettaglio interno (DSN, host,
    credenziali, stack del driver)."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": "indicatori temporaneamente non disponibili: riprova più tardi"
        },
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
    restano interamente dell'AI Experience Engine, l'unico che decide.

    Wave 3b: dopo aver ottenuto i candidati, prova a costruire uno `score_fn`
    dal Recommender ML (`recommender.costruisci_score_fn`) per il reranking
    "pertinenza vincolata a distribuzione dei flussi" (vedi
    `services/recommender/README.md`) e lo passa a `compose_itinerary`.

    NOTA sull'iniezione: qui `get_event_repository()` è chiamata
    DIRETTAMENTE (non tramite `Depends` nella firma), esattamente come già fa
    questo stesso endpoint per `get_candidate_source()` — a differenza di
    `POST /events`, dove il repository È il contenuto della richiesta ed è
    quindi iniettato via `Depends` per essere sostituibile con
    `app.dependency_overrides`. Il motivo è il VINCOLO CRITICO sotto: la
    risoluzione di un `Depends` da parte di FastAPI avviene PRIMA che il
    corpo di questa funzione inizi a eseguire, quindi un suo fallimento non
    sarebbe MAI catturabile dal `try/except` qui sotto e finirebbe
    inevitabilmente nel gestore globale di `RecommenderStorageError`
    (pensato per `/events`, un 503) — esattamente ciò che questo endpoint
    deve evitare. Chiamandola direttamente dentro il `try`, un test la
    sostituisce con `monkeypatch.setattr(api.main, "get_event_repository",
    ...)`, stessa tecnica già usata da `tests/test_booking.py` per
    `get_candidate_source`.

    VINCOLO CRITICO: a differenza di `/memory`, `/booking` ed `/events` —
    dove lo storage È il cuore della richiesta, quindi un fallimento
    infrastrutturale è un 503 legittimo (`memory_storage_error_handler`,
    `marketplace_storage_error_handler`, `event_storage_error_handler`) — qui
    lo storico comportamentale è un ARRICCHIMENTO OPZIONALE del ranking, non
    il contenuto della richiesta: l'utente ha chiesto un itinerario, non una
    lettura dello storico eventi. Un fallimento del Recommender (repository
    non raggiungibile — `recommender.RecommenderStorageError` — o qualunque
    altro errore imprevisto nella costruzione del repository o nella
    lettura/aggregazione dello storico) NON deve MAI propagare da qui: viene
    catturato e l'endpoint ricade su `score_fn=None`, cioè il ranking
    deterministico `calcola_score` da solo — esattamente il comportamento di
    questo endpoint PRIMA che questa wave esistesse. Stesso principio del
    cold start (repository vuoto -> punteggio bit-identico a
    `calcola_score`), esteso al caso "il recommender non è raggiungibile":
    mai un errore, mai rumore, mai un 500/503 per un problema di
    un'infrastruttura ausiliaria che non riguarda la richiesta dell'utente.
    Per questo qui la strategia è "cattura e degrada", non "503 esplicito"
    come in `/events`: sono scelte diverse per motivi diversi (centralità
    dello storage nella richiesta), non un'incoerenza tra i due endpoint.

    Fase 3 — canale fluttuante persistente (`docs/PROMOZIONE_TRACCIA.md`):
    dopo aver costruito `score_fn`, questo endpoint SOVRASCRIVE
    `ctx.signal.eventi_attivi` con la lettura AUTOREVOLE dallo store
    (`urban_memory.canale_fluttuante.sweep_and_fetch_active`), IGNORANDO
    qualunque valore mandato dal client nel body — PROPRIETÀ DI SICUREZZA:
    un client non può iniettare segnali fluttuanti falsi in una
    composizione (oggi ogni client manda `eventi_attivi=[]`; anche se ne
    mandasse uno costruito ad arte, verrebbe scartato qui, PRIMA che
    `compose_itinerary` veda `ctx`). Stessa tecnica di iniezione diretta
    (mai `Depends`) di `get_event_repository()` sopra, per lo STESSO motivo:
    `get_segnale_repository()`/`get_traccia_repository()`/
    `get_place_link_writer()` sono chiamate DENTRO il `try`, così un loro
    fallimento resta catturabile qui e non finisce in un gestore globale
    503 (che per questi tipi non esiste nemmeno, di proposito: il canale
    fluttuante non ha un endpoint HTTP pubblico ancora, quindi nessun altro
    percorso li solleva).

    VINCOLO CRITICO — identico a quello sopra per il Recommender, sulla
    STESSA riga di ragionamento: il canale fluttuante è un arricchimento
    OPZIONALE della composizione (una tappa fluttuante in più, "un
    violinista in piazza"), non il cuore della richiesta. Un fallimento
    catturato QUI (`SegnaleStorageError` da `sweep_scaduti`/`fetch_attivi`,
    o un fallimento nella costruzione dei repository/writer) NON deve MAI
    far fallire `/itinerary`: viene catturato e `eventi_attivi` resta `[]`
    (comportamento IDENTICO a ogni chiamante precedente a questa fase, che
    non popolava mai questo campo).

    DUE GARANZIE DIVERSE — non confonderle (precisato dopo una revisione
    `ethics-guardian`: la formulazione precedente le confondeva in una sola
    frase rassicurante, non vera per tutti i percorsi). Se il fallimento
    catturato QUI avviene PRIMA che `sweep_scaduti` committi (o nella sola
    costruzione dei repository), NESSUNA transizione è avvenuta: innocuo,
    mai una perdita, solo un ritardo — la prossima richiesta a `/itinerary`
    ritenta l'intero sweep quando lo store torna raggiungibile. Ma se
    `sweep_scaduti` ha GIÀ COMMITTATO la transizione `attivo -> expired` per
    un segnale e SOLO IL DEPOSITO DELLA TRACCIA per quel segnale fallisce
    (`deposita`/`place_link_writer` dentro
    `urban_memory.canale_fluttuante.sweep_and_fetch_active`), quella
    situazione NON raggiunge nemmeno questo blocco `except`: è già stata
    intercettata, LOGGATA e ISOLATA per singolo segnale dentro
    `sweep_and_fetch_active` stessa (vedi il suo docstring per il dettaglio
    completo) — e in quel caso specifico la conseguenza NON è "un ritardo,
    poi ritentato": la guardia dell'idempotenza (`WHERE stato='attivo'`)
    impedisce per costruzione a qualunque sweep futuro di ripescare un
    segnale già `expired`, quindi la traccia per quel segnale va persa in
    modo PERMANENTE. Il segnale stesso resta comunque correttamente
    `expired` (non più composto in un itinerario): a perdersi è solo la
    riga del ledger, non l'integrità del canale fluttuante nel suo insieme.

    Fase 3 — consumo degli `:Evento` PROMOSSI (`docs/PROMOZIONE_TRACCIA.md`
    §3, il livello "programmato", diverso dal canale fluttuante "accade
    ORA" sopra): dopo il blocco `eventi_attivi`, questo endpoint legge TUTTI
    gli `:Evento` ricorrenti dal grafo (`api.deps.get_evento_reader`,
    `Neo4jFrizioneClient.eventi_ricorrenti`, che riusa `urban_memory.
    frizione_pattern.leggi_eventi_ricorrenti` — nessuna nuova query Cypher),
    filtra in Python quelli con `stato == 'attivo'` (la query legge
    QUALUNQUE stato, il filtro è deliberatamente qui, non nel Cypher) e li
    converte in `list[contracts.EventoPromosso]` — mapping diretto
    `EventoRicorrente.evento_id -> EventoPromosso.id`, `place_id ->
    place_id`, `temi -> temi`; `cadenza_giorni`/`stato` restano
    nell'`EventoRicorrente` letto qui e NON attraversano il confine verso il
    motore (vedi il docstring di `contracts.EventoPromosso`: quel tipo
    arriva al motore già filtrato ad `attivo`, per costruzione).

    Stessa disciplina, stesso motivo, dello stesso blocco `eventi_attivi`
    sopra: `get_evento_reader()` è chiamato DIRETTAMENTE dentro il `try`
    (mai tramite `Depends` nella firma, per restare catturabile qui), ed è
    un ARRICCHIMENTO OPZIONALE della composizione (una tappa-evento in
    coda), non il cuore della richiesta — un `Neo4jFrizioneClient` assente
    (credenziali mancanti: `get_evento_reader()` ritorna `None`) o un grafo
    irraggiungibile (Aura in pausa — scenario NORMALE, CLAUDE.md) o
    QUALUNQUE altra eccezione imprevista viene catturata e degrada a
    `eventi_promossi=[]`, MAI un 503/500 per questo arricchimento — `/
    itinerary` risponde comunque 200. Il client non può in alcun modo
    influenzare questa lista (letta SOLO dal grafo, mai dal body della
    richiesta): stessa proprietà di sicurezza già garantita per
    `eventi_attivi`."""
    source = get_candidate_source()
    candidates = source.candidates(ctx)
    try:
        score_fn = recommender.costruisci_score_fn(get_event_repository(), candidates)
    except Exception:  # difesa in profondità: il recommender è un arricchimento
        # opzionale, mai un motivo di fallimento di /itinerary — degrada al
        # ranking deterministico (score_fn=None -> calcola_score da solo).
        score_fn = None

    eventi_attivi: list[SegnaleFluttuante] = []
    try:
        eventi_attivi = sweep_and_fetch_active(
            get_segnale_repository(),
            get_traccia_repository(),
            place_link_writer=get_place_link_writer(),
        )
    except Exception:  # difesa in profondità: il canale fluttuante è un
        # arricchimento opzionale, mai un motivo di fallimento di /itinerary
        # — degrada a eventi_attivi=[] (nessuna tappa fluttuante composta).
        # Cattura SOLO fallimenti di sweep_scaduti/fetch_attivi o della
        # costruzione dei repository/writer (mai una perdita: solo un
        # ritardo, vedi il docstring sopra) — un fallimento del deposito
        # della traccia per un SINGOLO segnale già scaduto è isolato PRIMA
        # di arrivare qui (urban_memory.canale_fluttuante.
        # sweep_and_fetch_active, che logga e non propaga).
        eventi_attivi = []

    # Il server SOVRASCRIVE SEMPRE ctx.signal.eventi_attivi con la lettura
    # autorevole dallo store — qualunque valore il client abbia mandato nel
    # body viene ignorato (proprietà di sicurezza, vedi il docstring sopra).
    ctx = ctx.model_copy(
        update={"signal": ctx.signal.model_copy(update={"eventi_attivi": eventi_attivi})}
    )

    eventi_promossi: list[EventoPromosso] = []
    try:
        evento_reader = get_evento_reader()
        if evento_reader is not None:
            eventi_promossi = [
                EventoPromosso(
                    id=evento.evento_id,
                    place_id=evento.place_id,
                    temi=list(evento.temi),
                )
                for evento in evento_reader.eventi_ricorrenti()
                if evento.stato == "attivo"
            ]
    except Exception:  # difesa in profondità: il consumo degli eventi
        # promossi è un arricchimento opzionale, mai un motivo di fallimento
        # di /itinerary — degrada a eventi_promossi=[] (nessuna tappa-evento
        # composta), esattamente come eventi_attivi sopra. Cattura sia
        # l'assenza/fallimento del client (`get_evento_reader`) sia un grafo
        # irraggiungibile durante `eventi_ricorrenti()`
        # (`urban_memory.frizione_pattern.FrizionePatternError`).
        eventi_promossi = []

    return compose_itinerary(
        ctx,
        candidates,
        reason_fn=compose_reason,
        score_fn=score_fn,
        eventi_promossi=eventi_promossi,
    )


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


@app.post("/booking", response_model=Booking, status_code=201)
def create_booking(
    request: BookingRequest,
    repo: _BookingRepositoryDep,
) -> Booking:
    """Prenotazione sul Marketplace (contratto §5, `docs/DATA_CONTRACTS.md`).

    `prezzo_eur` e `prenotabile` NON arrivano MAI dal chiamante (`BookingRequest`
    non li contiene, di proposito: sarebbe un varco per manomettere il prezzo)
    — li legge questo endpoint dal candidato corrente della `CandidateSource`
    (`api.deps.get_candidate_source`, seed o Neo4j), costruendo un
    `VisitorContext` con lo stesso profilo neutro usato in
    `/itinerary/adapt` (`_profilo_neutro_per_candidati`: serve solo a
    soddisfare l'interfaccia, non introduce preferenze). Se
    `request.experience_id` non è tra i candidati risponde 404 (risorsa
    inesistente, non un vincolo di dominio — non un `MarketplaceError`).

    Delega TUTTI i vincoli non negoziabili — stato iniziale `RICHIESTA`,
    rifiuto immediato se `prenotabile=False` — a
    `marketplace.service.request_booking`: un solo punto verificabile, mai
    duplicato qui. Le violazioni di dominio sollevano `MarketplaceError` (o
    una sottoclasse), mappata a 422 da `marketplace_error_handler`. Un
    fallimento INFRASTRUTTURALE dello storage (`MarketplaceStorageError`,
    sollevata da `PostgresBookingRepository` quando configurata via
    `DATABASE_URL`) è mappato a 503 da `marketplace_storage_error_handler`.
    Mai un 500 opaco in nessuno dei due casi. Il repository arriva via
    `Depends` (`api.deps.get_booking_repository`,
    `InMemoryBookingRepository` finché `DATABASE_URL` non è configurato)
    invece di essere chiamato direttamente: così un test può sostituirlo con
    `app.dependency_overrides` senza toccare la configurazione reale.

    `confirm_booking` non è esposto da questo BFF in questa wave (fuori
    scope: vedi `docs/DATA_CONTRACTS.md` §5)."""
    source = get_candidate_source()
    ctx = VisitorContext(
        person_id=request.person_id,
        profile=_profilo_neutro_per_candidati(),
        signal=_segnale_neutro_per_candidati(),
    )
    candidates = source.candidates(ctx)
    candidato = next(
        (c for c in candidates if c.experience.id == request.experience_id), None
    )
    if candidato is None:
        raise HTTPException(
            status_code=404,
            detail=f"esperienza id={request.experience_id!r} non trovata",
        )
    return marketplace.request_booking(
        repo,
        request,
        prezzo_eur=candidato.experience.prezzo_eur or 0.0,
        prenotabile=candidato.experience.prenotabile,
        orari_apertura=candidato.experience.orari_apertura,
    )


@app.post("/events", status_code=202)
def submit_behavior_event(
    event: BehaviorEvent,
    repo: _EventRepositoryDep,
) -> None:
    """Registra un evento comportamentale (contratto §6/§8,
    `docs/DATA_CONTRACTS.md`) per il Recommender ML (Wave 3b).

    `202 Accepted` (non 201, a differenza di `/memory`/`/booking`): questo
    endpoint non crea una risorsa interrogabile da un `GET` — è un segnale
    comportamentale accodato per l'aggregazione, coerente con
    `docs/DATA_CONTRACTS.md` §8 (`POST /events (BehaviorEvent) -> 202`).

    Delega la persistenza a `repo.record(evento)`
    (`recommender.BehaviorEventRepository`, iniettato via `Depends` —
    `api.deps.get_event_repository`, `InMemoryBehaviorEventRepository`
    finché `DATABASE_URL` non è configurato): così un test può sostituirlo
    con `app.dependency_overrides` senza toccare la configurazione reale.
    Un fallimento INFRASTRUTTURALE di storage
    (`recommender.RecommenderStorageError`) è mappato a 503 da
    `event_storage_error_handler`, mai a un 500 opaco.

    `BehaviorEvent.person_id` è uno pseudonimo: non viene MAI loggato qui, né
    altrove in questo endpoint — stesso principio di `person_id`/
    `contributor_id` negli altri endpoint di questo BFF."""
    repo.record(event)


@app.get("/dashboard/index", response_model=DashboardIndexResponse)
def dashboard_index(
    periodo: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> DashboardIndexResponse:
    """Aggregato di periodo dell'Urban Intelligence Index (contratto §7,
    `docs/DATA_CONTRACTS.md`; Wave 4). Wrapper PURO attorno a
    `intelligence_index.dashboard.indice_per_dashboard`: nessuna logica di
    calcolo qui, solo assemblaggio dei parametri iniettati (STESSO pattern
    di `scripts/verifica_index.py`).

    Fonti (tutte lette direttamente, mai tramite `Depends`, stesso motivo di
    `get_candidate_source()` in `create_itinerary`):
    - `esperienze_per_id(get_candidate_source())` — catalogo, seed o Neo4j.
    - `get_metrics_source().grado_semantico()` /
      `.non_connected_place_pairs(at=inizio)` — grafo, seed o Neo4j.
    - `get_event_source().events_in_period(inizio, fine)` — eventi
      comportamentali, in-memory o Postgres.
    - `get_memory_repository().list_pending() + .list_curated()` — TUTTI i
      contributi Urban Memory del periodo, non solo i curati (decisione già
      presa e documentata in `services/intelligence-index/README.md`).

    `itinerari_periodo=[]` sempre esplicito: nessuna persistenza reale di
    itinerari oggi (buco nei dati dichiarato, `docs/LIMITI.md`), mai un
    default silenzioso diverso da lista vuota.

    `periodo` è vincolato `pattern=r"^\d{4}-\d{2}$"` a livello di query
    (stesso principio di `ora: Query(ge=0, le=23)` su `dashboard_flows`
    sotto): una stringa malformata (es. `"abc"`, `"2026"`) è rifiutata con
    422 dalla validazione di FastAPI/Pydantic PRIMA di raggiungere
    `intervallo_periodo`. Il pattern valida solo la FORMA, non il range del
    mese: un `periodo` sintatticamente valido ma semanticamente assurdo
    (es. `"2026-13"`) fa sollevare `ValueError` a `intervallo_periodo`,
    catturato qui sotto e rilanciato come `HTTPException(422)` — stesso
    esito del client (422), motivo diverso (validazione a monte vs. a
    valle), mai un 500 opaco.

    Risponde SEMPRE 200 (a valle della validazione di `periodo`):
    `indice_per_dashboard` cattura già `DatiInsufficientiError`
    internamente e la traduce in `disponibile=False`, non la lascia mai
    propagare fin qui. Un fallimento INFRASTRUTTURALE
    (`IndexStorageError`/`MemoryStorageError`) risponde 503 (vedi
    `index_storage_error_handler`/`memory_storage_error_handler`), mai un
    500 opaco."""
    fonte_metriche = get_metrics_source()
    catalogo = indice_esperienze_per_id(get_candidate_source())
    grado = fonte_metriche.grado_semantico()
    try:
        inizio, fine = intervallo_periodo(periodo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    non_connesse, _denominatore = fonte_metriche.non_connected_place_pairs(at=inizio)
    eventi = get_event_source().events_in_period(inizio, fine)
    repo_memoria = get_memory_repository()
    memorie = repo_memoria.list_pending() + repo_memoria.list_curated()
    return indice_per_dashboard(
        periodo=periodo,
        eventi=eventi,
        esperienze_per_id=catalogo,
        grado_semantico=grado,
        n_luoghi_disponibili=len(grado),
        non_connesse_a_inizio_periodo=non_connesse,
        itinerari_periodo=[],
        memorie=memorie,
    )


@app.get("/dashboard/flows", response_model=DashboardFlowsResponse)
def dashboard_flows(
    periodo: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    giorno: Annotated[date | None, Query()] = None,
    ora: Annotated[int | None, Query(ge=0, le=23)] = None,
) -> DashboardFlowsResponse:
    """Heatmap dei flussi per luogo (contratto §7, `docs/DATA_CONTRACTS.md`;
    Wave 4). Wrapper PURO attorno a `intelligence_index.dashboard.
    celle_flusso`: nessuna logica di calcolo qui, solo assemblaggio dei
    parametri iniettati — STESSE fonti di `dashboard_index` sopra, tranne
    `non_connected_place_pairs`/Urban Memory (non servono a `celle_flusso`).

    `ora` è vincolato `ge=0, le=23` anche qui a livello di query (oltre che
    nel modello Pydantic sottostante): un valore fuori range produce un 422
    leggibile prima ancora di costruire il payload. `periodo` è vincolato
    `pattern=r"^\d{4}-\d{2}$"` sullo STESSO principio (vedi `dashboard_index`
    sopra per il dettaglio validazione a monte/a valle): forma malformata ->
    422 dal `Query`, mese fuori range (es. `"2026-13"`) -> `ValueError` di
    `intervallo_periodo` catturato qui sotto e rilanciato come
    `HTTPException(422)`.

    Una `FlowCell` per OGNI luogo del grafo (`grado_semantico`), gated
    indipendentemente a k=10 sui `person_id` distinti di ciascuna cella —
    zero tappe e 1-9 persone producono lo STESSO stato osservabile
    (`disponibile=False`), mai distinguibili dall'esterno (vedi
    `intelligence_index.dashboard.celle_flusso`). Risponde SEMPRE 200 (a
    valle della validazione di `periodo`): non esiste, per questo endpoint,
    alcuno stato "dato insufficiente" a livello di intera risposta (solo per
    singola cella, già rappresentato nel contratto)."""
    fonte_metriche = get_metrics_source()
    catalogo = indice_esperienze_per_id(get_candidate_source())
    grado = fonte_metriche.grado_semantico()
    try:
        inizio, fine = intervallo_periodo(periodo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    eventi = get_event_source().events_in_period(inizio, fine)
    return celle_flusso(
        periodo=periodo,
        eventi_periodo=eventi,
        esperienze_per_id=catalogo,
        grado_semantico=grado,
        giorno=giorno,
        ora=ora,
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


def _segnale_neutro_per_candidati() -> Signal:
    """`Signal` neutro usato SOLO per costruire il `VisitorContext` richiesto
    da `CandidateSource.candidates` in `POST /booking`, dove `BookingRequest`
    non trasporta alcun segnale (meteo, affollamento, stanchezza, ora): non
    influenza la scelta, `SeedCandidateSource` e `Neo4jCandidateSource` non
    filtrano su segnale (è responsabilità dell'Experience Engine, non
    toccato da questo endpoint — qui serve solo a leggere `prezzo_eur` e
    `prenotabile` dell'esperienza richiesta)."""
    return Signal(
        meteo="sereno",
        affollamento={},
        stanchezza=0.0,
        ora=time(12, 0),
    )


# Impronta esplicita: le Settings vengono lette a import-time per fallire
# in modo leggibile se la configurazione è malformata, ma nessuna variabile
# è obbligatoria (vedi api/settings.py).
get_settings()
