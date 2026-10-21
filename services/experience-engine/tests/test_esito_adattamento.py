"""Esito dell'adattamento, budget nelle sostituzioni, tappe escluse
(wave "adattamento", decisioni di prodotto 3 e 4).

- ogni tappa presente dopo un adattamento ha `esito_adattamento`;
- `MANTENUTA_SENZA_ALTERNATIVA` se e solo se il `reason` contiene la frase
  (pioggia o affollamento), con la disclosure partner sempre ultima;
- un'alternativa entra solo se l'itinerario resta nel budget
  (min(tempo_effettivo_min, minuti alla mezzanotte)); itinerario senza budget:
  nessun vincolo sulle sostituzioni;
- `adattato_da_segnale` True se e solo se c'è una sostituita o una tagliata;
  con sole mantenute gli arrivi restano quelli ricevuti;
- `tappe_escluse` si accumula tra adattamenti, una voce per id, vince la più
  recente; la frase di esito non si duplica.
"""

from __future__ import annotations

import re
from datetime import datetime, time

from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    TappaEsclusa,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary
from graph.seed_lucca import VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

FRASE_PIOGGIA = (
    "Con la pioggia non c'è un'alternativa al coperto compatibile con questo percorso "
    "e con il tempo a disposizione: la tappa resta in programma."
)


def frase_affollamento(luogo: str) -> str:
    return (
        f"C'è molta gente a {luogo}, ma non c'è un'alternativa più tranquilla compatibile "
        "con questo percorso e con il tempo a disposizione: la tappa resta in programma."
    )


_RE_AFFOLLAMENTO = re.compile(
    re.escape("C'è molta gente a ")
    + ".+?"
    + re.escape(
        ", ma non c'è un'alternativa più tranquilla compatibile con questo percorso "
        "e con il tempo a disposizione: la tappa resta in programma."
    )
)
FRASE_STANCHEZZA = "Tolta per la stanchezza: meglio una giornata più leggera."
ATTRIBUZIONE = "Offerta da Bottega di prova (esempio dimostrativo)."


def _ha_frase_mantenuta(reason: str) -> bool:
    return FRASE_PIOGGIA in reason or _RE_AFFOLLAMENTO.search(reason) is not None


def _esperienza(
    id_: str, durata: int, *, al_chiuso: bool, place: str | None = None,
    partner: bool = False,
) -> ExperienceNode:
    return ExperienceNode(
        id=id_, titolo=f"Titolo {id_}", place_id=place or f"luogo-{id_}", temi=[],
        durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
        partner_id="bottega-1" if partner else None,
        partner_abbonamento_attivo=partner,
    )


def _cand(
    esperienza: ExperienceNode, connessioni: int = 0, attribuzione: str | None = None
) -> GraphCandidate:
    return GraphCandidate(
        experience=esperienza,
        place_nome=f"Piazza {esperienza.id}",
        connessioni=[f"Connessione {i} di {esperienza.id}." for i in range(connessioni)],
        attribuzione=attribuzione,
    )


def _itinerario(
    stops: list[tuple[str, int]],
    budget: int | None,
    *,
    reason: str = "Motivo originale.",
    escluse: list[TappaEsclusa] | None = None,
) -> Itinerary:
    """Tappe con arrivi progressivi dalle 10:00 e trasferimento di 10 minuti."""
    out: list[ItineraryStop] = []
    minuti = 10 * 60
    for i, (id_, durata) in enumerate(stops):
        if i > 0:
            minuti += 10
        out.append(
            ItineraryStop(
                experience_id=id_, arrivo=time(minuti // 60, minuti % 60),
                durata_min=durata, reason=reason,
            )
        )
        minuti += durata
    return Itinerary(
        person_id="p", stops=out, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=budget, tempo_effettivo_min=budget,
        tappe_escluse=escluse or [],
    )


def _pioggia(ora: time = time(10, 0)) -> Signal:
    return Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=ora)


# ---------------------------------------------------------------------------
# Budget nelle sostituzioni
# ---------------------------------------------------------------------------


