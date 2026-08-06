"""Guard strutturale: `experience_engine` non deve MAI importare
`urban_memory` (CLAUDE.md — "Decide un solo componente": l'AI Experience
Engine dipende SOLO dai contratti; grafo e RAG sono INIETTATI, mai importati
— vedi `services/experience-engine/pyproject.toml`). Se questo dovesse
diventare vero, la purezza del motore ("un vincolo applicato in un solo
punto è verificabile") si romperebbe da un servizio che, per costruzione,
non deve nemmeno sapere che `urban_memory` esiste.

Verificato SUL CODICE SORGENTE (`ast`), non tramite import runtime: stesso
principio del test-guard AST già in uso in questo repo
(`services/experience-engine/tests/test_engine.py::
test_scoring_non_usa_partner_id_ne_prezzo`), qui applicato all'INTERO
pacchetto `experience_engine`, non a una singola funzione. Legge i file da
disco: non richiede che `experience_engine` sia installato nello stesso
ambiente/venv di `urban_memory` per essere eseguito."""

from __future__ import annotations

import ast
from pathlib import Path

# services/urban-memory/tests/test_x.py -> .parents[2] == services/
_EXPERIENCE_ENGINE_DIR = (
    Path(__file__).resolve().parents[2] / "experience-engine" / "experience_engine"
)


def _moduli_importati(albero: ast.AST) -> set[str]:
    nomi: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            nomi.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nomi.add(nodo.module.split(".")[0])
    return nomi


def test_experience_engine_dir_esiste() -> None:
    # Se questo fallisce, il test seguente sarebbe un falso "verde" per
    # percorso sbagliato, non per purezza reale: fallire rumorosamente.
    assert _EXPERIENCE_ENGINE_DIR.is_dir(), (
        f"atteso {_EXPERIENCE_ENGINE_DIR} — layout del repo cambiato?"
    )


def test_experience_engine_non_importa_mai_urban_memory() -> None:
    moduli_python = list(_EXPERIENCE_ENGINE_DIR.rglob("*.py"))
    assert moduli_python, "nessun modulo .py trovato: il guard non starebbe verificando nulla"

    for path in moduli_python:
        albero = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        importati = _moduli_importati(albero)
        assert "urban_memory" not in importati, (
            f"{path} importa 'urban_memory': viola la purezza dell'AI "
            "Experience Engine (CLAUDE.md — grafo/RAG/memoria sono "
            "INIETTATI, mai importati dal motore)."
        )
