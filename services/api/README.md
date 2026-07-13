# Lucca Soul — BFF (`services/api`)

Unico ingresso per l'app Flutter. Il BFF chiama i servizi interni
(experience-engine, graph, rag, recommender); l'app non tocca mai i servizi
diretti. Import name del pacchetto: `api` (nome distribuzione: `lucca-api`).

Wave 0: solo fondamenta — `GET /health` e `GET /contracts/version`. Gli
endpoint applicativi (`/session/onboarding`, `/itinerary`,
`/itinerary/adapt`, `/events`, `/dashboard/flows`) arrivano nelle wave
successive del `docs/BUILD_PLAN.md`.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts` è la single source of truth
degli schemi ed è una dipendenza **locale** (non su un indice pip): va
installata a parte, insieme al BFF, in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/api
```

## Configurazione

Copia il `.env.example` (profilo cloud, Aura + Neon) o `.env.local.example`
(profilo locale, con `docker compose up -d`) alla radice del repo in `.env`.
In Wave 0 tutte le variabili sono opzionali: `/health` risponde 200 anche
senza database attivi. Il codice non sa mai se gira in cloud o in locale:
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
