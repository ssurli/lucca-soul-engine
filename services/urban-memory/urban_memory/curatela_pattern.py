"""CLI di curatela: rileva i pattern ricorrenti dal ledger delle tracce e li
presenta al Promotore per la decisione — `python -m
urban_memory.curatela_pattern`.

Percorso RISTRETTO/FIDATO PROVVISORIO (stesso principio di
`submit_signal.py`/`verify.py`, `docs/LIMITI.md`, CLAUDE.md): nessuna auth,
nessun rate-limit, chi ha accesso a questa shell è, per costruzione, fidato.
NON un endpoint HTTP pubblico — quello resta fuori scope.

Nessuna promozione o rifiuto è MAI automatica: ogni pattern candidato viene
deciso da un umano (il Promotore), uno alla volta, mai in batch silenzioso.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL` e
`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` obbligatorie: il RILEVAMENTO
stesso consulta il grafo, per escludere dai candidati un pattern GIÀ
promosso — vedi `ricorrenza.rileva_candidati`, parametro `evento_esistente`.
Un rifiuto, una volta presentato il pattern, non tocca comunque mai il
grafo)::

    python -m urban_memory.curatela_pattern

Per ogni pattern candidato stampa `place_id`, `temi`, numero di occorrenze,
cadenza stimata (giorni) e coefficiente di variazione; chiede una decisione
(`a`pprova / `r`ifiuta / `s`alta) e, se necessario, il nome del Promotore
(uno pseudonimo, MAI PII) e — solo per il rifiuto — un motivo opzionale.

`promuovi_pattern`/`rifiuta_pattern` sono funzioni RICHIAMABILI
SEPARATAMENTE da `main()`: il percorso non-interattivo usato dai test (e da
un'eventuale futura interfaccia diversa dal prompt testuale)."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from ._env import database_url_from_env
from .cestino_repository import (
    PatternCestinato,
    PatternCestinatoRepository,
    PostgresPatternCestinatoRepository,
)
from .migrate import migrate
from .promozione_evento import Neo4jPromozioneWriter, PromozioneEventoError
from .ricorrenza import PatternCandidato, rileva_candidati
from .traccia_repository import PostgresTracciaRepository, TracciaRepository

__all__ = ["promuovi_pattern", "rifiuta_pattern", "main"]

_logger = logging.getLogger(__name__)

#: Firma di un "writer" di promozione — tipicamente
#: `promozione_evento.Neo4jPromozioneWriter.promuovi` (metodo legato):
#: riceve `(place_id, temi, cadenza_giorni, promotore)`, ritorna `evento_id`
#: o solleva `PromozioneEventoError`. `promotore` è INOLTRATO fino al grafo
#: (`:Evento.promosso_da`/`ultimo_ricalcolo_da`): l'atto di promozione
#: scrive struttura PERMANENTE e PUBBLICA, l'accountability persistente
#: conta più che per un rifiuto, non meno — un log applicativo non basta
#: (correzione ethics-guardian). Un `Protocol`/callable astratto, mai un
#: `Neo4jPromozioneWriter` concreto nella firma: testabile con un writer
#: finto senza toccare Neo4j.
_Writer = Callable[[str, tuple[str, ...], float, str], str]


def promuovi_pattern(candidato: PatternCandidato, *, promotore: str, writer: _Writer) -> str:
    """Promuove `candidato` a `:Evento` tramite `writer` (il grafo è sempre
    INIETTATO, mai costruito qui — stesso principio del resto del servizio),
    inoltrandogli `promotore` così l'accountability persiste SUL NODO
    (`promosso_da`/`ultimo_ricalcolo_da`), non solo nel log applicativo.
    Logga ANCHE la transizione `candidato -> promosso` (chi=Promotore,
    quando, quale pattern, cadenza). Ritorna `evento_id`.

    Propaga `PromozioneEventoError` se la scrittura fallisce (place_id
    inesistente nel grafo, o grafo irraggiungibile): in quel caso NESSUNA
    riga viene scritta da nessuna parte (né grafo, né cestino) — il pattern
    resta CANDIDATO, ricomparirà al prossimo rilevamento."""
    evento_id = writer(candidato.place_id, candidato.temi, candidato.cadenza_giorni, promotore)
    _logger.info(
        "transizione: candidato -> promosso (place_id=%s, temi=%s, "
        "cadenza_giorni=%.2f, evento_id=%s, promotore=%s, quando=%s)",
        candidato.place_id,
        candidato.temi,
        candidato.cadenza_giorni,
        evento_id,
        promotore,
        datetime.now(UTC).isoformat(),
    )
    return evento_id


def rifiuta_pattern(
    candidato: PatternCandidato,
    cestino_repo: PatternCestinatoRepository,
    *,
    promotore: str,
    motivo: str | None = None,
) -> PatternCestinato:
    """Cestina PERMANENTEMENTE il pattern (place_id + temi) di `candidato`
    (mai la singola candidata-del-momento). Logga la transizione
    `candidato -> cestinato` (chi=Promotore, quando, quale pattern,
    motivo). Non tocca mai il grafo."""
    quando = datetime.now(UTC)
    cestinato = cestino_repo.cestina(
        place_id=candidato.place_id,
        temi=list(candidato.temi),
        promotore=promotore,
        cestinato_il=quando,
        motivo=motivo,
    )
    _logger.info(
        "transizione: candidato -> cestinato (place_id=%s, temi=%s, "
        "motivo=%r, promotore=%s, quando=%s)",
        candidato.place_id,
        candidato.temi,
        motivo,
        promotore,
        quando.isoformat(),
    )
    return cestinato


def _stampa_candidato(indice: int, totale: int, candidato: PatternCandidato) -> None:
    print(f"\n--- Pattern candidato {indice}/{totale} ---")
    print(f"  place_id          : {candidato.place_id}")
    print(f"  temi              : {', '.join(candidato.temi)}")
    print(f"  occorrenze        : {len(candidato.occorrenze)}")
    print(f"  cadenza stimata   : {candidato.cadenza_giorni:.1f} giorni")
    print(f"  coefficiente var. : {candidato.coefficiente_variazione:.3f}")


def _chiedi(prompt: str) -> str:
    return input(prompt).strip()


def _esegui_interattivo(
    candidati: list[PatternCandidato],
    *,
    cestino_repo: PatternCestinatoRepository,
    writer: _Writer,
) -> None:
    for indice, candidato in enumerate(candidati, start=1):
        _stampa_candidato(indice, len(candidati), candidato)
        decisione = _chiedi("Decisione [a]pprova / [r]ifiuta / [s]alta: ").lower()
        if decisione in ("a", "approva"):
            promotore = _chiedi("Promotore (pseudonimo, mai PII): ")
            try:
                evento_id = promuovi_pattern(candidato, promotore=promotore, writer=writer)
            except PromozioneEventoError as exc:
                print(f"  FALLITO: {exc}")
                continue
            print(f"  OK: promosso a :Evento (id={evento_id!r}).")
        elif decisione in ("r", "rifiuta"):
            promotore = _chiedi("Promotore (pseudonimo, mai PII): ")
            motivo = _chiedi("Motivo (opzionale, invio per saltare): ") or None
            rifiuta_pattern(candidato, cestino_repo, promotore=promotore, motivo=motivo)
            print("  OK: pattern cestinato (permanente).")
        else:
            print("  Saltato: nessuna decisione presa ora (ricomparirà al prossimo rilevamento).")


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m urban_memory.curatela_pattern",
        description=(
            "Rileva i pattern ricorrenti dal ledger delle tracce e li "
            "presenta al Promotore per l'approvazione (-> :Evento) o il "
            "rifiuto (-> cestino permanente). Percorso ristretto/fidato: "
            "nessun endpoint HTTP pubblico, nessuna decisione automatica."
        ),
    )


def main(argv: Sequence[str] | None = None) -> None:
    _build_parser().parse_args(argv)
    dsn = database_url_from_env()

    print("=== Curatela dei pattern ricorrenti — Urban Memory ===\n")
    print("1. Migrazione schema (idempotente)...")
    try:
        migrate(dsn)
    except Exception as exc:  # stesso stile esplicito di submit_signal.py/verify.py
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK.")

    traccia_repo: TracciaRepository = PostgresTracciaRepository(dsn)
    cestino_repo = PostgresPatternCestinatoRepository(dsn)

    # Il rilevamento richiede il grafo (`evento_esistente`, per escludere i
    # pattern GIÀ promossi — vedi `ricorrenza.rileva_candidati`): apre il
    # writer/reader Neo4j PRIMA di rilevare, non dopo, così un pattern già
    # promosso non può mai essere ripresentato al Promotore. Aura in pausa
    # durante QUESTO passo è uno scenario NORMALE (CLAUDE.md — "Aura Free si
    # auto-mette in pausa"), non eccezionale: stesso stile esplicito di
    # `migrate()` sopra — mai un traceback grezzo del driver Neo4j.
    try:
        with Neo4jPromozioneWriter.from_env() as scrittore:
            print("2. Rilevamento dei pattern candidati...")
            candidati = rileva_candidati(
                traccia_repo, cestino_repo, evento_esistente=scrittore.esiste
            )
            print(
                f"   {len(candidati)} pattern candidato/i (esclusi i cestinati e i già promossi)."
            )

            if not candidati:
                print("\nNessun pattern da curare in questa corsa.")
                return

            print("3. Curatela (una decisione umana per pattern)...")
            _esegui_interattivo(candidati, cestino_repo=cestino_repo, writer=scrittore.promuovi)
    except Exception as exc:  # stesso stile esplicito di migrate()/submit_signal.py/verify.py
        print(f"   FALLITO: grafo non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    print("\n=== Curatela completata ===")


if __name__ == "__main__":
    main()
