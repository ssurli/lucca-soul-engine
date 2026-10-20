"""`sospesa` attraversa il grafo: export -> cypher -> `Neo4jCandidateSource`.

Nessuna connessione a Neo4j: record finti. Fail-closed come gli orari.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from graph.export_cypher import build_seed
from graph.registro import dataset_attivo, file_seed_cypher
from graph.seed_lucca import DATASET
from graph.source import CANDIDATES_QUERY_PATH, Neo4jCandidateSource

sys.path.insert(0, str(Path(__file__).parent))
from test_orari_grafo import _record_da  # noqa: E402


def _stmt(testo: str, esp_id: str) -> str:
    return next(s for s in testo.split(";\n") if f"{{id: '{esp_id}'}}" in s and "MERGE (e:" in s)


def test_export_scrive_sempre_sospesa() -> None:
    testo = build_seed(DATASET)
    sospese = [e for e in DATASET.esperienze if e.sospesa]
    assert testo.count("e.sospesa = false,") == len(DATASET.esperienze) - len(sospese)
    assert testo.count("e.sospesa = true,") == len(sospese)


def test_export_scrive_true_per_esperienza_sospesa() -> None:
    from dataclasses import replace

    sosp = DATASET.esperienze[0].model_copy(update={"sospesa": True})
    assert not DATASET.esperienze[0].sospesa
    ds = replace(DATASET, esperienze=[sosp, *DATASET.esperienze[1:]])
    testo = build_seed(ds)
    assert "e.sospesa = true," in _stmt(testo, sosp.id)
    gia_sospese = sum(1 for e in DATASET.esperienze if e.sospesa)
    assert testo.count("e.sospesa = true,") == gia_sospese + 1


def test_file_cypher_versionato_coerente_col_seed() -> None:
    assert file_seed_cypher(dataset_attivo()).read_text(encoding="utf-8") == build_seed(DATASET)


def test_query_candidati_restituisce_sospesa() -> None:
    assert "e.sospesa AS sospesa" in CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("grezzo", "atteso"), [(None, False), (True, True), (False, False)]
)
def test_record_valido(grezzo: Any, atteso: bool) -> None:
    rec = _record_da(DATASET.esperienze[0], [])
    rec["sospesa"] = grezzo
    c = Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]
    assert c.experience.sospesa is atteso


@pytest.mark.parametrize("grezzo", ["true", "false", "", 1, 0, [], {}, 1.0])
def test_record_non_booleano_solleva(grezzo: Any) -> None:
    rec = _record_da(DATASET.esperienze[0], [])
    rec["sospesa"] = grezzo
    with pytest.raises(ValueError, match=DATASET.esperienze[0].id):
        Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]


def test_seed_source_preserva_sospesa() -> None:
    sosp = DATASET.esperienze[0].model_copy(update={"sospesa": True})
    assert sosp.model_copy(update={"durata_min": 5}).sospesa is True
