"""Test di `urban_memory.promozione_evento`: generazione pura di Cypher
parametrico (`promozione_evento_cypher`) e la sua esecuzione
(`scrivi_evento_promosso`/`Neo4jPromozioneWriter`) contro un driver/sessione
Neo4j FINTI, locali a questo modulo (nessuna connessione reale). Un fake
dedicato (non `_neo4j_fakes.FakeDriver`, che riconosce solo le query di
`graph_link`/`luogo_traccia_link`): la query di promozione ha una forma
diversa (MATCH sul Luogo + MERGE dell'Evento nella STESSA query, RETURN
`evento_id`), e questo modulo introduce ANCHE una query di sola lettura
(`Neo4jPromozioneWriter.esiste`, solo `$evento_id`, nessun `$place_id`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from urban_memory.promozione_evento import (
    PROMOZIONE_EVENTO_WRITE_QUERY_PATH,
    Neo4jPromozioneWriter,
    PromozioneEventoError,
    evento_id_per_pattern,
    promozione_evento_cypher,
    scrivi_evento_promosso,
)

QUANDO = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


class _FakeResult:
    def __init__(self, valore: dict[str, Any] | None) -> None:
        self._valore = valore

    def single(self) -> dict[str, Any] | None:
        return self._valore


class _FakeSession:
    def __init__(self, driver: _FakeDriver) -> None:
        self._driver = driver

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        self._driver.query_eseguite.append((query, parameters))
        params = parameters or {}

        if "place_id" in params:
            # La query di PROMOZIONE (MATCH sul Luogo + MERGE dell'Evento).
            place_id = params.get("place_id")
            if place_id not in self._driver.luoghi_esistenti:
                return _FakeResult(None)  # simula un MATCH sul :Luogo senza righe
            evento_id = params.get("evento_id")
            self._driver.eventi_scritti[evento_id] = params
            return _FakeResult({"evento_id": evento_id})

        # La query di sola lettura "esiste" (solo $evento_id).
        evento_id = params.get("evento_id")
        if evento_id in self._driver.eventi_scritti:
            return _FakeResult({"evento_id": evento_id})
        return _FakeResult(None)

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeDriver:
    def __init__(
        self,
        luoghi_esistenti: set[str] | None = None,
        session_error: Exception | None = None,
    ) -> None:
        self.luoghi_esistenti = luoghi_esistenti if luoghi_esistenti is not None else set()
        self.session_error = session_error
        self.query_eseguite: list[tuple[str, dict[str, Any] | None]] = []
        self.eventi_scritti: dict[str, dict[str, Any] | None] = {}
        self.closed = False

    def session(self, database: str | None = None) -> _FakeSession:
        if self.session_error is not None:
            raise self.session_error
        return _FakeSession(self)

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# evento_id_per_pattern — deterministico
# ---------------------------------------------------------------------------


def test_evento_id_e_deterministico_per_lo_stesso_pattern() -> None:
    id1 = evento_id_per_pattern("piazza-anfiteatro", ("arte", "musica"))
    id2 = evento_id_per_pattern("piazza-anfiteatro", ("arte", "musica"))
    assert id1 == id2


def test_evento_id_diverso_per_pattern_diverso() -> None:
    id1 = evento_id_per_pattern("piazza-anfiteatro", ("musica",))
    id2 = evento_id_per_pattern("piazza-anfiteatro", ("arte",))
    assert id1 != id2


# ---------------------------------------------------------------------------
# promozione_evento_cypher — pura
# ---------------------------------------------------------------------------


def test_query_versionata_esiste() -> None:
    assert PROMOZIONE_EVENTO_WRITE_QUERY_PATH.exists()
    assert PROMOZIONE_EVENTO_WRITE_QUERY_PATH.name == "50_promozione_evento_write.cypher"


def test_promozione_evento_cypher_solo_match_sul_luogo_mai_merge_o_create() -> None:
    query, params = promozione_evento_cypher(
        "piazza-anfiteatro", "evento-x", ("musica",), 7.0, "promotore-1", QUANDO
    )
    assert "MATCH (l:Luogo {id: $place_id})" in query
    assert "MERGE (l" not in query
    assert "CREATE (l" not in query


def test_promozione_evento_cypher_ancora_via_si_svolge_a() -> None:
    query, _ = promozione_evento_cypher(
        "piazza-anfiteatro", "evento-x", ("musica",), 7.0, "promotore-1", QUANDO
    )
    assert "MERGE (e:Evento" in query
    assert "MERGE (e)-[:SI_SVOLGE_A]->(l)" in query


def test_promozione_evento_cypher_parametri() -> None:
    _, params = promozione_evento_cypher(
        "piazza-anfiteatro", "evento-x", ("arte", "musica"), 7.5, "promotore-1", QUANDO
    )
    assert params == {
        "place_id": "piazza-anfiteatro",
        "evento_id": "evento-x",
        "temi": ["arte", "musica"],
        "cadenza_giorni": 7.5,
        "promotore": "promotore-1",
        "promosso_il": QUANDO.isoformat(),
    }


def test_promozione_evento_cypher_registra_promosso_da() -> None:
    """Problema 1 (ethics-guardian): l'accountability della promozione deve
    persistere sul nodo, non solo in un log applicativo."""
    query, params = promozione_evento_cypher(
        "piazza-anfiteatro", "evento-x", ("musica",), 7.0, "promotore-1", QUANDO
    )
    assert "e.promosso_da = $promotore" in query
    assert params["promotore"] == "promotore-1"


def test_promozione_evento_cypher_on_create_preserva_promosso_il_originale() -> None:
    """Problema 2b (ethics-guardian): il MERGE usa ON CREATE/ON MATCH, non
    un SET incondizionato — una ripromozione non deve sovrascrivere la data
    ORIGINALE di prima promozione."""
    query, _ = promozione_evento_cypher(
        "piazza-anfiteatro", "evento-x", ("musica",), 7.0, "promotore-1", QUANDO
    )
    assert "ON CREATE SET" in query
    assert "ON MATCH SET" in query

    blocco_on_create, blocco_on_match = query.split("ON MATCH SET", 1)
    assert "e.promosso_il = $promosso_il" in blocco_on_create
    assert "e.promosso_da = $promotore" in blocco_on_create
    # La data/l'autore ORIGINALI non sono mai scritti nel ramo ON MATCH:
    # una ripromozione li lascia intatti.
    assert "e.promosso_il = $promosso_il" not in blocco_on_match
    assert "e.promosso_da = $promotore" not in blocco_on_match
    # Una ripromozione registra SEPARATAMENTE l'ultimo ricalcolo.
    assert "e.ultimo_ricalcolo_da = $promotore" in blocco_on_match
    assert "e.ultimo_ricalcolo_il = $promosso_il" in blocco_on_match


# ---------------------------------------------------------------------------
# scrivi_evento_promosso — esecuzione contro un driver finto
# ---------------------------------------------------------------------------


def test_scrivi_evento_promosso_place_id_esistente() -> None:
    driver = _FakeDriver(luoghi_esistenti={"piazza-anfiteatro"})

    evento_id = scrivi_evento_promosso(
        "piazza-anfiteatro",
        "evento-x",
        ("musica",),
        7.0,
        "promotore-1",
        promosso_il=QUANDO,
        driver=driver,
    )

    assert evento_id == "evento-x"
    assert len(driver.query_eseguite) == 1
    assert "evento-x" in driver.eventi_scritti
    assert driver.eventi_scritti["evento-x"]["promotore"] == "promotore-1"


def test_scrivi_evento_promosso_place_id_inesistente_solleva_errore_e_non_scrive_nulla() -> None:
    driver = _FakeDriver(luoghi_esistenti=set())  # nessun luogo esiste in questo grafo finto

    with pytest.raises(PromozioneEventoError):
        scrivi_evento_promosso(
            "place-mai-visto",
            "evento-x",
            ("musica",),
            7.0,
            "promotore-1",
            promosso_il=QUANDO,
            driver=driver,
        )

    assert driver.eventi_scritti == {}, "nessun :Evento deve essere stato scritto/aggiornato"


def test_scrivi_evento_promosso_grafo_irraggiungibile_solleva_errore() -> None:
    driver = _FakeDriver(session_error=RuntimeError("connessione rifiutata"))

    with pytest.raises(PromozioneEventoError):
        scrivi_evento_promosso(
            "piazza-anfiteatro",
            "evento-x",
            ("musica",),
            7.0,
            "promotore-1",
            promosso_il=QUANDO,
            driver=driver,
        )


def test_scrivi_evento_promosso_chiude_il_driver_solo_se_aperto_qui() -> None:
    driver = _FakeDriver(luoghi_esistenti={"piazza-anfiteatro"})
    scrivi_evento_promosso(
        "piazza-anfiteatro",
        "evento-x",
        ("musica",),
        7.0,
        "promotore-1",
        promosso_il=QUANDO,
        driver=driver,
    )
    assert driver.closed is False


# ---------------------------------------------------------------------------
# Neo4jPromozioneWriter — wrapper comodo, un driver riusato
# ---------------------------------------------------------------------------


def test_neo4j_promozione_writer_promuovi_delega() -> None:
    driver = _FakeDriver(luoghi_esistenti={"piazza-anfiteatro"})
    writer = Neo4jPromozioneWriter(driver, database="neo4j")

    evento_id = writer.promuovi(
        "piazza-anfiteatro", ("musica", "arte"), 30.0, "promotore-1", promosso_il=QUANDO
    )

    assert evento_id == evento_id_per_pattern("piazza-anfiteatro", ("musica", "arte"))
    assert driver.eventi_scritti[evento_id]["promotore"] == "promotore-1"


def test_neo4j_promozione_writer_ripromuovere_lo_stesso_pattern_e_idempotente() -> None:
    """MERGE sull'id deterministico: due promozioni dello stesso pattern
    aggiornano lo STESSO nodo, mai un duplicato."""
    driver = _FakeDriver(luoghi_esistenti={"piazza-anfiteatro"})
    writer = Neo4jPromozioneWriter(driver, database="neo4j")

    id1 = writer.promuovi("piazza-anfiteatro", ("musica",), 7.0, "promotore-1", promosso_il=QUANDO)
    id2 = writer.promuovi("piazza-anfiteatro", ("musica",), 8.0, "promotore-2", promosso_il=QUANDO)

    assert id1 == id2
    assert len(driver.eventi_scritti) == 1


def test_neo4j_promozione_writer_close_chiude_il_driver() -> None:
    driver = _FakeDriver()
    writer = Neo4jPromozioneWriter(driver)

    writer.close()

    assert driver.closed is True


# ---------------------------------------------------------------------------
# Neo4jPromozioneWriter.esiste — sola lettura, usata da rileva_candidati
# ---------------------------------------------------------------------------


def test_neo4j_promozione_writer_esiste_falso_se_mai_promosso() -> None:
    driver = _FakeDriver()
    writer = Neo4jPromozioneWriter(driver)

    assert writer.esiste("evento-mai-creato") is False


def test_neo4j_promozione_writer_esiste_vero_dopo_una_promozione() -> None:
    driver = _FakeDriver(luoghi_esistenti={"piazza-anfiteatro"})
    writer = Neo4jPromozioneWriter(driver)
    evento_id = writer.promuovi(
        "piazza-anfiteatro", ("musica",), 7.0, "promotore-1", promosso_il=QUANDO
    )

    assert writer.esiste(evento_id) is True
    assert writer.esiste("evento-un-altro-pattern") is False


def test_neo4j_promozione_writer_esiste_grafo_irraggiungibile_apertura_sessione() -> None:
    """Correzione ethics-guardian (follow-up): `esiste()` deve tradurre
    un'eccezione del driver in `PromozioneEventoError` — STESSA famiglia di
    `scrivi_evento_promosso` — mai propagarla grezza fino a
    `curatela_pattern.main`, che altrimenti andrebbe in crash (invece di
    uscire pulito) se Aura è in pausa durante il solo rilevamento."""
    driver = _FakeDriver(session_error=RuntimeError("connessione rifiutata"))
    writer = Neo4jPromozioneWriter(driver)

    with pytest.raises(PromozioneEventoError):
        writer.esiste("evento-qualunque")


class _FakeSessionRunFallisce:
    def __enter__(self) -> _FakeSessionRunFallisce:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        raise RuntimeError("query fallita")


class _FakeDriverRunFallisce:
    def __init__(self) -> None:
        self.closed = False

    def session(self, database: str | None = None) -> _FakeSessionRunFallisce:
        return _FakeSessionRunFallisce()

    def close(self) -> None:
        self.closed = True


def test_neo4j_promozione_writer_esiste_query_fallisce_durante_lesecuzione() -> None:
    """Stesso principio del test sopra, ma con il fallimento nella `.run()`
    (dopo che la sessione si è aperta con successo) invece che in
    `.session(...)`: entrambi i punti di fallimento del driver devono
    essere tradotti in `PromozioneEventoError`, mai propagati grezzi."""
    driver = _FakeDriverRunFallisce()
    writer = Neo4jPromozioneWriter(driver)

    with pytest.raises(PromozioneEventoError):
        writer.esiste("evento-qualunque")
