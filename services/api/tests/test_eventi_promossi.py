"""Test di integrazione — Fase 3 (consumo dei pattern promossi,
`docs/PROMOZIONE_TRACCIA.md` §3): il lato-lettura di `POST /itinerary` per
`experience_engine.engine.compose_itinerary(..., eventi_promossi=...)`.

Colpisce il BFF (`services/api`, `api.main:app`) con `TestClient`, stesso
stile di `test_fluttuante.py`: `pytest.importorskip` per non far esplodere la
raccolta se `api`/`urban_memory` non sono installabili,
`monkeypatch.setattr(api_main, "get_evento_reader", ...)` per sostituire il
lettore degli `:Evento` ricorrenti — chiamato DIRETTAMENTE da
`create_itinerary` (mai tramite `Depends`, stesso motivo di
`get_event_repository`/`get_segnale_repository`: un fallimento deve restare
catturabile dal `try/except` interno).

Copre i criteri del task:

1. Un `:Evento` ATTIVO e pertinente compare in coda nella risposta HTTP
   (`experience_id == evento.id`, SENZA prefisso — a differenza delle tappe
   fluttuanti che portano `fluttuante-<id>`).
2. Un fallimento del lettore Neo4j (client assente/credenziali mancanti, o
   un'eccezione durante `eventi_ricorrenti()`) degrada a
   `eventi_promossi=[]` senza far fallire la richiesta (COMUNQUE 200, mai un
   503/500).
3. Il client non può influenzare `eventi_promossi` tramite il body: il
   contratto (`VisitorContext`, `extra="forbid"`) non espone alcun campo per
   questo, e un `:Evento` NON pertinente ai temi/place letti dal grafo non
   compare comunque, a prescindere da cosa il client manda nel body.
4. Freno di emergenza (`frenato`, docs/STATE_MACHINE.md §4-bis(b)): un
   `:Evento` `attivo` MA `frenato=True` non compare mai, indipendentemente
   dal ciclo `stato` — overlay ortogonale, letto qui in sola lettura.
5. Guard strutturale (AST): il filtro-freno nel consumo di `/itinerary` è
   lettura pura — `api.main`/`api.deps` non importano MAI
   `urban_memory.freno_pattern`/`freno_repository` (i moduli che POSSONO
   scrivere `e.frenato`/`pattern_frenato`). Nessun `SET` è nemmeno
   raggiungibile da questo path: il freno si tira/rilascia SOLO da CLI."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

fastapi_testclient = pytest.importorskip(
    "fastapi.testclient", reason="fastapi non installato: pip install -e services/api"
)
api_main = pytest.importorskip(
    "api.main", reason="`api` non installabile: pip install -e services/api"
)
contracts = pytest.importorskip(
    "contracts", reason="`contracts` non installabile: pip install -e packages/contracts"
)
frizione_pattern = pytest.importorskip(
    "urban_memory.frizione_pattern",
    reason="`urban_memory` non installabile: pip install -e services/urban-memory",
)
graph_source = pytest.importorskip(
    "graph.source", reason="`graph` non installabile: pip install -e services/graph"
)

TestClient = fastapi_testclient.TestClient
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
EventoRicorrente = frizione_pattern.EventoRicorrente
SeedCandidateSource = graph_source.SeedCandidateSource

# "piazza-anfiteatro" è un place_id reale del seed (`services/graph/cypher/
# 01_seed_lucca.cypher`), stesso place_id di riferimento usato da
# `test_fluttuante.py`.
PLACE_ID_SEED = "piazza-anfiteatro"

# Date FISSE (mai date.today()). Ultima occorrenza nel ledger: lunedi' 2 marzo
# 2026, 12:00 UTC (= 13:00 a Roma, stesso giorno). Con cadenza 30 l'occorrenza
# attesa e' mercoledi' 1 aprile 2026 = `DATA_IN_FINESTRA` (coerente anche con
# `giorno_settimana=2`, mercoledi').
ULTIMA_OCCORRENZA_UTC = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
DATA_IN_FINESTRA = "2026-04-01"
ROMA = ZoneInfo("Europe/Rome")


class _FakeCandidateSource:
    """`CandidateSource` finta, stesso pattern di `test_fluttuante.py`:
    propone SEMPRE gli stessi candidati, a prescindere dal `VisitorContext`."""

    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


def _candidato_arte(durata_min: int = 30) -> Any:
    esperienza = ExperienceNode(
        id="exp-evento-promosso-test-fisso",
        titolo="Facciata Barocca",
        place_id=PLACE_ID_SEED,
        temi=["arte"],
        durata_min=durata_min,
        al_chiuso=False,
        accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza,
        place_nome="Piazza Fissa di Test",
        connessioni=['Evoca il tema "Arte".'],
    )


def _visitor_context(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "turista-fase3-eventi-promossi",
        "profile": {
            "curiosita": 0.3,
            "contemplazione": 0.2,
            "arte": 0.9,
            "con_bambini": False,
            "tempo_disponibile_min": 200,
        },
        "signal": {
            "meteo": "sereno",
            "affollamento": {},
            "stanchezza": 0.0,
            "ora": "10:00:00",
            "eventi_attivi": [],
            "data": DATA_IN_FINESTRA,
        },
    }
    base.update(overrides)
    return base


class _FakeEventoReader:
    """Sostituto di `Neo4jFrizioneClient`: espone SOLO `.eventi_ricorrenti()`
    (duck typing — `create_itinerary` non ne verifica il tipo), stesso
    principio dei fake repository di `test_fluttuante.py`."""

    def __init__(self, eventi: list[EventoRicorrente]) -> None:
        self._eventi = eventi

    def eventi_ricorrenti(self) -> list[EventoRicorrente]:
        return self._eventi


class _EventoReaderStorageGiu:
    """Simula un grafo irraggiungibile (Aura in pausa — scenario NORMALE,
    CLAUDE.md): solleva un'eccezione qualunque su `eventi_ricorrenti()`."""

    def eventi_ricorrenti(self) -> list[EventoRicorrente]:
        raise RuntimeError("grafo irraggiungibile (simulato)")


