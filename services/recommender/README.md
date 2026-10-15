# Lucca Soul — Recommender ML (`services/recommender`)

Wave 3b: il recommender **ordina**, non decide (CLAUDE.md — decide un solo
componente, l'Experience Engine) e non racconta. Import name del pacchetto:
`recommender` (nome distribuzione: `lucca-recommender`).

Impara l'**algoritmo** dai comportamenti storici (`BehaviorEvent`:
view/stop/photo/booking/review/skip/memory_contrib), non il modello
linguistico. Il prodotto di questo servizio è una `score_fn` compatibile con
`experience_engine.engine.ScoreFn`, da iniettare come `score_fn` in
`compose_itinerary` (lo fa il BFF, `services/api`) — il filtro duro
(`passa_filtri_duri`) si applica SEMPRE PRIMA e resta l'unica responsabilità
dell'Experience Engine: `score_fn` riceve solo candidati già ammessi.

## Il vincolo centrale della wave

I comportamenti storici riflettono l'overtourism **esistente**: ottimizzare
la "pertinenza" misurata sui dati storici manderebbe tutti dove sono già
andati tutti. La funzione obiettivo di questo servizio non è la pertinenza,
è: **pertinenza VINCOLATA a distribuzione dei flussi**.

- `base = calcola_score(...)` (riusata da `experience_engine.rules`, mai
  duplicata) misura l'affinità profilo <-> esperienza.
- Il punteggio finale è:

  ```
  punteggio = base - peso_storico * quota_storica_smussata(place)
                    - peso_struttura * quota_strutturale(place)
  ```

  due **penalità** indipendenti, mai un premio, entrambe sul LUOGO fisico
  (`place_id`, non la singola scheda esperienza):
  - **quota storica smussata** — quanto quel luogo ha già concentrato flusso
    storico REALE (`BehaviorEvent`), con smoothing additivo di Laplace;
  - **quota strutturale** — quanto quel luogo domina per PERTINENZA DI
    CONTENUTO attraverso un insieme fisso di profili archetipo, senza alcun
    dato storico.
- **Cold start** (zero eventi mappabili, o pochi sotto
  `SOGLIA_MINIMA_EVENTI_MAPPABILI = 20`): il risultato è **bit-identico** a
  `calcola_score` da solo — non un'approssimazione. ENTRAMBE le quote sono
  spente sotto soglia, non solo quella storica: senza uno storico
  sufficiente a giustificare correzioni, "cold start" significa "nessuna
  correzione", punto.
- Non si ottimizza **mai** click, conversioni, prenotazioni, valore delle
  commissioni, permanenza nell'app.

### Perché due termini, non uno solo — la diagnosi che ha reso necessario il fix

La prima versione di questo modulo penalizzava SOLO la quota storica. Un
test di integrazione (`tests/test_integration_wave3b.py`) ha trovato un
caso REALE in cui questo non bastava: con uno storico sintetico concentrato
su 2 luoghi, penalizzare quei 2 luoghi liberava budget che
`_seleziona_tappe` (in `experience_engine.engine`, non toccato da questo
modulo) riempiva con il MIGLIOR candidato disponibile per punteggio **base**
— che, per più profili diversi, era lo STESSO luogo (il più pertinente per
CONTENUTO attraverso profili diversi, indipendentemente da qualunque
storico). Quel luogo aveva ZERO eventi tracciati, quindi la sola penalità
storica (quota = 0 esatto per un luogo senza eventi) non lo toccava: il
luogo assorbiva il flusso spostato e la concentrazione AGGREGATA (misurata
su una popolazione di profili) peggiorava, invece di migliorare. "Essere
scelto un terzo delle volte è concentrazione, anche senza un solo evento."

Il fix ha due parti, ORTOGONALI tra loro:

1. **Smoothing additivo (Laplace)** sulla quota storica
   (`recommender.ranking._quota_storica_per_place`): ogni luogo tra i
   candidati correnti riceve una quota di base non nulla —
   `(conteggio[place] + alpha) / (totale + alpha * N)`, `alpha = 1.0`
   (`ALPHA_LAPLACE`, il valore standard di Laplace smoothing) — invece di
   quota = 0 esatto per un luogo senza eventi tracciati.
2. **Quota strutturale** (`recommender.ranking._quota_strutturale_per_place`):
   un secondo segnale, calcolato dal recommender stesso SENZA alcun dato
   esterno (niente `BehaviorEvent`, niente storico) — un insieme fisso di 6
   profili "archetipo" (`ARCHETIPI_STRUTTURALI`, documentati nel codice) più
   un segnale neutro fisso costruito localmente
   (`SEGNALE_NEUTRO_STRUTTURALE`). Per ogni archetipo si individua il luogo
   in testa per `calcola_score` puro; la quota finale è la frequenza con cui
   un luogo è in testa, aggregata sugli archetipi. Misura, in modo
   puramente deterministico e locale, quanto un luogo domina per pertinenza
   di CONTENUTO attraverso profili diversi — esattamente ciò che mancava.

