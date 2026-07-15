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
- i `riguarda` di un contributo CURATO devono esistere nel grafo — ma
  questa verifica sta ALLA CURATELA (`curate_contribution`/
  `publish_pending`, tramite `target_checker`), MAI al conferimento
  (`submit_contribution`): il conferimento non deve mai dipendere dalla
  disponibilità del grafo (Aura Free si auto-mette in pausa dopo
  inattività — il Cittadino deve poter conferire comunque). La curatela è
  il gate di pubblicazione: è lì che un riferimento invalido va bloccato
  (bug reale corretto: un contributo con `riguarda=['bottega-liuteria-1']`,
  un id INESISTENTE nel grafo, era arrivato a `curato=True`).

Il servizio non logga MAI il contenuto di un contributo (`testo`,
`media_uri`, `contributor_id`): nessuna riga di questo modulo chiama
`print`/`logging` sul payload. Un contributo può portare un racconto privato
o l'identità scelta di un cittadino — non è materiale da log, e il modo più
sicuro di garantirlo per sempre è non chiamare quelle funzioni affatto.
"""

from __future__ import annotations

from collections.abc import Callable

from contracts import MemoryContribution

from .repository import MemoryRepository

__all__ = [
    "UrbanMemoryError",
    "ConsentRequiredError",
    "LicenseRequiredError",
    "PseudonymRequiredError",
    "InvalidTargetsError",
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


class InvalidTargetsError(UrbanMemoryError):
    """Almeno un id in `riguarda` NON esiste nel grafo come `:Luogo`/
    `:Bottega`/`:Artista`. Sollevata da `curate_contribution`/
    `publish_pending` quando chiamate con un `target_checker`: la curatela
    è il gate di pubblicazione, un riferimento invalido non deve mai
    superarlo (`curato` resta `False`, nessuna scrittura sul repository).

    Sottoclasse di `UrbanMemoryError` — NON di `urban_memory.graph_link.
    MemoryLinkError` (un errore di ESECUZIONE contro il grafo, in un
    modulo diverso): questo è un vincolo di DOMINIO sul contributo, come
    `ConsentRequiredError`/`LicenseRequiredError`. Deliberato: così il BFF
    la mappa già a 422 (`UrbanMemoryError` -> 422) senza codice nuovo.
    """

    def __init__(self, memory_id: str, mancanti: list[str]) -> None:
        self.memory_id = memory_id
        self.mancanti = list(mancanti)
        super().__init__(
            f"contributo id={memory_id!r}: target inesistenti nel grafo: "
            f"{self.mancanti!r} — curatela rifiutata, curato resta False"
        )


def submit_contribution(
    repo: MemoryRepository, contribution: MemoryContribution
) -> MemoryContribution:
    """Valida i vincoli non negoziabili e persiste il contributo.

    Ordine dei controlli (dal più critico): consenso, poi licenza, poi
    pseudonimo — ciascuno solleva un'eccezione dedicata, così chi chiama può
    distinguere il motivo del rifiuto (utile per un conferimento leggero e
    contestuale: l'app può segnalare esattamente cosa manca).

    NESSUNA verifica dei target nel grafo qui, di proposito (decisione
    architetturale): il conferimento deve poter avvenire SEMPRE, anche a
    grafo non raggiungibile — è la curatela (`curate_contribution`) il gate
    che verifica i target, non questo passo.

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


def curate_contribution(
    repo: MemoryRepository,
    memory_id: str,
    *,
    target_checker: Callable[[list[str]], list[str]] | None = None,
) -> MemoryContribution:
    """Revisione umana che porta `curato=True`. Solo dopo questo passo il
    contributo compare in `get_curated`/`contributions_for_place`: la
    memoria di una città non si pubblica grezza. Solleva `KeyError` se
    `memory_id` non esiste nel repository.

    `target_checker` — DECISIONE ARCHITETTURALE (bug reale corretto: un
    contributo con `riguarda=['bottega-liuteria-1']`, un id INESISTENTE nel
    grafo, era arrivato a `curato=True`): la validazione dell'esistenza dei
    target sta ALLA CURATELA, non al conferimento. Il conferimento
    (`submit_contribution`) resta SEMPRE possibile, anche a grafo non
    disponibile (Aura Free si auto-mette in pausa dopo inattività: il
    Cittadino deve poter conferire comunque). La curatela è invece il gate
    di pubblicazione, ed è lì che un riferimento invalido va bloccato.

    - `target_checker=None` (default): comportamento IDENTICO a prima di
      questa correzione — NESSUNA verifica dei target. Pensato SOLO per
      test di dominio puri che non riguardano il grafo. Chi cura per
      pubblicare DAVVERO (`urban_memory.verify`, un endpoint di curatela
      nel BFF, `urban_memory.audit`) DEVE passare un `target_checker`
      reale — tipicamente `Neo4jMemoryLinker.targets_mancanti`, o il
      helper `urban_memory.graph_link.target_checker_from_env()`: ometterlo
      in produzione riapre esattamente il buco che questo parametro chiude.
    - `target_checker` fornito: riceve `riguarda` del contributo (una
      lista), deve ritornare gli id che NON esistono nel grafo. Se la
      lista ritornata non è vuota, solleva `InvalidTargetsError` (nomina
      gli id) e NON tocca il repository — `curato` resta `False`, nessuna
      scrittura avviene (né `repo.curate`, né altro).
    """
    if target_checker is not None:
        contribution = repo.get(memory_id)
        if contribution is None:
            raise KeyError(f"nessun contributo con id={memory_id!r}")
        mancanti = target_checker(list(contribution.riguarda))
        if mancanti:
            raise InvalidTargetsError(memory_id, mancanti)

    return repo.curate(memory_id)


#: Alias: nel BUILD_PLAN (Wave 2) la stessa revisione umana è indicata sia
#: come "curatela" (`curate_contribution`) sia come "pubblicazione della
#: coda" (`publish_pending`) — è lo stesso passo di dominio, un solo nome
#: interno (`curate_contribution`) evita di duplicare la logica. Essendo un
#: alias (non un wrapper), `publish_pending` eredita `target_checker`
#: automaticamente — anche curando in un ciclo su più `memory_id` (batch): è
#: la STESSA funzione, non una copia con una firma divergente.
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

