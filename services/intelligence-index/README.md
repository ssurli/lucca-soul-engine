# Lucca Soul — Urban Intelligence Index (`services/intelligence-index`)

Wave 4: gli **indicatori**. Se il sistema orienta le decisioni di una città, deve rendere conto dei
propri effetti con indicatori propri. Questo servizio calcola `contracts.UrbanIntelligenceIndex`
per un periodo (`"YYYY-MM"`, es. `"2026-07"`) a partire da `BehaviorEvent` (già persistiti da
`recommender`), dal grafo (`grado semantico`, snapshot `VICINO` — `services/graph`) e da Urban
Memory (TUTTI i contributi del periodo, indipendentemente da `curato` — `services/urban-memory`,
vedi `contributi_memoria` sotto). Import name del pacchetto: `intelligence_index` (nome
distribuzione: `lucca-intelligence-index`).

**Perché esiste.** Misura la **salute CULTURALE** della città, non soltanto quella economica o
infrastrutturale — un nuovo KPI per l'amministrazione, con lo stesso rigore con cui si misura il
traffico. Le dashboard per Comune, hotel e musei (fuori dal perimetro di questo servizio, vedi
"Cosa NON fa" sotto) leggeranno tutte da qui: una sola fonte, viste diverse.

## Il vincolo centrale della wave: aggregazione e non re-identificazione (k=10)

Ogni indicatore, a QUALUNQUE livello di dettaglio, deve coinvolgere almeno **10 `person_id`
distinti** prima di essere pubblicato — sotto soglia, MAI un numero calcolato su meno di k
persone, anche se tecnicamente disponibile. Questo è un gate di privacy (CLAUDE.md — "Privacy by
design"), applicato in **un solo punto centrale e riutilizzabile**
(`intelligence_index.soglia`), mai ricontrollato a mano in ogni funzione indicatore:

- `SOGLIA_MINIMA_PERSONE = 10` — costante unica, non un numero magico ripetuto.
- `richiedi_soglia(person_ids, contesto)` — solleva `DatiInsufficientiError` se sotto soglia.
  Usata da `intelligence_index.index.calcola_index`, UNA volta per indicatore: dato che
  `UrbanIntelligenceIndex` (contratto **congelato**, `packages/contracts`) ha campi `float`/`int`
  NON opzionali per 7 indicatori su 8, non esiste un modo di "pubblicare comunque, ma con un
  valore vuoto" dentro quel tipo — sollevare un'eccezione di dominio esplicita (stesso pattern
  delle altre eccezioni del repo: `ConsentRequiredError`, `InvalidTargetsError`...) è l'unica
  alternativa onesta a fabbricare un numero. Il chiamante (il BFF, in una wave successiva) la
  mappa in una risposta "dato insufficiente" esplicita.
- `valore_se_soglia(person_ids, valore)` — ritorna `None` invece di sollevare: pensata per future
  aggregazioni a grana più fine (drill-down della dashboard: per luogo, per profilo, per fascia
  oraria — fuori dal perimetro di questa wave, che produce solo l'aggregato a 8 campi), dove
  "omettere la cella" è preferibile a "interrompere l'intero calcolo".

**Decisione da confermare con ethics-guardian**: dato il contratto congelato non-Optional, una
popolazione sotto soglia per l'INTERO periodo (il livello più aggregato possibile) fa fallire
`calcola_index` con `DatiInsufficientiError`, non degradare silenziosamente un singolo campo. In
produzione (una città intera, un mese intero) questo non dovrebbe mai accadere; è un margine di
sicurezza esplicito, non un caso atteso.

**Tutti e 8 gli indicatori** applicano il gate, senza eccezioni: `contributi_memoria` è stato
l'ultimo a riceverlo (vedi la sezione dedicata sotto per la motivazione di `ethics-guardian`).

## `distribuzione_flussi` è l'indicatore che ci giudica

Misura **direttamente** l'overtourism (CLAUDE.md): se sale la concentrazione, il sistema sta
fallendo il proprio scopo, anche se tutti gli altri numeri sono buoni. Va reso visibile, mai
nascosto o smussato — nessuna funzione di questo servizio applica un floor, un cap "cosmetico" o
un arrotondamento che ne attenuerebbe un valore basso.

## Le 8 formule — negoziate vs proposte

Due indicatori (`distribuzione_flussi`, `nuovi_percorsi`) e uno negoziato in una forma più
articolata (`attivazione_locale`) hanno una formula **GIÀ NEGOZIATA** col committente. La **fonte**
di `contributi_memoria` è anch'essa **NEGOZIATA** (direzione esplicita e finale del committente —
vedi sotto), pur restando un semplice conteggio. I restanti tre (`tempo_medio_esperienza_min`,
`coinvolgimento`, `tasso_ritorno`) **NON hanno una formula pregressa** nella conversazione col
committente: sono **proposte** di questo modulo, derivate onestamente dai soli dati realmente
disponibili nel repo — da confermare con ethics-guardian e col committente prima di considerarle
definitive.

