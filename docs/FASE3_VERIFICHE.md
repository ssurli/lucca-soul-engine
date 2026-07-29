# FASE3_VERIFICHE.md — le cinque verifiche per prime (§3 del brief)

> **Stato: fatti verificati nel codice, non design.** Ogni riga sotto è stata controllata
> per assenza, contro il codice — mai presunta — prima che qualunque cosa in
> `docs/PROMOZIONE_TRACCIA.md` venisse disegnata (disciplina imposta da §0 e §3 del brief:
> *"Non progettare finché non li hai stabiliti. Se uno contraddice una costante congelata,
> fermati e segnala."*). Nessuna delle cinque ha richiesto di fermarsi: nessuna contraddice
> un congelato del brief in modo bloccante, ma il check 2 ha rivelato un vincolo reale
> (assenza di `creato_il`), sciolto da una decisione esplicita accettata dopo la verifica
> (Strada B, vedi tabella). Dettagli estesi nella conversazione che ha prodotto questo
> documento; qui la forma consultabile.

## Le cinque verifiche

| # | Domanda (brief §3) | Esito | Evidenza |
|---|---|---|---|
| 1 | L'audit dell'`expired` porta già `place_id` + `temi`? | **No — non esiste alcun audit dell'`expired`.** `expired` non è implementato: nessuna tabella, nessuna funzione lo produce. Il ledger delle tracce è un meccanismo NUOVO, non un log esistente da promuovere. | L'unico audit reale nel repo è `urban_memory/audit.py`, e riguarda tutt'altro: contributi curati con target mancanti nel grafo (`MemoryContribution.riguarda`), mai `SegnaleFluttuante`. |
| 2 | Il `Signal`, al momento della transizione a `expired`, ha ancora i temi in mano? | **I `temi` sì, ma manca `creato_il`.** Né `SegnaleFluttuante` né `Signal` portano un timestamp di creazione. `Signal.ora` è un'ora del giorno (`time`), non una data. **Sciolto da Strada B** (decisione accettata): `creato_il` della traccia è timbrato dal SERVER al momento di `expired`, non letto dal segnale — nessun campo nuovo su `SegnaleFluttuante`/`Signal`, che restano transitori esattamente come da contratto. | `packages/contracts/contracts/models.py`: `SegnaleFluttuante` ha `id, descrizione, temi, place_id, non_commerciale` (nessun timestamp); `Signal` ha `meteo, affollamento, stanchezza, ora: time, giorno_settimana, eventi_attivi` (nessun timestamp/data). |
| 3 | Esiste in Postgres/Neon un ledger di audit naturale, di cui la traccia possa essere una vista/proiezione filtrata? | **No — serve una tabella nuova.** `behavior_event` è il precedente idiomatico più vicino (append-only, chiave surrogata `BIGSERIAL`, `TIMESTAMPTZ`) ma non porta né `place_id` né `temi` — il suo `tipo` è vincolato da CHECK a un insieme fisso che non include nulla su fluttuanti/tracce. `memory_contribution` ha `creato_il` ma porta `contributor_id`, esplicitamente vietato dall'anagrafica minima della traccia (brief §5). Nessuna vista filtrata è possibile senza un join semanticamente sbagliato. | `services/recommender/sql/00_events_schema.sql`, `services/urban-memory/sql/00_memory_schema.sql`, `services/marketplace/sql/00_marketplace_schema.sql` — lette per intero, nessuna porta `place_id`+`temi` insieme. |
| 4 | `:Evento` esiste già come tipo di nodo, e con quale lifecycle? | **Esiste come label riservata ma VUOTA.** Un `CREATE CONSTRAINT` di unicità su `id` in `00_schema.cypher`, ma zero nodi nel seed, zero proprietà, zero relazioni che lo coinvolgono. `seed_lucca.py` lo dice esplicitamente: *"`Evento`... nello schema ma non ha seed in questa wave: `Evento` arriva con i segnali reali"* — riservato in anticipo per esattamente questo momento. Nessun lifecycle esiste ancora: va disegnato da zero (fatto in `docs/PROMOZIONE_TRACCIA.md` §3), non riusato. | `services/graph/cypher/00_schema.cypher:30`; `services/graph/graph/seed_lucca.py:16-19`. |
| 5 | Esiste già uno stato "chiuso/inattivo/dormiente" per `:Bottega` o `:Luogo`? | **No — nessun precedente da riusare.** Le dataclass sorgente hanno solo campi anagrafici: `Luogo(id, nome, categoria)`, `Bottega(id, nome, mestiere, place_id)`. L'unico booleano di stato/attivazione nel dominio è `Partner.abbonamento_attivo` — un fatto commerciale (abbonamento), non fisico (luogo aperto/chiuso/dormiente): nessuna analogia diretta riusabile per la dormienza di un pattern. | `services/graph/graph/seed_lucca.py:89-107`; `packages/contracts/contracts/models.py:188-202` (`Partner`). |

## Conseguenza per il design (§4 del brief)

- Check 2 **scioglie la questione retroattività** (brief §6, come previsto): se le
  occorrenze approvate non persistono mai come nodi (nessun meccanismo di persistenza
  esiste, checked ai punti 1-2), non c'è nulla da riscrivere sotto un pattern promosso —
  resta solo provenance (quali tracce/occorrenze l'hanno determinato), mai topologia.
- Check 3 fissa la forma del ledger: tabella nuova, propria migrazione, idiomatica di
  `behavior_event` (append-only, `IF NOT EXISTS`, chiave surrogata) — non una vista.
- Check 4 chiude la domanda 11 di `docs/STATE_MACHINE.md` §7: il nodo promosso è famiglia
  `:Evento`, non `:Luogo` e non una nuova `Esperienza`.
- Check 5 conferma che il "ritiro" di un pattern promosso (dormienza) è un meccanismo
  GENUINAMENTE NUOVO, non l'applicazione per analogia di uno stato già esistente altrove nel
  grafo.

Dettaglio completo di ciascun punto, incluse le proprietà proposte per `:Evento` e la
relazione di ancoraggio (`SI_SVOLGE_A`, chiusa contro il codice — vedi
`docs/PROMOZIONE_TRACCIA.md` §3), in `docs/PROMOZIONE_TRACCIA.md`. I due invarianti di
sistema scoperti nel corso di questa verifica (append-only sui target di `riguarda`;
"curato tira aggancio", quest'ultimo una decisione congelata non ancora vera nel codice)
sono in `docs/ENGINE_INVARIANTS.md` §11 — non duplicati qui.
