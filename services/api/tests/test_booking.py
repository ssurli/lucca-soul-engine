"""Test di integrazione — Wave 3a (Marketplace): `POST /booking`.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, stesso
stile dei test esistenti per `/memory` (`tests/test_integration_wave2.py`,
`tests/test_integration_wave2_persistence.py`, root del repo):
`pytest.importorskip` per non far esplodere la raccolta se `api` non è
installabile, `app.dependency_overrides` per sostituire il repository dello
storage senza toccare `api.deps`/`.env`.

Il dataset canonico del seed (`graph.seed_lucca.ESPERIENZE`) conteneva, in
origine, nessuna esperienza con `prenotabile=True`: sufficiente per il
criterio "esperienza non prenotabile -> 422" SENZA alcun doppiaggio, ma non
per il criterio "prenotazione riuscita" né per quello "storage giù" (che
deve superare il controllo di dominio per arrivare al repository). Per
questi due casi il modulo sostituisce `api.main.get_candidate_source`
(chiamata direttamente dall'endpoint, non iniettata via `Depends`: non
esiste un `app.dependency_overrides` per una funzione richiamata così, quindi
si usa `monkeypatch.setattr`, la stessa tecnica che pytest offre per questo
esatto scopo) con una `CandidateSource` finta (`_FakeCandidateSource`) che
propone UNA sola esperienza prenotabile, con un prezzo noto — non introduce
alcuna logica diversa da quella reale, sostituisce solo la fonte dei
candidati.

`graph-architect` ha da allora aggiunto al seed canonico un'esperienza REALE
prenotabile (`exp-laboratorio-liuteria`, `prezzo_eur=15.0`, partner
`liuteria-lucchese` — l'UNICA del seed con `prenotabile=True`, vedi
`graph.seed_lucca.ESPERIENZE` e `services/graph/tests`). Questo colma un gap
che `ethics-guardian` aveva segnalato: il criterio "esperienze prenotabili
end-to-end" (`docs/BUILD_PLAN.md`) va dimostrato anche attraverso il vero
`SeedCandidateSource` (`graph.source`), non solo attraverso la
`_FakeCandidateSource` fatta a mano — un doppio che isola bene la logica del
BFF ma non prova che il seed reale, così come `graph-architect` lo scrive,
produca davvero un candidato prenotabile con il prezzo giusto. I test più in
basso (`client_con_seed_reale`, `test_booking_riuscito_contro_seed_reale_*`)
coprono questo secondo percorso, in aggiunta ai test con la fake — nessuno
dei due sostituisce l'altro: la fake resta utile per isolare la logica del
BFF da un dataset specifico, il seed reale prova che i due sono coerenti.

ATTENZIONE (fonte di un bug osservato, non "aggiustato" qui, vedi nota in
fondo al modulo): quando questo servizio gira con un `.env` che ha
`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` configurati,
`api.deps.get_candidate_source()` (il DEFAULT, `lru_cache`, mai monkeypatchato)
risolve a `Neo4jCandidateSource`, mai a `SeedCandidateSource` — anche per un
test che vuole verificare il seed canonico. Ogni test che intende colpire
`SeedCandidateSource` deve quindi FORZARLA esplicitamente via
`monkeypatch.setattr(api_main, "get_candidate_source", lambda: SeedCandidateSource())`,
mai fare affidamento sul default dell'ambiente.

Se un test qui fallisce, il bug è nel servizio a valle (`api` o
`marketplace`), non nel test: non "aggiustare" l'asserzione per farla
passare.

BUG OSSERVATO E CORRETTO (non in questo file: in `services/graph`): in un
ambiente con `.env` che punta a un'istanza Aura reale non ancora ri-seedata
con lo schema Wave 3a (proprietà `prenotabile` assente sui nodi), i due test
che usano la fixture `client` "nuda" — `test_esperienza_inesistente_risponde_404`
e `test_esperienza_non_prenotabile_risponde_422` — non forzano
`SeedCandidateSource` e passano quindi per il vero
`api.deps.get_candidate_source()`, che in quell'ambiente risolve a
`Neo4jCandidateSource` reale: `Neo4jCandidateSource._to_candidate` riceveva
`prenotabile=None` dalla riga Cypher (proprietà mancante su un grafo non
ancora aggiornato) e falliva con `pydantic.ValidationError` (il campo non è
`bool | None` nel contratto) invece di produrre il 422 atteso. Non era un bug
di questo modulo (che forza sempre `SeedCandidateSource` per i test contro il
seed, vedi sopra), né dei due test preesistenti: la causa era
`services/graph/cypher/10_candidates.cypher`, che leggeva `e.prenotabile`
senza alcun default. Corretto con `coalesce(e.prenotabile, false) AS
prenotabile` (stesso pattern già usato per `partner_abbonamento_attivo`):
un'Esperienza su un grafo non ancora rieseguito degrada a "non prenotabile",
mai a un errore non gestito. Tutti i test di questo modulo, inclusi questi
due, passano ora anche contro l'Aura reale di questo ambiente.
"""

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
marketplace = pytest.importorskip(
    "marketplace", reason="`marketplace` non installabile: pip install -e services/marketplace"
)
graph_source = pytest.importorskip(
    "graph.source", reason="`graph` non installabile: pip install -e services/graph"
)

