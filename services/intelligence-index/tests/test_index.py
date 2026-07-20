"""Test di integrazione di `intelligence_index.index.calcola_index` — la
funzione che assembla `UrbanIntelligenceIndex`, PURA (nessun database),
copre: il gate k=10 applicato centralmente, il filtro per periodo, e che
`soddisfazione` resta sempre `None` (nessuna fonte reale oggi)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from contracts import BehaviorEvent, ExperienceNode, MemoryContribution, MemoryKind, PersonKind
from intelligence_index.index import calcola_index
from intelligence_index.soglia import SOGLIA_MINIMA_PERSONE, DatiInsufficientiError

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
    indicatore che dipende da questi eventi."""
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


def _memoria(
    id: str, giorno: int = 10, curato: bool = True, contributor_id: str = "cittadino-1"
) -> MemoryContribution:
    return MemoryContribution(
        id=id,
        kind=MemoryKind.RACCONTO,
        testo="un racconto",
        riguarda=["luogo-a"],
        contributor_id=contributor_id,
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, giorno, tzinfo=UTC),
        curato=curato,
    )


def _memorie_sopra_soglia(
    n: int = N_PERSONE_SOPRA_SOGLIA, giorno: int = 10, curato: bool = True
) -> list[MemoryContribution]:
    """`n` `MemoryContribution`, ciascuna da un `contributor_id` DISTINTO,
    tutte dentro luglio 2026 — popolazione sopra k=10 per `contributi_memoria`
    (stesso principio di `_eventi_sopra_soglia` per gli altri indicatori)."""
    return [
        _memoria(f"m{i}", giorno=giorno, curato=curato, contributor_id=f"c{i}")
        for i in range(n)
    ]


def test_calcola_index_produce_tutti_e_8_i_campi_sopra_soglia() -> None:
    indice = calcola_index(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=_memorie_sopra_soglia(),
    )
    assert indice.periodo == "2026-07"
    assert indice.tempo_medio_esperienza_min == 60.0
    assert 0.0 <= indice.coinvolgimento <= 1.0
    assert indice.soddisfazione is None
    assert 0.0 <= indice.tasso_ritorno <= 1.0
    assert 0.0 <= indice.nuovi_percorsi <= 1.0
    assert 0.0 <= indice.attivazione_locale <= 1.0
    assert 0.0 <= indice.distribuzione_flussi <= 1.0
    assert indice.contributi_memoria == N_PERSONE_SOPRA_SOGLIA


def test_calcola_index_soddisfazione_e_sempre_none() -> None:
    # Nessuna fonte reale oggi (nessuna recensione/survey in prodotto): MAI
    # un valore stimato, qualunque sia l'input.
    indice = calcola_index(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=_memorie_sopra_soglia(),
    )
    assert indice.soddisfazione is None


def test_calcola_index_solleva_sotto_la_soglia_k10() -> None:
    # Solo 3 persone (sotto k=10): MAI un numero pubblicato.
    eventi_pochi = [
        BehaviorEvent(
            person_id=f"p{i}",
            tipo="stop",
            experience_id="e-a",
            ts=datetime(2026, 7, 15, tzinfo=UTC),
        )
        for i in range(3)
    ]
    with pytest.raises(DatiInsufficientiError):
        calcola_index(
            periodo="2026-07",
            eventi=eventi_pochi,
            esperienze_per_id=CATALOGO,
            grado_semantico=GRADO_SEMANTICO,
            n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
            non_connesse_a_inizio_periodo=NON_CONNESSE,
            itinerari_periodo=[],
            memorie=[],
        )


def test_calcola_index_molti_contributi_da_pochi_contributor_solleva_il_gate() -> None:
    # Caso di re-identificazione più rilevante secondo ethics-guardian: NON
    # "pochi contributi" in assoluto (il conteggio grezzo qui è alto, 50),
    # ma MOLTI contributi concentrati su un SOLO/pochi contributor_id — una
    # persona molto attiva è identificabile tanto quanto una popolazione
    # piccola, indipendentemente da quanto alto sia il conteggio grezzo.
    memorie_concentrate = [
        _memoria(f"m{i}", contributor_id=f"c{i % 3}")  # solo 3 contributor_id distinti
        for i in range(50)
    ]
    with pytest.raises(DatiInsufficientiError) as exc_info:
        calcola_index(
            periodo="2026-07",
            eventi=_eventi_sopra_soglia(),
            esperienze_per_id=CATALOGO,
            grado_semantico=GRADO_SEMANTICO,
            n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
            non_connesse_a_inizio_periodo=NON_CONNESSE,
            itinerari_periodo=[],
            memorie=memorie_concentrate,
        )
    assert exc_info.value.contesto == "contributi_memoria"


