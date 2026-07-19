"""Test di `recommender.repository` e `recommender.features`.

`InMemoryBehaviorEventRepository` è il percorso di default (usato nei test e
finché `DATABASE_URL` non è configurato). `PostgresBehaviorEventRepository` è
testata contro un Postgres 16 EFFIMERO vero (vedi `tests/conftest.py`) — non
un mock: ingestion, aggregazione pesata, migrazione idempotente, il `CHECK`
del DB sul `tipo`, e che gli eventi sopravvivono alla chiusura e riapertura
della connessione.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest
from contracts import BehaviorEvent
from recommender import BehaviorEventRepository, InMemoryBehaviorEventRepository
from recommender.features import PESI_TIPO, conteggio_pesato_per_esperienza, pesare_conteggi_grezzi
from recommender.migrate import migrate
from recommender.repository import PostgresBehaviorEventRepository, RecommenderStorageError


def _evento(**overrides: object) -> BehaviorEvent:
    defaults: dict[str, object] = {
        "person_id": "turista-pseudonimo-1",
        "tipo": "view",
        "experience_id": "esperienza-1",
        "ts": datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return BehaviorEvent(**defaults)


# --- features: pesatura ------------------------------------------------------


def test_tutti_i_tipi_del_contratto_hanno_un_peso_documentato() -> None:
    """`PESI_TIPO` deve coprire ESATTAMENTE i valori del `Literal` di
    `BehaviorEvent.tipo` (docs/DATA_CONTRACTS.md §6): nessuno dimenticato,
    nessuno in più."""
    tipi_contratto = {"view", "stop", "photo", "booking", "review", "skip", "memory_contrib"}
    assert set(PESI_TIPO.keys()) == tipi_contratto


def test_skip_pesa_zero() -> None:
    """Un rifiuto esplicito non deve mai contribuire alla concentrazione."""
    assert PESI_TIPO["skip"] == 0.0


def test_nessun_peso_e_negativo() -> None:
    assert all(peso >= 0.0 for peso in PESI_TIPO.values())


def test_conteggio_pesato_aggrega_per_esperienza() -> None:
    eventi = [
        _evento(experience_id="exp-a", tipo="view"),
        _evento(experience_id="exp-a", tipo="stop"),
        _evento(experience_id="exp-b", tipo="skip"),
    ]
    conteggio = conteggio_pesato_per_esperienza(eventi)
    assert conteggio["exp-a"] == PESI_TIPO["view"] + PESI_TIPO["stop"]
    # "skip" pesa zero: la chiave può comparire ma con valore 0, mai negativa.
    assert conteggio.get("exp-b", 0.0) == 0.0


def test_conteggio_pesato_senza_eventi_e_vuoto() -> None:
    assert conteggio_pesato_per_esperienza([]) == {}


def test_pesare_conteggi_grezzi_equivale_alla_versione_in_memory() -> None:
    """La pesatura di righe grezze `(tipo, experience_id, n)` (il formato che
    arriva da un `GROUP BY` Postgres) deve produrre lo STESSO risultato della
    pesatura evento-per-evento in memoria: nessuna logica duplicata/divergente."""
    eventi = [
        _evento(experience_id="exp-a", tipo="view"),
        _evento(experience_id="exp-a", tipo="view"),
        _evento(experience_id="exp-a", tipo="booking"),
        _evento(experience_id="exp-b", tipo="photo"),
    ]
    atteso = conteggio_pesato_per_esperienza(eventi)
    righe_grezze = [("view", "exp-a", 2), ("booking", "exp-a", 1), ("photo", "exp-b", 1)]
    assert pesare_conteggi_grezzi(righe_grezze) == atteso


# --- InMemoryBehaviorEventRepository -----------------------------------------


def test_in_memory_repository_implementa_il_protocollo() -> None:
    repo: BehaviorEventRepository = InMemoryBehaviorEventRepository()
    assert hasattr(repo, "record")
    assert hasattr(repo, "conteggio_per_esperienza")


def test_in_memory_record_e_conteggio() -> None:
    repo = InMemoryBehaviorEventRepository()
    assert repo.conteggio_per_esperienza() == {}

    repo.record(_evento(experience_id="exp-a", tipo="stop"))
    repo.record(_evento(experience_id="exp-a", tipo="stop"))
    repo.record(_evento(experience_id="exp-b", tipo="view"))

    conteggio = repo.conteggio_per_esperienza()
    assert conteggio["exp-a"] == 2 * PESI_TIPO["stop"]
    assert conteggio["exp-b"] == PESI_TIPO["view"]


def test_in_memory_conteggio_non_espone_person_id() -> None:
    """Aggregato e anonimo: il dizionario risultante è raggruppato SOLO per
    `experience_id`, nessuna traccia di `person_id`."""
    repo = InMemoryBehaviorEventRepository()
    repo.record(_evento(person_id="turista-molto-specifico", experience_id="exp-a"))
    conteggio = repo.conteggio_per_esperienza()
    for chiave in conteggio:
        assert "turista" not in chiave


# --- PostgresBehaviorEventRepository: interfaccia e costruzione -------------


def test_postgres_repository_ha_linterfaccia_attesa() -> None:
    repo = PostgresBehaviorEventRepository(dsn="postgresql://esplicito/db")
    assert hasattr(repo, "record")
    assert hasattr(repo, "conteggio_per_esperienza")


def test_postgres_repository_dsn_arriva_sempre_dal_costruttore() -> None:
    repo = PostgresBehaviorEventRepository(dsn="postgresql://esplicito/db")
    assert repo._dsn == "postgresql://esplicito/db"


def test_postgres_repository_from_env_richiede_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv_vuoto = tmp_path / ".env"
    dotenv_vuoto.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        PostgresBehaviorEventRepository.from_env(dotenv_path=dotenv_vuoto)


def test_postgres_repository_from_env_legge_il_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('DATABASE_URL="postgresql://letto-dal-file/db"\n', encoding="utf-8")
    repo = PostgresBehaviorEventRepository.from_env(dotenv_path=dotenv)
    assert repo._dsn == "postgresql://letto-dal-file/db"


def test_postgres_get_con_connessione_non_raggiungibile_solleva_recommender_storage_error() -> None:
    repo = PostgresBehaviorEventRepository(dsn="postgresql://postgres@127.0.0.1:1/inesistente")
    with pytest.raises(RecommenderStorageError):
        repo.conteggio_per_esperienza()


# --- PostgresBehaviorEventRepository: persistenza reale (Postgres effimero) -


def test_migrate_e_idempotente(pg_dsn: str) -> None:
    migrate(pg_dsn)
    migrate(pg_dsn)  # seconda corsa: deve essere un no-op, non un errore


def test_postgres_record_poi_conteggio(pg_repo: PostgresBehaviorEventRepository) -> None:
    pg_repo.record(_evento(experience_id="exp-pg-1", tipo="stop"))
    pg_repo.record(_evento(experience_id="exp-pg-1", tipo="stop"))
    pg_repo.record(_evento(experience_id="exp-pg-2", tipo="view"))

    conteggio = pg_repo.conteggio_per_esperienza()
    assert conteggio["exp-pg-1"] == 2 * PESI_TIPO["stop"]
    assert conteggio["exp-pg-2"] == PESI_TIPO["view"]


def test_postgres_persistenza_sopravvive_a_una_nuova_connessione(pg_dsn: str) -> None:
    migrate(pg_dsn)

    scrittore = PostgresBehaviorEventRepository(pg_dsn)
    scrittore.record(_evento(experience_id="exp-persist-1", tipo="booking"))
    del scrittore  # nessuna connessione persistente da chiudere: per-operazione

    lettore = PostgresBehaviorEventRepository(pg_dsn)  # istanza NUOVA, stesso DSN
    conteggio = lettore.conteggio_per_esperienza()
    assert conteggio["exp-persist-1"] == PESI_TIPO["booking"]


def test_check_db_rifiuta_tipo_non_valido(pg_dsn: str) -> None:
    """Difesa in profondità: ANCHE un INSERT diretto (che scavalca
    `recommender.repository`) è rifiutato dal `CHECK` a livello DB."""
    migrate(pg_dsn)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                "INSERT INTO behavior_event (person_id, tipo, experience_id, ts) "
                "VALUES (%s, %s, %s, %s)",
                (
                    "pseudonimo",
                    "click",  # <- non è un tipo valido del contratto
                    "esperienza",
                    datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
                ),
            )


def test_postgres_id_e_ricevuto_il_sono_gestiti_dal_db(pg_dsn: str) -> None:
    """`BehaviorEvent` non ha `id`: verifica che lo schema lo generi da sé
    (surrogato) insieme a `ricevuto_il` (default `now()`), senza che
    `record()` debba fornirli."""
    migrate(pg_dsn)
    repo = PostgresBehaviorEventRepository(pg_dsn)
    repo.record(_evento(experience_id="exp-id-1"))
    with psycopg.connect(pg_dsn) as conn:
        riga = conn.execute(
            "SELECT id, ricevuto_il FROM behavior_event WHERE experience_id = %s",
            ("exp-id-1",),
        ).fetchone()
    assert riga is not None
    assert riga[0] is not None  # id surrogato generato dal DB
    assert riga[1] is not None  # ricevuto_il popolato dal default now()


# --- Protocol BehaviorEventRepository: stessi test, entrambe le implementazioni


def test_protocollo_record_e_conteggio_su_entrambe_le_implementazioni(
    any_behavior_event_repository: BehaviorEventRepository,
) -> None:
    repo = any_behavior_event_repository
    assert repo.conteggio_per_esperienza() == {}

    repo.record(_evento(experience_id="exp-protocollo-1", tipo="review"))
    repo.record(_evento(experience_id="exp-protocollo-1", tipo="review"))

    conteggio = repo.conteggio_per_esperienza()
    assert conteggio["exp-protocollo-1"] == 2 * PESI_TIPO["review"]
