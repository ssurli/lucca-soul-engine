"""CLI: persiste un `SegnaleFluttuante` nel canale fluttuante —
`python -m urban_memory.submit_signal`.

Percorso RISTRETTO/FIDATO PROVVISORIO (fase-fiducia, `docs/LIMITI.md`,
CLAUDE.md): esattamente come `link_to_graph` è invocato solo da
`verify.py`/`link.py` in questo pacchetto, `urban_memory.canale_fluttuante.
persist_signal` è invocato SOLO da questa CLI. Nessuna auth, nessuna prova
di presenza, nessun rate-limit: chi ha accesso a questa shell è, per
costruzione, fidato. NON un endpoint HTTP pubblico — quello resta fuori
scope finché non esiste un canale di sottomissione reale.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL`
obbligatoria)::

    python -m urban_memory.submit_signal `
        violinista-piazza-anfiteatro-1 `
        "Un violinista suona in piazza" `
        piazza-anfiteatro `
        --tema musica --tema arte `
        --minuti 90

Applica la migrazione (idempotente) prima di persistere — stesso passo 1 di
`urban_memory.verify` — così questa CLI resta rieseguibile da zero senza un
comando `migrate` separato preventivo.

`--minuti` (default 60): quanti minuti da ORA il segnale resta valido —
`valido_fino = datetime.now(UTC) + timedelta(minutes=minuti)`, sempre
tz-aware (il contratto lo impone: `SegnaleFluttuante._valido_fino_tz_aware`).
Massimo 1440 minuti (`DURATA_MASSIMA_SEGNALE_MIN`, 24h): oltre, `persist_signal`
rifiuta con `SegnaleDurataEccessivaError` (mai troncamento) e la CLI esce con 1.

`--commerciale`: dichiara il segnale COMMERCIALE (`non_commerciale=False`).
Di default un segnale è `non_commerciale=True` — persistibile comunque se
dichiarato commerciale (questa CLI non lo blocca, per audit/storico), ma
`contracts.segnale_fluttuante_ammissibile` lo esclude SEMPRE dalla
composizione di un itinerario (`experience_engine.rules.
segnali_fluttuanti_pertinenti`, `docs/DATA_CONTRACTS.md`): "visibilità non
acquistabile" applicata al canale fluttuante.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from contracts import SegnaleFluttuante

from ._env import database_url_from_env
from .canale_fluttuante import (
    DURATA_MASSIMA_SEGNALE_MIN,
    SegnaleDurataEccessivaError,
    persist_signal,
)
from .migrate import migrate
from .segnale_repository import PostgresSegnaleFluttuanteRepository, SegnaleStorageError

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m urban_memory.submit_signal",
        description=(
            "Persiste un SegnaleFluttuante (stato=attivo, salvo che "
            "valido_fino non sia già nel passato) nel canale fluttuante "
            "persistente. Percorso ristretto/fidato provvisorio: nessun "
            "endpoint HTTP pubblico."
        ),
    )
    parser.add_argument(
        "id", help="id univoco del segnale (es. 'violinista-piazza-anfiteatro-1')."
    )
    parser.add_argument(
        "descrizione", help="cosa accade ORA (es. 'Un violinista suona in piazza')."
    )
    parser.add_argument(
        "place_id", help="id del :Luogo dove accade (deve esistere nel grafo)."
    )
    parser.add_argument(
        "--tema",
        action="append",
        dest="temi",
        required=True,
        help="un tema del segnale (ripetibile: --tema musica --tema arte). Almeno uno.",
    )
    parser.add_argument(
        "--minuti",
        type=int,
        default=60,
        help=(
            "minuti da ORA a cui il segnale scade (default: 60, massimo: "
            f"{DURATA_MASSIMA_SEGNALE_MIN}; oltre, il segnale è rifiutato)."
        ),
    )
    parser.add_argument(
        "--commerciale",
        action="store_true",
        help=(
            "dichiara il segnale COMMERCIALE (default: non_commerciale=True). "
            "ATTENZIONE: un segnale commerciale non è MAI ammissibile a valle "
            "(contracts.segnale_fluttuante_ammissibile) — persistibile qui "
            "solo per audit/storico, mai composto in un itinerario."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    dsn = database_url_from_env()

    print(f"=== Persistenza segnale fluttuante — id={args.id!r} ===\n")
    print("1. Migrazione schema (idempotente)...")
    try:
        migrate(dsn)
    except Exception as exc:  # stesso stile esplicito di verify.py: mai un traceback grezzo
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK.")

    segnale = SegnaleFluttuante(
        id=args.id,
        descrizione=args.descrizione,
        temi=list(args.temi),
        place_id=args.place_id,
        non_commerciale=not args.commerciale,
        valido_fino=datetime.now(UTC) + timedelta(minutes=args.minuti),
    )

    print("2. Persistenza...")
    repo = PostgresSegnaleFluttuanteRepository(dsn)
    try:
        persistito = persist_signal(repo, segnale)
    except SegnaleDurataEccessivaError as exc:
        print(f"   FALLITO: {exc}")
        raise SystemExit(1) from exc
    except SegnaleStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    print(
        f"   OK: stato={persistito.stato.value}  "
        f"valido_fino={persistito.valido_fino.isoformat()}"
    )
    if persistito.stato.value == "expired":
        print(
            "   AVVISO: il segnale è nato già scaduto (valido_fino era già "
            "nel passato) — normalizzato a expired dal contratto, per "
            "costruzione (nessun --minuti negativo previsto da questa CLI, "
            "ma il contratto lo gestirebbe comunque)."
        )


if __name__ == "__main__":
    main()
