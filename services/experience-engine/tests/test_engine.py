"""Test dell'AI Experience Engine — a regole, deterministico, offline.

Copre i criteri d'accettazione della Wave 1:
  a) due profili diversi => itinerari con tappe DIVERSE;
  b) adapt su pioggia sostituisce le tappe all'aperto con al chiuso;
  c) adapt su affollamento alto sostituisce la tappa in quel luogo;
  d) ogni tappa ha un `reason` non vuoto in italiano;
  e) `accessibilita_richiesta` esclude ogni esperienza inaccessibile.

I candidati arrivano dal grafo reale (`graph.source.SeedCandidateSource`, 22
esperienze di Lucca) e i `reason` dalla RAG (`rag.reasons`): il motore li
riceve iniettati, non li importa.
"""

from __future__ import annotations

import inspect
from datetime import time

import pytest
from contracts import EmotionalProfile, GraphCandidate, Signal, VisitorContext
from experience_engine import adapt_itinerary, compose_itinerary, rules
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason


@pytest.fixture
def source() -> SeedCandidateSource:
    return SeedCandidateSource()


def _sereno() -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.2, ora=time(10, 0))


def _ctx(profile: EmotionalProfile, signal: Signal | None = None) -> VisitorContext:
    return VisitorContext(person_id="p", profile=profile, signal=signal or _sereno())


def _candidati(source: SeedCandidateSource, ctx: VisitorContext) -> list[GraphCandidate]:
    return source.candidates(ctx)


# --- a) due profili diversi => itinerari diversi ---------------------------


def test_due_profili_diversi_danno_itinerari_diversi(source: SeedCandidateSource) -> None:
    contemplativo = EmotionalProfile(
        curiosita=0.2, contemplazione=0.9, arte=0.3, con_bambini=True,
        tempo_disponibile_min=200,
    )
    amante_arte = EmotionalProfile(
        curiosita=0.9, contemplazione=0.2, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    ctx1 = _ctx(contemplativo)
    ctx2 = _ctx(amante_arte)
    it1 = compose_itinerary(ctx1, _candidati(source, ctx1), compose_reason)
    it2 = compose_itinerary(ctx2, _candidati(source, ctx2), compose_reason)

    ids1 = [s.experience_id for s in it1.stops]
    ids2 = [s.experience_id for s in it2.stops]
    assert ids1 and ids2
    assert ids1 != ids2


def test_determinismo_stesso_input_stesso_output(source: SeedCandidateSource) -> None:
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    a = compose_itinerary(ctx, cands, compose_reason)
    b = compose_itinerary(ctx, cands, compose_reason)
    assert [s.experience_id for s in a.stops] == [s.experience_id for s in b.stops]
    assert [s.arrivo for s in a.stops] == [s.arrivo for s in b.stops]


# --- b) adapt su pioggia ---------------------------------------------------


def test_adapt_pioggia_sostituisce_le_tappe_allaperto(source: SeedCandidateSource) -> None:
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.7, arte=0.5, con_bambini=False,
        tempo_disponibile_min=200,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    al_chiuso = {c.experience.id: c.experience.al_chiuso for c in cands}
    assert any(not al_chiuso[s.experience_id] for s in base.stops)  # c'erano tappe aperte

    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.2, ora=time(10, 0))
    adattato = adapt_itinerary(base, pioggia, cands, profile, compose_reason, adapt_reason)

    assert adattato.adattato_da_segnale is True
    assert all(al_chiuso[s.experience_id] for s in adattato.stops)


# --- c) adapt su affollamento ----------------------------------------------


def test_adapt_affollamento_sostituisce_la_tappa_in_quel_luogo(
    source: SeedCandidateSource,
) -> None:
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.6, arte=0.5, con_bambini=False,
        tempo_disponibile_min=200,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    per_id = {c.experience.id: c for c in cands}
    place0 = per_id[base.stops[0].experience_id].experience.place_id

    crowd = Signal(meteo="sereno", affollamento={place0: 0.9}, stanchezza=0.2, ora=time(10, 0))
    adattato = adapt_itinerary(base, crowd, cands, profile, compose_reason, adapt_reason)

    assert adattato.adattato_da_segnale is True
    assert adattato.stops[0].experience_id != base.stops[0].experience_id
    # La nuova prima tappa è in un luogo scorrevole (sotto la soglia di adapt).
    nuovo_place = per_id[adattato.stops[0].experience_id].experience.place_id
    assert crowd.affollamento.get(nuovo_place, 0.0) <= rules.SOGLIA_AFFOLLAMENTO_ADATTAMENTO
    assert adattato.stops[0].reason.startswith("Sostituita per")


