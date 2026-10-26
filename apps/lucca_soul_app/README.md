# Lucca Soul App

App Flutter — Human Experience Layer di Lucca Soul Lab. Parla **solo** con il
BFF (`services/api`); non conosce Neo4j, Postgres né alcun servizio interno.

## Avvio della demo (app servita dal BFF)

`scripts\avvia_demo.ps1` fa la build web dell'app (`flutter build web --release` con
`DEMO=true` e l'istante scelto), imposta `APP_WEB_DIR` sulla cartella `build\web` e avvia il BFF,
che serve l'app su `/` dalla stessa origine delle API (niente CORS). Il BFF usa il `.env` reale
(Aura e Neon): verificare prima che Aura sia RUNNING. Lo script si ferma se manca
`.venv\Scripts\python.exe`, se il comando `flutter` non esiste o se la porta 8000 è occupata
(indica il PID da fermare).

Dalla radice del repo, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Istante 2026-12-12T09:00:00Z
```

- `-Istante`: l'orologio fisso dell'app, SOLO nella forma `yyyy-MM-ddTHH:mm:ssZ` (UTC, con la
  `Z`). Default `2026-12-12T09:00:00Z`, cioè sabato 12/12 alle 10:00 a Lucca.
- `-Rete`: il BFF ascolta su `0.0.0.0` invece di `127.0.0.1`, per aprire la demo da un altro
  dispositivo; lo script stampa gli indirizzi IPv4 della macchina. Solo su una rete fidata (vedi
  `docs/LIMITI.md`, ondata 4):

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Istante 2026-12-12T09:00:00Z -Rete
  ```

Con la sessione PowerShell già abilitata agli script vale anche
`.\scripts\avvia_demo.ps1 -Istante 2026-12-12T09:00:00Z` (con o senza `-Rete`).

I due istanti del copione, nel browser:

- mattina, 10:00: `http://localhost:8000/`
- pomeriggio, 15:00: `http://localhost:8000/?istante=2026-12-12T14:00:00Z`

Il parametro `?istante=` vale solo nella build con `DEMO=true` (quella dello script), solo nella
forma con la `Z`, e prevale sull'istante della build; un valore non valido mostra un errore, mai un
orario di ripiego. Lo script stampa anche l'indirizzo del pomeriggio (istante + 5 ore). Per
fermare il BFF: Ctrl+C. Dopo modifiche all'app va rilanciato lo script (rifà la build).

## Sviluppo

1. Avvia il BFF locale (default `http://localhost:8000`), dalla radice del repo:
   ```powershell
   .venv\Scripts\python.exe -m uvicorn api.main:app --app-dir services\api --port 8000
   ```
2. Avvia l'app in Chrome, da `apps\lucca_soul_app`:
   ```powershell
   flutter pub get
   flutter run -d chrome --dart-define=BFF_URL=http://localhost:8000 --dart-define=DEMO=true
   ```
   Con `DEMO=true` l'indirizzo accetta `?istante=...Z` come nella demo. Attenzione: `flutter run`
   serve l'app da un'altra porta, quindi da un'altra origine, e il BFF apre CORS solo su
   `GET /dashboard/*`: le chiamate `POST` (`/itinerary`, `/memory`…) sono bloccate dal browser.
   In sviluppo si aggiunge `--web-browser-flag=--disable-web-security` (non verificato in questo
   aggiornamento della documentazione); per la demo vale la build servita dal BFF, sopra.

## Test

```
flutter test
```

I test coprono solo la logica pura (parsing/serializzazione dei contratti in
`lib/models/`, il diff delle tappe in `lib/util/itinerary_diff.dart`, la
regola di invio del conferimento in `lib/util/memory_gate.dart`): nessuna
dipendenza da un device o da un BFF in esecuzione.

## Schermate

- **Home** (`lib/main.dart`, `_HomeScreen`) — punto di ingresso: scegli tra
  "Sono un visitatore" (onboarding) e "Sono cittadino/a di Lucca" (vista
  Cittadino). Il Cittadino è un percorso di prima classe fin dalla radice
  dell'app, non nascosto dentro quello del turista.
