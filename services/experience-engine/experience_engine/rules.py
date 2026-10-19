"""Regole pure dell'AI Experience Engine — costanti, filtri e scoring.

Ogni funzione qui è PURA e deterministica: stessi input, stesso output, nessun
I/O, nessun accesso a grafo o RAG. È il cuore verificabile del "brevetto":
i vincoli etici vivono in UN SOLO PUNTO, così un'amministrazione può auditarli.

Il grafo PROPONE (candidati e connessioni), il recommender ORDINA, la RAG
RACCONTA: nessuno di loro sceglie. Sceglie l'Experience Engine applicando
queste regole. Per questo lo scoring NON legge mai `partner_id` né
`prezzo_eur`: la visibilità non è acquistabile, e un vincolo lo si verifica
solo dove è concentrato.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from datetime import UTC, date, datetime, time, timedelta
from typing import Final

from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    SegnaleFluttuante,
    Signal,
    VocabolarioTemi,
    rientra_in_orario,
    segnale_fluttuante_ammissibile,
)

# ---------------------------------------------------------------------------
# Costanti nominate
# ---------------------------------------------------------------------------

#: Sopra questa soglia un luogo è considerato criticamente affollato ed è
#: ESCLUSO in composizione: distribuire i flussi è un vincolo etico duro, non
#: una preferenza. Sotto soglia agisce comunque una penalità proporzionale.
SOGLIA_AFFOLLAMENTO_CRITICO = 0.8

#: In fase di adattamento una tappa il cui luogo supera questa soglia viene
#: riscritta verso un'alternativa più scorrevole (distribuzione dei flussi).
SOGLIA_AFFOLLAMENTO_ADATTAMENTO = 0.7

#: Sopra questa soglia di stanchezza il motore preferisce tappe brevi e, in
#: adattamento, accorcia l'itinerario: il benessere della persona conta più
#: della quantità di tappe.
SOGLIA_STANCHEZZA_ALTA = 0.7

#: Minuti di trasferimento stimati quando manca `distanza_m`.
TEMPO_TRASFERIMENTO_DEFAULT_MIN = 10

#: Velocità di cammino stimata (m/min) per convertire `distanza_m` in minuti.
VELOCITA_CAMMINO_M_MIN = 80

#: Durata (min) oltre la quale una tappa è considerata "lunga" ai fini del
#: bonus/malus di stanchezza.
DURATA_LUNGA_MIN = 90

#: Tolleranza di score entro cui si preferisce una tappa a tema diverso dalla
#: precedente (diversificazione), senza tradire l'ordinamento per affinità.
TOLLERANZA_DIVERSITA = 0.05

#: Durata (min) di una tappa aggiunta da un segnale fluttuante: per
#: definizione "breve" (un violinista in piazza non è una visita guidata),
#: quindi una costante della FEATURE, non un campo dichiarato dal segnale —
#: `SegnaleFluttuante` resta minimale (`docs/LIMITI.md` spiega la scelta).
DURATA_TAPPA_FLUTTUANTE_MIN = 15

#: Durata (min) di una tappa aggiunta da un `:Evento` PROMOSSO
#: (`contracts.EventoPromosso`, Fase 3). Stessa idea di
#: `DURATA_TAPPA_FLUTTUANTE_MIN` sopra: una costante della FEATURE, non un
#: campo dichiarato dall'evento — `EventoPromosso` non porta alcuna durata
#: (solo `ultima_occorrenza`/`cadenza_giorni`, per la finestra temporale:
#: nessuna durata sopravvive alla promozione, verificato).
#: TUNING: valore di PARTENZA, non calibrato su dati reali. La taratura è
#: deliberatamente differita a quando esisterà un `:Evento` promosso vero da
#: osservare; costante gemella (e non riuso diretto di
#: `DURATA_TAPPA_FLUTTUANTE_MIN`) proprio perché i due livelli — "accade ora"
#: e "programmato" — devono poter divergere senza toccarsi a vicenda.
DURATA_TAPPA_EVENTO_MIN = 15

#: Semi-ampiezza della finestra temporale di un `:Evento` PROMOSSO, come
#: FRAZIONE della sua cadenza: la visita è "in finestra" se dista al più
#: `FRAZIONE_FINESTRA_CADENZA * cadenza_giorni` giorni dall'occorrenza attesa
#: più vicina. PROPORZIONALE alla cadenza, mai una finestra fissa in giorni:
#: un evento settimanale ha ±1,05 giorni (≈ ±1), uno mensile (30 g) ±4,5.
#: TUNING: valore di PARTENZA, non calibrato su dati reali — la taratura è
#: deliberatamente differita a quando esisteranno `:Evento` promossi veri da
#: osservare (stesso principio di `K_ORIZZONTE_DORMIENZA` in
#: `urban_memory.frizione_pattern`). La finestra decide SOLO "quando"; "se
#: l'evento è ancora vivo" resta alla frizione (`stato`, filtrato a monte).
FRAZIONE_FINESTRA_CADENZA = 0.15

#: Tolleranza assoluta (giorni) sul confronto col bordo della finestra: il
#: bordo è INCLUSO, ma `k * cadenza_giorni` e `FRAZIONE * cadenza` sono float,
#: quindi un bordo esatto in aritmetica reale (es. cadenza 20/3, semi-ampiezza
#: 1,0) può risultare 0,9999999999 in float. Un miliardesimo di giorno
#: (< 0,1 ms) è irrilevante per la semantica e assorbe l'errore di
#: arrotondamento, invece di un confronto `<=` fragile.
TOLLERANZA_FINESTRA_GIORNI = 1e-9

# --- Pesi dello scoring (documentati: nessuno tocca partner_id/prezzo_eur) ---

W_CONTEMPLAZIONE = 0.30
W_ARTE = 0.30
W_CURIOSITA = 0.20
W_BAMBINI = 0.25
W_METEO = 0.15
W_STANCHEZZA = 0.15
PENALITA_AFFOLLAMENTO = 0.40

def stima_trasferimento_min(distanza_m: int | None) -> int:
    """Minuti di trasferimento tra due tappe.

    Usa `distanza_m` se il grafo l'ha fornita (prossimità reale fra luoghi),
    altrimenti una stima prudente costante. Serve al budget di tempo: un
    itinerario che sfora il tempo disponibile non rispetta la persona."""
    if distanza_m is None:
        return TEMPO_TRASFERIMENTO_DEFAULT_MIN
    if distanza_m <= 0:
        return 0
    return max(1, math.ceil(distanza_m / VELOCITA_CAMMINO_M_MIN))


def affinita_temi(temi: list[str], gruppo: AbstractSet[str]) -> float:
    """Quanto i temi di un'esperienza appartengono a un gruppo (0, 0.5 o 1).

    `gruppo` è un gruppo del vocabolario della città (`VocabolarioTemi`,
    frozenset) o un qualunque insieme di id di Tema.

    Conta le sovrapposizioni, satura a 2: due temi coerenti bastano a dire che
    l'esperienza "parla" a quel tratto; oltre non aggiunge informazione."""
    comuni = sum(1 for t in temi if t in gruppo)
    return min(comuni, 2) / 2.0


