"""Contratto: `ItineraryStop.causa_adattamento` (pioggia | affollamento | None).

Ammesso solo con esito SOSTITUITA o MANTENUTA_SENZA_ALTERNATIVA (validatore);
l'inverso non e' richiesto; default None; andata e ritorno JSON.
"""

from __future__ import annotations

import json
from datetime import time

import pytest
from contracts import EsitoAdattamento, ItineraryStop
from pydantic import ValidationError

CON_CAUSA = [
    EsitoAdattamento.SOSTITUITA,
    EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
]
CAUSE = ["pioggia", "affollamento"]


def _tappa(**extra: object) -> ItineraryStop:
    return ItineraryStop(
        experience_id="exp-x", arrivo=time(10, 0), durata_min=30, reason="Motivo.",
        **extra,  # type: ignore[arg-type]
    )


def test_default_none() -> None:
    assert _tappa().causa_adattamento is None
    assert _tappa(esito_adattamento=EsitoAdattamento.SOSTITUITA).causa_adattamento is None


@pytest.mark.parametrize("causa", CAUSE)
@pytest.mark.parametrize("esito", CON_CAUSA)
def test_causa_accettata_con_sostituita_e_mantenuta(
    causa: str, esito: EsitoAdattamento
) -> None:
    assert _tappa(esito_adattamento=esito, causa_adattamento=causa).causa_adattamento == causa


@pytest.mark.parametrize("causa", CAUSE)
def test_causa_rifiutata_con_non_toccata(causa: str) -> None:
    with pytest.raises(ValidationError, match="causa_adattamento"):
        _tappa(esito_adattamento=EsitoAdattamento.NON_TOCCATA, causa_adattamento=causa)


@pytest.mark.parametrize("causa", CAUSE)
def test_causa_rifiutata_con_esito_assente(causa: str) -> None:
    with pytest.raises(ValidationError, match="causa_adattamento"):
        _tappa(causa_adattamento=causa)
    with pytest.raises(ValidationError, match="causa_adattamento"):
        _tappa(esito_adattamento=None, causa_adattamento=causa)


@pytest.mark.parametrize("esito", CON_CAUSA)
def test_esito_senza_causa_resta_valido(esito: EsitoAdattamento) -> None:
    assert _tappa(esito_adattamento=esito).causa_adattamento is None


@pytest.mark.parametrize("valore", ["stanchezza", "Pioggia", "", "caldo"])
def test_valore_fuori_dal_literal_rifiutato(valore: str) -> None:
    with pytest.raises(ValidationError):
        _tappa(esito_adattamento=EsitoAdattamento.SOSTITUITA, causa_adattamento=valore)


@pytest.mark.parametrize("causa", [*CAUSE, None])
def test_andata_e_ritorno_json_conserva_il_campo(causa: str | None) -> None:
    t = _tappa(esito_adattamento=EsitoAdattamento.SOSTITUITA, causa_adattamento=causa)
    testo = t.model_dump_json()
    assert json.loads(testo)["causa_adattamento"] == causa
    dopo = ItineraryStop.model_validate_json(testo)
    assert dopo.causa_adattamento == causa
    assert dopo == t


def test_json_senza_la_chiave_resta_valido_con_none() -> None:
    dati = json.loads(
        _tappa(
            esito_adattamento=EsitoAdattamento.SOSTITUITA, causa_adattamento="pioggia"
        ).model_dump_json()
    )
    del dati["causa_adattamento"]
    assert ItineraryStop.model_validate_json(json.dumps(dati)).causa_adattamento is None


def test_json_con_causa_e_esito_non_toccata_rifiutato() -> None:
    dati = json.loads(_tappa().model_dump_json())
    dati["esito_adattamento"] = "non_toccata"
    dati["causa_adattamento"] = "pioggia"
    with pytest.raises(ValidationError):
        ItineraryStop.model_validate_json(json.dumps(dati))
