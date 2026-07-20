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
  **Vincolo esplicito sui segnali di terze parti** (precisazione del committente): stelle
  Google/TripAdvisor e simili NON sono mai feature, né dirette né come proxy — il numero di
  recensioni è notorietà, pesarlo reintrodurrebbe il bias di popolarità. Potrebbero valere SOLO
  come soglia di ammissione binaria (mai come contributo al punteggio), e sarebbe comunque
  responsabilità dell'Experience Engine, non del recommender. Il segnale di qualità legittimo è
  il feedback dei visitatori che alimenta l'Urban Intelligence Index (Wave 4) — reporting
  separato, mai un input del ranking individuale.
  **→ SODDISFATTA** (2026-07-19): `experience_engine.engine.compose_itinerary` accetta ora un
  `score_fn` iniettabile (stesso pattern di `reason_fn`); il filtro duro `passa_filtri_duri`
  resta invariato e applicato PRIMA, il recommender riordina i soli candidati già ammessi, mai
  seleziona né filtra. Nuovo servizio `services/recommender`: persistenza `BehaviorEvent` su
  Neon (migrazione idempotente), feature aggregate e anonime documentate in
  `services/recommender/README.md` con motivazione per ciascuna e una sezione esplicita "Cosa
  NON è una feature, e perché" (campi commerciali/proxy, rating di terze parti, dati di Urban
  Memory/Index — tutti esclusi). Punteggio finale = `calcola_score` penalizzato (mai premiato)
  da due termini indipendenti: quota storica (con smoothing di Laplace su tutti i luoghi
  candidati, non solo quelli con eventi tracciati) e quota strutturale (dominanza per pertinenza
  di contenuto attraverso un insieme fisso di profili-archetipo, nessun dato storico/esterno) —
  il secondo termine è nato da un bug reale trovato dal test di distribuzione: un luogo dominante
  per pertinenza ma a zero eventi tracciati assorbiva il flusso spostato da un luogo penalizzato,
  peggiorando la distribuzione aggregata. Limite combinato dei pesi verificato anche a runtime
  (`ValueError`), non solo documentato. `POST /events` (202) persiste eventi; `POST /itinerary`
  costruisce il reranking e degrada silenziosamente al ranking deterministico se il recommender
  fallisce per qualunque motivo (mai un errore per un arricchimento opzionale). Criterio di
  distribuzione verificato su 4 scenari storici indipendenti (concentrazione su 1 luogo, su 5
  luoghi, storico anche sul luogo dominante per pertinenza, randomizzato a seed fisso): nessuno
  peggiora la distribuzione rispetto al ranking deterministico puro. Cold start bit-identico a
  `calcola_score` da solo, verificato end-to-end. ethics-guardian **PASS** su funzione obiettivo,
  assenza di feature commerciali/proxy/rating esterni, effetto sulla distribuzione, privacy,
  spiegabilità. *Limite noto — vedi `docs/LIMITI.md`: la correzione è locale per-richiesta,
  robustezza empirica su 4 scenari, non garanzia matematica su una popolazione di richieste.
  Documentato con cosa servirebbe per una garanzia vera e il costo stimato — non intrapreso ora.*

