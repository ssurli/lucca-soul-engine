"""Tipi NEUTRI del dataset di una città: la forma, mai il contenuto.

Ogni città è un modulo `graph/seed_<slug>.py` che espone un `DATASET:
DatasetCitta`; il registro (`graph.registro`) lo risolve da `CITY_SEED`. La
tecnologia (schema, query, loader, sorgenti in-memory) legge SOLO da questi
tipi: replicare il motore su un'altra città significa scrivere un nuovo
modulo dataset, non toccare il codice.

Nodi: `Luogo`, `Artista`, `Bottega`, `Tema`, `Esperienza` (`ExperienceNode`,
importato da `contracts`: non è ridefinito qui) e `Partner` (idem).

Tipi minimi, locali a questo servizio (non sono contratti cross-servizio:
`docs/DATA_CONTRACTS.md` §2 definisce solo `ExperienceNode` e
`GraphCandidate` come tipi condivisi; Luogo/Artista/Bottega/Tema sono
dettaglio implementativo del grafo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from contracts import ExperienceNode, Partner

# `VICINO` non porta uno storico reale: il seed non ha mai registrato QUANDO
# un arco di prossimità fisica è stato scritto. Tutti gli archi dei dataset
# iniziali condividono un'unica EPOCA convenzionale ("sempre esistiti", non
# una data vera di scrittura): è il default di `RelazioneVicino.creato_il`.
# Un arco `VICINO` aggiunto dopo il seed deve invece portare
# `datetime.now(UTC)` al momento della scrittura (vedi `graph.topology.
# non_connected_place_pairs`, indicatore `nuovi_percorsi`).
VICINO_EPOCA_PREDEFINITA: datetime = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Luogo:
    id: str
    nome: str
    categoria: str  # "mura","piazza","chiesa","museo","giardino","torre","via","teatro"


@dataclass(frozen=True)
class Artista:
    id: str
    nome: str


@dataclass(frozen=True)
class Bottega:
    id: str
    nome: str
    mestiere: str  # "liuteria","ceramica","stampa","pasticceria","tessitura"
    place_id: str  # luogo dove si trova fisicamente la bottega


@dataclass(frozen=True)
class Tema:
    id: str
    nome: str  # etichetta leggibile, es. "Giacomo Puccini e la musica"


@dataclass(frozen=True)
class RelazioneVicino:
    """`(:Luogo)-[:VICINO {metri, creato_il}]->(:Luogo)`. Non direzionale nel
    dominio (la distanza vale nei due sensi): una riga sola per coppia, le
    API di lettura (`graph.source`, `cypher/10_candidates.cypher`) la
    trattano come non orientata.

    `creato_il`: default `VICINO_EPOCA_PREDEFINITA` per tutti gli archi del
    seed iniziale ("sempre esistiti", non una data vera). Un arco scritto
    dopo il seed dovrebbe passare `datetime.now(UTC)` esplicitamente: è ciò
    che rende possibile `graph.topology.non_connected_place_pairs` congelare
    uno snapshot di connettività a un istante T per l'indicatore
    `nuovi_percorsi`."""

    da_id: str
    a_id: str
    metri: int
    creato_il: datetime = VICINO_EPOCA_PREDEFINITA


@dataclass(frozen=True)
class RelazioneLegatoA:
    """`(:Artista)-[:LEGATO_A]->(:Luogo)`."""

    artista_id: str
    luogo_id: str


@dataclass(frozen=True)
class RelazioneBottegaEvoca:
    """`(:Bottega)-[:EVOCA]->(:Tema)`. Stesso tipo di relazione delle
    Esperienze (`Esperienza-[:EVOCA]->Tema`): la bottega evoca i temi del suo
    mestiere. Fatto SEMANTICO, non di prossimità: alimenta `connessioni` solo
    per i temi che l'esperienza specifica non evoca già (niente doppioni)."""

    bottega_id: str
    tema_id: str


@dataclass(frozen=True)
class RelazioneIspirataDa:
    """`(:Bottega)-[:ISPIRATA_DA]->(:Artista)`. Relazione SEMANTICA nuova
    (non di prossimità fisica, non `LEGATO_A` che è riservato ad
    Artista->Luogo): lega una bottega al lavoro di un artista che ne ispira
    il mestiere. `racconto` è la frase italiana che la rende esplicita in
    `GraphCandidate.connessioni` — è ciò che rende percorribile, per sole
    connessioni semantiche, "Artista -> ... -> artigiano -> oggetto"."""

    bottega_id: str
    artista_id: str
    racconto: str


@dataclass(frozen=True)
class RelazioneHaAbbonamento:
    """`(:Bottega)-[:HA_ABBONAMENTO]->(:Partner)`. Relazione COMMERCIALE
    (Wave 3a, marketplace): collega la Bottega del dominio culturale
    all'entità di ricavo `Partner` (`docs/DATA_CONTRACTS.md` §5). Una
    Bottega senza questa relazione è considerata sempre visibile (nessun
    partner = nessuna leva commerciale attiva su di essa)."""

    bottega_id: str
    partner_id: str


@dataclass(frozen=True)
class DatasetCitta:
    """Il contenuto completo di una città, nella forma che il motore legge.

    `nome` è lo slug (`^[a-z][a-z0-9_-]*$`) con cui il registro risolve il
    modulo e il file Cypher. `id_esempio_memoria` è l'id REALE di una Bottega
    o di un Luogo del dataset, usato dalla verifica di Urban Memory come
    bersaglio di una memoria di prova: la validazione ne garantisce
    l'esistenza (un id inesistente riprodurrebbe il bug delle memorie
    orfane).
    """

    nome: str
    luoghi: list[Luogo]
    artisti: list[Artista]
    legato_a: list[RelazioneLegatoA]
    botteghe: list[Bottega]
    temi: list[Tema]
    bottega_evoca: list[RelazioneBottegaEvoca]
    bottega_ispirata_da: list[RelazioneIspirataDa]
    partners: list[Partner]
    ha_abbonamento: list[RelazioneHaAbbonamento]
    esperienze: list[ExperienceNode]
    vicino: list[RelazioneVicino]
    vicino_epoca: datetime
    id_esempio_memoria: str

    def __post_init__(self) -> None:
        ids_validi = {b.id for b in self.botteghe} | {luogo.id for luogo in self.luoghi}
        if self.id_esempio_memoria not in ids_validi:
            raise ValueError(
                f"dataset {self.nome!r}: id_esempio_memoria {self.id_esempio_memoria!r} "
                "non è una Bottega né un Luogo del dataset"
            )
