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

import math
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from contracts import (
    EmotionalProfile,
    EventoPromosso,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    VisitorContext,
    rientra_in_orario,
)

from .rules import (
    DURATA_TAPPA_EVENTO_MIN,
    DURATA_TAPPA_FLUTTUANTE_MIN,
    SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
    SOGLIA_STANCHEZZA_ALTA,
    TEMPO_TRASFERIMENTO_DEFAULT_MIN,
    TOLLERANZA_DIVERSITA,
    calcola_score,
    eventi_promossi_pertinenti,
    giorno_occorrenza_attesa,
    passa_filtri_duri,
    segnali_fluttuanti_pertinenti,
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
    """`reason` di sostituzione minimo, se nessuna RAG è iniettata.

    Due frasi: il case del motivo non viene mai abbassato, perché spesso è una
    connessione del grafo che inizia con un nome proprio ("Luigi Boccherini…").
    """
    segnale_pulito = segnale.strip()
    prefisso = f"Sostituita per {segnale_pulito}" if segnale_pulito else "Sostituita"
    motivo_pulito = motivo.strip().rstrip(".;,").strip()
    if not motivo_pulito:
        return f"{prefisso}."
    return f"{prefisso}. {motivo_pulito[:1].upper() + motivo_pulito[1:]}."


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
# Segnali FLUTTUANTI (Signal.eventi_attivi) — AGGIUNTA in coda, mai una
# sostituzione. Livello "accade ora" (violinista in piazza): diverso dal
# livello "programmato" (:Evento promosso), che vive nella sezione gemella
# più sotto e arriva da una sorgente diversa (il grafo, non il `Signal`).
# ---------------------------------------------------------------------------

#: Prefisso dell'`experience_id` fittizio con cui una tappa fluttuante entra
#: in `Itinerary.stops`. Namespace SEPARATO da quello reale del seed
#: (`exp-...`): evita per costruzione che l'id di un segnale fluttuante
#: possa mai collidere con un'esperienza permanente vera (es. durante un
#: successivo `adapt_itinerary`, che risale a `GraphCandidate` proprio da
#: `experience_id`).
_PREFISSO_TAPPA_FLUTTUANTE = "fluttuante-"


def _minuti_trascorsi(inizio: time, fine: time) -> int:
    """Minuti tra due orari nella stessa giornata (mai negativo per come è
    usata qui: `fine` è sempre `>= inizio`, costruita avanzando `inizio`)."""
    base_inizio = datetime(2000, 1, 1, inizio.hour, inizio.minute, inizio.second)
    base_fine = datetime(2000, 1, 1, fine.hour, fine.minute, fine.second)
    return int((base_fine - base_inizio).total_seconds() // 60)


def _reason_fluttuante(segnale: SegnaleFluttuante, place_nome: str) -> str:
    """`reason` sempre non vuoto (spiegabilità obbligatoria) per una tappa
    fluttuante: racconta COSA (la descrizione dichiarata dal segnale) e DOVE
    (il nome del luogo, se noto tra i candidati; altrimenti il `place_id`
    grezzo — mai un nome fabbricato)."""
    return f"{segnale.descrizione} a {place_nome}: un'aggiunta per oggi, non era già in programma."


def _aggiungi_tappe_fluttuanti(
    stops: list[ItineraryStop],
    candidates: list[GraphCandidate],
    profile: EmotionalProfile,
    signal: Signal,
) -> list[ItineraryStop]:
    """Aggiunge, IN CODA, le tappe fluttuanti pertinenti — mai una
    sostituzione (le tappe 1-4 restano esattamente come composte). Rispetta
    il budget di tempo residuo: se non c'è spazio, la tappa fluttuante NON
    si aggiunge — mai forzata oltre `profile.tempo_disponibile_min`.

    Ogni tappa fluttuante costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessuna
    `distanza_m` nota per un segnale, stessa stima prudente già usata
    altrove per una distanza sconosciuta) + `DURATA_TAPPA_FLUTTUANTE_MIN`
    (una tappa "breve" per definizione)."""
    pertinenti = segnali_fluttuanti_pertinenti(signal.eventi_attivi, profile)
    if not pertinenti:
        return stops

    place_nomi = {c.experience.place_id: c.place_nome for c in candidates}

    if stops:
        minuti_usati = _minuti_trascorsi(signal.ora, stops[-1].arrivo) + stops[-1].durata_min
        orario_corrente = _somma_minuti(stops[-1].arrivo, stops[-1].durata_min)
    else:
        minuti_usati = 0
        orario_corrente = signal.ora

    nuove_tappe = list(stops)
    for segnale in pertinenti:
        costo = TEMPO_TRASFERIMENTO_DEFAULT_MIN + DURATA_TAPPA_FLUTTUANTE_MIN
        if minuti_usati + costo > profile.tempo_disponibile_min:
            continue  # niente budget: non si forza, si passa al prossimo segnale
        orario_corrente = _somma_minuti(orario_corrente, TEMPO_TRASFERIMENTO_DEFAULT_MIN)
        place_nome = place_nomi.get(segnale.place_id, segnale.place_id)
        nuove_tappe.append(
            ItineraryStop(
                experience_id=f"{_PREFISSO_TAPPA_FLUTTUANTE}{segnale.id}",
                arrivo=orario_corrente,
                durata_min=DURATA_TAPPA_FLUTTUANTE_MIN,
                reason=_reason_fluttuante(segnale, place_nome),
            )
        )
        orario_corrente = _somma_minuti(orario_corrente, DURATA_TAPPA_FLUTTUANTE_MIN)
        minuti_usati += costo

    return nuove_tappe


# ---------------------------------------------------------------------------
# Eventi PROMOSSI (:Evento attivi nel grafo, Fase 3) — AGGIUNTA in coda, mai
# una sostituzione. Stessa identica meccanica dei fluttuanti sopra (budget,
# orari progressivi, skip se non c'è spazio), sorgente DIVERSA: non
# `Signal.eventi_attivi` (stato del mondo, transitorio) ma nodi permanenti del
# grafo letti dal BFF e PASSATI al motore già filtrati a `stato='attivo'` —
# il motore non legge il grafo e non importa `graph`/`urban_memory`.
# ---------------------------------------------------------------------------

# NESSUN prefisso sull'`experience_id`, a differenza delle tappe fluttuanti
# (`_PREFISSO_TAPPA_FLUTTUANTE` sopra): `EventoPromosso.id` è GIÀ un id
# namespaced per costruzione — `evento-{place_id}-{temi}`, prodotto da
# `urban_memory.promozione_evento.evento_id_per_pattern` — quindi
# strutturalmente distinto sia dalle esperienze reali del seed (`exp-...`) sia
# dalle tappe fluttuanti (`fluttuante-...`). Aggiungere un secondo prefisso
# creerebbe un id che non corrisponde a nessun nodo del grafo, rompendo la
# tracciabilità della tappa verso l'`:Evento` che l'ha generata.


def _temi_leggibili(temi: list[str]) -> str:
    """Rende leggibile una lista di temi GREZZI (id/slug del grafo, es.
    "musica-di-strada") per il `reason` di una tappa-evento.

    `EventoPromosso.temi` porta lo stesso contenuto grezzo di
    `SegnaleFluttuante.temi` e di `ExperienceNode.temi` — id, non nomi umani
    (i nomi leggibili dei `:Tema` viaggiano su un campo separato della query
    candidati, `temi_nomi`, che qui non esiste). Sostituisce i trattini con
    spazi e unisce con virgola: trasformazione PURA, mai un lookup a un nodo
    `:Tema` che questa funzione non ha modo di fare — meglio un id reso
    leggibile che un nome fabbricato."""
    return ", ".join(tema.replace("-", " ") for tema in temi)


# Nomi italiani in CODICE, mai `strftime("%A")`/`%B`: il risultato non deve
# dipendere dalla locale di sistema della macchina che esegue il motore
# (notebook e PC fisso possono averne di diverse). Indici: `date.weekday()`
# (0=lunedì) e `date.month` (1=gennaio, indice 0 inutilizzato).
_GIORNI_SETTIMANA_IT = (
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
)
_MESI_IT = (
    "",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


def _giorno_relativo_it(giorno: date, data_visita: date) -> str:
    """Il giorno `giorno` detto in italiano RELATIVAMENTE a `data_visita`:
    "oggi", "domani", "ieri", altrimenti giorno della settimana + data
    ("giovedì 15 ottobre"). Pura, indipendente dalla locale di sistema."""
    scarto = (giorno - data_visita).days
    if scarto == 0:
        return "oggi"
    if scarto == 1:
        return "domani"
    if scarto == -1:
        return "ieri"
    return f"{_GIORNI_SETTIMANA_IT[giorno.weekday()]} {giorno.day} {_MESI_IT[giorno.month]}"


def _cadenza_leggibile(cadenza_giorni: float) -> str:
    """Cadenza APPROSSIMATA in italiano ("circa ogni 7 giorni"): arrotondata
    al giorno intero (mezzo giorno verso l'alto, mai `round` bancario), mai
    sotto 1 — è una regolarità osservata, non un calendario esatto."""
    giorni = max(1, math.floor(cadenza_giorni + 0.5))
    if giorni == 1:
        return "circa ogni giorno"
    return f"circa ogni {giorni} giorni"


def _reason_evento_promosso(evento: EventoPromosso, place_nome: str, data_visita: date) -> str:
    """`reason` sempre non vuoto, in italiano (spiegabilità obbligatoria) per
    una tappa generata da un `:Evento` promosso.

    La tappa compare SOLO se `data_visita` cade nella finestra attorno a
    un'occorrenza attesa (`rules.evento_in_finestra`), quindi il reason PUÒ
    nominare un giorno — ma ONESTAMENTE: è un'occorrenza ATTESA, proiettata
    da una regolarità osservata (`ultima_occorrenza` + k·`cadenza_giorni`),
    NON un appuntamento confermato da qualcuno. Lo dice esplicitamente.
    Include il giorno atteso relativo alla visita (`rules.
    giorno_occorrenza_attesa`, lo STESSO calcolo della finestra, non un
    secondo) e la cadenza approssimata. Nessun orario (non lo abbiamo) e
    nessuna descrizione dell'evento (non sopravvive alla promozione): una
    frase credibile e falsa sarebbe la peggiore forma di inspiegabilità."""
    giorno = giorno_occorrenza_attesa(evento.ultima_occorrenza, evento.cadenza_giorni, data_visita)
    quando = _giorno_relativo_it(giorno, data_visita)
    if giorno < data_visita:
        occorrenza = f"un'occorrenza era attesa {quando}"
    else:
        occorrenza = f"la prossima occorrenza è attesa {quando}"
    return (
        f"Presso {place_nome} si ripete qualcosa legato a {_temi_leggibili(evento.temi)}, "
        f"osservato {_cadenza_leggibile(evento.cadenza_giorni)}: {occorrenza}. "
        "È una stima dalla regolarità osservata, non un appuntamento confermato, "
        "e non ne conosciamo l'orario."
    )


def _aggiungi_tappe_eventi_promossi(
    stops: list[ItineraryStop],
    candidates: list[GraphCandidate],
    profile: EmotionalProfile,
    eventi_promossi: list[EventoPromosso],
    ora_inizio: time | None = None,
    *,
    data_visita: date | None,
) -> list[ItineraryStop]:
    """Aggiunge, IN CODA, le tappe degli eventi promossi pertinenti — mai una
    sostituzione (le tappe 1-4 e le eventuali tappe fluttuanti restano
    esattamente come composte). Rispetta il budget di tempo residuo: se non
    c'è spazio, la tappa NON si aggiunge — mai forzata oltre
    `profile.tempo_disponibile_min`.

    Ogni tappa-evento costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessuna
    `distanza_m` nota per un `:Evento`, stessa stima prudente già usata
    altrove per una distanza sconosciuta) + `DURATA_TAPPA_EVENTO_MIN`.

    `minuti_usati`/`orario_corrente` sono RICALCOLATI da `stops[-1]`, non
    portati da un accumulatore esterno: così questa funzione può essere
    chiamata DOPO `_aggiungi_tappe_fluttuanti` e continuare correttamente il
    budget condiviso, qualunque coda le due sezioni abbiano già prodotto.

    `ora_inizio` (`ctx.signal.ora` quando chiamata da `compose_itinerary`) è
    l'origine dell'orologio, e serve SOLO nel caso limite in cui `stops` è
    vuota — nessuna tappa reale né fluttuante da cui ripartire. Se in quel
    caso non è fornita, la tappa-evento NON si aggiunge: meglio non
    aggiungerla che collocarla a un orario fabbricato (es. mezzanotte), lo
    stesso principio per cui `place_nome` ricade sul `place_id` grezzo invece
    di inventare un nome.

    `data_visita` (`ctx.signal.data`) è keyword-only e SENZA default: decide
    la finestra temporale (`rules.eventi_promossi_pertinenti`, fail-closed se
    `None` — nessuna tappa-evento) e il giorno atteso raccontato nel
    `reason`. Nessun chiamante può dimenticarla in silenzio."""
    pertinenti = eventi_promossi_pertinenti(eventi_promossi, profile, data_visita)
    if not pertinenti or data_visita is None:
        return stops

    place_nomi = {c.experience.place_id: c.place_nome for c in candidates}

    if stops:
        # Origine del conteggio: `ora_inizio` se nota, altrimenti l'arrivo
        # della prima tappa — che per costruzione parte proprio da
        # `signal.ora` (vedi `_costruisci_stops`), quindi il risultato è lo
        # stesso; il fallback esiste per non dipendere da un parametro
        # facoltativo quando l'informazione è già dentro `stops`.
        origine = ora_inizio if ora_inizio is not None else stops[0].arrivo
        minuti_usati = _minuti_trascorsi(origine, stops[-1].arrivo) + stops[-1].durata_min
        orario_corrente = _somma_minuti(stops[-1].arrivo, stops[-1].durata_min)
    elif ora_inizio is not None:
        minuti_usati = 0
        orario_corrente = ora_inizio
    else:
        return stops

    nuove_tappe = list(stops)
    for evento in pertinenti:
        costo = TEMPO_TRASFERIMENTO_DEFAULT_MIN + DURATA_TAPPA_EVENTO_MIN
        if minuti_usati + costo > profile.tempo_disponibile_min:
            continue  # niente budget: non si forza, si passa al prossimo evento
        orario_corrente = _somma_minuti(orario_corrente, TEMPO_TRASFERIMENTO_DEFAULT_MIN)
        place_nome = place_nomi.get(evento.place_id, evento.place_id)
        nuove_tappe.append(
            ItineraryStop(
                # `evento.id` DIRETTAMENTE, senza prefisso — vedi il commento
                # in testa a questa sezione.
                experience_id=evento.id,
                arrivo=orario_corrente,
                durata_min=DURATA_TAPPA_EVENTO_MIN,
                reason=_reason_evento_promosso(evento, place_nome, data_visita),
            )
        )
        orario_corrente = _somma_minuti(orario_corrente, DURATA_TAPPA_EVENTO_MIN)
        minuti_usati += costo

    return nuove_tappe


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def compose_itinerary(
    ctx: VisitorContext,
    candidates: list[GraphCandidate],
    reason_fn: ReasonFn | None = None,
    score_fn: ScoreFn | None = None,
    eventi_promossi: list[EventoPromosso] | None = None,
) -> Itinerary:
    """Compone un `Itinerary` a regole per il contesto dato.

    Pipeline (separata in funzioni pure e testabili):
      1. filtri duri etici  -> `rules.passa_filtri_duri`
      2. scoring per affinità -> `score_fn` (default: `rules.calcola_score`)
      3. composizione a budget con diversificazione -> `_seleziona_tappe`
      4. `reason` obbligatorio per ogni tappa -> `_costruisci_stops`
      5. segnali FLUTTUANTI pertinenti, in CODA -> `_aggiungi_tappe_fluttuanti`
      6. eventi PROMOSSI pertinenti, in CODA -> `_aggiungi_tappe_eventi_promossi`

    `score_fn` è INIETTABILE (Wave 3b): il recommender può fornire un ranking
    alternativo. È applicato DOPO il filtro duro, mai prima: riceve solo i
    candidati già ammessi dai vincoli etici, quindi ORDINA ma non seleziona né
    filtra — non può "salvare" un candidato escluso. Se `None`, l'MVP usa
    `rules.calcola_score` (comportamento invariato per ogni chiamante esistente).

    Il passo 5 (`Signal.eventi_attivi`, segnali "accade ora" — violinista in
    piazza, non un nodo del grafo) è un'AGGIUNTA, mai una sostituzione: non
    tocca i passi 1-4, non tocca `score_fn`/`calcola_score`, non altera quali
    esperienze permanenti sono scelte né il loro punteggio. Se non c'è alcun
    segnale attivo (`eventi_attivi=[]`, ogni chiamante oggi), il passo 5 è un
    no-op — comportamento invariato.

    Il passo 6 (`eventi_promossi`, nodi `:Evento` PROMOSSI e attivi nel grafo,
    Fase 3 — il livello "programmato", diverso dal passo 5) segue esattamente
    la stessa regola: è un'AGGIUNTA in coda, mai una sostituzione; non tocca i
    passi 1-4, non tocca `score_fn`/`calcola_score`, non altera quali
    esperienze permanenti sono scelte né il loro punteggio. La lista arriva
    GIÀ pronta e già filtrata a `stato='attivo'` dal BFF (il motore non legge
    il grafo, non importa `graph` né `urban_memory`, e non scrive nulla). Se è
    `None` o vuota — ogni chiamante esistente oggi, che questo parametro non
    lo passa — il passo 6 è un no-op: comportamento invariato, bit per bit.
    Un evento compare SOLO se `ctx.signal.data` cade nella finestra attorno a
    un'occorrenza attesa (`rules.evento_in_finestra`); se `Signal.data` è
    `None` il passo 6 è un no-op (fail-closed: mai una data inventata).
    Il parametro è ULTIMO proprio per non spostare `reason_fn`/`score_fn` e
    non rompere le chiamate posizionali già in essere.

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
    stops = _aggiungi_tappe_fluttuanti(stops, candidates, profile, ctx.signal)
    stops = _aggiungi_tappe_eventi_promossi(
        stops,
        candidates,
        profile,
        eventi_promossi or [],
        ctx.signal.ora,
        data_visita=ctx.signal.data,
    )

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