- **Onboarding** (`lib/screens/onboarding_screen.dart`) — conversazione a 7
  domande (`perdersi`, `silenzio_musica`, `bellezza_storie`, `bambini`,
  `tempo`, `accessibilita`, `firenze`), pensata per stare sotto i due minuti.
  Chiama `POST /session/onboarding` e apre l'itinerario con l'`EmotionalProfile`
  ricevuto.
- **Itinerario** (`lib/screens/itinerary_screen.dart`) — chiama `POST /itinerary`
  con il `VisitorContext` (profilo + segnale corrente) e mostra ogni tappa con
  orario di arrivo, durata e `reason` sempre in evidenza. Ogni tappa ha
  un'azione "Lascia un ricordo" che apre il conferimento a Urban Memory.
- **Card adattiva** (`lib/widgets/adaptive_card.dart`) — tre bottoni di
  simulazione segnale (pioggia, mura affollate, stanchezza) che chiamano
  `POST /itinerary/adapt` e mostrano le tappe cambiate, evidenziate, con il
  nuovo `reason`.
- **Vista Cittadino** (`lib/screens/citizen_screen.dart`, Wave 2) — "il
  Cittadino non paga: alimenta la Urban Memory ed è la condizione di
  sostenibilità sociale del sistema" (CLAUDE.md). Mostra i contributi già
  curati di un luogo (`GET /memory/{place_id}`) e apre il conferimento con
  `contributor_kind = cittadino`.
- **Conferimento a Urban Memory** (`lib/widgets/memory_contribution_sheet.dart`,
  Wave 2) — bottom sheet leggero e contestuale (a una tappa dell'itinerario o
  a un luogo dalla vista Cittadino): tipo di ricordo, un breve racconto o un
  link a un media, licenza tracciata (default `CC-BY-SA-4.0`) e **consenso
  esplicito mai pre-spuntato**. Il bottone "Conferisci" resta disabilitato
  finché non c'è consenso, licenza e un contenuto (`lib/util/memory_gate.dart`,
  `docs/DATA_CONTRACTS.md` §4/§7: "nessuna eccezione"). Chiama `POST /memory`.

## Foto delle tappe

Le foto arrivano con un commit di soli dati, senza toccare il codice:

- il file è `assets/foto/<experience_id>.jpg` (la chiave è l'`experience_id` della tappa,
  non l'id del luogo);
- didascalia e autore stanno in `assets/foto/foto.json`, indicizzati per `experience_id`:
  `{"exp-...": {"didascalia": "...", "autore": "..."}}`. Oggi il file è `{}`;
- una foto si mostra SOLO se esistono entrambi (il jpg e la voce del json). Se manca uno dei due,
  o il json è malformato, la card resta com'è, senza errori;
- le tappe fluttuanti e gli eventi promossi (id che iniziano con `fluttuante-` o `evento-`) non
  hanno mai una foto, anche se esistesse il file.

Le foto devono essere del committente, senza persone riconoscibili né insegne, e senza dati GPS
(metadati EXIF rimossi prima del commit). La card mostra una miniatura 4:3 con la didascalia come
testo alternativo; toccandola si apre la foto intera con la riga «Foto: <autore>».

## Privacy

`person_id` (`lib/util/person_id.dart`) è uno pseudonimo casuale generato in
memoria a ogni avvio dell'app: non è derivato da alcun dato personale e non
viene mai scritto su storage persistente del device. Lo stesso vale per
`contributor_id` in un `MemoryContribution` (`lib/util/local_id.dart` genera
gli `id` locali dei conferimenti con lo stesso principio): mai un nome, mai
un dato identificante.

## Multilingua

La lingua della conversazione di onboarding è scelta esplicitamente
dall'utente (selettore in alto a destra). Da lì in poi l'app segue
`EmotionalProfile.lingue` restituito dal BFF (`lib/util/app_strings.dart`).

## Nota d'ambiente

Questo modulo è stato scritto senza Flutter/Dart SDK disponibile in questo
ambiente: non è stato possibile eseguire `flutter analyze`, `flutter pub get`
né `flutter test` qui. Il codice separa la logica pura (modelli, diff delle
tappe) dai widget proprio per essere verificabile appena l'SDK è disponibile.
