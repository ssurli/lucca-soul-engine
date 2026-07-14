"""Migrazione idempotente dello schema di Urban Memory (Postgres/Neon).

Applica `sql/00_memory_schema.sql` — letto da file (single source of verità,
non duplicato come stringa nel codice), rieseguibile da zero in un comando,
come il seed del grafo (CLAUDE.md).

Uso::

    python -m urban_memory.migrate          # legge DATABASE_URL dal .env
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from ._env import database_url_from_env

__all__ = ["SCHEMA_PATH", "migrate", "mask_dsn", "main"]

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SCHEMA_PATH = _SQL_DIR / "00_memory_schema.sql"


def migrate(dsn: str) -> None:
    """Applica lo schema (`CREATE TABLE`/`INDEX ... IF NOT EXISTS`) su `dsn`.

    Idempotente: rieseguibile senza errori né duplicazioni, sullo stesso
    principio del seed del grafo (`services/graph/cypher/`). `dsn` arriva
    SEMPRE da chi chiama (mai letto qui da `os.environ`): usa
    `database_url_from_env()` per costruirlo a partire da `DATABASE_URL`.
    """
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(sql)
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


def main() -> None:
    dsn = database_url_from_env()
    migrate(dsn)
    print(f"Schema Urban Memory applicato (idempotente) su {mask_dsn(dsn)}.")
    print(f"Sorgente: {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
