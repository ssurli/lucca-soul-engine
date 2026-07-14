// Verifica di esistenza dei target di un contributo di Urban Memory —
// eseguita PRIMA di 30_memory_link_write.cypher, nella STESSA transazione
// (vedi `urban_memory.graph_link.link_to_graph` / `_link_transaction`,
// `Session.execute_write`).
//
// BUG STORICO CORRETTO DA QUESTA QUERY (osservato su Aura reale): senza
// questo controllo, un id inesistente in $riguarda produceva in silenzio un
// nodo :Memoria orfano (creato comunque, senza relazioni) — un fallimento
// che si travestiva da successo. Ora: se anche un solo id in $riguarda non
// corrisponde a un nodo :Luogo, :Bottega o :Artista ESISTENTE, la funzione
// di transazione chiamante solleva `MemoryLinkError` PRIMA di eseguire
// 30_memory_link_write.cypher — nessun nodo :Memoria orfano, mai.
//
// Parametri:
//   $riguarda   list[string]   id di Luogo/Bottega/Artista attesi nel grafo
//
// Ritorna, in `mancanti`, la lista degli id di $riguarda che NON esistono
// (con uno di quei tre label): lista vuota => tutti i target esistono, si
// può procedere alla scrittura.
UNWIND $riguarda AS target_id
OPTIONAL MATCH (target) WHERE target.id = target_id
  AND (target:Luogo OR target:Bottega OR target:Artista)
WITH target_id, target
WHERE target IS NULL
RETURN collect(target_id) AS mancanti
