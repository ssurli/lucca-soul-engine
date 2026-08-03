"""Scrittura della proprietà derivata `:Luogo.ultima_traccia_il`
(`docs/PROMOZIONE_TRACCIA.md` §2a) — innescata dal deposito di una traccia
nel ledger (`urban_memory.canale_fluttuante.sweep_and_fetch_active`), MAI in
una transazione condivisa con Postgres: "due scritture in due store diversi"
è la stessa natura di rischio già accettata altrove nel repo
(`urban_memory.graph_link`: la Memoria e il suo aggancio al grafo non
condividono una transazione con Postgres), non una garanzia nuova da
inventare qui. Se questa scrittura fallisce, il ledger append-only su
Postgres resta comunque la fonte di verità: `ultima_traccia_il` è una
proiezione best-effort, mai l'originale — una divergenza temporanea si
autocorregge alla prossima traccia depositata per lo stesso luogo.

Stesso pattern in tre livelli di `urban_memory.graph_link`:

- `ultima_traccia_cypher` è una funzione PURA: nessun driver, nessuna
  connessione, nessuna sessione. Produce solo `(query, params)`,
  deterministica e testabile in isolamento. La query eseguita è la sola
  versionata in `services/urban-memory/cypher/40_luogo_traccia_write.cypher`
  (letta da file, non duplicata come stringa nel codice).
- `scrivi_ultima_traccia` ESEGUE quella query contro un driver Neo4j vero
  (Aura `neo4j+s://` o locale `bolt://`, secondo lo schema in `NEO4J_URI`:
  nessun `if local/cloud`). Nei test si passa un driver/sessione finti
  (nessuna connessione reale in `tests/`).
- `Neo4jLuogoTracciaLinker` possiede un driver Neo4j aperto UNA VOLTA (non a
  ogni scrittura) e lo riusa — stesso pattern di
  `urban_memory.graph_link.Neo4jMemoryLinker`/`graph.source.
  Neo4jCandidateSource`: comodo per il BFF, che ne mantiene UNA istanza per
  l'intero ciclo di vita del processo (`api.deps.get_place_link_writer`).

A differenza dell'aggancio di una `MemoryContribution` (verifica-poi-scrivi,
nella stessa transazione: `_link_transaction`), qui NON c'è nulla da
verificare prima di scrivere: `ultima_traccia_cypher` produce un `MATCH`
(mai un `MERGE`), quindi un `place_id` inesistente nel grafo è semplicemente
un no-op innocuo (zero righe toccate), non un errore — nessuna transazione
gestita è necessaria (`Session.run`, non `Session.execute_write`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ._env import neo4j_config_from_env

__all__ = [
    "LUOGO_TRACCIA_WRITE_QUERY_PATH",
    "ultima_traccia_cypher",
    "LuogoTracciaLinkError",
    "scrivi_ultima_traccia",
    "Neo4jLuogoTracciaLinker",
]

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
LUOGO_TRACCIA_WRITE_QUERY_PATH = _CYPHER_DIR / "40_luogo_traccia_write.cypher"


def ultima_traccia_cypher(place_id: str, quando: datetime) -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `40_luogo_traccia_write.cypher`: nessuna
    connessione, nessuna esecuzione, nessun effetto collaterale oltre alla
    lettura statica del file `.cypher` versionato.

    `quando` è serializzato come ISO 8601 (`.isoformat()`) — stesso pattern
    di `graph_link.riguarda_to_cypher` per `creato_il`. Non validato
    tz-aware QUI (funzione pura, come `riguarda_to_cypher`): è compito di
    chi produce `quando` (`canale_fluttuante.sweep_and_fetch_active`, che lo
    riceve già tz-aware da `datetime.now(UTC)`)."""
    query = LUOGO_TRACCIA_WRITE_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {"place_id": place_id, "quando": quando.isoformat()}
    return query, params


class LuogoTracciaLinkError(Exception):
    """La scrittura di `ultima_traccia_il` non è riuscita — SEMPRE per un
    problema di RAGGIUNGIBILITÀ del grafo (connessione, autenticazione,
    timeout), MAI per un `:Luogo` mancante: la query è un `MATCH` (mai un
    `MERGE`), quindi un `place_id` inesistente produce un no-op silenzioso
    (zero righe toccate), non un'eccezione. Stesso principio della metà
    "grafo irraggiungibile" di `urban_memory.graph_link.MemoryLinkError`.
    """


