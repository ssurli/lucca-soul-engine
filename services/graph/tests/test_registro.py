"""Test del registro dei dataset di città (`graph.registro`).

Offline: nessun database. Il `.env` reale non viene mai letto dai test che
toccano `CITY_SEED` (si passa sempre un `.env` temporaneo).
"""

from __future__ import annotations

import re
from datetime import time
from pathlib import Path

import pytest
from contracts import EmotionalProfile, Signal, VisitorContext
from graph import registro
from graph.dataset import DatasetCitta
from graph.env import city_seed_da_env
from graph.registro import (
    CITY_SEED_PREDEFINITO,
    carica_dataset,
    dataset_attivo,
    file_seed_cypher,
)
from graph.source import SeedCandidateSource

GRAPH_PKG = Path(registro.__file__).resolve().parent


def test_predefinito_e_il_dataset_di_lucca() -> None:
    assert CITY_SEED_PREDEFINITO == "lucca"
    for vuoto in (None, "", "   "):
        ds = carica_dataset(vuoto)
        assert isinstance(ds, DatasetCitta)
        assert ds.nome == "lucca"


def test_dataset_di_lucca_espone_i_contenuti_e_l_id_memoria() -> None:
    ds = carica_dataset("lucca")
    assert ds.id_esempio_memoria == "liuteria-lucchese"
    assert len(ds.luoghi) == 21
    assert ds.esperienze


@pytest.mark.parametrize("slug", ["Lucca", "1lucca", "luc ca", "../x", "lucca.py", "-a"])
def test_slug_invalido_solleva_value_error_leggibile(slug: str) -> None:
    with pytest.raises(ValueError, match="CITY_SEED"):
        carica_dataset(slug)


def test_modulo_inesistente_solleva_value_error_leggibile() -> None:
    with pytest.raises(ValueError, match="nessun dataset per CITY_SEED='citta_che_non_esiste'"):
        carica_dataset("citta-che-non-esiste")


def test_dataset_mancante_o_di_tipo_sbagliato(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import types

    def finto(nome: str) -> types.ModuleType:
        modulo = types.ModuleType(nome)
        if nome == "graph.seed_senza":
            return modulo
        modulo.__dict__["DATASET"] = 42
        return modulo

    monkeypatch.setattr(importlib, "import_module", finto)
    with pytest.raises(ValueError, match="non espone DATASET"):
        carica_dataset("senza")
    with pytest.raises(ValueError, match="atteso DatasetCitta"):
        carica_dataset("sbagliato")


def test_file_seed_cypher_di_lucca_e_il_file_esistente() -> None:
    percorso = file_seed_cypher("lucca")
    assert percorso.name == "01_seed_lucca.cypher"
    assert percorso.is_file()
    assert file_seed_cypher(carica_dataset("lucca")) == percorso
    with pytest.raises(ValueError, match="CITY_SEED"):
        file_seed_cypher("../evil")


def test_city_seed_ambiente_ha_precedenza_sul_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('CITY_SEED="da_file"\n', encoding="utf-8")

    monkeypatch.delenv("CITY_SEED", raising=False)
    assert city_seed_da_env(dotenv) == "da_file"

    monkeypatch.setenv("CITY_SEED", "da_ambiente")
    assert city_seed_da_env(dotenv) == "da_ambiente"


def test_city_seed_assente_o_vuoto_e_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CITY_SEED", raising=False)
    assert city_seed_da_env(tmp_path / "non_esiste.env") is None
    vuoto = tmp_path / ".env"
    vuoto.write_text("CITY_SEED=\n", encoding="utf-8")
    assert city_seed_da_env(vuoto) is None


def test_dataset_attivo_segue_city_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITY_SEED", "lucca")
    assert dataset_attivo() is carica_dataset("lucca")
    monkeypatch.setenv("CITY_SEED", "citta-che-non-esiste")
    with pytest.raises(ValueError, match="nessun dataset"):
        dataset_attivo()


def test_seed_candidate_source_default_uguale_a_dataset_esplicito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CITY_SEED", "lucca")
    ctx = VisitorContext(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.7,
            contemplazione=0.3,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=180,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
        luoghi_gia_visti=["casa-puccini"],
    )
    implicito = SeedCandidateSource().candidates(ctx)
    esplicito = SeedCandidateSource(carica_dataset("lucca")).candidates(ctx)
    assert implicito
    assert implicito == esplicito


def test_nessun_nome_di_citta_fuori_da_dataset_e_registro() -> None:
    """Il codice di produzione di `graph` non nomina la città: solo il modulo
    dataset (`seed_lucca.py`) e il registro (`CITY_SEED_PREDEFINITO`)."""
    consentiti = {"seed_lucca.py", "registro.py"}
    colpevoli = [
        f"{path.name}:{numero}"
        for path in sorted(GRAPH_PKG.glob("*.py"))
        if path.name not in consentiti
        for numero, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search("lucc", riga, re.IGNORECASE)
    ]
    assert colpevoli == []
