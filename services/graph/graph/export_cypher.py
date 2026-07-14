"""`python -m graph.export_cypher` — rigenera il Cypher versionato dal seed.

`graph.seed_lucca` è l'UNICA fonte di verità del dataset. Questo modulo la
traduce in due file committati in `cypher/`:

- `00_schema.cypher` — vincoli di unicità sugli `id` di ogni nodo (idempotente:
  `CREATE CONSTRAINT ... IF NOT EXISTS`);
- `01_seed_lucca.cypher` — `MERGE` di nodi e relazioni (idempotente: rieseguibile
  da zero senza duplicare nulla).

Perché generarlo invece di scriverlo a mano: replicare il motore su un'altra
città (Siena, Ferrara...) significa scrivere un nuovo `seed_<città>.py` e
rilanciare questo comando — la struttura del Cypher non cambia mai a mano.

Uso (dalla radice del repo, dopo `pip install -e services/graph`):

    python -m graph.export_cypher
"""

from __future__ import annotations

from pathlib import Path

from contracts import ExperienceNode

from graph.seed_lucca import (
    ARTISTI,
    BOTTEGA_EVOCA,
    BOTTEGA_ISPIRATA_DA,
    BOTTEGHE,
    ESPERIENZE,
    LEGATO_A,
    LUOGHI,
    TEMI,
    VICINO,
)

CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
SCHEMA_FILE = CYPHER_DIR / "00_schema.cypher"
SEED_FILE = CYPHER_DIR / "01_seed_lucca.cypher"

_HEADER = (
    "// File GENERATO da `python -m graph.export_cypher`.\n"
    "// Non modificare a mano: la fonte di verità è `graph/seed_lucca.py`.\n"
)

# Nodi previsti dallo schema (docs/DATA_CONTRACTS.md §2): `Evento` e `Memoria`
# non hanno seed in questa wave (arrivano rispettivamente con i segnali reali
# e con `urban-memory-engineer`, Wave 2) ma il vincolo di unicità è già qui
# per non riaprire lo schema più avanti.
_NODE_LABELS_WITH_ID = [
    "Luogo",
    "Artista",
    "Bottega",
    "Tema",
    "Esperienza",
    "Evento",
    "Memoria",
]


