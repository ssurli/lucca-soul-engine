# I limiti del motore

Scheda di accompagnamento. Tutto ciò che il sistema **non** fa, verificato nel codice,
con l'indicazione di cosa servirebbe per chiuderlo.

---

## Perché questa scheda esiste

Un documento che non dichiara i propri confini non è credibile davanti a un valutatore
esperto. Chi non ha mai trovato un problema, semplicemente non ha ancora guardato.

**In presentazione questa scheda è un'arma, non una debolezza.** Alla domanda «e questo lo
avete?» la risposta che fa guadagnare è: *«No, e sappiamo perché: è scritto nella nostra
documentazione, con l'indicazione di cosa servirebbe.»*

Ogni voce qui sotto è stata **verificata nel codice**, non ricordata.

---

# PARTE 1 — I difetti del motore

## 1. Gli eventi non hanno alcuna prova di presenza

**Cosa è garantito oggi:** niente. `POST /events` accetta qualunque evento e lo registra.

**Cosa NON è garantito:**
- nessun GPS, check-in, QR o conferma dell'operatore, in nessuna forma
- **nessun codice lato app genera eventi** — `apps/lucca_soul_app` non ha un solo riferimento
  a `BehaviorEvent`; `BffClient` non ha nemmeno un metodo per `POST /events`
- nessuna autenticazione, nessun rate limiting sull'endpoint

**Il punto più serio:** il recommender assegna a `stop` un peso doppio rispetto a `view` perché
significherebbe «presenza fisica reale e prolungata». **Quella semantica non è verificata da
nessun codice.** Il peso più importante del modello poggia su un'assunzione.

**Cosa servirebbe:** una chiave per client noto, un rate limiting, e una decisione di prodotto
sul tipo di prova (vedi Parte 2 — non è una scelta tecnica).

> Prerequisito del Living Lab. Non un miglioramento rimandabile.

---

## 2. La soddisfazione non è misurabile

**Cosa è garantito oggi:** l'evento `review` registra che una recensione è avvenuta.

**Cosa NON è garantito:** se fosse positiva o negativa. Non esiste alcun campo di valutazione,
in nessun punto del sistema. L'unico segnale potenzialmente negativo è `skip`, e nel recommender
ha **peso 0,0** — neutralizzato di proposito («mai un premio per essere ignorato»).

**Conseguenza:** se il sistema propone qualcosa di sbagliato, non lo sa e non lo saprà mai.

**Come è gestito:** l'indicatore `soddisfazione` della dashboard mostra esplicitamente
«non ancora misurabile» — non zero, non vuoto. Un buco dichiarato invece di un numero inventato.

**Cosa servirebbe:** un campo di valutazione esplicito, raccolto da utenti reali. **Non** un
proxy comportamentale travestito da soddisfazione: sarebbe engagement mascherato, esattamente
ciò che il progetto promette di non fare.

---

## 3. La scoperta fuori dal grafo è un vicolo cieco

**Cosa è garantito oggi:** un cittadino può conferire un racconto anche se il grafo è irraggiungibile.

**Cosa NON è garantito:** che quel racconto venga pubblicato. Se `riguarda` punta a un luogo che
non esiste nel grafo, il contributo **non raggiungerà mai `curato = True`** — la curatela verifica
i target. È un vicolo cieco permanente, non una scoperta.

**L'ironia da conoscere:** per un progetto che promette di raccogliere il patrimonio *non
riconosciuto*, la memoria di ciò che nessuno ha ancora catalogato è proprio quella che si perde.

**Cosa servirebbe:** un percorso opposto — «questo racconto riguarda un posto che non c'è;
il curatore può crearlo». Richiede che un curatore esista (vedi Parte 2).

---

## 4. Nessun raggio d'azione, nessuna coordinata

**Cosa è garantito oggi:** la relazione `VICINO` porta i **metri** fra due luoghi collegati, e
l'Experience Engine li converte in minuti a piedi per comporre l'itinerario sul tempo disponibile.

**Cosa NON è garantito:**
- `Luogo` non ha lat/lon — **nessuna coordinata assoluta, in nessun punto del progetto**
- non si può chiedere «cosa c'è entro 300 metri» da un punto qualsiasi: si possono solo seguire
  archi esistenti (38 su 15 luoghi, una rete sparsa)
