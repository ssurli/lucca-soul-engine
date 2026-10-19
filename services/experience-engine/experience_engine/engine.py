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
import re
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from typing import Literal

from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    EventoPromosso,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    TappaEsclusa,
    VisitorContext,
    VocabolarioTemi,
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
    frase_bagliore,
    giorno_occorrenza_attesa,
    passa_filtri_duri,
    segnali_fluttuanti_pertinenti,
    segnali_rilevanti,
    stima_trasferimento_min,
    temi_leggibili,
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
    """Avanza un orario di N minuti (giornata singola, senza data).

    Riavvolge a mezzanotte: per questo nessun itinerario deve mai arrivarci
    oltre. Il tetto è `_minuti_alla_mezzanotte`, applicato in composizione e
    in adattamento."""
    base = datetime(2000, 1, 1, orario.hour, orario.minute, orario.second)
    return (base + timedelta(minutes=minuti)).time()


#: Minuti di una giornata: un itinerario è sempre una sessione nella stessa
#: giornata e finisce al più alle 24:00 (decisione di prodotto, wave
#: "adattamento", `docs/BUILD_PLAN.md`).
MINUTI_GIORNATA = 24 * 60


def _minuti_alla_mezzanotte(ora: time) -> int:
    """Tetto della giornata: minuti da `ora` alle 24:00 (`1440 - (h*60 + m)`).

    UNICA funzione del tetto, usata dalla composizione (budget effettivo =
    min(budget dichiarato, questo valore)) e dall'adattamento (taglio delle
    tappe oltre mezzanotte, limite delle sostituzioni). Sempre >= 1: i
    secondi di `ora` non contano (un `Signal.ora` è un orario al minuto)."""
    return MINUTI_GIORNATA - (ora.hour * 60 + ora.minute)


def _tema_primario(candidate: GraphCandidate) -> str:
    temi = candidate.experience.temi
    return temi[0] if temi else ""


#: Inizio della frase di attribuzione (formato di `graph.attribuzione`, tutte
#: le versioni): è ciò che riconosce una disclosure nel `reason`.
_PREFISSO_ATTRIBUZIONE = "Offerta da "
#: Fine di una frase: un punto seguito da spazio o dalla fine del testo.
_RE_FINE_FRASE = re.compile(r"\.(?=\s|$)")


def _attribuzione_corrente(candidate: GraphCandidate) -> str:
    """Attribuzione del candidato normalizzata (spazi tolti, punto finale),
    oppure stringa vuota se il candidato non ne ha."""
    attribuzione = (getattr(candidate, "attribuzione", None) or "").strip()
    if not attribuzione:
        return ""
    return attribuzione if attribuzione.endswith(".") else attribuzione + "."


def _ultima_frase_attribuzione(reason: str, attribuzione: str) -> tuple[int, int] | None:
    """Estremi `[inizio, fine)` dell'ULTIMA frase del `reason` che inizia con
    "Offerta da ", o `None` se non c'è.

    La frase inizia a inizio testo o dopo uno spazio. Finisce: se coincide con
    l'attribuzione corrente, dove finisce quella; altrimenti al primo punto
    seguito da spazio o dalla fine del testo (un nome di bottega con un punto
    interno, es. "S.r.l. ", in un formato vecchio sarebbe tagliato lì:
    docs/LIMITI.md)."""
    inizio = len(reason)
    while True:
        inizio = reason.rfind(_PREFISSO_ATTRIBUZIONE, 0, inizio)
        if inizio < 0:
            return None
        if inizio == 0 or reason[inizio - 1].isspace():
            break
    if attribuzione and reason.startswith(attribuzione, inizio):
        return inizio, inizio + len(attribuzione)
    fine = _RE_FINE_FRASE.search(reason, inizio)
    return inizio, fine.end() if fine else len(reason)


def _con_disclosure(reason: str, candidate: GraphCandidate) -> str:
    """Rende l'attribuzione del partner l'UNICA e ULTIMA frase "Offerta da ..."
    del `reason`, calcolata dal candidato corrente del grafo.

    L'attribuzione è disclosure trasparente e veritiera, non promozione:
    compare solo DOPO i motivi reali della scelta e non tocca lo score (la
    visibilità non è acquistabile). Regola:
    - il `reason` finisce già con l'attribuzione corrente: invariato
      (idempotente);
    - il `reason` contiene una frase che inizia con "Offerta da " (per
      esempio nel formato di una versione precedente, arrivata dal client in
      `AdaptRequest`): l'ULTIMA di queste frasi è tolta e l'attribuzione
      corrente va in coda; se il candidato non ha più attribuzione (partner
      non più presente) la frase è solo tolta, il resto del `reason` non
      cambia;
    - nessuna frase "Offerta da " e attribuzione presente: si aggiunge in
      coda.
    Va chiamata SOLO con un candidato reale del grafo: le tappe sconosciute
    (stub dell'adattamento) non passano di qui."""
    attribuzione = _attribuzione_corrente(candidate)
    if attribuzione and reason.rstrip().endswith(attribuzione):
        return reason
    estremi = _ultima_frase_attribuzione(reason, attribuzione)
    if estremi is None:
        if not attribuzione:
            return reason
        testo = reason.rstrip()
    else:
        inizio, fine = estremi
        prima = reason[:inizio].rstrip()
        dopo = reason[fine:].strip()
        testo = " ".join(parte for parte in (prima, dopo) if parte)
        if not attribuzione:
            return testo
    if testo and not testo.endswith("."):
        testo += "."
    return f"{testo} {attribuzione}".strip()


