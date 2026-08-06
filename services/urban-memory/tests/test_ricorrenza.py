"""Test di `urban_memory.ricorrenza` — rilevamento pattern (dominio puro,
nessun I/O reale: `InMemoryTracciaRepository`/
`InMemoryPatternCestinatoRepository`, stesso stile di
`recommender.ranking.costruisci_score_fn`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from urban_memory.cestino_repository import InMemoryPatternCestinatoRepository
from urban_memory.promozione_evento import evento_id_per_pattern
from urban_memory.ricorrenza import N_MINIMO_OCCORRENZE, rileva_candidati
from urban_memory.traccia_repository import InMemoryTracciaRepository

BASE = datetime(2026, 1, 1, tzinfo=UTC)


_contatore_segnali = 0


def _deposita(repo, *, place_id: str, temi: list[str], giorni: list[float]) -> None:
    global _contatore_segnali
    for g in giorni:
        _contatore_segnali += 1
        repo.deposita(
            segnale_id=f"{place_id}-{'-'.join(temi)}-{_contatore_segnali}",
            place_id=place_id,
            temi=temi,
            creato_il=BASE + timedelta(days=g),
        )


@pytest.fixture
def repos():
    return InMemoryTracciaRepository(), InMemoryPatternCestinatoRepository()


def test_tre_occorrenze_regolari_e_candidato(repos) -> None:
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="piazza-anfiteatro", temi=["musica"], giorni=[0, 7, 14])

    candidati = rileva_candidati(traccia_repo, cestino_repo)

    assert len(candidati) == 1
    [candidato] = candidati
    assert candidato.place_id == "piazza-anfiteatro"
    assert candidato.temi == ("musica",)
    assert candidato.cadenza_giorni == pytest.approx(7.0)
    assert candidato.coefficiente_variazione == pytest.approx(0.0)


def test_due_occorrenze_non_e_candidato(repos) -> None:
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7])

    assert rileva_candidati(traccia_repo, cestino_repo) == []


def test_tre_occorrenze_molto_irregolari_non_e_candidato(repos) -> None:
    traccia_repo, cestino_repo = repos
    # Intervalli molto dispersi: 1 giorno, poi 40 giorni.
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 1, 41])

    assert rileva_candidati(traccia_repo, cestino_repo) == []


def test_stessa_soglia_funziona_per_pattern_settimanale_e_annuale(repos) -> None:
    """Nessun bias di scala: un pattern annuale con 3 occorrenze regolari a
    ~365gg è candidato quanto uno settimanale a ~7gg regolari — la
    regolarità è misurata RELATIVA (coefficiente di variazione), non in
    valore assoluto."""
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-settimanale", temi=["musica"], giorni=[0, 7, 14])
    _deposita(traccia_repo, place_id="luogo-annuale", temi=["festa"], giorni=[0, 365, 730])

    candidati = rileva_candidati(traccia_repo, cestino_repo)

    place_ids = {c.place_id for c in candidati}
    assert place_ids == {"luogo-settimanale", "luogo-annuale"}
    settimanale = next(c for c in candidati if c.place_id == "luogo-settimanale")
    annuale = next(c for c in candidati if c.place_id == "luogo-annuale")
    assert settimanale.coefficiente_variazione == pytest.approx(annuale.coefficiente_variazione)
    assert settimanale.cadenza_giorni == pytest.approx(7.0)
    assert annuale.cadenza_giorni == pytest.approx(365.0)


def test_cestinato_non_ricompare_anche_con_nuove_occorrenze(repos) -> None:
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7, 14])
    assert len(rileva_candidati(traccia_repo, cestino_repo)) == 1

    cestino_repo.cestina(
        place_id="luogo-a", temi=["storia"], promotore="promotore-1", cestinato_il=BASE
    )
    assert rileva_candidati(traccia_repo, cestino_repo) == []

    # Nuove occorrenze dello STESSO pattern, arrivate DOPO il rifiuto.
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[21, 28])

    assert rileva_candidati(traccia_repo, cestino_repo) == [], (
        "un pattern cestinato resta cestinato PER SEMPRE (v1), anche se "
        "accumula nuove occorrenze dopo il rifiuto"
    )


def test_pattern_gia_promosso_non_ricompare_come_candidato(repos) -> None:
    """Correzione ethics-guardian (problema 2): un pattern il cui `:Evento`
    esiste GIÀ nel grafo non deve mai essere ripresentato al Promotore —
    altrimenti rischia di essere RIFIUTATO (cestino permanente) mentre
    l'`:Evento` resta pubblico e attivo, un'incoerenza che nessun
    meccanismo riconcilierebbe."""
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7, 14])

    evento_id = evento_id_per_pattern("luogo-a", ("storia",))

    def evento_esistente(id_: str) -> bool:
        return id_ == evento_id

    candidati = rileva_candidati(traccia_repo, cestino_repo, evento_esistente=evento_esistente)

    assert candidati == []


def test_pattern_non_ancora_promosso_resta_candidato_con_checker_iniettato(repos) -> None:
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7, 14])

    candidati = rileva_candidati(
        traccia_repo, cestino_repo, evento_esistente=lambda _id: False
    )

    assert len(candidati) == 1


def test_rileva_candidati_propaga_eccezione_di_evento_esistente(repos) -> None:
    """Correzione ethics-guardian (follow-up): se `evento_esistente`
    (tipicamente `promozione_evento.Neo4jPromozioneWriter.esiste`) solleva
    (grafo irraggiungibile), `rileva_candidati` NON la inghiotte — propaga,
    così `urban_memory.curatela_pattern.main` può intercettarla al
    contorno e uscire pulito invece di restituire un risultato ambiguo o
    andare in crash altrove."""
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7, 14])

    def evento_esistente_che_fallisce(_id: str) -> bool:
        raise RuntimeError("grafo irraggiungibile")

    with pytest.raises(RuntimeError):
        rileva_candidati(
            traccia_repo, cestino_repo, evento_esistente=evento_esistente_che_fallisce
        )


def test_nessun_checker_evento_esistente_e_comportamento_identico_a_prima(repos) -> None:
    """`evento_esistente=None` (default): nessuna esclusione per "già
    promosso" — comportamento IDENTICO a prima di questa correzione, per i
    test di dominio puri che non riguardano il grafo."""
    traccia_repo, cestino_repo = repos
    _deposita(traccia_repo, place_id="luogo-a", temi=["storia"], giorni=[0, 7, 14])

    candidati = rileva_candidati(traccia_repo, cestino_repo)

    assert len(candidati) == 1


def test_minimo_occorrenze_sotto_il_vincolo_duro_solleva_errore(repos) -> None:
    traccia_repo, cestino_repo = repos
    with pytest.raises(ValueError):
        rileva_candidati(traccia_repo, cestino_repo, minimo_occorrenze=2)


def test_n_minimo_occorrenze_e_almeno_tre() -> None:
    assert N_MINIMO_OCCORRENZE >= 3
