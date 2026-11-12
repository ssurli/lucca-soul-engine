"""Il segnale "Troppa folla" simulato dall'app deve restare utile e coerente col motore.

Il valore sta tra la soglia di adattamento (sopra, le tappe all'aperto vengono
riscritte) e la soglia critica (da li' il filtro duro esclude tutto il luogo,
anche gli interni, che non potrebbero piu' fare da sostituto).
"""

from __future__ import annotations

import re
from pathlib import Path

from experience_engine.rules import (
    SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
    SOGLIA_AFFOLLAMENTO_CRITICO,
)

RADICE = Path(__file__).resolve().parent.parent
PRESETS = RADICE / "apps" / "lucca_soul_app" / "lib" / "util" / "signal_presets.dart"
SEED = RADICE / "services" / "graph" / "cypher" / "01_seed_lucca.cypher"

LUOGHI_ATTESI = ["via-fillungo", "san-michele-in-foro"]


def _sorgente() -> str:
    return PRESETS.read_text(encoding="utf-8")


def _valore_dart() -> float:
    m = re.search(
        r"const\s+double\s+kValoreAffollamentoSimulato\s*=\s*([0-9]*\.?[0-9]+)\s*;",
        _sorgente(),
    )
    assert m, f"costante kValoreAffollamentoSimulato non trovata in {PRESETS}"
    return float(m.group(1))


def _luoghi_dart() -> list[str]:
    m = re.search(
        r"const\s+List<String>\s+kLuoghiAffollatiSimulati\s*=\s*\[([^\]]*)\]\s*;",
        _sorgente(),
    )
    assert m, f"costante kLuoghiAffollatiSimulati non trovata in {PRESETS}"
    return re.findall(r"'([^']+)'", m.group(1))


def test_valore_tra_soglia_di_adattamento_e_soglia_critica() -> None:
    valore = _valore_dart()
    assert SOGLIA_AFFOLLAMENTO_ADATTAMENTO < valore < SOGLIA_AFFOLLAMENTO_CRITICO, (
        f"valore app {valore} fuori da ({SOGLIA_AFFOLLAMENTO_ADATTAMENTO}, "
        f"{SOGLIA_AFFOLLAMENTO_CRITICO})"
    )


def test_elenco_dei_luoghi_affollati_e_quello_atteso() -> None:
    assert _luoghi_dart() == LUOGHI_ATTESI


def test_ogni_luogo_dell_elenco_e_un_luogo_del_seed() -> None:
    seed = SEED.read_text(encoding="utf-8")
    luoghi_seed = set(re.findall(r"\(\w+:Luogo\s*\{id:\s*'([^']+)'\}\)", seed))
    assert luoghi_seed, f"nessun :Luogo trovato in {SEED}"
    mancanti = [lid for lid in _luoghi_dart() if lid not in luoghi_seed]
    assert not mancanti, f"luoghi non presenti nel seed: {mancanti}"
