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

class StatoSegnaleFluttuante(str, Enum):
    """Stato di persistenza di un SegnaleFluttuante — NON la macchina a stati
    completa del canale fluttuante (submitted/blocked/approved/rejected/
    expired, quella resta design, non codice: docs/STATE_MACHINE.md,
    docs/PROMOZIONE_TRACCIA.md), stesso principio già applicato da
    MemoryLinkState (§4). Qui solo il minimo che rende un segnale
    persistibile e interrogabile: attivo ora, oppure scaduto."""
    ATTIVO = "attivo"
    EXPIRED = "expired"          # nome in inglese: stesso termine letterale già
                                  # usato per lo stesso concetto in STATE_MACHINE.md/
                                  # PROMOZIONE_TRACCIA.md, un solo vocabolario

class SegnaleFluttuante(BaseModel):
    """Qualcosa che accade ORA e domani non c'è (un violinista in piazza,
    artisti di strada) — vive in Signal.eventi_attivi, stato del mondo in
    questo momento, NON un nodo del grafo, NON il livello "programmato"
    (:Evento, con data e organizzatore — fuori scope, vedi docs/LIMITI.md).

    valido_fino/stato fondano la persistenza di questo contratto: Signal
    resta transitorio (costruito per la singola richiesta, mai persistito),
    ma il SegnaleFluttuante che porta ORA una scadenza assoluta può
    sopravvivere a quella singola richiesta — fondazione del canale
    fluttuante persistente (repository/sweep/ledger, task successivo).
    Comportamento INVARIATO per ogni Signal costruito prima di questo campo.

    CONFINE ESPLICITO, deliberatamente NON colmato da un `valido_da`: il
    fluttuante "accade DA ADESSO" — nessun inizio programmabile. Un evento
    annunciato in anticipo è per definizione un :Evento PROGRAMMATO (livello
    diverso, fuori scope, vedi docs/PROMOZIONE_TRACCIA.md), non un
    fluttuante."""
    id: str
    descrizione: str                  # "un violinista suona in piazza" — alimenta il reason (min 1 carattere)
    temi: list[str]                   # stessa forma di ExperienceNode.temi (min 1 elemento)
    place_id: str                     # dove accade, il luogo vicino
    # OBBLIGATORIO, nessun default: garanzia esplicita di non-commercialità.
    # "Artista davanti alla nostra gelateria" è pubblicità, non ammessa —
    # bloccato per costruzione da segnale_fluttuante_ammissibile, mai
    # lasciato al buon senso di chi consuma il segnale.
    non_commerciale: bool
    # Scadenza ASSOLUTA, timezone-aware UTC (field_validator: rifiuta un
    # datetime naive — stesso vincolo dell'assert su tzinfo in
    # graph.seed_lucca per RelazioneVicino.creato_il). OBBLIGATORIO, nessun
    # default: un fluttuante persistito senza scadenza vivrebbe per sempre.
    valido_fino: datetime
    # Default ATTIVO: comportamento invariato per ogni segnale costruito
    # prima di questo campo. model_validator: se valido_fino è già nel
    # passato al momento della costruzione, NORMALIZZA a EXPIRED
    # (qualunque valore passato) invece di rifiutare la costruzione — un
    # SegnaleFluttuante deve poter rappresentare un record già scaduto letto
    # da un repository/audit; rifiutarlo romperebbe il round-trip che ogni
    # altro contratto di questo file garantisce. Diverso da affollamento
    # (§1, rifiutato se fuori scala): lì il dato è incoerente col dominio,
    # qui è un fatto passato perfettamente coerente, solo già esaurito.
    stato: StatoSegnaleFluttuante = StatoSegnaleFluttuante.ATTIVO

def segnale_fluttuante_ammissibile(segnale: SegnaleFluttuante) -> bool:
    """Filtro duro unico: `segnale.non_commerciale`. "Visibilità non
    acquistabile" applicata al vettore "segnalare invece di pagare una
    commissione" — un solo punto, riusato da
    experience_engine.rules.segnali_fluttuanti_pertinenti."""
    return segnale.non_commerciale

