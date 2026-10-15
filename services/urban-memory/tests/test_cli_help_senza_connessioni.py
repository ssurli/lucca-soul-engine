"""`--help` di `verify` e `migrate` stampa l'aiuto ed esce con 0 SENZA leggere
l'ambiente e SENZA aprire connessioni (prima di questa correzione queste CLI
non avevano argparse: `--help` le eseguiva davvero contro il database).

Sicurezza: i sottoprocessi ricevono SOLO DSN non raggiungibili (porta 1 su
loopback) e credenziali fittizie; l'ambiente di processo ha la precedenza sul
`.env` (`_env._merged_env`), quindi nessun valore reale viene mai usato.
"""

from __future__ import annotations

import os
import subprocess
import sys
from types import ModuleType

import pytest
from urban_memory import migrate, verify

MODULI = ["verify", "migrate"]

_ENV_FITTIZIO = {
    "DATABASE_URL": "postgresql://u:p@127.0.0.1:1/x",
    "NEO4J_URI": "neo4j+s://127.0.0.1:1",
    "NEO4J_USERNAME": "fittizio",
    "NEO4J_PASSWORD": "fittizia",
}


@pytest.mark.parametrize("nome", MODULI)
def test_help_in_sottoprocesso_esce_0_senza_connessioni(nome: str) -> None:
    env = {**os.environ, **_ENV_FITTIZIO}
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    risultato = subprocess.run(
        [sys.executable, "-m", f"urban_memory.{nome}", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )
    assert risultato.returncode == 0, risultato.stderr
    assert f"python -m urban_memory.{nome}" in risultato.stdout
    assert "usage" in risultato.stdout.lower()
    # Nessun tentativo di connessione: niente errori di rete né output di corsa.
    assert "Traceback" not in risultato.stderr
    assert "refused" not in (risultato.stdout + risultato.stderr).lower()
    assert "===" not in risultato.stdout


@pytest.mark.parametrize("modulo", [verify, migrate], ids=MODULI)
def test_help_in_process_non_tocca_ambiente_ne_connessioni(
    modulo: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _vietato(*_args: object, **_kwargs: object) -> None:
        pytest.fail("--help non deve leggere l'ambiente né aprire connessioni")

    for nome in ("database_url_from_env", "migrate", "neo4j_config_from_env", "place_id_esempio"):
        if hasattr(modulo, nome):
            monkeypatch.setattr(modulo, nome, _vietato)
    if modulo is verify:
        monkeypatch.setattr(verify.Neo4jMemoryLinker, "from_env", classmethod(_vietato))
        monkeypatch.setattr(verify, "PostgresMemoryRepository", _vietato)

    with pytest.raises(SystemExit) as exc_info:
        modulo.main(["--help"])
    assert exc_info.value.code == 0


@pytest.mark.parametrize("modulo", [verify, migrate], ids=MODULI)
def test_main_senza_argomenti_non_legge_sys_argv(
    modulo: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`main()` senza argv non deve ereditare il `sys.argv` del processo
    (sotto pytest conterrebbe le opzioni di pytest e argparse uscirebbe con 2)."""
    monkeypatch.setattr(sys, "argv", ["prog", "--opzione-sconosciuta"])

    def _ferma(*_a: object, **_k: object) -> str:
        raise RuntimeError("raggiunto-l-ambiente")

    monkeypatch.setattr(modulo, "database_url_from_env", _ferma)
    with pytest.raises(RuntimeError, match="raggiunto-l-ambiente"):
        modulo.main()
