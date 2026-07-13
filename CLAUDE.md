# Lucca Soul Lab — Engine

> **Urban Experience Intelligence Platform** — *The Human Experience Layer for Urban Digital Twins.*
> Questo repo è **il motore**: non racconta la città, la **orchestra**.
> Se funziona a Lucca, lo stesso motore si replica cambiando solo il contenuto locale
> (Siena, Mantova, Urbino, Ferrara…).

> «Le Smart City raccolgono dati. Le città intelligenti generano significato.»

**Fonte di verità concettuale:** il White Paper v1.0 (Volume 1). L'architettura lì definita è
**congelata**: il codice adotta quel vocabolario, non ne inventa uno parallelo. Se un nome qui
diverge dal white paper, il white paper vince.

## Tassonomia congelata (da rispettare nei nomi di moduli, classi ed endpoint)

```
Urban Digital Twin
├── Physical Layer / Infrastructure Layer / Data Layer   (presupposto, non nostro)
└── Urban Cognitive Layer                                ← IL NOSTRO PERIMETRO
      ├── Human Experience Layer     il contatto con le persone
      ├── Urban Knowledge Graph      la conoscenza della città
      ├── AI Experience Engine       il motore che compone (unico che DECIDE)
      ├── Ethical AI Engine          il sistema decisionale
      ├── Urban Intelligence Index   gli indicatori
      └── Urban Memory               la memoria collettiva
```

## Due livelli di orchestrazione — non confonderli

1. **Build-time (questo Claude Code).** La sessione principale è l'**orchestratore**: pianifica,
   delega ai subagent in `.claude/agents/`, integra, fa passare i gate. NON scrive codice di
   implementazione se esiste un subagent competente.
2. **Run-time (dentro il prodotto).** L'**AI Experience Engine** orchestra Knowledge Graph, RAG,
   Recommender e vincoli etici a ogni richiesta. È un componente che i subagent costruiscono.

## Stack

| Layer | Tecnologia | Dove gira |
|---|---|---|
| App | Flutter | locale |
| BFF / API | FastAPI (Python 3.12, Pydantic v2) | locale |
| Urban Knowledge Graph | Neo4j | **Aura (cloud)** — `neo4j+s://` |
| Transazionale + eventi + memoria | PostgreSQL | **Neon (cloud)** — `sslmode=require` |
| RAG / Vector store | **pgvector dentro Neon** + Anthropic API | cloud (nessun Docker) |
| Recommender | ML classico su eventi comportamentali | locale |

> **Ambiente: Windows / PowerShell.** Gli script per l'utente vanno in PowerShell (`.ps1`) o
> come comandi Python. Non dare per scontato `bash`.
>
> **DUE PROFILI, UN SOLO CODICE.** Il progetto gira su due macchine con configurazioni diverse:
>
> | | Notebook (no Docker) | PC fisso (con Docker) |
> |---|---|---|
> | Neo4j | Aura cloud (`neo4j+s://`) | Community locale (`bolt://`) |
> | Postgres | Neon (`sslmode=require`) | Postgres locale |
> | Vector store | pgvector su Neon | pgvector locale |
>
> **Il codice non deve MAI sapere dove gira.** Tutto passa da `NEO4J_URI` e `DATABASE_URL`,
> letti dal `.env`. Niente `if local/cloud` nel codice, niente host hardcoded, niente due
> implementazioni RAG: **pgvector in entrambi i profili**. Se un agente propone Qdrant o un
> percorso specifico per un profilo, è un errore: rifiutalo.

