# Lo spaccato del motore

Scheda di accompagnamento alle slide 23–28 del portfolio.
Prima il concetto, poi come è stato costruito l'argomento visivo.

---

# PARTE 1 — Il concetto di relazione

## La distinzione da cui parte tutto

In un database normale **«Puccini» è una riga con dei campi**: nome, data di nascita, categoria.
Se vuoi sapere cosa c'entra con altro, devi cercarlo tu, con una query che tu hai deciso di scrivere.

In un grafo **«Puccini» è un nodo**, e ciò che lo lega alle altre cose è **un oggetto a sé**:
una relazione con un nome, che si può percorrere.

Non è una differenza di formato. È una differenza di cosa il sistema *sa*.

## Un tratto vero del grafo di Lucca

```
        Giacomo Puccini          (Artista)
               │
          ispirata_da
               ▼
       Bottega di liuteria       (Bottega)
               │
             offre
               ▼
        Nasce un violino         (Esperienza)
               │
             evoca
               ▼
            Musica               (Tema)
               ▲
             evoca
               │
        Un'aria al Giglio        (Esperienza)
```

## Tre cose da notare

**La relazione ha un nome, e il nome è il significato.**
Non è «Puccini è collegato alla bottega» in modo generico: è `ispirata_da`. Il sistema sa *in che
modo* sono legati, non solo *che* lo sono. È la differenza fra un link e una frase.

**Ha una direzione, ma si percorre nei due sensi.**
Le due relazioni `evoca` puntano entrambe verso «Musica», perché nello schema vanno sempre
Esperienza → Tema. Eppure il motore parte da un'esperienza, sale al tema e **ridiscende** verso
l'altra. Percorrere una relazione al contrario è legittimo — ed è lì che nascono le sorprese.

**Si concatena — ed è il punto vero.**
Una relazione sola non serve a niente: il valore è che l'uscita di una è l'ingresso della
successiva. Da Puccini arrivi alla bottega in un passo. Ma da lì, attraverso il tema condiviso,
arrivi a un'aria all'opera — due esperienze che nessuna categoria avrebbe mai messo insieme,
perché una sta in «artigianato» e l'altra in «musica».

## Le sette relazioni del grafo di Lucca

| Relazione | Quante | Cosa dice, in italiano |
|---|---|---|
| `EVOCA` | 65 | questa esperienza (o bottega) **parla di** questo tema |
| `VICINO` | 38 | questi due luoghi **sono a due passi** |
| `SI_SVOLGE_A` | 22 | questa esperienza **accade** in questo luogo |
| `LEGATO_A` | 7 | questo artista **ha a che fare con** questo luogo |
| `OFFRE` | 5 | questa bottega **propone** questa esperienza |
| `HA_ABBONAMENTO` | 3 | questa bottega **è un partner attivo** |
| `ISPIRATA_DA` | 2 | questa bottega **si ispira a** questo artista |

`EVOCA` è la più numerosa e non è un caso: i 13 **Temi** funzionano da snodi. Ogni tema è un
incrocio dove si ritrovano esperienze che, per categoria, starebbero in scaffali diversi.
Tredici nodi che ne collegano ventisette: è il tessuto connettivo del grafo.

## Il numero da dire a voce

> **Su 142 relazioni, solo 38 sono `VICINO` — cioè distanza fisica.
> Le altre 104 dicono che cosa c'entra con cosa.**

Un navigatore conosce solo le 38: sa che il Duomo è vicino a San Michele, e sa portartici.
Non sa che un liutaio ha a che fare con Puccini, perché quella non è un'informazione
geografica — è culturale, e va scritta a mano, una relazione alla volta.

Ecco perché il grafo è un asset e non un file: **quelle 104 relazioni sono il lavoro**.
Non si scaricano da nessuna parte.

## Come dirlo in una frase

> «In un database Puccini è una scheda. Nel nostro grafo Puccini è un nodo, e ogni cosa che lo
> lega al resto della città è una relazione con un nome — che si può percorrere. Il liutaio si
> ispira a lui: è scritto. E da lì si continua a camminare.»

**Se ti chiedono «e chi le scrive queste relazioni?»** — è la parte migliore della risposta:
all'inizio le scrivete voi, poi Urban Memory le fa crescere. Ogni contributo di un cittadino
aggancia un nuovo nodo al grafo. Su Aura ce n'è già uno in più rispetto al seed.

---

# PARTE 2 — Le sei slide, e perché in quest'ordine

Sei slide (23–28), inserite **prima** del capitolo sulle prove. La sequenza è l'argomento:
si comincia dalla differenza, si passa ai fatti, si finisce con l'obiezione già disinnescata.

### 23 · Perché un grafo, non un catalogo

Due pannelli affiancati. A sinistra il catalogo: Musica, Artigianato, Monumenti — scatole che non
si parlano, e chi ama Puccini non arriverà mai al liutaio. A destra il grafo, col cammino reale
del seed: *Puccini —ISPIRATA_DA— Bottega di Liuteria —OFFRE— Nasce un violino*. Un salto solo.

**Perché apre il capitolo:** la persona *vede* la differenza invece di sentirsela descrivere,
e capisce da sola che serve una tecnologia diversa — senza che tu debba nominarla.

### 24 · Dentro il grafo

