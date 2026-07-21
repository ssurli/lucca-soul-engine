# Limiti noti

Questo documento raccoglie i limiti architetturali **noti e accettati** del motore — non bug da
correggere alla prossima occasione, ma proprietà del design attuale che non garantiscono ciò che
potrebbero sembrare garantire. Un limite qui dentro è dichiarato, non nascosto: se una wave
futura vuole rimuoverlo, deve prima leggere questa voce e il suo costo stimato.

---

## Il Recommender ML non garantisce matematicamente la non-concentrazione aggregata

**Introdotto:** Wave 3b. **Componente:** `services/recommender`.

### Cosa è garantito oggi

Il recommender (`recommender.ranking.costruisci_score_fn`) corregge `calcola_score` con due
penalità indipendenti — quota storica (con smoothing di Laplace) e quota strutturale (dominanza
per pertinenza di contenuto, da profili-archetipo fissi) — entrambe sul `place_id`, mai un
premio. Questo è verificato empiricamente su **4 scenari storici indipendenti**
(`tests/test_integration_wave3b.py`): concentrazione su 1 luogo, su 5 luoghi, storico presente
anche sul luogo dominante per pertinenza, e uno scenario randomizzato a seed fisso. In tutti e
quattro, la distribuzione aggregata (misurata su una popolazione di 10 profili diversi) non
peggiora mai rispetto al ranking deterministico puro.

Questa è **robustezza empirica**: il fix è stato validato contro scenari scelti per essere
rappresentativi e avversariali (incluso quello che aveva originariamente fatto fallire il design
precedente), non contro un caso singolo che si sarebbe potuto ottimizzare per far passare il
test.

### Cosa NON è garantito

Robustezza empirica su 4 scenari non è una **garanzia matematica** per qualunque distribuzione
storica possibile. Il recommender calcola una `score_fn` **locale, per singola richiesta**: dato
un profilo e un insieme di candidati, restituisce un punteggio corretto — ma non ha visibilità
su cosa stanno ricevendo, nello stesso momento, gli altri visitatori. Una correzione locale, per
costruzione, non può garantire che una metrica di distribuzione **aggregata su una popolazione di
richieste** non peggiori mai: è sempre possibile costruire uno scenario storico patologico in cui
penalizzare i luoghi tracciati come sovraffollati sposta il flusso su un'alternativa che, pur non
tracciata, diventa a sua volta un collo di bottiglia — esattamente il meccanismo che ha causato il
bug originale di questa wave, ora mitigato (quota strutturale) ma non reso matematicamente
impossibile in ogni scenario concepibile.

### Cosa servirebbe per una garanzia vera

| Approccio | Come funzionerebbe | Perché non è stato fatto ora |
|---|---|---|
| **Allocazione globale a batch** | Invece di rispondere richiesta per richiesta, raccogliere un insieme di richieste in una finestra temporale e risolvere un problema di assegnazione ottima (fair division) che massimizzi la pertinenza individuale sotto un vincolo di distribuzione aggregata. | Ottimizzazione combinatoria (NP-hard in generale). Richiede conoscere le richieste **prima** di servirle: incompatibile con un servizio che risponde in tempo reale man mano che i visitatori arrivano — cambierebbe il modello di servizio da "richiesta-risposta" a "batch differito". |
| **Stato condiviso in tempo reale + algoritmo di allocazione online** | Un contatore vivo e condiviso (es. Redis, o una tabella Postgres con incrementi atomici) di "quante persone sono state instradate verso il luogo X in questa finestra", letto e aggiornato ad ogni richiesta, con una penalità che cresce con l'allocazione **in corso** (non solo con lo storico passato) secondo un algoritmo di tipo *online fair allocation* / regret minimization. | Darebbe un limite superiore **vero** alla concentrazione, ma resta **probabilistico**, non assoluto (dipende dall'ordine di arrivo delle richieste, da condizioni di gara tra richieste simultanee). Richiede: infrastruttura condivisa nuova, gestione della concorrenza tra richieste simultanee, un algoritmo online non banale (R&D, non solo ingegneria) — non un adattamento incrementale del codice attuale. |

