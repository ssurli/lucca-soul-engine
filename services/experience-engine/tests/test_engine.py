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
import re
from datetime import UTC, datetime, time

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    FasciaApertura,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
)
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


#: Nomi commerciali/di booking che lo scoring NON deve MAI toccare. La lista è
#: esplicita apposta: ogni nuovo campo commerciale (partner, prezzo,
#: abbonamento, prenotazione, commissione) va aggiunto QUI, così il guard
#: cresce insieme ai contratti e "visibilità non acquistabile" resta strutturale.
NOMI_COMMERCIALI_VIETATI_NELLO_SCORING = (
    "partner_id",
    "partner_abbonamento_attivo",
    "abbonamento",
    "prezzo",
    "prenotabile",
    "prenotazione",
    "booking",
    "commission",
    "commissione",
)


def test_scoring_non_usa_partner_id_ne_prezzo() -> None:
    """Test-guard: lo scoring non deve MAI riferirsi a campi commerciali o di
    booking (partner, prezzo, abbonamento, prenotazione, commissione). La
    visibilità non è acquistabile: nessun canale commerciale cambia lo score.
    Si ispeziona il CODICE della funzione (docstring esclusa)."""
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
    codice = ast.unparse(funzione).lower()
    for vietato in NOMI_COMMERCIALI_VIETATI_NELLO_SCORING:
        assert vietato not in codice, f"lo scoring non deve riferirsi a '{vietato}'"


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


def _candidato(
    *,
    partner_id: str | None = None,
    prezzo_eur: float | None = None,
    attribuzione: str | None = None,
    partner_abbonamento_attivo: bool = True,
    prenotabile: bool = False,
    orari_apertura: list | None = None,
) -> GraphCandidate:
    """Costruisce a mano un candidato identico salvo i campi commerciali.

    Costruito a mano di proposito: il test comportamentale sull'invarianza NON
    deve dipendere da come il grafo popola (o meno) `attribuzione`."""
    from contracts import ExperienceNode

    exp = ExperienceNode(
        id="exp-x", titolo="Esperienza X", place_id="luogo", temi=["arte", "liuteria"],
        durata_min=40, al_chiuso=True, accessibile=True,
        partner_id=partner_id, prezzo_eur=prezzo_eur,
        partner_abbonamento_attivo=partner_abbonamento_attivo, prenotabile=prenotabile,
        orari_apertura=orari_apertura or [],
    )
    return GraphCandidate(
        experience=exp, place_nome="Luogo", connessioni=['Evoca il tema "Arte".'],
        attribuzione=attribuzione,
    )


def test_scoring_invariante_a_partner_prezzo_attribuzione() -> None:
    """VISIBILITÀ NON ACQUISTABILE (test comportamentale): due candidati
    identici in tutto tranne partner_id / prezzo_eur / attribuzione devono
    ottenere lo STESSO score. Nessun canale commerciale influenza la scelta."""
    profile = EmotionalProfile(
        curiosita=0.9, contemplazione=0.4, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    neutro = _candidato()
    commerciale = _candidato(
        partner_id="bottega-1", prezzo_eur=25.0,
        attribuzione="Offerta da Bottega Rossi, bottega di liuteria.",
    )
    assert rules.calcola_score(neutro, profile, signal) == rules.calcola_score(
        commerciale, profile, signal
    )


def test_scoring_bit_identico_con_abbonamento_e_prenotabilita_variati() -> None:
    """VISIBILITÀ NON ACQUISTABILE (Wave 3a): lo score deve restare
    BIT-IDENTICO al variare di `partner_abbonamento_attivo` e `prenotabile`.

    L'abbonamento decide solo la PRESENZA del candidato (filtro duro), mai il
    punteggio: aggiungere/togliere un partner, un prezzo o la prenotabilità non
    deve cambiare lo score nemmeno di un bit. Si testa `calcola_score`
    DIRETTAMENTE (non `passa_filtri_duri`) per isolare "score invariato" da
    "presenza filtrata": qui verifichiamo solo che lo score non si muova."""
    profile = EmotionalProfile(
        curiosita=0.9, contemplazione=0.4, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    # Candidato di riferimento: nessun partner, nessun prezzo.
    riferimento = _candidato()
    score_riferimento = rules.calcola_score(riferimento, profile, signal)

    # Ogni combinazione commerciale possibile deve dare lo STESSO identico score.
    varianti = [
        _candidato(partner_id="bottega-1", partner_abbonamento_attivo=True),
        _candidato(partner_id="bottega-1", partner_abbonamento_attivo=False),
        _candidato(partner_id="bottega-1", prezzo_eur=25.0, partner_abbonamento_attivo=True),
        _candidato(partner_id="bottega-1", prezzo_eur=999.0, partner_abbonamento_attivo=False),
        _candidato(partner_id="bottega-1", prezzo_eur=25.0, prenotabile=True),
        _candidato(prenotabile=True),
        _candidato(
            partner_id="bottega-1", prezzo_eur=25.0, prenotabile=True,
            attribuzione="Offerta da Bottega Rossi, bottega di liuteria.",
        ),
    ]
    for variante in varianti:
        # `==` su float è voluto: pretendiamo identità bit-a-bit, non prossimità.
        assert rules.calcola_score(variante, profile, signal) == score_riferimento


def test_partner_non_attivo_escluso_dai_filtri_duri() -> None:
    """Filtro duro (Wave 3a): un partner con abbonamento NON attivo è escluso;
    lo stesso candidato con abbonamento attivo passa. La presenza cambia solo
    per l'abbonamento — mai per il prezzo."""
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))

    attivo = _candidato(partner_id="bottega-1", partner_abbonamento_attivo=True)
    non_attivo = _candidato(partner_id="bottega-1", partner_abbonamento_attivo=False)
    # Esperienza senza partner: sempre visibile, anche col flag denormalizzato a False.
    senza_partner = _candidato(partner_id=None, partner_abbonamento_attivo=False)

    assert rules.passa_filtri_duri(attivo, profile, signal, []) is True
    assert rules.passa_filtri_duri(non_attivo, profile, signal, []) is False
    assert rules.passa_filtri_duri(senza_partner, profile, signal, []) is True


