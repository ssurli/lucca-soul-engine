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

from contracts import EmotionalProfile, GraphCandidate, Signal

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

# --- Pesi dello scoring (documentati: nessuno tocca partner_id/prezzo_eur) ---

W_CONTEMPLAZIONE = 0.30
W_ARTE = 0.30
W_CURIOSITA = 0.20
W_BAMBINI = 0.25
W_METEO = 0.15
W_STANCHEZZA = 0.15
PENALITA_AFFOLLAMENTO = 0.40

# ---------------------------------------------------------------------------
# Vocabolario dei temi (allineato al seed di Lucca)
# ---------------------------------------------------------------------------

#: Temi che parlano a chi cerca silenzio e raccoglimento.
TEMI_CONTEMPLATIVI = {"silenzio", "verde", "panorama", "romanico"}

#: Temi della bellezza e delle storie d'arte e musica.
TEMI_ARTE = {"arte", "puccini", "musica", "romanico", "liuteria"}

#: Temi "insoliti" che premiano chi ha voglia di perdersi: la sorpresa nasce
#: dalle connessioni del grafo, non da una categoria da vetrina.
TEMI_INSOLITI = {"artigianato", "liuteria", "romanico", "medievale"}

#: Temi freschi/verdi, apprezzati col caldo.
TEMI_VERDE = {"verde", "panorama"}

#: Tema esplicito per chi viaggia con bambini.
TEMA_BAMBINI = "con-bambini"


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


def affinita_temi(temi: list[str], gruppo: set[str]) -> float:
    """Quanto i temi di un'esperienza appartengono a un gruppo (0, 0.5 o 1).

    Conta le sovrapposizioni, satura a 2: due temi coerenti bastano a dire che
    l'esperienza "parla" a quel tratto; oltre non aggiunge informazione."""
    comuni = sum(1 for t in temi if t in gruppo)
    return min(comuni, 2) / 2.0


def passa_filtri_duri(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    signal: Signal,
    luoghi_gia_visti: list[str],
) -> bool:
    """Vincoli DURI dell'Ethical AI Engine (nessuna eccezione, mai):

    - `accessibilita_richiesta` => solo esperienze `accessibile=True`.
      L'inclusione non è negoziabile: nessuno score può reintrodurre una
      tappa inaccessibile per una persona che ha chiesto accessibilità.
    - Esclude i luoghi già visti: non si ripropone ciò che è già stato vissuto.
    - Esclude i luoghi criticamente affollati (>= soglia): distribuire i flussi
      per non aggravare l'overtourism è un dovere del motore, non un'opzione.
    """
    esperienza = candidate.experience
    if profile.accessibilita_richiesta and not esperienza.accessibile:
        return False
    if esperienza.place_id in luoghi_gia_visti:
        return False
    if signal.affollamento.get(esperienza.place_id, 0.0) >= SOGLIA_AFFOLLAMENTO_CRITICO:
        return False
    return True


def calcola_score(candidate: GraphCandidate, profile: EmotionalProfile, signal: Signal) -> float:
    """Affinità profilo <-> esperienza in [0, 1], deterministica.

    VISIBILITÀ NON ACQUISTABILE: questa funzione NON legge mai
    `candidate.experience.partner_id` né `candidate.experience.prezzo_eur`.
    Un partner compare solo se coerente col profilo e col luogo; non esiste
    prezzo che alteri lo score. Il vincolo è verificato da un test-guard che
    controlla l'assenza di quei nomi in questo modulo.
    """
    esperienza = candidate.experience
    temi = esperienza.temi

    score = 0.0
    # Affinità di profilo: temi contemplativi, d'arte, e la sorpresa (curiosità).
    score += W_CONTEMPLAZIONE * profile.contemplazione * affinita_temi(temi, TEMI_CONTEMPLATIVI)
    score += W_ARTE * profile.arte * affinita_temi(temi, TEMI_ARTE)

    # Curiosità: premia le connessioni del grafo (più connessioni = più
    # sorpresa possibile) e i temi insoliti. La sorpresa nasce dal grafo.
    sorpresa = 0.5 * min(len(candidate.connessioni), 4) / 4.0
    sorpresa += 0.5 * affinita_temi(temi, TEMI_INSOLITI)
    score += W_CURIOSITA * profile.curiosita * sorpresa

    # Con bambini: il tema è SEMPRE considerato e premiato quando pertinente.
    if profile.con_bambini and TEMA_BAMBINI in temi:
        score += W_BAMBINI

    # Segnale meteo: pioggia -> al chiuso; caldo -> chiuso o verde/fresco.
    if signal.meteo == "pioggia" and esperienza.al_chiuso:
        score += W_METEO
    elif signal.meteo == "caldo" and (esperienza.al_chiuso or affinita_temi(temi, TEMI_VERDE) > 0):
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


def segnali_rilevanti(candidate: GraphCandidate, signal: Signal) -> list[str]:
    """Chiavi di segnale (in italiano) pertinenti a QUESTA tappa, ordinate per
    rilevanza, da passare alla funzione di `reason`.

    Sono le stesse chiavi che il servizio RAG sa tradurre in frase
    ("pioggia", "caldo", "affollamento", "stanchezza"): la spiegabilità dice
    alla persona PERCHÉ quella tappa è stata scelta anche alla luce del mondo.
    """
    esperienza = candidate.experience
    segnali: list[str] = []
    if signal.meteo == "pioggia" and esperienza.al_chiuso:
        segnali.append("pioggia")
    elif signal.meteo == "caldo" and (
        esperienza.al_chiuso or affinita_temi(esperienza.temi, TEMI_VERDE) > 0
    ):
        segnali.append("caldo")

    affollamento = signal.affollamento.get(esperienza.place_id, 0.0)
    if affollamento < 0.3:
        segnali.append("affollamento")  # RAG: "in questo momento è meno affollato"

    if signal.stanchezza >= SOGLIA_STANCHEZZA_ALTA and esperienza.durata_min <= 45:
        segnali.append("stanchezza")

    return segnali
