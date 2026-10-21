"""Compito 4 (ondata 2a): i campi di SOLO TESTO per il motivo.

`articolo`, `etichetta`, `frase`/`fonte` dei temi, `racconto`/`fonte` dei
LEGATO_A. Garanzie: validazione a import (testo solo con fonte), dati di Lucca
esatti, `connessioni` INVARIATE (alimentano lo score), nessuna frase "da
catalogo" nei campi nuovi, Cypher generato coerente col dataset.
"""

from __future__ import annotations

import hashlib
import json
from datetime import time

import pytest
from contracts import ARTICOLI, EmotionalProfile, Signal, VisitorContext
from graph.dataset import Luogo, RelazioneLegatoA, Tema
from graph.export_cypher import build_schema, build_seed
from graph.registro import CYPHER_DIR, file_seed_cypher
from graph.seed_lucca import DATASET
from graph.source import SeedCandidateSource

_FONTE_PUCCINI = 'italia.it, pagina "San Michele in Foro"'
_FONTE_BOCCHERINI = (
    'Ministero della Cultura, "Profilo Boccherini"; '
    'Puccini Museum, pagina "Cattedrale di S. Martino"'
)
_RACCONTO_PUCCINI = (
    "In questa chiesa il giovane Giacomo Puccini dava lezioni d'organo al suo unico allievo, "
    "il sarto Carlo Della Nina; per la festa di San Michele vi si suonano ancora musiche "
    "della famiglia Puccini."
)
_RACCONTO_BOCCHERINI = (
    "Nel 1751, a otto anni, Luigi Boccherini debuttò come voce bianca nelle feste di "
    "Santa Croce, celebrate in questa cattedrale."
)

# sha256 di {visti: {esperienza: [connessioni, distanza_m]}} calcolato sul codice
# PRIMA del compito 4, per [] e per ogni luogo come unico "già visitato".
_HASH_CONNESSIONI_A_HEAD = "c01d8229230616a906c874886458950842cc989dd85a5e875c44fc2565391cd9"


def _ctx(visti: list[str]) -> VisitorContext:
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
        luoghi_gia_visti=visti,
    )


# --- validazione del dataset -------------------------------------------------


def test_articolo_non_valido_solleva() -> None:
    with pytest.raises(ValueError, match="articolo"):
        Luogo("x", "Posto", "piazza", articolo="un")


@pytest.mark.parametrize("articolo", [None, *ARTICOLI])
def test_articoli_ammessi(articolo: str | None) -> None:
    assert Luogo("x", "Posto", "piazza", articolo=articolo).articolo == articolo


def test_racconto_senza_fonte_solleva() -> None:
    with pytest.raises(ValueError, match="insieme"):
        RelazioneLegatoA("a", "l", racconto="Una storia.")
    with pytest.raises(ValueError, match="insieme"):
        RelazioneLegatoA("a", "l", racconto="Una storia.", fonte="   ")


def test_fonte_senza_racconto_solleva() -> None:
    with pytest.raises(ValueError, match="insieme"):
        RelazioneLegatoA("a", "l", fonte="Una fonte")


def test_frase_tema_senza_fonte_o_viceversa_solleva() -> None:
    with pytest.raises(ValueError, match="insieme"):
        Tema("t", "Tema", frase="Una frase.")
    with pytest.raises(ValueError, match="insieme"):
        Tema("t", "Tema", fonte="Una fonte")
    assert Tema("t", "Tema", frase="Una frase.", fonte="Una fonte").frase == "Una frase."


def test_testo_su_piu_righe_solleva() -> None:
    """Il loader spezza il Cypher su ';\\n': niente a-capo nei testi."""
    with pytest.raises(ValueError, match="a-capo"):
        RelazioneLegatoA("a", "l", racconto="Uno;\nDue", fonte="f")


def test_etichetta_di_default_e_il_nome_con_iniziale_minuscola() -> None:
    assert Tema("t", "Quiete del borgo").etichetta == "quiete del borgo"
    assert Tema("t", "Quiete", etichetta="silenzio").etichetta == "silenzio"


