"""Riordino per vicinanza delle tappe GIA' SCELTE (ondata 4, compito 1).

Regola APPROVATA dal committente (`engine._riordina_per_vicinanza`):
  - l'INSIEME delle tappe non cambia, cambia solo l'ordine;
  - la prima tappa e' ferma; le tappe senza punto d'arrivo restano ferme;
  - fino a 7 tappe mobili si provano tutte le permutazioni, sopra 7 il vicino
    piu' prossimo (`_passo`);
  - un ordine e' AMMESSO solo se ogni tappa e' aperta all'arrivo per tutta la
    visita, se rispetta il budget effettivo e se ha metri STRETTAMENTE minori
    di quelli di oggi;
  - tra gli ammessi vincono meno metri, a parita' le posizioni originali
    lessicograficamente minori; nessun ammesso = ordine di oggi.
  - solo composizione, mai adattamento.

Qui: (1) la guardia AST (le funzioni del riordino leggono solo punti, durate e
orari; `_seleziona_tappe` e l'adattamento non le chiamano), con la prova che
la guardia puo' fallire; (2) i casi COSTRUITI con punti sintetici su un piano
(x in metri verso est, y verso nord); (3) le code (`minuti_usati`).
La proprieta' sui casi del golden di Lucca vive in
`services/api/tests/test_riordino_vicinanza_golden.py`.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, time
from itertools import permutations
from types import FunctionType

import pytest
from contracts import (
    EmotionalProfile,
    ExperienceNode,
    FasciaApertura,
    GraphCandidate,
    Punto,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
    VocabolarioTemi,
    distanza_a_piedi_m,
)
from experience_engine import compose_itinerary
from experience_engine import engine as motore
from experience_engine import rules as regole

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)

ORA = time(10, 0)
LUNEDI = 0
BUDGET_AMPIO = 900


# ---------------------------------------------------------------------------
# (1) Guardia AST
# ---------------------------------------------------------------------------

#: Funzioni del riordino: leggono SOLO punti, durate e orari.
FUNZIONI_RIORDINO = (
    "_riordina_per_vicinanza",
    "_metri_ordine",
    "_ordine_ammesso",
    "_vicino_piu_prossimo",
)
#: Prefissi (minuscoli) di ogni riferimento che il riordino non puo' fare:
#: partner, prezzo, attribuzione, curiosita', fonti, abbonamento; piu' ogni
#: nome che contiene "score" (calcola_score, score_fn, _ordina_per_score...).
PREFISSI_VIETATI = (
    "partner",
    "abbonamento",
    "prezzo",
    "attribuzione",
    "_attribuzione",
    "curiosita",
    "fonte",
)


def _e_vietato(nome: str) -> bool:
    n = nome.lower()
    return n.startswith(PREFISSI_VIETATI) or "score" in n


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


def letture_vietate(radice: ast.AST) -> list[str]:
    """Attributi, nomi, argomenti, keyword, import e stringhe (non docstring)
    che leggono score, partner, prezzo, attribuzione, curiosita' o fonti."""
    docstring = _docstring_ids(radice)
    trovate: list[str] = []
    for nodo in ast.walk(radice):
        if isinstance(nodo, ast.Attribute) and _e_vietato(nodo.attr):
            trovate.append(ast.unparse(nodo))
        elif isinstance(nodo, ast.Name) and _e_vietato(nodo.id):
            trovate.append(nodo.id)
        elif isinstance(nodo, ast.arg) and _e_vietato(nodo.arg):
            trovate.append(nodo.arg)
        elif isinstance(nodo, ast.keyword) and nodo.arg and _e_vietato(nodo.arg):
            trovate.append(f"{nodo.arg}=")
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstring
            and _e_vietato(nodo.value)
        ):
            trovate.append(repr(nodo.value))
        elif isinstance(nodo, ast.alias) and _e_vietato(nodo.name.split(".")[-1]):
            trovate.append(f"import {nodo.name}")
    return trovate


def _albero(fn: Callable[..., object]) -> ast.AST:
    return ast.parse(textwrap.dedent(inspect.getsource(fn)))


def _nomi_chiamati(radice: ast.AST) -> set[str]:
    """Nomi (semplici) delle funzioni chiamate o passate come valore."""
    return {n.id for n in ast.walk(radice) if isinstance(n, ast.Name)}


