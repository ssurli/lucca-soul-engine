"""Test di `urban_memory.promozione_repository` — il ledger delle promozioni
(Fase 3). Parametrizzato con `any_promozione_repository` (InMemory + Postgres
effimero, `tests/conftest.py`): il ramo Postgres e' SALTATO (non fallito) se
il cluster effimero non e' disponibile. I test "irraggiungibile" girano
sempre (nessun server in ascolto sulla porta 1 locale)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from urban_memory.freno_repository import FrenoStorageError, PostgresPatternFrenatoRepository
from urban_memory.migrate import migrate
from urban_memory.promozione_repository import (
    PostgresPromozioneRepository,
    PromozioneStorageError,
)

T0 = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def _registra(repo, **override):
    kw = {
        "evento_id": "evento-x",
        "place_id": "luogo-x",
        "temi": ["arte", "musica"],
        "cadenza_giorni": 7.0,
        "promotore": "promotore-1",
        "promosso_il": T0,
    }
    kw.update(override)
    return repo.registra(**kw)


# ---------------------------------------------------------------------------
# Contratto comune (in-memory + Postgres)
# ---------------------------------------------------------------------------


def test_registra_ritorna_la_riga_con_i_campi_dati(any_promozione_repository) -> None:
    riga = _registra(any_promozione_repository)

    assert riga.id
    assert riga.evento_id == "evento-x"
    assert riga.place_id == "luogo-x"
    assert riga.temi == ("arte", "musica")
    assert riga.cadenza_giorni == 7.0
    assert riga.promotore == "promotore-1"
    assert riga.promosso_il == T0
    assert riga.promosso_il.tzinfo is not None


def test_ripromozione_e_una_riga_nuova_mai_un_upsert(any_promozione_repository) -> None:
    repo = any_promozione_repository
    r1 = _registra(repo, cadenza_giorni=7.0, promotore="primo")
    r2 = _registra(repo, cadenza_giorni=14.0, promotore="secondo", promosso_il=T0 + timedelta(1))

    righe = repo.elenca()
    assert len(righe) == 2
    assert r1.id != r2.id
    assert [r.promotore for r in righe] == ["primo", "secondo"]
    assert [r.cadenza_giorni for r in righe] == [7.0, 14.0]  # la prima NON e' sovrascritta


def test_registrata_vero_solo_per_evento_con_almeno_una_riga(any_promozione_repository) -> None:
    repo = any_promozione_repository
    assert repo.registrata("evento-x") is False
    _registra(repo)
    assert repo.registrata("evento-x") is True
    assert repo.registrata("evento-altro") is False


def test_elenca_ordina_per_promosso_il_non_per_inserimento(any_promozione_repository) -> None:
    repo = any_promozione_repository
    _registra(repo, evento_id="e-tardi", promosso_il=T0 + timedelta(days=2))
    _registra(repo, evento_id="e-presto", promosso_il=T0)
    _registra(repo, evento_id="e-mezzo", promosso_il=T0 + timedelta(days=1))

    assert [r.evento_id for r in repo.elenca()] == ["e-presto", "e-mezzo", "e-tardi"]


def test_temi_vuoti_e_ordine_dei_temi_preservati(any_promozione_repository) -> None:
    repo = any_promozione_repository
    _registra(repo, evento_id="e-vuoto", temi=[])
    _registra(repo, evento_id="e-ord", temi=["zeta", "alfa"])
    per_id = {r.evento_id: r for r in repo.elenca()}
    assert per_id["e-vuoto"].temi == ()
    assert per_id["e-ord"].temi == ("zeta", "alfa")


# ---------------------------------------------------------------------------
# Solo Postgres: vincoli DB, append-only, migrazione
# ---------------------------------------------------------------------------


def test_pg_nessun_unique_sul_pattern_stesso_istante_due_righe(pg_dsn: str) -> None:
    migrate(pg_dsn)
    repo = PostgresPromozioneRepository(pg_dsn)
    _registra(repo)
    _registra(repo)  # stesso evento_id, stesso istante, stesso promotore
    assert len(repo.elenca()) == 2


@pytest.mark.parametrize("cadenza", [0.0, -1.0])
def test_pg_cadenza_non_positiva_rifiutata_dal_check(pg_dsn: str, cadenza: float) -> None:
    migrate(pg_dsn)
    repo = PostgresPromozioneRepository(pg_dsn)
    with pytest.raises(PromozioneStorageError):
        _registra(repo, cadenza_giorni=cadenza)
    assert repo.elenca() == []


def test_pg_promotore_vuoto_rifiutato_dal_check(pg_dsn: str) -> None:
    migrate(pg_dsn)
    repo = PostgresPromozioneRepository(pg_dsn)
    with pytest.raises(PromozioneStorageError):
        _registra(repo, promotore="")
    assert repo.elenca() == []


_INSERT_DIRETTO = (
    "INSERT INTO pattern_promosso (id, evento_id, place_id, temi, cadenza_giorni, "
    "promotore, promosso_il) VALUES (%s, 'e', 'l', '{}', %s, %s, now())"
)


def test_pg_check_vale_anche_per_insert_diretto_che_bypassa_il_repository(pg_dsn: str) -> None:
    """Backstop a livello DB: nemmeno un INSERT diretto aggira i CHECK."""
    migrate(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(_INSERT_DIRETTO, ("id-1", 0.0, "p"))
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(_INSERT_DIRETTO, ("id-2", 7.0, ""))
        conn.rollback()
        conn.execute(_INSERT_DIRETTO, ("id-3", 7.0, "p"))  # il caso valido passa
        conn.commit()


def test_pg_id_duplicato_rifiutato_dalla_primary_key(pg_dsn: str) -> None:
    migrate(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(_INSERT_DIRETTO, ("stesso", 7.0, "p"))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(_INSERT_DIRETTO, ("stesso", 7.0, "p"))


def test_pg_senza_migrazione_solleva_storage_error(pg_dsn: str) -> None:
    repo = PostgresPromozioneRepository(pg_dsn)  # tabella assente
    with pytest.raises(PromozioneStorageError):
        _registra(repo)
    with pytest.raises(PromozioneStorageError):
        repo.elenca()
    with pytest.raises(PromozioneStorageError):
        repo.registrata("evento-x")


def test_pg_migrate_crea_pattern_promosso_ed_e_idempotente(pg_dsn: str) -> None:
    migrate(pg_dsn)
    repo = PostgresPromozioneRepository(pg_dsn)
    _registra(repo)

    migrate(pg_dsn)  # seconda e terza corsa: no-op, non sollevano
    migrate(pg_dsn)

    assert len(repo.elenca()) == 1, "la rimigrazione non deve toccare ne' svuotare il ledger"
    with psycopg.connect(pg_dsn) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_indexes "
            "WHERE tablename = 'pattern_promosso' AND indexname = 'pattern_promosso_evento_id_idx'"
        ).fetchone()
    assert row is not None and row[0] == 1


# ---------------------------------------------------------------------------
# PatternFrenatoRepository.ultime_azioni (contratto comune)
# ---------------------------------------------------------------------------


def _freno(repo, evento_id: str, azione: str, quando: datetime):
    return repo.registra(
        evento_id=evento_id,
        place_id=None,
        temi=[],
        azione=azione,
        attore="a",
        motivazione="motivo" if azione == "tirato" else None,
        quando=quando,
    )


def test_ultime_azioni_vuoto_senza_righe(any_freno_repository) -> None:
    assert any_freno_repository.ultime_azioni() == []


def test_ultime_azioni_una_riga_per_evento_e_vince_la_piu_recente(any_freno_repository) -> None:
    repo = any_freno_repository
    _freno(repo, "e-a", "tirato", T0)
    _freno(repo, "e-a", "rilasciato", T0 + timedelta(days=1))
    _freno(repo, "e-b", "tirato", T0)
    _freno(repo, "e-c", "rilasciato", T0)
    _freno(repo, "e-c", "tirato", T0 + timedelta(days=2))

    ultime = repo.ultime_azioni()

    assert len(ultime) == 3  # esattamente una per evento_id
    assert {r.evento_id: r.azione for r in ultime} == {
        "e-a": "rilasciato",
        "e-b": "tirato",
        "e-c": "tirato",
    }


def test_ultime_azioni_usa_quando_non_l_ordine_di_inserimento(any_freno_repository) -> None:
    repo = any_freno_repository
    # Inserita PER PRIMA ma cronologicamente ULTIMA.
    _freno(repo, "e-a", "rilasciato", T0 + timedelta(days=5))
    _freno(repo, "e-a", "tirato", T0)

    [ultima] = repo.ultime_azioni()
    assert ultima.azione == "rilasciato"


def test_ultime_azioni_parita_quando_tirato_inserito_prima_vince_tirato(
    any_freno_repository,
) -> None:
    repo = any_freno_repository
    _freno(repo, "e-a", "tirato", T0)
    _freno(repo, "e-a", "rilasciato", T0)

    [ultima] = repo.ultime_azioni()
    assert ultima.azione == "tirato"


def test_ultime_azioni_parita_quando_rilasciato_inserito_prima_vince_tirato(
    any_freno_repository,
) -> None:
    repo = any_freno_repository
    _freno(repo, "e-a", "rilasciato", T0)
    _freno(repo, "e-a", "tirato", T0)

    [ultima] = repo.ultime_azioni()
    assert ultima.azione == "tirato"


def test_ultime_azioni_quando_diversi_vince_il_piu_recente_anche_se_rilasciato(
    any_freno_repository,
) -> None:
    repo = any_freno_repository
    _freno(repo, "e-a", "tirato", T0 + timedelta(seconds=1))
    _freno(repo, "e-a", "rilasciato", T0 + timedelta(seconds=2))

    [ultima] = repo.ultime_azioni()
    assert ultima.azione == "rilasciato"


# ---------------------------------------------------------------------------
# Senza cluster: errori infrastrutturali tipizzati (storage irraggiungibile)
# ---------------------------------------------------------------------------

_DSN_IRRAGGIUNGIBILE = "postgresql://x@127.0.0.1:1/x?connect_timeout=2"


def test_ledger_irraggiungibile_solleva_promozione_storage_error() -> None:
    repo = PostgresPromozioneRepository(_DSN_IRRAGGIUNGIBILE)
    with pytest.raises(PromozioneStorageError):
        _registra(repo)
    with pytest.raises(PromozioneStorageError):
        repo.registrata("e")
    with pytest.raises(PromozioneStorageError):
        repo.elenca()


def test_freno_ultime_azioni_irraggiungibile_solleva_freno_storage_error() -> None:
    with pytest.raises(FrenoStorageError):
        PostgresPatternFrenatoRepository(_DSN_IRRAGGIUNGIBILE).ultime_azioni()
