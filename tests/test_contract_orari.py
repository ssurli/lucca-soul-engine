"""Contract test — orari: `rientra_in_orario(durata_min)`, codifica/decodifica
delle fasce per Neo4j, `Signal.istante`, `EsitoAdattamento.TAGLIATA_ORARIO`.

Se un test fallisce, il bug e' nel pacchetto contratti: segnalalo a
`contract-keeper`, non "aggiustare" l'asserzione.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any

import pytest
from contracts import (
    EsitoAdattamento,
    FasciaApertura,
    ItineraryStop,
    Signal,
    TappaEsclusa,
    codifica_fasce,
    decodifica_fasce,
    rientra_in_orario,
)
from pydantic import ValidationError


def _f(g: int, a: tuple[int, int], c: tuple[int, int]) -> FasciaApertura:
    return FasciaApertura(giorno_settimana=g, apertura=time(*a), chiusura=time(*c))


GIORNO = [_f(2, (10, 0), (18, 0))]
DUE_FASCE = [_f(2, (9, 0), (13, 0)), _f(2, (15, 0), (19, 0))]
NOTTE = [_f(2, (20, 0), (23, 59))]

# (fasce, giorno, ora, durata_min, atteso)
CASI_DURATA: list[tuple[list[FasciaApertura], int | None, time, int, bool]] = [
    (GIORNO, 2, time(11, 0), 60, True),  # dentro
    (GIORNO, 2, time(17, 0), 61, False),  # sfora la chiusura di 1 minuto
    (GIORNO, 2, time(17, 0), 60, True),  # finisce esattamente alla chiusura
    (GIORNO, 2, time(9, 30), 60, False),  # inizia prima dell'apertura
    (GIORNO, 2, time(10, 0), 60, True),  # inizia esattamente all'apertura
    (GIORNO, 3, time(11, 0), 30, False),  # altro giorno
    (DUE_FASCE, 2, time(12, 30), 60, False),  # a cavallo della pausa
    (DUE_FASCE, 2, time(12, 0), 60, True),  # prima fascia
    (DUE_FASCE, 2, time(16, 0), 120, True),  # seconda fascia
    (NOTTE, 2, time(23, 30), 60, False),  # oltre le 24:00
    (NOTTE, 2, time(23, 0), 120, False),  # oltre le 24:00
    ([], 2, time(3, 0), 600, True),  # nessun vincolo
    (GIORNO, None, time(3, 0), 600, True),  # giorno sconosciuto
]


@pytest.mark.parametrize(("fasce", "giorno", "ora", "durata", "atteso"), CASI_DURATA)
def test_rientra_in_orario_con_durata(
    fasce: list[FasciaApertura], giorno: int | None, ora: time, durata: int, atteso: bool
) -> None:
    assert rientra_in_orario(fasce, giorno, ora, durata_min=durata) is atteso


@pytest.mark.parametrize("fasce", [GIORNO, [], DUE_FASCE])
def test_rientra_in_orario_durata_negativa_solleva(fasce: list[FasciaApertura]) -> None:
    with pytest.raises(ValueError, match="durata_min"):
        rientra_in_orario(fasce, 2, time(11, 0), durata_min=-1)
    with pytest.raises(ValueError, match="durata_min"):
        rientra_in_orario(fasce, None, time(11, 0), durata_min=-1)


def test_durata_zero_identica_alla_chiamata_senza_parametro_su_griglia() -> None:
    scenari = [
        GIORNO,
        DUE_FASCE,
        [],
        [_f(0, (0, 0), (23, 59))],
        [_f(5, (8, 30), (12, 45)), _f(6, (15, 15), (19, 0))],
    ]
    for fasce in scenari:
        for giorno in [None, *range(7)]:
            for minuti in range(0, 24 * 60, 15):
                ora = time(minuti // 60, minuti % 60)
                assert rientra_in_orario(fasce, giorno, ora, durata_min=0) == rientra_in_orario(
                    fasce, giorno, ora
                )


def test_durata_zero_mantiene_la_semantica_storica_chiusura_esclusa() -> None:
    assert rientra_in_orario(GIORNO, 2, time(10, 0)) is True
    assert rientra_in_orario(GIORNO, 2, time(18, 0), durata_min=0) is False
    assert rientra_in_orario(GIORNO, 2, time(17, 59), durata_min=0) is True


# ---------------------------------------------------------------------------
# orari.py
# ---------------------------------------------------------------------------


def test_codifica_formato_e_andata_e_ritorno() -> None:
    fasce = [_f(0, (10, 0), (18, 0)), _f(6, (9, 5), (13, 30)), _f(0, (8, 0), (9, 0))]
    codificate = codifica_fasce(fasce)
    assert codificate == ["0|10:00|18:00", "6|09:05|13:30", "0|08:00|09:00"]
    assert decodifica_fasce(codificate) == fasce


def test_andata_e_ritorno_piu_fasce_stesso_giorno_ordine_preservato() -> None:
    fasce = [_f(3, (15, 0), (19, 0)), _f(3, (9, 0), (13, 0))]  # ordine NON cronologico
    assert decodifica_fasce(codifica_fasce(fasce)) == fasce
    assert codifica_fasce(decodifica_fasce(["3|15:00|19:00", "3|09:00|13:00"])) == [
        "3|15:00|19:00",
        "3|09:00|13:00",
    ]


def test_lista_vuota_roundtrip() -> None:
    assert codifica_fasce([]) == []
    assert decodifica_fasce([]) == []


MALFORMATE: list[Any] = [
    "7|10:00|18:00",
    "0|9:00|18:00",
    "0|10:00|18:00:00",
    "0 |10:00|18:00",
    "0|24:00|23:00",
    "0|18:00|10:00",
    "0|10:00|10:00",
    "",
    "0|10:00",
    42,
    None,
]


@pytest.mark.parametrize("valore", MALFORMATE, ids=repr)
def test_decodifica_rifiuta_le_stringhe_malformate(valore: Any) -> None:
    with pytest.raises(ValueError):
        decodifica_fasce([valore])


@pytest.mark.parametrize("valore", [v for v in MALFORMATE if isinstance(v, str) and v])
def test_decodifica_il_messaggio_cita_la_stringa(valore: str) -> None:
    with pytest.raises(ValueError) as exc:
        decodifica_fasce([valore])
    assert valore in str(exc.value)


def test_decodifica_fail_closed_una_malformata_invalida_tutta_la_lista() -> None:
    with pytest.raises(ValueError, match="0"):
        decodifica_fasce(["1|10:00|18:00", "0|10:00"])
    with pytest.raises(ValueError, match="garbage"):
        decodifica_fasce(["0|10:00|18:00", "garbage"])


# ---------------------------------------------------------------------------
# Signal.istante
# ---------------------------------------------------------------------------


def _signal(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meteo": "sereno",
        "affollamento": {},
        "stanchezza": 0.2,
        "ora": "09:00:00",
    }
    base.update(extra)
    return base


def test_istante_z_accettato_e_in_utc() -> None:
    s = Signal.model_validate(_signal(istante="2026-12-12T09:00:00Z"))
    assert s.istante == datetime(2026, 12, 12, 9, 0, tzinfo=UTC)
    assert s.istante is not None
    assert s.istante.utcoffset() == timedelta(0)


def test_istante_con_offset_normalizzato_a_utc() -> None:
    s = Signal.model_validate(_signal(istante="2026-12-12T09:00:00+01:00"))
    assert s.istante is not None
    assert s.istante.utcoffset() == timedelta(0)
    assert s.istante == datetime(2026, 12, 12, 8, 0, tzinfo=UTC)
    assert s.istante.hour == 8


def test_istante_datetime_python_con_fuso_normalizzato() -> None:
    s = Signal.model_validate(
        _signal(istante=datetime(2026, 12, 12, 9, 0, tzinfo=timezone(timedelta(hours=-5))))
    )
    assert s.istante is not None
    assert s.istante.hour == 14
    assert s.istante.utcoffset() == timedelta(0)


@pytest.mark.parametrize("valore", ["2026-12-12T09:00:00", datetime(2026, 12, 12, 9, 0)])
def test_istante_naive_rifiutato(valore: Any) -> None:
    with pytest.raises(ValidationError, match="fuso"):
        Signal.model_validate(_signal(istante=valore))


def test_istante_assente_e_none_e_il_resto_invariato() -> None:
    senza = Signal.model_validate(_signal())
    assert senza.istante is None
    con = Signal.model_validate(_signal(istante="2026-12-12T09:00:00Z"))
    assert senza.model_dump(exclude={"istante"}) == con.model_dump(exclude={"istante"})


# ---------------------------------------------------------------------------
# EsitoAdattamento.TAGLIATA_ORARIO
# ---------------------------------------------------------------------------


def test_tagliata_orario_valore_canonico() -> None:
    assert EsitoAdattamento.TAGLIATA_ORARIO.value == "tagliata_orario"


def test_tagliata_orario_valido_in_tappa_esclusa() -> None:
    t = TappaEsclusa(
        experience_id="exp-y", esito=EsitoAdattamento.TAGLIATA_ORARIO, reason="Chiusa all'arrivo."
    )
    assert t.esito is EsitoAdattamento.TAGLIATA_ORARIO
    assert TappaEsclusa.model_validate(t.model_dump(mode="json")) == t


def test_tagliata_orario_rifiutato_su_itinerary_stop() -> None:
    with pytest.raises(ValidationError, match="tappe_escluse"):
        ItineraryStop.model_validate(
            {
                "experience_id": "exp-x",
                "arrivo": "10:00:00",
                "durata_min": 30,
                "reason": "ok",
                "esito_adattamento": "tagliata_orario",
            }
        )
