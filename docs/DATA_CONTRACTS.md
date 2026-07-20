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
    affollamento: dict[str, float]    # place_id -> 0..1 (validato: ogni valore in [0,1])
    stanchezza: float                 # 0..1, sale durante la giornata
    ora: time
    eventi_attivi: list[str] = []

    # `field_validator` su `affollamento`: rigetta con errore in italiano (che
    # indica il place_id incriminato) qualunque valore fuori [0,1]. Motivo:
    # l'affollamento governa la distribuzione dei flussi; un valore fuori scala
    # inverte la logica etica del motore. Vedi packages/contracts per il codice.

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
`(:Esperienza)-[:EVOCA]->(:Tema)`, `(:Bottega)-[:EVOCA]->(:Tema)`,
`(:Bottega)-[:ISPIRATA_DA {racconto}]->(:Artista)`,
`(:Memoria)-[:RIGUARDA]->(:Luogo|:Bottega|:Artista)`.

```python
class Partner(BaseModel):
    """Un partner (bottega, operatore) che offre esperienze sul marketplace.

    `abbonamento_attivo` è l'UNICA leva che decide se le esperienze di questo
    partner compaiono tra i candidati: mai il ranking. Il modello di ricavo è
    un abbonamento di presenza (sì/no), MAI un'asta sulla visibilità: nessun
    campo di prezzo/commissione vive qui, e nessun campo di questo modello è
    mai letto dallo scoring dell'Experience Engine (che non importa nemmeno
    questo tipo — vede solo `ExperienceNode.partner_abbonamento_attivo`,
    booleano denormalizzato)."""
    id: str
    nome: str
    abbonamento_attivo: bool = True

class ExperienceNode(BaseModel):
    id: str
    titolo: str
    place_id: str
    temi: list[str]                   # "puccini","liuteria","medievale"...
    durata_min: int
    al_chiuso: bool                   # per il segnale "pioggia"
    accessibile: bool
    alimenta_memoria: bool = False    # l'esperienza produce contributi di Urban Memory
    partner_id: str | None = None
    prezzo_eur: float | None = None   # se presente: >= 0
    # Booleano denormalizzato, popolato a monte dal grafo/BFF a partire da
    # `Partner.abbonamento_attivo`. Default True: un'esperienza senza partner
    # (partner_id=None) è SEMPRE visibile. È l'UNICO campo che l'Experience
    # Engine legge per decidere presenza/assenza di un candidato (filtro duro
    # booleano in `passa_filtri_duri`), MAI un input numerico dello scoring:
    # così "visibilità non acquistabile" è strutturale, non una convenzione —
    # lo scoring non ha nemmeno bisogno di importare `Partner` o `prezzo_eur`.
    partner_abbonamento_attivo: bool = True
    # Deliberatamente NON derivato da `partner_id is not None`: presenza
    # commerciale (chi offre l'esperienza) e prenotabilità (se si può
    # prenotare) sono concetti distinti. Un'esperienza gratuita e senza
    # partner può essere prenotabile (posti limitati); un'esperienza con
    # partner può non esserlo.
    prenotabile: bool = False

class GraphCandidate(BaseModel):
    """Ciò che il grafo PROPONE all'Experience Engine.
    Il grafo non decide: propone candidati e connessioni leggibili."""
    experience: ExperienceNode
    place_nome: str
    connessioni: list[str]             # fatti in italiano, es. "Puccini è legato a questo luogo"
                                        # alimentano il `reason` E lo score di sorpresa
    distanza_m: int | None = None      # se presente: >= 0
    # `attribuzione` è SEPARATA da `connessioni` per prescrizione ethics-guardian:
    # le connessioni alimentano lo score di sorpresa del motore. Se l'attribuzione
    # commerciale vi finisse dentro, la presenza di un partner comprerebbe score,
    # violando "visibilità non acquistabile". `attribuzione` è SOLO narrazione
    # trasparente nel `reason`, mai input di scoring.
    attribuzione: str | None = None    # es. "Offerta da <bottega>, bottega di <mestiere>."
```

## 3. AI Experience Engine — uscita