class _FakeTraccia:
    """Sostituto di `TracciaRepository`: SOLO `occorrenze_per_pattern`
    (duck typing). `per_pattern=None` -> stesse occorrenze per ogni pattern;
    una lista vuota simula un ledger senza storia per il pattern."""

    def __init__(self, occorrenze: list[datetime]) -> None:
        self._occorrenze = occorrenze
        self.chiamate: list[tuple[str, list[str]]] = []

    def occorrenze_per_pattern(self, place_id: str, temi: list[str]) -> list[datetime]:
        self.chiamate.append((place_id, list(temi)))
        return list(self._occorrenze)


def _stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    evento_reader: Any,
    candidate_source: Any | None = None,
    occorrenze: list[datetime] | None = None,
    city_tz: Any = ROMA,
) -> _FakeTraccia:
    """Sostituisce `get_evento_reader`, `get_candidate_source` (default:
    `SeedCandidateSource()` reale), `get_traccia_repository` (ledger finto:
    default UNA occorrenza in `ULTIMA_OCCORRENZA_UTC`) e `get_city_tz`
    (default Europe/Rome) - stessa disciplina di `_stub_repos` in
    `test_fluttuante.py`: nessuna rete, nessun .env/CITY_TZ della macchina
    nei test. I test sul fuso letto da ambiente usano `_stub_senza_tz`."""
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: evento_reader)
    source = candidate_source if candidate_source is not None else SeedCandidateSource()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: source)
    traccia = _FakeTraccia([ULTIMA_OCCORRENZA_UTC] if occorrenze is None else occorrenze)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: traccia)
    monkeypatch.setattr(api_main, "get_city_tz", lambda: city_tz)
    return traccia


# ---------------------------------------------------------------------------
# 1. Evento attivo e pertinente -> tappa in coda nell'itinerario
# ---------------------------------------------------------------------------


