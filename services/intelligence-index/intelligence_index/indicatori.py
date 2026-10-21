"""Le 8 funzioni indicatore di `UrbanIntelligenceIndex`, PURE: ogni funzione
riceve dati già in memoria (eventi, catalogo, snapshot del grafo...) e
ritorna `(valore, person_ids_coinvolti)` — mai un accesso diretto a
Postgres/Neo4j. Il gate di privacy (`intelligence_index.soglia`) NON è
applicato qui dentro: ogni funzione si limita a ESPORRE l'insieme di
`person_id` distinti che ha usato per calcolare il valore, così che
`intelligence_index.index.calcola_index` possa applicare
`richiedi_soglia(persone, contesto)` in UN solo punto centrale, con lo
STESSO criterio per tutti e 8 gli indicatori (vedi `soglia.py`).

Tre indicatori (`distribuzione_flussi`, `nuovi_percorsi`, `attivazione_locale`)
hanno una formula GIÀ NEGOZIATA col committente — vedi i rispettivi
docstring per la fonte. La FONTE di `contributi_memoria` è ANCH'ESSA
NEGOZIATA (il committente ha dato una direzione esplicita e finale su quali
`MemoryContribution` contare, vedi il docstring della funzione), ma la sua
formula resta un semplice conteggio, senza scelte aggiuntive da confermare.
Anche `contributi_memoria` espone ora `(valore, person_ids_coinvolti)`,
STESSO pattern degli altri 7 indicatori (`ethics-guardian`, revisione
Wave 4: nessuna eccezione al gate k=10 — vedi il docstring della funzione).
I restanti tre (`tempo_medio_esperienza_min`, `coinvolgimento`,
`tasso_ritorno`) NON hanno una formula pregressa nella conversazione col
committente: sono PROPOSTE di questo modulo, derivate onestamente dai soli
dati realmente disponibili nel repo (`BehaviorEvent`, `MemoryContribution`)
— da confermare con ethics-guardian e col committente prima di considerarle
definitive (vedi il report della wave).

Nessuno di questi indicatori legge MAI un campo commerciale
(`ExperienceNode.partner_id`, `.prezzo_eur`, `.partner_abbonamento_attivo`,
`.prenotabile`) né alcun dato di `Partner`: "nessuno spazio è acquistabile"
(CLAUDE.md) vale anche per il reporting verso il Comune, non solo per il
ranking — un partner non deve poter comprare un indicatore migliore più di
quanto possa comprare visibilità.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from contracts import BehaviorEvent, ExperienceNode, Itinerary, MemoryContribution

from .distribuzione import distribuzione_flussi as _distribuzione_flussi_formula

__all__ = [
    "tempo_medio_esperienza_min",
    "coinvolgimento",
    "tasso_ritorno",
    "attivazione_locale",
    "distribuzione_flussi_indicatore",
    "nuovi_percorsi",
    "contributi_memoria",
    "contributi_memoria_curati",
]

#: Tipi di evento che indicano presenza fisica REALE (non una semplice vista
#: sullo schermo): usati da `tempo_medio_esperienza_min`. Stessa distinzione
#: già fatta da `recommender.features.PESI_TIPO` ("stop"/"booking" pesano il
#: doppio di "view" perché sono il segnale più diretto di presenza) — non
#: duplica quella tabella di pesi (che serve al ranking, uno scopo diverso),
#: ma condivide lo stesso principio: "view" da solo non è mai presenza.
_TIPI_PRESENZA_FISICA: frozenset[str] = frozenset({"stop", "booking"})

#: Tipi di evento che, su una coppia (person_id, experience_id) già vista,
#: contano come "conversione" per `coinvolgimento` — vedi la formula proposta
#: sotto per il perché.
_TIPI_CONVERSIONE: frozenset[str] = frozenset({"stop", "booking", "photo", "memory_contrib"})


# ---------------------------------------------------------------------------
# tempo_medio_esperienza_min — PROPOSTO (nessuna formula pregressa)
# ---------------------------------------------------------------------------


def tempo_medio_esperienza_min(
    eventi_periodo: Iterable[BehaviorEvent],
    esperienze_per_id: Mapping[str, ExperienceNode],
) -> tuple[float, set[str]]:
    """Durata media (minuti) delle esperienze effettivamente VISSUTE nel
    periodo.

    PROPOSTO — nessuna formula negoziata col committente per questo
    indicatore. Definizione scelta: media di `ExperienceNode.durata_min`,
    pesata sugli eventi `stop`/`booking` (presenza fisica reale, vedi
    `_TIPI_PRESENZA_FISICA`) — MAI `view` (potrebbe essere solo una scheda
    sfogliata sullo schermo, senza che la persona abbia mai messo piede nel
    luogo). "Pesata sugli eventi" significa che un'esperienza con più
    eventi di presenza contribuisce proporzionalmente di più alla media —
    la media aritmetica semplice delle durate su TUTTI gli eventi di
    presenza, non sulle sole esperienze distinte, ottiene esattamente
    questo.

    Un `experience_id` assente dal catalogo corrente (es. rimossa dal grafo
    dopo l'evento) non è mappabile: ignorato, stesso principio di
    `recommender.ranking._conteggio_grezzo_per_place`.

    Ritorna `(0.0, set())` se non ci sono eventi di presenza nel periodo:
    "nessuna esperienza vissuta" è un fatto legittimo, non un errore — il
    gate k=10 a valle (`intelligence_index.soglia`) impedirà comunque la
    pubblicazione di un valore calcolato su una popolazione troppo piccola.
    """
    durate: list[int] = []
    persone: set[str] = set()
    for evento in eventi_periodo:
        if evento.tipo not in _TIPI_PRESENZA_FISICA:
            continue
        esperienza = esperienze_per_id.get(evento.experience_id)
        if esperienza is None:
            continue
        durate.append(esperienza.durata_min)
        persone.add(evento.person_id)
    if not durate:
        return 0.0, persone
    return sum(durate) / len(durate), persone


# ---------------------------------------------------------------------------
# coinvolgimento — PROPOSTO (nessuna formula pregressa)
# ---------------------------------------------------------------------------


def coinvolgimento(eventi_periodo: Iterable[BehaviorEvent]) -> tuple[float, set[str]]:
    """Tasso in `[0, 1]`: quota di "viste" (`view`) che si CONVERTONO in un
    segnale di coinvolgimento più forte (`stop`, `booking`, `photo`,
    `memory_contrib`) sulla STESSA coppia `(person_id, experience_id)`.

    PROPOSTO — nessuna formula negoziata col committente. Granularità scelta
    deliberatamente a livello di COPPIA persona-esperienza (non un rapporto
    grezzo tra conteggi totali di eventi): un rapporto grezzo
    `conteggi[conversione] / conteggi[view]` potrebbe superare 1 se molte
    presenze fisiche avvengono SENZA una "view" precedente (es. una persona
    arriva sul posto senza aver mai aperto la scheda in app) — un numero
    fuori da `[0, 1]` violerebbe il contratto (`Field(ge=0, le=1)`) e
    comunque non avrebbe un'interpretazione onesta come "quota". Misurare
    sulla coppia mantiene il rapporto naturalmente in `[0, 1]` (l'insieme
    delle conversioni è un sottoinsieme dell'insieme delle viste, per
    costruzione) ed è più fedele alla domanda "quante VISTE si trasformano
    in qualcosa di più".

    Le coppie `(person_id, experience_id)` con presenza fisica ma SENZA una
    `view` precedente non entrano né a numeratore né a denominatore: non
    sono "viste convertite", sono un fenomeno diverso (già catturato da
    `tempo_medio_esperienza_min`), non "mancato coinvolgimento".

    Ritorna `(0.0, set())` se non ci sono eventi `view` nel periodo.
    """
    viste: set[tuple[str, str]] = set()
    target_conversione: set[tuple[str, str]] = set()
    for evento in eventi_periodo:
        chiave = (evento.person_id, evento.experience_id)
        if evento.tipo == "view":
            viste.add(chiave)
        elif evento.tipo in _TIPI_CONVERSIONE:
            target_conversione.add(chiave)

    persone_coinvolte = {person_id for person_id, _experience_id in viste}
    if not viste:
        return 0.0, persone_coinvolte

    convertite = viste & target_conversione
    return len(convertite) / len(viste), persone_coinvolte


# ---------------------------------------------------------------------------
# tasso_ritorno — PROPOSTO (nessuna formula pregressa)
# ---------------------------------------------------------------------------


def tasso_ritorno(eventi_periodo: Iterable[BehaviorEvent]) -> tuple[float, set[str]]:
    """Tasso in `[0, 1]`: quota di `person_id` attivi nel periodo che tornano
    su una data DISTINTA all'interno dello STESSO periodo.

    PROPOSTO — nessuna formula negoziata col committente. FINESTRA
    dichiarata esplicitamente: "ritorno" qui significa "attività su almeno
    2 date di calendario distinte all'interno del periodo corrente"
    (es. luglio: attivo il 3 e il 20 luglio conta come ritorno; attivo
    più volte nello stesso giorno no). Scelta per due motivi: (1) è
    calcolabile SOLO dai dati già richiesti per questo periodo
    (`BehaviorEventSource.events_in_period`), senza dover interrogare
    l'intera storia pregressa della piattaforma; (2) evita di confondere
    "sessione lunga in un solo giorno" con "essere tornati in città".

    LIMITE noto (dichiarato, non nascosto): questa definizione NON cattura
    la fedeltà CROSS-periodo (una persona attiva a giugno e di nuovo a
    luglio, ma mai due volte nello stesso mese, non risulta "di ritorno"
    qui). Una definizione cross-periodo è possibile con lo stesso
    repository (basta interrogare `events_in_period` su una finestra più
    ampia) ma richiede una decisione esplicita su QUANTO indietro guardare,
    fuori dal perimetro di questa wave — segnalata nel report, non
    implementata per non fabbricare una scelta arbitraria di finestra.

    Ritorna `(0.0, set())` se non ci sono eventi nel periodo.
    """
    giorni_per_persona: dict[str, set[object]] = {}
    for evento in eventi_periodo:
        giorni_per_persona.setdefault(evento.person_id, set()).add(evento.ts.date())

    persone = set(giorni_per_persona)
    if not persone:
        return 0.0, persone

    persone_di_ritorno = sum(1 for giorni in giorni_per_persona.values() if len(giorni) >= 2)
    return persone_di_ritorno / len(persone), persone


# ---------------------------------------------------------------------------
# attivazione_locale — FORMULA NEGOZIATA
# ---------------------------------------------------------------------------


def _percentile(valori_ordinati: list[int], frazione: float) -> float:
    """Percentile per interpolazione lineare (stessa convenzione del default
    di `numpy.percentile`): `frazione=0.5` è la mediana. Funzione LOCALE e
    minimale (nessuna dipendenza da `numpy` solo per questo), usata da
    `attivazione_locale` per calcolare la soglia sul grado semantico."""
    if not valori_ordinati:
        return 0.0
    if len(valori_ordinati) == 1:
        return float(valori_ordinati[0])
    posizione = frazione * (len(valori_ordinati) - 1)
    indice_basso = math.floor(posizione)
    indice_alto = math.ceil(posizione)
    if indice_basso == indice_alto:
        return float(valori_ordinati[indice_basso])
    peso = posizione - indice_basso
    return valori_ordinati[indice_basso] * (1 - peso) + valori_ordinati[indice_alto] * peso


def attivazione_locale(
    eventi_periodo: Iterable[BehaviorEvent],
    esperienze_per_id: Mapping[str, ExperienceNode],
    grado_semantico: Mapping[str, int],
    *,
    soglia_percentile: float = 0.5,
) -> tuple[float, set[str]]:
    """Tasso in `[0, 1]`: quota di tappe (`BehaviorEvent` tipo `"stop"`) su
    luoghi FUORI dai top per grado SEMANTICO, sul totale delle tappe nel
    periodo.

    FORMULA NEGOZIATA col committente (vedi il prompt della wave): il grado
    nella rete `VICINO`/prossimità fisica è stato ESPLICITAMENTE RESPINTO
    ("misura la pianta della città, non la cultura") — si usa invece
    `graph.topology.grado_semantico()` /
    `graph.metrics.GraphMetricsSource.grado_semantico()`, iniettato qui
    come dizionario già calcolato (nessun accesso diretto al grafo in questa
    funzione pura).

    "Top-N" = soglia sulla MEDIANA (default) del grado semantico, calcolata
    sull'INTERO universo di luoghi disponibili (`grado_semantico`, non solo
    quelli comparsi tra le tappe): `soglia_percentile` è un parametro
    ESPLICITO (`_percentile`, sopra), mai una soglia hardcoded in mezzo alla
    logica — chi chiama può scegliere un percentile diverso dalla mediana,
    ma il default resta quello negoziato.

    Un `place_id` con grado STRETTAMENTE minore della soglia è "fuori dai
    top" (luogo minore); un grado pari alla soglia resta "dentro" (coerente
    con "top-N": la mediana stessa è già un luogo "medio", non uno minore).

    Ritorna `(0.0, set())` se non ci sono tappe `"stop"` nel periodo.
    """
    tappe = [evento for evento in eventi_periodo if evento.tipo == "stop"]
    persone = {evento.person_id for evento in tappe}
    if not tappe:
        return 0.0, persone

    valori_grado = sorted(grado_semantico.values())
    soglia = _percentile(valori_grado, soglia_percentile)

    fuori_dai_top = 0
    for evento in tappe:
        esperienza = esperienze_per_id.get(evento.experience_id)
        if esperienza is None:
            continue
        grado_luogo = grado_semantico.get(esperienza.place_id, 0)
        if grado_luogo < soglia:
            fuori_dai_top += 1

    return fuori_dai_top / len(tappe), persone


# ---------------------------------------------------------------------------
# distribuzione_flussi — FORMULA NEGOZIATA (vedi intelligence_index.distribuzione)
# ---------------------------------------------------------------------------


def distribuzione_flussi_indicatore(
    eventi_periodo: Iterable[BehaviorEvent],
    esperienze_per_id: Mapping[str, ExperienceNode],
    n_luoghi_disponibili: int,
) -> tuple[float, set[str]]:
    """Wrapper che estrae i `place_id` delle tappe (`"stop"`) del periodo
    dagli eventi grezzi e delega la formula a
    `intelligence_index.distribuzione.distribuzione_flussi` — UNICA fonte di
    verità, condivisa con `tests/test_integration_wave3b.py` (vedi
    `distribuzione.py`). `distribuzione_flussi` È L'INDICATORE CHE CI
    GIUDICA (CLAUDE.md): misura l'overtourism direttamente.
    """
    tappe = [evento for evento in eventi_periodo if evento.tipo == "stop"]
    persone = {evento.person_id for evento in tappe}
    place_ids = [
        esperienze_per_id[evento.experience_id].place_id
        for evento in tappe
        if evento.experience_id in esperienze_per_id
    ]
    return _distribuzione_flussi_formula(place_ids, n_luoghi_disponibili), persone


# ---------------------------------------------------------------------------
# nuovi_percorsi — FORMULA NEGOZIATA
# ---------------------------------------------------------------------------


def nuovi_percorsi(
    itinerari_periodo: Iterable[Itinerary],
    esperienze_per_id: Mapping[str, ExperienceNode],
    non_connesse_a_inizio_periodo: set[frozenset[str]],
) -> tuple[float, set[str]]:
    """Tasso in `[0, 1]`: coppie CONSECUTIVE di tappe, in itinerari del
    periodo, che collegano due luoghi NON connessi da `VICINO` nello
    snapshot preso a INIZIO periodo — sul totale delle coppie di luoghi non
    connesse disponibili in quello stesso snapshot.

    FORMULA NEGOZIATA col committente (vedi il prompt della wave):

        nuovi_percorsi = |coppie consecutive non connesse allo snapshot|
                          / |tutte le coppie non connesse allo snapshot|

    `non_connesse_a_inizio_periodo` è il primo elemento della tupla
    ritornata da `graph.topology.non_connected_place_pairs(at=inizio_periodo)`
    / `GraphMetricsSource.non_connected_place_pairs(at=...)` — passato già
    calcolato (nessun accesso al grafo qui dentro).

    Il NUMERATORE conta coppie DISTINTE (un insieme, non un conteggio di
    occorrenze): un solo percorso nuovo usato da 50 itinerari diversi conta
    UNA volta, non 50 — coerente con la formula del contratto
    (`docs/DATA_CONTRACTS.md` §7: "un conteggio grezzo scenderebbe da solo
    man mano che il grafo cresce... confondendo la crescita del grafo con un
    calo dell'esplorazione spontanea" — lo stesso principio si applica a
    "quante volte" contro "quante coppie DIVERSE").

    Tappe CONSECUTIVE nello STESSO luogo (`place_a == place_b`) non formano
    una coppia (non è un "percorso" tra due luoghi).

    Un `experience_id` assente dal catalogo interrompe la sequenza in quel
    punto (la coppia (precedente, successivo) attorno al buco non è
    valutabile): non fabbrica un `place_id` per un'esperienza sconosciuta.

    Ritorna `(0.0, set())` se `non_connesse_a_inizio_periodo` è vuoto (grafo
    saturo: non esiste alcuna coppia "non connessa" da cui possa emergere un
    percorso nuovo — la formula sarebbe una divisione per zero, non un
    valore basso) o se non ci sono itinerari nel periodo.

    ATTENZIONE — buco nei dati (vedi report della wave): oggi NON esiste, in
    questo repo, alcuna fonte persistita di "itinerari generati con le loro
    tappe in sequenza, per periodo". `compose_itinerary`
    (`experience_engine.engine`) produce un `Itinerary` solo IN MEMORIA per
    la singola richiesta HTTP (`POST /itinerary`), mai scritto su
    Postgres/Neo4j. Questa funzione è quindi REALE e testata (con itinerari
    sintetici), ma `itinerari_periodo` non ha oggi alcun cablaggio a dati di
    produzione: finché tale persistenza non esiste, chi chiama
    `intelligence_index.index.calcola_index` deve passare esplicitamente
    `itinerari_periodo=[]` (o una lista raccolta da un'altra fonte
    ad-hoc) — MAI un valore fabbricato per colmare il buco.
    """
    denominatore = len(non_connesse_a_inizio_periodo)
    persone: set[str] = set()
    if denominatore == 0:
        return 0.0, persone

    coppie_emerse: set[frozenset[str]] = set()
    for itinerario in itinerari_periodo:
        sequenza_luoghi: list[str | None] = []
        for tappa in itinerario.stops:
            esperienza = esperienze_per_id.get(tappa.experience_id)
            if esperienza is None:
                # Buco esplicito (esperienza non nel catalogo): non fabbrica un place_id.
                sequenza_luoghi.append(None)
                continue
            sequenza_luoghi.append(esperienza.place_id)

        ha_almeno_una_coppia_valutabile = False
        for luogo_a, luogo_b in zip(sequenza_luoghi, sequenza_luoghi[1:], strict=False):
            if luogo_a is None or luogo_b is None or luogo_a == luogo_b:
                continue
            coppia = frozenset({luogo_a, luogo_b})
            ha_almeno_una_coppia_valutabile = True
            if coppia in non_connesse_a_inizio_periodo:
                coppie_emerse.add(coppia)
        if ha_almeno_una_coppia_valutabile:
            persone.add(itinerario.person_id)

    return len(coppie_emerse) / denominatore, persone


# ---------------------------------------------------------------------------
# contributi_memoria — FONTE NEGOZIATA (col committente, in modo esplicito e
# finale — non più una proposta di questo modulo)
# ---------------------------------------------------------------------------


def contributi_memoria(
    memorie_periodo: Iterable[MemoryContribution],
) -> tuple[int, set[str]]:
    """Conteggio di TUTTI i contributi di Urban Memory creati nel periodo,
    indipendentemente da `curato` — un conteggio, non una media: il
    contratto lo dichiara `int` (`docs/DATA_CONTRACTS.md` §7, "crescita
    della Urban Memory"). Ritorna `(valore, contributor_ids_coinvolti)`,
    STESSO pattern degli altri 7 indicatori.

    NEGOZIATA — il committente ha dato una direzione esplicita e finale su
    quale fonte usare, tornando alla proposta ORIGINALE di questo modulo
    (prima di una revisione successiva, poi anch'essa respinta, che aveva
    ristretto il conteggio ai soli `curato=True`). Esistono DUE fonti
    diverse nel repo per "un contributo di memoria è avvenuto":

    1. `BehaviorEvent` con `tipo="memory_contrib"` — un EVENTO che dice
       solo "un tentativo di conferimento è avvenuto ora", MAI se è stato
       poi approvato dalla curatela;
    2. `MemoryContribution` (qualunque valore di `curato`) in
       `services/urban-memory` — il contributo REALMENTE conferito, con
       consenso e licenza già validati da `urban_memory.service` (a
       differenza della fonte 1, non un semplice evento di tentativo).

    Questo modulo sceglie la FONTE 2, ma SENZA filtrare su `curato`: conta
    l'unione di `MemoryRepository.list_pending()` (`curato=False`) e
    `list_curated()` (`curato=True`) — non serve un metodo dedicato sul
    repository, "tutti" è la composizione dei due che esistono già
    (`curato` è un `bool`, i due insiemi sono mutuamente esclusivi). I
    contributi SCARTATI (`MemoryRepository.scarta`, solo non curati) sono
    esclusi a monte da entrambe le letture, quindi qui non contano. Il
    filtro per periodo su `creato_il` resta applicato dal chiamante
    (`intelligence_index.index.calcola_index`), qualunque sia l'insieme
    ricevuto.

    Tre ragioni, riportate dal committente:

    1. La curatela ha un ritardo fisiologico — contare solo i curati
       sottostima sistematicamente l'impegno civico recente, specialmente a
       ridosso della fine del periodo (un contributo del 28 del mese non ha
       fisicamente il tempo di essere revisionato prima della chiusura del
       periodo di reporting).
    2. Dopo il fix di Wave 2 (CLAUDE.md: "la curatela verifica i target...
       un contributo raggiunge `curato=True` solo se ogni id in `riguarda`
       esiste nel Knowledge Graph"), un contributo può restare bloccato in
       `curato=False` per ragioni TECNICHE (il luogo/artista che descrive
       non è ancora nel grafo), non solo perché in attesa di revisione
       umana — un blocco tecnico non è un'assenza di partecipazione.
    3. Una dashboard comunale che mostra "0 contributi" perché la curatela
       è ferma per un motivo tecnico, letta come "i cittadini non
       partecipano", è ESATTAMENTE il dato fuorviante da evitare —
       l'indicatore principale deve contare la PARTECIPAZIONE, non
       l'APPROVAZIONE. Il sotto-conteggio dei soli curati resta un dato
       utile (quanto della partecipazione è già pubblico), ma come
       drill-down separato — vedi `contributi_memoria_curati` sotto — non
       come l'indicatore che finisce nel contratto.

    GATE k=10 APPLICATO (decisione di `ethics-guardian`, revisione Wave 4):
    la vecchia motivazione per esentare questo indicatore dal gate
    ("un contributo curato è già pubblico, contarne il numero non espone
    nulla di nuovo") NON reggeva più da quando il conteggio include anche i
    `pending` — un `MemoryContribution` con `curato=False` NON è ancora
    pubblico (`GET /memory/{place_id}` restituisce solo i curati). Una cella
    di conteggio grezzo sotto soglia è il caso classico di soppressione
    cella nella disclosure control statistica: un "1" o un "2" rivela
    l'esistenza di una popolazione minuscola e potenzialmente identificabile,
    indipendentemente dal fatto che il campo esposto sia un tasso o un
    conteggio grezzo. `contributor_id` è quindi esposto qui, esattamente come
    `person_id`/`experience_id` negli altri indicatori, così che
    `intelligence_index.index.calcola_index` applichi `richiedi_soglia` nello
    STESSO punto centrale usato per tutti gli altri 7 campi — nessuna
    eccezione residua.
    """
    memorie = list(memorie_periodo)
    contributori = {m.contributor_id for m in memorie}
    return len(memorie), contributori


def contributi_memoria_curati(memorie_periodo: Iterable[MemoryContribution]) -> int:
    """Sotto-conteggio: quanti dei contributi ricevuti hanno `curato=True`.

    NON entra nel campo `UrbanIntelligenceIndex.contributi_memoria` (il
    contratto congelato resta un solo `int`, nessuna modifica): è un dato di
    DETTAGLIO, pronto per un futuro drill-down dashboard — stesso principio
    già seguito per `intelligence_index.soglia.valore_se_soglia` (pronto,
    non ancora cablato a un endpoint). Utile per rispondere a "quanta della
    partecipazione misurata da `contributi_memoria` è già pubblica" senza
    dover ripetere il filtro altrove.

    Riceve lo STESSO insieme già filtrato per periodo passato a
    `contributi_memoria` (non una seconda fonte, non un secondo filtro):
    chi chiama può calcolare `contributi_memoria(memorie_periodo)` e
    `contributi_memoria_curati(memorie_periodo)` sullo stesso `memorie_periodo`
    per ottenere `(totale, curati)`.
    """
    return sum(1 for memoria in memorie_periodo if memoria.curato)