# --- dati di Lucca -----------------------------------------------------------


def test_articoli_di_lucca() -> None:
    atteso = {
        "mura-urbane": "le", "piazza-anfiteatro": "la", "torre-guinigi": "la",
        "duomo-san-martino": "il", "casa-puccini": "la", "san-michele-in-foro": "la",
        "orto-botanico": "l'", "teatro-del-giglio": "il", "palazzo-pfanner": "il",
        "san-frediano": "la", "torre-delle-ore": "la", "piazza-napoleone": "la",
        "via-fillungo": None, "baluardo-san-paolino": "il", "museo-nazionale-guinigi": "il",
        "chiesa-san-francesco": "la", "real-collegio": "il", "museo-barsanti-matteucci": "il",
        "via-del-fosso": None, "baluardo-santa-croce": "il", "santi-giovanni-reparata": "la",
    }  # fmt: skip
    assert {luogo.id: luogo.articolo for luogo in DATASET.luoghi} == atteso


def test_etichette_di_lucca() -> None:
    assert {t.id: t.etichetta for t in DATASET.temi} == {
        "verde": "verde e giardini",
        "panorama": "panorama",
        "storia": "storia",
        "medievale": "medioevo",
        "gastronomia": "gastronomia",
        "arte": "arte",
        "silenzio": "silenzio e contemplazione",
        "puccini": "Giacomo Puccini e la musica",
        "musica": "musica",
        "romanico": "romanico",
        "con-bambini": "adatto ai bambini",
        "artigianato": "artigianato",
        "liuteria": "liuteria",
    }


def test_nessun_tema_di_lucca_ha_una_frase() -> None:
    assert all(t.frase is None and t.fonte is None for t in DATASET.temi)


def test_solo_due_racconti_legato_a_e_con_fonte() -> None:
    con_testo = {
        (r.artista_id, r.luogo_id): (r.racconto, r.fonte)
        for r in DATASET.legato_a
        if r.racconto or r.fonte
    }
    assert con_testo == {
        ("artista-puccini", "san-michele-in-foro"): (_RACCONTO_PUCCINI, _FONTE_PUCCINI),
        ("artista-boccherini", "duomo-san-martino"): (_RACCONTO_BOCCHERINI, _FONTE_BOCCHERINI),
    }


def test_nessun_legame_nuovo() -> None:
    assert {(r.artista_id, r.luogo_id) for r in DATASET.legato_a} == {
        ("artista-puccini", "casa-puccini"),
        ("artista-puccini", "san-michele-in-foro"),
        ("artista-puccini", "teatro-del-giglio"),
        ("artista-boccherini", "san-michele-in-foro"),
        ("artista-boccherini", "duomo-san-martino"),
        ("artista-civitali", "duomo-san-martino"),
        ("artista-catalani", "teatro-del-giglio"),
        ("artista-boccherini", "chiesa-san-francesco"),
    }


# --- candidati ---------------------------------------------------------------


def test_racconti_dei_candidati_solo_con_fonte() -> None:
    per_luogo = {
        "san-michele-in-foro": [_RACCONTO_PUCCINI],
        "duomo-san-martino": [_RACCONTO_BOCCHERINI],
    }
    visti_con_racconto = 0
    for c in SeedCandidateSource().candidates(_ctx([])):
        atteso = per_luogo.get(c.experience.place_id, [])
        assert c.racconti == atteso, c.experience.id
        visti_con_racconto += bool(atteso)
    assert visti_con_racconto >= 2


def test_etichette_nell_ordine_dei_temi_dell_esperienza() -> None:
    etichette = {t.id: t.etichetta for t in DATASET.temi}
    for c in SeedCandidateSource().candidates(_ctx([])):
        assert c.temi_etichette == [etichette[t] for t in c.experience.temi], c.experience.id
        assert c.place_articolo == next(
            lg.articolo for lg in DATASET.luoghi if lg.id == c.experience.place_id
        )


