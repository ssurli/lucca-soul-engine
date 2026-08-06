"""Test di `urban_memory.cestino_repository` — il cestino permanente dei
pattern rifiutati (Fase 3, promozione a `:Evento`). Parametrizzato con
`any_cestino_repository` (InMemory + Postgres effimero, vedi
`tests/conftest.py`): un test che passa solo su una implementazione lo
segnala. `PostgresPatternCestinatoRepository` è SALTATA (non fallita) se il
cluster Postgres 16 effimero non è disponibile in questo ambiente."""

from __future__ import annotations

from datetime import UTC, datetime

QUANDO = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def test_cestina_registra_il_pattern(any_cestino_repository) -> None:
    repo = any_cestino_repository

    cestinato = repo.cestina(
        place_id="piazza-anfiteatro",
        temi=["musica", "arte"],
        promotore="promotore-uno",
        cestinato_il=QUANDO,
        motivo="troppo raro per essere un ritmo",
    )

    assert cestinato.place_id == "piazza-anfiteatro"
    assert cestinato.temi == ("arte", "musica"), "canonico: ordinato alfabeticamente"
    assert cestinato.promotore == "promotore-uno"
    assert cestinato.motivo == "troppo raro per essere un ritmo"
    assert cestinato.id


def test_cestina_motivo_e_opzionale(any_cestino_repository) -> None:
    repo = any_cestino_repository

    cestinato = repo.cestina(
        place_id="luogo-x", temi=["storia"], promotore="promotore-uno", cestinato_il=QUANDO
    )

    assert cestinato.motivo is None


def test_e_cestinato_vero_dopo_cestina(any_cestino_repository) -> None:
    repo = any_cestino_repository
    repo.cestina(
        place_id="luogo-x", temi=["storia", "arte"], promotore="promotore-uno", cestinato_il=QUANDO
    )

    assert repo.e_cestinato("luogo-x", ["arte", "storia"]) is True, "ordine dei temi indifferente"


def test_e_cestinato_falso_per_pattern_mai_cestinato(any_cestino_repository) -> None:
    repo = any_cestino_repository
    assert repo.e_cestinato("luogo-mai-visto", ["musica"]) is False


def test_e_cestinato_falso_per_temi_diversi_stesso_luogo(any_cestino_repository) -> None:
    repo = any_cestino_repository
    repo.cestina(
        place_id="luogo-x", temi=["storia"], promotore="promotore-uno", cestinato_il=QUANDO
    )

    assert repo.e_cestinato("luogo-x", ["musica"]) is False


def test_cestina_e_idempotente_per_lo_stesso_pattern(any_cestino_repository) -> None:
    """Un pattern cestinato resta cestinato PER SEMPRE (v1): una seconda
    chiamata a `cestina` per lo STESSO pattern non crea una seconda riga —
    ritorna quella esistente, la decisione ORIGINALE non viene mai
    sovrascritta."""
    repo = any_cestino_repository
    primo = repo.cestina(
        place_id="luogo-x", temi=["storia"], promotore="promotore-1", cestinato_il=QUANDO
    )
    secondo = repo.cestina(
        place_id="luogo-x",
        temi=["storia"],
        promotore="promotore-2",
        cestinato_il=QUANDO,
        motivo="motivo diverso, arrivato dopo",
    )

    assert primo.id == secondo.id
    assert secondo.promotore == "promotore-1"
    assert secondo.motivo is None