def _con_bagliore(reason: str, candidate: GraphCandidate, frase: str | None) -> str:
    """Inserisce la frase del bagliore (`rules.frase_bagliore`) nel `reason`
    di una tappa GIÀ SCELTA, PRIMA della disclosure partner.

    La disclosure ("Offerta da ...") deve restare SEMPRE l'ultima frase. Due
    casi:
    - `reason_fn` NON ha incluso l'attribuzione: la frase si appende in coda,
      e `_con_disclosure` (chiamata dopo) appenderà l'attribuzione dopo di
      essa;
    - `reason_fn` HA GIÀ incluso l'attribuzione: `_con_disclosure` non la
      riappende (idempotente), quindi la frase va inserita PRIMA
      dell'ultima occorrenza dell'attribuzione, non in coda.
    Se l'attribuzione corrente non compare ma il `reason` ha una frase
    "Offerta da " (formato precedente, arrivato dal client), la frase va
    prima di quella: `_con_disclosure` la sostituirà con l'attribuzione
    corrente, che resta così l'ultima.
    `frase=None` -> `reason` restituito identico (bit per bit).

    Stessa regola per la frase dell'esito di adattamento
    (`_frase_esito`): una sola funzione colloca le frasi del motore prima
    della disclosure."""
    if not frase:
        return reason
    attribuzione = (getattr(candidate, "attribuzione", None) or "").strip()
    idx = reason.rfind(attribuzione) if attribuzione else -1
    if idx < 0:
        estremi = _ultima_frase_attribuzione(reason, "")
        idx = estremi[0] if estremi is not None else -1
    if idx >= 0:
        prima = reason[:idx].rstrip()
        dopo = reason[idx:]
    else:
        prima = reason.rstrip()
        dopo = ""
    if prima and not prima.endswith("."):
        prima += "."
    return " ".join(parte for parte in (prima, frase, dopo) if parte)


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

    - budget: somma durate + trasferimenti stimati <= tempo disponibile
      (`compose_itinerary` passa il budget EFFETTIVO, già troncato alla
      mezzanotte da `_minuti_alla_mezzanotte`);
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
    tracce_per_luogo: dict[str, list[tuple[datetime, tuple[str, ...]]]] | None = None,
    adesso: datetime | None = None,
    *,
    vocabolario: VocabolarioTemi,
) -> list[ItineraryStop]:
    """Trasforma i candidati scelti in tappe con orari progressivi e `reason`.

    Ogni tappa DEVE avere un `reason` non vuoto (spiegabilità obbligatoria):
    lo compone `reason_fn` a partire dalle connessioni del grafo e dai segnali
    rilevanti per quella tappa.

    Bagliore (`rules.frase_bagliore`): se `tracce_per_luogo` ha tracce per il
    `place_id` della tappa, il MOTORE aggiunge in modo deterministico una
    frase DOPO `reason_fn` (che riceve esattamente gli stessi argomenti di
    sempre: la frase non passa mai dall'LLM) e PRIMA della disclosure partner,
    che resta l'ultima frase. Le tappe sono GIÀ scelte: il bagliore non
    decide quali, quante né in che ordine. `None`/vuoto o `adesso=None` ->
    nessuna frase, `reason` identico a prima.

    Una sola frase per luogo per itinerario: se più tappe condividono lo
    stesso `place_id` (fino a 2, `_seleziona_tappe`), la frase va SOLO sulla
    prima in ordine di tappa; le successive dello stesso luogo hanno il
    `reason` senza frase (ripeterla sarebbe rumore, non spiegazione).

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    luoghi_con_frase: set[str] = set()
    for i, cand in enumerate(selezionati):
        if i > 0:
            orario = _somma_minuti(orario, stima_trasferimento_min(cand.distanza_m))
        segnali = segnali_rilevanti(cand, signal, vocabolario=vocabolario)
        reason = reason_fn(cand, profile, segnali)
        place_id = cand.experience.place_id
        if tracce_per_luogo and adesso is not None and place_id not in luoghi_con_frase:
            tracce = tracce_per_luogo.get(place_id)
            if tracce:
                frase = frase_bagliore(tracce, adesso)
                if frase:
                    luoghi_con_frase.add(place_id)
                    reason = _con_bagliore(reason, cand, frase)
        # Mai un reason vuoto: se reason_fn avesse prodotto solo una frase
        # "Offerta da" ormai senza partner, resta il suo testo.
        reason = _con_disclosure(reason, cand) or reason
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


def _minuti_usati_permanenti(selezionati: Sequence[GraphCandidate]) -> int:
    """Budget consumato dalle tappe permanenti scelte: SOMMA delle durate più
    il trasferimento stimato (`stima_trasferimento_min`) per ogni tappa dopo
    la prima — lo stesso identico conteggio di `_seleziona_tappe`. È anche il
    costo con cui l'adattamento verifica una sostituzione contro il budget.

    È una somma, mai una differenza di orari: gli `arrivo` sono `time` senza
    data e oltre la mezzanotte ripartono da 00:00, quindi una differenza
    diventerebbe negativa e le tappe in coda sforerebbero il budget."""
    totale = 0
    for i, cand in enumerate(selezionati):
        if i > 0:
            totale += stima_trasferimento_min(cand.distanza_m)
        totale += cand.experience.durata_min
    return totale


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
    minuti_usati: int,
    *,
    tempo_disponibile_min: int,
    vocabolario: VocabolarioTemi,
) -> tuple[list[ItineraryStop], int]:
    """Aggiunge, IN CODA, le tappe fluttuanti pertinenti — mai una
    sostituzione (le tappe 1-4 restano esattamente come composte). Rispetta
    il budget di tempo residuo: se non c'è spazio, la tappa fluttuante NON
    si aggiunge — mai forzata oltre `tempo_disponibile_min`, il budget
    EFFETTIVO (dichiarato troncato alla mezzanotte) che passa
    `compose_itinerary`: così nessuna tappa in coda finisce oltre le 24:00.

    Ogni tappa fluttuante costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessuna
    `distanza_m` nota per un segnale, stessa stima prudente già usata
    altrove per una distanza sconosciuta) + `DURATA_TAPPA_FLUTTUANTE_MIN`
    (una tappa "breve" per definizione).

    `minuti_usati` è il budget già consumato da `stops`, come SOMMA di
    durate e trasferimenti (`_minuti_usati_permanenti`), mai ricavato dagli
    orari: oltre la mezzanotte una differenza di `time` sarebbe negativa.
    Restituisce le tappe e il budget aggiornato, che il chiamante passa a
    `_aggiungi_tappe_eventi_promossi` (budget condiviso). `orario_corrente`
    riparte invece da `stops[-1]`: serve solo a dare l'`arrivo`.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    pertinenti = segnali_fluttuanti_pertinenti(
        signal.eventi_attivi, profile, vocabolario=vocabolario
    )
    if not pertinenti:
        return stops, minuti_usati

    place_nomi = {c.experience.place_id: c.place_nome for c in candidates}

    if stops:
        orario_corrente = _somma_minuti(stops[-1].arrivo, stops[-1].durata_min)
    else:
        orario_corrente = signal.ora

    nuove_tappe = list(stops)
    for segnale in pertinenti:
        costo = TEMPO_TRASFERIMENTO_DEFAULT_MIN + DURATA_TAPPA_FLUTTUANTE_MIN
        if minuti_usati + costo > tempo_disponibile_min:
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

    return nuove_tappe, minuti_usati


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


