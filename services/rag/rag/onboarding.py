"""Onboarding conversazionale -> EmotionalProfile.

L'LLM **dialoga, non decide**: qui non c'è alcuna scelta di tappe, solo la
lettura di un profilo emozionale da risposte in italiano colloquiale. Il
percorso è deterministico e testabile offline (nessuna chiamata LLM):
`profile_from_answers` fa parsing robusto di testo libero e non solleva mai
un'eccezione per un testo "strano" — degrada sempre a un default prudente.

Le domande (`DOMANDE`) sono versionate: `domanda_id` è stabile e non va
rinominato una volta pubblicato (rompe le risposte già raccolte). Se una
domanda cambia formulazione ma resta concettualmente la stessa, il suo
`domanda_id` resta invariato.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from contracts import EmotionalProfile, OnboardingRequest

__all__ = ["Domanda", "DOMANDE", "DOMANDE_BY_ID", "profile_from_answers"]


@dataclass(frozen=True)
class Domanda:
    """Una domanda dell'onboarding conversazionale.

    `campo` indica a quale campo di `EmotionalProfile` contribuisce la
    risposta (documentazione del mapping, non usato per il parsing stesso:
    ogni campo ha una logica di lettura dedicata in `profile_from_answers`).
    """

    domanda_id: str
    testo: str
    campo: str


# Mapping domanda -> campo di EmotionalProfile:
#   perdersi          -> curiosita
#   silenzio_musica    -> contemplazione
#   bellezza_storie    -> arte
#   bambini            -> con_bambini
#   tempo              -> tempo_disponibile_min
#   accessibilita      -> accessibilita_richiesta
#   firenze            -> ha_gia_visto_firenze
DOMANDE: list[Domanda] = [
    Domanda(
        domanda_id="perdersi",
        testo="Hai voglia di perderti tra vicoli e piazze, senza un itinerario fisso?",
        campo="curiosita",
    ),
    Domanda(
        domanda_id="silenzio_musica",
        testo="Cerchi il silenzio di una chiesa o preferisci un luogo con musica dal vivo?",
        campo="contemplazione",
    ),
    Domanda(
        domanda_id="bellezza_storie",
        testo="Ti colpisce di più la bellezza di un'opera o la storia che porta con sé?",
        campo="arte",
    ),
    Domanda(
        domanda_id="bambini",
        testo="Viaggi con bambini?",
        campo="con_bambini",
    ),
    Domanda(
        domanda_id="tempo",
        testo="Quanto tempo hai a disposizione oggi?",
        campo="tempo_disponibile_min",
    ),
    Domanda(
        domanda_id="accessibilita",
        testo="Hai bisogno di percorsi accessibili, senza scale né barriere?",
        campo="accessibilita_richiesta",
    ),
    Domanda(
        domanda_id="firenze",
        testo="Hai già visto Firenze?",
        campo="ha_gia_visto_firenze",
    ),
]

DOMANDE_BY_ID: dict[str, Domanda] = {d.domanda_id: d for d in DOMANDE}


# ---------------------------------------------------------------------------
# Default prudenti quando una risposta manca o non è interpretabile.
# Documentati qui perché sono una scelta di prodotto, non un dettaglio tecnico.
# ---------------------------------------------------------------------------
DEFAULT_CURIOSITA = 0.5
DEFAULT_CONTEMPLAZIONE = 0.5
DEFAULT_ARTE = 0.5
DEFAULT_CON_BAMBINI = False
DEFAULT_TEMPO_MIN = 120
DEFAULT_ACCESSIBILITA = False
DEFAULT_HA_GIA_VISTO_FIRENZE = False


def _normalizza(testo: str) -> str:
    """Minuscolo, senza accenti: rende il matching di parole chiave robusto
    a "sì"/"si", "città"/"citta", ecc."""
    if not testo:
        return ""
    decomposto = unicodedata.normalize("NFKD", testo)
    senza_accenti = "".join(c for c in decomposto if not unicodedata.combining(c))
    return senza_accenti.lower().strip()


_RE_FORTE = re.compile(r"\b(tantissimo|moltissimo|tanto|estremamente|assolutamente)\b")
_RE_MOLTO = re.compile(r"\bmolto\b")
_RE_POCO = re.compile(r"\bpoco\b|\bpochino\b")
_RE_UN_PO = re.compile(r"\bun\s*po['`]?\b")
_RE_SI_MODERATO = re.compile(r"\b(si|certo|ovvio|volentieri|abbastanza|diciamo)\b")
_RE_NO_FORTE = re.compile(r"\b(per\s*niente|niente\s*affatto|assolutamente\s*no|zero)\b")
_RE_NO = re.compile(r"\bno\b|\bnon\b|\bmai\b")
_RE_INIZIO_SI = re.compile(r"^si\b")
_RE_INIZIO_NO = re.compile(r"^(?:no|non)\b")


def _parse_intensita(testo: str, default: float) -> float:
    """Parsing robusto di un'intensità 0..1 da testo libero italiano
    (sì/no/molto/poco/un po'...). Non solleva mai eccezioni: testo vuoto o
    non interpretabile -> `default`."""
    try:
        t = _normalizza(testo)
        if not t:
            return default
        if _RE_NO_FORTE.search(t):
            return 0.0
        if _RE_FORTE.search(t):
            return 0.9
        if _RE_MOLTO.search(t):
            return 0.85
        if _RE_UN_PO.search(t):
            return 0.35
        if _RE_POCO.search(t):
            return 0.2
        if _RE_NO.search(t):
            return 0.05
        if _RE_SI_MODERATO.search(t):
            return 0.75
        return default
    except Exception:
        return default


def _parse_polarita(
    testo: str,
    positivi: tuple[str, ...],
    negativi: tuple[str, ...],
    default: float,
) -> float:
    """Parsing di una scala a due poli (es. silenzio<->musica, bellezza<->storie).
    `positivi` spinge verso 1.0, `negativi` verso 0.0. Mai eccezioni."""
    try:
        t = _normalizza(testo)
        if not t:
            return default
        ha_pos = any(k in t for k in positivi)
        ha_neg = any(k in t for k in negativi)
        if ha_pos and ha_neg:
            return 0.5
        if ha_pos:
            base = 0.8
        elif ha_neg:
            base = 0.2
        else:
            return default
        if _RE_FORTE.search(t) or _RE_MOLTO.search(t):
            return 0.95 if base > 0.5 else 0.05
        if _RE_UN_PO.search(t) or _RE_POCO.search(t):
            return 0.6 if base > 0.5 else 0.4
        return base
    except Exception:
        return default


def _parse_bool(
    testo: str,
    default: bool,
    positivi_extra: tuple[str, ...] = (),
    negativi_extra: tuple[str, ...] = (),
) -> bool:
    """Parsing sì/no robusto, con parole chiave di dominio opzionali
    (es. "bambini"/"figli" implicano sì anche senza un "sì" esplicito).

    Precedenza:
    1. un "sì" o un "no/non" ESPLICITO a inizio risposta (parola intera, dopo
       la normalizzazione) decide per primo: "No, non sono con bambini" è
       False anche se contiene "bambin"; "nonna" o "sicuro" non contano;
    2. altrimenti `negativi_extra`, poi `positivi_extra`;
    3. poi le regex generiche di negazione e di assenso;
    4. altrimenti `default`."""
    try:
        t = _normalizza(testo)
        if not t:
            return default
        if _RE_INIZIO_SI.match(t):
            return True
        if _RE_INIZIO_NO.match(t):
            return False
        if any(k in t for k in negativi_extra):
            return False
        if any(k in t for k in positivi_extra):
            return True
        if _RE_NO_FORTE.search(t) or _RE_NO.search(t):
            return False
        if _RE_SI_MODERATO.search(t) or _RE_FORTE.search(t):
            return True
        return default
    except Exception:
        return default


_NUMERI_ITALIANI = {
    "zero": 0,
    "un": 1,
    "uno": 1,
    "una": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
    "sei": 6,
    "sette": 7,
    "otto": 8,
    "nove": 9,
    "dieci": 10,
    "undici": 11,
    "dodici": 12,
}

_RE_ORE_NUM = re.compile(r"(\d+)\s*(?:ore|ora|h)\b")
_RE_MIN_NUM = re.compile(r"(\d+)\s*(?:minuti|minuto|min)\b")
_RE_ORE_PAROLA = re.compile(
    r"\b(" + "|".join(_NUMERI_ITALIANI) + r")\s*or"
)
_RE_MIN_PAROLA = re.compile(
    r"\b(" + "|".join(_NUMERI_ITALIANI) + r")\s*minut"
)


def _parse_minuti(testo: str, default: int) -> int:
    """Parsing dei minuti disponibili da testo libero: numeri, numeri scritti
    a parole, "mezza giornata", "tutto il giorno", "mezz'ora"... Mai eccezioni:
    testo non interpretabile -> `default`.

    Precedenza: "mezz'ora" (30), poi un NUMERO ESPLICITO (cifre o parole, ore o
    minuti) che vince sulle frasi generiche, poi le frasi generiche
    ("tutto il giorno" 480, "mezza giornata" 240, "poco tempo" 60,
    "tanto tempo" 240). Es. "Mezza giornata, circa tre ore" -> 180."""
    try:
        t = _normalizza(testo)
        if not t:
            return default
        if re.search(r"mezz\s*['`]?\s*or|mezzora", t):
            return 30

        m = _RE_ORE_NUM.search(t)
        if m:
            return int(m.group(1)) * 60

        m = _RE_MIN_NUM.search(t)
        if m:
            return int(m.group(1))

        m = _RE_ORE_PAROLA.search(t)
        if m:
            return _NUMERI_ITALIANI[m.group(1)] * 60

        m = _RE_MIN_PAROLA.search(t)
        if m:
            return _NUMERI_ITALIANI[m.group(1)]

        if re.search(r"tutto il giorno|tutta la giornata|giornata intera", t):
            return 480
        if re.search(r"mezza giornata", t):
            return 240
        if re.search(r"poco tempo|pochissimo tempo|di corsa|poco", t):
            return 60
        if re.search(r"tanto tempo|tantissimo tempo|tutta la vita", t):
            return 240

        return default
    except Exception:
        return default


def profile_from_answers(req: OnboardingRequest) -> EmotionalProfile:
    """Costruisce l'`EmotionalProfile` dalle risposte dell'onboarding.

    Parsing deterministico, robusto e senza eccezioni: una risposta mancante
    o incomprensibile ricade sempre su un default prudente (vedi le costanti
    `DEFAULT_*` sopra). `lingue` riflette sempre `req.lingua`.
    """
    risposte: dict[str, str] = {r.domanda_id: r.risposta for r in req.risposte}

    def _get(domanda_id: str) -> str:
        return risposte.get(domanda_id, "")

    curiosita = _parse_intensita(_get("perdersi"), DEFAULT_CURIOSITA)

    contemplazione = _parse_polarita(
        _get("silenzio_musica"),
        positivi=("silenzio", "quiete", "tranquillita", "pace", "raccoglimento"),
        negativi=("musica", "concerto", "rumore", "confusione", "movida"),
        default=DEFAULT_CONTEMPLAZIONE,
    )

    arte = _parse_polarita(
        _get("bellezza_storie"),
        positivi=("bellezza", "estetica", "arte", "dipinti", "opere", "opera"),
        negativi=("storie", "storia", "racconti", "racconto", "aneddoti", "leggende"),
        default=DEFAULT_ARTE,
    )

    con_bambini = _parse_bool(
        _get("bambini"),
        DEFAULT_CON_BAMBINI,
        positivi_extra=("bambin", "figli", "bimbi", "famiglia"),
        negativi_extra=("senza bambini", "da solo", "da sola", "in coppia"),
    )

    tempo_disponibile_min = _parse_minuti(_get("tempo"), DEFAULT_TEMPO_MIN)

    accessibilita_richiesta = _parse_bool(
        _get("accessibilita"),
        DEFAULT_ACCESSIBILITA,
        positivi_extra=(
            "sedia a rotelle",
            "carrozzina",
            "difficolta motorie",
            "disabilita",
            "passeggino",
        ),
    )

    ha_gia_visto_firenze = _parse_bool(
        _get("firenze"),
        DEFAULT_HA_GIA_VISTO_FIRENZE,
        positivi_extra=("gia visto", "gia stato", "gia stata", "conosco gia"),
        negativi_extra=("mai visto", "mai stato", "mai stata", "prima volta", "non ancora"),
    )

    return EmotionalProfile(
        curiosita=curiosita,
        contemplazione=contemplazione,
        arte=arte,
        con_bambini=con_bambini,
        tempo_disponibile_min=tempo_disponibile_min,
        accessibilita_richiesta=accessibilita_richiesta,
        ha_gia_visto_firenze=ha_gia_visto_firenze,
        lingue=[req.lingua],
    )
