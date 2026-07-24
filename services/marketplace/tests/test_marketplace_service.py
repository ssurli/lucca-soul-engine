"""Test dei vincoli non negoziabili di `marketplace.service`.

Copre i criteri d'accettazione della Wave 3a (CLAUDE.md,
docs/DATA_CONTRACTS.md §5): una `Booking` nasce sempre `RICHIESTA`; il
prezzo è uno snapshot congelato; un'esperienza non prenotabile rifiuta
subito la richiesta; e — il vincolo cardine — `CommissionRecord` non è MAI
calcolabile prima della conferma.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, time

import pytest
from contracts import BookingStatus, CommissionRecord, FasciaApertura
from marketplace import (
    BookingNotFoundError,
    ExperienceNotAvailableError,
    ExperienceNotBookableError,
    InMemoryBookingRepository,
    InvalidBookingStateError,
    confirm_booking,
    request_booking,
)


@pytest.fixture
def repo() -> InMemoryBookingRepository:
    return InMemoryBookingRepository()


# --- request_booking: stato iniziale, snapshot del prezzo -------------------


def test_request_booking_nasce_in_stato_richiesta(repo, booking_request_factory) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=20.0, prenotabile=True
    )
    assert prenotazione.stato == BookingStatus.RICHIESTA


def test_request_booking_congela_il_prezzo_dato(repo, booking_request_factory) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=17.5, prenotabile=True
    )
    assert prenotazione.prezzo_eur == 17.5


def test_request_booking_rifiuta_esperienza_non_prenotabile(repo, booking_request_factory) -> None:
    with pytest.raises(ExperienceNotBookableError):
        request_booking(repo, booking_request_factory(), prezzo_eur=20.0, prenotabile=False)


def test_request_booking_non_prenotabile_non_persiste_nulla(
    repo, booking_request_factory, monkeypatch
) -> None:
    """`repo.create` non viene MAI chiamato quando `prenotabile=False`: il
    rifiuto avviene prima di qualunque scrittura."""
    chiamato = []
    monkeypatch.setattr(repo, "create", lambda booking: chiamato.append(booking) or booking)

    with pytest.raises(ExperienceNotBookableError):
        request_booking(repo, booking_request_factory(), prezzo_eur=20.0, prenotabile=False)

    assert chiamato == []


def test_request_booking_id_deterministico_con_id_generator(repo, booking_request_factory) -> None:
    prenotazione = request_booking(
        repo,
        booking_request_factory(),
        prezzo_eur=20.0,
        prenotabile=True,
        id_generator=lambda: "booking-fisso-1",
    )
    assert prenotazione.id == "booking-fisso-1"


def test_request_booking_id_generator_di_default_produce_id_diversi(
    repo, booking_request_factory
) -> None:
    a = request_booking(repo, booking_request_factory(), prezzo_eur=10.0, prenotabile=True)
    b = request_booking(repo, booking_request_factory(), prezzo_eur=10.0, prenotabile=True)
    assert a.id != b.id


def test_request_booking_conserva_person_id_experience_id_quando(
    repo, booking_request_factory
) -> None:
    richiesta = booking_request_factory(
        person_id="pseudonimo-x", experience_id="esperienza-y"
    )
    prenotazione = request_booking(repo, richiesta, prezzo_eur=10.0, prenotabile=True)
    assert prenotazione.person_id == "pseudonimo-x"
    assert prenotazione.experience_id == "esperienza-y"
    assert prenotazione.quando == richiesta.quando


# --- orari di apertura (Wave 3a+, validazione minima) -----------------------
#
# `booking_request_factory` di default produce `quando=datetime(2026, 8, 1,
# 15, 0, tzinfo=UTC)` — un sabato (weekday()==5) alle 15:00.


def test_request_booking_accetta_quando_dentro_una_fascia_dichiarata(
    repo, booking_request_factory
) -> None:
    fascia_sabato_pomeriggio = FasciaApertura(
        giorno_settimana=5, apertura=time(14, 0), chiusura=time(19, 0)
    )
    prenotazione = request_booking(
        repo,
        booking_request_factory(),  # sabato 15:00 -> dentro 14:00-19:00
        prezzo_eur=20.0,
        prenotabile=True,
        orari_apertura=[fascia_sabato_pomeriggio],
    )
    assert prenotazione.stato == BookingStatus.RICHIESTA


def test_request_booking_rifiuta_quando_fuori_da_ogni_fascia_dichiarata(
    repo, booking_request_factory
) -> None:
    fascia_sabato_mattina = FasciaApertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(13, 0)
    )
    with pytest.raises(ExperienceNotAvailableError):
        request_booking(
            repo,
            booking_request_factory(),  # sabato 15:00 -> fuori da 9:00-13:00
            prezzo_eur=20.0,
            prenotabile=True,
            orari_apertura=[fascia_sabato_mattina],
        )


def test_request_booking_rifiuta_quando_in_un_giorno_diverso_da_quello_dichiarato(
    repo, booking_request_factory
) -> None:
    fascia_domenica = FasciaApertura(giorno_settimana=6, apertura=time(9, 0), chiusura=time(19, 0))
    with pytest.raises(ExperienceNotAvailableError):
        request_booking(
            repo,
            booking_request_factory(),  # sabato, non domenica
            prezzo_eur=20.0,
            prenotabile=True,
            orari_apertura=[fascia_domenica],
        )


def test_request_booking_fuori_orario_non_persiste_nulla(
    repo, booking_request_factory, monkeypatch
) -> None:
    """Stesso principio di `prenotabile=False`: il rifiuto per orario avviene
    PRIMA di qualunque scrittura."""
    chiamato = []
    monkeypatch.setattr(repo, "create", lambda booking: chiamato.append(booking) or booking)
    fascia_sabato_mattina = FasciaApertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(13, 0)
    )

    with pytest.raises(ExperienceNotAvailableError):
        request_booking(
            repo,
            booking_request_factory(),
            prezzo_eur=20.0,
            prenotabile=True,
            orari_apertura=[fascia_sabato_mattina],
        )

    assert chiamato == []


def test_request_booking_senza_orari_dichiarati_non_rifiuta_mai_per_questo(
    repo, booking_request_factory
) -> None:
    """`orari_apertura` omesso (default `None`/nessun vincolo dichiarato):
    comportamento INVARIATO, nessuna esperienza esistente oggi dichiara
    orari, quindi nessuna prenotazione deve rompersi per questo motivo."""
    prenotazione = request_booking(
        repo,
        booking_request_factory(quando=datetime(2026, 1, 1, 3, 0, tzinfo=UTC)),  # ora improbabile
        prezzo_eur=20.0,
        prenotabile=True,
    )
    assert prenotazione.stato == BookingStatus.RICHIESTA


def test_request_booking_orari_apertura_esplicitamente_vuota_non_rifiuta_mai(
    repo, booking_request_factory
) -> None:
    prenotazione = request_booking(
        repo,
        booking_request_factory(quando=datetime(2026, 1, 1, 3, 0, tzinfo=UTC)),
        prezzo_eur=20.0,
        prenotabile=True,
        orari_apertura=[],
    )
    assert prenotazione.stato == BookingStatus.RICHIESTA


def test_request_booking_prenotabile_falso_ha_priorita_sullorario(
    repo, booking_request_factory
) -> None:
    """Se un'esperienza non è prenotabile E l'orario è comunque fuori fascia,
    l'errore sollevato è SEMPRE `ExperienceNotBookableError` (controllato
    per primo): un ordine di controllo deterministico, non un dettaglio
    implementativo lasciato al caso."""
    fascia_sabato_mattina = FasciaApertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(13, 0)
    )
    with pytest.raises(ExperienceNotBookableError):
        request_booking(
            repo,
            booking_request_factory(),  # sabato 15:00, fuori fascia E non prenotabile
            prezzo_eur=20.0,
            prenotabile=False,
            orari_apertura=[fascia_sabato_mattina],
        )


# --- IL VINCOLO CARDINE: nessuna commissione prima della conferma -----------


def test_nessuna_commissione_esiste_prima_della_conferma(repo, booking_request_factory) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=20.0, prenotabile=True
    )
    assert repo.get_commission(prenotazione.id) is None


def test_confirm_booking_calcola_la_commissione_solo_dopo_la_conferma(
    repo, booking_request_factory
) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=100.0, prenotabile=True
    )
    assert repo.get_commission(prenotazione.id) is None  # ancora nessuna commissione

    confermata = confirm_booking(repo, prenotazione.id)

    assert confermata.stato == BookingStatus.CONFERMATA
    commissione = repo.get_commission(prenotazione.id)
    assert commissione is not None
    assert commissione.importo_eur == pytest.approx(15.0)  # 100 * 0.15
    assert commissione.percentuale == CommissionRecord.model_fields["percentuale"].default


def test_confirm_booking_persiste_la_transizione_di_stato_prima_di_registrare_la_commissione(
    repo, booking_request_factory, monkeypatch
) -> None:
    """Prova diretta dell'ORDINE: intercetta `record_commission` e verifica
    che, nel momento in cui viene chiamata, il repository riporta GIÀ lo
    stato CONFERMATA per questa prenotazione (non un ordine invertito)."""
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=50.0, prenotabile=True
    )

    stato_al_momento_della_registrazione: list[BookingStatus] = []
    originale = repo.record_commission

    def spia(commission):
        stato_al_momento_della_registrazione.append(repo.get(commission.booking_id).stato)
        return originale(commission)

    monkeypatch.setattr(repo, "record_commission", spia)

    confirm_booking(repo, prenotazione.id)

    assert stato_al_momento_della_registrazione == [BookingStatus.CONFERMATA]


def test_confirm_booking_e_idempotente_nessuna_doppia_commissione(
    repo, booking_request_factory
) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=100.0, prenotabile=True
    )
    confirm_booking(repo, prenotazione.id)
    prima = repo.get_commission(prenotazione.id)

    confermata_di_nuovo = confirm_booking(repo, prenotazione.id)  # seconda chiamata

    assert confermata_di_nuovo.stato == BookingStatus.CONFERMATA
    dopo = repo.get_commission(prenotazione.id)
    assert dopo == prima  # stessa commissione, non una seconda


def test_confirm_booking_id_sconosciuto_solleva_booking_not_found_error(repo) -> None:
    with pytest.raises(BookingNotFoundError):
        confirm_booking(repo, "non-esiste")


def test_confirm_booking_su_annullata_rifiutato(repo, booking_request_factory) -> None:
    prenotazione = request_booking(
        repo, booking_request_factory(), prezzo_eur=20.0, prenotabile=True
    )
    repo.update_status(prenotazione.id, BookingStatus.ANNULLATA)

    with pytest.raises(InvalidBookingStateError):
        confirm_booking(repo, prenotazione.id)

    # Nessuna commissione è stata registrata per una prenotazione annullata.
    assert repo.get_commission(prenotazione.id) is None


# --- nessun percorso di import verso experience_engine ----------------------


def test_service_non_importa_experience_engine() -> None:
    """Test-guard: nessuna riga di `marketplace.service` importa
    `experience_engine`. Ispeziona l'AST (non la sorgente grezza, che
    includerebbe anche le parole nella docstring che SPIEGA la regola)."""
    import ast

    import marketplace.service as service_module

    albero = ast.parse(inspect.getsource(service_module))
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            assert not any(
                alias.name.split(".")[0] == "experience_engine" for alias in nodo.names
            )
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.module is None or nodo.module.split(".")[0] != "experience_engine"


def test_percentuale_commissione_letta_dal_contratto_non_duplicata() -> None:
    """La percentuale usata da `confirm_booking` è la stessa costante del
    default di `CommissionRecord.percentuale`: se `contract-keeper` la
    cambia, questo modulo la segue senza modifiche di codice."""
    from marketplace.service import _PERCENTUALE_COMMISSIONE_DEFAULT

    assert _PERCENTUALE_COMMISSIONE_DEFAULT == CommissionRecord.model_fields["percentuale"].default
