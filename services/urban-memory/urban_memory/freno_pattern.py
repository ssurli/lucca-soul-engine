"""Il freno di emergenza su un `:Evento` promosso (Fase 3,
`docs/STATE_MACHINE.md` §4-bis(b)) — `python -m urban_memory.freno_pattern
tira|rilascia`.

Percorso RISTRETTO/FIDATO PROVVISORIO, stesso principio di
`curatela_pattern.py`/`frizione_pattern.py`/`submit_signal.py`
(`docs/LIMITI.md`, CLAUDE.md): nessuna auth, nessun rate-limit, chi ha
accesso a questa shell è, per costruzione, fidato. Un comando invocato
MANUALMENTE, MAI integrato in `/itinerary`, nell'Experience Engine o in
qualunque altro path del motore.

**Overlay, non una quarta voce di `stato`.** Il freno sopprime la
RACCOMANDAZIONE (`services/api/api/main.py`, `EventoRicorrente.frenato`),
mai il deposito della traccia: mentre è tirato, il ledger continua a
registrare veritieramente ciò che accade (`docs/PROMOZIONE_TRACCIA.md` §1).
Scrive SEMPRE e SOLO `e.frenato` (`62_freno_stato_write.cypher`,
`MATCH`+`SET` puro, mai un `MERGE`) — MAI `e.stato`, che resta di esclusiva
competenza di `urban_memory.frizione_pattern` (il ciclo di vita ordinario,
§4-bis(a)). Al rilascio, il pattern torna a QUALUNQUE stato la frizione
automatica indichi in quel momento — perché questo modulo non tocca mai
`e.stato`, non perché lo "ripristini" esplicitamente.

**Motivazione testuale OBBLIGATORIA su ogni tiro, opzionale al rilascio**
(`docs/STATE_MACHINE.md` §4-bis(b): "motivazione testuale obbligatoria su
ogni tiro" — il testo non lo richiede per il rilascio). `tira_freno` senza
motivazione (assente o vuota) solleva `ValueError` PRIMA di scrivere
qualunque cosa — né sul grafo né nel log Postgres (`pattern_frenato`,
`urban_memory.freno_repository`).

**Lista nominale di permessi (§4-bis(b) — "titolare di permesso-freno
individuale, sottoinsieme nominale di Promotori") — DELIBERATAMENTE FUORI
SCOPE in questa v1.** Il design la CONGELA come principio ("permesso
individuale, non capacità del ruolo") ma la marca esplicitamente come
**residuo di implementazione, non ancora deciso** (§7.14.1, item 16: "chi
amministra la lista... dove vive... con quale meccanismo" — APERTO). Fino a
quel task, questo comando resta un percorso ristretto via shell (stesso
principio di `curatela_pattern.py`/`frizione_pattern.py`): nessun
grant/revoke, nessuna lista nominale, nessun doppio-occhio (due firme) qui
— costruirli ora anticiperebbe una decisione di governance non ancora
presa, non colmerebbe un vuoto.

`tira_freno`/`rilascia_freno` sono funzioni PURE rispetto all'I/O reale
(ricevono `writer`/`repo` iniettati, mai costruiti al loro interno) —
RICHIAMABILI SEPARATAMENTE da `main()`, stesso principio di
`curatela_pattern.promuovi_pattern`/`rifiuta_pattern`: il percorso
non-interattivo usato dai test.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL` e
`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` obbligatorie)::

    python -m urban_memory.freno_pattern tira --evento-id evento-x `
        --attore "promotore-uno" --motivazione "ordinanza comunale immediata"

    python -m urban_memory.freno_pattern rilascia --evento-id evento-x `
        --attore "promotore-uno"

In alternativa a `--evento-id` (l'id tecnico), un operatore che conosce il
pattern ma non l'id può passare `--place-id`+`--temi` (temi separati da
virgola): l'id è risolto DETERMINISTICAMENTE via
`promozione_evento.evento_id_per_pattern` — nessuna lettura extra dal grafo
per risolverlo, stessa tecnica già usata alla promozione."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ._env import database_url_from_env, neo4j_config_from_env
from .freno_repository import (
    FrenoStorageError,
    PatternFrenato,
    PatternFrenatoRepository,
    PostgresPatternFrenatoRepository,
)
from .migrate import migrate
from .promozione_evento import evento_id_per_pattern

__all__ = [
    "FRENO_STATO_WRITE_QUERY_PATH",
    "freno_stato_write_cypher",
    "FrenoPatternError",
    "scrivi_freno_evento",
    "Neo4jFrenoClient",
    "tira_freno",
    "rilascia_freno",
    "main",
]

_logger = logging.getLogger(__name__)

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
FRENO_STATO_WRITE_QUERY_PATH = _CYPHER_DIR / "62_freno_stato_write.cypher"


def freno_stato_write_cypher(evento_id: str, frenato: bool) -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `62_freno_stato_write.cypher`: nessuna
    connessione, nessuna esecuzione, nessun effetto collaterale oltre alla
    lettura statica del file `.cypher` versionato."""
    query = FRENO_STATO_WRITE_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {"evento_id": evento_id, "frenato": frenato}
    return query, params


