"""Feature del recommender — aggregazione di `BehaviorEvent` per `experience_id`.

Unico input di questo modulo: `contracts.BehaviorEvent` (eventi comportamentali
sulla piattaforma propria — view/stop/photo/booking/review/skip/memory_contrib).
Tutte le feature prodotte sono AGGREGATE e ANONIME (CLAUDE.md — privacy by
design): `person_id` entra solo per essere contato, mai per essere esposto;
il dizionario risultante è raggruppato per `experience_id`, il dettaglio per
persona non sopravvive all'aggregazione.

VINCOLO — nessun segnale commerciale né di notorietà esterna:
questo modulo non importa `Partner`, non legge `prezzo_eur`,
`partner_abbonamento_attivo`, `prenotabile`, e non importa/legge NESSUN dato
di rating o recensione di provider terzi (Google, TripAdvisor o simili) né
alcun dato di Urban Memory / Urban Intelligence Index. Vedi il README di
questo servizio, sezione "Cosa NON è una feature, e perché", per la
motivazione estesa: in breve, la notorietà esterna è il proxy più diretto
dell'overtourism che questa wave esiste per contrastare, e i dati di Urban
Memory/Index sono un canale di REPORTING verso il Comune (Wave 4), non un
ciclo di feedback verso il reranking individuale.
"""

from __future__ import annotations

from collections.abc import Iterable

from contracts import BehaviorEvent

__all__ = ["PESI_TIPO", "conteggio_pesato_per_esperienza", "pesare_conteggi_grezzi"]

#: Peso di ogni `tipo` di evento nell'aggregazione per `experience_id`. Ogni
#: scelta è motivata: nessun peso è arbitrario, e nessuno di questi pesi premia
#: la sola ESPOSIZIONE/popolarità più di una presenza fisica reale — questo
#: dizionario alimenta SOLO il calcolo della quota storica di concentrazione
#: (vedi `recommender.ranking`), che è poi usata per PENALIZZARE, mai premiare.
#:
#: - "view" (1.0): baseline. Una vista è il segnale più debole di interesse
#:   (potrebbe essere solo passata sullo schermo), ma resta un'unità di
#:   esposizione: conta 1.
#: - "stop" (2.0): la persona si è fermata — presenza fisica reale e
#:   prolungata in quel luogo. Pesa il doppio di una vista perché è il
#:   segnale più diretto di "flusso" nel senso in cui questa wave lo intende
#:   (persone fisicamente presenti in un luogo).
#: - "photo" (1.5): un gesto di attenzione attivo (si fotografa ciò che colpisce
#:   davvero), più forte di una vista ma non equivalente a una tappa completa
#:   come "stop": peso intermedio.
#: - "booking" (2.0): un'intenzione di visita concreta. Stesso peso di "stop"
#:   (stesso ordine di segnale di presenza attesa/reale) — NON è trattato come
#:   segnale commerciale né come proxy di valore economico: qui conta solo
#:   come indicatore di flusso, esattamente come "stop". Il fatto che
#:   un'esperienza sia prenotabile o abbia un prezzo non entra in NESSUN
#:   calcolo di questo modulo: qui contiamo solo eventi, non euro.
#: - "review" (1.0): riflessione POST-visita. La presenza fisica è già contata
#:   da stop/booking: la review aggiunge un segnale leggero (conferma che la
#:   visita sia avvenuta) senza raddoppiare il peso della stessa visita.
#: - "skip" (0.0): rifiuto esplicito. Un contatore che misura CONCENTRAZIONE
#:   di flusso non deve mai premiare un luogo perché è stato ignorato molte
#:   volte: azzerato per costruzione. Deliberatamente non negativo: un valore
#:   negativo per luogo distorcerebbe la quota storica (potrebbe farla uscire
#:   da [0,1] o invertirne il significato) in un modo non facilmente
#:   spiegabile in italiano nel `reason` — mentre 0 resta semplice da motivare
#:   ("skip non conta come presenza").
#: - "memory_contrib" (1.5): un contributo alla Urban Memory è un segnale di
#:   coinvolgimento profondo e volontario (più di una vista, meno di una
#:   presenza fisica già contata altrove da stop/booking). È un evento raro:
#:   un peso moderato evita che pochi contributi dominino la quota storica di
#:   un luogo. NOTA: qui si conta solo che l'evento `memory_contrib` sia
#:   avvenuto (dalla lista di `BehaviorEvent`) — questo modulo NON legge il
#:   contenuto della `MemoryContribution` associata, né alcun dato aggregato
#:   della Urban Memory: quel canale è di reporting (Wave 4), non una feature
#:   di questo recommender.
PESI_TIPO: dict[str, float] = {
    "view": 1.0,
    "stop": 2.0,
    "photo": 1.5,
    "booking": 2.0,
    "review": 1.0,
    "skip": 0.0,
    "memory_contrib": 1.5,
}


def conteggio_pesato_per_esperienza(eventi: Iterable[BehaviorEvent]) -> dict[str, float]:
    """Aggrega `eventi` per `experience_id`, pesando ciascuno per `PESI_TIPO[tipo]`.

    Aggregato e anonimo: il risultato è raggruppato SOLO per `experience_id`;
    non esiste alcun modo di risalire da questo dizionario a un `person_id`
    (il dettaglio per persona non sopravvive all'aggregazione). Usato da
    `InMemoryBehaviorEventRepository.conteggio_per_esperienza`.
    """
    pesi: dict[str, float] = {}
    for evento in eventi:
        pesi[evento.experience_id] = pesi.get(evento.experience_id, 0.0) + PESI_TIPO.get(
            evento.tipo, 0.0
        )
    return pesi


def pesare_conteggi_grezzi(conteggi: Iterable[tuple[str, str, int]]) -> dict[str, float]:
    """Combina conteggi grezzi `(tipo, experience_id, n)` — tipicamente il
    risultato di un `GROUP BY tipo, experience_id` su Postgres — nello stesso
    schema di pesatura di `conteggio_pesato_per_esperienza`, senza duplicare
    `PESI_TIPO` in `recommender.repository`. Usato da
    `PostgresBehaviorEventRepository.conteggio_per_esperienza`.
    """
    pesi: dict[str, float] = {}
    for tipo, experience_id, n in conteggi:
        pesi[experience_id] = pesi.get(experience_id, 0.0) + PESI_TIPO.get(tipo, 0.0) * n
    return pesi
