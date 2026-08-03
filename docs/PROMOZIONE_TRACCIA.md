# PROMOZIONE_TRACCIA.md — Fase 3: il ledger delle tracce e la promozione fluttuante→permanente

> **Stato del documento: PARZIALMENTE implementato — non più "design, non implementazione"
> in blocco.** Un task successivo a questo design ("fondazione del canale fluttuante:
> persistenza + ledger") ha reso REALE §1 (il ledger delle tracce, tabella
> `traccia_luogo`) e §2(a) (`:Luogo.ultima_traccia_il`, scritta via Cypher versionato) —
> verificato contro il codice, non presunto, stessa disciplina di sempre. **§2(b) (il
> bagliore) e §3 (la pipeline ricorrenza→promozione→dormienza, inclusa la corsia
> fluttuanti `blocked`/`approved`/`rejected` di `docs/STATE_MACHINE.md` §4) restano
> DESIGN PURO, non toccati da quel task** — nessuna riga SQL/Cypher di quella parte è
> eseguibile. Ogni sezione sotto è annotata esplicitamente REALE o DESIGN, non lasciata
> all'inferenza. Fonte del design originario:
> `docs/brief_fase3_promozione_traccia.md` (vincolante, ma il codice lo sovrasta — §0 del
> brief). Questo documento presuppone Fase 1/2 approvate (`docs/STATE_MACHINE.md`) e i due
> invarianti del motore (`docs/ENGINE_INVARIANTS.md`): non li riapre, costruisce sopra.
>
> Prima di disegnare, il brief impone cinque verifiche contro il codice (§3 del brief). I
> risultati, in breve (dettaglio completo nella conversazione che ha prodotto questo
> documento, non ripetuto qui):
>
> 1. Nessun audit dell'`expired` porta già `place_id`+`temi` — `expired` non è implementato,
>    non c'è un log da promuovere. Il ledger è un meccanismo nuovo.
> 2. **Né `Signal` né `SegnaleFluttuante` portano un `creato_il`.** `SegnaleFluttuante` ha
>    `id, descrizione, temi, place_id, non_commerciale` — niente timestamp. `Signal.ora` è
>    un'ora del giorno (`time`), non una data. **Decisione accettata per sciogliere questo
>    (Strada B, vedi §1 sotto): NON si aggiunge un campo a `SegnaleFluttuante`/`Signal` — restano
>    transitori esattamente come da contratto oggi.** Il `creato_il` della traccia è
>    timbrato dal server nel momento di `expired`, non letto dal segnale.
> 3. Nessuna tabella Postgres esistente porta già `place_id`+`temi`: `behavior_event` è il
>    precedente idiomatico più vicino (append-only, chiave surrogata, `TIMESTAMPTZ`) ma non
>    la tabella giusta da cui proiettare una vista — serve una tabella nuova, con la stessa
>    idiomatica.
> 4. `:Evento` esiste già nello schema del grafo (`00_schema.cypher`, constraint di unicità
>    su `id`) ma **riservato e vuoto**: zero nodi nel seed, zero proprietà, zero relazioni.
>    `seed_lucca.py` lo dice esplicitamente: *"`Evento`... nello schema ma non ha seed in
>    questa wave: `Evento` arriva con i segnali reali"* — è il momento per cui era stato
>    preparato.
> 5. Nessuno stato chiuso/dormiente esiste oggi per `:Bottega`/`:Luogo` (entrambe dataclass
>    minime in `seed_lucca.py`, nessun campo di stato). Nessun precedente da riusare per
>    analogia per la dormienza del pattern.

---

## 1. Il ledger delle tracce — forma dati — **REALE, implementato**

**Verificato contro il codice**: `services/urban-memory/sql/01_fluttuante_schema.sql`
(tabella `traccia_luogo`), `services/urban-memory/urban_memory/traccia_repository.py`
(`Traccia`, `TracciaRepository` — doppia implementazione InMemory/Postgres). Il design
sotto è rispecchiato fedelmente dal codice, non solo un piano.

**Anagrafica minima** (brief §5): `place_id`, `temi[]`, `creato_il`. Nient'altro — niente
`contributor`, niente PII, niente testo libero, niente descrizione dell'occorrenza. È il
distillato del passaggio, non un secondo `SegnaleFluttuante` persistito.

