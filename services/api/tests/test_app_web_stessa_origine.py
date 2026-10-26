"""App web servita dal BFF sulla stessa origine (ondata 4, compito 2).

Blocca: (1) le rotte dell'API hanno la precedenza sul mount `/` per TUTTE le
rotte reali, enumerate da `app.routes` (nessuna lista scritta a mano: una rotta
nuova e' coperta da sola); (2) `GET /` e i file statici con `no-cache`;
(3) senza `APP_WEB_DIR` o con cartella inesistente nessun mount; (4) `GET
/itinerary` col mount risponde 404 (effetto accettato e documentato: il mount
cattura cio' che le rotte non gestiscono per quel metodo); (5) il middleware
CORS della dashboard resta invariato.

Nessuna infrastruttura reale: ogni selettore `get_*` di `api.main` e ogni
dipendenza FastAPI sono sostituiti da un doppio che solleva; la risposta puo'
quindi essere 4xx/5xx, ma deve venire dall'API, mai dall'index.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from api.settings import get_settings  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402

MARCATORE_INDEX = "INDEX-APP-WEB-MARCATORE-7f3a"
ROTTE_DOCUMENTAZIONE = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _scrivi_build(cartella: Path) -> Path:
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "index.html").write_text(
        f"<!doctype html><html><body>{MARCATORE_INDEX}</body></html>", encoding="utf-8"
    )
    (cartella / "main.dart.js").write_text("console.log('finto');", encoding="utf-8")
    return cartella


def _stacca_mount() -> None:
    api_main.app.router.routes[:] = [
        r for r in api_main.app.router.routes if not (isinstance(r, Mount) and r.name == "app-web")
    ]


def _vietato(*_a: Any, **_k: Any) -> Any:
    raise RuntimeError("infrastruttura vietata nei test")


def _isola_infrastruttura(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in [n for n in dir(api_main) if n.startswith("get_") and n != "get_settings"]:
        funzione = getattr(api_main, nome)
        if callable(funzione):
            api_main.app.dependency_overrides[funzione] = _vietato
            monkeypatch.setattr(api_main, nome, _vietato)
    # Le fonti dell'Index sono risolte dentro gli endpoint dashboard.
    try:
        deps_index = importlib.import_module("intelligence_index.deps")
    except ImportError:
        return
    for nome in [n for n in dir(deps_index) if n.startswith("get_")]:
        monkeypatch.setattr(deps_index, nome, _vietato)


@pytest.fixture(autouse=True)
def _pulizia(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _stacca_mount()
    _isola_infrastruttura(monkeypatch)
    yield
    _stacca_mount()
    api_main.app.dependency_overrides.clear()


@pytest.fixture
def build(tmp_path: Path) -> Path:
    return _scrivi_build(tmp_path / "web")


@pytest.fixture
def client_con_web(build: Path) -> TestClient:
    assert api_main.monta_app_web(api_main.app, build) is True
    return TestClient(api_main.app, raise_server_exceptions=False)


@pytest.fixture
def client_senza_web() -> TestClient:
    return TestClient(api_main.app, raise_server_exceptions=False)


def _rotte_reali() -> list[tuple[str, str]]:
    """(metodo, path) di ogni rotta dell'app, escluso il mount."""
    coppie: list[tuple[str, str]] = []
    for r in api_main.app.routes:
        if isinstance(r, Mount):
            continue
        assert isinstance(r, APIRoute | Route), f"tipo di rotta non previsto: {r!r}"
        for metodo in sorted((r.methods or set()) - {"HEAD", "OPTIONS"}):
            coppie.append((metodo, r.path))
    return coppie


def _istanzia(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "valore", path)


def test_enumerazione_comprende_api_e_documentazione(client_con_web: TestClient) -> None:
    path = {p for _, p in _rotte_reali()}
    assert ROTTE_DOCUMENTAZIONE <= path
    assert {"/health", "/itinerary", "/dashboard/index"} <= path


