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

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "EmotionalProfile",
    "Signal",
    "PersonKind",
    "VisitorContext",
    "ExperienceNode",
    "GraphCandidate",
    "ExperienceCandidate",
    "ItineraryStop",
    "Itinerary",
    "MemoryKind",
    "MemoryContribution",
    "Partner",
    "BookingStatus",
    "BookingRequest",
    "Booking",
    "CommissionRecord",
    "BehaviorEvent",
    "UrbanIntelligenceIndex",
    "OnboardingAnswer",
    "OnboardingRequest",
    "AdaptRequest",
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
    affollamento: dict[str, float]  # place_id -> 0..1 (validato: ogni valore in [0,1])
    stanchezza: float = Field(ge=0, le=1)  # sale durante la giornata
    ora: time
    eventi_attivi: list[str] = []

    @field_validator("affollamento")
    @classmethod
    def _affollamento_in_scala(cls, v: dict[str, float]) -> dict[str, float]:
        # L'affollamento governa la distribuzione dei flussi: un valore fuori
        # scala inverte la logica etica del motore (falsa la scelta tra
        # luoghi affollati e non). Validato per ogni place_id, non solo il tipo.
        for place_id, valore in v.items():
            if not 0 <= valore <= 1:
                raise ValueError(
                    f"affollamento fuori scala per place_id={place_id!r}: "
                    f"{valore} non è in [0,1]"
                )
        return v


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


class Partner(ContractModel):
    """Un partner (bottega, operatore) che offre esperienze sul marketplace.

    `abbonamento_attivo` è l'UNICA leva che decide se le esperienze di questo
    partner compaiono tra i candidati: mai il ranking. Il modello di ricavo è
    un abbonamento di presenza (sì/no), MAI un'asta sulla visibilità: nessun
    campo di prezzo/commissione vive qui, e nessun campo di questo modello è
    mai letto dallo scoring dell'Experience Engine — che non importa nemmeno
    questo tipo, vede solo `ExperienceNode.partner_abbonamento_attivo`
    (booleano denormalizzato).
    """

    id: str
    nome: str
    abbonamento_attivo: bool = True


class ExperienceNode(ContractModel):
    id: str
    titolo: str
    place_id: str
    temi: list[str]  # "puccini","liuteria","medievale"...
    durata_min: int = Field(ge=0)
    al_chiuso: bool  # per il segnale "pioggia"
    accessibile: bool
    alimenta_memoria: bool = False  # l'esperienza produce contributi di Urban Memory
    partner_id: str | None = None
    prezzo_eur: float | None = Field(default=None, ge=0)
    # Booleano denormalizzato, popolato a monte dal grafo/BFF a partire da
    # `Partner.abbonamento_attivo`. Default True: un'esperienza senza partner
    # (partner_id=None) è SEMPRE visibile. È l'UNICO campo che l'Experience
    # Engine legge per decidere presenza/assenza di un candidato (filtro duro
    # booleano, mai un input numerico dello scoring): così "visibilità non
    # acquistabile" è strutturale, non una convenzione — lo scoring non ha
    # nemmeno bisogno di importare `Partner` o `prezzo_eur`.
    partner_abbonamento_attivo: bool = True
    # Deliberatamente NON derivato da `partner_id is not None`: presenza
    # commerciale (chi offre l'esperienza) e prenotabilità (se si può
    # prenotare) sono concetti distinti. Un'esperienza gratuita e senza
    # partner può essere prenotabile (posti limitati); un'esperienza con
    # partner può non esserlo.
    prenotabile: bool = False


class GraphCandidate(ContractModel):
    """Candidato proposto dal grafo all'AI Experience Engine.

    Il grafo PROPONE connessioni (via `connessioni`, fatti leggibili in
    italiano che alimentano il `reason`); non decide. Sceglie solo
    l'Experience Engine.
    """

    experience: ExperienceNode
    place_nome: str
    connessioni: list[str]  # es. "Puccini è legato a questo luogo"
    distanza_m: int | None = Field(default=None, ge=0)
    # SEPARATA da `connessioni`: le connessioni alimentano lo score di
    # sorpresa del motore. Se l'attribuzione commerciale vi finisse dentro,
    # la presenza di un partner comprerebbe score, violando "visibilità non
    # acquistabile". `attribuzione` è SOLO narrazione trasparente nel
    # `reason`, mai input di scoring.
    attribuzione: str | None = None  # es. "Offerta da <bottega>, bottega di <mestiere>."


# ---------------------------------------------------------------------------
# 3. AI Experience Engine — uscita
# ---------------------------------------------------------------------------


