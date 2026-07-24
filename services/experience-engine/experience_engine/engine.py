"""AI Experience Engine — l'UNICO componente che DECIDE.

Compone un `Itinerary` a partire dai candidati che il grafo PROPONE, dai
`Signal` del mondo e dai vincoli etici; e lo RISCRIVE quando il mondo cambia
(pioggia, affollamento, stanchezza). La pipeline è a regole, deterministica e
testabile offline: due run identici producono lo stesso itinerario.

Il motore dipende SOLO dai contratti. Non importa `graph` né `rag`:
- i candidati arrivano come `list[GraphCandidate]` (li cabla il BFF dal grafo);
- il `reason` di ogni tappa arriva da una funzione INIETTABILE (`reason_fn`),
  che il BFF collega a `rag.reasons.compose_reason`. Se non iniettata, un
  fallback interno in italiano garantisce comunque la spiegabilità obbligatoria.

Così il vincolo etico è concentrato in un solo punto verificabile, e il motore
resta sostituibile città per città senza toccare grafo o RAG.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta

from contracts import (
    EmotionalProfile,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
    rientra_in_orario,
)

from .rules import (
    SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
    SOGLIA_STANCHEZZA_ALTA,
    TOLLERANZA_DIVERSITA,
    calcola_score,
    passa_filtri_duri,
    segnali_rilevanti,
    stima_trasferimento_min,
)

__all__ = ["compose_itinerary", "adapt_itinerary", "ReasonFn", "AdaptReasonFn", "ScoreFn"]

#: Firma della funzione che compone il `reason` di una tappa. Combacia con
#: `rag.reasons.compose_reason(candidate, profile, segnali)`.
ReasonFn = Callable[[GraphCandidate, EmotionalProfile, list[str]], str]

#: Firma della funzione che riscrive il `reason` di una tappa sostituita.
#: Combacia con `rag.reasons.adapt_reason(motivo, segnale)`.
AdaptReasonFn = Callable[[str, str], str]

#: Firma della funzione di scoring INIETTABILE dal recommender (Wave 3b).
#: Combacia con la funzione del recommender `(candidate, profile, signal) -> float`.
#: Il recommender ORDINA ma NON seleziona né filtra: riceve SOLO i candidati
#: già ammessi dal filtro duro (`passa_filtri_duri`), applicato prima e altrove.
#: Se non iniettata, il motore usa `rules.calcola_score` (comportamento MVP).
ScoreFn = Callable[[GraphCandidate, EmotionalProfile, Signal], float]


# ---------------------------------------------------------------------------
# Fallback interni di spiegabilità (usati solo se il BFF non inietta la RAG).
# Il motore NON importa `rag`: resta dipendente solo dai contratti.
# ---------------------------------------------------------------------------


def _fallback_reason(
    candidate: GraphCandidate, profile: EmotionalProfile, segnali: list[str]
) -> str:
    """`reason` minimo ma vero in italiano, se nessuna RAG è iniettata."""
    parti: list[str] = []
    if candidate.connessioni:
        parti.append(candidate.connessioni[0].strip().rstrip("."))
    else:
        parti.append(f"{candidate.experience.titolo} a {candidate.place_nome}")
    frasi_segnale = {
        "pioggia": "con la pioggia si sta al chiuso",
        "caldo": "con il caldo un luogo fresco si apprezza di più",
        "affollamento": "in questo momento è meno affollato",
        "stanchezza": "è una tappa breve, per non stancarti",
    }
    if segnali and segnali[0] in frasi_segnale:
        parti.append(frasi_segnale[segnali[0]])
    testo = "; ".join(parti)
    return testo[:1].upper() + testo[1:] + "."


def _fallback_adapt_reason(motivo: str, segnale: str) -> str:
    """`reason` di sostituzione minimo, se nessuna RAG è iniettata."""
    motivo_pulito = motivo.strip().rstrip(".;,")
    return f"Sostituita per {segnale}: {motivo_pulito[:1].lower() + motivo_pulito[1:]}."


# ---------------------------------------------------------------------------
# Utilità di composizione (pure, sull'orologio e sul budget di tempo)
# ---------------------------------------------------------------------------


def _somma_minuti(orario: time, minuti: int) -> time:
    """Avanza un orario di N minuti (giornata singola, senza data)."""
    base = datetime(2000, 1, 1, orario.hour, orario.minute, orario.second)
    return (base + timedelta(minutes=minuti)).time()


def _tema_primario(candidate: GraphCandidate) -> str:
    temi = candidate.experience.temi
    return temi[0] if temi else ""


def _con_disclosure(reason: str, candidate: GraphCandidate) -> str:
    """Appende l'attribuzione del partner (se presente) IN CODA al `reason`.

    L'attribuzione ("Offerta da ...") è disclosure trasparente e veritiera, non
    promozione: compare solo DOPO i motivi reali della scelta e non tocca lo
    score (la visibilità non è acquistabile). Se il `reason` non contiene già
    la frase, la si aggiunge come ultima frase."""
    attribuzione = getattr(candidate, "attribuzione", None)
    if not attribuzione:
        return reason
    attribuzione = attribuzione.strip()
    if not attribuzione or attribuzione in reason:
        return reason
    testo = reason.rstrip()
    if testo and not testo.endswith("."):
        testo += "."
    coda = attribuzione if attribuzione.endswith(".") else attribuzione + "."
    return f"{testo} {coda}".strip()


def _ordina_per_score(
    candidates: list[GraphCandidate],
    profile: EmotionalProfile,
    signal: Signal,
    score_fn: ScoreFn,
) -> list[tuple[float, GraphCandidate]]:
    """Ordina i candidati per (score decrescente, experience_id crescente).

    Lo score lo calcola `score_fn` (iniettabile): nell'MVP è `calcola_score`,
    ma il recommender può fornirne uno alternativo. Riceve SOLO candidati già
    ammessi dal filtro duro: ordina, non seleziona. Il tie-break su
    `experience_id` rende l'ordinamento TOTALE e stabile: è ciò che garantisce
    il determinismo richiesto dalla wave, qualunque sia la `score_fn`."""
    valutati = [(score_fn(c, profile, signal), c) for c in candidates]
    valutati.sort(key=lambda t: (-t[0], t[1].experience.id))
    return valutati


def _seleziona_tappe(
    valutati: list[tuple[float, GraphCandidate]], tempo_disponibile_min: int
) -> list[GraphCandidate]:
    """Riempie il budget di tempo diversificando luoghi e temi.

    - budget: somma durate + trasferimenti stimati <= tempo disponibile;
    - max 2 esperienze per stesso place_id;
    - preferisce, a parità (quasi) di score, un tema diverso dalla tappa
      precedente: la varietà è parte dell'esperienza, non un vezzo.
    """
    selezionati: list[GraphCandidate] = []
    conteggio_place: dict[str, int] = {}
    tempo_usato = 0
    rimanenti = list(valutati)

    while rimanenti:
        scelto_idx: int | None = None
        for idx, (score, cand) in enumerate(rimanenti):
            place = cand.experience.place_id
            if conteggio_place.get(place, 0) >= 2:
                continue
            trasferimento = stima_trasferimento_min(cand.distanza_m) if selezionati else 0
            costo = cand.experience.durata_min + trasferimento
            if tempo_usato + costo > tempo_disponibile_min:
                continue
            if scelto_idx is None:
                scelto_idx = idx
                # Diversificazione: se il migliore ripete il tema precedente,
                # cerca subito dopo un'alternativa a tema diverso entro la
                # tolleranza di score, senza tradire l'ordine per affinità.
                if selezionati and _tema_primario(cand) == _tema_primario(selezionati[-1]):
                    continue
                break
            alt_score, alt_cand = rimanenti[idx]
            if score - alt_score > TOLLERANZA_DIVERSITA:
                break
            if _tema_primario(alt_cand) != _tema_primario(selezionati[-1]):
                scelto_idx = idx
                break

        if scelto_idx is None:
            break

        _, cand = rimanenti.pop(scelto_idx)
        trasferimento = stima_trasferimento_min(cand.distanza_m) if selezionati else 0
        tempo_usato += cand.experience.durata_min + trasferimento
        conteggio_place[cand.experience.place_id] = (
            conteggio_place.get(cand.experience.place_id, 0) + 1
        )
        selezionati.append(cand)

    return selezionati


def _costruisci_stops(
    selezionati: list[GraphCandidate],
    profile: EmotionalProfile,
    signal: Signal,
    reason_fn: ReasonFn,
) -> list[ItineraryStop]:
    """Trasforma i candidati scelti in tappe con orari progressivi e `reason`.

    Ogni tappa DEVE avere un `reason` non vuoto (spiegabilità obbligatoria):
    lo compone `reason_fn` a partire dalle connessioni del grafo e dai segnali
    rilevanti per quella tappa."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    for i, cand in enumerate(selezionati):
        if i > 0:
            orario = _somma_minuti(orario, stima_trasferimento_min(cand.distanza_m))
        segnali = segnali_rilevanti(cand, signal)
        reason = _con_disclosure(reason_fn(cand, profile, segnali), cand)
        stops.append(
            ItineraryStop(
                experience_id=cand.experience.id,
                arrivo=orario,
                durata_min=cand.experience.durata_min,
                reason=reason,
            )
        )
        orario = _somma_minuti(orario, cand.experience.durata_min)
    return stops


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def compose_itinerary(
    ctx: VisitorContext,
    candidates: list[GraphCandidate],
    reason_fn: ReasonFn | None = None,
    score_fn: ScoreFn | None = None,
) -> Itinerary:
    """Compone un `Itinerary` a regole per il contesto dato.

    Pipeline (separata in funzioni pure e testabili):
      1. filtri duri etici  -> `rules.passa_filtri_duri`
      2. scoring per affinità -> `score_fn` (default: `rules.calcola_score`)
      3. composizione a budget con diversificazione -> `_seleziona_tappe`
      4. `reason` obbligatorio per ogni tappa -> `_costruisci_stops`

    `score_fn` è INIETTABILE (Wave 3b): il recommender può fornire un ranking
    alternativo. È applicato DOPO il filtro duro, mai prima: riceve solo i
    candidati già ammessi dai vincoli etici, quindi ORDINA ma non seleziona né
    filtra — non può "salvare" un candidato escluso. Se `None`, l'MVP usa
    `rules.calcola_score` (comportamento invariato per ogni chiamante esistente).

    Determinismo totale: a parità di score l'ordine è per `experience_id`.
    Due profili diversi possono produrre itinerari diversi — è il criterio
    d'accettazione centrale della wave.
    """
    fn = reason_fn or _fallback_reason
    score = score_fn or calcola_score
    profile = ctx.profile

    ammessi = [
        c
        for c in candidates
        if passa_filtri_duri(c, profile, ctx.signal, ctx.luoghi_gia_visti)
    ]
    valutati = _ordina_per_score(ammessi, profile, ctx.signal, score)
    selezionati = _seleziona_tappe(valutati, profile.tempo_disponibile_min)
    stops = _costruisci_stops(selezionati, profile, ctx.signal, fn)

    return Itinerary(
        person_id=ctx.person_id,
        stops=stops,
        generated_at=datetime.now(),
        adattato_da_segnale=False,
    )


