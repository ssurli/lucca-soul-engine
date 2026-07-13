// File GENERATO da `python -m graph.export_cypher`.
// Non modificare a mano: la fonte di verità è `graph/seed_lucca.py`.


CREATE CONSTRAINT luogo_id_unique IF NOT EXISTS FOR (n:Luogo) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT artista_id_unique IF NOT EXISTS FOR (n:Artista) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bottega_id_unique IF NOT EXISTS FOR (n:Bottega) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tema_id_unique IF NOT EXISTS FOR (n:Tema) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT esperienza_id_unique IF NOT EXISTS FOR (n:Esperienza) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evento_id_unique IF NOT EXISTS FOR (n:Evento) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT memoria_id_unique IF NOT EXISTS FOR (n:Memoria) REQUIRE n.id IS UNIQUE;