def _chiusura(partenza: Callable[..., object]) -> dict[str, FunctionType]:
    """Funzioni di `engine` e `rules` raggiungibili da `partenza` (inclusa)."""
    trovate: dict[str, FunctionType] = {}
    da_visitare = [partenza]
    while da_visitare:
        fn = da_visitare.pop()
        nome = getattr(fn, "__name__", "")
        if nome in trovate or not isinstance(fn, FunctionType):
            continue
        trovate[nome] = fn
        for chiamato in _nomi_chiamati(_albero(fn)):
            cand = getattr(motore, chiamato, None)
            if (
                isinstance(cand, FunctionType)
                and cand.__module__ in {motore.__name__, regole.__name__}
            ):
                da_visitare.append(cand)
    return trovate


def test_il_riordino_non_legge_score_partner_prezzo_attribuzione_curiosita_fonti() -> None:
    """Le quattro funzioni, e ogni funzione di `engine`/`rules` che chiamano
    (`_progressione`, `_passo`, `_minuti_usati_permanenti`, `aperta_durante`,
    ...), leggono solo punti, durate e orari."""
    for nome in FUNZIONI_RIORDINO:
        fn = getattr(motore, nome)
        for nome_chiamata, chiamata in _chiusura(fn).items():
            assert letture_vietate(_albero(chiamata)) == [], f"{nome} -> {nome_chiamata}"
    # Perimetro non vuoto: la chiusura raggiunge davvero gli helper del tempo.
    chiusura = _chiusura(motore._riordina_per_vicinanza)
    assert {"_progressione", "_passo", "_minuti_usati_permanenti", "aperta_durante"} <= set(
        chiusura
    )
    # Le funzioni di scoring non sono raggiungibili dal riordino.
    assert not set(chiusura) & {"calcola_score", "_ordina_per_score", "_seleziona_tappe"}


def test_seleziona_tappe_non_chiama_il_riordino() -> None:
    assert "_riordina_per_vicinanza" not in _nomi_chiamati(_albero(motore._seleziona_tappe))


def test_l_adattamento_non_chiama_il_riordino() -> None:
    """`adapt_itinerary` e tutte le funzioni di engine/rules che raggiunge."""
    chiusura = _chiusura(motore.adapt_itinerary)
    assert {"_migliore_alternativa", "_ricostruisci_stops"} <= set(chiusura), (
        "perimetro della guardia incompleto",
        sorted(chiusura),
    )
    for nome, fn in chiusura.items():
        assert "_riordina_per_vicinanza" not in _nomi_chiamati(_albero(fn)), nome
    assert "compose_itinerary" not in chiusura


def test_solo_compose_itinerary_chiama_il_riordino_tra_selezione_e_stops() -> None:
    chiamanti = [
        nome
        for nome, fn in vars(motore).items()
        if isinstance(fn, FunctionType)
        and fn.__module__ == motore.__name__
        and nome != "_riordina_per_vicinanza"
        and "_riordina_per_vicinanza" in _nomi_chiamati(_albero(fn))
    ]
    assert chiamanti == ["compose_itinerary"]
    righe: dict[str, int] = {}
    for nodo in ast.walk(_albero(motore.compose_itinerary)):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            righe.setdefault(nodo.func.id, nodo.lineno)
    assert (
        righe["_seleziona_tappe"] < righe["_riordina_per_vicinanza"] < righe["_costruisci_stops"]
    )


@pytest.mark.parametrize(
    "corpo",
    [
        "return c.partner_id",
        "return c.experience.partner_abbonamento_attivo",
        "return c.experience.prezzo_eur or 0",
        "return c.attribuzione",
        "return c.curiosita",
        "return c.fonte_orari",
        'return getattr(c, "fonte")',
        "return calcola_score(c, p, s)",
        "return score_fn(c, p, s)",
        "return _ordina_per_score(x, p, s, f)",
        "return sorted(x, key=lambda c: c.score)",
        "return f(score_fn=g)",
        "from experience_engine.rules import calcola_score",
    ],
)
def test_la_guardia_del_riordino_scatta(corpo: str) -> None:
    """La guardia puo' FALLIRE: una funzione finta che legge un riferimento
    vietato viene segnalata."""
    sorgente = f"def finta(c, p, s, x, f, g):\n    {corpo}\n"
    assert letture_vietate(ast.parse(sorgente)) != [], corpo


