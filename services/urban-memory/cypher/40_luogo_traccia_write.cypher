// Aggiorna la proprietà derivata `ultima_traccia_il` su un :Luogo quando una
// traccia viene depositata nel ledger (`traccia_luogo`, Postgres) — il segnale
// fluttuante che l'ha generata è appena transitato attivo -> expired
// (`urban_memory.canale_fluttuante.sweep_and_fetch_active`).
// Design: `docs/PROMOZIONE_TRACCIA.md` §2(a).
//
// Serve ESCLUSIVAMENTE a leggere "quando ha parlato l'ultima volta questo
// luogo" a costo di lettura zero (nessuna traversata Neo4j, nessuna query su
// Postgres) — un consumatore futuro (rilevamento dormienza di un pattern
// promosso, fuori scope qui). Il bagliore (curva di decadimento, somma pesata
// su TUTTE le tracce) NON è stored: resta calcolato in lettura da chi lo
// consuma, mai qui (docs/PROMOZIONE_TRACCIA.md §2(b), docs/LIMITI.md).
//
// MATCH, non MERGE: questa query non crea MAI un :Luogo. Se `$place_id` non
// esiste (ancora, o più) nel grafo, la query è un no-op silenzioso — zero
// righe toccate, nessun errore, nessun nodo orfano creato per un place_id
// inventato. Il ledger su Postgres (append-only, la fonte di verità) resta
// comunque scritto indipendentemente dall'esito di QUESTA query: due
// scritture in due store diversi, non una transazione distribuita — stessa
// natura di rischio già accettata altrove nel repo (`urban_memory.graph_link`
// per l'aggancio di una Memoria), non una garanzia nuova da inventare qui. Se
// questa scrittura fallisce, `ultima_traccia_il` resta un dato stantio (mai
// invalido): si autocorregge alla prossima traccia depositata per lo stesso
// luogo.
//
// Parametri:
//   $place_id   string        id del :Luogo che ha ricevuto la traccia
//   $quando     string (ISO)  timbro della traccia = `valido_fino` del segnale
//                             scaduto (calcolato dal server in submit_signal),
//                             normalizzato UTC. NON l'istante dello sweep pigro.
//
// MONOTONA: `ultima_traccia_il` tiene il MASSIMO. Un segnale scaduto prima può
// essere scritto dopo (sweep per id, o spazzato in una chiamata successiva):
// senza la guardia la proprietà regredirebbe. Il confronto è fra `datetime()`
// (non fra stringhe: i valori già presenti possono avere formati/offset diversi).
MATCH (l:Luogo {id: $place_id})
SET l.ultima_traccia_il = CASE
  WHEN l.ultima_traccia_il IS NULL
    OR datetime(l.ultima_traccia_il) < datetime($quando)
  THEN $quando
  ELSE l.ultima_traccia_il
END
