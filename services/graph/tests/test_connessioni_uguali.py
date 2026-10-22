"""Le due sorgenti producono le STESSE `connessioni`, nello stesso ordine.

`Neo4jCandidateSource._to_candidate` riceve un Record finto costruito dai dati
del seed come lo restituirebbe `10_candidates.cypher`, ma con le liste dei
`collect` in ordine MESCOLATO (la query non garantisce alcun ordine): l'ordine
canonico lo impone `graph.connessioni`. Nessuna connessione a Neo4j.
"""

from __future__ import annotations

import random
from datetime import time
from typing import Any

import pytest
from contracts import EmotionalProfile, Signal, VisitorContext, codifica_fasce
from graph.connessioni import frasi_connessioni
from graph.seed_lucca import DATASET, ESPERIENZE
from graph.source import Neo4jCandidateSource, SeedCandidateSource

_LUOGHI = {x.id: x for x in DATASET.luoghi}
_ARTISTI = {x.id: x for x in DATASET.artisti}
_TEMI = {x.id: x for x in DATASET.temi}
_BOTTEGHE = {x.id: x for x in DATASET.botteghe}


def _ctx(luoghi_gia_visti: list[str]) -> VisitorContext:
    return VisitorContext(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.5,
            contemplazione=0.5,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=180,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
        luoghi_gia_visti=luoghi_gia_visti,
    )


def _mescola[T](voci: list[T], rng: random.Random) -> list[T]:
    voci = list(voci)
    rng.shuffle(voci)
    return voci


def _record(esp_id: str, vicino_a: str | None, rng: random.Random) -> dict[str, Any]:
    """Il Record come lo restituirebbe la query, liste in ordine casuale."""
    e = next(x for x in ESPERIENZE if x.id == esp_id)
    luogo = _LUOGHI[e.place_id]
    artisti = [_ARTISTI[r.artista_id].nome for r in DATASET.legato_a if r.luogo_id == luogo.id]
    bottega = _BOTTEGHE[e.partner_id] if e.partner_id else None
    legati_racconti = [
        {"nome": _ARTISTI[r.artista_id].nome, "racconto": r.racconto, "fonte": r.fonte}
        for r in DATASET.legato_a
        if r.luogo_id == luogo.id
    ]
    racconti = [
        {"artista_id": r.artista_id, "racconto": r.racconto}
        for r in DATASET.bottega_ispirata_da
        if bottega and r.bottega_id == bottega.id
    ]
    temi_bottega = [
        {"id": r.tema_id, "nome": _TEMI[r.tema_id].nome}
        for r in DATASET.bottega_evoca
        if bottega and r.bottega_id == bottega.id
    ]
    metri = None
    nome_rif = None
    articolo_rif = None
    # Punto del luogo `$vicino_a`, null senza arco VICINO (come `riferimento_nome`).
    lat_rif = None
    lon_rif = None
    if vicino_a is not None:
        metri_v = [
            v.metri
            for v in DATASET.vicino
            if {v.da_id, v.a_id} == {luogo.id, vicino_a} and luogo.id != vicino_a
        ]
        if metri_v:
            metri = min(metri_v)
            nome_rif = _LUOGHI[vicino_a].nome
            articolo_rif = _LUOGHI[vicino_a].articolo
            punto_rif = _LUOGHI[vicino_a].punto
            lat_rif = punto_rif.lat if punto_rif else None
            lon_rif = punto_rif.lon if punto_rif else None
    return {
        "id": e.id,
        "titolo": e.titolo,
        "place_id": e.place_id,
        "temi": list(e.temi),
        "durata_min": e.durata_min,
        "al_chiuso": e.al_chiuso,
        "accessibile": e.accessibile,
        "alimenta_memoria": e.alimenta_memoria,
        "partner_id": e.partner_id,
        "prezzo_eur": e.prezzo_eur,
        "prenotabile": e.prenotabile,
        "orari_apertura": codifica_fasce(e.orari_apertura),
        "sospesa": e.sospesa,
        "place_nome": luogo.nome,
        "place_articolo": luogo.articolo,
        "curiosita_testi": [c.testo for c in luogo.curiosita],
        "curiosita_tipi": [c.tipo.value for c in luogo.curiosita],
        "curiosita_fonti": [c.fonte for c in luogo.curiosita],
        "luogo_lat": luogo.punto.lat if luogo.punto else None,
        "luogo_lon": luogo.punto.lon if luogo.punto else None,
        "punti_arrivo_lat": [p.lat for p in e.punti_arrivo],
        "punti_arrivo_lon": [p.lon for p in e.punti_arrivo],
        "artisti_nomi": _mescola(artisti, rng),
        "legati_racconti": _mescola(legati_racconti, rng),
        "botteghe": (
            [{"nome": bottega.nome, "mestiere": bottega.mestiere, "fittizio": bottega.fittizio}]
            if bottega
            else [{"nome": None, "mestiere": None, "fittizio": True}]
        ),
        "temi_evocati": _mescola(
            [
                {
                    "id": t,
                    "nome": _TEMI[t].nome,
                    "etichetta": _TEMI[t].etichetta,
                    "mostra_etichetta": _TEMI[t].mostra_etichetta,
                    "frase": _TEMI[t].frase,
                    "fonte": _TEMI[t].fonte,
                }
                for t in e.temi
                if t in _TEMI
            ],
            rng,
        ),
        "racconti_ispirazione": _mescola(racconti, rng),
        "temi_bottega": _mescola(temi_bottega, rng),
        "distanza_m": metri,
        "riferimento_nome": nome_rif,
        "riferimento_articolo": articolo_rif,
        "riferimento_lat": lat_rif,
        "riferimento_lon": lon_rif,
        "partner_abbonamento_attivo": True,
    }