- **`place_id`**: stesso spazio di `MemoryContribution.riguarda` — un id che esiste (o è
  esistito) come `:Luogo`/`:Bottega`/`:Artista`. Nessun controllo di esistenza al momento
  del deposito: il fluttuante era già stato validato a monte (pre-check `blocked` nella
  corsia fluttuanti, `STATE_MACHINE.md` §4) quando è diventato `approved`.
- **`temi[]`**: stessa forma di `SegnaleFluttuante.temi` / `ExperienceNode.temi` — riusa
  `experience_engine.rules.affinita_temi`, un solo vocabolario di affinità, mai un secondo
  criterio inventato per la traccia.
- **`creato_il`**: **Strada B** (decisione accettata, scioglie il check 2). Timbrato dal
  SERVER nell'istante in cui l'occorrenza approvata raggiunge `expired` — stesso schema
  concettuale di `behavior_event.ricevuto_il` (timestamp del server, non un istante
  dichiarato dal chiamante). `SegnaleFluttuante`/`Signal` non guadagnano alcun campo:
  restano transitori esattamente come da contratto oggi (nessun tocco a
  `packages/contracts`). Semanticamente corretto, non solo comodo: la traccia data il
  **passaggio-diventato-passato** (il fantasma si stacca dall'occorrenza e si deposita sul
  luogo), non la nascita del segnale — coerente con "place-anchored, non
  occurrence-anchored" (brief §5): al luogo non importa quando l'occorrenza è nata, solo
  che è stata reale (approvata) e ora è storia (scaduta).

**Identità della riga**: nessuna naturale, come `behavior_event` — due tracce identiche in
`place_id`/`temi`/istante restano due passaggi distinti (due violinisti diversi nello
stesso punto nello stesso minuto non sono lo stesso fatto). Chiave surrogata, non una
chiave composta.

**Limite reale trovato durante l'implementazione, non anticipato da questo design**: lo
sweep (`attivo → expired`, atomico) e il deposito della traccia non condividono una
transazione — un fallimento del deposito DOPO che lo sweep ha già committato causa la
perdita PERMANENTE e silenziosa della traccia per quel singolo segnale (isolata dal resto
del batch, non a cascata — trovato e corretto da un giro dedicato di `ethics-guardian`).
Il ledger resta quindi "immortale" per ogni riga che riesce a depositarsi, ma NON garantisce
che ogni segnale scaduto depositi effettivamente la sua riga. Dettaglio completo in
`docs/LIMITI.md`.

**Idiomatica — stessa forma di `behavior_event`, non una vista sopra di esso:**
- Tabella propria, append-only, con la propria migrazione dedicata — stesso pattern delle
  tre corsie esistenti (`recommender.migrate`, `marketplace.migrate`, `urban_memory.migrate`
  hanno ciascuna il proprio schema versionato + comando `migrate`). Questa è una quarta
  corsia, non un'aggiunta dentro una delle tre: non è un evento comportamentale
  (`behavior_event` ha `experience_id`, non un luogo; è ancorato a un'esperienza permanente,
  non a un fluttuante), non è un contributo di memoria (`memory_contribution` porta
  `contributor_id`, esplicitamente escluso qui), non è una prenotazione.
- Solo `CREATE ... IF NOT EXISTS`, nessun `DROP`, rieseguibile da zero in un comando — stesso
  vincolo non negoziabile di CLAUDE.md per ogni schema Postgres del repo.
- Indice per aggregazione-per-luogo (`place_id`): è la query che conta — "tutte le tracce di
  questo `place_id`" — mai una traversata Neo4j.
- Nessuna FK verso il grafo: Neo4j e Postgres restano store separati, nessuna transazione
  condivisa — stesso limite già accettato per `memory_contribution.riguarda`.