TestClient = fastapi_testclient.TestClient
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
SeedCandidateSource = graph_source.SeedCandidateSource

_ESPERIENZA_PRENOTABILE_ID = "exp-w3a-booking-prenotabile"
_ESPERIENZA_PRENOTABILE_PREZZO = 15.0

# Esperienza REALE del seed canonico, mai resa prenotabile (vedi docstring di
# modulo): usata per il criterio "non prenotabile -> 422" senza alcun doppio.
_ESPERIENZA_SEED_NON_PRENOTABILE_ID = "exp-passeggiata-mura"

# Esperienza REALE del seed canonico resa prenotabile da `graph-architect`
# (vedi docstring di modulo): l'UNICA di `graph.seed_lucca.ESPERIENZE` con
# `prenotabile=True`. Usata per il nuovo criterio "prenotazione riuscita
# end-to-end attraverso il vero SeedCandidateSource".
_ESPERIENZA_SEED_PRENOTABILE_ID = "exp-laboratorio-liuteria"
_ESPERIENZA_SEED_PRENOTABILE_PREZZO = 15.0


class _FakeCandidateSource:
    """`CandidateSource` finta: propone UNA sola esperienza prenotabile, con
    un prezzo noto. Nessuna logica diversa dalle implementazioni reali
    (`SeedCandidateSource`/`Neo4jCandidateSource`): stessa interfaccia
    (`candidates(ctx) -> list[GraphCandidate]`), sempre gli stessi candidati
    a prescindere dal `VisitorContext` ricevuto — proprio come le due
    implementazioni reali (il filtro è responsabilità dell'Experience
    Engine, non della `CandidateSource`, vedi `services/graph/graph/source.py`).
    """

    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


def _candidato_prenotabile(
    experience_id: str = _ESPERIENZA_PRENOTABILE_ID,
    prezzo_eur: float = _ESPERIENZA_PRENOTABILE_PREZZO,
) -> Any:
    esperienza = ExperienceNode(
        id=experience_id,
        titolo="Esperienza di prova prenotabile",
        place_id="luogo-w3a-test",
        temi=["prova"],
        durata_min=30,
        al_chiuso=True,
        accessibile=True,
        prezzo_eur=prezzo_eur,
        prenotabile=True,
    )
    return GraphCandidate(
        experience=esperienza,
        place_nome="Luogo di prova",
        connessioni=[],
    )


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


@pytest.fixture()
def client_con_esperienza_prenotabile(monkeypatch: pytest.MonkeyPatch) -> Any:
    """`TestClient` con `api.main.get_candidate_source` sostituita da una
    fonte finta che propone UNA sola esperienza prenotabile — necessaria
    perché il seed canonico non ne contiene nessuna (vedi docstring di
    modulo) — e con `api.deps.get_booking_repository` sovrascritto su
    `InMemoryBookingRepository` via `app.dependency_overrides`: questo test
    verifica la LOGICA del BFF (candidato -> Booking), non la
    raggiungibilità di un Postgres/Neon reale (che questo ambiente può avere
    configurato in `.env` senza lo schema del Marketplace ancora applicato —
    vedi `marketplace.migrate`); l'override rende il test deterministico e
    offline, stesso principio della guardia `InMemoryMemoryRepository` nei
    test di Urban Memory (`tests/test_integration_wave2.py`, radice del
    repo)."""
    fake_source = _FakeCandidateSource([_candidato_prenotabile()])
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fake_source)
    api_main.app.dependency_overrides[api_deps.get_booking_repository] = (
        marketplace.InMemoryBookingRepository
    )
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


