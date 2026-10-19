// File GENERATO da `python -m graph.export_cypher`.
// Non modificare a mano: la fonte di verità è il modulo dataset `graph/seed_<città>.py`
// selezionato da CITY_SEED.


// --- Nodi: Luogo -------------------------------------------------------
MERGE (l:Luogo {id: 'mura-urbane'})
SET l.nome = 'Mura di Lucca', l.categoria = 'mura';
MERGE (l:Luogo {id: 'piazza-anfiteatro'})
SET l.nome = 'Piazza dell\'Anfiteatro', l.categoria = 'piazza';
MERGE (l:Luogo {id: 'torre-guinigi'})
SET l.nome = 'Torre Guinigi', l.categoria = 'torre';
MERGE (l:Luogo {id: 'duomo-san-martino'})
SET l.nome = 'Duomo di San Martino', l.categoria = 'chiesa';
MERGE (l:Luogo {id: 'casa-puccini'})
SET l.nome = 'Casa Natale di Giacomo Puccini', l.categoria = 'museo';
MERGE (l:Luogo {id: 'san-michele-in-foro'})
SET l.nome = 'Chiesa di San Michele in Foro', l.categoria = 'chiesa';
MERGE (l:Luogo {id: 'orto-botanico'})
SET l.nome = 'Orto Botanico di Lucca', l.categoria = 'giardino';
MERGE (l:Luogo {id: 'teatro-del-giglio'})
SET l.nome = 'Teatro del Giglio', l.categoria = 'teatro';
MERGE (l:Luogo {id: 'palazzo-pfanner'})
SET l.nome = 'Palazzo Pfanner', l.categoria = 'giardino';
MERGE (l:Luogo {id: 'san-frediano'})
SET l.nome = 'Basilica di San Frediano', l.categoria = 'chiesa';
MERGE (l:Luogo {id: 'torre-delle-ore'})
SET l.nome = 'Torre delle Ore', l.categoria = 'torre';
MERGE (l:Luogo {id: 'piazza-napoleone'})
SET l.nome = 'Piazza Napoleone', l.categoria = 'piazza';
MERGE (l:Luogo {id: 'via-fillungo'})
SET l.nome = 'Via Fillungo', l.categoria = 'via';
MERGE (l:Luogo {id: 'baluardo-san-paolino'})
SET l.nome = 'Baluardo San Paolino', l.categoria = 'mura';
MERGE (l:Luogo {id: 'museo-nazionale-guinigi'})
SET l.nome = 'Museo Nazionale di Villa Guinigi', l.categoria = 'museo';

// --- Nodi: Artista ------------------------------------------------------
MERGE (a:Artista {id: 'artista-puccini'})
SET a.nome = 'Giacomo Puccini';
MERGE (a:Artista {id: 'artista-boccherini'})
SET a.nome = 'Luigi Boccherini';
MERGE (a:Artista {id: 'artista-civitali'})
SET a.nome = 'Matteo Civitali';
MERGE (a:Artista {id: 'artista-catalani'})
SET a.nome = 'Alfredo Catalani';

// --- Nodi: Bottega -------------------------------------------------------
MERGE (b:Bottega {id: 'liuteria-lucchese'})
SET b.nome = 'Bottega di liuteria', b.mestiere = 'liuteria', b.place_id = 'san-michele-in-foro', b.fittizio = true;
MERGE (b:Bottega {id: 'ceramica-lucca'})
SET b.nome = 'Laboratorio di ceramica', b.mestiere = 'ceramica', b.place_id = 'via-fillungo', b.fittizio = true;
MERGE (b:Bottega {id: 'stamperia-lucca'})
SET b.nome = 'Stamperia a torchio', b.mestiere = 'stampa', b.place_id = 'piazza-anfiteatro', b.fittizio = true;
MERGE (b:Bottega {id: 'pasticceria-storica'})
SET b.nome = 'Pasticceria', b.mestiere = 'pasticceria', b.place_id = 'piazza-napoleone', b.fittizio = true;
MERGE (b:Bottega {id: 'tessitura-lucca'})
SET b.nome = 'Laboratorio di tessitura', b.mestiere = 'tessitura', b.place_id = 'san-frediano', b.fittizio = true;

