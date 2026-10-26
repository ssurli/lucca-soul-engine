"""Taglio per stanchezza via BFF isolato (ondata 3, compito 1).

Caso reale: profilo curioso dalle risposte dell'app, mezza giornata (180 min),
sabato 12/12/2026 alle 15:00; poi "Piove" + "Sono stanco/a" (pioggia,
stanchezza 0.85). Itinerario ricevuto 25+30+40+35+10 = 140 min -> limite 93.
Dopo la sostituzione della prima tappa (20 min) il tempo è 20, 50, 90, 125, 135:
90 è più vicino a 93 di 125, quindi restano TRE tappe; quarta e quinta tagliate.

Ondata 3, compito 4: con i trasferimenti dai punti di arrivo (al posto della
stima prudente di 10 min) nella mezza giornata entra una quinta tappa da 20
min; prima l'itinerario ricevuto era 25+30+40+35 = 130 (limite 86) e veniva
tagliata la sola quarta. Il caso resta "tre tappe tenute".

Ondata 3, compito 8: con i tre luoghi nuovi la quinta tappa e' una da 10 min (prima
20): itinerario 140 min, limite 93 (prima 150 e 100); stesso esito, tre tappe tenute.

Ondata 4, compito 1 (decisione del committente, 26/10, APPROVATA): dall'ondata 4 la
composizione riordina le tappe per vicinanza (engine._riordina_per_vicinanza), quindi
il flusso reale non produce piu' questo itinerario. L'INGRESSO di
test_piove_e_stanco_tiene_tre_tappe e' stato CONGELATO come dato (ITINERARIO_ORDINE_VECCHIO,
composto con il riordino sostituito dall'identita', stesso profilo e stesso segnale): tutte le
sue asserzioni sono rimaste identiche. Il flusso reale riordinato e' coperto da
test_flusso_reale_riordinato_piove_e_stanco.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from contracts import OnboardingAnswer, OnboardingRequest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from rag.onboarding import profile_from_answers  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

RISPOSTE = {
    "perdersi": "Sì, mi piace perdermi senza una meta precisa",
    "bambini": "No, non sono con bambini",
    "tempo": "Mezza giornata, circa tre ore",
    "accessibilita": "No, nessuna esigenza di accessibilità",
    "silenzio_musica": "Un mix tra silenzio e musica",
    "bellezza_storie": "Un po' di bellezza e un po' di storie",
}
SEGNALE = {
    "meteo": "sereno", "affollamento": {}, "stanchezza": 0.1, "ora": "15:00:00",
    "data": "2026-12-12", "eventi_attivi": [], "istante": "2026-12-12T14:00:00Z",
}


ITINERARIO_ORDINE_VECCHIO: dict[str, Any] = {'person_id': 'p',
 'stops': [{'experience_id': 'exp-facciata-san-michele',
            'titolo': 'La facciata scolpita di San Michele in Foro',
            'arrivo': '15:00:00',
            'durata_min': 25,
            'reason': 'Hai voglia di perderti e lasciarti sorprendere. In questa chiesa il '
                      "giovane Giacomo Puccini dava lezioni d'organo al suo unico allievo, il "
                      'sarto Carlo Della Nina; per la festa di San Michele vi si suonano '
                      "ancora musiche della famiglia Puccini. All'aperto.",
            'esito_adattamento': None,
            'curiosita': [{'testo': "Si racconta che nell'anello al dito dell'arcangelo, in "
                                    'cima alla facciata, sia incastonato un grande smeraldo, '
                                    'visibile al tramonto da un punto preciso della piazza.',
                           'tipo': 'leggenda',
                           'fonte': 'Comune di Lucca, Mappa del centro storico 2024',
                           'fonte_pubblica': True}],
            'punto_arrivo': {'lat': 43.843206920716746, 'lon': 10.502521515682991}},
           {'experience_id': 'exp-interno-san-frediano',
            'titolo': 'La basilica di San Frediano e il fonte lustrale',
            'arrivo': '15:31:00',
            'durata_min': 30,
            'reason': 'Temi: romanico, arte, medioevo. Al chiuso.',
            'esito_adattamento': None,
            'curiosita': [{'testo': 'Nel mosaico della facciata compare anche Giuda, che '
                                    "l'iconografia classica non metterebbe in questa scena. "
                                    'Alza la mano destra chiusa, con indice e mignolo tesi: il '
                                    'racconto popolare ci vede il gesto delle corna.',
                           'tipo': 'fatto',
                           'fonte': 'dato del committente',
                           'fonte_pubblica': False}],
            'punto_arrivo': {'lat': 43.84611439494372, 'lon': 10.504828564629559}},
           {'experience_id': 'exp-santi-giovanni-reparata',
            'titolo': "La chiesa dei Santi Giovanni e Reparata e l'area archeologica",
            'arrivo': '16:10:00',
            'durata_min': 40,
            'reason': 'Temi: storia, arte, romanico. Al chiuso.',
            'esito_adattamento': None,
            'curiosita': [],
            'punto_arrivo': {'lat': 43.84119039780105, 'lon': 10.504274232740409}},
           {'experience_id': 'exp-duomo-volto-santo',
            'titolo': 'Il Volto Santo e il labirinto del Duomo',
            'arrivo': '16:52:00',
            'durata_min': 35,
            'reason': 'Nel 1751, a otto anni, Luigi Boccherini debuttò come voce bianca nelle '
                      'feste di Santa Croce, celebrate in questa cattedrale. Al chiuso.',
            'esito_adattamento': None,
            'curiosita': [{'testo': 'Sul pilastro del portico è inciso un labirinto, con '
                                    "un'iscrizione latina che richiama Dedalo e Teseo. Lo si "
                                    "legge come simbolo del cammino dell'anima verso la "
                                    'redenzione, lungo la Via Francigena.',
                           'tipo': 'fatto',
                           'fonte': 'dato del committente',
                           'fonte_pubblica': False}],
            'punto_arrivo': {'lat': 43.8407348442907, 'lon': 10.50546424867784}},
           {'experience_id': 'exp-solchi-san-pietro-somaldi',
            'titolo': 'I solchi sulla porta di San Pietro Somaldi',
            'arrivo': '17:37:00',
            'durata_min': 10,
            'reason': "Temi: storia, romanico. All'aperto.",
            'esito_adattamento': None,
            'curiosita': [{'testo': 'Sulla facciata e sugli stipiti del portale principale si '
                                    'vedono tre solchi paralleli scavati nella pietra, simili '
                                    'a graffi di artigli.',
                           'tipo': 'fatto',
                           'fonte': 'dato del committente',
                           'fonte_pubblica': False},
                          {'testo': 'Si racconta che siano le unghiate del diavolo.',
                           'tipo': 'leggenda',
                           'fonte': 'dato del committente',
                           'fonte_pubblica': False}],
            'punto_arrivo': {'lat': 43.84555613789234, 'lon': 10.508002871124265}}],
 'generated_at': '2026-10-26T10:09:21.762691',
 'adattato_da_segnale': False,
 'tempo_disponibile_min': 180,
 'tempo_effettivo_min': 180,
 'tappe_escluse': []}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato come in `test_golden_lucca.py`: seed versionato, repository
    in memoria, orologio fisso, nessuna credenziale."""
    fonte = SeedCandidateSource()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(
        api_main, "get_adesso", lambda: datetime(2026, 12, 12, 14, 0, tzinfo=UTC)
    )
    return TestClient(api_main.app)


