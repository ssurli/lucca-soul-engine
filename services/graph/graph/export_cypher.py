"""`python -m graph.export_cypher` — rigenera il Cypher versionato dal dataset.

Il modulo dataset della città (`graph/seed_<città>.py`, selezionato da
`CITY_SEED` via `graph.registro`) è l'UNICA fonte di verità. Questo modulo lo
traduce in due file committati in `cypher/`:

- `00_schema.cypher` — vincoli di unicità sugli `id` di ogni nodo (idempotente:
  `CREATE CONSTRAINT ... IF NOT EXISTS`);
- `01_seed_<città>.cypher` — `MERGE` di nodi e relazioni (idempotente:
  rieseguibile da zero senza duplicare nulla).

Perché generarlo invece di scriverlo a mano: replicare il motore su
un'altra città significa scrivere un nuovo `seed_<città>.py` e
rilanciare questo comando — la struttura del Cypher non cambia mai a mano.

Uso (dalla radice del repo, dopo `pip install -e services/graph`):

    python -m graph.export_cypher            # città di CITY_SEED
    python -m graph.export_cypher --city <slug>
"""

from __future__ import annotations

import argparse
from datetime import datetime

from contracts import ExperienceNode, Partner, codifica_fasce

from graph.dataset import DatasetCitta
from graph.registro import CYPHER_DIR, carica_dataset, dataset_attivo, file_seed_cypher

SCHEMA_FILE = CYPHER_DIR / "00_schema.cypher"

