"""Lettura di `BehaviorEvent` grezzi per periodo — Urban Intelligence Index.

`recommender.repository.BehaviorEventRepository.conteggio_per_esperienza()`
espone SOLO un aggregato PESATO (`recommender.features.PESI_TIPO`) su TUTTA
la storia, per `experience_id`: perfetto per il ranking (Wave 3b), ma
INSUFFICIENTE per l'Index, che ha bisogno di:
- eventi filtrati per PERIODO (non tutta la storia);
- `person_id` distinti a grana fine (per il gate k=10,
  `intelligence_index.soglia`);
- eventi grezzi (non pre-pesati/pre-aggregati per `experience_id`): alcuni
  indicatori (`tasso_ritorno`, `coinvolgimento`) ragionano su coppie
  `(person_id, experience_id)` o su date di calendario per persona, non su
  un conteggio già collassato.

Questo modulo introduce quindi un SECONDO percorso di lettura sulla STESSA
tabella `behavior_event` — già creata e migrata da `recommender.migrate`
(`services/recommender/sql/00_events_schema.sql`): NON una seconda
implementazione dello schema (nessun `CREATE TABLE` qui, nessuna
migrazione propria), SOLO una query di lettura diversa, per un bisogno
diverso (reporting/aggregazione periodica, non ranking in tempo reale).
Stesso principio già in uso nel repo per la stessa tabella condivisa da più
letture con scopi diversi.

Due percorsi per la stessa interfaccia (`BehaviorEventSource`), stesso
pattern di `recommender.repository.BehaviorEventRepository`:
- `InMemoryBehaviorEventSource` — lista in-process. Percorso usato dai test
  e finché `DATABASE_URL` non è configurato.
- `PostgresBehaviorEventSource` — Neon (`sslmode=require`) in cloud o
  Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
  cambia solo il DSN letto da `DATABASE_URL`. SOLA LETTURA: non scrive mai
  su `behavior_event` (la scrittura resta responsabilità esclusiva di
  `recommender.PostgresBehaviorEventRepository.record`, via `POST /events`
  nel BFF).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

import psycopg
from contracts import BehaviorEvent
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "BehaviorEventSource",
    "InMemoryBehaviorEventSource",
    "PostgresBehaviorEventSource",
    "IndexStorageError",
]


class BehaviorEventSource(Protocol):
    """Interfaccia comune di lettura degli eventi comportamentali grezzi,
    filtrati per un intervallo di tempo semi-aperto `[inizio, fine)` —
    coerente con `intelligence_index.periodo.intervallo_periodo`."""

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[BehaviorEvent]:
        """Tutti i `BehaviorEvent` con `inizio <= ts < fine`, GREZZI (non
        aggregati): il chiamante (`intelligence_index.indicatori`) fa
        l'aggregazione, non questo repository — stessa separazione già in
        uso in `recommender.repository` tra persistenza e `recommender.
        features` (aggregazione)."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryBehaviorEventSource:
    """Implementazione in-process (lista) di `BehaviorEventSource`.

    Non persiste tra processi: è il percorso usato nei test e finché
    `DATABASE_URL` non è configurato (vedi `PostgresBehaviorEventSource`).
    Può essere popolata direttamente con eventi già noti (utile nei test),
    oppure lasciata vuota e riempita con `record`.
    """

    def __init__(self, eventi: list[BehaviorEvent] | None = None) -> None:
        self._eventi: list[BehaviorEvent] = list(eventi) if eventi is not None else []

    def record(self, event: BehaviorEvent) -> None:
        """Comodità per i test (costruire uno storico sintetico): NON è
        parte di `BehaviorEventSource` (l'Index legge, non scrive)."""
        self._eventi.append(event)

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[BehaviorEvent]:
        return [evento for evento in self._eventi if inizio <= evento.ts < fine]


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo) — SOLA LETTURA
# ---------------------------------------------------------------------------


class IndexStorageError(Exception):
    """Errore INFRASTRUTTURALE di lettura (connessione, query fallita) — mai
    un'eccezione psycopg grezza lasciata risalire. Stessa distinzione di
    `recommender.RecommenderStorageError`/`urban_memory.MemoryStorageError`:
    questo servizio non applica regole di business sugli eventi (li legge e
    li aggrega soltanto) — solo infrastruttura. NON è
    `intelligence_index.soglia.DatiInsufficientiError` (quello è un vincolo
    di dominio/privacy, non un problema di storage)."""


class PostgresBehaviorEventSource:
    """Lettura reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso, o un cluster nativo). Stesso
    codice nei due profili: cambia solo il DSN. Nessun host hardcoded,
    nessun `if local/cloud`.

    Presuppone lo schema `behavior_event` GIÀ applicato da
    `recommender.migrate.migrate(dsn)` (o `python -m recommender.migrate`):
    questa classe non lo crea né lo verifica, e non scrive mai su quella
    tabella (SOLA LETTURA — vedi docstring di modulo).

    Una connessione per operazione: nessuno stato di connessione persistente
    tenuto in `self`. Ogni errore psycopg è mappato in `IndexStorageError`
    (mai lasciato propagare come eccezione psycopg grezza).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresBehaviorEventSource:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo — equivalente a
        `recommender.PostgresBehaviorEventRepository.from_env()`."""
        return cls(database_url_from_env(dotenv_path))

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[BehaviorEvent]:
        query = (
            "SELECT person_id, tipo, experience_id, ts FROM behavior_event "
            "WHERE ts >= %(inizio)s AND ts < %(fine)s"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"inizio": inizio, "fine": fine})
                    righe = cur.fetchall()
        except psycopg.Error as exc:
            raise IndexStorageError(
                f"lettura degli eventi comportamentali nel periodo "
                f"[{inizio.isoformat()}, {fine.isoformat()}) fallita: {exc}"
            ) from exc
        return [
            BehaviorEvent(
                person_id=riga["person_id"],
                tipo=riga["tipo"],
                experience_id=riga["experience_id"],
                ts=riga["ts"],
            )
            for riga in righe
        ]
