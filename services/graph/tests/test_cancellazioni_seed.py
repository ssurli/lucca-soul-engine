"""La pulizia `EVOCA` dell'export e la guardia del loader.

Senza Neo4j: si dimostra sul TESTO del seed generato che l'unica
cancellazione e` `(:Esperienza)-[:EVOCA]->(:Tema)` e che il loader rifiuta
ogni altra. L'effetto su un Neo4j reale NON e` eseguito qui.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from graph import loader
from graph.export_cypher import build_seed
from graph.seed_lucca import DATASET

FORMA_ESATTA = re.compile(
    r"MATCH \(e:Esperienza \{id: '(?P<id>(?:[^'\\]|\\.)*)'\}\)-\[r:EVOCA\]->\(t:Tema\) "
    r"WHERE NOT t\.id IN \[(?P<temi>[^\]]*)\] DELETE r;"
)


def _righe_delete(testo: str) -> list[str]:
    return [r for r in testo.splitlines() if not r.startswith("//") and "DELETE" in r]


def test_a_ogni_delete_ha_la_forma_esatta_e_tocca_solo_evoca_esperienza_tema() -> None:
    testo = build_seed(DATASET)
    righe = _righe_delete(testo)
    assert len(righe) == len(DATASET.esperienze)  # una per esperienza
    for riga in righe:
        m = FORMA_ESATTA.fullmatch(riga)
        assert m is not None, riga
    ids = [FORMA_ESATTA.fullmatch(r).group("id") for r in righe]  # type: ignore[union-attr]
    assert ids == [e.id for e in DATASET.esperienze]


def test_la_pulizia_precede_i_merge_evoca_dell_esperienza_e_ne_elenca_i_temi() -> None:
    testo = build_seed(DATASET)
    for e in DATASET.esperienze:
        pulizia = next(r for r in _righe_delete(testo) if f"{{id: '{e.id}'}}" in r)
        atteso = ", ".join(f"'{t}'" for t in e.temi)
        assert f"NOT t.id IN [{atteso}] DELETE r;" in pulizia
        primo_merge = testo.index(f"MATCH (e:Esperienza {{id: '{e.id}'}}), (t:Tema")
        assert testo.index(pulizia) < primo_merge


def test_b_il_seed_non_tocca_memoria_riguarda_evento_detach_remove() -> None:
    testo = build_seed(DATASET)
    senza_commenti = "\n".join(r for r in testo.splitlines() if not r.startswith("//"))
    for vietato in ("Memoria", "RIGUARDA", "Evento", "DETACH", "REMOVE"):
        assert vietato not in senza_commenti, vietato


def test_il_file_versionato_passa_la_guardia() -> None:
    from graph.registro import dataset_attivo, file_seed_cypher

    n = loader.valida_cancellazioni(file_seed_cypher(dataset_attivo()))
    assert n == len(DATASET.esperienze)


@pytest.mark.parametrize(
    "istruzione",
    [
        "MATCH (m:Memoria)-[r:RIGUARDA]->() DELETE r",
        "MATCH (e:Esperienza {id: 'x'}) DETACH DELETE e",
        "MATCH (n) DETACH DELETE n",
        "MATCH (e:Esperienza {id: 'x'})-[r:EVOCA]->(t:Tema) DELETE r",
        "MATCH (e:Esperienza {id: 'x'})-[r]->(t:Tema) WHERE NOT t.id IN ['a'] DELETE r",
        "MATCH (e:Esperienza {id: 'x'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['a'] DELETE t",
        "MATCH (e:Evento {id: 'x'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['a'] DELETE r",
        "MATCH (e:Esperienza {id: 'x'}) REMOVE e.orari_apertura",
        "match (m:Memoria)-[r:RIGUARDA]->() delete r",
        "MATCH (e:Esperienza {id: 'x'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['a'] DELETE r "
        "WITH 1 AS u MATCH (m:Memoria)-[q:RIGUARDA]->() DELETE q",
    ],
)
def test_c_la_guardia_rifiuta_un_seed_manipolato(tmp_path: Path, istruzione: str) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(build_seed(DATASET) + istruzione + ";\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cancellazione non ammessa"):
        loader.valida_cancellazioni(f)


def test_il_loader_rifiuta_prima_di_connettersi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_orari_grafo import _config

    f = tmp_path / "seed.cypher"
    f.write_text(build_seed(DATASET) + "MATCH (n) DETACH DELETE n;\n", encoding="utf-8")
    chiamate: list[str] = []
    monkeypatch.setattr(
        loader.GraphDatabase, "driver", lambda *a, **k: chiamate.append("driver")
    )
    with pytest.raises(ValueError, match="cancellazione non ammessa"):
        loader.run(_config(), f)
    assert chiamate == []


def test_parole_nei_letterali_non_fanno_rifiutare(tmp_path: Path) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(
        "MERGE (e:Esperienza {id: 'x'})\nSET e.titolo = 'Please delete remove detach';\n",
        encoding="utf-8",
    )
    assert loader.valida_cancellazioni(f) == 0
