# Lucca Soul Lab

Un'app che compone una giornata a piedi nel centro di Lucca a partire da sei domande, e spiega
ogni scelta. Per esempio, in una prova con le risposte «musica» e «mezza giornata», la giornata
comincia da San Michele in Foro: «in questa chiesa il giovane Giacomo Puccini dava lezioni
d'organo». Accanto, una leggenda sulla facciata e la sua fonte.

## Stato

Prototipo dimostrativo. Non è in linea: gira sul computer di chi lo avvia.
README aggiornato al 10 novembre 2026.

## Cosa fa oggi

- **Compone l'itinerario dalle risposte.** Sei domande (voglia di perdersi, silenzio o musica,
  bellezza o storie, bambini, tempo, accessibilità) diventano una giornata di tappe in ordine.
- **Si adatta a un cambiamento.** Tre interruttori simulano «Piove», «Mura affollate» e
  «Sono stanco/a». Con «Piove», per esempio, una tappa all'aperto diventa una al chiuso e la
  scheda dice «Sostituita per la pioggia». Si può tornare al percorso iniziale.
- **Mostra gli orari.** Per ogni tappa l'ora di arrivo e la durata, per la giornata l'intervallo
  complessivo.
- **Mostra la mappa.** Le tappe numerate su una mappa, con un link «Come arrivo qui».
- **Spiega con le fonti.** Ogni tappa ha un motivo leggibile; curiosità e leggende riportano la fonte.
- **Raccoglie ricordi.** Da ogni tappa si può lasciare un ricordo (racconto, foto, musica, mestiere,
  ricetta, dialetto, testimonianza), solo con consenso esplicito e una licenza. Va in revisione
  prima di essere pubblicato. Una vista per i cittadini elenca, luogo per luogo, i ricordi approvati.

## Cosa è vero e cosa è d'esempio

- **Luoghi reali:** 24 luoghi del centro storico e 35 esperienze.
- **Coordinate:** rilevate a mano dal committente su Google Maps il 22 ottobre 2026. Le distanze a
  piedi sono stime: linea d'aria moltiplicata per 1,3.
- **Orari:** ogni orario dichiara la sua fonte. Quattro vengono da siti ufficiali, gli altri sono
  indicati dal committente; alcuni sono stime dichiarate come tali.
- **Botteghe inventate:** le 5 botteghe artigiane sono esempi dimostrativi, non esercizi reali.
  Il motivo della tappa lo dice («esempio dimostrativo») e non hanno un punto sulla mappa.
- **Ricordi d'esempio:** i 4 ricordi caricati per la demo sono testi del committente, segnati
  «(esempio dimostrativo)».
- **Nessun dato reale di affollamento o di meteo.** I cambiamenti li simula chi usa l'app.
  Il cruscotto per gli enti non ha dati reali da mostrare.

## Cosa non fa

- Non verifica che una persona sia stata davvero in un luogo.
- Non conosce festività, chiusure straordinarie o posti disponibili: solo fasce orarie settimanali.
- I contenuti sono stati raccolti con cura ma non verificati sul posto.
- Non esiste un'app per telefono: l'app gira nel browser.
- Un'installazione serve una sola città. La separazione tra motore e contenuti di una città è
  provata solo su un borgo inventato, mai su una seconda città reale.

L'elenco completo, con cosa servirebbe per superare ogni limite, è in
[`I_LIMITI_DEL_MOTORE.md`](I_LIMITI_DEL_MOTORE.md) e [`docs/LIMITI.md`](docs/LIMITI.md).
Alcune voci di quei file sono state superate dal codice e lo dichiarano.

## Le regole che il codice fa rispettare

Ogni regola è protetta da test automatici, eseguiti a ogni invio del codice su GitHub.

| Regola | Dove è protetta |
|---|---|
| **Pagare non fa salire nessuno.** L'abbonamento decide solo se una bottega partner compare, mai dove. Le botteghe di oggi sono tutte dimostrative. | `services/experience-engine/tests/test_engine.py` (`test_scoring_non_usa_partner_id_ne_prezzo`, `test_scoring_bit_identico_con_abbonamento_e_prenotabilita_variati`, `test_partner_non_attivo_escluso_dai_filtri_duri`) |
| **Ogni decisione è spiegata.** Nessuna tappa, tolta o sostituita, resta senza un motivo. | `packages/contracts/contracts/models.py` (motivo obbligatorio); `services/experience-engine/tests/test_engine.py` (`test_ogni_tappa_ha_reason_non_vuoto`); `services/experience-engine/tests/test_escluse_reason_canonico.py` |
| **Nessun ricordo senza consenso e licenza.** | `services/urban-memory/tests/test_service.py`; vincoli del database in `services/urban-memory/tests/test_repository.py` (eseguiti in CI su Linux) |
| **Sotto le 10 persone il dato non si mostra.** Indicatori e mappa dei flussi del cruscotto restano nascosti. | `services/intelligence-index/tests/test_index.py`, `services/intelligence-index/tests/test_intelligence_index_dashboard.py`, `services/api/tests/test_dashboard.py` |