def test_evento_promosso_attivo_entra_nellitinerario(monkeypatch: pytest.MonkeyPatch) -> None:
    evento = EventoRicorrente(
        evento_id="evento-mercato-antiquario",
        place_id=PLACE_ID_SEED,
        temi=("musica",),  # coerente con un profilo arte>0, stesso tema di test_fluttuante.py
        stato="attivo",
        cadenza_giorni=30.0,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-mercato-antiquario" in ids, (
        f"l'evento promosso attivo non è entrato nell'itinerario: {ids}"
    )


def test_evento_promosso_non_attivo_non_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `:Evento` `sospeso` (letto dal grafo qualunque sia il suo stato,
    poi filtrato in Python) non deve mai comparire — il filtro
    `stato == 'attivo'` è il cuore di questo task."""
    evento = EventoRicorrente(
        evento_id="evento-sospeso-test",
        place_id=PLACE_ID_SEED,
        temi=("musica",),
        stato="sospeso",
        cadenza_giorni=30.0,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-sospeso-test" not in ids


# ---------------------------------------------------------------------------
# 1-bis. Freno di emergenza (`frenato`, docs/STATE_MACHINE.md §4-bis(b)):
#        overlay ORTOGONALE a `stato` sullo stesso :Evento, letto qui in
#        sola lettura (mai scritto dal BFF — si tira/rilascia SOLO da CLI,
#        `python -m urban_memory.freno_pattern`).
# ---------------------------------------------------------------------------


def test_evento_promosso_attivo_e_frenato_non_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `:Evento` `attivo` MA `frenato=True` non deve comparire: il freno
    sopprime la raccomandazione indipendentemente dallo stato del ciclo
    attivo/sospeso/dormiente."""
    evento = EventoRicorrente(
        evento_id="evento-frenato-test",
        place_id=PLACE_ID_SEED,
        temi=("musica",),
        stato="attivo",
        cadenza_giorni=30.0,
        frenato=True,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-frenato-test" not in ids, (
        f"un evento attivo e frenato non deve comparire in itinerario: {ids}"
    )


