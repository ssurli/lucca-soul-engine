"""Unica definizione di "periodo" per l'Urban Intelligence Index.

`UrbanIntelligenceIndex.periodo` è una stringa `"YYYY-MM"` (es. `"2026-07"`,
`packages/contracts/contracts/models.py`). Ogni pezzo del calcolo che ha
bisogno di un intervallo di tempo — il filtro degli eventi
(`BehaviorEventSource.events_in_period`), il filtro dei contributi di
Urban Memory (`MemoryContribution.creato_il`), lo snapshot del grafo a
INIZIO periodo (`graph.metrics.GraphMetricsSource.non_connected_place_pairs`)
— usa QUESTA funzione, mai una seconda conversione locale: due definizioni
di "inizio mese" leggermente diverse produrrebbero indicatori non
confrontabili tra loro senza che nessuno se ne accorga.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["intervallo_periodo"]


def intervallo_periodo(periodo: str) -> tuple[datetime, datetime]:
    """`"2026-07"` -> `(2026-07-01T00:00:00Z, 2026-08-01T00:00:00Z)`.

    Intervallo semi-aperto `[inizio, fine)`, sempre UTC (coerente con
    `BehaviorEvent.ts`/`MemoryContribution.creato_il`, entrambi
    timezone-aware). `inizio` è anche l'istante `at` per lo snapshot del
    grafo di `nuovi_percorsi` — "connesso all'INIZIO del periodo", non a un
    istante qualunque durante il periodo.

    Solleva `ValueError` se `periodo` non è nel formato `"YYYY-MM"`: fallire
    qui, leggibile, è meglio che produrre un intervallo silenziosamente
    sbagliato.
    """
    try:
        anno_str, mese_str = periodo.split("-")
        anno, mese = int(anno_str), int(mese_str)
    except ValueError as exc:
        raise ValueError(
            f"periodo={periodo!r} non è nel formato atteso \"YYYY-MM\" (es. \"2026-07\")"
        ) from exc
    if not 1 <= mese <= 12:
        raise ValueError(f"periodo={periodo!r}: mese {mese} fuori range [1, 12]")

    inizio = datetime(anno, mese, 1, tzinfo=UTC)
    if mese == 12:
        fine = datetime(anno + 1, 1, 1, tzinfo=UTC)
    else:
        fine = datetime(anno, mese + 1, 1, tzinfo=UTC)
    return inizio, fine
