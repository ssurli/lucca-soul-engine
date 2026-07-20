"""Test di integrazione — Wave 4 (Urban Intelligence Index): `GET
/dashboard/index` e `GET /dashboard/flows`.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, stesso
stile di `tests/test_booking.py`/`tests/test_events.py`:
`pytest.importorskip` per non far esplodere la raccolta se `api`/
`intelligence_index` non sono installabili, `monkeypatch.setattr` per
sostituire `api.main.get_candidate_source`/`get_metrics_source`/
`get_event_source`/`get_memory_repository` — TUTTE e quattro chiamate
DIRETTAMENTE nel corpo dei due endpoint (mai tramite `Depends`, vedi la
docstring di modulo in `api.main`), stessa tecnica già usata da
`test_booking.py` per `get_candidate_source` in `create_itinerary`.

ATTENZIONE (stessa trappola documentata in `test_booking.py`): un ambiente
con `.env` che ha `NEO4J_URI`/`DATABASE_URL` configurati farebbe risolvere i
default reali (`api.deps.get_candidate_source`, `api.deps.
get_memory_repository`, `intelligence_index.deps.get_metrics_source`/
`get_event_source`) a `Neo4jCandidateSource`/`PostgresMemoryRepository`/
`Neo4jMetricsSource`/`PostgresBehaviorEventSource` reali — una connessione di
rete vera durante i test. Ogni test che esercita la logica dei due endpoint
FORZA quindi tutte e quattro le fonti con dei doppi in-process, mai
affidamento sui default dell'ambiente. Le eccezioni sono i test di
validazione della query che FastAPI rifiuta PRIMA di eseguire il corpo
dell'endpoint (`ora` fuori range, `periodo` mancante o sintatticamente
malformato — non nella forma `"YYYY-MM"` accettata dal `pattern` del
`Query`): in questi casi nessuna fonte viene mai chiamata, un client "nudo"
è sufficiente e non tocca alcuna infrastruttura reale. Il caso di `periodo`
sintatticamente valido ma con mese fuori range (es. `"2026-13"`) è invece
DENTRO il corpo dell'endpoint — supera il `pattern`, arriva a
`intervallo_periodo`, solleva `ValueError` catturato e rilanciato come 422:
questi test FORZANO comunque le fonti (`get_candidate_source`/
`get_metrics_source`, chiamate prima del `try/except`), anche se poi non
usate.

Copre i quattro criteri richiesti: 200/`disponibile=True` sopra soglia (per
entrambi gli endpoint), 200/`disponibile=False` sotto soglia (per entrambi),
validazione di `ora` fuori range [0,23] (422), `periodo` mancante (422). In
più: `periodo` malformato (422 dal `pattern`), `periodo` sintatticamente
valido ma con mese fuori range (422 dal `try/except` su `ValueError`), e un
fallimento infrastrutturale di lettura degli eventi
(`intelligence_index.IndexStorageError`) risponde 503 senza dettagli
interni — prova diretta del nuovo `index_storage_error_handler` (stesso
stile di `test_storage_eventi_giu_risponde_503_senza_dettagli_interni` in
`test_events.py`)."""

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
contracts = pytest.importorskip(
    "contracts", reason="`contracts` non installabile: pip install -e packages/contracts"
)
intelligence_index = pytest.importorskip(
    "intelligence_index",
    reason="`intelligence_index` non installabile: pip install -e services/intelligence-index",
)
intelligence_index_soglia = pytest.importorskip(
    "intelligence_index.soglia",
    reason="`intelligence_index` non installabile: pip install -e services/intelligence-index",
)

TestClient = fastapi_testclient.TestClient
BehaviorEvent = contracts.BehaviorEvent
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
MemoryContribution = contracts.MemoryContribution
MemoryKind = contracts.MemoryKind
PersonKind = contracts.PersonKind
IndexStorageError = intelligence_index.IndexStorageError
SOGLIA_MINIMA_PERSONE = intelligence_index_soglia.SOGLIA_MINIMA_PERSONE

N_PERSONE_SOPRA_SOGLIA = SOGLIA_MINIMA_PERSONE + 5  # margine oltre k=10

_PLACE_A = "luogo-w4-a"
_PLACE_B = "luogo-w4-b"
_EXP_A = "exp-w4-a"
_EXP_B = "exp-w4-b"


