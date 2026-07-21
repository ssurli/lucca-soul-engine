// Grado semantico per Luogo — equivalente Neo4j di
// `graph.topology.grado_semantico()`, STESSA definizione logica (nessuna
// seconda fonte di verità, solo due implementazioni della stessa regola).
//
// Serve all'indicatore `attivazione_locale` (Wave 4, Urban Intelligence
// Index). Il committente ha respinto il grado nella rete `VICINO` (misura
// la centralità nella PIANTA della città — una scelta di modellazione del
// seed, non un fatto culturale): questo grado conta invece le relazioni
// CULTURALI (LEGATO_A, SI_SVOLGE_A, OFFRE, EVOCA, ISPIRATA_DA — tutto
// tranne VICINO) che toccano il Luogo, INCLUSE quelle delle Botteghe che
// ospita (Bottega.place_id). Una bottega culturalmente scollegata (poche
// EVOCA/ISPIRATA_DA) rende "minore" il luogo che la ospita, anche se quel
// luogo è fisicamente centralissimo.
//
// Un Luogo è toccato direttamente solo da LEGATO_A (Artista->Luogo) e
// SI_SVOLGE_A (Esperienza->Luogo): le altre relazioni semantiche (OFFRE,
// EVOCA, ISPIRATA_DA) non hanno mai un Luogo come endpoint diretto nello
// schema — toccano una Bottega, che si somma qui via `place_id`.
//
// Eseguita in produzione contro un grafo che, a differenza del seed
// offline, può avere accumulato relazioni ulteriori nel tempo (curatela,
// Urban Memory): per questo la versione live è la fonte di verità a
// runtime, la versione offline (`graph.topology`) serve ai test e al
// fallback locale (profilo "PC fisso con Docker").
//
// Nessun parametro. Una riga per Luogo: place_id, grado.
//
// FIX (2026-07-21, bug reale su Aura CYPHER 25): `botteghe_ospitate` era
// costruita con una pattern comprehension a pattern nodo-solo,
// `[(b:Bottega {place_id: l.id}) | b]` — sintassi Cypher 5, non valida in
// Cypher 25 (GQL-conformant: `CypherSyntaxError: Invalid input '|': expected
// an expression`, riprodotto identico su Aura reale). Una pattern
// comprehension richiede un PATH (almeno una relazione); un pattern di solo
// nodo non è un path valido per quella forma. Riscritta con
// `OPTIONAL MATCH` + `collect(b)`, che non usa affatto la sintassi di
// pattern comprehension: stesso risultato (lista vuota se nessuna Bottega ha
// `place_id = l.id`, esattamente come la vecchia `[]`), portabile su
// qualunque versione Cypher, nessuna seconda fonte di verità introdotta.
MATCH (l:Luogo)
WITH l,
     COUNT { (l)<-[:LEGATO_A]-(:Artista) } AS legato_a,
     COUNT { (l)<-[:SI_SVOLGE_A]-(:Esperienza) } AS si_svolge_a
OPTIONAL MATCH (b:Bottega {place_id: l.id})
WITH l, legato_a, si_svolge_a, collect(b) AS botteghe_ospitate
WITH l,
     legato_a + si_svolge_a AS grado_luogo,
     reduce(
       acc = 0, b IN botteghe_ospitate |
         acc
         + COUNT { (b)-[:OFFRE]->(:Esperienza) }
         + COUNT { (b)-[:EVOCA]->(:Tema) }
         + COUNT { (b)-[:ISPIRATA_DA]->(:Artista) }
     ) AS grado_botteghe_ospitate
RETURN l.id AS place_id, grado_luogo + grado_botteghe_ospitate AS grado
ORDER BY place_id
