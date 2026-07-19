"""Test di integrazione — Wave 3b: CRITERI DI ACCETTAZIONE (Recommender ML).

Chiama `experience_engine.engine.compose_itinerary` DIRETTAMENTE (nessun
BFF/HTTP: più semplice, più veloce, stesso principio di
`test_integration_wave1.py`), con candidati dal dataset canonico offline
(`graph.source.SeedCandidateSource` su `graph.seed_lucca`, 22 esperienze /
15 luoghi di Lucca, nessun database attivo). Ogni funzione qui sotto è UN
criterio d'accettazione della wave:

(b) DISTRIBUZIONE — IL CUORE DELLA WAVE (dichiarato esplicitamente dal
    committente: "questo test È il cuore della wave"). Uno storico
    sintetico FORTEMENTE concentrato su 2 `place_id` del seed (simula
    l'overtourism reale) non deve far aumentare la concentrazione dei
    luoghi scelti, rispetto al ranking deterministico, su una popolazione
    di 10 profili emozionali marcatamente diversi. Se questo fallisse, il
    recommender starebbe amplificando l'overtourism che questa wave esiste
    per contrastare: è un bug bloccante, non un dettaglio da aggiustare
    nell'assert.
(c) SPIEGABILITÀ — ogni tappa di ogni itinerario prodotto con lo `score_fn`
    del recommender (in qualunque scenario, incluso quello di (b)) ha un
    `reason` non vuoto e leggibile.
(d) COLD START end-to-end — con un repository di eventi VUOTO, l'itinerario
    prodotto con `score_fn=costruisci_score_fn(repo_vuoto, ...)` è
    BIT-IDENTICO (stessi `experience_id`, stesso ordine, stessi orari) a
    quello prodotto con `score_fn=None`.

Se un test qui fallisce, il bug è nel servizio a valle (recommender /
experience-engine), non nel test: non "aggiustare" l'asserzione per farla
passare, segnala il bug al subagent competente (vedi CLAUDE.md).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any

import pytest
from contracts import (
    BehaviorEvent,
    EmotionalProfile,
    GraphCandidate,
    Itinerary,
    Signal,
    VisitorContext,
)
from experience_engine.engine import compose_itinerary
from graph.seed_lucca import ESPERIENZE, LUOGHI
from graph.source import SeedCandidateSource
from rag.reasons import compose_reason
from recommender import PESI_TIPO, InMemoryBehaviorEventRepository, costruisci_score_fn

ESPERIENZE_BY_ID = {e.id: e for e in ESPERIENZE}

#: Universo dei `place_id` che il seed canonico può proporre (15): il
#: denominatore della metrica di distribuzione (sotto), NON il numero di
#: luoghi effettivamente comparsi in un dato itinerario.
N_LUOGHI_DISPONIBILI = len(LUOGHI)

SIGNALE_BASE = Signal(meteo="sereno", affollamento={}, stanchezza=0.2, ora=time(10, 0, 0))


# ---------------------------------------------------------------------------
# Helper 1: metrica di distribuzione (entropia di Shannon normalizzata)
# ---------------------------------------------------------------------------


def _distribuzione_flussi(place_ids: Iterable[str], n_luoghi_disponibili: int) -> float:
    """Indice di distribuzione dei flussi in [0, 1], STESSA semantica di
    `UrbanIntelligenceIndex.distribuzione_flussi`
    (`packages/contracts/contracts/models.py`): 1 = perfettamente
    distribuiti, 0 = completamente concentrati.

    Formula: entropia di Shannon normalizzata sul numero di luoghi
    DISPONIBILI (non su quelli effettivamente comparsi)::

        H(p) = - sum_i p_i * log(p_i)      p_i = frequenza del place_id i
                                            tra le tappe osservate
        distribuzione = H(p) / log(n)      n = N_LUOGHI_DISPONIBILI

    Normalizzare sull'intero universo di `place_id` che il grafo può
    proporre — non sul numero di luoghi distinti effettivamente comparsi —
    è la scelta deliberata che rende le due configurazioni (A:
    deterministica, B: con recommender) confrontabili A PARITÀ DI METRICA:
    usare invece il numero di luoghi comparsi premierebbe artificialmente
    una selezione che ne ignora la maggioranza ma distribuisce "bene" i
    pochi che tocca.

    - Massimo (1.0): ogni luogo disponibile compare con la stessa frequenza.
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


