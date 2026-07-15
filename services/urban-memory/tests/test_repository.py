"""Test di `urban_memory.repository`.

`InMemoryMemoryRepository` è il percorso di default (usato nei test e
finché `DATABASE_URL` non è configurato). `PostgresMemoryRepository` è
testata contro un Postgres 16 EFFIMERO vero (vedi `tests/conftest.py`:
`postgres_cluster`/`pg_dsn`/`pg_repo`) — non un mock: submit/get_curated/
list_pending/curate, la migrazione idempotente, i `CHECK` del DB a difesa
in profondità di consenso e licenza, e soprattutto che il contributo
sopravvive alla chiusura e riapertura della connessione (la persistenza che
il committente ha chiesto di dimostrare). Se Postgres 16 non è disponibile
in questo ambiente, quei test sono SALTATI (`pytest.skip`), non falliti.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import InMemoryMemoryRepository, MemoryRepository, PostgresMemoryRepository
from urban_memory.migrate import migrate
from urban_memory.repository import MemoryStorageError


def _contributo(**overrides: object) -> MemoryContribution:
    defaults: dict[str, object] = {
        "id": "mem-repo-1",
        "kind": MemoryKind.FOTOGRAFIA,
        "riguarda": ["luogo-1"],
        "contributor_id": "occhio-di-lucca",
        "contributor_kind": PersonKind.TURISTA,
        "consenso": True,
        "licenza": "CC-BY-4.0",
        "creato_il": datetime(2026, 7, 14, 8, 0),
        "curato": False,
    }
    defaults.update(overrides)
    return MemoryContribution(**defaults)


# --- InMemoryMemoryRepository implementa il Protocol ------------------------


def test_in_memory_repository_implementa_il_protocollo() -> None:
    repo: MemoryRepository = InMemoryMemoryRepository()
    assert hasattr(repo, "submit")
    assert hasattr(repo, "get_curated")
    assert hasattr(repo, "list_pending")
    assert hasattr(repo, "curate")
    assert hasattr(repo, "get")
    assert hasattr(repo, "list_curated")


def test_submit_ritorna_il_contributo_persistito() -> None:
    repo = InMemoryMemoryRepository()
    contributo = _contributo()
    persistito = repo.submit(contributo)
    assert persistito == contributo


def test_list_pending_contiene_solo_i_non_curati() -> None:
    repo = InMemoryMemoryRepository()
    repo.submit(_contributo(id="a", curato=False))
    repo.submit(_contributo(id="b", curato=True))
    assert [c.id for c in repo.list_pending()] == ["a"]


def test_curate_imposta_curato_true_e_lo_restituisce() -> None:
    repo = InMemoryMemoryRepository()
    repo.submit(_contributo(id="a", curato=False))

    aggiornato = repo.curate("a")

    assert aggiornato.curato is True
    assert repo.list_pending() == []


def test_curate_id_sconosciuto_solleva_keyerror() -> None:
    repo = InMemoryMemoryRepository()
    with pytest.raises(KeyError):
        repo.curate("non-esiste")


def test_get_curated_richiede_sia_curato_che_place_id() -> None:
    repo = InMemoryMemoryRepository()
    repo.submit(_contributo(id="a", riguarda=["luogo-1"], curato=True))
    repo.submit(_contributo(id="b", riguarda=["luogo-2"], curato=True))
    repo.submit(_contributo(id="c", riguarda=["luogo-1"], curato=False))

    assert [c.id for c in repo.get_curated("luogo-1")] == ["a"]


def test_get_curated_su_place_id_senza_contributi_e_vuoto() -> None:
    repo = InMemoryMemoryRepository()
    assert repo.get_curated("luogo-mai-visto") == []


def test_in_memory_get_restituisce_il_contributo_esistente() -> None:
    repo = InMemoryMemoryRepository()
    contributo = _contributo(id="mem-esiste")
    repo.submit(contributo)

    trovato = repo.get("mem-esiste")

    assert trovato == contributo


def test_in_memory_get_id_sconosciuto_restituisce_none() -> None:
    repo = InMemoryMemoryRepository()
    assert repo.get("non-esiste") is None


def test_in_memory_list_curated_contiene_solo_i_curati() -> None:
    repo = InMemoryMemoryRepository()
    repo.submit(_contributo(id="a", riguarda=["luogo-a"], curato=True))
    repo.submit(_contributo(id="b", riguarda=["luogo-b"], curato=True))
    repo.submit(_contributo(id="c", riguarda=["luogo-c"], curato=False))

    # A DIFFERENZA di get_curated(place_id): nessun filtro per place, TUTTI
    # i curati indipendentemente da dove riguardano — è ciò che serve
    # all'audit per scandagliare l'intero database, non un place alla volta.
    assert sorted(c.id for c in repo.list_curated()) == ["a", "b"]


def test_in_memory_get_riflette_lo_stato_curato_aggiornato() -> None:
    """`get` legge lo stato REALE, non uno stantio: dopo `curate`, rilegge
    `curato=True` — lo stesso principio che rende `urban_memory.verify`
    idempotente (rilegge sempre prima di assumere)."""
    repo = InMemoryMemoryRepository()
    repo.submit(_contributo(id="mem-curabile", curato=False))

    repo.curate("mem-curabile")

    assert repo.get("mem-curabile").curato is True  # type: ignore[union-attr]


# --- PostgresMemoryRepository: interfaccia e costruzione -------------------


def test_postgres_repository_ha_linterfaccia_attesa() -> None:
    repo = PostgresMemoryRepository(dsn="postgresql://esplicito/db")
    assert hasattr(repo, "submit")
    assert hasattr(repo, "get_curated")
    assert hasattr(repo, "list_pending")
    assert hasattr(repo, "curate")
    assert hasattr(repo, "get")
    assert hasattr(repo, "list_curated")


def test_postgres_repository_dsn_arriva_sempre_dal_costruttore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il DSN non viene mai letto implicitamente da `os.environ` dentro i
    metodi: costruirla direttamente con un DSN esplicito non deve dipendere
    da `DATABASE_URL` nell'ambiente (solo `from_env()` lo legge)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    repo = PostgresMemoryRepository(dsn="postgresql://esplicito/db")
    assert repo._dsn == "postgresql://esplicito/db"


def test_postgres_repository_from_env_richiede_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv_vuoto = tmp_path / ".env"
    dotenv_vuoto.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        PostgresMemoryRepository.from_env(dotenv_path=dotenv_vuoto)


def test_postgres_repository_from_env_legge_il_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('DATABASE_URL="postgresql://letto-dal-file/db"\n', encoding="utf-8")
    repo = PostgresMemoryRepository.from_env(dotenv_path=dotenv)
    assert repo._dsn == "postgresql://letto-dal-file/db"


# --- PostgresMemoryRepository: persistenza reale (Postgres 16 effimero) ----
#
# Tutti i test sotto dipendono (direttamente o via `pg_dsn`/`pg_repo`) dalla
# fixture `postgres_cluster` (tests/conftest.py): se questo ambiente non può
# avviare un Postgres 16 effimero, sono SALTATI, non falliti.


def test_migrate_e_idempotente(pg_dsn: str) -> None:
    """Rieseguita due volte sullo stesso DSN, `migrate` non solleva: `CREATE
    TABLE`/`INDEX ... IF NOT EXISTS`, nessun `DROP` (CLAUDE.md — rieseguibile
    da zero in un comando, come il seed del grafo)."""
    migrate(pg_dsn)
    migrate(pg_dsn)  # seconda corsa: deve essere un no-op, non un errore


def test_postgres_repository_implementa_il_protocollo(pg_repo: PostgresMemoryRepository) -> None:
    repo: MemoryRepository = pg_repo
    assert hasattr(repo, "submit")
    assert hasattr(repo, "get_curated")
    assert hasattr(repo, "list_pending")
    assert hasattr(repo, "curate")
    assert hasattr(repo, "get")
    assert hasattr(repo, "list_curated")


def test_postgres_submit_poi_get_curated_e_vuoto_finche_non_curato(
    pg_repo: PostgresMemoryRepository,
) -> None:
    contributo = _contributo(
        id="mem-pg-1",
        riguarda=["luogo-pg-1"],
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    persistito = pg_repo.submit(contributo)
    assert persistito.id == "mem-pg-1"
    assert persistito.curato is False
    assert pg_repo.get_curated("luogo-pg-1") == []  # non ancora curato


def test_postgres_curate_pubblica_il_contributo(pg_repo: PostgresMemoryRepository) -> None:
    contributo = _contributo(
        id="mem-pg-2",
        riguarda=["luogo-pg-2"],
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    pg_repo.submit(contributo)

    curato = pg_repo.curate("mem-pg-2")
    assert curato.curato is True

    pubblicati = pg_repo.get_curated("luogo-pg-2")
    assert [c.id for c in pubblicati] == ["mem-pg-2"]
    assert pubblicati[0].licenza == contributo.licenza
    assert pubblicati[0].kind == contributo.kind


def test_postgres_curate_id_sconosciuto_solleva_keyerror(pg_repo: PostgresMemoryRepository) -> None:
    with pytest.raises(KeyError):
        pg_repo.curate("non-esiste-su-postgres")


def test_postgres_get_curated_filtra_per_place_id_e_per_curato(
    pg_repo: PostgresMemoryRepository,
) -> None:
    creato_il = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    pg_repo.submit(_contributo(id="a", riguarda=["luogo-a"], creato_il=creato_il))
    pg_repo.submit(_contributo(id="b", riguarda=["luogo-b"], creato_il=creato_il))
    pg_repo.submit(_contributo(id="c", riguarda=["luogo-a"], creato_il=creato_il))
    pg_repo.curate("a")
    pg_repo.curate("b")
    # "c" resta non curato di proposito

    assert [c.id for c in pg_repo.get_curated("luogo-a")] == ["a"]


def test_postgres_list_pending_contiene_solo_i_non_curati(
    pg_repo: PostgresMemoryRepository,
) -> None:
    creato_il = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    pg_repo.submit(_contributo(id="p1", riguarda=["luogo-p"], creato_il=creato_il))
    pg_repo.submit(_contributo(id="p2", riguarda=["luogo-p"], creato_il=creato_il))
    pg_repo.curate("p2")

    assert [c.id for c in pg_repo.list_pending()] == ["p1"]


def test_postgres_list_curated_contiene_solo_i_curati(
    pg_repo: PostgresMemoryRepository,
) -> None:
    creato_il = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    pg_repo.submit(_contributo(id="c1", riguarda=["luogo-c1"], creato_il=creato_il))
    pg_repo.submit(_contributo(id="c2", riguarda=["luogo-c2"], creato_il=creato_il))
    pg_repo.submit(_contributo(id="c3", riguarda=["luogo-c1"], creato_il=creato_il))
    pg_repo.curate("c1")
    pg_repo.curate("c2")
    # "c3" resta non curato di proposito

    # A DIFFERENZA di get_curated(place_id): nessun filtro per place — è
    # ciò che serve a `urban_memory.audit` per scandagliare OGNI curato.
    assert sorted(c.id for c in pg_repo.list_curated()) == ["c1", "c2"]


def test_postgres_persistenza_sopravvive_a_una_nuova_connessione(pg_dsn: str) -> None:
    """IL CUORE DELLA RICHIESTA: dopo aver chiuso il repository "scrittore" e
    aperto un repository NUOVO sullo STESSO DSN (nessuno stato di
    connessione condiviso: simula un riavvio del processo), il contributo
    curato è ANCORA lì. È la differenza tra `PostgresMemoryRepository` e lo
    stub in-memory che si azzerava al riavvio."""
    migrate(pg_dsn)

    scrittore = PostgresMemoryRepository(pg_dsn)
    contributo = _contributo(
        id="mem-persist-1",
        riguarda=["luogo-persist"],
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    scrittore.submit(contributo)
    scrittore.curate("mem-persist-1")
    del scrittore  # nessuna connessione persistente da chiudere: per-operazione

    lettore = PostgresMemoryRepository(pg_dsn)  # istanza NUOVA, stesso DSN
    pubblicati = lettore.get_curated("luogo-persist")
    assert [c.id for c in pubblicati] == ["mem-persist-1"]
    assert pubblicati[0].curato is True

    # Una TERZA istanza (un altro "riavvio") continua a vederlo: non è un
    # comportamento di una singola riconnessione fortunata.
    ancora = PostgresMemoryRepository(pg_dsn)
    assert [c.id for c in ancora.get_curated("luogo-persist")] == ["mem-persist-1"]


def test_check_db_rifiuta_insert_diretto_senza_consenso(pg_dsn: str) -> None:
    """Difesa in profondità: ANCHE un INSERT diretto (che scavalca
    `urban_memory.service`) è rifiutato dal `CHECK` a livello DB — non solo
    dal servizio applicativo."""
    migrate(pg_dsn)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                "INSERT INTO memory_contribution "
                "(id, kind, riguarda, contributor_id, contributor_kind, "
                "consenso, licenza, creato_il, curato) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    "mem-senza-consenso-diretto",
                    "racconto",
                    ["luogo-x"],
                    "qualcuno",
                    "turista",
                    False,  # <- consenso=False: deve essere rifiutato dal CHECK
                    "CC-BY-4.0",
                    datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
                    False,
                ),
            )


def test_check_db_rifiuta_insert_diretto_con_licenza_vuota(pg_dsn: str) -> None:
    migrate(pg_dsn)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                "INSERT INTO memory_contribution "
                "(id, kind, riguarda, contributor_id, contributor_kind, "
                "consenso, licenza, creato_il, curato) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    "mem-senza-licenza-diretto",
                    "racconto",
                    ["luogo-x"],
                    "qualcuno",
                    "turista",
                    True,
                    "",  # <- licenza vuota: deve essere rifiutata dal CHECK
                    datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
                    False,
                ),
            )


def test_postgres_get_restituisce_il_contributo_esistente(
    pg_repo: PostgresMemoryRepository,
) -> None:
    contributo = _contributo(
        id="mem-pg-get-1",
        riguarda=["luogo-pg-get"],
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    pg_repo.submit(contributo)

    trovato = pg_repo.get("mem-pg-get-1")

    assert trovato is not None
    assert trovato.id == "mem-pg-get-1"
    assert trovato.riguarda == ["luogo-pg-get"]
    assert trovato.licenza == contributo.licenza
    assert trovato.curato is False  # get rilegge lo stato REALE, non curato


def test_postgres_get_id_sconosciuto_restituisce_none(pg_repo: PostgresMemoryRepository) -> None:
    assert pg_repo.get("mai-esistito-su-postgres") is None


def test_postgres_get_riflette_lo_stato_curato_aggiornato(
    pg_repo: PostgresMemoryRepository,
) -> None:
    """Come per `InMemoryMemoryRepository`: `get` legge lo stato REALE dal
    DB, mai una copia stantia — è ciò su cui si basa l'idempotenza onesta
    di `urban_memory.verify` (rilegge sempre prima di assumere)."""
    contributo = _contributo(
        id="mem-pg-get-curato",
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    pg_repo.submit(contributo)
    assert pg_repo.get("mem-pg-get-curato").curato is False  # type: ignore[union-attr]

    pg_repo.curate("mem-pg-get-curato")

    assert pg_repo.get("mem-pg-get-curato").curato is True  # type: ignore[union-attr]


def test_postgres_get_con_connessione_non_raggiungibile_solleva_memory_storage_error() -> None:
    """`get` mappa un errore psycopg (qui: connessione rifiutata, porta 1 su
    localhost non ha alcun listener) in `MemoryStorageError` — non lo lascia
    propagare come eccezione psycopg grezza, né lo confonde con `None`
    ("non trovato": un errore di storage NON è un "non esiste")."""
    repo = PostgresMemoryRepository(dsn="postgresql://postgres@127.0.0.1:1/inesistente")
    with pytest.raises(MemoryStorageError):
        repo.get("qualunque-id")


def test_postgres_submit_id_duplicato_solleva_memory_storage_error(
    pg_repo: PostgresMemoryRepository,
) -> None:
    """Un errore psycopg (qui: violazione della chiave primaria) è mappato
    in `MemoryStorageError` — infrastrutturale, MAI un `UrbanMemoryError` di
    dominio: il BFF deve poterle distinguere."""
    contributo = _contributo(
        id="mem-duplicato",
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )
    pg_repo.submit(contributo)
    with pytest.raises(MemoryStorageError):
        pg_repo.submit(contributo)


# --- Protocol MemoryRepository: stessi test, entrambe le implementazioni ---


def test_protocollo_submit_get_curated_curate_su_entrambe_le_implementazioni(
    any_memory_repository: MemoryRepository,
) -> None:
    """Lo stesso ciclo di vita (submit -> non pubblicato -> curate ->
    pubblicato) vale IDENTICO su `InMemoryMemoryRepository` e su
    `PostgresMemoryRepository`: è lo stesso `Protocol`, non due contratti
    diversi con lo stesso nome."""
    repo = any_memory_repository
    contributo = _contributo(
        id="mem-protocollo-1",
        riguarda=["luogo-protocollo"],
        creato_il=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    )

    persistito = repo.submit(contributo)
    assert persistito.id == "mem-protocollo-1"
    assert repo.get_curated("luogo-protocollo") == []
    assert [c.id for c in repo.list_pending()] == ["mem-protocollo-1"]
    assert repo.get("mem-protocollo-1").curato is False  # type: ignore[union-attr]
    assert repo.get("mai-esistito-in-nessuna-implementazione") is None

    assert [c.id for c in repo.list_curated()] == []  # non ancora curato

    curato = repo.curate("mem-protocollo-1")
    assert curato.curato is True
    assert [c.id for c in repo.get_curated("luogo-protocollo")] == ["mem-protocollo-1"]
    assert repo.list_pending() == []
    assert repo.get("mem-protocollo-1").curato is True  # type: ignore[union-attr]
    assert [c.id for c in repo.list_curated()] == ["mem-protocollo-1"]

    with pytest.raises(KeyError):
        repo.curate("non-esiste-in-nessuna-implementazione")
