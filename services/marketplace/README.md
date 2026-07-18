# Lucca Soul — Marketplace (`services/marketplace`)

Wave 3a: prenotazioni (`Booking`) su esperienze prenotabili e la commissione
che ne deriva (`CommissionRecord`) — un dato **contabile**, mai un input di
scoring. Import name del pacchetto: `marketplace` (nome distribuzione:
`lucca-marketplace`).

Il Recommender ML (Wave 3b) e il filtro duro dell'abbonamento
nell'Experience Engine (`services/experience-engine`, in lavorazione in
parallelo) **non fanno parte di questo servizio**: questo README copre solo
il Marketplace.

## Regole non negoziabili

Applicate in un solo punto verificabile, `marketplace.service` (CLAUDE.md,
`docs/DATA_CONTRACTS.md` §5):

- **Stato iniziale.** Una `Booking` nasce SEMPRE in `RICHIESTA`
  (`request_booking`): non esiste un modo di crearla già `CONFERMATA`.
- **Prezzo, snapshot.** `prezzo_eur` è congelato al momento della richiesta
  (chi chiama passa il prezzo corrente dell'`ExperienceNode`); non viene mai
  ricalcolato dal listino, anche se questo cambia dopo.
- **Prenotabilità.** Una richiesta su un'esperienza con
  `ExperienceNode.prenotabile=False` è rifiutata SUBITO
  (`ExperienceNotBookableError`), prima di persistere nulla. `prenotabile` è
  un concetto DISTINTO dalla presenza commerciale di un partner
  (`partner_id`/`partner_abbonamento_attivo`): non si deduce dall'uno
  all'altro.
- **La commissione è calcolata SOLO dopo la conferma.**
  `marketplace.service.confirm_booking` è l'UNICA funzione che calcola un
  `CommissionRecord` (`importo_eur = prezzo_eur * percentuale`,
  `percentuale` letta dal default del contratto, `CommissionRecord.
  model_fields["percentuale"].default` — mai una costante duplicata), e lo
  fa SOLO dopo che `repo.update_status(booking_id, CONFERMATA)` è già
  tornato dal repository. Confermare una prenotazione già `CONFERMATA` è
  idempotente: nessuna doppia commissione (rinforzato a livello DB da
  `commission_record.booking_id PRIMARY KEY`).
- **Nessuna asta sulla visibilità.** Il modello di ricavo dei partner resta
  un abbonamento di presenza (sì/no, `Partner.abbonamento_attivo`). Questo
  pacchetto non introduce, in nessun modello o funzione, un campo
  "peso"/"boost"/"priorita_pagata": nessuno spazio è acquistabile
  (CLAUDE.md), e nessun prezzo pagato da un partner altera questa regola.
- **Nessun percorso verso l'Experience Engine.** `marketplace` non importa
  `services/experience-engine` e non è importato da esso. Lo scoring del
  motore non vede mai `CommissionRecord` né `Partner`: vede solo
  `ExperienceNode.partner_abbonamento_attivo` (booleano denormalizzato).
- **Persiste davvero.** `PostgresBookingRepository` scrive su Postgres reale
  (Neon in cloud, `sslmode=require`; Postgres locale sul PC fisso — stesso
  codice, cambia solo il DSN): la prenotazione e la commissione sopravvivono
  al riavvio del processo. I vincoli sullo stato e sui valori numerici sono
  ribaditi ANCHE a livello DB con `CHECK` — difesa in profondità, non solo
  applicativa.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts` è la single source of truth
degli schemi (`Booking`, `BookingRequest`, `BookingStatus`,
`CommissionRecord`...) ed è una dipendenza locale (non su un indice pip): va
installata a parte, insieme a questo pacchetto, in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/marketplace
```

## Moduli

- `marketplace/repository.py` — `BookingRepository` (Protocol):
  `create`/`get`/`update_status`/`record_commission`/`get_commission`.
  - `InMemoryBookingRepository` — dizionari in-process. **Percorso usato dai
    test e finché `DATABASE_URL` non è configurato.**
  - `PostgresBookingRepository(dsn)` — Neon (`sslmode=require` in cloud) o
    Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
    cambia solo il DSN. **Persiste davvero**: una connessione (e una
    transazione) per operazione, nessuno stato tenuto in RAM tra una
    chiamata e l'altra. Ogni errore psycopg è mappato in
    `MarketplaceStorageError` (infrastrutturale, NON un `MarketplaceError`
    di dominio). `PostgresBookingRepository.from_env()` legge
    `DATABASE_URL` dal `.env` (radice del repo) o dall'ambiente di
    processo. Richiede lo schema applicato una volta (vedi "Migrazione"
    sotto).
- `marketplace/migrate.py` — `migrate(dsn)`: applica lo schema idempotente
  `sql/00_marketplace_schema.sql` (`CREATE TABLE`/`INDEX ... IF NOT EXISTS`,
  nessun `DROP`). Anche come CLI: `python -m marketplace.migrate` (legge
  `DATABASE_URL` dal `.env`).
- `marketplace/service.py` — la logica di dominio: `request_booking`,
  `confirm_booking`. Le eccezioni dedicate, tutte sottoclassi di
  `MarketplaceError`: `ExperienceNotBookableError`, `BookingNotFoundError`,
  `InvalidBookingStateError` (il BFF le mappa rispettivamente a 422, 404,
  409 — vedi `services/api`).
  - `request_booking(repo, request, *, prezzo_eur, prenotabile,
    id_generator=None)` — crea la `Booking` (stato `RICHIESTA`, id
    `booking-<uuid4>` di default, sovrascrivibile per id deterministici
    nei test/verify).
  - `confirm_booking(repo, booking_id)` — legge la prenotazione
    (`BookingNotFoundError` se assente), rifiuta se `ANNULLATA`
    (`InvalidBookingStateError`), è idempotente se già `CONFERMATA`
    (ritorna senza ricalcolare), altrimenti persiste la transizione a
    `CONFERMATA` e SOLO DOPO calcola e registra la `CommissionRecord`.
- `marketplace/verify.py` — CLI di verifica end-to-end (`python -m
  marketplace.verify`): migra → richiede → **verifica che nessuna
  commissione esista prima della conferma** → conferma → rilegge da un
  repository nuovo → verifica aritmeticamente `importo_eur`. RIESEGUIBILE
  ALL'INFINITO, stesso principio di `urban_memory.verify`: ogni passo legge
  PRIMA lo stato reale invece di assumere che il passo precedente sia
  riuscito.

## Migrazione dello schema (una tantum, idempotente)

```powershell
$env:DATABASE_URL = "postgresql://...neon.tech/...?sslmode=require"   # o Postgres locale
python -m marketplace.migrate
```

Rieseguibile in sicurezza da zero (nessun `DROP`, solo `CREATE ... IF NOT
EXISTS`): stesso principio del seed del grafo e dello schema di Urban
Memory. Applica `sql/00_marketplace_schema.sql`, che include:
`booking.stato IN ('richiesta','confermata','annullata')`,
`booking.prezzo_eur >= 0`, `commission_record.booking_id PRIMARY KEY`
(al massimo una commissione per prenotazione), `commission_record.
importo_eur >= 0`, `commission_record.percentuale` in `[0, 1]`.

## Uso — offline, senza database (`InMemoryBookingRepository`)

```powershell
python -c "
from datetime import datetime, UTC
from contracts import BookingRequest
from marketplace import (
    InMemoryBookingRepository, request_booking, confirm_booking,
    ExperienceNotBookableError,
)

repo = InMemoryBookingRepository()
richiesta = BookingRequest(
    person_id='turista-pseudonimo-1',
    experience_id='esperienza-liuteria-1',
    quando=datetime.now(UTC),
)

prenotazione = request_booking(repo, richiesta, prezzo_eur=20.0, prenotabile=True)
print('creata:', prenotazione.id, prenotazione.stato.value)
print('commissione prima della conferma:', repo.get_commission(prenotazione.id))  # None

confermata = confirm_booking(repo, prenotazione.id)
print('confermata:', confermata.stato.value)
print('commissione dopo la conferma:', repo.get_commission(prenotazione.id))
"
```

Una richiesta su un'esperienza non prenotabile è rifiutata subito, senza
persistere nulla:

```powershell
python -c "
from datetime import datetime, UTC
from contracts import BookingRequest
from marketplace import InMemoryBookingRepository, request_booking, ExperienceNotBookableError

repo = InMemoryBookingRepository()
richiesta = BookingRequest(
    person_id='turista-pseudonimo-1', experience_id='esperienza-non-prenotabile',
    quando=datetime.now(UTC),
)
try:
    request_booking(repo, richiesta, prezzo_eur=20.0, prenotabile=False)
except ExperienceNotBookableError as e:
    print('rifiutata:', e)
"
```

## Uso — con `DATABASE_URL` (Neon o Postgres locale): persiste DAVVERO

Il cablaggio è identico nei due profili — cambia solo il `.env`
(`.env.example` per Neon, `.env.local.example` per Postgres locale via
Docker, alla radice del repo). Nessun `if local/cloud` nel codice.

```powershell
python -c "
from marketplace import PostgresBookingRepository
repo = PostgresBookingRepository.from_env()   # legge DATABASE_URL dal .env
"
```

## Verifica end-to-end — il comando PowerShell ESATTO

```powershell
cd services\marketplace

# Variabili dal .env alla radice del repo.
$envFile = Get-Content ..\..\.env | Where-Object { $_ -match '^\s*[A-Z_]+=' }
foreach ($line in $envFile) {
    $key, $value = $line -split '=', 2
    Set-Item -Path "Env:$($key.Trim())" -Value $value.Trim().Trim('"')
}

# MIGRATE + VERIFY in un solo comando: applica lo schema (idempotente),
# richiede una prenotazione d'esempio, dimostra che nessuna commissione
# esiste prima della conferma, conferma, rilegge da un repository NUOVO
# (prova di persistenza reale) e verifica aritmeticamente la commissione.
python -m marketplace.migrate
python -m marketplace.verify
```

Rilancia SOLO `verify` — anche dopo aver chiuso il terminale, riavviato il
notebook, o su un altro giorno: la prenotazione d'esempio
(`booking-verify-persistenza`) e la sua commissione compaiono ANCORA al
passo 5 della CLI ("persisteva GIÀ da una corsa precedente"). Se invece
sparissero, la persistenza sarebbe rotta.

## Test

```powershell
pytest services/marketplace/tests
```

Segue lo stesso pattern di `services/urban-memory/tests`: i test di
`PostgresBookingRepository` (persistenza reale, migrazione idempotente,
`CHECK` del DB, rilettura via `repo.get`/`repo.get_commission`) usano un
Postgres effimero avviato al volo dalla suite; se Postgres non è installato
in macchina, quei test sono **saltati**, non falliti. I test di dominio
(`request_booking`, `confirm_booking`, il vincolo "nessuna commissione prima
della conferma", l'idempotenza della conferma) girano sempre, con
`InMemoryBookingRepository`, senza bisogno di un database.