def test_alternativa_che_sfora_il_budget_scartata_tappa_mantenuta_con_frase() -> None:
    # Itinerario: una tappa all'aperto di 30 min, budget 40. L'unica
    # alternativa al chiuso dura 60: sforerebbe.
    orig = _cand(_esperienza("orig", 30, al_chiuso=False))
    lunga = _cand(_esperienza("lunga", 60, al_chiuso=True), connessioni=2)
    it = _itinerario([("orig", 30)], budget=40)

    r = adapt_itinerary(it, _pioggia(), [orig, lunga], None, vocabolario=VOCABOLARIO)

    assert [s.experience_id for s in r.stops] == ["orig"]
    assert r.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert r.stops[0].reason == f"Motivo originale. {FRASE_PIOGGIA}"
    assert r.adattato_da_segnale is False
    assert r.tempo_disponibile_min == 40
    assert r.tempo_effettivo_min == 40


def test_senza_budget_comportamento_precedente_sostituisce_anche_se_lunga() -> None:
    """Itinerario senza budget (JSON precedenti al campo): nessun vincolo di
    budget sulle sostituzioni (docs/LIMITI.md)."""
    orig = _cand(_esperienza("orig", 30, al_chiuso=False))
    lunga = _cand(_esperienza("lunga", 60, al_chiuso=True), connessioni=2)
    it = _itinerario([("orig", 30)], budget=None)

    r = adapt_itinerary(it, _pioggia(), [orig, lunga], None, vocabolario=VOCABOLARIO)

    assert [s.experience_id for s in r.stops] == ["lunga"]
    assert r.stops[0].esito_adattamento is EsitoAdattamento.SOSTITUITA
    assert r.adattato_da_segnale is True
    assert r.tempo_disponibile_min is None
    assert r.tempo_effettivo_min is None


def test_budget_sceglie_la_migliore_tra_quelle_che_stanno_nel_budget() -> None:
    orig = _cand(_esperienza("orig", 30, al_chiuso=False))
    lunga = _cand(_esperienza("lunga", 60, al_chiuso=True), connessioni=4)  # score più alto
    breve = _cand(_esperienza("breve", 35, al_chiuso=True))
    it = _itinerario([("orig", 30)], budget=40)

    r = adapt_itinerary(it, _pioggia(), [orig, lunga, breve], None, vocabolario=VOCABOLARIO)

    assert [s.experience_id for s in r.stops] == ["breve"]
    # Controllo: senza budget vince quella con score più alto.
    r2 = adapt_itinerary(
        _itinerario([("orig", 30)], budget=None), _pioggia(), [orig, lunga, breve], None,
        vocabolario=VOCABOLARIO,
    )
    assert [s.experience_id for s in r2.stops] == ["lunga"]


def test_budget_conta_durate_e_trasferimenti_di_tutto_litinerario() -> None:
    # Due tappe: a (aperto, 30) + 10 + b (chiuso, 30) = 70; budget 75.
    # Sostituta di a da 35 -> 75 (entra); da 36 -> 76 (sfora).
    a = _cand(_esperienza("a", 30, al_chiuso=False))
    b = _cand(_esperienza("b", 30, al_chiuso=True))
    entra = _cand(_esperienza("alt", 35, al_chiuso=True))
    sfora = _cand(_esperienza("alt", 36, al_chiuso=True))
    it = _itinerario([("a", 30), ("b", 30)], budget=75)

    ok = adapt_itinerary(it, _pioggia(), [a, b, entra], None, vocabolario=VOCABOLARIO)
    no = adapt_itinerary(it, _pioggia(), [a, b, sfora], None, vocabolario=VOCABOLARIO)

    assert [s.experience_id for s in ok.stops] == ["alt", "b"]
    assert [s.experience_id for s in no.stops] == ["a", "b"]
    assert no.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA


def test_limite_e_il_minimo_tra_budget_e_mezzanotte() -> None:
    # Budget ampio (600) ma il segnale è delle 23:00: restano 60 minuti.
    orig = _cand(_esperienza("orig", 30, al_chiuso=False))
    alt = _cand(_esperienza("alt", 70, al_chiuso=True))
    it = _itinerario([("orig", 30)], budget=600)

    r = adapt_itinerary(it, _pioggia(time(23, 0)), [orig, alt], None, vocabolario=VOCABOLARIO)

    assert [s.experience_id for s in r.stops] == ["orig"]
    assert r.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert r.tappe_escluse == []  # 30 minuti stanno prima della mezzanotte


