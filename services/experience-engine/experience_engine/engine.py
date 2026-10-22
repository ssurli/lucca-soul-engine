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
from collections.abc import Set as AbstractSet
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from typing import Any, Literal, Protocol

from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    EventoPromosso,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Punto,
    SegnaleFluttuante,
    Signal,
    TappaEsclusa,
    VisitorContext,
    VocabolarioTemi,
    con_articolo,
    con_luogo,
    distanza_a_piedi_m,
    punto_piu_vicino,
)

from .rules import (
    DURATA_TAPPA_EVENTO_MIN,
    DURATA_TAPPA_FLUTTUANTE_MIN,
    SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
    SOGLIA_STANCHEZZA_ALTA,
    TEMPO_TRASFERIMENTO_DEFAULT_MIN,
    TOLLERANZA_DIVERSITA,
    aperta_durante,
    calcola_score,
    esperienza_sospesa,
    eventi_promossi_pertinenti,
    frase_bagliore,
    giorno_occorrenza_attesa,
    passa_filtri_duri,
    passa_filtri_statici,
    segnali_fluttuanti_pertinenti,
    segnali_rilevanti,
    stima_trasferimento_min,
    temi_leggibili,
)

__all__ = ["compose_itinerary", "adapt_itinerary", "ReasonFn", "AdaptReasonFn", "ScoreFn"]

class ReasonFn(Protocol):
    """Firma della funzione che compone il `reason` di una tappa. Combacia con
    `rag.reasons.compose_reason(candidate, profile, segnali, *, prima_tappa)`.

    `prima_tappa` (keyword) è True SOLO per la prima tappa dell'itinerario
    finale (arrivo più presto): lì, e solo lì, il motivo può aprire con la
    frase del profilo, così il profilo compare al massimo una volta per
    itinerario. False per ogni altra tappa e per i motivi dei sostituti,
    tranne il sostituto che in adattamento risulta PRIMA tappa
    (`_con_frase_profilo`)."""

    def __call__(
        self,
        candidate: GraphCandidate,
        profile: EmotionalProfile,
        segnali: list[str],
        /,
        *,
        prima_tappa: bool,
    ) -> str: ...


#: Firma della funzione che riscrive il `reason` di una tappa sostituita.
#: Combacia con `rag.reasons.adapt_reason(motivo, segnale)`.
AdaptReasonFn = Callable[[str, str], str]

#: Firma della funzione di scoring INIETTABILE dal recommender (Wave 3b).
#: Combacia con la funzione del recommender `(candidate, profile, signal) -> float`.
#: Il recommender ORDINA ma NON seleziona né filtra: riceve SOLO i candidati
#: già ammessi dai filtri duri statici (`passa_filtri_statici`), applicati
#: prima e altrove; il filtro sugli orari (`aperta_durante`) dipende
#: dall'arrivo e lo applica `_seleziona_tappe` slot per slot, dopo lo score.
#: Se non iniettata, il motore usa `rules.calcola_score` (comportamento MVP).
ScoreFn = Callable[[GraphCandidate, EmotionalProfile, Signal], float]


# ---------------------------------------------------------------------------
# Fallback interni di spiegabilità (usati solo se il BFF non inietta la RAG).
# Il motore NON importa `rag`: resta dipendente solo dai contratti.
# ---------------------------------------------------------------------------


#: Frasi dei segnali: STESSO testo di `rag.reasons` (il motore non importa
#: `rag`; l'uguaglianza dei due testi è verificata da un test).
_FRASI_SEGNALE_FALLBACK: dict[str, str] = {
    "pioggia": "con la pioggia si sta al chiuso",
    "sereno": "con il cielo sereno conviene stare all'aperto",
    "caldo": "con questo caldo un luogo fresco si apprezza di più",
    "freddo": "con il freddo un luogo al chiuso è più comodo",
    "affollamento": "in questo momento è meno affollato",
    "stanchezza": "è una tappa più breve, per non stancarti troppo",
}


def _frase_fallback(testo: str) -> str:
    """Iniziale maiuscola e punto finale (nessun secondo punto se il testo
    termina già con ".", "!" o "?")."""
    t = testo.strip()
    if not t:
        return ""
    t = t[:1].upper() + t[1:]
    return t if t[-1] in ".!?" else t + "."


#: Soglie del tratto NETTO: STESSI valori di `rag.reasons` (verificato da un
#: test). Un tratto 0..1 entra nel `reason` solo se >= 0.7 o <= 0.2, limiti
#: inclusi con tolleranza in virgola mobile.
_SOGLIA_TRATTO_ALTA_FALLBACK = 0.7
_SOGLIA_TRATTO_BASSA_FALLBACK = 0.2
_TOLLERANZA_TRATTO_FALLBACK = 1e-9


def _tratto_netto_fallback(valore: float) -> bool:
    return (
        valore >= _SOGLIA_TRATTO_ALTA_FALLBACK - _TOLLERANZA_TRATTO_FALLBACK
        or valore <= _SOGLIA_TRATTO_BASSA_FALLBACK + _TOLLERANZA_TRATTO_FALLBACK
    )


def _tratto_dominante_fallback(profile: EmotionalProfile) -> str | None:
    """Tratto più marcato del profilo (stessa regola di `rag.reasons`): prima
    i vincoli espliciti (bambini, accessibilità), poi, tra i soli tratti 0..1
    NETTI (>= 0.7 o <= 0.2, limiti inclusi), quello più lontano da 0.5, a
    parità il primo nell'ordine contemplazione, arte, curiosità. Nessun
    tratto netto: nessuna frase (mai inventata)."""
    if profile.con_bambini:
        return "è pensata anche per chi viaggia con bambini"
    if profile.accessibilita_richiesta:
        return "rispetta il bisogno di un percorso accessibile"
    tratti: list[tuple[float, float, str]] = [
        (
            profile.contemplazione,
            abs(profile.contemplazione - 0.5),
            "cerchi silenzio e raccoglimento"
            if profile.contemplazione >= 0.5
            else "ami i luoghi vivi, con musica e movimento",
        ),
        (
            profile.arte,
            abs(profile.arte - 0.5),
            "ti lasci conquistare dalla bellezza"
            if profile.arte >= 0.5
            else "preferisci le storie che un luogo racconta",
        ),
        (
            profile.curiosita,
            abs(profile.curiosita - 0.5),
            "hai voglia di perderti e lasciarti sorprendere"
            if profile.curiosita >= 0.5
            else "preferisci un percorso chiaro, senza troppe sorprese",
        ),
    ]
    netti = [(scarto, frase) for valore, scarto, frase in tratti if _tratto_netto_fallback(valore)]
    if not netti:
        return None
    # `sort` è stabile anche con reverse=True: a parità resta l'ordine sopra.
    netti.sort(key=lambda c: c[0], reverse=True)
    return netti[0][1]


#: TUTTE le frasi del profilo che `_tratto_dominante_fallback` (e, con lo
#: stesso testo, `rag.reasons._tratto_dominante`) può produrre: servono a
#: riconoscere una frase del profilo già presente in un `reason` ricevuto
#: (`_con_frase_profilo`). Completezza verificata da un test.
_FRASI_PROFILO_FALLBACK: tuple[str, ...] = (
    "è pensata anche per chi viaggia con bambini",
    "rispetta il bisogno di un percorso accessibile",
    "cerchi silenzio e raccoglimento",
    "ami i luoghi vivi, con musica e movimento",
    "ti lasci conquistare dalla bellezza",
    "preferisci le storie che un luogo racconta",
    "hai voglia di perderti e lasciarti sorprendere",
    "preferisci un percorso chiaro, senza troppe sorprese",
)


