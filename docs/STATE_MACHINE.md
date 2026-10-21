# STATE_MACHINE.md — la macchina a stati del CURATORE (design, non implementato)

> **Stato del documento: DESIGN, non codice.** Nessuno stato qui sotto esiste come colonna
> in `memory_contribution`, nessun endpoint HTTP lo espone, nessuna authority level è
> cablata. Questo file trascrive fedelmente il design discusso attraverso Fase 1 e Fase 2,
> incluse le correzioni fatte durante la progettazione stessa (una assunzione iniziale del
> brief — §3 sotto — si è rivelata falsa contro il codice ed è stata ritirata: la lascio
> visibile invece di riscrivere la storia, perché il metodo — verificare, non presumere —
> è parte del contenuto). **Se il codice cambia, questo documento va riverificato, non
> aggiornato per analogia.**
>
> Per i fatti verificati sul motore delle esperienze (non sulla curatela), vedi
> `docs/ENGINE_INVARIANTS.md` — perimetro diverso, non duplicato qui.
>
> **Eccezione al "design, non codice" del titolo — SEI pezzi, non più cinque.** L'invariante B
> (`approved → agganciato` automatico, Fase 3 Task 1), la **fondazione persistenza+ledger
> della corsia fluttuanti** (Fase 3, task successivo: persistenza di `SegnaleFluttuante`,
> sweep pigro `attivo → expired`, deposito della traccia, `:Luogo.ultima_traccia_il`), il
> **rilevamento pattern ricorrenti + promozione a `:Evento`** (Fase 3, task successivo:
> `urban_memory.ricorrenza`/`promozione_evento`/`curatela_pattern`/`cestino_repository`), la
> **frizione automatica a cadenza** (`attivo ⇄ sospeso → dormiente`,
> `urban_memory.frizione_pattern`, comando `python -m urban_memory.frizione_pattern` — QUESTA
> NOTA diceva finora, erroneamente non aggiornata, che restava design puro: corretto qui), il
> **consumo degli `:Evento` promossi in un itinerario reale**
> (`experience_engine.engine._aggiungi_tappe_eventi_promossi`, letto dal grafo dal BFF e
> passato a `compose_itinerary` come nuovo tipo condiviso `contracts.EventoPromosso`) e il
> **freno di emergenza, v1 MINIMA** (`urban_memory.freno_pattern`, comando `python -m
> urban_memory.freno_pattern tira|rilascia` — verificato da un giro DEDICATO di
> `ethics-guardian`, due passaggi: un FAIL iniziale su un bug reale — `attore` non validato
> prima di scrivere, poteva produrre un `:Evento` frenato senza riga di audit — poi PASS dopo
> la correzione) sono passati da design a **codice reale**. §0 e §4 sotto sono stati
> riverificati e riscritti contro il codice per riflettere i primi due — ciascuno con una nota
> esplicita di cosa è reale e cosa resta design (§4: vedi "REALTÀ vs DESIGN" più sotto, subito
> dopo il diagramma della corsia fluttuanti); il terzo, il quarto e il quinto hanno la propria
> nota REALTÀ vs DESIGN nella sezione "Ricorrenza → promozione" più sotto in questo file (il
> quarto anche in §4-bis(a)) e in `docs/PROMOZIONE_TRACCIA.md` §3; il sesto (il freno) ha la
> propria nota REALTÀ vs DESIGN in §4-bis(b) sotto e in `docs/PROMOZIONE_TRACCIA.md` §3.
> Tutto il resto del documento (`blocked`/`deferred`/`rejected` della corsia principale, le tre
> uscite dal target fantasma, `blocked`/`approved`/`rejected` della corsia fluttuanti, la lista
> nominale dei permessi-freno e il grant/revoke — §7.14.1, ancora residuo implementativo APERTO)
> resta design puro, invariato.
> Dettaglio delle sei implementazioni e delle loro verifiche: `docs/ENGINE_INVARIANTS.md`
> §11-B (invariante B) e `docs/PROMOZIONE_TRACCIA.md` (nota di apertura + §3, persistenza+
> ledger, rilevamento+promozione, frizione, consumo e freno).
>
> **Fase 3 (Promozione & Traccia, `docs/brief_fase3_promozione_traccia.md`)** ha chiuso tre
> punti che questo documento lasciava aperti — §7.1 (`approved → agganciato`, ora
> automatico), §7.11 (tipo dell'entità promossa, ora `:Evento`) e §7.14 (il ciclo di vita del
> pattern promosso dopo la promozione, chiuso con DUE meccanismi distinti — frizione
> automatica a cadenza e freno di emergenza, §4-bis sotto; una prima bozza di questa
> chiusura, un "ritiro manuale" generico, è stata **abbandonata**, non congelata) — e ha
> aggiunto un effetto collaterale a `expired` nella corsia fluttuanti (§4 sotto). §7.14.1
> (item 16 in §7, il livello di autorità del freno) è **CHIUSA anch'essa nel principio**:
> permesso individuale nominale, ristretto a un sottoinsieme di Promotori, mai l'intero
> ruolo — resta solo un residuo di dettaglio implementativo (chi amministra la lista),
> stessa classe di tuning degli item 12/15, non una domanda di design ancora aperta. Il
> design esteso (ledger delle tracce, bagliore, pipeline ricorrenza→promozione→dormienza)
> vive in `docs/PROMOZIONE_TRACCIA.md`, non duplicato qui: questo file resta la macchina a
> stati, quello il meccanismo che si aggancia a `expired`.

## 0. Punto di partenza — cosa fa la curatela OGGI (verificato nel codice, non assunto)

- **`submit_contribution`** (dietro `POST /memory`): valida consenso/licenza/pseudonimo,
  forza `curato=False` a prescindere da cosa arriva, **non verifica mai i target nel
  grafo** — il conferimento resta sempre possibile anche ad Aura in pausa.
- **`curate_contribution`** (alias `publish_pending`): l'UNICA funzione che porta
  `curato=True`. Prende un `target_checker` opzionale (tipicamente
  `Neo4jMemoryLinker.targets_mancanti`): se un id in `riguarda` non esiste come
  `:Luogo`/`:Bottega`/`:Artista`, solleva `InvalidTargetsError` e **non scrive nulla**.
  Verifica SOLO esistenza — non crea mai un nodo mancante. **Aggiornato in Fase 3**: prende
  anche un `linker` opzionale — se fornito, incatena l'aggancio al grafo (sotto) subito
  dopo `curato=True`, nello stesso passo. `target_checker=None`/`linker=None` (i default)
  riproducono il comportamento pre-Fase-3, riservato ai test di dominio puri.
- **Cosa scrive esattamente** (letto testualmente in entrambe le implementazioni, non
  presunto):
  ```python
  # InMemoryMemoryRepository.curate
  aggiornato = corrente.model_copy(update={"curato": True})
  # PostgresMemoryRepository.curate
  "UPDATE memory_contribution SET curato = true WHERE id = %(id)s RETURNING ..."
  ```
  Un booleano, nessun'altra colonna — QUESTO passo specifico (`repo.curate`) non è
  cambiato. **Ma se `curate_contribution` ha ricevuto un `linker`**, appena dopo scrive
  anche `stato_aggancio` (colonna reale, non più solo design: `AGGANCIATO`/
  `AGGANCIO_FALLITO`) tramite `repo.set_stato_aggancio` — vedi punto successivo.
