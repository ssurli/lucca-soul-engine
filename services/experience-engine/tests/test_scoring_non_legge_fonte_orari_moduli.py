"""Guardia AST: `fonte_orari` non e' letta da NESSUNA funzione di scoring ne' dal motore.

`test_scoring_non_legge_fonte_orari.py` ispeziona la sola `rules.calcola_score`.
Qui il perimetro e' allargato ai moduli interi: `experience_engine.rules`,
`experience_engine.engine` (ordinamenti e selezione) e `recommender.ranking`
(la `score_fn` calda). `fonte_orari` e' solo testo di trasparenza: se uno di
questi moduli la leggesse, la fonte di un orario potrebbe favorire un candidato.

Un riferimento e': attributo, nome, argomento, parola chiave, import o stringa
(non docstring) che contenga `fonte_orari`.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import ModuleType

import pytest
from experience_engine import engine, rules
from recommender import ranking

MARCATORE = "fonte_orari"


def _docstring_ids(radice: ast.AST) -> set[int]:
    ids: set[int] = set()
    for n in ast.walk(radice):
        corpo = getattr(n, "body", None)
        if (
            isinstance(corpo, list)
            and corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            ids.add(id(corpo[0].value))
    return ids


def letture_fonte_orari(radice: ast.AST) -> list[str]:
    docstring = _docstring_ids(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and MARCATORE in nodo.attr.lower():
            trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and MARCATORE in nodo.id.lower():
            trovate.append(nodo.id)
        elif isinstance(nodo, ast.arg) and MARCATORE in nodo.arg.lower():
            trovate.append(nodo.arg)
        elif isinstance(nodo, ast.keyword) and nodo.arg and MARCATORE in nodo.arg.lower():
            trovate.append(nodo.arg)
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and MARCATORE in nodo.value.lower()
        ):
            trovate.append(repr(nodo.value))
        elif isinstance(nodo, ast.alias) and MARCATORE in nodo.name.lower():
            trovate.append(f"import {nodo.name}")
    return trovate


@pytest.mark.parametrize(
    ("etichetta", "modulo"), [("rules", rules), ("engine", engine), ("ranking", ranking)]
)
def test_i_moduli_di_scoring_e_motore_non_leggono_fonte_orari(
    etichetta: str, modulo: ModuleType
) -> None:
    albero = ast.parse(inspect.getsource(modulo))
    # Il perimetro non e' vuoto: il modulo contiene funzioni vere.
    assert sum(isinstance(n, ast.FunctionDef) for n in ast.walk(albero)) >= 3, etichetta
    assert letture_fonte_orari(albero) == [], (
        f"{modulo.__name__} non deve leggere `fonte_orari`: e' solo testo di trasparenza"
    )


def _letture(sorgente: str) -> list[str]:
    return letture_fonte_orari(ast.parse(textwrap.dedent(sorgente)))


@pytest.mark.parametrize(
    "corpo",
    [
        "return 1.0 if candidate.experience.fonte_orari else 0.0",
        'return getattr(candidate.experience, "fonte_orari")',
        'return candidate.model_dump()["experience"]["fonte_orari"]',
        "return fonte_orari",
        "return f(fonte_orari=1)",
        "from contracts import fonte_orari",
    ],
)
def test_la_guardia_scatta(corpo: str) -> None:
    assert _letture(f"def f(candidate):\n    {corpo}\n") != [], corpo


def test_la_guardia_ignora_le_docstring() -> None:
    sorgente = '''
        def f(candidate):
            """fonte_orari nella docstring: ignorata"""
            return candidate.titolo
    '''
    assert _letture(sorgente) == []
