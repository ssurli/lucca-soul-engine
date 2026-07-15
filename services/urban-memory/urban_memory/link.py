"""CLI: aggancia (o riverifica l'aggancio di) UN contributo già persistito
al Knowledge Graph — `python -m urban_memory.link`.

Perché esiste (a valle di un fatto osservato in produzione): `urban_memory.
verify` dimostra che un contributo persiste su Postgres — ma NON garantisce
che l'aggancio al grafo sia MAI stato eseguito davvero. Su Aura reale si
sono osservati 0 nodi `:Memoria` e nessuna relazione `RIGUARDA`, nonostante
la riga fosse già presente su Neon (`curato=True`): il passo 5 di `verify`
non era mai stato raggiunto con `NEO4J_URI` configurata (o era fallito
senza che nessuno se ne accorgesse). Questo comando è lo strumento dedicato
per eseguire — e VERIFICARE — SOLO l'aggancio, contro il dato REALMENTE
persistito (mai un contributo ricostruito in memoria: sempre riletto da
Postgres con `repo.get`).

Due modalità, mutuamente esclusive:

1. `python -m urban_memory.link [memory_id]` (default: lo stesso
   `CONTRIBUTO_ID` di `urban_memory.verify`, `"mem-verify-persistenza"`).
   Rilegge il contributo DA POSTGRES via `repo.get(memory_id)`. Se non
   esiste, ERRORE esplicito ("prima persistilo con verify") ed exit 1 — non
   un traceback opaco, non un "0 righe" silenzioso. Altrimenti lo aggancia
   al grafo con `Neo4jMemoryLinker` (ATOMICO: verifica poi scrive, nella
   stessa transazione — vedi `urban_memory.graph_link`), stampando il
   conteggio `:Memoria`/`:RIGUARDA` PRIMA e DOPO. Se `MemoryLinkError`
   viene sollevata, stampa gli id mancanti (nel messaggio dell'eccezione)
   ed esce con 1: nessun nodo orfano, mai.

2. `python -m urban_memory.link --controprova`: dimostra che il
   fallimento FORTE del linker funziona DAVVERO, SENZA toccare Postgres —
   costruisce un contributo EFFIMERO (mai persistito) con un target che
   NON esiste nel grafo, misura il conteggio `:Memoria`/`:RIGUARDA` PRIMA,
   tenta l'aggancio (DEVE fallire con `MemoryLinkError`), rimisura il
   conteggio (DEVE essere invariato). Stampa "CONTROPROVA SUPERATA" ed
   esce con 0 se il comportamento atteso si verifica; "CONTROPROVA
   FALLITA" ed esce con 1 altrimenti (il link non ha sollevato, o il
   conteggio è cambiato: un sintomo esattamente del bug corretto).

Entrambe le modalità richiedono `NEO4J_URI`/`NEO4J_USERNAME`/
`NEO4J_PASSWORD` (dal `.env`, mai hardcoded: Aura `neo4j+s://` o locale
`bolt://` dipendono solo dallo schema nella stringa) — sono le uniche che
toccano DAVVERO il grafo. La modalità 1 richiede anche `DATABASE_URL`
(per rileggere da Postgres); la modalità `--controprova` no.

Le funzioni interne (`link_memory`, `controprova`) accettano un
`Neo4jMemoryLinker` già costruito (iniettabile): la CLI vera (`main`) ne
costruisce uno reale da `.env`; i test ne passano uno costruito su un
driver FINTO (nessuna connessione reale in `tests/`).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime

from contracts import MemoryContribution, MemoryKind, PersonKind

from ._env import database_url_from_env
from .graph_link import MemoryLinkError, Neo4jMemoryLinker
from .repository import MemoryStorageError, PostgresMemoryRepository
from .verify import CONTRIBUTO_ID

__all__ = ["link_memory", "controprova", "main"]

#: id di un target che, per costruzione, non esiste nel grafo: usato SOLO
#: dalla controprova (contributo effimero, mai persistito su Postgres).
_TARGET_INESISTENTE = "id-che-non-esiste-nel-grafo"


def link_memory(memory_id: str, *, dsn: str, linker: Neo4jMemoryLinker) -> None:
    """Rilegge `memory_id` DA POSTGRES (`dsn`) e lo aggancia al grafo con
    `linker` (già costruito: iniettabile per i test). Il contributo
    agganciato è SEMPRE quello letto dal DB — mai uno ricostruito in
    memoria, per non mascherare una divergenza tra ciò che si CREDE
    persistito e ciò che è DAVVERO persistito.

    Esce con `SystemExit(1)` (dopo aver stampato un messaggio esplicito,
    mai un traceback opaco) se: il contributo non esiste su Postgres, la
    lettura fallisce (`MemoryStorageError`), o l'aggancio fallisce
    (`MemoryLinkError` — nessun nodo `:Memoria` orfano viene creato in
    ogni caso, è la garanzia della funzione che la solleva).
    """
    repo = PostgresMemoryRepository(dsn)
    try:
        contributo = repo.get(memory_id)
    except MemoryStorageError as exc:
        print(f"ERRORE: impossibile leggere da Postgres — {exc}")
        raise SystemExit(1) from exc

    if contributo is None:
        print(f"ERRORE: contributo non trovato (id={memory_id!r}) su Postgres.")
        print("        Prima persistilo: python -m urban_memory.verify")
        raise SystemExit(1)

    print(f"Contributo riletto da Postgres: id={contributo.id!r}  curato={contributo.curato}")
    print(f"  kind={contributo.kind.value}  riguarda={contributo.riguarda}")

    prima_memorie, prima_relazioni = linker.count_memoria()
    print(
        f"Prima dell'aggancio: {prima_memorie} nodo/i :Memoria, "
        f"{prima_relazioni} relazione/i :RIGUARDA."
    )

    try:
        linker.link(contributo)
    except MemoryLinkError as exc:
        # Il messaggio dell'eccezione nomina già gli id mancanti (vedi
        # `urban_memory.graph_link._link_transaction`): non c'è bisogno di
        # ricalcolarli qui, solo di non inghiottirli in silenzio.
        print(f"ERRORE: aggancio al grafo NON riuscito — {exc}")
        raise SystemExit(1) from exc

    dopo_memorie, dopo_relazioni = linker.count_memoria()
    print(
        f"Dopo l'aggancio:     {dopo_memorie} nodo/i :Memoria, "
        f"{dopo_relazioni} relazione/i :RIGUARDA."
    )
    print("OK: aggancio al grafo riuscito.")


def _contributo_controprova() -> MemoryContribution:
    """Contributo EFFIMERO (mai persistito su Postgres, mai inviato a
    `submit_contribution`): esiste solo per dimostrare che il linker
    rifiuta un target inesistente. `riguarda` punta a un id che, per
    costruzione, non esiste nel grafo."""
    return MemoryContribution(
        id="mem-controprova-link-effimero",
        kind=MemoryKind.RACCONTO,
        riguarda=[_TARGET_INESISTENTE],
        contributor_id="controprova-automatica",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime.now(UTC),
    )


def controprova(linker: Neo4jMemoryLinker) -> bool:
    """Dimostra il fallimento FORTE del linker: un target inesistente DEVE
    far sollevare `MemoryLinkError` e NON deve cambiare il conteggio
    `:Memoria`/`:RIGUARDA`. Non tocca Postgres (il contributo è effimero,
    costruito in memoria, mai `submit_contribution`-ato).

    Ritorna `True` se il comportamento atteso si verifica (la controprova
    È superata), `False` altrimenti — funzione pura rispetto a stdout/exit
    code, testabile in isolamento (la CLI in `main()` traduce il booleano
    in messaggio + codice di uscita).
    """
    contributo = _contributo_controprova()
    prima = linker.count_memoria()

    try:
        linker.link(contributo)
    except MemoryLinkError:
        dopo = linker.count_memoria()
        return dopo == prima  # nessun nodo creato: il conteggio non è cambiato

    return False  # il link avrebbe dovuto fallire: la controprova FALLISCE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m urban_memory.link",
        description=(
            "Aggancia al Knowledge Graph un contributo GIÀ PERSISTITO su "
            "Postgres (riletto con repo.get, mai ricostruito in memoria), "
            "oppure dimostra (--controprova) che un target inesistente fa "
            "fallire l'aggancio senza creare nulla."
        ),
    )
    parser.add_argument(
        "memory_id",
        nargs="?",
        default=CONTRIBUTO_ID,
        help=f"id del contributo da rileggere e agganciare (default: {CONTRIBUTO_ID!r}).",
    )
    parser.add_argument(
        "--controprova",
        action="store_true",
        help="dimostra il fallimento forte del linker SENZA toccare Postgres, poi esce.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    # NEO4J_URI/USERNAME/PASSWORD servono a ENTRAMBE le modalità (sono le
    # uniche che toccano davvero il grafo); DATABASE_URL serve solo alla
    # rilettura da Postgres, quindi è letta SOLO nel ramo non-controprova.
    with Neo4jMemoryLinker.from_env() as linker:
        if args.controprova:
            print("=== Controprova: il linker rifiuta un target inesistente ===\n")
            print(f"Target inesistente usato: {_TARGET_INESISTENTE!r}\n")
            if controprova(linker):
                print("CONTROPROVA SUPERATA: errore esplicito, nessun nodo creato.")
                return
            print("CONTROPROVA FALLITA: il linker non si è comportato come atteso.")
            raise SystemExit(1)

        dsn = database_url_from_env()
        print(f"=== Aggancio al grafo — id={args.memory_id!r} ===\n")
        link_memory(args.memory_id, dsn=dsn, linker=linker)


if __name__ == "__main__":
    main()
