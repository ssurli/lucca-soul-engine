"""Test di `urban_memory.link`: rilettura da Postgres (`repo.get`) +
aggancio al grafo (`Neo4jMemoryLinker`), con un driver Neo4j FINTO (nessuna
connessione reale) per il grafo e — per la parte Postgres — il cluster
EFFIMERO reale (`tests/conftest.py`: `pg_repo`/`pg_dsn`), non un mock:
dimostra che `link_memory` legge DAVVERO il contributo persistito, mai uno
ricostruito in memoria.

Se Postgres 16 non è disponibile in questo ambiente, i test che dipendono
da `pg_repo`/`pg_dsn` sono SALTATI (`pytest.skip`), non falliti — i test di
`controprova` (nessun Postgres coinvolto) girano sempre.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _neo4j_fakes import FakeDriver
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import submit_contribution
from urban_memory.graph_link import Neo4jMemoryLinker
from urban_memory.link import _TARGET_INESISTENTE, controprova, link_memory


def _contributo(**overrides: object) -> MemoryContribution:
    defaults: dict[str, object] = {
        "id": "mem-link-1",
        "kind": MemoryKind.RACCONTO,
        "riguarda": ["liuteria-lucchese"],
        "contributor_id": "voce-di-verifica",
        "contributor_kind": PersonKind.CITTADINO,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": datetime.now(UTC),
        "curato": False,
    }
    defaults.update(overrides)
    return MemoryContribution(**defaults)


# ---------------------------------------------------------------------------
# controprova(linker) -> bool — nessun Postgres coinvolto
# ---------------------------------------------------------------------------


def test_controprova_supera_quando_il_target_non_esiste() -> None:
    driver = FakeDriver(mancanti=[_TARGET_INESISTENTE])
    linker = Neo4jMemoryLinker(driver)

    assert controprova(linker) is True


def test_controprova_non_crea_nessun_nodo() -> None:
    driver = FakeDriver(mancanti=[_TARGET_INESISTENTE])
    linker = Neo4jMemoryLinker(driver)

    controprova(linker)

    assert not any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)


def test_controprova_il_conteggio_e_invariato() -> None:
    driver = FakeDriver(mancanti=[_TARGET_INESISTENTE])
    linker = Neo4jMemoryLinker(driver)

    prima = linker.count_memoria()
    controprova(linker)
    dopo = linker.count_memoria()

    assert prima == dopo == (0, 0)


def test_controprova_usa_un_target_dichiaratamente_inesistente() -> None:
    """La controprova non dipende da un `mancanti` "fortunato" passato dal
    test: il contributo effimero che costruisce punta sempre allo stesso id
    dedicato (`_TARGET_INESISTENTE`) — qui lo verifichiamo lasciando il
    driver finto nel suo stato di default (nessun id dichiarato mancante:
    la verifica finta lo scoprirebbe comunque mancante se il driver la
    calcolasse dai dati, ma su questo fake la verifica dipende da `driver.
    mancanti`, quindi il chiamante di `controprova` DEVE passare un driver
    coerente con il contributo che essa stessa costruisce)."""
    driver = FakeDriver(mancanti=[_TARGET_INESISTENTE])
    linker = Neo4jMemoryLinker(driver)

    controprova(linker)

    # `count_memoria()` (chiamata prima e dopo da `controprova`) registra
    # anche lei una entry in `query_eseguite` (params=None): isoliamo la
    # query di VERIFICA per contenuto, non per posizione nell'elenco.
    query_di_verifica = [
        params for query, params in driver.query_eseguite if "AS mancanti" in query
    ]
    assert query_di_verifica == [{"riguarda": [_TARGET_INESISTENTE]}]


def test_controprova_fallisce_se_il_link_non_solleva() -> None:
    """Se (per un bug futuro) il linker smettesse di rifiutare un target
    inesistente, `controprova` deve tornare `False` — non alzare
    un'eccezione, non dare un falso "superata"."""
    driver = FakeDriver(mancanti=[])  # il target "esiste" per questo driver finto: il link riesce

    assert controprova(Neo4jMemoryLinker(driver)) is False


