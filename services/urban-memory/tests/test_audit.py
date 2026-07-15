"""Test di `urban_memory.audit`: verifica dei target dei contributi CURATI,
con un driver Neo4j FINTO (nessuna connessione reale) e — per la parte
Postgres — il cluster EFFIMERO reale (`tests/conftest.py`: `pg_repo`).

Copre il criterio esplicito: "un curato invalido nel DB -> riportato e
exit 1; tutti validi -> exit 0" — separando la funzione pura `audit()`
(quali contributi sono validi/invalidi) dalla decisione di codice di
uscita (`_stampa_report`, testabile senza alcun `.env`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from _neo4j_fakes import FakeDriver
from contracts import MemoryContribution, MemoryKind, PersonKind
from urban_memory import submit_contribution
from urban_memory.audit import _stampa_report, audit
from urban_memory.graph_link import Neo4jMemoryLinker


def _contributo(**overrides: object) -> MemoryContribution:
    defaults: dict[str, object] = {
        "id": "mem-audit-1",
        "kind": MemoryKind.RACCONTO,
        "riguarda": ["liuteria-lucchese"],
        "contributor_id": "voce-di-controllo",
        "contributor_kind": PersonKind.CITTADINO,
        "consenso": True,
        "licenza": "CC-BY-SA-4.0",
        "creato_il": datetime.now(UTC),
        "curato": False,
    }
    defaults.update(overrides)
    return MemoryContribution(**defaults)


# ---------------------------------------------------------------------------
# audit(repo, target_checker) — Postgres effimero reale + driver Neo4j finto
# ---------------------------------------------------------------------------


def test_audit_tutti_validi(pg_repo) -> None:
    contributo = _contributo(id="mem-valido")
    submit_contribution(pg_repo, contributo)
    pg_repo.curate(contributo.id)  # curatela SENZA target_checker: il test simula un DB reale

    driver = FakeDriver(mancanti=[])  # tutti i target "esistono" per questo grafo finto
    linker = Neo4jMemoryLinker(driver)

    validi, invalidi = audit(pg_repo, linker.targets_mancanti)

    assert [c.id for c in validi] == ["mem-valido"]
    assert invalidi == []


def test_audit_rileva_un_curato_con_target_mancante(pg_repo) -> None:
    """IL CUORE DELLA RICHIESTA: il bug reale (curato=True con
    riguarda=['bottega-liuteria-1'], un id inesistente) è esattamente
    questo scenario — un contributo curato PRIMA che `target_checker`
    esistesse. `audit` lo scova, non lo corregge."""
    contributo = _contributo(id="mem-orfano", riguarda=["bottega-liuteria-1"])
    submit_contribution(pg_repo, contributo)
    pg_repo.curate(contributo.id)  # curatela SENZA target_checker: riproduce il bug storico

    driver = FakeDriver(mancanti=["bottega-liuteria-1"])
    linker = Neo4jMemoryLinker(driver)

    validi, invalidi = audit(pg_repo, linker.targets_mancanti)

    assert validi == []
    assert len(invalidi) == 1
    contributo_invalido, mancanti = invalidi[0]
    assert contributo_invalido.id == "mem-orfano"
    assert mancanti == ["bottega-liuteria-1"]


def test_audit_ignora_i_non_curati(pg_repo) -> None:
    submit_contribution(pg_repo, _contributo(id="mem-pending", riguarda=["bottega-liuteria-1"]))
    # NON curato: audit legge SOLO curato=True (list_curated), quindi
    # nemmeno lo vede — coerente con "il conferimento non deve mai
    # dipendere dal grafo": un pending non è ancora sotto esame.

    driver = FakeDriver(mancanti=["bottega-liuteria-1"])
    linker = Neo4jMemoryLinker(driver)

    validi, invalidi = audit(pg_repo, linker.targets_mancanti)

    assert validi == []
    assert invalidi == []


def test_audit_con_curati_misti_conta_correttamente(pg_repo) -> None:
    creato_il = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
    contributo_valido = _contributo(
        id="mem-ok", riguarda=["liuteria-lucchese"], creato_il=creato_il
    )
    contributo_invalido = _contributo(
        id="mem-rotto", riguarda=["bottega-liuteria-1"], creato_il=creato_il
    )
    submit_contribution(pg_repo, contributo_valido)
    submit_contribution(pg_repo, contributo_invalido)
    pg_repo.curate("mem-ok")
    pg_repo.curate("mem-rotto")

    driver = FakeDriver(mancanti=["bottega-liuteria-1"])
    linker = Neo4jMemoryLinker(driver)

    validi, invalidi = audit(pg_repo, linker.targets_mancanti)

    assert [c.id for c in validi] == ["mem-ok"]
    assert [c.id for c, _ in invalidi] == ["mem-rotto"]


# ---------------------------------------------------------------------------
# _stampa_report(validi, invalidi) -> int — nessun I/O, testabile in
# isolamento: è qui che si decide "exit 1"/"exit 0".
# ---------------------------------------------------------------------------


def test_stampa_report_ritorna_1_se_almeno_un_invalido(capsys) -> None:
    contributo = _contributo(id="mem-x")

    codice = _stampa_report([], [(contributo, ["bottega-liuteria-1"])])

    assert codice == 1
    catturato = capsys.readouterr().out
    assert "mem-x" in catturato
    assert "bottega-liuteria-1" in catturato
    assert "AUDIT FALLITO" in catturato


def test_stampa_report_ritorna_0_se_tutto_valido(capsys) -> None:
    contributo = _contributo(id="mem-y")

    codice = _stampa_report([contributo], [])

    assert codice == 0
    catturato = capsys.readouterr().out
    assert "AUDIT OK" in catturato


def test_stampa_report_non_stampa_testo_ne_media_uri_ne_contributor_id(capsys) -> None:
    """Nessun testo/PII: solo id, kind, riguarda, mancanti — mai il payload
    del contributo (stesso principio di `urban_memory.service`)."""
    contributo = _contributo(
        id="mem-privato",
        testo="Segreto: la nonna raccontava della bottega del nonno.",
        contributor_id="pseudonimo-riservato",
        media_uri="https://esempio.invalid/foto-privata.jpg",
    )

    _stampa_report([], [(contributo, ["bottega-liuteria-1"])])

    catturato = capsys.readouterr().out
    assert contributo.testo not in catturato
    assert contributo.contributor_id not in catturato
    assert contributo.media_uri not in catturato
