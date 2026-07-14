"""CLI di verifica: dimostra che la Urban Memory PERSISTE davvero.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL`
obbligatoria, `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` opzionali)::

    python -m urban_memory.verify

Cosa fa, in ordine, stampando ogni passo in italiano:

1. `migrate(DATABASE_URL)` — applica lo schema (idempotente: sicuro anche
   se già applicato in una corsa precedente).
2. `submit_contribution` di un contributo d'esempio (consenso=True, licenza
   tracciata, `kind=racconto`, agganciato a un place noto).
3. `curate_contribution` — la revisione umana prima della pubblicazione.
4. Rilegge il contributo appena curato da `get_curated` e lo stampa: è la
   prova che il dato è nel database, non solo nella risposta della prima
   chiamata.
5. Se `NEO4J_URI` è configurata, esegue `link_to_graph` e stampa quante
   `:Memoria`/`RIGUARDA` risultano nel grafo.

Lanciato DUE VOLTE (o una volta, poi di nuovo dopo un riavvio del
processo/macchina) mostra lo stesso contributo ancora presente al passo 4:
è la dimostrazione di persistenza reale che lo stub in-memory non poteva
dare — il fossato del progetto non può vivere solo in RAM.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contracts import MemoryContribution, MemoryKind, PersonKind

from ._env import database_url_from_env, neo4j_config_from_env
from .migrate import mask_dsn, migrate
from .repository import MemoryStorageError, PostgresMemoryRepository
from .service import curate_contribution, submit_contribution

CONTRIBUTO_ID = "mem-verify-persistenza"
PLACE_ID_ESEMPIO = "bottega-liuteria-1"


def _contributo_esempio() -> MemoryContribution:
    return MemoryContribution(
        id=CONTRIBUTO_ID,
        kind=MemoryKind.RACCONTO,
        testo="Il racconto di una bottega di liuteria, tramandato in famiglia.",
        riguarda=[PLACE_ID_ESEMPIO],
        contributor_id="voce-di-verifica",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime.now(UTC),
    )


def _verifica_postgres(dsn: str) -> MemoryContribution:
    print(f"1. Migrazione schema su {mask_dsn(dsn)} (idempotente)...")
    migrate(dsn)
    print("   OK: `memory_contribution` esiste (o esisteva già).")

    repo = PostgresMemoryRepository(dsn)

    contributo = _contributo_esempio()
    print(f"2. Conferimento del contributo d'esempio (id={contributo.id!r})...")
    try:
        submit_contribution(repo, contributo)
        print("   OK: consenso e licenza validati, contributo persistito.")
    except MemoryStorageError as exc:
        print(f"   (submit non ripetuto: {exc}")
        print("    id già presente da una corsa precedente — previsto, non un errore)")

    print(f"3. Curatela del contributo (id={contributo.id!r})...")
    try:
        curate_contribution(repo, contributo.id)
        print("   OK: curato=True.")
    except KeyError as exc:
        print(f"   ATTENZIONE: {exc}")

    print("4. Rilettura da un repository NUOVO (simula un riavvio del processo)...")
    repo_riletto = PostgresMemoryRepository(dsn)
    pubblicati = repo_riletto.get_curated(PLACE_ID_ESEMPIO)
    trovato = next((c for c in pubblicati if c.id == CONTRIBUTO_ID), None)
    if trovato is None:
        print("   FALLITO: il contributo NON è stato ritrovato. La persistenza non funziona.")
        raise SystemExit(1)
    print("   TROVATO — la memoria è ANCORA presente dopo la riapertura della connessione:")
    print(f"     id={trovato.id!r}  kind={trovato.kind.value}  licenza={trovato.licenza!r}")
    print(f"     contributor_kind={trovato.contributor_kind.value}  curato={trovato.curato}")
    print(f"     riguarda={trovato.riguarda}  creato_il={trovato.creato_il.isoformat()}")
    return trovato


def _verifica_grafo(contributo: MemoryContribution) -> None:
    try:
        neo4j_config_from_env()
    except ValueError:
        print(
            "5. NEO4J_URI non configurata: salto l'aggancio al grafo "
            "(solo la persistenza Postgres è stata verificata)."
        )
        return

    from .graph_link import Neo4jMemoryLinker

    print("5. Aggancio al Knowledge Graph (Neo4j)...")
    with Neo4jMemoryLinker.from_env() as linker:
        linker.link(contributo)
        memorie, relazioni = linker.count_memoria()
        print(f"   OK: {memorie} nodo/i :Memoria, {relazioni} relazione/i :RIGUARDA nel grafo.")


def main() -> None:
    print("=== Verifica di persistenza — Urban Memory ===\n")
    dsn = database_url_from_env()
    contributo = _verifica_postgres(dsn)
    print()
    _verifica_grafo(contributo)
    print("\n=== Verifica completata ===")


if __name__ == "__main__":
    main()
