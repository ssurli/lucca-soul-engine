# Lucca Soul Lab — Sintesi fattuale del motore (per uso pitch)

> Documento di FATTI, non di marketing. Ogni numero qui dentro è stato ricontato o rieseguito
> il 2026-07-22, in questa sessione, contro il codice versionato in `main` e — dove indicato —
> contro l'infrastruttura cloud REALE (Neo4j Aura + Neon), non contro doppi in-process o dati
> stimati. Dove un numero riportato in passato (verbalmente, non nel repo) non è stato
> ritrovabile né riproducibile, è dichiarato esplicitamente come tale, non arrotondato per
> sembrare completo — stesso principio di `docs/LIMITI.md`.
>
> Ambiente di verifica: Python 3.13.7, `.venv` con tutti i pacchetti `lucca-*` in editable
> mode (stessa lista di `.github/workflows/ci.yml`), `.env` con credenziali reali Aura/Neon.

---

## 1. Componenti realmente costruiti (Wave 0 → 4)

| Wave | Componente | Cosa fa (una riga) |
|---|---|---|
| 0 | `packages/contracts` | Tipi Pydantic v2 condivisi (single source of truth) — importati da tutti i servizi, mai ridefiniti. |
| 0 | `services/api` (BFF FastAPI) | Unico ingresso HTTP dell'app: orchestra i servizi interni, mai un accesso diretto a DB dal client. |
| 1 | `services/graph` | Urban Knowledge Graph (Neo4j): schema, seed versionato di Lucca, query dei candidati esperienza. |
| 1 | `services/rag` | Onboarding conversazionale → `EmotionalProfile`; genera i `reason` in italiano. L'LLM dialoga, non decide. |
| 1 | `services/experience-engine` | **AI Experience Engine** — l'unico componente che DECIDE: filtri etici duri + scoring + composizione a budget → `Itinerary` deterministico e spiegabile. |
| 1 | `apps/lucca_soul_app` (Flutter) | Onboarding, itinerario con `reason` in evidenza, card adattiva ai segnali (pioggia/affollamento/stanchezza). |
| 2 | `services/urban-memory` | Conferimento contributi (racconto, foto, mestiere…) con consenso obbligatorio, licenza tracciata, curatela prima della pubblicazione, aggancio al grafo via `RIGUARDA`. |
| 3a | `services/marketplace` | Prenotazioni (`Booking`) + commissione (`CommissionRecord`, dato contabile, registrato SOLO dopo la conferma, mai un input di scoring). |
| 3b | `services/recommender` | ML classico su `BehaviorEvent`: produce una `score_fn` che **penalizza** (mai premia) la concentrazione storica di flusso su un luogo — plug-in opzionale dentro l'Experience Engine, mai un secondo decisore. |
| 4 | `services/intelligence-index` | Calcola gli 8 indicatori dell'Urban Intelligence Index per periodo, gate di privacy k=10 applicato in un solo punto centrale, mai un valore pubblicato sotto soglia. |
| 4 | `GET /dashboard/index`, `GET /dashboard/flows` (BFF) | Wrapper HTTP puri sull'Index — rispondono SEMPRE 200, "dato insufficiente" è un campo del body, mai un errore HTTP. |
| 4 | `apps/lucca_soul_app` — `DashboardScreen` + `scripts/dashboard_viewer.html` | Due viste dello stesso substrato dati (Comune: 8 indicatori; Hotel/Museo: 2 mirati) — una in Flutter (scritta, non ancora compilata in questa sessione), una statica HTML (verificata dal vivo). |

---

## 2. Numeri reali

### 2.1 Il grafo

Due misurazioni indipendenti, entrambe di oggi:

| | Nodi | Relazioni | Densità¹ | Grado medio² |
|---|---|---|---|---|
| **Seed versionato** (`graph.seed_lucca`, riproducibile da zero con `python -m graph.loader`) | 62 | 142 | 0,03755 | 4,581 |
| **Aura live** (interrogato direttamente via driver Neo4j, `.env` reale) | 63 | 146 | 0,03738 | 4,635 |

