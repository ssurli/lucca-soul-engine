"""Lettura delle credenziali Neo4j da variabili d'ambiente / `.env`.

Il codice non sa MAI se gira contro Aura (`neo4j+s://`) o contro Neo4j
Community in locale (`bolt://`): legge solo `NEO4J_URI`, `NEO4J_USERNAME`,
`NEO4J_PASSWORD`, `NEO4J_DATABASE`. Nessun host hardcoded, nessun `if
local/cloud` — lo schema dell'URI vive solo nel `.env` che l'utente sceglie.

Usato da `graph.loader` (`python -m graph.loader`). `graph.source.
Neo4jCandidateSource` NON legge l'ambiente da sé: riceve URI/credenziali dal
costruttore, così chi lo chiama (qui, o un servizio a valle) resta libero di
scegliere la fonte di configurazione.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REQUIRED = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"


def _repo_root() -> Path:
    # services/graph/graph/env.py -> radice del repo, 3 livelli sopra.
    return Path(__file__).resolve().parents[3]


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parser minimale di `.env`: KEY=VALUE, righe vuote e `#commenti`
    ignorati, virgolette attorno al valore rimosse. Niente dipendenza da
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


def load_neo4j_config(dotenv_path: Path | None = None) -> Neo4jConfig:
    """Legge NEO4J_URI/USERNAME/PASSWORD/DATABASE dal `.env` (radice del
    repo) e dall'ambiente di processo (che ha sempre la precedenza sul file).

    Solleva `ValueError` con l'elenco delle variabili mancanti se la
    configurazione non è completa: fallire in modo leggibile qui è meglio che
    fallire dentro il driver Neo4j con un errore di rete generico.
    """
    env = _read_dotenv(dotenv_path or (_repo_root() / ".env"))
    env.update(os.environ)

    missing = [key for key in _REQUIRED if not env.get(key)]
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


def city_seed_da_env(dotenv_path: Path | None = None) -> str | None:
    """Legge `CITY_SEED` (slug del dataset di città) con la STESSA precedenza
    di `load_neo4j_config`: ambiente di processo > `.env` di radice.

    Ritorna `None` se non è impostata o è vuota: sarà il registro
    (`graph.registro`) a applicare il predefinito. Nessuna validazione qui."""
    env = _read_dotenv(dotenv_path or (_repo_root() / ".env"))
    env.update(os.environ)
    valore = env.get("CITY_SEED", "").strip()
    return valore or None
