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
- **Aggancio al grafo, ATOMICO.** Ogni contributo si collega al Knowledge
  Graph con `(:Memoria)-[:RIGUARDA]->(:Luogo|:Bottega|:Artista)`
  (`urban_memory.graph_link`). Prima di creare il nodo `:Memoria`, il grafo
  viene VERIFICATO: se anche un solo id in `riguarda` non esiste, NON si
  crea nulla — `MemoryLinkError` lo nomina esplicitamente. Verifica e
  scrittura girano nella stessa transazione Neo4j (`Session.execute_write`):
  mai un nodo `:Memoria` orfano (bug reale corretto, osservato su Aura — un
  id inesistente creava in silenzio una Memoria con zero relazioni).
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
  `submit`/`get_curated`/`list_pending`/`curate`/`get`.
  - `get(memory_id) -> MemoryContribution | None` rilegge un contributo
    COSÌ COM'È persistito (curato o no; `None` se non esiste) — un lookup,
    non un comando. Usato da `urban_memory.verify` per non assumere mai che
    un passo precedente sia riuscito, e da `urban_memory.link` per
    riagganciare al grafo il dato REALMENTE persistito.
  - `InMemoryMemoryRepository` — dizionario in-process. **Percorso usato dai
    test e finché `DATABASE_URL` non è configurato.**
  - `PostgresMemoryRepository(dsn)` — Neon (`sslmode=require` in cloud) o
    Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
    cambia solo il DSN. **Persiste davvero**: una connessione (e una
    transazione) per operazione, nessuno stato tenuto in RAM tra una
    chiamata e l'altra — il contributo sopravvive al riavvio del processo.
    Ogni errore psycopg (anche in `get`) è mappato in `MemoryStorageError`
    (infrastrutturale, NON un `UrbanMemoryError` di dominio).
    `PostgresMemoryRepository.from_env()` legge `DATABASE_URL` dal `.env`
    (radice del repo) o dall'ambiente di processo. Richiede lo schema
    applicato una volta (vedi "Migrazione" sotto).
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
  - `riguarda_check_cypher(contribution) -> (query, params)` e
    `riguarda_to_cypher(contribution) -> (query, params)`: funzioni
    **pure**, non eseguono nulla contro Neo4j. Le query sono versionate in
    `cypher/30_memory_link_check.cypher` (verifica di esistenza) e
    `cypher/30_memory_link_write.cypher` (scrittura) — lette da file: unica
    fonte di verità, non duplicate come stringa nel codice.
  - `link_to_graph(contribution, *, driver=None)` / `Neo4jMemoryLinker` —
    ESEGUONO le due query davvero, contro Aura (`neo4j+s://`) o Neo4j
    locale (`bolt://`): lo schema dell'URI dipende solo da `NEO4J_URI`
    (`.env`), mai da un `if local/cloud` nel codice. **ATOMICO**: verifica
    poi scrive, nella STESSA transazione (`Session.execute_write`); se un
    id in `riguarda` manca, solleva `MemoryLinkError` (lo nomina) e non
    scrive nulla — nessun nodo `:Memoria` orfano. Rifiuta anche una
    `riguarda` vuota, con lo stesso errore, prima di aprire qualunque
    sessione. Senza `driver` esplicito, apre e chiude un driver da
    `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE`.
