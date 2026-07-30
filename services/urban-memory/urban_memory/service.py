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
  `stato_aggancio` è SEMPRE azzerato a `None` insieme a `curato`, per lo
  STESSO motivo: un client potrebbe altrimenti fabbricare
  `stato_aggancio="agganciato"` fin dal conferimento (bug reale corretto,
  trovato da `ethics-guardian` — vedi `submit_contribution`).
- i `riguarda` di un contributo CURATO devono esistere nel grafo — ma
  questa verifica sta ALLA CURATELA (`curate_contribution`/
  `publish_pending`, tramite `target_checker`), MAI al conferimento
  (`submit_contribution`): il conferimento non deve mai dipendere dalla
  disponibilità del grafo (Aura Free si auto-mette in pausa dopo
  inattività — il Cittadino deve poter conferire comunque). La curatela è
  il gate di pubblicazione: è lì che un riferimento invalido va bloccato
  (bug reale corretto: un contributo con `riguarda=['bottega-liuteria-1']`,
  un id INESISTENTE nel grafo, era arrivato a `curato=True`).
- **"Curato tira aggancio"** (invariante `docs/ENGINE_INVARIANTS.md` §11-B):
  quando `curate_contribution`/`publish_pending` riceve anche un `linker`
  (oltre al `target_checker`), l'aggancio al grafo è innescato
  AUTOMATICAMENTE subito dopo `curato=True`, nella stessa chiamata — mai un
  passo separato che qualcuno può dimenticare. "Curato ma non agganciato"
  resta un TRANSITORIO interno a questa chiamata, mai uno stato di riposo:
  l'esito (`MemoryContribution.stato_aggancio`, `contracts.MemoryLinkState`)
  è sempre `AGGANCIATO` o `AGGANCIO_FALLITO` — quest'ultimo un'attesa
  RECUPERABILE (vedi `retry_link_contribution`), mai un vicolo cieco.
  `linker=None` (default): comportamento IDENTICO a prima — nessun
  aggancio tentato, `stato_aggancio` resta `None`. Stesso pattern già
  stabilito per `target_checker`: opt-in esplicito, obbligatorio per chi
  cura per pubblicare DAVVERO.

Il servizio non logga MAI il CONTENUTO di un contributo (`testo`,
`media_uri`, `contributor_id`): nessuna riga di questo modulo chiama
`print()`, né passa quei tre campi a `logging`. Le uniche righe di log che
questo modulo produce sono le transizioni AUTOMATICHE dell'aggancio
(`approved -> agganciato` / `approved -> aggancio_fallito`,
`docs/STATE_MACHINE.md` §1: "anche l'automatico logga") — solo
`memory_id` (non PII: un id di contributo) ed esito, mai il payload.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from contracts import MemoryContribution, MemoryLinkState

from .graph_link import MemoryLinkError
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
    "retry_link_contribution",
    "pending_contributions",
    "contributions_for_place",
]

_logger = logging.getLogger(__name__)

#: Tipo del `linker`: riceve il `MemoryContribution` GIÀ curato e lo
#: aggancia al grafo (o solleva `MemoryLinkError`) — esattamente la firma di
#: `Neo4jMemoryLinker.link` (metodo legato) o di `functools.partial(
#: link_to_graph, driver=...)`. Nessun valore di ritorno: l'esito si legge
#: dall'assenza/presenza di `MemoryLinkError`, mai da un booleano.
_Linker = Callable[[MemoryContribution], None]


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
    autopubblica. Per lo STESSO motivo, `stato_aggancio` è SEMPRE forzato a
    `None`: un client (es. `POST /memory`, che accetta un `MemoryContribution`
    grezzo — `services/api`) potrebbe altrimenti fabbricare
    `stato_aggancio="agganciato"` fin dal conferimento. Senza questo azzeramento
    quel valore fabbricato sopravviverebbe indisturbato, perché
    `curate_contribution` chiamata senza `linker` (il percorso di produzione
    reale oggi, `urban_memory.verify`) non lo tocca né lo valida —
    riproducendo esattamente lo scenario "nodo :Memoria sembra scritto ma
    non lo è" che l'intera automazione (`docs/ENGINE_INVARIANTS.md` §11-B)
    esiste per rendere impossibile, solo raggiunto da un vettore diverso
    (input fabbricato in ingresso, non assenza di automazione). Bug reale
    trovato da `ethics-guardian`, corretto qui.
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

    da_persistere = contribution.model_copy(update={"curato": False, "stato_aggancio": None})
    return repo.submit(da_persistere)


