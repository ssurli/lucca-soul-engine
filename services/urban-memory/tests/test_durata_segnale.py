"""Test del tetto alla durata di un segnale fluttuante
(`DURATA_MASSIMA_SEGNALE_MIN` = 1440 min): `persist_signal` e CLI
`submit_signal`. Repository in-memory, `now` iniettato."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from contracts import SegnaleFluttuante
from urban_memory import submit_signal
from urban_memory.canale_fluttuante import (
    DURATA_MASSIMA_SEGNALE_MIN,
    SegnaleDurataEccessivaError,
    persist_signal,
)
from urban_memory.segnale_repository import InMemorySegnaleFluttuanteRepository

# Orologio reale (il contratto normalizza a EXPIRED un valido_fino già passato).
NOW = datetime.now(UTC)
FAR_FUTURE = NOW + timedelta(days=30)


def _segnale(minuti: int) -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id="violinista-1",
        descrizione="Un violinista suona in piazza",
        temi=["musica"],
        place_id="piazza-anfiteatro",
        non_commerciale=True,
        valido_fino=NOW + timedelta(minutes=minuti),
    )


def _tutti(repo: InMemorySegnaleFluttuanteRepository) -> list[SegnaleFluttuante]:
    return repo.fetch_attivi(NOW)


def test_tetto_e_1440() -> None:
    assert DURATA_MASSIMA_SEGNALE_MIN == 1440


def test_esattamente_il_tetto_e_accettato_e_persistito() -> None:
    repo = InMemorySegnaleFluttuanteRepository()
    segnale = _segnale(1440)

    assert persist_signal(repo, segnale, now=NOW) == segnale
    assert _tutti(repo) == [segnale]


def test_un_minuto_oltre_il_tetto_e_rifiutato_senza_persistere() -> None:
    repo = InMemorySegnaleFluttuanteRepository()

    with pytest.raises(SegnaleDurataEccessivaError):
        persist_signal(repo, _segnale(1441), now=NOW)

    assert _tutti(repo) == []
    assert repo.fetch_attivi(FAR_FUTURE - timedelta(days=1)) == []


def test_messaggio_non_vuoto_cita_il_tetto_e_nessun_troncamento() -> None:
    repo = InMemorySegnaleFluttuanteRepository()

    with pytest.raises(SegnaleDurataEccessivaError) as info:
        persist_signal(repo, _segnale(1441), now=NOW)

    msg = str(info.value)
    assert msg.strip()
    assert "1440" in msg
    # Nessuna versione accorciata (es. valido_fino = now + 1440) persistita.
    assert _tutti(repo) == []
    assert repo.fetch_attivi(NOW + timedelta(minutes=1)) == []


def test_errore_e_un_valueerror() -> None:
    assert issubclass(SegnaleDurataEccessivaError, ValueError)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _patch_cli(monkeypatch: pytest.MonkeyPatch) -> InMemorySegnaleFluttuanteRepository:
    repo = InMemorySegnaleFluttuanteRepository()
    monkeypatch.setattr(submit_signal, "migrate", lambda dsn: None)
    monkeypatch.setattr(submit_signal, "database_url_from_env", lambda: "postgresql://fake")
    monkeypatch.setattr(submit_signal, "PostgresSegnaleFluttuanteRepository", lambda dsn: repo)
    return repo


def _argv(minuti: int) -> list[str]:
    return [
        "violinista-1",
        "Un violinista suona in piazza",
        "piazza-anfiteatro",
        "--tema",
        "musica",
        "--minuti",
        str(minuti),
    ]


def test_cli_1441_minuti_esce_con_1_fallito_e_non_persiste(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _patch_cli(monkeypatch)

    with pytest.raises(SystemExit) as info:
        submit_signal.main(_argv(1441))

    assert info.value.code == 1
    assert "FALLITO" in capsys.readouterr().out
    assert repo.fetch_attivi(datetime.now(UTC)) == []
    assert repo.fetch_attivi(datetime.now(UTC) + timedelta(minutes=1)) == []


def test_cli_1440_minuti_ha_successo_e_persiste(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _patch_cli(monkeypatch)

    submit_signal.main(_argv(1440))

    out = capsys.readouterr().out
    assert "FALLITO" not in out
    assert [s.id for s in repo.fetch_attivi(datetime.now(UTC))] == ["violinista-1"]