class Signal(BaseModel):              # stato del mondo, ORA
    meteo: Literal["sereno","pioggia","caldo","freddo"]
    affollamento: dict[str, float]    # place_id -> 0..1 (validato: ogni valore in [0,1])
    stanchezza: float                 # 0..1, sale durante la giornata
    ora: time
    # 0=lunedì...6=domenica (date.weekday()). Opzionale, default None. Se `data`
    # è presente e questo è None viene DERIVATO = data.weekday() (non è un
    # giorno fabbricato: viene da una data dichiarata dal client; `data` è la
    # fonte unica del "quando" per giorno). Se `data` è None resta com'è
    # (anche None) e `rientra_in_orario` (§2) non esclude nulla per giorno.
    # ATTENZIONE: la derivazione ACCENDE in produzione il filtro sugli orari
    # di apertura, prima inerte perché nessun client mandava il giorno. Gli
    # orari sono valutati all'ARRIVO di ogni tappa, NON all'`ora` del segnale:
    # composizione = `rules.aperta_durante(esperienza, giorno, arrivo)` slot per
    # slot in `_seleziona_tappe` (il pre-filtro `passa_filtri_statici` non li
    # guarda); adattamento = sostituto valutato all'arrivo ricalcolato +
    # `_taglia_fuori_orario` (TAGLIATA_ORARIO). `passa_filtri_duri(..., *,
    # arrivo)` = statici + aperta_durante. Usato per `ExperienceNode.orari_apertura`.
    giorno_settimana: int | None = None      # se presente: 0..6
    # Data (calendario LOCALE della città) della visita, mandata dal CLIENT
    # insieme a `ora` (stessa fonte, stesso orologio: nessuno sfasamento
    # UTC/locale). Opzionale, default None: MAI una data fabbricata. Se None il
    # contratto non decide: l'Experience Engine tratta l'assenza come
    # fail-closed (nessun EventoPromosso). Se presente DERIVA `giorno_settimana`.
    # Validatore: `data` presente e `giorno_settimana` None -> derivato;
    # entrambi presenti devono valere `data.weekday() == giorno_settimana`,
    # altrimenti ValueError.
    data: date | None = None
    # Segnali FLUTTUANTI attivi ORA. Era `list[str]` (dichiarato nel
    # contratto, mai letto da nessuna logica — verificato prima di questo
    # cambio): un interruttore già cablato, mai acceso. Lista vuota
    # (default) = nessun segnale attivo, comportamento invariato per ogni
    # chiamante che non lo popola.
    eventi_attivi: list[SegnaleFluttuante] = []
    # Istante UTC (ISO 8601) mandato dal client. Opzionale, default None: senza
    # istante il comportamento è identico a prima. Validatore: deve essere
    # timezone-aware (un datetime naive -> errore di validazione, un istante
    # senza fuso è ambiguo) e viene NORMALIZZATO a UTC.
    # Il contratto NON deriva ora/data/giorno_settimana da `istante` (non
    # conosce il fuso della città): lo fa il BFF con `CITY_TZ`. Se `istante` è
    # presente il BFF SOSTITUISCE `ora`, `data` e `giorno_settimana` con i valori
    # ricavati in `CITY_TZ` (l'istante vince sui valori del dispositivo). Se
    # `CITY_TZ` manca o non è valido il BFF ignora `istante`, usa `ora`/`data`
    # del client e lo scrive nel log (stesso schema fail-closed degli eventi
    # promossi: 200 e log, nessun valore inventato). `ora` resta OBBLIGATORIO.
    # `istante` è solo un dato di ingresso del BFF: non entra in scoring né in
    # `segnali_rilevanti`.
    istante: datetime | None = None

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

class FasciaApertura(BaseModel):
    """Una fascia settimanale RICORRENTE in cui un'esperienza è aperta.
    Validazione MINIMA (Wave 3a+): solo un pattern che si ripete ogni
    settimana. NON modella eccezioni calendariali, festività, chiusure
    straordinarie, capienza o conflitti di slot — si disegnano quando una
    bottega reale ne dichiara il bisogno, non prima (docs/LIMITI.md)."""
    giorno_settimana: int              # 0=lunedì ... 6=domenica (date.weekday())
    apertura: time
    chiusura: time                     # deve essere > apertura: niente turni a cavallo di mezzanotte

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
    # booleano in `passa_filtri_statici`), MAI un input numerico dello scoring:
    # così "visibilità non acquistabile" è strutturale, non una convenzione —
    # lo scoring non ha nemmeno bisogno di importare `Partner` o `prezzo_eur`.
    partner_abbonamento_attivo: bool = True
    # Deliberatamente NON derivato da `partner_id is not None`: presenza
    # commerciale (chi offre l'esperienza) e prenotabilità (se si può
    # prenotare) sono concetti distinti. Un'esperienza gratuita e senza
    # partner può essere prenotabile (posti limitati); un'esperienza con
    # partner può non esserlo.
    prenotabile: bool = False
    # Fasce settimanali ricorrenti in cui l'esperienza è aperta. Lista VUOTA
    # (default) = nessun vincolo dichiarato: SEMPRE considerata aperta, per
    # costruzione — comportamento invariato per ogni esperienza che non
    # dichiara orari (tutte quelle del seed oggi). Letta da
    # `rientra_in_orario(orari_apertura, giorno_settimana, ora) -> bool`
    # (packages/contracts), riusata IDENTICA da `experience_engine.rules.
    # aperta_durante` (wrapper unico con durata_min=esperienza.durata_min,
    # valutato all'ARRIVO della tappa; parte di `passa_filtri_duri`) e da
    # `marketplace.service.request_booking` (validazione della
    # prenotazione): stessa informazione, un solo modello, due usi.
    orari_apertura: list[FasciaApertura] = []

