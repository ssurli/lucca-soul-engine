"""Taglio per stanchezza con TETTO sull'itinerario ricevuto (correzione C).

Regola di `_taglia_per_stanchezza(itinerary, correnti)`:
- `limite` = int(2/3 * somma delle durate di `correnti`) (DOPO le sostituzioni),
  accumulo sulle durate di `correnti`; la tappa successiva si tiene se
  `|incluso - limite| < |escluso - limite|` (a parita' si esclude), al primo
  escluso ci si ferma (prefisso). Prima il limite usava `itinerary.stops`: era il
  bug (una sostituzione piu' corta allargava il limite e il taglio teneva PIU'
  tappe di quelle che avrebbe tenuto senza sostituzioni).
- TETTO: `n0` e `t0` sono numero di tappe e minuti di visita che la stessa regola
  terrebbe sull'itinerario RICEVUTO senza sostituzioni (durate di
  `itinerary.stops`). Si tiene il prefisso piu' lungo ammesso dalla regola che
  rispetta anche `numero <= n0` e `minuti <= t0`.
- ECCEZIONE approvata dal committente: resta "almeno una tappa". La prima e'
  sempre tenuta, anche se da sola supera `t0`.
"""

from __future__ import annotations

import random
from datetime import datetime, time

import pytest
from contracts import ExperienceNode, Itinerary, ItineraryStop
from experience_engine.engine import _CandidatoConReason, _taglia_per_stanchezza


def _cand(id_: str, durata: int) -> _CandidatoConReason:
    return _CandidatoConReason(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
            durata_min=durata, al_chiuso=True, accessibile=True,
        ),
        place_nome=f"Piazza {id_}",
        connessioni=[],
        id_originale=id_,
    )


