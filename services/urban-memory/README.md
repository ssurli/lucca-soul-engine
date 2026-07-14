# Lucca Soul — Urban Memory (`services/urban-memory`)

Il fossato difendibile del progetto: contenuto che nessun concorrente può
acquisire dall'esterno, perché nasce solo dalla partecipazione — i racconti
degli anziani, i saperi artigiani, il dialetto, le botteghe che chiudono. Non
è un archivio da riempire una volta con un progetto finanziato: **cresce con
l'uso**. Ogni esperienza vissuta può generare un `MemoryContribution`. Import
name del pacchetto: `urban_memory` (nome distribuzione: `lucca-urban-memory`).

## Regole non negoziabili

Applicate in un solo punto verificabile, `urban_memory.service` (CLAUDE.md,
`docs/DATA_CONTRACTS.md` §4):

- **Consenso.** `MemoryContribution.consenso` deve essere `True` per
  persistere. Nessuna eccezione: `submit_contribution` solleva
  `ConsentRequiredError` altrimenti.
- **Licenza.** Sempre tracciata ed esplicita (es. `CC-BY-SA-4.0`): un
  contributo senza licenza chiara è un debito legale, non un asset.
  `LicenseRequiredError` se vuota o solo whitespace.
- **Pseudonimo.** `contributor_id` è obbligatorio e non vuoto: il contributo
  si firma con un nome scelto, mai con PII. `PseudonymRequiredError`
  altrimenti.
- **Curatela prima della pubblicazione.** `curato` è sempre forzato a
  `False` alla creazione — nessuna auto-pubblicazione. Solo dopo
  `curate_contribution` il contributo compare in `get_curated`/
  `contributions_for_place`: la memoria di una città non si pubblica grezza.
- **Nessun log del contenuto.** Il servizio non chiama mai `print`/`logging`
  sul payload di un contributo (`testo`, `media_uri`, `contributor_id`).
- **Aggancio al grafo.** Ogni contributo si collega al Knowledge Graph con
  `(:Memoria)-[:RIGUARDA]->(:Luogo|:Bottega|:Artista)`
  (`urban_memory.graph_link.riguarda_to_cypher`): la memoria arricchisce il
  grafo, non vive a lato.
- **Persiste davvero.** `PostgresMemoryRepository` scrive su Postgres reale
  (Neon in cloud, `sslmode=require`; Postgres locale sul PC fisso — stesso
  codice, cambia solo il DSN): il contributo sopravvive al riavvio del
  processo. I due vincoli non negoziabili (consenso, licenza) sono ribaditi
  ANCHE a livello DB con `CHECK` — difesa in profondità, non solo
  applicativa.

## Installazione (PowerShell, Windows)

