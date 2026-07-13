# Lucca Soul — BFF (`services/api`)

Unico ingresso per l'app Flutter. Il BFF chiama i servizi interni
(experience-engine, graph, rag, recommender); l'app non tocca mai i servizi
diretti. Import name del pacchetto: `api` (nome distribuzione: `lucca-api`).

Wave 1: pipeline completa di raccomandazione.

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

`POST /events` e `GET /dashboard/flows` arrivano nelle wave successive del
`docs/BUILD_PLAN.md`.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts`, `services/graph`, `services/rag`
e `services/experience-engine` sono dipendenze **locali** (non su un indice
pip): vanno installate a parte, insieme al BFF, in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/graph -e services/rag `
    -e services/experience-engine -e services/api
```

## Sorgente dei candidati del grafo

`api/deps.get_candidate_source` sceglie la `CandidateSource` leggendo SOLO il
`.env` (mai un `if local/cloud` nel codice): se `NEO4J_URI` (+ username e
password) sono configurati usa `Neo4jCandidateSource` (Aura `neo4j+s://` o
Neo4j Community `bolt://` locale — lo schema dell'URI vive solo nel `.env`);
altrimenti ricade su `SeedCandidateSource`, lo stesso dataset canonico
versionato in `services/graph/graph/seed_lucca.py`. L'istanza è creata una
sola volta (`lru_cache`), non ad ogni richiesta.

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