# ---------------------------------------------------------------------------
# Doppi in-process delle quattro fonti — MAI le implementazioni reali (Seed/
# Neo4j/Postgres): stessa interfaccia, dati sintetici e deterministici.
# ---------------------------------------------------------------------------


def _esperienza(id: str, place_id: str) -> ExperienceNode:
    return ExperienceNode(
        id=id,
        titolo=f"esperienza {id}",
        place_id=place_id,
        temi=["prova"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
    )


def _candidato(id: str, place_id: str, place_nome: str) -> GraphCandidate:
    return GraphCandidate(
        experience=_esperienza(id, place_id),
        place_nome=place_nome,
        connessioni=[],
    )


class _FakeCandidateSource:
    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


class _FakeMetricsSource:
    """Doppio di `graph.metrics.GraphMetricsSource` (`Protocol`)."""

    def __init__(
        self,
        grado_semantico: dict[str, int],
        non_connesse: set[frozenset[str]] | None = None,
    ) -> None:
        self._grado_semantico = grado_semantico
        self._non_connesse = non_connesse or set()

    def grado_semantico(self) -> dict[str, int]:
        return self._grado_semantico

    def non_connected_place_pairs(self, at: datetime) -> tuple[set[frozenset[str]], int]:
        return self._non_connesse, len(self._non_connesse)


class _FakeEventSource:
    """Doppio di `intelligence_index.repository.BehaviorEventSource`."""

    def __init__(self, eventi: list[Any]) -> None:
        self._eventi = eventi

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[Any]:
        return [evento for evento in self._eventi if inizio <= evento.ts < fine]


class _EventSourceStorageGiu:
    """Simula uno storage irraggiungibile: solleva `IndexStorageError`
    (infrastrutturale) con un messaggio che porta deliberatamente dettagli
    interni (DSN finto, 'psycopg'), per verificare che il BFF non li faccia
    mai trapelare nella risposta HTTP — stesso pattern di
    `_RepositoryEventiStorageGiu` in `test_events.py`."""

    _MESSAGGIO_INTERNO = (
        "connessione fallita: dsn=postgresql://user:s3cr3t@db-host:5432/lucca "
        "(psycopg.OperationalError, sslmode=require)"
    )

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[Any]:
        raise IndexStorageError(self._MESSAGGIO_INTERNO)


class _FakeMemoryRepository:
    """Doppio di `urban_memory.MemoryRepository` (`Protocol`), solo lettura."""

    def __init__(
        self,
        pending: list[Any] | None = None,
        curated: list[Any] | None = None,
    ) -> None:
        self._pending = pending or []
        self._curated = curated or []

    def list_pending(self) -> list[Any]:
        return self._pending

    def list_curated(self) -> list[Any]:
        return self._curated


def _memoria(id: str, contributor_id: str) -> Any:
    return MemoryContribution(
        id=id,
        kind=MemoryKind.RACCONTO,
        testo="un racconto",
        riguarda=[_PLACE_A],
        contributor_id=contributor_id,
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 10, tzinfo=UTC),
        curato=True,
    )


def _eventi_sopra_soglia() -> list[Any]:
    """`N_PERSONE_SOPRA_SOGLIA` persone, ciascuna con una `view` + uno `stop`
    su `_EXP_A` (place `_PLACE_A`), tutte dentro luglio 2026 — popolazione
    sopra k=10 per ogni indicatore che dipende da questi eventi. STESSO
    scenario di `tests/test_dashboard.py::_eventi_sopra_soglia` in
    `services/intelligence-index`."""
    eventi: list[Any] = []
    for i in range(N_PERSONE_SOPRA_SOGLIA):
        person_id = f"p{i}"
        eventi.append(
            BehaviorEvent(
                person_id=person_id,
                tipo="view",
                experience_id=_EXP_A,
                ts=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
            )
        )
        eventi.append(
            BehaviorEvent(
                person_id=person_id,
                tipo="stop",
                experience_id=_EXP_A,
                ts=datetime(2026, 7, 15, 10, 30, tzinfo=UTC),
            )
        )
    return eventi


def _memorie_sopra_soglia() -> list[Any]:
    return [_memoria(f"m{i}", f"c{i}") for i in range(N_PERSONE_SOPRA_SOGLIA)]