# --- orari di apertura (Wave 3a+, validazione minima) -----------------------


def test_esperienza_chiusa_in_quel_giorno_ora_esclusa_dai_filtri_duri() -> None:
    """Quinto filtro duro: un'esperienza con `orari_apertura` dichiarati che
    NON coprono il giorno/ora del segnale corrente è esclusa — stessa
    informazione di `marketplace.service.request_booking`, un solo modello
    (`contracts.rientra_in_orario`), due usi."""
    fascia_sabato_mattina = FasciaApertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(13, 0)
    )
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    candidato = _candidato(orari_apertura=[fascia_sabato_mattina])

    dentro = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), giorno_settimana=5
    )
    fuori_ora = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(15, 0), giorno_settimana=5
    )
    fuori_giorno = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), giorno_settimana=2
    )

    assert rules.passa_filtri_duri(candidato, profile, dentro, []) is True
    assert rules.passa_filtri_duri(candidato, profile, fuori_ora, []) is False
    assert rules.passa_filtri_duri(candidato, profile, fuori_giorno, []) is False


def test_esperienza_senza_orari_dichiarati_mai_esclusa_per_questo_motivo() -> None:
    """Comportamento INVARIATO: un'esperienza senza `orari_apertura`
    dichiarati (il default, ogni esperienza del seed oggi) non viene MAI
    esclusa per questo filtro, qualunque giorno/ora porti il segnale."""
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    candidato = _candidato()  # orari_apertura di default: []
    for ora, giorno in [(time(3, 0), 0), (time(23, 59), 6), (time(12, 0), None)]:
        signal = Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora, giorno_settimana=giorno
        )
        assert rules.passa_filtri_duri(candidato, profile, signal, []) is True


def test_segnale_senza_giorno_settimana_non_esclude_per_orario() -> None:
    """`Signal.giorno_settimana=None` (il default, es. per ogni chiamante che
    non lo popola ancora): il filtro non esclude MAI un'esperienza per
    questo motivo, anche se dichiara orari — non si inventa un giorno per
    applicare un vincolo che nessuno ha chiesto."""
    fascia = FasciaApertura(giorno_settimana=5, apertura=time(9, 0), chiusura=time(13, 0))
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    candidato = _candidato(orari_apertura=[fascia])
    signal_senza_giorno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(15, 0))

    assert rules.passa_filtri_duri(candidato, profile, signal_senza_giorno, []) is True


# --- FIX ethics-guardian (2026-07-24): adapt_itinerary poteva reintrodurre --
# --- un'esperienza CHIUSA come alternativa (bug reale, trovato dal gate) ---


