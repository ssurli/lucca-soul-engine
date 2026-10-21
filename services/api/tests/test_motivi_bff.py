"""Motivi delle tappe attraverso il BFF (ondata 2a, compito 4).

Via HTTP (`POST /itinerary`, `POST /itinerary/adapt`), sullo stesso BFF isolato
di `test_golden_lucca.py` (seed della citta', repository in-memory, nessuna
credenziale, `adesso` fisso). Le richieste sono quelle del golden
(`golden/lucca_itinerari.json`), usate come input:

- ogni `reason` (tappe e tappe escluse) e' non vuoto;
- nei testi composti dal codice attuale nessun residuo del formato vecchio
  ("è legato a", "Evoca il tema", "La bottega evoca"), nessun id `exp-`, e
  nessuna parola sull'affollamento ("affollat") se l'affollamento di quel luogo
  non e' stato misurato nel segnale; nessuna frase sul prezzo ("gratuit",
  decisione del committente per l'ondata 2a);
- la frase del profilo compare al massimo una volta per itinerario e solo
  sulla prima tappa (composizione); al massimo una volta dopo l'adattamento;
- tappe, orari ed esiti (tutto tranne `reason` e `titolo`) sono identici
  all'`atteso` del golden: cambiano solo i testi. Esclusi i 3 casi
  `demo|*|pioggia-15`, il cui itinerario ricevuto e' il vecchio `demo|*|sereno-10`
  e che saranno rigenerati.

Nei casi `adapt` del golden l'itinerario ricevuto porta i `reason` del formato
VECCHIO, e le tappe non toccate li conservano per contratto: per quei casi i
controlli di testo valgono sulle sole tappe SOSTITUITE. La copertura completa
dell'adattamento e' l'andata e ritorno: itinerario composto ORA, poi adattato
con ciascun segnale di adattamento del golden.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import ESPERIENZE  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
PLACE = {e.id: e.place_id for e in ESPERIENZE}

VIETATE = ("è legato a", "Evoca il tema", "La bottega evoca", "exp-")
FRASI_PROFILO = (
    "È pensata anche per chi viaggia con bambini.",
    "Rispetta il bisogno di un percorso accessibile.",
    "Cerchi silenzio e raccoglimento.",
    "Ami i luoghi vivi, con musica e movimento.",
    "Ti lasci conquistare dalla bellezza.",
    "Preferisci le storie che un luogo racconta.",
    "Hai voglia di perderti e lasciarti sorprendere.",
    "Preferisci un percorso chiaro, senza troppe sorprese.",
)
DA_RIGENERARE = {"demo|con-bambini|pioggia-15", "demo|contemplativo|pioggia-15",
                 "demo|curioso|pioggia-15"}


def _casi() -> dict[str, Any]:
    casi: dict[str, Any] = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return casi


def _compose() -> list[str]:
    return sorted(k for k, c in _casi().items() if c["tipo"] == "compose")


def _segnali_adattamento() -> dict[str, dict[str, Any]]:
    """Un segnale per ciascun tipo di adattamento del golden (chiave =
    ultimo segmento della chiave del caso)."""
    out: dict[str, dict[str, Any]] = {}
    for k, c in sorted(_casi().items()):
        if c["tipo"] == "adapt" and k not in DA_RIGENERARE:
            out.setdefault(k.rsplit("|", 1)[1], c["richiesta"]["signal"])
    return out


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato, stesso schema di `test_golden_lucca.py`."""
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


def _post(client: TestClient, tipo: str, corpo: dict[str, Any]) -> dict[str, Any]:
    percorso = "/itinerary" if tipo == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=corpo)
    assert resp.status_code == 200, resp.text
    risposta: dict[str, Any] = resp.json()
    return risposta


def _conta_profilo(reason: str) -> int:
    return sum(reason.count(f) for f in FRASI_PROFILO)


def _errori_testo(voce: dict[str, Any], misurati: set[str]) -> list[str]:
    """Errori del `reason` di una voce composta dal codice attuale."""
    eid = voce["experience_id"]
    reason: str = voce.get("reason") or ""
    errori = [f"{eid}: contiene {v!r}: {reason!r}" for v in VIETATE if v in reason]
    if "affollat" in reason.lower() and PLACE.get(eid) not in misurati:
        errori.append(f"{eid}: parla di affollamento senza valore misurato: {reason!r}")
    if "gratuit" in reason.lower():
        errori.append(f"{eid}: frase sul prezzo: {reason!r}")
    return errori


def _errori_vuoti(risposta: dict[str, Any]) -> list[str]:
    return [
        f"{v['experience_id']}: reason vuoto"
        for v in [*risposta["stops"], *risposta["tappe_escluse"]]
        if not (v.get("reason") or "").strip()
    ]


def _errori_profilo(stops: list[dict[str, Any]], *, solo_prima: bool) -> list[str]:
    errori: list[str] = []
    totale = sum(_conta_profilo(s["reason"]) for s in stops)
    if totale > 1:
        errori.append(f"frase del profilo {totale} volte")
    if solo_prima:
        errori.extend(
            f"frase del profilo sulla tappa {i} ({s['experience_id']})"
            for i, s in enumerate(stops)
            if i > 0 and _conta_profilo(s["reason"])
        )
    return errori


