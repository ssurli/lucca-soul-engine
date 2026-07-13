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
- `EVOCA` da `ExperienceNode.temi` (id di `Tema`);
- `OFFRE` da `ExperienceNode.partner_id` (id di `Bottega`, quando presente).

Relazioni esplicite (non derivabili da un solo campo): `VICINO` tra Luoghi,
`LEGATO_A` tra Artista e Luogo.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts import ExperienceNode

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
    """`(:Luogo)-[:VICINO {metri}]->(:Luogo)`. Non direzionale nel dominio
    (la distanza vale nei due sensi): una riga sola per coppia, le API di
    lettura (`graph.source`, `cypher/10_candidates.cypher`) la trattano come
    non orientata."""

    da_id: str
    a_id: str
    metri: int


@dataclass(frozen=True)
class RelazioneLegatoA:
    """`(:Artista)-[:LEGATO_A]->(:Luogo)`."""

    artista_id: str
    luogo_id: str


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
# ---------------------------------------------------------------------------

VICINO: list[RelazioneVicino] = [
    RelazioneVicino("mura-urbane", "baluardo-san-paolino", 50),
    RelazioneVicino("mura-urbane", "orto-botanico", 100),
    RelazioneVicino("mura-urbane", "piazza-napoleone", 400),
    RelazioneVicino("mura-urbane", "museo-nazionale-guinigi", 500),
    RelazioneVicino("piazza-anfiteatro", "torre-guinigi", 250),
    RelazioneVicino("piazza-anfiteatro", "san-frediano", 200),
    RelazioneVicino("piazza-anfiteatro", "via-fillungo", 100),
    RelazioneVicino("via-fillungo", "torre-delle-ore", 150),
    RelazioneVicino("via-fillungo", "san-michele-in-foro", 200),
    RelazioneVicino("san-michele-in-foro", "duomo-san-martino", 300),
    RelazioneVicino("san-michele-in-foro", "piazza-napoleone", 250),
    RelazioneVicino("duomo-san-martino", "casa-puccini", 200),
    RelazioneVicino("teatro-del-giglio", "piazza-napoleone", 100),
    RelazioneVicino("teatro-del-giglio", "san-michele-in-foro", 350),
    RelazioneVicino("palazzo-pfanner", "san-frediano", 150),
    RelazioneVicino("palazzo-pfanner", "torre-guinigi", 400),
    RelazioneVicino("torre-guinigi", "torre-delle-ore", 300),
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

    assert len(luoghi_ids) == len(LUOGHI), "id di Luogo duplicati nel seed"
    assert len(artisti_ids) == len(ARTISTI), "id di Artista duplicati nel seed"
    assert len(botteghe_ids) == len(BOTTEGHE), "id di Bottega duplicati nel seed"
    assert len(temi_ids) == len(TEMI), "id di Tema duplicati nel seed"
    assert len(esperienze_ids) == len(ESPERIENZE), "id di Esperienza duplicati nel seed"

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

    for rel in LEGATO_A:
        assert rel.artista_id in artisti_ids, f"LEGATO_A: artista sconosciuto {rel.artista_id!r}"
        assert rel.luogo_id in luoghi_ids, f"LEGATO_A: luogo sconosciuto {rel.luogo_id!r}"


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
