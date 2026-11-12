"""Guardia AST: lo scoring e la scelta non leggono MAI se un partner e' dimostrativo.

`GraphCandidate.partner_dimostrativo` e `ItineraryStop.dimostrativa` sono SOLA
presentazione: dicono all'app che la bottega che offre la tappa e' un esempio
(`Bottega.fittizio=True`), non un esercizio reale. Se una funzione che sceglie
o ordina li leggesse, l'essere (o non essere) un partner dimostrativo
cambierebbe la visibilita' di una tappa: un canale commerciale nello scoring,
vietato da "nessuno spazio e' acquistabile".

Stesso schema di `test_scoring_non_legge_curiosita.py` (modulo intero con
allowlist), perche' i costruttori di tappe DEVONO copiare il campo. Un
riferimento e' un attributo, un nome, un argomento, un import o una stringa
(docstring escluse) che contenga un marcatore: `dimostrativ` copre
`partner_dimostrativo` e `dimostrativa`, `fittizi` il campo d'origine
`Bottega.fittizio`. Una keyword di costruzione (`ItineraryStop(dimostrativa=...)`)
non e' una lettura ed e' ammessa ovunque; il suo VALORE, se legge il campo,
viene comunque trovato (e' un attributo).

Perimetro:
- `experience_engine.rules`: tutto (`calcola_score`, filtri duri, segnali...);
- `recommender.ranking`: tutto (`costruisci_score_fn` con la chiusura `_score`,
  quote, esposizione, gating);
- `experience_engine.engine`: tutto TRANNE i costruttori di tappe
  (`AMMESSE_NEL_MOTORE`). In particolare `_ordina_per_score`,
  `_seleziona_tappe`, `_migliore_alternativa`, `compose_itinerary`,
  `adapt_itinerary` sono controllate.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import ModuleType

import pytest
from experience_engine import engine, rules
from recommender import ranking

MARCATORI = ("dimostrativ", "fittizi")


def _marcato(testo: str) -> bool:
    return any(m in testo.lower() for m in MARCATORI)


#: Le sole funzioni del motore che possono leggere il campo: lo copiano sulla
#: tappa, non scelgono ne' ordinano. `_stub_da_stop` non serve: fissa
#: `partner_dimostrativo=False` con una keyword, che non e' una lettura.
AMMESSE_NEL_MOTORE = frozenset({
    "_costruisci_stops",
    "_narrazione_tappa",
})

#: Funzioni di scoring/scelta che il perimetro DEVE contenere (non vacuita').
ATTESE = {
    "rules": {"calcola_score", "passa_filtri_statici", "passa_filtri_duri", "affinita_temi"},
    "ranking": {
        "costruisci_score_fn",
        "_score",
        "_conteggio_grezzo_per_place",
        "_quota_storica_per_place",
        "_quota_strutturale_per_place",
        "_esposizione_top_k_per_place",
        "_applica_gating_esposizione",
    },
    "engine": {
        "_ordina_per_score",
        "_seleziona_tappe",
        "_migliore_alternativa",
        "compose_itinerary",
        "adapt_itinerary",
        "_taglia_per_stanchezza",
        "_taglia_fuori_orario",
        "_ricostruisci_stops",
        "_marca_reason",
        "_stub_da_stop",
    },
}


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


def letture_dimostrativa(radice: ast.AST) -> list[str]:
    """Riferimenti al campo dimostrativo in `radice` (docstring escluse).

    Vuota = nessuna lettura. Ogni voce e' il frammento di codice colpevole."""
    docstring = _docstring_ids(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and _marcato(nodo.attr):
            trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and _marcato(nodo.id):
            trovate.append(nodo.id)
        elif isinstance(nodo, ast.arg) and _marcato(nodo.arg):
            trovate.append(nodo.arg)
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and _marcato(nodo.value)
        ):
            trovate.append(repr(nodo.value))
        elif isinstance(nodo, ast.alias) and _marcato(nodo.name):
            trovate.append(f"import {nodo.name}")
    return trovate


def _albero(modulo: ModuleType) -> ast.Module:
    return ast.parse(inspect.getsource(modulo))


