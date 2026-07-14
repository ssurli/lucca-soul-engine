"""Test di `urban_memory.repository`.

`InMemoryMemoryRepository` è il percorso principale (usato nei test e
finché `DATABASE_URL` non è configurato). `PostgresMemoryRepository` non è
testabile live in questo ambiente (nessun Postgres raggiungibile): resta
coperta da test che ne verificano l'interfaccia e la predisposizione
(`NotImplementedError`, DSN mai letto implicitamente dall'ambiente).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import InMemoryMemoryRepository, MemoryRepository, PostgresMemoryRepository


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


# --- PostgresMemoryRepository: predisposta, non implementata ---------------


def test_postgres_repository_ha_linterfaccia_attesa() -> None:
    repo = PostgresMemoryRepository(dsn="postgresql://esplicito/db")
    assert hasattr(repo, "submit")
    assert hasattr(repo, "get_curated")
    assert hasattr(repo, "list_pending")
    assert hasattr(repo, "curate")


def test_postgres_repository_non_implementata_solleva_not_implemented_error() -> None:
    repo = PostgresMemoryRepository(dsn="postgresql://esplicito/db")
    contributo = _contributo()
    with pytest.raises(NotImplementedError):
        repo.submit(contributo)
    with pytest.raises(NotImplementedError):
        repo.get_curated("luogo-1")
    with pytest.raises(NotImplementedError):
        repo.list_pending()
    with pytest.raises(NotImplementedError):
        repo.curate("mem-repo-1")


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