- `urban_memory/verify.py` — CLI di verifica end-to-end (`python -m
  urban_memory.verify`): migra → conferisce → cura → rilegge da un
  repository nuovo → (se `NEO4J_URI` è presente) aggancia al grafo. RIESE-
  GUIBILE ALL'INFINITO: ogni passo legge PRIMA lo stato reale (`repo.get`)
  invece di assumere che il passo precedente sia riuscito — un
  `MemoryStorageError` in un punto qualunque è SEMPRE "FALLITO" ed exit 1,
  mai scambiato per "id già presente" (bug corretto: prima confondeva "il
  DB non risponde" con "il DB ha già la riga").
- `urban_memory/link.py` — CLI dedicata SOLO all'aggancio al grafo
  (`python -m urban_memory.link [memory_id]`), a valle di `verify`: rilegge
  il contributo DA POSTGRES (mai un oggetto ricostruito in memoria) e lo
  aggancia, stampando il conteggio `:Memoria`/`:RIGUARDA` prima e dopo.
  Esiste perché un fatto osservato in produzione ha mostrato che `verify`
  può persistere su Postgres SENZA che l'aggancio al grafo sia mai avvenuto
  (es. `NEO4J_URI` assente in quella corsa) — questo comando lo esegue (o
  rieffettua) in isolamento, e con `--controprova` dimostra, SENZA toccare
  Postgres, che un target inesistente fa fallire l'aggancio con
  `MemoryLinkError` senza creare nulla.

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

`riguarda_check_cypher`/`riguarda_to_cypher` producono solo `(query,
params)` (pure, non eseguono nulla). `link_to_graph`/`Neo4jMemoryLinker` le
eseguono davvero contro Neo4j (Aura `neo4j+s://` o locale `bolt://`, dal
`.env`), ATOMICAMENTE — usa un id REALE del seed (`liuteria-lucchese`, non
un id inventato: un id inesistente fa sollevare `MemoryLinkError`, per
design, senza creare nulla):

```powershell
python -c "
from datetime import datetime
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import riguarda_to_cypher, Neo4jMemoryLinker, MemoryLinkError

contributo = MemoryContribution(
    id='mem-demo-1', kind=MemoryKind.MESTIERE,
    riguarda=['liuteria-lucchese'],  # id REALE del seed (services/graph/graph/seed_lucca.py)
    contributor_id='voce-del-borgo', contributor_kind=PersonKind.CITTADINO,
    consenso=True, licenza='CC-BY-SA-4.0', creato_il=datetime.now(), curato=True,
)
query, params = riguarda_to_cypher(contributo)
print(query); print(params)

# Esecuzione live contro Neo4j (Aura o locale, da NEO4J_URI nel .env),
# ATOMICA: se 'liuteria-lucchese' non esistesse ancora nel grafo di
# destinazione (seed non applicato), MemoryLinkError lo dice esplicitamente
# e NESSUN nodo :Memoria viene creato — mai un nodo orfano.
try:
    with Neo4jMemoryLinker.from_env() as linker:
        linker.link(contributo)
        print('nodi :Memoria / relazioni :RIGUARDA nel grafo:', linker.count_memoria())
except MemoryLinkError as e:
    print('aggancio rifiutato, nessun nodo creato:', e)
"
```

## Pulizia di un nodo `:Memoria` orfano (bug storico, già corretto)

Prima di questa correzione, un id in `riguarda` inesistente nel grafo
produceva in silenzio un nodo `:Memoria` SENZA alcuna relazione `RIGUARDA`
(osservato su Aura reale). Il codice ora lo impedisce (`link_to_graph` è
atomico: verifica prima, scrive poi, nella stessa transazione), ma un nodo
orfano creato PRIMA della correzione resta nel grafo finché non viene
rimosso a mano. Da eseguire una tantum contro Aura (Neo4j Browser, `cypher-
shell`, o `session.run` da Python):

```cypher
MATCH (m:Memoria) WHERE NOT (m)-[:RIGUARDA]->() DETACH DELETE m
```

`DETACH DELETE` è prudenziale: elimina anche eventuali relazioni ENTRANTI
sul nodo (nel nostro schema `:Memoria` non ne ha mai in ingresso, solo
`RIGUARDA` in uscita — ma se in futuro qualcosa collegasse un altro nodo
*a* una Memoria, `DETACH` evita comunque un errore "nodo con relazioni
pendenti", senza toccare NESSUN altro nodo). Il filtro `WHERE NOT
(m)-[:RIGUARDA]->()` è MIRATO: colpisce solo le `:Memoria` senza alcuna
relazione `RIGUARDA` uscente (gli unici nodi orfani possibili con questo
schema) — una `:Memoria` curata e correttamente agganciata non viene mai
toccata.

## Verifica end-to-end — i TRE comandi PowerShell ESATTI

Tre comandi separati DI PROPOSITO: il primo prepara lo schema, il secondo
dimostra la persistenza su Postgres, il terzo dimostra (e riverifica, in
isolamento) l'aggancio al Knowledge Graph — così un fallimento del terzo
(l'aggancio) non si confonde MAI con un fallimento del secondo (la
persistenza): è esattamente la distinzione che il fatto osservato in
produzione (riga presente su Neon, ma 0 nodi `:Memoria` su Aura) ha reso
necessaria.

`urban_memory.verify`/`urban_memory.link` usano
`PLACE_ID_ESEMPIO = "liuteria-lucchese"` — un id REALE del seed del grafo
(`services/graph/graph/seed_lucca.py`; le altre botteghe: `ceramica-lucca`,
`stamperia-lucca`, `pasticceria-storica`, `tessitura-lucca`). Se il seed non
è ancora stato applicato ad Aura, applicalo prima con `python -m
graph.loader` (`services/graph`) — altrimenti il comando 3 solleva
`MemoryLinkError` per design (nessun nodo `:Memoria` orfano), anche con
l'id giusto.

```powershell
cd services\urban-memory

# 0. Variabili dal .env alla radice del repo (Neon in cloud: sslmode=require
#    è già dentro la stringa; NEO4J_URI è opzionale per il comando 2, ma
#    OBBLIGATORIA per il comando 3).
$envFile = Get-Content ..\..\.env | Where-Object { $_ -match '^\s*[A-Z_]+=' }
foreach ($line in $envFile) {
    $key, $value = $line -split '=', 2
    Set-Item -Path "Env:$($key.Trim())" -Value $value.Trim().Trim('"')
}

# 1. MIGRATE — schema idempotente (sicuro anche se già applicato).
python -m urban_memory.migrate

# 2. VERIFY — conferisci -> cura -> rileggi da un repository NUOVO (prova di
#    persistenza su Postgres). Se NEO4J_URI è presente prova ANCHE l'aggancio,
#    ma NON è la fonte di verità per il grafo: usa il comando 3 per quello.
python -m urban_memory.verify

# 3. LINK — aggancio al grafo, in isolamento, sul contributo REALMENTE
#    persistito al passo 2 (rilettura via repo.get, mai un oggetto
#    ricostruito in memoria). Stampa il conteggio :Memoria/:RIGUARDA PRIMA
#    e DOPO: se resta 0/0, l'aggancio non è avvenuto — mai un "OK" silenzioso.
python -m urban_memory.link mem-verify-persistenza
```

Rilancia SOLO il comando 2 (`verify`) — anche dopo aver chiuso il terminale,
riavviato il notebook, o su un altro giorno: il contributo d'esempio
(`mem-verify-persistenza`) compare ANCORA al passo 4 della CLI ("TROVATO...
persisteva GIÀ da una corsa precedente"). Se invece sparisse, la persistenza
sarebbe rotta.

Rilancia SOLO il comando 3 (`link`) per riverificare (o rieseguire) SOLO
l'aggancio — è idempotente (`MERGE`): rieseguirlo su un contributo già
agganciato non duplica nulla, il conteggio "dopo" resta lo stesso.

**Controprova del fallimento forte** (dimostra che un target inesistente fa
fallire l'aggancio DAVVERO, senza creare nulla — SENZA toccare Postgres,
richiede solo `NEO4J_URI`):

```powershell
python -m urban_memory.link --controprova
```

Output atteso: `CONTROPROVA SUPERATA: errore esplicito, nessun nodo creato.`
(exit code `0`). Se invece stampa `CONTROPROVA FALLITA` (exit code `1`), il
linker ha smesso di rifiutare un target inesistente — una regressione del
bug corretto in questa wave, da trattare come un incidente.

## Test

```powershell
pytest services/urban-memory/tests
```

I test di `PostgresMemoryRepository` e `urban_memory.link` (persistenza
reale, migrazione idempotente, `CHECK` del DB, rilettura via `repo.get`)
usano un Postgres 16 **effimero** avviato al volo dalla suite stessa
(`tests/conftest.py`: `initdb` + `pg_ctl` in una directory temporanea, auth
`trust`, solo locale) — nessun `DATABASE_URL` da impostare per farli girare,
e nessun impatto su Neon. Se Postgres 16 non è installato in macchina, quei
test sono **saltati** (`pytest.skip`), non falliti; i test di
`urban_memory.graph_link`/`urban_memory.link` con driver Neo4j FINTO
(`tests/_neo4j_fakes.py`, condiviso dai due moduli di test) girano sempre,
senza bisogno di un Neo4j vero.