def _migliore_alternativa(
    candidates: list[GraphCandidate],
    signal: Signal,
    profile: EmotionalProfile,
    esclusi: set[str],
    richiede_accessibile: bool,
    solo_al_chiuso: bool,
    max_affollamento: float,
) -> GraphCandidate | None:
    """Migliore candidato non già usato che rispetta i vincoli del segnale.

    Deterministico: tie-break per `experience_id`. Mantiene i vincoli duri
    (accessibilità mai degradata; luogo scorrevole per l'affollamento;
    orari di apertura — Wave 3a+, `ExperienceNode.orari_apertura` — perché
    una sostituzione in adattamento non deve MAI reintrodurre un'esperienza
    chiusa nel giorno/ora del segnale: trovato da una verifica etica
    dedicata, prima non coperto qui pur essendo già coperto in
    `rules.passa_filtri_duri` per la composizione iniziale — stessa
    informazione, `contracts.rientra_in_orario`, ora applicata anche qui).

    NOTA (limite pre-esistente, non chiuso da questa correzione): questa
    funzione NON verifica `partner_abbonamento_attivo` — un partner con
    abbonamento non attivo può quindi, oggi, essere reintrodotto come
    alternativa in adattamento, mentre `passa_filtri_duri` lo esclude
    sempre in composizione iniziale. Non è un problema introdotto da questo
    fix (preesisteva anche prima degli orari di apertura): documentato in
    `docs/LIMITI.md`, non corretto qui perché fuori dallo scope di questa
    verifica (che riguardava gli orari, non l'abbonamento)."""
    ammessi: list[GraphCandidate] = []
    for c in candidates:
        e = c.experience
        if e.id in esclusi:
            continue
        if richiede_accessibile and not e.accessibile:
            continue
        if solo_al_chiuso and not e.al_chiuso:
            continue
        if signal.affollamento.get(e.place_id, 0.0) > max_affollamento:
            continue
        if not rientra_in_orario(e.orari_apertura, signal.giorno_settimana, signal.ora):
            continue
        ammessi.append(c)
    if not ammessi:
        return None
    ammessi.sort(key=lambda c: (-calcola_score(c, profile, signal), c.experience.id))
    return ammessi[0]


