// Query "candidati" per l'AI Experience Engine.
//
// Il grafo PROPONE per connessioni: ogni riga porta i fatti grezzi (artisti
// legati al luogo, temi evocati, distanza dal punto di riferimento, e la
// catena SEMANTICA della bottega che eventualmente offre l'esperienza) da
// cui `graph.source.Neo4jCandidateSource` monta un `GraphCandidate`. Non
// ordina e non applica vincoli etici: quello spetta all'AI Experience
// Engine, il solo componente che decide.
//
// `botteghe` (nome, mestiere, fittizio; dalla relazione OFFRE, fatto COMMERCIALE) è nel
// risultato ma alimenta SOLO `GraphCandidate.attribuzione` (narrazione
// trasparente nel `reason`), MAI `connessioni`: `connessioni` conta nella
// componente "sorpresa" dello score del motore, e la presenza di un
// partner non deve comprare punteggio con la propria sola esistenza —
// "nessuno spazio è acquistabile" (CLAUDE.md).
//
// `racconti_ispirazione` (da `ISPIRATA_DA`) e `temi_bottega` (da `EVOCA`
// Bottega->Tema) sono invece fatti SEMANTICI — della stessa natura di
// `artisti_nomi`/`temi_nomi` — e alimentano `connessioni`: sono ciò che
// rende raggiungibile, per sole relazioni di significato, il percorso
// "Puccini -> ... -> liutaio -> violino" (vedi graph/topology.py).
//
// ORDINE: i `collect` non sono ordinati e non serve: l'ordine canonico delle
// `connessioni` lo impone `graph.connessioni.frasi_connessioni` in Python,
// identico al seed. `temi_evocati` e `racconti_ispirazione` portano gli id
// (tema, artista) necessari a quell'ordinamento; `distanza_m` e
// `riferimento_nome` (nome del luogo `$vicino_a`, null senza VICINO)
// alimentano la frase "A N m da X, già visitato.".
//
// `partner_abbonamento_attivo` (Wave 3a, marketplace — `docs/DATA_CONTRACTS.md`
// §5) è un JOIN puro: legge `Partner.abbonamento_attivo` risalendo dalla
// Bottega referenziata da `e.partner_id` via `HA_ABBONAMENTO`, MAI logica di
// scoring. Default `true` se l'esperienza non ha partner (`e.partner_id IS
// NULL`) o se la Bottega non ha alcun `HA_ABBONAMENTO` collegato: solo un
// Partner ESPLICITAMENTE presente con `abbonamento_attivo = false` fa
// scendere il booleano. Il consumer (`graph.source.Neo4jCandidateSource`)
// lo scrive, senza modifiche, in `ExperienceNode.partner_abbonamento_attivo`;
// l'Experience Engine lo legge come filtro duro booleano in
// `passa_filtri_duri` (`services/experience-engine`), mai come input di
// `calcola_score`.
//
// `botteghe[].fittizio` (disclosure "esempio dimostrativo" nell'attribuzione)
// può mancare su un grafo il cui seed non è ancora stato rieseguito dopo
// l'introduzione della proprietà (Aura Free si cancella dopo 30 giorni di
// inattività). Il default è `true`: una bottega senza il dato si DICHIARA
// dimostrativa, mai reale per omissione — come `prenotabile` degrada al
// default sicuro. Quando nessuna bottega offre l'esperienza, l'OPTIONAL MATCH
// produce una entry con `nome` nullo: il consumer Python la scarta.
//
// Campi di SOLO TESTO per il motivo (ondata 2a, compito 4), mai input di
// scoring: `l.articolo` / `riferimento_articolo` (grammatica del luogo),
// `legati_racconti` (racconto + fonte di ogni LEGATO_A del luogo) e
// `temi_evocati[].etichetta/frase/fonte`. Racconti e frasi entrano nel
// `GraphCandidate` SOLO se hanno una fonte (filtro in
// `graph.connessioni.racconti_con_fonte`). `connessioni` resta invariata.
//
// `curiosita_testi/tipi/fonti` (ondata 2a, compito 5): curiosità del LUOGO come
// tre liste parallele (stesso indice = stessa curiosità, ordine del seed), SOLO
// narrazione, mai input di scoring. Su un grafo caricato prima del campo mancano:
// `coalesce` dà liste vuote (nessuna curiosità), mai un errore.
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
OPTIONAL MATCH (art:Artista)-[la:LEGATO_A]->(l)
OPTIONAL MATCH (bot:Bottega)-[:OFFRE]->(e)
OPTIONAL MATCH (e)-[:EVOCA]->(tema:Tema)
OPTIONAL MATCH (bot)-[isp:ISPIRATA_DA]->(ispart:Artista)
OPTIONAL MATCH (bot)-[:EVOCA]->(temab:Tema)
OPTIONAL MATCH (l)-[vic:VICINO]-(rif:Luogo {id: $vicino_a})
OPTIONAL MATCH (bp:Bottega {id: e.partner_id})-[:HA_ABBONAMENTO]->(partner:Partner)
WITH e, l,
     collect(DISTINCT art.nome) AS artisti_nomi,
     collect(DISTINCT {nome: art.nome, racconto: la.racconto, fonte: la.fonte}) AS legati_racconti,
     collect(DISTINCT {nome: bot.nome, mestiere: bot.mestiere,
                       fittizio: coalesce(bot.fittizio, true)}) AS botteghe,
     collect(DISTINCT {id: tema.id, nome: tema.nome, etichetta: tema.etichetta,
                       frase: tema.frase, fonte: tema.fonte}) AS temi_evocati,
     collect(DISTINCT {artista_id: ispart.id, racconto: isp.racconto}) AS racconti_ispirazione,
     collect(DISTINCT {id: temab.id, nome: temab.nome}) AS temi_bottega,
     min(vic.metri) AS distanza_m,
     min(rif.nome) AS riferimento_nome,
     min(rif.articolo) AS riferimento_articolo,
     collect(DISTINCT partner.abbonamento_attivo) AS abbonamenti_partner
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
  // `prenotabile` (Wave 3a, marketplace) può mancare su un grafo il cui seed
  // non è ancora stato rieseguito dopo l'introduzione della proprietà (Aura
  // Free si cancella dopo 30 giorni di inattività — CLAUDE.md — quindi questa
  // non è un'eccezione ma una condizione ricorrente e attesa). Un'Esperienza
  // senza questa proprietà non deve mai propagare `null` fino a
  // `ExperienceNode.prenotabile` (bool, default `false` nel contratto):
  // degrada all'unico default sicuro — non prenotabile — esattamente come
  // `partner_abbonamento_attivo` degrada a `true` per un Partner assente.
  coalesce(e.prenotabile, false) AS prenotabile,
  // `orari_apertura`: lista di stringhe "g|HH:MM|HH:MM" (formato di
  // `contracts.orari`, decodificato FAIL-CLOSED da `Neo4jCandidateSource`).
  // Su un grafo caricato prima dell'introduzione della proprietà manca: lì
  // `coalesce` dà la lista vuota, cioè "nessun orario dichiarato" (come
  // `ExperienceNode.orari_apertura` di default). Solo l'ASSENZA diventa vuota:
  // un valore presente ma malformato NON viene toccato qui e fa sollevare il
  // consumer.
  coalesce(e.orari_apertura, []) AS orari_apertura,
  // `sospesa`: NON si applica `coalesce`. Proprietà assente -> null nel record
  // (grafo caricato prima del campo), che `Neo4jCandidateSource` legge come
  // `false`; un valore presente non booleano fa sollevare il consumer
  // (fail-closed). Il filtro duro è nell'Experience Engine, non qui.
  e.sospesa AS sospesa,
  l.nome AS place_nome,
  l.articolo AS place_articolo,
  coalesce(l.curiosita_testi, []) AS curiosita_testi,
  coalesce(l.curiosita_tipi, []) AS curiosita_tipi,
  coalesce(l.curiosita_fonti, []) AS curiosita_fonti,
  artisti_nomi,
  legati_racconti,
  botteghe,
  temi_evocati,
  racconti_ispirazione,
  temi_bottega,
  distanza_m,
  riferimento_nome,
  riferimento_articolo,
  CASE WHEN size(abbonamenti_partner) = 0 THEN true ELSE abbonamenti_partner[0] END
    AS partner_abbonamento_attivo
ORDER BY e.id
