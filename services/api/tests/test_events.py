"""Test di integrazione — Wave 3b (Recommender ML): `POST /events` e il
wiring del reranking in `POST /itinerary`.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, stesso
stile di `tests/test_booking.py`: `pytest.importorskip` per non far esplodere
la raccolta se `api`/`recommender` non sono installabili,
`app.dependency_overrides` per sostituire il repository iniettato via
`Depends` senza toccare `api.deps`/`.env`.

Copre tre criteri:

1. `POST /events` risponde 202 (non 201: nessuna risorsa interrogabile, solo
   un segnale comportamentale accodato — `docs/DATA_CONTRACTS.md` §8).
2. Storage giù su `/events` -> 503, mai un dettaglio interno nel corpo
   (stesso stile di `test_storage_giu_risponde_503_senza_dettagli_interni`
   in `test_booking.py`).
3. `POST /itinerary` con uno storico eventi che solleva
   `RecommenderStorageError` risponde COMUNQUE 200 con un itinerario valido:
   prova diretta del vincolo "il recommender non deve mai far fallire
   /itinerary" (vedi il commento in `api.main.create_itinerary`).

   `api.main.create_itinerary` chiama `get_event_repository()`
   DIRETTAMENTE (non tramite `Depends` nella firma dell'endpoint — vedi la
   NOTA nella docstring di quella funzione per il motivo): un
   `app.dependency_overrides` non avrebbe alcun effetto su quella chiamata,
   perché quel dizionario è consultato solo dal risolutore di dipendenze di
   FastAPI, mai da una chiamata diretta a una funzione Python. Questo test
   sostituisce quindi `api.main.get_event_repository` con
   `monkeypatch.setattr`, la stessa tecnica già usata da `test_booking.py`
   per `get_candidate_source` (chiamata anch'essa direttamente, non via
   `Depends`, nello stesso endpoint)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)
api_deps = pytest.importorskip(
    "api.deps", reason="`api` non installabile: pip install -e services/api"
)
contracts = pytest.importorskip(
    "contracts", reason="`contracts` non installabile: pip install -e packages/contracts"
)
recommender = pytest.importorskip(
    "recommender", reason="`recommender` non installabile: pip install -e services/recommender"
)

TestClient = fastapi_testclient.TestClient
EmotionalProfile = contracts.EmotionalProfile
Signal = contracts.Signal
VisitorContext = contracts.VisitorContext


def _payload_evento(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "turista-w3b-pseudonimo",
        "tipo": "stop",
        "experience_id": "exp-passeggiata-mura",
        "ts": datetime(2026, 7, 17, 10, 0, tzinfo=UTC).isoformat(),
    }
    base.update(overrides)
    return base


def _visitor_context() -> dict[str, Any]:
    return {
        "person_id": "turista-w3b-itinerario",
        "profile": {
            "curiosita": 0.7,
            "contemplazione": 0.5,
            "arte": 0.6,
            "con_bambini": False,
            "tempo_disponibile_min": 120,
        },
        "signal": {
            "meteo": "sereno",
            "affollamento": {},
            "stanchezza": 0.0,
            "ora": "10:00:00",
        },
    }


# ---------------------------------------------------------------------------
# 1. POST /events risponde 202
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_con_repo_eventi_in_memoria(monkeypatch: pytest.MonkeyPatch) -> Any:
    """`TestClient` con `api.deps.get_event_repository` sovrascritto su
    `InMemoryBehaviorEventRepository` via `app.dependency_overrides` — il
    repository ARRIVA via `Depends` in `submit_behavior_event` — così il
    test è deterministico e offline, indipendente da un eventuale
    `DATABASE_URL` configurato in questo ambiente."""
    api_main.app.dependency_overrides[api_deps.get_event_repository] = (
        recommender.InMemoryBehaviorEventRepository
    )
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def test_evento_registrato_risponde_202(client_con_repo_eventi_in_memoria: Any) -> None:
    resp = client_con_repo_eventi_in_memoria.post("/events", json=_payload_evento())

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# 2. Storage non disponibile su /events -> 503, mai un dettaglio interno
# ---------------------------------------------------------------------------


class _RepositoryEventiStorageGiu:
    """Simula uno storage irraggiungibile: solleva `RecommenderStorageError`
    (infrastrutturale) su OGNI operazione, con un messaggio che porta
    deliberatamente dettagli interni (DSN finto, 'psycopg') per verificare
    che il BFF non li faccia mai trapelare nella risposta HTTP — stesso
    pattern di `_RepositoryStorageGiu` in `test_booking.py`."""

    _MESSAGGIO_INTERNO = (
        "connessione fallita: dsn=postgresql://user:s3cr3t@db-host:5432/lucca "
        "(psycopg.OperationalError, sslmode=require)"
    )

    def record(self, event: Any) -> None:
        raise recommender.RecommenderStorageError(self._MESSAGGIO_INTERNO)

    def conteggio_per_esperienza(self) -> dict[str, float]:
        raise recommender.RecommenderStorageError(self._MESSAGGIO_INTERNO)


@pytest.fixture()
def client_con_storage_eventi_giu(monkeypatch: pytest.MonkeyPatch) -> Any:
    api_main.app.dependency_overrides[api_deps.get_event_repository] = (
        _RepositoryEventiStorageGiu
    )
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def test_storage_eventi_giu_risponde_503_senza_dettagli_interni(
    client_con_storage_eventi_giu: Any,
) -> None:
    resp = client_con_storage_eventi_giu.post("/events", json=_payload_evento())

    assert resp.status_code == 503
    corpo_minuscolo = resp.text.lower()
    for frammento in ("psycopg", "dsn", "postgresql://", "password", "sslmode"):
        assert frammento not in corpo_minuscolo, (
            f"la risposta 503 espone un dettaglio interno vietato "
            f"({frammento!r}): {resp.text}"
        )


# ---------------------------------------------------------------------------
# 3. POST /itinerary con lo storico eventi giù risponde COMUNQUE 200: il
#    recommender è un arricchimento opzionale, mai un motivo di fallimento.
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_con_itinerario_e_storico_giu(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Sostituisce `api.main.get_event_repository` (chiamata DIRETTAMENTE da
    `create_itinerary`, non tramite `Depends`: vedi la docstring di modulo)
    con una funzione che ritorna un repository la cui
    `conteggio_per_esperienza()` solleva SEMPRE `RecommenderStorageError` —
    esattamente il punto in cui `recommender.costruisci_score_fn` legge lo
    storico. Non tocca `api.deps.get_candidate_source`: l'itinerario passa
    per la `CandidateSource` reale configurata in questo ambiente (seed o
    Neo4j), esattamente come farebbe una richiesta reale."""
    fake_repo = _RepositoryEventiStorageGiu()
    monkeypatch.setattr(api_main, "get_event_repository", lambda: fake_repo)
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def test_itinerario_risponde_200_anche_con_storico_eventi_giu(
    client_con_itinerario_e_storico_giu: Any,
) -> None:
    resp = client_con_itinerario_e_storico_giu.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    body = resp.json()
    assert body["person_id"] == "turista-w3b-itinerario"
    assert isinstance(body["stops"], list)


def test_itinerario_risponde_200_con_repo_in_memoria_normale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controprova: con un repository di eventi normale (vuoto, cold start),
    `/itinerary` risponde 200 esattamente come prima — il wiring del
    reranking non introduce un percorso di errore per il caso comune."""
    repo_vuoto = recommender.InMemoryBehaviorEventRepository()
    monkeypatch.setattr(api_main, "get_event_repository", lambda: repo_vuoto)
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["stops"], list)
