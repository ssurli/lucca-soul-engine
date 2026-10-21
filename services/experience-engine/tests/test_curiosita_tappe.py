"""Curiosita' dei luoghi sulle tappe (ondata 2a, compito 5).

- composizione: ogni tappa da candidato porta `candidate.curiosita`;
- adattamento: per un candidato NOTO vince il catalogo (una tappa ricevuta senza
  curiosita' le riceve; il client non puo' iniettarne di sue); uno stub
  (candidato sconosciuto) conserva quelle ricevute;
- tappe fluttuanti ed eventi promossi: lista vuota;
- il `reason` non contiene le curiosita' (l'app le mostra sotto il motivo);
- le curiosita' non cambiano ne' lo score ne' le tappe scelte (prova
  comportamentale, accanto alla guardia AST `test_scoring_non_legge_curiosita.py`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from contracts import (
    Curiosita,
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    TipoCuriosita,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary, rules
from graph.seed_lucca import LUOGHI, VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason
from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn

SABATO = date(2026, 12, 12)

FATTO = Curiosita(
    testo="Il campanile fu rialzato nel Trecento.", tipo=TipoCuriosita.FATTO,
    fonte="archivio di prova",
)
LEGGENDA = Curiosita(
    testo="Si racconta che il diavolo abbia lasciato un'impronta sul sagrato.",
    tipo=TipoCuriosita.LEGGENDA, fonte="tradizione orale di prova",
)
INIETTATA = Curiosita(
    testo="Testo inventato dal client.", tipo=TipoCuriosita.FATTO, fonte="client",
)

PROFILI = {
    "curioso": EmotionalProfile(
        curiosita=0.9, contemplazione=0.2, arte=0.4, con_bambini=False,
        tempo_disponibile_min=300,
    ),
    "contemplativo": EmotionalProfile(
        curiosita=0.2, contemplazione=0.9, arte=0.5, con_bambini=False,
        tempo_disponibile_min=240,
    ),
    "con-bambini": EmotionalProfile(
        curiosita=0.6, contemplazione=0.3, arte=0.3, con_bambini=True,
        tempo_disponibile_min=240,
    ),
    "accessibile": EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=300, accessibilita_richiesta=True,
    ),
}


def _sereno(ora: time = time(10, 0)) -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora, data=SABATO)


def _pioggia() -> Signal:
    return Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=SABATO)


def _profilo() -> EmotionalProfile:
    return PROFILI["curioso"]


def _esperienza(
    id_: str, *, al_chiuso: bool = True, temi: list[str] | None = None, durata: int = 60
) -> ExperienceNode:
    return ExperienceNode(
        id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=temi or [],
        durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
    )


def _cand(
    esperienza: ExperienceNode, curiosita: list[Curiosita] | None = None
) -> GraphCandidate:
    return GraphCandidate(
        experience=esperienza, place_nome=f"Piazza {esperienza.id}",
        connessioni=['Evoca il tema "Arte".'], curiosita=curiosita or [],
    )


def _stop(
    id_: str, arrivo: time, curiosita: list[Curiosita] | None = None
) -> ItineraryStop:
    return ItineraryStop(
        experience_id=id_, titolo=f"Titolo {id_}", arrivo=arrivo, durata_min=60,
        reason="Motivo originale.", curiosita=curiosita or [],
    )


def _itinerario(stops: list[ItineraryStop]) -> Itinerary:
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=300, tempo_effettivo_min=300,
    )


def _componi(
    cands: list[GraphCandidate], profilo: EmotionalProfile | None = None
) -> Itinerary:
    ctx = VisitorContext(person_id="p", profile=profilo or _profilo(), signal=_sereno())
    return compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)


# ---------------------------------------------------------------------------
# Composizione (candidati sintetici)
# ---------------------------------------------------------------------------


def test_composizione_ogni_tappa_porta_le_curiosita_del_candidato() -> None:
    cands = [
        _cand(_esperienza("a", temi=["arte"]), [FATTO, LEGGENDA]),
        _cand(_esperienza("b", temi=["arte"]), [LEGGENDA]),
        _cand(_esperienza("c", temi=["arte"])),
    ]
    it = _componi(cands)
    per_id = {c.experience.id: c.curiosita for c in cands}
    assert {s.experience_id for s in it.stops} == {"a", "b", "c"}
    for s in it.stops:
        assert s.curiosita == per_id[s.experience_id], s.experience_id


def test_il_reason_non_contiene_le_curiosita() -> None:
    """L'app mostra le curiosita' SOTTO il motivo: il `reason` non le ripete
    (ne' in composizione ne' in adattamento)."""
    cands = [
        _cand(_esperienza("a", temi=["arte"], al_chiuso=False), [FATTO, LEGGENDA]),
        _cand(_esperienza("b", temi=["arte"]), [FATTO]),
    ]
    it = _componi(cands)
    adattato = adapt_itinerary(
        it, _pioggia(), cands, _profilo(), compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )
    for itinerario in (it, adattato):
        for s in itinerario.stops:
            for c in (FATTO, LEGGENDA):
                assert c.testo not in s.reason, (s.experience_id, s.reason)
                assert c.fonte not in s.reason, (s.experience_id, s.reason)
            assert "Si racconta" not in s.reason


def test_le_curiosita_non_cambiano_score_ne_scelta() -> None:
    """Prova comportamentale: candidati identici salvo le curiosita' danno lo
    stesso score (motore e recommender) e lo stesso itinerario (curiosita' a
    parte)."""
    esperienze = [_esperienza(f"x{i}", temi=["arte"], durata=40 + 5 * i) for i in range(6)]
    senza = [_cand(e) for e in esperienze]
    # Curiosita' solo su alcuni, in quantita' diverse: se contassero,
    # l'ordine cambierebbe.
    con = [_cand(e, [FATTO, LEGGENDA] * (i % 3)) for i, e in enumerate(esperienze)]
    profilo, segnale = _profilo(), _sereno()
    repo = InMemoryBehaviorEventRepository()
    fn_senza = costruisci_score_fn(repo, senza, vocabolario=VOCABOLARIO)
    fn_con = costruisci_score_fn(repo, con, vocabolario=VOCABOLARIO)
    for a, b in zip(senza, con, strict=True):
        assert rules.calcola_score(a, profilo, segnale, vocabolario=VOCABOLARIO) == (
            rules.calcola_score(b, profilo, segnale, vocabolario=VOCABOLARIO)
        )
        assert fn_senza(a, profilo, segnale) == fn_con(b, profilo, segnale)

    def _senza_curiosita(it: Itinerary) -> list[ItineraryStop]:
        return [s.model_copy(update={"curiosita": []}) for s in it.stops]

    assert _senza_curiosita(_componi(senza)) == _senza_curiosita(_componi(con))


def test_tappe_fluttuanti_ed_eventi_promossi_senza_curiosita() -> None:
    esperienza = ExperienceNode(
        id="exp-arte", titolo="Una visita d'arte", place_id="luogo-fisso",
        temi=["arte", "musica", "storia"], durata_min=30, al_chiuso=True, accessibile=True,
    )
    cand = GraphCandidate(
        experience=esperienza, place_nome="Piazza fissa", connessioni=[],
        curiosita=[FATTO],
    )
    fluttuante = SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza",
        temi=["musica"], place_id="luogo-fisso", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    evento = EventoPromosso(
        id="evento-luogo-fisso-musica", place_id="luogo-fisso", temi=["musica"],
        ultima_occorrenza=date(2026, 12, 5), cadenza_giorni=7.0,
    )
    profilo = EmotionalProfile(
        curiosita=0.9, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=300,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        data=SABATO, eventi_attivi=[fluttuante],
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=signal)
    it = compose_itinerary(
        ctx, [cand], compose_reason, eventi_promossi=[evento], vocabolario=VOCABOLARIO
    )
    per_id = {s.experience_id: s.curiosita for s in it.stops}
    # Stesso luogo dell'esperienza, ma fluttuante ed evento non la ereditano.
    assert per_id == {
        "exp-arte": [FATTO],
        "fluttuante-violinista-1": [],
        "evento-luogo-fisso-musica": [],
    }
    # In adattamento restano stub: curiosita' conservate (vuote).
    r = adapt_itinerary(it, _sereno(), [cand], profilo, vocabolario=VOCABOLARIO)
    assert {s.experience_id: s.curiosita for s in r.stops} == per_id


# ---------------------------------------------------------------------------
# Adattamento: candidato noto (vince il catalogo) e stub (conserva)
# ---------------------------------------------------------------------------


def test_adattamento_senza_cambiamenti_noto_vince_il_catalogo_stub_conserva() -> None:
    cands = [_cand(_esperienza("t0"), [FATTO]), _cand(_esperienza("t1"), [LEGGENDA])]
    it = _itinerario([
        _stop("t0", time(10, 0)),                    # vecchio client: nessuna curiosita'
        _stop("t1", time(11, 10), [INIETTATA]),      # client che ne inietta una sua
        _stop("ignota", time(12, 20), [INIETTATA]),  # stub: conservata
        _stop("ignota-vuota", time(13, 30)),
    ])
    r = adapt_itinerary(it, _sereno(), cands, None, vocabolario=VOCABOLARIO)
    assert r.adattato_da_segnale is False
    assert [(s.experience_id, s.curiosita) for s in r.stops] == [
        ("t0", [FATTO]),
        ("t1", [LEGGENDA]),
        ("ignota", [INIETTATA]),
        ("ignota-vuota", []),
    ]


def test_adattamento_con_ricostruzione_sostituta_porta_le_sue_curiosita() -> None:
    """Pioggia su t0 all'aperto: sostituita da `alt`, che porta le curiosita'
    del SUO luogo (non quelle di t0). Gli stop sono ricostruiti: il noto t1
    riceve quelle del catalogo, lo stub conserva le sue."""
    cands = [
        _cand(_esperienza("t0", al_chiuso=False), [FATTO]),
        _cand(_esperienza("alt"), [LEGGENDA]),
        _cand(_esperienza("t1"), [FATTO, LEGGENDA]),
    ]
    it = _itinerario([
        _stop("t0", time(10, 0), [FATTO]),
        _stop("t1", time(11, 10), [INIETTATA]),
        _stop("ignota", time(12, 20), [INIETTATA]),
    ])
    r = adapt_itinerary(it, _pioggia(), cands, None, vocabolario=VOCABOLARIO)
    assert r.adattato_da_segnale is True
    assert [(s.experience_id, s.curiosita) for s in r.stops] == [
        ("alt", [LEGGENDA]),
        ("t1", [FATTO, LEGGENDA]),
        ("ignota", [INIETTATA]),
    ]


# ---------------------------------------------------------------------------
# Sul seed della citta'
# ---------------------------------------------------------------------------


def _curiosita_seed() -> dict[str, list[Curiosita]]:
    return {luogo.id: list(luogo.curiosita) for luogo in LUOGHI}


@pytest.mark.parametrize("nome", sorted(PROFILI))
def test_sul_seed_le_tappe_portano_le_curiosita_del_loro_luogo(nome: str) -> None:
    ctx = VisitorContext(person_id="p", profile=PROFILI[nome], signal=_sereno())
    cands = list(SeedCandidateSource().candidates(ctx))
    it = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)
    luogo_di = {c.experience.id: c.experience.place_id for c in cands}
    seed = _curiosita_seed()
    assert it.stops
    for s in it.stops:
        assert s.curiosita == seed[luogo_di[s.experience_id]], s.experience_id
        for c in s.curiosita:
            assert c.testo not in s.reason


def test_il_seed_esercita_tappe_con_curiosita() -> None:
    """Le asserzioni sul seed non sono vuote: almeno una tappa ha curiosita'."""
    con_curiosita = 0
    for profilo in PROFILI.values():
        ctx = VisitorContext(person_id="p", profile=profilo, signal=_sereno())
        cands = list(SeedCandidateSource().candidates(ctx))
        it = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)
        con_curiosita += sum(1 for s in it.stops if s.curiosita)
    assert con_curiosita > 0
