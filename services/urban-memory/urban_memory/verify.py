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
   un `target_checker` reale (`Neo4jMemoryLinker.targets_mancanti`) —
   `InvalidTargetsError` qui è "FALLITO", exit 1, con gli id mancanti
   nominati. Se `NEO4J_URI` NON è configurata, cura senza verifica
   (comportamento precedente) ma stampa un AVVISO esplicito: la curatela
   senza grafo configurato non protegge da riferimenti invalidi. `KeyError`
   (con o senza `target_checker`) significa che il passo 2 non ha davvero
   persistito nulla: FALLITO, exit 1 — mai una spallucciata.

   Da questa wave (Fase 3, invariante "curato tira aggancio",
   `docs/ENGINE_INVARIANTS.md` §11-B): se `NEO4J_URI` È configurata, la
   curatela passa ANCHE un `linker` reale (`Neo4jMemoryLinker.link`) — è
   QUESTO il percorso di produzione reale (l'unico oggi, in assenza di un
   endpoint HTTP di curatela — `docs/STATE_MACHINE.md` §0) che esercita
   l'automazione su dati veri: l'aggancio al grafo è innescato
   AUTOMATICAMENTE, nella stessa chiamata, subito dopo `curato=True`. Lo
   stato risultante (`MemoryContribution.stato_aggancio`, `AGGANCIATO` o
   `AGGANCIO_FALLITO`) è stampato esplicitamente. `AGGANCIO_FALLITO` non è
   un "FALLITO" della CLI: è un esito registrato, recuperabile — vedi
   passo 5.
4. Rilegge da un repository NUOVO (`repo.get`, mai `get_curated` più il
   filtro manuale): è la prova che il dato è nel database, non solo nella
   risposta della chiamata precedente. Il messaggio distingue esplicitamente
   se il contributo è stato "persistito ORA da questa corsa" o "persisteva
   GIÀ da una corsa precedente" — non li confonde mai. Stampa anche
   `stato_aggancio` così com'è REALMENTE persistito.
5. Se `NEO4J_URI` è configurata, dimostra IDEMPOTENZA/RETRY: chiama
   `retry_link_contribution` sul contributo RILETTO AL PASSO 4 (mai un
   oggetto ricostruito in memoria), con lo STESSO `Neo4jMemoryLinker` già
   condiviso dal passo 3, e stampa il conteggio `:Memoria`/`RIGUARDA` PRIMA
   e DOPO. Due scenari, distinti dallo stato letto al passo 4:
   - se il passo 3 aveva già portato `stato_aggancio=AGGANCIATO`, questo
     passo dimostra che RIESEGUIRE l'aggancio non duplica nulla (`MERGE` è
     idempotente: il conteggio "dopo" resta identico al "prima");
   - se il passo 3 aveva prodotto `AGGANCIO_FALLITO` (o se un contributo di
     una corsa precedente era rimasto curato ma mai agganciato, PRIMA che
     questa automazione esistesse), questo passo dimostra il RECUPERO: lo
     stato diventa `AGGANCIATO` e il conteggio aumenta.

   Se `retry_link_contribution` solleva un errore inatteso (storage, o un
   `UrbanMemoryError` di dominio), il passo è segnalato come ERRORE
   ESPLICITO — mai in silenzio. Per riverificare/rieseguire SOLO l'aggancio
   su un contributo già persistito, in isolamento, resta disponibile
   `python -m urban_memory.link [memory_id]`.

Lanciato DUE VOLTE (o una volta, poi di nuovo dopo un riavvio del
processo/macchina) mostra lo stesso contributo ancora presente al passo 4:
è la dimostrazione di persistenza reale che lo stub in-memory non poteva
dare — il fossato del progetto non può vivere solo in RAM.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import psycopg
from contracts import MemoryContribution, MemoryKind, MemoryLinkState, PersonKind

from ._env import city_seed_from_env, database_url_from_env, neo4j_config_from_env
from .graph_link import Neo4jMemoryLinker
from .migrate import mask_dsn, migrate
from .repository import MemoryStorageError, PostgresMemoryRepository
from .service import (
    InvalidTargetsError,
    UrbanMemoryError,
    curate_contribution,
    retry_link_contribution,
    submit_contribution,
)