### `distribuzione_flussi` — NEGOZIATA

`intelligence_index/distribuzione.py`. Entropia di Shannon normalizzata sul numero di luoghi
**disponibili** (non su quelli effettivamente comparsi), sulla frequenza di `place_id` tra le
tappe (`BehaviorEvent` tipo `"stop"`):

```
H(p) = - sum_i p_i * log(p_i)      p_i = frequenza del place_id i tra le tappe osservate
distribuzione = H(p) / log(n)      n = luoghi disponibili (1 = distribuiti, 0 = concentrati)
```

Questa formula è nata come helper di test in `tests/test_integration_wave3b.py` (Wave 3b,
criterio di accettazione del Recommender: "il recommender non deve aumentare la concentrazione dei
flussi"), **prima** che esistesse questo modulo. `intelligence_index.distribuzione` è
l'estrazione di quella formula in un'**unica fonte di verità**: sia
`tests/test_integration_wave3b.py::_distribuzione_flussi` (ora un alias di import) sia
`intelligence_index.indicatori.distribuzione_flussi_indicatore` la importano da qui — nessuna
delle due la ridefinisce.

Normalizzare sull'intero universo di luoghi (non sui soli comparsi) è la scelta deliberata che
rende confrontabili popolazioni di tappe diverse **a parità di metrica**: usare il numero di
luoghi comparsi premierebbe artificialmente una popolazione che ne tocca pochi ma li distribuisce
"bene" fra loro, ignorando la maggior parte della città.

`n_luoghi_disponibili` = `len(grado_semantico)` (`graph.topology.grado_semantico()` /
`GraphMetricsSource.grado_semantico()` ritorna una riga per **ogni** Luogo, incluso grado zero):
stessa fonte già iniettata per `attivazione_locale`, nessuna seconda query.

### `attivazione_locale` — NEGOZIATA

`(tappe BehaviorEvent tipo="stop" su luoghi FUORI dai top-N per grado SEMANTICO) / (tappe totali
nel periodo)`. Il grado nella rete `VICINO`/prossimità fisica è stato **esplicitamente respinto**
dal committente ("misura la pianta della città, non la cultura"): si usa invece
`graph.topology.grado_semantico()` / `graph.metrics.GraphMetricsSource.grado_semantico()` — grado
CULTURALE (relazioni `LEGATO_A`/`SI_SVOLGE_A`/`OFFRE`/`EVOCA`/`ISPIRATA_DA`, incluse quelle delle
Botteghe ospitate), non fisico.

"Top-N" = soglia sulla **mediana** (default) del grado semantico, calcolata sull'intero universo
di luoghi disponibili. Il percentile è un **parametro esplicito**
(`soglia_percentile`, `intelligence_index.indicatori.attivazione_locale`), mai una soglia
hardcoded in mezzo alla logica — chi chiama può scegliere un percentile diverso dalla mediana, il
default resta quello negoziato. Un luogo con grado **strettamente minore** della soglia è "fuori
dai top" (luogo minore); un grado pari alla soglia resta "dentro".

### `nuovi_percorsi` — NEGOZIATA (con un buco nei dati dichiarato)

```
nuovi_percorsi(periodo) = |coppie consecutive in itinerari del periodo, NON collegate nello
                            snapshot VICINO di INIZIO periodo|
                          / |tutte le coppie non connesse in quello snapshot|
```

Tasso, non conteggio (riflesso nel contratto: `float` in `[0, 1]`): un conteggio grezzo
scenderebbe da solo man mano che il grafo cresce (più relazioni = meno coppie "non collegate"),
confondendo la crescita del grafo con un calo dell'esplorazione spontanea (vedi
`docs/DATA_CONTRACTS.md` §7).

