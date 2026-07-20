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

Wave 4 (Urban Intelligence Index) aggiunge due primitive, entrambe replicate
sulla sorgente Neo4j live in `graph.metrics` (stessa interfaccia logica di
`graph.source.CandidateSource`):

- `grado_semantico()` — grado CULTURALE di ogni Luogo (per `attivazione_
  locale`), non il grado nella rete `VICINO` (respinto dal committente:
  misura la centralità nella PIANTA della città, non quanto un luogo è
  raccontato culturalmente).
- `non_connected_place_pairs()` — snapshot di connettività `VICINO` a un
  istante T (per `nuovi_percorsi`): quali coppie di Luoghi non sono ancora
  collegate direttamente.

Le relazioni sono trattate come NON orientate per la ricerca dei cammini: lo
scopo è il RACCONTO delle connessioni (chi è legato a cosa), non l'inferenza
causale — la stessa ragione per cui `VICINO` è già simmetrico nel dominio, e
per cui `graph.source.SeedCandidateSource` legge `LEGATO_A`/`OFFRE` in
entrambe le direzioni.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations

from graph.seed_lucca import (
    BOTTEGA_EVOCA,
    BOTTEGA_ISPIRATA_DA,
    BOTTEGHE,
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


def grado_semantico() -> dict[str, int]:
    """Grado semantico di ogni Luogo: quante relazioni CULTURALI
    (`SEMANTIC_RELATION_TYPES` — tutto tranne `VICINO`) lo toccano, INCLUSE
    quelle delle Botteghe che ospita (`Bottega.place_id`).

    Serve all'indicatore `attivazione_locale` (Wave 4, Urban Intelligence
    Index): il committente ha respinto il grado nella rete `VICINO` (misura
    la centralità nella PIANTA della città — una scelta di modellazione del
    seed, non un fatto culturale) e ha chiesto questo al suo posto. Una
    bottega culturalmente scollegata (poche `EVOCA`/`ISPIRATA_DA`) deve
    rendere "minore" il luogo che la ospita, anche se quel luogo è
    fisicamente centralissimo — l'esempio del committente: una bottega in
    via Fillungo, circondata da dieci vicini fisici ma culturalmente
    invisibile. Per questo il grado di una Bottega ospitata si SOMMA a
    quello del Luogo, invece di essere ignorato.

    "Luogo minore" (soglia, tipicamente la mediana) NON è compito di questa
    funzione: chi applica la soglia la riceve come parametro esplicito, mai
    hardcoded qui (vedi `services/intelligence-index`)."""
    adiacenza = build_adjacency(SEMANTIC_RELATION_TYPES)
    gradi: dict[str, int] = {}
    for luogo in LUOGHI:
        grado = len(adiacenza.get(luogo.id, []))
        for bottega in BOTTEGHE:
            if bottega.place_id == luogo.id:
                grado += len(adiacenza.get(bottega.id, []))
        gradi[luogo.id] = grado
    return gradi


def non_connected_place_pairs(
    at: datetime | None = None,
) -> tuple[set[frozenset[str]], int]:
    """Coppie di `place_id` NON collegate direttamente da `VICINO` (mai per
    cammini semantici) in uno snapshot del grafo congelato all'istante `at`.

    Serve all'indicatore `nuovi_percorsi` (Wave 4, Urban Intelligence
    Index): confrontando questo insieme a due istanti T0 e T1 (chiamando
    questa funzione due volte, con `at` diverso), chi calcola l'indicatore
    vede quali coppie erano non-connesse a T0 e sono diventate connesse
    entro T1 — la definizione stessa di "percorso nuovo". Questa funzione
    espone solo lo snapshot grezzo: il confronto tra due snapshot e il
    calcolo dell'indicatore NON sono compito di `graph` (vedi
    `services/intelligence-index`).

    `at=None` (default) = snapshot "adesso": TUTTI gli archi `VICINO`
    correnti, senza filtro temporale. `at` timezone-aware (`datetime.now(
    UTC)` tipicamente) = solo gli archi con `creato_il <= at` — coerente con
    `RelazioneVicino.creato_il` (vedi `graph.seed_lucca.VICINO_EPOCA`: gli
    archi del seed iniziale sono "sempre esistiti", quindi entrano in
    qualunque snapshot, anche il più antico).

    Ritorna `(coppie_non_connesse, len(coppie_non_connesse))`: il secondo
    valore è il denominatore della normalizzazione a valle (`nuovi_percorsi`
    è un rapporto, non un conteggio assoluto — vedi `docs/DATA_CONTRACTS.md`
    §7). Ogni coppia è un `frozenset({place_id_a, place_id_b})`: `VICINO` è
    non orientata nel dominio, la stessa ragione per cui `build_adjacency`
    la tratta come tale."""
    archi_nello_snapshot = {
        frozenset({rel.da_id, rel.a_id}) for rel in VICINO if at is None or rel.creato_il <= at
    }
    tutte_le_coppie = {frozenset({a.id, b.id}) for a, b in combinations(LUOGHI, 2)}
    non_connesse = tutte_le_coppie - archi_nello_snapshot
    return non_connesse, len(non_connesse)
