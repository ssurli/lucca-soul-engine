"""Guardia AST: lo scoring e la scelta non leggono MAI la causa dell'adattamento.

`_CandidatoConReason.causa_deciso` e `ItineraryStop.causa_adattamento` sono SOLA
spiegazione (perche' la tappa e' cambiata o e' stata mantenuta), mai input di
scoring: se una funzione che sceglie o ordina li leggesse, l'esito di un
adattamento precedente influenzerebbe la scelta successiva.

Stesso schema di `test_scoring_non_legge_causaa.py`. Marcatori: gli
identificatori `causa_deciso` e `causa_adattamento` (la variabile locale
`causa` di `adapt_itinerary` e le keyword di costruzione non sono letture del
campo). Perimetro: `rules` e `ranking` per intero; `engine` per intero TRANNE
`adapt_itinerary` (che decide la causa e la scrive nella tappa),
`_marca_reason` e `_ricostruisci_stops` (costruttori che la copiano) e
`_CandidatoConReason` (che dichiara il campo).
`_migliore_alternativa`, `_ordina_per_score`, `_seleziona_tappe` e gli altri
restano controllati.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import ModuleType

import pytest
from experience_engine import engine, rules
from recommender import ranking

MARCATORI = ("causa_deciso", "causa_adattamento")


def _marcato(testo: str) -> bool:
    return any(m in testo.lower() for m in MARCATORI)


#: Le sole parti del motore che possono toccare il campo: lo decidono o lo copiano
#: sulla tappa, non scelgono ne' ordinano.
AMMESSE_NEL_MOTORE = frozenset({
    "adapt_itinerary",
    "_marca_reason",
    "_ricostruisci_stops",
    "_CandidatoConReason",  # dichiara il campo
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


def letture_causa(radice: ast.AST) -> list[str]:
    """Riferimenti al campo causa in `radice` (docstring escluse).

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


def _nomi_definiti(radice: ast.AST) -> set[str]:
    """Funzioni e classi (l'allowlist include la classe che dichiara il campo)."""
    return {
        n.name
        for n in ast.walk(radice)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
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
def test_rules_e_ranking_non_leggono_il_causa_deciso(
    etichetta: str, modulo: ModuleType
) -> None:
    albero = _albero(modulo)
    assert ATTESE[etichetta] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    trovate = letture_causa(albero)
    assert trovate == [], (
        f"{modulo.__name__} non deve leggere se la causa dell'adattamento: e' sola "
        f"presentazione, mai input di scoring. Trovate: {trovate}"
    )


def test_engine_legge_il_causa_deciso_solo_nei_costruttori_di_tappe() -> None:
    albero = _albero(engine)
    assert ATTESE["engine"] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    assert AMMESSE_NEL_MOTORE <= _nomi_definiti(albero), "allowlist non aggiornata"
    colpevoli = {
        nome: trovate
        for nome, nodo in _parti_del_modulo(albero)
        if nome not in AMMESSE_NEL_MOTORE and (trovate := letture_causa(nodo))
    }
    assert colpevoli == {}, (
        "nel motore solo le parti ammesse possono toccare la causa "
        f"(scelta e ordinamento mai): {colpevoli}"
    )


def test_le_ammesse_leggono_davvero_il_campo() -> None:
    """Non vacuita' dell'allowlist: se un costruttore smettesse di copiare il
    campo, la sua voce andrebbe tolta (allowlist minima)."""
    albero = _albero(engine)
    per_nome = dict(_parti_del_modulo(albero))
    for nome in AMMESSE_NEL_MOTORE:
        assert letture_causa(per_nome[nome]) != [], nome


def test_calcola_score_e_la_chiusura_del_recommender_puliti_anche_da_sole() -> None:
    from graph.seed_lucca import VOCABOLARIO
    from recommender import InMemoryBehaviorEventRepository

    score_fn = ranking.costruisci_score_fn(
        InMemoryBehaviorEventRepository(), [], vocabolario=VOCABOLARIO
    )
    for fn in (rules.calcola_score, score_fn):
        albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        assert letture_causa(albero) == [], getattr(fn, "__name__", fn)


# ---------------------------------------------------------------------------
# Sensibilita': la guardia scatta davvero
# ---------------------------------------------------------------------------


def _letture(sorgente: str) -> list[str]:
    return letture_causa(ast.parse(textwrap.dedent(sorgente)))


@pytest.mark.parametrize(
    "corpo",
    [
        "return 1.0 if candidate.causa_deciso else 0.5",
        'return getattr(candidate, "causa_deciso")',
        'return candidate.model_dump()["causa_deciso"]',
        "return stop.causa_adattamento",
        "return [s for s in stops if not s.causa_adattamento]",
        "return c.causa_deciso",
        "return causa_deciso",
        "from contracts import causa_deciso",
    ],
)
def test_la_guardia_scatta(corpo: str) -> None:
    sorgente = f"def f(candidate, stop, stops, c):\n    {corpo}\n"
    assert _letture(sorgente) != [], corpo


def test_la_guardia_scatta_in_una_chiusura_e_in_una_lambda() -> None:
    sorgente = """
        def costruisci(candidati):
            def _score(candidate, profile, signal):
                return 0.0 if candidate.causa_deciso else 1.0
            ordina = lambda c: c.causa_deciso
            return _score, ordina
    """
    assert sorted(_letture(sorgente)) == [
        "c.causa_deciso",
        "candidate.causa_deciso",
    ]


def test_la_guardia_ignora_docstring_e_keyword_di_costruzione() -> None:
    sorgente = '''
        def f(candidate):
            """causa_deciso nella docstring: ignorata"""
            return ItineraryStop(experience_id="x", causa_adattamento=None)
    '''
    assert _letture(sorgente) == []