def _eventi_sotto_soglia() -> list[Any]:
    """Solo 3 persone (sotto k=10): fa fallire il gate centrale di
    `calcola_index`, tradotto da `indice_per_dashboard` in
    `disponibile=False`, mai propagato come eccezione."""
    return [
        BehaviorEvent(
            person_id=f"p{i}",
            tipo="stop",
            experience_id=_EXP_A,
            ts=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
        )
        for i in range(3)
    ]


_CANDIDATI = [
    _candidato(_EXP_A, _PLACE_A, "Luogo A"),
    _candidato(_EXP_B, _PLACE_B, "Luogo B"),
]
_GRADO_SEMANTICO = {_PLACE_A: 10, _PLACE_B: 2}


def _forza_fonti(
    monkeypatch: pytest.MonkeyPatch,
    *,
    eventi: list[Any],
    memorie_pending: list[Any] | None = None,
    memorie_curate: list[Any] | None = None,
) -> None:
    monkeypatch.setattr(
        api_main, "get_candidate_source", lambda: _FakeCandidateSource(_CANDIDATI)
    )
    monkeypatch.setattr(
        api_main, "get_metrics_source", lambda: _FakeMetricsSource(_GRADO_SEMANTICO)
    )
    monkeypatch.setattr(api_main, "get_event_source", lambda: _FakeEventSource(eventi))
    monkeypatch.setattr(
        api_main,
        "get_memory_repository",
        lambda: _FakeMemoryRepository(pending=memorie_pending, curated=memorie_curate),
    )


# ---------------------------------------------------------------------------
# GET /dashboard/index
# ---------------------------------------------------------------------------


