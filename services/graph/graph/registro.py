"""Registro dei dataset di città: risolve `CITY_SEED` in un `DatasetCitta`.

Un'installazione = una città. Il nome della città vive in UN punto del
codice di produzione (`CITY_SEED_PREDEFINITO`) e nei moduli dataset
`graph/seed_<slug>.py`; tutto il resto (sorgenti, topologia, export, loader)
riceve un `DatasetCitta` e non sa quale città sia.

Convenzione di risoluzione, per lo slug `s` (con `-` -> `_` per il modulo):
- dataset: modulo `graph.seed_<s>`, attributo `DATASET: DatasetCitta`;
- Cypher:  `cypher/01_seed_<s>.cypher`, generato da `graph.export_cypher`.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

from graph.dataset import DatasetCitta
from graph.env import city_seed_da_env

# UNICO punto fuori dai moduli dataset (`graph/seed_<città>.py`) in cui compare
# il nome di una città. Sta in un'allowlist esplicita della guardia che vieta
# nomi di città nel codice di produzione: non spostarlo, non duplicarlo.
CITY_SEED_PREDEFINITO = "lucca"

CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _normalizza_slug(nome: str) -> str:
    """Valida lo slug e lo riporta alla forma usata nei nomi di modulo/file
    (`-` -> `_`). `ValueError` leggibile se non è uno slug."""
    if not _SLUG_RE.fullmatch(nome):
        raise ValueError(
            f"CITY_SEED {nome!r} non valido: serve uno slug minuscolo "
            "(lettere, cifre, '_' o '-', che inizia con una lettera)"
        )
    return nome.replace("-", "_")


def carica_dataset(nome: str | None) -> DatasetCitta:
    """Importa `graph.seed_<slug>` e ne restituisce `DATASET`.

    `None` o stringa vuota -> `CITY_SEED_PREDEFINITO`. `ValueError` con un
    messaggio leggibile per slug invalido, modulo inesistente o `DATASET`
    mancante/di tipo sbagliato."""
    slug = _normalizza_slug((nome or "").strip() or CITY_SEED_PREDEFINITO)
    modulo_nome = f"graph.seed_{slug}"
    try:
        modulo = importlib.import_module(modulo_nome)
    except ModuleNotFoundError as exc:
        if exc.name != modulo_nome:
            raise  # dipendenza mancante DENTRO il dataset: non mascherarla
        raise ValueError(
            f"nessun dataset per CITY_SEED={slug!r}: manca il modulo "
            f"services/graph/graph/seed_{slug}.py"
        ) from exc
    dataset = getattr(modulo, "DATASET", None)
    if dataset is None:
        raise ValueError(
            f"il modulo {modulo_nome} non espone DATASET (atteso un DatasetCitta)"
        )
    if not isinstance(dataset, DatasetCitta):
        raise ValueError(
            f"{modulo_nome}.DATASET è di tipo {type(dataset).__name__}, "
            "atteso DatasetCitta"
        )
    return dataset


def file_seed_cypher(dataset_o_nome: DatasetCitta | str) -> Path:
    """Percorso di `cypher/01_seed_<slug>.cypher` per un dataset o uno slug."""
    nome = dataset_o_nome.nome if isinstance(dataset_o_nome, DatasetCitta) else dataset_o_nome
    return CYPHER_DIR / f"01_seed_{_normalizza_slug(nome)}.cypher"


def dataset_attivo() -> DatasetCitta:
    """Il dataset della città di questa installazione (`CITY_SEED`)."""
    return carica_dataset(city_seed_da_env())