def _nomi_funzioni(radice: ast.AST) -> set[str]:
    return {
        n.name for n in ast.walk(radice) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _parti_del_modulo(albero: ast.Module) -> list[tuple[str, ast.AST]]:
    return [
        (getattr(nodo, "name", f"<riga {getattr(nodo, 'lineno', '?')}>"), nodo)
        for nodo in albero.body
    ]


# ---------------------------------------------------------------------------
# La guardia sul codice di produzione
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("etichetta", "modulo"), [("rules", rules), ("ranking", ranking)])
def test_rules_e_ranking_non_leggono_il_partner_dimostrativo(
    etichetta: str, modulo: ModuleType
) -> None:
    albero = _albero(modulo)
    assert ATTESE[etichetta] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    trovate = letture_dimostrativa(albero)
    assert trovate == [], (
        f"{modulo.__name__} non deve leggere se un partner e' dimostrativo: e' sola "
        f"presentazione, mai input di scoring. Trovate: {trovate}"
    )


def test_engine_legge_il_partner_dimostrativo_solo_nei_costruttori_di_tappe() -> None:
    albero = _albero(engine)
    assert ATTESE["engine"] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    assert AMMESSE_NEL_MOTORE <= _nomi_funzioni(albero), "allowlist non aggiornata"
    colpevoli = {
        nome: trovate
        for nome, nodo in _parti_del_modulo(albero)
        if nome not in AMMESSE_NEL_MOTORE and (trovate := letture_dimostrativa(nodo))
    }
    assert colpevoli == {}, (
        "nel motore solo i costruttori di tappe possono leggere il partner "
        f"dimostrativo (scelta e ordinamento mai): {colpevoli}"
    )


def test_le_ammesse_leggono_davvero_il_campo() -> None:
    """Non vacuita' dell'allowlist: se un costruttore smettesse di copiare il
    campo, la sua voce andrebbe tolta (allowlist minima)."""
    albero = _albero(engine)
    per_nome = dict(_parti_del_modulo(albero))
    for nome in AMMESSE_NEL_MOTORE:
        assert letture_dimostrativa(per_nome[nome]) != [], nome


def test_calcola_score_e_la_chiusura_del_recommender_puliti_anche_da_sole() -> None:
    from graph.seed_lucca import VOCABOLARIO
    from recommender import InMemoryBehaviorEventRepository

    score_fn = ranking.costruisci_score_fn(
        InMemoryBehaviorEventRepository(), [], vocabolario=VOCABOLARIO
    )
    for fn in (rules.calcola_score, score_fn):
        albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        assert letture_dimostrativa(albero) == [], getattr(fn, "__name__", fn)


# ---------------------------------------------------------------------------
# Sensibilita': la guardia scatta davvero
# ---------------------------------------------------------------------------


def _letture(sorgente: str) -> list[str]:
    return letture_dimostrativa(ast.parse(textwrap.dedent(sorgente)))


@pytest.mark.parametrize(
    "corpo",
    [
        "return 1.0 if candidate.partner_dimostrativo else 0.5",
        'return getattr(candidate, "partner_dimostrativo")',
        'return candidate.model_dump()["partner_dimostrativo"]',
        "return stop.dimostrativa",
        "return [s for s in stops if not s.dimostrativa]",
        "return bottega.fittizio",
        "return partner_dimostrativo",
        "from contracts import partner_dimostrativo",
    ],
)
def test_la_guardia_scatta(corpo: str) -> None:
    sorgente = f"def f(candidate, stop, stops, bottega):\n    {corpo}\n"
    assert _letture(sorgente) != [], corpo


def test_la_guardia_scatta_in_una_chiusura_e_in_una_lambda() -> None:
    sorgente = """
        def costruisci(candidati):
            def _score(candidate, profile, signal):
                return 0.0 if candidate.partner_dimostrativo else 1.0
            ordina = lambda c: c.partner_dimostrativo
            return _score, ordina
    """
    assert sorted(_letture(sorgente)) == [
        "c.partner_dimostrativo",
        "candidate.partner_dimostrativo",
    ]


def test_la_guardia_ignora_docstring_e_keyword_di_costruzione() -> None:
    sorgente = '''
        def f(candidate):
            """partner_dimostrativo nella docstring: ignorata"""
            return ItineraryStop(experience_id="x", dimostrativa=False)
    '''
    assert _letture(sorgente) == []
