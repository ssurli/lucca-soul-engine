// Query "candidati" per l'AI Experience Engine.
//
// Il grafo PROPONE per connessioni: ogni riga porta i fatti grezzi (artisti
// legati al luogo, temi evocati, distanza dal punto di riferimento) da cui
// `graph.source.Neo4jCandidateSource` monta un `GraphCandidate`. Non ordina e
// non applica vincoli etici: quello spetta all'AI Experience Engine, il solo
// componente che decide.
//
// `botteghe_nomi` (dalla relazione OFFRE) è nel risultato ma alimenta SOLO
// `GraphCandidate.attribuzione` (narrazione trasparente nel `reason`), MAI
// `connessioni`: `connessioni` conta nella componente "sorpresa" dello score
// del motore, e la presenza di un partner non deve comprare punteggio —
// "nessuno spazio è acquistabile" (CLAUDE.md).
//
// Parametri (tutti opzionali: `null` o lista vuota = nessun filtro):
//   $temi         list[string]   id di Tema da cercare tra quelli evocati
//   $al_chiuso    bool | null    filtro esatto su Esperienza.al_chiuso
//   $accessibile  bool | null    filtro esatto su Esperienza.accessibile
//   $vicino_a     string | null  place_id di riferimento per la prossimità
//   $raggio_m     int | null     raggio massimo in metri da $vicino_a
//                                (ignorato se $vicino_a è null)
//
// Usata da `graph.source.Neo4jCandidateSource.candidates(ctx)` con
// `$vicino_a` = ultimo luogo di `ctx.luoghi_gia_visti` (se presente) e tutti
// gli altri filtri disattivati: il grafo propone SEMPRE tutto, filtrare su
// segnale/profilo è compito dell'Experience Engine. La query resta
// comunque pienamente parametrica per chi la richiama direttamente.
MATCH (e:Esperienza)-[:SI_SVOLGE_A]->(l:Luogo)
WHERE ($temi IS NULL OR size($temi) = 0
       OR EXISTS { MATCH (e)-[:EVOCA]->(t:Tema) WHERE t.id IN $temi })
  AND ($al_chiuso IS NULL OR e.al_chiuso = $al_chiuso)
  AND ($accessibile IS NULL OR e.accessibile = $accessibile)
  AND ($vicino_a IS NULL
       OR l.id = $vicino_a
       OR EXISTS {
            MATCH (l)-[v:VICINO]-(:Luogo {id: $vicino_a})
            WHERE $raggio_m IS NULL OR v.metri <= $raggio_m
          })
OPTIONAL MATCH (art:Artista)-[:LEGATO_A]->(l)
OPTIONAL MATCH (bot:Bottega)-[:OFFRE]->(e)
OPTIONAL MATCH (e)-[:EVOCA]->(tema:Tema)
OPTIONAL MATCH (l)-[vic:VICINO]-(:Luogo {id: $vicino_a})
WITH e, l,
     collect(DISTINCT art.nome) AS artisti_nomi,
     collect(DISTINCT bot.nome) AS botteghe_nomi,
     collect(DISTINCT tema.nome) AS temi_nomi,
     min(vic.metri) AS distanza_m
RETURN
  e.id AS id,
  e.titolo AS titolo,
  e.place_id AS place_id,
  e.temi AS temi,
  e.durata_min AS durata_min,
  e.al_chiuso AS al_chiuso,
  e.accessibile AS accessibile,
  e.alimenta_memoria AS alimenta_memoria,
  e.partner_id AS partner_id,
  e.prezzo_eur AS prezzo_eur,
  l.nome AS place_nome,
  artisti_nomi,
  botteghe_nomi,
  temi_nomi,
  distanza_m
ORDER BY e.id
