"""Motivo (ondata 2a, compito 4): le cinque frasi di `compose_reason`."""

from __future__ import annotations

from typing import Any

from contracts import EmotionalProfile, ExperienceNode, GraphCandidate
from rag.reasons import compose_reason

NEUTRO = EmotionalProfile(
    curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False, tempo_disponibile_min=120
)
CONTEMPLATIVO = NEUTRO.model_copy(update={"contemplazione": 0.9})


def _cand(*, al_chiuso: bool = False, prezzo: float | None = None, **kw: Any) -> GraphCandidate:
    esp = ExperienceNode(
        id="exp-x", titolo="Titolo", place_id="p", temi=["verde"], durata_min=30,
        al_chiuso=al_chiuso, accessibile=True, prezzo_eur=prezzo,
    )
    return GraphCandidate(
        experience=esp, place_nome="Orto Botanico",
        connessioni=["Qualcosa è legato a questo luogo"],
        **kw,
    )


def test_esempio_prima_tappa_etichette() -> None:
    c = _cand(temi_etichette=["verde e giardini"])
    assert compose_reason(c, CONTEMPLATIVO) == (
        "Cerchi silenzio e raccoglimento. Temi: verde e giardini. All'aperto."
    )


def test_esempio_racconto_non_prima_tappa() -> None:
    c = _cand(al_chiuso=True, racconti=["In questa chiesa il giovane Giacomo Puccini …"])
    assert compose_reason(c, CONTEMPLATIVO, prima_tappa=False) == (
        "In questa chiesa il giovane Giacomo Puccini …. Al chiuso."
    )


def test_racconto_con_punto_non_ne_riceve_un_altro() -> None:
    c = _cand(racconti=["Un racconto."])
    assert compose_reason(c, NEUTRO) == "Un racconto. All'aperto."


def test_racconto_vince_sulle_etichette() -> None:
    c = _cand(racconti=["Racconto con fonte."], temi_etichette=["arte", "storia"])
    out = compose_reason(c, NEUTRO)
    assert "Racconto con fonte." in out
    assert "Temi:" not in out


def test_etichette_multiple() -> None:
    c = _cand(temi_etichette=["arte", "storia"])
    assert compose_reason(c, NEUTRO) == "Temi: arte, storia. All'aperto."


def test_al_chiuso_e_all_aperto() -> None:
    assert compose_reason(_cand(al_chiuso=True), NEUTRO) == "Al chiuso."
    assert compose_reason(_cand(al_chiuso=False), NEUTRO) == "All'aperto."


def test_nessuna_frase_sul_prezzo_qualunque_prezzo() -> None:
    for prezzo in (None, 0, 8.0):
        out = compose_reason(_cand(prezzo=prezzo), NEUTRO)
        assert out == "All'aperto."
        assert "gratuit" not in out


def test_vicinanza_con_articoli() -> None:
    casi = [("il", "dal Duomo"), ("la", "dalla Duomo"), ("l'", "dall'Duomo"), (None, "da Duomo")]
    for art, atteso in casi:
        c = _cand(distanza_m=250, vicinanza_nome="Duomo", vicinanza_articolo=art)
        assert compose_reason(c, NEUTRO) == f"All'aperto. A 250 m {atteso}, già visitato."


def test_vicinanza_assente_senza_nome() -> None:
    assert "già visitato" not in compose_reason(_cand(distanza_m=250), NEUTRO)


def test_segnale() -> None:
    out = compose_reason(_cand(), NEUTRO, ["pioggia"])
    assert out == "All'aperto. Con la pioggia si sta al chiuso."
    assert compose_reason(_cand(), NEUTRO, ["affollamento"]).endswith(
        "In questo momento è meno affollato."
    )


def test_profilo_solo_con_prima_tappa() -> None:
    c = _cand()
    assert compose_reason(c, CONTEMPLATIVO, prima_tappa=True).startswith("Cerchi silenzio")
    assert "Cerchi" not in compose_reason(c, CONTEMPLATIVO, prima_tappa=False)


def test_non_usa_connessioni_ne_formule_vietate() -> None:
    c = _cand(temi_etichette=["arte"], racconti=[])
    for prima in (True, False):
        out = compose_reason(c, CONTEMPLATIVO, ["pioggia"], prima_tappa=prima)
        for vietato in ("è legato a", "Evoca il tema", "La bottega evoca", "exp-", "Qualcosa"):
            assert vietato not in out
        assert out.strip()
