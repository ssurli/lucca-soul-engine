"""Guardia AST: lo scoring non legge MAI `fonte_orari`.

`fonte_orari` e' il nome della fonte degli orari: solo testo di trasparenza.
Se `calcola_score` la leggesse, una fonte potrebbe favorire un candidato.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from pathlib import Path

from experience_engine import rules

sys.path.insert(0, str(Path(__file__).parent))
from test_scoring_non_legge_orari import _nomi_usati  # noqa: E402


def test_calcola_score_non_legge_fonte_orari() -> None:
    albero = ast.parse(textwrap.dedent(inspect.getsource(rules.calcola_score)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    usati = {n.lower() for n in _nomi_usati(funzione)}
    assert not any("fonte" in n for n in usati), (
        "calcola_score non deve riferirsi a 'fonte_orari' (ne' a fonti): e' solo testo"
    )


def test_la_guardia_scatta_su_un_accesso_a_fonte_orari() -> None:
    sorgente = textwrap.dedent(
        '''
        def f(candidate):
            return 1.0 if candidate.experience.fonte_orari else 0.0
        '''
    )
    funzione = ast.parse(sorgente).body[0]
    assert isinstance(funzione, ast.FunctionDef)
    assert "fonte_orari" in _nomi_usati(funzione)