def passa_filtri_statici(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    signal: Signal,
    luoghi_gia_visti: list[str],
) -> bool:
    """Vincoli DURI dell'Ethical AI Engine che NON dipendono dall'istante di
    arrivo alla tappa (nessuna eccezione, mai). Sono i filtri 1-4 di
    `passa_filtri_duri`; il filtro 5 (orari) è `aperta_durante`.

    - `accessibilita_richiesta` => solo esperienze `accessibile=True`.
      L'inclusione non è negoziabile: nessuno score può reintrodurre una
      tappa inaccessibile per una persona che ha chiesto accessibilità.
    - Esclude i luoghi già visti: non si ripropone ciò che è già stato vissuto.
    - Esclude i luoghi criticamente affollati (>= soglia): distribuire i flussi
      per non aggravare l'overtourism è un dovere del motore, non un'opzione.
    - Esclude le esperienze di un partner con abbonamento NON attivo. Questa è
      l'UNICA leva commerciale ammessa, ed è un interruttore booleano di
      PRESENZA, non un input dello scoring: la visibilità non è acquistabile,
      quindi un partner o c'è (abbonamento attivo) o non c'è, ma quando c'è
      concorre esattamente come tutti gli altri — il suo punteggio non cambia
      di un bit. Verificato dal booleano denormalizzato `partner_abbonamento_attivo`
      (popolato a monte dal grafo); `calcola_score` non lo legge mai.

    Non legge orari né istanti: la composizione la usa come pre-filtro
    (prima dello scoring) e controlla gli orari slot per slot, all'arrivo.
    """
    esperienza = candidate.experience
    if profile.accessibilita_richiesta and not esperienza.accessibile:
        return False
    if esperienza.place_id in luoghi_gia_visti:
        return False
    if signal.affollamento.get(esperienza.place_id, 0.0) >= SOGLIA_AFFOLLAMENTO_CRITICO:
        return False
    if esperienza.partner_id is not None and not esperienza.partner_abbonamento_attivo:
        return False
    return True


