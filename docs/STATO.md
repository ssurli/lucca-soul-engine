# Stato del progetto — 2026-10-21

`main`: ondata 1c inclusa (merge fast-forward di `feat/ondata1c-contenuti`, correzione `e36dfec`; CI verde).
Ondata 2a inclusa (merge fast-forward di `feat/ondata2a-testi`, `d9f6664`; CI verde).
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

## Da fare (committente), dopo il merge della 2a

Comandi PowerShell completi nel report della 2a; tutti dalla radice del repo, su `main`.

1. Migrazione Neon (due colonne nuove, nessuna cancellazione): `.venv\Scripts\python.exe -m urban_memory.migrate`.
2. Scarto del contributo di prova "demo inserimento" con `scripts\scarta_contributo.py` (elenco,
   prova a secco, poi `--esegui`).
3. Ricarica del seed su Aura (curiosità, racconti, articoli): `.venv\Scripts\python.exe -m graph.loader`.
4. Riavvio del BFF (i `.cypher` sono letti una volta).

## Prossima ondata: 2b (app)

- Interruttori dei segnali nell'app (oggi i segnali si sommano).
- Badge (tra cui "dimostrativo" per ricordi e botteghe fittizie).
- Domanda su Firenze.

## Dopo l'ondata 2, verso la demo del 12/12/2026

1. **Coordinate e mappa**: coordinate dei luoghi nel seed, distanze reali tra le tappe, link
   "Come arrivo qui" a Google Maps (a piedi, un link per tappa, nessuna chiave). Per
   `exp-pfanner-dalle-mura` il punto è sulle Mura, non il palazzo. Riferimento per il controllo:
   la mappa ufficiale del centro storico 2024. Nella stessa ondata dati, per ogni esperienza va
   registrata la **pagina ufficiale degli orari** come fonte.
2. **Ondata grafica**: direzione "C" (canvas "Lucca Soul — direzioni grafiche": caratteri del deck,
   accento mattone, mappa in alto, interruttori dei segnali con "Annulla"), logo delle Mura nella
   testata, icona e favicon dell'app (oggi quelle di Flutter). Miniature solo con foto di licenza
   nota (proprie o Wikimedia Commons con credito).
3. **Blocco del codice verso il 5/12**, poi prove con l'orologio fissato a sabato 12/12 (10:00 e
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