_HEADER = (
    "// File GENERATO da `python -m graph.export_cypher`.\n"
    "// Non modificare a mano: la fonte di verità è il modulo dataset `graph/seed_<città>.py`\n"
    "// selezionato da CITY_SEED.\n"
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
    "Partner",
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


def _cypher_datetime(value: datetime) -> str:
    """`datetime('...')` — tipo temporale nativo di Neo4j (non una stringa),
    così `cypher/12_non_connected_pairs.cypher` può confrontarlo con
    `datetime($at)` senza cast. `value` deve essere timezone-aware
    (il dataset lo garantisce: vedi `graph.dataset.RelazioneVicino`)."""
    return f"datetime({_cypher_str(value.isoformat())})"


def _cypher_str_list(values: list[str]) -> str:
    return "[" + ", ".join(_cypher_str(v) for v in values) + "]"


_RELATION_TYPES_COMMENT = (
    "// Tipi di relazione del grafo (documentazione, nessun vincolo Neo4j li\n"
    "// richiede esplicitamente):\n"
    "//   (:Artista)-[:LEGATO_A]->(:Luogo)\n"
    "//   (:Luogo)-[:VICINO {metri, creato_il}]->(:Luogo)   -- non orientata nel dominio;\n"
    "//     creato_il (Wave 4): VICINO_EPOCA per tutti gli archi del seed iniziale\n"
    "//     ('sempre esistiti', non una data vera — vedi il modulo dataset), un vero\n"
    "//     datetime.now(UTC) per ogni arco scritto dopo il seed. Serve a congelare uno\n"
    "//     snapshot di connettività a un istante T (graph/topology.py,\n"
    "//     cypher/12_non_connected_pairs.cypher) per l'indicatore nuovi_percorsi.\n"
    "//   (:Bottega)-[:OFFRE]->(:Esperienza)\n"
    "//   (:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)\n"
    "//   (:Esperienza)-[:EVOCA]->(:Tema)\n"
    "//   (:Bottega)-[:EVOCA]->(:Tema)                      -- SEMANTICA, non di prossimità\n"
    "//   (:Bottega)-[:ISPIRATA_DA {racconto}]->(:Artista)  -- SEMANTICA, NUOVA: introdotta\n"
    "//     perché una bottega di liuteria fosse raggiungibile da Puccini per sole\n"
    "//     connessioni semantiche, senza passare per VICINO (vedi graph/topology.py).\n"
    "//   (:Bottega)-[:HA_ABBONAMENTO]->(:Partner)          -- COMMERCIALE, NUOVA\n"
    "//     (Wave 3a, marketplace): Partner.abbonamento_attivo è l'UNICA leva che\n"
    "//     decide presenza/assenza tra i candidati (mai il ranking, mai lo score).\n"
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
        f"b.place_id = {_cypher_str(bottega.place_id)}, "
        f"b.fittizio = {_cypher_bool(bottega.fittizio)};"
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
        f"    e.prezzo_eur = {_cypher_number_or_null(e.prezzo_eur)},\n"
        f"    e.prenotabile = {_cypher_bool(e.prenotabile)},\n"
        # Scritta SEMPRE, anche vuota: il `SET` sovrascrive, quindi un orario
        # tolto dal dataset sparisce da un grafo già caricato (omettendola
        # resterebbe quello vecchio). Formato: `contracts.codifica_fasce`.
        f"    e.orari_apertura = {_cypher_str_list(codifica_fasce(e.orari_apertura))};"
    )


def _vicino_statement(rel) -> str:
    return (
        f"MATCH (a:Luogo {{id: {_cypher_str(rel.da_id)}}}), "
        f"(b:Luogo {{id: {_cypher_str(rel.a_id)}}})\n"
        f"MERGE (a)-[r:VICINO]->(b)\n"
        f"SET r.metri = {rel.metri}, r.creato_il = {_cypher_datetime(rel.creato_il)};"
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


def _partner_statement(partner: Partner) -> str:
    return (
        f"MERGE (p:Partner {{id: {_cypher_str(partner.id)}}})\n"
        f"SET p.nome = {_cypher_str(partner.nome)}, "
        f"p.abbonamento_attivo = {_cypher_bool(partner.abbonamento_attivo)};"
    )


def _ha_abbonamento_statement(rel) -> str:
    return (
        f"MATCH (b:Bottega {{id: {_cypher_str(rel.bottega_id)}}}), "
        f"(p:Partner {{id: {_cypher_str(rel.partner_id)}}})\n"
        f"MERGE (b)-[:HA_ABBONAMENTO]->(p);"
    )


def build_seed(dataset: DatasetCitta | None = None) -> str:
    ds = dataset if dataset is not None else dataset_attivo()
    parts: list[str] = [_HEADER]

    parts.append("\n// --- Nodi: Luogo -------------------------------------------------------")
    for luogo in ds.luoghi:
        parts.append(_luogo_statement(luogo))

    parts.append("\n// --- Nodi: Artista ------------------------------------------------------")
    for artista in ds.artisti:
        parts.append(_artista_statement(artista))

    parts.append("\n// --- Nodi: Bottega -------------------------------------------------------")
    for bottega in ds.botteghe:
        parts.append(_bottega_statement(bottega))

    parts.append("\n// --- Nodi: Tema -----------------------------------------------------------")
    for tema in ds.temi:
        parts.append(_tema_statement(tema))

    parts.append("\n// --- Nodi: Esperienza ---------------------------------------------------")
    for esperienza in ds.esperienze:
        parts.append(_esperienza_statement(esperienza))

    parts.append("\n// --- Nodi: Partner (Wave 3a, marketplace) -------------------------------")
    for partner in ds.partners:
        parts.append(_partner_statement(partner))

    parts.append("\n// --- Relazioni: VICINO (Luogo -> Luogo) --------------------------------")
    for vicino in ds.vicino:
        parts.append(_vicino_statement(vicino))

    parts.append("\n// --- Relazioni: LEGATO_A (Artista -> Luogo) ----------------------------")
    for legato in ds.legato_a:
        parts.append(_legato_a_statement(legato))

    parts.append("\n// --- Relazioni: SI_SVOLGE_A (Esperienza -> Luogo), da place_id --------")
    for esperienza in ds.esperienze:
        parts.append(_si_svolge_a_statement(esperienza))

    parts.append("\n// --- Relazioni: EVOCA (Esperienza -> Tema), da temi --------------------")
    for esperienza in ds.esperienze:
        for tema_id in esperienza.temi:
            parts.append(_evoca_statement(esperienza, tema_id))

    parts.append("\n// --- Relazioni: OFFRE (Bottega -> Esperienza), da partner_id -----------")
    for esperienza in ds.esperienze:
        if esperienza.partner_id is not None:
            parts.append(_offre_statement(esperienza, esperienza.partner_id))

    parts.append(
        "\n// --- Relazioni SEMANTICHE: EVOCA (Bottega -> Tema) ----------------------\n"
        "// Non di prossimità: la bottega evoca i temi del suo mestiere anche a\n"
        "// prescindere dall'esperienza specifica che offre."
    )
    for evoca in ds.bottega_evoca:
        parts.append(_bottega_evoca_statement(evoca))

    parts.append(
        "\n// --- Relazioni SEMANTICHE: ISPIRATA_DA (Bottega -> Artista) -------------\n"
        "// Tipo di relazione NUOVO (non VICINO, non LEGATO_A che è riservato ad\n"
        "// Artista->Luogo): lega una bottega al lavoro di un artista che ne ispira\n"
        "// il mestiere. `racconto` è la frase che rende esplicita la connessione.\n"
        "// È ciò che rende percorribile, per sole connessioni semantiche,\n"
        "// \"Puccini -> ... -> liutaio -> violino\" (vedi graph/topology.py)."
    )
    for ispirata in ds.bottega_ispirata_da:
        parts.append(_ispirata_da_statement(ispirata))

    parts.append(
        "\n// --- Relazioni COMMERCIALI: HA_ABBONAMENTO (Bottega -> Partner) ---------\n"
        "// Wave 3a (marketplace): Partner.abbonamento_attivo è l'UNICA leva che\n"
        "// decide presenza/assenza di un'esperienza tra i candidati, mai il ranking.\n"
        "// Una Bottega senza questa relazione è sempre visibile (default True)."
    )
    for abbonamento in ds.ha_abbonamento:
        parts.append(_ha_abbonamento_statement(abbonamento))

    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Rigenera schema + seed Cypher dal dataset della città."
    )
    parser.add_argument(
        "--city",
        default=None,
        help="slug della città (default: CITY_SEED dall'ambiente o dal .env)",
    )
    args = parser.parse_args(argv)
    dataset = carica_dataset(args.city) if args.city else dataset_attivo()
    seed_file = file_seed_cypher(dataset)

    CYPHER_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_FILE.write_text(build_schema(), encoding="utf-8")
    seed_file.write_text(build_seed(dataset), encoding="utf-8")
    print(f"Scritto: {SCHEMA_FILE}")
    print(f"Scritto: {seed_file}")


if __name__ == "__main__":
    main()
