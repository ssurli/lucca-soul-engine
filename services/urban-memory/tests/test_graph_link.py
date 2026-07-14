"""Test di `urban_memory.graph_link`: generazione pura di Cypher parametrico
per agganciare un contributo al Knowledge Graph. Nessuna connessione a
Neo4j: solo `(query, params)`."""

from __future__ import annotations

import inspect
from datetime import datetime

from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import riguarda_to_cypher
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
    """Test-guard: nessun driver Neo4j nel modulo (nessuna connessione,
    nessuna sessione). Ispeziona l'AST (non la sorgente grezza, che
    includerebbe anche "Neo4j" nella docstring che SPIEGA perché non ce
    n'è uno): niente import di `neo4j`, nessun uso del nome `GraphDatabase`
    o `Driver`, nessuna chiamata `.run(...)`. La funzione produce solo
    `(query, params)`."""
    import ast

    import urban_memory.graph_link as graph_link_module

    nomi_vietati = {"neo4j", "GraphDatabase", "Driver"}
    albero = ast.parse(inspect.getsource(graph_link_module))
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
