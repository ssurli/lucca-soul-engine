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

import re
from datetime import UTC, date, datetime, time
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "EmotionalProfile",
    "Signal",
    "SegnaleFluttuante",
    "StatoSegnaleFluttuante",
    "segnale_fluttuante_ammissibile",
    "PersonKind",
    "VisitorContext",
    "FasciaApertura",
    "ExperienceNode",
    "GraphCandidate",
    "EventoPromosso",
    "VocabolarioTemi",
    "ExperienceCandidate",
    "EsitoAdattamento",
    "ItineraryStop",
    "TappaEsclusa",
    "Itinerary",
    "MemoryKind",
    "MemoryLinkState",
    "MemoryContribution",
    "Partner",
    "BookingStatus",
    "BookingRequest",
    "Booking",
    "CommissionRecord",
    "BehaviorEvent",
    "UrbanIntelligenceIndex",
    "DashboardIndexResponse",
    "FlowCell",
    "DashboardFlowsResponse",
    "OnboardingAnswer",
    "OnboardingRequest",
    "AdaptRequest",
    "rientra_in_orario",
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


class StatoSegnaleFluttuante(str, Enum):
    """Stato di persistenza di un `SegnaleFluttuante` — NON la macchina a
    stati completa del canale fluttuante (`submitted`/`blocked`/`approved`/
    `rejected`/`expired`, quella resta design, non codice:
    `docs/STATE_MACHINE.md`, `docs/PROMOZIONE_TRACCIA.md`), stesso principio
    applicato più sotto in questo file da `MemoryLinkState` (§4). Qui solo
    il minimo che rende un segnale persistibile e interrogabile: attivo ora,
    oppure scaduto.
    Curatela, approvazione e promozione a `:Evento` restano fuori da questo
    contratto: repository/sweep/ledger sono un task successivo.

    - `ATTIVO`: `valido_fino` non è ancora passato.
    - `EXPIRED`: `valido_fino` è nel passato. Nome in inglese non per
      inconsistenza col resto del dominio (italiano, vedi CLAUDE.md), ma
      perché è il MEDESIMO termine, lettera per lettera, già usato per lo
      stesso concetto in `docs/STATE_MACHINE.md`/`docs/PROMOZIONE_TRACCIA.md`
      — un solo vocabolario tra il design della corsia fluttuanti e questo
      contratto, non due parole per la stessa cosa.
    """

    ATTIVO = "attivo"
    EXPIRED = "expired"


