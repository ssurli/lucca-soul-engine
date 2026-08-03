"""Test di integrazione — Fase 3 (canale fluttuante persistente,
`docs/PROMOZIONE_TRACCIA.md`): il lato-lettura di `POST /itinerary`.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, stesso
stile di `test_events.py`: `pytest.importorskip` per non far esplodere la
raccolta se `api`/`urban_memory` non sono installabili,
`monkeypatch.setattr(api_main, ...)` per sostituire
`get_segnale_repository`/`get_traccia_repository`/`get_place_link_writer` —
chiamate DIRETTAMENTE da `create_itinerary` (mai tramite `Depends`, per lo
stesso motivo di `get_event_repository`: un fallimento deve restare
catturabile dal `try/except` interno, mai finire in un gestore globale che
per queste eccezioni non esiste nemmeno).

Copre i criteri del task:

1. Un segnale ATTIVO (`valido_fino > now`) compare tra `eventi_attivi` ed
   entra nell'itinerario composto (tappa `fluttuante-<id>`).
2. Un segnale SCADUTO non compare e deposita una traccia (via lo
   store reale invocato dall'endpoint).
3. Store irraggiungibile -> `/itinerary` risponde COMUNQUE 200, mai un 503.
4. Il server IGNORA `eventi_attivi` mandato dal client nel body (proprietà
   di sicurezza)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
urban_memory = pytest.importorskip(
    "urban_memory", reason="`urban_memory` non installabile: pip install -e services/urban-memory"
)
graph_source = pytest.importorskip(
    "graph.source", reason="`graph` non installabile: pip install -e services/graph"
)

TestClient = fastapi_testclient.TestClient
SegnaleFluttuante = contracts.SegnaleFluttuante
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
InMemorySegnaleFluttuanteRepository = urban_memory.InMemorySegnaleFluttuanteRepository
InMemoryTracciaRepository = urban_memory.InMemoryTracciaRepository
SegnaleStorageError = urban_memory.SegnaleStorageError
SeedCandidateSource = graph_source.SeedCandidateSource

ORA = datetime.now(UTC)

# "piazza-anfiteatro" è un place_id reale del seed (`services/graph/cypher/
# 01_seed_lucca.cypher`): usato anche da `urban_memory.verify`/`tests` di
# altri servizi come place_id di riferimento del seed canonico.
PLACE_ID_SEED = "piazza-anfiteatro"


class _FakeCandidateSource:
    """`CandidateSource` finta, stesso pattern di `_FakeCandidateSource` in
    `test_booking.py`: propone SEMPRE gli stessi candidati, a prescindere
    dal `VisitorContext` — usata per controllare con precisione il budget di
    tempo residuo (il seed reale, con molti candidati coerenti su un profilo
    `arte` alto, riempie da solo un budget anche ampio, lasciando poco spazio
    prevedibile per la tappa fluttuante)."""

    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


def _candidato_arte(durata_min: int = 30) -> Any:
    esperienza = ExperienceNode(
        id="exp-fluttuante-test-fisso",
        titolo="Facciata Barocca",
        place_id=PLACE_ID_SEED,
        temi=["arte"],
        durata_min=durata_min,
        al_chiuso=False,
        accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza,
        place_nome="Piazza Fissa di Test",
        connessioni=['Evoca il tema "Arte".'],
    )


def _segnale(**overrides: Any):
    defaults: dict[str, Any] = {
        "id": "violinista-test-fluttuante",
        "descrizione": "Un violinista suona in piazza",
        "temi": ["musica"],  # in TEMI_ARTE: coerente con un profilo arte>0
        "place_id": PLACE_ID_SEED,
        "non_commerciale": True,
        "valido_fino": ORA + timedelta(hours=1),
    }
    defaults.update(overrides)
    return SegnaleFluttuante(**defaults)


def _visitor_context(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "turista-fase3-canale-fluttuante",
        "profile": {
            "curiosita": 0.3,
            "contemplazione": 0.2,
            "arte": 0.9,
            "con_bambini": False,
            "tempo_disponibile_min": 200,
        },
        "signal": {
            "meteo": "sereno",
            "affollamento": {},
            "stanchezza": 0.0,
            "ora": "10:00:00",
            "eventi_attivi": [],
        },
    }
    base.update(overrides)
    return base


def _stub_repos(
    monkeypatch: pytest.MonkeyPatch, *, segnale_repo, traccia_repo, candidate_source=None
) -> None:
    """Sostituisce `get_segnale_repository`/`get_traccia_repository`/
    `get_place_link_writer` (canale fluttuante) E, SEMPRE, `get_candidate_
    source` (default: `SeedCandidateSource()` reale, mai il default non
    forzato di `api.deps`). Quest'ultimo è deliberato e NON opzionale —
    stessa disciplina già stabilita da `test_booking.py.
    client_con_seed_reale`: in un ambiente con `.env` che ha `NEO4J_URI`
    configurato (questo sandbox lo ha: credenziali Aura reali, irraggiungibili
    da qui), il default di `api.deps.get_candidate_source()` risolverebbe a
    `Neo4jCandidateSource` reale, tentando una connessione di rete vera
    durante il test — esattamente ciò che questa funzione evita, in OGNI
    test di questo file, non solo in quello che lo richiede esplicitamente
    per il controllo del budget."""
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnale_repo)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: traccia_repo)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    source = candidate_source if candidate_source is not None else SeedCandidateSource()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: source)


# ---------------------------------------------------------------------------
# 1. Segnale attivo -> eventi_attivi -> tappa nell'itinerario
# ---------------------------------------------------------------------------


def test_segnale_attivo_entra_nellitinerario(monkeypatch: pytest.MonkeyPatch) -> None:
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    segnale_repo.persist(_segnale())
    # Candidate source finta con UN SOLO candidato piccolo (30 min): budget
    # residuo prevedibile per la tappa fluttuante (25 min) — il seed reale,
    # con un profilo `arte` alto, riempirebbe da solo un budget anche ampio.
    _stub_repos(
        monkeypatch,
        segnale_repo=segnale_repo,
        traccia_repo=InMemoryTracciaRepository(),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    stops = resp.json()["stops"]
    ids = [s["experience_id"] for s in stops]
    assert "fluttuante-violinista-test-fluttuante" in ids, (
        f"la tappa fluttuante non è entrata nell'itinerario: {ids}"
    )


# ---------------------------------------------------------------------------
# 2. Segnale scaduto -> non compare, deposita traccia
# ---------------------------------------------------------------------------


def test_segnale_scaduto_non_compare_e_deposita_traccia(monkeypatch: pytest.MonkeyPatch) -> None:
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    # Costruito ATTIVO con un margine ampio (5 minuti: robusto a un ritardo
    # di collection/import di pytest, che altrimenti farebbe scattare QUI
    # `SegnaleFluttuante._expired_se_gia_scaduto` — normalizzando stato=
    # EXPIRED già alla costruzione, vanificando il test), poi "invecchiato"
    # con `model_copy` (nessuna rivalidazione: stato resta ATTIVO in colonna,
    # solo valido_fino torna nel passato reale) — simula un segnale la cui
    # finestra si è chiusa nel tempo trascorso tra il conferimento e questa
    # richiesta, senza dover davvero attendere.
    tra_5_minuti = datetime.now(UTC) + timedelta(minutes=5)
    segnale = _segnale(id="scaduto-per-davvero", valido_fino=tra_5_minuti)
    segnale_invecchiato = segnale.model_copy(
        update={"valido_fino": datetime.now(UTC) - timedelta(seconds=1)}
    )
    assert segnale_invecchiato.stato.value == "attivo"  # precondizione: la guardia è nel repo
    segnale_repo.persist(segnale_invecchiato)
    traccia_repo = InMemoryTracciaRepository()
    _stub_repos(monkeypatch, segnale_repo=segnale_repo, traccia_repo=traccia_repo)
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "fluttuante-scaduto-per-davvero" not in ids

    tracce = traccia_repo.list_for_place(PLACE_ID_SEED)
    assert len(tracce) == 1
    assert tracce[0].segnale_id == "scaduto-per-davvero"


# ---------------------------------------------------------------------------
# 3. Store irraggiungibile -> COMUNQUE 200, mai un 503
# ---------------------------------------------------------------------------


class _SegnaleRepositoryStorageGiu:
    """Simula uno store irraggiungibile: solleva `SegnaleStorageError` su
    OGNI operazione — stesso pattern di `_RepositoryEventiStorageGiu` in
    `test_events.py`."""

    def sweep_scaduti(self, now: datetime) -> list[Any]:
        raise SegnaleStorageError("connessione a Postgres fallita (simulato)")

    def fetch_attivi(self, now: datetime) -> list[Any]:
        raise SegnaleStorageError("connessione a Postgres fallita (simulato)")

    def persist(self, segnale: Any) -> Any:
        raise SegnaleStorageError("connessione a Postgres fallita (simulato)")


def test_store_irraggiungibile_risponde_200_senza_tappe_fluttuanti(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_repos(
        monkeypatch,
        segnale_repo=_SegnaleRepositoryStorageGiu(),
        traccia_repo=InMemoryTracciaRepository(),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200, (
        "un fallimento dello store del canale fluttuante NON deve mai far "
        f"fallire /itinerary (mai un 503): {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert isinstance(body["stops"], list)
    assert all(not s["experience_id"].startswith("fluttuante-") for s in body["stops"])


# ---------------------------------------------------------------------------
# 4. Il server IGNORA eventi_attivi mandato dal client (sicurezza)
# ---------------------------------------------------------------------------


def test_server_ignora_eventi_attivi_mandato_dal_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # Store REALMENTE vuoto (nessun segnale persistito): se il server
    # rispettasse il valore del client, la tappa fluttuante falsa
    # comparirebbe comunque nell'itinerario. Deve NON comparire.
    _stub_repos(
        monkeypatch,
        segnale_repo=InMemorySegnaleFluttuanteRepository(),
        traccia_repo=InMemoryTracciaRepository(),
    )
    client = TestClient(api_main.app)

    segnale_falso = {
        "id": "segnale-iniettato-dal-client",
        "descrizione": "Un segnale che il client ha inventato",
        "temi": ["musica"],
        "place_id": PLACE_ID_SEED,
        "non_commerciale": True,
        "valido_fino": (ORA + timedelta(hours=1)).isoformat(),
    }
    ctx = _visitor_context(
        signal={
            "meteo": "sereno",
            "affollamento": {},
            "stanchezza": 0.0,
            "ora": "10:00:00",
            "eventi_attivi": [segnale_falso],
        }
    )

    resp = client.post("/itinerary", json=ctx)

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "fluttuante-segnale-iniettato-dal-client" not in ids, (
        "un segnale fluttuante mandato dal client nel body NON deve mai "
        f"entrare nella composizione: {ids}"
    )