def test_vicinanza_ha_la_stessa_condizione_della_frase_gia_visitato() -> None:
    luoghi = {lg.id: lg for lg in DATASET.luoghi}
    for visto in luoghi:
        for c in SeedCandidateSource().candidates(_ctx([visto])):
            frase = any(f.endswith("già visitato.") for f in c.connessioni)
            assert (c.vicinanza_nome is not None) == frase, (visto, c.experience.id)
            if frase:
                assert c.vicinanza_nome == luoghi[visto].nome
                assert c.vicinanza_articolo == luoghi[visto].articolo
                assert c.distanza_m is not None
            else:
                assert c.vicinanza_articolo is None


def test_senza_visti_nessuna_vicinanza() -> None:
    for c in SeedCandidateSource().candidates(_ctx([])):
        assert c.vicinanza_nome is None and c.vicinanza_articolo is None


def test_connessioni_e_distanze_invariate_rispetto_a_prima_del_compito_4() -> None:
    """Testo, numero e ordine delle `connessioni` (e `distanza_m`) per tutti i
    candidati, con e senza luoghi già visti: alimentano lo score."""
    fuori: dict[str, dict[str, list[object]]] = {}
    for visti in [[], *[[lg.id] for lg in DATASET.luoghi]]:
        fuori[",".join(visti)] = {
            c.experience.id: [c.connessioni, c.distanza_m]
            for c in SeedCandidateSource().candidates(_ctx(visti))
        }
    dump = json.dumps(fuori, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert hashlib.sha256(dump).hexdigest() == _HASH_CONNESSIONI_A_HEAD


def test_nessuna_frase_da_catalogo_nei_campi_nuovi() -> None:
    vietati = ("è legato a", "Evoca il tema", "La bottega evoca", "exp-")
    for visto in [None, *[lg.id for lg in DATASET.luoghi]]:
        for c in SeedCandidateSource().candidates(_ctx([visto] if visto else [])):
            testi = [*c.racconti, *c.temi_etichette]
            testi += [x for x in (c.vicinanza_nome, c.vicinanza_articolo, c.place_articolo) if x]
            for t in testi:
                assert not any(v in t for v in vietati), (c.experience.id, t)
                assert '"' not in t, (c.experience.id, t)


def test_il_candidato_non_espone_i_dati_di_un_altro_luogo() -> None:
    for c in SeedCandidateSource().candidates(_ctx([])):
        if c.experience.place_id not in ("san-michele-in-foro", "duomo-san-martino"):
            assert c.racconti == []


# --- Cypher ------------------------------------------------------------------


def test_cypher_committato_coincide_col_generato() -> None:
    assert file_seed_cypher(DATASET).read_text(encoding="utf-8") == build_seed(DATASET)
    assert (CYPHER_DIR / "00_schema.cypher").read_text(encoding="utf-8") == build_schema()


def test_cypher_scrive_i_campi_nuovi_con_set_idempotente() -> None:
    testo = build_seed(DATASET)
    assert "l.articolo = 'l\\''" in testo  # orto-botanico
    assert "l.articolo = NULL" in testo  # le vie
    assert "t.etichetta = 'medioevo'" in testo
    assert "t.frase = NULL, t.fonte = NULL" in testo
    assert f"r.fonte = '{_FONTE_PUCCINI}'" in testo
    assert "MERGE (a)-[r:LEGATO_A]->(l)\nSET r.racconto = NULL, r.fonte = NULL;" in testo
    # I due racconti stanno su UN solo statement ciascuno (il loader spezza su ";\n").
    legato = [st for st in testo.split(";\n") if "[r:LEGATO_A]" in st]
    assert len(legato) == len(DATASET.legato_a)
    assert sum("SET r.racconto = '" in st for st in legato) == 2


def test_query_candidati_restituisce_i_dati_nuovi() -> None:
    q = (CYPHER_DIR / "10_candidates.cypher").read_text(encoding="utf-8")
    for pezzo in (
        "l.articolo AS place_articolo",
        "legati_racconti",
        "riferimento_articolo",
        "etichetta: tema.etichetta",
        "frase: tema.frase",
        "fonte: tema.fonte",
        "racconto: la.racconto",
    ):
        assert pezzo in q, pezzo