def aperta_durante(
    esperienza: ExperienceNode, giorno_settimana: int | None, arrivo: time
) -> bool:
    """Filtro duro 5: l'esperienza è APERTA per tutta la visita, cioè
    l'intervallo [`arrivo`, `arrivo` + `esperienza.durata_min`] cade in UNA
    fascia di `orari_apertura` del giorno `giorno_settimana`.

    UNICO punto del motore che interpreta gli orari: è un wrapper sopra
    `contracts.rientra_in_orario(..., durata_min=esperienza.durata_min)`, la
    STESSA funzione usata da `marketplace.service.request_booking` (un solo
    modello di "cosa significa aperto"). Nessun'altra lettura di
    `orari_apertura` nel motore.

    `arrivo` è l'istante in cui il visitatore arriva alla tappa (quello che
    vedrà nell'itinerario), MAI l'ora del segnale: un luogo aperto alle 9 e
    chiuso alle 13 non è adatto a una tappa che inizia alle 15.

    Lista `orari_apertura` vuota (il caso di ogni esperienza del seed oggi)
    o `giorno_settimana` `None`: non esclude MAI nulla — nessun vincolo
    fabbricato. Un intervallo che supera le 24:00 non rientra mai (lo dice
    `rientra_in_orario`). Validazione minima: capienza, conflitti di slot ed
    eccezioni calendariali restano fuori scope (`docs/LIMITI.md`)."""
    return rientra_in_orario(
        esperienza.orari_apertura,
        giorno_settimana,
        arrivo,
        durata_min=esperienza.durata_min,
    )


def passa_filtri_duri(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    signal: Signal,
    luoghi_gia_visti: list[str],
    *,
    arrivo: time,
) -> bool:
    """TUTTI i vincoli DURI dell'Ethical AI Engine (nessuna eccezione, mai),
    per un candidato che arriverebbe alla tappa all'istante `arrivo`:

    1-4. `passa_filtri_statici`: accessibilità richiesta, luoghi già visti,
         affollamento critico, partner con abbonamento non attivo;
    5.   `aperta_durante(esperienza, signal.giorno_settimana, arrivo)`: aperta
         per l'intero intervallo [arrivo, arrivo + durata].

    `arrivo` è keyword-only e OBBLIGATORIO, senza default: nessun chiamante
    può tornare per distrazione al controllo all'ora del SEGNALE. Il
    chiamante calcola l'arrivo con la stessa progressione con cui costruisce
    le tappe (`engine._costruisci_stops` / `engine._ricostruisci_stops`).
    """
    return passa_filtri_statici(candidate, profile, signal, luoghi_gia_visti) and aperta_durante(
        candidate.experience, signal.giorno_settimana, arrivo
    )


def calcola_score(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    signal: Signal,
    *,
    vocabolario: VocabolarioTemi,
) -> float:
    """Affinità profilo <-> esperienza in [0, 1], deterministica.

    VISIBILITÀ NON ACQUISTABILE: questa funzione NON legge mai
    `candidate.experience.partner_id`, `candidate.experience.prezzo_eur`,
    `candidate.experience.partner_abbonamento_attivo` né
    `candidate.attribuzione`. L'abbonamento del partner decide solo la
    PRESENZA del candidato (filtro duro in `passa_filtri_statici`), mai il
    punteggio. L'attribuzione ("Offerta da ...") è una
    disclosure che vive SOLO nel `reason`, in coda ai motivi reali: non deve
    entrare nello scoring — in particolare non deve gonfiare la componente
    `sorpresa`, che conta le `connessioni` del grafo e nient'altro. Un partner
    compare solo se coerente col profilo e col luogo; non esiste prezzo che
    alteri lo score. Il vincolo è verificato da un test-guard (AST) e da un
    test comportamentale (score invariante a partner/prezzo/attribuzione).

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio.
    """
    esperienza = candidate.experience
    temi = esperienza.temi

    score = 0.0
    # Affinità di profilo: temi contemplativi, d'arte, e la sorpresa (curiosità).
    score += (
        W_CONTEMPLAZIONE * profile.contemplazione * affinita_temi(temi, vocabolario.contemplativi)
    )
    score += W_ARTE * profile.arte * affinita_temi(temi, vocabolario.arte)

    # Curiosità: premia le connessioni del grafo (più connessioni = più
    # sorpresa possibile) e i temi insoliti. La sorpresa nasce dal grafo.
    sorpresa = 0.5 * min(len(candidate.connessioni), 4) / 4.0
    sorpresa += 0.5 * affinita_temi(temi, vocabolario.insoliti)
    score += W_CURIOSITA * profile.curiosita * sorpresa

    # Con bambini: il tema è SEMPRE considerato e premiato quando pertinente.
    if profile.con_bambini and vocabolario.bambini in temi:
        score += W_BAMBINI

    # Segnale meteo: pioggia -> al chiuso; caldo -> chiuso o verde/fresco.
    if signal.meteo == "pioggia" and esperienza.al_chiuso:
        score += W_METEO
    elif signal.meteo == "caldo" and (
        esperienza.al_chiuso or affinita_temi(temi, vocabolario.verde) > 0
    ):
        score += W_METEO

    # Stanchezza alta: preferisci tappe brevi (bonus proporzionale alla brevità).
    if signal.stanchezza > 0:
        brevita = 1.0 - min(esperienza.durata_min, DURATA_LUNGA_MIN) / DURATA_LUNGA_MIN
        score += W_STANCHEZZA * signal.stanchezza * brevita

    # VINCOLO ETICO — distribuzione dei flussi: penalità proporzionale
    # all'affollamento del luogo, anche sotto la soglia critica. Il motore
    # sposta attivamente flusso verso i luoghi meno affollati.
    affollamento = signal.affollamento.get(esperienza.place_id, 0.0)
    score -= PENALITA_AFFOLLAMENTO * affollamento

    return max(0.0, min(1.0, score))