def test_dashboard_index_disponibile_sopra_soglia(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_fonti(
        monkeypatch,
        eventi=_eventi_sopra_soglia(),
        memorie_curate=_memorie_sopra_soglia(),
    )
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": "2026-07"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["periodo"] == "2026-07"
    assert body["disponibile"] is True
    assert body["index"] is not None
    assert body["index"]["periodo"] == "2026-07"
    assert body["motivo_indisponibilita"] is None


def test_dashboard_index_non_disponibile_sotto_soglia(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_fonti(monkeypatch, eventi=_eventi_sotto_soglia())
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": "2026-07"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["disponibile"] is False
    assert body["index"] is None
    assert body["motivo_indisponibilita"]
    motivo = body["motivo_indisponibilita"].lower()
    assert "privacy" in motivo or "k=10" in motivo


def test_dashboard_index_periodo_mancante_risponde_422() -> None:
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index")

    assert resp.status_code == 422


@pytest.mark.parametrize("periodo_malformato", ["abc", "2026", "2026-7", "2026-07-01"])
def test_dashboard_index_periodo_malformato_risponde_422(periodo_malformato: str) -> None:
    """`periodo` non nella forma `"YYYY-MM"`: rifiutato dal `pattern` del
    `Query` PRIMA di eseguire il corpo dell'endpoint — nessuna fonte viene
    mai chiamata, stesso motivo del test `_periodo_mancante` sopra (vedi
    docstring di modulo)."""
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": periodo_malformato})

    assert resp.status_code == 422


def test_dashboard_index_periodo_mese_fuori_range_risponde_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`"2026-13"` supera il `pattern` (forma sintatticamente valida) ma fa
    sollevare `ValueError` a `intervallo_periodo` (mese 13 fuori [1, 12]):
    catturato nell'endpoint e rilanciato come 422, mai un 500 opaco."""
    _forza_fonti(monkeypatch, eventi=[])
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": "2026-13"})

    assert resp.status_code == 422


def test_dashboard_index_storage_giu_risponde_503_senza_dettagli_interni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_main, "get_candidate_source", lambda: _FakeCandidateSource(_CANDIDATI)
    )
    monkeypatch.setattr(
        api_main, "get_metrics_source", lambda: _FakeMetricsSource(_GRADO_SEMANTICO)
    )
    monkeypatch.setattr(api_main, "get_event_source", lambda: _EventSourceStorageGiu())
    monkeypatch.setattr(
        api_main, "get_memory_repository", lambda: _FakeMemoryRepository()
    )
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": "2026-07"})

    assert resp.status_code == 503
    corpo_minuscolo = resp.text.lower()
    for frammento in ("psycopg", "dsn", "postgresql://", "password", "sslmode"):
        assert frammento not in corpo_minuscolo, (
            f"la risposta 503 espone un dettaglio interno vietato "
            f"({frammento!r}): {resp.text}"
        )


# ---------------------------------------------------------------------------
# GET /dashboard/flows
# ---------------------------------------------------------------------------


def test_dashboard_flows_disponibile_sopra_soglia(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_fonti(monkeypatch, eventi=_eventi_sopra_soglia())
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params={"periodo": "2026-07"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["periodo"] == "2026-07"
    assert {cella["place_id"] for cella in body["celle"]} == set(_GRADO_SEMANTICO)
    cella_a = next(cella for cella in body["celle"] if cella["place_id"] == _PLACE_A)
    assert cella_a["disponibile"] is True
    assert cella_a["conteggio_tappe"] == N_PERSONE_SOPRA_SOGLIA


def test_dashboard_flows_non_disponibile_sotto_soglia(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_fonti(monkeypatch, eventi=_eventi_sotto_soglia())
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params={"periodo": "2026-07"})

    assert resp.status_code == 200
    body = resp.json()
    cella_a = next(cella for cella in body["celle"] if cella["place_id"] == _PLACE_A)
    assert cella_a["disponibile"] is False
    assert cella_a["conteggio_tappe"] is None
    # Un luogo senza nessuna tappa (_PLACE_B) resta indistinguibile da uno
    # sotto soglia con eventi (_PLACE_A, 3 persone) — stesso stato osservabile.
    cella_b = next(cella for cella in body["celle"] if cella["place_id"] == _PLACE_B)
    assert (cella_b["disponibile"], cella_b["conteggio_tappe"]) == (
        cella_a["disponibile"],
        cella_a["conteggio_tappe"],
    )


def test_dashboard_flows_ora_fuori_range_risponde_422(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params={"periodo": "2026-07", "ora": 24})

    assert resp.status_code == 422


def test_dashboard_flows_periodo_mancante_risponde_422() -> None:
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows")

    assert resp.status_code == 422


@pytest.mark.parametrize("periodo_malformato", ["abc", "2026", "2026-7", "2026-07-01"])
def test_dashboard_flows_periodo_malformato_risponde_422(periodo_malformato: str) -> None:
    """Stesso principio di `test_dashboard_index_periodo_malformato_risponde_422`
    sopra: il `pattern` del `Query` rifiuta la richiesta prima del corpo
    dell'endpoint, nessuna fonte viene mai chiamata."""
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params={"periodo": periodo_malformato})

    assert resp.status_code == 422


def test_dashboard_flows_periodo_mese_fuori_range_risponde_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stesso principio di `test_dashboard_index_periodo_mese_fuori_range_risponde_422`
    sopra: `"2026-13"` supera il `pattern` ma fa sollevare `ValueError` a
    `intervallo_periodo`, catturato e rilanciato come 422."""
    _forza_fonti(monkeypatch, eventi=[])
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params={"periodo": "2026-13"})

    assert resp.status_code == 422


def test_dashboard_flows_filtro_giorno_ora_applicato(monkeypatch: pytest.MonkeyPatch) -> None:
    _forza_fonti(monkeypatch, eventi=_eventi_sopra_soglia())
    client = TestClient(api_main.app)

    resp = client.get(
        "/dashboard/flows",
        params={"periodo": "2026-07", "giorno": "2026-07-15", "ora": 10},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["giorno"] == "2026-07-15"
    assert body["ora"] == 10
    cella_a = next(cella for cella in body["celle"] if cella["place_id"] == _PLACE_A)
    assert cella_a["disponibile"] is True
    assert cella_a["conteggio_tappe"] == N_PERSONE_SOPRA_SOGLIA

    resp_altra_ora = client.get(
        "/dashboard/flows",
        params={"periodo": "2026-07", "giorno": "2026-07-15", "ora": 9},
    )
    body_altra_ora = resp_altra_ora.json()
    cella_a_9 = next(
        cella for cella in body_altra_ora["celle"] if cella["place_id"] == _PLACE_A
    )
    assert cella_a_9["disponibile"] is False
    assert cella_a_9["conteggio_tappe"] is None
