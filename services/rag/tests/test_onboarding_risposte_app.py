"""Anti-deriva tra l'app e il parser dell'onboarding.

I test esistenti usavano risposte inventate ("no, da sola") e non le stringhe ESATTE che
l'app Flutter invia (`OnboardingOption(etichetta, risposta)` in `onboarding_screen.dart`).
Cosi' "No, non sono con bambini" veniva letto come `con_bambini=True` e "Mezza giornata,
circa tre ore" come 240 minuti invece di 180.

Questo modulo legge le domande direttamente dal file Dart, esige che ogni coppia
(domandaId, etichetta) abbia un valore atteso in tabella (e viceversa) e verifica che
`profile_from_answers` produca il profilo giusto. Se l'app cambia testo o opzioni, il test
fallisce e chiede di aggiornare parser e tabella.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from contracts import EmotionalProfile, OnboardingAnswer, OnboardingRequest
from rag.onboarding import profile_from_answers

RADICE = Path(__file__).resolve().parents[3]
FILE_DART = RADICE / "apps" / "lucca_soul_app" / "lib" / "screens" / "onboarding_screen.dart"

# Stringa Dart tra apici singoli, con \' (e \\) escapati.
_STR = r"'((?:[^'\\]|\\.)*)'"
_RE_DOMANDA = re.compile(r"OnboardingQuestion\(\s*domandaId:\s*" + _STR)
_RE_OPZIONE = re.compile(r"OnboardingOption\(\s*" + _STR + r"\s*,\s*" + _STR + r"\s*\)")

N_DOMANDE = 7
N_OPZIONI = 18


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


def _leggi_domande_dart() -> list[tuple[str, str, str]]:
    """Ritorna [(domandaId, etichetta, risposta)] in ordine di file."""
    assert FILE_DART.is_file(), f"File Dart non trovato: {FILE_DART}"
    testo = FILE_DART.read_text(encoding="utf-8")
    inizio = testo.find("kOnboardingQuestions")
    assert inizio >= 0, "kOnboardingQuestions non trovato nel file Dart: struttura cambiata"
    testo = testo[inizio:]
    domande = list(_RE_DOMANDA.finditer(testo))
    assert len(domande) == N_DOMANDE, (
        f"Trovate {len(domande)} domande nel Dart, attese {N_DOMANDE}: "
        "aggiornare parser, tabella e questo test."
    )
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(domande):
        fine = domande[i + 1].start() if i + 1 < len(domande) else len(testo)
        for o in _RE_OPZIONE.finditer(testo, m.end(), fine):
            out.append((_unescape(m.group(1)), _unescape(o.group(1)), _unescape(o.group(2))))
    assert len(out) == N_OPZIONI, (
        f"Trovate {len(out)} opzioni nel Dart, attese {N_OPZIONI}: "
        "aggiornare parser, tabella e questo test."
    )
    return out


# (domandaId, etichetta) -> (campo del profilo, verifica)
# verifica: valore esatto (bool/int/float) oppure ("<", x) / ("tra", a, b) / (">", x)
ATTESI: dict[tuple[str, str], tuple[str, object]] = {
    ("bambini", "Sì"): ("con_bambini", True),
    ("bambini", "No"): ("con_bambini", False),
    ("accessibilita", "Sì"): ("accessibilita_richiesta", True),
    ("accessibilita", "No"): ("accessibilita_richiesta", False),
    ("firenze", "Sì"): ("ha_gia_visto_firenze", True),
    ("firenze", "No"): ("ha_gia_visto_firenze", False),
    ("silenzio_musica", "Silenzio"): ("contemplazione", 0.8),
    ("silenzio_musica", "Un mix"): ("contemplazione", 0.5),
    ("silenzio_musica", "Musica"): ("contemplazione", 0.2),
    ("bellezza_storie", "La bellezza"): ("arte", 0.8),
    ("bellezza_storie", "Entrambe"): ("arte", 0.5),
    ("bellezza_storie", "Le storie"): ("arte", 0.2),
    ("perdersi", "Sì, senza meta"): ("curiosita", (">", 0.5)),
    ("perdersi", "Un po'"): ("curiosita", ("tra", 0.0, 0.5)),
    ("perdersi", "No, un percorso chiaro"): ("curiosita", ("<", 0.5)),
    ("tempo", "Un'ora"): ("tempo_disponibile_min", 60),
    ("tempo", "Mezza giornata"): ("tempo_disponibile_min", 180),
    ("tempo", "Tutto il giorno"): ("tempo_disponibile_min", 480),
}


def _profilo(domanda_id: str, risposta: str) -> EmotionalProfile:
    req = OnboardingRequest(risposte=[OnboardingAnswer(domanda_id=domanda_id, risposta=risposta)])
    return profile_from_answers(req)


def _verifica(valore: object, atteso: object) -> None:
    if isinstance(atteso, bool):
        assert valore is atteso
    elif isinstance(atteso, tuple):
        assert isinstance(valore, float)
        if atteso[0] == ">":
            assert valore > atteso[1]
        elif atteso[0] == "<":
            assert valore < atteso[1]
        else:
            assert atteso[1] < valore < atteso[2]
    elif isinstance(atteso, float):
        assert isinstance(valore, float)
        assert abs(valore - atteso) <= 1e-9
    else:
        assert valore == atteso


def test_struttura_dart_e_tabella_coincidono() -> None:
    coppie_dart = {(d, e) for d, e, _ in _leggi_domande_dart()}
    coppie_tabella = set(ATTESI)
    nuove = sorted(coppie_dart - coppie_tabella)
    sparite = sorted(coppie_tabella - coppie_dart)
    assert not nuove and not sparite, (
        "L'onboarding dell'app e la tabella del test divergono. "
        "Aggiornare il parser (services/rag/rag/onboarding.py) E la tabella ATTESI. "
        f"Nel Dart ma non in tabella: {nuove}. In tabella ma non nel Dart: {sparite}."
    )


def _casi_app() -> list[object]:
    try:
        righe = _leggi_domande_dart()
    except AssertionError:
        return []  # il fallimento chiaro e' in test_struttura_dart_e_tabella_coincidono
    return [pytest.param(d, e, r, id=f"{d}|{e}") for d, e, r in righe if (d, e) in ATTESI]


@pytest.mark.parametrize(("domanda_id", "etichetta", "risposta"), _casi_app())
def test_risposta_esatta_dell_app(domanda_id: str, etichetta: str, risposta: str) -> None:
    campo, atteso = ATTESI[(domanda_id, etichetta)]
    profilo = _profilo(domanda_id, risposta)
    _verifica(getattr(profilo, campo), atteso)


def test_la_lettura_del_dart_non_e_vuota() -> None:
    assert len(_casi_app()) > 0


# --- Test mirati sul parser (testi liberi) ---


def test_si_con_bambini_e_non_vedo_l_ora() -> None:
    assert _profilo("bambini", "sì, sono con bambini, non vedo l'ora").con_bambini is True


def test_non_ho_bambini() -> None:
    assert _profilo("bambini", "non ho bambini").con_bambini is False


def test_mezza_giornata_da_sola() -> None:
    assert _profilo("tempo", "mezza giornata").tempo_disponibile_min == 240


def test_mezza_giornata_con_tre_ore() -> None:
    assert _profilo("tempo", "Mezza giornata, circa tre ore").tempo_disponibile_min == 180
