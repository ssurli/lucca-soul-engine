"""Misura (NON un test) della concentrazione dei flussi con e senza recommender.

Per ogni storico sintetico confronta
  A = distribuzione dei flussi con il ranking deterministico (`score_fn=None`),
  B = distribuzione dei flussi con `costruisci_score_fn` addestrato su quello
      storico,
sugli stessi 10 profili e sugli stessi candidati del test di integrazione
`tests/test_integration_wave3b.py` (da cui importa profili, segnale e i 4
scenari). La distribuzione e' `intelligence_index.distribuzione.distribuzione_flussi`
(piu' alta = flussi piu' distribuiti). Stampa A, B, B - A, il conteggio dei casi
con B >= A e il peggior B - A.

Batteria: i 4 scenari del test, piu' 40 storici casuali (seed 200-239; per ogni
seed `randint(3, 8)` luoghi, pesi `random() + 0.1`, massa totale 800).

Perche' NON e' un test: la batteria dei 40 storici casuali NON ha un esito
garantito (la correzione in uso e' provvisoria e B >= A non vale su ogni
storico). Renderla bloccante la farebbe fallire per una proprieta' che il
progetto non promette; serve invece a MISURARE quanto il recommender si
discosta dal ranking deterministico e a confrontare candidate diverse. Gli
scenari con esito richiesto restano nel test di integrazione.

Usa il motore e il recommender del repo correnti e il dataset della citta'
attiva (`CITY_SEED`, via `graph.registro`). Nessuna connessione: repository in
memoria, nessuna credenziale.

Uso (PowerShell, dalla radice del repo):

    .venv\\Scripts\\python.exe scripts\\misura_concentrazione_recommender.py
"""

from __future__ import annotations

import os
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

# Nessuna connessione: valori non raggiungibili se l'ambiente non li imposta.
os.environ.setdefault("NEO4J_URI", "bolt://127.0.0.1:1")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from contracts import BehaviorEvent, GraphCandidate, Itinerary, VisitorContext  # noqa: E402
from experience_engine.engine import compose_itinerary  # noqa: E402
from graph.registro import dataset_attivo  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from intelligence_index.distribuzione import distribuzione_flussi  # noqa: E402
from rag.reasons import compose_reason  # noqa: E402
from recommender import (  # noqa: E402
    PESI_TIPO,
    InMemoryBehaviorEventRepository,
    ScoreFn,
    costruisci_score_fn,
)
from test_integration_wave3b import (  # noqa: E402
    PROFILI_DIVERSI,
    SCENARI_DISTRIBUZIONE,
    SIGNALE_BASE,
)

MASSA_STORICA = 800.0
SEED_BATTERIA = range(200, 240)
TOLLERANZA = 1e-9

DATASET = dataset_attivo()
VOCABOLARIO = DATASET.vocabolario
N_LUOGHI = len(DATASET.luoghi)
ESPERIENZE_PER_LUOGO: dict[str, list[str]] = {}
for _esp in DATASET.esperienze:
    ESPERIENZE_PER_LUOGO.setdefault(_esp.place_id, []).append(_esp.id)
LUOGO_DI_ESPERIENZA = {e.id: e.place_id for e in DATASET.esperienze}


def _candidati() -> list[GraphCandidate]:
    ctx = VisitorContext(
        person_id="misura-template", profile=PROFILI_DIVERSI[0], signal=SIGNALE_BASE
    )
    return SeedCandidateSource(dataset=DATASET).candidates(ctx)


def _repo_da_massa(massa_per_luogo: dict[str, float]) -> InMemoryBehaviorEventRepository:
    repo = InMemoryBehaviorEventRepository()
    for place_id, massa in massa_per_luogo.items():
        ids = ESPERIENZE_PER_LUOGO[place_id]
        for experience_id in ids:
            for i in range(round(massa / len(ids) / PESI_TIPO["stop"])):
                repo.record(
                    BehaviorEvent(
                        person_id=f"misura-{experience_id}-{i}",
                        tipo="stop",
                        experience_id=experience_id,
                        ts=datetime(2026, 6, 1, tzinfo=UTC),
                    )
                )
    return repo


def _itinerari(candidati: list[GraphCandidate], score_fn: ScoreFn | None) -> list[Itinerary]:
    return [
        compose_itinerary(
            VisitorContext(person_id=f"misura-v{i}", profile=p, signal=SIGNALE_BASE),
            candidati,
            reason_fn=compose_reason,
            score_fn=score_fn,
            vocabolario=VOCABOLARIO,
        )
        for i, p in enumerate(PROFILI_DIVERSI)
    ]


def _distribuzione(itinerari: list[Itinerary]) -> float:
    luoghi = [LUOGO_DI_ESPERIENZA[s.experience_id] for it in itinerari for s in it.stops]
    return distribuzione_flussi(luoghi, N_LUOGHI)


def _storico_casuale(seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    luoghi = [luogo.id for luogo in DATASET.luoghi]
    k = rng.randint(3, 8)
    scelti_ids = rng.sample(luoghi, k)
    pesi = [rng.random() + 0.1 for _ in scelti_ids]
    tot = sum(pesi)
    return {p: w / tot * MASSA_STORICA for p, w in zip(scelti_ids, pesi, strict=True)}


def _riga(nome: str, a: float, b: float) -> float:
    d = b - a
    esito = "ok" if d >= -TOLLERANZA else "PEGGIORA"
    print(f"{nome:42} A={a:.4f}  B={b:.4f}  B-A={d:+.4f}  {esito}")
    return d


def main() -> None:
    candidati = _candidati()
    a = _distribuzione(_itinerari(candidati, None))
    print(f"dataset: {DATASET.nome}  luoghi={N_LUOGHI}  candidati={len(candidati)}  A={a:.4f}")

    print("\n== Scenari del test di integrazione ==")
    diffs_scenari: list[float] = []
    for sc in SCENARI_DISTRIBUZIONE:
        if not set(sc.massa_per_luogo) <= set(ESPERIENZE_PER_LUOGO):
            print(f"{sc.id:42} saltato: luoghi assenti nel dataset attivo")
            continue
        repo = _repo_da_massa(sc.massa_per_luogo)
        fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
        diffs_scenari.append(_riga(sc.id, a, _distribuzione(_itinerari(candidati, fn))))

    print("\n== Batteria storici casuali (seed 200-239) ==")
    diffs: list[float] = []
    for seed in SEED_BATTERIA:
        repo = _repo_da_massa(_storico_casuale(seed))
        fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
        diffs.append(_riga(f"seed {seed}", a, _distribuzione(_itinerari(candidati, fn))))

    ok = sum(d >= -TOLLERANZA for d in diffs)
    print(f"\nbatteria: B >= A in {ok}/{len(diffs)}  peggior B-A = {min(diffs):+.4f}")
    if diffs_scenari:
        oks = sum(d >= -TOLLERANZA for d in diffs_scenari)
        peggiore = min(diffs_scenari)
        print(f"scenari:  B >= A in {oks}/{len(diffs_scenari)}  peggior B-A = {peggiore:+.4f}")


if __name__ == "__main__":
    main()