class SegnaleFluttuante(ContractModel):
    """Un segnale FLUTTUANTE: qualcosa che accade ORA e domani non c'è (un
    violinista in piazza, artisti di strada) — vive in `Signal.eventi_attivi`,
    accanto a meteo/affollamento: stato del mondo in questo momento, non
    struttura. NON è un nodo del grafo, NON è il livello "programmato"
    (`:Evento`, con data e organizzatore — fuori scope qui, vedi
    `docs/LIMITI.md`). Come questo segnale entra nel mondo (chi lo segnala,
    con quale prova) è il problema di `POST /events`, già documentato in
    `docs/LIMITI.md`: qui si assume che il segnale arrivi già com'è.

    `valido_fino`/`stato` (sotto) fondano la persistenza di questo
    contratto: `Signal` resta transitorio (costruito per la singola
    richiesta, mai persistito), ma il `SegnaleFluttuante` che porta con sé
    ORA una scadenza assoluta può sopravvivere a quella singola richiesta —
    fondazione del canale fluttuante persistente (repository/sweep/ledger,
    task successivo a questo). Prima di questo campo la scadenza era solo
    implicita ("chi genera la richiesta include un segnale SOLO finché è
    davvero attivo"): comportamento INVARIATO per ogni `Signal` costruito
    prima d'ora, che non popolava né poteva popolare questo campo.

    CONFINE ESPLICITO, deliberatamente NON colmato da un `valido_da`: il
    fluttuante "accade DA ADESSO" — nessun inizio programmabile. Un evento
    annunciato in anticipo è per definizione un `:Evento` PROGRAMMATO
    (livello diverso, fuori scope qui, vedi `docs/PROMOZIONE_TRACCIA.md`),
    non un fluttuante. Aggiungere un `valido_da` per gestire un segnale che
    nasce già scaduto (vedi il `model_validator` sotto) confonderebbe i due
    livelli che questo stesso docstring, sopra, dichiara distinti — non è
    una scelta rimandata, è un confine di dominio.
    """

    id: str
    # "un violinista suona in piazza" — alimenta il `reason` della tappa
    # aggiunta, mai un testo fabbricato dal motore.
    descrizione: str = Field(min_length=1)
    # Stessa forma di `ExperienceNode.temi`: riusa l'identica logica di
    # affinità (`experience_engine.rules.affinita_temi`) già usata per lo
    # scoring delle esperienze permanenti — un solo modo di intendere
    # "a chi parla questo tema", non un secondo criterio inventato qui.
    temi: list[str] = Field(min_length=1)
    place_id: str  # dove accade, il luogo vicino
    # OBBLIGATORIO, nessun default: garanzia ESPLICITA che il segnale non
    # riferisce un'attività commerciale. "Artista davanti alla nostra
    # gelateria" è pubblicità travestita da segnale, non ammessa — il filtro
    # duro (`segnale_fluttuante_ammissibile` sotto) la blocca per
    # costruzione, mai lasciato al buon senso di chi consuma il segnale.
    # Nessun default: chi genera il segnale deve dichiararlo esplicitamente,
    # stesso principio di `MemoryContribution.consenso`.
    non_commerciale: bool
    # Scadenza ASSOLUTA, timezone-aware UTC — stesso obbligo di ogni
    # timestamp persistito in questo repo (vedi l'assert su `tzinfo` nel
    # modulo dataset della città, `graph/seed_<città>.py` selezionato da
    # CITY_SEED, per `RelazioneVicino.creato_il`; epoca in
    # `graph.dataset.DatasetCitta.vicino_epoca`, default
    # `graph.dataset.VICINO_EPOCA_PREDEFINITA`, stesso pattern
    # imitato dal `field_validator` sotto: nessun contratto in
    # `packages/contracts` aveva finora bisogno di imporlo a livello
    # Pydantic, questo è il primo). OBBLIGATORIO, nessun default: un
    # fluttuante persistito senza scadenza vivrebbe per sempre — stessa
    # classe di errore che `non_commerciale` (sopra) previene per la
    # commercialità: chi genera il segnale DEVE dichiarare quando smette di
    # essere vero, mai lasciato a un default silenzioso.
    valido_fino: datetime
    # Due soli stati (vedi `StatoSegnaleFluttuante` sopra). Default `ATTIVO`:
    # comportamento INVARIATO per ogni segnale costruito prima di questo
    # campo — dentro `Signal`, transitorio, un segnale presente era sempre
    # trattato come attivo per costruzione (mai spento a metà richiesta).
    stato: StatoSegnaleFluttuante = StatoSegnaleFluttuante.ATTIVO

    @field_validator("valido_fino")
    @classmethod
    def _valido_fino_tz_aware(cls, v: datetime) -> datetime:
        # Stesso vincolo, stesso messaggio d'errore concettuale dell'assert
        # su `RelazioneVicino.creato_il` nel modulo dataset della città
        # (`graph/seed_<città>.py`, vedi `graph.dataset`): un timestamp
        # naive non è confrontabile in modo affidabile con
        # `datetime.now(UTC)` (il confronto sotto, e ogni sweep futuro che
        # legga questo campo dal repository).
        if v.tzinfo is None:
            raise ValueError(
                "SegnaleFluttuante.valido_fino deve essere timezone-aware "
                "(UTC) — stesso vincolo di ogni timestamp persistito in "
                "questo repo (vedi graph.dataset, modulo dataset della città)"
            )
        return v

    @model_validator(mode="after")
    def _expired_se_gia_scaduto(self) -> SegnaleFluttuante:
        # Caso-limite: `valido_fino` già nel passato al momento della
        # costruzione — un ritardo/errore di chi genera il segnale, non
        # "programmazione" (per quello esiste il confine `valido_da`,
        # deliberatamente assente, vedi il docstring della classe).
        #
        # Scelta: NORMALIZZA (forza `stato=EXPIRED`, qualunque valore sia
        # stato passato), non rifiuta. Motivo, in ordine di peso:
        # 1. un `SegnaleFluttuante` deve poter rappresentare un record già
        #    scaduto letto da un repository/audit (il task successivo che
        #    questo contratto fonda) — rifiutare la costruzione
        #    renderebbe impossibile ricostruire un segnale scaduto da uno
        #    storico, rompendo il round-trip che ogni altro contratto di
        #    questo file garantisce (vedi i test `test_round_trip_json_*`);
        # 2. descrizione/temi/place_id restano informativi anche a cose
        #    fatte (utili per un audit), buttarli per un errore di TEMPO —
        #    non di CONTENUTO — sarebbe una perdita di dato onesto, non una
        #    protezione.
        # Diverso da `_affollamento_in_scala` sotto (che RIFIUTA un valore
        # fuori scala): lì il dato è strutturalmente incoerente col dominio
        # (un affollamento del 150% non significa nulla); qui il dato è
        # perfettamente coerente — un fatto passato — solo già esaurito.
        gia_scaduto = self.valido_fino <= datetime.now(UTC)
        if gia_scaduto and self.stato != StatoSegnaleFluttuante.EXPIRED:
            self.stato = StatoSegnaleFluttuante.EXPIRED
        return self


def segnale_fluttuante_ammissibile(segnale: SegnaleFluttuante) -> bool:
    """Filtro duro, unico e centrale: un segnale fluttuante che riferisce
    un'attività commerciale non è MAI ammissibile, qualunque sia la sua
    coerenza con un profilo. "Visibilità non acquistabile" applicata a un
    vettore nuovo (segnalare invece di pagare una commissione): un solo
    punto verificabile, riusato da chi consuma `Signal.eventi_attivi` —
    `experience_engine.rules.segnali_fluttuanti_pertinenti` applica QUESTO
    controllo prima, mai un controllo scritto una seconda volta altrove."""
    return segnale.non_commerciale


