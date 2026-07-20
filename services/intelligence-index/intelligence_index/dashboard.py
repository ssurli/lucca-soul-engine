"""Adattatori PURI verso le due risposte di `GET /dashboard/*` — nessuna
logica di calcolo nuova, nessun accesso diretto a Postgres/Neo4j. Sarà
`api-engineer`, in una wave successiva, a procurarsi gli argomenti (via
`intelligence_index.deps`, `intelligence_index.catalogo.esperienze_per_id`,
`graph.metrics.GraphMetricsSource.grado_semantico()`...) e a chiamare queste
due funzioni dentro l'endpoint HTTP.

- `indice_per_dashboard` — wrapper di `intelligence_index.index.calcola_index`
  per `contracts.DashboardIndexResponse` (`GET /dashboard/index`): traduce
  `DatiInsufficientiError` in uno stato "dato insufficiente" di prima classe,
  invece di propagare l'eccezione grezza o fabbricare un
  `UrbanIntelligenceIndex`.
- `celle_flusso` — aggregazione per `contracts.DashboardFlowsResponse`
  (`GET /dashboard/flows`): UNA `FlowCell` per OGNI luogo del grafo (anche
  quelli senza nessuna tappa), gated indipendentemente sulla soglia k=10 dei
  `person_id` distinti coinvolti in QUELLA cella
  (`intelligence_index.soglia.valore_se_soglia`).

Punto critico di correttezza (vedi il docstring di `celle_flusso`): un luogo
a ZERO tappe deve restare INDISTINGUIBILE, nella risposta, da un luogo con
1-9 persone — entrambi sotto la soglia k=10, entrambi `disponibile=False`.
Non esiste, in questo modulo, alcun ramo speciale per il conteggio zero.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from contracts import (
    BehaviorEvent,
    DashboardFlowsResponse,
    DashboardIndexResponse,
    ExperienceNode,
    FlowCell,
    Itinerary,
    MemoryContribution,
)

from .index import calcola_index
from .soglia import SOGLIA_MINIMA_PERSONE, DatiInsufficientiError, valore_se_soglia

__all__ = ["indice_per_dashboard", "celle_flusso"]


def indice_per_dashboard(
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
) -> DashboardIndexResponse:
    """Wrapper di `calcola_index` per `GET /dashboard/index`.

    STESSI parametri di `intelligence_index.index.calcola_index`, riusati
    senza aggiungere né rimuovere nulla — nessuna dipendenza nuova, nessuna
    logica di calcolo nuova: questa funzione si limita a catturare
    `DatiInsufficientiError` e a tradurla in una risposta di prima classe,
    invece di lasciarla propagare grezza fino al BFF.

    - Se `calcola_index` riesce: `disponibile=True`, `index` popolato,
      `motivo_indisponibilita=None`.
    - Se `calcola_index` solleva `DatiInsufficientiError` (un qualunque
      indicatore dell'intero periodo è sotto la soglia k=10): `disponibile=
      False`, `index=None`, `motivo_indisponibilita=` un messaggio GENERICO
      costruito qui, MAI `str(eccezione)`.

      `DatiInsufficientiError.__str__()` include `n_persone` — il conteggio
      ESATTO di persone distinte sotto soglia. Utile nei log interni/nel
      debug lato server, ma è esattamente il dato che il gate k=10 esiste per
      nascondere: se finisse, così com'è, nel campo `motivo_indisponibilita`
      di una `DashboardIndexResponse`, raggiungerebbe la risposta JSON
      pubblica di `GET /dashboard/index` e permetterebbe la stessa
      re-identificazione che la soglia di aggregazione deve prevenire — solo
      sul canale "spiegazione leggibile" invece che sul canale "valore". Per
      questo il messaggio pubblico è ricostruito da zero qui, usando
      SOLO `exc.contesto` (il nome dell'indicatore, non identificante) e
      `exc.soglia` (la costante k, pubblica e nota) — MAI `exc.n_persone`.

    Il `model_validator` di `DashboardIndexResponse` (`packages/contracts`)
    verifica per costruzione che i due stati non si mescolino mai: questa
    funzione non ha bisogno di controllare da sé la coerenza dei campi che
    passa al costruttore.
    """
    try:
        index = calcola_index(
            periodo,
            eventi,
            esperienze_per_id,
            grado_semantico,
            n_luoghi_disponibili,
            non_connesse_a_inizio_periodo,
            itinerari_periodo,
            memorie,
            soglia_percentile_attivazione=soglia_percentile_attivazione,
            soglia_minima_persone=soglia_minima_persone,
        )
    except DatiInsufficientiError as exc:
        motivo_indisponibilita = (
            f"dato insufficiente per {exc.contesto!r}: sotto la soglia minima "
            f"di aggregazione k={exc.soglia} (privacy by design) — questo "
            "indicatore non viene pubblicato per questo periodo."
        )
        return DashboardIndexResponse(
            periodo=periodo,
            disponibile=False,
            index=None,
            motivo_indisponibilita=motivo_indisponibilita,
        )
    return DashboardIndexResponse(
        periodo=periodo,
        disponibile=True,
        index=index,
        motivo_indisponibilita=None,
    )


def celle_flusso(
    periodo: str,
    eventi_periodo: Iterable[BehaviorEvent],
    esperienze_per_id: Mapping[str, ExperienceNode],
    grado_semantico: Mapping[str, int],
    *,
    giorno: date | None = None,
    ora: int | None = None,
    soglia_minima_persone: int = SOGLIA_MINIMA_PERSONE,
) -> DashboardFlowsResponse:
    """Aggregazione per `GET /dashboard/flows`.

    Parametri — tutti iniettati, nessuno letto da qui (nessun accesso
    diretto a Postgres/Neo4j):

    - `eventi_periodo`: `BehaviorEvent` GIÀ filtrati per `periodo` (stesso
      contratto di `intelligence_index.index.calcola_index`: chi chiama ha
      già applicato `intervallo_periodo(periodo)`, questa funzione non lo
      rifà). `giorno`/`ora`, se forniti, restringono ULTERIORMENTE questo
      stesso insieme.
    - `esperienze_per_id`: catalogo `experience_id -> ExperienceNode`
      (`intelligence_index.catalogo.esperienze_per_id`) — per risalire da
      `BehaviorEvent.experience_id` al `place_id` fisico.
    - `grado_semantico`: `place_id -> grado`
      (`graph.topology.grado_semantico()` /
      `GraphMetricsSource.grado_semantico()`) — STESSA fonte già usata da
      `intelligence_index.indicatori.attivazione_locale`, non una query
      nuova: le SUE CHIAVI sono l'universo completo dei luoghi del grafo
      (quella funzione ritorna una riga per ogni `Luogo`, incluso grado
      zero), quindi produce una `FlowCell` per ognuna, anche se il luogo non
      compare in nessuna tappa.

    Per ogni `place_id` in `grado_semantico`:

    1. Filtra gli eventi tipo `"stop"` il cui `experience_id` mappa (via
       `esperienze_per_id`) a quel `place_id`, ulteriormente ristretti da
       `giorno`/`ora` se forniti (`evento.ts.date() == giorno`,
       `evento.ts.hour == ora`). Un `experience_id` assente dal catalogo non
       è mappabile: ignorato, stesso principio di
       `intelligence_index.indicatori.tempo_medio_esperienza_min`.
    2. `conteggio = len(tappe)`, `persone = {evento.person_id per evento in
       tappe}`.
    3. `intelligence_index.soglia.valore_se_soglia(persone, conteggio)`:
       ritorna `conteggio` se `persone` raggiunge k=10 `person_id` distinti,
       altrimenti `None`.
    4. `FlowCell(place_id=..., disponibile=valore is not None,
       conteggio_tappe=valore)`.

    PUNTO CRITICO DI CORRETTEZZA (non negoziabile — vedi il docstring di
    modulo): il passo 3 è l'UNICO punto che decide `disponibile`, applicato
    UNIFORMEMENTE a ogni cella, incluse quelle a zero tappe. Un luogo con
    ZERO tappe ha ANCHE zero `person_id` distinti, quindi ricade SOTTO la
    soglia k=10 esattamente come un luogo con 1-9 persone: `valore_se_soglia`
    su un insieme vuoto ritorna `None` per costruzione (`len(set()) == 0 <
    10`), quindi `disponibile=False`, `conteggio_tappe=None` — LO STESSO
    stato di una cella con, ad esempio, 3 tappe/3 persone. Non esiste (e non
    deve mai esistere) un ramo `if conteggio == 0: disponibile = True` che
    tratti lo zero come "provabilmente innocuo": se una cella a zero tappe
    fosse distinguibile da una cella soppressa, un osservatore della
    dashboard potrebbe dedurre PER ESCLUSIONE che ogni cella soppressa ha
    necessariamente TRA 1 e 9 persone — l'esatta informazione che il gate
    k=10 deve nascondere.
    """
    eventi_per_luogo: dict[str, list[BehaviorEvent]] = {}
    for evento in eventi_periodo:
        if evento.tipo != "stop":
            continue
        if giorno is not None and evento.ts.date() != giorno:
            continue
        if ora is not None and evento.ts.hour != ora:
            continue
        esperienza = esperienze_per_id.get(evento.experience_id)
        if esperienza is None:
            continue
        eventi_per_luogo.setdefault(esperienza.place_id, []).append(evento)

    celle: list[FlowCell] = []
    for place_id in grado_semantico:
        tappe = eventi_per_luogo.get(place_id, [])
        conteggio = len(tappe)
        persone = {evento.person_id for evento in tappe}
        valore = valore_se_soglia(persone, conteggio, soglia=soglia_minima_persone)
        celle.append(
            FlowCell(
                place_id=place_id,
                disponibile=valore is not None,
                conteggio_tappe=valore,
            )
        )

    return DashboardFlowsResponse(periodo=periodo, giorno=giorno, ora=ora, celle=celle)