## Per chi vuole provarlo

Prerequisiti: Windows con PowerShell, Git, Python 3.13, Flutter (la CI usa 3.47.7), accesso a
Internet per i pacchetti e per la mappa.

```powershell
git clone https://github.com/ssurli/lucca-soul-engine.git
cd lucca-soul-engine
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e packages\contracts -e services\graph -e services\rag -e services\experience-engine -e services\urban-memory -e services\marketplace -e services\recommender -e services\intelligence-index -e services\api
powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1
```

Lo script costruisce l'app web, avvia il BFF sulla porta 8000 e stampa gli indirizzi: mattina
`http://localhost:8000/`, pomeriggio con `?istante=...`.

**Senza `.env`** la demo funziona con i dati versionati nel repo. È stata provata così su una
copia pulita: itinerario, adattamento, ricordo inviato, vista Cittadino e dashboard si aprono.
Differenze: i ricordi restano in memoria fino allo spegnimento, nessun ricordo risulta approvato
e la dashboard mostra solo «dato insufficiente».

**Con Neo4j Aura e Neon:** copia `.env.example` in `.env` e compila i valori (Aura vuole
`neo4j+s://`, Neon `sslmode=require`). `scripts\bootstrap.ps1` è facoltativo: verifica le
connessioni e abilita l'estensione `vector` su Neon. Le credenziali stanno solo nel `.env`.

**Demo da un altro dispositivo:**
`powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Rete` ascolta su tutta la rete
locale e stampa questo avviso: «Modalita' -Rete: SOLO per la demo su rete fidata. POST /memory e POST
/booking scrivono su Neon e /docs e' leggibile da chiunque sulla rete.»

**Rete con ispezione TLS:** se Python fallisce con `SSLCertVerificationError`, esegui
`pip install pip-system-certs`: Python userà i certificati di Windows, senza disattivare la verifica.

**Aura Free** si mette in pausa da sola e viene cancellata dopo 30 giorni di inattività. Il seed
del grafo è versionato in `services/graph/cypher/` e si ricarica da zero: procedura in
[`services/urban-memory/README.md`](services/urban-memory/README.md), sezione «Aura cancellata».

Test: `.venv\Scripts\python.exe -m pytest` (più le cartelle `services\*\tests`, come nella CI in
`.github/workflows/`) e `flutter test` in `apps/lucca_soul_app`.

## Com'è fatto

| Cartella | Cosa contiene |
|---|---|
| `apps/lucca_soul_app` | L'app Flutter (web): domande, itinerario, mappa, ricordi, dashboard. |
| `services/api` | Il BFF FastAPI: l'unico ingresso dell'app, serve anche l'app web. |
| `services/experience-engine` | Il motore che decide le tappe, a regole, deterministico e spiegabile. |
| `services/graph` | Il grafo dei luoghi (Neo4j): schema, Cypher, dati della città scelti da `CITY_SEED`. |
| `services/rag` | Le domande iniziali e i testi dei motivi; l'arricchimento via LLM è facoltativo. |
| `services/recommender` | Riordina le proposte penalizzando i luoghi già più frequentati. |
| `services/urban-memory` | I ricordi: consenso, licenza, revisione, aggancio ai luoghi. |
| `services/intelligence-index` | Gli indicatori aggregati e anonimi per la dashboard. |
| `services/marketplace` | Prenotazioni delle botteghe partner; non influisce sul punteggio. |
| `packages/contracts` | I tipi di dati condivisi da tutti i servizi (vedi `docs/DATA_CONTRACTS.md`). |

Il vocabolario del dominio è definito in [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md).
Gran parte del codice è scritta da agenti di Claude Code, definiti in `.claude/agents/`, ed è
verificata da test e dalla CI su GitHub.

## Contribuire

Due strade, entrambe dalla sezione Issues di GitHub:

- **Contenuti:** segnalare un errore su un luogo, un orario o una fonte, o proporre un contenuto.
- **Codice:** aprire una issue prima di una pull request.

Chi apre una pull request accetta le licenze di [`LICENZE.md`](LICENZE.md).

Autore: Stefano Surlinelli.

## Licenze

- Codice: EUPL-1.2 (`LICENSE`, testo italiano in `LICENSE.it.txt`).
- Documentazione e testi del seed: CC BY 4.0.
- Foto, logo delle Mura e nome "Lucca Soul Lab": tutti i diritti riservati.

Dettagli, eccezioni e terze parti in [`LICENZE.md`](LICENZE.md).
