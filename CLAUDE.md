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

| Layer | Tecnologia |
|---|---|
| App | Flutter |
| BFF / API | FastAPI (Python 3.12, Pydantic v2) |
| Urban Knowledge Graph | Neo4j (Cypher) |
| Transazionale + eventi + memoria | PostgreSQL |
| RAG | Vector DB (Qdrant) + Anthropic API |
| Recommender | ML classico su eventi comportamentali |

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
