"""Guardia AST: nessun modulo del motore o del recommender fa riferimento a foto.

Decisione del committente (ondata 4, compito 5-bis): le foto delle tappe vivono
SOLO nell'app (`apps/lucca_soul_app/assets/foto/<experience_id>.jpg` + `foto.json`).
Nessun campo di contratto, nessuna modifica al motore: la foto non entra MAI nel
punteggio ne' nelle decisioni.

Perimetro: TUTTI i moduli dei pacchetti `experience_engine` e `recommender`
(incluso `engine.py`), scoperti dal filesystem cosi' un modulo futuro e' coperto
d'ufficio. Cercano il marcatore (case-insensitive, sottostringa) in attributi,
nomi, argomenti, keyword, import e stringhe non docstring. Escluse solo
docstring e commenti (che l'AST non vede).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import ModuleType

import experience_engine
import pytest
import recommender
from contracts import models

MARCATORI = ("foto", "photo", "immagine", "image", "didascalia", "autore_foto")


def _marcato(testo: str) -> bool:
    return any(m in testo.lower() for m in MARCATORI)


def _docstring_ids(radice: ast.AST) -> set[int]:
    ids: set[int] = set()
    for n in ast.walk(radice):
        corpo = getattr(n, "body", None)
        if (
            isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and isinstance(corpo, list)
            and corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            ids.add(id(corpo[0].value))
    return ids


#: Unica eccezione: la CHIAVE `"photo"` del dizionario `PESI_TIPO` in
#: `recommender/features.py`. E' il tipo di evento `BehaviorEvent.tipo == "photo"`
#: del contratto (`packages/contracts/contracts/models.py`, ~riga 1054): il gesto
#: del visitatore che fotografa, NON la foto della tappa. Individuata per nodo AST
#: (chiave costante di un `ast.Dict` assegnato a `PESI_TIPO`); ogni altra
#: occorrenza dei marcatori, anche in quello stesso file, fa scattare la guardia.
FILE_EVENTI = "features.py"
DIZIONARIO_EVENTI = "PESI_TIPO"
CHIAVE_EVENTO = "photo"


def _chiavi_evento_ammesse(albero: ast.AST) -> set[int]:
    ammesse: set[int] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Assign):
            bersagli = nodo.targets
        elif isinstance(nodo, ast.AnnAssign):
            bersagli = [nodo.target]
        else:
            continue
        if not any(isinstance(b, ast.Name) and b.id == DIZIONARIO_EVENTI for b in bersagli):
            continue
        if isinstance(nodo.value, ast.Dict):
            for chiave in nodo.value.keys:
                if isinstance(chiave, ast.Constant) and chiave.value == CHIAVE_EVENTO:
                    ammesse.add(id(chiave))
    return ammesse


def riferimenti_foto(radice: ast.AST, *, ammetti_chiave_evento: bool = False) -> list[str]:
    """Riferimenti a foto in `radice` (docstring escluse). Vuota = nessuno."""
    docstring = _docstring_ids(radice)
    if ammetti_chiave_evento:
        docstring |= _chiavi_evento_ammesse(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and _marcato(nodo.attr):
            trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and _marcato(nodo.id):
            trovate.append(nodo.id)
        elif isinstance(nodo, ast.arg) and _marcato(nodo.arg):
            trovate.append(f"arg {nodo.arg}")
        elif isinstance(nodo, ast.keyword) and nodo.arg is not None and _marcato(nodo.arg):
            trovate.append(f"keyword {nodo.arg}")
        elif isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and _marcato(
            nodo.name
        ):
            trovate.append(f"def {nodo.name}")
        elif isinstance(nodo, ast.alias) and (
            _marcato(nodo.name) or (nodo.asname is not None and _marcato(nodo.asname))
        ):
            trovate.append(f"import {nodo.name}")
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and _marcato(nodo.module):
            trovate.append(f"from {nodo.module}")
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and _marcato(nodo.value)
        ):
            trovate.append(repr(nodo.value))
    return trovate


def _moduli(pacchetto: ModuleType) -> list[Path]:
    radice = Path(inspect.getfile(pacchetto)).parent
    return sorted(radice.rglob("*.py"))


PERIMETRO = [*_moduli(experience_engine), *_moduli(recommender)]


@pytest.mark.parametrize("percorso", PERIMETRO, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_il_modulo_non_fa_riferimento_a_foto(percorso: Path) -> None:
    albero = ast.parse(percorso.read_text(encoding="utf-8"))
    eventi = percorso.name == FILE_EVENTI and percorso.parent.name == "recommender"
    trovate = riferimenti_foto(albero, ammetti_chiave_evento=eventi)
    assert trovate == [], (
        f"{percorso.name}: la foto vive solo nell'app e non entra mai in scoring o "
        f"decisioni. Trovate: {trovate}"
    )


def test_il_perimetro_non_e_vuoto() -> None:
    nomi = {p.name for p in PERIMETRO}
    assert {"engine.py", "rules.py", "ranking.py", "features.py"} <= nomi
    assert len(PERIMETRO) >= 6


@pytest.mark.parametrize("modello", ["ItineraryStop", "GraphCandidate"])
def test_i_contratti_non_hanno_campi_foto(modello: str) -> None:
    campi = getattr(models, modello).model_fields
    colpevoli = [c for c in campi if _marcato(c)]
    assert colpevoli == [], f"{modello} non deve avere campi foto: {colpevoli}"


# ---------------------------------------------------------------------------
# Sensibilita': la guardia scatta davvero
# ---------------------------------------------------------------------------


def _letture(sorgente: str) -> list[str]:
    return riferimenti_foto(ast.parse(textwrap.dedent(sorgente)))


def test_la_guardia_scatta_su_una_funzione_finta() -> None:
    trovate = _letture(
        '''
        def calcola_score(candidate, profile, signal):
            """foto nella docstring: ignorata"""
            # foto in un commento: ignorato
            return 1.0 if candidate.foto else 0.0
        '''
    )
    assert trovate == ["candidate.foto"]


@pytest.mark.parametrize(
    "corpo",
    [
        'return getattr(candidate, "foto")',
        'return candidate.model_dump()["Photo_URL"]',
        "return len(immagine)",
        "return f(didascalia=1)",
        "return candidate.autore_foto",
        "return image_count",
    ],
)
def test_la_guardia_scatta_sulle_letture_indirette(corpo: str) -> None:
    assert _letture(f"def f(candidate):\n    {corpo}\n") != [], corpo


def test_la_guardia_scatta_su_argomenti_import_e_def() -> None:
    assert _letture("def f(foto): return 1") == ["arg foto"]
    assert _letture("from x import photo_utils") == ["import photo_utils"]
    assert _letture("import PIL.Image as im") != []
    assert _letture("def _carica_foto(): return 1") == ["def _carica_foto"]


def test_la_guardia_ignora_docstring_e_commenti() -> None:
    assert _letture('def f():\n    """foto, photo, immagine"""\n    # image\n    return 1\n') == []


def test_l_eccezione_ammette_solo_la_chiave_del_dizionario_degli_eventi() -> None:
    ok = 'PESI_TIPO: dict[str, float] = {"view": 1.0, "photo": 1.5}\n'
    albero = ast.parse(ok)
    assert riferimenti_foto(albero, ammetti_chiave_evento=True) == []
    assert riferimenti_foto(albero) == ["'photo'"]  # senza eccezione scatta


@pytest.mark.parametrize(
    "sorgente",
    [
        # stesso dizionario: altra chiave, valore
        'PESI_TIPO = {"view": 1.0, "photo_url": 1.5}\n',
        'PESI_TIPO = {"view": "photo"}\n',
        # attributo
        'PESI_TIPO = {"view": 1.0}\nx = PESI_TIPO.photo\n',
        # "photo" in un altro dizionario o in un'altra stringa del file
        'ALTRO = {"photo": 1.5}\n',
        'PESI_TIPO = {"view": 1.0}\nx = "tipo photo"\n',
        'PESI_TIPO = {"view": 1.0}\nx = ["photo"]\n',
        'PESI_TIPO = {"view": 1.0}\nPESI_TIPO["photo"] = 2.0\n',
        'PESI_TIPO = {"view": 1.0}\nfoto = 1\n',
        'PESI_TIPO = {"view": 1.0}\ndef f(c):\n    return c.foto\n',
    ],
)
def test_ogni_altra_occorrenza_in_features_fa_scattare_la_guardia(sorgente: str) -> None:
    assert riferimenti_foto(ast.parse(sorgente), ammetti_chiave_evento=True) != [], sorgente