def _contiene_frase_profilo(reason: str) -> bool:
    """Vero se `reason` contiene una qualunque frase del profilo (non solo
    quella del profilo corrente), senza distinguere maiuscole e minuscole."""
    testo = reason.lower()
    return any(frase in testo for frase in _FRASI_PROFILO_FALLBACK)


def _fallback_reason(
    candidate: GraphCandidate,
    profile: EmotionalProfile,
    segnali: list[str],
    /,
    *,
    prima_tappa: bool = True,
) -> str:
    """`reason` in italiano se nessuna RAG è iniettata: le stesse cinque frasi
    (e lo stesso testo) di `rag.reasons.compose_reason`, in quest'ordine:
    1. (solo `prima_tappa`) il tratto dominante del profilo;
    2. il primo racconto con fonte, altrimenti "Temi: a, b.";
    3. sempre e solo "Al chiuso."/"All'aperto." (nessuna frase sul prezzo);
    4. la vicinanza a un luogo già visitato;
    5. la frase del primo segnale (già solo misurato).
    Non legge `connessioni` (alimentano solo il punteggio). Mai vuoto."""
    frasi: list[str] = []
    if prima_tappa:
        tratto = _tratto_dominante_fallback(profile)
        if tratto:
            frasi.append(_frase_fallback(tratto))
    racconto = next((r for r in candidate.racconti if r.strip()), None)
    if racconto:
        frasi.append(_frase_fallback(racconto))
    else:
        etichette = [e.strip() for e in candidate.temi_etichette if e.strip()]
        if etichette:
            frasi.append(f"Temi: {', '.join(etichette)}.")
    esp = candidate.experience
    dove = "Al chiuso" if esp.al_chiuso else "All'aperto"
    frasi.append(dove + ".")
    if candidate.distanza_m is not None and candidate.vicinanza_nome:
        luogo = con_luogo("da", candidate.vicinanza_articolo, candidate.vicinanza_nome)
        frasi.append(f"A {candidate.distanza_m} m {luogo}, già visitato.")
    if segnali and segnali[0].strip():
        chiave = segnali[0].strip().lower()
        frase_segnale = _FRASI_SEGNALE_FALLBACK.get(chiave, segnali[0].strip())
        frasi.append(_frase_fallback(frase_segnale))
    return " ".join(frasi)


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


# ---------------------------------------------------------------------------
# Trasferimento tra tappe consecutive e punto di arrivo (ondata 3, compito 4).
# UNICO punto della progressione: composizione, budget, arrivi, sostituzioni,
# tetto della giornata e ricostruzione degli orari passano tutti di qui.
# DATI DI POSIZIONE: decidono solo TEMPO (trasferimento) e il link "Come
# arrivo qui", mai lo score né l'ordine per affinità.
# ---------------------------------------------------------------------------


def _passo(
    cand: GraphCandidate, punto_precedente: Punto | None, *, prima: bool
) -> tuple[int, Punto | None]:
    """(minuti di trasferimento verso `cand`, punto di arrivo scelto per `cand`)
    se `cand` segue una tappa il cui punto di arrivo è `punto_precedente`.

    Punto di arrivo: prima tappa -> il primo di `cand.punti_arrivo`; tappe
    successive -> il più vicino a `punto_precedente` (`contracts.
    punto_piu_vicino`, a parità il primo); precedente senza punto (bottega,
    stub) -> il primo della lista; `cand` senza punti -> `None`.

    Trasferimento: 0 per la prima tappa; altrimenti
    `stima_trasferimento_min(distanza_a_piedi_m(precedente, scelto))` se
    entrambe hanno un punto, se no la stima prudente
    `TEMPO_TRASFERIMENTO_DEFAULT_MIN`. Non legge `distanza_m` (che misura la
    distanza dall'ultimo luogo GIÀ VISITATO, non dalla tappa precedente)."""
    punti = cand.punti_arrivo
    primo = punti[0] if punti else None
    if prima:
        return 0, primo
    if punto_precedente is None or primo is None:
        return TEMPO_TRASFERIMENTO_DEFAULT_MIN, primo
    scelto = punto_piu_vicino(punto_precedente, punti) or primo
    return stima_trasferimento_min(distanza_a_piedi_m(punto_precedente, scelto)), scelto


