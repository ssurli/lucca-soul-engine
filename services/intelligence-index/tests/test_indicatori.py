"""Test delle 8 funzioni indicatore (`intelligence_index.indicatori`), pure:
nessun database, solo dati sintetici in memoria — copre sia le formule
NEGOZIATE (`attivazione_locale`, `distribuzione_flussi_indicatore`,
`nuovi_percorsi`, e la fonte di `contributi_memoria`) sia quelle PROPOSTE da
questo modulo (`tempo_medio_esperienza_min`, `coinvolgimento`,
`tasso_ritorno`)."""

from __future__ import annotations

from datetime import UTC, datetime, time

from contracts import (
    BehaviorEvent,
    ExperienceNode,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    PersonKind,
)
from intelligence_index.indicatori import (
    _percentile,
    attivazione_locale,
    coinvolgimento,
    contributi_memoria,
    contributi_memoria_curati,
    distribuzione_flussi_indicatore,
    nuovi_percorsi,
    tasso_ritorno,
    tempo_medio_esperienza_min,
)


def _exp(id: str, place_id: str, durata_min: int = 30) -> ExperienceNode:
    return ExperienceNode(
        id=id,
        titolo=f"esperienza {id}",
        place_id=place_id,
        temi=[],
        durata_min=durata_min,
        al_chiuso=False,
        accessibile=True,
    )


