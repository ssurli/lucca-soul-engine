"""Test di `urban_memory.canale_fluttuante` — l'orchestrazione del lato
scrittura (`persist_signal`) e del lato lettura (`sweep_and_fetch_active`)
del canale fluttuante persistente (Fase 3, `docs/PROMOZIONE_TRACCIA.md`).

Usa `InMemorySegnaleFluttuanteRepository`/`InMemoryTracciaRepository`
(nessun database reale: questi test riguardano l'ORCHESTRAZIONE tra i due
repository e il `place_link_writer`, non la persistenza in sé — già coperta
da `test_segnale_repository.py`/`test_traccia_repository.py`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from contracts import SegnaleFluttuante
from urban_memory.canale_fluttuante import persist_signal, sweep_and_fetch_active
from urban_memory.segnale_repository import InMemorySegnaleFluttuanteRepository
from urban_memory.traccia_repository import InMemoryTracciaRepository

ORA = datetime.now(UTC)


def _segnale(**overrides: object) -> SegnaleFluttuante:
    defaults: dict[str, object] = {
        "id": "violinista-piazza-anfiteatro-1",
        "descrizione": "Un violinista suona in piazza",
        "temi": ["musica", "arte"],
        "place_id": "piazza-anfiteatro",
        "non_commerciale": True,
        "valido_fino": ORA + timedelta(hours=1),
    }
    defaults.update(overrides)
    return SegnaleFluttuante(**defaults)


# ---------------------------------------------------------------------------
# persist_signal — lato scrittura
# ---------------------------------------------------------------------------


def test_persist_signal_delega_al_repository() -> None:
    repo = InMemorySegnaleFluttuanteRepository()
    segnale = _segnale()

    persistito = persist_signal(repo, segnale)

    assert persistito == segnale
    assert repo.fetch_attivi(ORA) == [segnale]


# ---------------------------------------------------------------------------
# sweep_and_fetch_active — lato lettura: cammino felice
# ---------------------------------------------------------------------------


def test_segnale_attivo_compare_tra_gli_eventi_attivi() -> None:
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(valido_fino=ORA + timedelta(hours=2)))

    attivi = sweep_and_fetch_active(segnale_repo, traccia_repo, now=ORA)

    assert [s.id for s in attivi] == ["violinista-piazza-anfiteatro-1"]


def test_segnale_scaduto_non_compare_e_deposita_traccia_una_sola_volta() -> None:
    """Cammino felice della scadenza: un segnale scaduto (a) NON compare tra
    gli attivi e (b) deposita ESATTAMENTE una traccia — con `place_id`/`temi`
    presi dal segnale e `creato_il` timbrato dal server (Strada B)."""
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade-oggi", valido_fino=ORA + timedelta(minutes=1)))

    istante_sweep = ORA + timedelta(hours=1)  # simulato: dopo la scadenza
    attivi = sweep_and_fetch_active(segnale_repo, traccia_repo, now=istante_sweep)

    assert attivi == [], "un segnale scaduto non deve mai comparire tra gli attivi"
    tracce = traccia_repo.list_for_place("piazza-anfiteatro")
    assert len(tracce) == 1
    traccia = tracce[0]
    assert traccia.segnale_id == "scade-oggi"
    assert traccia.place_id == "piazza-anfiteatro"
    assert traccia.temi == ("musica", "arte")
    assert traccia.creato_il == istante_sweep


def test_creato_il_della_traccia_e_tz_aware() -> None:
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade", valido_fino=ORA + timedelta(minutes=1)))

    sweep_and_fetch_active(segnale_repo, traccia_repo, now=ORA + timedelta(hours=1))

    traccia = traccia_repo.list_for_place("piazza-anfiteatro")[0]
    assert traccia.creato_il.tzinfo is not None


# ---------------------------------------------------------------------------
# IDEMPOTENZA — load-bearing, test esplicito e dedicato
# ---------------------------------------------------------------------------


def test_sweep_ripetuto_non_rideposita_la_traccia() -> None:
    """LOAD-BEARING: uno scaduto già spazzato NON deve MAI ri-depositare la
    traccia. Chiama `sweep_and_fetch_active` DUE volte con lo stesso segnale
    già scaduto: solo la PRIMA chiamata deposita, la seconda è un no-op —
    verificato contando le righe nel ledger, non assumendolo."""
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade-una-volta", valido_fino=ORA + timedelta(minutes=1)))

    istante = ORA + timedelta(hours=1)
    sweep_and_fetch_active(segnale_repo, traccia_repo, now=istante)
    sweep_and_fetch_active(segnale_repo, traccia_repo, now=istante)
    sweep_and_fetch_active(segnale_repo, traccia_repo, now=istante + timedelta(days=365))

    tracce = traccia_repo.list_for_place("piazza-anfiteatro")
    assert len(tracce) == 1, (
        f"sweep_and_fetch_active ripetuto ha depositato {len(tracce)} tracce "
        "invece di 1: violazione dell'idempotenza load-bearing"
    )


# ---------------------------------------------------------------------------
# place_link_writer — proprietà derivata sul grafo, best-effort
# ---------------------------------------------------------------------------


def test_place_link_writer_invocato_per_ogni_segnale_scaduto() -> None:
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade", valido_fino=ORA + timedelta(minutes=1)))
    chiamate: list[tuple[str, object]] = []

    def _writer(place_id: str, quando: datetime) -> None:
        chiamate.append((place_id, quando))

    istante = ORA + timedelta(hours=1)
    sweep_and_fetch_active(segnale_repo, traccia_repo, place_link_writer=_writer, now=istante)

    assert chiamate == [("piazza-anfiteatro", istante)]


def test_place_link_writer_none_di_default_non_e_mai_chiamato() -> None:
    # Default None: nessuna scrittura nel grafo, nessun errore — comodo per
    # test di dominio puri che riguardano solo Postgres.
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade", valido_fino=ORA + timedelta(minutes=1)))

    # Nessuna eccezione, nessun place_link_writer passato.
    attivi = sweep_and_fetch_active(segnale_repo, traccia_repo, now=ORA + timedelta(hours=1))
    assert attivi == []


def test_place_link_writer_che_fallisce_e_isolato_non_propaga(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Revisione `ethics-guardian`: un `place_link_writer` che fallisce
    (grafo irraggiungibile) NON deve MAI propagare — `ultima_traccia_il` è
    una proprietà DERIVATA, best-effort (docs/PROMOZIONE_TRACCIA.md §2a). La
    traccia su Postgres (già depositata PRIMA del tentativo di scrittura sul
    grafo) resta presente: solo la proprietà derivata non si aggiorna, mai
    un dato perso."""
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade", valido_fino=ORA + timedelta(minutes=1)))

    def _writer_che_fallisce(place_id: str, quando: datetime) -> None:
        raise RuntimeError("grafo irraggiungibile (simulato)")

    with caplog.at_level("WARNING"):
        attivi = sweep_and_fetch_active(
            segnale_repo,
            traccia_repo,
            place_link_writer=_writer_che_fallisce,
            now=ORA + timedelta(hours=1),
        )

    assert attivi == []  # nessuna eccezione propagata fin qui
    tracce = traccia_repo.list_for_place("piazza-anfiteatro")
    assert len(tracce) == 1, "la traccia su Postgres resta la fonte di verità, mai persa"
    assert any("ultima_traccia_il" in r.message for r in caplog.records), (
        "il fallimento del place_link_writer deve essere loggato, non silenzioso"
    )