def rientra_in_orario(orari_apertura: list[FasciaApertura], giorno_settimana: int | None,
                      ora: time, *, durata_min: int = 0) -> bool: ...
    # Un solo interprete degli orari, tre usi: composizione, prenotazione
    # (durata_min=0) e adattamento (durata_min>0).
    # - lista vuota o giorno None -> True (nessun vincolo), sempre.
    # - durata_min=0 (default): IDENTICA a prima, `apertura <= ora < chiusura`
    #   in almeno una fascia del giorno. Il marketplace non passa durata_min.
    # - durata_min>0: True se [ora, ora+durata_min] cade interamente in UNA
    #   fascia del giorno: `apertura <= ora` e `ora+durata <= chiusura`, calcolato
    #   in MINUTI dalla mezzanotte (mai aritmetica su `time`, che si riavvolge).
    #   Un intervallo che supera le 24:00 non rientra mai.
    # - durata_min<0 -> ValueError.
    # - `ora` è l'ARRIVO della tappa (non l'ora del segnale) per l'engine.

# Codifica degli orari per Neo4j (packages/contracts/contracts/orari.py, esportata
# da `contracts`). Neo4j non accetta liste di mappe come proprietà: ogni fascia è
# UNA stringa "g|HH:MM|HH:MM" (g = 0..6, 0=lunedì come date.weekday(); ore a due
# cifre con zero iniziale; niente spazi né secondi). L'UNICO modulo che conosce il
# formato: chi scrive (export cypher) e chi legge (loader, Neo4jCandidateSource)
# lo importa da lì.
#   codifica_fasce(fasce: Sequence[FasciaApertura]) -> list[str]
#   decodifica_fasce(valori: Sequence[str]) -> list[FasciaApertura]
# Validi:      "0|10:00|18:00"   "6|09:30|13:00"   (più fasce nello stesso giorno ammesse)
# Non validi:  "7|10:00|18:00" (giorno)   "0|9:00|18:00" (ora senza zero)
#              "0|10:00|18:00:00" (secondi)   "0| 10:00|18:00" (spazi)
#              "0|18:00|10:00" e "0|10:00|10:00" (chiusura <= apertura)
#              "0|25:00|26:00" (ora non valida)   42 / None (non stringa)
# FAIL-CLOSED: decodifica_fasce solleva ValueError (citando la stringa) per
# qualunque valore malformato; MAI lista vuota né stringa saltata, perché una
# lista vuota significa "sempre aperto" e un orario guasto non deve mai diventarlo.
# Andata e ritorno esatto, ordine preservato: decodifica(codifica(x)) == x.
# codifica_fasce rifiuta (ValueError) orari con secondi o fuso, non rappresentabili.

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
    # (+ " (esempio dimostrativo)" prima del punto finale se la bottega è fittizia)

