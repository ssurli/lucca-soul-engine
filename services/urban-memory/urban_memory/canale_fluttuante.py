"""Il canale fluttuante persistente (Fase 3, `docs/PROMOZIONE_TRACCIA.md`) —
le due giunture che collegano `Signal.eventi_attivi`
(`packages/contracts`) allo storage, SENZA toccare il motore
(`experience_engine.engine.compose_itinerary` resta PURO, legge solo
`ctx.signal.eventi_attivi`: verificato — nessuna riga di questo modulo
importa `experience_engine`, nessuna riga di `experience_engine` importa
`urban_memory`).

**Lato SCRITTURA** (`persist_signal`): persiste un `SegnaleFluttuante`
(stato `ATTIVO`, il default del contratto — a meno che `valido_fino` sia già
nel passato). Invocato SOLO da un percorso RISTRETTO/FIDATO provvisorio
(`python -m urban_memory.submit_signal`) — stesso principio di
`link_to_graph`, invocato solo da `verify.py`/`link.py`. NON un endpoint
HTTP pubblico (fase-fiducia, fuori scope — CLAUDE.md, `docs/LIMITI.md`).

**Lato LETTURA** (`sweep_and_fetch_active`): invocato dal BFF
(`api.main.create_itinerary`, PRIMA di `compose_itinerary`). Tre passi, in
ordine:

(a) **spazza gli scaduti** — `SegnaleFluttuanteRepository.sweep_scaduti`
    transita ATOMICAMENTE ogni segnale `attivo` con `valido_fino <= now` a
    `expired`. GLOBALE (non filtrata per luogo): ogni composizione
    d'itinerario, per QUALUNQUE luogo, innesca lo stesso sweep — chiude il
    buco classico del lazy-sweep ("i luoghi tranquilli non vengono mai
    spazzati").
(b) **deposita una traccia** per OGNI segnale appena transitato che sia
    ANCHE ammissibile (`contracts.segnale_fluttuante_ammissibile` — mai per
    quelli già `expired` da prima, la guardia è la query di
    `sweep_scaduti`, vedi `docs/PROMOZIONE_TRACCIA.md` §1; e mai per un
    segnale commerciale, vedi il paragrafo dedicato più sotto), e aggiorna
    la proprietà derivata `:Luogo.ultima_traccia_il` (best-effort, via
    `place_link_writer` — vedi sotto). ISOLATO PER SEGNALE, vedi sotto.
    **Il timbro (`Traccia.creato_il` e `ultima_traccia_il`) è il
    `valido_fino` del segnale scaduto, normalizzato UTC — NON l'istante
    dello sweep**: lo sweep è pigro (solo su POST /itinerary), con poco
    traffico un segnale del sabato verrebbe timbrato lunedì e la fase
    (giorno/ora) della ricorrenza sarebbe rumore. Resta un timbro del server
    (`valido_fino` è calcolato in `submit_signal`). `istante` serve solo a
    `sweep_scaduti`/`fetch_attivi`. Le tracce depositate PRIMA di questa
    correzione (timbrate allo sweep) non si riscrivono (append-only).
(c) **fetcha gli attivi** — `SegnaleFluttuanteRepository.fetch_attivi`,
    con lo STESSO `now` di (a): quello che popola `Signal.eventi_attivi`.

**IDEMPOTENZA (load-bearing).** La transizione `attivo -> expired` è la
GUARDIA primaria (`SegnaleFluttuanteRepository.sweep_scaduti`, vedi il suo
docstring): un segnale già `expired` non viene mai restituito una seconda
volta da `sweep_scaduti`, quindi il ciclo `for segnale in scaduti` qui sotto
non deposita MAI una seconda traccia per lo stesso segnale — `expired ->
expired` è un no-op per costruzione, non un caso gestito esplicitamente.

**CHI CATTURA COSA — due garanzie DIVERSE, non confonderle (revisione
`ethics-guardian`, FAIL corretto in questa versione).**

`sweep_scaduti` e `fetch_attivi` (letture/scritture SUL repository dei
segnali) NON sono catturati qui: propagano SEMPRE. È corretto che lo
facciano — se `sweep_scaduti` fallisce PRIMA di committare, nessuna
transizione è avvenuta (nessun danno, solo un ritardo: la prossima chiamata
riprova sull'intero batch); se fallisce DOPO aver committato non c'è nulla
da recuperare qui (la transizione È già persistita). Chi chiama
(`api.main.create_itinerary`) cattura questi due casi e degrada a
`eventi_attivi=[]` — mai un 503.

`deposita` (il ledger) e `place_link_writer` (la proprietà derivata) sono
INVECE catturati QUI, per singolo segnale, dentro il ciclo — MAI propagati:
un fallimento su un segnale non deve mai abortire il deposito degli altri
segnali dello stesso sweep (isolamento del danno, non una transazione
condivisa fra `SegnaleFluttuanteRepository` e `TracciaRepository` — quella
resta deliberatamente esclusa, stesso principio già accettato in
`urban_memory.graph_link` per `:Memoria`/Postgres: "due scritture in due
store diversi", non una garanzia nuova da inventare).

**FILTRO DI AMMISSIBILITÀ SUL DEPOSITO (varco chiuso, revisione dedicata
`ethics-guardian` — non un'autovalutazione).** Un giro DEDICATO di
`ethics-guardian` sull'intera catena segnale->traccia->pattern->promozione->
consumo in itinerario ha trovato un varco: `contracts.
segnale_fluttuante_ammissibile` (il filtro "nessuno spazio è acquistabile",
CLAUDE.md) era applicato SOLO nel consumo diretto di `Signal.eventi_attivi`
(`experience_engine.rules.segnali_fluttuanti_pertinenti`), MAI nel percorso
parallelo del ledger delle tracce — un `SegnaleFluttuante` commerciale
(`non_commerciale=False`) poteva quindi attraversare indenne sweep ->
deposito -> pattern ricorrente -> promozione a `:Evento` -> raccomandazione
in un itinerario reale, bypassando il filtro perché quel percorso non passa
mai da `Signal.eventi_attivi`. Il fix riusa la STESSA funzione già impiegata
per il consumo diretto (`segnale_fluttuante_ammissibile` — un solo criterio,
mai un secondo scritto qui) e la applica QUI, nel ciclo `for segnale in
scaduti`, PRIMA di `traccia_repo.deposita`: un segnale non ammissibile
`continue`-a senza depositare una `Traccia` né chiamare
`place_link_writer` per sé — un luogo non deve "brillare"
(`ultima_traccia_il`) per un segnale che non sarebbe mai stato composto.
Il filtro si applica SOLO qui, mai altrove in questa funzione: NON tocca
`sweep_scaduti` (la transizione `attivo -> expired` avviene comunque,
incondizionatamente, per QUALUNQUE segnale, commerciale o no — un segnale
scade per il solo fatto di essere scaduto, non per la sua ammissibilità) e
NON tocca `persist_signal`/la persistenza del segnale grezzo (resta
invariata, per audit/storico, indipendentemente da `non_commerciale` — vedi
il suo docstring). Il segnale commerciale scaduto resta quindi correttamente
`expired` in Postgres, visibile per audit, ma inerte per il ledger: non
genera mai una `Traccia`, quindi non può mai maturare in un pattern
ricorrente né in un `:Evento` promosso.

**ATTENZIONE — CONSEGUENZA NON RIMEDIABILE, dichiarata esplicitamente, non
nascosta:** `sweep_scaduti` ha GIÀ COMMITTATO la transizione `attivo ->
expired` per un segnale PRIMA che questo modulo tenti `deposita` per quello
stesso segnale. Se `deposita` (o `place_link_writer`) fallisce DOPO quel
commit, la traccia per QUEL segnale specifico va PERSA IN MODO PERMANENTE E
SILENZIOSO (loggata, mai propagata): la guardia dell'idempotenza
(`WHERE stato='attivo'`) impedisce PER COSTRUZIONE a qualunque sweep futuro
di ripescare un segnale già `expired` — non esiste un secondo tentativo.
Questo NON è "un ritardo, poi ritentato alla prossima richiesta" (quella
proprietà vale SOLO per un fallimento di `sweep_scaduti`/`fetch_attivi`,
vedi sopra): è una perdita del singolo dato-traccia, non del segnale (che
resta comunque correttamente `expired`, non più composto in un itinerario).
Non è stata introdotta una transazione condivisa per chiuderla (fuori
scope, architettura deliberatamente esclusa — vedi sopra): l'isolamento
per-segnale qui sotto riduce il raggio del danno da "fino a N tracce perse
in un solo sweep" a "al più 1 traccia persa per segnale coinvolto", non lo
elimina.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from contracts import SegnaleFluttuante, segnale_fluttuante_ammissibile

from .segnale_repository import SegnaleFluttuanteRepository
from .traccia_repository import TracciaRepository

__all__ = ["PlaceLinkWriter", "persist_signal", "sweep_and_fetch_active"]

_logger = logging.getLogger(__name__)

#: Riceve `(place_id, quando)` — `quando` = `valido_fino` UTC del segnale, la
#: scrittura è monotona (massimo) — e aggiorna `ultima_traccia_il` sul `:Luogo`
#: nel Knowledge Graph — tipicamente `urban_memory.luogo_traccia_link.
#: Neo4jLuogoTracciaLinker.scrivi` (metodo legato, con un driver reale). Mai
#: un valore di ritorno: l'esito si legge dall'assenza/presenza
#: dell'eccezione (`LuogoTracciaLinkError`), propagata da
#: `sweep_and_fetch_active` a chi chiama, mai inghiottita qui.
PlaceLinkWriter = Callable[[str, datetime], None]


def persist_signal(
    repo: SegnaleFluttuanteRepository, segnale: SegnaleFluttuante
) -> SegnaleFluttuante:
    """Persiste `segnale` nel canale fluttuante. Nessuna logica di dominio
    ulteriore qui: il contratto (`packages/contracts.SegnaleFluttuante`) ha
    già validato tz-awareness di `valido_fino`, `non_commerciale` esplicito,
    `temi`/`descrizione` non vuoti — e ha già normalizzato `stato=EXPIRED`
    se `valido_fino` era già nel passato al momento della costruzione.
    Invocato SOLO da un percorso ristretto/fidato (vedi il docstring del
    modulo)."""
    return repo.persist(segnale)


def sweep_and_fetch_active(
    segnale_repo: SegnaleFluttuanteRepository,
    traccia_repo: TracciaRepository,
    *,
    place_link_writer: PlaceLinkWriter | None = None,
    now: datetime | None = None,
) -> list[SegnaleFluttuante]:
    """Lato-lettura del canale fluttuante: sweep degli scaduti (deposita
    traccia + proprietà derivata), poi fetch degli attivi rimasti — vedi il
    docstring del modulo per i tre passi (a)/(b)/(c).

    `now`: iniettabile per i test (default `datetime.now(UTC)`) — UN SOLO
    istante per l'intero sweep+fetch di questa chiamata: evita che un
    segnale scada esattamente TRA lo sweep e il fetch, restando invisibile a
    entrambi in questa chiamata (non è un problema: verrà preso dalla
    PROSSIMA chiamata, mai perso — il canale è persistente).

    `place_link_writer=None` (default): nessuna scrittura nel grafo — comodo
    per test di dominio puri che riguardano solo Postgres, stesso pattern di
    `target_checker=None`/`linker=None` in `urban_memory.service`. Chi
    cablaggia per produzione (`api.deps.get_place_link_writer`) passa un
    writer reale — tipicamente `Neo4jLuogoTracciaLinker.scrivi` (metodo
    legato).

    `sweep_scaduti`/`fetch_attivi` propagano QUALUNQUE eccezione (il
    cattura-e-degrada è responsabilità di chi chiama). `deposita`/
    `place_link_writer` sono INVECE catturati QUI, per singolo segnale —
    MAI propagati: un fallimento su un segnale è ISOLATO (loggato,
    `continue`), non abortisce il deposito degli altri segnali dello stesso
    sweep. Vedi il docstring del modulo per la conseguenza NON rimediabile
    di questo isolamento (una traccia può andare persa in modo permanente e
    silenzioso per il segnale su cui `deposita` fallisce, DOPO che
    `sweep_scaduti` ha già committato la sua transizione)."""
    istante = now if now is not None else datetime.now(UTC)

    scaduti = segnale_repo.sweep_scaduti(istante)
    # Ordine di deposito: per `valido_fino` (UTC) poi id — cronologico e
    # deterministico (lo sweep itera per id, non per tempo). Pulizia del
    # ledger/della sequenza di scritture; la correttezza di
    # `ultima_traccia_il` NON dipende da questo ordine (la Cypher è monotona,
    # serve comunque fra sweep diversi).
    scaduti = sorted(scaduti, key=lambda s: (s.valido_fino.astimezone(UTC), s.id))
    for segnale in scaduti:
        if not segnale_fluttuante_ammissibile(segnale):
            # "Nessuno spazio è acquistabile" (CLAUDE.md) applicato ANCHE
            # qui — vedi il paragrafo dedicato nel docstring del modulo. La
            # transizione attivo->expired è GIA' avvenuta sopra (invariata,
            # intenzionale): il segnale commerciale semplicemente non
            # contribuisce al ledger né alla proprietà derivata sul luogo.
            continue

        # Timbro della traccia = QUANDO il segnale è scaduto davvero
        # (`valido_fino`, calcolato dal server in submit_signal: resta un
        # timbro del server, Strada B), non quando lo sweep pigro l'ha
        # notato. Normalizzato UTC: psycopg restituisce TIMESTAMPTZ nel fuso
        # della sessione.
        timbro = segnale.valido_fino.astimezone(UTC)
        try:
            traccia_repo.deposita(
                segnale_id=segnale.id,
                place_id=segnale.place_id,
                temi=list(segnale.temi),
                creato_il=timbro,
            )
        except Exception as exc:
            # PERDITA PERMANENTE E SILENZIOSA per QUESTO segnale (vedi
            # docstring del modulo): sweep_scaduti ha già committato
            # attivo->expired, la guardia dell'idempotenza impedisce per
            # costruzione un secondo tentativo futuro. Isolata (non
            # propagata): gli altri segnali di questo stesso sweep
            # proseguono comunque.
            _logger.error(
                "PERDITA PERMANENTE: deposito traccia fallito per un "
                "segnale già transitato a expired (commit irreversibile) — "
                "questo segnale non depositerà MAI una traccia "
                "(segnale_id=%s, place_id=%s): %s",
                segnale.id,
                segnale.place_id,
                exc,
            )
            continue

        if place_link_writer is not None:
            try:
                place_link_writer(segnale.place_id, timbro)
            except Exception as exc:
                # Proprietà DERIVATA, best-effort (docs/PROMOZIONE_TRACCIA.md
                # §2a): la traccia su Postgres (già depositata sopra) resta
                # la fonte di verità. Isolata come sopra: non abortisce né
                # questo segnale (la traccia è comunque scritta) né i
                # successivi.
                _logger.warning(
                    "ultima_traccia_il NON aggiornata sul grafo per "
                    "place_id=%s (dato derivato, best-effort — la traccia "
                    "su Postgres resta la fonte di verità, si autocorregge "
                    "alla prossima traccia depositata per lo stesso "
                    "luogo): %s",
                    segnale.place_id,
                    exc,
                )

    return segnale_repo.fetch_attivi(istante)
