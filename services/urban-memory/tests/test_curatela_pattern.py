"""Test di `urban_memory.curatela_pattern` — le funzioni RICHIAMABILI
separatamente dal `main()` interattivo: `promuovi_pattern`/`rifiuta_pattern`,
e il ciclo interattivo `_esegui_interattivo` (I/O astratto dietro `_chiedi`,
monkeypatchabile — nessun `input()` reale, nessun driver Neo4j vero).

`main()` stesso NON è testato qui: costruisce sempre `PostgresTracciaRepository`/
`PostgresPatternCestinatoRepository`/`Neo4jPromozioneWriter.from_env()` al suo
interno (nessun parametro di iniezione nella firma) — stesso pattern non
testato di `urban_memory.verify.main()`/`urban_memory.submit_signal.main()` in
questo servizio: una CLI di persistenza REALE, verificata girandola contro
uno storage vero, non con un mock. Se in futuro serve testarla end-to-end
senza infrastruttura, la firma di `main()` andrebbe prima resa iniettabile
(repository/writer come parametri) — una modifica di produzione, non di
questo file."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from urban_memory import curatela_pattern
from urban_memory.cestino_repository import InMemoryPatternCestinatoRepository
from urban_memory.curatela_pattern import promuovi_pattern, rifiuta_pattern
from urban_memory.promozione_evento import PromozioneEventoError, evento_id_per_pattern
from urban_memory.ricorrenza import PatternCandidato, rileva_candidati
from urban_memory.traccia_repository import InMemoryTracciaRepository

CANDIDATO = PatternCandidato(
    place_id="piazza-anfiteatro",
    temi=("arte", "musica"),
    occorrenze=(
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 8, tzinfo=UTC),
        datetime(2026, 1, 15, tzinfo=UTC),
    ),
    cadenza_giorni=7.0,
    coefficiente_variazione=0.0,
)


def test_promuovi_pattern_chiama_il_writer_con_i_parametri_del_pattern_e_il_promotore() -> None:
    """Correzione ethics-guardian (problema 1): `promotore` deve essere
    INOLTRATO al writer — è l'accountability della promozione, e a
    differenza del rifiuto (persistito in `pattern_cestinato.promotore`)
    l'unica altra traccia sarebbe un log applicativo, non garantito
    persistente."""
    chiamate: list[tuple[str, tuple[str, ...], float, str]] = []

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        chiamate.append((place_id, temi, cadenza_giorni, promotore))
        return "evento-fittizio"

    evento_id = promuovi_pattern(CANDIDATO, promotore="promotore-1", writer=writer)

    assert evento_id == "evento-fittizio"
    assert chiamate == [("piazza-anfiteatro", ("arte", "musica"), 7.0, "promotore-1")]


def test_promuovi_pattern_propaga_errore_del_writer_senza_toccare_il_cestino() -> None:
    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        raise PromozioneEventoError("luogo inesistente")

    with pytest.raises(PromozioneEventoError):
        promuovi_pattern(CANDIDATO, promotore="promotore-1", writer=writer)


def test_rifiuta_pattern_cestina_col_promotore_e_motivo() -> None:
    cestino_repo = InMemoryPatternCestinatoRepository()

    cestinato = rifiuta_pattern(
        CANDIDATO, cestino_repo, promotore="promotore-1", motivo="troppo raro"
    )

    assert cestinato.place_id == "piazza-anfiteatro"
    assert cestinato.temi == ("arte", "musica")
    assert cestinato.promotore == "promotore-1"
    assert cestinato.motivo == "troppo raro"
    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["musica", "arte"]) is True


def test_rifiuta_pattern_motivo_e_opzionale() -> None:
    cestino_repo = InMemoryPatternCestinatoRepository()

    cestinato = rifiuta_pattern(CANDIDATO, cestino_repo, promotore="promotore-1")

    assert cestinato.motivo is None


def test_rifiuta_pattern_non_tocca_mai_il_grafo() -> None:
    """Nessun parametro "writer"/driver nella firma di `rifiuta_pattern`:
    strutturalmente impossibile scrivere sul grafo durante un rifiuto."""
    import inspect

    firma = inspect.signature(rifiuta_pattern)
    assert "writer" not in firma.parameters
    assert "driver" not in firma.parameters


# ---------------------------------------------------------------------------
# _esegui_interattivo — il ciclo decisionale del Promotore, un candidato alla
# volta. `_chiedi` (l'unico punto di I/O reale, `input()`) è monkeypatchato:
# nessuna interazione col terminale, nessuna infrastruttura reale.
# ---------------------------------------------------------------------------


def test_esegui_interattivo_approva_chiama_il_writer_e_promuove(monkeypatch, capsys) -> None:
    risposte = iter(["a", "promotore-1"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))
    chiamate: list[tuple[str, tuple[str, ...], float, str]] = []

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        chiamate.append((place_id, temi, cadenza_giorni, promotore))
        return "evento-fittizio"

    cestino_repo = InMemoryPatternCestinatoRepository()
    curatela_pattern._esegui_interattivo([CANDIDATO], cestino_repo=cestino_repo, writer=writer)

    assert chiamate == [("piazza-anfiteatro", ("arte", "musica"), 7.0, "promotore-1")]
    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["arte", "musica"]) is False
    assert "OK: promosso a :Evento" in capsys.readouterr().out


def test_esegui_interattivo_approva_con_writer_che_fallisce_stampa_fallito_senza_sollevare(
    monkeypatch, capsys
) -> None:
    """Un `PromozioneEventoError` durante l'approvazione (place_id inesistente
    nel grafo, grafo irraggiungibile) è riportato al Promotore, non propagato:
    il ciclo prosegue con l'eventuale candidato successivo (qui non ce n'è —
    la lista finisce, nessun crash)."""
    risposte = iter(["a", "promotore-1"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        raise PromozioneEventoError("luogo inesistente nel grafo")

    cestino_repo = InMemoryPatternCestinatoRepository()
    curatela_pattern._esegui_interattivo([CANDIDATO], cestino_repo=cestino_repo, writer=writer)

    out = capsys.readouterr().out
    assert "FALLITO" in out
    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["arte", "musica"]) is False


def test_esegui_interattivo_rifiuta_cestina_il_pattern_senza_toccare_il_writer(
    monkeypatch, capsys
) -> None:
    risposte = iter(["r", "promotore-1", "troppo raro"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        raise AssertionError("il writer non deve mai essere chiamato per un rifiuto")

    cestino_repo = InMemoryPatternCestinatoRepository()
    curatela_pattern._esegui_interattivo([CANDIDATO], cestino_repo=cestino_repo, writer=writer)

    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["arte", "musica"]) is True
    assert "cestinato (permanente)" in capsys.readouterr().out


def test_esegui_interattivo_decisione_non_riconosciuta_salta_senza_effetti(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: "")

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        raise AssertionError("il writer non deve mai essere chiamato quando si salta")

    cestino_repo = InMemoryPatternCestinatoRepository()
    curatela_pattern._esegui_interattivo([CANDIDATO], cestino_repo=cestino_repo, writer=writer)

    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["arte", "musica"]) is False
    assert "Saltato" in capsys.readouterr().out


def test_esegui_interattivo_itera_su_piu_candidati_nell_ordine_ricevuto(monkeypatch) -> None:
    secondo_candidato = PatternCandidato(
        place_id="san-michele",
        temi=("storia",),
        occorrenze=(
            datetime(2026, 2, 1, tzinfo=UTC),
            datetime(2026, 2, 8, tzinfo=UTC),
            datetime(2026, 2, 15, tzinfo=UTC),
        ),
        cadenza_giorni=7.0,
        coefficiente_variazione=0.0,
    )
    # CANDIDATO -> rifiuta; secondo_candidato -> approva.
    risposte = iter(["r", "promotore-1", "", "a", "promotore-1"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))
    chiamate: list[str] = []

    def writer(place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str) -> str:
        chiamate.append(place_id)
        return "evento-fittizio"

    cestino_repo = InMemoryPatternCestinatoRepository()
    curatela_pattern._esegui_interattivo(
        [CANDIDATO, secondo_candidato], cestino_repo=cestino_repo, writer=writer
    )

    assert cestino_repo.e_cestinato("piazza-anfiteatro", ["arte", "musica"]) is True
    assert chiamate == ["san-michele"]


# ---------------------------------------------------------------------------
# Integrazione: rileva_candidati (urban_memory.ricorrenza) + promuovi_pattern
# — la stessa promozione ripetuta su una seconda corsa del rilevamento
# produce lo STESSO evento_id (deterministico, `promozione_evento.
# evento_id_per_pattern`). QUI `rileva_candidati` è chiamata SENZA
# `evento_esistente` (nessun grafo iniettato: test di dominio puro), quindi
# NON esclude il pattern già promosso alla seconda corsa — il pattern
# ricompare identico, ed è proprio l'idempotenza dell'evento_id a
# garantire che ripromuoverlo non crei un `:Evento` duplicato sul grafo. Chi
# rileva per la curatela REALE (`urban_memory.curatela_pattern.main`) passa
# SEMPRE `evento_esistente` — vedi `test_ricorrenza.
# test_pattern_gia_promosso_non_ricompare_come_candidato`.
# ---------------------------------------------------------------------------


def test_flusso_rileva_promuovi_rileva_di_nuovo_produce_lo_stesso_evento_id() -> None:
    traccia_repo = InMemoryTracciaRepository()
    cestino_repo = InMemoryPatternCestinatoRepository()
    for indice, giorni in enumerate([0, 7, 14]):
        traccia_repo.deposita(
            segnale_id=f"segnale-{indice}",
            place_id="piazza-anfiteatro",
            temi=["arte", "musica"],
            creato_il=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=giorni),
        )

    def writer_deterministico(
        place_id: str, temi: tuple[str, ...], cadenza_giorni: float, promotore: str
    ) -> str:
        return evento_id_per_pattern(place_id, temi)

    [candidato_1] = rileva_candidati(traccia_repo, cestino_repo)
    evento_id_1 = promuovi_pattern(
        candidato_1, promotore="promotore-1", writer=writer_deterministico
    )

    [candidato_2] = rileva_candidati(traccia_repo, cestino_repo)
    evento_id_2 = promuovi_pattern(
        candidato_2, promotore="promotore-1", writer=writer_deterministico
    )

    assert candidato_1 == candidato_2
    assert evento_id_1 == evento_id_2 == "evento-piazza-anfiteatro-arte-musica"
