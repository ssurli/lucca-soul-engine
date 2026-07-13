"""Sorgenti di candidati per l'AI Experience Engine.

Il grafo PROPONE per CONNESSIONI (fatti leggibili in italiano: un artista
legato al luogo, un tema evocato, una bottega che offre l'esperienza, una
vicinanza a un luogo già in contesto). Non ordina, non filtra su segnale
(pioggia, affollamento, stanchezza) e non assegna punteggi: quello è compito,
rispettivamente, del Signal/Ethical AI Engine e del Recommender, orchestrati
dall'AI Experience Engine — l'unico componente che DECIDE.

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

from contracts import ExperienceNode, GraphCandidate, VisitorContext
from neo4j import Driver, GraphDatabase

from graph.seed_lucca import (
    ARTISTI,
    BOTTEGHE,
    ESPERIENZE,
    LEGATO_A,
    LUOGHI,
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
        for rel in LEGATO_A:
            self._artisti_per_luogo.setdefault(rel.luogo_id, []).append(rel.artista_id)

        self._vicini: dict[str, list[tuple[str, int]]] = {}
        for rel in VICINO:
            self._vicini.setdefault(rel.da_id, []).append((rel.a_id, rel.metri))
            self._vicini.setdefault(rel.a_id, []).append((rel.da_id, rel.metri))

    def candidates(self, ctx: VisitorContext) -> list[GraphCandidate]:
        riferimento = ctx.luoghi_gia_visti[-1] if ctx.luoghi_gia_visti else None
        risultato: list[GraphCandidate] = []
        for esperienza in ESPERIENZE:
            luogo = self._luoghi.get(esperienza.place_id)
            if luogo is None:
                # Non dovrebbe accadere: `graph.seed_lucca._validate()` lo
                # garantisce a import-time. Difensivo, non silenzioso.
                continue
            risultato.append(
                GraphCandidate(
                    experience=esperienza,
                    place_nome=luogo.nome,
                    connessioni=self._connessioni(esperienza, luogo, riferimento),
                    distanza_m=self._distanza(esperienza.place_id, riferimento),
                )
            )
        return risultato

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
            bottega = self._botteghe.get(esperienza.partner_id)
            if bottega is not None:
                frasi.append(f"Offerta da {bottega.nome}, bottega di {bottega.mestiere}.")

        if riferimento is not None and riferimento != luogo.id:
            luogo_riferimento = self._luoghi.get(riferimento)
            if luogo_riferimento is not None:
                for vicino_id, metri in self._vicini.get(luogo.id, []):
                    if vicino_id == riferimento:
                        frasi.append(
                            f"A {metri} m da {luogo_riferimento.nome}, già visitato."
                        )
                        break

        return frasi

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
        params = {
            "temi": [],
            "al_chiuso": None,
            "accessibile": None,
            "vicino_a": vicino_a,
            "raggio_m": None,
        }
        with self._driver.session(database=self._database) as session:
            records = list(session.run(self._query, params))
        return [self._to_candidate(record) for record in records]

    @staticmethod
    def _to_candidate(record: object) -> GraphCandidate:
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
        )
        connessioni: list[str] = []
        for nome in record["artisti_nomi"] or []:
            if nome:
                connessioni.append(f"{nome} è legato a questo luogo.")
        for nome in record["temi_nomi"] or []:
            if nome:
                connessioni.append(f'Evoca il tema "{nome}".')
        for nome in record["botteghe_nomi"] or []:
            if nome:
                connessioni.append(f"Offerta da {nome}.")
        return GraphCandidate(
            experience=esperienza,
            place_nome=record["place_nome"],
            connessioni=connessioni,
            distanza_m=record["distanza_m"],
        )