- **Confermato dal check §3**: non può essere una vista filtrata su `behavior_event` (che
  non porta né `place_id` né `temi`, e il cui `tipo` è un `CHECK` chiuso su un insieme fisso
  che non include nulla su fluttuanti/tracce) né su `memory_contribution` (porta
  `contributor_id`, esplicitamente vietato dall'anagrafica minima).
- **Collocazione del codice — CHIUSA**: `services/urban-memory` (stesso spirito del white
  paper — "Urban Memory cresce con l'uso": un fluttuante approvato che scade è, in un certo
  senso, un conferimento automatico e anonimo alla memoria del luogo). Decisione presa
  dall'orchestratore al momento dell'implementazione (non un servizio dedicato nuovo),
  coerente con l'istruzione del brief di modellare la persistenza su
  `urban_memory/repository.py` — nuovi moduli `segnale_repository.py`/
  `traccia_repository.py`/`canale_fluttuante.py`/`luogo_traccia_link.py` accanto a quelli
  esistenti, non duplicati altrove.

**Solo occorrenze approvate-e-poi-scadute depositano — PRINCIPIO valido, ma vacuamente vero
oggi.** Le rifiutate: nulla (brief §5, estende "le rifiutate non fanno pattern" di Fase 2 a
"le rifiutate non fanno traccia"). Senza questo confine, occorrenze respinte
"accenderebbero" comunque un luogo mai davvero toccato dal fenomeno. **Nota di
implementazione (non presente nel design originario)**: il codice reale oggi non ha ALCUN
concetto di `rejected` per un segnale fluttuante (`STATE_MACHINE.md` §4 — `blocked`/
`approved`/`rejected` restano design puro, non implementati da questo task) — ogni segnale
persistito dal percorso fidato (`submit_signal.py`) è trattato come implicitamente
approvato, quindi OGNI segnale che scade deposita sempre la sua traccia, incondizionatamente
(`urban_memory.canale_fluttuante.sweep_and_fetch_active`). Il principio "le rifiutate non
fanno traccia" è quindi rispettato per COSTRUZIONE (non esiste ancora un modo di rifiutare),
non per un controllo esplicito nel codice del deposito — quando la revisione umana verrà
costruita, il deposito dovrà diventare condizionato da un vero stato `approved`, non più
incondizionato su ogni `expired`.

## 2. La proprietà derivata sul grafo + il bagliore

Due meccanismi distinti — tenerli separati evita di confonderli in fase di implementazione.
**Stato epistemico diverso tra i due, come per gli invarianti del motore — non
confonderli**: (a) è REALE, (b) resta DESIGN.

### (a) `:Luogo.ultima_traccia_il` — proprietà derivata, un solo scopo — **REALE, implementato**

**Verificato contro il codice**: `services/urban-memory/cypher/40_luogo_traccia_write.cypher`
(un `MATCH`+`SET` puro, MAI un `MERGE` — confermato non crea mai un `:Luogo` inesistente,
verificato anche da un giro dedicato di `ethics-guardian`), `services/urban-memory/
urban_memory/luogo_traccia_link.py` (`Neo4jLuogoTracciaLinker`, stesso pattern di driver
diretto già usato da `graph_link.py`). Il design sotto è rispecchiato fedelmente dal codice.

Serve **esclusivamente** a rilevare la dormienza di un pattern promosso (§3, ANCORA DESIGN)
a costo di lettura zero: "quando ha parlato l'ultima volta questo luogo" senza mai
interrogare Postgres o traversare il grafo. **Nessun consumatore reale ancora** (§3 non è
implementata): la proprietà si aggiorna già ma nessuno la legge oggi per prendere una
decisione — scritta in anticipo per il momento in cui §3 verrà costruita, stesso principio
già visto per la label `:Evento` riservata ma vuota nello schema.

- **Si rinfresca in scrittura**, non in lettura: un `SET` sul nodo `:Luogo` nello stesso
  momento in cui la riga viene appesa al ledger. Due scritture in due store diversi, non una
  transazione distribuita — stessa natura di rischio già accettata altrove nel repo
  (`link_to_graph`/Postgres), non una garanzia nuova da inventare qui.
- Se una delle due scritture fallisce, il ledger (append-only, immortale) resta la fonte di
  verità; `ultima_traccia_il` è una proiezione best-effort, mai l'originale. Una divergenza
  temporanea si autocorregge alla prossima traccia depositata per lo stesso luogo — a
  differenza di `link_to_graph` (che verifica ESISTENZA e quindi richiede atomicità
  stretta), qui non c'è nulla da "esistere": un errore di sincronia produce al più un dato
  stantio, mai un dato invalido.

### (b) Il bagliore — MAI stored, calcolato in lettura

Non una proprietà sul grafo, non una colonna in Postgres. Calcolato al momento del bisogno
da chi lo consuma (candidati: `experience-engine` per scoring/`reason`, `index-engineer` per
un cruscotto — nessuno dei due è deciso o cablato qui, restano consumatori futuri).

**Forma** (non i numeri — brief §4.1 lo chiede esplicitamente come forma):

```
bagliore(luogo, adesso) = Σ [ per ogni traccia di quel place_id ]  peso(adesso − traccia.creato_il)
```

dove `peso` è una funzione monotona decrescente del tempo trascorso **con un pavimento
positivo** — mai zero: ogni traccia contribuisce sempre un residuo non nullo, per quanto
vecchia. Forma illustrativa dello shape (non tuning):

```
peso(Δt) = pavimento + (1 − pavimento) · decadimento(Δt)
```

con `decadimento` una funzione tipo esponenziale o iperbolica — quale delle due, e i valori
di `pavimento`/tasso, sono domande di tuning (§4 sotto), stessa classe di `tasso_ritorno`.

**Perché sommare su TUTTE le tracce e non solo sull'ultima**: un luogo con dieci passaggi
recenti "brilla" più di uno con un solo passaggio, anche se entrambi hanno lo stesso
`ultima_traccia_il`. La doppia natura del ledger (diario + battito, brief §6) richiede due
letture diverse — l'ultimo istante (per la dormienza: binaria, parla ancora o no) e la somma
pesata (per il bagliore: continuo, quanto forte parla).

**"Costo zero" (brief §5) si riferisce al grafo** — nessuna traversata Neo4j per sapere
quanto un luogo è vivo — non a Postgres, dove il costo esiste ma è quello di
un'aggregazione a chiave indicizzata, esattamente il caso d'uso per cui Postgres è scelto.

## 3. La pipeline ricorrenza → promozione → dormienza

**Rilevamento ricorrenza**: sorgente = occorrenze APPROVATE (mai rifiutate, brief §6) di
stessa descrizione/temi/place_id entro una finestra — meccanismo già descritto in
`STATE_MACHINE.md` §4 ("Ricorrenza → promozione"), non riscritto qui. Soglia N e finestra W
restano deliberatamente non decise (§4 sotto).

**Nodo promosso: famiglia `:Evento`** (chiude la domanda 11 di `STATE_MACHINE.md` §7,
check §3.4 del brief) — la label esiste già, riservata da `00_schema.cypher` con un
constraint di unicità su `id`, ma zero nodi, zero proprietà, zero seed. Ancorato al `:Luogo`
esistente tramite una relazione, **non** un nuovo `:Luogo` (la piazza è già un luogo; la
musica ricorrente che vi accade non lo è).

Proprietà proposte (design, non Cypher eseguibile) — **riviste dalla chiusura di
`docs/STATE_MACHINE.md` §4-bis** (item 14 §7, brief §7.2): il modello di dormienza qui sotto
era "invecchiamento assoluto di `ultima_traccia_il`"; è stato sostituito dalla **frizione
automatica a cadenza**, e si è aggiunto un **freno di emergenza** ortogonale, non uno stato.
Dettaglio completo in `docs/STATE_MACHINE.md` §4-bis, non ripetuto qui:

- `ricorrente = true` — costante per un `:Evento` di questa famiglia.
- `cadenza` — il ritmo delle occorrenze che hanno fatto rilevare il pattern come ricorrente
  (es. "ogni sabato"), salvato al momento della promozione. **Campo nuovo, non ancora
  verificato contro il codice**: se il rilevamento ricorrenza (§3 sotto) produce solo un
  conteggio grezzo e non un ritmo, questo campo va popolato esplicitamente alla promozione,
  non dedotto a posteriori — non verificabile oggi perché il rilevamento ricorrenza non
  esiste ancora (`docs/FASE3_VERIFICHE.md`, check 1).
- `stato ∈ {attivo, sospeso, dormiente}` — **non più `ritirato`**: mortale ma
  standing-until-revoked, mai una DELETE (invariante A, brief §2: append-only sui target di
  `riguarda` — un `:Evento` promosso, una volta creato, non sparisce mai, si spegne).
  Transizioni automatiche, sensibili al RITMO (`cadenza`), non al tempo assoluto:
  `attivo → sospeso` dopo K battiti di cadenza mancati; `sospeso → attivo` automatico su
  traccia fresca; `sospeso → dormiente` se la sospensione supera un orizzonte lungo. Gestisce
  nativamente la stagionalità (un pattern annuale vive `sospeso` undici mesi l'anno, mai
  dichiarato morto). K, orizzonte e tolleranza sul ritmo: tuning, non decisi qui
  (`docs/STATE_MACHINE.md` §7 item 12/15).
- `ultima_traccia_il` — stessa proprietà derivata di §2(a), applicata al `place_id`
  d'origine: alimenta la frizione (a) sopra, non più un invecchiamento assoluto isolato.
- **Freno di emergenza — NON una proprietà di `stato`.** Override di sicurezza manuale,
  ortogonale al ciclo di vita sopra, applicabile in qualunque momento indipendentemente da
  `attivo`/`sospeso`/`dormiente`: sopprime la raccomandazione (mai il deposito delle tracce,
  il ledger resta veritiero), tiro e rilascio entrambi manuali (non si auto-rilascia su
  traccia fresca), append-only (ogni tiro/rilascio una riga permanente, motivazione
  obbligatoria, log a salienza massima). Al rilascio il pattern torna allo stato che la
  frizione (a) indica in quel momento, mai forzato ad `attivo`. Livello di autorità:
  **CHIUSO nel principio** — permesso individuale nominale, ristretto a un sottoinsieme di
  Promotori, mai l'intero ruolo; concessione/revoca del permesso stesso tracciata e
  reversibile (append-only), nessun doppio-occhio sul singolo tiro (restrizione
  sull'accesso, non sulla procedura). Residuo di dettaglio implementativo (chi amministra la
  lista) — `docs/STATE_MACHINE.md` §7.14.1, item 16. Dettaglio completo:
  `docs/STATE_MACHINE.md` §4-bis(b).

**Relazione di ancoraggio: `SI_SVOLGE_A` — CHIUSO contro il codice, non una proposta.**
Verificato l'intero `services/graph/cypher/01_seed_lucca.cypher`: nel seed esistono
esattamente sette tipi di relazione — `LEGATO_A` (7), `VICINO` (3), `OFFRE` (5),
`SI_SVOLGE_A` (22), `EVOCA` (65), `ISPIRATA_DA` (non ancora contata sopra ma presente),
`HA_ABBONAMENTO` (3). Di queste, una sola porta la semantica "questo accade/si trova qui":
`SI_SVOLGE_A` (`:Esperienza -[:SI_SVOLGE_A]-> :Luogo`, derivata da `ExperienceNode.place_id`
in `seed_lucca.py`). Le altre due candidate sono ESCLUSE per motivo esplicito nel codice, non
per assunzione:
- `LEGATO_A` (Artista→Luogo) è **riservata per iscritto** a un'altra semantica — il commento
  di `RelazioneIspirataDa` in `seed_lucca.py:157-159` lo dice testualmente: *"non `LEGATO_A`
  che è riservato ad Artista->Luogo"* — un legame biografico/artistico, non un ancoraggio
  spaziale generico. Riusarlo per `:Evento` confonderebbe due fatti diversi sotto lo stesso
  verbo.
- `Bottega.place_id` **non produce nemmeno una relazione**: è un campo validato per
  esistenza (`assert bottega.place_id in luoghi_ids`) ma mai materializzato come arco nel
  grafo — non è un precedente di "ancoraggio", è un caso a parte (una bottega non ha bisogno
  di un arco per essere trovata per luogo, la query dei candidati passa da `place_id` come
  proprietà, non da una traversata).

`:Evento` è, nella forma, la stessa cosa di `:Esperienza`: un'attività che accade a un
`:Luogo` che esiste già, non il luogo stesso. Riusare `SI_SVOLGE_A` non è un'analogia
comoda: è la stessa relazione applicata alla stessa forma di fatto — un solo modo di
intendere "accade qui" (CLAUDE.md, "un solo modo di intendere"), non un verbo parallelo
introdotto per l'occasione. Nessuna nuova decisione di `graph-architect` da prendere su
QUALE relazione usare — resta solo l'implementazione (fuori scope qui, design non tocca
Cypher).

