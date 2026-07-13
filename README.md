# Lucca Soul Lab — Engine (orchestrator + multi-agent scaffold)

**v2 — allineato al White Paper v1.0 (architettura congelata).**

Scaffold Claude Code per costruire il motore di **Lucca Soul Lab** — *Urban Experience
Intelligence Platform*. La sessione Claude Code fa da **orchestratore** e delega a subagent
specialisti.

> «Le Smart City raccolgono dati. Le città intelligenti generano significato.»

## Cosa c'è

```
CLAUDE.md                    # memoria di progetto: tassonomia congelata, regole, protocollo
RUNBOOK.md                   # come lanciare (guidato / lancio unico presidiato)
docker-compose.yml           # Postgres, Neo4j, Qdrant
scripts/bootstrap.sh         # Wave 0 in un comando (Linux/macOS/WSL)
scripts/bootstrap.ps1        # idem, per Windows PowerShell
docs/
  ARCHITECTURE.md            # i due livelli di orchestrazione + flusso runtime
  DATA_CONTRACTS.md          # tipi condivisi = single source of truth (anti-divergenza)
  BUILD_PLAN.md              # 6 wave, assegnazioni, criteri di accettazione
.claude/agents/              # 12 specialisti
  tech-lead                  # orchestratore/planner (tool Task)
  contract-keeper            # custode dei contratti dati
  graph-architect            # Urban Knowledge Graph (Neo4j)
  rag-engineer               # RAG + assistente conversazionale
  recommender-engineer       # ML recommendation
  experience-engine          # AI Experience Engine — l'unico che DECIDE
  urban-memory-engineer      # Urban Memory — il fossato difendibile   [NUOVO]
  index-engineer             # Urban Intelligence Index + dashboard    [NUOVO]
  ethics-guardian            # Ethical AI Engine (gate, sola lettura)
  api-engineer               # BFF FastAPI
  frontend-engineer          # app Flutter
  test-engineer              # contract + integration test
```

## Due livelli — non confonderli

- **Build-time**: i subagent scrivono il codice (questo scaffold).
- **Run-time**: l'**AI Experience Engine** orchestra grafo + RAG + ML + etica a ogni richiesta.

## Le sei wave

| Wave | Contenuto |
|---|---|
| 0 | Fondamenta & contratti (blocca tutto) |
| 1 | **Proof of Concept**: conversazione → itinerario adattivo |
| 2 | **Urban Memory** — anticipata: è il fossato, e cresce solo con l'uso |
| 3 | Marketplace + Recommender ML |
| 4 | Urban Intelligence Index + Dashboard |
| 5 | Replica (Siena / Ferrara): cambia il dataset, non la tecnologia |

## Avvio  (modalità cloud: Aura + Neon)

1. Copia questi file nella radice del repo, `git init`, `git add -A && git commit`.
2. Lancia il bootstrap — al primo giro crea il `.env` e si ferma:
   - **Linux / macOS / WSL / Git Bash:** `./scripts/bootstrap.sh`
   - **Windows PowerShell:** `.\scripts\bootstrap.ps1`
     (se Windows blocca lo script: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)
3. Compila il `.env`:
   - **Neo4j Aura** → `NEO4J_URI=neo4j+s://...` (NON `bolt://`), `NEO4J_USERNAME`, `NEO4J_PASSWORD`
   - **Neon** → `DATABASE_URL=postgresql://...?sslmode=require` (stringa **diretta** per le migrazioni)
   - `ANTHROPIC_API_KEY`
4. Rilancia il bootstrap — verifica le connessioni remote, avvia Qdrant, crea lo scheletro.
   Per il check delle credenziali (il più utile): `pip install neo4j "psycopg[binary]"`
5. Apri Claude Code nel repo e segui `RUNBOOK.md` (Modo A consigliato).

Requisiti: Docker + `docker compose` v2 (serve solo per Qdrant).

> **Aura Free**: si auto-mette in pausa e l'istanza viene **cancellata dopo 30 giorni di
> inattività**. Per questo il seed del grafo è versionato e rieseguibile: il grafo è un artefatto
> ricostruibile, non un archivio. Vale anche come disciplina per la replica su altre città.
> Vuoi zero limiti e zero cloud? Nel `docker-compose.yml` c'è la modalità locale commentata
> (Neo4j **Community Edition**, gratuita e senza limiti di dati).

## Regole non negoziabili

Un solo schema · decide solo l'Experience Engine · privacy by design · **mai** ottimizzare
click/pubblicità/vendite · **visibilità non acquistabile** · spiegabilità obbligatoria ·
consenso e licenza per ogni contributo di Urban Memory.

Il vocabolario è quello del White Paper. Se un nome nel codice diverge, **vince il White Paper**.