def test_piove_e_stanco_tiene_tre_tappe(client: TestClient) -> None:
    req = OnboardingRequest(
        lingua="it",
        risposte=[OnboardingAnswer(domanda_id=k, risposta=v) for k, v in RISPOSTE.items()],
    )
    profilo = profile_from_answers(req).model_dump(mode="json")
    it: dict[str, Any] = copy.deepcopy(ITINERARIO_ORDINE_VECCHIO)
    durate = [s["durata_min"] for s in it["stops"]]
    # Precondizione del caso: se il seed cambia, il caso va ripensato.
    assert durate == [25, 30, 40, 35, 10]
    assert int(sum(durate) * 2 / 3) == 93

    r = client.post(
        "/itinerary/adapt",
        json={
            "itinerary": it,
            "signal": {**SEGNALE, "meteo": "pioggia", "stanchezza": 0.85},
            "profile": profilo,
        },
    )
    assert r.status_code == 200
    ad: dict[str, Any] = r.json()
    assert [s["durata_min"] for s in ad["stops"]] == [20, 30, 40]
    assert [s["esito_adattamento"] for s in ad["stops"]] == [
        "sostituita", "non_toccata", "non_toccata",
    ]
    # Prefisso: le tre tappe tenute sono le prime tre ricevute (la prima
    # sostituita), le tagliate sono le ultime due.
    assert [s["experience_id"] for s in ad["stops"]][1:] == [
        s["experience_id"] for s in it["stops"][1:3]
    ]
    assert [(e["experience_id"], e["esito"]) for e in ad["tappe_escluse"]] == [
        (it["stops"][3]["experience_id"], "tagliata_stanchezza"),
        (it["stops"][4]["experience_id"], "tagliata_stanchezza"),
    ]
    assert ad["adattato_da_segnale"] is True


