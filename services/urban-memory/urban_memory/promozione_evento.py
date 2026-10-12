"""Scrittura del nodo `:Evento` alla PROMOZIONE di un pattern ricorrente
(Fase 3) — innescata SOLO da una decisione umana esplicita del Promotore
(`python -m urban_memory.curatela_pattern`), mai automatica.

Stesso pattern in tre livelli di `urban_memory.luogo_traccia_link`/
`urban_memory.graph_link`:

- `promozione_evento_cypher` è una funzione PURA: nessun driver, nessuna
  connessione, nessuna sessione. Produce solo `(query, params)`,
  deterministica e testabile in isolamento. La query eseguita è la sola
  versionata in `services/urban-memory/cypher/50_promozione_evento_write.
  cypher` (letta da file, non duplicata come stringa nel codice).
- `scrivi_evento_promosso` ESEGUE quella query contro un driver Neo4j vero
  (Aura `neo4j+s://` o locale `bolt://`, secondo lo schema in `NEO4J_URI`:
  nessun `if local/cloud`). Nei test si passa un driver/sessione finti
  (nessuna connessione reale in `tests/`).
- `Neo4jPromozioneWriter` possiede un driver Neo4j aperto UNA VOLTA (non a
  ogni scrittura) e lo riusa — comodo per il comando di curatela, che può
  promuovere più pattern nella stessa corsa.

`evento_id_per_pattern` produce un id DETERMINISTICO (derivato da
place_id+temi), non un uuid casuale: vedi il docstring del file `.cypher`
versionato per il perché (idempotenza della ripromozione — MERGE non
duplica mai il nodo).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ._env import neo4j_config_from_env

__all__ = [
    "PROMOZIONE_EVENTO_WRITE_QUERY_PATH",
    "evento_id_per_pattern",
    "promozione_evento_cypher",
    "PromozioneEventoError",
    "LuogoMancanteError",
    "RIPRISTINO_EVENTO_WRITE_QUERY_PATH",
    "ripristino_evento_cypher",
    "scrivi_evento_ripristinato",
    "scrivi_evento_promosso",
    "Neo4jPromozioneWriter",
]

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
PROMOZIONE_EVENTO_WRITE_QUERY_PATH = _CYPHER_DIR / "50_promozione_evento_write.cypher"
RIPRISTINO_EVENTO_WRITE_QUERY_PATH = _CYPHER_DIR / "51_ripristino_evento_write.cypher"


def evento_id_per_pattern(place_id: str, temi: tuple[str, ...] | list[str]) -> str:
    """Id DETERMINISTICO del `:Evento` per un pattern (place_id + insieme di
    temi — GIÀ canonico: chi chiama passa tipicamente
    `PatternCandidato.temi`, ordinato alfabeticamente da
    `traccia_repository.PatternAggregato`). NON un uuid casuale: così
    ripromuovere lo stesso pattern (nuove occorrenze, corsa futura del
    comando di curatela) aggiorna lo STESSO nodo `:Evento` invece di crearne
    uno duplicato — vedi il `.cypher` versionato."""
    return f"evento-{place_id}-{'-'.join(temi)}"


def promozione_evento_cypher(
    place_id: str,
    evento_id: str,
    temi: tuple[str, ...] | list[str],
    cadenza_giorni: float,
    promotore: str,
    promosso_il: datetime,
) -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `50_promozione_evento_write.cypher`:
    produce `MATCH (l:Luogo {id: $place_id})` seguito da
    `MERGE (e:Evento {id: $evento_id})` (con `ON CREATE`/`ON MATCH`
    distinti — vedi il `.cypher` versionato: `promosso_da`/`promosso_il`
    sono scritti SOLO alla prima creazione, una ripromozione registra
    separatamente `ultimo_ricalcolo_da`/`ultimo_ricalcolo_il`) e
    `MERGE (e)-[:SI_SVOLGE_A]->(l)`.

    `promotore` è uno PSEUDONIMO (mai PII, stesso trattamento di
    `pattern_cestinato.promotore`): l'accountability persistente
    dell'atto che scrive struttura PERMANENTE e PUBBLICA nel grafo — a
    differenza di un log applicativo, non garantito persistente né
    interrogabile mesi dopo.

    Pura: non apre connessioni, non esegue nulla, non ha effetti collaterali
    oltre alla lettura (statica, non parametrica) del file `.cypher`
    versionato. Restituisce solo `(query, params)`. `promosso_il` è
    serializzato come ISO 8601 (`.isoformat()`) — stesso pattern di
    `graph_link.riguarda_to_cypher` per `creato_il`."""
    query = PROMOZIONE_EVENTO_WRITE_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {
        "place_id": place_id,
        "evento_id": evento_id,
        "temi": list(temi),
        "cadenza_giorni": cadenza_giorni,
        "promotore": promotore,
        "promosso_il": promosso_il.isoformat(),
    }
    return query, params


