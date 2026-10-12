"""CLI di ripristino: ricostruisce nel grafo TUTTI gli `:Evento` promossi dal
ledger Postgres — `python -m urban_memory.ripristina_eventi`.

Perché esiste: Aura Free viene cancellata per inattività (fatto osservato) e
la decisione di promozione viveva solo nel grafo (CLAUDE.md: nessun dato
vive solo su Aura). Ora la FONTE DI VERITÀ è `pattern_promosso` (append-only,
`sql/04_promozione_schema.sql`); il grafo ne è la proiezione, rigenerabile.

Sequenza di recupero dopo la perdita di Aura::

    python -m graph.loader                      # 1. seed del grafo (Luoghi...)
    python -m urban_memory.link                 # 2. :Memoria da Postgres
    python -m urban_memory.ripristina_eventi    # 3. QUESTO comando
    python -m urban_memory.frizione_pattern     # 4. ricalcola e.stato

Cosa fa, per ogni `evento_id` del ledger (semantica ON CREATE/ON MATCH di
`cypher/50_promozione_evento_write.cypher`):
- `promosso_da`/`promosso_il` dalla PRIMA riga (data originale di promozione);
- `temi`/`cadenza_giorni` dalla riga PIÙ RECENTE; se le righe sono più di
  una, la più recente fornisce anche `ultimo_ricalcolo_da`/`_il`;
- MERGE deterministico (`evento_id_per_pattern`): IDEMPOTENTE, rieseguibile.
`e.frenato` è scritto NELLA STESSA query del nodo (ultima azione per
`evento_id` in `pattern_frenato`, false se nessuna): niente seconda fase,
mai un evento frenato attivo e non frenato. Le letture (ledger, freno,
cestino) precedono ogni scrittura: se una fallisce, nulla è proiettato. Un
pattern presente sia nel cestino sia nel ledger NON è proiettato (conflitto).

`e.stato` NON viene ripristinato: un evento nuovo parte 'sospeso' (fail-safe,
non raccomandabile; uno già esistente non è toccato) e la frizione automatica
(`urban_memory.frizione_pattern`, `sospeso -> attivo`) lo riporta attivo —
passo 4 OBBLIGATORIO, stampato a fine comando.

Exit 1 se almeno un evento non è proiettato (`:Luogo` mancante: elencato, va
prima ricaricato il seed; oppure grafo irraggiungibile: il comando si ferma).
Limite: promozioni avvenute PRIMA dell'introduzione del ledger non vi sono
registrate e non sono recuperabili da qui. Nessun PII stampato: solo id
tecnici e conteggi (mai `promotore`).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ._env import database_url_from_env
from .cestino_repository import CestinoStorageError, PostgresPatternCestinatoRepository
from .freno_repository import (
    FrenoStorageError,
    PatternFrenatoRepository,
    PostgresPatternFrenatoRepository,
)
from .migrate import migrate
from .promozione_evento import LuogoMancanteError, Neo4jPromozioneWriter, PromozioneEventoError
from .promozione_repository import (
    PatternPromosso,
    PostgresPromozioneRepository,
    PromozioneRepository,
    PromozioneStorageError,
)

__all__ = ["EventoDaRipristinare", "RapportoRipristino", "raggruppa_ledger", "ripristina", "main"]


@dataclass(frozen=True)
class EventoDaRipristinare:
    evento_id: str
    place_id: str
    temi: tuple[str, ...]
    cadenza_giorni: float
    promotore: str
    promosso_il: datetime
    ultimo_ricalcolo_da: str | None
    ultimo_ricalcolo_il: datetime | None
    #: Ultima azione in `pattern_frenato` == 'tirato'. Scritto NELLA STESSA
    #: query del nodo (fail-closed: mai un evento frenato attivo e non frenato).
    frenato: bool = False


@dataclass
class RapportoRipristino:
    proiettati: list[str] = field(default_factory=list)
    luogo_mancante: list[tuple[str, str]] = field(default_factory=list)  # (evento_id, place_id)
    conflitto_cestino: list[str] = field(default_factory=list)  # evento_id
    grafo_irraggiungibile: str | None = None  # messaggio, se il comando si è fermato
    non_tentati: int = 0
    frenati: list[str] = field(default_factory=list)  # proiettati con frenato=true
    freno_senza_evento: list[str] = field(default_factory=list)  # evento_id non nel ledger

    @property
    def ok(self) -> bool:
        return not (self.luogo_mancante or self.conflitto_cestino or self.grafo_irraggiungibile)


def raggruppa_ledger(
    righe: Sequence[PatternPromosso], frenati: frozenset[str] = frozenset()
) -> list[EventoDaRipristinare]:
    """Una voce per `evento_id`: PRIMA riga per promotore/promosso_il, riga
    PIÙ RECENTE per temi/cadenza/ricalcolo (ordine di `righe` = cronologico,
    come garantito da `PromozioneRepository.elenca`). `frenati`: gli
    `evento_id` con freno tirato. Funzione pura."""
    per_evento: dict[str, list[PatternPromosso]] = {}
    for riga in righe:
        per_evento.setdefault(riga.evento_id, []).append(riga)
    risultato: list[EventoDaRipristinare] = []
    for evento_id, gruppo in per_evento.items():
        prima, ultima = gruppo[0], gruppo[-1]
        ricalcolato = len(gruppo) > 1
        risultato.append(
            EventoDaRipristinare(
                evento_id=evento_id,
                place_id=ultima.place_id,
                temi=ultima.temi,
                cadenza_giorni=ultima.cadenza_giorni,
                promotore=prima.promotore,
                promosso_il=prima.promosso_il,
                ultimo_ricalcolo_da=ultima.promotore if ricalcolato else None,
                ultimo_ricalcolo_il=ultima.promosso_il if ricalcolato else None,
                frenato=evento_id in frenati,
            )
        )
    return risultato


def ripristina(
    promozione_repo: PromozioneRepository,
    freno_repo: PatternFrenatoRepository,
    *,
    proietta: Callable[[EventoDaRipristinare], str],
    e_cestinato: Callable[[str, list[str]], bool],
) -> RapportoRipristino:
    """Ricostruisce gli eventi dal ledger, freno incluso. `proietta`
    (tipicamente `Neo4jPromozioneWriter.ripristina` adattato) e `e_cestinato`
    sono INIETTATI. Idempotente.

    FAIL-CLOSED: TUTTE le letture (ledger, `ultime_azioni()` del freno,
    cestino) avvengono PRIMA della prima proiezione — se una fallisce
    l'eccezione risale e NULLA è proiettato. Nodo e `e.frenato` sono scritti
    da una sola query (51): nessuna fase 2, nessun evento frenato attivo e non
    frenato. Un evento in conflitto col cestino NON è proiettato. Se il grafo
    è irraggiungibile si ferma al primo errore."""
    righe = promozione_repo.elenca()
    ultime = freno_repo.ultime_azioni()
    frenati = frozenset(r.evento_id for r in ultime if r.azione == "tirato")
    eventi = raggruppa_ledger(righe, frenati)
    conflitti = {e.evento_id for e in eventi if e_cestinato(e.place_id, list(e.temi))}

    rapporto = RapportoRipristino()
    noti = {e.evento_id for e in eventi}
    rapporto.freno_senza_evento = [r.evento_id for r in ultime if r.evento_id not in noti]
    da_proiettare = []
    for evento in eventi:
        if evento.evento_id in conflitti:
            rapporto.conflitto_cestino.append(evento.evento_id)
        else:
            da_proiettare.append(evento)

    for indice, evento in enumerate(da_proiettare):
        try:
            proietta(evento)
        except LuogoMancanteError:
            rapporto.luogo_mancante.append((evento.evento_id, evento.place_id))
        except PromozioneEventoError as exc:
            rapporto.grafo_irraggiungibile = str(exc)
            rapporto.non_tentati = len(da_proiettare) - indice - 1
            break
        else:
            rapporto.proiettati.append(evento.evento_id)
            if evento.frenato:
                rapporto.frenati.append(evento.evento_id)
    return rapporto


def _stampa_rapporto(rapporto: RapportoRipristino) -> int:
    """Report in italiano; ritorna il codice di uscita. Solo id tecnici e
    conteggi: mai `promotore`/`motivazione`."""
    print(f":Evento proiettati nel grafo: {len(rapporto.proiettati)}")
    if rapporto.luogo_mancante:
        print(f":Evento NON proiettati (:Luogo mancante): {len(rapporto.luogo_mancante)}")
        for evento_id, place_id in rapporto.luogo_mancante:
            print(f"  - evento_id={evento_id!r}  place_id={place_id!r}")
        print("  Rimedio: ricarica il seed (python -m graph.loader) e rilancia questo comando.")
    if rapporto.conflitto_cestino:
        n = len(rapporto.conflitto_cestino)
        print(f":Evento NON proiettati (conflitto cestino/ledger): {n}")
        for evento_id in rapporto.conflitto_cestino:
            print(f"  - evento_id={evento_id!r}  (pattern nel cestino permanente E nel ledger)")
        print("  Rimedio: decisione umana su quale dei due vale; l'evento non è stato proiettato.")
    if rapporto.grafo_irraggiungibile:
        print(f"FERMATO: {rapporto.grafo_irraggiungibile}")
        print(f"  Eventi non tentati: {rapporto.non_tentati}")
    print(f"Freno ripristinato (scritto col nodo) su {len(rapporto.frenati)} evento/i.")
    for evento_id in rapporto.freno_senza_evento:
        print(f"  - ATTENZIONE: freno registrato per evento_id={evento_id!r} assente dal ledger")
    print()
    print(
        "e.stato NON ripristinato: i nuovi :Evento partono 'sospeso' (NON raccomandabili). "
        "Passo OBBLIGATORIO successivo: python -m urban_memory.frizione_pattern "
        "(riporta ad 'attivo' ciò che la cadenza consente)."
    )
    if rapporto.ok:
        print("RIPRISTINO OK.")
        return 0
    print("RIPRISTINO INCOMPLETO.")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m urban_memory.ripristina_eventi",
        description=(
            "Ricostruisce nel grafo gli :Evento promossi (e il freno) dal "
            "ledger Postgres pattern_promosso. Idempotente. Richiede "
            "DATABASE_URL e NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD nel .env. "
            "Non ripristina e.stato: lancia poi frizione_pattern."
        ),
    )


def main(argv: Sequence[str] | None = None) -> None:
    _build_parser().parse_args(argv)
    dsn = database_url_from_env()
    print("=== Ripristino degli :Evento promossi dal ledger — Urban Memory ===\n")
    try:
        migrate(dsn)  # idempotente: garantisce che pattern_promosso esista
        promozione_repo = PostgresPromozioneRepository(dsn)
        freno_repo = PostgresPatternFrenatoRepository(dsn)
        with (
            Neo4jPromozioneWriter.from_env() as scrittore,
        ):
            rapporto = ripristina(
                promozione_repo,
                freno_repo,
                proietta=lambda e: scrittore.ripristina(
                    e.place_id,
                    e.evento_id,
                    e.temi,
                    e.cadenza_giorni,
                    e.promotore,
                    e.promosso_il,
                    e.ultimo_ricalcolo_da,
                    e.ultimo_ricalcolo_il,
                    e.frenato,
                ),
                e_cestinato=PostgresPatternCestinatoRepository(dsn).e_cestinato,
            )
    except (PromozioneStorageError, FrenoStorageError, CestinoStorageError) as exc:
        print(f"FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # stesso stile esplicito degli altri CLI
        print(f"FALLITO: errore durante il ripristino — {exc}")
        raise SystemExit(1) from exc

    codice = _stampa_rapporto(rapporto)
    if codice != 0:
        raise SystemExit(codice)


if __name__ == "__main__":
    main()