# ---------------------------------------------------------------------------
# Helper 2: 10 profili emozionali marcatamente diversi
# ---------------------------------------------------------------------------

#: Almeno 8-10 `EmotionalProfile` diversi tra loro (curiosità, contemplazione,
#: arte, con_bambini, tempo disponibile): un solo profilo non basta a
#: rivelare un bias SISTEMICO di concentrazione, serve vedere se il
#: recommender spinge visitatori DIVERSI verso GLI STESSI pochi luoghi.
PROFILI_DIVERSI: list[EmotionalProfile] = [
    EmotionalProfile(
        curiosita=0.9, contemplazione=0.1, arte=0.2,
        con_bambini=False, tempo_disponibile_min=90,
    ),
    EmotionalProfile(
        curiosita=0.1, contemplazione=0.9, arte=0.8,
        con_bambini=False, tempo_disponibile_min=240,
    ),
    EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5,
        con_bambini=True, tempo_disponibile_min=180,
    ),
    EmotionalProfile(
        curiosita=0.8, contemplazione=0.3, arte=0.9,
        con_bambini=False, tempo_disponibile_min=300,
    ),
    EmotionalProfile(
        curiosita=0.2, contemplazione=0.7, arte=0.1,
        con_bambini=True, tempo_disponibile_min=120,
    ),
    EmotionalProfile(
        curiosita=0.95, contemplazione=0.05, arte=0.95,
        con_bambini=False, tempo_disponibile_min=150,
    ),
    EmotionalProfile(
        curiosita=0.4, contemplazione=0.4, arte=0.4,
        con_bambini=False, tempo_disponibile_min=60,
    ),
    EmotionalProfile(
        curiosita=0.6, contemplazione=0.8, arte=0.3,
        con_bambini=True, tempo_disponibile_min=200,
    ),
    EmotionalProfile(
        curiosita=0.3, contemplazione=0.2, arte=0.7,
        con_bambini=False, tempo_disponibile_min=270,
    ),
    EmotionalProfile(
        curiosita=0.7, contemplazione=0.6, arte=0.6,
        con_bambini=True, tempo_disponibile_min=330,
    ),
]

#: 2 luoghi reali del seed su cui concentrare (quasi) tutto lo storico
#: sintetico: `mura-urbane` (exp-passeggiata-mura, exp-bici-mura) e
#: `piazza-anfiteatro` (exp-mercato-anfiteatro, exp-torchio-stamperia).
#: Gli altri ~13 luoghi non ricevono alcun evento storico.
ESPERIENZE_LUOGHI_CONCENTRATI = [
    "exp-passeggiata-mura",
    "exp-bici-mura",
    "exp-mercato-anfiteatro",
    "exp-torchio-stamperia",
]

#: Eventi "stop" per esperienza concentrata: 100 * 4 esperienze = 400 eventi,
#: peso 2.0 ciascuno (`recommender.features.PESI_TIPO["stop"]`) = 800 di
#: massa storica MAPPABILE, ben oltre `SOGLIA_MINIMA_EVENTI_MAPPABILI = 20`
#: (esce nettamente dal cold start).
N_EVENTI_PER_ESPERIENZA_CONCENTRATA = 100


def _repository_storico_concentrato() -> InMemoryBehaviorEventRepository:
    """Storico sintetico FORTEMENTE concentrato: simula l'overtourism reale
    (centinaia di eventi "stop" quasi tutti su 2 `place_id`, zero sugli
    altri ~13 luoghi del seed)."""
    repo = InMemoryBehaviorEventRepository()
    for experience_id in ESPERIENZE_LUOGHI_CONCENTRATI:
        for i in range(N_EVENTI_PER_ESPERIENZA_CONCENTRATA):
            repo.record(
                BehaviorEvent(
                    person_id=f"turista-storico-{experience_id}-{i}",
                    tipo="stop",
                    experience_id=experience_id,
                    ts=datetime(2026, 6, 1, tzinfo=UTC),
                )
            )
    return repo


