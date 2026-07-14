// Aggancio di un contributo di Urban Memory al Knowledge Graph.
//
// Ogni Memoria si aggancia al grafo con `(:Memoria)-[:RIGUARDA]->
// (:Luogo|:Bottega|:Artista)` (docs/DATA_CONTRACTS.md §2, §4): la memoria
// ARRICCHISCE il grafo, non vive a lato.
//
// Generata da `urban_memory.graph_link.riguarda_to_cypher(contribution)`,
// che legge QUESTO file (single source of truth: il testo eseguito e il
// testo versionato non possono divergere) e vi affianca solo i parametri.
// La funzione è PURA e non esegue nulla: nessun driver Neo4j è importato in
// questa wave. L'esecuzione reale (Aura `neo4j+s://` o locale `bolt://`,
// mai un `if local/cloud`: lo schema dell'URI vive solo nel `.env`) spetta
// a chi ha il driver — `services/api` o `services/graph`, in una wave
// successiva.
//
// Idempotente: `MERGE` non duplica né la Memoria né le relazioni se la
// query viene rieseguita con lo stesso `$id` e lo stesso `$riguarda`.
//
// Le proprietà scritte sul nodo :Memoria sono volutamente MINIME: il grafo
// porta il collegamento e ciò che serve a filtrare/etichettare (tipo,
// licenza, curatela), non il payload. `testo`/`media_uri` restano nella
// Urban Memory (mai duplicati nel grafo): l'`id` è la chiave per andarli a
// recuperare da lì.
//
// `MATCH (target) WHERE target.id = target_id AND (target:Luogo OR
// target:Bottega OR target:Artista)` collega SOLO a nodi ESISTENTI di quei
// tipi: non crea il target. Se un id in $riguarda non esiste ancora nel
// grafo (o è di un altro tipo), quella riga dell'UNWIND non produce alcuna
// relazione — non fa fallire il resto della query. Con `$riguarda` vuoto la
// Memoria viene comunque creata/aggiornata, semplicemente senza relazioni.
//
// Parametri:
//   $id                string          MemoryContribution.id
//   $kind              string          MemoryContribution.kind (valore enum)
//   $contributor_kind  string          MemoryContribution.contributor_kind (valore enum)
//   $licenza           string          MemoryContribution.licenza (es. "CC-BY-SA-4.0")
//   $curato            bool            MemoryContribution.curato
//   $creato_il         string (ISO)    MemoryContribution.creato_il
//   $riguarda          list[string]    id di Luogo/Bottega/Artista nel grafo
MERGE (m:Memoria {id: $id})
SET m.kind = $kind,
    m.contributor_kind = $contributor_kind,
    m.licenza = $licenza,
    m.curato = $curato,
    m.creato_il = $creato_il
WITH m
UNWIND $riguarda AS target_id
MATCH (target) WHERE target.id = target_id
  AND (target:Luogo OR target:Bottega OR target:Artista)
MERGE (m)-[:RIGUARDA]->(target)