def _itinerario(durate: list[int]) -> Itinerary:
    out: list[ItineraryStop] = []
    minuti = 8 * 60
    for i, durata in enumerate(durate):
        out.append(
            ItineraryStop(
                experience_id=f"r{i}", arrivo=time(minuti // 60, minuti % 60),
                durata_min=durata, reason="Motivo originale.",
            )
        )
        minuti += durata + 10
    return Itinerary(person_id="p", stops=out, generated_at=datetime(2026, 1, 1))


def _correnti(durate: list[int]) -> list[_CandidatoConReason]:
    return [_cand(f"c{i}", d) for i, d in enumerate(durate)]


def _prefisso_regola(durate: list[int], limite: int) -> int:
    """Lunghezza del prefisso della regola "piu' vicino al limite" (senza il
    minimo di una tappa). Riferimento indipendente dal motore."""
    tempo = 0
    n = 0
    for d in durate:
        incluso = tempo + d
        if abs(incluso - limite) >= abs(tempo - limite):
            break
        n += 1
        tempo = incluso
    return n


def _regola_precedente(durate: list[int]) -> int:
    """Regola con limite 2/3 sulle stesse durate, almeno una tappa."""
    return max(1, _prefisso_regola(durate, int(sum(durate) * 2 / 3)))


def _attese(ricevute: list[int], correnti: list[int]) -> int:
    """Numero di tappe che la regola con tetto deve tenere."""
    n0 = _regola_precedente(ricevute)
    t0 = sum(ricevute[:n0])
    k = _prefisso_regola(correnti, int(sum(correnti) * 2 / 3))
    n = 0
    minuti = 0
    for d in correnti[: min(k, n0)]:
        if minuti + d > t0:
            break
        n += 1
        minuti += d
    return max(1, n)


def _tenute(ricevute: list[int], correnti: list[int]) -> list[_CandidatoConReason]:
    return _taglia_per_stanchezza(_itinerario(ricevute), _correnti(correnti))


def _casi_casuali(quanti: int, seed: int) -> list[tuple[list[int], list[int]]]:
    rng = random.Random(seed)
    casi: list[tuple[list[int], list[int]]] = []
    for _ in range(quanti):
        n = rng.randint(1, 6)
        massimo = rng.choice([5, 15, 60, 150])
        ricevute = [rng.randint(1, massimo) for _ in range(n)]
        correnti = list(ricevute)
        for i in range(n):
            if rng.random() < 0.5:  # sostituzione di durata arbitraria
                correnti[i] = rng.randint(1, massimo * 2)
        casi.append((ricevute, correnti))
    return casi


def test_universale_il_tetto_non_si_supera_mai() -> None:
    """Su migliaia di casi: numero tenute <= n0 SEMPRE; minuti tenuti <= t0
    SEMPRE tranne quando resta una sola tappa. Quella e' l'ECCEZIONE approvata
    dal committente: la prima tappa resta sempre, anche se da sola supera t0."""
    casi = _casi_casuali(6000, seed=20261112)
    for ricevute, correnti in casi:
        n0 = _regola_precedente(ricevute)
        t0 = sum(ricevute[:n0])
        tenute = _tenute(ricevute, correnti)
        minuti = sum(c.experience.durata_min for c in tenute)
        contesto = f"ricevute={ricevute} correnti={correnti} n0={n0} t0={t0}"
        assert 1 <= len(tenute) <= n0, contesto
        assert len(tenute) == 1 or minuti <= t0, contesto
        # Prefisso delle correnti, nello stesso ordine.
        assert [c.experience.id for c in tenute] == [f"c{i}" for i in range(len(tenute))]


def test_universale_coincide_con_la_regola_attesa() -> None:
    for ricevute, correnti in _casi_casuali(6000, seed=7):
        attese = _attese(ricevute, correnti)
        assert len(_tenute(ricevute, correnti)) == attese, f"{ricevute} {correnti}"


def test_senza_sostituzioni_identico_alla_regola_precedente() -> None:
    """Correnti con le stesse durate dei ricevuti: il tetto non morde, vale il
    prefisso con limite 2/3 (almeno una tappa)."""
    for ricevute, _ in _casi_casuali(4000, seed=99):
        tenute = _tenute(ricevute, list(ricevute))
        assert len(tenute) == _regola_precedente(ricevute), f"{ricevute}"


def test_caso_demo_terza_sostituita_da_10_tiene_tre_tappe() -> None:
    # Ricevuti 30,30,25,40,20 (145, limite 96): la regola tiene 3 tappe, 85 min.
    # Correnti 30,30,10,40,20 (130, limite 86): 30, 60, 70 e il taglio si
    # ferma a 3. Col limite sui ricevuti (bug) 70 -> 110 era piu' vicino a 96
    # e ne teneva 4.
    tenute = _tenute([30, 30, 25, 40, 20], [30, 30, 10, 40, 20])
    assert len(tenute) == 3


def test_controesempio_prima_tappa_accorciata_tiene_una_tappa() -> None:
    # Ricevuti 100,10,10,10: la regola tiene solo la prima (n0 = 1, t0 = 100).
    # La prima diventa 30: col solo limite 2/3 sulle correnti (60 -> 40) se ne
    # terrebbero 2 (30, 40); col limite sui ricevuti (bug) tutte e 4. Il tetto
    # n0 = 1 le riduce a una.
    assert len(_tenute([100, 10, 10, 10], [30, 10, 10, 10])) == 1


def test_controesempio_prima_tappa_allungata_eccezione_prima_tappa() -> None:
    # La prima diventa 120 > t0 = 100: resta comunque, da sola (eccezione
    # "almeno una tappa" approvata dal committente).
    tenute = _tenute([100, 10, 10, 10], [120, 10, 10, 10])
    assert [c.experience.durata_min for c in tenute] == [120]


@pytest.mark.parametrize("durate", [[1], [60], [30, 30, 30]])
def test_una_tappa_o_nessuna_sostituzione_almeno_una_resta(durate: list[int]) -> None:
    assert len(_tenute(durate, list(durate))) >= 1
