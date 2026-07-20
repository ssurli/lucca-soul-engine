"""Dataset canonico del seed Lucca — FONTE DI VERITÀ UNICA.

Ogni altra via di alimentazione del grafo nasce da questo modulo:

- `graph.source.SeedCandidateSource` lo legge direttamente, in memoria (il
  percorso usato nei test e finché `NEO4J_URI` non è configurato);
- `graph.export_cypher` lo traduce in Cypher versionato
  (`cypher/00_schema.cypher`, `cypher/01_seed_lucca.cypher`), committato e
  rieseguibile da zero con `python -m graph.loader`.

Replicare il motore su un'altra città (Siena, Ferrara...) significa scrivere
un nuovo modulo con questa stessa forma: la tecnologia (schema, query,
loader) non cambia, cambia solo il contenuto.

Nodi: `Luogo`, `Artista`, `Bottega`, `Tema`, `Esperienza` (`ExperienceNode`,
importato da `contracts`: non è ridefinito qui). `Evento` e `Memoria` sono
nello schema (`cypher/00_schema.cypher`) ma non hanno seed in questa wave:
`Evento` arriva con i segnali reali, `Memoria` con `urban-memory-engineer`
(Wave 2).

Relazioni derivate implicitamente dai campi di `ExperienceNode` (niente
tabelle separate da tenere sincronizzate a mano):
- `SI_SVOLGE_A` da `ExperienceNode.place_id`;
- `EVOCA` (Esperienza -> Tema) da `ExperienceNode.temi` (id di `Tema`);
- `OFFRE` da `ExperienceNode.partner_id` (id di `Bottega`, quando presente).

Relazioni esplicite (non derivabili da un solo campo): `VICINO` tra Luoghi,
`LEGATO_A` tra Artista e Luogo.

Relazioni SEMANTICHE bottega (non di prossimità fisica — vedi diagnosi Aura
del 2026-07-14: densità VICINO troppo bassa e Bottega di Liuteria
irraggiungibile da Puccini per sole connessioni fisiche):
- `EVOCA` (Bottega -> Tema): stesso tipo di relazione delle Esperienze — una
  bottega evoca i temi del suo mestiere anche a prescindere dall'esperienza
  specifica che offre;
- `ISPIRATA_DA` (Bottega -> Artista): relazione NUOVA, non di prossimità.
  Lega una bottega a un artista il cui lavoro ne è l'ispirazione (es. la
  liuteria è ispirata da Puccini e Boccherini). Porta con sé `racconto`, la
  frase italiana che rende esplicita la connessione in `connessioni`.

Queste due relazioni sono ciò che rende raggiungibile, per SOLE connessioni
semantiche (`LEGATO_A`, `SI_SVOLGE_A`, `OFFRE`, `EVOCA`, `ISPIRATA_DA` — mai
`VICINO`), il percorso canonico del White Paper: Puccini -> ... -> Bottega di
Liuteria. Verificato in `graph.topology` e `tests/test_topology.py`.

Marketplace (Wave 3a — `docs/DATA_CONTRACTS.md` §5):
- `HA_ABBONAMENTO` (Bottega -> Partner): relazione NUOVA. Un `Partner` è
  l'entità di ricavo (`Partner.abbonamento_attivo`, importato da
  `contracts`, NON ridefinito qui); la Bottega è l'entità del dominio
  culturale (mestiere, luogo). Le due restano separate perché il modello di
  ricavo (abbonamento di presenza) non deve mai inquinare il nodo che il
  grafo usa per raccontare connessioni semantiche (`EVOCA`, `ISPIRATA_DA`).
  Una Bottega SENZA relazione `HA_ABBONAMENTO` è trattata come sempre
  visibile (default `True`), stessa regola di `ExperienceNode.
  partner_abbonamento_attivo` in `contracts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from contracts import ExperienceNode, Partner

# `VICINO` non porta uno storico reale: il seed non ha mai registrato QUANDO
# un arco di prossimità fisica è stato scritto. Wave 4 (Urban Intelligence
# Index, indicatore `nuovi_percorsi`) ha bisogno di poter "congelare" uno
# snapshot del grafo a un istante T (vedi `graph.topology.
# non_connected_place_pairs`), quindi ogni arco `VICINO` porta ora
# `creato_il`. Onestà del dato: non si inventa una data reale per gli archi
# del seed iniziale (nessuno ce l'ha), quindi tutti condividono questa unica
# EPOCA convenzionale — "sempre esistiti", non una data vera di scrittura.
# Un futuro arco `VICINO` aggiunto dopo il seed (es. da una curatela che
# arricchisce la prossimità fisica, fuori dal perimetro di questa wave) deve
# invece portare `datetime.now(UTC)` al momento della scrittura: solo da lì
# in poi la data ha un significato storico reale, ed è quello che rende
# possibile distinguere "già connesso all'inizio del periodo" da "connesso
# DA POCO" — la definizione stessa di "nuovo percorso".
VICINO_EPOCA: datetime = datetime(2026, 1, 1, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Nodi: tipi minimi, locali a questo servizio (non sono contratti
# cross-servizio: `docs/DATA_CONTRACTS.md` §2 definisce solo `ExperienceNode`
# e `GraphCandidate` come tipi condivisi; Luogo/Artista/Bottega/Tema sono
# dettaglio implementativo del grafo).
# ---------------------------------------------------------------------------


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

    `creato_il`: default `VICINO_EPOCA` per tutti gli archi del seed
    iniziale ("sempre esistiti", non una data vera — vedi commento su
    `VICINO_EPOCA`). Un arco scritto dopo il seed dovrebbe passare
    `datetime.now(UTC)` esplicitamente: è ciò che rende possibile
    `graph.topology.non_connected_place_pairs` congelare uno snapshot di
    connettività a un istante T per l'indicatore `nuovi_percorsi`."""

    da_id: str
    a_id: str
    metri: int
    creato_il: datetime = VICINO_EPOCA


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
    connessioni semantiche, "Puccini -> ... -> liutaio -> violino"."""

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


# ---------------------------------------------------------------------------
# Luoghi — 15 luoghi reali di Lucca
# ---------------------------------------------------------------------------

LUOGHI: list[Luogo] = [
    Luogo("mura-urbane", "Mura di Lucca", "mura"),
    Luogo("piazza-anfiteatro", "Piazza dell'Anfiteatro", "piazza"),
    Luogo("torre-guinigi", "Torre Guinigi", "torre"),
    Luogo("duomo-san-martino", "Duomo di San Martino", "chiesa"),
    Luogo("casa-puccini", "Casa Natale di Giacomo Puccini", "museo"),
    Luogo("san-michele-in-foro", "Chiesa di San Michele in Foro", "chiesa"),
    Luogo("orto-botanico", "Orto Botanico di Lucca", "giardino"),
    Luogo("teatro-del-giglio", "Teatro del Giglio", "teatro"),
    Luogo("palazzo-pfanner", "Palazzo Pfanner", "giardino"),
    Luogo("san-frediano", "Basilica di San Frediano", "chiesa"),
    Luogo("torre-delle-ore", "Torre delle Ore", "torre"),
    Luogo("piazza-napoleone", "Piazza Napoleone", "piazza"),
    Luogo("via-fillungo", "Via Fillungo", "via"),
    Luogo("baluardo-san-paolino", "Baluardo San Paolino", "mura"),
    Luogo("museo-nazionale-guinigi", "Museo Nazionale di Villa Guinigi", "museo"),
]

# ---------------------------------------------------------------------------
# Artisti
# ---------------------------------------------------------------------------

ARTISTI: list[Artista] = [
    Artista("artista-puccini", "Giacomo Puccini"),
    Artista("artista-boccherini", "Luigi Boccherini"),
    Artista("artista-civitali", "Matteo Civitali"),
    Artista("artista-catalani", "Alfredo Catalani"),
]

LEGATO_A: list[RelazioneLegatoA] = [
    RelazioneLegatoA("artista-puccini", "casa-puccini"),
    RelazioneLegatoA("artista-puccini", "san-michele-in-foro"),
    RelazioneLegatoA("artista-puccini", "teatro-del-giglio"),
    RelazioneLegatoA("artista-boccherini", "san-michele-in-foro"),
    RelazioneLegatoA("artista-boccherini", "duomo-san-martino"),
    RelazioneLegatoA("artista-civitali", "duomo-san-martino"),
    RelazioneLegatoA("artista-catalani", "teatro-del-giglio"),
]

# ---------------------------------------------------------------------------
# Botteghe — 5 botteghe, ciascuna radicata in un luogo del seed
# ---------------------------------------------------------------------------

BOTTEGHE: list[Bottega] = [
    Bottega(
        "liuteria-lucchese", "Bottega di Liuteria Lucchese", "liuteria", "san-michele-in-foro"
    ),
    Bottega("ceramica-lucca", "Bottega di Ceramica Artistica", "ceramica", "via-fillungo"),
    Bottega("stamperia-lucca", "Antica Stamperia Lucchese", "stampa", "piazza-anfiteatro"),
    Bottega(
        "pasticceria-storica",
        "Pasticceria Storica del Buccellato",
        "pasticceria",
        "piazza-napoleone",
    ),
    Bottega("tessitura-lucca", "Bottega di Tessitura a Mano", "tessitura", "san-frediano"),
]

# ---------------------------------------------------------------------------
# Temi
# ---------------------------------------------------------------------------

TEMI: list[Tema] = [
    Tema("verde", "Verde e giardini"),
    Tema("panorama", "Panorama"),
    Tema("storia", "Storia"),
    Tema("medievale", "Medievale"),
    Tema("gastronomia", "Gastronomia"),
    Tema("arte", "Arte"),
    Tema("silenzio", "Silenzio e contemplazione"),
    Tema("puccini", "Giacomo Puccini e la musica"),
    Tema("musica", "Musica"),
    Tema("romanico", "Romanico"),
    Tema("con-bambini", "Adatto ai bambini"),
    Tema("artigianato", "Artigianato"),
    Tema("liuteria", "Liuteria"),
]

# ---------------------------------------------------------------------------
# Relazioni SEMANTICHE delle botteghe — bottega -> tema, bottega -> artista.
#
# Non di prossimità: sono ciò che rende raggiungibile un artigiano pertinente
# a partire da un artista SENZA passare per `VICINO` (vedi `graph.topology`).
# `BOTTEGA_EVOCA` riusa il tipo di relazione `EVOCA` (come le Esperienze);
# `BOTTEGA_ISPIRATA_DA` introduce il nuovo tipo `ISPIRATA_DA`.
# ---------------------------------------------------------------------------

BOTTEGA_EVOCA: list[RelazioneBottegaEvoca] = [
    RelazioneBottegaEvoca("liuteria-lucchese", "liuteria"),
    RelazioneBottegaEvoca("liuteria-lucchese", "musica"),
    RelazioneBottegaEvoca("liuteria-lucchese", "artigianato"),
    RelazioneBottegaEvoca("ceramica-lucca", "artigianato"),
    RelazioneBottegaEvoca("stamperia-lucca", "artigianato"),
    RelazioneBottegaEvoca("stamperia-lucca", "storia"),
    RelazioneBottegaEvoca("pasticceria-storica", "gastronomia"),
    RelazioneBottegaEvoca("tessitura-lucca", "artigianato"),
    RelazioneBottegaEvoca("tessitura-lucca", "silenzio"),
]

BOTTEGA_ISPIRATA_DA: list[RelazioneIspirataDa] = [
    RelazioneIspirataDa(
        "liuteria-lucchese",
        "artista-puccini",
        "Puccini compose opere; qui un liutaio costruisce i violini che le eseguono.",
    ),
    RelazioneIspirataDa(
        "liuteria-lucchese",
        "artista-boccherini",
        "Boccherini fu virtuoso di violoncello: la stessa famiglia di strumenti "
        "che nasce in questa bottega.",
    ),
]

# ---------------------------------------------------------------------------
# Partner — Wave 3a (marketplace, `docs/DATA_CONTRACTS.md` §5).
#
# 3 partner di esempio, collegati a 3 delle 5 botteghe via `HA_ABBONAMENTO`.
# Deliberatamente NON tutte e 5: le due botteghe restanti (`pasticceria-
# storica`, `tessitura-lucca`) dimostrano il caso "Bottega con `partner_id` su
# un'Esperienza ma nessun nodo `:Partner` collegato" -> `partner_abbonamento_
# attivo` deve restare `True` di default (nessuna leva commerciale attiva
# esplicitamente significa nessun blocco), verificato in `tests/test_source.py`
# e `tests/test_seed_lucca.py`.
#
# `partner-stamperia-lucca` ha `abbonamento_attivo=False` apposta: è il caso
# che deve sparire dai candidati quando l'Experience Engine applica il filtro
# duro (letto da `ExperienceNode.partner_abbonamento_attivo`, MAI qui).
# ---------------------------------------------------------------------------

PARTNERS: list[Partner] = [
    Partner(
        id="partner-liuteria-lucchese",
        nome="Bottega di Liuteria Lucchese — abbonamento presenza",
        abbonamento_attivo=True,
    ),
    Partner(
        id="partner-ceramica-lucca",
        nome="Bottega di Ceramica Artistica — abbonamento presenza",
        abbonamento_attivo=True,
    ),
    Partner(
        id="partner-stamperia-lucca",
        nome="Antica Stamperia Lucchese — abbonamento presenza",
        abbonamento_attivo=False,
    ),
]

HA_ABBONAMENTO: list[RelazioneHaAbbonamento] = [
    RelazioneHaAbbonamento("liuteria-lucchese", "partner-liuteria-lucchese"),
    RelazioneHaAbbonamento("ceramica-lucca", "partner-ceramica-lucca"),
    RelazioneHaAbbonamento("stamperia-lucca", "partner-stamperia-lucca"),
]

# ---------------------------------------------------------------------------
# Esperienze — 22 esperienze (>= 15 richieste), mix voluto di al_chiuso,
# accessibile, durata (20-90 min) e temi, per produrre itinerari DIVERSI a
# seconda del profilo e riscritture credibili su pioggia/affollamento.
# ---------------------------------------------------------------------------

ESPERIENZE: list[ExperienceNode] = [
    ExperienceNode(
        id="exp-passeggiata-mura",
        titolo="Passeggiata sulle Mura rinascimentali",
        place_id="mura-urbane",
        temi=["verde", "panorama", "storia"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-bici-mura",
        titolo="Giro in bicicletta sulle Mura",
        place_id="mura-urbane",
        temi=["verde", "con-bambini", "panorama"],
        durata_min=45,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-mercato-anfiteatro",
        titolo="Il mercato mattutino nell'ovale romano",
        place_id="piazza-anfiteatro",
        temi=["medievale", "storia", "gastronomia"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-salita-torre-guinigi",
        titolo="Salita alla Torre Guinigi tra i lecci",
        place_id="torre-guinigi",
        temi=["panorama", "verde", "storia"],
        durata_min=40,
        al_chiuso=False,
        accessibile=False,
    ),
    ExperienceNode(
        id="exp-duomo-volto-santo",
        titolo="Il Volto Santo e il labirinto del Duomo",
        place_id="duomo-san-martino",
        temi=["arte", "medievale", "silenzio"],
        durata_min=35,
        al_chiuso=True,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-casa-puccini-visita",
        titolo="Le stanze di Giacomo Puccini",
        place_id="casa-puccini",
        temi=["puccini", "musica", "storia"],
        durata_min=50,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-concerto-giglio",
        titolo="Un'aria all'opera del Giglio",
        place_id="teatro-del-giglio",
        temi=["puccini", "musica", "arte"],
        durata_min=90,
        al_chiuso=True,
        accessibile=True,
        prezzo_eur=25.0,
    ),
    ExperienceNode(
        id="exp-facciata-san-michele",
        titolo="La facciata scolpita di San Michele in Foro",
        place_id="san-michele-in-foro",
        temi=["arte", "medievale", "romanico"],
        durata_min=25,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-orto-botanico-silenzio",
        titolo="Un'ora di silenzio tra le piante secolari",
        place_id="orto-botanico",
        temi=["verde", "silenzio"],
        durata_min=45,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-orto-botanico-bambini",
        titolo="Caccia al tesoro botanica per famiglie",
        place_id="orto-botanico",
        temi=["con-bambini", "verde"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-giardino-pfanner",
        titolo="Il giardino barocco di Palazzo Pfanner",
        place_id="palazzo-pfanner",
        temi=["verde", "arte", "panorama"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-mosaico-san-frediano",
        titolo="Il mosaico dorato di San Frediano",
        place_id="san-frediano",
        temi=["arte", "medievale", "romanico"],
        durata_min=25,
        al_chiuso=True,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-meccanismo-torre-ore",
        titolo="Il meccanismo ottocentesco della Torre delle Ore",
        place_id="torre-delle-ore",
        temi=["storia", "panorama"],
        durata_min=35,
        al_chiuso=False,
        accessibile=False,
    ),
    ExperienceNode(
        id="exp-piazza-napoleone",
        titolo="La piazza granducale e i suoi platani",
        place_id="piazza-napoleone",
        temi=["storia", "verde"],
        durata_min=20,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-struscio-fillungo",
        titolo="Struscio serale in via Fillungo",
        place_id="via-fillungo",
        temi=["gastronomia", "artigianato"],
        durata_min=40,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-tramonto-baluardo",
        titolo="Tramonto dal Baluardo San Paolino",
        place_id="baluardo-san-paolino",
        temi=["panorama", "silenzio", "verde"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-collezione-villa-guinigi",
        titolo="La collezione archeologica di Villa Guinigi",
        place_id="museo-nazionale-guinigi",
        temi=["arte", "storia"],
        durata_min=55,
        al_chiuso=True,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-laboratorio-liuteria",
        titolo="Un violino nasce: laboratorio del liutaio",
        place_id="san-michele-in-foro",
        temi=["liuteria", "artigianato", "musica"],
        durata_min=50,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
        partner_id="liuteria-lucchese",
        prezzo_eur=15.0,
        # `prenotabile` è indipendente dalla presenza di un partner (vedi
        # `docs/DATA_CONTRACTS.md` §2): questa è l'unica esperienza del seed
        # canonico resa prenotabile, a dimostrazione che il campo non si
        # deduce mai da `partner_id`/l'abbonamento della bottega.
        prenotabile=True,
    ),
    ExperienceNode(
        id="exp-decorazione-ceramica",
        titolo="Decora la tua ciotola: bottega di ceramica",
        place_id="via-fillungo",
        temi=["artigianato", "con-bambini"],
        durata_min=45,
        al_chiuso=True,
        accessibile=True,
        partner_id="ceramica-lucca",
        prezzo_eur=20.0,
    ),
    ExperienceNode(
        id="exp-torchio-stamperia",
        titolo="Una pagina al torchio: la stamperia storica",
        place_id="piazza-anfiteatro",
        temi=["artigianato", "storia"],
        durata_min=35,
        al_chiuso=True,
        accessibile=False,
        partner_id="stamperia-lucca",
    ),
    ExperienceNode(
        id="exp-buccellato-pasticceria",
        titolo="Il buccellato: il dolce di Lucca",
        place_id="piazza-napoleone",
        temi=["gastronomia", "con-bambini"],
        durata_min=20,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
        partner_id="pasticceria-storica",
        prezzo_eur=8.0,
    ),
    ExperienceNode(
        id="exp-telaio-tessitura",
        titolo="Il telaio a mano: tessitura lucchese",
        place_id="san-frediano",
        temi=["artigianato", "silenzio"],
        durata_min=40,
        al_chiuso=True,
        accessibile=True,
        partner_id="tessitura-lucca",
    ),
]

# ---------------------------------------------------------------------------
# Vicinanze — grafo di prossimità tra luoghi (una riga per coppia)
#
# Corretto dopo la diagnosi su Aura del 2026-07-14: densità media 2,3
# vicini/luogo (una CATENA) con 4 vicoli ciechi (casa-puccini, orto-botanico,
# baluardo-san-paolino, museo-nazionale-guinigi, tutti a 1 solo vicino).
# Lucca dentro le Mura è un centro storico compatto (~1,6 x 1,1 km): quasi
# ogni luogo del seed è raggiungibile a piedi in ~10-15 min da ogni altro.
# `mura-urbane` è un anello che tocca la maggior parte dei luoghi (hub), non
# un nodo di passaggio isolato. Target: densità media >= 4, nessun luogo con
# < 2 vicini (verificato in `tests/test_topology.py`). Le distanze restano
# plausibili (nessuna scorciatoia impossibile), ma la città È piccola.
# ---------------------------------------------------------------------------

VICINO: list[RelazioneVicino] = [
    # mura-urbane: l'anello, hub della rete (8 vicini)
    RelazioneVicino("mura-urbane", "baluardo-san-paolino", 50),
    RelazioneVicino("mura-urbane", "orto-botanico", 100),
    RelazioneVicino("mura-urbane", "piazza-napoleone", 400),
    RelazioneVicino("mura-urbane", "museo-nazionale-guinigi", 450),
    RelazioneVicino("mura-urbane", "palazzo-pfanner", 350),
    RelazioneVicino("mura-urbane", "san-frediano", 400),
    RelazioneVicino("mura-urbane", "torre-guinigi", 600),
    RelazioneVicino("mura-urbane", "casa-puccini", 550),
    # piazza-anfiteatro
    RelazioneVicino("piazza-anfiteatro", "torre-guinigi", 300),
    RelazioneVicino("piazza-anfiteatro", "san-frediano", 250),
    RelazioneVicino("piazza-anfiteatro", "via-fillungo", 150),
    RelazioneVicino("piazza-anfiteatro", "museo-nazionale-guinigi", 500),
    RelazioneVicino("piazza-anfiteatro", "san-michele-in-foro", 350),
    # via-fillungo (l'asse commerciale, hub)
    RelazioneVicino("via-fillungo", "torre-delle-ore", 100),
    RelazioneVicino("via-fillungo", "san-michele-in-foro", 200),
    RelazioneVicino("via-fillungo", "casa-puccini", 200),
    RelazioneVicino("via-fillungo", "torre-guinigi", 250),
    RelazioneVicino("via-fillungo", "piazza-napoleone", 300),
    # san-michele-in-foro (hub centrale)
    RelazioneVicino("san-michele-in-foro", "duomo-san-martino", 300),
    RelazioneVicino("san-michele-in-foro", "piazza-napoleone", 250),
    RelazioneVicino("san-michele-in-foro", "torre-delle-ore", 200),
    RelazioneVicino("san-michele-in-foro", "teatro-del-giglio", 350),
    # duomo-san-martino
    RelazioneVicino("duomo-san-martino", "casa-puccini", 200),
    RelazioneVicino("duomo-san-martino", "torre-delle-ore", 350),
    RelazioneVicino("duomo-san-martino", "piazza-napoleone", 450),
    RelazioneVicino("duomo-san-martino", "museo-nazionale-guinigi", 600),
    # casa-puccini (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("casa-puccini", "teatro-del-giglio", 400),
    # teatro-del-giglio
    RelazioneVicino("teatro-del-giglio", "piazza-napoleone", 100),
    RelazioneVicino("teatro-del-giglio", "torre-delle-ore", 300),
    # piazza-napoleone (hub)
    RelazioneVicino("piazza-napoleone", "torre-delle-ore", 250),
    # torre-delle-ore (hub)
    RelazioneVicino("torre-delle-ore", "torre-guinigi", 300),
    # torre-guinigi
    RelazioneVicino("torre-guinigi", "palazzo-pfanner", 400),
    # palazzo-pfanner (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("palazzo-pfanner", "san-frediano", 150),
    RelazioneVicino("palazzo-pfanner", "baluardo-san-paolino", 300),
    # san-frediano
    RelazioneVicino("san-frediano", "baluardo-san-paolino", 350),
    RelazioneVicino("san-frediano", "orto-botanico", 500),
    # baluardo-san-paolino (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("baluardo-san-paolino", "orto-botanico", 400),
    # orto-botanico (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("orto-botanico", "museo-nazionale-guinigi", 700),
    # museo-nazionale-guinigi (ex vicolo cieco: ora 4 vicini)
]

# ---------------------------------------------------------------------------
# Integrità referenziale — controllata a import-time: il seed è la fonte di
# verità, un errore qui deve rompere subito (fail fast), non silenziosamente
# a runtime dentro Neo4j.
# ---------------------------------------------------------------------------


def _validate() -> None:
    luoghi_ids = {luogo.id for luogo in LUOGHI}
    artisti_ids = {a.id for a in ARTISTI}
    botteghe_ids = {b.id for b in BOTTEGHE}
    temi_ids = {t.id for t in TEMI}
    esperienze_ids = {e.id for e in ESPERIENZE}
    partner_ids = {p.id for p in PARTNERS}

    assert len(luoghi_ids) == len(LUOGHI), "id di Luogo duplicati nel seed"
    assert len(artisti_ids) == len(ARTISTI), "id di Artista duplicati nel seed"
    assert len(botteghe_ids) == len(BOTTEGHE), "id di Bottega duplicati nel seed"
    assert len(temi_ids) == len(TEMI), "id di Tema duplicati nel seed"
    assert len(esperienze_ids) == len(ESPERIENZE), "id di Esperienza duplicati nel seed"
    assert len(partner_ids) == len(PARTNERS), "id di Partner duplicati nel seed"

    for bottega in BOTTEGHE:
        assert bottega.place_id in luoghi_ids, f"{bottega.id}: place_id sconosciuto"

    for esperienza in ESPERIENZE:
        assert esperienza.place_id in luoghi_ids, (
            f"{esperienza.id}: place_id {esperienza.place_id!r} non è un Luogo del seed"
        )
        for tema_id in esperienza.temi:
            assert tema_id in temi_ids, f"{esperienza.id}: tema {tema_id!r} non è nel seed"
        if esperienza.partner_id is not None:
            assert esperienza.partner_id in botteghe_ids, (
                f"{esperienza.id}: partner_id {esperienza.partner_id!r} non è una Bottega del seed"
            )

    for rel in VICINO:
        assert rel.da_id in luoghi_ids, f"VICINO: luogo sconosciuto {rel.da_id!r}"
        assert rel.a_id in luoghi_ids, f"VICINO: luogo sconosciuto {rel.a_id!r}"
        assert rel.metri >= 0, f"VICINO {rel.da_id}->{rel.a_id}: metri negativi"
        assert rel.creato_il.tzinfo is not None, (
            f"VICINO {rel.da_id}->{rel.a_id}: creato_il non timezone-aware "
            "(serve per confrontarlo con datetime.now(UTC) negli snapshot)"
        )

    for rel in LEGATO_A:
        assert rel.artista_id in artisti_ids, f"LEGATO_A: artista sconosciuto {rel.artista_id!r}"
        assert rel.luogo_id in luoghi_ids, f"LEGATO_A: luogo sconosciuto {rel.luogo_id!r}"

    for rel in BOTTEGA_EVOCA:
        assert rel.bottega_id in botteghe_ids, (
            f"BOTTEGA_EVOCA: bottega sconosciuta {rel.bottega_id!r}"
        )
        assert rel.tema_id in temi_ids, f"BOTTEGA_EVOCA: tema sconosciuto {rel.tema_id!r}"

    for rel in BOTTEGA_ISPIRATA_DA:
        assert rel.bottega_id in botteghe_ids, (
            f"BOTTEGA_ISPIRATA_DA: bottega sconosciuta {rel.bottega_id!r}"
        )
        assert rel.artista_id in artisti_ids, (
            f"BOTTEGA_ISPIRATA_DA: artista sconosciuto {rel.artista_id!r}"
        )
        assert rel.racconto, (
            f"BOTTEGA_ISPIRATA_DA {rel.bottega_id}->{rel.artista_id}: racconto vuoto"
        )

    for rel in HA_ABBONAMENTO:
        assert rel.bottega_id in botteghe_ids, (
            f"HA_ABBONAMENTO: bottega sconosciuta {rel.bottega_id!r}"
        )
        assert rel.partner_id in partner_ids, (
            f"HA_ABBONAMENTO: partner sconosciuto {rel.partner_id!r}"
        )
    bottega_con_abbonamento = [rel.bottega_id for rel in HA_ABBONAMENTO]
    assert len(bottega_con_abbonamento) == len(set(bottega_con_abbonamento)), (
        "HA_ABBONAMENTO: una Bottega non può avere più di un Partner"
    )
    assert any(not p.abbonamento_attivo for p in PARTNERS), (
        "seed marketplace: serve almeno un Partner con abbonamento_attivo=False "
        "per poter testare il filtro duro (vedi CLAUDE.md, filtro sui candidati)"
    )


_validate()


# ---------------------------------------------------------------------------
# Lookup — indicizzazioni comode per `graph.source` e `graph.export_cypher`
# ---------------------------------------------------------------------------


def luogo_by_id(place_id: str) -> Luogo | None:
    return next((luogo for luogo in LUOGHI if luogo.id == place_id), None)


def tema_by_id(tema_id: str) -> Tema | None:
    return next((t for t in TEMI if t.id == tema_id), None)


def bottega_by_id(bottega_id: str) -> Bottega | None:
    return next((b for b in BOTTEGHE if b.id == bottega_id), None)


def artisti_per_luogo(place_id: str) -> list[Artista]:
    artisti_ids = {rel.artista_id for rel in LEGATO_A if rel.luogo_id == place_id}
    return [a for a in ARTISTI if a.id in artisti_ids]


def vicini_di(place_id: str) -> list[tuple[str, int]]:
    """Luoghi vicini a `place_id` (relazione trattata come non orientata)."""
    risultato: list[tuple[str, int]] = []
    for rel in VICINO:
        if rel.da_id == place_id:
            risultato.append((rel.a_id, rel.metri))
        elif rel.a_id == place_id:
            risultato.append((rel.da_id, rel.metri))
    return risultato


def partner_by_id(partner_id: str) -> Partner | None:
    return next((p for p in PARTNERS if p.id == partner_id), None)


def abbonamento_attivo_per_bottega(bottega_id: str | None) -> bool:
    """`True` di default (nessun partner = sempre visibile), come
    `ExperienceNode.partner_abbonamento_attivo` in `contracts`. `bottega_id`
    è l'id di `Bottega`, non di `Partner` (`ExperienceNode.partner_id`
    referenzia una Bottega, coerente con la relazione `OFFRE`). Usata da
    `graph.source.SeedCandidateSource` per popolare il booleano denormalizzato
    senza alcuna logica di scoring: è un puro fatto del grafo."""
    if bottega_id is None:
        return True
    rel = next((r for r in HA_ABBONAMENTO if r.bottega_id == bottega_id), None)
    if rel is None:
        return True
    partner = partner_by_id(rel.partner_id)
    if partner is None:
        return True
    return partner.abbonamento_attivo