def test_evento_promosso_attivo_e_non_frenato_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stesso evento del test precedente, ma `frenato=False`: nessuna
    regressione sul comportamento esistente (deve comparire, come prima
    dell'introduzione del freno)."""
    evento = EventoRicorrente(
        evento_id="evento-non-frenato-test",
        place_id=PLACE_ID_SEED,
        temi=("musica",),
        stato="attivo",
        cadenza_giorni=30.0,
        frenato=False,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-non-frenato-test" in ids, (
        f"un evento attivo e non frenato deve comparire in itinerario: {ids}"
    )


def test_evento_sospeso_e_frenato_non_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `:Evento` `sospeso` E `frenato=True`: doppio motivo di esclusione,
    nessuna sorpresa nella combinazione (resta fuori sia per `stato` che per
    `frenato`)."""
    evento = EventoRicorrente(
        evento_id="evento-sospeso-e-frenato-test",
        place_id=PLACE_ID_SEED,
        temi=("musica",),
        stato="sospeso",
        cadenza_giorni=30.0,
        frenato=True,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-sospeso-e-frenato-test" not in ids


# ---------------------------------------------------------------------------
# 2. Grafo/lettore irraggiungibile -> COMUNQUE 200, mai un 503/500
# ---------------------------------------------------------------------------


def test_lettore_irraggiungibile_risponde_200_senza_tappe_evento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, evento_reader=_EventoReaderStorageGiu())
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200, (
        "un fallimento del lettore di eventi promossi NON deve mai far "
        f"fallire /itinerary (mai un 503/500): {resp.status_code} {resp.text}"
    )
    assert isinstance(resp.json()["stops"], list)


def test_evento_reader_assente_risponde_200_senza_tappe_evento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`get_evento_reader()` ritorna `None` (credenziali Neo4j mancanti) —
    stesso scenario NORMALE di `get_place_link_writer() is None`, mai un
    errore."""
    _stub(monkeypatch, evento_reader=None)
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    assert isinstance(resp.json()["stops"], list)


# ---------------------------------------------------------------------------
# 3. Il client non può influenzare eventi_promossi tramite il body
# ---------------------------------------------------------------------------


def test_client_non_puo_iniettare_eventi_promossi_nel_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`VisitorContext` (`extra="forbid"`) non espone alcun campo per
    `eventi_promossi`: un tentativo di iniettarlo nel body viene respinto
    dalla validazione del contratto, PRIMA che l'endpoint esegua — nessun
    canale, di nessun tipo, dal client all'elenco degli eventi promossi."""
    _stub(monkeypatch, evento_reader=_FakeEventoReader([]))
    client = TestClient(api_main.app)

    ctx = _visitor_context()
    ctx["eventi_promossi"] = [
        {"id": "evento-iniettato-dal-client", "place_id": PLACE_ID_SEED, "temi": ["musica"]}
    ]

    resp = client.post("/itinerary", json=ctx)

    assert resp.status_code == 422, (
        "il contratto deve respingere un campo eventi_promossi nel body, "
        f"non esiste un canale client->motore per questo tipo: {resp.status_code}"
    )


def test_evento_non_pertinente_non_entra_a_prescindere_dal_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anche con un body che non tocca in alcun modo `eventi_promossi` (non
    esiste un campo per farlo), un `:Evento` letto dal grafo ma NON
    pertinente al profilo (nessun tema in comune con una dimensione a peso
    > 0) resta fuori dall'itinerario — la pertinenza è decisa SOLO da
    `experience_engine.rules.eventi_promossi_pertinenti`, mai dal client."""
    evento_non_pertinente = EventoRicorrente(
        evento_id="evento-non-pertinente-test",
        place_id=PLACE_ID_SEED,
        temi=("gastronomia",),  # nessun peso nel profilo sotto (tutti zero tranne arte)
        stato="attivo",
        cadenza_giorni=30.0,
    )
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento_non_pertinente]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    client = TestClient(api_main.app)

    resp = client.post("/itinerary", json=_visitor_context())

    assert resp.status_code == 200
    ids = [s["experience_id"] for s in resp.json()["stops"]]
    assert "evento-non-pertinente-test" not in ids


# ---------------------------------------------------------------------------
# 4. Finestra temporale: il BFF fornisce i FATTI (ultima occorrenza dal
#    ledger, in data LOCALE; cadenza), la decisione e' del motore.
# ---------------------------------------------------------------------------


def _evento_attivo(
    evento_id: str = "evento-finestra-test", cadenza: float = 30.0, frenato: bool = False
) -> EventoRicorrente:
    return EventoRicorrente(
        evento_id=evento_id,
        place_id=PLACE_ID_SEED,
        temi=("musica",),
        stato="attivo",
        cadenza_giorni=cadenza,
        frenato=frenato,
    )


def _ids(resp: Any) -> list[str]:
    return [s["experience_id"] for s in resp.json()["stops"]]


def _post(monkeypatch: pytest.MonkeyPatch, evento: EventoRicorrente, ctx: dict, **kw: Any) -> Any:
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([evento]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
        **kw,
    )
    return TestClient(api_main.app).post("/itinerary", json=ctx)


def test_finestra_fuori_finestra_non_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _visitor_context()
    ctx["signal"]["data"] = "2026-04-15"  # 14 giorni dall'attesa, finestra 4,5
    resp = _post(monkeypatch, _evento_attivo(), ctx)
    assert resp.status_code == 200
    assert "evento-finestra-test" not in _ids(resp)


def test_finestra_data_assente_nessun_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _visitor_context()
    del ctx["signal"]["data"]
    resp = _post(monkeypatch, _evento_attivo(), ctx)
    assert resp.status_code == 200
    assert "evento-finestra-test" not in _ids(resp)


def test_g_frenato_in_finestra_non_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    # Controllo anti-vacuita': stesso scenario, non frenato -> compare.
    resp_ok = _post(monkeypatch, _evento_attivo(frenato=False), _visitor_context())
    assert "evento-finestra-test" in _ids(resp_ok)

    traccia = _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([_evento_attivo(frenato=True)]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    resp = TestClient(api_main.app).post("/itinerary", json=_visitor_context())
    assert resp.status_code == 200
    assert "evento-finestra-test" not in _ids(resp)
    assert traccia.chiamate == [], "un evento frenato non deve nemmeno interrogare il ledger"


@pytest.mark.parametrize("valore", ["", "   ", "Mars/Olympus_Mons", "non-un-fuso"])
def test_h_city_tz_assente_o_invalida_nessun_evento_ma_200(
    monkeypatch: pytest.MonkeyPatch, valore: str
) -> None:
    """Passa dal VERO `api.deps.get_city_tz` (CITY_TZ letta da `Settings`),
    non da uno stub: la cache di `get_settings` va azzerata prima e dopo."""
    from api import deps, settings as api_settings

    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([_evento_attivo()]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    monkeypatch.setattr(api_main, "get_city_tz", deps.get_city_tz)  # ripristina il reale
    monkeypatch.setenv("CITY_TZ", valore)
    api_settings.get_settings.cache_clear()
    try:
        resp = TestClient(api_main.app).post("/itinerary", json=_visitor_context())
        assert resp.status_code == 200
        assert "evento-finestra-test" not in _ids(resp)
        assert deps.get_city_tz() is None

        # Controllo anti-vacuita': con un fuso valido lo stesso scenario fa comparire l'evento.
        monkeypatch.setenv("CITY_TZ", "Europe/Rome")
        api_settings.get_settings.cache_clear()
        resp_ok = TestClient(api_main.app).post("/itinerary", json=_visitor_context())
        assert "evento-finestra-test" in _ids(resp_ok)
    finally:
        api_settings.get_settings.cache_clear()


def test_h_ledger_senza_occorrenze_per_il_pattern_evento_saltato(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resp = _post(monkeypatch, _evento_attivo(), _visitor_context(), occorrenze=[])
    assert resp.status_code == 200
    assert "evento-finestra-test" not in _ids(resp)


def test_h_conversione_fuso_la_data_locale_non_utc_arriva_al_motore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Occorrenza 2026-03-02 23:30 UTC = 2026-03-03 00:30 a Roma (CET, +1).
    Settimanale: attesa locale 10 marzo (UTC: 9 marzo). Visita 11 marzo:
    dista 1 giorno dalla data LOCALE (dentro, finestra 1,05) ma 2 da quella
    UTC (fuori). Compare solo se il BFF passa al motore la data locale."""
    catturati: list[Any] = []
    originale = api_main.compose_itinerary

    def _spia(*args: Any, **kwargs: Any) -> Any:
        catturati.extend(kwargs.get("eventi_promossi") or [])
        return originale(*args, **kwargs)

    monkeypatch.setattr(api_main, "compose_itinerary", _spia)
    ctx = _visitor_context()
    ctx["signal"]["data"] = "2026-03-11"  # mercoledi'
    resp = _post(
        monkeypatch,
        _evento_attivo(cadenza=7.0),
        ctx,
        occorrenze=[datetime(2026, 3, 2, 23, 30, tzinfo=UTC)],
    )

    assert resp.status_code == 200
    assert len(catturati) == 1
    assert catturati[0].ultima_occorrenza.isoformat() == "2026-03-03"  # locale, non 03-02
    assert catturati[0].cadenza_giorni == 7.0
    assert "evento-finestra-test" in _ids(resp)


def test_h_usa_l_occorrenza_piu_recente_del_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    catturati: list[Any] = []
    originale = api_main.compose_itinerary

    def _spia(*args: Any, **kwargs: Any) -> Any:
        catturati.extend(kwargs.get("eventi_promossi") or [])
        return originale(*args, **kwargs)

    monkeypatch.setattr(api_main, "compose_itinerary", _spia)
    _post(
        monkeypatch,
        _evento_attivo(),
        _visitor_context(),
        occorrenze=[
            datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
            ULTIMA_OCCORRENZA_UTC,
            datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        ],
    )
    assert [e.ultima_occorrenza.isoformat() for e in catturati] == ["2026-03-02"]


@pytest.mark.parametrize("non_finita", [float("inf"), float("nan")])
def test_h_cadenza_non_finita_salta_solo_quell_evento(
    monkeypatch: pytest.MonkeyPatch, non_finita: float
) -> None:
    """Un evento con cadenza inf/nan viene saltato DA SOLO: l'altro, in
    finestra, compare ancora e la risposta e' 200 (non si svuota la lista)."""
    buono = _evento_attivo("evento-buono", cadenza=30.0)
    rotto = _evento_attivo("evento-cadenza-rotta", cadenza=non_finita)
    _stub(
        monkeypatch,
        evento_reader=_FakeEventoReader([rotto, buono]),
        candidate_source=_FakeCandidateSource([_candidato_arte()]),
    )
    resp = TestClient(api_main.app).post("/itinerary", json=_visitor_context())
    assert resp.status_code == 200
    ids = _ids(resp)
    assert "evento-buono" in ids
    assert "evento-cadenza-rotta" not in ids


def test_i_data_incoerente_con_giorno_settimana_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, evento_reader=_FakeEventoReader([]))
    ctx = _visitor_context()
    ctx["signal"]["data"] = "2026-04-01"  # mercoledi' = 2
    ctx["signal"]["giorno_settimana"] = 0
    resp = TestClient(api_main.app).post("/itinerary", json=ctx)
    assert resp.status_code == 422

    # Controllo: coerente (2) -> 200.
    ctx["signal"]["giorno_settimana"] = 2
    assert TestClient(api_main.app).post("/itinerary", json=ctx).status_code == 200