Il denominatore viene da `graph.topology.non_connected_place_pairs(at=inizio_periodo)` /
`GraphMetricsSource.non_connected_place_pairs(at=...)` — lo snapshot delle coppie di luoghi non
connesse da `VICINO` a **inizio periodo** (`intelligence_index.periodo.intervallo_periodo`, unica
definizione di "periodo" nel servizio). Il numeratore conta coppie **distinte** (un insieme, non
occorrenze): un solo percorso nuovo usato da 50 itinerari diversi conta una volta, non 50.

**BUCO NEI DATI — dichiarato, non aggirato.** Oggi **non esiste**, in questo repo, alcuna fonte
persistita di "itinerari generati con le loro tappe in sequenza, per periodo".
`experience_engine.engine.compose_itinerary` produce un `Itinerary` solo **in memoria** per la
singola richiesta HTTP (`POST /itinerary`, `services/api/api/main.py`); non viene mai scritto su
Postgres/Neo4j. La funzione `intelligence_index.indicatori.nuovi_percorsi` è quindi **reale e
testata** (con itinerari sintetici, `tests/test_indicatori.py`), ma `itinerari_periodo` non ha
oggi alcun cablaggio a dati di produzione: chi chiama `calcola_index` deve passare esplicitamente
`itinerari_periodo=[]` finché tale persistenza non esiste — **mai** un valore fabbricato per
colmare il buco. Con `itinerari_periodo=[]`, il gate k=10 non scatta (nessuna persona coinvolta
non è "popolazione troppo piccola", è assenza di dato: vedi `calcola_index`), e il valore
risultante è `0.0` per costruzione (nessuna coppia emersa da zero itinerari) — **questo `0.0` va
letto come "wiring assente", non come "nessun percorso nuovo osservato"**, finché la persistenza
degli itinerari non esiste. Segnalato esplicitamente per `api-engineer`/una wave successiva:
servirebbe una tabella `itinerary`/`itinerary_stop` (surrogata, come `behavior_event`) scritta da
`POST /itinerary`, e questo servizio la leggerebbe in sola lettura, stesso principio già applicato
a `PostgresBehaviorEventSource` sotto.

### `tempo_medio_esperienza_min` — PROPOSTA

Media di `ExperienceNode.durata_min`, pesata sugli eventi `stop`/`booking` (presenza fisica reale)
— **mai** `view` (potrebbe essere solo una scheda sfogliata sullo schermo, senza che la persona
abbia mai messo piede nel luogo). "Pesata sugli eventi" = media aritmetica su **tutti** gli eventi
di presenza (non sulle sole esperienze distinte): un'esperienza con più eventi di presenza
contribuisce proporzionalmente di più. Stessa distinzione già fatta da
`recommender.features.PESI_TIPO` (`stop`/`booking` pesano il doppio di `view`), ma non ne
duplica la tabella (che serve al ranking, uno scopo diverso).

### `coinvolgimento` — PROPOSTA

Tasso in `[0, 1]`: quota di "viste" (`view`) che si convertono in un segnale più forte
(`stop`/`booking`/`photo`/`memory_contrib`) sulla **stessa coppia** `(person_id, experience_id)`.
Granularità scelta deliberatamente a livello di coppia, non un rapporto grezzo tra conteggi
totali: un rapporto grezzo potrebbe superare 1 se molte presenze fisiche avvengono senza una
"view" precedente (es. arrivo diretto sul posto), violando `Field(ge=0, le=1)` del contratto e
comunque privo di un'interpretazione onesta come "quota". Misurare sulla coppia mantiene il
rapporto naturalmente in `[0, 1]` (le conversioni sono un sottoinsieme delle viste, per
costruzione). Le coppie con presenza fisica ma senza una view precedente non entrano né a
numeratore né a denominatore: non sono "viste convertite" (già catturate da
`tempo_medio_esperienza_min`), non "mancato coinvolgimento".

### `tasso_ritorno` — PROPOSTA (finestra dichiarata)