class Signal(ContractModel):
    """Stato del mondo, ORA."""

    meteo: Literal["sereno", "pioggia", "caldo", "freddo"]
    affollamento: dict[str, float]  # place_id -> 0..1 (validato: ogni valore in [0,1])
    stanchezza: float = Field(ge=0, le=1)  # sale durante la giornata
    ora: time
    # Giorno della settimana (0=lunedì...6=domenica, coerente con
    # `datetime.date.weekday()`), per valutare `ExperienceNode.orari_apertura`
    # (Wave 3a+, validazione minima — vedi FasciaApertura sotto). OPZIONALE,
    # default None. NON è un giorno fabbricato: se `data` è presente, il
    # giorno è DERIVATO da una data dichiarata dal client
    # (`giorno_settimana = data.weekday()`, vedi il validatore sotto), quindi
    # `data` è la fonte unica del "quando" per giorno. Se `data` è `None` e il
    # chiamante non lo specifica resta `None` (nessun default silenzioso tipo
    # "sempre lunedì": escluderebbe candidati per un motivo che nessuno ha
    # dichiarato); `rientra_in_orario` (sotto) allora non esclude nulla per
    # giorno.
    # ATTENZIONE (cambio di comportamento): la derivazione ACCENDE per la
    # prima volta in produzione il filtro sugli orari di apertura per giorno
    # (`rientra_in_orario`), finora inerte perché nessun client mandava
    # `giorno_settimana`; ora l'app manda `data`. Il giorno è valutato
    # all'ARRIVO di ogni tappa, NON all'`ora` del segnale: in composizione
    # `rules.aperta_durante(esperienza, giorno, arrivo)` è controllata slot per
    # slot in `_seleziona_tappe` (il pre-filtro statico `passa_filtri_statici`
    # non guarda gli orari); in adattamento il sostituto è valutato all'arrivo
    # ricalcolato e `_taglia_fuori_orario` toglie (TAGLIATA_ORARIO) le tappe
    # chiuse all'arrivo. `passa_filtri_duri(..., *, arrivo)` è la somma dei due.
    giorno_settimana: int | None = Field(default=None, ge=0, le=6)
    # Data (calendario LOCALE della città) della visita, mandata dal CLIENT
    # insieme a `ora`: stessa fonte e stesso orologio, quindi nessuno
    # sfasamento UTC/locale tra le due. Serve a valutare la finestra
    # temporale degli `EventoPromosso`. OPZIONALE, default None: MAI una data
    # fabbricata — un default silenzioso (es. "oggi" del server) farebbe
    # comparire o sparire eventi per una data che nessuno ha dichiarato. Se
    # `None` il contratto non decide nulla: è l'Experience Engine a trattare
    # l'assenza come fail-closed (nessun evento promosso). Se presente,
    # DERIVA `giorno_settimana` (= `data.weekday()`) quando questo è omesso.
    data: date | None = None
    # Segnali FLUTTUANTI attivi ORA (vedi `SegnaleFluttuante` sopra). Era
    # `list[str]` — dichiarato nel contratto, mai letto da nessuna logica
    # (né `experience_engine.rules`, né `.engine`, né l'adattamento):
    # verificato prima di questo cambio, non un campo nuovo ma un
    # interruttore già cablato, mai acceso. Default lista vuota = nessun
    # segnale attivo, comportamento INVARIATO per ogni chiamante che non lo
    # popola (tutti, oggi).
    eventi_attivi: list[SegnaleFluttuante] = []
    # Istante UTC (ISO 8601) mandato dal client. OPZIONALE, default None:
    # senza istante il comportamento è IDENTICO a prima. Deve essere
    # timezone-aware (un istante senza fuso è ambiguo: errore di
    # validazione) e viene NORMALIZZATO a UTC. Il contratto NON deriva
    # `ora`/`data`/`giorno_settimana` da `istante`: non conosce il fuso della
    # città. Lo fa il BFF con `CITY_TZ`: se `istante` è presente il BFF
    # SOSTITUISCE `ora`, `data` e `giorno_settimana` con i valori ricavati in
    # `CITY_TZ` (l'istante vince sui valori del dispositivo). Se `CITY_TZ`
    # manca o non è valido il BFF ignora `istante`, usa `ora`/`data` del
    # client e lo scrive nel log (fail-closed come gli eventi promossi: 200 e
    # log, nessun valore inventato). `ora` resta OBBLIGATORIO. `istante` è
    # solo un dato di ingresso del BFF: non entra in scoring né in
    # `segnali_rilevanti`.
    istante: datetime | None = None

    @field_validator("istante")
    @classmethod
    def _istante_aware_in_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError(
                "istante deve avere un fuso orario (ISO 8601 con offset o 'Z'): "
                f"{v.isoformat()!r} è naive e quindi ambiguo"
            )
        return v.astimezone(UTC)

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

    @model_validator(mode="after")
    def _data_coerente_con_giorno_settimana(self) -> Signal:
        # Due fonti per lo stesso fatto che si contraddicono: meglio rifiutare
        # che scegliere in silenzio quale delle due credere (il filtro orari
        # legge `giorno_settimana`, la finestra eventi legge `data`).
        if self.data is None:
            return self
        if self.giorno_settimana is None:
            # Derivazione: `data` è la fonte unica del giorno. ContractModel
            # NON è frozen e non ha validate_assignment, quindi l'assegnazione
            # diretta è corretta e non ri-esegue i validatori.
            self.giorno_settimana = self.data.weekday()
        elif self.data.weekday() != self.giorno_settimana:
            raise ValueError(
                f"data {self.data.isoformat()} è un giorno {self.data.weekday()} "
                f"(0=lunedì...6=domenica), incoerente con "
                f"giorno_settimana={self.giorno_settimana}"
            )
        return self


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


