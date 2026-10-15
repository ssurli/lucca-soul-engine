"""Test di `recommender.ranking` — il cuore della Wave 3b.

Copre i criteri di accettazione della wave, ESTESI dopo la diagnosi del
committente su `tests/test_integration_wave3b.py` (l'entropia aggregata
peggiorava perché un luogo a ZERO eventi ma alta pertinenza di contenuto
assorbiva il flusso spostato da un luogo storicamente concentrato):

  a) COLD START: con storico sotto soglia (o assente), il punteggio è
     BIT-IDENTICO a `calcola_score` da solo — ENTRAMBE le quote (storica e
     strutturale) sono spente, non solo quella storica.
  b) la penalità STORICA cresce con la quota del LUOGO (non della singola
     esperienza), a parità di pertinenza di base — con SMOOTHING additivo
     (Laplace): un luogo senza eventi propri riceve comunque una quota
     storica non nulla se il totale mappabile supera la soglia.
  c) la penalità STRUTTURALE penalizza un luogo che domina per pertinenza di
     CONTENUTO attraverso profili diversi (`ARCHETIPI_STRUTTURALI`), anche
     con ZERO eventi storici propri — è il termine che chiude la falla
     diagnosticata.
  d) il limite massimo di penalità COMBINATA (`LIMITE_PESO_COMBINATO_MAX`)
     non ribalta mai un vantaggio di pertinenza enorme, ed è verificato
     anche a runtime (`ValueError` se superato).
  e) VISIBILITÀ NON ACQUISTABILE: test-guard AST su tutte le funzioni che
     concorrono al punteggio (non solo la chiusura `_score`), più un test
     comportamentale di invarianza bit-a-bit ai campi commerciali, con
     QUALUNQUE storico di eventi (non solo cold start).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime, time
from typing import Any

from contracts import BehaviorEvent, EmotionalProfile, ExperienceNode, GraphCandidate, Signal
from experience_engine import rules
from graph.seed_lucca import VOCABOLARIO
from recommender import InMemoryBehaviorEventRepository, costruisci_score_fn
from recommender.ranking import (
    ALPHA_LAPLACE,
    ARCHETIPI_STRUTTURALI,
    LIMITE_PESO_COMBINATO_MAX,
    PESO_STORICO_DEFAULT,
    PESO_STRUTTURA_DEFAULT,
    SOGLIA_MINIMA_EVENTI_MAPPABILI,
    _conteggio_grezzo_per_place,
    _quota_storica_per_place,
    _quota_strutturale_per_place,
)


def _profilo(**overrides: object) -> EmotionalProfile:
    defaults: dict[str, object] = {
        "curiosita": 0.6,
        "contemplazione": 0.5,
        "arte": 0.7,
        "con_bambini": False,
        "tempo_disponibile_min": 180,
    }
    defaults.update(overrides)
    return EmotionalProfile(**defaults)


def _segnale(**overrides: object) -> Signal:
    defaults: dict[str, object] = {
        "meteo": "sereno",
        "affollamento": {},
        "stanchezza": 0.0,
        "ora": time(10, 0),
    }
    defaults.update(overrides)
    return Signal(**defaults)


def _candidato(
    *,
    experience_id: str = "exp-x",
    place_id: str = "luogo-x",
    partner_id: str | None = None,
    prezzo_eur: float | None = None,
    attribuzione: str | None = None,
    partner_abbonamento_attivo: bool = True,
    prenotabile: bool = False,
    temi: list[str] | None = None,
    n_connessioni: int = 1,
) -> GraphCandidate:
    """Costruisce a mano un candidato (stesso principio di
    `experience-engine/tests/test_engine.py::_candidato`): il test di
    invarianza NON deve dipendere da come il grafo popola i campi."""
    esperienza = ExperienceNode(
        id=experience_id,
        titolo="Esperienza X",
        place_id=place_id,
        temi=temi if temi is not None else ["arte", "liuteria"],
        durata_min=40,
        al_chiuso=True,
        accessibile=True,
        partner_id=partner_id,
        prezzo_eur=prezzo_eur,
        partner_abbonamento_attivo=partner_abbonamento_attivo,
        prenotabile=prenotabile,
    )
    return GraphCandidate(
        experience=esperienza,
        place_nome="Luogo",
        connessioni=['Evoca il tema "Arte".'] * n_connessioni,
        attribuzione=attribuzione,
    )


def _eventi_stop(experience_id: str, n: int) -> list[BehaviorEvent]:
    return [
        BehaviorEvent(
            person_id=f"p-{experience_id}-{i}",
            tipo="stop",
            experience_id=experience_id,
            ts=datetime(2026, 7, 1, tzinfo=UTC),
        )
        for i in range(n)
    ]


# --- a) COLD START: bit-identico a calcola_score (ENTRAMBE le quote spente) --


def test_cold_start_repo_vuoto_e_bit_identico_a_calcola_score() -> None:
    repo = InMemoryBehaviorEventRepository()
    candidati = [_candidato(experience_id="exp-1", place_id="luogo-1")]
    score_fn = costruisci_score_fn(repo, candidati, vocabolario=VOCABOLARIO)

    profilo = _profilo()
    segnale = _segnale()
    for cand in candidati:
        # `==` su float voluto: bit-identico, non prossimità.
        assert score_fn(cand, profilo, segnale) == rules.calcola_score(
            cand, profilo, segnale,
            vocabolario=VOCABOLARIO,
        )


def test_cold_start_sotto_soglia_e_bit_identico_a_calcola_score() -> None:
    """Anche con QUALCHE evento (ma sotto `SOGLIA_MINIMA_EVENTI_MAPPABILI`),
    entrambe le quote restano spente per costruzione: il punteggio non deve
    muoversi di un bit rispetto a `calcola_score` da solo."""
    repo = InMemoryBehaviorEventRepository()
    candidato = _candidato(experience_id="exp-1", place_id="luogo-1")
    for evento in _eventi_stop("exp-1", 5):  # peso 2.0 ciascuno: ben sotto la soglia di 20
        repo.record(evento)
    assert sum(repo.conteggio_per_esperienza().values()) < SOGLIA_MINIMA_EVENTI_MAPPABILI

    score_fn = costruisci_score_fn(repo, [candidato], vocabolario=VOCABOLARIO)
    profilo = _profilo()
    segnale = _segnale()
    assert score_fn(candidato, profilo, segnale) == rules.calcola_score(
        candidato, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )


def test_cold_start_evento_non_mappabile_non_esce_dal_cold_start() -> None:
    """Un evento storico su un `experience_id` che NON è tra i candidati
    correnti non è mappabile: non deve contribuire al totale, quindi non
    deve far uscire dal cold start anche se numericamente supererebbe la
    soglia."""
    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("esperienza-scomparsa-dal-grafo", 30):
        repo.record(evento)
    candidato = _candidato(experience_id="exp-1", place_id="luogo-1")
    score_fn = costruisci_score_fn(repo, [candidato], vocabolario=VOCABOLARIO)
    profilo = _profilo()
    segnale = _segnale()
    assert score_fn(candidato, profilo, segnale) == rules.calcola_score(
        candidato, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )


def test_cold_start_spegne_anche_il_termine_strutturale() -> None:
    """Il termine strutturale non dipende da alcun `BehaviorEvent`: dimostra
    che, PRESO DA SOLO, produrrebbe una quota non nulla per un luogo che
    domina per contenuto — eppure `costruisci_score_fn`, in cold start
    (storico sotto soglia), lo tiene comunque spento: "cold start" significa
    "nessuna correzione", non solo "nessuna correzione storica"."""
    dominante = _candidato(
        experience_id="exp-dominante",
        place_id="luogo-dominante",
        temi=["silenzio", "panorama", "arte", "puccini", "artigianato", "liuteria", "con-bambini"],
    )
    generico = _candidato(experience_id="exp-generico", place_id="luogo-generico", temi=["mercato"])

    # Preso da solo, il termine strutturale premia (in negativo, ai fini
    # della quota) nettamente il luogo dominante.
    quota_strutturale_isolata = _quota_strutturale_per_place(
        [dominante, generico],
        vocabolario=VOCABOLARIO,
    )
    assert quota_strutturale_isolata["luogo-dominante"] > 0.0

    # Ma con repo VUOTO (cold start), `costruisci_score_fn` non applica
    # nessuna correzione: bit-identico a `calcola_score`.
    repo = InMemoryBehaviorEventRepository()
    score_fn = costruisci_score_fn(repo, [dominante, generico], vocabolario=VOCABOLARIO)
    profilo = _profilo()
    segnale = _segnale()
    assert score_fn(dominante, profilo, segnale) == rules.calcola_score(
        dominante, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )
    assert score_fn(generico, profilo, segnale) == rules.calcola_score(
        generico, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )


# --- b) PARTE 1: smoothing additivo (Laplace) sulla quota storica ----------


def test_smoothing_da_quota_storica_non_nulla_a_un_luogo_a_zero_eventi_propri() -> None:
    """PARTE 1 del fix: un luogo SENZA eventi propri, ma tra i candidati
    CORRENTI di una richiesta il cui totale mappabile supera la soglia
    (storico concentrato su UN ALTRO luogo), riceve comunque una quota
    storica NON NULLA — a differenza del comportamento pre-fix (quota = 0
    esatto per un luogo senza eventi tracciati)."""
    concentrato = _candidato(experience_id="exp-concentrato", place_id="luogo-concentrato")
    a_zero_eventi = _candidato(experience_id="exp-zero", place_id="luogo-zero-eventi")
    candidati = [concentrato, a_zero_eventi]

    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("exp-concentrato", 30):  # ben sopra soglia
        repo.record(evento)

    grezzo = _conteggio_grezzo_per_place(repo.conteggio_per_esperienza(), candidati)
    assert grezzo.get("luogo-zero-eventi", 0.0) == 0.0  # nessun evento REALE su questo luogo

    quota = _quota_storica_per_place(grezzo, candidati, ALPHA_LAPLACE)
    assert quota["luogo-zero-eventi"] > 0.0, (
        "lo smoothing di Laplace deve rendere non nulla la quota di un "
        "luogo senza eventi propri, quando il totale mappabile è oltre soglia"
    )
    assert quota["luogo-zero-eventi"] < quota["luogo-concentrato"], (
        "un luogo a zero eventi propri deve comunque restare MENO penalizzato "
        "di un luogo che concentra davvero lo storico"
    )


def test_penalita_storica_cresce_con_la_quota_del_luogo() -> None:
    """A parità di pertinenza di base (stessi temi/durata/accessibilità/
    al_chiuso, `signal.affollamento` vuoto => stesso `calcola_score`) e a
    parità di quota STRUTTURALE (stessi temi di default => stesso
    pareggio strutturale per entrambi i luoghi), il luogo con più storico
    concentrato riceve un punteggio finale PIÙ BASSO — e, con lo smoothing,
    anche il luogo "tranquillo" riceve una penalità (piccola, non nulla)."""
    molto_visitato = _candidato(experience_id="exp-a", place_id="luogo-affollato")
    poco_visitato = _candidato(experience_id="exp-b", place_id="luogo-tranquillo")

    profilo = _profilo()
    segnale = _segnale()
    base_a = rules.calcola_score(molto_visitato, profilo, segnale, vocabolario=VOCABOLARIO)
    base_b = rules.calcola_score(poco_visitato, profilo, segnale, vocabolario=VOCABOLARIO)
    assert base_a == base_b  # stessa pertinenza di base: unica variabile è lo storico

    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("exp-a", 30):  # ben sopra SOGLIA_MINIMA_EVENTI_MAPPABILI
        repo.record(evento)

    score_fn = costruisci_score_fn(repo, [molto_visitato, poco_visitato], vocabolario=VOCABOLARIO)
    punteggio_a = score_fn(molto_visitato, profilo, segnale)
    punteggio_b = score_fn(poco_visitato, profilo, segnale)

    assert punteggio_a < base_a  # penalizzato dallo storico concentrato su di lui
    assert punteggio_b < base_b  # smoothing: penalizzato anche se poco, senza storico proprio
    assert punteggio_a < punteggio_b  # la concentrazione REALE pesa comunque di più


def test_quota_aggrega_per_place_non_per_singola_esperienza() -> None:
    """Due esperienze DIVERSE nello stesso luogo devono condividere la
    stessa quota storica E la stessa quota strutturale (aggregate sul
    `place_id`), non quote separate per `experience_id`."""
    esperienza_1 = _candidato(experience_id="exp-1", place_id="piazza-affollata")
    esperienza_2 = _candidato(experience_id="exp-2", place_id="piazza-affollata")

    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("exp-1", 15):
        repo.record(evento)
    for evento in _eventi_stop("exp-2", 15):
        repo.record(evento)

    score_fn = costruisci_score_fn(repo, [esperienza_1, esperienza_2], vocabolario=VOCABOLARIO)
    profilo = _profilo()
    segnale = _segnale()
    # Stesso place_id => stesse quote => stessa penalità (base identica per costruzione).
    assert score_fn(esperienza_1, profilo, segnale) == score_fn(esperienza_2, profilo, segnale)


# --- c) PARTE 2: quota strutturale (dominio per pertinenza di contenuto) ---


def test_archetipi_strutturali_sono_sei_e_diversi_tra_loro() -> None:
    """Guard di documentazione: l'insieme di archetipi è fisso (6, come
    documentato) e ciascuno è effettivamente diverso dagli altri (nessun
    duplicato che renderebbe un archetipo ridondante)."""
    assert len(ARCHETIPI_STRUTTURALI) == 6
    firme = {
        (a.curiosita, a.contemplazione, a.arte, a.con_bambini, a.tempo_disponibile_min)
        for a in ARCHETIPI_STRUTTURALI
    }
    assert len(firme) == len(ARCHETIPI_STRUTTURALI)


def test_quota_strutturale_individua_il_luogo_dominante_per_contenuto() -> None:
    """Un luogo con temi che intersecano OGNI gruppo tematico pesato da
    `calcola_score` (contemplativi, arte, insoliti, bambini) vince tutti gli
    archetipi strutturali contro un luogo dai temi generici ("mercato"): la
    quota strutturale del primo è 1.0, quella del secondo 0.0."""
    dominante = _candidato(
        experience_id="exp-dominante",
        place_id="luogo-dominante",
        temi=["silenzio", "panorama", "arte", "puccini", "artigianato", "liuteria", "con-bambini"],
    )
    generico = _candidato(experience_id="exp-generico", place_id="luogo-generico", temi=["mercato"])

    quota = _quota_strutturale_per_place([dominante, generico], vocabolario=VOCABOLARIO)
    assert quota["luogo-dominante"] == 1.0
    assert quota["luogo-generico"] == 0.0


def test_quota_strutturale_penalizza_un_luogo_a_zero_eventi_storici_propri() -> None:
    """IL CUORE DELLA PARTE 2, la dimostrazione diretta della diagnosi: un
    luogo con ZERO eventi storici propri, ma che domina per pertinenza di
    contenuto attraverso gli archetipi, riceve comunque una penalità nel
    punteggio finale — a patto che il totale storico MAPPABILE (anche se
    concentrato altrove) superi la soglia di cold start."""
    dominante = _candidato(
        experience_id="exp-dominante",
        place_id="luogo-dominante",
        temi=["silenzio", "panorama", "arte", "puccini", "artigianato", "liuteria", "con-bambini"],
    )
    concentrato_altrove = _candidato(
        experience_id="exp-concentrato", place_id="luogo-concentrato", temi=["mercato"]
    )

    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("exp-concentrato", 30):  # zero eventi su "exp-dominante"
        repo.record(evento)

    score_fn = costruisci_score_fn(repo, [dominante, concentrato_altrove], vocabolario=VOCABOLARIO)
    profilo = _profilo()
    segnale = _segnale()

    base_dominante = rules.calcola_score(dominante, profilo, segnale, vocabolario=VOCABOLARIO)
    punteggio_dominante = score_fn(dominante, profilo, segnale)

    assert punteggio_dominante < base_dominante, (
        "un luogo a zero eventi storici propri ma dominante per pertinenza "
        "di contenuto deve comunque essere penalizzato dal termine "
        "strutturale — è esattamente la falla diagnosticata dal committente"
    )


# --- d) limite di penalità combinata ----------------------------------------


def test_penalita_combinata_massima_non_ribalta_un_vantaggio_di_pertinenza_enorme() -> None:
    """Anche nel caso peggiore (entrambe le quote = 1.0 sullo stesso luogo:
    tutto il flusso storico mappabile E dominio strutturale assoluto su un
    solo luogo), la penalità combinata (<= `LIMITE_PESO_COMBINATO_MAX`) non
    deve MAI superare un vantaggio di pertinenza ampio: è un vincolo che
    modula l'ordine, mai un veto assoluto.

    Il vantaggio di pertinenza deve essere costruito su PIÙ assi pesati
    contemporaneamente (contemplazione + arte + curiosità/sorpresa +
    bambini): nessun singolo peso di `calcola_score` supera da solo 0.4
    (`W_CONTEMPLAZIONE`/`W_ARTE` = 0.30 sono i più alti), quindi un
    "vantaggio enorme" che superi `LIMITE_PESO_COMBINATO_MAX` non può
    nascere da un solo tema affine: va fatto convergere il profilo e i temi
    del candidato "popolare" su tutti gli assi a cui il profilo dà peso, e
    tenere il candidato "libero" su temi che non intersecano nessuno dei
    gruppi tematici di `experience_engine.rules`."""
    molto_pertinente_ma_popolare = _candidato(
        experience_id="exp-pop",
        place_id="luogo-popolare",
        temi=["silenzio", "panorama", "arte", "puccini", "artigianato", "liuteria", "con-bambini"],
    )
    poco_pertinente_ma_libero = _candidato(
        experience_id="exp-libero", place_id="luogo-libero", temi=["mercato"]
    )

    profilo = _profilo(arte=1.0, curiosita=1.0, contemplazione=1.0, con_bambini=True)
    segnale = _segnale()
    base_popolare = rules.calcola_score(
        molto_pertinente_ma_popolare, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )
    base_libero = rules.calcola_score(
        poco_pertinente_ma_libero, profilo, segnale,
        vocabolario=VOCABOLARIO,
    )
    assert base_popolare - base_libero > LIMITE_PESO_COMBINATO_MAX

    repo = InMemoryBehaviorEventRepository()
    for evento in _eventi_stop("exp-pop", 50):  # TUTTO il flusso mappabile su un solo luogo
        repo.record(evento)

    score_fn = costruisci_score_fn(
        repo, [molto_pertinente_ma_popolare, poco_pertinente_ma_libero], vocabolario=VOCABOLARIO
    )
    punteggio_popolare = score_fn(molto_pertinente_ma_popolare, profilo, segnale)
    punteggio_libero = score_fn(poco_pertinente_ma_libero, profilo, segnale)

    # Il vantaggio di pertinenza scelto sopra supera il limite massimo di
    # penalità combinata, quindi l'ordine NON si ribalta.
    assert punteggio_popolare > punteggio_libero


def test_costruisci_score_fn_senza_vocabolario_solleva_typeerror() -> None:
    repo = InMemoryBehaviorEventRepository()
    senza_vocabolario: Any = costruisci_score_fn
    try:
        senza_vocabolario(repo, [_candidato()])
    except TypeError:
        return
    raise AssertionError("vocabolario deve essere obbligatorio")


def test_pesi_di_default_rispettano_il_limite_combinato() -> None:
    assert PESO_STORICO_DEFAULT + PESO_STRUTTURA_DEFAULT <= LIMITE_PESO_COMBINATO_MAX


def test_costruisci_score_fn_rifiuta_pesi_oltre_il_limite_combinato() -> None:
    repo = InMemoryBehaviorEventRepository()
    candidati = [_candidato(experience_id="exp-1", place_id="luogo-1")]
    try:
        costruisci_score_fn(
            repo,
            candidati,
            vocabolario=VOCABOLARIO,
            peso_storico=LIMITE_PESO_COMBINATO_MAX,
            peso_struttura=LIMITE_PESO_COMBINATO_MAX,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "costruisci_score_fn doveva rifiutare peso_storico + peso_struttura "
            "> LIMITE_PESO_COMBINATO_MAX con un ValueError"
        )


# --- e) VISIBILITÀ NON ACQUISTABILE ------------------------------------------


#: Stessa lista di `experience-engine/tests/test_engine.py`: ogni nuovo campo
#: commerciale va aggiunto QUI, così il guard cresce insieme ai contratti.
NOMI_COMMERCIALI_VIETATI_NEL_RANKING = (
    "partner_id",
    "partner_abbonamento_attivo",
    "abbonamento",
    "prezzo",
    "prenotabile",
    "prenotazione",
    "booking",
    "commission",
    "commissione",
    "attribuzione",
)


def _codice_senza_docstring(fn: object) -> str:
    """Codice sorgente di `fn` (funzione o closure), docstring esclusa —
    stesso principio di normalizzazione usato per ispezionare `_score`."""
    albero = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    funzione = albero.body[0]
    assert isinstance(funzione, ast.FunctionDef)
    if (
        funzione.body
        and isinstance(funzione.body[0], ast.Expr)
        and isinstance(funzione.body[0].value, ast.Constant)
    ):
        funzione.body = funzione.body[1:]
    return ast.unparse(funzione).lower()


def test_ranking_non_usa_campi_commerciali_ne_attribuzione() -> None:
    """Test-guard: la funzione di ranking restituita da `costruisci_score_fn`
    (la chiusura `_score`) non deve MAI riferirsi a campi commerciali o
    all'attribuzione (che è disclosure per il `reason`, non un input di
    scoring). Si ispeziona il CODICE della funzione (docstring esclusa)."""
    repo = InMemoryBehaviorEventRepository()
    score_fn = costruisci_score_fn(repo, [_candidato()], vocabolario=VOCABOLARIO)

    codice = _codice_senza_docstring(score_fn)
    for vietato in NOMI_COMMERCIALI_VIETATI_NEL_RANKING:
        assert vietato not in codice, f"il ranking non deve riferirsi a '{vietato}'"


def test_quota_strutturale_e_quota_storica_non_usano_campi_commerciali() -> None:
    """Estensione del test-guard AST alle DUE funzioni introdotte da questo
    fix (`_quota_storica_per_place`, `_quota_strutturale_per_place`) e alla
    loro base comune (`_conteggio_grezzo_per_place`): nessuna delle tre deve
    riferirsi a campi commerciali o all'attribuzione. Usano solo
    `calcola_score`, `EmotionalProfile`, `Signal` e
    `candidate.experience.place_id` / `.id` — stesso perimetro già verificato
    per `_score`."""
    for funzione in (
        _conteggio_grezzo_per_place,
        _quota_storica_per_place,
        _quota_strutturale_per_place,
    ):
        codice = _codice_senza_docstring(funzione)
        for vietato in NOMI_COMMERCIALI_VIETATI_NEL_RANKING:
            assert vietato not in codice, (
                f"'{funzione.__name__}' non deve riferirsi a '{vietato}'"
            )


def test_ranking_bit_identico_al_variare_dei_campi_commerciali() -> None:
    """VISIBILITÀ NON ACQUISTABILE (test comportamentale): due candidati
    identici in tutto tranne `partner_id`/`prezzo_eur`/
    `partner_abbonamento_attivo`/`prenotabile` devono ottenere lo STESSO
    punteggio, con QUALUNQUE storico di eventi (non solo cold start)."""
    riferimento = _candidato(experience_id="exp-x", place_id="luogo-x")
    varianti = [
        _candidato(experience_id="exp-x", place_id="luogo-x", partner_id="bottega-1"),
        _candidato(
            experience_id="exp-x", place_id="luogo-x",
            partner_id="bottega-1", partner_abbonamento_attivo=False,
        ),
        _candidato(
            experience_id="exp-x", place_id="luogo-x",
            partner_id="bottega-1", prezzo_eur=25.0, partner_abbonamento_attivo=True,
        ),
        _candidato(experience_id="exp-x", place_id="luogo-x", prenotabile=True),
        _candidato(
            experience_id="exp-x", place_id="luogo-x",
            partner_id="bottega-1", prezzo_eur=999.0, prenotabile=True,
            attribuzione="Offerta da Bottega Rossi, bottega di liuteria.",
        ),
    ]

    profilo = _profilo()
    segnale = _segnale()

    # QUALUNQUE storico di eventi, non solo cold start: 40 eventi "stop" sul
    # place_id condiviso da tutte le varianti (place_id non cambia mai).
    for storico_eventi in ([], _eventi_stop("exp-x", 40)):
        repo = InMemoryBehaviorEventRepository()
        for evento in storico_eventi:
            repo.record(evento)

        candidati_correnti = [riferimento, *varianti]
        score_fn = costruisci_score_fn(repo, candidati_correnti, vocabolario=VOCABOLARIO)

        punteggio_riferimento = score_fn(riferimento, profilo, segnale)
        for variante in varianti:
            assert score_fn(variante, profilo, segnale) == punteggio_riferimento