def segnali_rilevanti(
    candidate: GraphCandidate, signal: Signal, *, vocabolario: VocabolarioTemi
) -> list[str]:
    """Chiavi di segnale (in italiano) pertinenti a QUESTA tappa, ordinate per
    rilevanza, da passare alla funzione di `reason`.

    Sono le stesse chiavi che il servizio RAG sa tradurre in frase
    ("pioggia", "caldo", "affollamento", "stanchezza"): la spiegabilità dice
    alla persona PERCHÉ quella tappa è stata scelta anche alla luce del mondo.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio.
    """
    esperienza = candidate.experience
    segnali: list[str] = []
    if signal.meteo == "pioggia" and esperienza.al_chiuso:
        segnali.append("pioggia")
    elif signal.meteo == "caldo" and (
        esperienza.al_chiuso or affinita_temi(esperienza.temi, vocabolario.verde) > 0
    ):
        segnali.append("caldo")

    affollamento = signal.affollamento.get(esperienza.place_id, 0.0)
    if affollamento < 0.3:
        segnali.append("affollamento")  # RAG: "in questo momento è meno affollato"

    if signal.stanchezza >= SOGLIA_STANCHEZZA_ALTA and esperienza.durata_min <= 45:
        segnali.append("stanchezza")

    return segnali


# ---------------------------------------------------------------------------
# Segnali FLUTTUANTI (Signal.eventi_attivi) — livello "accade ora", diverso
# dal livello "programmato" (:Evento, fuori scope: docs/LIMITI.md).
# ---------------------------------------------------------------------------


def _coerente_col_profilo(
    temi: list[str], profile: EmotionalProfile, *, vocabolario: VocabolarioTemi
) -> bool:
    """Un tema del segnale fluttuante appartiene a un gruppo la cui
    dimensione di profilo corrispondente è > 0 — STESSO ragionamento per
    connessioni già usato da `calcola_score` per le esperienze permanenti
    (`affinita_temi` contro i gruppi del vocabolario della città:
    `contemplativi`/`arte`/`insoliti`, più il tema `bambini`), non un secondo
    criterio inventato per l'occasione: "il segnale evoca un tema, il tema
    raggiunge chi è affine".

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    if profile.contemplazione > 0 and affinita_temi(temi, vocabolario.contemplativi) > 0:
        return True
    if profile.arte > 0 and affinita_temi(temi, vocabolario.arte) > 0:
        return True
    if profile.curiosita > 0 and affinita_temi(temi, vocabolario.insoliti) > 0:
        return True
    if profile.con_bambini and vocabolario.bambini in temi:
        return True
    return False


def segnali_fluttuanti_pertinenti(
    eventi_attivi: list[SegnaleFluttuante],
    profile: EmotionalProfile,
    *,
    vocabolario: VocabolarioTemi,
) -> list[SegnaleFluttuante]:
    """Segnali fluttuanti pertinenti per QUESTO profilo, nell'ordine in cui
    sono arrivati (determinismo: nessun riordino inventato qui).

    Due condizioni, ENTRAMBE necessarie:
    1. `contracts.segnale_fluttuante_ammissibile` — filtro DURO, MAI
       un'eccezione: un segnale commerciale non è mai pertinente, qualunque
       sia la sua coerenza col profilo. Verificato PRIMA, non dopo: un
       segnale commerciale ma incoerente col profilo e uno commerciale ma
       perfettamente coerente sono scartati allo stesso identico modo.
    2. `_coerente_col_profilo` — un tema in comune con almeno una dimensione
       a cui il profilo tiene davvero (peso > 0).

    NON legge né tocca `calcola_score`: nessuna esperienza permanente vede
    il proprio punteggio cambiare in base a `eventi_attivi` — questa
    funzione produce solo la lista di CANDIDATI fluttuanti da aggiungere,
    mai un input allo scoring delle esperienze del grafo.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    return [
        segnale
        for segnale in eventi_attivi
        if segnale_fluttuante_ammissibile(segnale)
        and _coerente_col_profilo(segnale.temi, profile, vocabolario=vocabolario)
    ]


# ---------------------------------------------------------------------------
# Eventi PROMOSSI (:Evento attivi nel grafo, Fase 3) — livello "programmato",
# diverso dal livello "accade ora" (`Signal.eventi_attivi`, sopra).
# ---------------------------------------------------------------------------