class EventoPromosso(BaseModel):
    """Un `:Evento` PROMOSSO e ATTIVO nel Knowledge Graph (Fase 3): un pattern
    ricorrente rilevato da tracce fluttuanti, promosso da una decisione umana
    esplicita (`urban_memory.promozione_evento`), che ora vive come nodo
    permanente del grafo — livello diverso da `SegnaleFluttuante` (§1,
    `Signal.eventi_attivi`, "accade ORA e domani non c'è"): questo è il
    livello "programmato", con una cadenza propria.

    Stesso principio di minimalismo di `SegnaleFluttuante`: SOLO ciò che
    serve per comparire come tappa in coda in un itinerario, letto dal grafo
    da `services/api` (il BFF) e passato a
    `experience_engine.engine.compose_itinerary` come parametro iniettabile
    — il motore dipende SOLO dai contratti, non importa mai `graph` né `rag`
    (vedi il docstring di `compose_itinerary`), stesso principio già
    applicato a `GraphCandidate`.

    Deliberatamente ASSENTI, e perché:
    - `stato`: chi costruisce la lista da passare al motore filtra GIÀ per
      `stato='attivo'` PRIMA di costruire questo tipo — stesso principio per
      cui `Signal.eventi_attivi` arriva al motore già filtrato ai soli
      fluttuanti attivi, mai con uno stato da ricontrollare a valle. Un
      `EventoPromosso` che raggiunge il motore è, per costruzione, sempre
      attivo.
    - `promosso_da`/`promosso_il`: accountability della DECISIONE di
      promozione (chi, quando), non pertinente al CONSUMO in un itinerario.
    - nessun campo narrativo/descrizione: non esiste nulla di equivalente sul
      nodo `:Evento` reale — verificato, la `descrizione` del segnale
      fluttuante originale non sopravvive alla promozione (vedi
      `50_promozione_evento_write.cypher`).

    Finestra temporale: il contratto trasporta SOLO i FATTI grezzi
    (`ultima_occorrenza`, `cadenza_giorni`); la proiezione (ultima + k*cadenza,
    k>=1, occorrenza più vicina a `Signal.data`) e la DECISIONE "in finestra
    sì/no" le prende solo l'Experience Engine (funzione pura). "Se è vivo" resta
    a `stato` (già filtrato a monte): la finestra decide solo "quando".
    `ultima_occorrenza` è data LOCALE della città, confrontabile con
    `Signal.data`; la conversione dall'UTC del ledger la fa il BFF con un fuso
    da configurazione (mai nel codice). Il `creato_il` della traccia nel ledger
    è il `valido_fino` UTC del segnale scaduto (calcolato dal server in
    submit_signal), non l'istante dello sweep pigro (`sweep_and_fetch_active`,
    eseguito solo quando qualcuno chiama POST /itinerary): la transizione a
    `expired` può avvenire giorni dopo, il timbro no. Resta l'imprecisione di
    `valido_fino` rispetto all'occorrenza reale (è la fine dichiarata della
    finestra del segnale, non il suo inizio), e le tracce depositate prima di
    questa correzione, timbrate allo sweep, restano sfasate in avanti
    (append-only, mai riscritte)."""
    id: str        # id deterministico del nodo :Evento (evento_id_per_pattern)
    place_id: str  # il :Luogo a cui è ancorato (SI_SVOLGE_A)
    ultima_occorrenza: date      # data LOCALE (non UTC) dell'ultima occorrenza nel ledger
    cadenza_giorni: float        # > 0 e finito (Field(gt=0, allow_inf_nan=False)): inf/nan rifiutati
    temi: list[str]  # stessa forma di SegnaleFluttuante.temi/ExperienceNode.temi (min 1 elemento)
```

### VocabolarioTemi — le categorie tematiche dichiarate dalla città

```python
class VocabolarioTemi(ContractModel):   # frozen=True, extra="forbid"
    contemplativi: frozenset[str]   # id di Tema (gruppo; può essere vuoto)
    arte: frozenset[str]            # id di Tema (gruppo; può essere vuoto)
    insoliti: frozenset[str]        # id di Tema (gruppo; può essere vuoto)
    verde: frozenset[str]           # id di Tema (gruppo; può essere vuoto)
    bambini: str                    # UN id di Tema (match per appartenenza `in temi`), es. "con-bambini"