class ExperienceCandidate(ContractModel):
    experience_id: str
    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)  # SPIEGABILITÀ OBBLIGATORIA, in italiano


class ItineraryStop(ContractModel):
    experience_id: str
    arrivo: time
    durata_min: int = Field(ge=0)
    reason: str = Field(min_length=1)  # SPIEGABILITÀ OBBLIGATORIA, in italiano


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
    # min_length=1: un contributo DEVE riferirsi ad almeno un nodo del grafo,
    # altrimenti sarebbe un nodo :Memoria orfano. Non garantisce che gli id
    # esistano nel grafo: quel controllo è a runtime, nel linker
    # urban_memory.graph_link (collegamento atomico).
    riguarda: list[str] = Field(min_length=1)  # id di Luogo / Bottega / Artista
    contributor_id: str  # PSEUDONIMO
    contributor_kind: PersonKind
    esperienza_id: str | None = None  # da quale esperienza nasce
    consenso: bool  # OBBLIGATORIO: nessun conferimento senza consenso esplicito
    licenza: str = Field(min_length=1)  # es. "CC-BY-SA-4.0" — sempre tracciata
    creato_il: datetime
    curato: bool = False  # revisione prima della pubblicazione


# ---------------------------------------------------------------------------
# 5. Marketplace — prenotazioni e ricavo (dato contabile, mai input di scoring)
# ---------------------------------------------------------------------------


class BookingStatus(str, Enum):
    RICHIESTA = "richiesta"
    CONFERMATA = "confermata"
    ANNULLATA = "annullata"


class BookingRequest(ContractModel):
    """Input di POST /booking."""

    person_id: str  # PSEUDONIMO
    experience_id: str
    quando: datetime  # data e ora richieste per l'esperienza


class Booking(ContractModel):
    id: str
    person_id: str  # PSEUDONIMO
    experience_id: str
    quando: datetime
    stato: BookingStatus = BookingStatus.RICHIESTA
    # Snapshot: il prezzo dell'ExperienceNode può cambiare nel tempo, la
    # Booking congela quanto pattuito al momento della richiesta. È un
    # contratto tra persona e partner: non deve seguire il listino corrente.
    prezzo_eur: float = Field(ge=0)
    creato_il: datetime


class CommissionRecord(ContractModel):
    """Dato CONTABILE, separato da `Booking` per prescrizione ethics-guardian
    (stesso principio di `GraphCandidate.attribuzione`, sezione 2 sopra):
    la commissione è calcolata DOPO che l'Experience Engine ha già scelto la
    tappa. Lo scoring lavora su `GraphCandidate`/`ExperienceNode`, che non
    contengono e non importano questo tipo. Tenere `CommissionRecord` in un
    modello a parte, mai raggiungibile da `experience_engine.rules`, rende
    STRUTTURALMENTE impossibile che la commissione diventi un domani un input
    di scoring: non esiste un percorso di import che colleghi i due moduli.
    """

    booking_id: str
    importo_eur: float = Field(ge=0)
    percentuale: float = Field(default=0.15, ge=0, le=1)  # commissione sul prezzo, non sul ranking
    registrata_il: datetime


# ---------------------------------------------------------------------------
# 6. Eventi comportamentali (per il recommender e l'Index)
# ---------------------------------------------------------------------------


class BehaviorEvent(ContractModel):
    person_id: str  # pseudonimo
    tipo: Literal["view", "stop", "photo", "booking", "review", "skip", "memory_contrib"]
    experience_id: str
    ts: datetime
    # NIENTE PII. Aggregabile.


# ---------------------------------------------------------------------------
# 7. Urban Intelligence Index — indicatori (anonimi e aggregati)
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
    distribuzione_flussi: float = Field(ge=0, le=1)  # 1 = distribuiti, 0 = overtourism
    contributi_memoria: int = Field(ge=0)  # crescita della Urban Memory


# ---------------------------------------------------------------------------
# 8. API (BFF) — modelli di richiesta
# ---------------------------------------------------------------------------


class OnboardingAnswer(ContractModel):
    """Una risposta della conversazione di onboarding ("Hai voglia di
    perderti?"...). Testo libero: il parsing è del servizio RAG."""

    domanda_id: str
    risposta: str


class OnboardingRequest(ContractModel):
    """Input di POST /session/onboarding (output: EmotionalProfile)."""

    risposte: list[OnboardingAnswer]
    lingua: str = "it"


class AdaptRequest(ContractModel):
    """Input di POST /itinerary/adapt."""

    itinerary: Itinerary
    signal: Signal

