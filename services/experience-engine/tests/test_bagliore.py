"""Test del bagliore (docs/PROMOZIONE_TRACCIA.md §2b): funzione pura in
`rules.py` + integrazione in `compose_itinerary(..., tracce_per_luogo=...)`.

Il bagliore entra SOLO nel `reason` di tappe permanenti GIA' scelte: mai
nello scoring, nella selezione, nell'ordine. Questi test lo verificano."""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, date, datetime, time, timedelta

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
)
from experience_engine import compose_itinerary, rules
from experience_engine.engine import _costruisci_stops
from graph.seed_lucca import VOCABOLARIO

ADESSO = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
FRASE_ARTE = "È un luogo che torna spesso a vivere di arte."


def _t(giorni_fa: float, *temi: str) -> tuple[datetime, tuple[str, ...]]:
    return (ADESSO - timedelta(days=giorni_fa), tuple(temi))


# --- funzione pura ----------------------------------------------------------


@pytest.mark.parametrize("giorni", [0, 1, 30, 365, 3650, 10**5])
def test_peso_mai_zero_e_sopra_pavimento(giorni: float) -> None:
    p = rules.peso_traccia(timedelta(days=giorni))
    assert p > 0.0
    assert p >= rules.PAVIMENTO_BAGLIORE
    assert p <= 1.0


def test_peso_a_zero_giorni_e_uno() -> None:
    assert rules.peso_traccia(timedelta(0)) == 1.0


def test_peso_monotono_decrescente_su_griglia() -> None:
    griglia = [0, 0.5, 1, 2, 7, 14, 30, 60, 90, 180, 365, 1000]
    pesi = [rules.peso_traccia(timedelta(days=g)) for g in griglia]
    for a, b in zip(pesi, pesi[1:], strict=False):
        assert a >= b
    assert pesi[0] > pesi[-1]
    # strettamente decrescente finche' il residuo e' rappresentabile
    assert all(a > b for a, b in zip(pesi[:8], pesi[1:9], strict=False))


def test_peso_delta_negativo_vale_uno() -> None:
    assert rules.peso_traccia(timedelta(days=-5)) == 1.0
    assert rules.peso_traccia(timedelta(seconds=-1)) == 1.0


def test_somma_di_piu_tracce_supera_una_sola() -> None:
    una = rules.bagliore([_t(10, "arte")], ADESSO)
    tre = rules.bagliore([_t(10, "arte"), _t(10, "arte"), _t(20, "arte")], ADESSO)
    assert tre > una


def test_bagliore_vuoto_e_zero() -> None:
    assert rules.bagliore([], ADESSO) == 0.0


def test_bagliore_naive_trattato_come_utc() -> None:
    naive = (datetime(2026, 5, 31, 12, 0), ("arte",))
    aware = (datetime(2026, 5, 31, 12, 0, tzinfo=UTC), ("arte",))
    assert rules.bagliore([naive], ADESSO) == rules.bagliore([aware], ADESSO)


def test_sotto_soglia_nessuna_frase() -> None:
    assert rules.frase_bagliore([_t(400, "arte")], ADESSO) is None
    assert rules.frase_bagliore([_t(0, "arte")], ADESSO) is None  # una sola, peso <= 1
    assert rules.frase_bagliore([], ADESSO) is None


