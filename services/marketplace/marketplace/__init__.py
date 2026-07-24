"""Lucca Soul Lab — Engine: Marketplace (`services/marketplace`), Wave 3a.

Prenotazioni (`Booking`) su esperienze prenotabili e la commissione che ne
deriva (`CommissionRecord`) — un dato CONTABILE, registrato SOLO dopo che la
prenotazione è stata confermata. Import name del pacchetto: `marketplace`
(nome distribuzione: `lucca-marketplace`).

Vincolo non negoziabile (prescrizione ethics-guardian,
`docs/DATA_CONTRACTS.md` §5), applicato in un solo punto verificabile
(`marketplace.service.confirm_booking`):

- una `Booking` nasce SEMPRE in stato `RICHIESTA` (`request_booking`);
- `CommissionRecord` è calcolato e persistito SOLO da `confirm_booking`, e
  SOLO dopo che la transizione a `CONFERMATA` è già stata scritta — mai
  prima, mai da un'altra funzione;
- il modello di ricavo dei partner resta un abbonamento di presenza (sì/no,
  `Partner.abbonamento_attivo`): questo pacchetto non introduce alcuna asta
  sulla visibilità, nessun campo "peso"/"boost"/"priorita_pagata" in
  nessun modello o funzione;
- questo pacchetto NON importa `services/experience-engine` (né viceversa):
  lo scoring del motore non ha alcun percorso di import verso
  `CommissionRecord` o `Partner` — vede solo il booleano denormalizzato
  `ExperienceNode.partner_abbonamento_attivo`.

Uso tipico::

    from marketplace import (
        InMemoryBookingRepository,
        request_booking, confirm_booking,
        ExperienceNotBookableError, BookingNotFoundError, InvalidBookingStateError,
    )

    repo = InMemoryBookingRepository()
    prenotazione = request_booking(
        repo, booking_request, prezzo_eur=15.0, prenotabile=True,
    )                                            # stato RICHIESTA
    confermata = confirm_booking(repo, prenotazione.id)  # stato CONFERMATA
                                                          # + CommissionRecord

Persistenza reale (Neon in cloud o Postgres locale — mai `if local/cloud`,
solo `DATABASE_URL`). Una tantum, applica la migrazione idempotente
(`python -m marketplace.migrate`), poi::

    from marketplace import PostgresBookingRepository

    repo = PostgresBookingRepository.from_env()  # legge DATABASE_URL
    request_booking(repo, booking_request, prezzo_eur=15.0, prenotabile=True)

`python -m marketplace.verify` dimostra end-to-end (su Postgres reale) che
la prenotazione persiste, che nessuna commissione esiste prima della
conferma, e che la commissione registrata dopo la conferma è aritmeticamente
corretta (`prezzo_eur * percentuale`).
"""

from __future__ import annotations

from .migrate import SCHEMA_PATH, migrate
from .repository import (
    BookingRepository,
    InMemoryBookingRepository,
    MarketplaceStorageError,
    PostgresBookingRepository,
)
from .service import (
    BookingNotFoundError,
    ExperienceNotAvailableError,
    ExperienceNotBookableError,
    InvalidBookingStateError,
    MarketplaceError,
    confirm_booking,
    request_booking,
)

__all__ = [
    "BookingRepository",
    "InMemoryBookingRepository",
    "PostgresBookingRepository",
    "MarketplaceStorageError",
    "MarketplaceError",
    "ExperienceNotBookableError",
    "ExperienceNotAvailableError",
    "BookingNotFoundError",
    "InvalidBookingStateError",
    "request_booking",
    "confirm_booking",
    "migrate",
    "SCHEMA_PATH",
]
