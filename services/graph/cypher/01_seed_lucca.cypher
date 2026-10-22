// File GENERATO da `python -m graph.export_cypher`.
// Non modificare a mano: la fonte di verità è il modulo dataset `graph/seed_<città>.py`
// selezionato da CITY_SEED.


// --- Nodi: Luogo -------------------------------------------------------
MERGE (l:Luogo {id: 'mura-urbane'})
SET l.nome = 'Mura di Lucca', l.categoria = 'mura', l.articolo = 'le',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = NULL,
    l.lon = NULL;
MERGE (l:Luogo {id: 'piazza-anfiteatro'})
SET l.nome = 'Piazza dell\'Anfiteatro', l.categoria = 'piazza', l.articolo = 'la',
    l.curiosita_testi = ['Uno solo degli ingressi alla piazza ricalca un\'antica porta dell\'anfiteatro romano.'],
    l.curiosita_tipi = ['fatto'],
    l.curiosita_fonti = ['dato del committente'],
    l.curiosita_fonti_pubbliche = [false],
    l.lat = 43.8453750945062,
    l.lon = 10.506130836198794;
MERGE (l:Luogo {id: 'torre-guinigi'})
SET l.nome = 'Torre Guinigi', l.categoria = 'torre', l.articolo = 'la',
    l.curiosita_testi = ['Si racconta che il leccio in cima alla torre perse le foglie quando Paolo Guinigi fu catturato.'],
    l.curiosita_tipi = ['leggenda'],
    l.curiosita_fonti = ['dato del committente'],
    l.curiosita_fonti_pubbliche = [false],
    l.lat = 43.84385893695291,
    l.lon = 10.507472634710469;
MERGE (l:Luogo {id: 'duomo-san-martino'})
SET l.nome = 'Duomo di San Martino', l.categoria = 'chiesa', l.articolo = 'il',
    l.curiosita_testi = ['Sul pilastro del portico è inciso un labirinto, con un\'iscrizione latina che richiama Dedalo e Teseo. Lo si legge come simbolo del cammino dell\'anima verso la redenzione, lungo la Via Francigena.'],
    l.curiosita_tipi = ['fatto'],
    l.curiosita_fonti = ['dato del committente'],
    l.curiosita_fonti_pubbliche = [false],
    l.lat = 43.8407348442907,
    l.lon = 10.50546424867784;
MERGE (l:Luogo {id: 'casa-puccini'})
SET l.nome = 'Casa Natale di Giacomo Puccini', l.categoria = 'museo', l.articolo = 'la',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.843207634585866,
    l.lon = 10.501333062529884;
MERGE (l:Luogo {id: 'san-michele-in-foro'})
SET l.nome = 'Chiesa di San Michele in Foro', l.categoria = 'chiesa', l.articolo = 'la',
    l.curiosita_testi = ['Si racconta che nell\'anello al dito dell\'arcangelo, in cima alla facciata, sia incastonato un grande smeraldo, visibile al tramonto da un punto preciso della piazza.'],
    l.curiosita_tipi = ['leggenda'],
    l.curiosita_fonti = ['Comune di Lucca, Mappa del centro storico 2024'],
    l.curiosita_fonti_pubbliche = [true],
    l.lat = 43.843206920716746,
    l.lon = 10.502521515682991;
MERGE (l:Luogo {id: 'orto-botanico'})
SET l.nome = 'Orto Botanico di Lucca', l.categoria = 'giardino', l.articolo = 'l\'',
    l.curiosita_testi = ['Si racconta che nelle notti di luna piena il fantasma di Lucida Mansi attraversi le Mura su un cocchio, per poi sparire nel laghetto dell\'Orto Botanico.'],
    l.curiosita_tipi = ['leggenda'],
    l.curiosita_fonti = ['Comune di Lucca, cartina "Le Mura di Lucca"'],
    l.curiosita_fonti_pubbliche = [true],
    l.lat = 43.84100710602395,
    l.lon = 10.51019343794917;
MERGE (l:Luogo {id: 'teatro-del-giglio'})
SET l.nome = 'Teatro del Giglio', l.categoria = 'teatro', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84062952605113,
    l.lon = 10.502840967928876;
