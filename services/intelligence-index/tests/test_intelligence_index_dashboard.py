"""Test di `intelligence_index.dashboard` — i due adattatori PURI verso
`DashboardIndexResponse` (`GET /dashboard/index`) e `DashboardFlowsResponse`
(`GET /dashboard/flows`). Nessun database: stessi dati sintetici in memoria
dello stile di `tests/test_index.py`."""

from __future__ import annotations

from datetime import UTC, date, datetime

from contracts import BehaviorEvent, ExperienceNode, MemoryContribution, MemoryKind, PersonKind
from intelligence_index.dashboard import celle_flusso, indice_per_dashboard
from intelligence_index.soglia import SOGLIA_MINIMA_PERSONE

N_PERSONE_SOPRA_SOGLIA = SOGLIA_MINIMA_PERSONE + 5  # margine oltre k=10


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


CATALOGO = {
    "e-a": _exp("e-a", "luogo-a", durata_min=60),
    "e-b": _exp("e-b", "luogo-b", durata_min=30),
}

GRADO_SEMANTICO = {"luogo-a": 10, "luogo-b": 2, "luogo-c": 5}
N_LUOGHI_DISPONIBILI = len(GRADO_SEMANTICO)
NON_CONNESSE: set[frozenset[str]] = {frozenset({"luogo-a", "luogo-b"})}


def _eventi_sopra_soglia() -> list[BehaviorEvent]:
    """`N_PERSONE_SOPRA_SOGLIA` persone, ciascuna con una `view` + uno `stop`
    su `e-a`, tutte dentro luglio 2026 — popolazione sopra k=10 per OGNI
    indicatore che dipende da questi eventi. STESSO scenario di
    `tests/test_index.py::_eventi_sopra_soglia`."""
    eventi: list[BehaviorEvent] = []
    for i in range(N_PERSONE_SOPRA_SOGLIA):
        person_id = f"p{i}"
        eventi.append(
            BehaviorEvent(
                person_id=person_id,
                tipo="view",
                experience_id="e-a",
                ts=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
            )
        )
        eventi.append(
            BehaviorEvent(
                person_id=person_id,
                tipo="stop",
                experience_id="e-a",
                ts=datetime(2026, 7, 15, 10, 30, tzinfo=UTC),
            )
        )
    return eventi


def _memorie_sopra_soglia() -> list[MemoryContribution]:
    """`N_PERSONE_SOPRA_SOGLIA` `MemoryContribution`, ciascuna da un
    `contributor_id` DISTINTO, dentro luglio 2026 — popolazione sopra k=10
    per `contributi_memoria` (stesso principio di `_eventi_sopra_soglia`),
    altrimenti il gate k=10 centrale di `calcola_index` farebbe fallire
    anche lo scenario "sopra soglia" per un indicatore diverso da quello
    sotto test."""
    return [
        MemoryContribution(
            id=f"m{i}",
            kind=MemoryKind.RACCONTO,
            testo="un racconto",
            riguarda=["luogo-a"],
            contributor_id=f"c{i}",
            contributor_kind=PersonKind.CITTADINO,
            consenso=True,
            licenza="CC-BY-SA-4.0",
            creato_il=datetime(2026, 7, 10, tzinfo=UTC),
            curato=True,
        )
        for i in range(N_PERSONE_SOPRA_SOGLIA)
    ]


# ---------------------------------------------------------------------------
# indice_per_dashboard
# ---------------------------------------------------------------------------


def test_indice_per_dashboard_disponibile_sopra_soglia() -> None:
    risposta = indice_per_dashboard(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=_memorie_sopra_soglia(),
    )
    assert risposta.periodo == "2026-07"
    assert risposta.disponibile is True
    assert risposta.index is not None
    assert risposta.index.periodo == "2026-07"
    assert risposta.motivo_indisponibilita is None


def test_indice_per_dashboard_non_disponibile_sotto_soglia() -> None:
    # Solo 3 persone (sotto k=10): calcola_index solleva DatiInsufficientiError,
    # il wrapper la traduce in uno stato esplicito, mai la propaga.
    eventi_pochi = [
        BehaviorEvent(
            person_id=f"p{i}",
            tipo="stop",
            experience_id="e-a",
            ts=datetime(2026, 7, 15, tzinfo=UTC),
        )
        for i in range(3)
    ]
    risposta = indice_per_dashboard(
        periodo="2026-07",
        eventi=eventi_pochi,
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=[],
    )
    assert risposta.periodo == "2026-07"
    assert risposta.disponibile is False
    assert risposta.index is None
    assert risposta.motivo_indisponibilita is not None
    motivo = risposta.motivo_indisponibilita.lower()
    assert "privacy" in motivo or "k=10" in motivo


# ---------------------------------------------------------------------------
# celle_flusso
# ---------------------------------------------------------------------------