¹ densità = relazioni / (nodi × (nodi−1)) — grafo diretto, coppie ordinate.
² grado medio = 2 × relazioni / nodi (somma entrata+uscita).

La differenza tra i due (+1 nodo, +4 relazioni sul vivo) è **attesa e documentata**
(`graph/metrics.py`): Aura accumula nel tempo ciò che il seed offline non ha — qui,
concretamente, 1 nodo `:Memoria` con 1 relazione `:RIGUARDA` (un contributo reale di Urban
Memory già agganciato) e 3 relazioni `:VICINO` in più rispetto al seed originale.

Composizione del seed per tipo di nodo: 15 `Luogo`, 22 `Esperienza`, 13 `Tema`, 5 `Bottega`,
4 `Artista`, 3 `Partner`. Per tipo di relazione: 38 `VICINO` (prossimità fisica), 56 `EVOCA`
(Esperienza→Tema) + 9 `EVOCA` (Bottega→Tema) = 65 `EVOCA` totali, 22 `SI_SVOLGE_A`
(Esperienza→Luogo), 7 `LEGATO_A` (Artista→Luogo), 5 `OFFRE` (Bottega→Esperienza),
3 `HA_ABBONAMENTO` (Bottega→Partner), 2 `ISPIRATA_DA` (Bottega→Artista).

### 2.2 Test

Eseguiti dal vivo in questa sessione, stessa suite di `.github/workflows/ci.yml` (`tests/` +
ogni `services/*/tests`), interprete `.venv`:

- **508 test raccolti, 451 passati, 57 skippati, 0 falliti** (404 s).
- Gli skip sono TUTTI ambientali, non nascosti: Postgres locale non disponibile in questa
  sessione (persistenza reale testata altrove, contro Neon vero — vedi §3) o percorso
  offline non applicabile quando `DATABASE_URL` è configurato.
- `apps/lucca_soul_app` (Flutter): 3 file di test scritti (`models_test.dart`,
  `memory_test.dart`, `itinerary_diff_test.dart`, più `dashboard_models_test.dart` e
  `periodo_test.dart` per la Wave 4) — **mai eseguiti** in questa sessione (SDK Flutter/Dart
  assente). Dichiarato in `docs/LIMITI.md`, non contato tra i 451 passati sopra.

### 2.3 Servizi ed endpoint

- **8 servizi Python** (`services/api`, `experience-engine`, `graph`, `rag`, `recommender`,
  `urban-memory`, `marketplace`, `intelligence-index`) + **1 pacchetto contratti**
  (`packages/contracts`) + **1 app client** (`apps/lucca_soul_app`, Flutter).
- **11 endpoint HTTP** sul BFF (`services/api/api/main.py`): `GET /health`,
  `GET /contracts/version`, `POST /session/onboarding`, `POST /itinerary`,
  `POST /itinerary/adapt`, `POST /memory`, `GET /memory/{place_id}`, `POST /booking`,
  `POST /events`, `GET /dashboard/index`, `GET /dashboard/flows`.

---

## 3. Le prove — un vincolo etico, il test che lo protegge, cosa ha trovato

### 3.1 Visibilità non acquistabile (Wave 1/3a)

- **Vincolo:** nessun campo commerciale (`partner_id`, `prezzo_eur`, `attribuzione`) può
  influenzare lo score di un'esperienza — solo la sua PRESENZA (`Partner.abbonamento_attivo`).
- **Test che lo protegge, oggi:** `services/experience-engine/tests/test_engine.py::
  test_scoring_invariante_a_partner_prezzo_attribuzione` e
  `::test_scoring_bit_identico_con_abbonamento_e_prenotabilita_variati` — asserzione di
  uguaglianza **bit-a-bit** (`==` su float, non tolleranza), su 7 varianti commerciali diverse
  contro lo stesso candidato neutro. Rieseguiti ora: **passano**.
