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
    cambia solo il DSN. **Predisposta ma non ancora implementata** in questa
    wave (nessun database raggiungibile da qui): i metodi sollevano
    `NotImplementedError`. Lo schema di tabella atteso è documentato nella
    docstring della classe. `PostgresMemoryRepository.from_env()` legge
    `DATABASE_URL` dal `.env` (radice del repo) o dall'ambiente di processo.
- `urban_memory/service.py` — la logica di dominio: `submit_contribution`,
  `curate_contribution` (alias `publish_pending`), `pending_contributions`,
  `contributions_for_place`. Le eccezioni dedicate: `ConsentRequiredError`,
  `LicenseRequiredError`, `PseudonymRequiredError` (tutte sottoclassi di
  `UrbanMemoryError`).
- `urban_memory/graph_link.py` — `riguarda_to_cypher(contribution) ->
  (query, params)`: funzione **pura**, non esegue nulla contro Neo4j. La
  query è versionata in `cypher/30_memory_link.cypher` (letta da file: unica
  fonte di verità, non duplicata come stringa nel codice).

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

## Uso — con `DATABASE_URL` (Neon o Postgres locale)

`PostgresMemoryRepository` non è ancora implementata (vedi sopra): quando lo
sarà, il cablaggio sarà identico nei due profili — cambia solo il `.env`
(`.env.example` per Neon, `.env.local.example` per Postgres locale via
Docker, alla radice del repo):

```powershell
python -c "
from urban_memory import PostgresMemoryRepository
repo = PostgresMemoryRepository.from_env()   # legge DATABASE_URL dal .env
"
```

Nessun `if local/cloud` nel codice: `sslmode=require` (Neon) o una stringa
locale dipendono solo dal valore di `DATABASE_URL`.

## Aggancio al grafo — `riguarda_to_cypher`

```powershell
python -c "
from datetime import datetime
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import riguarda_to_cypher

contributo = MemoryContribution(
    id='mem-demo-1', kind=MemoryKind.MESTIERE,
    riguarda=['bottega-liuteria-1', 'artista-puccini'],
    contributor_id='voce-del-borgo', contributor_kind=PersonKind.CITTADINO,
    consenso=True, licenza='CC-BY-SA-4.0', creato_il=datetime.now(), curato=True,
)
query, params = riguarda_to_cypher(contributo)
print(query)
print(params)
"
```

## Test

```powershell
pytest services/urban-memory/tests
```