class _Result(Protocol):
    def single(self) -> Any: ...


class _Session(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc_info: object) -> None: ...


class _Driver(Protocol):
    def session(self, database: str | None = None) -> _Session: ...

    def close(self) -> None: ...


def scrivi_ultima_traccia(
    place_id: str,
    quando: datetime,
    *,
    driver: _Driver | None = None,
    database: str | None = None,
    dotenv_path: Path | None = None,
) -> None:
    """Aggiorna `ultima_traccia_il` sul `:Luogo` con id `place_id`. Sola
    scrittura, nessuna transazione gestita (`Session.run`, non
    `execute_write`): non serve — vedi il docstring del modulo.

    Se `driver` non è passato, ne apre uno da `NEO4J_URI`/`NEO4J_USERNAME`/
    `NEO4J_PASSWORD`/`NEO4J_DATABASE` (dal `.env`, mai hardcoded) e lo chiude
    a fine chiamata — stesso pattern di
    `urban_memory.graph_link.link_to_graph`. Se `driver` è passato (un
    driver FINTO nei test, o uno già aperto e condiviso — vedi
    `Neo4jLuogoTracciaLinker`), il ciclo di vita resta di chi lo possiede.

    Qualunque eccezione sollevata aprendo la sessione o eseguendo la query
    (tranne `LuogoTracciaLinkError` stessa) viene ri-sollevata come
    `LuogoTracciaLinkError`, incatenata (`from exc`): una sola famiglia di
    eccezioni per chi chiama — che, nel lato-lettura di `POST /itinerary`
    (`api.main.create_itinerary`), la cattura e degrada
    (`eventi_attivi=[]`), mai un 503.
    """
    driver_aperto_qui = driver is None
    if driver is None:
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        database = database or cfg.database
    database = database or "neo4j"

    query, params = ultima_traccia_cypher(place_id, quando)
    try:
        with driver.session(database=database) as session:
            session.run(query, params)
    except LuogoTracciaLinkError:
        raise  # già il tipo giusto: non ri-avvolgere
    except Exception as exc:
        raise LuogoTracciaLinkError(
            f"impossibile scrivere ultima_traccia_il per place_id={place_id!r}: {exc}"
        ) from exc
    finally:
        if driver_aperto_qui:
            driver.close()


class Neo4jLuogoTracciaLinker:
    """Wrapper comodo attorno a `scrivi_ultima_traccia`: possiede un driver
    Neo4j aperto UNA VOLTA (non a ogni scrittura) e lo riusa — stesso
    pattern di `urban_memory.graph_link.Neo4jMemoryLinker`/
    `graph.source.Neo4jCandidateSource`. Usato dal BFF
    (`api.deps.get_place_link_writer`, una sola istanza per l'intero ciclo
    di vita del processo, mai un driver per richiesta)."""

    def __init__(self, driver: _Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Neo4jLuogoTracciaLinker:
        """Costruisce leggendo `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
        `NEO4J_DATABASE` dal `.env` (radice del repo) o dall'ambiente di
        processo."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        return cls(driver, database=cfg.database)

    @classmethod
    def from_credentials(
        cls, *, uri: str, username: str, password: str, database: str = "neo4j"
    ) -> Neo4jLuogoTracciaLinker:
        """Costruisce da credenziali già lette (stesso pattern di
        `graph.source.Neo4jCandidateSource.from_credentials`): usato da
        `api.deps.get_place_link_writer`, che legge già `api.settings.
        Settings` — evita una seconda lettura indipendente del `.env`."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        driver = GraphDatabase.driver(uri, auth=(username, password))
        return cls(driver, database=database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jLuogoTracciaLinker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def scrivi(self, place_id: str, quando: datetime) -> None:
        """`(place_id, quando) -> None` — esattamente la firma richiesta da
        `urban_memory.canale_fluttuante.PlaceLinkWriter`: passalo
        direttamente come metodo legato
        (`sweep_and_fetch_active(..., place_link_writer=linker.scrivi)`)."""
        scrivi_ultima_traccia(place_id, quando, driver=self._driver, database=self._database)
