"""Aggancio della Urban Memory al Knowledge Graph.

Ogni contributo curato si aggancia al grafo con `(:Memoria)-[:RIGUARDA]->
(:Luogo|:Bottega|:Artista)` (docs/DATA_CONTRACTS.md §2, §4): la memoria
ARRICCHISCE il grafo, non vive a lato.

Questo modulo NON esegue nulla contro Neo4j (nessun driver, nessuna
connessione, nessuna sessione): `riguarda_to_cypher` è una funzione PURA che
produce solo `(query, params)`, deterministica e testabile in isolamento.
La query eseguita è la stessa, e la sola, versionata in
`services/urban-memory/cypher/30_memory_link.cypher` (letta da file, non
duplicata come stringa nel codice: non può divergere da sé stessa). È il BFF
(`services/api`) o `services/graph` a eseguirla realmente, con lo stesso
pattern già usato per `10_candidates.cypher`
(`graph.source.Neo4jCandidateSource`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts import MemoryContribution

__all__ = ["riguarda_to_cypher", "MEMORY_LINK_QUERY_PATH"]

_CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"
MEMORY_LINK_QUERY_PATH = _CYPHER_DIR / "30_memory_link.cypher"


def riguarda_to_cypher(contribution: MemoryContribution) -> tuple[str, dict[str, Any]]:
    """Query + parametri per agganciare `contribution` al Knowledge Graph.

    Produce SEMPRE `MERGE (m:Memoria {id: $id})` (idempotente: rieseguibile
    senza duplicare) e, per ogni id in `contribution.riguarda`, una
    relazione `MERGE (m)-[:RIGUARDA]->(target)` verso un nodo ESISTENTE
    `Luogo`, `Bottega` o `Artista` (non crea il target: se un id non esiste
    ancora nel grafo, quella riga dell'UNWIND semplicemente non produce
    alcuna relazione). Con `riguarda` vuoto la Memoria viene comunque
    creata/aggiornata, senza relazioni.

    Le proprietà scritte sul nodo `:Memoria` sono volutamente MINIME (kind,
    licenza, curato, contributor_kind, creato_il): il grafo porta il
    collegamento e ciò che serve a filtrare/etichettare, non il payload —
    `testo`/`media_uri` restano nella Urban Memory, non duplicati nel grafo;
    l'`id` è la chiave per andarli a recuperare da lì.

    Pura: non apre connessioni, non esegue nulla, non ha effetti collaterali
    oltre alla lettura (statica, non parametrica) del file `.cypher`
    versionato. Restituisce solo `(query, params)`.
    """
    query = MEMORY_LINK_QUERY_PATH.read_text(encoding="utf-8")
    params: dict[str, Any] = {
        "id": contribution.id,
        "kind": contribution.kind.value,
        "contributor_kind": contribution.contributor_kind.value,
        "licenza": contribution.licenza,
        "curato": contribution.curato,
        "creato_il": contribution.creato_il.isoformat(),
        "riguarda": list(contribution.riguarda),
    }
    return query, params
