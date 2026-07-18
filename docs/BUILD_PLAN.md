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
  **→ SODDISFATTA** (2026-07-14): `tests/test_integration_wave2.py` copre esperienza→contributo→
  curatela→pubblicazione e l'aggancio `(:Memoria)-[:RIGUARDA]->(...)`; ethics-guardian **PASS**
  su consenso, licenza, pseudonimizzazione, curatela, Cittadino di prima classe, no monetizzazione.
  **Persistenza reale** (2026-07-14): `PostgresMemoryRepository` (psycopg 3) su Neon/Postgres,
  migrazione `sql/00_memory_schema.sql` idempotente con `CHECK(consenso=true)`/`CHECK(licenza)`
  come backstop DB; `MemoryStorageError`→**503** sul BFF (mai 500 opaco); writer live dei nodi
  `:Memoria` (`link_to_graph`). Persistenza provata contro Postgres reale (sopravvive alla
  riapertura); ethics-guardian **PASS** anche sul percorso di persistenza. Verifica utente:
  `python -m urban_memory.migrate` e `python -m urban_memory.verify` col `.env` (vedi
  `services/urban-memory/README.md`). *Resta da eseguire dall'utente la verifica live contro il
  proprio Neon/Aura (non raggiungibili dalla CI).*

> **Perché prima del marketplace:** Urban Memory è ciò che nessun concorrente può copiare, e cresce
> solo con l'uso. Prima comincia ad accumularsi, prima il fossato esiste.

## Wave 3a — Marketplace  *(SOLO prenotazione; il Recommender è la 3b, separata)*
- **contract-keeper**: `Partner` (abbonamento_attivo), esperienza prenotabile (disponibilità,
  prezzo), `Booking`/`BookingStatus`, `CommissionRecord` (dato contabile separato).
- **graph-architect**: seed Partner + flag abbonamento sui candidati (presenza, non score).
- **experience-engine**: filtro duro "partner non attivo → escluso"; guard che lo score resta
  bit-identico a partner/prezzo/commissione.
- **api-engineer**: `services/marketplace` (booking, persistenza Neon, commissione 15%
  registrata DOPO la scelta), endpoint `POST /booking` sul BFF.
- **ethics-guardian**: gate esplicito — la visibilità non è acquistabile; l'abbonamento è
  l'UNICO effetto (presenza sì/no, mai ranking).
- **test-engineer**: test bit-identico (score invariato con/senza partner, prezzo, commissione)
  in CI; test di persistenza booking.
- ✅ **Accettazione:** esperienze prenotabili end-to-end; commissione mai input di scoring;
  partner non attivo sparisce dai candidati senza toccare lo score altrui; test bit-identico
  verde in CI; ethics-guardian PASS.
  **→ SODDISFATTA** (2026-07-18): `Partner`/`Booking`/`BookingRequest`/`BookingStatus`/
  `CommissionRecord` in `packages/contracts`; seed con un Partner ad abbonamento non attivo
  (`stamperia-lucca`) e relazione `HA_ABBONAMENTO`; `passa_filtri_duri` esclude un'esperienza
  con partner non attivo, `calcola_score` non legge mai `partner_id`/`prezzo_eur`/
  `partner_abbonamento_attivo`/`attribuzione` (guard AST + test bit-identico
  `test_scoring_bit_identico_con_abbonamento_e_prenotabilita_variati`, verde in
  `services/experience-engine`); `services/marketplace` (nuovo servizio: `request_booking`/
  `confirm_booking`, commissione 15% calcolata e registrata SOLO dopo che la conferma è già
  persistita — mai prima) con persistenza reale su Postgres/Neon (`PostgresBookingRepository`)
  e repository in-memory; `POST /booking` sul BFF (404 su esperienza inesistente, 422 su
  vincoli di dominio, 503 su storage non disponibile, mai un 500 opaco). Prezzo e
  prenotabilità letti SEMPRE dal grafo/candidati correnti, mai dal body della richiesta.
  Un'esperienza reale del seed (`exp-laboratorio-liuteria`) resa prenotabile end-to-end,
  provata da test contro il vero `SeedCandidateSource` (non solo un doppio). CI estesa a
  `windows-latest` oltre `ubuntu-latest` e a `services/marketplace`. ethics-guardian **PASS**
  (due giri: un gap iniziale su "prenotabile end-to-end" non dimostrato dal seed reale,
  colmato e riverificato). *Nota: un fallimento intermittente di
  `tests/test_integration_wave1.py` in suite combinata lunga (`neo4j.exceptions.SessionExpired`,
  connessione Aura chiusa dal server) è una fragilità pre-esistente di `Neo4jCandidateSource`
  (driver cache-ato per l'intera sessione pytest, nessun retry su errori di connessione
  transitori) — non introdotta da questa wave, tracciata come debito tecnico separato.*

## Wave 3b — Recommender ML  *(separata, non iniziare senza via libera)*
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