**Dormienza — automatica, da FRIZIONE A CADENZA, CHIUSA** (brief §6, chiusura in
`docs/STATE_MACHINE.md` §4-bis(a) — sostituisce questo paragrafo nella sua forma originaria
"invecchiamento assoluto di `ultima_traccia_il`"): l'`:Evento` promosso porta con sé la
propria `cadenza` (il ritmo delle occorrenze rilevate come ricorrenti), salvata alla
promozione. `attivo → sospeso` dopo **K battiti di cadenza mancati** (non un tempo assoluto);
`sospeso → attivo` automatico su una traccia fresca; `sospeso → dormiente` se la sospensione
supera un orizzonte lungo. Nessuna sveglia separata, nessun job che "controlla se è morto":
la cadenza mancata stessa — letta al bisogno o da un batch periodico, dettaglio
implementativo non deciso qui — È il segnale, come nel modello originario; cambia solo COSA
si misura (battiti di ritmo, non giorni). Ogni transizione loggata (brief §1.4: anche
l'automatico logga chi/quando/perché — chi=sistema, perché="K battiti mancati" /
"sospensione oltre orizzonte"). **Perché il cambio rispetto al modello originario**: un
tempo assoluto tratterebbe un pattern stagionale (es. un mercatino annuale, undici mesi di
silenzio ogni anno per costruzione) come morto ogni anno — la cadenza lo riconosce invece
come "in pausa attesa", non "cessato". Dettaglio completo, coi tre stati e i numeri non
decisi (K, orizzonte, tolleranza): `docs/STATE_MACHINE.md` §4-bis(a).

