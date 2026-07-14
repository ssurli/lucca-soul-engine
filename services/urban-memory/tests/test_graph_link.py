"""Test di `urban_memory.graph_link`: generazione pura di Cypher parametrico
(`riguarda_to_cypher`/`riguarda_check_cypher`) e la sua esecuzione ATOMICA
(`link_to_graph`/`Neo4jMemoryLinker`) contro un driver/sessione/transazione
Neo4j FINTI (nessuna connessione reale: registra solo query+parametri
eseguiti).

Copre il fix del bug osservato su Aura: un id in `riguarda` inesistente nel
grafo produceva in silenzio un nodo `:Memoria` orfano (creato comunque,
zero relazioni). Da questa wave: verifica PRIMA, scrittura DOPO, nella
stessa transazione — se un target manca, `MemoryLinkError` lo nomina e la
query di creazione del nodo `:Memoria` non viene MAI eseguita.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import MemoryLinkError, Neo4jMemoryLinker, link_to_graph, riguarda_to_cypher
from urban_memory.graph_link import (
    MEMORY_LINK_CHECK_QUERY_PATH,
    MEMORY_LINK_WRITE_QUERY_PATH,
    riguarda_check_cypher,
)


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


def test_query_versionate_esistono() -> None:
    assert MEMORY_LINK_CHECK_QUERY_PATH.exists()
    assert MEMORY_LINK_CHECK_QUERY_PATH.name == "30_memory_link_check.cypher"
    assert MEMORY_LINK_WRITE_QUERY_PATH.exists()
    assert MEMORY_LINK_WRITE_QUERY_PATH.name == "30_memory_link_write.cypher"


# ---------------------------------------------------------------------------
# riguarda_to_cypher — query di SCRITTURA, pura
# ---------------------------------------------------------------------------


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


def test_query_e_i_params_restano_gli_stessi_a_ogni_chiamata() -> None:
    # Deterministico: stesso contributo -> stessa (query, params).
    contributo = _contributo()
    q1, p1 = riguarda_to_cypher(contributo)
    q2, p2 = riguarda_to_cypher(contributo)
    assert q1 == q2
    assert p1 == p2


# ---------------------------------------------------------------------------
# riguarda_check_cypher — query di VERIFICA, pura
# ---------------------------------------------------------------------------


def test_riguarda_check_cypher_restituisce_i_mancanti() -> None:
    query, params = riguarda_check_cypher(_contributo(riguarda=["luogo-1", "bottega-1"]))
    assert "UNWIND $riguarda AS target_id" in query
    assert "RETURN collect(target_id) AS mancanti" in query
    assert params == {"riguarda": ["luogo-1", "bottega-1"]}


def test_riguarda_check_cypher_non_scrive_nulla() -> None:
    # Solo lettura: nessun MERGE/CREATE/SET nella query di verifica.
    query, _ = riguarda_check_cypher(_contributo())
    for parola_vietata in ("MERGE", "CREATE", "SET "):
        assert parola_vietata not in query


# ---------------------------------------------------------------------------
# link_to_graph / Neo4jMemoryLinker — ATOMICO: verifica poi scrittura, nella
# stessa transazione (fake Driver/Session/Transaction: nessuna connessione
# reale, solo registrazione di query+parametri eseguiti).
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, valore_single: dict[str, Any] | None) -> None:
        self._valore_single = valore_single

    def single(self) -> dict[str, Any] | None:
        return self._valore_single


class _FakeTransaction:
    """Transazione finta passata da `_FakeSession.execute_write` alla
    funzione di transazione (`urban_memory.graph_link._link_transaction`):
    registra ogni `.run(...)` nell'ordine in cui avviene — è così che i test
    (b)/(c) dimostrano che la query di SCRITTURA non viene mai eseguita
    quando la verifica fallisce."""

    def __init__(
        self, registro: list[tuple[str, dict[str, Any] | None]], mancanti: list[str]
    ) -> None:
        self._registro = registro
        self._mancanti = mancanti

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        self._registro.append((query, parameters))
        if "RETURN collect(target_id) AS mancanti" in query:
            return _FakeResult({"mancanti": list(self._mancanti)})
        return _FakeResult(None)


class _FakeSession:
    def __init__(
        self,
        registro: list[tuple[str, dict[str, Any] | None]],
        mancanti: list[str] | None = None,
        valore_single: dict[str, Any] | None = None,
    ) -> None:
        self._registro = registro
        self._mancanti = mancanti if mancanti is not None else []
        self._valore_single = valore_single
        self.execute_write_calls = 0

    def execute_write(self, transaction_function: Any, *args: Any, **kwargs: Any) -> Any:
        self.execute_write_calls += 1
        tx = _FakeTransaction(self._registro, self._mancanti)
        return transaction_function(tx, *args, **kwargs)

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        # Usata SOLO da `Neo4jMemoryLinker.count_memoria` (lettura, fuori da
        # qualunque transazione gestita): non passa da `_FakeTransaction`.
        self._registro.append((query, parameters))
        return _FakeResult(self._valore_single)

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeDriver:
    """Driver Neo4j finto: registra ogni `(query, params)` eseguito da una
    sessione aperta con `.session(database=...)`. Nessuna connessione, nessun
    socket: solo liste in memoria — esattamente ciò che il task chiede.

    `mancanti`: gli id che la query di VERIFICA finta deve dichiarare
    mancanti (default: nessuno, cioè "tutti i target esistono")."""

    def __init__(
        self, mancanti: list[str] | None = None, valore_single: dict[str, Any] | None = None
    ) -> None:
        self.query_eseguite: list[tuple[str, dict[str, Any] | None]] = []
        self.database_richiesti: list[str | None] = []
        self.sessioni_aperte: list[_FakeSession] = []
        self.closed = False
        self._mancanti = mancanti if mancanti is not None else []
        self._valore_single = valore_single

    def session(self, database: str | None = None) -> _FakeSession:
        self.database_richiesti.append(database)
        sessione = _FakeSession(
            self.query_eseguite, mancanti=self._mancanti, valore_single=self._valore_single
        )
        self.sessioni_aperte.append(sessione)
        return sessione

    def close(self) -> None:
        self.closed = True


# --- (a) target esistenti: verifica ESEGUITA, poi la scrittura ESEGUITA ----


def test_link_to_graph_con_target_esistenti_verifica_poi_scrive() -> None:
    driver = _FakeDriver(mancanti=[])  # tutti i target "esistono" nel grafo finto
    contributo = _contributo(riguarda=["bottega-1", "artista-1"])

    link_to_graph(contributo, driver=driver, database="neo4j")

    messaggio = "verifica + scrittura, nell'ordine, nella stessa transazione"
    assert len(driver.query_eseguite) == 2, messaggio

    check_eseguita, check_params = driver.query_eseguite[0]
    check_attesa, check_params_attesi = riguarda_check_cypher(contributo)
    assert check_eseguita == check_attesa
    assert check_params == check_params_attesi

    scrittura_eseguita, scrittura_params = driver.query_eseguite[1]
    scrittura_attesa, scrittura_params_attesi = riguarda_to_cypher(contributo)
    assert scrittura_eseguita == scrittura_attesa
    assert scrittura_params == scrittura_params_attesi
    assert "MERGE (m:Memoria {id: $id})" in scrittura_eseguita
    assert "MERGE (m)-[:RIGUARDA]->(target)" in scrittura_eseguita

    assert driver.database_richiesti == ["neo4j"]


def test_link_to_graph_con_target_esistenti_usa_execute_write_una_sola_volta() -> None:
    """Verifica e scrittura girano nella STESSA transazione (`execute_write`
    chiamato una volta sola, non due sessioni/transazioni separate: è
    l'atomicità che rende impossibile un nodo :Memoria orfano)."""
    driver = _FakeDriver(mancanti=[])

    link_to_graph(_contributo(), driver=driver)

    assert len(driver.sessioni_aperte) == 1
    assert driver.sessioni_aperte[0].execute_write_calls == 1


# --- (b) target inesistente: MemoryLinkError, MAI la query di scrittura ----


def test_link_to_graph_con_target_inesistente_solleva_memory_link_error() -> None:
    driver = _FakeDriver(mancanti=["bottega-fantasma"])
    contributo = _contributo(riguarda=["bottega-fantasma", "artista-1"])

    with pytest.raises(MemoryLinkError, match=r"bottega-fantasma"):
        link_to_graph(contributo, driver=driver)


def test_link_to_graph_con_target_inesistente_non_esegue_mai_la_scrittura() -> None:
    """IL CUORE DEL FIX: se un target manca, il nodo :Memoria non deve MAI
    essere creato — nessun nodo orfano, come accaduto su Aura."""
    driver = _FakeDriver(mancanti=["bottega-fantasma"])
    contributo = _contributo(riguarda=["bottega-fantasma"])

    with pytest.raises(MemoryLinkError):
        link_to_graph(contributo, driver=driver)

    # La verifica È stata eseguita (una sola query: quella di CHECK)...
    assert len(driver.query_eseguite) == 1
    query_eseguita, _ = driver.query_eseguite[0]
    assert "RETURN collect(target_id) AS mancanti" in query_eseguita

    # ...ma MERGE (m:Memoria ...) — la creazione del nodo — non è MAI stata
    # eseguita: nessun nodo :Memoria orfano può esistere.
    assert not any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)