MERGE (l:Luogo {id: 'palazzo-pfanner'})
SET l.nome = 'Palazzo Pfanner', l.categoria = 'giardino', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.8455344278912,
    l.lon = 10.503022099598914;
MERGE (l:Luogo {id: 'san-frediano'})
SET l.nome = 'Basilica di San Frediano', l.categoria = 'chiesa', l.articolo = 'la',
    l.curiosita_testi = ['Nel mosaico della facciata compare anche Giuda, che l\'iconografia classica non metterebbe in questa scena. Alza la mano destra chiusa, con indice e mignolo tesi: il racconto popolare ci vede il gesto delle corna.'],
    l.curiosita_tipi = ['fatto'],
    l.curiosita_fonti = ['dato del committente'],
    l.curiosita_fonti_pubbliche = [false],
    l.lat = 43.84611439494372,
    l.lon = 10.504828564629559;
MERGE (l:Luogo {id: 'torre-delle-ore'})
SET l.nome = 'Torre delle Ore', l.categoria = 'torre', l.articolo = 'la',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84341924030429,
    l.lon = 10.504123087494012;
MERGE (l:Luogo {id: 'piazza-napoleone'})
SET l.nome = 'Piazza Napoleone', l.categoria = 'piazza', l.articolo = 'la',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.841381710949506,
    l.lon = 10.502460320754349;
MERGE (l:Luogo {id: 'via-fillungo'})
SET l.nome = 'Via Fillungo', l.categoria = 'via', l.articolo = NULL,
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.842686481849164,
    l.lon = 10.504022332247528;
MERGE (l:Luogo {id: 'baluardo-san-paolino'})
SET l.nome = 'Baluardo San Paolino', l.categoria = 'mura', l.articolo = 'il',
    l.curiosita_testi = ['Si racconta che il 12 luglio 1664, festa di San Paolino, i cannoni delle Mura spararono per i festeggiamenti senza essere caricati a salve, e che solo l\'intervento miracoloso del santo salvò la folla radunata sotto le Mura.'],
    l.curiosita_tipi = ['leggenda'],
    l.curiosita_fonti = ['Comune di Lucca, cartina "Le Mura di Lucca"'],
    l.curiosita_fonti_pubbliche = [true],
    l.lat = 43.840816169243126,
    l.lon = 10.496989849819938;
MERGE (l:Luogo {id: 'museo-nazionale-guinigi'})
SET l.nome = 'Museo Nazionale di Villa Guinigi', l.categoria = 'museo', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84532590685096,
    l.lon = 10.51227072450463;
MERGE (l:Luogo {id: 'chiesa-san-francesco'})
SET l.nome = 'Chiesa di San Francesco', l.categoria = 'chiesa', l.articolo = 'la',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84544716682871,
    l.lon = 10.510919717837515;
MERGE (l:Luogo {id: 'real-collegio'})
SET l.nome = 'Real Collegio', l.categoria = 'chiostro', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.846454429687576,
    l.lon = 10.503858387960499;
MERGE (l:Luogo {id: 'museo-barsanti-matteucci'})
SET l.nome = 'Museo Barsanti e Matteucci', l.categoria = 'museo', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.843638790269274,
    l.lon = 10.507385090128256;
MERGE (l:Luogo {id: 'via-del-fosso'})
SET l.nome = 'Via del Fosso', l.categoria = 'via', l.articolo = NULL,
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84529568253382,
    l.lon = 10.509682371585473;
MERGE (l:Luogo {id: 'baluardo-santa-croce'})
SET l.nome = 'Baluardo Santa Croce', l.categoria = 'mura', l.articolo = 'il',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84569128378519,
    l.lon = 10.497872636788552;
