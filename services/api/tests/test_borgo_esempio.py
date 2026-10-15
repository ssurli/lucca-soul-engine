"""Il motore e' replicabile: una citta' SINTETICA ("borgo-esempio") al posto di Lucca.

Il dataset (`fixtures/borgo_esempio.py`) e' inventato per test, mai caricato su
Aura; la fixture lo registra in `sys.modules` come `graph.seed_borgo_esempio`
(nessun file in `services/graph/graph`). Si verifica che, cambiando SOLO il
contenuto locale, motore e BFF producano itinerari validi, con `reason` in
italiano, senza alcun id o nome di Lucca, e con i filtri etici intatti.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from collections.abc import Iterator
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
from api import deps  # noqa: E402
from api import settings as api_settings  # noqa: E402
from api.settings import get_settings  # noqa: E402
from contracts import (  # noqa: E402
    AdaptRequest,
    EmotionalProfile,
    ExperienceNode,
    Itinerary,
    Signal,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.dataset import DatasetCitta  # noqa: E402
from graph.registro import carica_dataset  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from rag.reasons import adapt_reason, compose_reason  # noqa: E402
from recommender import InMemoryBehaviorEventRepository  # noqa: E402
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

SLUG = "borgo-esempio"
_FILE_DATASET = Path(__file__).parent / "fixtures" / "borgo_esempio.py"
_MODULO_REGISTRO = "graph.seed_borgo_esempio"


def _carica_modulo_fixture() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("_fixture_borgo_esempio", _FILE_DATASET)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def borgo(monkeypatch: pytest.MonkeyPatch) -> DatasetCitta:
    """Registra il borgo come `graph.seed_borgo_esempio` per la durata del test."""
    sorgente = _carica_modulo_fixture()
    modulo = types.ModuleType(_MODULO_REGISTRO)
    modulo.__dict__["DATASET"] = sorgente.DATASET
    monkeypatch.setitem(sys.modules, _MODULO_REGISTRO, modulo)
    ds: DatasetCitta = sorgente.DATASET
    return ds


def _id_lucca() -> set[str]:
    lucca = carica_dataset("lucca")
    ids: set[str] = set()
    ids |= {x.id for x in lucca.luoghi}
    ids |= {x.id for x in lucca.artisti}
    ids |= {x.id for x in lucca.botteghe}
    ids |= {x.id for x in lucca.temi}
    ids |= {x.id for x in lucca.partners}
    ids |= {x.id for x in lucca.esperienze}
    return ids


def _nomi_lucca() -> set[str]:
    lucca = carica_dataset("lucca")
    nomi: set[str] = {"Lucca", "lucchese", "Lucchese"}
    nomi |= {x.nome for x in lucca.luoghi}
    nomi |= {x.nome for x in lucca.artisti}
    nomi |= {x.nome for x in lucca.botteghe}
    nomi |= {x.nome for x in lucca.partners}
    return nomi


# --- criterio "reason leggibile in italiano" ------------------------------------

_PAROLE_ITALIANE = re.compile(
    r"\b(è|e|ed|di|del|della|dei|il|la|le|per|che|un|una|con|in|a|da|tema|sostituita|"
    r"offerta|legato|legata|evoca|tappa|cerchi|ami|hai|ti|chi|più|meno)\b",
    re.IGNORECASE,
)
_PAROLE_INGLESI = re.compile(
    r"\b(the|and|with|because|recommended|you|your|is|are|for|this|that|visit)\b",
    re.IGNORECASE,
)


def _assert_reason_italiano(reason: str) -> None:
    assert reason.strip(), "reason vuoto"
    assert _PAROLE_ITALIANE.search(reason), f"reason non sembra italiano: {reason!r}"
    assert not _PAROLE_INGLESI.search(reason), f"reason con parole inglesi: {reason!r}"


# --- profili e segnali ------------------------------------------------------------


def _profilo(**kw: Any) -> EmotionalProfile:
    base: dict[str, Any] = {
        "curiosita": 0.5, "contemplazione": 0.5, "arte": 0.5,
        "con_bambini": False, "tempo_disponibile_min": 180,
    }
    base.update(kw)
    return EmotionalProfile(**base)


PROFILI: dict[str, EmotionalProfile] = {
    "contemplativo": _profilo(contemplazione=0.95, arte=0.3, curiosita=0.2),
    "amante-arte": _profilo(arte=0.95, contemplazione=0.3, curiosita=0.6),
    "con-bambini": _profilo(con_bambini=True, tempo_disponibile_min=150),
    "poco-tempo": _profilo(curiosita=0.9, tempo_disponibile_min=60),
    "accessibile": _profilo(accessibilita_richiesta=True),
    "tanto-tempo": _profilo(curiosita=0.9, arte=0.8, tempo_disponibile_min=100000),
}


def _segnale(**kw: Any) -> Signal:
    base: dict[str, Any] = {
        "meteo": "sereno", "affollamento": {}, "stanchezza": 0.1, "ora": time(10, 0),
    }
    base.update(kw)
    return Signal(**base)


def _ctx(nome: str, profilo: EmotionalProfile, segnale: Signal | None = None) -> VisitorContext:
    return VisitorContext(
        person_id=f"borgo-{nome}", profile=profilo, signal=segnale or _segnale()
    )


def _controlla_itinerario(
    it: Itinerary, ds: DatasetCitta, budget_min: int | None = None
) -> None:
    per_id = {e.id: e for e in ds.esperienze}
    assert it.stops, "itinerario vuoto"
    for stop in it.stops:
        assert stop.experience_id in per_id, f"tappa fuori dal borgo: {stop.experience_id}"
        _assert_reason_italiano(stop.reason)
    if budget_min is not None:
        totale = sum(s.durata_min for s in it.stops)
        assert totale <= budget_min, f"budget superato: {totale} > {budget_min}"


def _senza_lucca(it: Itinerary) -> None:
    """Nessun id di Lucca tra le tappe (confronto ESATTO: gli id di Tema di
    Lucca sono parole brevi, un confronto per sottostringa darebbe falsi
    positivi) e nessun nome lucchese nei testi dei `reason`."""
    id_lucca = _id_lucca()
    nomi = _nomi_lucca()
    for stop in it.stops:
        assert stop.experience_id not in id_lucca, f"id di Lucca: {stop.experience_id}"
        for nome in nomi:
            assert nome not in stop.reason, f"nome di Lucca {nome!r} in: {stop.reason!r}"


# ---------------------------------------------------------------------------
# Il dataset e il registro
# ---------------------------------------------------------------------------


def test_registro_trova_il_borgo_e_nessun_id_collide_con_lucca(borgo: DatasetCitta) -> None:
    assert carica_dataset(SLUG) is borgo
    ids_borgo = (
        {x.id for x in borgo.luoghi} | {x.id for x in borgo.artisti}
        | {x.id for x in borgo.botteghe} | {x.id for x in borgo.temi}
        | {x.id for x in borgo.partners} | {x.id for x in borgo.esperienze}
    )
    assert all(i.startswith("be-") for i in ids_borgo)
    assert not (ids_borgo & _id_lucca())
    assert not ({x.nome for x in borgo.luoghi} & _nomi_lucca())


def test_il_borgo_non_resta_registrato_dopo_il_test() -> None:
    assert _MODULO_REGISTRO not in sys.modules
    with pytest.raises(ValueError, match="borgo_esempio"):
        carica_dataset(SLUG)


def test_dimensioni_e_vocabolario_del_borgo(borgo: DatasetCitta) -> None:
    assert 6 <= len(borgo.luoghi) <= 8 and len(borgo.artisti) == 2
    assert 8 <= len(borgo.temi) <= 10 and 10 <= len(borgo.esperienze) <= 12
    v = borgo.vocabolario
    assert v.contemplativi and v.arte and v.insoliti and v.verde and v.bambini
    cands = SeedCandidateSource(borgo).candidates(_ctx("x", _profilo()))
    stato = {c.experience.id: c.experience.partner_abbonamento_attivo for c in cands}
    assert stato["be-exp-lab-ceramica"] is True
    assert stato["be-exp-stampa-sospesa"] is False


# ---------------------------------------------------------------------------
# a) motore diretto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(PROFILI))
def test_motore_compone_itinerari_validi(borgo: DatasetCitta, nome: str) -> None:
    profilo = PROFILI[nome]
    ctx = _ctx(nome, profilo)
    cands = SeedCandidateSource(borgo).candidates(ctx)
    it = compose_itinerary(ctx, cands, reason_fn=compose_reason, vocabolario=borgo.vocabolario)
    _controlla_itinerario(it, borgo, profilo.tempo_disponibile_min)
    _senza_lucca(it)


def test_motore_due_profili_diversi_itinerari_diversi(borgo: DatasetCitta) -> None:
    def tappe(nome: str) -> list[str]:
        ctx = _ctx(nome, PROFILI[nome])
        it = compose_itinerary(
            ctx,
            SeedCandidateSource(borgo).candidates(ctx),
            reason_fn=compose_reason,
            vocabolario=borgo.vocabolario,
        )
        return [s.experience_id for s in it.stops]

    assert tappe("contemplativo") != tappe("con-bambini")


@pytest.mark.parametrize(
    "segnale",
    [
        _segnale(meteo="pioggia"),
        _segnale(affollamento={"be-museo-sassi": 0.95, "be-giardino-nebbie": 0.95}),
        _segnale(stanchezza=0.95),
    ],
    ids=["pioggia", "affollamento", "stanchezza"],
)
@pytest.mark.parametrize("nome", ["contemplativo", "amante-arte", "tanto-tempo"])
def test_motore_adatta_su_segnale(borgo: DatasetCitta, nome: str, segnale: Signal) -> None:
    ctx = _ctx(nome, PROFILI[nome])
    cands = SeedCandidateSource(borgo).candidates(ctx)
    base = compose_itinerary(ctx, cands, reason_fn=compose_reason, vocabolario=borgo.vocabolario)
    adattato = adapt_itinerary(
        base, segnale, cands, profile=None,
        reason_fn=compose_reason, adapt_reason_fn=adapt_reason,
        vocabolario=borgo.vocabolario,
    )
    _controlla_itinerario(adattato, borgo, PROFILI[nome].tempo_disponibile_min)
    _senza_lucca(adattato)
    if segnale.meteo == "pioggia":
        per_id = {e.id: e for e in borgo.esperienze}
        ids_base = [x.experience_id for x in base.stops]
        ids_nuovi = [x.experience_id for x in adattato.stops]

        def alternative_ammissibili(tappa: str, gia_usate: list[str]) -> set[str]:
            """Alternative al chiuso per `tappa`, calcolate dal DATASET (non da
            `passa_filtri_duri`, che sarebbe un oracolo tautologico): al chiuso,
            non gia' nell'itinerario, partner (se c'e') con abbonamento attivo,
            e accessibili se la tappa sostituita lo e' (adapt senza profilo:
            l'accessibilita' non si degrada). Orari di apertura e affollamento
            NON entrano: verificato che nel borgo nessuna esperienza dichiara
            `orari_apertura` e il segnale di pioggia non ha affollamento ne'
            `giorno_settimana` (asserito sotto)."""
            sostituita = per_id[tappa]
            return {
                e.id
                for e in borgo.esperienze
                if e.al_chiuso
                and e.id not in gia_usate
                and not (e.partner_id is not None and not _partner_attivo(borgo, e))
                and (e.accessibile or not sostituita.accessibile)
            }

        assert all(not e.orari_apertura for e in borgo.esperienze)
        assert not segnale.affollamento and segnale.giorno_settimana is None
        aperte_base = [i for i in ids_base if not per_id[i].al_chiuso]
        if not aperte_base:
            # Niente all'aperto da riscrivere: itinerario invariato.
            assert adattato.adattato_da_segnale is False
            assert ids_nuovi == ids_base
        else:
            if any(alternative_ammissibili(i, ids_base) for i in aperte_base):
                assert adattato.adattato_da_segnale is True
            # All'aperto resta solo se NON c'e' alcuna alternativa ammissibile libera.
            for i in ids_nuovi:
                if not per_id[i].al_chiuso:
                    assert not alternative_ammissibili(i, ids_nuovi), (
                        f"{i} resta all'aperto pur con alternative ammissibili"
                    )
        assert "be-exp-stampa-sospesa" not in ids_nuovi
        if nome == "tanto-tempo":
            # Caso esplicito: l'unica alternativa al chiuso libera e' di un partner
            # sospeso, quindi l'itinerario resta invariato (valori attesi cablati).
            assert ids_nuovi == ids_base
            assert adattato.adattato_da_segnale is False
            assert "be-exp-stampa-sospesa" not in ids_nuovi


def _partner_attivo(borgo: DatasetCitta, e: ExperienceNode) -> bool:
    """Stato dell'abbonamento letto dal DATASET (Partner via relazione bottega)."""
    bottega = e.partner_id
    partner_ids = {r.partner_id for r in borgo.ha_abbonamento if r.bottega_id == bottega}
    return any(p.abbonamento_attivo for p in borgo.partners if p.id in partner_ids)


