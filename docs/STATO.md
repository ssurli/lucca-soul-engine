# Stato del progetto — 2026-10-20

`main`: ondata 1c inclusa (merge fast-forward di `feat/ondata1c-contenuti`, correzione `e36dfec`; CI verde).
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
  delle botteghe, script dei 4 ricordi dimostrativi (non ancora eseguito).

## Da fare (committente), in quest'ordine

Comandi PowerShell completi nel report della 1c; tutti dalla radice del repo, su `main`.

1. Ricarica del seed su Aura: `.venv\Scripts\python.exe -m graph.loader`.
2. Controllo su Aura: 32 esperienze, 1 sospesa (`exp-meccanismo-torre-ore`), 21 luoghi.
3. Prova a secco dei ricordi: `.venv\Scripts\python.exe scripts\carica_ricordi_demo.py`
   (legge soltanto; si ferma se le persone distinte sarebbero 7 o più, o se un luogo manca su Aura).
4. Scrittura dei ricordi: stesso comando con `--esegui`; se l'aggancio al grafo non riesce, rilanciarlo.
5. Riavvio del BFF e prova "Piove" con il profilo curioso: app con
   `--dart-define=DEMO_ISTANTE=2026-12-12T14:00:00Z` (le 15:00 di Lucca), onboarding da visitatore
   curioso, poi il pulsante "Piove" premuto UNA volta (oggi i segnali si sommano). Criterio: nessuna
   tappa all'aperto e nessuna bottega partner.

## Prossima ondata: 2 (testi e app)

- Testi delle tappe e riscrittura dei motivi (difetto d).
- Titoli leggibili delle esperienze in app (blocco 2 del Traguardo A).
- Badge (tra cui "dimostrativo" per ricordi e botteghe fittizie).
- Interruttori dei segnali nell'app.
- Campo "curiosità" per le leggende (labirinto, smeraldo, Lucida Mansi, leccio dei Guinigi, ...):
  testo della tappa che non entra mai nel punteggio.

## Dopo l'ondata 2, verso la demo del 12/12/2026

1. **Coordinate e mappa**: coordinate dei luoghi nel seed, distanze reali tra le tappe, link
   "Come arrivo qui" a Google Maps (a piedi, un link per tappa, nessuna chiave). Per
   `exp-pfanner-dalle-mura` il punto è sulle Mura, non il palazzo. Riferimento per il controllo:
   la mappa ufficiale del centro storico 2024.
2. **Ondata grafica**: direzione "C" (canvas "Lucca Soul — direzioni grafiche": caratteri del deck,
   accento mattone, mappa in alto, interruttori dei segnali con "Annulla"), logo delle Mura nella
   testata, icona e favicon dell'app (oggi quelle di Flutter). Miniature solo con foto di licenza
   nota (proprie o Wikimedia Commons con credito).
3. **Blocco del codice verso il 5/12**, poi prove con l'orologio fissato a sabato 12/12 (10:00 e
   15:00) e Aura verificata RUNNING il giorno prima.

## Dopo la demo

- **Modello del tempo**: orari con periodo di validità (stagioni), chiusure e aperture per data,
  tramonto calcolato dalle coordinate, stato dell'itinerario (tappe fatte / in corso / da fare);
  `sospesa` sostituito da un periodo di chiusura.
- **Recommender**: riprogettazione dell'effetto gregge con un criterio di uscita misurabile.
- **Ricordi**: campo `dimostrativo` escluso da ogni aggregazione dell'Index.
- **Pioggia**: valutare di togliere, invece di mantenere, una tappa all'aperto senza alternativa.
- **Contenuti rinviati**: Museo della Zecca, Cammino di San Josemaría (descritto in modo neutro),
  Domus Romana, Palazzo Mansi; botteghe reali solo come aderenti, con il loro consenso.

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