### Connessioni — trappole da evitare
- **Neo4j Aura vuole `neo4j+s://`** (TLS), non `bolt://`. Le variabili sono `NEO4J_URI`,
  `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
- **Neon richiede `sslmode=require`**. Per le **migrazioni** usa la stringa **diretta**
  (senza `-pooler`); quella pooled è per i client ad alta concorrenza.
- **Aura Free si auto-mette in pausa e viene cancellata dopo 30 giorni di inattività.**
  Conseguenza vincolante: il seed del grafo è **versionato** in `services/graph/cypher/` e
  dev'essere **rieseguibile da zero in un comando**. Nessun dato vive solo su Aura.
- **Vector store = pgvector dentro Neon.** Nessun Qdrant. Abilitazione una tantum:
  `CREATE EXTENSION IF NOT EXISTS vector;` (l'estensione si chiama `vector`, non `pgvector`).
  Gli embedding stanno in colonne `VECTOR(EMBEDDING_DIM)`; indici HNSW per la similarità.
- Credenziali SOLO nel `.env` (mai nel codice, mai nei commit).

Layout target:
```
apps/lucca_soul_app          # Flutter
services/api                 # BFF FastAPI (unico ingresso dell'app)
services/experience-engine   # AI Experience Engine (il "brevetto")
services/graph               # Urban Knowledge Graph: schema, Cypher, ingestion
services/rag                 # RAG + assistente conversazionale
services/recommender         # ML recommendation
services/urban-memory        # Urban Memory: conferimenti, consenso, curatela
services/intelligence-index  # Urban Intelligence Index: aggregazioni anonime
packages/contracts           # tipi condivisi (Pydantic) — SINGLE SOURCE OF TRUTH
docs/                        # ARCHITECTURE, DATA_CONTRACTS, BUILD_PLAN
```

## Protocollo di orchestrazione (sessione principale)

Per ogni wave del `docs/BUILD_PLAN.md`:
1. **Contracts first.** Nessun modulo parte finché i tipi condivisi non sono in
   `docs/DATA_CONTRACTS.md` + `packages/contracts`. Le modifiche allo schema passano SOLO da
   `contract-keeper`.
2. **Delega in parallelo** i moduli indipendenti (grafo, RAG, recommender, memory…).
3. **Ethics gate.** Ogni cambiamento a recommender / experience-engine / intelligence-index /
   urban-memory passa da `ethics-guardian` prima del merge.
4. **Tests always.** `test-engineer` scrive test di contratto e integrazione. Nessun modulo è
   "fatto" senza test verdi.
5. **Integra** e aggiorna il BUILD_PLAN (spunta i criteri di accettazione).

## Regole non negoziabili (valgono per TUTTI i subagent)

- **Un solo schema.** I campi canonici sono in `docs/DATA_CONTRACTS.md`. Gli agenti li
  **importano**, non li ridefiniscono.
- **Decide un solo componente.** Il grafo propone, il recommender ordina, l'LLM racconta:
  nessuno di essi sceglie. Sceglie l'Experience Engine — perché un vincolo applicato in un solo
  punto è verificabile, distribuito no.
- **Privacy by design.** `visitor_id` è uno pseudonimo. Nessun PII in log, eventi, dashboard.
- **Obiettivo etico.** Si ottimizzano *distribuzione dei flussi, valorizzazione locale,
  inclusione, accessibilità, sostenibilità, spiegabilità* — MAI click / pubblicità / vendite.
  **Nessuno spazio è acquistabile:** un partner compare solo se coerente. Non esiste un prezzo
  che modifichi questa regola.
- **Spiegabilità obbligatoria.** Ogni raccomandazione e ogni tappa espone un `reason` leggibile
  in italiano. La spiegabilità rende il vincolo etico auditabile da un'amministrazione.
- **Urban Memory cresce con l'uso.** Ogni esperienza vissuta può alimentare la memoria: non è un
  archivio da riempire una volta. Il conferimento richiede consenso esplicito e licenza tracciata.
- **Italiano** nel dominio, inglese nei nomi dei pilastri (sono termini congelati).

## Glossario di dominio (allineato al white paper)

`Visitatore` · `Cittadino` · `ProfiloEmozionale` (curioso, contemplativo, ama-arte, con-bambini,
poco-tempo…) · `Segnale` (meteo, affollamento, stanchezza, ora, evento) · `Esperienza` ·
`Itinerario` · `Bottega` · `Memoria` (contributo alla Urban Memory) · `UrbanIntelligenceIndex`.

**I cinque clienti:** Turista · Cittadino · Operatori · Comune · Sviluppatori.
Il Cittadino non paga: alimenta la Urban Memory ed è la condizione di sostenibilità sociale del
sistema. Non trattarlo come un utente di seconda classe.

## Convenzioni

- Python tipizzato, Pydantic v2, `ruff` + `mypy`, `pytest`.
- Cypher versionato in `services/graph/cypher/`.
- Un solo ingresso per l'app: il BFF (`services/api`). L'app non chiama mai i servizi interni.
