"""GOLDEN di Lucca: il comportamento del motore sul dataset di Lucca, congelato.

I file in `golden/` (`lucca_itinerari.json`, `lucca_punteggi.json`) sono i VALORI
ATTESI, catturati UNA volta prima dei refactor (CITY_SEED, parametro `vocabolario`,
vocabolari dei temi spostati nel dataset). Sono CONGELATI dal commit in cui sono
entrati: nessun diff ammesso mai piu'. Mai rigenerati, nemmeno
automaticamente: se un file manca il test FALLISCE.

UN TEST CHE FALLISCE QUI E' UNA REGRESSIONE SU LUCCA, non un motivo per
rigenerare il golden. Si corregge il codice, non il JSON.

Due livelli, entrambi "replay" dei JSON (richiesta/specifica + atteso):
  a) ITINERARI via HTTP del BFF (`POST /itinerary`, `POST /itinerary/adapt`):
     uguaglianza ESATTA di `person_id`, `adattato_da_segnale` e, per ogni tappa,
     `experience_id`, `arrivo`, `durata_min`, `reason` (ordine incluso).
     `generated_at` escluso. Ambiente isolato: seed di Lucca, repository
     in-memory (recommender a freddo), nessuna credenziale, `adesso` fisso.
  b) PUNTEGGI: `rules.calcola_score` e la `score_fn` di
     `recommender.costruisci_score_fn` (repository vuoto = freddo; repository
     con eventi sintetici fissi = caldo), tolleranza ASSOLUTA 1e-9.

MANUTENZIONE: le firme cambieranno (parametro `vocabolario` keyword-only). Tutte
le chiamate a `calcola_score`, `costruisci_score_fn` e `SeedCandidateSource` sono
negli helper `_h_*` qui sotto: si adattano QUELLI, mai i JSON.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from experience_engine import rules  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import VOCABOLARIO  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import (  # noqa: E402
    BehaviorEventRepository,
    InMemoryBehaviorEventRepository,
    costruisci_score_fn,
)
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
FILE_ITINERARI = GOLDEN_DIR / "lucca_itinerari.json"
FILE_PUNTEGGI = GOLDEN_DIR / "lucca_punteggi.json"

ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
TOLLERANZA_ASSOLUTA = 1e-9
ESPERIENZE_LUCCA = 22


# ---------------------------------------------------------------------------
# Helper dipendenti dalle FIRME (unico punto da adattare nei refactor)
# ---------------------------------------------------------------------------


def _h_fonte_candidati() -> Any:
    """La fonte dei candidati di Lucca (seed versionato, nessun Neo4j)."""
    return SeedCandidateSource()


def _h_candidati_lucca() -> list[Any]:
    """I 22 candidati di Lucca, con un contesto neutro (nessun luogo visto)."""
    ctx = contracts.VisitorContext(
        person_id="golden-candidati",
        profile=contracts.EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5,
            con_bambini=False, tempo_disponibile_min=100000,
        ),
        signal=contracts.Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        ),
    )
    return list(_h_fonte_candidati().candidates(ctx))


def _h_calcola_score(candidato: Any, profilo: Any, segnale: Any) -> float:
    return float(rules.calcola_score(candidato, profilo, segnale, vocabolario=VOCABOLARIO))


def _h_score_fn(repo: BehaviorEventRepository, candidati: list[Any]) -> Any:
    return costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)


# ---------------------------------------------------------------------------
# Caricamento golden (mai rigenerato: se manca, FALLISCE)
# ---------------------------------------------------------------------------


def _carica(path: Path) -> dict[str, Any]:
    if not path.is_file():
        pytest.fail(
            f"golden mancante: {path}. I golden sono congelati e NON si rigenerano "
            "automaticamente: ripristinare il file dal repository."
        )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _id_casi() -> list[str]:
    if not FILE_ITINERARI.is_file():
        return ["__golden_mancante__"]
    return sorted(json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"])


# ---------------------------------------------------------------------------
# Livello a) itinerari via HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato: nessuna credenziale, nessuna cache, nessun orologio reale.

    I selettori sono sostituiti in `api.main` (come fanno gli altri test del
    BFF): `.env` e `lru_cache` di `api.deps` non hanno alcun effetto. Repository
    freschi per test: nessuno stato condiviso, recommender a freddo."""
    fonte = _h_fonte_candidati()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(api_main, "get_adesso", lambda: ADESSO_FISSO)
    return TestClient(api_main.app)


def _riduci(itinerario: dict[str, Any]) -> dict[str, Any]:
    """Solo i campi congelati; `generated_at` escluso."""
    return {
        "person_id": itinerario["person_id"],
        "adattato_da_segnale": itinerario["adattato_da_segnale"],
        "stops": [
            {k: s[k] for k in ("experience_id", "arrivo", "durata_min", "reason")}
            for s in itinerario["stops"]
        ],
    }


