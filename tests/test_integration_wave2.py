"""Test di integrazione — Wave 2: CRITERI DI ACCETTAZIONE (Urban Memory).

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, end-to-end,
senza alcun database attivo (`DATABASE_URL` non impostata =>
`InMemoryMemoryRepository`, vedi `api.deps.get_memory_repository`). Ogni
funzione qui sotto è UN criterio d'accettazione della wave, leggibile da
solo:

1. Nessun contributo persiste senza consenso: `POST /memory` con
   `consenso=false` -> 422, e a livello `urban_memory.service` (con un
   `InMemoryMemoryRepository` dedicato) `submit_contribution` solleva
   `ConsentRequiredError` senza lasciare traccia nel repository.
2. Nessun contributo senza licenza: `licenza=""` -> 422 (il contratto stesso
   ha `Field(min_length=1)`); `licenza` assente -> 422.
3. Pseudonimo obbligatorio: `contributor_id=""` -> 422 (via
   `PseudonymRequiredError`); nessun campo PII nel contratto.
4. Curatela prima della pubblicazione: un contributo valido appena creato ha
   `curato=False` e NON compare in `GET /memory/{place_id}`; dopo
   `curate_contribution` (via lo STESSO repository usato dal BFF, vedi nota
   sotto) compare.
5. Aggancio al grafo: `riguarda_to_cypher(contribution)` produce
   `MERGE (:Memoria)` + una `RIGUARDA` per ogni id in `riguarda` (via
   `UNWIND $riguarda`, parametrico).
6. Un'esperienza vissuta genera un contributo: un `MemoryContribution` con
   `esperienza_id` valorizzato (kind RACCONTO) attraversa
   submit -> curate -> `GET /memory/{place_id}` e compare.

NOTA sulla condivisione del repository (criterio 4 e 6): il BFF non espone
un endpoint HTTP di curatela in questa wave (vedi CLAUDE.md del task). Per
testare submit via HTTP e curatela via service SENZA duplicare lo storage,
questo modulo chiama direttamente `api.deps.get_memory_repository()` — è
decorata con `@lru_cache`, quindi la seconda chiamata (qui, nello stesso
processo del `TestClient`, che gira in-process) restituisce la STESSA
istanza già creata dal primo `POST /memory` gestito dall'endpoint, non una
nuova. Un `autouse fixture` verifica che quell'istanza sia
`InMemoryMemoryRepository` (il percorso offline verificato di questa wave) e
salta i test altrimenti, invece di far fallire in modo fuorviante un test
che assumerebbe un repository sbagliato.

Se un test qui fallisce, il bug è nel servizio a valle (api / urban_memory),
non nel test: non "aggiustare" l'asserzione per farla passare, segnala il
bug al subagent competente (vedi CLAUDE.md).
"""

from __future__ import annotations

from typing import Any

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from pydantic import ValidationError
from urban_memory import (
    ConsentRequiredError,
    InMemoryMemoryRepository,
    curate_contribution,
    riguarda_to_cypher,
    submit_contribution,
)

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


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


@pytest.fixture(autouse=True)
def _richiede_repository_in_memory() -> None:
    """Guardia: i criteri 4 e 6 assumono che `api.deps.get_memory_repository()`
    risolva a `InMemoryMemoryRepository` (percorso offline, nessun
    `DATABASE_URL`). Se un ambiente lo configurasse diversamente, salta con un
    messaggio esplicito invece di far fallire in modo fuorviante i test che
    condividono quell'istanza con il BFF."""
    repo = api_deps.get_memory_repository()
    if not isinstance(repo, InMemoryMemoryRepository):
        pytest.skip(
            "api.deps.get_memory_repository() non risolve a "
            "InMemoryMemoryRepository (DATABASE_URL configurato?): questa "
            "wave verifica solo il percorso offline."
        )


# ---------------------------------------------------------------------------
# Helper di costruzione payload (nessun contratto ridefinito: solo dizionari
# conformi a `packages/contracts`, come li manderebbe l'app Flutter).
# ---------------------------------------------------------------------------


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "mem-w2-default",
        "kind": MemoryKind.RACCONTO.value,
        "testo": "Un racconto di prova per i test di integrazione Wave 2.",
        "media_uri": None,
        "riguarda": ["bottega-w2-default"],
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
# 1. Nessun contributo persiste senza consenso
# ---------------------------------------------------------------------------


def test_nessun_contributo_persiste_senza_consenso(client: Any) -> None:
    place_id = "luogo-w2-consenso"
    payload = _payload(id="mem-w2-no-consenso", riguarda=[place_id], consenso=False)

    resp = client.post("/memory", json=payload)
    assert resp.status_code == 422
    assert "consenso" in resp.json()["detail"].lower()

    # Mai persistito: non compare nemmeno cercandolo per place_id.
    get_resp = client.get(f"/memory/{place_id}")
    assert get_resp.status_code == 200
    assert get_resp.json() == []

    # Stesso vincolo verificato direttamente a livello `urban_memory.service`,
    # con un repository DEDICATO (non quello del BFF): submit_contribution
    # deve sollevare ConsentRequiredError e non lasciare traccia.
    repo = InMemoryMemoryRepository()
    contributo = MemoryContribution(
        **_payload(id="mem-w2-no-consenso-service", riguarda=[place_id], consenso=False)
    )
    with pytest.raises(ConsentRequiredError):
        submit_contribution(repo, contributo)
    assert repo.list_pending() == []
    assert repo.get_curated(place_id) == []


# ---------------------------------------------------------------------------
# 2. Nessun contributo senza licenza
# ---------------------------------------------------------------------------


