"""Contratti dati condivisi di Lucca Soul Lab — Engine.

Single source of truth: questo modulo rispecchia ESATTAMENTE
`docs/DATA_CONTRACTS.md`. Ogni servizio importa questi tipi, non li
ridefinisce. Le modifiche passano solo da `contract-keeper` e aggiornano
contemporaneamente il markdown e questo pacchetto.

Nessun campo di questi contratti contiene PII: `person_id` e
`contributor_id` sono pseudonimi; gli eventi comportamentali sono
aggregabili/anonimi.
"""

from __future__ import annotations

from datetime import datetime, time
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EmotionalProfile",
    "Signal",
    "PersonKind",
    "VisitorContext",
    "ExperienceNode",
    "ExperienceCandidate",
    "ItineraryStop",
    "Itinerary",
    "MemoryKind",
    "MemoryContribution",
    "BehaviorEvent",
    "UrbanIntelligenceIndex",
]


class ContractModel(BaseModel):
    """Base condivisa dei contratti.

    `extra="forbid"` impedisce a un servizio di aggiungere campi non
    canonici (es. `tempo_min` invece di `durata_min`): la divergenza di
    schema viene rifiutata a runtime invece di propagarsi silenziosamente.
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 1. Human Experience Layer — profilo e contesto
# ---------------------------------------------------------------------------


class EmotionalProfile(ContractModel):
    """Rappresentazione dinamica, temporanea e NON identificante di ciò che
    una persona cerca in questo momento. Cambia durante la giornata."""

    curiosita: float = Field(ge=0, le=1)  # "hai voglia di perderti?"
    contemplazione: float = Field(ge=0, le=1)  # silenzio vs musica
    arte: float = Field(ge=0, le=1)  # bellezza vs storie
    con_bambini: bool
    tempo_disponibile_min: int = Field(ge=0)
    accessibilita_richiesta: bool = False
    ha_gia_visto_firenze: bool = False
    lingue: list[str] = ["it"]


class Signal(ContractModel):
    """Stato del mondo, ORA."""

    meteo: Literal["sereno", "pioggia", "caldo", "freddo"]
    affollamento: dict[str, float]  # place_id -> 0..1
    stanchezza: float = Field(ge=0, le=1)  # sale durante la giornata
    ora: time
    eventi_attivi: list[str] = []


class PersonKind(str, Enum):
    TURISTA = "turista"
    CITTADINO = "cittadino"  # non paga: alimenta la Urban Memory


class VisitorContext(ContractModel):
    person_id: str  # PSEUDONIMO. Mai PII.
    kind: PersonKind = PersonKind.TURISTA
    profile: EmotionalProfile
    signal: Signal
    luoghi_gia_visti: list[str] = []


# ---------------------------------------------------------------------------
# 2. Urban Knowledge Graph (Neo4j)
# ---------------------------------------------------------------------------


class ExperienceNode(ContractModel):
    id: str
    titolo: str
    place_id: str
    temi: list[str]  # "puccini","liuteria","medievale"...
    durata_min: int = Field(ge=0)
    al_chiuso: bool  # per il segnale "pioggia"
    accessibile: bool
    alimenta_memoria: bool = False  # l'esperienza produce contributi di Urban Memory
    partner_id: str | None
    prezzo_eur: float | None = Field(ge=0)


# ---------------------------------------------------------------------------
# 3. AI Experience Engine — uscita
# ---------------------------------------------------------------------------


class ExperienceCandidate(ContractModel):
    experience_id: str
    score: float = Field(ge=0, le=1)
    reason: str  # SPIEGABILITÀ OBBLIGATORIA, in italiano


class ItineraryStop(ContractModel):
    experience_id: str
    arrivo: time
    durata_min: int = Field(ge=0)
    reason: str


class Itinerary(ContractModel):
    person_id: str
    stops: list[ItineraryStop]
    generated_at: datetime
    adattato_da_segnale: bool = False  # true quando riscritto (pioggia, affollamento, stanchezza)


# ---------------------------------------------------------------------------
# 4. Urban Memory — la memoria collettiva
# ---------------------------------------------------------------------------


class MemoryKind(str, Enum):
    RACCONTO = "racconto"
    FOTOGRAFIA = "fotografia"
    MUSICA = "musica"
    MESTIERE = "mestiere"
    RICETTA = "ricetta"
    DIALETTO = "dialetto"
    TESTIMONIANZA = "testimonianza"


class MemoryContribution(ContractModel):
    """Ogni esperienza vissuta può alimentare la memoria della città.
    Non è un archivio da riempire una volta: cresce con l'uso."""

    id: str
    kind: MemoryKind
    testo: str | None = None
    media_uri: str | None = None
    riguarda: list[str]  # id di Luogo / Bottega / Artista nel grafo
    contributor_id: str  # PSEUDONIMO
    contributor_kind: PersonKind
    esperienza_id: str | None = None  # da quale esperienza nasce
    consenso: bool  # OBBLIGATORIO: nessun conferimento senza consenso esplicito
    licenza: str  # es. "CC-BY-SA-4.0" — sempre tracciata
    creato_il: datetime
    curato: bool = False  # revisione prima della pubblicazione


# ---------------------------------------------------------------------------
# 5. Eventi comportamentali (per il recommender e l'Index)
# ---------------------------------------------------------------------------


class BehaviorEvent(ContractModel):
    person_id: str  # pseudonimo
    tipo: Literal["view", "stop", "photo", "booking", "review", "skip", "memory_contrib"]
    experience_id: str
    ts: datetime
    # NIENTE PII. Aggregabile.


# ---------------------------------------------------------------------------
# 6. Urban Intelligence Index — indicatori (anonimi e aggregati)
# ---------------------------------------------------------------------------


class UrbanIntelligenceIndex(ContractModel):
    """La salute CULTURALE della città, non solo quella economica.
    Tutti i valori sono aggregati e non re-identificabili."""

    periodo: str  # es. "2026-07"
    tempo_medio_esperienza_min: float = Field(ge=0)
    coinvolgimento: float = Field(ge=0, le=1)
    soddisfazione: float = Field(ge=0, le=5)
    tasso_ritorno: float = Field(ge=0, le=1)
    nuovi_percorsi: int = Field(ge=0)  # itinerari emergenti e inattesi
    attivazione_locale: float = Field(ge=0, le=1)  # quanto il territorio minore viene raggiunto
    distribuzione_flussi: float = Field(ge=0, le=1)  # 1 = distribuiti, 0 = concentrati (overtourism)
    contributi_memoria: int = Field(ge=0)  # crescita della Urban Memory

