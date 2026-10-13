"""Test di `urban_memory.luogo_traccia_link`: generazione pura di Cypher
parametrico (`ultima_traccia_cypher`) e la sua esecuzione (`scrivi_ultima_
traccia`/`Neo4jLuogoTracciaLinker`) contro un driver/sessione Neo4j FINTI
(`_neo4j_fakes.FakeDriver`, riusato da `test_graph_link.py`) — nessuna
connessione reale."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _neo4j_fakes import FakeDriver
from urban_memory.luogo_traccia_link import (
    LUOGO_TRACCIA_WRITE_QUERY_PATH,
    LuogoTracciaLinkError,
    Neo4jLuogoTracciaLinker,
    scrivi_ultima_traccia,
    ultima_traccia_cypher,
)

QUANDO = datetime(2026, 7, 14, 23, 59, 59, tzinfo=UTC)


def test_query_versionata_esiste() -> None:
    assert LUOGO_TRACCIA_WRITE_QUERY_PATH.exists()
    assert LUOGO_TRACCIA_WRITE_QUERY_PATH.name == "40_luogo_traccia_write.cypher"


# ---------------------------------------------------------------------------
# ultima_traccia_cypher — pura
# ---------------------------------------------------------------------------


def test_ultima_traccia_cypher_produce_match_set() -> None:
    query, params = ultima_traccia_cypher("piazza-anfiteatro", QUANDO)

    assert "MATCH (l:Luogo {id: $place_id})" in query
    assert "SET l.ultima_traccia_il = CASE" in query
    assert params == {"place_id": "piazza-anfiteatro", "quando": QUANDO.isoformat()}


def test_ultima_traccia_cypher_e_monotona() -> None:
    """La scrittura tiene il massimo (confronto via datetime(), non stringhe):
    un segnale scaduto prima, scritto dopo, non fa regredire la proprietà."""
    query, _ = ultima_traccia_cypher("piazza-anfiteatro", QUANDO)
    assert "datetime(l.ultima_traccia_il) < datetime($quando)" in query
    assert "l.ultima_traccia_il IS NULL" in query


def test_ultima_traccia_cypher_normalizza_in_utc() -> None:
    from datetime import timedelta, timezone

    roma = datetime(2026, 7, 15, 1, 59, 59, tzinfo=timezone(timedelta(hours=2)))
    _, params = ultima_traccia_cypher("piazza-anfiteatro", roma)
    assert params["quando"] == QUANDO.isoformat()
    assert params["quando"].endswith("+00:00")


def test_ultima_traccia_cypher_non_crea_mai_il_luogo() -> None:
    query, _ = ultima_traccia_cypher("piazza-anfiteatro", QUANDO)
    assert "MERGE (l" not in query
    assert "CREATE (l" not in query


# ---------------------------------------------------------------------------
# scrivi_ultima_traccia — esecuzione contro un driver finto
# ---------------------------------------------------------------------------


def test_scrivi_ultima_traccia_esegue_la_query_sul_driver() -> None:
    driver = FakeDriver()

    scrivi_ultima_traccia("piazza-anfiteatro", QUANDO, driver=driver, database="neo4j")

    assert len(driver.query_eseguite) == 1
    query, params = driver.query_eseguite[0]
    assert "SET l.ultima_traccia_il" in query
    assert params == {"place_id": "piazza-anfiteatro", "quando": QUANDO.isoformat()}


def test_scrivi_ultima_traccia_place_id_inesistente_e_un_no_op_innocuo() -> None:
    # FakeDriver non simula "il place_id non esiste" come un'eccezione (la
    # query reale sarebbe un MATCH senza righe, zero effetti): qui verifica
    # solo che nessuna eccezione venga sollevata per un place_id qualunque.
    driver = FakeDriver()

    scrivi_ultima_traccia("place-mai-visto", QUANDO, driver=driver, database="neo4j")

    assert len(driver.query_eseguite) == 1  # eseguita comunque, nessun errore


def test_scrivi_ultima_traccia_grafo_irraggiungibile_solleva_luogo_traccia_link_error() -> None:
    driver = FakeDriver(session_error=RuntimeError("connessione rifiutata"))

    with pytest.raises(LuogoTracciaLinkError):
        scrivi_ultima_traccia("piazza-anfiteatro", QUANDO, driver=driver, database="neo4j")


def test_scrivi_ultima_traccia_chiude_il_driver_solo_se_aperto_qui() -> None:
    driver = FakeDriver()
    # driver passato esplicitamente: il ciclo di vita resta di chi lo possiede.
    scrivi_ultima_traccia("piazza-anfiteatro", QUANDO, driver=driver, database="neo4j")
    assert driver.closed is False


# ---------------------------------------------------------------------------
# Neo4jLuogoTracciaLinker — wrapper comodo, un driver riusato
# ---------------------------------------------------------------------------


def test_neo4j_luogo_traccia_linker_scrivi_delega_a_scrivi_ultima_traccia() -> None:
    driver = FakeDriver()
    linker = Neo4jLuogoTracciaLinker(driver, database="neo4j")

    linker.scrivi("piazza-anfiteatro", QUANDO)
    linker.scrivi("duomo-san-martino", QUANDO)

    assert len(driver.query_eseguite) == 2
    place_ids = [(params or {})["place_id"] for _, params in driver.query_eseguite]
    assert place_ids == ["piazza-anfiteatro", "duomo-san-martino"]


def test_neo4j_luogo_traccia_linker_close_chiude_il_driver() -> None:
    driver = FakeDriver()
    linker = Neo4jLuogoTracciaLinker(driver, database="neo4j")

    linker.close()

    assert driver.closed is True
