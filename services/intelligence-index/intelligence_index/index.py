"""`calcola_index` — assembla `UrbanIntelligenceIndex` per un periodo.

Funzione PURA di orchestrazione: riceve TUTTI i dati grezzi/pre-calcolati
già in memoria (eventi, catalogo di esperienze, grado semantico, snapshot
del grafo, itinerari, TUTTI i contributi di memoria del periodo,
indipendentemente da `curato` — vedi `contributi_memoria`) e produce
`UrbanIntelligenceIndex` — nessun accesso diretto a Postgres/Neo4j qui
dentro, stesso principio di `recommender.costruisci_score_fn(repo, ...)`:
chi vuole eseguirla contro dati reali inietta repository/sorgenti reali
(`intelligence_index.deps`), chi vuole testarla passa dati sintetici.

Applica il gate di privacy k=10 (`intelligence_index.soglia.richiedi_soglia`)
UNA VOLTA per indicatore, in un solo punto centrale — MAI ricontrollato a
mano dentro le singole funzioni di `intelligence_index.indicatori`.

Vedi il README del servizio per la lista "formula negoziata col committente"
vs "proposta da questo modulo" di ciascun indicatore.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from contracts import (
    BehaviorEvent,
    ExperienceNode,
    Itinerary,
    MemoryContribution,
    UrbanIntelligenceIndex,
)

from . import indicatori
from .periodo import intervallo_periodo
from .soglia import SOGLIA_MINIMA_PERSONE, richiedi_soglia

__all__ = ["calcola_index"]


def calcola_index(
    periodo: str,
    eventi: Iterable[BehaviorEvent],
    esperienze_per_id: Mapping[str, ExperienceNode],
    grado_semantico: Mapping[str, int],
    n_luoghi_disponibili: int,
    non_connesse_a_inizio_periodo: set[frozenset[str]],
    itinerari_periodo: Iterable[Itinerary],
    memorie: Iterable[MemoryContribution],
    *,
    soglia_percentile_attivazione: float = 0.5,
    soglia_minima_persone: int = SOGLIA_MINIMA_PERSONE,
) -> UrbanIntelligenceIndex:
    """Calcola `UrbanIntelligenceIndex` per `periodo` (`"YYYY-MM"`).

    Parametri — tutti iniettati, nessuno letto da qui:

    - `eventi`: `BehaviorEvent` grezzi. NON serve pre-filtrarli per
      `periodo`: questa funzione applica `intervallo_periodo(periodo)` da
      sé (unica definizione di "periodo", vedi `intelligence_index.
      periodo`). Può quindi ricevere l'intera storia o già un sottoinsieme
      più ampio (es. da `BehaviorEventSource.events_in_period` con un
      margine) — il filtro qui è idempotente.
    - `esperienze_per_id`: catalogo `experience_id -> ExperienceNode`
      (`intelligence_index.catalogo.esperienze_per_id`).
    - `grado_semantico`: `place_id -> grado` (`graph.topology.
      grado_semantico()` / `GraphMetricsSource.grado_semantico()`) —
      per `attivazione_locale`.
    - `n_luoghi_disponibili`: universo di luoghi che il grafo può
      proporre (`len(grado_semantico)`, dato che quella funzione ritorna
      una riga per OGNI Luogo, incluso grado zero — stessa fonte, nessuna
      seconda query) — per `distribuzione_flussi`.
    - `non_connesse_a_inizio_periodo`: `graph.topology.
      non_connected_place_pairs(at=intervallo_periodo(periodo)[0])[0]`
      (il set di coppie, non la tupla intera) — per `nuovi_percorsi`.
    - `itinerari_periodo`: **BUCO NEI DATI NOTO** (vedi
      `intelligence_index.indicatori.nuovi_percorsi` e il README): oggi
      nessuna fonte persistita esiste nel repo. Finché non esiste, passare
      esplicitamente `[]` (MAI ometterlo silenziosamente in un default
      "comodo": l'assenza del parametro deve essere una decisione visibile
      di chi chiama, non un default nascosto in questa funzione).
    - `memorie`: TUTTI i `MemoryContribution` del periodo, indipendentemente
      da `curato` (NEGOZIATA col committente — vedi il docstring di
      `intelligence_index.indicatori.contributi_memoria` per il perché: la
      curatela ha un ritardo fisiologico e può bloccare un contributo per
      ragioni tecniche, non solo di revisione; l'indicatore misura la
      PARTECIPAZIONE, non l'APPROVAZIONE) — tipicamente l'unione di
      `urban_memory.MemoryRepository.list_pending()` e `.list_curated()`
      (non esiste un metodo "tutti" dedicato sul repository: non serve,
      `curato` è un `bool` e i due elenchi coprono l'intero spazio). Filtrati
      per periodo qui dentro, su `creato_il`.

    Solleva `intelligence_index.soglia.DatiInsufficientiError` se la
    popolazione di `person_id` distinti che alimenta un indicatore non
    raggiunge `soglia_minima_persone` — MAI un valore fabbricato per un
    campo del contratto che non è opzionale (vedi il README, sezione sul
    gate k=10 e il contratto congelato). `nuovi_percorsi` fa eccezione SOLO
    quando non ci sono itinerari da valutare (nessuna persona coinvolta,
    non "poche persone coinvolte" — il gate non ha nulla da rifiutare: è
    un'assenza di dato, non un rischio di re-identificazione).
    """
    inizio, fine = intervallo_periodo(periodo)
    eventi_periodo = [evento for evento in eventi if inizio <= evento.ts < fine]
    memorie_periodo = [
        memoria for memoria in memorie if inizio <= memoria.creato_il < fine
    ]

    tempo, persone_tempo = indicatori.tempo_medio_esperienza_min(
        eventi_periodo, esperienze_per_id
    )
    richiedi_soglia(persone_tempo, "tempo_medio_esperienza_min", soglia_minima_persone)

    coinv, persone_coinv = indicatori.coinvolgimento(eventi_periodo)
    richiedi_soglia(persone_coinv, "coinvolgimento", soglia_minima_persone)

    ritorno, persone_ritorno = indicatori.tasso_ritorno(eventi_periodo)
    richiedi_soglia(persone_ritorno, "tasso_ritorno", soglia_minima_persone)

    attivazione, persone_attivazione = indicatori.attivazione_locale(
        eventi_periodo,
        esperienze_per_id,
        grado_semantico,
        soglia_percentile=soglia_percentile_attivazione,
    )
    richiedi_soglia(persone_attivazione, "attivazione_locale", soglia_minima_persone)

    distribuzione, persone_distribuzione = indicatori.distribuzione_flussi_indicatore(
        eventi_periodo, esperienze_per_id, n_luoghi_disponibili
    )
    richiedi_soglia(persone_distribuzione, "distribuzione_flussi", soglia_minima_persone)

    percorsi, persone_percorsi = indicatori.nuovi_percorsi(
        itinerari_periodo, esperienze_per_id, non_connesse_a_inizio_periodo
    )
    if persone_percorsi:
        # Gate applicato SOLO se esistono itinerari da valutare: un insieme
        # vuoto qui significa "nessun itinerario passato" (buco nei dati
        # noto, vedi sopra), non "popolazione troppo piccola" — non è una
        # situazione di rischio di re-identificazione da rifiutare.
        richiedi_soglia(persone_percorsi, "nuovi_percorsi", soglia_minima_persone)

    memoria, persone_memoria = indicatori.contributi_memoria(memorie_periodo)
    richiedi_soglia(persone_memoria, "contributi_memoria", soglia_minima_persone)

    return UrbanIntelligenceIndex(
        periodo=periodo,
        tempo_medio_esperienza_min=tempo,
        coinvolgimento=coinv,
        # Nessuna fonte reale oggi (nessuna recensione/survey in prodotto):
        # `None` esplicito, MAI un valore stimato/fabbricato solo per
        # riempire il contratto (docs/DATA_CONTRACTS.md §7).
        soddisfazione=None,
        tasso_ritorno=ritorno,
        nuovi_percorsi=percorsi,
        attivazione_locale=attivazione,
        distribuzione_flussi=distribuzione,
        contributi_memoria=memoria,
    )