def test_link_to_graph_con_piu_target_inesistenti_li_nomina_tutti() -> None:
    driver = _FakeDriver(mancanti=["luogo-fantasma", "bottega-fantasma"])
    contributo = _contributo(riguarda=["luogo-fantasma", "bottega-fantasma"])

    with pytest.raises(MemoryLinkError) as errore:
        link_to_graph(contributo, driver=driver)

    assert "luogo-fantasma" in str(errore.value)
    assert "bottega-fantasma" in str(errore.value)


# --- (c) riguarda vuoto: ERA "Memoria creata senza relazioni", ORA errore --


def test_link_to_graph_con_riguarda_vuoto_solleva_memory_link_error_senza_driver() -> None:
    """RIBALTAMENTO del vecchio comportamento (il bug): `riguarda` vuoto NON
    crea più una Memoria senza relazioni — è un `MemoryLinkError` esplicito,
    sollevato PRIMA di aprire qualunque sessione.

    `MemoryContribution(riguarda=[])` è già rifiutata dal contratto stesso
    (`Field(min_length=1)`, `packages/contracts`): per esercitare la difesa
    in profondità del LINKER (che non si fida nemmeno di un contratto già
    validato altrove — es. un oggetto costruito con `model_construct`, o un
    contratto futuro meno restrittivo) si usa `model_copy`, che NON
    rivalida, per ottenere comunque un `riguarda` vuoto qui."""
    driver = _FakeDriver()
    contributo_con_riguarda_vuoto = _contributo().model_copy(update={"riguarda": []})

    with pytest.raises(MemoryLinkError, match="riguarda"):
        link_to_graph(contributo_con_riguarda_vuoto, driver=driver)

    assert driver.database_richiesti == []  # nessuna sessione aperta
    assert driver.query_eseguite == []  # nessuna query eseguita


