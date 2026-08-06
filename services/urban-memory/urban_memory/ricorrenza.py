"""Rilevamento dei pattern ricorrenti dal ledger delle tracce (Fase 3,
promozione a `:Evento`) — funzione PURA di dominio: dato l'accesso a
`TracciaRepository`/`PatternCestinatoRepository`, produce i pattern
CANDIDATI alla promozione, esclusi quelli già cestinati. Nessun I/O diretto
qui: solo attraverso i due repository iniettati — testabile senza Postgres/
Neo4j reali, stesso stile di `recommender.ranking.costruisci_score_fn`.

Modello (congelato — brief "Rilevamento pattern ricorrenti + promozione"):
un pattern è identificato da `place_id` + INSIEME di `temi` (l'ordine non è
significativo — canonicalizzato come tupla ordinata alfabeticamente, stessa
convenzione di `traccia_repository.PatternAggregato`/
`cestino_repository.PatternCestinato`). Minimo `N_MINIMO_OCCORRENZE`
occorrenze per parlare di un ritmo — vincolo DURO, mai sotto 3: con 2
occorrenze esiste un solo intervallo, non abbastanza per distinguere un
ritmo da una coincidenza.

Fra le occorrenze (ordinate per `creato_il`) si calcolano gli intervalli
consecutivi; la REGOLARITÀ è misurata RELATIVA alla scala (coefficiente di
variazione = deviazione standard / media degli intervalli): la STESSA soglia
di tolleranza vale sia per un pattern settimanale (~7gg) sia per uno annuale
(~365gg), senza dover tarare per scala. NESSUNA finestra temporale W: si usa
tutta la storia disponibile del pattern (deliberato — non esiste già un
precedente per una W libera in questo repo, introdurla ora sarebbe una
scelta arbitraria non richiesta).

`cadenza_giorni` (salvata sul nodo `:Evento` alla promozione — VINCOLO
LOAD-BEARING: è l'input di un task futuro, la "frizione automatica a
cadenza" che conterà i "battiti mancati") è il valore MEDIO degli intervalli
— il valore rappresentativo del ritmo, non la mediana né l'ultimo intervallo
osservato.

`evento_esistente` (opzionale, iniettato — mai una connessione cablata qui):
un pattern il cui `:Evento` esiste GIÀ nel grafo (`evento_id_per_pattern`)
non è MAI restituito come candidato, per lo STESSO motivo di un pattern
cestinato — mostrarlo di nuovo esporrebbe il Promotore al rischio di
RIFIUTARLO (cestino PERMANENTE) mentre l'`:Evento` corrispondente resta
pubblico e attivo nel grafo: una divergenza cestino/grafo che nessun
meccanismo riconcilierebbe più (correzione ethics-guardian, a differenza di
`urban_memory.audit` per `MemoryContribution`)."""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .cestino_repository import PatternCestinatoRepository
from .promozione_evento import evento_id_per_pattern
from .traccia_repository import TracciaRepository

__all__ = [
    "N_MINIMO_OCCORRENZE",
    "TOLLERANZA_REGOLARITA",
    "PatternCandidato",
    "rileva_candidati",
]

#: Occorrenze minime per parlare di un ritmo — vincolo DURO (mai sotto 3, non
#: configurabile al di sotto): con 2 occorrenze esiste un solo intervallo,
#: non abbastanza per distinguere un ritmo da una coincidenza.
#: TUNING: il valore di partenza (3) è deliberatamente il minimo ammesso; da
#: calibrare verso l'ALTO sui dati reali del pilota, mai verso il basso —
#: `rileva_candidati` solleva `ValueError` se chiamata con un valore
#: inferiore.
N_MINIMO_OCCORRENZE: int = 3

#: Soglia di tolleranza sul coefficiente di variazione (deviazione standard
#: / media degli intervalli, in valore assoluto) sotto la quale un pattern è
#: CANDIDATO. TUNING: 0.35 è un valore di partenza ragionevole (tollera una
#: dispersione fino al 35% della media), da calibrare sui dati reali del
#: pilota — non definitivo.
TOLLERANZA_REGOLARITA: float = 0.35


