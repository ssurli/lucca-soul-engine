"""Il BFF passa DAVVERO il vocabolario dichiarato dal dataset della città.

`api.main.get_dataset` è sostituito con un `DatasetCitta` il cui vocabolario è
un oggetto riconoscibile (identità, non uguaglianza); `compose_itinerary`,
`adapt_itinerary` e `recommender.costruisci_score_fn` sono spiati in
`api.main`. Isolamento: `.env` e `lru_cache` di `api.deps` non hanno effetto
(selettori sostituiti in `api.main`, come in test_golden_lucca.py); nessun
valore di ambiente viene letto o stampato.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from contracts import VocabolarioTemi  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import DATASET as LUCCA  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

GOLDEN = Path(__file__).parent / "golden" / "lucca_itinerari.json"


def _richiesta(tipo: str) -> dict[str, Any]:
    casi = json.loads(GOLDEN.read_text(encoding="utf-8"))["casi"]
    return next(c["richiesta"] for c in casi.values() if c["tipo"] == tipo)


@pytest.fixture
def spie(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    # Ids esistenti in Lucca (il dataset valida il vocabolario), ma insiemi
    # diversi da quello storico e istanza distinta: riconoscibile per identità.
    riconoscibile = VocabolarioTemi(
        contemplativi=frozenset({"verde"}),
        arte=frozenset({"arte"}),
        insoliti=frozenset(),
        verde=frozenset({"verde"}),
        bambini="con-bambini",
    )
    dataset = dataclasses.replace(LUCCA, vocabolario=riconoscibile)
    chiamate: dict[str, Any] = {
        "vocabolario": riconoscibile,
        "compose": [],
        "adapt": [],
        "score": [],
    }

    compose_vero = api_main.compose_itinerary
    adapt_vero = api_main.adapt_itinerary
    score_vero = api_main.recommender.costruisci_score_fn

    def compose_spia(*a: Any, **k: Any) -> Any:
        chiamate["compose"].append(k.get("vocabolario"))
        return compose_vero(*a, **k)

    def adapt_spia(*a: Any, **k: Any) -> Any:
        chiamate["adapt"].append(k.get("vocabolario"))
        return adapt_vero(*a, **k)

    def score_spia(*a: Any, **k: Any) -> Any:
        chiamate["score"].append(k.get("vocabolario"))
        return score_vero(*a, **k)

    fonte = SeedCandidateSource()
    eventi = InMemoryBehaviorEventRepository()
    monkeypatch.setattr(api_main, "get_dataset", lambda: dataset)
    monkeypatch.setattr(api_main, "compose_itinerary", compose_spia)
    monkeypatch.setattr(api_main, "adapt_itinerary", adapt_spia)
    monkeypatch.setattr(api_main.recommender, "costruisci_score_fn", score_spia)
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(
        api_main, "get_segnale_repository", lambda: InMemorySegnaleFluttuanteRepository()
    )
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: InMemoryTracciaRepository())
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(api_main, "get_adesso", lambda: datetime(2026, 6, 15, 10, 0, tzinfo=UTC))
    return chiamate


def test_itinerary_passa_il_vocabolario_del_dataset(spie: dict[str, Any]) -> None:
    resp = TestClient(api_main.app).post("/itinerary", json=_richiesta("compose"))
    assert resp.status_code == 200, resp.text
    assert len(spie["compose"]) == 1 and len(spie["score"]) == 1
    assert spie["compose"][0] is spie["vocabolario"]
    assert spie["score"][0] is spie["vocabolario"]


def test_itinerary_adapt_passa_il_vocabolario_del_dataset(spie: dict[str, Any]) -> None:
    resp = TestClient(api_main.app).post("/itinerary/adapt", json=_richiesta("adapt"))
    assert resp.status_code == 200, resp.text
    assert len(spie["adapt"]) == 1
    assert spie["adapt"][0] is spie["vocabolario"]