def _eventi_flussi() -> list[BehaviorEvent]:
    """`luogo-a`: `N_PERSONE_SOPRA_SOGLIA` tappe/persone distinte, tutte il
    15/07 alle 10. `luogo-b`: 3 tappe/persone distinte (sotto k=10), il
    16/07 alle 9. `luogo-c`: nessuna tappa (assente da questa lista, ma
    presente in `GRADO_SEMANTICO`)."""
    eventi: list[BehaviorEvent] = []
    for i in range(N_PERSONE_SOPRA_SOGLIA):
        eventi.append(
            BehaviorEvent(
                person_id=f"pa{i}",
                tipo="stop",
                experience_id="e-a",
                ts=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
            )
        )
    for i in range(3):
        eventi.append(
            BehaviorEvent(
                person_id=f"pb{i}",
                tipo="stop",
                experience_id="e-b",
                ts=datetime(2026, 7, 16, 9, 0, tzinfo=UTC),
            )
        )
    return eventi


def test_celle_flusso_copre_tutti_i_luoghi_del_grafo() -> None:
    risposta = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
    )
    assert risposta.periodo == "2026-07"
    assert {cella.place_id for cella in risposta.celle} == set(GRADO_SEMANTICO)
    assert len(risposta.celle) == N_LUOGHI_DISPONIBILI


def test_celle_flusso_luogo_sopra_soglia_e_visibile() -> None:
    risposta = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
    )
    cella_a = next(cella for cella in risposta.celle if cella.place_id == "luogo-a")
    assert cella_a.disponibile is True
    assert cella_a.conteggio_tappe == N_PERSONE_SOPRA_SOGLIA


def test_celle_flusso_luogo_sotto_soglia_con_eventi_e_soppresso() -> None:
    risposta = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
    )
    cella_b = next(cella for cella in risposta.celle if cella.place_id == "luogo-b")
    assert cella_b.disponibile is False
    assert cella_b.conteggio_tappe is None


def test_celle_flusso_luogo_a_zero_eventi_e_indistinguibile_dal_soppresso() -> None:
    """PUNTO CRITICO: una cella a ZERO tappe (`luogo-c`, nessun evento) e una
    cella con eventi ma sotto soglia (`luogo-b`, 3 tappe/3 persone) devono
    produrre ESATTAMENTE lo stesso stato osservabile: `disponibile=False,
    conteggio_tappe=None`. Se fossero distinguibili, un osservatore potrebbe
    dedurre per esclusione che una cella soppressa ha necessariamente tra 1 e
    9 persone — l'informazione che il gate k=10 deve nascondere."""
    risposta = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
    )
    cella_b = next(cella for cella in risposta.celle if cella.place_id == "luogo-b")
    cella_c = next(cella for cella in risposta.celle if cella.place_id == "luogo-c")

    assert cella_c.disponibile is False
    assert cella_c.conteggio_tappe is None
    # Stesso identico stato osservabile del luogo con 3 tappe/3 persone:
    assert (cella_b.disponibile, cella_b.conteggio_tappe) == (
        cella_c.disponibile,
        cella_c.conteggio_tappe,
    )


def test_celle_flusso_filtro_giorno_restringe_il_conteggio() -> None:
    # Tutte le tappe di luogo-a sono il 15/07: filtrare su un altro giorno
    # deve azzerare il conteggio (e quindi sopprimere la cella, sotto k=10).
    risposta_15 = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        giorno=date(2026, 7, 15),
    )
    cella_a_15 = next(cella for cella in risposta_15.celle if cella.place_id == "luogo-a")
    assert cella_a_15.disponibile is True
    assert cella_a_15.conteggio_tappe == N_PERSONE_SOPRA_SOGLIA
    assert risposta_15.giorno == date(2026, 7, 15)

    risposta_16 = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        giorno=date(2026, 7, 16),
    )
    cella_a_16 = next(cella for cella in risposta_16.celle if cella.place_id == "luogo-a")
    assert cella_a_16.disponibile is False
    assert cella_a_16.conteggio_tappe is None


def test_celle_flusso_filtro_ora_restringe_il_conteggio() -> None:
    # Le tappe di luogo-a sono tutte alle 10; un filtro su un'altra ora deve
    # svuotare la cella.
    risposta_10 = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        ora=10,
    )
    cella_a_10 = next(cella for cella in risposta_10.celle if cella.place_id == "luogo-a")
    assert cella_a_10.disponibile is True
    assert cella_a_10.conteggio_tappe == N_PERSONE_SOPRA_SOGLIA
    assert risposta_10.ora == 10

    risposta_9 = celle_flusso(
        periodo="2026-07",
        eventi_periodo=_eventi_flussi(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        ora=9,
    )
    cella_a_9 = next(cella for cella in risposta_9.celle if cella.place_id == "luogo-a")
    assert cella_a_9.disponibile is False
    assert cella_a_9.conteggio_tappe is None
