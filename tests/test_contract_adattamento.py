"""Contract test — wave "adattamento" (2026-10-16): `EsitoAdattamento`,
`ItineraryStop.esito_adattamento`, `TappaEsclusa`, budget dell'`Itinerary`.

Rete di sicurezza contro la divergenza di schema: default retrocompatibili (i
JSON precedenti alla wave restano validi) e validatori. Se un test fallisce,
il bug e' nel pacchetto contratti: segnalalo a `contract-keeper`, non
"aggiustare" l'asserzione.
"""

from __future__ import annotations

from datetime import time
from typing import Any

import pytest
from contracts import EsitoAdattamento, Itinerary, ItineraryStop, TappaEsclusa
from pydantic import ValidationError

ESITI_DI_TAGLIO = [
    EsitoAdattamento.TAGLIATA_STANCHEZZA,
    EsitoAdattamento.TAGLIATA_TETTO_GIORNATA,
    EsitoAdattamento.TAGLIATA_ORARIO,
]
ESITI_DI_TAPPA = [
    EsitoAdattamento.NON_TOCCATA,
    EsitoAdattamento.SOSTITUITA,
    EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA,
]


def _stop(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "experience_id": "exp-x",
        "arrivo": "10:00:00",
        "durata_min": 30,
        "reason": "Perche' e' coerente con il tuo percorso.",
    }
    base.update(extra)
    return base


