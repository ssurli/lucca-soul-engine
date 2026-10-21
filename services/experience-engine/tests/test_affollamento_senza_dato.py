"""Nessuna affermazione sull'affollamento senza un dato misurato.

L'app manda sempre `affollamento: {}`: prima di questa correzione
`rules.segnali_rilevanti` leggeva `signal.affollamento.get(place_id, 0.0)` e
una chiave ASSENTE valeva come "zero misurato", quindi ogni tappa diceva
"in questo momento è meno affollato" senza alcun dato. Ora la frase compare
solo se il luogo della tappa è presente nel segnale con un valore basso.

Provato sia col fallback interno del motore (`reason_fn=None`) sia con
`rag.reasons.compose_reason` iniettato, come fa il BFF.
"""

from __future__ import annotations

from datetime import time

import pytest
from contracts import EmotionalProfile, GraphCandidate, Itinerary, Signal, VisitorContext
from experience_engine import compose_itinerary, rules
from experience_engine.engine import ReasonFn
from graph.seed_lucca import VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import compose_reason

PROFILO = EmotionalProfile(
    curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False,
    tempo_disponibile_min=240,
)

#: (id, reason_fn): `None` = fallback interno del motore.
REASON_FNS: list[tuple[str, ReasonFn | None]] = [
    ("fallback", None),
    ("rag", compose_reason),
]


def _segnale(affollamento: dict[str, float]) -> Signal:
    # Sereno e stanchezza bassa: nessun altro segnale precede l'affollamento.
    return Signal(meteo="sereno", affollamento=affollamento, stanchezza=0.1, ora=time(10, 0))


def _ctx(affollamento: dict[str, float]) -> VisitorContext:
    return VisitorContext(person_id="p", profile=PROFILO, signal=_segnale(affollamento))


def _candidati(affollamento: dict[str, float]) -> list[GraphCandidate]:
    return SeedCandidateSource().candidates(_ctx(affollamento))


def _componi(affollamento: dict[str, float], reason_fn: ReasonFn | None) -> Itinerary:
    ctx = _ctx(affollamento)
    return compose_itinerary(ctx, _candidati(affollamento), reason_fn, vocabolario=VOCABOLARIO)


def _parla_di_affollamento(reason: str) -> bool:
    return "affollat" in reason.lower()


@pytest.mark.parametrize(("nome", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
def test_senza_dato_nessuna_tappa_parla_di_affollamento(
    nome: str, reason_fn: ReasonFn | None
) -> None:
    it = _componi({}, reason_fn)
    assert it.stops
    for stop in it.stops:
        assert not _parla_di_affollamento(stop.reason), (nome, stop.experience_id, stop.reason)


@pytest.mark.parametrize(("nome", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
def test_dato_misurato_basso_la_frase_solo_su_quella_tappa(
    nome: str, reason_fn: ReasonFn | None
) -> None:
    base = _componi({}, reason_fn)
    assert base.stops
    luogo_di = {c.experience.id: c.experience.place_id for c in _candidati({})}
    luogo_bersaglio = luogo_di[base.stops[0].experience_id]
    # 0.0 MISURATO (diverso da assente): penalità nulla in `calcola_score`,
    # quindi l'itinerario resta lo stesso e cambia solo il `reason` della
    # tappa misurata (una tappa per luogo: è una sola).
    it = _componi({luogo_bersaglio: 0.0}, reason_fn)
    assert [s.experience_id for s in it.stops] == [s.experience_id for s in base.stops]
    for stop in it.stops:
        if luogo_di[stop.experience_id] == luogo_bersaglio:
            assert _parla_di_affollamento(stop.reason), (nome, stop.reason)
        else:
            assert not _parla_di_affollamento(stop.reason), (nome, stop.experience_id, stop.reason)


@pytest.mark.parametrize(("nome", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
def test_dato_misurato_01_su_ogni_luogo_la_frase_su_ogni_tappa(
    nome: str, reason_fn: ReasonFn | None
) -> None:
    luoghi = {c.experience.place_id for c in _candidati({})}
    it =_componi(dict.fromkeys(luoghi, 0.1), reason_fn)
    assert it.stops
    for stop in it.stops:
        assert _parla_di_affollamento(stop.reason), (nome, stop.experience_id, stop.reason)


def test_segnali_rilevanti_chiave_assente_non_vale_zero() -> None:
    cand = _candidati({})[0]
    pid = cand.experience.place_id
    assert "affollamento" not in rules.segnali_rilevanti(
        cand, _segnale({}), vocabolario=VOCABOLARIO
    )
    assert "affollamento" not in rules.segnali_rilevanti(
        cand, _segnale({"altro-luogo": 0.0}), vocabolario=VOCABOLARIO
    )
    assert "affollamento" in rules.segnali_rilevanti(
        cand, _segnale({pid: 0.1}), vocabolario=VOCABOLARIO
    )
    assert "affollamento" not in rules.segnali_rilevanti(
        cand, _segnale({pid: 0.3}), vocabolario=VOCABOLARIO
    )
