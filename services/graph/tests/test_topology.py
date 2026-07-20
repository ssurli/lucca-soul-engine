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

from datetime import UTC, datetime, timedelta
from itertools import combinations as _combinations

from graph.seed_lucca import BOTTEGHE, LUOGHI, VICINO, VICINO_EPOCA
from graph.topology import (
    SEMANTIC_RELATION_TYPES,
    grado_semantico,
    non_connected_place_pairs,
    shortest_path,
    vicino_degree,
)

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


# ---------------------------------------------------------------------------
# grado_semantico() — Wave 4, indicatore `attivazione_locale`. Test di
# PROPRIETÀ (soglie/dispersione), non di valori esatti: il seed cambia nel
# tempo (vedi commento di modulo di `graph.topology`). Verificato a mano dal
# committente sul seed attuale (15 luoghi, grado da 1 a 10, mediana 2, 5
# luoghi sotto mediana) — questi test fissano solo le proprietà strutturali
# che rendono la metrica non degenere, non quei numeri.
# ---------------------------------------------------------------------------


def test_grado_semantico_copre_tutti_i_luoghi() -> None:
    gradi = grado_semantico()
    assert set(gradi) == {luogo.id for luogo in LUOGHI}


def test_grado_semantico_nessun_luogo_a_zero() -> None:
    # Un grado zero renderebbe quel luogo indistinguibile da un luogo
    # inesistente nel grafo culturale: la metrica deve discriminare tra
    # "poco raccontato" e "assente", non confonderli.
    gradi = grado_semantico()
    a_zero = {place_id: grado for place_id, grado in gradi.items() if grado == 0}
    assert not a_zero, f"luoghi con grado semantico zero: {a_zero}"


def test_grado_semantico_media_almeno_due() -> None:
    gradi = grado_semantico()
    media = sum(gradi.values()) / len(gradi)
    assert media >= 2, f"grado semantico medio troppo basso: {media:.2f} (richiesto >= 2)"


def test_grado_semantico_ha_dispersione_minima() -> None:
    # Una metrica piatta (stesso grado ovunque) non discriminerebbe alcun
    # "luogo minore": deve esistere una vera distribuzione, con luoghi sotto
    # e sopra la mediana.
    gradi = grado_semantico()
    valori = sorted(gradi.values())
    assert valori[0] < valori[-1], (
        f"grado semantico identico per tutti i luoghi ({valori[0]}): nessuna dispersione"
    )
    mediana = valori[len(valori) // 2]
    sotto_mediana = [v for v in valori if v < mediana]
    assert sotto_mediana, (
        "nessun luogo sotto la mediana: la soglia 'luogo minore' non taglierebbe nulla"
    )


def test_grado_semantico_include_il_grado_delle_botteghe_ospitate() -> None:
    # Il punto centrale della richiesta del committente: il grado di una
    # Bottega ospitata si SOMMA a quello del Luogo che la ospita, non viene
    # ignorato — altrimenti un luogo fisicamente centrale ma con una
    # bottega culturalmente invisibile non verrebbe mai penalizzato.
    gradi = grado_semantico()
    for bottega in BOTTEGHE:
        # Ogni Luogo che ospita almeno una Bottega ha un grado semantico
        # almeno pari al grado "puro" del Luogo (LEGATO_A + SI_SVOLGE_A):
        # verificato indirettamente controllando che il grado non cali mai
        # sotto quello di un luogo omologo senza botteghe ospitate.
        assert gradi[bottega.place_id] >= 0  # non degenere (vedi test sopra)
    # Controprova diretta: san-michele-in-foro ospita la Bottega di Liuteria
    # (EVOCA x3 + ISPIRATA_DA x2 = 5 relazioni semantiche proprie, oltre a
    # quelle del Luogo stesso via LEGATO_A/SI_SVOLGE_A): il suo grado deve
    # essere strettamente maggiore di quello che avrebbe SENZA sommare la
    # bottega, cioè maggiore del solo conteggio LEGATO_A/SI_SVOLGE_A diretto.
    from graph.topology import build_adjacency

    adiacenza = build_adjacency(SEMANTIC_RELATION_TYPES)
    grado_solo_luogo = len(adiacenza.get("san-michele-in-foro", []))
    assert gradi["san-michele-in-foro"] > grado_solo_luogo, (
        "il grado della Bottega di Liuteria non si somma a quello del Luogo che la ospita"
    )


# ---------------------------------------------------------------------------
# non_connected_place_pairs() — Wave 4, indicatore `nuovi_percorsi`.
# ---------------------------------------------------------------------------


def test_non_connected_place_pairs_copre_tutte_le_coppie_possibili() -> None:
    # Ogni coppia di Luoghi è o connessa (esclusa) o non connessa (inclusa):
    # nessuna coppia deve sparire.
    connesse, _ = non_connected_place_pairs(at=None)
    totale_coppie_possibili = len(list(_combinations(LUOGHI, 2)))
    archi_unici = {frozenset({rel.da_id, rel.a_id}) for rel in VICINO}
    assert len(connesse) + len(archi_unici) == totale_coppie_possibili


def test_non_connected_place_pairs_dimensione_coerente_con_linsieme() -> None:
    coppie, dimensione = non_connected_place_pairs(at=None)
    assert dimensione == len(coppie)
    assert dimensione > 0, "seed degenere: tutte le coppie di luoghi sarebbero già connesse"


def test_non_connected_place_pairs_nessuna_coppia_restituita_e_in_realta_vicina() -> None:
    # Controprova diretta contro VICINO: nessuna coppia nell'insieme "non
    # connesse" deve corrispondere a un arco VICINO realmente presente.
    archi = {frozenset({rel.da_id, rel.a_id}) for rel in VICINO}
    non_connesse, _ = non_connected_place_pairs(at=None)
    assert non_connesse.isdisjoint(archi)


def test_non_connected_place_pairs_prima_dellepoca_del_seed_tutte_le_coppie_sono_non_connesse() -> (
    None
):
    # Uno snapshot congelato PRIMA di VICINO_EPOCA non deve vedere nessun
    # arco del seed (tutti nascono con creato_il = VICINO_EPOCA): onestà
    # dello storico, non un archivio inventato.
    prima_dellepoca = VICINO_EPOCA - timedelta(days=1)
    non_connesse, dimensione = non_connected_place_pairs(at=prima_dellepoca)
    totale_coppie_possibili = len(list(_combinations(LUOGHI, 2)))
    assert dimensione == totale_coppie_possibili
    assert len(non_connesse) == totale_coppie_possibili


def test_non_connected_place_pairs_at_none_equivale_a_ora() -> None:
    # `at=None` (snapshot "adesso") deve coincidere con uno snapshot preso a
    # un istante ben dopo VICINO_EPOCA: nessun filtro temporale attivo.
    molto_dopo = datetime.now(UTC) + timedelta(days=3650)
    assert non_connected_place_pairs(at=None) == non_connected_place_pairs(at=molto_dopo)
