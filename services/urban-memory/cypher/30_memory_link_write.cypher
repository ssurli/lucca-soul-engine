// Scrittura del nodo :Memoria e delle relazioni RIGUARDA per un contributo
// di Urban Memory — eseguita SOLO DOPO che 30_memory_link_check.cypher, IN
// QUESTA STESSA TRANSAZIONE, ha confermato che OGNI id in $riguarda esiste
// nel grafo (vedi `urban_memory.graph_link._link_transaction`). Se il
// controllo trova anche un solo id mancante, questa query non viene MAI
// eseguita — nessun nodo :Memoria orfano può essere creato.
//
// Ogni Memoria si aggancia al grafo con `(:Memoria)-[:RIGUARDA]->
// (:Luogo|:Bottega|:Artista)` (docs/DATA_CONTRACTS.md §2, §4): la memoria
// ARRICCHISCE il grafo, non vive a lato.
//
// Le proprietà scritte sul nodo :Memoria sono volutamente MINIME: il grafo
// porta il collegamento e ciò che serve a filtrare/etichettare (tipo,
// licenza, curatela), non il payload. `testo`/`media_uri` restano nella
// Urban Memory (mai duplicati nel grafo): l'`id` è la chiave per andarli a
// recuperare da lì.
//
// Idempotente: MERGE non duplica né la Memoria né le relazioni se la query
// viene rieseguita con lo stesso $id e lo stesso $riguarda.
//
// `MATCH (target) WHERE target.id = target_id AND (target:Luogo OR
// target:Bottega OR target:Artista)` è un secondo strato di sicurezza (non
// crea mai il target): nel finestrino teoricamente possibile in cui un
// target sparisse tra il controllo e questa scrittura, ALL'INTERNO della
// STESSA transazione, questa riga dell'UNWIND semplicemente non
// produrrebbe quella singola relazione — un caso limite che
// 30_memory_link_check.cypher, eseguita immediatamente prima nella stessa
// transazione, rende trascurabile in pratica.
//
// Parametri:
//   $id                string          MemoryContribution.id
//   $kind              string          MemoryContribution.kind (valore enum)
//   $contributor_kind  string          MemoryContribution.contributor_kind (valore enum)
//   $licenza           string          MemoryContribution.licenza (es. "CC-BY-SA-4.0")
//   $curato            bool            MemoryContribution.curato
//   $creato_il         string (ISO)    MemoryContribution.creato_il
//   $riguarda          list[string]    id di Luogo/Bottega/Artista, GIÀ verificati esistenti
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