# `temi_leggibili` (resa leggibile dei temi grezzi nel `reason`) vive in
# `rules.py`: la usano sia `_reason_evento_promosso` qui sotto sia
# `rules.frase_bagliore` — un solo punto, nessuna copia.


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
        f"Presso {place_nome} si ripete qualcosa legato a {temi_leggibili(evento.temi)}, "
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
    minuti_usati: int,
    tempo_disponibile_min: int,
    data_visita: date | None,
    vocabolario: VocabolarioTemi,
) -> list[ItineraryStop]:
    """Aggiunge, IN CODA, le tappe degli eventi promossi pertinenti — mai una
    sostituzione (le tappe 1-4 e le eventuali tappe fluttuanti restano
    esattamente come composte). Rispetta il budget di tempo residuo: se non
    c'è spazio, la tappa NON si aggiunge — mai forzata oltre
    `tempo_disponibile_min`, il budget EFFETTIVO (dichiarato troncato alla
    mezzanotte) che passa `compose_itinerary`.

    Ogni tappa-evento costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessuna
    `distanza_m` nota per un `:Evento`, stessa stima prudente già usata
    altrove per una distanza sconosciuta) + `DURATA_TAPPA_EVENTO_MIN`.

    `minuti_usati` (keyword-only, obbligatorio) è il budget già consumato da
    `stops` — tappe permanenti più eventuali tappe fluttuanti — come SOMMA
    di durate e trasferimenti, quello restituito da
    `_aggiungi_tappe_fluttuanti`: così il budget condiviso continua
    correttamente qualunque coda sia già stata prodotta. Non è mai ricavato
    dagli orari: gli `arrivo` sono `time` senza data e oltre la mezzanotte
    una differenza sarebbe negativa. `orario_corrente` riparte invece da
    `stops[-1]`: serve solo a dare l'`arrivo` alla tappa.

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
    `reason`. Nessun chiamante può ometterla senza accorgersene.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    pertinenti = eventi_promossi_pertinenti(
        eventi_promossi, profile, data_visita, vocabolario=vocabolario
    )
    if not pertinenti or data_visita is None:
        return stops

    place_nomi = {c.experience.place_id: c.place_nome for c in candidates}

    if stops:
        orario_corrente = _somma_minuti(stops[-1].arrivo, stops[-1].durata_min)
    elif ora_inizio is not None:
        orario_corrente = ora_inizio
    else:
        return stops

    nuove_tappe = list(stops)
    for evento in pertinenti:
        costo = TEMPO_TRASFERIMENTO_DEFAULT_MIN + DURATA_TAPPA_EVENTO_MIN
        if minuti_usati + costo > tempo_disponibile_min:
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
    tracce_per_luogo: dict[str, list[tuple[datetime, tuple[str, ...]]]] | None = None,
    *,
    adesso: datetime | None = None,
    vocabolario: VocabolarioTemi,
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

    `tracce_per_luogo` (`place_id` -> tracce `(creato_il, temi)` del ledger,
    lette dal chiamante) aggiunge al `reason` delle SOLE tappe permanenti già
    scelte al passo 4 la frase del bagliore (`rules.frase_bagliore`: soglia
    `rules.SOGLIA_BAGLIORE` sul bagliore RECENTE, `rules.bagliore_recente`),
    prima della disclosure partner, al più UNA volta per luogo (la prima
    tappa di quel `place_id`). Non tocca i passi 1-3 né 5-6: nessuno score,
    nessuna selezione, nessun ordine cambia; tappe fluttuanti ed eventi
    promossi non ricevono la frase. `None`/vuoto -> comportamento invariato,
    bit per bit. È l'ultimo parametro posizionale, per non spostare le
    chiamate posizionali esistenti.

    `adesso` (keyword-only, dopo `tracce_per_luogo`) è l'istante su cui si
    calcola il decadimento delle tracce: il chiamante (BFF) può passarlo per
    avere un solo orologio iniettabile. Se `None` e `tracce_per_luogo` non è
    vuoto, è `datetime.now(UTC)`, calcolato UNA volta qui e passato giù.

    `vocabolario` (keyword-only, obbligatorio): vocabolario dei temi della
    città, dato del dataset; il motore non ne ha uno proprio.
    Inoltrato a ogni regola che legge i temi; se `score_fn` è `None` lo score
    di default è `rules.calcola_score` legato a questo vocabolario.

    Determinismo totale: a parità di score l'ordine è per `experience_id`.
    Due profili diversi possono produrre itinerari diversi — è il criterio
    d'accettazione centrale della wave.
    """
    fn = reason_fn or _fallback_reason
    score: ScoreFn = score_fn or partial(calcola_score, vocabolario=vocabolario)
    profile = ctx.profile

    ammessi = [
        c
        for c in candidates
        if passa_filtri_duri(c, profile, ctx.signal, ctx.luoghi_gia_visti)
    ]
    valutati = _ordina_per_score(ammessi, profile, ctx.signal, score)
    # Tetto della giornata: l'itinerario è una sessione nella stessa giornata.
    # Il budget EFFETTIVO è il dichiarato troncato alla mezzanotte e vale per
    # la selezione e per entrambe le code. Poiché gli arrivi partono da
    # `signal.ora` e avanzano esattamente della somma conteggiata nel budget,
    # nessuna tappa può finire oltre le 24:00. Le tappe che non entrano per
    # il tetto non vanno in `tappe_escluse`: non sono mai state proposte.
    budget_dichiarato = profile.tempo_disponibile_min
    budget_effettivo = min(budget_dichiarato, _minuti_alla_mezzanotte(ctx.signal.ora))
    selezionati = _seleziona_tappe(valutati, budget_effettivo)
    if adesso is None and tracce_per_luogo:
        adesso = datetime.now(UTC)
    stops = _costruisci_stops(
        selezionati,
        profile,
        ctx.signal,
        fn,
        tracce_per_luogo,
        adesso,
        vocabolario=vocabolario,
    )
    # Budget già consumato: SOMMA di durate e trasferimenti (stesso conteggio
    # di `_seleziona_tappe`), portata attraverso le due code — mai ricavata
    # dagli orari, che oltre la mezzanotte ripartono da 00:00.
    minuti_usati = _minuti_usati_permanenti(selezionati)
    stops, minuti_usati = _aggiungi_tappe_fluttuanti(
        stops,
        candidates,
        profile,
        ctx.signal,
        minuti_usati,
        tempo_disponibile_min=budget_effettivo,
        vocabolario=vocabolario,
    )
    stops = _aggiungi_tappe_eventi_promossi(
        stops,
        candidates,
        profile,
        eventi_promossi or [],
        ctx.signal.ora,
        minuti_usati=minuti_usati,
        tempo_disponibile_min=budget_effettivo,
        data_visita=ctx.signal.data,
        vocabolario=vocabolario,
    )

    # Budget registrato nell'itinerario, per l'adattamento. Il contratto lo
    # vuole > 0 (`Itinerary.tempo_disponibile_min`), mentre il profilo
    # ammette 0 (`EmotionalProfile.tempo_disponibile_min`, ge=0): un budget
    # dichiarato di 0 minuti non è rappresentabile e l'itinerario resta
    # SENZA budget (entrambi None, come impone il validatore). Con 0 minuti
    # la composizione non sceglie tappe di durata > 0.
    if budget_dichiarato > 0:
        tempo_disponibile: int | None = budget_dichiarato
        tempo_effettivo: int | None = budget_effettivo
    else:
        tempo_disponibile = None
        tempo_effettivo = None

    return Itinerary(
        person_id=ctx.person_id,
        stops=stops,
        generated_at=datetime.now(),
        adattato_da_segnale=False,
        tempo_disponibile_min=tempo_disponibile,
        tempo_effettivo_min=tempo_effettivo,
    )