- **L'aggancio al grafo — CHIUSO IN CODICE (Fase 3), non più "esiste ma altrove".**
  `urban_memory.graph_link.link_to_graph()` (o `Neo4jMemoryLinker.link()`) resta la SOLA
  funzione che scrive `MERGE (m:Memoria)-[:RIGUARDA]->(target)`, ma ora è incatenata
  automaticamente a `curate_contribution` quando questa riceve un `linker` (seam unico
  `_innesca_aggancio`, `service.py:256`, condiviso da entrambe le implementazioni del
  repository). **Percorso di produzione reale oggi**: `urban_memory/verify.py`, passo 3
  (non più passo 5) — passa `linker=linker.link` insieme a `target_checker`, condividendo
  lo stesso `Neo4jMemoryLinker` aperto una volta in `main()`. Il passo 5 non fa più il
  PRIMO aggancio: dimostra invece che `retry_link_contribution` è idempotente su un
  contributo già `AGGANCIATO` e recupera un `AGGANCIO_FALLITO`/legacy `None`. **Nessun
  endpoint HTTP** invoca ancora `curate_contribution` con un `linker` reale — l'automazione
  è vera per costruzione SOLO per chi lo passa esplicitamente, non per ogni chiamante
  futuro (stessa disciplina già richiesta per `target_checker`). Dettaglio verificato:
  `docs/ENGINE_INVARIANTS.md` §11-B.
- **`_link_transaction` è atomica per costruzione**, non per convenzione: verifica TUTTI
  gli id di `riguarda` in una sola transazione Neo4j (`execute_write`); se anche uno solo
  manca, solleva `MemoryLinkError` **prima** di scrivere qualunque cosa. L'aggancio
  parziale non è uno stato che il meccanismo attuale può produrre.
- **`pending_contributions`**: lista grezza (`list_pending()`), nessun ordinamento, nessuna
  vista aggregata.
- **`audit`** (CLI, sola lettura): scova contributi *già* curati i cui target sono nel
  frattempo spariti — segnala, non corregge.
- **Cosa NON esiste, verificato per assenza**:
  - Nessun endpoint HTTP per curatela — solo `POST /memory` e `GET /memory/{place_id}`.
  - Scarto esplicito solo per i non curati; i curati restano senza rifiuto. Un contributo
    NON curato può essere scartato con un motivo obbligatorio (`MemoryRepository.scarta`,
    `scripts/scarta_contributo.py`, colonne `scartato_il`/`motivo_scarto` di
    `sql/05_scarto_schema.sql`): mai DELETE, la riga resta; sparisce da `list_pending`,
    `list_curated`, `get_curated` e quindi dall'Index; `get(id)` la restituisce ancora e
    `curate` su uno scartato fallisce. Lo scarto di un curato non esiste (non c'è un "ritiro"
    della pubblicazione): un curato che non va resta curato. Lo stato di scarto è interno al
    repository, non è nel contratto `MemoryContribution`.
  - Nessuna creazione di nodi — la curatela blocca se un target manca, non offre "crealo".
  - Nessuna promozione — il concetto fluttuante→permanente non esiste in nessuna forma.
  - Nessun log della DECISIONE UMANA oltre lo stato booleano finale — non c'è "chi, quando,
    perché" per `curato=True` in sé (item 2 in §7 sotto, ancora aperto). **Eccezione
    puntuale, Fase 3**: la transizione AUTOMATICA `approved → agganciato`/
    `aggancio_fallito` (quando `linker` è passato) È loggata (chi=sistema, quando, esito —
    mai il contenuto del contributo) — non colma il buco sulla decisione umana, che resta
    aperto, ma non è più vero che "nessuna transizione" logghi qualcosa.
- **Il grafo è append-only per i target di `riguarda`** (verificato con un grep dell'intero
  repo per `DETACH DELETE|DELETE \(|REMOVE \(|DROP CONSTRAINT`): una sola occorrenza in
  tutto il repository, in `services/urban-memory/README.md` — un comando Cypher
  documentato per pulizia manuale una tantum (non codice eseguibile), che colpisce SOLO
  nodi `:Memoria` orfani, MAI `:Luogo`/`:Bottega`/`:Artista`. Conseguenza per il design
  sotto: una race "il target esisteva quando è stato approvato, non esiste più quando si
  aggancia" **è impossibile via codice applicativo** in questo repository (resta
  teoricamente possibile solo fuori dal codebase, via accesso diretto a Neo4j Browser —
  un rischio di governance dell'accesso, non una proprietà della macchina a stati).

## 1. Fase 1 — la coda come esperienza (non un nuovo schema)

### Cosa aspetta una decisione oggi vs in prospettiva

| Tipo | Curabile OGGI | Perché |
|---|---|---|
| Contributi di Urban Memory | **Sì** | `pending_contributions()`/`curate_contribution()` esistono |
| Segnali fluttuanti da verificare | **No** | nessun meccanismo li mette in coda; `Signal` è transitorio, non persiste |
| Luoghi proposti fuori dal grafo | **No** | un contributo con target inesistente si blocca in eterno oggi |
| Fluttuanti ricorrenti da promuovere | **No** | il concetto non esiste |

### Ordinamento della coda principale — non FIFO

