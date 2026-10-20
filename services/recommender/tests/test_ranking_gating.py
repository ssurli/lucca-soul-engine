"""Test del GATING PER ESPOSIZIONE (ondata 1b-2, recommender Cand. 1).

Il termine STORICO di ogni luogo e' moltiplicato per
`min(1, esposizione / (FATTORE_SOGLIA_ESPOSIZIONE / N))`: `esposizione` e' la
quota di apparizione del luogo nei primi `K_ESPOSIZIONE_TOP` (3) per ciascuno
dei 6 `ARCHETIPI_STRUTTURALI` (segnale neutro), `N` il numero di luoghi tra i
candidati. Il termine strutturale, i pesi e il cold start sono invariati.

I test di comportamento calcolano il punteggio atteso con un ORACOLO
indipendente (formula della quota storica con smoothing ricostruita qui dai
conteggi del repository, fattore di gating a mano), cosi' falliscono con il
`ranking.py` precedente (nessun gating) per un'asserzione, non per un import.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from datetime import UTC, datetime, time

import pytest
from contracts import BehaviorEvent, EmotionalProfile, ExperienceNode, GraphCandidate, Signal
from experience_engine import rules
from graph.seed_lucca import VOCABOLARIO
from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn
from recommender import ranking as ranking_mod
from recommender.ranking import (
    ALPHA_LAPLACE,
    PESO_STORICO_DEFAULT,
    PESO_STRUTTURA_DEFAULT,
    _quota_strutturale_per_place,
)

# --- dataset sintetico: 10 luoghi, esposizioni note --------------------------

_TEMI_RICCO = ["silenzio", "panorama", "arte", "puccini", "artigianato", "liuteria", "con-bambini"]

#: place_id -> temi. Con questi 10 luoghi (N = 10, soglia 2/N = 0.2) le
#: esposizioni nei top-3 dei 6 archetipi sono (verificate da
#: `test_esposizioni_del_dataset_sintetico`):
#:   p0 = 1/3 (pieno)   p2 = 2/9 (pieno)   p1 = p3 = 1/6 (parziale, 5/6)
#:   p4 = p5 = 1/18 (parziale, 5/18)       p6..p9 = 0 (nessuna esposizione)
_LUOGHI: dict[str, list[str]] = {
    "p0": _TEMI_RICCO,
    "p1": ["silenzio", "panorama"],
    "p2": ["arte", "puccini"],
    "p3": ["artigianato", "liuteria"],
    "p4": ["con-bambini"],
    "p5": ["silenzio", "arte"],
    "p6": ["mercato"],
    "p7": ["mercato"],
    "p8": ["mercato"],
    "p9": ["mercato"],
}

_FATTORE_ATTESO: dict[str, float] = {
    "p0": 1.0,
    "p2": 1.0,
    "p1": (1 / 6) / 0.2,
    "p3": (1 / 6) / 0.2,
    "p4": (1 / 18) / 0.2,
    "p5": (1 / 18) / 0.2,
    "p6": 0.0,
    "p7": 0.0,
    "p8": 0.0,
    "p9": 0.0,
}


def _candidato(place_id: str, temi: list[str], *, n_connessioni: int = 1) -> GraphCandidate:
    esperienza = ExperienceNode(
        id=f"exp-{place_id}",
        titolo=f"Esperienza {place_id}",
        place_id=place_id,
        temi=temi,
        durata_min=40,
        al_chiuso=True,
        accessibile=True,
    )
    return GraphCandidate(
        experience=esperienza,
        place_nome="Luogo",
        connessioni=['Evoca il tema "Arte".'] * n_connessioni,
    )


def _candidati() -> list[GraphCandidate]:
    return [_candidato(place_id, temi) for place_id, temi in _LUOGHI.items()]


def _profilo() -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=0.6, contemplazione=0.5, arte=0.7, con_bambini=False, tempo_disponibile_min=180
    )


def _segnale() -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))


def _repo_con_storico(stop_per_place: dict[str, int]) -> InMemoryBehaviorEventRepository:
    repo = InMemoryBehaviorEventRepository()
    for place_id, n in stop_per_place.items():
        for i in range(n):
            repo.record(
                BehaviorEvent(
                    person_id=f"p-{place_id}-{i}",
                    tipo="stop",
                    experience_id=f"exp-{place_id}",
                    ts=datetime(2026, 7, 1, tzinfo=UTC),
                )
            )
    return repo


#: Storico oltre soglia (30 stop = 60 punti), su un luogo per ciascuna fascia.
_STORICO = {"p6": 10, "p0": 10, "p3": 10, "p4": 10}


def _penalita_storica_attesa(
    repo: InMemoryBehaviorEventRepository, place_id: str, *, con_gating: bool
) -> float:
    """Oracolo: peso * quota_smussata * fattore, dai conteggi del repository."""
    conteggi = repo.conteggio_per_esperienza()
    n = len(_LUOGHI)
    totale = sum(conteggi.values())
    quota = (conteggi.get(f"exp-{place_id}", 0.0) + ALPHA_LAPLACE) / (totale + ALPHA_LAPLACE * n)
    fattore = _FATTORE_ATTESO[place_id] if con_gating else 1.0
    return PESO_STORICO_DEFAULT * quota * fattore


def _punteggio_atteso(
    repo: InMemoryBehaviorEventRepository,
    candidato: GraphCandidate,
    strutturale: dict[str, float],
) -> float:
    place_id = candidato.experience.place_id
    base = rules.calcola_score(candidato, _profilo(), _segnale(), vocabolario=VOCABOLARIO)
    return (
        base
        - _penalita_storica_attesa(repo, place_id, con_gating=True)
        - PESO_STRUTTURA_DEFAULT * strutturale[place_id]
    )


# --- precondizione: le esposizioni del dataset sono quelle dichiarate --------


def test_esposizioni_del_dataset_sintetico() -> None:
    esposizione = ranking_mod._esposizione_top_k_per_place(_candidati(), vocabolario=VOCABOLARIO)
    n = len(_LUOGHI)
    for place_id, fattore in _FATTORE_ATTESO.items():
        assert min(1.0, esposizione[place_id] / (2.0 / n)) == pytest.approx(fattore)
    assert sum(esposizione.values()) == pytest.approx(1.0)  # 6 archetipi x 3 posti x 1/3 / 6


# --- gating: zero / proporzionale / pieno -------------------------------------


def test_storia_senza_esposizione_non_riceve_penalita_storica() -> None:
    """p6 ha molta storia ma esposizione zero nei top-3 degli archetipi:
    la penalita' storica e' ZERO (resta solo la strutturale, qui 0.0)."""
    candidati = _candidati()
    repo = _repo_con_storico(_STORICO)
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    p6 = next(c for c in candidati if c.experience.place_id == "p6")

    base = rules.calcola_score(p6, _profilo(), _segnale(), vocabolario=VOCABOLARIO)
    strutturale = _quota_strutturale_per_place(candidati, vocabolario=VOCABOLARIO)
    assert strutturale["p6"] == 0.0  # isola il termine storico
    assert score_fn(p6, _profilo(), _segnale()) == pytest.approx(base, abs=1e-12)


def test_esposizione_alla_soglia_riceve_penalita_storica_piena() -> None:
    """p0 (esposizione 1/3 >= 2/N = 0.2): fattore 1, penalita' storica intera."""
    candidati = _candidati()
    repo = _repo_con_storico(_STORICO)
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    p0 = next(c for c in candidati if c.experience.place_id == "p0")
    strutturale = _quota_strutturale_per_place(candidati, vocabolario=VOCABOLARIO)

    base = rules.calcola_score(p0, _profilo(), _segnale(), vocabolario=VOCABOLARIO)
    atteso = (
        base
        - _penalita_storica_attesa(repo, "p0", con_gating=False)
        - PESO_STRUTTURA_DEFAULT * strutturale["p0"]
    )
    assert score_fn(p0, _profilo(), _segnale()) == pytest.approx(atteso, abs=1e-12)


