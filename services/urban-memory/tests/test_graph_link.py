"""Test di `urban_memory.graph_link`: generazione pura di Cypher parametrico
(`riguarda_to_cypher`) e la sua esecuzione (`link_to_graph`/
`Neo4jMemoryLinker`) contro un driver Neo4j FINTO (nessuna connessione
reale: registra solo query+parametri eseguiti)."""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import Neo4jMemoryLinker, link_to_graph, riguarda_to_cypher
from urban_memory.graph_link import MEMORY_LINK_QUERY_PATH


def _contributo(**overrides: object) -> MemoryContribution:
    defaults: dict[str, object] = {
        "id": "mem-graph-1",
        "kind": MemoryKind.MESTIERE,
        "testo": "Il mestiere del liutaio, tramandato da tre generazioni.",
        "riguarda": ["bottega-1", "artista-1"],
        "contributor_id": "voce-del-borgo",
        "contributor_kind": PersonKind.CITTADINO,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": datetime(2026, 7, 14, 9, 30),
        "curato": True,
    }
    defaults.update(overrides)
    return MemoryContribution(**defaults)


def test_query_versionata_esiste() -> None:
    assert MEMORY_LINK_QUERY_PATH.exists()
    assert MEMORY_LINK_QUERY_PATH.name == "30_memory_link.cypher"


def test_riguarda_to_cypher_produce_merge_memoria() -> None:
    query, params = riguarda_to_cypher(_contributo())
    assert "MERGE (m:Memoria {id: $id})" in query
    assert params["id"] == "mem-graph-1"


def test_riguarda_to_cypher_merge_riguarda_per_ogni_target() -> None:
    contributo = _contributo(riguarda=["luogo-1", "bottega-1", "artista-1"])
    query, params = riguarda_to_cypher(contributo)
    assert "UNWIND $riguarda AS target_id" in query
    assert "MERGE (m)-[:RIGUARDA]->(target)" in query
    assert params["riguarda"] == ["luogo-1", "bottega-1", "artista-1"]


def test_riguarda_to_cypher_filtra_su_luogo_bottega_artista() -> None:
    query, _ = riguarda_to_cypher(_contributo())
    assert "target:Luogo" in query
    assert "target:Bottega" in query
    assert "target:Artista" in query


def test_riguarda_to_cypher_non_crea_il_target() -> None:
    # Solo MATCH sul target (nodo esistente), mai MERGE/CREATE di un nodo
    # Luogo/Bottega/Artista: il contributo si aggancia, non inventa il nodo.
    query, _ = riguarda_to_cypher(_contributo())
    assert "MATCH (target)" in query
    assert "CREATE (target" not in query
    assert "MERGE (target" not in query


def test_query_e_idempotente_solo_merge() -> None:
    query, _ = riguarda_to_cypher(_contributo())
    assert "CREATE " not in query  # solo MERGE: rieseguibile senza duplicare


def test_riguarda_to_cypher_non_esegue_nulla_ed_e_pura() -> None:
    """Test-guard SU `riguarda_to_cypher` (non sull'intero modulo: da questa
    wave `graph_link.py` ospita ANCHE l'esecuzione live — `link_to_graph`/
    `Neo4jMemoryLinker`, testate sotto con un driver finto — quindi il
    modulo nel suo complesso importa `neo4j` di proposito). Ispeziona l'AST
    della sola funzione `riguarda_to_cypher` (non la sorgente grezza, che
    includerebbe anche "Neo4j" nella docstring che SPIEGA la regola): niente
    import di `neo4j`, nessun uso del nome `GraphDatabase` o `Driver`,
    nessuna chiamata `.run(...)`. Resta una funzione pura: produce solo
    `(query, params)`, non apre nulla."""
    import ast

    import urban_memory.graph_link as graph_link_module

    nomi_vietati = {"neo4j", "GraphDatabase", "Driver"}
    codice_funzione = inspect.getsource(graph_link_module.riguarda_to_cypher)
    albero = ast.parse(codice_funzione)
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            assert not any(alias.name.split(".")[0] in nomi_vietati for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.module is None or nodo.module.split(".")[0] not in nomi_vietati
        elif isinstance(nodo, ast.Name):
            assert nodo.id not in nomi_vietati
        elif isinstance(nodo, ast.Attribute):
            assert nodo.attr != "run"


def test_riguarda_to_cypher_params_riflettono_i_campi_del_contributo() -> None:
    contributo = _contributo(
        kind=MemoryKind.RICETTA,
        licenza="CC0-1.0",
        curato=False,
        contributor_kind=PersonKind.TURISTA,
    )
    _, params = riguarda_to_cypher(contributo)
    assert params["kind"] == "ricetta"
    assert params["licenza"] == "CC0-1.0"
    assert params["curato"] is False
    assert params["contributor_kind"] == "turista"
    assert params["creato_il"] == contributo.creato_il.isoformat()


def test_riguarda_to_cypher_con_riguarda_vuoto_crea_solo_la_memoria() -> None:
    contributo = _contributo(riguarda=[])
    query, params = riguarda_to_cypher(contributo)
    assert params["riguarda"] == []
    assert "MERGE (m:Memoria {id: $id})" in query


def test_query_e_i_params_restano_gli_stessi_a_ogni_chiamata() -> None:
    # Deterministico: stesso contributo -> stessa (query, params).
    contributo = _contributo()
    q1, p1 = riguarda_to_cypher(contributo)
    q2, p2 = riguarda_to_cypher(contributo)
    assert q1 == q2
    assert p1 == p2


# ---------------------------------------------------------------------------
# link_to_graph / Neo4jMemoryLinker — eseguono riguarda_to_cypher() contro un
# driver Neo4j FINTO: nessuna connessione reale, solo registrazione di
# query+parametri (CLAUDE.md/task: "testalo con un driver/sessione FINTI").
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, valore_single: dict[str, Any] | None) -> None:
        self._valore_single = valore_single

    def single(self) -> dict[str, Any] | None:
        return self._valore_single