```

- **Semantica:** dato della città, non del motore. Il motore lo riceve e non lo
  inventa (nessun default cablato). Serve solo all'affinità tematica (profilo
  contemplazione/arte/curiosità/con_bambini, meteo caldo -> verde, coerenza
  dei segnali fluttuanti/eventi promossi), con gli stessi vincoli etici di
  `calcola_score`: non influenza la presenza dei partner, nessun campo
  commerciale, nessun nome di città.
- **Validazione:** ogni id è uno slug minuscolo non vuoto
  (`^[a-z0-9]+(-[a-z0-9]+)*$`); gli insiemi vuoti sono ammessi; `bambini` è
  obbligatorio. JSON: gli insiemi sono liste (ordine non garantito).
- **Produce:** il dataset della città selezionato da `CITY_SEED`
  (`DatasetCitta`, services/graph). **Consuma:** Experience Engine e
  recommender, via BFF (graph -> api -> experience-engine -> recommender).
- **Invariante (non nel contratto):** ogni id deve essere un `Tema` del
  dataset; lo verifica il dataset in graph, il contratto non conosce i temi.
- **Origine:** sostituisce le costanti `TEMI_CONTEMPLATIVI`, `TEMI_ARTE`,
  `TEMI_INSOLITI`, `TEMI_VERDE`, `TEMA_BAMBINI` di
  `experience_engine/rules.py` (-> `contemplativi`, `arte`, `insoliti`,
  `verde`, `bambini`).
- **REGOLA DI CURATELA (per chi cura il dataset di una città):**
  - il vocabolario si definisce per SIGNIFICATO del tema rispetto alla
    dimensione del profilo (contemplazione, arte, curiosità, verde,
    bambini), MAI in funzione di chi offre le esperienze che lo evocano;
  - un gruppo non si costruisce a partire dai temi di un partner; un tema
    evocato solo da esperienze con partner non dovrebbe entrare in un gruppo
    senza una motivazione di significato documentata nel modulo dataset;
  - coerente con "nessuno spazio è acquistabile": nessun prezzo modifica il
    vocabolario, perché darebbe affinità sistematica a un partner per via di
    dato anziché di codice;
  - **limite aperto:** la regola NON è verificata automaticamente (sarà
    registrato in `docs/LIMITI.md`). Il codice garantisce solo che i filtri
    duri e lo score non leggono campi commerciali.

## 3. AI Experience Engine — uscita

```python
class ExperienceCandidate(BaseModel):
    experience_id: str
    score: float                      # 0..1
    reason: str                       # SPIEGABILITÀ OBBLIGATORIA, in italiano (min 1 carattere)

class EsitoAdattamento(str, Enum):
    NON_TOCCATA = "non_toccata"
    SOSTITUITA = "sostituita"
    MANTENUTA_SENZA_ALTERNATIVA = "mantenuta_senza_alternativa"
    TAGLIATA_STANCHEZZA = "tagliata_stanchezza"
    TAGLIATA_TETTO_GIORNATA = "tagliata_tetto_giornata"
    TAGLIATA_ORARIO = "tagliata_orario"   # all'arrivo ricalcolato il luogo è chiuso: l'intervallo
                                          # [arrivo, arrivo+durata] non cade in una fascia di apertura.
                                          # Solo in Itinerary.tappe_escluse, mai tra le stops

class ItineraryStop(BaseModel):
    experience_id: str
    arrivo: time
    durata_min: int
    reason: str                       # SPIEGABILITÀ OBBLIGATORIA, in italiano (min 1 carattere)
    esito_adattamento: EsitoAdattamento | None = None
                                      # None = itinerario mai adattato; descrive SOLO l'ULTIMO
                                      # segnale valutato. TAGLIATA_* NON ammessi su una tappa
                                      # presente (validatore)

class TappaEsclusa(BaseModel):        # tappa tolta da un adattamento
    experience_id: str
    esito: EsitoAdattamento           # solo TAGLIATA_STANCHEZZA, TAGLIATA_TETTO_GIORNATA o TAGLIATA_ORARIO (validatore)
    reason: str                       # in italiano, min 1 carattere (spiegabilità obbligatoria)

class Itinerary(BaseModel):
    person_id: str
    stops: list[ItineraryStop]
    generated_at: datetime
    adattato_da_segnale: bool = False # True se e solo se l'ULTIMO adattamento ha almeno una tappa
                                      # SOSTITUITA o TAGLIATA (stanchezza, tetto o orario). Una tappa
                                      # MANTENUTA_SENZA_ALTERNATIVA NON lo accende (l'app lo mostra
                                      # come badge "Riscritta"): quel caso è portato da
                                      # esito_adattamento e da una frase nel reason.
    tempo_disponibile_min: int | None = None  # gt=0. Budget dichiarato alla composizione, stesso
                                      # significato di EmotionalProfile.tempo_disponibile_min.
                                      # Lo scrive solo la composizione; l'adattamento lo ricopia.
                                      # None = itinerario senza budget (precedente al campo):
                                      # l'adattamento usa profilo neutro, nessun vincolo di budget.
    tempo_effettivo_min: int | None = None    # gt=0. Budget dopo il tetto della giornata:
                                      # min(dichiarato, minuti da signal.ora alle 24:00).
                                      # Entrambi None o entrambi valorizzati; effettivo <= dichiarato
                                      # (model_validator)
    tappe_escluse: list[TappaEsclusa] = []    # tappe tolte da un adattamento (stanchezza o tetto
                                      # della giornata); si accumulano tra adattamenti successivi