MERGE (l:Luogo {id: 'santi-giovanni-reparata'})
SET l.nome = 'Chiesa dei Santi Giovanni e Reparata', l.categoria = 'chiesa', l.articolo = 'la',
    l.curiosita_testi = [],
    l.curiosita_tipi = [],
    l.curiosita_fonti = [],
    l.curiosita_fonti_pubbliche = [],
    l.lat = 43.84119039780105,
    l.lon = 10.504274232740409;

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
SET t.nome = 'Verde e giardini', t.etichetta = 'verde e giardini', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'panorama'})
SET t.nome = 'Panorama', t.etichetta = 'panorama', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'storia'})
SET t.nome = 'Storia', t.etichetta = 'storia', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'medievale'})
SET t.nome = 'Medievale', t.etichetta = 'medioevo', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'gastronomia'})
SET t.nome = 'Gastronomia', t.etichetta = 'gastronomia', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'arte'})
SET t.nome = 'Arte', t.etichetta = 'arte', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'silenzio'})
SET t.nome = 'Silenzio e contemplazione', t.etichetta = 'silenzio e contemplazione', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'puccini'})
SET t.nome = 'Giacomo Puccini e la musica', t.etichetta = 'Giacomo Puccini', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'musica'})
SET t.nome = 'Musica', t.etichetta = 'musica', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'romanico'})
SET t.nome = 'Romanico', t.etichetta = 'romanico', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'con-bambini'})
SET t.nome = 'Adatto ai bambini', t.etichetta = 'adatto ai bambini', t.mostra_etichetta = false, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'artigianato'})
SET t.nome = 'Artigianato', t.etichetta = 'artigianato', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;
MERGE (t:Tema {id: 'liuteria'})
SET t.nome = 'Liuteria', t.etichetta = 'liuteria', t.mostra_etichetta = true, t.frase = NULL, t.fonte = NULL;

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
    e.sospesa = false,
    e.punti_arrivo_lat = [43.83975799648603, 43.84807404345435, 43.841277451100694, 43.842315738273435, 43.84552607610066, 43.83882258921756],
    e.punti_arrivo_lon = [10.506535046223485, 10.507089236931973, 10.496706879150684, 10.497113013689594, 10.514030908363878, 10.501625645596407],
    e.fonte_orari = 'dato del committente',
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
    e.sospesa = false,
    e.punti_arrivo_lat = [43.83975799648603, 43.84807404345435, 43.841277451100694, 43.842315738273435, 43.84552607610066, 43.83882258921756],
    e.punti_arrivo_lon = [10.506535046223485, 10.507089236931973, 10.496706879150684, 10.497113013689594, 10.514030908363878, 10.501625645596407],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-mercato-anfiteatro'})
SET e.titolo = 'L\'ovale dell\'Anfiteatro romano',
    e.place_id = 'piazza-anfiteatro',
    e.temi = ['storia', 'medievale'],
    e.durata_min = 30,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
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
    e.prezzo_eur = 8.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|09:30|16:30', '1|09:30|16:30', '2|09:30|16:30', '3|09:30|16:30', '4|09:30|16:30', '5|09:30|16:30', '6|09:30|16:30'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|10:00|18:00', '1|10:00|18:00', '2|10:00|18:00', '3|10:00|18:00', '4|10:00|18:00', '5|10:00|18:00', '6|12:00|18:00'];