class _FakeSession:
    def __init__(
        self, registro: list[tuple[str, dict[str, Any] | None]], valore_single=None
    ) -> None:
        self._registro = registro
        self._valore_single = valore_single

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        self._registro.append((query, parameters))
        return _FakeResult(self._valore_single)

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeDriver:
    """Driver Neo4j finto: registra ogni `(query, params)` eseguito da una
    sessione aperta con `.session(database=...)`. Nessuna connessione, nessun
    socket: solo liste in memoria — esattamente ciò che il task chiede."""

    def __init__(self, valore_single: dict[str, Any] | None = None) -> None:
        self.query_eseguite: list[tuple[str, dict[str, Any] | None]] = []
        self.database_richiesti: list[str | None] = []
        self.closed = False
        self._valore_single = valore_single

    def session(self, database: str | None = None) -> _FakeSession:
        self.database_richiesti.append(database)
        return _FakeSession(self.query_eseguite, self._valore_single)

    def close(self) -> None:
        self.closed = True


def test_link_to_graph_con_driver_esplicito_esegue_la_query_di_riguarda_to_cypher() -> None:
    driver = _FakeDriver()
    contributo = _contributo(riguarda=["luogo-1", "bottega-1"])

    link_to_graph(contributo, driver=driver, database="neo4j")

    assert len(driver.query_eseguite) == 1
    query_eseguita, params_eseguiti = driver.query_eseguite[0]
    query_attesa, params_attesi = riguarda_to_cypher(contributo)
    assert query_eseguita == query_attesa
    assert params_eseguiti == params_attesi
    assert driver.database_richiesti == ["neo4j"]


def test_link_to_graph_con_driver_esplicito_non_lo_chiude() -> None:
    """Il ciclo di vita di un driver passato da chi chiama resta di chi
    chiama: `link_to_graph` non lo chiude (solo un driver aperto al suo
    interno, quando `driver=None`, viene chiuso a fine chiamata)."""
    driver = _FakeDriver()
    link_to_graph(_contributo(), driver=driver)
    assert driver.closed is False


def test_link_to_graph_usa_database_default_neo4j_se_non_specificato() -> None:
    driver = _FakeDriver()
    link_to_graph(_contributo(), driver=driver)
    assert driver.database_richiesti == ["neo4j"]


def test_link_to_graph_senza_driver_richiede_le_variabili_neo4j(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Senza un driver esplicito, `link_to_graph` legge NEO4J_URI/USERNAME/
    PASSWORD dal `.env`/ambiente PRIMA di tentare qualunque connessione: qui
    verifichiamo che l'errore sia leggibile (nessun tentativo di rete)."""
    for var in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"):
        monkeypatch.delenv(var, raising=False)
    dotenv_vuoto = tmp_path / ".env"
    dotenv_vuoto.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="NEO4J"):
        link_to_graph(_contributo(), dotenv_path=dotenv_vuoto)


def test_neo4j_memory_linker_link_delega_a_link_to_graph_sul_driver_posseduto() -> None:
    driver = _FakeDriver()
    linker = Neo4jMemoryLinker(driver, database="lucca")
    contributo = _contributo(riguarda=["artista-1"])

    linker.link(contributo)

    assert len(driver.query_eseguite) == 1
    query_eseguita, params_eseguiti = driver.query_eseguite[0]
    query_attesa, params_attesi = riguarda_to_cypher(contributo)
    assert query_eseguita == query_attesa
    assert params_eseguiti == params_attesi
    assert driver.database_richiesti == ["lucca"]
    assert driver.closed is False  # link() non possiede il driver, non lo chiude


def test_neo4j_memory_linker_count_memoria() -> None:
    driver = _FakeDriver(valore_single={"memorie": 3, "relazioni": 7})
    linker = Neo4jMemoryLinker(driver)

    memorie, relazioni = linker.count_memoria()

    assert (memorie, relazioni) == (3, 7)


def test_neo4j_memory_linker_context_manager_chiude_il_driver_posseduto() -> None:
    driver = _FakeDriver()
    with Neo4jMemoryLinker(driver) as linker:
        linker.link(_contributo())
        assert driver.closed is False
    assert driver.closed is True