class PromozioneEventoError(Exception):
    """La promozione non è avvenuta — NESSUN nodo `:Evento` è stato creato
    o aggiornato. Due cause, ENTRAMBE arrivano come questo stesso tipo:

    - `$place_id` non esiste (ancora, o più) come `:Luogo`: la query è un
      `MATCH` (mai un `MERGE`) sul luogo, quindi zero righe restituite —
      sollevata esplicitamente da `scrivi_evento_promosso`, mai un successo
      silenzioso (mai un `:Luogo` fantasma creato per compensare);
    - il grafo è IRRAGGIUNGIBILE (Aura in pausa, rete assente, credenziali
      non valide): l'eccezione nativa del driver Neo4j è ri-sollevata come
      questo stesso tipo (incatenata con `from`, la causa originale resta
      ispezionabile).
    """


class LuogoMancanteError(PromozioneEventoError):
    """Sottotipo di `PromozioneEventoError`: il `:Luogo` di ancoraggio NON
    esiste nel grafo (il grafo risponde, il luogo manca). Distinto dal
    "grafo irraggiungibile" perché ha rimedio diverso (ricaricare il seed:
    `python -m graph.loader`) — usato dal ripristino per il report."""


class _Result(Protocol):
    def single(self) -> Any: ...


class _Session(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc_info: object) -> None: ...


class _Driver(Protocol):
    def session(self, database: str | None = None) -> _Session: ...

    def close(self) -> None: ...


