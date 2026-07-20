"""Test di integrazione END-TO-END — Wave 4 (Urban Intelligence Index):
non re-identificabilità AL CONFINE DELL'API.

Richiesta esplicita del committente (non ancora coperta da
`services/api/tests/test_dashboard.py`, che usa popolazioni sintetiche
generiche sopra/sotto soglia): il test deve usare uno scenario COSTRUITO PER
FALLIRE — un evento raro, isolato, appartenente a UNA SOLA persona, in un
luogo minore, in un giorno e un'ora precisi (il caso più identificabile
possibile: "quella persona è stata in quel luogo minore in quel preciso
momento") — non uno storico abbondante che passerebbe senza verificare nulla.

La verifica passa SEMPRE da `fastapi.testclient.TestClient` su `api.main.app`
(mai `celle_flusso`/`indice_per_dashboard` chiamate direttamente in Python,
stessa tecnica di `services/api/tests/test_dashboard.py`): dev'essere un test
che fallirebbe anche per un bug puramente HTTP/di serializzazione (es. un
`response_model` che dimenticasse di escludere un campo), non solo per un bug
nella funzione Python sottostante — è per questo che vive qui, in `tests/`,
come test di integrazione multi-servizio (graph/candidati -> intelligence-index
-> api), invece che in `services/api/tests/` o `services/intelligence-index/tests/`.

Scenario avversariale (`_forza_fonti`, sotto):
- `PLACE_MAJOR` — controllo positivo: molte persone (28), deve restare
  visibile a OGNI livello di filtro.
- `PLACE_MINOR` — un SOLO evento da una SOLA persona (`_PERSON_SOLITARIO`),
  nel giorno/ora precisi `GIORNO_EVENTO_RARO`/`ORA_EVENTO_RARO` (un martedì
  alle 15:00 di luglio 2026): deve restare soppresso a OGNI livello.
- `PLACE_BOUNDARY` — il confine k=10 stesso: 9 persone (soppresso) vs. 10
  (visibile), non un arrotondamento approssimativo (né 5 né 15).

Ogni funzione qui sotto è un criterio richiesto esplicitamente dal
committente. Se un test qui fallisce, il bug è nel servizio a valle
(`intelligence_index.dashboard`/`services/api/api/main.py`/i contratti), non
nel test: non "aggiustare" l'asserzione per farla passare, segnala il bug al
subagent competente (vedi CLAUDE.md)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

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
intelligence_index = pytest.importorskip(
    "intelligence_index",
    reason="`intelligence_index` non installabile: pip install -e services/intelligence-index",
)
intelligence_index_soglia = pytest.importorskip(
    "intelligence_index.soglia",
    reason="`intelligence_index` non installabile: pip install -e services/intelligence-index",
)

TestClient = fastapi_testclient.TestClient
BehaviorEvent = contracts.BehaviorEvent
ExperienceNode = contracts.ExperienceNode
GraphCandidate = contracts.GraphCandidate
SOGLIA_MINIMA_PERSONE = intelligence_index_soglia.SOGLIA_MINIMA_PERSONE
assert SOGLIA_MINIMA_PERSONE == 10, (
    "questo file codifica k=10 esplicitamente nei suoi scenari (9 vs 10 "
    "persone): se la soglia cambia, gli scenari sotto vanno rivisti a mano, "
    "non silenziosamente disallineati da questa costante"
)

PERIODO = "2026-07"

#: Il momento più identificabile possibile: un martedì alle 15:00 di luglio
#: 2026 (verificato: `date(2026, 7, 14).isoweekday() == 2`, martedì).
GIORNO_EVENTO_RARO = date(2026, 7, 14)
ORA_EVENTO_RARO = 15
#: Un'altra ora dello STESSO giorno raro (per distinguere il filtro
#: `giorno` dal filtro `giorno`+`ora`, più fine).
ALTRA_ORA_STESSO_GIORNO = 16
#: Un altro giorno del periodo, distinto da quello raro (per distinguere
#: l'aggregato di periodo dal filtro `giorno`).
ALTRO_GIORNO = GIORNO_EVENTO_RARO + timedelta(days=5)

PLACE_MAJOR = "piazza-maggiore-priv-w4"  # controllo positivo: sempre visibile
PLACE_MINOR = "vicolo-minore-priv-w4"  # evento raro: sempre soppresso
PLACE_BOUNDARY = "cortile-boundary-priv-w4"  # confine esatto k=10

EXP_MAJOR = "exp-priv-w4-major"
EXP_MINOR = "exp-priv-w4-minor"
EXP_BOUNDARY = "exp-priv-w4-boundary"

#: Unica persona coinvolta nell'evento raro — il caso più identificabile:
#: "quella persona è stata in quel luogo minore in quel preciso momento".
_PERSON_SOLITARIO = "visitatore-solitario-w4"


# ---------------------------------------------------------------------------
# Doppi in-process delle fonti (stesso pattern di
# `services/api/tests/test_dashboard.py`) — MAI una connessione reale a
# Neo4j/Postgres.
# ---------------------------------------------------------------------------


def _esperienza(id: str, place_id: str) -> Any:
    return ExperienceNode(
        id=id,
        titolo=f"esperienza {id}",
        place_id=place_id,
        temi=["prova"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
    )


def _candidato(id: str, place_id: str, place_nome: str) -> Any:
    return GraphCandidate(
        experience=_esperienza(id, place_id),
        place_nome=place_nome,
        connessioni=[],
    )


class _FakeCandidateSource:
    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    def candidates(self, ctx: Any) -> list[Any]:
        return self._candidates


class _FakeMetricsSource:
    """Doppio di `graph.metrics.GraphMetricsSource` (`Protocol`)."""

    def __init__(self, grado_semantico: dict[str, int]) -> None:
        self._grado_semantico = grado_semantico

    def grado_semantico(self) -> dict[str, int]:
        return self._grado_semantico

    def non_connected_place_pairs(self, at: datetime) -> tuple[set[frozenset[str]], int]:
        return set(), 0


class _FakeEventSource:
    """Doppio di `intelligence_index.repository.BehaviorEventSource`."""

    def __init__(self, eventi: list[Any]) -> None:
        self._eventi = eventi

    def events_in_period(self, inizio: datetime, fine: datetime) -> list[Any]:
        return [evento for evento in self._eventi if inizio <= evento.ts < fine]


class _FakeMemoryRepository:
    """Doppio di `urban_memory.MemoryRepository` (`Protocol`), solo lettura.
    Non serve al contenuto di NESSUNO scenario qui sotto (né `/dashboard/flows`
    né gli indicatori di `/dashboard/index` esercitati in questo file dipendono
    dalla Urban Memory) — presente solo perché `dashboard_index` la chiama
    sempre (`repo.list_pending() + repo.list_curated()`), mai `None`."""

    def list_pending(self) -> list[Any]:
        return []

    def list_curated(self) -> list[Any]:
        return []


_CANDIDATI = [
    _candidato(EXP_MAJOR, PLACE_MAJOR, "Piazza Maggiore (controllo positivo)"),
    _candidato(EXP_MINOR, PLACE_MINOR, "Vicolo Minore (evento raro)"),
    _candidato(EXP_BOUNDARY, PLACE_BOUNDARY, "Cortile Boundary (confine k=10)"),
]
_GRADO_SEMANTICO = {PLACE_MAJOR: 10, PLACE_MINOR: 2, PLACE_BOUNDARY: 5}


def _forza_fonti(monkeypatch: pytest.MonkeyPatch, *, eventi: list[Any]) -> None:
    monkeypatch.setattr(
        api_main, "get_candidate_source", lambda: _FakeCandidateSource(_CANDIDATI)
    )
    monkeypatch.setattr(
        api_main, "get_metrics_source", lambda: _FakeMetricsSource(_GRADO_SEMANTICO)
    )
    monkeypatch.setattr(api_main, "get_event_source", lambda: _FakeEventSource(eventi))
    monkeypatch.setattr(api_main, "get_memory_repository", lambda: _FakeMemoryRepository())


def _stop(person_id: str, experience_id: str, giorno: date, ora: int) -> Any:
    return BehaviorEvent(
        person_id=person_id,
        tipo="stop",
        experience_id=experience_id,
        ts=datetime(giorno.year, giorno.month, giorno.day, ora, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Scenario 1: evento raro isolato (PLACE_MINOR, 1 persona) vs. controllo
# positivo (PLACE_MAJOR, molte persone) — soppressione verificata a OGNI
# livello di filtro che `GET /dashboard/flows` espone.
# ---------------------------------------------------------------------------


def _eventi_scenario_evento_raro() -> list[Any]:
    eventi: list[Any] = []

    # PLACE_MAJOR: 28 persone distinte in totale, distribuite in modo che i
    # tre livelli di filtro diano conteggi DIVERSI (28 / 23 / 20) — dimostra
    # che il filtro `giorno`/`ora` sta davvero restringendo, non che i tre
    # livelli coincidono per costruzione:
    #   - 20 persone esattamente nel giorno/ora dell'evento raro
    #     (il livello più fine, quello dove l'evento raro è isolato al
    #     massimo);
    #   - 3 persone in più nello STESSO giorno raro ma un'altra ora
    #     (contano nel filtro per giorno, non in quello per giorno+ora);
    #   - 5 persone in più in un altro giorno del periodo (contano solo
    #     nell'aggregato di periodo, senza filtro).
    for i in range(20):
        eventi.append(
            _stop(f"turista-major-{i}", EXP_MAJOR, GIORNO_EVENTO_RARO, ORA_EVENTO_RARO)
        )
    for i in range(3):
        eventi.append(
            _stop(
                f"turista-major-altraora-{i}",
                EXP_MAJOR,
                GIORNO_EVENTO_RARO,
                ALTRA_ORA_STESSO_GIORNO,
            )
        )
    for i in range(5):
        eventi.append(
            _stop(f"turista-major-altrogiorno-{i}", EXP_MAJOR, ALTRO_GIORNO, ORA_EVENTO_RARO)
        )

    # PLACE_MINOR: l'evento raro — UNA sola persona, UN solo evento, nel
    # giorno/ora più identificabili possibile.
    eventi.append(
        _stop(_PERSON_SOLITARIO, EXP_MINOR, GIORNO_EVENTO_RARO, ORA_EVENTO_RARO)
    )

    return eventi


#: (params richiesta, conteggio atteso di PLACE_MAJOR) per i 3 livelli di
#: filtro che `GET /dashboard/flows` espone: nessun filtro, `giorno`,
#: `giorno`+`ora`.
_LIVELLI_DI_FILTRO_ATTESI: list[tuple[dict[str, Any], int]] = [
    ({"periodo": PERIODO}, 28),
    ({"periodo": PERIODO, "giorno": GIORNO_EVENTO_RARO.isoformat()}, 23),
    (
        {
            "periodo": PERIODO,
            "giorno": GIORNO_EVENTO_RARO.isoformat(),
            "ora": ORA_EVENTO_RARO,
        },
        20,
    ),
]


@pytest.mark.parametrize(
    "params, conteggio_atteso_major",
    _LIVELLI_DI_FILTRO_ATTESI,
    ids=["nessun_filtro", "filtro_giorno", "filtro_giorno_e_ora"],
)
def test_evento_raro_soppresso_e_controllo_positivo_visibile_a_ogni_livello(
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, Any],
    conteggio_atteso_major: int,
) -> None:
    _forza_fonti(monkeypatch, eventi=_eventi_scenario_evento_raro())
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/flows", params=params)

    assert resp.status_code == 200
    body = resp.json()
    celle_per_place = {cella["place_id"]: cella for cella in body["celle"]}

    # L'evento raro (1 sola persona, il caso più identificabile) resta
    # soppresso a QUESTO livello di filtro.
    cella_minor = celle_per_place[PLACE_MINOR]
    assert cella_minor["disponibile"] is False, (
        f"[{params}] PLACE_MINOR (1 persona, evento raro) risulta "
        f"disponibile — violazione del gate k=10: {cella_minor!r}"
    )
    assert cella_minor["conteggio_tappe"] is None, (
        f"[{params}] PLACE_MINOR soppresso ma `conteggio_tappe` non è None: "
        f"{cella_minor!r} — un numero qualunque qui sarebbe già la "
        "re-identificazione che il gate deve prevenire"
    )

    # Il controllo positivo resta visibile, con il conteggio corretto per
    # QUESTO livello di filtro — la soppressione è mirata (colpisce solo chi
    # deve), non l'endpoint che sopprime tutto per prudenza.
    cella_major = celle_per_place[PLACE_MAJOR]
    assert cella_major["disponibile"] is True, (
        f"[{params}] PLACE_MAJOR (controllo positivo, sopra soglia) risulta "
        f"soppresso: {cella_major!r}"
    )
    assert cella_major["conteggio_tappe"] == conteggio_atteso_major, (
        f"[{params}] PLACE_MAJOR: atteso conteggio_tappe="
        f"{conteggio_atteso_major!r}, ottenuto {cella_major['conteggio_tappe']!r}"
    )


def test_json_grezzo_celle_soppresse_non_contiene_conteggio_di_popolazione(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica ESPLICITA sulla risposta HTTP grezza (non solo sui campi
    tipizzati di Pydantic): nessuna cella, soppressa o meno, espone una
    chiave non dichiarata nel contratto (`FlowCell` ha `extra="forbid"`, ma
    questo test non si fida dello schema — prova direttamente sulla
    risposta HTTP reale, come richiesto esplicitamente dal committente)."""
    _forza_fonti(monkeypatch, eventi=_eventi_scenario_evento_raro())
    client = TestClient(api_main.app)

    resp = client.get(
        "/dashboard/flows",
        params={
            "periodo": PERIODO,
            "giorno": GIORNO_EVENTO_RARO.isoformat(),
            "ora": ORA_EVENTO_RARO,
        },
    )

    assert resp.status_code == 200
    body = resp.json()

    campi_attesi = {"place_id", "disponibile", "conteggio_tappe"}
    for cella in body["celle"]:
        assert set(cella.keys()) == campi_attesi, (
            f"la cella {cella!r} espone campi non nel contratto `FlowCell` "
            f"({campi_attesi!r}): possibile fuga di un conteggio di "
            "popolazione non dichiarato"
        )

    # Difesa ULTERIORE, indipendente dallo schema: cerca sull'intero testo
    # grezzo della risposta HTTP eventuali chiavi/nomi di campo sospetti che
    # potrebbero portare un conteggio di popolazione, anche se non elencati
    # sopra (es. un bug che aggiungesse un campo mai visto in questo test).
    corpo_minuscolo = resp.text.lower()
    for frammento_vietato in ("n_persone", '"persone"', '"count"', "population", "n_people"):
        assert frammento_vietato not in corpo_minuscolo, (
            f"la risposta HTTP contiene {frammento_vietato!r}, un possibile "
            f"conteggio di popolazione non previsto dal contratto: {resp.text}"
        )

    cella_minor = next(c for c in body["celle"] if c["place_id"] == PLACE_MINOR)
    assert cella_minor == {
        "place_id": PLACE_MINOR,
        "disponibile": False,
        "conteggio_tappe": None,
    }, f"cella soppressa con forma inattesa: {cella_minor!r}"


