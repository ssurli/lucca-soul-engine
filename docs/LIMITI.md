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

---

## Il BFF ha CORS aperto (`allow_origins="*"`) su `/dashboard/*` — va ristretto prima di un deploy pubblico

**Introdotto:** Wave 4. **Componente:** `services/api` (`api.main.dashboard_readonly_cors`).

Questa NON è una nota estetica: è un cambio di postura di sicurezza del BFF, e va trattato come
tale da chiunque tocchi questo file in futuro.

### Cosa è garantito oggi

Per far funzionare `scripts/dashboard_viewer.html` (pagina statica, senza build, aperta con un
doppio clic da `file://` — origin `"null"` per il browser — mentre il BFF gira in locale), è stato
aggiunto un middleware scritto a mano (non `fastapi.middleware.cors.CORSMiddleware` di libreria,
che si applicherebbe all'INTERA app senza scoping per path) che apre `Access-Control-Allow-Origin:
*` SOLO quando **entrambe** le condizioni valgono:
- il metodo è `GET` (o `OPTIONS` di preflight per una `GET`);
- il path inizia per `/dashboard/`.

Verificato con richieste HTTP reali (`Origin: null`, sia `GET` che `OPTIONS` di preflight): la
risposta ha l'intestazione CORS su `GET /dashboard/index`/`GET /dashboard/flows`, e NE È PRIVA su
`GET /health`, `GET /contracts/version`, `GET /memory/{place_id}` e su qualunque `POST` (`/memory`,
`/booking`, `/events`, `/session/onboarding`, `/itinerary*`) — questi ultimi restano IRRAGGIUNGIBILI
da una pagina web di origine diversa, wildcard o no. Un browser applica CORS SOLO alle richieste
che parte lui stesso: questo non ha alcun effetto sull'app Flutter (client HTTP nativo) né su
chiamate server-to-server.

### Cosa NON è garantito

`allow_origins="*"` significa letteralmente "qualunque sito web che il browser dell'utente visita
può leggere `GET /dashboard/*` di QUESTO BFF, se l'utente ha anche questo BFF raggiungibile in
rete (es. `localhost` durante lo sviluppo, ma anche una porta esposta per errore, o un domani un
deploy pubblico)". Oggi il rischio pratico è basso: `/dashboard/*` espone solo dati già aggregati e
gated a k=10 (mai PII), e in locale il "sito web arbitrario" nello stesso browser è comunque un
rischio marginale rispetto a un dev in ambiente controllato. Ma **il wildcard non sa distinguere
"BFF locale di sviluppo" da "BFF esposto pubblicamente"**: è una proprietà del codice, non
dell'ambiente in cui gira oggi. Se questo servizio finisce online così com'è, `allow_origins="*"`
resta attivo esattamente allo stesso modo, e a quel punto permette a QUALUNQUE sito di terzi di
leggere gli aggregati pubblici del Comune tramite il browser di un visitatore ignaro — non uno
scenario catastrofico (i dati sono già aggregati e pensati per essere pubblici), ma comunque una
postura che nessuno ha deciso esplicitamente per un contesto di produzione: è nata per far
funzionare uno strumento locale, non è mai stata valutata per un deploy pubblico.

### Cosa servirebbe per chiudere il buco

- **Restringere `Access-Control-Allow-Origin` a origin specifici**, non `"*"`, nel momento in cui
  il BFF smette di essere "solo locale": una lista esplicita (dominio della dashboard Comune
  ufficiale, se/quando esiste) invece del wildcard — richiede una decisione di deploy (quali
  origin sono legittimi), non solo un cambio di codice.
- In alternativa, **se il viewer HTML locale non serve più in quel contesto** (es. sostituito
  definitivamente dall'app Flutter compilata), il modo più semplice di chiudere il buco è
  rimuovere `dashboard_readonly_cors` del tutto: nessun endpoint applicativo dell'app Flutter (un
  client nativo, non un browser) ne ha mai avuto bisogno.
- Qualunque delle due scelte richiede una decisione umana esplicita al momento del deploy — questo
  file esiste apposta perché quella decisione non venga presa per omissione (il wildcard
  "funzionava in locale, non l'ho più guardato").

### Decisione

Non ristretto ora: `allow_origins="*"` resta per uno strumento di sviluppo locale
(`scripts/dashboard_viewer.html`), scoped comunque a `GET`/`OPTIONS` su `/dashboard/*` (mai
l'intera app, mai i path di scrittura). Questo limite va riletto — non ignorato — prima di:
- esporre `services/api` (il BFF) su una rete diversa da `localhost`/una rete di sviluppo fidata,
  per qualunque motivo (demo pubblica, staging raggiungibile da internet, produzione);
- rimuovere `scripts/dashboard_viewer.html` dal repo (a quel punto il middleware non ha più un
  consumatore: valutare se rimuoverlo insieme, non lasciarlo "per sicurezza" senza uno scopo).

---

## Il White Paper promette "gestisce disponibilità" nel Marketplace; il codice Wave 3a non lo faceva

**Introdotto:** Wave 3a. **Componente:** `services/marketplace`. **Trovato:** verifica manuale
(2026-07-22/23) prima di onboardare botteghe reali per il Living Lab.

### Cosa diceva il materiale di pitch

Il White Paper (`docs/LUCCA_SOUL_LAB_Portfolio_v1.0.pdf`, pagina Marketplace) promette
esplicitamente: *"La piattaforma mette in rete chi crea cultura e **gestisce disponibilità**,
prenotazioni, pagamenti, recensioni e statistiche."* — "gestisce disponibilità" è una capacità
dichiarata del concept, non una frase generica.

### Cosa faceva il codice, prima di questa correzione

Niente. `marketplace.service.request_booking` accettava `BookingRequest.quando` (un `datetime`
libero) e non applicava ALCUNA validazione contro di esso: nessun controllo di orario, nessuna
verifica di conflitto/doppia prenotazione sullo stesso slot, nessuna gestione di capienza.
L'unico gate era — ed è tuttora — un booleano tutto-o-niente, `ExperienceNode.prenotabile`
(prenotabile in assoluto, mai per fascia/giorno). Non era un'assenza silenziosa: era uno scarto
misurabile tra la narrativa del pitch (che già dichiara "gestisce disponibilità") e il codice
Wave 3a effettivamente costruito.

### Cosa è stato chiuso ora (validazione MINIMA, non il calendario completo)

`ExperienceNode.orari_apertura` (fasce settimanali RICORRENTI, `FasciaApertura`:
`giorno_settimana` + `apertura` + `chiusura`), `Signal.giorno_settimana` (opzionale, mai
fabbricato), e la funzione pura condivisa `contracts.rientra_in_orario` — riusata IDENTICA da
`experience_engine.rules.passa_filtri_duri` (quinto filtro duro sull'itinerario) e da
`marketplace.service.request_booking` (rifiuta con `ExperienceNotAvailableError` PRIMA di
persistere, stesso schema di `ExperienceNotBookableError`). Lista `orari_apertura` vuota o
`giorno_settimana` assente = nessun vincolo, mai un'esclusione fabbricata: comportamento
invariato per ogni esperienza del seed di oggi, che non dichiara ancora orari.

### Cosa resta fuori scope, deliberatamente — vedi la voce successiva

Capienza (posti disponibili per slot), conflitti tra due prenotazioni sullo stesso slot,
eccezioni calendariali e festività: NON sono stati fabbricati ora. Vedi la voce successiva in
questo file per il dettaglio e il perché.

### Decisione

Il gate "gestisce disponibilità" del pitch è ora PARZIALMENTE vero: orari settimanali sì,
capienza/conflitti/eccezioni no. Questo limite va riletto prima di:
- presentare il Marketplace come "gestisce disponibilità" senza qualificare esplicitamente che
  oggi significa "fasce settimanali ricorrenti", non un calendario completo;
- onboardare una bottega reale il cui modello di disponibilità non è rappresentabile con fasce
  settimanali ricorrenti (turni irregolari, chiusure straordinarie frequenti) — a quel punto
  rileggere anche la voce successiva.

---

## Orari di apertura: capienza, conflitti di slot ed eccezioni calendariali restano fuori scope

**Introdotto:** Wave 3a+. **Componente:** `packages/contracts`, `services/marketplace`,
`services/experience-engine`.

### Cosa è garantito oggi

`FasciaApertura` (fasce settimanali ricorrenti) e la validazione minima descritta nella voce
precedente: un'esperienza dichiara QUANDO è aperta nella settimana tipo, e sia la composizione
dell'itinerario sia la prenotazione rispettano quel vincolo, con un solo modello
(`rientra_in_orario`) condiviso tra i due usi.

### Cosa NON è garantito

- **Capienza**: nessun conteggio di posti disponibili per slot. Due, dieci, cento persone
  possono richiedere lo stesso identico `quando` per la stessa esperienza: tutte vengono accolte
  in stato `RICHIESTA` (poi eventualmente confermate a mano da chi gestisce la bottega). Non
  esiste un numero massimo dichiarato né un contatore che lo faccia rispettare.
- **Conflitti di slot**: nessuna verifica che due prenotazioni sullo stesso `experience_id` allo
  stesso `quando` (o in una finestra sovrapposta, se l'esperienza dura più del singolo istante)
  siano compatibili tra loro. `request_booking` valuta ogni richiesta in isolamento.
- **Eccezioni calendariali e festività**: `FasciaApertura` è RICORRENTE per costruzione (un
  giorno della settimana, non una data): non esiste un modo di dichiarare "chiuso il 25
  dicembre" o "chiuso per ferie dal 10 al 20 agosto" senza disattivare l'intera fascia
  settimanale che coprirebbe anche i giorni non eccezionali.
- **Turni a cavallo di mezzanotte**: `FasciaApertura` richiede `chiusura > apertura` nello
  stesso giorno (vincolo di contratto, `model_validator`): un turno reale 22:00->02:00 non è
  rappresentabile con una singola fascia.

### Trovato da un giro DEDICATO di ethics-guardian (2026-07-24), non da un'autovalutazione

Un'autovalutazione dell'implementatore aveva dichiarato questo lavoro "PASS". Un giro separato,
esplicitamente adversariale, ha trovato quattro cose che l'implementatore non aveva visto — lo
stesso ruolo che il gate ha già avuto in Wave 1 (attribuzione mescolata nello score) e Wave 3b/4
(gate mancante su `contributi_memoria`; fuga del conteggio esatto in `motivo_indisponibilita`).

1. **BUG REALE, CORRETTO in questa stessa verifica**: `experience_engine.engine.
   _migliore_alternativa` (usata da `adapt_itinerary` per sostituire una tappa su pioggia/
   affollamento) aveva una sua logica di filtro scritta a mano — non chiamava
   `rules.passa_filtri_duri` né `contracts.rientra_in_orario`. Una riscrittura per pioggia
   poteva quindi sostituire una tappa con un'esperienza CHIUSA in quel momento, anche se la
   composizione iniziale la escludeva correttamente. Riprodotto con uno scenario minimo
   (tappa all'aperto sotto pioggia, unica alternativa al chiuso aperta solo 20:00-23:00,
   segnale delle 10:00): la sostituzione avveniva. Corretto aggiungendo lo stesso controllo
   (`rientra_in_orario`) a `_migliore_alternativa`; test di regressione permanente
   `test_adapt_non_sostituisce_con_unalternativa_chiusa_in_quellorario`
   (`services/experience-engine/tests/test_engine.py`). Riverificato: l'intera suite
   combinata (`tests/` + ogni `services/*/tests`) resta verde dopo la correzione.
2. **GAP PRE-ESISTENTE, TROVATO INCIDENTALMENTE, NON CORRETTO qui (fuori scope di questa
   verifica)**: la stessa `_migliore_alternativa` non verifica NEMMENO
   `partner_abbonamento_attivo` — un partner con abbonamento non attivo, escluso sempre in
   composizione iniziale da `passa_filtri_duri` (Wave 3a), può quindi essere reintrodotto
   come alternativa durante un adattamento. Non è stato introdotto da questo lavoro sugli
   orari (esisteva già da quando è stato aggiunto il filtro sull'abbonamento in Wave 3a, mai
   esteso ad `adapt`): segnalato qui perché "va tracciato, non lasciato implicito", non
   corretto perché la richiesta di questa verifica riguardava gli orari, non l'abbonamento.
3. **LIMITE DI PROGETTAZIONE, non un bug isolato**: `passa_filtri_duri` (e quindi anche il
   controllo sugli orari) valuta OGNI candidato contro un SINGOLO istante — `signal.ora`/
   `signal.giorno_settimana` al momento in cui la composizione INIZIA — non contro l'orario
   effettivo in cui quella tappa verrebbe visitata più avanti nella sequenza (che
   `_costruisci_stops` calcola solo DOPO aver scelto e ordinato le tappe). Su un itinerario
   di più ore, questo può escludere per errore un'esperienza che aprirebbe in tempo per
   quando l'itinerario la raggiungerebbe, o includerne una che nel frattempo avrebbe già
   chiuso. Non è un problema NUOVO introdotto dagli orari: lo stesso limite vale già per il
   filtro sull'affollamento (`signal.affollamento`, valutato anch'esso su un solo istante) —
   ma è molto più visibile per gli orari, dove "aperto/chiuso" cambia in modo netto nell'arco
   di poche ore, mentre l'affollamento cambia con più continuità. Risolverlo davvero
   richiederebbe filtrare/schedulare in un unico passo (sapere l'orario di visita PRIMA di
   escludere un candidato), un cambio di architettura della pipeline di composizione, non un
   aggiustamento locale.
   **Nota (finestra degli `:Evento` promossi):** la stessa logica a istante singolo vale per
   `Signal.data`, ma a granularità di GIORNO: la finestra (che ragiona in giorni) è valutata
   sulla data d'inizio della composizione; conta solo per un itinerario che scavalca la
   mezzanotte. Dettaglio nella voce sulla finestra temporale, in fondo a questo file.
4. **ASSUNZIONE DI INTEGRITÀ NON VERIFICATA, della stessa famiglia del limite su
   `POST /events`** (voce successiva in questo file): `orari_apertura` è interamente
   auto-dichiarato da chi cura il grafo/la bottega, senza alcuna verifica. Non è un problema
   NUOVO (la stessa fiducia non verificata vale già per `accessibile`, `al_chiuso`,
   `prenotabile`) ma ha un incentivo asimmetrico specifico: dichiarare orari più ampi del
   vero PUÒ SOLO aumentare le occasioni in cui un'esperienza è considerata (mai diminuirle,
   perché il campo esclude soltanto, non assegna punteggio) — quindi l'unico incentivo a
   mentire va in una direzione sola, "dichiarati sempre aperto". Nessuna verifica, nessuna
   conseguenza tracciata per una dichiarazione falsa.

### Cosa servirebbe per chiudere questi buchi (proposte, NON implementate ora)

1. **Capienza**: un campo `capienza: int | None` su `ExperienceNode` o su una nuova entità
   "slot" collegata alla prenotazione, più un conteggio delle prenotazioni `RICHIESTA`/
   `CONFERMATA` già esistenti per lo stesso `quando` prima di accettarne una nuova. Decisione
   da prendere: la capienza è per ESPERIENZA (stesso numero ogni volta che si tiene) o per
   OCCORRENZA specifica (una volta con più posti, un'altra con meno)?
2. **Conflitti di slot**: richiede prima la capienza (senza un numero massimo, "conflitto" non è
   definibile) e una decisione su cosa succede quando lo slot è pieno — la richiesta viene
   rifiutata subito (`ExperienceNotAvailableError` esteso, o un nuovo errore dedicato?) o messa
   in lista d'attesa?
3. **Eccezioni calendariali**: un secondo modello, es. `EccezioneApertura {data: date, chiuso:
   bool, apertura: time | None, chiusura: time | None}`, che sovrascrive `FasciaApertura` per una
   data specifica — verificato PRIMA della fascia ricorrente in `rientra_in_orario`. Aggiunge una
   seconda lista da mantenere per ogni esperienza: vale la complessità solo se una bottega reale
   ha davvero bisogno di dichiarare chiusure straordinarie oltre al pattern settimanale.
4. **Turni a cavallo di mezzanotte**: o si accettano due fasce (es. 22:00-23:59 + 00:00-02:00 il
   giorno dopo, un'approssimazione già disponibile con il modello attuale) o si estende
   `FasciaApertura` con un giorno "esteso" — una scelta di modellazione, non solo un fix.
5. **`partner_abbonamento_attivo` in `_migliore_alternativa`** (trovato al punto 2 sopra):
   aggiungere lo stesso controllo già presente in `passa_filtri_duri`. A differenza degli
   orari (appena corretti in questa verifica), non è stato fatto qui perché fuori scope
   della richiesta — ma è la correzione più economica di questa lista: stesso pattern già
   scritto, un'unica riga in più.
6. **Filtro consapevole dell'orario di visita effettivo** (trovato al punto 3 sopra):
   richiede di invertire l'ordine attuale "filtra poi schedula" in qualcosa che sappia, PRIMA
   di escludere un candidato, a che ora verrebbe effettivamente visitato — un cambio di
   architettura della pipeline di `compose_itinerary`, non un aggiustamento locale. Vale la
   pena solo se un itinerario reale, di più ore, mostra davvero il problema (un'esperienza
   esclusa che sarebbe stata aperta in tempo, o inclusa quando ormai avrebbe già chiuso).

### Decisione

Nessuno di questi sei punti è implementato ora. I primi quattro, DELIBERATAMENTE: costruirli
senza una bottega reale che ne dichiari il bisogno specifico (quale capienza? quali eccezioni?
quali turni notturni?) sarebbe fabbricare una scelta di modellazione arbitraria — lo stesso
principio già applicato in questo file a `tasso_ritorno`/`nuovi_percorsi`. Il quinto e il sesto,
perché fuori dallo scope della verifica che li ha trovati (rispettivamente: l'abbonamento
partner, non gli orari; un cambio di architettura, non un fix locale) — non perché siano meno
reali dei primi quattro. Questo limite va riletto quando il
Living Lab onboarda la prima bottega reale che dichiara uno di questi bisogni (per i primi
quattro punti) o prima di estendere ulteriormente `adapt_itinerary`/la pipeline di composizione
(per il quinto e il sesto) — a quel punto la richiesta reale guida quale delle sei proposte (o
quale variante) implementare, non il contrario.

---

## `POST /events` non ha alcuna prova di presenza, autenticazione o rate limiting — prerequisito del Living Lab

**Introdotto:** Wave 3b. **Componente:** `services/api` (`POST /events`), `services/recommender`.
**Trovato:** verifica manuale (2026-07-23), dopo che il committente ha inviato 10 eventi `stop`
fabbricati dal terminale contro il BFF reale senza che il sistema rilevasse o rifiutasse nulla
(stesso meccanismo già usato, con pulizia esplicita, per la prova del gate k=10 in Wave 4 —
vedi la voce precedente su `scripts/pulisci_eventi_prefisso.py`).

### Cosa è garantito oggi

`BehaviorEvent` è validato SOLO nella FORMA (Pydantic: `person_id: str`, `tipo:
Literal["view","stop","photo","booking","review","skip","memory_contrib"]`, `experience_id:
str`, `ts: datetime`), non nel CONTENUTO. `api.main.submit_behavior_event` fa esattamente
`repo.record(event)` — nessun controllo aggiuntivo. Nessuna PII: `person_id` resta uno
pseudonimo, mai loggato.

### Cosa NON è garantito — i quattro punti richiesti, verificati uno per uno

1. **Nessun meccanismo di prova di presenza, in nessuna forma.** Cercato in tutto il repo
   (contratti, grafo, BFF, recommender, app Flutter) e nel White Paper
   (`docs/LUCCA_SOUL_LAB_Portfolio_v1.0.pdf`): zero occorrenze di GPS, check-in, QR,
   conferma operatore, geolocalizzazione, beacon, NFC. `services/recommender/README.md`
   DOCUMENTA esplicitamente l'assunzione su cui poggia l'intero schema di pesi
   (`PESI_TIPO`): `tipo="stop"` vale il doppio di `view` perché significa "presenza fisica
   reale e prolungata in quel luogo" — un'assunzione filosofica, verificata da NULLA nel
   codice.
2. **Nessun codice, nemmeno abbozzato, genera eventi lato app.** `apps/lucca_soul_app` non ha
   ALCUN riferimento a "events"/"BehaviorEvent" in nessun file: `BffClient` non ha un metodo
   per `POST /events`. Le uniche righe mai scritte in `behavior_event` in questa
   collaborazione sono arrivate da chiamate HTTP dirette (terminale/script), mai dall'app —
   l'unico modo che esiste OGGI per generare un evento è bypassare completamente l'app.
3. **Nessun modo per registrare un luogo NON presente nel grafo — nessun percorso di
   scoperta reale.** `BehaviorEvent.experience_id` non è validato contro il catalogo al
   momento dell'invio (nessun vincolo di chiave esterna a livello di contratto o di
   endpoint): un id sconosciuto non genera un errore, viene silenziosamente IGNORATO più
   tardi in aggregazione (`intelligence_index.dashboard.celle_flusso`: "un `experience_id`
   assente dal catalogo non è mappabile: ignorato"). `MemoryContribution.riguarda` PUÒ
   referenziare un id inesistente al momento del conferimento (per design: il Cittadino può
   sempre conferire, anche con Aura in pausa) — ma quel contributo non raggiungerà MAI
   `curato=True` (la curatela verifica i target, `InvalidTargetsError`), quindi non
   comparirà mai via `GET /memory/{place_id}`: un vicolo cieco permanente, non un percorso
   di scoperta. L'unico modo in cui un luogo realmente nuovo diventa un nodo di prima classe
   oggi è il seed versionato (`graph.seed_lucca`), scritto a mano da chi cura il grafo — mai
   a runtime, mai da un contributo di campo.
4. **Nessuna autenticazione, nessun rate limiting.** Verificato per ricerca testuale:
   zero occorrenze di auth/Authorization/api_key/rate limit in tutto `services/api`;
   l'unico middleware registrato sull'app è quello CORS (Wave 4, scoped a `GET
   /dashboard/*`, niente a che vedere con `/events`). Chiunque raggiunga il BFF in rete può
   inviare un numero illimitato di eventi fabbricati, con qualunque `person_id` a piacere.

Il punto 4 AGGRAVA il limite già documentato sopra in questo file ("`behavior_event` non
distingue eventi reali da sintetici/di test, e non ha retention"): lì il problema era che un
evento GENUINO di verifica inquinava il ranking senza scadenza temporale nel Recommender; qui
il problema è A MONTE — non c'è nemmeno un modo di distinguere un evento genuino da uno
fabbricato dal nulla, e chiunque può generarne quanti ne vuole, senza friction, senza
autenticazione, senza limite di frequenza. Le due lacune si compongono: un solo abuso non
autenticato altera il ranking reale per sempre, non per una finestra limitata.

### Cosa servirebbe (proposte, NON implementate — richiesta esplicita di non farlo ora)

1. **Autenticazione minima su `POST /events`**: anche solo una chiave per client noto (l'app
   ufficiale), non un sistema di identità completo — sposta il rischio da "chiunque in rete"
   a "chiunque abbia la chiave dell'app": un primo filtro, non una soluzione contro un abuso
   deliberato che estrae la chiave dall'app stessa.
2. **Rate limiting** per IP e/o per pseudonimo (es. N eventi/minuto): riduce il danno di un
   abuso automatizzato ingenuo, non lo elimina (un pseudonimo diverso ad ogni richiesta lo
   aggira facilmente).
3. **Un segnale minimo di presenza reale**: legare l'evento a qualcosa che richieda essere
   fisicamente nel luogo — un QR affisso in loco, un check-in geolocalizzato (richiede la
   posizione del dispositivo: un dato sensibile, da trattare coerentemente con "niente
   storage di PII sul device" già vincolante per il client Flutter), o una conferma
   dell'operatore/bottega (il più debole tecnicamente ma il più coerente con un pilota
   piccolo e supervisionato). Tre modelli diversi, costi e implicazioni di privacy diversi:
   una decisione di prodotto prima che tecnica, non una scelta tecnica isolata.
4. **Un percorso di scoperta per un luogo nuovo**: oggi non esiste in nessuna forma.
   Servirebbe un flusso esplicito (es. una proposta di nuovo nodo che un umano/la curatela
   approva prima che entri nel grafo) — non un tipo di `BehaviorEvent`/`MemoryContribution`
   esistente riadattato: un luogo non ancora nel grafo non ha nemmeno un `place_id` a cui
   agganciare un contributo.

### Decisione

Nessuno dei quattro punti è implementato — non era la richiesta di questa verifica. Ma è un
PREREQUISITO del Living Lab, non solo un miglioramento futuro rimandabile: il momento in cui
persone reali (non solo chi verifica manualmente da terminale, con la disciplina di ripulire
subito dopo) iniziano a generare eventi è esattamente il momento in cui l'assenza di TUTTI E
QUATTRO questi controlli smette di essere un rischio teorico. Questo limite va riletto — non
ignorato — prima di:
- aprire `POST /events` a un pubblico reale, anche in un pilota piccolo e supervisionato;
- decidere quale delle quattro proposte sopra (o quale combinazione) implementare — ciascuna
  ha un costo e un'implicazione di privacy diversi, non sono intercambiabili né equivalenti;
- fidarsi di `distribuzione_flussi`/di qualunque indicatore dell'Urban Intelligence Index
  derivato da eventi non verificati, in un contesto dove il risultato informa decisioni reali
  di un'amministrazione (CLAUDE.md: "le Smart City raccolgono dati, le città intelligenti
  generano significato" — un significato costruito su eventi non verificati è un significato
  fabbricato, non generato).

---

## Livello FLUTTUANTE attivato (`Signal.eventi_attivi`): cosa resta fuori scope

**Introdotto:** Wave 1 (campo dormiente nel contratto), attivato Wave 3a+. **Componente:**
`packages/contracts`, `services/experience-engine`.

### Cosa è garantito oggi

`Signal.eventi_attivi` (era `list[str]`, mai letto da nessuna logica — verificato prima di
attivarlo, non un campo nuovo) ora porta `list[SegnaleFluttuante]`: qualcosa che accade ORA e
domani non c'è (un violinista in piazza), diverso dal livello "programmato" (vedi sotto).
`experience_engine.engine.compose_itinerary` aggiunge, IN CODA e mai in sostituzione, le tappe
fluttuanti pertinenti (coerenti col tema di almeno una dimensione di profilo con peso > 0, MAI
un segnale commerciale — `contracts.segnale_fluttuante_ammissibile`, filtro duro, nessuna
eccezione), rispettando il budget di tempo residuo. Non tocca `calcola_score`: nessuna
esperienza permanente cambia punteggio in base a `eventi_attivi` (test comportamentale
dedicato, bit-identico con e senza segnali attivi). Namespace dell'`experience_id` fittizio
(`fluttuante-<id>`) separato da quello reale (`exp-...`): nessuna collisione strutturale con
un'esperienza permanente.

### Cosa NON è garantito — deliberatamente, per esplicita richiesta di non fabbricare

- **Il livello "programmato"** (`:Evento` come nodo del grafo, con data e organizzatore — la
  stessa etichetta riservata ma mai popolata già documentata altrove in questo file) resta
  fuori scope: altra cosa, altra wave. Il livello fluttuante non lo sostituisce né lo anticipa
  — sono due meccanismi diversi per due nozioni diverse di "evento" (istantaneo vs
  calendarizzato).
- **La PROMOZIONE** (un segnale fluttuante che si ripete più volte, nello stesso luogo, con lo
  stesso tema, diventa un'esperienza permanente o un `:Evento` programmato) NON esiste in
  nessuna forma. Richiederebbe una coda di curatela — verifica umana prima che un pattern
  ricorrente diventi un'entità di prima classe nel grafo — che oggi non esiste per questo
  scopo (la curatela di Urban Memory, `urban_memory.service`, verifica CONTRIBUTI a nodi già
  esistenti, non promuove segnali a nodi nuovi: un problema diverso). **Evoluzione prevista,
  non implementata**: quando/se serve, andrebbe costruita come un nuovo flusso di curatela
  dedicato, con una soglia esplicita da negoziare ("quante ripetizioni bastano?", la stessa
  classe di decisione già rimandata per `tasso_ritorno` — vedi sopra in questo file).
- **Come i segnali fluttuanti entrano nel sistema nel mondo reale** (chi segnala il violinista,
  con quale prova che sia successo davvero) NON era stato costruito qui: era ESATTAMENTE il
  problema già documentato nella voce precedente di questo file (`POST /events` senza prova di
  presenza, autenticazione, rate limiting). Questa attivazione ASSUMEVA che
  `Signal.eventi_attivi` arrivasse già popolato onestamente nella richiesta — non costruiva, e
  non doveva costruire, il canale d'ingresso.
  **Aggiornamento (Fase 3, fondazione persistenza+ledger)**: `Signal.eventi_attivi` ora ha
  una sorgente reale — `SegnaleFluttuante` persiste in Postgres e il server lo fetcha
  autorevolmente ad ogni `POST /itinerary`, sovrascrivendo sempre quanto mandato dal client
  (proprietà di sicurezza verificata). Ma il canale d'INGRESSO resta un percorso
  RISTRETTO/FIDATO provvisorio — `python -m urban_memory.submit_signal`, una CLI, stesso
  principio di `link_to_graph` chiamato solo da `verify.py` — MAI un endpoint HTTP pubblico.
  Il problema descritto sopra (chi può generare un segnale, con quale prova) resta quindi
  APERTO nella sua forma originale per chiunque non abbia accesso alla CLI: solo il
  "come si scrive" è cambiato (persistenza reale invece di un campo sempre vuoto), non il
  "chi può scrivere" — quella resta la fase-fiducia, non ancora affrontata.
- **`SegnaleFluttuante.non_commerciale` è interamente auto-dichiarato, senza alcuna verifica**
  — stessa famiglia di fiducia non verificata già accettata per `ExperienceNode.orari_apertura`
  (vedi sopra in questo file) e per `POST /events`: nessun controllo impedisce a chi genera un
  segnale di dichiarare falsamente `non_commerciale=True` per un'attività che in realtà lo è.
  Il filtro duro (`segnale_fluttuante_ammissibile`) protegge SOLO contro un segnale onestamente
  marcato commerciale, non contro uno mentito. Trovato durante un giro dedicato di
  ethics-guardian su questa stessa funzionalità (vedi changelog in `docs/BUILD_PLAN.md`).
  **Aggiornamento (Fase 3, promozione + consumo degli `:Evento`) — TROVATO e POI CHIUSO,
  entrambi da giri DEDICATI di `ethics-guardian`, non un'autovalutazione.** Quando il consumo
  degli `:Evento` promossi in un itinerario è stato costruito, un giro dedicato ha verificato
  che questo varco non si fermava al singolo segnale fluttuante: attraversava l'intera
  pipeline di promozione senza mai essere richiuso. Verificato codice alla mano, PRIMA del
  fix: `non_commerciale` non sopravviveva nemmeno al deposito nel ledger
  (`urban_memory.traccia_repository.Traccia` porta solo `place_id`/`temi`/`creato_il` —
  nessun campo commerciale); `urban_memory.canale_fluttuante.sweep_and_fetch_active` depositava
  una traccia per OGNI segnale scaduto, senza rifiltrare per commerciale;
  `urban_memory.ricorrenza.rileva_candidati` non leggeva né scriveva nulla sul carattere
  commerciale (il dato era già perso, non solo ignorato); la CLI di curatela
  (`urban_memory.curatela_pattern._stampa_candidato`) mostrava al Promotore SOLO `place_id`,
  `temi`, occorrenze, cadenza e coefficiente di variazione — nessuna informazione sul
  carattere commerciale era disponibile da mostrare a quel punto, quindi la revisione umana
  alla promozione non poteva ri-verificarlo, non perché non lo facesse ma perché il dato non
  c'era più. Un pattern commerciale (auto-dichiarato onestamente non-commerciale per errore, o
  mentito fin dall'inizio) che si ripeteva abbastanza volte poteva quindi diventare un
  `:Evento` promosso senza che NESSUNO dei due controlli teoricamente esistenti
  (auto-dichiarazione del segnale, curatela umana del pattern) lo intercettasse mai. **Prima
  della Fase 3 "consumo degli `:Evento` promossi" questo varco era teorico**: nessun
  consumatore leggeva mai un `:Evento` in un itinerario — il consumo lo ha reso concretamente
  raggiungibile da un visitatore reale, sotto forma di una tappa "contesto sul luogo"
  (`experience_engine.engine._aggiungi_tappe_eventi_promossi`), esattamente la superficie che
  il principio "nessuno spazio è acquistabile" (CLAUDE.md) deve proteggere.

  **CHIUSO, non solo dichiarato**: su richiesta esplicita del committente, un secondo giro
  dedicato ha risalito l'intera catena e confermato il verdetto "GARANZIA NON PRESERVATA",
  indicando il punto più economico per il fix. Corretto alla RADICE, non sul consumo (nessuna
  ridisegnazione del ledger/della curatela è servita): `urban_memory.canale_fluttuante.
  sweep_and_fetch_active` ora scarta un segnale non ammissibile
  (`contracts.segnale_fluttuante_ammissibile` — la STESSA funzione già usata per il consumo
  diretto dei fluttuanti, nessuna seconda logica inventata) PRIMA del deposito della
  `Traccia`: un segnale commerciale scade comunque (`attivo → expired`, invariato, per audit),
  ma non genera mai più una traccia, quindi non può mai maturare in un pattern ricorrente né
  in un `:Evento` promosso. Un terzo giro, indipendente, ha riverificato punto per punto
  (ordine del controllo rispetto al deposito, non-alterazione della transizione `expired`,
  non-interferenza con `submit_signal.py`, assenza di un secondo scrittore del ledger che
  bypassi il filtro — grep su tutti i chiamanti di `TracciaRepository.deposita` in codice di
  produzione: uno solo, ora protetto) e confermato **"GARANZIA ORA PRESERVATA"**.

  **Cosa resta, e non è chiuso da questo fix — lo stesso limite di sempre, non uno nuovo**:
  l'auto-dichiarazione di `non_commerciale=True` resta interamente fidata — un segnale che
  MENTE fin dall'inizio (dichiara `non_commerciale=True` per un'attività che in realtà non lo
  è) supera il filtro esattamente come lo superava prima, perché il filtro verifica il campo
  dichiarato, non la realtà sottostante. Nessun fix di questa voce può chiudere quel limite
  (richiederebbe un meccanismo di verifica indipendente della dichiarazione, non un filtro sul
  dato che il segnale stesso porta) — resta esattamente dove il primo paragrafo di questa
  voce lo colloca.
- **`SegnaleFluttuante.temi` è ALTRETTANTO auto-dichiarato**, e il vettore di gioco è diverso da
  quello sul commerciale: non "farsi passare per non commerciale" ma "dichiarare temi larghi
  (es. sempre `arte`, il gruppo più popolato) per massimizzare a chi il segnale risulta
  pertinente" — anche per un segnale onestamente non commerciale. Nessun controllo lo impedisce.
  Trovato nello stesso giro di ethics-guardian, distinto dal punto sopra (quello riguarda SE il
  segnale compare; questo riguarda A CHI compare).
- **`adapt_itinerary` non rivaluta MAI i segnali fluttuanti**: due conseguenze, non correggibili
  senza uscire dallo scope di questa attivazione. (1) Un segnale fluttuante nuovo, apparso dopo
  la composizione iniziale, non entra MAI in un itinerario già composto — solo un successivo
  `compose_itinerary` da zero lo vedrebbe. (2) Una tappa fluttuante già aggiunta è STRUTTURALMENTE
  immune a pioggia/affollamento in un adapt successivo (il meccanismo di fallback per tappe
  "sconosciute", `_stub_da_stop`, la forza sempre `al_chiuso=True`): un violinista all'aperto
  aggiunto prima che iniziasse a piovere resta in programma anche sotto la pioggia, mai
  riscritto verso un'alternativa al chiuso. Coerente con "si infila senza togliere nulla" per
  la sola aggiunta iniziale, ma non è una garanzia che la tappa resti sensata per tutta la
  giornata.
- **Nessun limite al numero di tappe fluttuanti aggiunte**: finché il budget di tempo lo
  consente, TUTTI i segnali pertinenti vengono aggiunti, in ordine di arrivo. Non è stato
  fabbricato un tetto arbitrario (es. "massimo 2 al giorno") senza un caso reale che ne mostri
  il bisogno — stesso principio già applicato altrove in questo file.
- **Nessun filtro di affollamento/accessibilità sulla tappa fluttuante**: `SegnaleFluttuante`
  non porta `accessibile`/`al_chiuso` (scelta di forma minimale, `docs/BUILD_PLAN.md`
  documenta il perché): una tappa fluttuante può quindi essere aggiunta anche se il suo luogo
  è affollato, e non è mai esclusa per un profilo che richiede accessibilità.

### Cosa servirebbe per chiudere questi buchi (proposte, NON implementate ora)

1. **Coda di curatela per la promozione**: un nuovo modello (es. `segnale fluttuante osservato N
   volte, stesso place_id/tema, negli ultimi M giorni`) e una soglia esplicita da negoziare col
   committente, non stimata qui.
2. **Verifica di `non_commerciale`**: nessuna proposta tecnica specifica oltre a quanto già
   scritto per `POST /events` (autenticazione, un segnale minimo di presenza reale) — lo stesso
   canale d'ingresso irrisolto copre anche questo campo, non è un problema separato da
   risolvere due volte.
3. **Tetto al numero di tappe fluttuanti** e **filtro di affollamento/accessibilità sulla tappa
   fluttuante**: entrambi richiedono prima un caso reale (un pilota con più segnali attivi
   contemporaneamente, o un profilo con accessibilità richiesta che incontra un segnale) che ne
   mostri il bisogno concreto.

### Decisione

Il livello fluttuante è attivato con lo scope minimo esplicitamente richiesto: aggiunta,
pertinenza per tema, filtro duro sul commerciale, rispetto del budget. Il livello programmato,
la promozione, la verifica del canale d'ingresso e i due affinamenti del punto 3 restano fuori,
deliberatamente. Questo limite va riletto prima di:
- costruire il livello "programmato" (`:Evento`) — a quel punto va deciso anche se/come si
  collega al fluttuante (la promozione);
- aprire la generazione di segnali fluttuanti a un pubblico reale, per lo stesso motivo già
  scritto per `POST /events`: la fiducia non verificata (qui: `non_commerciale`) smette di
  essere un rischio teorico nel momento in cui persone reali, non solo chi verifica a mano,
  possono generare segnali.

---

## Un contributo `curato=True` ma non ancora agganciato resta comunque visibile via API

**Introdotto:** Fase 3, Task 1. **Componente:** `services/urban-memory`. **Trovato durante:**
il giro dedicato di `ethics-guardian` sull'automazione "curato tira aggancio"
(`docs/ENGINE_INVARIANTS.md` §11-B).

### Cosa è garantito oggi

`get_curated`/`contributions_for_place` (`InMemoryMemoryRepository` e
`PostgresMemoryRepository`, `services/urban-memory/urban_memory/repository.py`) filtrano
SOLO su `curato=True`, mai su `stato_aggancio`. Verificato che nessun consumatore odierno
attraversa `(:Memoria)-[:RIGUARDA]->(...)` dal grafo per decisioni utente: l'Urban
Intelligence Index legge `MemoryContribution` da Postgres, non dal grafo;
`experience-engine` non tocca `:Memoria` in nessuna forma. L'inconsistenza descritta sotto
non è quindi sfruttabile da nessun percorso reale oggi.

### Cosa NON è garantito

Un contributo con `curato=True` e `stato_aggancio` in `AGGANCIO_FALLITO` (o `None`, un
contributo curato prima che questa automazione esistesse) compare comunque via
`GET /memory/{place_id}` — indistinguibile, per chi consuma quell'endpoint, da un
contributo già effettivamente scritto nel grafo. Se in futuro una feature interrogasse il
grafo direttamente per gli stessi dati (es. per arricchire un candidato esperienza con le
memorie collegate), potrebbe non trovare quello che l'API pubblica sta già mostrando.

### Cosa servirebbe per chiudere il buco

Filtrare `get_curated`/`contributions_for_place` anche su `stato_aggancio=AGGANCIATO`,
oppure esporre `stato_aggancio` nel payload dell'endpoint così che chi consuma l'API possa
distinguere i due casi. Nessuna delle due è stata fatta ora: non fabbricare un filtro
aggiuntivo senza un consumatore reale che ne mostri il bisogno (stesso principio già
applicato altrove in questo file).

### Decisione

Non chiuso ora — verificato non sfruttabile oggi (nessun consumatore attraversa il grafo per
questi dati). Questo limite va riletto prima di costruire qualunque feature che legga
`(:Memoria)-[:RIGUARDA]->(...)` dal grafo invece che `MemoryContribution` da Postgres.

---

## `retry_link_contribution` non ha rate limit

**Introdotto:** Fase 3, Task 1. **Componente:** `services/urban-memory`. **Trovato durante:**
lo stesso giro di `ethics-guardian` sopra.

### Cosa è garantito oggi

`retry_link_contribution` (`services/urban-memory/urban_memory/service.py:289`) è invocato
oggi SOLO manualmente, dalla CLI `python -m urban_memory.verify` (passo 5,
`_verifica_aggancio_idempotente`) — nessun loop automatico, nessun job schedulato lo
richiama.

### Cosa NON è garantito

Se in futuro si costruisse un processo che scorre `list_aggancio_fallito()` e richiama
`retry_link_contribution` su ciascuno (il caso d'uso naturale per cui la coda di retry
esiste), non c'è oggi alcun backoff o limite di frequenza: un Aura persistentemente
irraggiungibile produrrebbe tentativi ripetuti senza attenuazione.

### Cosa servirebbe per chiudere il buco

Un backoff (es. esponenziale, con un tetto) sul processo che consuma
`list_aggancio_fallito()`, quando quel processo verrà scritto — non prima: non fabbricare un
rate limit senza un job reale che lo richieda.

### Decisione

Non implementato ora — nessun rischio attivo (nessun loop automatico esiste). Questo limite
va riletto prima di costruire un job/endpoint che consumi `list_aggancio_fallito()` in modo
automatico e ripetuto.

---

## Il canale fluttuante persistente: lo sweep è pigro, la traccia arriva in ritardo indefinito

**Introdotto:** Fase 3, fondazione persistenza+ledger. **Componente:** `services/urban-memory`,
`services/api`.

### Cosa è garantito oggi

`SegnaleFluttuante` persiste con una scadenza assoluta (`valido_fino`, tz-aware UTC). La
transizione `attivo → expired` è deliberatamente LAZY (non un job/cron): avviene solo in
lettura, innescata dalla prima `POST /itinerary` che arriva dopo la scadenza
(`urban_memory.segnale_repository.sweep_scaduti`, chiamata da
`urban_memory.canale_fluttuante.sweep_and_fetch_active` dentro `api.main.create_itinerary`).
La query è GLOBALE (non filtrata per luogo): ogni richiesta, per qualunque luogo, spazza
TUTTI i segnali scaduti nel frattempo — non solo quelli del luogo interrogato in quella
richiesta specifica. Questo evita il buco classico del lazy-sweep ("i luoghi tranquilli non
vengono mai spazzati").

### Cosa NON è garantito

Se NESSUNA richiesta arriva a `POST /itinerary` per un periodo prolungato, i segnali scaduti
restano `stato=attivo` in Postgres indefinitamente: nessuna traccia si deposita, `:Luogo.
ultima_traccia_il` non si aggiorna, finché non arriva la prossima richiesta (per qualunque
luogo). Non è una perdita di dato (il segnale non sparisce, la traccia arriverà appena una
richiesta arriva), solo un RITARDO indefinito — ma un ritardo che può essere arbitrariamente
lungo se il traffico si ferma. Un cruscotto/audit che leggesse `ultima_traccia_il` per
giudicare quanto un luogo "parla" potrebbe vedere un dato stantio più a lungo di quanto ci si
aspetterebbe da un sistema con sweep attivo.

### Cosa servirebbe per chiudere il buco

Un job schedulato (cron/worker periodico) che chiami `sweep_and_fetch_active` (o solo la sua
parte di sweep) a intervalli regolari, indipendentemente dal traffico su `/itinerary`.
Deliberatamente NON costruito ora: nessun caso reale ne mostra il bisogno prima che il canale
fluttuante abbia traffico reale da osservare — stesso principio di "non sovra-modellare" già
applicato altrove in questo file.

### Decisione

Non implementato ora. Questo limite va riletto prima di:
- presentare `ultima_traccia_il`/il ledger delle tracce come "in tempo reale" a un
  consumatore (Comune, dashboard) — oggi è "aggiornato alla prossima richiesta reale", non
  un flusso continuo;
- decidere se investire in un job schedulato, quando il traffico reale su `/itinerary`
  mostrerà se il ritardo è effettivamente un problema pratico o solo teorico.

---

## Un fallimento del deposito, dopo lo sweep, perde la traccia in modo permanente (isolato al singolo segnale)

**Introdotto:** Fase 3, fondazione persistenza+ledger. **Componente:** `services/urban-memory`.
**Trovato durante:** un giro dedicato di `ethics-guardian`, non un'autovalutazione.

### Cosa è garantito oggi

Lo sweep (`sweep_scaduti`, un `UPDATE ... WHERE stato='attivo' AND valido_fino<=now
RETURNING` atomico) e il deposito della traccia (`traccia_repo.deposita`, un `INSERT`
separato per ogni segnale scaduto) NON condividono una transazione — scelta deliberata,
stesso principio già accettato altrove nel repo per `link_to_graph`/Postgres ("due scritture
in due store diversi, non una transazione distribuita da inventare"). Un fallimento nel
deposito di UN segnale è ISOLATO: non blocca né fa fallire il deposito degli altri segnali
scaduti nello stesso sweep (`urban_memory.canale_fluttuante.sweep_and_fetch_active`, ogni
`deposita`/`place_link_writer` avvolto in un try/except per-segnale, che logga e continua —
corretto dopo un FAIL iniziale di `ethics-guardian` che aveva trovato il ciclo capace di
abortire interamente su un solo fallimento).

### Cosa NON è garantito

Se `deposita` fallisce per un segnale specifico (es. un blip di connessione Postgres/Neon
transitorio) DOPO che `sweep_scaduti` ha già committato la sua transizione `attivo→expired`,
quella traccia va PERSA in modo PERMANENTE e SILENZIOSO (solo un log a livello `ERROR`, mai
un errore visibile a un chiamante HTTP): la guardia primaria dell'idempotenza
(`WHERE stato='attivo'`) impedisce per costruzione a qualunque sweep futuro di ripescare un
segnale già `expired`. Il segnale stesso resta correttamente `expired` (non più composto in
un itinerario) — a perdersi è solo la riga del ledger per quel segnale specifico, non
l'integrità del canale nel suo insieme. Questo contraddice, per il singolo segnale colpito,
l'aspettativa di `docs/PROMOZIONE_TRACCIA.md` §2a che il ledger sia "append-only, immortale...
la fonte di verità" — è vero per ogni riga che riesce a depositarsi, non è garantito che ogni
segnale scaduto ci riesca.

### Cosa servirebbe per chiudere il buco

Una coda di retry per i depositi falliti (stesso principio già applicato all'aggancio al
grafo di Urban Memory, `list_aggancio_fallito()`/`retry_link_contribution` — Fase 3, Task 1),
oppure una transazione condivisa Postgres tra `segnale_fluttuante` e `traccia_luogo` (stessa
connessione per sweep+deposito, con rollback dello sweep se il deposito fallisce) — quest'
ultima cambierebbe l'architettura attuale (le due tabelle sono oggi gestite da repository
indipendenti con connessioni proprie) e non è stata richiesta da `ethics-guardian` come
bloccante.

### Decisione

Non implementato ora — il rischio è stato RIDOTTO (isolamento per-segnale, non più un
fallimento a cascata su un intero batch) ma non ELIMINATO, deliberatamente: nessuna coda di
retry è stata costruita senza un caso reale (traffico reale sul canale fluttuante) che ne
mostri la frequenza pratica del problema. Questo limite va riletto prima di:
- presentare il ledger delle tracce come garanzia assoluta di completezza a un consumatore
  reale (es. se il bagliore, `docs/PROMOZIONE_TRACCIA.md` §2b, entrasse in produzione e un
  luogo "sembrasse" meno vivo di quanto sia per una traccia mai depositata);
- decidere se investire in una coda di retry dedicata, quando il traffico reale mostrerà
  quanto spesso questo scenario si manifesta davvero.

---

## `POST /itinerary/adapt` non sanifica `Signal.eventi_attivi` come fa `POST /itinerary`

**Introdotto:** Fase 3, fondazione persistenza+ledger. **Componente:** `services/api`.
**Trovato durante:** lo stesso giro di `ethics-guardian` sopra (osservazione non bloccante).

### Cosa è garantito oggi

`POST /itinerary` ora sovrascrive SEMPRE `ctx.signal.eventi_attivi` con la lettura autorevole
dallo store (sweep+fetch), ignorando qualunque valore il client abbia mandato nel body —
proprietà di sicurezza verificata da un test dedicato. `POST /itinerary/adapt` invece passa
`request.signal` DIRETTAMENTE ad `adapt_itinerary`, senza alcuna sanificazione.

### Cosa NON è garantito

Un client potrebbe, in teoria, iniettare `eventi_attivi` fabbricati anche in
`/itinerary/adapt`. Oggi è INNOCUO: `adapt_itinerary`/`experience_engine.engine` non leggono
MAI `signal.eventi_attivi` (limite già dichiarato in `docs/ENGINE_INVARIANTS.md` §6:
"`adapt_itinerary` non rivaluta mai i segnali fluttuanti" — un limite pre-esistente a questa
fase, non introdotto ora). Ma è una TRAPPOLA LATENTE: un futuro sviluppatore che estendesse
`adapt_itinerary` per rivalutare i segnali fluttuanti (chiudendo il limite sopra) potrebbe
dimenticare che questo endpoint non applica la stessa igiene di `/itinerary`, reintroducendo
la vulnerabilità che `/itinerary` ha appena chiuso.

### Cosa servirebbe per chiudere il buco

Applicare la stessa sovrascrittura autorevole (sweep+fetch dallo store) anche in
`/itinerary/adapt`, MA solo quando (se mai) `adapt_itinerary` verrà esteso per rivalutare i
segnali fluttuanti — farlo ora, prima che `adapt_itinerary` legga quel campo, sarebbe lavoro
morto: nessun percorso lo consumerebbe.

### Decisione

Non implementato ora — nessun rischio attivo (il campo non viene mai letto da `adapt`). Va
riletto — non ignorato — nello stesso momento in cui si chiude il limite gemello in
`docs/ENGINE_INVARIANTS.md` §6 ("`adapt_itinerary` non rivaluta mai i segnali fluttuanti"):
le due estensioni vanno fatte insieme, non l'una dimenticando l'altra.

---

## Il cestino dei pattern ricorrenti è permanente in v1; nessuna interfaccia oltre la CLI

**Introdotto:** Fase 3, rilevamento pattern ricorrenti + promozione `:Evento` + cestino.
**Componente:** `services/urban-memory`.

### Cosa è garantito oggi

`urban_memory.cestino_repository` (tabella `pattern_cestinato`) registra il rifiuto
PERMANENTE di un pattern (`place_id`+insieme di `temi`): un pattern cestinato non ricompare
MAI più come candidato, anche accumulando nuove occorrenze nel ledger dopo il rifiuto —
verificato da un test dedicato. La colonna `motivo` esiste ed è opzionalmente popolabile dal
Promotore al momento del rifiuto (`python -m urban_memory.curatela_pattern`). Il comando è un
percorso ristretto/fidato, stesso principio di `submit_signal.py`/`verify.py`: nessuna auth,
nessun rate limit, nessun endpoint HTTP.

### Cosa NON è garantito

Il `motivo` è registrato ma NON guida alcuna logica: non esiste una distinzione fra un
rifiuto "temporaneo" (es. "troppo presto per giudicare, ririvedi fra un anno") e uno
"definitivo" (es. "è pubblicità mascherata") — ogni rifiuto ha lo stesso effetto,
permanente e indistinguibile dagli altri se non per il testo libero del `motivo`. Inoltre,
la curatela esiste SOLO come comando CLI: nessuna interfaccia grafica, nessun endpoint HTTP,
nessun modo per un Promotore di rivedere l'elenco dei pattern già cestinati (nessun
equivalente di `GET /memory/{place_id}` per il cestino) — un pattern cestinato per errore
richiederebbe un intervento diretto su Postgres per essere corretto.

### Cosa servirebbe per chiudere il buco

1. **Logica "temporaneo vs permanente"** sul cestino: un campo di tipo/categoria sul
   rifiuto (non solo testo libero) che determini se/quando un pattern può essere
   ripresentato. Richiede prima dati reali sui motivi di rifiuto più comuni nel pilota — non
   fabbricata ora per lo stesso principio già applicato altrove in questo file
   (`tasso_ritorno`, capienza del marketplace): non tarare una categorizzazione a tavolino
   senza un caso reale che la richieda.
2. **Un modo di rivedere/annullare un rifiuto**: un comando o un endpoint che elenchi
   `pattern_cestinato` e permetta di rimuovere una riga (rompendo l'append-only solo per
   questo caso esplicito, con log dedicato) — non costruito ora.
3. **Un'interfaccia oltre la CLI**: fuori scope per questa v1, esplicitamente (stesso
   principio già accettato per il canale fluttuante — `docs/LIMITI.md`, voce su
   `SegnaleFluttuante.non_commerciale`/canale d'ingresso).

### Decisione

Non implementato ora — scope minimo deliberato (v1: curatore reale da CLI + cestino
permanente). Questo limite va riletto prima di:
- aprire la curatela dei pattern a più di un Promotore o a un uso ad alta frequenza (a quel
  punto un rifiuto per errore, irreversibile senza toccare Postgres a mano, diventa un
  rischio operativo concreto, non solo teorico);
- decidere se/come costruire la logica temporaneo/permanente — a quel punto i `motivo`
  raccolti finora sono il dato su cui basare la categorizzazione.

---

## Il rilevamento automatico di un pattern ricorrente non lascia un record d'audit distinto dalla decisione del Promotore

**Introdotto:** Fase 3, rilevamento pattern ricorrenti + promozione `:Evento` + cestino.
**Componente:** `services/urban-memory`.

### Cosa è garantito oggi

Le due transizioni UMANE — `candidato → promosso` e `candidato → cestinato` — sono entrambe
loggate (`chi=Promotore, quando, pattern, cadenza/motivo`) e, per la promozione, anche
persistite come proprietà del nodo `:Evento` (`promosso_da`/`promosso_il`, mai sovrascritte
da una ripromozione — corretto dopo un FAIL dedicato di `ethics-guardian`). Il rifiuto è
persistito in `pattern_cestinato`, append-only.

### Cosa NON è garantito

`urban_memory.ricorrenza.rileva_candidati` — il rilevamento AUTOMATICO, system-detected, di
un pattern che supera la soglia N+tolleranza — è una funzione PURA, senza alcun log
applicativo del fatto stesso "il sistema ha rilevato questo pattern come ricorrente, in base
a queste occorrenze, in questo momento". Questo diverge dal principio congelato di
`docs/STATE_MACHINE.md` §5/§1.4 ("ogni transizione di stato logga chi/quando/perché — anche
le automatiche... una transizione system-detected, es. il rilevamento ricorrenza, va
comunque registrata"), che usa letteralmente questo caso come esempio. Non è un rischio di
integrità (il rilevamento è ricalcolato identico ad ogni corsa della CLI dallo stesso ledger,
non è uno stato che si possa perdere), ma un buco di accountability: un'amministrazione che
volesse ricostruire mesi dopo "quando è emerso per la prima volta questo pattern, anche prima
che un Promotore lo notasse" non troverebbe nulla.

### Cosa servirebbe per chiudere il buco

Un log applicativo (`logging`, stesso livello di persistenza già accettato per le transizioni
umane di questo stesso file prima della correzione sul grafo) emesso da
`rileva_candidati` — o da chi la chiama — alla prima volta che un pattern supera la soglia:
richiede però di distinguere "prima volta rilevato" da "rilevato di nuovo alla corsa
successiva" (oggi `rileva_candidati` non ha memoria fra una corsa e l'altra), quindi non è
un aggiustamento puramente locale.

### Decisione

Non implementato ora — non bloccante (nessuna perdita di stato, solo di un audit trail
opzionale), non richiesto esplicitamente dal brief che ha introdotto questa funzionalità
(che imponeva la tracciabilità solo per le transizioni innescate da un umano, già
soddisfatta). Va riletto prima di:
- presentare la curatela dei pattern come "auditabile end-to-end" a un'amministrazione;
- costruire un meccanismo che debba sapere "da quanto tempo" un pattern è candidato (oggi
  non derivabile se non dalla prima occorrenza nel ledger, un proxy imperfetto).

---

## La frizione automatica a cadenza (`attivo ⇄ sospeso → dormiente`) è un batch manuale: la riattivazione non è in tempo reale, e non ha uno scheduler

**Introdotto:** Fase 3, frizione automatica a cadenza. **Componente:** `services/urban-memory`
(`urban_memory.frizione_pattern`).

### Cosa è garantito oggi

`python -m urban_memory.frizione_pattern` calcola e applica la transizione di stato di ogni
`:Evento {ricorrente: true}` esistente, leggendo le sue occorrenze ESATTE dal ledger
Postgres (`TracciaRepository.occorrenze_per_pattern`, filtrato per `place_id`+`temi`) e
scrivendo `e.stato` solo se cambia (`MATCH`+`SET` puro, mai un `MERGE`). Ogni transizione
automatica applicata è loggata esplicitamente (chi=sistema, quando, evento_id, stato
precedente→nuovo, perché) — colma, per questo meccanismo, il gap di accountability
documentato nella voce precedente di questo file per il rilevamento ricorrenza. La logica è
sensibile alla CADENZA (`attivo → sospeso` in battiti mancati) e non a un tempo assoluto
fisso per la sospensione, con un orizzonte di dormienza proporzionale alla cadenza del
singolo pattern (`max(pavimento assoluto, moltiplicatore × cadenza_giorni)` — corretto da un
giro dedicato di `ethics-guardian` che aveva trovato i valori di default iniziali in
tensione, vedi sotto). Verificato: 228 test passano.

> **AGGIORNAMENTO (Fase 3, consumo degli `:Evento` promossi in `/itinerary`) — l'affermazione
> precedente in questo paragrafo ("nessuna riga di questo modulo è raggiungibile da
> `/itinerary`") NON è più vera, e va corretta esplicitamente, non lasciata implicita.**
> `services/api/api/deps.get_evento_reader` riusa direttamente
> `urban_memory.frizione_pattern.Neo4jFrizioneClient`/`leggi_eventi_ricorrenti`: `POST
> /itinerary` legge ORA tutti gli `:Evento {ricorrente: true}`, filtra `stato == 'attivo'` e fa
> comparire i pattern attivi come tappe in coda (`experience_engine.engine.
> _aggiungi_tappe_eventi_promossi`, `docs/PROMOZIONE_TRACCIA.md` §3). Conseguenza diretta dei
> due limiti sopra, ora concreta e non più teorica: se `frizione_pattern` non viene rieseguito
> con regolarità (nessuno scheduler, vedi sotto), un `:Evento` il cui `stato` è rimasto
> stantio su `'attivo'` (perché nessuno ha rilanciato il comando dopo che il pattern è
> realmente cessato) continua a comparire in itinerari reali finché qualcuno non fa girare il
> comando — non è più solo "un dato di stato non aggiornato", è "una raccomandazione a un
> visitatore basata su un dato non aggiornato". Verificato per `ethics-guardian` dedicato
> (PASS sull'implementazione tecnica del consumo — nessun impatto su score, nessuna
> forzatura di budget, nessuna iniezione lato client, degradazione sempre a 200, `reason`
> onesto — ma FAIL iniziale proprio su questa frase non aggiornata, corretta qui). Vedi anche
> la voce su `SegnaleFluttuante.non_commerciale` più sopra in questo file (sezione "Livello
> FLUTTUANTE attivato"), per il secondo varco (verifica del carattere commerciale) reso
> concretamente raggiungibile dallo stesso lavoro.
>
> **AGGIORNAMENTO (finestra temporale).** Dal task "finestra temporale degli `:Evento`
> promossi" un evento `attivo` stantio non compare più in OGNI itinerario, ma solo nei giorni
> in finestra attorno alla sua occorrenza proiettata (`ultima_occorrenza` letta dal ledger a
> ogni richiesta). Il limite resta: la finestra decide solo "quando", "se è vivo" resta a
> `stato`, quindi uno `stato` stantio continua a far comparire l'evento nei giorni in cui la
> sua cadenza lo proietterebbe. Dettaglio nella voce "La finestra temporale degli `:Evento`
> promossi", in fondo a questo file.

### Cosa NON è garantito

- **`sospeso → attivo` non è in tempo reale.** Il design originario
  (`docs/STATE_MACHINE.md` §4-bis(a), prima di questa implementazione) ipotizzava "automatico
  non appena arriva una traccia fresca". Il codice reale calcola il clock del pattern SOLO
  quando `frizione_pattern` viene eseguito — non c'è alcun trigger legato al deposito di una
  traccia (`urban_memory.canale_fluttuante.sweep_and_fetch_active`, che gira dentro
  `/itinerary`). Un pattern può quindi restare `sospeso` più a lungo di quanto la sola cadenza
  indicherebbe, se questo comando non viene rieseguito con regolarità dopo che il pattern ha
  ripreso a manifestarsi. Decisione architetturale deliberata (vedi il docstring del modulo):
  l'alternativa (dare al percorso caldo di `/itinerary` visibilità su `:Evento` per
  aggiornare lo stato ad ogni traccia) avrebbe accoppiato il motore puro a una scrittura sul
  grafo non necessaria per comporre un itinerario.
- **Nessuno scheduler esiste.** Il comando va invocato manualmente (stesso principio di
  `curatela_pattern.py`/`submit_signal.py`/`verify.py`): non esiste un job periodico, un
  cron, o un trigger che lo richiami automaticamente. Senza disciplina operativa (rieseguirlo
  a intervalli regolari), gli `:Evento` promossi possono restare con uno `stato` stantio
  indefinitamente — un pattern realmente cessato mesi fa potrebbe restare `attivo` finché
  nessuno fa girare il comando.
- **Nessuna riattivazione da `dormiente`.** Una volta dichiarato `dormiente`, un `:Evento` non
  torna mai automaticamente `attivo`/`sospeso` in questo comando, anche se il pattern
  ricomincia a manifestarsi con nuove tracce nel ledger — `calcola_transizione` tratta
  `dormiente` come vicolo cieco per costruzione. Fuori scope deliberato (nessun caso reale
  osservato che ne mostri il bisogno); se servirà, è un task a sé.
- **Nessuna "tolleranza sul ritmo".** Il design originario (`docs/PROMOZIONE_TRACCIA.md` §5,
  item 3) menzionava una tolleranza su quanto una cadenza può slittare prima di contare come
  "battito mancato" — `calcola_transizione` non ha alcun parametro equivalente: usa il
  rapporto esatto `giorni_trascorsi / cadenza_giorni`, nessuna soglia di margine.
- **I tre valori di tuning (`K_BATTITI_SOSPENSIONE=2`, `ORIZZONTE_DORMIENZA_GIORNI=180.0`,
  `K_ORIZZONTE_DORMIENZA=3.0`) sono valori di PARTENZA**, non calibrati su alcun dato reale
  del pilota — stessa classe di `ricorrenza.N_MINIMO_OCCORRENZE`/`TOLLERANZA_REGOLARITA`. Un
  giro dedicato di `ethics-guardian` (non un'autovalutazione) ha trovato che i valori
  inizialmente proposti erano in tensione reale: con `K_BATTITI_SOSPENSIONE=2` e un pattern a
  cadenza lunga (es. annuale, `cadenza_giorni≈365`), la soglia `attivo→sospeso` scattava solo
  a ~730 giorni — ma un `ORIZZONTE_DORMIENZA_GIORNI=180` fisso e indipendente dalla cadenza
  era già ampiamente superato ben prima di quell'istante, quindi il pattern sarebbe stato
  dichiarato `dormiente` quasi subito dopo essere entrato in `sospeso`, vanificando lo scopo
  dichiarato (gestire nativamente la stagionalità). Corretto rendendo l'orizzonte
  proporzionale alla cadenza (`max(pavimento, moltiplicatore × cadenza_giorni)`) prima della
  chiusura di questo lavoro — ma la calibrazione dei tre numeri resta comunque da fare sui
  dati reali del pilota, non definitiva.

### Cosa servirebbe per chiudere questi buchi (proposte, NON implementate ora)

1. **Uno scheduler** (cron, job periodico) che invochi `python -m urban_memory.frizione_pattern`
   a intervalli regolari — decisione operativa (quale intervallo?), non solo tecnica.
2. **Riattivazione in tempo reale**: solo se un caso reale mostra che il ritardo del batch è
   inaccettabile — richiederebbe ripensare l'accoppiamento hot-path/grafo deliberatamente
   evitato in questa implementazione, non un aggiustamento locale.
3. **Riattivazione da `dormiente`**: da progettare quando/se un caso reale la richiede
   (un pattern dichiarato morto che poi ricomincia).
4. **Calibrazione dei tre numeri di tuning** sui dati reali del pilota, come già rimandato per
   `N_MINIMO_OCCORRENZE`/`TOLLERANZA_REGOLARITA` sopra in questo file.

### Decisione

Non implementato ora. Il comando resta un batch manuale, senza scheduler, senza riattivazione
da `dormiente`, senza tolleranza sul ritmo — dichiarato esplicitamente, non un buco silenzioso.
Questo limite va riletto prima di:
- affidarsi allo `stato` di un `:Evento` come sempre aggiornato in un contesto di produzione
  reale (Living Lab) senza una disciplina operativa esplicita di riesecuzione del comando;
- decidere di investire in uno scheduler o in una riattivazione in tempo reale.

---

## Il freno di emergenza (v1 minima) è un percorso fidato/CLI provvisorio, senza lista nominale di permessi

**Introdotto:** Fase 3, freno di emergenza v1 minima. **Componente:** `services/urban-memory`
(`urban_memory.freno_pattern`), `services/api` (`api.main`, filtro di consumo).

### Cosa è garantito oggi

Il freno (`python -m urban_memory.freno_pattern tira|rilascia`) sopprime la raccomandazione di
un `:Evento` promosso senza mai toccare `e.stato`: proprietà separata `e.frenato`
(`cypher/62_freno_stato_write.cypher`, `MATCH`+`SET` puro, mai `MERGE`), letta dal filtro di
consumo in `POST /itinerary` (`services/api/api/main.py`, ora `stato == 'attivo' and not
frenato`) — lettura pura, nessuna scrittura raggiungibile dal path caldo (verificato con un
guard AST: il BFF non importa mai `freno_pattern`/`freno_repository`). Il ledger delle tracce
resta veritiero: un pattern frenato continua a depositare tracce normalmente (verificato con un
guard AST bidirezionale — nessun import incrociato tra i moduli del freno e
`canale_fluttuante`/`traccia_repository` — e un test comportamentale end-to-end).
`motivazione` e `attore` sono entrambi validati PRIMA di ogni scrittura (né sul grafo né sulla
tabella `pattern_frenato`) su `tira_freno`/`rilascia_freno` — quest'ultimo trovato mancante da
un giro dedicato di `ethics-guardian` (FAIL iniziale: un `attore` vuoto poteva produrre un
`:Evento` frenato senza riga di audit, perché la scrittura sul grafo precede quella
sull'audit), corretto e riverificato PASS. La tabella `pattern_frenato` è append-only, senza
vincolo UNIQUE (il freno è ripetibile: ogni tiro/rilascio è una riga nuova, mai un upsert).

### Cosa NON è garantito

Il design congelato (`docs/STATE_MACHINE.md §4-bis(b)`) prevede un **permesso individuale
nominale**: solo un sottoinsieme ristretto di Promotori può tirare il freno, con
concessione/revoca del permesso stesso tracciata e reversibile. **Nessuna parte di questo
livello di autorità è implementata.** Il comando è oggi un percorso **fidato/CLI
provvisorio** — stessa postura già accettata per `curatela_pattern.py`/`frizione_pattern.py`/
`submit_signal.py`: nessuna autenticazione, nessun rate-limit, nessuna lista che distingua un
Promotore autorizzato al freno da uno che non lo è. Chiunque abbia accesso alla shell del
repository (con `.env` configurato) può tirare o rilasciare il freno su qualunque `:Evento`
promosso, fornendo un `attore` a piacere (uno pseudonimo non verificato, esattamente come
`promotore` in `pattern_cestinato`/`:Evento.promosso_da` — stessa fiducia non verificata già
accettata altrove in questo file per `POST /events`/`SegnaleFluttuante.non_commerciale`).

Conseguenza pratica: l'"accountability" oggi è **auditabile** (ogni azione lascia una riga
persistita, interrogabile, con attore+motivazione+timestamp) ma **non autorizzata** — non c'è
modo, nel codice, di impedire a chi ha accesso alla CLI di tirare il freno senza averne il
titolo istituzionale. Per un contesto di pubblica amministrazione (un Comune che deve poter
rispondere "chi AVEVA IL POTERE di frenare questo pattern il giorno X", non solo "chi lo ha
fatto"), questo è un gap reale, non solo teorico, nel momento in cui più di una persona ha
accesso al comando.

### Cosa servirebbe per chiudere il buco

Una lista nominale persistita (tabella o configurazione) di chi detiene il permesso-freno, con
grant/revoke tracciato e reversibile (append-only, stesso principio già applicato a
`pattern_frenato`), e un controllo in `tira_freno`/`rilascia_freno` che verifichi `attore`
contro quella lista PRIMA di scrivere — rifiutando, non solo loggando, un tentativo da un
attore non autorizzato. Residuo esplicitamente differito dal brief (`docs/STATE_MACHINE.md`
§7.14.1, item 16): chi amministra concretamente la lista (un Admin di piattaforma? il Comune?
il Promotore più anziano?) non è deciso — costruirla ora senza quella decisione fabbricherebbe
un meccanismo di governance a tavolino, stesso principio già applicato altrove in questo file
(`tasso_ritorno`, capienza del marketplace).

### Decisione

Non implementato ora, deliberatamente — v1 minima esplicitamente scoped a questo. Questo
limite va riletto prima di:
- aprire l'accesso al comando `freno_pattern` a più di una persona fidata nel Living Lab (a
  quel punto l'assenza di una lista nominale smette di essere un rischio teorico);
- decidere chi amministra la lista dei permessi-freno, sciogliendo il residuo di
  `docs/STATE_MACHINE.md` §7.14.1.

---

## Non-atomicità tra la scrittura sul grafo e quella di audit del freno di emergenza

**Introdotto:** Fase 3, freno di emergenza v1 minima. **Componente:** `services/urban-memory`
(`urban_memory.freno_pattern`). **Trovato durante:** un giro dedicato di `ethics-guardian`,
osservazione non bloccante lasciata dopo la correzione del bug bloccante (voce precedente in
questo file, sulla validazione di `attore`).

### Cosa è garantito oggi

`tira_freno`/`rilascia_freno` validano `motivazione`/`attore` PRIMA di ogni effetto
collaterale: un tentativo con uno dei due campi vuoto/whitespace non scrive NULLA, né sul
grafo né su `pattern_frenato` — chiude il bug bloccante trovato nel primo giro di
`ethics-guardian`.

### Cosa NON è garantito

Anche dopo quella correzione, `writer(evento_id, ...)` (scrittura su Neo4j) e
`repo.registra(...)` (scrittura su Postgres) restano DUE scritture separate, non
transazionali — stesso limite architetturale già accettato altrove nel repo per
`link_to_graph`/Postgres e per lo sweep+deposito del canale fluttuante (`docs/LIMITI.md`, voce
"Un fallimento del deposito..."). Se `repo.registra` fallisce per una causa infrastrutturale
DOPO che `writer` ha già scritto `e.frenato` con successo (es. un blip di connessione Postgres
transitorio, non più un `attore`/`motivazione` invalidi — quel caso è chiuso), il freno resta
comunque tirato sul grafo ma senza la riga di audit corrispondente in quella specifica
esecuzione. Nessun test esercita esplicitamente questo scenario (scrittura sul grafo riuscita,
scrittura di audit fallita per causa infrastrutturale).

### Cosa servirebbe per chiudere il buco

Una coda di retry per l'audit fallito (stesso principio già applicato altrove — `docs/
ENGINE_INVARIANTS.md` §11-B, `list_aggancio_fallito()`/`retry_link_contribution`), oppure
invertire l'ordine di scrittura (registrare prima l'intento in `pattern_frenato`, poi scrivere
sul grafo) — quest'ultima non elimina il problema, lo sposta (un `writer` fallito dopo un
`repo.registra` riuscito lascerebbe una riga di audit per un'azione mai avvenuta sul grafo).
Nessuna delle due è stata costruita ora: nessun caso reale (traffico reale sul comando) mostra
la frequenza pratica di questo scenario.

### Decisione

Non implementato ora — il rischio è residuale (richiede un fallimento infrastrutturale nella
finestra tra le due scritture, non un input malformato: quel caso è già chiuso) e non
bloccante secondo il giro di `ethics-guardian` che lo ha trovato. Questo limite va riletto
prima di:
- presentare il freno come garanzia assoluta di audit completo in un contesto di produzione
  reale (Living Lab);
- decidere se investire in una coda di retry o in un cambio di ordine delle scritture, quando
  il traffico reale mostrerà se questo scenario si manifesta davvero.


---

## Le promozioni anteriori al ledger `pattern_promosso` non sono recuperabili

### Cosa è garantito oggi

Ogni promozione fatta con `curatela_pattern` dopo l'introduzione di `pattern_promosso`
(`sql/04_promozione_schema.sql`) è registrata PRIMA nel ledger Postgres e poi proiettata sul
grafo: `python -m urban_memory.ripristina_eventi` ricostruisce gli `:Evento` (e `e.frenato`) dopo
la perdita di Aura. Se la proiezione fallisce dopo il ledger la promozione resta registrata e
verrà proiettata dal ripristino.

### Cosa NON è garantito

- Gli `:Evento` promossi PRIMA del ledger vivevano solo su Aura: se il grafo è già perso, la
  decisione (chi, quando, cadenza) non è ricostruibile da nessuna fonte. Vanno ripromossi
  dal Promotore (i pattern ricompaiono come candidati se le tracce ci sono ancora).
- `e.stato` non è ripristinato: i nuovi eventi partono `sospeso` (fail-safe, non
  raccomandabili) finché `frizione_pattern` non li riporta `attivo`; un evento già dormiente
  perde quello stato fino alla corsa. Un freno su un evento assente dal ledger è
  segnalato come avviso, non applicabile.
- Il ripristino non rilascia mai un freno (`e.frenato = $frenato OR coalesce(e.frenato, false)`):
  un freno presente sul grafo ma assente da `pattern_frenato` resta tirato; si rilascia solo
  con `freno_pattern rilascia`.
- Il ripristino scrive `promosso_da`/`promosso_il` con `coalesce`: su un nodo GIÀ esistente
  (anche pre-ledger) non sovrascrive l'accountability originale, ma il ledger non la corregge
  se divergente. Un pattern presente sia nel cestino sia nel ledger non è proiettato.
- Un `:Luogo` sparito tra la verifica e la proiezione lascia una riga nel ledger che il
  ripristino segnalerà (exit 1) finché il seed non è ricaricato.

### Decisione

Accettato: il ledger copre il futuro, il passato si ripromuove a mano.

---

## La finestra temporale degli `:Evento` promossi: fatti approssimati, data dal client

**Introdotto:** Fase 3, consumo degli `:Evento` con finestra temporale (sostituisce la v1
"compare in qualunque giorno"). **Componenti:** `experience_engine.rules`
(`evento_in_finestra`, `FRAZIONE_FINESTRA_CADENZA`), `services/api/api/main.create_itinerary`,
`contracts.Signal.data`/`EventoPromosso.ultima_occorrenza`/`cadenza_giorni`,
`apps/lucca_soul_app` (`Signal.orologio`).

### Cosa è garantito oggi

- Un `:Evento` promosso, `attivo` e non frenato compare SOLO se `Signal.data` cade entro
  `FRAZIONE_FINESTRA_CADENZA × cadenza_giorni` (0.15, valore di PARTENZA, tuning differito)
  dall'occorrenza proiettata più vicina `ultima_occorrenza + k·cadenza_giorni`, k ≥ 1 intero.
  Bordo incluso. La finestra è proporzionale alla cadenza, mai fissa (settimanale ≈ ±1 giorno,
  mensile ≈ ±4,5 giorni). Decide solo l'Experience Engine, funzione pura; il BFF passa i fatti.
- Fail-closed, mai una data inventata: `Signal.data` assente, `CITY_TZ` assente o non valido,
  nessuna occorrenza nel ledger per il pattern, `cadenza_giorni <= 0` o non finita (inf/nan:
  rifiutata dal contratto, saltata per singolo evento dal BFF), proiezione non
  rappresentabile come `date` → l'evento NON compare. `/itinerary` risponde comunque 200.
- `data` e `giorno_settimana` incoerenti nello stesso `Signal` → 422 (validatore del contratto).
- La finestra decide solo "quando"; "se è vivo" resta alla frizione (`stato`). `calcola_score`
  e `passa_filtri_duri` non leggono `Signal.data`. Tappa sempre in coda, a budget.
- Un client che mente sulla propria data cambia solo il proprio itinerario: `data` non entra
  nel ledger, negli eventi comportamentali, nei log, negli indici; la lista degli eventi è
  letta solo da grafo e ledger.

### Cosa NON è garantito

- **`ultima_occorrenza` è sfasata in avanti.** Il timbro di una traccia è l'istante dello
  sweep pigro (`canale_fluttuante.sweep_and_fetch_active`, eseguito solo quando qualcuno chiama
  `POST /itinerary`), non l'istante dell'occorrenza reale. In bassa affluenza lo scarto può
  superare la finestra stessa (±1 giorno per un settimanale): la proiezione eredita lo scarto.
- **Cadenze molto corte sono "sempre in finestra".** `cadenza_giorni` è una media di
  intervalli, vincolata solo a `> 0`: con cadenza ≤ ~1 giorno ogni giorno contiene
  un'occorrenza proiettata, e il pattern si comporta come nella v1 senza finestra. Non peggiora
  la v1 (la finestra è un sottoinsieme del "sempre"), ma non la migliora. Nessun pavimento di
  cadenza esiste oggi (né in `rileva_candidati` né alla curatela).
- **La fase si sposta con nuove tracce.** `ultima_occorrenza` è riletta dal ledger a ogni
  richiesta: un nuovo segnale ammissibile sullo stesso pattern ri-ancora la finestra. Può
  scegliere in quali giorni l'evento compare, mai aumentarne l'esposizione oltre la v1. La
  difesa contro i segnali commerciali resta quella alla radice
  (`segnale_fluttuante_ammissibile`, auto-dichiarata: limite noto, voce su
  `SegnaleFluttuante.non_commerciale`).
- **Finestra simmetrica: "era attesa ieri".** Un'occorrenza proiettata già passata ma in
  finestra produce comunque una tappa; il `reason` lo dichiara ("un'occorrenza era attesa
  ieri", "stima", "orario ignoto"), ma la tappa propone 15 minuti per qualcosa che forse non
  c'è più.
- **Fuso del dispositivo vs fuso della città.** L'app manda la data locale del DISPOSITIVO;
  il BFF converte il ledger con `CITY_TZ`. Un dispositivo in un altro fuso può sfalsare di ±1
  giorno: per cadenze brevi (finestra < 1 giorno) la finestra reale può essere mancata.
- **Una query al ledger per ogni evento attivo, a ogni `/itinerary`**
  (`occorrenze_per_pattern`, che restituisce tutte le occorrenze per prenderne il massimo).
  Accettato ora; ottimizzazione futura: un metodo batch che restituisca `max(creato_il)` per
  tutti i pattern in una sola query.
- **App non verificata a compilazione.** La compilazione di `Signal.data` nell'app Flutter
  (`Signal.orologio`, `signal_presets.dart`) è scritta ma non compilata né testata: `flutter`/
  `dart` non sono installati (stessa condizione della voce sulla dashboard Flutter). Usa un
  record con nome (Dart 3; `pubspec.yaml` dichiara `sdk >=3.3.0`). Senza questa parte, in
  produzione nessun evento comparirebbe mai (fail-closed).
- **Itinerario a cavallo della mezzanotte.** La finestra usa la data della visita al momento
  della composizione (stesso limite "istante singolo" dei filtri duri, voce sugli orari di
  apertura): una tappa-evento collocata dopo la mezzanotte è valutata sulla data d'inizio.

### Cosa servirebbe per chiudere questi buchi (proposte, NON implementate ora)

1. Timbro più fedele: uno sweep periodico indipendente da `/itinerary`, o timbrare la traccia
   con la fine dichiarata della finestra del segnale invece che con l'istante dello sweep.
2. Pavimento di cadenza (es. ≥ 2 giorni) in `rileva_candidati` o un avviso al Promotore in
   curatela per i pattern quasi quotidiani.
3. Finestra asimmetrica (solo occorrenze ≥ `data_visita`, o un anticipo massimo minore del
   ritardo) per non proporre tappe già passate.
4. Metodo batch sul ledger.

### Decisione

Accettato come v1 della finestra. Verifica: giro dedicato di `ethics-guardian` (vedi
`docs/PROMOZIONE_TRACCIA.md` §3, nota sulla finestra).
