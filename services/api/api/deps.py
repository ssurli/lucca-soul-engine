"""Dipendenze del BFF: selezione della fonte dei candidati del grafo e del
repository di Urban Memory.

Il codice non sa MAI se `NEO4J_URI` punta ad Aura (`neo4j+s://`) o a Neo4j
Community locale (`bolt://`): legge solo se le credenziali sono presenti nel
`.env`. Se configurate, usa `Neo4jCandidateSource`; altrimenti ricade sul
seed versionato (`SeedCandidateSource`) — lo stesso dataset canonico, mai un
dataset diverso a seconda del profilo (cloud/locale).

L'istanza è creata una sola volta (`lru_cache`): aprire un driver Neo4j a
ogni richiesta sarebbe costoso e inutile. Stesso pattern per
`get_memory_repository` (Urban Memory, Wave 2), `get_booking_repository`
(Marketplace, Wave 3a) e — Fase 3, il canale fluttuante persistente
(`docs/PROMOZIONE_TRACCIA.md`) — `get_segnale_repository`/
`get_traccia_repository`/`get_place_link_writer`.
"""

from __future__ import annotations

from functools import lru_cache

import marketplace
import recommender
from graph.source import CandidateSource, Neo4jCandidateSource, SeedCandidateSource
from urban_memory import (
    InMemoryMemoryRepository,
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
    MemoryRepository,
    MemoryStorageError,
    Neo4jLuogoTracciaLinker,
    PlaceLinkWriter,
    PostgresMemoryRepository,
    PostgresSegnaleFluttuanteRepository,
    PostgresTracciaRepository,
    SegnaleFluttuanteRepository,
    SegnaleStorageError,
    TracciaRepository,
    TracciaStorageError,
)

from api.settings import get_settings

__all__ = [
    "get_candidate_source",
    "get_memory_repository",
    "get_booking_repository",
    "get_event_repository",
    "get_segnale_repository",
    "get_traccia_repository",
    "get_place_link_writer",
]


@lru_cache
def get_candidate_source() -> CandidateSource:
    """Sceglie la fonte dei candidati in base al `.env`, una volta sola.

    `Neo4jCandidateSource` richiede URI + username + password; se anche solo
    una delle tre manca, il BFF non tenta la connessione e ricade sul seed
    (evita di rompere l'avvio quando la configurazione è parziale).
    """
    settings = get_settings()
    if settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password:
        return Neo4jCandidateSource.from_credentials(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database or "neo4j",
        )
    return SeedCandidateSource()


@lru_cache
def get_memory_repository() -> MemoryRepository:
    """Sceglie il repository di Urban Memory in base al `.env`, una volta
    sola — stesso pattern di `get_candidate_source`: nessun `if
    local/cloud`, solo presenza di `DATABASE_URL`.

    Se `DATABASE_URL` è configurato usa `PostgresMemoryRepository` (Neon in
    cloud o Postgres locale — stesso codice nei due profili, cambia solo il
    DSN): persiste DAVVERO, con connessione lazy per operazione (nessun
    tentativo di rete qui, all'istanziazione — va bene costruirla anche a
    database non ancora raggiungibile o migrazione non ancora applicata: il
    fallimento emerge alla prima operazione reale su `/memory`, non qui).
    Altrimenti ricade su `InMemoryMemoryRepository` (in-process, non
    persiste tra riavvii — è il percorso verificato dallo smoke test di
    questo servizio quando `DATABASE_URL` non è impostato).

    Ogni errore infrastrutturale di storage (connessione, credenziali,
    query fallita) è responsabilità esclusiva di
    `urban_memory.repository.PostgresMemoryRepository`, che lo mappa già in
    `MemoryStorageError` — mai lasciato propagare come eccezione psycopg
    grezza. Questa funzione non implementa NESSUNA logica di database: si
    limita ad avvolgere in `MemoryStorageError` anche un eventuale
    fallimento della sola costruzione (`from_env()`, che legge
    `DATABASE_URL` e può sollevare `ValueError` se la variabile risulta
    assente qui pur essendo vista come presente da `api.settings.Settings`
    — stesso `.env`, letture indipendenti), così che
    `api.main.memory_storage_error_handler` (503, mai un 500 opaco) catturi
    ANCHE questo caso, non solo i fallimenti nelle operazioni successive.
    """
    settings = get_settings()
    if settings.database_url:
        try:
            return PostgresMemoryRepository.from_env()
        except MemoryStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise MemoryStorageError(
                "impossibile inizializzare la persistenza di Urban Memory"
            ) from exc
    return InMemoryMemoryRepository()