def curate_contribution(
    repo: MemoryRepository,
    memory_id: str,
    *,
    target_checker: Callable[[list[str]], list[str]] | None = None,
    linker: _Linker | None = None,
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

    `linker` — invariante "curato tira aggancio" (`docs/ENGINE_INVARIANTS.md`
    §11-B): se fornito, SUBITO dopo che `repo.curate(memory_id)` ha portato
    `curato=True`, questa funzione tenta l'aggancio al grafo chiamando
    `linker(contribution)` — stesso seam per `InMemoryMemoryRepository` e
    `PostgresMemoryRepository` (opera solo attraverso il `Protocol
    MemoryRepository`, non conosce l'implementazione concreta).

    - `linker=None` (default): comportamento IDENTICO a prima di questa
      automazione — nessun aggancio tentato, `stato_aggancio` resta `None`.
      Pensato SOLO per test di dominio puri. Chi cura per pubblicare DAVVERO
      DEVE passare un `linker` reale — tipicamente `Neo4jMemoryLinker.link`
      (metodo legato).
    - `linker` fornito e l'aggancio RIESCE: `stato_aggancio` diventa
      `MemoryLinkState.AGGANCIATO`.
    - `linker` fornito e l'aggancio FALLISCE (`MemoryLinkError` — in questo
      repository sempre infrastrutturale: l'invariante A, append-only sui
      target, esclude un target sparito dopo il pre-check di
      `target_checker` sopra): `stato_aggancio` diventa
      `MemoryLinkState.AGGANCIO_FALLITO`. NON solleva l'eccezione: è uno
      stato di ATTESA RECUPERABILE (vedi `retry_link_contribution`), non un
      errore da propagare a chi chiama `curate_contribution` — il contributo
      resta comunque `curato=True` (la revisione umana è avvenuta ed è
      irrevocabile da qui), semplicemente non ancora agganciato.

    In ENTRAMBI i casi la transizione è loggata (chi=sistema, quando,
    esito) — mai il contenuto del contributo, solo `memory_id`.
    """
    if target_checker is not None:
        contribution = repo.get(memory_id)
        if contribution is None:
            raise KeyError(f"nessun contributo con id={memory_id!r}")
        mancanti = target_checker(list(contribution.riguarda))
        if mancanti:
            raise InvalidTargetsError(memory_id, mancanti)

    curato = repo.curate(memory_id)

    if linker is not None:
        curato = _innesca_aggancio(repo, curato, linker)

    return curato


#: Alias: nel BUILD_PLAN (Wave 2) la stessa revisione umana è indicata sia
#: come "curatela" (`curate_contribution`) sia come "pubblicazione della
#: coda" (`publish_pending`) — è lo stesso passo di dominio, un solo nome
#: interno (`curate_contribution`) evita di duplicare la logica. Essendo un
#: alias (non un wrapper), `publish_pending` eredita `target_checker`/
#: `linker` automaticamente — anche curando in un ciclo su più `memory_id`
#: (batch): è la STESSA funzione, non una copia con una firma divergente.
publish_pending = curate_contribution


def _innesca_aggancio(
    repo: MemoryRepository, contribution: MemoryContribution, linker: _Linker
) -> MemoryContribution:
    """Seam UNICO che innesca `link_to_graph` dopo che `curato` è diventato
    `True` — chiamato SOLO da `curate_contribution` (subito dopo
    `repo.curate`) e da `retry_link_contribution` (sullo stesso contributo
    già curato, per riprovare). Opera esclusivamente attraverso il
    `Protocol MemoryRepository`: nessuna logica duplicata tra
    `InMemoryMemoryRepository` e `PostgresMemoryRepository`.

    Registra l'esito con `repo.set_stato_aggancio` e logga la transizione
    (chi=sistema, quando, esito — MAI `testo`/`media_uri`/`contributor_id`):
    coerente con "anche l'automatico logga" (`docs/STATE_MACHINE.md` §1).
    """
    try:
        linker(contribution)
    except MemoryLinkError:
        aggiornato = repo.set_stato_aggancio(contribution.id, MemoryLinkState.AGGANCIO_FALLITO)
        _logger.info(
            "transizione automatica: approved -> aggancio_fallito "
            "(memory_id=%s, chi=sistema)",
            contribution.id,
        )
        return aggiornato

    aggiornato = repo.set_stato_aggancio(contribution.id, MemoryLinkState.AGGANCIATO)
    _logger.info(
        "transizione automatica: approved -> agganciato (memory_id=%s, chi=sistema)",
        contribution.id,
    )
    return aggiornato


def retry_link_contribution(
    repo: MemoryRepository, memory_id: str, *, linker: _Linker
) -> MemoryContribution:
    """Ritenta l'aggancio al grafo di un contributo GIÀ curato — tipicamente
    uno in `stato_aggancio=AGGANCIO_FALLITO`, il percorso di RECUPERO che
    rende `aggancio_fallito` un'attesa recuperabile e non un vicolo cieco
    (`docs/ENGINE_INVARIANTS.md` §11-B). Riusa lo stesso seam
    (`_innesca_aggancio`) di `curate_contribution`: nessuna logica duplicata.

    Funziona su QUALUNQUE contributo curato, non solo su quelli in
    `AGGANCIO_FALLITO` (rieseguirlo su un già `AGGANCIATO` è innocuo:
    `link_to_graph` è idempotente, `MERGE` non duplica nulla) — comodo per
    un retry "a tappeto" su `repo.list_aggancio_fallito()` senza dover
    ricontrollare lo stato prima di chiamare.

    Solleva `KeyError` se `memory_id` non esiste. Solleva `UrbanMemoryError`
    se il contributo esiste ma NON è ancora curato: il retry dell'aggancio
    ha senso solo per un contributo APPROVATO — riaganciare un pending
    significherebbe agganciare qualcosa che la curatela non ha ancora
    revisionato.
    """
    contribution = repo.get(memory_id)
    if contribution is None:
        raise KeyError(f"nessun contributo con id={memory_id!r}")
    if not contribution.curato:
        raise UrbanMemoryError(
            f"contributo id={memory_id!r} non è curato: il retry dell'aggancio "
            "si applica solo a contributi già approvati (curato=True)."
        )
    return _innesca_aggancio(repo, contribution, linker)


def pending_contributions(repo: MemoryRepository) -> list[MemoryContribution]:
    """Coda di curatela: contributi non ancora revisionati (`curato=False`),
    la vista che alimenta l'interfaccia di revisione umana."""
    return repo.list_pending()


def contributions_for_place(repo: MemoryRepository, place_id: str) -> list[MemoryContribution]:
    """Contributi pubblicabili per un Luogo/Bottega/Artista: delega SEMPRE a
    `get_curated`, così solo i contributi curati sono mai restituiti — mai
    un accesso diretto che li scavalchi."""
    return repo.get_curated(place_id)

