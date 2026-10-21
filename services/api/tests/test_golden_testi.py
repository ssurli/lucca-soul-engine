"""Criteri di accettazione sui TESTI del golden di Lucca (ondata 2a, compito 6).

Legge `golden/lucca_itinerari.json` (l'`atteso` congelato, DECIMA modifica autorizzata)
e asserisce proprieta' dei `reason` che il confronto esatto di `test_golden_lucca.py`
non dichiara. Per i casi `demo|` rigioca anche la richiesta sul BFF isolato, per
controllare `titolo` (il golden non lo congela).

Criteri:
- nessun `reason` vuoto;
- nessuna occorrenza di "Evoca il tema" ne' di "è legato a" (le vecchie frasi
  meccaniche), ne' di "exp-" (un id non si mostra mai) in `reason` ne' in `titolo`;
- nessuna frase sull'affollamento senza un valore misurato: "affollat" e' ammesso solo
  se il `Signal` della richiesta ha almeno un `affollamento` (misurato);
- la frase del profilo (i tratti di `rag.reasons._tratto_dominante`) compare al massimo
  UNA volta in ogni itinerario.

Ambito. `demo|` e tutti i `compose` (richiesta e atteso nascono dal codice attuale):
tutti i criteri su ogni tappa. Casi `adapt`: per CONTRATTO le tappe non toccate
(`non_toccata`) conservano il `reason` della richiesta e le mantenute senza alternativa
lo conservano e vi aggiungono una frase; le richieste dei casi `adapt`/`adapt-budget`/
`adapt-profilo` sono VECCHIE (composte prima dell'ondata 2a), quindi quei testi hanno
ancora le frasi meccaniche e il tratto del profilo ripetuto. Su quei casi si asserisce
il contratto (conservazione) e i criteri solo sui testi NUOVI: le tappe `sostituita` e
le `tappe_escluse`. Sui tre `demo|...|pioggia-15`, la cui richiesta e' stata rigenerata
dalla composizione attuale, valgono tutti i criteri su ogni tappa."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from rag.reasons import _tratto_dominante  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

FILE_ITINERARI = Path(__file__).parent / "golden" / "lucca_itinerari.json"
ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
VIETATE = ("Evoca il tema", "è legato a", "exp-")


def _casi() -> dict[str, Any]:
    casi: dict[str, Any] = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return casi


def _chiavi(prefisso: str) -> list[str]:
    return sorted(k for k in _casi() if k.startswith(prefisso))


def _chiavi_compose() -> list[str]:
    return sorted(k for k, c in _casi().items() if c["tipo"] == "compose")


def _chiavi_adapt() -> list[str]:
    return sorted(k for k, c in _casi().items() if c["tipo"] == "adapt")


def _frasi_profilo() -> set[str]:
    """Le frasi che `rag.reasons._tratto_dominante` puo' produrre, ricavate dalla
    funzione stessa su una griglia di profili (nessun elenco duplicato qui)."""
    frasi: set[str] = set()
    valori = (0.0, 0.2, 0.5, 0.8, 1.0)
    for bambini in (False, True):
        for accessibile in (False, True):
            for cur in valori:
                for con in valori:
                    for arte in valori:
                        profilo = contracts.EmotionalProfile(
                            curiosita=cur, contemplazione=con, arte=arte,
                            con_bambini=bambini, accessibilita_richiesta=accessibile,
                            tempo_disponibile_min=240,
                        )
                        frase = _tratto_dominante(profilo)
                        if frase:
                            frasi.add(frase)
    return frasi


def _testi_nuovi(caso: dict[str, Any], tutti: bool) -> list[tuple[str, str]]:
    """(experience_id, reason) da verificare. `tutti`: ogni tappa e tappa esclusa;
    altrimenti solo i testi nuovi di un adattamento (sostituite ed escluse)."""
    atteso = caso["atteso"]
    out = [
        (s["experience_id"], s["reason"])
        for s in atteso["stops"]
        if tutti or s["esito_adattamento"] == "sostituita"
    ]
    out += [(t["experience_id"], t["reason"]) for t in atteso["tappe_escluse"]]
    return out


def _verifica_testi(chiave: str, caso: dict[str, Any], testi: list[tuple[str, str]]) -> None:
    misurato = bool(caso["richiesta"]["signal"].get("affollamento"))
    for exp_id, reason in testi:
        assert reason.strip(), f"{chiave}/{exp_id}: reason vuoto"
        for vietata in VIETATE:
            assert vietata not in reason, f"{chiave}/{exp_id}: contiene {vietata!r}: {reason}"
        if not misurato:
            assert "affollat" not in reason.lower(), (
                f"{chiave}/{exp_id}: frase sull'affollamento senza valore misurato: {reason}"
            )


def _verifica_tratto_una_volta(chiave: str, testi: list[tuple[str, str]]) -> None:
    unito = " ".join(r for _, r in testi).lower()
    for frase in _frasi_profilo():
        n = unito.count(frase.lower())
        assert n <= 1, f"{chiave}: la frase del profilo {frase!r} compare {n} volte"


def test_le_frasi_del_profilo_sono_otto() -> None:
    """Guardia anti-vuoto: il criterio 'una volta sola' guarda 8 frasi reali."""
    assert len(_frasi_profilo()) == 8


def test_la_verifica_dei_testi_scatta() -> None:
    """Doppio negativo: le funzioni di verifica FALLISCONO su testi rotti."""
    caso: dict[str, Any] = {"richiesta": {"signal": {"affollamento": {}}}}
    with pytest.raises(AssertionError):
        _verifica_testi("x", caso, [("exp-a", "Evoca il tema \"Arte\".")])
    with pytest.raises(AssertionError):
        _verifica_testi("x", caso, [("a", "Giacomo Puccini è legato a Casa Puccini.")])
    with pytest.raises(AssertionError):
        _verifica_testi("x", caso, [("a", "In questo momento è meno affollato. Al chiuso.")])
    with pytest.raises(AssertionError):
        _verifica_testi("x", caso, [("a", "  ")])
    with pytest.raises(AssertionError):
        _verifica_testi("x", caso, [("a", "Vedi exp-duomo.")])
    misurato: dict[str, Any] = {"richiesta": {"signal": {"affollamento": {"mura-urbane": 0.9}}}}
    _verifica_testi("x", misurato, [("a", "In questo momento è meno affollato.")])
    frase = next(iter(_frasi_profilo()))
    with pytest.raises(AssertionError):
        _verifica_tratto_una_volta("x", [("a", f"{frase.capitalize()}."), ("b", f"E {frase}.")])
    _verifica_tratto_una_volta("x", [("a", f"{frase.capitalize()}."), ("b", "Al chiuso.")])


def test_casi_attesi_nel_golden() -> None:
    assert len(_chiavi("demo|")) == 10
    assert len(_chiavi_compose()) >= 40
    assert len(_chiavi_adapt()) >= 30


@pytest.mark.parametrize("chiave", _chiavi("demo|"))
def test_demo_criteri_sull_atteso(chiave: str) -> None:
    caso = _casi()[chiave]
    testi = _testi_nuovi(caso, tutti=True)
    assert testi
    # I demo non hanno affollamento misurato: nessuna frase sull'affollamento.
    assert not caso["richiesta"]["signal"].get("affollamento")
    _verifica_testi(chiave, caso, testi)
    _verifica_tratto_una_volta(chiave, testi)


@pytest.mark.parametrize("chiave", _chiavi("demo|"))
def test_demo_richiesta_con_testi_nuovi(chiave: str) -> None:
    """La richiesta (anche l'itinerario da adattare, nei `pioggia-15`) e' stata
    composta dal codice attuale: stessi criteri sui testi dell'itinerario in ingresso."""
    caso = _casi()[chiave]
    if caso["tipo"] != "adapt":
        return
    ingresso = [(s["experience_id"], s["reason"]) for s in caso["richiesta"]["itinerary"]["stops"]]
    _verifica_testi(chiave, caso, ingresso)
    _verifica_tratto_una_volta(chiave, ingresso)


@pytest.mark.parametrize("chiave", _chiavi_compose())
def test_compose_criteri_sull_atteso(chiave: str) -> None:
    caso = _casi()[chiave]
    testi = _testi_nuovi(caso, tutti=True)
    assert testi
    _verifica_testi(chiave, caso, testi)
    _verifica_tratto_una_volta(chiave, testi)


@pytest.mark.parametrize("chiave", _chiavi_adapt())
def test_adapt_testi_nuovi_e_contratto_di_conservazione(chiave: str) -> None:
    caso = _casi()[chiave]
    # Testi NUOVI (sostituite ed escluse): tutti i criteri.
    _verifica_testi(chiave, caso, _testi_nuovi(caso, tutti=False))
    # Contratto: le tappe non toccate conservano il reason della richiesta, le mantenute
    # lo conservano e vi aggiungono una frase.
    richiesta = {s["experience_id"]: s["reason"] for s in caso["richiesta"]["itinerary"]["stops"]}
    for s in caso["atteso"]["stops"]:
        if s["esito_adattamento"] == "non_toccata":
            assert s["reason"] == richiesta[s["experience_id"]], (chiave, s["experience_id"])
        elif s["esito_adattamento"] == "mantenuta_senza_alternativa":
            assert s["reason"].startswith(richiesta[s["experience_id"]]), (
                chiave, s["experience_id"],
            )
            assert len(s["reason"]) > len(richiesta[s["experience_id"]])
        assert s["reason"].strip(), (chiave, s["experience_id"])


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


@pytest.mark.parametrize("chiave", _chiavi("demo|"))
def test_demo_titoli_senza_id(client: TestClient, chiave: str) -> None:
    """Il golden non congela `titolo`: si rigioca la richiesta. Ogni tappa e tappa
    esclusa ha un titolo leggibile, mai un id."""
    caso = _casi()[chiave]
    percorso = "/itinerary" if caso["tipo"] == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=caso["richiesta"])
    assert resp.status_code == 200, resp.text
    risposta = resp.json()
    voci = [*risposta["stops"], *risposta["tappe_escluse"]]
    assert voci
    for v in voci:
        assert v["titolo"] and v["titolo"].strip(), (chiave, v["experience_id"])
        assert "exp-" not in v["titolo"], (chiave, v["titolo"])
        assert "exp-" not in v["reason"], (chiave, v["reason"])
