# Lucca Soul — BFF (`services/api`)

Unico ingresso per l'app Flutter. Il BFF chiama i servizi interni
(experience-engine, graph, rag, recommender); l'app non tocca mai i servizi
diretti. Import name del pacchetto: `api` (nome distribuzione: `lucca-api`).

Wave 1: pipeline completa di raccomandazione. Wave 2: Urban Memory.

- `GET /health`, `GET /contracts/version` — fondamenta (Wave 0).
- `POST /session/onboarding` (`OnboardingRequest` -> `EmotionalProfile`) —
  delega a `rag.onboarding.profile_from_answers`.
- `POST /itinerary` (`VisitorContext` -> `Itinerary`) — candidati dalla
  `CandidateSource` configurata (vedi `api/deps.py`), composti da
  `experience_engine.engine.compose_itinerary` con i `reason` di
  `rag.reasons.compose_reason`.
- `POST /itinerary/adapt` (`AdaptRequest` -> `Itinerary`) — riscrittura via
  `experience_engine.engine.adapt_itinerary` con i `reason` di
  `rag.reasons.adapt_reason`.
- `POST /memory` (`MemoryContribution` -> 201 `MemoryContribution`, sempre
  con `curato=False`) — delega a
  `urban_memory.service.submit_contribution`. Un conferimento senza
  `consenso=True`, senza `licenza` o senza `contributor_id` non persiste
  MAI: solleva `ConsentRequiredError` / `LicenseRequiredError` /
  `PseudonymRequiredError` (tutte `urban_memory.UrbanMemoryError`), mappate
  da `urban_memory_error_handler` a **422** con un messaggio italiano
  esplicativo (`"conferimento rifiutato: ..."`), mai a un 500. `licenza`
  vuota è già rifiutata prima, a **422**, dalla validazione Pydantic del
  contratto (`min_length=1`). Il servizio non logga mai `testo`,
  `media_uri` o `contributor_id`.
- `GET /memory/{place_id}` (-> `list[MemoryContribution]`) — SOLO contributi
  **curati** (`curato=True`) che riguardano quel `place_id`, via
  `urban_memory.service.contributions_for_place`.

`POST /events` e `GET /dashboard/flows` arrivano nelle wave successive del
`docs/BUILD_PLAN.md`.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts`, `services/graph`, `services/rag`,
`services/experience-engine` e `services/urban-memory` sono dipendenze
**locali** (non su un indice pip): vanno installate a parte, insieme al BFF,
in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/graph -e services/rag `
    -e services/experience-engine -e services/urban-memory -e services/api
```

## Sorgente dei candidati del grafo

`api/deps.get_candidate_source` sceglie la `CandidateSource` leggendo SOLO il
`.env` (mai un `if local/cloud` nel codice): se `NEO4J_URI` (+ username e
password) sono configurati usa `Neo4jCandidateSource` (Aura `neo4j+s://` o
Neo4j Community `bolt://` locale — lo schema dell'URI vive solo nel `.env`);
altrimenti ricade su `SeedCandidateSource`, lo stesso dataset canonico
versionato in `services/graph/graph/seed_lucca.py`. L'istanza è creata una
sola volta (`lru_cache`), non ad ogni richiesta.

## Repository della Urban Memory

`api/deps.get_memory_repository` sceglie il `MemoryRepository` leggendo SOLO
`DATABASE_URL` (stesso pattern di `get_candidate_source`, nessun `if
local/cloud`): se configurato usa `PostgresMemoryRepository.from_env()`,
altrimenti `InMemoryMemoryRepository`. **ATTENZIONE:**
`PostgresMemoryRepository` (Neon in cloud, Postgres locale via Docker) è
predisposta in `services/urban-memory` ma NON ancora implementata in questa
wave — ogni suo metodo solleva `NotImplementedError` (nessun database è
raggiungibile da lì). In pratica, finché non viene implementata, tenere
`DATABASE_URL` non configurato in Wave 2: `/memory` e `/memory/{place_id}`
funzionano allora su `InMemoryMemoryRepository` (non persiste tra processi;
è il percorso verificato dallo smoke test di questo servizio). L'istanza è
creata una sola volta (`lru_cache`).

## Configurazione

Copia il `.env.example` (profilo cloud, Aura + Neon) o `.env.local.example`
(profilo locale, con `docker compose up -d`) alla radice del repo in `.env`.
Tutte le variabili sono opzionali: `/health` risponde 200 anche senza
database attivi, e senza `NEO4J_URI` configurato `/itinerary` e
`/itinerary/adapt` funzionano comunque sul seed versionato
(`SeedCandidateSource`). Il codice non sa mai se gira in cloud o in locale:
legge solo `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`,
`DATABASE_URL` dal `.env`.

## Avvio

Dalla radice del repo (perché `Settings` legge `.env` dalla working directory):

```powershell
uvicorn api.main:app --reload
```

- `GET http://127.0.0.1:8000/health` → `{"status": "ok", "service": "lucca-soul-bff", "version": "..."}`
- `GET http://127.0.0.1:8000/docs` → OpenAPI (fonte autoritativa dell'API)
- `GET http://127.0.0.1:8000/contracts/version` → conferma che gli schemi vengono da `packages/contracts`

## Test rapido senza avviare un server

```powershell
python -c "from starlette.testclient import TestClient; from api.main import app; print(TestClient(app).get('/health').json())"
```
