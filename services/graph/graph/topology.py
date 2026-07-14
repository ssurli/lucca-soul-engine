"""Ricerca su grafo in-memory sul dataset canonico — offline, senza Neo4j.

Serve a due scopi, entrambi verificati in `tests/test_topology.py`:

1. Misurare la topologia dei Luoghi (`VICINO`): densità media e distribuzione
   dei vicini, per garantire che il grafo sia una RETE camminabile e non una
   catena (diagnosi Aura del 2026-07-14: densità 2,3 vicini/luogo, 4 vicoli
   ciechi con un solo vicino).
2. Dimostrare che i percorsi SEMANTICI (`LEGATO_A`, `SI_SVOLGE_A`, `OFFRE`,
   `EVOCA`, `ISPIRATA_DA` — tutto tranne `VICINO`) collegano un Artista a una
   Bottega pertinente entro pochi salti: è la prova del principio "il grafo
   ragiona su relazioni, non categorie" (Puccini -> ... -> liutaio ->
   violino), indipendente dalla prossimità fisica.

Le relazioni sono trattate come NON orientate per la ricerca dei cammini: lo
scopo è il RACCONTO delle connessioni (chi è legato a cosa), non l'inferenza
causale — la stessa ragione per cui `VICINO` è già simmetrico nel dominio, e
per cui `graph.source.SeedCandidateSource` legge `LEGATO_A`/`OFFRE` in
entrambe le direzioni.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from graph.seed_lucca import (
    BOTTEGA_EVOCA,
    BOTTEGA_ISPIRATA_DA,
    ESPERIENZE,
    LEGATO_A,
    LUOGHI,
    VICINO,
)

# Tutti i tipi di relazione tranne VICINO: quelle "semantiche" (artisti, temi,
# botteghe, esperienze) che devono, da sole, rendere raggiungibile un
# artigiano pertinente a partire da un artista — indipendentemente dalla
# prossimità fisica.
SEMANTIC_RELATION_TYPES: frozenset[str] = frozenset(
    {"LEGATO_A", "SI_SVOLGE_A", "OFFRE", "EVOCA", "ISPIRATA_DA"}
)
ALL_RELATION_TYPES: frozenset[str] = SEMANTIC_RELATION_TYPES | {"VICINO"}


@dataclass(frozen=True)
class Edge:
    da: str
    tipo: str
    a: str


def _all_edges() -> list[Edge]:
    """Tutte le relazioni del seed come archi (nodo, tipo, nodo), ricostruite
    dagli stessi campi che alimentano `graph.export_cypher` — nessuna
    seconda fonte di verità."""
    edges: list[Edge] = []

    for rel in VICINO:
        edges.append(Edge(rel.da_id, "VICINO", rel.a_id))

    for rel in LEGATO_A:
        edges.append(Edge(rel.artista_id, "LEGATO_A", rel.luogo_id))

    for esperienza in ESPERIENZE:
        edges.append(Edge(esperienza.id, "SI_SVOLGE_A", esperienza.place_id))
        for tema_id in esperienza.temi:
            edges.append(Edge(esperienza.id, "EVOCA", tema_id))
        if esperienza.partner_id is not None:
            edges.append(Edge(esperienza.partner_id, "OFFRE", esperienza.id))

    for rel in BOTTEGA_EVOCA:
        edges.append(Edge(rel.bottega_id, "EVOCA", rel.tema_id))

    for rel in BOTTEGA_ISPIRATA_DA:
        edges.append(Edge(rel.bottega_id, "ISPIRATA_DA", rel.artista_id))

    return edges


def build_adjacency(
    relation_types: frozenset[str] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Adiacenza NON orientata: nodo -> [(vicino, tipo_relazione), ...].

    `relation_types=None` include tutte le relazioni; passare
    `SEMANTIC_RELATION_TYPES` per escludere `VICINO` (prossimità fisica) e
    dimostrare la raggiungibilità puramente semantica.
    """
    adiacenza: dict[str, list[tuple[str, str]]] = {}
    for edge in _all_edges():
        if relation_types is not None and edge.tipo not in relation_types:
            continue
        adiacenza.setdefault(edge.da, []).append((edge.a, edge.tipo))
        adiacenza.setdefault(edge.a, []).append((edge.da, edge.tipo))
    return adiacenza


def shortest_path(
    origine: str,
    destinazione: str,
    relation_types: frozenset[str] | None = None,
) -> list[tuple[str, str, str]] | None:
    """BFS non orientata sul grafo canonico. Ritorna il cammino più corto
    come lista di `(nodo_da, tipo_relazione, nodo_a)`, oppure `None` se
    `destinazione` non è raggiungibile da `origine`."""
    if origine == destinazione:
        return []

    adiacenza = build_adjacency(relation_types)
    visitati = {origine}
    coda: deque[tuple[str, list[tuple[str, str, str]]]] = deque([(origine, [])])

    while coda:
        nodo, cammino = coda.popleft()
        for vicino, tipo in adiacenza.get(nodo, []):
            if vicino in visitati:
                continue
            nuovo_cammino = [*cammino, (nodo, tipo, vicino)]
            if vicino == destinazione:
                return nuovo_cammino
            visitati.add(vicino)
            coda.append((vicino, nuovo_cammino))

    return None


def vicino_degree() -> dict[str, int]:
    """Grado di ogni Luogo nella sola rete `VICINO` (non orientata)."""
    adiacenza = build_adjacency(frozenset({"VICINO"}))
    return {luogo.id: len(adiacenza.get(luogo.id, [])) for luogo in LUOGHI}
