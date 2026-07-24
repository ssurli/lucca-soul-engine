"""Marketplace — logica di dominio: richiesta, conferma, commissione.

Qui vivono i vincoli non negoziabili del Marketplace (Wave 3a,
`docs/DATA_CONTRACTS.md` §5), applicati in UN SOLO PUNTO verificabile —
lo stesso principio di `urban_memory.service` e dell'AI Experience Engine
("un vincolo applicato in un solo punto è verificabile, distribuito no"):

- una `Booking` nasce SEMPRE in stato `RICHIESTA` (`request_booking`);
- `prezzo_eur` è uno SNAPSHOT: congelato al momento della richiesta, non
  ricalcolato dal listino corrente (chi chiama passa il prezzo attuale
  dell'`ExperienceNode`, `request_booking` lo scrive una volta sola nella
  `Booking` e non lo tocca più);
- una prenotazione su un'esperienza `prenotabile=False` è rifiutata SUBITO,
  prima di persistere nulla (`ExperienceNotBookableError`);
- **`CommissionRecord` è calcolato SOLO da `confirm_booking`, e SOLO DOPO
  che la transizione a `CONFERMATA` è già stata persistita** (vedi il corpo
  della funzione: la sequenza `repo.update_status(...)` precede SEMPRE il
  calcolo di `importo_eur`). Nessun'altra funzione di questo modulo calcola
  una commissione. Non esiste un percorso per calcolarla PRIMA della
  conferma: `request_booking` non la tocca, e non c'è nessuna funzione
  "calcola commissione preventiva" in questo file, di proposito — sarebbe
  esattamente il varco che trasformerebbe un dato contabile in un segnale
  di scoring.
- la percentuale usata è quella di default del contratto
  (`CommissionRecord.percentuale`, 0.15), letta dal modello — mai duplicata
  come costante scollegata, per non poter mai divergere dal contratto.

Questo modulo NON importa `services/experience-engine` (né viceversa: quel
servizio non importa `marketplace`): lo scoring dell'Experience Engine non
ha alcun percorso di import verso `CommissionRecord` o `Partner.
abbonamento_attivo` — vede solo il booleano denormalizzato
`ExperienceNode.partner_abbonamento_attivo` (docs/DATA_CONTRACTS.md §2, §5).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from contracts import (
    Booking,
    BookingRequest,
    BookingStatus,
    CommissionRecord,
    FasciaApertura,
    rientra_in_orario,
)

from .repository import BookingRepository

__all__ = [
    "MarketplaceError",
    "ExperienceNotBookableError",
    "ExperienceNotAvailableError",
    "BookingNotFoundError",
    "InvalidBookingStateError",
    "request_booking",
    "confirm_booking",
]

#: Letta dal contratto (single source of truth), mai duplicata come
#: costante scollegata: se `contract-keeper` cambia il default di
#: `CommissionRecord.percentuale`, questo modulo lo segue senza modifiche.
_PERCENTUALE_COMMISSIONE_DEFAULT: float = CommissionRecord.model_fields["percentuale"].default


class MarketplaceError(Exception):
    """Base per le eccezioni di dominio del Marketplace."""


class ExperienceNotBookableError(MarketplaceError):
    """L'esperienza richiesta ha `prenotabile=False`: non prenotabile, a
    prescindere dal partner (`prenotabile` e presenza commerciale del
    partner sono concetti distinti, docs/DATA_CONTRACTS.md §2)."""


class ExperienceNotAvailableError(MarketplaceError):
    """`BookingRequest.quando` cade fuori dalle fasce settimanali dichiarate
    in `ExperienceNode.orari_apertura` (validazione MINIMA, Wave 3a+: fasce
    ricorrenti soltanto — niente capienza, conflitti di slot o eccezioni
    calendariali, vedi `docs/LIMITI.md`). Distinta da
    `ExperienceNotBookableError`: quella dice "questa esperienza non si
    prenota mai", questa dice "non in QUESTO momento". Un'esperienza che non
    dichiara orari (`orari_apertura` vuota, il default) non solleva MAI
    questo errore — nessun vincolo fabbricato per un'esperienza che non ne
    ha dichiarato uno."""


class BookingNotFoundError(MarketplaceError):
    """`booking_id` non esiste nel repository. Sottoclasse di
    `MarketplaceError` (non un `KeyError` nudo) così il BFF la mappa a un
    404 esplicito senza ambiguità con un `KeyError` generico di libreria."""


class InvalidBookingStateError(MarketplaceError):
    """La transizione di stato richiesta non è ammessa (es. confermare una
    prenotazione già `ANNULLATA`)."""


def request_booking(
    repo: BookingRepository,
    request: BookingRequest,
    *,
    prezzo_eur: float,
    prenotabile: bool,
    orari_apertura: list[FasciaApertura] | None = None,
    id_generator: Callable[[], str] | None = None,
) -> Booking:
    """Crea una `Booking` in stato `RICHIESTA` e la persiste.

    `prezzo_eur` e `prenotabile` arrivano da chi chiama (tipicamente il BFF,
    che li legge dall'`ExperienceNode` corrente via la `CandidateSource` del
    grafo — questo modulo non conosce il grafo, non lo importa): il prezzo
    diventa lo SNAPSHOT congelato nella `Booking` e non verrà più
    ricalcolato, anche se il listino cambia dopo.

    Rifiuta SUBITO (`ExperienceNotBookableError`, nessuna scrittura) se
    `prenotabile` è `False`: un'esperienza gratuita e senza partner può
    essere prenotabile (posti limitati), una con partner può non esserlo —
    `prenotabile` non si deduce mai da `partner_id`/l'abbonamento del
    partner (docs/DATA_CONTRACTS.md §2), lo decide solo questo flag,
    verificato in un solo punto.

    `orari_apertura` (validazione MINIMA, Wave 3a+): stesso pattern di
    `prezzo_eur`/`prenotabile`, arriva da chi chiama, letto
    dall'`ExperienceNode` corrente. Rifiuta SUBITO (`ExperienceNotAvailableError`,
    nessuna scrittura) se `request.quando` cade fuori da TUTTE le fasce
    dichiarate — usa `contracts.rientra_in_orario`, la STESSA funzione
    riusata dal quinto filtro duro di `experience_engine.rules.
    passa_filtri_duri` (stessa informazione, un solo modello, due usi).
    `None`/lista vuota (default) = nessun orario dichiarato: non solleva mai
    questo errore per un'esperienza che non ha dichiarato vincoli — nessuna
    esclusione fabbricata per un dato assente. Capienza, conflitti di slot,
    eccezioni calendariali e festività restano DELIBERATAMENTE fuori da
    questa validazione (`docs/LIMITI.md`): si disegnano quando una bottega
    reale ne dichiara il bisogno, non prima.

    `id_generator` — di default un id `booking-<uuid4>`; sovrascrivibile per
    id deterministici (usato da `marketplace.verify` per un round-trip
    riproducibile).
    """
    if not prenotabile:
        raise ExperienceNotBookableError(
            f"esperienza id={request.experience_id!r} non è prenotabile "
            "(ExperienceNode.prenotabile=False): richiesta rifiutata, "
            "nessuna prenotazione creata."
        )

    if not rientra_in_orario(
        orari_apertura or [], request.quando.weekday(), request.quando.time()
    ):
        raise ExperienceNotAvailableError(
            f"esperienza id={request.experience_id!r} richiesta per "
            f"{request.quando.isoformat()!r}, fuori dalle fasce di apertura "
            "dichiarate (ExperienceNode.orari_apertura): richiesta rifiutata, "
            "nessuna prenotazione creata."
        )

    genera_id = id_generator or (lambda: f"booking-{uuid4()}")
    booking = Booking(
        id=genera_id(),
        person_id=request.person_id,
        experience_id=request.experience_id,
        quando=request.quando,
        stato=BookingStatus.RICHIESTA,
        prezzo_eur=prezzo_eur,
        creato_il=datetime.now(UTC),
    )
    return repo.create(booking)


def confirm_booking(repo: BookingRepository, booking_id: str) -> Booking:
    """Conferma una prenotazione e, SOLO DOPO, registra la sua commissione.

    Ordine ESATTO (non negoziabile, prescrizione ethics-guardian):
    1. legge la `Booking` corrente (`repo.get`) — `BookingNotFoundError` se
       non esiste;
    2. rifiuta (`InvalidBookingStateError`) se è `ANNULLATA` — non si
       conferma una prenotazione annullata;
    3. se è già `CONFERMATA`, ritorna SENZA ricalcolare/ri-registrare nulla:
       idempotente, mai una seconda `CommissionRecord` per la stessa
       `Booking` (difesa applicativa, oltre al `PRIMARY KEY` su
       `commission_record.booking_id` a livello DB);
    4. SOLO altrimenti (era `RICHIESTA`): persiste la transizione a
       `CONFERMATA` (`repo.update_status`) — e SOLO DOPO che questa riga è
       tornata dal repository, calcola `importo_eur = prezzo_eur *
       percentuale` e lo registra (`repo.record_commission`).

    Il calcolo della commissione non precede MAI, nel codice, la chiamata a
    `repo.update_status`: leggilo dall'ordine delle istruzioni qui sotto,
    non da un commento a parte.
    """
    booking = repo.get(booking_id)
    if booking is None:
        raise BookingNotFoundError(f"nessuna prenotazione con id={booking_id!r}")

    if booking.stato == BookingStatus.ANNULLATA:
        raise InvalidBookingStateError(
            f"prenotazione id={booking_id!r} è annullata: non può essere confermata"
        )

    if booking.stato == BookingStatus.CONFERMATA:
        return booking  # idempotente: nessuna doppia commissione

    confermata = repo.update_status(booking_id, BookingStatus.CONFERMATA)

    importo_eur = round(confermata.prezzo_eur * _PERCENTUALE_COMMISSIONE_DEFAULT, 2)
    commissione = CommissionRecord(
        booking_id=confermata.id,
        importo_eur=importo_eur,
        percentuale=_PERCENTUALE_COMMISSIONE_DEFAULT,
        registrata_il=datetime.now(UTC),
    )
    repo.record_commission(commissione)

    return confermata
