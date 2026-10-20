"""Revisione indipendente degli orari nel grafo (completa `test_orari_grafo.py`).

Aggiunge: file REALE generato (non costruito a mano) con una stringa
malformata iniettata, malformata tra molte esperienze valide, valori non-lista
in `_to_candidate`. Nessuna connessione a Neo4j: driver finto.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from graph import loader
from graph.registro import dataset_attivo, file_seed_cypher
from graph.source import Neo4jCandidateSource

sys.path.insert(0, str(Path(__file__).parent))
from test_orari_grafo import _config, _Driver, _esp_con_orari, _record_da  # noqa: E402

RIGA_VUOTA = "e.orari_apertura = [];"


def _testo_reale() -> str:
    return file_seed_cypher(dataset_attivo()).read_text(encoding="utf-8")


def _fasce_nel_dataset() -> int:
    return sum(len(e.orari_apertura) for e in dataset_attivo().esperienze)


def test_file_reale_generato_e_valido_e_conta_le_fasce_del_dataset() -> None:
    """Il seed versionato valida e le fasce lette sono quelle del dataset
    (alcune esperienze ne hanno, altre no: restano righe vuote)."""
    assert _fasce_nel_dataset() > 0
    assert loader.valida_orari(file_seed_cypher(dataset_attivo())) == _fasce_nel_dataset()
    assert RIGA_VUOTA in _testo_reale()


@pytest.mark.parametrize("posizione", ["prima", "meta", "ultima"])
def test_file_reale_con_una_stringa_malformata_tra_molte_valide_e_rifiutato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, posizione: str
) -> None:
    testo = _testo_reale()
    n = testo.count(RIGA_VUOTA)
    assert n >= 3
    indice = {"prima": 0, "meta": n // 2, "ultima": n - 1}[posizione]
    # Tutte le altre esperienze: una fascia VALIDA; una sola malformata.
    pezzi = testo.split(RIGA_VUOTA)
    out = pezzi[0]
    for k in range(n):
        valore = "'0|08:00|12:00'" if k != indice else "'0|08:00|12:0'"
        out += f"e.orari_apertura = [{valore}];" + pezzi[k + 1]
    f = tmp_path / "seed.cypher"
    f.write_text(out, encoding="utf-8")

    creati: list[str] = []
    registro: list[str] = []

    def finto(*a: object, **k: object) -> _Driver:
        creati.append("driver")
        return _Driver(registro)

    monkeypatch.setattr(loader.GraphDatabase, "driver", finto)
    with pytest.raises(ValueError, match=r"0\|08:00\|12:0'"):
        loader.run(_config(), f)
    assert creati == [] and registro == []


def test_file_reale_con_tutte_le_fasce_valide_conta_e_carica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    testo = _testo_reale()
    n = testo.count(RIGA_VUOTA)
    f = tmp_path / "seed.cypher"
    f.write_text(
        testo.replace(RIGA_VUOTA, "e.orari_apertura = ['1|09:00|18:00', '1|19:00|22:00'];"),
        encoding="utf-8",
    )
    assert loader.valida_orari(f) == 2 * n + _fasce_nel_dataset()
    registro: list[str] = []
    monkeypatch.setattr(loader.GraphDatabase, "driver", lambda *a, **k: _Driver(registro))
    assert loader.run(_config(), f) > 10


@pytest.mark.parametrize(
    "valore",
    [
        "0|08:00|12:00", 5, "", 0, False, {},
        ("0|08:00|12:00",), {"0|08:00|12:00": 1},
    ],
    ids=["stringa", "int", "stringa-vuota", "zero", "false", "dict-vuoto", "tupla", "dict"],
)
def test_to_candidate_non_lista_solleva_valueerror(valore: Any) -> None:
    """Solo `None` vale `[]`; qualunque non-lista solleva ValueError e non
    diventa mai `[]` ("sempre aperto")."""
    with pytest.raises(ValueError):
        Neo4jCandidateSource._to_candidate(_record_da(_esp_con_orari(), valore))  # type: ignore[arg-type]
