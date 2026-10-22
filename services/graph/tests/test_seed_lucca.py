"""Test sul dataset canonico: conteggi minimi e integrità referenziale.

`graph.seed_lucca._validate()` gira già a import-time (fail fast); questi
test fissano i CONTEGGI richiesti dalla Wave 1 come rete di sicurezza contro
regressioni silenziose (es. qualcuno rimuove un'esperienza per errore).
"""

from __future__ import annotations

from graph.seed_lucca import ARTISTI, BOTTEGHE, ESPERIENZE, LEGATO_A, LUOGHI, TEMI, VICINO


def test_almeno_dodici_luoghi() -> None:
    assert 12 <= len(LUOGHI) <= 24


def test_cinque_botteghe() -> None:
    assert len(BOTTEGHE) == 5


def test_almeno_quindici_esperienze() -> None:
    assert len(ESPERIENZE) >= 15


def test_artisti_e_temi_presenti() -> None:
    assert len(ARTISTI) >= 2
    assert len(TEMI) >= 5


def test_relazioni_presenti() -> None:
    assert len(VICINO) > 0
    assert len(LEGATO_A) > 0


def test_esperienze_hanno_mix_al_chiuso() -> None:
    al_chiuso = sum(1 for e in ESPERIENZE if e.al_chiuso)
    all_aperto = len(ESPERIENZE) - al_chiuso
    assert al_chiuso > 0
    assert all_aperto > 0


def test_esperienze_hanno_mix_accessibile() -> None:
    accessibili = sum(1 for e in ESPERIENZE if e.accessibile)
    non_accessibili = len(ESPERIENZE) - accessibili
    assert accessibili > 0
    assert non_accessibili > 0


def test_durate_variano_tra_10_e_90_minuti() -> None:
    durate = [e.durata_min for e in ESPERIENZE]
    assert min(durate) <= 30
    assert max(durate) >= 60
    assert all(10 <= d <= 90 for d in durate)


def test_temi_diversi_tra_le_esperienze() -> None:
    temi_usati = {tema for e in ESPERIENZE for tema in e.temi}
    assert len(temi_usati) >= 8
