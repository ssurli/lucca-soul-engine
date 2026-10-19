"""Sostituzione per pioggia/affollamento: costo e tema (difetto g, 2026-10-19).

Regole di `_migliore_alternativa` / `adapt_itinerary`:
1. vincolo DURO di costo: il sostituto non costa piu' della tappa tolta
   (`prezzo_eur` None = 0);
2. tra gli ammessi: prima chi condivide almeno un tema con la tappa tolta
   (preferenza FORTE, non filtro), poi score, poi id.

Etica: il prezzo puo' solo ESCLUDERE un candidato piu' caro, mai favorirne uno;
il partner non conta (nessuno spazio e' acquistabile).

Score controllato: profilo con solo `arte=1`, vocabolario con arte={"arte","arte2"}:
ogni tema d'arte aggiunge 0.15 (max due); la pioggia aggiunge a TUTTI i candidati al chiuso
lo stesso bonus meteo (non discrimina).
"""

from __future__ import annotations

from datetime import datetime, time

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    Signal,
    VisitorContext,
    VocabolarioTemi,
)
from experience_engine import adapt_itinerary, compose_itinerary
from experience_engine.engine import _migliore_alternativa
from experience_engine.rules import SOGLIA_AFFOLLAMENTO_ADATTAMENTO, calcola_score
from graph.seed_lucca import VOCABOLARIO as VOCABOLARIO_LUCCA
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

VOC = VocabolarioTemi(
    contemplativi=frozenset({"silenzio"}),
    arte=frozenset({"arte", "arte2"}),
    insoliti=frozenset(),
    verde=frozenset({"verde"}),
    bambini="con-bambini",
)
PROFILO = EmotionalProfile(
    curiosita=0.0, contemplazione=0.0, arte=1.0, con_bambini=False,
    tempo_disponibile_min=600,
)
PIOGGIA = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(9, 0))
TEMA_TOLTA = "tema-x"


def _nodo(
    id_: str,
    temi: list[str],
    *,
    prezzo: float | None = None,
    al_chiuso: bool = True,
    partner_id: str | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Tappa {id_}", place_id=f"luogo-{id_}", temi=temi,
            durata_min=30, al_chiuso=al_chiuso, accessibile=True,
            prezzo_eur=prezzo, partner_id=partner_id,
        ),
        place_nome=f"Luogo {id_}",
        connessioni=[],
    )


def _tolta(prezzo: float | None = None) -> GraphCandidate:
    return _nodo("tolta", [TEMA_TOLTA], prezzo=prezzo, al_chiuso=False)


def _scegli(
    candidati: list[GraphCandidate], prezzo_tolta: float | None = None
) -> str | None:
    """Id del sostituto scelto per la tappa tolta (all'aperto, sotto la pioggia)."""
    tolta = _tolta(prezzo_tolta)
    alt = _migliore_alternativa(
        candidates=[tolta, *candidati],
        signal=PIOGGIA,
        profile=PROFILO,
        esclusi={"tolta"},
        richiede_accessibile=False,
        solo_al_chiuso=True,
        max_affollamento=SOGLIA_AFFOLLAMENTO_ADATTAMENTO,
        vocabolario=VOC,
        prezzo_tolta=prezzo_tolta or 0.0,
        temi_tolta=tolta.experience.temi,
    )
    return None if alt is None else alt.experience.id


def _adatta(candidati: list[GraphCandidate], prezzo_tolta: float | None = None) -> Itinerary:
    tolta = _tolta(prezzo_tolta)
    it = Itinerary(
        person_id="p",
        stops=[
            ItineraryStop(
                experience_id="tolta", arrivo=time(9, 0), durata_min=30,
                reason="Motivo originale.",
            )
        ],
        generated_at=datetime(2026, 1, 1),
    )
    return adapt_itinerary(
        it, PIOGGIA, [tolta, *candidati], PROFILO, compose_reason, adapt_reason,
        vocabolario=VOC,
    )


