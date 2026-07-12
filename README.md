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
scripts/bootstrap.sh         # Wave 0 in un comando
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

## Avvio

1. Copia questi file nella radice del repo, `git init`, `git add -A && git commit`.
2. `./scripts/bootstrap.sh` — scheletro cartelle, `.env`, e infrastruttura dati su Docker.
   Metti la tua `ANTHROPIC_API_KEY` nel `.env` generato.
3. Apri Claude Code nel repo e segui `RUNBOOK.md` (Modo A consigliato).

Requisiti: Docker + `docker compose` v2.

## Regole non negoziabili

Un solo schema · decide solo l'Experience Engine · privacy by design · **mai** ottimizzare
click/pubblicità/vendite · **visibilità non acquistabile** · spiegabilità obbligatoria ·
consenso e licenza per ogni contributo di Urban Memory.

Il vocabolario è quello del White Paper. Se un nome nel codice diverge, **vince il White Paper**.
