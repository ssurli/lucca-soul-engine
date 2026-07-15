"""Driver/sessione/transazione Neo4j FINTI, condivisi dai test di
`urban_memory.graph_link` e `urban_memory.link`. Nessuna connessione reale:
solo registrazione di query+parametri eseguiti, più un piccolo stato interno
("quali id sono stati scritti come :Memoria e quante relazioni RIGUARDA")
così `count_memoria()` riflette DAVVERO l'effetto delle scritture eseguite
finora — non un valore statico scollegato da cosa è stato scritto davvero.

Nome del file con underscore iniziale: NON è un modulo di test (pytest lo
ignora: non inizia per `test_` né finisce per `_test`), è solo un helper
importabile dagli altri moduli di test in questa directory.
"""

from __future__ import annotations

from typing import Any


class FakeResult:
    def __init__(self, valore_single: dict[str, Any] | None) -> None:
        self._valore_single = valore_single

    def single(self) -> dict[str, Any] | None:
        return self._valore_single


class FakeTransaction:
    """Transazione finta passata da `FakeSession.execute_write` alla
    funzione di transazione (`urban_memory.graph_link._link_transaction`):
    registra ogni `.run(...)` sul driver, nell'ordine in cui avviene — è
    così che i test dimostrano che la query di SCRITTURA non viene mai
    eseguita quando la verifica fallisce. Aggiorna anche lo stato del
    "grafo finto" del driver quando la query di SCRITTURA viene eseguita
    (mai per la query di verifica, che è sola lettura)."""

    def __init__(self, driver: FakeDriver) -> None:
        self._driver = driver

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeResult:
        self._driver.query_eseguite.append((query, parameters))
        if "RETURN collect(target_id) AS mancanti" in query:
            return FakeResult({"mancanti": list(self._driver.mancanti)})
        if "MERGE (m:Memoria" in query and parameters is not None:
            self._driver._registra_scrittura(parameters)
        return FakeResult(None)


class FakeSession:
    def __init__(self, driver: FakeDriver) -> None:
        self._driver = driver
        self.execute_write_calls = 0

    def execute_write(self, transaction_function: Any, *args: Any, **kwargs: Any) -> Any:
        self.execute_write_calls += 1
        tx = FakeTransaction(self._driver)
        return transaction_function(tx, *args, **kwargs)

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeResult:
        # Usata SOLO da `Neo4jMemoryLinker.count_memoria` (lettura, fuori da
        # qualunque transazione gestita): non passa da `FakeTransaction`.
        self._driver.query_eseguite.append((query, parameters))
        if self._driver.valore_single is not None:
            return FakeResult(self._driver.valore_single)
        return FakeResult(self._driver.conteggio_dinamico())

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeDriver:
    """Driver Neo4j finto: registra ogni `(query, params)` eseguito da una
    sessione aperta con `.session(database=...)`. Nessuna connessione, nessun
    socket: solo liste/insiemi in memoria — esattamente ciò che il task
    chiede.

    `mancanti`: gli id che la query di VERIFICA finta deve dichiarare
    mancanti (default: nessuno, cioè "tutti i target esistono"). Si applica
    a qualunque verifica eseguita su questo driver — coerente con i test che
    fissano il comportamento atteso una volta per l'intero test.

    `valore_single`: se passato, le letture dirette (`count_memoria`)
    ritornano SEMPRE questo valore fisso — comodo per testarlo in
    isolamento. Se `None` (default), il conteggio è DINAMICO: riflette le
    scritture DAVVERO eseguite su questo driver — comodo per dimostrare
    "prima" (0, 0) e "dopo" (N, M) un `.link()` reale (`urban_memory.link`).
    """

    def __init__(
        self, mancanti: list[str] | None = None, valore_single: dict[str, Any] | None = None
    ) -> None:
        self.query_eseguite: list[tuple[str, dict[str, Any] | None]] = []
        self.database_richiesti: list[str | None] = []
        self.sessioni_aperte: list[FakeSession] = []
        self.closed = False
        self.mancanti = mancanti if mancanti is not None else []
        self.valore_single = valore_single
        self._memoria_ids: set[str] = set()
        self._relazioni = 0

    def _registra_scrittura(self, parametri_scrittura: dict[str, Any]) -> None:
        self._memoria_ids.add(parametri_scrittura["id"])
        self._relazioni += len(parametri_scrittura.get("riguarda") or [])

    def conteggio_dinamico(self) -> dict[str, int]:
        return {"memorie": len(self._memoria_ids), "relazioni": self._relazioni}

    def session(self, database: str | None = None) -> FakeSession:
        self.database_richiesti.append(database)
        sessione = FakeSession(self)
        self.sessioni_aperte.append(sessione)
        return sessione

    def close(self) -> None:
        self.closed = True
