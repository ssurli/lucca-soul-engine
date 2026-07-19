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