# --- comportamento generale di link_to_graph --------------------------------


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


# --- Neo4jMemoryLinker --------------------------------------------------


def test_neo4j_memory_linker_link_delega_a_link_to_graph_sul_driver_posseduto() -> None:
    driver = _FakeDriver(mancanti=[])
    linker = Neo4jMemoryLinker(driver, database="lucca")
    contributo = _contributo(riguarda=["artista-1"])

    linker.link(contributo)

    assert len(driver.query_eseguite) == 2  # verifica + scrittura
    scrittura_eseguita, scrittura_params = driver.query_eseguite[1]
    scrittura_attesa, scrittura_params_attesi = riguarda_to_cypher(contributo)
    assert scrittura_eseguita == scrittura_attesa
    assert scrittura_params == scrittura_params_attesi
    assert driver.database_richiesti == ["lucca"]
    assert driver.closed is False  # link() non possiede il driver, non lo chiude


def test_neo4j_memory_linker_link_propaga_memory_link_error_senza_creare_nulla() -> None:
    driver = _FakeDriver(mancanti=["bottega-fantasma"])
    linker = Neo4jMemoryLinker(driver)

    with pytest.raises(MemoryLinkError, match="bottega-fantasma"):
        linker.link(_contributo(riguarda=["bottega-fantasma"]))

    assert not any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)


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