@pytest.fixture()
def client_con_seed_reale(monkeypatch: pytest.MonkeyPatch) -> Any:
    """`TestClient` contro il vero `SeedCandidateSource` (`graph.source`,
    dataset canonico `graph.seed_lucca`) — non la `_FakeCandidateSource`
    fatta a mano. Forza SEMPRE la fonte via `monkeypatch.setattr`, mai
    affidamento sul default di `api.deps.get_candidate_source()`: in un
    ambiente con `.env` che ha `NEO4J_URI` configurato, quel default
    risolverebbe a `Neo4jCandidateSource` reale (vedi ATTENZIONE nella
    docstring di modulo), tentando una connessione di rete vera durante i
    test — esattamente ciò che questa fixture evita.

    Sovrascrive anche `api.deps.get_booking_repository` su
    `marketplace.InMemoryBookingRepository` via `app.dependency_overrides`,
    stesso motivo di `client_con_esperienza_prenotabile`: isolare dalla
    raggiungibilità di un Postgres/Neon reale non ancora migrato in questo
    ambiente, non dalla `CandidateSource` (quella qui è VERA, di proposito).
    """
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: SeedCandidateSource())
    api_main.app.dependency_overrides[api_deps.get_booking_repository] = (
        marketplace.InMemoryBookingRepository
    )
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


class _RepositoryStorageGiu:
    """Simula uno storage irraggiungibile: solleva `MarketplaceStorageError`
    (infrastrutturale, mai un `MarketplaceError` di dominio) su OGNI
    operazione, con un messaggio che porta deliberatamente dettagli interni
    (DSN finto, 'psycopg') per verificare che il BFF non li faccia mai
    trapelare nella risposta HTTP."""

    _MESSAGGIO_INTERNO = (
        "connessione fallita: dsn=postgresql://user:s3cr3t@db-host:5432/lucca "
        "(psycopg.OperationalError, sslmode=require)"
    )

    def create(self, booking: Any) -> Any:
        raise marketplace.MarketplaceStorageError(self._MESSAGGIO_INTERNO)

    def get(self, booking_id: str) -> Any:
        raise marketplace.MarketplaceStorageError(self._MESSAGGIO_INTERNO)

    def update_status(self, booking_id: str, stato: Any) -> Any:
        raise marketplace.MarketplaceStorageError(self._MESSAGGIO_INTERNO)

    def record_commission(self, commission: Any) -> Any:
        raise marketplace.MarketplaceStorageError(self._MESSAGGIO_INTERNO)

    def get_commission(self, booking_id: str) -> Any:
        raise marketplace.MarketplaceStorageError(self._MESSAGGIO_INTERNO)


