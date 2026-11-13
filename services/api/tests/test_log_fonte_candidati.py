"""All'avvio il BFF dichiara UNA volta la fonte dei candidati, senza rivelare
valori della configurazione e senza aprire connessioni (driver Neo4j pigro).

Isolamento: `api.settings.ENV_FILE` punta a un `.env` temporaneo (mai quello
reale), `NEO4J_*` sono rimosse dall'ambiente di processo, e la risoluzione
DNS / `socket.create_connection` sono vietate per tutta la durata del test.
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from api import deps as api_deps
from api import main as api_main
from api import settings as api_settings
from fastapi.testclient import TestClient

RIGA_SEED = "fonte dei candidati: seed (credenziali Neo4j assenti)"
RIGA_NEO4J = "fonte dei candidati: Neo4j"

URI = "neo4j+s://irraggiungibile.invalid"
HOST = "irraggiungibile.invalid"
UTENTE = "utente-sentinella-7f3a"
PASSWORD = "password-sentinella-9c2e"
DATABASE = "database-sentinella-4b1d"
VALORI_SENTINELLA = (URI, HOST, UTENTE, PASSWORD, DATABASE)

VARIABILI_NEO4J = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")


def _svuota_cache() -> None:
    api_settings.get_settings.cache_clear()
    api_deps.get_candidate_source.cache_clear()
    api_deps.get_dataset.cache_clear()


@pytest.fixture(autouse=True)
def _pulizia() -> Iterator[None]:
    _svuota_cache()
    yield
    # Chiude il driver se la fonte Neo4j e' stata creata (la cache ha un solo
    # elemento, quello dell'ultimo avvio).
    if api_deps.get_candidate_source.cache_info().currsize:
        sorgente = api_deps.get_candidate_source()
        chiudi = getattr(sorgente, "close", None)
        if callable(chiudi):
            chiudi()
    _svuota_cache()


@pytest.fixture
def senza_rete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vieta DNS e connessioni TCP: se l'avvio toccasse la rete, il test cade."""

    def _vietato(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("accesso alla rete vietato durante l'avvio del BFF")

    monkeypatch.setattr(socket, "getaddrinfo", _vietato)
    monkeypatch.setattr(socket, "create_connection", _vietato)


def _prepara_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, righe: list[str]) -> None:
    for nome in VARIABILI_NEO4J:
        monkeypatch.delenv(nome, raising=False)
    env = tmp_path / ".env"
    env.write_text("\n".join(righe) + "\n", encoding="utf-8")
    monkeypatch.setattr(api_settings, "ENV_FILE", env)


def _avvia(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    # Il lifespan deve usare davvero il selettore di api.deps (nessun
    # monkeypatch residuo di altri test su api.main.get_candidate_source).
    assert api_main.get_candidate_source is api_deps.get_candidate_source
    caplog.set_level(logging.DEBUG)  # root: cattura tutti i logger
    caplog.set_level(logging.INFO, logger="api.deps")
    with TestClient(api_main.app) as client:
        assert client.get("/health").status_code == 200
    return list(caplog.records)


def _righe_fonte(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [r for r in records if r.name == "api.deps" and "fonte dei candidati" in r.getMessage()]


def _nessun_valore_nei_log(records: list[logging.LogRecord]) -> None:
    for r in records:
        testo = r.getMessage()
        if r.exc_text:
            testo += r.exc_text
        for valore in VALORI_SENTINELLA:
            assert valore not in testo, f"valore di configurazione nel log di {r.name}"


def test_avvio_senza_credenziali_logga_una_riga_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    senza_rete: None,
) -> None:
    _prepara_env(monkeypatch, tmp_path, ["CITY_TZ=Europe/Rome"])
    records = _avvia(caplog)

    righe = _righe_fonte(records)
    assert [r.getMessage() for r in righe] == [RIGA_SEED]
    assert righe[0].levelno == logging.INFO
    # La riga seed nomina "Neo4j" ("credenziali Neo4j assenti"): si esclude la
    # riga della fonte Neo4j, non ogni occorrenza della parola.
    assert not any(r.getMessage() == RIGA_NEO4J for r in records)
    _nessun_valore_nei_log(records)


def test_avvio_con_credenziali_logga_una_riga_neo4j_senza_valori(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    senza_rete: None,
) -> None:
    _prepara_env(
        monkeypatch,
        tmp_path,
        [
            f"NEO4J_URI={URI}",
            f"NEO4J_USERNAME={UTENTE}",
            f"NEO4J_PASSWORD={PASSWORD}",
            f"NEO4J_DATABASE={DATABASE}",
        ],
    )
    # Nessun 503 e nessuna eccezione all'avvio: `_avvia` esce da `with
    # TestClient` senza errori, e /health risponde 200, con rete vietata.
    records = _avvia(caplog)

    righe = _righe_fonte(records)
    assert [r.getMessage() for r in righe] == [RIGA_NEO4J]
    assert righe[0].levelno == logging.INFO
    assert not any("seed" in r.getMessage() for r in righe)
    _nessun_valore_nei_log(records)
