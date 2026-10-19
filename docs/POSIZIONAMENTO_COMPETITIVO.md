# Posizionamento competitivo — Lucca Soul Lab rispetto alle app "anti-trappola" e anti-overtourism

> Stato: analisi del 16/10/2026, verificata contro il codice al commit `4f84379`; numeri dei test
> rieseguiti il 19/10/2026 su `a79abc3`: 1.456 passati, 121 saltati (radice 273 + 5 saltati;
> servizi 1.183 + 116 saltati). Le affermazioni sui concorrenti vengono da fonti pubbliche
> (siti e stampa, elenco in fondo) e possono essere cambiate. Le etichette usate:
> **[verificato]** = eseguito o letto nel codice di questo repo; **[fonte]** = dichiarato pubblicamente
> dal concorrente; **[stima]** = inferenza, da confermare.

---

## 0. La tesi in una frase

Le app concorrenti ottimizzano **l'esperienza del singolo viaggiatore** ("niente trappole per turisti").
Lucca Soul Lab ottimizza **l'equilibrio della città**: pertinenza per il visitatore *vincolata* alla
distribuzione dei flussi, e una memoria collettiva che nasce dai cittadini.
Sono due categorie diverse anche quando lo schermo sembra simile.

Il rischio di sembrare un clone non è nel codice: è nel racconto. Se presentiamo il progetto partendo
dall'onboarding emotivo e dai "consigli autentici", siamo indistinguibili da Hint. Se partiamo dalla
distribuzione dei flussi e da Urban Memory, non abbiamo concorrenti diretti tra quelli analizzati.

---

## 1. Punto centrale A — La distribuzione dei flussi

### Cosa c'è oggi nel codice [verificato]

- **Funzione obiettivo vincolata.** `services/recommender/recommender/ranking.py`: lo score non è la
  pertinenza ma la pertinenza corretta da due penalità sul *luogo*:
  - *quota storica*: quanto il luogo ha già concentrato flusso reale (`BehaviorEvent`);
  - *quota strutturale*: quanto il luogo domina per pertinenza attraverso profili diversi, anche con
    zero eventi (chiude la falla del "luogo perfetto che assorbe tutto il flusso liberato").
- **Agganciato al prodotto.** `POST /itinerary` costruisce lo `score_fn` dal recommender e lo passa
  all'Experience Engine. Non è una funzione dormiente.
- **Affollamento nel motore.** `experience_engine/rules.py` ed `engine.py`: penalità proporzionale,
  esclusione oltre una soglia critica, sostituzione della tappa in `/itinerary/adapt`.
- **Misura.** `intelligence_index/distribuzione.py`: `distribuzione_flussi` come entropia di Shannon
  normalizzata, esposta in `GET /dashboard/index` e `/dashboard/flows` con soppressione a soglia k.
- **Regressione bloccante.** `tests/test_integration_wave3b.py`: se il recommender peggiora
  l'entropia aggregata, la CI si rompe. Nello scenario originale (storico concentrato su 2 luoghi)
  l'entropia passa da 0,783 a 0,842, ricalcolata il 19/10/2026 con gli helper del test; il test
  verifica solo che non scenda, non questi valori.
- **Nessun pay-to-play.** Nessun campo esprime priorità a pagamento; i vettori commerciali indiretti
  (segnali fluttuanti, eventi promossi) sono chiusi e verificati da `ethics-guardian`.

### Cosa NON c'è ancora [verificato, vedi `I_LIMITI_DEL_MOTORE.md` e `docs/LIMITI.md`]

| Limite | Perché conta | Come si chiude |
|---|---|---|
| `Signal.affollamento` arriva dal client: **nessuna fonte reale** lo popola | Senza dati veri il motore redistribuisce "alla cieca" | Accordo dati col Comune (sensori, varchi, biglietterie, parcheggi) |
| Correzione **locale per richiesta**, non garanzia aggregata | Su molte richieste l'aggregato può ancora peggiorare in casi limite | Allocazione online con stato condiviso — fase di ricerca a sé |
| L'Index misura **solo gli utenti dell'app** | Non è una fotografia dei flussi cittadini | Dichiararlo; incrociare con dati esterni |
| `behavior_event` senza flag sintetico né finestra temporale | Un evento di prova altera ranking e indicatori | Flag `sintetico` + finestra su `ts` |
| `nuovi_percorsi` senza persistenza degli itinerari | Il valore va letto come "non misurato", non come zero | Persistere gli itinerari |
| App e dashboard Flutter: compilano (`flutter analyze` e `flutter test` verdi in CI) ma **non sono mai state avviate**: mancano le cartelle piattaforma | Non dimostrabile a un cliente | Prima esecuzione e prova manuale (Traguardo A, blocco 1, `docs/BUILD_PLAN.md`) |

### Come va raccontata all'amministrazione

Non "vi mostriamo i flussi" (il monitoraggio i Comuni lo comprano già altrove), ma:

1. il Comune fornisce i segnali di affollamento;
2. il motore redistribuisce chi usa l'app;
3. l'Index **dimostra l'effetto**: chi segue Lucca Soul si distribuisce meglio di prima?

È uno strumento di **intervento con misura di efficacia incorporata**. È la parte che un'app B2C
non ha interesse a costruire, perché il suo cliente è il turista che paga, non la città [stima].

---

## 2. Punto centrale B — Urban Memory

### Cosa c'è oggi [verificato]

- `services/urban-memory/` è il servizio più sviluppato del repo (~6.400 righe).
- Conferimento con **consenso esplicito e licenza tracciata**; nessun contributo persiste senza.
- **Curatela come gate di pubblicazione:** `curato=True` solo se ogni target in `riguarda` esiste nel grafo.
- Endpoint `POST /memory` e `GET /memory/{place_id}` (solo contenuti curati).
- Il Cittadino ha un percorso proprio e non paga: è la condizione di sostenibilità sociale.

### Perché è il vantaggio difficile da copiare

- Il contenuto **nasce dalla partecipazione** (racconti, mestieri, botteghe, dialetto) e cresce con
  l'uso: un concorrente non può comprarlo né generarlo.
- È **patrimonio immateriale**, non una lista di locali: apre canali di finanziamento culturale che
  un'app di consigli non ha [stima — da verificare sui bandi, white paper App. C].

### Limiti [verificato]

- Un racconto su un luogo che **non è nel grafo** non verrà mai pubblicato: proprio la memoria non
  ancora catalogata, quella più fragile, oggi si perde. Si chiude con il curatore che può creare il luogo.
- Senza cittadini reali che conferiscono, il fossato è teorico: dipende dal Living Lab, non dal codice.

---

## 3. Confronto con le app in sviluppo o sul mercato

### Hint (ex Mr. Franz) — il concorrente più vicino

**Cos'è [fonte]:** start-up milanese (HINT S.R.L.), pre-seed da 500.000 €, app su App Store e Google
Play. Mappe personali con posti scelti da persone del posto ("Hinter") abbinate al profilo del
viaggiatore; nessun locale paga per entrare; chatbot "Scout"; community per città. 17 città
(soprattutto Giappone, Corea, metropoli), con Firenze, Venezia e Napoli annunciate entro novembre 2026.
Vende mappe e pass al viaggiatore (B2C). Si posiziona esplicitamente *contro* AI e algoritmi.

| Dimensione | Hint | Lucca Soul Lab |
|---|---|---|
| Problema dichiarato | Stress del viaggiatore, trappole per turisti | Overtourism e significato della città |
| Cliente | Viaggiatore pagante | Turista, Cittadino, Operatori, Comune, Sviluppatori |
| Funzione obiettivo | Soddisfazione del singolo | Pertinenza **vincolata** alla distribuzione dei flussi [verificato] |
| Fonte dei contenuti | Rete di local [non verificato: se siano pagati] + team editoriale | Knowledge Graph + Urban Memory partecipativa + CURATOR |
| Unità consigliata | Il singolo posto | Il percorso di senso (relazioni nel grafo) |
| Profilazione | Onboarding "come viaggi" → abbinamento a local simili | `EmotionalProfile` da onboarding conversazionale |
| Eventi effimeri | Non dichiarati | Segnali fluttuanti → `:Evento` con cadenza, attrito, freno [verificato] |
| Misura per la città | Assente | Urban Intelligence Index, privacy a soglia k [verificato] |
| Spiegabilità | Nota del local sul posto | `reason` obbligatorio su ogni tappa [verificato]; in adattamento è verificabile solo per le tappe rigenerate dal server (`docs/LIMITI.md`, voce "il `reason` delle tappe mantenute o non toccate è testo del client") |
| Pay-to-play | Escluso | Escluso, con gate etico separato [verificato] |
| Copertura | 17 città, in espansione | 1 città pilota, replicabile cambiando dataset |
| Maturità di mercato | App pubblicata, >3.000 acquirenti dichiarati | Mai in mano a utenti reali |

**Pro di Lucca Soul Lab rispetto a Hint**
- Obiettivo anti-concentrazione **nel codice e in CI**, non nel marketing.
- Urban Memory: contenuto che una rete di consiglieri locali non produce.
- Profondità su una città (Puccini, Mura, eventi) invece di ampiezza.
- Ha un cliente istituzionale naturale; Hint no.
- Spiegabilità auditabile da un'amministrazione, oggi solo per le tappe rigenerate dal server
  (voce in `docs/LIMITI.md`).

**Contro di Lucca Soul Lab rispetto a Hint**
- Hint esiste sul mercato, ha capitale, brand, app negli store e utenti paganti; noi no.
- La loro rete di local produce contenuti **validati sul campo**; il nostro seed è curato, non
  validato (`I_LIMITI_DEL_MOTORE.md` §11).