@pytest.mark.parametrize("place_id", ["p3", "p4"])
def test_esposizione_intermedia_penalita_storica_proporzionale(place_id: str) -> None:
    """p3 (fattore 5/6) e p4 (fattore 5/18): penalita' storica = quota * fattore."""
    candidati = _candidati()
    repo = _repo_con_storico(_STORICO)
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    candidato = next(c for c in candidati if c.experience.place_id == place_id)
    strutturale = _quota_strutturale_per_place(candidati, vocabolario=VOCABOLARIO)

    atteso = _punteggio_atteso(repo, candidato, strutturale)
    assert score_fn(candidato, _profilo(), _segnale()) == pytest.approx(atteso, abs=1e-12)
    # E' davvero intermedia: strettamente tra "nessuna" e "piena".
    base = rules.calcola_score(candidato, _profilo(), _segnale(), vocabolario=VOCABOLARIO)
    senza_storica = base - PESO_STRUTTURA_DEFAULT * strutturale[place_id]
    piena = senza_storica - _penalita_storica_attesa(repo, place_id, con_gating=False)
    assert piena < score_fn(candidato, _profilo(), _segnale()) < senza_storica


def test_il_gating_non_aumenta_mai_la_penalita() -> None:
    """Per ogni luogo il punteggio col gating e' >= di quello senza gating
    (oracolo con fattore 1) e <= della sola base meno la strutturale."""
    candidati = _candidati()
    repo = _repo_con_storico(_STORICO)
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    strutturale = _quota_strutturale_per_place(candidati, vocabolario=VOCABOLARIO)
    for candidato in candidati:
        place_id = candidato.experience.place_id
        base = rules.calcola_score(candidato, _profilo(), _segnale(), vocabolario=VOCABOLARIO)
        senza_gating = (
            base
            - _penalita_storica_attesa(repo, place_id, con_gating=False)
            - PESO_STRUTTURA_DEFAULT * strutturale[place_id]
        )
        punteggio = score_fn(candidato, _profilo(), _segnale())
        assert punteggio >= senza_gating - 1e-12
        assert punteggio <= base - PESO_STRUTTURA_DEFAULT * strutturale[place_id] + 1e-12