_SCENARI: list[list[str]] = [[]] + [[luogo.id] for luogo in DATASET.luoghi]


@pytest.mark.parametrize("seed_casuale", [0, 1, 2, 3])
@pytest.mark.parametrize("visti", _SCENARI, ids=lambda v: v[0] if v else "senza-visti")
def test_connessioni_identiche_tra_seed_e_neo4j(visti: list[str], seed_casuale: int) -> None:
    rng = random.Random(seed_casuale)
    vicino_a = visti[-1] if visti else None
    dal_seed = {c.experience.id: c for c in SeedCandidateSource().candidates(_ctx(visti))}
    assert set(dal_seed) == {e.id for e in ESPERIENZE}
    for esp_id, atteso in dal_seed.items():
        record = _record(esp_id, vicino_a, rng)
        da_neo4j = Neo4jCandidateSource._to_candidate(record, vicino_a)  # type: ignore[arg-type]
        assert da_neo4j.connessioni == atteso.connessioni, esp_id
        assert da_neo4j.attribuzione == atteso.attribuzione, esp_id
        # Campi di solo testo per il motivo (compito 4): identici tra le sorgenti.
        assert da_neo4j.place_articolo == atteso.place_articolo, esp_id
        assert da_neo4j.racconti == atteso.racconti, esp_id
        assert da_neo4j.temi_etichette == atteso.temi_etichette, esp_id
        assert da_neo4j.vicinanza_nome == atteso.vicinanza_nome, esp_id
        assert da_neo4j.vicinanza_articolo == atteso.vicinanza_articolo, esp_id


def test_gia_visitato_compare_su_entrambe_e_per_ultimo() -> None:
    visti = ["mura-urbane"]
    rng = random.Random(0)
    visto_almeno_una_volta = False
    for c in SeedCandidateSource().candidates(_ctx(visti)):
        n = Neo4jCandidateSource._to_candidate(  # type: ignore[arg-type]
            _record(c.experience.id, "mura-urbane", rng), "mura-urbane"
        )
        gia = [f for f in n.connessioni if f.endswith("già visitato.")]
        assert gia == [f for f in c.connessioni if f.endswith("già visitato.")]
        if gia:
            visto_almeno_una_volta = True
            assert n.connessioni[-1] == gia[0]
    assert visto_almeno_una_volta


def test_nessun_gia_visitato_se_il_luogo_e_il_riferimento() -> None:
    for c in SeedCandidateSource().candidates(_ctx(["teatro-del-giglio"])):
        if c.experience.place_id == "teatro-del-giglio":
            assert not any("già visitato" in f for f in c.connessioni)


def test_ordine_canonico_dell_helper_indipendente_dall_input() -> None:
    kw: dict[str, Any] = {
        "luogo_nome": "Luogo",
        "temi_esperienza": ["t2", "t1"],
        "nomi_temi": {"t1": "Uno", "t2": "Due"},
        "riferimento": (120, "Altrove"),
    }
    a = frasi_connessioni(
        artisti_nomi=["beta", "Alfa", "Zeta"],
        racconti_ispirazione=[("b", "RB"), ("a", "RA")],
        temi_bottega=[("t9", "Nove"), ("t1", "Uno"), ("t5", "Cinque")],
        **kw,
    )
    b = frasi_connessioni(
        artisti_nomi=["Zeta", "Alfa", "beta"],
        racconti_ispirazione=[("a", "RA"), ("b", "RB")],
        temi_bottega=[("t5", "Cinque"), ("t9", "Nove"), ("t1", "Uno")],
        **kw,
    )
    assert a == b
    assert a == [
        "Alfa è legato a Luogo.",
        "beta è legato a Luogo.",
        "Zeta è legato a Luogo.",
        'Evoca il tema "Due".',
        'Evoca il tema "Uno".',
        "RA",
        "RB",
        'La bottega evoca anche il tema "Cinque".',
        'La bottega evoca anche il tema "Nove".',
        "A 120 m da Altrove, già visitato.",
    ]


def test_seed_giglio_catalani_prima_di_puccini() -> None:
    giglio = next(
        c
        for c in SeedCandidateSource().candidates(_ctx([]))
        if c.experience.id == "exp-concerto-giglio"
    )
    assert giglio.connessioni[0] == "Alfredo Catalani è legato a Teatro del Giglio."


def test_attribuzione_neo4j_sceglie_la_bottega_dal_nome_minore() -> None:
    """Piu' botteghe nel `collect` (ordine non garantito): vince sempre il
    nome minore (casefold, poi nome), qualunque sia l'ordine di arrivo."""
    esp = next(e for e in ESPERIENZE if e.partner_id)
    botteghe = [
        {"nome": "zeta Liuteria", "mestiere": "liutaio", "fittizio": True},
        {"nome": "Alfa Liuteria", "mestiere": "liutaio", "fittizio": False},
        {"nome": "beta Liuteria", "mestiere": "liutaio", "fittizio": True},
    ]
    atteso = "Offerta da Alfa Liuteria, bottega di liutaio."
    rng = random.Random(7)
    for _ in range(12):
        record = _record(esp.id, None, rng)
        record["botteghe"] = _mescola(botteghe, rng)
        assert Neo4jCandidateSource._to_candidate(record, None).attribuzione == atteso  # type: ignore[arg-type]