@pytest.fixture()
def client_con_storage_giu(monkeypatch: pytest.MonkeyPatch) -> Any:
    """`TestClient` con `api.deps.get_booking_repository` sovrascritto (via
    `app.dependency_overrides`, il repository ARRIVA via `Depends`) da un
    repository che solleva SEMPRE `MarketplaceStorageError`, E con
    `api.main.get_candidate_source` sostituita da una fonte con
    un'esperienza prenotabile (altrimenti il 422 di dominio precederebbe
    sempre il tentativo di scrittura, e lo storage giù non sarebbe mai
    raggiunto — vedi `marketplace.service.request_booking`)."""
    fake_source = _FakeCandidateSource([_candidato_prenotabile()])
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fake_source)
    api_main.app.dependency_overrides[api_deps.get_booking_repository] = (
        _RepositoryStorageGiu
    )
    try:
        yield TestClient(api_main.app)
    finally:
        api_main.app.dependency_overrides.clear()


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "turista-w3a-pseudonimo",
        "experience_id": _ESPERIENZA_PRENOTABILE_ID,
        "quando": datetime(2026, 8, 1, 10, 0, tzinfo=UTC).isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Booking riuscito: 201, stato=RICHIESTA, prezzo dal candidato (non dal
#    body — BookingRequest non lo contiene).
# ---------------------------------------------------------------------------


def test_booking_riuscito_stato_richiesta(client_con_esperienza_prenotabile: Any) -> None:
    resp = client_con_esperienza_prenotabile.post("/booking", json=_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["stato"] == "richiesta"
    assert body["person_id"] == "turista-w3a-pseudonimo"
    assert body["experience_id"] == _ESPERIENZA_PRENOTABILE_ID
    assert body["prezzo_eur"] == _ESPERIENZA_PRENOTABILE_PREZZO
    assert body["id"]  # generato dal service layer

    # Nessun campo di Partner/CommissionRecord in questa risposta.
    campi_vietati = {"partner_id", "abbonamento_attivo", "importo_eur", "percentuale"}
    assert not (campi_vietati & set(body)), (
        f"la risposta di POST /booking espone campi non previsti: "
        f"{campi_vietati & set(body)}"
    )


# ---------------------------------------------------------------------------
# 2. Esperienza inesistente tra i candidati -> 404 (non un MarketplaceError)
# ---------------------------------------------------------------------------


def test_esperienza_inesistente_risponde_404(client: Any) -> None:
    payload = _payload(experience_id="exp-non-esiste-w3a")
    resp = client.post("/booking", json=payload)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Esperienza prenotabile=False -> 422, con un'esperienza REALE del seed
#    (mai resa prenotabile di proposito, vedi docstring di modulo): nessun
#    doppiaggio necessario per questo criterio.
# ---------------------------------------------------------------------------


def test_esperienza_non_prenotabile_risponde_422(client: Any) -> None:
    payload = _payload(experience_id=_ESPERIENZA_SEED_NON_PRENOTABILE_ID)
    resp = client.post("/booking", json=payload)

    assert resp.status_code == 422
    dettaglio = resp.json()["detail"].lower()
    assert "prenotazione rifiutata" in dettaglio
    assert "prenotabile" in dettaglio


# ---------------------------------------------------------------------------
# 4. Storage non disponibile -> 503, mai un dettaglio interno nel corpo
# ---------------------------------------------------------------------------


def test_storage_giu_risponde_503_senza_dettagli_interni(
    client_con_storage_giu: Any,
) -> None:
    resp = client_con_storage_giu.post("/booking", json=_payload())

    assert resp.status_code == 503
    corpo_minuscolo = resp.text.lower()
    for frammento in ("psycopg", "dsn", "postgresql://", "password", "sslmode"):
        assert frammento not in corpo_minuscolo, (
            f"la risposta 503 espone un dettaglio interno vietato "
            f"({frammento!r}): {resp.text}"
        )


# ---------------------------------------------------------------------------
# 5. Booking riuscito attraverso il vero SeedCandidateSource (non la fake):
#    dimostra il criterio "esperienze prenotabili end-to-end" sul dataset
#    canonico reale (`graph.seed_lucca`), non su un doppio con un prezzo
#    finto — vedi docstring di modulo per il motivo di questo test in più.
# ---------------------------------------------------------------------------


def test_booking_riuscito_contro_seed_reale_stato_richiesta(
    client_con_seed_reale: Any,
) -> None:
    payload = _payload(experience_id=_ESPERIENZA_SEED_PRENOTABILE_ID)
    resp = client_con_seed_reale.post("/booking", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["stato"] == "richiesta"
    assert body["experience_id"] == _ESPERIENZA_SEED_PRENOTABILE_ID
    assert body["prezzo_eur"] == _ESPERIENZA_SEED_PRENOTABILE_PREZZO


# ---------------------------------------------------------------------------
# 6. Assert negativo sullo stesso percorso reale: nessun'altra esperienza del
#    seed (qui la stessa già usata dal test 3, `exp-passeggiata-mura`) deve
#    poter essere prenotata attraverso il vero SeedCandidateSource —
#    `exp-laboratorio-liuteria` resta l'UNICA eccezione del seed.
# ---------------------------------------------------------------------------


def test_altra_esperienza_seed_non_prenotabile_contro_seed_reale_risponde_422(
    client_con_seed_reale: Any,
) -> None:
    payload = _payload(experience_id=_ESPERIENZA_SEED_NON_PRENOTABILE_ID)
    resp = client_con_seed_reale.post("/booking", json=payload)

    assert resp.status_code == 422
    dettaglio = resp.json()["detail"].lower()
    assert "prenotazione rifiutata" in dettaglio
    assert "prenotabile" in dettaglio