**Retroattività: si dissolve** (brief §6, confermato dal check §3.2) — le occorrenze
approvate non persistono come nodi (spariscono a `expired`, lasciando solo una traccia
anonima nel ledger). Non c'è nulla sotto il pattern promosso da riscrivere. Ciò che resta
della "storia" che ha portato alla promozione è **provenance**, non topologia: quali righe
del ledger (place_id + temi + intervallo di `creato_il`) hanno determinato la rilevazione di
ricorrenza — un fatto di audit (loggabile nella transizione `ricorrente`, già previsto da
`STATE_MACHINE.md` §4: "quali occorrenze l'hanno determinata"), mai un arco nel grafo verso
occorrenze che non esistono più come nodi.

**Ritiro manuale — CHIUSA** (brief §7.2, `docs/STATE_MACHINE.md` §4-bis(b)): non un "ritiro"
che sposta il pattern in un nuovo stato terminale (bozza abbandonata), ma un **freno di
emergenza** — override di sicurezza, ortogonale alla frizione sopra, non una voce di
`stato`. Tiro e rilascio entrambi manuali (non si auto-rilascia su traccia fresca, a
differenza della frizione), immediato, sopprime solo la raccomandazione (il ledger continua
a ricevere tracce normalmente), append-only con motivazione obbligatoria e log a salienza
massima. Al rilascio il pattern torna allo stato che la frizione indica in quel momento, mai
forzato ad `attivo`. Scoped a motivi di sicurezza/legale/immediatezza: usarlo perché "il
pattern è finito" è un uso improprio, quello è compito della frizione. **Livello di
autorità: CHIUSO nel principio** (`docs/STATE_MACHINE.md` §7.14.1, item 16) — permesso
individuale nominale concesso a un sottoinsieme ristretto di Promotori, mai l'intero ruolo,
con concessione/revoca tracciata e reversibile e nessun doppio-occhio sul singolo tiro.
Resta solo un residuo di dettaglio implementativo (chi amministra concretamente la lista dei
permessi), stessa classe di tuning di K/orizzonte/tolleranza sopra — non una decisione di
governance ancora da prendere.

