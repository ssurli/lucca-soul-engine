"""Scarto esplicito (mai DELETE) di un contributo non curato: repository
in-memory e Postgres (cluster effimero, saltato se assente), migrazione 05."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import (
    ContributoInesistente,
    ContributoNonScartabile,
    ContributoScartato,
    InMemoryMemoryRepository,
    MemoryRepository,
    MotivoScartoRichiesto,
)
from urban_memory.migrate import SCHEMA_PATHS, migrate

_SQL_05 = Path(__file__).resolve().parents[1] / "sql" / "05_scarto_schema.sql"


def _c(id: str, *, curato: bool = False, riguarda: str = "luogo-1") -> MemoryContribution:
    return MemoryContribution(
        id=id,
        kind=MemoryKind.RACCONTO,
        testo=f"racconto {id}",
        riguarda=[riguarda],
        contributor_id=f"p-{id}",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
        curato=curato,
    )


def test_scarto_toglie_da_pending(any_memory_repository: MemoryRepository) -> None:
    repo = any_memory_repository
    repo.submit(_c("a"))
    repo.submit(_c("b"))
    repo.scarta("a", "fuori tema")
    assert [c.id for c in repo.list_pending()] == ["b"]


def test_scarto_non_tocca_i_curati_e_get_restituisce_ancora_lo_scartato(
    any_memory_repository: MemoryRepository,
) -> None:
    repo = any_memory_repository
    repo.submit(_c("a"))
    repo.submit(_c("c"))
    repo.curate("c")
    repo.scarta("a", "duplicato")
    assert [c.id for c in repo.list_curated()] == ["c"]
    assert [c.id for c in repo.get_curated("luogo-1")] == ["c"]
    # get() e un lookup "cosi com'e": lo scartato esiste ancora (mai DELETE).
    assert repo.get("a") is not None


def test_scarto_su_curato_fallisce_e_resta_visibile(
    any_memory_repository: MemoryRepository,
) -> None:
    repo = any_memory_repository
    repo.submit(_c("c"))
    repo.curate("c")
    with pytest.raises(ContributoNonScartabile):
        repo.scarta("c", "ripensamento")
    assert [c.id for c in repo.get_curated("luogo-1")] == ["c"]
    assert [c.id for c in repo.list_curated()] == ["c"]


def test_scarto_su_inesistente_fallisce(any_memory_repository: MemoryRepository) -> None:
    with pytest.raises(ContributoInesistente):
        any_memory_repository.scarta("non-esiste", "x")


def test_scarto_due_volte_fallisce(any_memory_repository: MemoryRepository) -> None:
    repo = any_memory_repository
    repo.submit(_c("a"))
    repo.scarta("a", "x")
    with pytest.raises(ContributoNonScartabile):
        repo.scarta("a", "y")


@pytest.mark.parametrize("motivo", ["", "   ", "\n\t"])
def test_scarto_motivo_vuoto_fallisce_senza_scrivere(
    any_memory_repository: MemoryRepository, motivo: str
) -> None:
    repo = any_memory_repository
    repo.submit(_c("a"))
    with pytest.raises(MotivoScartoRichiesto):
        repo.scarta("a", motivo)
    assert [c.id for c in repo.list_pending()] == ["a"]


def test_motivo_vuoto_e_un_valueerror() -> None:
    assert issubclass(MotivoScartoRichiesto, ValueError)


def test_curare_uno_scartato_fallisce(any_memory_repository: MemoryRepository) -> None:
    repo = any_memory_repository
    repo.submit(_c("a"))
    repo.scarta("a", "x")
    with pytest.raises(ContributoScartato):
        repo.curate("a")
    assert repo.list_curated() == []


def test_curate_inesistente_resta_keyerror(any_memory_repository: MemoryRepository) -> None:
    with pytest.raises(KeyError):
        any_memory_repository.curate("nope")


def test_scartato_non_entra_nel_conteggio_dell_index() -> None:
    """L'Index conta list_pending()+list_curated(): l'esclusione nei repository
    basta (stessa composizione di `api.main` e `intelligence_index`)."""
    from intelligence_index.indicatori import contributi_memoria

    repo = InMemoryMemoryRepository()
    for i in range(3):
        repo.submit(_c(f"m{i}"))
    repo.curate("m0")
    assert contributi_memoria(repo.list_pending() + repo.list_curated())[0] == 3
    repo.scarta("m1", "spam")
    valore, persone = contributi_memoria(repo.list_pending() + repo.list_curated())
    assert valore == 2
    assert "p-m1" not in persone


# --- migrazione 05 -----------------------------------------------------------


def test_05_e_nello_schema_path_dopo_00() -> None:
    assert _SQL_05 in SCHEMA_PATHS
    assert SCHEMA_PATHS.index(_SQL_05) > 0
    assert SCHEMA_PATHS[0].name == "00_memory_schema.sql"


def test_05_statico_solo_if_not_exists_e_nessun_drop() -> None:
    righe = [
        r.strip().upper()
        for r in _SQL_05.read_text(encoding="utf-8").splitlines()
        if r.strip() and not r.strip().startswith("--")
    ]
    assert righe, "il file non contiene istruzioni"
    assert all("ADD COLUMN IF NOT EXISTS" in r for r in righe)
    testo = " ".join(righe)
    assert "DROP" not in testo and "DELETE" not in testo


def test_migrate_05_rieseguita_e_scarto_persiste(pg_dsn: str) -> None:
    from urban_memory.repository import PostgresMemoryRepository

    migrate(pg_dsn)
    migrate(pg_dsn)
    migrate(pg_dsn)
    repo = PostgresMemoryRepository(pg_dsn)
    repo.submit(_c("a"))
    repo.scarta("a", "  fuori tema  ")
    with psycopg.connect(pg_dsn) as conn:
        riga = conn.execute(
            "SELECT scartato_il, motivo_scarto FROM memory_contribution WHERE id = 'a'"
        ).fetchone()
    assert riga is not None and riga[0] is not None and riga[1] == "fuori tema"