# ---------------------------------------------------------------------------
# c) filtri etici sul borgo (motore)
# ---------------------------------------------------------------------------


def _tutti_gli_itinerari(borgo: DatasetCitta) -> Iterator[Itinerary]:
    sorgente = SeedCandidateSource(borgo)
    segnali = [
        _segnale(), _segnale(meteo="pioggia"),
        _segnale(affollamento={"be-museo-sassi": 0.95}), _segnale(stanchezza=0.95),
    ]
    for nome, profilo in PROFILI.items():
        for segnale in segnali:
            ctx = _ctx(nome, profilo, segnale)
            cands = sorgente.candidates(ctx)
            it = compose_itinerary(
                ctx, cands, reason_fn=compose_reason, vocabolario=borgo.vocabolario
            )
            yield it
            yield adapt_itinerary(
                it, segnale, cands, profile=None,
                reason_fn=compose_reason, adapt_reason_fn=adapt_reason,
                vocabolario=borgo.vocabolario,
            )


def test_accessibilita_richiesta_solo_esperienze_accessibili(borgo: DatasetCitta) -> None:
    accessibili = {e.id for e in borgo.esperienze if e.accessibile}
    profilo = PROFILI["accessibile"]
    sorgente = SeedCandidateSource(borgo)
    for segnale in (_segnale(), _segnale(meteo="pioggia"), _segnale(stanchezza=0.95)):
        ctx = _ctx("accessibile", profilo, segnale)
        cands = sorgente.candidates(ctx)
        it = compose_itinerary(
            ctx, cands, reason_fn=compose_reason, vocabolario=borgo.vocabolario
        )
        assert it.stops
        assert {s.experience_id for s in it.stops} <= accessibili


