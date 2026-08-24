// Aggiorna `e.stato` per la frizione automatica a cadenza
// (`urban_memory.frizione_pattern`, `python -m urban_memory.frizione_pattern`)
// — un comando batch RISTRETTO/FIDATO invocato manualmente, MAI innescato da
// `/itinerary`, dall'Experience Engine o da qualunque altro path del motore.
//
// MATCH + SET puro, MAI un MERGE — stesso principio di
// `40_luogo_traccia_write.cypher`: il nodo `:Evento` esiste già (creato alla
// promozione, `50_promozione_evento_write.cypher`), questa query non crea
// mai un `:Evento` nuovo. Se `$evento_id` non esiste (più?) nel grafo, il
// MATCH non produce righe: nessuna scrittura, nessun nodo fantasma creato —
// coerente con l'invariante A (un `:Evento` promosso non sparisce mai, si
// spegne solo cambiando `stato`, mai una DELETE).
//
// Scritta SOLO quando il codice chiamante (`urban_memory.frizione_pattern.
// main`) ha già deciso che lo stato calcolato differisce da quello letto:
// questa query è INCONDIZIONATA — esegue sempre il SET se raggiunta, la
// decisione "scrivere o no" vive interamente nel Python chiamante, non qui.
//
// Parametri:
//   $evento_id    string   id del :Evento la cui frizione automatica ha deciso una transizione
//   $nuovo_stato  string   uno tra 'attivo' / 'sospeso' / 'dormiente'
MATCH (e:Evento {id: $evento_id})
SET e.stato = $nuovo_stato
RETURN e.id AS evento_id
