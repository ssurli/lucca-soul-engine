# Brief vincolante — Fase 3: Promozione & Traccia (Lucca Soul Lab)

## 0. REGOLA META — leggila prima di tutto, sovrasta ogni altra regola qui sotto

Questo brief è vincolante, **ma il codice del repository lo sovrasta.** Se una qualunque costante qui sotto contraddice ciò che il codice fa davvero, **FERMATI e segnalalo** — non riconciliare in silenzio, non adattare la realtà alla specifica. La forza di questo ciclo è stata verificare *per assenza, contro il codice*, non per assunzione. Diverse costanti di questo brief derivano da assunzioni sul motore che vanno confermate (vedi §3): trattarle come vere prima della verifica sarebbe un errore.

Questo brief **non riapre Fase 1 né Fase 2.** Entrambe sono approvate. Qui si progetta il livello Promozione & Traccia, sopra la macchina a stati già validata.

---

## 1. CONGELATO — ereditato da Fase 1/2, non ridiscutere

1. **`submit_contribution` non verifica mai i target.** Il muro sta alla pubblicazione, non al conferimento (Wave 2, nel codice).
2. **Lo pseudonimo resta pseudonimo.** `contributor_id` mai in chiaro come identità.
3. **Rifiuto esplicito = stato di prima classe con reason category.** Rifiutato ≠ dimenticato.
4. **Ogni transizione di stato logga chi/quando/perché — anche le automatiche.** Una transizione system-detected (es. rilevamento ricorrenza) va comunque registrata: §1.4 non fa eccezione per l'automatico.
5. **Gate consenso-terzi: strutturale, non un flag.** Per un item a rischio-terzi, l'arco verso `approved` è *rimosso dall'insieme delle mosse legali*, non controllato a runtime. Chi aggiunge automazione futura costruisce le transizioni disponibili PARTENDO da questa esclusione.
6. **`link_to_graph` è atomico — tutto-o-niente.** Verifica tutti gli id di `riguarda` prima di scrivere; se ne manca uno, non scrive nulla. L'aggancio parziale non è uno stato producibile.

**Decisioni nuove, chiuse nel giro di progettazione, ora congelate:**

7. **`approved → agganciato` è AUTOMATICO** — esecuzione di sistema, non autorità umana. L'approvazione ha già giudicato l'esistenza dei target; agganciare è la coda meccanica di quella decisione. **Conseguenza load-bearing:** "curato ma non agganciato" cessa di essere uno stato di riposo raggiungibile in produzione — diventa un transitorio, o un `aggancio_fallito` esplicito se Aura è irraggiungibile. Questo *chiude* il bug curato-ma-orfano rendendolo non producibile, non gestendolo.

---

## 2. INVARIANTI DEL MOTORE — scoperti in questo ciclo, da annotare FUORI da questo documento

Questi due fatti sono emersi progettando il curatore ma sono verità del **motore**, vere a prescindere dalla Fase 3. Vanno in un `ENGINE_INVARIANTS.md` (o equivalente), non solo qui:

- **A — Append-only sui target di `riguarda`.** Nessun percorso di codice applicativo cancella `:Luogo`/`:Bottega`/`:Artista`. Unica rimozione nel repo: un comando manuale in un README che colpisce solo `:Memoria` orfane. Il grafo, per i tipi che `riguarda` referenzia, è append-only.
- **B — Curato tira aggancio** (dal §1.7): ogni `approved` innesca il proprio `link_to_graph`.

Questi due invarianti sono **vincoli di progettazione** per la Fase 3: qualunque cosa disegni deve rispettarli, non aggirarli.

---

## 3. VERIFICA PER PRIMO — precedenza §0, prima di disegnare qualunque cosa

Cinque check contro il codice. **Non progettare finché non li hai stabiliti.** Se uno contraddice una costante congelata, fermati e segnala.

