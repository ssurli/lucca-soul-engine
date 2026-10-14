"""Test BFF del bagliore (docs/PROMOZIONE_TRACCIA.md §2b): `POST /itinerary`
legge le tracce dei luoghi candidati dal ledger server-side, fail-closed.
Stesso stile di `test_eventi_promossi.py`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
api_main = pytest.importorskip("api.main")
contracts = pytest.importorskip("contracts")
urban_memory_repo = pytest.importorskip("urban_memory.traccia_repository")

TestClient = fastapi_testclient.TestClient
PLACE = "piazza-test-bagliore"
FRASE = "È un luogo che torna spesso a vivere di arte."


class _Source:
    def __init__(self, candidates: list[Any]) -> None:
        self._c = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._c


class _EventoReaderVuoto:
    def eventi_ricorrenti(self) -> list[Any]:
        return []


class _RepoCheSolleva:
    def __init__(self) -> None:
        self.chiamate = 0

    def tracce_per_luoghi(self, place_ids: Any) -> Any:
        self.chiamate += 1
        raise RuntimeError("ledger irraggiungibile (simulato)")

    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        raise RuntimeError("ledger irraggiungibile (simulato)")


class _RepoSpia(urban_memory_repo.InMemoryTracciaRepository):
    def __init__(self) -> None:
        super().__init__()
        self.richieste: list[list[str]] = []

    def tracce_per_luoghi(self, place_ids: Any) -> Any:
        self.richieste.append(list(place_ids))
        return super().tracce_per_luoghi(place_ids)


def _cand(eid: str, place: str, temi: list[str]) -> Any:
    esp = contracts.ExperienceNode(
        id=eid, titolo=f"Titolo {eid}", place_id=place, temi=temi, durata_min=30,
        al_chiuso=False, accessibile=True,
    )
    return contracts.GraphCandidate(
        experience=esp, place_nome=f"Luogo {place}", connessioni=['Evoca il tema "Arte".']
    )


def _body(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "turista-bagliore",
        "profile": {
            "curiosita": 0.3, "contemplazione": 0.2, "arte": 0.9, "con_bambini": False,
            "tempo_disponibile_min": 200,
        },
        "signal": {
            "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0, "ora": "10:00:00",
            "eventi_attivi": [],
        },
    }
    base.update(extra)
    return base


def _stub(monkeypatch: pytest.MonkeyPatch, repo: Any) -> None:
    cands = [_cand("exp-bagliore-1", PLACE, ["arte"]), _cand("exp-bagliore-2", "altro", ["arte"])]
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: _Source(cands))
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: _EventoReaderVuoto())
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: repo)
    monkeypatch.setattr(api_main, "get_city_tz", lambda: None)


def _repo_con_tracce(n: int = 3) -> _RepoSpia:
    repo = _RepoSpia()
    ora = datetime.now(UTC)
    for i in range(n):
        repo.deposita(
            segnale_id=f"s{i}", place_id=PLACE, temi=["arte"], creato_il=ora - timedelta(days=1 + i)
        )
    return repo


def test_caso_felice_frase_nel_reason_della_tappa(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo_con_tracce(3)
    _stub(monkeypatch, repo)
    resp = TestClient(api_main.app).post("/itinerary", json=_body())
    assert resp.status_code == 200
    stops = {s["experience_id"]: s for s in resp.json()["stops"]}
    assert FRASE in stops["exp-bagliore-1"]["reason"]
    assert "torna spesso a vivere" not in stops["exp-bagliore-2"]["reason"]
    # una sola lettura batch, con i place_id distinti dei candidati
    assert len(repo.richieste) == 1
    assert sorted(repo.richieste[0]) == sorted({PLACE, "altro"})


def test_tracce_insufficienti_nessuna_frase(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _repo_con_tracce(1))
    resp = TestClient(api_main.app).post("/itinerary", json=_body())
    assert resp.status_code == 200
    assert all("torna spesso a vivere" not in s["reason"] for s in resp.json()["stops"])


def test_fail_closed_ledger_che_solleva_200_stesse_tappe(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _repo_con_tracce(3))
    client = TestClient(api_main.app, raise_server_exceptions=False)
    con_frase = client.post("/itinerary", json=_body()).json()

    rotto = _RepoCheSolleva()
    _stub(monkeypatch, rotto)
    resp = client.post("/itinerary", json=_body())

    assert resp.status_code == 200
    assert rotto.chiamate == 1  # la lettura e' stata tentata davvero
    guasto = resp.json()
    assert [s["experience_id"] for s in guasto["stops"]] == [
        s["experience_id"] for s in con_frase["stops"]
    ]
    for s in guasto["stops"]:
        assert "torna spesso a vivere" not in s["reason"]
        assert s["reason"]


def test_fail_closed_con_repo_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, None)  # AttributeError su None.tracce_per_luoghi
    resp = TestClient(api_main.app, raise_server_exceptions=False).post(
        "/itinerary", json=_body()
    )
    assert resp.status_code == 200
    assert all("torna spesso a vivere" not in s["reason"] for s in resp.json()["stops"])


@pytest.mark.parametrize(
    "extra",
    [
        {"tracce_per_luogo": {PLACE: [["2026-01-01T00:00:00Z", ["arte"]]] * 5}},
        {"tracce": [1, 2, 3]},
    ],
)
def test_le_tracce_non_vengono_dal_body(monkeypatch: pytest.MonkeyPatch, extra: dict) -> None:
    _stub(monkeypatch, _repo_con_tracce(0))  # ledger vuoto
    client = TestClient(api_main.app)
    resp = client.post("/itinerary", json=_body(**extra))
    assert resp.status_code == 422  # extra="forbid": il campo e' rifiutato
    corpo = _body()
    corpo["signal"].update(extra)
    assert client.post("/itinerary", json=corpo).status_code == 422
    ok = client.post("/itinerary", json=_body())
    assert ok.status_code == 200
    assert all("torna spesso a vivere" not in s["reason"] for s in ok.json()["stops"])


# --- orologio iniettato (api.main.get_adesso) -------------------------------

FISSO = datetime(2030, 1, 15, 9, 0, tzinfo=UTC)  # futuro: con now() reale non darebbe frase


def _repo_fisso(n: int = 3) -> _RepoSpia:
    repo = _RepoSpia()
    for i in range(n):
        repo.deposita(
            segnale_id=f"f{i}", place_id=PLACE, temi=["arte"],
            creato_il=FISSO - timedelta(days=1 + i),
        )
    return repo


def test_adesso_fissato_frase_deterministica(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _repo_fisso())
    monkeypatch.setattr(api_main, "get_adesso", lambda: FISSO)
    client = TestClient(api_main.app)
    r1 = client.post("/itinerary", json=_body()).json()
    r2 = client.post("/itinerary", json=_body()).json()
    stops = {s["experience_id"]: s["reason"] for s in r1["stops"]}
    assert FRASE in stops["exp-bagliore-1"]
    assert [s["reason"] for s in r1["stops"]] == [s["reason"] for s in r2["stops"]]


def test_adesso_fissato_lontano_nessuna_frase(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _repo_fisso())
    monkeypatch.setattr(api_main, "get_adesso", lambda: FISSO + timedelta(days=3 * 365))
    resp = TestClient(api_main.app).post("/itinerary", json=_body())
    assert resp.status_code == 200
    assert all("torna spesso a vivere" not in s["reason"] for s in resp.json()["stops"])


def test_get_adesso_letto_una_volta_per_richiesta(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _repo_fisso())
    letture: list[int] = []

    def _adesso() -> datetime:
        letture.append(1)
        return FISSO

    monkeypatch.setattr(api_main, "get_adesso", _adesso)
    client = TestClient(api_main.app)
    client.post("/itinerary", json=_body())
    assert len(letture) == 1
    client.post("/itinerary", json=_body())
    assert len(letture) == 2