def _migliore_alternativa(
    candidates: list[GraphCandidate],
    signal: Signal,
    profile: EmotionalProfile,
    esclusi: set[str],
    richiede_accessibile: bool,
    solo_al_chiuso: bool,
    max_affollamento: float,
    *,
    entra_nel_budget: Callable[[GraphCandidate], bool] | None = None,
    vocabolario: VocabolarioTemi,
) -> GraphCandidate | None:
    """Migliore candidato non già usato che rispetta i vincoli del segnale.

    Deterministico: tie-break per `experience_id`.

    I vincoli DURI vengono da un solo punto, `rules.passa_filtri_duri`
    (accessibilità richiesta dal profilo, affollamento critico, partner con
    abbonamento NON attivo, orari di apertura): la stessa funzione usata in
    composizione iniziale, così una sostituzione in adattamento non può MAI
    reintrodurre ciò che la composizione esclude. L'adattamento non ha luoghi
    già visti da passare (lista vuota).

    A questi si aggiungono SOLO i vincoli specifici dell'adattamento:
    - `esclusi`: esperienze già presenti nell'itinerario;
    - `richiede_accessibile`: regola CONSERVATIVA per tappa quando il
      profilo è assente (una tappa accessibile si sostituisce solo con una
      accessibile) — l'accessibilità non viene mai degradata;
    - `solo_al_chiuso`: con la pioggia, solo esperienze al chiuso;
    - affollamento > `max_affollamento`: luogo scorrevole. La soglia di
      adattamento (0.7) è più severa di quella critica di
      `passa_filtri_duri` (0.8) e la include;
    - `entra_nel_budget`: predicato sul TEMPO (durata e trasferimento
      dell'alternativa, nient'altro) costruito da `adapt_itinerary`; un
      candidato che sforerebbe il budget non è ammesso, e vince il migliore
      tra quelli che stanno nel budget. `None` = nessun vincolo di budget
      (itinerario senza budget). Il predicato non legge partner né prezzo:
      il vincolo di tempo vale identico per ogni candidato.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    ammessi: list[GraphCandidate] = []
    for c in candidates:
        if not passa_filtri_duri(c, profile, signal, []):
            continue
        e = c.experience
        if e.id in esclusi:
            continue
        if richiede_accessibile and not e.accessibile:
            continue
        if solo_al_chiuso and not e.al_chiuso:
            continue
        if signal.affollamento.get(e.place_id, 0.0) > max_affollamento:
            continue
        if entra_nel_budget is not None and not entra_nel_budget(c):
            continue
        ammessi.append(c)
    if not ammessi:
        return None
    ammessi.sort(
        key=lambda c: (
            -calcola_score(c, profile, signal, vocabolario=vocabolario),
            c.experience.id,
        )
    )
    return ammessi[0]


def adapt_itinerary(
    itinerary: Itinerary,
    signal: Signal,
    candidates: list[GraphCandidate],
    profile: EmotionalProfile | None = None,
    reason_fn: ReasonFn | None = None,
    adapt_reason_fn: AdaptReasonFn | None = None,
    *,
    vocabolario: VocabolarioTemi,
) -> Itinerary:
    """Riscrive SOLO ciò che il nuovo segnale tocca.

    In ordine:
    1. pioggia: le tappe `al_chiuso=False` sono sostituite dalla migliore
       alternativa `al_chiuso=True` non già presente; affollamento > soglia
       sul luogo di una tappa: sostituzione con alternativa in luogo
       scorrevole (distribuzione dei flussi). Un'alternativa entra solo se
       l'itinerario con la sostituzione resta nel budget (vedi sotto). Senza
       alternativa ammissibile la tappa resta, con esito
       `MANTENUTA_SENZA_ALTERNATIVA` e una frase in coda al `reason`.
    2. stanchezza > soglia: taglia le tappe in coda oltre ~2/3 del tempo
       originale (il benessere conta più del numero di tappe); le tappe
       tolte vanno in `tappe_escluse` (`TAGLIATA_STANCHEZZA`).
    3. tetto della giornata: con gli arrivi ricalcolati da `signal.ora`, le
       tappe che finirebbero oltre le 24:00 escono e vanno in
       `tappe_escluse` (`TAGLIATA_TETTO_GIORNATA`). Vale sempre, anche per
       un itinerario senza budget.

    Budget: `itinerary.tempo_disponibile_min` / `tempo_effettivo_min` sono
    ricopiati invariati. Limite delle sostituzioni = min(tempo_effettivo_min,
    minuti alla mezzanotte da `signal.ora`); costo = somma di durate e
    trasferimenti (`_minuti_usati_permanenti`), mai differenze di orari.
    Itinerario SENZA budget (`tempo_effettivo_min is None`, JSON precedenti
    al campo): nessun vincolo di budget sulle sostituzioni, comportamento
    precedente alla wave "adattamento" (`docs/LIMITI.md`, "Itinerario senza
    budget: l'adattamento non vincola le sostituzioni").

    Esito: ogni tappa presente ha `esito_adattamento` valorizzato
    (`NON_TOCCATA`, `SOSTITUITA`, `MANTENUTA_SENZA_ALTERNATIVA`), riferito
    SOLO a questo segnale. `adattato_da_segnale` è True se e solo se almeno
    una tappa è sostituita o tagliata. Se nessuna lo è, gli arrivi restano
    quelli ricevuti e cambiano solo `reason` ed esito; altrimenti gli arrivi
    sono ricalcolati da `signal.ora`. Le tappe non toccate conservano il
    `reason` ricevuto (tolta soltanto un'eventuale frase di esito di un
    adattamento precedente, che descriveva un altro segnale); se la tappa ha
    un candidato reale, la disclosure partner è ricalcolata dal candidato
    corrente (`_con_disclosure`), una sola e sempre ultima. Le tappe senza
    candidato restano intatte (`_reason_finale`).

    `tappe_escluse` si accumula: parte da `itinerary.tappe_escluse` e
    aggiunge le nuove, una sola voce per `experience_id` (vince l'esito più
    recente). Un'esperienza tornata tra le tappe non è più esclusa.

    `vocabolario` (keyword-only, obbligatorio): vocabolario dei temi della
    città, dato del dataset; il motore non ne ha uno proprio.
    """
    fn = reason_fn or _fallback_reason
    adapt_fn = adapt_reason_fn or _fallback_adapt_reason
    per_id = {c.experience.id: c for c in candidates}
    # Accessibilità: se il profilo la richiede, vale sempre. Se il profilo è
    # assente (`AdaptRequest.profile` è opzionale), regola CONSERVATIVA per tappa:
    # una tappa accessibile può essere sostituita SOLO da una accessibile.
    base_accessibile = profile.accessibilita_richiesta if profile is not None else False
    profilo_effettivo = profile or _profilo_neutro()
    minuti_mezzanotte = _minuti_alla_mezzanotte(signal.ora)

    # Limite di budget per le sostituzioni.
    limite_budget: int | None
    if itinerary.tempo_effettivo_min is None:
        # Itinerario SENZA budget (precedente al campo): nessun vincolo di
        # budget sulle sostituzioni, scelta ESPLICITA e documentata in
        # docs/LIMITI.md. Il tetto della giornata (passo 3) vale comunque.
        limite_budget = None
    else:
        limite_budget = min(itinerary.tempo_effettivo_min, minuti_mezzanotte)

    # Stato corrente: un candidato per tappa ricevuta, con reason ed esito
    # decisi. Di partenza ogni tappa è NON_TOCCATA, col reason ricevuto
    # ripulito dalla frase di un esito precedente.
    correnti: list[_CandidatoConReason] = []
    for stop in itinerary.stops:
        reason_base = _senza_frase_esito(stop.reason)
        cand = per_id.get(stop.experience_id)
        if cand is None:
            # Non conosciamo questa esperienza tra i candidati (tappa
            # fluttuante, evento promosso, esperienza sparita): la lasciamo
            # intatta invece di riscrivere al buio.
            correnti.append(_stub_da_stop(stop, reason_base))
        else:
            correnti.append(
                _marca_reason(cand, reason_base, EsitoAdattamento.NON_TOCCATA, stop.experience_id)
            )

    usati = {s.experience_id for s in itinerary.stops}
    sostituite = False

    # 1. Sostituzioni (pioggia / affollamento).
    for i, stop in enumerate(itinerary.stops):
        cand = per_id.get(stop.experience_id)
        if cand is None:
            continue

        e = cand.experience
        place_affollato = (
            signal.affollamento.get(e.place_id, 0.0) > SOGLIA_AFFOLLAMENTO_ADATTAMENTO
        )
        piove_e_aperto = signal.meteo == "pioggia" and not e.al_chiuso

        if not (piove_e_aperto or place_affollato):
            continue  # tappa non toccata dal segnale

        entra_nel_budget: Callable[[GraphCandidate], bool] | None
        if limite_budget is None:
            entra_nel_budget = None  # itinerario senza budget: vedi sopra
        else:
            entra_nel_budget = partial(
                _sostituzione_nel_budget, correnti=correnti, indice=i, limite=limite_budget
            )

        richiede_accessibile = base_accessibile or (profile is None and e.accessibile)
        alt = _migliore_alternativa(
            candidates=candidates,
            signal=signal,
            profile=profilo_effettivo,
            esclusi=usati,
            richiede_accessibile=richiede_accessibile,
            solo_al_chiuso=piove_e_aperto,
            max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
            entra_nel_budget=entra_nel_budget,
            vocabolario=vocabolario,
        )
        if alt is None:
            # Nessuna alternativa ammissibile (vincoli duri, segnale, budget):
            # la tappa resta e lo dice, prima della disclosure partner.
            frase = _frase_esito(
                EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
                motivo="pioggia" if piove_e_aperto else "affollamento",
                luogo=cand.place_nome,
            )
            correnti[i] = _marca_reason(
                cand,
                _con_bagliore(correnti[i].reason_deciso or stop.reason, cand, frase),
                EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
                stop.experience_id,
            )
            continue

        usati.discard(e.id)
        usati.add(alt.experience.id)
        motivo = alt.connessioni[0] if alt.connessioni else alt.experience.titolo
        segnale = "la pioggia" if piove_e_aperto else f"l'affollamento a {cand.place_nome}"
        alt_reason = adapt_fn(motivo, segnale)
        correnti[i] = _marca_reason(
            alt, alt_reason, EsitoAdattamento.SOSTITUITA, stop.experience_id
        )
        sostituite = True

    nuove_escluse: list[TappaEsclusa] = []

    # 2. Stanchezza alta: taglia la coda oltre ~2/3 del tempo originale.
    if signal.stanchezza > SOGLIA_STANCHEZZA_ALTA:
        tenuti = _taglia_per_stanchezza(itinerary, correnti)
        nuove_escluse.extend(
            _escludi(c, EsitoAdattamento.TAGLIATA_STANCHEZZA) for c in correnti[len(tenuti):]
        )
        correnti = tenuti

    # 3. Tetto della giornata, sugli arrivi ricalcolati da `signal.ora`.
    entro = _entro_la_giornata(correnti, minuti_mezzanotte)
    nuove_escluse.extend(
        _escludi(c, EsitoAdattamento.TAGLIATA_TETTO_GIORNATA) for c in correnti[len(entro):]
    )
    correnti = entro

    cambiato = sostituite or bool(nuove_escluse)

    if cambiato:
        stops = _ricostruisci_stops(
            correnti, profilo_effettivo, signal, fn, vocabolario=vocabolario
        )
    else:
        # Nessuna tappa sostituita o tagliata: arrivi INVARIATI, cambiano
        # solo reason ed esito (stessa lunghezza e stesso ordine).
        stops = [
            stop.model_copy(
                update={
                    "reason": _reason_finale(
                        c, c.reason_deciso or stop.reason, profilo_effettivo, signal, fn,
                        vocabolario=vocabolario,
                    ),
                    "esito_adattamento": c.esito_deciso,
                }
            )
            for stop, c in zip(itinerary.stops, correnti, strict=True)
        ]

    return Itinerary(
        person_id=itinerary.person_id,
        stops=stops,
        generated_at=datetime.now() if cambiato else itinerary.generated_at,
        adattato_da_segnale=cambiato,
        tempo_disponibile_min=itinerary.tempo_disponibile_min,
        tempo_effettivo_min=itinerary.tempo_effettivo_min,
        tappe_escluse=_unisci_escluse(itinerary.tappe_escluse, nuove_escluse, stops),
    )


# ---------------------------------------------------------------------------
# Supporto all'adattamento
# ---------------------------------------------------------------------------


def _profilo_neutro() -> EmotionalProfile:
    """Profilo neutro usato quando `AdaptRequest.profile` è assente:
    serve solo a ordinare le alternative, non reintroduce preferenze. Il suo
    `tempo_disponibile_min` NON è mai usato come budget: il budget
    dell'adattamento viene dall'itinerario (`Itinerary.tempo_effettivo_min`)."""
    return EmotionalProfile(
        curiosita=0.5,
        contemplazione=0.5,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=10_000,
    )


# --- Esito dell'adattamento: UNICO punto da cui nasce la frase --------------

_FRASE_MANTENUTA_PIOGGIA = (
    "Con la pioggia non c'è un'alternativa al coperto compatibile con questo percorso "
    "e con il tempo a disposizione: la tappa resta in programma."
)
_PREFISSO_MANTENUTA_AFFOLLAMENTO = "C'è molta gente a "
_SUFFISSO_MANTENUTA_AFFOLLAMENTO = (
    ", ma non c'è un'alternativa più tranquilla compatibile con questo percorso "
    "e con il tempo a disposizione: la tappa resta in programma."
)
_FRASE_TAGLIATA_STANCHEZZA = "Tolta per la stanchezza: meglio una giornata più leggera."
_FRASE_TAGLIATA_TETTO = (
    "Non c'è più tempo oggi per questa tappa: la giornata finisce a mezzanotte."
)

#: Riconosce la frase di affollamento qualunque sia il luogo. Il luogo è
#: "temperato": non può contenere di nuovo il prefisso, così la corrispondenza
#: parte dall'ultima occorrenza utile e non inghiotte testo del reason.
_RE_MANTENUTA_AFFOLLAMENTO = re.compile(
    " ?"
    + re.escape(_PREFISSO_MANTENUTA_AFFOLLAMENTO)
    + "(?:(?!"
    + re.escape(_PREFISSO_MANTENUTA_AFFOLLAMENTO)
    + ").)*?"
    + re.escape(_SUFFISSO_MANTENUTA_AFFOLLAMENTO),
    re.DOTALL,
)


def _frase_esito(
    esito: EsitoAdattamento,
    *,
    motivo: Literal["pioggia", "affollamento"] | None = None,
    luogo: str = "",
) -> str | None:
    """Frase in italiano che racconta l'esito dell'adattamento di una tappa.

    UNICA funzione da cui nascono le frasi di esito, così campo e testo non
    possono divergere:
    - `MANTENUTA_SENZA_ALTERNATIVA`: frase della pioggia (anche se il luogo è
      pure affollato) o dell'affollamento a `luogo`; va in coda al `reason`,
      prima della disclosure partner;
    - `TAGLIATA_STANCHEZZA` / `TAGLIATA_TETTO_GIORNATA`: `reason` della
      `TappaEsclusa`;
    - `NON_TOCCATA` / `SOSTITUITA`: nessuna frase (`None`); la sostituita ha
      il proprio `reason` di sostituzione."""
    if esito is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA:
        if motivo == "pioggia":
            return _FRASE_MANTENUTA_PIOGGIA
        return f"{_PREFISSO_MANTENUTA_AFFOLLAMENTO}{luogo}{_SUFFISSO_MANTENUTA_AFFOLLAMENTO}"
    if esito is EsitoAdattamento.TAGLIATA_STANCHEZZA:
        return _FRASE_TAGLIATA_STANCHEZZA
    if esito is EsitoAdattamento.TAGLIATA_TETTO_GIORNATA:
        return _FRASE_TAGLIATA_TETTO
    return None


def _senza_frase_esito(reason: str) -> str:
    """Toglie da un `reason` la frase di un esito precedente (mantenuta senza
    alternativa): l'esito descrive SOLO l'ultimo segnale, e un secondo
    adattamento non deve duplicarla né lasciarla su una tappa non più
    toccata. Se non c'è nessuna frase, il `reason` torna identico."""
    pulito = reason.replace(" " + _FRASE_MANTENUTA_PIOGGIA, "").replace(
        _FRASE_MANTENUTA_PIOGGIA, ""
    )
    pulito = _RE_MANTENUTA_AFFOLLAMENTO.sub("", pulito)
    if pulito == reason:
        return reason
    return pulito.strip() or reason


# --- Candidati con reason/esito decisi --------------------------------------


class _CandidatoConReason(GraphCandidate):
    """Candidato con `reason` ed esito già decisi (interno all'adapt).

    `id_originale` è l'`experience_id` della tappa ricevuta che questo
    candidato occupa: se la tappa viene tagliata, in `tappe_escluse` finisce
    la tappa che il visitatore aveva, non la sua eventuale sostituta."""

    reason_deciso: str | None = None
    esito_deciso: EsitoAdattamento | None = None
    id_originale: str = ""
    #: Tappa ricevuta la cui esperienza non è tra i candidati: il suo `reason`
    #: resta intatto, disclosure compresa ("non riscrivere al buio").
    senza_candidato: bool = False


def _marca_reason(
    cand: GraphCandidate, reason: str, esito: EsitoAdattamento, id_originale: str
) -> _CandidatoConReason:
    dati = cand.model_dump()
    for campo in ("reason_deciso", "esito_deciso", "id_originale", "senza_candidato"):
        dati.pop(campo, None)
    return _CandidatoConReason(
        **dati, reason_deciso=reason, esito_deciso=esito, id_originale=id_originale
    )


def _stub_da_stop(stop: ItineraryStop, reason: str) -> _CandidatoConReason:
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
        reason_deciso=reason,
        esito_deciso=EsitoAdattamento.NON_TOCCATA,
        id_originale=stop.experience_id,
        senza_candidato=True,
    )