Entrambi i termini sono spenti insieme sotto `SOGLIA_MINIMA_EVENTI_MAPPABILI`
(cold start): la quota strutturale, pur non dipendendo da alcuno storico,
resta comunque una CORREZIONE, e senza storico sufficiente a giustificare
correzioni non se ne applica nessuna.

### Limite massimo di penalità combinata

`peso_storico` (`PESO_STORICO_DEFAULT = 0.3`) e `peso_struttura`
(`PESO_STRUTTURA_DEFAULT = 0.2`) sono pesi indipendenti, ma la loro SOMMA
deve rispettare `LIMITE_PESO_COMBINATO_MAX = 0.5`: ciascuna quota è in
[0, 1], quindi la penalità massima combinata possibile è
`(peso_storico + peso_struttura) * 1.0`. Con la somma di default (0.5),
anche il caso limite peggiore (un solo luogo che satura ENTRAMBE le quote a
1.0) perde al più 0.5 punti di score — mai abbastanza da ribaltare un
vantaggio di pertinenza ampio (es. base = 0.9 con doppia quota = 1.0 resta a
0.4, ancora davanti a base = 0.3 con doppia quota = 0.0). Il vincolo è
verificato anche A RUNTIME: `costruisci_score_fn` solleva `ValueError` se
`peso_storico + peso_struttura > LIMITE_PESO_COMBINATO_MAX`.

### Limite noto di questa correzione (non nascosto)

Questa è una correzione **locale, per singola richiesta**: robustezza
empirica su 4 scenari storici indipendenti (`tests/test_integration_wave3b.py`),
non una garanzia matematica su qualunque scenario possibile. Analisi
completa — cosa servirebbe per una garanzia vera (allocazione globale a
batch, o stato condiviso in tempo reale con un algoritmo di allocazione
online) e il costo stimato — in **`docs/LIMITI.md`**, sezione "Il Recommender
ML non garantisce matematicamente la non-concentrazione aggregata".

## Feature usate — lista esplicita, con motivazione

L'unico input di dominio di questo servizio è `contracts.BehaviorEvent`,
aggregato per `place_id` (mai per singola `experience_id`: è il luogo fisico
a subire l'affollamento, non la scheda esperienza — vedi
`recommender.ranking._quota_storica_per_place`). Ogni `tipo` di evento
contribuisce con un peso, definito in `recommender.features.PESI_TIPO`:

| `tipo` | peso | perché |
|---|---|---|
| `view` | 1.0 | baseline: il segnale più debole di interesse (potrebbe essere solo passata sullo schermo), ma resta un'unità di esposizione. |
| `stop` | 2.0 | presenza fisica reale e prolungata in quel luogo: il segnale più diretto di "flusso" nel senso in cui questa wave lo intende — pesa il doppio di una vista. |
| `photo` | 1.5 | gesto di attenzione attivo (si fotografa ciò che colpisce davvero): più forte di una vista, non equivalente a una tappa completa. |
| `booking` | 2.0 | intenzione di visita concreta, stesso ordine di segnale di presenza di `stop`. Conta **solo come indicatore di flusso**, esattamente come `stop`: il fatto che un'esperienza sia prenotabile o abbia un prezzo non entra in nessun calcolo — qui si contano eventi, non euro. |
| `review` | 1.0 | riflessione POST-visita: la presenza fisica è già contata da `stop`/`booking`, la review aggiunge solo una conferma leggera che la visita sia avvenuta, senza raddoppiare il peso della stessa visita. |
| `skip` | 0.0 | rifiuto esplicito: un contatore di concentrazione non deve mai premiare un luogo perché è stato ignorato molte volte. Zero (non negativo) per restare in `[0, 1]` e facilmente spiegabile in italiano nel `reason` ("skip non conta come presenza"). |
| `memory_contrib` | 1.5 | un contributo alla Urban Memory è un segnale di coinvolgimento volontario profondo (più di una vista, meno di una presenza fisica già contata da `stop`/`booking`); peso moderato perché è un evento raro e pochi contributi non devono dominare la quota storica di un luogo. Si conta **solo che l'evento sia avvenuto**, mai il contenuto della `MemoryContribution` associata. |