def test_api_ha_precedenza_su_tutte_le_rotte(client_con_web: TestClient) -> None:
    rotte = _rotte_reali()
    assert rotte
    for metodo, path in rotte:
        r = client_con_web.request(metodo, _istanzia(path))
        assert MARCATORE_INDEX not in r.text, f"{metodo} {path} servita dall'index"
        # Il mount aggiunge no-cache a ogni sua risposta: una rotta reale no.
        assert r.headers.get("cache-control") != "no-cache", f"{metodo} {path} servita dal mount"


def test_rotte_note_servite_dall_api(client_con_web: TestClient) -> None:
    assert client_con_web.get("/health").status_code == 200
    assert "openapi" in client_con_web.get("/openapi.json").json()
    assert "swagger" in client_con_web.get("/docs").text.lower()


def test_radice_serve_index_con_no_cache(client_con_web: TestClient) -> None:
    r = client_con_web.get("/")
    assert r.status_code == 200
    assert MARCATORE_INDEX in r.text
    assert r.headers["cache-control"] == "no-cache"


def test_file_statico_con_no_cache(client_con_web: TestClient) -> None:
    r = client_con_web.get("/main.dart.js")
    assert r.status_code == 200
    assert "finto" in r.text
    assert r.headers["cache-control"] == "no-cache"


def test_senza_mount_radice_404(client_senza_web: TestClient) -> None:
    assert client_senza_web.get("/").status_code == 404


@pytest.mark.parametrize("cartella", [None, "", "non/esiste/proprio"])
def test_monta_app_web_senza_cartella_valida_non_monta(
    cartella: str | None, tmp_path: Path
) -> None:
    valore = str(tmp_path / cartella) if cartella else cartella
    prima = len(api_main.app.routes)
    assert api_main.monta_app_web(api_main.app, valore) is False
    assert len(api_main.app.routes) == prima
    assert TestClient(api_main.app, raise_server_exceptions=False).get("/").status_code == 404


def test_env_app_web_dir_attiva_il_mount_all_import(
    monkeypatch: pytest.MonkeyPatch, build: Path
) -> None:
    """Percorso reale: APP_WEB_DIR + reload di api.main, poi ripristino."""
    monkeypatch.setenv("APP_WEB_DIR", str(build))
    get_settings.cache_clear()
    try:
        ricaricato = importlib.reload(api_main)
        r = TestClient(ricaricato.app, raise_server_exceptions=False).get("/")
        assert r.status_code == 200 and MARCATORE_INDEX in r.text
    finally:
        monkeypatch.delenv("APP_WEB_DIR", raising=False)
        get_settings.cache_clear()
        importlib.reload(api_main)
    assert TestClient(api_main.app, raise_server_exceptions=False).get("/").status_code == 404


def test_env_cartella_inesistente_nessun_mount(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APP_WEB_DIR", str(tmp_path / "assente"))
    get_settings.cache_clear()
    try:
        ricaricato = importlib.reload(api_main)
        assert TestClient(ricaricato.app, raise_server_exceptions=False).get("/").status_code == 404
    finally:
        monkeypatch.delenv("APP_WEB_DIR", raising=False)
        get_settings.cache_clear()
        importlib.reload(api_main)


def test_get_itinerary_con_mount_e_404(client_con_web: TestClient) -> None:
    """Effetto accettato dal committente: la rotta e' solo-POST, il mount
    cattura il GET e risponde 404 invece di 405."""
    r = client_con_web.get("/itinerary")
    assert r.status_code == 404
    assert MARCATORE_INDEX not in r.text


def test_cors_dashboard_invariato(client_con_web: TestClient) -> None:
    # `periodo` mancante -> 422 prima di qualunque sorgente: il middleware agisce comunque.
    con = client_con_web.get("/dashboard/index")
    assert con.status_code == 422
    assert con.headers.get("access-control-allow-origin") == "*"
    assert client_con_web.get("/").headers.get("access-control-allow-origin") is None
    pre = client_con_web.options(
        "/dashboard/index", headers={"Access-Control-Request-Method": "GET", "Origin": "null"}
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-methods"] == "GET"
    # Identico senza mount.
    _stacca_mount()
    senza = TestClient(api_main.app, raise_server_exceptions=False).get("/dashboard/index")
    assert senza.status_code == 422
    assert senza.headers.get("access-control-allow-origin") == "*"