// --- Nodi: Tema -----------------------------------------------------------
MERGE (t:Tema {id: 'verde'})
SET t.nome = 'Verde e giardini';
MERGE (t:Tema {id: 'panorama'})
SET t.nome = 'Panorama';
MERGE (t:Tema {id: 'storia'})
SET t.nome = 'Storia';
MERGE (t:Tema {id: 'medievale'})
SET t.nome = 'Medievale';
MERGE (t:Tema {id: 'gastronomia'})
SET t.nome = 'Gastronomia';
MERGE (t:Tema {id: 'arte'})
SET t.nome = 'Arte';
MERGE (t:Tema {id: 'silenzio'})
SET t.nome = 'Silenzio e contemplazione';
MERGE (t:Tema {id: 'puccini'})
SET t.nome = 'Giacomo Puccini e la musica';
MERGE (t:Tema {id: 'musica'})
SET t.nome = 'Musica';
MERGE (t:Tema {id: 'romanico'})
SET t.nome = 'Romanico';
MERGE (t:Tema {id: 'con-bambini'})
SET t.nome = 'Adatto ai bambini';
MERGE (t:Tema {id: 'artigianato'})
SET t.nome = 'Artigianato';
MERGE (t:Tema {id: 'liuteria'})
SET t.nome = 'Liuteria';

// --- Nodi: Esperienza ---------------------------------------------------
MERGE (e:Esperienza {id: 'exp-passeggiata-mura'})
SET e.titolo = 'Passeggiata sulle Mura rinascimentali',
    e.place_id = 'mura-urbane',
    e.temi = ['verde', 'panorama', 'storia'],
    e.durata_min = 60,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-bici-mura'})
SET e.titolo = 'Giro in bicicletta sulle Mura',
    e.place_id = 'mura-urbane',
    e.temi = ['verde', 'con-bambini', 'panorama'],
    e.durata_min = 45,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-mercato-anfiteatro'})
SET e.titolo = 'Il mercato mattutino nell\'ovale romano',
    e.place_id = 'piazza-anfiteatro',
    e.temi = ['medievale', 'storia', 'gastronomia'],
    e.durata_min = 30,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-salita-torre-guinigi'})
SET e.titolo = 'Salita alla Torre Guinigi tra i lecci',
    e.place_id = 'torre-guinigi',
    e.temi = ['panorama', 'verde', 'storia'],
    e.durata_min = 40,
    e.al_chiuso = false,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-duomo-volto-santo'})
SET e.titolo = 'Il Volto Santo e il labirinto del Duomo',
    e.place_id = 'duomo-san-martino',
    e.temi = ['arte', 'medievale', 'silenzio'],
    e.durata_min = 35,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-casa-puccini-visita'})
SET e.titolo = 'Le stanze di Giacomo Puccini',
    e.place_id = 'casa-puccini',
    e.temi = ['puccini', 'musica', 'storia'],
    e.durata_min = 50,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-concerto-giglio'})
SET e.titolo = 'Un\'aria all\'opera del Giglio',
    e.place_id = 'teatro-del-giglio',
    e.temi = ['puccini', 'musica', 'arte'],
    e.durata_min = 90,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = 25.0,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-facciata-san-michele'})
SET e.titolo = 'La facciata scolpita di San Michele in Foro',
    e.place_id = 'san-michele-in-foro',
    e.temi = ['arte', 'medievale', 'romanico'],
    e.durata_min = 25,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-orto-botanico-silenzio'})
SET e.titolo = 'Un\'ora di silenzio tra le piante secolari',
    e.place_id = 'orto-botanico',
    e.temi = ['verde', 'silenzio'],
    e.durata_min = 45,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-orto-botanico-bambini'})
