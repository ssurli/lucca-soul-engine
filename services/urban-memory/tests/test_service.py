"""Test dei vincoli non negoziabili di `urban_memory.service`.

Copre i criteri d'accettazione della Wave 2 (CLAUDE.md,
docs/DATA_CONTRACTS.md §4): nessun contributo persiste senza consenso
esplicito E licenza tracciata; niente auto-pubblicazione; `contributor_id` è
uno pseudonimo obbligatorio; solo i contributi curati sono pubblici.
"""

from __future__ import annotations

import inspect

import pytest
from contracts import MemoryKind
from urban_memory import (
    ConsentRequiredError,
    InMemoryMemoryRepository,
    LicenseRequiredError,
    PseudonymRequiredError,
    contributions_for_place,
    curate_contribution,
    pending_contributions,
    submit_contribution,
)


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


# --- consenso: NESSUNA eccezione --------------------------------------------


def test_submit_senza_consenso_rifiutato(repo, valid_contribution_factory) -> None:
    contributo = valid_contribution_factory(consenso=False)
    with pytest.raises(ConsentRequiredError):
        submit_contribution(repo, contributo)


def test_submit_senza_consenso_non_lascia_traccia(repo, valid_contribution_factory) -> None:
    contributo = valid_contribution_factory(consenso=False)
    with pytest.raises(ConsentRequiredError):
        submit_contribution(repo, contributo)
    assert pending_contributions(repo) == []
    assert contributions_for_place(repo, "bottega-liuteria-1") == []


# --- licenza: sempre tracciata ed esplicita ---------------------------------


@pytest.mark.parametrize("licenza", ["   ", "\t\n"])
def test_submit_senza_licenza_rifiutato(repo, valid_contribution_factory, licenza) -> None:
    # NOTA: `licenza=""` non arriva nemmeno qui: `MemoryContribution.licenza`
    # ha già `Field(min_length=1)` nel contratto (packages/contracts), quindi
    # una stringa VUOTA è rifiutata prima, alla costruzione dell'oggetto (vedi
    # `test_contratto_rifiuta_licenza_completamente_vuota`). Qui copriamo il
    # caso che il contratto da solo non intercetta: whitespace-only, che
    # supera `min_length=1` ma è comunque "nessuna licenza" nella sostanza.
    contributo = valid_contribution_factory(licenza=licenza)
    with pytest.raises(LicenseRequiredError):
        submit_contribution(repo, contributo)


