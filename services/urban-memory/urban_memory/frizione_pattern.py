"""La frizione automatica a cadenza di un `:Evento` promosso (Fase 3,
`docs/PROMOZIONE_TRACCIA.md` §3, `docs/STATE_MACHINE.md` §4-bis(a)) —
`python -m urban_memory.frizione_pattern`.

Percorso RISTRETTO/FIDATO PROVVISORIO, stesso principio di
`curatela_pattern.py`/`submit_signal.py`/`verify.py` (`docs/LIMITI.md`,
CLAUDE.md): nessuna auth, nessun rate-limit, chi ha accesso a questa shell è,
per costruzione, fidato. Un comando batch invocato MANUALMENTE, MAI integrato
in `POST /itinerary`, nell'Experience Engine o in qualunque altro path del
motore.

**Decisione architetturale 1 — il clock si CALCOLA, non si scrive ad ogni
traccia.** Non esiste un campo scritto sull'`:Evento` (o altrove) ad ogni
deposito di traccia (`urban_memory.canale_fluttuante.sweep_and_fetch_active`,
il percorso caldo di `/itinerary`): accoppiare quel percorso a un lookup su
`:Evento` violerebbe la purezza già rispettata dal motore. Il clock (ultima
occorrenza, battiti di cadenza mancati) si CALCOLA dal ledger Postgres
(`traccia_luogo`, via `TracciaRepository.occorrenze_per_pattern`), filtrato
per il `place_id`+`temi` ESATTI del pattern, ogni volta che QUESTO comando
gira — mai in tempo reale, mai ad ogni richiesta.

**Decisione architetturale 2 — riattivazione solo a questa corsa, non in
tempo reale.** `sospeso -> attivo` avviene SOLO quando questo comando viene
eseguito e trova un'occorrenza abbastanza recente: NON appena la traccia si
deposita (quello resterebbe un fatto silente nel ledger finché nessuno fa
girare questo comando). Dichiarato esplicitamente, non nascosto: un pattern
può restare "sospeso" più a lungo di quanto la sola cadenza indicherebbe, se
questo comando non viene eseguito con regolarità — un limite noto, non un
bug.

**`dormiente` non transita mai automaticamente qui.** Nessuna riattivazione
da `dormiente` è prevista in questo comando (fuori scope, task futuro se
servirà) — `calcola_transizione` ritorna sempre `(None, None)` per un evento
già `dormiente`, per costruzione.

Ogni transizione automatica applicata è LOGGATA esplicitamente (chi=sistema,
quando, evento_id/place_id/temi, stato precedente -> nuovo, perché) via
`logging` — stesso principio già applicato da
`curatela_pattern.promuovi_pattern`/`rifiuta_pattern` per le transizioni
umane. Colma esplicitamente (non lo ripete) il limite documentato in
`docs/LIMITI.md` ("il rilevamento automatico di un pattern ricorrente non
lascia un record d'audit distinto"): qui ogni transizione automatica lascia
sempre un log, coerente con `docs/STATE_MACHINE.md` §5/§1.4 ("anche
l'automatico logga chi/quando/perché").

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL` e
`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` obbligatorie: legge il ledger
delle tracce da Postgres e gli `:Evento` ricorrenti da Neo4j)::

    python -m urban_memory.frizione_pattern

Per ogni `:Evento {ricorrente: true}` esistente: legge le sue occorrenze
esatte dal ledger (`place_id`+`temi` già presenti sul nodo), calcola l'ultima
occorrenza e i battiti di cadenza mancati, decide la transizione (se dovuta)
e scrive `e.stato` SOLO se cambia rispetto a quello letto — un `MATCH`+`SET`
puro, mai un `MERGE` (il nodo esiste già).

`calcola_transizione` è una funzione PURA, richiamabile separatamente da
`main()` — nessun I/O, testabile in isolamento senza Postgres/Neo4j reali."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ._env import database_url_from_env, neo4j_config_from_env
from ._neo4j_tipi import Driver, ReadSession
from .migrate import migrate
from .traccia_repository import PostgresTracciaRepository, TracciaRepository

__all__ = [
    "K_BATTITI_SOSPENSIONE",
    "ORIZZONTE_DORMIENZA_GIORNI",
    "K_ORIZZONTE_DORMIENZA",
    "EVENTI_RICORRENTI_READ_QUERY_PATH",
    "FRIZIONE_STATO_WRITE_QUERY_PATH",
    "EventoRicorrente",
    "eventi_ricorrenti_read_cypher",
    "frizione_stato_write_cypher",
    "FrizionePatternError",
    "leggi_eventi_ricorrenti",
    "scrivi_stato_evento",
    "Neo4jFrizioneClient",
    "calcola_transizione",
    "main",
]

_logger = logging.getLogger(__name__)

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
EVENTI_RICORRENTI_READ_QUERY_PATH = _CYPHER_DIR / "60_eventi_ricorrenti_read.cypher"
FRIZIONE_STATO_WRITE_QUERY_PATH = _CYPHER_DIR / "61_frizione_stato_write.cypher"

#: Battiti di cadenza mancati oltre i quali un pattern `attivo` passa a
#: `sospeso` (non un numero di giorni assoluto: un pattern settimanale che
#: salta K sabati e uno mensile che salta K mesi attraversano la stessa
#: soglia LOGICA). TUNING: valore di PARTENZA, da calibrare sui dati reali
#: del pilota — non definitivo. Stessa classe di
#: `ricorrenza.N_MINIMO_OCCORRENZE`/`ricorrenza.TOLLERANZA_REGOLARITA`.
K_BATTITI_SOSPENSIONE: int = 2

#: Orizzonte di dormienza in giorni (tempo ASSOLUTO trascorso dall'ultima
#: occorrenza — non in battiti) oltre il quale un pattern `sospeso` passa a
#: `dormiente`. NON è più (da solo) la soglia usata da `calcola_transizione`:
#: una costante FISSA indipendente dalla cadenza fallirebbe esattamente sui
#: pattern che questo modulo dichiara di gestire nativamente (stagionalità
#: lunga) — un pattern annuale (`cadenza_giorni` ~365) entra in `sospeso`
#: solo a ~`K_BATTITI_SOSPENSIONE * cadenza_giorni` giorni (~730), un istante
#: già ben oltre un orizzonte fisso di ~6 mesi: verrebbe dichiarato
#: `dormiente` quasi subito, vanificando lo scopo. La soglia REALE è
#: `max(ORIZZONTE_DORMIENZA_GIORNI, K_ORIZZONTE_DORMIENZA * cadenza_giorni)`
#: (vedi `K_ORIZZONTE_DORMIENZA` sotto e `calcola_transizione`): questa
#: costante resta il PAVIMENTO assoluto, utile per cadenze cortissime
#: (settimanale, mensile) dove un orizzonte proporzionale alla sola cadenza
#: sarebbe irragionevolmente breve in termini assoluti. TUNING: valore di
#: PARTENZA (~6 mesi), da calibrare sui dati reali del pilota — non
#: definitivo, stessa classe di tuning di `K_BATTITI_SOSPENSIONE` sopra.
ORIZZONTE_DORMIENZA_GIORNI: float = 180.0

#: Moltiplicatore di `cadenza_giorni` che rende l'orizzonte di dormienza
#: PROPORZIONALE alla cadenza del singolo pattern, non solo un tempo
#: assoluto fisso: combinato con `ORIZZONTE_DORMIENZA_GIORNI` via
#: `max(ORIZZONTE_DORMIENZA_GIORNI, K_ORIZZONTE_DORMIENZA * cadenza_giorni)`
#: in `calcola_transizione`, garantisce che un pattern resti `sospeso` per
#: un multiplo ragionevole della propria cadenza — non un tempo trascurabile
#: o nullo — prima di essere dichiarato `dormiente`. Con i default attuali
#: (`K_BATTITI_SOSPENSIONE=2`, `K_ORIZZONTE_DORMIENZA=3.0`) un pattern resta
#: `sospeso` per circa UNA cadenza intera dopo essere entrato in `sospeso`
#: (2 battiti mancati per entrare in `sospeso`, 3 per la dormienza): un
#: pattern annuale resta `sospeso` undici-dodici mesi prima di essere
#: dichiarato morto, coerente con la stagionalità che questo modulo dichiara
#: di gestire nativamente. Per cadenze cortissime (settimanale, mensile) il
#: pavimento `ORIZZONTE_DORMIENZA_GIORNI` sopra vince comunque (nessuna
#: regressione: stesso comportamento di prima). TUNING: valore di PARTENZA,
#: da calibrare sui dati reali del pilota — non definitivo, stessa classe di
#: tuning di `K_BATTITI_SOSPENSIONE`/`ORIZZONTE_DORMIENZA_GIORNI` sopra.
K_ORIZZONTE_DORMIENZA: float = 3.0


@dataclass(frozen=True)
class EventoRicorrente:
    """Un `:Evento {ricorrente: true}` letto dal grafo. `temi` è GIÀ canonico
    (scritto in quella forma alla promozione,
    `promozione_evento.promozione_evento_cypher`).

    `frenato` (docs/STATE_MACHINE.md §4-bis(b), freno di emergenza) NON è
    consumato dalla frizione automatica a cadenza di QUESTO modulo — vive
    qui solo perché questo resta l'UNICO tipo che attraversa
    `leggi_eventi_ricorrenti`/`Neo4jFrizioneClient.eventi_ricorrenti()`,
    condiviso dal consumo in `services/api/api/main.py` (che sopprime la
    raccomandazione quando `frenato` è vero). La lettura/scrittura del
    freno vive interamente in `urban_memory.freno_pattern` (responsabilità
    separata: la frizione decide `stato`, il freno decide `frenato` — mai
    lo stesso modulo, mai la stessa proprietà)."""

    evento_id: str
    place_id: str
    temi: tuple[str, ...]
    stato: str
    cadenza_giorni: float
    frenato: bool = False


def eventi_ricorrenti_read_cypher() -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `60_eventi_ricorrenti_read.cypher`: nessuna
    connessione, nessuna esecuzione, nessun effetto collaterale oltre alla
    lettura statica (non parametrica) del file `.cypher` versionato. Nessun
    parametro nella query (enumera OGNI `:Evento` ricorrente esistente)."""
    query = EVENTI_RICORRENTI_READ_QUERY_PATH.read_text(encoding="utf-8")
    return query, {}


