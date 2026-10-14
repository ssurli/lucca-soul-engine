"""Test di `TracciaRepository.tracce_per_luoghi` (lettura batch per il
bagliore, docs/PROMOZIONE_TRACCIA.md §2b). Parametrizzato con
`any_traccia_repository` (InMemory + Postgres effimero: il ramo Postgres
salta se il cluster non e' disponibile)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _dep(repo, sid: str, place: str, giorni: float, temi=("arte",)):
    return repo.deposita(
        segnale_id=sid, place_id=place, temi=list(temi), creato_il=BASE + timedelta(days=giorni)
    )


def test_vuoto_restituisce_dict_vuoto(any_traccia_repository) -> None:
    repo = any_traccia_repository
    assert repo.tracce_per_luoghi([]) == {}
    _dep(repo, "s1", "luogo-a", 0)
    assert repo.tracce_per_luoghi([]) == {}


def test_luoghi_assenti_non_presenti(any_traccia_repository) -> None:
    repo = any_traccia_repository
    _dep(repo, "s1", "luogo-a", 0)
    out = repo.tracce_per_luoghi(["luogo-a", "luogo-senza-tracce"])
    assert set(out) == {"luogo-a"}
    assert repo.tracce_per_luoghi(["luogo-senza-tracce"]) == {}


def test_duplicati_in_input_tollerati(any_traccia_repository) -> None:
    repo = any_traccia_repository
    _dep(repo, "s1", "luogo-a", 0)
    _dep(repo, "s2", "luogo-a", 1)
    out = repo.tracce_per_luoghi(["luogo-a", "luogo-a", "luogo-a"])
    assert set(out) == {"luogo-a"}
    assert len(out["luogo-a"]) == 2  # nessuna traccia duplicata nell'output


def test_ordine_creato_il_poi_id(any_traccia_repository) -> None:
    repo = any_traccia_repository
    _dep(repo, "s3", "luogo-a", 10)
    _dep(repo, "s1", "luogo-a", 0)
    _dep(repo, "s2", "luogo-a", 5)
    _dep(repo, "s4", "luogo-a", 5)  # stesso istante: spareggio per id
    righe = repo.tracce_per_luoghi(["luogo-a"])["luogo-a"]
    chiavi = [(t.creato_il, t.id) for t in righe]
    assert chiavi == sorted(chiavi)
    assert righe[0].segnale_id == "s1"
    assert righe[-1].segnale_id == "s3"
    assert len(righe) == 4


def test_filtro_per_luogo(any_traccia_repository) -> None:
    repo = any_traccia_repository
    _dep(repo, "s1", "luogo-a", 0)
    _dep(repo, "s2", "luogo-b", 1)
    _dep(repo, "s3", "luogo-c", 2)
    out = repo.tracce_per_luoghi(["luogo-a", "luogo-c"])
    assert set(out) == {"luogo-a", "luogo-c"}
    assert all(t.place_id == "luogo-a" for t in out["luogo-a"])
    assert [t.segnale_id for t in out["luogo-c"]] == ["s3"]


def test_coerente_con_list_for_place(any_traccia_repository) -> None:
    repo = any_traccia_repository
    for i in range(4):
        _dep(repo, f"s{i}", "luogo-a", i * 3, temi=("arte", "musica"))
    assert repo.tracce_per_luoghi(["luogo-a"])["luogo-a"] == repo.list_for_place("luogo-a")