SET e.titolo = 'Caccia al tesoro botanica per famiglie',
    e.place_id = 'orto-botanico',
    e.temi = ['con-bambini', 'verde'],
    e.durata_min = 60,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-giardino-pfanner'})
SET e.titolo = 'Il giardino barocco di Palazzo Pfanner',
    e.place_id = 'palazzo-pfanner',
    e.temi = ['verde', 'arte', 'panorama'],
    e.durata_min = 30,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-mosaico-san-frediano'})
SET e.titolo = 'Il mosaico dorato di San Frediano',
    e.place_id = 'san-frediano',
    e.temi = ['arte', 'medievale', 'romanico'],
    e.durata_min = 25,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-meccanismo-torre-ore'})
SET e.titolo = 'Il meccanismo ottocentesco della Torre delle Ore',
    e.place_id = 'torre-delle-ore',
    e.temi = ['storia', 'panorama'],
    e.durata_min = 35,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-piazza-napoleone'})
SET e.titolo = 'La piazza granducale e i suoi platani',
    e.place_id = 'piazza-napoleone',
    e.temi = ['storia', 'verde'],
    e.durata_min = 20,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-struscio-fillungo'})
SET e.titolo = 'Struscio serale in via Fillungo',
    e.place_id = 'via-fillungo',
    e.temi = ['gastronomia', 'artigianato'],
    e.durata_min = 40,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-tramonto-baluardo'})
SET e.titolo = 'Tramonto dal Baluardo San Paolino',
    e.place_id = 'baluardo-san-paolino',
    e.temi = ['panorama', 'silenzio', 'verde'],
    e.durata_min = 30,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-collezione-villa-guinigi'})
SET e.titolo = 'La collezione archeologica di Villa Guinigi',
    e.place_id = 'museo-nazionale-guinigi',
    e.temi = ['arte', 'storia'],
    e.durata_min = 55,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-laboratorio-liuteria'})
SET e.titolo = 'Un violino nasce: laboratorio del liutaio',
    e.place_id = 'san-michele-in-foro',
    e.temi = ['liuteria', 'artigianato', 'musica'],
    e.durata_min = 50,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = 'liuteria-lucchese',
    e.prezzo_eur = 15.0,
    e.prenotabile = true,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-decorazione-ceramica'})
SET e.titolo = 'Decora la tua ciotola: bottega di ceramica',
    e.place_id = 'via-fillungo',
    e.temi = ['artigianato', 'con-bambini'],
    e.durata_min = 45,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = 'ceramica-lucca',
    e.prezzo_eur = 20.0,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-torchio-stamperia'})
SET e.titolo = 'Una pagina al torchio: la stamperia storica',
    e.place_id = 'piazza-anfiteatro',
    e.temi = ['artigianato', 'storia'],
    e.durata_min = 35,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = 'stamperia-lucca',
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-buccellato-pasticceria'})
SET e.titolo = 'Il buccellato: il dolce di Lucca',
    e.place_id = 'piazza-napoleone',
    e.temi = ['gastronomia', 'con-bambini'],
    e.durata_min = 20,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = 'pasticceria-storica',
    e.prezzo_eur = 8.0,
    e.prenotabile = false,
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-telaio-tessitura'})
SET e.titolo = 'Il telaio a mano: tessitura lucchese',
    e.place_id = 'san-frediano',
    e.temi = ['artigianato', 'silenzio'],
    e.durata_min = 40,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = 'tessitura-lucca',
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.orari_apertura = [];

// --- Nodi: Partner (Wave 3a, marketplace) -------------------------------
MERGE (p:Partner {id: 'partner-liuteria-lucchese'})
SET p.nome = 'Bottega di liuteria — abbonamento presenza', p.abbonamento_attivo = true;
MERGE (p:Partner {id: 'partner-ceramica-lucca'})
SET p.nome = 'Laboratorio di ceramica — abbonamento presenza', p.abbonamento_attivo = true;
MERGE (p:Partner {id: 'partner-stamperia-lucca'})
SET p.nome = 'Stamperia a torchio — abbonamento presenza', p.abbonamento_attivo = false;

