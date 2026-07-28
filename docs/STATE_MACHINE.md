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

## 0. Punto di partenza — cosa fa la curatela OGGI (verificato nel codice, non assunto)

- **`submit_contribution`** (dietro `POST /memory`): valida consenso/licenza/pseudonimo,
  forza `curato=False` a prescindere da cosa arriva, **non verifica mai i target nel
  grafo** — il conferimento resta sempre possibile anche ad Aura in pausa.
- **`curate_contribution`** (alias `publish_pending`): l'UNICA funzione che porta
  `curato=True`. Prende un `target_checker` opzionale (tipicamente
  `Neo4jMemoryLinker.targets_mancanti`): se un id in `riguarda` non esiste come
  `:Luogo`/`:Bottega`/`:Artista`, solleva `InvalidTargetsError` e **non scrive nulla**.
  Verifica SOLO esistenza — non crea mai un nodo mancante.
- **Cosa scrive esattamente** (letto testualmente in entrambe le implementazioni, non
  presunto):
  ```python
  # InMemoryMemoryRepository.curate
  aggiornato = corrente.model_copy(update={"curato": True})
  # PostgresMemoryRepository.curate
  "UPDATE memory_contribution SET curato = true WHERE id = %(id)s RETURNING ..."
  ```
  **Un booleano. Nessun'altra colonna, nessuna scrittura verso Neo4j.** Verificato con un
  grep degli import di `service.py`/`repository.py`: nessuno dei due importa `graph_link`.
- **L'aggancio al grafo esiste, ma altrove**: `urban_memory.graph_link.link_to_graph()`
  (o `Neo4jMemoryLinker.link()`) è la SOLA funzione che scrive
  `MERGE (m:Memoria)-[:RIGUARDA]->(target)`. **Chiamata da un solo punto in tutto il
  repo**: `urban_memory/verify.py`, come passo 5, esplicitamente separato dal passo 3
  (`curate_contribution`). Nessun percorso di produzione le incatena.
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
  - Nessun rifiuto esplicito — solo `curato=True` o "resta pending per sempre",
    indistinguibile da "nessuno l'ha ancora guardato".
  - Nessuna creazione di nodi — la curatela blocca se un target manca, non offre "crealo".
  - Nessuna promozione — il concetto fluttuante→permanente non esiste in nessuna forma.
  - Nessun log delle decisioni oltre lo stato booleano finale — non c'è "chi, quando,
    perché".
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
submit (NUOVO — prerequisito non risolto qui: oggi Signal.eventi_attivi
        non persiste MAI fuori da una singola richiesta di itinerario;
        perché questa corsia esista serve un canale di sottomissione
        indipendente che oggi non esiste — vedi docs/LIMITI.md)
   │
   ▼
"submitted"  (descrizione/temi/place_id/non_commerciale dichiarati;
              porta con sé un orologio — durata della finestra NON decisa)
   │
   │ pre-check automatico: place_id esiste come Luogo/Bottega/Artista?
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
┌────────┬─────────┬──────────┐
▼        ▼         ▼          ▼
approved rejected  expired  (nessuna azione entro la finestra)
(Guardiano) (+reason  (automatico,     │
            category)  clock-based,    ▼
                        terminale,  "expired"
                        SEMPRE in audit — mai silenzioso)
```

`expired` è deliberatamente **distinto** da `rejected`: uno è un giudizio sul contenuto,
l'altro è un fatto di processo (nessuno è arrivato in tempo). Confonderli nasconderebbe un
problema di capacità del team dietro una metrica di qualità dei contenuti.

**Nessun `agganciato` in questa corsia**, per scelta esplicita: un'occorrenza approvata non
scrive nulla nel grafo — resta un fatto di runtime (il motore la usa per una composizione
di itinerario, poi scompare con la richiesta, come oggi). Solo la promozione (sotto) scrive
struttura permanente.

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
 nel grafo; QUALE tipo  individualmente sulla corsia normale —
 esattamente — Esperienza "ignorato" non tocca retroattivamente le
 o :Evento "programmato" — occorrenze già approvate)
 domanda aperta, non
 chiusa qui)
```

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
| `approved → agganciato` | **APERTO — non assegnato** (§7.1) | chi/cosa, quando |
| `ricorrente → promosso` | **Promotore** | chi, quando, perché |
| imposta flag `richiede_revisione_umana` | Guardiano (chiunque) | chi, quando |
| `submitted/blocked → approved/rejected` (fluttuante) | Guardiano | chi, quando, perché |
| `submitted/blocked → expired` (fluttuante) | automatico (clock) | quando, sistema, sempre in audit |

**Ordine verticale**: `approva < aggancia < crea < promuovi` — tenuto nell'ordine dato dal
brief originario, non riordinato. L'accountability (colonna destra) è **identica a ogni
riga** — un Guardiano logga tanto quanto un Costruttore: sono i **poteri di scrittura** che
salgono, mai l'obbligo di rendicontare. Vale anche per le transizioni automatiche
(`submitted→blocked`, `submitted→expired`, `occorrenze→ricorrente`): "sistema" è
un'identità loggata come un'altra, non un'esenzione.

## 7. Domande aperte — sollevate, non risolte (consolidate)

1. **`approved → agganciato`: chi/cosa la esegue.** È un'azione MECCANICA (nessun giudizio
   nuovo rispetto a `approved`, dato che l'esistenza dei target è già stata giudicata) più
   che un giudizio umano — candidata a esecuzione automatica di sistema, gated solo da
   "l'approvazione è avvenuta e i target erano validi in quel momento". Non deciso: tiene
   insieme il dubbio se debba essere autorità *umana* affatto.
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
11. **Tipo dell'entità promossa**: Esperienza (nel senso di `ExperienceNode`) o `:Evento`
    "programmato" (esplicitamente fuori scope nel resto del progetto) — non chiuso.
12. **Soglia N e finestra per la rilevazione di "ricorrente"** — non decise, stessa classe
    di scelta già rimandata altrove nel progetto (es. `tasso_ritorno`).
13. **Richiamo automatico per tempo di `deferred`** (`deferred_until`) — deliberatamente
    omesso per ora, nessun caso reale a giustificarlo oggi.

## 8. Cosa questo documento NON è

Non è un contratto (`packages/contracts`), non è uno schema SQL, non è un endpoint HTTP.
Nessuna riga di `services/urban-memory` implementa uno stato oltre al booleano `curato`
oggi esistente. Prima di implementare qualunque pezzo di questa macchina: contract-keeper
per lo schema, ethics-guardian come passaggio separato (non autovalutazione) su ogni
transizione che tocca autorità o consenso, come per ogni altra wave di questo repository.