def adapt_itinerary(
    itinerary: Itinerary,
    signal: Signal,
    candidates: list[GraphCandidate],
    profile: EmotionalProfile | None = None,
    reason_fn: ReasonFn | None = None,
    adapt_reason_fn: AdaptReasonFn | None = None,
) -> Itinerary:
    """Riscrive SOLO ciò che il nuovo segnale tocca.

    - pioggia: le tappe `al_chiuso=False` sono sostituite dalla migliore
      alternativa `al_chiuso=True` non già presente;
    - affollamento > soglia sul luogo di una tappa: sostituzione con
      alternativa in luogo scorrevole (distribuzione dei flussi);
    - stanchezza > soglia: taglia le tappe in coda oltre ~2/3 del tempo
      originale (il benessere conta più del numero di tappe).

    Le tappe non toccate restano IDENTICHE, `reason` compreso. Se nulla va
    riscritto, l'itinerario originale è restituito invariato
    (`adattato_da_segnale` resta False).
    """
    fn = reason_fn or _fallback_reason
    adapt_fn = adapt_reason_fn or _fallback_adapt_reason
    per_id = {c.experience.id: c for c in candidates}
    # Accessibilità: se il profilo la richiede, vale sempre. Se il profilo è
    # assente (l'AdaptRequest non lo trasporta), regola CONSERVATIVA per tappa:
    # una tappa accessibile può essere sostituita SOLO da una accessibile.
    base_accessibile = profile.accessibilita_richiesta if profile is not None else False
    profilo_effettivo = profile or _profilo_neutro()

    usati = {s.experience_id for s in itinerary.stops}
    nuovi_candidati: list[GraphCandidate] = []
    cambiato = False

    for stop in itinerary.stops:
        cand = per_id.get(stop.experience_id)
        if cand is None:
            # Non conosciamo questa esperienza tra i candidati: la lasciamo
            # intatta (reason compreso) invece di riscrivere al buio.
            nuovi_candidati.append(_stub_da_stop(stop))
            continue

        e = cand.experience
        place_affollato = (
            signal.affollamento.get(e.place_id, 0.0) > SOGLIA_AFFOLLAMENTO_ADATTAMENTO
        )
        piove_e_aperto = signal.meteo == "pioggia" and not e.al_chiuso

        if not (piove_e_aperto or place_affollato):
            # Tappa non toccata dal segnale: resta IDENTICA, reason compreso.
            nuovi_candidati.append(_marca_reason(cand, stop.reason))
            continue

        richiede_accessibile = base_accessibile or (profile is None and e.accessibile)
        alt = _migliore_alternativa(
            candidates=candidates,
            signal=signal,
            profile=profilo_effettivo,
            esclusi=usati,
            richiede_accessibile=richiede_accessibile,
            solo_al_chiuso=piove_e_aperto,
            max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
        )
        if alt is None:
            nuovi_candidati.append(_marca_reason(cand, stop.reason))
            continue

        usati.discard(e.id)
        usati.add(alt.experience.id)
        motivo = alt.connessioni[0] if alt.connessioni else alt.experience.titolo
        segnale = "la pioggia" if piove_e_aperto else f"l'affollamento a {cand.place_nome}"
        alt_reason = adapt_fn(motivo, segnale)
        nuovi_candidati.append(_marca_reason(alt, alt_reason))
        cambiato = True

    # Stanchezza alta: taglia la coda oltre ~2/3 del tempo originale.
    if signal.stanchezza > SOGLIA_STANCHEZZA_ALTA:
        tagliati = _taglia_per_stanchezza(itinerary, nuovi_candidati)
        if len(tagliati) < len(nuovi_candidati):
            nuovi_candidati = tagliati
            cambiato = True

    if not cambiato:
        return itinerary

    stops = _ricostruisci_stops(nuovi_candidati, profilo_effettivo, signal, fn)
    return Itinerary(
        person_id=itinerary.person_id,
        stops=stops,
        generated_at=datetime.now(),
        adattato_da_segnale=True,
    )


