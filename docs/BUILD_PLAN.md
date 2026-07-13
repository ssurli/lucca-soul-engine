# BUILD PLAN — Waves

Mappato sulla roadmap del White Paper (Fase 0 Ricerca → 1 PoC → 2 Living Lab → 3 Smart City →
4 Replica nazionale → 5 Replica europea). Questo repo costruisce le **Fasi 1–4**.

Ogni wave: obiettivo → agenti → criteri di accettazione. L'orchestratore esegue una wave alla volta.

---

## Wave 0 — Fondamenta & contratti  *(blocca tutto il resto)*
- **contract-keeper**: crea `packages/contracts` (Pydantic v2) da `docs/DATA_CONTRACTS.md`.
- **api-engineer**: scaffold FastAPI, integra `docker-compose.yml`, endpoint `/health`.
- **test-engineer**: setup pytest + contract test che importano `packages/contracts`.
- ✅ **Accettazione:** connessioni Aura + Neon verificate; pgvector abilitato; contratti
  importabili da tutti i servizi; CI verde. *(Il profilo locale con `docker compose up` resta
  opzionale: stesso codice, cambia solo il `.env`.)*

## Wave 1 — Proof of Concept: la conversazione → l'itinerario  *(= Fase 1 del white paper)*
- **graph-architect**: schema Neo4j + seed Lucca (10-15 luoghi, 5 botteghe, esperienze) + query candidati.
- **rag-engineer**: onboarding conversazionale ("Hai voglia di perderti?") → `EmotionalProfile`; genera `reason`.
- **experience-engine**: motore *a regole* — grafo + segnale + vincoli → `Itinerary`;
  endpoint `/itinerary` e `/itinerary/adapt` (pioggia, affollamento, stanchezza).
- **api-engineer**: espone gli endpoint sul BFF.
- **frontend-engineer**: onboarding + itinerario + card adattiva.
- **ethics-guardian**: gate su distribuzione, accessibilità, spiegabilità, visibilità non acquistabile.
- **test-engineer**: integrazione onboarding→itinerario e riscrittura da segnale.
- ✅ **Accettazione:** due profili diversi ⇒ due itinerari diversi; `adapt` riscrive su pioggia e su
  affollamento; **ogni tappa ha un `reason`**; nessun percorso viola `accessibile`.
  **→ SODDISFATTA** (2026-07-13): coperta da `tests/test_integration_wave1.py` end-to-end sul BFF
  (seed offline); ethics-guardian **PASS** su tutti e 7 i punti dopo la correzione
  "attribuzione fuori dallo score". *Nota: verificato con `SeedCandidateSource`; la verifica
  live su Aura (stesso seed via `python -m graph.loader`) resta da eseguire sul profilo cloud.*

> È la dimostrazione centrale del white paper. Se questa wave passa, il concetto è provato.

## Wave 2 — Urban Memory  *(il fossato — anticipata di proposito)*
- **urban-memory-engineer**: conferimento contributi, consenso, licenze, curatela, aggancio al grafo.
- **graph-architect**: relazione `(:Memoria)-[:RIGUARDA]->(...)`; la memoria arricchisce il KG.
- **frontend-engineer**: conferimento leggero e contestuale (non un modulo burocratico); vista Cittadino.
- **ethics-guardian**: gate su consenso, pseudonimizzazione, licenze.
- **test-engineer**: nessun contributo persiste senza `consenso=True` e `licenza`.
- ✅ **Accettazione:** un'esperienza vissuta genera un contributo; il contributo compare nel grafo;
  il Cittadino ha un percorso d'uso proprio.

> **Perché prima del marketplace:** Urban Memory è ciò che nessun concorrente può copiare, e cresce
> solo con l'uso. Prima comincia ad accumularsi, prima il fossato esiste.

## Wave 3 — Marketplace + Recommender ML
- **api-engineer**: esperienze prenotabili, ingestion `/events`.
- **recommender-engineer**: modello su `BehaviorEvent` che riordina i candidati (con `reason`).
- **ethics-guardian**: gate sull'obiettivo — mai click/vendite; nessuna visibilità acquistabile.
- **test-engineer**: test che il recommender rispetti i vincoli etici.
- ✅ **Accettazione:** il recommender migliora la pertinenza senza aumentare la concentrazione dei
  flussi; tutto resta spiegabile.

## Wave 4 — Urban Intelligence Index + Dashboard  *(= Fase 3, Smart City)*
- **index-engineer**: aggregazioni anonime, calcolo degli 8 indicatori, endpoint `/dashboard/*`.
- **frontend-engineer**: dashboard Comune (heatmap + Index), viste hotel e museo.
- **ethics-guardian**: soglie di aggregazione, non re-identificabilità.
- ✅ **Accettazione:** nessun PII derivabile e nessuna cella re-identificante; gli 8 indicatori
  calcolati; `distribuzione_flussi` visibile e non nascosto.

## Wave 5 — Replica  *(= Fase 4)*
- **graph-architect**: nuovo seed di contenuto (Siena / Ferrara). Tecnologia invariata.
- ✅ **Accettazione:** cambiando **solo il dataset**, il motore genera itinerari per la nuova città.
  È la prova di scalabilità su cui poggia l'intero investment case.

---

## KICKOFF — Modo A (guidato, consigliato)

```
Leggi CLAUDE.md e docs/. Sei l'orchestratore. Esegui SOLO la Wave 0 del BUILD_PLAN,
poi fermati e riepiloga i criteri di accettazione prima di chiedermi il via per la Wave 1.
```

## KICKOFF — Modo B (lancio unico presidiato)

Vedi `RUNBOOK.md`: una sola incollata, con gate automatici che fermano la corsa se i test o
l'ethics-guardian falliscono.

> **Consiglio.** Parti lean: per le Wave 0–1 bastano contract-keeper, api-engineer,
> graph-architect, experience-engine, rag-engineer, frontend-engineer, test-engineer.
> Attiva urban-memory, recommender e index dalle wave successive.
