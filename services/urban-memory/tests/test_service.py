"""Test dei vincoli non negoziabili di `urban_memory.service`.

Copre i criteri d'accettazione della Wave 2 (CLAUDE.md,
docs/DATA_CONTRACTS.md §4): nessun contributo persiste senza consenso
esplicito E licenza tracciata; niente auto-pubblicazione; `contributor_id` è
uno pseudonimo obbligatorio; solo i contributi curati sono pubblici.
"""

from __future__ import annotations

import inspect
import logging
from datetime import UTC, datetime

import pytest
from contracts import MemoryContribution, MemoryKind, MemoryLinkState, PersonKind
from urban_memory import (
    ConsentRequiredError,
    InMemoryMemoryRepository,
    InvalidTargetsError,
    LicenseRequiredError,
    PostgresMemoryRepository,
    PseudonymRequiredError,
    contributions_for_place,
    curate_contribution,
    pending_contributions,
    publish_pending,
    submit_contribution,
)
from urban_memory.graph_link import MemoryLinkError


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


def test_submit_azzera_stato_aggancio_fabbricato_in_ingresso(
    repo, valid_contribution_factory
) -> None:
    """Bug reale trovato da `ethics-guardian`: `submit_contribution` forzava
    `curato=False` ma NON azzerava `stato_aggancio` — un client (es.
    `POST /memory`, che accetta un `MemoryContribution` grezzo) poteva
    fabbricare `stato_aggancio=AGGANCIATO` fin dal conferimento, e quel
    valore sarebbe sopravvissuto indisturbato perché `curate_contribution`
    chiamata senza `linker` (il percorso di produzione reale oggi,
    `urban_memory.verify`) non lo tocca né lo valida — riproducendo lo
    scenario "nodo :Memoria sembra scritto ma non lo è" da un vettore
    diverso (input fabbricato, non assenza di automazione)."""
    contributo = valid_contribution_factory(
        stato_aggancio=MemoryLinkState.AGGANCIATO  # tentativo di aggancio fabbricato
    )
    persistito = submit_contribution(repo, contributo)
    assert persistito.stato_aggancio is None
    riletto = repo.get(persistito.id)
    assert riletto is not None
    assert riletto.stato_aggancio is None


def test_submit_azzera_anche_stato_aggancio_fallito_fabbricato_in_ingresso(
    repo, valid_contribution_factory
) -> None:
    """Stessa garanzia per l'altro valore possibile del campo (non solo
    `AGGANCIATO`): nessun valore fabbricato di `stato_aggancio` sopravvive
    al conferimento, qualunque esso sia."""
    contributo = valid_contribution_factory(stato_aggancio=MemoryLinkState.AGGANCIO_FALLITO)
    persistito = submit_contribution(repo, contributo)
    assert persistito.stato_aggancio is None


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


# --- curatela: la validazione dei target sta QUI, non al submit ------------
#
# Decisione architetturale (bug reale corretto): un contributo con
# riguarda=['bottega-liuteria-1'] (nodo INESISTENTE nel grafo) era arrivato
# a curato=True. submit_contribution non deve MAI dipendere dal grafo (Aura
# Free si auto-mette in pausa: il Cittadino deve poter conferire comunque);
# è curate_contribution, con un target_checker, il gate che blocca.


def test_curate_con_target_checker_tutti_mancanti_solleva_invalid_targets_error(
    repo, valid_contribution_factory
) -> None:
    # valid_contribution_factory ha di default riguarda=["bottega-liuteria-1"]
    # — esattamente l'id INESISTENTE del bug reale.
    contributo = valid_contribution_factory()
    submit_contribution(repo, contributo)

    def target_checker_tutto_mancante(riguarda: list[str]) -> list[str]:
        return list(riguarda)  # nessun id "esiste" per questo checker finto

    with pytest.raises(InvalidTargetsError) as errore:
        curate_contribution(repo, contributo.id, target_checker=target_checker_tutto_mancante)

    assert "bottega-liuteria-1" in str(errore.value)
    assert errore.value.mancanti == ["bottega-liuteria-1"]
    assert errore.value.memory_id == contributo.id


def test_curate_con_target_checker_invalido_non_tocca_il_repository(
    repo, valid_contribution_factory
) -> None:
    """`curato` NON diventa `True`: verifica che il repository non venga
    toccato — il repository resta esattamente come dopo il submit."""
    contributo = valid_contribution_factory()
    submit_contribution(repo, contributo)

    with pytest.raises(InvalidTargetsError):
        curate_contribution(repo, contributo.id, target_checker=lambda riguarda: list(riguarda))

    rilecto = repo.get(contributo.id)
    assert rilecto is not None
    assert rilecto.curato is False
    assert contributions_for_place(repo, "bottega-liuteria-1") == []
    assert contributo.id in [c.id for c in pending_contributions(repo)]


def test_curate_con_target_checker_nessun_mancante_cura_normalmente(
    repo, valid_contribution_factory
) -> None:
    contributo = valid_contribution_factory()
    submit_contribution(repo, contributo)

    curato = curate_contribution(repo, contributo.id, target_checker=lambda riguarda: [])

    assert curato.curato is True
    assert [c.id for c in contributions_for_place(repo, "bottega-liuteria-1")] == [contributo.id]


def test_curate_senza_target_checker_comportamento_invariato(
    repo, valid_contribution_factory
) -> None:
    """`target_checker=None` (default): comportamento IDENTICO a prima di
    questa correzione — nessuna verifica dei target. Pensato SOLO per test
    di dominio puri che non riguardano il grafo (questo file)."""
    contributo = valid_contribution_factory()  # riguarda un id inesistente nel grafo
    submit_contribution(repo, contributo)

    curato = curate_contribution(repo, contributo.id)  # nessun target_checker qui

    assert curato.curato is True