**Costo stimato:** settimane di lavoro dedicato (progettazione dell'algoritmo online, infrastruttura
condivisa, test di concorrenza) — probabilmente una wave a sé, non un task all'interno di una wave
esistente. C'è sinergia naturale con l'**Urban Intelligence Index** (Wave 4), che dovrà comunque
tracciare `distribuzione_flussi` in modo aggregato: lo stato condiviso richiesto dal secondo
approccio potrebbe riusare la stessa infrastruttura di tracciamento, ma l'algoritmo di allocazione
online **con garanzia** resta un pezzo di ricerca applicata in più, non incluso nel semplice
tracciamento a fini di reporting.

### Decisione

Non implementato ora. Il recommender resta con la correzione locale (Wave 3b), validata sui 4
scenari sopra. Questo limite va riletto prima di:
- estendere il recommender con nuovi termini di penalità (per non illudersi di "risolvere" un
  problema strutturale con un altro aggiustamento locale);
- decidere lo scope della Wave 4 (Urban Intelligence Index), dove il tracciamento in tempo quasi
  reale della distribuzione dei flussi è comunque previsto — è il punto naturale in cui
  rivalutare se investire nell'algoritmo di allocazione online.

---

## `tasso_ritorno` misura solo il ritorno ENTRO lo stesso periodo, non la fedeltà cross-periodo

**Introdotto:** Wave 4. **Componente:** `services/intelligence-index`.

### Cosa è garantito oggi

`intelligence_index.indicatori.tasso_ritorno` misura, per un periodo (`"YYYY-MM"`), la quota di
`person_id` attivi che tornano su una data di calendario DISTINTA **all'interno dello stesso
periodo** (es. luglio: attivo il 3 e il 20 luglio conta come ritorno; attivo più volte nello
stesso giorno no). Questa finestra è stata scelta deliberatamente, per due motivi: (1) è
calcolabile SOLO dai dati già richiesti per quel periodo (`BehaviorEventSource.
events_in_period`), senza dover interrogare l'intera storia pregressa della piattaforma; (2)
evita di confondere "sessione lunga in un solo giorno" con "essere tornati in città". Il valore è
reale e testato (`tests/test_indicatori.py`), non un placeholder.

### Cosa NON è garantito