Due criteri, in quest'ordine, entrambi già coerenti con principi applicati altrove nel
motore (nessun criterio nuovo inventato per l'occasione):

1. **Rompe il silenzio di un luogo** — un contributo il cui target ha oggi zero
   contributi curati sale in cima (stesso principio di distribuzione/attivazione locale
   già cablato nel motore: sbloccare il primo racconto su una bottega minore vale più che
   aggiungere il decimo su un luogo già raccontato).
2. **Anzianità**, dentro quella fascia.

I segnali fluttuanti (§4) romperebbero questo ordine con una priorità temporale assoluta,
diversa dai contributi di memoria che non scadono — motivo per cui vivono in una corsia
separata (§4), non iniettati qui.

## 2. §0 — la correzione di provenienza (tenuta visibile, non riscritta)

Il brief di Fase 2 assumeva (§3 originaria): *"l'approvazione multi-target scrive
topologia — la curatela multi-target è già un atto sul grafo."* **Verificato falso** contro
il codice (vedi §0 sopra): `curate_contribution` e `link_to_graph` sono due atti separati,
nessun percorso li incatena automaticamente. **§3 è stata ritirata**; la macchina sotto
tratta `approved` e `agganciato` come **due transizioni di prima classe distinte**, non una
sola.

## 3. La macchina a stati — corsia principale (versione finale)

```
submit_contribution (ESISTE)
        │
        ▼
   "submitted"  (consenso/licenza/pseudonimo già validati; target NON ancora controllati)
        │
        │  pre-check automatico, sola lettura (stesso target_checker esistente,
        │  spostato PRIMA nel ciclo di vita invece che solo al click)
        │
   ┌────┴────┐
   ▼         ▼
[tutti i    [≥1 id manca]
 target          │
 esistono]       ▼
   │         "blocked"  — precalcolato, mai un'eccezione a runtime
   │              │
   │      per OGNI id mancante in riguarda (grana di SINGOLO id,
   │      non di contributo — l'aggancio è tutto-o-niente, quindi
   │      blocked deve risolversi id per id):
   │      ┌───────┼────────┬─────────────────┐
   │      ▼       ▼        ▼                 ▼
   │   crea    redirect  rimuovi da      (nessuna risoluzione:
   │   nodo    a nodo    riguarda         resta in blocked,
   │  (COSTRUT-esistente (Guardiano)      visibile, non forzato)
   │   TORE)  (Guardiano)
   │      │       │        │
   │      └───────┴────┬───┘
   │                    ▼
   │         riguarda residuo, tutti id verificati esistenti
   │                    │
   │           [riguarda vuoto?] ──sì──► "rejected" (contributo intero,
   │                    │no                non una singola voce)
   │                    ▼
   └──────────────► "submitted"  (rientra pulito, target validi)
                         │
        ┌────────┬───────┼────────┐
        ▼        ▼       ▼        ▼
    approved  rejected deferred  flag "richiede_revisione_umana" = True
   (Guardiano) (+reason  (esplicito,  (settabile in QUALUNQUE stato
               category)  NON risale   non-terminale; MAI azzerato;
                          per anzianità vedi §5 — rimuove transizioni,
                          — vive in una  non le "controlla")
                          mensola propria,
                          vedi §3-bis)
        │
        ▼
   [link_to_graph — stesso target_checker, seconda lettura nel tempo]
        │
   ┌────┴────┐
   ▼         ▼
"agganciato"  "aggancio_fallito"
(terminale,    (unica causa possibile in questo repository:
 :Memoria +     infrastrutturale — Aura irraggiungibile durante
 :RIGUARDA       la seconda lettura. La race "target sparito nel
 scritti)        frattempo" è impossibile via codice applicativo,
                 vedi §0. Risoluzione: APERTA — vedi §6.1)
```

### Perché il redirect non è un rifiuto

`blocked → redirect` corregge `riguarda` verso un id **esistente** — il contributo resta
esattamente quello che era, cambia solo l'etichetta a cui si aggancia. Livello
**Guardiano**, non Costruttore: non crea nulla di nuovo nel grafo, corregge un riferimento
a qualcosa che già c'è — stesso ordine di potere di "approva".

### §3-bis — `deferred`, l'uscita che mancava

Nella prima stesura `deferred` aveva un ingresso e nessuna via d'uscita — "pending per
sempre" con un nome più educato. Corretto così:

- **Non rientra nella lista principale per anzianità** (rimbalzerebbe ogni mattina).
- **Vive in una mensola propria**, visitata deliberatamente dal curatore, mai iniettata
  nell'ordinamento automatico — stesso principio strutturale della corsia fluttuanti
  (§4), applicato qui a un problema diverso (non scadenza, ma "non voglio deciderlo ora").
- **Uscita**: `deferred → submitted` (richiamo esplicito, un'azione del curatore) oppure
  direttamente a un terminale (`approved`/`rejected`) dalla mensola stessa.
- **Ordinamento al rientro** (proposta, non fatto acquisito): riprende la `creato_il`
  originale, non la data del richiamo — per non penalizzare il contributore per il tempo
  di riflessione del curatore.
- **Deliberatamente omesso**: un richiamo automatico per tempo (`deferred_until`) — non
  c'è un caso reale che lo richieda oggi, coerente con "non sovra-modellare".

### Il flag `richiede_revisione_umana` — non uno stato

Un vincolo di compliance permanente (es. il contributo cita per nome una terza persona)
non può vivere in uno *stato*, perché uno stato normale si **lascia**; la garanzia
sparirebbe alla transizione successiva. È modellato come flag monotono (mai azzerato una
volta impostato), impostabile dal curatore in qualunque stato non-terminale, in qualunque
momento prima di un terminale. Il suo funzionamento **strutturale** (non un semplice
controllo runtime) è approfondito in §5.

## 4. La corsia dei segnali fluttuanti (entità separata dai contributi di memoria)

### Perché una corsia separata, non un'iniezione per priorità nella lista unica

Alternativa concreta considerata e scartata: iniettare i fluttuanti nella lista unica con
un termine che pesa il tempo residuo alla scadenza.

- L'ordinamento della lista principale (rompe-il-silenzio, poi anzianità) confronta cose
  che **non decadono** — il loro valore è permanente o cresce nel tempo. Un fluttuante ha
  un valore che **si azzera**. Non esiste un cambio-valuta onesto tra "questo conta per
  sempre" e "questo conta per i prossimi 20 minuti".
- Un fluttuante iniettato con priorità alta (perché sta per scadere) salterebbe
  sistematicamente in cima, spostando in basso proprio i contributi "rompi-il-silenzio" —
  la lista unica proteggerebbe **meno**, non di più, i luoghi minori: l'esatto obiettivo
  che quell'ordinamento esiste per servire, vanificato dalla stessa iniezione pensata per
  "aiutare".
- Costo cognitivo reale: un curatore che scorre una lista mista deve ricalibrare il
  giudizio riga per riga ("è urgente-perché-permanente o urgente-perché-scade?").
- Ibrido scartato (iniettare solo sotto una soglia di tempo residuo): introduce un terzo
  comportamento da imparare per un guadagno senza un caso reale a giustificarlo.

**Decisione: due corsie, entrambe SEMPRE visibili** (mai una dietro una scheda nascosta,
altrimenti il fluttuante scade prima di essere notato — lo stesso problema, mascherato).
Corsia fluttuanti pinnata in alto: il costo residuo diventa "un'occhiata in più", non "un
contesto da ricostruire".

### Macchina a stati della corsia fluttuanti

```
submit — CHIUSO IN CODICE per la sola PERSISTENZA (Fase 3, fondazione
        persistenza+ledger), NON per la revisione sotto (blocked/
        approved/rejected restano design puro, vedi nota **REALTÀ vs
        DESIGN** più sotto): `SegnaleFluttuante` persiste ora in
        Postgres (`services/urban-memory/urban_memory/
        segnale_repository.py`), invocabile da `python -m
        urban_memory.submit_signal` — un percorso RISTRETTO/FIDATO
        provvisorio, stesso principio di `link_to_graph` chiamato solo
        da `verify.py` (Task 1). NESSUN endpoint HTTP pubblico ancora:
        quello resta la "fase fiducia" (prova di presenza, auth, rate
        limit — `docs/LIMITI.md`), non implementata qui.
   │
   ▼
"submitted"  (descrizione/temi/place_id/non_commerciale dichiarati;
              porta con sé un orologio — CHIUSO: `valido_fino`, per
              singolo segnale, non un timer globale condiviso — ma
              QUANTO debba durare tipicamente resta una decisione di
              prodotto non presa, item 7 in §7 sotto)
   │
   │ pre-check automatico: place_id esiste come Luogo/Bottega/Artista?
   │   ANCORA APERTO (item 8 in §7): nessun codice valida
   │   `SegnaleFluttuante.place_id` contro il grafo, né alla
   │   persistenza né altrove — un `place_id` inventato persiste
   │   comunque, oggi.
   │
┌──┴──┐
▼     ▼
[sì]  [no]
 │     ▼
 │  "blocked" — STESSA meccanica a tre uscite (crea/redirect/rifiuta)
 │             della corsia principale, MA in tensione con l'orologio:
 │             creare un nodo è una decisione da Costruttore, presa
 │             normalmente con calma — qui il segnale può scadere
 │             prima che qualcuno con quel livello la prenda.
 │             TENSIONE STRUTTURALE, non risolta: le due corsie
 │             condividono la meccanica di risoluzione del target
 │             fantasma ma non condividono il tempo disponibile.
 │     │
 │     ├─── risolto (crea/redirect) ───► torna a "submitted"
 │     └─── non risolvibile in tempo ──► "expired"
 │
 ▼
┌────────┬──────────┐
▼        ▼          
approved rejected  (nessuna azione entro la finestra ──► anch'essa expired, sotto)
(Guardiano) (+reason
            category)
   │        │
   │        └──────────────────────────────┐
   │  (clock: `valido_fino <= now`,          │
   │   per singolo segnale — CHIUSO, non     │
   │   più "stesso orologio per tutti")      │
   ▼                                          ▼
"expired"  (automatico — ma CLOCK-BASED è oggi LAZY, non un job: la
           transizione avviene IN LETTURA, alla prima `POST
           /itinerary` successiva alla scadenza — `sweep_scaduti`,
           `urban_memory.segnale_repository`. Vedi nota REALTÀ vs
           DESIGN sotto per cosa esattamente è codice reale qui.
           SEMPRE in audit — mai silenzioso — nel senso che deposita
           sempre una traccia se il segnale era attivo, MAI nel senso
           di un log "chi/quando/perché" della transizione stessa,
           che oggi non esiste)
   │
   │  effetto collaterale, condizionato da COME si è arrivati qui
   │  (Fase 3, `docs/PROMOZIONE_TRACCIA.md` — non più "nessuna scrittura"
   │  come accettato in Fase 2: `expired` ora biforca sul proprio passato)
   │
┌──┴──────────────────────┐
▼                          ▼
[l'occorrenza era         [l'occorrenza NON era mai stata
 "approved" prima          "approved" — mai decisa, o "rejected"]
 di scadere]                     │
   │                             ▼
   ▼                      NESSUNA scrittura (come in Fase 2:
deposita UNA riga nel      un'occorrenza mai approvata non lascia
ledger delle tracce        traccia — §5 del brief: "le rifiutate
(place_id, temi,           non fanno traccia", estende "le
creato_il — timbrato       rifiutate non fanno pattern" di Fase 2)
dal SERVER: `valido_fino`
del segnale (UTC, non
l'istante dello sweep),
automatico,
in `services/urban-memory`
(collocazione CHIUSA,
Fase 3 — non più
"o servizio dedicato"),
vedi PROMOZIONE_TRACCIA §1)
```

**REALTÀ vs DESIGN in questa corsia — non confonderli leggendo il diagramma sopra.** La
fondazione persistenza+ledger (Fase 3) ha reso reale SOLO un sottoinsieme stretto di questa
macchina, verificato nel codice (`services/urban-memory/urban_memory/{segnale_repository,
canale_fluttuante,traccia_repository,luogo_traccia_link}.py`):

- **Reale**: `submit` (persistenza, `stato=ATTIVO` di default), `attivo → expired` (lazy,
  innescato da `POST /itinerary` — mai un job/cron, vedi `docs/LIMITI.md`), il deposito
  della traccia su quella transizione, la proprietà derivata `:Luogo.ultima_traccia_il`.
- **NON reale, ancora design puro**: `blocked` (nessun `target_checker` su `place_id` —
  item 8 sotto), `approved`/`rejected` da un Guardiano — **non esiste nel codice nessuno
  stato diverso da `ATTIVO`/`EXPIRED`**. Ogni segnale che entra dal percorso fidato
  (`submit_signal.py`) è trattato come implicitamente approvato: non c'è un gate di
  revisione umana da superare, la fiducia è tutta nel percorso ristretto della CLI, non in
  una decisione di un Guardiano. Conseguenza per il principio "solo le approvate
  depositano traccia, le rifiutate non lasciano nulla" (§5 del brief, ancora valido come
  PRINCIPIO): oggi è vero per COSTRUZIONE, non per APPLICAZIONE — non esiste ancora un
  `rejected` da cui distinguersi, quindi ogni segnale scaduto deposita sempre la sua
  traccia, senza eccezioni, perché non c'è ancora un modo di rifiutarne uno.

Quando la revisione umana (`blocked`/`approved`/`rejected`) verrà costruita, questa nota va
riverificata — non aggiornata per analogia — e il deposito della traccia dovrà diventare
condizionato da un vero stato `approved`, non più incondizionato.

`expired` è deliberatamente **distinto** da `rejected`: uno è un giudizio sul contenuto,
l'altro è un fatto di processo (nessuno è arrivato in tempo). Confonderli nasconderebbe un
problema di capacità del team dietro una metrica di qualità dei contenuti.

**Nessun `agganciato` in questa corsia**, per scelta esplicita: un'occorrenza approvata non
scrive nulla nel grafo AL MOMENTO DELL'APPROVAZIONE — resta un fatto di runtime (il motore
la usa per una composizione di itinerario). A differenza di quanto valeva in Fase 2, però,
non "scompare" senza lasciare traccia: quando la sua finestra si chiude (`expired`), se era
approvata deposita l'anagrafica minima nel ledger (sopra) — un fatto in Postgres, non nel
grafo (il ledger non è topologia, è diario del luogo, `docs/PROMOZIONE_TRACCIA.md` §1). La
promozione (sotto) resta l'unica che scrive struttura PERMANENTE nel grafo (`:Evento`); il
ledger è il fatto che rende quella promozione possibile da rilevare.

