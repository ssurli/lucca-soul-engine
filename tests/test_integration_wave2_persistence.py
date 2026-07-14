"""Test di integrazione — Wave 2 (completamento persistenza): distinzione
DOMINIO vs INFRASTRUTTURA sulla Urban Memory, attraverso il BFF (`api.main`).

Colpisce `services/api` con `TestClient`. I criteri qui sotto sono quelli
del committente per questa wave:

1. Storage giù (`MemoryStorageError`, infrastrutturale) -> **503** su
   `POST /memory` e su `GET /memory/{place_id}`, con il messaggio italiano
   generico esatto atteso da `api.main.memory_storage_error_handler` — e
   NESSUN dettaglio interno (DSN, `psycopg`, host) nel corpo della risposta.
2. Violazione di dominio (consenso mancante) resta **422**, non 503: la
   distinzione dominio/infrastruttura è verificata end-to-end, non solo a
   livello di tipo Python.
3. `MemoryStorageError` NON è una sottoclasse di `UrbanMemoryError` (così i
   due `@app.exception_handler` di `api.main` non si confondono: FastAPI
   sceglie l'handler più specifico registrato per il tipo dell'eccezione
   sollevata, e le due gerarchie devono restare disgiunte).

Se un test qui fallisce, il bug è nel servizio a valle (`api` o
`urban_memory`), non nel test: non "aggiustare" l'asserzione per farla
passare, segnala il bug al subagent competente (vedi CLAUDE.md).
"""

from __future__ import annotations

from typing import Any

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import MemoryStorageError, UrbanMemoryError

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)
api_deps = pytest.importorskip(
    "api.deps", reason="`api` non installabile: pip install -e services/api"
)

TestClient = fastapi_testclient.TestClient

_DETTAGLIO_503_ATTESO = "memoria temporaneamente non disponibile: riprova più tardi"

# Frammenti che NON devono mai comparire nel corpo di una risposta 503: un
# dettaglio infrastrutturale (DSN, driver, host) trapelato violerebbe la
# regola "mai un 500 opaco ma anche mai dettagli interni" di
# `api.main.memory_storage_error_handler`.
_FRAMMENTI_INTERNI_VIETATI = (
    "psycopg",
    "dsn",
    "postgresql://",
    "host=",
    "password",
    "sslmode",
    "connection",
    "traceback",
)


class _RepositoryGiu:
    """Repository finto che simula uno storage irraggiungibile: solleva
    `MemoryStorageError` (infrastrutturale) su OGNI operazione, con un
    messaggio che porta deliberatamente dettagli interni (DSN finto,
    'psycopg') per verificare che il BFF non li faccia mai trapelare nella
    risposta HTTP (li logga/propaga solo internamente, come farebbe
    `PostgresMemoryRepository` davvero)."""

    _MESSAGGIO_INTERNO = (
        "connessione fallita: dsn=postgresql://user:s3cr3t@db-host:5432/lucca "
        "(psycopg.OperationalError, sslmode=require)"
    )

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        raise MemoryStorageError(self._MESSAGGIO_INTERNO)

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        raise MemoryStorageError(self._MESSAGGIO_INTERNO)

    def list_pending(self) -> list[MemoryContribution]:
        raise MemoryStorageError(self._MESSAGGIO_INTERNO)

    def curate(self, memory_id: str) -> MemoryContribution:
        raise MemoryStorageError(self._MESSAGGIO_INTERNO)


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


@pytest.fixture()
def client_con_storage_giu() -> Any:
    """`TestClient` con `api.deps.get_memory_repository` sovrascritto da un
    repository che solleva SEMPRE `MemoryStorageError` — simula Postgres/Neon
    irraggiungibile senza avere bisogno di un database reale."""
    api_main.app.dependency_overrides[api_deps.get_memory_repository] = _RepositoryGiu
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "mem-w2p-default",
        "kind": MemoryKind.RACCONTO.value,
        "testo": "Un racconto di prova per i test di persistenza Wave 2.",
        "media_uri": None,
        "riguarda": ["bottega-w2p-default"],
        "contributor_id": "pseudonimo-test",
        "contributor_kind": PersonKind.CITTADINO.value,
        "esperienza_id": None,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": "2026-07-14T10:00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. 503 su storage giù — POST /memory
