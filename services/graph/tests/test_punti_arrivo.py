"""Compito 3 (ondata 3): coordinate dei luoghi e punti di arrivo delle esperienze.

Dati del committente (Google Maps, 22/10/2026) esatti nel seed, regola di
risoluzione unica (esperienza > luogo > vuoto; vuoto con bottega fittizia) uguale
in `SeedCandidateSource` e nel mapping Neo4j (record finti), Cypher committato
uguale al generato, float scritti con precisione piena.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from contracts import Punto
from graph.dataset import Luogo
from graph.export_cypher import build_seed
from graph.punti import codifica_punti, decodifica_punti, punto_da_coordinate, risolvi_punti_arrivo
from graph.registro import CYPHER_DIR, file_seed_cypher
from graph.seed_lucca import DATASET
from graph.source import Neo4jCandidateSource, SeedCandidateSource

sys.path.insert(0, str(Path(__file__).parent))
from test_connessioni_uguali import _ctx, _record  # noqa: E402

_LUOGHI_ATTESI: dict[str, tuple[float, float]] = {
    "duomo-san-martino": (43.8407348442907, 10.50546424867784),
    "san-michele-in-foro": (43.843206920716746, 10.502521515682991),
    "san-frediano": (43.84611439494372, 10.504828564629559),
    "piazza-anfiteatro": (43.8453750945062, 10.506130836198794),
    "torre-guinigi": (43.84385893695291, 10.507472634710469),
    "casa-puccini": (43.843207634585866, 10.501333062529884),
    "orto-botanico": (43.84100710602395, 10.51019343794917),
    "teatro-del-giglio": (43.84062952605113, 10.502840967928876),
    "palazzo-pfanner": (43.8455344278912, 10.503022099598914),
    "torre-delle-ore": (43.84341924030429, 10.504123087494012),
    "piazza-napoleone": (43.841381710949506, 10.502460320754349),
    "via-fillungo": (43.842686481849164, 10.504022332247528),
    "baluardo-san-paolino": (43.840816169243126, 10.496989849819938),
    "museo-nazionale-guinigi": (43.84532590685096, 10.51227072450463),
    "chiesa-san-francesco": (43.84544716682871, 10.510919717837515),
    "real-collegio": (43.846454429687576, 10.503858387960499),
    "museo-barsanti-matteucci": (43.843638790269274, 10.507385090128256),
    "via-del-fosso": (43.84529568253382, 10.509682371585473),
    "baluardo-santa-croce": (43.84569128378519, 10.497872636788552),
    "santi-giovanni-reparata": (43.84119039780105, 10.504274232740409),
    # Ondata 3, compito 8 (dato del committente, 22/10/2026).
    "palazzo-bernardini": (43.84257809211349, 10.50566149655655),
    "san-pietro-somaldi": (43.84555613789234, 10.508002871124265),
    "parco-giochi-san-donato": (43.84458794966101, 10.497221545825257),
}

_RAMPE: list[tuple[float, float]] = [
    (43.83975799648603, 10.506535046223485),
    (43.84807404345435, 10.507089236931973),
    (43.841277451100694, 10.496706879150684),
    (43.842315738273435, 10.497113013689594),
    (43.84552607610066, 10.514030908363878),
    (43.83882258921756, 10.501625645596407),
]
_TRAMONTO: list[tuple[float, float]] = [
    (43.84668153219125, 10.502592655389329),
    (43.84060703195673, 10.496914055249684),
    (43.84260326710044, 10.513896040654814),
    (43.84750898171982, 10.513950290731266),
    (43.848580906193554, 10.508889574921993),
]
_PUNTI_ESPERIENZE: dict[str, list[tuple[float, float]]] = {
    "exp-passeggiata-mura": _RAMPE,
    "exp-bici-mura": _RAMPE,
    "exp-tramonto-baluardo": _TRAMONTO,
    "exp-pfanner-dalle-mura": [(43.846610457117684, 10.502497041284132)],
}

_BOTTEGHE = {b.id: b for b in DATASET.botteghe}


def _coppie(punti: list[Punto]) -> list[tuple[float, float]]:
    return [(p.lat, p.lon) for p in punti]


def _statement(testo: str, intestazione: str) -> str:
    """Lo statement (il loader spezza su punto e virgola + a-capo) che inizia con `intestazione`."""
    return next(st for st in testo.split(";" + chr(10)) if intestazione in st)


# --- dati del seed -----------------------------------------------------------


def test_punti_dei_luoghi_esatti_dal_seed() -> None:
    trovati = {
        luogo.id: (luogo.punto.lat, luogo.punto.lon) for luogo in DATASET.luoghi if luogo.punto
    }
    assert trovati == _LUOGHI_ATTESI


def test_mura_urbane_senza_punto() -> None:
    mura = next(luogo for luogo in DATASET.luoghi if luogo.id == "mura-urbane")
    assert mura.punto is None


def test_punti_di_arrivo_delle_quattro_esperienze() -> None:
    trovati = {e.id: _coppie(e.punti_arrivo) for e in DATASET.esperienze if e.punti_arrivo}
    assert trovati == _PUNTI_ESPERIENZE


def test_punto_non_valido_solleva() -> None:
    with pytest.raises(ValueError):
        Punto(lat=91, lon=0)
    with pytest.raises(ValueError, match="punto"):
        Luogo("x", "Posto", "piazza", punto=(1.0, 2.0))  # type: ignore[arg-type]


# --- regola di risoluzione (funzione pura) ----------------------------------


def test_regola_esperienza_batte_luogo_batte_vuoto() -> None:
    a, b = Punto(lat=1, lon=2), Punto(lat=3, lon=4)
    assert risolvi_punti_arrivo([a], b, False) == [a]
    assert risolvi_punti_arrivo([], b, False) == [b]
    assert risolvi_punti_arrivo([], None, False) == []


def test_regola_bottega_fittizia_vuota_anche_con_punti() -> None:
    a, b = Punto(lat=1, lon=2), Punto(lat=3, lon=4)
    assert risolvi_punti_arrivo([a], b, True) == []
    assert risolvi_punti_arrivo([], b, True) == []


def test_codifica_decodifica_round_trip() -> None:
    punti = [Punto(lat=a, lon=o) for a, o in _RAMPE]
    lat, lon = codifica_punti(punti)
    assert decodifica_punti(lat, lon, "x") == punti
    assert decodifica_punti(None, None, "x") == []
    with pytest.raises(ValueError, match="lunghezza"):
        decodifica_punti([1.0], [], "x")
    with pytest.raises(ValueError, match="insieme"):
        punto_da_coordinate(1.0, None, "x")
    assert punto_da_coordinate(None, None, "x") is None


# --- risoluzione nelle due fonti --------------------------------------------


def _attesi_per_esperienza() -> dict[str, list[tuple[float, float]]]:
    attesi: dict[str, list[tuple[float, float]]] = {}
    for e in DATASET.esperienze:
        fittizia = bool(e.partner_id and _BOTTEGHE[e.partner_id].fittizio)
        if fittizia:
            attesi[e.id] = []
        elif e.id in _PUNTI_ESPERIENZE:
            attesi[e.id] = _PUNTI_ESPERIENZE[e.id]
        elif e.place_id in _LUOGHI_ATTESI:
            attesi[e.id] = [_LUOGHI_ATTESI[e.place_id]]
        else:
            attesi[e.id] = []
    return attesi


def test_seed_risolve_i_punti_di_arrivo() -> None:
    candidati = SeedCandidateSource(DATASET).candidates(_ctx([]))
    assert {c.experience.id: _coppie(c.punti_arrivo) for c in candidati} == (
        _attesi_per_esperienza()
    )


def test_seed_bottega_fittizia_vuota_anche_se_il_luogo_ha_un_punto() -> None:
    candidati = {c.experience.id: c for c in SeedCandidateSource(DATASET).candidates(_ctx([]))}
    assert "san-michele-in-foro" in _LUOGHI_ATTESI
    assert candidati["exp-laboratorio-liuteria"].punti_arrivo == []
    senza_partner = [
        c
        for c in candidati.values()
        if c.experience.place_id == "san-michele-in-foro" and not c.experience.partner_id
    ]
    for c in senza_partner:
        assert _coppie(c.punti_arrivo) == [_LUOGHI_ATTESI["san-michele-in-foro"]]


def test_seed_alle_mura_senza_punti_propri_resta_vuoto() -> None:
    candidati = SeedCandidateSource(DATASET).candidates(_ctx([]))
    for c in candidati:
        if c.experience.place_id == "mura-urbane" and not c.experience.punti_arrivo:
            assert c.punti_arrivo == []


@pytest.mark.parametrize("visto", [None, "casa-puccini", "mura-urbane"])
def test_seed_uguale_a_neo4j(visto: str | None) -> None:
    rng = random.Random(3)
    seed = {
        c.experience.id: c
        for c in SeedCandidateSource(DATASET).candidates(_ctx([visto] if visto else []))
    }
    for esp_id, atteso in seed.items():
        record: Any = _record(esp_id, visto, rng)
        da_neo4j = Neo4jCandidateSource._to_candidate(record, visto)
        assert da_neo4j.punti_arrivo == atteso.punti_arrivo, esp_id
        assert da_neo4j.experience.punti_arrivo == atteso.experience.punti_arrivo, esp_id


def _record_di(esp_id: str, extra: dict[str, Any]) -> Any:
    return {**_record(esp_id, None, random.Random(1)), **extra}


def _punti_neo4j(extra: dict[str, Any]) -> list[tuple[float, float]]:
    record = _record_di("exp-passeggiata-mura", extra)
    return _coppie(Neo4jCandidateSource._to_candidate(record).punti_arrivo)


def test_neo4j_regola_su_record_finti() -> None:
    nessuna = [{"nome": None, "mestiere": None, "fittizio": True}]
    reale = [{"nome": "Bottega Vera", "mestiere": "liuteria", "fittizio": False}]
    fittizia = [{"nome": "Bottega Demo", "mestiere": "liuteria", "fittizio": True}]
    luogo = {"luogo_lat": 1.5, "luogo_lon": 2.5, "botteghe": nessuna}
    # Esperienza > luogo.
    assert _punti_neo4j(
        {**luogo, "punti_arrivo_lat": [10.0, 11.0], "punti_arrivo_lon": [20.0, 21.0]}
    ) == [
        (10.0, 20.0),
        (11.0, 21.0),
    ]
    # Luogo se l'esperienza non ha punti.
    assert _punti_neo4j({**luogo, "punti_arrivo_lat": [], "punti_arrivo_lon": []}) == [(1.5, 2.5)]
    # Ne' esperienza ne' luogo (anche proprieta' assenti = None): vuoto.
    assert (
        _punti_neo4j(
            {
                "luogo_lat": None,
                "luogo_lon": None,
                "punti_arrivo_lat": None,
                "punti_arrivo_lon": None,
            }
        )
        == []
    )
    # Bottega reale: i punti restano.
    assert _punti_neo4j(
        {**luogo, "botteghe": reale, "punti_arrivo_lat": [], "punti_arrivo_lon": []}
    ) == [(1.5, 2.5)]
    # Bottega fittizia: vuoto anche con punti dell'esperienza e del luogo.
    assert (
        _punti_neo4j(
            {**luogo, "botteghe": fittizia, "punti_arrivo_lat": [10.0], "punti_arrivo_lon": [20.0]}
        )
        == []
    )


def test_neo4j_liste_di_lunghezza_diversa_o_punto_a_meta_solleva() -> None:
    with pytest.raises(ValueError, match="lunghezza"):
        _punti_neo4j({"punti_arrivo_lat": [1.0], "punti_arrivo_lon": []})
    with pytest.raises(ValueError, match="insieme"):
        _punti_neo4j({"luogo_lat": 1.0, "luogo_lon": None})


# --- Cypher -----------------------------------------------------------------


def test_cypher_committato_uguale_al_generato() -> None:
    assert file_seed_cypher(DATASET).read_text(encoding="utf-8") == build_seed(DATASET)


def test_cypher_scrive_lat_lon_dei_luoghi_con_precisione_piena() -> None:
    testo = build_seed(DATASET)
    for luogo_id, (lat, lon) in _LUOGHI_ATTESI.items():
        blocco = _statement(testo, f"MERGE (l:Luogo {{id: '{luogo_id}'}})")
        trovato = re.search(r"l\.lat = (\S+),\s+l\.lon = (\S+)$", blocco)
        assert trovato is not None, luogo_id
        assert (float(trovato.group(1)), float(trovato.group(2))) == (lat, lon)
    mura = _statement(testo, "MERGE (l:Luogo {id: 'mura-urbane'})")
    assert "l.lat = NULL" in mura and "l.lon = NULL" in mura


def test_cypher_scrive_liste_parallele_delle_esperienze_sempre() -> None:
    testo = build_seed(DATASET)
    blocchi = [st for st in testo.split(";" + chr(10)) if "MERGE (e:Esperienza" in st]
    assert len(blocchi) == len(DATASET.esperienze)
    assert all("e.punti_arrivo_lat = [" in st and "e.punti_arrivo_lon = [" in st for st in blocchi)
    for esp_id, attesi in _PUNTI_ESPERIENZE.items():
        blocco = _statement(testo, f"MERGE (e:Esperienza {{id: '{esp_id}'}})")
        lat = re.search(r"e\.punti_arrivo_lat = \[(.*?)\]", blocco)
        lon = re.search(r"e\.punti_arrivo_lon = \[(.*?)\]", blocco)
        assert lat is not None and lon is not None
        letti = list(
            zip(
                (float(x) for x in lat.group(1).split(", ")),
                (float(x) for x in lon.group(1).split(", ")),
                strict=True,
            )
        )
        assert letti == attesi
    assert "e.punti_arrivo_lat = []," in testo


def test_schema_documenta_la_codifica() -> None:
    schema = (CYPHER_DIR / "00_schema.cypher").read_text(encoding="utf-8")
    assert "punti_arrivo_lat" in schema and "Luogo {lat, lon}" in schema


def test_query_candidati_restituisce_i_punti() -> None:
    q = (CYPHER_DIR / "10_candidates.cypher").read_text(encoding="utf-8")
    for riga in (
        "l.lat AS luogo_lat",
        "l.lon AS luogo_lon",
        "coalesce(e.punti_arrivo_lat, []) AS punti_arrivo_lat",
        "coalesce(e.punti_arrivo_lon, []) AS punti_arrivo_lon",
    ):
        assert riga in q
