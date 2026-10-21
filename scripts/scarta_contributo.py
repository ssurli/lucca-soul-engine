"""Scarta in modo esplicito un contributo NON curato della Urban Memory (mai DELETE).

PROVA A SECCO DI DEFAULT: la riga resta nella tabella, lo scarto imposta solo
`scartato_il`/`motivo_scarto` (`sql/05_scarto_schema.sql`); il contributo sparisce
da coda di curatela, letture pubbliche e Urban Intelligence Index. Ammesso solo
per i contributi non curati: i curati restano senza rifiuto.

Prerequisito: lo schema 05 applicato (`python -m urban_memory.migrate`).

Uso (PowerShell, dalla radice del repo):

    # elenco dei pending (id, creato_il, primi 60 caratteri del testo)
    .venv\\Scripts\\python.exe scripts\\scarta_contributo.py

    # prova a secco: mostra cosa cambierebbe, non scrive
    .venv\\Scripts\\python.exe scripts\\scarta_contributo.py --id memoria-x --motivo "fuori tema"

    # scrive davvero
    .venv\\Scripts\\python.exe scripts\\scarta_contributo.py --id memoria-x `
        --motivo "fuori tema" --esegui

Exit code: 0 successo, 1 ogni errore (contributo curato, inesistente o gia'
scartato; motivo vuoto; database non utilizzabile). Non si stampa mai
`contributor_id`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from urban_memory._env import database_url_from_env
from urban_memory.repository import (
    ContributoInesistente,
    ContributoNonScartabile,
    MemoryRepository,
    MemoryStorageError,
    MotivoScartoRichiesto,
    PostgresMemoryRepository,
)

__all__ = ["main"]

_ANTEPRIMA = 60


def _breve(testo: str | None) -> str:
    pulito = " ".join((testo or "").split())
    return pulito[:_ANTEPRIMA]


def _dsn_con_timeout(dsn: str, secondi: int = 10) -> str:
    """Aggiunge `connect_timeout` al DSN se assente (libpq su Windows puo'
    restare appeso su un host irraggiungibile)."""
    if "connect_timeout" in dsn:
        return dsn
    separatore = "&" if "?" in dsn else "?"
    return f"{dsn}{separatore}connect_timeout={secondi}"


def _elenca(repo: MemoryRepository, out: TextIO) -> int:
    pending = repo.list_pending()
    print(f"Contributi in attesa di curatela: {len(pending)}", file=out)
    for c in pending:
        print(f"{c.id} | {c.creato_il.isoformat()} | {_breve(c.testo)}", file=out)
    return 0


def esegui(
    repo: MemoryRepository,
    memory_id: str,
    motivo: str,
    *,
    scrivi: bool,
    out: TextIO | None = None,
) -> int:
    """Logica senza rete propria: il repository e' iniettato. Ritorna l'exit code."""
    out = out or sys.stdout
    print(
        "Modalita': " + ("ESECUZIONE" if scrivi else "PROVA A SECCO (nessuna scrittura)"),
        file=out,
    )
    try:
        if not motivo.strip():
            raise MotivoScartoRichiesto("il motivo di scarto e' obbligatorio")
        contributo = repo.get(memory_id)
        if contributo is None:
            raise ContributoInesistente(f"nessun contributo con id={memory_id!r}")
        if contributo.curato:
            raise ContributoNonScartabile(
                f"il contributo id={memory_id!r} e' curato: non si scarta"
            )
        if memory_id not in {c.id for c in repo.list_pending()}:
            raise ContributoNonScartabile(f"il contributo id={memory_id!r} e' gia' scartato")
        print(f"id: {contributo.id}", file=out)
        print(f"testo: {_breve(contributo.testo)}", file=out)
        print(f"motivo: {motivo.strip()}", file=out)
        if not scrivi:
            print("Nulla scritto. Aggiungi --esegui per scartare davvero.", file=out)
            return 0
        repo.scarta(memory_id, motivo)
        print(f"Scartato id={memory_id} (la riga resta, esclusa dalle letture).", file=out)
        return 0
    except (ContributoInesistente, ContributoNonScartabile, MotivoScartoRichiesto) as exc:
        print(f"ERRORE: {exc}", file=out)
        return 1


def main(argv: Sequence[str] | None = None, repo: MemoryRepository | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scarta un contributo non curato (prova a secco di default)."
    )
    parser.add_argument("--id", dest="memory_id", help="id del contributo da scartare")
    parser.add_argument("--motivo", help="motivo dello scarto (obbligatorio con --id)")
    parser.add_argument("--esegui", action="store_true", help="scrive davvero")
    args = parser.parse_args(argv)
    try:
        if repo is None:
            repo = PostgresMemoryRepository(_dsn_con_timeout(database_url_from_env()))
        if args.memory_id is None:
            if args.motivo is not None or args.esegui:
                print("ERRORE: --motivo e --esegui richiedono --id.")
                return 1
            return _elenca(repo, sys.stdout)
        return esegui(repo, args.memory_id, args.motivo or "", scrivi=args.esegui)
    except (ValueError, MemoryStorageError) as exc:
        print(f"ERRORE: configurazione o database non utilizzabili ({type(exc).__name__}).")
    except Exception as exc:
        print(f"ERRORE: operazione non riuscita ({type(exc).__name__}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
