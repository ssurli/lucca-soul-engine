"""`ItineraryStop.causa_adattamento` via HTTP del BFF (seed di Lucca, in-memory).

Flussi del copione: `/itinerary` poi `/itinerary/adapt` con i segnali dei tre
preset dell'app («Troppa folla»: via-fillungo e san-michele-in-foro a 0.75;
«Piove»; «Piove + Stanco/a»: stanchezza 0.85). Per ogni tappa sostituita o
mantenuta la causa e' valorizzata e concorda col `reason`; le non toccate
hanno None; il valore inviato dal client e' ignorato.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from experience_engine.engine import (  # noqa: E402
    _FRASE_MANTENUTA_PIOGGIA,
    _PREFISSO_MANTENUTA_AFFOLLAMENTO,
    _SUFFISSO_MANTENUTA_AFFOLLAMENTO,
)
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
FOLLA = 0.75
LUOGHI_FOLLA = ["via-fillungo", "san-michele-in-foro"]
PROFILI_DEMO = ["ama-arte", "contemplativo", "curioso", "con-bambini", "onnivoro"]


def _segnale(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0,
        "ora": "10:00:00", "data": "2026-12-12", "eventi_attivi": [],
    }
    base.update(kw)
    return base


PRESET: dict[str, dict[str, Any]] = {
    "Troppa folla": _segnale(affollamento={luogo: FOLLA for luogo in LUOGHI_FOLLA}),
    "Piove": _segnale(meteo="pioggia"),
    "Piove + Stanco/a": _segnale(meteo="pioggia", stanchezza=0.85),
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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
    monkeypatch.setattr(api_main, "get_adesso", lambda: ADESSO_FISSO)
    return TestClient(api_main.app)


def _richiesta_compose(profilo: str, tempo: int) -> dict[str, Any]:
    casi = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    richiesta: dict[str, Any] = json.loads(
        json.dumps(casi[f"demo|{profilo}|sereno-10"]["richiesta"])
    )
    richiesta["profile"]["tempo_disponibile_min"] = tempo
    return richiesta


def _flusso(
    client: TestClient, profilo: str, preset: str, tempo: int, *, itin_mod: Any = None
) -> list[dict[str, Any]]:
    resp = client.post("/itinerary", json=_richiesta_compose(profilo, tempo))
    assert resp.status_code == 200, resp.text
    itin = resp.json()
    # Composizione: nessuna causa.
    assert all(s.get("causa_adattamento") is None for s in itin["stops"])
    if itin_mod is not None:
        itin = itin_mod(itin)
    resp = client.post(
        "/itinerary/adapt", json={"itinerary": itin, "signal": PRESET[preset]}
    )
    assert resp.status_code == 200, resp.text
    stops: list[dict[str, Any]] = resp.json()["stops"]
    return stops


def _dice_affollamento(reason: str) -> bool:
    return reason.startswith("Sostituita per l'affollamento") or (
        _PREFISSO_MANTENUTA_AFFOLLAMENTO in reason
        and _SUFFISSO_MANTENUTA_AFFOLLAMENTO in reason
    )


def _dice_pioggia(reason: str) -> bool:
    return reason.startswith("Sostituita per la pioggia") or _FRASE_MANTENUTA_PIOGGIA in reason


def _controlla(stops: list[dict[str, Any]], preset: str) -> set[str | None]:
    viste: set[str | None] = set()
    for s in stops:
        esito, causa, reason = s["esito_adattamento"], s["causa_adattamento"], s["reason"]
        viste.add(causa)
        if esito in ("sostituita", "mantenuta_senza_alternativa"):
            assert causa in ("pioggia", "affollamento"), (preset, s)
            if causa == "pioggia":
                assert _dice_pioggia(reason) and not _dice_affollamento(reason), (preset, s)
            else:
                assert _dice_affollamento(reason) and not _dice_pioggia(reason), (preset, s)
        else:
            assert causa is None, (preset, s)
            assert not _dice_pioggia(reason) and not _dice_affollamento(reason), (preset, s)
    return viste


@pytest.mark.parametrize("preset", list(PRESET))
def test_causa_valorizzata_e_coerente_col_reason(client: TestClient, preset: str) -> None:
    viste: set[str | None] = set()
    toccate = 0
    for profilo in PROFILI_DEMO:
        for tempo in (180, 400):
            stops = _flusso(client, profilo, preset, tempo)
            toccate += sum(
                s["esito_adattamento"] in ("sostituita", "mantenuta_senza_alternativa")
                for s in stops
            )
            viste |= _controlla(stops, preset)
    # Non vacuita': il preset tocca davvero qualche tappa.
    assert toccate > 0, f"nessuna tappa toccata dal preset {preset!r}: il test non prova nulla"
    if preset == "Troppa folla":
        assert "affollamento" in viste and "pioggia" not in viste
    else:
        assert "pioggia" in viste and "affollamento" not in viste


@pytest.mark.parametrize("preset", list(PRESET))
def test_il_valore_inviato_dal_client_e_ignorato(client: TestClient, preset: str) -> None:
    """Il client forza causa 'affollamento'/'pioggia' (con esito 'sostituita') su tutte
    le tappe: la risposta e' identica a quella senza forzatura."""
    def forza(causa: str) -> Any:
        def mod(itin: dict[str, Any]) -> dict[str, Any]:
            return {
                **itin,
                "stops": [
                    {**s, "esito_adattamento": "sostituita", "causa_adattamento": causa}
                    for s in itin["stops"]
                ],
            }
        return mod

    for profilo in ("curioso", "con-bambini"):
        base = _flusso(client, profilo, preset, 400)
        for causa in ("pioggia", "affollamento"):
            forzata = _flusso(client, profilo, preset, 400, itin_mod=forza(causa))
            assert [s["causa_adattamento"] for s in forzata] == [
                s["causa_adattamento"] for s in base
            ], (profilo, preset, causa)
            _controlla(forzata, preset)