def test_curate_con_target_checker_id_sconosciuto_solleva_keyerror(repo) -> None:
    with pytest.raises(KeyError):
        curate_contribution(repo, "non-esiste-mai", target_checker=lambda riguarda: [])


def test_publish_pending_e_lo_stesso_curate_contribution() -> None:
    """Alias, non un wrapper: eredita `target_checker` (anche in un ciclo su
    più `memory_id`, "in batch") perché È la stessa funzione."""
    assert publish_pending is curate_contribution


def test_publish_pending_con_target_checker_solleva_invalid_targets_error(
    repo, valid_contribution_factory
) -> None:
    contributo = valid_contribution_factory()
    submit_contribution(repo, contributo)

    with pytest.raises(InvalidTargetsError):
        publish_pending(repo, contributo.id, target_checker=lambda riguarda: list(riguarda))


def test_curate_con_target_checker_su_postgres_reale_non_persiste_curato(pg_repo) -> None:
    """Stessa garanzia delle prove sopra, ma contro un Postgres VERO (non un
    mock, non InMemory): dopo `InvalidTargetsError`, una RILETTURA DAL DB
    (una connessione nuova, via `pg_repo.get`) conferma `curato=False` — il
    cuore della richiesta del committente."""
    contributo = MemoryContribution(
        id="mem-invalid-targets-pg",
        kind=MemoryKind.RACCONTO,
        riguarda=["bottega-liuteria-1"],  # id INESISTENTE nel grafo, per costruzione
        contributor_id="voce-di-controllo",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 15, 9, 0, tzinfo=UTC),
    )
    submit_contribution(pg_repo, contributo)

    with pytest.raises(InvalidTargetsError):
        curate_contribution(pg_repo, contributo.id, target_checker=lambda riguarda: list(riguarda))

    rilecto: PostgresMemoryRepository = pg_repo
    trovato = rilecto.get(contributo.id)
    assert trovato is not None
    assert trovato.curato is False
    assert pg_repo.get_curated("bottega-liuteria-1") == []


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


def test_service_non_chiama_print() -> None:
    """Test-guard (come `test_scoring_non_usa_partner_id_ne_prezzo` in
    experience-engine): nessuna riga ESEGUITA di `urban_memory.service` deve
    chiamare `print()` — il contenuto di un contributo non deve mai finire
    su stdout. Ispeziona l'AST (non la sorgente grezza, che includerebbe
    anche le parole nella docstring che SPIEGA la regola).

    Da questa wave (Fase 3, invariante "curato tira aggancio") il modulo usa
    LEGITTIMAMENTE `logging` per le transizioni automatiche dell'aggancio
    (`approved -> agganciato`/`approved -> aggancio_fallito`,
    `docs/STATE_MACHINE.md` §1: "anche l'automatico logga"): la garanzia
    "mai il contenuto in un log" resta, ma si verifica sugli ARGOMENTI delle
    chiamate di log (vedi `test_log_delle_transizioni_non_espone_mai_attributi_di_contenuto`
    e il test comportamentale con `caplog` sotto), non più vietando
    `logging` in blocco."""
    import ast

    import urban_memory.service as service_module

    albero = ast.parse(inspect.getsource(service_module))
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id != "print"


def test_log_delle_transizioni_non_espone_mai_attributi_di_contenuto() -> None:
    """Test-guard sui SOLI argomenti delle chiamate `_logger.<livello>(...)`:
    nessun accesso ad attributo `.testo`/`.media_uri`/`.contributor_id` può
    comparire tra gli argomenti di una chiamata di log — il modo più sicuro
    di garantire che il contenuto di un contributo non finisca mai in un log
    è che il codice non possa nemmeno leggerlo lì dentro quella chiamata."""
    import ast

    import urban_memory.service as service_module

    vietati = {"testo", "media_uri", "contributor_id"}
    albero = ast.parse(inspect.getsource(service_module))
    for nodo in ast.walk(albero):
        e_chiamata_di_log = (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and isinstance(nodo.func.value, ast.Name)
            and nodo.func.value.id == "_logger"
        )
        if not e_chiamata_di_log:
            continue
        for sotto_nodo in ast.walk(nodo):
            if isinstance(sotto_nodo, ast.Attribute):
                assert sotto_nodo.attr not in vietati


def test_transizioni_automatiche_loggano_memory_id_ed_esito_mai_il_contenuto(
    repo, valid_contribution_factory, caplog
) -> None:
    """Garanzia comportamentale (non solo AST): dopo una transizione
    automatica `approved -> aggancio_fallito`, i log CATTURATI DAVVERO non
    contengono `testo`/`contributor_id` del contributo, ma contengono l'id
    del contributo e l'esito — coerente con "anche l'automatico logga"
    (`docs/STATE_MACHINE.md` §1)."""
    contributo = valid_contribution_factory(
        id="mem-log-transizione",
        testo="Segreto: la nonna raccontava della bottega del nonno.",
        contributor_id="pseudonimo-riservato-log",
    )
    submit_contribution(repo, contributo)

    def linker_che_fallisce(c: MemoryContribution) -> None:
        raise MemoryLinkError("grafo irraggiungibile (simulato)")

    with caplog.at_level(logging.INFO, logger="urban_memory.service"):
        curate_contribution(repo, contributo.id, linker=linker_che_fallisce)

    messaggi = "\n".join(record.getMessage() for record in caplog.records)
    assert contributo.testo not in messaggi
    assert contributo.contributor_id not in messaggi
    assert contributo.id in messaggi
    assert "aggancio_fallito" in messaggi