CONTRIBUTO_ID = "mem-verify-persistenza"


def place_id_esempio() -> str:
    """Id d'esempio per `riguarda`: `id_esempio_memoria` del dataset scelto
    da `CITY_SEED` (ambiente > `.env`; assente -> dataset predefinito).

    Deve essere un id REALE del seed del grafo, mai inventato — un id
    inesistente qui riproduce il bug corretto in `urban_memory.graph_link`
    (nodo :Memoria orfano). Per questo viene dal dataset (validato
    all'import), non da una costante.

    `graph` è importato QUI, localmente: dipendenza della sola CLI di
    verifica, non del resto del pacchetto. `ValueError` leggibile se
    `CITY_SEED` non risolve in un dataset.
    """
    from graph.registro import carica_dataset

    return carica_dataset(city_seed_from_env()).id_esempio_memoria


def _contributo_esempio(place_id: str) -> MemoryContribution:
    return MemoryContribution(
        id=CONTRIBUTO_ID,
        kind=MemoryKind.RACCONTO,
        testo="Il racconto di una bottega di liuteria, tramandato in famiglia.",
        riguarda=[place_id],
        contributor_id="voce-di-verifica",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime.now(UTC),
    )


def _stato_aggancio_label(contributo: MemoryContribution) -> str:
    """Rappresentazione leggibile di `stato_aggancio` per lo stdout della
    CLI: `None` è un fatto legittimo (mai curato, o mai tentato), non un
    errore — va distinto da un valore reale, mai confuso con una stringa
    vuota o "N/D" che suggerirebbe un problema."""
    return contributo.stato_aggancio.value if contributo.stato_aggancio is not None else "None"