def _esc(value: str) -> str:
    """Escape minimale per stringhe Cypher tra apici singoli."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _cypher_str(value: str) -> str:
    return f"'{_esc(value)}'"


def _cypher_str_or_null(value: str | None) -> str:
    return "NULL" if value is None else _cypher_str(value)


def _cypher_number_or_null(value: float | int | None) -> str:
    return "NULL" if value is None else repr(value)


def _cypher_bool(value: bool) -> str:
    return "true" if value else "false"


def _cypher_str_list(values: list[str]) -> str:
    return "[" + ", ".join(_cypher_str(v) for v in values) + "]"


_RELATION_TYPES_COMMENT = (
    "// Tipi di relazione del grafo (documentazione, nessun vincolo Neo4j li\n"
    "// richiede esplicitamente):\n"
    "//   (:Artista)-[:LEGATO_A]->(:Luogo)\n"
    "//   (:Luogo)-[:VICINO {metri}]->(:Luogo)              -- non orientata nel dominio\n"
    "//   (:Bottega)-[:OFFRE]->(:Esperienza)\n"
    "//   (:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)\n"
    "//   (:Esperienza)-[:EVOCA]->(:Tema)\n"
    "//   (:Bottega)-[:EVOCA]->(:Tema)                      -- SEMANTICA, non di prossimità\n"
    "//   (:Bottega)-[:ISPIRATA_DA {racconto}]->(:Artista)  -- SEMANTICA, NUOVA: introdotta\n"
    "//     perché la Bottega di Liuteria fosse raggiungibile da Puccini per sole\n"
    "//     connessioni semantiche, senza passare per VICINO (vedi graph/topology.py).\n"
)


def build_schema() -> str:
    lines = [_HEADER, "", _RELATION_TYPES_COMMENT]
    for label in _NODE_LABELS_WITH_ID:
        lines.append(
            f"CREATE CONSTRAINT {label.lower()}_id_unique IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE;"
        )
    return "\n".join(lines) + "\n"


def _luogo_statement(luogo) -> str:
    return (
        f"MERGE (l:Luogo {{id: {_cypher_str(luogo.id)}}})\n"
        f"SET l.nome = {_cypher_str(luogo.nome)}, l.categoria = {_cypher_str(luogo.categoria)};"
    )


def _artista_statement(artista) -> str:
    return (
        f"MERGE (a:Artista {{id: {_cypher_str(artista.id)}}})\n"
        f"SET a.nome = {_cypher_str(artista.nome)};"
    )


def _bottega_statement(bottega) -> str:
    return (
        f"MERGE (b:Bottega {{id: {_cypher_str(bottega.id)}}})\n"
        f"SET b.nome = {_cypher_str(bottega.nome)}, "
        f"b.mestiere = {_cypher_str(bottega.mestiere)}, "
        f"b.place_id = {_cypher_str(bottega.place_id)};"
    )


def _tema_statement(tema) -> str:
    return (
        f"MERGE (t:Tema {{id: {_cypher_str(tema.id)}}})\n"
        f"SET t.nome = {_cypher_str(tema.nome)};"
    )


def _esperienza_statement(e: ExperienceNode) -> str:
    return (
        f"MERGE (e:Esperienza {{id: {_cypher_str(e.id)}}})\n"
        f"SET e.titolo = {_cypher_str(e.titolo)},\n"
        f"    e.place_id = {_cypher_str(e.place_id)},\n"
        f"    e.temi = {_cypher_str_list(e.temi)},\n"
        f"    e.durata_min = {e.durata_min},\n"
        f"    e.al_chiuso = {_cypher_bool(e.al_chiuso)},\n"
        f"    e.accessibile = {_cypher_bool(e.accessibile)},\n"
        f"    e.alimenta_memoria = {_cypher_bool(e.alimenta_memoria)},\n"
        f"    e.partner_id = {_cypher_str_or_null(e.partner_id)},\n"
        f"    e.prezzo_eur = {_cypher_number_or_null(e.prezzo_eur)};"
    )


def _vicino_statement(rel) -> str:
    return (
        f"MATCH (a:Luogo {{id: {_cypher_str(rel.da_id)}}}), "
        f"(b:Luogo {{id: {_cypher_str(rel.a_id)}}})\n"
        f"MERGE (a)-[r:VICINO]->(b)\n"
        f"SET r.metri = {rel.metri};"
    )


def _legato_a_statement(rel) -> str:
    return (
        f"MATCH (a:Artista {{id: {_cypher_str(rel.artista_id)}}}), "
        f"(l:Luogo {{id: {_cypher_str(rel.luogo_id)}}})\n"
        f"MERGE (a)-[:LEGATO_A]->(l);"
    )


def _si_svolge_a_statement(e: ExperienceNode) -> str:
    return (
        f"MATCH (e:Esperienza {{id: {_cypher_str(e.id)}}}), "
        f"(l:Luogo {{id: {_cypher_str(e.place_id)}}})\n"
        f"MERGE (e)-[:SI_SVOLGE_A]->(l);"
    )


def _evoca_statement(e: ExperienceNode, tema_id: str) -> str:
    return (
        f"MATCH (e:Esperienza {{id: {_cypher_str(e.id)}}}), "
        f"(t:Tema {{id: {_cypher_str(tema_id)}}})\n"
        f"MERGE (e)-[:EVOCA]->(t);"
    )


def _offre_statement(e: ExperienceNode, bottega_id: str) -> str:
    return (
        f"MATCH (b:Bottega {{id: {_cypher_str(bottega_id)}}}), "
        f"(e:Esperienza {{id: {_cypher_str(e.id)}}})\n"
        f"MERGE (b)-[:OFFRE]->(e);"
    )


def _bottega_evoca_statement(rel) -> str:
    return (
        f"MATCH (b:Bottega {{id: {_cypher_str(rel.bottega_id)}}}), "
        f"(t:Tema {{id: {_cypher_str(rel.tema_id)}}})\n"
        f"MERGE (b)-[:EVOCA]->(t);"
    )


def _ispirata_da_statement(rel) -> str:
    return (
        f"MATCH (b:Bottega {{id: {_cypher_str(rel.bottega_id)}}}), "
        f"(a:Artista {{id: {_cypher_str(rel.artista_id)}}})\n"
        f"MERGE (b)-[r:ISPIRATA_DA]->(a)\n"
        f"SET r.racconto = {_cypher_str(rel.racconto)};"
    )


def build_seed() -> str:
    parts: list[str] = [_HEADER]

    parts.append("\n// --- Nodi: Luogo -------------------------------------------------------")
    for luogo in LUOGHI:
        parts.append(_luogo_statement(luogo))

    parts.append("\n// --- Nodi: Artista ------------------------------------------------------")
    for artista in ARTISTI:
        parts.append(_artista_statement(artista))

    parts.append("\n// --- Nodi: Bottega -------------------------------------------------------")
    for bottega in BOTTEGHE:
        parts.append(_bottega_statement(bottega))

    parts.append("\n// --- Nodi: Tema -----------------------------------------------------------")
    for tema in TEMI:
        parts.append(_tema_statement(tema))

    parts.append("\n// --- Nodi: Esperienza ---------------------------------------------------")
    for esperienza in ESPERIENZE:
        parts.append(_esperienza_statement(esperienza))

    parts.append("\n// --- Relazioni: VICINO (Luogo -> Luogo) --------------------------------")
    for rel in VICINO:
        parts.append(_vicino_statement(rel))

    parts.append("\n// --- Relazioni: LEGATO_A (Artista -> Luogo) ----------------------------")
    for rel in LEGATO_A:
        parts.append(_legato_a_statement(rel))

    parts.append("\n// --- Relazioni: SI_SVOLGE_A (Esperienza -> Luogo), da place_id --------")
    for esperienza in ESPERIENZE:
        parts.append(_si_svolge_a_statement(esperienza))

    parts.append("\n// --- Relazioni: EVOCA (Esperienza -> Tema), da temi --------------------")
    for esperienza in ESPERIENZE:
        for tema_id in esperienza.temi:
            parts.append(_evoca_statement(esperienza, tema_id))

    parts.append("\n// --- Relazioni: OFFRE (Bottega -> Esperienza), da partner_id -----------")
    for esperienza in ESPERIENZE:
        if esperienza.partner_id is not None:
            parts.append(_offre_statement(esperienza, esperienza.partner_id))

    parts.append(
        "\n// --- Relazioni SEMANTICHE: EVOCA (Bottega -> Tema) ----------------------\n"
        "// Non di prossimità: la bottega evoca i temi del suo mestiere anche a\n"
        "// prescindere dall'esperienza specifica che offre."
    )
    for rel in BOTTEGA_EVOCA:
        parts.append(_bottega_evoca_statement(rel))

    parts.append(
        "\n// --- Relazioni SEMANTICHE: ISPIRATA_DA (Bottega -> Artista) -------------\n"
        "// Tipo di relazione NUOVO (non VICINO, non LEGATO_A che è riservato ad\n"
        "// Artista->Luogo): lega una bottega al lavoro di un artista che ne ispira\n"
        "// il mestiere. `racconto` è la frase che rende esplicita la connessione.\n"
        "// È ciò che rende percorribile, per sole connessioni semantiche,\n"
        "// \"Puccini -> ... -> liutaio -> violino\" (vedi graph/topology.py)."
    )
    for rel in BOTTEGA_ISPIRATA_DA:
        parts.append(_ispirata_da_statement(rel))

    return "\n".join(parts) + "\n"


def main() -> None:
    CYPHER_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_FILE.write_text(build_schema(), encoding="utf-8")
    SEED_FILE.write_text(build_seed(), encoding="utf-8")
    print(f"Scritto: {SCHEMA_FILE}")
    print(f"Scritto: {SEED_FILE}")


if __name__ == "__main__":
    main()
