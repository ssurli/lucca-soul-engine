# ENGINE_INVARIANTS.md — fatti verificati sull'AI Experience Engine

> Non un design doc. Un **elenco di fatti**, ognuno riletto nel codice al momento in cui
> questo documento è stato scritto (non ricordato, non presunto). Dove un fatto è un
> LIMITE anziché una garanzia, rimanda a `docs/LIMITI.md`. Se il codice diverge da questo
> documento in futuro, **vince il codice**: questo file va aggiornato, non il contrario.

## Perimetro

Questo documento copre `services/experience-engine` (`rules.py`, `engine.py`) — l'unico
componente che **decide** (CLAUDE.md: «il grafo propone, il recommender ordina, la RAG
racconta»). Non copre i fatti su Urban Memory / aggancio al grafo / curatela: quelli sono
in `docs/STATE_MACHINE.md` §1, verificati per uno scopo diverso (progettare il curatore),
non duplicati qui.

**Eccezione esplicita (§11 sotto)**: due fatti sul grafo, emersi progettando la curatela
(Fase 3, `docs/brief_fase3_promozione_traccia.md` §2) ma veri a prescindere da quale
servizio tocca il grafo — non specifici di `experience-engine`, non specifici della
curatela. Vivono qui perché sono *verità di sistema*, non design di un componente.

## 1. Un solo punto di decisione, pipeline a 6 passi

`compose_itinerary` (`engine.py:321`):

1. Filtri duri etici → `rules.passa_filtri_duri` — **SELEZIONA** (ammette/esclude).
2. Scoring → `score_fn` (default `rules.calcola_score`) — **ORDINA**, mai seleziona: riceve
   solo i candidati già ammessi dal passo 1, non può "salvare" un escluso.
3. Composizione a budget con diversificazione → `_seleziona_tappe`.
4. `reason` obbligatorio per ogni tappa → `_costruisci_stops`.
5. Segnali FLUTTUANTI pertinenti, solo in coda → `_aggiungi_tappe_fluttuanti`.
6. `:Evento` PROMOSSI pertinenti E in finestra temporale, solo in coda →
   `_aggiungi_tappe_eventi_promossi` (vedi §8-bis).

`score_fn`/`reason_fn` sono iniettabili (Wave 3b) ma il default a `None` riproduce
esattamente il comportamento MVP — nessun chiamante esistente cambia comportamento
introducendo l'iniezione.

## 2. I cinque filtri duri di `passa_filtri_duri` (`rules.py:118`, in quest'ordine esatto)

1. `profile.accessibilita_richiesta` → solo `esperienza.accessibile=True`. Non negoziabile:
   nessuno score può reintrodurre una tappa inaccessibile a chi l'ha chiesta.
2. `esperienza.place_id in luoghi_gia_visti` → esclusa.
3. `signal.affollamento.get(place_id, 0.0) >= SOGLIA_AFFOLLAMENTO_CRITICO` (**0.8**) →
   esclusa. Vincolo etico duro (distribuzione dei flussi), non una preferenza.
4. `partner_id is not None and not partner_abbonamento_attivo` → esclusa. **L'unica leva
   commerciale ammessa** ed è un interruttore booleano di PRESENZA, non un input dello
   scoring.
