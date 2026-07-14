"""Lettura di configurazione da variabili d'ambiente / `.env`.

Helper condiviso da `repository.py` (`DATABASE_URL`) e `graph_link.py`
(`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE`) — stesso
pattern di `graph.env.load_neo4j_config` (`services/graph`, fuori dal
perimetro di questo servizio): il codice non sa MAI se gira contro Aura/Neon
(cloud) o locale — legge solo l'ambiente. Nessun host hardcoded, nessun `if
local/cloud`.

Modulo privato del pacchetto (`_env`, non nell'`__all__` di `urban_memory`):
non è pensato per essere importato fuori da qui.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Neo4jConfig",
    "read_dotenv",
    "database_url_from_env",
    "neo4j_config_from_env",
]


def _repo_root() -> Path:
    # services/urban-memory/urban_memory/_env.py -> radice del repo, 3 sopra
    # (stessa profondità di services/graph/graph/env.py).
    return Path(__file__).resolve().parents[3]


def read_dotenv(path: Path) -> dict[str, str]:
    """Parser minimale di `.env`: KEY=VALUE, righe vuote e `#commenti`
    ignorati, virgolette attorno al valore rimosse. Nessuna dipendenza da
    `python-dotenv`: qui basta questo."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _merged_env(dotenv_path: Path | None) -> dict[str, str]:
    env = read_dotenv(dotenv_path or (_repo_root() / ".env"))
    env.update(os.environ)  # l'ambiente di processo ha sempre la precedenza
    return env


def database_url_from_env(dotenv_path: Path | None = None) -> str:
    """Legge `DATABASE_URL` dal `.env` (radice del repo) o dall'ambiente di
    processo. Neon (`sslmode=require`) o Postgres locale dipendono SOLO da
    questo valore: nessun host hardcoded, nessun `if local/cloud` qui.

    Solleva `ValueError` se manca: fallire qui, in modo leggibile, è meglio
    che fallire dentro il driver con un errore di rete generico.
    """
    dsn = _merged_env(dotenv_path).get("DATABASE_URL")
    if not dsn:
        raise ValueError("DATABASE_URL mancante nel .env o nell'ambiente")
    return dsn


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"


def neo4j_config_from_env(dotenv_path: Path | None = None) -> Neo4jConfig:
    """Legge `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE`
    dal `.env` (radice del repo) o dall'ambiente di processo. Nessun host
    hardcoded, nessun `if local/cloud`: Aura (`neo4j+s://`) o locale
    (`bolt://`) dipendono solo dallo schema dentro `NEO4J_URI`.

    Solleva `ValueError` con l'elenco delle variabili mancanti se
    `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` non sono tutte presenti
    (`NEO4J_DATABASE` è opzionale, default `"neo4j"`).
    """
    env = _merged_env(dotenv_path)
    required = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError(
            "variabili Neo4j mancanti nel .env o nell'ambiente: " + ", ".join(missing)
        )
    return Neo4jConfig(
        uri=env["NEO4J_URI"],
        username=env["NEO4J_USERNAME"],
        password=env["NEO4J_PASSWORD"],
        database=env.get("NEO4J_DATABASE") or "neo4j",
    )
