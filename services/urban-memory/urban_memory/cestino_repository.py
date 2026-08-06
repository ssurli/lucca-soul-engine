"""Il cestino permanente dei pattern rifiutati (Fase 3, promozione di un
pattern ricorrente a `:Evento`).

Si cestina il PATTERN (`place_id` + INSIEME di `temi`), non la singola
candidata-del-momento: un pattern cestinato resta cestinato PER SEMPRE (v1,
deliberatamente permanente — la "cestino temporaneo vs permanente" è fuori
scope, task futuro), anche se accumula nuove occorrenze nel ledger dopo il
rifiuto. Altrimenti il cestino non servirebbe a nulla.

Append-only, stesso principio di `traccia_luogo`
(`urban_memory.traccia_repository`): si inserisce, non si aggiorna né
cancella mai una riga. `motivo` è registrato ma NON usato per guidare
alcuna logica in questa v1 — raccoglie solo dati per un task futuro.

Due percorsi per la stessa interfaccia (`PatternCestinatoRepository`), stesso
pattern di `urban_memory.traccia_repository.TracciaRepository`:

- `InMemoryPatternCestinatoRepository` — dizionario in-process. Percorso di
  test e finché `DATABASE_URL` non è configurato.
- `PostgresPatternCestinatoRepository` — Neon o Postgres locale, stesso
  schema versionato in `services/urban-memory/sql/02_ricorrenza_schema.sql`
  (tabella `pattern_cestinato`).
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
    "PatternCestinato",
    "PatternCestinatoRepository",
    "InMemoryPatternCestinatoRepository",
    "PostgresPatternCestinatoRepository",
    "CestinoStorageError",
]


def _temi_canonici(temi: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Stessa canonicalizzazione di
    `traccia_repository.PatternAggregato`/`ricorrenza.PatternCandidato`:
    tupla ordinata alfabeticamente — l'identità di un pattern è l'INSIEME
    dei temi, non l'ordine in cui sono arrivati da un segnale."""
    return tuple(sorted(temi))


@dataclass(frozen=True)
class PatternCestinato:
    """Una riga del cestino — immutabile. `id` è una chiave SURROGATA
    (stesso principio di `Traccia.id`); l'identità DI DOMINIO del pattern
    cestinato è `(place_id, temi)`, verificata da
    `PatternCestinatoRepository.e_cestinato`."""

    id: str
    place_id: str
    temi: tuple[str, ...]
    motivo: str | None
    promotore: str
    cestinato_il: datetime