### Ricorrenza → promozione

```
occorrenze APPROVATE (mai quelle rifiutate — un segnale respinto
ripetutamente è spam, non un pattern da promuovere: merita semmai
un allarme, non una promozione) di stessa descrizione/temi/place_id,
entro una finestra
   │
   │  rilevamento automatico (soglia N e finestra: NON decise —
   │  stessa classe di scelta già rimandata altrove nel progetto)
   ▼
"ricorrente" — fatto sul PATTERN, non su una singola occorrenza;
               anche se system-detected, la transizione va comunque
               registrata (chi=sistema, quando, quali occorrenze
               l'hanno determinata) — l'accountability non fa
               eccezione per le transizioni automatiche
   │
┌──┴──┐
▼     ▼
"promosso"          "ignorato"
(Promotore — crea   (il pattern resta noto ma non diventa permanente;
 un'entità PERMANENTE le occorrenze future continuano a essere curate
 nel grafo: famiglia  individualmente sulla corsia normale —
 `:Evento`, ANCORATA   "ignorato" non tocca retroattivamente le
 al `:Luogo` esistente occorrenze già approvate)
 — non un nuovo
 `:Luogo` — CHIUSO dal
 check §3.4 del brief
 Fase 3: la label
 esiste già nello
 schema del grafo,
 riservata ma vuota,
 vedi `docs/
 PROMOZIONE_TRACCIA.md`
 §3)
   │
   │  ciclo di vita ordinario dopo la promozione — CHIUSO (§4-bis
   │  sotto): frizione automatica a cadenza, non più un singolo
   │  invecchiamento assoluto di `ultima_traccia_il`
   ▼
"attivo" ⇄ "sospeso" → "dormiente"    (§4-bis(a) — battiti di
                                        cadenza mancati, non tempo
                                        assoluto; gestisce la
                                        stagionalità nativamente)
```

**REALTÀ vs DESIGN in questo diagramma — non confonderli.** Un task successivo a questo
design ("rilevamento pattern ricorrenti + promozione :Evento + cestino") ha reso reale un
tratto di questa sequenza, verificato contro il codice:

- **Reale**: il rilevamento automatico e la transizione `candidato → "promosso"` (via
  `python -m urban_memory.curatela_pattern`, un Promotore decide esplicitamente — mai
  automatica) e `candidato → "cestinato"` (equivalente REALE di "ignorato" sopra, con un
  nome diverso: si scrive nel cestino permanente, `pattern_cestinato`, invece di restare un
  fatto non tracciato — vedi `docs/PROMOZIONE_TRACCIA.md` §3). La sorgente delle occorrenze è
  il ledger delle tracce (§1 di `PROMOZIONE_TRACCIA.md`), non — come immaginato da questo
  diagramma originario — le occorrenze "approvate" della corsia fluttuanti (quella
  distinzione `approved`/`rejected` per il singolo segnale non esiste ancora, vedi sotto).
- **Divergenza dal principio "anche se system-detected, la transizione va comunque
  registrata"** (`§5` di questo file, il testo del diagramma sopra lo dice esplicitamente
  per "ricorrente"): il rilevamento reale (`urban_memory.ricorrenza.rileva_candidati`) è una
  funzione PURA, senza log applicativo del fatto "il sistema ha rilevato questo pattern come
  ricorrente, in base a queste occorrenze" — solo le due transizioni UMANE successive
  (promosso/cestinato) sono loggate. Limite dichiarato, non bloccante, non chiuso da questo
  task: vedi `docs/LIMITI.md` e `docs/PROMOZIONE_TRACCIA.md` §3.
- **NON reale, resta design puro**: `"ignorato"` come stato distinto da "cestinato" (nel
  codice reale un rifiuto è sempre permanente, non esiste una terza via "resta noto ma non
  promosso, senza cestinarlo"); l'intero ciclo `"attivo" ⇄ "sospeso" → "dormiente"` (§4-bis
  sotto, frizione automatica a cadenza) e il freno di emergenza; la distinzione
  `approved`/`rejected` per il singolo SEGNALO fluttuante (§4 sopra) — il rilevamento reale
  legge il ledger così com'è, senza poter escludere un'occorrenza "mai rivista da un
  Guardiano" da una "genuinamente approvata", perché quella distinzione non esiste ancora a
  monte.

Nessuno stato `"ritirato"` in questa sequenza: il freno di emergenza (§4-bis(b)) è un
override ortogonale, non una quarta voce di `stato` — dettaglio completo sotto.

## 4-bis. Il ciclo di vita del pattern promosso — CHIUSA (brief §7.2, item 14 §7)

Chiude con **due meccanismi distinti**, non un singolo "ritiro manuale" come una prima bozza
di questa chiusura ipotizzava (**abbandonata**, non congelata — non vive altrove in questo
repo). Uno è il ciclo di vita ORDINARIO di ogni pattern promosso (automatico, sempre attivo);
l'altro è un override di SICUREZZA (manuale, eccezionale, ortogonale al primo). Non vanno
confusi né nella forma né nell'autorità che li governa.

### (a) Frizione automatica a cadenza — il ciclo di vita normale