def test_adapt_senza_segnale_rilevante_restituisce_invariato(
    source: SeedCandidateSource,
) -> None:
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    # Stesso meteo sereno, niente affollamento, poca stanchezza: nulla da riscrivere.
    invariato = adapt_itinerary(base, _sereno(), cands, profile, compose_reason, adapt_reason)
    assert invariato is base
    assert invariato.adattato_da_segnale is False


def test_adapt_stanchezza_accorcia_litinerario(source: SeedCandidateSource) -> None:
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.6, con_bambini=False,
        tempo_disponibile_min=300,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    stanco = Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0))
    adattato = adapt_itinerary(base, stanco, cands, profile, compose_reason, adapt_reason)
    if len(base.stops) > 1:
        assert len(adattato.stops) < len(base.stops)
        assert adattato.adattato_da_segnale is True


# --- d) ogni tappa ha un reason non vuoto ----------------------------------


def test_ogni_tappa_ha_reason_non_vuoto(source: SeedCandidateSource) -> None:
    profile = EmotionalProfile(
        curiosita=0.8, contemplazione=0.4, arte=0.8, con_bambini=True,
        tempo_disponibile_min=240,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    it = compose_itinerary(ctx, cands, compose_reason)
    assert it.stops
    for s in it.stops:
        assert s.reason and s.reason.strip()


def test_reason_fallback_interno_senza_rag(source: SeedCandidateSource) -> None:
    # Senza iniettare la RAG, il fallback interno garantisce la spiegabilità.
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=120,
    )
    ctx = _ctx(profile)
    it = compose_itinerary(ctx, _candidati(source, ctx))
    assert it.stops
    for s in it.stops:
        assert s.reason and s.reason.strip().endswith(".")


# --- e) accessibilità ------------------------------------------------------


def test_accessibilita_richiesta_esclude_le_non_accessibili(
    source: SeedCandidateSource,
) -> None:
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.8, con_bambini=False,
        tempo_disponibile_min=300, accessibilita_richiesta=True,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    it = compose_itinerary(ctx, cands, compose_reason)
    acc = {c.experience.id: c.experience.accessibile for c in cands}
    assert it.stops
    assert all(acc[s.experience_id] for s in it.stops)


def test_adapt_non_degrada_accessibilita_con_profilo_assente(
    source: SeedCandidateSource,
) -> None:
    # profile=None: una tappa accessibile va sostituita solo con una accessibile.
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.8, con_bambini=False,
        tempo_disponibile_min=300, accessibilita_richiesta=True,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    per_id = {c.experience.id: c for c in cands}
    # Affolla tutti i luoghi delle tappe attuali per forzare sostituzioni.
    affollamento = {per_id[s.experience_id].experience.place_id: 0.95 for s in base.stops}
    crowd = Signal(meteo="sereno", affollamento=affollamento, stanchezza=0.1, ora=time(10, 0))
    adattato = adapt_itinerary(base, crowd, cands, None, compose_reason, adapt_reason)
    acc = {c.experience.id: c.experience.accessibile for c in cands}
    assert all(acc[s.experience_id] for s in adattato.stops)


# --- vincolo etico: visibilità non acquistabile ----------------------------


def test_scoring_non_usa_partner_id_ne_prezzo() -> None:
    """Test-guard: lo scoring non deve MAI riferirsi a `partner_id` o
    `prezzo_eur`. La visibilità non è acquistabile: nessun prezzo cambia lo
    score. Si ispeziona il CODICE della funzione (docstring esclusa)."""
    import ast
    import textwrap

    albero = ast.parse(textwrap.dedent(inspect.getsource(rules.calcola_score)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    # Rimuove la docstring: il vincolo riguarda il codice eseguito, non i commenti.
    if (
        funzione.body
        and isinstance(funzione.body[0], ast.Expr)
        and isinstance(funzione.body[0].value, ast.Constant)
    ):
        funzione.body = funzione.body[1:]
    codice = ast.unparse(funzione)
    assert "partner_id" not in codice
    assert "prezzo" not in codice


def test_scoring_penalizza_affollamento() -> None:
    """La penalità di distribuzione deve ridurre lo score di un luogo affollato."""
    from contracts import ExperienceNode

    exp = ExperienceNode(
        id="x", titolo="T", place_id="luogo", temi=["arte"], durata_min=30,
        al_chiuso=True, accessibile=True,
    )
    cand = GraphCandidate(experience=exp, place_nome="Luogo", connessioni=[])
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    vuoto = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    pieno = Signal(meteo="sereno", affollamento={"luogo": 0.7}, stanchezza=0.0, ora=time(10, 0))
    assert rules.calcola_score(cand, profile, pieno) < rules.calcola_score(cand, profile, vuoto)