def frizione_stato_write_cypher(evento_id: str, nuovo_stato: str) -> tuple[str, dict[str, Any]]:
    """Query + parametri PURI per `61_frizione_stato_write.cypher`: nessuna
    connessione, nessuna esecuzione, nessun effetto collaterale oltre alla
    lettura statica del file `.cypher` versionato."""
    query = FRIZIONE_STATO_WRITE_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {"evento_id": evento_id, "nuovo_stato": nuovo_stato}
    return query, params


class FrizionePatternError(Exception):
    """Errore INFRASTRUTTURALE (grafo irraggiungibile — Aura in pausa, rete
    assente, credenziali non valide) durante la lettura degli `:Evento`
    ricorrenti o la scrittura di una transizione di stato — NON un errore di
    dominio: non esiste, in questo modulo, un caso in cui "zero righe"
    sia un errore. La lettura (`MATCH` su TUTTI gli `:Evento` ricorrenti)
    ritorna semplicemente una lista vuota se non ne esiste alcuno; la
    scrittura (`MATCH` sul singolo `$evento_id`) è un no-op silenzioso se
    quel nodo non esiste (più?) — stesso principio di
    `luogo_traccia_link.LuogoTracciaLinkError`."""


def leggi_eventi_ricorrenti(
    *, driver: Driver[ReadSession], database: str | None = None
) -> list[EventoRicorrente]:
    """Tutti gli `:Evento {ricorrente: true}` esistenti nel grafo, con le
    proprietà necessarie alla frizione. Lista vuota se non ne esiste alcuno
    (mai un errore). Solleva `FrizionePatternError` se il grafo è
    irraggiungibile."""
    query, params = eventi_ricorrenti_read_cypher()
    try:
        with driver.session(database=database) as session:
            righe = session.run(query, params).data()
    except FrizionePatternError:
        raise  # già il tipo giusto: non ri-avvolgere
    except Exception as exc:
        raise FrizionePatternError(
            f"grafo irraggiungibile durante la lettura degli eventi ricorrenti: {exc}"
        ) from exc
    return [
        EventoRicorrente(
            evento_id=riga["evento_id"],
            place_id=riga["place_id"],
            temi=tuple(riga["temi"] or []),
            stato=riga["stato"],
            cadenza_giorni=riga["cadenza_giorni"],
            # `.get(...)`, non `riga["frenato"]`: una riga proveniente da un
            # test o da un grafo non ancora aggiornato può non avere la
            # chiave affatto (o averla a `None`) — deve leggersi come
            # `False` in ENTRAMBI i casi (mai frenato di default), stesso
            # principio del `coalesce(e.frenato, false)` nella query.
            frenato=bool(riga.get("frenato") or False),
        )
        for riga in righe
    ]