# ---------------------------------------------------------------------------


def test_post_memory_503_su_storage_giu(client_con_storage_giu: Any) -> None:
    payload = _payload(id="mem-w2p-post-giu")
    resp = client_con_storage_giu.post("/memory", json=payload)

    assert resp.status_code == 503
    body = resp.json()
    assert body == {"detail": _DETTAGLIO_503_ATTESO}

    corpo_minuscolo = resp.text.lower()
    for frammento in _FRAMMENTI_INTERNI_VIETATI:
        assert frammento not in corpo_minuscolo, (
            f"la risposta 503 espone un dettaglio interno vietato "
            f"({frammento!r}): {resp.text}"
        )


# ---------------------------------------------------------------------------
# 1bis. 503 su storage giù — GET /memory/{place_id}
# ---------------------------------------------------------------------------


def test_get_memory_by_place_503_su_storage_giu(client_con_storage_giu: Any) -> None:
    resp = client_con_storage_giu.get("/memory/bottega-w2p-get-giu")

    assert resp.status_code == 503
    body = resp.json()
    assert body == {"detail": _DETTAGLIO_503_ATTESO}

    corpo_minuscolo = resp.text.lower()
    for frammento in _FRAMMENTI_INTERNI_VIETATI:
        assert frammento not in corpo_minuscolo, (
            f"la risposta 503 espone un dettaglio interno vietato "
            f"({frammento!r}): {resp.text}"
        )


# ---------------------------------------------------------------------------
# 2. Il 422 di dominio resta 422, non 503 — anche con l'override attivo
#    NON è coinvolto (l'errore di dominio è sollevato PRIMA di toccare il
#    repository, da urban_memory.service.submit_contribution): lo
#    verifichiamo sia sul client normale sia su quello con storage giù, per
#    dimostrare che la distinzione dominio/infrastruttura tiene in
#    entrambi i casi.
# ---------------------------------------------------------------------------


def test_422_di_dominio_resta_422_con_storage_su(client: Any) -> None:
    payload = _payload(id="mem-w2p-no-consenso", consenso=False)
    resp = client.post("/memory", json=payload)

    assert resp.status_code == 422
    assert "consenso" in resp.json()["detail"].lower()


def test_422_di_dominio_resta_422_anche_con_storage_giu(client_con_storage_giu: Any) -> None:
    """Un contributo senza consenso viene rifiutato da `urban_memory.service`
    PRIMA di raggiungere il repository: deve restare 422 anche quando il
    repository iniettato solleverebbe `MemoryStorageError` per qualunque
    operazione — a dimostrazione che i due tipi di errore non si confondono
    mai, indipendentemente dallo stato dello storage."""
    payload = _payload(id="mem-w2p-no-consenso-giu", consenso=False)
    resp = client_con_storage_giu.post("/memory", json=payload)

    assert resp.status_code == 422
    assert "consenso" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. MemoryStorageError NON è una sottoclasse di UrbanMemoryError
# ---------------------------------------------------------------------------


def test_memory_storage_error_non_e_sottoclasse_di_urban_memory_error() -> None:
    assert not issubclass(MemoryStorageError, UrbanMemoryError), (
        "MemoryStorageError (infrastrutturale, -> 503) non deve essere una "
        "sottoclasse di UrbanMemoryError (dominio, -> 422): altrimenti "
        "urban_memory_error_handler intercetterebbe anche i fallimenti di "
        "storage, mascherandoli da 422 invece di 503."
    )
    assert issubclass(MemoryStorageError, Exception)