def test_la_guardia_del_riordino_non_ha_falsi_positivi() -> None:
    sorgente = '''
        def buona(selezionati, progressione):
            """partner_id, prezzo_eur e score nella docstring: ignorati"""
            return [selezionati[i].experience.durata_min for i, _ in enumerate(progressione)]
    '''
    assert letture_vietate(ast.parse(textwrap.dedent(sorgente))) == []


def test_la_guardia_scatta_anche_sull_helper_raggiunto() -> None:
    """Il riordino che chiamasse un helper che legge il prezzo verrebbe colto
    dalla chiusura: la lettura sta nell'helper, non nella funzione."""
    sorgente = (
        "def helper(c):\n    return c.experience.prezzo_eur\n"
        "def riordina(c):\n    return helper(c)\n"
    )
    albero = ast.parse(sorgente)
    funzioni = {n.name: n for n in albero.body if isinstance(n, ast.FunctionDef)}
    assert letture_vietate(funzioni["riordina"]) == []
    assert letture_vietate(funzioni["helper"]) != []
    assert _nomi_chiamati(funzioni["riordina"]) >= {"helper"}


# ---------------------------------------------------------------------------
# (2) Casi costruiti
# ---------------------------------------------------------------------------


def punto(x: float, y: float = 0.0) -> Punto:
    """Punto a `x` metri a est e `y` a nord di un'origine vicino a Lucca."""
    return Punto(lat=43.84 + y / 111_000, lon=10.50 + x / 80_300)


def cand(
    id_: str,
    pos: Punto | None,
    *,
    durata: int = 30,
    orari: Sequence[tuple[time, time]] | None = None,
    luogo: str | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_,
            titolo=f"Tappa {id_}",
            place_id=luogo or f"luogo-{id_}",
            temi=["arte"],
            durata_min=durata,
            al_chiuso=True,
            accessibile=True,
            orari_apertura=[
                FasciaApertura(giorno_settimana=LUNEDI, apertura=a, chiusura=c)
                for a, c in (orari or [])
            ],
        ),
        place_nome=f"Luogo {id_}",
        connessioni=[],
        punti_arrivo=[pos] if pos is not None else [],
    )


def riordina(
    tappe: list[GraphCandidate],
    *,
    budget: int = BUDGET_AMPIO,
    ora: time = ORA,
    giorno: int | None = LUNEDI,
) -> list[str]:
    risultato = motore._riordina_per_vicinanza(
        tappe, ora_partenza=ora, giorno_settimana=giorno, tempo_disponibile_min=budget
    )
    return [c.experience.id for c in risultato]


def ids(tappe: Sequence[GraphCandidate]) -> list[str]:
    return [c.experience.id for c in tappe]


def metri(tappe: Sequence[GraphCandidate]) -> int:
    return int(motore._metri_ordine(motore._progressione(tappe)))


def minuti(tappe: Sequence[GraphCandidate]) -> int:
    return int(motore._minuti_usati_permanenti(tappe))


def test_i_metri_sono_la_somma_delle_distanze_a_piedi_tra_consecutive() -> None:
    a, b, c = punto(0), punto(1000), punto(2500)
    attesi = distanza_a_piedi_m(a, b) + distanza_a_piedi_m(b, c)
    assert metri([cand("a", a), cand("b", b), cand("c", c)]) == attesi
    # Una coppia con una tappa senza punto non conta.
    assert metri([cand("a", a), cand("bot", None), cand("c", c)]) == 0


def zigzag() -> list[GraphCandidate]:
    """Prima tappa a 0; poi 2000, 1000, 3000 lungo una retta: l'ordine di oggi
    va avanti e indietro, l'unico ordine piu' corto e' 0, 1000, 2000, 3000."""
    return [
        cand("s0", punto(0)),
        cand("a", punto(2000)),
        cand("b", punto(1000)),
        cand("c", punto(3000)),
    ]


def test_ordine_piu_corto_ammesso_viene_scelto_e_la_prima_tappa_resta() -> None:
    tappe = zigzag()
    assert riordina(tappe) == ["s0", "b", "a", "c"]
    nuovo = [tappe[0], tappe[2], tappe[1], tappe[3]]
    assert metri(nuovo) < metri(tappe)


def test_l_insieme_delle_tappe_non_cambia() -> None:
    tappe = zigzag()
    assert sorted(riordina(tappe)) == sorted(ids(tappe))
    assert riordina(tappe)[0] == "s0"


