"""`python -m graph.loader` — (ri)popola Neo4j da zero, in un solo comando.

Esegue, in ordine, gli script versionati in `cypher/`:

1. `00_schema.cypher` — vincoli e indici (`CREATE ... IF NOT EXISTS`:
   idempotente);
2. `01_seed_<città>.cypher` — nodi e relazioni del dataset della città scelta
   da `CITY_SEED` (`graph.registro`; `MERGE`: idempotente).

Aura Free cancella l'istanza dopo 30 giorni di inattività: il grafo è un
ARTEFATTO RICOSTRUIBILE, non un archivio. Questo comando è l'unico modo
supportato per popolarlo, sia su Aura sia su Neo4j Community in locale — la
differenza tra i due profili sta solo nel `.env` (`neo4j+s://` vs
`bolt://`), mai nel codice.

Uso (PowerShell, dalla radice del repo, dopo `pip install -e packages/
contracts -e services/graph` e con `.env` compilato):

    python -m graph.loader
"""

from __future__ import annotations

import sys
from pathlib import Path

from neo4j import GraphDatabase

from graph.env import Neo4jConfig, load_neo4j_config
from graph.registro import CYPHER_DIR, dataset_attivo, file_seed_cypher

SCHEMA_FILE = CYPHER_DIR / "00_schema.cypher"


def _statements(path: Path) -> list[str]:
    """Spezza un file `.cypher` in singole istruzioni eseguibili.

    Convenzione dei file generati da `graph.export_cypher`: ogni istruzione
    termina con `;` seguito da newline, i commenti sono righe che iniziano
    con `//`. Nessuna istruzione del seed contiene `;` dentro una stringa
    letterale (i valori del dataset non lo richiedono).
    """
    text = path.read_text(encoding="utf-8")
    statements: list[str] = []
    for chunk in text.split(";\n"):
        righe_utili = [
            line for line in chunk.splitlines() if not line.strip().startswith("//")
        ]
        stmt = "\n".join(righe_utili).strip()
        if stmt:
            statements.append(stmt)
    return statements


def run(config: Neo4jConfig, seed_file: Path | None = None) -> int:
    """Esegue schema + seed su Neo4j. Ritorna il numero di istruzioni eseguite.

    `seed_file=None` -> il seed della città attiva (`CITY_SEED`)."""
    seed = seed_file if seed_file is not None else file_seed_cypher(dataset_attivo())
    driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))
    eseguite = 0
    try:
        driver.verify_connectivity()
        with driver.session(database=config.database) as session:
            for path in (SCHEMA_FILE, seed):
                for statement in _statements(path):
                    session.run(statement)
                    eseguite += 1
    finally:
        driver.close()
    return eseguite


def main() -> None:
    try:
        config = load_neo4j_config()
    except ValueError as exc:
        print(f"Configurazione Neo4j mancante: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    seed_file = file_seed_cypher(dataset_attivo())
    eseguite = run(config, seed_file)
    print(
        f"OK: {eseguite} istruzioni Cypher eseguite su database={config.database!r} "
        f"({SCHEMA_FILE.name} + {seed_file.name})."
    )


if __name__ == "__main__":
    main()