MERGE (e:Esperienza {id: 'exp-casa-puccini-visita'})
SET e.titolo = 'Le stanze di Giacomo Puccini',
    e.place_id = 'casa-puccini',
    e.temi = ['puccini', 'musica', 'storia'],
    e.durata_min = 50,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = true,
    e.partner_id = NULL,
    e.prezzo_eur = 9.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'Puccini Museum',
    e.orari_apertura = ['0|10:00|14:00', '2|10:00|14:00', '3|10:00|14:00', '4|10:00|17:00', '5|10:00|17:00', '6|10:00|17:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
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
    e.prezzo_eur = 6.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['4|11:00|16:00', '5|11:00|16:00', '6|11:00|16:00'];
MERGE (e:Esperienza {id: 'exp-orto-botanico-bambini'})
SET e.titolo = 'Caccia al tesoro botanica per famiglie',
    e.place_id = 'orto-botanico',
    e.temi = ['con-bambini', 'verde'],
    e.durata_min = 60,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = 6.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['4|11:00|16:00', '5|11:00|16:00', '6|11:00|16:00'];
MERGE (e:Esperienza {id: 'exp-giardino-pfanner'})
SET e.titolo = 'Il giardino barocco di Palazzo Pfanner',
    e.place_id = 'palazzo-pfanner',
    e.temi = ['verde', 'arte', 'panorama'],
    e.durata_min = 30,
    e.al_chiuso = false,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = 10.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|08:00|16:30', '1|08:00|16:30', '2|08:00|16:30', '3|08:00|16:30', '4|08:00|16:30', '5|08:00|16:30', '6|08:00|16:30'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
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
    e.prezzo_eur = 8.0,
    e.prenotabile = false,
    e.sospesa = true,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'sito del Comune di Lucca',
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|17:30|21:00', '1|17:30|21:00', '2|17:30|21:00', '3|17:30|21:00', '4|17:30|21:00', '5|17:30|21:00', '6|17:30|21:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [43.84668153219125, 43.84060703195673, 43.84260326710044, 43.84750898171982, 43.848580906193554],
    e.punti_arrivo_lon = [10.502592655389329, 10.496914055249684, 10.513896040654814, 10.513950290731266, 10.508889574921993],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|16:00|17:00', '1|16:00|17:00', '2|16:00|17:00', '3|16:00|17:00', '4|16:00|17:00', '5|16:00|17:00', '6|16:00|17:00'];
MERGE (e:Esperienza {id: 'exp-collezione-villa-guinigi'})
SET e.titolo = 'La collezione archeologica di Villa Guinigi',
    e.place_id = 'museo-nazionale-guinigi',
    e.temi = ['arte', 'storia'],
    e.durata_min = 55,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = 6.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|12:00|18:00', '2|12:00|18:00', '3|12:00|18:00', '4|12:00|18:00', '5|12:00|18:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|09:30|12:30', '2|09:30|12:30', '3|09:30|12:30', '4|09:30|12:30', '5|09:30|12:30', '1|15:30|19:00', '2|15:30|19:00', '3|15:30|19:00', '4|15:30|19:00', '5|15:30|19:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|09:30|12:30', '2|09:30|12:30', '3|09:30|12:30', '4|09:30|12:30', '5|09:30|12:30', '1|15:30|19:00', '2|15:30|19:00', '3|15:30|19:00', '4|15:30|19:00', '5|15:30|19:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|09:30|12:30', '2|09:30|12:30', '3|09:30|12:30', '4|09:30|12:30', '5|09:30|12:30', '1|15:30|19:00', '2|15:30|19:00', '3|15:30|19:00', '4|15:30|19:00', '5|15:30|19:00'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|08:00|13:00', '2|08:00|13:00', '3|08:00|13:00', '4|08:00|13:00', '5|08:00|13:00', '6|08:00|13:00', '1|15:30|19:30', '2|15:30|19:30', '3|15:30|19:30', '4|15:30|19:30', '5|15:30|19:30', '6|15:30|19:30'];
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
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['1|09:30|12:30', '2|09:30|12:30', '3|09:30|12:30', '4|09:30|12:30', '5|09:30|12:30', '1|15:30|19:00', '2|15:30|19:00', '3|15:30|19:00', '4|15:30|19:00', '5|15:30|19:00'];
MERGE (e:Esperienza {id: 'exp-interno-san-michele'})
SET e.titolo = 'L\'interno di San Michele in Foro',
    e.place_id = 'san-michele-in-foro',
    e.temi = ['romanico', 'arte'],
    e.durata_min = 20,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|07:40|12:00', '1|07:40|12:00', '2|07:40|12:00', '3|07:40|12:00', '4|07:40|12:00', '5|07:40|12:00', '0|15:00|17:30', '1|15:00|17:30', '2|15:00|17:30', '3|15:00|17:30', '4|15:00|17:30', '5|15:00|17:30'];
MERGE (e:Esperienza {id: 'exp-interno-san-frediano'})
SET e.titolo = 'La basilica di San Frediano e il fonte lustrale',
    e.place_id = 'san-frediano',
    e.temi = ['romanico', 'arte', 'medievale'],
    e.durata_min = 30,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|08:30|12:00', '1|08:30|12:00', '2|08:30|12:00', '3|08:30|12:00', '4|08:30|12:00', '5|08:30|12:00', '0|15:00|17:00', '1|15:00|17:00', '2|15:00|17:00', '3|15:00|17:00', '4|15:00|17:00', '5|15:00|17:00', '6|10:30|17:00'];
