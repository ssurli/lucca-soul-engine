// Coppie di Luogo NON collegate direttamente da VICINO in uno snapshot del
// grafo congelato a $at — equivalente Neo4j di
// `graph.topology.non_connected_place_pairs()`, STESSA definizione logica.
//
// Serve all'indicatore `nuovi_percorsi` (Wave 4, Urban Intelligence Index):
// confrontando questo insieme a due istanti T0 e T1 (due esecuzioni con
// $at diverso), chi calcola l'indicatore vede quali coppie erano
// non-connesse a T0 e sono diventate connesse entro T1 — la definizione
// stessa di "percorso nuovo". Questa query espone solo lo snapshot grezzo:
// il confronto tra due snapshot e il calcolo dell'indicatore NON sono
// compito di questo servizio (vedi services/intelligence-index).
//
// "Collegate" = arco VICINO diretto (prossimità fisica), MAI un cammino
// semantico (LEGATO_A/SI_SVOLGE_A/OFFRE/EVOCA/ISPIRATA_DA): coerente con
// `graph.topology.SEMANTIC_RELATION_TYPES` che esclude esplicitamente
// VICINO da quel conteggio.
//
// Parametri:
//   $at   string (ISO 8601) | null   istante dello snapshot.
//         null = snapshot "adesso": TUTTI gli archi VICINO correnti, senza
//         filtro temporale (coerente con `non_connected_place_pairs(at=
//         None)`).
//         Altrimenti: un arco entra nello snapshot se non ha `creato_il`
//         (grafo scritto prima dell'introduzione di questa proprietà —
//         trattato come "sempre esistito", stessa regola degli archi del
//         seed iniziale, vedi `DatasetCitta.vicino_epoca`) OPPURE se
//         creato_il <= $at.
//
// Ritorna una riga sola: `coppie_non_connesse`, lista di [place_id_a,
// place_id_b] (place_id_a < place_id_b, quindi ogni coppia compare una sola
// volta). La dimensione (denominatore della normalizzazione) è
// `size(coppie_non_connesse)`, calcolabile lato Python senza una colonna
// dedicata.
MATCH (a:Luogo), (b:Luogo)
WHERE a.id < b.id
  AND NOT EXISTS {
        MATCH (a)-[v:VICINO]-(b)
        WHERE $at IS NULL OR v.creato_il IS NULL OR v.creato_il <= datetime($at)
      }
RETURN collect([a.id, b.id]) AS coppie_non_connesse
