"""Il motore usa DAVVERO il vocabolario dei temi che riceve.

Il vocabolario è dato della città (`contracts.VocabolarioTemi`), non del
motore: qui si costruiscono vocabolari INVENTATI nel test (nessun dataset
reale) e si verifica che scoring, segnali rilevanti, coerenza col profilo,
segnali fluttuanti ed eventi promossi seguano quello passato, e nient'altro.
Se il motore leggesse ancora un vocabolario cablato, questi test fallirebbero.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal

import pytest
from contracts import (
    EmotionalProfile,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    SegnaleFluttuante,
    Signal,
    VocabolarioTemi,
)
from experience_engine import rules

#: Vocabolario inventato: ogni gruppo contiene SOLO temi che nessun dataset
#: reale dichiara.
_VOC_INVENTATO = VocabolarioTemi(
    contemplativi=frozenset({"quiete-inventata"}),
    arte=frozenset({"tema-inventato-arte"}),
    insoliti=frozenset({"stranezza-inventata"}),
    verde=frozenset({"fresco-inventato"}),
    bambini="piccoli-inventati",
)

#: Vocabolario con TUTTI i gruppi vuoti e un tema `bambini` che nessuna
#: esperienza del test porta.
_VOC_VUOTO = VocabolarioTemi(
    contemplativi=frozenset(),
    arte=frozenset(),
    insoliti=frozenset(),
    verde=frozenset(),
    bambini="tema-inesistente",
)

#: Temi che un motore con vocabolario cablato avrebbe premiato: con un
#: vocabolario che non li contiene NON devono contare nulla.
_TEMI_STORICI = ["musica", "arte", "silenzio", "verde", "panorama", "con-bambini"]


def _candidato(
    temi: list[str],
    *,
    durata_min: int = 60,
    al_chiuso: bool = False,
    connessioni: list[str] | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id="exp-1", titolo="Esperienza di prova", place_id="luogo-1", temi=temi,
            durata_min=durata_min, al_chiuso=al_chiuso, accessibile=True,
        ),
        place_nome="Luogo di prova",
        connessioni=connessioni or [],
    )


def _profilo(
    *,
    curiosita: float = 0.0,
    contemplazione: float = 0.0,
    arte: float = 0.0,
    con_bambini: bool = False,
) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=curiosita, contemplazione=contemplazione, arte=arte,
        con_bambini=con_bambini, tempo_disponibile_min=180,
    )


def _sereno() -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))


# --- (a) il gruppo "arte" è quello del vocabolario ricevuto ----------------


def test_arte_segue_il_vocabolario_ricevuto() -> None:
    """Col vocabolario inventato, il tema inventato dà affinità arte piena
    (2 occorrenze -> 1.0) e "musica" nessuna: nessun gruppo cablato."""
    profilo = _profilo(arte=1.0)
    inventato = _candidato(["tema-inventato-arte", "tema-inventato-arte"])
    musica = _candidato(["musica"])

    s_inventato = rules.calcola_score(inventato, profilo, _sereno(), vocabolario=_VOC_INVENTATO)
    s_musica = rules.calcola_score(musica, profilo, _sereno(), vocabolario=_VOC_INVENTATO)

    assert s_inventato == pytest.approx(rules.W_ARTE * 1.0 * 1.0)
    assert s_musica == 0.0


def test_affinita_temi_accetta_frozenset() -> None:
    """`affinita_temi` prende i gruppi del vocabolario (frozenset) con lo
    stesso comportamento di sempre (0, 0.5, 1, saturazione a 2); un `set`
    resta accettato."""
    gruppo = _VOC_INVENTATO.arte
    assert isinstance(gruppo, frozenset)
    assert rules.affinita_temi([], gruppo) == 0.0
    assert rules.affinita_temi(["musica"], gruppo) == 0.0
    assert rules.affinita_temi(["tema-inventato-arte"], gruppo) == 0.5
    assert rules.affinita_temi(["tema-inventato-arte"] * 3, gruppo) == 1.0
    assert rules.affinita_temi(["tema-inventato-arte"], {"tema-inventato-arte"}) == 0.5


def test_stessa_esperienza_score_diverso_con_vocabolari_diversi() -> None:
    """Stesso candidato, profilo e segnale: cambia solo il vocabolario e lo
    score cambia. Il vocabolario è un input reale dello scoring."""
    profilo = _profilo(arte=1.0, contemplazione=1.0)
    cand = _candidato(["tema-inventato-arte", "quiete-inventata"])
    con = rules.calcola_score(cand, profilo, _sereno(), vocabolario=_VOC_INVENTATO)
    senza = rules.calcola_score(cand, profilo, _sereno(), vocabolario=_VOC_VUOTO)
    assert con == pytest.approx(rules.W_ARTE * 0.5 + rules.W_CONTEMPLAZIONE * 0.5)
    assert senza == 0.0


# --- (b) vocabolario vuoto: restano solo le componenti non tematiche -------


@pytest.mark.parametrize("meteo", ["sereno", "pioggia", "caldo"])
@pytest.mark.parametrize("al_chiuso", [False, True])
@pytest.mark.parametrize("n_connessioni", [0, 2, 6])
def test_vocabolario_vuoto_score_solo_da_componenti_non_tematiche(
    meteo: Literal["sereno", "pioggia", "caldo"], al_chiuso: bool, n_connessioni: int
) -> None:
    """Gruppi vuoti e `bambini` assente dai temi: lo score dipende SOLO da
    sorpresa-connessioni, meteo/al_chiuso, stanchezza e affollamento. I temi
    dell'esperienza (anche un "verde" col caldo) non contano nulla."""
    profilo = _profilo(curiosita=0.8, contemplazione=1.0, arte=1.0, con_bambini=True)
    signal = Signal(meteo=meteo, affollamento={"luogo-1": 0.1}, stanchezza=0.5, ora=time(10, 0))
    connessioni = [f"connessione {i}" for i in range(n_connessioni)]
    cand = _candidato(_TEMI_STORICI, durata_min=30, al_chiuso=al_chiuso, connessioni=connessioni)

    atteso = rules.W_CURIOSITA * 0.8 * (0.5 * min(n_connessioni, 4) / 4.0)
    if meteo in ("pioggia", "caldo") and al_chiuso:
        atteso += rules.W_METEO
    brevita = 1.0 - min(30, rules.DURATA_LUNGA_MIN) / rules.DURATA_LUNGA_MIN
    atteso += rules.W_STANCHEZZA * 0.5 * brevita
    atteso -= rules.PENALITA_AFFOLLAMENTO * 0.1
    atteso = max(0.0, min(1.0, atteso))

    score = rules.calcola_score(cand, profilo, signal, vocabolario=_VOC_VUOTO)
    assert score == pytest.approx(atteso)

    # Controprova: togliere TUTTI i temi non cambia nulla col vocabolario vuoto.
    senza_temi = _candidato([], durata_min=30, al_chiuso=al_chiuso, connessioni=connessioni)
    assert rules.calcola_score(senza_temi, profilo, signal, vocabolario=_VOC_VUOTO) == (
        pytest.approx(score)
    )


