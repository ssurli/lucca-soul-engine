"""CLI di audit: verifica che NESSUN contributo CURATO abbia target
invalidi nel grafo — `python -m urban_memory.audit`.

Perché esiste (decisione architetturale del committente): la validazione
dell'esistenza dei target sta ALLA CURATELA (`urban_memory.service.
curate_contribution` con un `target_checker`), non al conferimento — il
conferimento non deve mai dipendere dalla disponibilità del grafo (Aura
Free si auto-mette in pausa dopo inattività: il Cittadino deve poter
conferire comunque). Ma questo lascia un buco per i contributi curati
PRIMA che questa barriera esistesse: un fatto reale osservato — un
contributo con `riguarda=['bottega-liuteria-1']`, un id INESISTENTE nel
grafo, era arrivato a `curato=True`. Questo comando è lo strumento di
AUDIT (sola lettura: non scrive né corregge nulla, né in Postgres né nel
grafo) da lanciare su Neon+Aura per scovare — mai correggere in automatico,
solo segnalare — quei contributi residui.

Uso (PowerShell, `.env` con `DATABASE_URL` e `NEO4J_URI`/`NEO4J_USERNAME`/
`NEO4J_PASSWORD` — ENTRAMBI obbligatori: un audit del grafo non ha senso
senza il grafo da verificare)::

    python -m urban_memory.audit

Legge da Postgres TUTTI i contributi con `curato=True`
(`MemoryRepository.list_curated`) e, per ciascuno, verifica i suoi
`riguarda` nel grafo (`Neo4jMemoryLinker.targets_mancanti`). Stampa un
report: quanti sono validi (solo un conteggio) e quali hanno target
mancanti (id del contributo + gli id mancanti). Nessun testo/PII stampato:
solo `id`, `kind`, `riguarda` (id del grafo, non contenuto) — mai
`testo`/`media_uri`/`contributor_id` (stesso principio di `urban_memory.
service`: non logga mai il payload).

Exit `0` se nessun contributo curato ha target invalidi; `1` altrimenti — è
il segnale che il committente controlla per sapere se resta lavoro da fare
(tipicamente: applicare il seed mancante nel grafo, poi far ricurare, o
correggere `riguarda` a mano).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from contracts import MemoryContribution

from ._env import database_url_from_env
from .graph_link import Neo4jMemoryLinker
from .repository import MemoryStorageError, PostgresMemoryRepository

__all__ = ["audit", "main"]


def audit(
    repo: PostgresMemoryRepository, target_checker: Callable[[list[str]], list[str]]
) -> tuple[list[MemoryContribution], list[tuple[MemoryContribution, list[str]]]]:
    """Verifica OGNI contributo curato di `repo` con `target_checker`.

    Ritorna `(validi, invalidi)`: `validi` è la lista dei contributi curati
    i cui target esistono tutti nel grafo; `invalidi` è una lista di
    `(contributo, mancanti)` per quelli che non lo sono. Funzione pura
    rispetto a stdout/exit code (testabile in isolamento, senza `.env`): è
    `main()` a tradurre il risultato in report + codice di uscita.
    """
    curati = repo.list_curated()
    validi: list[MemoryContribution] = []
    invalidi: list[tuple[MemoryContribution, list[str]]] = []
    for contributo in curati:
        mancanti = target_checker(list(contributo.riguarda))
        if mancanti:
            invalidi.append((contributo, mancanti))
        else:
            validi.append(contributo)
    return validi, invalidi


def _stampa_report(
    validi: list[MemoryContribution], invalidi: list[tuple[MemoryContribution, list[str]]]
) -> int:
    """Stampa il report in italiano e ritorna il codice di uscita (`0` se
    nessun invalido, `1` altrimenti). Separata da `main()` per essere
    testabile senza alcun I/O (`DATABASE_URL`/`NEO4J_URI`): riceve
    `(validi, invalidi)` già calcolati da `audit()`. Nessun testo/PII: solo
    `id`, `kind`, `riguarda`, `mancanti`."""
    print(f"Contributi curati VALIDI (target tutti esistenti nel grafo): {len(validi)}")
    if invalidi:
        print(f"Contributi curati INVALIDI (target mancanti nel grafo): {len(invalidi)}")
        for contributo, mancanti in invalidi:
            print(f"  - id={contributo.id!r}  kind={contributo.kind.value}")
            print(f"    riguarda={contributo.riguarda}  mancanti={mancanti!r}")
    else:
        print("Nessun contributo curato con target invalidi.")

    print()
    if invalidi:
        print(f"AUDIT FALLITO: {len(invalidi)} contributo/i curato/i con target invalidi.")
        return 1
    print("AUDIT OK: nessun contributo curato con target invalidi.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m urban_memory.audit",
        description=(
            "Verifica che NESSUN contributo CURATO (curato=True) su Postgres "
            "abbia target (riguarda) inesistenti nel Knowledge Graph. Sola "
            "lettura: non scrive e non corregge nulla, né in Postgres né nel "
            "grafo — segnala soltanto. Richiede DATABASE_URL e NEO4J_URI/"
            "NEO4J_USERNAME/NEO4J_PASSWORD nel .env (entrambi obbligatori: "
            "un audit del grafo non ha senso senza il grafo)."
        ),
    )


def main(argv: Sequence[str] = ()) -> None:
    # Parsing PRIMA di ogni lettura d'ambiente o connessione: --help esce con 0.
    # Default `()` (non `None`): senza argomenti non si legge il sys.argv del processo.
    _build_parser().parse_args(list(argv))

    print("=== Audit — contributi curati con target invalidi nel grafo ===\n")
    dsn = database_url_from_env()
    repo = PostgresMemoryRepository(dsn)

    try:
        with Neo4jMemoryLinker.from_env() as linker:
            validi, invalidi = audit(repo, linker.targets_mancanti)
    except MemoryStorageError as exc:
        print(f"FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    codice_uscita = _stampa_report(validi, invalidi)
    if codice_uscita != 0:
        raise SystemExit(codice_uscita)


if __name__ == "__main__":
    main(sys.argv[1:])
