"""Aggancio della Urban Memory al Knowledge Graph.

Ogni contributo curato si aggancia al grafo con `(:Memoria)-[:RIGUARDA]->
(:Luogo|:Bottega|:Artista)` (docs/DATA_CONTRACTS.md §2, §4): la memoria
ARRICCHISCE il grafo, non vive a lato.

Due livelli, come `graph.source` (`services/graph`, fuori dal perimetro di
questo servizio, ma stesso pattern):

- `riguarda_to_cypher` è una funzione PURA: nessun driver, nessuna
  connessione, nessuna sessione. Produce solo `(query, params)`,
  deterministica e testabile in isolamento. La query eseguita è la stessa,
  e la sola, versionata in `services/urban-memory/cypher/30_memory_link.
  cypher` (letta da file, non duplicata come stringa nel codice: non può
  divergere da sé stessa).
- `link_to_graph` / `Neo4jMemoryLinker` ESEGUONO quella query contro un
  driver Neo4j vero (Aura `neo4j+s://` o locale `bolt://`, secondo la
  stringa in `NEO4J_URI`: nessun `if local/cloud`). Nei test si passa un
  driver/sessione FINTI (nessuna connessione reale in `tests/`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from contracts import MemoryContribution

from ._env import neo4j_config_from_env

__all__ = [
    "riguarda_to_cypher",
    "MEMORY_LINK_QUERY_PATH",
    "link_to_graph",
    "Neo4jMemoryLinker",
]

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
MEMORY_LINK_QUERY_PATH = _CYPHER_DIR / "30_memory_link.cypher"


def riguarda_to_cypher(contribution: MemoryContribution) -> tuple[str, dict[str, Any]]:
    """Query + parametri per agganciare `contribution` al Knowledge Graph.

    Produce SEMPRE `MERGE (m:Memoria {id: $id})` (idempotente: rieseguibile
    senza duplicare) e, per ogni id in `contribution.riguarda`, una
    relazione `MERGE (m)-[:RIGUARDA]->(target)` verso un nodo ESISTENTE
    `Luogo`, `Bottega` o `Artista` (non crea il target: se un id non esiste
    ancora nel grafo, quella riga dell'UNWIND semplicemente non produce
    alcuna relazione). Con `riguarda` vuoto la Memoria viene comunque
    creata/aggiornata, senza relazioni.

    Le proprietà scritte sul nodo `:Memoria` sono volutamente MINIME (kind,
    licenza, curato, contributor_kind, creato_il): il grafo porta il
    collegamento e ciò che serve a filtrare/etichettare, non il payload —
    `testo`/`media_uri` restano nella Urban Memory, non duplicati nel grafo;
    l'`id` è la chiave per andarli a recuperare da lì.

    Pura: non apre connessioni, non esegue nulla, non ha effetti collaterali
    oltre alla lettura (statica, non parametrica) del file `.cypher`
    versionato. Restituisce solo `(query, params)`.
    """
    query = MEMORY_LINK_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {
        "id": contribution.id,
        "kind": contribution.kind.value,
        "contributor_kind": contribution.contributor_kind.value,
        "licenza": contribution.licenza,
        "curato": contribution.curato,
        "creato_il": contribution.creato_il.isoformat(),
        "riguarda": list(contribution.riguarda),
    }
    return query, params


# ---------------------------------------------------------------------------
# Esecuzione live contro Neo4j (Aura o locale) — stesso pattern di
# `graph.source.Neo4jCandidateSource` (services/graph)
# ---------------------------------------------------------------------------


class _Session(Protocol):
    """Sottoinsieme di `neo4j.Session` usato qui: solo `.run(query, params)`.
    Un `Protocol` (non il tipo concreto `neo4j.Session`) così un test può
    passare una sessione FINTA che registra query+parametri senza aprire una
    connessione reale."""

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc_info: object) -> None: ...


class _Driver(Protocol):
    """Sottoinsieme di `neo4j.Driver` usato qui: solo `.session(database=...)`
    (e `.close()` per chi possiede il driver). Un `Protocol` per lo stesso
    motivo di `_Session`: testabile con un driver finto."""

    def session(self, database: str | None = None) -> _Session: ...

    def close(self) -> None: ...


def link_to_graph(
    contribution: MemoryContribution,
    *,
    driver: _Driver | None = None,
    database: str | None = None,
    dotenv_path: Path | None = None,
) -> None:
    """Esegue `riguarda_to_cypher(contribution)` contro Neo4j: crea/aggiorna
    il nodo `:Memoria` e le relazioni `RIGUARDA` (docs/DATA_CONTRACTS.md §2,
    §4) — la memoria ARRICCHISCE il grafo, non vive a lato. Nessun testo/PII
    finisce nel nodo: solo `kind`, `contributor_kind`, `licenza`, `curato`,
    `creato_il` e gli id di `riguarda` (vedi `riguarda_to_cypher`).

    Se `driver` non è passato, ne apre uno da `NEO4J_URI`/`NEO4J_USERNAME`/
    `NEO4J_PASSWORD`/`NEO4J_DATABASE` (dal `.env`, mai hardcoded: `neo4j+s://`
    per Aura o `bolt://` in locale dipendono solo dallo schema nella
    stringa) e lo chiude a fine chiamata. Se `driver` è passato — un driver
    FINTO nei test, o uno già aperto e condiviso da chi chiama (vedi
    `Neo4jMemoryLinker`) — il ciclo di vita resta di chi lo possiede: non
    viene chiuso qui.

    Idempotente quanto lo è `riguarda_to_cypher`: `MERGE`, rieseguibile
    senza duplicare né la Memoria né le relazioni.
    """
    query, params = riguarda_to_cypher(contribution)

    driver_aperto_qui = driver is None
    if driver is None:
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        database = database or cfg.database
    database = database or "neo4j"

    try:
        with driver.session(database=database) as session:
            session.run(query, params)
    finally:
        if driver_aperto_qui:
            driver.close()


class Neo4jMemoryLinker:
    """Wrapper comodo attorno a `link_to_graph`, stesso pattern di
    `graph.source.Neo4jCandidateSource`: possiede un driver Neo4j aperto una
    volta (non a ogni chiamata) e lo riusa per agganciare più contributi —
    utile per la CLI di verifica (`urban_memory.verify`) e per un futuro
    cablaggio nel BFF.
    """

    def __init__(self, driver: _Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Neo4jMemoryLinker:
        """Costruisce leggendo `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
        `NEO4J_DATABASE` dal `.env` (radice del repo) o dall'ambiente di
        processo. Nessun `if local/cloud`: Aura o locale dipendono solo dallo
        schema in `NEO4J_URI`."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        return cls(driver, database=cfg.database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jMemoryLinker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def link(self, contribution: MemoryContribution) -> None:
        """Aggancia `contribution` al grafo, riusando il driver posseduto da
        questa istanza (mai chiuso da `link_to_graph` in questo caso)."""
        link_to_graph(contribution, driver=self._driver, database=self._database)

    def count_memoria(self) -> tuple[int, int]:
        """`(nodi :Memoria, relazioni :RIGUARDA uscenti da :Memoria)`: comodo
        per la CLI di verifica, per mostrare che l'aggancio è avvenuto
        davvero."""
        query = (
            "MATCH (m:Memoria) "
            "OPTIONAL MATCH (m)-[r:RIGUARDA]->() "
            "RETURN count(DISTINCT m) AS memorie, count(r) AS relazioni"
        )
        with self._driver.session(database=self._database) as session:
            record = session.run(query).single()
        return record["memorie"], record["relazioni"]