def _evento(person_id: str, tipo: str, experience_id: str, giorno: int = 5) -> BehaviorEvent:
    return BehaviorEvent(
        person_id=person_id,
        tipo=tipo,
        experience_id=experience_id,
        ts=datetime(2026, 7, giorno, 10, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# tempo_medio_esperienza_min
# ---------------------------------------------------------------------------


def test_tempo_medio_ignora_le_sole_view() -> None:
    catalogo = {"e1": _exp("e1", "luogo-1", durata_min=60)}
    eventi = [_evento("p1", "view", "e1")]
    valore, persone = tempo_medio_esperienza_min(eventi, catalogo)
    assert valore == 0.0
    assert persone == set()


def test_tempo_medio_pesato_sugli_eventi_di_presenza() -> None:
    catalogo = {
        "e1": _exp("e1", "luogo-1", durata_min=60),
        "e2": _exp("e2", "luogo-2", durata_min=30),
    }
    eventi = [
        _evento("p1", "stop", "e1"),
        _evento("p2", "stop", "e1"),
        _evento("p3", "booking", "e2"),
    ]
    valore, persone = tempo_medio_esperienza_min(eventi, catalogo)
    # (60 + 60 + 30) / 3 = 50.0: due eventi su e1 pesano il doppio di uno su e2.
    assert valore == 50.0
    assert persone == {"p1", "p2", "p3"}


def test_tempo_medio_ignora_esperienza_non_nel_catalogo() -> None:
    catalogo = {"e1": _exp("e1", "luogo-1", durata_min=60)}
    eventi = [_evento("p1", "stop", "e1"), _evento("p2", "stop", "e-rimossa")]
    valore, persone = tempo_medio_esperienza_min(eventi, catalogo)
    assert valore == 60.0
    assert persone == {"p1"}


# ---------------------------------------------------------------------------
# coinvolgimento
# ---------------------------------------------------------------------------


def test_coinvolgimento_senza_view_e_zero() -> None:
    eventi = [_evento("p1", "stop", "e1")]
    valore, persone = coinvolgimento(eventi)
    assert valore == 0.0
    assert persone == set()


def test_coinvolgimento_tutte_le_view_convertono() -> None:
    eventi = [
        _evento("p1", "view", "e1"),
        _evento("p1", "stop", "e1"),
        _evento("p2", "view", "e2"),
        _evento("p2", "photo", "e2"),
    ]
    valore, persone = coinvolgimento(eventi)
    assert valore == 1.0
    assert persone == {"p1", "p2"}


def test_coinvolgimento_quota_parziale() -> None:
    eventi = [
        _evento("p1", "view", "e1"),
        _evento("p1", "stop", "e1"),  # converte
        _evento("p2", "view", "e2"),  # non converte
    ]
    valore, persone = coinvolgimento(eventi)
    assert valore == 0.5
    assert persone == {"p1", "p2"}


def test_coinvolgimento_presenza_senza_view_non_conta_ne_su_ne_giu() -> None:
    eventi = [
        _evento("p1", "view", "e1"),  # non converte: nessun evento forte su (p1, e1)
        _evento("p2", "stop", "e2"),  # presenza SENZA view precedente: ignorata qui
    ]
    valore, persone = coinvolgimento(eventi)
    assert valore == 0.0
    assert persone == {"p1"}  # p2 non ha mai "visto": non entra nel denominatore


# ---------------------------------------------------------------------------
# tasso_ritorno
# ---------------------------------------------------------------------------


def test_tasso_ritorno_nessun_evento_e_zero() -> None:
    valore, persone = tasso_ritorno([])
    assert valore == 0.0
    assert persone == set()


def test_tasso_ritorno_persona_attiva_un_solo_giorno_non_conta() -> None:
    eventi = [_evento("p1", "view", "e1", giorno=5), _evento("p1", "stop", "e1", giorno=5)]
    valore, persone = tasso_ritorno(eventi)
    assert valore == 0.0
    assert persone == {"p1"}


def test_tasso_ritorno_persona_attiva_due_giorni_distinti_conta() -> None:
    eventi = [_evento("p1", "view", "e1", giorno=5), _evento("p1", "stop", "e1", giorno=20)]
    valore, persone = tasso_ritorno(eventi)
    assert valore == 1.0
    assert persone == {"p1"}


def test_tasso_ritorno_quota_su_popolazione_mista() -> None:
    eventi = [
        _evento("p1", "view", "e1", giorno=5),
        _evento("p1", "stop", "e1", giorno=20),  # p1: 2 giorni -> ritorno
        _evento("p2", "view", "e1", giorno=5),  # p2: 1 giorno -> no ritorno
    ]
    valore, persone = tasso_ritorno(eventi)
    assert valore == 0.5
    assert persone == {"p1", "p2"}


# ---------------------------------------------------------------------------
# attivazione_locale
# ---------------------------------------------------------------------------


def test_attivazione_locale_nessuna_tappa_e_zero() -> None:
    valore, persone = attivazione_locale([], {}, {})
    assert valore == 0.0
    assert persone == set()


def test_attivazione_locale_percentile_e_mediana_di_default() -> None:
    assert _percentile([1, 2, 3, 4, 5], 0.5) == 3.0
    assert _percentile([1, 2, 3, 4], 0.5) == 2.5


def test_attivazione_locale_tappe_su_luoghi_minori_vs_maggiori() -> None:
    catalogo = {
        "e-maggiore": _exp("e-maggiore", "luogo-maggiore"),
        "e-minore": _exp("e-minore", "luogo-minore"),
    }
    # Grado semantico: 3 luoghi, mediana = 5 (grado di "luogo-medio").
    grado = {"luogo-maggiore": 10, "luogo-medio": 5, "luogo-minore": 1}
    eventi = [
        _evento("p1", "stop", "e-maggiore"),
        _evento("p2", "stop", "e-minore"),
        _evento("p3", "stop", "e-minore"),
    ]
    valore, persone = attivazione_locale(eventi, catalogo, grado)
    # 2 tappe su 3 sono su un luogo con grado (1) < mediana (5): fuori dai top.
    assert valore == 2 / 3
    assert persone == {"p1", "p2", "p3"}


def test_attivazione_locale_ignora_eventi_non_stop() -> None:
    catalogo = {"e1": _exp("e1", "luogo-minore")}
    grado = {"luogo-minore": 1, "luogo-maggiore": 10}
    eventi = [_evento("p1", "view", "e1"), _evento("p1", "booking", "e1")]
    valore, persone = attivazione_locale(eventi, catalogo, grado)
    assert valore == 0.0
    assert persone == set()


# ---------------------------------------------------------------------------
# distribuzione_flussi_indicatore
# ---------------------------------------------------------------------------


def test_distribuzione_flussi_indicatore_usa_solo_gli_stop() -> None:
    catalogo = {"e1": _exp("e1", "luogo-1"), "e2": _exp("e2", "luogo-2")}
    eventi = [
        _evento("p1", "view", "e1"),  # ignorato
        _evento("p1", "stop", "e1"),
        _evento("p2", "stop", "e2"),
    ]
    valore, persone = distribuzione_flussi_indicatore(eventi, catalogo, 15)
    assert 0.0 < valore < 1.0
    assert persone == {"p1", "p2"}


def test_distribuzione_flussi_indicatore_concentrazione_totale() -> None:
    catalogo = {"e1": _exp("e1", "luogo-1")}
    eventi = [_evento(f"p{i}", "stop", "e1") for i in range(5)]
    valore, persone = distribuzione_flussi_indicatore(eventi, catalogo, 15)
    assert valore == 0.0
    assert len(persone) == 5


# ---------------------------------------------------------------------------
# nuovi_percorsi
# ---------------------------------------------------------------------------


def _tappa(experience_id: str, ora: int = 10) -> ItineraryStop:
    return ItineraryStop(
        experience_id=experience_id, arrivo=time(ora, 0), durata_min=30, reason="motivo di prova"
    )


def _itinerario(person_id: str, experience_ids: list[str]) -> Itinerary:
    return Itinerary(
        person_id=person_id,
        stops=[_tappa(eid, ora=10 + i) for i, eid in enumerate(experience_ids)],
        generated_at=datetime(2026, 7, 10, tzinfo=UTC),
    )


def test_nuovi_percorsi_denominatore_zero_e_zero() -> None:
    valore, persone = nuovi_percorsi([], {}, set())
    assert valore == 0.0
    assert persone == set()


def test_nuovi_percorsi_nessun_itinerario_e_zero_ma_denominatore_non_zero() -> None:
    non_connesse = {frozenset({"a", "b"}), frozenset({"b", "c"})}
    valore, persone = nuovi_percorsi([], {}, non_connesse)
    assert valore == 0.0
    assert persone == set()


def test_nuovi_percorsi_coppia_emersa_conta_una_sola_volta() -> None:
    catalogo = {"e-a": _exp("e-a", "a"), "e-b": _exp("e-b", "b"), "e-c": _exp("e-c", "c")}
    non_connesse = {frozenset({"a", "b"}), frozenset({"b", "c"}), frozenset({"a", "c"})}
    itinerari = [
        _itinerario("p1", ["e-a", "e-b"]),  # emerge la coppia {a, b}
        _itinerario("p2", ["e-a", "e-b"]),  # stessa coppia: non raddoppia il numeratore
    ]
    valore, persone = nuovi_percorsi(itinerari, catalogo, non_connesse)
    assert valore == 1 / 3
    assert persone == {"p1", "p2"}


def test_nuovi_percorsi_ignora_coppie_gia_connesse() -> None:
    catalogo = {"e-a": _exp("e-a", "a"), "e-b": _exp("e-b", "b")}
    non_connesse: set[frozenset[str]] = {frozenset({"x", "y"})}  # {a, b} NON è tra le non connesse
    itinerari = [_itinerario("p1", ["e-a", "e-b"])]
    valore, persone = nuovi_percorsi(itinerari, catalogo, non_connesse)
    assert valore == 0.0
    # p1 ha comunque prodotto una coppia VALUTABILE (due luoghi distinti,
    # entrambi nel catalogo): entra nel gate k=10 come "persona il cui
    # itinerario ha contribuito al calcolo", anche se quella coppia non è
    # emersa come nuova (era già connessa) — il gate deve riflettere la
    # popolazione che ha alimentato numeratore+denominatore, non solo chi ha
    # prodotto un "successo".
    assert persone == {"p1"}


def test_nuovi_percorsi_tappe_consecutive_stesso_luogo_non_formano_coppia() -> None:
    catalogo = {"e-a1": _exp("e-a1", "a"), "e-a2": _exp("e-a2", "a")}
    non_connesse: set[frozenset[str]] = {frozenset({"a", "b"})}
    itinerari = [_itinerario("p1", ["e-a1", "e-a2"])]
    valore, persone = nuovi_percorsi(itinerari, catalogo, non_connesse)
    assert valore == 0.0
    assert persone == set()


# ---------------------------------------------------------------------------
# contributi_memoria
# ---------------------------------------------------------------------------


def _memoria(
    id: str, curato: bool = True, contributor_id: str = "cittadino-1"
) -> MemoryContribution:
    return MemoryContribution(
        id=id,
        kind=MemoryKind.RACCONTO,
        testo="un racconto",
        riguarda=["luogo-1"],
        contributor_id=contributor_id,
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 10, tzinfo=UTC),
        curato=curato,
    )


def test_contributi_memoria_conta_la_lista_ricevuta() -> None:
    memorie = [
        _memoria("m1", contributor_id="c1"),
        _memoria("m2", contributor_id="c2"),
        _memoria("m3", contributor_id="c3"),
    ]
    valore, contributori = contributi_memoria(memorie)
    assert valore == 3
    assert contributori == {"c1", "c2", "c3"}


def test_contributi_memoria_lista_vuota_e_zero() -> None:
    valore, contributori = contributi_memoria([])
    assert valore == 0
    assert contributori == set()


def test_contributi_memoria_conta_curati_e_non_curati_indistintamente() -> None:
    # NEGOZIATA col committente: l'indicatore misura la PARTECIPAZIONE, non
    # l'APPROVAZIONE — un contributo curato=False (in coda alla curatela, o
    # bloccato per un target non ancora nel grafo, vedi CLAUDE.md Wave 2)
    # conta comunque.
    memorie = [
        _memoria("m-curato-1", curato=True, contributor_id="c1"),
        _memoria("m-curato-2", curato=True, contributor_id="c2"),
        _memoria("m-pending-1", curato=False, contributor_id="c3"),
        _memoria("m-pending-2", curato=False, contributor_id="c4"),
        _memoria("m-pending-3", curato=False, contributor_id="c5"),
    ]
    valore, contributori = contributi_memoria(memorie)
    assert valore == 5
    assert contributori == {"c1", "c2", "c3", "c4", "c5"}


def test_contributi_memoria_solo_non_curati_conta_comunque() -> None:
    memorie = [
        _memoria("m1", curato=False, contributor_id="c1"),
        _memoria("m2", curato=False, contributor_id="c2"),
    ]
    valore, contributori = contributi_memoria(memorie)
    assert valore == 2
    assert contributori == {"c1", "c2"}


def test_contributi_memoria_deduplica_i_contributor_id_ripetuti() -> None:
    # Lo stesso contributor_id compare su più contributi: la popolazione
    # coinvolta è deduplicata, stesso principio di soglia.persone_sufficienti
    # (il gate k=10 conta persone distinte, non contributi).
    memorie = [
        _memoria("m1", contributor_id="c1"),
        _memoria("m2", contributor_id="c1"),
        _memoria("m3", contributor_id="c2"),
    ]
    valore, contributori = contributi_memoria(memorie)
    assert valore == 3
    assert contributori == {"c1", "c2"}


def test_contributi_memoria_curati_conta_solo_i_curati() -> None:
    memorie = [
        _memoria("m-curato-1", curato=True),
        _memoria("m-curato-2", curato=True),
        _memoria("m-pending-1", curato=False),
        _memoria("m-pending-2", curato=False),
        _memoria("m-pending-3", curato=False),
    ]
    assert contributi_memoria_curati(memorie) == 2


def test_contributi_memoria_curati_lista_vuota_e_zero() -> None:
    assert contributi_memoria_curati([]) == 0


def test_contributi_memoria_curati_nessun_curato_e_zero() -> None:
    memorie = [_memoria("m1", curato=False), _memoria("m2", curato=False)]
    assert contributi_memoria_curati(memorie) == 0