Dalla radice del repo. `packages/contracts` è la single source of truth
degli schemi (`MemoryContribution`, `MemoryKind`, `PersonKind`...) ed è una
dipendenza locale (non su un indice pip): va installata a parte, insieme a
questo pacchetto, in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/urban-memory
```

## Moduli

- `urban_memory/repository.py` — `MemoryRepository` (Protocol):
  `submit`/`get_curated`/`list_pending`/`curate`.
  - `InMemoryMemoryRepository` — dizionario in-process. **Percorso usato dai
    test e finché `DATABASE_URL` non è configurato.**
  - `PostgresMemoryRepository(dsn)` — Neon (`sslmode=require` in cloud) o
    Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
    cambia solo il DSN. **Persiste davvero**: una connessione (e una
    transazione) per operazione, nessuno stato tenuto in RAM tra una
    chiamata e l'altra — il contributo sopravvive al riavvio del processo.
    Ogni errore psycopg è mappato in `MemoryStorageError` (infrastrutturale,
    NON un `UrbanMemoryError` di dominio). `PostgresMemoryRepository.
    from_env()` legge `DATABASE_URL` dal `.env` (radice del repo) o
    dall'ambiente di processo. Richiede lo schema applicato una volta (vedi
    "Migrazione" sotto).
- `urban_memory/migrate.py` — `migrate(dsn)`: applica lo schema idempotente
  `sql/00_memory_schema.sql` (`CREATE TABLE`/`INDEX ... IF NOT EXISTS`,
  nessun `DROP`). Anche come CLI: `python -m urban_memory.migrate` (legge
  `DATABASE_URL` dal `.env`).
- `urban_memory/service.py` — la logica di dominio: `submit_contribution`,
  `curate_contribution` (alias `publish_pending`), `pending_contributions`,
  `contributions_for_place`. Le eccezioni dedicate: `ConsentRequiredError`,
  `LicenseRequiredError`, `PseudonymRequiredError` (tutte sottoclassi di
  `UrbanMemoryError`).
- `urban_memory/graph_link.py`:
  - `riguarda_to_cypher(contribution) -> (query, params)`: funzione
    **pura**, non esegue nulla contro Neo4j. La query è versionata in
    `cypher/30_memory_link.cypher` (letta da file: unica fonte di verità,
    non duplicata come stringa nel codice).
  - `link_to_graph(contribution, *, driver=None)` / `Neo4jMemoryLinker` —
    ESEGUONO quella query davvero, contro Aura (`neo4j+s://`) o Neo4j locale
    (`bolt://`): lo schema dell'URI dipende solo da `NEO4J_URI` (`.env`),
    mai da un `if local/cloud` nel codice. Senza `driver` esplicito, apre e
    chiude un driver da `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
    `NEO4J_DATABASE`.
- `urban_memory/verify.py` — CLI di verifica end-to-end (`python -m
  urban_memory.verify`): migra → conferisce → cura → rilegge da un
  repository nuovo → (se `NEO4J_URI` è presente) aggancia al grafo. Pensata
  per essere lanciata due volte: la seconda corsa deve trovare lo stesso
  contributo ancora lì.

## Migrazione dello schema (una tantum, idempotente)

```powershell
$env:DATABASE_URL = "postgresql://...neon.tech/...?sslmode=require"   # o Postgres locale
python -m urban_memory.migrate
```

Rieseguibile in sicurezza da zero (nessun `DROP`, solo `CREATE ... IF NOT
EXISTS`): stesso principio del seed del grafo. Applica
`sql/00_memory_schema.sql`, che include due `CHECK` non aggirabili nemmeno
da un INSERT diretto: `consenso = true` e `char_length(licenza) >= 1`.

## Uso — offline, senza database (`InMemoryMemoryRepository`)

```powershell
python -c "
from datetime import datetime
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import (
    InMemoryMemoryRepository, submit_contribution, curate_contribution,
    contributions_for_place, ConsentRequiredError,
)

repo = InMemoryMemoryRepository()

contributo = MemoryContribution(
    id='mem-demo-1',
    kind=MemoryKind.RACCONTO,
    testo='Il racconto di una bottega di liuteria, tramandato in famiglia.',
    riguarda=['bottega-liuteria-1'],
    contributor_id='nonna-lucia',
    contributor_kind=PersonKind.CITTADINO,
    consenso=True,
    licenza='CC-BY-SA-4.0',
    creato_il=datetime.now(),
)

submit_contribution(repo, contributo)
print('curati prima della curatela:', contributions_for_place(repo, 'bottega-liuteria-1'))

curate_contribution(repo, contributo.id)
print('curati dopo la curatela:', [c.id for c in contributions_for_place(repo, 'bottega-liuteria-1')])
"
```

Un contributo senza consenso è rifiutato subito, senza persistere nulla:

```powershell
python -c "
from datetime import datetime
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import InMemoryMemoryRepository, submit_contribution, ConsentRequiredError

repo = InMemoryMemoryRepository()
contributo = MemoryContribution(
    id='mem-senza-consenso', kind=MemoryKind.FOTOGRAFIA, riguarda=['bottega-1'],
    contributor_id='qualcuno', contributor_kind=PersonKind.TURISTA,
    consenso=False, licenza='CC-BY-4.0', creato_il=datetime.now(),
)
try:
    submit_contribution(repo, contributo)
except ConsentRequiredError as e:
    print('rifiutato:', e)
