"""Calcola l'Urban Intelligence Index sul periodo corrente contro le fonti reali
(Neon/Aura, lette dal .env alla radice del repo) — nessun BFF, nessun endpoint:
chiama direttamente `intelligence_index.calcola_index`, la stessa funzione pura
usata dai test.

Uso (PowerShell, dalla radice del repo):

    python scripts\\verifica_index.py [YYYY-MM]

Senza argomenti usa il mese corrente. Solleva DatiInsufficientiError con un
messaggio leggibile se la popolazione di un indicatore e' sotto k=10 -- e'
il comportamento ATTESO (soppressione), non un errore da correggere.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from intelligence_index import calcola_index, deps
from intelligence_index.catalogo import esperienze_per_id
from intelligence_index.periodo import intervallo_periodo
from intelligence_index.soglia import DatiInsufficientiError

periodo = sys.argv[1] if len(sys.argv) > 1 else datetime.now(UTC).strftime("%Y-%m")

fonte_candidati = deps.get_candidate_source()
fonte_metriche = deps.get_metrics_source()
sorgente_eventi = deps.get_event_source()
repo_memoria = deps.get_memory_repository()

print(f"periodo={periodo!r}")
print(f"candidate_source={type(fonte_candidati).__name__}")
print(f"metrics_source={type(fonte_metriche).__name__}")
print(f"event_source={type(sorgente_eventi).__name__}")
print(f"memory_repository={type(repo_memoria).__name__}")

catalogo = esperienze_per_id(fonte_candidati)
grado = fonte_metriche.grado_semantico()
inizio, fine = intervallo_periodo(periodo)
non_connesse, denominatore = fonte_metriche.non_connected_place_pairs(at=inizio)

eventi = sorgente_eventi.events_in_period(inizio, fine)
memorie = repo_memoria.list_pending() + repo_memoria.list_curated()

print(f"luoghi nel catalogo: {len(catalogo)}")
print(f"eventi nel periodo: {len(eventi)}")
print(f"contributi Urban Memory (pending+curati) nel periodo: {len(memorie)}")
print(f"coppie non connesse a inizio periodo: {denominatore}")

try:
    indice = calcola_index(
        periodo=periodo,
        eventi=eventi,
        esperienze_per_id=catalogo,
        grado_semantico=grado,
        n_luoghi_disponibili=len(grado),
        non_connesse_a_inizio_periodo=non_connesse,
        itinerari_periodo=[],  # buco nei dati noto: nessuna persistenza reale oggi
        memorie=memorie,
    )
except DatiInsufficientiError as exc:
    print(f"\nSOPPRESSO (atteso sotto k=10): {exc}")
else:
    print("\n" + indice.model_dump_json(indent=2))