Tasso in `[0, 1]`: quota di `person_id` attivi nel periodo che tornano su una **data di calendario
distinta all'interno dello stesso periodo** (es. luglio: attivo il 3 e il 20 luglio conta come
ritorno; attivo più volte nello stesso giorno no). Finestra scelta per due motivi: (1) calcolabile
solo dai dati già richiesti per questo periodo, senza interrogare l'intera storia pregressa; (2)
evita di confondere "sessione lunga in un solo giorno" con "essere tornati in città".

**Limite noto**: non cattura la fedeltà CROSS-periodo (attivo a giugno e di nuovo a luglio, mai
due volte nello stesso mese, non risulta "di ritorno" qui). Possibile con lo stesso repository
(basta interrogare `events_in_period` su una finestra più ampia), ma richiede una decisione
esplicita su quanto indietro guardare — fuori dal perimetro di questa wave, per non fabbricare una
scelta arbitraria di finestra.

### `contributi_memoria` — NEGOZIATA (fonte decisa esplicitamente dal committente)

Conteggio di **TUTTI** i `MemoryContribution` creati nel periodo, **indipendentemente da
`curato`** — non conteggio di `BehaviorEvent` tipo `"memory_contrib"` (un evento dice solo "un
tentativo di conferimento è avvenuto ora", mai se il contributo è poi passato la curatela).

Storia della decisione (rilevante perché il committente vi ha fatto riferimento esplicito):
questa era la proposta **originale** del modulo. Una revisione successiva l'aveva ristretta ai
soli `curato=True` (motivazione: "la Urban Memory pubblica, non i tentativi grezzi"). Il
committente ha **respinto** quella restrizione e riportato l'indicatore alla fonte originale, per
tre ragioni:

1. La curatela ha un **ritardo fisiologico** — contare solo i curati sottostima sistematicamente
   l'impegno civico recente, specialmente a ridosso della fine del periodo di reporting.
2. Dopo il fix di Wave 2 (CLAUDE.md: "la curatela verifica i target... un contributo raggiunge
   `curato=True` solo se ogni id in `riguarda` esiste nel Knowledge Graph"), un contributo può
   restare bloccato in `curato=False` per ragioni **tecniche** (il luogo/artista descritto non è
   ancora nel grafo), non solo perché in attesa di revisione umana.
3. Una dashboard comunale che mostra "0 contributi" perché la curatela è ferma per un motivo
   tecnico, letta come "i cittadini non partecipano", è **esattamente** il dato fuorviante da
   evitare — l'indicatore principale deve contare la **partecipazione**, non l'**approvazione**.

Fonte: l'unione di `urban_memory.MemoryRepository.list_pending()` (`curato=False`) e
`.list_curated()` (`curato=True`) — non serve un metodo dedicato "tutti" sul repository: `curato`
è un `bool`, i due elenchi sono mutuamente esclusivi e coprono l'intero spazio (nessuno stato
"rifiutato" separato).

**Sotto-conteggio disponibile, non nel contratto**: `intelligence_index.indicatori.
contributi_memoria_curati(memorie_periodo)` conta quanti dei contributi ricevuti hanno
`curato=True` — utile come drill-down futuro ("quanta della partecipazione è già pubblica"), ma
NON entra nel campo `UrbanIntelligenceIndex.contributi_memoria` (il contratto congelato resta un
solo `int`): stesso principio già seguito per `valore_se_soglia` (pronto, non ancora cablato a un
endpoint).

**Gate k=10 — APPLICATO (decisione di `ethics-guardian`).** La vecchia motivazione per esentare
questo indicatore dal gate k=10 ("un contributo curato è già pubblico, contarne il numero non
espone nulla di nuovo") **non reggeva più**: il conteggio include anche i `pending`, che NON sono
ancora pubblici (`GET /memory/{place_id}` restituisce solo i curati). `ethics-guardian` ha dato
una motivazione precisa, indipendente dal fatto che il campo esposto sia un tasso o un conteggio
grezzo: le celle di conteggio grezzo sotto soglia sono il caso classico di **soppressione cella**
nella disclosure control statistica — un "1" o un "2" in una cella rivela l'esistenza di una
popolazione minuscola e potenzialmente identificabile. `contributi_memoria`
(`intelligence_index.indicatori.contributi_memoria`) espone quindi ora `(valore,
contributor_ids_coinvolti)`, **STESSO pattern degli altri 7 indicatori**, e
`intelligence_index.index.calcola_index` applica `richiedi_soglia(persone_memoria,
"contributi_memoria", soglia_minima_persone)` nello stesso punto centrale usato per tutti gli
altri campi — **nessuna eccezione residua**: tutti e 8 gli indicatori passano dal gate k=10 (salvo
`nuovi_percorsi`, che non ha nulla da rifiutare quando `itinerari_periodo=[]`: è un'assenza di
dato, non una popolazione piccola — vedi sopra).

Il caso di re-identificazione più rilevante per questo indicatore non è "pochi contributi in
assoluto", ma **molti contributi concentrati su un solo/pochi `contributor_id`**: una persona
molto attiva nella Urban Memory è identificabile tanto quanto una popolazione piccola, anche con
un conteggio grezzo alto — coperto esplicitamente da un test dedicato
(`tests/test_index.py::test_calcola_index_molti_contributi_da_pochi_contributor_solleva_il_gate`).

### `soddisfazione` — nessuna fonte oggi

Sempre `None` in questa wave: nessuna recensione/survey in prodotto (`docs/DATA_CONTRACTS.md`
§7). `calcola_index` lo imposta esplicitamente a `None`, **mai** un valore stimato o interpolato
da altri indicatori solo per riempire il campo.

## Cosa NON è un input di nessun indicatore, e perché

- **Campi commerciali** (`ExperienceNode.partner_id`, `.prezzo_eur`, `.partner_abbonamento_attivo`,
  `.prenotabile`, `contracts.Partner`, `contracts.CommissionRecord`). "Nessuno spazio è
  acquistabile" (CLAUDE.md) vale anche per il **reporting verso il Comune**, non solo per il
  ranking: un partner non deve poter comprare un indicatore migliore più di quanto possa comprare
  visibilità. Nessun modulo di questo servizio importa `Partner`/`CommissionRecord`; nessuna
  funzione di `intelligence_index.indicatori` legge un campo commerciale di `ExperienceNode`
  (solo `place_id`/`durata_min`, gli unici due campi effettivamente usati).
- **Click, conversioni, ricavi pubblicitari.** Nessun evento di `BehaviorEvent` è pesato per
  valore economico: `coinvolgimento`/`tempo_medio_esperienza_min` contano **solo che l'evento sia
  avvenuto**, mai `ExperienceNode.prezzo_eur` o l'esito di una `Booking`/`CommissionRecord`.
- **Rating/recensioni di provider terzi** (Google, TripAdvisor o simili). Nessun campo di questo
  tipo esiste in `packages/contracts` né nel seed del grafo: se un domani venisse introdotto, non
  entrerebbe comunque in un indicatore di questo servizio — stessa esclusione già motivata (e più
  estesa) in `services/recommender/README.md`, "Cosa NON è una feature, e perché".
- **`grado` nella rete `VICINO`** (prossimità fisica) come proxy di "quanto un luogo è centrale
  culturalmente" per `attivazione_locale`: esplicitamente respinto dal committente, si usa il
  grado **semantico** (vedi sopra).

## Struttura del pacchetto

- `intelligence_index/periodo.py` — `intervallo_periodo(periodo)`: unica conversione
  `"YYYY-MM"` -> `[inizio, fine)` UTC, usata da tutto il resto del servizio (eventi, memorie,
  snapshot del grafo): due definizioni di "inizio mese" leggermente diverse produrrebbero
  indicatori non confrontabili senza che nessuno se ne accorga.
- `intelligence_index/soglia.py` — il gate k=10 (vedi sopra): `SOGLIA_MINIMA_PERSONE`,
  `DatiInsufficientiError`, `richiedi_soglia`, `valore_se_soglia`.
- `intelligence_index/distribuzione.py` — `distribuzione_flussi(place_ids, n_luoghi_disponibili)`,
  formula condivisa con `tests/test_integration_wave3b.py` (vedi sopra).
- `intelligence_index/catalogo.py` — `esperienze_per_id(candidate_source)`: catalogo
  `experience_id -> ExperienceNode`, ottenuto da `graph.source.CandidateSource.candidates(...)`
  con un contesto NEUTRO (stesso principio del `SEGNALE_NEUTRO_STRUTTURALE` di
  `recommender.ranking`) — nessuna query nuova, nessuna seconda fonte di verità sul catalogo.
- `intelligence_index/indicatori.py` — le 8 funzioni pure, ognuna ritorna
  `(valore, person_ids_coinvolti)`: il gate k=10 NON è applicato qui dentro, solo esposto, così
  che `calcola_index` lo applichi in un solo punto centrale con lo stesso criterio per tutti.
- `intelligence_index/index.py` — `calcola_index(periodo, eventi, esperienze_per_id,
  grado_semantico, n_luoghi_disponibili, non_connesse_a_inizio_periodo, itinerari_periodo,
  memorie, ...) -> UrbanIntelligenceIndex`: orchestrazione PURA (nessun accesso diretto a
  Postgres/Neo4j), stesso principio di `recommender.costruisci_score_fn(repo, ...)` — tutte le
  dipendenze sono iniettate, mai lette da qui. Applica il filtro di periodo e il gate k=10.
- `intelligence_index/repository.py` — `BehaviorEventSource` (`Protocol`):
  `events_in_period(inizio, fine) -> list[BehaviorEvent]`.
  - `InMemoryBehaviorEventSource` — lista in-process. Percorso dei test e finché `DATABASE_URL`
    non è configurato.
  - `PostgresBehaviorEventSource` — Neon (`sslmode=require`) o Postgres locale: **sola lettura**
    sulla STESSA tabella `behavior_event` già creata/migrata da `recommender.migrate`
    (`services/recommender/sql/00_events_schema.sql`). Non un secondo schema: una query di
    lettura diversa (filtrata per periodo, non aggregata) per un bisogno diverso (reporting, non
    ranking). `recommender.repository.BehaviorEventRepository.conteggio_per_esperienza()` resta
    l'unica fonte per il ranking; non è sufficiente per l'Index (nessun filtro per periodo, nessun
    `person_id` a grana fine).
- `intelligence_index/deps.py` — selezione Seed/Neo4j e In-Memory/Postgres in base al `.env`
  (il fallback Seed usa il dataset scelto da `CITY_SEED`, letto dallo stesso `merged_env()`;
  valore invalido -> `ValueError`),
  STESSO pattern di `services/api/api/deps.py` (nessun `if local/cloud`, solo presenza delle
  variabili d'ambiente), duplicato localmente qui — come già fanno `recommender._env`/
  `urban_memory._env` — per comodità di chi cablerà l'endpoint dashboard (`api-engineer`, fuori
  dal perimetro di questa wave). `calcola_index` non importa mai questo modulo: resta testabile
  senza alcun database.
- `intelligence_index/dashboard.py` — i due adattatori PURI verso le risposte dashboard
  (`docs/DATA_CONTRACTS.md` §7, sottosezione "Risposte dashboard"), vedi sotto.

## Adattatori dashboard — `intelligence_index/dashboard.py`

Nessuna logica di calcolo nuova: due funzioni PURE (nessun accesso diretto a Postgres/Neo4j, tutto
iniettato) che traducono l'uscita di `calcola_index`/degli eventi grezzi nei due contratti di
`GET /dashboard/*` (`packages/contracts`). Non ancora cablate a nessun endpoint HTTP — quello è il
passo successivo di `api-engineer`, che si procurerà gli argomenti via `intelligence_index.deps`,
`intelligence_index.catalogo.esperienze_per_id` e `graph.metrics.GraphMetricsSource.
grado_semantico()`.

### `indice_per_dashboard(...) -> DashboardIndexResponse`

Wrapper di `calcola_index`: STESSI parametri, nessuna dipendenza nuova. Cattura
`DatiInsufficientiError` e la traduce in uno stato "dato insufficiente" di prima classe invece di
propagarla grezza o fabbricare un `UrbanIntelligenceIndex`:

- calcolo riuscito -> `disponibile=True`, `index` popolato, `motivo_indisponibilita=None`;
- `DatiInsufficientiError` sollevata -> `disponibile=False`, `index=None`,
  `motivo_indisponibilita=` un messaggio GENERICO, costruito qui a partire SOLO da
  `exc.contesto` (il nome dell'indicatore, es. `"coinvolgimento"` — non identificante) e
  `exc.soglia` (la costante k, pubblica e nota) — **MAI `str(eccezione)`, MAI `exc.n_persone`.**

**Bug di privacy corretto in questa wave — MAI riusare `str(eccezione)` così com'è come testo
pubblico.** `DatiInsufficientiError.__str__()` include `n_persone`: il conteggio ESATTO di persone
distinte sotto soglia (es. `"3 persone distinte coinvolte"`). Quel messaggio è corretto e utile nei
log interni/nel debug lato server — ma un'implementazione precedente di `indice_per_dashboard`
passava `str(eccezione)` direttamente a `motivo_indisponibilita`, che è un campo pubblico di
`DashboardIndexResponse`, servito da `GET /dashboard/index`. Il risultato: un conteggio grezzo di
popolazione (`"3 persone"`) raggiungeva la risposta JSON pubblica — la STESSA classe di violazione
di re-identificazione che il gate k=10 esiste per prevenire su `celle_flusso`/sui valori numerici
degli indicatori, solo su un canale diverso: la "spiegazione leggibile" invece del "valore". Un
conteggio sotto soglia è identificante indipendentemente da DOVE compare nella risposta HTTP — in
una chiave JSON numerica o annidato dentro una frase libera in un campo di testo, il rischio di
re-identificazione è lo stesso. Per questo `indice_per_dashboard` ricostruisce SEMPRE il messaggio
pubblico da zero, senza mai propagare `n_persone`. Verificato esplicitamente in
`tests/test_integration_wave4_privacy.py::test_dashboard_index_popolazione_intera_sotto_soglia_httpreale`,
che cerca la cifra REALE della popolazione dello scenario come token isolato nella risposta HTTP
reale (non solo l'assenza di chiavi JSON come `"n_persone"`, che da sola non avrebbe intercettato
questo bug: il numero non viveva in una chiave, viveva dentro una frase).

Il `model_validator` di `DashboardIndexResponse` verifica per costruzione che i due stati non si
mescolino mai: questa funzione non ricontrolla da sé quella coerenza.

### `celle_flusso(...) -> DashboardFlowsResponse`

Aggregazione per la heatmap: UNA `FlowCell` per OGNI `place_id` in `grado_semantico` (STESSA fonte
già iniettata per `attivazione_locale`/`distribuzione_flussi` — le sue chiavi sono l'universo
completo dei luoghi del grafo, incluso grado zero), anche per i luoghi senza nessuna tappa nel
periodo/filtro. Per ogni luogo: filtra gli eventi `"stop"` che vi mappano (via
`esperienze_per_id`), ulteriormente ristretti da `giorno`/`ora` se forniti; poi
`intelligence_index.soglia.valore_se_soglia(persone, conteggio)` decide `disponibile`/
`conteggio_tappe`, gate indipendente per cella (k=10 `person_id` distinti).

**Punto critico di correttezza, non negoziabile: zero tappe è indistinguibile da sotto-soglia.**
Un luogo a ZERO tappe ha anche zero `person_id` distinti, quindi ricade SOTTO k=10 esattamente
come un luogo con 1-9 persone — `valore_se_soglia` applicato uniformemente, senza alcun ramo
speciale per il conteggio zero, produce lo STESSO `disponibile=False, conteggio_tappe=None` per
entrambi i casi. Se lo zero fosse trattato come "provabilmente innocuo" (es. `disponibile=True,
conteggio_tappe=0`), un osservatore della dashboard potrebbe dedurre PER ESCLUSIONE che ogni cella
soppressa ha necessariamente TRA 1 e 9 persone — esattamente l'informazione che il gate k=10 deve
nascondere. Coperto esplicitamente da
`tests/test_dashboard.py::test_celle_flusso_luogo_a_zero_eventi_e_indistinguibile_dal_soppresso`.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts`, `services/graph` e `services/urban-memory` sono
dipendenze locali (non su un indice pip):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/graph -e services/urban-memory -e services/intelligence-index
```

## Uso — offline, senza database (funzione pura)

```powershell
python -c "
from graph.source import SeedCandidateSource
from graph.metrics import SeedMetricsSource
from intelligence_index import calcola_index
from intelligence_index.catalogo import esperienze_per_id
from intelligence_index.periodo import intervallo_periodo

fonte_candidati = SeedCandidateSource()   # dataset da CITY_SEED (predefinito se assente)
fonte_metriche = SeedMetricsSource()
catalogo = esperienze_per_id(fonte_candidati)
grado = fonte_metriche.grado_semantico()
inizio, _fine = intervallo_periodo('2026-07')
non_connesse, _ = fonte_metriche.non_connected_place_pairs(at=inizio)

indice = calcola_index(
    periodo='2026-07',
    eventi=[],                          # BehaviorEvent, es. da un repository
    esperienze_per_id=catalogo,
    grado_semantico=grado,
    n_luoghi_disponibili=len(grado),
    non_connesse_a_inizio_periodo=non_connesse,
    itinerari_periodo=[],               # buco nei dati noto, vedi sopra
    memorie=[],                         # TUTTI i MemoryContribution del periodo
)
print(indice)
"
```

## Uso — con `DATABASE_URL`/`NEO4J_URI` (Neon/Aura o locali): dati reali

```powershell
python -c "
from intelligence_index import deps
from intelligence_index.catalogo import esperienze_per_id
from intelligence_index.periodo import intervallo_periodo

fonte_candidati = deps.get_candidate_source()      # Seed o Neo4j, in base al .env
fonte_metriche = deps.get_metrics_source()
sorgente_eventi = deps.get_event_source()          # InMemory o Postgres
repo_memoria = deps.get_memory_repository()

inizio, fine = intervallo_periodo('2026-07')
eventi = sorgente_eventi.events_in_period(inizio, fine)
# TUTTI i contributi del periodo, non solo curato=True (NEGOZIATA col
# committente — vedi la sezione contributi_memoria sopra): unione di
# list_pending() e list_curated(), non un metodo dedicato sul repository.
memorie = repo_memoria.list_pending() + repo_memoria.list_curated()
"
```

## Test

```powershell
pytest services/intelligence-index
```

Tutti i test girano **senza database**: `PostgresBehaviorEventSource`/`Neo4jCandidateSource`/
`Neo4jMetricsSource`/`PostgresMemoryRepository` sono coperti da test statici (import, struttura del
`Protocol`, scelta in `deps.py` con l'ambiente monkeypatchato — vedi `tests/test_deps.py`, che
monkeypatcha `deps.merged_env` invece di `os.environ`: questo repo ha un `.env` **reale** con
`NEO4J_URI`/`DATABASE_URL` di sviluppo alla radice, quindi ripulire solo `os.environ` darebbe un
falso verde in locale, stessa trappola già documentata in
`services/api/tests/test_booking.py`). `tests/test_indicatori.py` e `tests/test_index.py` coprono
ogni formula (negoziata e proposta) con dati sintetici; `tests/test_distribuzione.py` verifica i
casi limite dell'entropia (concentrazione totale, distribuzione perfetta, normalizzazione
sull'universo disponibile); `tests/test_dashboard.py` copre i due adattatori
(`indice_per_dashboard`/`celle_flusso`): i due stati di `DashboardIndexResponse`, e per
`celle_flusso` un luogo sopra soglia, uno sotto soglia con eventi, uno a zero eventi
(esplicitamente indistinguibile dal precedente — vedi sopra), il filtro `giorno`/`ora`, e che
`celle` copra sempre tutti i `place_id` del grafo. Se in una wave successiva verrà aggiunta una
fonte persistita di itinerari, servirà un test di integrazione con Postgres/Neo4j reali —
segnalato per `test-engineer`, non scavalcato qui.

```powershell
ruff check services/intelligence-index
```

## Cosa NON fa questo servizio (fuori dal suo perimetro)

- **Nessun endpoint HTTP.** `GET /dashboard/index` e `GET /dashboard/flows`
  (`docs/DATA_CONTRACTS.md` §7-§8) sono responsabilità del BFF (`services/api`), in una wave
  successiva — questo servizio espone solo `calcola_index`, i due adattatori
  `indice_per_dashboard`/`celle_flusso` (`intelligence_index/dashboard.py`) e le loro dipendenze
  iniettabili. Nessuno dei due adattatori si procura da sé eventi/catalogo/`grado_semantico`: li
  riceve per iniezione, esattamente come `calcola_index`.
- **Nessun drill-down per profilo.** `celle_flusso` copre il drill-down per luogo (e, tramite i
  filtri opzionali, per luogo×giorno e luogo×ora), ma nessuna funzione di questo servizio
  aggrega per profilo emozionale — fuori dal perimetro di questa wave.
- **Nessuna scrittura.** Solo lettura di `behavior_event` (Recommender) e `memory_contribution`
  (Urban Memory); la scrittura resta responsabilità esclusiva di `POST /events` e `POST /memory`.
