"""Attribuzione delle botteghe dimostrative e flag `fittizio` obbligatorio.

(a) `Neo4jCandidateSource._to_candidate` (su un Record finto con tutte le chiavi
della query `10_candidates.cypher`) produce la stessa `attribuzione` di
`SeedCandidateSource`. (b) Nessuna bottega senza flag esplicito.
Nessuna connessione a Neo4j.
"""

from __future__ import annotations

from typing import Any

import pytest
from contracts import EmotionalProfile, Signal, VisitorContext, codifica_fasce  # noqa: I001
from graph import attribuzione as _attribuzione
from graph.dataset import Bottega
from graph.seed_lucca import DATASET, ESPERIENZE
from graph.source import Neo4jCandidateSource, SeedCandidateSource

_SUFFISSO = "(esempio dimostrativo)"
_BOTTEGHE = {b.id: b for b in DATASET.botteghe}


def _ctx() -> VisitorContext:
    from datetime import time

    return VisitorContext(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.5,
            contemplazione=0.5,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=180,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
    )


def _record(esp_id: str, botteghe: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Record con TUTTE le chiavi restituite dalla query, dai dati del seed."""
    e = next(x for x in ESPERIENZE if x.id == esp_id)
    luogo = next(x for x in DATASET.luoghi if x.id == e.place_id)
    if botteghe is None:
        b = _BOTTEGHE[e.partner_id] if e.partner_id else None
        botteghe = (
            [{"nome": b.nome, "mestiere": b.mestiere, "fittizio": b.fittizio}]
            if b
            else [{"nome": None, "mestiere": None, "fittizio": True}]
        )
    return {
        "id": e.id,
        "titolo": e.titolo,
        "place_id": e.place_id,
        "temi": list(e.temi),
        "durata_min": e.durata_min,
        "al_chiuso": e.al_chiuso,
        "accessibile": e.accessibile,
        "alimenta_memoria": e.alimenta_memoria,
        "partner_id": e.partner_id,
        "prezzo_eur": e.prezzo_eur,
        "prenotabile": e.prenotabile,
        "orari_apertura": codifica_fasce(e.orari_apertura),
        "place_nome": luogo.nome,
        "artisti_nomi": [],
        "botteghe": botteghe,
        "temi_evocati": [],
        "racconti_ispirazione": [],
        "temi_bottega": [],
        "distanza_m": None,
        "riferimento_nome": None,
        "partner_abbonamento_attivo": True,
    }


_CON_PARTNER = [e.id for e in ESPERIENZE if e.partner_id is not None]


def test_ci_sono_almeno_due_esperienze_di_partner() -> None:
    assert "exp-laboratorio-liuteria" in _CON_PARTNER
    assert len(_CON_PARTNER) >= 2


@pytest.mark.parametrize("esp_id", _CON_PARTNER)
def test_attribuzione_neo4j_identica_a_quella_del_seed(esp_id: str) -> None:
    dal_seed = next(
        c for c in SeedCandidateSource().candidates(_ctx()) if c.experience.id == esp_id
    )
    da_neo4j = Neo4jCandidateSource._to_candidate(_record(esp_id))  # type: ignore[arg-type]
    assert dal_seed.attribuzione is not None
    assert da_neo4j.attribuzione == dal_seed.attribuzione
    assert _SUFFISSO in da_neo4j.attribuzione


def test_fittizio_assente_nella_entry_implica_disclosure() -> None:
    rec = _record(
        "exp-laboratorio-liuteria",
        [{"nome": "Bottega di liuteria", "mestiere": "liuteria"}],
    )
    cand = Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]
    assert cand.attribuzione == (
        "Offerta da Bottega di liuteria (esempio dimostrativo)."
    )


def test_nessuna_bottega_attribuzione_none() -> None:
    rec = _record("exp-passeggiata-mura")
    assert rec["botteghe"][0]["nome"] is None
    cand = Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]
    assert cand.attribuzione is None


def test_fittizio_false_nessun_suffisso() -> None:
    rec = _record(
        "exp-laboratorio-liuteria",
        [{"nome": "Bottega Reale", "mestiere": "liuteria", "fittizio": False}],
    )
    cand = Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]
    assert cand.attribuzione == "Offerta da Bottega Reale, bottega di liuteria."
    assert "esempio" not in (cand.attribuzione or "")


def test_testo_attribuzione_helper() -> None:
    assert _attribuzione.testo_attribuzione("X", "stampa", True) == (
        "Offerta da X, bottega di stampa (esempio dimostrativo)."
    )
    assert (
        _attribuzione.testo_attribuzione("X", "stampa", False) == "Offerta da X, bottega di stampa."
    )


def test_neo4j_record_di_libreria_se_costruibile() -> None:
    """Se `neo4j.Record` e' costruibile, stesso esito del dict."""
    from neo4j import Record

    rec = _record("exp-laboratorio-liuteria")
    r = Record(zip(rec.keys(), rec.values(), strict=True))
    dal_seed = next(
        c
        for c in SeedCandidateSource().candidates(_ctx())
        if c.experience.id == "exp-laboratorio-liuteria"
    )
    assert Neo4jCandidateSource._to_candidate(r).attribuzione == dal_seed.attribuzione


# --- (b) nessuna bottega senza flag esplicito ------------------------------


def test_bottega_senza_fittizio_solleva_typeerror() -> None:
    with pytest.raises(TypeError):
        Bottega("b", "Bottega", "liuteria", "luogo")  # type: ignore[call-arg]


def test_ogni_bottega_di_lucca_ha_fittizio_bool_e_true() -> None:
    assert len(DATASET.botteghe) == 5
    for b in DATASET.botteghe:
        assert isinstance(b.fittizio, bool), b.id
        assert b.fittizio is True, b.id


def test_nomi_botteghe_solo_mestiere() -> None:
    for b in DATASET.botteghe:
        for vietata in ("lucca", "lucchese", "antica", "storica"):
            assert vietata not in b.nome.lower(), f"{b.id}: {b.nome!r}"
