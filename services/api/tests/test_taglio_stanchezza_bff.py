"""Taglio per stanchezza via BFF isolato (ondata 3, compito 1).

Caso reale: profilo curioso dalle risposte dell'app, mezza giornata (180 min),
sabato 12/12/2026 alle 15:00; poi "Piove" + "Sono stanco/a" (pioggia,
stanchezza 0.85). Itinerario ricevuto 25+30+40+35+20 = 150 min -> limite 100.
Dopo la sostituzione della prima tappa (20 min) il tempo è 20, 50, 90, 125, 145:
90 è più vicino a 100 di 125, quindi restano TRE tappe; quarta e quinta tagliate.

Ondata 3, compito 4: con i trasferimenti dai punti di arrivo (al posto della
stima prudente di 10 min) nella mezza giornata entra una quinta tappa da 20
min; prima l'itinerario ricevuto era 25+30+40+35 = 130 (limite 86) e veniva
tagliata la sola quarta. Il caso resta "tre tappe tenute".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from contracts import OnboardingAnswer, OnboardingRequest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from rag.onboarding import profile_from_answers  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

RISPOSTE = {
    "perdersi": "Sì, mi piace perdermi senza una meta precisa",
    "bambini": "No, non sono con bambini",
    "tempo": "Mezza giornata, circa tre ore",
    "accessibilita": "No, nessuna esigenza di accessibilità",
    "silenzio_musica": "Un mix tra silenzio e musica",
    "bellezza_storie": "Un po' di bellezza e un po' di storie",
}
SEGNALE = {
    "meteo": "sereno", "affollamento": {}, "stanchezza": 0.1, "ora": "15:00:00",
    "data": "2026-12-12", "eventi_attivi": [], "istante": "2026-12-12T14:00:00Z",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato come in `test_golden_lucca.py`: seed versionato, repository
    in memoria, orologio fisso, nessuna credenziale."""
    fonte = SeedCandidateSource()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(
        api_main, "get_adesso", lambda: datetime(2026, 12, 12, 14, 0, tzinfo=UTC)
    )
    return TestClient(api_main.app)


def test_piove_e_stanco_tiene_tre_tappe(client: TestClient) -> None:
    req = OnboardingRequest(
        lingua="it",
        risposte=[OnboardingAnswer(domanda_id=k, risposta=v) for k, v in RISPOSTE.items()],
    )
    profilo = profile_from_answers(req).model_dump(mode="json")
    r = client.post(
        "/itinerary",
        json={"person_id": "p", "kind": "turista", "profile": profilo, "signal": SEGNALE},
    )
    assert r.status_code == 200
    it: dict[str, Any] = r.json()
    durate = [s["durata_min"] for s in it["stops"]]
    # Precondizione del caso: se il seed cambia, il caso va ripensato.
    assert durate == [25, 30, 40, 35, 20]
    assert int(sum(durate) * 2 / 3) == 100

    r = client.post(
        "/itinerary/adapt",
        json={
            "itinerary": it,
            "signal": {**SEGNALE, "meteo": "pioggia", "stanchezza": 0.85},
            "profile": profilo,
        },
    )
    assert r.status_code == 200
    ad: dict[str, Any] = r.json()
    assert [s["durata_min"] for s in ad["stops"]] == [20, 30, 40]
    assert [s["esito_adattamento"] for s in ad["stops"]] == [
        "sostituita", "non_toccata", "non_toccata",
    ]
    # Prefisso: le tre tappe tenute sono le prime tre ricevute (la prima
    # sostituita), le tagliate sono le ultime due.
    assert [s["experience_id"] for s in ad["stops"]][1:] == [
        s["experience_id"] for s in it["stops"][1:3]
    ]
    assert [(e["experience_id"], e["esito"]) for e in ad["tappe_escluse"]] == [
        (it["stops"][3]["experience_id"], "tagliata_stanchezza"),
        (it["stops"][4]["experience_id"], "tagliata_stanchezza"),
    ]
    assert ad["adattato_da_segnale"] is True