Questa definizione strutturalmente **non può misurare** il fenomeno più interessante per
un'amministrazione: la fedeltà pluriennale o stagionale di un turista. Il ritorno vero di un
turista è tipicamente a **mesi di distanza** (l'anno dopo, la stagione dopo), non dentro lo stesso
periodo di reporting — una persona attiva a giugno e di nuovo a luglio, ma mai due volte nello
stesso mese, non risulta "di ritorno" con la definizione attuale, anche se è esattamente il caso
che un Comune vorrebbe vedere in una dashboard sul turismo di ritorno. Quello che l'indicatore
misura oggi è più vicino a "pattern di soggiorno più lungo dentro lo stesso mese" che a "fedeltà
alla città".

### Cosa servirebbe per una definizione cross-periodo

Una definizione cross-periodo è possibile con lo **stesso** repository: basta interrogare
`BehaviorEventSource.events_in_period` su una finestra più ampia del periodo corrente (es.
`[periodo - N mesi, fine periodo)`), invece di limitarsi al periodo stesso, e verificare se un
`person_id` attivo nel periodo corrente compare anche in un periodo precedente della finestra.
Il pezzo mancante non è tecnico — è una **decisione esplicita su quanto indietro guardare** (un
anno? una stagione? un numero fisso di mesi?), che determina cosa "ritorno" significa nella
pratica e quanto costa in query storiche. Non è stata presa in questa wave per non fabbricare una
scelta arbitraria di finestra solo per riempire la formula: una finestra sbagliata (troppo corta,
troppo lunga) produrrebbe un numero altrettanto fuorviante di quello attuale, solo con un'aria di
maggiore completezza.

### Decisione

Non implementato ora. `tasso_ritorno` resta con la finestra intra-periodo (Wave 4), dichiarata sia
nel docstring della funzione sia nel README del servizio. Questo limite va riletto prima di:
- presentare `tasso_ritorno` a un'amministrazione come misura di "fedeltà" senza qualificare
  esplicitamente che è fedeltà **entro il mese**, non cross-stagione;
- decidere di investire in una definizione cross-periodo, che richiede prima la decisione
  esplicita sulla finestra (quanto indietro guardare) menzionata sopra — non un adattamento
  incrementale silenzioso della formula attuale.

---

## `nuovi_percorsi` ritorna `0.0` quando `itinerari_periodo=[]`: indistinguibile da uno zero reale

**Introdotto:** Wave 4. **Componente:** `services/intelligence-index`.

### Cosa è garantito oggi

`intelligence_index.indicatori.nuovi_percorsi` è una funzione REALE e testata (con itinerari
sintetici, `tests/test_indicatori.py`): calcola correttamente la quota di coppie consecutive di
tappe, in itinerari del periodo, che collegano due luoghi NON connessi da `VICINO` nello snapshot
di inizio periodo, sul totale delle coppie non connesse disponibili in quello snapshot — la
formula NEGOZIATA col committente (vedi README del servizio). Quando riceve un
`itinerari_periodo` non vuoto, il valore prodotto è affidabile e passa dal gate k=10
(`intelligence_index.index.calcola_index`).

### Cosa NON è garantito

Oggi **non esiste**, in questo repo, alcuna fonte persistita di "itinerari generati con le loro
tappe in sequenza, per periodo". `experience_engine.engine.compose_itinerary` produce un
`Itinerary` solo **in memoria** per la singola richiesta HTTP (`POST /itinerary`,
`services/api/api/main.py`): non viene mai scritto su Postgres/Neo4j. Di conseguenza, chi chiama
`calcola_index` in produzione deve passare esplicitamente `itinerari_periodo=[]` — non per scelta
di dominio, ma perché non c'è altro da passare (buco nei dati, non un caso applicativo reale). Con
`itinerari_periodo=[]`, il gate k=10 non scatta (nessun itinerario da valutare non è "popolazione
troppo piccola", è assenza di dato) e la formula produce `0.0` per costruzione (nessuna coppia può
emergere da zero itinerari).

Questo `0.0`, una volta esposto su una dashboard (Comune, hotel, musei — tutte leggono dallo
stesso `UrbanIntelligenceIndex`), è **indistinguibile** da uno zero reale ("nessun percorso nuovo
osservato nel periodo, popolazione presente ma senza esplorazione spontanea"). Un amministratore
che legge `nuovi_percorsi: 0.0` in una dashboard non ha modo di sapere, da quel solo numero, se
sta guardando "il wiring non è ancora collegato" o "i visitatori non hanno esplorato percorsi
nuovi questo mese" — due fatti con implicazioni completamente diverse per una decisione pubblica.

### Cosa servirebbe per chiudere il buco

Una tabella `itinerary`/`itinerary_stop` (surrogata, stesso principio già applicato a
`behavior_event` da `recommender.migrate`), scritta da `POST /itinerary` al momento della
generazione, con le tappe in sequenza e il periodo di generazione. `intelligence_index` la
leggerebbe in **sola lettura** (stesso principio già applicato a `PostgresBehaviorEventSource`,
`intelligence_index/repository.py`), popolando `itinerari_periodo` con dati reali invece di `[]`.
Già segnalato per `api-engineer`/una wave successiva nel README del servizio
(`services/intelligence-index/README.md`, sezione `nuovi_percorsi`).

### Decisione

Non implementato ora. `nuovi_percorsi` resta con `itinerari_periodo=[]` finché la persistenza
degli itinerari non esiste, e il valore `0.0` prodotto in quel caso va letto come **"wiring
assente"**, non come **"nessun percorso nuovo osservato"** — dichiarato nel docstring della
funzione, nel README del servizio e qui. Questo limite va riletto prima di:
- cablare `GET /dashboard/index` (`docs/DATA_CONTRACTS.md` §8) verso una dashboard reale per il
  Comune: se la persistenza degli itinerari non esiste ancora a quel punto, la dashboard deve
  segnalare esplicitamente "dato non disponibile" per questo campo, non presentare `0.0` come un
  valore misurato;
- decidere di investire nella tabella `itinerary`/`itinerary_stop` sopra, che chiuderebbe il buco
  senza richiedere alcuna modifica alla formula già scritta e testata.

---

## La dashboard Flutter (Wave 4) è scritta ma non verificata a compilazione/esecuzione

**Introdotto:** Wave 4. **Componente:** `apps/lucca_soul_app`.

### Cosa è garantito oggi

`DashboardScreen` e i quattro modelli che rispecchiano `docs/DATA_CONTRACTS.md` §7
(`UrbanIntelligenceIndex`, `DashboardIndexResponse`, `FlowCell`, `DashboardFlowsResponse`) sono
scritti seguendo fedelmente le convenzioni già in uso nel resto dell'app (stesso stile di
`fromJson`/`toJson` di `MemoryContribution`/`Itinerary`, stesso pattern di stato
caricamento/errore/dati di `ItineraryScreen`/`CitizenScreen`). `BffClient.dashboardIndex`/
`dashboardFlows` sono l'unico punto di rete verso `GET /dashboard/*` (nessuna chiamata diretta a
`services/intelligence-index`). `DashboardIndexResponse`/`FlowCell` hanno un costruttore privato
(`._`): l'unico modo di ottenere un'istanza è `fromJson`, così il vincolo di coerenza
`disponibile ⇔ valore` del contratto non è aggirabile componendo l'oggetto a mano lato client.
Sono stati scritti anche due file di test (`test/dashboard_models_test.dart`,
`test/periodo_test.dart`) nello stesso stile "puro" già in uso (`test/models_test.dart`,
`test/itinerary_diff_test.dart`): nessuna dipendenza da widget/device, solo round-trip JSON e
funzioni di formattazione data.

