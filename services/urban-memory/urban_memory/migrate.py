"""Migrazione idempotente dello schema di Urban Memory (Postgres/Neon).

Applica OGNI file `sql/*_schema.sql` — letto da file (single source of
verità, non duplicato come stringa nel codice), rieseguibile da zero in un
comando, come il seed del grafo (CLAUDE.md). Due schemi oggi, applicati IN
ORDINE (il prefisso numerico ne fissa l'ordine, `sorted()` su nomi di file):

- `00_memory_schema.sql` — `memory_contribution` (Wave 2, la Urban Memory).
- `01_fluttuante_schema.sql` — `segnale_fluttuante`/`traccia_luogo` (Fase 3,
  il canale fluttuante persistente e il suo ledger,
  `docs/PROMOZIONE_TRACCIA.md`).

Un solo comando applica ENTRAMBI, in una connessione, in una transazione
sola (`conn.execute`/`conn.commit` una volta sola per tutti i file): non
serve un comando `migrate` per schema, esattamente come prima di questo
cambio non ne serviva uno per `00_memory_schema.sql` da solo.

Uso::

    python -m urban_memory.migrate          # legge DATABASE_URL dal .env
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import psycopg

from ._env import database_url_from_env

__all__ = ["SCHEMA_PATH", "SCHEMA_PATHS", "migrate", "mask_dsn", "main"]

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

#: Mantenuto per compatibilità (era l'UNICO schema prima di questa wave):
#: continua a puntare a `00_memory_schema.sql`, mai rimosso né ridefinito.
SCHEMA_PATH = _SQL_DIR / "00_memory_schema.sql"

#: TUTTI gli schemi versionati di questo servizio, in ordine di applicazione
#: (il prefisso numerico del nome file ne fissa l'ordine): quello che
#: `migrate()` applica davvero, da questa wave in poi.
SCHEMA_PATHS: tuple[Path, ...] = tuple(sorted(_SQL_DIR.glob("*_schema.sql")))


def migrate(dsn: str) -> None:
    """Applica OGNI schema in `SCHEMA_PATHS` (`CREATE TABLE`/`INDEX ... IF
    NOT EXISTS`) su `dsn`, in ordine, in una sola connessione.

    Idempotente: rieseguibile senza errori né duplicazioni, sullo stesso
    principio del seed del grafo (`services/graph/cypher/`) — ogni file SQL
    è a sua volta idempotente (`CREATE ... IF NOT EXISTS`, mai un `DROP`),
    quindi applicarli di nuovo (es. dopo l'aggiunta di
    `01_fluttuante_schema.sql` su un database che aveva già solo
    `00_memory_schema.sql`) è un no-op sul primo e crea solo ciò che manca
    sul secondo. `dsn` arriva SEMPRE da chi chiama (mai letto qui da
    `os.environ`): usa `database_url_from_env()` per costruirlo a partire da
    `DATABASE_URL`.
    """
    with psycopg.connect(dsn) as conn:
        for path in SCHEMA_PATHS:
            conn.execute(path.read_text(encoding="utf-8"))
        conn.commit()


def mask_dsn(dsn: str) -> str:
    """Rappresentazione di `dsn` sicura da stampare: nasconde la password
    (se presente nella stringa) dietro `***`. Usata da `verify.py` e dalla
    CLI di migrazione: non si logga mai una credenziale per intero."""
    if "://" not in dsn:
        return dsn
    schema, _, resto = dsn.partition("://")
    userinfo, _, hostpart = resto.partition("@")
    if not hostpart:
        return dsn  # nessun "@": niente userinfo da nascondere
    if ":" in userinfo:
        user, _, _password = userinfo.partition(":")
        userinfo = f"{user}:***"
    return f"{schema}://{userinfo}@{hostpart}"


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m urban_memory.migrate",
        description=(
            "Applica in modo idempotente gli schemi SQL della Urban Memory "
            "(sql/*_schema.sql, in ordine). ATTENZIONE: SI CONNETTE e SCRIVE sul "
            "database di DATABASE_URL (.env o ambiente): per Neon usa la stringa "
            "diretta, senza -pooler."
        ),
    )


def main(argv: Sequence[str] = ()) -> None:
    # Parsing PRIMA di ogni lettura d'ambiente o connessione: --help esce con 0.
    # Default `()` (non `None`): senza argomenti non si legge il sys.argv del processo.
    _build_parser().parse_args(list(argv))
    dsn = database_url_from_env()
    migrate(dsn)
    print(f"Schema Urban Memory applicato (idempotente) su {mask_dsn(dsn)}.")
    for path in SCHEMA_PATHS:
        print(f"Sorgente: {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
