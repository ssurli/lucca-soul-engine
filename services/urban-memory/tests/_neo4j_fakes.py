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
        risultato = self._driver._risultato_per(query, parameters)
        if risultato is not None:
            return FakeResult(risultato)
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
        # Usata da letture DIRETTE, fuori da qualunque transazione gestita
        # (non passano da `FakeTransaction`): `count_memoria` E
        # `targets_mancanti` la chiamano entrambe.
        self._driver.query_eseguite.append((query, parameters))
        return FakeResult(self._driver._risultato_per(query, parameters))

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeDriver:
    """Driver Neo4j finto: registra ogni `(query, params)` eseguito da una
    sessione aperta con `.session(database=...)`. Nessuna connessione, nessun
    socket: solo liste/insiemi in memoria — esattamente ciò che il task
    chiede.

    `mancanti`: l'INSIEME degli id che, in questo grafo finto, non esistono
    — non necessariamente gli id di UNA chiamata: ogni verifica calcola
    l'INTERSEZIONE tra gli id richiesti (`$riguarda`) e questo insieme,
    preservando l'ordine della richiesta (come farebbe `UNWIND` + `collect`
    su Neo4j vero). Un contributo che riguarda solo id fuori da `mancanti`
    risulta quindi valido, anche se `mancanti` non è vuoto — utile per
    simulare un grafo con ALCUNI id mancanti e altri no (es. `urban_memory.
    audit` su più contributi, alcuni validi e alcuni no, sullo STESSO
    driver).

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

    def _risultato_per(
        self, query: str, parameters: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Simula la risposta in base al CONTENUTO della query — lo stesso
        riconoscimento serve sia dentro una transazione gestita
        (`FakeTransaction.run`, es. `_link_transaction`) sia per letture
        dirette fuori da una transazione (`FakeSession.run`, es.
        `count_memoria`/`targets_mancanti`): la query di verifica
        (`30_memory_link_check.cypher`, colonna `mancanti`) e la query di
        conteggio (`count_memoria`, colonne `memorie`/`relazioni`) sono
        entrambe sola lettura ed eseguibili in entrambi i modi dal codice
        reale. `None` se la query non è nota (es. la query di SCRITTURA:
        gestita a parte da `FakeTransaction.run`, che aggiorna lo stato).

        La query di verifica ritorna l'INTERSEZIONE tra `$riguarda` (i
        parametri della CHIAMATA, non un valore fisso) e `self.mancanti`
        (l'insieme di id "inesistenti" configurato sul driver): permette a
        UN SOLO driver finto di rispondere correttamente a più contributi
        diversi, alcuni validi e alcuni no (vedi `urban_memory.audit`)."""
        if "AS mancanti" in query:
            richiesti = (parameters or {}).get("riguarda", [])
            return {"mancanti": [rid for rid in richiesti if rid in self.mancanti]}
        if "AS memorie" in query:
            if self.valore_single is not None:
                return self.valore_single
            return self.conteggio_dinamico()
        return None

    def session(self, database: str | None = None) -> FakeSession:
        self.database_richiesti.append(database)
        sessione = FakeSession(self)
        self.sessioni_aperte.append(sessione)
        return sessione

    def close(self) -> None:
        self.closed = True