Tutto questo è stato prodotto e revisionato **solo per lettura**: struttura, nomi dei campi
JSON (confrontati riga per riga con `docs/DATA_CONTRACTS.md`), tipi, generics, presenza di
`const`/`required` dove atteso.

### Cosa NON è garantito

Nessuno di questi file è mai stato **compilato**. In questa sessione non era disponibile né
`flutter` né `dart` (`which flutter`/`which dart` falliscono, `apps/lucca_soul_app` non ha mai
visto un `flutter pub get`). Di conseguenza:
- Non è provato che il codice sia sintatticamente valido oltre la lettura manuale: un refuso di
  generics, un import mancante, un parametro posizionale scambiato per nominale — niente di
  tutto ciò sarebbe stato per forza notato a occhio.
- Le icone `Icons.*` usate in `dashboard_screen.dart` sono state scelte "alla cieca", preferendo
  deliberatamente nomi storici e ben noti dell'icon font Material (es. `Icons.favorite_border`
  invece di `Icons.favorite_outline`, `Icons.pie_chart_outline` invece di
  `Icons.scatter_plot_outlined`) proprio perché non era possibile verificare con l'analyzer se un
  nome esiste nella versione del pacchetto `flutter` risolta dal `pubspec.yaml`.
- I due nuovi file di test non sono mai stati **eseguiti**: `flutter test` non è mai girato, quindi
  non c'è nessuna prova che le asserzioni scritte in `dashboard_models_test.dart`/
  `periodo_test.dart` passino — potrebbero fallire per un dettaglio di formattazione o di
  arrotondamento mai osservato perché mai fatto girare.
