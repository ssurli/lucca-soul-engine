// RIPRISTINO di un :Evento promosso dal ledger Postgres `pattern_promosso`
// (`python -m urban_memory.ripristina_eventi`) — dopo la perdita del grafo
// (Aura Free cancellata per inattivita'). Il ledger e' la fonte di verita',
// il grafo la proiezione: questa query riproduce lo STATO FINALE che
// `50_promozione_evento_write.cypher` avrebbe prodotto applicando in ordine
// tutti gli atti del ledger per questo evento_id. Il chiamante calcola:
//   - promosso_da / promosso_il : dalla PRIMA riga (data originale: la
//     frizione a cadenza conta i battiti mancanti da li');
//   - temi / cadenza_giorni     : dalla riga PIU' RECENTE;
//   - ultimo_ricalcolo_*        : dalla riga piu' recente SE esistono piu'
//     righe, altrimenti null (un SET a null rimuove la proprieta').
//
// IDEMPOTENTE: rieseguibile all'infinito, stesso risultato (MERGE su id
// deterministico; SET incondizionato di valori derivati dal ledger).
//
// MATCH sul :Luogo, MAI MERGE: nessun :Luogo fantasma. Luogo mancante ->
// zero righe -> il chiamante lo riporta come fallito (il seed del grafo va
// ricaricato PRIMA: `python -m graph.loader`).
//
// FRENO ATOMICO: `e.frenato = $frenato` e' nello STESSO SET del nodo (il
// chiamante lo ricava dall'ultima azione di `pattern_frenato`, false se
// nessuna): non esiste una finestra in cui un evento frenato sia attivo e non
// frenato (fail-closed). Il ripristino NON RILASCIA MAI un freno: su un nodo
// esistente gia' frenato (es. freno scritto sul grafo ma audit Postgres
// fallito) `$frenato=false` lo lascia frenato (`$frenato OR coalesce(
// e.frenato, false)`); il rilascio e' esclusivo di `freno_pattern rilascia`.
//
// `e.stato` NON e' ripristinato: ON CREATE parte da 'sospeso' (FAIL-SAFE:
// `POST /itinerary` consuma solo stato == 'attivo', quindi un evento appena
// ricostruito non e' raccomandabile finche' `urban_memory.frizione_pattern`
// non lo riporta ad 'attivo' con `sospeso -> attivo`); su un nodo gia'
// esistente NON viene toccato.
//
// `promosso_da`/`promosso_il`: coalesce — un nodo gia' esistente (anche
// pre-ledger) NON perde la sua accountability originale.
//
// Parametri: $place_id, $evento_id, $temi, $cadenza_giorni, $promotore,
//   $promosso_il (ISO), $ultimo_ricalcolo_da (string|null),
//   $ultimo_ricalcolo_il (ISO|null), $frenato (boolean)
MATCH (l:Luogo {id: $place_id})
MERGE (e:Evento {id: $evento_id})
ON CREATE SET
    e.stato = 'sospeso'
SET
    e.ricorrente = true,
    e.temi = $temi,
    e.cadenza_giorni = $cadenza_giorni,
    e.promosso_da = coalesce(e.promosso_da, $promotore),
    e.promosso_il = coalesce(e.promosso_il, $promosso_il),
    e.ultimo_ricalcolo_da = $ultimo_ricalcolo_da,
    e.ultimo_ricalcolo_il = $ultimo_ricalcolo_il,
    e.frenato = ($frenato OR coalesce(e.frenato, false))
MERGE (e)-[:SI_SVOLGE_A]->(l)
RETURN e.id AS evento_id
