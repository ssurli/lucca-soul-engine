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
- `SeedCandidateSource` — in-memory sul dataset canonico (`graph.seed_lucca`).
  È il percorso usato nei test e finché `NEO4J_URI` non è configurato.
- `Neo4jCandidateSource` — stessa interfaccia via driver Neo4j ufficiale,
  contro Aura (`neo4j+s://`) o Neo4j Community locale (`bolt://`): lo schema
  dell'URI vive solo nel `.env`, mai nel codice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from contracts import ExperienceNode, GraphCandidate, Partner, VisitorContext
from neo4j import Driver, GraphDatabase, Record

from graph.errors import translate_driver_errors
from graph.seed_lucca import (
    ARTISTI,
    BOTTEGA_EVOCA,
    BOTTEGA_ISPIRATA_DA,
    BOTTEGHE,
    ESPERIENZE,
    HA_ABBONAMENTO,
    LEGATO_A,
    LUOGHI,
    PARTNERS,
    TEMI,
    VICINO,
    Artista,
    Bottega,
    Luogo,
    Tema,
)

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
    """Implementazione in-memory sul dataset canonico `graph.seed_lucca`.

    Restituisce SEMPRE tutte le esperienze del seed (anche quelle nei luoghi
    già visti in `ctx.luoghi_gia_visti`: filtrarle qui sarebbe una decisione,
    non una proposta — spetta all'AI Experience Engine). Usa il contesto solo
    per arricchire le `connessioni` con fatti di prossimità al riferimento più
    recente del visitatore.
    """

    def __init__(self) -> None:
        self._luoghi: dict[str, Luogo] = {luogo.id: luogo for luogo in LUOGHI}
        self._artisti: dict[str, Artista] = {a.id: a for a in ARTISTI}
        self._botteghe: dict[str, Bottega] = {b.id: b for b in BOTTEGHE}
        self._temi: dict[str, Tema] = {t.id: t for t in TEMI}

        self._artisti_per_luogo: dict[str, list[str]] = {}
        for legato in LEGATO_A:
            self._artisti_per_luogo.setdefault(legato.luogo_id, []).append(legato.artista_id)

        self._vicini: dict[str, list[tuple[str, int]]] = {}
        for vicino in VICINO:
            self._vicini.setdefault(vicino.da_id, []).append((vicino.a_id, vicino.metri))
            self._vicini.setdefault(vicino.a_id, []).append((vicino.da_id, vicino.metri))

        # Relazioni SEMANTICHE della bottega (non di prossimità): temi che
        # evoca oltre a quelli della singola esperienza, e artisti il cui
        # lavoro la ispira (con il racconto già in italiano).
        self._bottega_evoca: dict[str, list[str]] = {}
        for evoca in BOTTEGA_EVOCA:
            self._bottega_evoca.setdefault(evoca.bottega_id, []).append(evoca.tema_id)

        self._bottega_ispirata_da: dict[str, list[tuple[str, str]]] = {}
        for ispirata in BOTTEGA_ISPIRATA_DA:
            self._bottega_ispirata_da.setdefault(ispirata.bottega_id, []).append(
                (ispirata.artista_id, ispirata.racconto)
            )

        # Marketplace (Wave 3a): stato dell'abbonamento del Partner collegato
        # alla Bottega via `HA_ABBONAMENTO`. Fatto puro del grafo (JOIN),
        # nessuna logica di scoring qui.
        self._partners: dict[str, Partner] = {p.id: p for p in PARTNERS}
        self._ha_abbonamento: dict[str, str] = {
            rel.bottega_id: rel.partner_id for rel in HA_ABBONAMENTO
        }

    def candidates(self, ctx: VisitorContext) -> list[GraphCandidate]:
        riferimento = ctx.luoghi_gia_visti[-1] if ctx.luoghi_gia_visti else None
        risultato: list[GraphCandidate] = []
        for esperienza in ESPERIENZE:
            luogo = self._luoghi.get(esperienza.place_id)
            if luogo is None:
                # Non dovrebbe accadere: `graph.seed_lucca._validate()` lo
                # garantisce a import-time. Difensivo, non silenzioso.
                continue
            # Booleano denormalizzato (Wave 3a): un JOIN sul grafo, non uno
            # score. `model_copy` non muta l'istanza condivisa in `ESPERIENZE`.
            esperienza_effettiva = esperienza.model_copy(
                update={
                    "partner_abbonamento_attivo": self._abbonamento_attivo(esperienza.partner_id)
                }
            )
            risultato.append(
                GraphCandidate(
                    experience=esperienza_effettiva,
                    place_nome=luogo.nome,
                    connessioni=self._connessioni(esperienza, luogo, riferimento),
                    distanza_m=self._distanza(esperienza.place_id, riferimento),
                    attribuzione=self._attribuzione(esperienza),
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
        frasi: list[str] = []

        for artista_id in self._artisti_per_luogo.get(luogo.id, []):
            artista = self._artisti[artista_id]
            frasi.append(f"{artista.nome} è legato a {luogo.nome}.")

        for tema_id in esperienza.temi:
            tema = self._temi.get(tema_id)
            if tema is not None:
                frasi.append(f'Evoca il tema "{tema.nome}".')

        if esperienza.partner_id is not None:
            frasi.extend(self._catena_semantica_bottega(esperienza.partner_id, esperienza.temi))

        if riferimento is not None and riferimento != luogo.id:
            luogo_riferimento = self._luoghi.get(riferimento)
            if luogo_riferimento is not None:
                for vicino_id, metri in self._vicini.get(luogo.id, []):
                    if vicino_id == riferimento:
                        frasi.append(f"A {metri} m da {luogo_riferimento.nome}, già visitato.")
                        break

        return frasi

    def _catena_semantica_bottega(self, bottega_id: str, temi_esperienza: list[str]) -> list[str]:
        """Fatti SEMANTICI della bottega (`ISPIRATA_DA`, `EVOCA`): non fatti
        commerciali (quello è `_attribuzione`). Sono ciò che rende
        percorribile "Puccini -> ... -> liutaio -> violino" per sole
        connessioni di significato (vedi `graph.topology`). Non duplica i
        temi che l'esperienza evoca già."""
        frasi: list[str] = []

        for _artista_id, racconto in self._bottega_ispirata_da.get(bottega_id, []):
            frasi.append(racconto)

        for tema_id in self._bottega_evoca.get(bottega_id, []):
            if tema_id in temi_esperienza:
                continue
            tema = self._temi.get(tema_id)
            if tema is not None:
                frasi.append(f'La bottega evoca anche il tema "{tema.nome}".')

        return frasi

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
        return f"Offerta da {bottega.nome}, bottega di {bottega.mestiere}."

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
        return [self._to_candidate(record) for record in records]

    @staticmethod
    def _to_candidate(record: Record) -> GraphCandidate:
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
        )
        connessioni: list[str] = []
        for nome in record["artisti_nomi"] or []:
            if nome:
                connessioni.append(f"{nome} è legato a questo luogo.")
        for nome in record["temi_nomi"] or []:
            if nome:
                connessioni.append(f'Evoca il tema "{nome}".')
        # `racconti_ispirazione` (ISPIRATA_DA) e `temi_bottega` (EVOCA
        # Bottega->Tema) sono fatti SEMANTICI, non commerciali: entrano in
        # `connessioni` come qualunque altro fatto del grafo (vedi docstring
        # di modulo). Filtrano i duplicati con i temi già evocati da `e`.
        for racconto in record["racconti_ispirazione"] or []:
            if racconto:
                connessioni.append(racconto)
        temi_esperienza = set(record["temi"] or [])
        for entry in record["temi_bottega"] or []:
            tema_id = entry.get("id") if entry else None
            tema_nome = entry.get("nome") if entry else None
            if tema_id and tema_nome and tema_id not in temi_esperienza:
                connessioni.append(f'La bottega evoca anche il tema "{tema_nome}".')
        # `botteghe_nomi` NON entra in `connessioni` (contate nello score del
        # motore): alimenta solo `attribuzione`, fatto commerciale separato e
        # non conteggiato — "nessuno spazio è acquistabile".
        botteghe_nomi = [nome for nome in (record["botteghe_nomi"] or []) if nome]
        attribuzione = f"Offerta da {botteghe_nomi[0]}." if botteghe_nomi else None
        return GraphCandidate(
            experience=esperienza,
            place_nome=record["place_nome"],
            connessioni=connessioni,
            distanza_m=record["distanza_m"],
            attribuzione=attribuzione,
        )
