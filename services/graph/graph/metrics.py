"""Metriche di topologia per l'Urban Intelligence Index (Wave 4).

Due primitive, entrambe con l'implementazione offline (`graph.topology`,
in-memory sul dataset canonico) e l'equivalente Neo4j live — STESSO
principio già in uso in `graph.source` (`CandidateSource` /
`SeedCandidateSource` / `Neo4jCandidateSource`): un'unica interfaccia
`Protocol`, nessun `if local/cloud` nel codice chiamante. La differenza tra
Aura (`neo4j+s://`) e Neo4j locale (`bolt://`) vive solo nella stringa
`NEO4J_URI` passata da chi istanzia `Neo4jMetricsSource`.

- `grado_semantico()` — per l'indicatore `attivazione_locale`: grado
  CULTURALE di ogni Luogo (relazioni `SEMANTIC_RELATION_TYPES`, incluse
  quelle delle Botteghe ospitate), non il grado nella rete `VICINO`
  (respinto dal committente — vedi `graph.topology`).
- `non_connected_place_pairs(at)` — per l'indicatore `nuovi_percorsi`:
  coppie di `place_id` non collegate direttamente da `VICINO` in uno
  snapshot congelato all'istante `at`.

In produzione la fonte live (`Neo4jMetricsSource`) è quella che conta: il
grafo su Aura accumula nel tempo relazioni che il seed offline non ha
(curatela, Urban Memory). La sorgente offline (`SeedMetricsSource`) resta il
percorso dei test e il fallback locale (profilo "PC fisso con Docker"), mai
l'unica fonte a runtime — stessa regola già documentata in
`graph.source.SeedCandidateSource`.

"Luogo minore" (soglia sul grado semantico, tipicamente la mediana) e il
calcolo vero e proprio di `nuovi_percorsi`/`attivazione_locale` NON sono
compito di questo modulo: chi li applica riceve i dizionari/insiemi grezzi
qui esposti, mai una soglia hardcoded (vedi `services/intelligence-index`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from neo4j import Driver, GraphDatabase

from graph import topology
from graph.errors import translate_driver_errors

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
GRADO_SEMANTICO_QUERY_PATH = _CYPHER_DIR / "11_grado_semantico.cypher"
NON_CONNECTED_PAIRS_QUERY_PATH = _CYPHER_DIR / "12_non_connected_pairs.cypher"


class GraphMetricsSource(Protocol):
    """Interfaccia comune alle due sorgenti (offline e Neo4j live). Nessuna
    delle due applica soglie o normalizza: espongono solo i fatti grezzi del
    grafo, come `graph.source.CandidateSource` fa per i candidati."""

    def grado_semantico(self) -> dict[str, int]: ...

    def non_connected_place_pairs(
        self, at: datetime | None = None
    ) -> tuple[set[frozenset[str]], int]: ...


# ---------------------------------------------------------------------------
# In-memory, sul dataset canonico
# ---------------------------------------------------------------------------


class SeedMetricsSource:
    """Implementazione in-memory: delega direttamente a `graph.topology`,
    nessuna seconda fonte di verità. Percorso usato nei test e finché
    `NEO4J_URI` non è configurato (vedi docstring di modulo)."""

    def grado_semantico(self) -> dict[str, int]:
        return topology.grado_semantico()

    def non_connected_place_pairs(
        self, at: datetime | None = None
    ) -> tuple[set[frozenset[str]], int]:
        return topology.non_connected_place_pairs(at)


# ---------------------------------------------------------------------------
# Via Neo4j (Aura o locale), stessa interfaccia
# ---------------------------------------------------------------------------


class Neo4jMetricsSource:
    """Stessa interfaccia di `SeedMetricsSource`, letta da Neo4j.

    URI/credenziali arrivano SEMPRE dal costruttore (mai hardcoded qui): chi
    la istanzia le legge da `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD`
    / `NEO4J_DATABASE` (vedi `graph.env.load_neo4j_config`), esattamente
    come `graph.source.Neo4jCandidateSource`.

    Le query sono versionate in `cypher/11_grado_semantico.cypher` e
    `cypher/12_non_connected_pairs.cypher`, caricate da file — non
    incorporate nel codice.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database
        self._grado_semantico_query = GRADO_SEMANTICO_QUERY_PATH.read_text(encoding="utf-8")
        self._non_connected_pairs_query = NON_CONNECTED_PAIRS_QUERY_PATH.read_text(encoding="utf-8")

    @classmethod
    def from_credentials(
        cls, uri: str, username: str, password: str, database: str = "neo4j"
    ) -> Neo4jMetricsSource:
        # URI malformato = errore di configurazione, non indisponibilita'.
        driver = GraphDatabase.driver(uri, auth=(username, password))
        return cls(driver, database=database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jMetricsSource:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def grado_semantico(self) -> dict[str, int]:
        with translate_driver_errors(), self._driver.session(database=self._database) as session:
            records = list(session.run(self._grado_semantico_query))
        return {record["place_id"]: record["grado"] for record in records}

    def non_connected_place_pairs(
        self, at: datetime | None = None
    ) -> tuple[set[frozenset[str]], int]:
        params = {"at": at.isoformat() if at is not None else None}
        with translate_driver_errors(), self._driver.session(database=self._database) as session:
            record = session.run(self._non_connected_pairs_query, params).single()
        coppie_grezze = record["coppie_non_connesse"] if record is not None else []
        coppie = {frozenset(coppia) for coppia in coppie_grezze}
        return coppie, len(coppie)
