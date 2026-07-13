"""Test di integrazione — Wave 1: CRITERI DI ACCETTAZIONE.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, end-to-end,
senza alcun database attivo (`NEO4J_URI` non impostata => `SeedCandidateSource`,
22 esperienze di Lucca, offline). Ogni funzione qui sotto è UN criterio
d'accettazione della wave, leggibile da solo:

1. Onboarding -> `EmotionalProfile` -> `/itinerary` end-to-end (>= 2 tappe,
   entro il tempo disponibile).
2. Due profili emozionali marcatamente diversi => due itinerari DIVERSI.
3. `/itinerary/adapt` su pioggia riscrive le tappe all'aperto.
4. `/itinerary/adapt` su affollamento alto riscrive la tappa in quel luogo.
5. Ogni tappa ha un `reason` non vuoto, leggibile, in italiano.
6. L'accessibilità non è mai violata (`accessibilita_richiesta=True`).
7. Determinismo: stessa richiesta due volte => stesso itinerario.

Se un test qui fallisce, il bug è nel servizio a valle (api / experience-engine
/ rag / graph), non nel test: non "aggiustare" l'asserzione per farla passare,
segnala il bug al subagent competente (vedi CLAUDE.md).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)
seed_lucca = pytest.importorskip(
    "graph.seed_lucca", reason="`graph` non installabile: pip install -e services/graph"
)

TestClient = fastapi_testclient.TestClient

ESPERIENZE_BY_ID = {e.id: e for e in seed_lucca.ESPERIENZE}


@pytest.fixture()
def client() -> Any:
    return TestClient(api_main.app)


# ---------------------------------------------------------------------------
# Helper di costruzione payload (nessun contratto ridefinito: solo dizionari
# conformi a `packages/contracts`, come li manderebbe l'app Flutter).
# ---------------------------------------------------------------------------


def _signal(
    meteo: str = "sereno",
    affollamento: dict[str, float] | None = None,
    stanchezza: float = 0.2,
    ora: str = "10:00:00",
) -> dict[str, Any]:
    return {
        "meteo": meteo,
        "affollamento": affollamento or {},
        "stanchezza": stanchezza,
        "ora": ora,
    }


def _profile(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "curiosita": 0.5,
        "contemplazione": 0.5,
        "arte": 0.5,
        "con_bambini": False,
        "tempo_disponibile_min": 180,
    }
    base.update(overrides)
    return base


def _visitor_context(
    person_id: str,
    profile: dict[str, Any] | None = None,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "person_id": person_id,
        "profile": profile or _profile(),
        "signal": signal or _signal(),
    }


PROFILO_CONTEMPLATIVO_BAMBINI_TANTO_TEMPO = _profile(
    curiosita=0.15,
    contemplazione=0.9,
    arte=0.3,
    con_bambini=True,
    tempo_disponibile_min=240,
)

PROFILO_CURIOSO_ARTE_POCO_TEMPO = _profile(
    curiosita=0.95,
    contemplazione=0.15,
    arte=0.9,
    con_bambini=False,
    tempo_disponibile_min=90,
)


# ---------------------------------------------------------------------------
# 1. Onboarding -> EmotionalProfile -> /itinerary end-to-end
# ---------------------------------------------------------------------------


def test_onboarding_a_itinerario_end_to_end(client: Any) -> None:
    onboarding_payload = {
        "risposte": [
            {"domanda_id": "perdersi", "risposta": "sì, molto"},
            {"domanda_id": "silenzio_musica", "risposta": "cerco il silenzio"},
            {"domanda_id": "bellezza_storie", "risposta": "la bellezza"},
            {"domanda_id": "bambini", "risposta": "no, da sola"},
            {"domanda_id": "tempo", "risposta": "tre ore"},
            {"domanda_id": "accessibilita", "risposta": "no"},
            {"domanda_id": "firenze", "risposta": "no, mai vista"},
        ],
        "lingua": "it",
    }
    resp_onboarding = client.post("/session/onboarding", json=onboarding_payload)
    assert resp_onboarding.status_code == 200
    profile = resp_onboarding.json()

    # Il profilo risultante è un EmotionalProfile valido e coerente con le
    # risposte (tempo "tre ore" -> 180 minuti).
    assert profile["tempo_disponibile_min"] == 180
    assert 0 <= profile["curiosita"] <= 1

    ctx = _visitor_context("visitor-e2e", profile=profile)
    resp_itinerary = client.post("/itinerary", json=ctx)
    assert resp_itinerary.status_code == 200
    itinerary = resp_itinerary.json()

    assert len(itinerary["stops"]) >= 2, "l'itinerario deve avere almeno 2 tappe"

    tempo_usato = sum(stop["durata_min"] for stop in itinerary["stops"])
    assert tempo_usato <= profile["tempo_disponibile_min"], (
        "la somma delle durate delle tappe non deve superare il tempo disponibile "
        "dichiarato nel profilo (i trasferimenti si sommano sopra, quindi devono "
        "starci a maggior ragione)"
    )


# ---------------------------------------------------------------------------
# 2. Due profili diversi => due itinerari diversi
# ---------------------------------------------------------------------------


def test_due_profili_emozionali_diversi_producono_itinerari_diversi(client: Any) -> None:
    ctx_contemplativo = _visitor_context(
        "visitor-contemplativo", profile=PROFILO_CONTEMPLATIVO_BAMBINI_TANTO_TEMPO
    )
    ctx_curioso = _visitor_context("visitor-curioso", profile=PROFILO_CURIOSO_ARTE_POCO_TEMPO)

    resp1 = client.post("/itinerary", json=ctx_contemplativo)
    resp2 = client.post("/itinerary", json=ctx_curioso)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    itinerario1 = resp1.json()
    itinerario2 = resp2.json()

    ids1 = [stop["experience_id"] for stop in itinerario1["stops"]]
    ids2 = [stop["experience_id"] for stop in itinerario2["stops"]]

    assert ids1, "il profilo contemplativo deve produrre almeno una tappa"
    assert ids2, "il profilo curioso deve produrre almeno una tappa"
    assert ids1 != ids2, (
        "profili emozionali marcatamente diversi devono produrre itinerari "
        f"diversi: entrambi hanno prodotto {ids1}"
    )


# ---------------------------------------------------------------------------
# 3. /itinerary/adapt su pioggia
# ---------------------------------------------------------------------------


def test_adapt_su_pioggia_riscrive_le_tappe_allaperto(client: Any) -> None:
    # Profilo e tempo ampio scelti per garantire tappe all'aperto nel seed
    # (verificato sopra a mano: produce un mix di al_chiuso True/False).
    ctx = _visitor_context(
        "visitor-pioggia",
        profile=_profile(
            curiosita=0.5, contemplazione=0.7, arte=0.5, con_bambini=False,
            tempo_disponibile_min=200,
        ),
    )
    base_resp = client.post("/itinerary", json=ctx)
    assert base_resp.status_code == 200
    base = base_resp.json()

    al_chiuso_originale = [
        ESPERIENZE_BY_ID[stop["experience_id"]].al_chiuso for stop in base["stops"]
    ]
    assert any(not al_chiuso for al_chiuso in al_chiuso_originale), (
        "precondizione del test: l'itinerario di partenza deve contenere "
        "almeno una tappa all'aperto, altrimenti il test non verifica nulla"
    )

    adapt_payload = {
        "itinerary": base,
        "signal": _signal(meteo="pioggia"),
    }
    adapt_resp = client.post("/itinerary/adapt", json=adapt_payload)
    assert adapt_resp.status_code == 200
    adattato = adapt_resp.json()

    assert adattato["adattato_da_segnale"] is True

    al_chiuso_dopo = [
        ESPERIENZE_BY_ID[stop["experience_id"]].al_chiuso for stop in adattato["stops"]
    ]
    assert all(al_chiuso_dopo), (
        "con la pioggia nessuna tappa all'aperto deve restare nell'itinerario "
        f"adattato: {[stop['experience_id'] for stop in adattato['stops']]}"
    )


# ---------------------------------------------------------------------------
# 4. /itinerary/adapt su affollamento
# ---------------------------------------------------------------------------


def test_adapt_su_affollamento_riscrive_la_tappa_in_quel_luogo(client: Any) -> None:
    ctx = _visitor_context(
        "visitor-affollamento",
        profile=_profile(
            curiosita=0.5, contemplazione=0.6, arte=0.5, con_bambini=False,
            tempo_disponibile_min=200,
        ),
    )
    base_resp = client.post("/itinerary", json=ctx)
    assert base_resp.status_code == 200
    base = base_resp.json()
    assert base["stops"], "precondizione: serve almeno una tappa da affollare"

    prima_tappa_id = base["stops"][0]["experience_id"]
    place0 = ESPERIENZE_BY_ID[prima_tappa_id].place_id

    adapt_payload = {
        "itinerary": base,
        "signal": _signal(affollamento={place0: 0.9}),
    }
    adapt_resp = client.post("/itinerary/adapt", json=adapt_payload)
    assert adapt_resp.status_code == 200
    adattato = adapt_resp.json()

    assert adattato["adattato_da_segnale"] is True
    ids_dopo = [stop["experience_id"] for stop in adattato["stops"]]
    assert prima_tappa_id not in ids_dopo, (
        f"la tappa {prima_tappa_id!r} nel luogo affollato (0.9) doveva essere "
        f"sostituita, ma è ancora presente: {ids_dopo}"
    )


# ---------------------------------------------------------------------------
# 5. Ogni tappa ha un `reason` non vuoto, in italiano
# ---------------------------------------------------------------------------

# Parole italiane comuni che ci si aspetta di incontrare in un `reason`
# composto da `rag.reasons.compose_reason` (connettivi, articoli, verbi
# tipici delle frasi generate). Non è un controllo linguistico completo:
# è la rete di sicurezza minima contro un reason non tradotto o vuoto.
PAROLE_ITALIANE_ATTESE = {
    "è", "e", "il", "la", "di", "a", "con", "per", "che", "un", "una",
    "questo", "questa", "tappa", "sei", "sono", "ha", "hai", "tuo", "tua",
}


def _contiene_parola_italiana(testo: str) -> bool:
    parole = set(re.findall(r"[a-zàèéìòù']+", testo.lower()))
    return bool(parole & PAROLE_ITALIANE_ATTESE)


@pytest.mark.parametrize(
    "profile",
    [PROFILO_CONTEMPLATIVO_BAMBINI_TANTO_TEMPO, PROFILO_CURIOSO_ARTE_POCO_TEMPO],
)
def test_ogni_tappa_ha_reason_leggibile_in_italiano(client: Any, profile: dict[str, Any]) -> None:
    ctx = _visitor_context("visitor-reason", profile=profile)
    resp = client.post("/itinerary", json=ctx)
    assert resp.status_code == 200
    itinerary = resp.json()
    assert itinerary["stops"], "precondizione: serve almeno una tappa"

    for stop in itinerary["stops"]:
        reason = stop["reason"]
        assert reason, f"reason vuoto per la tappa {stop['experience_id']!r}"
        assert len(reason) > 10, (
            f"reason troppo corto per essere leggibile: {reason!r}"
        )
        assert _contiene_parola_italiana(reason), (
            f"reason non sembra in italiano: {reason!r}"
        )


# ---------------------------------------------------------------------------
# 6. Accessibilità mai violata
# ---------------------------------------------------------------------------


def test_accessibilita_richiesta_non_e_mai_violata(client: Any) -> None:
    ctx = _visitor_context(
        "visitor-accessibile",
        profile=_profile(
            curiosita=0.5, contemplazione=0.5, arte=0.8, con_bambini=False,
            tempo_disponibile_min=300, accessibilita_richiesta=True,
        ),
    )
    resp = client.post("/itinerary", json=ctx)
    assert resp.status_code == 200
    itinerary = resp.json()
    assert itinerary["stops"], "precondizione: serve almeno una tappa"

    for stop in itinerary["stops"]:
        esperienza = ESPERIENZE_BY_ID[stop["experience_id"]]
        assert esperienza.accessibile is True, (
            f"tappa non accessibile {stop['experience_id']!r} proposta a un "
            "profilo che ha dichiarato accessibilita_richiesta=True"
        )


# ---------------------------------------------------------------------------
# 7. Determinismo
# ---------------------------------------------------------------------------


def test_stessa_richiesta_due_volte_produce_lo_stesso_itinerario(client: Any) -> None:
    ctx = _visitor_context(
        "visitor-determinismo",
        profile=_profile(
            curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
            tempo_disponibile_min=180,
        ),
    )
    resp1 = client.post("/itinerary", json=ctx)
    resp2 = client.post("/itinerary", json=ctx)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    it1 = resp1.json()
    it2 = resp2.json()

    # `generated_at` è l'unico campo che legittimamente cambia tra due
    # chiamate (timestamp di composizione): il resto deve essere identico.
    stops1 = [{k: v for k, v in stop.items()} for stop in it1["stops"]]
    stops2 = [{k: v for k, v in stop.items()} for stop in it2["stops"]]
    assert stops1 == stops2
    assert it1["person_id"] == it2["person_id"]
    assert it1["adattato_da_segnale"] == it2["adattato_da_segnale"]