## 4. Integrazione nella macchina a stati — riga esplicita, non bullonata

Fatto in `docs/STATE_MACHINE.md` §4 direttamente (non ripetuto qui): il diagramma della
corsia fluttuanti ora mostra `expired` come terminale **con effetto collaterale
condizionato**, non più "nessuna scrittura" come accettato in Fase 2:

- occorrenza **mai approvata** (mai decisa, o rifiutata) che raggiunge `expired` → nessuna
  scrittura, esattamente come prima.
- occorrenza **approvata** che raggiunge `expired` (la sua finestra si chiude comunque, con
  lo stesso orologio) → deposita una riga nel ledger (§1), timbrata dal server in
  quell'istante.

La transizione di stato (loggata per accountability, brief §1.4: chi=sistema, quando,
perché) e la riga del ledger (anonima, senza contributor, brief §5) sono **due record
distinti con due scopi distinti** — non confonderli: uno è audit della macchina a stati,
l'altro è il diario del luogo. `STATE_MACHINE.md` §6 li tiene ora come due righe separate
nella tabella dei due assi di autorità.

## 5. Domande ancora aperte — sollevate, non risolte

Tenute anche in `docs/STATE_MACHINE.md` §7 (items 12, 15 aperti; 14 e 16 CHIUSE nel
principio, con solo un residuo di tuning/dettaglio implementativo) per restare in un solo
posto consultabile insieme alle altre domande della macchina a stati:

