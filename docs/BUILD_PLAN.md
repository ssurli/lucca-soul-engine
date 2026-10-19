# BUILD PLAN — Waves

Mappato sulla roadmap del White Paper (Fase 0 Ricerca → 1 PoC → 2 Living Lab → 3 Smart City →
4 Replica nazionale → 5 Replica europea). Questo repo costruisce le **Fasi 1–4**.

Ogni wave: obiettivo → agenti → criteri di accettazione. L'orchestratore esegue una wave alla volta.

> **Canali d'ingresso, stato attuale**: segnali (fluttuanti, transitori) — **fatto**
> (`docs/PROMOZIONE_TRACCIA.md`); relazioni (archi stabili tra entità, es. pizzeria↔rafting,
> alimentati via curatela) — **non ancora aperto**, nessuna porta d'ingresso oggi.
> **Scala**: Lucca prima, poi area vasta — non si salta direttamente alla replica nazionale
> (Fase 4).

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
  **→ SCARTO TROVATO E CHIUSO IN PARTE, PRIMA DEL LIVING LAB** (2026-07-23): il White Paper
  promette che il Marketplace "gestisce disponibilità"; `request_booking` non applicava alcuna
  validazione su `BookingRequest.quando` (né orari, né capienza, né conflitti). Aggiunta
  validazione MINIMA: `ExperienceNode.orari_apertura` (fasce settimanali ricorrenti,
  `FasciaApertura`), `Signal.giorno_settimana` (opzionale, mai fabbricato; poi ricavato da `Signal.data` quando il client manda solo la data — `docs/LIMITI.md`), e
  `contracts.rientra_in_orario` — una sola funzione pura riusata IDENTICA dal quinto filtro duro
  di `experience_engine.rules.passa_filtri_duri` (itinerario) e da
  `marketplace.service.request_booking` (`ExperienceNotAvailableError`, stesso schema di
  `ExperienceNotBookableError`, rifiuta PRIMA di persistere). Nessuna esperienza esistente
  dichiara ancora orari: comportamento invariato per il seed di oggi (lista vuota/giorno assente
  = nessun vincolo, mai un'esclusione fabbricata; per l'app il giorno non è più assente — è
  ricavato da `Signal.data` — quindi il filtro è acceso, con effetto nullo finché il seed non
  dichiara orari). Capienza, conflitti di slot, eccezioni
  calendariali e festività restano DELIBERATAMENTE fuori scope — non fabbricati senza una
  bottega reale davanti (`docs/LIMITI.md`, due voci dedicate). `contract-keeper`: nuovi campi
  in `packages/contracts`/`docs/DATA_CONTRACTS.md`. Test aggiunti in `tests/test_contracts.py`,
  `services/experience-engine/tests/test_engine.py`, `services/marketplace/tests/
  test_marketplace_service.py`; suite combinata rilanciata (`tests/` + ogni `services/*/tests`),
  nessuna regressione; `ruff check .` e `mypy` sui moduli toccati puliti.
  **ethics-guardian** (2026-07-24, giro DEDICATO e separato, non un'autovalutazione — richiesto
  esplicitamente dal committente perché "un'autovalutazione non lo sostituisce"): **FAIL
  iniziale**, un bug REALE trovato che l'implementatore non aveva visto —
  `experience_engine.engine._migliore_alternativa` (la sostituzione di tappa in
  `adapt_itinerary` su pioggia/affollamento) aveva una logica di filtro scritta a mano, non
  chiamava `rientra_in_orario`: una riscrittura poteva reintrodurre un'esperienza CHIUSA come
  alternativa, anche se la composizione iniziale la escludeva correttamente. Riprodotto con
  uno scenario minimo, corretto (stesso controllo aggiunto a `_migliore_alternativa`), test di
  regressione permanente aggiunto
  (`test_adapt_non_sostituisce_con_unalternativa_chiusa_in_quellorario`), suite combinata
  rilanciata da zero: verde. **PASS** dopo la correzione. Il gate ha inoltre segnalato, senza
  correggerli (fuori scope di questa verifica), due punti ulteriori — entrambi tracciati in
  `docs/LIMITI.md`, non lasciati impliciti: (a) la stessa `_migliore_alternativa` non verifica
  nemmeno `partner_abbonamento_attivo` (gap Wave 3a pre-esistente, mai esteso ad `adapt`,
  scoperto incidentalmente); (b) tutti i filtri duri (non solo gli orari) valutano ogni
  candidato contro un singolo istante di `Signal`, non contro l'orario in cui la tappa verrebbe
  effettivamente visitata più avanti nella sequenza — limite di progettazione della pipeline,
  molto più visibile per gli orari che per l'affollamento. Nessun canale commerciale toccato dal
  filtro sugli orari (letto solo da `passa_filtri_duri`/`_migliore_alternativa`, mai da
  `calcola_score`); nessuna capienza fabbricata; il vincolo resta in un solo modello
  (`rientra_in_orario`) per tutti e tre gli usi (composizione, adattamento, prenotazione).
  Aggiunta anche una nota in `services/recommender/README.md`, accanto alla tabella dei pesi:
  il peso 2.0 di `stop` poggia su un'assunzione di presenza fisica che nessun codice verifica
  oggi (rimanda a `docs/LIMITI.md`, voce su `POST /events`).
  **→ LIVELLO FLUTTUANTE ATTIVATO** (2026-07-27): `Signal.eventi_attivi` era `list[str]`,
  dichiarato nel contratto dalla Wave 1, mai letto da nessuna logica (verificato prima di
  attivarlo) — un interruttore già cablato, mai acceso. Diventato `list[SegnaleFluttuante]`
  (`id`, `descrizione`, `temi`, `place_id`, `non_commerciale` — quest'ultimo OBBLIGATORIO,
  nessun default, stesso principio di `MemoryContribution.consenso`). Due funzioni pure, un
  solo punto ciascuna: `contracts.segnale_fluttuante_ammissibile` (filtro duro sul
  commerciale — "visibilità non acquistabile" applicato al vettore "segnalare invece di
  pagare una commissione") ed `experience_engine.rules.segnali_fluttuanti_pertinenti`
  (coerenza col profilo, STESSO ragionamento per connessioni/gruppi tematici già usato da
  `calcola_score`, non un secondo criterio). `experience_engine.engine.compose_itinerary`
  aggiunge, IN CODA e mai in sostituzione, le tappe fluttuanti pertinenti, rispettando il
  budget residuo (`profile.tempo_disponibile_min`) — namespace `experience_id` separato
  (`fluttuante-<id>`) dal reale (`exp-...`), nessuna collisione strutturale. `calcola_score`
  non importa né legge `Signal.eventi_attivi` in nessuna forma: bit-identico con e senza
  segnali attivi (test dedicato). `git diff --stat` tocca SOLO `packages/contracts`,
  `services/experience-engine` e i loro test — né `services/graph` né `services/recommender`,
  come richiesto esplicitamente in verifica. Suite combinata rilanciata da zero (`tests/` +
  ogni `services/*/tests`): 497 passed, 57 skipped (stessi motivi ambientali di sempre), 0
  failed — 20 test in più rispetto a prima di questa attivazione. `ruff check .` e `mypy` sui
  moduli toccati puliti. Verificato anche dal vivo, non solo in CI: `POST /itinerary` contro
  Neon+Aura reali con un `Signal.eventi_attivi` popolato — un segnale non commerciale coerente
  col profilo (`temi=["musica"]`, profilo con `arte=0.9`) produce una tappa
  `fluttuante-violinista-anfiteatro` in coda, con `reason` che nomina correttamente il luogo
  reale letto dal grafo ("Piazza dell'Anfiteatro"); un secondo segnale identico ma
  `non_commerciale=false` non compare mai, nello stesso itinerario.
  **ethics-guardian** (giro DEDICATO e separato, non un'autovalutazione): **verdetto esplicito
  sul vettore "visibilità comprata via segnalazione" — PASS**, verificato non per lettura ma
  con un test comportamentale bit-identico (`test_segnale_fluttuante_non_altera_score_esperienze_permanenti`)
  che prova sia `calcola_score` sia le tappe reali scelte da `compose_itinerary` invariati con
  e senza segnali attivi. Nessun FAIL bloccante questa volta (a differenza del giro precedente
  su `adapt_itinerary`), ma sei punti trovati e segnalati esplicitamente — tracciati in
  `docs/LIMITI.md`, non lasciati impliciti: (1) `non_commerciale` è auto-dichiarato, senza
  verifica — un segnale può mentire; (2) `temi` è ALTRETTANTO auto-dichiarato, un vettore
  distinto (non "se compare" ma "a chi compare", dichiarando temi larghi per massimizzare la
  pertinenza); (3) `adapt_itinerary` non rivaluta mai i segnali fluttuanti — un segnale nuovo
  apparso dopo la composizione iniziale non entra mai in un itinerario già composto; (4) una
  tappa fluttuante già aggiunta è strutturalmente immune a pioggia/affollamento in un adapt
  successivo (il fallback `_stub_da_stop` la forza sempre `al_chiuso=True`); (5) nessun tetto
  al numero di tappe fluttuanti aggiungibili; (6) nessun filtro di affollamento/accessibilità
  sulla tappa fluttuante (`SegnaleFluttuante` non porta questi campi, forma minimale
  deliberata). Nessuno dei sei è stato fabbricato/corretto senza un caso reale che ne mostri
  il bisogno — stesso principio già applicato al resto di questo file. Promozione a
  permanente (un fluttuante ricorrente diventa un'esperienza o un `:Evento` programmato) e il
  livello "programmato" stesso restano fuori scope, annotati come evoluzione prevista.
  **Nessuno dei sei è bloccante ora** — restano annotati in `docs/LIMITI.md` così come
  trovati. Due di loro, però, non sono debito isolato: ricadono su lavoro già previsto altrove,
  e va detto esplicitamente per non perdere il collegamento:
  - **(1) e (2), l'auto-dichiarazione di `non_commerciale`/`temi`**, sono esattamente il
    problema che una coda di curatela dovrebbe risolvere — lo stesso principio già
    operativo per Urban Memory (`urban_memory.service`, un contributo raggiunge `curato=True`
    solo dopo revisione umana). La curatela per il livello fluttuante non esiste ancora
    (`docs/LIMITI.md` la elenca come evoluzione prevista, non progettata): quando verrà
    disegnata, deve coprire ANCHE la verifica di queste due autodichiarazioni, non solo la
    promozione a permanente — sono la stessa esigenza ("qualcuno deve controllare cosa viene
    dichiarato"), non due problemi distinti da progettare due volte.
  - **(3) e (4), la mancata rivalutazione dei fluttuanti in `adapt_itinerary`**, sono il passo
    naturale successivo del livello fluttuante, e toccano la STESSA logica del bug orari
    corretto in questa stessa collaborazione (`_migliore_alternativa`/`_stub_da_stop`, la voce
    precedente in questo changelog): quel fix ha insegnato dove intervenire (il punto in cui
    `adapt_itinerary` ricostruisce le tappe); estenderlo ai segnali fluttuanti — rivalutare
    `eventi_attivi` ad ogni adapt, non solo forzare `al_chiuso=True` sullo stub — è la
    continuazione diretta di quel lavoro, non un fronte nuovo scollegato.
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
  **→ DASHBOARD FRONTEND SODDISFATTA, MA NON VERIFICATA A COMPILAZIONE** (2026-07-20):
  `apps/lucca_soul_app` — nuova schermata `DashboardScreen` (Comune: tutti e 8 gli indicatori;
  Hotel/Museo: solo `distribuzione_flussi` + `attivazione_locale`, stesso substrato dati, taglio
  lato client), client verso i due endpoint (`BffClient.dashboardIndex`/`dashboardFlows` — l'app
  non parla mai direttamente con `services/intelligence-index`), modelli con costruttore privato
  (`fromJson` è l'unico modo di ottenere un'istanza, così il vincolo di coerenza
  `disponibile`⇔valore non è aggirabile lato client). Vincolo non negoziabile rispettato: una cella/
  indicatore soppresso da k=10 è SEMPRE un badge esplicito ("dato insufficiente per garantire
  l'anonimato"), mai uno zero né confuso con `soddisfazione=null` (buco dati diverso, testo
  diverso). `distribuzione_flussi` è sempre la card più prominente, in entrambe le viste.
  **Limite dichiarato**: né `frontend-engineer` né l'orchestratore hanno potuto eseguire `flutter
  analyze`/`flutter test` in questa sessione (SDK Flutter/Dart non installato in questo ambiente) —
  verificata solo con lettura manuale del codice (struttura, tipi, rispetto del vincolo di
  visualizzazione). Da compilare e testare con `flutter analyze && flutter test` su una macchina
  con Flutter installato prima di considerare la UI definitivamente verificata — non solo scritta.
  Stesso principio di `soddisfazione`/`nuovi_percorsi` sopra: un buco dichiarato, non un verde
  presunto — dettaglio completo (cosa servirebbe per chiudere il buco, comandi esatti) in
  `docs/LIMITI.md`.
  **→ LIMITE SOPRA CHIUSO A METÀ — ANALIZZATA E TESTATA, MAI AVVIATA** (2026-10-14): sul
  notebook, Flutter 3.47.7, `flutter analyze` 0 issue e `flutter test` 38/38 (intera suite
  dell'app, incluso `dashboard_models_test.dart`). Resta aperto: l'app non è mai stata avviata
  (cartelle piattaforma assenti, `flutter run` senza target) — vedi `docs/LIMITI.md`.
  **→ LIMITE TROVATO DURANTE LA VERIFICA MANUALE CONTRO NEON/AURA REALI** (2026-07-21): il gate
  k=10 di `GET /dashboard/*` è periodo-scoped e si è confermato reale (evento sintetico su un
  periodo futuro, "2027-01", isolato dal mese corrente). Ma `recommender.repository.
  PostgresBehaviorEventRepository.conteggio_per_esperienza()` legge `behavior_event` SENZA alcun
  filtro temporale — ogni riga, sintetica o reale, influenza la quota storica del ranking di
  `POST /itinerary` da subito e per sempre, a prescindere dal `ts`. Nessun modo oggi di marcare un
  evento come sintetico né alcuna retention. Nuovo strumento `scripts/pulisci_eventi_prefisso.py`
  (cancella per prefisso di `person_id`, stampa il conteggio cancellato) per ripulire SUBITO dopo
  ogni verifica manuale con dati reali. Limite documentato per esteso, con cosa servirebbe (flag
  `sintetico`/finestra temporale nella query), in `docs/LIMITI.md`.
  **→ BUG REALE TROVATO E CORRETTO, RIVERIFICATO LIVE** (2026-07-21): `cypher/11_grado_semantico.
  cypher` costruiva `botteghe_ospitate` con una pattern comprehension a pattern nodo-solo
  (`[(b:Bottega {place_id: l.id}) | b]`) — sintassi Cypher 5 non valida in Cypher 25
  (GQL-conformant, una pattern comprehension richiede un PATH, non un singolo nodo), riprodotta
  identica su Aura reale (`CypherSyntaxError` a riga/offset esatti) e bloccante: faceva rispondere
  500 a `GET /dashboard/flows`, impedendo la verifica del vincolo k=10. Riscritta con
  `OPTIONAL MATCH` + `collect(b)`, nessuna pattern comprehension. Scansionati tutti i `.cypher`
  versionati e le query inline nei `.py`: nessun'altra occorrenza di pattern comprehension né di
  altri costrutti Cypher 5 non validi in Cypher 25. Riverificato DAL VIVO, non solo staticamente:
  `Neo4jMetricsSource.grado_semantico()` contro Aura reale non solleva più l'errore e produce un
  risultato IDENTICO, luogo per luogo, al calcolo offline (`graph.topology.grado_semantico()`);
  `GET /dashboard/flows`/`GET /dashboard/index` avviati dal `.venv` contro Neon+Aura reali
  rispondono 200 (non più 500). `pytest` su `services/graph/tests` + `tests/` +
  `services/api/tests` + `services/intelligence-index/tests`: 240 passed, 11 skipped (motivi non
  correlati), nessuna regressione.
  **→ WAVE 4 CHIUSA — vincolo bloccante k=10 verificato dal committente, dal vivo** (2026-07-21):
  prova eseguita dal committente sulla propria macchina, `GET /dashboard/flows` contro Neon+Aura
  reali (dopo il fix Cypher sopra), sullo stesso schema avversariale di
  `tests/test_integration_wave4_privacy.py` (confine esatto k=9 vs k=10, a tutti e tre i livelli
  di filtro che l'endpoint espone — periodo, periodo+giorno, periodo+giorno+ora): con 9 persone
  distinte, `disponibile=false` e `conteggio_tappe=null` a TUTTI e tre i livelli; con la decima
  persona, `disponibile=true` e `conteggio_tappe=10` — confine esatto, mai un arrotondamento
  approssimativo. In nessun caso la cella soppressa è stata mostrata come zero né omessa dalla
  lista: lo stesso comportamento già provato via `TestClient` in `tests/`, ora confermato anche
  contro l'infrastruttura cloud reale del committente, non solo contro doppi in-process. Eventi
  sintetici della prova ripuliti da `behavior_event` con `scripts/pulisci_eventi_prefisso.py`
  subito dopo, coerente col limite documentato in `docs/LIMITI.md` (nessuno scoping temporale
  nel Recommender). Con questo, il vincolo BLOCCANTE della wave — soppressione k=10 al confine
  dell'API, provata contro Neon/Aura reali, non solo in CI — è soddisfatto. **Wave 4 chiusa.**
  Limiti dichiarati non chiusi da questa verifica (restano aperti, per design — vedi
  `docs/LIMITI.md`): `soddisfazione` senza fonte dati reale; `nuovi_percorsi` con
  `itinerari_periodo=[]` (nessuna persistenza itinerari); `tasso_ritorno` solo intra-periodo;
  dashboard Flutter non compilata/testata (SDK assente in questa sessione); `behavior_event` senza
  flag sintetico né retention.
  **→ ADDENDUM POST-CHIUSURA — viewer HTML statico + CORS aperto su `/dashboard/*`**
  (2026-07-22): `scripts/dashboard_viewer.html`, un solo file senza build né dipendenze, per
  vedere la dashboard senza compilare Flutter (stesse scelte di visualizzazione di
  `DashboardScreen`: `distribuzione_flussi` in evidenza, celle soppresse SEMPRE un badge esplicito,
  mai uno zero, `soddisfazione` assente mostrata come "non ancora misurabile", distinta dal badge
  k=10). Richiede CORS lato BFF (una pagina `file://` ha origin "null"): aggiunto
  `api.main.dashboard_readonly_cors`, un middleware scritto a mano — NON il `CORSMiddleware` di
  libreria, che si applicherebbe all'intera app — scoped a `GET`/`OPTIONS` SOLO su `/dashboard/*`;
  verificato con richieste HTTP reali che l'intestazione CORS è assente su `/health`,
  `/contracts/version`, `/memory/{place_id}` e su ogni `POST`. **Cambio di postura di sicurezza,
  non un dettaglio estetico**: `allow_origins="*"` va bene per uno strumento locale, MAI lasciato
  com'è per un deploy pubblico del BFF — dettaglio completo (cosa NON è garantito, cosa servirebbe)
  in `docs/LIMITI.md`.

## Wave 5 — Replica  *(= Fase 4)*
- **graph-architect**: nuovo seed di contenuto (Siena / Ferrara). Tecnologia invariata.
- ✅ **Accettazione:** cambiando **solo il dataset**, il motore genera itinerari per la nuova città.
  È la prova di scalabilità su cui poggia l'intero investment case.

## Candidati per la prossima wave  *(registrati, NON pianificati né implementati)*
Voci aperte in `docs/LIMITI.md`. Nessuna è assegnata: prima la decisione di prodotto, poi
`contract-keeper` se tocca il contratto → `experience-engine` → `test-engineer` → `ethics-guardian`.
1. **Sostituzione ammessa se il costo non peggiora** — voce "Sostituzione rifiutata quando
   l'itinerario supera già il limite". Oggi, se l'itinerario supera già
   `min(tempo_effettivo_min, minuti alla mezzanotte)`, l'adattamento rifiuta anche un'alternativa
   più corta e più tranquilla: contraddice la tesi "pertinenza vincolata alla distribuzione dei
   flussi" di `docs/POSIZIONAMENTO_COMPETITIVO.md`. Correzione proposta:
   `costo(ipotesi) <= max(limite, costo(itinerario corrente))`. Cambia il golden in modo
   controllato.
2. **Orari all'arrivo di ogni tappa** — residuo della voce "Orari di apertura verificati solo
   all'ora del segnale" (decisione 2 del 2026-10-16: rimandato finché nessuna esperienza dichiara
   `orari_apertura`).
3. **Frase della tappa mantenuta senza budget** — voce "La frase della tappa mantenuta cita il
   tempo anche senza budget".
4. **Titolo dell'esperienza in `ItineraryStop` e `TappaEsclusa`, riempito dal grafo**, insieme
   alla prima esecuzione dell'app (cartelle piattaforma assenti, `flutter run` senza target) —
   voce "L'app non ha nomi leggibili delle tappe". Oggi schede e note mostrano lo slug
   `experience_id`. Passa da `contract-keeper`; cambia il golden.

### Decisioni di prodotto per la wave sull'adattamento (confermate il 2026-10-16) — ATTUATE
**→ Wave adattamento COMPLETATA il 16/10/2026, provata su Aura** (ramo `wave-adattamento`, integrato in `main`): contratti `f84b97d`, engine
`e68c704` + `11c163c` (disclosure unica), graph `b2269be`, app `8f268ec`; golden rigenerato una
volta (58 casi con richieste invariate + 16 `adapt-budget|…`), ogni differenza attribuita a una
decisione con 0 casi non attribuiti, `lucca_punteggi.json` invariato. Gate: `test-engineer` verde,
`ethics-guardian` PASS con osservazioni non bloccanti (corrette o registrate in `docs/LIMITI.md`).
Wave lanciata in una sessione di Claude Code, con il §0 nel prompt. Ordine dei gate:
`contract-keeper` (punti 3 e 4 in un solo passaggio) → `experience-engine` / `graph-architect` →
`test-engineer` → `ethics-guardian`. Il golden cambia in modo controllato.
1. **Un itinerario è sempre una sessione nella stessa giornata.** Il tetto è la mezzanotte della
   città e il budget viene troncato lì (l'onboarding produce 120 minuti di default; il problema
   nasce solo da client che chiamano l'API direttamente).
2. **Orari all'arrivo di ogni tappa: rimandati.** Nessuna esperienza ha `orari_apertura`; le uniche
   candidate sono ora dichiaratamente dimostrative.
3. **Budget registrato nell'`Itinerary` composto**, non nell'`AdaptRequest`: resta legato
   all'itinerario e non obbliga a rimandare l'intero profilo.
4. **Esito dell'adattamento per tappa** (per esempio «segnale valutato, mantenuta: nessuna
   alternativa ammissibile»): un segnale può toccare più tappe con esiti diversi. Caso di prova
   `adapt|onnivoro|pioggia`.
5. **Allineare le connessioni tra seed e Neo4j** (frasi e ordine) — voce "Connessioni diverse tra
   seed in memoria e Neo4j" in `docs/LIMITI.md`; sistema anche l'attribuzione tautologica
   («Pasticceria, bottega di pasticceria»).

## Traguardo A — demo presentabile  *(obiettivo 12/12/2026)*
Blocchi in ordine: ognuno parte quando il precedente è chiuso. Ogni blocco segue il protocollo
(`contract-keeper` se tocca il contratto → agente competente → `test-engineer` →
`ethics-guardian` dove richiesto).
1. **Prima esecuzione dell'app.** L'app compila (`flutter analyze` e `flutter test` verdi in CI)
   ma non è mai stata avviata: mancano le cartelle piattaforma.
2. **Titolo leggibile dell'esperienza** in `ItineraryStop` e `TappaEsclusa`, riempito dal grafo
   — voce "L'app non ha nomi leggibili delle tappe" in `docs/LIMITI.md`.
3. **Ora adatta di un'esperienza** — voce "Il motore non conosce l'ora adatta di un'esperienza".
4. **Sostituzione ammessa se il costo non peggiora** — voce "Sostituzione rifiutata quando
   l'itinerario supera già il limite".
5. ~~**Orari verificati all'arrivo di ogni tappa**, prima di qualunque esercizio con orari reali —
   residuo della voce "Orari di apertura verificati solo all'ora del segnale".~~ **CHIUSO
   (2026-10-19, ondata 1b-1):** controllo all'arrivo in composizione e in adattamento, esito
   `tagliata_orario`, fuso della città da `Signal.istante`, orari attraverso il grafo. Test:
   `test_orari_all_arrivo.py`, `test_istante_bff.py`, `test_orari_grafo*.py`. Golden invariato.
   Il blocco 3 (ora adatta) resta aperto: dipende dagli orari reali dell'ondata 1b-2.
6. **Il curatore crea un luogo nuovo da un contributo di Urban Memory**, perché un racconto su un
   luogo non ancora nel grafo non vada perso.

**Rinviati finché non c'è una fonte reale:** flag `sintetico` su `behavior_event`; import di dati
di affollamento.

**Candidati (registrati, non pianificati):**
- App web servita dal BFF sulla stessa origine (niente CORS), per demo da telefono e messa online.
  Oggi la prima esecuzione usa Chrome con `--disable-web-security`, solo in locale.

**Regola di perimetro:** i nuovi difetti trovati durante il Traguardo A vanno in `docs/LIMITI.md`,
salvo che blocchino la demo.

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
