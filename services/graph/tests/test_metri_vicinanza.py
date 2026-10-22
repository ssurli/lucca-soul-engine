"""Metri della frase "A … m da …, già visitato" dai punti (ondata 3, compito 4).

Condizione INVARIATA (decisione del committente: archi e metri VICINO non si
toccano): la frase c'è solo se esiste l'arco VICINO tra il luogo e quello già
visitato. Cambiano i METRI: `distanza_a_piedi_m(punto del riferimento,
punto_piu_vicino(punto del riferimento, cand.punti_arrivo))`, la stessa stima
che il motore usa per il trasferimento. Se il riferimento (es. `mura-urbane`)
o il candidato (bottega dimostrativa) non hanno un punto, restano i metri
dell'arco VICINO. Stessa regola per seed e Neo4j (`graph.source.metri_vicinanza`).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

import pytest
from contracts import GraphCandidate, Punto, distanza_a_piedi_m, distanza_linea_aria_m
from graph.registro import CYPHER_DIR
from graph.seed_lucca import DATASET
from graph.source import Neo4jCandidateSource, SeedCandidateSource, metri_vicinanza

sys.path.insert(0, str(Path(__file__).parent))
from test_connessioni_uguali import _ctx, _record  # noqa: E402

_LUOGHI = {lg.id: lg for lg in DATASET.luoghi}


def _punto(place_id: str) -> Punto:
    punto = _LUOGHI[place_id].punto
    assert punto is not None, place_id
    return punto


def _metri_vicino(a: str, b: str) -> int:
    return min(v.metri for v in DATASET.vicino if {v.da_id, v.a_id} == {a, b})


def _candidati(visto: str) -> dict[str, GraphCandidate]:
    return {c.experience.id: c for c in SeedCandidateSource().candidates(_ctx([visto]))}


def test_duomo_san_michele_470_m_a_piedi_al_posto_dei_300_dell_arco() -> None:
    assert _metri_vicino("duomo-san-martino", "san-michele-in-foro") == 300
    c = SeedCandidateSource().candidates(_ctx(["duomo-san-martino"]))
    facciata = next(x for x in c if x.experience.id == "exp-facciata-san-michele")
    assert facciata.distanza_m == 470
    assert facciata.connessioni[-1] == "A 470 m da Duomo di San Martino, già visitato."
    assert facciata.vicinanza_nome == "Duomo di San Martino"


def test_candidato_con_piu_punti_usa_il_piu_vicino_al_riferimento() -> None:
    rif = _punto("casa-puccini")
    c = next(
        x
        for x in SeedCandidateSource().candidates(_ctx(["casa-puccini"]))
        if x.experience.id == "exp-passeggiata-mura"
    )
    assert len(c.punti_arrivo) == 6
    vicino = min(c.punti_arrivo, key=lambda p: distanza_linea_aria_m(rif, p))
    assert vicino != c.punti_arrivo[0]  # non e' semplicemente il primo
    assert c.distanza_m == distanza_a_piedi_m(rif, vicino)
    assert c.connessioni[-1].startswith(f"A {c.distanza_m} m da ")


def test_riferimento_senza_punto_resta_il_metro_vicino() -> None:
    """`mura-urbane` non ha un punto (ha solo le rampe delle esperienze)."""
    assert _LUOGHI["mura-urbane"].punto is None
    visti = 0
    for c in SeedCandidateSource().candidates(_ctx(["mura-urbane"])):
        if c.vicinanza_nome is None:
            continue
        visti += 1
        assert c.distanza_m == _metri_vicino(c.experience.place_id, "mura-urbane")
        assert c.connessioni[-1].startswith(f"A {c.distanza_m} m da ")
    assert visti > 0


def test_bottega_dimostrativa_senza_punti_resta_il_metro_vicino() -> None:
    c = next(
        x
        for x in SeedCandidateSource().candidates(_ctx(["duomo-san-martino"]))
        if x.experience.id == "exp-laboratorio-liuteria"
    )
    assert c.punti_arrivo == []
    assert c.distanza_m == _metri_vicino("san-michele-in-foro", "duomo-san-martino") == 300


def test_senza_arco_vicino_nessuna_frase_e_distanza_come_prima() -> None:
    """Condizione invariata: nessun arco VICINO -> nessuna frase, `distanza_m`
    None; sul luogo stesso 0."""
    for c in SeedCandidateSource().candidates(_ctx(["duomo-san-martino"])):
        pid = c.experience.place_id
        if pid == "duomo-san-martino":
            assert c.distanza_m == 0 and c.vicinanza_nome is None
        elif not any({v.da_id, v.a_id} == {pid, "duomo-san-martino"} for v in DATASET.vicino):
            assert c.distanza_m is None and c.vicinanza_nome is None
            assert not any(f.endswith("già visitato.") for f in c.connessioni)


def test_regola_pura() -> None:
    a = Punto(lat=43.84, lon=10.50)
    b = Punto(lat=43.845, lon=10.50)
    assert metri_vicinanza(999, None, [a]) == 999
    assert metri_vicinanza(999, a, []) == 999
    assert metri_vicinanza(999, a, [b, a]) == 0
    assert metri_vicinanza(999, a, [b]) == distanza_a_piedi_m(a, b)


@pytest.mark.parametrize("visto", [lg.id for lg in DATASET.luoghi])
def test_neo4j_stessi_metri_del_seed(visto: str) -> None:
    rng = random.Random(7)
    for esp_id, atteso in _candidati(visto).items():
        record: Any = _record(esp_id, visto, rng)
        da_neo4j = Neo4jCandidateSource._to_candidate(record, visto)
        if atteso.experience.place_id == visto:
            # Divergenza PREESISTENTE, non di questo compito: sul luogo stesso il
            # seed da' 0, la query (nessun VICINO con se stesso) null.
            assert da_neo4j.distanza_m is None and atteso.distanza_m == 0, esp_id
        else:
            assert da_neo4j.distanza_m == atteso.distanza_m, esp_id
        assert da_neo4j.connessioni == atteso.connessioni, esp_id


def test_query_candidati_porta_il_punto_del_riferimento() -> None:
    q = (CYPHER_DIR / "10_candidates.cypher").read_text(encoding="utf-8")
    assert "min(rif.lat) AS riferimento_lat" in q
    assert "min(rif.lon) AS riferimento_lon" in q
    ritorno = q.split("RETURN", 1)[1]
    assert "riferimento_lat," in ritorno and "riferimento_lon," in ritorno