5. `not rientra_in_orario(orari_apertura, signal.giorno_settimana, signal.ora)` → esclusa
   (Wave 3a+, orari di apertura). Se `orari_apertura=[]` o `signal.giorno_settimana is None`
   il filtro non esclude MAI nulla — nessun default fabbricato. `giorno_settimana` è RICAVATO
   da `Signal.data` quando il client manda solo la data (l'app lo fa sempre): per l'app il
   filtro è attivo; effetto reale nullo finché il grafo non popola `orari_apertura`
   (`docs/LIMITI.md`, voce "`giorno_settimana` ricavato da `Signal.data`").

Nessun sesto filtro esiste oggi. Se se ne aggiunge uno, va qui — non altrove, non
duplicato.

## 3. `calcola_score` — cosa NON legge mai (visibilità non acquistabile)

Verificato sia da lettura diretta sia da un test-guard AST + un test comportamentale
(score invariante a partner/prezzo/attribuzione, stesso file `rules.py:165`):

- **`experience.partner_id`** — mai letto.
- **`experience.prezzo_eur`** — mai letto.
- **`experience.partner_abbonamento_attivo`** — decide solo la PRESENZA (filtro 4 sopra),
  mai il punteggio: quando un partner c'è, concorre esattamente come tutti gli altri.
- **`candidate.attribuzione`** — vive SOLO nel `reason` finale (disclosure "Offerta da…",
  aggiunta in coda dal motivo reale), mai nello scoring, in particolare mai nella
  componente `sorpresa` (che conta `len(candidate.connessioni)` e temi, nient'altro).
- **`Signal.eventi_attivi`** (segnali fluttuanti) — mai letto: nessuna esperienza
  permanente vede il proprio punteggio cambiare per via di un segnale fluttuante.
- **`ExperienceNode.orari_apertura`** — letto SOLO dal filtro duro 5, mai dallo scoring.

Nessun prezzo altera lo score: non esiste un pagamento che modifichi questo comportamento
(CLAUDE.md, «nessuno spazio è acquistabile»).

## 4. Funzioni pure condivise — un solo punto, tutti i chiamanti elencati

Principio ricorrente in questo repo: *un vincolo verificato in un solo punto è auditabile,
distribuito no.* Ogni funzione sotto ha **una sola definizione** in `packages/contracts`
o `rules.py`, e questi sono **tutti** i chiamanti verificati oggi:

| Funzione | Definita in | Chiamata da |
|---|---|---|
| `contracts.rientra_in_orario` | `packages/contracts/contracts/models.py:242` | `rules.passa_filtri_duri` (composizione) · `engine._migliore_alternativa` (adattamento) · `marketplace.service.request_booking` (prenotazione) |
| `contracts.segnale_fluttuante_ammissibile` | `packages/contracts/contracts/models.py:117` | `rules.segnali_fluttuanti_pertinenti` |
| `rules.segnali_fluttuanti_pertinenti` | `rules.py:270` | `engine._aggiungi_tappe_fluttuanti` — **solo** in `compose_itinerary`, mai in `adapt_itinerary` (vedi §6) |
| `rules.affinita_temi` | `rules.py:109` | `calcola_score` (3 volte) · `_coerente_col_profilo` |
| `rules.evento_in_finestra` / `rules.occorrenza_attesa_giorni` | `rules.py` | `rules.eventi_promossi_pertinenti` (la decisione "in finestra") · `rules.giorno_occorrenza_attesa` → `engine._reason_evento_promosso` (solo il testo, mai la decisione) |
| `rules.eventi_promossi_pertinenti` | `rules.py` | `engine._aggiungi_tappe_eventi_promossi` — **solo** in `compose_itinerary`, mai in `adapt_itinerary` |
| `rules.calcola_score` | `rules.py:165` | `compose_itinerary` (via `score_fn` default) · `_migliore_alternativa` (per ordinare le alternative in adapt) |

Tre chiamanti diversi per "cosa significa aperto" (`rientra_in_orario`), un solo modello.

## 5. Determinismo

- `_ordina_per_score`/`_migliore_alternativa`: a parità di score, tie-break su
  `experience_id` — mai un ordine arbitrario del dizionario/lista.
- `_seleziona_tappe`: composizione a budget deterministica dato lo stesso input.
- `compose_itinerary`: stesso profilo + stesso segnale + stessi candidati → stesso
  itinerario, sempre. Profili diversi possono (devono) produrre itinerari diversi — è il
  criterio d'accettazione centrale di Wave 1.

## 6. Cosa `adapt_itinerary` NON eredita da `compose_itinerary` (verificato, non presunto)

`adapt_itinerary` (`engine.py:423`) non richiama `compose_itinerary`: ha una propria logica
di riscrittura mirata, con conseguenze concrete:

- `_migliore_alternativa` (`engine.py:375`) **reimplementa a mano** un sottoinsieme dei
  filtri duri — accessibilità, `al_chiuso`, affollamento, **e ora anche orari di apertura**
  (fix di questa sessione: prima mancava, trovato da un giro dedicato di ethics-guardian,
  non da autovalutazione) — ma **non chiama `passa_filtri_duri`**: sono due
  implementazioni parallele della "stessa" idea di filtro, non un'unica funzione condivisa.
- **Non verifica `partner_abbonamento_attivo`** — gap pre-esistente, non chiuso da questa
  sessione, documentato in `docs/LIMITI.md`: un partner con abbonamento non attivo può oggi
  essere reintrodotto come alternativa in adattamento, mentre `passa_filtri_duri` lo esclude
  sempre in composizione iniziale.
- **Non chiama mai `segnali_fluttuanti_pertinenti`**: un segnale fluttuante comparso *dopo*
  la composizione iniziale non entra mai via `adapt_itinerary` — solo `compose_itinerary`
  ne tiene conto.
- Una tappa fluttuante **già presente** sopravvive a un `adapt` non per una garanzia
  progettata, ma come **effetto collaterale** di `_stub_da_stop` (`engine.py:548`): quando
  `adapt_itinerary` incontra un `experience_id` (qui `fluttuante-<id>`) che non è tra i
  `candidates` correnti, ricostruisce un candidato "fantasma" con `al_chiuso=True` e
  `place_id=stop.experience_id` (un id che non compare mai in `signal.affollamento`). Per
  costruzione questo rende la tappa fluttuante immune sia alla riscrittura da pioggia
  (`piove_e_aperto` richiede `not al_chiuso`, sempre falso qui) sia da affollamento
  (`signal.affollamento.get(place_id, 0.0)` è sempre `0.0`). **Verificato con un test
  dedicato** che forza una vera ricostruzione (non solo l'invarianza banale del path
  "niente cambia").

## 7. Limite di progettazione: i filtri valutano un solo istante

`passa_filtri_duri` valuta OGNI candidato contro **lo stesso `Signal`** (l'istante di
inizio della composizione), non contro l'orario effettivo in cui quella tappa verrebbe
visitata nella sequenza dell'itinerario. Vale sia per l'affollamento sia per gli orari di
apertura — più visibile per gli orari (che cambiano nettamente in poche ore: un luogo
aperto alle 9 può chiudere alle 13, e una tappa alle 15 nello stesso itinerario non viene
ri-verificata contro quell'orario specifico). Non corretto in questa sessione: fuori
scope, documentato in `docs/LIMITI.md`.

## 8. Segnali fluttuanti (`Signal.eventi_attivi`) — vincoli del passo 5

- Costante `DURATA_TAPPA_FLUTTUANTE_MIN = 15` (`rules.py:63`): durata fissa per
  definizione ("un violinista in piazza non è una visita guidata"), non un campo
  dichiarato dal segnale.
- Costo per aggiunta: `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (10) + `DURATA_TAPPA_FLUTTUANTE_MIN`
  (15) = 25 minuti, addebitati al budget `profile.tempo_disponibile_min`. Se non c'è
  spazio, la tappa **non si aggiunge**: mai forzata oltre il budget.
- Aggiunte **solo in coda**, mai in sostituzione: le tappe 1-4 (quelle scelte dai passi
  1-4 della pipeline) restano esattamente come composte.
- Namespace separato: `experience_id = f"fluttuante-{segnale.id}"` — non collide mai con
  gli id del grafo.
- `segnali_fluttuanti_pertinenti` applica due condizioni, **entrambe necessarie**, nello
  stesso ordine sia nel codice sia nel test: `segnale_fluttuante_ammissibile` (booleano
  dichiarato `non_commerciale`, filtro duro, **prima**) e `_coerente_col_profilo` (almeno
  un tema in comune con una dimensione di profilo > 0, **dopo**) — un segnale commerciale
  ma coerente col profilo è scartato allo stesso identico modo di uno commerciale e
  incoerente.
- Nessun tetto al numero di tappe fluttuanti aggiungibili, nessun filtro di affollamento o
  accessibilità applicato alla tappa fluttuante stessa (limiti dichiarati, non chiusi, in
  `docs/LIMITI.md`).

## 8-bis. `:Evento` promossi — vincoli del passo 6 (finestra temporale)

- Il motore riceve FATTI (`EventoPromosso.ultima_occorrenza`, data locale già convertita dal
  BFF con `CITY_TZ`; `cadenza_giorni` finita e `> 0`, `allow_inf_nan=False`) e decide da solo: occorrenza proiettata più vicina
  `ultima_occorrenza + k·cadenza_giorni`, k ≥ 1 intero; in finestra se lo scarto è
  `<= FRAZIONE_FINESTRA_CADENZA × cadenza_giorni` (0.15, tuning differito) più una
  tolleranza float nominata (`TOLLERANZA_FINESTRA_GIORNI`), bordo incluso. Finestra
  proporzionale alla cadenza, mai fissa.
- `Signal.data is None` → nessuna tappa-evento (fail-closed). Proiezione non
  rappresentabile come `date` → evento fuori finestra, mai un'eccezione.
- Due condizioni, entrambe necessarie: `_coerente_col_profilo` E in finestra. Nessun
  filtro commerciale qui (il vaglio è a monte, alla radice del ledger e alla promozione
  umana — docstring di `eventi_promossi_pertinenti`).
- `stato`/frenato sono filtrati dal BFF prima: la finestra decide solo "quando", mai "se è
  vivo".
- Stessi vincoli di budget e posizione delle tappe fluttuanti (§8):
  `DURATA_TAPPA_EVENTO_MIN`, costo a budget, solo in coda, mai sostituzione.
- `calcola_score` e `passa_filtri_duri` non leggono `Signal.data` (§3 resta vero).

## 9. Separazione strutturale da Marketplace

`services/marketplace` e `services/experience-engine` non si importano a vicenda —
verificato con un test-guard che analizza l'AST degli import (non solo grep testuale, che
un rename potrebbe eludere). `CommissionRecord` (Wave 3a) non è mai raggiungibile da
`experience_engine.rules`/`engine`: la commissione è un fatto del marketplace, non
un'informazione che il motore etico può vedere o usare per decidere.

## 10. Spiegabilità: `reason` sempre non vuoto

Ogni `ItineraryStop` — incluse le tappe fluttuanti (`_reason_fluttuante`, `engine.py:259`)
e le tappe non toccate da un adattamento — porta un `reason` non vuoto (`min_length=1` nel
contratto). Nessun path del motore produce una tappa senza spiegazione in italiano.

## 11. Invarianti del grafo — repo-wide, non specifici di `experience-engine` (Fase 3)

Due fatti emersi progettando il curatore (`docs/STATE_MACHINE.md`) ma che riguardano il
grafo nel suo insieme, non un componente — annotati qui perché sopravvivano oltre la
sessione che li ha scoperti, come impone `docs/brief_fase3_promozione_traccia.md` §2.
**Stato epistemico diverso tra i due — non confonderli:**

- **A — Append-only sui target di `riguarda`. VERO OGGI, verificato nel codice.** Un grep
  dell'intero repository per `DETACH DELETE|DELETE \(|REMOVE \(|DROP CONSTRAINT` produce
  **una sola occorrenza** in tutto il repo: un comando Cypher documentato (non eseguibile
  da codice applicativo) in `services/urban-memory/README.md`, per pulizia manuale una
  tantum — colpisce SOLO nodi `:Memoria` orfani, MAI `:Luogo`/`:Bottega`/`:Artista`. Nessun
  percorso di codice applicativo cancella questi tre tipi di nodo, oggi. Conseguenza: una
  race "il target esisteva quando riferito, non esiste più dopo" è impossibile via codice
  applicativo in questo repository (resta teoricamente possibile solo fuori dal codebase,
  via accesso diretto a Neo4j Browser — rischio di governance dell'accesso, non proprietà
  della macchina a stati).
- **B — "Curato tira aggancio": VERO OGGI, riverificato contro il codice (non più
  "DECISIONE CONGELATA, non ancora vera" — implementato e confermato PASS da un giro
  dedicato di `ethics-guardian`, due passaggi: un FAIL iniziale su un bug reale, poi PASS
  dopo la correzione, riverificato contro il codice scritto, non per analogia).**
  `curate_contribution` (`services/urban-memory/urban_memory/service.py:168`) accetta ora
  un parametro `linker` opzionale: se fornito, SUBITO dopo che `repo.curate(memory_id)` ha
  portato `curato=True`, la stessa funzione tenta l'aggancio al grafo attraverso il seam
  unico `_innesca_aggancio` (`service.py:256`, condiviso da `InMemoryMemoryRepository` e
  `PostgresMemoryRepository` tramite il solo `Protocol MemoryRepository` — nessuna logica
  duplicata tra le due implementazioni). Esito registrato in un nuovo campo del contratto,
  `MemoryContribution.stato_aggancio: MemoryLinkState | None`
  (`packages/contracts/contracts/models.py`, valori `AGGANCIATO`/`AGGANCIO_FALLITO`) — non
  più un booleano isolato. `aggancio_fallito` è un'attesa RECUPERABILE, mai un vicolo
  cieco: `retry_link_contribution` (`service.py:289`) riusa lo stesso seam per riprovare, e
  `list_aggancio_fallito()` (`repository.py`) espone la coda di recupero su entrambe le
  implementazioni. Ogni transizione automatica è loggata (chi=sistema, quando, esito — MAI
  il contenuto del contributo: verificato che nessun log contenga `contributor_id`, `testo`
  o `media_uri`).

  **Bug reale trovato e corretto durante la verifica dedicata**: la prima versione
  dell'automazione lasciava `submit_contribution` senza azzerare `stato_aggancio` in
  ingresso — un client HTTP (`POST /memory` accetta un `MemoryContribution` grezzo) poteva
  fabbricare `stato_aggancio=AGGANCIATO` fin dal conferimento, e quel valore sopravviveva
  indisturbato perché l'unico percorso di produzione reale che cura (vedi sotto) non lo
  toccava. Corretto in `service.py:179`:
  `contribution.model_copy(update={"curato": False, "stato_aggancio": None})` — stesso
  trattamento di `curato`. Due test di regressione dedicati in
  `services/urban-memory/tests/test_service.py`.

  **Caveat esplicito, per-chiamante, non globale** (raccomandato dal secondo giro di
  `ethics-guardian`, non un dettaglio da sottintendere): l'automazione è VERA nel codice ed
  è **esercitata oggi in un solo percorso di produzione reale**, `python -m
  urban_memory.verify` (contro Neon+Aura veri: il passo 3 dello script,
  `urban_memory/verify.py:177-179`, passa ora `linker=linker.link` a
  `curate_contribution`; il passo 5, ex primo-aggancio, è stato trasformato in una
  dimostrazione di idempotenza/recupero, `_verifica_aggancio_idempotente`,
  `verify.py:231-287`). **Non esiste ancora alcun endpoint HTTP di curatela**
  (`docs/STATE_MACHINE.md` §0) — quando ne verrà costruito uno, dovrà passare `linker=`
  ESPLICITAMENTE per ereditare l'automazione, esattamente come già vale per
  `target_checker`: ometterlo riaprirebbe il buco "curato ma non agganciato" per quel
  chiamante specifico. L'invariante è quindi vera per costruzione per chi passa `linker=`,
  non per costruzione per ogni chiamante futuro.

  **Osservazioni non bloccanti, tracciate in `docs/LIMITI.md`, non in questa voce**: un
  contributo `curato=True` con `stato_aggancio` diverso da `AGGANCIATO` resta comunque
  visibile via `GET /memory/{place_id}` (`get_curated`/`contributions_for_place` filtrano
  solo su `curato`); nessun rate limit su `retry_link_contribution`. Nessuna delle due
  invalida l'invariante B: sono proprietà collaterali del meccanismo, non del suo nucleo.