# ---------------------------------------------------------------------------
# Supporto all'adattamento
# ---------------------------------------------------------------------------

#: Marcatore per trasportare, in adapt, un `reason` già deciso (tappa
#: sostituita) o quello originale (tappa intatta) accanto al candidato.
_REASON_ATTR = "_reason_deciso"


def _profilo_neutro() -> EmotionalProfile:
    """Profilo neutro usato quando l'`AdaptRequest` non trasporta il profilo:
    serve solo a ordinare le alternative, non reintroduce preferenze."""
    return EmotionalProfile(
        curiosita=0.5,
        contemplazione=0.5,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=10_000,
    )


class _CandidatoConReason(GraphCandidate):
    """Candidato con un `reason` già deciso allegato (interno all'adapt)."""

    reason_deciso: str | None = None


def _marca_reason(cand: GraphCandidate, reason: str) -> _CandidatoConReason:
    return _CandidatoConReason(**cand.model_dump(), reason_deciso=reason)


def _stub_da_stop(stop: ItineraryStop) -> _CandidatoConReason:
    """Ricostruisce un candidato "fantasma" da una tappa sconosciuta, così da
    conservarla identica (reason compreso) quando non è tra i candidati."""
    from contracts import ExperienceNode

    esperienza = ExperienceNode(
        id=stop.experience_id,
        titolo=stop.experience_id,
        place_id=stop.experience_id,
        temi=[],
        durata_min=stop.durata_min,
        al_chiuso=True,
        accessibile=True,
    )
    return _CandidatoConReason(
        experience=esperienza,
        place_nome=stop.experience_id,
        connessioni=[],
        reason_deciso=stop.reason,
    )