```python
class ExperienceCandidate(BaseModel):
    experience_id: str
    score: float                      # 0..1
    reason: str                       # SPIEGABILITÀ OBBLIGATORIA, in italiano (min 1 carattere)

class ItineraryStop(BaseModel):
    experience_id: str
    arrivo: time
    durata_min: int
    reason: str                       # SPIEGABILITÀ OBBLIGATORIA, in italiano (min 1 carattere)

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
    # min_length=1: un contributo DEVE riferirsi ad almeno un nodo del grafo,
    # altrimenti sarebbe un nodo :Memoria orfano. Non garantisce che gli id
    # esistano nel grafo: quel controllo è a runtime, nel linker
    # urban_memory.graph_link (collegamento atomico).
    riguarda: list[str]               # id di Luogo / Bottega / Artista (min 1 elemento)
    contributor_id: str               # PSEUDONIMO
    contributor_kind: PersonKind
    esperienza_id: str | None = None  # da quale esperienza nasce
    consenso: bool                    # OBBLIGATORIO: nessun conferimento senza consenso esplicito
    licenza: str                      # es. "CC-BY-SA-4.0" — sempre tracciata (min 1 carattere)
    creato_il: datetime
    curato: bool = False              # revisione; curabile solo se tutti i target di
                                       # `riguarda` esistono nel grafo
```

## 5. Marketplace — prenotazioni e ricavo (dato contabile, mai input di scoring)

```python
class BookingStatus(str, Enum):
    RICHIESTA = "richiesta"
    CONFERMATA = "confermata"
    ANNULLATA = "annullata"

class BookingRequest(BaseModel):          # input di POST /booking
    person_id: str                        # PSEUDONIMO
    experience_id: str
    quando: datetime                      # data e ora richieste per l'esperienza

class Booking(BaseModel):
    id: str
    person_id: str                        # PSEUDONIMO
    experience_id: str
    quando: datetime
    stato: BookingStatus = BookingStatus.RICHIESTA
    prezzo_eur: float                     # snapshot: il prezzo dell'ExperienceNode può
                                           # cambiare nel tempo, la Booking congela quanto
                                           # pattuito al momento della richiesta (>= 0)
    creato_il: datetime

class CommissionRecord(BaseModel):
    """Dato CONTABILE, separato da `Booking` per prescrizione ethics-guardian
    (stesso principio di `attribuzione` in `GraphCandidate`, sezione 2):

    la commissione è calcolata DOPO che l'Experience Engine ha già scelto la
    tappa — lo scoring lavora su `GraphCandidate`/`ExperienceNode`, che non
    contengono e non importano questo tipo. Tenere `CommissionRecord` in un
    modello a parte, mai raggiungibile da `experience_engine.rules`, rende
    STRUTTURALMENTE impossibile che un domani la commissione diventi un input
    di scoring: non esiste un percorso di import che colleghi i due moduli."""
    booking_id: str
    importo_eur: float                    # >= 0
    percentuale: float = 0.15             # in [0,1]; commissione sul prezzo, non sul ranking
    registrata_il: datetime
```

## 6. Eventi comportamentali (per il recommender e l'Index)

```python
class BehaviorEvent(BaseModel):
    person_id: str                    # pseudonimo
    tipo: Literal["view","stop","photo","booking","review","skip","memory_contrib"]
    experience_id: str
    ts: datetime
    # NIENTE PII. Aggregabile.
```

## 7. Urban Intelligence Index — indicatori (anonimi e aggregati)

```python
class UrbanIntelligenceIndex(BaseModel):
    """La salute CULTURALE della città, non solo quella economica.
    Tutti i valori sono aggregati e non re-identificabili."""
    periodo: str                      # es. "2026-07"
    tempo_medio_esperienza_min: float
    coinvolgimento: float             # 0..1
    soddisfazione: float | None = None  # 0..5, opzionale: nessuna fonte dati reale
                                       # oggi (niente recensioni/survey in prodotto);
                                       # None finché non esiste, mai un valore stimato
    tasso_ritorno: float              # 0..1
    # tasso in [0,1], non conteggio grezzo: coppie consecutive di un
    # itinerario NON collegate nel grafo, allo snapshot preso a INIZIO
    # periodo, sul totale delle coppie non collegate disponibili in quello
    # stesso snapshot. Un conteggio grezzo scenderebbe da solo man mano che
    # il grafo cresce (più relazioni = meno coppie "non collegate"),
    # confondendo la crescita del grafo con un calo dell'esplorazione
    # spontanea.
    nuovi_percorsi: float              # 0..1 — itinerari emergenti e inattesi
    attivazione_locale: float         # 0..1 quanto il territorio minore viene raggiunto
    distribuzione_flussi: float       # 0..1  1 = distribuiti, 0 = concentrati (overtourism)
    contributi_memoria: int           # crescita della Urban Memory
```