```

Tutti i campi aggiunti il 2026-10-16 hanno un default: i JSON esistenti (incluso
`services/api/tests/golden/lucca_itinerari.json`) continuano a validare.

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

class MemoryLinkState(str, Enum):
    """Esito dell'aggancio automatico al Knowledge Graph, innescato quando
    curato diventa True (invariante "curato tira aggancio",
    docs/ENGINE_INVARIANTS.md §11-B). NON una macchina a stati completa
    (docs/STATE_MACHINE.md resta design): solo il minimo per distinguere un
    aggancio riuscito da uno da riprovare."""
    AGGANCIATO = "agganciato"
    AGGANCIO_FALLITO = "aggancio_fallito"       # attesa recuperabile, retry quando il grafo torna su

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
    stato_aggancio: MemoryLinkState | None = None  # esito dell'aggancio automatico al grafo,
                                       # impostato SOLO da urban_memory dopo un tentativo reale
                                       # (None finché curato=False, o mai tentato)
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

`marketplace.service.request_booking` (validazione minima, Wave 3a+) rifiuta PRIMA di persistere
— nessuna scrittura, stesso stile del rifiuto su `prenotabile=False` — se `BookingRequest.quando`
cade fuori dalle `ExperienceNode.orari_apertura` dichiarate: solleva `ExperienceNotAvailableError`,
stesso schema di `ExperienceNotBookableError`. Usa `rientra_in_orario` (§2) derivando
`giorno_settimana`/`ora` da `quando.weekday()`/`quando.time()`.

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

### Risposte dashboard (`GET /dashboard/*`) — soppressione k=10 provata al confine dell'API

Requisito non negoziabile del committente: la soglia k=10 (privacy by design, CLAUDE.md) è provata
al confine dell'API, a OGNI livello di dettaglio che l'API espone (aggregato per periodo, per
luogo, per combinazione luogo×giorno×ora). Nessuna cella soppressa può far trapelare — nemmeno
opzionalmente — un conteggio di popolazione grezzo: solo un booleano `disponibile` e il valore (o
`None` se soppresso).

```python
class DashboardIndexResponse(BaseModel):
    """Wrapper del BFF per GET /dashboard/index.

    `intelligence_index.calcola_index` solleva `DatiInsufficientiError` se un
    qualunque indicatore dell'intero periodo è sotto k=10 (raro in produzione,
    possibile su un periodo storico con pochi dati). Il BFF non propaga
    l'eccezione grezza né fabbrica un `UrbanIntelligenceIndex`: la risposta è
    sempre uno di due stati espliciti.

    Vincolo di coerenza (applicato per costruzione via `model_validator`, non
    solo per disciplina di chi popola il modello): `disponibile=True` implica
    `index is not None` e `motivo_indisponibilita is None`; `disponibile=False`
    implica il contrario. Nessuno stato intermedio."""
    periodo: str
    disponibile: bool
    index: UrbanIntelligenceIndex | None = None       # popolato SOLO se disponibile=True
    motivo_indisponibilita: str | None = None          # popolato SOLO se disponibile=False, IT

class FlowCell(BaseModel):
    """Una riga di heatmap per un luogo. Gated INDIPENDENTEMENTE dalle altre
    celle sulla soglia k=10 dei person_id distinti di QUESTA cella specifica
    (intelligence_index.soglia.valore_se_soglia — esiste già, non ancora
    cablato a nessun chiamante prima di questa wave).

    Espone SOLO `disponibile` e il conteggio (o None se soppressa): MAI un
    conteggio di popolazione (es. n_persone), nemmeno opzionale. Un conteggio
    grezzo di persone sarebbe già di per sé la violazione di re-identificazione
    che il gate deve prevenire, a prescindere dal fatto che il VALORE
    dell'indicatore venga poi nascosto. Nessun campo di questo modello può
    esporlo: garanzia strutturale, non disciplina di chi lo popola."""
    place_id: str
    disponibile: bool
    conteggio_tappe: int | None = None   # None se soppressa (sotto k=10 person_id distinti)

class DashboardFlowsResponse(BaseModel):
    """Risposta di GET /dashboard/flows. SEMPRE una riga per luogo, mai una
    combinatoria esplosiva luogo×giorno×ora in un solo payload (15 luoghi ×
    ~30 giorni × 24 ore sarebbero migliaia di righe per una singola
    chiamata). I filtri opzionali giorno/ora restringono la STESSA lista di
    celle: così l'API espone la granularità luogo×giorno×ora, un filtro alla
    volta, non un cubo precalcolato."""
    periodo: str
    giorno: date | None = None   # filtro applicato alla richiesta, se presente
    ora: int | None = None       # 0..23, fascia oraria applicata, se presente
    celle: list[FlowCell]        # una riga per luogo disponibile nel grafo
```

Vincolo di coerenza (`FlowCell`, stesso pattern di `DashboardIndexResponse`): `disponibile=True`
implica `conteggio_tappe is not None`; `disponibile=False` implica `conteggio_tappe is None`.

## 8. API (BFF) — contratto sintetico

```
POST /session/onboarding   -> EmotionalProfile
POST /itinerary            (VisitorContext) -> Itinerary
POST /itinerary/adapt      (Itinerary + Signal + EmotionalProfile?) -> Itinerary
POST /events               (BehaviorEvent) -> 202
POST /memory               (MemoryContribution) -> 201   # richiede consenso
GET  /memory/{place_id}    -> list[MemoryContribution]   # solo contenuti curati
POST /booking              (BookingRequest) -> Booking   # commissione registrata a parte,
                                                          # DOPO la scelta (CommissionRecord)
GET  /dashboard/flows      -> DashboardFlowsResponse     # query: periodo, giorno?, ora?
                                                          # heatmap aggregata, gate k=10 per cella
GET  /dashboard/index      -> DashboardIndexResponse     # query: periodo
                                                          # wrapper di UrbanIntelligenceIndex,
                                                          # esplicita "dato insufficiente" (k=10)
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
    itinerary: Itinerary                   # il budget di tempo viaggia QUI
    signal: Signal                         # (Itinerary.tempo_disponibile_min), non nella richiesta
    profile: EmotionalProfile | None = None
    # Opzionale, retrocompatibile. Se presente, il profilo del visitatore guida
    # l'ordinamento delle alternative e l'accessibilita' (accessibilita_richiesta).
    # Se assente: profilo neutro e regola prudente per tappa (una tappa accessibile
    # si sostituisce solo con una accessibile); comportamento invariato.
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
- "Curato tira aggancio" (`docs/ENGINE_INVARIANTS.md` §11-B): quando `curate_contribution`/
  `publish_pending` riceve un `linker`, l'aggancio al grafo è innescato automaticamente
  dopo `curato=True`, nella stessa chiamata — `MemoryContribution.stato_aggancio` diventa
  `AGGANCIATO` o `AGGANCIO_FALLITO` (mai lasciato `None` in modo silenzioso quando un
  `linker` è stato passato). `AGGANCIO_FALLITO` è uno stato di attesa recuperabile
  (`retry_link_contribution`), mai un vicolo cieco.
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
- La soglia di aggregazione k=10 è provata al confine dell'API a OGNI livello di dettaglio
  esposto (`DashboardIndexResponse` per l'aggregato di periodo, `FlowCell` per luogo, ed è
  a grana ancora più fine — per combinazione luogo×giorno×ora — quando `DashboardFlowsResponse`
  è filtrata da `giorno`/`ora`). Nessuno dei due modelli espone un conteggio di popolazione
  grezzo (`n_persone` o simile), nemmeno opzionale: solo un booleano `disponibile` e il valore
  (`index`/`conteggio_tappe`), o `None` se la cella è soppressa. Un conteggio di popolazione,
  anche dietro un valore soppresso, sarebbe già di per sé la violazione di re-identificazione
  che il gate deve prevenire.
- `DashboardIndexResponse` e `FlowCell` non ammettono stati intermedi tra "disponibile" e "non
  disponibile" (vincolo di contratto: `model_validator`, non solo convenzione): `disponibile=True`
  implica il valore valorizzato e l'eventuale motivo assente; `disponibile=False` implica il
  contrario.
- `ExperienceNode.orari_apertura` (lista vuota di default) e `Signal.giorno_settimana`
  (`None` di default, ricavato da `Signal.data` se il client manda solo la data) non
  escludono MAI nulla quando non dichiarati: `rientra_in_orario`
  ritorna sempre `True` in assenza di uno dei due dati — nessuna esclusione fabbricata per
  un'informazione che il chiamante non ha fornito. La stessa funzione, lo stesso modello,
  alimenta sia il filtro orari di `experience_engine.rules.aperta_durante` (valutato
  all'arrivo di ogni tappa, parte di `passa_filtri_duri`) sia la
  validazione di `marketplace.service.request_booking`: un vincolo su "cosa significa aperto"
  applicato in un solo punto, non duplicato con la possibilità di divergere.
- `SegnaleFluttuante.non_commerciale` è OBBLIGATORIO, nessun default (vincolo di contratto:
  campo richiesto, non `bool = False`/`bool = True`): chi genera un segnale fluttuante deve
  dichiararlo esplicitamente. `segnale_fluttuante_ammissibile` è l'UNICO punto che lo legge
  per decidere ammissibilità; `experience_engine.rules.calcola_score` non legge mai
  `Signal.eventi_attivi`, in nessuna forma — un'aggiunta di tappa fluttuante non altera lo
  score di nessuna esperienza permanente: "visibilità non acquistabile" applicata anche al
  vettore "segnalare invece di pagare una commissione".
- `SegnaleFluttuante.valido_fino` è OBBLIGATORIO, nessun default, e deve essere
  timezone-aware (vincolo di contratto: `field_validator`, rifiuta un `datetime` naive —
  stesso obbligo di ogni timestamp persistito nel repo). `SegnaleFluttuante.stato`
  (`StatoSegnaleFluttuante`, default `ATTIVO`) è forzato a `EXPIRED` per costruzione
  (`model_validator`) se `valido_fino` è già nel passato al momento della validazione,
  qualunque valore sia stato passato: NORMALIZZA, non rifiuta — un segnale già scaduto
  resta un dato valido (utile a un audit/repository), non un errore da bloccare in
  costruzione. Nessun campo `valido_da`: il fluttuante "accade DA ADESSO", un inizio
  programmabile è per definizione un `:Evento` PROGRAMMATO (fuori scope,
  `docs/PROMOZIONE_TRACCIA.md`).
- `EventoPromosso` (§2) è il contratto minimo — `id`/`place_id`/`temi` più i fatti della
  finestra temporale `ultima_occorrenza` (data locale) e `cadenza_giorni` (> 0), mai una
  occorrenza proiettata né una decisione "in finestra" — con cui un `:Evento`
  promosso e ATTIVO nel Knowledge Graph raggiunge `experience_engine.engine.compose_itinerary`
  come parametro iniettabile: il motore non importa `graph` né `rag`, stesso principio già
  applicato a `GraphCandidate`. Chi legge dal grafo (`services/api`) filtra GIÀ per
  `stato='attivo'` PRIMA di costruire questo tipo: nessuno stato, nessuna
  accountability di promozione (`promosso_da`/`promosso_il`) e nessun testo narrativo vivono
  in questo contratto — sono task futuri o informazioni non pertinenti al consumo in un
  itinerario (vedi il docstring del modello in `packages/contracts`).
- Adattamento e tetto della giornata (`Itinerary`, wave "adattamento"): in un itinerario con
  budget, ogni `arrivo + durata_min` deve stare entro le 24:00 della stessa giornata e la somma
  di durate e trasferimenti deve essere `<= tempo_effettivo_min`. Queste due verifiche sono
  dell'Experience Engine (non esprimibili nel contratto Pydantic). Una tappa tagliata esiste
  SOLO in `tappe_escluse` (mai tra le `stops`, vincolo di contratto sui validatori di
  `ItineraryStop.esito_adattamento` e `TappaEsclusa.esito`). L'esito è portato sia dal campo
  (`esito_adattamento` / `TappaEsclusa.esito`) sia da una frase nel `reason`, derivata in un
  UNICO punto a partire dall'esito, così campo e testo non possono divergere.

## Changelog

- **2026-10-19 — difetto j (adattamento e profilo).** Aggiunto `AdaptRequest.profile:
  EmotionalProfile | None = None` (retrocompatibile: senza `profile` il comportamento è
  invariato, profilo neutro e regola prudente per tappa). Nessun campo rinominato o rimosso.
  Consumatori: `services/api` (`POST /itinerary/adapt`, oggi `profile=None`),
  `services/experience-engine` (`adapt_itinerary`), `apps/lucca_soul_app`
  (`lib/models/adapt_request.dart`, specchio Dart: da allineare solo se l'app deve inviarlo).
- **2026-10-16 — wave "adattamento".** Aggiunti: `EsitoAdattamento` (enum),
  `ItineraryStop.esito_adattamento`, `TappaEsclusa`, `Itinerary.tempo_disponibile_min`,
  `Itinerary.tempo_effettivo_min`, `Itinerary.tappe_escluse`. Cambiata la semantica di
  `Itinerary.adattato_da_segnale` (vedi §3). Nessun campo rinominato o rimosso; tutti i campi
  nuovi hanno default. `AdaptRequest` invariato: il budget viaggia nell'itinerary. Consumatori:
  `services/experience-engine` (composizione/adattamento), `services/api` (`/itinerary`,
  `/itinerary/adapt`, golden), `apps/lucca_soul_app` (badge "Riscritta", tappe escluse).
