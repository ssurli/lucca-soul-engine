"""Guardia AST: lo scoring e la scelta non leggono MAI le curiosita' dei luoghi.

`GraphCandidate.curiosita` (ondata 2a, compito 5) e' SOLO narrazione: l'app la
mostra sotto il `reason`. Stesso principio di `attribuzione`: se una funzione
che sceglie o ordina la leggesse, un luogo "piu' curioso" (o piu' raccontato
nel seed) comprerebbe visibilita'.

Perche' una guardia nuova e non un'estensione delle liste di
`test_scoring_non_usa_partner_id_ne_prezzo` (test_engine.py) e di
`test_scoring_non_legge_orari.py`: quelle cercano una SOTTOSTRINGA nel codice,
ma "curiosita" e' anche un asse legittimo del profilo (`profile.curiosita`,
`W_CURIOSITA` in `calcola_score`). Questa guardia distingue il ricevente:
un accesso `.curiosita` e' ammesso solo su un parametro annotato
`EmotionalProfile`; ogni altro accesso, il tipo `Curiosita`, un identificatore
o una stringa con "curiosita" (es. `getattr(c, "curiosita")`,
`model_dump()["curiosita"]`) la fa scattare. Docstring escluse, keyword di
costruzione (`EmotionalProfile(curiosita=0.5)`) non sono letture.

Perimetro (modulo intero, cosi' ogni funzione futura e' coperta d'ufficio):
- `experience_engine.rules`: tutto (`calcola_score`, filtri duri, segnali...);
- `recommender.ranking`: tutto (`costruisci_score_fn` con la chiusura
  `_score`, quote storica e strutturale, esposizione, gating) — le stesse
  funzioni coperte dalle guardie commerciali del recommender;
- `experience_engine.engine`: tutto TRANNE i costruttori di tappe che devono
  copiare le curiosita' sulla tappa (`AMMESSE_NEL_MOTORE`). In particolare
  `_ordina_per_score`, `_seleziona_tappe`, `_migliore_alternativa`,
  `compose_itinerary`, `adapt_itinerary` sono controllate.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import ModuleType

import pytest
from experience_engine import engine, rules
from recommender import ranking

#: Identificatori che contengono "curiosita" ma sono l'asse del PROFILO.
NOMI_DEL_PROFILO = frozenset({"W_CURIOSITA"})

#: Le sole funzioni del motore che possono leggere `candidate.curiosita`: la
#: copiano sulla tappa, non scelgono ne' ordinano.
AMMESSE_NEL_MOTORE = frozenset({
    "_costruisci_stops",
    "_ricostruisci_stops",
    "_stub_da_stop",
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
    },
}

_Funzione = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda


def _docstring(nodo: ast.AST) -> ast.Constant | None:
    corpo = getattr(nodo, "body", None)
    if (
        isinstance(corpo, list)
        and corpo
        and isinstance(corpo[0], ast.Expr)
        and isinstance(corpo[0].value, ast.Constant)
        and isinstance(corpo[0].value.value, str)
    ):
        return corpo[0].value
    return None


def _parametri_profilo(radice: ast.AST) -> set[str]:
    """Parametri annotati `EmotionalProfile` (anche `| None`) di ogni funzione
    contenuta in `radice`: i soli riceventi ammessi per `.curiosita`."""
    nomi: set[str] = set()
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            argomenti = nodo.args
            for a in [*argomenti.posonlyargs, *argomenti.args, *argomenti.kwonlyargs]:
                if a.annotation is not None and "EmotionalProfile" in ast.unparse(a.annotation):
                    nomi.add(a.arg)
    return nomi


def letture_curiosita(radice: ast.AST) -> list[str]:
    """Riferimenti alle curiosita' dei luoghi in `radice` (docstring escluse).

    Vuota = nessuna lettura. Ogni voce e' il frammento di codice colpevole."""
    docstring = {id(d) for n in ast.walk(radice) if (d := _docstring(n)) is not None}
    profili = _parametri_profilo(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and "curiosita" in nodo.attr.lower():
            ricevente_profilo = isinstance(nodo.value, ast.Name) and nodo.value.id in profili
            if not (nodo.attr == "curiosita" and ricevente_profilo):
                trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and "curiosita" in nodo.id.lower():
            if nodo.id not in NOMI_DEL_PROFILO:
                trovate.append(nodo.id)
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and "curiosita" in nodo.value.lower()
        ):
            trovate.append(repr(nodo.value))
        elif isinstance(nodo, ast.alias) and "curiosita" in nodo.name.lower():
            trovate.append(f"import {nodo.name}")
    return trovate


def _albero(modulo: ModuleType) -> ast.Module:
    return ast.parse(inspect.getsource(modulo))


