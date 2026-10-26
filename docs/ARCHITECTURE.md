# ARCHITECTURE

Vocabolario congelato dal White Paper v1.0. Il codice adotta questi nomi.

## Dove ci collochiamo

```
Urban Digital Twin                    (presupposto — non è il nostro prodotto)
├── Physical Layer                    edifici, spazi, monumenti
├── Infrastructure Layer              reti, mobilità, illuminazione, IoT
├── Data Layer                        open data, sensori, eventi, meteo
│
└── Urban Cognitive Layer             ← IL NOSTRO PERIMETRO
      ├── Human Experience Layer      il contatto con le persone
      ├── Urban Knowledge Graph       la conoscenza della città
      ├── AI Experience Engine        il motore che compone
      ├── Ethical AI Engine           il sistema decisionale
      ├── Urban Intelligence Index    gli indicatori
      └── Urban Memory                la memoria collettiva
```

Il Digital Twin **sa dove sono** le persone. Non sa **che cosa stanno vivendo**.
Quel divario è il nostro perimetro.

## Flusso a runtime (una richiesta di itinerario)

```
App Flutter  ──POST /itinerary (VisitorContext)──►  BFF FastAPI
                                                        │
                                                        ▼
                                          AI EXPERIENCE ENGINE
                                          (l'unico che DECIDE)
                                                        │
   ┌────────────────┬──────────────────┬────────────────┼─────────────────┐
   ▼                ▼                  ▼                ▼                 ▼
Knowledge Graph  Recommender        Signal         Ethical AI          RAG + LLM
candidati per    riordina su        filtra/        vincoli:            genera il `reason`
CONNESSIONI      comportamenti      riscrive       distribuzione,      e il racconto
(Puccini →       (il modello di     (pioggia →     accessibilità,      multilingue
 liutaio →        Netflix)          al_chiuso;     sostenibilità       (dialoga,
 violino)                            Mura piene →                       NON decide)
                                     alternativa)
                                                        │
                                                        ▼
                                          Itinerary  (ogni tappa con `reason`)
```

Ogni interazione emette `BehaviorEvent`. Gli eventi alimentano due cose:
- il **Recommender** (che impara l'algoritmo, non il modello linguistico);
- l'**Urban Intelligence Index** (aggregazioni anonime → dashboard del Comune).

Ogni esperienza vissuta può inoltre generare un `MemoryContribution` → **Urban Memory**, che a sua
volta arricchisce il Knowledge Graph. Il ciclo è chiuso: **la città che genera esperienze è la
stessa che, misurandole, impara.**

## Perché i livelli sono separati

- **Urban Knowledge Graph** — ragiona su RELAZIONI, non categorie. È da qui che nascono i percorsi
  sorprendenti, e la sorpresa non è decorativa: è la ragione per cui l'esperienza non è replicabile
  da una guida né da un motore di ricerca.
- **Recommender** — apprende dai comportamenti. ML classico, non riaddestramento di LLM.
- **RAG + LLM** — dialoga, spiega, personalizza. **Non decide.** È intercambiabile: il modello
  linguistico è una commodity, non il nostro fossato.
- **AI Experience Engine** — combina tutto e applica i vincoli. **Decide solo lui**, perché un
  vincolo applicato in un solo punto è verificabile; distribuito su più componenti, no.
- **Urban Memory** — il fossato difendibile: contenuto acquisibile solo tramite partecipazione.
- **Urban Intelligence Index** — rende il sistema responsabile dei propri effetti.

## MVP vs completo

Nell'MVP l'Experience Engine è **a regole** (grafo + segnale + vincoli etici), deterministico e
testabile; il recommender è un ranking placeholder; la RAG serve per onboarding e `reason`. L'ML
entra quando esistono eventi reali. Non serve riaddestrare nulla: la RAG lavora su dati aggiornati.

**Stato attuale (ondata 4).** I livelli "Recommender" e "RAG + LLM" sopra sono l'architettura
target. Oggi i motivi (`reason`) e il profilo dell'onboarding sono costruiti da regole, senza LLM
né vector store: `rag.reasons.compose_reason` e `rag.onboarding.profile_from_answers` sono
deterministici; `rag.reasons.enrich_with_llm` esiste ma il BFF non lo chiama, e nessun codice usa
ancora pgvector. Il recommender è un'euristica (penalità di concentrazione, nessun modello
addestrato) che si accende solo sopra 20 eventi mappabili (`SOGLIA_MINIMA_EVENTI_MAPPABILI`): per
la demo è di fatto spento (cold start).
