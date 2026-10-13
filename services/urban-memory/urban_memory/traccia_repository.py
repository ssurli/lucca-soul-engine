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
    "PatternAggregato",
]


@dataclass(frozen=True)
class Traccia:
    """Una riga del ledger — immutabile, come si conviene a un append-only.
    `id` è una chiave SURROGATA (generata dall'applicazione, `uuid4`), non
    una chiave naturale: due tracce identiche in place_id/temi/istante
    restano due passaggi distinti (stesso principio di `behavior_event`,
    docs/PROMOZIONE_TRACCIA.md §1). `creato_il` è il `valido_fino` (UTC) del
    segnale scaduto — quando il segnale è scaduto davvero, NON l'istante
    dello sweep pigro che l'ha notato."""

    id: str
    segnale_id: str
    place_id: str
    temi: tuple[str, ...]
    creato_il: datetime


@dataclass(frozen=True)
class PatternAggregato:
    """Un pattern ricorrente grezzo: stesso `place_id` + stesso INSIEME di
    `temi` (canonicalizzato come tupla ordinata alfabeticamente — l'ordine in
    cui i temi arrivano da un singolo segnale non è significativo ai fini
    dell'identità del pattern, solo il loro INSIEME lo è), con tutte le sue
    occorrenze nel ledger. `occorrenze` è `creato_il` di ogni traccia del
    pattern, in ordine crescente — la materia prima da cui
    `urban_memory.ricorrenza.rileva_candidati` calcola intervalli, cadenza e
    regolarità: nessuna logica statistica qui, solo conteggio e
    raggruppamento."""

    place_id: str
    temi: tuple[str, ...]
    occorrenze: tuple[datetime, ...]


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

    def pattern_ricorrenti(self, minimo_occorrenze: int) -> list[PatternAggregato]:
        """Enumera i pattern (place_id + insieme di temi) che hanno
        raggiunto ALMENO `minimo_occorrenze` tracce nel ledger, ciascuno con
        le proprie occorrenze (`creato_il`), ordinate crescenti — la vista
        grezza da cui `urban_memory.ricorrenza.rileva_candidati` calcola
        cadenza e regolarità. Nessuna logica di soglia/tolleranza qui: solo
        conteggio e raggruppamento (il vincolo duro N>=3 vive in
        `urban_memory.ricorrenza.N_MINIMO_OCCORRENZE`, non qui — questo
        metodo accetta qualunque `minimo_occorrenze` positivo, è un
        primitivo di aggregazione, non il gate di dominio)."""
        ...

    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        """Le occorrenze (`creato_il`) di UN pattern ESATTO — `place_id` +
        l'INSIEME di `temi` (canonicalizzato, l'ordine non è significativo,
        stessa convenzione di `PatternAggregato`) — ordinate crescenti.

        A differenza di `pattern_ricorrenti` (che aggrega TUTTI i pattern
        sopra soglia in un colpo solo) e di `list_for_place` (che restituisce
        TUTTE le tracce di un luogo, mischiando temi diversi), questo metodo
        mira a UN pattern specifico e GIÀ promosso: la lettura che
        `urban_memory.frizione_pattern` esegue per calcolare l'ultima
        occorrenza e i battiti di cadenza mancati di UN `:Evento` esistente
        (letto dal grafo con le proprie proprietà `place_id`+`temi`), non un
        campo scritto ad ogni deposito di traccia — il clock del pattern si
        CALCOLA da questo metodo ogni volta che serve, non si mantiene
        incrementalmente nell'hot path di `/itinerary`
        (`urban_memory.canale_fluttuante.sweep_and_fetch_active`), per non
        accoppiare quel percorso a un lookup su `:Evento`.

        Lista vuota se nessuna traccia esiste per questo pattern esatto
        (mai un errore: un pattern promosso con zero occorrenze nel ledger è
        un caso degenere che chi chiama tratta esplicitamente, non un
        malfunzionamento di questo metodo)."""
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

    def pattern_ricorrenti(self, minimo_occorrenze: int) -> list[PatternAggregato]:
        gruppi: dict[tuple[str, tuple[str, ...]], list[datetime]] = {}
        for traccia in self._store.values():
            chiave = (traccia.place_id, tuple(sorted(traccia.temi)))
            gruppi.setdefault(chiave, []).append(traccia.creato_il)
        risultato = [
            PatternAggregato(place_id=place_id, temi=temi, occorrenze=tuple(sorted(occorrenze)))
            for (place_id, temi), occorrenze in gruppi.items()
            if len(occorrenze) >= minimo_occorrenze
        ]
        return sorted(risultato, key=lambda p: (p.place_id, p.temi))

    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        temi_canonici = tuple(sorted(temi))
        occorrenze = [
            traccia.creato_il
            for traccia in self._store.values()
            if traccia.place_id == place_id and tuple(sorted(traccia.temi)) == temi_canonici
        ]
        return sorted(occorrenze)


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

    def pattern_ricorrenti(self, minimo_occorrenze: int) -> list[PatternAggregato]:
        # La canonicalizzazione (temi ordinati alfabeticamente) avviene QUI,
        # in query, non nell'indice (Postgres non ammette una sotto-query in
        # un'espressione di indice): vedi il commento su
        # `traccia_luogo_place_id_temi_idx` in
        # `sql/02_ricorrenza_schema.sql`.
        query = (
            "WITH canonico AS ("
            "  SELECT place_id, "
            "         (SELECT array_agg(t ORDER BY t) FROM unnest(temi) AS t) AS temi_canonici, "
            "         creato_il "
            "  FROM traccia_luogo"
            ") "
            "SELECT place_id, temi_canonici, "
            "       array_agg(creato_il ORDER BY creato_il) AS occorrenze "
            "FROM canonico "
            "GROUP BY place_id, temi_canonici "
            "HAVING count(*) >= %(minimo)s "
            "ORDER BY place_id, temi_canonici"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"minimo": minimo_occorrenze})
                    righe = list(cur.fetchall())
        except psycopg.Error as exc:
            raise TracciaStorageError(f"aggregazione fallita su traccia_luogo: {exc}") from exc
        return [
            PatternAggregato(
                place_id=riga["place_id"],
                temi=tuple(riga["temi_canonici"] or []),
                occorrenze=tuple(riga["occorrenze"] or []),
            )
            for riga in righe
        ]

    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        # Stessa canonicalizzazione IN QUERY di `pattern_ricorrenti` (il
        # confronto è sull'array ORDINATO alfabeticamente, non sull'array
        # grezzo così com'è arrivato dal segnale): un pattern esatto è
        # identificato dall'INSIEME dei temi, non dal loro ordine di arrivo.
        temi_canonici = sorted(temi)
        query = (
            "SELECT creato_il FROM traccia_luogo "
            "WHERE place_id = %(place_id)s "
            "AND (SELECT array_agg(t ORDER BY t) FROM unnest(temi) AS t) = %(temi_canonici)s "
            "ORDER BY creato_il"
        )
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, {"place_id": place_id, "temi_canonici": temi_canonici})
                    righe = list(cur.fetchall())
        except psycopg.Error as exc:
            raise TracciaStorageError(
                f"lettura fallita su traccia_luogo per pattern place_id={place_id!r}, "
                f"temi={temi_canonici!r}: {exc}"
            ) from exc
        return [riga["creato_il"] for riga in righe]


def _from_row(riga: dict[str, Any]) -> Traccia:
    return Traccia(
        id=riga["id"],
        segnale_id=riga["segnale_id"],
        place_id=riga["place_id"],
        temi=tuple(riga["temi"] or []),
        creato_il=riga["creato_il"],
    )