@lru_cache
def get_booking_repository() -> marketplace.BookingRepository:
    """Sceglie il repository del Marketplace in base al `.env`, una volta
    sola — stesso pattern di `get_memory_repository` (Wave 2): nessun `if
    local/cloud`, solo presenza di `DATABASE_URL`.

    Se `DATABASE_URL` è configurato usa `marketplace.PostgresBookingRepository`
    (Neon in cloud o Postgres locale — stesso codice nei due profili, cambia
    solo il DSN): persiste DAVVERO, con connessione lazy per operazione.
    Altrimenti ricade su `marketplace.InMemoryBookingRepository` (in-process,
    non persiste tra riavvii — il percorso verificato dai test di questo
    servizio quando `DATABASE_URL` non è impostato).

    Ogni errore infrastrutturale di storage (connessione, credenziali, query
    fallita) è responsabilità esclusiva di
    `marketplace.repository.PostgresBookingRepository`, che lo mappa già in
    `MarketplaceStorageError` — mai lasciato propagare come eccezione psycopg
    grezza. Questa funzione non implementa NESSUNA logica di database: si
    limita ad avvolgere in `MarketplaceStorageError` anche un eventuale
    fallimento della sola costruzione (`from_env()`, che legge `DATABASE_URL`
    e può sollevare `ValueError` se la variabile risulta assente qui pur
    essendo vista come presente da `api.settings.Settings` — stesso `.env`,
    letture indipendenti), così che un handler analogo a
    `api.main.memory_storage_error_handler` (503, mai un 500 opaco) catturi
    ANCHE questo caso, non solo i fallimenti nelle operazioni successive.
    """
    settings = get_settings()
    if settings.database_url:
        try:
            return marketplace.PostgresBookingRepository.from_env()
        except marketplace.MarketplaceStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise marketplace.MarketplaceStorageError(
                "impossibile inizializzare la persistenza del Marketplace"
            ) from exc
    return marketplace.InMemoryBookingRepository()


@lru_cache
def get_event_repository() -> recommender.BehaviorEventRepository:
    """Sceglie il repository degli eventi comportamentali (Recommender, Wave
    3b) in base al `.env`, una volta sola — stesso pattern di
    `get_memory_repository`/`get_booking_repository`: nessun `if
    local/cloud`, solo presenza di `DATABASE_URL`.

    Se `DATABASE_URL` è configurato usa `recommender.PostgresBehaviorEventRepository`
    (Neon in cloud o Postgres locale — stesso codice nei due profili, cambia
    solo il DSN): persiste DAVVERO, con connessione lazy per operazione.
    Altrimenti ricade su `recommender.InMemoryBehaviorEventRepository`
    (in-process, non persiste tra riavvii — il percorso verificato dai test
    di questo servizio quando `DATABASE_URL` non è impostato, e quello di
    cold start: repository vuoto, `costruisci_score_fn` produce un
    punteggio bit-identico a `calcola_score` da solo).

    Ogni errore infrastrutturale di storage (connessione, credenziali, query
    fallita) è responsabilità esclusiva di
    `recommender.repository.PostgresBehaviorEventRepository`, che lo mappa
    già in `RecommenderStorageError` — mai lasciato propagare come
    eccezione psycopg grezza. Questa funzione non implementa NESSUNA logica
    di database: si limita ad avvolgere in `RecommenderStorageError` anche
    un eventuale fallimento della sola costruzione (`from_env()`, che legge
    `DATABASE_URL` e può sollevare `ValueError` se la variabile risulta
    assente qui pur essendo vista come presente da `api.settings.Settings`
    — stesso `.env`, letture indipendenti), così che
    `api.main.event_storage_error_handler` (503 su `POST /events`, mai un
    500 opaco) catturi ANCHE questo caso, non solo i fallimenti nelle
    operazioni successive.

    NOTA — a differenza di `/memory` e `/booking`, questo repository è
    iniettato ANCHE nel wiring di `POST /itinerary` (`api.main.create_itinerary`),
    dove un suo fallimento (qui o nella lettura dello storico da
    `recommender.costruisci_score_fn`) NON deve mai propagare: lo storico
    comportamentale è un arricchimento opzionale del ranking, non il cuore
    della richiesta — vedi il commento in `create_itinerary`."""
    settings = get_settings()
    if settings.database_url:
        try:
            return recommender.PostgresBehaviorEventRepository.from_env()
        except recommender.RecommenderStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise recommender.RecommenderStorageError(
                "impossibile inizializzare la persistenza degli eventi comportamentali"
            ) from exc
    return recommender.InMemoryBehaviorEventRepository()


