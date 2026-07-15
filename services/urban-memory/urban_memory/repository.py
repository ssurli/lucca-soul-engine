"""Persistenza dei contributi di Urban Memory.

Due percorsi per la stessa interfaccia (`MemoryRepository`), stesso pattern
di `graph.source.CandidateSource`:

- `InMemoryMemoryRepository` — dizionario in-process. È il percorso usato
  nei test e finché `DATABASE_URL` non è configurato.
- `PostgresMemoryRepository` — Neon (`sslmode=require`) in cloud o Postgres
  locale (Docker sul PC fisso): stesso codice nei due profili, cambia solo
  il DSN letto da `DATABASE_URL`. Persiste DAVVERO: la memoria non si azzera
  al riavvio del processo (il fossato del progetto non può vivere solo in
  RAM). Lo schema di tabella è versionato e idempotente in
  `services/urban-memory/sql/00_memory_schema.sql` (vedi `urban_memory.
  migrate`), con `CHECK (consenso = true)` e `CHECK (char_length(licenza) >=
  1)` a difesa in profondità, oltre ai controlli già fatti da
  `urban_memory.service`.

Nessuna delle due implementazioni applica i vincoli etici (consenso,
licenza, pseudonimo, curatela): quelli vivono in `urban_memory.service`, in
un solo punto verificabile. Il repository sa solo leggere e scrivere ciò
che il servizio gli passa già validato — i due `CHECK` in
`00_memory_schema.sql` sono l'unica eccezione, ed esistono apposta come
seconda barriera, non come prima.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import psycopg
from contracts import MemoryContribution
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "MemoryRepository",
    "InMemoryMemoryRepository",
    "PostgresMemoryRepository",
    "MemoryStorageError",
]

_COLUMNS = (
    "id",
    "kind",
    "testo",
    "media_uri",
    "riguarda",
    "contributor_id",
    "contributor_kind",
    "esperienza_id",
    "consenso",
    "licenza",
    "creato_il",
    "curato",
)
_COLUMNS_SQL = ", ".join(_COLUMNS)


class MemoryRepository(Protocol):
    """Interfaccia comune di persistenza per i contributi di Urban Memory."""

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        """Persiste il contributo (già validato da `urban_memory.service`) e
        lo restituisce."""
        ...

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        """Contributi CURATI (`curato=True`) che riguardano `place_id`
        (`place_id in contribution.riguarda`). Solo questi sono
        pubblicabili: la memoria di una città non si pubblica grezza."""
        ...

    def list_pending(self) -> list[MemoryContribution]:
        """Contributi in attesa di curatela (`curato=False`): la coda che
        alimenta la revisione umana prima della pubblicazione."""
        ...

    def curate(self, memory_id: str) -> MemoryContribution:
        """Imposta `curato=True` sul contributo `memory_id` e lo restituisce.
        Solleva `KeyError` se `memory_id` non esiste."""
        ...

    def get(self, memory_id: str) -> MemoryContribution | None:
        """Il contributo con id `memory_id`, letto COSÌ COM'È persistito —
        curato o no. `None` se non esiste: a differenza di `curate`, questo
        è un lookup, non un comando, quindi "non esiste" non è un errore.
        Usato per RILEGGERE un contributo già persistito (es. per riagganciarlo
        al grafo con il dato reale, mai uno ricostruito in memoria) — vedi
        `urban_memory.link`."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryMemoryRepository:
    """Implementazione in-process (dizionario) di `MemoryRepository`.

    Non persiste tra processi: è il percorso usato nei test e finché
    `DATABASE_URL` non è configurato (vedi `PostgresMemoryRepository`).
    """

    def __init__(self) -> None:
        self._store: dict[str, MemoryContribution] = {}

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        self._store[contribution.id] = contribution
        return contribution

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        risultato = [c for c in self._store.values() if c.curato and place_id in c.riguarda]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def list_pending(self) -> list[MemoryContribution]:
        risultato = [c for c in self._store.values() if not c.curato]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def curate(self, memory_id: str) -> MemoryContribution:
        try:
            corrente = self._store[memory_id]
        except KeyError:
            raise KeyError(f"nessun contributo con id={memory_id!r}") from None
        aggiornato = corrente.model_copy(update={"curato": True})
        self._store[memory_id] = aggiornato
        return aggiornato

    def get(self, memory_id: str) -> MemoryContribution | None:
        return self._store.get(memory_id)


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class MemoryStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB,
    query fallita) — NON un'eccezione di dominio: NON è una sottoclasse di
    `urban_memory.service.UrbanMemoryError`.

    La distinzione è deliberata: `UrbanMemoryError` (e le sue sottoclassi:
    `ConsentRequiredError`, `LicenseRequiredError`, `PseudonymRequiredError`)
    significa "questo contributo viola una regola non negoziabile", un 422
    per il BFF. `MemoryStorageError` significa "il database non ha potuto
    completare l'operazione" (rete, credenziali, un `CHECK` scattato per un
    bug applicativo a monte) — il BFF può distinguerla e rispondere di
    conseguenza, invece di restituire un 500 opaco che confonde le due
    situazioni molto diverse.
    """


class PostgresMemoryRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso, o un cluster nativo). Stesso
    codice nei due profili: cambia solo il DSN. Nessun host hardcoded,
    nessun `if local/cloud` — dipende solo dalla stringa passata al
    costruttore (tipicamente `DATABASE_URL`, letta da `from_env()`).

    Lo schema atteso (`memory_contribution`, colonne speculari a
    `MemoryContribution`, `docs/DATA_CONTRACTS.md` §4) è versionato e
    idempotente in `services/urban-memory/sql/00_memory_schema.sql`: va
    applicato una volta con `urban_memory.migrate.migrate(dsn)` (o `python -m
    urban_memory.migrate`) prima di usare questa classe. Questa classe non
    applica la migrazione da sé (nessun DDL implicito a ogni richiesta): la
    migrazione è un passo esplicito e versionato, come il seed del grafo.

    Una connessione (e una transazione) per operazione: nessuno stato di
    connessione persistente tenuto in `self` — coerente con "la memoria
    sopravvive al riavvio del processo che la scrive", non solo del
    processo che la legge. Ogni errore psycopg è mappato in
    `MemoryStorageError` (mai lasciato propagare come eccezione psycopg
    grezza): è un errore infrastrutturale, non un `UrbanMemoryError` di
    dominio.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresMemoryRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo. Comodità equivalente a
        `graph.env.load_neo4j_config()` per il lato Postgres."""
        return cls(database_url_from_env(dotenv_path))

    # -- lettura/scrittura -----------------------------------------------

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        query = (
            f"INSERT INTO memory_contribution ({_COLUMNS_SQL}) "
            f"VALUES (%(id)s, %(kind)s, %(testo)s, %(media_uri)s, %(riguarda)s, "
            f"%(contributor_id)s, %(contributor_kind)s, %(esperienza_id)s, "
            f"%(consenso)s, %(licenza)s, %(creato_il)s, %(curato)s) "
            f"RETURNING {_COLUMNS_SQL}"
        )
        params = _to_params(contribution)
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryStorageError(
                f"impossibile persistere il contributo id={contribution.id!r}: {exc}"
            ) from exc
        assert riga is not None  # RETURNING su un INSERT riuscito produce sempre una riga
        return _from_row(riga)

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM memory_contribution "
            "WHERE curato = true AND %(place_id)s = ANY(riguarda) "
            "ORDER BY creato_il, id"
        )
        righe = self._select(query, {"place_id": place_id})
        return [_from_row(riga) for riga in righe]

    def list_pending(self) -> list[MemoryContribution]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM memory_contribution "
            "WHERE curato = false ORDER BY creato_il, id"
        )
        righe = self._select(query, {})
        return [_from_row(riga) for riga in righe]

    def curate(self, memory_id: str) -> MemoryContribution:
        query = (
            f"UPDATE memory_contribution SET curato = true "
            f"WHERE id = %(id)s RETURNING {_COLUMNS_SQL}"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"id": memory_id})
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryStorageError(
                f"impossibile curare il contributo id={memory_id!r}: {exc}"
            ) from exc
        if riga is None:
            raise KeyError(f"nessun contributo con id={memory_id!r}")
        return _from_row(riga)

    def get(self, memory_id: str) -> MemoryContribution | None:
        query = f"SELECT {_COLUMNS_SQL} FROM memory_contribution WHERE id = %(id)s"
        righe = self._select(query, {"id": memory_id})
        if not righe:
            return None
        return _from_row(righe[0])

    # -- interno ------------------------------------------------------------

    def _select(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    return list(cur.fetchall())
        except psycopg.Error as exc:
            raise MemoryStorageError(f"lettura fallita su memory_contribution: {exc}") from exc


def _to_params(contribution: MemoryContribution) -> dict[str, Any]:
    return {
        "id": contribution.id,
        "kind": contribution.kind.value,
        "testo": contribution.testo,
        "media_uri": contribution.media_uri,
        "riguarda": list(contribution.riguarda),
        "contributor_id": contribution.contributor_id,
        "contributor_kind": contribution.contributor_kind.value,
        "esperienza_id": contribution.esperienza_id,
        "consenso": contribution.consenso,
        "licenza": contribution.licenza,
        "creato_il": contribution.creato_il,
        "curato": contribution.curato,
    }


def _from_row(riga: dict[str, Any]) -> MemoryContribution:
    return MemoryContribution(
        id=riga["id"],
        kind=riga["kind"],
        testo=riga["testo"],
        media_uri=riga["media_uri"],
        riguarda=list(riga["riguarda"] or []),
        contributor_id=riga["contributor_id"],
        contributor_kind=riga["contributor_kind"],
        esperienza_id=riga["esperienza_id"],
        consenso=riga["consenso"],
        licenza=riga["licenza"],
        creato_il=riga["creato_il"],
        curato=riga["curato"],
    )