def _errori_risposta_nuova(risposta: dict[str, Any], misurati: set[str]) -> list[str]:
    errori = _errori_vuoti(risposta)
    for voce in [*risposta["stops"], *risposta["tappe_escluse"]]:
        errori.extend(_errori_testo(voce, misurati))
    return errori


# ---------------------------------------------------------------------------
# (3), (4), (1): richieste del golden
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chiave", sorted(_casi()))
def test_motivi_dalle_richieste_del_golden(client: TestClient, chiave: str) -> None:
    caso = _casi()[chiave]
    richiesta = caso["richiesta"]
    risposta = _post(client, caso["tipo"], richiesta)
    misurati = set(richiesta["signal"]["affollamento"])
    assert not _errori_vuoti(risposta), (chiave, _errori_vuoti(risposta))
    if caso["tipo"] == "compose":
        errori = _errori_risposta_nuova(risposta, misurati)
        errori += _errori_profilo(risposta["stops"], solo_prima=True)
        assert risposta["stops"]
    else:
        # Tappe non toccate: `reason` ricevuto (formato vecchio) per contratto.
        errori = [
            e
            for s in risposta["stops"]
            if s["esito_adattamento"] == "sostituita"
            for e in _errori_testo(s, misurati)
        ]
        errori += [
            f"{s['experience_id']}: sostituita con la frase del profilo"
            for s in risposta["stops"]
            if s["esito_adattamento"] == "sostituita" and _conta_profilo(s["reason"])
        ]
    assert not errori, (chiave, errori)


# ---------------------------------------------------------------------------
# (2), (4): andata e ritorno, itinerario composto ORA poi adattato
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chiave", _compose())
def test_motivi_dopo_adattamento_andata_e_ritorno(client: TestClient, chiave: str) -> None:
    richiesta = _casi()[chiave]["richiesta"]
    composto = _post(client, "compose", richiesta)
    misurati_compose = set(richiesta["signal"]["affollamento"])
    for nome, segnale in _segnali_adattamento().items():
        for profilo in (richiesta["profile"], None):
            corpo: dict[str, Any] = {"itinerary": composto, "signal": segnale}
            if profilo is not None:
                corpo["profile"] = profilo
            adattato = _post(client, "adapt", corpo)
            misurati = misurati_compose | set(segnale["affollamento"])
            errori = _errori_risposta_nuova(adattato, misurati)
            errori += _errori_profilo(adattato["stops"], solo_prima=False)
            errori += [
                f"{s['experience_id']}: sostituita con la frase del profilo"
                for s in adattato["stops"]
                if s["esito_adattamento"] == "sostituita" and _conta_profilo(s["reason"])
            ]
            assert not errori, (chiave, nome, profilo is not None, errori)


# ---------------------------------------------------------------------------
# (5): cambiano solo i testi
# ---------------------------------------------------------------------------


def _struttura(itinerario: dict[str, Any]) -> dict[str, Any]:
    """Tutto tranne `reason`, `titolo` e `generated_at`."""
    return {
        "person_id": itinerario["person_id"],
        "adattato_da_segnale": itinerario["adattato_da_segnale"],
        "tempo_disponibile_min": itinerario["tempo_disponibile_min"],
        "tempo_effettivo_min": itinerario["tempo_effettivo_min"],
        "stops": [
            {k: s[k] for k in ("experience_id", "arrivo", "durata_min", "esito_adattamento")}
            for s in itinerario["stops"]
        ],
        "tappe_escluse": [
            {k: t[k] for k in ("experience_id", "esito")} for t in itinerario["tappe_escluse"]
        ],
    }


@pytest.mark.parametrize("chiave", sorted(k for k in _casi() if k not in DA_RIGENERARE))
def test_tappe_orari_esiti_identici_al_golden(client: TestClient, chiave: str) -> None:
    caso = _casi()[chiave]
    risposta = _post(client, caso["tipo"], caso["richiesta"])
    assert _struttura(risposta) == _struttura(caso["atteso"])


def test_casi_esclusi_dal_confronto_sono_solo_i_tre_da_rigenerare() -> None:
    assert len(_casi()) == 91
    assert DA_RIGENERARE <= set(_casi())
    assert len([k for k in _casi() if k not in DA_RIGENERARE]) == 88


def test_le_guardie_scattano() -> None:
    """Doppio negativo: i controlli falliscono su testi rotti."""
    eid = next(iter(PLACE))
    rotta = {"experience_id": eid,
             "reason": "Evoca il tema x. Giacomo è legato a y. exp-a. Meno affollato. "
                       "Al chiuso, gratuita."}
    assert len(_errori_testo(rotta, set())) == 5
    assert len(_errori_testo(rotta, {PLACE[eid]})) == 4
    doppio = [{"experience_id": "a", "reason": FRASI_PROFILO[0]},
              {"experience_id": "b", "reason": FRASI_PROFILO[2]}]
    assert len(_errori_profilo(doppio, solo_prima=True)) == 2
    assert len(_errori_profilo(doppio, solo_prima=False)) == 1
    assert _errori_vuoti({"stops": [{"experience_id": "a", "reason": " "}],
                          "tappe_escluse": []})
