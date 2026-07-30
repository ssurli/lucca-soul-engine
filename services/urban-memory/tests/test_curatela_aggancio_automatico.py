"""Test dell'invariante "curato tira aggancio" (`docs/ENGINE_INVARIANTS.md`
§11-B, Fase 3): `curate_contribution`/`publish_pending`, quando ricevono un
`linker`, innescano `link_to_graph` AUTOMATICAMENTE subito dopo
`curato=True` — mai un secondo passo separato che qualcuno può dimenticare.
"Curato ma non agganciato" resta un transitorio interno alla chiamata, mai
uno stato di riposo: l'esito è sempre `MemoryLinkState.AGGANCIATO` o
`MemoryLinkState.AGGANCIO_FALLITO` (un'attesa RECUPERABILE, mai un vicolo
cieco — vedi `retry_link_contribution`).

Due livelli di test, come nel resto del modulo:

- Sullo STESSO `Protocol MemoryRepository`, parametrizzato su ENTRAMBE le
  implementazioni (`any_memory_repository`, da `tests/conftest.py`): il seam
  (`urban_memory.service._innesca_aggancio`) opera solo attraverso il
  Protocol, quindi la transizione di stato deve comportarsi IDENTICA su
  `InMemoryMemoryRepository` e `PostgresMemoryRepository` — con `linker`
  finti (funzioni Python semplici, nessun driver Neo4j coinvolto: la logica
  di dominio non ha bisogno di un grafo vero per essere testata).
- Contro un driver Neo4j FINTO vero e proprio (`_neo4j_fakes.FakeDriver` +
  `Neo4jMemoryLinker`, stesso helper di `test_graph_link.py`): verifica che
  gli edge `:RIGUARDA` siano DAVVERO scritti nel cammino felice, e DAVVERO
  assenti (nessun aggancio parziale) quando il grafo è irraggiungibile.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _neo4j_fakes import FakeDriver
from contracts import MemoryContribution, MemoryKind, MemoryLinkState, PersonKind
from urban_memory import (
    InMemoryMemoryRepository,
    MemoryRepository,
    UrbanMemoryError,
    curate_contribution,
    pending_contributions,
    retry_link_contribution,
    submit_contribution,
)
from urban_memory.graph_link import MemoryLinkError, Neo4jMemoryLinker


def _contributo(**overrides: object) -> MemoryContribution:
    defaults: dict[str, object] = {
        "id": "mem-aggancio-1",
        "kind": MemoryKind.MESTIERE,
        "testo": "Il mestiere del liutaio, tramandato da tre generazioni.",
        "riguarda": ["liuteria-lucchese"],
        "contributor_id": "voce-del-borgo",
        "contributor_kind": PersonKind.CITTADINO,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": datetime(2026, 7, 20, 9, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return MemoryContribution(**defaults)


# ---------------------------------------------------------------------------
# Livello di dominio — linker FINTI (funzioni Python), su ENTRAMBE le
# implementazioni di MemoryRepository (any_memory_repository).
# ---------------------------------------------------------------------------


def test_curate_senza_linker_stato_aggancio_resta_none(
    any_memory_repository: MemoryRepository,
) -> None:
    """Comportamento IDENTICO a prima di questa automazione quando
    `linker=None` (default): nessun aggancio tentato."""
    repo = any_memory_repository
    submit_contribution(repo, _contributo())

    curato = curate_contribution(repo, "mem-aggancio-1")

    assert curato.curato is True
    assert curato.stato_aggancio is None


def test_curate_con_linker_riuscito_imposta_agganciato(
    any_memory_repository: MemoryRepository,
) -> None:
    repo = any_memory_repository
    submit_contribution(repo, _contributo())
    chiamate: list[str] = []

    def linker_che_riesce(contribution: MemoryContribution) -> None:
        chiamate.append(contribution.id)

    curato = curate_contribution(repo, "mem-aggancio-1", linker=linker_che_riesce)

    assert curato.curato is True
    assert curato.stato_aggancio == MemoryLinkState.AGGANCIATO
    assert chiamate == ["mem-aggancio-1"]
    # Persistito nel repository, non solo nel valore di ritorno:
    riletto = repo.get("mem-aggancio-1")
    assert riletto is not None
    assert riletto.stato_aggancio == MemoryLinkState.AGGANCIATO


def test_curate_con_linker_fallito_imposta_aggancio_fallito_ma_resta_curato(
    any_memory_repository: MemoryRepository,
) -> None:
    """IL CUORE DELL'INVARIANTE: un aggancio fallito NON deve mai produrre un
    curato-orfano SILENZIOSO — lo stato lo dice esplicitamente
    (`AGGANCIO_FALLITO`) — e non deve sollevare un'eccezione che interrompe
    `curate_contribution`: la revisione umana è avvenuta ed è valida
    indipendentemente dal grafo."""
    repo = any_memory_repository
    submit_contribution(repo, _contributo())

    def linker_che_fallisce(contribution: MemoryContribution) -> None:
        raise MemoryLinkError("grafo irraggiungibile (simulato)")

    curato = curate_contribution(repo, "mem-aggancio-1", linker=linker_che_fallisce)

    assert curato.curato is True  # la curatela resta valida
    assert curato.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO
    # Non "torna pending": è curato, semplicemente non ancora agganciato.
    assert "mem-aggancio-1" not in [c.id for c in pending_contributions(repo)]
    # Visibile nella coda di retry — MAI un fallimento silenzioso.
    falliti = repo.list_aggancio_fallito()
    assert [c.id for c in falliti] == ["mem-aggancio-1"]


def test_curate_con_linker_fallito_non_solleva_memory_link_error(
    any_memory_repository: MemoryRepository,
) -> None:
    """`MemoryLinkError` è CATTURATA, non propagata: `aggancio_fallito` è un
    esito registrato, non un errore che interrompe la chiamata."""
    repo = any_memory_repository
    submit_contribution(repo, _contributo())

    def linker_che_fallisce(contribution: MemoryContribution) -> None:
        raise MemoryLinkError("grafo irraggiungibile (simulato)")

    # Nessuna eccezione qui: se ne solleva una, il test fallisce di suo.
    curate_contribution(repo, "mem-aggancio-1", linker=linker_che_fallisce)


def test_retry_link_contribution_su_aggancio_fallito_diventa_agganciato(
    any_memory_repository: MemoryRepository,
) -> None:
    """Il percorso di RECUPERO: quando l'aggancio torna a funzionare, un
    retry esplicito porta `AGGANCIO_FALLITO -> AGGANCIATO` — mai un vicolo
    cieco."""
    repo = any_memory_repository
    submit_contribution(repo, _contributo())
    stato = {"aura_giu": True}

    def linker_intermittente(contribution: MemoryContribution) -> None:
        if stato["aura_giu"]:
            raise MemoryLinkError("grafo irraggiungibile (simulato)")

    fallito = curate_contribution(repo, "mem-aggancio-1", linker=linker_intermittente)
    assert fallito.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO

    stato["aura_giu"] = False  # Aura torna raggiungibile
    riprovato = retry_link_contribution(repo, "mem-aggancio-1", linker=linker_intermittente)

    assert riprovato.stato_aggancio == MemoryLinkState.AGGANCIATO
    riletto = repo.get("mem-aggancio-1")
    assert riletto is not None
    assert riletto.stato_aggancio == MemoryLinkState.AGGANCIATO
    assert repo.list_aggancio_fallito() == []  # uscito dalla coda di retry


def test_retry_link_contribution_su_gia_agganciato_resta_agganciato(
    any_memory_repository: MemoryRepository,
) -> None:
    """Rieseguire il retry su un contributo GIÀ agganciato è innocuo
    (`link_to_graph` è idempotente, `MERGE` non duplica nulla) — comodo per
    un retry "a tappeto" senza dover prima controllare lo stato."""
    repo = any_memory_repository
    submit_contribution(repo, _contributo())

    def linker_che_riesce(contribution: MemoryContribution) -> None:
        return None

    curate_contribution(repo, "mem-aggancio-1", linker=linker_che_riesce)
    riprovato = retry_link_contribution(repo, "mem-aggancio-1", linker=linker_che_riesce)

    assert riprovato.stato_aggancio == MemoryLinkState.AGGANCIATO


def test_retry_link_contribution_su_non_curato_solleva_errore_di_dominio(
    any_memory_repository: MemoryRepository,
) -> None:
    repo = any_memory_repository
    submit_contribution(repo, _contributo())  # MAI curato

    with pytest.raises(UrbanMemoryError, match="non è curato"):
        retry_link_contribution(repo, "mem-aggancio-1", linker=lambda c: None)


def test_retry_link_contribution_id_sconosciuto_solleva_keyerror(
    any_memory_repository: MemoryRepository,
) -> None:
    repo = any_memory_repository
    with pytest.raises(KeyError):
        retry_link_contribution(repo, "non-esiste-mai", linker=lambda c: None)


def test_publish_pending_eredita_linker_come_alias() -> None:
    """`publish_pending` È `curate_contribution` (stesso identico oggetto
    funzione): eredita `linker` esattamente come eredita `target_checker`."""
    from urban_memory import publish_pending

    assert publish_pending is curate_contribution


# ---------------------------------------------------------------------------
# Livello del grafo — driver Neo4j FINTO vero e proprio (stesso helper di
# test_graph_link.py): dimostra che gli edge :RIGUARDA sono DAVVERO scritti
# (o DAVVERO assenti) sul grafo, non solo che lo stato di dominio cambia.
# ---------------------------------------------------------------------------


def test_curate_con_linker_reale_scrive_gli_edge_riguarda() -> None:
    repo = InMemoryMemoryRepository()
    submit_contribution(repo, _contributo(riguarda=["liuteria-lucchese", "ceramica-lucca"]))

    driver = FakeDriver(mancanti=[])  # tutti i target "esistono" nel grafo finto
    linker = Neo4jMemoryLinker(driver)

    curato = curate_contribution(
        repo,
        "mem-aggancio-1",
        target_checker=linker.targets_mancanti,
        linker=linker.link,
    )

    assert curato.stato_aggancio == MemoryLinkState.AGGANCIATO
    assert any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)
    memorie, relazioni = linker.count_memoria()
    assert memorie == 1
    assert relazioni == 2  # un RIGUARDA per ogni id di riguarda


def test_curate_con_grafo_irraggiungibile_non_scrive_nessun_edge_parziale() -> None:
    """Il target_checker (eseguito PRIMA, su un grafo raggiungibile) supera
    la verifica; è la SCRITTURA (`linker`) a incontrare un grafo diventato
    irraggiungibile nel frattempo — la sequenza che `docs/STATE_MACHINE.md`
    §3 descrive come "seconda lettura nel tempo". Nessun nodo :Memoria
    orfano, nessun edge parziale: il contributo resta curato, in attesa di
    retry."""
    repo = InMemoryMemoryRepository()
    submit_contribution(repo, _contributo(riguarda=["liuteria-lucchese"]))

    def target_checker_ok(riguarda: list[str]) -> list[str]:
        return []  # il pre-check, un istante prima, trova tutto a posto

    driver_giu = FakeDriver(session_error=ConnectionError("Aura non raggiungibile (simulato)"))
    linker_giu = Neo4jMemoryLinker(driver_giu)

    curato = curate_contribution(
        repo,
        "mem-aggancio-1",
        target_checker=target_checker_ok,
        linker=linker_giu.link,
    )

    assert curato.curato is True
    assert curato.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO
    assert driver_giu.query_eseguite == []  # nessuna query: la sessione non si è mai aperta
    assert not any("MERGE (m:Memoria" in q for q, _ in driver_giu.query_eseguite)


def test_retry_dopo_grafo_irraggiungibile_scrive_gli_edge_quando_torna_su() -> None:
    """Ciclo COMPLETO: curatela con Aura giù -> aggancio_fallito -> Aura
    torna raggiungibile -> retry -> edge scritti DAVVERO."""
    repo = InMemoryMemoryRepository()
    submit_contribution(repo, _contributo(riguarda=["liuteria-lucchese"]))

    driver_giu = FakeDriver(session_error=ConnectionError("Aura non raggiungibile (simulato)"))
    linker_giu = Neo4jMemoryLinker(driver_giu)
    fallito = curate_contribution(
        repo,
        "mem-aggancio-1",
        target_checker=lambda riguarda: [],
        linker=linker_giu.link,
    )
    assert fallito.stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO

    driver_su = FakeDriver(mancanti=[])  # una nuova connessione: Aura è tornata raggiungibile
    linker_su = Neo4jMemoryLinker(driver_su)
    riprovato = retry_link_contribution(repo, "mem-aggancio-1", linker=linker_su.link)

    assert riprovato.stato_aggancio == MemoryLinkState.AGGANCIATO
    memorie, relazioni = linker_su.count_memoria()
    assert memorie == 1
    assert relazioni == 1