# ---------------------------------------------------------------------------
# 5. Guard strutturale (AST) — il filtro-freno nel consumo è lettura pura:
#    nessun modulo di questo BFF importa `urban_memory.freno_pattern`/
#    `freno_repository` (gli UNICI moduli che possono scrivere `e.frenato`/
#    `pattern_frenato`), quindi nessun `SET` è nemmeno raggiungibile dal path
#    `/itinerary` — stesso principio del guard già in uso in
#    `services/urban-memory/tests/test_purezza_experience_engine.py` e
#    `test_freno_non_accoppia_traccia.py`, applicato qui al confine BFF.
# ---------------------------------------------------------------------------

_API_PACKAGE_DIR = Path(__file__).resolve().parents[1] / "api"
_MODULI_FRENO_SCRITTURA = ("freno_pattern", "freno_repository")


def _moduli_importati(albero: ast.AST) -> set[str]:
    nomi: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            nomi.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nomi.add(nodo.module.split(".")[-1])
    return nomi


def test_api_package_dir_esiste() -> None:
    assert _API_PACKAGE_DIR.is_dir(), (
        f"atteso {_API_PACKAGE_DIR} — layout del repo cambiato?"
    )


def test_api_non_importa_mai_i_moduli_di_scrittura_del_freno() -> None:
    """`api/main.py`/`api/deps.py` (e qualunque altro modulo del BFF) non
    importano MAI `freno_pattern`/`freno_repository`: solo `frizione_pattern`
    (via `Neo4jFrizioneClient.eventi_ricorrenti`, un lettore) è raggiungibile
    da `create_itinerary` — il freno resta un percorso CLI ristretto/fidato,
    mai invocabile da `/itinerary` o da qualunque altro endpoint di questo
    BFF (docs/STATE_MACHINE.md §4-bis(b))."""
    moduli_python = list(_API_PACKAGE_DIR.rglob("*.py"))
    assert moduli_python, "nessun modulo .py trovato: il guard non starebbe verificando nulla"

    for path in moduli_python:
        albero = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        importati = _moduli_importati(albero)
        for nome_freno in _MODULI_FRENO_SCRITTURA:
            assert nome_freno not in importati, (
                f"{path} importa {nome_freno!r}: il BFF non deve MAI poter "
                "scrivere il freno — /itinerary legge SOLO `e.frenato` "
                "(tramite `EventoRicorrente`), non lo tira/rilascia mai."
            )
