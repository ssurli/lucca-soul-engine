"""Regola "una tappa per luogo" (ondata 1b-2, approvata dal committente).

Composizione: `_seleziona_tappe` ammette al massimo UNA esperienza per `place_id`
(prima erano 2). Adattamento: un sostituto non puo' avere il `place_id` di
un'ALTRA tappa rimasta nell'itinerario; il luogo della tappa sostituita e'
ammesso (facciata -> interno della stessa chiesa). Gli stub (tappe fluttuanti,
eventi promossi, esperienze sparite) non occupano luoghi. La regola legge solo
`place_id`: mai partner, prezzo, attribuzione.

Motivazione etica: distribuzione dei flussi. Due tappe nello stesso luogo
concentrano le visite senza aggiungere esperienza.

Scenari a punteggio controllato: profilo con solo `arte=1`, vocabolario con
arte={"arte","arte2"} (ogni tema d'arte aggiunge 0.15, max due).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from datetime import datetime, time

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
    VocabolarioTemi,
)
from experience_engine import adapt_itinerary, compose_itinerary
from experience_engine import engine as motore
from experience_engine.engine import _migliore_alternativa
from experience_engine.rules import SOGLIA_AFFOLLAMENTO_ADATTAMENTO
from rag.reasons import adapt_reason, compose_reason

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte", "arte2"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)


def _profilo(minuti: int) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.0, contemplazione=0.0, arte=1.0, con_bambini=False,
        tempo_disponibile_min=minuti,
    )


SERENO = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(9, 0))
PIOGGIA = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(9, 0))


def _cand(
    id_: str,
    luogo: str,
    temi: list[str],
    *,
    al_chiuso: bool = True,
    durata: int = 30,
    prezzo: float | None = None,
    partner_id: str | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=luogo, temi=temi,
            durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
            prezzo_eur=prezzo, partner_id=partner_id,
        ),
        place_nome=f"Luogo {luogo}",
        connessioni=[],
        distanza_m=0,  # trasferimento 0: il budget conta solo le durate
    )


def _compose(candidati: list[GraphCandidate], minuti: int) -> Itinerary:
    ctx = VisitorContext(person_id="p", profile=_profilo(minuti), signal=SERENO)
    return compose_itinerary(ctx, candidati, compose_reason, vocabolario=VOC)


def _itinerario(ids_durate: list[tuple[str, int]], minuti: int = 600) -> Itinerary:
    stops: list[ItineraryStop] = []
    ora = 9 * 60
    for id_, durata in ids_durate:
        stops.append(
            ItineraryStop(
                experience_id=id_, arrivo=time(ora // 60, ora % 60), durata_min=durata,
                reason="Motivo originale.",
            )
        )
        ora += durata
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=minuti, tempo_effettivo_min=minuti,
    )


def _adatta(itinerario: Itinerary, candidati: list[GraphCandidate]) -> Itinerary:
    return adapt_itinerary(
        itinerario, PIOGGIA, candidati, _profilo(600), compose_reason, adapt_reason,
        vocabolario=VOC,
    )


def _luoghi(it: Itinerary, candidati: list[GraphCandidate]) -> list[str]:
    per_id = {c.experience.id: c.experience.place_id for c in candidati}
    return [per_id.get(s.experience_id, s.experience_id) for s in it.stops]


# --- 1. composizione ---------------------------------------------------------


def _scenario_compose() -> list[GraphCandidate]:
    return [
        # Due esperienze MOLTO pertinenti nello stesso luogo.
        _cand("a1", "luogo-a", ["arte", "arte2"]),
        _cand("a2", "luogo-a", ["arte", "arte2"]),
        # Meno pertinenti, in luoghi diversi (temi primari distinti: niente
        # scambi per diversificazione).
        _cand("b", "luogo-b", ["arte"]),
        _cand("c", "luogo-c", ["arte"]),
    ]


def test_composizione_una_sola_esperienza_per_luogo() -> None:
    cands = _scenario_compose()
    it = _compose(cands, minuti=90)  # tre slot da 30'
    luoghi = _luoghi(it, cands)
    assert luoghi.count("luogo-a") == 1
    assert len(set(luoghi)) == len(luoghi)  # nessun luogo ripetuto


def test_composizione_il_budget_liberato_va_a_un_altro_luogo() -> None:
    cands = _scenario_compose()
    it = _compose(cands, minuti=90)
    ids = [s.experience_id for s in it.stops]
    # Prima: a1, a2, b (due tappe in luogo-a). Ora: a1, b, c.
    assert ids[0] == "a1"
    assert "a2" not in ids
    assert len(ids) == 3
    assert {"b", "c"} <= set(ids)


def test_composizione_un_luogo_resta_occupato_anche_se_il_secondo_non_entrerebbe() -> None:
    """Il luogo e' occupato fino alla fine: anche un'esperienza piu' breve, che
    entrerebbe nel budget residuo, non rientra."""
    cands = [
        _cand("a1", "luogo-a", ["arte", "arte2"], durata=30),
        _cand("a2", "luogo-a", ["arte", "arte2"], durata=10),
    ]
    it = _compose(cands, minuti=100)
    assert [s.experience_id for s in it.stops] == ["a1"]


# --- 2. sostituzione ---------------------------------------------------------


def _scenario_sostituzione() -> list[GraphCandidate]:
    return [
        # Tappa all'aperto, tolta dalla pioggia.
        _cand("x", "luogo-x", ["tema-x"], al_chiuso=False),
        # Tappa rimasta (al chiuso), nel luogo y.
        _cand("y", "luogo-y", ["altro"]),
        # Il miglior sostituto (condivide un tema con x) sta nel luogo di y.
        _cand("alt-y", "luogo-y", ["arte", "arte2", "tema-x"]),
        # Sostituto peggiore (nessun tema in comune) in un luogo libero.
        _cand("alt-z", "luogo-z", ["nulla"]),
    ]


def test_sostituzione_non_raddoppia_il_luogo_di_una_tappa_rimasta() -> None:
    cands = _scenario_sostituzione()
    out = _adatta(_itinerario([("x", 30), ("y", 30)]), cands)
    luoghi = _luoghi(out, cands)
    assert len(set(luoghi)) == len(luoghi), luoghi
    ids = [s.experience_id for s in out.stops]
    assert "alt-y" not in ids  # il miglior sostituto sta nel luogo di y
    assert ids == ["alt-z", "y"]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_sostituzione_senza_altri_luoghi_resta_mantenuta_senza_alternativa() -> None:
    cands = [c for c in _scenario_sostituzione() if c.experience.id != "alt-z"]
    out = _adatta(_itinerario([("x", 30), ("y", 30)]), cands)
    assert [s.experience_id for s in out.stops] == ["x", "y"]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert out.stops[0].reason.strip()


def test_sostituzioni_in_sequenza_contano_le_scelte_precedenti() -> None:
    """Due tappe all'aperto, due sostituti nello stesso luogo w: il primo entra,
    il secondo no (il luogo w e' ora occupato dalla sostituzione precedente)."""
    cands = [
        _cand("x1", "luogo-x1", ["t1"], al_chiuso=False),
        _cand("x2", "luogo-x2", ["t2"], al_chiuso=False),
        _cand("w1", "luogo-w", ["arte", "arte2", "t1", "t2"]),
        _cand("w2", "luogo-w", ["arte", "t1", "t2"]),
    ]
    out = _adatta(_itinerario([("x1", 30), ("x2", 30)]), cands)
    assert [s.experience_id for s in out.stops] == ["w1", "x2"]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.SOSTITUITA
    assert out.stops[1].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


def test_migliore_alternativa_luoghi_occupati_esclude_per_place_id() -> None:
    tolta = _cand("x", "luogo-x", ["tema-x"], al_chiuso=False)
    alt_y = _cand("alt-y", "luogo-y", ["arte", "arte2", "tema-x"])
    alt_z = _cand("alt-z", "luogo-z", ["nulla"])

    def scegli(occupati: frozenset[str]) -> str | None:
        alt = _migliore_alternativa(
            candidates=[tolta, alt_y, alt_z], signal=PIOGGIA, profile=_profilo(600),
            esclusi={"x"}, richiede_accessibile=False, solo_al_chiuso=True,
            max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
            luoghi_occupati=occupati, arrivo_di=lambda _c: PIOGGIA.ora,
            vocabolario=VOC, prezzo_tolta=0.0, temi_tolta=tolta.experience.temi,
        )
        return None if alt is None else alt.experience.id

    assert scegli(frozenset()) == "alt-y"
    assert scegli(frozenset({"luogo-y"})) == "alt-z"
    assert scegli(frozenset({"luogo-y", "luogo-z"})) is None


# --- 3. garanzia: stesso luogo della tappa TOLTA resta ammesso ----------------


def test_facciata_to_interno_stesso_luogo_con_pioggia_resta_ammesso() -> None:
    cands = [
        _cand("facciata", "chiesa", ["tema-f"], al_chiuso=False),
        _cand("interno", "chiesa", ["arte", "tema-f"]),
        _cand("altro", "luogo-altro", ["arte"]),
    ]
    out = _adatta(_itinerario([("facciata", 30), ("altro", 30)]), cands)
    assert [s.experience_id for s in out.stops] == ["interno", "altro"]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.SOSTITUITA


def test_interno_della_chiesa_vietato_se_un_altra_tappa_rimasta_e_in_chiesa() -> None:
    """Contrappeso: se un'ALTRA tappa rimasta sta gia' nella chiesa, l'interno
    non e' un sostituto ammesso."""
    cands = [
        _cand("facciata", "chiesa", ["tema-f"], al_chiuso=False),
        _cand("cripta", "chiesa", ["altro"]),
        _cand("interno", "chiesa", ["arte", "tema-f"]),
    ]
    out = _adatta(_itinerario([("facciata", 30), ("cripta", 30)]), cands)
    assert [s.experience_id for s in out.stops] == ["facciata", "cripta"]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


# --- 4. garanzia: gli stub non bloccano nessun luogo ---------------------------


@pytest.mark.parametrize("stub", ["fluttuante-violinista-1", "exp-sparita"])
def test_gli_stub_non_occupano_luoghi(stub: str) -> None:
    """Lo stub ha `place_id` fittizio = proprio `experience_id`: se contasse, un
    candidato in un luogo con quell'id sarebbe bloccato. Non deve."""
    cands = [
        _cand("x", "luogo-x", ["tema-x"], al_chiuso=False),
        _cand("alt", stub, ["arte", "arte2", "tema-x"]),  # place_id == id dello stub
    ]
    out = _adatta(_itinerario([("x", 30), (stub, 15)]), cands)
    assert [s.experience_id for s in out.stops] == ["alt", stub]
    assert out.stops[0].esito_adattamento == EsitoAdattamento.SOSTITUITA
    assert out.stops[1].reason == "Motivo originale."  # lo stub resta intatto


# --- 5. guardia: la regola legge solo place_id ---------------------------------

NOMI_VIETATI = {
    "partner_id", "prezzo_eur", "attribuzione", "abbonamento_attivo", "partner", "prezzo",
}


def _nomi(nodo: ast.AST) -> set[str]:
    nomi: set[str] = set()
    for n in ast.walk(nodo):
        if isinstance(n, ast.Name):
            nomi.add(n.id)
        elif isinstance(n, ast.Attribute):
            nomi.add(n.attr)
        elif isinstance(n, ast.keyword) and n.arg:
            nomi.add(n.arg)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            nomi.add(n.value)
    return nomi


def _albero(funzione: Callable[..., object]) -> ast.FunctionDef:
    f = ast.parse(textwrap.dedent(inspect.getsource(funzione))).body[0]
    assert isinstance(f, ast.FunctionDef)
    if f.body and isinstance(f.body[0], ast.Expr) and isinstance(f.body[0].value, ast.Constant):
        f.body = f.body[1:]  # docstring esclusa
    return f


def test_guardia_seleziona_tappe_non_legge_partner_ne_prezzo() -> None:
    nomi = _nomi(_albero(motore._seleziona_tappe))
    assert "place_id" in nomi  # la guardia non e' vacua
    assert not (nomi & NOMI_VIETATI), nomi & NOMI_VIETATI


def test_guardia_vincolo_nella_sostituzione_legge_solo_place_id() -> None:
    # 1) il filtro in `_migliore_alternativa`: l'`if` che usa `luoghi_occupati`.
    f = _albero(_migliore_alternativa)
    blocchi = [
        n for n in ast.walk(f)
        if isinstance(n, ast.If) and "luoghi_occupati" in _nomi(n.test)
    ]
    assert len(blocchi) == 1
    assert "place_id" in _nomi(blocchi[0].test)
    assert not (_nomi(blocchi[0]) & NOMI_VIETATI), _nomi(blocchi[0]) & NOMI_VIETATI
    # 2) la costruzione dell'insieme in `adapt_itinerary`.
    g = _albero(adapt_itinerary)
    costruzioni = [
        n for n in ast.walk(g)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "luoghi_occupati" for t in n.targets)
    ]
    assert len(costruzioni) == 1
    nomi = _nomi(costruzioni[0])
    assert "place_id" in nomi
    assert not (nomi & NOMI_VIETATI), nomi & NOMI_VIETATI


