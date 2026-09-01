// Aggiorna `e.frenato` per il freno di emergenza (`urban_memory.freno_pattern`,
// `python -m urban_memory.freno_pattern tira|rilascia`) — docs/STATE_MACHINE.md
// §4-bis(b): un OVERLAY di sicurezza manuale, ortogonale al ciclo di vita
// ordinario (§4-bis(a), `61_frizione_stato_write.cypher`), MAI una quarta
// voce di `e.stato`. Percorso RISTRETTO/FIDATO, invocato manualmente, MAI da
// `/itinerary`, dall'Experience Engine o da qualunque altro path del motore.
//
// MATCH + SET puro, MAI un MERGE — stesso principio di
// `61_frizione_stato_write.cypher`: il nodo `:Evento` esiste già (creato alla
// promozione, `50_promozione_evento_write.cypher`), questa query non crea
// mai un `:Evento` nuovo. Se `$evento_id` non esiste (più?) nel grafo, il
// MATCH non produce righe: nessuna scrittura, nessun nodo fantasma creato —
// coerente con l'invariante A (un `:Evento` promosso non sparisce mai, si
// spegne solo cambiando stato/frenato, mai una DELETE).
//
// Questa query NON tocca MAI `e.stato`: il freno e la frizione automatica a
// cadenza scrivono due proprietà DISTINTE dello stesso nodo. `$frenato=true`
// per tirare il freno, `$frenato=false` per rilasciarlo — il rilascio NON
// forza `e.stato` ad `attivo`: al rilascio il pattern torna a qualunque
// stato il ciclo di vita ordinario (§4-bis(a)) indica in quel momento,
// perché questa query non lo tocca affatto.
//
// Parametri:
//   $evento_id  string   id del :Evento su cui agisce il freno di emergenza
//   $frenato    boolean  true = freno tirato (raccomandazione soppressa),
//                        false = freno rilasciato
MATCH (e:Evento {id: $evento_id})
SET e.frenato = $frenato
RETURN e.id AS evento_id
