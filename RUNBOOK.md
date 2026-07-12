# RUNBOOK — come lanciare la build

Prerequisiti: Claude Code installato, `git init`, i file di questo scaffold nel repo.
Gli agenti si caricano all'avvio della sessione (se editi un file agente su disco, riavvia).

## Modo A — guidato, una wave alla volta (consigliato)

Nella sessione Claude Code, incolla:

```
Leggi CLAUDE.md e docs/. Sei l'orchestratore. Esegui SOLO la Wave 0 del BUILD_PLAN,
poi fermati e riepiloga i criteri di accettazione prima di chiedermi il via per la Wave 1.
```

Poi, wave per wave, dai il via alla successiva. Massimo controllo, spesa minima, correggi
presto le scelte di schema.

## Modo B — lancio unico presidiato (una sola incollata, con guardrail)

Se vuoi far girare tutto da un solo prompt ma senza corse cieche, incolla questo:

```
Leggi CLAUDE.md e docs/. Sei l'orchestratore del motore Lucca Soul.
Esegui le wave del BUILD_PLAN in ordine, con queste REGOLE DI GATE:

1. Wave 0 PRIMA di tutto: contract-keeper crea packages/contracts. Nessun altro modulo
   parte finché i contratti non esistono.
2. Per ogni wave: delega ai subagent competenti (in parallelo dove indipendenti),
   poi fai girare test-engineer; su recommender / experience-engine / urban-memory /
   intelligence-index fai girare ethics-guardian.
3. NON passare alla wave successiva se: i criteri di accettazione non sono soddisfatti,
   OPPURE i test non sono verdi, OPPURE ethics-guardian ritorna FAIL.
   In quel caso fermati, spiega il problema e chiedi come procedere.
4. Alla fine di OGNI wave: riepiloga in 5 righe cosa è stato fatto e i criteri spuntati,
   poi prosegui automaticamente alla wave dopo (se i gate sono verdi).
5. Fermati e chiedi conferma esplicita PRIMA di iniziare la Wave 2 (Urban Memory),
   così validiamo insieme il Proof of Concept.

Rispetta sempre le regole non negoziabili di CLAUDE.md: un solo schema; decide solo
l'Experience Engine; privacy by design; obiettivo etico (mai click/pubblicità/vendite);
visibilità non acquistabile; spiegabilità obbligatoria; consenso e licenza per ogni contributo
di Urban Memory. Il vocabolario è quello del White Paper: non inventare nomi paralleli.
```

Questo ti dà "un unico lancio" ma con checkpoint automatici: si ferma dove serve invece di
accumulare errori.

## Consiglio pratico

Parti **lean**: per le Wave 0–1 attiva contract-keeper, api-engineer, graph-architect,
experience-engine, rag-engineer, frontend-engineer, test-engineer. Aggiungi
urban-memory-engineer (Wave 2), recommender-engineer (Wave 3) e index-engineer (Wave 4)
quando servono.

Nota costi: i subagent in parallelo scalano ~linearmente in token (ognuno rilegge il proprio
contesto). Parallelo per esplorazione/tempo; sequenziale per budget stretto.
