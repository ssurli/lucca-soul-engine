"""Test di `scripts/scarta_contributo.py` — repository in memoria, nessuna rete."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory.repository import InMemoryMemoryRepository

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scarta_contributo.py"


def _carica() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scarta_contributo", _PATH)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _carica()


def _repo() -> InMemoryMemoryRepository:
    repo = InMemoryMemoryRepository()
    for i, curato in (("a", False), ("b", True)):
        repo.submit(
            MemoryContribution(
                id=i,
                kind=MemoryKind.RACCONTO,
                testo="x" * 100,
                riguarda=["luogo-1"],
                contributor_id=f"pseudonimo-segreto-{i}",
                contributor_kind=PersonKind.CITTADINO,
                consenso=True,
                licenza="CC-BY-SA-4.0",
                creato_il=datetime(2026, 7, 14, tzinfo=UTC),
                curato=curato,
            )
        )
    return repo


def test_elenco_senza_contributor_id_e_testo_troncato(capsys: pytest.CaptureFixture[str]) -> None:
    assert script.main([], repo=_repo()) == 0
    out = capsys.readouterr().out
    assert "a | " in out and "pseudonimo-segreto" not in out
    assert "x" * 60 in out and "x" * 61 not in out
    assert "b | " not in out  # curato: non e in coda


def test_prova_a_secco_non_scrive(capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo()
    assert script.main(["--id", "a", "--motivo", "spam"], repo=repo) == 0
    out = capsys.readouterr().out
    assert "spam" in out and "pseudonimo-segreto" not in out
    assert [c.id for c in repo.list_pending()] == ["a"]


def test_esegui_scrive() -> None:
    repo = _repo()
    assert script.main(["--id", "a", "--motivo", "spam", "--esegui"], repo=repo) == 0
    assert repo.list_pending() == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--id", "b", "--motivo", "x", "--esegui"],  # curato
        ["--id", "zzz", "--motivo", "x", "--esegui"],  # inesistente
        ["--id", "a", "--motivo", "  ", "--esegui"],  # motivo vuoto
        ["--id", "a", "--esegui"],  # motivo mancante
        ["--id", "b", "--motivo", "x"],  # anche a secco segnala l'errore
    ],
)
def test_errori_exit_code_non_zero(argv: list[str]) -> None:
    repo = _repo()
    assert script.main(argv, repo=repo) != 0
    assert [c.id for c in repo.list_pending()] == ["a"]
    assert [c.id for c in repo.list_curated()] == ["b"]


def test_gia_scartato_exit_non_zero() -> None:
    repo = _repo()
    assert script.main(["--id", "a", "--motivo", "x", "--esegui"], repo=repo) == 0
    assert script.main(["--id", "a", "--motivo", "y", "--esegui"], repo=repo) != 0
