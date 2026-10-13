# Lucca Soul App

App Flutter — Human Experience Layer di Lucca Soul Lab. Parla **solo** con il
BFF (`services/api`); non conosce Neo4j, Postgres né alcun servizio interno.

## Avvio

1. Avvia il BFF locale (default `http://localhost:8000`), dalla radice del repo:
   ```powershell
   .venv\Scripts\python.exe -m uvicorn api.main:app --app-dir services\api --port 8000
   ```
2. Avvia l'app:
   ```
   flutter pub get
   flutter run
   ```
3. Per puntare a un BFF diverso:
   ```
   flutter run --dart-define=BFF_URL=http://192.168.1.10:8000
   ```

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