def occorrenza_attesa_giorni(
    ultima_occorrenza: date, cadenza_giorni: float, data_visita: date
) -> float:
    """Occorrenza ATTESA più vicina a `data_visita`, espressa in giorni
    (float) a partire da `ultima_occorrenza`: `k * cadenza_giorni` con `k`
    INTERO e `k >= 1` (l'ultima occorrenza osservata è già passata: si
    proietta solo in avanti da lì).

    Considera sia `floor` sia `ceil` del rapporto
    `(data_visita - ultima_occorrenza) / cadenza_giorni`, entrambi clampati a
    `k >= 1`, e sceglie quello a distanza minima da `data_visita`. A parità
    esatta di distanza vince il `k` MINORE (tie-break deterministico). Una
    visita precedente (o uguale) a `ultima_occorrenza` ricade su `k = 1`.

    PURA: nessun "oggi" del sistema, nessuna locale. `cadenza_giorni > 0` è
    garantito dal contratto (`EventoPromosso.cadenza_giorni`, `gt=0`)."""
    delta = float((data_visita - ultima_occorrenza).days)
    rapporto = delta / cadenza_giorni
    k_basso = max(1, math.floor(rapporto))
    k_alto = max(1, math.ceil(rapporto))
    # min su (distanza, k): a parità di distanza vince il k minore.
    k = min((k_basso, k_alto), key=lambda kk: (abs(delta - kk * cadenza_giorni), kk))
    return k * cadenza_giorni


def proiezione_occorrenza_attesa(
    ultima_occorrenza: date, cadenza_giorni: float, data_visita: date
) -> date | None:
    """Giorno di calendario dell'occorrenza attesa più vicina
    (`occorrenza_attesa_giorni`), arrotondato al giorno più vicino con il
    mezzo giorno verso l'alto (`floor(x + 0.5)`, mai l'arrotondamento
    bancario di `round`) — oppure `None` se la proiezione NON è
    rappresentabile come `date`.

    UNICO punto in cui la proiezione può fallire. `Signal.data` arriva dal
    client: una visita vicina a `date.max`/`date.min`, o una cadenza
    degenere (enorme, infinita, o così piccola che `delta / cadenza`
    esplode a `inf`), può portare `ultima_occorrenza + k·cadenza` fuori
    dall'intervallo di `date` (`OverflowError`) o produrre un float non
    convertibile (`OverflowError`/`ValueError` da `math.floor`). FAIL-CLOSED
    e SENZA inventare date: nessun clamp a `date.max`, nessuna data
    "vicina" di ripiego — `None`, e il chiamante tratta l'evento come
    FUORI finestra. PURA."""
    try:
        offset = occorrenza_attesa_giorni(ultima_occorrenza, cadenza_giorni, data_visita)
        return ultima_occorrenza + timedelta(days=math.floor(offset + 0.5))
    except (OverflowError, ValueError):
        return None


def giorno_occorrenza_attesa(
    ultima_occorrenza: date, cadenza_giorni: float, data_visita: date
) -> date:
    """Giorno di calendario dell'occorrenza attesa più vicina
    (`proiezione_occorrenza_attesa`). Serve SOLO a raccontarla nel `reason`:
    la decisione "in finestra" la prende `evento_in_finestra` sui giorni
    float, non su questo valore arrotondato.

    PRECONDIZIONE: l'evento è in finestra (`evento_in_finestra` è `True`),
    il che implica una proiezione rappresentabile. Il motore la chiama solo
    sugli eventi già filtrati da `eventi_promossi_pertinenti`; chiamarla
    fuori da quella garanzia con una proiezione non rappresentabile è un
    errore di programmazione (`ValueError`), mai una data inventata."""
    giorno = proiezione_occorrenza_attesa(ultima_occorrenza, cadenza_giorni, data_visita)
    if giorno is None:
        raise ValueError("occorrenza attesa non rappresentabile come date")
    return giorno


def evento_in_finestra(ultima_occorrenza: date, cadenza_giorni: float, data_visita: date) -> bool:
    """`True` se `data_visita` cade nella finestra attorno all'occorrenza
    attesa più vicina: `|data_visita - occorrenza| <=
    FRAZIONE_FINESTRA_CADENZA * cadenza_giorni`, bordo INCLUSO (con
    `TOLLERANZA_FINESTRA_GIORNI` contro l'errore float).

    FAIL-CLOSED: se l'occorrenza attesa non è rappresentabile come `date`
    (`proiezione_occorrenza_attesa` è `None` — es. `Signal.data` vicino a
    `date.max`, cadenza degenere) l'evento è FUORI finestra, anche se in
    aritmetica float risulterebbe dentro. Così nessun evento che compare può
    poi far fallire il racconto del suo giorno nel `reason`.

    Decide SOLO "quando". "Se l'evento è ancora vivo" (dormienza, battiti
    mancati) NON è qui: lo decide la frizione, via `stato`, già filtrato a
    monte dal BFF."""
    if proiezione_occorrenza_attesa(ultima_occorrenza, cadenza_giorni, data_visita) is None:
        return False
    delta = float((data_visita - ultima_occorrenza).days)
    occorrenza = occorrenza_attesa_giorni(ultima_occorrenza, cadenza_giorni, data_visita)
    semi_ampiezza = FRAZIONE_FINESTRA_CADENZA * cadenza_giorni
    return abs(delta - occorrenza) <= semi_ampiezza + TOLLERANZA_FINESTRA_GIORNI


