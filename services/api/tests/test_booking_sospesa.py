"""`POST /booking` con un'esperienza prenotabile ma SOSPESA (ondata 1b-2).

Modello: `test_booking.py`. Il BFF passa `sospesa` letta dal candidato a
`marketplace.request_booking`, che rifiuta (422) senza scrivere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
api_deps = pytest.importorskip("api.deps")
marketplace = pytest.importorskip("marketplace")
from contracts import ExperienceNode, GraphCandidate  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_ID = "exp-sospesa-prenotabile"


class _Fonte:
    def __init__(self, sospesa: bool) -> None:
        self._c = [
            GraphCandidate(
                experience=ExperienceNode(
                    id=_ID, titolo="Prova", place_id="luogo-prova", temi=["prova"],
                    durata_min=30, al_chiuso=True, accessibile=True,
                    prezzo_eur=10.0, prenotabile=True, sospesa=sospesa,
                ),
                place_nome="Luogo di prova",
                connessioni=[],
            )
        ]

    def candidates(self, ctx: Any) -> list[Any]:
        return self._c


def _client(
    monkeypatch: pytest.MonkeyPatch, sospesa: bool, repo: Any
) -> TestClient:
    fonte = _Fonte(sospesa)
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    api_main.app.dependency_overrides[api_deps.get_booking_repository] = lambda: repo
    return TestClient(api_main.app)


def _payload() -> dict[str, Any]:
    return {
        "person_id": "turista-pseudonimo",
        "experience_id": _ID,
        "quando": datetime(2026, 8, 1, 10, 0, tzinfo=UTC).isoformat(),
    }


def test_booking_esperienza_sospesa_risponde_422_e_non_crea(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = marketplace.InMemoryBookingRepository()
    try:
        resp = _client(monkeypatch, True, repo).post("/booking", json=_payload())
    finally:
        api_main.app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert repo._bookings == {}


def test_booking_esperienza_non_sospesa_resta_201(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = marketplace.InMemoryBookingRepository()
    try:
        resp = _client(monkeypatch, False, repo).post("/booking", json=_payload())
    finally:
        api_main.app.dependency_overrides.clear()
    assert resp.status_code == 201
    assert len(repo._bookings) == 1