def _itinerario(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "person_id": "visitor-1",
        "stops": [_stop()],
        "generated_at": "2026-10-16T10:00:00",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Vocabolario dell'enum
# ---------------------------------------------------------------------------


def test_esiti_hanno_i_valori_canonici() -> None:
    assert {e.value for e in EsitoAdattamento} == {
        "non_toccata",
        "sostituita",
        "mantenuta_senza_alternativa",
        "tagliata_stanchezza",
        "tagliata_tetto_giornata",
        "tagliata_orario",
    }


# ---------------------------------------------------------------------------
# Default retrocompatibili: i JSON precedenti alla wave restano validi
# ---------------------------------------------------------------------------


def test_itinerario_senza_i_campi_nuovi_e_valido_con_i_default() -> None:
    it = Itinerary.model_validate(_itinerario())
    assert it.tempo_disponibile_min is None
    assert it.tempo_effettivo_min is None
    assert it.tappe_escluse == []
    assert it.adattato_da_segnale is False
    assert it.stops[0].esito_adattamento is None


def test_tappe_escluse_default_non_e_condiviso_tra_istanze() -> None:
    a = Itinerary.model_validate(_itinerario())
    b = Itinerary.model_validate(_itinerario())
    a.tappe_escluse.append(
        TappaEsclusa(
            experience_id="exp-y",
            esito=EsitoAdattamento.TAGLIATA_STANCHEZZA,
            reason="Tolta per la stanchezza.",
        )
    )
    assert b.tappe_escluse == []


def test_andata_e_ritorno_json_conserva_tutti_i_campi_nuovi() -> None:
    it = Itinerary.model_validate(
        _itinerario(
            stops=[_stop(esito_adattamento="sostituita")],
            tempo_disponibile_min=300,
            tempo_effettivo_min=120,
            tappe_escluse=[
                {
                    "experience_id": "exp-y",
                    "esito": "tagliata_tetto_giornata",
                    "reason": "Non c'e' piu' tempo oggi.",
                }
            ],
            adattato_da_segnale=True,
        )
    )
    dump = it.model_dump(mode="json")
    assert dump["stops"][0]["esito_adattamento"] == "sostituita"
    assert dump["tappe_escluse"][0]["esito"] == "tagliata_tetto_giornata"
    assert Itinerary.model_validate(dump) == it


# ---------------------------------------------------------------------------
# Validatore di Itinerary: budget coerente
# ---------------------------------------------------------------------------


def test_budget_entrambi_valorizzati_e_uguali_e_valido() -> None:
    it = Itinerary.model_validate(_itinerario(tempo_disponibile_min=120, tempo_effettivo_min=120))
    assert it.tempo_effettivo_min == 120


def test_budget_effettivo_minore_del_dichiarato_e_valido() -> None:
    it = Itinerary.model_validate(_itinerario(tempo_disponibile_min=3000, tempo_effettivo_min=840))
    assert (it.tempo_disponibile_min, it.tempo_effettivo_min) == (3000, 840)


def test_budget_effettivo_maggiore_del_dichiarato_rifiutato() -> None:
    with pytest.raises(ValidationError, match="non può superare"):
        Itinerary.model_validate(_itinerario(tempo_disponibile_min=100, tempo_effettivo_min=101))


@pytest.mark.parametrize(
    "campi",
    [{"tempo_disponibile_min": 120}, {"tempo_effettivo_min": 120}],
)
def test_budget_solo_uno_dei_due_rifiutato(campi: dict[str, int]) -> None:
    with pytest.raises(ValidationError, match="entrambi"):
        Itinerary.model_validate(_itinerario(**campi))


@pytest.mark.parametrize("campo", ["tempo_disponibile_min", "tempo_effettivo_min"])
@pytest.mark.parametrize("valore", [0, -1])
def test_budget_deve_essere_strettamente_positivo(campo: str, valore: int) -> None:
    altro = (
        "tempo_effettivo_min" if campo == "tempo_disponibile_min" else "tempo_disponibile_min"
    )
    with pytest.raises(ValidationError):
        Itinerary.model_validate(_itinerario(**{campo: valore, altro: 100}))


# ---------------------------------------------------------------------------
# Validatore di ItineraryStop: nessun esito di taglio su una tappa presente
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("esito", ESITI_DI_TAPPA)
def test_tappa_presente_accetta_gli_esiti_di_tappa(esito: EsitoAdattamento) -> None:
    stop = ItineraryStop.model_validate(_stop(esito_adattamento=esito.value))
    assert stop.esito_adattamento is esito


@pytest.mark.parametrize("esito", ESITI_DI_TAGLIO)
def test_tappa_presente_rifiuta_gli_esiti_di_taglio(esito: EsitoAdattamento) -> None:
    with pytest.raises(ValidationError, match="tappe_escluse"):
        ItineraryStop.model_validate(_stop(esito_adattamento=esito.value))


def test_esito_di_taglio_rifiutato_anche_dentro_un_itinerario() -> None:
    with pytest.raises(ValidationError):
        Itinerary.model_validate(
            _itinerario(stops=[_stop(esito_adattamento="tagliata_stanchezza")])
        )


def test_esito_sconosciuto_rifiutato() -> None:
    with pytest.raises(ValidationError):
        ItineraryStop.model_validate(_stop(esito_adattamento="inventato"))


def test_tappa_costruita_in_python_con_orario_time() -> None:
    stop = ItineraryStop(
        experience_id="exp-x",
        arrivo=time(10, 0),
        durata_min=0,
        reason="ok",
        esito_adattamento=EsitoAdattamento.NON_TOCCATA,
    )
    assert stop.esito_adattamento is EsitoAdattamento.NON_TOCCATA


# ---------------------------------------------------------------------------
# Validatore di TappaEsclusa: solo esiti di taglio, reason obbligatorio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("esito", ESITI_DI_TAGLIO)
def test_tappa_esclusa_accetta_gli_esiti_di_taglio(esito: EsitoAdattamento) -> None:
    t = TappaEsclusa(experience_id="exp-y", esito=esito, reason="Tolta.")
    assert t.esito is esito


@pytest.mark.parametrize("esito", ESITI_DI_TAPPA)
def test_tappa_esclusa_rifiuta_gli_esiti_di_tappa(esito: EsitoAdattamento) -> None:
    with pytest.raises(ValidationError, match="tagliata_stanchezza"):
        TappaEsclusa(experience_id="exp-y", esito=esito, reason="Tolta.")


def test_tappa_esclusa_reason_obbligatorio_e_non_vuoto() -> None:
    with pytest.raises(ValidationError):
        TappaEsclusa.model_validate({"experience_id": "exp-y", "esito": "tagliata_stanchezza"})
    with pytest.raises(ValidationError):
        TappaEsclusa(
            experience_id="exp-y", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA, reason=""
        )


def test_tappa_esclusa_non_ammette_campi_extra() -> None:
    with pytest.raises(ValidationError):
        TappaEsclusa.model_validate(
            {
                "experience_id": "exp-y",
                "esito": "tagliata_stanchezza",
                "reason": "Tolta.",
                "durata_min": 30,
            }
        )


def test_itinerary_e_stop_non_ammettono_campi_extra() -> None:
    with pytest.raises(ValidationError):
        Itinerary.model_validate(_itinerario(esito="sostituita"))
    with pytest.raises(ValidationError):
        ItineraryStop.model_validate(_stop(esito="sostituita"))

