"""`POST /itinerary/adapt` CON `profile` (difetto j), via HTTP del BFF.

Ambiente isolato come in `test_golden_lucca.py`: seed di Lucca, repository
in-memory, `adesso` fisso, nessuna credenziale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import ESPERIENZE  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from rag.onboarding import profile_from_answers  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
ACCESSIBILI = {e.id for e in ESPERIENZE if e.accessibile}
PLACE_DI = {e.id: e.place_id for e in ESPERIENZE}


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


def _profilo(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "curiosita": 0.5, "contemplazione": 0.5, "arte": 0.5,
        "con_bambini": False, "tempo_disponibile_min": 180,
        "accessibilita_richiesta": False,
    }
    base.update(kw)
    return base


def _segnale(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meteo": "sereno", "affollamento": {}, "stanchezza": 0.0,
        "ora": "10:00:00", "data": "2026-06-15", "eventi_attivi": [],
    }
    base.update(kw)
    return base


def _componi(client: TestClient, profilo: dict[str, Any], pid: str = "t-adapt") -> dict[str, Any]:
    resp = client.post(
        "/itinerary",
        json={"person_id": pid, "profile": profilo, "signal": _segnale(), "luoghi_gia_visti": []},
    )
    assert resp.status_code == 200, resp.text
    out: dict[str, Any] = resp.json()
    assert out["stops"], "itinerario vuoto: il test non esercita nulla"
    return out


_ASSENTE = "assente"


def _adatta(
    client: TestClient, itin: dict[str, Any], segnale: dict[str, Any],
    profilo: dict[str, Any] | None | str = _ASSENTE,
) -> dict[str, Any]:
    corpo: dict[str, Any] = {"itinerary": itin, "signal": segnale}
    if profilo != _ASSENTE:
        corpo["profile"] = profilo
    resp = client.post("/itinerary/adapt", json=corpo)
    assert resp.status_code == 200, resp.text
    out: dict[str, Any] = resp.json()
    return out


def _senza_ts(itin: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in itin.items() if k != "generated_at"}


def _luoghi(itin: dict[str, Any]) -> list[str]:
    return sorted({PLACE_DI[s["experience_id"]] for s in itin["stops"]})


def _minuti_del_giorno(orario: str) -> int:
    ore, minuti, _ = orario.split(":")
    return int(ore) * 60 + int(minuti)


PROFILI_ACCESSIBILI = [
    _profilo(accessibilita_richiesta=True),
    _profilo(accessibilita_richiesta=True, con_bambini=True, curiosita=0.9),
    _profilo(accessibilita_richiesta=True, arte=0.9, contemplazione=0.9, tempo_disponibile_min=90),
    _profilo(accessibilita_richiesta=True, curiosita=0.1, arte=0.1, tempo_disponibile_min=400),
]


def test_retrocompatibilita_senza_profile_e_profile_null(client: TestClient) -> None:
    itin = _componi(client, _profilo())
    segnali = [
        _segnale(meteo="pioggia"),
        _segnale(stanchezza=0.9),
        *[_segnale(affollamento={p: 0.9}) for p in _luoghi(itin)],
    ]
    for sig in segnali:
        senza = _adatta(client, itin, sig)
        nullo = _adatta(client, itin, sig, None)
        assert _senza_ts(senza) == _senza_ts(nullo)


@pytest.mark.parametrize("profilo", PROFILI_ACCESSIBILI)
def test_accessibilita_con_profilo_su_tutti_i_segnali(
    client: TestClient, profilo: dict[str, Any]
) -> None:
    itin = _componi(client, profilo)
    assert all(s["experience_id"] in ACCESSIBILI for s in itin["stops"])
    segnali = {
        "pioggia": _segnale(meteo="pioggia"),
        "stanchezza": _segnale(stanchezza=0.9),
        **{f"affollamento:{p}": _segnale(affollamento={p: 0.95}) for p in _luoghi(itin)},
    }
    for nome, sig in segnali.items():
        out = _adatta(client, itin, sig, profilo)
        for s in out["stops"]:
            assert s["experience_id"] in ACCESSIBILI, (
                f"{nome}: tappa non accessibile {s['experience_id']}"
            )


def test_accessibilita_esaustiva_su_tutti_i_luoghi_del_seed(client: TestClient) -> None:
    """Affollamento di OGNI luogo del seed, uno alla volta, su un itinerario
    accessibile lungo."""
    profilo = _profilo(accessibilita_richiesta=True, tempo_disponibile_min=600)
    itin = _componi(client, profilo)
    for p in sorted({e.place_id for e in ESPERIENZE}):
        out = _adatta(client, itin, _segnale(affollamento={p: 0.95}), profilo)
        assert all(s["experience_id"] in ACCESSIBILI for s in out["stops"]), p


def test_senza_accessibilita_risponde_200_e_filtri_duri(client: TestClient) -> None:
    profilo = _profilo(accessibilita_richiesta=False)
    itin = _componi(client, profilo)
    segnali = [
        _segnale(meteo="pioggia"),
        _segnale(stanchezza=0.9),
        *[_segnale(affollamento={p: 0.95}) for p in _luoghi(itin)],
    ]
    for sig in segnali:
        out = _adatta(client, itin, sig, profilo)
        ids = [s["experience_id"] for s in out["stops"]]
        assert set(ids) <= set(PLACE_DI)
        assert len(ids) == len(set(ids))
        assert all(s["reason"] for s in out["stops"])
        if out["tempo_effettivo_min"] is not None and out["stops"]:
            primo, ultimo = out["stops"][0], out["stops"][-1]
            tot = (
                _minuti_del_giorno(ultimo["arrivo"])
                - _minuti_del_giorno(primo["arrivo"])
                + ultimo["durata_min"]
            )
            assert tot <= out["tempo_effettivo_min"]


# Risposte ESATTE dell'app (onboarding_screen.dart), eccetto `bambini`.
_RISPOSTE_APP = {
    "perdersi": "Sì, mi piace perdermi senza una meta precisa",
    "silenzio_musica": "Silenzio e contemplazione",
    "bellezza_storie": "La bellezza silenziosa dei luoghi",
    "tempo": "Mezza giornata, circa tre ore",
    "accessibilita": "No, nessuna esigenza di accessibilità",
    "firenze": "No, non ho ancora visto Firenze",
}
_BAMBINI_NO = "No, non sono con bambini"
_BAMBINI_SI = "Sì, sono con bambini"


def _profilo_da_app(bambini: str) -> dict[str, Any]:
    req = contracts.OnboardingRequest(
        risposte=[
            contracts.OnboardingAnswer(domanda_id=k, risposta=v)
            for k, v in {**_RISPOSTE_APP, "bambini": bambini}.items()
        ],
        lingua="it",
    )
    out: dict[str, Any] = profile_from_answers(req).model_dump(mode="json")
    return out


def _reasons_compose_e_adapt(client: TestClient, profilo: dict[str, Any]) -> list[str]:
    itin = _componi(client, profilo)
    reasons = [s["reason"] for s in itin["stops"]]
    segnali = [
        _segnale(meteo="pioggia"),
        _segnale(stanchezza=0.9),
        *[_segnale(affollamento={p: 0.95}) for p in _luoghi(itin)],
    ]
    for sig in segnali:
        reasons += [s["reason"] for s in _adatta(client, itin, sig, profilo)["stops"]]
    return reasons


def test_profilo_no_bambini_nessun_reason_con_bambini(client: TestClient) -> None:
    profilo = _profilo_da_app(_BAMBINI_NO)
    assert profilo["con_bambini"] is False
    reasons = _reasons_compose_e_adapt(client, profilo)
    assert reasons
    assert not [r for r in reasons if "bambini" in r.lower()]


def test_profilo_si_bambini_almeno_un_reason_con_bambini(client: TestClient) -> None:
    profilo = _profilo_da_app(_BAMBINI_SI)
    assert profilo["con_bambini"] is True
    reasons = _reasons_compose_e_adapt(client, profilo)
    assert any("bambini" in r.lower() for r in reasons)


def test_il_profilo_arriva_al_motore(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profilo = _profilo(con_bambini=True, curiosita=0.9)
    itin = _componi(client, profilo)
    ids = [s["experience_id"] for s in itin["stops"]]
    if "exp-bici-mura" not in ids:
        pytest.skip(f"exp-bici-mura non nell'itinerario composto: {ids}")
    sig = _segnale(affollamento={"mura-urbane": 0.95})

    visto: list[Any] = []
    originale = api_main.adapt_itinerary

    def spia(*a: Any, **kw: Any) -> Any:
        visto.append(kw.get("profile"))
        return originale(*a, **kw)

    monkeypatch.setattr(api_main, "adapt_itinerary", spia)
    _adatta(client, itin, sig, profilo)
    _adatta(client, itin, sig)
    assert visto[0] is not None, "il profilo non e' arrivato a adapt_itinerary"
    assert visto[0].con_bambini is True
    assert visto[1] is None
