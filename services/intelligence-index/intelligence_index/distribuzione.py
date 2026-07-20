"""`distribuzione_flussi` — entropia di Shannon normalizzata.

FORMULA GIÀ NEGOZIATA col committente. Nasce come helper di test in
`tests/test_integration_wave3b.py` (Wave 3b, criterio di accettazione "il
recommender non deve aumentare la concentrazione dei flussi rispetto al
ranking deterministico"), PRIMA che esistesse questo modulo: quel test
misurava la stessa nozione di concentrazione che
`UrbanIntelligenceIndex.distribuzione_flussi` (Wave 4) deve ora riportare al
Comune. Questa funzione È l'estrazione di quella formula in un'UNICA fonte
di verità: sia `tests/test_integration_wave3b.py` sia
`intelligence_index.indicatori` la IMPORTANO da qui — nessuna delle due la
ridefinisce (vedi il commit che ha spostato il codice, non duplicato).

`distribuzione_flussi` È L'INDICATORE CHE CI GIUDICA (CLAUDE.md): misura
DIRETTAMENTE l'overtourism. Se sale la concentrazione, il sistema sta
fallendo il proprio scopo — anche se tutti gli altri indicatori sono buoni.
Va reso visibile, mai nascosto o smussato: nessuna delle funzioni di questo
modulo applica un floor, un cap "cosmetico" o un arrotondamento che
attenuerebbe un valore basso.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

__all__ = ["distribuzione_flussi"]


def distribuzione_flussi(place_ids: Iterable[str], n_luoghi_disponibili: int) -> float:
    """Indice di distribuzione dei flussi in `[0, 1]`: `1` = perfettamente
    distribuiti, `0` = completamente concentrati.

    Formula: entropia di Shannon normalizzata sul numero di luoghi
    DISPONIBILI (non su quelli effettivamente comparsi tra `place_ids`)::

        H(p) = - sum_i p_i * log(p_i)      p_i = frequenza del place_id i
                                            tra le tappe osservate
        distribuzione = H(p) / log(n)      n = n_luoghi_disponibili

    Normalizzare sull'intero universo di `place_id` che il grafo può
    proporre — non sul numero di luoghi distinti effettivamente comparsi in
    `place_ids` — è la scelta deliberata che rende confrontabili due
    popolazioni di tappe diverse A PARITÀ DI METRICA: usare invece il numero
    di luoghi comparsi premierebbe artificialmente una popolazione che ne
    tocca pochi ma li distribuisce "bene" fra loro, ignorando la maggior
    parte della città.

    - Massimo (1.0): ogni luogo disponibile compare con la stessa frequenza
      (o non è comparsa nessuna tappa: nulla da penalizzare).
    - Minimo (0.0): un solo `place_id` concentra tutte le tappe (H = 0).
    """
    ids = list(place_ids)
    if not ids:
        return 1.0  # nessuna tappa osservata: nessuna concentrazione da penalizzare
    if n_luoghi_disponibili <= 1:
        return 1.0  # normalizzazione indefinita (log(1) == 0): caso degenere
    conteggi = Counter(ids)
    totale = sum(conteggi.values())
    entropia = -sum((n / totale) * math.log(n / totale) for n in conteggi.values())
    return entropia / math.log(n_luoghi_disponibili)
