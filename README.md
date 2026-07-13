# Lucca Soul Lab — Engine (orchestrator + multi-agent scaffold)

**v4 — cloud puro, zero infrastruttura locale.** Allineato al White Paper v1.0.

Scaffold Claude Code per costruire il motore di **Lucca Soul Lab** — *Urban Experience
Intelligence Platform*. La sessione Claude Code fa da **orchestratore** e delega a subagent
specialisti.

> «Le Smart City raccolgono dati. Le città intelligenti generano significato.»

## Due profili, un solo codice

Il codice **non sa dove gira**: cambia solo il `.env`.

| | Profilo CLOUD (senza Docker) | Profilo LOCALE (con Docker) |
|---|---|---|
| Urban Knowledge Graph | Neo4j **Aura** (`neo4j+s://`) | Neo4j **Community** (`bolt://`) |
| Dati, eventi, Urban Memory | **Neon** (`sslmode=require`) | Postgres locale |
| Vector store (RAG) | **pgvector** dentro Neon | **pgvector** dentro Postgres |
| Serve Docker? | **no** | sì |

Il vector store è **pgvector in entrambi i profili**: una sola implementazione RAG da mantenere.
Il profilo cloud gira anche su un portatile aziendale bloccato (nessun diritto di amministratore).

Il bootstrap **rileva da solo** il profilo leggendo il `.env` e, se è locale, avvia Docker.

## Cosa c'è

```
CLAUDE.md                    # memoria di progetto: tassonomia congelata, regole, protocollo
RUNBOOK.md                   # come lanciare (guidato / lancio unico presidiato)
scripts/bootstrap.ps1        # Wave 0 in un comando (Windows PowerShell)
scripts/bootstrap.sh         # idem (Linux/macOS/WSL)
docker-compose.yml           # solo per il PROFILO LOCALE
.env.example                 # profilo CLOUD  (Aura + Neon)
.env.local.example           # profilo LOCALE (Docker)
docs/
  ARCHITECTURE.md            # i due livelli di orchestrazione + flusso runtime
  DATA_CONTRACTS.md          # tipi condivisi = single source of truth (anti-divergenza)
  BUILD_PLAN.md              # 6 wave, assegnazioni, criteri di accettazione
.claude/agents/              # 12 specialisti
  tech-lead                  # orchestratore/planner (tool Task)
  contract-keeper            # custode dei contratti dati
  graph-architect            # Urban Knowledge Graph (Aura)
  rag-engineer               # RAG + assistente conversazionale (pgvector)
  recommender-engineer       # ML recommendation
  experience-engine          # AI Experience Engine — l'unico che DECIDE
  urban-memory-engineer      # Urban Memory — il fossato difendibile
  index-engineer             # Urban Intelligence Index + dashboard
  ethics-guardian            # Ethical AI Engine (gate, sola lettura)
  api-engineer               # BFF FastAPI
  frontend-engineer          # app Flutter
  test-engineer              # contract + integration test
```

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
2. Installa i client:
   ```
   pip install neo4j "psycopg[binary]"
   ```
3. Lancia il bootstrap — al primo giro crea il `.env` e si ferma:
   - **Windows PowerShell:** `.\scripts\bootstrap.ps1`
     (se Windows blocca lo script: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)
   - **Linux / macOS / WSL:** `./scripts/bootstrap.sh`
4. Compila il `.env`:
   - **Profilo CLOUD** (da `.env.example`): `NEO4J_URI=neo4j+s://...` (NON `bolt://`),
     `DATABASE_URL=postgresql://...?sslmode=require` (stringa **diretta**, senza `-pooler`),
     `ANTHROPIC_API_KEY`.
   - **Profilo LOCALE** (da `.env.local.example`): basta copiarlo e aggiungere `ANTHROPIC_API_KEY`.
     Il bootstrap avvierà Docker da solo.
5. Rilancia il bootstrap: verifica le connessioni e **abilita pgvector** su Neon automaticamente.
6. Apri Claude Code nel repo e segui `RUNBOOK.md` (Modo A consigliato).

> **Aura Free**: si auto-mette in pausa e l'istanza viene **cancellata dopo 30 giorni di
> inattività**. Per questo il seed del grafo è versionato e rieseguibile in un comando: il grafo
> è un artefatto ricostruibile, non un archivio. È anche la disciplina che serve per la Wave 5.

## Regole non negoziabili

Un solo schema · decide solo l'Experience Engine · privacy by design · **mai** ottimizzare
click/pubblicità/vendite · **visibilità non acquistabile** · spiegabilità obbligatoria ·
consenso e licenza per ogni contributo di Urban Memory.

Il vocabolario è quello del White Paper. Se un nome nel codice diverge, **vince il White Paper**.