def test_il_punteggio_sintetico_e_quello_atteso() -> None:
    """Guardia dello scenario: lo score e' governato dal solo tema 'arte'."""
    alto = _nodo("a", ["arte", "arte2"])
    medio = _nodo("m", ["arte"])
    zero = _nodo("z", [TEMA_TOLTA])
    s = {
        c.experience.id: calcola_score(c, PROFILO, PIOGGIA, vocabolario=VOC)
        for c in (alto, medio, zero)
    }
    assert s["a"] > s["m"] > s["z"]


# --- 1. vincolo duro di costo ------------------------------------------------


def test_candidato_piu_caro_non_scelto_anche_con_score_piu_alto() -> None:
    caro_forte = _nodo("caro", ["arte", TEMA_TOLTA], prezzo=8.0)  # score alto, tema comune
    gratis_debole = _nodo("gratis", ["altro"])  # score 0
    assert _scegli([caro_forte, gratis_debole], prezzo_tolta=None) == "gratis"


def test_unico_ammissibile_piu_caro_mantenuta_senza_alternativa_con_reason() -> None:
    caro = _nodo("caro", ["arte"], prezzo=8.0)
    assert _scegli([caro], prezzo_tolta=None) is None
    adattato = _adatta([caro], prezzo_tolta=None)
    (stop,) = adattato.stops
    assert stop.experience_id == "tolta"
    assert stop.esito_adattamento == EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert stop.reason.strip()
    assert "pioggia" in stop.reason


@pytest.mark.parametrize(
    ("prezzo_tolta", "prezzo_sostituto", "ammesso"),
    [
        (None, None, True),
        (None, 0.0, True),   # None = 0: un sostituto gratuito e' ammesso
        (None, 5.0, False),  # None = 0: un sostituto a pagamento e' escluso
        (15.0, 8.0, True),   # piu' economico della tolta: ammesso
        (15.0, 15.0, True),  # pari prezzo: ammesso (<=)
        (15.0, 25.0, False),
        (0.0, 0.01, False),
    ],
)
def test_prezzo_none_vale_zero_e_confronto_con_la_tolta(
    prezzo_tolta: float | None, prezzo_sostituto: float | None, ammesso: bool
) -> None:
    cand = _nodo("sost", ["arte"], prezzo=prezzo_sostituto)
    assert (_scegli([cand], prezzo_tolta) == "sost") is ammesso


# --- 2. preferenza di tema (forte, non filtro) -------------------------------


def test_a_parita_di_ammissibilita_vince_chi_condivide_un_tema_anche_con_score_minore() -> None:
    forte_senza_tema = _nodo("a-forte", ["arte", "arte2"])
    debole_con_tema = _nodo("b-debole", [TEMA_TOLTA])
    pa = calcola_score(forte_senza_tema, PROFILO, PIOGGIA, vocabolario=VOC)
    pb = calcola_score(debole_con_tema, PROFILO, PIOGGIA, vocabolario=VOC)
    assert pa > pb
    assert _scegli([forte_senza_tema, debole_con_tema]) == "b-debole"


def test_il_tema_non_e_un_filtro_senza_temi_comuni_vince_lo_score() -> None:
    migliore = _nodo("z-migliore", ["arte", "arte2"])
    peggiore = _nodo("a-peggiore", ["altro"])
    assert _scegli([peggiore, migliore]) == "z-migliore"


def test_il_tema_non_aggira_il_costo() -> None:
    """Il tema e' una preferenza tra gli AMMESSI: non riammette un candidato caro."""
    caro_con_tema = _nodo("caro", [TEMA_TOLTA], prezzo=3.0)
    gratis_senza_tema = _nodo("gratis", ["altro"])
    assert _scegli([caro_con_tema, gratis_senza_tema]) == "gratis"


