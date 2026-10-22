"""Frase del profilo: solo tratti NETTI (ondata 2b, compito 4).

Un tratto 0..1 entra nel `reason` solo se >= 0.7 oppure <= 0.2 (limiti
inclusi, anche quando il valore arriva da un calcolo in virgola mobile). Tra i
tratti netti vince il più lontano da 0.5; nessun tratto netto, nessuna frase.
I flag booleani (bambini, accessibilità) restano prioritari e invariati.
"""

from __future__ import annotations

import pytest
from contracts import EmotionalProfile
from rag.reasons import _tratto_dominante

CURIOSO = "hai voglia di perderti e lasciarti sorprendere"
CHIARO = "preferisci un percorso chiaro, senza troppe sorprese"


def _profilo(
    curiosita: float = 0.5,
    contemplazione: float = 0.5,
    arte: float = 0.5,
    *,
    bambini: bool = False,
    accessibile: bool = False,
) -> EmotionalProfile:
    return EmotionalProfile(
        curiosita=curiosita, contemplazione=contemplazione, arte=arte,
        con_bambini=bambini, accessibilita_richiesta=accessibile,
        tempo_disponibile_min=240,
    )


def test_un_po_di_curiosita_non_produce_frase() -> None:
    """Curiosità 0.35 (risposta "Un po'"), altri tratti neutri, nessun flag."""
    assert _tratto_dominante(_profilo(curiosita=0.35)) is None


def test_curiosita_alta_produce_la_frase() -> None:
    assert _tratto_dominante(_profilo(curiosita=0.75)) == CURIOSO


@pytest.mark.parametrize(
    ("valore", "attesa"),
    [
        (0.7, CURIOSO),
        (0.69, None),
        (0.2, CHIARO),
        (0.21, None),
        (0.0, CHIARO),
        (1.0, CURIOSO),
        # Rumore di virgola mobile attorno ai limiti: restano inclusi.
        (0.1 * 7, CURIOSO),  # 0.7000000000000001
        (0.7 - 1e-12, CURIOSO),
        (1 - 0.8, CHIARO),  # 0.19999999999999996
        (0.2 + 1e-12, CHIARO),
        # ...ma la tolleranza non allarga le soglie.
        (0.7 - 1e-6, None),
        (0.2 + 1e-6, None),
    ],
)
def test_limiti_inclusi_ed_esclusi(valore: float, attesa: str | None) -> None:
    assert _tratto_dominante(_profilo(curiosita=valore)) == attesa


def test_tra_i_netti_vince_il_piu_lontano_da_0_5() -> None:
    # contemplazione 0.8 (scarto 0.3) contro curiosità 0.1 (scarto 0.4).
    assert _tratto_dominante(_profilo(curiosita=0.1, contemplazione=0.8)) == CHIARO
    # Un tratto non netto più lontano da 0.5 di uno netto non conta mai: qui
    # nessuno è più lontano, ma un tratto 0.65 non deve vincere su 0.7.
    assert _tratto_dominante(_profilo(curiosita=0.7, arte=0.65)) == CURIOSO


def test_a_parita_vale_l_ordine_contemplazione_arte_curiosita() -> None:
    assert _tratto_dominante(_profilo(curiosita=0.9, contemplazione=0.9, arte=0.9)) == (
        "cerchi silenzio e raccoglimento"
    )
    assert _tratto_dominante(_profilo(curiosita=0.9, arte=0.9)) == (
        "ti lasci conquistare dalla bellezza"
    )


def test_tratto_non_netto_ignorato_anche_se_il_piu_lontano() -> None:
    """Arte 0.3 (scarto 0.2, non netto) non entra; curiosità 0.7 (netta) sì."""
    assert _tratto_dominante(_profilo(curiosita=0.7, arte=0.3)) == CURIOSO
    assert _tratto_dominante(_profilo(arte=0.3, contemplazione=0.65)) is None


def test_flag_prioritari_invariati() -> None:
    assert _tratto_dominante(_profilo(curiosita=0.35, bambini=True)) == (
        "è pensata anche per chi viaggia con bambini"
    )
    assert _tratto_dominante(_profilo(curiosita=0.9, accessibile=True)) == (
        "rispetta il bisogno di un percorso accessibile"
    )
    assert _tratto_dominante(_profilo(bambini=True, accessibile=True)) == (
        "è pensata anche per chi viaggia con bambini"
    )
