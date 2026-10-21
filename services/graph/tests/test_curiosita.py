"""Compito 5 (ondata 2a): le curiosità dei luoghi.

Sette curiosità esatte sui luoghi giusti (testi e fonti del committente),
seed e Neo4j (record finti) identici, Cypher committato uguale al generato,
nessuna leggenda che non si presenti come tale. `connessioni` non cambia
(lo prova `test_campi_motivo.py` con l'hash congelato).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

import pytest
from contracts import Curiosita, TipoCuriosita
from graph.dataset import Luogo
from graph.export_cypher import build_seed
from graph.registro import CYPHER_DIR, file_seed_cypher
from graph.seed_lucca import DATASET
from graph.source import Neo4jCandidateSource, SeedCandidateSource

sys.path.insert(0, str(Path(__file__).parent))
from test_connessioni_uguali import _ctx, _record  # noqa: E402

_COMUNE_MAPPA = "Comune di Lucca, Mappa del centro storico 2024"
_COMUNE_MURA = 'Comune di Lucca, cartina "Le Mura di Lucca"'
_COMMITTENTE = "dato del committente"

_ATTESE: dict[str, list[tuple[TipoCuriosita, str, str]]] = {
    "duomo-san-martino": [
        (
            TipoCuriosita.FATTO,
            "Sul pilastro del portico è inciso un labirinto, con un'iscrizione latina che "
            "richiama Dedalo e Teseo. Lo si legge come simbolo del cammino dell'anima verso "
            "la redenzione, lungo la Via Francigena.",
            _COMMITTENTE,
        )
    ],
    "san-michele-in-foro": [
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che nell'anello al dito dell'arcangelo, in cima alla facciata, sia "
            "incastonato un grande smeraldo, visibile al tramonto da un punto preciso della "
            "piazza.",
            _COMUNE_MAPPA,
        )
    ],
    "orto-botanico": [
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che nelle notti di luna piena il fantasma di Lucida Mansi attraversi "
            "le Mura su un cocchio, per poi sparire nel laghetto dell'Orto Botanico.",
            _COMUNE_MURA,
        )
    ],
    "torre-guinigi": [
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che il leccio in cima alla torre perse le foglie quando Paolo "
            "Guinigi fu catturato.",
            _COMMITTENTE,
        )
    ],
    "piazza-anfiteatro": [
        (
            TipoCuriosita.FATTO,
            "Uno solo degli ingressi alla piazza ricalca un'antica porta dell'anfiteatro "
            "romano.",
            _COMMITTENTE,
        )
    ],
    "san-frediano": [
        (
            TipoCuriosita.FATTO,
            "Nel mosaico della facciata compare anche Giuda, che l'iconografia classica non "
            "metterebbe in questa scena. Alza la mano destra chiusa, con indice e mignolo "
            "tesi: il racconto popolare ci vede il gesto delle corna.",
            _COMMITTENTE,
        )
    ],
    "baluardo-san-paolino": [
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che il 12 luglio 1664, festa di San Paolino, i cannoni delle Mura "
            "spararono per i festeggiamenti senza essere caricati a salve, e che solo "
            "l'intervento miracoloso del santo salvò la folla radunata sotto le Mura.",
            _COMUNE_MURA,
        )
    ],
}


def test_sette_curiosita_esatte_sui_luoghi_giusti() -> None:
    trovate = {
        luogo.id: [(c.tipo, c.testo, c.fonte) for c in luogo.curiosita]
        for luogo in DATASET.luoghi
        if luogo.curiosita
    }
    assert trovate == _ATTESE
    assert sum(len(v) for v in trovate.values()) == 7


def test_tipi_e_fonti() -> None:
    tutte = [c for luogo in DATASET.luoghi for c in luogo.curiosita]
    assert sum(c.tipo == TipoCuriosita.LEGGENDA for c in tutte) == 4
    assert sum(c.tipo == TipoCuriosita.FATTO for c in tutte) == 3
    assert all(c.fonte.strip() for c in tutte)


def test_ogni_leggenda_inizia_con_si_racconta() -> None:
    leggende = [
        c for luogo in DATASET.luoghi for c in luogo.curiosita if c.tipo == TipoCuriosita.LEGGENDA
    ]
    assert leggende
    assert all(c.testo.startswith("Si racconta") for c in leggende)


def test_curiosita_con_a_capo_solleva() -> None:
    voce = Curiosita(testo="Uno;\nDue", tipo=TipoCuriosita.FATTO, fonte="f")
    with pytest.raises(ValueError, match="a-capo"):
        Luogo("x", "Posto", "piazza", curiosita=(voce,))
    voce = Curiosita(testo="Uno", tipo=TipoCuriosita.FATTO, fonte="f\ng")
    with pytest.raises(ValueError, match="a-capo"):
        Luogo("x", "Posto", "piazza", curiosita=(voce,))


def test_luogo_senza_curiosita_per_default() -> None:
    assert Luogo("x", "Posto", "piazza").curiosita == ()


def test_seed_porta_le_curiosita_del_luogo_su_ogni_esperienza() -> None:
    per_luogo = {luogo.id: list(luogo.curiosita) for luogo in DATASET.luoghi}
    candidati = SeedCandidateSource(DATASET).candidates(_ctx([]))
    for c in candidati:
        assert c.curiosita == per_luogo[c.experience.place_id], c.experience.id
    assert {c.experience.place_id for c in candidati if c.curiosita} == set(_ATTESE)


@pytest.mark.parametrize("visto", [None, "casa-puccini", "mura-urbane"])
def test_seed_uguale_a_neo4j(visto: str | None) -> None:
    rng = random.Random(7)
    seed = {
        c.experience.id: c
        for c in SeedCandidateSource(DATASET).candidates(_ctx([visto] if visto else []))
    }
    for esp_id, atteso in seed.items():
        record: Any = _record(esp_id, visto, rng)
        da_neo4j = Neo4jCandidateSource._to_candidate(record, visto)
        assert da_neo4j.curiosita == atteso.curiosita, esp_id


def _record_con(extra: dict[str, Any]) -> Any:
    esp = next(e.id for e in DATASET.esperienze if e.place_id == "torre-guinigi")
    return {**_record(esp, None, random.Random(1)), **extra}


def test_neo4j_proprieta_assenti_sono_nessuna_curiosita() -> None:
    record = _record_con({"curiosita_testi": None, "curiosita_tipi": None, "curiosita_fonti": None})
    assert Neo4jCandidateSource._to_candidate(record).curiosita == []


def test_neo4j_liste_di_lunghezza_diversa_solleva() -> None:
    with pytest.raises(ValueError, match="lunghezza"):
        Neo4jCandidateSource._to_candidate(_record_con({"curiosita_tipi": []}))


def test_neo4j_leggenda_senza_si_racconta_solleva() -> None:
    record = _record_con({"curiosita_testi": ["Il leccio perse le foglie."]})
    with pytest.raises(ValueError, match="Si racconta"):
        Neo4jCandidateSource._to_candidate(record)


def test_cypher_committato_uguale_al_generato() -> None:
    assert file_seed_cypher(DATASET).read_text(encoding="utf-8") == build_seed(DATASET)


def test_cypher_scrive_liste_parallele_con_set_anche_vuote() -> None:
    testo = build_seed(DATASET)
    # Un solo statement per luogo (il loader spezza su ";\n"), sempre con le tre liste.
    luoghi = [st for st in testo.split(";\n") if "MERGE (l:Luogo" in st]
    assert len(luoghi) == len(DATASET.luoghi)
    assert all("l.curiosita_testi = [" in st and "l.curiosita_fonti = [" in st for st in luoghi)
    vuote = "l.curiosita_testi = [],\n    l.curiosita_tipi = [],\n    l.curiosita_fonti = []"
    assert vuote in testo
    # Escape di apostrofi; le virgolette doppie restano intatte.
    assert "un\\'iscrizione latina" in testo
    assert "'Comune di Lucca, cartina \"Le Mura di Lucca\"'" in testo


def test_query_candidati_restituisce_le_curiosita() -> None:
    q = (CYPHER_DIR / "10_candidates.cypher").read_text(encoding="utf-8")
    for campo in ("curiosita_testi", "curiosita_tipi", "curiosita_fonti"):
        assert f"coalesce(l.{campo}, []) AS {campo}" in q