def _progressione(tappe: Sequence[GraphCandidate]) -> list[tuple[int, Punto | None]]:
    """`_passo` applicato in ordine: per ogni tappa (trasferimento dalla
    precedente, punto di arrivo). Il trasferimento dipende dalla tappa
    PRECEDENTE: cambiare una tappa cambia anche il trasferimento della
    successiva."""
    risultato: list[tuple[int, Punto | None]] = []
    precedente: Punto | None = None
    for i, cand in enumerate(tappe):
        passo = _passo(cand, precedente, prima=i == 0)
        risultato.append(passo)
        precedente = passo[1]
    return risultato


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
    valutati: list[tuple[float, GraphCandidate]],
    tempo_disponibile_min: int,
    *,
    ora_partenza: time,
    giorno_settimana: int | None,
) -> list[GraphCandidate]:
    """Riempie il budget di tempo diversificando luoghi e temi.

    - budget: somma durate + trasferimenti stimati <= tempo disponibile
      (`compose_itinerary` passa il budget EFFETTIVO, già troncato alla
      mezzanotte da `_minuti_alla_mezzanotte`);
    - una tappa per luogo (vincolo di composizione): al massimo UNA
      esperienza per `place_id`. Un candidato il cui `place_id` è già tra le
      tappe scelte è saltato, come uno fuori budget, e non rientra più
      (il luogo resta occupato fino alla fine). Motivazione: distribuzione
      dei flussi — due tappe nello stesso luogo concentrano le visite e non
      aggiungono esperienza. Il vincolo legge solo `place_id`: mai partner,
      prezzo né attribuzione, e non tocca lo score;
    - orari (filtro duro 6, `rules.aperta_durante`): per ogni candidato si
      calcola l'arrivo ESATTAMENTE come in `_costruisci_stops`,
      `ora_partenza + tempo_usato + trasferimento` (trasferimento 0 per la
      prima tappa); se l'esperienza non è aperta per [arrivo, arrivo +
      durata] il candidato è saltato IN QUESTO SLOT, come uno che non sta
      nel budget, ma resta tra i rimanenti e può entrare in uno slot
      successivo. Lo stesso vale nel ramo della diversificazione;
    - preferisce, a parità (quasi) di score, un tema diverso dalla tappa
      precedente: la varietà è parte dell'esperienza, non un vezzo.

    `ora_partenza` e `giorno_settimana` vengono dal `Signal`
    (`signal.ora`, `signal.giorno_settimana`). Con `orari_apertura` vuoti
    (ogni esperienza del seed oggi) o `giorno_settimana` `None` il controllo
    non salta mai nulla: selezione identica a prima.
    """
    selezionati: list[GraphCandidate] = []
    luoghi_scelti: set[str] = set()
    tempo_usato = 0
    rimanenti = list(valutati)
    # Punto di arrivo dell'ultima tappa scelta (`_passo`): il trasferimento
    # di ogni candidato dipende da lì, non dallo score.
    punto_ultimo: Punto | None = None

    while rimanenti:
        scelto_idx: int | None = None
        for idx, (score, cand) in enumerate(rimanenti):
            if cand.experience.place_id in luoghi_scelti:
                continue  # una tappa per luogo: il luogo è già in itinerario
            trasferimento, _ = _passo(cand, punto_ultimo, prima=not selezionati)
            costo = cand.experience.durata_min + trasferimento
            if tempo_usato + costo > tempo_disponibile_min:
                continue
            # Arrivo come in `_costruisci_stops`: nessun riavvolgimento, perché
            # `tempo_usato + costo` sta nel budget, già troncato alla mezzanotte.
            arrivo = _somma_minuti(ora_partenza, tempo_usato + trasferimento)
            if not aperta_durante(cand.experience, giorno_settimana, arrivo):
                continue  # chiusa in questo slot: come fuori budget, resta tra i rimanenti
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
        trasferimento, punto_ultimo = _passo(cand, punto_ultimo, prima=not selezionati)
        tempo_usato += cand.experience.durata_min + trasferimento
        luoghi_scelti.add(cand.experience.place_id)
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
    lo compone `reason_fn` a partire dai campi di testo del candidato e dai
    segnali rilevanti per quella tappa. `prima_tappa=True` SOLO per la prima
    tappa (arrivo più presto): la frase del profilo compare una volta sola.

    Bagliore (`rules.frase_bagliore`): se `tracce_per_luogo` ha tracce per il
    `place_id` della tappa, il MOTORE aggiunge in modo deterministico una
    frase DOPO `reason_fn` (che riceve esattamente gli stessi argomenti di
    sempre: la frase non passa mai dall'LLM) e PRIMA della disclosure partner,
    che resta l'ultima frase. Le tappe sono GIÀ scelte: il bagliore non
    decide quali, quante né in che ordine. `None`/vuoto o `adesso=None` ->
    nessuna frase, `reason` identico a prima.

    Una sola frase per luogo per itinerario: `_seleziona_tappe` sceglie già
    al più una tappa per `place_id`, ma la guardia resta: se più tappe
    condividessero lo stesso `place_id`, la frase andrebbe SOLO sulla prima
    in ordine di tappa (ripeterla sarebbe rumore, non spiegazione).

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    luoghi_con_frase: set[str] = set()
    progressione = _progressione(selezionati)
    for i, cand in enumerate(selezionati):
        trasferimento, punto_arrivo = progressione[i]
        orario = _somma_minuti(orario, trasferimento)  # 0 per la prima tappa
        segnali = segnali_rilevanti(cand, signal, vocabolario=vocabolario)
        # Le tappe sono già nell'ordine FINALE (arrivi progressivi da
        # `signal.ora`): la prima è quella che arriva più presto, l'unica che
        # porta la frase del profilo. Le code (fluttuanti, eventi promossi)
        # vengono dopo e non la portano mai.
        reason = reason_fn(cand, profile, segnali, prima_tappa=i == 0)
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
                # Titolo leggibile dal catalogo: l'app non mostra mai l'id.
                titolo=cand.experience.titolo,
                # Curiosita' del luogo, dal seed: SOLO narrazione, l'app le
                # mostra sotto il `reason` (che non le contiene). Mai lette
                # dallo scoring (guardia AST in tests/test_scoring_non_legge_curiosita.py).
                curiosita=cand.curiosita,
                arrivo=orario,
                durata_min=cand.experience.durata_min,
                reason=reason,
                # Deciso dal motore (`_passo`); l'app costruisce solo il link.
                punto_arrivo=punto_arrivo,
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
    il trasferimento dalla tappa precedente (`_progressione`, 0 per la prima)
    — lo stesso identico conteggio di `_seleziona_tappe`. È anche il costo con
    cui l'adattamento verifica una sostituzione contro il budget: poiché il
    trasferimento dipende dalla tappa precedente, una sostituzione cambia
    anche quello della tappa successiva, ed è contato qui.

    È una somma, mai una differenza di orari: gli `arrivo` sono `time` senza
    data e oltre la mezzanotte ripartono da 00:00, quindi una differenza
    diventerebbe negativa e le tappe in coda sforerebbero il budget."""
    return sum(
        trasferimento + cand.experience.durata_min
        for cand, (trasferimento, _) in zip(
            selezionati, _progressione(selezionati), strict=True
        )
    )


def _reason_fluttuante(
    segnale: SegnaleFluttuante, place_nome: str, place_articolo: str | None = None
) -> str:
    """`reason` sempre non vuoto (spiegabilità obbligatoria) per una tappa
    fluttuante: racconta COSA (la descrizione dichiarata dal segnale) e DOVE
    (il nome del luogo, se noto tra i candidati, con il suo articolo dal
    dataset via `con_luogo`; altrimenti il `place_id` grezzo senza articolo
    — mai un nome fabbricato)."""
    dove = con_luogo("a", place_articolo, place_nome)
    return f"{segnale.descrizione} {dove}: un'aggiunta per oggi, non era già in programma."


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

    Ogni tappa fluttuante costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessun
    punto di arrivo noto per un segnale, stessa stima prudente di `_passo`
    per una tappa senza punto) e non ha `punto_arrivo` + `DURATA_TAPPA_FLUTTUANTE_MIN`
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
    place_articoli = {c.experience.place_id: c.place_articolo for c in candidates}

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
                # Nessun `titolo`: `SegnaleFluttuante` non ne ha uno, e la sua
                # `descrizione` apre gia' il `reason` (ripeterla non e' un
                # titolo). L'app mostra un'etichetta generica, mai l'id.
                titolo=None,
                # Nessuna curiosita': un segnale fluttuante non e' un luogo
                # del catalogo con curiosita' nel seed.
                curiosita=[],
                arrivo=orario_corrente,
                durata_min=DURATA_TAPPA_FLUTTUANTE_MIN,
                reason=_reason_fluttuante(
                    segnale, place_nome, place_articoli.get(segnale.place_id)
                ),
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


def _reason_evento_promosso(
    evento: EventoPromosso,
    place_nome: str,
    data_visita: date,
    place_articolo: str | None = None,
) -> str:
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
    frase credibile e falsa sarebbe la peggiore forma di inspiegabilità.

    Il luogo è nominato con il suo articolo dal dataset (`con_articolo`:
    "Presso la Chiesa…"); luogo sconosciuto tra i candidati: `place_id`
    grezzo, senza articolo."""
    giorno = giorno_occorrenza_attesa(evento.ultima_occorrenza, evento.cadenza_giorni, data_visita)
    quando = _giorno_relativo_it(giorno, data_visita)
    if giorno < data_visita:
        occorrenza = f"un'occorrenza era attesa {quando}"
    else:
        occorrenza = f"la prossima occorrenza è attesa {quando}"
    luogo = con_articolo(place_articolo, place_nome)
    return (
        f"Presso {luogo} si ripete qualcosa legato a {temi_leggibili(evento.temi)}, "
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

    Ogni tappa-evento costa `TEMPO_TRASFERIMENTO_DEFAULT_MIN` (nessun
    punto di arrivo noto per un `:Evento`, stessa stima prudente di `_passo`
    per una tappa senza punto) e non ha `punto_arrivo` + `DURATA_TAPPA_EVENTO_MIN`.

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
    place_articoli = {c.experience.place_id: c.place_articolo for c in candidates}

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
                # Nessun `titolo`: `EventoPromosso` non ha un campo narrativo
                # (vedi il suo docstring) e un nome fabbricato qui sarebbe
                # inventato. L'app mostra un'etichetta generica, mai l'id.
                titolo=None,
                # Nessuna curiosita': l'evento promosso non porta quelle del
                # luogo (non e' un'esperienza del catalogo).
                curiosita=[],
                arrivo=orario_corrente,
                durata_min=DURATA_TAPPA_EVENTO_MIN,
                reason=_reason_evento_promosso(
                    evento, place_nome, data_visita, place_articoli.get(evento.place_id)
                ),
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
      1. filtri duri etici statici -> `rules.passa_filtri_statici`
         (esperienza sospesa, accessibilità richiesta, luoghi già visti,
         affollamento critico, partner con abbonamento non attivo)
      2. scoring per affinità -> `score_fn` (default: `rules.calcola_score`)
      3. composizione a budget con diversificazione, vincolo "una tappa per
         luogo" (al massimo una esperienza per `place_id`: distribuzione dei
         flussi, due tappe nello stesso luogo concentrano le visite e non
         aggiungono esperienza) e filtro duro 6 (orari,
         `rules.aperta_durante`) all'ARRIVO di ogni slot -> `_seleziona_tappe`
      4. `reason` obbligatorio per ogni tappa -> `_costruisci_stops`
      5. segnali FLUTTUANTI pertinenti, in CODA -> `_aggiungi_tappe_fluttuanti`
      6. eventi PROMOSSI pertinenti, in CODA -> `_aggiungi_tappe_eventi_promossi`

    `score_fn` è INIETTABILE (Wave 3b): il recommender può fornire un ranking
    alternativo. È applicato DOPO i filtri duri statici, mai prima: riceve
    solo i candidati già ammessi da quei vincoli etici, quindi ORDINA ma non
    seleziona né filtra — non può "salvare" un candidato escluso. Il filtro
    sugli orari non può stare prima dello score perché dipende dall'arrivo,
    cioè dallo slot: lo applica `_seleziona_tappe`, e lo score non lo
    scavalca (un candidato chiuso in uno slot è saltato qualunque sia il
    suo punteggio). Se `None`, l'MVP usa
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

    Il vincolo "una tappa per luogo" riguarda le tappe PERMANENTI (passo 3).
    Le code dei passi 5-6 non lo applicano: una tappa fluttuante o un evento
    promosso nello stesso luogo di una tappa permanente si aggiunge comunque
    (comportamento invariato: la regola approvata riguarda le esperienze).

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
        if passa_filtri_statici(c, profile, ctx.signal, ctx.luoghi_gia_visti)
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
    selezionati = _seleziona_tappe(
        valutati,
        budget_effettivo,
        ora_partenza=ctx.signal.ora,
        giorno_settimana=ctx.signal.giorno_settimana,
    )
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
    luoghi_occupati: AbstractSet[str] = frozenset(),
    entra_nel_budget: Callable[[GraphCandidate], bool] | None = None,
    arrivo_di: Callable[[GraphCandidate], time],
    vocabolario: VocabolarioTemi,
    prezzo_tolta: float,
    temi_tolta: Sequence[str],
) -> GraphCandidate | None:
    """Migliore candidato non già usato che rispetta i vincoli del segnale.

    Deterministico: ordinamento (tema condiviso, score, `experience_id`).

    I vincoli DURI vengono da un solo punto, `rules.passa_filtri_duri`
    (esperienza sospesa, accessibilità richiesta dal profilo, affollamento
    critico, partner con abbonamento NON attivo, orari di apertura): gli
    stessi filtri della
    composizione iniziale (`passa_filtri_statici` + `aperta_durante`), così
    una sostituzione in adattamento non può MAI reintrodurre ciò che la
    composizione esclude. L'adattamento non ha luoghi già visti da passare
    (lista vuota). Gli orari sono valutati all'arrivo del CANDIDATO nella
    posizione della tappa tolta: `arrivo_di(c)` (keyword, obbligatorio) lo
    calcola con la progressione di `_ricostruisci_stops`, perché l'arrivo
    dipende dal trasferimento del candidato stesso (`_arrivo_in_posizione`).

    A questi si aggiungono SOLO i vincoli specifici dell'adattamento:
    - `esclusi`: esperienze già presenti nell'itinerario;
    - una tappa per luogo (`luoghi_occupati`): un sostituto non può avere
      il `place_id` di un'ALTRA tappa rimasta nell'itinerario. Il chiamante
      passa i luoghi delle tappe correnti al momento della scelta, ESCLUSA
      la tappa che si sostituisce: facciata -> interno della stessa chiesa
      resta ammesso. Le tappe stub (fluttuanti, eventi promossi, esperienze
      sparite) non occupano luoghi. Default vuoto solo per i test di dominio
      che chiamano la funzione direttamente; `adapt_itinerary` lo passa
      sempre. Motivazione: distribuzione dei flussi —
      due tappe nello stesso luogo concentrano le visite e non aggiungono
      esperienza. Legge solo `place_id`, mai partner, prezzo o attribuzione;
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
      il vincolo di tempo vale identico per ogni candidato;
    - costo: `prezzo_tolta` è il prezzo della tappa tolta (None = 0). Un
      candidato è ammesso solo se `(prezzo_eur or 0) <= prezzo_tolta`: chi
      ha scelto una tappa gratuita non si ritrova a pagare per colpa della
      pioggia o della folla.

    Ordinamento degli ammessi: prima chi condivide almeno un tema con la
    tappa tolta (`temi_tolta`), poi `-calcola_score`, poi `experience_id`.
    Il tema è una preferenza FORTE ma NON un filtro: con la pioggia una
    tappa all'aperto spesso non ha gemelle tematiche al chiuso, e meglio
    un'alternativa di altro tema che nessuna.

    Motivazione etica: il prezzo può solo ESCLUDERE un candidato più caro
    della tappa tolta, mai dare punteggio o favorire un candidato. Tra gli
    ammessi decidono solo tema e score, criteri uguali per tutti, partner
    compresi: nessuno spazio è acquistabile. `partner_id` non è letto.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    temi_set = set(temi_tolta)
    ammessi: list[GraphCandidate] = []
    for c in candidates:
        if not passa_filtri_duri(c, profile, signal, [], arrivo=arrivo_di(c)):
            continue
        e = c.experience
        if e.id in esclusi:
            continue
        if e.place_id in luoghi_occupati:
            continue  # una tappa per luogo: luogo già di un'altra tappa
        if richiede_accessibile and not e.accessibile:
            continue
        if solo_al_chiuso and not e.al_chiuso:
            continue
        if signal.affollamento.get(e.place_id, 0.0) > max_affollamento:
            continue
        if entra_nel_budget is not None and not entra_nel_budget(c):
            continue
        if (e.prezzo_eur or 0.0) > prezzo_tolta:
            continue
        ammessi.append(c)
    if not ammessi:
        return None
    ammessi.sort(
        key=lambda c: (
            not (temi_set & set(c.experience.temi)),
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
       l'itinerario con la sostituzione resta nel budget (vedi sotto) e se
       non costa più della tappa tolta; tra gli ammessi si preferisce chi ne
       condivide un tema (`_migliore_alternativa`). Vincolo "una tappa per
       luogo": il sostituto non può stare nel `place_id` di un'altra tappa
       rimasta (distribuzione dei flussi: due tappe nello stesso luogo
       concentrano le visite e non aggiungono esperienza); il luogo della
       tappa sostituita è ammesso. I luoghi sono quelli delle tappe correnti
       AL MOMENTO della scelta (sostituzioni precedenti comprese), escluse le
       tappe stub. Senza
       alternativa ammissibile la tappa resta, con esito
       `MANTENUTA_SENZA_ALTERNATIVA` e una frase in coda al `reason`.
    2. stanchezza > soglia: taglia le tappe in coda oltre ~2/3 del tempo
       originale (il benessere conta più del numero di tappe); le tappe
       tolte vanno in `tappe_escluse` (`TAGLIATA_STANCHEZZA`).
    3. tetto della giornata: con gli arrivi ricalcolati da `signal.ora`, le
       tappe che finirebbero oltre le 24:00 escono e vanno in
       `tappe_escluse` (`TAGLIATA_TETTO_GIORNATA`). Vale sempre, anche per
       un itinerario senza budget.
    4. sospensione e orari di apertura (`_taglia_fuori_orario`): OGNI tappa
       rimasta con un candidato reale, anche non toccata, è ricontrollata.
       Prima la sospensione (`rules.esperienza_sospesa`): un'esperienza
       diventata `sospesa` dopo la composizione esce in `tappe_escluse`
       (`TAGLIATA_SOSPESA`), anche se fosse pure fuori orario. Poi gli orari
       (`rules.aperta_durante`, filtro duro 6) sull'arrivo che il visitatore
       vedrà: le tappe chiuse per [arrivo, arrivo + durata] escono in
       `tappe_escluse` (`TAGLIATA_ORARIO`). Timeline, uguale per i due tagli:
       se i passi 1-3 non hanno cambiato nulla si usano gli arrivi RICEVUTI;
       se lì una tappa esce, le restanti sono rivalutate sugli arrivi
       ricalcolati da `signal.ora`. Se i passi 1-3 hanno cambiato qualcosa,
       un solo passaggio in ordine da `signal.ora`, dove l'arrivo di ogni
       tappa dipende dalle sole tappe TENUTE prima di lei. Le tappe stub
       (fluttuanti, eventi promossi) non hanno orari né `sospesa` e non
       escono mai a questo passo. Un taglio per sospensione o per orario
       accende `adattato_da_segnale`.

    Filtri statici e tappe MANTENUTE: le tappe che restano (non toccate o
    mantenute senza alternativa) ripassano la sospensione e gli orari
    (passo 4), non gli altri filtri statici (accessibilità, luoghi già
    visti, affollamento critico, partner non attivo): quelli li ripassano
    solo i SOSTITUTI (`_migliore_alternativa` -> `rules.passa_filtri_duri`).
    La sospensione è letta con la stessa funzione di
    `rules.passa_filtri_statici` (`rules.esperienza_sospesa`): un solo punto
    la interpreta.

    Sostituzioni e orari: il sostituto in posizione i è scelto sull'arrivo
    che il visitatore vedrà, `signal.ora + _minuti_usati_permanenti(
    tappe[:i]) + trasferimento(sostituto)` (`_arrivo_in_posizione`); un
    taglio successivo può solo anticiparlo, e il passo 4 lo ricontrolla.

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
    una tappa è sostituita o tagliata (stanchezza, tetto, sospensione o
    orario). Se
    nessuna lo è, gli arrivi restano quelli ricevuti e cambiano solo
    `reason` ed esito; altrimenti gli arrivi
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

    # Titolo di una tappa (presente o esclusa) per `experience_id`: dal
    # catalogo se il candidato e' noto (anche se la tappa ricevuta non ne
    # aveva uno: itinerario vecchio); altrimenti quello ricevuto, anche None
    # (stub: "non riscrivere al buio").
    titoli_ricevuti: dict[str, str | None] = {
        t.experience_id: t.titolo for t in itinerary.tappe_escluse
    }
    titoli_ricevuti.update({s.experience_id: s.titolo for s in itinerary.stops})

    def titolo_di(experience_id: str) -> str | None:
        noto = per_id.get(experience_id)
        if noto is not None:
            return noto.experience.titolo
        return titoli_ricevuti.get(experience_id)

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
        # Arrivo che il visitatore VEDRÀ se il candidato entra in posizione i:
        # stessa progressione di `_ricostruisci_stops`, da `signal.ora`.
        arrivo_di = partial(
            _arrivo_in_posizione, ora_partenza=signal.ora, precedenti=correnti[:i]
        )
        # Una tappa per luogo: luoghi delle ALTRE tappe correnti in questo
        # momento (le sostituzioni già fatte contano), esclusa la i-esima che
        # si sostituisce. Gli stub non hanno un luogo reale: il loro
        # `place_id` fittizio è l'`experience_id`, e non entra nell'insieme.
        luoghi_occupati = {
            c.experience.place_id
            for j, c in enumerate(correnti)
            if j != i and not c.senza_candidato
        }
        alt = _migliore_alternativa(
            candidates=candidates,
            signal=signal,
            profile=profilo_effettivo,
            esclusi=usati,
            luoghi_occupati=luoghi_occupati,
            richiede_accessibile=richiede_accessibile,
            solo_al_chiuso=piove_e_aperto,
            max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
            entra_nel_budget=entra_nel_budget,
            arrivo_di=arrivo_di,
            vocabolario=vocabolario,
            prezzo_tolta=e.prezzo_eur or 0.0,
            temi_tolta=e.temi,
        )
        if alt is None:
            # Nessuna alternativa ammissibile (vincoli duri, segnale, budget):
            # la tappa resta e lo dice, prima della disclosure partner.
            frase = _frase_esito(
                EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
                motivo="pioggia" if piove_e_aperto else "affollamento",
                luogo=cand.place_nome,
                articolo=cand.place_articolo,
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
        # Motivo SPECIFICO del sostituto, composto come quello di una tappa
        # non prima (la frase del profilo la aggiunge, al più una volta e
        # solo se il sostituto risulta PRIMA tappa, `_con_frase_profilo` dopo
        # i tagli) e senza segnali (il segnale è già detto da "Sostituita per
        # ..."). `connessioni` alimentano solo il punteggio, non il testo.
        motivo = fn(alt, profilo_effettivo, [], prima_tappa=False)
        if piove_e_aperto:
            segnale = "la pioggia"
        else:
            segnale = "l'affollamento " + con_luogo("a", cand.place_articolo, cand.place_nome)
        alt_reason = adapt_fn(motivo, segnale)
        correnti[i] = _marca_reason(
            alt, alt_reason, EsitoAdattamento.SOSTITUITA, stop.experience_id,
            segnale_sostituzione=segnale,
        )
        sostituite = True

    nuove_escluse: list[TappaEsclusa] = []

    # 2. Stanchezza alta: taglia la coda oltre ~2/3 del tempo originale.
    if signal.stanchezza > SOGLIA_STANCHEZZA_ALTA:
        tenuti = _taglia_per_stanchezza(itinerary, correnti)
        nuove_escluse.extend(
            _escludi(c, EsitoAdattamento.TAGLIATA_STANCHEZZA, titolo_di)
            for c in correnti[len(tenuti):]
        )
        correnti = tenuti

    # 3. Tetto della giornata, sugli arrivi ricalcolati da `signal.ora`.
    entro = _entro_la_giornata(correnti, minuti_mezzanotte)
    nuove_escluse.extend(
        _escludi(c, EsitoAdattamento.TAGLIATA_TETTO_GIORNATA, titolo_di)
        for c in correnti[len(entro):]
    )
    correnti = entro

    # 4. Sospensione, poi orari di apertura sull'arrivo che il visitatore
    # VEDRÀ (vedi la docstring: arrivi ricevuti se nulla è cambiato,
    # altrimenti da `signal.ora`). Le tappe tolte non spostano mai in avanti
    # le successive: il tetto della giornata del passo 3 resta rispettato.
    cambiato_prima = sostituite or bool(nuove_escluse)
    correnti, tolte = _taglia_fuori_orario(
        correnti,
        signal,
        arrivi_ricevuti=None if cambiato_prima else [s.arrivo for s in itinerary.stops],
    )
    nuove_escluse.extend(_escludi(c, esito, titolo_di) for c, esito in tolte)

    # 5. Frase del profilo: al più una volta, sulla PRIMA tappa del risultato
    # e solo se è SOSTITUITA (le non toccate e le mantenute conservano il
    # `reason` ricevuto) e se nessun'altra tappa ne porta già una (es. reason
    # ricevuti nel formato vecchio). Serve il profilo della richiesta: senza,
    # nessuna frase.
    if profile is not None and correnti:
        correnti[0] = _con_frase_profilo(
            correnti[0], profile, fn, adapt_fn, per_id, altre=correnti[1:]
        )

    # Un taglio per sospensione o per orario aggiunge una voce a
    # `nuove_escluse`, quindi accende `cambiato`.
    cambiato = sostituite or bool(nuove_escluse)

    if cambiato:
        stops = _ricostruisci_stops(
            correnti, profilo_effettivo, signal, fn, vocabolario=vocabolario
        )
    else:
        # Nessuna tappa sostituita o tagliata: arrivi INVARIATI, cambiano
        # solo reason ed esito (stessa lunghezza e stesso ordine). Il punto di
        # arrivo è ricalcolato dal catalogo (`_progressione`), come il titolo.
        stops = [
            stop.model_copy(
                update={
                    "reason": _reason_finale(
                        c, c.reason_deciso or stop.reason, profilo_effettivo, signal, fn,
                        vocabolario=vocabolario,
                    ),
                    "esito_adattamento": c.esito_deciso,
                    "punto_arrivo": _punto_in_uscita(c, punto),
                    **_narrazione_tappa(c),
                }
            )
            for stop, c, (_, punto) in zip(
                itinerary.stops, correnti, _progressione(correnti), strict=True
            )
        ]

    return Itinerary(
        person_id=itinerary.person_id,
        stops=stops,
        generated_at=datetime.now() if cambiato else itinerary.generated_at,
        adattato_da_segnale=cambiato,
        tempo_disponibile_min=itinerary.tempo_disponibile_min,
        tempo_effettivo_min=itinerary.tempo_effettivo_min,
        tappe_escluse=_unisci_escluse(
            itinerary.tappe_escluse, nuove_escluse, stops, titolo_di
        ),
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
#: Il luogo segue il prefisso con la sua preposizione articolata
#: (`con_luogo("a", articolo, nome)`: "alla Torre…", "all'Orto…", "a Via…").
_PREFISSO_MANTENUTA_AFFOLLAMENTO = "C'è molta gente "
_SUFFISSO_MANTENUTA_AFFOLLAMENTO = (
    ", ma non c'è un'alternativa più tranquilla compatibile con questo percorso "
    "e con il tempo a disposizione: la tappa resta in programma."
)
_FRASE_TAGLIATA_STANCHEZZA = "Tolta per la stanchezza: meglio una giornata più leggera."
_FRASE_TAGLIATA_TETTO = (
    "Non c'è più tempo oggi per questa tappa: la giornata finisce a mezzanotte."
)
_FRASE_TAGLIATA_ORARIO = (
    "Tolta: all'ora in cui ci arriveresti il luogo è chiuso, "
    "o chiude prima della fine della visita."
)
_FRASE_TAGLIATA_SOSPESA = "Tolta: in questo periodo il luogo è chiuso."

#: Preposizioni che possono seguire il prefisso: "a" semplice (luogo senza
#: articolo, e forma VECCHIA "C'è molta gente a <nome>" degli itinerari
#: ricevuti) e le sue articolate (`contracts.preposizione_articolata`).
_PREPOSIZIONI_A = ("a ", "al ", "allo ", "alla ", "all'", "ai ", "agli ", "alle ")

#: Riconosce la frase di affollamento qualunque sia il luogo e la sua
#: preposizione (vecchia "a <nome>" o con articolo "alla <nome>"). Il luogo è
#: "temperato": non può contenere di nuovo il prefisso, così la corrispondenza
#: parte dall'ultima occorrenza utile e non inghiotte testo del reason.
_RE_MANTENUTA_AFFOLLAMENTO = re.compile(
    " ?"
    + re.escape(_PREFISSO_MANTENUTA_AFFOLLAMENTO)
    + "(?:"
    + "|".join(re.escape(p) for p in _PREPOSIZIONI_A)
    + ")"
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
    articolo: str | None = None,
) -> str | None:
    """Frase in italiano che racconta l'esito dell'adattamento di una tappa.

    UNICA funzione da cui nascono le frasi di esito, così campo e testo non
    possono divergere:
    - `MANTENUTA_SENZA_ALTERNATIVA`: frase della pioggia (anche se il luogo è
      pure affollato) o dell'affollamento a `luogo` (con la preposizione
      articolata dal suo `articolo`, `con_luogo`); va in coda al `reason`,
      prima della disclosure partner;
    - `TAGLIATA_STANCHEZZA` / `TAGLIATA_TETTO_GIORNATA` / `TAGLIATA_ORARIO` /
      `TAGLIATA_SOSPESA`: `reason` della `TappaEsclusa`;
    - `NON_TOCCATA` / `SOSTITUITA`: nessuna frase (`None`); la sostituita ha
      il proprio `reason` di sostituzione."""
    if esito is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA:
        if motivo == "pioggia":
            return _FRASE_MANTENUTA_PIOGGIA
        dove = con_luogo("a", articolo, luogo)
        return f"{_PREFISSO_MANTENUTA_AFFOLLAMENTO}{dove}{_SUFFISSO_MANTENUTA_AFFOLLAMENTO}"
    if esito is EsitoAdattamento.TAGLIATA_STANCHEZZA:
        return _FRASE_TAGLIATA_STANCHEZZA
    if esito is EsitoAdattamento.TAGLIATA_TETTO_GIORNATA:
        return _FRASE_TAGLIATA_TETTO
    if esito is EsitoAdattamento.TAGLIATA_ORARIO:
        return _FRASE_TAGLIATA_ORARIO
    if esito is EsitoAdattamento.TAGLIATA_SOSPESA:
        return _FRASE_TAGLIATA_SOSPESA
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
    #: Solo per gli stub (`senza_candidato`): il `titolo` della tappa
    #: ricevuta, conservato com'e' (anche None).
    titolo_ricevuto: str | None = None
    #: Solo per le tappe `SOSTITUITA`: il segnale detto da "Sostituita per
    #: ..." ("la pioggia", "l'affollamento alla ..."), per ricomporre il
    #: `reason` con la frase del profilo (`_con_frase_profilo`).
    segnale_sostituzione: str | None = None
    #: Solo per gli stub (`senza_candidato`): il `punto_arrivo` della tappa
    #: ricevuta, conservato com'e' nella risposta ("non riscrivere al buio").
    #: Non entra MAI nelle distanze: uno stub non ha `punti_arrivo`, quindi il
    #: suo trasferimento (e quello della tappa dopo) resta la stima prudente.
    punto_ricevuto: Punto | None = None


def _punto_in_uscita(cand: _CandidatoConReason, punto: Punto | None) -> Punto | None:
    """`punto_arrivo` della tappa restituita: quello scelto da `_progressione`
    per un candidato reale (il catalogo vince sul client), quello ricevuto per
    uno stub."""
    return cand.punto_ricevuto if cand.senza_candidato else punto


def _titolo_tappa(cand: _CandidatoConReason) -> str | None:
    """Titolo della tappa che `cand` occupa: dal catalogo
    (`ExperienceNode.titolo`) se il candidato e' reale; per uno stub quello
    ricevuto (il `titolo` dell'`ExperienceNode` fantasma e' l'id, mai da
    mostrare)."""
    if cand.senza_candidato:
        return cand.titolo_ricevuto
    return cand.experience.titolo


def _narrazione_tappa(cand: _CandidatoConReason) -> dict[str, Any]:
    """Campi di SOLA narrazione della tappa che `cand` occupa (`titolo` e
    curiosita' del luogo), per l'aggiornamento di una tappa ricevuta.

    Le curiosita' vengono da `cand.curiosita`: per un candidato noto e' il
    catalogo (vince sul client), per uno stub quelle ricevute (copiate da
    `_stub_da_stop`). Sta in una funzione a parte perche' la guardia AST
    (tests/test_scoring_non_legge_curiosita.py) ammette letture delle
    curiosita' solo nei costruttori di tappe, mai in `adapt_itinerary` o nelle
    funzioni che scelgono e ordinano."""
    return {"titolo": _titolo_tappa(cand), "curiosita": list(cand.curiosita)}


def _marca_reason(
    cand: GraphCandidate,
    reason: str,
    esito: EsitoAdattamento,
    id_originale: str,
    *,
    segnale_sostituzione: str | None = None,
) -> _CandidatoConReason:
    dati = cand.model_dump()
    for campo in (
        "reason_deciso", "esito_deciso", "id_originale", "senza_candidato", "titolo_ricevuto",
        "segnale_sostituzione", "punto_ricevuto",
    ):
        dati.pop(campo, None)
    return _CandidatoConReason(
        **dati, reason_deciso=reason, esito_deciso=esito, id_originale=id_originale,
        segnale_sostituzione=segnale_sostituzione,
    )


def _con_frase_profilo(
    cand: _CandidatoConReason,
    profile: EmotionalProfile,
    reason_fn: ReasonFn,
    adapt_fn: AdaptReasonFn,
    per_id: dict[str, GraphCandidate],
    *,
    altre: Sequence[_CandidatoConReason],
) -> _CandidatoConReason:
    """Aggiunge la frase del profilo al `reason` della PRIMA tappa
    dell'itinerario adattato, SOLO se quella tappa è `SOSTITUITA`:
    "Sostituita per la pioggia. <Frase profilo>. <resto del motivo>.".

    La frase la scrive `reason_fn` con `prima_tappa=True` (il motore non
    conosce i testi della RAG): il motivo del sostituto è ricomposto così e
    ripassato da `adapt_fn` con lo stesso segnale. Ogni altro esito è
    restituito intatto: una `NON_TOCCATA` conserva il `reason` ricevuto
    (invariante del contratto, anche se è diventata prima perché l'originale
    è stata tagliata), una `MANTENUTA_SENZA_ALTERNATIVA` conserva il suo e
    aggiunge solo la frase di esito. Profilo senza tratto netto né flag:
    `reason_fn` non aggiunge nulla e il `reason` resta quello deciso. Se il
    motivo senza frase la contenesse già, non la si ripete.

    `altre`: le ALTRE tappe del risultato. Se una di esse porta già una
    qualunque frase del profilo (`_contiene_frase_profilo`, anche di un altro
    profilo: es. `reason` ricevuti nel formato vecchio, conservati per
    contratto), non se ne aggiunge un'altra: al più una volta per itinerario."""
    if (
        cand.esito_deciso is not EsitoAdattamento.SOSTITUITA
        or cand.senza_candidato
        or cand.segnale_sostituzione is None
        or any(_contiene_frase_profilo(a.reason_deciso or "") for a in altre)
    ):
        return cand
    originale = per_id.get(cand.experience.id)
    if originale is None:
        return cand
    motivo_con = reason_fn(originale, profile, [], prima_tappa=True)
    motivo_senza = reason_fn(originale, profile, [], prima_tappa=False)
    if motivo_con == motivo_senza:
        return cand  # nessun tratto netto né flag: nessuna frase
    if motivo_con.endswith(motivo_senza):
        frase = motivo_con[: len(motivo_con) - len(motivo_senza)].strip()
        if not frase or frase.lower() in motivo_senza.lower():
            return cand  # la frase c'è già nel motivo: non si ripete
    nuovo = adapt_fn(motivo_con, cand.segnale_sostituzione)
    return cand.model_copy(update={"reason_deciso": nuovo})


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
        titolo_ricevuto=stop.titolo,
        # Stub: si conservano le curiosita' ricevute ("non riscrivere al
        # buio"), come il titolo. Per un candidato NOTO vince invece il
        # catalogo (`_marca_reason` copia `cand.curiosita`): il client non
        # puo' iniettare curiosita' sue in una tappa del catalogo.
        curiosita=stop.curiosita,
        punto_ricevuto=stop.punto_arrivo,
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
    mai differenze di orari: il trasferimento della tappa SUCCESSIVA è
    ricalcolato dal punto di arrivo dell'alternativa. Legge solo durata e
    punti di arrivo: nessun partner, nessun prezzo."""
    ipotesi = [*correnti[:indice], alternativa, *correnti[indice + 1 :]]
    return _minuti_usati_permanenti(ipotesi) <= limite


def _taglia_per_stanchezza(
    itinerary: Itinerary, correnti: list[_CandidatoConReason]
) -> list[_CandidatoConReason]:
    """Mantiene le tappe di testa il cui tempo totale è il più vicino ai 2/3
    del tempo originale (prefisso).

    - `limite` = `int(2/3 * somma delle durate dell'itinerario RICEVUTO)`
      (`itinerary.stops`, cioè PRIMA delle sostituzioni di questo adattamento);
      il tempo è invece sommato sulle durate di `correnti`, cioè DOPO le
      sostituzioni (una tappa sostituita conta con la durata del sostituto).
      Solo durate di visita: i trasferimenti non entrano nel conto.
    - Scorrendo in ordine, la tappa successiva si TIENE se il totale che la
      include è strettamente più vicino al limite di quello che la esclude
      (`|incl - limite| < |escl - limite|`); a parità di distanza si ESCLUDE.
      Al primo escluso ci si ferma: il risultato è sempre un prefisso, mai si
      salta una tappa per tenerne una successiva.
    - Almeno una tappa resta sempre: se la prima da sola supera il limite
      (anche di oltre il doppio, caso in cui la regola la escluderebbe) è
      comunque tenuta, e solo lei.

    Le tappe di coda sono le meno affini (l'itinerario è ordinato per score in
    composizione): tagliarle riduce lo sforzo senza sacrificare il meglio."""
    durata_originale = sum(s.durata_min for s in itinerary.stops)
    limite = int(durata_originale * 2 / 3)
    tenuti: list[_CandidatoConReason] = []
    tempo = 0
    for cand in correnti:
        incluso = tempo + cand.experience.durata_min
        if abs(incluso - limite) >= abs(tempo - limite):
            break
        tenuti.append(cand)
        tempo = incluso
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


def _arrivo_in_posizione(
    candidato: GraphCandidate,
    *,
    ora_partenza: time,
    precedenti: Sequence[GraphCandidate],
) -> time:
    """Arrivo di `candidato` se viene dopo `precedenti` in un itinerario che
    parte a `ora_partenza`: `ora_partenza + _minuti_usati_permanenti(precedenti)
    + trasferimento(candidato)` (trasferimento dal punto di arrivo dell'ultima
    dei `precedenti`, `_passo`; 0 se è la prima tappa). È la
    STESSA progressione di `_ricostruisci_stops` e di `_costruisci_stops`:
    l'arrivo valutato dagli orari è quello che il visitatore vedrà.

    Riavvolge oltre la mezzanotte come `_somma_minuti`: con un budget
    (`tempo_effettivo_min`) non succede mai, perché il limite delle
    sostituzioni è già troncato alla mezzanotte; senza budget (JSON
    precedenti al campo) una tappa oltre le 24:00 è comunque tolta dal tetto
    della giornata (passo 3 di `adapt_itinerary`)."""
    minuti = _minuti_usati_permanenti(precedenti)
    if precedenti:
        punto_precedente = _progressione(precedenti)[-1][1]
        minuti += _passo(candidato, punto_precedente, prima=False)[0]
    return _somma_minuti(ora_partenza, minuti)


def _taglia_fuori_orario(
    correnti: list[_CandidatoConReason],
    signal: Signal,
    *,
    arrivi_ricevuti: list[time] | None,
) -> tuple[list[_CandidatoConReason], list[tuple[_CandidatoConReason, EsitoAdattamento]]]:
    """Passo 4 di `adapt_itinerary`: OGNI tappa con un candidato reale (anche
    non toccata dal segnale) è ricontrollata, in quest'ordine:
    1. sospensione (`rules.esperienza_sospesa`): se l'esperienza è sospesa
       esce con `TAGLIATA_SOSPESA`, qualunque sia il suo arrivo e anche se
       fosse pure fuori orario;
    2. orari (`rules.aperta_durante`) sull'arrivo che il visitatore vedrà:
       se è chiusa esce con `TAGLIATA_ORARIO`.
    Restituisce (tappe tenute, tappe tolte con il loro esito), entrambe
    nell'ordine dell'itinerario.

    Timeline (identica per i due tagli: entrambi liberano tempo):
    - `arrivi_ricevuti` non `None` (nulla è cambiato ai passi 1-3: gli arrivi
      restituiti sarebbero quelli ricevuti): ogni tappa è valutata al SUO
      arrivo ricevuto. Se nessuna esce, nulla cambia. Se almeno una esce
      (sospesa o chiusa), quelle tappe sono tolte, l'itinerario diventa
      "cambiato" e si prosegue come sotto sulle restanti (gli arrivi saranno
      ricalcolati da `signal.ora`, quindi vanno rivalutati lì).
    - altrimenti (o dopo il caso sopra): UN solo passaggio in ordine, con
      l'arrivo di ogni tappa calcolato da `signal.ora` sulle sole tappe
      TENUTE prima di lei (`_arrivo_in_posizione`, la progressione di
      `_ricostruisci_stops`). Togliere una tappa anticipa le successive, che
      sono valutate già al nuovo arrivo.
    Così ogni tappa restituita non è sospesa ed è aperta all'arrivo con cui
    viene restituita.

    Le tappe stub (senza candidato: fluttuanti, eventi promossi, esperienze
    sparite) non hanno orari né `sospesa` e non sono mai tolte; contano però
    nella timeline. Senza esperienze sospese, con `orari_apertura` vuoti o
    `signal.giorno_settimana` `None` nessuna tappa è mai tolta: comportamento
    identico a prima."""
    giorno = signal.giorno_settimana

    def esito_uscita(cand: _CandidatoConReason, arrivo: time) -> EsitoAdattamento | None:
        if cand.senza_candidato:
            return None
        if esperienza_sospesa(cand.experience):
            return EsitoAdattamento.TAGLIATA_SOSPESA
        if not aperta_durante(cand.experience, giorno, arrivo):
            return EsitoAdattamento.TAGLIATA_ORARIO
        return None

    esiti: dict[int, EsitoAdattamento] = {}  # id(candidato) -> esito di uscita
    restanti = correnti
    if arrivi_ricevuti is not None:
        for cand, arrivo in zip(correnti, arrivi_ricevuti, strict=True):
            esito = esito_uscita(cand, arrivo)
            if esito is not None:
                esiti[id(cand)] = esito
        if not esiti:
            return correnti, []
        restanti = [c for c in correnti if id(c) not in esiti]

    tenuti: list[_CandidatoConReason] = []
    for cand in restanti:
        if not cand.senza_candidato:
            arrivo = _arrivo_in_posizione(cand, ora_partenza=signal.ora, precedenti=tenuti)
            esito = esito_uscita(cand, arrivo)
            if esito is not None:
                esiti[id(cand)] = esito
                continue
        tenuti.append(cand)

    # Tolte nell'ordine dell'itinerario ricevuto (gli oggetti sono distinti).
    tolte = [(c, esiti[id(c)]) for c in correnti if id(c) in esiti]
    return tenuti, tolte


def _esclusa_canonica(
    experience_id: str, esito: EsitoAdattamento, titolo: str | None
) -> TappaEsclusa:
    """`TappaEsclusa` col `reason` del motore, ricavato SOLO dall'esito
    (`_frase_esito`): nessun testo libero arrivato dal client sopravvive.
    `titolo`: dal catalogo se l'esperienza e' nota, altrimenti quello
    ricevuto (vedi `titolo_di` in `adapt_itinerary`)."""
    frase = _frase_esito(esito)
    if frase is None:
        raise ValueError(f"esito {esito.value!r} non è un esito di taglio")
    return TappaEsclusa(experience_id=experience_id, titolo=titolo, esito=esito, reason=frase)


def _escludi(
    cand: _CandidatoConReason,
    esito: EsitoAdattamento,
    titolo_di: Callable[[str], str | None],
) -> TappaEsclusa:
    """`TappaEsclusa` per una tappa tolta (stanchezza, tetto, sospensione,
    orario): in
    `tappe_escluse` finisce la tappa che il visitatore aveva
    (`id_originale`), non la sua eventuale sostituta."""
    experience_id = cand.id_originale or cand.experience.id
    return _esclusa_canonica(experience_id, esito, titolo_di(experience_id))


def _unisci_escluse(
    precedenti: list[TappaEsclusa],
    nuove: list[TappaEsclusa],
    stops: list[ItineraryStop],
    titolo_di: Callable[[str], str | None],
) -> list[TappaEsclusa]:
    """Accumula le tappe escluse tra adattamenti: una sola voce per
    `experience_id`, vince la più recente (che va in fondo). Nessun tetto di
    lunghezza. Un'esperienza tornata tra le tappe non è più esclusa.

    Vale per ogni esito di taglio, `TAGLIATA_ORARIO` e `TAGLIATA_SOSPESA`
    compresi.

    Il `reason` di OGNI voce è rigenerato dall'esito (`_esclusa_canonica`):
    le esclusioni ricevute dal client portano un testo libero, e il testo
    restituito dev'essere sempre quello del motore."""
    unite: dict[str, TappaEsclusa] = {}
    for tappa in [*precedenti, *nuove]:
        unite.pop(tappa.experience_id, None)
        unite[tappa.experience_id] = _esclusa_canonica(
            tappa.experience_id, tappa.esito, titolo_di(tappa.experience_id)
        )
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
        # `prima_tappa=False`: in adattamento la frase del profilo resta dove
        # l'aveva già il `reason` ricevuto, o la aggiunge `_con_frase_profilo`
        # alla prima tappa SOSTITUITA (al più una volta).
        finale = _con_disclosure(reason_fn(cand, profile, segnali, prima_tappa=False), cand)
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
    Trasferimenti e punti di arrivo vengono da `_progressione`, come in
    composizione: una tappa sostituita cambia anche il trasferimento e il
    punto di arrivo della successiva.

    `vocabolario`: vocabolario dei temi della città, dato del dataset; il
    motore non ne ha uno proprio."""
    stops: list[ItineraryStop] = []
    orario = signal.ora
    progressione = _progressione(correnti)
    for i, cand in enumerate(correnti):
        trasferimento, punto_arrivo = progressione[i]
        orario = _somma_minuti(orario, trasferimento)  # 0 per la prima tappa
        reason = _reason_finale(
            cand, cand.reason_deciso or "", profile, signal, reason_fn, vocabolario=vocabolario
        )
        stops.append(
            ItineraryStop(
                experience_id=cand.experience.id,
                titolo=_titolo_tappa(cand),
                curiosita=cand.curiosita,
                arrivo=orario,
                durata_min=cand.experience.durata_min,
                reason=reason,
                esito_adattamento=cand.esito_deciso or EsitoAdattamento.NON_TOCCATA,
                punto_arrivo=_punto_in_uscita(cand, punto_arrivo),
            )
        )
        orario = _somma_minuti(orario, cand.experience.durata_min)
    return stops