def test_contratto_rifiuta_licenza_completamente_vuota(valid_contribution_factory) -> None:
    """Doppio strato di difesa: una `licenza` vuota è già rifiutata dal
    contratto stesso (`Field(min_length=1)`), prima ancora che
    `submit_contribution` possa intervenire."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        valid_contribution_factory(licenza="")


def test_submit_con_licenza_valida_non_solleva(repo, valid_contribution_factory) -> None:
    contributo = valid_contribution_factory(licenza="CC-BY-SA-4.0")
    persistito = submit_contribution(repo, contributo)
    assert persistito.licenza == "CC-BY-SA-4.0"


# --- pseudonimo obbligatorio -------------------------------------------------


@pytest.mark.parametrize("contributor_id", ["", "   ", "\t"])
def test_submit_senza_pseudonimo_rifiutato(
    repo, valid_contribution_factory, contributor_id
) -> None:
    contributo = valid_contribution_factory(contributor_id=contributor_id)
    with pytest.raises(PseudonymRequiredError):
        submit_contribution(repo, contributo)


# --- niente auto-pubblicazione: curato=False forzato alla creazione --------


def test_submit_forza_curato_false_anche_se_in_ingresso_e_true(
    repo, valid_contribution_factory
) -> None:
    contributo = valid_contribution_factory(curato=True)  # tentativo di auto-pubblicazione
    persistito = submit_contribution(repo, contributo)
    assert persistito.curato is False
    assert contributions_for_place(repo, "bottega-liuteria-1") == []


# --- ciclo di vita: submit -> pending -> curate -> pubblico -----------------


def test_contributo_valido_non_compare_finche_non_curato(repo, valid_contribution_factory) -> None:
    contributo = valid_contribution_factory()
    persistito = submit_contribution(repo, contributo)
    assert persistito.curato is False
    assert contributions_for_place(repo, "bottega-liuteria-1") == []
    assert persistito.id in [c.id for c in pending_contributions(repo)]


def test_curate_contribution_pubblica_il_contributo(repo, valid_contribution_factory) -> None:
    contributo = valid_contribution_factory()
    submit_contribution(repo, contributo)

    curato = curate_contribution(repo, contributo.id)

    assert curato.curato is True
    pubblicati = contributions_for_place(repo, "bottega-liuteria-1")
    assert [c.id for c in pubblicati] == [contributo.id]
    assert contributo.id not in [c.id for c in pending_contributions(repo)]


def test_curate_id_sconosciuto_solleva_keyerror(repo) -> None:
    with pytest.raises(KeyError):
        curate_contribution(repo, "non-esiste")


# --- get_curated filtra per place_id E per curato ---------------------------


def test_get_curated_filtra_per_place_id(repo, valid_contribution_factory) -> None:
    a = valid_contribution_factory(id="mem-a", riguarda=["luogo-a"])
    b = valid_contribution_factory(id="mem-b", riguarda=["luogo-b"])
    submit_contribution(repo, a)
    submit_contribution(repo, b)
    curate_contribution(repo, "mem-a")
    curate_contribution(repo, "mem-b")

    solo_a = contributions_for_place(repo, "luogo-a")
    assert [c.id for c in solo_a] == ["mem-a"]


def test_get_curated_esclude_i_non_curati(repo, valid_contribution_factory) -> None:
    curato = valid_contribution_factory(id="mem-curato", riguarda=["luogo-x"])
    non_curato = valid_contribution_factory(id="mem-pending", riguarda=["luogo-x"])
    submit_contribution(repo, curato)
    submit_contribution(repo, non_curato)
    curate_contribution(repo, "mem-curato")

    risultato = contributions_for_place(repo, "luogo-x")
    assert [c.id for c in risultato] == ["mem-curato"]


# --- round-trip end-to-end ---------------------------------------------------


def test_roundtrip_racconto_consenso_licenza_cc_by_sa(repo, valid_contribution_factory) -> None:
    """Un MemoryContribution valido (kind RACCONTO, consenso=True, licenza
    CC-BY-SA-4.0) attraversa submit -> curate -> get_curated."""
    contributo = valid_contribution_factory(
        id="mem-roundtrip",
        kind=MemoryKind.RACCONTO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        riguarda=["bottega-liuteria-1"],
    )

    submit_contribution(repo, contributo)
    assert contributions_for_place(repo, "bottega-liuteria-1") == []  # non ancora curato

    curate_contribution(repo, "mem-roundtrip")
    pubblicati = contributions_for_place(repo, "bottega-liuteria-1")

    assert len(pubblicati) == 1
    assert pubblicati[0].id == "mem-roundtrip"
    assert pubblicati[0].kind == MemoryKind.RACCONTO
    assert pubblicati[0].curato is True
    assert pubblicati[0].licenza == "CC-BY-SA-4.0"


# --- nessuna PII/contenuto loggato -------------------------------------------


def test_submit_non_stampa_il_contenuto_del_contributo(
    repo, valid_contribution_factory, capsys
) -> None:
    contributo = valid_contribution_factory(
        testo="Segreto: la nonna raccontava della bottega del nonno.",
        contributor_id="pseudonimo-riservato",
    )
    submit_contribution(repo, contributo)
    catturato = capsys.readouterr()
    assert contributo.testo not in catturato.out
    assert contributo.contributor_id not in catturato.out
    assert catturato.out == ""


def test_service_non_chiama_print_ne_logging() -> None:
    """Test-guard (come `test_scoring_non_usa_partner_id_ne_prezzo` in
    experience-engine): nessuna riga ESEGUITA di `urban_memory.service` deve
    chiamare `print()` o importare/usare `logging`. Ispeziona l'AST (non la
    sorgente grezza, che includerebbe anche le parole nella docstring che
    SPIEGA la regola) — il modo più sicuro di garantire che il contenuto di
    un contributo non finisca mai in un log è non chiamarli affatto."""
    import ast

    import urban_memory.service as service_module

    albero = ast.parse(inspect.getsource(service_module))
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            assert not any(alias.name.split(".")[0] == "logging" for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.module is None or nodo.module.split(".")[0] != "logging"
        elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id != "print"
