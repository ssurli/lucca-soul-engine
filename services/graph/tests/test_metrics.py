"""Test di `graph.metrics` (Wave 4, Urban Intelligence Index).

Stesso approccio di `tests/test_source.py`: `Neo4jMetricsSource` non è
testabile live in questo ambiente (nessuna istanza Neo4j raggiungibile),
quindi resta coperta da test statici (import, struttura del Protocol, e
verifica che le query versionate esistano e contengano i punti chiave della
logica dichiarata). `SeedMetricsSource` è il percorso principale dei test:
deve produrre ESATTAMENTE gli stessi risultati delle funzioni pure di
`graph.topology` — nessuna seconda fonte di verità, solo una delega.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from graph import topology
from graph.metrics import (
    GRADO_SEMANTICO_QUERY_PATH,
    NON_CONNECTED_PAIRS_QUERY_PATH,
    GraphMetricsSource,
    Neo4jMetricsSource,
    SeedMetricsSource,
)
from graph.seed_lucca import VICINO_EPOCA


def test_seed_metrics_source_implementa_il_protocollo() -> None:
    source: GraphMetricsSource = SeedMetricsSource()
    assert hasattr(source, "grado_semantico")
    assert hasattr(source, "non_connected_place_pairs")


def test_seed_metrics_source_grado_semantico_delega_a_topology() -> None:
    source = SeedMetricsSource()
    assert source.grado_semantico() == topology.grado_semantico()


def test_seed_metrics_source_non_connected_place_pairs_delega_a_topology() -> None:
    source = SeedMetricsSource()
    assert source.non_connected_place_pairs() == topology.non_connected_place_pairs()

    at = datetime.now(UTC)
    assert source.non_connected_place_pairs(at=at) == topology.non_connected_place_pairs(at=at)


def test_seed_metrics_source_rispetta_lepoca_del_seed() -> None:
    source = SeedMetricsSource()
    prima_dellepoca = VICINO_EPOCA - timedelta(days=1)
    _coppie, dimensione = source.non_connected_place_pairs(at=prima_dellepoca)
    _coppie_ora, dimensione_ora = source.non_connected_place_pairs(at=None)
    # Prima dell'epoca convenzionale, nessun arco del seed è "già esistito":
    # lo snapshot deve avere STRETTAMENTE più coppie non connesse di adesso
    # (a meno di un seed patologico senza alcun arco VICINO, escluso da
    # `tests/test_topology.py::test_nessun_nodo_isolato_nella_rete_vicino`).
    assert dimensione > dimensione_ora


# ---------------------------------------------------------------------------
# Neo4jMetricsSource — solo test statici (nessuna istanza Neo4j raggiungibile
# in questo ambiente), stesso approccio di `tests/test_source.py`.
# ---------------------------------------------------------------------------


def test_neo4j_metrics_source_e_importabile_e_implementa_il_protocollo() -> None:
    source: GraphMetricsSource = Neo4jMetricsSource.__new__(Neo4jMetricsSource)
    assert hasattr(source, "grado_semantico")
    assert hasattr(source, "non_connected_place_pairs")


def _query_body(path) -> str:
    """Corpo eseguibile del file `.cypher`, righe di commento (`//`)
    rimosse: gli assert sulla LOGICA della query non devono dipendere dal
    contenuto della prosa esplicativa (che, legittimamente, cita anche i
    tipi di relazione ESCLUSI, per spiegare perché lo sono)."""
    righe = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("//")
    ]
    return "\n".join(righe)


def test_query_grado_semantico_versionata_esiste_ed_e_coerente() -> None:
    assert GRADO_SEMANTICO_QUERY_PATH.exists()
    corpo = _query_body(GRADO_SEMANTICO_QUERY_PATH)
    # Stessa definizione di `graph.topology.grado_semantico`: solo LEGATO_A e
    # SI_SVOLGE_A toccano un Luogo direttamente, OFFRE/EVOCA/ISPIRATA_DA
    # entrano tramite le Botteghe ospitate (place_id).
    for atteso in ("LEGATO_A", "SI_SVOLGE_A", "OFFRE", "EVOCA", "ISPIRATA_DA", "place_id"):
        assert atteso in corpo, f"{atteso!r} atteso nel corpo di {GRADO_SEMANTICO_QUERY_PATH.name}"
    assert "VICINO" not in corpo, (
        "grado_semantico non deve contare VICINO: è il grado respinto dal committente"
    )


def test_query_non_connected_pairs_versionata_esiste_ed_e_coerente() -> None:
    assert NON_CONNECTED_PAIRS_QUERY_PATH.exists()
    corpo = _query_body(NON_CONNECTED_PAIRS_QUERY_PATH)
    assert "VICINO" in corpo
    assert "$at" in corpo
    assert "creato_il" in corpo
    # Nessun cammino semantico: la query deve ragionare solo su VICINO.
    for non_atteso in ("LEGATO_A", "SI_SVOLGE_A", "ISPIRATA_DA"):
        assert non_atteso not in corpo, (
            f"{non_atteso!r} non dovrebbe comparire nel corpo: la connettività di "
            "nuovi_percorsi è solo VICINO, mai un cammino semantico"
        )