class FrenoPatternError(Exception):
    """Errore INFRASTRUTTURALE (grafo irraggiungibile — Aura in pausa, rete
    assente, credenziali non valide) durante la scrittura del freno — NON un
    errore di dominio, stesso ruolo di
    `frizione_pattern.FrizionePatternError`. Un `evento_id` inesistente
    (più?) nel grafo è un no-op silenzioso (`MATCH` puro), mai un errore."""


class _Result(Protocol):
    def data(self) -> list[dict[str, Any]]: ...


class _Session(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc_info: object) -> None: ...


class _Driver(Protocol):
    def session(self, database: str | None = None) -> _Session: ...

    def close(self) -> None: ...


def scrivi_freno_evento(
    evento_id: str, frenato: bool, *, driver: _Driver, database: str | None = None
) -> None:
    """Scrive `e.frenato = frenato` per l'`:Evento` con id `evento_id` —
    `MATCH`+`SET` puro, mai un `MERGE`, e MAI tocca `e.stato`. No-op
    silenzioso se `evento_id` non esiste (più?) nel grafo (nessun nodo
    fantasma creato). Solleva `FrenoPatternError` se il grafo è
    irraggiungibile."""
    query, params = freno_stato_write_cypher(evento_id, frenato)
    try:
        with driver.session(database=database) as session:
            session.run(query, params)
    except FrenoPatternError:
        raise  # già il tipo giusto: non ri-avvolgere
    except Exception as exc:
        raise FrenoPatternError(
            f"grafo irraggiungibile durante la scrittura del freno "
            f"(evento_id={evento_id!r}, frenato={frenato!r}): {exc}"
        ) from exc