def test_caso3_un_ordine_piu_corto_viola_un_orario_resta_l_ordine_di_oggi() -> None:
    """B apre alle 11:30. Oggi arriva alle 11:50; ogni ordine piu' corto lo
    mette per primo dopo la tappa fissa (arrivo 10:47, chiusa)."""
    senza_orari = zigzag()
    assert riordina(senza_orari) == ["s0", "b", "a", "c"]  # controllo: senza il vincolo
    con_orari = zigzag()
    con_orari[2] = cand("b", punto(1000), orari=[(time(11, 30), time(18, 0))])
    assert riordina(con_orari) == ["s0", "a", "b", "c"]
    # Il vincolo e' proprio l'orario: l'ordine scartato era piu' corto.
    assert metri([con_orari[0], con_orari[2], con_orari[1], con_orari[3]]) < metri(con_orari)


def test_orario_di_chiusura_prima_della_fine_della_visita_non_e_ammesso() -> None:
    """Aperta all'arrivo ma non per tutta la visita: arrivo 10:47 + 30 minuti
    supera la chiusura delle 11:00."""
    tappe = zigzag()
    tappe[2] = cand("b", punto(1000), orari=[(time(8, 0), time(11, 0))])
    # Oggi B arriva alle 11:50, chiusa: l'ordine di oggi e' comunque quello
    # che resta, e quello piu' corto (B alle 10:47, fine 11:17) e' scartato.
    assert riordina(tappe) == ["s0", "a", "b", "c"]


def test_giorno_non_specificato_non_blocca_per_orario() -> None:
    tappe = zigzag()
    tappe[2] = cand("b", punto(1000), orari=[(time(11, 30), time(18, 0))])
    assert riordina(tappe, giorno=None) == ["s0", "b", "a", "c"]


def test_caso4_gia_ottimo_resta_l_ordine_di_oggi() -> None:
    tappe = [cand("s0", punto(0)), cand("b", punto(1000)), cand("a", punto(2000))]
    assert riordina(tappe) == ["s0", "b", "a"]


def test_caso4_parita_di_metri_non_basta_resta_l_ordine_di_oggi() -> None:
    """S0 al centro, A a +1000 e B a -1000: i due ordini hanno gli stessi metri.
    Servono metri STRETTAMENTE minori: non si riordina."""
    tappe = [cand("s0", punto(0)), cand("a", punto(1000)), cand("b", punto(-1000))]
    assert metri(tappe) == metri([tappe[0], tappe[2], tappe[1]])
    assert riordina(tappe) == ["s0", "a", "b"]
    invertito = [tappe[0], tappe[2], tappe[1]]
    assert riordina(invertito) == ["s0", "b", "a"]


def test_caso4_punti_tutti_uguali_nessun_riordino() -> None:
    tappe = [cand(f"t{i}", punto(500)) for i in range(5)]
    assert riordina(tappe) == [f"t{i}" for i in range(5)]


def test_caso4_nessun_ordine_piu_corto_ammesso_per_orari_resta_quello_di_oggi() -> None:
    """Tre tappe mobili, tutti gli ordini piu' corti scartati: ordine di oggi."""
    tappe = [
        cand("s0", punto(0)),
        cand("a", punto(2000), orari=[(time(11, 0), time(13, 0))]),
        cand("b", punto(1000), orari=[(time(11, 40), time(13, 0))]),
        cand("c", punto(3000), orari=[(time(11, 0), time(23, 0))]),
    ]
    assert riordina(tappe) == ids(tappe)


def test_sotto_due_tappe_mobili_nessun_riordino() -> None:
    assert riordina([cand("s0", punto(0))]) == ["s0"]
    assert riordina([cand("s0", punto(0)), cand("a", punto(100))]) == ["s0", "a"]
    assert riordina([]) == []


def test_caso5_una_bottega_senza_punto_resta_nella_sua_posizione() -> None:
    tappe = [
        cand("s0", punto(0)),
        cand("a", punto(3000)),
        cand("bottega", None),
        cand("b", punto(1000)),
        cand("c", punto(2000)),
    ]
    risultato = riordina(tappe)
    assert risultato[2] == "bottega"
    assert risultato[0] == "s0"
    assert sorted(risultato) == sorted(ids(tappe))
    nuovo = [next(t for t in tappe if t.experience.id == i) for i in risultato]
    assert metri(nuovo) < metri(tappe)
    assert risultato == ["s0", "b", "bottega", "a", "c"]


