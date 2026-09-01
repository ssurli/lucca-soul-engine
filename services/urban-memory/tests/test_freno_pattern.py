"""Test di `urban_memory.freno_pattern` — il freno di emergenza su un
`:Evento` promosso (Fase 3, `docs/STATE_MACHINE.md` §4-bis(b)).

Tre livelli, stesso principio di `tests/test_frizione_pattern.py`:

- Query Cypher pure (`freno_stato_write_cypher`) — nessuna connessione.
- Esecuzione (`scrivi_freno_evento`/`Neo4jFrenoClient`) contro un
  driver/sessione Neo4j FINTI, locali a questo modulo.
- Le funzioni di dominio `tira_freno`/`rilascia_freno`, con un `writer`
  finto (una funzione spia) e `InMemoryPatternFrenatoRepository` — il
  percorso richiamabile separatamente da `main()`, usato qui.

`main()` NON è testato qui — stesso principio, stesso motivo, di
`tests/test_frizione_pattern.py`/`tests/test_curatela_pattern.py`: costruisce
sempre `PostgresPatternFrenatoRepository`/`Neo4jFrenoClient.from_env()` al
suo interno, una CLI di persistenza REALE verificata girandola contro uno
storage vero, non con un mock."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from urban_memory.freno_pattern import (
    FRENO_STATO_WRITE_QUERY_PATH,
    FrenoPatternError,
    Neo4jFrenoClient,
    freno_stato_write_cypher,
    rilascia_freno,
    scrivi_freno_evento,
    tira_freno,
)
from urban_memory.freno_repository import InMemoryPatternFrenatoRepository

QUANDO = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Query Cypher pure — nessuna connessione, nessuna esecuzione
# ---------------------------------------------------------------------------


def test_query_di_scrittura_versionata_esiste() -> None:
    assert FRENO_STATO_WRITE_QUERY_PATH.exists()
    assert FRENO_STATO_WRITE_QUERY_PATH.name == "62_freno_stato_write.cypher"


def test_freno_stato_write_cypher_solo_match_e_set_mai_merge_mai_stato() -> None:
    query, params = freno_stato_write_cypher("evento-x", True)
    assert "MATCH (e:Evento {id: $evento_id})" in query
    assert "SET e.frenato = $frenato" in query
    # Cerca la clausola REALE `MERGE (`/`SET e.stato`, non la parola nuda
    # (i commenti versionati la discutono in prosa) — stessa cautela di
    # `test_frizione_pattern.test_frizione_stato_write_cypher_solo_match_e_set_mai_merge`.
    assert "MERGE (" not in query
    assert "SET e.stato" not in query
    assert params == {"evento_id": "evento-x", "frenato": True}


def test_freno_stato_write_cypher_letta_dal_file_versionato_non_duplicata() -> None:
    query, _ = freno_stato_write_cypher("evento-x", True)
    assert query == FRENO_STATO_WRITE_QUERY_PATH.read_text(encoding="utf-8")


def test_freno_stato_write_cypher_parametro_frenato_false_per_il_rilascio() -> None:
    _, params = freno_stato_write_cypher("evento-x", False)
    assert params == {"evento_id": "evento-x", "frenato": False}


# ---------------------------------------------------------------------------
# Esecuzione contro un driver/sessione FINTI — nessuna connessione reale
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, righe: list[dict[str, Any]]) -> None:
        self._righe = righe

    def data(self) -> list[dict[str, Any]]:
        return self._righe


class _FakeSession:
    def __init__(self, driver: _FakeDriver) -> None:
        self._driver = driver

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeResult:
        self._driver.query_eseguite.append((query, parameters))
        params = parameters or {}
        evento_id = params.get("evento_id")
        for evento in self._driver.eventi:
            if evento["evento_id"] == evento_id:
                # Verifica di dominio: questa query scrive SOLO `frenato`,
                # mai `stato` — riprodotto anche nel fake, non solo
                # verificato via ispezione della query testuale sopra.
                assert "stato" not in params
                evento["frenato"] = params.get("frenato")
                return _FakeResult([{"evento_id": evento_id}])
        return _FakeResult([])  # evento_id inesistente: no-op, nessuna riga

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeDriver:
    def __init__(
        self,
        eventi: list[dict[str, Any]] | None = None,
        session_error: Exception | None = None,
    ) -> None:
        self.eventi = eventi if eventi is not None else []
        self.session_error = session_error
        self.query_eseguite: list[tuple[str, dict[str, Any] | None]] = []
        self.closed = False

    def session(self, database: str | None = None) -> _FakeSession:
        if self.session_error is not None:
            raise self.session_error
        return _FakeSession(self)

    def close(self) -> None:
        self.closed = True


_EVENTO_GREZZO = {
    "evento_id": "evento-piazza-anfiteatro-arte-musica",
    "place_id": "piazza-anfiteatro",
    "temi": ["arte", "musica"],
    "stato": "attivo",
    "cadenza_giorni": 7.0,
    "frenato": False,
}


def test_scrivi_freno_evento_tira_il_freno() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    scrivi_freno_evento("evento-piazza-anfiteatro-arte-musica", True, driver=driver)
    assert driver.eventi[0]["frenato"] is True
    assert driver.eventi[0]["stato"] == "attivo", "lo stato non viene mai toccato"


def test_scrivi_freno_evento_rilascia_il_freno() -> None:
    evento = dict(_EVENTO_GREZZO)
    evento["frenato"] = True
    driver = _FakeDriver(eventi=[evento])
    scrivi_freno_evento("evento-piazza-anfiteatro-arte-musica", False, driver=driver)
    assert driver.eventi[0]["frenato"] is False
    assert driver.eventi[0]["stato"] == "attivo"


def test_scrivi_freno_evento_rilascio_non_riporta_levento_ad_attivo() -> None:
    """Verifica ESPLICITA (non per assunzione) del punto §7.1 del checklist:
    `rilascia_freno`/`scrivi_freno_evento` non impostano MAI `e.stato` a
    'attivo' (o a qualunque altro valore) — un `:Evento` `sospeso` E
    `frenato=True`, una volta rilasciato (`frenato=False`), resta `sospeso`:
    torna raccomandabile SOLO se la frizione automatica lo riporta `attivo`
    in un momento successivo, mai come effetto collaterale del rilascio del
    freno stesso."""
    evento = dict(_EVENTO_GREZZO)
    evento["stato"] = "sospeso"
    evento["frenato"] = True
    driver = _FakeDriver(eventi=[evento])

    scrivi_freno_evento("evento-piazza-anfiteatro-arte-musica", False, driver=driver)

    assert driver.eventi[0]["frenato"] is False
    assert driver.eventi[0]["stato"] == "sospeso", (
        "il rilascio del freno non deve MAI riportare l'evento ad 'attivo': "
        "resta nello stato che la frizione automatica indica, qui 'sospeso'"
    )


def test_scrivi_freno_evento_query_eseguita_non_contiene_mai_stato() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    scrivi_freno_evento("evento-piazza-anfiteatro-arte-musica", True, driver=driver)
    [(query, params)] = driver.query_eseguite
    assert "SET e.stato" not in query
    assert params is not None
    assert "stato" not in params


def test_scrivi_freno_evento_inesistente_e_un_no_op_silenzioso() -> None:
    driver = _FakeDriver(eventi=[])
    scrivi_freno_evento("evento-mai-esistito", True, driver=driver)  # non deve sollevare
    assert driver.eventi == []


def test_scrivi_freno_evento_grafo_irraggiungibile_solleva_errore() -> None:
    driver = _FakeDriver(session_error=RuntimeError("connessione rifiutata"))
    with pytest.raises(FrenoPatternError):
        scrivi_freno_evento("evento-x", True, driver=driver)


# ---------------------------------------------------------------------------
# Neo4jFrenoClient — wrapper comodo, un driver riusato
# ---------------------------------------------------------------------------


def test_neo4j_freno_client_imposta_frenato_delega() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    client = Neo4jFrenoClient(driver, database="neo4j")

    client.imposta_frenato("evento-piazza-anfiteatro-arte-musica", True)

    assert driver.eventi[0]["frenato"] is True


def test_neo4j_freno_client_close_chiude_il_driver() -> None:
    driver = _FakeDriver()
    client = Neo4jFrenoClient(driver)

    client.close()

    assert driver.closed is True


def test_neo4j_freno_client_context_manager_chiude_il_driver() -> None:
    driver = _FakeDriver()
    with Neo4jFrenoClient(driver) as client:
        assert client is not None
    assert driver.closed is True


# ---------------------------------------------------------------------------
# tira_freno / rilascia_freno — funzioni di dominio, writer finto + repo
# ---------------------------------------------------------------------------


class _WriterSpia:
    """Un `writer` finto (`(evento_id, frenato) -> None`): registra ogni
    chiamata, mai una connessione reale."""

    def __init__(self) -> None:
        self.chiamate: list[tuple[str, bool]] = []

    def __call__(self, evento_id: str, frenato: bool) -> None:
        self.chiamate.append((evento_id, frenato))


def test_tira_freno_scrive_sul_grafo_e_registra_il_tiro() -> None:
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    riga = tira_freno(
        "evento-x",
        attore="promotore-uno",
        motivazione="ordinanza comunale immediata",
        writer=writer,
        repo=repo,
        place_id="piazza-anfiteatro",
        temi=["arte", "musica"],
        quando=QUANDO,
    )

    assert writer.chiamate == [("evento-x", True)]
    assert riga.azione == "tirato"
    assert riga.motivazione == "ordinanza comunale immediata"
    [registrata] = repo.per_evento("evento-x")
    assert registrata.azione == "tirato"
    assert registrata.attore == "promotore-uno"
    assert registrata.motivazione == "ordinanza comunale immediata"


@pytest.mark.parametrize("motivazione_invalida", ["", "   ", None])
def test_tira_freno_senza_motivazione_e_rifiutato_senza_scrivere_nulla(
    motivazione_invalida: str | None,
) -> None:
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    with pytest.raises(ValueError):
        tira_freno(
            "evento-x",
            attore="promotore-uno",
            motivazione=motivazione_invalida,  # type: ignore[arg-type]
            writer=writer,
            repo=repo,
            quando=QUANDO,
        )

    assert writer.chiamate == [], "nessuna scrittura sul grafo se la motivazione manca"
    assert repo.per_evento("evento-x") == [], "nessuna riga registrata se la motivazione manca"


@pytest.mark.parametrize("attore_invalido", ["", "   ", None])
def test_tira_freno_senza_attore_e_rifiutato_senza_scrivere_nulla(
    attore_invalido: str | None,
) -> None:
    """Correzione ethics-guardian: un `attore` vuoto/whitespace/assente
    scriverebbe `e.frenato=true` sul grafo prima di fallire (o, con
    `InMemoryPatternFrenatoRepository`, senza fallire affatto) su
    `repo.registra` — un freno tirato senza alcuna riga di audit
    recuperabile su chi/quando/perché. La guardia deve rifiutare PRIMA di
    chiamare `writer`/`repo`, stesso stile della guardia su `motivazione`
    sopra."""
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    with pytest.raises(ValueError):
        tira_freno(
            "evento-x",
            attore=attore_invalido,  # type: ignore[arg-type]
            motivazione="ordinanza comunale immediata",
            writer=writer,
            repo=repo,
            quando=QUANDO,
        )

    assert writer.chiamate == [], "nessuna scrittura sul grafo se l'attore manca"
    assert repo.per_evento("evento-x") == [], "nessuna riga registrata se l'attore manca"


def test_rilascia_freno_scrive_sul_grafo_e_registra_il_rilascio() -> None:
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    riga = rilascia_freno(
        "evento-x", attore="promotore-uno", writer=writer, repo=repo, quando=QUANDO
    )

    assert writer.chiamate == [("evento-x", False)]
    assert riga.azione == "rilasciato"
    assert riga.motivazione is None


def test_rilascia_freno_accetta_una_motivazione_facoltativa() -> None:
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    riga = rilascia_freno(
        "evento-x",
        attore="promotore-uno",
        motivazione="la situazione è rientrata",
        writer=writer,
        repo=repo,
        quando=QUANDO,
    )

    assert riga.motivazione == "la situazione è rientrata"


@pytest.mark.parametrize("attore_invalido", ["", "   ", None])
def test_rilascia_freno_senza_attore_e_rifiutato_senza_scrivere_nulla(
    attore_invalido: str | None,
) -> None:
    """Stessa correzione ethics-guardian di `tira_freno`, simmetrica sul
    rilascio."""
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    with pytest.raises(ValueError):
        rilascia_freno(
            "evento-x",
            attore=attore_invalido,  # type: ignore[arg-type]
            writer=writer,
            repo=repo,
            quando=QUANDO,
        )

    assert writer.chiamate == [], "nessuna scrittura sul grafo se l'attore manca"
    assert repo.per_evento("evento-x") == [], "nessuna riga registrata se l'attore manca"


def test_tiro_e_rilascio_ripetuti_producono_righe_multiple() -> None:
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    tira_freno(
        "evento-x",
        attore="promotore-uno",
        motivazione="primo tiro",
        writer=writer,
        repo=repo,
        quando=QUANDO,
    )
    rilascia_freno("evento-x", attore="promotore-uno", writer=writer, repo=repo, quando=QUANDO)
    tira_freno(
        "evento-x",
        attore="promotore-due",
        motivazione="secondo tiro, causa diversa",
        writer=writer,
        repo=repo,
        quando=QUANDO,
    )

    assert writer.chiamate == [("evento-x", True), ("evento-x", False), ("evento-x", True)]
    righe = repo.per_evento("evento-x")
    assert [riga.azione for riga in righe] == ["tirato", "rilasciato", "tirato"]
    assert len({riga.id for riga in righe}) == 3, "mai un upsert: sempre righe nuove"


def test_ne_tira_ne_rilascia_scrivono_mai_lo_stato() -> None:
    """Verifica ESPLICITA, al livello del `writer`: la firma stessa di
    `_Writer` (`(evento_id, frenato) -> None`) non lascia spazio a un
    parametro `stato` — nessuna chiamata registrata dalla spia porta mai un
    terzo argomento o una chiave `stato`."""
    writer = _WriterSpia()
    repo = InMemoryPatternFrenatoRepository()

    tira_freno(
        "evento-x",
        attore="promotore-uno",
        motivazione="motivo",
        writer=writer,
        repo=repo,
        quando=QUANDO,
    )
    rilascia_freno("evento-x", attore="promotore-uno", writer=writer, repo=repo, quando=QUANDO)

    for chiamata in writer.chiamate:
        assert len(chiamata) == 2  # (evento_id, frenato) — nessun terzo campo "stato"