def test_gating_unita_su_funzione_pura() -> None:
    """`_applica_gating_esposizione`: fattore = min(1, esp / (2/N)), N = len(quota)."""
    quota = dict.fromkeys(("a", "b", "c", "d"), 0.4)  # N = 4, soglia 0.5
    esposizione = {"a": 0.0, "b": 0.25, "c": 0.5, "d": 0.9}
    risultato = ranking_mod._applica_gating_esposizione(quota, esposizione)
    assert risultato["a"] == 0.0
    assert risultato["b"] == pytest.approx(0.2)
    assert risultato["c"] == pytest.approx(0.4)
    assert risultato["d"] == pytest.approx(0.4)  # mai oltre la quota originale


# --- cold start: garanzia, invariata -----------------------------------------


def test_cold_start_resta_bit_identico_a_calcola_score() -> None:
    candidati = _candidati()
    repo = _repo_con_storico({"p0": 5})  # 10 punti < soglia 20
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    for candidato in candidati:
        assert score_fn(candidato, _profilo(), _segnale()) == rules.calcola_score(
            candidato, _profilo(), _segnale(), vocabolario=VOCABOLARIO
        )


# --- guardia AST: nessun campo commerciale nelle funzioni nuove --------------

_VIETATI = (
    "partner_id",
    "partner_abbonamento_attivo",
    "abbonamento",
    "prezzo",
    "prenotabile",
    "prenotazione",
    "booking",
    "commission",
    "commissione",
    "attribuzione",
)


def _codice_senza_docstring(fn: Callable[..., object]) -> str:
    albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    if (
        funzione.body
        and isinstance(funzione.body[0], ast.Expr)
        and isinstance(funzione.body[0].value, ast.Constant)
    ):
        funzione.body = funzione.body[1:]
    return ast.unparse(funzione).lower()


def test_funzioni_di_gating_non_usano_campi_commerciali_ne_attribuzione() -> None:
    funzioni = (
        ranking_mod._esposizione_top_k_per_place,
        ranking_mod._applica_gating_esposizione,
    )
    for funzione in funzioni:
        codice = _codice_senza_docstring(funzione)
        for vietato in _VIETATI:
            assert vietato not in codice, f"'{funzione.__name__}' non deve usare '{vietato}'"


def test_punteggio_invariante_ai_campi_commerciali_con_gating_attivo() -> None:
    """Stesso luogo, con/senza partner, prezzo, prenotabile, attribuzione: stesso
    punteggio, con storico oltre soglia (gating attivo)."""
    candidati = _candidati()
    riferimento = candidati[3]
    commerciale = GraphCandidate(
        experience=riferimento.experience.model_copy(
            update={
                "partner_id": "bottega-1",
                "prezzo_eur": 999.0,
                "prenotabile": True,
                "partner_abbonamento_attivo": True,
            }
        ),
        place_nome=riferimento.place_nome,
        connessioni=riferimento.connessioni,
        attribuzione="Offerta da Bottega Rossi.",
    )
    repo = _repo_con_storico(_STORICO)
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)
    score_fn_comm = costruisci_score_fn(
        repo, [*candidati[:3], commerciale, *candidati[4:]], vocabolario=VOCABOLARIO
    )
    assert score_fn(riferimento, _profilo(), _segnale()) == score_fn_comm(
        commerciale, _profilo(), _segnale()
    )


def test_zero_candidati_con_soglia_zero_non_solleva() -> None:
    """Regressione: con zero candidati e `soglia_minima_eventi=0` il gating
    divideva per `len(quota_storica) == 0` (ZeroDivisionError). Prima del
    gating quel caso non falliva."""
    repo = InMemoryBehaviorEventRepository()
    score_fn = costruisci_score_fn(repo, [], vocabolario=VOCABOLARIO, soglia_minima_eventi=0)
    assert callable(score_fn)