# ---------------------------------------------------------------------------
# Canale fluttuante persistente (Fase 3, docs/PROMOZIONE_TRACCIA.md) —
# stesso pattern di get_memory_repository/get_booking_repository/
# get_event_repository sopra: nessun `if local/cloud`, solo presenza di
# DATABASE_URL (per le due tabelle Postgres) / delle tre credenziali Neo4j
# (per la proprietà derivata `ultima_traccia_il`).
# ---------------------------------------------------------------------------


@lru_cache
def get_segnale_repository() -> SegnaleFluttuanteRepository:
    """Sceglie il repository della tabella-segnale in base al `.env`, una
    volta sola — stesso pattern di `get_memory_repository`.

    Se `DATABASE_URL` è configurato usa `PostgresSegnaleFluttuanteRepository`
    (Neon in cloud o Postgres locale): persiste DAVVERO, con connessione lazy
    per operazione. Altrimenti ricade su
    `InMemorySegnaleFluttuanteRepository` (in-process, non persiste tra
    riavvii — il percorso usato dai test e dallo smoke test di questo
    servizio quando `DATABASE_URL` non è impostato).

    NOTA — a differenza di `/memory`/`/booking`/`/events`, questo repository
    è iniettato SOLO nel wiring di `POST /itinerary`
    (`api.main.create_itinerary`), dove il canale fluttuante è un
    arricchimento OPZIONALE della composizione: un suo fallimento (qui o
    nelle operazioni successive di `urban_memory.canale_fluttuante.
    sweep_and_fetch_active`) NON deve mai propagare — è per questo che
    questa funzione è chiamata DIRETTAMENTE dentro il `try` di
    `create_itinerary`, mai tramite `Depends` nella firma (stesso motivo,
    stessa tecnica, di `get_event_repository` — vedi il commento in
    `create_itinerary`)."""
    settings = get_settings()
    if settings.database_url:
        try:
            return PostgresSegnaleFluttuanteRepository.from_env()
        except SegnaleStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise SegnaleStorageError(
                "impossibile inizializzare la persistenza del canale fluttuante"
            ) from exc
    return InMemorySegnaleFluttuanteRepository()


@lru_cache
def get_traccia_repository() -> TracciaRepository:
    """Sceglie il repository del ledger delle tracce in base al `.env`, una
    volta sola — stesso pattern di `get_segnale_repository`, stessa NOTA
    sull'iniezione diretta (mai `Depends`) in `create_itinerary`."""
    settings = get_settings()
    if settings.database_url:
        try:
            return PostgresTracciaRepository.from_env()
        except TracciaStorageError:
            raise
        except Exception as exc:  # difesa in profondità: mai un errore grezzo
            raise TracciaStorageError(
                "impossibile inizializzare la persistenza del ledger delle tracce"
            ) from exc
    return InMemoryTracciaRepository()


@lru_cache
def get_place_link_writer() -> PlaceLinkWriter | None:
    """Scrittore della proprietà derivata `:Luogo.ultima_traccia_il` sul
    Knowledge Graph — `None` se `NEO4J_URI`/`NEO4J_USERNAME`/
    `NEO4J_PASSWORD` non sono TUTTE presenti (stesso pattern di
    `get_candidate_source`: senza credenziali complete non si tenta la
    connessione; `sweep_and_fetch_active` tratta `place_link_writer=None`
    come "nessuna scrittura nel grafo", mai un errore).

    Un solo driver Neo4j, aperto una volta per l'intero ciclo di vita del
    processo (`Neo4jLuogoTracciaLinker`, stesso pattern di
    `Neo4jCandidateSource` sopra), riusato per ogni richiesta — mai un
    driver per richiesta. Il metodo legato `.scrivi` è esattamente la firma
    richiesta da `urban_memory.canale_fluttuante.PlaceLinkWriter`."""
    settings = get_settings()
    if settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password:
        linker = Neo4jLuogoTracciaLinker.from_credentials(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database or "neo4j",
        )
        return linker.scrivi
    return None