# ---------------------------------------------------------------------------
# Fixture di scenario condivisa: (A) deterministico vs (B) con recommender,
# sui 10 profili, sullo STESSO storico concentrato e sugli STESSI candidati.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scenario_distribuzione() -> dict[str, Any]:
    fonte = SeedCandidateSource()
    # I candidati NON dipendono dal profilo (solo da `luoghi_gia_visti`,
    # vuoto qui): un'unica lista, reale, condivisa da entrambe le
    # configurazioni e da tutti i 10 profili.
    ctx_neutro = VisitorContext(
        person_id="visitor-w3b-template",
        profile=PROFILI_DIVERSI[0],
        signal=SIGNALE_BASE,
    )
    candidati = fonte.candidates(ctx_neutro)

    repo_concentrato = _repository_storico_concentrato()
    score_fn_b = costruisci_score_fn(repo_concentrato, candidati)

    itinerari_a: list[Itinerary] = []
    itinerari_b: list[Itinerary] = []
    for i, profilo in enumerate(PROFILI_DIVERSI):
        ctx = VisitorContext(
            person_id=f"visitor-w3b-{i}", profile=profilo, signal=SIGNALE_BASE
        )
        itinerari_a.append(
            compose_itinerary(ctx, candidati, reason_fn=compose_reason, score_fn=None)
        )
        itinerari_b.append(
            compose_itinerary(ctx, candidati, reason_fn=compose_reason, score_fn=score_fn_b)
        )

    return {"candidati": candidati, "itinerari_a": itinerari_a, "itinerari_b": itinerari_b}


# ---------------------------------------------------------------------------
# (b) DISTRIBUZIONE — il cuore della wave
#
# Il committente ha chiesto esplicitamente PIÙ scenari, per evitare
# l'overfitting al singolo scenario storico (concentrazione su 2 luoghi,
# `mura-urbane` + `piazza-anfiteatro`) che ha guidato il fix originale
# (smoothing di Laplace + quota strutturale in `recommender.ranking`):
# "se correggi finché questo scenario passa, hai reso il modello robusto a
# UN caso". Ogni scenario sotto gira come un test SEPARATO (parametrizzato):
# un fallimento in uno scenario non è mascherato dal successo degli altri.
#
# NOTA: lo scenario storico "originale" (2 luoghi, `_repository_storico_
# concentrato` / `scenario_distribuzione` sopra) resta invariato e continua
# ad alimentare SOLO i test (c) e (d) sotto — non è duplicato qui come
# scenario, perché i 4 scenari richiesti dal committente sono ulteriori
# rispetto a quello, non una sua riformulazione.
# ---------------------------------------------------------------------------

#: Peso di un evento "stop" (`recommender.features.PESI_TIPO`), riusato qui
#: (non un numero magico duplicato) per tradurre una "massa storica" bersaglio
#: in un numero di eventi sintetici da registrare.
PESO_EVENTO_STOP: float = PESI_TIPO["stop"]

#: Stessa massa storica totale (~800 di peso pesato) già usata dallo scenario
#: originale a 2 luoghi: tenerla COSTANTE tra tutti gli scenari rende le 4
#: distribuzioni_B confrontabili a parità di "quanta storia" alimenta il
#: recommender — cambia SOLO su quanti/quali luoghi quella massa si concentra,
#: ben oltre `SOGLIA_MINIMA_EVENTI_MAPPABILI = 20` in ogni scenario.
MASSA_STORICA_TOTALE: float = 800.0

#: Esperienze reali del seed, raggruppate per `place_id`: serve a distribuire
#: una massa storica bersaglio PER LUOGO sulle sue esperienze reali (mai un
#: `experience_id` inventato).
ESPERIENZE_PER_LUOGO: dict[str, list[str]] = {}
for _esperienza in ESPERIENZE:
    ESPERIENZE_PER_LUOGO.setdefault(_esperienza.place_id, []).append(_esperienza.id)


