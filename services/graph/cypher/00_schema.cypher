// File GENERATO da `python -m graph.export_cypher`.
// Non modificare a mano: la fonte di verità è `graph/seed_lucca.py`.


// Tipi di relazione del grafo (documentazione, nessun vincolo Neo4j li
// richiede esplicitamente):
//   (:Artista)-[:LEGATO_A]->(:Luogo)
//   (:Luogo)-[:VICINO {metri}]->(:Luogo)              -- non orientata nel dominio
//   (:Bottega)-[:OFFRE]->(:Esperienza)
//   (:Esperienza)-[:SI_SVOLGE_A]->(:Luogo)
//   (:Esperienza)-[:EVOCA]->(:Tema)
//   (:Bottega)-[:EVOCA]->(:Tema)                      -- SEMANTICA, non di prossimità
//   (:Bottega)-[:ISPIRATA_DA {racconto}]->(:Artista)  -- SEMANTICA, NUOVA: introdotta
//     perché la Bottega di Liuteria fosse raggiungibile da Puccini per sole
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