1. **Soglia N e finestra W** per il rilevamento della ricorrenza — stessa classe di
   `tasso_ritorno`, si fissa quando c'è il dato reale.
2. ~~**Override manuale del ritiro pattern**~~ **CHIUSA** (`docs/STATE_MACHINE.md` §4-bis):
   non un override generico, ma due meccanismi distinti — frizione automatica a cadenza
   (§3 sopra) e freno di emergenza (§3 sopra).
2-bis. ~~**§7.14.1 — livello di autorità del freno di emergenza**: intero ruolo Promotore o
   sottoinsieme ristretto?~~ **CHIUSA nel principio** — permesso individuale nominale,
   ristretto, mai l'intero ruolo, concessione/revoca tracciata e reversibile, nessun
   doppio-occhio sul tiro (stessa domanda di `docs/STATE_MACHINE.md` §7 item 16, non
   duplicata in due forme diverse). Il residuo (chi amministra la lista) è dettaglio
   implementativo, ripiegato nel tuning dell'item 3 sotto — non una domanda di design a sé.
3. **Forma della curva di decadimento — disegnata qui (§2b); i numeri no**: tasso di
   decadimento, valore del pavimento, soglia di invecchiamento per la dormienza — E ORA
   ANCHE K (battiti mancati per sospendere) e l'orizzonte lungo (sospeso→dormiente) della
   frizione a cadenza (§3, §4-bis(a) di `docs/STATE_MACHINE.md`), E chi amministra la lista
   dei permessi-freno (§7.14.1) — stessa classe di tuning/dettaglio implementativo, non
   struttura.
4. ~~**Collocazione del codice del ledger**: `services/urban-memory` o un servizio nuovo
   dedicato?~~ **CHIUSA** — `services/urban-memory` (§1 sopra), decisione presa
   dall'orchestratore al momento dell'implementazione, non da questo documento di design.
5. **Chi consuma il bagliore** (§2b): `experience-engine` per lo scoring/`reason`,
   `index-engineer` per un cruscotto, entrambi, nessuno dei due ancora — non deciso, resta
   un consumatore futuro. Nota per quando si deciderà: `ENGINE_INVARIANTS.md` §3 registra
   oggi che `Signal.eventi_attivi` non altera mai lo score di un'esperienza permanente —
   se il bagliore entrasse nello scoring, quell'invariante andrebbe riverificato esplicitamente,
   non presunto ancora valido.

## 6. Scenario concreto — una giornata, un ciclo di vita

Non tassonomia astratta (disciplina brief §8): un violinista suona in Piazza Napoleone ogni
sabato sera per sei settimane di fila.

