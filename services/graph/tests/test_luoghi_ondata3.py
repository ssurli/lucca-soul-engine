"""Compito 8 (ondata 3): tre luoghi e tre esperienze nuovi (dato del committente).

Dati esatti, punto dei luoghi, 6 archi VICINO nuovi, nessun LEGATO_A nuovo, Cypher committato
uguale al generato, mapping Neo4j (record finti) uguale al seed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from contracts import TipoCuriosita, distanza_a_piedi_m
from graph.export_cypher import build_seed
from graph.registro import dataset_attivo, file_seed_cypher
from graph.seed_lucca import DATASET, LEGATO_A, VICINO
from graph.source import Neo4jCandidateSource, SeedCandidateSource

sys.path.insert(0, str(Path(__file__).parent))
from test_connessioni_uguali import _ctx  # noqa: E402
from test_orari_grafo import _record_da  # noqa: E402

_LUOGHI = {lg.id: lg for lg in DATASET.luoghi}
_ESP = {e.id: e for e in DATASET.esperienze}
_COMMITTENTE = "dato del committente"

_LUOGHI_ATTESI = {
    "palazzo-bernardini": (
        "Palazzo Bernardini", "il", "palazzo", 43.84257809211349, 10.50566149655655,
    ),
    "san-pietro-somaldi": (
        "Chiesa di San Pietro Somaldi", "la", "chiesa", 43.84555613789234, 10.508002871124265,
    ),
    "parco-giochi-san-donato": (
        "Parco giochi di Porta San Donato", "il", "giardino",
        43.84458794966101, 10.497221545825257,
    ),
}  # fmt: skip

# id -> (titolo, place_id, temi, durata_min)
_ESPERIENZE_ATTESE = {
    "exp-finestra-bernardini": (
        "La finestra storta di Palazzo Bernardini", "palazzo-bernardini", ["storia"], 10,
    ),
    "exp-solchi-san-pietro-somaldi": (
        "I solchi sulla porta di San Pietro Somaldi", "san-pietro-somaldi",
        ["storia", "romanico"], 10,
    ),
    "exp-parco-giochi-san-donato": (
        "Il parco giochi di Porta San Donato", "parco-giochi-san-donato",
        ["con-bambini", "verde"], 45,
    ),
}  # fmt: skip


def test_luoghi_esatti_con_punto() -> None:
    for luogo_id, (nome, articolo, categoria, lat, lon) in _LUOGHI_ATTESI.items():
        luogo = _LUOGHI[luogo_id]
        assert (luogo.nome, luogo.articolo, luogo.categoria) == (nome, articolo, categoria)
        assert luogo.punto is not None and (luogo.punto.lat, luogo.punto.lon) == (lat, lon)


def test_esperienze_esatte() -> None:
    for esp_id, (titolo, place_id, temi, durata) in _ESPERIENZE_ATTESE.items():
        e = _ESP[esp_id]
        assert (e.titolo, e.place_id, e.temi, e.durata_min) == (titolo, place_id, temi, durata)
        assert e.al_chiuso is False
        assert e.accessibile is False
        assert not e.prezzo_eur  # gratuita: come le altre gratuite del seed (omesso)
        assert e.partner_id is None and e.partner_abbonamento_attivo is True
        assert e.orari_apertura == [] and e.punti_arrivo == []
        assert e.sospesa is False and e.prenotabile is False and e.alimenta_memoria is False
        assert e.fonte_orari == _COMMITTENTE


def test_temi_nel_vocabolario_del_seed() -> None:
    temi = {t.id for t in DATASET.temi}
    for e in (_ESP[i] for i in _ESPERIENZE_ATTESE):
        assert set(e.temi) <= temi


def test_conteggi() -> None:
    assert len(DATASET.luoghi) == 24
    assert len(DATASET.esperienze) == 35


def test_curiosita_esatte_nell_ordine() -> None:
    bern = [
        (c.tipo, c.testo, c.fonte, c.fonte_pubblica)
        for c in _LUOGHI["palazzo-bernardini"].curiosita
    ]
    assert bern == [
        (
            TipoCuriosita.FATTO,
            "Guarda la finestra a destra del portone: lo stipite di pietra è curvo, piegato "
            "come se fosse di legno.",
            _COMMITTENTE,
            False,
        ),
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che, per far posto al palazzo dei Bernardini, fu demolita una piccola "
            "chiesa che custodiva un'immagine miracolosa della Madonna, e che a convincere i "
            "committenti fosse stato il diavolo. Tolta la protezione del luogo sacro, il "
            "diavolo avrebbe toccato lo stipite della finestra e l'avrebbe torto come legno "
            "morbido, avvertendo che la pietra non sarebbe mai più tornata dritta.",
            _COMMITTENTE,
            False,
        ),
    ]
    somaldi = [
        (c.tipo, c.testo, c.fonte, c.fonte_pubblica)
        for c in _LUOGHI["san-pietro-somaldi"].curiosita
    ]
    assert somaldi == [
        (
            TipoCuriosita.FATTO,
            "Sulla facciata e sugli stipiti del portale principale si vedono tre solchi "
            "paralleli scavati nella pietra, simili a graffi di artigli.",
            _COMMITTENTE,
            False,
        ),
        (
            TipoCuriosita.LEGGENDA,
            "Si racconta che siano le unghiate del diavolo.",
            _COMMITTENTE,
            False,
        ),
    ]
    assert _LUOGHI["parco-giochi-san-donato"].curiosita == ()


def test_archi_vicino_nuovi_esatti_e_nessun_legato_a_nuovo() -> None:
    """Due archi per luogo nuovo, verso i primi due vicini per distanza a piedi calcolata
    dai punti (`distanza_a_piedi_m`); metri = quelli calcolati."""
    nuovi = set(_LUOGHI_ATTESI)
    attesi = {
        ("palazzo-bernardini", "via-fillungo", 170),
        ("palazzo-bernardini", "torre-delle-ore", 200),
        ("san-pietro-somaldi", "via-del-fosso", 180),
        ("san-pietro-somaldi", "piazza-anfiteatro", 200),
        ("parco-giochi-san-donato", "baluardo-santa-croce", 170),
        ("parco-giochi-san-donato", "casa-puccini", 470),
    }
    reali = [(v.da_id, v.a_id, v.metri) for v in VICINO if {v.da_id, v.a_id} & nuovi]
    assert len(reali) == 6 and set(reali) == attesi
    for da, a, metri in attesi:
        pa, pb = _LUOGHI[da].punto, _LUOGHI[a].punto
        assert pa is not None and pb is not None
        assert distanza_a_piedi_m(pa, pb) == metri
    for luogo in nuovi:
        origine = _LUOGHI[luogo].punto
        assert origine is not None
        propri = sorted(
            (distanza_a_piedi_m(origine, altro.punto), altro.id)
            for altro in DATASET.luoghi
            if altro.id != luogo and altro.punto is not None
        )[:2]
        assert {i for _, i in propri} == {a for da, a, _m in attesi if da == luogo}
    assert not [r for r in LEGATO_A if r.luogo_id in nuovi]


def test_candidati_dal_seed_con_punto_del_luogo_e_curiosita() -> None:
    candidati = {c.experience.id: c for c in SeedCandidateSource(DATASET).candidates(_ctx([]))}
    for esp_id, (_, place_id, _, _) in _ESPERIENZE_ATTESE.items():
        c = candidati[esp_id]
        punto = _LUOGHI[place_id].punto
        assert punto is not None
        assert [(p.lat, p.lon) for p in c.punti_arrivo] == [(punto.lat, punto.lon)]
        assert c.curiosita == list(_LUOGHI[place_id].curiosita)


def test_cypher_committato_uguale_al_generato_e_senza_punto_e_virgola_nei_testi() -> None:
    testo = build_seed(DATASET)
    assert file_seed_cypher(dataset_attivo()).read_text(encoding="utf-8") == testo
    for luogo_id in _LUOGHI_ATTESI:
        stmt = next(s for s in testo.split(";\n") if f"MERGE (l:Luogo {{id: '{luogo_id}'}})" in s)
        luogo = _LUOGHI[luogo_id]
        assert luogo.punto is not None
        assert f"l.lat = {luogo.punto.lat!r}," in stmt
        assert stmt.count("'") >= 2 * len(luogo.curiosita)
    for esp_id in _ESPERIENZE_ATTESE:
        assert any(f"MERGE (e:Esperienza {{id: '{esp_id}'}})" in s for s in testo.split(";\n"))


def test_mapping_neo4j_uguale_al_seed() -> None:
    for esp_id in _ESPERIENZE_ATTESE:
        e = _ESP[esp_id]
        luogo = _LUOGHI[e.place_id]
        record: Any = _record_da(e, [])
        record["curiosita_testi"] = [c.testo for c in luogo.curiosita]
        record["curiosita_tipi"] = [c.tipo.value for c in luogo.curiosita]
        record["curiosita_fonti"] = [c.fonte for c in luogo.curiosita]
        record["curiosita_fonti_pubbliche"] = [c.fonte_pubblica for c in luogo.curiosita]
        c = Neo4jCandidateSource._to_candidate(record)
        assert c.curiosita == list(luogo.curiosita)
        assert c.experience.fonte_orari == _COMMITTENTE