def _sostituzione_nel_budget(
    alternativa: GraphCandidate,
    *,
    correnti: Sequence[GraphCandidate],
    indice: int,
    limite: int,
) -> bool:
    """Vero se l'itinerario con `alternativa` al posto della tappa `indice`
    resta entro `limite` minuti. Costo = somma di durate e trasferimenti
    (`_minuti_usati_permanenti`, lo stesso conteggio della composizione),
    mai differenze di orari. Legge solo durata e distanza: nessun partner,
    nessun prezzo."""
    ipotesi = [*correnti[:indice], alternativa, *correnti[indice + 1 :]]
    return _minuti_usati_permanenti(ipotesi) <= limite


def _taglia_per_stanchezza(
    itinerary: Itinerary, correnti: list[_CandidatoConReason]
) -> list[_CandidatoConReason]:
    """Mantiene le tappe di testa entro ~2/3 del tempo originale (prefisso).

    Le tappe di coda sono le meno affini (l'itinerario è ordinato per score in
    composizione): tagliarle riduce lo sforzo senza sacrificare il meglio."""
    durata_originale = sum(s.durata_min for s in itinerary.stops)
    limite = int(durata_originale * 2 / 3)
    tenuti: list[_CandidatoConReason] = []
    tempo = 0
    for cand in correnti:
        prossimo = tempo + cand.experience.durata_min
        if tenuti and prossimo > limite:
            break
        tenuti.append(cand)
        tempo = prossimo
    return tenuti or correnti[:1]