MERGE (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'})
SET e.titolo = 'La chiesa di San Francesco e il suo chiostro',
    e.place_id = 'chiesa-san-francesco',
    e.temi = ['musica', 'silenzio', 'storia'],
    e.durata_min = 30,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['5|10:00|19:00', '6|10:00|19:00'];
MERGE (e:Esperienza {id: 'exp-chiostro-real-collegio'})
SET e.titolo = 'Il chiostro del Real Collegio',
    e.place_id = 'real-collegio',
    e.temi = ['silenzio', 'storia'],
    e.durata_min = 20,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|09:00|12:00', '1|09:00|12:00', '2|09:00|12:00', '3|09:00|12:00', '4|09:00|12:00'];
MERGE (e:Esperienza {id: 'exp-sortita-san-paolino'})
SET e.titolo = 'La sortita sotterranea del Baluardo San Paolino',
    e.place_id = 'baluardo-san-paolino',
    e.temi = ['storia', 'con-bambini'],
    e.durata_min = 20,
    e.al_chiuso = true,
    e.accessibile = true,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-museo-barsanti-matteucci'})
SET e.titolo = 'Il motore a scoppio di Barsanti e Matteucci',
    e.place_id = 'museo-barsanti-matteucci',
    e.temi = ['storia', 'con-bambini'],
    e.durata_min = 45,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'barsantiematteucci.it, via committente',
    e.orari_apertura = ['4|11:00|17:00', '5|11:00|17:00', '6|11:00|17:00'];
MERGE (e:Esperienza {id: 'exp-pfanner-dalle-mura'})
SET e.titolo = 'Il giardino Pfanner visto dalle Mura',
    e.place_id = 'palazzo-pfanner',
    e.temi = ['verde', 'panorama'],
    e.durata_min = 15,
    e.al_chiuso = false,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [43.846610457117684],
    e.punti_arrivo_lon = [10.502497041284132],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|08:00|17:00', '1|08:00|17:00', '2|08:00|17:00', '3|08:00|17:00', '4|08:00|17:00', '5|08:00|17:00', '6|08:00|17:00'];
MERGE (e:Esperienza {id: 'exp-via-del-fosso'})
SET e.titolo = 'Via del Fosso: il canale e i ponticelli',
    e.place_id = 'via-del-fosso',
    e.temi = ['silenzio', 'storia'],
    e.durata_min = 20,
    e.al_chiuso = false,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = [];
MERGE (e:Esperienza {id: 'exp-sotterraneo-santa-croce'})
SET e.titolo = 'Il sotterraneo del Baluardo Santa Croce e la mostra "Ri-conoscere le Mura"',
    e.place_id = 'baluardo-santa-croce',
    e.temi = ['storia'],
    e.durata_min = 40,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = NULL,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'dato del committente',
    e.orari_apertura = ['0|10:00|16:00', '1|10:00|16:00', '2|10:00|16:00', '3|10:00|16:00', '4|10:00|16:00', '5|10:00|16:00', '6|10:00|16:00'];
MERGE (e:Esperienza {id: 'exp-santi-giovanni-reparata'})
SET e.titolo = 'La chiesa dei Santi Giovanni e Reparata e l\'area archeologica',
    e.place_id = 'santi-giovanni-reparata',
    e.temi = ['storia', 'arte', 'romanico'],
    e.durata_min = 40,
    e.al_chiuso = true,
    e.accessibile = false,
    e.alimenta_memoria = false,
    e.partner_id = NULL,
    e.prezzo_eur = 4.0,
    e.prenotabile = false,
    e.sospesa = false,
    e.punti_arrivo_lat = [],
    e.punti_arrivo_lon = [],
    e.fonte_orari = 'museocattedralelucca.it, via committente',
    e.orari_apertura = ['0|10:00|18:00', '1|10:00|18:00', '2|10:00|18:00', '3|10:00|18:00', '4|10:00|18:00', '5|10:00|18:00', '6|10:00|18:00'];

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
MATCH (a:Luogo {id: 'chiesa-san-francesco'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'chiesa-san-francesco'}), (b:Luogo {id: 'mura-urbane'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'chiesa-san-francesco'}), (b:Luogo {id: 'piazza-anfiteatro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 400, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'chiesa-san-francesco'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'chiesa-san-francesco'}), (b:Luogo {id: 'via-fillungo'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 500, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'real-collegio'}), (b:Luogo {id: 'san-frediano'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'real-collegio'}), (b:Luogo {id: 'palazzo-pfanner'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'real-collegio'}), (b:Luogo {id: 'mura-urbane'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'real-collegio'}), (b:Luogo {id: 'piazza-anfiteatro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'real-collegio'}), (b:Luogo {id: 'via-fillungo'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'museo-barsanti-matteucci'}), (b:Luogo {id: 'torre-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'museo-barsanti-matteucci'}), (b:Luogo {id: 'via-fillungo'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'museo-barsanti-matteucci'}), (b:Luogo {id: 'piazza-anfiteatro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'museo-barsanti-matteucci'}), (b:Luogo {id: 'chiesa-san-francesco'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 350, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'museo-barsanti-matteucci'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-del-fosso'}), (b:Luogo {id: 'mura-urbane'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-del-fosso'}), (b:Luogo {id: 'chiesa-san-francesco'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-del-fosso'}), (b:Luogo {id: 'orto-botanico'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 150, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-del-fosso'}), (b:Luogo {id: 'museo-nazionale-guinigi'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'via-del-fosso'}), (b:Luogo {id: 'piazza-anfiteatro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'mura-urbane'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 50, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'palazzo-pfanner'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 450, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 550, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'real-collegio'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 600, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'san-frediano'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 650, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'baluardo-santa-croce'}), (b:Luogo {id: 'piazza-anfiteatro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 750, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'santi-giovanni-reparata'}), (b:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 100, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'santi-giovanni-reparata'}), (b:Luogo {id: 'piazza-napoleone'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 200, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'santi-giovanni-reparata'}), (b:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'santi-giovanni-reparata'}), (b:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 250, r.creato_il = datetime('2026-01-01T00:00:00+00:00');
MATCH (a:Luogo {id: 'santi-giovanni-reparata'}), (b:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:VICINO]->(b)
SET r.metri = 300, r.creato_il = datetime('2026-01-01T00:00:00+00:00');

// --- Relazioni: LEGATO_A (Artista -> Luogo) ----------------------------
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'casa-puccini'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = 'In questa chiesa il giovane Giacomo Puccini dava lezioni d\'organo al suo unico allievo, il sarto Carlo Della Nina; per la festa di San Michele vi si suonano ancora musiche della famiglia Puccini.', r.fonte = 'italia.it, pagina "San Michele in Foro"';
MATCH (a:Artista {id: 'artista-puccini'}), (l:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;
MATCH (a:Artista {id: 'artista-boccherini'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;
MATCH (a:Artista {id: 'artista-boccherini'}), (l:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = 'Nel 1751, a otto anni, Luigi Boccherini debuttò come voce bianca nelle feste di Santa Croce, celebrate in questa cattedrale.', r.fonte = 'Ministero della Cultura, "Profilo Boccherini"; Puccini Museum, pagina "Cattedrale di S. Martino"';
MATCH (a:Artista {id: 'artista-civitali'}), (l:Luogo {id: 'duomo-san-martino'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;
MATCH (a:Artista {id: 'artista-catalani'}), (l:Luogo {id: 'teatro-del-giglio'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;
MATCH (a:Artista {id: 'artista-boccherini'}), (l:Luogo {id: 'chiesa-san-francesco'})
MERGE (a)-[r:LEGATO_A]->(l)
SET r.racconto = NULL, r.fonte = NULL;

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
MATCH (e:Esperienza {id: 'exp-interno-san-michele'}), (l:Luogo {id: 'san-michele-in-foro'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-interno-san-frediano'}), (l:Luogo {id: 'san-frediano'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'}), (l:Luogo {id: 'chiesa-san-francesco'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-chiostro-real-collegio'}), (l:Luogo {id: 'real-collegio'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-sortita-san-paolino'}), (l:Luogo {id: 'baluardo-san-paolino'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-museo-barsanti-matteucci'}), (l:Luogo {id: 'museo-barsanti-matteucci'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-pfanner-dalle-mura'}), (l:Luogo {id: 'palazzo-pfanner'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-via-del-fosso'}), (l:Luogo {id: 'via-del-fosso'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-sotterraneo-santa-croce'}), (l:Luogo {id: 'baluardo-santa-croce'})
MERGE (e)-[:SI_SVOLGE_A]->(l);
MATCH (e:Esperienza {id: 'exp-santi-giovanni-reparata'}), (l:Luogo {id: 'santi-giovanni-reparata'})
MERGE (e)-[:SI_SVOLGE_A]->(l);

// --- Relazioni: EVOCA (Esperienza -> Tema), da temi --------------------
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['verde', 'panorama', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-passeggiata-mura'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['verde', 'con-bambini', 'panorama'] DELETE r;
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-bici-mura'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'medievale'] DELETE r;
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mercato-anfiteatro'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['panorama', 'verde', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-salita-torre-guinigi'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['arte', 'medievale', 'silenzio'] DELETE r;
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-duomo-volto-santo'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['puccini', 'musica', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'puccini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-casa-puccini-visita'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['puccini', 'musica', 'arte'] DELETE r;
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'puccini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-concerto-giglio'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['arte', 'medievale', 'romanico'] DELETE r;
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-facciata-san-michele'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['verde', 'silenzio'] DELETE r;
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-silenzio'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['con-bambini', 'verde'] DELETE r;
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-orto-botanico-bambini'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['verde', 'arte', 'panorama'] DELETE r;
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-giardino-pfanner'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['arte', 'medievale', 'romanico'] DELETE r;
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-mosaico-san-frediano'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'panorama'] DELETE r;
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-meccanismo-torre-ore'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'verde'] DELETE r;
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-piazza-napoleone'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['gastronomia', 'artigianato'] DELETE r;
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'}), (t:Tema {id: 'gastronomia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-struscio-fillungo'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['panorama', 'silenzio', 'verde'] DELETE r;
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-tramonto-baluardo'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['arte', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-collezione-villa-guinigi'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['liuteria', 'artigianato', 'musica'] DELETE r;
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'liuteria'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-laboratorio-liuteria'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['artigianato', 'con-bambini'] DELETE r;
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-decorazione-ceramica'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['artigianato', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-torchio-stamperia'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['gastronomia', 'con-bambini'] DELETE r;
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'}), (t:Tema {id: 'gastronomia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-buccellato-pasticceria'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['artigianato', 'silenzio'] DELETE r;
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'}), (t:Tema {id: 'artigianato'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-telaio-tessitura'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-interno-san-michele'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['romanico', 'arte'] DELETE r;
MATCH (e:Esperienza {id: 'exp-interno-san-michele'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-interno-san-michele'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-interno-san-frediano'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['romanico', 'arte', 'medievale'] DELETE r;
MATCH (e:Esperienza {id: 'exp-interno-san-frediano'}), (t:Tema {id: 'romanico'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-interno-san-frediano'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-interno-san-frediano'}), (t:Tema {id: 'medievale'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['musica', 'silenzio', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'}), (t:Tema {id: 'musica'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-chiesa-chiostro-san-francesco'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-chiostro-real-collegio'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['silenzio', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-chiostro-real-collegio'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-chiostro-real-collegio'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-sortita-san-paolino'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'con-bambini'] DELETE r;
MATCH (e:Esperienza {id: 'exp-sortita-san-paolino'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-sortita-san-paolino'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-museo-barsanti-matteucci'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'con-bambini'] DELETE r;
MATCH (e:Esperienza {id: 'exp-museo-barsanti-matteucci'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-museo-barsanti-matteucci'}), (t:Tema {id: 'con-bambini'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-pfanner-dalle-mura'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['verde', 'panorama'] DELETE r;
MATCH (e:Esperienza {id: 'exp-pfanner-dalle-mura'}), (t:Tema {id: 'verde'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-pfanner-dalle-mura'}), (t:Tema {id: 'panorama'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-via-del-fosso'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['silenzio', 'storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-via-del-fosso'}), (t:Tema {id: 'silenzio'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-via-del-fosso'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-sotterraneo-santa-croce'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia'] DELETE r;
MATCH (e:Esperienza {id: 'exp-sotterraneo-santa-croce'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-santi-giovanni-reparata'})-[r:EVOCA]->(t:Tema) WHERE NOT t.id IN ['storia', 'arte', 'romanico'] DELETE r;
MATCH (e:Esperienza {id: 'exp-santi-giovanni-reparata'}), (t:Tema {id: 'storia'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-santi-giovanni-reparata'}), (t:Tema {id: 'arte'})
MERGE (e)-[:EVOCA]->(t);
MATCH (e:Esperienza {id: 'exp-santi-giovanni-reparata'}), (t:Tema {id: 'romanico'})
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