def test_adapt_non_sostituisce_con_unalternativa_chiusa_in_quellorario() -> None:
    """Bug reale trovato da un giro DEDICATO di ethics-guardian, separato
    dall'implementazione (non un'autovalutazione): `_migliore_alternativa`
    (usata da `adapt_itinerary` per sostituire una tappa su pioggia/
    affollamento) aveva la sua logica di filtro scritta a mano e non
    chiamava affatto `rientra_in_orario` -- una sostituzione poteva quindi
    reintrodurre un'esperienza chiusa nel giorno/ora del segnale, anche se
    `passa_filtri_duri` la escludeva gia' correttamente in composizione
    iniziale. Riprodotto e corretto: ora `_migliore_alternativa` applica lo
    STESSO controllo, stessa funzione `contracts.rientra_in_orario`.

    Scenario: piove, la tappa originale (all'aperto) va sostituita; l'UNICA
    alternativa al chiuso disponibile e' aperta solo 20:00-23:00, mentre il
    segnale e' delle 10:00 di sabato -- quindi NESSUNA alternativa valida
    esiste, e la tappa originale deve restare invariata (mai una tappa
    chiusa sostituita al posto suo)."""
    fascia_solo_sera = FasciaApertura(
        giorno_settimana=5, apertura=time(20, 0), chiusura=time(23, 0)
    )
    esperienza_chiusa_ora = ExperienceNode(
        id="exp-chiusa-ora", titolo="Museo", place_id="luogo-b", temi=[],
        durata_min=30, al_chiuso=True, accessibile=True,
        orari_apertura=[fascia_solo_sera],
    )
    esperienza_originale = ExperienceNode(
        id="exp-originale", titolo="Passeggiata", place_id="luogo-a", temi=[],
        durata_min=30, al_chiuso=False, accessibile=True,
    )
    candidati = [
        GraphCandidate(experience=esperienza_originale, place_nome="A", connessioni=[]),
        GraphCandidate(
            experience=esperienza_chiusa_ora, place_nome="B",
            connessioni=["Unica alternativa al chiuso disponibile"],
        ),
    ]
    itinerario = Itinerary(
        person_id="p",
        stops=[ItineraryStop(experience_id="exp-originale", arrivo=time(10, 0), durata_min=30,
                              reason="motivo iniziale")],
        generated_at=datetime.now(),
    )
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=120,
    )
    # Sabato (giorno_settimana=5) alle 10:00: la tappa all'aperto va sostituita
    # (piove), ma l'unica candidata al chiuso apre solo alle 20:00.
    segnale_pioggia = Signal(
        meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0), giorno_settimana=5
    )

    risultato = adapt_itinerary(
        itinerario, segnale_pioggia, candidati, profile,
        reason_fn=compose_reason, adapt_reason_fn=adapt_reason,
    )

    assert risultato.stops[0].experience_id == "exp-originale", (
        "l'unica alternativa al chiuso e' chiusa in questo orario: l'itinerario "
        "non deve sostituire la tappa con un'esperienza chiusa"
    )
    assert risultato.adattato_da_segnale is False


def test_reason_contiene_attribuzione_ma_score_invariato() -> None:
    """Con `attribuzione` valorizzata il `reason` finale la contiene (disclosure
    trasparente in coda), ma lo score resta identico al caso senza attribuzione:
    la disclosure racconta, non promuove."""
    profile = EmotionalProfile(
        curiosita=0.8, contemplazione=0.4, arte=0.9, con_bambini=False,
        tempo_disponibile_min=120,
    )
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    attribuzione = "Offerta da Bottega Rossi, bottega di liuteria."

    con_attr = _candidato(attribuzione=attribuzione)
    senza_attr = _candidato()

    # Score invariato.
    assert rules.calcola_score(con_attr, profile, signal) == rules.calcola_score(
        senza_attr, profile, signal
    )

    # Il reason finale contiene la disclosure, in coda.
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    it = compose_itinerary(ctx, [con_attr], compose_reason)
    assert len(it.stops) == 1
    reason = it.stops[0].reason
    assert attribuzione in reason
    assert reason.strip().endswith(attribuzione)

    # Senza attribuzione, il reason non la inventa.
    it2 = compose_itinerary(ctx, [senza_attr], compose_reason)
    assert "Offerta da" not in it2.stops[0].reason


# --- score_fn iniettabile (Wave 3b): il recommender ORDINA, non seleziona ----


def test_compose_senza_score_fn_uguale_al_default_esplicito(
    source: SeedCandidateSource,
) -> None:
    """`compose_itinerary` senza `score_fn` deve produrre ESATTAMENTE lo stesso
    itinerario che si otterrebbe iniettando esplicitamente `rules.calcola_score`:
    il default non è un ramo diverso, è `calcola_score`. Zero regressioni per i
    chiamanti esistenti (BFF Wave 1/2/3a) che non passano `score_fn`."""
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    implicito = compose_itinerary(ctx, cands, compose_reason)
    esplicito = compose_itinerary(ctx, cands, compose_reason, score_fn=rules.calcola_score)
    assert [s.experience_id for s in implicito.stops] == [
        s.experience_id for s in esplicito.stops
    ]
    assert [s.arrivo for s in implicito.stops] == [s.arrivo for s in esplicito.stops]


def test_score_fn_iniettato_cambia_realmente_lordine(source: SeedCandidateSource) -> None:
    """Un `score_fn` che INVERTE la preferenza (`-calcola_score`) deve cambiare
    davvero l'ordine delle tappe rispetto al default: prova che l'iniezione è
    usata, non ignorata. Il recommender fornisce un ranking alternativo e il
    motore lo rispetta."""
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)

    def score_invertito(
        cand: GraphCandidate, prof: EmotionalProfile, sig: Signal
    ) -> float:
        return -rules.calcola_score(cand, prof, sig)

    default = compose_itinerary(ctx, cands, compose_reason)
    invertito = compose_itinerary(ctx, cands, compose_reason, score_fn=score_invertito)

    ids_default = [s.experience_id for s in default.stops]
    ids_invertito = [s.experience_id for s in invertito.stops]
    assert ids_default and ids_invertito
    # L'ordine deve cambiare: l'iniezione ha effetto reale, non è ignorata.
    assert ids_default != ids_invertito


