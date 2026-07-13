# Lucca Soul — Urban Knowledge Graph (`services/graph`)

Il grafo ragiona su RELAZIONI, non categorie: propone percorsi sorprendenti
(Puccini -> opera -> Teatro del Giglio -> liutaio -> violino). **Propone, non
decide**: sceglie solo l'AI Experience Engine (`services/experience-engine`).

Import name del pacchetto: `graph` (nome distribuzione: `lucca-graph`).

## Fonte di verità: `graph/seed_lucca.py`

Il dataset di Lucca (15 Luoghi, 5 Botteghe, 22 Esperienze, 4 Artisti, 13
Temi, relazioni `VICINO`/`LEGATO_A`) vive in un solo posto: `graph/
seed_lucca.py`. Da lì nascono DUE vie, sempre allineate:

1. **In-memory** — `graph.source.SeedCandidateSource` legge il dataset
   direttamente. È il percorso usato nei test e finché `NEO4J_URI` non è
   configurato.
2. **Cypher versionato** — `cypher/00_schema.cypher` e `cypher/
   01_seed_lucca.cypher` sono generati dal dataset e COMMITTATI: rigenerarli
   dopo una modifica al seed è

   ```powershell
   python -m graph.export_cypher
   ```

   Non modificare i file `.cypher` a mano: la fonte di verità resta
   `seed_lucca.py`.

Replicare il motore su un'altra città (Siena, Ferrara...) significa scrivere
un nuovo `graph/seed_<città>.py` con la stessa forma e rilanciare
`export_cypher`: la tecnologia (schema, query, loader) non cambia, cambia
solo il contenuto.

## Schema

Nodi: `Luogo`, `Artista`, `Bottega`, `Tema`, `Esperienza` (= `ExperienceNode`
di `packages/contracts`, non ridefinito qui). `Evento` e `Memoria` sono già
nel vincolo di unicità di `00_schema.cypher` ma non hanno seed in questa
wave (arrivano rispettivamente con i segnali reali e con
`urban-memory-engineer`, Wave 2).

Relazioni: `(:Artista)-[:LEGATO_A]->(:Luogo)`, `(:Luogo)-[:VICINO
{metri}]->(:Luogo)`, `(:Bottega)-[:OFFRE]->(:Esperienza)`,
`(:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)`, `(:Esperienza)-[:EVOCA]->(:Tema)`.

## Installazione (PowerShell, Windows)

Dalla radice del repo:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/graph
```

## Uso — candidati (senza Neo4j)

```powershell
python -c "
from datetime import time
from contracts import EmotionalProfile, Signal, VisitorContext
from graph.source import SeedCandidateSource

ctx = VisitorContext(
    person_id='visitor-demo',
    profile=EmotionalProfile(curiosita=0.8, contemplazione=0.3, arte=0.6, con_bambini=False, tempo_disponibile_min=180),
    signal=Signal(meteo='sereno', affollamento={}, stanchezza=0.1, ora=time(10, 0)),
)
for candidato in SeedCandidateSource().candidates(ctx)[:3]:
    print(candidato.experience.titolo, '->', candidato.connessioni)
"
```

## Popolare Neo4j (Aura o locale) — `make seed` equivalente

Compila il `.env` alla radice del repo (`NEO4J_URI`, `NEO4J_USERNAME`,
`NEO4J_PASSWORD`, `NEO4J_DATABASE` — vedi `.env.example` per Aura,
`.env.local.example` per Neo4j Community locale), poi da questa directory o
dalla radice del repo:

```powershell
python -m graph.loader
```

Esegue `cypher/00_schema.cypher` e `cypher/01_seed_lucca.cypher` in ordine.
Entrambi sono idempotenti (`CREATE CONSTRAINT ... IF NOT EXISTS`, `MERGE`):
è sicuro rilanciare il comando quante volte serve, anche da un'istanza Aura
Free ricreata da zero dopo la cancellazione per inattività.

## `Neo4jCandidateSource`

Stessa interfaccia (`CandidateSource.candidates(ctx) -> list[GraphCandidate]`)
via driver Neo4j ufficiale. URI/credenziali arrivano dal costruttore, mai
hardcoded:

```python
from graph.env import load_neo4j_config
from graph.source import Neo4jCandidateSource

config = load_neo4j_config()
with Neo4jCandidateSource.from_credentials(
    config.uri, config.username, config.password, config.database
) as source:
    candidati = source.candidates(ctx)
```

Nessun `if local/cloud` nel codice: `neo4j+s://` (Aura, TLS) o `bolt://`
(locale) dipendono solo dal valore di `NEO4J_URI` nel `.env`.

## Test

```powershell
pytest services/graph/tests
```