def test_partner_non_attivo_mai_presente_in_composizione(borgo: DatasetCitta) -> None:
    sorgente = SeedCandidateSource(borgo)
    visti: set[str] = set()
    for nome, profilo in PROFILI.items():
        for segnale in (
            _segnale(), _segnale(meteo="pioggia"), _segnale(affollamento={"be-museo-sassi": 0.95}),
        ):
            ctx = _ctx(nome, profilo, segnale)
            it = compose_itinerary(
                ctx, sorgente.candidates(ctx), reason_fn=compose_reason,
                vocabolario=borgo.vocabolario,
            )
            visti |= {s.experience_id for s in it.stops}
    assert "be-exp-stampa-sospesa" not in visti
    # Non e' un test vuoto: il partner ATTIVO compare, quindi il filtro discrimina.
    assert "be-exp-lab-ceramica" in visti


def test_partner_non_attivo_mai_presente_anche_in_adattamento(borgo: DatasetCitta) -> None:
    visti: set[str] = set()
    for it in _tutti_gli_itinerari(borgo):
        visti |= {s.experience_id for s in it.stops}
    assert "be-exp-stampa-sospesa" not in visti


# ---------------------------------------------------------------------------
# b) BFF con CITY_SEED=borgo-esempio
# ---------------------------------------------------------------------------