// --- Relazioni: VICINO (Luogo -> Luogo) --------------------------------
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'baluardo-san-paolino'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 50, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'orto-botanico'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'palazzo-pfanner'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'san-frediano'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 600, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'mura-urbane'}), (b:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 550, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-anfiteatro'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-anfiteatro'}), (b:Luogo {id: 'san-frediano'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-anfiteatro'}), (b:Luogo {id: 'via-fillungo'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 150, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-anfiteatro'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 500, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-anfiteatro'}), (b:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-fillungo'}), (b:Luogo {id: 'torre-delle-ore'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-fillungo'}), (b:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-fillungo'}), (b:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-fillungo'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-fillungo'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-michele-in-foro'}), (b:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-michele-in-foro'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-michele-in-foro'}), (b:Luogo {id: 'torre-delle-ore'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-michele-in-foro'}), (b:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'duomo-san-martino'}), (b:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'duomo-san-martino'}), (b:Luogo {id: 'torre-delle-ore'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'duomo-san-martino'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'duomo-san-martino'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 600, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'casa-puccini'}), (b:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'teatro-del-giglio'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'teatro-del-giglio'}), (b:Luogo {id: 'torre-delle-ore'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'piazza-napoleone'}), (b:Luogo {id: 'torre-delle-ore'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'torre-delle-ore'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'torre-guinigi'}), (b:Luogo {id: 'palazzo-pfanner'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'palazzo-pfanner'}), (b:Luogo {id: 'san-frediano'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 150, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'palazzo-pfanner'}), (b:Luogo {id: 'baluardo-san-paolino'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-frediano'}), (b:Luogo {id: 'baluardo-san-paolino'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'san-frediano'}), (b:Luogo {id: 'orto-botanico'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 500, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-san-paolino'}), (b:Luogo {id: 'orto-botanico'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'orto-botanico'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 700, r.creato_il = datetime('2026-01-01T00:00:00+00:00');

// --- Relazioni: LEGATO_A (Artista -> Luogo) ----------------------------
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'casa-puccini'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-boccherini'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-boccherini'}), (l:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-civitali'}), (l:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[:LEGATO_A]->(l);
MATCH (a:Artista {id: 'artista-catalani'}), (l:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[:LEGATO_A]->(l);

// --- Relazioni: SI_SVOLGE_A (Esperienza -> Luogo), da place_id --------
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (l:Luogo {id: 'mura-urbane'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (l:Luogo {id: 'mura-urbane'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (l:Luogo {id: 'piazza-anfiteatro'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (l:Luogo {id: 'torre-guinigi'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (l:Luogo {id: 'duomo-san-martino'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (l:Luogo {id: 'casa-puccini'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (l:Luogo {id: 'teatro-del-giglio'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'}), (l:Luogo {id: 'orto-botanico'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'}), (l:Luogo {id: 'orto-botanico'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (l:Luogo {id: 'palazzo-pfanner'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (l:Luogo {id: 'san-frediano'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'}), (l:Luogo {id: 'torre-delle-ore'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'}), (l:Luogo {id: 'piazza-napoleone'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'}), (l:Luogo {id: 'via-fillungo'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (l:Luogo {id: 'baluardo-san-paolino'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'}), (l:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'}), (l:Luogo {id: 'via-fillungo'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'}), (l:Luogo {id: 'piazza-anfiteatro'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'}), (l:Luogo {id: 'piazza-napoleone'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'}), (l:Luogo {id: 'san-frediano'})
MERGE (e)-[:SI_SVOLGE_A]->(l);

// --- Relazioni: EVOCA (Esperienza -> Tema), da temi --------------------
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (t:Tema {id: 'gastronomia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'puccini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'puccini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'}), (t:Tema {id: 'gastronomia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'liuteria'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'}), (t:Tema {id: 'gastronomia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);

// --- Relazioni: OFFRE (Bottega -> Esperienza), da partner_id -----------
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (e:Esperienza {id: 'exp-laboratorio-liuteria'})
MERGE (b)-[:OFFRE]->(e);
MATCH (b:Bottega {id: 'ceramica-lucca'}), (e:Esperienza {id: 'exp-decorazione-ceramica'})
MERGE (b)-[:OFFRE]->(e);
MATCH (b:Bottega {id: 'stamperia-lucca'}), (e:Esperienza {id: 'exp-torchio-stamperia'})
MERGE (b)-[:OFFRE]->(e);
MATCH (b:Bottega {id: 'pasticceria-storica'}), (e:Esperienza {id: 'exp-buccellato-pasticceria'})
MERGE (b)-[:OFFRE]->(e);
MATCH (b:Bottega {id: 'tessitura-lucca'}), (e:Esperienza {id: 'exp-telaio-tessitura'})
MERGE (b)-[:OFFRE]->(e);

// --- Relazioni SEMANTICHE: EVOCA (Bottega -> Tema) ----------------------
// Non di prossimità: la bottega evoca i temi del suo mestiere anche a
// prescindere dall'esperienza specifica che offre.
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (t:Tema {id: 'liuteria'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (t:Tema {id: 'musica'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (t:Tema {id: 'artigianato'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'ceramica-lucca'}), (t:Tema {id: 'artigianato'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'stamperia-lucca'}), (t:Tema {id: 'artigianato'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'stamperia-lucca'}), (t:Tema {id: 'storia'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'pasticceria-storica'}), (t:Tema {id: 'gastronomia'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'tessitura-lucca'}), (t:Tema {id: 'artigianato'})
MERGE (b)-[:EVOCA]->(t);
MATCH (b:Bottega {id: 'tessitura-lucca'}), (t:Tema {id: 'silenzio'})
MERGE (b)-[:EVOCA]->(t);

// --- Relazioni SEMANTICHE: ISPIRATA_DA (Bottega -> Artista) -------------
// Tipo di relazione NUOVO (non VICINO, non LEGATO_A che è riservato ad
// Artista->Luogo): lega una bottega al lavoro di un artista che ne ispira
// il mestiere. `racconto` è la frase che rende esplicita la connessione.
// È ciò che rende percorribile, per sole connessioni semantiche,
// "Puccini -> ... -> liutaio -> violino" (vedi graph/topology.py).
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (a:Artista {id: 'artista-puccini'})
MERGE (b)-[r:ISPIRATA_DA]->(a)
SET r.racconto = 'Puccini compose opere; in una bottega di liuteria nascono i violini che le eseguono.';
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (a:Artista {id: 'artista-boccherini'})
MERGE (b)-[r:ISPIRATA_DA]->(a)
SET r.racconto = 'Boccherini fu virtuoso di violoncello: la stessa famiglia di strumenti che nasce in una bottega di liuteria.';

// --- Relazioni COMMERCIALI: HA_ABBONAMENTO (Bottega -> Partner) ---------
// Wave 3a (marketplace): Partner.abbonamento_attivo è l'UNICA leva che
// decide presenza/assenza di un'esperienza tra i candidati, mai il ranking.
// Una Bottega senza questa relazione è sempre visibile (default True).
MATCH (b:Bottega {id: 'liuteria-lucchese'}), (p:Partner {id: 'partner-liuteria-lucchese'})
MERGE (b)-[:HA_ABBONAMENTO]->(p);
MATCH (b:Bottega {id: 'ceramica-lucca'}), (p:Partner {id: 'partner-ceramica-lucca'})
MERGE (b)-[:HA_ABBONAMENTO]->(p);
MATCH (b:Bottega {id: 'stamperia-lucca'}), (p:Partner {id: 'partner-stamperia-lucca'})
MERGE (b)-[:HA_ABBONAMENTO]->(p);
