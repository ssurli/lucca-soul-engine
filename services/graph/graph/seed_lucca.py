"""Dataset canonico del seed Lucca — FONTE DI VERITÀ UNICA.

Ogni altra via di alimentazione del grafo nasce da questo modulo:

- `graph.source.SeedCandidateSource` lo legge direttamente, in memoria (il
  percorso usato nei test e finché `NEO4J_URI` non è configurato);
- `graph.export_cypher` lo traduce in Cypher versionato
  (`cypher/00_schema.cypher`, `cypher/01_seed_lucca.cypher`), committato e
  rieseguibile da zero con `python -m graph.loader`.

Questo è il modulo dataset di Lucca, selezionato dal registro
(`graph.registro`) quando `CITY_SEED` è "lucca" (il predefinito). Replicare il
motore su un'altra città significa scrivere un nuovo
modulo `seed_<città>.py` che espone un `DATASET: DatasetCitta` (tipi in
`graph.dataset`): la tecnologia (schema, query, loader) non cambia, cambia
solo il contenuto.

Nodi: `Luogo`, `Artista`, `Bottega`, `Tema`, `Esperienza` (`ExperienceNode`,
importato da `contracts`: non è ridefinito qui). `Evento` e `Memoria` sono
nello schema (`cypher/00_schema.cypher`) ma non hanno seed in questa wave:
`Evento` arriva con i segnali reali, `Memoria` con `urban-memory-engineer`
(Wave 2).

Relazioni derivate implicitamente dai campi di `ExperienceNode` (niente
tabelle separate da tenere sincronizzate a mano):
- `SI_SVOLGE_A` da `ExperienceNode.place_id`;
- `EVOCA` (Esperienza -> Tema) da `ExperienceNode.temi` (id di `Tema`);
- `OFFRE` da `ExperienceNode.partner_id` (id di `Bottega`, quando presente).

Relazioni esplicite (non derivabili da un solo campo): `VICINO` tra Luoghi,
`LEGATO_A` tra Artista e Luogo.

Relazioni SEMANTICHE bottega (non di prossimità fisica — vedi diagnosi Aura
del 2026-07-14: densità VICINO troppo bassa e Bottega di Liuteria
irraggiungibile da Puccini per sole connessioni fisiche):
- `EVOCA` (Bottega -> Tema): stesso tipo di relazione delle Esperienze — una
  bottega evoca i temi del suo mestiere anche a prescindere dall'esperienza
  specifica che offre;
- `ISPIRATA_DA` (Bottega -> Artista): relazione NUOVA, non di prossimità.
  Lega una bottega a un artista il cui lavoro ne è l'ispirazione (es. la
  liuteria è ispirata da Puccini e Boccherini). Porta con sé `racconto`, la
  frase italiana che rende esplicita la connessione in `connessioni`.

Queste due relazioni sono ciò che rende raggiungibile, per SOLE connessioni
semantiche (`LEGATO_A`, `SI_SVOLGE_A`, `OFFRE`, `EVOCA`, `ISPIRATA_DA` — mai
`VICINO`), il percorso canonico del White Paper: Puccini -> ... -> Bottega di
Liuteria. Verificato in `graph.topology` e `tests/test_topology.py`.

Marketplace (Wave 3a — `docs/DATA_CONTRACTS.md` §5):
- `HA_ABBONAMENTO` (Bottega -> Partner): relazione NUOVA. Un `Partner` è
  l'entità di ricavo (`Partner.abbonamento_attivo`, importato da
  `contracts`, NON ridefinito qui); la Bottega è l'entità del dominio
  culturale (mestiere, luogo). Le due restano separate perché il modello di
  ricavo (abbonamento di presenza) non deve mai inquinare il nodo che il
  grafo usa per raccontare connessioni semantiche (`EVOCA`, `ISPIRATA_DA`).
  Una Bottega SENZA relazione `HA_ABBONAMENTO` è trattata come sempre
  visibile (default `True`), stessa regola di `ExperienceNode.
  partner_abbonamento_attivo` in `contracts`.
"""

from __future__ import annotations

from datetime import time

from contracts import (
    Curiosita,
    ExperienceNode,
    FasciaApertura,
    Partner,
    Punto,
    TipoCuriosita,
    VocabolarioTemi,
)

from graph.dataset import VICINO_EPOCA_PREDEFINITA as _EPOCA
from graph.dataset import (
    Artista,
    Bottega,
    DatasetCitta,
    Luogo,
    RelazioneBottegaEvoca,
    RelazioneHaAbbonamento,
    RelazioneIspirataDa,
    RelazioneLegatoA,
    RelazioneVicino,
    Tema,
)

__all__ = [
    "Artista",
    "Bottega",
    "DATASET",
    "Luogo",
    "RelazioneBottegaEvoca",
    "RelazioneHaAbbonamento",
    "RelazioneIspirataDa",
    "RelazioneLegatoA",
    "RelazioneVicino",
    "Tema",
]

# `VICINO` non porta uno storico reale: il seed non ha mai registrato QUANDO
# un arco di prossimità fisica è stato scritto. Wave 4 (Urban Intelligence
# Index, indicatore `nuovi_percorsi`) ha bisogno di poter "congelare" uno
# snapshot del grafo a un istante T (vedi `graph.topology.
# non_connected_place_pairs`), quindi ogni arco `VICINO` porta ora
# `creato_il`. Onestà del dato: non si inventa una data reale per gli archi
# del seed iniziale (nessuno ce l'ha), quindi tutti condividono questa unica
# EPOCA convenzionale — "sempre esistiti", non una data vera di scrittura.
# Un futuro arco `VICINO` aggiunto dopo il seed (es. da una curatela che
# arricchisce la prossimità fisica, fuori dal perimetro di questa wave) deve
# invece portare `datetime.now(UTC)` al momento della scrittura: solo da lì
# in poi la data ha un significato storico reale, ed è quello che rende
# possibile distinguere "già connesso all'inizio del periodo" da "connesso
# DA POCO" — la definizione stessa di "nuovo percorso".
VICINO_EPOCA = _EPOCA

# I tipi dei nodi e delle relazioni (`Luogo`, `Artista`, `Bottega`, `Tema`,
# `Relazione*`) vivono in `graph.dataset` (neutri, condivisi da ogni città) e
# sono ri-esportati qui per compatibilità.

# ---------------------------------------------------------------------------
# Luoghi — 24 luoghi reali di Lucca
# ---------------------------------------------------------------------------