> **REALTÀ vs DESIGN — Un task successivo a questo design ("verifica §0 — frizione, sola
> lettura" + implementazione conseguente) ha reso REALE il calcolo e l'applicazione della
> transizione, verificato contro il codice**: `urban_memory.frizione_pattern` (comando
> `python -m urban_memory.frizione_pattern`), funzione pura `calcola_transizione`, query
> `cypher/60_eventi_ricorrenti_read.cypher` (lettura)/`61_frizione_stato_write.cypher`
> (scrittura, `MATCH`+`SET` puro, mai un `MERGE`). Verificato con un giro DEDICATO di
> `ethics-guardian` (PASS con riserva — un problema numerico reale nei default trovato e
> corretto in questa stessa collaborazione, vedi sotto), non un'autovalutazione.
> **Due deviazioni CONCRETE dal design sotto, da conoscere prima di leggerlo**:
> (1) il clock del pattern (l'ultima occorrenza) NON è una proprietà scritta sul nodo
> `:Evento` — si CALCOLA ogni volta dal ledger Postgres (`TracciaRepository.
> occorrenze_per_pattern`, nuovo metodo, filtrato per `place_id`+`temi` esatti del pattern),
> per non accoppiare l'hot path di `/itinerary` (dove le tracce vengono depositate,
> `urban_memory.canale_fluttuante.sweep_and_fetch_active`) a un lookup su `:Evento`; (2)
> **`sospeso → attivo` NON è "automatico non appena arriva una traccia fresca"** come il
> design originario sotto ipotizzava — avviene SOLO quando `python -m
> urban_memory.frizione_pattern` viene rieseguito e trova un'occorrenza abbastanza recente:
> un pattern può restare `sospeso` più a lungo di quanto la sola cadenza indicherebbe se il
> comando non gira con regolarità. Dichiarato esplicitamente nel modulo, non nascosto — vedi
> `docs/LIMITI.md` per il dettaglio completo di questa e altre deviazioni. Il comando resta
> un batch RISTRETTO/FIDATO (nessuna auth, nessun rate limiting, invocato manualmente),
> MAI raggiungibile da `/itinerary` o dall'Experience Engine — verificato per assenza di
> import incrociati.

Sostituisce il modello iniziale di `docs/PROMOZIONE_TRACCIA.md` §3 ("`ultima_traccia_il`
invecchia oltre una soglia assoluta → `dormiente`") con un modello sensibile al **ritmo** del
pattern, non al tempo assoluto:

- Il pattern promosso salva la propria **cadenza** (il ritmo delle occorrenze che lo hanno
  fatto rilevare come ricorrente — es. "ogni sabato") al momento della promozione. **REALE**:
  `e.cadenza_giorni` (float, media giorni tra occorrenze consecutive — non una mediana né
  l'ultimo intervallo), scritta da `promozione_evento_cypher` alla promozione — vedi
  `docs/FASE3_VERIFICHE.md`/`docs/PROMOZIONE_TRACCIA.md` §3 per la chiusura di questo punto.
- **`attivo → sospeso`**: dopo **K battiti mancati** della cadenza attesa — non un numero di
  giorni assoluto. Un pattern settimanale che salta due sabati e uno mensile che salta due
  mesi attraversano la stessa soglia *logica* (K battiti), non la stessa soglia in giorni.
  **REALE**: `K_BATTITI_SOSPENSIONE` (default 2, dichiarato tuning di partenza).
- **`sospeso → attivo`**: **REALE, ma solo a corsa del comando** (vedi nota REALTÀ vs DESIGN
  sopra) — non "non appena arriva una traccia fresca" come ipotizzato qui sotto in origine:
  automatico nel senso che nessun curatore decide, ma non istantaneo rispetto al deposito
  della traccia.
- **`sospeso → dormiente`**: se la sospensione supera un **orizzonte lungo** (assoluto, non
  in battiti — a un certo punto anche un pattern annuale va dichiarato dormiente se non si
  ripresenta più). **REALE, con una correzione rispetto al design originario**: l'orizzonte
  NON è una costante fissa indipendente dalla cadenza (una soglia fissa avrebbe dichiarato
  `dormiente` un pattern annuale quasi subito dopo essere entrato in `sospeso` — bug trovato
  da `ethics-guardian` sui valori di default iniziali, corretto prima della chiusura) — è
  `max(ORIZZONTE_DORMIENZA_GIORNI, K_ORIZZONTE_DORMIENZA * cadenza_giorni)`: un pavimento
  assoluto (180 giorni, per le cadenze cortissime) combinato con un multiplo della cadenza
  stessa (per le cadenze lunghe, dove il pavimento da solo sarebbe insufficiente).
- **Gestisce nativamente la stagionalità**: un pattern annuale (es. un mercatino di Natale)
  vive `sospeso` per undici-dodici mesi ogni anno senza mai essere dichiarato morto — il
  modello precedente (invecchiamento assoluto di `ultima_traccia_il`) lo avrebbe spento ogni
  anno, confondendo "stagionale" con "cessato" — lo stesso errore concettuale che
  `docs/LIMITI.md` documenta altrove per `tasso_ritorno` (finestra sbagliata = fenomeno
  travisato). **Verificato ora anche numericamente** (non solo concettualmente): con i
  default reali, un pattern annuale entra in `sospeso` a ~730 giorni e in `dormiente` solo
  oltre ~1095 giorni — circa una cadenza intera di margine, non un istante.
- **Numeri**: K (battiti mancati per sospendere), l'orizzonte assoluto e il suo moltiplicatore
  di cadenza (per dormire da sospeso) hanno ora valori REALI di partenza nel codice
  (`K_BATTITI_SOSPENSIONE=2`, `ORIZZONTE_DORMIENZA_GIORNI=180.0`,
  `K_ORIZZONTE_DORMIENZA=3.0`), dichiarati esplicitamente tuning da calibrare sul pilota, non
  definitivi — stessa classe di scelta già rimandata per la soglia N/finestra W della
  ricorrenza (§7 item 12) e per la curva di decadimento del bagliore (§7 item 15, ancora
  design puro). La **tolleranza sul ritmo** (quanto una cadenza può slittare prima di
  contare come "mancata") resta invece NON implementata: `calcola_transizione` non ha un
  parametro di tolleranza, solo il rapporto esatto giorni-trascorsi/cadenza.

### (b) Freno di emergenza — override di sicurezza, non uno stato — CHIUSA (§7.14.1)

> **REALTÀ vs DESIGN — v1 MINIMA implementata, verificata contro il codice, non presunta.**
> `urban_memory.freno_pattern` (comando `python -m urban_memory.freno_pattern tira|rilascia`)
> ha reso REALE l'overlay: nuova proprietà `e.frenato` sul nodo `:Evento` (`cypher/
> 62_freno_stato_write.cypher`, `MATCH`+`SET` puro, mai `MERGE`, mai `e.stato` — ortogonalità
> verificata sia da lettura sia da test AST/parametrici sulla query eseguita), separata per
> costruzione dallo `stato` scritto dalla frizione (a): nessuna delle due query tocca la
> proprietà dell'altra. La catena di lettura (`cypher/60_eventi_ricorrenti_read.cypher` →
> `EventoRicorrente.frenato` → `services/api/api/main.py`) porta il flag fino al filtro di
> consumo in `POST /itinerary`, ora `stato == 'attivo' and not frenato` — lettura pura, nessun
> `SET` raggiungibile dal path `/itinerary` (verificato con un guard AST dedicato: il BFF non
> importa mai i moduli di scrittura del freno). Tabella Postgres `pattern_frenato`
> (append-only, **nessun vincolo UNIQUE** — il freno è ripetibile, ogni tiro/rilascio è una
> riga nuova), doppia implementazione InMemory/Postgres. **Motivazione testuale obbligatoria
> su ogni `tira`** (validata PRIMA di qualunque scrittura, nessuna scrittura né sul grafo né
> sulla tabella se assente/whitespace). Verificato da un giro DEDICATO di `ethics-guardian`,
> due passaggi: **FAIL iniziale** su un bug reale — la stessa guardia esisteva per
> `motivazione` ma non per `attore`, e poiché la scrittura sul grafo precede quella di audit,
> un `attore` vuoto poteva produrre un `:Evento` frenato SENZA alcuna riga di audit
> recuperabile (con Postgres: il grafo scrive, poi il CHECK `pattern_frenato_attore_check`
> rigetta l'INSERT e il comando esce lasciando il freno tirato senza traccia di chi/quando/
> perché; con InMemory, ancora più silenzioso: nessun errore affatto). Corretto aggiungendo la
> stessa guardia (`not attore or not attore.strip()`) prima di ogni scrittura in
> `tira_freno`/`rilascia_freno`; **PASS** dopo la correzione, riverificato (righe esatte
> confermate, guardie simmetriche, test che asseriscono esplicitamente l'assenza di scritture
> su entrambi i canali). Suite `services/urban-memory`: 272 passed, 71 skipped (ambientali,
> Postgres non disponibile in questa sessione), 0 failed — eseguita e riconfermata
> dall'orchestratore, non solo riportata dall'agente.
>
> **NON reale, resta design puro (v1 deliberatamente minima)**: la lista nominale dei
> permessi-freno e il meccanismo di grant/revoke (§7.14.1, item 16 sotto — residuo
> implementativo, non principio ancora aperto). Il percorso oggi è **fidato/CLI provvisorio**,
> stesso principio già in uso per `curatela_pattern.py`/`frizione_pattern.py`/
> `submit_signal.py`: nessuna auth, nessun rate-limit, chi ha accesso alla shell è, per
> costruzione, fidato — non un buco nuovo, la stessa postura già accettata altrove in questa
> fase (`docs/LIMITI.md`). Il "nessun doppio-occhio" e la "distinguibilità in audit" restano
> quindi verificati SOLO al livello tecnico (query, tabella, test) — non al livello di
> governance (chi ha materialmente accesso alla CLI), che resta un residuo dichiarato, non
> implementato.

Ortogonale al ciclo di vita (a): **non** una quarta voce di `stato`, un overlay applicabile
in qualunque momento indipendentemente da dove il pattern si trovi (`attivo`/`sospeso`/
`dormiente`).

- **Permesso individuale, non capacità del ruolo — il PRINCIPIO, deciso.** Il freno non è
  esercitabile da chiunque abbia il ruolo Promotore: è un potere ristretto a un sottoinsieme
  NOMINALE, modellato come permesso concesso a persone specifiche, non come proprietà del
  livello. Un Promotore senza il permesso-freno vede l'azione (nell'interfaccia, nel modello)
  ma **l'esecuzione gli è negata** — l'azione esiste, il potere no.
- **La concessione/revoca del permesso è essa stessa un atto tracciato e reversibile**,
  append-only (concesso da chi/quando, revocato da chi/quando) — "chi può tirare il freno" è
  in ogni momento una lista nominale auditabile: requisito di governance per un contesto
  istituzionale pubblico (un Comune deve poter rispondere "chi aveva il potere di frenare
  questo pattern il giorno X").
- **Nessun doppio-occhio (due firme) sul singolo tiro.** Il freno vive sull'immediatezza
  (zero latenza), incompatibile con un'approvazione a due firme. La restrizione è
  sull'ACCESSO (chi può — lista nominale), non sulla PROCEDURA (quante firme servono per un
  singolo tiro): due meccanismi di governance distinti, non intercambiabili — uno limita CHI,
  l'altro rallenterebbe OGNI esecuzione.
- **Tiro e rilascio sono entrambi manuali.** A differenza della frizione (a), che si
  auto-recupera da sola su una traccia fresca, il freno **non si rilascia mai da solo**:
  resta tirato finché qualcuno con permesso non lo rilascia esplicitamente, anche se nel
  frattempo il pattern continuasse a manifestarsi.
- **Sopprime la RACCOMANDAZIONE, non il deposito della traccia.** Mentre il freno è tirato,
  il motore smette di proporre il pattern — ma se un'occorrenza viene comunque segnalata e
  approvata sulla corsia fluttuanti nel frattempo, la sua traccia si deposita normalmente nel
  ledger (`docs/PROMOZIONE_TRACCIA.md` §1). **Il ledger resta veritiero**: non mente su cosa
  è successo solo perché il pattern è temporaneamente silenziato lato raccomandazione.
- **Al rilascio, il pattern torna allo stato che il ciclo di vita (a) indica IN QUEL
  MOMENTO** — mai forzato ad `attivo`. Se durante il periodo frenato la frizione automatica
  avrebbe comunque portato il pattern a `sospeso` o `dormiente` (perché nessuna traccia si è
  depositata), è quello lo stato che riemerge al rilascio: il freno non "congela" il ciclo di
  vita sottostante, lo sovrasta solo lato raccomandazione.
- **Append-only su due livelli distinti**: (i) ogni tiro/rilascio del freno è una riga
  permanente (chi, quando, motivazione), (ii) ogni concessione/revoca del permesso stesso è
  anch'essa una riga permanente (chi ha concesso/revocato, quando) — due log append-only
  separati, coerenti con l'invariante A (`docs/ENGINE_INVARIANTS.md` §11) applicato qui non
  ai nodi del grafo ma a due sequenze di governance.
- **Motivazione testuale obbligatoria** su ogni tiro — non un campo opzionale — e **log a
  salienza massima**, distinguibile in audit da una transizione ordinaria della frizione (a):
  chi audita deve poter separare a colpo d'occhio "il pattern si è spento da solo" da
  "qualcuno lo ha spento apposta, e perché".
- **Scopo scoped stretto**: sicurezza, legale, immediatezza, causa esterna (es. il Comune
  vieta i busker con effetto immediato). **Usarlo per "il pattern è semplicemente finito" è
  un uso improprio** — quello è esattamente il compito della frizione (a), che lo gestisce
  già senza intervento umano.

**Residuo — dettaglio implementativo, non domanda di design (§7.14.1, item 16 in §7):** chi
amministra concretamente la lista nominale (chi ha l'autorità di concedere/revocare il
permesso-freno stesso — un Admin di piattaforma? il Comune? il Promotore più anziano?), dove
tecnicamente vive la lista, con quale meccanismo esatto si registra grant/revoke. Il
PRINCIPIO è chiuso (permesso individuale, ristretto, tracciato, reversibile, nessun
doppio-occhio sul tiro); questo è tuning/implementazione, stessa classe di K/orizzonte/
tolleranza sopra — non una decisione di governance ancora da prendere sul CHI del freno, solo
su come si amministra concretamente l'elenco.

## 5. Il gate contro l'auto-approvazione — strutturale, non convenzionale

Non basta dire "il flag viene controllato": una condizione controllata a runtime è
bucabile da un bug futuro che dimentica di controllarla. La regola è più forte:

**Ogni transizione della macchina è taggata `umana` (richiede un curatore identificato,
loggato) o `automatica` (innescata dal sistema).** Verificato riscrivendo l'intera macchina
sopra: **ogni singolo percorso che raggiunge `approved` o `promosso` passa per almeno una
transizione `umana`** — non ne esiste uno automatico che ci arrivi (`submitted→blocked`,
`submitted→expired`, `occorrenze→ricorrente` sono automatiche, ma nessuna delle tre è una
pubblicazione: classificano, scadono, o segnalano un pattern — non approvano).

Regola strutturale per quando (non se) un'automazione verrà aggiunta:
**`richiede_revisione_umana=True` non è un controllo eseguito PRIMA di una transizione
automatica — è la RIMOZIONE di quella transizione dall'insieme delle mosse legali per
quell'item.** Non "se il flag è vero, blocca" (una condizione che qualcuno può dimenticare
di scrivere), ma "l'arco verso `approved` per via automatica non esiste in questo grafo di
transizioni per un item flaggato" — la differenza tra un cancello che qualcuno deve
ricordarsi di chiudere e un muro che non ha mai avuto una porta. Chi implementerà
un'automazione futura dovrà costruire l'insieme delle transizioni disponibili PARTENDO da
questa esclusione, non aggiungerla come eccezione a posteriori.

## 6. I due assi di autorità — per transizione, non per tipo di item

| Transizione | Asse verticale (chi può) | Asse orizzontale (log) |
|---|---|---|
| `submitted → approved` | Guardiano | chi, quando — "perché" aperto (§7.2) |
| `submitted/blocked → rejected` (contributo) | Guardiano | chi, quando, perché (reason category) |
| `submitted → deferred` | Guardiano | chi, quando |
| `blocked`, per-id: redirect / rimuovi da riguarda | Guardiano | chi, quando, perché (a quale id) |
| `blocked`, per-id: crea nodo e aggancia | **Costruttore** | chi, quando, perché |
| `approved → agganciato` | **automatico (sistema)** — CHIUSO, brief Fase 3 §1.7 | chi/cosa=sistema, quando |
| `ricorrente → promosso` | **Promotore** — REALE, `python -m urban_memory.curatela_pattern` | chi, quando, pattern, cadenza (persistiti su `:Evento.promosso_da`/`promosso_il`, mai un log soltanto) |
| `candidato → cestinato` (equivalente reale di "ignorato" del diagramma — permanente, non una terza via) | **Promotore** — REALE, stesso comando | chi, quando, pattern, motivo se dato (persistiti su `pattern_cestinato`, append-only) |
| imposta flag `richiede_revisione_umana` | Guardiano (chiunque) | chi, quando |
| `submitted/blocked → approved/rejected` (fluttuante) | Guardiano | chi, quando, perché |
| `submitted/blocked → expired` (fluttuante) | automatico (clock) | quando, sistema, sempre in audit |
| `expired` (da `approved`) → deposita traccia | automatico (sistema) | quando (= istante dello sweep che esegue la transizione; il `creato_il` della traccia è invece il `valido_fino` del segnale, `docs/PROMOZIONE_TRACCIA.md` §1), sistema, perché="finestra scaduta, occorrenza era approvata" — **non** è il log della traccia stessa (che resta anonima, senza contributor, `docs/PROMOZIONE_TRACCIA.md` §1): è il log della TRANSIZIONE, due record distinti (§1.4 non fa eccezione per l'automatico; §5 del brief impone comunque l'anagrafica minima sulla traccia) |
| `attivo → sospeso` / `sospeso → dormiente` (frizione, §4-bis(a)) | automatico (K battiti mancati / orizzonte lungo superato) | quando si rileva, sistema, perché="cadenza mancata" / "sospensione oltre orizzonte" |
| `sospeso → attivo` (frizione, §4-bis(a)) | automatico (traccia fresca depositata) | quando, sistema |
| tira / rilascia freno di emergenza (§4-bis(b)) | **titolare di permesso-freno individuale** nel PRINCIPIO (sottoinsieme nominale di Promotori, MAI l'intero ruolo — CHIUSA); **REALE oggi**: chiunque abbia accesso alla CLI (`python -m urban_memory.freno_pattern`), percorso fidato/provvisorio, stessa postura di `curatela_pattern.py`/`frizione_pattern.py` — la lista nominale resta APERTA (riga sotto) | chi (`attore`, pseudonimo, validato obbligatorio), quando, motivazione testuale OBBLIGATORIA (validata prima di ogni scrittura) — persistita in `pattern_frenato` (append-only, interrogabile), distinguibile in audit dalle righe automatiche della frizione |
| concedi / revoca permesso-freno (§4-bis(b)) | **APERTO — dettaglio implementativo (§7.14.1, item 16)**: chi amministra la lista, non deciso | chi, quando — append-only, reversibile |

**Ordine verticale**: `approva < aggancia < crea < promuovi` — tenuto nell'ordine dato dal
brief originario, non riordinato. L'accountability (colonna destra) è **identica a ogni
riga** — un Guardiano logga tanto quanto un Costruttore: sono i **poteri di scrittura** che
salgono, mai l'obbligo di rendicontare. Vale anche per le transizioni automatiche
(`submitted→blocked`, `submitted→expired`, `occorrenze→ricorrente`): "sistema" è
un'identità loggata come un'altra, non un'esenzione.

## 7. Domande aperte — sollevate, non risolte (consolidate)

1. ~~`approved → agganciato`: chi/cosa la esegue.~~ **CHIUSA** (brief Fase 3 §1.7, tenuta
   visibile invece di cancellata — stessa disciplina della correzione di provenienza in
   §2): è automatica, esecuzione di sistema. Conseguenza load-bearing: "curato ma non
   agganciato" cessa di essere uno stato di riposo raggiungibile in produzione — diventa un
   transitorio, o un `aggancio_fallito` esplicito se Aura è irraggiungibile. Chiude il bug
   curato-ma-orfano rendendolo non producibile, non gestendolo.
2. **Il "perché" di un'approvazione banale.** Per un rifiuto il "perché" è naturale (reason
   category). Per un'approvazione con un solo clic (il caso comune di Fase 1), forzare una
   giustificazione esplicita rischia di rompere quel flusso — non deciso se "perché" sia il
   fatto stesso di aver approvato, o richieda un campo separato.
3. **Identità del curatore.** `contributor_id` è pseudonimo per proteggere chi contribuisce.
   Un curatore esercita un'autorità istituzionale — resta aperto se debba avere
   un'identità reale (non pseudonima) nel record di audit, un'asimmetria non ancora
   dichiarata.
4. **"Creare un nodo" è atomico o ha una propria sotto-procedura?** Decidere categoria
   (Luogo/Bottega/Artista), nome canonico, eventuali duplicati — potrebbe meritare una
   propria macro a stati, fuori scope qui.
5. **Elenco esatto delle categorie di motivo di rifiuto** — un insieme FISSO, mai testo
   libero, ma quali categorie non è deciso qui.
6. **Ambito del canale di ritorno verso il contributore** — su quali transizioni si attiva:
   solo `rejected`? Anche `redirected`? Anche `approved`?
7. **Finestra di scadenza dei fluttuanti** — quanto dura, e se l'assenza del curatore per
   un weekend debba produrre `expired` silenziosi o un allarme.
8. **Un `blocked` fluttuante ha bisogno di un proprio `target_checker` su `place_id`?**
   Oggi nessun codice valida `SegnaleFluttuante.place_id` contro il grafo.
9. **`aggancio_fallito`: distinguibilità delle cause.** `MemoryLinkError` non separa (a
   differenza di `MemoryStorageError`/`UrbanMemoryError` altrove nel modulo) un fallimento
   di dominio da uno infrastrutturale. Ridotto in portata da §0 (la causa di dominio "target
   sparito" è impossibile via codice applicativo), ma la distinzione strutturale nel codice
   di eccezioni resta assente — rilevante se in futuro emergesse un'altra causa di dominio
   non ancora prevista.
10. **Tensione strutturale nella corsia fluttuanti**: `blocked` lì condivide la meccanica
    di risoluzione del target fantasma con la corsia principale, ma non condivide il tempo
    disponibile per usarla (§4) — non risolta.
11. ~~**Tipo dell'entità promossa**: Esperienza o `:Evento` "programmato" — non chiuso.~~
    **CHIUSA** (brief Fase 3, check §3.4): `:Evento`. La label esiste già nello schema del
    grafo (`00_schema.cypher`, constraint di unicità su `id`) ma senza seed/proprietà —
    riservata in anticipo per esattamente questo momento (`seed_lucca.py`: "Evento arriva
    con i segnali reali"). Dettagli in `docs/PROMOZIONE_TRACCIA.md` §3.
12. ~~**Soglia N e finestra per la rilevazione di "ricorrente"**~~ **PARZIALMENTE CHIUSA nel
    codice**: `N_MINIMO_OCCORRENZE=3` (pavimento duro) e `TOLLERANZA_REGOLARITA=0.35`
    (coefficiente di variazione degli intervalli, scala-indipendente) sono valori di
    PARTENZA reali in `urban_memory.ricorrenza`, tuning da calibrare sui dati del pilota —
    stessa classe di `tasso_ritorno`, non definitivi. Nessuna finestra W: sostituita da
    "tutta la storia disponibile del pattern" (vedi `docs/PROMOZIONE_TRACCIA.md` §3).
13. **Richiamo automatico per tempo di `deferred`** (`deferred_until`) — deliberatamente
    omesso per ora, nessun caso reale a giustificarlo oggi.
14. ~~**Ritiro manuale di un `:Evento` promosso**: la dormienza è *solo* da silenzio del
    ledger (automatica), o un curatore può ritirare a mano un pattern che sa morto *prima*
    che il ledger taccia da solo?~~ **CHIUSA** (brief Fase 3 §7.2, §4-bis sopra): non un
    singolo "ritiro manuale" (bozza abbandonata), ma DUE meccanismi distinti — la **frizione
    automatica a cadenza** (§4-bis(a), il ciclo di vita ordinario: `attivo ⇄ sospeso →
    dormiente`, sensibile al ritmo del pattern, non al tempo assoluto) e il **freno di
    emergenza** (§4-bis(b), override di sicurezza manuale, ortogonale, non uno stato — CHIUSO
    anche il livello di autorità, §7.14.1: permesso individuale nominale, mai l'intero ruolo
    Promotore). Lascia solo un residuo implementativo, item 16 sotto — non una domanda di
    design ancora aperta.
15. **Soglia di invecchiamento per `ultima_traccia_il → dormiente`, e forma esatta della
    curva di decadimento del bagliore** (brief Fase 3 §7.3): la FORMA è disegnata in
    `docs/PROMOZIONE_TRACCIA.md` §2 (decadimento verso un pavimento positivo, mai zero); i
    numeri (tasso, pavimento, soglia di dormienza) sono tuning, stessa classe rimandata
    dell'item 12 — non decisi qui.
16. ~~**§7.14.1 — Livello di autorità del freno di emergenza**: intero ruolo Promotore o
    sottoinsieme ristretto?~~ **CHIUSA nel principio** (§4-bis(b) sopra): permesso
    individuale nominale, ristretto a un sottoinsieme di Promotori, MAI l'intero ruolo —
    concessione/revoca tracciata e reversibile, nessun doppio-occhio sul singolo tiro (la
    restrizione è sull'accesso, non sulla procedura). **Residuo, dettaglio implementativo,
    stessa classe di tuning di K/orizzonte/tolleranza (item 15) — non una domanda di design
    ancora da decidere**: chi amministra concretamente la lista (chi concede/revoca il
    permesso-freno stesso), dove vive tecnicamente, con quale meccanismo esatto.

## 8. Cosa questo documento NON è

Non è un contratto (`packages/contracts`), non è uno schema SQL, non è un endpoint HTTP.
Nessuna riga di `services/urban-memory` implementa uno stato oltre al booleano `curato`
oggi esistente. Prima di implementare qualunque pezzo di questa macchina: contract-keeper
per lo schema, ethics-guardian come passaggio separato (non autovalutazione) su ogni
transizione che tocca autorità o consenso, come per ogni altra wave di questo repository.