def test_caso5_la_bottega_in_seconda_posizione_resta_li() -> None:
    tappe = [
        cand("s0", punto(0)),
        cand("bottega", None),
        cand("a", punto(2000)),
        cand("b", punto(1000)),
    ]
    # Mobili: a e b negli slot 2 e 3; sono adiacenti, b dopo a costa meno.
    risultato = riordina(tappe)
    assert risultato[1] == "bottega"
    assert sorted(risultato) == sorted(ids(tappe))


def test_caso6_a_parita_di_metri_vince_la_posizione_originale_minore() -> None:
    """Q ed R hanno lo stesso punto: gli ordini (s0, q, r, p) e (s0, r, q, p)
    hanno gli stessi metri e sono entrambi piu' corti di oggi (s0, p, q, r).
    Vince quello con le posizioni originali lessicograficamente minori."""
    p, q, r = punto(3000), punto(1000), punto(1000)
    tappe = [cand("s0", punto(0)), cand("p", p), cand("q", q), cand("r", r)]
    uno = [tappe[0], tappe[2], tappe[3], tappe[1]]
    due = [tappe[0], tappe[3], tappe[2], tappe[1]]
    assert metri(uno) == metri(due) < metri(tappe)
    assert riordina(tappe) == ["s0", "q", "r", "p"]  # posizioni (0, 2, 3, 1) < (0, 3, 2, 1)
    # Scambiando q ed r nell'ordine di oggi, vince l'altro: lo decide la posizione.
    scambiate = [tappe[0], tappe[1], tappe[3], tappe[2]]
    assert riordina(scambiate) == ["s0", "r", "q", "p"]


def test_la_scelta_coincide_con_la_ricerca_esaustiva_indipendente() -> None:
    """Nessuna dipendenza dall'implementazione del riordino: ricerca esaustiva
    scritta qui con le sole funzioni di distanza dei contratti."""
    tappe = [
        cand("s0", punto(0, 0)),
        cand("a", punto(1750, 840)),
        cand("b", punto(2940, 90)),
        cand("c", punto(1110, 1610)),
        cand("d", punto(2450, 2820)),
    ]

    def totale(ordine: Sequence[GraphCandidate]) -> int:
        punti = [t.punti_arrivo[0] for t in ordine]
        return sum(distanza_a_piedi_m(x, y) for x, y in zip(punti, punti[1:], strict=False))

    oggi = totale(tappe)
    migliore: tuple[int, tuple[int, ...]] | None = None
    for perm in permutations(range(1, 5)):
        ordine = [tappe[0], *(tappe[i] for i in perm)]
        t = totale(ordine)
        if t < oggi and (migliore is None or (t, (0, *perm)) < migliore):
            migliore = (t, (0, *perm))
    atteso = ids(tappe) if migliore is None else [tappe[i].experience.id for i in migliore[1]]
    assert riordina(tappe) == atteso
    assert atteso != ids(tappe)


# --- Budget ---------------------------------------------------------------------


def casi_budget() -> list[GraphCandidate]:
    """Quattro tappe, 20 minuti l'una. Un SOLO ordine e' piu' corto di oggi
    (7260 m contro 7270) ma costa un minuto in piu' (173 contro 172): gli
    arrotondamenti dei trasferimenti non sono monotoni nei metri."""
    punti = [(1750, 840), (2940, 90), (1110, 1610), (2450, 2820)]
    return [cand(f"t{i}", punto(x, y), durata=20) for i, (x, y) in enumerate(punti)]


def test_budget_effettivo_un_ordine_piu_corto_ma_oltre_il_budget_non_e_ammesso() -> None:
    tappe = casi_budget()
    assert minuti(tappe) == 172
    # Budget di oggi: l'unico ordine piu' corto costa 173, e' scartato.
    assert riordina(tappe, budget=172) == ids(tappe)
    # Un minuto in piu': l'ordine piu' corto entra.
    risultato = riordina(tappe, budget=173)
    assert risultato != ids(tappe)
    nuovo = [next(t for t in tappe if t.experience.id == i) for i in risultato]
    assert metri(nuovo) < metri(tappe)
    assert minuti(nuovo) == 173