# Coordinate (`punto`): dato del committente, rilevato su Google Maps il 22/10/2026.
# Il punto e' l'ingresso o il punto di sosta; note: duomo-san-martino portico;
# san-michele-in-foro e san-frediano facciata; piazza-anfiteatro, piazza-napoleone
# centro piazza; torre-guinigi ingresso oggi in via Guinigi 29; casa-puccini Corte San
# Lorenzo; teatro-del-giglio piazza del Giglio; torre-delle-ore via Fillungo;
# via-fillungo inizio, incrocio con via Santa Croce; baluardo-san-paolino ingresso della
# sortita, via del Pallone; chiesa-san-francesco piazza San Francesco;
# real-collegio ingresso del chiostro; via-del-fosso fontana, Madonna dello Stellario;
# baluardo-santa-croce ingresso della mostra, da via delle Conce sotto il porticato
# della Casermetta; gli altri ingresso. `mura-urbane` non ha un punto: valgono i
# `punti_arrivo` delle esperienze.
LUOGHI: list[Luogo] = [
    Luogo("mura-urbane", "Mura di Lucca", "mura", articolo="le"),
    Luogo(
        "piazza-anfiteatro",
        "Piazza dell'Anfiteatro",
        "piazza",
        articolo="la",
        curiosita=(
            Curiosita(
                testo=(
                    "Uno solo degli ingressi alla piazza ricalca un'antica porta "
                    "dell'anfiteatro romano."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.8453750945062, lon=10.506130836198794),
    ),
    Luogo(
        "torre-guinigi",
        "Torre Guinigi",
        "torre",
        articolo="la",
        curiosita=(
            Curiosita(
                testo=(
                    "Si racconta che il leccio in cima alla torre perse le foglie quando "
                    "Paolo Guinigi fu catturato."
                ),
                tipo=TipoCuriosita.LEGGENDA,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.84385893695291, lon=10.507472634710469),
    ),
    Luogo(
        "duomo-san-martino",
        "Duomo di San Martino",
        "chiesa",
        articolo="il",
        curiosita=(
            Curiosita(
                testo=(
                    "Sul pilastro del portico è inciso un labirinto, con un'iscrizione "
                    "latina che richiama Dedalo e Teseo. Lo si legge come simbolo del "
                    "cammino dell'anima verso la redenzione, lungo la Via Francigena."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.8407348442907, lon=10.50546424867784),
    ),
    Luogo(
        "casa-puccini",
        "Casa Natale di Giacomo Puccini",
        "museo",
        articolo="la",
        punto=Punto(lat=43.843207634585866, lon=10.501333062529884),
    ),
    Luogo(
        "san-michele-in-foro",
        "Chiesa di San Michele in Foro",
        "chiesa",
        articolo="la",
        curiosita=(
            Curiosita(
                testo=(
                    "Si racconta che nell'anello al dito dell'arcangelo, in cima alla "
                    "facciata, sia incastonato un grande smeraldo, visibile al tramonto da "
                    "un punto preciso della piazza."
                ),
                tipo=TipoCuriosita.LEGGENDA,
                fonte="Comune di Lucca, Mappa del centro storico 2024",
                fonte_pubblica=True,
            ),
        ),
        punto=Punto(lat=43.843206920716746, lon=10.502521515682991),
    ),
    Luogo(
        "orto-botanico",
        "Orto Botanico di Lucca",
        "giardino",
        articolo="l'",
        curiosita=(
            Curiosita(
                testo=(
                    "Si racconta che nelle notti di luna piena il fantasma di Lucida Mansi "
                    "attraversi le Mura su un cocchio, per poi sparire nel laghetto "
                    "dell'Orto Botanico."
                ),
                tipo=TipoCuriosita.LEGGENDA,
                fonte='Comune di Lucca, cartina "Le Mura di Lucca"',
                fonte_pubblica=True,
            ),
            # Il ginkgo non e' un luogo ne' un'esperienza (decisione del committente).
            Curiosita(
                testo=(
                    "A pochi passi dall'Orto, in via Elisa, davanti all'ingresso della "
                    "Fondazione Ragghianti, cresce un ginkgo biloba: in autunno le sue foglie "
                    "diventano d'oro."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.84100710602395, lon=10.51019343794917),
    ),
    Luogo(
        "teatro-del-giglio",
        "Teatro del Giglio",
        "teatro",
        articolo="il",
        punto=Punto(lat=43.84062952605113, lon=10.502840967928876),
    ),
    Luogo(
        "palazzo-pfanner",
        "Palazzo Pfanner",
        "giardino",
        articolo="il",
        punto=Punto(lat=43.8455344278912, lon=10.503022099598914),
    ),
    Luogo(
        "san-frediano",
        "Basilica di San Frediano",
        "chiesa",
        articolo="la",
        curiosita=(
            Curiosita(
                testo=(
                    "Nel mosaico della facciata compare anche Giuda, che l'iconografia "
                    "classica non metterebbe in questa scena. Alza la mano destra chiusa, "
                    "con indice e mignolo tesi: il racconto popolare ci vede il gesto delle"
                    " corna."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.84611439494372, lon=10.504828564629559),
    ),
    Luogo(
        "torre-delle-ore",
        "Torre delle Ore",
        "torre",
        articolo="la",
        punto=Punto(lat=43.84341924030429, lon=10.504123087494012),
    ),
    Luogo(
        "piazza-napoleone",
        "Piazza Napoleone",
        "piazza",
        articolo="la",
        punto=Punto(lat=43.841381710949506, lon=10.502460320754349),
    ),
    Luogo(
        "via-fillungo",
        "Via Fillungo",
        "via",
        articolo=None,
        punto=Punto(lat=43.842686481849164, lon=10.504022332247528),
    ),
    Luogo(
        "baluardo-san-paolino",
        "Baluardo San Paolino",
        "mura",
        articolo="il",
        curiosita=(
            Curiosita(
                testo=(
                    "Si racconta che il 12 luglio 1664, festa di San Paolino, i cannoni "
                    "delle Mura spararono per i festeggiamenti senza essere caricati a "
                    "salve, e che solo l'intervento miracoloso del santo salvò la folla "
                    "radunata sotto le Mura."
                ),
                tipo=TipoCuriosita.LEGGENDA,
                fonte='Comune di Lucca, cartina "Le Mura di Lucca"',
                fonte_pubblica=True,
            ),
        ),
        punto=Punto(lat=43.840816169243126, lon=10.496989849819938),
    ),
    Luogo(
        "museo-nazionale-guinigi",
        "Museo Nazionale di Villa Guinigi",
        "museo",
        articolo="il",
        punto=Punto(lat=43.84532590685096, lon=10.51227072450463),
    ),
    # `Luogo.categoria` è una stringa libera (nessuna lista chiusa, nessuna
    # logica la legge: solo scritta sul nodo); "chiesa" e "chiostro" sono i
    # termini più fedeli al luogo.
    Luogo(
        "chiesa-san-francesco",
        "Chiesa di San Francesco",
        "chiesa",
        articolo="la",
        punto=Punto(lat=43.84544716682871, lon=10.510919717837515),
    ),
    Luogo(
        "real-collegio",
        "Real Collegio",
        "chiostro",
        articolo="il",
        punto=Punto(lat=43.846454429687576, lon=10.503858387960499),
    ),
    # Ondata 1c (dati del committente).
    # via Sant'Andrea 58
    Luogo(
        "museo-barsanti-matteucci",
        "Museo Barsanti e Matteucci",
        "museo",
        articolo="il",
        punto=Punto(lat=43.843638790269274, lon=10.507385090128256),
    ),
    Luogo(
        "via-del-fosso",
        "Via del Fosso",
        "via",
        articolo=None,
        punto=Punto(lat=43.84529568253382, lon=10.509682371585473),
    ),
    # Angolo nord-ovest delle Mura, tra Porta San Donato e la Piattaforma San Frediano.
    Luogo(
        "baluardo-santa-croce",
        "Baluardo Santa Croce",
        "mura",
        articolo="il",
        punto=Punto(lat=43.84569128378519, lon=10.497872636788552),
    ),
    Luogo(
        "santi-giovanni-reparata",
        "Chiesa dei Santi Giovanni e Reparata",
        "chiesa",
        articolo="la",
        punto=Punto(lat=43.84119039780105, lon=10.504274232740409),
    ),
    # Ondata 3 (dati del committente, 22/10/2026): punto = ingresso / punto di sosta.
    Luogo(
        "palazzo-bernardini",
        "Palazzo Bernardini",
        "palazzo",
        articolo="il",
        curiosita=(
            Curiosita(
                testo=(
                    "Guarda la finestra a destra del portone: lo stipite di pietra è curvo, "
                    "piegato come se fosse di legno."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
            Curiosita(
                testo=(
                    "Si racconta che, per far posto al palazzo dei Bernardini, fu demolita una "
                    "piccola chiesa che custodiva un'immagine miracolosa della Madonna, e che a "
                    "convincere i committenti fosse stato il diavolo. Tolta la protezione del "
                    "luogo sacro, il diavolo avrebbe toccato lo stipite della finestra e "
                    "l'avrebbe torto come legno morbido, avvertendo che la pietra non sarebbe "
                    "mai più tornata dritta."
                ),
                tipo=TipoCuriosita.LEGGENDA,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.84257809211349, lon=10.50566149655655),
    ),
    Luogo(
        "san-pietro-somaldi",
        "Chiesa di San Pietro Somaldi",
        "chiesa",
        articolo="la",
        curiosita=(
            Curiosita(
                testo=(
                    "Sulla facciata e sugli stipiti del portale principale si vedono tre solchi "
                    "paralleli scavati nella pietra, simili a graffi di artigli."
                ),
                tipo=TipoCuriosita.FATTO,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
            Curiosita(
                testo="Si racconta che siano le unghiate del diavolo.",
                tipo=TipoCuriosita.LEGGENDA,
                fonte="dato del committente",
                fonte_pubblica=False,
            ),
        ),
        punto=Punto(lat=43.84555613789234, lon=10.508002871124265),
    ),
    Luogo(
        "parco-giochi-san-donato",
        "Parco giochi di Porta San Donato",
        "giardino",
        articolo="il",
        punto=Punto(lat=43.84458794966101, lon=10.497221545825257),
    ),
]

# ---------------------------------------------------------------------------
# Artisti
# ---------------------------------------------------------------------------

ARTISTI: list[Artista] = [
    Artista("artista-puccini", "Giacomo Puccini"),
    Artista("artista-boccherini", "Luigi Boccherini"),
    Artista("artista-civitali", "Matteo Civitali"),
    Artista("artista-catalani", "Alfredo Catalani"),
]

# `racconto` + `fonte` (solo due legami): l'unico testo narrativo del grafo che
# può entrare nel motivo. Gli altri legami restano fatti senza racconto.
LEGATO_A: list[RelazioneLegatoA] = [
    RelazioneLegatoA("artista-puccini", "casa-puccini"),
    RelazioneLegatoA(
        "artista-puccini",
        "san-michele-in-foro",
        racconto=(
            "In questa chiesa il giovane Giacomo Puccini dava lezioni d'organo al suo unico "
            "allievo, il sarto Carlo Della Nina; per la festa di San Michele vi si suonano "
            "ancora musiche della famiglia Puccini."
        ),
        fonte='italia.it, pagina "San Michele in Foro"',
    ),
    RelazioneLegatoA("artista-puccini", "teatro-del-giglio"),
    RelazioneLegatoA("artista-boccherini", "san-michele-in-foro"),
    RelazioneLegatoA(
        "artista-boccherini",
        "duomo-san-martino",
        racconto=(
            "Nel 1751, a otto anni, Luigi Boccherini debuttò come voce bianca nelle feste "
            "di Santa Croce, celebrate in questa cattedrale."
        ),
        fonte=(
            'Ministero della Cultura, "Profilo Boccherini"; '
            'Puccini Museum, pagina "Cattedrale di S. Martino"'
        ),
    ),
    RelazioneLegatoA("artista-civitali", "duomo-san-martino"),
    RelazioneLegatoA("artista-catalani", "teatro-del-giglio"),
    # Boccherini è sepolto in San Francesco (fonte: Comune di Lucca). Unico
    # legame aggiunto: ogni connessione in più alza la "sorpresa" nello score
    # e concentrerebbe le visite.
    RelazioneLegatoA("artista-boccherini", "chiesa-san-francesco"),
]

# ---------------------------------------------------------------------------
# Botteghe — 5 botteghe, ciascuna radicata in un luogo del seed
# ---------------------------------------------------------------------------

# Botteghe DIMOSTRATIVE: nessuna corrisponde a un esercizio reale (`fittizio=True`).
# I nomi portano solo il mestiere, senza città né aggettivi d'insegna, così non
# possono essere scambiati per attività esistenti.
BOTTEGHE: list[Bottega] = [
    Bottega(
        "liuteria-lucchese", "Bottega di liuteria", "liuteria", "san-michele-in-foro", fittizio=True
    ),
    Bottega("ceramica-lucca", "Laboratorio di ceramica", "ceramica", "via-fillungo", fittizio=True),
    Bottega("stamperia-lucca", "Stamperia a torchio", "stampa", "piazza-anfiteatro", fittizio=True),
    Bottega("pasticceria-storica", "Pasticceria", "pasticceria", "piazza-napoleone", fittizio=True),
    Bottega(
        "tessitura-lucca", "Laboratorio di tessitura", "tessitura", "san-frediano", fittizio=True
    ),
]

# ---------------------------------------------------------------------------
# Temi
# ---------------------------------------------------------------------------

TEMI: list[Tema] = [
    Tema("verde", "Verde e giardini", etichetta="verde e giardini"),
    Tema("panorama", "Panorama", etichetta="panorama"),
    Tema("storia", "Storia", etichetta="storia"),
    Tema("medievale", "Medievale", etichetta="medioevo"),
    Tema("gastronomia", "Gastronomia", etichetta="gastronomia"),
    Tema("arte", "Arte", etichetta="arte"),
    Tema("silenzio", "Silenzio e contemplazione", etichetta="silenzio e contemplazione"),
    Tema("puccini", "Giacomo Puccini e la musica", etichetta="Giacomo Puccini"),
    Tema("musica", "Musica", etichetta="musica"),
    Tema("romanico", "Romanico", etichetta="romanico"),
    Tema("con-bambini", "Adatto ai bambini", mostra_etichetta=False),
    Tema("artigianato", "Artigianato", etichetta="artigianato"),
    Tema("liuteria", "Liuteria", etichetta="liuteria"),
]

# ---------------------------------------------------------------------------
# Relazioni SEMANTICHE delle botteghe — bottega -> tema, bottega -> artista.
#
# Non di prossimità: sono ciò che rende raggiungibile un artigiano pertinente
# a partire da un artista SENZA passare per `VICINO` (vedi `graph.topology`).
# `BOTTEGA_EVOCA` riusa il tipo di relazione `EVOCA` (come le Esperienze);
# `BOTTEGA_ISPIRATA_DA` introduce il nuovo tipo `ISPIRATA_DA`.
# ---------------------------------------------------------------------------

BOTTEGA_EVOCA: list[RelazioneBottegaEvoca] = [
    RelazioneBottegaEvoca("liuteria-lucchese", "liuteria"),
    RelazioneBottegaEvoca("liuteria-lucchese", "musica"),
    RelazioneBottegaEvoca("liuteria-lucchese", "artigianato"),
    RelazioneBottegaEvoca("ceramica-lucca", "artigianato"),
    RelazioneBottegaEvoca("stamperia-lucca", "artigianato"),
    RelazioneBottegaEvoca("stamperia-lucca", "storia"),
    RelazioneBottegaEvoca("pasticceria-storica", "gastronomia"),
    RelazioneBottegaEvoca("tessitura-lucca", "artigianato"),
    RelazioneBottegaEvoca("tessitura-lucca", "silenzio"),
]

BOTTEGA_ISPIRATA_DA: list[RelazioneIspirataDa] = [
    RelazioneIspirataDa(
        "liuteria-lucchese",
        "artista-puccini",
        "Puccini compose opere; in una bottega di liuteria nascono i violini che le eseguono.",
    ),
    RelazioneIspirataDa(
        "liuteria-lucchese",
        "artista-boccherini",
        "Boccherini fu virtuoso di violoncello: la stessa famiglia di strumenti "
        "che nasce in una bottega di liuteria.",
    ),
]

# ---------------------------------------------------------------------------
# Partner — Wave 3a (marketplace, `docs/DATA_CONTRACTS.md` §5).
#
# 3 partner di esempio, collegati a 3 delle 5 botteghe via `HA_ABBONAMENTO`.
# Deliberatamente NON tutte e 5: le due botteghe restanti (`pasticceria-
# storica`, `tessitura-lucca`) dimostrano il caso "Bottega con `partner_id` su
# un'Esperienza ma nessun nodo `:Partner` collegato" -> `partner_abbonamento_
# attivo` deve restare `True` di default (nessuna leva commerciale attiva
# esplicitamente significa nessun blocco), verificato in `tests/test_source.py`
# e `tests/test_seed_lucca.py`.
#
# `partner-stamperia-lucca` ha `abbonamento_attivo=False` apposta: è il caso
# che deve sparire dai candidati quando l'Experience Engine applica il filtro
# duro (letto da `ExperienceNode.partner_abbonamento_attivo`, MAI qui).
# ---------------------------------------------------------------------------

PARTNERS: list[Partner] = [
    Partner(
        id="partner-liuteria-lucchese",
        nome="Bottega di liuteria — abbonamento presenza",
        abbonamento_attivo=True,
    ),
    Partner(
        id="partner-ceramica-lucca",
        nome="Laboratorio di ceramica — abbonamento presenza",
        abbonamento_attivo=True,
    ),
    Partner(
        id="partner-stamperia-lucca",
        nome="Stamperia a torchio — abbonamento presenza",
        abbonamento_attivo=False,
    ),
]

HA_ABBONAMENTO: list[RelazioneHaAbbonamento] = [
    RelazioneHaAbbonamento("liuteria-lucchese", "partner-liuteria-lucchese"),
    RelazioneHaAbbonamento("ceramica-lucca", "partner-ceramica-lucca"),
    RelazioneHaAbbonamento("stamperia-lucca", "partner-stamperia-lucca"),
]

# ---------------------------------------------------------------------------
# Esperienze — 35 esperienze (>= 15 richieste), mix voluto di al_chiuso,
# accessibile, durata (20-90 min) e temi, per produrre itinerari DIVERSI a
# seconda del profilo e riscritture credibili su pioggia/affollamento.
#
# PRINCIPIO DEI DATI (orari, prezzi, sospensioni): il seed porta l'orario
# INVERNALE (novembre-dicembre), la stagione della demo (sabato 12/12/2026) e
# il caso più restrittivo. L'errore che ne risulta è quello innocuo: d'estate
# si omette un luogo aperto, d'inverno non si manda nessuno davanti a un
# luogo chiuso. `giorno_settimana`: 0 = lunedì. `prezzo_eur` = biglietto
# intero.
#
# Fonti: dati del committente (19-20/10/2026); sito del Comune di Lucca
# (Torre delle Ore chiusa da novembre a febbraio; Boccherini sepolto in San
# Francesco); Puccini Museum per Casa Puccini (orario 1/11-31/1). Le fonti
# per esperienza sono nei commenti. Nessuna esperienza non citata ha fasce:
# nessuna fascia = nessun vincolo orario noto.
# ---------------------------------------------------------------------------


def _fasce(
    giorni: list[int], apertura: tuple[int, int], chiusura: tuple[int, int]
) -> list[FasciaApertura]:
    """Una fascia [apertura, chiusura) per ciascun giorno (0 = lunedì)."""
    return [
        FasciaApertura(giorno_settimana=g, apertura=time(*apertura), chiusura=time(*chiusura))
        for g in giorni
    ]


# Fonte degli orari (`ExperienceNode.fonte_orari`): il NOME della fonte come e'
# citato nei commenti di questo seed, altrimenti "dato del committente". Solo
# testo, mai nel punteggio. Le botteghe dimostrative (orari fittizi fissati dal
# committente) e le esperienze senza fasce portano "dato del committente".
_FONTE_COMMITTENTE = "dato del committente"
_FONTE_COMUNE = "sito del Comune di Lucca"
_FONTE_PUCCINI_MUSEUM = "Puccini Museum"
_FONTE_BARSANTI = "barsantiematteucci.it"
_FONTE_REPARATA = "museocattedralelucca.it"

_TUTTI = [0, 1, 2, 3, 4, 5, 6]
_LUN_SAB = [0, 1, 2, 3, 4, 5]
# Orari DIMOSTRATIVI delle botteghe fittizie (fissati dal committente, non di
# esercizi reali): mar-sab 09:30-12:30 e 15:30-19:00. Il concerto al Giglio
# resta senza orari (evento a orario fisso, non modellato).
_ORARI_BOTTEGA_DEMO = _fasce([1, 2, 3, 4, 5], (9, 30), (12, 30)) + _fasce(
    [1, 2, 3, 4, 5], (15, 30), (19, 0)
)

# Rampe di accesso alle Mura (dato del committente, Google Maps 22/10/2026), per
# `exp-passeggiata-mura` ed `exp-bici-mura`; il primo e' quello della prima tappa.
_PUNTI_RAMPE_MURA: list[Punto] = [
    Punto(lat=43.83975799648603, lon=10.506535046223485),  # Baluardo San Colombano
    Punto(lat=43.84807404345435, lon=10.507089236931973),  # Porta Santa Maria
    Punto(lat=43.841277451100694, lon=10.496706879150684),  # Baluardo San Paolino
    Punto(lat=43.842315738273435, lon=10.497113013689594),  # Piazzale Verdi
    Punto(lat=43.84552607610066, lon=10.514030908363878),  # Casa del Boia
    Punto(lat=43.83882258921756, lon=10.501625645596407),  # Baluardo Santa Maria
]

ESPERIENZE: list[ExperienceNode] = [
    ExperienceNode(
        id="exp-passeggiata-mura",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Passeggiata sulle Mura rinascimentali",
        place_id="mura-urbane",
        temi=["verde", "panorama", "storia"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
        punti_arrivo=_PUNTI_RAMPE_MURA,
    ),
    ExperienceNode(
        id="exp-bici-mura",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Giro in bicicletta sulle Mura",
        place_id="mura-urbane",
        temi=["verde", "con-bambini", "panorama"],
        durata_min=45,
        al_chiuso=False,
        accessibile=True,
        punti_arrivo=_PUNTI_RAMPE_MURA,
    ),
    ExperienceNode(
        # Riscritta (stesso id): in piazza non c'è un mercato quotidiano; i
        # mercatini occasionali sono eventi, non esperienze. Nessun orario.
        id="exp-mercato-anfiteatro",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="L'ovale dell'Anfiteatro romano",
        place_id="piazza-anfiteatro",
        temi=["storia", "medievale"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
    ),
    ExperienceNode(
        id="exp-salita-torre-guinigi",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Salita alla Torre Guinigi tra i lecci",
        place_id="torre-guinigi",
        temi=["panorama", "verde", "storia"],
        durata_min=40,
        al_chiuso=False,
        accessibile=False,
        prezzo_eur=8.0,
        # Tutti i giorni 09:30-16:30 (fonte: dati del committente, 19-20/10/2026).
        orari_apertura=_fasce(_TUTTI, (9, 30), (16, 30)),
    ),
    ExperienceNode(
        id="exp-duomo-volto-santo",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il Volto Santo e il labirinto del Duomo",
        place_id="duomo-san-martino",
        temi=["arte", "medievale", "silenzio"],
        durata_min=35,
        al_chiuso=True,
        accessibile=True,
        # Lun-sab 10:00-18:00; dom 12:00-18:00 (fonte: dati del committente).
        orari_apertura=_fasce(_LUN_SAB, (10, 0), (18, 0)) + _fasce([6], (12, 0), (18, 0)),
    ),
    ExperienceNode(
        id="exp-casa-puccini-visita",
        fonte_orari=_FONTE_PUCCINI_MUSEUM,
        titolo="Le stanze di Giacomo Puccini",
        place_id="casa-puccini",
        temi=["puccini", "musica", "storia"],
        durata_min=50,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
        prezzo_eur=9.0,
        # Orario 1/11-31/1 (fonte: Puccini Museum): lun, mer, gio 10-14; ven, sab,
        # dom 10-17; martedì chiuso.
        orari_apertura=_fasce([0, 2, 3], (10, 0), (14, 0)) + _fasce([4, 5, 6], (10, 0), (17, 0)),
    ),
    ExperienceNode(
        id="exp-concerto-giglio",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Un'aria all'opera del Giglio",
        place_id="teatro-del-giglio",
        temi=["puccini", "musica", "arte"],
        durata_min=90,
        al_chiuso=True,
        accessibile=True,
        prezzo_eur=25.0,
    ),
    ExperienceNode(
        id="exp-facciata-san-michele",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La facciata scolpita di San Michele in Foro",
        place_id="san-michele-in-foro",
        temi=["arte", "medievale", "romanico"],
        durata_min=25,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-orto-botanico-silenzio",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Un'ora di silenzio tra le piante secolari",
        place_id="orto-botanico",
        temi=["verde", "silenzio"],
        durata_min=45,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
        prezzo_eur=6.0,
        # Ven, sab, dom 11:00-16:00 (fonte: dati del committente).
        orari_apertura=_fasce([4, 5, 6], (11, 0), (16, 0)),
    ),
    ExperienceNode(
        id="exp-orto-botanico-bambini",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Caccia al tesoro botanica per famiglie",
        place_id="orto-botanico",
        temi=["con-bambini", "verde"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
        prezzo_eur=6.0,
        # Ven, sab, dom 11:00-16:00 (fonte: dati del committente).
        orari_apertura=_fasce([4, 5, 6], (11, 0), (16, 0)),
    ),
    ExperienceNode(
        id="exp-giardino-pfanner",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il giardino barocco di Palazzo Pfanner",
        place_id="palazzo-pfanner",
        temi=["verde", "arte", "panorama"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
        # Biglietto unico giardino e museo. Fascia "luce del giorno" invernale,
        # tutti i giorni 08:00-16:30: giardino privato, di sera chiuso.
        prezzo_eur=10.0,
        orari_apertura=_fasce(_TUTTI, (8, 0), (16, 30)),
    ),
    ExperienceNode(
        id="exp-mosaico-san-frediano",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il mosaico dorato di San Frediano",
        place_id="san-frediano",
        temi=["arte", "medievale", "romanico"],
        durata_min=25,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-meccanismo-torre-ore",
        fonte_orari=_FONTE_COMUNE,
        titolo="Il meccanismo ottocentesco della Torre delle Ore",
        place_id="torre-delle-ore",
        temi=["storia", "panorama"],
        durata_min=35,
        al_chiuso=True,
        accessibile=False,
        prezzo_eur=8.0,
        # Chiusa da novembre a febbraio (fonte: sito del Comune di Lucca): esiste
        # ma in questo periodo non è visitabile.
        sospesa=True,
    ),
    ExperienceNode(
        id="exp-piazza-napoleone",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La piazza granducale e i suoi platani",
        place_id="piazza-napoleone",
        temi=["storia", "verde"],
        durata_min=20,
        al_chiuso=False,
        accessibile=True,
    ),
    ExperienceNode(
        id="exp-struscio-fillungo",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Struscio serale in via Fillungo",
        place_id="via-fillungo",
        temi=["gastronomia", "artigianato"],
        durata_min=40,
        al_chiuso=False,
        accessibile=True,
        # Tutti i giorni 17:30-21:00: STIMA (fonte: dati del committente).
        orari_apertura=_fasce(_TUTTI, (17, 30), (21, 0)),
    ),
    ExperienceNode(
        id="exp-tramonto-baluardo",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Tramonto dal Baluardo San Paolino",
        place_id="baluardo-san-paolino",
        temi=["panorama", "silenzio", "verde"],
        durata_min=30,
        al_chiuso=False,
        accessibile=True,
        alimenta_memoria=True,
        # Tutti i giorni 16:00-17:00: il tramonto di dicembre (STIMA: ora del tramonto
        # arrotondata, non da una fonte pubblicata).
        orari_apertura=_fasce(_TUTTI, (16, 0), (17, 0)),
        # Punti di arrivo (dato del committente, Google Maps 22/10/2026), il primo
        # e' quello della prima tappa.
        punti_arrivo=[
            Punto(lat=43.84668153219125, lon=10.502592655389329),
            Punto(lat=43.84060703195673, lon=10.496914055249684),
            Punto(lat=43.84260326710044, lon=10.513896040654814),
            Punto(lat=43.84750898171982, lon=10.513950290731266),
            Punto(lat=43.848580906193554, lon=10.508889574921993),
        ],
    ),
    ExperienceNode(
        id="exp-collezione-villa-guinigi",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La collezione archeologica di Villa Guinigi",
        place_id="museo-nazionale-guinigi",
        temi=["arte", "storia"],
        durata_min=55,
        al_chiuso=True,
        accessibile=True,
        prezzo_eur=6.0,
        # Mar-sab 12:00-18:00 (fonte: dati del committente). Alcune domeniche è
        # aperta: omesse (caso più restrittivo).
        orari_apertura=_fasce([1, 2, 3, 4, 5], (12, 0), (18, 0)),
    ),
    ExperienceNode(
        id="exp-laboratorio-liuteria",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Un violino nasce: laboratorio del liutaio",
        place_id="san-michele-in-foro",
        temi=["liuteria", "artigianato", "musica"],
        durata_min=50,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
        partner_id="liuteria-lucchese",
        prezzo_eur=15.0,
        # `prenotabile` è indipendente dalla presenza di un partner (vedi
        # `docs/DATA_CONTRACTS.md` §2): questa è l'unica esperienza del seed
        # canonico resa prenotabile, a dimostrazione che il campo non si
        # deduce mai da `partner_id`/l'abbonamento della bottega.
        prenotabile=True,
        # Orari DIMOSTRATIVI (fittizi, fissati dal committente), come la bottega.
        orari_apertura=_ORARI_BOTTEGA_DEMO,
    ),
    ExperienceNode(
        id="exp-decorazione-ceramica",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Decora la tua ciotola: bottega di ceramica",
        place_id="via-fillungo",
        temi=["artigianato", "con-bambini"],
        durata_min=45,
        al_chiuso=True,
        accessibile=True,
        partner_id="ceramica-lucca",
        prezzo_eur=20.0,
        orari_apertura=_ORARI_BOTTEGA_DEMO,  # dimostrativi (fittizi)
    ),
    ExperienceNode(
        id="exp-torchio-stamperia",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Una pagina al torchio: la stamperia storica",
        place_id="piazza-anfiteatro",
        temi=["artigianato", "storia"],
        durata_min=35,
        al_chiuso=True,
        accessibile=False,
        partner_id="stamperia-lucca",
        orari_apertura=_ORARI_BOTTEGA_DEMO,  # dimostrativi (fittizi)
    ),
    ExperienceNode(
        id="exp-buccellato-pasticceria",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il buccellato: il dolce di Lucca",
        place_id="piazza-napoleone",
        temi=["gastronomia", "con-bambini"],
        durata_min=20,
        al_chiuso=True,
        accessibile=True,
        alimenta_memoria=True,
        partner_id="pasticceria-storica",
        prezzo_eur=8.0,
        # Orari DIMOSTRATIVI (fittizi, fissati dal committente): mar-dom.
        orari_apertura=(
            _fasce([1, 2, 3, 4, 5, 6], (8, 0), (13, 0))
            + _fasce([1, 2, 3, 4, 5, 6], (15, 30), (19, 30))
        ),
    ),
    ExperienceNode(
        id="exp-telaio-tessitura",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il telaio a mano: tessitura lucchese",
        place_id="san-frediano",
        temi=["artigianato", "silenzio"],
        durata_min=40,
        al_chiuso=True,
        accessibile=True,
        partner_id="tessitura-lucca",
        orari_apertura=_ORARI_BOTTEGA_DEMO,  # dimostrativi (fittizi)
    ),
    # Quattro esperienze di interni (ondata 1b-2). Tutte gratuite, al chiuso,
    # senza partner, senza alimenta_memoria. `accessibile=False` perché
    # l'accessibilità NON è stata verificata: in dubbio si esclude, non si
    # promette. Orari: dati del committente (19-20/10/2026).
    ExperienceNode(
        id="exp-interno-san-michele",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="L'interno di San Michele in Foro",
        place_id="san-michele-in-foro",
        temi=["romanico", "arte"],
        durata_min=20,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=_fasce(_LUN_SAB, (7, 40), (12, 0)) + _fasce(_LUN_SAB, (15, 0), (17, 30)),
    ),
    ExperienceNode(
        id="exp-interno-san-frediano",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La basilica di San Frediano e il fonte lustrale",
        place_id="san-frediano",
        temi=["romanico", "arte", "medievale"],
        durata_min=30,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=(
            _fasce(_LUN_SAB, (8, 30), (12, 0))
            + _fasce(_LUN_SAB, (15, 0), (17, 0))
            + _fasce([6], (10, 30), (17, 0))
        ),
    ),
    ExperienceNode(
        id="exp-chiesa-chiostro-san-francesco",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La chiesa di San Francesco e il suo chiostro",
        place_id="chiesa-san-francesco",
        temi=["musica", "silenzio", "storia"],
        durata_min=30,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=_fasce([5, 6], (10, 0), (19, 0)),
    ),
    ExperienceNode(
        id="exp-chiostro-real-collegio",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il chiostro del Real Collegio",
        place_id="real-collegio",
        temi=["silenzio", "storia"],
        durata_min=20,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=_fasce([0, 1, 2, 3, 4], (9, 0), (12, 0)),
    ),
    # Sei esperienze di contenuto locale (ondata 1c). Tutte senza partner. Fonte:
    # committente; Barsanti: barsantiematteucci.it via committente; Reparata:
    # museocattedralelucca.it via committente. `accessibile=False` dove non
    # verificato (prudente).
    ExperienceNode(
        # Nessuna fascia: accesso 24 ore su 24.
        id="exp-sortita-san-paolino",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La sortita sotterranea del Baluardo San Paolino",
        place_id="baluardo-san-paolino",
        temi=["storia", "con-bambini"],
        durata_min=20,
        al_chiuso=True,
        accessibile=True,
    ),
    ExperienceNode(
        # Ven, sab, dom 11:00-17:00. Accessibilità non verificata.
        id="exp-museo-barsanti-matteucci",
        fonte_orari=_FONTE_BARSANTI,
        titolo="Il motore a scoppio di Barsanti e Matteucci",
        place_id="museo-barsanti-matteucci",
        temi=["storia", "con-bambini"],
        durata_min=45,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=_fasce([4, 5, 6], (11, 0), (17, 0)),
    ),
    ExperienceNode(
        # Stesso luogo del giardino: la regola "una tappa per luogo" le rende
        # alternative. Tutti i giorni 08:00-17:00.
        id="exp-pfanner-dalle-mura",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il giardino Pfanner visto dalle Mura",
        place_id="palazzo-pfanner",
        temi=["verde", "panorama"],
        durata_min=15,
        al_chiuso=False,
        accessibile=False,
        orari_apertura=_fasce(_TUTTI, (8, 0), (17, 0)),
        # Sulle Mura, vicino alla Casermetta San Salvatore (dato del committente,
        # Google Maps 22/10/2026): prevale sul punto del luogo (il giardino).
        punti_arrivo=[Punto(lat=43.846610457117684, lon=10.502497041284132)],
    ),
    ExperienceNode(
        # Nessuna fascia: illuminata la sera.
        id="exp-via-del-fosso",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Via del Fosso: il canale e i ponticelli",
        place_id="via-del-fosso",
        temi=["silenzio", "storia"],
        durata_min=20,
        al_chiuso=False,
        accessibile=False,
    ),
    ExperienceNode(
        # Tutti i giorni 10:00-16:00 (il sito del Comune riporta 16:30: tenuto
        # il più restrittivo). Accessibilità non verificata.
        id="exp-sotterraneo-santa-croce",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo='Il sotterraneo del Baluardo Santa Croce e la mostra "Ri-conoscere le Mura"',
        place_id="baluardo-santa-croce",
        temi=["storia"],
        durata_min=40,
        al_chiuso=True,
        accessibile=False,
        orari_apertura=_fasce(_TUTTI, (10, 0), (16, 0)),
    ),
    ExperienceNode(
        # Tutti i giorni 10:00-18:00.
        id="exp-santi-giovanni-reparata",
        fonte_orari=_FONTE_REPARATA,
        titolo="La chiesa dei Santi Giovanni e Reparata e l'area archeologica",
        place_id="santi-giovanni-reparata",
        temi=["storia", "arte", "romanico"],
        durata_min=40,
        al_chiuso=True,
        accessibile=False,
        prezzo_eur=4.0,
        orari_apertura=_fasce(_TUTTI, (10, 0), (18, 0)),
    ),
    # Tre esperienze all'aperto (ondata 3, dati del committente 22/10/2026). Gratuite
    # (come le altre gratuite del seed: `prezzo_eur` omesso), senza partner,
    # `accessibile=False` (non verificato), nessun vincolo orario noto (lista vuota).
    # Il parco giochi e' "sempre aperto": nessuna fascia, come deciso dal committente.
    ExperienceNode(
        id="exp-finestra-bernardini",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="La finestra storta di Palazzo Bernardini",
        place_id="palazzo-bernardini",
        temi=["storia"],
        durata_min=10,
        al_chiuso=False,
        accessibile=False,
    ),
    ExperienceNode(
        id="exp-solchi-san-pietro-somaldi",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="I solchi sulla porta di San Pietro Somaldi",
        place_id="san-pietro-somaldi",
        temi=["storia", "romanico"],
        durata_min=10,
        al_chiuso=False,
        accessibile=False,
    ),
    ExperienceNode(
        id="exp-parco-giochi-san-donato",
        fonte_orari=_FONTE_COMMITTENTE,
        titolo="Il parco giochi di Porta San Donato",
        place_id="parco-giochi-san-donato",
        temi=["con-bambini", "verde"],
        durata_min=45,
        al_chiuso=False,
        accessibile=False,
    ),
]

# ---------------------------------------------------------------------------
# Vicinanze — grafo di prossimità tra luoghi (una riga per coppia)
#
# Corretto dopo la diagnosi su Aura del 2026-07-14: densità media 2,3
# vicini/luogo (una CATENA) con 4 vicoli ciechi (casa-puccini, orto-botanico,
# baluardo-san-paolino, museo-nazionale-guinigi, tutti a 1 solo vicino).
# Lucca dentro le Mura è un centro storico compatto (~1,6 x 1,1 km): quasi
# ogni luogo del seed è raggiungibile a piedi in ~10-15 min da ogni altro.
# `mura-urbane` è un anello che tocca la maggior parte dei luoghi (hub), non
# un nodo di passaggio isolato. Target: densità media >= 4, nessun luogo con
# < 2 vicini (verificato in `tests/test_topology.py`). Le distanze restano
# plausibili (nessuna scorciatoia impossibile), ma la città È piccola.
# ---------------------------------------------------------------------------

VICINO: list[RelazioneVicino] = [
    # mura-urbane: l'anello, hub della rete (8 vicini)
    RelazioneVicino("mura-urbane", "baluardo-san-paolino", 50),
    RelazioneVicino("mura-urbane", "orto-botanico", 100),
    RelazioneVicino("mura-urbane", "piazza-napoleone", 400),
    RelazioneVicino("mura-urbane", "museo-nazionale-guinigi", 450),
    RelazioneVicino("mura-urbane", "palazzo-pfanner", 350),
    RelazioneVicino("mura-urbane", "san-frediano", 400),
    RelazioneVicino("mura-urbane", "torre-guinigi", 600),
    RelazioneVicino("mura-urbane", "casa-puccini", 550),
    # piazza-anfiteatro
    RelazioneVicino("piazza-anfiteatro", "torre-guinigi", 300),
    RelazioneVicino("piazza-anfiteatro", "san-frediano", 250),
    RelazioneVicino("piazza-anfiteatro", "via-fillungo", 150),
    RelazioneVicino("piazza-anfiteatro", "museo-nazionale-guinigi", 500),
    RelazioneVicino("piazza-anfiteatro", "san-michele-in-foro", 350),
    # via-fillungo (l'asse commerciale, hub)
    RelazioneVicino("via-fillungo", "torre-delle-ore", 100),
    RelazioneVicino("via-fillungo", "san-michele-in-foro", 200),
    RelazioneVicino("via-fillungo", "casa-puccini", 200),
    RelazioneVicino("via-fillungo", "torre-guinigi", 250),
    RelazioneVicino("via-fillungo", "piazza-napoleone", 300),
    # san-michele-in-foro (hub centrale)
    RelazioneVicino("san-michele-in-foro", "duomo-san-martino", 300),
    RelazioneVicino("san-michele-in-foro", "piazza-napoleone", 250),
    RelazioneVicino("san-michele-in-foro", "torre-delle-ore", 200),
    RelazioneVicino("san-michele-in-foro", "teatro-del-giglio", 350),
    # duomo-san-martino
    RelazioneVicino("duomo-san-martino", "casa-puccini", 200),
    RelazioneVicino("duomo-san-martino", "torre-delle-ore", 350),
    RelazioneVicino("duomo-san-martino", "piazza-napoleone", 450),
    RelazioneVicino("duomo-san-martino", "museo-nazionale-guinigi", 600),
    # casa-puccini (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("casa-puccini", "teatro-del-giglio", 400),
    # teatro-del-giglio
    RelazioneVicino("teatro-del-giglio", "piazza-napoleone", 100),
    RelazioneVicino("teatro-del-giglio", "torre-delle-ore", 300),
    # piazza-napoleone (hub)
    RelazioneVicino("piazza-napoleone", "torre-delle-ore", 250),
    # torre-delle-ore (hub)
    RelazioneVicino("torre-delle-ore", "torre-guinigi", 300),
    # torre-guinigi
    RelazioneVicino("torre-guinigi", "palazzo-pfanner", 400),
    # palazzo-pfanner (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("palazzo-pfanner", "san-frediano", 150),
    RelazioneVicino("palazzo-pfanner", "baluardo-san-paolino", 300),
    # san-frediano
    RelazioneVicino("san-frediano", "baluardo-san-paolino", 350),
    RelazioneVicino("san-frediano", "orto-botanico", 500),
    # baluardo-san-paolino (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("baluardo-san-paolino", "orto-botanico", 400),
    # orto-botanico (ex vicolo cieco: ora 4 vicini)
    RelazioneVicino("orto-botanico", "museo-nazionale-guinigi", 700),
    # museo-nazionale-guinigi (ex vicolo cieco: ora 4 vicini)
    #
    # STIME (ondata 1b-2): le distanze dei due luoghi nuovi sono stime
    # dichiarate, non misure; saranno sostituite dalle coordinate in
    # un'ondata successiva.
    # chiesa-san-francesco
    RelazioneVicino("chiesa-san-francesco", "museo-nazionale-guinigi", 250),
    RelazioneVicino("chiesa-san-francesco", "mura-urbane", 300),
    RelazioneVicino("chiesa-san-francesco", "piazza-anfiteatro", 400),
    RelazioneVicino("chiesa-san-francesco", "torre-guinigi", 450),
    RelazioneVicino("chiesa-san-francesco", "via-fillungo", 500),
    # real-collegio
    RelazioneVicino("real-collegio", "san-frediano", 100),
    RelazioneVicino("real-collegio", "palazzo-pfanner", 200),
    RelazioneVicino("real-collegio", "mura-urbane", 250),
    RelazioneVicino("real-collegio", "piazza-anfiteatro", 300),
    RelazioneVicino("real-collegio", "via-fillungo", 350),
    #
    # STIME (ondata 1c): distanze in linea d'aria dei 4 luoghi nuovi, dichiarate
    # stime (fonte: committente), non misure. `creato_il` = epoca di default (non
    # una data reale): questi archi NON contano come nuovi percorsi nell'Index.
    # museo-barsanti-matteucci
    RelazioneVicino("museo-barsanti-matteucci", "torre-guinigi", 100),
    RelazioneVicino("museo-barsanti-matteucci", "via-fillungo", 200),
    RelazioneVicino("museo-barsanti-matteucci", "piazza-anfiteatro", 250),
    RelazioneVicino("museo-barsanti-matteucci", "chiesa-san-francesco", 350),
    RelazioneVicino("museo-barsanti-matteucci", "museo-nazionale-guinigi", 450),
    # via-del-fosso
    RelazioneVicino("via-del-fosso", "mura-urbane", 100),
    RelazioneVicino("via-del-fosso", "chiesa-san-francesco", 100),
    RelazioneVicino("via-del-fosso", "orto-botanico", 150),
    RelazioneVicino("via-del-fosso", "museo-nazionale-guinigi", 200),
    RelazioneVicino("via-del-fosso", "piazza-anfiteatro", 450),
    # baluardo-santa-croce
    RelazioneVicino("baluardo-santa-croce", "mura-urbane", 50),
    RelazioneVicino("baluardo-santa-croce", "palazzo-pfanner", 450),
    RelazioneVicino("baluardo-santa-croce", "casa-puccini", 450),
    RelazioneVicino("baluardo-santa-croce", "san-michele-in-foro", 550),
    RelazioneVicino("baluardo-santa-croce", "real-collegio", 600),
    RelazioneVicino("baluardo-santa-croce", "san-frediano", 650),
    RelazioneVicino("baluardo-santa-croce", "piazza-anfiteatro", 750),
    # santi-giovanni-reparata
    RelazioneVicino("santi-giovanni-reparata", "duomo-san-martino", 100),
    RelazioneVicino("santi-giovanni-reparata", "piazza-napoleone", 200),
    RelazioneVicino("santi-giovanni-reparata", "casa-puccini", 250),
    RelazioneVicino("santi-giovanni-reparata", "teatro-del-giglio", 250),
    RelazioneVicino("santi-giovanni-reparata", "san-michele-in-foro", 300),
    # Ondata 3 (compito 8): due archi per ciascuno dei 3 luoghi nuovi, verso i primi due
    # vicini per distanza a piedi. Fonte: metri CALCOLATI dai punti del committente
    # (22/10/2026) con `contracts.distanza_a_piedi_m` (linea d'aria x 1,3, arrotondata ai
    # 10 m), non misurati. `creato_il` = epoca di default come gli altri archi del seed.
    RelazioneVicino("palazzo-bernardini", "via-fillungo", 170),
    RelazioneVicino("palazzo-bernardini", "torre-delle-ore", 200),
    RelazioneVicino("san-pietro-somaldi", "via-del-fosso", 180),
    RelazioneVicino("san-pietro-somaldi", "piazza-anfiteatro", 200),
    RelazioneVicino("parco-giochi-san-donato", "baluardo-santa-croce", 170),
    RelazioneVicino("parco-giochi-san-donato", "casa-puccini", 470),
]

# ---------------------------------------------------------------------------
# Integrità referenziale — controllata a import-time: il seed è la fonte di
# verità, un errore qui deve rompere subito (fail fast), non silenziosamente
# a runtime dentro Neo4j.
# ---------------------------------------------------------------------------


def _validate() -> None:
    luoghi_ids = {luogo.id for luogo in LUOGHI}
    artisti_ids = {a.id for a in ARTISTI}
    botteghe_ids = {b.id for b in BOTTEGHE}
    temi_ids = {t.id for t in TEMI}
    esperienze_ids = {e.id for e in ESPERIENZE}
    partner_ids = {p.id for p in PARTNERS}

    assert len(luoghi_ids) == len(LUOGHI), "id di Luogo duplicati nel seed"
    assert len(artisti_ids) == len(ARTISTI), "id di Artista duplicati nel seed"
    assert len(botteghe_ids) == len(BOTTEGHE), "id di Bottega duplicati nel seed"
    assert len(temi_ids) == len(TEMI), "id di Tema duplicati nel seed"
    assert len(esperienze_ids) == len(ESPERIENZE), "id di Esperienza duplicati nel seed"
    assert len(partner_ids) == len(PARTNERS), "id di Partner duplicati nel seed"

    for bottega in BOTTEGHE:
        assert bottega.place_id in luoghi_ids, f"{bottega.id}: place_id sconosciuto"

    for esperienza in ESPERIENZE:
        assert esperienza.place_id in luoghi_ids, (
            f"{esperienza.id}: place_id {esperienza.place_id!r} non è un Luogo del seed"
        )
        for tema_id in esperienza.temi:
            assert tema_id in temi_ids, f"{esperienza.id}: tema {tema_id!r} non è nel seed"
        if esperienza.partner_id is not None:
            assert esperienza.partner_id in botteghe_ids, (
                f"{esperienza.id}: partner_id {esperienza.partner_id!r} non è una Bottega del seed"
            )

    for vicino in VICINO:
        assert vicino.da_id in luoghi_ids, f"VICINO: luogo sconosciuto {vicino.da_id!r}"
        assert vicino.a_id in luoghi_ids, f"VICINO: luogo sconosciuto {vicino.a_id!r}"
        assert vicino.metri >= 0, f"VICINO {vicino.da_id}->{vicino.a_id}: metri negativi"
        assert vicino.creato_il.tzinfo is not None, (
            f"VICINO {vicino.da_id}->{vicino.a_id}: creato_il non timezone-aware "
            "(serve per confrontarlo con datetime.now(UTC) negli snapshot)"
        )

    for legato in LEGATO_A:
        assert legato.artista_id in artisti_ids, (
            f"LEGATO_A: artista sconosciuto {legato.artista_id!r}"
        )
        assert legato.luogo_id in luoghi_ids, f"LEGATO_A: luogo sconosciuto {legato.luogo_id!r}"

    for evoca in BOTTEGA_EVOCA:
        assert evoca.bottega_id in botteghe_ids, (
            f"BOTTEGA_EVOCA: bottega sconosciuta {evoca.bottega_id!r}"
        )
        assert evoca.tema_id in temi_ids, f"BOTTEGA_EVOCA: tema sconosciuto {evoca.tema_id!r}"

    for ispirata in BOTTEGA_ISPIRATA_DA:
        assert ispirata.bottega_id in botteghe_ids, (
            f"BOTTEGA_ISPIRATA_DA: bottega sconosciuta {ispirata.bottega_id!r}"
        )
        assert ispirata.artista_id in artisti_ids, (
            f"BOTTEGA_ISPIRATA_DA: artista sconosciuto {ispirata.artista_id!r}"
        )
        assert ispirata.racconto, (
            f"BOTTEGA_ISPIRATA_DA {ispirata.bottega_id}->{ispirata.artista_id}: racconto vuoto"
        )

    for abbonamento in HA_ABBONAMENTO:
        assert abbonamento.bottega_id in botteghe_ids, (
            f"HA_ABBONAMENTO: bottega sconosciuta {abbonamento.bottega_id!r}"
        )
        assert abbonamento.partner_id in partner_ids, (
            f"HA_ABBONAMENTO: partner sconosciuto {abbonamento.partner_id!r}"
        )
    bottega_con_abbonamento = [rel.bottega_id for rel in HA_ABBONAMENTO]
    assert len(bottega_con_abbonamento) == len(set(bottega_con_abbonamento)), (
        "HA_ABBONAMENTO: una Bottega non può avere più di un Partner"
    )
    assert any(not p.abbonamento_attivo for p in PARTNERS), (
        "seed marketplace: serve almeno un Partner con abbonamento_attivo=False "
        "per poter testare il filtro duro (vedi CLAUDE.md, filtro sui candidati)"
    )


_validate()

# Vocabolario tematico di Lucca: sono i vocabolari che prima vivevano nel
# motore (experience-engine), spostati qui perché dato della città. Ogni id
# deve essere un `Tema` di questo dataset (verificato da `DatasetCitta`).
VOCABOLARIO = VocabolarioTemi(
    contemplativi=frozenset({"silenzio", "verde", "panorama", "romanico"}),
    arte=frozenset({"arte", "puccini", "musica", "romanico", "liuteria"}),
    insoliti=frozenset({"artigianato", "liuteria", "romanico", "medievale"}),
    verde=frozenset({"verde", "panorama"}),
    bambini="con-bambini",
)

DATASET = DatasetCitta(
    nome="lucca",
    luoghi=LUOGHI,
    artisti=ARTISTI,
    legato_a=LEGATO_A,
    botteghe=BOTTEGHE,
    temi=TEMI,
    bottega_evoca=BOTTEGA_EVOCA,
    bottega_ispirata_da=BOTTEGA_ISPIRATA_DA,
    partners=PARTNERS,
    ha_abbonamento=HA_ABBONAMENTO,
    esperienze=ESPERIENZE,
    vicino=VICINO,
    vicino_epoca=VICINO_EPOCA,
    # Bottega esistente nel dataset (dimostrativa, `fittizio=True`): bersaglio
    # della memoria di prova di Urban Memory.
    id_esempio_memoria="liuteria-lucchese",
    vocabolario=VOCABOLARIO,
)


# ---------------------------------------------------------------------------
# Lookup — indicizzazioni comode per `graph.source` e `graph.export_cypher`
# ---------------------------------------------------------------------------


def luogo_by_id(place_id: str) -> Luogo | None:
    return next((luogo for luogo in LUOGHI if luogo.id == place_id), None)


def tema_by_id(tema_id: str) -> Tema | None:
    return next((t for t in TEMI if t.id == tema_id), None)


def bottega_by_id(bottega_id: str) -> Bottega | None:
    return next((b for b in BOTTEGHE if b.id == bottega_id), None)


def artisti_per_luogo(place_id: str) -> list[Artista]:
    artisti_ids = {rel.artista_id for rel in LEGATO_A if rel.luogo_id == place_id}
    return [a for a in ARTISTI if a.id in artisti_ids]


def vicini_di(place_id: str) -> list[tuple[str, int]]:
    """Luoghi vicini a `place_id` (relazione trattata come non orientata)."""
    risultato: list[tuple[str, int]] = []
    for vicino in VICINO:
        if vicino.da_id == place_id:
            risultato.append((vicino.a_id, vicino.metri))
        elif vicino.a_id == place_id:
            risultato.append((vicino.da_id, vicino.metri))
    return risultato


def partner_by_id(partner_id: str) -> Partner | None:
    return next((p for p in PARTNERS if p.id == partner_id), None)


def abbonamento_attivo_per_bottega(bottega_id: str | None) -> bool:
    """`True` di default (nessun partner = sempre visibile), come
    `ExperienceNode.partner_abbonamento_attivo` in `contracts`. `bottega_id`
    è l'id di `Bottega`, non di `Partner` (`ExperienceNode.partner_id`
    referenzia una Bottega, coerente con la relazione `OFFRE`). Usata da
    `graph.source.SeedCandidateSource` per popolare il booleano denormalizzato
    senza alcuna logica di scoring: è un puro fatto del grafo."""
    if bottega_id is None:
        return True
    rel = next((r for r in HA_ABBONAMENTO if r.bottega_id == bottega_id), None)
    if rel is None:
        return True
    partner = partner_by_id(rel.partner_id)
    if partner is None:
        return True
    return partner.abbonamento_attivo
