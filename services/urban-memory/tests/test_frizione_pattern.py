"""Test di `urban_memory.frizione_pattern`: la funzione PURA di calcolo
(`calcola_transizione`), la generazione pura di Cypher
(`eventi_ricorrenti_read_cypher`/`frizione_stato_write_cypher`), e la loro
esecuzione (`leggi_eventi_ricorrenti`/`scrivi_stato_evento`/
`Neo4jFrizioneClient`) contro un driver/sessione Neo4j FINTI, locali a questo
modulo (nessuna connessione reale).

`main()` NON è testato qui — stesso principio, dichiarato dallo stesso
motivo, di `tests/test_curatela_pattern.py`: costruisce sempre
`PostgresTracciaRepository`/`Neo4jFrizioneClient.from_env()` al suo interno
(nessun parametro di iniezione nella firma), una CLI di persistenza REALE
verificata girandola contro uno storage vero, non con un mock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from urban_memory.frizione_pattern import (
    EVENTI_RICORRENTI_READ_QUERY_PATH,
    FRIZIONE_STATO_WRITE_QUERY_PATH,
    EventoRicorrente,
    FrizionePatternError,
    Neo4jFrizioneClient,
    calcola_transizione,
    eventi_ricorrenti_read_cypher,
    frizione_stato_write_cypher,
    leggi_eventi_ricorrenti,
    scrivi_stato_evento,
)

ADESSO = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# calcola_transizione — pura, nessun I/O
# ---------------------------------------------------------------------------


def test_dormiente_non_transita_mai() -> None:
    """Nessuna riattivazione da dormiente è prevista in questo comando —
    fuori scope, per costruzione ritorna sempre (None, None)."""
    occorrenze = [ADESSO]  # traccia frescissima: se ci fosse un bug, riattiverebbe
    nuovo_stato, motivo = calcola_transizione("dormiente", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_nessuna_occorrenza_nessuna_transizione() -> None:
    nuovo_stato, motivo = calcola_transizione("attivo", 7.0, [], ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_cadenza_non_positiva_nessuna_transizione() -> None:
    """Stesso principio di `ricorrenza.rileva_candidati`: una cadenza <= 0
    non è definibile, mai una divisione per zero, mai una transizione
    fabbricata."""
    occorrenze = [ADESSO - timedelta(days=100)]
    nuovo_stato, motivo = calcola_transizione("attivo", 0.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_occorrenza_nel_futuro_e_un_caso_degenere_nessuna_transizione() -> None:
    occorrenze = [ADESSO + timedelta(days=10)]
    nuovo_stato, motivo = calcola_transizione("attivo", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_attivo_resta_attivo_sotto_la_soglia_di_battiti_mancati() -> None:
    # Cadenza settimanale, ultima occorrenza una settimana fa: 1 battito
    # mancato, sotto K=2 di default.
    occorrenze = [ADESSO - timedelta(days=7)]
    nuovo_stato, motivo = calcola_transizione("attivo", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_attivo_passa_a_sospeso_a_k_battiti_mancati() -> None:
    # Cadenza settimanale, 14 giorni trascorsi: esattamente 2 battiti
    # mancati (K=2 default) -> sospeso.
    occorrenze = [ADESSO - timedelta(days=14)]
    nuovo_stato, motivo = calcola_transizione("attivo", 7.0, occorrenze, ADESSO)
    assert nuovo_stato == "sospeso"
    assert motivo == "cadenza mancata"


def test_attivo_usa_lultima_occorrenza_non_la_prima() -> None:
    # Prima occorrenza vecchissima (attiverebbe la sospensione da sola), ma
    # l'ULTIMA è recente: nessuna transizione.
    occorrenze = [
        ADESSO - timedelta(days=365),
        ADESSO - timedelta(days=1),
    ]
    nuovo_stato, motivo = calcola_transizione("attivo", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_sospeso_torna_attivo_su_traccia_fresca() -> None:
    # Sotto la soglia di battito mancato (K=2): il pattern ha ripreso.
    occorrenze = [ADESSO - timedelta(days=1)]
    nuovo_stato, motivo = calcola_transizione("sospeso", 7.0, occorrenze, ADESSO)
    assert nuovo_stato == "attivo"
    assert motivo == "traccia fresca"


def test_sospeso_resta_sospeso_sopra_k_ma_sotto_lorizzonte() -> None:
    # 3 battiti mancati (>= K=2) ma tempo assoluto (21gg) ben sotto
    # l'orizzonte di default (180gg): resta sospeso, nessuna transizione.
    occorrenze = [ADESSO - timedelta(days=21)]
    nuovo_stato, motivo = calcola_transizione("sospeso", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_sospeso_passa_a_dormiente_oltre_lorizzonte() -> None:
    occorrenze = [ADESSO - timedelta(days=200)]  # oltre ORIZZONTE_DORMIENZA_GIORNI=180
    nuovo_stato, motivo = calcola_transizione("sospeso", 7.0, occorrenze, ADESSO)
    assert nuovo_stato == "dormiente"
    assert motivo == "sospensione oltre orizzonte"


# ---------------------------------------------------------------------------
# Regressione: l'orizzonte di dormienza è DERIVATO dalla cadenza (non una
# costante fissa indipendente da essa) — un pattern a cadenza lunga (annuale)
# deve restare `sospeso` per un periodo proporzionato alla propria cadenza,
# non attraversarlo in modo trascurabile o nullo.
# ---------------------------------------------------------------------------


def test_pattern_annuale_entra_in_sospeso_ma_non_e_gia_dormiente() -> None:
    # Cadenza annuale (~365gg), 2 battiti mancati (K=2 default) -> sospeso,
    # esattamente all'istante in cui l'orizzonte FISSO (180gg, vecchio
    # comportamento) sarebbe già ampiamente superato. Con l'orizzonte
    # derivato dalla cadenza (K_ORIZZONTE_DORMIENZA=3.0 default), a questo
    # stesso istante il pattern deve restare `sospeso`, MAI passare
    # direttamente a `dormiente`.
    cadenza_giorni = 365.0
    occorrenze = [ADESSO - timedelta(days=2 * cadenza_giorni)]  # ~730gg: entra in sospeso
    nuovo_stato, motivo = calcola_transizione("attivo", cadenza_giorni, occorrenze, ADESSO)
    assert nuovo_stato == "sospeso"
    assert motivo == "cadenza mancata"

    # Stessa combinazione (occorrenze, cadenza), ma partendo da `sospeso`:
    # non deve ancora essere `dormiente`, perché l'orizzonte derivato
    # (K_ORIZZONTE_DORMIENZA * cadenza_giorni = 3.0 * 365 = 1095gg) non è
    # ancora superato dai ~730gg trascorsi.
    nuovo_stato, motivo = calcola_transizione("sospeso", cadenza_giorni, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_pattern_annuale_resta_sospeso_per_un_periodo_proporzionato_alla_cadenza() -> None:
    # Ancora ben oltre il vecchio orizzonte fisso (180gg) ma sotto la soglia
    # derivata dalla cadenza (3.0 * 365 = 1095gg): resta sospeso, nessuna
    # transizione fabbricata a dormiente.
    cadenza_giorni = 365.0
    occorrenze = [ADESSO - timedelta(days=1000)]
    nuovo_stato, motivo = calcola_transizione("sospeso", cadenza_giorni, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_pattern_annuale_passa_a_dormiente_oltre_lorizzonte_derivato_dalla_cadenza() -> None:
    # Oltre la soglia derivata (3.0 * 365 = 1095gg): dormiente, come atteso.
    cadenza_giorni = 365.0
    occorrenze = [ADESSO - timedelta(days=1100)]
    nuovo_stato, motivo = calcola_transizione("sospeso", cadenza_giorni, occorrenze, ADESSO)
    assert nuovo_stato == "dormiente"
    assert motivo == "sospensione oltre orizzonte"


def test_pattern_settimanale_nessuna_regressione_con_lorizzonte_derivato() -> None:
    # Cadenza corta (settimanale, già testata sopra): il pavimento assoluto
    # ORIZZONTE_DORMIENZA_GIORNI=180 vince su K_ORIZZONTE_DORMIENZA * 7
    # (= 21gg con i default) — stesso comportamento di prima, nessuna
    # regressione sul caso già coperto da
    # `test_sospeso_resta_sospeso_sopra_k_ma_sotto_lorizzonte` e
    # `test_sospeso_passa_a_dormiente_oltre_lorizzonte`.
    occorrenze_sotto_orizzonte = [ADESSO - timedelta(days=21)]
    nuovo_stato, motivo = calcola_transizione("sospeso", 7.0, occorrenze_sotto_orizzonte, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)

    occorrenze_oltre_orizzonte = [ADESSO - timedelta(days=200)]
    nuovo_stato, motivo = calcola_transizione("sospeso", 7.0, occorrenze_oltre_orizzonte, ADESSO)
    assert nuovo_stato == "dormiente"
    assert motivo == "sospensione oltre orizzonte"


def test_stato_sconosciuto_nessuna_transizione_fabbricata() -> None:
    occorrenze = [ADESSO - timedelta(days=1000)]
    nuovo_stato, motivo = calcola_transizione("chissa-che-stato", 7.0, occorrenze, ADESSO)
    assert (nuovo_stato, motivo) == (None, None)


def test_soglie_configurabili_esplicitamente() -> None:
    """K e l'orizzonte sono parametri, non solo costanti globali — permette
    di testare la logica senza dipendere dai valori di default (tuning)."""
    occorrenze = [ADESSO - timedelta(days=10)]
    nuovo_stato, _ = calcola_transizione(
        "attivo", 5.0, occorrenze, ADESSO, k_battiti_sospensione=1
    )
    assert nuovo_stato == "sospeso"  # 2 battiti mancati >= k=1


# ---------------------------------------------------------------------------
# Query Cypher pure — nessuna connessione, nessuna esecuzione
# ---------------------------------------------------------------------------


def test_query_di_lettura_versionata_esiste() -> None:
    assert EVENTI_RICORRENTI_READ_QUERY_PATH.exists()
    assert EVENTI_RICORRENTI_READ_QUERY_PATH.name == "60_eventi_ricorrenti_read.cypher"


def test_query_di_scrittura_versionata_esiste() -> None:
    assert FRIZIONE_STATO_WRITE_QUERY_PATH.exists()
    assert FRIZIONE_STATO_WRITE_QUERY_PATH.name == "61_frizione_stato_write.cypher"


def test_eventi_ricorrenti_read_cypher_nessun_parametro_e_sola_lettura() -> None:
    query, params = eventi_ricorrenti_read_cypher()
    assert params == {}
    assert "MATCH (e:Evento {ricorrente: true})-[:SI_SVOLGE_A]->(l:Luogo)" in query
    # Sola lettura: nessuna clausola SET/MERGE ESEGUIBILE — cercata come
    # sintassi di clausola reale (`SET e.`/`MERGE (`), non come sottostringa
    # qualunque: i commenti versionati nel file discutono DI questi concetti
    # in prosa ("nessun MATCH+SET qui", "la MERGE di promozione..."), quindi
    # una ricerca cieca della sola parola darebbe un falso positivo sui
    # commenti stessi — stesso principio di
    # `test_promozione_evento.
    # test_promozione_evento_cypher_solo_match_sul_luogo_mai_merge_o_create`.
    assert "SET e." not in query
    assert "MERGE (" not in query


def test_eventi_ricorrenti_read_cypher_non_e_duplicata_come_stringa_altrove() -> None:
    """La query eseguita è ESATTAMENTE quella letta dal file versionato —
    stesso principio di `test_promozione_evento.test_query_versionata_esiste`:
    nessuna copia incollata nel modulo Python."""
    query, _ = eventi_ricorrenti_read_cypher()
    assert query == EVENTI_RICORRENTI_READ_QUERY_PATH.read_text(encoding="utf-8")


def test_eventi_ricorrenti_read_cypher_ritorna_le_proprieta_necessarie() -> None:
    query, _ = eventi_ricorrenti_read_cypher()
    for campo in ("evento_id", "place_id", "temi", "stato", "cadenza_giorni"):
        assert campo in query


def test_frizione_stato_write_cypher_solo_match_e_set_mai_merge() -> None:
    query, params = frizione_stato_write_cypher("evento-x", "sospeso")
    assert "MATCH (e:Evento {id: $evento_id})" in query
    assert "SET e.stato = $nuovo_stato" in query
    # Stessa cautela di sopra: cerca la clausola REALE `MERGE (`, non la
    # parola nuda (i commenti versionati la discutono in prosa).
    assert "MERGE (" not in query
    assert params == {"evento_id": "evento-x", "nuovo_stato": "sospeso"}


def test_frizione_stato_write_cypher_letta_dal_file_versionato_non_duplicata() -> None:
    """Stesso principio di `test_eventi_ricorrenti_read_cypher_non_e_duplicata_
    come_stringa_altrove`: la query eseguita è ESATTAMENTE quella nel file,
    mai una copia incollata nel modulo Python."""
    query, _ = frizione_stato_write_cypher("evento-x", "sospeso")
    assert query == FRIZIONE_STATO_WRITE_QUERY_PATH.read_text(encoding="utf-8")


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

        if "MATCH (e:Evento {ricorrente: true})" in query:
            return _FakeResult(list(self._driver.eventi))

        # Query di scrittura: MATCH (e:Evento {id: $evento_id}) SET e.stato = ...
        evento_id = params.get("evento_id")
        nuovo_stato = params.get("nuovo_stato")
        for evento in self._driver.eventi:
            if evento["evento_id"] == evento_id:
                evento["stato"] = nuovo_stato
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
}


def test_leggi_eventi_ricorrenti_vuota_se_nessun_evento() -> None:
    driver = _FakeDriver()
    assert leggi_eventi_ricorrenti(driver=driver) == []


def test_leggi_eventi_ricorrenti_mappa_le_proprieta() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])

    [evento] = leggi_eventi_ricorrenti(driver=driver)

    assert evento == EventoRicorrente(
        evento_id="evento-piazza-anfiteatro-arte-musica",
        place_id="piazza-anfiteatro",
        temi=("arte", "musica"),
        stato="attivo",
        cadenza_giorni=7.0,
    )


def test_leggi_eventi_ricorrenti_mappa_frenato_true() -> None:
    """`frenato` (freno di emergenza, `urban_memory.freno_pattern`,
    `docs/STATE_MACHINE.md` §4-bis(b)) è letto dalla stessa riga, insieme
    alle proprietà della frizione — un `:Evento` con il freno tirato."""
    grezzo = dict(_EVENTO_GREZZO)
    grezzo["frenato"] = True
    driver = _FakeDriver(eventi=[grezzo])

    [evento] = leggi_eventi_ricorrenti(driver=driver)

    assert evento.frenato is True


def test_leggi_eventi_ricorrenti_frenato_assente_di_default_a_false() -> None:
    """Un `:Evento` promosso PRIMA dell'esistenza del freno non ha la
    proprietà `frenato` sul nodo: la query versionata la legge con
    `coalesce(e.frenato, false)`, ma questo test simula anche il caso in cui
    la chiave manchi DEL TUTTO dalla riga (driver/versione della query
    precedente) — comportamento invariato, mai frenato di default."""
    grezzo = dict(_EVENTO_GREZZO)
    assert "frenato" not in grezzo
    driver = _FakeDriver(eventi=[grezzo])

    [evento] = leggi_eventi_ricorrenti(driver=driver)

    assert evento.frenato is False


def test_leggi_eventi_ricorrenti_frenato_none_e_false() -> None:
    """`coalesce` nella query non dovrebbe mai restituire `None`, ma la
    mappatura Python resta difensiva: una riga con `frenato=None` si legge
    comunque come `False`, mai come un errore o un `None` propagato."""
    grezzo = dict(_EVENTO_GREZZO)
    grezzo["frenato"] = None
    driver = _FakeDriver(eventi=[grezzo])

    [evento] = leggi_eventi_ricorrenti(driver=driver)

    assert evento.frenato is False


def test_leggi_eventi_ricorrenti_grafo_irraggiungibile_solleva_errore() -> None:
    driver = _FakeDriver(session_error=RuntimeError("connessione rifiutata"))
    with pytest.raises(FrizionePatternError):
        leggi_eventi_ricorrenti(driver=driver)


def test_scrivi_stato_evento_aggiorna_il_nodo() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    scrivi_stato_evento("evento-piazza-anfiteatro-arte-musica", "sospeso", driver=driver)
    assert driver.eventi[0]["stato"] == "sospeso"


def test_scrivi_stato_evento_inesistente_e_un_no_op_silenzioso() -> None:
    """MATCH puro: un evento_id non (più) esistente non solleva errore,
    nessun nodo fantasma creato."""
    driver = _FakeDriver(eventi=[])
    scrivi_stato_evento("evento-mai-esistito", "sospeso", driver=driver)  # non deve sollevare
    assert driver.eventi == []


def test_scrivi_stato_evento_grafo_irraggiungibile_solleva_errore() -> None:
    driver = _FakeDriver(session_error=RuntimeError("connessione rifiutata"))
    with pytest.raises(FrizionePatternError):
        scrivi_stato_evento("evento-x", "sospeso", driver=driver)


# ---------------------------------------------------------------------------
# Neo4jFrizioneClient — wrapper comodo, un driver riusato
# ---------------------------------------------------------------------------


def test_neo4j_frizione_client_eventi_ricorrenti_delega() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    client = Neo4jFrizioneClient(driver, database="neo4j")

    [evento] = client.eventi_ricorrenti()

    assert evento.evento_id == "evento-piazza-anfiteatro-arte-musica"


def test_neo4j_frizione_client_aggiorna_stato_delega() -> None:
    driver = _FakeDriver(eventi=[dict(_EVENTO_GREZZO)])
    client = Neo4jFrizioneClient(driver, database="neo4j")

    client.aggiorna_stato("evento-piazza-anfiteatro-arte-musica", "dormiente")

    assert driver.eventi[0]["stato"] == "dormiente"


def test_neo4j_frizione_client_close_chiude_il_driver() -> None:
    driver = _FakeDriver()
    client = Neo4jFrizioneClient(driver)

    client.close()

    assert driver.closed is True


def test_neo4j_frizione_client_context_manager_chiude_il_driver() -> None:
    driver = _FakeDriver()
    with Neo4jFrizioneClient(driver) as client:
        assert client is not None
    assert driver.closed is True
