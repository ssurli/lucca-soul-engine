"""Test del gate di privacy k-anonimato (`intelligence_index.soglia`)."""

from __future__ import annotations

import pytest
from intelligence_index.soglia import (
    SOGLIA_MINIMA_PERSONE,
    DatiInsufficientiError,
    persone_sufficienti,
    richiedi_soglia,
    valore_se_soglia,
)


def test_soglia_minima_e_10() -> None:
    # Valore concordato col committente per questa wave — un cambiamento qui
    # deve essere una decisione esplicita, non un refactor incidentale.
    assert SOGLIA_MINIMA_PERSONE == 10


def test_persone_sufficienti_deduplica() -> None:
    # Stesso person_id ripetuto 20 volte conta come 1 sola persona: sotto
    # soglia nonostante 20 eventi.
    assert persone_sufficienti(["p1"] * 20) is False
    assert persone_sufficienti([f"p{i}" for i in range(10)]) is True
    assert persone_sufficienti([f"p{i}" for i in range(9)]) is False


def test_richiedi_soglia_non_solleva_sopra_soglia() -> None:
    richiedi_soglia([f"p{i}" for i in range(10)], "contesto-di-prova")  # non deve sollevare


def test_richiedi_soglia_solleva_sotto_soglia_con_messaggio_leggibile() -> None:
    with pytest.raises(DatiInsufficientiError) as exc_info:
        richiedi_soglia([f"p{i}" for i in range(9)], "attivazione_locale")
    errore = exc_info.value
    assert errore.contesto == "attivazione_locale"
    assert errore.n_persone == 9
    assert errore.soglia == SOGLIA_MINIMA_PERSONE
    assert "attivazione_locale" in str(errore)
    assert "9" in str(errore)


def test_richiedi_soglia_rispetta_soglia_personalizzata() -> None:
    richiedi_soglia(["p1", "p2", "p3"], "contesto", soglia=3)  # non deve sollevare
    with pytest.raises(DatiInsufficientiError):
        richiedi_soglia(["p1", "p2"], "contesto", soglia=3)


def test_valore_se_soglia_ritorna_none_sotto_soglia() -> None:
    assert valore_se_soglia(["p1", "p2"], 0.42) is None


def test_valore_se_soglia_ritorna_il_valore_sopra_soglia() -> None:
    assert valore_se_soglia([f"p{i}" for i in range(10)], 0.42) == 0.42