def test_golden_itinerari_presente_e_non_vuoto() -> None:
    casi = _carica(FILE_ITINERARI)["casi"]
    tipi = {c["tipo"] for c in casi.values()}
    assert tipi == {"compose", "adapt"}
    assert sum(1 for c in casi.values() if c["tipo"] == "compose") >= 40
    assert sum(1 for c in casi.values() if c["tipo"] == "adapt") >= 12


@pytest.mark.parametrize("chiave", _id_casi())
def test_golden_itinerario(client: TestClient, chiave: str) -> None:
    caso = _carica(FILE_ITINERARI)["casi"][chiave]
    percorso = "/itinerary" if caso["tipo"] == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=caso["richiesta"])
    assert resp.status_code == 200, resp.text
    assert _riduci(resp.json()) == caso["atteso"], f"REGRESSIONE su Lucca: {chiave}"


# ---------------------------------------------------------------------------
# Livello b) punteggi
# ---------------------------------------------------------------------------


def _chiave(experience_id: str, profilo: str, segnale: str) -> str:
    return f"{experience_id}|{profilo}|{segnale}"


def _confronta(attesi: dict[str, float], ottenuti: dict[str, float]) -> list[str]:
    errori: list[str] = []
    if set(attesi) != set(ottenuti):
        errori.append(f"insieme di chiavi diverso: {sorted(set(attesi) ^ set(ottenuti))[:5]}")
    for k, atteso in attesi.items():
        if k in ottenuti and not math.isclose(
            atteso, ottenuti[k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA
        ):
            errori.append(f"{k}: atteso {atteso!r}, ottenuto {ottenuti[k]!r}")
    return errori


def _calcola_tutto(spec: dict[str, Any]) -> dict[str, dict[str, float]]:
    profili = {k: contracts.EmotionalProfile.model_validate(v) for k, v in spec["profili"].items()}
    segnali = {k: contracts.Signal.model_validate(v) for k, v in spec["segnali"].items()}
    candidati = _h_candidati_lucca()

    caldo = InMemoryBehaviorEventRepository()
    for e in spec["eventi"]:
        caldo.record(contracts.BehaviorEvent.model_validate(e))
    fn_fredda = _h_score_fn(InMemoryBehaviorEventRepository(), candidati)
    fn_calda = _h_score_fn(caldo, candidati)

    out: dict[str, dict[str, float]] = {
        "calcola_score": {}, "score_fn_fredda": {}, "score_fn_calda": {},
    }
    for c in candidati:
        for np_, p in profili.items():
            for ns, s in segnali.items():
                k = _chiave(c.experience.id, np_, ns)
                out["calcola_score"][k] = _h_calcola_score(c, p, s)
                out["score_fn_fredda"][k] = float(fn_fredda(c, p, s))
                out["score_fn_calda"][k] = float(fn_calda(c, p, s))
    return out


def test_golden_punteggi_copre_tutte_le_esperienze() -> None:
    spec = _carica(FILE_PUNTEGGI)
    ids = {k.split("|")[0] for k in spec["punteggi"]["calcola_score"]}
    assert len(ids) == ESPERIENZE_LUCCA
    assert ids == {c.experience.id for c in _h_candidati_lucca()}


@pytest.mark.parametrize("funzione", ["calcola_score", "score_fn_fredda", "score_fn_calda"])
def test_golden_punteggi(funzione: str) -> None:
    spec = _carica(FILE_PUNTEGGI)
    errori = _confronta(spec["punteggi"][funzione], _calcola_tutto(spec)[funzione])
    assert not errori, f"REGRESSIONE su Lucca ({funzione}): {len(errori)} diff, es. {errori[:5]}"


def test_golden_score_fn_calda_esercita_il_termine_storico() -> None:
    """Il golden 'caldo' ha senso solo se lo storico cambia davvero i punteggi:
    sia nel file congelato sia ricalcolato ora."""
    spec = _carica(FILE_PUNTEGGI)
    p = spec["punteggi"]
    differenti = [
        k for k in p["score_fn_fredda"]
        if not math.isclose(
            p["score_fn_fredda"][k], p["score_fn_calda"][k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA
        )
    ]
    assert differenti, "la score_fn calda coincide con la fredda: storico non esercitato"
    # La fredda e' bit-identica a calcola_score solo se ENTRAMBE le quote sono spente.
    for k, v in p["calcola_score"].items():
        assert math.isclose(v, p["score_fn_fredda"][k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA)