def _nomi_funzioni(radice: ast.AST) -> set[str]:
    return {
        n.name for n in ast.walk(radice) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _parti_del_modulo(albero: ast.Module) -> list[tuple[str, ast.AST]]:
    """Ogni istruzione di primo livello, etichettata col nome se e' una
    funzione o una classe."""
    parti: list[tuple[str, ast.AST]] = []
    for nodo in albero.body:
        nome = getattr(nodo, "name", f"<riga {getattr(nodo, 'lineno', '?')}>")
        parti.append((nome, nodo))
    return parti


# ---------------------------------------------------------------------------
# La guardia sul codice di produzione
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("etichetta", "modulo"), [("rules", rules), ("ranking", ranking)]
)
def test_rules_e_ranking_non_leggono_le_curiosita(etichetta: str, modulo: ModuleType) -> None:
    albero = _albero(modulo)
    assert ATTESE[etichetta] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    trovate = letture_curiosita(albero)
    assert trovate == [], (
        f"{modulo.__name__} non deve leggere le curiosita' dei luoghi: sono solo "
        f"narrazione, mai input di scoring. Trovate: {trovate}"
    )


def test_engine_legge_le_curiosita_solo_nei_costruttori_di_tappe() -> None:
    albero = _albero(engine)
    assert ATTESE["engine"] <= _nomi_funzioni(albero), "perimetro della guardia incompleto"
    assert AMMESSE_NEL_MOTORE <= _nomi_funzioni(albero), "allowlist non aggiornata"
    colpevoli = {
        nome: trovate
        for nome, nodo in _parti_del_modulo(albero)
        if nome not in AMMESSE_NEL_MOTORE and (trovate := letture_curiosita(nodo))
    }
    assert colpevoli == {}, (
        "nel motore solo i costruttori di tappe possono leggere le curiosita' "
        f"(scelta e ordinamento mai): {colpevoli}"
    )


def test_calcola_score_e_la_chiusura_del_recommender_puliti_anche_da_sole() -> None:
    """Le due funzioni di scoring vere, ispezionate da sole come fanno le guardie
    commerciali (la chiusura `_score` restituita da `costruisci_score_fn`)."""
    from graph.seed_lucca import VOCABOLARIO
    from recommender import InMemoryBehaviorEventRepository

    score_fn = ranking.costruisci_score_fn(
        InMemoryBehaviorEventRepository(), [], vocabolario=VOCABOLARIO
    )
    for fn in (rules.calcola_score, score_fn):
        albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        assert letture_curiosita(albero) == [], getattr(fn, "__name__", fn)


# ---------------------------------------------------------------------------
# Sensibilita': la guardia scatta davvero
# ---------------------------------------------------------------------------


def _letture(sorgente: str) -> list[str]:
    return letture_curiosita(ast.parse(textwrap.dedent(sorgente)))


def test_la_guardia_scatta_su_candidate_curiosita() -> None:
    trovate = _letture(
        '''
        def calcola_score(candidate, profile: EmotionalProfile, signal):
            """candidate.curiosita nella docstring: ignorata"""
            return profile.curiosita * len(candidate.curiosita)
        '''
    )
    assert trovate == ["candidate.curiosita"]


@pytest.mark.parametrize(
    "corpo",
    [
        'return getattr(candidate, "curiosita")',
        'return candidate.model_dump()["curiosita"]',
        "return isinstance(candidate.experience, Curiosita)",
        "return len(_curiosita_del_luogo(candidate))",
        "return any(c.fonte for c in candidate.curiosita)",
        # Ricevente di nome `profile` ma NON annotato: conservativo, scatta.
        "return profile.curiosita",
    ],
)
def test_la_guardia_scatta_sulle_letture_indirette(corpo: str) -> None:
    sorgente = f"def f(candidate, profile):\n    {corpo}\n"
    assert _letture(sorgente) != [], corpo


def test_la_guardia_scatta_in_una_chiusura_e_in_una_lambda() -> None:
    sorgente = """
        def costruisci(candidati):
            def _score(candidate, profile: EmotionalProfile, signal):
                return len(candidate.curiosita)
            ordina = lambda c: len(c.curiosita)
            return _score, ordina
    """
    assert sorted(_letture(sorgente)) == ["c.curiosita", "candidate.curiosita"]


def test_la_guardia_ammette_l_asse_del_profilo() -> None:
    """Nessun falso positivo sul profilo: e' cio' che `calcola_score` fa davvero."""
    sorgente = """
        def calcola_score(candidate, profile: EmotionalProfile | None, signal):
            neutro = EmotionalProfile(curiosita=0.5, contemplazione=0.5)
            return W_CURIOSITA * profile.curiosita + neutro.contemplazione
    """
    assert _letture(sorgente) == []
