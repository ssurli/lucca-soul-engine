"""Ranking del Recommender — `score_fn` compatibile con
`experience_engine.engine.ScoreFn` (Wave 3b).

VINCOLO CENTRALE DI QUESTA WAVE: la funzione obiettivo NON è la pertinenza.
È PERTINENZA VINCOLATA A DISTRIBUZIONE DEI FLUSSI. `calcola_score` (riusato
da `experience_engine.rules`, mai duplicato) misura l'affinità profilo <->
esperienza; questo modulo la corregge con DUE penalità indipendenti, sempre
sul LUOGO (`place_id`, non la singola esperienza):

1. **Quota storica** (`_quota_storica_per_place`): quanto quel luogo ha già
   concentrato flusso storico REALE, misurato solo da `BehaviorEvent`
   aggregati sulla piattaforma propria.
2. **Quota strutturale** (`_quota_strutturale_per_place`): quanto quel luogo
   domina per PERTINENZA DI CONTENUTO attraverso profili diversi, calcolata
   in modo puramente deterministico e locale (nessun `BehaviorEvent`, nessun
   dato esterno) su un insieme fisso di archetipi (vedi sotto).

Il secondo termine esiste per una falla diagnosticata: un luogo con ZERO
eventi tracciati ma altissima pertinenza di contenuto attraverso profili
diversi (nel dataset della città di riferimento, una chiesa romanica) può assorbire il flusso
liberato dalla penalizzazione di un luogo storicamente concentrato, perché
`_seleziona_tappe` (in `experience_engine.engine`, NON toccato da questo
modulo) riempie ogni slot di budget liberato con il MIGLIOR candidato per
punteggio, e un luogo a zero eventi non riceve alcuna penalità dalla sola
quota storica. "Essere scelto un terzo delle volte è concentrazione, anche
senza un solo evento" — da qui il termine strutturale.

Non si ottimizza mai click, conversioni, prenotazioni, valore delle
commissioni, permanenza nell'app — e nessun segnale di notorietà esterna
(rating/recensioni di provider terzi) o di Urban Memory/Index entra qui: solo
`BehaviorEvent` (per la quota storica) e `calcola_score` su archetipi fissi
(per la quota strutturale) — vedi `recommender.features` e il README del
servizio.

Il grafo/place_id non arrivano da un import di `services/graph`: la mappa
`experience_id -> place_id` è costruita SOLO dai `GraphCandidate` ricevuti a
runtime per QUESTA richiesta (`candidati_correnti`), mai da un join/import
del grafo — questo modulo non importa `graph`.

LIMITE NOTO (documentato anche nel README): questa è una correzione LOCALE,
per-richiesta. Non può garantire matematicamente che una metrica di
distribuzione aggregata su una POPOLAZIONE di richieste non peggiori mai —
non la garantisce e non la elimina il rischio di regressione. Nella
configurazione finale (con il gating sotto) B >= A vale in 34 storici
casuali su 40, meno dei 38 su 40 della versione precedente a questa
correzione: il gating migliora la distribuzione media ma non e' monotono.

CORREZIONE PROVVISORIA "GATING PER PRESSIONE DI CONTENUTO" (ondata 1b-2,
candidata G3). Il termine STORICO di ogni luogo e' moltiplicato per
`min(1, esposizione / (FATTORE_SOGLIA_ESPOSIZIONE / N))`, dove `esposizione`
e' la quota con cui il luogo compare nei primi `K_ESPOSIZIONE_TOP` (3) per
ciascuno dei 6 `ARCHETIPI_STRUTTURALI`, con segnale neutro, e `N` e' il
numero di luoghi tra i candidati correnti. Idea: uno storico alto su un
luogo che il CONTENUTO non spinge verso i primi posti di nessun archetipo
e' scontato meno ("effetto gregge": penalizzare un luogo gia' frequentato
che il ranking per pertinenza non avrebbe comunque proposto sposta il
flusso su altri luoghi senza ridurre la concentrazione). Il gating non
introduce penalita' nuove e non supera mai il termine storico originale:
i pesi (0.3 / 0.2) e `LIMITE_PESO_COMBINATO_MAX` sono invariati.

Limiti dichiarati, senza abbellimenti:

- L'esposizione dipende dai 6 archetipi del recommender, NON dal profilo del
  visitatore reale: due visitatori diversi vedono lo stesso gating.
- E' una correzione PROVVISORIA dell'"effetto gregge", da riprogettare dopo
  la demo. I parametri (k=3, fattore 2) sono quelli simulati, non tarati.
- Non garantisce B >= A su qualunque storico: nella batteria di 40 storici
  casuali della configurazione finale B >= A vale in 34 casi su 40 (vedi
  `scripts/misura_concentrazione_recommender.py`, non e' un test).
- Rischio: un luogo molto frequentato ma poco spinto dal contenuto viene
  scoraggiato MENO di prima, quindi puo' restare congestionato.

Il recommender ORDINA, non filtra: nessun luogo e nessuna esperienza esce
dalla lista, e nessun campo commerciale (`partner_id`, `prezzo_eur`,
`partner_abbonamento_attivo`, `prenotabile`, attribuzione) e' letto.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import time

from contracts import EmotionalProfile, GraphCandidate, Signal, VocabolarioTemi
from experience_engine.rules import calcola_score

from .repository import BehaviorEventRepository

__all__ = [
    "ScoreFn",
    "PESO_STORICO_DEFAULT",
    "PESO_STRUTTURA_DEFAULT",
    "LIMITE_PESO_COMBINATO_MAX",
    "SOGLIA_MINIMA_EVENTI_MAPPABILI",
    "ALPHA_LAPLACE",
    "ARCHETIPI_STRUTTURALI",
    "SEGNALE_NEUTRO_STRUTTURALE",
    "K_ESPOSIZIONE_TOP",
    "FATTORE_SOGLIA_ESPOSIZIONE",
    "costruisci_score_fn",
]

#: Alias locale della stessa firma di `experience_engine.engine.ScoreFn`
#: (`Callable[[GraphCandidate, EmotionalProfile, Signal], float]`). Non è una
#: firma alternativa: è duplicata qui SOLO perché questo pacchetto non importa
#: `experience_engine.engine` (importa solo `experience_engine.rules.
#: calcola_score`, come prescritto) e quindi non può riferirsi al tipo
#: originale senza allargare la superficie di import. Il BFF passa il
#: risultato di `costruisci_score_fn(...)` come `score_fn` a
#: `experience_engine.compose_itinerary`: la compatibilità è strutturale
#: (stessi tipi di parametro e di ritorno), non nominale.
ScoreFn = Callable[[GraphCandidate, EmotionalProfile, Signal], float]

#: Costante di smoothing additivo (Laplace / "add-one"), applicata alla
#: quota storica per `place_id`. Senza smoothing un luogo SENZA eventi
#: tracciati riceve quota = 0, cioè "rischio zero, penalità zero": è
#: esattamente la falla diagnosticata (un luogo a zero eventi ma altissima
#: pertinenza di contenuto assorbe il flusso spostato dalla penalizzazione
#: di un luogo concentrato, senza mai essere penalizzato a sua volta).
#: `alpha = 1.0` è il valore standard del Laplace smoothing: equivale ad
#: assegnare a OGNI luogo tra i candidati correnti uno "pseudo-conteggio" di
#: un singolo evento in più, il minimo che basta a rendere non-nulla la
#: quota di un luogo a zero eventi, senza distorcere in modo percepibile la
#: quota di un luogo con uno storico reale già consistente (l'effetto dello
#: pseudo-conteggio si diluisce con `alpha / (totale + alpha * N)`, quindi
#: diventa trascurabile quando `totale` cresce).
ALPHA_LAPLACE: float = 1.0

#: Peso della penalità di quota STORICA (fondata su `BehaviorEvent` reali).
#: Vedi `LIMITE_PESO_COMBINATO_MAX` per il vincolo sulla somma con
#: `PESO_STRUTTURA_DEFAULT`.
PESO_STORICO_DEFAULT: float = 0.3

#: Peso della penalità di quota STRUTTURALE (dominio di contenuto attraverso
#: profili diversi, nessun dato storico). Pesato meno del termine storico:
#: è una correzione preventiva su un rischio di concentrazione desunto dalla
#: sola pertinenza di contenuto, non un fatto osservato come lo storico reale
#: — merita comunque un peso non trascurabile perché corregge esattamente il
#: caso diagnosticato (luogo a zero eventi che domina per pertinenza pura).
#: Vedi `LIMITE_PESO_COMBINATO_MAX` per il vincolo sulla somma con
#: `PESO_STORICO_DEFAULT`.
PESO_STRUTTURA_DEFAULT: float = 0.2

#: Limite massimo per `peso_storico + peso_struttura`, ridefinito e
#: riderivato rispetto al singolo `PESO_PENALITA_DISTRIBUZIONE_DEFAULT` di
#: prima di questa correzione (ora sostituito da due pesi distinti): ciascuna
#: quota (storica smussata e strutturale) è per costruzione in [0, 1], quindi
#: la penalità massima combinata possibile è
#: `(peso_storico + peso_struttura) * 1.0`. Con la somma di default
#: `0.3 + 0.2 = 0.5`, anche il caso limite peggiore — UN SOLO luogo che
#: saturi ENTRAMBE le quote a 1.0 (tutto il flusso storico mappabile su quel
#: luogo E quel luogo in testa per pertinenza pura in TUTTI gli archetipi
#: strutturali) — perde al più 0.5 punti di score: un luogo con base = 0.9 e
#: doppia quota = 1.0 resta a 0.4, ancora DAVANTI a un luogo con base = 0.3 e
#: doppia quota = 0.0 (0.4 > 0.3). Il vincolo modula l'ordine, non lo
#: ribalta con un veto — stesso principio già documentato per il singolo
#: peso, esteso alla somma. `costruisci_score_fn` rifiuta esplicitamente
#: (`ValueError`) qualunque combinazione di pesi che superi questo limite:
#: il vincolo etico è verificato a runtime, non solo in un commento.
LIMITE_PESO_COMBINATO_MAX: float = 0.5

#: Sotto questa soglia di eventi storici MAPPABILI (cioè il cui
#: `experience_id` corrisponde a un `place_id` tra i candidati CORRENTI), la
#: stima di concentrazione non è affidabile: un singolo evento non deve
#: bastare a penalizzare un luogo. In questo caso ENTRAMBE le quote (storica
#: e strutturale) sono spente — dizionari vuoti — e il punteggio finale è
#: BIT-IDENTICO a `calcola_score` da solo (criterio di accettazione esplicito
#: di questa wave, verificato end-to-end da
#: `tests/test_integration_wave3b.py::test_cold_start_end_to_end...`). Anche
#: il termine strutturale (che di per sé non dipende da NESSUN evento
#: storico) resta spento sotto soglia: senza storico sufficiente a
#: giustificare correzioni, "cold start" significa "nessuna correzione",
#: punto — non solo "nessuna correzione storica". Valore scelto per essere
#: un ordine di grandezza superiore al numero di candidati tipici di un
#: itinerario (poche decine), così da richiedere una storia reale prima di
#: modulare l'ordine.
SOGLIA_MINIMA_EVENTI_MAPPABILI: int = 20

# ---------------------------------------------------------------------------
# Quota strutturale — archetipi fissi e segnale neutro (nessun dato esterno)
# ---------------------------------------------------------------------------

#: Segnale neutro, costruito LOCALMENTE in questo modulo (non importato da
#: `services/api` né da `experience_engine.engine._profilo_neutro`, che non
#: sono dipendenze di questo pacchetto): meteo sereno, nessun affollamento,
#: stanchezza zero. La quota strutturale deve misurare SOLO l'affinità di
#: contenuto tra profilo e temi di un'esperienza, isolata da qualunque
#: condizione contingente (meteo, folla, stanchezza) — un segnale non neutro
#: introdurrebbe una variabile in più nella misura di dominio strutturale,
#: che per definizione deve dipendere solo dai temi e dal profilo.
SEGNALE_NEUTRO_STRUTTURALE = Signal(
    meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(12, 0)
)

#: Insieme FISSO e documentato di profili "archetipo", rappresentativi della
#: popolazione di visitatori, usato SOLO per misurare quanto un luogo domina
#: per PERTINENZA DI CONTENUTO attraverso profili diversi — nessun dato
#: storico, nessun `BehaviorEvent`, calcolo puramente deterministico e
#: locale. Sei archetipi, ciascuno motivato:
#:
#: - CURIOSO_PURO: isola l'asse sorpresa/novità (temi insoliti + numero di
#:   connessioni del grafo) al massimo, senza contaminazione dagli altri
#:   assi: rivela quale luogo domina quando la SOLA voglia di scoprire è
#:   pertinente.
#: - CONTEMPLATIVO_PURO: isola l'asse silenzio/quiete/panorama, il tratto
#:   opposto al "turismo da flusso" — chi cerca la folla non cerca
#:   contemplazione: rivela il luogo dominante per chi la evita per indole,
#:   non solo perché lo storico lo suggerisce.
#: - AMANTE_ARTE_PURO: isola l'asse bellezza/storia/musica — l'asse su cui il
#:   dataset della città di riferimento concentra più contenuto: è
#:   l'archetipo più a rischio di produrre un vincitore strutturale netto,
#:   motivo per cui va incluso esplicitamente e non solo implicito in
#:   "misto equilibrato".
#: - CON_BAMBINI: rappresenta le famiglie. Il bonus booleano `W_BAMBINI`
#:   (0.25) di `calcola_score` è indipendente dagli altri assi e può da solo
#:   determinare il vincitore: merita un archetipo dedicato, non una
#:   variazione minore di un altro.
#: - POCO_TEMPO: chi ha poco tempo cerca i punti salienti "da non perdere"
#:   (curiosità alta) ma non ha margine per la contemplazione lenta
#:   (contemplazione bassa). `tempo_disponibile_min` non entra in
#:   `calcola_score` (governa solo il budget in `experience_engine.engine`,
#:   non toccato da questo modulo): questo archetipo è incluso comunque per
#:   il MIX di assi emotivi che lo rende distinto dagli altri, un tratto
#:   reale e frequente nella popolazione di visitatori.
#: - MISTO_EQUILIBRATO: nessun tratto dominante — il turista "medio" senza
#:   preferenze marcate, il caso più comune, a bilanciare i cinque archetipi
#:   "puri" sopra.
#:
#: Scelta del rango "in testa" = SOLO il primo (rank-1 per punteggio, con
#: pareggi ripartiti equamente tra i luoghi a pari punteggio massimo), non i
#: primi 2-3: rispecchia esattamente il meccanismo diagnosticato che ha
#: causato il bug — `_seleziona_tappe` riempie uno slot di budget liberato
#: con il MIGLIOR candidato disponibile per punteggio, cioè esattamente il
#: rank-1 corrente. Misurare il rank-1 aggregato sugli archetipi è quindi la
#: misura più diretta del rischio: includere i primi 2-3 diluirebbe il
#: segnale con luoghi che non sono la prima scelta di NESSUNO slot liberato.
ARCHETIPI_STRUTTURALI: list[EmotionalProfile] = [
    EmotionalProfile(
        curiosita=1.0, contemplazione=0.0, arte=0.0,
        con_bambini=False, tempo_disponibile_min=180,
    ),  # CURIOSO_PURO
    EmotionalProfile(
        curiosita=0.0, contemplazione=1.0, arte=0.0,
        con_bambini=False, tempo_disponibile_min=180,
    ),  # CONTEMPLATIVO_PURO
    EmotionalProfile(
        curiosita=0.0, contemplazione=0.0, arte=1.0,
        con_bambini=False, tempo_disponibile_min=180,
    ),  # AMANTE_ARTE_PURO
    EmotionalProfile(
        curiosita=0.4, contemplazione=0.2, arte=0.3,
        con_bambini=True, tempo_disponibile_min=120,
    ),  # CON_BAMBINI
    EmotionalProfile(
        curiosita=0.8, contemplazione=0.1, arte=0.4,
        con_bambini=False, tempo_disponibile_min=45,
    ),  # POCO_TEMPO
    EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5,
        con_bambini=False, tempo_disponibile_min=180,
    ),  # MISTO_EQUILIBRATO
]

#: Ampiezza (k) della classifica per archetipo usata per misurare la
#: ESPOSIZIONE di contenuto di un luogo nel gating del termine storico: un
#: luogo e' "spinto dal contenuto" se compare tra i primi `k = 3` luoghi di
#: almeno un archetipo. Provvisorio: valore simulato, non tarato.
K_ESPOSIZIONE_TOP: int = 3

#: Fattore della soglia di esposizione: il termine storico di un luogo e'
#: pieno (moltiplicatore 1) quando la sua esposizione raggiunge
#: `FATTORE_SOGLIA_ESPOSIZIONE / N` (N = numero di luoghi candidati), cioe'
#: il doppio della quota uniforme `1 / N`; sotto, scala linearmente fino a 0.
#: Provvisorio: valore simulato, non tarato.
FATTORE_SOGLIA_ESPOSIZIONE: float = 2.0


def _conteggio_grezzo_per_place(
    conteggio_per_esperienza: dict[str, float],
    candidati_correnti: Iterable[GraphCandidate],
) -> dict[str, float]:
    """Conteggio storico grezzo (non normalizzato, non smussato) per
    `place_id`, aggregato dai `BehaviorEvent` mappabili sui candidati
    CORRENTI di questa richiesta.

    "Eventi mappabili": eventi il cui `experience_id` corrisponde a un
    `place_id` tra i candidati di QUESTA richiesta. Un evento storico su
    un'esperienza che oggi non è tra i candidati (es. rimossa, o fuori dai
    filtri duri per un altro motivo) non entra né a favore né contro nessuna
    quota: è semplicemente ignorato, non essendo mappabile ORA.

    La concentrazione che conta ai fini di "distribuzione dei flussi" /
    "overtourism" è quella sul LUOGO fisico, non sulla singola esperienza:
    due esperienze diverse nello stesso luogo (es. due botteghe nella stessa
    piazza) contribuiscono ENTRAMBE alla stessa quota, perché è il luogo
    fisico a subire l'affollamento, non la singola scheda esperienza.
    """
    mappa_experience_place = {
        candidato.experience.id: candidato.experience.place_id for candidato in candidati_correnti
    }

    conteggio_per_place: dict[str, float] = {}
    for experience_id, peso in conteggio_per_esperienza.items():
        place_id = mappa_experience_place.get(experience_id)
        if place_id is None:
            continue  # evento non mappabile su un candidato di QUESTA richiesta
        conteggio_per_place[place_id] = conteggio_per_place.get(place_id, 0.0) + peso
    return conteggio_per_place


def _quota_storica_per_place(
    conteggio_grezzo_per_place: dict[str, float],
    candidati_correnti: list[GraphCandidate],
    alpha: float,
) -> dict[str, float]:
    """Quota storica di concentrazione per `place_id`, in [0, 1], con
    SMOOTHING ADDITIVO (Laplace) — chiamata SOLO quando il totale mappabile
    ha già superato `SOGLIA_MINIMA_EVENTI_MAPPABILI` (il cold start resta
    gestito interamente da `costruisci_score_fn`, che in quel caso non
    chiama nemmeno questa funzione).

    Formula, per OGNI `place_id` tra i candidati CORRENTI (non solo quelli
    con eventi tracciati — è esattamente il punto dello smoothing):

        quota[place] = (conteggio_grezzo[place] + alpha) / (totale + alpha * N)

    dove `N` è il numero di `place_id` DISTINTI tra `candidati_correnti` di
    QUESTA richiesta (non il totale del grafo) e `totale` è la somma dei
    conteggi grezzi. Senza smoothing un luogo a ZERO eventi riceve quota = 0
    ("rischio zero, penalità zero"): è la falla che lasciava un luogo a zero
    eventi ma alta pertinenza di contenuto libero di assorbire il flusso
    spostato da un luogo penalizzato. Con `alpha = 1.0` (`ALPHA_LAPLACE`)
    ogni luogo riceve comunque una quota di base non nulla.
    """
    place_ids_correnti = {candidato.experience.place_id for candidato in candidati_correnti}
    n_place = len(place_ids_correnti)
    if n_place == 0:
        return {}
    totale = sum(conteggio_grezzo_per_place.values())
    denominatore = totale + alpha * n_place
    return {
        place_id: (conteggio_grezzo_per_place.get(place_id, 0.0) + alpha) / denominatore
        for place_id in place_ids_correnti
    }


def _quota_strutturale_per_place(
    candidati_correnti: list[GraphCandidate],
    *,
    vocabolario: VocabolarioTemi,
) -> dict[str, float]:
    """Quota strutturale di dominio per `place_id`, in [0, 1] — misura
    quanto un luogo domina per PERTINENZA DI CONTENUTO attraverso profili
    diversi, calcolata SENZA alcun dato storico/esterno: solo `calcola_score`
    su `ARCHETIPI_STRUTTURALI` e `SEGNALE_NEUTRO_STRUTTURALE`.

    Per ogni archetipo: si calcola `calcola_score` di ogni candidato,
    si prende — PER LUOGO — il punteggio migliore tra le sue esperienze
    (stesso principio "aggrega per place_id" della quota storica: due
    esperienze diverse nello stesso luogo non devono essere contate come
    due luoghi separati né sottovalutare il luogo scegliendo la peggiore
    delle due), e si individua il luogo (o i luoghi, in caso di pareggio
    esatto) col punteggio massimo. Ogni luogo "in testa" riceve un credito
    di `1 / numero di luoghi in pareggio` per quell'archetipo (così la somma
    dei crediti distribuiti in un singolo archetipo è sempre 1.0). La quota
    finale è la media dei crediti su tutti gli archetipi.

    Dizionario vuoto se non ci sono candidati (nessun luogo da valutare).
    """
    place_ids_correnti = {candidato.experience.place_id for candidato in candidati_correnti}
    if not place_ids_correnti:
        return {}

    crediti: dict[str, float] = dict.fromkeys(place_ids_correnti, 0.0)
    for archetipo in ARCHETIPI_STRUTTURALI:
        punteggio_migliore_per_place: dict[str, float] = {}
        for candidato in candidati_correnti:
            punteggio = calcola_score(
                candidato, archetipo, SEGNALE_NEUTRO_STRUTTURALE, vocabolario=vocabolario
            )
            place_id = candidato.experience.place_id
            attuale = punteggio_migliore_per_place.get(place_id)
            if attuale is None or punteggio > attuale:
                punteggio_migliore_per_place[place_id] = punteggio

        punteggio_massimo = max(punteggio_migliore_per_place.values())
        vincitori = [
            place_id
            for place_id, punteggio in punteggio_migliore_per_place.items()
            if punteggio == punteggio_massimo
        ]
        credito_per_vincitore = 1.0 / len(vincitori)
        for place_id in vincitori:
            crediti[place_id] += credito_per_vincitore

    n_archetipi = len(ARCHETIPI_STRUTTURALI)
    return {place_id: credito / n_archetipi for place_id, credito in crediti.items()}


def _esposizione_top_k_per_place(
    candidati_correnti: list[GraphCandidate],
    *,
    vocabolario: VocabolarioTemi,
    k: int = K_ESPOSIZIONE_TOP,
) -> dict[str, float]:
    """Esposizione di contenuto per `place_id`, in [0, 1]: quota di
    apparizione del luogo nei primi `k` per ciascuno dei 6
    `ARCHETIPI_STRUTTURALI`, con `SEGNALE_NEUTRO_STRUTTURALE`.

    Per ogni archetipo si prende, PER LUOGO, il punteggio migliore tra le sue
    esperienze (come nella quota strutturale), si ordinano i luoghi per
    punteggio decrescente (a parita', per `place_id` crescente: ordine
    deterministico) e ciascuno dei primi `k` riceve un credito `1 / k`. La
    quota e' la media dei crediti sugli archetipi.

    Dipende dai 6 archetipi del recommender, NON dal profilo del visitatore.
    Nessun dato storico, nessun campo commerciale.
    """
    place_ids = {candidato.experience.place_id for candidato in candidati_correnti}
    crediti: dict[str, float] = dict.fromkeys(place_ids, 0.0)
    for archetipo in ARCHETIPI_STRUTTURALI:
        migliore: dict[str, float] = {}
        for candidato in candidati_correnti:
            punteggio = calcola_score(
                candidato, archetipo, SEGNALE_NEUTRO_STRUTTURALE, vocabolario=vocabolario
            )
            place_id = candidato.experience.place_id
            if place_id not in migliore or punteggio > migliore[place_id]:
                migliore[place_id] = punteggio
        in_testa = sorted(migliore.items(), key=lambda coppia: (-coppia[1], coppia[0]))[:k]
        for place_id, _ in in_testa:
            crediti[place_id] += 1.0 / k
    n_archetipi = len(ARCHETIPI_STRUTTURALI)
    return {place_id: credito / n_archetipi for place_id, credito in crediti.items()}


def _applica_gating_esposizione(
    quota_storica: dict[str, float],
    esposizione: dict[str, float],
    *,
    fattore: float = FATTORE_SOGLIA_ESPOSIZIONE,
) -> dict[str, float]:
    """Moltiplica la quota storica di ogni luogo per
    `min(1, esposizione / (fattore / N))`, con `N = len(quota_storica)`.
    Non aumenta mai la quota: il gating puo' solo ridurre la penalita'."""
    if not quota_storica:
        return {}  # nessun luogo candidato: niente da pesare (evita la divisione per zero)
    soglia = fattore / len(quota_storica)
    return {
        place_id: quota * min(1.0, esposizione.get(place_id, 0.0) / soglia)
        for place_id, quota in quota_storica.items()
    }


def costruisci_score_fn(
    repo: BehaviorEventRepository,
    candidati_correnti: list[GraphCandidate],
    *,
    vocabolario: VocabolarioTemi,
    peso_storico: float = PESO_STORICO_DEFAULT,
    peso_struttura: float = PESO_STRUTTURA_DEFAULT,
    soglia_minima_eventi: int = SOGLIA_MINIMA_EVENTI_MAPPABILI,
    alpha_smoothing: float = ALPHA_LAPLACE,
) -> ScoreFn:
    """Costruisce una `score_fn` compatibile con
    `experience_engine.engine.ScoreFn`, da passare come `score_fn` a
    `compose_itinerary` (il BFF fa questo cablaggio).

    `punteggio = base - peso_storico * quota_storica_smussata(place) -
    peso_struttura * quota_strutturale(place)`. Entrambe le quote sono
    calcolate UNA VOLTA SOLA qui (non a ogni chiamata della funzione
    ritornata) e catturate nella chiusura: chiamare di nuovo
    `costruisci_score_fn` per la prossima richiesta rilegge lo storico
    aggiornato e ricalcola la quota strutturale sui candidati di quella
    richiesta.

    COLD START: se il totale storico MAPPABILE è sotto `soglia_minima_eventi`
    (soglia 0 inclusa), ENTRAMBE le quote sono spente (nessuna chiamata alle
    funzioni che le calcolano) e il punteggio è BIT-IDENTICO a
    `calcola_score` da solo — anche il termine strutturale, che di per sé non
    dipende da alcun evento storico, resta spento sotto soglia: senza
    storico sufficiente a giustificare CORREZIONI, "cold start" significa
    "nessuna correzione", non solo "nessuna correzione storica".

    Rifiuta (`ValueError`) qualunque combinazione di pesi la cui somma superi
    `LIMITE_PESO_COMBINATO_MAX`: il vincolo etico "la penalità combinata non
    ribalta mai un vantaggio di pertinenza enorme" è verificato a runtime,
    non solo documentato.

    GATING (correzione PROVVISORIA, ondata 1b-2): il termine storico di ogni
    luogo e' moltiplicato per `min(1, esposizione / (FATTORE_SOGLIA_ESPOSIZIONE
    / N))`, con `esposizione` = quota del luogo nei primi `K_ESPOSIZIONE_TOP`
    (3) per ciascuno dei 6 `ARCHETIPI_STRUTTURALI` (segnale neutro). Onesta':
    la penalita' dipende dai 6 archetipi del recommender, NON dal profilo del
    visitatore; e' una correzione provvisoria dell'"effetto gregge", da
    riprogettare dopo la demo; non garantisce B >= A su qualunque storico
    (34 su 40 nella batteria della configurazione finale); un luogo molto
    frequentato ma poco spinto dal contenuto viene scoraggiato meno. Pesi,
    limite combinato e soglia del cold start sono invariati; il termine
    strutturale resta il rank-1 originale. Il recommender ordina, non filtra.

    La funzione ritornata (`_score`) è quella verificata dal test-guard AST
    del servizio (`tests/test_ranking.py`): NON legge mai
    `candidate.experience.partner_id`, `.prezzo_eur`,
    `.partner_abbonamento_attivo`, `.prenotabile`, né `candidate.attribuzione`
    — né direttamente né come proxy. Legge SOLO `candidate.experience.place_id`
    (per il lookup delle quote) e delega il resto a `calcola_score`.
    """
    if peso_storico + peso_struttura > LIMITE_PESO_COMBINATO_MAX:
        raise ValueError(
            f"peso_storico ({peso_storico}) + peso_struttura ({peso_struttura}) = "
            f"{peso_storico + peso_struttura} supera LIMITE_PESO_COMBINATO_MAX "
            f"({LIMITE_PESO_COMBINATO_MAX}): la penalità combinata potrebbe "
            "ribaltare un vantaggio di pertinenza, invece di limitarsi a "
            "modularlo — vedi la derivazione documentata su "
            "LIMITE_PESO_COMBINATO_MAX."
        )

    conteggio_grezzo = _conteggio_grezzo_per_place(
        repo.conteggio_per_esperienza(), candidati_correnti
    )
    totale_mappabile = sum(conteggio_grezzo.values())

    if totale_mappabile < soglia_minima_eventi:
        quota_storica: dict[str, float] = {}
        quota_strutturale: dict[str, float] = {}
    else:
        quota_storica = _applica_gating_esposizione(
            _quota_storica_per_place(conteggio_grezzo, candidati_correnti, alpha_smoothing),
            _esposizione_top_k_per_place(candidati_correnti, vocabolario=vocabolario),
        )
        quota_strutturale = _quota_strutturale_per_place(
            candidati_correnti, vocabolario=vocabolario
        )

    def _score(candidate: GraphCandidate, profile: EmotionalProfile, signal: Signal) -> float:
        base = calcola_score(candidate, profile, signal, vocabolario=vocabolario)
        place_id = candidate.experience.place_id
        quota_s = quota_storica.get(place_id, 0.0)
        quota_st = quota_strutturale.get(place_id, 0.0)
        # COLD START (entrambe le quote == {}): quota_s == quota_st == 0.0
        # per costruzione, quindi `base - 0.0 - 0.0 == base`, bit-identico a
        # `calcola_score`.
        return base - peso_storico * quota_s - peso_struttura * quota_st

    return _score
