"""Parità degli orari di apertura tra seed, Cypher e `Neo4jCandidateSource`.

L'esperienza con orari usata qui e` DI TEST; negli helper il seed e` privato
dei suoi orari reali, cosi` i conteggi dipendono solo dai dati di test. Nessuna
connessione a Neo4j: il loader è provato con un driver finto che registra le
chiamate.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Any

import pytest
from contracts import ExperienceNode, FasciaApertura, codifica_fasce, decodifica_fasce
from graph import loader
from graph.export_cypher import build_seed
from graph.seed_lucca import DATASET
from graph.source import CANDIDATES_QUERY_PATH, Neo4jCandidateSource

FASCE = [
    FasciaApertura(giorno_settimana=0, apertura=time(8, 30), chiusura=time(12, 0)),
    FasciaApertura(giorno_settimana=0, apertura=time(15, 0), chiusura=time(17, 0)),
    FasciaApertura(giorno_settimana=6, apertura=time(10, 0), chiusura=time(13, 30)),
]


def _esp_con_orari() -> ExperienceNode:
    base = DATASET.esperienze[0]
    return base.model_copy(update={"id": "exp-test-orari", "orari_apertura": FASCE})


def _dataset_con_orari() -> Any:
    from dataclasses import replace

    # Gli orari REALI del seed sono azzerati: qui contano solo le fasce di test.
    senza_orari = [e.model_copy(update={"orari_apertura": []}) for e in DATASET.esperienze]
    return replace(DATASET, esperienze=[*senza_orari, _esp_con_orari()])


def _valori_dal_cypher(testo: str, esp_id: str) -> list[str]:
    stmt = next(s for s in testo.split(";\n") if f"{{id: '{esp_id}'}}" in s and "MERGE (e:" in s)
    riga = next(r for r in stmt.splitlines() if "e.orari_apertura" in r)
    import re

    return re.findall(r"'([^']*)'", riga.split("=", 1)[1])


def _record_da(e: ExperienceNode, orari: Any) -> dict[str, Any]:
    luogo = next(x for x in DATASET.luoghi if x.id == e.place_id)
    return {
        "id": e.id, "titolo": e.titolo, "place_id": e.place_id, "temi": list(e.temi),
        "durata_min": e.durata_min, "al_chiuso": e.al_chiuso, "accessibile": e.accessibile,
        "alimenta_memoria": e.alimenta_memoria, "partner_id": None, "prezzo_eur": None,
        "prenotabile": False, "orari_apertura": orari, "sospesa": None,
        "fonte_orari": e.fonte_orari, "place_nome": luogo.nome,
        "place_articolo": luogo.articolo, "legati_racconti": [], "riferimento_articolo": None,
        "curiosita_testi": [], "curiosita_tipi": [], "curiosita_fonti": [],
        "curiosita_fonti_pubbliche": [],
        "luogo_lat": None, "luogo_lon": None, "punti_arrivo_lat": [], "punti_arrivo_lon": [],
        "artisti_nomi": [], "botteghe": [], "temi_evocati": [], "racconti_ispirazione": [],
        "temi_bottega": [], "distanza_m": None, "riferimento_nome": None,
        "partner_abbonamento_attivo": True,
    }


def test_export_scrive_sempre_la_proprieta_anche_vuota() -> None:
    testo = build_seed(DATASET)
    senza_orari = [e for e in DATASET.esperienze if not e.orari_apertura]
    assert senza_orari, "il seed deve avere anche esperienze senza fasce"
    assert testo.count("e.orari_apertura = [];") == len(senza_orari)


def test_parita_seed_cypher_decodifica_fasce_multiple_stesso_giorno() -> None:
    testo = build_seed(_dataset_con_orari())
    valori = _valori_dal_cypher(testo, "exp-test-orari")
    assert valori == ["0|08:30|12:00", "0|15:00|17:00", "6|10:00|13:30"]
    assert valori == codifica_fasce(FASCE)
    assert decodifica_fasce(valori) == FASCE


def test_to_candidate_decodifica_identico_al_seed() -> None:
    e = _esp_con_orari()
    c = Neo4jCandidateSource._to_candidate(_record_da(e, codifica_fasce(FASCE)))  # type: ignore[arg-type]
    assert c.experience.orari_apertura == FASCE


def test_to_candidate_senza_proprieta_e_lista_vuota() -> None:
    # `coalesce(e.orari_apertura, [])` nella query dà []; None è difensivo.
    for assente in ([], None):
        c = Neo4jCandidateSource._to_candidate(_record_da(_esp_con_orari(), assente))  # type: ignore[arg-type]
        assert c.experience.orari_apertura == []


@pytest.mark.parametrize("guasto", ["0|8:30|12:00", "7|08:00|09:00", "0|12:00|08:00", "boh"])
def test_to_candidate_orario_malformato_solleva(guasto: str) -> None:
    with pytest.raises(ValueError):
        Neo4jCandidateSource._to_candidate(_record_da(_esp_con_orari(), ["0|08:30|12:00", guasto]))  # type: ignore[arg-type]


def test_query_usa_coalesce_sugli_orari() -> None:
    q = CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")
    assert "coalesce(e.orari_apertura, []) AS orari_apertura" in q


# --- loader ---------------------------------------------------------------


class _Sessione:
    def __init__(self, registro: list[str]) -> None:
        self.registro = registro

    def __enter__(self) -> _Sessione:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def run(self, stmt: str, *a: object, **k: object) -> None:
        self.registro.append(stmt)


class _Driver:
    def __init__(self, registro: list[str]) -> None:
        self.registro = registro

    def verify_connectivity(self) -> None:
        self.registro.append("verify")

    def session(self, **k: object) -> _Sessione:
        return _Sessione(self.registro)

    def close(self) -> None:
        self.registro.append("close")


def _config() -> Any:
    from graph.env import Neo4jConfig

    return Neo4jConfig(uri="neo4j+s://finto.invalid", username="u", password="p", database="d")


def test_loader_valida_il_seed_con_orari_validi(tmp_path: Path) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(build_seed(_dataset_con_orari()), encoding="utf-8")
    assert loader.valida_orari(f) == len(FASCE)


def test_loader_rifiuta_orario_malformato_prima_di_ogni_chiamata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    testo = build_seed(_dataset_con_orari()).replace("'0|15:00|17:00'", "'0|15:00|17:0'")
    f = tmp_path / "seed.cypher"
    f.write_text(testo, encoding="utf-8")
    registro: list[str] = []
    creati: list[str] = []

    def finto_driver(*a: object, **k: object) -> _Driver:
        creati.append("driver")
        return _Driver(registro)

    monkeypatch.setattr(loader.GraphDatabase, "driver", finto_driver)
    with pytest.raises(ValueError, match=r"exp-test-orari.*0\|15:00\|17:0"):
        loader.run(_config(), f)
    assert creati == [] and registro == []


def test_loader_rifiuta_forma_non_riconosciuta(tmp_path: Path) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(
        "MERGE (e:Esperienza {id: 'x'})\nSET e.orari_apertura = $param;\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="forma non riconosciuta"):
        loader.valida_orari(f)


def test_loader_con_seed_valido_esegue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(build_seed(_dataset_con_orari()), encoding="utf-8")
    registro: list[str] = []
    monkeypatch.setattr(loader.GraphDatabase, "driver", lambda *a, **k: _Driver(registro))
    assert loader.run(_config(), f) > 10
