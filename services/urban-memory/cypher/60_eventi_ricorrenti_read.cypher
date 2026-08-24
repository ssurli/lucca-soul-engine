// Legge tutti i pattern promossi (:Evento {ricorrente: true}), con le
// proprietà necessarie alla frizione automatica a cadenza
// (`urban_memory.frizione_pattern`, `python -m urban_memory.frizione_pattern`)
// — un comando batch RISTRETTO/FIDATO, invocato manualmente. MAI eseguita da
// `/itinerary`, dall'Experience Engine o da qualunque altro path del motore:
// la frizione è un comando a sé, non un lookup che vive sul percorso caldo
// (stesso motivo per cui il clock del pattern si CALCOLA da questa lettura
// invece di essere un campo scritto ad ogni deposito di traccia).
//
// SOLA LETTURA: nessun MATCH+SET qui. La scrittura dello stato vive in
// `61_frizione_stato_write.cypher`, una query separata — stesso principio a
// tre livelli (pura / esecuzione / wrapper con driver riusato) già applicato
// da `promozione_evento.py`/`luogo_traccia_link.py`: query pure separate
// dall'esecuzione, mai una query che fa entrambe le cose.
//
// Ancoraggio: (:Evento)-[:SI_SVOLGE_A]->(:Luogo) — la STESSA relazione già
// scritta alla promozione (`50_promozione_evento_write.cypher`), mai una
// nuova: un `:Evento` ricorrente è sempre ancorato a un `:Luogo` per
// costruzione (la MERGE di promozione crea sempre anche la relazione).
//
// Nessun parametro: enumera OGNI `:Evento` ricorrente esistente nel grafo,
// a prescindere dal suo `stato` attuale (`attivo`/`sospeso`/`dormiente`) — è
// il codice Python chiamante (`urban_memory.frizione_pattern.main`) a
// decidere, pattern per pattern, se una transizione è dovuta; questa query
// non filtra né decide nulla.
MATCH (e:Evento {ricorrente: true})-[:SI_SVOLGE_A]->(l:Luogo)
RETURN e.id AS evento_id,
       l.id AS place_id,
       e.temi AS temi,
       e.stato AS stato,
       e.cadenza_giorni AS cadenza_giorni