class FasciaApertura(ContractModel):
    """Una fascia settimanale RICORRENTE in cui un'esperienza è aperta.

    Validazione MINIMA (Wave 3a+, richiesta esplicitamente prima del Living
    Lab dopo che si è trovato lo scarto tra il White Paper — che promette
    "gestisce disponibilità" nel Marketplace — e il codice, che non lo
    faceva: vedi `docs/LIMITI.md`). Modella SOLO un pattern che si ripete
    ogni settimana: NON eccezioni calendariali, NON festività, NON chiusure
    straordinarie, NON capienza/conflitti di slot. Costruire quelle cose
    ORA, senza una bottega reale davanti che ne dichiari il bisogno, sarebbe
    una scelta di modellazione arbitraria — lo stesso principio già
    applicato in questo repo a `tasso_ritorno`/`nuovi_percorsi`
    (`docs/LIMITI.md`): si disegnano quando un caso reale le forza, non
    prima.
    """

    giorno_settimana: int = Field(ge=0, le=6)  # 0=lunedì ... 6=domenica (date.weekday())
    apertura: time
    chiusura: time

    @model_validator(mode="after")
    def _chiusura_dopo_apertura(self) -> FasciaApertura:
        # Niente turni a cavallo di mezzanotte in questa versione minima:
        # una fascia vive interamente dentro UN giorno. Un turno notturno
        # reale (es. 22:00->02:00) andrebbe modellato con una decisione
        # esplicita in più (due fasce? un giorno "esteso"?) — la stessa
        # classe di scelta che questo contratto rimanda finché non c'è una
        # bottega reale che la richiede.
        if self.chiusura <= self.apertura:
            raise ValueError(
                f"FasciaApertura: chiusura ({self.chiusura}) deve essere DOPO "
                f"apertura ({self.apertura}) — niente turni a cavallo di "
                "mezzanotte in questa versione minima del contratto"
            )
        return self


def rientra_in_orario(
    orari_apertura: list[FasciaApertura],
    giorno_settimana: int | None,
    ora: time,
    *,
    durata_min: int = 0,
) -> bool:
    """Vero se `ora` (nel giorno `giorno_settimana`) rientra in almeno una
    fascia di `orari_apertura` — oppure se non c'è alcun vincolo da
    applicare.

    Un solo interprete degli orari, tre usi: composizione (istante di
    arrivo), prenotazione (`durata_min=0`) e adattamento (con `durata_min`
    > 0: l'intero intervallo [ora, ora + durata_min] deve cadere in UNA
    fascia).
    - `durata_min == 0` (default): risultato IDENTICO al comportamento
      storico, `apertura <= ora < chiusura` in almeno una fascia del giorno.
    - `durata_min > 0`: `apertura <= ora` e `ora + durata_min <= chiusura`,
      calcolato in MINUTI dalla mezzanotte (mai aritmetica su `time`, che si
      riavvolge). Un intervallo che supera le 24:00 non rientra mai.
    - `durata_min < 0`: `ValueError`.

    Due casi fanno passare SEMPRE, per costruzione, mai un'esclusione
    fabbricata per un dato che il chiamante non ha fornito:
    - `orari_apertura` vuota: nessun orario dichiarato per questa
      esperienza (default di `ExperienceNode.orari_apertura` — ogni
      esperienza del seed oggi, comportamento INVARIATO);
    - `giorno_settimana` è `None`: il chiamante non ha specificato il
      giorno (default di `Signal.giorno_settimana`) — non si inventa un
      giorno per applicare un filtro che nessuno ha chiesto.

    Funzione PURA, riusata IDENTICA (stessa informazione, un solo modello,
    due usi) da:
    - `experience_engine.rules.aperta_durante` (wrapper unico, con
      `durata_min=esperienza.durata_min`) — filtro orari dell'itinerario,
      con `giorno_settimana` da `Signal` e `ora` = ARRIVO della tappa (non
      l'ora del segnale); parte di `passa_filtri_duri(..., *, arrivo)`;
    - `marketplace.service.request_booking` — validazione della
      prenotazione, con `giorno_settimana`/`ora` derivati da
      `BookingRequest.quando` (`.weekday()`/`.time()`, sempre presenti: una
      `datetime` concreta non è mai "giorno sconosciuto").

    Vive qui, in `packages/contracts` — non in `experience_engine` né in
    `marketplace` — perché nessuno dei due servizi importa l'altro
    (verificato da `services/marketplace/tests/test_marketplace_service.py::
    test_service_non_importa_experience_engine`): un'unica fonte di verità
    su cosa significa "aperto" che entrambi possono importare senza
    introdurre una dipendenza diretta tra loro.
    """
    if durata_min < 0:
        raise ValueError(f"durata_min non può essere negativa: {durata_min}")
    if not orari_apertura or giorno_settimana is None:
        return True
    if durata_min == 0:
        return any(
            fascia.giorno_settimana == giorno_settimana
            and fascia.apertura <= ora < fascia.chiusura
            for fascia in orari_apertura
        )
    inizio = ora.hour * 60 + ora.minute
    fine = inizio + durata_min
    if fine > 24 * 60:
        return False
    return any(
        fascia.giorno_settimana == giorno_settimana
        and fascia.apertura.hour * 60 + fascia.apertura.minute <= inizio
        and fine <= fascia.chiusura.hour * 60 + fascia.chiusura.minute
        for fascia in orari_apertura
    )


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
    # Fasce settimanali RICORRENTI in cui l'esperienza è aperta (validazione
    # minima, vedi `FasciaApertura`). Lista VUOTA (default) = nessun vincolo
    # dichiarato: l'esperienza resta SEMPRE considerata aperta, per
    # costruzione — comportamento INVARIATO per ogni esperienza che non
    # dichiara orari (tutte quelle del seed oggi). Letta da
    # `rientra_in_orario`, mai altrove: un solo punto interpreta questo
    # campo, sia in composizione d'itinerario sia in prenotazione.
    orari_apertura: list[FasciaApertura] = []
    # L'esperienza ESISTE nel grafo ma oggi NON si può fare (chiusura
    # stagionale, restauro). Distinto dagli orari: `orari_apertura` dice
    # QUANDO è aperta nella settimana, `sospesa` dice che in questo periodo
    # non lo è mai. Interruttore manuale del dataset (va riportato a False
    # alla riapertura). Esiste perché il loader del grafo fa solo MERGE:
    # togliere un'esperienza dal seed lascerebbe un nodo orfano su Aura,
    # quindi la si sospende invece di toglierla. È un vincolo di PRESENZA
    # (filtro duro in `experience_engine.rules.passa_filtri_statici`), mai
    # un input dello scoring: `calcola_score` non lo legge.
    sospesa: bool = False


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
    # (+ " (esempio dimostrativo)" prima del punto finale se la bottega è fittizia)


