"""GOLDEN di Lucca: il comportamento del motore sul dataset di Lucca, congelato.

I file in `golden/` (`lucca_itinerari.json`, `lucca_punteggi.json`) sono i VALORI
ATTESI, catturati UNA volta prima dei refactor (CITY_SEED, parametro `vocabolario`,
vocabolari dei temi spostati nel dataset). Sono CONGELATI dal commit in cui sono
entrati: nessun diff ammesso mai piu'. Mai rigenerati, nemmeno
automaticamente: se un file manca il test FALLISCE.

UN TEST CHE FALLISCE QUI E' UNA REGRESSIONE SU LUCCA, non un motivo per
rigenerare il golden. Si corregge il codice, non il JSON.
UNICA modifica autorizzata: il caso `adapt|onnivoro|pioggia` e' stato aggiornato
quando `_migliore_alternativa` ha iniziato ad applicare `passa_filtri_duri`
(exp-torchio-stamperia, partner con abbonamento non attivo, non e' piu' reintrodotta).
SECONDA modifica autorizzata (2026-10-16), solo in `lucca_itinerari.json` e solo nelle
stringhe di attribuzione: le botteghe del seed sono dimostrative, rinominate col solo
mestiere e con attribuzione "(esempio dimostrativo)"; cambiano solo le stringhe
"Offerta da ..." (47 casi su 58); punteggi invariati (`lucca_punteggi.json` intatto).
TERZA modifica autorizzata (2026-10-16, wave "adattamento"), solo in
`lucca_itinerari.json`: i valori ATTESI dei 58 casi esistenti sono stati rigenerati
UNA volta, per le decisioni di prodotto 1 (tetto della giornata alle 24:00),
3 (campi nuovi: `tempo_disponibile_min`, `tempo_effettivo_min`,
`esito_adattamento`, `tappe_escluse`), 4 (esito e frase della tappa mantenuta
senza alternativa), 5 (connessioni identiche tra seed e Neo4j) e per l'attribuzione
senza ripetizioni (una sola disclosure "Offerta da ..."). Le RICHIESTE dei 58 casi
sono invariate: i 16 `adapt|...` diventano casi di retrocompatibilita'
(itinerario senza `tempo_disponibile_min`, quindi senza vincolo di budget, e `reason`
con l'attribuzione del formato vecchio, che l'adattamento sostituisce). Ogni
differenza e' stata attribuita a una decisione con uno script di confronto
atteso-vecchio/atteso-nuovo (zero differenze non attribuite).
In piu' sono stati AGGIUNTI 16 casi `adapt-budget|<profilo>|<segnale>` (stessi
profili e segnali dei 16 `adapt|...`) le cui richieste nascono dagli itinerari
composti dal codice NUOVO (con `tempo_disponibile_min`). Motivo: mettere alla
prova il vincolo di budget dell'adattamento, che i casi esistenti (senza budget)
non esercitano. Per questi casi, e per ogni caso con `tempo_effettivo_min`, il
test asserisce che i minuti dopo l'adattamento non lo superino.

QUARTA modifica autorizzata (2026-10-19, ondata 1, difetto g), solo in
`lucca_itinerari.json`: l'`atteso` di 14 casi, tutti adattamenti di pioggia o
affollamento (adapt-budget: con-bambini x3, curioso x3, onnivoro/affollamento-moderato;
adapt: accessibile/pioggia, con-bambini x3, curioso x3). Motivo: nella sostituzione
`_migliore_alternativa` ora (1) esclude un sostituto piu' caro della tappa tolta
(`prezzo_eur` None = 0) e (2) preferisce, tra gli ammessi, chi condivide almeno un
tema con la tappa tolta, poi score, poi id. Le RICHIESTE dei 74 casi e i 60 `atteso`
restanti sono identici; `lucca_punteggi.json` intatto (punteggi invariati: g non
tocca `calcola_score`). Ogni differenza e' stata attribuita da uno script di confronto
atteso-vecchio/risposta-nuova (zero non attribuite) a: un sostituto "prima" piu' caro
della tolta ora escluso (liuteria 15 EUR, pasticceria 8 EUR, concerto 25 EUR), oppure
un sostituto "dopo" che condivide un tema dove il "prima" non lo condivideva, oppure
slittamento/mantenuta conseguente (sostituto gia' preso da un'altra tappa; budget).

QUINTA modifica autorizzata (2026-10-19, ondata 1, difetto b), in `lucca_itinerari.json`
E, per la PRIMA volta, in `lucca_punteggi.json`. Motivo: correzione del seed di Lucca,
`exp-mosaico-san-frediano` al_chiuso True->False (e' all'aperto) e
`exp-meccanismo-torre-ore` al_chiuso False->True (e' al chiuso); `rules.calcola_score`
legge `al_chiuso` solo con segnale pioggia (bonus al chiuso) e caldo (penalita' all'aperto).
Itinerari: cambia l'`atteso` di 21 casi su 74 (richieste e altri 53 `atteso` identici):
13 compose (accessibile, ama-arte, con-bambini, curioso, onnivoro, poco-tempo x caldo e
pioggia, tranne contemplativo solo pioggia) e 8 adapt/adapt-budget (accessibile, con-bambini,
curioso, onnivoro x pioggia). Cambiano solo casi con caldo o pioggia. Punteggi: 21 chiavi
per ciascuna delle 3 funzioni (`calcola_score`, `score_fn_fredda`, `score_fn_calda`) =
San Frediano x 7 profili x {caldo, pioggia} (14) + Torre delle Ore x 7 profili x pioggia (7);
nessun'altra chiave. Attribuzione verificata da script (non dedotta): compose = San Frediano
perde il bonus al chiuso con pioggia/caldo (o Torre delle Ore lo guadagna con pioggia) e
cambiano posizione/ingresso/uscita; adapt = San Frediano, ora all'aperto, sotto la pioggia
e' sostituita o mantenuta senza alternativa, oppure non e' piu' disponibile come sostituto
al chiuso, oppure Torre delle Ore e' nuovo sostituto al chiuso (mai per chi chiede
accessibilita'), oppure slittamento/budget conseguente. Zero differenze non attribuite.

SESTA modifica autorizzata (2026-10-20, ondata 1b-2, recommender Cand. 1), SOLO in
`lucca_punteggi.json` e SOLO in `punteggi.score_fn_calda`: 630 chiavi su 770 cambiano
(max |diff| 0.0368, min 0.0023; tutte in diminuzione di penalita', mai in aumento).
`calcola_score` e `score_fn_fredda` byte-identici (verificato per uguaglianza dei valori
e del testo del file fuori da `score_fn_calda`); `lucca_itinerari.json` intatto (gli
itinerari girano a freddo, il gating non e' attivo sotto la soglia del cold start).
Motivo: `ranking.py` moltiplica la quota storica di ogni luogo per
`min(1, esposizione / (2/N))`, con `esposizione` = quota del luogo nei primi 3 dei 6
`ARCHETIPI_STRUTTURALI` e N = 15 luoghi di Lucca: 13 luoghi su 15 hanno fattore < 1, quindi
la penalita' storica si riduce su tutte le loro chiavi calde. Attribuzione verificata da
script, chiave per chiave (non dedotta): ogni chiave cambiata appartiene a un luogo con
fattore < 1, ogni chiave di un luogo con fattore < 1 cambia (0 invariate), zero chiavi non
attribuite; ricalcolando con il gating disattivato si riottiene esattamente il golden
precedente. Pesi, termine strutturale e cold start invariati.

SETTIMA modifica autorizzata (2026-10-20, ondata 1b-2, regola una tappa per luogo), SOLO
in `lucca_itinerari.json` (l'`atteso` di 25 casi su 78; richieste e altri 53 `atteso`
identici; `lucca_punteggi.json` byte-identico, verificato con `cmp`). Motivo:
`_seleziona_tappe` ammette al massimo UNA esperienza per `place_id` (prima 2) e, in
adattamento, un sostituto non puo' avere il `place_id` di un'altra tappa rimasta (il
luogo della tappa sostituita resta ammesso). Attribuzione verificata da script, caso per
caso (zero non attribuiti): tipo (a) = compose il cui `atteso` precedente aveva due tappe
nello stesso `place_id`; tipo (b) = adapt in cui un sostituto precedente stava nel luogo
di un'altra tappa rimasta; tipo (c) = slittamento o budget conseguente ad (a)/(b)
(la tappa tolta libera tempo, entrano altre tappe o cambiano gli orari).
  compose, 21 casi, tutti con duplicato nell'`atteso` precedente. Duplicati (numero di casi,
  alcuni ne hanno piu' di uno): San Michele in Foro (facciata + liuteria) 20; Mura urbane
  (bici + passeggiata) 6; San Frediano (mosaico + telaio) 6; Orto botanico 5; Piazza
  Napoleone 2. Classe: [a] = solo duplicato (le uniche tappe tolte sono membri di un
  duplicato, entrano altre nel budget liberato, l'ordine relativo delle restanti non
  cambia, cambiano gli orari successivi): 9 casi; [a+c] = oltre al duplicato cambiano altre
  tappe (tolta una non duplicata, o riordino delle restanti per slittamento/diversificazione):
  12 casi. Tabella (nome profilo|segnale, `-` tolte, `+` aggiunte, senza prefisso `exp-`):
  accessibile|affollamento [a] -laboratorio-liuteria +casa-puccini-visita
  accessibile|sereno [a] -laboratorio-liuteria +casa-puccini-visita
  accessibile|stanchezza [a] -laboratorio-liuteria +tramonto-baluardo,piazza-napoleone
  accessibile|visti [a+c] -laboratorio-liuteria,piazza-napoleone +casa-puccini-visita
  ama-arte|affollamento [a+c] -laboratorio-liuteria,giardino-pfanner +concerto-giglio
  ama-arte|pioggia [a] -facciata-san-michele +mosaico-san-frediano
  ama-arte|sereno [a+c] -laboratorio-liuteria,giardino-pfanner +concerto-giglio
  ama-arte|stanchezza [a+c] -laboratorio-liuteria +duomo-volto-santo,piazza-napoleone
  ama-arte|visti [a+c] -laboratorio-liuteria,giardino-pfanner,piazza-napoleone +concerto-giglio
  contemplativo|visti [a] -passeggiata-mura +orto-botanico-silenzio
  curioso|affollamento [a+c] -laboratorio-liuteria +salita-torre-guinigi,piazza-napoleone
  curioso|pioggia [a] -facciata-san-michele +buccellato-pasticceria
  curioso|sereno [a+c] -laboratorio-liuteria +casa-puccini-visita
  curioso|stanchezza [a+c] -laboratorio-liuteria,piazza-napoleone
      +tramonto-baluardo,salita-torre-guinigi
  curioso|visti [a+c] -laboratorio-liuteria,salita-torre-guinigi
      +casa-puccini-visita,tramonto-baluardo
  onnivoro|affollamento [a] -laboratorio-liuteria,orto-botanico-silenzio,telaio-tessitura
      +mercato-anfiteatro
  onnivoro|caldo [a+c] -facciata-san-michele,passeggiata-mura,orto-botanico-silenzio,
      telaio-tessitura
      +collezione-villa-guinigi,meccanismo-torre-ore,mercato-anfiteatro
  onnivoro|pioggia [a+c] -facciata-san-michele,telaio-tessitura,passeggiata-mura,piazza-napoleone
      +salita-torre-guinigi,mercato-anfiteatro,tramonto-baluardo
  onnivoro|sereno [a+c] -laboratorio-liuteria,passeggiata-mura,orto-botanico-silenzio,
      telaio-tessitura
      +collezione-villa-guinigi,meccanismo-torre-ore,mercato-anfiteatro
  onnivoro|stanchezza [a] -laboratorio-liuteria,orto-botanico-silenzio,passeggiata-mura,
      telaio-tessitura
      +meccanismo-torre-ore,collezione-villa-guinigi,mercato-anfiteatro
  onnivoro|visti [a] -laboratorio-liuteria,passeggiata-mura,orto-botanico-silenzio,telaio-tessitura,
      piazza-napoleone
      +collezione-villa-guinigi,meccanismo-torre-ore
  adapt, tipo (b), 4 casi: adapt-budget|accessibile|pioggia e adapt-profilo|accessibile|
  pioggia (telaio-tessitura stava a San Frediano, come il mosaico rimasto: ora
  giardino-pfanner); adapt-budget|onnivoro|affollamento-moderato (piazza-napoleone nel
  luogo del buccellato, struscio-fillungo nel luogo della decorazione ceramica);
  adapt-budget|onnivoro|affollamento-oltre-soglia (piazza-napoleone nel luogo del
  buccellato). Le richieste di adattamento restano le vecchie: contengono ancora itinerari
  con due tappe nello stesso luogo, che l'adattamento non tocca.
  Effetto sulla liuteria: `exp-laboratorio-liuteria` compare in 25 dei 42 compose prima,
  in 9 dopo.

OTTAVA modifica autorizzata (2026-10-20, ondata 1b-2, commit C; rigenerazione AUTORIZZATA
dal committente), in `lucca_itinerari.json` E in `lucca_punteggi.json`. Motivo: i dati del
commit B (dati reali invernali di Lucca) cambiano il seed: 17 luoghi (+ San Francesco e Real
Collegio, con i loro `vicino` e un `legato_a`), 26 esperienze (+ interno di San Michele,
interno di San Frediano, chiesa e chiostro di San Francesco, chiostro del Real Collegio),
`orari_apertura` invernali di 9 esperienze, `prezzo_eur` di 7, Torre delle Ore
(`exp-meccanismo-torre-ore`) con `sospesa=True`, `exp-mercato-anfiteatro` riscritta (titolo e
temi). Le RICHIESTE dei 78 casi preesistenti sono identiche (verificato per confronto con
`git show HEAD:...`); cambia l'`atteso` di 60 casi su 78 (compose 33 su 42; adapt 12 su 16,
adapt-budget 11 su 16, adapt-profilo 4 su 4), 18 restano identici.
  ATTRIBUZIONE degli itinerari, verificata da script e non dedotta. Metodo: il dataset di
  HEAD~1 (prima di B) con UNA categoria di B alla volta applicata (valori del seed attuale),
  replay delle stesse richieste e confronto con l'`atteso` precedente. Controlli: senza
  categorie i 78 `atteso` precedenti sono riprodotti ESATTAMENTE (0 differenze); con tutte e
  cinque il dataset coincide col seed attuale (60 differenze, quelle del golden nuovo).
  Cause = categorie che, applicate da sole, cambiano il caso. Causa UNICA, 36 casi: orario 19,
  luogo/esperienza nuova 10, prezzo 5, esperienza riscritta (mercato) 2. Cause COMBINATE, 24
  casi (nessuno senza causa: per ciascuno almeno una categoria da sola lo cambia). In tutto:
  orario 40 casi, luogo/esperienza nuova 22, prezzo 16, sospensione 10, mercato 9.
  [orario] adapt-budget|{con-bambini,onnivoro}|stanchezza; adapt|con-bambini|stanchezza;
  adapt|onnivoro|{affollamento-moderato,affollamento-oltre-soglia,pioggia,stanchezza};
  compose|accessibile|{caldo,stanchezza}; compose|con-bambini|{affollamento,caldo,sereno,
  stanchezza,visti}; compose|contemplativo|{affollamento,caldo,sereno,stanchezza,visti}.
  [nuovo] compose|ama-arte|{affollamento,pioggia,sereno,stanchezza,visti};
  compose|curioso|{affollamento,pioggia,sereno}; compose|poco-tempo|{caldo,pioggia}.
  [prezzo] adapt-budget|accessibile|pioggia; adapt-budget|con-bambini|{affollamento-moderato,
  pioggia}; adapt-profilo|accessibile|pioggia; adapt|con-bambini|affollamento-moderato
  (un sostituto "prima" piu' caro della tappa tolta ora e' escluso).
  [mercato] adapt-budget|curioso|{affollamento-moderato,affollamento-oltre-soglia}.
  [orario+prezzo] adapt-budget|con-bambini|affollamento-oltre-soglia;
  adapt-profilo|con-bambini|mura-affollate; adapt|accessibile|pioggia;
  adapt|con-bambini|{affollamento-oltre-soglia,pioggia};
  adapt|curioso|{affollamento-moderato,affollamento-oltre-soglia,pioggia}.
  [orario+nuovo] compose|ama-arte|caldo; compose|curioso|{caldo,stanchezza,visti}.
  [orario+sospensione+nuovo+mercato] compose|onnivoro|{affollamento,caldo,pioggia,sereno,
  stanchezza}. [orario+sospensione+nuovo] compose|onnivoro|visti.
  [sospensione+nuovo] compose|contemplativo|pioggia.
  [orario+mercato] adapt-budget|onnivoro|affollamento-moderato.
  [orario+prezzo+mercato] adapt-budget|onnivoro|affollamento-oltre-soglia.
  [orario+sospensione] adapt-budget|onnivoro|pioggia.
  [prezzo+sospensione] adapt-profilo|no-bambini|pioggia.
  [prezzo+sospensione+nuovo] adapt-profilo|pioggia|tappa-gratuita.
  I casi `adapt*` partono da itinerari gia' composti: cambiano perche' un sostituto e' piu'
  caro (prezzo), chiuso all'arrivo (orario), sospeso (Torre delle Ore), nuovo (interni al
  chiuso) o riscritto (mercato), oppure per slittamento/budget conseguente.
  PUNTEGGI. Chiavi: 770 -> 910 per ciascuna delle 3 funzioni. Chiavi NUOVE: 140 per funzione
  = le 4 esperienze nuove x 7 profili x 5 segnali (35 ciascuna); nessun'altra. Chiavi CAMBIATE
  nelle 22 esperienze preesistenti: `calcola_score` e `score_fn_fredda` 31, tutte di
  `exp-mercato-anfiteatro` (temi riscritti, max |diff| 0.0225); prezzi, orari e sospensione
  non sono letti da `calcola_score` (verificato: 0 chiavi cambiate applicandoli da soli).
  `score_fn_calda` 521 = le stesse 31 + 490 su 14 esperienze preesistenti (35 ciascuna):
  causa le 4 candidate nuove nell'insieme dei candidati (gating di esposizione della Cand. 1,
  `ranking.py`); verificato: con i dati B ma l'insieme dei candidati SENZA le 4 nuove restano
  solo le 31 chiavi del mercato.
  CASI NUOVI, 13 (richieste nuove, `atteso` dal codice attuale, a freddo):
  `demo|<profilo>|sereno-10` per i 7 profili di `lucca_punteggi.json` (accessibile, ama-arte,
  con-bambini, contemplativo, curioso, onnivoro, poco-tempo), sabato 12/12/2026 ore 10:00,
  sereno; `demo|{curioso,con-bambini,contemplativo}|pioggia-15` (tipo adapt): itinerario
  composto alle 15:00 di sabato 12/12/2026 con meteo sereno e adattato alle 15:00 con meteo
  pioggia, profilo nell'AdaptRequest; `feriale|{curioso,contemplativo,con-bambini}|sereno-10`,
  mercoledi' 9/12/2026 ore 10:00. Il giorno e l'ora sono quelli del `Signal` (`data`, `ora`),
  non l'orologio (`get_adesso` resta fisso). Le proprieta' dei casi sono asserite da
  `test_golden_orari_rispettati`, `test_golden_nessuna_sospesa` e
  `test_golden_pioggia_sostituti_non_piu_cari`, su TUTTI i casi.

NONA modifica autorizzata (2026-10-20, ondata 1c, contenuti locali per la demo;
rigenerazione AUTORIZZATA dal committente), in `lucca_itinerari.json` E in
`lucca_punteggi.json`. Motivo: i dati del commit 47eb400 cambiano il seed in due modi (e
solo in due): (a) 4 luoghi nuovi (museo-barsanti-matteucci, via-del-fosso,
baluardo-santa-croce, santi-giovanni-reparata; 21 in tutto) con 22 archi VICINO, e 6
esperienze nuove (sortita di San Paolino, Barsanti e Matteucci, Pfanner dalle Mura, via del
Fosso, sotterraneo di Santa Croce, Santi Giovanni e Reparata; 32 in tutto); (b) gli orari
DIMOSTRATIVI delle 5 botteghe (liuteria, ceramica, stamperia, telaio mar-sab 9:30-12:30 e
15:30-19:00; pasticceria mar-dom 8-13 e 15:30-19:30). Le RICHIESTE dei 91 casi sono
identiche (verificato per confronto con `git show HEAD:...`; nessun caso aggiunto o tolto):
anche i 3 `demo|...|pioggia-15` restano casi `adapt` con l'itinerario congelato composto con
i dati vecchi. Cambia l'`atteso` di 69 casi su 91, 22 restano identici.
  ATTRIBUZIONE degli itinerari, verificata da script e non dedotta (stesso metodo
  dell'OTTAVA). Dataset del commit c446a13 (prima di 1c) con UNA categoria applicata alla
  volta (valori del seed attuale): [nuovo] = luoghi + legato_a + vicino + 6 esperienze nuove;
  [orario] = `orari_apertura` delle 5 botteghe. Replay delle stesse richieste e confronto
  con l'`atteso` precedente. Controlli: senza categorie i 91 `atteso` precedenti sono
  riprodotti ESATTAMENTE (0 differenze); con entrambe il dataset coincide col seed attuale
  (luoghi, vicino ed esperienze uguali; 69 differenze, quelle del golden nuovo). Zero casi
  senza causa. Causa UNICA 31 casi: orario 16, nuovo 15. Cause COMBINATE (orario+nuovo) 38
  casi. In tutto: orario 54 casi, nuovo 53.
  Composizione/adattamento (composizione = compose, demo `sereno-10`, feriale: 38 cambiati su
  52; adattamento = adapt, adapt-budget, adapt-profilo, demo `pioggia-15`: 31 su 39):
    composizione 38 = orario solo 2 (compose|accessibile|{caldo,pioggia}); nuovo solo 12
    (compose|{ama-arte,curioso}|{affollamento,sereno,stanchezza,visti}, demo|ama-arte|
    sereno-10, demo|curioso|sereno-10, feriale|{con-bambini,curioso}|sereno-10);
    orario+nuovo 24 (compose 21, demo 2, feriale 1).
    adattamento 31 = orario solo 14 (adapt e adapt-budget, 7 ciascuno: accessibile|
    {affollamento-moderato,pioggia}, curioso|{affollamento-moderato,stanchezza},
    onnivoro|{affollamento-moderato,affollamento-oltre-soglia,stanchezza}); nuovo solo 3
    (i 3 `demo|...|pioggia-15`: un sostituto al chiuso nuovo, p. es. Barsanti, Santi Giovanni
    e Reparata, sortita di San Paolino); orario+nuovo 14 (adapt-budget 5, adapt-profilo 4,
    adapt 5).
  Lettura: compose cambiano per esperienze nuove che entrano nel ranking/nel budget, o per
  botteghe chiuse all'arrivo (lunedi' e prima delle 15:30 o dopo le 12:30); adapt per
  sostituti nuovi (al chiuso) o botteghe chiuse all'arrivo, oppure slittamento/budget
  conseguente. I 22 identici: 14 composizione, 8 adattamento.
  DEMO PIOGGIA-15 (misura a parte). Richiesta congelata (itinerario vecchio): tappe
  all'aperto mantenute senza alternativa 1 per caso (mosaico di San Frediano; Piazza
  Napoleone x2), prima di 1c 0, 3 e 2. Flusso realistico (composto alle 15:00 sereno con i
  dati 1c, adattato alle 15:00 con pioggia, profilo nell'AdaptRequest; NON e' nel golden):
  con-bambini 1 (facciata di San Michele), contemplativo 1 (Piazza Napoleone), curioso 0.
  PUNTEGGI. Chiavi: 910 -> 1120 per ciascuna delle 3 funzioni. Chiavi NUOVE: 210 per funzione
  = le 6 esperienze nuove x 7 profili x 5 segnali (35 ciascuna); nessun'altra, nessuna
  tolta. Chiavi CAMBIATE nelle 26 esperienze preesistenti: `calcola_score` e
  `score_fn_fredda` 0 (gli orari non sono letti dallo score; i luoghi nuovi non entrano nello
  score di un'altra esperienza). `score_fn_calda` 595 = 17 esperienze preesistenti x 35
  (max |diff| 0.0201); 9 esperienze (7 luoghi) restano invariate. Causa: le 6 candidate
  nuove nell'insieme dei candidati (N luoghi 17 -> 21): cambiano il fattore di gating di
  esposizione della Cand. 1 (`ranking.py`: 7 luoghi, es. palazzo-pfanner da 0.472 a 0.000,
  mura-urbane e orto-botanico a 1.000) e la quota strutturale (casa-puccini, san-frediano,
  san-michele-in-foro, teatro-del-giglio); verificato: con i dati 1c ma l'insieme dei
  candidati SENZA le 6 nuove restano 0 chiavi cambiate.

DECIMA modifica autorizzata (2026-10-21, ondata 2a, testi; rigenerazione AUTORIZZATA dal
committente), SOLO in `lucca_itinerari.json` (`lucca_punteggi.json` byte-identico, verificato
con `cmp`: nessun punteggio e' stato toccato). Motivo: l'ondata 2a cambia SOLO i testi:
nessuna frase sull'affollamento senza un valore misurato (6bd30b2), `titolo` leggibili sulle
tappe (e62fd97), `reason` riscritti da campi separati dalle connessioni, senza "Evoca il
tema" ne' "X e' legato a" (6c8ca15), curiosita' dei luoghi come racconto, mai nel punteggio
(87f9b2f). Decisione del committente: le tappe non cambiano, il diff riguarda solo i testi.
Cambia l'`atteso` di 83 casi su 91: 80 dei 88 casi a richiesta invariata (solo testo) e i 3
`demo|{curioso,con-bambini,contemplativo}|pioggia-15`; 8 casi restano identici.
  ATTRIBUZIONE, verificata da script e non dedotta. Per gli 88 casi con richiesta invariata,
  tolti `reason` (tappe ed escluse) l'`atteso` nuovo coincide con il vecchio campo per campo
  (esperienze, ordine, arrivo, durata, esito, budget, escluse): 80 cambiati, 0 differenze non
  testuali, 8 identici.
  I 3 `demo|...|pioggia-15` sono stati RIGENERATI ANCHE NELLA RICHIESTA (come nella OTTAVA:
  sabato 12/12/2026, itinerario composto alle 15:00 con meteo sereno via `POST /itinerary`,
  profilo e `person_id` del caso, poi adattato alle 15:00 con meteo pioggia, profilo
  nell'AdaptRequest): l'itinerario congelato nella richiesta conteneva i testi vecchi, che
  l'adattamento conserva per le tappe non toccate. Con la richiesta nuova le tappe cambiano
  rispetto al vecchio `atteso`: con-bambini la composizione include la sortita di San Paolino
  prima della facciata (e il mosaico di San Frediano esce), contemplativo composizione e
  adattamento con le stesse tappe, curioso la composizione ha santi-giovanni-reparata e
  mercato-anfiteatro al posto di bici-mura e Piazza Napoleone. La richiesta vecchia era
  l'itinerario composto con i dati precedenti alla 1c (NONA modifica).
  Verifica a parte (eseguita, non dedotta): composizione e adattamento di questi tre casi con
  il codice PRECEDENTE all'ondata (f701b04) danno le stesse tappe, arrivi, durate ed esiti del
  codice attuale: la differenza di tappe rispetto al vecchio `atteso` viene dalla richiesta
  rigenerata, non dal codice dell'ondata.
  Etichette dei temi: "adatto ai bambini" non e' un'etichetta mostrata
  (`Tema.mostra_etichetta=False`; connessioni e punteggi invariati) e l'etichetta del tema di
  Puccini e' "Giacomo Puccini": nessun reason di `Temi:` cita "bambini" per chi non li ha.
  Nessuna frase sul prezzo (decisione del committente): la frase 3 dei motivi e' solo
  "Al chiuso."/"All'aperto."; ", gratuita" compariva anche con `prezzo_eur` assente (falso,
  p. es. il Duomo). Seed e prezzi invariati. Rispetto al golden di HEAD (1f4b157) cambiano 81
  casi su 91 e SOLO per la rimozione di ", gratuita" nei reason (nuovo == HEAD con ", gratuita"
  tolto, richieste dei 3 `pioggia-15` incluse, 91 casi su 91, tappe invariate). Rispetto a
  main (f701b04) i conteggi della DECIMA restano 83 casi su 91 cambiati (80 degli 88 a richiesta
  invariata, 8 identici, 0 differenze non testuali, + i 3 `pioggia-15`).
  CRITERI sui testi (asseriti da `test_golden_testi.py`): nessun "affollat" senza affollamento
  misurato, nessun "Evoca il tema", "e' legato a", "exp-" o "gratuit" in `reason`/`titolo`,
  nessun `reason`
  vuoto, la frase del profilo (`rag.reasons._tratto_dominante`) al massimo una volta per
  itinerario. Sui casi `adapt`/`adapt-budget`/`adapt-profilo` (richiesta vecchia) le tappe non
  toccate CONSERVANO per contratto il `reason` della richiesta e le mantenute senza alternativa
  lo conservano e vi aggiungono una frase: lo stesso criterio vale solo per i testi nuovi
  (tappe sostituite ed escluse).

UNDICESIMA modifica autorizzata (2026-10-22, ondata 2b, compito 4; rigenerazione AUTORIZZATA
dal committente), SOLO in `lucca_itinerari.json` (`lucca_punteggi.json` byte-identico,
verificato con `git diff` e confronto: nessun punteggio toccato). Motivo: i testi dei motivi
(9ae5185): la frase del profilo entra solo per tratti netti (>= 0,7 o <= 0,2) e, in
adattamento, compare sulla prima tappa SOSTITUITA dopo "Sostituita per ...", al massimo una
volta per itinerario. Le RICHIESTE dei 91 casi sono invariate; le tappe non cambiano (esperienze,
ordine, arrivo, durata, esito, budget, escluse), cambiano solo i `reason`. Cambia l'`atteso` di
12 casi su 91, sempre e solo la prima tappa: adapt-profilo|no-bambini|pioggia,
adapt-profilo|pioggia|tappa-gratuita, compose|poco-tempo|{affollamento,caldo,pioggia,sereno,
stanchezza,visti}, demo|{con-bambini,contemplativo,curioso}|pioggia-15, demo|poco-tempo|
sereno-10; 79 restano identici. ATTRIBUZIONE verificata da script (non dedotta): rigiocate le
richieste invariate sul BFF isolato, tolti i `reason` (tappe ed escluse) l'`atteso` nuovo
coincide con il vecchio campo per campo: 12 cambiati, 0 differenze non testuali.

DODICESIMA modifica autorizzata (2026-10-22, ondata 3; rigenerazione AUTORIZZATA dal
committente; cambiano anche le tappe), in `lucca_itinerari.json` E in `lucca_punteggi.json`.
Motivo: (1) il codice dell'ondata 3 cambia gli itinerari: 8198fdb (compito 1, taglio per
stanchezza al prefisso piu' vicino ai 2/3), afdc223 (compito 4, trasferimento reale tra tappe
dai punti di arrivo: gli arrivi non sono piu' a passo fisso), 7b5cf5f (compito 8, 3 luoghi e 3
esperienze nuovi: finestra Bernardini, parco giochi di San Donato, solchi di San Pietro
Somaldi; 24 luoghi e 35 esperienze in tutto) e 8aa734b (6 archi VICINO per quei luoghi);
0f310ef, 02e4e96, 5b3641d, 9c20380, 4382cbb, 21c7263 non cambiano nessun caso (campi non
confrontati dal golden: `punto_arrivo`, `fonte`, `fonte_orari`, ecc.; verificato, 0 differenze).
(2) i 10 casi `demo|...` hanno PROFILI NUOVI: costruiti passando a
`rag.onboarding.profile_from_answers` le risposte ESATTE dell'app (`kOnboardingQuestions`,
`firenze` nascosta e non inviata), mai valori scritti a mano. Tempo "Mezza giornata, circa tre
ore" (180 min) per tutti tranne poco-tempo ("Circa un'ora, poco tempo", 60 min: la risposta
che definisce il profilo). Risposte (perdersi / silenzio_musica / bellezza_storie / bambini /
accessibilita), tutte con il testo esatto dell'app:
  curioso       "Sì, mi piace perdermi..." / Un mix / Un po' di bellezza e... / No / No
  contemplativo "Un po', ma con qualche punto fermo" / Silenzio / Un po' di bellezza e... / No / No
  ama-arte      "Un po', ma..." / Un mix / "La bellezza silenziosa dei luoghi" / No / No
  con-bambini   "Un po', ma..." / Un mix / Un po' di bellezza e... / "Sì, sono con bambini" / No
  accessibile   "Un po', ma..." / Un mix / Un po' di bellezza e... / No / "Sì, mi serve..."
  onnivoro      "Sì, mi piace perdermi..." / Silenzio / La bellezza / "Sì, sono con bambini" / No
  poco-tempo    "Un po', ma..." / Un mix / Un po' di bellezza e... / No / No (tempo 1 ora)
Le richieste degli 81 casi non `demo|` sono IDENTICHE; i 10 `demo|` sono rigenerati nella
richiesta (profilo completo come i `adapt-profilo|`; stessa forma di prima: compose sabato
12/12/2026 ore 10:00 sereno; `pioggia-15` = itinerario composto via `POST /itinerary` alle
15:00 con meteo sereno, poi adattato alle 15:00 con pioggia, profilo nell'AdaptRequest).
Cambia l'`atteso` di 91 casi su 91 (81 non `demo|` + 10 `demo|`).
  ATTRIBUZIONE, verificata da script e non dedotta. Metodo: le stesse richieste rigiocate sul
BFF isolato con il codice di OGNI commit (f90b146 e i 10 commit dell'ondata, worktree
temporanei poi rimossi). Controllo: a f90b146 i 91 `atteso` precedenti sono riprodotti
ESATTAMENTE (0 differenze). Cause = commit in cui l'esito del caso cambia (incrementale).
  Casi non `demo|` (81, richieste invariate; 409 tappe cambiate in tutto, contando le
posizioni con id/arrivo/durata/esito diversi e la differenza di lunghezza): causa UNICA
c4 46 casi (28 solo orari di arrivo, 18 anche tappe diverse), c8 5, c1 2; cause COMBINATE
c4+c8 22, c4+c8+VICINO 3, c1+c4 2, c4+VICINO 1. In tutto: c1 4 casi, c4 74, c8 30, VICINO 4.
Zero casi senza causa. I 4 casi VICINO sono tutti `compose|{ama-arte,curioso,onnivoro,poco-
tempo}|visti` (gli archi VICINO contano solo con `luoghi_gia_visti` non vuoto: con la lista
vuota non cambiano punteggi ne' casi `demo|`; riverificato: 0 casi `demo|` cambiati allo
stadio 8aa734b e punteggi uguali tra 7b5cf5f e 8aa734b).
  Casi `demo|` (10): la causa e' sempre i PROFILI NUOVI (la richiesta cambia, 10 su 10).
Effetto del solo codice sulle richieste nuove (stessa richiesta rigiocata allo stadio
precedente e dopo): c4 (trasferimento reale) in tutti e 10; c8 (esperienze nuove) in 6
(ama-arte, con-bambini x2, curioso x2, onnivoro); c1 e VICINO in nessuno (nessuna stanchezza,
nessun luogo gia' visto). Zero non attribuiti.
  PUNTEGGI. Chiavi: 1120 -> 1225 per ciascuna delle 3 funzioni. Chiavi NUOVE: 105 per funzione
= le 3 esperienze nuove x 7 profili x 5 segnali; nessuna tolta. Chiavi CAMBIATE nelle 32
esperienze preesistenti: `calcola_score` e `score_fn_fredda` 0; `score_fn_calda` 595 = 17
esperienze x 35 (max |diff| 0.0076). Causa: le 3 candidate nuove nell'insieme dei candidati
(N luoghi 21 -> 24: cambia il gating di esposizione della Cand. 1, `ranking.py`); verificato:
con i dati attuali ma l'insieme dei candidati SENZA le 3 nuove restano 0 chiavi cambiate.
  CRITERI sui testi (asseriti da `test_golden_testi.py`, verificati su TUTTI i casi `demo|`):
nessun "affollat", "e' legato a", "Evoca il tema", "gratuit", "exp-" in `reason`/`titolo`.

TREDICESIMA modifica autorizzata (2026-10-26, ondata 4, compito 1; rigenerazione AUTORIZZATA
dal committente), SOLO in `lucca_itinerari.json` (`lucca_punteggi.json` byte-identico,
verificato con `cmp`: nessun punteggio toccato). Motivo: riordino per vicinanza delle tappe
GIA' SCELTE, `engine._riordina_per_vicinanza` (regola approvata: prima tappa e tappe senza
punto ferme; fino a 7 tappe mobili tutte le permutazioni, sopra 7 il vicino piu' prossimo;
ordine ammesso solo se tutte aperte all'arrivo per tutta la durata, budget effettivo
rispettato e metri a piedi STRETTAMENTE minori; tra gli ammessi meno metri, a parita' le
posizioni originali lessicograficamente minori). Solo composizione, mai adattamento: le
coordinate decidono l'ordine di visita, mai quali tappe, ne' la prima, ne' il punteggio.
Cambia l'`atteso` di 42 casi su 91: 39 composizioni (su 52: compose 42, demo `sereno-10` 7,
feriale 3; 13 restano identiche) e i 3 `demo|{con-bambini,contemplativo,curioso}|pioggia-15`;
49 restano identici. Le RICHIESTE di 88 casi sono identiche (verificato per confronto con
la versione precedente del file); le richieste di tutti i 36 `adapt|`, `adapt-budget|`,
`adapt-profilo|` sono congelate e il loro `atteso` e' identico (verificato: stesso `atteso`
rigiocando la richiesta col codice nuovo).
  ATTRIBUZIONE, verificata da script e non dedotta (le stesse richieste rigiocate con il
codice nuovo e con `_riordina_per_vicinanza` sostituita dall'identita'). Controllo: con il
riordino disattivato i 52 `atteso` delle composizioni sono riprodotti ESATTAMENTE dal golden
precedente (0 differenze). Ogni differenza dei 39 casi cambiati e' solo ordine delle tappe e
conseguenti arrivi: stesso insieme di tappe, stessa prima tappa, stessa durata e stesso
`reason` di ogni tappa, stesso budget e stesse tappe escluse. Zero differenze non attribuite.
I metri a piedi non aumentano mai (52 casi su 52); `test_riordino_vicinanza_golden.py` lo
asserisce ricalcolandolo dal codice.
  I 3 `demo|...|pioggia-15` sono stati RIGENERATI ANCHE NELLA RICHIESTA, con lo stesso
procedimento della DECIMA e della DODICESIMA: itinerario composto alle 15:00 di sabato
12/12/2026 con meteo sereno via `POST /itinerary` (profilo e `person_id` del caso, stessa
richiesta di composizione dei `sereno-10` salvo l'ora), poi adattato alle 15:00 con meteo
pioggia, profilo nell'AdaptRequest. L'itinerario congelato nella richiesta era composto con
l'ordine di prima: con il riordino cambiano la composizione e quindi l'adattamento.
Controllo (eseguito): composto con il riordino disattivato, l'itinerario riproduce
ESATTAMENTE le tappe, gli arrivi e i `reason` della richiesta congelata precedente (3 casi su
3); la richiesta precedente, rigiocata col codice nuovo, da' l'`atteso` precedente.

AGGIUNTI (2026-10-19, ondata 1): 4 casi `adapt-profilo|...` (tipo `adapt`), la cui
richiesta porta `profile` nell'AdaptRequest (difetto j); i 74 casi esistenti sono
byte-identici. Profili da `rag.onboarding.profile_from_answers` con le risposte esatte
dell'app. Itinerari composti dal codice attuale (con budget). Scopo:
  - `con-bambini|mura-affollate`: famiglia con bambini, affollamento 0.9 a `mura-urbane`:
    `exp-bici-mura` e' sostituita da un'esperienza gratuita con temi in comune (difetto g);
  - `pioggia|tappa-gratuita`: pioggia su tappe all'aperto gratuite: ogni sostituto e' gratuito (g);
  - `accessibile|pioggia`: accessibilita' richiesta nel profilo: ogni sostituto e' accessibile (j);
  - `no-bambini|pioggia`: "No, non sono con bambini": nessun `reason` cita i bambini (j).
La proprieta' di ciascuno e' asserita da `test_golden_adapt_profilo_proprieta`.

Due livelli, entrambi "replay" dei JSON (richiesta/specifica + atteso):
  a) ITINERARI via HTTP del BFF (`POST /itinerary`, `POST /itinerary/adapt`):
     uguaglianza ESATTA di `person_id`, `adattato_da_segnale`,
     `tempo_disponibile_min`, `tempo_effettivo_min`, per ogni tappa
     `experience_id`, `arrivo`, `durata_min`, `reason`, `esito_adattamento`
     (ordine incluso) e di `tappe_escluse` (`experience_id`, `esito`, `reason`,
     in ordine). `generated_at` escluso. Ambiente isolato: seed di Lucca, repository
     in-memory (recommender a freddo), nessuna credenziale, `adesso` fisso.
  b) PUNTEGGI: `rules.calcola_score` e la `score_fn` di
     `recommender.costruisci_score_fn` (repository vuoto = freddo; repository
     con eventi sintetici fissi = caldo), tolleranza ASSOLUTA 1e-9.

MANUTENZIONE: le firme cambieranno (parametro `vocabolario` keyword-only). Tutte
le chiamate a `calcola_score`, `costruisci_score_fn` e `SeedCandidateSource` sono
negli helper `_h_*` qui sotto: si adattano QUELLI, mai i JSON.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi.testclient", reason="fastapi non installato")
api_main = pytest.importorskip("api.main", reason="`api` non installabile")
contracts = pytest.importorskip("contracts", reason="`contracts` non installabile")
from experience_engine import rules  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from graph.seed_lucca import VOCABOLARIO  # noqa: E402
from graph.source import SeedCandidateSource  # noqa: E402
from recommender import (  # noqa: E402
    BehaviorEventRepository,
    InMemoryBehaviorEventRepository,
    costruisci_score_fn,
)
from urban_memory import (  # noqa: E402
    InMemorySegnaleFluttuanteRepository,
    InMemoryTracciaRepository,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
FILE_ITINERARI = GOLDEN_DIR / "lucca_itinerari.json"
FILE_PUNTEGGI = GOLDEN_DIR / "lucca_punteggi.json"

ADESSO_FISSO = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
TOLLERANZA_ASSOLUTA = 1e-9
ESPERIENZE_LUCCA = 35


# ---------------------------------------------------------------------------
# Helper dipendenti dalle FIRME (unico punto da adattare nei refactor)
# ---------------------------------------------------------------------------


def _h_fonte_candidati() -> Any:
    """La fonte dei candidati di Lucca (seed versionato, nessun Neo4j)."""
    return SeedCandidateSource()


def _h_candidati_lucca() -> list[Any]:
    """I 35 candidati di Lucca, con un contesto neutro (nessun luogo visto)."""
    ctx = contracts.VisitorContext(
        person_id="golden-candidati",
        profile=contracts.EmotionalProfile(
            curiosita=0.5, contemplazione=0.5, arte=0.5,
            con_bambini=False, tempo_disponibile_min=100000,
        ),
        signal=contracts.Signal(
            meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        ),
    )
    return list(_h_fonte_candidati().candidates(ctx))


def _h_calcola_score(candidato: Any, profilo: Any, segnale: Any) -> float:
    return float(rules.calcola_score(candidato, profilo, segnale, vocabolario=VOCABOLARIO))


def _h_score_fn(repo: BehaviorEventRepository, candidati: list[Any]) -> Any:
    return costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)


# ---------------------------------------------------------------------------
# Caricamento golden (mai rigenerato: se manca, FALLISCE)
# ---------------------------------------------------------------------------


def _carica(path: Path) -> dict[str, Any]:
    if not path.is_file():
        pytest.fail(
            f"golden mancante: {path}. I golden sono congelati e NON si rigenerano "
            "automaticamente: ripristinare il file dal repository."
        )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _id_casi() -> list[str]:
    if not FILE_ITINERARI.is_file():
        return ["__golden_mancante__"]
    return sorted(json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"])


# ---------------------------------------------------------------------------
# Livello a) itinerari via HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """BFF isolato: nessuna credenziale, nessuna cache, nessun orologio reale.

    I selettori sono sostituiti in `api.main` (come fanno gli altri test del
    BFF): `.env` e `lru_cache` di `api.deps` non hanno alcun effetto. Repository
    freschi per test: nessuno stato condiviso, recommender a freddo."""
    fonte = _h_fonte_candidati()
    eventi = InMemoryBehaviorEventRepository()
    segnali = InMemorySegnaleFluttuanteRepository()
    tracce = InMemoryTracciaRepository()
    monkeypatch.setattr(api_main, "get_candidate_source", lambda: fonte)
    monkeypatch.setattr(api_main, "get_event_repository", lambda: eventi)
    monkeypatch.setattr(api_main, "get_segnale_repository", lambda: segnali)
    monkeypatch.setattr(api_main, "get_traccia_repository", lambda: tracce)
    monkeypatch.setattr(api_main, "get_place_link_writer", lambda: None)
    monkeypatch.setattr(api_main, "get_evento_reader", lambda: None)
    monkeypatch.setattr(api_main, "get_adesso", lambda: ADESSO_FISSO)
    return TestClient(api_main.app)


def _riduci(itinerario: dict[str, Any]) -> dict[str, Any]:
    """Solo i campi congelati; `generated_at` escluso."""
    return {
        "person_id": itinerario["person_id"],
        "adattato_da_segnale": itinerario["adattato_da_segnale"],
        "tempo_disponibile_min": itinerario["tempo_disponibile_min"],
        "tempo_effettivo_min": itinerario["tempo_effettivo_min"],
        "stops": [
            {
                k: s[k]
                for k in ("experience_id", "arrivo", "durata_min", "reason", "esito_adattamento")
            }
            for s in itinerario["stops"]
        ],
        "tappe_escluse": [
            {k: t[k] for k in ("experience_id", "esito", "reason")}
            for t in itinerario["tappe_escluse"]
        ],
    }


def _minuti_del_giorno(orario: str) -> int:
    ore, minuti, _secondi = orario.split(":")
    return int(ore) * 60 + int(minuti)


def _minuti_itinerario(stops: list[dict[str, Any]]) -> int:
    """Minuti dell'itinerario = somma di durate e trasferimenti, calcolata
    dagli orari SENZA riavvolgimento: ultimo arrivo + ultima durata - primo
    arrivo, con gli orari come minuti dall'inizio della giornata. Poiche' gli
    arrivi avanzano esattamente della somma di durate e trasferimenti, e'
    lo stesso numero che il motore conteggia contro il budget. L'asserzione
    `ultimo >= primo` fallisce se un orario si e' riavvolto oltre la
    mezzanotte (il tetto della giornata lo vieta). Nessuna tappa: 0."""
    if not stops:
        return 0
    primo = _minuti_del_giorno(stops[0]["arrivo"])
    ultimo = _minuti_del_giorno(stops[-1]["arrivo"])
    assert ultimo >= primo, "orari riavvolti oltre la mezzanotte"
    return ultimo - primo + int(stops[-1]["durata_min"])


def test_golden_itinerari_presente_e_non_vuoto() -> None:
    casi = _carica(FILE_ITINERARI)["casi"]
    tipi = {c["tipo"] for c in casi.values()}
    assert tipi == {"compose", "adapt"}
    assert sum(1 for c in casi.values() if c["tipo"] == "compose") >= 40
    assert sum(1 for c in casi.values() if c["tipo"] == "adapt") >= 12
    # Wave "adattamento": 16 casi di retrocompatibilita' (itinerario SENZA
    # budget) + 16 casi che esercitano il budget (itinerario COL budget).
    retro = {k: c for k, c in casi.items() if k.startswith("adapt|")}
    budget = {k: c for k, c in casi.items() if k.startswith("adapt-budget|")}
    assert len(retro) == 16
    assert len(budget) == 16
    assert {k.split("|", 1)[1] for k in retro} == {k.split("|", 1)[1] for k in budget}
    assert all(c["tipo"] == "adapt" for c in [*retro.values(), *budget.values()])
    assert all(
        c["richiesta"]["itinerary"].get("tempo_disponibile_min") is None for c in retro.values()
    )
    assert all(
        c["richiesta"]["itinerary"].get("tempo_effettivo_min") is not None
        for c in budget.values()
    )
    # Ondata 1 (difetto j): 4 casi con il profilo nella richiesta di adattamento.
    profilo = {k: c for k, c in casi.items() if k.startswith("adapt-profilo|")}
    assert len(profilo) == 4
    assert all(c["tipo"] == "adapt" for c in profilo.values())
    assert all(c["richiesta"].get("profile") for c in profilo.values())


@pytest.mark.parametrize("chiave", _id_casi())
def test_golden_itinerario(client: TestClient, chiave: str) -> None:
    caso = _carica(FILE_ITINERARI)["casi"][chiave]
    percorso = "/itinerary" if caso["tipo"] == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=caso["richiesta"])
    assert resp.status_code == 200, resp.text
    risposta = resp.json()
    assert _riduci(risposta) == caso["atteso"], f"REGRESSIONE su Lucca: {chiave}"
    # Tetto della giornata: nessun itinerario finisce oltre le 24:00 (anche senza budget).
    if risposta["stops"]:
        ultima = risposta["stops"][-1]
        assert _minuti_del_giorno(ultima["arrivo"]) + ultima["durata_min"] <= 24 * 60, chiave
    # Il budget effettivo non si supera mai (composizione e adattamento).
    if risposta["tempo_effettivo_min"] is not None:
        minuti = _minuti_itinerario(risposta["stops"])
        assert minuti <= risposta["tempo_effettivo_min"], (
            f"{chiave}: {minuti} minuti oltre tempo_effettivo_min="
            f"{risposta['tempo_effettivo_min']}"
        )


def _esperienze_seed() -> dict[str, Any]:
    from graph.seed_lucca import ESPERIENZE

    return {e.id: e for e in ESPERIENZE}


def _sostituti_con_tema_ammissibili(
    caso: dict[str, Any], tolta: str, arrivo: str, seed: dict[str, Any]
) -> list[str]:
    """Esperienze gratuite che condividono un tema con `tolta` e passano i vincoli
    duri nel contesto della richiesta (non gia' in itinerario, luogo non occupato da
    un'altra tappa, non sospese, accessibili se richiesto, luogo sotto la soglia di
    adattamento 0.7, aperte per [arrivo, arrivo + durata] nel giorno della richiesta)."""
    richiesta = caso["richiesta"]
    originali = [s["experience_id"] for s in richiesta["itinerary"]["stops"]]
    occupati = {seed[i].place_id for i in originali if i != tolta}
    giorno = _giorno_della_richiesta(caso)
    accessibile = bool(richiesta["profile"].get("accessibilita_richiesta"))
    out: list[str] = []
    for e in seed.values():
        if not set(e.temi) & set(seed[tolta].temi) or e.id in originali or e.prezzo_eur:
            continue
        if e.sospesa or e.place_id in occupati or (accessibile and not e.accessibile):
            continue
        if richiesta["signal"]["affollamento"].get(e.place_id, 0.0) > 0.7:
            continue
        if _violazioni_orari([_tappa(e.id, arrivo, e.durata_min)], giorno, seed):
            continue
        out.append(e.id)
    return out


def test_golden_adapt_profilo_proprieta() -> None:
    """Sul golden (senza rieseguire il motore), la proprieta' dichiarata di ogni caso
    `adapt-profilo|...`, con prezzo/accessibile/temi dal seed di Lucca."""
    casi = _carica(FILE_ITINERARI)["casi"]
    seed = _esperienze_seed()

    def sostituzioni(chiave: str) -> list[tuple[str, str]]:
        caso = casi[chiave]
        # Le tappe tolte (chiuse all'arrivo ricalcolato, `tappe_escluse`) non hanno
        # una tappa corrispondente: l'allineamento e' sulle tappe RIMASTE.
        escluse = {t["experience_id"] for t in caso["atteso"]["tappe_escluse"]}
        originali = [
            s["experience_id"]
            for s in caso["richiesta"]["itinerary"]["stops"]
            if s["experience_id"] not in escluse
        ]
        stops = caso["atteso"]["stops"]
        assert len(stops) == len(originali), chiave
        coppie = [
            (o, s["experience_id"])
            for o, s in zip(originali, stops, strict=True)
            if s["esito_adattamento"] == "sostituita"
        ]
        assert coppie, f"{chiave}: nessuna tappa sostituita"
        assert all(a != b for a, b in coppie), chiave
        return coppie

    def gratuito(exp_id: str) -> bool:
        return not seed[exp_id].prezzo_eur

    # 1) bici delle Mura sostituita da un'esperienza gratuita con un tema in comune.
    k1 = "adapt-profilo|con-bambini|mura-affollate"
    assert casi[k1]["richiesta"]["profile"]["con_bambini"] is True
    ids1 = [s["experience_id"] for s in casi[k1]["richiesta"]["itinerary"]["stops"]]
    assert "exp-bici-mura" in ids1
    coppie1 = sostituzioni(k1)
    assert [o for o, _ in coppie1] == ["exp-bici-mura"]
    for tolta, nuova in coppie1:
        assert gratuito(nuova), (k1, nuova)
        if not set(seed[tolta].temi) & set(seed[nuova].temi):
            # Il tema in comune e' una preferenza, non un filtro: un sostituto senza
            # temi in comune e' corretto solo se nessun'esperienza con temi in comune
            # era ammissibile (gratuita, aperta all'arrivo, luogo libero e non affollato).
            arrivo = next(
                s["arrivo"] for s in casi[k1]["atteso"]["stops"] if s["experience_id"] == nuova
            )
            assert not _sostituti_con_tema_ammissibili(casi[k1], tolta, arrivo, seed), (
                k1, tolta, nuova,
            )

    # 2) pioggia su tappe all'aperto: nessun sostituto costa piu' della tappa tolta (una
    # tappa gratuita ha per sostituto una gratuita). Con i prezzi del commit B l'orto
    # botanico per famiglie costa 6 EUR: la richiesta congelata non contiene piu' solo
    # tappe gratuite, quindi la regola e' asserita nella forma generale (tolta gratuita
    # => sostituto gratuito resta un caso particolare).
    k2 = "adapt-profilo|pioggia|tappa-gratuita"
    assert casi[k2]["richiesta"]["signal"]["meteo"] == "pioggia"
    coppie2 = sostituzioni(k2)
    for tolta, nuova in coppie2:
        assert not seed[tolta].al_chiuso, (k2, tolta)
        assert _prezzo(seed[nuova]) <= _prezzo(seed[tolta]), (k2, tolta, nuova)
        if gratuito(tolta):
            assert gratuito(nuova), (k2, nuova)

    # 3) accessibilita' richiesta: ogni sostituto e' accessibile.
    k3 = "adapt-profilo|accessibile|pioggia"
    assert casi[k3]["richiesta"]["profile"]["accessibilita_richiesta"] is True
    for _tolta, nuova in sostituzioni(k3):
        assert seed[nuova].accessibile is True, (k3, nuova)

    # 4) senza bambini: nessun reason di tappa li cita.
    k4 = "adapt-profilo|no-bambini|pioggia"
    assert casi[k4]["richiesta"]["profile"]["con_bambini"] is False
    sostituzioni(k4)
    for s in casi[k4]["atteso"]["stops"]:
        assert "bambini" not in s["reason"].lower(), (k4, s["experience_id"], s["reason"])


# ---------------------------------------------------------------------------
# Proprieta' su TUTTI i casi (vecchi e nuovi), calcolate sull'ESITO REALE
# (la risposta del BFF a cui si rigioca la richiesta), non sul JSON atteso.
# ---------------------------------------------------------------------------


def _risposta(client: TestClient, caso: dict[str, Any]) -> dict[str, Any]:
    percorso = "/itinerary" if caso["tipo"] == "compose" else "/itinerary/adapt"
    resp = client.post(percorso, json=caso["richiesta"])
    assert resp.status_code == 200, resp.text
    risposta: dict[str, Any] = resp.json()
    return risposta


def _giorno_della_richiesta(caso: dict[str, Any]) -> int:
    """Giorno della settimana (0 = lunedi') del `Signal.data` della richiesta."""
    return date.fromisoformat(caso["richiesta"]["signal"]["data"]).weekday()


def _violazioni_orari(
    stops: list[dict[str, Any]], giorno: int, seed: dict[str, Any]
) -> list[str]:
    """Tappe il cui intervallo [arrivo, arrivo + durata] non cade in UNA fascia
    di `orari_apertura` del giorno. Stessa semantica di `rules.aperta_durante`
    (e di `contracts.rientra_in_orario`): `apertura <= arrivo` e
    `arrivo + durata <= chiusura`, in minuti dalla mezzanotte; nessuna fascia
    dichiarata per l'esperienza = nessun vincolo."""
    errori: list[str] = []
    for s in stops:
        esperienza = seed[s["experience_id"]]
        if not esperienza.orari_apertura:
            continue
        inizio = _minuti_del_giorno(s["arrivo"])
        fine = inizio + int(s["durata_min"])
        if not any(
            f.giorno_settimana == giorno
            and f.apertura.hour * 60 + f.apertura.minute <= inizio
            and fine <= f.chiusura.hour * 60 + f.chiusura.minute
            for f in esperienza.orari_apertura
        ):
            errori.append(f"{s['experience_id']} arrivo {s['arrivo']} durata {s['durata_min']}")
    return errori


def _violazioni_sospese(stops: list[dict[str, Any]], seed: dict[str, Any]) -> list[str]:
    return [s["experience_id"] for s in stops if seed[s["experience_id"]].sospesa]


def _prezzo(esperienza: Any) -> float:
    return float(esperienza.prezzo_eur or 0.0)


def _violazioni_prezzo_pioggia(
    caso: dict[str, Any], risposta: dict[str, Any], seed: dict[str, Any]
) -> list[str]:
    """Sostituti piu' cari della tappa tolta. Allineamento posizionale: le tappe
    originali non finite in `tappe_escluse` corrispondono, nell'ordine, alle
    tappe della risposta (una sostituzione tiene la posizione)."""
    escluse = {t["experience_id"] for t in risposta["tappe_escluse"]}
    originali = [
        s["experience_id"]
        for s in caso["richiesta"]["itinerary"]["stops"]
        if s["experience_id"] not in escluse
    ]
    nuove = risposta["stops"]
    assert len(originali) == len(nuove), "tappe originali e adattate non allineabili"
    errori: list[str] = []
    for tolta, s in zip(originali, nuove, strict=True):
        if s["esito_adattamento"] != "sostituita":
            continue
        if _prezzo(seed[s["experience_id"]]) > _prezzo(seed[tolta]):
            errori.append(f"{tolta} ({_prezzo(seed[tolta])}) -> {s['experience_id']}")
    return errori


def _casi_pioggia_adapt() -> list[str]:
    if not FILE_ITINERARI.is_file():
        return ["__golden_mancante__"]
    casi = json.loads(FILE_ITINERARI.read_text(encoding="utf-8"))["casi"]
    return sorted(
        k for k, c in casi.items()
        if c["tipo"] == "adapt" and c["richiesta"]["signal"]["meteo"] == "pioggia"
    )


@pytest.mark.parametrize("chiave", _id_casi())
def test_golden_orari_rispettati(client: TestClient, chiave: str) -> None:
    """(a) Nessuna tappa arriva fuori dalle fasce di apertura del giorno della richiesta."""
    caso = _carica(FILE_ITINERARI)["casi"][chiave]
    risposta = _risposta(client, caso)
    errori = _violazioni_orari(risposta["stops"], _giorno_della_richiesta(caso), _esperienze_seed())
    assert not errori, f"{chiave}: tappe fuori orario: {errori}"


@pytest.mark.parametrize("chiave", _id_casi())
def test_golden_nessuna_sospesa(client: TestClient, chiave: str) -> None:
    """(b) Nessuna esperienza `sospesa=True` tra le tappe."""
    caso = _carica(FILE_ITINERARI)["casi"][chiave]
    risposta = _risposta(client, caso)
    assert not _violazioni_sospese(risposta["stops"], _esperienze_seed()), chiave


@pytest.mark.parametrize("chiave", _casi_pioggia_adapt())
def test_golden_pioggia_sostituti_non_piu_cari(client: TestClient, chiave: str) -> None:
    """(c) In ogni adattamento per pioggia del golden, nessun sostituto costa piu' della
    tappa tolta (`prezzo_eur` None = 0). Gli altri casi non hanno sostituzioni per pioggia."""
    caso = _carica(FILE_ITINERARI)["casi"][chiave]
    assert caso["tipo"] == "adapt" and caso["richiesta"]["signal"]["meteo"] == "pioggia"
    risposta = _risposta(client, caso)
    errori = _violazioni_prezzo_pioggia(caso, risposta, _esperienze_seed())
    assert not errori, f"{chiave}: sostituti piu' cari: {errori}"


def test_golden_proprieta_non_vuote(client: TestClient) -> None:
    """Le tre proprieta' sono ESERCITATE dal golden (nessuna asserzione vuota):
    ci sono tappe con orari dichiarati, la Torre delle Ore e' sospesa nel seed e
    candidata, e almeno una sostituzione per pioggia viene valutata."""
    casi = _carica(FILE_ITINERARI)["casi"]
    seed = _esperienze_seed()
    assert seed["exp-meccanismo-torre-ore"].sospesa is True
    assert "exp-meccanismo-torre-ore" in {c.experience.id for c in _h_candidati_lucca()}
    con_orari = 0
    for caso in casi.values():
        con_orari += sum(
            1 for s in _risposta(client, caso)["stops"] if seed[s["experience_id"]].orari_apertura
        )
    assert con_orari >= 50, con_orari
    sostituzioni = 0
    for chiave in _casi_pioggia_adapt():
        risposta = _risposta(client, casi[chiave])
        sostituzioni += sum(1 for s in risposta["stops"] if s["esito_adattamento"] == "sostituita")
    assert sostituzioni >= 5, sostituzioni


def _tappa(
    experience_id: str, arrivo: str, durata: int, esito: str | None = None
) -> dict[str, Any]:
    return {
        "experience_id": experience_id, "arrivo": arrivo, "durata_min": durata,
        "esito_adattamento": esito,
    }


def test_le_guardie_delle_proprieta_scattano() -> None:
    """Le tre funzioni di verifica FALLISCONO se la proprieta' e' rotta (doppio
    negativo: l'asserzione non e' vuota)."""
    seed = _esperienze_seed()
    # (a) sabato 12/12/2026 (giorno 5): il Duomo apre 10:00, Casa Puccini chiude alle 17:00;
    # il mercoledi' (giorno 2) l'Orto botanico e' chiuso.
    assert not _violazioni_orari([_tappa("exp-duomo-volto-santo", "10:00:00", 35)], 5, seed)
    assert _violazioni_orari([_tappa("exp-duomo-volto-santo", "09:30:00", 35)], 5, seed)
    assert _violazioni_orari([_tappa("exp-casa-puccini-visita", "16:30:00", 60)], 5, seed)
    assert _violazioni_orari([_tappa("exp-orto-botanico-silenzio", "12:00:00", 60)], 2, seed)
    # (b)
    assert _violazioni_sospese([_tappa("exp-meccanismo-torre-ore", "10:00:00", 35)], seed) == [
        "exp-meccanismo-torre-ore"
    ]
    assert not _violazioni_sospese([_tappa("exp-duomo-volto-santo", "10:00:00", 35)], seed)
    # (c) tolta gratuita (bici delle Mura) -> sostituto a pagamento (Casa Puccini, 9 EUR)
    caso = {"richiesta": {"itinerary": {"stops": [{"experience_id": "exp-bici-mura"}]}}}
    rotta = {
        "stops": [_tappa("exp-casa-puccini-visita", "10:00:00", 60, "sostituita")],
        "tappe_escluse": [],
    }
    assert _violazioni_prezzo_pioggia(caso, rotta, seed)
    ok = {
        "stops": [_tappa("exp-duomo-volto-santo", "10:00:00", 35, "sostituita")],
        "tappe_escluse": [],
    }
    assert not _violazioni_prezzo_pioggia(caso, ok, seed)


# ---------------------------------------------------------------------------
# Livello b) punteggi
# ---------------------------------------------------------------------------


def _chiave(experience_id: str, profilo: str, segnale: str) -> str:
    return f"{experience_id}|{profilo}|{segnale}"


def _confronta(attesi: dict[str, float], ottenuti: dict[str, float]) -> list[str]:
    errori: list[str] = []
    if set(attesi) != set(ottenuti):
        errori.append(f"insieme di chiavi diverso: {sorted(set(attesi) ^ set(ottenuti))[:5]}")
    for k, atteso in attesi.items():
        if k in ottenuti and not math.isclose(
            atteso, ottenuti[k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA
        ):
            errori.append(f"{k}: atteso {atteso!r}, ottenuto {ottenuti[k]!r}")
    return errori


def _calcola_tutto(spec: dict[str, Any]) -> dict[str, dict[str, float]]:
    profili = {k: contracts.EmotionalProfile.model_validate(v) for k, v in spec["profili"].items()}
    segnali = {k: contracts.Signal.model_validate(v) for k, v in spec["segnali"].items()}
    candidati = _h_candidati_lucca()

    caldo = InMemoryBehaviorEventRepository()
    for e in spec["eventi"]:
        caldo.record(contracts.BehaviorEvent.model_validate(e))
    fn_fredda = _h_score_fn(InMemoryBehaviorEventRepository(), candidati)
    fn_calda = _h_score_fn(caldo, candidati)

    out: dict[str, dict[str, float]] = {
        "calcola_score": {}, "score_fn_fredda": {}, "score_fn_calda": {},
    }
    for c in candidati:
        for np_, p in profili.items():
            for ns, s in segnali.items():
                k = _chiave(c.experience.id, np_, ns)
                out["calcola_score"][k] = _h_calcola_score(c, p, s)
                out["score_fn_fredda"][k] = float(fn_fredda(c, p, s))
                out["score_fn_calda"][k] = float(fn_calda(c, p, s))
    return out


def test_golden_punteggi_copre_tutte_le_esperienze() -> None:
    spec = _carica(FILE_PUNTEGGI)
    ids = {k.split("|")[0] for k in spec["punteggi"]["calcola_score"]}
    assert len(ids) == ESPERIENZE_LUCCA
    assert ids == {c.experience.id for c in _h_candidati_lucca()}


@pytest.mark.parametrize("funzione", ["calcola_score", "score_fn_fredda", "score_fn_calda"])
def test_golden_punteggi(funzione: str) -> None:
    spec = _carica(FILE_PUNTEGGI)
    errori = _confronta(spec["punteggi"][funzione], _calcola_tutto(spec)[funzione])
    assert not errori, f"REGRESSIONE su Lucca ({funzione}): {len(errori)} diff, es. {errori[:5]}"


def test_golden_score_fn_calda_esercita_il_termine_storico() -> None:
    """Il golden 'caldo' ha senso solo se lo storico cambia davvero i punteggi:
    sia nel file congelato sia ricalcolato ora."""
    spec = _carica(FILE_PUNTEGGI)
    p = spec["punteggi"]
    differenti = [
        k for k in p["score_fn_fredda"]
        if not math.isclose(
            p["score_fn_fredda"][k], p["score_fn_calda"][k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA
        )
    ]
    assert differenti, "la score_fn calda coincide con la fredda: storico non esercitato"
    # La fredda e' bit-identica a calcola_score solo se ENTRAMBE le quote sono spente.
    for k, v in p["calcola_score"].items():
        assert math.isclose(v, p["score_fn_fredda"][k], rel_tol=0, abs_tol=TOLLERANZA_ASSOLUTA)
