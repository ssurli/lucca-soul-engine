"""Test di topologia — la prova del concetto richiesta dal committente dopo
la diagnosi su Aura del 2026-07-14: il grafo deve essere una RETE
camminabile (non una catena) e i percorsi SEMANTICI devono collegare artisti
pertinenti a botteghe, indipendentemente dalla prossimità fisica (`VICINO`).

Diagnosi originale: densità media 2,3 vicini/luogo; 4 vicoli ciechi con un
solo vicino (`casa-puccini`, `orto-botanico`, `baluardo-san-paolino`,
`museo-nazionale-guinigi`); la Bottega di Liuteria mai raggiunta dai
percorsi che partono da Puccini.

N canonico = 3 salti: è la lunghezza massima che riflette ancora la
narrazione del White Paper (Artista -> Luogo -> Esperienza -> Bottega, la
catena minima quando non esiste una relazione diretta) senza essere così
larga da nascondere un grafo comunque debolmente connesso. Nel seed attuale
il cammino trovato è più corto (`ISPIRATA_DA` diretto), ma il test verifica
la soglia, non il valore esatto: la fonte di verità resta `seed_lucca.py`.
"""

from __future__ import annotations

from graph.seed_lucca import LUOGHI
from graph.topology import SEMANTIC_RELATION_TYPES, shortest_path, vicino_degree

CANONICAL_MAX_HOPS = 3

EX_VICOLI_CIECHI = [
    "casa-puccini",
    "orto-botanico",
    "baluardo-san-paolino",
    "museo-nazionale-guinigi",
]


def test_densita_media_vicino_almeno_quattro() -> None:
    gradi = vicino_degree()
    media = sum(gradi.values()) / len(gradi)
    assert media >= 4, f"densità media VICINO troppo bassa: {media:.2f} (richiesto >= 4)"


def test_nessun_luogo_con_meno_di_due_vicini() -> None:
    gradi = vicino_degree()
    scarsi = {place_id: grado for place_id, grado in gradi.items() if grado < 2}
    assert not scarsi, f"luoghi con meno di 2 vicini: {scarsi}"


def test_ex_vicoli_ciechi_ora_hanno_almeno_due_vicini() -> None:
    # I quattro luoghi diagnosticati su Aura come vicoli ciechi (1 solo
    # vicino): la correzione deve toccarli esplicitamente, non solo alzare
    # la media.
    gradi = vicino_degree()
    for place_id in EX_VICOLI_CIECHI:
        assert place_id in gradi, f"{place_id} non è nel seed"
        assert gradi[place_id] >= 2, (
            f"{place_id}: ancora un vicolo cieco ({gradi[place_id]} vicini)"
        )


def test_nessun_nodo_isolato_nella_rete_vicino() -> None:
    gradi = vicino_degree()
    for luogo in LUOGHI:
        assert gradi.get(luogo.id, 0) > 0, f"{luogo.id} è isolato nella rete VICINO"


def test_tutti_i_luoghi_sono_in_una_singola_componente_connessa() -> None:
    # Una rete densa ma spezzata in isole non basterebbe: verifichiamo che
    # TUTTI i luoghi siano raggiungibili l'uno dall'altro via VICINO.
    from collections import deque

    from graph.topology import build_adjacency

    adiacenza = build_adjacency(frozenset({"VICINO"}))
    partenza = LUOGHI[0].id
    visitati = {partenza}
    coda = deque([partenza])
    while coda:
        nodo = coda.popleft()
        for vicino, _tipo in adiacenza.get(nodo, []):
            if vicino not in visitati:
                visitati.add(vicino)
                coda.append(vicino)
    tutti_i_luoghi = {luogo.id for luogo in LUOGHI}
    assert visitati == tutti_i_luoghi, f"luoghi non raggiungibili: {tutti_i_luoghi - visitati}"


def test_puccini_raggiunge_la_bottega_di_liuteria_per_connessioni_semantiche() -> None:
    # Il cammino canonico del White Paper: un artista che, per relazioni di
    # SIGNIFICATO (non di prossimità fisica), porta a un artigiano
    # pertinente. `relation_types=SEMANTIC_RELATION_TYPES` esclude `VICINO`
    # esplicitamente dalla ricerca.
    cammino = shortest_path(
        "artista-puccini", "liuteria-lucchese", relation_types=SEMANTIC_RELATION_TYPES
    )
    assert cammino is not None, (
        "Puccini non raggiunge la Bottega di Liuteria per sole connessioni semantiche"
    )
    assert len(cammino) <= CANONICAL_MAX_HOPS, (
        f"cammino semantico troppo lungo ({len(cammino)} salti, max {CANONICAL_MAX_HOPS}): "
        f"{cammino}"
    )
    # Nessun passo del cammino deve usare VICINO: la raggiungibilità è
    # dimostrata SOLO per connessioni semantiche.
    for _da, tipo, _a in cammino:
        assert tipo != "VICINO", f"il cammino semantico usa VICINO: {cammino}"


def test_puccini_non_raggiunge_la_bottega_di_liuteria_solo_via_vicino() -> None:
    # Controprova: senza le relazioni semantiche (solo VICINO), Puccini
    # (nodo Artista) non è nemmeno un nodo della rete VICINO — la
    # raggiungibilità del liutaio a partire da un artista non è un
    # sottoprodotto della prossimità fisica, ma una relazione a sé.
    cammino = shortest_path(
        "artista-puccini", "liuteria-lucchese", relation_types=frozenset({"VICINO"})
    )
    assert cammino is None