class Neo4jFrenoClient:
    """Wrapper comodo: possiede un driver Neo4j aperto UNA VOLTA (non a ogni
    scrittura) e lo riusa — stesso pattern di
    `frizione_pattern.Neo4jFrizioneClient`/
    `promozione_evento.Neo4jPromozioneWriter`. Un client GEMELLO, non una
    riutilizzazione di `Neo4jFrizioneClient`: quello legge/scrive lo stato
    ordinario (`e.stato`), questo scrive solo il freno (`e.frenato`) — due
    responsabilità distinte, stessa disciplina del resto del servizio (la
    frizione decide `stato`, il freno decide `frenato`)."""

    def __init__(self, driver: _Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Neo4jFrenoClient:
        """Costruisce leggendo `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
        `NEO4J_DATABASE` dal `.env` (radice del repo) o dall'ambiente di
        processo."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        return cls(driver, database=cfg.database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jFrenoClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def imposta_frenato(self, evento_id: str, frenato: bool) -> None:
        """Scrive il freno, riusando il driver posseduto da questa istanza.
        Firma pensata per essere passata direttamente come `writer` a
        `tira_freno`/`rilascia_freno` (metodo legato)."""
        scrivi_freno_evento(evento_id, frenato, driver=self._driver, database=self._database)


#: Firma di un "writer" del freno — tipicamente
#: `Neo4jFrenoClient.imposta_frenato` (metodo legato): riceve
#: `(evento_id, frenato)`, nessun ritorno. Un `Protocol`/callable astratto,
#: mai un `Neo4jFrenoClient` concreto nella firma di `tira_freno`/
#: `rilascia_freno`: testabile con un writer finto senza toccare Neo4j —
#: stesso principio di `curatela_pattern._Writer`.
_Writer = Callable[[str, bool], None]


def tira_freno(
    evento_id: str,
    *,
    attore: str,
    motivazione: str,
    writer: _Writer,
    repo: PatternFrenatoRepository,
    place_id: str | None = None,
    temi: Sequence[str] | None = None,
    quando: datetime | None = None,
) -> PatternFrenato:
    """Tira il freno su `evento_id`: sopprime la raccomandazione senza
    toccare `e.stato` (`docs/STATE_MACHINE.md` §4-bis(b)).

    `motivazione` è OBBLIGATORIA (non un campo opzionale) — se assente o
    vuota (dopo `.strip()`), solleva `ValueError` PRIMA di chiamare
    `writer`/`repo`: NESSUNA scrittura, né sul grafo né nel log
    `pattern_frenato`. Verificato ESPLICITAMENTE dai test: la validazione è
    il primo passo di questa funzione, non un controllo a valle.

    Scrive `e.frenato = true` (via `writer`, tipicamente
    `Neo4jFrenoClient.imposta_frenato`) E una riga in `pattern_frenato` con
    `azione='tirato'` (via `repo.registra`) — MAI `e.stato`. Logga anche la
    transizione (chi=`attore`, quando, evento_id, motivazione) — stesso
    principio di `curatela_pattern.promuovi_pattern`/`rifiuta_pattern`, ma a
    salienza distinguibile in audit da una transizione automatica della
    frizione (`docs/STATE_MACHINE.md` §4-bis(b): "log a salienza massima").

    `attore` è OBBLIGATORIO (pseudonimo di chi agisce, MAI PII) — se assente
    o vuoto (dopo `.strip()`), solleva `ValueError` PRIMA di chiamare
    `writer`/`repo`, stessa guardia di `motivazione` sopra: un `attore`
    vuoto scriverebbe `e.frenato=true` sul grafo (`writer`) e poi
    fallirebbe silenziosamente (o peggio, con `InMemoryPatternFrenatoRepository`,
    senza fallire affatto) su `repo.registra` — un freno tirato senza alcuna
    riga di audit recuperabile su chi/quando/perché, in violazione di
    `docs/STATE_MACHINE.md` §4-bis(b) ("log a salienza massima,
    distinguibile in audit"). Validato QUI, non lasciato al `CHECK` DB
    (`pattern_frenato_attore_check`), che resta comunque un backstop."""
    if not attore or not attore.strip():
        raise ValueError(
            "attore obbligatorio (pseudonimo di chi agisce) — nessuna scrittura effettuata"
        )
    if not motivazione or not motivazione.strip():
        raise ValueError(
            "motivazione obbligatoria per tirare il freno "
            "(docs/STATE_MACHINE.md §4-bis(b)) — nessuna scrittura effettuata"
        )
    quando = quando or datetime.now(UTC)

    writer(evento_id, True)
    riga = repo.registra(
        evento_id=evento_id,
        place_id=place_id,
        temi=list(temi) if temi else [],
        azione="tirato",
        attore=attore,
        motivazione=motivazione,
        quando=quando,
    )
    _logger.warning(  # WARNING, non INFO: freno di emergenza, salienza massima
        "FRENO TIRATO (evento_id=%s, place_id=%s, temi=%s, attore=%s, "
        "motivazione=%r, quando=%s)",
        evento_id,
        place_id,
        temi,
        attore,
        motivazione,
        quando.isoformat(),
    )
    return riga


def rilascia_freno(
    evento_id: str,
    *,
    attore: str,
    writer: _Writer,
    repo: PatternFrenatoRepository,
    motivazione: str | None = None,
    place_id: str | None = None,
    temi: Sequence[str] | None = None,
    quando: datetime | None = None,
) -> PatternFrenato:
    """Rilascia il freno su `evento_id`: `motivazione` è OPZIONALE (a
    differenza del tiro — `docs/STATE_MACHINE.md` §4-bis(b) la richiede solo
    "su ogni tiro"). Scrive `e.frenato = false` (mai `e.stato`: il pattern
    torna a QUALUNQUE stato il ciclo di vita ordinario indica in quel
    momento, perché questa funzione non lo tocca) e una riga in
    `pattern_frenato` con `azione='rilasciato'`. Logga la transizione.

    `attore` è OBBLIGATORIO (stessa guardia, stesso motivo di `tira_freno`
    sopra) — se assente o vuoto (dopo `.strip()`), solleva `ValueError`
    PRIMA di chiamare `writer`/`repo`: nessuna scrittura, né sul grafo né
    nel log."""
    if not attore or not attore.strip():
        raise ValueError(
            "attore obbligatorio (pseudonimo di chi agisce) — nessuna scrittura effettuata"
        )
    quando = quando or datetime.now(UTC)

    writer(evento_id, False)
    riga = repo.registra(
        evento_id=evento_id,
        place_id=place_id,
        temi=list(temi) if temi else [],
        azione="rilasciato",
        attore=attore,
        motivazione=motivazione,
        quando=quando,
    )
    _logger.info(
        "freno rilasciato (evento_id=%s, place_id=%s, temi=%s, attore=%s, "
        "motivazione=%r, quando=%s)",
        evento_id,
        place_id,
        temi,
        attore,
        motivazione,
        quando.isoformat(),
    )
    return riga


def _risolvi_evento_id(args: argparse.Namespace) -> tuple[str, str | None, tuple[str, ...]]:
    """`--evento-id` diretto, oppure `--place-id`+`--temi` risolto
    DETERMINISTICAMENTE via `evento_id_per_pattern` (nessuna lettura dal
    grafo: stessa tecnica già usata alla promozione). `_build_parser` sotto
    garantisce che uno dei due sia presente (gruppo mutuamente esclusivo,
    richiesto) e che `--temi` accompagni sempre `--place-id`."""
    if args.evento_id:
        return args.evento_id, None, ()
    temi_grezzi = args.temi or ""
    temi = tuple(sorted(t.strip() for t in temi_grezzi.split(",") if t.strip()))
    if not temi:
        raise SystemExit("--temi (separati da virgola) è obbligatorio insieme a --place-id")
    evento_id = evento_id_per_pattern(args.place_id, temi)
    return evento_id, args.place_id, temi


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m urban_memory.freno_pattern",
        description=(
            "Tira o rilascia il freno di emergenza su un :Evento promosso "
            "(docs/STATE_MACHINE.md §4-bis(b)): sopprime la raccomandazione "
            "senza toccare il ciclo di vita automatico (e.stato). Percorso "
            "ristretto/fidato: nessun endpoint HTTP pubblico, MAI invocato "
            "da /itinerary o dal motore."
        ),
    )
    sottocomandi = parser.add_subparsers(dest="azione", required=True)

    def _aggiungi_argomenti_target(sub: argparse.ArgumentParser) -> None:
        gruppo = sub.add_mutually_exclusive_group(required=True)
        gruppo.add_argument("--evento-id", type=str, default=None, help="id tecnico del :Evento")
        gruppo.add_argument(
            "--place-id", type=str, default=None, help="id del :Luogo (richiede --temi)"
        )
        sub.add_argument(
            "--temi", type=str, default=None, help="temi separati da virgola (con --place-id)"
        )
        sub.add_argument(
            "--attore", type=str, required=True, help="pseudonimo di chi agisce, MAI PII"
        )

    tira_parser = sottocomandi.add_parser("tira", help="Tira il freno (sopprime la tappa)")
    _aggiungi_argomenti_target(tira_parser)
    tira_parser.add_argument(
        "--motivazione", type=str, required=True, help="OBBLIGATORIA su ogni tiro"
    )

    rilascia_parser = sottocomandi.add_parser("rilascia", help="Rilascia il freno")
    _aggiungi_argomenti_target(rilascia_parser)
    rilascia_parser.add_argument(
        "--motivazione", type=str, default=None, help="opzionale al rilascio"
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    dsn = database_url_from_env()

    print("=== Freno di emergenza — Urban Memory ===\n")
    print("1. Migrazione schema (idempotente)...")
    try:
        migrate(dsn)
    except Exception as exc:  # stesso stile esplicito di frizione_pattern.py
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK.")

    evento_id, place_id, temi = _risolvi_evento_id(args)
    repo: PatternFrenatoRepository = PostgresPatternFrenatoRepository(dsn)

    try:
        with Neo4jFrenoClient.from_env() as client:
            if args.azione == "tira":
                print(f"2. Tiro del freno su {evento_id!r}...")
                try:
                    riga = tira_freno(
                        evento_id,
                        attore=args.attore,
                        motivazione=args.motivazione,
                        writer=client.imposta_frenato,
                        repo=repo,
                        place_id=place_id,
                        temi=temi,
                    )
                except ValueError as exc:
                    print(f"   RIFIUTATO: {exc}")
                    raise SystemExit(1) from exc
                print(f"   OK: freno TIRATO (riga id={riga.id!r}).")
            else:  # "rilascia" — l'unico altro sottocomando ammesso dal parser
                print(f"2. Rilascio del freno su {evento_id!r}...")
                riga = rilascia_freno(
                    evento_id,
                    attore=args.attore,
                    motivazione=args.motivazione,
                    writer=client.imposta_frenato,
                    repo=repo,
                    place_id=place_id,
                    temi=temi,
                )
                print(f"   OK: freno RILASCIATO (riga id={riga.id!r}).")
    except FrenoStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # stesso stile esplicito di frizione_pattern.py
        print(f"   FALLITO: grafo non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    print("\n=== Freno completato ===")


if __name__ == "__main__":
    main()