def test_ordine_ammesso_controlla_budget_e_orari_all_arrivo() -> None:
    tappe = [cand("a", punto(0)), cand("b", punto(800)), cand("c", punto(1600))]
    prog = motore._progressione(tappe)
    usati = minuti(tappe)
    ok = dict(ora_partenza=ORA, giorno_settimana=LUNEDI)
    assert motore._ordine_ammesso(tappe, prog, tempo_disponibile_min=usati, **ok)
    assert not motore._ordine_ammesso(tappe, prog, tempo_disponibile_min=usati - 1, **ok)
    chiusa = [tappe[0], cand("b", punto(800), orari=[(time(15, 0), time(18, 0))]), tappe[2]]
    assert not motore._ordine_ammesso(
        chiusa, motore._progressione(chiusa), tempo_disponibile_min=BUDGET_AMPIO, **ok
    )


# --- Ramo oltre 7 tappe mobili (vicino piu' prossimo) ------------------------------


def lunga_zigzag(n_mobili: int = 8) -> list[GraphCandidate]:
    """Prima tappa a 0 e `n_mobili` tappe lungo una retta, in ordine
    alternato lontano-vicino: il vicino piu' prossimo le mette in fila."""
    xs = list(range(1000, 1000 * (n_mobili + 1), 1000))
    alternate: list[int] = []
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        alternate.append(xs[hi])
        hi -= 1
        if lo <= hi:
            alternate.append(xs[lo])
            lo += 1
    return [cand("s0", punto(0))] + [cand(f"m{x}", punto(x)) for x in alternate]


@pytest.fixture
def solo_vicino_piu_prossimo(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Vieta le permutazioni e conta le chiamate al vicino piu' prossimo."""
    chiamate: list[int] = []
    originale = motore._vicino_piu_prossimo

    def spia(selezionati: Sequence[GraphCandidate], slot: Sequence[int]) -> list[int]:
        chiamate.append(len(slot))
        return list(originale(selezionati, slot))

    def vietate(*_a: object, **_k: object) -> None:
        raise AssertionError("sopra 7 tappe mobili non si provano le permutazioni")

    monkeypatch.setattr(motore, "_vicino_piu_prossimo", spia)
    monkeypatch.setattr(motore, "permutations", vietate)
    return chiamate


def test_caso7_sopra_sette_mobili_usa_il_vicino_piu_prossimo(
    solo_vicino_piu_prossimo: list[int],
) -> None:
    tappe = lunga_zigzag(8)
    assert motore.MAX_TAPPE_MOBILI_PERMUTAZIONI == 7
    risultato = riordina(tappe)
    assert solo_vicino_piu_prossimo == [8]
    assert risultato == ["s0"] + [f"m{x}" for x in range(1000, 9000, 1000)]
    nuovo = [next(t for t in tappe if t.experience.id == i) for i in risultato]
    assert metri(nuovo) < metri(tappe)
    assert sorted(risultato) == sorted(ids(tappe))


def test_caso7_fino_a_sette_mobili_si_provano_le_permutazioni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def vietato(*_a: object, **_k: object) -> list[int]:
        raise AssertionError("fino a 7 tappe mobili non serve il vicino piu' prossimo")

    monkeypatch.setattr(motore, "_vicino_piu_prossimo", vietato)
    tappe = lunga_zigzag(7)
    risultato = riordina(tappe)
    assert risultato == ["s0"] + [f"m{x}" for x in range(1000, 8000, 1000)]


def test_caso7_vincolo_orario_anche_nel_ramo_vicino_piu_prossimo(
    solo_vicino_piu_prossimo: list[int],
) -> None:
    """L'ultima tappa dell'ordine del vicino piu' prossimo e' chiusa all'arrivo:
    l'ordine non e' ammesso, resta quello di oggi."""
    tappe = lunga_zigzag(8)
    ultima = tappe[-1]  # nell'ordine di oggi
    # Nell'ordine NN la tappa m1000 e' la prima mobile (arrivo 10:47): apre alle 11.
    m1000 = next(i for i, t in enumerate(tappe) if t.experience.id == "m1000")
    tappe[m1000] = cand("m1000", punto(1000), orari=[(time(11, 0), time(23, 0))])
    assert ultima.experience.id != "m1000"
    assert riordina(tappe) == ids(tappe)
    assert solo_vicino_piu_prossimo == [8]


def test_caso7_vincolo_di_budget_nel_ramo_vicino_piu_prossimo(
    solo_vicino_piu_prossimo: list[int],
) -> None:
    """Nove tappe: il vicino piu' prossimo ha meno metri (9410 contro 9440) ma
    costa un minuto in piu' (301 contro 300)."""
    punti = [
        (1400, 1990), (650, 320), (120, 140), (170, 1840), (820, 1680),
        (940, 910), (1270, 1280), (1630, 500), (1930, 290),
    ]  # fmt: skip
    tappe = [cand(f"t{i}", punto(x, y), durata=20) for i, (x, y) in enumerate(punti)]
    assert minuti(tappe) == 300
    assert riordina(tappe, budget=300) == ids(tappe)
    risultato = riordina(tappe, budget=301)
    assert solo_vicino_piu_prossimo == [8, 8]
    assert risultato == ["t0", "t4", "t6", "t5", "t1", "t2", "t7", "t8", "t3"]
    nuovo = [next(t for t in tappe if t.experience.id == i) for i in risultato]
    assert (metri(nuovo), minuti(nuovo)) == (9410, 301)
    assert metri(tappe) == 9440


def test_caso7_se_non_migliora_resta_l_ordine_di_oggi(
    solo_vicino_piu_prossimo: list[int],
) -> None:
    tappe = [cand("s0", punto(0))] + [cand(f"m{i}", punto(1000 * i)) for i in range(1, 9)]
    assert riordina(tappe) == ids(tappe)
    assert solo_vicino_piu_prossimo == [8]


def test_caso7_le_tappe_senza_punto_non_contano_come_mobili(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """8 tappe con punto ma una e' una bottega: 7 mobili, permutazioni."""
    def vietato(*_a: object, **_k: object) -> list[int]:
        raise AssertionError("7 tappe mobili: permutazioni")

    monkeypatch.setattr(motore, "_vicino_piu_prossimo", vietato)
    tappe = lunga_zigzag(7)
    tappe.insert(4, cand("bottega", None))
    risultato = riordina(tappe)
    assert risultato[4] == "bottega"


# ---------------------------------------------------------------------------
# (3) Le code: `minuti_usati` sull'ordine finale
# ---------------------------------------------------------------------------


def _contesto(minuti_disponibili: int, *, violino: bool) -> VisitorContext:
    eventi = (
        [
            SegnaleFluttuante(
                id="violino",
                place_id="luogo-s0",
                temi=["arte"],
                descrizione="Un violinista",
                non_commerciale=True,
                valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
            )
        ]
        if violino
        else []
    )
    return VisitorContext(
        person_id="p",
        profile=EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
            tempo_disponibile_min=minuti_disponibili,
        ),
        signal=Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=ORA, eventi_attivi=eventi
        ),
    )