## 8. API (BFF) — contratto sintetico

```
POST /session/onboarding   -> EmotionalProfile
POST /itinerary            (VisitorContext) -> Itinerary
POST /itinerary/adapt      (Itinerary + Signal) -> Itinerary
POST /events               (BehaviorEvent) -> 202
POST /memory               (MemoryContribution) -> 201   # richiede consenso
GET  /memory/{place_id}    -> list[MemoryContribution]   # solo contenuti curati
POST /booking              (BookingRequest) -> Booking   # commissione registrata a parte,
                                                          # DOPO la scelta (CommissionRecord)
GET  /dashboard/flows      -> heatmap aggregata
GET  /dashboard/index      -> UrbanIntelligenceIndex
```

Modelli di richiesta:

```python
class OnboardingAnswer(BaseModel):
    """Una risposta della conversazione di onboarding ("Hai voglia di
    perderti?"...). Testo libero: il parsing è del servizio RAG."""
    domanda_id: str
    risposta: str

class OnboardingRequest(BaseModel):        # input di POST /session/onboarding
    risposte: list[OnboardingAnswer]       # (output: EmotionalProfile, già esistente)
    lingua: str = "it"

class AdaptRequest(BaseModel):             # input di POST /itinerary/adapt
    itinerary: Itinerary
    signal: Signal
```

> OpenAPI generato da FastAPI è la versione autoritativa dell'API; questo blocco è il riassunto.

## Vincoli trasversali (verificati da `ethics-guardian`)

- Nessun campo di questi contratti contiene PII.
- `reason` è obbligatorio ovunque compaia una raccomandazione (vincolo di contratto:
  `min_length=1` su `ExperienceCandidate.reason` e `ItineraryStop.reason`).
- `GraphCandidate.attribuzione` è narrazione trasparente, sempre separata da
  `connessioni`: non deve mai influenzare lo score (nessun "acquisto" di visibilità).
- `MemoryContribution.consenso` deve essere `True` per essere persistito. Nessuna eccezione.
- `MemoryContribution.licenza` è sempre tracciata (vincolo di contratto: `min_length=1`,
  mai vuota).
- `MemoryContribution.riguarda` non può essere vuoto (vincolo di contratto: `min_length=1`).
- Ogni id in `MemoryContribution.riguarda` deve esistere nel Knowledge Graph: il
  collegamento è atomico, nessun nodo `:Memoria` orfano (verificato al link-time, non
  esprimibile nel contratto Pydantic).
- Un contributo non può raggiungere `curato=True` se un id in `riguarda` non esiste nel
  Knowledge Graph: la curatela verifica i target (`InvalidTargetsError`), il linker resta
  atomico al link-time. Il submit NON dipende dal grafo: il conferimento del Cittadino è
  sempre possibile.
- Nessun campo esprime "priorità a pagamento": la visibilità non è acquistabile.
- `Partner.abbonamento_attivo` è l'UNICA leva che decide presenza/assenza di un'esperienza
  tra i candidati (filtro duro booleano su `ExperienceNode.partner_abbonamento_attivo`),
  MAI un input di scoring. Il modello di ricavo è un abbonamento di presenza, mai un'asta
  sulla visibilità: nessun contratto definisce (né deve mai definire) campi come "peso",
  "boost" o "priorita_pagata".
- Nessun campo di `Booking` o `CommissionRecord` è mai letto dallo scoring dell'Experience
  Engine: `experience_engine.rules` non importa questi tipi. `CommissionRecord` è
  registrato DOPO che l'Experience Engine ha già scelto la tappa (dato contabile
  a posteriori, mai un input ex-ante).
- `Booking.prezzo_eur` è uno snapshot al momento della richiesta (non il prezzo corrente
  di `ExperienceNode`): la Booking è un contratto tra persona e partner, non deve
  cambiare se il listino cambia dopo la prenotazione.