- Le 5 botteghe del seed sono dimostrative; i posti di Hint sono reali.
- Sull'esperienza d'ingresso (profilo emotivo → consigli personali) **siamo indistinguibili**.
- Il nostro vantaggio sui flussi oggi gira senza dati reali di affollamento.
- La nostra app compila (`flutter analyze` e `flutter test` verdi in CI) ma non è mai stata
  avviata: mancano le cartelle piattaforma.

**Rischio specifico:** Firenze entra in Hint a breve. Lucca come "gita da Firenze" è plausibile nel
medio periodo [stima], ma probabilmente come aggiunta leggera: se il loro modello paga i local per
posto [non verificato], e su una città piccola il costo si divide su pochi acquirenti.

### Unexpected Italy

**[fonte]** Start-up italiana, app lanciata nell'estate 2024 per suggerire mete e itinerari meno noti,
presentata dalla stampa come antidoto all'overtourism; attiva su Venezia, Roma, Vicenza, Bassano del
Grappa e Modena (agosto 2024).

- **Somiglianza:** è l'unica tra quelle analizzate che dichiara apertamente l'overtourism come obiettivo.
- **Differenza [stima]:** sposta il turista *tra destinazioni* (mete minori); noi lo distribuiamo
  *dentro* la città e misuriamo l'effetto. Nessuna evidenza pubblica di un indicatore di efficacia
  per l'amministrazione né di una memoria partecipativa.
- **Da verificare:** stato attuale del prodotto, se esiste un'offerta B2G.

### EPU (Repubblica Ceca)

**[fonte]** App di Gatyer e Algodos, sostenuta dal Ministero dell'Ambiente ceco: percorsi alternativi
per alleggerire i luoghi naturali più affollati, con avvisi sulle restrizioni in vigore.

- **Somiglianza:** obiettivo di redistribuzione, sostegno pubblico.
- **Differenza:** ambito naturalistico, catalogo di percorsi predefiniti, nessuna personalizzazione
  né misura dichiarata [stima].
- **Utile come precedente:** dimostra che un ente pubblico finanzia questo tipo di strumento.

### Precedenti istituzionali (non in sviluppo, ma utili per il racconto)

- **Play London with Mr Bean (2017)**: gioco a punti per portare i turisti fuori dal centro. La
  stampa di settore dubitava che disperdesse davvero i flussi invece di alimentare attrazioni già
  piene [fonte]. È esattamente il dubbio a cui risponde il nostro test di entropia.
- **App di Dubrovnik (annunciata 2018)**: avvisi di affollamento nella città vecchia e mete alternative
  [fonte]. Il modello "il Comune fornisce il dato, l'app redistribuisce" è quello che proponiamo.

---

## 4. Sintesi: dove giochiamo e dove no

| Terreno | Giochiamo? | Perché |
|---|---|---|
| App B2C "consigli autentici" per turisti | **No** | Hint ci batte su capitale, contenuti, distribuzione |
| Strumento di redistribuzione con misura per il Comune | **Sì — terreno principale** | Vincolo nel codice + Index; nessun concorrente analizzato lo offre |
| Conservazione del patrimonio immateriale urbano | **Sì — fossato** | Urban Memory; nessun concorrente analizzato lo fa |
| Copertura multi-città | Non ora | Replicabile per design, ma un pilota alla volta |

---

## 5. Cosa serve prima di presentarsi a un'amministrazione

In ordine di priorità:

1. **Una fonte reale per `Signal.affollamento`** — anche solo un CSV di biglietteria museale o parcheggi.
2. **Flag `sintetico` + finestra temporale** su `behavior_event`, per non inquinare ranking e Index.
3. **App e dashboard avviate e provate a mano** almeno una volta (oggi compilano in CI ma mancano
   le cartelle piattaforma).
4. **Il percorso "luogo non nel grafo"** per Urban Memory, perché la memoria più fragile non vada persa.
5. Una frase onesta sul confine: l'Index misura l'effetto delle raccomandazioni sugli utenti dell'app,
   non i flussi dell'intera città.

---

## Fonti

- Hint — sito ufficiale: https://gethint.com/
- Startupbusiness, "Traveltech firm Hint raises €500,000 in a pre-seed funding round":
  https://www.startupbusiness.it/en/traveltech-firm-hint-raises-e500000-in-a-pre-seed-funding-round/156953/
- Hint su Trustpilot: https://it.trustpilot.com/review/gethint.com
- Sky TG24, Unexpected Italy (22/08/2024): https://tg24.sky.it/economia/2024/08/22/overtourism-italia-app
- Radio Prague International, EPU: https://english.radio.cz/node/8833808
- Skift, Play London (2018): https://skift.com/2018/06/27/london-uses-mobile-gaming-app-to-help-tackle-overtourism/
- Reuters via The Daily Star, Dubrovnik e overtourism:
  https://www.thedailystar.net/business/europes-tourist-hotspots-look-ways-cope-the-crowds-1546876
