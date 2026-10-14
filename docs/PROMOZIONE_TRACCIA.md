# PROMOZIONE_TRACCIA.md — Fase 3: il ledger delle tracce e la promozione fluttuante→permanente

> **Stato del documento: PARZIALMENTE implementato — non più "design, non implementazione"
> in blocco.** Un task successivo a questo design ("fondazione del canale fluttuante:
> persistenza + ledger") ha reso REALE §1 (il ledger delle tracce, tabella
> `traccia_luogo`) e §2(a) (`:Luogo.ultima_traccia_il`, scritta via Cypher versionato) —
> verificato contro il codice, non presunto, stessa disciplina di sempre. **Un secondo
> task ("rilevamento pattern ricorrenti + promozione :Evento + cestino") ha reso REALE
> anche una FETTA di §3** — il rilevamento della ricorrenza e la promozione a `:Evento`
> via curatela umana da CLI, dettaglio nella nota REALTÀ vs DESIGN dentro §3 sotto. **Un
> terzo task ("verifica §0 — frizione, sola lettura" + implementazione conseguente) ha reso
> REALE anche la frizione automatica a cadenza** (`attivo ⇄ sospeso → dormiente`,
> `urban_memory.frizione_pattern`, comando `python -m urban_memory.frizione_pattern`) —
> dettaglio nella nota REALTÀ vs DESIGN dentro §3 sotto, subito dopo quella del rilevamento/
> promozione. **Un quarto task ("brief vincolante — consumo degli `:Evento` v1 minima") ha
> reso REALE anche il CONSUMO**: un `:Evento` promosso e `stato='attivo'`, pertinente al
> profilo, compare ora come tappa in coda in un itinerario reale
> (`experience_engine.engine._aggiungi_tappe_eventi_promossi`, letto dal grafo dal BFF —
> `services/api/api/deps.get_evento_reader`/`main.create_itinerary` — e passato a
> `compose_itinerary` come nuovo tipo condiviso `contracts.EventoPromosso`). **Questo chiude
> il cerchio traccia → promozione → frizione → consumo**: un fluttuante che si ripete
> abbastanza volte non resta più un fatto solo interno a `services/urban-memory`, arriva
> davvero a un visitatore. Dettaglio nella nota REALTÀ vs DESIGN dentro §3 sotto, in coda alle
> altre tre. **Un sesto task, successivo al freno di emergenza (quinto, descritto più sotto) — "finestra
> temporale degli `:Evento` promossi" — ha reso REALE
> anche la FINESTRA**: la v1 del consumo faceva comparire un `:Evento` in qualunque giorno;
> ora compare solo se la data della visita (`Signal.data`, mandata dal client) cade in una
> finestra PROPORZIONALE alla cadenza attorno all'occorrenza proiettata più vicina
> (`experience_engine.rules.evento_in_finestra`; fail-closed senza data) — dettaglio nella
> nota REALTÀ vs DESIGN dentro §3 sotto, in coda alle altre. **Il filtro
> di ammissibilità commerciale sul pattern promosso è stato CHIUSO in questa stessa
> collaborazione**, non lasciato aperto: un giro dedicato di `ethics-guardian` aveva trovato
> (verdetto "GARANZIA NON PRESERVATA") che un segnale commerciale poteva attraversare indenne
> l'intera catena fino a comparire in un itinerario reale — il filtro esistente
> (`contracts.segnale_fluttuante_ammissibile`) proteggeva solo il consumo diretto di
> `Signal.eventi_attivi`, mai il percorso del ledger. Corretto alla RADICE (non sul consumo:
> `EventoPromosso` resta senza campo `non_commerciale`, per design — non serve, il filtro
> agisce a monte), in `urban_memory.canale_fluttuante.sweep_and_fetch_active`: un segnale non
> ammissibile non deposita più alcuna `Traccia`, quindi non può mai maturare in un pattern
> ricorrente. Un secondo giro di `ethics-guardian`, indipendente, ha riverificato e confermato
> "GARANZIA ORA PRESERVATA" (fino al limite noto e già accettato dell'auto-dichiarazione
> mentita di `non_commerciale`, invariato — dettaglio in `docs/LIMITI.md`, voce estesa su
> `SegnaleFluttuante.non_commerciale`). **Un quinto task ("brief vincolante — freno di
> emergenza v1 minima") ha reso REALE anche l'OVERLAY DI SICUREZZA**: `urban_memory.
> freno_pattern` (comando `python -m urban_memory.freno_pattern tira|rilascia`) scrive una
> proprietà separata `e.frenato` sul nodo `:Evento` (mai `e.stato`), letta dallo stesso filtro
> di consumo (`services/api/api/main.py`, ora `stato == 'attivo' and not frenato`) — un evento
> frenato smette di essere raccomandato ma continua a depositare tracce normalmente (il ledger
> resta veritiero). Tabella Postgres `pattern_frenato` (append-only, senza UNIQUE — il freno è
> ripetibile), motivazione testuale obbligatoria su ogni tiro. Verificato da un giro DEDICATO
> di `ethics-guardian`, due passaggi: **FAIL iniziale** su un bug reale (`attore` non validato
> prima di scrivere, poteva lasciare un `:Evento` frenato senza riga di audit recuperabile),
> **PASS** dopo la correzione (stessa guardia già usata per `motivazione`, replicata per
> `attore`, riverificata riga per riga). Dettaglio nella nota REALTÀ vs DESIGN dentro §3 sotto,
> in coda alle altre quattro, e in `docs/STATE_MACHINE.md` §4-bis(b). **Resta DESIGN PURO,
> deliberatamente fuori scope per questa v1**: la lista nominale dei permessi-freno e il
> grant/revoke (§7.14.1, residuo implementativo non ancora deciso) — il percorso oggi è
> fidato/CLI provvisorio, stessa postura di `curatela_pattern.py`/`frizione_pattern.py`. **§2(b)
> (il bagliore), più la corsia fluttuanti
> `blocked`/`approved`/`rejected` di `docs/STATE_MACHINE.md` §4, restano DESIGN PURO** —
> nessuna riga di quelle parti è eseguibile. Ogni sezione sotto è
> annotata esplicitamente REALE o DESIGN, non lasciata all'inferenza. Fonte del design
> originario:
> `docs/brief_fase3_promozione_traccia.md` (vincolante, ma il codice lo sovrasta — §0 del
> brief). Questo documento presuppone Fase 1/2 approvate (`docs/STATE_MACHINE.md`) e i due
> invarianti del motore (`docs/ENGINE_INVARIANTS.md`): non li riapre, costruisce sopra.
>
> Prima di disegnare, il brief impone cinque verifiche contro il codice (§3 del brief). I
> risultati, in breve (dettaglio completo nella conversazione che ha prodotto questo
> documento, non ripetuto qui):
>
> 1. Nessun audit dell'`expired` porta già `place_id`+`temi` — `expired` non è implementato,
>    non c'è un log da promuovere. Il ledger è un meccanismo nuovo.
> 2. **Né `Signal` né `SegnaleFluttuante` portano un `creato_il`.** `SegnaleFluttuante` ha
>    `id, descrizione, temi, place_id, non_commerciale` — niente timestamp. `Signal.ora` è
>    un'ora del giorno (`time`), non una data. **Decisione accettata per sciogliere questo
>    (Strada B, vedi §1 sotto): NON si aggiunge un campo a `SegnaleFluttuante`/`Signal` — restano
>    transitori esattamente come da contratto oggi.** Il `creato_il` della traccia è
>    timbrato dal server nel momento di `expired`, non letto dal segnale. **Corretto in
>    seguito** (bug di correttezza, §1 sotto): il timbro è il `valido_fino` del segnale —
>    sempre un valore del server, calcolato in `submit_signal` — non l'istante dello sweep.
> 3. Nessuna tabella Postgres esistente porta già `place_id`+`temi`: `behavior_event` è il
>    precedente idiomatico più vicino (append-only, chiave surrogata, `TIMESTAMPTZ`) ma non
>    la tabella giusta da cui proiettare una vista — serve una tabella nuova, con la stessa
>    idiomatica.
> 4. `:Evento` esiste già nello schema del grafo (`00_schema.cypher`, constraint di unicità
>    su `id`) ma **riservato e vuoto**: zero nodi nel seed, zero proprietà, zero relazioni.
>    `seed_lucca.py` lo dice esplicitamente: *"`Evento`... nello schema ma non ha seed in
>    questa wave: `Evento` arriva con i segnali reali"* — è il momento per cui era stato
>    preparato.
> 5. Nessuno stato chiuso/dormiente esiste oggi per `:Bottega`/`:Luogo` (entrambe dataclass
>    minime in `seed_lucca.py`, nessun campo di stato). Nessun precedente da riusare per
>    analogia per la dormienza del pattern.

---

## 1. Il ledger delle tracce — forma dati — **REALE, implementato**

**Verificato contro il codice**: `services/urban-memory/sql/01_fluttuante_schema.sql`
(tabella `traccia_luogo`), `services/urban-memory/urban_memory/traccia_repository.py`
(`Traccia`, `TracciaRepository` — doppia implementazione InMemory/Postgres). Il design
sotto è rispecchiato fedelmente dal codice, non solo un piano.

**Anagrafica minima** (brief §5): `place_id`, `temi[]`, `creato_il`. Nient'altro — niente
`contributor`, niente PII, niente testo libero, niente descrizione dell'occorrenza. È il
distillato del passaggio, non un secondo `SegnaleFluttuante` persistito.

- **`place_id`**: stesso spazio di `MemoryContribution.riguarda` — un id che esiste (o è
  esistito) come `:Luogo`/`:Bottega`/`:Artista`. Nessun controllo di esistenza al momento
  del deposito: il fluttuante era già stato validato a monte (pre-check `blocked` nella
  corsia fluttuanti, `STATE_MACHINE.md` §4) quando è diventato `approved`.
- **`temi[]`**: stessa forma di `SegnaleFluttuante.temi` / `ExperienceNode.temi` — riusa
  `experience_engine.rules.affinita_temi`, un solo vocabolario di affinità, mai un secondo
  criterio inventato per la traccia.
- **`creato_il`**: **Strada B** (decisione accettata, scioglie il check 2). Timbrato dal
  SERVER nell'istante in cui l'occorrenza approvata raggiunge `expired` (design originario:
  vedi la CORREZIONE in fondo a questo punto — il timbro reale è `valido_fino`, e l'analogia
  con `behavior_event.ricevuto_il`, che è il `now()` della ricezione, non vale più). `SegnaleFluttuante`/`Signal` non guadagnano alcun campo:
  restano transitori esattamente come da contratto oggi (nessun tocco a
  `packages/contracts`). Semanticamente corretto, non solo comodo: la traccia data il
  **passaggio-diventato-passato** (il fantasma si stacca dall'occorrenza e si deposita sul
  luogo), non la nascita del segnale — coerente con "place-anchored, non
  occurrence-anchored" (brief §5): al luogo non importa quando l'occorrenza è nata, solo
  che è stata reale (approvata) e ora è storia (scaduta).
  **CORREZIONE (bug di correttezza, REALE):** "l'istante in cui raggiunge `expired`" era in
  pratica l'istante dello SWEEP PIGRO (`canale_fluttuante.sweep_and_fetch_active`, eseguito
  solo quando qualcuno chiama `POST /itinerary`): con poco traffico la traccia di un evento
  del sabato poteva essere timbrata lunedì, e la finestra degli `:Evento` e `cadenza_giorni`
  ne ereditavano il rumore. Ora `creato_il = segnale.valido_fino` normalizzato in UTC — la
  fine della finestra del segnale, il momento in cui il passaggio È diventato passato, non
  quello in cui qualcuno se n'è accorto. Strada B intatta: `valido_fino` è calcolato dal
  server (`submit_signal.py`), nessun campo nuovo su `SegnaleFluttuante`.
  `:Luogo.ultima_traccia_il` riceve lo stesso valore, con scrittura MONOTONA
  (`cypher/40_luogo_traccia_write.cypher`: tiene il massimo, perché un segnale scaduto prima
  può essere spazzato dopo). Le tracce già nel ledger NON sono riscritte (append-only):
  restano timbrate allo sweep — `docs/LIMITI.md`.

**Identità della riga**: nessuna naturale, come `behavior_event` — due tracce identiche in
`place_id`/`temi`/istante restano due passaggi distinti (due violinisti diversi nello
stesso punto nello stesso minuto non sono lo stesso fatto). Chiave surrogata, non una
chiave composta.

**Limite reale trovato durante l'implementazione, non anticipato da questo design**: lo
sweep (`attivo → expired`, atomico) e il deposito della traccia non condividono una
transazione — un fallimento del deposito DOPO che lo sweep ha già committato causa la
perdita PERMANENTE e silenziosa della traccia per quel singolo segnale (isolata dal resto
del batch, non a cascata — trovato e corretto da un giro dedicato di `ethics-guardian`).
Il ledger resta quindi "immortale" per ogni riga che riesce a depositarsi, ma NON garantisce
che ogni segnale scaduto depositi effettivamente la sua riga. Dettaglio completo in
`docs/LIMITI.md`.

**Idiomatica — stessa forma di `behavior_event`, non una vista sopra di esso:**
- Tabella propria, append-only, con la propria migrazione dedicata — stesso pattern delle
  tre corsie esistenti (`recommender.migrate`, `marketplace.migrate`, `urban_memory.migrate`
  hanno ciascuna il proprio schema versionato + comando `migrate`). Questa è una quarta
  corsia, non un'aggiunta dentro una delle tre: non è un evento comportamentale
  (`behavior_event` ha `experience_id`, non un luogo; è ancorato a un'esperienza permanente,
  non a un fluttuante), non è un contributo di memoria (`memory_contribution` porta
  `contributor_id`, esplicitamente escluso qui), non è una prenotazione.
- Solo `CREATE ... IF NOT EXISTS`, nessun `DROP`, rieseguibile da zero in un comando — stesso
  vincolo non negoziabile di CLAUDE.md per ogni schema Postgres del repo.
- Indice per aggregazione-per-luogo (`place_id`): è la query che conta — "tutte le tracce di
  questo `place_id`" — mai una traversata Neo4j.
- Nessuna FK verso il grafo: Neo4j e Postgres restano store separati, nessuna transazione
  condivisa — stesso limite già accettato per `memory_contribution.riguarda`.
- **Confermato dal check §3**: non può essere una vista filtrata su `behavior_event` (che
  non porta né `place_id` né `temi`, e il cui `tipo` è un `CHECK` chiuso su un insieme fisso
  che non include nulla su fluttuanti/tracce) né su `memory_contribution` (porta
  `contributor_id`, esplicitamente vietato dall'anagrafica minima).
- **Collocazione del codice — CHIUSA**: `services/urban-memory` (stesso spirito del white
  paper — "Urban Memory cresce con l'uso": un fluttuante approvato che scade è, in un certo
  senso, un conferimento automatico e anonimo alla memoria del luogo). Decisione presa
  dall'orchestratore al momento dell'implementazione (non un servizio dedicato nuovo),
  coerente con l'istruzione del brief di modellare la persistenza su
  `urban_memory/repository.py` — nuovi moduli `segnale_repository.py`/
  `traccia_repository.py`/`canale_fluttuante.py`/`luogo_traccia_link.py` accanto a quelli
  esistenti, non duplicati altrove.

**Solo occorrenze approvate-e-poi-scadute depositano — PRINCIPIO valido, ma vacuamente vero
oggi.** Le rifiutate: nulla (brief §5, estende "le rifiutate non fanno pattern" di Fase 2 a
"le rifiutate non fanno traccia"). Senza questo confine, occorrenze respinte
"accenderebbero" comunque un luogo mai davvero toccato dal fenomeno. **Nota di
implementazione (non presente nel design originario)**: il codice reale oggi non ha ALCUN
concetto di `rejected` per un segnale fluttuante (`STATE_MACHINE.md` §4 — `blocked`/
`approved`/`rejected` restano design puro, non implementati da questo task) — ogni segnale
persistito dal percorso fidato (`submit_signal.py`) è trattato come implicitamente
approvato, quindi sull'asse `approved`/`rejected` OGNI segnale che scade deposita la sua
traccia incondizionatamente (`urban_memory.canale_fluttuante.sweep_and_fetch_active`). Il
principio "le rifiutate non fanno traccia" è quindi rispettato per COSTRUZIONE su
quell'asse (non esiste ancora un modo di rifiutare), non per un controllo esplicito nel
codice del deposito — quando la revisione umana verrà costruita, il deposito dovrà diventare
condizionato ANCHE da un vero stato `approved`, non più incondizionato su ogni `expired`.
**Aggiornamento — un SECONDO asse esiste ora, indipendente da `approved`/`rejected`**: un giro
DEDICATO di `ethics-guardian` ha verificato l'intera catena segnale→traccia→pattern→
promozione→consumo in itinerario e trovato che un segnale commerciale
(`non_commerciale=False`) poteva attraversarla indenne (il filtro "nessuno spazio è
acquistabile", `contracts.segnale_fluttuante_ammissibile`, era applicato SOLO nel consumo
diretto di `Signal.eventi_attivi`, mai nel percorso del ledger) — **chiuso**: lo stesso sweep
ora scarta anche i segnali non ammissibili PRIMA del deposito
(`if not segnale_fluttuante_ammissibile(segnale): continue`,
`urban_memory.canale_fluttuante.sweep_and_fetch_active`), riverificato indipendentemente da
un secondo giro di `ethics_guardian` ("GARANZIA ORA PRESERVATA"). I due assi restano
distinti e non vanno confusi: "approvato/rifiutato" (ancora vacuamente vero, sopra) e
"commercialmente ammissibile" (ora REALMENTE applicato, non più vacuo) sono due filtri
diversi sullo stesso deposito, non lo stesso controllo raccontato due volte.

## 2. La proprietà derivata sul grafo + il bagliore

Due meccanismi distinti — tenerli separati evita di confonderli in fase di implementazione.
**Stato epistemico diverso tra i due, come per gli invarianti del motore — non
confonderli**: (a) è REALE, (b) è REALE dal bagliore-nel-reason (consumatore: solo il
`reason` del motore, mai lo scoring).

### (a) `:Luogo.ultima_traccia_il` — proprietà derivata, un solo scopo — **REALE, implementato**

**Verificato contro il codice**: `services/urban-memory/cypher/40_luogo_traccia_write.cypher`
(un `MATCH`+`SET` puro, MAI un `MERGE` — confermato non crea mai un `:Luogo` inesistente,
verificato anche da un giro dedicato di `ethics-guardian`), `services/urban-memory/
urban_memory/luogo_traccia_link.py` (`Neo4jLuogoTracciaLinker`, stesso pattern di driver
diretto già usato da `graph_link.py`). Il design sotto è rispecchiato fedelmente dal codice.

Serve **esclusivamente** a rilevare la dormienza di un pattern promosso (§3, ANCORA DESIGN)
a costo di lettura zero: "quando ha parlato l'ultima volta questo luogo" senza mai
interrogare Postgres o traversare il grafo. **Nessun consumatore reale ancora** (§3 non è
implementata): la proprietà si aggiorna già ma nessuno la legge oggi per prendere una
decisione — scritta in anticipo per il momento in cui §3 verrà costruita, stesso principio
già visto per la label `:Evento` riservata ma vuota nello schema.

- **Si rinfresca in scrittura**, non in lettura: un `SET` sul nodo `:Luogo` nello stesso
  momento in cui la riga viene appesa al ledger. Due scritture in due store diversi, non una
  transazione distribuita — stessa natura di rischio già accettata altrove nel repo
  (`link_to_graph`/Postgres), non una garanzia nuova da inventare qui.
- Se una delle due scritture fallisce, il ledger (append-only, immortale) resta la fonte di
  verità; `ultima_traccia_il` è una proiezione best-effort, mai l'originale. Una divergenza
  temporanea si autocorregge alla prossima traccia depositata per lo stesso luogo — a
  differenza di `link_to_graph` (che verifica ESISTENZA e quindi richiede atomicità
  stretta), qui non c'è nulla da "esistere": un errore di sincronia produce al più un dato
  stantio, mai un dato invalido.

### (b) Il bagliore — MAI stored, calcolato in lettura — **REALE, implementato (solo nel `reason`)**

Non una proprietà sul grafo, non una colonna in Postgres. Calcolato al momento del bisogno
da chi lo consuma.

**Verificato contro il codice** (il disegno sotto è rispecchiato dal codice):
- **Fatti (BFF).** `api.main.create_itinerary` legge, PRIMA di `compose_itinerary`, le tracce
  dei luoghi di TUTTI i candidati con UNA lettura batch
  (`TracciaRepository.tracce_per_luoghi`, `WHERE place_id = ANY(...)`, indicizzata — EXPLAIN
  su Neon: Bitmap Index Scan) e le passa come ultimo parametro
  `tracce_per_luogo: dict[str, list[tuple[datetime, tuple[str, ...]]]]` (solo tipi base,
  nessun tipo nuovo nel contratto). Le tracce vengono solo dal ledger, mai dal body.
  Fail-closed: qualunque eccezione → `{}`, nessuna frase, itinerario invariato, mai un 500.
- **Decisione (motore, funzione pura in `experience_engine/rules.py`).** `peso_traccia(Δt) =
  PAVIMENTO_BAGLIORE + (1 − PAVIMENTO_BAGLIORE) · 0.5^(giorni / EMIVITA_BAGLIORE_GIORNI)`,
  `bagliore = Σ peso` (pavimento incluso, per consumatori futuri). La FRASE decide invece
  sulla sola parte decadente, `bagliore_recente = Σ (1 − PAVIMENTO_BAGLIORE) ·
  0.5^(giorni / EMIVITA_BAGLIORE_GIORNI)`: il pavimento, sommato su un ledger immortale,
  renderebbe "vivo" per sempre un luogo morto da anni. `tema_dominante` = tema con la parte
  decadente cumulata maggiore (spareggio alfabetico), `frase_bagliore` = None sotto
  `SOGLIA_BAGLIORE` (su `bagliore_recente`; una traccia da sola non basta mai). Costanti di
  partenza 0.05 / 30 giorni / 1.5, tuning differito. Una sola frase per luogo per itinerario;
  `adesso` arriva dall'orologio del server via BFF. Collocata nel motore perché è
  l'unico componente che decide e l'unico consumatore oggi; un secondo consumatore la
  sposterebbe in `packages/contracts`, mai una copia.
- **Dove entra.** SOLO nel `reason` delle tappe permanenti GIÀ scelte
  (`engine._costruisci_stops` → `_con_bagliore`): frase deterministica, aggiunta dal motore
  DOPO `reason_fn` (mai passata all'LLM) e PRIMA della disclosure partner, che resta l'ultima
  frase: «È un luogo che torna spesso a vivere di <tema>.» (senza articolo, valida per
  qualunque tema). Non tocca `calcola_score`/`passa_filtri_duri`, non aggiunge, toglie né
  riordina tappe (`docs/ENGINE_INVARIANTS.md` §3, test-guard AST).

**Cosa resta fuori:** nessuno scoring (il bagliore non ordina nulla); nessun cruscotto
`index-engineer`; nessuna frase sulle tappe fluttuanti, sulle tappe-evento promosso, né sulle
tappe sostituite da `adapt_itinerary` (che non legge il ledger); taratura delle costanti;
somma pesata in SQL (duplicherebbe la funzione pura). Limiti in `docs/LIMITI.md`, voci
"Il bagliore nel reason" e "La lettura batch del ledger cresce senza limite".

**Forma** (non i numeri — brief §4.1 lo chiede esplicitamente come forma):

```
bagliore(luogo, adesso) = Σ [ per ogni traccia di quel place_id ]  peso(adesso − traccia.creato_il)
```

dove `peso` è una funzione monotona decrescente del tempo trascorso **con un pavimento
positivo** — mai zero: ogni traccia contribuisce sempre un residuo non nullo, per quanto
vecchia. Forma illustrativa dello shape (non tuning):

```
peso(Δt) = pavimento + (1 − pavimento) · decadimento(Δt)
```

con `decadimento` una funzione tipo esponenziale o iperbolica — quale delle due, e i valori
di `pavimento`/tasso, sono domande di tuning (§4 sotto), stessa classe di `tasso_ritorno`.

**Perché sommare su TUTTE le tracce e non solo sull'ultima**: un luogo con dieci passaggi
recenti "brilla" più di uno con un solo passaggio, anche se entrambi hanno lo stesso
`ultima_traccia_il`. La doppia natura del ledger (diario + battito, brief §6) richiede due
letture diverse — l'ultimo istante (per la dormienza: binaria, parla ancora o no) e la somma
pesata (per il bagliore: continuo, quanto forte parla).

**"Costo zero" (brief §5) si riferisce al grafo** — nessuna traversata Neo4j per sapere
quanto un luogo è vivo — non a Postgres, dove il costo esiste ma è quello di
un'aggregazione a chiave indicizzata, esattamente il caso d'uso per cui Postgres è scelto.

## 3. La pipeline ricorrenza → promozione → dormienza

**REALTÀ vs DESIGN in questa sezione — non confonderli.** Un task successivo a questo
design ("rilevamento pattern ricorrenti + promozione :Evento + cestino") ha reso REALE il
rilevamento e la promozione — verificato contro il codice:

- **Reale**: `urban_memory.ricorrenza.rileva_candidati` (rilevamento: `place_id`+insieme di
  `temi` canonico, minimo `N_MINIMO_OCCORRENZE=3` occorrenze — vincolo DURO, mai
  configurabile sotto — e regolarità misurata come coefficiente di variazione degli
  intervalli, `TOLLERANZA_REGOLARITA=0.35`, scala-indipendente: la stessa soglia vale per un
  pattern settimanale e uno annuale); `urban_memory.promozione_evento.scrivi_evento_promosso`
  (scrive `:Evento` via `MATCH (:Luogo)` + `MERGE (:Evento)-[:SI_SVOLGE_A]->(:Luogo)`,
  `cypher/50_promozione_evento_write.cypher`); il comando CLI
  `python -m urban_memory.curatela_pattern` (percorso ristretto/fidato, stesso principio di
  `submit_signal.py`/`verify.py` — NESSUN endpoint HTTP pubblico). Il cestino permanente
  (`urban_memory.cestino_repository`, tabella `pattern_cestinato`,
  `sql/02_ricorrenza_schema.sql`) è la Strada per "occorrenze rifiutate non fanno pattern"
  di questa fase: si cestina il PATTERN, non la singola candidata, e resta cestinato per
  sempre (v1, deliberatamente permanente — vedi `docs/LIMITI.md`).
- **Deviazioni CONCRETE dal design originario sotto, da conoscere prima di leggerlo**:
  nessuna finestra temporale W libera (del rilevamento ricorrenza, non la finestra di consumo degli `:Evento`) (si usa tutta la storia disponibile del pattern, non
  una fetta scelta a mano — coerente con "non esiste un precedente per una W libera nel
  repo", verificato prima di implementare); `cadenza` è `cadenza_giorni: float` (la MEDIA
  degli intervalli in giorni), non un'etichetta categorica come "settimanale"/"annuale"
  suggerito più sotto in questa sezione; il nodo porta anche `promosso_da`/`promosso_il`
  (chi/quando della PRIMA promozione, mai sovrascritti) e, a una ripromozione,
  `ultimo_ricalcolo_da`/`ultimo_ricalcolo_il` (separati, mai confusi con l'originale) — non
  previsti nella bozza di proprietà sotto, aggiunti dopo un FAIL di `ethics-guardian` che
  aveva trovato l'accountability della promozione persa (solo loggata, mai persistita sul
  grafo). Un pattern il cui `:Evento` esiste già non è mai ripresentato come candidato
  (`evento_esistente`, stesso principio del cestino) — altro fix dello stesso giro.
- **Ora REALE anche la frizione automatica a cadenza** (`attivo ⇄ sospeso → dormiente`,
  `urban_memory.frizione_pattern`, `python -m urban_memory.frizione_pattern`) — verificato
  contro il codice, non presunto. Funzione pura `calcola_transizione`; lettura di tutti gli
  `:Evento {ricorrente: true}` (`cypher/60_eventi_ricorrenti_read.cypher`) e scrittura dello
  stato (`cypher/61_frizione_stato_write.cypher`, `MATCH`+`SET` puro, mai un `MERGE` — il
  nodo esiste già, creato solo alla promozione). **Due deviazioni dal design**, dettaglio
  completo in `docs/STATE_MACHINE.md` §4-bis(a): (1) il clock del pattern (ultima occorrenza)
  non è una proprietà sul nodo `:Evento` — si CALCOLA ogni volta dal ledger Postgres
  (`TracciaRepository.occorrenze_per_pattern`, nuovo metodo, filtrato per `place_id`+`temi`
  esatti), per non accoppiare l'hot path di `/itinerary` a un lookup sul grafo; (2)
  `sospeso → attivo` NON è istantaneo al deposito di una traccia fresca — avviene solo alla
  successiva corsa del comando (un pattern può restare `sospeso` più a lungo di quanto la
  cadenza indicherebbe se il comando non gira con regolarità — dichiarato, non nascosto,
  `docs/LIMITI.md`). Un giro DEDICATO di `ethics-guardian` (non un'autovalutazione) ha dato
  PASS con riserva: ha trovato un bug numerico reale nei valori di default iniziali
  (`K_BATTITI_SOSPENSIONE`/`ORIZZONTE_DORMIENZA_GIORNI` in tensione — un pattern annuale
  sarebbe stato dichiarato `dormiente` quasi subito dopo `sospeso`, vanificando lo scopo
  dichiarato di gestire la stagionalità), corretto rendendo l'orizzonte di dormienza
  proporzionale alla cadenza del singolo pattern (`max(pavimento assoluto, moltiplicatore ×
  cadenza_giorni)`), con test di regressione dedicato per cadenze lunghe.
- **Ora REALE anche il consumo**: un `:Evento {ricorrente: true, stato: 'attivo'}`, pertinente
  al profilo, compare come tappa in coda in un itinerario reale — stessa identica meccanica
  già in uso per i segnali fluttuanti (`_aggiungi_tappe_fluttuanti`), ramo gemello
  `experience_engine.engine._aggiungi_tappe_eventi_promossi`. Il BFF (`services/api/api/deps.
  get_evento_reader`, `main.create_itinerary`) legge dal grafo RIUSANDO
  `urban_memory.frizione_pattern.leggi_eventi_ricorrenti`/`Neo4jFrizioneClient` (nessuna nuova
  query Cypher), filtra in Python `stato == 'attivo'`, converte nel nuovo tipo condiviso
  `contracts.EventoPromosso` (`id, place_id, temi` — minimale, nessun `cadenza_giorni`/`stato`
  attraversa il confine verso il motore) e lo passa a `compose_itinerary` come nuovo parametro
  iniettabile, stesso principio di `score_fn`/`reason_fn`. **Precisazione, non una
  contraddizione col punto (1) sopra**: l'hot path di `/itinerary` ORA legge `:Evento.stato`
  (proprietà già scritta dalla promozione/frizione), ma non calcola né scrive MAI il clock
  del pattern — quella logica resta interamente nel batch `frizione_pattern`, invariata. Il
  `reason` di una tappa-evento era scritto deliberatamente come CONTESTO SUL LUOGO
  (`"{place_nome} ha un carattere legato a {temi}: un tratto ricorrente del luogo, non un
  appuntamento di oggi."`), mai un appuntamento — quella v1 non verificava se la cadenza
  combaciasse col giorno di visita, quindi un `:Evento` poteva comparire in un giorno diverso
  da quello dell'occorrenza reale e il racconto non doveva promettere una presenza fisica.
  **SUPERATO dalla finestra temporale** (punto "Ora REALE anche la finestra temporale" sotto):
  il `reason` è ora un appuntamento ATTESO, mai confermato. Un giro DEDICATO di
  `ethics-guardian` ha dato FAIL iniziale (non un'autovalutazione) — non sull'implementazione
  tecnica (score/budget/sicurezza/onestà del reason tutti verificati PASS), ma su una frase
  ormai falsa lasciata in `docs/LIMITI.md` ("nessuna riga di frizione_pattern è raggiungibile
  da `/itinerary`") e sull'assenza di una dichiarazione esplicita che il consumo rende ora
  concretamente raggiungibile un varco preesistente (un pattern commerciale può diventare un
  `:Evento` promosso senza che nessun controllo lo intercetti, perché il carattere commerciale
  non sopravvive al deposito nel ledger) — **PASS** dopo l'aggiornamento di `docs/LIMITI.md`.
  **Il varco stesso, non solo la sua dichiarazione, è stato poi chiuso in un secondo giro,
  su richiesta esplicita del committente**: un terzo giro DEDICATO di `ethics-guardian` ha
  risalito l'intera catena (`submit_signal.py` → `canale_fluttuante.py` →
  `traccia_repository.py` → `ricorrenza.py` → `curatela_pattern.py` → `promozione_evento.py`
  → `eventi_promossi_pertinenti`) e confermato "GARANZIA NON PRESERVATA": un segnale
  commerciale attraversava indenne ogni passaggio, perché nessuno di essi rifiltrava
  `non_commerciale` (l'informazione stessa si perde già al deposito della `Traccia`, che non
  porta quel campo). Fix applicato alla RADICE, in `urban_memory.canale_fluttuante.
  sweep_and_fetch_active`: un segnale non ammissibile (`contracts.
  segnale_fluttuante_ammissibile`, la STESSA funzione già usata per il consumo diretto dei
  fluttuanti, nessuna seconda logica inventata) non deposita più alcuna `Traccia` né aggiorna
  `:Luogo.ultima_traccia_il` — resta comunque persistito e correttamente `expired` per audit
  (`submit_signal.py` invariato). Un quarto giro, ancora indipendente, ha riverificato punto
  per punto (ordine del controllo, non-alterazione della transizione `expired`,
  non-interferenza con la persistenza grezza, assenza di un secondo scrittore del ledger che
  bypassi il filtro) e confermato **"GARANZIA ORA PRESERVATA"** — fino al limite noto e già
  accettato dell'auto-dichiarazione mentita di `non_commerciale` (un segnale può sempre
  mentire su sé stesso; nessun filtro a valle può correggerlo), invariato e non oggetto di
  questo fix. Dettaglio completo in `docs/LIMITI.md`, voce estesa su
  `SegnaleFluttuante.non_commerciale`.
- **Ora REALE anche la finestra temporale** (v1 della finestra, sostituisce "compare in
  qualunque giorno"). Il FATTO e la DECISIONE stanno in due posti distinti:
  - **Fatto, nel BFF** (`services/api/api/main.create_itinerary`): per ogni `:Evento`
    `attivo` e non frenato legge le occorrenze dal ledger
    (`TracciaRepository.occorrenze_per_pattern`, una query per evento — batch come
    ottimizzazione futura, `docs/LIMITI.md`), ne prende il massimo (UTC) e lo converte nella
    DATA LOCALE della città con `CITY_TZ` dal `.env` (mai scritto nel codice). Passa
    `EventoPromosso.ultima_occorrenza` e `cadenza_giorni` — mai una "prossima occorrenza"
    già calcolata. Precisazione al punto (1) sopra: l'hot path di `/itinerary` ORA legge
    anche il ledger, in sola lettura; il clock della FRIZIONE (battiti mancati, `stato`)
    resta interamente nel batch `frizione_pattern`.
  - **Decisione, solo nell'Experience Engine** (`experience_engine.rules.
    occorrenza_attesa_giorni`/`evento_in_finestra`, funzioni pure, chiamate da
    `eventi_promossi_pertinenti`): tra le occorrenze `ultima_occorrenza + k·cadenza_giorni`
    con k ≥ 1 intero sceglie la più vicina alla data della visita; in finestra se lo scarto è
    `<= FRAZIONE_FINESTRA_CADENZA × cadenza_giorni` (0.15, valore di PARTENZA, tuning
    differito — stesso principio di `K_ORIZZONTE_DORMIENZA`), bordo incluso. La finestra
    decide solo "quando"; "se è vivo" resta a `stato`.
  - **Fail-closed, mai una data inventata**: `Signal.data` assente, `CITY_TZ` assente o non
    valido, nessuna occorrenza nel ledger, `cadenza_giorni` non positiva o non finita
    (inf/nan), proiezione non rappresentabile → l'evento non
    compare. `data` e `giorno_settimana` incoerenti → 422 (validatore del contratto).
  - **Invariato**: in coda, mai in sostituzione, `DURATA_TAPPA_EVENTO_MIN`, costo a budget,
    solo `attivo`, frenati esclusi; `calcola_score` e `passa_filtri_duri` non toccati.
  - **`reason`**: ora un appuntamento ATTESO e dichiarato come stima ("la prossima
    occorrenza è attesa domani… è una stima dalla regolarità osservata, non un appuntamento
    confermato, e non ne conosciamo l'orario"). Solo per eventi in finestra.
  - **App**: `Signal.data` compilata dall'app Flutter dallo stesso orologio di `ora`
    (`Signal.orologio`), NON verificata a compilazione (`flutter` assente — `docs/LIMITI.md`).
  - **Limiti** (tracce storiche timbrate allo sweep pigro e quindi sfasate in avanti — le
    nuove sono timbrate a `valido_fino`, §1 —, cadenze quasi
    quotidiane sempre in finestra, finestra simmetrica "era attesa ieri", fuso del
    dispositivo): `docs/LIMITI.md`, voce "La finestra temporale degli `:Evento` promossi".
  - Verifica: giro DEDICATO di `ethics-guardian`, due passaggi. **FAIL iniziale** solo sulla
    documentazione di audit (questo file e `docs/LIMITI.md` dicevano ancora "nessuna
    finestra"; docstring di `EventoPromosso` impreciso sul timbro), codice già PASS; nello
    stesso giro trovati e corretti un `OverflowError` provocabile dal client con date estreme
    (500 → fail-closed, `rules.proiezione_occorrenza_attesa`) e una cadenza `inf` accettata
    dal contratto (ora `allow_inf_nan=False`; il BFF salta il singolo evento). **PASS** al
    secondo giro, indipendente: la finestra non apre un vettore commerciale — è un filtro in
    più, mai un input di score, e restringe l'esposizione della v1 (che era "sempre"),
    non la allarga.
- **Ledger delle promozioni e ripristino del grafo** (`sql/04_promozione_schema.sql`, tabella
  `pattern_promosso`, append-only, senza UNIQUE; `urban_memory.promozione_repository`).
  Aura Free è stata cancellata per inattività e la decisione di promozione viveva solo nel
  grafo: ora **Postgres è la fonte di verità, il grafo la proiezione**. Ordine in
  `curatela_pattern.promuovi_pattern`: (1) lettura `luogo_esiste` (luogo mancante o grafo
  irraggiungibile: NULLA scritto, il pattern resta candidato); (2) riga nel ledger; (3)
  proiezione sul grafo. Se (3) fallisce la promozione RESTA registrata
  (`ProiezioneGrafoPendenteError`, messaggio "REGISTRATA, NON ANCORA SUL GRAFO": non va
  ripetuta, i pattern già nel ledger sono esclusi dal rilevamento). Ripristino:
  `python -m graph.loader` poi `python -m urban_memory.ripristina_eventi`
  (idempotente; riga PRIMA per `promosso_da/_il` con `coalesce`, mai sovrascritti su un nodo
  esistente; riga PIÙ RECENTE per cadenza/ricalcolo, `cypher/51_ripristino_evento_write.cypher`).
  FAIL-CLOSED: `e.frenato` (ultima azione di `pattern_frenato`; a parità ESATTA di `quando` vince `tirato`, in Postgres e in-memory) è scritto NELLA STESSA query
  del nodo e tutte le letture (ledger, freno, cestino) precedono ogni scrittura; un pattern nel
  cestino E nel ledger NON è proiettato (conflitto, exit 1; `promuovi_pattern` lo rifiuta già
  prima di scrivere). `e.stato` NON è ripristinato: i nuovi eventi partono `sospeso` (non
  raccomandabili, `/itinerary` consuma solo `attivo`) e il passo OBBLIGATORIO successivo
  `python -m urban_memory.frizione_pattern` fa `sospeso -> attivo`. Limite: le promozioni anteriori
  al ledger non vi sono registrate e non sono recuperabili.
- **Ora REALE anche il freno di emergenza** (v1 minima — `urban_memory.freno_pattern`, `python
  -m urban_memory.freno_pattern tira|rilascia`): proprietà separata `e.frenato` sul nodo
  `:Evento` (mai `e.stato`), tabella Postgres `pattern_frenato` (append-only, senza UNIQUE),
  motivazione obbligatoria su ogni tiro validata prima di ogni scrittura. Il filtro di consumo
  in `POST /itinerary` è ora `stato == 'attivo' and not frenato` — lettura pura, nessuna
  scrittura raggiungibile dal path caldo. Verificato da un giro DEDICATO di `ethics-guardian`
  (FAIL iniziale su `attore` non validato → un `:Evento` frenato poteva restare senza riga di
  audit → corretto → PASS). Dettaglio completo in `docs/STATE_MACHINE.md` §4-bis(b). **Resta
  design puro**: la lista nominale dei permessi-freno e il grant/revoke (§7.14.1) — v1
  deliberatamente su percorso fidato/CLI, come `curatela_pattern.py`/`frizione_pattern.py`.
- **Resta design
  puro**: la corsia di revisione umana `blocked`/`approved`/
  `rejected` dei singoli SEGNALI fluttuanti (`STATE_MACHINE.md` §4) — quella distinta dalla
  revisione del PATTERN qui sopra: ogni segnale che arriva dal canale fluttuante persistente
  è trattato come implicitamente approvato (nessun `rejected` esiste ancora per il singolo
  segnale), quindi il ledger su cui `rileva_candidati` legge non distingue oggi segnali
  "genuinamente approvati da un Guardiano" da "mai rivisti da nessuno" — stesso limite già
  dichiarato in `STATE_MACHINE.md` §4.
- **Limite noto non chiuso da questo task**: la transizione automatica "occorrenze →
  ricorrente" (system-detected, un pattern supera la soglia N+tolleranza) NON produce un
  record d'audit persistente distinto dalla decisione del Promotore — `rileva_candidati` è
  una funzione pura, senza log applicativo del "sistema ha rilevato questo pattern come
  ricorrente in base a queste occorrenze". Solo le due transizioni UMANE successive
  (`candidato → promosso`, `candidato → cestinato`) sono loggate (`chi=Promotore, quando,
  pattern, cadenza/motivo` — `curatela_pattern.py`). Questo diverge dal principio
  `STATE_MACHINE.md` §5/§1.4 originario ("anche se system-detected, la transizione va
  comunque registrata... rilevamento ricorrenza" è l'esempio letterale usato lì) — non
  bloccante (il rilevamento è ricalcolato ad ogni corsa della CLI, non uno stato perso: la
  stessa candidatura ricompare identica finché non viene decisa), ma dichiarato qui invece
  di lasciato implicito, coerente con la disciplina del resto di questo file. Vedi
  `docs/LIMITI.md` per il dettaglio.

**Rilevamento ricorrenza** (design originario, sotto — la Strada REALE sopra lo rispetta
nella sostanza, con le deviazioni dichiarate): sorgente = occorrenze APPROVATE (mai
rifiutate, brief §6) di stessa descrizione/temi/place_id entro una finestra — meccanismo già
descritto in `STATE_MACHINE.md` §4 ("Ricorrenza → promozione"), non riscritto qui. Soglia N e
finestra W: **N ha ora un valore reale nel codice** (`N_MINIMO_OCCORRENZE=3`, pavimento duro,
tuning verso l'alto — vedi sopra); **W non esiste ancora** e non è stata introdotta
(deliberato, vedi sopra) — resta non decisa nel senso più forte: non richiesta da questo
design.

**Nodo promosso: famiglia `:Evento`** (chiude la domanda 11 di `STATE_MACHINE.md` §7,
check §3.4 del brief) — la label esiste già, riservata da `00_schema.cypher` con un
constraint di unicità su `id`, ma zero nodi, zero proprietà, zero seed. Ancorato al `:Luogo`
esistente tramite una relazione, **non** un nuovo `:Luogo` (la piazza è già un luogo; la
musica ricorrente che vi accade non lo è).

Proprietà proposte (design, non Cypher eseguibile) — **riviste dalla chiusura di
`docs/STATE_MACHINE.md` §4-bis** (item 14 §7, brief §7.2): il modello di dormienza qui sotto
era "invecchiamento assoluto di `ultima_traccia_il`"; è stato sostituito dalla **frizione
automatica a cadenza**, e si è aggiunto un **freno di emergenza** ortogonale, non uno stato.
Dettaglio completo in `docs/STATE_MACHINE.md` §4-bis, non ripetuto qui:

- `ricorrente = true` — costante per un `:Evento` di questa famiglia.
- `cadenza` — il ritmo delle occorrenze che hanno fatto rilevare il pattern come ricorrente
  (es. "ogni sabato"), salvato al momento della promozione. **Campo nuovo, non ancora
  verificato contro il codice**: se il rilevamento ricorrenza (§3 sotto) produce solo un
  conteggio grezzo e non un ritmo, questo campo va popolato esplicitamente alla promozione,
  non dedotto a posteriori — non verificabile oggi perché il rilevamento ricorrenza non
  esiste ancora (`docs/FASE3_VERIFICHE.md`, check 1).
- `stato ∈ {attivo, sospeso, dormiente}` — **non più `ritirato`**: mortale ma
  standing-until-revoked, mai una DELETE (invariante A, brief §2: append-only sui target di
  `riguarda` — un `:Evento` promosso, una volta creato, non sparisce mai, si spegne).
  Transizioni automatiche, sensibili al RITMO (`cadenza`), non al tempo assoluto:
  `attivo → sospeso` dopo K battiti di cadenza mancati; `sospeso → attivo` automatico su
  traccia fresca; `sospeso → dormiente` se la sospensione supera un orizzonte lungo. Gestisce
  nativamente la stagionalità (un pattern annuale vive `sospeso` undici mesi l'anno, mai
  dichiarato morto). K, orizzonte e tolleranza sul ritmo: tuning, non decisi qui
  (`docs/STATE_MACHINE.md` §7 item 12/15).
- `ultima_traccia_il` — stessa proprietà derivata di §2(a), applicata al `place_id`
  d'origine: alimenta la frizione (a) sopra, non più un invecchiamento assoluto isolato.
- **Freno di emergenza — NON una proprietà di `stato`.** Override di sicurezza manuale,
  ortogonale al ciclo di vita sopra, applicabile in qualunque momento indipendentemente da
  `attivo`/`sospeso`/`dormiente`: sopprime la raccomandazione (mai il deposito delle tracce,
  il ledger resta veritiero), tiro e rilascio entrambi manuali (non si auto-rilascia su
  traccia fresca), append-only (ogni tiro/rilascio una riga permanente, motivazione
  obbligatoria, log a salienza massima). Al rilascio il pattern torna allo stato che la
  frizione (a) indica in quel momento, mai forzato ad `attivo`. Livello di autorità:
  **CHIUSO nel principio** — permesso individuale nominale, ristretto a un sottoinsieme di
  Promotori, mai l'intero ruolo; concessione/revoca del permesso stesso tracciata e
  reversibile (append-only), nessun doppio-occhio sul singolo tiro (restrizione
  sull'accesso, non sulla procedura). Residuo di dettaglio implementativo (chi amministra la
  lista) — `docs/STATE_MACHINE.md` §7.14.1, item 16. Dettaglio completo:
  `docs/STATE_MACHINE.md` §4-bis(b).

**Relazione di ancoraggio: `SI_SVOLGE_A` — CHIUSO contro il codice, non una proposta.**
Verificato l'intero `services/graph/cypher/01_seed_lucca.cypher`: nel seed esistono
esattamente sette tipi di relazione — `LEGATO_A` (7), `VICINO` (3), `OFFRE` (5),
`SI_SVOLGE_A` (22), `EVOCA` (65), `ISPIRATA_DA` (non ancora contata sopra ma presente),
`HA_ABBONAMENTO` (3). Di queste, una sola porta la semantica "questo accade/si trova qui":
`SI_SVOLGE_A` (`:Esperienza -[:SI_SVOLGE_A]-> :Luogo`, derivata da `ExperienceNode.place_id`
in `seed_lucca.py`). Le altre due candidate sono ESCLUSE per motivo esplicito nel codice, non
per assunzione:
- `LEGATO_A` (Artista→Luogo) è **riservata per iscritto** a un'altra semantica — il commento
  di `RelazioneIspirataDa` in `seed_lucca.py:157-159` lo dice testualmente: *"non `LEGATO_A`
  che è riservato ad Artista->Luogo"* — un legame biografico/artistico, non un ancoraggio
  spaziale generico. Riusarlo per `:Evento` confonderebbe due fatti diversi sotto lo stesso
  verbo.
- `Bottega.place_id` **non produce nemmeno una relazione**: è un campo validato per
  esistenza (`assert bottega.place_id in luoghi_ids`) ma mai materializzato come arco nel
  grafo — non è un precedente di "ancoraggio", è un caso a parte (una bottega non ha bisogno
  di un arco per essere trovata per luogo, la query dei candidati passa da `place_id` come
  proprietà, non da una traversata).

`:Evento` è, nella forma, la stessa cosa di `:Esperienza`: un'attività che accade a un
`:Luogo` che esiste già, non il luogo stesso. Riusare `SI_SVOLGE_A` non è un'analogia
comoda: è la stessa relazione applicata alla stessa forma di fatto — un solo modo di
intendere "accade qui" (CLAUDE.md, "un solo modo di intendere"), non un verbo parallelo
introdotto per l'occasione. Nessuna nuova decisione di `graph-architect` da prendere su
QUALE relazione usare — resta solo l'implementazione (fuori scope qui, design non tocca
Cypher).

**Dormienza — automatica, da FRIZIONE A CADENZA, CHIUSA** (brief §6, chiusura in
`docs/STATE_MACHINE.md` §4-bis(a) — sostituisce questo paragrafo nella sua forma originaria
"invecchiamento assoluto di `ultima_traccia_il`"): l'`:Evento` promosso porta con sé la
propria `cadenza` (il ritmo delle occorrenze rilevate come ricorrenti), salvata alla
promozione. `attivo → sospeso` dopo **K battiti di cadenza mancati** (non un tempo assoluto);
`sospeso → attivo` automatico su una traccia fresca; `sospeso → dormiente` se la sospensione
supera un orizzonte lungo. Nessuna sveglia separata, nessun job che "controlla se è morto":
la cadenza mancata stessa — letta al bisogno o da un batch periodico, dettaglio
implementativo non deciso qui — È il segnale, come nel modello originario; cambia solo COSA
si misura (battiti di ritmo, non giorni). Ogni transizione loggata (brief §1.4: anche
l'automatico logga chi/quando/perché — chi=sistema, perché="K battiti mancati" /
"sospensione oltre orizzonte"). **Perché il cambio rispetto al modello originario**: un
tempo assoluto tratterebbe un pattern stagionale (es. un mercatino annuale, undici mesi di
silenzio ogni anno per costruzione) come morto ogni anno — la cadenza lo riconosce invece
come "in pausa attesa", non "cessato". Dettaglio completo, coi tre stati e i numeri non
decisi (K, orizzonte, tolleranza): `docs/STATE_MACHINE.md` §4-bis(a).

**Retroattività: si dissolve** (brief §6, confermato dal check §3.2) — le occorrenze
approvate non persistono come nodi (spariscono a `expired`, lasciando solo una traccia
anonima nel ledger). Non c'è nulla sotto il pattern promosso da riscrivere. Ciò che resta
della "storia" che ha portato alla promozione è **provenance**, non topologia: quali righe
del ledger (place_id + temi + intervallo di `creato_il`) hanno determinato la rilevazione di
ricorrenza — un fatto di audit (loggabile nella transizione `ricorrente`, già previsto da
`STATE_MACHINE.md` §4: "quali occorrenze l'hanno determinata"), mai un arco nel grafo verso
occorrenze che non esistono più come nodi.

**Ritiro manuale — CHIUSA nel principio, REALE nella v1 minima** (brief §7.2, `docs/
STATE_MACHINE.md` §4-bis(b)): non un "ritiro" che sposta il pattern in un nuovo stato
terminale (bozza abbandonata), ma un **freno di emergenza** — override di sicurezza,
ortogonale alla frizione sopra, non una voce di `stato`. Tiro e rilascio entrambi manuali (non
si auto-rilascia su traccia fresca, a differenza della frizione), immediato, sopprime solo la
raccomandazione (il ledger continua a ricevere tracce normalmente — verificato con un test
comportamentale dedicato, non solo per assunzione), append-only con motivazione obbligatoria e
log a salienza massima. Al rilascio il pattern torna allo stato che la frizione indica in quel
momento, mai forzato ad `attivo` — conseguenza gratuita dell'ortogonalità (`frenato` non tocca
mai `stato`), non una logica di ripristino da mantenere. **REALE**: `urban_memory.
freno_pattern` (comando `python -m urban_memory.freno_pattern tira|rilascia`), proprietà
`e.frenato` sul nodo `:Evento` (`cypher/62_freno_stato_write.cypher`), tabella Postgres
`pattern_frenato` (append-only, senza UNIQUE — il freno è ripetibile). Motivazione validata
PRIMA di ogni scrittura — un giro dedicato di `ethics-guardian` aveva trovato che la stessa
guardia mancava per `attore` (un `:Evento` frenato con `attore` vuoto poteva restare senza
riga di audit, perché la scrittura sul grafo precede quella sulla tabella), corretto e
riverificato PASS. Scoped a motivi di sicurezza/legale/immediatezza: usarlo perché "il
pattern è finito" è un uso improprio, quello è compito della frizione — questo resta un
vincolo d'uso, non tecnico, non enforced dal codice. **Livello di
autorità: CHIUSO nel principio, ma NON ANCORA REALE** (`docs/STATE_MACHINE.md` §7.14.1, item
16) — permesso individuale nominale concesso a un sottoinsieme ristretto di Promotori, mai
l'intero ruolo, con concessione/revoca tracciata e reversibile e nessun doppio-occhio sul
singolo tiro: questo resta design puro. La v1 implementata usa invece un percorso
fidato/CLI provvisorio (chi ha accesso alla shell è, per costruzione, fidato — stessa postura
di `curatela_pattern.py`/`frizione_pattern.py`), deliberatamente, non per omissione. Resta
solo un residuo di dettaglio implementativo (chi amministra concretamente la lista dei
permessi), stessa classe di tuning di K/orizzonte/tolleranza sopra — non una decisione di
governance ancora da prendere.

## 4. Integrazione nella macchina a stati — riga esplicita, non bullonata

Fatto in `docs/STATE_MACHINE.md` §4 direttamente (non ripetuto qui): il diagramma della
corsia fluttuanti ora mostra `expired` come terminale **con effetto collaterale
condizionato**, non più "nessuna scrittura" come accettato in Fase 2:

- occorrenza **mai approvata** (mai decisa, o rifiutata) che raggiunge `expired` → nessuna
  scrittura, esattamente come prima.
- occorrenza **approvata** che raggiunge `expired` (la sua finestra si chiude comunque, con
  lo stesso orologio) → deposita una riga nel ledger (§1), timbrata con il `valido_fino`
  del segnale (valore calcolato dal server in `submit_signal`) (non con l'istante, più tardo, dello sweep pigro — §1).

La transizione di stato (loggata per accountability, brief §1.4: chi=sistema, quando,
perché) e la riga del ledger (anonima, senza contributor, brief §5) sono **due record
distinti con due scopi distinti** — non confonderli: uno è audit della macchina a stati,
l'altro è il diario del luogo. `STATE_MACHINE.md` §6 li tiene ora come due righe separate
nella tabella dei due assi di autorità.

## 5. Domande ancora aperte — sollevate, non risolte

Tenute anche in `docs/STATE_MACHINE.md` §7 (items 12, 15 aperti; 14 e 16 CHIUSE nel
principio, con solo un residuo di tuning/dettaglio implementativo) per restare in un solo
posto consultabile insieme alle altre domande della macchina a stati:

1. ~~**Soglia N e finestra W** per il rilevamento della ricorrenza.~~ **PARZIALMENTE
   CHIUSA nel codice** (non nel principio di tuning): `N_MINIMO_OCCORRENZE=3` (pavimento
   duro, mai sotto) e `TOLLERANZA_REGOLARITA=0.35` (coefficiente di variazione) sono valori
   di PARTENZA reali in `urban_memory.ricorrenza`, dichiarati esplicitamente come tuning da
   calibrare sui dati del pilota — stessa classe di `tasso_ritorno`, non definitivi. **W non
   esiste**: sostituita per design da "tutta la storia disponibile del pattern" (nessuna
   finestra libera introdotta, coerente con l'assenza di un precedente nel repo, verificata
   prima di implementare — vedi §3 sopra).
2. ~~**Override manuale del ritiro pattern**~~ **CHIUSA** (`docs/STATE_MACHINE.md` §4-bis):
   non un override generico, ma due meccanismi distinti — frizione automatica a cadenza
   (§3 sopra) e freno di emergenza (§3 sopra).
2-bis. ~~**§7.14.1 — livello di autorità del freno di emergenza**: intero ruolo Promotore o
   sottoinsieme ristretto?~~ **CHIUSA nel principio** — permesso individuale nominale,
   ristretto, mai l'intero ruolo, concessione/revoca tracciata e reversibile, nessun
   doppio-occhio sul tiro (stessa domanda di `docs/STATE_MACHINE.md` §7 item 16, non
   duplicata in due forme diverse). Il residuo (chi amministra la lista) è dettaglio
   implementativo, ripiegato nel tuning dell'item 3 sotto — non una domanda di design a sé.
3. **Forma della curva di decadimento (bagliore, §2b) — REALE, i numeri no**: decadimento
   esponenziale con pavimento, valori di PARTENZA nel codice (`PAVIMENTO_BAGLIORE=0.05`,
   `EMIVITA_BAGLIORE_GIORNI=30.0`, `SOGLIA_BAGLIORE=1.5`, sulla sola parte decadente, in `experience_engine.rules`), da
   calibrare sul pilota, non definitivi.
   **La frizione a cadenza (§3, §4-bis(a) di `docs/STATE_MACHINE.md`) è invece PARZIALMENTE
   CHIUSA nel codice** (stessa classe della soglia N/tolleranza dell'item 1): K battiti
   mancati per sospendere (`K_BATTITI_SOSPENSIONE=2`), l'orizzonte assoluto di dormienza
   (`ORIZZONTE_DORMIENZA_GIORNI=180.0`) e il suo moltiplicatore di cadenza
   (`K_ORIZZONTE_DORMIENZA=3.0`, aggiunto per correggere un bug reale trovato da
   `ethics-guardian` — un orizzonte fisso indipendente dalla cadenza avrebbe vanificato la
   gestione della stagionalità per i pattern a cadenza lunga) sono valori di PARTENZA reali
   in `urban_memory.frizione_pattern`, dichiarati esplicitamente tuning da calibrare sul
   pilota, non definitivi. La **tolleranza sul ritmo** (quanto una cadenza può slittare
   prima di contare come "mancata") resta invece NON implementata — nessun parametro
   equivalente esiste in `calcola_transizione`. Resta aperto anche chi amministra la lista
   dei permessi-freno (§7.14.1) — dettaglio implementativo, non struttura.
4. ~~**Collocazione del codice del ledger**: `services/urban-memory` o un servizio nuovo
   dedicato?~~ **CHIUSA** — `services/urban-memory` (§1 sopra), decisione presa
   dall'orchestratore al momento dell'implementazione, non da questo documento di design.
5. **Chi consuma il bagliore** (§2b): **PARZIALMENTE CHIUSA** — `experience-engine`, SOLO
   per il `reason` di tappe già scelte, mai per lo scoring (`ENGINE_INVARIANTS.md` §3:
   «`calcola_score` non legge mai il bagliore», con test-guard AST). Restano aperti un
   cruscotto `index-engineer` e un eventuale uso nello scoring: quest'ultimo richiederebbe di
   riaprire esplicitamente §3, non è un'estensione naturale.
6. **Finestra temporale degli `:Evento` promossi — REALE, i numeri no**:
   `FRAZIONE_FINESTRA_CADENZA=0.15` è un valore di PARTENZA (stessa classe di
   `K_ORIZZONTE_DORMIENZA`), da calibrare sul pilota. Aperte, non decise: finestra simmetrica
   o asimmetrica (oggi un'occorrenza "attesa ieri" produce ancora una tappa); un pavimento di
   cadenza per i pattern quasi quotidiani (oggi sempre in finestra). Il timbro del ledger è
   stato CORRETTO (`valido_fino` invece dell'istante dello sweep, §1); restano sfasate le
   tracce storiche. Dettaglio: `docs/LIMITI.md`.

## 6. Scenario concreto — una giornata, un ciclo di vita

Non tassonomia astratta (disciplina brief §8): un violinista suona in Piazza Napoleone ogni
sabato sera per sei settimane di fila.

1. **Sabato 1**: qualcuno segnala il fluttuante (canale di sottomissione ancora non
   esistente, `docs/LIMITI.md` — assunto qui che arrivi già com'è). Un Guardiano lo approva
   (`submitted → approved`). Il motore lo usa per comporre itinerari quella sera. A
   mezzanotte la finestra scade: **era approvato** → `expired` deposita una traccia
   `(place_id=piazza-napoleone, temi=[musica-di-strada], creato_il=sabato 1, 00:00)`.
   `:Luogo(piazza-napoleone).ultima_traccia_il` si aggiorna allo stesso istante.
2. **Sabati 2-6**: stesso ciclo, cinque tracce in più — stesso `place_id`, stessi `temi`,
   `creato_il` diversi. Nessun nodo nuovo nel grafo: sei occorrenze, sei righe di ledger,
   zero topologia aggiuntiva.
3. **Rilevamento ricorrenza** (soglia N/finestra W, non decise qui): sei occorrenze
   approvate, stesso pattern, entro sei settimane → `ricorrente`, loggata (chi=sistema,
   quali occorrenze — o quali tracce — l'hanno determinata).
4. **Promozione**: un Promotore la promuove. Nasce
   `(:Evento {id, ricorrente=true, stato=attivo, cadenza=settimanale})-[:SI_SVOLGE_A]->
   (:Luogo{id=piazza-napoleone})` — la `cadenza` (settimanale) è salvata qui, alla
   promozione (`docs/STATE_MACHINE.md` §4-bis(a)). Nessuna occorrenza passata viene
   riscritta: restano solo le sei righe di ledger e la transizione `ricorrente` come
   provenance.
5. **Le settimane successive**: il violinista continua. Ogni sabato scaduto approvato
   deposita una nuova traccia; `ultima_traccia_il` di Piazza Napoleone resta fresca; il
   bagliore calcolato in lettura resta alto (molte tracce recenti pesano molto).
6. **Il violinista smette gradualmente** (semplicemente si stanca). Il sabato 8 non si
   presenta: un battito di cadenza mancato. Se salta anche il sabato 9 (K=2, per fissare
   un'idea — non deciso davvero, §5 item 3), `:Evento(piazza-napoleone-violinista).stato:
   attivo → sospeso`, automatico, loggato (`docs/STATE_MACHINE.md` §4-bis(a)) — non ancora
   `dormiente`: la frizione a cadenza non tratta due sabati saltati come morte del pattern.
   Se il violinista tornasse un sabato successivo, `sospeso → attivo` automatico, nessun
   intervento del curatore. Ma non torna: la sospensione supera l'orizzonte lungo (non
   deciso) → `sospeso → dormiente`, automatico, loggato. Il nodo resta nel grafo — non è mai
   stato cancellato, solo spento. Il bagliore calcolato in lettura, nel frattempo, è
   scivolato verso il pavimento (mai zero): le vecchie tracce sbiadiscono, non si
   seppelliscono — il luogo "ricorda debolmente" anche molto tempo dopo che il fenomeno è
   tornato silenzioso. Quel ricordo vive SOLO in `bagliore()` (consumatori futuri): la frase
   nel `reason` decide sulla sola parte decadente, quindi si spegne man mano che le ultime
   tracce decadono (emivita 30 giorni): con N passaggi dopo l'ultimo sabato la frase resta
   accesa per circa 30·log2(0.95·N/1.5) giorni (N=10 ~80, N=40 ~140), poi tace per sempre.
7. **Variante — il Comune vieta i busker con effetto immediato, sabato 4** (invece del
   ritiro graduale sopra): il pattern è ancora `attivo` (nessun battito mancato), ma un
   Promotore con **permesso-freno** (uno dei pochi della lista nominale, non l'intero ruolo)
   tira il **freno di emergenza** (`docs/STATE_MACHINE.md`
   §4-bis(b)) — immediato, motivazione obbligatoria ("ordinanza comunale n. …, busker
   vietati da oggi"), loggato a salienza massima. Il motore smette di raccomandare la tappa
   fluttuante da quel momento. Se qualcuno segnalasse comunque un'occorrenza sabato 5 e un
   Guardiano (per errore, o perché non a conoscenza del freno) la approvasse, la sua traccia
   si depositerebbe comunque a `expired` — il ledger resta veritorio, il freno non lo tocca.
   Il freno resta tirato finché qualcuno non lo rilascia esplicitamente: non si spegne da
   solo neanche se passano mesi di silenzio. Al rilascio, il pattern non torna `attivo` per
   default — torna a ciò che la frizione (a) indica in quel momento: se nel frattempo sono
   mancati abbastanza battiti da giustificare `sospeso`, è `sospeso` che riemerge.

## 8. Cosa questo documento NON è

Non è uno schema SQL (`packages/contracts`/`services/*/sql` restano gli unici posti dove uno
schema è reale), non è Cypher, non è un endpoint HTTP, non è una modifica ai contratti
esistenti (`SegnaleFluttuante`/`Signal` restano esattamente come sono — Strada B lo impone
esplicitamente). Prima di implementare qualunque pezzo: `contract-keeper` per la forma dati
del ledger (se emerge un contratto condiviso), `graph-architect` per la relazione di
ancoraggio e le proprietà di `:Evento`, `ethics-guardian` prima di ogni merge che tocchi
scoring/reason se e quando il bagliore entra in `experience-engine`, `test-engineer` per il
ciclo di vita sopra come test di integrazione — nessuna eccezione rispetto a ogni altra wave
di questo repository.