- **Cosa ha trovato quando ha fallito:** durante la Wave 1 il grafo mescolava `attribuzione`
  ("Offerta da...") dentro `connessioni` (il campo che alimenta lo score di sorpresa) — la
  presenza di un partner comprava punteggio. Corretto separando `GraphCandidate.attribuzione`
  da `connessioni` (commit `eb26b5e`/`b432e94`/`bca3c8d`, "Wave 1 (ethics gate)"). **Nota
  onesta:** il delta numerico esatto di quel run originale non è preservato nel repo (i commit
  che hanno introdotto il fix non registrano il valore prima/dopo, solo la correzione
  strutturale) — non lo riporto come fatto perché non l'ho ritrovato né potuto riprodurre;
  quello che è verificabile oggi è il vincolo di invarianza permanente sopra, non quel numero.

### 3.2 Distribuzione dei flussi non peggiorata dal Recommender (Wave 3b)

- **Vincolo:** un ranking corretto da storico comportamentale non deve MAI aumentare la
  concentrazione dei flussi rispetto al ranking deterministico puro.
- **Test che lo protegge:** `tests/test_integration_wave3b.py::
  test_il_recommender_non_aumenta_la_concentrazione_dei_flussi`, parametrizzato su **4 scenari
  storici indipendenti** (concentrazione su 1 luogo, su 5 luoghi, storico anche sul luogo
  dominante per pertinenza, randomizzato a seed fisso 42). Rieseguito ora: **4/4 passano**.
- **Numeri reali, ricalcolati ora** sullo scenario originale (concentrazione su `mura-urbane` +
  `piazza-anfiteatro`, zero storico su `san-michele-in-foro`): il ranking deterministico sceglie
  `san-michele-in-foro` **13 volte su 44 tappe totali** (10 profili) — nettamente il luogo
  dominante per pertinenza strutturale (entropia normalizzata di distribuzione = 0,7826). Con
  la correzione del recommender attiva (default: penalità storica + penalità strutturale),
  l'entropia sale a 0,8419 — **distribuzione più uniforme, mai peggiore**.
- **Cosa ha trovato quando ha fallito, in sviluppo:** un luogo dominante per pertinenza di
  contenuto ma a ZERO eventi storici tracciati poteva assorbire il flusso liberato dalla
  penalizzazione degli altri luoghi concentrati — peggiorando, non migliorando, la
  distribuzione aggregata. Corretto aggiungendo una seconda penalità indipendente (quota
  strutturale, `recommender.ranking._quota_strutturale_per_place`) accanto a quella storica.
  **Nota onesta:** ho provato a riprodurre ORA il fallimento originale disattivando la sola
  quota strutturale (`peso_struttura=0.0`) sullo stesso scenario: con la sola quota storica
  (smoothing di Laplace) già presente, la distribuzione non scende comunque sotto quella
  deterministica in questa specifica riproduzione (0,7898 vs 0,7826, ancora ≥) — segno che lo
  smoothing di Laplace da solo attutisce già buona parte del problema su QUESTO scenario
  preciso. Non ho un modo verificato di riprodurre esattamente il run di sviluppo originale che
  ha fallito (mai committato in stato "rotto": la Wave 3b è un solo commit già corretto) — lo
  dichiaro invece di stimare un numero.

### 3.3 Soppressione k=10 al confine dell'API (Wave 4)

- **Vincolo:** nessuna cella/indicatore aggregato sotto 10 `person_id` distinti può essere
  pubblicato — mai un numero, nemmeno approssimato.
