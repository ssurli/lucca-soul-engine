"""Sorgenti di candidati per l'AI Experience Engine.

Il grafo PROPONE per CONNESSIONI (fatti leggibili in italiano: un artista
legato al luogo, un tema evocato, una bottega ispirata dal lavoro di un
artista, una vicinanza a un luogo già in contesto). Non ordina, non filtra su
segnale (pioggia, affollamento, stanchezza) e non assegna punteggi: quello è
compito, rispettivamente, del Signal/Ethical AI Engine e del Recommender,
orchestrati dall'AI Experience Engine — l'unico componente che DECIDE.

`connessioni` alimenta la componente "sorpresa" dello score del motore
(`len(connessioni)`). La regola che separa cosa vi entra non è "l'esperienza
ha un partner?" ma "il fatto è SEMANTICO o COMMERCIALE?":
- SEMANTICO (entra in `connessioni`, come qualunque altro fatto del grafo):
  artista legato al luogo, tema evocato, bottega ispirata da un artista
  (`ISPIRATA_DA`) o che evoca un tema (`EVOCA`) — sono relazioni di
  significato, identiche in natura a "artista legato al luogo": un'esperienza
  con più connessioni semantiche vere è, a ragione, più sorprendente;
- COMMERCIALE (va SOLO in `GraphCandidate.attribuzione`, mai in
  `connessioni`): "chi offre l'esperienza" (`OFFRE`). Un partner non deve
  comprare punteggio con la propria sola esistenza — "nessuno spazio è
  acquistabile" (CLAUDE.md). Per questo un'esperienza con partner ma senza
  relazioni semantiche proprie (`ISPIRATA_DA`/`EVOCA` aggiuntivi) genera
  esattamente le stesse `connessioni` di una gemella senza partner (vedi
  `tests/test_source.py`).

Marketplace (Wave 3a): entrambe le implementazioni popolano
`ExperienceNode.partner_abbonamento_attivo` — booleano denormalizzato letto da
`Partner.abbonamento_attivo` risalendo `(:Bottega)-[:HA_ABBONAMENTO]->
(:Partner)` a partire dalla Bottega referenziata da `partner_id`. È un JOIN,
non uno score: il valore risultante è l'UNICO input che l'Experience Engine
legge per decidere presenza/assenza di un candidato (`passa_filtri_duri` in
`services/experience-engine/experience_engine/rules.py`, non toccato qui).

Due implementazioni della stessa interfaccia (`CandidateSource`):
- `SeedCandidateSource` — in-memory sul dataset canonico della città (`graph.dataset.
  DatasetCitta`, scelto da `CITY_SEED` via `graph.registro`). È il percorso
  usato nei test e finché `NEO4J_URI` non è configurato.
- `Neo4jCandidateSource` — stessa interfaccia via driver Neo4j ufficiale,
  contro Aura (`neo4j+s://`) o Neo4j Community locale (`bolt://`): lo schema
  dell'URI vive solo nel `.env`, mai nel codice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from contracts import (
    Curiosita,
    ExperienceNode,
    FasciaApertura,
    GraphCandidate,
    Partner,
    TipoCuriosita,
    VisitorContext,
    decodifica_fasce,
)
from neo4j import Driver, GraphDatabase, Record

from graph.attribuzione import testo_attribuzione
from graph.connessioni import etichette_temi, frasi_connessioni, racconti_con_fonte
from graph.dataset import Artista, Bottega, DatasetCitta, Luogo, Tema
from graph.errors import translate_driver_errors
from graph.registro import dataset_attivo

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
CANDIDATES_QUERY_PATH = _CYPHER_DIR / "10_candidates.cypher"


class CandidateSource(Protocol):
    """Interfaccia comune: dato un `VisitorContext`, propone candidati per
    connessioni. Nessuna delle due implementazioni ordina o decide."""

    def candidates(self, ctx: VisitorContext) -> list[GraphCandidate]: ...


# ---------------------------------------------------------------------------
# In-memory, sul dataset canonico
# ---------------------------------------------------------------------------


class SeedCandidateSource:
    """Implementazione in-memory sul dataset canonico della città.

    `dataset=None` -> dataset attivo (`graph.registro.dataset_attivo`, da
    `CITY_SEED`). Legge SOLO dal dataset ricevuto.

    Restituisce SEMPRE tutte le esperienze del seed (anche quelle nei luoghi
    già visti in `ctx.luoghi_gia_visti`: filtrarle qui sarebbe una decisione,
    non una proposta — spetta all'AI Experience Engine). Usa il contesto solo
    per arricchire le `connessioni` con fatti di prossimità al riferimento più
    recente del visitatore.
    """

    def __init__(self, dataset: DatasetCitta | None = None) -> None:
        ds = dataset if dataset is not None else dataset_attivo()
        self._esperienze = ds.esperienze
        self._luoghi: dict[str, Luogo] = {luogo.id: luogo for luogo in ds.luoghi}
        self._artisti: dict[str, Artista] = {a.id: a for a in ds.artisti}
        self._botteghe: dict[str, Bottega] = {b.id: b for b in ds.botteghe}
        self._temi: dict[str, Tema] = {t.id: t for t in ds.temi}

        self._artisti_per_luogo: dict[str, list[str]] = {}
        self._legati_per_luogo: dict[str, list[tuple[str, str | None, str | None]]] = {}
        for legato in ds.legato_a:
            self._artisti_per_luogo.setdefault(legato.luogo_id, []).append(legato.artista_id)
            self._legati_per_luogo.setdefault(legato.luogo_id, []).append(
                (self._artisti[legato.artista_id].nome, legato.racconto, legato.fonte)
            )

        self._vicini: dict[str, list[tuple[str, int]]] = {}
        for vicino in ds.vicino:
            self._vicini.setdefault(vicino.da_id, []).append((vicino.a_id, vicino.metri))
            self._vicini.setdefault(vicino.a_id, []).append((vicino.da_id, vicino.metri))

        # Relazioni SEMANTICHE della bottega (non di prossimità): temi che
        # evoca oltre a quelli della singola esperienza, e artisti il cui
        # lavoro la ispira (con il racconto già in italiano).
        self._bottega_evoca: dict[str, list[str]] = {}
        for evoca in ds.bottega_evoca:
            self._bottega_evoca.setdefault(evoca.bottega_id, []).append(evoca.tema_id)

        self._bottega_ispirata_da: dict[str, list[tuple[str, str]]] = {}
        for ispirata in ds.bottega_ispirata_da:
            self._bottega_ispirata_da.setdefault(ispirata.bottega_id, []).append(
                (ispirata.artista_id, ispirata.racconto)
            )

        # Marketplace (Wave 3a): stato dell'abbonamento del Partner collegato
        # alla Bottega via `HA_ABBONAMENTO`. Fatto puro del grafo (JOIN),
        # nessuna logica di scoring qui.
        self._partners: dict[str, Partner] = {p.id: p for p in ds.partners}
        self._ha_abbonamento: dict[str, str] = {
            rel.bottega_id: rel.partner_id for rel in ds.ha_abbonamento
        }

    def candidates(self, ctx: VisitorContext) -> list[GraphCandidate]:
        riferimento = ctx.luoghi_gia_visti[-1] if ctx.luoghi_gia_visti else None
        risultato: list[GraphCandidate] = []
        for esperienza in self._esperienze:
            luogo = self._luoghi.get(esperienza.place_id)
            if luogo is None:
                # Non dovrebbe accadere: la validazione del dataset lo
                # garantisce a import-time. Difensivo, non silenzioso.
                continue
            # Booleano denormalizzato (Wave 3a): un JOIN sul grafo, non uno
            # score. `model_copy` non muta l'istanza condivisa nel dataset.
            esperienza_effettiva = esperienza.model_copy(
                update={
                    "partner_abbonamento_attivo": self._abbonamento_attivo(esperienza.partner_id)
                }
            )
            vicinanza = self._vicinanza(luogo, riferimento)
            risultato.append(
                GraphCandidate(
                    experience=esperienza_effettiva,
                    place_nome=luogo.nome,
                    connessioni=self._connessioni(esperienza, luogo, riferimento),
                    distanza_m=self._distanza(esperienza.place_id, riferimento),
                    attribuzione=self._attribuzione(esperienza),
                    place_articolo=luogo.articolo,
                    racconti=racconti_con_fonte(
                        legati=self._legati_per_luogo.get(luogo.id, []),
                        temi_esperienza=esperienza.temi,
                        frasi_temi={t.id: (t.frase, t.fonte) for t in self._temi.values()},
                    ),
                    temi_etichette=etichette_temi(
                        esperienza.temi,
                        {t.id: t.etichetta for t in self._temi.values() if t.mostra_etichetta},
                    ),
                    vicinanza_nome=vicinanza[1].nome if vicinanza else None,
                    vicinanza_articolo=vicinanza[1].articolo if vicinanza else None,
                    curiosita=list(luogo.curiosita),
                )
            )
        return risultato

    def _abbonamento_attivo(self, bottega_id: str | None) -> bool:
        """`True` di default: nessun partner (`bottega_id is None`), oppure
        una Bottega senza `HA_ABBONAMENTO` collegato, sono sempre visibili.
        Solo un `Partner` esplicitamente presente con `abbonamento_attivo =
        False` fa scendere il booleano — coerente con la query Cypher
        (`cypher/10_candidates.cypher`) e con `docs/DATA_CONTRACTS.md` §5."""
        if bottega_id is None:
            return True
        partner_id = self._ha_abbonamento.get(bottega_id)
        if partner_id is None:
            return True
        partner = self._partners.get(partner_id)
        if partner is None:
            return True
        return partner.abbonamento_attivo

    def _connessioni(
        self, esperienza: ExperienceNode, luogo: Luogo, riferimento: str | None
    ) -> list[str]:
        artisti_nomi = [self._artisti[a].nome for a in self._artisti_per_luogo.get(luogo.id, [])]
        racconti: list[tuple[str, str]] = []
        temi_bottega: list[tuple[str, str]] = []
        if esperienza.partner_id is not None:
            racconti = list(self._bottega_ispirata_da.get(esperienza.partner_id, []))
            for tema_id in self._bottega_evoca.get(esperienza.partner_id, []):
                tema = self._temi.get(tema_id)
                if tema is not None:
                    temi_bottega.append((tema_id, tema.nome))

        trovata = self._vicinanza(luogo, riferimento)
        vicinanza = (trovata[0], trovata[1].nome) if trovata else None

        return frasi_connessioni(
            luogo_nome=luogo.nome,
            artisti_nomi=artisti_nomi,
            temi_esperienza=esperienza.temi,
            nomi_temi={t.id: t.nome for t in self._temi.values()},
            racconti_ispirazione=racconti,
            temi_bottega=temi_bottega,
            riferimento=vicinanza,
        )

    def _vicinanza(self, luogo: Luogo, riferimento: str | None) -> tuple[int, Luogo] | None:
        """(metri, luogo già visitato) se `luogo` è VICINO al riferimento e non
        coincide con esso: la condizione unica della frase "A … m da …, già
        visitato" e dei campi `vicinanza_*`."""
        if riferimento is None or riferimento == luogo.id:
            return None
        luogo_riferimento = self._luoghi.get(riferimento)
        metri_vicino = [m for v, m in self._vicini.get(luogo.id, []) if v == riferimento]
        if luogo_riferimento is None or not metri_vicino:
            return None
        return (min(metri_vicino), luogo_riferimento)

    def _attribuzione(self, esperienza: ExperienceNode) -> str | None:
        """Fatto commerciale trasparente ("chi offre l'esperienza"), separato
        da `connessioni`: non deve mai contribuire alla "sorpresa" contata
        dal motore (`len(connessioni)`). `None` se l'esperienza non ha un
        partner (`OFFRE`)."""
        if esperienza.partner_id is None:
            return None
        bottega = self._botteghe.get(esperienza.partner_id)
        if bottega is None:
            return None
        return testo_attribuzione(bottega.nome, bottega.mestiere, bottega.fittizio)

    def _distanza(self, place_id: str, riferimento: str | None) -> int | None:
        if riferimento is None:
            return None
        if riferimento == place_id:
            return 0
        for vicino_id, metri in self._vicini.get(place_id, []):
            if vicino_id == riferimento:
                return metri
        return None


# ---------------------------------------------------------------------------
# Via Neo4j (Aura o locale), stessa interfaccia
# ---------------------------------------------------------------------------


def _sospesa_da_record(record: Record) -> bool:
    """Fail-closed: solo `None` (proprietà assente) è `False`; solo un `bool`
    vero e proprio è accettato. Stringhe e int (anche 0/1: in Python `bool` è
    sottoclasse di `int`, qui si rifiuta l'int) sollevano ValueError."""
    grezzo = record["sospesa"]
    if grezzo is None:
        return False
    if not isinstance(grezzo, bool):
        raise ValueError(
            f"sospesa dell'esperienza {record['id']!r}: atteso un booleano, "
            f"trovato {type(grezzo).__name__} {grezzo!r}"
        )
    return grezzo


def _curiosita_da_record(record: Record) -> list[Curiosita]:
    """Ricompone le curiosità dalle tre liste parallele del luogo, nell'ordine
    del seed. Fail-closed: liste di lunghezza diversa, tipo ignoto o fonte
    vuota sollevano ValueError (`Curiosita` valida tipo, fonte e "Si racconta"
    delle leggende). Proprietà assenti (`None`, grafo non ricaricato) = nessuna."""
    testi = record["curiosita_testi"] or []
    tipi = record["curiosita_tipi"] or []
    fonti = record["curiosita_fonti"] or []
    if not (len(testi) == len(tipi) == len(fonti)):
        raise ValueError(
            f"curiosità del luogo {record['place_id']!r}: liste parallele di lunghezza "
            f"diversa (testi={len(testi)}, tipi={len(tipi)}, fonti={len(fonti)})"
        )
    return [
        Curiosita(testo=testo, tipo=TipoCuriosita(tipo), fonte=fonte)
        for testo, tipo, fonte in zip(testi, tipi, fonti, strict=True)
    ]


def _fasce_da_record(record: Record) -> list[FasciaApertura]:
    """Fail-closed: solo `None` (proprietà assente) è `[]`; ogni valore non
    `list` solleva ValueError. Le fasce malformate le rifiuta `decodifica_fasce`."""
    grezzo = record["orari_apertura"]
    if grezzo is None:
        return []
    if not isinstance(grezzo, list):
        raise ValueError(
            f"orari_apertura dell'esperienza {record['id']!r}: attesa una lista, "
            f"trovato {type(grezzo).__name__} {grezzo!r}"
        )
    return decodifica_fasce(grezzo)


class Neo4jCandidateSource:
    """Stessa interfaccia di `SeedCandidateSource`, letta da Neo4j.

    URI/credenziali arrivano SEMPRE dal costruttore (mai hardcoded qui): chi
    la istanzia le legge da `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD`
    / `NEO4J_DATABASE` (vedi `graph.env.load_neo4j_config`). Nessun `if
    local/cloud`: lo schema `neo4j+s://` (Aura) o `bolt://` (locale) sta solo
    nella stringa URI passata da chi chiama.

    La query è versionata in `cypher/10_candidates.cypher` e caricata da
    file, non incorporata nel codice.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database
        self._query = CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")

    @classmethod
    def from_credentials(
        cls, uri: str, username: str, password: str, database: str = "neo4j"
    ) -> Neo4jCandidateSource:
        # URI malformato = errore di configurazione, non indisponibilita'.
        driver = GraphDatabase.driver(uri, auth=(username, password))
        return cls(driver, database=database)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jCandidateSource:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def candidates(self, ctx: VisitorContext) -> list[GraphCandidate]:
        vicino_a = ctx.luoghi_gia_visti[-1] if ctx.luoghi_gia_visti else None
        params: dict[str, object] = {
            "temi": [],
            "al_chiuso": None,
            "accessibile": None,
            "vicino_a": vicino_a,
            "raggio_m": None,
        }
        with translate_driver_errors(), self._driver.session(database=self._database) as session:
            records = list(session.run(self._query, params))
        return [self._to_candidate(record, vicino_a) for record in records]

    @staticmethod
    def _to_candidate(record: Record, vicino_a: str | None = None) -> GraphCandidate:
        esperienza = ExperienceNode(
            id=record["id"],
            titolo=record["titolo"],
            place_id=record["place_id"],
            temi=list(record["temi"]),
            durata_min=record["durata_min"],
            al_chiuso=record["al_chiuso"],
            accessibile=record["accessibile"],
            alimenta_memoria=record["alimenta_memoria"],
            partner_id=record["partner_id"],
            prezzo_eur=record["prezzo_eur"],
            # Booleano denormalizzato (Wave 3a): la query ha già fatto il
            # JOIN su `Partner.abbonamento_attivo` via `HA_ABBONAMENTO`; qui
            # si copia soltanto il risultato, nessuna logica aggiuntiva.
            partner_abbonamento_attivo=record["partner_abbonamento_attivo"],
            # `prenotabile` è una proprietà propria del nodo `:Esperienza`
            # (non derivata da partner/abbonamento, vedi `docs/DATA_CONTRACTS.md`
            # §2): si copia il valore così come scritto dal seed.
            prenotabile=record["prenotabile"],
            # Fail-closed: una fascia malformata o un valore non-lista
            # solleva ValueError, non diventa lista vuota (= "sempre
            # aperto"). Solo `None` (proprietà assente) è `[]`.
            orari_apertura=_fasce_da_record(record),
            sospesa=_sospesa_da_record(record),
        )
        # Fatti SEMANTICI (artisti, temi, `ISPIRATA_DA`, `EVOCA` della bottega) e
        # prossimità al luogo già visitato: testo e ORDINE sono imposti da
        # `graph.connessioni`, identici al seed per costruzione (la query non
        # garantisce alcun ordine nei `collect`).
        temi_grezzi = [t for t in record["temi_evocati"] or [] if t and t["nome"]]
        nomi_temi = {t["id"]: t["nome"] for t in temi_grezzi}
        racconti = [
            (r["artista_id"], r["racconto"])
            for r in record["racconti_ispirazione"] or []
            if r and r["racconto"]
        ]
        temi_bottega = [
            (t["id"], t["nome"])
            for t in record["temi_bottega"] or []
            if t and t["id"] and t["nome"]
        ]
        metri = record["distanza_m"]
        nome_riferimento = record["riferimento_nome"]
        con_vicinanza = (
            metri is not None
            and bool(nome_riferimento)
            and vicino_a is not None
            and record["place_id"] != vicino_a
        )
        vicinanza = (metri, nome_riferimento) if con_vicinanza else None
        connessioni = frasi_connessioni(
            luogo_nome=record["place_nome"],
            artisti_nomi=[n for n in record["artisti_nomi"] or [] if n],
            temi_esperienza=list(record["temi"] or []),
            nomi_temi=nomi_temi,
            racconti_ispirazione=racconti,
            temi_bottega=temi_bottega,
            riferimento=vicinanza,
        )
        # `botteghe` NON entra in `connessioni` (contate nello score del
        # motore): alimenta solo `attribuzione`, fatto commerciale separato e
        # non conteggiato — "nessuno spazio è acquistabile".
        # Le entry hanno `nome` nullo quando l'OPTIONAL MATCH non trova
        # bottega: si scartano qui. `fittizio` assente su un grafo non
        # ricaricato e' gia' `true` (coalesce nella query).
        # Piu' botteghe possibili: il `collect` non e' ordinato, quindi si sceglie
        # in modo deterministico (nome casefold, poi nome) PRIMA di attribuire.
        botteghe = sorted(
            (b for b in (record["botteghe"] or []) if b and b.get("nome")),
            key=lambda b: (b["nome"].casefold(), b["nome"]),
        )
        attribuzione = (
            testo_attribuzione(
                botteghe[0]["nome"],
                botteghe[0].get("mestiere") or "",
                bool(botteghe[0].get("fittizio", True)),
            )
            if botteghe
            else None
        )
        # Campi di SOLO TESTO per il motivo, costruiti dagli stessi helper del
        # seed. Un grafo non ancora ricaricato (proprietà assenti) degrada:
        # etichetta = nome con l'iniziale minuscola (come il default del
        # dataset), nessun racconto, nessun articolo.
        etichette = {
            t["id"]: (t.get("etichetta") or t["nome"][:1].lower() + t["nome"][1:])
            for t in temi_grezzi
            # `mostra_etichetta` e' scritta esplicitamente dal seed; il ripiego
            # vale solo se la proprieta' MANCA (grafo non ricaricato = mostrato).
            if t.get("mostra_etichetta") is not False
        }
        frasi_temi = {t["id"]: (t.get("frase"), t.get("fonte")) for t in temi_grezzi}
        legati = [
            (g["nome"], g.get("racconto"), g.get("fonte"))
            for g in record["legati_racconti"] or []
            if g and g.get("nome")
        ]
        return GraphCandidate(
            experience=esperienza,
            place_nome=record["place_nome"],
            connessioni=connessioni,
            distanza_m=record["distanza_m"],
            attribuzione=attribuzione,
            place_articolo=record["place_articolo"],
            racconti=racconti_con_fonte(
                legati=legati,
                temi_esperienza=list(record["temi"] or []),
                frasi_temi=frasi_temi,
            ),
            temi_etichette=etichette_temi(list(record["temi"] or []), etichette),
            vicinanza_nome=nome_riferimento if con_vicinanza else None,
            vicinanza_articolo=record["riferimento_articolo"] if con_vicinanza else None,
            curiosita=_curiosita_da_record(record),
        )