def _pesi_esperienza_da_massa_per_luogo(massa_per_luogo: dict[str, float]) -> dict[str, float]:
    """Traduce una massa storica bersaglio PER LUOGO (`place_id -> peso`) in
    una massa storica per ESPERIENZA (`experience_id -> peso`), l'unità che
    `BehaviorEvent`/il repository capiscono davvero.

    La massa di ciascun luogo è distribuita in parti UGUALI tra le sue
    esperienze reali del seed (1 esperienza = tutta la massa a lei; 2
    esperienze = metà ciascuna): il criterio di questa wave riguarda la
    concentrazione sul LUOGO fisico (vedi `_quota_storica_per_place` in
    `recommender.ranking`), non su quale delle sue esperienze la ospiti.
    """
    pesi_esperienza: dict[str, float] = {}
    for place_id, massa in massa_per_luogo.items():
        experience_ids = ESPERIENZE_PER_LUOGO.get(place_id)
        if not experience_ids:
            raise ValueError(
                f"place_id {place_id!r} non ha alcuna esperienza nel seed canonico "
                "(`graph.seed_lucca.ESPERIENZE`): scenario di test mal costruito"
            )
        quota = massa / len(experience_ids)
        for experience_id in experience_ids:
            pesi_esperienza[experience_id] = quota
    return pesi_esperienza


def _repository_da_pesi_esperienza(
    pesi_esperienza: dict[str, float],
) -> InMemoryBehaviorEventRepository:
    """Costruisce un repository storico sintetico con eventi "stop" (stesso
    tipo di evento dello scenario originale) tali che la massa PESATA per
    ogni `experience_id` approssimi `pesi_esperienza` (arrotondando al numero
    di eventi più vicino: la massa bersaglio è nell'ordine delle centinaia,
    l'arrotondamento a un singolo evento è trascurabile)."""
    repo = InMemoryBehaviorEventRepository()
    for experience_id, peso in pesi_esperienza.items():
        n_eventi = round(peso / PESO_EVENTO_STOP)
        for i in range(n_eventi):
            repo.record(
                BehaviorEvent(
                    person_id=f"turista-storico-{experience_id}-{i}",
                    tipo="stop",
                    experience_id=experience_id,
                    ts=datetime(2026, 6, 1, tzinfo=UTC),
                )
            )
    return repo


def _itinerari_b_per_repo(
    candidati: list[GraphCandidate], repo: InMemoryBehaviorEventRepository
) -> list[Itinerary]:
    """Itinerari (configurazione B, con recommender) per i 10
    `PROFILI_DIVERSI`, addestrati sullo storico di `repo` — stessi candidati e
    stesso segnale della fixture `contesto_base_w3b`."""
    score_fn_b = costruisci_score_fn(repo, candidati)
    itinerari_b: list[Itinerary] = []
    for i, profilo in enumerate(PROFILI_DIVERSI):
        ctx = VisitorContext(
            person_id=f"visitor-w3b-scenario-{i}", profile=profilo, signal=SIGNALE_BASE
        )
        itinerari_b.append(
            compose_itinerary(ctx, candidati, reason_fn=compose_reason, score_fn=score_fn_b)
        )
    return itinerari_b


def _massa_per_luogo_randomizzata(
    *, seed: int, min_luoghi: int, max_luoghi: int, massa_totale: float
) -> dict[str, float]:
    """Scenario 4: distribuzione CASUALE (ma riproducibile) della massa
    storica su un sottoinsieme casuale di `place_id` reali.

    `random.Random(seed)` — un'istanza LOCALE, mai `random` globale — con
    seed FISSO (42): la riproducibilità in CI è il punto stesso di questo
    scenario. Un seed non fisso renderebbe il test flaky (potrebbe passare o
    fallire a seconda della run) e, peggio, irriproducibile per chi indaga un
    fallimento: con un seed fisso lo scenario che fallisce oggi fallirà
    IDENTICO domani, su qualunque macchina.
    """
    rng = random.Random(seed)
    tutti_i_luoghi = [luogo.id for luogo in LUOGHI]
    n_luoghi = rng.randint(min_luoghi, max_luoghi)
    luoghi_scelti = rng.sample(tutti_i_luoghi, n_luoghi)
    # `+ 0.1`: evita che un peso grezzo capiti a ~0 (rng.random() in [0, 1)) e
    # un luogo scelto finisca con massa storica trascurabile per puro caso.
    pesi_grezzi = [rng.random() + 0.1 for _ in luoghi_scelti]
    totale_grezzo = sum(pesi_grezzi)
    return {
        luogo: (peso / totale_grezzo) * massa_totale
        for luogo, peso in zip(luoghi_scelti, pesi_grezzi, strict=True)
    }


