"""Punti di arrivo: regola di risoluzione e codifica Cypher, in UN solo modulo.

DATO DI POSIZIONE: non entra MAI nel punteggio (guardia AST in
`services/experience-engine/tests/test_scoring_non_legge_punti.py`).

Regola unica (`risolvi_punti_arrivo`), usata da `SeedCandidateSource` e
`Neo4jCandidateSource`:
    1. partner fittizio (bottega dimostrativa)  -> []   (un indirizzo inventato
       porterebbe in un negozio reale: decisione del committente);
    2. `ExperienceNode.punti_arrivo` se non vuoto;
    3. altrimenti `[luogo.punto]` se il luogo ha un punto;
    4. altrimenti [].

Codifica Neo4j (che non accetta liste di mappe): liste PARALLELE di float.
    (:Luogo      {lat, lon})                          -- assenti/NULL = nessun punto
    (:Esperienza {punti_arrivo_lat, punti_arrivo_lon}) -- stesso indice = stesso punto,
        nell'ordine del seed (il primo e' quello della prima tappa); scritte SEMPRE,
        anche vuote, cosi' il SET sovrascrive.
"""

from __future__ import annotations

from collections.abc import Sequence

from contracts import Punto


def risolvi_punti_arrivo(
    punti_esperienza: Sequence[Punto],
    punto_luogo: Punto | None,
    bottega_fittizia: bool,
) -> list[Punto]:
    if bottega_fittizia:
        return []
    if punti_esperienza:
        return list(punti_esperienza)
    if punto_luogo is not None:
        return [punto_luogo]
    return []


def codifica_punti(punti: Sequence[Punto]) -> tuple[list[float], list[float]]:
    """(lat, lon) come liste parallele, nell'ordine dato."""
    return [p.lat for p in punti], [p.lon for p in punti]


def decodifica_punti(
    lats: Sequence[float] | None, lons: Sequence[float] | None, chi: str
) -> list[Punto]:
    """Fail-closed: lunghezze diverse sollevano ValueError; `None` = nessun punto
    (grafo non ricaricato). `Punto` valida l'intervallo."""
    lats = lats or []
    lons = lons or []
    if len(lats) != len(lons):
        raise ValueError(
            f"punti di arrivo di {chi}: liste parallele di lunghezza diversa "
            f"(lat={len(lats)}, lon={len(lons)})"
        )
    return [Punto(lat=a, lon=o) for a, o in zip(lats, lons, strict=True)]


def punto_da_coordinate(lat: float | None, lon: float | None, chi: str) -> Punto | None:
    """Punto di un nodo con `lat`/`lon` scalari; entrambi assenti = None, uno solo
    = ValueError (fail-closed)."""
    if lat is None and lon is None:
        return None
    if lat is None or lon is None:
        raise ValueError(f"punto di {chi}: lat e lon vanno insieme (lat={lat}, lon={lon})")
    return Punto(lat=lat, lon=lon)
