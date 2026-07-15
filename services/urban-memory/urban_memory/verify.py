"""CLI di verifica: dimostra che la Urban Memory PERSISTE davvero.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL`
obbligatoria, `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` opzionali)::

    python -m urban_memory.verify

RIESEGUIBILE ALL'INFINITO: ogni passo legge PRIMA lo stato reale del
database (mai "assume che il passo precedente sia riuscito", mai scambia un
errore di storage per un successo). Ogni corsa, in ordine, stampa:

1. `migrate(DATABASE_URL)` — applica lo schema (idempotente: sicuro anche
   se già applicato in una corsa precedente).
2. Il contributo d'esempio: PRIMA `repo.get(CONTRIBUTO_ID)`. Se esiste già
   (una corsa precedente lo ha persistito), lo usa così com'è — "già
   presente" è un successo, è la prova di persistenza, non un caso da
   scartare. Se non esiste, `submit_contribution` lo crea ORA. Se
   `MemoryStorageError` viene sollevata in QUALSIASI di questi due punti
   (connessione, credenziali, un `CHECK` scattato), la CLI lo dichiara
   ESPLICITAMENTE "FALLITO" ed esce con 1 — MAI più scambiato per "id già
   presente" (bug corretto: prima confondeva "il DB non risponde" con "il
   DB ha già la riga").
3. Curatela: se il contributo è già `curato=True` (da una corsa
   precedente), lo dichiara "già curato" (successo — NON riverificata: è
   `python -m urban_memory.audit` lo strumento per scovare curati
   PRECEDENTI rimasti con target invalidi, non questo passo). Altrimenti
   `curate_contribution`. DECISIONE ARCHITETTURALE (bug reale corretto: un
   contributo con un id inesistente nel grafo era arrivato a
   `curato=True`): se `NEO4J_URI` È configurata, la curatela PASSA SEMPRE
   un `target_checker` reale (`Neo4jMemoryLinker.targets_mancanti` — vedi
   passo 5) — `InvalidTargetsError` qui è "FALLITO", exit 1, con gli id
   mancanti nominati. Se `NEO4J_URI` NON è configurata, cura senza
   verifica (comportamento precedente) ma stampa un AVVISO esplicito: la
   curatela senza grafo configurato non protegge da riferimenti invalidi.
   `KeyError` (con o senza `target_checker`) significa che il passo 2 non
   ha davvero persistito nulla: FALLITO, exit 1 — mai una spallucciata.
4. Rilegge da un repository NUOVO (`repo.get`, mai `get_curated` più il
   filtro manuale): è la prova che il dato è nel database, non solo nella
   risposta della chiamata precedente. Il messaggio distingue esplicitamente
   se il contributo è stato "persistito ORA da questa corsa" o "persisteva
   GIÀ da una corsa precedente" — non li confonde mai.
5. Se `NEO4J_URI` è configurata, aggancia al grafo IL CONTRIBUTO RILETTO AL
   PASSO 4 (mai un oggetto ricostruito in memoria) con lo STESSO
   `Neo4jMemoryLinker` già aperto per il `target_checker` del passo 3
   (ATOMICO: verifica prima, scrive poi, nella stessa transazione) e stampa
   quante `:Memoria`/`RIGUARDA` risultano nel grafo. Se `MemoryLinkError`
   viene sollevata (tipicamente: `PLACE_ID_ESEMPIO` non esiste ancora nel
   grafo di destinazione), il passo è segnalato come ERRORE ESPLICITO — mai
   in silenzio, e mai un nodo `:Memoria` orfano.

   ATTENZIONE (fatto osservato in produzione): questo passo dimostra che
   l'aggancio riesce IN QUESTA CORSA. Non dimostra che sia MAI avvenuto in
   una corsa precedente (es. se `NEO4J_URI` non era configurata quella
   volta) — per verificarlo/rieseguirlo in isolamento su un contributo già
   persistito, usa `python -m urban_memory.link [memory_id]`.

Lanciato DUE VOLTE (o una volta, poi di nuovo dopo un riavvio del
processo/macchina) mostra lo stesso contributo ancora presente al passo 4:
è la dimostrazione di persistenza reale che lo stub in-memory non poteva
dare — il fossato del progetto non può vivere solo in RAM.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import psycopg
from contracts import MemoryContribution, MemoryKind, PersonKind

from ._env import database_url_from_env, neo4j_config_from_env
from .graph_link import MemoryLinkError, Neo4jMemoryLinker
from .migrate import mask_dsn, migrate
from .repository import MemoryStorageError, PostgresMemoryRepository
from .service import InvalidTargetsError, curate_contribution, submit_contribution

CONTRIBUTO_ID = "mem-verify-persistenza"
# ATTENZIONE: deve essere un id REALE del seed del grafo (services/graph/
# graph/seed_lucca.py), non inventato — un id inesistente qui riproduce
# esattamente il bug corretto in `urban_memory.graph_link` (nodo :Memoria
# orfano). Le botteghe del seed: liuteria-lucchese, ceramica-lucca,
# stamperia-lucca, pasticceria-storica, tessitura-lucca.
PLACE_ID_ESEMPIO = "liuteria-lucchese"


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


def _verifica_postgres(
    dsn: str, *, target_checker: Callable[[list[str]], list[str]] | None
) -> MemoryContribution:
    print(f"1. Migrazione schema su {mask_dsn(dsn)} (idempotente)...")
    try:
        migrate(dsn)
    except psycopg.Error as exc:
        # Stesso pattern esplicito degli altri passi (prescrizione ethics):
        # mai un traceback grezzo al posto di un FALLITO leggibile.
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK: `memory_contribution` esiste (o esisteva già).")

    repo = PostgresMemoryRepository(dsn)

    print(f"2. Contributo d'esempio (id={CONTRIBUTO_ID!r})...")
    try:
        contributo = repo.get(CONTRIBUTO_ID)
    except MemoryStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    persistito_ora = contributo is None
    if contributo is not None:
        print("   Già presente da una corsa precedente (OK: è la prova di persistenza).")
    else:
        try:
            contributo = submit_contribution(repo, _contributo_esempio())
        except MemoryStorageError as exc:
            print(f"   FALLITO: storage non disponibile/errore — {exc}")
            raise SystemExit(1) from exc
        print("   OK: consenso e licenza validati, contributo persistito ORA.")

    print(f"3. Curatela del contributo (id={contributo.id!r})...")
    if contributo.curato:
        print("   Già curato da una corsa precedente (OK: non serve rifare la curatela).")
        print("   (non riverificato qui: usa `python -m urban_memory.audit` per gli storici)")
    else:
        if target_checker is None:
            print("   AVVISO: curatela SENZA verifica dei target — grafo non configurato")
            print("           (NEO4J_URI assente): un riferimento invalido potrebbe passare.")
        try:
            contributo = curate_contribution(repo, contributo.id, target_checker=target_checker)
        except InvalidTargetsError as exc:
            print(f"   FALLITO: target invalidi nel grafo — {exc}")
            raise SystemExit(1) from exc
        except MemoryStorageError as exc:
            print(f"   FALLITO: storage non disponibile/errore — {exc}")
            raise SystemExit(1) from exc
        except KeyError as exc:
            print(f"   FALLITO: {exc}")
            print("            (significa che il passo 2 non ha davvero persistito nulla)")
            raise SystemExit(1) from exc
        verificato = " (target verificati nel grafo)" if target_checker is not None else ""
        print(f"   OK: curato=True{verificato}.")

    print("4. Rilettura da un repository NUOVO (simula un riavvio del processo)...")
    repo_riletto = PostgresMemoryRepository(dsn)
    try:
        trovato = repo_riletto.get(CONTRIBUTO_ID)
    except MemoryStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    if trovato is None or not trovato.curato:
        print("   FALLITO: il contributo NON è stato ritrovato (curato).")
        print("            La persistenza non funziona.")
        raise SystemExit(1)

    origine = (
        "persistito ORA da questa corsa"
        if persistito_ora
        else "persisteva GIÀ da una corsa precedente"
    )
    print(f"   TROVATO ({origine}) — la memoria è ANCORA presente dopo la riapertura:")
    print(f"     id={trovato.id!r}  kind={trovato.kind.value}  licenza={trovato.licenza!r}")
    print(f"     contributor_kind={trovato.contributor_kind.value}  curato={trovato.curato}")
    print(f"     riguarda={trovato.riguarda}  creato_il={trovato.creato_il.isoformat()}")
    return trovato


def _verifica_grafo(contributo: MemoryContribution, *, linker: Neo4jMemoryLinker) -> None:
    print("5. Aggancio al Knowledge Graph (Neo4j), con il contributo RILETTO al passo 4...")
    try:
        linker.link(contributo)
        memorie, relazioni = linker.count_memoria()
        print(f"   OK: {memorie} nodo/i :Memoria, {relazioni} relazione/i :RIGUARDA nel grafo.")
    except MemoryLinkError as exc:
        # MAI silenzioso: se il link fallisce, NON è "ok" — è un errore
        # esplicito (tipicamente: PLACE_ID_ESEMPIO non esiste nel grafo di
        # destinazione, o il seed non è stato applicato con `python -m
        # graph.loader`). Nessun nodo :Memoria orfano è stato creato (è
        # esattamente ciò che questa eccezione garantisce), ma la verifica
        # va segnalata come fallita, non taciuta.
        print(f"   ERRORE: aggancio al grafo NON riuscito — {exc}")
        raise SystemExit(1) from exc


def _grafo_non_configurato() -> None:
    print(
        "5. NEO4J_URI non configurata: salto l'aggancio al grafo "
        "(solo la persistenza Postgres è stata verificata)."
    )


def main() -> None:
    print("=== Verifica di persistenza — Urban Memory ===\n")
    dsn = database_url_from_env()

    try:
        neo4j_config_from_env()
        grafo_configurato = True
    except ValueError:
        grafo_configurato = False

    if grafo_configurato:
        with Neo4jMemoryLinker.from_env() as linker:
            # Un solo driver, per l'INTERA corsa: il target_checker della
            # curatela (passo 3) e l'aggancio (passo 5) condividono lo
            # stesso `Neo4jMemoryLinker` — un solo round-trip di apertura.
            contributo = _verifica_postgres(dsn, target_checker=linker.targets_mancanti)
            print()
            _verifica_grafo(contributo, linker=linker)
    else:
        _verifica_postgres(dsn, target_checker=None)
        print()
        _grafo_non_configurato()

    print("\n=== Verifica completata ===")


if __name__ == "__main__":
    main()