@dataclass(frozen=True)
class ScenarioDistribuzione:
    """Uno scenario di storico sintetico per il criterio di distribuzione:
    `id` è il nome leggibile in `pytest -v` (un fallimento riporta ESATTAMENTE
    quale scenario), `massa_per_luogo` è la massa storica bersaglio per
    `place_id` reale del seed (tradotta in eventi da
    `_pesi_esperienza_da_massa_per_luogo` + `_repository_da_pesi_esperienza`)."""

    id: str
    massa_per_luogo: dict[str, float]


SCENARI_DISTRIBUZIONE: list[ScenarioDistribuzione] = [
    # 1) Concentrazione estrema su UN SOLO luogo reale, diverso da
    #    `san-michele-in-foro` (il luogo dominante per pertinenza strutturale
    #    pura — vedi `recommender.ranking.ARCHETIPI_STRUTTURALI` — che merita
    #    uno scenario dedicato, lo scenario 3 sotto): `mura-urbane`, con le
    #    sue 2 esperienze reali (`exp-passeggiata-mura`, `exp-bici-mura`) che
    #    si dividono l'intera massa storica.
    ScenarioDistribuzione(
        id="concentrazione_1_luogo_mura_urbane",
        massa_per_luogo={"mura-urbane": MASSA_STORICA_TOTALE},
    ),
    # 2) Concentrazione più ampia (5 dei 15 luoghi disponibili, un terzo),
    #    ma ancora marcata: massa storica ripartita in QUOTE UGUALI tra 5
    #    luoghi reali, tutti diversi da `san-michele-in-foro` (stesso motivo
    #    dello scenario 1 — quel luogo ha uno scenario dedicato).
    ScenarioDistribuzione(
        id="concentrazione_5_luoghi",
        massa_per_luogo={
            luogo: MASSA_STORICA_TOTALE / 5
            for luogo in (
                "mura-urbane",
                "piazza-anfiteatro",
                "orto-botanico",
                "san-frediano",
                "palazzo-pfanner",
            )
        },
    ),
    # 3) Il caso OPPOSTO a quello che ha causato il bug originale: lì
    #    `san-michele-in-foro` (il luogo dominante per pertinenza strutturale,
    #    verificato empiricamente contando le occorrenze nell'itinerario
    #    deterministico sui 10 profili: 13 tappe su 43, nettamente il primo)
    #    aveva ZERO eventi storici e poteva assorbire il flusso liberato dalla
    #    penalizzazione degli altri 2 luoghi concentrati. Qui invece riceve
    #    ANCH'ESSO una quota di storico REALE — proporzionata ma NON
    #    maggioritaria (250 su 800 = 31%) — insieme a 2 altri luoghi
    #    concentrati (`mura-urbane` 350, `piazza-anfiteatro` 200): il caso
    #    realistico in cui un luogo popolare per contenuto accumula ANCHE
    #    footfall reale tracciato.
    ScenarioDistribuzione(
        id="storico_anche_su_san_michele_in_foro",
        massa_per_luogo={
            "san-michele-in-foro": 250.0,
            "mura-urbane": 350.0,
            "piazza-anfiteatro": 200.0,
        },
    ),
    # 4) Randomizzato con seed fisso (42, riproducibile in CI — vedi
    #    `_massa_per_luogo_randomizzata`): un sottoinsieme casuale (tra 3 e 8)
    #    dei 15 luoghi reali, con pesi casuali ma massa totale invariata
    #    (~800, ben oltre `SOGLIA_MINIMA_EVENTI_MAPPABILI = 20`). Con
    #    seed=42 il campione risultante è 8 luoghi (`piazza-anfiteatro`,
    #    `mura-urbane`, `piazza-napoleone`, `casa-puccini`,
    #    `duomo-san-martino`, `torre-delle-ore`, `torre-guinigi`,
    #    `museo-nazionale-guinigi`) — NON include `san-michele-in-foro` per
    #    puro esito del campionamento, non per scelta esplicita: a differenza
    #    degli scenari 1-3, qui il campione stesso (non solo i pesi) dipende
    #    dal seed.
    ScenarioDistribuzione(
        id="randomizzato_seed_42",
        massa_per_luogo=_massa_per_luogo_randomizzata(
            seed=42, min_luoghi=3, max_luoghi=8, massa_totale=MASSA_STORICA_TOTALE
        ),
    ),
]


