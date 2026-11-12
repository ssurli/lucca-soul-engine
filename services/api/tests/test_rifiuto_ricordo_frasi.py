"""`POST /memory` rifiutato: la frase per la persona e' scelta dal TIPO
dell'eccezione (`api.main._FRASI_RIFIUTO_RICORDO`), mai da `str(exc)`.

Nessun DB reale: il repository e' sostituito con `app.dependency_overrides`
(stessa tecnica di `tests/test_integration_wave2_persistence.py`).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
api_deps = pytest.importorskip("api.deps", reason="`api` non installabile")
from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemoryMemoryRepository,
    InvalidTargetsError,
    UrbanMemoryError,
)

FRASE_CONSENSO = "Per conservare il ricordo serve il tuo consenso: spunta la casella e riprova."
FRASE_LICENZA = "Scegli una licenza per il ricordo e riprova."
FRASE_PSEUDONIMO = "Non è stato possibile firmare il ricordo. Chiudi il foglio, riaprilo e riprova."
FRASE_GENERICA = "Il ricordo non può essere conservato così com'è."

# Valori sentinella univoci: non devono MAI riapparire nel corpo del 422.
SENTINELLA_TESTO = "TESTO-SENTINELLA-7f3a91c2"
SENTINELLA_MEDIA = "https://media.example/SENTINELLA-media-5b8d"
SENTINELLA_CONTRIBUTORE = "CONTRIBUTORE-SENTINELLA-c04e"
NOMI_TECNICI = ("MemoryContribution", "consenso deve", "contributor_id", "Error", "licenza deve")


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "mem-frasi-1",
        "kind": "racconto",
        "testo": SENTINELLA_TESTO,
        "media_uri": SENTINELLA_MEDIA,
        "riguarda": ["luogo-frasi"],
        "contributor_id": SENTINELLA_CONTRIBUTORE,
        "contributor_kind": "cittadino",
        "esperienza_id": None,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": "2026-07-14T10:00:00",
    }
    base.update(overrides)
    return base


class _SottoclasseNuova(UrbanMemoryError):
    """Sottoclasse futura non prevista dalla tabella delle frasi."""


class _RepoChe(InMemoryMemoryRepository):
    def __init__(self, eccezione: Exception) -> None:
        super().__init__()
        self._eccezione = eccezione

    def submit(self, contribution: Any) -> Any:
        raise self._eccezione


@pytest.fixture
def client() -> Iterator[TestClient]:
    api_main.app.dependency_overrides[api_deps.get_memory_repository] = InMemoryMemoryRepository
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def _client_con_eccezione(eccezione: Exception) -> TestClient:
    api_main.app.dependency_overrides[api_deps.get_memory_repository] = lambda: _RepoChe(eccezione)
    return TestClient(api_main.app)


def _verifica_rifiuto(resp: Any, frase: str, payload: dict[str, Any]) -> None:
    assert resp.status_code == 422
    assert resp.json() == {"detail": frase}
    assert "charset=utf-8" in resp.headers["content-type"].lower()
    corpo = resp.content.decode("utf-8")
    for segreto in (payload["testo"], payload["media_uri"], payload["contributor_id"]):
        if segreto:
            assert segreto not in corpo
    for nome in NOMI_TECNICI:
        assert nome not in corpo


def test_senza_consenso(client: TestClient) -> None:
    p = _payload(consenso=False)
    _verifica_rifiuto(client.post("/memory", json=p), FRASE_CONSENSO, p)


def test_licenza_di_soli_spazi(client: TestClient) -> None:
    p = _payload(licenza="   ")
    _verifica_rifiuto(client.post("/memory", json=p), FRASE_LICENZA, p)


def test_contributor_id_vuoto(client: TestClient) -> None:
    p = _payload(contributor_id="")
    _verifica_rifiuto(client.post("/memory", json=p), FRASE_PSEUDONIMO, p)


def test_urban_memory_error_generica_via_http() -> None:
    try:
        p = _payload()
        resp = _client_con_eccezione(
            UrbanMemoryError(f"MemoryContribution contributor_id {SENTINELLA_CONTRIBUTORE}")
        ).post("/memory", json=p)
        _verifica_rifiuto(resp, FRASE_GENERICA, p)
    finally:
        api_main.app.dependency_overrides.clear()


def test_sottoclasse_nuova_via_http() -> None:
    try:
        p = _payload()
        resp = _client_con_eccezione(
            _SottoclasseNuova(f"consenso deve essere True {SENTINELLA_TESTO}")
        ).post("/memory", json=p)
        _verifica_rifiuto(resp, FRASE_GENERICA, p)
    finally:
        api_main.app.dependency_overrides.clear()


def test_invalid_targets_error_frase_generica_via_http() -> None:
    try:
        p = _payload()
        eccezione = InvalidTargetsError("mem-frasi-1", ["luogo-frasi"])
        resp = _client_con_eccezione(eccezione).post("/memory", json=p)
        _verifica_rifiuto(resp, FRASE_GENERICA, p)
    finally:
        api_main.app.dependency_overrides.clear()


@pytest.mark.parametrize("eccezione", [UrbanMemoryError("x"), _SottoclasseNuova("y")])
def test_gestore_diretto_con_request_fittizia(eccezione: UrbanMemoryError) -> None:
    request = Request({"type": "http", "method": "POST", "path": "/memory", "headers": []})
    risposta = asyncio.run(
        _chiama(api_main.urban_memory_error_handler, request, eccezione)
    )
    assert risposta.status_code == 422
    assert json.loads(risposta.body) == {"detail": FRASE_GENERICA}
    assert "charset=utf-8" in risposta.headers["content-type"].lower()


async def _chiama(gestore: Any, request: Request, exc: UrbanMemoryError) -> Any:
    return gestore(request, exc)