I 62 nodi e le 142 relazioni con la composizione vera. E il numero che decide l'argomento:
**solo 38 relazioni su 142 sono prossimità fisica; le altre 104 sono semantiche.**

**Perché è la seconda:** dopo aver mostrato la differenza, serve dimostrare che non è
un'illustrazione concettuale. È il seed versionato, ricostruibile con un comando.

### 25 · Anatomia di una richiesta

Le cinque fasi dal dialogo all'itinerario, con evidenziata la quarta — l'unica che decide.

### 26 · Chi decide

Tre componenti con la scritta «✕ non decide», e sotto, su banda terracotta, l'Experience Engine.

**È il momento migliore del deck.** Un vincolo applicato in un punto solo è auditabile;
distribuito su cinque componenti non lo è più — nemmeno da voi. È il motivo per cui potete
*dimostrare* l'etica invece di dichiararla, ed è l'unica cosa che un concorrente non può
imitare con uno slogan. Rallenta qui.

### 27 · «Ma non è semplicemente un chatbot?»

L'obiezione è nel titolo invece che attesa dal pubblico. Cosa fa l'LLM (onboarding, `reason`,
multilingua, RAG senza riaddestramento) e cosa non fa (non sceglie, non ordina, non vede prezzi
né partner).

Chiusa con la riga che vale: **il `reason` è obbligatorio per contratto — una tappa senza
spiegazione non può nemmeno essere costruita.**

### 28 · La città che risponde

Pioggia, saturazione, stanchezza. Con il dettaglio che nessun concorrente può imitare: nella
riscrittura per affollamento il sistema **non manda mai verso un'altra concentrazione** —
la regola vale anche quando adatta.

---

# PARTE 3 — I tre livelli del tempo

Una città non offre solo cose che ci sono sempre. Ci sono cose che accadono una volta, e cose
che ci sono adesso e domani no. Il motore le distingue per **dove vivono**, non per quanto durano.

| Livello | Esempio | Dove vive | Come entra | Stato |
|---|---|---|---|---|
| **Permanente** | la bottega del liutaio | nel grafo | seed curato a mano | costruito |
| **Programmato** | il concerto di sabato alle 21 | nel grafo, con una data | inserito con data + organizzatore | **da costruire** |
| **Fluttuante** | il violinista che suona adesso | nel segnale | segnalato, scade da solo | costruito |

La distinzione non è la durata: è che il permanente e il programmato sono **struttura** (stanno
nel grafo), il fluttuante è **stato del mondo** (sta nel `Signal`, accanto a meteo e affollamento).

## Il fluttuante, in dettaglio

Il violinista in Anfiteatro non è un nodo del grafo: è una nota temporanea attaccata a un luogo.
Quando ce n'è uno attivo e coerente col profilo della persona, il motore **aggiunge** una tappa
breve all'itinerario — non sostituisce, non compete.

Tre regole lo tengono onesto:
- **aggiunge solo se coerente** — il violinista entra nel giro di chi il grafo collega alla
  musica, non di chi cerca artigianato;
- **mai un'attività commerciale** — un violinista in piazza sì, «artista davanti alla nostra
  gelateria» no: quello è pubblicità travestita da segnale, bloccata per costruzione;
- **non tocca il punteggio** di nessun'altra esperienza — è un'aggiunta, verificata bit-identica.

**Perché scade da solo:** il `Signal` è transitorio, mai salvato. Non serve cancellare il
violinista — semplicemente, alla richiesta successiva, non c'è più. Il costo di un errore
effimero è basso, ed è per questo che il fluttuante può essere alimentato senza curatela
preventiva, mentre il permanente no.

## Dove finisce una locandina — la domanda che ti faranno

Una locandina appesa a un muro **non è fluttuante**: annuncia in anticipo qualcosa con una data.
È l'esempio tipico del livello **programmato**. Il fluttuante è «sta succedendo adesso»; la
locandina è «succederà, segnatelo» — struttura opposta.

La domanda che scioglie ogni dubbio è una sola: **c'è una data futura precisa?**
- sì → programmato (il concerto di sabato)
- no, è «adesso e presto finisce» → fluttuante (il violinista)

Unica eccezione: una locandina *vaga* — «artisti di strada oggi in centro», senza data —
segnala una condizione temporanea della città, ed è aria di fluttuante.

**Il livello programmato oggi non è ancora costruito** (`:Evento` è un'etichetta predisposta nello
schema ma senza nodi). Le locandine vivono lì: sono il prossimo pezzo, e passano dalla curatela —
perché qualcuno deve leggere la locandina e decidere che è vera.

---

## Nota sui numeri

Tutti i dati di queste slide vengono da `docs/SINTESI_FATTUALE.md`, ricontati o rieseguiti,
mai stimati. I nomi delle relazioni sono quelli veri dello schema Neo4j: se un valutatore
tecnico chiede di vedere il grafo, quello che trova corrisponde alla slide.

## Se hai poco tempo

In plenaria bastano **due slide**: la 23 (la differenza) e la 26 (chi decide).
Le altre quattro sono appendice per chi fa domande — e un deck a cui rispondi *sfogliando*
comunica più sicurezza di uno che scorri tutto.

---

*Scheda di accompagnamento — vedi anche `COME_RACCONTARLO.md` per il copione parlato.*
