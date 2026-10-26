# Stato del progetto — 2026-10-26

`main`: ondata 1c inclusa (merge fast-forward di `feat/ondata1c-contenuti`, correzione `e36dfec`; CI verde).
Ondata 2a inclusa (merge fast-forward di `feat/ondata2a-testi`, `d9f6664`; CI verde).
Ondata 2b inclusa (merge fast-forward di `feat/ondata2b-app`, `9be2259`; CI verde).
Ondata 3 inclusa (merge fast-forward di `feat/ondata3-dati`, `b7f2f6f`; CI verde).
Ondata 4 inclusa in `main` (`6e93b06`..`effa9aa`, avanzamento veloce dal ramo `feat/ondata4-grafica`).
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

- **4** (grafica e demo), commit sul ramo `feat/ondata4-grafica`:
  - compito 1 (`ccdefb0`): riordino delle tappe per vicinanza in composizione (prima tappa fissa,
    botteghe ferme; fino a 7 tappe mobili tutte le permutazioni, sopra 7 vicino più prossimo;
    ordine accettato solo se tutte aperte all'arrivo, budget rispettato e metri strettamente
    minori). Distanze stimate (linea d'aria × 1,3), non un percorso su strada. Regola in
    `docs/ENGINE_INVARIANTS.md` §4-bis;
  - compito 2 (`6e93b06`): il BFF serve la build web su `/` se `APP_WEB_DIR` punta a una cartella
    esistente (stessa origine, niente CORS); `scripts\avvia_demo.ps1` (`-Istante`, `-Rete`); con
    `--dart-define=DEMO=true` l'app accetta `?istante=...Z` nell'indirizzo;
  - compito 3 (`92b7853`): grafica direzione C;
  - compito 4 (`8daafaa`): mappa dell'itinerario in alto (flutter_map + OpenStreetMap);
  - compito 5 (`5be487d`): favicon e icone web dal logo delle Mura;
  - compito 5-quater (`27a88e7`): nessuna tappa in coda (fluttuanti, eventi promossi) per chi
    chiede accessibilità;
  - compito 5-ter (badge "dimostrativo" come campo di contratto): NON fatto, per decisione del
    committente; il segno resta nel testo del motivo («(esempio dimostrativo)»);
  - compito 7: documentazione (questo aggiornamento).

## Da fare (committente), dopo il merge della 3

1. Ricarica del seed su Aura: `.venv\Scripts\python.exe -m graph.loader`.
2. Riavvio del BFF (i `.cypher` sono letti una volta).
3. Prova in app: profilo curioso, mezza giornata, Piove più Sono stanco/a: attese 3 tappe, non 2
   (dall'ondata 4, con le tappe riordinate per vicinanza, sono 4: si taglia solo il Duomo);
   il link "Come arrivo qui" porta all'ingresso giusto.

## Prossimo passo: blocco del codice e prove della demo

1. **Blocco del codice a metà novembre.** Dopo, solo correzioni di difetti che bloccano la demo.
2. **Prove con l'orologio fissato a sabato 12/12**, alle 10:00 e alle 15:00 (ora di Lucca). Dalla
   radice del repo:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Istante 2026-12-12T09:00:00Z
   ```
   poi nel browser `http://localhost:8000/` (10:00) e
   `http://localhost:8000/?istante=2026-12-12T14:00:00Z` (15:00). Dettagli in
   `apps/lucca_soul_app/README.md`.
3. **Aura verificata RUNNING il giorno prima** (Aura Free si mette in pausa).
4. **Copione aggiornato** (dall'ondata 4, tappe riordinate per vicinanza):
   - profilo curioso alle 10:00: ordine atteso San Michele, Pfanner, San Frediano, San Pietro
     Somaldi, Santi Giovanni, circa 1,6 km invece di 2,35;
   - alle 15:00, curioso con «Piove» + «Sono stanco/a»: restano 4 tappe (tagliato il Duomo).

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
