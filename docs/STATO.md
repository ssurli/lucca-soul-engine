# Stato del progetto — 2026-10-22

`main`: ondata 1c inclusa (merge fast-forward di `feat/ondata1c-contenuti`, correzione `e36dfec`; CI verde).
Ondata 2a inclusa (merge fast-forward di `feat/ondata2a-testi`, `d9f6664`; CI verde).
Ondata 2b inclusa (merge fast-forward di `feat/ondata2b-app`, `9be2259`; CI verde).
Ondata 3 inclusa (merge fast-forward di `feat/ondata3-dati`, `b7f2f6f`; CI verde).
I dettagli sono in `docs/LIMITI.md` e `docs/BUILD_PLAN.md`; questo file è solo il punto della
situazione.

## Ondate chiuse

- **1** (19/10): difetti della prima prova manuale: onboarding sì/no e durata, profilo
  nell'adattamento, sostituto mai più caro della tappa tolta, mosaico e Torre delle Ore al chiuso o
  all'aperto corretti.
- **1b-1** (19/10): orari verificati all'arrivo di ogni tappa, in composizione e in adattamento
  (`tagliata_orario`), fuso della città, orari letti dal grafo.
- **1b-2** (20/10): esperienza sospesa (Torre delle Ore), una tappa per luogo, correzione
  provvisoria del recommender (Cand. 1), orari e prezzi invernali reali, 2 luoghi e 4 esperienze
  nuove, golden con 13 casi demo e feriali.
- **1c** (20/10): 4 luoghi e 6 esperienze nuove (21 luoghi, 32 esperienze), orari dimostrativi
  delle botteghe, script dei 4 ricordi dimostrativi.
- **21/10, committente**: seed ricaricato su Aura, ricordi dimostrativi eseguiti (4, agganciati,
  2 persone distinte), prova "Piove" eseguita.
- **2a** (21/10): scarto esplicito dei contributi non curati (mai DELETE), nessuna frase
  sull'affollamento senza un valore misurato, titoli leggibili in app, motivi riscritti da campi
  separati dalle connessioni (racconti con fonte, temi come etichette, articoli dei luoghi, profilo
  solo sulla prima tappa), curiosità dei luoghi (mai nel punteggio), golden alla DECIMA modifica.

- **22/10, committente**: passi della 2a eseguiti: migrazione Neon, scarto del contributo di
  prova, ricarica del seed su Aura, prova manuale dell'app.
- **2b** (22/10, app): interruttori dei segnali (segnale combinato dall'itinerario originale,
  "Annulla", "Torna al percorso iniziale"), badge "Cambiata" solo sulle tappe sostituite,
  domanda su Firenze nascosta, frase del profilo solo per tratti netti (>= 0,7 o <= 0,2) e sulla
  prima tappa sostituita, golden alla UNDICESIMA modifica (solo testi, tappe invariate).
  Non fatti in 2b: fonte delle curiosità solo se pubblica (rimandata all'ondata dati, cambia il
  contratto) e badge "dimostrativo" per ricordi e botteghe fittizie (da ripianificare).

- **3** (22/10, dati): taglio per stanchezza al prefisso più vicino ai 2/3; messaggio "nessun
  effetto" rispetto al risultato precedente; contratto aperto (`Punto`, `punti_arrivo`,
  `punto_arrivo`, `fonte_pubblica`, `fonte_orari`); coordinate dei luoghi e punti di arrivo
  (Mura, tramonto, Pfanner dalle Mura) rilevati dal committente; trasferimento reale tra tappe
  consecutive (linea d'aria × 1,3); link "Come arrivo qui" a piedi (nessuno sulle botteghe);
  fonte delle curiosità mostrata solo se pubblica; fonte degli orari per esperienza; 3 luoghi ed
  esperienze nuove (Palazzo Bernardini, San Pietro Somaldi, parco giochi di Porta San Donato) con
  6 archi VICINO, curiosità del ginkgo sull'Orto; casi `demo|` dalle risposte reali dell'app
  (180 minuti; poco-tempo "Circa un'ora"); golden alla DODICESIMA modifica (cambiano le tappe).

## Da fare (committente), dopo il merge della 3

1. Ricarica del seed su Aura: `.venv\Scripts\python.exe -m graph.loader`.
2. Riavvio del BFF (i `.cypher` sono letti una volta).
3. Prova in app: profilo curioso, mezza giornata, Piove più Sono stanco/a: attese 3 tappe, non 2;
   il link "Come arrivo qui" porta all'ingresso giusto.

## Prossima ondata: grafica (direzione C)

1. **App servita dal BFF sulla stessa origine** (niente CORS): oggi l'app funziona solo in un
   Chrome con `--disable-web-security`.
2. Direzione "C" (canvas "Lucca Soul — direzioni grafiche": caratteri del deck, accento mattone,
   mappa in alto, interruttori dei segnali con "Annulla"), logo delle Mura nella testata, icona e
   favicon dell'app (oggi quelle di Flutter). Miniature solo con foto di licenza nota (proprie o
   Wikimedia Commons con credito).