def _entro_la_giornata(
    correnti: list[_CandidatoConReason], minuti_alla_mezzanotte: int
) -> list[_CandidatoConReason]:
    """Prefisso delle tappe che, con gli arrivi ricalcolati da `signal.ora`
    (stessa progressione di `_ricostruisci_stops`), finiscono entro le 24:00.
    La fine di ogni tappa avanza in modo monotono, quindi le tappe fuori dal
    tetto sono sempre una coda."""
    tenuti: list[_CandidatoConReason] = []
    for cand in correnti:
        if _minuti_usati_permanenti([*tenuti, cand]) > minuti_alla_mezzanotte:
            break
        tenuti.append(cand)
    return tenuti


def _esclusa_canonica(experience_id: str, esito: EsitoAdattamento) -> TappaEsclusa:
    """`TappaEsclusa` col `reason` del motore, ricavato SOLO dall'esito
    (`_frase_esito`): nessun testo libero arrivato dal client sopravvive."""
    frase = _frase_esito(esito)
    if frase is None:
        raise ValueError(f"esito {esito.value!r} non è un esito di taglio")
    return TappaEsclusa(experience_id=experience_id, esito=esito, reason=frase)


def _escludi(cand: _CandidatoConReason, esito: EsitoAdattamento) -> TappaEsclusa:
    return _esclusa_canonica(cand.id_originale or cand.experience.id, esito)


