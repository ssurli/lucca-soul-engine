# DATA CONTRACTS — Single Source of Truth

> **Regola d'oro:** questi tipi vivono anche in `packages/contracts` (Pydantic v2) e sono importati
> da tutti i servizi. Nessun agente ridefinisce un campo qui presente. Ogni modifica passa da
> `contract-keeper` e aggiorna *contemporaneamente* questo file e il pacchetto.
>
> Il vocabolario è quello del White Paper v1.0 (congelato).

## 1. Human Experience Layer — profilo e contesto

```python
class EmotionalProfile(BaseModel):
    """Rappresentazione dinamica, temporanea e NON identificante di ciò che
    una persona cerca in questo momento. Cambia durante la giornata."""
    curiosita: float          # 0..1  "hai voglia di perderti?"
    contemplazione: float     # 0..1  silenzio vs musica
    arte: float               # 0..1  bellezza vs storie
    con_bambini: bool
    tempo_disponibile_min: int
    accessibilita_richiesta: bool = False
    ha_gia_visto_firenze: bool = False
    lingue: list[str] = ["it"]

class Signal(BaseModel):              # stato del mondo, ORA
    meteo: Literal["sereno","pioggia","caldo","freddo"]
    affollamento: dict[str, float]    # place_id -> 0..1
    stanchezza: float                 # 0..1, sale durante la giornata
    ora: time
    eventi_attivi: list[str] = []

class PersonKind(str, Enum):
    TURISTA = "turista"
    CITTADINO = "cittadino"           # non paga: alimenta la Urban Memory

class VisitorContext(BaseModel):
    person_id: str                    # PSEUDONIMO. Mai PII.
    kind: PersonKind = PersonKind.TURISTA
    profile: EmotionalProfile
    signal: Signal
    luoghi_gia_visti: list[str] = []
```

## 2. Urban Knowledge Graph (Neo4j)

Nodi: `Luogo`, `Artista`, `Bottega`, `Evento`, `Esperienza`, `Tema`.
Relazioni: `(:Artista)-[:LEGATO_A]->(:Luogo)`, `(:Luogo)-[:VICINO {metri}]->(:Luogo)`,
`(:Bottega)-[:OFFRE]->(:Esperienza)`, `(:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)`,
`(:Esperienza)-[:EVOCA]->(:Tema)`, `(:Memoria)-[:RIGUARDA]->(:Luogo|:Bottega|:Artista)`.

```python
class ExperienceNode(BaseModel):
    id: str
    titolo: str
    place_id: str
    temi: list[str]                   # "puccini","liuteria","medievale"...
    durata_min: int
    al_chiuso: bool                   # per il segnale "pioggia"
    accessibile: bool
    alimenta_memoria: bool = False    # l'esperienza produce contributi di Urban Memory
    partner_id: str | None
    prezzo_eur: float | None
```

## 3. AI Experience Engine — uscita

```python
class ExperienceCandidate(BaseModel):
    experience_id: str
    score: float                      # 0..1
    reason: str                       # SPIEGABILITÀ OBBLIGATORIA, in italiano

class ItineraryStop(BaseModel):
    experience_id: str
    arrivo: time
    durata_min: int
    reason: str

class Itinerary(BaseModel):
    person_id: str
    stops: list[ItineraryStop]
    generated_at: datetime
    adattato_da_segnale: bool = False # true quando riscritto (pioggia, affollamento, stanchezza)
```

## 4. Urban Memory — la memoria collettiva

```python
class MemoryKind(str, Enum):
    RACCONTO = "racconto"
    FOTOGRAFIA = "fotografia"
    MUSICA = "musica"
    MESTIERE = "mestiere"
    RICETTA = "ricetta"
    DIALETTO = "dialetto"
    TESTIMONIANZA = "testimonianza"

class MemoryContribution(BaseModel):
    """Ogni esperienza vissuta può alimentare la memoria della città.
    Non è un archivio da riempire una volta: cresce con l'uso."""
    id: str
    kind: MemoryKind
    testo: str | None = None
    media_uri: str | None = None
    riguarda: list[str]               # id di Luogo / Bottega / Artista nel grafo
    contributor_id: str               # PSEUDONIMO
    contributor_kind: PersonKind
    esperienza_id: str | None = None  # da quale esperienza nasce
    consenso: bool                    # OBBLIGATORIO: nessun conferimento senza consenso esplicito
    licenza: str                      # es. "CC-BY-SA-4.0" — sempre tracciata
    creato_il: datetime
    curato: bool = False              # revisione prima della pubblicazione
```

## 5. Eventi comportamentali (per il recommender e l'Index)

```python
class BehaviorEvent(BaseModel):
    person_id: str                    # pseudonimo
    tipo: Literal["view","stop","photo","booking","review","skip","memory_contrib"]
    experience_id: str
    ts: datetime
    # NIENTE PII. Aggregabile.
```

## 6. Urban Intelligence Index — indicatori (anonimi e aggregati)

```python
class UrbanIntelligenceIndex(BaseModel):
    """La salute CULTURALE della città, non solo quella economica.
    Tutti i valori sono aggregati e non re-identificabili."""
    periodo: str                      # es. "2026-07"
    tempo_medio_esperienza_min: float
    coinvolgimento: float             # 0..1
    soddisfazione: float              # 0..5
    tasso_ritorno: float              # 0..1
    nuovi_percorsi: int               # itinerari emergenti e inattesi
    attivazione_locale: float         # 0..1 quanto il territorio minore viene raggiunto
    distribuzione_flussi: float       # 0..1  1 = distribuiti, 0 = concentrati (overtourism)
    contributi_memoria: int           # crescita della Urban Memory
```

## 7. API (BFF) — contratto sintetico

```
POST /session/onboarding   -> EmotionalProfile
POST /itinerary            (VisitorContext) -> Itinerary
POST /itinerary/adapt      (Itinerary + Signal) -> Itinerary
POST /events               (BehaviorEvent) -> 202
POST /memory               (MemoryContribution) -> 201   # richiede consenso
GET  /memory/{place_id}    -> list[MemoryContribution]   # solo contenuti curati
GET  /dashboard/flows      -> heatmap aggregata
GET  /dashboard/index      -> UrbanIntelligenceIndex
```

> OpenAPI generato da FastAPI è la versione autoritativa dell'API; questo blocco è il riassunto.

## Vincoli trasversali (verificati da `ethics-guardian`)

- Nessun campo di questi contratti contiene PII.
- `reason` è obbligatorio ovunque compaia una raccomandazione.
- `MemoryContribution.consenso` deve essere `True` per essere persistito. Nessuna eccezione.
- Nessun campo esprime "priorità a pagamento": la visibilità non è acquistabile.