def _pulisci_cache() -> None:
    get_settings.cache_clear()
    deps.get_dataset.cache_clear()
    deps.get_candidate_source.cache_clear()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, borgo: DatasetCitta
) -> Iterator[TestClient]:
    """BFF reale sul borgo: `.env` del repo neutralizzato (ENV_FILE inesistente, nessuna
    credenziale), selezione del dataset VERA (`CITY_SEED` -> `get_dataset`),
    repository in-memory, orologio fisso."""
    monkeypatch.setattr(api_settings, "ENV_FILE", tmp_path / ".env")  # inesistente
    for var in (
        "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE", "DATABASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CITY_SEED", SLUG)
    _pulisci_cache()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(
        api_main, "get_adesso", lambda: datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
    )
    yield TestClient(api_main.app)
    _pulisci_cache()


def test_bff_usa_il_dataset_del_borgo(client: TestClient, borgo: DatasetCitta) -> None:
    assert deps.get_dataset() is borgo
    fonte = deps.get_candidate_source()
    assert isinstance(fonte, SeedCandidateSource)
    assert fonte._esperienze == borgo.esperienze


@pytest.mark.parametrize("nome", sorted(PROFILI))
def test_bff_itinerary_sul_borgo(client: TestClient, borgo: DatasetCitta, nome: str) -> None:
    profilo = PROFILI[nome]
    resp = client.post("/itinerary", json=_ctx(nome, profilo).model_dump(mode="json"))
    assert resp.status_code == 200, resp.text
    it = Itinerary.model_validate(resp.json())
    _controlla_itinerario(it, borgo, profilo.tempo_disponibile_min)
    _senza_lucca(it)


