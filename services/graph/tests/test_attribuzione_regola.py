"""Regola dell'attribuzione: la clausola ", bottega di {mestiere}" è omessa
quando il nome contiene già il mestiere (confronto casefold)."""

from __future__ import annotations

import pytest
from graph import attribuzione
from graph.seed_lucca import DATASET


def test_nome_contiene_il_mestiere_clausola_omessa() -> None:
    assert (
        attribuzione.testo_attribuzione("Pasticceria", "pasticceria", True)
        == "Offerta da Pasticceria (esempio dimostrativo)."
    )


def test_nome_non_contiene_il_mestiere_clausola_presente() -> None:
    assert attribuzione.testo_attribuzione("Stamperia a torchio", "stampa", True) == (
        "Offerta da Stamperia a torchio, bottega di stampa (esempio dimostrativo)."
    )


@pytest.mark.parametrize(
    ("nome", "mestiere"),
    [
        ("PASTICCERIA", "pasticceria"),
        ("pasticceria", "PASTICCERIA"),
        ("Bottega di Liuteria", "liuteria"),
    ],
)
def test_maiuscole_diverse_stessa_regola(nome: str, mestiere: str) -> None:
    assert attribuzione.testo_attribuzione(nome, mestiere, False) == f"Offerta da {nome}."


def test_fittizio_si_e_no() -> None:
    assert (
        attribuzione.testo_attribuzione("Pasticceria", "pasticceria", False)
        == "Offerta da Pasticceria."
    )
    assert (
        attribuzione.testo_attribuzione("Atelier", "stampa", False)
        == "Offerta da Atelier, bottega di stampa."
    )
    assert attribuzione.testo_attribuzione("Atelier", "stampa", True).endswith(
        "(esempio dimostrativo)."
    )


def test_cinque_botteghe_del_seed() -> None:
    attese = {
        "liuteria-lucchese": "Offerta da Bottega di liuteria (esempio dimostrativo).",
        "ceramica-lucca": "Offerta da Laboratorio di ceramica (esempio dimostrativo).",
        "stamperia-lucca": (
            "Offerta da Stamperia a torchio, bottega di stampa (esempio dimostrativo)."
        ),
        "pasticceria-storica": "Offerta da Pasticceria (esempio dimostrativo).",
        "tessitura-lucca": "Offerta da Laboratorio di tessitura (esempio dimostrativo).",
    }
    ottenute = {
        b.id: attribuzione.testo_attribuzione(b.nome, b.mestiere, b.fittizio)
        for b in DATASET.botteghe
    }
    assert ottenute == attese