def test_deposita_che_fallisce_e_isolato_non_propaga(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Revisione `ethics-guardian` (FAIL corretto): un fallimento di
    `deposita` per un segnale già transitato a `expired` (commit
    irreversibile in `sweep_scaduti`, vedi il docstring del modulo) NON deve
    MAI propagare da `sweep_and_fetch_active` — è isolato, loggato con
    salienza ERROR (non WARNING: è una perdita PERMANENTE, non un dato
    stantio recuperabile come `ultima_traccia_il`), e la chiamata prosegue
    normalmente (ritorna `fetch_attivi`, mai un'eccezione)."""
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale(id="scade", valido_fino=ORA + timedelta(minutes=1)))
    # Deposita già una traccia con lo stesso segnale_id "a mano" per forzare
    # la violazione dell'idempotenza (difesa in profondità del repository,
    # vedi test_traccia_repository.py) — il modo più semplice per far
    # fallire `deposita` senza un mock dedicato.
    traccia_repo.deposita(
        segnale_id="scade", place_id="piazza-anfiteatro", temi=["musica"], creato_il=ORA
    )

    with caplog.at_level("ERROR"):
        attivi = sweep_and_fetch_active(segnale_repo, traccia_repo, now=ORA + timedelta(hours=1))

    assert attivi == []  # nessuna eccezione propagata fin qui
    assert any("PERDITA PERMANENTE" in r.message for r in caplog.records), (
        "la perdita permanente della traccia deve essere loggata esplicitamente, "
        "mai silenziosa"
    )


# ---------------------------------------------------------------------------
# ISOLAMENTO PER SEGNALE — revisione ethics-guardian, load-bearing
# ---------------------------------------------------------------------------


def test_fallimento_deposita_isolato_non_blocca_gli_altri_segnali(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LOAD-BEARING (revisione `ethics-guardian`, FAIL corretto in questa
    versione): due segnali scadono nello stesso sweep. Il deposito del
    PRIMO fallisce (storage simulato) — il SECONDO deve comunque ricevere
    la sua traccia: un fallimento per-segnale non deve mai propagarsi ad
    altri segnali dello stesso batch (nessuna transazione condivisa tra
    `SegnaleFluttuanteRepository` e `TracciaRepository`: l'isolamento è
    PER SEGNALE, non atomicità piena)."""
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    scade_a_breve = ORA + timedelta(minutes=1)
    segnale_repo.persist(
        _segnale(id="fallisce", place_id="luogo-a", temi=["musica"], valido_fino=scade_a_breve)
    )
    segnale_repo.persist(
        _segnale(id="riesce", place_id="luogo-b", temi=["storia"], valido_fino=scade_a_breve)
    )

    reale = InMemoryTracciaRepository()

    class _TracciaRepoCheFallisceSuUnSegnale:
        """Delega al repository reale, tranne per `segnale_id="fallisce"`,
        dove simula uno storage irraggiungibile — un TEST DOUBLE mirato,
        non un mock generico: dimostra l'isolamento senza dipendere da un
        dettaglio implementativo del repository reale (come la violazione
        UNIQUE usata in `test_deposita_che_fallisce_e_isolato_non_propaga`
        sopra)."""

        def deposita(
            self, *, segnale_id: str, place_id: str, temi: list[str], creato_il: datetime
        ):
            if segnale_id == "fallisce":
                raise RuntimeError("storage irraggiungibile (simulato)")
            return reale.deposita(
                segnale_id=segnale_id, place_id=place_id, temi=temi, creato_il=creato_il
            )

        def list_for_place(self, place_id: str):
            return reale.list_for_place(place_id)

    istante = ORA + timedelta(hours=1)
    with caplog.at_level("ERROR"):
        attivi = sweep_and_fetch_active(
            segnale_repo, _TracciaRepoCheFallisceSuUnSegnale(), now=istante
        )

    assert attivi == []  # entrambi scaduti, nessuno attivo

    # Il segnale che fallisce NON ha depositato nulla...
    assert reale.list_for_place("luogo-a") == []
    # ...ma il segnale SUCCESSIVO nello STESSO sweep è comunque depositato:
    # l'isolamento per-segnale ha contenuto il danno.
    tracce_b = reale.list_for_place("luogo-b")
    assert len(tracce_b) == 1
    assert tracce_b[0].segnale_id == "riesce"

    assert any(
        "PERDITA PERMANENTE" in r.message and "fallisce" in r.message for r in caplog.records
    )
