"""Test di `intelligence_index.distribuzione.distribuzione_flussi` —
l'indicatore che ci giudica (CLAUDE.md): l'entropia di Shannon normalizzata,
formula già negoziata (estratta da `tests/test_integration_wave3b.py`)."""

from __future__ import annotations

import math

from intelligence_index.distribuzione import distribuzione_flussi


def test_nessuna_tappa_e_massimo_per_definizione() -> None:
    # Nessuna tappa osservata: nulla da penalizzare.
    assert distribuzione_flussi([], 15) == 1.0


def test_un_solo_luogo_disponibile_e_caso_degenere() -> None:
    assert distribuzione_flussi(["unico-luogo"], 1) == 1.0
    assert distribuzione_flussi([], 0) == 1.0


def test_concentrazione_totale_su_un_luogo_e_zero() -> None:
    valore = distribuzione_flussi(["a", "a", "a", "a"], 4)
    assert valore == 0.0


def test_distribuzione_perfetta_su_tutti_i_luoghi_disponibili_e_uno() -> None:
    # 4 luoghi disponibili, ognuno compare con la stessa frequenza.
    valore = distribuzione_flussi(["a", "b", "c", "d"], 4)
    assert math.isclose(valore, 1.0, abs_tol=1e-9)


def test_distribuzione_parziale_su_sottoinsieme_e_intermedia() -> None:
    # 2 luoghi equamente frequentati, ma solo 2 dei 15 luoghi DISPONIBILI:
    # deve essere STRETTAMENTE minore di 1 (normalizzato sull'universo, non
    # sui soli luoghi comparsi) e strettamente maggiore di 0.
    valore = distribuzione_flussi(["a", "b", "a", "b"], 15)
    atteso = math.log(2) / math.log(15)
    assert math.isclose(valore, atteso, rel_tol=1e-9)
    assert 0.0 < valore < 1.0


def test_normalizzata_sui_luoghi_disponibili_non_su_quelli_comparsi() -> None:
    # Stessa distribuzione di frequenze (2 luoghi, 50/50), ma universi
    # disponibili diversi: il valore DEVE cambiare, perché la normalizzazione
    # è sull'intero universo di luoghi, non sui 2 comparsi.
    piccolo_universo = distribuzione_flussi(["a", "b", "a", "b"], 2)
    grande_universo = distribuzione_flussi(["a", "b", "a", "b"], 15)
    assert math.isclose(piccolo_universo, 1.0, abs_tol=1e-9)
    assert grande_universo < piccolo_universo


def test_valore_sempre_in_intervallo_01() -> None:
    for place_ids, n in [
        (["a"], 15),
        (["a", "b", "c"], 15),
        (["a"] * 100 + ["b"], 15),
        (list("abcdefghij"), 15),
    ]:
        valore = distribuzione_flussi(place_ids, n)
        assert -1e-9 <= valore <= 1.0 + 1e-9