# ---------------------------------------------------------------------------
# Scenario 2: il confine ESATTO k=10 — 9 persone soppresso, 10 persone
# visibile, sullo STESSO luogo/giorno/ora (nessun arrotondamento
# approssimativo: né 5, né 15, esattamente il bordo).
# ---------------------------------------------------------------------------


def _eventi_boundary(n_persone: int) -> list[Any]:
    return [
        _stop(f"cittadino-boundary-{i}", EXP_BOUNDARY, GIORNO_EVENTO_RARO, ORA_EVENTO_RARO)
        for i in range(n_persone)
    ]


@pytest.mark.parametrize(
    "params",
    [p for p, _ in _LIVELLI_DI_FILTRO_ATTESI],
    ids=["nessun_filtro", "filtro_giorno", "filtro_giorno_e_ora"],
)
def test_confine_k10_9_persone_soppresso_10_persone_visibile(
    monkeypatch: pytest.MonkeyPatch, params: dict[str, Any]
) -> None:
    client = TestClient(api_main.app)

    # 9 persone (appena SOTTO la soglia k=10): la cella deve essere soppressa.
    _forza_fonti(monkeypatch, eventi=_eventi_boundary(9))
    resp_9 = client.get("/dashboard/flows", params=params)
    assert resp_9.status_code == 200
    cella_9 = next(
        c for c in resp_9.json()["celle"] if c["place_id"] == PLACE_BOUNDARY
    )
    assert cella_9["disponibile"] is False, (
        f"[{params}] 9 persone distinte (sotto k=10) risultano disponibili: {cella_9!r}"
    )
    assert cella_9["conteggio_tappe"] is None

    # Una decima persona distinta, STESSO luogo/giorno/ora: ora la cella deve
    # diventare visibile, con conteggio esattamente 10 — il confine è k=10,
    # non un arrotondamento approssimativo.
    _forza_fonti(monkeypatch, eventi=_eventi_boundary(10))
    resp_10 = client.get("/dashboard/flows", params=params)
    assert resp_10.status_code == 200
    cella_10 = next(
        c for c in resp_10.json()["celle"] if c["place_id"] == PLACE_BOUNDARY
    )
    assert cella_10["disponibile"] is True, (
        f"[{params}] 10 persone distinte (=k=10) risultano soppresse: {cella_10!r}"
    )
    assert cella_10["conteggio_tappe"] == 10, (
        f"[{params}] atteso conteggio_tappe=10 con esattamente 10 persone "
        f"distinte, ottenuto {cella_10['conteggio_tappe']!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: `GET /dashboard/index` — l'INTERA popolazione del periodo
# sotto k=10 (solo 3 persone attive in tutto il mese), verificato sulla
# risposta HTTP reale (non sulla funzione Python sottostante).
# ---------------------------------------------------------------------------


#: Numero di persone distinte usate dallo scenario sotto — DELIBERATAMENTE
#: piccolo (3, sotto k=10) e DELIBERATAMENTE distinto da qualunque cifra che
#: possa comparire legittimamente nel messaggio generico (es. la soglia
#: "10", o un "1"/"0" annidato in "k=10"): se questa cifra riappare nel
#: `motivo_indisponibilita`, è la popolazione reale sotto soglia che è
#: trapelata, non un rumore innocuo.
N_PERSONE_SCENARIO_INDEX = 3


def test_dashboard_index_popolazione_intera_sotto_soglia_httpreale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eventi_pochissime_persone = [
        _stop(f"cittadino-raro-{i}", EXP_MAJOR, GIORNO_EVENTO_RARO, ORA_EVENTO_RARO)
        for i in range(N_PERSONE_SCENARIO_INDEX)
    ]
    _forza_fonti(monkeypatch, eventi=eventi_pochissime_persone)
    client = TestClient(api_main.app)

    resp = client.get("/dashboard/index", params={"periodo": PERIODO})

    assert resp.status_code == 200
    body = resp.json()
    assert body["disponibile"] is False, (
        f"solo {N_PERSONE_SCENARIO_INDEX} persone attive nell'intero periodo, "
        f"atteso disponibile=False: {body!r}"
    )
    assert body["index"] is None, f"disponibile=False ma `index` non è None: {body!r}"
    assert body["motivo_indisponibilita"], (
        f"disponibile=False richiede un `motivo_indisponibilita` leggibile: {body!r}"
    )
    motivo = body["motivo_indisponibilita"].lower()
    assert "privacy" in motivo or "k=10" in motivo or "10" in motivo, (
        f"motivo_indisponibilita non sembra riferirsi al gate di privacy k=10: {body!r}"
    )

    # Difesa ulteriore sul JSON grezzo: nessun conteggio di popolazione (es.
    # "3 persone") deve trapelare fuori dal messaggio leggibile atteso.
    corpo_minuscolo = resp.text.lower()
    for frammento_vietato in ('"n_persone"', '"persone"', '"count"'):
        assert frammento_vietato not in corpo_minuscolo, (
            f"la risposta HTTP contiene {frammento_vietato!r}: {resp.text}"
        )

    # Verifica ESPLICITA e MIRATA del bug di re-identificazione trovato dal
    # committente: `DatiInsufficientiError.__str__()` include il conteggio
    # ESATTO di persone sotto soglia (es. "3 persone distinte coinvolte") —
    # utile nei log interni, ma se quel testo raggiungesse COSÌ COM'È
    # `motivo_indisponibilita`, la cifra reale della popolazione (qui: 3)
    # sarebbe leggibile nella risposta HTTP pubblica. Il controllo sopra
    # (assenza delle CHIAVI JSON `"n_persone"`/`"persone"`/`"count"`) non lo
    # avrebbe MAI intercettato: il numero non vive in una chiave, vive
    # annidato dentro una frase libera ("... 3 persone distinte
    # coinvolte..."). Cerchiamo quindi la cifra VERA come TOKEN isolato
    # (confini di parola), per non generare falsi positivi contro altri
    # numeri legittimi nel messaggio (es. la soglia pubblica "k=10", che
    # contiene "1" e "0" ma non "3" come token isolato).
    cifra_reale_popolazione = str(N_PERSONE_SCENARIO_INDEX)
    assert not re.search(rf"\b{cifra_reale_popolazione}\b", body["motivo_indisponibilita"]), (
        f"`motivo_indisponibilita` contiene la cifra reale della popolazione "
        f"sotto soglia ({cifra_reale_popolazione!r}) come token isolato — "
        "re-identificazione: BUG bloccante di privacy (stessa classe di "
        "violazione del gate k=10 già bloccata su `contributi_memoria`, qui "
        "sul canale 'spiegazione leggibile' invece che sul canale 'valore'): "
        f"{body!r}"
    )
    # E, indipendentemente dai confini di token: la frase caratteristica del
    # messaggio "grezzo" di `DatiInsufficientiError` non deve MAI comparire
    # nella risposta pubblica — se ricompare, `indice_per_dashboard` è
    # tornato a passare `str(eccezione)` così com'è.
    assert "persone distinte coinvolte" not in motivo, (
        f"`motivo_indisponibilita` riusa il messaggio grezzo di "
        f"`DatiInsufficientiError` (che include `n_persone`), invece di "
        f"costruire un messaggio pubblico generico: {body!r}"
    )