- **Test che lo protegge:** `tests/test_integration_wave4_privacy.py` — scenario avversariale
  via `TestClient` HTTP reale (non funzioni Python dirette): un evento isolato di UNA persona
  su un luogo minore, verificato a TUTTI i livelli di filtro (`periodo`, `+giorno`,
  `+giorno+ora`), più il confine ESATTO 9 (soppresso) vs 10 (visibile) persone. Rieseguiti ora:
  **passano**.
- **Cosa ha trovato quando ha fallito:** un bug di privacy REALE, non solo un gap di test —
  `motivo_indisponibilita` di `GET /dashboard/index` esponeva inizialmente il conteggio ESATTO
  di persone sotto soglia, perché il messaggio pubblico riusava `str(DatiInsufficientiError)`
  as-is (quel messaggio interno include letteralmente `f"{n_persone} persone distinte
  coinvolte"`, `services/intelligence-index/intelligence_index/soglia.py`). Corretto costruendo
  il messaggio pubblico SOLO da `contesto`/`soglia` (mai `n_persone`) in
  `intelligence_index.dashboard.indice_per_dashboard`. Il test che lo doveva intercettare
  cercava solo chiavi JSON tra virgolette, non un numero incorporato in una frase libera — è
  stato rafforzato con una ricerca a confini di token (`\b3\b`) sul messaggio pubblico.
- **Verificato anche fuori CI, contro infrastruttura reale:** in questa stessa collaborazione,
  ho riprodotto e corretto un secondo bug bloccante trovato SOLO contro Aura reale (non in CI,
  che gira su un profilo diverso) — una pattern comprehension Cypher 5 non valida in Cypher 25
  in `cypher/11_grado_semantico.cypher` (`CypherSyntaxError`, faceva rispondere 500 a
  `GET /dashboard/flows`). Corretto, riverificato dal vivo (risultato identico al calcolo
  offline). Il committente ha poi eseguito personalmente, sulla propria macchina contro Neon+
  Aura reali, la prova del confine k=9/k=10 a tutti e tre i livelli di filtro: 9 persone →
  `disponibile=false`/`conteggio_tappe=null`; 10 persone → `disponibile=true`/
  `conteggio_tappe=10` — confine esatto, mai una cella soppressa mostrata come zero o omessa.

---

## 4. Limiti dichiarati (`docs/LIMITI.md`) — sintesi

Sei limiti, ciascuno con: cosa è garantito, cosa NON lo è, cosa servirebbe, decisione esplicita
di non chiuderlo ora. In una riga ciascuno:

1. **Recommender, distribuzione aggregata** — la correzione è locale per-richiesta, robusta su
   4 scenari (vedi §3.2), ma non è una garanzia matematica su ogni popolazione di richieste
   possibile: servirebbe un'allocazione globale o uno stato condiviso online (settimane di
   lavoro dedicato, probabile wave a sé).
2. **`tasso_ritorno`** — misura il ritorno solo ENTRO lo stesso periodo (mese), non la fedeltà
   cross-stagione: la finestra "quanto indietro guardare" è una decisione non ancora presa.
3. **`nuovi_percorsi`** — oggi riceve sempre `itinerari_periodo=[]` (nessuna persistenza reale
   degli itinerari generati): il valore `0.0` prodotto va letto come "wiring assente", non
   "nessun percorso nuovo osservato".
4. **Dashboard Flutter (`DashboardScreen`)** — scritta seguendo le convenzioni dell'app, MAI
   compilata né testata in questa sessione (SDK assente): verificata solo a lettura.
5. **`behavior_event` senza scoping temporale** — il Recommender legge l'intera tabella senza
   filtro su `ts`: un evento sintetico di verifica (anche datato nel futuro) altera SUBITO il
   ranking reale finché non viene ripulito (`scripts/pulisci_eventi_prefisso.py`).
6. **CORS aperto su `/dashboard/*`** (`allow_origins="*"`) — necessario per
   `scripts/dashboard_viewer.html` (viewer locale senza build), scoped a GET/`/dashboard/*` e
   verificato che non copra altri path/metodi, ma va ristretto a origin specifici prima di
   qualunque deploy pubblico del BFF.

