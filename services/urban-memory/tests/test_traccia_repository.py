"""Test di `urban_memory.traccia_repository` — il ledger delle tracce (Fase
3, `docs/PROMOZIONE_TRACCIA.md` §1).

Parametrizzato con `any_traccia_repository` (InMemory + Postgres effimero,
vedi `tests/conftest.py`): un test che passa solo su una implementazione la
segnala. `PostgresTracciaRepository` è SALTATA (non fallita) se il cluster
Postgres 16 effimero non è disponibile in questo ambiente."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from urban_memory.traccia_repository import TracciaStorageError

CREATO_IL = datetime(2026, 7, 14, 23, 59, 59, tzinfo=UTC)


def test_deposita_ritorna_una_traccia_con_anagrafica_minima(any_traccia_repository) -> None:
    repo = any_traccia_repository

    traccia = repo.deposita(
        segnale_id="segnale-1",
        place_id="piazza-anfiteatro",
        temi=["musica", "arte"],
        creato_il=CREATO_IL,
    )

    assert traccia.segnale_id == "segnale-1"
    assert traccia.place_id == "piazza-anfiteatro"
    assert traccia.temi == ("musica", "arte")
    assert traccia.creato_il == CREATO_IL
    assert traccia.id  # chiave surrogata, generata, non vuota


def test_deposita_genera_id_diversi_per_tracce_diverse(any_traccia_repository) -> None:
    repo = any_traccia_repository

    t1 = repo.deposita(
        segnale_id="segnale-a", place_id="luogo-a", temi=["musica"], creato_il=CREATO_IL
    )
    t2 = repo.deposita(
        segnale_id="segnale-b", place_id="luogo-a", temi=["musica"], creato_il=CREATO_IL
    )

    assert t1.id != t2.id, (
        "due tracce identiche in place_id/temi/istante restano due passaggi "
        "distinti (docs/PROMOZIONE_TRACCIA.md §1): chiave surrogata, non una "
        "chiave composta su place_id/temi/creato_il"
    )


def test_creato_il_tz_aware_persiste_senza_perdita(any_traccia_repository) -> None:
    repo = any_traccia_repository
    istante = datetime.now(UTC)

    traccia = repo.deposita(
        segnale_id="segnale-tz", place_id="luogo-x", temi=["storia"], creato_il=istante
    )

    assert traccia.creato_il.tzinfo is not None, "creato_il deve restare tz-aware"


def test_deposita_due_volte_lo_stesso_segnale_id_solleva_errore(any_traccia_repository) -> None:
    """Difesa in profondità dell'idempotenza (la guardia primaria è a monte,
    in `SegnaleFluttuanteRepository.sweep_scaduti`): un bug applicativo che
    chiamasse `deposita` due volte per lo STESSO `segnale_id` deve fallire
    rumorosamente, mai duplicare silenziosamente il ledger."""
    repo = any_traccia_repository
    repo.deposita(
        segnale_id="segnale-duplicato", place_id="luogo-x", temi=["storia"], creato_il=CREATO_IL
    )

    with pytest.raises(TracciaStorageError):
        repo.deposita(
            segnale_id="segnale-duplicato",
            place_id="luogo-x",
            temi=["storia"],
            creato_il=CREATO_IL,
        )


def test_list_for_place_filtra_per_luogo_in_ordine_di_deposito(any_traccia_repository) -> None:
    repo = any_traccia_repository
    repo.deposita(
        segnale_id="s1",
        place_id="luogo-a",
        temi=["musica"],
        creato_il=datetime(2026, 7, 1, tzinfo=UTC),
    )
    repo.deposita(
        segnale_id="s2",
        place_id="luogo-b",
        temi=["storia"],
        creato_il=datetime(2026, 7, 2, tzinfo=UTC),
    )
    repo.deposita(
        segnale_id="s3",
        place_id="luogo-a",
        temi=["musica"],
        creato_il=datetime(2026, 7, 3, tzinfo=UTC),
    )

    tracce_a = repo.list_for_place("luogo-a")

    assert [t.segnale_id for t in tracce_a] == ["s1", "s3"]


def test_list_for_place_vuota_se_nessuna_traccia(any_traccia_repository) -> None:
    repo = any_traccia_repository
    assert repo.list_for_place("luogo-mai-visto") == []
