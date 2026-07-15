"""Aggancio della Urban Memory al Knowledge Graph.

Ogni contributo curato si aggancia al grafo con `(:Memoria)-[:RIGUARDA]->
(:Luogo|:Bottega|:Artista)` (docs/DATA_CONTRACTS.md §2, §4): la memoria
ARRICCHISCE il grafo, non vive a lato.

L'aggancio è ATOMICO: prima di creare qualunque nodo `:Memoria`, il grafo
viene verificato. Se anche un solo id in `contribution.riguarda` non esiste
come `:Luogo`/`:Bottega`/`:Artista`, NON si crea nulla — mai un nodo
`:Memoria` orfano. È la correzione di un bug reale osservato su Aura: senza
questo controllo, un id inesistente produceva in silenzio un nodo `:Memoria`
con ZERO relazioni, un fallimento travestito da successo. Verifica e
scrittura girano nella STESSA transazione Neo4j (`Session.execute_write`):
se la verifica fallisce, la funzione di transazione solleva PRIMA di
scrivere, ed `execute_write` fa rollback — nessuno stato intermedio resta.

Tre livelli, come `graph.source` (`services/graph`, fuori dal perimetro di
questo servizio, ma stesso pattern):

- `riguarda_check_cypher` / `riguarda_to_cypher` sono funzioni PURE: nessun
  driver, nessuna connessione, nessuna sessione. Producono solo
  `(query, params)`, deterministiche e testabili in isolamento. Le query
  eseguite sono le stesse, e le sole, versionate in
  `services/urban-memory/cypher/30_memory_link_check.cypher` e
  `30_memory_link_write.cypher` (lette da file, non duplicate come stringa
  nel codice: non possono divergere da sé stesse).
- `_link_transaction` è la funzione di transazione: verifica, poi (solo se
  tutto esiste) scrive. Non è pubblica: la sua unica porta d'ingresso è
  `link_to_graph`.
- `link_to_graph` / `Neo4jMemoryLinker` ESEGUONO tutto questo contro un
  driver Neo4j vero (Aura `neo4j+s://` o locale `bolt://`, secondo la
  stringa in `NEO4J_URI`: nessun `if local/cloud`). Nei test si passa un
  driver/sessione/transazione FINTI (nessuna connessione reale in `tests/`).

`Neo4jMemoryLinker.targets_mancanti` riusa la STESSA query di verifica
(sola lettura, non scrive nulla) fuori dal contesto di un aggancio: è il
`target_checker` che `urban_memory.service.curate_contribution`/
`publish_pending` e `urban_memory.audit` usano per verificare l'esistenza
dei target ALLA CURATELA (decisione architetturale: il conferimento non
deve mai dipendere dalla disponibilità del grafo — vedi `urban_memory.
service`). `target_checker_from_env` è il modo comodo di costruirne uno da
`.env`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from contracts import MemoryContribution

from ._env import neo4j_config_from_env

__all__ = [
    "riguarda_to_cypher",
    "riguarda_check_cypher",
    "MEMORY_LINK_CHECK_QUERY_PATH",
    "MEMORY_LINK_WRITE_QUERY_PATH",
    "MemoryLinkError",
    "link_to_graph",
    "Neo4jMemoryLinker",
    "target_checker_from_env",
]

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
MEMORY_LINK_CHECK_QUERY_PATH = _CYPHER_DIR / "30_memory_link_check.cypher"
MEMORY_LINK_WRITE_QUERY_PATH = _CYPHER_DIR / "30_memory_link_write.cypher"


class MemoryLinkError(Exception):
    """L'aggancio al grafo non può avvenire — NESSUN nodo `:Memoria` è stato
    creato. NON è una sottoclasse di `urban_memory.service.UrbanMemoryError`
    (quella famiglia riguarda i vincoli sul CONTRIBUTO stesso: consenso,
    licenza, pseudonimo): questa riguarda lo STATO DEL GRAFO al momento
    dell'aggancio — un id in `riguarda` che non esiste (ancora, o più) come
    `:Luogo`/`:Bottega`/`:Artista`, o una `riguarda` vuota arrivata fin qui
    nonostante il contratto la vieti.

    Sollevata SEMPRE prima di qualunque scrittura (vedi `_link_transaction`):
    quando arriva a chi chiama, nessun nodo `:Memoria` orfano è stato
    creato — è la garanzia che questa eccezione esiste per dare.
    """


def riguarda_to_cypher(contribution: MemoryContribution) -> tuple[str, dict[str, Any]]:
    """Query + parametri per SCRIVERE `contribution` nel Knowledge Graph
    (`30_memory_link_write.cypher`): produce `MERGE (m:Memoria {id: $id})`
    (idempotente: rieseguibile senza duplicare) e, per ogni id in
    `contribution.riguarda`, una relazione `MERGE (m)-[:RIGUARDA]->(target)`
    verso un nodo `Luogo`, `Bottega` o `Artista`.

    ATTENZIONE: questa funzione da sola NON verifica che i target esistano —
    è pura, non esegue nulla. La verifica (`riguarda_check_cypher`) e questa
    scrittura vanno eseguite IN QUESTO ORDINE, nella stessa transazione: è
    compito di `link_to_graph`/`_link_transaction`, non di questa funzione.
    Chiamarla direttamente senza aver prima verificato l'esistenza dei
    target può ricreare il bug che questo modulo corregge (un nodo
    `:Memoria` orfano se un target non esiste).

    Le proprietà scritte sul nodo `:Memoria` sono volutamente MINIME (kind,
    licenza, curato, contributor_kind, creato_il): il grafo porta il
    collegamento e ciò che serve a filtrare/etichettare, non il payload —
    `testo`/`media_uri` restano nella Urban Memory, non duplicati nel grafo;
    l'`id` è la chiave per andarli a recuperare da lì.

    Pura: non apre connessioni, non esegue nulla, non ha effetti collaterali
    oltre alla lettura (statica, non parametrica) del file `.cypher`
    versionato. Restituisce solo `(query, params)`.
    """
    query = MEMORY_LINK_WRITE_QUERY_PATH.read_text(encoding="utf-8")
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


def _check_query_and_params(ids: list[str]) -> tuple[str, dict[str, Any]]:
    """Query + parametri della verifica di esistenza (`30_memory_link_check.
    cypher`) per una lista di id NUDA — non richiede un `MemoryContribution`
    completo. Condivisa da `riguarda_check_cypher` (che la applica a
    `contribution.riguarda`) e da `Neo4jMemoryLinker.targets_mancanti` (che
    la applica a una lista arbitraria, fuori dal contesto di un aggancio):
    stessa query, una sola volta letta da file."""
    query = MEMORY_LINK_CHECK_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {"riguarda": list(ids)}
    return query, params


def riguarda_check_cypher(contribution: MemoryContribution) -> tuple[str, dict[str, Any]]:
    """Query + parametri per VERIFICARE che ogni id in `contribution.
    riguarda` esista nel grafo come `:Luogo`/`:Bottega`/`:Artista`
    (`30_memory_link_check.cypher`), PRIMA di scrivere alcunché. Pura come
    `riguarda_to_cypher`: non esegue nulla, produce solo `(query, params)`.

    Il record restituito dall'esecuzione ha una colonna `mancanti`: la lista
    (eventualmente vuota) degli id di `riguarda` che NON esistono con quei
    label. Lista vuota => si può procedere a `riguarda_to_cypher`.
    """
    return _check_query_and_params(contribution.riguarda)


# ---------------------------------------------------------------------------
# Esecuzione live contro Neo4j (Aura o locale) — stesso pattern di
# `graph.source.Neo4jCandidateSource` (services/graph)
# ---------------------------------------------------------------------------


class _Result(Protocol):
    """Sottoinsieme di `neo4j.Result` usato qui: solo `.single()` (un solo
    record atteso, sia dalla verifica sia da `count_memoria`)."""

    def single(self) -> Any: ...


class _Transaction(Protocol):
    """Sottoinsieme di `neo4j.ManagedTransaction` usato da
    `_link_transaction`: solo `.run(query, params)`. Un `Protocol` (non il
    tipo concreto) così un test può passare una transazione FINTA che
    registra query+parametri senza aprire nulla di reale."""

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result: ...


class _Session(Protocol):
    """Sottoinsieme di `neo4j.Session` usato qui: `.execute_write(...)` per
    l'aggancio ATOMICO (verifica + scrittura nella stessa transazione, con
    rollback automatico se la funzione di transazione solleva), `.run(...)`
    per la sola lettura di `Neo4jMemoryLinker.count_memoria` (fuori da
    qualunque scrittura, non necessita di una transazione gestita)."""

    def execute_write(self, transaction_function: Any, *args: Any, **kwargs: Any) -> Any: ...

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc_info: object) -> None: ...


class _Driver(Protocol):
    """Sottoinsieme di `neo4j.Driver` usato qui: solo `.session(database=...)`
    (e `.close()` per chi possiede il driver). Un `Protocol` per lo stesso
    motivo di `_Session`: testabile con un driver finto."""

    def session(self, database: str | None = None) -> _Session: ...

    def close(self) -> None: ...


def _link_transaction(tx: _Transaction, contribution: MemoryContribution) -> None:
    """Funzione di transazione per `Session.execute_write`: VERIFICA che
    ogni id in `contribution.riguarda` esista nel grafo, e SOLO se tutti
    esistono esegue la scrittura — nella STESSA transazione. Se la verifica
    trova anche un solo id mancante, solleva `MemoryLinkError` PRIMA di
    chiamare `riguarda_to_cypher`/eseguire qualunque `MERGE (m:Memoria...)`:
    `execute_write` fa rollback automaticamente sull'eccezione, quindi
    nessun nodo `:Memoria` orfano può restare — è la correzione del bug
    osservato su Aura.
    """
    check_query, check_params = riguarda_check_cypher(contribution)
    risultato = tx.run(check_query, check_params).single()
    mancanti = list(risultato["mancanti"]) if risultato is not None else list(contribution.riguarda)
    if mancanti:
        raise MemoryLinkError(
            f"target inesistenti nel grafo: {mancanti!r} — nodo :Memoria "
            f"NON creato (id={contribution.id!r})"
        )

    write_query, write_params = riguarda_to_cypher(contribution)
    tx.run(write_query, write_params)


def link_to_graph(
    contribution: MemoryContribution,
    *,
    driver: _Driver | None = None,
    database: str | None = None,
    dotenv_path: Path | None = None,
) -> None:
    """Aggancia `contribution` al grafo in modo ATOMICO: verifica che ogni
    id in `contribution.riguarda` esista come `:Luogo`/`:Bottega`/`:Artista`
    e SOLO allora crea/aggiorna il nodo `:Memoria` e le relazioni `RIGUARDA`
    (docs/DATA_CONTRACTS.md §2, §4) — nella stessa transazione
    (`_link_transaction`, via `Session.execute_write`). Se anche un solo
    target manca, solleva `MemoryLinkError` (che nomina gli id mancanti) e
    NON crea nulla: nessun nodo `:Memoria` orfano, mai.

    Difesa in profondità: se `contribution.riguarda` è vuoto, solleva
    `MemoryLinkError` SUBITO, prima di aprire o toccare qualunque driver/
    sessione (il contratto (`packages/contracts`) vieta già una `riguarda`
    vuota; questa funzione non si fida e rifiuta comunque).

    Nessun testo/PII finisce nel nodo: solo `kind`, `contributor_kind`,
    `licenza`, `curato`, `creato_il` e gli id di `riguarda` (vedi
    `riguarda_to_cypher`).

    Se `driver` non è passato, ne apre uno da `NEO4J_URI`/`NEO4J_USERNAME`/
    `NEO4J_PASSWORD`/`NEO4J_DATABASE` (dal `.env`, mai hardcoded: `neo4j+s://`
    per Aura o `bolt://` in locale dipendono solo dallo schema nella
    stringa) e lo chiude a fine chiamata. Se `driver` è passato — un driver
    FINTO nei test, o uno già aperto e condiviso da chi chiama (vedi
    `Neo4jMemoryLinker`) — il ciclo di vita resta di chi lo possiede: non
    viene chiuso qui.
    """
    if not contribution.riguarda:
        raise MemoryLinkError(
            "MemoryContribution.riguarda è vuoto: nessun target da "
            "agganciare nel grafo, nodo :Memoria NON creato "
            f"(id={contribution.id!r})."
        )

    driver_aperto_qui = driver is None
    if driver is None:
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        database = database or cfg.database
    database = database or "neo4j"

    try:
        with driver.session(database=database) as session:
            session.execute_write(_link_transaction, contribution)
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
        """Aggancia `contribution` al grafo, ATOMICAMENTE (vedi
        `link_to_graph`), riusando il driver posseduto da questa istanza
        (mai chiuso da `link_to_graph` in questo caso). Solleva
        `MemoryLinkError` — senza creare alcun nodo `:Memoria` — se un
        target in `riguarda` non esiste."""
        link_to_graph(contribution, driver=self._driver, database=self._database)

    def count_memoria(self) -> tuple[int, int]:
        """`(nodi :Memoria, relazioni :RIGUARDA uscenti da :Memoria)`: comodo
        per la CLI di verifica, per mostrare che l'aggancio è avvenuto
        davvero (e che non esistono `:Memoria` orfane)."""
        query = (
            "MATCH (m:Memoria) "
            "OPTIONAL MATCH (m)-[r:RIGUARDA]->() "
            "RETURN count(DISTINCT m) AS memorie, count(r) AS relazioni"
        )
        with self._driver.session(database=self._database) as session:
            record = session.run(query).single()
        return record["memorie"], record["relazioni"]

    def targets_mancanti(self, ids: list[str]) -> list[str]:
        """Quali id in `ids` NON esistono nel grafo come `:Luogo`/`:Bottega`/
        `:Artista` — riusa la STESSA query di verifica di `_link_transaction`
        (`30_memory_link_check.cypher`, `_check_query_and_params`): sola
        lettura, nessuna scrittura, nessuna transazione gestita (non serve:
        non modifica nulla).

        È il `target_checker` (`Callable[[list[str]], list[str]]`) che
        `urban_memory.service.curate_contribution`/`publish_pending` e
        `urban_memory.audit` usano — passalo direttamente come metodo
        legato: `curate_contribution(repo, id, target_checker=linker.
        targets_mancanti)`.
        """
        query, params = _check_query_and_params(ids)
        with self._driver.session(database=self._database) as session:
            record = session.run(query, params).single()
        return list(record["mancanti"]) if record is not None else list(ids)


_TargetChecker = Callable[[list[str]], list[str]]


@contextmanager
def target_checker_from_env(dotenv_path: Path | None = None) -> Iterator[_TargetChecker]:
    """Context manager comodo: apre un `Neo4jMemoryLinker` da `.env`
    (`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` — Aura
    `neo4j+s://` o locale `bolt://`, nessun `if local/cloud`) e cede un
    `target_checker` pronto — `Neo4jMemoryLinker.targets_mancanti`, con
    esattamente la firma richiesta da `urban_memory.service.
    curate_contribution`/`publish_pending`. Chiude il driver all'uscita del
    blocco `with` — anche se avvengono più chiamate al checker dentro
    (`urban_memory.audit` ne fa molte sullo stesso driver, aperto una volta
    sola; `urban_memory.verify` ne fa una).

    Uso::

        with target_checker_from_env() as target_checker:
            curate_contribution(repo, memory_id, target_checker=target_checker)
    """
    with Neo4jMemoryLinker.from_env(dotenv_path) as linker:
        yield linker.targets_mancanti
