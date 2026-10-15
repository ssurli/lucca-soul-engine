"""Il recommender eredita il vocabolario dei temi: non ne ha uno proprio.

`costruisci_score_fn` inoltra `vocabolario` a `calcola_score` (e alla quota
strutturale). Vocabolari INVENTATI nel test; stesso candidato, profilo e
segnale: cambia solo il vocabolario e il punteggio cambia.
"""

from __future__ import annotations

from datetime import time

import pytest
from contracts import EmotionalProfile, ExperienceNode, GraphCandidate, Signal, VocabolarioTemi
from experience_engine import rules
from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn
from recommender.ranking import _quota_strutturale_per_place

_VOC_A = VocabolarioTemi(
    contemplativi=frozenset({"tema-x"}), arte=frozenset({"tema-y"}),
    insoliti=frozenset(), verde=frozenset(), bambini="piccoli-inventati",
)
_VOC_B = VocabolarioTemi(
    contemplativi=frozenset({"tema-y"}), arte=frozenset({"tema-x"}),
    insoliti=frozenset(), verde=frozenset(), bambini="piccoli-inventati",
)


def _cand(id_: str, place: str, temi: list[str]) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Esperienza {id_}", place_id=place, temi=temi,
            durata_min=40, al_chiuso=True, accessibile=True,
        ),
        place_nome=f"Luogo {place}",
        connessioni=[],
    )


_PROFILO = EmotionalProfile(
    curiosita=0.0, contemplazione=1.0, arte=0.0, con_bambini=False, tempo_disponibile_min=120,
)
_SEGNALE = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))


def test_cold_start_punteggio_segue_il_vocabolario() -> None:
    cand = _cand("exp-x", "luogo-1", ["tema-x", "tema-x"])
    repo = InMemoryBehaviorEventRepository()
    fn_a = costruisci_score_fn(repo, [cand], vocabolario=_VOC_A)
    fn_b = costruisci_score_fn(repo, [cand], vocabolario=_VOC_B)

    s_a = fn_a(cand, _PROFILO, _SEGNALE)
    s_b = fn_b(cand, _PROFILO, _SEGNALE)

    assert s_a == rules.calcola_score(cand, _PROFILO, _SEGNALE, vocabolario=_VOC_A)
    assert s_b == rules.calcola_score(cand, _PROFILO, _SEGNALE, vocabolario=_VOC_B)
    assert s_a == pytest.approx(rules.W_CONTEMPLAZIONE)
    assert s_b == 0.0
    assert s_a != s_b


def test_quota_strutturale_segue_il_vocabolario() -> None:
    """Termine strutturale attivo (soglia 0): le quote per luogo dipendono dal
    vocabolario, quindi anche il punteggio finale (stessa base, quote diverse)."""
    x = _cand("exp-x", "luogo-1", ["tema-x", "tema-x"])
    y = _cand("exp-y", "luogo-2", ["tema-y", "tema-y"])
    candidati = [x, y]

    q_a = _quota_strutturale_per_place(candidati, vocabolario=_VOC_A)
    q_b = _quota_strutturale_per_place(candidati, vocabolario=_VOC_B)
    assert q_a != q_b

    repo = InMemoryBehaviorEventRepository()
    fn_a = costruisci_score_fn(repo, candidati, vocabolario=_VOC_A, soglia_minima_eventi=0)
    fn_b = costruisci_score_fn(repo, candidati, vocabolario=_VOC_B, soglia_minima_eventi=0)
    assert fn_a(x, _PROFILO, _SEGNALE) != fn_b(x, _PROFILO, _SEGNALE)
