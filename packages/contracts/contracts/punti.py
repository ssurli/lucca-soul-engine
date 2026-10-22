"""Distanze tra punti (WGS84): funzioni pure condivise.

DATI DI POSIZIONE: non entrano MAI nel punteggio. Usi ammessi:

- tempo di trasferimento tra tappe consecutive (Experience Engine);
- la frase «A ... m da ..., già visitato» (grafo);
- la scelta di `ItineraryStop.punto_arrivo` (il punto d'arrivo più vicino
  alla tappa precedente).

Questo è l'UNICO modulo che conosce la formula e il coefficiente: chi calcola
distanze importa da qui, non le riscrive.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import Punto

__all__ = [
    "COEFFICIENTE_PERCORSO_PIEDI",
    "RAGGIO_TERRESTRE_M",
    "distanza_a_piedi_m",
    "distanza_linea_aria_m",
    "punto_piu_vicino",
]

# Coefficiente di percorso a piedi in centro storico: costante DICHIARATA,
# non misurata (vedi docs/LIMITI.md). Moltiplica la linea d'aria.
COEFFICIENTE_PERCORSO_PIEDI: float = 1.3

# Raggio terrestre medio, in metri.
RAGGIO_TERRESTRE_M: float = 6_371_000.0

_PASSO_ARROTONDAMENTO_M = 10


def distanza_linea_aria_m(a: Punto, b: Punto) -> float:
    """Distanza in linea d'aria in metri (formula dell'emisenoverso)."""
    fi_a = math.radians(a.lat)
    fi_b = math.radians(b.lat)
    d_fi = fi_b - fi_a
    d_lam = math.radians(b.lon - a.lon)
    h = math.sin(d_fi / 2) ** 2 + math.cos(fi_a) * math.cos(fi_b) * math.sin(d_lam / 2) ** 2
    h = min(1.0, max(0.0, h))
    return 2 * RAGGIO_TERRESTRE_M * math.asin(math.sqrt(h))


def distanza_a_piedi_m(a: Punto, b: Punto) -> int:
    """Distanza a piedi stimata: linea d'aria x `COEFFICIENTE_PERCORSO_PIEDI`,
    arrotondata ai 10 m con round half up ESPLICITO (floor(x/10 + 0.5) * 10,
    non il `round()` di Python che arrotonda al pari). 0 se i punti coincidono.
    """
    stima = distanza_linea_aria_m(a, b) * COEFFICIENTE_PERCORSO_PIEDI
    passi = math.floor(stima / _PASSO_ARROTONDAMENTO_M + 0.5)
    return int(passi * _PASSO_ARROTONDAMENTO_M)


def punto_piu_vicino(riferimento: Punto, candidati: Sequence[Punto]) -> Punto | None:
    """Il candidato più vicino al riferimento (linea d'aria). A parità vince il
    primo nella lista; `None` se la lista è vuota."""
    migliore: Punto | None = None
    migliore_d = math.inf
    for c in candidati:
        d = distanza_linea_aria_m(riferimento, c)
        if d < migliore_d:
            migliore, migliore_d = c, d
    return migliore