def test_score_fn_forza_una_tappa_specifica_in_testa(source: SeedCandidateSource) -> None:
    """Un `score_fn` che dà punteggio massimo a UN candidato specifico lo porta
    in testa all'itinerario: il ranking del recommender determina l'ordine tra i
    candidati ammessi."""
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    default = compose_itinerary(ctx, cands, compose_reason)
    # Scegli un candidato ammesso che NON è già la prima tappa del default.
    ammessi = [
        c for c in cands
        if rules.passa_filtri_duri(c, profile, ctx.signal, ctx.luoghi_gia_visti)
    ]
    prima_default = default.stops[0].experience_id
    bersaglio = next(c for c in ammessi if c.experience.id != prima_default)

    def score_favorisce(
        cand: GraphCandidate, prof: EmotionalProfile, sig: Signal
    ) -> float:
        return 1.0 if cand.experience.id == bersaglio.experience.id else 0.0

    forzato = compose_itinerary(ctx, cands, compose_reason, score_fn=score_favorisce)
    assert forzato.stops[0].experience_id == bersaglio.experience.id


def test_score_fn_non_puo_salvare_candidato_escluso_dal_filtro_duro(
    source: SeedCandidateSource,
) -> None:
    """IL FILTRO DURO RESTA SOVRANO: un candidato escluso dai vincoli etici
    (qui: non accessibile con `accessibilita_richiesta=True`) NON compare tra le
    tappe nemmeno con uno `score_fn` che gli assegna punteggio massimo. Il
    recommender non vede i candidati esclusi e non può reintrodurli: ordina solo
    ciò che il filtro ha già ammesso."""
    from contracts import ExperienceNode

    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.8, con_bambini=False,
        tempo_disponibile_min=300, accessibilita_richiesta=True,
    )
    ctx = _ctx(profile)
    # Candidato deliberatamente inaccessibile: il filtro duro lo esclude.
    escluso = GraphCandidate(
        experience=ExperienceNode(
            id="exp-inaccessibile", titolo="Torre senza ascensore", place_id="torre",
            temi=["arte"], durata_min=30, al_chiuso=True, accessibile=False,
        ),
        place_nome="Torre",
        connessioni=['Evoca il tema "Arte".'],
    )
    cands = [escluso, *_candidati(source, ctx)]

    def score_massimo_allescluso(
        cand: GraphCandidate, prof: EmotionalProfile, sig: Signal
    ) -> float:
        return 1.0 if cand.experience.id == "exp-inaccessibile" else 0.0

    it = compose_itinerary(ctx, cands, compose_reason, score_fn=score_massimo_allescluso)
    assert it.stops
    ids = [s.experience_id for s in it.stops]
    assert "exp-inaccessibile" not in ids
    # E ogni tappa presente è comunque accessibile (filtro duro rispettato).
    acc = {c.experience.id: c.experience.accessibile for c in cands}
    assert all(acc[i] for i in ids)


def test_disclosure_non_duplicata_in_adapt() -> None:
    """La disclosure è idempotente: una tappa non toccata dall'adapt conserva
    il reason originale senza ripetere l'attribuzione."""
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.4, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    attribuzione = "Offerta da Bottega Rossi, bottega di liuteria."
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.2, ora=time(10, 0))
    cand = _candidato(attribuzione=attribuzione)
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    base = compose_itinerary(ctx, [cand], compose_reason)
    # Segnale che tocca un ALTRO luogo: questa tappa resta intatta.
    crowd = Signal(
        meteo="sereno", affollamento={"altro-luogo": 0.9}, stanchezza=0.2, ora=time(10, 0)
    )
    adattato = adapt_itinerary(base, crowd, [cand], profile, compose_reason, adapt_reason)
    reason = adattato.stops[0].reason if adattato.stops else base.stops[0].reason
    assert reason.count(attribuzione) == 1


# ---------------------------------------------------------------------------
# Segnali FLUTTUANTI (Signal.eventi_attivi) — livello "accade ora" (un
# violinista in piazza), diverso dal livello "programmato" (:Evento, fuori
# scope: docs/LIMITI.md). AGGIUNTA in coda, mai una sostituzione.
# ---------------------------------------------------------------------------


def _candidato_arte(durata_min: int = 30) -> GraphCandidate:
    """Un solo candidato reale, a tema "arte", su un luogo fisso — usato per
    controllare con precisione il budget di tempo residuo nei test sotto."""
    esperienza = ExperienceNode(
        id="exp-fisso", titolo="Facciata Barocca", place_id="luogo-fisso",
        temi=["arte"], durata_min=durata_min, al_chiuso=False, accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza, place_nome="Piazza Fissa", connessioni=['Evoca il tema "Arte".'],
    )


