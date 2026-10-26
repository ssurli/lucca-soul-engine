"""Guardia AST: lo scoring non legge MAI le coordinate (punti di arrivo / punto / lat / lon).

`GraphCandidate.punti_arrivo`, `ExperienceNode.punti_arrivo`, `Luogo.punto` e
`contracts.Punto` (ondata 3, compito 3) sono DATI DI POSIZIONE: servono al
trasferimento tra tappe e al link "Come arrivo qui", mai al punteggio. Se lo
scoring o il recommender li leggessero, la posizione di un luogo (o la vicinanza
a un partner) comprerebbe visibilita'.

Perimetro: `experience_engine.rules` e `recommender.ranking` per intero, piu' le
due funzioni di scoring vere ispezionate da sole (`rules.calcola_score` e la
chiusura `_score` di `ranking.costruisci_score_fn`). Il modulo `engine` NON e'
nel perimetro: il motore usa i punti per il tempo di trasferimento e, dopo la
selezione, per l'ordine di visita delle tappe GIÀ SCELTE
(`engine._riordina_per_vicinanza`, ondata 4) — mai per l'ordine per affinità;
la guardia sui suoi ordinamenti vive in `test_trasferimento_punti.py`.

Un riferimento e': attributo, nome, import o stringa (non docstring) che sia un
identificatore di posizione (`punti_arrivo`, `punto`, `punto_arrivo`, `lat`,
`lon`, `Punto`) o ne contenga il prefisso (`punti_arrivo*`, `punto_*`), oppure
una funzione o costante di distanza di `contracts.punti` (ondata 3, compito 4:
`distanza_a_piedi_m`, `distanza_linea_aria_m`, `punto_piu_vicino`,
`COEFFICIENTE_PERCORSO_PIEDI`).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import ModuleType

import pytest
from experience_engine import rules
from recommender import ranking

_ESATTI = frozenset({"punto", "punti", "lat", "lon", "lng", "latitudine", "longitudine"})
_PREFISSI = (
    "punti_arrivo",
    "punto_",
    "luogo_lat",
    "luogo_lon",
    "riferimento_lat",
    "riferimento_lon",
    # Distanze tra punti (`contracts.punti`): `punto_piu_vicino` e' gia' `punto_`.
    "distanza_a_piedi",
    "distanza_linea_aria",
    "coefficiente_percorso",
)


def _e_posizione(nome: str) -> bool:
    n = nome.lower()
    return n in _ESATTI or n.startswith(_PREFISSI)


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


def letture_posizione(radice: ast.AST) -> list[str]:
    docstring = _docstring_ids(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and _e_posizione(nodo.attr):
            trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and _e_posizione(nodo.id):
            trovate.append(nodo.id)
        elif isinstance(nodo, ast.arg) and _e_posizione(nodo.arg):
            trovate.append(nodo.arg)
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and _e_posizione(nodo.value)
        ):
            trovate.append(repr(nodo.value))
        elif isinstance(nodo, ast.alias) and _e_posizione(nodo.name.split(".")[-1]):
            trovate.append(f"import {nodo.name}")
    return trovate


@pytest.mark.parametrize(("etichetta", "modulo"), [("rules", rules), ("ranking", ranking)])
def test_rules_e_ranking_non_leggono_le_coordinate(etichetta: str, modulo: ModuleType) -> None:
    albero = ast.parse(inspect.getsource(modulo))
    funzioni = {n.name for n in ast.walk(albero) if isinstance(n, ast.FunctionDef)}
    attese = {"calcola_score"} if etichetta == "rules" else {"costruisci_score_fn", "_score"}
    assert attese <= funzioni, "perimetro della guardia incompleto"
    assert letture_posizione(albero) == [], (
        f"{modulo.__name__} non deve leggere le coordinate: dato di posizione, mai input di scoring"
    )


def test_calcola_score_e_la_chiusura_del_recommender_puliti_anche_da_sole() -> None:
    from graph.seed_lucca import VOCABOLARIO
    from recommender import InMemoryBehaviorEventRepository

    score_fn = ranking.costruisci_score_fn(
        InMemoryBehaviorEventRepository(), [], vocabolario=VOCABOLARIO
    )
    for fn in (rules.calcola_score, score_fn):
        albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        assert letture_posizione(albero) == [], getattr(fn, "__name__", fn)


def _letture(sorgente: str) -> list[str]:
    return letture_posizione(ast.parse(textwrap.dedent(sorgente)))


@pytest.mark.parametrize(
    "corpo",
    [
        "return len(candidate.punti_arrivo)",
        "return candidate.experience.punti_arrivo[0]",
        "return luogo.punto",
        "return p.lat + p.lon",
        'return getattr(candidate, "punti_arrivo")',
        'return candidate.model_dump()["punti_arrivo"]',
        "return isinstance(x, Punto) or Punto",
        "return punto_arrivo",
        "return distanza_a_piedi_m(a, b)",
        "return contracts.distanza_linea_aria_m(a, b)",
        "return punto_piu_vicino(a, candidate.x)",
        "return COEFFICIENTE_PERCORSO_PIEDI * x",
        "from contracts import distanza_a_piedi_m",
    ],
)
def test_la_guardia_scatta(corpo: str) -> None:
    assert _letture(f"def f(candidate, luogo, p, x):\n    {corpo}\n") != [], corpo


def test_la_guardia_non_ha_falsi_positivi_sul_profilo_e_ignora_le_docstring() -> None:
    sorgente = '''
        def calcola_score(candidate, profile, signal):
            """punti_arrivo nella docstring: ignorata"""
            return W_CURIOSITA * profile.curiosita + len(candidate.connessioni)
    '''
    assert _letture(sorgente) == []