## Wave 4 — Urban Intelligence Index + Dashboard  *(= Fase 3, Smart City)*
- **index-engineer**: aggregazioni anonime, calcolo degli 8 indicatori, endpoint `/dashboard/*`.
- **frontend-engineer**: dashboard Comune (heatmap + Index), viste hotel e museo.
- **ethics-guardian**: soglie di aggregazione, non re-identificabilità.
- ✅ **Accettazione:** nessun PII derivabile e nessuna cella re-identificante; gli 8 indicatori
  calcolati; `distribuzione_flussi` visibile e non nascosto.
  **→ CALCOLO SODDISFATTO** (2026-07-20): nuovo servizio `services/intelligence-index` —
  `calcola_index(periodo, ...)` produce `contracts.UrbanIntelligenceIndex` per un periodo, funzione
  PURA (nessun accesso diretto a Postgres/Neo4j, dipendenze iniettate — stesso principio di
  `recommender.costruisci_score_fn`). Due formule negoziate col committente respingendo la prima
  proposta tecnica: `attivazione_locale` usa il grado SEMANTICO di un luogo (relazioni culturali,
  nuova funzione `graph.topology.grado_semantico()`), non il grado nella rete `VICINO` (prossimità
  fisica, respinto — misura la pianta della città, non la cultura); `nuovi_percorsi` è un TASSO
  (contratto cambiato int→float) su uno snapshot del grafo congelato a inizio periodo, non un
  conteggio grezzo che scenderebbe da solo mano a mano che il grafo cresce. `distribuzione_flussi`
  (entropia di Shannon) estratta dal test Wave 3b in un'unica fonte di verità condivisa. Gate di
  privacy k=10 (`intelligence_index.soglia`) applicato in un solo punto centrale a **tutti e 8** gli
  indicatori senza eccezioni — inclusa la correzione post-review su `contributi_memoria` (conta
  TUTTI i contributi del periodo, curati e pending, per non sottostimare la partecipazione civica
  dietro il ritardo fisiologico della curatela; il gate impedisce comunque la pubblicazione sotto
  10 `contributor_id` distinti, anche a fronte di un conteggio grezzo alto ma concentrato su
  poche persone). `soddisfazione` reso esplicitamente opzionale nel contratto (nessuna fonte reale
  oggi, mai un valore stimato). Buco nei dati dichiarato, non aggirato: `nuovi_percorsi` richiede
  `itinerari_periodo`, che oggi non ha alcuna persistenza reale (`compose_itinerary` produce
  `Itinerary` solo in memoria per la singola richiesta HTTP) — documentato in
  `services/intelligence-index/README.md` e in `docs/LIMITI.md` (insieme al limite noto di
  `tasso_ritorno`, che non cattura la fedeltà cross-periodo). `ethics-guardian` **PASS** finale
  (un FAIL iniziale sul gate mancante su `contributi_memoria`, corretto e riconfermato).
  **→ ENDPOINT SODDISFATTO** (2026-07-20): `GET /dashboard/index?periodo=YYYY-MM` e
  `GET /dashboard/flows?periodo=YYYY-MM&giorno=&ora=` (`services/api/api/main.py`), wrapper HTTP
  puri attorno a due nuove funzioni di `services/intelligence-index/intelligence_index/
  dashboard.py` (`indice_per_dashboard`, `celle_flusso`). Nuovi contratti congelati
  (`DashboardIndexResponse`, `FlowCell`, `DashboardFlowsResponse`,
  `packages/contracts/contracts/models.py`) progettati perché una cella soppressa non possa MAI
  esporre un conteggio di popolazione, nemmeno opzionale (`FlowCell` non ha e non può avere un
  campo tipo `n_persone`: garanzia strutturale via `extra="forbid"`, non disciplina di chi la
  popola). Zero eventi e 1-9 persone in una cella producono lo STESSO stato osservabile
  (`disponibile=False, conteggio_tappe=None`) — altrimenti un osservatore dedurrebbe per esclusione
  la popolazione di una cella soppressa. Entrambi gli endpoint rispondono sempre 200 (mai un 500
  per dato insufficiente: `disponibile: bool` nel body); `periodo` malformato o con mese fuori
  range risponde 422, non 500. **Bug di privacy reale trovato e corretto durante la verifica**
  (non solo un gap di test): `motivo_indisponibilita` di `GET /dashboard/index` esponeva
  inizialmente il conteggio ESATTO di persone sotto soglia (`str(DatiInsufficientiError)` include
  `n_persone`) — corretto per costruire un messaggio pubblico solo da `contesto`/`soglia` (mai il
  conteggio reale); il test che lo avrebbe dovuto intercettare cercava solo chiavi JSON tra
  virgolette, non un numero incorporato in una frase libera — rafforzato di conseguenza. Test
  avversariale end-to-end dedicato (`tests/test_integration_wave4_privacy.py`, via `TestClient`
  HTTP reale, non funzioni Python dirette): scenario costruito per fallire (una sola persona, un
  luogo minore, un giorno/un'ora precisi, non uno storico abbondante), verificato a ogni livello di
  filtro esposto dall'API (aggregato, per giorno, per giorno+ora) e sul confine esatto k=9 vs
  k=10. `ethics-guardian` **PASS** finale su tutto il livello endpoint, incluso il fix di privacy
  riverificato da zero (non sulla parola dell'agente che l'ha corretto).
  **→ DASHBOARD FRONTEND (Comune/hotel/museo) ANCORA DA FARE**: `frontend-engineer` non ancora
  coinvolto — resta l'ultimo pezzo della wave.

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