def test_calcola_index_filtra_gli_eventi_fuori_dal_periodo() -> None:
    eventi_fuori_periodo = [
        BehaviorEvent(
            person_id=f"p{i}",
            tipo="stop",
            experience_id="e-a",
            ts=datetime(2026, 6, 15, tzinfo=UTC),  # GIUGNO, non luglio
        )
        for i in range(N_PERSONE_SOPRA_SOGLIA)
    ]
    # Nessun evento cade in luglio: la popolazione di luglio è vuota (0
    # persone), quindi il gate k=10 deve rifiutare esplicitamente, non
    # calcolare un valore su dati di un mese diverso.
    with pytest.raises(DatiInsufficientiError):
        calcola_index(
            periodo="2026-07",
            eventi=eventi_fuori_periodo,
            esperienze_per_id=CATALOGO,
            grado_semantico=GRADO_SEMANTICO,
            n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
            non_connesse_a_inizio_periodo=NON_CONNESSE,
            itinerari_periodo=[],
            memorie=[],
        )


def test_calcola_index_esclude_memoria_di_un_altro_mese() -> None:
    # N_PERSONE_SOPRA_SOGLIA contributi DISTINTI dentro il periodo (luglio) +
    # un contributo fuori periodo (agosto): la popolazione di luglio resta
    # sopra k=10 da sola, cosi' il test isola davvero "il filtro esclude
    # agosto" dal gate k=10 (altrimenti un solo contributo in periodo
    # solleverebbe DatiInsufficientiError per un motivo diverso da quello
    # che il test vuole verificare).
    memoria_agosto = MemoryContribution(
        id="m-agosto",
        kind=MemoryKind.RACCONTO,
        testo="un racconto",
        riguarda=["luogo-a"],
        contributor_id="cittadino-agosto",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 8, 1, tzinfo=UTC),
        curato=True,
    )
    indice = calcola_index(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=[*_memorie_sopra_soglia(), memoria_agosto],
    )
    assert indice.contributi_memoria == N_PERSONE_SOPRA_SOGLIA


def test_calcola_index_conta_i_contributi_pending_e_curati_del_periodo() -> None:
    # Il committente ha respinto il filtro su curato=True: contributi_memoria
    # deve contare la PARTECIPAZIONE (tutti i contributi del periodo), non
    # l'APPROVAZIONE — un contributo pending non è "assenza di partecipazione".
    # N_PERSONE_SOPRA_SOGLIA contributor_id DISTINTI, misti curato/pending,
    # per restare sopra il gate k=10 (ora applicato anche a contributi_memoria).
    memorie = [
        _memoria(f"m-curato-{i}", curato=True, contributor_id=f"c-curato-{i}")
        for i in range(N_PERSONE_SOPRA_SOGLIA - 3)
    ] + [
        _memoria(f"m-pending-{i}", curato=False, contributor_id=f"c-pending-{i}")
        for i in range(3)
    ]
    indice = calcola_index(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=memorie,
    )
    assert indice.contributi_memoria == N_PERSONE_SOPRA_SOGLIA


def test_calcola_index_nessun_itinerario_non_solleva_il_gate_di_nuovi_percorsi() -> None:
    # Buco nei dati noto (vedi README/indicatori.nuovi_percorsi): passare
    # itinerari_periodo=[] non deve far fallire l'intero calcolo.
    indice = calcola_index(
        periodo="2026-07",
        eventi=_eventi_sopra_soglia(),
        esperienze_per_id=CATALOGO,
        grado_semantico=GRADO_SEMANTICO,
        n_luoghi_disponibili=N_LUOGHI_DISPONIBILI,
        non_connesse_a_inizio_periodo=NON_CONNESSE,
        itinerari_periodo=[],
        memorie=_memorie_sopra_soglia(),
    )
    assert indice.nuovi_percorsi == 0.0
