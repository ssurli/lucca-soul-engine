"""Persistenza dei contributi di Urban Memory.

Due percorsi per la stessa interfaccia (`MemoryRepository`), stesso pattern
di `graph.source.CandidateSource`:

- `InMemoryMemoryRepository` — dizionario in-process. È il percorso usato
  nei test e finché `DATABASE_URL` non è configurato.
- `PostgresMemoryRepository` — Neon (`sslmode=require`) in cloud o Postgres
  locale (Docker sul PC fisso): stesso codice nei due profili, cambia solo
  il DSN. Predisposta ma NON ancora implementata in questa wave: nessun
  database è raggiungibile da qui (vedi la sua docstring per lo schema di
  tabella atteso).

Nessuna delle due implementazioni applica i vincoli etici (consenso,
licenza, pseudonimo, curatela): quelli vivono in `urban_memory.service`, in
un solo punto verificabile. Il repository sa solo leggere e scrivere ciò
che il servizio gli passa già validato.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from contracts import MemoryContribution

__all__ = [
    "MemoryRepository",
    "InMemoryMemoryRepository",
    "PostgresMemoryRepository",
]


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


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker) — predisposta, non implementata
# ---------------------------------------------------------------------------


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parser minimale di `.env` (stesso pattern di `graph.env`): KEY=VALUE,
    righe vuote e `#commenti` ignorati, virgolette attorno al valore
    rimosse. Nessuna dipendenza da `python-dotenv`: qui basta questo."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _database_url_from_env(dotenv_path: Path | None = None) -> str:
    """Legge `DATABASE_URL` dal `.env` (radice del repo) e dall'ambiente di
    processo (che ha sempre la precedenza sul file). Nessun host hardcoded,
    nessun `if local/cloud`: Neon (`sslmode=require`) o Postgres locale
    dipendono solo da questo valore.

    Solleva `ValueError` se `DATABASE_URL` manca: fallire qui, in modo
    leggibile, è meglio che fallire dentro un driver con un errore di rete
    generico.
    """
    # urban_memory/repository.py -> radice del repo, 3 livelli sopra
    # (stessa profondità di services/graph/graph/env.py).
    repo_root = Path(__file__).resolve().parents[3]
    env = _read_dotenv(dotenv_path or (repo_root / ".env"))
    env.update(os.environ)

    dsn = env.get("DATABASE_URL")
    if not dsn:
        raise ValueError("DATABASE_URL mancante nel .env o nell'ambiente")
    return dsn


class PostgresMemoryRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker) sul PC fisso. NON ANCORA IMPLEMENTATA in questa
    wave: nessun database è raggiungibile da questo ambiente. Il posto è
    predisposto perché `services/api` possa cablarla in una wave successiva
    senza cambiare l'interfaccia (`MemoryRepository`).

    Il DSN arriva SEMPRE dal costruttore (mai letto da `os.environ` dentro i
    metodi di lettura/scrittura): usa `from_env()` per costruirla a partire
    da `DATABASE_URL`, così chi la istanzia resta libero di scegliere la
    fonte di configurazione — stesso pattern di
    `graph.source.Neo4jCandidateSource.from_credentials`. Nessun host
    hardcoded, nessun `if local/cloud`: Neon o Postgres locale dipendono
    solo dal valore di `DATABASE_URL` nel `.env`.

    Tabella attesa (allineata a `docs/DATA_CONTRACTS.md` §4 —
    `MemoryContribution`)::

        CREATE TABLE IF NOT EXISTS memory_contribution (
            id                TEXT PRIMARY KEY,
            kind              TEXT NOT NULL,
            testo             TEXT,
            media_uri         TEXT,
            riguarda          TEXT[] NOT NULL DEFAULT '{}',
            contributor_id    TEXT NOT NULL,      -- pseudonimo, mai PII
            contributor_kind  TEXT NOT NULL,
            esperienza_id     TEXT,
            consenso          BOOLEAN NOT NULL,   -- deve essere TRUE
            licenza           TEXT NOT NULL,
            creato_il         TIMESTAMPTZ NOT NULL,
            curato            BOOLEAN NOT NULL DEFAULT FALSE
        );

        -- Vincolo etico ribadito a livello di schema (secondo strato:
        -- `urban_memory.service` lo applica già prima di arrivare qui;
        -- un contributo senza consenso non deve poter persistere nemmeno
        -- per un bug futuro nel livello applicativo).
        ALTER TABLE memory_contribution
            ADD CONSTRAINT memory_contribution_consenso_check CHECK (consenso IS TRUE);

        -- get_curated(place_id) è la query più frequente (curato=True e
        -- place_id in riguarda): indice mirato su entrambi gli accessi.
        CREATE INDEX IF NOT EXISTS memory_contribution_curato_idx
            ON memory_contribution (curato);
        CREATE INDEX IF NOT EXISTS memory_contribution_riguarda_gin_idx
            ON memory_contribution USING GIN (riguarda);

    Come per il grafo (`services/graph/cypher/`), la migrazione andrà
    versionata quando questa classe verrà implementata; qui resta solo
    documentata perché nessun database è raggiungibile in questa wave.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresMemoryRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo. Comodità equivalente a
        `graph.env.load_neo4j_config()` per il lato Postgres."""
        return cls(_database_url_from_env(dotenv_path))

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        raise NotImplementedError(
            "PostgresMemoryRepository non è ancora implementata: nessun "
            "database è raggiungibile in questa wave. Usa "
            "InMemoryMemoryRepository nel frattempo (vedi il README del "
            "servizio)."
        )

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        raise NotImplementedError(
            "PostgresMemoryRepository non è ancora implementata: nessun "
            "database è raggiungibile in questa wave. Usa "
            "InMemoryMemoryRepository nel frattempo (vedi il README del "
            "servizio)."
        )

    def list_pending(self) -> list[MemoryContribution]:
        raise NotImplementedError(
            "PostgresMemoryRepository non è ancora implementata: nessun "
            "database è raggiungibile in questa wave. Usa "
            "InMemoryMemoryRepository nel frattempo (vedi il README del "
            "servizio)."
        )

    def curate(self, memory_id: str) -> MemoryContribution:
        raise NotImplementedError(
            "PostgresMemoryRepository non è ancora implementata: nessun "
            "database è raggiungibile in questa wave. Usa "
            "InMemoryMemoryRepository nel frattempo (vedi il README del "
            "servizio)."
        )