@pytest.fixture(scope="module")
def contesto_base_w3b() -> dict[str, Any]:
    """Candidati e itinerari DETERMINISTICI (configurazione A), CONDIVISI da
    tutti e 4 gli scenari: A non dipende in alcun modo dallo storico
    (`score_fn=None`), quindi calcolarlo una volta sola per modulo è corretto
    (non un'ottimizzazione che nasconde una dipendenza reale) e garantisce
    che i 4 scenari confrontino la stessa identica baseline."""
    fonte = SeedCandidateSource()
    ctx_neutro = VisitorContext(
        person_id="visitor-w3b-scenari-template",
        profile=PROFILI_DIVERSI[0],
        signal=SIGNALE_BASE,
    )
    candidati = fonte.candidates(ctx_neutro)

    itinerari_a: list[Itinerary] = []
    for i, profilo in enumerate(PROFILI_DIVERSI):
        ctx = VisitorContext(
            person_id=f"visitor-w3b-scenari-{i}", profile=profilo, signal=SIGNALE_BASE
        )
        itinerari_a.append(
            compose_itinerary(ctx, candidati, reason_fn=compose_reason, score_fn=None)
        )

    return {"candidati": candidati, "itinerari_a": itinerari_a}


@pytest.mark.parametrize(
    "scenario", SCENARI_DISTRIBUZIONE, ids=[s.id for s in SCENARI_DISTRIBUZIONE]
)
def test_il_recommender_non_aumenta_la_concentrazione_dei_flussi(
    scenario: ScenarioDistribuzione,
    contesto_base_w3b: dict[str, Any],
) -> None:
    candidati: list[GraphCandidate] = contesto_base_w3b["candidati"]
    itinerari_a: list[Itinerary] = contesto_base_w3b["itinerari_a"]

    pesi_esperienza = _pesi_esperienza_da_massa_per_luogo(scenario.massa_per_luogo)
    repo = _repository_da_pesi_esperienza(pesi_esperienza)
    itinerari_b = _itinerari_b_per_repo(candidati, repo)

    assert all(it.stops for it in itinerari_a), "precondizione: ogni profilo produce tappe (A)"
    assert all(it.stops for it in itinerari_b), "precondizione: ogni profilo produce tappe (B)"

    place_ids_a = [
        ESPERIENZE_BY_ID[stop.experience_id].place_id
        for it in itinerari_a
        for stop in it.stops
    ]
    place_ids_b = [
        ESPERIENZE_BY_ID[stop.experience_id].place_id
        for it in itinerari_b
        for stop in it.stops
    ]

    distribuzione_a = _distribuzione_flussi(place_ids_a, N_LUOGHI_DISPONIBILI)
    distribuzione_b = _distribuzione_flussi(place_ids_b, N_LUOGHI_DISPONIBILI)

    # Criterio di successo della wave: il recommender (B), addestrato su
    # QUESTO scenario di storico concentrato, non deve produrre tappe
    # aggregate PIÙ concentrate del ranking deterministico (A). Tolleranza
    # minima solo per instabilità numerica del logaritmo in virgola mobile.
    # NON indebolire mai questo assert per farlo passare: uno scenario che lo
    # viola è un bug bloccante nel recommender, da segnalare, non da
    # nascondere allentando la soglia.
    assert distribuzione_b >= distribuzione_a - 1e-9, (
        f"[scenario={scenario.id!r}] il recommender ha AUMENTATO la "
        f"concentrazione dei flussi rispetto al ranking deterministico: "
        f"distribuzione_A={distribuzione_a!r}, distribuzione_B={distribuzione_b!r} "
        f"(massa_per_luogo={scenario.massa_per_luogo!r}, "
        f"place_ids_A={place_ids_a}, place_ids_B={place_ids_b})"
    )

    # Assert di sanità: il recommender deve DAVVERO agire (produrre un
    # ordinamento diverso per almeno una parte dei profili), altrimenti il
    # test sopra passerebbe banalmente perché il recommender è inerte.
    ids_a_per_profilo = [[s.experience_id for s in it.stops] for it in itinerari_a]
    ids_b_per_profilo = [[s.experience_id for s in it.stops] for it in itinerari_b]
    almeno_un_profilo_diverso = any(
        a != b for a, b in zip(ids_a_per_profilo, ids_b_per_profilo, strict=True)
    )
    assert almeno_un_profilo_diverso, (
        f"[scenario={scenario.id!r}] il recommender non ha cambiato "
        "l'ordinamento di NESSUN profilo rispetto al ranking deterministico: "
        f"con uno storico così concentrato ({MASSA_STORICA_TOTALE!r} di massa "
        f"storica su {scenario.massa_per_luogo!r}) dovrebbe modulare l'ordine "
        "per almeno alcuni dei 10 profili — il test sulla distribuzione "
        "passerebbe altrimenti solo perché il recommender è di fatto inerte, "
        "non perché protegge davvero dall'overtourism."
    )