def ripristino_evento_cypher(
    place_id: str,
    evento_id: str,
    temi: tuple[str, ...] | list[str],
    cadenza_giorni: float,
    promotore: str,
    promosso_il: datetime,
    ultimo_ricalcolo_da: str | None,
    ultimo_ricalcolo_il: datetime | None,
    frenato: bool,
) -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `51_ripristino_evento_write.cypher` (stato
    finale di un `:Evento` ricostruito dal ledger `pattern_promosso`)."""
    query = RIPRISTINO_EVENTO_WRITE_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {
        "place_id": place_id,
        "evento_id": evento_id,
        "temi": list(temi),
        "cadenza_giorni": cadenza_giorni,
        "promotore": promotore,
        "promosso_il": promosso_il.isoformat(),
        "ultimo_ricalcolo_da": ultimo_ricalcolo_da,
        "ultimo_ricalcolo_il": (
            ultimo_ricalcolo_il.isoformat() if ultimo_ricalcolo_il is not None else None
        ),
        "frenato": frenato,
    }
    return query, params


def scrivi_evento_ripristinato(
    place_id: str,
    evento_id: str,
    temi: tuple[str, ...] | list[str],
    cadenza_giorni: float,
    promotore: str,
    promosso_il: datetime,
    ultimo_ricalcolo_da: str | None,
    ultimo_ricalcolo_il: datetime | None,
    frenato: bool,
    *,
    driver: _Driver,
    database: str | None = None,
) -> str:
    """Proietta nel grafo un `:Evento` dal ledger (idempotente). Solleva
    `LuogoMancanteError` se il `:Luogo` non esiste, `PromozioneEventoError`
    se il grafo è irraggiungibile. Mai un `:Luogo` fantasma."""
    query, params = ripristino_evento_cypher(
        place_id,
        evento_id,
        temi,
        cadenza_giorni,
        promotore,
        promosso_il,
        ultimo_ricalcolo_da,
        ultimo_ricalcolo_il,
        frenato,
    )
    try:
        with driver.session(database=database or "neo4j") as session:
            risultato = session.run(query, params).single()
    except Exception as exc:
        raise PromozioneEventoError(
            f"grafo irraggiungibile durante il ripristino (evento_id={evento_id!r}): {exc}"
        ) from exc
    if risultato is None:
        raise LuogoMancanteError(
            f":Luogo con id={place_id!r} non esiste nel grafo: :Evento {evento_id!r} "
            "NON ripristinato (ricarica prima il seed: python -m graph.loader)."
        )
    return str(risultato["evento_id"])


def scrivi_evento_promosso(
    place_id: str,
    evento_id: str,
    temi: tuple[str, ...] | list[str],
    cadenza_giorni: float,
    promotore: str,
    *,
    promosso_il: datetime | None = None,
    driver: _Driver | None = None,
    database: str | None = None,
    dotenv_path: Path | None = None,
) -> str:
    """Crea/aggiorna il nodo `:Evento` per il pattern (place_id, temi,
    cadenza_giorni), lo ancora al `:Luogo` esistente
    (`(:Evento)-[:SI_SVOLGE_A]->(:Luogo)`) e registra `promotore` (uno
    pseudonimo, MAI PII) come autore della decisione — `promosso_da` alla
    prima creazione, `ultimo_ricalcolo_da` a una ripromozione (vedi il
    `.cypher` versionato). Ritorna `evento_id`.

    Solleva `PromozioneEventoError` (NESSUN nodo creato/aggiornato) se
    `place_id` non esiste nel grafo (zero righe dal `MATCH`) o se il grafo è
    irraggiungibile.

    `driver`/`database`/`dotenv_path`: stesso pattern di
    `luogo_traccia_link.scrivi_ultima_traccia`. Se `driver` non è passato,
    ne apre uno da `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
    `NEO4J_DATABASE` (dal `.env`, mai hardcoded) e lo chiude a fine
    chiamata. Se `driver` è passato (un driver FINTO nei test, o uno già
    aperto e condiviso — vedi `Neo4jPromozioneWriter`), il ciclo di vita
    resta di chi lo possiede.
    """
    promosso_il = promosso_il or datetime.now(UTC)

    driver_aperto_qui = driver is None
    if driver is None:
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        database = database or cfg.database
    database = database or "neo4j"

    query, params = promozione_evento_cypher(
        place_id, evento_id, temi, cadenza_giorni, promotore, promosso_il
    )
    try:
        with driver.session(database=database) as session:
            risultato = session.run(query, params).single()
    except PromozioneEventoError:
        raise  # già il tipo giusto: non ri-avvolgere
    except Exception as exc:
        raise PromozioneEventoError(
            f"grafo irraggiungibile durante la promozione (place_id={place_id!r}): {exc}"
        ) from exc
    finally:
        if driver_aperto_qui:
            driver.close()

    if risultato is None:
        raise LuogoMancanteError(
            f":Luogo con id={place_id!r} non esiste nel grafo: nodo :Evento "
            "NON creato/aggiornato — nessun :Luogo fantasma."
        )
    return str(risultato["evento_id"])


class Neo4jPromozioneWriter:
    """Wrapper comodo attorno a `scrivi_evento_promosso`: possiede un driver
    Neo4j aperto UNA VOLTA (non a ogni scrittura) e lo riusa — stesso
    pattern di `luogo_traccia_link.Neo4jLuogoTracciaLinker`. Usato dal
    comando di curatela (`urban_memory.curatela_pattern`), una sola istanza
    per l'intera corsa (può promuovere più pattern)."""

    def __init__(self, driver: _Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Neo4jPromozioneWriter:
        """Costruisce leggendo `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
        `NEO4J_DATABASE` dal `.env` (radice del repo) o dall'ambiente di
        processo."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        return cls(driver, database=cfg.database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jPromozioneWriter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def promuovi(
        self,
        place_id: str,
        temi: tuple[str, ...] | list[str],
        cadenza_giorni: float,
        promotore: str,
        promosso_il: datetime | None = None,
    ) -> str:
        """Promuove il pattern (place_id, temi) a `:Evento` con
        `cadenza_giorni`, registrando `promotore` (pseudonimo, MAI PII)
        come autore della decisione, riusando il driver posseduto da
        questa istanza. Ritorna `evento_id` (deterministico,
        `evento_id_per_pattern`). Firma pensata per essere passata
        direttamente come `writer` a
        `urban_memory.curatela_pattern.promuovi_pattern` (metodo legato)."""
        evento_id = evento_id_per_pattern(place_id, temi)
        return scrivi_evento_promosso(
            place_id,
            evento_id,
            temi,
            cadenza_giorni,
            promotore,
            promosso_il=promosso_il,
            driver=self._driver,
            database=self._database,
        )

    def ripristina(
        self,
        place_id: str,
        evento_id: str,
        temi: tuple[str, ...] | list[str],
        cadenza_giorni: float,
        promotore: str,
        promosso_il: datetime,
        ultimo_ricalcolo_da: str | None,
        ultimo_ricalcolo_il: datetime | None,
        frenato: bool,
    ) -> str:
        """Proiezione idempotente di un evento dal ledger (vedi
        `scrivi_evento_ripristinato`), riusando il driver posseduto."""
        return scrivi_evento_ripristinato(
            place_id,
            evento_id,
            temi,
            cadenza_giorni,
            promotore,
            promosso_il,
            ultimo_ricalcolo_da,
            ultimo_ricalcolo_il,
            frenato,
            driver=self._driver,
            database=self._database,
        )

    def luogo_esiste(self, place_id: str) -> bool:
        """`True` se un `:Luogo` con questo id esiste nel grafo — sola
        lettura. Usato da `curatela_pattern.promuovi_pattern` PRIMA di
        scrivere il ledger (mai registrare promozioni su un luogo
        inesistente). Solleva `PromozioneEventoError` se il grafo è
        irraggiungibile (nulla è stato scritto: il pattern resta candidato)."""
        query = "MATCH (l:Luogo {id: $place_id}) RETURN l.id AS id"
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(query, {"place_id": place_id}).single()
        except Exception as exc:
            raise PromozioneEventoError(
                f"grafo irraggiungibile durante la verifica del luogo "
                f"(place_id={place_id!r}): {exc}"
            ) from exc
        return record is not None

    def esiste(self, evento_id: str) -> bool:
        """`True` se un `:Evento` con questo id esiste GIÀ nel grafo — sola
        lettura, nessuna transazione gestita (non serve: non scrive nulla).

        Usato da `urban_memory.ricorrenza.rileva_candidati` (parametro
        `evento_esistente`) per escludere dai candidati un pattern GIÀ
        promosso: senza questo controllo, ripresentarlo esporrebbe il
        Promotore al rischio di RIFIUTARLO (cestino PERMANENTE) mentre
        l'`:Evento` corrispondente resta pubblico e attivo nel grafo — una
        divergenza cestino/grafo che nessun meccanismo riconcilierebbe più
        (a differenza di `urban_memory.audit` per `MemoryContribution`).

        Solleva `PromozioneEventoError` se il grafo è IRRAGGIUNGIBILE (Aura
        in pausa — scenario NORMALE secondo CLAUDE.md, non eccezionale —
        rete assente, credenziali non valide): STESSA famiglia di eccezione
        di `scrivi_evento_promosso` (non una nuova, dedicata alla sola
        lettura) perché per chi chiama (`ricorrenza.rileva_candidati`,
        `curatela_pattern.main`) "il grafo non risponde" è un'unica causa
        di fallimento del rilevamento, a prescindere che la query fosse una
        lettura o una scrittura — una sola famiglia di eccezioni da gestire,
        stesso principio di `graph_link.MemoryLinkError`. Senza questo
        try/except, un'eccezione nativa del driver (es.
        `neo4j.exceptions.ServiceUnavailable`) risalirebbe grezza fino a
        `curatela_pattern.main`, un crash invece di un'uscita pulita."""
        query = "MATCH (e:Evento {id: $evento_id}) RETURN e.id AS evento_id"
        try:
            with self._driver.session(database=self._database) as session:
                record = session.run(query, {"evento_id": evento_id}).single()
        except Exception as exc:
            raise PromozioneEventoError(
                f"grafo irraggiungibile durante la verifica di esistenza "
                f"(evento_id={evento_id!r}): {exc}"
            ) from exc
        return record is not None