- `flutter analyze` non è mai girato: le regole di `apps/lucca_soul_app/analysis_options.yaml`
  (`strict-casts`, `strict-inference`, `require_trailing_commas`, `prefer_const_constructors`) non
  sono mai state applicate al nuovo codice, solo emulate a mano nella lettura.

Questo è esattamente lo stesso tipo di buco di `soddisfazione` sopra (Wave 4,
`services/intelligence-index`): un dato/uno stato dichiarato assente, non un valore fabbricato per
sembrare completo. Qui il "valore fabbricato" sarebbe presentare la dashboard come "fatta" quando
in realtà è "scritta, non provata".

### Cosa servirebbe per chiudere il buco

1. **Flutter SDK** installato su una macchina (versione compatibile col vincolo
   `flutter: ">=3.19.0"` di `apps/lucca_soul_app/pubspec.yaml`; `dart >=3.3.0 <4.0.0`).
2. Nell'ordine, da `apps/lucca_soul_app/`:
   - `flutter pub get` — risolve le dipendenze (`http`, `flutter_lints`), scarica il toolchain.
   - `flutter analyze` — verifica statica reale: tipi, generics, regole di
     `analysis_options.yaml`, nomi di icone/API inesistenti.
   - `flutter test` — esegue TUTTA la suite (`test/models_test.dart`, `test/memory_test.dart`,
     `test/itinerary_diff_test.dart`, e i due nuovi `test/dashboard_models_test.dart`,
     `test/periodo_test.dart`), non solo i file nuovi: un regressione sui modelli esistenti
     sarebbe altrettanto grave di un test nuovo che fallisce.
3. **Eventualmente**, un job CI dedicato (es. GitHub Actions, `actions/flutter-action` più
   `flutter pub get && flutter analyze && flutter test`) che scatti automaticamente ad ogni push
   che tocca `apps/lucca_soul_app/**`. Senza CI, questo buco si ripresenterà identico ad ogni wave
   futura che tocchi l'app Flutter in una sessione senza una macchina con Flutter disponibile —
   una CI lo renderebbe strutturalmente impossibile da ignorare, non affidato alla memoria di chi
   orchestra la wave successiva.

### Decisione

Non verificato ora. Il codice della dashboard resta nello stato "scritto, non compilato" finché
qualcuno non esegue i tre comandi del punto 2 sopra su una macchina con Flutter SDK installato.
Questo limite va riletto prima di:
- presentare la dashboard Comune/Operatori come pronta a un cliente reale (Comune, hotel, museo);
- aggiungere altro codice sopra `apps/lucca_soul_app/lib/screens/dashboard_screen.dart` e i suoi
  modelli, che aggraverebbe il buco invece di chiuderlo se non verificato incrementalmente;
- decidere di investire nel job CI del punto 3, che è l'unico modo per non ripetere questo stesso
  limite ad ogni wave successiva che tocchi l'app.

---

## `behavior_event` non distingue eventi reali da sintetici/di test, e non ha retention

**Introdotto:** Wave 3b. **Componente:** `services/recommender`. **Trovato durante:** la verifica
manuale della Wave 4 (voce precedente in questo file) contro Neon/Aura reali.

### Cosa è garantito oggi

`intelligence_index` (Wave 4, `GET /dashboard/*`) filtra SEMPRE `behavior_event` per periodo
(`events_in_period(inizio, fine)`): un evento con `ts` fuori dall'intervallo richiesto non entra
nel calcolo di quella dashboard. Fin qui, isolare una prova manuale su un periodo futuro (es.
"2027-01") protegge davvero le metriche del mese corrente che un Comune/hotel/museo starebbe
guardando oggi.

### Cosa NON è garantito