def test_flusso_reale_riordinato_piove_e_stanco(client: TestClient) -> None:
    """Stesso profilo e stesso segnale, ma composizione REALE (con il riordino
    per vicinanza) e poi "Piove" + stanchezza 0.85.

    Composizione: facciata-san-michele, interno-san-frediano, solchi-san-pietro-somaldi,
    santi-giovanni-reparata, duomo-volto-santo (durate 25, 30, 10, 40, 35 = 140, limite 93).
    Dopo le sostituzioni le durate correnti sono 20, 30, 20, 40, 35 e i totali cumulati
    20, 50, 70, 110, 145: la quarta si tiene (|110 - 93| = 17 < |70 - 93| = 23), la quinta no
    (|145 - 93| = 52 >= 17). Il tempo tenuto e' quindi 110 minuti (somma delle durate,
    senza trasferimenti, come _taglia_per_stanchezza) contro un limite di 93."""
    req = OnboardingRequest(
        lingua="it",
        risposte=[OnboardingAnswer(domanda_id=k, risposta=v) for k, v in RISPOSTE.items()],
    )
    profilo = profile_from_answers(req).model_dump(mode="json")
    r = client.post(
        "/itinerary",
        json={"person_id": "p", "kind": "turista", "profile": profilo, "signal": SEGNALE},
    )
    assert r.status_code == 200
    it: dict[str, Any] = r.json()
    assert [s["experience_id"] for s in it["stops"]] == [
        "exp-facciata-san-michele",
        "exp-interno-san-frediano",
        "exp-solchi-san-pietro-somaldi",
        "exp-santi-giovanni-reparata",
        "exp-duomo-volto-santo",
    ]
    durate = [s["durata_min"] for s in it["stops"]]
    assert durate == [25, 30, 10, 40, 35]
    limite = int(sum(durate) * 2 / 3)
    assert limite == 93

    r = client.post(
        "/itinerary/adapt",
        json={
            "itinerary": it,
            "signal": {**SEGNALE, "meteo": "pioggia", "stanchezza": 0.85},
            "profile": profilo,
        },
    )
    assert r.status_code == 200
    ad: dict[str, Any] = r.json()
    assert [(s["experience_id"], s["esito_adattamento"]) for s in ad["stops"]] == [
        ("exp-interno-san-michele", "sostituita"),
        ("exp-interno-san-frediano", "non_toccata"),
        ("exp-sortita-san-paolino", "sostituita"),
        ("exp-santi-giovanni-reparata", "non_toccata"),
    ]
    assert [(e["experience_id"], e["esito"]) for e in ad["tappe_escluse"]] == [
        ("exp-duomo-volto-santo", "tagliata_stanchezza"),
    ]
    assert ad["adattato_da_segnale"] is True
    # Scelta del prefisso rispetto all'obiettivo: tempo tenuto = somma delle durate
    # correnti (dopo le sostituzioni), come nel motore.
    tenuto = sum(s["durata_min"] for s in ad["stops"])
    assert [s["durata_min"] for s in ad["stops"]] == [20, 30, 20, 40]
    assert tenuto == 110
    assert abs(tenuto - limite) == 17
    # La quinta tappa avrebbe portato il tempo a 145, piu' lontano dal limite.
    assert abs(tenuto - limite) < abs(tenuto + 35 - limite)
    # Senza la quarta il tempo sarebbe 70, piu' lontano di 110.
    assert abs(tenuto - limite) < abs(tenuto - 40 - limite)