def test_il_prezzo_non_favorisce_vince_lo_score() -> None:
    """Due ammessi con stesso tema condiviso: decide lo score, non il prezzo.
    L'economico (gratis) ha score inferiore e perde contro il piu' caro-ma-ammesso."""
    economico_debole = _nodo("a-economico", [TEMA_TOLTA], prezzo=None)
    costoso_forte = _nodo("b-costoso", [TEMA_TOLTA, "arte"], prezzo=10.0)
    assert (
        calcola_score(costoso_forte, PROFILO, PIOGGIA, vocabolario=VOC)
        > calcola_score(economico_debole, PROFILO, PIOGGIA, vocabolario=VOC)
    )
    assert _scegli([economico_debole, costoso_forte], prezzo_tolta=15.0) == "b-costoso"
    # E a parita' di score non decide il prezzo ma l'id.
    a = _nodo("a-id", [TEMA_TOLTA], prezzo=10.0)
    b = _nodo("b-id", [TEMA_TOLTA], prezzo=None)
    assert _scegli([b, a], prezzo_tolta=15.0) == "a-id"


# --- partner irrilevante ------------------------------------------------------


@pytest.mark.parametrize("partner_su_a", [True, False])
def test_partner_irrilevante_decide_lo_score(partner_su_a: bool) -> None:
    """Due candidati gratuiti con lo stesso tema: lo score decide e scambiando
    `partner_id` l'esito non cambia."""
    forte = _nodo("forte", [TEMA_TOLTA, "arte"], partner_id="p-1" if partner_su_a else None)
    debole = _nodo("debole", [TEMA_TOLTA], partner_id=None if partner_su_a else "p-1")
    assert _scegli([debole, forte]) == "forte"
    assert _scegli([forte, debole]) == "forte"


# --- property-like sul seed di Lucca -----------------------------------------


def _profili() -> list[EmotionalProfile]:
    base = dict(tempo_disponibile_min=400)
    return [
        EmotionalProfile(curiosita=0.9, contemplazione=0.1, arte=0.2, con_bambini=False, **base),
        EmotionalProfile(curiosita=0.1, contemplazione=0.9, arte=0.1, con_bambini=False, **base),
        EmotionalProfile(curiosita=0.3, contemplazione=0.2, arte=0.9, con_bambini=False, **base),
        EmotionalProfile(curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=True, **base),
        EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
            accessibilita_richiesta=True, **base,
        ),
    ]


def test_seed_lucca_ogni_sostituzione_non_costa_piu_della_tappa_tolta() -> None:
    fonte = SeedCandidateSource()
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(8, 0))
    sostituzioni = 0
    for i, profilo in enumerate(_profili()):
        ctx = VisitorContext(person_id=f"prop-{i}", profile=profilo, signal=sereno)
        candidati = fonte.candidates(ctx)
        prezzi = {c.experience.id: c.experience.prezzo_eur or 0.0 for c in candidati}
        base = compose_itinerary(ctx, candidati, compose_reason, vocabolario=VOCABOLARIO_LUCCA)
        originali = [s.experience_id for s in base.stops]
        luoghi = {c.experience.id: c.experience.place_id for c in candidati}

        segnali = [Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(8, 0))]
        for livello in (0.75, 0.79):  # sopra la soglia di adattamento, sotto la critica
            segnali.append(
                Signal(
                    meteo="sereno", stanchezza=0.0, ora=time(8, 0),
                    affollamento={luoghi[e]: livello for e in originali},
                )
            )
        for segnale in segnali:
            adattato = adapt_itinerary(
                base, segnale, candidati, profilo, compose_reason, adapt_reason,
                vocabolario=VOCABOLARIO_LUCCA,
            )
            assert len(adattato.stops) == len(originali), "nessun taglio atteso"
            for tolta, stop in zip(originali, adattato.stops, strict=True):
                if stop.esito_adattamento != EsitoAdattamento.SOSTITUITA:
                    continue
                sostituzioni += 1
                assert prezzi[stop.experience_id] <= prezzi[tolta], (
                    f"profilo {i}: {tolta} ({prezzi[tolta]} EUR) -> "
                    f"{stop.experience_id} ({prezzi[stop.experience_id]} EUR)"
                )
                assert stop.reason.strip()
    assert sostituzioni > 0, "la proprieta' non e' stata esercitata"
