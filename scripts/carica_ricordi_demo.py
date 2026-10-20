"""Carica 4 ricordi DIMOSTRATIVI nella Urban Memory (Lucca), in modo idempotente.

PROVA A SECCO DI DEFAULT: senza flag legge soltanto (Postgres + Neo4j in sola
lettura) e stampa cosa farebbe. `--esegui` scrive.

Passi (stessi sia a secco sia con --esegui; solo l'ultimo scrive):
1. soglia di privacy: le persone distinte (`contributor_id`) su TUTTI i
   `memory_contribution`, INCLUSO `demo-lucca-soul` come se i ricordi ci
   fossero gia', devono restare sotto `SOGLIA_MINIMA_PERSONE - 3` (cioe' < 7
   con k=10): altrimenti il ricordo demo potrebbe contribuire a far scattare
   il gate k-anonimato della dashboard. Se >= 7: nessuna scrittura, exit 1.
2. target: ogni id in `riguarda` deve esistere nel grafo (target_checker
   REALE, mai None). Se manca qualcosa: "ricarica prima il seed", exit 1 e
   NESSUNA scrittura (ci si ferma prima del submit, anche se il submit non
   dipenderebbe dal grafo: si evita di lasciare ricordi in coda non curabili).
3. per ogni id: assente -> submit + curatela (con linker reale: curato tira
   aggancio); presente non curato -> curatela; gia' curato -> nulla.

Uso (PowerShell, dalla radice del repo):

    .venv\\Scripts\\python.exe scripts\\carica_ricordi_demo.py
    .venv\\Scripts\\python.exe scripts\\carica_ricordi_demo.py --esegui

Exit code: 0 successo, 1 ogni errore. Nessun PII nei log: si stampano solo id
dei ricordi e conteggi.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TextIO

from contracts import MemoryContribution, MemoryKind, MemoryLinkState, PersonKind
from intelligence_index.soglia import SOGLIA_MINIMA_PERSONE
from urban_memory._env import database_url_from_env
from urban_memory.graph_link import Neo4jMemoryLinker
from urban_memory.repository import MemoryRepository, MemoryStorageError, PostgresMemoryRepository
from urban_memory.service import (
    curate_contribution,
    retry_link_contribution,
    submit_contribution,
)

__all__ = ["CONTRIBUTOR_DEMO", "LICENZA_DEMO", "RICORDI_DEMO", "esegui_caricamento", "main"]

CONTRIBUTOR_DEMO = "demo-lucca-soul"
LICENZA_DEMO = "CC-BY-SA-4.0"

#: (id, riguarda, testo) — testi esatti richiesti dal committente.
RICORDI_DEMO: tuple[tuple[str, str, str], ...] = (
    (
        "memoria-demo-mura-urbane",
        "mura-urbane",
        "Le Mura non sono sempre state un giardino. Fu Maria Luisa di Borbone, duchessa di "
        "Lucca dal 1817 al 1824, a trasformarle in passeggiata pubblica. Il progetto è di "
        "Lorenzo Nottolini: un viale centrale per le carrozze, due laterali per chi va a "
        "piedi. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-piazza-anfiteatro",
        "piazza-anfiteatro",
        "Circa tre metri sotto i tuoi piedi c'è ancora la base dell'anfiteatro romano del II "
        "secolo. Le case ne hanno conservato la forma ellittica; la piazza vuota al centro la "
        "aprì Nottolini nel 1830, demolendo gli edifici interni. Si entra da quattro porte, "
        "una per vertice. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-duomo-san-martino",
        "duomo-san-martino",
        "Ogni 13 settembre migliaia di lumini accendono il centro per la Luminara di Santa "
        "Croce. La processione parte da San Frediano, dove il Volto Santo fu collocato per "
        "primo, attraversa via Fillungo e piazza San Michele e arriva qui, davanti al Duomo "
        "che oggi lo custodisce. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-chiesa-san-francesco",
        "chiesa-san-francesco",
        "Qui c'è il monumento di Ugolino Visconti, detto Nino, giudice di Gallura, che Dante "
        "incontra nel Purgatorio. Nella stessa chiesa riposano due musicisti lucchesi, Luigi "
        "Boccherini e Francesco Geminiani. (esempio dimostrativo)",
    ),
)


def _costruisci(memory_id: str, riguarda: str, testo: str) -> MemoryContribution:
    return MemoryContribution(
        id=memory_id,
        kind=MemoryKind.RACCONTO,
        testo=testo,
        riguarda=[riguarda],
        contributor_id=CONTRIBUTOR_DEMO,
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza=LICENZA_DEMO,
        creato_il=datetime.now(UTC),
    )


def esegui_caricamento(
    repo: MemoryRepository,
    target_checker: Callable[[list[str]], list[str]],
    linker: Callable[[MemoryContribution], None] | None,
    *,
    esegui: bool,
    soglia_minima: int = SOGLIA_MINIMA_PERSONE,
    out: TextIO | None = None,
) -> int:
    """Logica principale, senza rete propria: repo/checker/linker iniettati.
    Ritorna l'exit code (0 ok, 1 errore)."""
    out = out or sys.stdout
    modo = "ESECUZIONE" if esegui else "PROVA A SECCO (nessuna scrittura)"
    print(f"Modalita': {modo}", file=out)

    esistenti = {c.id: c for c in repo.list_pending() + repo.list_curated()}

    # 1. soglia: persone distinte con la demo inclusa "come se ci fosse gia'".
    # Il controllo serve solo se c'e' almeno un submit da fare: curatela e retry
    # di aggancio di ricordi gia' presenti non aggiungono persone.
    ricordi = [_costruisci(*r) for r in RICORDI_DEMO]
    da_sottomettere = [r.id for r in ricordi if r.id not in esistenti]
    if da_sottomettere:
        persone = {c.contributor_id for c in esistenti.values()} | {CONTRIBUTOR_DEMO}
        limite = soglia_minima - 3
        print(
            f"Persone distinte (demo inclusa): {len(persone)}; "
            f"devono restare sotto k-3 = {limite} (k = {soglia_minima}).",
            file=out,
        )
        if len(persone) >= limite:
            print(
                f"ERRORE: {len(persone)} >= {limite}. Nessuna scrittura: il ricordo demo "
                "rischierebbe di concorrere al superamento della soglia di privacy k.",
                file=out,
            )
            return 1
    else:
        print("Nessun ricordo da sottomettere: controllo soglia non necessario.", file=out)

    # 2. target nel grafo (sola lettura)
    mancanti = target_checker(sorted({t for r in ricordi for t in r.riguarda}))
    if mancanti:
        print(
            f"ERRORE: target inesistenti nel grafo: {', '.join(mancanti)}. "
            "Ricarica prima il seed del grafo. Nessuna scrittura.",
            file=out,
        )
        return 1
    print("Target nel grafo: tutti presenti.", file=out)

    # 3. un'azione per id. Con un linker, "curato" non basta: l'invariante
    # "curato tira aggancio" vuole stato_aggancio == AGGANCIATO (None incluso =
    # non agganciato). Un curato non agganciato viene ritentato con
    # retry_link_contribution. (linker=None solo nei test di dominio puri.)
    non_agganciati: list[str] = []
    for ricordo in ricordi:
        corrente = esistenti.get(ricordo.id)
        if corrente is not None and corrente.curato:
            if linker is None or corrente.stato_aggancio == MemoryLinkState.AGGANCIATO:
                print(f"  {ricordo.id}: gia' curato e agganciato, nulla da fare.", file=out)
                continue
            if not esegui:
                print(
                    f"  {ricordo.id}: curato ma non agganciato: verrebbe ritentato "
                    "l'aggancio.",
                    file=out,
                )
                continue
            esito = retry_link_contribution(repo, ricordo.id, linker=linker)
            fatto = "aggancio ritentato"
        else:
            azione = "curerebbe" if corrente is not None else "sottometterebbe e curerebbe"
            if not esegui:
                print(f"  {ricordo.id}: {azione}.", file=out)
                continue
            if corrente is None:
                submit_contribution(repo, ricordo)
            esito = curate_contribution(
                repo, ricordo.id, target_checker=target_checker, linker=linker
            )
            fatto = "sottomesso e curato" if corrente is None else "curato"
        stato = esito.stato_aggancio.value if esito.stato_aggancio else "non tentato"
        print(f"  {ricordo.id}: {fatto} (aggancio: {stato}).", file=out)
        if linker is not None and esito.stato_aggancio != MemoryLinkState.AGGANCIATO:
            non_agganciati.append(ricordo.id)
    if non_agganciati:
        print(
            f"ERRORE: aggancio al grafo non riuscito per: {', '.join(non_agganciati)}. "
            "I ricordi sono curati ma non agganciati: rilancia lo script con --esegui "
            "(ritentera' l'aggancio).",
            file=out,
        )
        return 1
    return 0


def _dsn_con_timeout(dsn: str, secondi: int = 10) -> str:
    """Aggiunge `connect_timeout` al DSN se assente: su Windows libpq puo'
    restare appeso a tempo indefinito su un host irraggiungibile."""
    if "connect_timeout" in dsn:
        return dsn
    separatore = "&" if "?" in dsn else "?"
    return f"{dsn}{separatore}connect_timeout={secondi}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carica 4 ricordi dimostrativi (idempotente).")
    parser.add_argument(
        "--esegui", action="store_true", help="scrive davvero (default: prova a secco)"
    )
    args = parser.parse_args(argv)
    try:
        repo = PostgresMemoryRepository(_dsn_con_timeout(database_url_from_env()))
        with Neo4jMemoryLinker.from_env() as linker:
            return esegui_caricamento(
                repo, linker.targets_mancanti, linker.link, esegui=args.esegui
            )
    except (ValueError, MemoryStorageError) as exc:
        print(f"ERRORE: configurazione o database non utilizzabili ({type(exc).__name__}).")
    except Exception as exc:  # connessione Neo4j e altri errori infrastrutturali
        print(f"ERRORE: operazione non riuscita ({type(exc).__name__}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
