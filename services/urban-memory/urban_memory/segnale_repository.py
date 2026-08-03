"""Persistenza della tabella-segnale del canale fluttuante (Fase 3,
`docs/PROMOZIONE_TRACCIA.md`).

Due percorsi per la stessa interfaccia (`SegnaleFluttuanteRepository`),
STESSO pattern di `urban_memory.repository.MemoryRepository`:

- `InMemorySegnaleFluttuanteRepository` — dizionario in-process. Percorso di
  test e finché `DATABASE_URL` non è configurato.
- `PostgresSegnaleFluttuanteRepository` — Neon (`sslmode=require`) in cloud o
  Postgres locale (Docker sul PC fisso): stesso codice nei due profili,
  cambia solo il DSN. Schema versionato e idempotente in
  `services/urban-memory/sql/01_fluttuante_schema.sql` (applicato da
  `urban_memory.migrate.migrate`).

**SCADENZA PIGRA (lazy), IDEMPOTENTE per costruzione.** `sweep_scaduti(now)`
è l'UNICA operazione che scrive lo stato `expired`: la query
(`WHERE stato = 'attivo' AND valido_fino <= now`) È la guardia — un segnale
già `expired` non corrisponde mai una seconda volta, quindi `sweep_scaduti`
ritorna SOLO i segnali che sono transitati `attivo -> expired` IN QUESTA
chiamata (mai quelli già scaduti in una chiamata precedente). Questo è ciò
che rende il deposito della traccia, a valle in
`urban_memory.canale_fluttuante.sweep_and_fetch_active`, IDEMPOTENTE senza
bisogno di ulteriore logica: chiamare `sweep_scaduti` due volte sullo stesso
segnale scaduto ritorna una lista vuota la seconda volta, per costruzione
della query — mai un "no-op esplicito" calcolato a parte.

Nessuna delle due implementazioni applica vincoli di dominio (non_commerciale
ammissibile, filtro per profilo...): quelli vivono altrove
(`contracts.segnale_fluttuante_ammissibile`,
`experience_engine.rules.segnali_fluttuanti_pertinenti`). Il repository sa
solo persistere/interrogare ciò che gli viene passato già validato dal
contratto (`SegnaleFluttuante`, `packages/contracts`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg
from contracts import SegnaleFluttuante, StatoSegnaleFluttuante
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "SegnaleFluttuanteRepository",
    "InMemorySegnaleFluttuanteRepository",
    "PostgresSegnaleFluttuanteRepository",
    "SegnaleStorageError",
]

_COLUMNS = (
    "id",
    "descrizione",
    "temi",
    "place_id",
    "non_commerciale",
    "valido_fino",
    "stato",
)
_COLUMNS_SQL = ", ".join(_COLUMNS)


class SegnaleFluttuanteRepository(Protocol):
    """Interfaccia comune di persistenza per la tabella-segnale."""

    def persist(self, segnale: SegnaleFluttuante) -> SegnaleFluttuante:
        """Persiste `segnale` (stato tipicamente `ATTIVO`, il default del
        contratto — a meno che `valido_fino` sia già nel passato: vedi
        `SegnaleFluttuante._expired_se_gia_scaduto`) e lo restituisce."""
        ...

    def sweep_scaduti(self, now: datetime) -> list[SegnaleFluttuante]:
        """Transita ATOMICAMENTE ogni segnale `attivo` con
        `valido_fino <= now` a `expired`, e ritorna SOLO quelli appena
        transitati DA QUESTA chiamata (mai quelli già `expired` da una
        chiamata precedente — la guardia è la query stessa, vedi il
        docstring del modulo). Lista vuota se non c'è nulla da spazzare —
        comportamento IDEMPOTENTE per costruzione: rieseguire questa
        chiamata sugli stessi segnali già spazzati ritorna sempre `[]`."""
        ...

    def fetch_attivi(self, now: datetime) -> list[SegnaleFluttuante]:
        """I segnali `attivo` con `valido_fino > now` — quelli che
        popoleranno `Signal.eventi_attivi` per la composizione
        dell'itinerario. Chiamare DOPO `sweep_scaduti(now)` con lo STESSO
        `now`, mai prima: altrimenti un segnale già scaduto (ma non ancora
        spazzato) potrebbe apparire qui come attivo."""
        ...


# ---------------------------------------------------------------------------
# In-memory — percorso di test e di default finché DATABASE_URL non c'è
# ---------------------------------------------------------------------------


class InMemorySegnaleFluttuanteRepository:
    """Implementazione in-process (dizionario) di
    `SegnaleFluttuanteRepository`. Non persiste tra processi."""

    def __init__(self) -> None:
        self._store: dict[str, SegnaleFluttuante] = {}

    def persist(self, segnale: SegnaleFluttuante) -> SegnaleFluttuante:
        self._store[segnale.id] = segnale
        return segnale

    def sweep_scaduti(self, now: datetime) -> list[SegnaleFluttuante]:
        scaduti: list[SegnaleFluttuante] = []
        for id_, segnale in list(self._store.items()):
            if segnale.stato == StatoSegnaleFluttuante.ATTIVO and segnale.valido_fino <= now:
                aggiornato = segnale.model_copy(update={"stato": StatoSegnaleFluttuante.EXPIRED})
                self._store[id_] = aggiornato
                scaduti.append(aggiornato)
        return sorted(scaduti, key=lambda s: s.id)

    def fetch_attivi(self, now: datetime) -> list[SegnaleFluttuante]:
        attivi = [
            s
            for s in self._store.values()
            if s.stato == StatoSegnaleFluttuante.ATTIVO and s.valido_fino > now
        ]
        return sorted(attivi, key=lambda s: s.id)


# ---------------------------------------------------------------------------
# Postgres (Neon in cloud, locale con Docker/Postgres nativo)
# ---------------------------------------------------------------------------


class SegnaleStorageError(Exception):
    """Errore INFRASTRUTTURALE di persistenza (connessione, vincolo DB, query
    fallita) sulla tabella-segnale — stesso ruolo di
    `urban_memory.repository.MemoryStorageError`: NON un errore di dominio.

    Nel lato-lettura di `POST /itinerary` (`api.main.create_itinerary`) ogni
    istanza di questa eccezione viene catturata e degradata a
    `eventi_attivi=[]` — MAI un 503, a differenza di `/memory`/`/booking`/
    `/events`: qui lo storage del canale fluttuante è un arricchimento
    opzionale della composizione, non il cuore della richiesta.
    """


class PostgresSegnaleFluttuanteRepository:
    """Persistenza reale via Postgres — Neon (`sslmode=require`) in cloud,
    Postgres locale (Docker sul PC fisso). Stesso codice nei due profili:
    cambia solo il DSN. Schema versionato in
    `services/urban-memory/sql/01_fluttuante_schema.sql`, applicato da
    `urban_memory.migrate.migrate(dsn)` prima del primo uso — questa classe
    non applica alcun DDL implicito.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> PostgresSegnaleFluttuanteRepository:
        """Costruisce leggendo `DATABASE_URL` dal `.env` (radice del repo) o
        dall'ambiente di processo."""
        return cls(database_url_from_env(dotenv_path))

    def persist(self, segnale: SegnaleFluttuante) -> SegnaleFluttuante:
        query = (
            f"INSERT INTO segnale_fluttuante ({_COLUMNS_SQL}) "
            "VALUES (%(id)s, %(descrizione)s, %(temi)s, %(place_id)s, "
            "%(non_commerciale)s, %(valido_fino)s, %(stato)s) "
            f"RETURNING {_COLUMNS_SQL}"
        )
        params = _to_params(segnale)
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise SegnaleStorageError(
                f"impossibile persistere il segnale fluttuante id={segnale.id!r}: {exc}"
            ) from exc
        assert riga is not None  # RETURNING su un INSERT riuscito produce sempre una riga
        return _from_row(riga)

    def sweep_scaduti(self, now: datetime) -> list[SegnaleFluttuante]:
        # UPDATE ... WHERE stato = 'attivo' AND valido_fino <= now è la
        # guardia ATOMICA: una seconda esecuzione con lo stesso `now` (o uno
        # successivo) non trova più righe con stato='attivo' per i segnali
        # già transitati da questa chiamata — RETURNING ritorna quindi SOLO
        # le righe appena transitate, mai quelle già expired.
        query = (
            "UPDATE segnale_fluttuante SET stato = 'expired' "
            "WHERE stato = 'attivo' AND valido_fino <= %(now)s "
            f"RETURNING {_COLUMNS_SQL}"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"now": now})
                    righe = list(cur.fetchall())
                conn.commit()
        except psycopg.Error as exc:
            raise SegnaleStorageError(f"sweep fallito su segnale_fluttuante: {exc}") from exc
        return sorted((_from_row(riga) for riga in righe), key=lambda s: s.id)

    def fetch_attivi(self, now: datetime) -> list[SegnaleFluttuante]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM segnale_fluttuante "
            "WHERE stato = 'attivo' AND valido_fino > %(now)s ORDER BY id"
        )
        righe = self._select(query, {"now": now})
        return [_from_row(riga) for riga in righe]

    # -- interno ------------------------------------------------------------

    def _select(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    return list(cur.fetchall())
        except psycopg.Error as exc:
            raise SegnaleStorageError(f"lettura fallita su segnale_fluttuante: {exc}") from exc


def _to_params(segnale: SegnaleFluttuante) -> dict[str, Any]:
    return {
        "id": segnale.id,
        "descrizione": segnale.descrizione,
        "temi": list(segnale.temi),
        "place_id": segnale.place_id,
        "non_commerciale": segnale.non_commerciale,
        "valido_fino": segnale.valido_fino,
        "stato": segnale.stato.value,
    }


def _from_row(riga: dict[str, Any]) -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id=riga["id"],
        descrizione=riga["descrizione"],
        temi=list(riga["temi"] or []),
        place_id=riga["place_id"],
        non_commerciale=riga["non_commerciale"],
        valido_fino=riga["valido_fino"],
        stato=riga["stato"],
    )