def _violinista(non_commerciale: bool = True) -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza",
        temi=["musica"], place_id="luogo-fisso", non_commerciale=non_commerciale,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_segnale_fluttuante_coerente_aggiunge_tappa_con_reason() -> None:
    """(a) segnale coerente col profilo -> tappa aggiunta, con reason non
    vuoto che racconta cosa e dove."""
    profile = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        eventi_attivi=[_violinista()],
    )
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    it = compose_itinerary(ctx, [_candidato_arte()], compose_reason)

    assert len(it.stops) == 2
    tappa = it.stops[-1]
    assert tappa.experience_id == "fluttuante-violinista-1"
    assert tappa.reason  # spiegabilità obbligatoria: mai vuoto
    assert "violinista" in tappa.reason
    assert "Piazza Fissa" in tappa.reason  # place_nome risolto dai candidati reali


def test_segnale_fluttuante_non_coerente_non_aggiunge_tappa() -> None:
    """(b) segnale NON coerente col profilo (nessuna dimensione del profilo
    engaged sui suoi temi) -> non aggiunta."""
    profile = EmotionalProfile(
        curiosita=0.0, contemplazione=0.0, arte=0.0, con_bambini=False,
        tempo_disponibile_min=200,
    )
    segnale = SegnaleFluttuante(
        id="storico-1", descrizione="una guida racconta la storia della torre",
        temi=["storia"], place_id="luogo-fisso", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), eventi_attivi=[segnale]
    )
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    it = compose_itinerary(ctx, [_candidato_arte()], compose_reason)

    assert len(it.stops) == 1
    assert all(not s.experience_id.startswith("fluttuante-") for s in it.stops)


def test_segnale_fluttuante_commerciale_mai_aggiunto_anche_se_coerente() -> None:
    """(c) segnale commerciale -> MAI aggiunto, anche se coerente col
    profilo (filtro duro, nessuna eccezione)."""
    profile = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        eventi_attivi=[_violinista(non_commerciale=False)],
    )
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    it = compose_itinerary(ctx, [_candidato_arte()], compose_reason)

    assert len(it.stops) == 1
    assert all(not s.experience_id.startswith("fluttuante-") for s in it.stops)


def test_segnale_fluttuante_non_altera_score_esperienze_permanenti() -> None:
    """(d) VISIBILITÀ NON ACQUISTABILE via segnalazione: `calcola_score` è
    bit-identico con e senza segnali fluttuanti attivi, e le tappe REALI
    scelte (nessuna coda fluttuante) sono bit-identiche a loro volta."""
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    cand = _candidato_arte()
    signal_senza = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    signal_con = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        eventi_attivi=[_violinista()],
    )

    # `==` su float è voluto: bit-identico, non prossimità.
    assert rules.calcola_score(cand, profile, signal_senza) == rules.calcola_score(
        cand, profile, signal_con
    )

    ctx_senza = VisitorContext(person_id="p", profile=profile, signal=signal_senza)
    ctx_con = VisitorContext(person_id="p", profile=profile, signal=signal_con)
    it_senza = compose_itinerary(ctx_senza, [cand], compose_reason)
    it_con = compose_itinerary(ctx_con, [cand], compose_reason)
    reali_con = [s for s in it_con.stops if not s.experience_id.startswith("fluttuante-")]

    assert [s.experience_id for s in it_senza.stops] == [s.experience_id for s in reali_con]
    assert [s.reason for s in it_senza.stops] == [s.reason for s in reali_con]
    assert [s.arrivo for s in it_senza.stops] == [s.arrivo for s in reali_con]


def test_segnale_fluttuante_non_forzato_senza_budget() -> None:
    """(e) niente budget residuo -> la tappa fluttuante NON si forza, anche
    se pertinente."""
    profile = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=30,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        eventi_attivi=[_violinista()],
    )
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    # L'unico candidato reale (30 min) consuma TUTTO il budget da solo.
    it = compose_itinerary(ctx, [_candidato_arte(durata_min=30)], compose_reason)

    assert len(it.stops) == 1
    assert not it.stops[0].experience_id.startswith("fluttuante-")


def test_eventi_attivi_vuoto_di_default_non_aggiunge_nulla() -> None:
    """Comportamento INVARIATO: `Signal.eventi_attivi=[]` (il default, ogni
    chiamante oggi) non aggiunge alcuna tappa fluttuante."""
    profile = EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    it = compose_itinerary(ctx, [_candidato_arte()], compose_reason)

    assert len(it.stops) == 1
    assert all(not s.experience_id.startswith("fluttuante-") for s in it.stops)


