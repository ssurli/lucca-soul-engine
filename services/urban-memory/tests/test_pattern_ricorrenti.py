"""Test di `TracciaRepository.pattern_ricorrenti` — l'aggregazione per
pattern (place_id + insieme di temi) che alimenta `urban_memory.ricorrenza`.
Parametrizzato con `any_traccia_repository` (InMemory + Postgres effimero,
vedi `tests/conftest.py`): un test che passa solo su una implementazione lo
segnala."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _deposita(
    repo, *, segnale_id: str, place_id: str, temi: list[str], giorni_da_base: float
) -> None:
    repo.deposita(
        segnale_id=segnale_id,
        place_id=place_id,
        temi=temi,
        creato_il=BASE + timedelta(days=giorni_da_base),
    )


def test_pattern_ricorrenti_raggruppa_temi_indipendentemente_dallordine(
    any_traccia_repository,
) -> None:
    repo = any_traccia_repository
    place_id = "piazza-anfiteatro"
    _deposita(repo, segnale_id="s1", place_id=place_id, temi=["musica", "arte"], giorni_da_base=0)
    _deposita(repo, segnale_id="s2", place_id=place_id, temi=["arte", "musica"], giorni_da_base=7)
    _deposita(repo, segnale_id="s3", place_id=place_id, temi=["musica", "arte"], giorni_da_base=14)

    pattern = repo.pattern_ricorrenti(3)

    assert len(pattern) == 1
    [p] = pattern
    assert p.place_id == place_id
    # Canonico: ordinato alfabeticamente, l'ordine di arrivo è indifferente.
    assert p.temi == ("arte", "musica")
    assert len(p.occorrenze) == 3
    assert list(p.occorrenze) == sorted(p.occorrenze)


def test_pattern_ricorrenti_esclude_sotto_soglia(any_traccia_repository) -> None:
    repo = any_traccia_repository
    _deposita(repo, segnale_id="s1", place_id="luogo-a", temi=["storia"], giorni_da_base=0)
    _deposita(repo, segnale_id="s2", place_id="luogo-a", temi=["storia"], giorni_da_base=7)

    assert repo.pattern_ricorrenti(3) == []


def test_pattern_ricorrenti_distingue_luoghi_e_temi_diversi(any_traccia_repository) -> None:
    repo = any_traccia_repository
    for i in range(3):
        giorni = i * 7.0
        _deposita(
            repo, segnale_id=f"a{i}", place_id="luogo-a", temi=["musica"], giorni_da_base=giorni
        )
        _deposita(
            repo, segnale_id=f"b{i}", place_id="luogo-b", temi=["musica"], giorni_da_base=giorni
        )
        _deposita(
            repo, segnale_id=f"c{i}", place_id="luogo-a", temi=["arte"], giorni_da_base=giorni
        )

    pattern = repo.pattern_ricorrenti(3)

    chiavi = {(p.place_id, p.temi) for p in pattern}
    assert chiavi == {
        ("luogo-a", ("musica",)),
        ("luogo-b", ("musica",)),
        ("luogo-a", ("arte",)),
    }


def test_pattern_ricorrenti_vuoto_se_nessuna_traccia(any_traccia_repository) -> None:
    repo = any_traccia_repository
    assert repo.pattern_ricorrenti(3) == []