def eventi_promossi_pertinenti(
    eventi: list[EventoPromosso],
    profile: EmotionalProfile,
    data_visita: date | None,
    *,
    vocabolario: VocabolarioTemi,
) -> list[EventoPromosso]:
    """Eventi promossi pertinenti per QUESTO profilo e QUESTA data di visita,
    nell'ordine in cui sono arrivati (determinismo: nessun riordino inventato
    qui — stessa garanzia di `segnali_fluttuanti_pertinenti` sopra).

    FAIL-CLOSED sulla data: se `data_visita` è `None` (il client non l'ha
    dichiarata in `Signal.data`) la lista è VUOTA — mai una data inventata
    (es. "oggi" del server), che farebbe comparire o sparire eventi per un
    giorno che nessuno ha dichiarato. Parametro senza default, apposta: ogni
    chiamante deve dire esplicitamente quale data sta usando (anche `None`).

    Altrimenti DUE condizioni, entrambe necessarie:
    1. `_coerente_col_profilo` — un tema in comune con almeno una dimensione
       a cui il profilo tiene davvero (peso > 0). È ESATTAMENTE la stessa
       funzione riusata dai fluttuanti, non un secondo criterio: "il tema
       raggiunge chi è affine" si scrive in un posto solo.
    2. `evento_in_finestra` — la visita cade vicino a un'occorrenza ATTESA,
       proiettata da `ultima_occorrenza` + k·`cadenza_giorni`. Decide solo
       "quando"; "se è vivo" resta allo `stato` filtrato a monte.

    PERCHÉ NON APPLICA L'AMMISSIBILITÀ COMMERCIALE (non è un'omissione).
    `segnali_fluttuanti_pertinenti` applica in più
    `contracts.segnale_fluttuante_ammissibile`, che legge
    `SegnaleFluttuante.non_commerciale`: un campo che `EventoPromosso` NON ha,
    e deliberatamente. Un segnale fluttuante entra nel mondo per
    auto-segnalazione, senza che nessuno lo abbia vagliato — lì il filtro duro
    sul commerciale è l'unica difesa contro la pubblicità travestita da
    segnale. Un `:Evento` promosso, invece, esiste SOLO perché una decisione
    umana esplicita di curatela lo ha promosso da pattern ricorrente a nodo
    permanente del grafo (`urban_memory.promozione_evento`): il vaglio è già
    avvenuto, a monte e da una persona. Riapplicarlo qui non aggiungerebbe
    protezione — non c'è un campo su cui applicarlo — e fingere di applicarlo
    (es. un default `non_commerciale=True`) darebbe una garanzia che nessuno
    ha davvero dichiarato. Il vincolo "visibilità non acquistabile" resta
    intatto per un'altra via, più forte: un `:Evento` non si compra, si
    promuove, e la promozione è tracciata (`promosso_da`/`promosso_il` sul
    nodo).

    NON legge né tocca `calcola_score`: nessuna esperienza permanente vede il
    proprio punteggio cambiare per la presenza di un evento promosso — questa
    funzione produce solo la lista di eventi da aggiungere in coda, mai un
    input allo scoring delle esperienze del grafo.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio.
    """
    if data_visita is None:
        return []
    return [
        evento
        for evento in eventi
        if _coerente_col_profilo(evento.temi, profile, vocabolario=vocabolario)
        and evento_in_finestra(evento.ultima_occorrenza, evento.cadenza_giorni, data_visita)
    ]


# ---------------------------------------------------------------------------
# Bagliore (docs/PROMOZIONE_TRACCIA.md §2b) — quanto un luogo "torna a vivere"
# secondo le tracce del ledger. Entra SOLO nel `reason` di tappe GIÀ SCELTE:
# mai nello scoring, mai nella selezione, mai nell'ordine delle tappe.
#
# COLLOCAZIONE: qui, in `rules.py` del motore, e non in `urban-memory` né in
# `contracts`. Il motore è l'UNICO componente che decide (anche cosa dire nel
# `reason` deterministico), ed è oggi l'unico consumatore del bagliore: un
# vincolo concentrato in un solo punto è auditabile. Se un secondo
# consumatore (es. un cruscotto dell'Urban Intelligence Index) ne avesse
# bisogno, la funzione andrebbe spostata in un punto condiviso, non copiata.
#
# PURE: nessun orologio (l'istante `adesso` è SEMPRE un parametro), nessun
# I/O. Le tracce arrivano già lette dal chiamante come coppie
# `(creato_il, temi)`.
# ---------------------------------------------------------------------------