def test_tappa_fluttuante_sopravvive_invariata_a_un_adapt_successivo() -> None:
    """Una tappa fluttuante non è tra i `candidates` di un successivo
    `adapt_itinerary` (il suo `experience_id` non esiste in nessun
    `GraphCandidate`): il percorso di fallback già esistente per una tappa
    "sconosciuta" (`_stub_da_stop`) la conserva intatta — mai riscritta, mai
    rimossa da un adattamento successivo. Il segnale usato qui forza una
    VERA sostituzione della tappa reale (luogo affollato + un'alternativa
    scorrevole disponibile), cosicché `adapt_itinerary` ricostruisca
    davvero gli stop (`_ricostruisci_stops`) invece di limitarsi a
    ritornare l'itinerario originale invariato — la coda fluttuante deve
    sopravvivere anche a QUESTO percorso, non solo al caso banale in cui
    l'adapt non tocca nulla."""
    profile = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        eventi_attivi=[_violinista()],
    )
    cand = _candidato_arte()
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)
    base = compose_itinerary(ctx, [cand], compose_reason)
    assert base.stops[-1].experience_id == "fluttuante-violinista-1"

    alternativa = ExperienceNode(
        id="exp-alternativa", titolo="Alternativa", place_id="luogo-alternativo",
        temi=["arte"], durata_min=30, al_chiuso=False, accessibile=True,
    )
    cand_alt = GraphCandidate(experience=alternativa, place_nome="Altro Luogo", connessioni=[])

    crowd = Signal(
        meteo="sereno", affollamento={"luogo-fisso": 0.9}, stanchezza=0.0, ora=time(10, 0)
    )
    adattato = adapt_itinerary(
        base, crowd, [cand, cand_alt], profile, compose_reason, adapt_reason
    )

    assert adattato.adattato_da_segnale is True  # prova che una VERA ricostruzione è avvenuta
    fluttuanti_dopo = [s for s in adattato.stops if s.experience_id.startswith("fluttuante-")]
    assert len(fluttuanti_dopo) == 1
    assert fluttuanti_dopo[0].experience_id == "fluttuante-violinista-1"
    assert fluttuanti_dopo[0].reason == base.stops[-1].reason


# ---------------------------------------------------------------------------
# Eventi PROMOSSI (:Evento attivi nel grafo, Fase 3) — livello "programmato",
# diverso dal livello "accade ora" (Signal.eventi_attivi, sopra). AGGIUNTA in
# coda, mai una sostituzione. Sorgente: il grafo via BFF, non il `Signal`.
# ---------------------------------------------------------------------------

#: Id nel formato REALE prodotto da
#: `urban_memory.promozione_evento.evento_id_per_pattern`:
#: `evento-{place_id}-{'-'.join(temi)}`. Il test lo scrive esteso, non lo
#: calcola, così una futura divergenza di formato si vede subito.
_ID_EVENTO_MUSICA = "evento-luogo-fisso-musica-musica-di-strada"


def _evento_musica() -> EventoPromosso:
    """Un `:Evento` promosso sul luogo di `_candidato_arte`, con un tema che
    parla al profilo "arte" (`musica` ∈ `TEMI_ARTE`) e uno slug a più parole
    (`musica-di-strada`) per verificare la resa leggibile nel `reason`."""
    return EventoPromosso(
        id=_ID_EVENTO_MUSICA,
        place_id="luogo-fisso",
        temi=["musica", "musica-di-strada"],
    )


def _profilo_arte(tempo_disponibile_min: int = 200) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=tempo_disponibile_min,
    )


def test_evento_promosso_pertinente_aggiunge_tappa_in_coda() -> None:
    """(a) evento coerente col profilo e con budget disponibile -> tappa
    aggiunta IN CODA, con l'id del nodo `:Evento` INTATTO (nessun prefisso) e
    un `reason` che nomina il luogo."""
    profile = _profilo_arte()
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    it = compose_itinerary(
        ctx, [_candidato_arte()], compose_reason, eventi_promossi=[_evento_musica()]
    )

    assert len(it.stops) == 2
    tappa = it.stops[-1]
    # Nessun prefisso: l'id del grafo arriva intatto fino alla tappa.
    assert tappa.experience_id == _ID_EVENTO_MUSICA
    assert not tappa.experience_id.startswith("fluttuante-")
    assert tappa.reason  # spiegabilità obbligatoria: mai vuoto
    assert "Piazza Fissa" in tappa.reason  # place_nome risolto dai candidati reali
    # La tappa reale resta la prima: aggiunta, mai sostituzione.
    assert it.stops[0].experience_id == "exp-fisso"


def test_evento_promosso_non_pertinente_non_aggiunge_tappa() -> None:
    """(b) evento NON coerente col profilo (nessuna dimensione a peso > 0 sui
    suoi temi) -> non aggiunto."""
    profile = EmotionalProfile(
        curiosita=0.0, contemplazione=0.0, arte=0.0, con_bambini=False,
        tempo_disponibile_min=200,
    )
    evento = EventoPromosso(
        id="evento-luogo-fisso-storia", place_id="luogo-fisso", temi=["storia"]
    )
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    it = compose_itinerary(ctx, [_candidato_arte()], compose_reason, eventi_promossi=[evento])

    assert len(it.stops) == 1
    assert all(not s.experience_id.startswith("evento-") for s in it.stops)