# ---------------------------------------------------------------------------
# (c) SPIEGABILITÀ
# ---------------------------------------------------------------------------


def test_ogni_tappa_col_recommender_ha_reason_non_vuoto_e_leggibile(
    scenario_distribuzione: dict[str, Any],
) -> None:
    itinerari_b: list[Itinerary] = scenario_distribuzione["itinerari_b"]
    assert itinerari_b, "precondizione: lo scenario deve produrre itinerari"

    for itinerario in itinerari_b:
        assert itinerario.stops, f"nessuna tappa per {itinerario.person_id!r}"
        for stop in itinerario.stops:
            reason = stop.reason
            assert reason, (
                f"reason vuoto per la tappa {stop.experience_id!r} "
                f"({itinerario.person_id!r})"
            )
            assert reason.strip(), (
                f"reason tutto whitespace per la tappa {stop.experience_id!r} "
                f"({itinerario.person_id!r})"
            )
            assert len(reason) > 10, (
                f"reason troppo corto per essere leggibile: {reason!r} "
                f"(tappa {stop.experience_id!r}, {itinerario.person_id!r})"
            )


# ---------------------------------------------------------------------------
# (d) COLD START end-to-end
# ---------------------------------------------------------------------------


def test_cold_start_end_to_end_itinerario_bit_identico_a_score_fn_none() -> None:
    fonte = SeedCandidateSource()
    profilo = EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=180,
    )
    ctx = VisitorContext(person_id="visitor-w3b-cold-start", profile=profilo, signal=SIGNALE_BASE)
    candidati = fonte.candidates(ctx)

    repo_vuoto = InMemoryBehaviorEventRepository()
    score_fn_cold_start = costruisci_score_fn(repo_vuoto, candidati)

    itinerario_deterministico = compose_itinerary(
        ctx, candidati, reason_fn=compose_reason, score_fn=None
    )
    itinerario_cold_start = compose_itinerary(
        ctx, candidati, reason_fn=compose_reason, score_fn=score_fn_cold_start
    )

    assert itinerario_deterministico.stops, "precondizione: servono tappe da confrontare"

    # BIT-IDENTICO, non un'approssimazione: stessi experience_id, stesso
    # ordine, stessi orari, stessi reason (stesso reason_fn, stesso score
    # per costruzione => stesso ordinamento => stesso orario progressivo).
    assert itinerario_deterministico.stops == itinerario_cold_start.stops, (
        "cold start (repository di eventi vuoto): l'itinerario col "
        "recommender deve essere BIT-IDENTICO a quello con score_fn=None, "
        f"invece:\ndeterministico={itinerario_deterministico.stops!r}\n"
        f"cold_start={itinerario_cold_start.stops!r}"
    )
    assert itinerario_deterministico.person_id == itinerario_cold_start.person_id
    assert (
        itinerario_deterministico.adattato_da_segnale
        == itinerario_cold_start.adattato_da_segnale
    )