def _compone(
    tappe: list[GraphCandidate], budget: int
) -> list[str]:
    punteggi = {t.experience.id: 1.0 - i / 100 for i, t in enumerate(tappe)}
    it = compose_itinerary(
        _contesto(budget, violino=True),
        tappe,
        score_fn=lambda c, _p, _s: punteggi[c.experience.id],
        vocabolario=VOC,
    )
    return [s.experience_id for s in it.stops]


def test_caso8_il_riordino_libera_minuti_e_una_tappa_fluttuante_entra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le quattro tappe di oggi riempiono il budget esatto (nessun posto per il
    violinista: 25 minuti). L'ordine riordinato costa meno (`minuti_usati`
    sull'ordine FINALE) e il violinista entra in coda. Senza il riordino, no."""
    tappe = zigzag()
    budget = minuti(tappe)
    nuovo = [tappe[0], tappe[2], tappe[1], tappe[3]]
    costo_fluttuante = regole.TEMPO_TRASFERIMENTO_DEFAULT_MIN + regole.DURATA_TAPPA_FLUTTUANTE_MIN
    assert minuti(nuovo) + costo_fluttuante <= budget < minuti(tappe) + costo_fluttuante

    assert _compone(tappe, budget) == ["s0", "b", "a", "c", "fluttuante-violino"]

    monkeypatch.setattr(motore, "_riordina_per_vicinanza", lambda sel, **_kw: list(sel))
    assert _compone(tappe, budget) == ["s0", "a", "b", "c"]


def test_caso8_le_tappe_permanenti_non_cambiano_con_o_senza_riordino(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tappe = zigzag()
    budget = minuti(tappe)
    con = _compone(tappe, budget)
    monkeypatch.setattr(motore, "_riordina_per_vicinanza", lambda sel, **_kw: list(sel))
    senza = _compone(tappe, budget)
    assert sorted(i for i in con if not i.startswith("fluttuante-")) == sorted(senza)
    assert con[0] == senza[0]