def test_vincolo_di_budget_identico_con_o_senza_partner() -> None:
    """Il budget legge solo il tempo: un'alternativa di partner attivo con la
    stessa durata ha lo stesso esito di una senza partner."""
    orig = _cand(_esperienza("orig", 30, al_chiuso=False))
    for durata, atteso in ((35, "alt"), (60, "orig")):
        esiti = set()
        for partner in (False, True):
            alt = _cand(_esperienza("alt", durata, al_chiuso=True, partner=partner))
            r = adapt_itinerary(
                _itinerario([("orig", 30)], budget=40), _pioggia(), [orig, alt], None,
                vocabolario=VOCABOLARIO,
            )
            esiti.add(r.stops[0].experience_id)
        assert esiti == {atteso}


# ---------------------------------------------------------------------------
# Esito e frase: coerenza, testo esatto, disclosure ultima
# ---------------------------------------------------------------------------


def test_frase_affollamento_testo_esatto_con_il_nome_del_luogo() -> None:
    orig = _cand(_esperienza("orig", 30, al_chiuso=True, place="luogo-x"))
    it = _itinerario([("orig", 30)], budget=100)
    folla = Signal(meteo="sereno", affollamento={"luogo-x": 0.75}, stanchezza=0.0, ora=time(10, 0))

    r = adapt_itinerary(it, folla, [orig], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert r.stops[0].reason == f"Motivo originale. {frase_affollamento('Piazza orig')}"


def test_pioggia_e_affollamento_insieme_vale_la_frase_della_pioggia() -> None:
    orig = _cand(_esperienza("orig", 30, al_chiuso=False, place="luogo-x"))
    it = _itinerario([("orig", 30)], budget=100)
    segnale = Signal(
        meteo="pioggia", affollamento={"luogo-x": 0.75}, stanchezza=0.0, ora=time(10, 0)
    )
    r = adapt_itinerary(it, segnale, [orig], None, vocabolario=VOCABOLARIO)
    assert r.stops[0].reason == f"Motivo originale. {FRASE_PIOGGIA}"
    assert "molta gente" not in r.stops[0].reason


def test_disclosure_resta_lultima_frase_della_tappa_mantenuta() -> None:
    orig = _cand(_esperienza("orig", 30, al_chiuso=False), attribuzione=ATTRIBUZIONE)
    it = _itinerario([("orig", 30)], budget=100, reason=f"Motivo originale. {ATTRIBUZIONE}")

    r = adapt_itinerary(it, _pioggia(), [orig], None, vocabolario=VOCABOLARIO)

    assert r.stops[0].reason == f"Motivo originale. {FRASE_PIOGGIA} {ATTRIBUZIONE}"
    assert r.stops[0].reason.count(ATTRIBUZIONE) == 1


def _adatta_seed(signal: Signal, tempo: int) -> tuple[Itinerary, list[GraphCandidate]]:
    profilo = EmotionalProfile(
        curiosita=0.6, contemplazione=0.6, arte=0.6, con_bambini=True,
        tempo_disponibile_min=tempo,
    )
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    ctx = VisitorContext(person_id="p", profile=profilo, signal=sereno)
    cands = SeedCandidateSource().candidates(ctx)
    base = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)
    return (
        adapt_itinerary(
            base, signal, cands, None, compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
        ),
        cands,
    )


def test_coerenza_campo_frase_e_disclosure_ultima_sul_seed() -> None:
    """Su più segnali e budget: esito == MANTENUTA se e solo se la frase è
    nel reason; se il candidato ha un'attribuzione, il reason finisce con
    essa. Almeno una mantenuta e una sostituita compaiono (non vacuo)."""
    luoghi = {"mura-urbane": 0.75, "san-michele-in-foro": 0.75, "orto-botanico": 0.75}
    segnali = [
        Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
        Signal(meteo="sereno", affollamento=luoghi, stanchezza=0.0, ora=time(10, 0)),
        Signal(meteo="pioggia", affollamento=luoghi, stanchezza=0.0, ora=time(10, 0)),
    ]
    visti: set[EsitoAdattamento] = set()
    for segnale in segnali:
        for tempo in (90, 200, 400):
            r, cands = _adatta_seed(segnale, tempo)
            per_id = {c.experience.id: c for c in cands}
            for s in r.stops:
                assert s.esito_adattamento is not None
                visti.add(s.esito_adattamento)
                mantenuta = s.esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
                assert mantenuta == _ha_frase_mantenuta(s.reason), (s.experience_id, s.reason)
                attribuzione = per_id[s.experience_id].attribuzione
                if attribuzione:
                    assert s.reason.endswith(attribuzione.strip()), s.reason
    assert EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA in visti
    assert EsitoAdattamento.SOSTITUITA in visti


