# Come raccontare Lucca Soul Lab

Guida per parlarne a voce. Non un documento da leggere: frasi da dire.

---

## La regola che vale più di tutte

**Parti dall'esempio, non dall'architettura.**

Nessuno ha bisogno di capire la pipeline. Devono capire perché un grafo produce qualcosa
che un catalogo non può produrre. E quello si spiega con un caso concreto, in trenta secondi.

Se cominci con "abbiamo un knowledge graph con un layer RAG", hai già perso la stanza.

---

## 1. I trenta secondi

> «Prendiamo un appassionato di Puccini che arriva a Lucca.
>
> Qualunque app gli dà le stesse tre cose: la casa natale, il teatro, il museo.
> Sono le tre cose che stanno nella categoria "Puccini".
>
> Il nostro sistema lo porta nella bottega di un liutaio, a vedere nascere un violino.
>
> Perché da noi Puccini e il liutaio **sono collegati**. Non stanno in due categorie diverse:
> stanno nella stessa rete di relazioni. E quella connessione un elenco non ce l'ha.»

Poi ti fermi. Lascia che sia l'altro a chiedere "e come fa?".

**Perché funziona:** la persona *vede* la differenza invece di sentirsela descrivere.
E capisce da sola che serve una tecnologia diversa, senza che tu debba nominarla.

---

## 2. Se hai due minuti

Aggiungi, nell'ordine — una frase per punto, senza dilungarti:

**La domanda cambiata.**
> «Le app turistiche rispondono tutte a "cosa posso vedere". Producono cataloghi, e infatti
> ne esistono migliaia. Noi rispondiamo a "chi vuoi diventare oggi". È un'altra tecnologia,
> non un altro design.»

**Cos'è il grafo, in una riga.**
> «Non un database di monumenti: una rete di relazioni fra luoghi, artisti, botteghe, temi,
> tradizioni. Un database lo interroghi per categoria. Una rete la attraversi.»

**Il numero che chiude il punto.**
> «Nel grafo di Lucca abbiamo 142 relazioni. Solo 38 sono distanza fisica. Le altre 104
> sono semantiche: il sistema sa cosa c'entra con cosa, non solo cosa sta vicino a cosa.»

**L'adattamento.**
> «E cambia mentre la giornata cambia. Se comincia a piovere, il percorso si riscrive verso
> luoghi al chiuso. Se le Mura sono sature, ti sposta — e mai verso un altro posto affollato.»

**La città in tempo reale.**
> «E reagisce a ciò che accade adesso. Se c'è un violinista che suona in una piazza, e a te
> interessa la musica, il sistema ti ci porta — te lo aggiunge al volo. Ma se una gelateria
> prova a segnalarsi da sola per farsi passare gente davanti, quella non entra: un segnale non
> può mai essere un'attività commerciale. È la differenza fra sentire la città e farsi vendere.»

**Il vincolo etico, in forma di fatto.**
> «Un algoritmo normale ottimizza i click. Applicato a una città, quello vuol dire mandare
> tutti dove sono già tutti. Il nostro ottimizza la distribuzione dei flussi. E lo dimostriamo:
> c'è un test che fa fallire il sistema se la concentrazione peggiora.»

Chiudi qui. Due minuti bastano per farsi ricordare.

---

## 3. Se hai dieci minuti (e le slide)

Usa **cinque slide**, in questo ordine. Non di più.

| Slide | Cosa dici |
|---|---|
| **23** Perché un grafo | L'esempio Puccini → liutaio. Fai il confronto a voce coi due pannelli. |
| **24** Dentro il grafo | «Non è un'illustrazione: è il seed vero, ricostruibile con un comando.» Il 104 su 142. |
| **26** Chi decide | Qui ti fermi più a lungo. Vedi sotto. |
| **31** I vincoli e i test | «Ogni principio ha un test che lo difende. E quando hanno fallito, hanno fermato cose vere.» |
| **32** Il bug di privacy | La storia. È quella che si ricordano. |