1. **Sabato 1**: qualcuno segnala il fluttuante (canale di sottomissione ancora non
   esistente, `docs/LIMITI.md` — assunto qui che arrivi già com'è). Un Guardiano lo approva
   (`submitted → approved`). Il motore lo usa per comporre itinerari quella sera. A
   mezzanotte la finestra scade: **era approvato** → `expired` deposita una traccia
   `(place_id=piazza-napoleone, temi=[musica-di-strada], creato_il=sabato 1, 00:00)`.
   `:Luogo(piazza-napoleone).ultima_traccia_il` si aggiorna allo stesso istante.
2. **Sabati 2-6**: stesso ciclo, cinque tracce in più — stesso `place_id`, stessi `temi`,
   `creato_il` diversi. Nessun nodo nuovo nel grafo: sei occorrenze, sei righe di ledger,
   zero topologia aggiuntiva.
3. **Rilevamento ricorrenza** (soglia N/finestra W, non decise qui): sei occorrenze
   approvate, stesso pattern, entro sei settimane → `ricorrente`, loggata (chi=sistema,
   quali occorrenze — o quali tracce — l'hanno determinata).
4. **Promozione**: un Promotore la promuove. Nasce
   `(:Evento {id, ricorrente=true, stato=attivo, cadenza=settimanale})-[:SI_SVOLGE_A]->
   (:Luogo{id=piazza-napoleone})` — la `cadenza` (settimanale) è salvata qui, alla
   promozione (`docs/STATE_MACHINE.md` §4-bis(a)). Nessuna occorrenza passata viene
   riscritta: restano solo le sei righe di ledger e la transizione `ricorrente` come
   provenance.
5. **Le settimane successive**: il violinista continua. Ogni sabato scaduto approvato
   deposita una nuova traccia; `ultima_traccia_il` di Piazza Napoleone resta fresca; il
   bagliore calcolato in lettura resta alto (molte tracce recenti pesano molto).
6. **Il violinista smette gradualmente** (semplicemente si stanca). Il sabato 8 non si
   presenta: un battito di cadenza mancato. Se salta anche il sabato 9 (K=2, per fissare
   un'idea — non deciso davvero, §5 item 3), `:Evento(piazza-napoleone-violinista).stato:
   attivo → sospeso`, automatico, loggato (`docs/STATE_MACHINE.md` §4-bis(a)) — non ancora
   `dormiente`: la frizione a cadenza non tratta due sabati saltati come morte del pattern.
   Se il violinista tornasse un sabato successivo, `sospeso → attivo` automatico, nessun
   intervento del curatore. Ma non torna: la sospensione supera l'orizzonte lungo (non
   deciso) → `sospeso → dormiente`, automatico, loggato. Il nodo resta nel grafo — non è mai
   stato cancellato, solo spento. Il bagliore calcolato in lettura, nel frattempo, è
   scivolato verso il pavimento (mai zero): le vecchie tracce sbiadiscono, non si
   seppelliscono — il luogo "ricorda debolmente" anche molto tempo dopo che il fenomeno è
   tornato silenzioso.
7. **Variante — il Comune vieta i busker con effetto immediato, sabato 4** (invece del
   ritiro graduale sopra): il pattern è ancora `attivo` (nessun battito mancato), ma un
   Promotore con **permesso-freno** (uno dei pochi della lista nominale, non l'intero ruolo)
   tira il **freno di emergenza** (`docs/STATE_MACHINE.md`
   §4-bis(b)) — immediato, motivazione obbligatoria ("ordinanza comunale n. …, busker
   vietati da oggi"), loggato a salienza massima. Il motore smette di raccomandare la tappa
   fluttuante da quel momento. Se qualcuno segnalasse comunque un'occorrenza sabato 5 e un
   Guardiano (per errore, o perché non a conoscenza del freno) la approvasse, la sua traccia
   si depositerebbe comunque a `expired` — il ledger resta veritorio, il freno non lo tocca.
   Il freno resta tirato finché qualcuno non lo rilascia esplicitamente: non si spegne da
   solo neanche se passano mesi di silenzio. Al rilascio, il pattern non torna `attivo` per
   default — torna a ciò che la frizione (a) indica in quel momento: se nel frattempo sono
   mancati abbastanza battiti da giustificare `sospeso`, è `sospeso` che riemerge.

## 8. Cosa questo documento NON è

Non è uno schema SQL (`packages/contracts`/`services/*/sql` restano gli unici posti dove uno
schema è reale), non è Cypher, non è un endpoint HTTP, non è una modifica ai contratti
esistenti (`SegnaleFluttuante`/`Signal` restano esattamente come sono — Strada B lo impone
esplicitamente). Prima di implementare qualunque pezzo: `contract-keeper` per la forma dati
del ledger (se emerge un contratto condiviso), `graph-architect` per la relazione di
ancoraggio e le proprietà di `:Evento`, `ethics-guardian` prima di ogni merge che tocchi
scoring/reason se e quando il bagliore entra in `experience-engine`, `test-engineer` per il
ciclo di vita sopra come test di integrazione — nessuna eccezione rispetto a ogni altra wave
di questo repository.
