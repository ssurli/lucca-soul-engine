"""Prova dell'isolamento anche nella seconda invocazione della CI (`pytest services/...`).

Il conftest di RADICE e' l'unico responsabile; qui si verifica solo l'effetto.
"""

from __future__ import annotations

import os

import pytest
from api import deps
from api.settings import ENV_FILE, get_settings
from graph.source import Neo4jCandidateSource, SeedCandidateSource


@pytest.mark.parametrize(
    "nome",
    ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE", "DATABASE_URL",
     "ANTHROPIC_API_KEY"],
)
def test_nessuna_variabile_di_infrastruttura(nome: str) -> None:
    assert nome not in os.environ


def test_settings_e_getter_senza_infrastruttura() -> None:
    assert not ENV_FILE.exists()
    impostazioni = get_settings()
    assert impostazioni.neo4j_uri is None
    assert impostazioni.database_url is None
    sorgente = deps.get_candidate_source()
    assert isinstance(sorgente, SeedCandidateSource)
    assert not isinstance(sorgente, Neo4jCandidateSource)
    assert type(deps.get_memory_repository()).__name__.startswith("InMemory")