def scrivi_stato_evento(
    evento_id: str, nuovo_stato: str, *, driver: Driver[ReadSession], database: str | None = None
) -> None:
    """Scrive `e.stato = nuovo_stato` per l'`:Evento` con id `evento_id` —
    `MATCH`+`SET` puro, mai un `MERGE`. No-op silenzioso se `evento_id` non
    esiste (più?) nel grafo (nessun nodo fantasma creato). Solleva
    `FrizionePatternError` se il grafo è irraggiungibile."""
    query, params = frizione_stato_write_cypher(evento_id, nuovo_stato)
    try:
        with driver.session(database=database) as session:
            session.run(query, params)
    except FrizionePatternError:
        raise  # già il tipo giusto: non ri-avvolgere
    except Exception as exc:
        raise FrizionePatternError(
            f"grafo irraggiungibile durante la scrittura dello stato "
            f"(evento_id={evento_id!r}, nuovo_stato={nuovo_stato!r}): {exc}"
        ) from exc


class Neo4jFrizioneClient:
    """Wrapper comodo: possiede un driver Neo4j aperto UNA VOLTA (non a ogni
    lettura/scrittura) e lo riusa — stesso pattern di
    `promozione_evento.Neo4jPromozioneWriter`/
    `luogo_traccia_link.Neo4jLuogoTracciaLinker`. Usato dal comando batch
    (`main()` sotto), una sola istanza per l'intera corsa."""

    def __init__(self, driver: Driver[ReadSession], database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> Neo4jFrizioneClient:
        """Costruisce leggendo `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/
        `NEO4J_DATABASE` dal `.env` (radice del repo) o dall'ambiente di
        processo."""
        from neo4j import GraphDatabase  # import locale: nessuna dipendenza

        cfg = neo4j_config_from_env(dotenv_path)
        driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
        return cls(driver, database=cfg.database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jFrizioneClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def eventi_ricorrenti(self) -> list[EventoRicorrente]:
        """Tutti gli `:Evento` ricorrenti esistenti, riusando il driver
        posseduto da questa istanza."""
        return leggi_eventi_ricorrenti(driver=self._driver, database=self._database)

    def aggiorna_stato(self, evento_id: str, nuovo_stato: str) -> None:
        """Scrive la transizione decisa, riusando il driver posseduto da
        questa istanza."""
        scrivi_stato_evento(evento_id, nuovo_stato, driver=self._driver, database=self._database)


def calcola_transizione(
    stato_corrente: str,
    cadenza_giorni: float,
    occorrenze: Sequence[datetime],
    adesso: datetime,
    *,
    k_battiti_sospensione: int = K_BATTITI_SOSPENSIONE,
    orizzonte_dormienza_giorni: float = ORIZZONTE_DORMIENZA_GIORNI,
    k_orizzonte_dormienza: float = K_ORIZZONTE_DORMIENZA,
) -> tuple[str | None, str | None]:
    """Decide la transizione di stato della frizione automatica a cadenza,
    dato lo stato corrente di un `:Evento`, la sua `cadenza_giorni` e le
    occorrenze ESATTE del suo pattern (`TracciaRepository.
    occorrenze_per_pattern`). Ritorna `(nuovo_stato, motivo)` se una
    transizione è dovuta, `(None, None)` altrimenti (nessun cambiamento).
    Funzione PURA: nessun I/O, nessuna scrittura — solo calcolo.

    Regole (frizione a CADENZA, non a tempo assoluto):

    - `dormiente` non transita MAI qui — nessuna riattivazione da dormiente
      è prevista in questo comando (fuori scope, task futuro).
    - Nessuna occorrenza, o `cadenza_giorni <= 0` (nessuna cadenza
      definibile — stesso principio di `ricorrenza.rileva_candidati`): nessuna
      transizione fabbricata.
    - `attivo -> sospeso` se i battiti di cadenza mancati (giorni trascorsi
      dall'ultima occorrenza / `cadenza_giorni`) sono `>= k_battiti_sospensione`.
    - `sospeso -> dormiente` se il tempo trascorso dall'ultima occorrenza
      supera `max(orizzonte_dormienza_giorni, k_orizzonte_dormienza *
      cadenza_giorni)` (tempo ASSOLUTO, non in battiti). L'orizzonte è
      DERIVATO dalla cadenza del singolo pattern, non una costante fissa
      indipendente da essa: una soglia fissa fallirebbe sui pattern a
      cadenza lunga (semestrale, annuale), dove `attivo -> sospeso` scatta
      già oltre quella soglia fissa, rendendo `sospeso` attraversabile in
      modo trascurabile o nullo. `orizzonte_dormienza_giorni` resta il
      PAVIMENTO assoluto (rilevante per le cadenze cortissime, dove un
      orizzonte proporzionale alla sola cadenza sarebbe irragionevolmente
      breve in termini assoluti).
    - `sospeso -> attivo` se i battiti mancati sono sotto la soglia (una
      traccia più recente della soglia di battito mancato è apparsa: il
      pattern ha ripreso) — questa riattivazione avviene SOLO quando QUESTO
      comando gira, non in tempo reale al deposito della traccia (vedi il
      docstring del modulo).
    - Qualunque altro stato corrente (sconosciuto): nessuna transizione
      fabbricata."""
    if stato_corrente == "dormiente":
        return None, None
    if not occorrenze or cadenza_giorni <= 0:
        return None, None

    ultima_occorrenza = max(occorrenze)
    giorni_trascorsi = (adesso - ultima_occorrenza).total_seconds() / 86400
    if giorni_trascorsi < 0:
        # Occorrenza nel "futuro" rispetto ad `adesso` — caso degenere
        # (orologi disallineati, dato corrotto): nessuna transizione
        # fabbricata, mai un battito negativo.
        return None, None
    battiti_mancati = giorni_trascorsi / cadenza_giorni

    if stato_corrente == "attivo":
        if battiti_mancati >= k_battiti_sospensione:
            return "sospeso", "cadenza mancata"
        return None, None

    if stato_corrente == "sospeso":
        soglia_dormienza = max(orizzonte_dormienza_giorni, k_orizzonte_dormienza * cadenza_giorni)
        if giorni_trascorsi > soglia_dormienza:
            return "dormiente", "sospensione oltre orizzonte"
        if battiti_mancati < k_battiti_sospensione:
            return "attivo", "traccia fresca"
        return None, None

    return None, None  # stato sconosciuto: nessuna transizione fabbricata


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m urban_memory.frizione_pattern",
        description=(
            "Applica la frizione automatica a cadenza a ogni :Evento "
            "ricorrente esistente (attivo -> sospeso -> dormiente, o "
            "sospeso -> attivo su traccia fresca). Percorso ristretto/"
            "fidato: nessun endpoint HTTP pubblico, MAI invocato da "
            "/itinerary o dal motore."
        ),
    )


def main(argv: Sequence[str] | None = None) -> None:
    _build_parser().parse_args(argv)
    dsn = database_url_from_env()

    print("=== Frizione automatica a cadenza — Urban Memory ===\n")
    print("1. Migrazione schema (idempotente)...")
    try:
        migrate(dsn)
    except Exception as exc:  # stesso stile esplicito di curatela_pattern.py
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK.")

    traccia_repo: TracciaRepository = PostgresTracciaRepository(dsn)

    try:
        with Neo4jFrizioneClient.from_env() as client:
            print("2. Lettura dei pattern promossi (:Evento {ricorrente: true})...")
            eventi = client.eventi_ricorrenti()
            print(f"   {len(eventi)} evento/i ricorrente/i trovato/i.")

            adesso = datetime.now(UTC)
            transizioni = 0
            print("3. Calcolo ed eventuale applicazione delle transizioni...")
            for evento in eventi:
                occorrenze = traccia_repo.occorrenze_per_pattern(
                    evento.place_id, list(evento.temi)
                )
                nuovo_stato, motivo = calcola_transizione(
                    evento.stato, evento.cadenza_giorni, occorrenze, adesso
                )
                if nuovo_stato is None or nuovo_stato == evento.stato:
                    continue

                client.aggiorna_stato(evento.evento_id, nuovo_stato)
                transizioni += 1
                _logger.info(
                    "transizione automatica: %s -> %s (evento_id=%s, place_id=%s, "
                    "temi=%s, motivo=%r, quando=%s)",
                    evento.stato,
                    nuovo_stato,
                    evento.evento_id,
                    evento.place_id,
                    evento.temi,
                    motivo,
                    adesso.isoformat(),
                )
                print(f"   {evento.evento_id}: {evento.stato} -> {nuovo_stato} ({motivo})")

            print(f"\n{transizioni} transizione/i applicata/e.")
    except Exception as exc:  # stesso stile esplicito di curatela_pattern.py
        print(f"   FALLITO: grafo non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    print("\n=== Frizione completata ===")


if __name__ == "__main__":
    main()