### La slide 26 è il tuo momento migliore

È l'argomento che nessun concorrente può copiare a parole. Dillo così:

> «Guardate: il grafo propone, ma non decide. Il recommender ordina, ma non decide —
> e può solo penalizzare, mai premiare. Il modello linguistico racconta, ma non decide.
>
> Decide **un solo componente**.
>
> Non è un dettaglio tecnico: è la ragione per cui possiamo *dimostrare* l'etica invece di
> dichiararla. Un vincolo applicato in un punto solo lo si può controllare. Distribuito su
> cinque componenti, no — e nessuno può più verificarlo, nemmeno noi.»

### La storia del bug (slide 32)

Raccontala come una storia, non come una specifica:

> «La regola dice: se un dato riguarda meno di dieci persone, non si pubblica — o si
> risalirebbe alla singola persona. Quella regola funzionava.
>
> Ma il sistema doveva anche *spiegare* perché il dato non c'era. E quel messaggio riusava
> l'errore interno, che conteneva il conteggio esatto delle persone.
>
> La protezione funzionava. A tradirla era la frase che spiegava la protezione.
>
> L'abbiamo trovato noi, corretto, e scritto nella documentazione. Non è il tipo di cosa
> che una certificazione di conformità intercetta.»

**Perché questa storia è la più efficace che hai:** dimostra che i controlli lavorano davvero,
e che siete disposti a raccontare un errore. Chi ha valutato progetti sa che chi non ha mai
trovato un problema, semplicemente non ha guardato.

---

## 4. Le domande che ti faranno

### «Ma non è un chatbot? Non è ChatGPT?»

> «Il modello linguistico da noi fa tre cose: conduce la conversazione iniziale, scrive la
> spiegazione di ogni tappa in italiano, e traduce. Non sceglie niente. Non ordina niente.
> Non sa nemmeno quali attività sono partner e quanto costano.
>
> Ed è sostituibile: se domani esce un modello migliore, lo cambiamo in un pomeriggio.
> Quello che non si sostituisce è il grafo della città e la memoria che ci accumuliamo dentro.»

### «E se lo fa Google?»

> «Il modello linguistico è una commodity, ce l'hanno tutti. Il nostro vantaggio è il grafo
> delle relazioni culturali di Lucca e la memoria collettiva che i cittadini ci conferiscono.
> Quella non si compra e non si scarica: si costruisce stando in una città, con le persone
> che ci vivono. Google può fare il motore. Non può fare la memoria di Lucca.»

### «Chi mantiene i contenuti? Non è un costo enorme?»

> «È la ragione per cui Urban Memory esiste. Chi partecipa a un laboratorio o ascolta il
> racconto di un anziano non consuma contenuto: ne produce. La memoria cresce con l'uso
> invece di consumarsi. È l'opposto di un archivio da riempire una volta con un progetto
> finanziato che poi si esaurisce.»

### «Come guadagnate?»

> «Cinque fonti indipendenti: accesso premium per i turisti, commissione sulle esperienze
> prenotate, abbonamento per gli operatori, licenza per hotel e strutture, licenza per il
> Comune sulla dashboard.
>
> Quello che **non** facciamo è vendere visibilità. Un partner compare se è coerente con la
> persona, punto. Non esiste un prezzo che sposti la posizione. Rinunciamo alla via più
> rapida al ricavo, e in cambio siamo vendibili a un'amministrazione pubblica.»

### «Come garantite che non sia il solito algoritmo che spinge chi paga?»

Questa è la domanda a cui hai la risposta migliore. Non rispondere con un principio:

> «Non ve lo chiediamo per fiducia. C'è un test che verifica che il punteggio di
> un'esperienza sia **identico** con e senza partner, con e senza prezzo, con e senza
> commissione. Bit per bit. Se qualcuno domani scrivesse codice che dà un vantaggio a chi
> paga, quel test si romperebbe e il codice non entrerebbe.
>
> E la commissione viene registrata *dopo* che la scelta è stata fatta, in una tabella
> separata. Nel momento in cui il sistema decide, quel dato non esiste ancora.»

### «Funziona davvero? L'avete provato?»

> «Il motore esiste e gira: cinque fasi di sviluppo chiuse, oltre cinquecento test, un grafo
> di Lucca ricostruibile da zero con un comando. Ogni fase l'ho verificata io a mano contro
> l'infrastruttura vera, non su dati simulati.
>
> Quello che manca è la sperimentazione con persone reali. È esattamente la fase per cui
> cerchiamo il partner.»

### «Perché Lucca?»

> «Perché è la scala giusta per un esperimento: abbastanza grande da avere un flusso
> internazionale vero, abbastanza piccola perché un'iniziativa possa diventarne un punto di
> riferimento. Ed è murata — un perimetro chiuso, per uno studio sui flussi, è un vantaggio
> metodologico raro.
>
> Ma Lucca non è il mercato: è il laboratorio. Se funziona qui, lo stesso motore si replica
> cambiando solo il contenuto locale.»

---

## 5. «Ma non lo fa già un RAG con gli embedding?»

È l'obiezione più prevedibile di tutte — la prima cosa che viene in mente a chiunque conosca
un po' di tecnologia. Un modello generico, messo davanti alla stessa sfida, ci arriva in trenta
secondi: vettori, recensioni, similarità. Averla vista costruire è un vantaggio: sai esattamente
com'è fatta la soluzione ovvia, e perché non è la tua.

### La soluzione ovvia

Prendi le recensioni (TripAdvisor, Google, blog), estrai gli aggettivi emotivi, trasformi tutto
in vettori. L'utente esprime un mood, lo trasformi in un vettore, e cerchi i luoghi **più vicini**
in quello spazio. Poi un LLM scrive l'itinerario con tono empatico.

È RAG standard, fatto bene. E ha tre debolezze strutturali — che sono i tuoi tre punti di forza.

### Perché la tua è un'altra cosa

**Il sistema ovvio misura una distanza. Il tuo attraversa una rete.**

La similarità ti porta a ciò che *assomiglia* al tuo mood: cerchi «malinconia», trovi luoghi già
etichettati malinconici. È un abbinamento accurato — l'opposto della sorpresa. Il tuo motore non
abbina, **cammina**: da Puccini arriva al liutaio seguendo una *relazione*, non perché il liutaio
abbia recensioni malinconiche. La serendipità vera nasce dal seguire una connessione verso qualcosa
che non ti aspettavi, non dal trovare ciò che ti somiglia.

### Le tre debolezze del modello ovvio

**Si fonda sulle recensioni — cioè sulla popolarità.** I luoghi senza recensioni non esistono:
il liutaio con dodici commenti è invisibile accanto alle Mura con diecimila. È esattamente il bias
che genera overtourism, ed è il motivo per cui hai scartato le stelle di Google. Il sistema ovvio
ci costruisce sopra tutto; tu l'hai escluso per principio.

**Non ha dove mettere l'etica.** Un sistema a pura similarità manda tutti i «malinconici» nello
stesso chiostro nascosto, finché non è più nascosto. La funzione obiettivo è una sola — la
vicinanza — e non c'è posto per un vincolo di distribuzione. Il tuo penalizza la concentrazione
per progetto.

**Non ha memoria della città.** Il modello ovvio legge recensioni che stanno già su internet.
Tu accumuli i racconti dei cittadini, che su internet non ci sono e non ci saranno mai. Il suo
contenuto è scaricabile; il tuo no.

### Chi decide — la differenza che riassume tutto

