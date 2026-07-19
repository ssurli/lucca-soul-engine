# Limiti noti

Questo documento raccoglie i limiti architetturali **noti e accettati** del motore — non bug da
correggere alla prossima occasione, ma proprietà del design attuale che non garantiscono ciò che
potrebbero sembrare garantire. Un limite qui dentro è dichiarato, non nascosto: se una wave
futura vuole rimuoverlo, deve prima leggere questa voce e il suo costo stimato.

---

## Il Recommender ML non garantisce matematicamente la non-concentrazione aggregata

**Introdotto:** Wave 3b. **Componente:** `services/recommender`.

### Cosa è garantito oggi

Il recommender (`recommender.ranking.costruisci_score_fn`) corregge `calcola_score` con due
penalità indipendenti — quota storica (con smoothing di Laplace) e quota strutturale (dominanza
per pertinenza di contenuto, da profili-archetipo fissi) — entrambe sul `place_id`, mai un
premio. Questo è verificato empiricamente su **4 scenari storici indipendenti**
(`tests/test_integration_wave3b.py`): concentrazione su 1 luogo, su 5 luoghi, storico presente
anche sul luogo dominante per pertinenza, e uno scenario randomizzato a seed fisso. In tutti e
quattro, la distribuzione aggregata (misurata su una popolazione di 10 profili diversi) non
peggiora mai rispetto al ranking deterministico puro.

Questa è **robustezza empirica**: il fix è stato validato contro scenari scelti per essere
rappresentativi e avversariali (incluso quello che aveva originariamente fatto fallire il design
precedente), non contro un caso singolo che si sarebbe potuto ottimizzare per far passare il
test.

### Cosa NON è garantito

Robustezza empirica su 4 scenari non è una **garanzia matematica** per qualunque distribuzione
storica possibile. Il recommender calcola una `score_fn` **locale, per singola richiesta**: dato
un profilo e un insieme di candidati, restituisce un punteggio corretto — ma non ha visibilità
su cosa stanno ricevendo, nello stesso momento, gli altri visitatori. Una correzione locale, per
costruzione, non può garantire che una metrica di distribuzione **aggregata su una popolazione di
richieste** non peggiori mai: è sempre possibile costruire uno scenario storico patologico in cui
penalizzare i luoghi tracciati come sovraffollati sposta il flusso su un'alternativa che, pur non
tracciata, diventa a sua volta un collo di bottiglia — esattamente il meccanismo che ha causato il
bug originale di questa wave, ora mitigato (quota strutturale) ma non reso matematicamente
impossibile in ogni scenario concepibile.

### Cosa servirebbe per una garanzia vera

| Approccio | Come funzionerebbe | Perché non è stato fatto ora |
|---|---|---|
| **Allocazione globale a batch** | Invece di rispondere richiesta per richiesta, raccogliere un insieme di richieste in una finestra temporale e risolvere un problema di assegnazione ottima (fair division) che massimizzi la pertinenza individuale sotto un vincolo di distribuzione aggregata. | Ottimizzazione combinatoria (NP-hard in generale). Richiede conoscere le richieste **prima** di servirle: incompatibile con un servizio che risponde in tempo reale man mano che i visitatori arrivano — cambierebbe il modello di servizio da "richiesta-risposta" a "batch differito". |
| **Stato condiviso in tempo reale + algoritmo di allocazione online** | Un contatore vivo e condiviso (es. Redis, o una tabella Postgres con incrementi atomici) di "quante persone sono state instradate verso il luogo X in questa finestra", letto e aggiornato ad ogni richiesta, con una penalità che cresce con l'allocazione **in corso** (non solo con lo storico passato) secondo un algoritmo di tipo *online fair allocation* / regret minimization. | Darebbe un limite superiore **vero** alla concentrazione, ma resta **probabilistico**, non assoluto (dipende dall'ordine di arrivo delle richieste, da condizioni di gara tra richieste simultanee). Richiede: infrastruttura condivisa nuova, gestione della concorrenza tra richieste simultanee, un algoritmo online non banale (R&D, non solo ingegneria) — non un adattamento incrementale del codice attuale. |

**Costo stimato:** settimane di lavoro dedicato (progettazione dell'algoritmo online, infrastruttura
condivisa, test di concorrenza) — probabilmente una wave a sé, non un task all'interno di una wave
esistente. C'è sinergia naturale con l'**Urban Intelligence Index** (Wave 4), che dovrà comunque
tracciare `distribuzione_flussi` in modo aggregato: lo stato condiviso richiesto dal secondo
approccio potrebbe riusare la stessa infrastruttura di tracciamento, ma l'algoritmo di allocazione
online **con garanzia** resta un pezzo di ricerca applicata in più, non incluso nel semplice
tracciamento a fini di reporting.

### Decisione

Non implementato ora. Il recommender resta con la correzione locale (Wave 3b), validata sui 4
scenari sopra. Questo limite va riletto prima di:
- estendere il recommender con nuovi termini di penalità (per non illudersi di "risolvere" un
  problema strutturale con un altro aggiustamento locale);
- decidere lo scope della Wave 4 (Urban Intelligence Index), dove il tracciamento in tempo quasi
  reale della distribuzione dei flussi è comunque previsto — è il punto naturale in cui
  rivalutare se investire nell'algoritmo di allocazione online.