def test_guardia_non_e_vacua() -> None:
    def finta(c: GraphCandidate) -> bool:
        return c.experience.partner_id is not None and c.experience.prezzo_eur == 0

    assert _nomi(ast.parse(textwrap.dedent(inspect.getsource(finta)))) & NOMI_VIETATI


@pytest.mark.parametrize(
    ("prezzo", "partner"), [(None, None), (0.0, "bottega-x"), (5.0, "bottega-x")]
)
def test_il_blocco_del_luogo_non_dipende_da_partner_ne_prezzo(
    prezzo: float | None, partner: str | None
) -> None:
    """Un sostituto nel luogo di una tappa rimasta e' escluso quale che sia il
    suo partner o prezzo: la regola non fa sconti ne' eccezioni commerciali."""
    tolta = _cand("x", "luogo-x", ["tema-x"], al_chiuso=False, prezzo=5.0)
    nel_luogo = _cand(
        "alt-y", "luogo-y", ["arte", "arte2", "tema-x"], prezzo=prezzo, partner_id=partner
    )
    alt = _migliore_alternativa(
        candidates=[tolta, nel_luogo], signal=PIOGGIA, profile=_profilo(600),
        esclusi={"x"}, richiede_accessibile=False, solo_al_chiuso=True,
        max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
        luoghi_occupati=frozenset({"luogo-y"}), arrivo_di=lambda _c: PIOGGIA.ora,
        vocabolario=VOC, prezzo_tolta=5.0, temi_tolta=tolta.experience.temi,
    )
    assert alt is None