- un'attività non può dichiarare un'area di servizio
- il parametro `raggio_m` esiste nel codice ma è **dormiente**: sempre `None`, mai popolato —
  ed è un filtro del *visitatore*, non un attributo dell'attività

**Conseguenze pratiche:** la heatmap della dashboard è un'aggregazione per luogo, non una mappa.
E per replicare su un'altra città la rete `VICINO` va ricostruita a mano.

**Decisione presa:** non costruirlo finché non c'è un caso reale che lo forzi. Quando servirà
(un artigiano itinerante, un servizio a domicilio), la risposta minima è l'elenco esplicito dei
luoghi serviti — non un sistema geometrico, sovradimensionato per un pilota su una città.

---

## 5. Orari e disponibilità: solo il minimo

**Cosa è garantito oggi** (implementato dopo la verifica): fasce settimanali ricorrenti su
`ExperienceNode.orari_apertura`, un quinto filtro duro nella composizione dell'itinerario, e il
rifiuto della prenotazione fuori orario *prima* di persistere.

**Cosa NON è garantito:** capienza (`prenotabile` è un booleano, non un contatore), conflitti di
slot, doppie prenotazioni, eccezioni calendariali, festività, turni a cavallo di mezzanotte.

**Lo scarto da conoscere:** il White Paper promette che la piattaforma «gestisce **disponibilità**,
prenotazioni, pagamenti, recensioni e statistiche». Il codice oggi gestisce prenotazioni e
commissioni; disponibilità solo nella forma minima; recensioni no. **La riga del documento va
allineata** — è l'unica cosa che espone davvero in una presentazione.

---

## 6. La distribuzione dei flussi: robusta, non garantita

**Cosa è garantito oggi:** il motore penalizza la concentrazione, e il recommender **migliora** la
distribuzione su quattro scenari storici indipendenti (entropia 0,783 → 0,842 nel caso base).
Il test è in CI: se qualcuno peggiorasse la concentrazione, la build si rompe.

**Cosa NON è garantito:** la correzione è **locale, per singola richiesta**. Non è una garanzia
matematica che su una popolazione di diecimila richieste l'aggregato non peggiori mai. È
robustezza empirica su quattro scenari, non un teorema.

**Cosa servirebbe:** allocazione globale a lotti, o stato condiviso online con minimizzazione del
rimpianto. Settimane di lavoro, probabilmente una fase a sé — con sinergia verso l'Urban
Intelligence Index, che calcola già lo stato aggregato che servirebbe.

---

## 7. Gli eventi non hanno finestra temporale

**Cosa NON è garantito:** il recommender legge `behavior_event` **senza filtro su `ts`** — ogni
riga che entra in quella tabella influenza il ranking per sempre, a prescindere dalla data.

Non esiste un flag `sintetico`, non esiste retention. Un evento di prova altera immediatamente
le raccomandazioni reali.

**Cosa servirebbe:** un flag per escludere i sintetici dall'aggregazione, **oppure** una finestra
temporale nella query di quota storica. Sono soluzioni **ortogonali, non alternative**.

---

## 8. La dashboard non è mai stata compilata

**Cosa è garantito oggi:** il codice Dart esiste, segue le convenzioni del resto dell'app, e i
modelli hanno costruttore privato — il client non può fabbricarsi un `disponibile = true`
aggirando la soppressione.

**Cosa NON è garantito:** nulla di eseguibile. Mai `flutter pub get`, mai `flutter analyze`,
mai `flutter test`. Le icone sono scelte alla cieca, i test scritti ma mai fatti girare.

**Nota:** il vincolo di privacy è comunque protetto, perché vive **al confine dell'API**, non
nell'interfaccia. Un client qualsiasi — Flutter, curl, un'app di terzi — non può ottenere celle
sotto soglia.

---

## 9. Due indicatori con confini dichiarati

**`tasso_ritorno`** misura il ritorno **entro il periodo**, non fra stagioni. Ma il ritorno vero
di un turista è a mesi di distanza: l'indicatore cattura la parte meno significativa del fenomeno.

**`nuovi_percorsi`** è implementato e testato, ma **manca la persistenza degli itinerari**: il
valore va letto come «non ancora misurato», non come zero.

---

## 10. Il CORS è aperto in lettura