#: Residuo minimo del peso di una traccia, per quanto vecchia: il peso non
#: arriva MAI a zero (§2b: "con un pavimento positivo"). TUNING: valore di
#: PARTENZA, non calibrato su dati reali — la taratura è deliberatamente
#: differita al pilota (stessa classe di `K_BATTITI_SOSPENSIONE` in
#: `urban_memory.frizione_pattern`).
PAVIMENTO_BAGLIORE: Final = 0.05

#: Emivita (giorni) della parte decadente del peso di una traccia: dopo
#: `EMIVITA_BAGLIORE_GIORNI` giorni la parte sopra il pavimento si dimezza.
#: TUNING: valore di PARTENZA, non calibrato — taratura differita al pilota.
EMIVITA_BAGLIORE_GIORNI: Final = 30.0

#: Bagliore RECENTE minimo (`bagliore_recente`, sola parte decadente, MAI il
#: pavimento) perché il `reason` dica che un luogo "torna spesso a vivere".
#: La frase è al presente: deve poggiare solo su passaggi recenti. Una
#: traccia da sola non basta MAI (massimo decadente per traccia =
#: 1 − PAVIMENTO = 0.95 < 1.5); due tracce bastano se entrambe hanno meno di
#: ~10 giorni, tre se meno di ~28. Il pavimento, che si accumula senza limite
#: (ledger immortale), conta SOLO in `bagliore()`, per consumatori futuri: qui
#: il contributo di ogni traccia tende a 0. Da sola la soglia non sarebbe un
#: tetto assoluto sui passaggi vecchi: con N tracce di età d la frase
#: resterebbe accesa finché d <= EMIVITA·log2(0.95·N / SOGLIA) — finestra
#: logaritmica in N (N=10 ~80 giorni, N=40 ~140). Questa finestra è ora
#: TAGLIATA a `ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI` dall'ultima traccia,
#: qualunque sia N (vedi sotto).
#: TUNING: valore di PARTENZA, non calibrato — taratura differita al pilota.
SOGLIA_BAGLIORE: Final = 1.5

#: Età massima (giorni) della traccia PIÙ RECENTE di un luogo perché la frase
#: del bagliore possa accendersi: oltre, `frase_bagliore` è `None` a
#: prescindere dal bagliore, per quante tracce vecchie ci siano. DERIVATA
#: dall'emivita, non una costante indipendente: resta UNA sola manopola da
#: tarare (`EMIVITA_BAGLIORE_GIORNI`). 60 giorni (2 emivite) coprono un
#: evento mensile con margine: 30 secchi lo farebbero sparire alla vigilia
#: dell'occorrenza successiva. Confronto stretto: esattamente 60 giorni è
#: ammesso.
ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI: Final = 2 * EMIVITA_BAGLIORE_GIORNI


def temi_leggibili(temi: Sequence[str]) -> str:
    """Rende leggibile una lista di temi GREZZI (id/slug del grafo, es.
    "tema-a-piu-parole") per un `reason`.

    `EventoPromosso.temi`, `SegnaleFluttuante.temi`, `ExperienceNode.temi` e
    i temi delle tracce portano id, non nomi umani (i nomi leggibili dei
    `:Tema` viaggiano su un campo separato della query candidati,
    `temi_nomi`, che qui non esiste). Sostituisce i trattini con spazi e
    unisce con virgola: trasformazione PURA, mai un lookup a un nodo `:Tema`
    che questa funzione non ha modo di fare — meglio un id reso leggibile che
    un nome fabbricato. Usata dal `reason` delle tappe-evento
    (`engine._reason_evento_promosso`) e da `frase_bagliore`: un solo punto."""
    return ", ".join(tema.replace("-", " ") for tema in temi)


def _come_utc(istante: datetime) -> datetime:
    """Un `datetime` naive è trattato come UTC; uno aware è convertito a UTC."""
    if istante.tzinfo is None:
        return istante.replace(tzinfo=UTC)
    return istante.astimezone(UTC)


def _parte_decadente(delta: timedelta) -> float:
    """Parte DECADENTE del peso di una traccia trascorso `delta`:
    `(1 − PAVIMENTO) · 0.5 ** (giorni / EMIVITA)`, in (0, 1 − PAVIMENTO].

    Unico punto del calcolo del decadimento, usato sia da `peso_traccia` sia
    da `bagliore_recente`/`tema_dominante`. Un `delta` negativo (traccia "nel
    futuro" rispetto ad `adesso`, es. orologi disallineati) è trattato come 0:
    valore massimo, mai oltre."""
    giorni = max(0.0, delta.total_seconds() / 86400.0)
    return (1.0 - PAVIMENTO_BAGLIORE) * 0.5 ** (giorni / EMIVITA_BAGLIORE_GIORNI)


def peso_traccia(delta: timedelta) -> float:
    """Peso di una traccia trascorso `delta` dalla sua creazione:
    `PAVIMENTO + (1 − PAVIMENTO) · 0.5 ** (giorni / EMIVITA)`.

    Monotona decrescente in `delta`, in (PAVIMENTO, 1.0], MAI zero. Un
    `delta` negativo (traccia "nel futuro" rispetto ad `adesso`, es. orologi
    disallineati) è trattato come 0: peso 1.0, mai oltre."""
    return PAVIMENTO_BAGLIORE + _parte_decadente(delta)


