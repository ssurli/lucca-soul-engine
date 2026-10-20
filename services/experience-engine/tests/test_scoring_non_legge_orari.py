"""Guardia AST: lo scoring non legge MAI orari, arrivi o istanti.

Gli orari sono un filtro duro (`rules.aperta_durante`, applicato all'arrivo
dalla composizione e dall'adattamento): possono solo ESCLUDERE. Se
`calcola_score` li leggesse, un orario potrebbe favorire un candidato. Questa
guardia affianca `test_scoring_non_usa_partner_id_ne_prezzo` (test_engine.py,
campi commerciali) e ispeziona identificatori, attributi, argomenti, keyword e
stringhe del CODICE di `calcola_score` (docstring esclusa).
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from experience_engine import rules

VIETATI = (
    "orari_apertura",
    "arrivo",
    "istante",
    "giorno_settimana",
    "aperta_durante",
    "rientra_in_orario",
)


def _nomi_usati(funzione: ast.FunctionDef) -> set[str]:
    corpo = funzione.body
    if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
        corpo = corpo[1:]  # docstring: non e' codice eseguito
    nomi: set[str] = set()
    for istruzione in corpo:
        for nodo in ast.walk(istruzione):
            if isinstance(nodo, ast.Name):
                nomi.add(nodo.id)
            elif isinstance(nodo, ast.Attribute):
                nomi.add(nodo.attr)
            elif isinstance(nodo, ast.keyword) and nodo.arg:
                nomi.add(nodo.arg)
            elif isinstance(nodo, ast.arg):
                nomi.add(nodo.arg)
            elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                nomi.add(nodo.value)
    nomi.update(a.arg for a in funzione.args.args + funzione.args.kwonlyargs)
    return nomi


def test_calcola_score_non_legge_orari_arrivo_istante_giorno() -> None:
    albero = ast.parse(textwrap.dedent(inspect.getsource(rules.calcola_score)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    usati = {n.lower() for n in _nomi_usati(funzione)}
    for vietato in VIETATI:
        assert not any(vietato in n for n in usati), (
            f"calcola_score non deve riferirsi a '{vietato}': gli orari sono un "
            "filtro duro, mai un fattore di score"
        )


def test_calcola_score_non_legge_sospesa() -> None:
    """`sospesa` e' un interruttore di presenza (`passa_filtri_statici`), mai
    un fattore di score: ne' penalita' ne' bonus."""
    albero = ast.parse(textwrap.dedent(inspect.getsource(rules.calcola_score)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    usati = {n.lower() for n in _nomi_usati(funzione)}
    assert not any("sospesa" in n for n in usati), (
        "calcola_score non deve riferirsi a 'sospesa': e' un filtro di presenza"
    )


def test_la_guardia_sospesa_scatta_su_un_accesso_attributo() -> None:
    sorgente = textwrap.dedent(
        '''
        def f(candidate):
            return 0.0 if candidate.experience.sospesa else 1.0
        '''
    )
    funzione = ast.parse(sorgente).body[0]
    assert isinstance(funzione, ast.FunctionDef)
    assert "sospesa" in _nomi_usati(funzione)


def test_la_guardia_sa_riconoscere_un_riferimento_vietato() -> None:
    """Controllo di sensibilita': la guardia scatta davvero."""
    sorgente = textwrap.dedent(
        '''
        def f(candidate, signal):
            """arrivo nella docstring: ignorato"""
            return rientra_in_orario(
                candidate.experience.orari_apertura, signal.giorno_settimana, signal.ora
            )
        '''
    )
    funzione = ast.parse(sorgente).body[0]
    assert isinstance(funzione, ast.FunctionDef)
    usati = _nomi_usati(funzione)
    assert {"rientra_in_orario", "orari_apertura", "giorno_settimana"} <= usati
    assert "arrivo" not in usati
