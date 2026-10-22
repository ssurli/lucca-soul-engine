// File GENERATO da `python -m graph.export_cypher`.
// Non modificare a mano: la fonte di verità è il modulo dataset `graph/seed_<città>.py`
// selezionato da CITY_SEED.


// Tipi di relazione del grafo (documentazione, nessun vincolo Neo4j li
// richiede esplicitamente):
//   (:Artista)-[:LEGATO_A {racconto, fonte}]->(:Luogo)  -- racconto solo con fonte
//   (:Luogo {curiosita_testi, curiosita_tipi, curiosita_fonti,
//     curiosita_fonti_pubbliche})  -- liste parallele, stesso indice = stessa curiosità;
//     tipo 'leggenda' | 'fatto'; ogni testo ha la fonte; fonti_pubbliche = booleani
//     (la fonte si puo' mostrare al pubblico); sola narrazione, mai nel punteggio
//   (:Luogo {lat, lon})  -- punto del luogo (WGS84, float a precisione piena), assenti
//     se il luogo non ha un punto; (:Esperienza {punti_arrivo_lat, punti_arrivo_lon})
//     -- liste parallele di float, stesso indice = stesso punto, ordine del seed (il
//     primo e' quello della prima tappa), scritte SEMPRE anche vuote. Codifica e regola
//     di risoluzione in graph/punti.py. DATO DI POSIZIONE: mai nel punteggio.
//   (:Luogo)-[:VICINO {metri, creato_il}]->(:Luogo)   -- non orientata nel dominio;
//     creato_il (Wave 4): VICINO_EPOCA per tutti gli archi del seed iniziale
//     ('sempre esistiti', non una data vera — vedi il modulo dataset), un vero
//     datetime.now(UTC) per ogni arco scritto dopo il seed. Serve a congelare uno
//     snapshot di connettività a un istante T (graph/topology.py,
//     cypher/12_non_connected_pairs.cypher) per l'indicatore nuovi_percorsi.
//   (:Esperienza {fonte_orari})  -- nome della fonte degli orari (testo; solo
//     trasparenza, mai nel punteggio)
//   (:Bottega)-[:OFFRE]->(:Esperienza)
//   (:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)
//   (:Esperienza)-[:EVOCA]->(:Tema)
//   (:Bottega)-[:EVOCA]->(:Tema)                      -- SEMANTICA, non di prossimità
//   (:Bottega)-[:ISPIRATA_DA {racconto}]->(:Artista)  -- SEMANTICA, NUOVA: introdotta
//     perché una bottega di liuteria fosse raggiungibile da Puccini per sole
//     connessioni semantiche, senza passare per VICINO (vedi graph/topology.py).
//   (:Bottega)-[:HA_ABBONAMENTO]->(:Partner)          -- COMMERCIALE, NUOVA
//     (Wave 3a, marketplace): Partner.abbonamento_attivo è l'UNICA leva che
//     decide presenza/assenza tra i candidati (mai il ranking, mai lo score).

CREATE CONSTRAINT luogo_id_unique IF NOT EXISTS FOR (n:Luogo) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT artista_id_unique IF NOT EXISTS FOR (n:Artista) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bottega_id_unique IF NOT EXISTS FOR (n:Bottega) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tema_id_unique IF NOT EXISTS FOR (n:Tema) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT esperienza_id_unique IF NOT EXISTS FOR (n:Esperienza) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evento_id_unique IF NOT EXISTS FOR (n:Evento) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT memoria_id_unique IF NOT EXISTS FOR (n:Memoria) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT partner_id_unique IF NOT EXISTS FOR (n:Partner) REQUIRE n.id IS UNIQUE;