---

## 5. Diagramma testuale del flusso runtime (coerente col codice reale)

Percorso centrale — dalla conversazione all'itinerario spiegabile (`services/api/api/main.py`,
`services/experience-engine/experience_engine/engine.py`):

```
Turista (app Flutter / client HTTP)
   │
   │ POST /session/onboarding  { risposte[], lingua }
   ▼
BFF (api.main) ──▶ rag.onboarding.profile_from_answers(risposte)
   │
   ▼
EmotionalProfile  (curiosità, contemplazione, arte, con_bambini, tempo_disponibile_min...)
   │
   │ POST /itinerary  { person_id, kind, profile, signal, luoghi_gia_visti }
   ▼
BFF: create_itinerary(ctx)
   │
   ├─ (1) source = get_candidate_source()             # Neo4jCandidateSource | SeedCandidateSource
   │      candidates = source.candidates(ctx)          # cypher/10_candidates.cypher
   │      → list[GraphCandidate]   IL GRAFO PROPONE, NON DECIDE
   │
   ├─ (2) try:  score_fn = recommender.costruisci_score_fn(get_event_repository(), candidates)
   │      except Exception:  score_fn = None            # arricchimento OPZIONALE, mai un 500
   │
   ▼
experience_engine.engine.compose_itinerary(ctx, candidates, reason_fn=compose_reason, score_fn)
   │        L'AI EXPERIENCE ENGINE — L'UNICO COMPONENTE CHE DECIDE
   │
   ├─ (a) rules.passa_filtri_duri()      → filtro etico DURO (accessibilità, abbonamento
   │                                        partner, luoghi già visti...): esclude, non ordina
   ├─ (b) score_fn OR rules.calcola_score() → punteggio di pertinenza; se il recommender è
   │                                        presente PENALIZZA (mai premia) la concentrazione
   ├─ (c) _seleziona_tappe()             → composizione a budget (tempo_disponibile_min),
   │                                        diversificazione, determinismo a parità di score
   └─ (d) rag.reasons.compose_reason()   → reason OBBLIGATORIO (min_length=1) per OGNI tappa
   ▼
Itinerary { person_id, stops: [{ experience_id, arrivo, durata_min, reason }], generated_at }
   │
   ▼
Risposta HTTP 200 → app Flutter (ogni tappa con orario + reason in evidenza)
```

Segnale che cambia a runtime (pioggia, affollamento, stanchezza):

```
App → POST /itinerary/adapt { itinerary, signal }
        → experience_engine.engine.adapt_itinerary(...)  → stesso motore, stessi filtri duri,
          reason_fn = rag.reasons.adapt_reason  → Itinerary riscritto, adattato_da_segnale=true
```

Anelli di retroazione (mai un secondo decisore, solo dati che rientrano come input opzionale
o come reporting):

```
stops vissuti ──▶ POST /events (BehaviorEvent) ──▶ Postgres/Neon (behavior_event)
                                                        │
                                                        ▼
                                          recommender.costruisci_score_fn
                                          (penalità storica, mai un premio) ──▶ rientra in (2) sopra

esperienza vissuta ──▶ POST /memory (MemoryContribution, consenso obbligatorio)
                              │
                              ▼
                   urban_memory.submit_contribution → curatela → (:Memoria)-[:RIGUARDA]->(...)
                              │
                              ▼ (letto, mai scritto, da)
                   intelligence_index.dashboard.indice_per_dashboard / celle_flusso
                              │  (+ behavior_event + graph.metrics.grado_semantico)
                              ▼
                   GET /dashboard/index | GET /dashboard/flows
                   (gate k=10 in UN solo punto — intelligence_index.soglia — mai aggirabile)
                              │
                              ▼
                   DashboardScreen (Flutter, non compilata) | scripts/dashboard_viewer.html (verificato)
```