**Su cosa poggia questa tabella, esplicitamente**: il peso 2.0 di `stop` (il più alto della
tabella insieme a `booking`) è giustificato sopra come "presenza fisica reale e prolungata in
quel luogo" — ma oggi NESSUN codice verifica che un evento `stop` corrisponda a una presenza
fisica reale. `POST /events` accetta qualunque `BehaviorEvent` sintatticamente valido, senza
prova di presenza (GPS, check-in, QR, conferma operatore), senza autenticazione, senza rate
limiting: chiunque raggiunga il BFF può generare eventi `stop` fabbricati, gratis, quanti ne
vuole. Chi legge questa tabella per capire perché un luogo pesa nella distribuzione dei flussi
deve sapere che il peso riflette un'assunzione di autenticità, non un fatto verificato —
dettaglio completo, coi quattro punti verificati uno per uno e le proposte di rimedio (non
implementate), in `docs/LIMITI.md` ("`POST /events` non ha alcuna prova di presenza,
autenticazione o rate limiting — prerequisito del Living Lab").

Questi pesi alimentano **solo** il calcolo della quota storica di
concentrazione per `place_id` (`recommender.ranking._quota_storica_per_place`,
con smoothing di Laplace — vedi sopra), usata poi esclusivamente per
**penalizzare**, mai per premiare.

La mappa `experience_id -> place_id` necessaria all'aggregazione si
costruisce **solo** dai `GraphCandidate` ricevuti a runtime per la richiesta
corrente (`candidati_correnti`), mai da un join/import del grafo: questo
pacchetto non importa `services/graph`.

La quota **strutturale** (`recommender.ranking._quota_strutturale_per_place`)
non usa NESSUN `BehaviorEvent`: è calcolata solo da `calcola_score` sui
`candidati_correnti` di questa richiesta contro un insieme fisso di 6
profili archetipo (`ARCHETIPI_STRUTTURALI`) e un segnale neutro costruito
localmente (`SEGNALE_NEUTRO_STRUTTURALE`) — nessun input esterno, nessun
dato commerciale, nessun dato di Urban Memory/Index.

## Cosa NON è una feature, e perché

- **Campi commerciali** (`ExperienceNode.partner_id`, `.prezzo_eur`,
  `.partner_abbonamento_attivo`, `.prenotabile`, `GraphCandidate.attribuzione`).
  Né direttamente né come proxy ("ha un prezzo", "ha un partner_id non
  nullo", "è prenotabile" sono proxy vietati): la visibilità non è
  acquistabile, e un vincolo lo si verifica solo dove è concentrato — questo
  modulo non ha nemmeno un percorso di import verso `contracts.Partner`.
  Verificato da un test-guard AST + un test comportamentale di invarianza
  bit-a-bit (`tests/test_ranking.py`).
- **Rating e recensioni di provider terzi** (Google, TripAdvisor o simili).
  Il numero di recensioni è **notorietà**: pesarlo — anche solo come
  contributo positivo al punteggio — reintrodurrebbe il bias di popolarità
  che questa wave esiste per contrastare. È il proxy più diretto
  dell'overtourism: un luogo già affollato ha, quasi per definizione, più
  recensioni di uno appena scoperto. Nessun campo di rating esterno esiste
  oggi né in `packages/contracts` né nel seed del grafo (vincolo
  preventivo/documentale, non una correzione di codice esistente). Se un
  domani un simile segnale venisse introdotto, potrebbe valere **al
  massimo** come soglia di ammissione binaria (mai come contributo al
  punteggio) — e sarebbe comunque responsabilità dell'Experience Engine
  (il filtro duro), non del recommender.
- **Dati di Urban Memory / Urban Intelligence Index.** Il feedback dei
  visitatori sulle esperienze della piattaforma è il segnale di qualità
  legittimo del progetto, ma alimenta l'Urban Intelligence Index (Wave 4) —
  un sistema di **reporting** verso il Comune, aggregato per periodo, mai un
  input della funzione di ranking individuale di questa wave. Questo modulo
  conta solo che un evento `memory_contrib` sia avvenuto (dalla lista di
  `BehaviorEvent`): non legge mai il contenuto della `MemoryContribution`
  associata né alcun dato aggregato di Urban Memory/Index. Mescolare un
  canale di reporting collettivo con il reranking individuale creerebbe un
  ciclo di feedback fuori dal perimetro di questa wave.
- **`experience_id` come unità di concentrazione.** La quota storica è
  aggregata per `place_id`, non per singola esperienza: due esperienze
  diverse nello stesso luogo (es. due botteghe nella stessa piazza)
  contribuiscono ENTRAMBE alla stessa quota, perché è il luogo fisico a
  subire l'affollamento.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts` (schemi) e
`services/experience-engine` (`rules.calcola_score`) sono dipendenze locali
(non su un indice pip): vanno installate a parte, insieme a questo pacchetto,
in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/experience-engine -e services/recommender
```

## Moduli

- `recommender/features.py` — `PESI_TIPO` (tabella sopra) e le funzioni pure
  di aggregazione: `conteggio_pesato_per_esperienza` (da una lista di
  `BehaviorEvent`, percorso in-memory) e `pesare_conteggi_grezzi` (da righe
  `(tipo, experience_id, n)`, il formato di un `GROUP BY` Postgres — stessa
  logica, nessuna duplicazione).
- `recommender/repository.py` — `BehaviorEventRepository` (Protocol):
  `record(event)` / `conteggio_per_esperienza()`.
  - `InMemoryBehaviorEventRepository` — lista in-process. **Percorso usato
    dai test e finché `DATABASE_URL` non è configurato.**
  - `PostgresBehaviorEventRepository(dsn)` — Neon (`sslmode=require` in
    cloud) o Postgres locale (Docker sul PC fisso): stesso codice nei due
    profili, cambia solo il DSN. Persiste DAVVERO: una connessione (e una
    transazione) per operazione. Ogni errore psycopg è mappato in
    `RecommenderStorageError` (infrastrutturale, mai un'eccezione psycopg
    grezza lasciata risalire). `.from_env()` legge `DATABASE_URL` dal `.env`
    (radice del repo) o dall'ambiente di processo.
- `recommender/migrate.py` — `migrate(dsn)`: applica lo schema idempotente
  `sql/00_events_schema.sql` (`CREATE TABLE`/`INDEX ... IF NOT EXISTS`,
  nessun `DROP`). Anche come CLI: `python -m recommender.migrate` (legge
  `DATABASE_URL` dal `.env`).
- `recommender/ranking.py` — `costruisci_score_fn(repo, candidati_correnti,
  *, peso_storico=0.3, peso_struttura=0.2, soglia_minima_eventi=20,
  alpha_smoothing=1.0) -> ScoreFn`, con
  `ScoreFn = Callable[[GraphCandidate, EmotionalProfile, Signal], float]`
  (stessa firma strutturale di `experience_engine.engine.ScoreFn`). Vedi "Il
  vincolo centrale della wave" sopra per la logica; solleva `ValueError` se
  `peso_storico + peso_struttura > LIMITE_PESO_COMBINATO_MAX (0.5)`.
- `sql/00_events_schema.sql` — tabella `behavior_event`: `BehaviorEvent` non
  ha un campo `id` nel contratto, quindi la tabella usa una chiave surrogata
  (`id BIGSERIAL`) più `ricevuto_il` (timestamp server, distinto da `ts` —
  quando l'evento è avvenuto lato client). `CHECK` sul `tipo`, difesa in
  profondità oltre alla validazione Pydantic a monte.

## Migrazione dello schema (una tantum, idempotente)

```powershell
$env:DATABASE_URL = "postgresql://...neon.tech/...?sslmode=require"   # o Postgres locale
python -m recommender.migrate
```

## Uso — offline, senza database (`InMemoryBehaviorEventRepository`)

```powershell
python -c "
from datetime import datetime, UTC
from contracts import BehaviorEvent
from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn

repo = InMemoryBehaviorEventRepository()
repo.record(BehaviorEvent(
    person_id='turista-pseudonimo-1', tipo='stop',
    experience_id='esperienza-1', ts=datetime.now(UTC),
))

# candidati_correnti: normalmente arrivano dal grafo per QUESTA richiesta.
# vocabolario: VocabolarioTemi del dataset della città scelto da CITY_SEED,
# passato dal BFF (il recommender non lo sceglie né ha un default).
# score_fn = costruisci_score_fn(repo, candidati_correnti, vocabolario=vocabolario)
# itinerario = compose_itinerary(ctx, candidati_correnti, reason_fn, score_fn)
print(repo.conteggio_per_esperienza())
"
```

## Uso — con `DATABASE_URL` (Neon o Postgres locale): persiste DAVVERO

```powershell
python -c "
from recommender import PostgresBehaviorEventRepository
repo = PostgresBehaviorEventRepository.from_env()   # legge DATABASE_URL dal .env
"
```

## Test

```powershell
pytest services/recommender
```

I test di `PostgresBehaviorEventRepository` (persistenza reale, migrazione
idempotente, `CHECK` del DB) usano un Postgres 16 effimero avviato al volo
dalla suite (`tests/conftest.py`, stesso pattern di
`services/marketplace/tests/conftest.py`); se Postgres non è installato in
macchina, quei test sono **saltati**, non falliti. `tests/test_ranking.py`
copre i criteri di accettazione della wave (aggiornati dopo la diagnosi sul
termine strutturale): cold start bit-identico (entrambe le quote spente),
smoothing di Laplace sulla quota storica, penalizzazione del termine
strutturale per un luogo a zero eventi ma dominante per contenuto, il
limite massimo di penalità combinata (anche verificato a runtime), e
"visibilità non acquistabile" (test-guard AST esteso a tutte le funzioni di
quota + test comportamentale di invarianza ai campi commerciali, con
qualunque storico di eventi). Girano sempre, senza bisogno di un database.

```powershell
ruff check services/recommender
```