class EventoPromosso(ContractModel):
    """Un `:Evento` PROMOSSO e ATTIVO nel Knowledge Graph (Fase 3): un
    pattern ricorrente rilevato da tracce fluttuanti, promosso da una
    decisione umana esplicita (`urban_memory.promozione_evento`), che ora
    vive come nodo permanente del grafo — livello diverso da
    `SegnaleFluttuante` (§1, `Signal.eventi_attivi`, "accade ORA e domani
    non c'è"): questo è il livello "programmato", con una cadenza propria.

    Stesso principio di minimalismo di `SegnaleFluttuante`: SOLO ciò che
    serve per comparire come tappa in coda in un itinerario, letto dal
    grafo da `services/api` (il BFF) e passato a
    `experience_engine.engine.compose_itinerary` come parametro iniettabile
    — il motore dipende SOLO dai contratti, non importa mai `graph` né
    `rag` (vedi il docstring di `compose_itinerary`), stesso principio già
    applicato a `GraphCandidate`.

    Deliberatamente ASSENTI, e perché:
    - `stato`: chi costruisce la lista da passare al motore filtra GIÀ per
      `stato='attivo'` PRIMA di costruire questo tipo — stesso principio
      per cui `Signal.eventi_attivi` arriva al motore già filtrato ai soli
      fluttuanti attivi, mai con uno stato da ricontrollare a valle. Un
      `EventoPromosso` che raggiunge il motore è, per costruzione, sempre
      attivo.
    - `promosso_da`/`promosso_il`: accountability della DECISIONE di
      promozione (chi, quando), non pertinente al CONSUMO in un itinerario.
    - nessun campo narrativo/descrizione: non esiste nulla di equivalente
      sul nodo `:Evento` reale — verificato, la `descrizione` del segnale
      fluttuante originale non sopravvive alla promozione (vedi
      `50_promozione_evento_write.cypher`).

    Finestra temporale: il contratto trasporta SOLO i FATTI grezzi
    (`ultima_occorrenza`, `cadenza_giorni`); la proiezione (ultima +
    k*cadenza, k>=1, occorrenza più vicina a `Signal.data`) e la DECISIONE
    "in finestra sì/no" le prende solo l'Experience Engine, con una funzione
    pura. "Se è vivo" resta a `stato` (già filtrato a monte): la finestra
    decide soltanto "quando". `ultima_occorrenza` è una data LOCALE della
    città, confrontabile direttamente con `Signal.data`; la conversione dal
    timestamp UTC del ledger la fa chi legge il ledger (il BFF), con un fuso
    letto da configurazione, mai scritto nel codice. Il `creato_il` della
    traccia nel ledger è il `valido_fino` UTC del segnale scaduto (calcolato
    dal server in submit_signal), non l'istante dello sweep pigro
    (`sweep_and_fetch_active`, eseguito solo quando qualcuno chiama POST
    /itinerary): la transizione a `expired` può avvenire giorni dopo, il
    timbro no. Resta l'imprecisione di `valido_fino` rispetto all'occorrenza
    reale (è la fine dichiarata della finestra del segnale, non il suo
    inizio), e le tracce depositate prima di questa correzione, timbrate allo
    sweep, restano sfasate in avanti (append-only, mai riscritte).
    """

    # id deterministico del nodo `:Evento` (urban_memory.promozione_evento.evento_id_per_pattern)
    id: str
    place_id: str  # il `:Luogo` a cui è ancorato (`SI_SVOLGE_A`)
    # Data LOCALE dell'ultima occorrenza nel ledger (non UTC): vedi docstring.
    ultima_occorrenza: date
    # gt=0: una cadenza nulla o negativa non ha senso e, usata dal motore per
    # proiettare le occorrenze successive, produrrebbe una finestra
    # degenere (divisione/ciclo infinito) invece di un errore esplicito.
    # allow_inf_nan=False: `inf` passerebbe gt=0, ma una cadenza infinita non è
    # un fatto reale (nessuna occorrenza successiva proiettabile); `nan` idem.
    cadenza_giorni: float = Field(gt=0, allow_inf_nan=False)
    # Stessa forma di `SegnaleFluttuante.temi`/`ExperienceNode.temi`: riusa
    # l'identica logica di affinità (`experience_engine.rules.affinita_temi`),
    # non un secondo criterio inventato qui. min_length=1: un pattern
    # promosso è sempre ancorato ad almeno un tema.
    temi: list[str] = Field(min_length=1)