Nel sistema ovvio, l'LLM riceve i luoghi già scelti dalla similarità e il contesto iniettato nel
prompt, e **decide**. Se sbaglia tono, ignora il meteo o si fa influenzare da una recensione, non
c'è nulla sotto a correggerlo.

Nel tuo, l'LLM **racconta ma non decide**. La scelta l'ha già fatta l'Experience Engine con i
filtri duri; il modello aggiunge la spiegazione. È il motivo per cui il tuo sistema è verificabile
e il suo no: nel suo, per sapere perché ha proposto quel luogo devi interrogare un LLM; nel tuo,
la ragione è nel grafo e nei vincoli, e la puoi mostrare a un Comune.

Nota anche l'adattamento: «se piove, orienta verso un caffè con vetrate» nel modello ovvio è un
suggerimento iniettato nel prompt, che l'LLM può ignorare. Nel tuo è un **filtro duro**: se piove,
il posto all'aperto è escluso prima che l'LLM parli. La differenza è fra «chiedo gentilmente al
modello di tenerne conto» e «la regola non è negoziabile».

### La risposta, pronta

> «Quella è la soluzione ovvia, e l'ho vista costruire da un modello generico in trenta secondi.
> Si fonda sulle recensioni — quindi sulla popolarità, il bias che genera overtourism — mette il
> modello linguistico al centro della decisione, e non ha nessun posto dove applicare un vincolo
> etico. Io ho fatto il contrario: ragiono per relazioni, non per somiglianza; il modello racconta
> ma non decide; e i vincoli sono nel codice, verificabili. È più difficile da costruire. È anche
> l'unica versione che si può vendere a un Comune.»

**Una nota onesta:** la similarità vettoriale non è sbagliata come *componente* — è utile dentro
il tuo sistema, per il RAG che genera le spiegazioni. Ma è un mattone, non l'edificio. Il modello
ovvio scambia il mattone per l'edificio; tu hai costruito l'edificio.

---

## 6. Cosa NON dire

**Non dire «usiamo l'intelligenza artificiale».**
Lo dicono tutti, non distingue nulla, e sposta l'attenzione sulla tecnologia invece che sulla
differenza. Di' cosa fa il sistema, e lascia che sia l'altro a dire "quindi è AI".

**Non partire dall'architettura.**
"Urban Cognitive Layer", "Knowledge Graph", "RAG" sono nomi utili *dopo* che la persona ha
capito. Prima sono rumore.

**Non chiamarla «app».**
È un motore. L'app è il punto di contatto. La differenza conta soprattutto con un investitore:
un'app vale il suo download, un motore vale ogni città su cui si replica.

**Non promettere numeri che non hai.**
Il modello economico è pianificato per la versione 1.2 del dossier. Se ti chiedono proiezioni,
la risposta giusta è: «Il piano finanziario è in costruzione su dati verificati. Preferisco
darvelo dopo che averlo inventato adesso.» Quella frase, davanti a un valutatore serio,
vale più di qualsiasi tabella.

**Non nascondere i limiti.**
Ne avete sei documentati. Se emerge il tema, tirali fuori tu per primo: «Sappiamo che questa
correzione è robusta ma non è una garanzia matematica, ed è scritto nella nostra
documentazione.» Chi dichiara un confine rende credibile tutto il resto.

---

## 7. Le tre frasi da sapere a memoria

Se ne ricordi solo tre, siano queste.

> **«Le Smart City raccolgono dati. Le città intelligenti generano significato.»**

> **«Un catalogo indicizza. Un grafo attraversa. È lì che nasce la sorpresa —
> e la sorpresa è il prodotto.»**

> **«Decide un solo componente. È per questo che l'etica possiamo dimostrarla,
> invece di dichiararla.»**

---

## 8. Se hai trenta secondi e una sola cosa da dire

Il liutaio.

Non l'architettura, non i numeri, non l'etica. Il liutaio.
È l'unica cosa che si ricordano dopo una settimana — e da lì si torna a tutto il resto.
