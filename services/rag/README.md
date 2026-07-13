# Lucca Soul — RAG (`services/rag`)

Onboarding conversazionale → `EmotionalProfile`, e generazione del `reason`
(spiegabilità). Import name del pacchetto: `rag` (nome distribuzione:
`lucca-rag`).

L'LLM **dialoga, non decide**: costruisce il profilo emozionale
dall'onboarding e può arricchire il racconto, ma la scelta delle tappe è
sempre dell'**AI Experience Engine**. Il percorso principale di questo
servizio è **deterministico e testabile offline**: non richiede
`ANTHROPIC_API_KEY` né il pacchetto `anthropic`.

## Installazione

Dalla radice del repo. `packages/contracts` è la single source of truth
degli schemi ed è una dipendenza locale (non su un indice pip): va
installata a parte, insieme a questo pacchetto, in editable mode.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e packages/contracts -e services/rag
```

## Moduli

- `rag/onboarding.py` — le domande dell'onboarding (`DOMANDE`, versionate
  per `domanda_id`) e `profile_from_answers(req) -> EmotionalProfile`: parsing
  robusto e deterministico di risposte in italiano colloquiale. Nessuna
  risposta strana solleva un'eccezione: si ricade sempre su un default
  prudente e documentato.
- `rag/reasons.py` — `compose_reason(candidate, profile, segnali) -> str`
  compone il `reason` intrecciando una connessione dal grafo, il tratto del
  profilo pertinente e l'eventuale segnale attivo; `adapt_reason(motivo,
  segnale) -> str` riscrive il `reason` di una tappa sostituita
  dall'Experience Engine. `enrich_with_llm(...)` è un arricchimento
  **opzionale**, dietro `ANTHROPIC_API_KEY`, mai richiesto dai test.

## Mapping domande → campi di `EmotionalProfile`

| `domanda_id`      | testo (it)                                             | campo                      |
|--------------------|---------------------------------------------------------|-----------------------------|
| `perdersi`          | "Hai voglia di perderti tra vicoli e piazze...?"        | `curiosita`                 |
| `silenzio_musica`   | "Cerchi il silenzio... o preferisci la musica dal vivo?" | `contemplazione`            |
| `bellezza_storie`   | "Ti colpisce di più la bellezza... o la storia...?"      | `arte`                      |
| `bambini`           | "Viaggi con bambini?"                                    | `con_bambini`                |
| `tempo`             | "Quanto tempo hai a disposizione oggi?"                  | `tempo_disponibile_min`     |
| `accessibilita`     | "Hai bisogno di percorsi accessibili...?"                | `accessibilita_richiesta`   |
| `firenze`           | "Hai già visto Firenze?"                                 | `ha_gia_visto_firenze`      |

## Default quando una risposta manca o non è interpretabile

`curiosita`, `contemplazione`, `arte` → `0.5` (neutro) · `con_bambini` →
`False` · `tempo_disponibile_min` → `120` (due ore) ·
`accessibilita_richiesta` → `False` · `ha_gia_visto_firenze` → `False`.
`lingue` riflette sempre `OnboardingRequest.lingua`.

## Smoke test rapido

```powershell
python -c "
from contracts import OnboardingAnswer, OnboardingRequest, GraphCandidate, ExperienceNode
from rag import profile_from_answers, compose_reason

req = OnboardingRequest(risposte=[
    OnboardingAnswer(domanda_id='perdersi', risposta='si, tantissimo!'),
    OnboardingAnswer(domanda_id='silenzio_musica', risposta='preferisco il silenzio'),
    OnboardingAnswer(domanda_id='tempo', risposta='due ore'),
], lingua='it')
print(profile_from_answers(req))
"
```

## Nota — vector store (pgvector su Neon)

Il retrieval su dati aggiornati (grafo, eventi, artisti) userà **pgvector
dentro Neon** (nessun Qdrant, nessun Docker), riusando la stessa
`DATABASE_URL`: `CREATE EXTENSION IF NOT EXISTS vector;` una tantum, colonne
`VECTOR(EMBEDDING_DIM)` con indice HNSW. L'indicizzazione arriva in una wave
successiva: la Wave 1 copre onboarding e `reason`.
