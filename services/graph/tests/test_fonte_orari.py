"""`fonte_orari` attraversa il grafo: seed -> Cypher -> `Neo4jCandidateSource`.

Solo testo, mai nel punteggio. Nessuna connessione a Neo4j: record finti.
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

COMMITTENTE = "dato del committente"

# Tabella attesa esperienza -> fonte (nome come citato nei commenti del seed).
ATTESE: dict[str, str] = {
    "exp-casa-puccini-visita": "Puccini Museum",
    "exp-meccanismo-torre-ore": "sito del Comune di Lucca",
    "exp-museo-barsanti-matteucci": "barsantiematteucci.it, via committente",
    "exp-santi-giovanni-reparata": "museocattedralelucca.it, via committente",
}


def _atteso(esp_id: str) -> str:
    return ATTESE.get(esp_id, COMMITTENTE)


def test_ogni_esperienza_del_seed_ha_fonte_orari_non_vuota() -> None:
    for e in DATASET.esperienze:
        assert e.fonte_orari and e.fonte_orari.strip(), e.id
        assert "\n" not in e.fonte_orari, e.id  # il Cypher si spezza su ";\n"
        assert ";" not in e.fonte_orari, e.id


def test_tabella_esperienza_fonte() -> None:
    reale = {e.id: e.fonte_orari for e in DATASET.esperienze}
    assert reale == {e.id: _atteso(e.id) for e in DATASET.esperienze}
    assert set(ATTESE) <= set(reale)


def test_botteghe_dimostrative_dato_del_committente() -> None:
    for e in DATASET.esperienze:
        if e.partner_id is not None:
            assert e.fonte_orari == COMMITTENTE, e.id


def test_round_trip_cypher() -> None:
    testo = build_seed(DATASET)
    for e in DATASET.esperienze:
        stmt = next(
            s for s in testo.split(";\n") if f"{{id: '{e.id}'}}" in s and "MERGE (e:" in s
        )
        assert f"    e.fonte_orari = '{e.fonte_orari}',\n" in stmt + "\n", e.id
    assert testo.count("e.fonte_orari = ") == len(DATASET.esperienze)
    assert file_seed_cypher(dataset_attivo()).read_text(encoding="utf-8") == testo


def test_fonte_orari_prima_di_orari_apertura() -> None:
    """`orari_apertura` chiude lo statement (il loader lo legge con una regex)."""
    testo = build_seed(DATASET)
    assert testo.count("e.orari_apertura = [") == len(DATASET.esperienze)
    for stmt in testo.split(";\n"):
        if "MERGE (e:Esperienza" in stmt:
            assert stmt.index("e.fonte_orari") < stmt.index("e.orari_apertura")


def test_query_candidati_restituisce_fonte_orari() -> None:
    assert "e.fonte_orari AS fonte_orari" in CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("grezzo", [None, "sito del Comune di Lucca", COMMITTENTE])
def test_mapping_neo4j(grezzo: Any) -> None:
    rec = _record_da(DATASET.esperienze[0], [])
    rec["fonte_orari"] = grezzo
    c = Neo4jCandidateSource._to_candidate(rec)  # type: ignore[arg-type]
    assert c.experience.fonte_orari == grezzo


def test_mapping_neo4j_dal_seed() -> None:
    for e in DATASET.esperienze:
        c = Neo4jCandidateSource._to_candidate(_record_da(e, []))  # type: ignore[arg-type]
        assert c.experience.fonte_orari == e.fonte_orari