Aperto **solo in GET** e limitato agli endpoint `/dashboard/*` — dati già aggregati e anonimizzati
— per far funzionare il viewer HTML locale. Verificato che `OPTIONS` su `POST /events` viene
rifiutato.

**Da restringere a origin specifici prima di qualunque deploy.** Non deve restare un wildcard
dimenticato il giorno che il BFF finisce online.

---

## 11. Il seed è curato, non validato sul campo

Il seed di Lucca contiene fatti largamente noti e plausibili, riconosciuti da chi conosce la
città. Ma **nessun liutaio ha confermato di ispirarsi a Puccini**, e le distanze in metri fra i
luoghi sono stime, non misurazioni.

Adeguato per un proof of concept. Insufficiente il giorno in cui una persona segue quell'itinerario
e trova la bottega chiusa.

---

# PARTE 2 — Chi risolve cosa

Delle criticità sopra, **quattro su sei categorie non si risolvono programmando.**

| | Come si chiude | Quando |
|---|---|---|
| Autenticazione e rate limiting | **codice** — mezza giornata | prima di aprire l'endpoint |
| Generazione eventi dall'app | **codice + Flutter** | con l'app in mano alle persone |
| Prova di presenza | **decisione di prodotto** | col Comune, sul tema privacy |
| Soddisfazione | **persone reali** | Living Lab |
| Scoperta fuori dal grafo | **un ruolo umano** (curatore) | quando il curatore esiste |
| Garanzia aggregata | **ricerca** — una fase a sé | con flussi veri da distribuire |

## Sulla prova di presenza — perché non è una scelta tecnica

Il GPS continuo risolverebbe tutto e **contraddirebbe il progetto**: un sistema che promette
privacy by design e sopprime le celle sotto dieci persone non può tracciare gli spostamenti
individuali. Un DPO comunale lo vedrebbe subito.

Le alternative compatibili, in ordine di forza decrescente:
- **conferma dell'operatore** — la bottega registra il passaggio: la prova più affidabile
- **QR alla bottega** — prova ragionevole, nessun tracciamento continuo
- **check-in volontario** — nessuna prova, ma nessuna intrusione; e un dato che la persona *sa*
  di aver dato è più onesto di una posizione dedotta

**C'è una via d'uscita già disponibile:** il `booking` è una prova migliore dello `stop`. Chi
prenota e riceve conferma ha lasciato una traccia verificata da entrambe le parti. Forse il
segnale forte non è «sono stato lì» ma «ho prenotato e la bottega ha confermato».

---

# PARTE 3 — Come dirlo

## La frase che chiude il tema

> «Abbiamo sei limiti documentati. Quattro si chiudono solo con persone reali in città — ed è
> esattamente per quello che cerchiamo il partner. Gli altri due li chiudiamo noi.»

## Se ti chiedono di un limite specifico

Non difenderti. Confermalo e spiega la scelta:

> «No, non ce l'abbiamo. È scritto nella nostra documentazione dei limiti, con l'indicazione di
> cosa servirebbe. Non l'abbiamo costruito perché non abbiamo ancora un caso reale che lo forzi —
> e preferiamo non modellare vincoli che nessuno ci ha ancora posto.»

## Se ti chiedono dei numeri che non hai

> «Il piano finanziario è in costruzione su dati verificati. Preferisco darvelo dopo che averlo
> inventato adesso.»

## Il principio, se serve dichiararlo

> «Ogni volta che abbiamo dovuto scegliere fra un indicatore vuoto e uno finto, abbiamo scelto
> il vuoto. La dashboard dice "non ancora misurabile" invece di mostrare uno zero. È una scelta
> che si paga in una demo e si ripaga in una verifica.»

---

## Una nota per te

Quattro di questi buchi sono emersi da domande che hai fatto tu, in mezz'ora, dopo aver capito
come funziona il motore. Nessuno era noto prima.

Il valore di chi dirige un progetto non è aver scritto il codice: è saper fare le domande che
lo rompono. Continua a farle — sono la stessa cosa che farà un valutatore, e conviene arrivarci
prima tu.

---

*Fonte: `docs/LIMITI.md` del repository, più le verifiche condotte sul codice.
Vedi anche `LO_SPACCATO_DEL_MOTORE.md` e `COME_RACCONTARLO.md`.*