# ---------------------------------------------------------------------------
# link_memory(memory_id, dsn=..., linker=...) — Postgres effimero reale
# ---------------------------------------------------------------------------


def test_link_memory_id_inesistente_su_postgres_esce_con_errore(pg_repo, capsys) -> None:
    driver = FakeDriver()
    linker = Neo4jMemoryLinker(driver)

    with pytest.raises(SystemExit) as errore:
        link_memory("mem-mai-persistito", dsn=pg_repo._dsn, linker=linker)

    assert errore.value.code == 1
    catturato = capsys.readouterr().out
    assert "ERRORE" in catturato
    assert "non trovato" in catturato
    assert "verify" in catturato  # suggerisce il rimedio: prima persistilo
    # nessuna sessione Neo4j aperta: l'errore è stato rilevato PRIMA di
    # toccare il grafo.
    assert driver.query_eseguite == []


def test_link_memory_rilegge_da_postgres_il_contributo_reale(pg_repo) -> None:
    """IL CUORE DELLA RICHIESTA: il contributo agganciato è quello LETTO DAL
    DB (con tutti i suoi campi), mai un oggetto ricostruito in memoria da
    `link_memory` stessa."""
    contributo = _contributo(id="mem-link-esistente", riguarda=["liuteria-lucchese"])
    submit_contribution(pg_repo, contributo)

    driver = FakeDriver(mancanti=[])
    linker = Neo4jMemoryLinker(driver)

    link_memory(contributo.id, dsn=pg_repo._dsn, linker=linker)

    scritture = [
        params
        for query, params in driver.query_eseguite
        if params is not None and "MERGE (m:Memoria" not in query and "kind" in params
    ]
    assert scritture, (
        "la query di scrittura deve essere stata eseguita con i parametri del contributo"
    )
    assert scritture[-1]["id"] == contributo.id
    assert scritture[-1]["riguarda"] == ["liuteria-lucchese"]
    assert scritture[-1]["licenza"] == contributo.licenza


def test_link_memory_target_inesistente_esce_con_errore_e_non_scrive(pg_repo) -> None:
    contributo = _contributo(id="mem-link-orfano", riguarda=["bottega-fantasma"])
    submit_contribution(pg_repo, contributo)

    driver = FakeDriver(mancanti=["bottega-fantasma"])
    linker = Neo4jMemoryLinker(driver)

    with pytest.raises(SystemExit) as errore:
        link_memory(contributo.id, dsn=pg_repo._dsn, linker=linker)

    assert errore.value.code == 1
    # Nessun nodo :Memoria orfano: la query di scrittura non è mai partita.
    assert not any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)


def test_link_memory_stampa_il_conteggio_prima_e_dopo(pg_repo, capsys) -> None:
    contributo = _contributo(id="mem-link-conteggio", riguarda=["liuteria-lucchese"])
    submit_contribution(pg_repo, contributo)

    driver = FakeDriver(mancanti=[])
    linker = Neo4jMemoryLinker(driver)

    link_memory(contributo.id, dsn=pg_repo._dsn, linker=linker)

    catturato = capsys.readouterr().out
    assert "Prima dell'aggancio" in catturato
    assert "Dopo l'aggancio" in catturato
    assert "0 nodo/i :Memoria" in catturato  # prima: grafo finto vuoto
    assert "1 nodo/i :Memoria" in catturato  # dopo: un :Memoria creato
    assert "OK: aggancio al grafo riuscito." in catturato


def test_link_memory_su_contributo_gia_curato_lo_aggancia_comunque(pg_repo) -> None:
    """`link_memory` non richiede `curato=True`: aggancia qualunque
    contributo REALMENTE persistito, indipendentemente dallo stato di
    curatela (che riguarda la pubblicazione, non l'aggancio al grafo)."""
    contributo = _contributo(id="mem-link-curato", riguarda=["liuteria-lucchese"])
    submit_contribution(pg_repo, contributo)
    pg_repo.curate(contributo.id)

    driver = FakeDriver(mancanti=[])
    linker = Neo4jMemoryLinker(driver)

    link_memory(contributo.id, dsn=pg_repo._dsn, linker=linker)

    assert any("MERGE (m:Memoria" in q for q, _ in driver.query_eseguite)