def _unisci_escluse(
    precedenti: list[TappaEsclusa],
    nuove: list[TappaEsclusa],
    stops: list[ItineraryStop],
) -> list[TappaEsclusa]:
    """Accumula le tappe escluse tra adattamenti: una sola voce per
    `experience_id`, vince la più recente (che va in fondo). Nessun tetto di
    lunghezza. Un'esperienza tornata tra le tappe non è più esclusa.

    Il `reason` di OGNI voce è rigenerato dall'esito (`_esclusa_canonica`):
    le esclusioni ricevute dal client portano un testo libero, e il testo
    restituito dev'essere sempre quello del motore."""
    unite: dict[str, TappaEsclusa] = {}
    for tappa in [*precedenti, *nuove]:
        unite.pop(tappa.experience_id, None)
        unite[tappa.experience_id] = _esclusa_canonica(tappa.experience_id, tappa.esito)
    presenti = {s.experience_id for s in stops}
    return [t for t in unite.values() if t.experience_id not in presenti]


def _reason_finale(
    cand: _CandidatoConReason,
    reason: str,
    profile: EmotionalProfile,
    signal: Signal,
    reason_fn: ReasonFn,
    *,
    vocabolario: VocabolarioTemi,
) -> str:
    """`reason` finale di una tappa adattata.

    - Tappa senza candidato (stub): `reason` ricevuto INTATTO, disclosure
      compresa: non si riscrive al buio.
    - Tappa con candidato reale: disclosure ricalcolata dal candidato
      corrente (`_con_disclosure`: una sola, sempre ultima). Il resto del
      testo è quello deciso (ricevuto dal client per le tappe mantenute o non
      toccate, docs/LIMITI.md). Se il `reason` manca, o resta vuoto dopo aver
      tolto una disclosure non più valida, lo compone `reason_fn`."""
    if cand.senza_candidato:
        return reason
    finale = _con_disclosure(reason, cand) if reason else ""
    if not finale:
        segnali = segnali_rilevanti(cand, signal, vocabolario=vocabolario)
        finale = _con_disclosure(reason_fn(cand, profile, segnali), cand)
    return finale


def _ricostruisci_stops(
    correnti: list[_CandidatoConReason],
    profile: EmotionalProfile,
    signal: Signal,
    reason_fn: ReasonFn,
    *,
    vocabolario: VocabolarioTemi,
) -> list[ItineraryStop]:
    """Ricalcola orari progressivi da `signal.ora` conservando `reason` ed
    esito già decisi, e componendo via `reason_fn` un `reason` mancante.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    for i, cand in enumerate(correnti):
        if i > 0:
            orario = _somma_minuti(orario, stima_trasferimento_min(cand.distanza_m))
        reason = _reason_finale(
            cand, cand.reason_deciso or "", profile, signal, reason_fn, vocabolario=vocabolario
        )
        stops.append(
            ItineraryStop(
                experience_id=cand.experience.id,
                arrivo=orario,
                durata_min=cand.experience.durata_min,
                reason=reason,
                esito_adattamento=cand.esito_deciso or EsitoAdattamento.NON_TOCCATA,
            )
        )
        orario = _somma_minuti(orario, cand.experience.durata_min)
    return stops
