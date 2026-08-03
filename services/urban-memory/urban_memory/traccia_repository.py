"""Il ledger delle tracce (Fase 3, `docs/PROMOZIONE_TRACCIA.md` §1) — ciò che
RESTA quando un segnale fluttuante approvato scade.

Append-only, place-anchored (mai occurrence-anchored): una riga per
transizione `attivo -> expired`, mai aggiornata né cancellata. Anagrafica
MINIMA — `place_id`, `temi[]`, `creato_il` — NIENTE `contributor_id`/PII/
testo libero, stessa disciplina già rispettata da `MemoryContribution` per i
campi sensibili (CLAUDE.md, docs/DATA_CONTRACTS.md §4).

`Traccia` NON è un contratto condiviso (`packages/contracts`): a differenza
di `MemoryContribution`/`SegnaleFluttuante`, nessun altro servizio la
consuma ancora — il bagliore derivato (`docs/PROMOZIONE_TRACCIA.md` §2b,
fuori scope per questa wave) sarebbe il primo consumatore futuro, e a quel
punto la domanda "va promossa a `packages/contracts`?" tornerà a
`contract-keeper`. Fino ad allora vive solo qui, interna a
`services/urban-memory`.

Due percorsi per la stessa interfaccia (`TracciaRepository`), stesso pattern
di `urban_memory.repository.MemoryRepository` e
`urban_memory.segnale_repository.SegnaleFluttuanteRepository`:

- `InMemoryTracciaRepository` — dizionario in-process. Percorso di test e
  finché `DATABASE_URL` non è configurato.
- `PostgresTracciaRepository` — Neon o Postgres locale, stesso schema
  versionato in `services/urban-memory/sql/01_fluttuante_schema.sql`
  (tabella `traccia_luogo`).

**IDEMPOTENZA — difesa in profondità, non la guardia primaria.** La guardia
primaria vive in `urban_memory.segnale_repository.
SegnaleFluttuanteRepository.sweep_scaduti` (la transizione atomica
attivo->expired: un segnale già `expired` non viene mai restituito una
seconda volta, quindi `deposita` non viene mai chiamato due volte per lo
stesso segnale nel flusso normale — vedi `urban_memory.canale_fluttuante.
sweep_and_fetch_active`). ENTRAMBE le implementazioni qui sotto ribadiscono
comunque il vincolo — `segnale_id` UNIQUE, sia a livello DB (Postgres) sia a
livello applicativo (in-memory) — così un bug futuro che chiamasse
`deposita` due volte per lo stesso `segnale_id` fallisce rumorosamente
(`TracciaStorageError`) invece di duplicare silenziosamente il ledger.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "Traccia",
    "TracciaRepository",
    "InMemoryTracciaRepository",
    "PostgresTracciaRepository",
    "TracciaStorageError",
]


@dataclass(frozen=True)
class Traccia:
    """Una riga del ledger — immutabile, come si conviene a un append-only.
    `id` è una chiave SURROGATA (generata dall'applicazione, `uuid4`), non
    una chiave naturale: due tracce identiche in place_id/temi/istante
    restano due passaggi distinti (stesso principio di `behavior_event`,
    docs/PROMOZIONE_TRACCIA.md §1)."""

    id: str
    segnale_id: str
    place_id: str
    temi: tuple[str, ...]
    creato_il: datetime


class TracciaRepository(Protocol):
    """Interfaccia comune di persistenza per il ledger delle tracce."""

    def deposita(
        self, *, segnale_id: str, place_id: str, temi: list[str], creato_il: datetime
    ) -> Traccia:
        """Deposita UNA riga di traccia (append-only: nessun aggiornamento,
        nessuna cancellazione). Solleva `TracciaStorageError` se una traccia
        per `segnale_id` esiste già — difesa in profondità
        dell'idempotenza (la guardia primaria è a monte, in
        `SegnaleFluttuanteRepository.sweep_scaduti`)."""
        ...

    def list_for_place(self, place_id: str) -> list[Traccia]:
        """Tutte le tracce depositate per `place_id`, in ordine di deposito
        — la vista "diario del luogo" (docs/PROMOZIONE_TRACCIA.md §1), letta
        da un consumatore futuro (bagliore, dormienza di un pattern
        promosso). Nessuna logica di aggregazione qui: solo lettura grezza
        del ledger."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryTracciaRepository:
    """Implementazione in-process (dizionario) di `TracciaRepository`. Non
    persiste tra processi."""

    def __init__(self) -> None:
        self._store: dict[str, Traccia] = {}

    def deposita(
        self, *, segnale_id: str, place_id: str, temi: list[str], creato_il: datetime
    ) -> Traccia:
        if any(t.segnale_id == segnale_id for t in self._store.values()):
            raise TracciaStorageError(
                f"traccia già depositata per segnale_id={segnale_id!r}: "
                "violazione dell'idempotenza (deposita chiamato due volte "
                "sullo stesso segnale)"
            )
        traccia = Traccia(
            id=f"traccia-{uuid.uuid4().hex}",
            segnale_id=segnale_id,
            place_id=place_id,
            temi=tuple(temi),
            creato_il=creato_il,
        )
        self._store[traccia.id] = traccia
        return traccia

    def list_for_place(self, place_id: str) -> list[Traccia]:
        risultato = [t for t in self._store.values() if t.place_id == place_id]
        return sorted(risultato, key=lambda t: (t.creato_il, t.id))


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class TracciaStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB, query
    fallita) sul ledger — stesso ruolo di
    `urban_memory.repository.MemoryStorageError`/
    `urban_memory.segnale_repository.SegnaleStorageError`: NON un errore di
    dominio. Catturata e degradata nel lato-lettura di `POST /itinerary`
    (`api.main.create_itinerary`), mai un 503."""


class PostgresTracciaRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso). Stesso codice nei due profili:
    cambia solo il DSN. Schema versionato in
    `services/urban-memory/sql/01_fluttuante_schema.sql` (tabella
    `traccia_luogo`, `UNIQUE(segnale_id)` a difesa dell'idempotenza),
    applicato da `urban_memory.migrate.migrate(dsn)` prima del primo uso.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresTracciaRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo."""
        return cls(database_url_from_env(dotenv_path))

    def deposita(
        self, *, segnale_id: str, place_id: str, temi: list[str], creato_il: datetime
    ) -> Traccia:
        id_ = f"traccia-{uuid.uuid4().hex}"
        query = (
            "INSERT INTO traccia_luogo (id, segnale_id, place_id, temi, creato_il) "
            "VALUES (%(id)s, %(segnale_id)s, %(place_id)s, %(temi)s, %(creato_il)s) "
            "RETURNING id, segnale_id, place_id, temi, creato_il"
        )
        params: dict[str, Any] = {
            "id": id_,
            "segnale_id": segnale_id,
            "place_id": place_id,
            "temi": list(temi),
            "creato_il": creato_il,
        }
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            # Cattura ANCHE la violazione UNIQUE(segnale_id) (difesa in
            # profondità dell'idempotenza): uniformata alla stessa famiglia
            # di eccezione infrastrutturale, mai un'eccezione psycopg grezza.
            raise TracciaStorageError(
                f"impossibile depositare la traccia per segnale_id={segnale_id!r}: {exc}"
            ) from exc
        assert riga is not None  # RETURNING su un INSERT riuscito produce sempre una riga
        return _from_row(riga)

    def list_for_place(self, place_id: str) -> list[Traccia]:
        query = (
            "SELECT id, segnale_id, place_id, temi, creato_il FROM traccia_luogo "
            "WHERE place_id = %(place_id)s ORDER BY creato_il, id"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"place_id": place_id})
                    righe = list(cur.fetchall())
        except psycopg.Error as exc:
            raise TracciaStorageError(f"lettura fallita su traccia_luogo: {exc}") from exc
        return [_from_row(riga) for riga in righe]


def _from_row(riga: dict[str, Any]) -> Traccia:
    return Traccia(
        id=riga["id"],
        segnale_id=riga["segnale_id"],
        place_id=riga["place_id"],
        temi=tuple(riga["temi"] or []),
        creato_il=riga["creato_il"],
    )
