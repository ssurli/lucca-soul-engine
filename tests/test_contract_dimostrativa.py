"""Contratto: `GraphCandidate.partner_dimostrativo` e `ItineraryStop.dimostrativa`.

Default False, andata e ritorno JSON, retrocompatibilita' (JSON senza la chiave).
"""

from __future__ import annotations

import json
from datetime import time

import pytest
from contracts import ExperienceNode, GraphCandidate, ItineraryStop


def _candidato(**extra: object) -> GraphCandidate:
    esperienza = ExperienceNode(
        id="exp-x", titolo="Titolo", place_id="luogo-x", temi=[],
        durata_min=30, al_chiuso=True, accessibile=True,
    )
    return GraphCandidate(experience=esperienza, place_nome="Piazza", connessioni=[], **extra)  # type: ignore[arg-type]


def _tappa(**extra: object) -> ItineraryStop:
    return ItineraryStop(
        experience_id="exp-x", arrivo=time(10, 0), durata_min=30, reason="Motivo.",
        **extra,  # type: ignore[arg-type]
    )


def test_default_false_su_entrambi() -> None:
    assert _candidato().partner_dimostrativo is False
    assert _tappa().dimostrativa is False


@pytest.mark.parametrize("valore", [True, False])
def test_candidato_andata_e_ritorno_json(valore: bool) -> None:
    c = _candidato(partner_dimostrativo=valore)
    dopo = GraphCandidate.model_validate_json(c.model_dump_json())
    assert dopo.partner_dimostrativo is valore
    assert dopo == c


@pytest.mark.parametrize("valore", [True, False])
def test_tappa_andata_e_ritorno_json(valore: bool) -> None:
    t = _tappa(dimostrativa=valore)
    dopo = ItineraryStop.model_validate_json(t.model_dump_json())
    assert dopo.dimostrativa is valore
    assert dopo == t
    assert json.loads(t.model_dump_json())["dimostrativa"] is valore


def test_tappa_json_senza_la_chiave_resta_valida_con_false() -> None:
    dati = json.loads(_tappa(dimostrativa=True).model_dump_json())
    del dati["dimostrativa"]
    assert "dimostrativa" not in dati
    assert ItineraryStop.model_validate_json(json.dumps(dati)).dimostrativa is False


def test_candidato_json_senza_la_chiave_resta_valido_con_false() -> None:
    dati = json.loads(_candidato(partner_dimostrativo=True).model_dump_json())
    del dati["partner_dimostrativo"]
    assert GraphCandidate.model_validate_json(json.dumps(dati)).partner_dimostrativo is False