def _taglia_per_stanchezza(
    itinerary: Itinerary, correnti: list[GraphCandidate]
) -> list[GraphCandidate]:
    """Mantiene le tappe di testa entro ~2/3 del tempo originale.

    Le tappe di coda sono le meno affini (l'itinerario è ordinato per score in
    composizione): tagliarle riduce lo sforzo senza sacrificare il meglio."""
    durata_originale = sum(s.durata_min for s in itinerary.stops)
    limite = int(durata_originale * 2 / 3)
    tenuti: list[GraphCandidate] = []
    tempo = 0
    for cand in correnti:
        prossimo = tempo + cand.experience.durata_min
        if tenuti and prossimo > limite:
            break
        tenuti.append(cand)
        tempo = prossimo
    return tenuti or correnti[:1]


def _ricostruisci_stops(
    correnti: list[GraphCandidate],
    profile: EmotionalProfile,
    signal: Signal,
    reason_fn: ReasonFn,
) -> list[ItineraryStop]:
    """Ricalcola orari progressivi conservando i `reason` già decisi (tappe
    intatte o sostituite) e componendo quelli mancanti via `reason_fn`."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    for i, cand in enumerate(correnti):
        if i > 0:
            orario = _somma_minuti(orario, stima_trasferimento_min(cand.distanza_m))
        reason = getattr(cand, "reason_deciso", None)
        if not reason:
            reason = reason_fn(cand, profile, segnali_rilevanti(cand, signal))
        # Disclosure in coda (idempotente: non duplica se già presente, es.
        # nelle tappe non toccate che conservano il reason originale).
        reason = _con_disclosure(reason, cand)
        stops.append(
            ItineraryStop(
                experience_id=cand.experience.id,
                arrivo=orario,
                durata_min=cand.experience.durata_min,
                reason=reason,
            )
        )
        orario = _somma_minuti(orario, cand.experience.durata_min)
    return stops
