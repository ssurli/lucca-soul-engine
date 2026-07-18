"""Test di `marketplace.repository`.

`InMemoryBookingRepository` è il percorso di default (usato nei test e
finché `DATABASE_URL` non è configurato). `PostgresBookingRepository` è
testata contro un Postgres 16 EFFIMERO vero (vedi `tests/conftest.py`) — non
un mock: create/get/update_status/record_commission/get_commission, la
migrazione idempotente, i `CHECK` del DB a difesa in profondità, e
soprattutto che la prenotazione e la commissione sopravvivono alla chiusura
e riapertura della connessione.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest
from contracts import Booking, BookingStatus, CommissionRecord
from marketplace import BookingRepository, InMemoryBookingRepository, PostgresBookingRepository
from marketplace.migrate import migrate
from marketplace.repository import MarketplaceStorageError
from marketplace.service import confirm_booking


def _booking(**overrides: object) -> Booking:
    defaults: dict[str, object] = {
        "id": "booking-repo-1",
        "person_id": "pseudonimo-1",
        "experience_id": "esperienza-1",
        "quando": datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
        "stato": BookingStatus.RICHIESTA,
        "prezzo_eur": 25.0,
        "creato_il": datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Booking(**defaults)


def _commissione(**overrides: object) -> CommissionRecord:
    defaults: dict[str, object] = {
        "booking_id": "booking-repo-1",
        "importo_eur": 3.75,
        "percentuale": 0.15,
        "registrata_il": datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return CommissionRecord(**defaults)


# --- InMemoryBookingRepository implementa il Protocol -----------------------


def test_in_memory_repository_implementa_il_protocollo() -> None:
    repo: BookingRepository = InMemoryBookingRepository()
    assert hasattr(repo, "create")
    assert hasattr(repo, "get")
    assert hasattr(repo, "update_status")
    assert hasattr(repo, "record_commission")
    assert hasattr(repo, "get_commission")


def test_create_ritorna_la_prenotazione_persistita() -> None:
    repo = InMemoryBookingRepository()
    prenotazione = _booking()
    persistita = repo.create(prenotazione)
    assert persistita == prenotazione


def test_get_id_sconosciuto_restituisce_none() -> None:
    repo = InMemoryBookingRepository()
    assert repo.get("non-esiste") is None


def test_update_status_aggiorna_e_restituisce() -> None:
    repo = InMemoryBookingRepository()
    repo.create(_booking(id="b1"))

    aggiornata = repo.update_status("b1", BookingStatus.CONFERMATA)

    assert aggiornata.stato == BookingStatus.CONFERMATA
    assert repo.get("b1").stato == BookingStatus.CONFERMATA  # type: ignore[union-attr]


def test_update_status_id_sconosciuto_solleva_keyerror() -> None:
    repo = InMemoryBookingRepository()
    with pytest.raises(KeyError):
        repo.update_status("non-esiste", BookingStatus.CONFERMATA)


def test_record_commission_e_get_commission() -> None:
    repo = InMemoryBookingRepository()
    repo.create(_booking(id="b1"))
    assert repo.get_commission("b1") is None

    commissione = repo.record_commission(_commissione(booking_id="b1"))

    assert repo.get_commission("b1") == commissione


def test_get_commission_senza_commissione_restituisce_none() -> None:
    repo = InMemoryBookingRepository()
    repo.create(_booking(id="b1"))
    assert repo.get_commission("b1") is None


# --- PostgresBookingRepository: interfaccia e costruzione -------------------


def test_postgres_repository_ha_linterfaccia_attesa() -> None:
    repo = PostgresBookingRepository(dsn="postgresql://esplicito/db")
    assert hasattr(repo, "create")
    assert hasattr(repo, "get")
    assert hasattr(repo, "update_status")
    assert hasattr(repo, "record_commission")
    assert hasattr(repo, "get_commission")


def test_postgres_repository_dsn_arriva_sempre_dal_costruttore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    repo = PostgresBookingRepository(dsn="postgresql://esplicito/db")
    assert repo._dsn == "postgresql://esplicito/db"


def test_postgres_repository_from_env_richiede_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv_vuoto = tmp_path / ".env"
    dotenv_vuoto.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        PostgresBookingRepository.from_env(dotenv_path=dotenv_vuoto)


def test_postgres_repository_from_env_legge_il_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('DATABASE_URL="postgresql://letto-dal-file/db"\n', encoding="utf-8")
    repo = PostgresBookingRepository.from_env(dotenv_path=dotenv)
    assert repo._dsn == "postgresql://letto-dal-file/db"


# --- PostgresBookingRepository: persistenza reale (Postgres 16 effimero) ---


def test_migrate_e_idempotente(pg_dsn: str) -> None:
    migrate(pg_dsn)
    migrate(pg_dsn)  # seconda corsa: deve essere un no-op, non un errore


def test_postgres_create_poi_get(pg_repo: PostgresBookingRepository) -> None:
    prenotazione = _booking(id="booking-pg-1")
    persistita = pg_repo.create(prenotazione)
    assert persistita.id == "booking-pg-1"

    trovata = pg_repo.get("booking-pg-1")
    assert trovata is not None
    assert trovata.stato == BookingStatus.RICHIESTA
    assert trovata.prezzo_eur == 25.0


def test_postgres_update_status(pg_repo: PostgresBookingRepository) -> None:
    pg_repo.create(_booking(id="booking-pg-2"))

    aggiornata = pg_repo.update_status("booking-pg-2", BookingStatus.CONFERMATA)

    assert aggiornata.stato == BookingStatus.CONFERMATA
    assert pg_repo.get("booking-pg-2").stato == BookingStatus.CONFERMATA  # type: ignore[union-attr]


def test_postgres_update_status_id_sconosciuto_solleva_keyerror(
    pg_repo: PostgresBookingRepository,
) -> None:
    with pytest.raises(KeyError):
        pg_repo.update_status("non-esiste-su-postgres", BookingStatus.CONFERMATA)


def test_postgres_record_commission_e_get_commission(pg_repo: PostgresBookingRepository) -> None:
    pg_repo.create(_booking(id="booking-pg-3"))
    assert pg_repo.get_commission("booking-pg-3") is None

    registrata = pg_repo.record_commission(_commissione(booking_id="booking-pg-3"))

    riletta = pg_repo.get_commission("booking-pg-3")
    assert riletta is not None
    assert riletta.importo_eur == registrata.importo_eur


def test_postgres_persistenza_sopravvive_a_una_nuova_connessione(pg_dsn: str) -> None:
    """IL CUORE DELLA RICHIESTA: dopo aver chiuso il repository "scrittore" e
    aperto un repository NUOVO sullo STESSO DSN, la prenotazione confermata e
    la sua commissione sono ANCORA lì."""
    migrate(pg_dsn)

    scrittore = PostgresBookingRepository(pg_dsn)
    scrittore.create(_booking(id="booking-persist-1"))
    scrittore.update_status("booking-persist-1", BookingStatus.CONFERMATA)
    scrittore.record_commission(_commissione(booking_id="booking-persist-1"))
    del scrittore  # nessuna connessione persistente da chiudere: per-operazione

    lettore = PostgresBookingRepository(pg_dsn)  # istanza NUOVA, stesso DSN
    prenotazione = lettore.get("booking-persist-1")
    assert prenotazione is not None
    assert prenotazione.stato == BookingStatus.CONFERMATA
    assert lettore.get_commission("booking-persist-1") is not None

    ancora = PostgresBookingRepository(pg_dsn)  # un'ALTRA istanza
    assert ancora.get("booking-persist-1").stato == BookingStatus.CONFERMATA  # type: ignore[union-attr]


def test_check_db_rifiuta_stato_non_valido(pg_dsn: str) -> None:
    """Difesa in profondità: ANCHE un INSERT diretto (che scavalca
    `marketplace.service`) è rifiutato dal `CHECK` a livello DB."""
    migrate(pg_dsn)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                "INSERT INTO booking "
                "(id, person_id, experience_id, quando, stato, prezzo_eur, creato_il) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    "booking-stato-invalido",
                    "pseudonimo",
                    "esperienza",
                    datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
                    "in_lavorazione",  # <- non è richiesta/confermata/annullata
                    10.0,
                    datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
                ),
            )


def test_check_db_rifiuta_prezzo_negativo(pg_dsn: str) -> None:
    migrate(pg_dsn)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                "INSERT INTO booking "
                "(id, person_id, experience_id, quando, stato, prezzo_eur, creato_il) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    "booking-prezzo-negativo",
                    "pseudonimo",
                    "esperienza",
                    datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
                    "richiesta",
                    -1.0,  # <- prezzo negativo: deve essere rifiutato dal CHECK
                    datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
                ),
            )


def test_check_db_rifiuta_doppia_commissione_sulla_stessa_prenotazione(
    pg_repo: PostgresBookingRepository,
) -> None:
    """`commission_record.booking_id` è PRIMARY KEY: una seconda
    `record_commission` sulla stessa prenotazione è rifiutata dal DB (difesa
    in profondità oltre alla logica idempotente di `confirm_booking`)."""
    pg_repo.create(_booking(id="booking-doppia-commissione"))
    pg_repo.record_commission(_commissione(booking_id="booking-doppia-commissione"))

    with pytest.raises(MarketplaceStorageError):
        pg_repo.record_commission(_commissione(booking_id="booking-doppia-commissione"))


def test_postgres_create_id_duplicato_solleva_marketplace_storage_error(
    pg_repo: PostgresBookingRepository,
) -> None:
    pg_repo.create(_booking(id="booking-duplicato"))
    with pytest.raises(MarketplaceStorageError):
        pg_repo.create(_booking(id="booking-duplicato"))


def test_postgres_get_con_connessione_non_raggiungibile_solleva_marketplace_storage_error() -> None:
    repo = PostgresBookingRepository(dsn="postgresql://postgres@127.0.0.1:1/inesistente")
    with pytest.raises(MarketplaceStorageError):
        repo.get("qualunque-id")


# --- Protocol BookingRepository: stessi test, entrambe le implementazioni --


def test_protocollo_create_get_update_status_su_entrambe_le_implementazioni(
    any_booking_repository: BookingRepository,
) -> None:
    repo = any_booking_repository
    prenotazione = _booking(id="booking-protocollo-1")

    persistita = repo.create(prenotazione)
    assert persistita.id == "booking-protocollo-1"
    assert repo.get("booking-protocollo-1").stato == BookingStatus.RICHIESTA  # type: ignore[union-attr]
    assert repo.get_commission("booking-protocollo-1") is None

    aggiornata = repo.update_status("booking-protocollo-1", BookingStatus.CONFERMATA)
    assert aggiornata.stato == BookingStatus.CONFERMATA

    commissione = repo.record_commission(_commissione(booking_id="booking-protocollo-1"))
    assert repo.get_commission("booking-protocollo-1") == commissione

    with pytest.raises(KeyError):
        repo.update_status("non-esiste-in-nessuna-implementazione", BookingStatus.CONFERMATA)


# --- Separazione contabile: booking e commission_record ---------------------
#
# Verifica permanente, contro Postgres reale, di quanto già confermato
# manualmente in chiusura di Wave 3a (prescrizione ethics-guardian,
# docs/DATA_CONTRACTS.md §5): la commissione è un dato contabile SEPARATO
# dalla prenotazione, a livello di SCHEMA (tabelle e colonne distinte) e a
# livello di SEQUENZA TEMPORALE (calcolata solo dopo la conferma).


def test_booking_e_commission_record_sono_due_tabelle_distinte(pg_dsn: str) -> None:
    """Non una tabella sola con entrambi i concetti, non una vista che li
    unisce: due tabelle distinte nello schema reale."""
    migrate(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        righe = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name IN (%s, %s)",
            ("booking", "commission_record"),
        ).fetchall()

    nomi_tabelle = {riga[0] for riga in righe}
    assert nomi_tabelle == {"booking", "commission_record"}


def test_booking_non_ha_nessuna_colonna_di_commissione(pg_dsn: str) -> None:
    """`booking` non deve MAI acquisire una colonna di commissione: verifica
    che l'insieme delle colonne di `commission_record` non intersechi
    l'insieme delle colonne di `booking`, invece di una whitelist rigida
    delle colonne di `booking` (che si romperebbe a ogni futura colonna
    legittima aggiunta lì)."""
    migrate(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        colonne_booking = {
            riga[0]
            for riga in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                ("booking",),
            ).fetchall()
        }
        colonne_commissione = {
            riga[0]
            for riga in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                ("commission_record",),
            ).fetchall()
        }

    assert colonne_booking  # la tabella esiste davvero e ha colonne
    assert colonne_commissione  # idem per commission_record
    assert colonne_booking & colonne_commissione == set()


def test_commissione_e_registrata_solo_dopo_la_conferma_con_cronologia_reale(
    pg_repo: PostgresBookingRepository,
) -> None:
    """`confirm_booking` (il percorso reale, non `record_commission` diretto)
    calcola e registra la commissione SOLO dopo che la conferma è già
    persistita. Il riferimento temporale viene da un orologio ESTERNO al
    codice sotto test (catturato qui, nel test, subito prima della
    chiamata) — non da due timestamp scritti entrambi dal codice testato,
    confronto che proverebbe ben poco."""
    prenotazione = pg_repo.create(_booking(id="booking-cronologia-1"))
    assert pg_repo.get_commission("booking-cronologia-1") is None

    prima_della_conferma = datetime.now(UTC)
    confirm_booking(pg_repo, "booking-cronologia-1")

    commissione = pg_repo.get_commission("booking-cronologia-1")
    assert commissione is not None
    assert commissione.registrata_il >= prima_della_conferma
    assert commissione.registrata_il > prenotazione.creato_il