1. **L'audit dell'`expired` porta già `place_id` + `temi`?** Se sì, il ledger delle tracce (§5) è quasi un sottoprodotto: promuovi un log già scritto da "interno operativo" a "diario del luogo", non crei un meccanismo nuovo.
2. **Il `Signal`, al momento della transizione a `expired`, ha ancora i temi in mano?** Il design dichiara il segnale transitorio: conferma che al momento dello scadere i tre campi (`place_id`, `temi`, `creato_il`) siano ancora disponibili da scrivere, non già svaniti.
3. **Esiste in Postgres/Neon un ledger di audit naturale**, di cui la traccia possa essere una vista/proiezione filtrata (solo `expired`, solo da approvati) — o serve tabella nuova?
4. **`:Evento` esiste già come tipo di nodo, e con quale lifecycle?** L'agente l'ha nominato in Fase 2 ("`:Evento` programmato") ma non è confermato reale. Se esiste con uno stato, la promozione ci si appoggia; se non esiste, il tipo è genuinamente nuovo.
5. **Esiste già uno stato "chiuso/inattivo/dormiente"** per `:Bottega` o `:Luogo` (es. una bottega che chiude non sparisce, viene marcata chiusa) da riusare per il ritiro del pattern? Se sì, il ritiro non è un meccanismo nuovo — è lo stesso.

I check 2, 4 e 5 possono spostare la forma della soluzione. Il check 2 in particolare **scioglie la questione retroattività** (§6): se le occorrenze approvate non persistono come nodi, non c'è nulla da riscrivere sotto il pattern promosso.

---

## 4. COSA DEVI PRODURRE — e nient'altro

La Fase 3 è **design**, non implementazione. NON scrivere schema SQL eseguibile, Cypher, o codice. Se una scelta è impossibile senza toccare il codice, segnalala come vincolo.

1. **Il ledger delle tracce** (forma dati): `(place_id, temi[], creato_il)`, append-only, in Postgres, place-anchored. La **proprietà derivata** sul nodo grafo (`vitalita` o `ultima_traccia_il`) e come/quando si rinfresca. La **forma** della funzione di decadimento del bagliore (la *forma*, non i numeri).
2. **La pipeline ricorrenza → promozione → dormienza**: il rilevamento della ricorrenza, il tipo `:Evento` creato e come si ancora al `:Luogo`, il meccanismo di dormienza da silenzio-del-ledger.
3. **L'integrazione pulita nella macchina a stati**: `expired` deposita traccia — riga esplicita nel diagramma, non bullonata sopra (vedi nota §7).
4. **Le domande ancora aperte**: sollevate, non risolte per decreto.

---

## 5. VINCOLI SUL MECCANISMO-TRACCIA

- **Solo occorrenze approvate-e-poi-scadute depositano traccia. Le rifiutate: nulla.** La traccia è il residuo di qualcosa di genuino ma transitorio, non di spazzatura. Estende la regola già stabilita in Fase 2 ("le rifiutate non fanno pattern"): non fanno pattern *e* non fanno traccia. Senza questo confine, dieci finti busker pubblicitari "attiverebbero" una piazza mai visitata dalla musica.
- **La traccia è anagrafica minima:** `place_id`, `temi[]`, `creato_il`. NIENTE `contributor`, NIENTE PII, NIENTE testo libero, NIENTE descrizione dell'occorrenza. È il distillato del passaggio, spogliato di ciò che era personale e transitorio.
- **Il ledger vive in Postgres, NON nel grafo.** Migliaia di tracce come nodi gonfierebbero Neo4j senza beneficio di traversata (non si traversa *da* una traccia — si aggregano per luogo). Aggregazione-per-chiave = Postgres. Il grafo resta pulito; il `:Luogo` porta al più una **proprietà derivata** che proietta il bagliore graph-side a costo zero.
- **Il ledger è immortale** — append-only, nessuna traccia cancellata mai (coerente con invariante A). Il **bagliore** invece si calcola con **decadimento temporale in lettura**: pesa le tracce recenti, lascia sbiadire le vecchie a un chiarore debole che **non arriva mai a zero**. Non seppellisci, non cancelli, non evanesci — sbiadisci senza sparire. Questo è "aleggia" fatto di interi.
- **La traccia è place-anchored, non occurrence-anchored.** Lo spirito non aleggia sull'occorrenza morta (quella scade, giustamente) — aleggia sul Luogo, che *ricorda di essere stato visitato*. Il fantasma non ha bisogno di un tempio, ha bisogno di un'impronta.