"
```

## Uso — con `DATABASE_URL` (Neon o Postgres locale): persiste DAVVERO

Il cablaggio è identico nei due profili — cambia solo il `.env`
(`.env.example` per Neon, `.env.local.example` per Postgres locale via
Docker, alla radice del repo). Nessun `if local/cloud` nel codice:
`sslmode=require` (Neon) o una stringa locale dipendono solo dal valore di
`DATABASE_URL`.

```powershell
python -c "
from urban_memory import PostgresMemoryRepository
repo = PostgresMemoryRepository.from_env()   # legge DATABASE_URL dal .env
"
```

## Aggancio al grafo

`riguarda_to_cypher` produce solo `(query, params)` (pura, non esegue
nulla). `link_to_graph`/`Neo4jMemoryLinker` la eseguono davvero contro Neo4j
(Aura `neo4j+s://` o locale `bolt://`, dal `.env`):

```powershell
python -c "
from datetime import datetime
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import riguarda_to_cypher, Neo4jMemoryLinker

contributo = MemoryContribution(
    id='mem-demo-1', kind=MemoryKind.MESTIERE,
    riguarda=['bottega-liuteria-1', 'artista-puccini'],
    contributor_id='voce-del-borgo', contributor_kind=PersonKind.CITTADINO,
    consenso=True, licenza='CC-BY-SA-4.0', creato_il=datetime.now(), curato=True,
)
query, params = riguarda_to_cypher(contributo)
print(query); print(params)

# Esecuzione live contro Neo4j (Aura o locale, da NEO4J_URI nel .env):
with Neo4jMemoryLinker.from_env() as linker:
    linker.link(contributo)
    print('nodi :Memoria / relazioni :RIGUARDA nel grafo:', linker.count_memoria())
"
```

## Verifica di persistenza — comandi PowerShell ESATTI

Dimostra che un contributo conferito ORA è ancora leggibile DOPO un riavvio
(un'altra corsa dello stesso comando, o il PC riacceso): il `DATABASE_URL`
punta a Neon (o al Postgres locale), quindi non c'è alcun processo Python da
tenere vivo tra le due corse.

```powershell
cd services\urban-memory

# 1. Variabili dal .env alla radice del repo (Neon in cloud: sslmode=require
#    è già dentro la stringa; NEO4J_URI è opzionale, se assente la CLI salta
#    solo il passo 5 e verifica comunque la persistenza su Postgres).
$envFile = Get-Content ..\..\.env | Where-Object { $_ -match '^\s*[A-Z_]+=' }
foreach ($line in $envFile) {
    $key, $value = $line -split '=', 2
    Set-Item -Path "Env:$($key.Trim())" -Value $value.Trim().Trim('"')
}

# 2. Migrazione (una tantum, idempotente: sicura anche se già applicata).
python -m urban_memory.migrate

# 3. Conferisci -> cura -> rileggi -> (se NEO4J_URI c'è) aggancia al grafo.
python -m urban_memory.verify
```

Rilancia SOLO il passo 3 (`python -m urban_memory.verify`) — anche dopo aver
chiuso il terminale, riavviato il notebook, o su un altro giorno: il
contributo d'esempio (`mem-verify-persistenza`) compare ANCORA al passo 4
della CLI ("TROVATO — la memoria è ANCORA presente dopo la riapertura della
connessione"). Se invece sparisse, la persistenza sarebbe rotta — è
esattamente ciò che questa CLI verifica.

## Test

```powershell
pytest services/urban-memory/tests
```

I test di `PostgresMemoryRepository` (persistenza reale, migrazione
idempotente, `CHECK` del DB) usano un Postgres 16 **effimero** avviato al
volo dalla suite stessa (`tests/conftest.py`: `initdb` + `pg_ctl` in una
directory temporanea, auth `trust`, solo locale) — nessun `DATABASE_URL`
da impostare per farli girare, e nessun impatto su Neon. Se Postgres 16 non
è installato in macchina, quei test sono **saltati** (`pytest.skip`), non
falliti; i test di `urban_memory.graph_link` con driver Neo4j finto girano
sempre, senza bisogno di un Neo4j vero.