# ---------------------------------------------------------------------------
# adattato_da_segnale e arrivi
# ---------------------------------------------------------------------------


def test_sole_mantenute_adattato_false_e_arrivi_invariati() -> None:
    a = _cand(_esperienza("a", 30, al_chiuso=False))
    b = _cand(_esperienza("b", 30, al_chiuso=True))
    it = _itinerario([("a", 30), ("b", 30)], budget=200)
    # Segnale delle 15:00: se gli arrivi fossero ricalcolati partirebbero da lì.
    r = adapt_itinerary(it, _pioggia(time(15, 0)), [a, b], None, vocabolario=VOCABOLARIO)

    assert r.adattato_da_segnale is False
    assert [s.arrivo for s in r.stops] == [s.arrivo for s in it.stops]
    assert [s.esito_adattamento for s in r.stops] == [
        EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
        EsitoAdattamento.NON_TOCCATA,
    ]
    assert r.stops[1].reason == it.stops[1].reason


def test_sostituita_accende_adattato_e_ricalcola_gli_arrivi() -> None:
    a = _cand(_esperienza("a", 30, al_chiuso=False))
    alt = _cand(_esperienza("alt", 30, al_chiuso=True))
    it = _itinerario([("a", 30)], budget=200)
    r = adapt_itinerary(it, _pioggia(time(15, 0)), [a, alt], None, vocabolario=VOCABOLARIO)
    assert r.adattato_da_segnale is True
    assert r.stops[0].esito_adattamento is EsitoAdattamento.SOSTITUITA
    assert r.stops[0].arrivo == time(15, 0)


def test_tagliata_per_stanchezza_accende_adattato_e_va_in_tappe_escluse() -> None:
    cands = [_cand(_esperienza(f"t{i}", 60, al_chiuso=True)) for i in range(3)]
    it = _itinerario([(f"t{i}", 60) for i in range(3)], budget=300)
    stanco = Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0))

    r = adapt_itinerary(it, stanco, cands, None, vocabolario=VOCABOLARIO)

    assert r.adattato_da_segnale is True
    assert [s.experience_id for s in r.stops] == ["t0", "t1"]  # 2/3 di 180 = 120
    assert r.tappe_escluse == [
        TappaEsclusa(
            experience_id="t2", titolo="Titolo t2", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA,
            reason=FRASE_STANCHEZZA,
        )
    ]
    assert all(s.esito_adattamento is EsitoAdattamento.NON_TOCCATA for s in r.stops)


def test_tappe_fuori_dai_candidati_hanno_esito_non_toccata() -> None:
    a = _cand(_esperienza("a", 30, al_chiuso=False))
    it = _itinerario([("a", 30), ("fluttuante-v1", 15)], budget=200)
    r = adapt_itinerary(it, _pioggia(), [a], None, vocabolario=VOCABOLARIO)
    assert r.stops[1].experience_id == "fluttuante-v1"
    assert r.stops[1].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert r.stops[1].reason == it.stops[1].reason


# ---------------------------------------------------------------------------
# Adattamenti consecutivi
# ---------------------------------------------------------------------------