def _verifica_postgres(
    dsn: str,
    place_id: str,
    *,
    target_checker: Callable[[list[str]], list[str]] | None,
    linker: Callable[[MemoryContribution], None] | None,
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
            contributo = submit_contribution(repo, _contributo_esempio(place_id))
        except MemoryStorageError as exc:
            print(f"   FALLITO: storage non disponibile/errore — {exc}")
            raise SystemExit(1) from exc
        print("   OK: consenso e licenza validati, contributo persistito ORA.")

    print(f"3. Curatela del contributo (id={contributo.id!r})...")
    if contributo.curato:
        print("   Già curato da una corsa precedente (OK: non serve rifare la curatela).")
        print("   (non riverificato qui: usa `python -m urban_memory.audit` per gli storici)")
        print(f"   stato_aggancio={_stato_aggancio_label(contributo)} (dalla corsa precedente)")
    else:
        if target_checker is None:
            print("   AVVISO: curatela SENZA verifica dei target — grafo non configurato")
            print("           (NEO4J_URI assente): un riferimento invalido potrebbe passare.")
        try:
            contributo = curate_contribution(
                repo, contributo.id, target_checker=target_checker, linker=linker
            )
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
        if linker is not None:
            # "Curato tira aggancio" (docs/ENGINE_INVARIANTS.md §11-B): questa
            # È la curatela che innesca l'automazione su dati veri — l'unico
            # percorso di produzione reale oggi (nessun endpoint HTTP di
            # curatela: docs/STATE_MACHINE.md §0).
            print(f"   Aggancio automatico: stato_aggancio={_stato_aggancio_label(contributo)}")
            if contributo.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO:
                print(
                    "   AVVISO: aggancio automatico NON riuscito (attesa recuperabile, "
                    "mai un vicolo cieco)."
                )
                print("           Il passo 5 riprova esplicitamente (retry_link_contribution).")

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
    print(f"     stato_aggancio={_stato_aggancio_label(trovato)}")
    return trovato


def _verifica_aggancio_idempotente(
    dsn: str, memory_id: str, *, linker: Neo4jMemoryLinker
) -> None:
    """Passo 5: NON il primo aggancio (quello lo innesca già il passo 3,
    automaticamente, via `curate_contribution(..., linker=...)` — invariante
    "curato tira aggancio", `docs/ENGINE_INVARIANTS.md` §11-B). Questo passo
    dimostra invece che RIPETERE l'aggancio con `retry_link_contribution` è
    sicuro in ENTRAMBI gli scenari letti al passo 4:

    - `stato_aggancio=AGGANCIATO`: il conteggio :Memoria/:RIGUARDA PRIMA e
      DOPO resta identico — `MERGE` è idempotente, nessuna duplicazione;
    - `stato_aggancio=AGGANCIO_FALLITO` (o `None`, un contributo curato
      PRIMA che questa automazione esistesse): il conteggio AUMENTA e lo
      stato diventa `AGGANCIATO` — il RECUPERO che rende `AGGANCIO_FALLITO`
      un'attesa recuperabile, mai un vicolo cieco.

    Rilegge SEMPRE `memory_id` da un repository NUOVO (mai un oggetto
    ricostruito in memoria, mai il valore di ritorno del passo 3): stessa
    disciplina "mai assumere, sempre rileggere" del resto di questo script.
    """
    print("5. Retry dell'aggancio al Knowledge Graph — dimostra IDEMPOTENZA/RECUPERO...")
    repo = PostgresMemoryRepository(dsn)
    prima_memorie, prima_relazioni = linker.count_memoria()
    print(
        f"   Prima del retry: {prima_memorie} nodo/i :Memoria, "
        f"{prima_relazioni} relazione/i :RIGUARDA."
    )
    try:
        aggiornato = retry_link_contribution(repo, memory_id, linker=linker.link)
    except MemoryStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    except UrbanMemoryError as exc:
        # `retry_link_contribution` solleva questo SOLO se il contributo non
        # è (ancora) curato — non dovrebbe accadere qui: il passo 4 ha già
        # verificato `trovato.curato`. Segnalato comunque, mai inghiottito.
        print(f"   FALLITO: {exc}")
        raise SystemExit(1) from exc

    dopo_memorie, dopo_relazioni = linker.count_memoria()
    print(
        f"   Dopo il retry:   {dopo_memorie} nodo/i :Memoria, "
        f"{dopo_relazioni} relazione/i :RIGUARDA."
    )
    if aggiornato.stato_aggancio != MemoryLinkState.AGGANCIATO:
        # `retry_link_contribution` non propaga MAI `MemoryLinkError` (lo
        # traduce in `stato_aggancio=AGGANCIO_FALLITO`, come `curate_
        # contribution`): un aggancio ancora fallito qui è un ERRORE
        # esplicito della CLI, non un'eccezione — mai silenzioso.
        print(
            f"   ERRORE: aggancio ancora NON riuscito dopo il retry "
            f"(stato_aggancio={_stato_aggancio_label(aggiornato)}) — grafo "
            "irraggiungibile, o l'id d'esempio non esiste ancora nel grafo "
            "di destinazione (applica il seed con `python -m graph.loader`)."
        )
        raise SystemExit(1)
    print("   OK: aggancio confermato (idempotente — nessuna duplicazione).")


def _grafo_non_configurato() -> None:
    print(
        "5. NEO4J_URI non configurata: salto l'aggancio al grafo "
        "(solo la persistenza Postgres è stata verificata)."
    )


def main() -> None:
    print("=== Verifica di persistenza — Urban Memory ===\n")
    dsn = database_url_from_env()
    try:
        place_id = place_id_esempio()
    except ValueError as exc:
        print(f"FALLITO: CITY_SEED non risolvibile — {exc}")
        raise SystemExit(1) from exc

    try:
        neo4j_config_from_env()
        grafo_configurato = True
    except ValueError:
        grafo_configurato = False

    if grafo_configurato:
        with Neo4jMemoryLinker.from_env() as linker:
            # Un solo driver, per l'INTERA corsa: il target_checker/linker
            # della curatela (passo 3 — invariante "curato tira aggancio")
            # e il retry di verifica (passo 5) condividono lo stesso
            # Neo4jMemoryLinker — un solo round-trip di apertura.
            contributo = _verifica_postgres(
                dsn, place_id, target_checker=linker.targets_mancanti, linker=linker.link
            )
            print()
            _verifica_aggancio_idempotente(dsn, contributo.id, linker=linker)
    else:
        _verifica_postgres(dsn, place_id, target_checker=None, linker=None)
        print()
        _grafo_non_configurato()

    print("\n=== Verifica completata ===")


if __name__ == "__main__":
    main()