def test_molte_tracce_vecchie_superano_la_soglia_in_bagliore_ma_nessuna_frase() -> None:
    # Spec cambiata: la frase e' al presente, decide `bagliore_recente`.
    tracce = [_t(3650, "arte")] * 50  # bagliore() = 50 * ~0.05 = 2.5 >= soglia
    assert rules.bagliore(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.bagliore_recente(tracce, ADESSO) < 1e-6
    assert rules.frase_bagliore(tracce, ADESSO) is None


def test_40_tracce_di_3_anni_fa_nessuna_frase() -> None:
    tracce = [_t(3 * 365, "arte")] * 40
    assert rules.bagliore(tracce, ADESSO) == pytest.approx(2.0, abs=0.01)
    assert rules.bagliore_recente(tracce, ADESSO) < 1e-6
    assert rules.frase_bagliore(tracce, ADESSO) is None


def test_2_tracce_di_ieri_frase() -> None:
    assert rules.frase_bagliore([_t(1, "arte"), _t(1, "arte")], ADESSO) == FRASE_ARTE


def test_una_traccia_da_sola_non_basta_mai() -> None:
    assert rules.SOGLIA_BAGLIORE > 1 - rules.PAVIMENTO_BAGLIORE
    assert rules.frase_bagliore([_t(0, "arte")], ADESSO) is None
    assert rules.bagliore_recente([_t(0, "arte")], ADESSO) == pytest.approx(
        1 - rules.PAVIMENTO_BAGLIORE
    )


@pytest.mark.parametrize(
    ("n", "giorni", "frase"),
    [
        (2, 5, True),
        (2, 10, True),
        (2, 11, False),
        (2, 15, False),
        (3, 20, True),
        (3, 27, True),
        (3, 29, False),
        (3, 40, False),
    ],
)
def test_bordi_della_soglia(n: int, giorni: float, frase: bool) -> None:
    tracce = [_t(giorni, "arte")] * n
    assert (rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE) is frase
    assert rules.frase_bagliore(tracce, ADESSO) == (FRASE_ARTE if frase else None)


def test_bagliore_invariata_pavimento_incluso() -> None:
    assert rules.peso_traccia(timedelta(days=30)) == pytest.approx(0.525)
    assert rules.bagliore([_t(30, "arte")], ADESSO) == pytest.approx(0.525)
    assert rules.bagliore([_t(0, "arte")] * 2, ADESSO) == pytest.approx(2.0)
    assert rules.bagliore([], ADESSO) == 0.0


def test_tema_dominante_pesato_sulla_sola_parte_decadente() -> None:
    tracce = [_t(3 * 365, "musica")] * 40 + [_t(1, "arte")] * 2
    # col pavimento "musica" vincerebbe (40*0.05 = 2.0 > 2*~0.98)
    assert rules.tema_dominante(tracce, ADESSO) == "arte"
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE


def test_sopra_soglia_frase_esatta() -> None:
    tracce = [_t(1, "arte"), _t(2, "arte"), _t(3, "arte")]
    assert rules.bagliore(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE


def test_tema_dominante_pesato_non_contato() -> None:
    tracce = [_t(730, "musica"), _t(730, "musica"), _t(730, "musica"), _t(30, "arte")]
    # numericamente, con le costanti attuali: 3 vecchie < 1 recente
    peso_vecchia = rules.peso_traccia(timedelta(days=730))
    peso_recente = rules.peso_traccia(timedelta(days=30))
    assert 3 * peso_vecchia < peso_recente
    assert rules.tema_dominante(tracce, ADESSO) == "arte"
    # il conteggio puro direbbe "musica": il principio e' il peso
    assert sum("musica" in t for _, t in tracce) > sum("arte" in t for _, t in tracce)


def test_tema_dominante_spareggio_alfabetico() -> None:
    tracce = [_t(5, "musica"), _t(5, "arte")]
    assert rules.tema_dominante(tracce, ADESSO) == "arte"
    tracce = [_t(5, "storia"), _t(5, "musica")]
    assert rules.tema_dominante(tracce, ADESSO) == "musica"


def test_tema_dominante_nessun_tema() -> None:
    assert rules.tema_dominante([], ADESSO) is None
    assert rules.tema_dominante([_t(1)], ADESSO) is None


def test_tema_ripetuto_nella_stessa_traccia_conta_una_volta() -> None:
    assert rules.tema_dominante([_t(1, "arte", "arte"), _t(1, "musica")], ADESSO) == "arte"
    # musica,musica pesa quanto una sola volta: pareggio con arte -> alfabetico
    pareggio = [_t(1, "musica", "musica"), _t(1, "arte")]
    assert rules.tema_dominante(pareggio, ADESSO) == "arte"


@pytest.mark.parametrize(
    ("tema", "attesa"),
    [
        ("arte", "È un luogo che torna spesso a vivere di arte."),
        ("artigianato", "È un luogo che torna spesso a vivere di artigianato."),
    ],
)
def test_grammatica_senza_articolo(tema: str, attesa: str) -> None:
    tracce = [_t(1, tema), _t(1, tema), _t(2, tema)]
    assert rules.frase_bagliore(tracce, ADESSO) == attesa


# --- fixture motore ---------------------------------------------------------


def _esp(eid: str, place: str, temi: list[str], *, partner: bool = False) -> ExperienceNode:
    return ExperienceNode(
        id=eid, titolo=f"Titolo {eid}", place_id=place, temi=temi, durata_min=30,
        al_chiuso=True, accessibile=True, partner_id="bottega-x" if partner else None,
    )


def _cand(
    eid: str, place: str, temi: list[str], dist: float = 100.0, attribuzione: str | None = None,
    partner: bool = False,
) -> GraphCandidate:
    return GraphCandidate(
        experience=_esp(eid, place, temi, partner=partner), place_nome=f"Luogo {place}",
        connessioni=['Evoca il tema "Arte".'], distanza_m=dist, attribuzione=attribuzione,
    )


PROFILO = EmotionalProfile(
    curiosita=0.5, contemplazione=0.4, arte=0.9, con_bambini=False, tempo_disponibile_min=300
)


def _ctx(eventi: list[SegnaleFluttuante] | None = None, data: date | None = None) -> VisitorContext:
    return VisitorContext(
        person_id="p", profile=PROFILO,
        signal=Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
            eventi_attivi=eventi or [], data=data,
        ),
    )


def _candidati() -> list[GraphCandidate]:
    return [
        _cand("exp-a", "luogo-a", ["arte"], 100.0),
        _cand("exp-b", "luogo-b", ["arte", "storia"], 200.0),
        _cand("exp-c", "luogo-c", ["contemplazione"], 300.0),
    ]


def _tracce_recenti(*temi: str, n: int = 3) -> list[tuple[datetime, tuple[str, ...]]]:
    ora = datetime.now(UTC)
    return [(ora - timedelta(days=1 + i), tuple(temi)) for i in range(n)]


class _Spia:
    """reason_fn finto: registra gli argomenti, restituisce testo fisso."""

    def __init__(self, includi: str = "") -> None:
        self.chiamate: list[tuple] = []
        self.includi = includi

    def __call__(self, cand, profile, segnali):
        self.chiamate.append((cand, profile, tuple(segnali)))
        return f"Motivo di {cand.experience.id}." + (f" {self.includi}" if self.includi else "")


# --- motore: nessun effetto su score/selezione/ordine -----------------------


def test_score_e_ordine_bit_identici_con_e_senza_tracce() -> None:
    def componi(tracce):
        visti: list[tuple[str, float]] = []

        def score_fn(cand, profile, signal):
            s = rules.calcola_score(cand, profile, signal, vocabolario=VOCABOLARIO)
            visti.append((cand.experience.id, s))
            return s

        it = compose_itinerary(
            _ctx(),
            _candidati(),
            _Spia(),
            score_fn=score_fn,
            tracce_per_luogo=tracce,
            vocabolario=VOCABOLARIO,
        )
        return visti, it

    tracce = {"luogo-a": _tracce_recenti("arte"), "luogo-b": _tracce_recenti("storia")}
    visti_senza, it_senza = componi(None)
    visti_con, it_con = componi(tracce)
    assert visti_senza and visti_senza == visti_con  # stessi float, stessa sequenza
    assert [s.experience_id for s in it_senza.stops] == [s.experience_id for s in it_con.stops]


def test_tappe_identiche_unica_differenza_il_reason() -> None:
    tracce = {"luogo-a": _tracce_recenti("arte"), "luogo-b": _tracce_recenti("storia")}
    senza = compose_itinerary(_ctx(), _candidati(), _Spia(), vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        _ctx(), _candidati(), _Spia(), tracce_per_luogo=tracce, vocabolario=VOCABOLARIO,
    )
    assert len(senza.stops) == len(con.stops) >= 2
    for a, b in zip(senza.stops, con.stops, strict=True):
        assert a.model_dump(exclude={"reason"}) == b.model_dump(exclude={"reason"})
    assert any(a.reason != b.reason for a, b in zip(senza.stops, con.stops, strict=True))


def test_frase_esatta_dopo_reason_fn_e_reason_fn_non_la_vede() -> None:
    tracce = {"luogo-a": _tracce_recenti("arte")}
    spia_senza, spia_con = _Spia(), _Spia()
    senza = compose_itinerary(_ctx(), _candidati(), spia_senza, vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        _ctx(), _candidati(), spia_con, tracce_per_luogo=tracce, vocabolario=VOCABOLARIO,
    )

    assert spia_senza.chiamate == spia_con.chiamate  # stessi argomenti, mai la frase
    assert FRASE_ARTE not in repr(spia_con.chiamate)

    per_id_senza = {s.experience_id: s.reason for s in senza.stops}
    per_id_con = {s.experience_id: s.reason for s in con.stops}
    assert per_id_con["exp-a"] == f"{per_id_senza['exp-a']} {FRASE_ARTE}"
    assert per_id_con["exp-a"].index("Motivo di exp-a.") < per_id_con["exp-a"].index(FRASE_ARTE)
    for eid in per_id_con:  # luoghi senza tracce: invariati
        if eid != "exp-a":
            assert per_id_con[eid] == per_id_senza[eid]


def test_sotto_soglia_nel_motore_reason_invariato() -> None:
    tracce = {"luogo-a": [(datetime.now(UTC) - timedelta(days=1), ("arte",))]}
    senza = compose_itinerary(_ctx(), _candidati(), _Spia(), vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        _ctx(), _candidati(), _Spia(), tracce_per_luogo=tracce, vocabolario=VOCABOLARIO,
    )
    assert [s.reason for s in senza.stops] == [s.reason for s in con.stops]


@pytest.mark.parametrize("includi_nel_reason_fn", [False, True])
def test_disclosure_partner_resta_ultima_frase(includi_nel_reason_fn: bool) -> None:
    attr = "Offerta da Bottega Rossi, bottega di liuteria."
    cands = [
        _cand("exp-p", "luogo-p", ["arte"], 100.0, attribuzione=attr, partner=True),
        _cand("exp-b", "luogo-b", ["storia"], 200.0),
    ]
    spia = _Spia(includi=attr if includi_nel_reason_fn else "")
    it = compose_itinerary(
        _ctx(),
        cands,
        spia,
        tracce_per_luogo={"luogo-p": _tracce_recenti("arte")},
        vocabolario=VOCABOLARIO,
    )
    reason = next(s.reason for s in it.stops if s.experience_id == "exp-p")
    assert reason.endswith(attr)
    assert reason.count(attr) == 1
    assert FRASE_ARTE in reason
    assert reason.index(FRASE_ARTE) < reason.index(attr)
    assert reason.index("Motivo di exp-p.") < reason.index(FRASE_ARTE)
    assert reason == f"Motivo di exp-p. {FRASE_ARTE} {attr}"


@pytest.mark.parametrize("tracce", [None, {}])
def test_tracce_none_o_vuote_reason_identico_a_oggi(tracce) -> None:
    base = compose_itinerary(_ctx(), _candidati(), _Spia(), vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        _ctx(), _candidati(), _Spia(), tracce_per_luogo=tracce, vocabolario=VOCABOLARIO,
    )
    assert base.model_dump(exclude={"generated_at"}) == con.model_dump(exclude={"generated_at"})


def test_tracce_di_luoghi_non_candidati_ignorate() -> None:
    base = compose_itinerary(_ctx(), _candidati(), _Spia(), vocabolario=VOCABOLARIO)
    con = compose_itinerary(
        _ctx(),
        _candidati(),
        _Spia(),
        tracce_per_luogo={"altrove": _tracce_recenti("arte")},
        vocabolario=VOCABOLARIO,
    )
    assert base.model_dump(exclude={"generated_at"}) == con.model_dump(exclude={"generated_at"})


def test_tappe_fluttuanti_ed_eventi_promossi_senza_frase() -> None:
    flutt = SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza", temi=["musica"],
        place_id="luogo-a", non_commerciale=True, valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    evento = EventoPromosso(
        id="evento-luogo-a-musica", place_id="luogo-a", temi=["musica"],
        ultima_occorrenza=date(2026, 3, 2), cadenza_giorni=30.0,
    )
    data = date(2026, 4, 1)  # = ultima + 30 giorni
    tracce = {"luogo-a": _tracce_recenti("musica")}
    it = compose_itinerary(
        _ctx([flutt], data), _candidati(), _Spia(), eventi_promossi=[evento],
        tracce_per_luogo=tracce,
        vocabolario=VOCABOLARIO,
    )
    ids = [s.experience_id for s in it.stops]
    assert "fluttuante-violinista-1" in ids and "evento-luogo-a-musica" in ids
    frase = "È un luogo che torna spesso a vivere di musica."
    assert any(s.experience_id == "exp-a" and s.reason.endswith(frase) for s in it.stops)
    base = compose_itinerary(
        _ctx([flutt], data),
        _candidati(),
        _Spia(),
        eventi_promossi=[evento],
        vocabolario=VOCABOLARIO,
    )
    for s in it.stops:
        if s.experience_id in ("fluttuante-violinista-1", "evento-luogo-a-musica"):
            assert "torna spesso a vivere" not in s.reason
    code_con = [s for s in it.stops if s.experience_id != "exp-a"]
    code_base = [s for s in base.stops if s.experience_id != "exp-a"]
    assert code_con == code_base


# --- test-guard AST: visibilita' / score non toccati dal bagliore -----------

NOMI_BAGLIORE_VIETATI = {
    "bagliore", "frase_bagliore", "tema_dominante", "peso_traccia", "tracce_per_luogo",
    "temi_leggibili", "PAVIMENTO_BAGLIORE", "EMIVITA_BAGLIORE_GIORNI", "SOGLIA_BAGLIORE",
}


def _identificatori(funzione) -> set[str]:
    albero = ast.parse(textwrap.dedent(inspect.getsource(funzione)))
    f = albero.body[0]
    assert isinstance(f, ast.FunctionDef)
    if f.body and isinstance(f.body[0], ast.Expr) and isinstance(f.body[0].value, ast.Constant):
        f.body = f.body[1:]  # docstring esclusa: conta il codice eseguito
    nomi: set[str] = set()
    for n in ast.walk(f):
        if isinstance(n, ast.Name):
            nomi.add(n.id)
        elif isinstance(n, ast.Attribute):
            nomi.add(n.attr)
        elif isinstance(n, ast.arg):
            nomi.add(n.arg)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            nomi.add(n.value)
    return nomi


@pytest.mark.parametrize("funzione", [rules.calcola_score, rules.passa_filtri_duri])
def test_guard_score_e_filtri_non_referenziano_il_bagliore(funzione) -> None:
    nomi = _identificatori(funzione)
    assert not (nomi & NOMI_BAGLIORE_VIETATI), nomi & NOMI_BAGLIORE_VIETATI
    assert not [n for n in nomi if "bagliore" in n.lower()]


def test_guard_non_e_vacuo() -> None:
    def finta(c, p, s, tracce_per_luogo=None):
        return rules.bagliore(tracce_per_luogo, s)

    assert _identificatori(finta) & NOMI_BAGLIORE_VIETATI


# --- una frase per luogo, adesso iniettato ----------------------------------


def _tracce_fisse(*temi: str, n: int = 3) -> list[tuple[datetime, tuple[str, ...]]]:
    return [(ADESSO - timedelta(days=1 + i), tuple(temi)) for i in range(n)]


def test_due_tappe_stesso_luogo_frase_una_sola_volta_sulla_prima() -> None:
    """Guardia di `_costruisci_stops`: la composizione sceglie al piu' una tappa
    per luogo (regola "una tappa per luogo", ondata 1b-2), quindi il caso di due
    tappe nello stesso luogo non e' piu' raggiungibile da `compose_itinerary`.
    La guardia pero' resta nel codice: la si esercita chiamando direttamente
    `_costruisci_stops` con due candidati dello stesso luogo."""
    selezionati = [
        _cand("exp-a1", "luogo-a", ["arte"], 100.0),
        _cand("exp-a2", "luogo-a", ["arte"], 150.0),
        _cand("exp-b", "luogo-b", ["arte"], 200.0),
    ]
    tracce = {"luogo-a": _tracce_fisse("arte"), "luogo-b": _tracce_fisse("arte")}
    stops = _costruisci_stops(
        selezionati, PROFILO, _ctx().signal, _Spia(),
        tracce_per_luogo=tracce, adesso=ADESSO, vocabolario=VOCABOLARIO,
    )
    del_luogo_a = [s for s in stops if s.experience_id in ("exp-a1", "exp-a2")]
    assert len(del_luogo_a) == 2  # il caso e' davvero esercitato
    assert [FRASE_ARTE in s.reason for s in del_luogo_a] == [True, False]
    assert sum(s.reason.count(FRASE_ARTE) for s in stops) == 2  # una per luogo
    b = next(s for s in stops if s.experience_id == "exp-b")
    assert FRASE_ARTE in b.reason


def test_la_composizione_non_produce_due_tappe_nello_stesso_luogo_col_bagliore() -> None:
    """Con la regola "una tappa per luogo" la frase del bagliore compare una
    sola volta per luogo anche da `compose_itinerary`."""
    cands = [
        _cand("exp-a1", "luogo-a", ["arte"], 100.0),
        _cand("exp-a2", "luogo-a", ["arte"], 150.0),
        _cand("exp-b", "luogo-b", ["arte"], 200.0),
    ]
    tracce = {"luogo-a": _tracce_fisse("arte"), "luogo-b": _tracce_fisse("arte")}
    it = compose_itinerary(
        _ctx(), cands, _Spia(), tracce_per_luogo=tracce, adesso=ADESSO, vocabolario=VOCABOLARIO,
    )
    assert len([s for s in it.stops if s.experience_id in ("exp-a1", "exp-a2")]) == 1
    assert sum(s.reason.count(FRASE_ARTE) for s in it.stops) == 2  # luogo-a e luogo-b


def test_adesso_e_keyword_only() -> None:
    with pytest.raises(TypeError):
        compose_itinerary(  # type: ignore[misc]
            _ctx(), _candidati(), _Spia(), None, None, None, ADESSO, vocabolario=VOCABOLARIO
        )


def test_adesso_esplicito_deterministico_e_governa_il_decadimento() -> None:
    tracce = {"luogo-a": _tracce_fisse("arte")}
    r1 = compose_itinerary(
        _ctx(),
        _candidati(),
        _Spia(),
        tracce_per_luogo=tracce,
        adesso=ADESSO,
        vocabolario=VOCABOLARIO,
    )
    r2 = compose_itinerary(
        _ctx(),
        _candidati(),
        _Spia(),
        tracce_per_luogo=tracce,
        adesso=ADESSO,
        vocabolario=VOCABOLARIO,
    )
    assert [s.reason for s in r1.stops] == [s.reason for s in r2.stops]
    assert any(FRASE_ARTE in s.reason for s in r1.stops)
    tardi = ADESSO + timedelta(days=3 * 365)
    r3 = compose_itinerary(
        _ctx(),
        _candidati(),
        _Spia(),
        tracce_per_luogo=tracce,
        adesso=tardi,
        vocabolario=VOCABOLARIO,
    )
    assert all(FRASE_ARTE not in s.reason for s in r3.stops)


# --- tetto sull'eta' dell'ultima traccia ------------------------------------


def test_tetto_e_derivato_dall_emivita() -> None:
    assert rules.ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI == 2 * rules.EMIVITA_BAGLIORE_GIORNI


def test_40_tracce_con_ultima_a_130_giorni_decide_il_tetto() -> None:
    tracce = [_t(130, "arte")] * 40
    # senza il tetto la soglia sarebbe superata: decide il tetto
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) is None


