"""Lucca Soul Lab — Engine: Urban Knowledge Graph (Neo4j).

Il grafo ragiona su RELAZIONI, non categorie: propone percorsi sorprendenti
(Puccini -> opera -> Teatro del Giglio -> liutaio -> violino). Non ordina e
non decide: sceglie solo l'AI Experience Engine.

`graph.seed_lucca` è la fonte di verità versionata del dataset di Lucca. Da
questo dataset unico nascono sia il percorso in-memory (`graph.source`) sia
il Cypher versionato in `cypher/` (rigenerato da `graph.export_cypher`).
"""

from __future__ import annotations

__version__ = "0.1.0"
