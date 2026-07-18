"""Lettura di configurazione da variabili d'ambiente / `.env`.

Stesso pattern di `urban_memory._env` (`services/urban-memory`) e di
`graph.env.load_neo4j_config` (`services/graph`): il codice non sa MAI se
gira contro Neon (`sslmode=require`, cloud) o Postgres locale (Docker sul
PC fisso) — legge solo `DATABASE_URL` dall'ambiente. Nessun host
hardcoded, nessun `if local/cloud`.

Il Marketplace (Wave 3a) non ha bisogno di Neo4j: le prenotazioni e la
commissione vivono solo su Postgres. Per questo, a differenza di
`urban_memory._env`, qui c'è solo `database_url_from_env` — nessun
`Neo4jConfig` da leggere (il servizio non tocca mai il grafo).

Modulo privato del pacchetto (`_env`, non nell'`__all__` di `marketplace`):
non è pensato per essere importato fuori da qui.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["read_dotenv", "database_url_from_env"]


def _repo_root() -> Path:
    # services/marketplace/marketplace/_env.py -> radice del repo, 3 sopra
    # (stessa profondità di services/urban-memory/urban_memory/_env.py).
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
