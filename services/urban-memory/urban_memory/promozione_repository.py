"""Il LEDGER permanente delle promozioni (Fase 3): fonte di verita' della
decisione di promuovere un pattern a `:Evento`. Il grafo e' la proiezione.

Perche': la decisione viveva solo nel grafo, e Aura Free viene cancellata
per inattivita' (CLAUDE.md: nessun dato vive solo su Aura). Con questo
ledger `python -m urban_memory.ripristina_eventi` ricostruisce gli `:Evento`.

APPEND-ONLY, stesso principio di `freno_repository`: ogni promozione o
ricalcolo e' una riga NUOVA, nessun UNIQUE sul pattern, nessun
UPDATE/DELETE. Due percorsi per la stessa interfaccia
(`PromozioneRepository`): `InMemoryPromozioneRepository` (test / senza
`DATABASE_URL`) e `PostgresPromozioneRepository` (schema in
`sql/04_promozione_schema.sql`, connessione aperta a ogni operazione).
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
    "PatternPromosso",
    "PromozioneRepository",
    "InMemoryPromozioneRepository",
    "PostgresPromozioneRepository",
    "PromozioneStorageError",
]


@dataclass(frozen=True)
class PatternPromosso:
    """Una riga del ledger delle promozioni — immutabile. `promotore` e'
    uno pseudonimo (mai PII)."""

    id: str
    evento_id: str
    place_id: str
    temi: tuple[str, ...]
    cadenza_giorni: float
    promotore: str
    promosso_il: datetime


class PromozioneRepository(Protocol):
    def registra(
        self,
        *,
        evento_id: str,
        place_id: str,
        temi: list[str],
        cadenza_giorni: float,
        promotore: str,
        promosso_il: datetime,
    ) -> PatternPromosso:
        """Inserisce SEMPRE una riga nuova (mai upsert)."""
        ...

    def registrata(self, evento_id: str) -> bool:
        """`True` se esiste almeno una promozione per `evento_id`."""
        ...

    def elenca(self) -> list[PatternPromosso]:
        """TUTTE le righe, ordinate per `promosso_il` (poi `id`)."""
        ...


class PromozioneStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza sul ledger delle promozioni
    (stesso ruolo di `FrenoStorageError`): non un errore di dominio."""


class InMemoryPromozioneRepository:
    def __init__(self) -> None:
        self._righe: list[PatternPromosso] = []

    def registra(
        self,
        *,
        evento_id: str,
        place_id: str,
        temi: list[str],
        cadenza_giorni: float,
        promotore: str,
        promosso_il: datetime,
    ) -> PatternPromosso:
        riga = PatternPromosso(
            id=f"promozione-{uuid.uuid4().hex}",
            evento_id=evento_id,
            place_id=place_id,
            temi=tuple(temi),
            cadenza_giorni=cadenza_giorni,
            promotore=promotore,
            promosso_il=promosso_il,
        )
        self._righe.append(riga)
        return riga

    def registrata(self, evento_id: str) -> bool:
        return any(r.evento_id == evento_id for r in self._righe)

    def elenca(self) -> list[PatternPromosso]:
        return sorted(self._righe, key=lambda r: (r.promosso_il, r.id))


_COLONNE = "id, evento_id, place_id, temi, cadenza_giorni, promotore, promosso_il"


class PostgresPromozioneRepository:
    """Persistenza reale (Neon `sslmode=require` o Postgres locale: stesso
    codice, cambia solo il DSN). Schema in `sql/04_promozione_schema.sql`,
    applicato da `urban_memory.migrate.migrate(dsn)`. Connessione aperta a
    ogni operazione (lazy), come `PostgresPatternFrenatoRepository`."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresPromozioneRepository:
        return cls(database_url_from_env(dotenv_path))

    def registra(
        self,
        *,
        evento_id: str,
        place_id: str,
        temi: list[str],
        cadenza_giorni: float,
        promotore: str,
        promosso_il: datetime,
    ) -> PatternPromosso:
        query = (
            "INSERT INTO pattern_promosso "
            "(id, evento_id, place_id, temi, cadenza_giorni, promotore, promosso_il) "
            "VALUES (%(id)s, %(evento_id)s, %(place_id)s, %(temi)s, %(cadenza_giorni)s, "
            f"%(promotore)s, %(promosso_il)s) RETURNING {_COLONNE}"
        )
        params: dict[str, Any] = {
            "id": f"promozione-{uuid.uuid4().hex}",
            "evento_id": evento_id,
            "place_id": place_id,
            "temi": list(temi),
            "cadenza_giorni": cadenza_giorni,
            "promotore": promotore,
            "promosso_il": promosso_il,
        }
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise PromozioneStorageError(
                f"impossibile registrare la promozione per evento_id={evento_id!r}: {exc}"
            ) from exc
        assert riga is not None  # INSERT senza ON CONFLICT: sempre una riga
        return _from_row(riga)

    def registrata(self, evento_id: str) -> bool:
        query = "SELECT 1 AS x FROM pattern_promosso WHERE evento_id = %(evento_id)s LIMIT 1"
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"evento_id": evento_id})
                    return cur.fetchone() is not None
        except psycopg.Error as exc:
            raise PromozioneStorageError(f"lettura fallita su pattern_promosso: {exc}") from exc

    def elenca(self) -> list[PatternPromosso]:
        query = f"SELECT {_COLONNE} FROM pattern_promosso ORDER BY promosso_il, id"
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query)  # type: ignore[call-overload]
                    righe = cur.fetchall()
        except psycopg.Error as exc:
            raise PromozioneStorageError(f"lettura fallita su pattern_promosso: {exc}") from exc
        return [_from_row(r) for r in righe]


def _from_row(riga: dict[str, Any]) -> PatternPromosso:
    return PatternPromosso(
        id=riga["id"],
        evento_id=riga["evento_id"],
        place_id=riga["place_id"],
        temi=tuple(riga["temi"] or []),
        cadenza_giorni=float(riga["cadenza_giorni"]),
        promotore=riga["promotore"],
        promosso_il=riga["promosso_il"],
    )