def bagliore(tracce: Sequence[tuple[datetime, Sequence[str]]], adesso: datetime) -> float:
    """Bagliore di un luogo: Σ `peso_traccia(adesso − creato_il)` su TUTTE le
    sue tracce (§2b: dieci passaggi recenti brillano più di uno solo),
    pavimento INCLUSO. Non decide la frase del `reason` (quella usa
    `bagliore_recente`): il pavimento si accumula senza limite su un ledger
    immortale, quindi qui resta solo per consumatori futuri.
    `creato_il`/`adesso` naive sono trattati come UTC. Lista vuota → 0.0."""
    ora = _come_utc(adesso)
    return sum((peso_traccia(ora - _come_utc(creato_il)) for creato_il, _ in tracce), 0.0)


def bagliore_recente(tracce: Sequence[tuple[datetime, Sequence[str]]], adesso: datetime) -> float:
    """Bagliore RECENTE di un luogo: Σ della sola parte DECADENTE del peso,
    `(1 − PAVIMENTO) · 0.5 ** (giorni / EMIVITA)`, su tutte le tracce — il
    pavimento ESCLUSO. Tende a 0 per tracce vecchie, per quante siano: è la
    grandezza su cui `frase_bagliore` confronta `SOGLIA_BAGLIORE`.
    Stessa gestione di `peso_traccia`: `delta` negativo -> 0 giorni;
    `creato_il`/`adesso` naive trattati come UTC. Lista vuota → 0.0."""
    ora = _come_utc(adesso)
    return sum((_parte_decadente(ora - _come_utc(creato_il)) for creato_il, _ in tracce), 0.0)


def tema_dominante(
    tracce: Sequence[tuple[datetime, Sequence[str]]], adesso: datetime
) -> str | None:
    """Tema col peso RECENTE massimo fra le tracce: ogni tema riceve la sola
    parte DECADENTE del peso della traccia che lo contiene (coerente con
    `bagliore_recente`, su cui si decide la frase: il tema detto al presente
    è quello dei passaggi recenti). Una traccia che ripete un tema lo conta
    una volta sola. Temi vuoti/solo spazi ignorati. Spareggio alfabetico
    (deterministico, anche se tutti i pesi decadenti fossero 0 — caso in cui
    `frase_bagliore` è comunque già `None`). `None` se nessun tema."""
    ora = _come_utc(adesso)
    pesi: dict[str, float] = {}
    for creato_il, temi in tracce:
        peso = _parte_decadente(ora - _come_utc(creato_il))
        for tema in dict.fromkeys(t for t in temi if t.strip()):
            pesi[tema] = pesi.get(tema, 0.0) + peso
    if not pesi:
        return None
    return min(pesi, key=lambda t: (-pesi[t], t))


def frase_bagliore(
    tracce: Sequence[tuple[datetime, Sequence[str]]], adesso: datetime
) -> str | None:
    """Frase deterministica per il `reason` di una tappa GIÀ SCELTA, oppure
    `None` (tracce vuote, traccia più recente con età oltre
    `ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI`, `bagliore_recente` sotto
    `SOGLIA_BAGLIORE`, nessun tema). La soglia è sul bagliore RECENTE, mai su
    `bagliore()`: la frase è al presente ("torna spesso"). In più, se
    l'ultimo passaggio è più vecchio di `ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI`
    giorni la frase è spenta qualunque sia il numero di tracce: se anche
    l'ULTIMO passaggio è vecchio, nessun numero di tracce la accende. Con una
    traccia recente, invece, le tracce vecchie contano ancora nella somma e
    possono portarla sopra soglia. Età dell'ultima traccia =
    `adesso − max(creato_il)` (naive → UTC); una traccia "nel futuro" ha età
    0; confronto stretto (esattamente il tetto è ammesso). Unico punto di
    questo controllo: `bagliore`/`bagliore_recente`/`tema_dominante` non lo
    applicano.

    Dice SOLO luogo (implicito: è la tappa) + tema: mai descrizioni, autori,
    date — il contenuto delle tracce resta nel ledger. Nessun articolo
    inventato (nessuna tabella tema→articolo): il tema è reso leggibile con
    `temi_leggibili`, lo stesso helper del `reason` delle tappe-evento."""
    if not tracce:
        return None
    ora = _come_utc(adesso)
    ultima = max(_come_utc(creato_il) for creato_il, _ in tracce)
    if ora - ultima > timedelta(days=ETA_MASSIMA_ULTIMA_TRACCIA_GIORNI):
        return None
    if bagliore_recente(tracce, adesso) < SOGLIA_BAGLIORE:
        return None
    tema = tema_dominante(tracce, adesso)
    if tema is None:
        return None
    return f"È un luogo che torna spesso a vivere di {temi_leggibili([tema])}."