def test_evento_promosso_non_forzato_senza_budget() -> None:
    """(c) niente budget residuo -> la tappa-evento NON si forza, anche se
    pertinente. Nessuna eccezione: si passa oltre, in silenzio."""
    profile = _profilo_arte(tempo_disponibile_min=30)
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    # L'unico candidato reale (30 min) consuma TUTTO il budget da solo.
    it = compose_itinerary(
        ctx, [_candidato_arte(durata_min=30)], compose_reason,
        eventi_promossi=[_evento_musica()],
    )

    assert len(it.stops) == 1
    assert it.stops[0].experience_id == "exp-fisso"


def test_eventi_promossi_none_o_vuoto_lascia_itinerario_identico(
    source: SeedCandidateSource,
) -> None:
    """Comportamento INVARIATO per ogni chiamante esistente: non passare
    `eventi_promossi` (il default `None`, tutti oggi) o passarlo vuoto produce
    un itinerario BIT-IDENTICO — ids, reason e orari."""
    profile = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)

    senza = compose_itinerary(ctx, cands, compose_reason)
    none_esplicito = compose_itinerary(ctx, cands, compose_reason, eventi_promossi=None)
    vuoto = compose_itinerary(ctx, cands, compose_reason, eventi_promossi=[])

    for altro in (none_esplicito, vuoto):
        assert [s.experience_id for s in senza.stops] == [s.experience_id for s in altro.stops]
        assert [s.reason for s in senza.stops] == [s.reason for s in altro.stops]
        assert [s.arrivo for s in senza.stops] == [s.arrivo for s in altro.stops]
        assert [s.durata_min for s in senza.stops] == [s.durata_min for s in altro.stops]


def test_evento_promosso_non_altera_score_ne_tappe_reali() -> None:
    """VISIBILITÀ NON ACQUISTABILE anche per il canale "promozione":
    `calcola_score` è bit-identico con e senza eventi promossi, e le tappe
    REALI (esclusa la coda `evento-...`) restano bit-identiche — stesso ordine,
    stessi reason, stessi orari."""
    profile = _profilo_arte()
    cand = _candidato_arte()
    signal = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    ctx = VisitorContext(person_id="p", profile=profile, signal=signal)

    # `==` su float è voluto: bit-identico, non prossimità. `calcola_score` non
    # ha nemmeno un parametro in cui un evento promosso possa entrare.
    prima = rules.calcola_score(cand, profile, signal)
    it_con = compose_itinerary(
        ctx, [cand], compose_reason, eventi_promossi=[_evento_musica()]
    )
    assert rules.calcola_score(cand, profile, signal) == prima

    it_senza = compose_itinerary(ctx, [cand], compose_reason)
    reali_con = [s for s in it_con.stops if not s.experience_id.startswith("evento-")]

    assert [s.experience_id for s in it_senza.stops] == [s.experience_id for s in reali_con]
    assert [s.reason for s in it_senza.stops] == [s.reason for s in reali_con]
    assert [s.arrivo for s in it_senza.stops] == [s.arrivo for s in reali_con]


def test_reason_evento_promosso_e_contesto_sul_luogo_non_un_appuntamento() -> None:
    """Il `reason` di una tappa-evento racconta un CONTESTO SUL LUOGO (nome
    del luogo + temi resi leggibili), e NON promette mai un giorno o un orario
    specifico: `EventoPromosso` non trasporta cadenza né finestra temporale,
    quindi una promessa del genere sarebbe credibile e falsa."""
    profile = _profilo_arte()
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    it = compose_itinerary(
        ctx, [_candidato_arte()], compose_reason, eventi_promossi=[_evento_musica()]
    )
    reason = it.stops[-1].reason

    # Contesto sul luogo: il luogo è nominato...
    assert "Piazza Fissa" in reason
    # ...e i temi compaiono in forma leggibile (slug -> parole, niente trattini).
    assert "musica di strada" in reason
    assert "musica-di-strada" not in reason
    # ...detto esplicitamente come tratto ricorrente, non come appuntamento.
    assert "non un appuntamento" in reason

    # NESSUNA promessa temporale: né un orario (10:30, 18.00...) né un giorno.
    assert re.search(r"\d{1,2}[:.]\d{2}", reason) is None
    giorni = (
        "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
        "stasera", "stamattina", "alle ore",
    )
    assert all(g not in reason.lower() for g in giorni)


def test_evento_promosso_determinismo_stesso_input_stesso_output() -> None:
    """Stesso profilo e stessi `eventi_promossi` -> stesso identico risultato a
    ogni chiamata (nessun riordino, nessuna sorgente non deterministica)."""
    profile = _profilo_arte()
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    eventi = [
        _evento_musica(),
        EventoPromosso(
            id="evento-luogo-fisso-liuteria", place_id="luogo-fisso", temi=["liuteria"]
        ),
    ]
    a = compose_itinerary(ctx, [_candidato_arte()], compose_reason, eventi_promossi=eventi)
    b = compose_itinerary(ctx, [_candidato_arte()], compose_reason, eventi_promossi=eventi)

    assert [s.experience_id for s in a.stops] == [s.experience_id for s in b.stops]
    assert [s.arrivo for s in a.stops] == [s.arrivo for s in b.stops]
    assert [s.reason for s in a.stops] == [s.reason for s in b.stops]
    # L'ordine di arrivo è preservato: nessun riordino inventato dal motore.
    assert [s.experience_id for s in a.stops][1:] == [e.id for e in eventi]


