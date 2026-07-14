"""Urban Memory — logica di dominio: consenso, licenza, pseudonimo, curatela.

Qui vivono i VINCOLI NON NEGOZIABILI del fossato difendibile del progetto
(CLAUDE.md, docs/DATA_CONTRACTS.md §4), applicati in UN SOLO PUNTO
verificabile — lo stesso principio dell'AI Experience Engine ("un vincolo
applicato in un solo punto è verificabile, distribuito no"):

- `MemoryContribution.consenso` deve essere `True` per persistere. NESSUNA
  eccezione.
- la `licenza` è sempre tracciata ed esplicita: un contributo senza licenza
  chiara è un debito legale, non un asset.
- `contributor_id` è uno pseudonimo non vuoto: il contributo si firma con un
  nome scelto, mai con PII.
- `curato` è sempre `False` alla creazione: la pubblicazione richiede
  revisione umana (`curate_contribution`), mai auto-pubblicazione.

Il servizio non logga MAI il contenuto di un contributo (`testo`,
`media_uri`, `contributor_id`): nessuna riga di questo modulo chiama
`print`/`logging` sul payload. Un contributo può portare un racconto privato
o l'identità scelta di un cittadino — non è materiale da log, e il modo più
sicuro di garantirlo per sempre è non chiamare quelle funzioni affatto.
"""

from __future__ import annotations

from contracts import MemoryContribution

from .repository import MemoryRepository

__all__ = [
    "UrbanMemoryError",
    "ConsentRequiredError",
    "LicenseRequiredError",
    "PseudonymRequiredError",
    "submit_contribution",
    "curate_contribution",
    "publish_pending",
    "pending_contributions",
    "contributions_for_place",
]


class UrbanMemoryError(Exception):
    """Base per le eccezioni di dominio della Urban Memory."""


class ConsentRequiredError(UrbanMemoryError):
    """`consenso` non è `True`. Nessuna eccezione è ammessa a questa regola:
    né un partner, né un'urgenza editoriale, né un progetto finanziato la
    aggirano."""


class LicenseRequiredError(UrbanMemoryError):
    """`licenza` è vuota o solo whitespace: un contributo senza licenza
    tracciata (es. "CC-BY-SA-4.0") è un debito legale, non un asset."""


class PseudonymRequiredError(UrbanMemoryError):
    """`contributor_id` è vuoto o solo whitespace: il contributo deve poter
    essere firmato con uno pseudonimo scelto, mai in forma anonima e mai con
    PII grezza."""


def submit_contribution(
    repo: MemoryRepository, contribution: MemoryContribution
) -> MemoryContribution:
    """Valida i vincoli non negoziabili e persiste il contributo.

    Ordine dei controlli (dal più critico): consenso, poi licenza, poi
    pseudonimo — ciascuno solleva un'eccezione dedicata, così chi chiama può
    distinguere il motivo del rifiuto (utile per un conferimento leggero e
    contestuale: l'app può segnalare esattamente cosa manca).

    `curato` è SEMPRE forzato a `False` nell'oggetto persistito,
    indipendentemente da cosa porta l'oggetto in ingresso: la curatela è un
    passo successivo, umano, mai automatico — nessun conferimento si
    autopubblica.
    """
    if contribution.consenso is not True:
        raise ConsentRequiredError(
            "MemoryContribution.consenso deve essere True per persistere: "
            "nessuna eccezione."
        )
    if not contribution.licenza or not contribution.licenza.strip():
        raise LicenseRequiredError(
            "MemoryContribution.licenza è obbligatoria e tracciata "
            "(es. 'CC-BY-SA-4.0'): un contributo senza licenza chiara è un "
            "debito legale, non un asset."
        )
    if not contribution.contributor_id or not contribution.contributor_id.strip():
        raise PseudonymRequiredError(
            "MemoryContribution.contributor_id deve essere uno pseudonimo "
            "non vuoto: il contributo si firma con un nome scelto, mai in "
            "forma anonima."
        )

    da_persistere = contribution.model_copy(update={"curato": False})
    return repo.submit(da_persistere)


def curate_contribution(repo: MemoryRepository, memory_id: str) -> MemoryContribution:
    """Revisione umana che porta `curato=True`. Solo dopo questo passo il
    contributo compare in `get_curated`/`contributions_for_place`: la
    memoria di una città non si pubblica grezza. Solleva `KeyError` se
    `memory_id` non esiste nel repository."""
    return repo.curate(memory_id)


#: Alias: nel BUILD_PLAN (Wave 2) la stessa revisione umana è indicata sia
#: come "curatela" (`curate_contribution`) sia come "pubblicazione della
#: coda" (`publish_pending`) — è lo stesso passo di dominio, un solo nome
#: interno (`curate_contribution`) evita di duplicare la logica.
publish_pending = curate_contribution


def pending_contributions(repo: MemoryRepository) -> list[MemoryContribution]:
    """Coda di curatela: contributi non ancora revisionati (`curato=False`),
    la vista che alimenta l'interfaccia di revisione umana."""
    return repo.list_pending()


def contributions_for_place(repo: MemoryRepository, place_id: str) -> list[MemoryContribution]:
    """Contributi pubblicabili per un Luogo/Bottega/Artista: delega SEMPRE a
    `get_curated`, così solo i contributi curati sono mai restituiti — mai
    un accesso diretto che li scavalchi."""
    return repo.get_curated(place_id)
