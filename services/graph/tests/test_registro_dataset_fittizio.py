"""Gate aggiuntivo (test-engineer): il motore usa DAVVERO il dataset risolto.

Nessun file di dataset nel codice di produzione: il modulo fittizio vive solo
in `sys.modules` per la durata del test. Nessun accesso al `.env` reale né a
Neo4j: ogni chiamata riceve un dataset o uno slug esplicito.
"""

from __future__ import annotations

import types
from datetime import time
from pathlib import Path

import pytest
from contracts import EmotionalProfile, ExperienceNode, Signal, VisitorContext, VocabolarioTemi
from graph import loader
from graph.dataset import Bottega, DatasetCitta, Luogo, Tema
from graph.export_cypher import build_seed
from graph.registro import CYPHER_DIR, carica_dataset, file_seed_cypher
from graph.seed_lucca import DATASET as LUCCA
from graph.source import SeedCandidateSource

SLUG = "terra-di-prova"


def _dataset_finto(nome: str = SLUG) -> DatasetCitta:
    return DatasetCitta(
        nome=nome,
        luoghi=[Luogo(id="zz-piazza-inventata", nome="Piazza Zorbonia", categoria="piazza")],
        artisti=[],
        legato_a=[],
        botteghe=[
            Bottega(
                id="zz-bottega-inventata",
                nome="Bottega dei Fantasmi",
                mestiere="ceramica",
                place_id="zz-piazza-inventata",
                fittizio=True,
            )
        ],
        temi=[Tema(id="zz-tema", nome="Tema inventato")],
        bottega_evoca=[],
        bottega_ispirata_da=[],
        partners=[],
        ha_abbonamento=[],
        esperienze=[
            ExperienceNode(
                id="zz-exp",
                titolo="Esperienza inventata",
                place_id="zz-piazza-inventata",
                temi=["zz-tema"],
                durata_min=20,
                al_chiuso=False,
                accessibile=True,
            )
        ],
        vicino=[],
        vicino_epoca=LUCCA.vicino_epoca,
        id_esempio_memoria="zz-bottega-inventata",
        vocabolario=VocabolarioTemi(
            contemplativi=frozenset({"zz-tema"}),
            arte=frozenset(),
            insoliti=frozenset(),
            verde=frozenset({"zz-tema"}),
            bambini="zz-tema",
        ),
    )


@pytest.fixture
def finto(monkeypatch: pytest.MonkeyPatch) -> DatasetCitta:
    ds = _dataset_finto()
    modulo = types.ModuleType("graph.seed_terra_di_prova")
    modulo.__dict__["DATASET"] = ds
    monkeypatch.setitem(__import__("sys").modules, "graph.seed_terra_di_prova", modulo)
    monkeypatch.delenv("CITY_SEED", raising=False)
    return ds


def _ctx() -> VisitorContext:
    return VisitorContext(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.5,
            contemplazione=0.5,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=120,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
        luoghi_gia_visti=[],
    )


def test_slug_con_trattino_risolve_modulo_e_file_con_underscore(finto: DatasetCitta) -> None:
    assert carica_dataset(SLUG) is finto
    assert file_seed_cypher(SLUG) == CYPHER_DIR / "01_seed_terra_di_prova.cypher"
    assert file_seed_cypher(finto) == file_seed_cypher(SLUG)
    # la forma con underscore e quella con trattino sono lo stesso modulo
    assert carica_dataset("terra_di_prova") is finto


def test_carica_dataset_non_predefinito_non_e_lucca(finto: DatasetCitta) -> None:
    ds = carica_dataset(SLUG)
    assert ds.nome == SLUG
    assert ds is not LUCCA


def test_seed_candidate_source_usa_solo_il_dataset_risolto(finto: DatasetCitta) -> None:
    ds = carica_dataset(SLUG)
    candidati = SeedCandidateSource(ds).candidates(_ctx())
    assert [c.experience.id for c in candidati] == ["zz-exp"]
    assert candidati[0].place_nome == "Piazza Zorbonia"
    id_lucca = {e.id for e in LUCCA.esperienze}
    assert not id_lucca & {c.experience.id for c in candidati}


def test_build_seed_del_dataset_finto_non_contiene_lucca(finto: DatasetCitta) -> None:
    testo = build_seed(carica_dataset(SLUG))
    assert "zz-bottega-inventata" in testo
    assert "Piazza Zorbonia" in testo
    for luogo in LUCCA.luoghi:
        assert luogo.id not in testo


def test_statements_su_file_del_dataset_finto(finto: DatasetCitta, tmp_path: Path) -> None:
    f = tmp_path / "seed.cypher"
    f.write_text(build_seed(finto), encoding="utf-8")
    stmts = loader._statements(f)
    assert stmts
    assert any("zz-exp" in s for s in stmts)


def test_id_esempio_memoria_inesistente_e_rifiutato() -> None:
    base = _dataset_finto()
    with pytest.raises(ValueError, match="id_esempio_memoria"):
        DatasetCitta(**{**base.__dict__, "id_esempio_memoria": "non-esiste"})
    # un Luogo e' un bersaglio valido quanto una Bottega
    DatasetCitta(**{**base.__dict__, "id_esempio_memoria": "zz-piazza-inventata"})


def test_build_seed_lucca_e_byte_identico_al_file_committato() -> None:
    atteso = file_seed_cypher(LUCCA).read_bytes().decode("utf-8")
    atteso = atteso.replace("\r\n", "\n")
    assert build_seed(LUCCA).replace("\r\n", "\n") == atteso


def test_statements_del_seed_predefinito_non_vuoto() -> None:
    stmts = loader._statements(file_seed_cypher(LUCCA))
    assert len(stmts) > 10
    assert all(s and not s.startswith("//") for s in stmts)


def test_vocabolario_lucca_e_quello_storico_del_motore() -> None:
    v = LUCCA.vocabolario
    assert v.contemplativi == frozenset({"silenzio", "verde", "panorama", "romanico"})
    assert v.arte == frozenset({"arte", "puccini", "musica", "romanico", "liuteria"})
    assert v.insoliti == frozenset({"artigianato", "liuteria", "romanico", "medievale"})
    assert v.verde == frozenset({"verde", "panorama"})
    assert v.bambini == "con-bambini"


def test_vocabolario_con_id_inesistente_e_rifiutato() -> None:
    base = _dataset_finto()
    voc = VocabolarioTemi(
        contemplativi=frozenset({"zz-tema", "zz-fantasma"}),
        arte=frozenset(),
        insoliti=frozenset(),
        verde=frozenset(),
        bambini="zz-assente",
    )
    with pytest.raises(ValueError, match="zz-assente, zz-fantasma"):
        DatasetCitta(**{**base.__dict__, "vocabolario": voc})
