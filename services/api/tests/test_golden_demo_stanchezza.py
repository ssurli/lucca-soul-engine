"""Stanchezza di partenza a 0 nella demo (approvata dal committente).

Le richieste dei casi `demo|...` stanno nel golden (`richiesta` di ogni caso, per
`/itinerary` e per `/itinerary/adapt`): qui si legge solo il file, senza
ricostruire nulla e senza toccare ne' il motore ne' il golden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN = Path(__file__).parent / "golden" / "lucca_itinerari.json"


def _casi_demo() -> dict[str, dict[str, Any]]:
    casi: dict[str, dict[str, Any]] = json.loads(GOLDEN.read_text(encoding="utf-8"))["casi"]
    return {k: c for k, c in casi.items() if k.startswith("demo|")}


def test_ci_sono_casi_demo() -> None:
    # Niente vacuita': senza casi `demo|` gli altri controlli non provano nulla.
    assert len(_casi_demo()) > 0, "nessun caso demo| nel golden"


def test_ogni_caso_demo_parte_da_stanchezza_zero() -> None:
    casi = _casi_demo()
    assert casi, "nessun caso demo| nel golden"
    fuori = {
        chiave: caso["richiesta"]["signal"]["stanchezza"]
        for chiave, caso in casi.items()
        if caso["richiesta"]["signal"]["stanchezza"] != 0.0
    }
    assert not fuori, f"casi demo| con stanchezza di partenza diversa da 0.0: {fuori}"
