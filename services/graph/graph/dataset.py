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

from contracts import ARTICOLI, Curiosita, ExperienceNode, Partner, VocabolarioTemi

# `VICINO` non porta uno storico reale: il seed non ha mai registrato QUANDO
# un arco di prossimità fisica è stato scritto. Tutti gli archi dei dataset
# iniziali condividono un'unica EPOCA convenzionale ("sempre esistiti", non
# una data vera di scrittura): è il default di `RelazioneVicino.creato_il`.
# Un arco `VICINO` aggiunto dopo il seed deve invece portare
# `datetime.now(UTC)` al momento della scrittura (vedi `graph.topology.
# non_connected_place_pairs`, indicatore `nuovi_percorsi`).
VICINO_EPOCA_PREDEFINITA: datetime = datetime(2026, 1, 1, tzinfo=UTC)


def _valida_testo_con_fonte(chi: str, testo: str | None, fonte: str | None) -> None:
    """Testo narrativo e fonte vanno insieme: un testo senza fonte o una fonte
    senza testo è un errore a import (vuoto/solo spazi = assente)."""
    for valore in (testo, fonte):
        if valore is not None and "\n" in valore:
            # Il loader spezza il Cypher su ";\n": testi su una riga sola.
            raise ValueError(f"{chi}: testo e fonte non possono contenere a-capo")
    ha_testo = bool(testo and testo.strip())
    ha_fonte = bool(fonte and fonte.strip())
    if ha_testo != ha_fonte:
        raise ValueError(
            f"{chi}: testo e fonte vanno dichiarati insieme "
            f"(testo={'sì' if ha_testo else 'no'}, fonte={'sì' if ha_fonte else 'no'})"
        )


@dataclass(frozen=True)
class Luogo:
    id: str
    nome: str
    categoria: str  # "mura","piazza","chiesa","museo","giardino","torre","via","teatro"
    # Articolo determinativo del nome (uno di `contracts.ARTICOLI`), dato di
    # grammatica del dataset; None = nome senza articolo (es. una via).
    articolo: str | None = None
    # Curiosità del LUOGO (ogni esperienza in quel luogo le porta), nell'ordine
    # del seed. Solo narrazione, mai input di scoring. Ognuna ha una fonte
    # (obbligatoria nel contratto `contracts.Curiosita`).
    curiosita: tuple[Curiosita, ...] = ()

    def __post_init__(self) -> None:
        if self.articolo is not None and self.articolo not in ARTICOLI:
            raise ValueError(
                f"luogo {self.id!r}: articolo {self.articolo!r} non valido "
                f"(atteso None o uno di {ARTICOLI})"
            )
        for voce in self.curiosita:
            # Stessa regola dei racconti: il loader spezza il Cypher su ";\n".
            _valida_testo_con_fonte(f"curiosità del luogo {self.id!r}", voce.testo, voce.fonte)


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
    # True = bottega dimostrativa, non un esercizio reale: la disclosure
    # ("esempio dimostrativo") ne dipende. Obbligatorio, nessun default.
    fittizio: bool


@dataclass(frozen=True)
class Tema:
    id: str
    nome: str  # nome del tema, es. "Giacomo Puccini e la musica"
    # Etichetta leggibile da inserire in una frase ("Temi: a, b."). Se omessa
    # è il nome con l'iniziale minuscola; un dataset la dichiara esplicita.
    etichetta: str = ""
    # Frase narrativa del tema: ammessa SOLO con `fonte` (nessun testo senza
    # fonte, nessuna fonte senza testo).
    frase: str | None = None
    fonte: str | None = None

    def __post_init__(self) -> None:
        if not self.etichetta:
            object.__setattr__(self, "etichetta", self.nome[:1].lower() + self.nome[1:])
        _valida_testo_con_fonte(f"tema {self.id!r}", self.frase, self.fonte)


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
    # Racconto del legame: ammesso SOLO con `fonte`. Senza racconto il legame
    # resta un fatto del grafo (alimenta `connessioni`) ma non entra nel motivo.
    racconto: str | None = None
    fonte: str | None = None

    def __post_init__(self) -> None:
        _valida_testo_con_fonte(
            f"legato_a {self.artista_id!r}->{self.luogo_id!r}", self.racconto, self.fonte
        )


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
    modulo e il file Cypher. `id_esempio_memoria` è l'id di una Bottega o
    di un Luogo ESISTENTE nel dataset, usato dalla verifica di Urban Memory come
    bersaglio di una memoria di prova: la validazione ne garantisce
    l'esistenza (un id inesistente riprodurrebbe il bug delle memorie
    orfane).

    `vocabolario` è il dato della città con cui il motore legge i `Tema`
    (gruppi tematici): ogni suo id deve essere l'id di un `Tema` del dataset.
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
    vocabolario: VocabolarioTemi

    def __post_init__(self) -> None:
        ids_validi = {b.id for b in self.botteghe} | {luogo.id for luogo in self.luoghi}
        if self.id_esempio_memoria not in ids_validi:
            raise ValueError(
                f"dataset {self.nome!r}: id_esempio_memoria {self.id_esempio_memoria!r} "
                "non è una Bottega né un Luogo del dataset"
            )
        id_vocabolario = {
            *self.vocabolario.contemplativi,
            *self.vocabolario.arte,
            *self.vocabolario.insoliti,
            *self.vocabolario.verde,
            self.vocabolario.bambini,
        }
        mancanti = sorted(id_vocabolario - {t.id for t in self.temi})
        if mancanti:
            raise ValueError(
                f"dataset {self.nome!r}: il vocabolario cita id che non sono Tema "
                f"del dataset: {', '.join(mancanti)}"
            )