def test_bambini_segue_il_vocabolario() -> None:
    """Il bonus bambini scatta sul tema `bambini` del vocabolario ricevuto,
    non su un tema cablato."""
    profilo = _profilo(con_bambini=True)
    inventato = _candidato(["piccoli-inventati"])
    storico = _candidato(["con-bambini"])
    assert rules.calcola_score(inventato, profilo, _sereno(), vocabolario=_VOC_INVENTATO) == (
        pytest.approx(rules.W_BAMBINI)
    )
    assert rules.calcola_score(storico, profilo, _sereno(), vocabolario=_VOC_INVENTATO) == 0.0


def test_verde_col_caldo_segue_il_vocabolario() -> None:
    """Col caldo, un'esperienza all'aperto prende il bonus meteo e il segnale
    "caldo" solo se un suo tema è nel gruppo `verde` RICEVUTO."""
    caldo = Signal(meteo="caldo", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    profilo = _profilo()
    fresco = _candidato(["fresco-inventato"])
    verde_storico = _candidato(["verde", "panorama"])

    assert rules.calcola_score(fresco, profilo, caldo, vocabolario=_VOC_INVENTATO) == (
        pytest.approx(rules.W_METEO)
    )
    assert rules.calcola_score(verde_storico, profilo, caldo, vocabolario=_VOC_INVENTATO) == 0.0

    assert "caldo" in rules.segnali_rilevanti(fresco, caldo, vocabolario=_VOC_INVENTATO)
    assert "caldo" not in rules.segnali_rilevanti(
        verde_storico, caldo, vocabolario=_VOC_INVENTATO
    )
    assert "caldo" not in rules.segnali_rilevanti(fresco, caldo, vocabolario=_VOC_VUOTO)


# --- (c) coerenza col profilo, segnali fluttuanti, eventi promossi ---------


@pytest.mark.parametrize(
    ("profilo", "tema_coerente"),
    [
        (_profilo(contemplazione=1.0), "quiete-inventata"),
        (_profilo(arte=1.0), "tema-inventato-arte"),
        (_profilo(curiosita=1.0), "stranezza-inventata"),
        (_profilo(con_bambini=True), "piccoli-inventati"),
    ],
)
def test_coerente_col_profilo_segue_il_vocabolario(
    profilo: EmotionalProfile, tema_coerente: str
) -> None:
    """Ogni dimensione del profilo è raggiunta dal tema del gruppo ricevuto;
    i temi "storici" non raggiungono nessuno; col vocabolario vuoto nulla."""
    assert rules._coerente_col_profilo([tema_coerente], profilo, vocabolario=_VOC_INVENTATO)
    assert not rules._coerente_col_profilo(_TEMI_STORICI, profilo, vocabolario=_VOC_INVENTATO)
    assert not rules._coerente_col_profilo([tema_coerente], profilo, vocabolario=_VOC_VUOTO)


def _fluttuante(id_: str, temi: list[str]) -> SegnaleFluttuante:
    return SegnaleFluttuante(
        id=id_, descrizione="qualcosa accade in piazza", temi=temi, place_id="luogo-1",
        non_commerciale=True, valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_segnali_fluttuanti_seguono_il_vocabolario() -> None:
    profilo = _profilo(arte=1.0)
    inventato = _fluttuante("f-inventato", ["tema-inventato-arte"])
    musica = _fluttuante("f-musica", ["musica"])

    pertinenti = rules.segnali_fluttuanti_pertinenti(
        [inventato, musica], profilo, vocabolario=_VOC_INVENTATO
    )
    assert [s.id for s in pertinenti] == ["f-inventato"]

    # Un vocabolario dove "musica" è arte: ora passa il segnale musica.
    voc_musica = VocabolarioTemi(
        contemplativi=frozenset(), arte=frozenset({"musica"}), insoliti=frozenset(),
        verde=frozenset(), bambini="tema-inesistente",
    )
    pertinenti = rules.segnali_fluttuanti_pertinenti(
        [inventato, musica], profilo, vocabolario=voc_musica
    )
    assert [s.id for s in pertinenti] == ["f-musica"]


def test_eventi_promossi_seguono_il_vocabolario() -> None:
    profilo = _profilo(arte=1.0)

    def evento(id_: str, temi: list[str]) -> EventoPromosso:
        # Ultima occorrenza lunedì 2/3/2026, cadenza 7: il 9/3 è in finestra.
        return EventoPromosso(
            id=id_, place_id="luogo-1", temi=temi,
            ultima_occorrenza=date(2026, 3, 2), cadenza_giorni=7.0,
        )

    eventi = [evento("e-inventato", ["tema-inventato-arte"]), evento("e-musica", ["musica"])]
    pertinenti = rules.eventi_promossi_pertinenti(
        eventi, profilo, date(2026, 3, 9), vocabolario=_VOC_INVENTATO
    )
    assert [e.id for e in pertinenti] == ["e-inventato"]
    assert rules.eventi_promossi_pertinenti(
        eventi, profilo, date(2026, 3, 9), vocabolario=_VOC_VUOTO
    ) == []