class PatternCestinatoRepository(Protocol):
    """Interfaccia comune di persistenza per il cestino dei pattern
    rifiutati."""

    def cestina(
        self,
        *,
        place_id: str,
        temi: list[str],
        promotore: str,
        cestinato_il: datetime,
        motivo: str | None = None,
    ) -> PatternCestinato:
        """Registra il rifiuto PERMANENTE del pattern (place_id + insieme di
        temi). `motivo` è opzionale, registrato ma NON usato per guidare
        alcuna logica in questa v1 — solo dati per un task futuro.

        IDEMPOTENTE per registrazione ripetuta: se il pattern è GIÀ
        cestinato (stessa `place_id` + stesso INSIEME di `temi`, da una
        decisione precedente), NON crea una seconda riga — ritorna quella
        ESISTENTE (la decisione originale non viene mai sovrascritta da una
        chiamata successiva). Coerente con "un pattern cestinato resta
        cestinato per sempre"."""
        ...

    def e_cestinato(self, place_id: str, temi: list[str]) -> bool:
        """`True` se il pattern (place_id + insieme di temi) è già stato
        cestinato — usato da `urban_memory.ricorrenza.rileva_candidati` per
        escluderlo PER SEMPRE dai candidati, anche con nuove occorrenze nel
        ledger."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryPatternCestinatoRepository:
    """Implementazione in-process (dizionario) di
    `PatternCestinatoRepository`. Non persiste tra processi."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, tuple[str, ...]], PatternCestinato] = {}

    def cestina(
        self,
        *,
        place_id: str,
        temi: list[str],
        promotore: str,
        cestinato_il: datetime,
        motivo: str | None = None,
    ) -> PatternCestinato:
        chiave = (place_id, _temi_canonici(temi))
        esistente = self._store.get(chiave)
        if esistente is not None:
            return esistente
        cestinato = PatternCestinato(
            id=f"cestino-{uuid.uuid4().hex}",
            place_id=place_id,
            temi=chiave[1],
            motivo=motivo,
            promotore=promotore,
            cestinato_il=cestinato_il,
        )
        self._store[chiave] = cestinato
        return cestinato

    def e_cestinato(self, place_id: str, temi: list[str]) -> bool:
        return (place_id, _temi_canonici(temi)) in self._store


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class CestinoStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB,
    query fallita) sul cestino — stesso ruolo di
    `traccia_repository.TracciaStorageError`/`repository.MemoryStorageError`:
    NON un errore di dominio."""


class PostgresPatternCestinatoRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso). Stesso codice nei due profili:
    cambia solo il DSN. Schema versionato in
    `services/urban-memory/sql/02_ricorrenza_schema.sql` (tabella
    `pattern_cestinato`, `UNIQUE(place_id, temi)` a difesa della permanenza),
    applicato da `urban_memory.migrate.migrate(dsn)` prima del primo uso.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresPatternCestinatoRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo."""
        return cls(database_url_from_env(dotenv_path))

    def cestina(
        self,
        *,
        place_id: str,
        temi: list[str],
        promotore: str,
        cestinato_il: datetime,
        motivo: str | None = None,
    ) -> PatternCestinato:
        temi_canonici = list(_temi_canonici(temi))
        id_ = f"cestino-{uuid.uuid4().hex}"
        query = (
            "INSERT INTO pattern_cestinato "
            "(id, place_id, temi, motivo, promotore, cestinato_il) "
            "VALUES (%(id)s, %(place_id)s, %(temi)s, %(motivo)s, %(promotore)s, "
            "%(cestinato_il)s) "
            "ON CONFLICT (place_id, temi) DO NOTHING "
            "RETURNING id, place_id, temi, motivo, promotore, cestinato_il"
        )
        params: dict[str, Any] = {
            "id": id_,
            "place_id": place_id,
            "temi": temi_canonici,
            "motivo": motivo,
            "promotore": promotore,
            "cestinato_il": cestinato_il,
        }
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                    if riga is None:
                        # Conflitto: il pattern è GIÀ cestinato da una
                        # decisione precedente — rilegge quella riga
                        # ESISTENTE, mai fabbrica un duplicato né sovrascrive
                        # la decisione originale.
                        cur.execute(
                            "SELECT id, place_id, temi, motivo, promotore, cestinato_il "
                            "FROM pattern_cestinato "
                            "WHERE place_id = %(place_id)s AND temi = %(temi)s",
                            {"place_id": place_id, "temi": temi_canonici},
                        )
                        riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise CestinoStorageError(
                f"impossibile cestinare il pattern place_id={place_id!r}, "
                f"temi={temi_canonici!r}: {exc}"
            ) from exc
        assert riga is not None  # o l'INSERT, o la SELECT di conflitto, produce sempre una riga
        return _from_row(riga)

    def e_cestinato(self, place_id: str, temi: list[str]) -> bool:
        temi_canonici = list(_temi_canonici(temi))
        query = (
            "SELECT 1 FROM pattern_cestinato "
            "WHERE place_id = %(place_id)s AND temi = %(temi)s"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, {"place_id": place_id, "temi": temi_canonici})
                    trovato = cur.fetchone() is not None
        except psycopg.Error as exc:
            raise CestinoStorageError(f"lettura fallita su pattern_cestinato: {exc}") from exc
        return trovato


def _from_row(riga: dict[str, Any]) -> PatternCestinato:
    return PatternCestinato(
        id=riga["id"],
        place_id=riga["place_id"],
        temi=tuple(riga["temi"] or []),
        motivo=riga["motivo"],
        promotore=riga["promotore"],
        cestinato_il=riga["cestinato_il"],
    )