`recommender.repository.PostgresBehaviorEventRepository.conteggio_per_esperienza()` — la query
che alimenta la correzione di quota storica di `recommender.ranking.costruisci_score_fn`, applicata
a OGNI `POST /itinerary` reale — NON ha alcun filtro temporale:

```sql
SELECT tipo, experience_id, COUNT(*) FROM behavior_event GROUP BY tipo, experience_id
```

Legge tutta la tabella, sempre. Conseguenza: **ogni riga che entra in `behavior_event` influenza
il ranking per sempre**, indipendentemente da quale `ts` porta — un evento datato nel futuro
inquina la quota storica ADESSO, non "quando arriva quella data". Non esiste, oggi, alcun modo di:
- marcare una riga come sintetica/di test e farla escludere automaticamente
  dall'aggregazione (nessun campo `sintetico`/`is_test` in `BehaviorEvent`/`behavior_event`);
- limitare `conteggio_per_esperienza()` a una finestra recente: non c'è retention né a livello di
  query né a livello di schema (nessun job di pulizia/scadenza).

Su un dataset piccolo e in fase iniziale (come questo), anche una manciata di eventi sintetici non
ripuliti sposta il ranking reale in modo misurabile — non è un problema che si manifesta solo a
grande scala. L'unica difesa esistente oggi è disciplina manuale: cancellare esplicitamente e
SUBITO ogni evento sintetico con uno strumento dedicato (`scripts/pulisci_eventi_prefisso.py`), non
una garanzia strutturale del sistema.

### Cosa servirebbe per chiudere il buco (proposte, NON implementate ora)

1. **Un flag `sintetico`/`is_test`** su `BehaviorEvent` (`packages/contracts`, campo nuovo con
   default `False`, retro-compatibile) e sulla colonna corrispondente di `behavior_event`
   (`00_events_schema.sql`), escluso per costruzione da `conteggio_per_esperienza()`
   (`WHERE sintetico = false`) e da qualunque altro consumatore aggregato presente o futuro.
   Limite di questa strada: sposta l'onere da "ricordarsi di pulire" a "ricordarsi di marcare" —
   non lo elimina strutturalmente, solo lo rende meno distruttivo se dimenticato (la riga resta,
   ma esclusa dall'aggregazione).
2. **Una finestra temporale nella query di quota storica** (es. `WHERE ts >= now() - INTERVAL
   '...'`), che limiterebbe il danno di QUALUNQUE riga anomala — sintetica o reale ma vecchia — a
   una finestra finita invece che "per sempre". Cambierebbe anche la semantica di prodotto del
   Recommender (la quota storica diventerebbe "storia recente", non "tutta la storia mai
   registrata"): è una decisione da negoziare col committente, non solo un dettaglio tecnico —
   stessa classe di decisione già rimandata per `tasso_ritorno` sopra in questo file ("quanto
   indietro guardare").
3. Le due proposte sono ortogonali, non alternative: la (1) risolve "sintetico vs reale", la (2)
   risolve "vecchio vs recente"; un sistema maturo probabilmente le vuole entrambe.

### Decisione

Non implementato ora. Finché non esiste (1) o (2), qualunque evento inserito manualmente in
`behavior_event` per una verifica contro Neon/Aura reali — questa o una wave futura — deve essere
ripulito ESPLICITAMENTE e SUBITO dopo la prova (`scripts/pulisci_eventi_prefisso.py` o equivalente),
mai rimandato con la motivazione "tanto è nel futuro" o "tanto sono pochi eventi": entrambe le
attenuanti valgono per `intelligence_index`, NESSUNA delle due vale per il Recommender. Questo
limite va riletto prima di:
- generare un altro batch di eventi sintetici contro Neon reale per qualunque verifica manuale
  futura (stessa disciplina di pulizia immediata, non posticipabile);
- decidere se investire in (1) e/o (2) — a quel punto rileggere anche la voce `tasso_ritorno` sopra,
  stessa classe di decisione ("quanto indietro guardare").
