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

`set_stato_aggancio`/`list_aggancio_fallito` registrano/interrogano
`MemoryContribution.stato_aggancio` (`contracts.MemoryLinkState`): l'ESITO
di un tentativo di aggancio al grafo, MAI la decisione di curatela in sé.
Scritti SOLO da `urban_memory.service` (`curate_contribution` quando riceve
un `linker`, `retry_link_contribution`) — invariante "curato tira aggancio",
`docs/ENGINE_INVARIANTS.md` §11-B.

Scarto esplicito (`scarta`, `sql/05_scarto_schema.sql`): un contributo NON
curato può essere scartato con un motivo; mai un DELETE. Lo stato di scarto
(`scartato_il`, `motivo_scarto`) vive nel repository, NON nel contratto
`MemoryContribution`. Le letture di pubblicazione e di aggregazione
(`list_pending`, `list_curated`, `get_curated`) escludono gli scartati, quindi
li esclude anche l'Urban Intelligence Index che le somma. `list_aggancio_fallito`
riguarda solo i curati e uno scartato non è mai curato: nessun filtro
necessario. `get(id)` invece restituisce ANCHE gli scartati ("così com'è
persistito": è un lookup per id, non una lettura di pubblicazione); `curate`
su uno scartato fallisce con `ContributoScartato`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg
from contracts import MemoryContribution, MemoryLinkState
from psycopg.rows import dict_row

from ._env import database_url_from_env

__all__ = [
    "MemoryRepository",
    "InMemoryMemoryRepository",
    "PostgresMemoryRepository",
    "MemoryStorageError",
    "ScartoError",
    "ContributoInesistente",
    "ContributoNonScartabile",
    "ContributoScartato",
    "MotivoScartoRichiesto",
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
    "stato_aggancio",
)
_COLUMNS_SQL = ", ".join(_COLUMNS)


class ScartoError(Exception):
    """Base degli errori di dominio dello scarto/curatela sul repository."""


class ContributoInesistente(ScartoError):
    """Nessun contributo con quell'id."""


class ContributoNonScartabile(ScartoError):
    """Il contributo è già curato o già scartato: non si scarta."""


class ContributoScartato(ScartoError):
    """Il contributo è stato scartato: non si cura."""


class MotivoScartoRichiesto(ScartoError, ValueError):
    """Il motivo di scarto è obbligatorio e non può essere vuoto."""


def _motivo_valido(motivo: str) -> str:
    pulito = motivo.strip()
    if not pulito:
        raise MotivoScartoRichiesto("il motivo di scarto è obbligatorio e non può essere vuoto")
    return pulito


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

    def list_curated(self) -> list[MemoryContribution]:
        """TUTTI i contributi con `curato=True`, su qualunque place — a
        differenza di `get_curated(place_id)`, che filtra per un singolo
        place. Usato da `urban_memory.audit` per verificare l'esistenza dei
        target di OGNI contributo pubblicato, non di uno alla volta."""
        ...

    def set_stato_aggancio(
        self, memory_id: str, stato: MemoryLinkState
    ) -> MemoryContribution:
        """Registra l'ESITO di un tentativo di aggancio al grafo
        (`AGGANCIATO`/`AGGANCIO_FALLITO`) sul contributo `memory_id` e lo
        restituisce aggiornato. Scritto SOLO da `urban_memory.service`
        (`curate_contribution`/`retry_link_contribution`), mai dal
        conferimento o dalla curatela in sé: è un fatto sull'ESECUZIONE
        dell'aggancio, non sulla revisione umana. Solleva `KeyError` se
        `memory_id` non esiste."""
        ...

    def list_aggancio_fallito(self) -> list[MemoryContribution]:
        """Contributi CURATI (`curato=True`) il cui ultimo tentativo di
        aggancio al grafo è fallito (`stato_aggancio=AGGANCIO_FALLITO`): la
        coda di retry (`urban_memory.service.retry_link_contribution`) —
        stato di attesa recuperabile, mai un vicolo cieco."""
        ...

    def scarta(self, memory_id: str, motivo: str) -> MemoryContribution:
        """Scarta (mai DELETE) un contributo esistente, NON curato e non già
        scartato; `motivo` obbligatorio (strip non vuoto, altrimenti
        `MotivoScartoRichiesto`). Solleva `ContributoInesistente` se l'id non
        esiste, `ContributoNonScartabile` se è curato o già scartato. Gli
        scartati spariscono da `list_pending`/`list_curated`/`get_curated`."""
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
        # Stato di scarto fuori dal contratto: id -> (scartato_il, motivo).
        self._scartati: dict[str, tuple[datetime, str]] = {}

    def _visibili(self) -> list[MemoryContribution]:
        return [c for c in self._store.values() if c.id not in self._scartati]

    def submit(self, contribution: MemoryContribution) -> MemoryContribution:
        self._store[contribution.id] = contribution
        return contribution

    def get_curated(self, place_id: str) -> list[MemoryContribution]:
        risultato = [c for c in self._visibili() if c.curato and place_id in c.riguarda]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def list_pending(self) -> list[MemoryContribution]:
        risultato = [c for c in self._visibili() if not c.curato]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def curate(self, memory_id: str) -> MemoryContribution:
        try:
            corrente = self._store[memory_id]
        except KeyError:
            raise KeyError(f"nessun contributo con id={memory_id!r}") from None
        if memory_id in self._scartati:
            raise ContributoScartato(f"il contributo id={memory_id!r} è stato scartato")
        aggiornato = corrente.model_copy(update={"curato": True})
        self._store[memory_id] = aggiornato
        return aggiornato

    def get(self, memory_id: str) -> MemoryContribution | None:
        return self._store.get(memory_id)

    def list_curated(self) -> list[MemoryContribution]:
        risultato = [c for c in self._visibili() if c.curato]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def set_stato_aggancio(
        self, memory_id: str, stato: MemoryLinkState
    ) -> MemoryContribution:
        try:
            corrente = self._store[memory_id]
        except KeyError:
            raise KeyError(f"nessun contributo con id={memory_id!r}") from None
        aggiornato = corrente.model_copy(update={"stato_aggancio": stato})
        self._store[memory_id] = aggiornato
        return aggiornato

    def list_aggancio_fallito(self) -> list[MemoryContribution]:
        risultato = [
            c
            for c in self._store.values()
            if c.curato and c.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO
        ]
        return sorted(risultato, key=lambda c: (c.creato_il, c.id))

    def scarta(self, memory_id: str, motivo: str) -> MemoryContribution:
        _motivo_valido(motivo)
        corrente = self._store.get(memory_id)
        if corrente is None:
            raise ContributoInesistente(f"nessun contributo con id={memory_id!r}")
        if corrente.curato or memory_id in self._scartati:
            raise ContributoNonScartabile(
                f"il contributo id={memory_id!r} è curato o già scartato: non si scarta"
            )
        self._scartati[memory_id] = (datetime.now(UTC), motivo.strip())
        return corrente


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
            f"%(consenso)s, %(licenza)s, %(creato_il)s, %(curato)s, %(stato_aggancio)s) "
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
            "WHERE curato = true AND scartato_il IS NULL AND %(place_id)s = ANY(riguarda) "
            "ORDER BY creato_il, id"
        )
        righe = self._select(query, {"place_id": place_id})
        return [_from_row(riga) for riga in righe]

    def list_pending(self) -> list[MemoryContribution]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM memory_contribution "
            "WHERE curato = false AND scartato_il IS NULL ORDER BY creato_il, id"
        )
        righe = self._select(query, {})
        return [_from_row(riga) for riga in righe]

    def curate(self, memory_id: str) -> MemoryContribution:
        query = (
            f"UPDATE memory_contribution SET curato = true "
            f"WHERE id = %(id)s AND scartato_il IS NULL RETURNING {_COLUMNS_SQL}"
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
            # Nessuna riga aggiornata: inesistente oppure scartato.
            if self.get(memory_id) is None:
                raise KeyError(f"nessun contributo con id={memory_id!r}")
            raise ContributoScartato(f"il contributo id={memory_id!r} è stato scartato")
        return _from_row(riga)

    def get(self, memory_id: str) -> MemoryContribution | None:
        query = f"SELECT {_COLUMNS_SQL} FROM memory_contribution WHERE id = %(id)s"
        righe = self._select(query, {"id": memory_id})
        if not righe:
            return None
        return _from_row(righe[0])

    def list_curated(self) -> list[MemoryContribution]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM memory_contribution "
            "WHERE curato = true AND scartato_il IS NULL ORDER BY creato_il, id"
        )
        righe = self._select(query, {})
        return [_from_row(riga) for riga in righe]

    def set_stato_aggancio(
        self, memory_id: str, stato: MemoryLinkState
    ) -> MemoryContribution:
        query = (
            f"UPDATE memory_contribution SET stato_aggancio = %(stato)s "
            f"WHERE id = %(id)s RETURNING {_COLUMNS_SQL}"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"id": memory_id, "stato": stato.value})
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryStorageError(
                f"impossibile registrare l'esito dell'aggancio per id={memory_id!r}: {exc}"
            ) from exc
        if riga is None:
            raise KeyError(f"nessun contributo con id={memory_id!r}")
        return _from_row(riga)

    def list_aggancio_fallito(self) -> list[MemoryContribution]:
        query = (
            f"SELECT {_COLUMNS_SQL} FROM memory_contribution "
            "WHERE curato = true AND stato_aggancio = %(stato)s ORDER BY creato_il, id"
        )
        righe = self._select(query, {"stato": MemoryLinkState.AGGANCIO_FALLITO.value})
        return [_from_row(riga) for riga in righe]

    def scarta(self, memory_id: str, motivo: str) -> MemoryContribution:
        pulito = _motivo_valido(motivo)
        query = (
            "UPDATE memory_contribution SET scartato_il = now(), "
            "motivo_scarto = %(motivo)s "
            "WHERE id = %(id)s AND curato = false AND scartato_il IS NULL "
            f"RETURNING {_COLUMNS_SQL}"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"id": memory_id, "motivo": pulito})
                    riga = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryStorageError(
                f"impossibile scartare il contributo id={memory_id!r}: {exc}"
            ) from exc
        if riga is None:
            if self.get(memory_id) is None:
                raise ContributoInesistente(f"nessun contributo con id={memory_id!r}")
            raise ContributoNonScartabile(
                f"il contributo id={memory_id!r} è curato o già scartato: non si scarta"
            )
        return _from_row(riga)

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
        "stato_aggancio": (
            contribution.stato_aggancio.value if contribution.stato_aggancio is not None else None
        ),
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
        stato_aggancio=riga.get("stato_aggancio"),
    )
