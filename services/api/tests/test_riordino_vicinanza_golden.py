"""Riordino per vicinanza sui casi del golden di Lucca (ondata 4, compito 1).

Su TUTTI i casi di composizione del golden (`compose|...`, `demo|*|sereno-10`,
`feriale|*|sereno-10`: 52 casi), confrontando la composizione di oggi con la
composizione a riordino DISATTIVATO (`engine._riordina_per_vicinanza`
sostituita dall'identita'):

  - l'insieme delle tappe (experience_id) e' identico;
  - la prima tappa e' la stessa;
  - i metri a piedi non aumentano mai (i punti d'arrivo sono quelli delle tappe);
  - durate e `reason` di ogni tappa, budget e tappe escluse non cambiano:
    cambiano solo ordine e arrivi.

Orari rispettati e budget non superato restano asseriti, su ogni caso, da
`test_golden_orari_rispettati` e `test_golden_itinerario` (`test_golden_lucca.py`).
Il riordino e' solo composizione: l'adattamento non lo usa, quindi gli `adapt*`
con richiesta congelata restano identici (asserito in `test_golden_lucca.py`).
Il confronto col golden vive in `test_golden_lucca.py`; qui la proprieta' e' ricalcolata
dal codice, non letta dal JSON atteso.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from contracts import Punto, distanza_a_piedi_m  # noqa: E402
from experience_engine import engine as motore  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
CASI_COMPOSIZIONE_ATTESI = 52


def _chiavi_composizione() -> list[str]:
    if not FILE_ITINERARI.is_file():
        return ["__golden_mancante__"]
    casi = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return sorted(k for k, c in casi.items() if c["tipo"] == "compose")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    fonte = SeedCandidateSource()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: InMemoryBehaviorEventRepository())
    monkeypatch.setattr(
        api_main, "get_segnale_repository", lambda: InMemorySegnaleFluttuanteRepository()
    )
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: InMemoryTracciaRepository())
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(api_main, "get_adesso", lambda: ADESSO_FISSO)
    yield TestClient(api_main.app)


def _richiesta(chiave: str) -> dict[str, Any]:
    casi = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    richiesta: dict[str, Any] = casi[chiave]["richiesta"]
    return richiesta


def _compone(client: TestClient, chiave: str) -> dict[str, Any]:
    resp = client.post("/itinerary", json=_richiesta(chiave))
    assert resp.status_code == 200, resp.text
    risposta: dict[str, Any] = resp.json()
    return risposta


def _compone_senza_riordino(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, chiave: str
) -> dict[str, Any]:
    with monkeypatch.context() as m:
        m.setattr(motore, "_riordina_per_vicinanza", lambda selezionati, **_kw: list(selezionati))
        return _compone(client, chiave)


def _metri(risposta: dict[str, Any]) -> int:
    totale = 0
    precedente: Punto | None = None
    for tappa in risposta["stops"]:
        dato = tappa.get("punto_arrivo")
        corrente = Punto(**dato) if dato else None
        if precedente is not None and corrente is not None:
            totale += distanza_a_piedi_m(precedente, corrente)
        precedente = corrente
    return totale


def _ids(risposta: dict[str, Any]) -> list[str]:
    return [s["experience_id"] for s in risposta["stops"]]


def test_il_golden_ha_i_casi_di_composizione_attesi() -> None:
    chiavi = _chiavi_composizione()
    assert len(chiavi) == CASI_COMPOSIZIONE_ATTESI
    assert any(k.startswith("demo|") and k.endswith("|sereno-10") for k in chiavi)
    assert any(k.startswith("feriale|") for k in chiavi)


@pytest.mark.parametrize("chiave", _chiavi_composizione())
def test_il_riordino_conserva_insieme_e_prima_tappa_e_non_aumenta_i_metri(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, chiave: str
) -> None:
    prima = _compone_senza_riordino(client, monkeypatch, chiave)
    dopo = _compone(client, chiave)
    assert set(_ids(dopo)) == set(_ids(prima)), chiave
    assert len(_ids(dopo)) == len(_ids(prima)), chiave
    if prima["stops"]:
        assert _ids(dopo)[0] == _ids(prima)[0], chiave
    assert _metri(dopo) <= _metri(prima), chiave
    # Solo ordine e arrivi: durata e motivo di ogni tappa sono quelli di prima.
    sintesi_prima = {s["experience_id"]: (s["durata_min"], s["reason"]) for s in prima["stops"]}
    sintesi_dopo = {s["experience_id"]: (s["durata_min"], s["reason"]) for s in dopo["stops"]}
    assert sintesi_dopo == sintesi_prima, chiave
    assert dopo["tempo_effettivo_min"] == prima["tempo_effettivo_min"], chiave
    assert dopo["tappe_escluse"] == prima["tappe_escluse"], chiave


def test_il_riordino_agisce_davvero_sul_golden(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La proprieta' non e' vuota: molti casi cambiano ordine, e quando
    cambiano i metri diminuiscono STRETTAMENTE."""
    riordinati = 0
    for chiave in _chiavi_composizione():
        prima = _compone_senza_riordino(client, monkeypatch, chiave)
        dopo = _compone(client, chiave)
        if _ids(dopo) != _ids(prima):
            riordinati += 1
            assert _metri(dopo) < _metri(prima), chiave
        else:
            assert _metri(dopo) == _metri(prima), chiave
    assert riordinati >= 30, riordinati


def test_il_confronto_fallirebbe_con_un_riordino_che_cambia_l_insieme(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doppio negativo: un finto riordino che toglie una tappa viene colto."""
    chiave = "demo|curioso|sereno-10"
    prima = _compone_senza_riordino(client, monkeypatch, chiave)
    with monkeypatch.context() as m:
        m.setattr(motore, "_riordina_per_vicinanza", lambda selezionati, **_kw: selezionati[:-1])
        dopo = _compone(client, chiave)
    assert set(_ids(dopo)) != set(_ids(prima))
