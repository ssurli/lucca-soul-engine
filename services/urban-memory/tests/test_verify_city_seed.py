"""`verify.place_id_esempio`: l'id d'esempio viene dal dataset scelto da
`CITY_SEED`, mai da una costante. Nessuna connessione a Neon/Aura: si testa
solo la scelta dell'id e l'uscita d'errore della CLI PRIMA di ogni I/O.

Isolamento: nel repo esiste un `.env` reale. `_repo_root` viene puntato a una
cartella vuota e `CITY_SEED` tolta dall'ambiente, così nessun valore reale
influenza i test (e nessun valore viene letto o stampato).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from graph.registro import carica_dataset
from urban_memory import _env, verify


@pytest.fixture(autouse=True)
def _ambiente_isolato(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(_env, "_repo_root", lambda: tmp_path)  # niente .env reale
    monkeypatch.delenv("CITY_SEED", raising=False)


def test_city_seed_assente_usa_il_dataset_predefinito() -> None:
    assert verify.place_id_esempio() == carica_dataset(None).id_esempio_memoria


def test_city_seed_da_dotenv_isolato(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("CITY_SEED=\n", encoding="utf-8")
    assert verify.place_id_esempio() == carica_dataset(None).id_esempio_memoria


def test_city_seed_invalido_fallisce_in_modo_leggibile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CITY_SEED", "citta-che-non-esiste")
    with pytest.raises(ValueError, match="CITY_SEED"):
        verify.place_id_esempio()


def test_cli_esce_con_errore_se_city_seed_invalido(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CITY_SEED", "Non Valido!")
    monkeypatch.setattr(verify, "database_url_from_env", lambda: "postgresql://x/y")
    with pytest.raises(SystemExit) as exc_info:
        verify.main()
    assert exc_info.value.code == 1
    assert "CITY_SEED" in capsys.readouterr().out