def test_nessun_contributo_senza_licenza(client: Any) -> None:
    # licenza="": già rifiutata dal contratto stesso (Field(min_length=1)),
    # quindi il 422 arriva dalla validazione Pydantic di FastAPI.
    payload_vuota = _payload(id="mem-w2-licenza-vuota", licenza="")
    resp_vuota = client.post("/memory", json=payload_vuota)
    assert resp_vuota.status_code == 422

    # licenza assente dal body: 422 "campo obbligatorio mancante".
    payload_assente = _payload(id="mem-w2-licenza-assente")
    del payload_assente["licenza"]
    resp_assente = client.post("/memory", json=payload_assente)
    assert resp_assente.status_code == 422


# ---------------------------------------------------------------------------
# 3. Pseudonimo obbligatorio, nessun campo PII
# ---------------------------------------------------------------------------


def test_pseudonimo_obbligatorio_e_nessun_campo_pii(client: Any) -> None:
    payload = _payload(id="mem-w2-no-pseudonimo", contributor_id="")
    resp = client.post("/memory", json=payload)
    assert resp.status_code == 422
    dettaglio = resp.json()["detail"].lower()
    assert "pseudonimo" in dettaglio or "contributor_id" in dettaglio

    # contributor_id è uno PSEUDONIMO: il contratto non deve esporre nessun
    # campo che assomigli a PII grezza (nome, email, telefono, indirizzo...).
    campi_pii_vietati = {
        "email", "nome", "cognome", "telefono", "phone", "indirizzo",
        "address", "full_name", "surname", "first_name", "last_name",
        "cognome_nome", "codice_fiscale",
    }
    campi_modello = set(MemoryContribution.model_fields)
    assert not (campi_modello & campi_pii_vietati), (
        f"il contratto MemoryContribution espone campi che assomigliano a "
        f"PII: {campi_modello & campi_pii_vietati}"
    )
    assert "contributor_id" in campi_modello


# ---------------------------------------------------------------------------
# 4. Curatela prima della pubblicazione
# ---------------------------------------------------------------------------


def test_curatela_prima_della_pubblicazione(client: Any) -> None:
    place_id = "luogo-w2-curatela"
    payload = _payload(id="mem-w2-curatela", riguarda=[place_id])

    resp = client.post("/memory", json=payload)
    assert resp.status_code == 201
    creato = resp.json()
    assert creato["curato"] is False

    get_prima = client.get(f"/memory/{place_id}")
    assert get_prima.status_code == 200
    assert get_prima.json() == [], "un contributo non ancora curato non deve comparire"

    # Curatela via lo STESSO repository usato dall'endpoint (vedi nota nel
    # docstring del modulo su api.deps.get_memory_repository/@lru_cache).
    repo = api_deps.get_memory_repository()
    curato = curate_contribution(repo, "mem-w2-curatela")
    assert curato.curato is True

    get_dopo = client.get(f"/memory/{place_id}")
    assert get_dopo.status_code == 200
    ids_pubblicati = [c["id"] for c in get_dopo.json()]
    assert "mem-w2-curatela" in ids_pubblicati


# ---------------------------------------------------------------------------
# 5. Aggancio al grafo: MERGE (:Memoria) + una RIGUARDA per ogni id
# ---------------------------------------------------------------------------


def test_riguarda_to_cypher_produce_merge_memoria_e_una_riguarda_per_id() -> None:
    riguarda_ids = ["luogo-w2-a", "bottega-w2-b", "artista-w2-c"]
    contributo = MemoryContribution(
        **_payload(id="mem-w2-cypher", riguarda=riguarda_ids)
    )

    query, params = riguarda_to_cypher(contributo)

    assert "MERGE (m:Memoria" in query
    assert "RIGUARDA" in query
    assert "UNWIND $riguarda" in query, (
        "una RIGUARDA per ogni id in riguarda: la query fa UNWIND di "
        "$riguarda, così ogni id del contributo produce (al più) una "
        "relazione MERGE (m)-[:RIGUARDA]->(target)"
    )
    assert params["id"] == "mem-w2-cypher"
    assert params["riguarda"] == riguarda_ids

    # riguarda vuoto: VIETATO dal contratto (min_length=1). Un contributo che
    # non riguarda alcun nodo sarebbe un :Memoria orfano — è il bug osservato
    # su Aura. Il vincolo lo blocca alla costruzione, prima ancora del linker.
    with pytest.raises(ValidationError):
        MemoryContribution(**_payload(id="mem-w2-cypher-vuoto", riguarda=[]))


# ---------------------------------------------------------------------------
# 6. Un'esperienza vissuta genera un contributo
# ---------------------------------------------------------------------------


def test_esperienza_vissuta_genera_un_contributo_racconto(client: Any) -> None:
    place_id = "luogo-w2-esperienza"
    payload = _payload(
        id="mem-w2-esperienza",
        kind=MemoryKind.RACCONTO.value,
        esperienza_id="esperienza-liuteria-lucca",
        riguarda=[place_id],
        testo="Dopo la visita alla bottega, il racconto del liutaio.",
    )

    resp = client.post("/memory", json=payload)
    assert resp.status_code == 201
    creato = resp.json()
    assert creato["esperienza_id"] == "esperienza-liuteria-lucca"
    assert creato["kind"] == "racconto"
    assert creato["curato"] is False

    repo = api_deps.get_memory_repository()
    curate_contribution(repo, "mem-w2-esperienza")

    get_resp = client.get(f"/memory/{place_id}")
    assert get_resp.status_code == 200
    pubblicati = get_resp.json()
    assert any(
        c["id"] == "mem-w2-esperienza" and c["esperienza_id"] == "esperienza-liuteria-lucca"
        for c in pubblicati
    ), f"il contributo curato non compare in GET /memory/{place_id}: {pubblicati}"
