"""Il log permanente del freno di emergenza (docs/STATE_MACHINE.md §4-bis(b),
Fase 3, override di sicurezza su un `:Evento` promosso).

A differenza del cestino (`urban_memory.cestino_repository`), il freno è
RIPETIBILE nel tempo: tirare e rilasciare più volte lo stesso `evento_id` è
un uso normale, previsto ("il pattern è tornato a manifestarsi, poi è stato
di nuovo necessario frenarlo per un motivo diverso") — nessun `UNIQUE`, ogni
azione (`registra`) inserisce SEMPRE una riga nuova, mai un upsert: non c'è
nulla con cui una seconda riga potrebbe confliggere.

Append-only, stesso principio di `traccia_luogo`/`pattern_cestinato`: si
inserisce, non si aggiorna né cancella mai una riga. L'obbligatorietà della
motivazione su un tiro (`docs/STATE_MACHINE.md` — "motivazione testuale
obbligatoria su ogni tiro", non sul rilascio) è verificata dal chiamante
(`urban_memory.freno_pattern.tira_freno`) PRIMA di arrivare qui — questo
repository resta un magazzino, non applica la regola di dominio da solo
(stesso principio di `MemoryContribution.consenso` vs
`urban_memory.service.submit_contribution`: la validazione applicativa è il
gate, lo schema DB è un backstop).

Due percorsi per la stessa interfaccia (`PatternFrenatoRepository`), stesso
pattern di `urban_memory.cestino_repository.PatternCestinatoRepository`:

- `InMemoryPatternFrenatoRepository` — lista in-process. Percorso di test e
  finché `DATABASE_URL` non è configurato.
- `PostgresPatternFrenatoRepository` — Neon o Postgres locale, stesso schema
  versionato in `services/urban-memory/sql/03_freno_schema.sql` (tabella
  `pattern_frenato`).
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
    "PatternFrenato",
    "PatternFrenatoRepository",
    "InMemoryPatternFrenatoRepository",
    "PostgresPatternFrenatoRepository",
    "FrenoStorageError",
]


@dataclass(frozen=True)
class PatternFrenato:
    """Una riga del log del freno — immutabile. `id` è una chiave SURROGATA
    (stesso principio di `PatternCestinato.id`); a differenza del cestino,
    NON esiste qui un'identità di dominio unica: `(evento_id, azione,
    quando)` può ripetersi legittimamente nel tempo (tiri/rilasci
    ripetuti)."""

    id: str
    evento_id: str
    place_id: str | None
    temi: tuple[str, ...]
    azione: str  # 'tirato' | 'rilasciato'
    attore: str
    motivazione: str | None
    quando: datetime


class PatternFrenatoRepository(Protocol):
    """Interfaccia comune di persistenza per il log del freno di
    emergenza."""

    def registra(
        self,
        *,
        evento_id: str,
        place_id: str | None,
        temi: list[str],
        azione: str,
        attore: str,
        motivazione: str | None,
        quando: datetime,
    ) -> PatternFrenato:
        """Registra un tiro (`azione='tirato'`) o un rilascio
        (`azione='rilasciato'`) del freno su `evento_id`. Inserisce SEMPRE
        una riga NUOVA — mai un upsert: il freno è ripetibile nel tempo,
        niente qui va deduplicato."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemoryPatternFrenatoRepository:
    """Implementazione in-process (lista) di `PatternFrenatoRepository`. Non
    persiste tra processi."""

    def __init__(self) -> None:
        self._righe: list[PatternFrenato] = []

    def registra(
        self,
        *,
        evento_id: str,
        place_id: str | None,
        temi: list[str],
        azione: str,
        attore: str,
        motivazione: str | None,
        quando: datetime,
    ) -> PatternFrenato:
        riga = PatternFrenato(
            id=f"freno-{uuid.uuid4().hex}",
            evento_id=evento_id,
            place_id=place_id,
            temi=tuple(temi),
            azione=azione,
            attore=attore,
            motivazione=motivazione,
            quando=quando,
        )
        self._righe.append(riga)
        return riga

    def per_evento(self, evento_id: str) -> list[PatternFrenato]:
        """Comodità per i test: tutte le righe registrate per `evento_id`,
        nell'ordine di inserimento. Non fa parte del `Protocol` (non
        necessaria a `urban_memory.freno_pattern`), solo un aiuto locale a
        questa implementazione e alla sua controparte Postgres sotto."""
        return [riga for riga in self._righe if riga.evento_id == evento_id]


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class FrenoStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB,
    query fallita) sul log del freno — stesso ruolo di
    `cestino_repository.CestinoStorageError`: NON un errore di dominio."""


class PostgresPatternFrenatoRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso). Stesso codice nei due profili:
    cambia solo il DSN. Schema versionato in
    `services/urban-memory/sql/03_freno_schema.sql` (tabella
    `pattern_frenato`, NESSUN `UNIQUE`: ogni azione è una riga nuova),
    applicato da `urban_memory.migrate.migrate(dsn)` prima del primo uso.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresPatternFrenatoRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo."""
        return cls(database_url_from_env(dotenv_path))

    def registra(
        self,
        *,
        evento_id: str,
        place_id: str | None,
        temi: list[str],
        azione: str,
        attore: str,
        motivazione: str | None,
        quando: datetime,
    ) -> PatternFrenato:
        id_ = f"freno-{uuid.uuid4().hex}"
        query = (
            "INSERT INTO pattern_frenato "
            "(id, evento_id, place_id, temi, azione, attore, motivazione, quando) "
            "VALUES (%(id)s, %(evento_id)s, %(place_id)s, %(temi)s, %(azione)s, "
            "%(attore)s, %(motivazione)s, %(quando)s) "
            "RETURNING id, evento_id, place_id, temi, azione, attore, motivazione, quando"
        )
        params: dict[str, Any] = {
            "id": id_,
            "evento_id": evento_id,
            "place_id": place_id,
            "temi": list(temi),
            "azione": azione,
            "attore": attore,
            "motivazione": motivazione,
            "quando": quando,
        }
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise FrenoStorageError(
                f"impossibile registrare il freno per evento_id={evento_id!r}, "
                f"azione={azione!r}: {exc}"
            ) from exc
        assert riga is not None  # l'INSERT senza ON CONFLICT produce sempre una riga
        return _from_row(riga)

    def per_evento(self, evento_id: str) -> list[PatternFrenato]:
        """Comodità per i test (stessa firma della controparte in-memory
        sopra): tutte le righe registrate per `evento_id`, ordinate per
        `quando`."""
        query = (
            "SELECT id, evento_id, place_id, temi, azione, attore, motivazione, quando "
            "FROM pattern_frenato WHERE evento_id = %(evento_id)s ORDER BY quando"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"evento_id": evento_id})
                    righe = cur.fetchall()
        except psycopg.Error as exc:
            raise FrenoStorageError(f"lettura fallita su pattern_frenato: {exc}") from exc
        return [_from_row(riga) for riga in righe]


def _from_row(riga: dict[str, Any]) -> PatternFrenato:
    return PatternFrenato(
        id=riga["id"],
        evento_id=riga["evento_id"],
        place_id=riga["place_id"],
        temi=tuple(riga["temi"] or []),
        azione=riga["azione"],
        attore=riga["attore"],
        motivazione=riga["motivazione"],
        quando=riga["quando"],
    )