@pytest.mark.parametrize(
    "segnale",
    [
        _segnale(meteo="pioggia"),
        _segnale(affollamento={"be-museo-sassi": 0.95, "be-giardino-nebbie": 0.95}),
        _segnale(stanchezza=0.95),
    ],
    ids=["pioggia", "affollamento", "stanchezza"],
)
@pytest.mark.parametrize("nome", ["contemplativo", "amante-arte", "tanto-tempo"])
def test_bff_adapt_sul_borgo(
    client: TestClient, borgo: DatasetCitta, nome: str, segnale: Signal
) -> None:
    base = client.post("/itinerary", json=_ctx(nome, PROFILI[nome]).model_dump(mode="json"))
    assert base.status_code == 200, base.text
    richiesta = AdaptRequest(itinerary=Itinerary.model_validate(base.json()), signal=segnale)
    resp = client.post("/itinerary/adapt", json=richiesta.model_dump(mode="json"))
    assert resp.status_code == 200, resp.text
    it = Itinerary.model_validate(resp.json())
    _controlla_itinerario(it, borgo, PROFILI[nome].tempo_disponibile_min)
    _senza_lucca(it)


def test_bff_filtri_etici_sul_borgo(client: TestClient, borgo: DatasetCitta) -> None:
    accessibili = {e.id for e in borgo.esperienze if e.accessibile}
    visti: set[str] = set()
    for nome, profilo in PROFILI.items():
        for segnale in (_segnale(), _segnale(meteo="pioggia"), _segnale(stanchezza=0.95)):
            resp = client.post(
                "/itinerary", json=_ctx(nome, profilo, segnale).model_dump(mode="json")
            )
            assert resp.status_code == 200, resp.text
            ids = {s["experience_id"] for s in resp.json()["stops"]}
            visti |= ids
            if profilo.accessibilita_richiesta:
                assert ids <= accessibili, f"{nome}: tappe non accessibili {ids - accessibili}"
    assert "be-exp-stampa-sospesa" not in visti
    assert "be-exp-lab-ceramica" in visti


def test_bff_adapt_non_reintroduce_partner_non_attivo(
    client: TestClient, borgo: DatasetCitta
) -> None:
    ctx = _ctx("tanto-tempo", PROFILI["tanto-tempo"], _segnale(meteo="pioggia"))
    base = client.post("/itinerary", json=ctx.model_dump(mode="json"))
    assert base.status_code == 200, base.text
    richiesta = AdaptRequest(
        itinerary=Itinerary.model_validate(base.json()), signal=_segnale(meteo="pioggia")
    )
    resp = client.post("/itinerary/adapt", json=richiesta.model_dump(mode="json"))
    assert resp.status_code == 200, resp.text
    assert "be-exp-stampa-sospesa" not in {s["experience_id"] for s in resp.json()["stops"]}
