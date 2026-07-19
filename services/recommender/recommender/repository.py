"""Persistenza degli eventi comportamentali (`BehaviorEvent`) — Recommender.

Due percorsi per la stessa interfaccia (`BehaviorEventRepository`), stesso
pattern di `marketplace.repository.BookingRepository`:

- `InMemoryBehaviorEventRepository` — lista in-process. È il percorso usato
  nei test e finché `DATABASE_URL` non è configurato.
- `PostgresBehaviorEventRepository` — Neon (`sslmode=require`) in cloud o
  Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
  cambia solo il DSN letto da `DATABASE_URL`. Persiste DAVVERO. Lo schema è
  versionato e idempotente in `services/recommender/sql/00_events_schema.sql`
  (vedi `recommender.migrate`).

Nessuna delle due implementazioni legge o espone campi commerciali
(`Partner`, `prezzo_eur`, `partner_abbonamento_attivo`, `prenotabile`): questo
modulo non importa quei tipi, e non ha alcun percorso di import verso di
essi — non potrebbe leggerli anche volendo. Stesso principio per i segnali
di notorietà esterna (rating/recensioni di provider terzi) e per i dati di
Urban Memory / Urban Intelligence Index: nessuno di questi tipi è importato
qui (vedi il README del servizio, sezione "Cosa NON è una feature, e perché").
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import psycopg
from contracts import BehaviorEvent

from ._env import database_url_from_env
from .features import conteggio_pesato_per_esperienza, pesare_conteggi_grezzi

__all__ = [
    "BehaviorEventRepository",
    "InMemoryBehaviorEventRepository",
    "PostgresBehaviorEventRepository",
    "RecommenderStorageError",
]


class BehaviorEventRepository(Protocol):
    """Interfaccia comune di persistenza e aggregazione degli eventi."""

    def record(self, event: BehaviorEvent) -> None:
        """Persiste UN evento comportamentale. Nessuna validazione di dominio
        oltre a quella già fatta da Pydantic sul contratto `BehaviorEvent`:
        questo repository non decide se un evento è "valido" nel senso di
        business, solo se è persistibile."""
        ...

    def conteggio_per_esperienza(self) -> dict[str, float]:
        """Conteggio AGGREGATO e PESATO (vedi `recommender.features.PESI_TIPO`)
        degli eventi per `experience_id`, su TUTTA la storia persistita.

        Aggregato e anonimo per costruzione: il risultato non contiene
        `person_id` né alcun dettaglio per singola persona. Questa è l'UNICA
        feature esposta dal repository al livello di ranking
        (`recommender.ranking.costruisci_score_fn`): nessun altro metodo di
        aggregazione è necessario per questa wave.
        """
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryBehaviorEventRepository:
    """Implementazione in-process (lista) di `BehaviorEventRepository`.

    Non persiste tra processi: è il percorso usato nei test e finché
    `DATABASE_URL` non è configurato (vedi `PostgresBehaviorEventRepository`).
    """

    def __init__(self) -> None:
        self._eventi: list[BehaviorEvent] = []

    def record(self, event: BehaviorEvent) -> None:
        self._eventi.append(event)

    def conteggio_per_esperienza(self) -> dict[str, float]:
        return conteggio_pesato_per_esperienza(self._eventi)


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class RecommenderStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB, query
    fallita) — mai un'eccezione psycopg grezza lasciata risalire. Stessa
    distinzione di `marketplace.repository.MarketplaceStorageError` e
    `urban_memory.repository.MemoryStorageError`: questo servizio non ha
    (per ora) eccezioni di dominio proprie, perché non applica regole di
    business sugli eventi (li registra e li aggrega soltanto) — solo
    infrastruttura."""


class PostgresBehaviorEventRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso, o un cluster nativo). Stesso
    codice nei due profili: cambia solo il DSN. Nessun host hardcoded,
    nessun `if local/cloud`.

    Lo schema atteso (`behavior_event`, colonne speculari a `BehaviorEvent`
    più `id` surrogato e `ricevuto_il`, docs/DATA_CONTRACTS.md §6) è
    versionato e idempotente in
    `services/recommender/sql/00_events_schema.sql`: va applicato una volta
    con `recommender.migrate.migrate(dsn)` (o `python -m recommender.migrate`)
    prima di usare questa classe.

    Una connessione (e una transazione) per operazione: nessuno stato di
    connessione persistente tenuto in `self`. Ogni errore psycopg è mappato in
    `RecommenderStorageError` (mai lasciato propagare come eccezione psycopg
    grezza).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresBehaviorEventRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo — equivalente a
        `marketplace.repository.PostgresBookingRepository.from_env()`."""
        return cls(database_url_from_env(dotenv_path))

    def record(self, event: BehaviorEvent) -> None:
        query = (
            "INSERT INTO behavior_event (person_id, tipo, experience_id, ts) "
            "VALUES (%(person_id)s, %(tipo)s, %(experience_id)s, %(ts)s)"
        )
        params = {
            "person_id": event.person_id,
            "tipo": event.tipo,
            "experience_id": event.experience_id,
            "ts": event.ts,
        }
        try:
            with psycopg.connect(self._dsn) as conn:
                conn.execute(query, params)
                conn.commit()
        except psycopg.Error as exc:
            raise RecommenderStorageError(
                f"impossibile registrare l'evento comportamentale "
                f"(experience_id={event.experience_id!r}, tipo={event.tipo!r}): {exc}"
            ) from exc

    def conteggio_per_esperienza(self) -> dict[str, float]:
        query = (
            "SELECT tipo, experience_id, COUNT(*) FROM behavior_event "
            "GROUP BY tipo, experience_id"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    righe = cur.fetchall()
        except psycopg.Error as exc:
            raise RecommenderStorageError(
                f"lettura aggregata degli eventi comportamentali fallita: {exc}"
            ) from exc
        return pesare_conteggi_grezzi(righe)
