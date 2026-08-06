// Promuove un pattern ricorrente a :Evento — Fase 3, curatela UMANA
// (`python -m urban_memory.curatela_pattern`), MAI automatica: un
// Promotore decide esplicitamente, pattern per pattern.
//
// Ancoraggio: SOLO (:Evento)-[:SI_SVOLGE_A]->(:Luogo) — la relazione
// "accade qui" già in uso per (:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)
// (services/graph/cypher/01_seed_lucca.cypher), MAI una relazione nuova
// (NON `LEGATO_A`: riservata semanticamente ad Artista->Luogo).
//
// MATCH sul :Luogo, MAI un MERGE: questa query non crea MAI un :Luogo. Se
// $place_id non esiste (ancora, o più) nel grafo, il MATCH non produce
// righe e NESSUNA clausola successiva (MERGE :Evento, SET, MERGE
// SI_SVOLGE_A) viene eseguita — niente :Evento orfano, niente relazione
// fantasma. Chi chiama (`urban_memory.promozione_evento.
// scrivi_evento_promosso`) tratta "zero righe restituite" come errore
// esplicito (place_id inesistente), mai un successo silenzioso.
//
// $evento_id È DETERMINISTICO (derivato da place_id+temi, non un uuid
// casuale — vedi `promozione_evento.evento_id_per_pattern`): ripromuovere
// lo STESSO pattern (es. dopo nuove occorrenze in una corsa futura del
// comando di curatela) aggiorna lo stesso nodo :Evento invece di crearne
// uno duplicato — MERGE è idempotente per costruzione, stesso principio
// di `MERGE (m:Memoria {id: $id})` in `30_memory_link_write.cypher`.
//
// ON CREATE / ON MATCH (NON un SET incondizionato dopo il MERGE): una
// PRIMA promozione fissa `promosso_da`/`promosso_il` — la data ORIGINALE
// di prima promozione, VINCOLO LOAD-BEARING per un consumatore futuro (la
// frizione automatica a cadenza, che conterà i "battiti mancati" a
// partire da quella data). Una RIPROMOZIONE dello stesso pattern (nuove
// occorrenze accumulate) aggiorna `cadenza_giorni`/`temi` e registra
// SEPARATAMENTE `ultimo_ricalcolo_da`/`ultimo_ricalcolo_il`, ma NON
// sovrascrive mai `promosso_da`/`promosso_il`: un `SET` incondizionato
// perderebbe la data originale a ogni ripromozione. `e.ricorrente`/
// `e.stato` sono scritti SOLO alla creazione: `stato` è mutabile da un
// task futuro (dormienza/sospensione, fuori scope qui) — una ripromozione
// non deve mai riportarlo forzatamente ad 'attivo'.
//
// :Evento può essere creato con MERGE/CREATE (è il nodo NUOVO che questa
// funzionalità introduce, coerente col vincolo di unicità su `id` già
// esistente — `evento_id_unique`, services/graph/cypher/00_schema.cypher).
//
// `promosso_da`/`ultimo_ricalcolo_da` sono uno PSEUDONIMO del Promotore
// (mai PII) — stesso trattamento di `pattern_cestinato.promotore`: è
// l'accountability persistente e interrogabile dell'atto che scrive
// struttura PERMANENTE e PUBBLICA nel grafo (a differenza di un log
// applicativo, non garantito persistente).
//
// Parametri:
//   $place_id        string        id del :Luogo su cui ancorare l'evento
//   $evento_id        string        id deterministico del :Evento
//   $temi             list[string]  i temi del pattern promosso
//   $cadenza_giorni   float         intervallo medio fra le occorrenze, in giorni
//   $promotore        string        pseudonimo del Promotore che decide ORA
//   $promosso_il      string (ISO) istante di QUESTA decisione (creazione o ricalcolo)
MATCH (l:Luogo {id: $place_id})
MERGE (e:Evento {id: $evento_id})
ON CREATE SET
    e.ricorrente = true,
    e.stato = 'attivo',
    e.temi = $temi,
    e.cadenza_giorni = $cadenza_giorni,
    e.promosso_da = $promotore,
    e.promosso_il = $promosso_il
ON MATCH SET
    e.temi = $temi,
    e.cadenza_giorni = $cadenza_giorni,
    e.ultimo_ricalcolo_da = $promotore,
    e.ultimo_ricalcolo_il = $promosso_il
MERGE (e)-[:SI_SVOLGE_A]->(l)
RETURN e.id AS evento_id