3. Badge "dimostrativo" per ricordi e botteghe fittizie (rimasto dalla 2b, da ripianificare).

Poi **blocco del codice verso il 5/12**, prove con l'orologio fissato a sabato 12/12 (10:00 e
15:00) e Aura verificata RUNNING il giorno prima.

## Dopo la demo

- **Modello del tempo**: orari con periodo di validità (stagioni), chiusure e aperture per data,
  tramonto calcolato dalle coordinate, stato dell'itinerario (tappe fatte / in corso / da fare);
  `sospesa` sostituito da un periodo di chiusura. Orari estivi (per esempio la mostra di Santa
  Croce, 10:00–18:30) ed eccezioni datate (Lucca Comics, Summer Festival, chiusure festive). Poi un
  **controllo periodico degli orari** come attività programmata: confronta le pagine ufficiali con
  il seed e produce solo un elenco di differenze da confermare; non scrive mai nel seed.
- **Recommender**: riprogettazione dell'effetto gregge con un criterio di uscita misurabile.
- **Ricordi**: campo `dimostrativo` escluso da ogni aggregazione dell'Index, con la stessa
  esclusione dello scarto (`scartato_il`).
- **Sorpresa nel punteggio**: oggi conta le frasi di connessione, non i legami del grafo; da
  ricalcolare sugli archi.
- **Pioggia**: valutare di togliere, invece di mantenere, una tappa all'aperto senza alternativa.
- **Contenuti rinviati**: Museo della Zecca, Cammino di San Josemaría (descritto in modo neutro),
  Domus Romana, Palazzo Mansi; botteghe reali solo come aderenti, con il loro consenso.
- **Luoghi del territorio e degli eventi** (coordinate già fornite dal committente il 22/10, da
  ricevere a parte): Palazzo Ducale, Ex Cavallerizza, Conservatorio Boccherini, San Romano, le
  piazze San Francesco, San Frediano e Antelminelli, Villa Bottini, Giardino degli Osservanti,
  Biblioteca Agorà, Biblioteca civica, Museo della Cattedrale, Santa Maria Foris Portam (Colonna
  Mozza), Fontana della Pupporona, via del Bastardo, Chiesa di Santa Caterina (detta "delle
  Sigaraie", davanti all'ex Manifattura Tabacchi: sconsacrata, apre solo per mostre, quindi luogo
  di eventi e non esperienza). San Ponziano: visitabile solo su richiesta. Zecca e Palazzo Mansi:
  rinviati. Esclusi per regola: esercizi commerciali reali (antiquari, ostello, locali), la Casa
  Circondariale.
- **Curiosità "lungo la strada" con un punto proprio**: oggi una curiosità è del luogo; per
  esempio il ginkgo di via Elisa (43.84281287071769, 10.51120294952295) è registrato come curiosità
  dell'Orto botanico.

## Voci aperte principali di `docs/LIMITI.md`

- **Recommender: correzione provvisoria dell'effetto gregge (Cand. 1)**, da riprogettare dopo la
  demo; manca un criterio di uscita misurabile. Con i dati della 1c: 40/40 storici con B ≥ A.
- **Pioggia: obiettivo raggiunto in 1 caso demo su 3** (curioso). Con-bambini e contemplativo
  mantengono una tappa all'aperto verso le 18, quando i sostituti gratuiti al chiuso sono chiusi.
- **Accessibilità non verificate**: la sortita di San Paolino è `accessibile=True` per dato del
  committente, non verificato; i luoghi nuovi non verificati sono `False`. Con la pioggia il
  sabato alle 15 i sostituti gratuiti, al chiuso e accessibili sono 2 (Duomo, sortita).
- **Ricordi dimostrativi**: contano nell'Index nel mese del caricamento; serve il campo
  `dimostrativo` prima che le persone reali arrivino a 8.
- **Orari**: solo invernali e settimanali; botteghe con orari fittizi; `sospesa` della Torre delle
  Ore da riportare a `False` a marzo.