---

## 6. VINCOLI SULLA PROMOZIONE

- **Solo occorrenze APPROVATE fanno pattern** (mai le rifiutate — un segnale respinto ripetutamente è spam, semmai un allarme, non una promozione).
- **`ricorrente` è un fatto sul PATTERN, non sull'occorrenza.** Anche se system-detected, la transizione si logga (§1.4).
- **Il nodo promosso è famiglia `:Evento`, ancorato al `:Luogo` esistente — NON `:Luogo`.** La piazza è già un Luogo; la musica ricorrente non è un luogo, è un evento che vi accade. Se sia `:Evento` con proprietà (`ricorrente=true`, `stato=attivo`) o un tipo nuovo si decide contro il codice (check §3.4).
- **Permanente ma MORTALE — standing-until-revoked, non eterno, non evanescente.** Un pattern può morire (i busker smettono, il mercatino trasloca). Ma un nodo evanescente che sfarfalla dentro-e-fuori violerebbe l'invariante append-only. Il ritiro è quindi un **cambio di stato** (marcato dormiente/ritirato), non una rimozione — parente stretto della bottega che chiude senza sparire dal grafo.
- **Retroattività — probabilmente si dissolve.** La domanda "le occorrenze già approvate vengono riscritte sotto il pattern promosso?" dipende dal check §3.2: se le occorrenze approvate NON persistono come nodi (svaniscono a `expired`), non esiste nulla da ri-agganciare. Resta solo la **provenance** della promozione (quali occorrenze l'hanno determinata) — che è audit, non topologia.
- **Dormienza da silenzio del ledger.** Un `:Evento` promosso i cui passaggi si diradano smette di accumulare tracce fresche: `ultima_traccia_il` invecchia. Quell'invecchiamento *è* il segnale di dormienza — nessun curatore deve dichiarare morto un pattern, nessuna sveglia separata. Stessa meccanica del decadimento del bagliore, applicata al lifecycle. Il ledger fa doppio servizio: memoria del luogo *e* battito che segnala quando un pattern tace.

---

## 7. DOMANDE DA LASCIARE APERTE — sollevare, non decretare

1. **Soglia N e finestra W** per il rilevamento della ricorrenza. Se non decise ora, dichiarale della stessa classe di `tasso_ritorno` (si fissano quando c'è il dato reale, non a tavolino).
2. **Override manuale del ritiro pattern.** La dormienza è *solo* da silenzio-del-ledger (automatica), oppure il curatore può anche ritirare a mano un pattern che sa morto (es. il Comune ha vietato i busker) *prima* che il ledger taccia? È una decisione di prodotto del committente — sollevala, non risolverla.
3. **Forma esatta della curva di decadimento** del bagliore (tuning, non struttura). Ometti i numeri, definisci solo la forma.

---

## 8. DISCIPLINA DA MANTENERE + ORDINE DI LAVORO

Disciplina (invariata da Fase 1/2):
- Separa visibilmente il vero-oggi dal prospettico.
- Verifica per assenza, contro il codice.
- La prova è uno **scenario concreto** (una "giornata" o un ciclo di vita narrato: un'occorrenza nasce, scade, deposita traccia; un luogo si accende; un pattern viene promosso, poi tace e va dormiente) — non tassonomia astratta.

Ordine:
1. Le cinque verifiche §3 (precedenza §0). Se qualcosa contraddice il congelato, **fermati e segnala** prima di disegnare.
2. Il ledger + proprietà derivata + forma del decadimento (§4.1, §5).
3. La pipeline promozione + dormienza (§4.2, §6).
4. L'integrazione nella macchina a stati (§4.3): **nota bene** — `expired` non è più "terminale, nessuna scrittura" come accettato in Fase 2. Ora è terminale **con effetto collaterale** (deposita traccia *se e solo se* l'occorrenza era approvata). È un cambiamento reale rispetto alla macchina approvata: rientralo pulito, non bullonato sopra.
5. Le domande aperte (§7), sollevate e non risolte.