_SLUG_TEMA = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _valida_slug_tema(valore: str) -> str:
    if not _SLUG_TEMA.fullmatch(valore):
        raise ValueError(
            f"id di Tema non valido: {valore!r} (atteso slug minuscolo, "
            "es. 'con-bambini'; non vuoto)"
        )
    return valore


class VocabolarioTemi(ContractModel):
    """Le categorie tematiche con cui il motore legge i `Tema` di una città.

    È DATO DELLA CITTÀ, non del motore: lo dichiara il dataset della città
    selezionata (`CITY_SEED`, services/graph) e attraversa i confini
    graph -> api -> experience-engine -> recommender. Il motore lo riceve e
    non lo inventa: nessun vocabolario di default cablato nel motore.

    Serve SOLO all'affinità tematica (stessi vincoli etici di
    `calcola_score`): non influenza la presenza dei partner, non contiene
    campi commerciali, non è un canale per pesare uno spazio. Nessun nome di
    città nei tipi: i valori sono id di `Tema`, i nomi dei campi sono
    categorie.

    Semantica (invariata rispetto alle costanti storiche dell'engine):
    - `contemplativi`, `arte`, `insoliti`, `verde`: GRUPPI di id di Tema;
      insiemi vuoti AMMESSI (una città può non avere temi "insoliti").
    - `bambini`: UN solo id di Tema (match per appartenenza `in temi`).

    REGOLA DI CURATELA: il vocabolario si definisce per SIGNIFICATO del tema
    rispetto alla dimensione del profilo, mai in funzione di chi offre le
    esperienze che lo evocano. Un gruppo non si costruisce a partire dai temi
    di un partner; un tema evocato solo da esperienze con partner non
    dovrebbe entrare in un gruppo senza una motivazione di significato
    documentata nel modulo dataset. Nessun prezzo modifica il vocabolario
    ("nessuno spazio è acquistabile"). Limite aperto: la regola NON è
    verificata automaticamente (docs/LIMITI.md); il codice garantisce solo
    che filtri duri e score non leggono campi commerciali.

    Immutabile (`frozen`) e hashable. Gli insiemi si serializzano in JSON
    come liste (ordine non garantito: non fare affidamento sull'ordine).
    Invariante NON verificata qui: ogni id deve essere un `Tema` del dataset;
    il contratto non conosce i temi, la validazione è del dataset in graph.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contemplativi: frozenset[str]
    arte: frozenset[str]
    insoliti: frozenset[str]
    verde: frozenset[str]
    bambini: str

    @field_validator("contemplativi", "arte", "insoliti", "verde")
    @classmethod
    def _gruppo_slug(cls, v: frozenset[str]) -> frozenset[str]:
        for tema in v:
            _valida_slug_tema(tema)
        return v

    @field_validator("bambini")
    @classmethod
    def _bambini_slug(cls, v: str) -> str:
        return _valida_slug_tema(v)


# ---------------------------------------------------------------------------
# 3. AI Experience Engine — uscita
# ---------------------------------------------------------------------------


class ExperienceCandidate(ContractModel):
    experience_id: str
    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)  # SPIEGABILITÀ OBBLIGATORIA, in italiano


class EsitoAdattamento(str, Enum):
    """Esito dell'ultimo adattamento su una tappa.

    - `NON_TOCCATA`: il segnale non ha richiesto modifiche.
    - `SOSTITUITA`: la tappa è stata sostituita da un'alternativa.
    - `MANTENUTA_SENZA_ALTERNATIVA`: il segnale la penalizzava ma non esisteva
      un'alternativa; resta in itinerario (NON accende `adattato_da_segnale`).
    - `TAGLIATA_STANCHEZZA` / `TAGLIATA_TETTO_GIORNATA` / `TAGLIATA_ORARIO`:
      la tappa è stata tolta; compare solo in `Itinerary.tappe_escluse`, mai
      tra le `stops`. `TAGLIATA_ORARIO`: all'arrivo ricalcolato il luogo è
      chiuso (l'intervallo [arrivo, arrivo + durata] non cade in una fascia
      di apertura).
    """

    NON_TOCCATA = "non_toccata"
    SOSTITUITA = "sostituita"
    MANTENUTA_SENZA_ALTERNATIVA = "mantenuta_senza_alternativa"
    TAGLIATA_STANCHEZZA = "tagliata_stanchezza"
    TAGLIATA_TETTO_GIORNATA = "tagliata_tetto_giornata"
    TAGLIATA_ORARIO = "tagliata_orario"


_ESITI_TAGLIO = frozenset(
    {
        EsitoAdattamento.TAGLIATA_STANCHEZZA,
        EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
        EsitoAdattamento.TAGLIATA_ORARIO,
    }
)


class ItineraryStop(ContractModel):
    experience_id: str
    arrivo: time
    durata_min: int = Field(ge=0)
    reason: str = Field(min_length=1)  # SPIEGABILITÀ OBBLIGATORIA, in italiano
    # None = itinerario mai adattato. Descrive SOLO l'ultimo segnale valutato.
    esito_adattamento: EsitoAdattamento | None = None

    @field_validator("esito_adattamento")
    @classmethod
    def _no_esito_di_taglio_su_tappa_presente(
        cls, v: EsitoAdattamento | None
    ) -> EsitoAdattamento | None:
        if v in _ESITI_TAGLIO:
            raise ValueError(
                "esito_adattamento di taglio non ammesso su una tappa presente: "
                "le tappe tagliate vivono in Itinerary.tappe_escluse"
            )
        return v


class TappaEsclusa(ContractModel):
    """Tappa tolta da un adattamento (stanchezza, tetto della giornata, orario)."""

    experience_id: str
    esito: EsitoAdattamento
    reason: str = Field(min_length=1)  # SPIEGABILITÀ OBBLIGATORIA, in italiano

    @field_validator("esito")
    @classmethod
    def _solo_esiti_di_taglio(cls, v: EsitoAdattamento) -> EsitoAdattamento:
        if v not in _ESITI_TAGLIO:
            raise ValueError(
                "esito di TappaEsclusa ammesso solo: tagliata_stanchezza, "
                "tagliata_tetto_giornata, tagliata_orario"
            )
        return v


class Itinerary(ContractModel):
    """Itinerario composto (e, eventualmente, adattato a un segnale).

    `adattato_da_segnale` è True se e solo se l'ultimo adattamento ha almeno
    una tappa SOSTITUITA o una tappa TAGLIATA (stanchezza, tetto o orario:
    chiusa all'arrivo ricalcolato). Una tappa
    mantenuta senza alternativa NON lo accende (l'app lo mostra come badge
    "Riscritta"): quel caso è portato da `esito_adattamento` e da una frase
    nel `reason`.
    """

    person_id: str
    stops: list[ItineraryStop]
    generated_at: datetime
    adattato_da_segnale: bool = False
    # Budget dichiarato alla composizione (stesso significato di
    # EmotionalProfile.tempo_disponibile_min). Lo scrive solo la composizione;
    # l'adattamento lo ricopia. None = itinerario senza budget.
    tempo_disponibile_min: int | None = Field(default=None, gt=0)
    # Budget dopo il tetto della giornata:
    # min(dichiarato, minuti da signal.ora alle 24:00).
    tempo_effettivo_min: int | None = Field(default=None, gt=0)
    # Tappe tolte da un adattamento; si accumulano tra adattamenti successivi.
    tappe_escluse: list[TappaEsclusa] = Field(default_factory=list)

    @model_validator(mode="after")
    def _budget_coerente(self) -> Itinerary:
        dichiarato = self.tempo_disponibile_min
        effettivo = self.tempo_effettivo_min
        if (dichiarato is None) != (effettivo is None):
            raise ValueError(
                "tempo_disponibile_min e tempo_effettivo_min devono essere "
                "entrambi None o entrambi valorizzati"
            )
        if dichiarato is not None and effettivo is not None and effettivo > dichiarato:
            raise ValueError("tempo_effettivo_min non può superare tempo_disponibile_min")
        return self


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


class MemoryLinkState(str, Enum):
    """Esito dell'aggancio automatico al Knowledge Graph, innescato quando
    un contributo diventa `curato=True` (invariante "curato tira aggancio",
    `docs/ENGINE_INVARIANTS.md` §11-B). NON è una macchina a stati completa
    (`docs/STATE_MACHINE.md` resta design, non codice): solo il minimo per
    distinguere un aggancio riuscito da uno da riprovare.

    - `AGGANCIATO`: `(:Memoria)-[:RIGUARDA]->(...)` scritto nel grafo.
    - `AGGANCIO_FALLITO`: l'aggancio non è riuscito (in questo repository,
      per costruzione, SEMPRE una causa infrastrutturale — Aura
      irraggiungibile: l'invariante A, append-only sui target, esclude un
      target sparito). Stato di ATTESA RECUPERABILE: un retry successivo
      può portarlo ad `AGGANCIATO`, mai un vicolo cieco.
    """

    AGGANCIATO = "agganciato"
    AGGANCIO_FALLITO = "aggancio_fallito"


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
    # `None` finché l'aggancio al grafo non è mai stato tentato (mai curato,
    # o curato prima che questa automazione esistesse). Impostato SOLO da
    # `urban_memory` dopo un tentativo reale di `link_to_graph` — mai
    # dall'esterno: submit/curatela non lo toccano mai direttamente.
    stato_aggancio: MemoryLinkState | None = None


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
    # Opzionale: oggi non esiste una fonte dati reale (nessuna recensione/survey
    # in prodotto). Finché non esiste, il valore è esplicitamente None — mai
    # stimato o fabbricato solo per riempire il contratto.
    soddisfazione: float | None = Field(default=None, ge=0, le=5)
    tasso_ritorno: float = Field(ge=0, le=1)
    # tasso, non conteggio: coppie consecutive NON collegate nel grafo allo
    # snapshot di INIZIO periodo, sul totale delle coppie non collegate
    # disponibili in quello stesso snapshot. Un conteggio grezzo scenderebbe
    # da solo man mano che il grafo cresce (più relazioni = meno coppie
    # "non collegate"), confondendo la crescita del grafo con un calo
    # dell'esplorazione spontanea.
    nuovi_percorsi: float = Field(ge=0, le=1)  # itinerari emergenti e inattesi
    attivazione_locale: float = Field(ge=0, le=1)  # quanto il territorio minore viene raggiunto
    distribuzione_flussi: float = Field(ge=0, le=1)  # 1 = distribuiti, 0 = overtourism
    contributi_memoria: int = Field(ge=0)  # crescita della Urban Memory


# ---------------------------------------------------------------------------
# 7bis. Urban Intelligence Index — risposte dashboard (BFF)
# ---------------------------------------------------------------------------


class DashboardIndexResponse(ContractModel):
    """Wrapper del BFF per `GET /dashboard/index`.

    `intelligence_index.calcola_index` solleva `DatiInsufficientiError` se un
    qualunque indicatore dell'intero periodo è sotto la soglia di
    aggregazione k=10 (raro in produzione — una città intera, un mese
    intero — ma possibile, es. un periodo storico con pochi dati di test).
    Il BFF non può propagare quell'eccezione grezza né restituire un
    `UrbanIntelligenceIndex` fabbricato: questo wrapper rende esplicito lo
    stato "dato insufficiente" come risposta di prima classe.

    Vincolo di coerenza (applicato per costruzione, non solo per
    disciplina di chi popola il modello — vedi `model_validator` sotto):
    `disponibile=True` implica `index is not None` e
    `motivo_indisponibilita is None`; `disponibile=False` implica il
    contrario (`index is None`, `motivo_indisponibilita` una stringa non
    vuota, leggibile in italiano). Nessuno stato intermedio.
    """

    periodo: str
    disponibile: bool
    index: UrbanIntelligenceIndex | None = None  # popolato SOLO se disponibile=True
    # popolato SOLO se disponibile=False, leggibile in italiano
    motivo_indisponibilita: str | None = None

    @model_validator(mode="after")
    def _coerenza_disponibilita(self) -> DashboardIndexResponse:
        if self.disponibile:
            if self.index is None:
                raise ValueError(
                    "DashboardIndexResponse: disponibile=True richiede `index` valorizzato"
                )
            if self.motivo_indisponibilita is not None:
                raise ValueError(
                    "DashboardIndexResponse: disponibile=True non ammette "
                    "`motivo_indisponibilita`"
                )
        else:
            if self.index is not None:
                raise ValueError("DashboardIndexResponse: disponibile=False richiede `index=None`")
            if not self.motivo_indisponibilita:
                raise ValueError(
                    "DashboardIndexResponse: disponibile=False richiede "
                    "`motivo_indisponibilita` non vuoto"
                )
        return self


class FlowCell(ContractModel):
    """Una riga di heatmap per un luogo (`GET /dashboard/flows`).

    Gated INDIPENDENTEMENTE dalle altre celle sulla soglia k=10 dei
    `person_id` distinti coinvolti in QUESTA cella specifica (stesso
    principio del gate su `UrbanIntelligenceIndex`, ma a grana più fine —
    per cella, non per l'intero periodo — usando
    `intelligence_index.soglia.valore_se_soglia`, che ritorna `None` invece
    di sollevare: pensato esattamente per questo drill-down).

    Espone SOLO un booleano `disponibile` e il conteggio di tappe (o `None`
    se la cella è soppressa): MAI un conteggio di popolazione (es.
    `n_persone`), nemmeno opzionale. Un conteggio di popolazione grezzo —
    "3 persone in questa cella" — sarebbe già di per sé la violazione di
    re-identificazione che il gate deve prevenire, indipendentemente dal
    fatto che il VALORE dell'indicatore (`conteggio_tappe`) venga poi
    nascosto. Non esiste un campo che possa esporlo: è una garanzia
    strutturale del contratto, non una disciplina di chi lo popola.

    Stesso vincolo di coerenza di `DashboardIndexResponse`:
    `disponibile=True` implica `conteggio_tappe is not None`;
    `disponibile=False` implica `conteggio_tappe is None`.
    """

    place_id: str
    disponibile: bool
    conteggio_tappe: int | None = Field(default=None, ge=0)  # None se soppressa (sotto k=10)

    @model_validator(mode="after")
    def _coerenza_disponibilita(self) -> FlowCell:
        if self.disponibile and self.conteggio_tappe is None:
            raise ValueError("FlowCell: disponibile=True richiede `conteggio_tappe` valorizzato")
        if not self.disponibile and self.conteggio_tappe is not None:
            raise ValueError("FlowCell: disponibile=False richiede `conteggio_tappe=None`")
        return self


class DashboardFlowsResponse(ContractModel):
    """Risposta di `GET /dashboard/flows`.

    Design deliberato: SEMPRE una riga per luogo (`celle`), mai una
    combinatoria esplosiva luogo×giorno×ora in un solo payload — con 15
    luoghi × ~30 giorni × 24 ore sarebbero migliaia di righe per una singola
    chiamata. I filtri opzionali `giorno`/`ora` (applicati lato query,
    riportati qui per trasparenza sulla richiesta effettivamente servita)
    restringono la STESSA lista di celle a un giorno/una fascia oraria
    specifici: è così che l'API espone la granularità luogo×giorno×ora,
    un filtro alla volta, non un cubo precalcolato. Ogni cella è gated
    indipendentemente dalle altre (vedi `FlowCell`).
    """

    periodo: str
    giorno: date | None = None  # filtro applicato alla richiesta, se presente
    ora: int | None = Field(default=None, ge=0, le=23)  # fascia oraria applicata, se presente
    # una riga per luogo disponibile nel grafo (place_id da graph.topology/graph.metrics)
    celle: list[FlowCell]


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
    """Input di POST /itinerary/adapt.

    `profile` (opzionale, retrocompatibile): se presente, il profilo del visitatore
    guida l'ordinamento delle alternative e l'accessibilita'
    (`accessibilita_richiesta`). Se assente, profilo neutro e regola prudente per
    tappa (una tappa accessibile si sostituisce solo con una accessibile):
    comportamento invariato.
    """

    itinerary: Itinerary
    signal: Signal
    profile: EmotionalProfile | None = None