def test_tappa_evento_promosso_sopravvive_invariata_a_un_adapt_successivo() -> None:
    """Una tappa-evento non è tra i `candidates` di un successivo
    `adapt_itinerary` (il suo `experience_id` è quello di un nodo `:Evento`,
    non di un'`:Esperienza`): deve comportarsi ESATTAMENTE come una tappa
    sconosciuta — il percorso `_stub_da_stop` già esistente la conserva
    intatta, `reason` compreso. Il segnale forza una VERA sostituzione della
    tappa reale, così l'adapt ricostruisce davvero gli stop invece di
    ritornare l'itinerario invariato: la coda-evento deve sopravvivere anche a
    QUEL percorso. L'adattamento di una tappa-evento è fuori scope, come per i
    fluttuanti."""
    profile = _profilo_arte()
    cand = _candidato_arte()
    ctx = VisitorContext(
        person_id="p", profile=profile,
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    )
    base = compose_itinerary(ctx, [cand], compose_reason, eventi_promossi=[_evento_musica()])
    assert base.stops[-1].experience_id == _ID_EVENTO_MUSICA

    alternativa = ExperienceNode(
        id="exp-alternativa", titolo="Alternativa", place_id="luogo-alternativo",
        temi=["arte"], durata_min=30, al_chiuso=False, accessibile=True,
    )
    cand_alt = GraphCandidate(experience=alternativa, place_nome="Altro Luogo", connessioni=[])

    crowd = Signal(
        meteo="sereno", affollamento={"luogo-fisso": 0.9}, stanchezza=0.0, ora=time(10, 0)
    )
    adattato = adapt_itinerary(
        base, crowd, [cand, cand_alt], profile, compose_reason, adapt_reason
    )

    assert adattato.adattato_da_segnale is True  # prova che una VERA ricostruzione è avvenuta
    eventi_dopo = [s for s in adattato.stops if s.experience_id.startswith("evento-")]
    assert len(eventi_dopo) == 1
    assert eventi_dopo[0].experience_id == _ID_EVENTO_MUSICA
    assert eventi_dopo[0].reason == base.stops[-1].reason
    assert eventi_dopo[0].durata_min == base.stops[-1].durata_min


# --- reason di sostituzione di fallback: il nome proprio resta maiuscolo ----


def test_fallback_adapt_reason_non_abbassa_il_nome_proprio() -> None:
    from experience_engine.engine import _fallback_adapt_reason

    reason = _fallback_adapt_reason("Luigi Boccherini è legato a questo luogo.", "la pioggia")

    assert reason == "Sostituita per la pioggia. Luigi Boccherini è legato a questo luogo."
    assert "luigi" not in reason
    assert reason.startswith("Sostituita per")


def test_fallback_adapt_reason_maiuscola_iniziale_e_motivo_vuoto() -> None:
    from experience_engine.engine import _fallback_adapt_reason

    assert (
        _fallback_adapt_reason("  un chiostro al riparo;", "la pioggia")
        == "Sostituita per la pioggia. Un chiostro al riparo."
    )
    assert _fallback_adapt_reason("", "la pioggia") == "Sostituita per la pioggia."
    assert _fallback_adapt_reason(" . ", "la pioggia") == "Sostituita per la pioggia."


def test_adapt_senza_rag_usa_fallback_a_due_frasi(source: SeedCandidateSource) -> None:
    profile = EmotionalProfile(
        curiosita=0.5,
        contemplazione=0.6,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=200,
    )
    ctx = _ctx(profile)
    cands = _candidati(source, ctx)
    base = compose_itinerary(ctx, cands, compose_reason)
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.2, ora=time(10, 0))

    adattato = adapt_itinerary(base, pioggia, cands, profile, compose_reason)

    sostituite = [s for s in adattato.stops if s.reason.startswith("Sostituita per")]
    assert sostituite, "la pioggia deve sostituire almeno una tappa all'aperto"
    for stop in sostituite:
        # Nessun "…: minuscola": il motivo è una seconda frase con iniziale maiuscola.
        match = re.match(r"Sostituita per [^.]+\.(?: (.))?", stop.reason)
        assert match is not None, stop.reason
        if match.group(1) is not None:
            assert match.group(1).isupper(), stop.reason


def test_fallback_adapt_reason_segnale_vuoto() -> None:
    from experience_engine.engine import _fallback_adapt_reason

    assert _fallback_adapt_reason("", "") == "Sostituita."
    assert _fallback_adapt_reason("  ", "   ") == "Sostituita."
    assert (
        _fallback_adapt_reason("Luigi Boccherini è legato a questo luogo.", "  ")
        == "Sostituita. Luigi Boccherini è legato a questo luogo."
    )
