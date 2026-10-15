"""Un vocabolario OSTILE non apre alcun canale commerciale.

Il vocabolario contiene esattamente i temi di un'esperienza con partner. Lo
score deve comunque essere IDENTICO a parita' di temi/connessioni, qualunque
sia `partner_id`, `prezzo_eur`, `partner_abbonamento_attivo`, `prenotabile`,
`attribuzione`: il vocabolario pesa solo l'affinita' tematica.
"""

from __future__ import annotations

from datetime import time
from typing import Literal

import pytest
from contracts import EmotionalProfile, ExperienceNode, GraphCandidate, Signal, VocabolarioTemi
from experience_engine import rules

_TEMI = ["tema-partner-a", "tema-partner-b"]

_VOC_OSTILE = VocabolarioTemi(
    contemplativi=frozenset(_TEMI),
    arte=frozenset(_TEMI),
    insoliti=frozenset(_TEMI),
    verde=frozenset(_TEMI),
    bambini="tema-partner-a",
)


def _cand(
    *,
    partner_id: str | None,
    prezzo_eur: float | None,
    abbonamento: bool,
    prenotabile: bool,
    attribuzione: str | None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id="exp-1", titolo="Esperienza", place_id="luogo-1", temi=list(_TEMI),
            durata_min=45, al_chiuso=False, accessibile=True,
            partner_id=partner_id, prezzo_eur=prezzo_eur,
            partner_abbonamento_attivo=abbonamento, prenotabile=prenotabile,
        ),
        place_nome="Luogo",
        connessioni=["una connessione", "un'altra"],
        attribuzione=attribuzione,
    )


_PROFILI = [
    EmotionalProfile(curiosita=1.0, contemplazione=0.0, arte=0.0, con_bambini=False,
                     tempo_disponibile_min=120),
    EmotionalProfile(curiosita=0.0, contemplazione=1.0, arte=1.0, con_bambini=False,
                     tempo_disponibile_min=120),
    EmotionalProfile(curiosita=0.3, contemplazione=0.6, arte=0.9, con_bambini=True,
                     tempo_disponibile_min=60),
    EmotionalProfile(curiosita=0.0, contemplazione=0.0, arte=0.0, con_bambini=True,
                     tempo_disponibile_min=30),
]


@pytest.mark.parametrize("profilo", _PROFILI)
@pytest.mark.parametrize("meteo", ["sereno", "caldo", "pioggia"])
def test_score_identico_con_o_senza_partner(
    profilo: EmotionalProfile, meteo: Literal["sereno", "caldo", "pioggia"]
) -> None:
    signal = Signal(
        meteo=meteo,
        affollamento={}, stanchezza=0.2, ora=time(10, 0),
    )
    base = rules.calcola_score(
        _cand(partner_id=None, prezzo_eur=None, abbonamento=False, prenotabile=False,
              attribuzione=None),
        profilo, signal, vocabolario=_VOC_OSTILE,
    )
    varianti = [
        dict(partner_id="partner-1", prezzo_eur=5.0, abbonamento=True, prenotabile=True,
             attribuzione="Bottega Uno"),
        dict(partner_id="partner-1", prezzo_eur=500.0, abbonamento=True, prenotabile=True,
             attribuzione=None),
        dict(partner_id="partner-2", prezzo_eur=0.0, abbonamento=False, prenotabile=False,
             attribuzione="Bottega Due"),
        dict(partner_id="partner-2", prezzo_eur=99999.0, abbonamento=False, prenotabile=True,
             attribuzione=None),
        dict(partner_id=None, prezzo_eur=1000.0, abbonamento=True, prenotabile=False,
             attribuzione="Solo attribuzione"),
    ]
    for v in varianti:
        # `==` voluto: identico bit a bit, non prossimo.
        assert rules.calcola_score(_cand(**v), profilo, signal, vocabolario=_VOC_OSTILE) == base, v
