"""Persistenza del Marketplace (`Booking`, `CommissionRecord`).

Due percorsi per la stessa interfaccia (`BookingRepository`), stesso pattern
di `urban_memory.repository.MemoryRepository`:

- `InMemoryBookingRepository` — dizionari in-process. È il percorso usato
  nei test e finché `DATABASE_URL` non è configurato.
- `PostgresBookingRepository` — Neon (`sslmode=require`) in cloud o Postgres
  locale (Docker sul PC fisso): stesso codice nei due profili, cambia solo
  il DSN letto da `DATABASE_URL`. Persiste DAVVERO. Lo schema è versionato e
  idempotente in `services/marketplace/sql/00_marketplace_schema.sql` (vedi
  `marketplace.migrate`), con `CHECK` a difesa in profondità oltre ai
  controlli già fatti da `marketplace.service`.

Nessuna delle due implementazioni applica i vincoli di dominio (stato
iniziale RICHIESTA, commissione calcolata solo dopo la conferma): quelli
vivono in `marketplace.service`, in un solo punto verificabile. Il
repository sa solo leggere e scrivere ciò che il servizio gli passa già
costruito — `commission_record.booking_id PRIMARY KEY` in
`00_marketplace_schema.sql` è l'unica eccezione, difesa in profondità contro
una doppia registrazione, non la garanzia primaria.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import psycopg
from contracts import Booking, BookingStatus, CommissionRecord
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "BookingRepository",
    "InMemoryBookingRepository",
    "PostgresBookingRepository",
    "MarketplaceStorageError",
]

_BOOKING_COLUMNS = (
    "id",
    "person_id",
    "experience_id",
    "quando",
    "stato",
    "prezzo_eur",
    "creato_il",
)
_BOOKING_COLUMNS_SQL = ", ".join(_BOOKING_COLUMNS)

_COMMISSION_COLUMNS = ("booking_id", "importo_eur", "percentuale", "registrata_il")
_COMMISSION_COLUMNS_SQL = ", ".join(_COMMISSION_COLUMNS)


class BookingRepository(Protocol):
    """Interfaccia comune di persistenza per prenotazioni e commissioni."""

    def create(self, booking: Booking) -> Booking:
        """Persiste una `Booking` NUOVA (stato tipicamente RICHIESTA, già
        deciso da `marketplace.service.request_booking`) e la restituisce."""
        ...

    def get(self, booking_id: str) -> Booking | None:
        """La prenotazione con id `booking_id`, così com'è persistita.
        `None` se non esiste: è un lookup, non un comando."""
        ...

    def update_status(self, booking_id: str, stato: BookingStatus) -> Booking:
        """Aggiorna `stato` e restituisce la `Booking` aggiornata. Solleva
        `KeyError` se `booking_id` non esiste. Non applica NESSUNA regola di
        transizione (es. "non si conferma un'annullata"): quella vive in
        `marketplace.service.confirm_booking`, l'unico chiamante previsto."""
        ...

    def record_commission(self, commission: CommissionRecord) -> CommissionRecord:
        """Persiste una `CommissionRecord` e la restituisce. Chiamata SOLO
        da `marketplace.service.confirm_booking`, dopo che la prenotazione è
        già stata portata a CONFERMATA — mai prima."""
        ...

    def get_commission(self, booking_id: str) -> CommissionRecord | None:
        """La commissione registrata per `booking_id`, se esiste. `None` se
        la prenotazione non è (ancora) stata confermata: usato da
        `marketplace.service.confirm_booking` per rendere la conferma
        idempotente (mai una doppia commissione sulla stessa prenotazione)."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryBookingRepository:
    """Implementazione in-process (dizionari) di `BookingRepository`.

    Non persiste tra processi: è il percorso usato nei test e finché
    `DATABASE_URL` non è configurato (vedi `PostgresBookingRepository`).
    """

    def __init__(self) -> None:
        self._bookings: dict[str, Booking] = {}
        self._commissions: dict[str, CommissionRecord] = {}

    def create(self, booking: Booking) -> Booking:
        self._bookings[booking.id] = booking
        return booking

    def get(self, booking_id: str) -> Booking | None:
        return self._bookings.get(booking_id)

    def update_status(self, booking_id: str, stato: BookingStatus) -> Booking:
        try:
            corrente = self._bookings[booking_id]
        except KeyError:
            raise KeyError(f"nessuna prenotazione con id={booking_id!r}") from None
        aggiornata = corrente.model_copy(update={"stato": stato})
        self._bookings[booking_id] = aggiornata
        return aggiornata

    def record_commission(self, commission: CommissionRecord) -> CommissionRecord:
        self._commissions[commission.booking_id] = commission
        return commission

    def get_commission(self, booking_id: str) -> CommissionRecord | None:
        return self._commissions.get(booking_id)


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class MarketplaceStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB,
    query fallita) — NON un'eccezione di dominio: NON è una sottoclasse di
    `marketplace.service.MarketplaceError`.

    Stessa distinzione di `urban_memory.repository.MemoryStorageError`: un
    `MarketplaceError` (o sottoclasse) significa "questa richiesta viola una
    regola non negoziabile" (422/404/409 lato BFF); `MarketplaceStorageError`
    significa "il database non ha potuto completare l'operazione" (rete,
    credenziali, un `CHECK` scattato per un bug applicativo a monte) — il
    BFF la distingue e risponde con un 503, mai un 500 opaco.
    """


class PostgresBookingRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso, o un cluster nativo). Stesso
    codice nei due profili: cambia solo il DSN. Nessun host hardcoded,
    nessun `if local/cloud`.

    Lo schema atteso (`booking`, `commission_record`, colonne speculari a
    `Booking`/`CommissionRecord`, `docs/DATA_CONTRACTS.md` §5) è versionato e
    idempotente in `services/marketplace/sql/00_marketplace_schema.sql`: va
    applicato una volta con `marketplace.migrate.migrate(dsn)` (o `python -m
    marketplace.migrate`) prima di usare questa classe. Questa classe non
    applica la migrazione da sé (nessun DDL implicito a ogni richiesta).

    Una connessione (e una transazione) per operazione: nessuno stato di
    connessione persistente tenuto in `self` — coerente con "il dato
    sopravvive al riavvio del processo che lo scrive". Ogni errore psycopg è
    mappato in `MarketplaceStorageError` (mai lasciato propagare come
    eccezione psycopg grezza).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresBookingRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo — equivalente a `urban_memory.repository.
        PostgresMemoryRepository.from_env()` per il Marketplace."""
        return cls(database_url_from_env(dotenv_path))

    # -- booking -----------------------------------------------------------

    def create(self, booking: Booking) -> Booking:
        query = (
            f"INSERT INTO booking ({_BOOKING_COLUMNS_SQL}) "
            "VALUES (%(id)s, %(person_id)s, %(experience_id)s, %(quando)s, "
            "%(stato)s, %(prezzo_eur)s, %(creato_il)s) "
            f"RETURNING {_BOOKING_COLUMNS_SQL}"
        )
        params = _booking_to_params(booking)
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MarketplaceStorageError(
                f"impossibile persistere la prenotazione id={booking.id!r}: {exc}"
            ) from exc
        assert riga is not None  # RETURNING su un INSERT riuscito produce sempre una riga
        return _booking_from_row(riga)

    def get(self, booking_id: str) -> Booking | None:
        query = f"SELECT {_BOOKING_COLUMNS_SQL} FROM booking WHERE id = %(id)s"
        righe = self._select(query, {"id": booking_id})
        if not righe:
            return None
        return _booking_from_row(righe[0])

    def update_status(self, booking_id: str, stato: BookingStatus) -> Booking:
        query = (
            "UPDATE booking SET stato = %(stato)s "
            f"WHERE id = %(id)s RETURNING {_BOOKING_COLUMNS_SQL}"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"id": booking_id, "stato": stato.value})
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MarketplaceStorageError(
                f"impossibile aggiornare lo stato della prenotazione id={booking_id!r}: {exc}"
            ) from exc
        if riga is None:
            raise KeyError(f"nessuna prenotazione con id={booking_id!r}")
        return _booking_from_row(riga)

    # -- commission ----------------------------------------------------------

    def record_commission(self, commission: CommissionRecord) -> CommissionRecord:
        query = (
            f"INSERT INTO commission_record ({_COMMISSION_COLUMNS_SQL}) "
            "VALUES (%(booking_id)s, %(importo_eur)s, %(percentuale)s, %(registrata_il)s) "
            f"RETURNING {_COMMISSION_COLUMNS_SQL}"
        )
        params = _commission_to_params(commission)
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MarketplaceStorageError(
                f"impossibile registrare la commissione per "
                f"booking_id={commission.booking_id!r}: {exc}"
            ) from exc
        assert riga is not None
        return _commission_from_row(riga)

    def get_commission(self, booking_id: str) -> CommissionRecord | None:
        query = (
            f"SELECT {_COMMISSION_COLUMNS_SQL} FROM commission_record "
            "WHERE booking_id = %(booking_id)s"
        )
        righe = self._select(query, {"booking_id": booking_id})
        if not righe:
            return None
        return _commission_from_row(righe[0])

    # -- interno ------------------------------------------------------------

    def _select(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    return list(cur.fetchall())
        except psycopg.Error as exc:
            raise MarketplaceStorageError(f"lettura fallita sul Marketplace: {exc}") from exc


def _booking_to_params(booking: Booking) -> dict[str, Any]:
    return {
        "id": booking.id,
        "person_id": booking.person_id,
        "experience_id": booking.experience_id,
        "quando": booking.quando,
        "stato": booking.stato.value,
        "prezzo_eur": booking.prezzo_eur,
        "creato_il": booking.creato_il,
    }


def _booking_from_row(riga: dict[str, Any]) -> Booking:
    return Booking(
        id=riga["id"],
        person_id=riga["person_id"],
        experience_id=riga["experience_id"],
        quando=riga["quando"],
        stato=riga["stato"],
        prezzo_eur=riga["prezzo_eur"],
        creato_il=riga["creato_il"],
    )


def _commission_to_params(commission: CommissionRecord) -> dict[str, Any]:
    return {
        "booking_id": commission.booking_id,
        "importo_eur": commission.importo_eur,
        "percentuale": commission.percentuale,
        "registrata_il": commission.registrata_il,
    }


def _commission_from_row(riga: dict[str, Any]) -> CommissionRecord:
    return CommissionRecord(
        booking_id=riga["booking_id"],
        importo_eur=riga["importo_eur"],
        percentuale=riga["percentuale"],
        registrata_il=riga["registrata_il"],
    )
