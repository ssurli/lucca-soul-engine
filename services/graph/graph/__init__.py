"""Urban Knowledge Graph (Neo4j) dell'Urban Cognitive Layer.

Il grafo ragiona su RELAZIONI, non categorie: propone percorsi sorprendenti
(Puccini -> opera -> Teatro del Giglio -> liutaio -> violino). Non ordina e
non decide: sceglie solo l'AI Experience Engine.

Il dataset della città (`graph.dataset.DatasetCitta`, modulo
`graph/seed_<città>.py`) è risolto da `CITY_SEED` tramite `graph.registro`: è
la fonte di verità versionata. Da questo dataset unico nascono sia il
percorso in-memory (`graph.source`) sia il Cypher versionato in `cypher/`
(rigenerato da `graph.export_cypher`).
"""

from __future__ import annotations

__version__ = "0.1.0"

from graph.errors import GraphUnavailableError

__all__ = ["GraphUnavailableError", "__version__"]
