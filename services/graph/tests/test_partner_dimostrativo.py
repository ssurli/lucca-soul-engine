"""`GraphCandidate.partner_dimostrativo`: parita' tra le due fonti.

Seed (`SeedCandidateSource`) e Neo4j (`Neo4jCandidateSource._to_candidate` su
record simulati con tutte le chiavi della query) valorizzano lo stesso campo,
con la stessa valutazione del suffisso «(esempio dimostrativo)» di
`attribuzione`. Nessuna connessione a Neo4j.
"""

from __future__ import annotations

from typing import Any

import pytest
from graph.seed_lucca import DATASET, ESPERIENZE
from graph.source import Neo4jCandidateSource, SeedCandidateSource

# Riuso dei helper del test di parita' dell'attribuzione (nessuna modifica a quel file).
from test_attribuzione_bottega import _SUFFISSO, _ctx, _record  # noqa: I001

_IDS = [e.id for e in ESPERIENZE]
_CON_PARTNER = {e.id for e in ESPERIENZE if e.partner_id is not None}


def _dal_seed() -> dict[str, Any]:
    return {c.experience.id: c for c in SeedCandidateSource().candidates(_ctx())}


def _da_neo4j(rec: dict[str, Any]) -> Any:
    return Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]


def test_cinque_botteghe_e_le_loro_esperienze() -> None:
    assert len(DATASET.botteghe) == 5
    assert len(_CON_PARTNER) == 5


@pytest.mark.parametrize("esp_id", _IDS)
def test_parita_seed_neo4j_per_ogni_esperienza(esp_id: str) -> None:
    dal_seed = _dal_seed()[esp_id]
    da_neo4j = _da_neo4j(_record(esp_id))
    assert da_neo4j.partner_dimostrativo is dal_seed.partner_dimostrativo


def test_seed_lucca_vero_solo_per_le_esperienze_di_bottega() -> None:
    dal_seed = _dal_seed()
    assert set(dal_seed) == set(_IDS)
    for esp_id, c in dal_seed.items():
        assert c.partner_dimostrativo is (esp_id in _CON_PARTNER), esp_id


@pytest.mark.parametrize("esp_id", _IDS)
def test_coincide_con_il_suffisso_in_attribuzione(esp_id: str) -> None:
    c = _dal_seed()[esp_id]
    assert c.partner_dimostrativo is (_SUFFISSO in (c.attribuzione or "")), esp_id
    n = _da_neo4j(_record(esp_id))
    assert n.partner_dimostrativo is (_SUFFISSO in (n.attribuzione or "")), esp_id


def test_neo4j_bottega_senza_fittizio_e_dimostrativa() -> None:
    rec = _record(
        "exp-laboratorio-liuteria", [{"nome": "Bottega di liuteria", "mestiere": "liuteria"}]
    )
    c = _da_neo4j(rec)
    assert c.partner_dimostrativo is True
    assert _SUFFISSO in (c.attribuzione or "")


def test_neo4j_bottega_fittizio_false_non_e_dimostrativa() -> None:
    rec = _record(
        "exp-laboratorio-liuteria",
        [{"nome": "Bottega Reale", "mestiere": "liuteria", "fittizio": False}],
    )
    c = _da_neo4j(rec)
    assert c.partner_dimostrativo is False
    assert _SUFFISSO not in (c.attribuzione or "")


def test_neo4j_bottega_fittizio_true_e_dimostrativa() -> None:
    rec = _record(
        "exp-laboratorio-liuteria",
        [{"nome": "Bottega X", "mestiere": "liuteria", "fittizio": True}],
    )
    assert _da_neo4j(rec).partner_dimostrativo is True


def test_neo4j_senza_botteghe_non_e_dimostrativa() -> None:
    for botteghe in ([], [{"nome": None, "mestiere": None, "fittizio": True}]):
        c = _da_neo4j(_record("exp-passeggiata-mura", botteghe))
        assert c.partner_dimostrativo is False
        assert c.attribuzione is None