def test_tetto_2_tracce_di_ieri_frase() -> None:
    assert rules.frase_bagliore([_t(1, "arte"), _t(1, "arte")], ADESSO) == FRASE_ARTE


def test_bordo_59_giorni_frase() -> None:
    tracce = [_t(59, "arte")] * 10
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE


def test_bordo_61_giorni_nessuna_frase_decide_il_tetto() -> None:
    tracce = [_t(61, "arte")] * 10
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) is None


def test_bordo_esattamente_60_giorni_ammesso() -> None:
    tracce = [_t(60, "arte")] * 10
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE


def test_bordo_60_giorni_piu_un_secondo_nessuna_frase() -> None:
    tracce = [(ADESSO - timedelta(days=60, seconds=1), ("arte",))] * 10
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) is None


def test_molte_vecchie_piu_una_recente_decide_l_ultima() -> None:
    vecchie = [_t(130, "arte")] * 40
    assert rules.frase_bagliore(vecchie, ADESSO) is None
    tracce = [*vecchie, _t(1, "arte")]
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE


def test_traccia_nel_futuro_non_e_esclusa_dal_tetto() -> None:
    futura = (ADESSO + timedelta(days=5), ("arte",))
    tracce = [*([_t(130, "arte")] * 40), futura]
    assert rules.bagliore_recente(tracce, ADESSO) >= rules.SOGLIA_BAGLIORE
    assert rules.frase_bagliore(tracce, ADESSO) == FRASE_ARTE
    # solo tracce future: eta' 0, pesano 1 ciascuna
    assert rules.frase_bagliore([futura, futura], ADESSO) == FRASE_ARTE


def test_naive_e_aware_misti_nel_tetto() -> None:
    naive_ieri = (datetime(2026, 5, 31, 12, 0), ("arte",))
    aware_ieri = (datetime(2026, 5, 31, 12, 0, tzinfo=UTC), ("arte",))
    assert rules.frase_bagliore([naive_ieri, aware_ieri], ADESSO) == FRASE_ARTE
    # adesso naive con tracce aware
    adesso_naive = datetime(2026, 6, 1, 12, 0)
    assert rules.frase_bagliore([aware_ieri, naive_ieri], adesso_naive) == FRASE_ARTE
    # naive oltre il tetto
    vecchia_naive = (datetime(2026, 3, 1, 12, 0), ("arte",))
    assert rules.frase_bagliore([vecchia_naive] * 40, ADESSO) is None