@dataclass(frozen=True)
class PatternCandidato:
    """Un pattern rilevato come CANDIDATO alla promozione: place_id + temi
    (canonico, tupla ordinata alfabeticamente), le occorrenze che lo
    sostengono, la cadenza stimata (`cadenza_giorni`, media degli
    intervalli) e il coefficiente di variazione che ha superato la soglia di
    tolleranza — esposto per trasparenza/spiegabilità nella presentazione al
    Promotore (`urban_memory.curatela_pattern`), non solo per il calcolo
    interno."""

    place_id: str
    temi: tuple[str, ...]
    occorrenze: tuple[datetime, ...]
    cadenza_giorni: float
    coefficiente_variazione: float


def _intervalli_in_giorni(occorrenze: tuple[datetime, ...]) -> list[float]:
    """Intervalli, in giorni (float), fra occorrenze CONSECUTIVE — presume
    `occorrenze` già ordinate crescenti (garantito da
    `TracciaRepository.pattern_ricorrenti`)."""
    return [
        (dopo - prima).total_seconds() / 86400
        for prima, dopo in zip(occorrenze, occorrenze[1:], strict=False)
    ]


def rileva_candidati(
    traccia_repo: TracciaRepository,
    cestino_repo: PatternCestinatoRepository,
    *,
    minimo_occorrenze: int = N_MINIMO_OCCORRENZE,
    tolleranza: float = TOLLERANZA_REGOLARITA,
    evento_esistente: Callable[[str], bool] | None = None,
) -> list[PatternCandidato]:
    """Pattern CANDIDATI alla promozione, esclusi i cestinati E i già
    promossi (se `evento_esistente` è fornito).

    Solleva `ValueError` se `minimo_occorrenze` scende sotto il vincolo duro
    `N_MINIMO_OCCORRENZE` (3): non configurabile sotto questa soglia, a
    prescindere da chi chiama.

    Un pattern con media degli intervalli `<= 0` (occorrenze coincidenti
    nello stesso istante, o comunque un caso degenere in cui una "cadenza"
    non è definibile) non è MAI un candidato — nessuna divisione per zero,
    nessun valore fabbricato.

    `evento_esistente` — `Callable[[str], bool]`, tipicamente
    `promozione_evento.Neo4jPromozioneWriter.esiste` (metodo legato):
    riceve `evento_id_per_pattern(place_id, temi)` e ritorna `True` se
    quel `:Evento` esiste GIÀ nel grafo. `None` (default): NESSUN controllo
    — comportamento IDENTICO a prima di questa correzione, pensato SOLO per
    test di dominio puri che non riguardano il grafo. Chi rileva candidati
    per la curatela REALE (`urban_memory.curatela_pattern`) DEVE passarlo:
    ometterlo riapre il rischio che un pattern già promosso sia presentato
    di nuovo come candidato e venga rifiutato per errore (cestino
    permanente contro un `:Evento` pubblico rimasto attivo)."""
    if minimo_occorrenze < N_MINIMO_OCCORRENZE:
        raise ValueError(
            f"minimo_occorrenze={minimo_occorrenze} è sotto il vincolo duro "
            f"N_MINIMO_OCCORRENZE={N_MINIMO_OCCORRENZE}: non configurabile "
            "sotto 3 occorrenze."
        )

    candidati: list[PatternCandidato] = []
    for pattern in traccia_repo.pattern_ricorrenti(minimo_occorrenze):
        if cestino_repo.e_cestinato(pattern.place_id, list(pattern.temi)):
            continue  # cestinato: non ri-emerge MAI più, anche con nuove occorrenze

        if evento_esistente is not None and evento_esistente(
            evento_id_per_pattern(pattern.place_id, pattern.temi)
        ):
            continue  # già promosso: non ricompare come candidato da (ri)decidere

        intervalli = _intervalli_in_giorni(pattern.occorrenze)
        media = statistics.mean(intervalli)
        if media <= 0:
            continue  # nessuna cadenza definibile: non un candidato
        deviazione = statistics.pstdev(intervalli)
        coefficiente_variazione = deviazione / media

        if coefficiente_variazione <= tolleranza:
            candidati.append(
                PatternCandidato(
                    place_id=pattern.place_id,
                    temi=pattern.temi,
                    occorrenze=pattern.occorrenze,
                    cadenza_giorni=media,
                    coefficiente_variazione=coefficiente_variazione,
                )
            )
    return candidati
