"""Test di `urban_memory.freno_repository` — il log permanente del freno di
emergenza (Fase 3, `docs/STATE_MACHINE.md` §4-bis(b)). Parametrizzato con
`any_freno_repository` (InMemory + Postgres effimero, vedi
`tests/conftest.py`): un test che passa solo su una implementazione lo
segnala. `PostgresPatternFrenatoRepository` è SALTATA (non fallita) se il
cluster Postgres 16 effimero non è disponibile in questo ambiente.

A DIFFERENZA di `test_cestino_repository.py`: nessun test di idempotenza —
il freno non ha `UNIQUE`, ogni `registra` è sempre una riga nuova."""

from __future__ import annotations

from datetime import UTC, datetime

QUANDO = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def test_registra_un_tiro(any_freno_repository) -> None:
    repo = any_freno_repository

    riga = repo.registra(
        evento_id="evento-piazza-anfiteatro-arte-musica",
        place_id="piazza-anfiteatro",
        temi=["musica", "arte"],
        azione="tirato",
        attore="promotore-uno",
        motivazione="ordinanza comunale immediata",
        quando=QUANDO,
    )

    assert riga.evento_id == "evento-piazza-anfiteatro-arte-musica"
    assert riga.azione == "tirato"
    assert riga.attore == "promotore-uno"
    assert riga.motivazione == "ordinanza comunale immediata"
    assert riga.id


def test_registra_un_rilascio_senza_motivazione(any_freno_repository) -> None:
    repo = any_freno_repository

    riga = repo.registra(
        evento_id="evento-x",
        place_id=None,
        temi=[],
        azione="rilasciato",
        attore="promotore-uno",
        motivazione=None,
        quando=QUANDO,
    )

    assert riga.azione == "rilasciato"
    assert riga.motivazione is None


def test_tiri_e_rilasci_ripetuti_sono_righe_multiple(any_freno_repository) -> None:
    """Nessun `UNIQUE`: tirare e rilasciare più volte lo stesso evento_id
    produce righe SEPARATE, mai un upsert."""
    repo = any_freno_repository

    repo.registra(
        evento_id="evento-x",
        place_id=None,
        temi=[],
        azione="tirato",
        attore="promotore-uno",
        motivazione="primo tiro",
        quando=QUANDO,
    )
    repo.registra(
        evento_id="evento-x",
        place_id=None,
        temi=[],
        azione="rilasciato",
        attore="promotore-uno",
        motivazione=None,
        quando=QUANDO,
    )
    repo.registra(
        evento_id="evento-x",
        place_id=None,
        temi=[],
        azione="tirato",
        attore="promotore-due",
        motivazione="secondo tiro, motivo diverso",
        quando=QUANDO,
    )

    righe = repo.per_evento("evento-x")
    assert len(righe) == 3
    assert [riga.azione for riga in righe] == ["tirato", "rilasciato", "tirato"]
    # Nessuna riga sovrascritta: ID tutti distinti.
    assert len({riga.id for riga in righe}) == 3