def test_frase_non_duplicata_e_tolta_quando_il_segnale_passa() -> None:
    a = _cand(_esperienza("a", 30, al_chiuso=False), attribuzione=ATTRIBUZIONE)
    it = _itinerario([("a", 30)], budget=200, reason=f"Motivo originale. {ATTRIBUZIONE}")

    uno = adapt_itinerary(it, _pioggia(), [a], None, vocabolario=VOCABOLARIO)
    due = adapt_itinerary(uno, _pioggia(), [a], None, vocabolario=VOCABOLARIO)
    assert due.stops[0].reason == uno.stops[0].reason
    assert due.stops[0].reason.count(FRASE_PIOGGIA) == 1
    assert due.stops[0].reason.endswith(ATTRIBUZIONE)

    # Da pioggia ad affollamento: la frase cambia, non si somma.
    folla = Signal(
        meteo="sereno", affollamento={"luogo-a": 0.75}, stanchezza=0.0, ora=time(10, 0)
    )
    tre = adapt_itinerary(due, folla, [a], None, vocabolario=VOCABOLARIO)
    assert tre.stops[0].reason == (
        f"Motivo originale. {frase_affollamento('Piazza a')} {ATTRIBUZIONE}"
    )

    # Segnale passato: tappa non toccata, nessuna frase di esito.
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    quattro = adapt_itinerary(tre, sereno, [a], None, vocabolario=VOCABOLARIO)
    assert quattro.stops[0].esito_adattamento is EsitoAdattamento.NON_TOCCATA
    assert quattro.stops[0].reason == f"Motivo originale. {ATTRIBUZIONE}"


def test_tappe_escluse_si_accumulano_senza_duplicati_vince_la_piu_recente() -> None:
    cands = [_cand(_esperienza(f"t{i}", 60, al_chiuso=True)) for i in range(4)]
    precedente = TappaEsclusa(
        experience_id="t3", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA, reason=FRASE_STANCHEZZA
    )
    vecchia = TappaEsclusa(
        experience_id="z-vecchia", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA,
        reason=FRASE_STANCHEZZA,
    )
    # t3 era già esclusa per stanchezza e ricompare tra le tappe ricevute
    # (es. il visitatore l'ha rimessa): stasera esce di nuovo, per il tetto.
    it = _itinerario(
        [(f"t{i}", 60) for i in range(4)], budget=300, escluse=[vecchia, precedente]
    )
    tardi = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(21, 0))

    r = adapt_itinerary(it, tardi, cands, None, vocabolario=VOCABOLARIO)

    # 180 minuti: t0 (60) + t1 (70) = 130; t2 (70) -> 200 > 180.
    assert [s.experience_id for s in r.stops] == ["t0", "t1"]
    ids = [t.experience_id for t in r.tappe_escluse]
    assert ids.count("t3") == 1
    assert sorted(ids) == ["t2", "t3", "z-vecchia"]
    per_id = {t.experience_id: t for t in r.tappe_escluse}
    assert per_id["t3"].esito is EsitoAdattamento.TAGLIATA_TETTO_GIORNATA
    assert per_id["z-vecchia"].esito is EsitoAdattamento.TAGLIATA_STANCHEZZA  # conservata

    # Secondo adattamento: le escluse restano, nessun duplicato.
    r2 = adapt_itinerary(r, tardi, cands, None, vocabolario=VOCABOLARIO)
    assert sorted(t.experience_id for t in r2.tappe_escluse) == ["t2", "t3", "z-vecchia"]


def test_stanchezza_poi_tetto_due_adattamenti_consecutivi() -> None:
    cands = [_cand(_esperienza(f"t{i}", 60, al_chiuso=True)) for i in range(4)]
    it = _itinerario([(f"t{i}", 60) for i in range(4)], budget=300)
    stanco = Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0))
    uno = adapt_itinerary(it, stanco, cands, None, vocabolario=VOCABOLARIO)
    # 2/3 di 240 = 160: t0, t1 (120), t2 porterebbe a 180.
    assert [s.experience_id for s in uno.stops] == ["t0", "t1"]
    assert [(t.experience_id, t.esito) for t in uno.tappe_escluse] == [
        ("t2", EsitoAdattamento.TAGLIATA_STANCHEZZA),
        ("t3", EsitoAdattamento.TAGLIATA_STANCHEZZA),
    ]
    tardi = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(23, 0))
    due = adapt_itinerary(uno, tardi, cands, None, vocabolario=VOCABOLARIO)
    assert [s.experience_id for s in due.stops] == ["t0"]
    assert [(t.experience_id, t.esito) for t in due.tappe_escluse] == [
        ("t2", EsitoAdattamento.TAGLIATA_STANCHEZZA),
        ("t3", EsitoAdattamento.TAGLIATA_STANCHEZZA),
        ("t1", EsitoAdattamento.TAGLIATA_TETTO_GIORNATA),
    ]
    assert due.adattato_da_segnale is True
