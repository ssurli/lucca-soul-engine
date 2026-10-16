"""Integrazione — wave "adattamento": andata e ritorno compose -> adapt via BFF.

Il JSON di risposta di `POST /itinerary` (e di `POST /itinerary/adapt`) viene
REINVIATO tale e quale a `POST /itinerary/adapt`, come fa l'app: i campi nuovi
(`tempo_disponibile_min`, `tempo_effettivo_min`, `tappe_escluse`,
`esito_adattamento`) devono sopravvivere e il BFF, con `extra="forbid"`, deve
accettarli. Offline: `SeedCandidateSource`, nessun database (come
`test_integration_wave1.py`).

Se un test fallisce, il bug e' nel servizio a valle: segnalalo, non
"aggiustare" l'asserzione.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)

TestClient = fastapi_testclient.TestClient

MINUTI_GIORNATA = 24 * 60


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


def _signal(
    meteo: str = "sereno", stanchezza: float = 0.1, ora: str = "10:00:00"
) -> dict[str, Any]:
    return {"meteo": meteo, "affollamento": {}, "stanchezza": stanchezza, "ora": ora}


def _contesto(person_id: str, tempo: int, ora: str = "10:00:00") -> dict[str, Any]:
    return {
        "person_id": person_id,
        "profile": {
            "curiosita": 0.9,
            "contemplazione": 0.3,
            "arte": 0.6,
            "con_bambini": False,
            "tempo_disponibile_min": tempo,
        },
        "signal": _signal(ora=ora),
    }


def _minuti(stops: list[dict[str, Any]]) -> int:
    """Ultimo arrivo + ultima durata - primo arrivo (senza riavvolgimento)."""

    def mm(o: str) -> int:
        h, m, _ = o.split(":")
        return int(h) * 60 + int(m)

    if not stops:
        return 0
    assert mm(stops[-1]["arrivo"]) >= mm(stops[0]["arrivo"]), "orari riavvolti"
    return mm(stops[-1]["arrivo"]) + stops[-1]["durata_min"] - mm(stops[0]["arrivo"])


def _componi(client: Any, person_id: str = "rt-1", tempo: int = 240, ora: str = "10:00:00") -> Any:
    resp = client.post("/itinerary", json=_contesto(person_id, tempo, ora))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _adatta(client: Any, itinerario: dict[str, Any], segnale: dict[str, Any]) -> Any:
    return client.post("/itinerary/adapt", json={"itinerary": itinerario, "signal": segnale})


# ---------------------------------------------------------------------------
# La composizione registra il budget; la risposta contiene i campi nuovi
# ---------------------------------------------------------------------------


def test_compose_registra_budget_e_campi_nuovi(client: Any) -> None:
    it = _componi(client, tempo=240)
    assert it["tempo_disponibile_min"] == 240
    assert it["tempo_effettivo_min"] == 240
    assert it["tappe_escluse"] == []
    assert it["adattato_da_segnale"] is False
    assert all(s["esito_adattamento"] is None for s in it["stops"])
    assert _minuti(it["stops"]) <= it["tempo_effettivo_min"]


def test_compose_di_sera_tronca_il_budget_alla_mezzanotte(client: Any) -> None:
    it = _componi(client, person_id="rt-sera", tempo=240, ora="22:00:00")
    assert it["tempo_disponibile_min"] == 240
    assert it["tempo_effettivo_min"] == 120
    assert _minuti(it["stops"]) <= 120
    ultima = it["stops"][-1]
    h, m, _ = ultima["arrivo"].split(":")
    assert int(h) * 60 + int(m) + ultima["durata_min"] <= MINUTI_GIORNATA


# ---------------------------------------------------------------------------
# Andata e ritorno: la risposta reinviata e' accettata, i campi sopravvivono
# ---------------------------------------------------------------------------


def test_risposta_di_compose_reinviata_all_adapt_e_accettata(client: Any) -> None:
    base = _componi(client)
    resp = _adatta(client, base, _signal(meteo="pioggia"))
    assert resp.status_code == 200, resp.text
    ad = resp.json()
    # il budget fa andata e ritorno invariato
    assert ad["tempo_disponibile_min"] == base["tempo_disponibile_min"]
    assert ad["tempo_effettivo_min"] == base["tempo_effettivo_min"]
    # ogni tappa presente ha un esito di tappa (mai di taglio) e un reason
    for s in ad["stops"]:
        assert s["esito_adattamento"] in {
            "non_toccata",
            "sostituita",
            "mantenuta_senza_alternativa",
        }
        assert s["reason"].strip()
    # il vincolo di budget vale dopo l'adattamento
    assert _minuti(ad["stops"]) <= ad["tempo_effettivo_min"]


def test_risposta_di_adapt_reinviata_di_nuovo_e_tappe_escluse_si_conservano(client: Any) -> None:
    base = _componi(client)
    primo = _adatta(client, base, _signal(stanchezza=0.9))
    assert primo.status_code == 200, primo.text
    primo_json = primo.json()
    assert primo_json["adattato_da_segnale"] is True
    assert primo_json["tappe_escluse"], "con stanchezza alta la coda va in tappe_escluse"
    assert {t["esito"] for t in primo_json["tappe_escluse"]} == {"tagliata_stanchezza"}
    assert all(t["reason"].strip() for t in primo_json["tappe_escluse"])
    # le tappe tolte non sono piu' tra le stops
    presenti = {s["experience_id"] for s in primo_json["stops"]}
    assert presenti.isdisjoint({t["experience_id"] for t in primo_json["tappe_escluse"]})

    # Secondo giro: la risposta (con tappe_escluse e esito non null) torna cosi' com'e'.
    secondo = _adatta(client, copy.deepcopy(primo_json), _signal(meteo="sereno", stanchezza=0.1))
    assert secondo.status_code == 200, secondo.text
    secondo_json = secondo.json()
    assert secondo_json["tappe_escluse"] == primo_json["tappe_escluse"]
    assert secondo_json["tempo_disponibile_min"] == base["tempo_disponibile_min"]
    assert secondo_json["tempo_effettivo_min"] == base["tempo_effettivo_min"]
    # nessun segnale da applicare: l'esito dell'ultimo segnale e' non_toccata
    assert all(s["esito_adattamento"] == "non_toccata" for s in secondo_json["stops"])
    assert secondo_json["adattato_da_segnale"] is False


def test_itinerario_senza_campi_nuovi_e_ancora_accettato(client: Any) -> None:
    """Retrocompatibilita': un client vecchio non manda budget ne' esiti."""
    base = _componi(client)
    vecchio = copy.deepcopy(base)
    for campo in ("tempo_disponibile_min", "tempo_effettivo_min", "tappe_escluse"):
        del vecchio[campo]
    for s in vecchio["stops"]:
        del s["esito_adattamento"]
    resp = _adatta(client, vecchio, _signal(meteo="pioggia"))
    assert resp.status_code == 200, resp.text
    ad = resp.json()
    assert ad["tempo_disponibile_min"] is None
    assert ad["tempo_effettivo_min"] is None
    assert all(s["reason"].strip() for s in ad["stops"])


# ---------------------------------------------------------------------------
# Il BFF rifiuta cio' che i contratti rifiutano (extra="forbid", validatori)
# ---------------------------------------------------------------------------


def test_campo_extra_in_una_tappa_esclusa_rifiutato_422(client: Any) -> None:
    primo = _adatta(client, _componi(client), _signal(stanchezza=0.9)).json()
    primo["tappe_escluse"][0]["durata_min"] = 30
    assert _adatta(client, primo, _signal()).status_code == 422


def test_campo_extra_sull_itinerario_rifiutato_422(client: Any) -> None:
    base = _componi(client)
    base["budget_residuo"] = 10
    assert _adatta(client, base, _signal()).status_code == 422


def test_esito_di_taglio_su_una_tappa_presente_rifiutato_422(client: Any) -> None:
    base = _componi(client)
    base["stops"][0]["esito_adattamento"] = "tagliata_tetto_giornata"
    assert _adatta(client, base, _signal()).status_code == 422


def test_tappa_esclusa_con_esito_di_tappa_rifiutata_422(client: Any) -> None:
    base = _componi(client)
    base["tappe_escluse"] = [
        {"experience_id": "exp-x", "esito": "sostituita", "reason": "Non e' un taglio."}
    ]
    assert _adatta(client, base, _signal()).status_code == 422


def test_budget_incoerente_rifiutato_422(client: Any) -> None:
    base = _componi(client)
    base["tempo_effettivo_min"] = base["tempo_disponibile_min"] + 1
    assert _adatta(client, base, _signal()).status_code == 422
    solo = _componi(client)
    del solo["tempo_effettivo_min"]
    assert _adatta(client, solo, _signal()).status_code == 422
