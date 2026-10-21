"""`titolo` delle tappe (ondata 2a, compito 3): l'Experience Engine scrive su
OGNI `ItineraryStop` e `TappaEsclusa` il titolo leggibile del catalogo
(`ExperienceNode.titolo`), cosi' l'app non mostra mai un id.

- composizione: titolo = `candidate.experience.titolo`;
- adattamento: una tappa ricevuta SENZA titolo (itinerario vecchio) il cui
  candidato e' noto riceve il titolo dal catalogo (anche se sostituita, tagliata
  o esclusa); uno stub (candidato sconosciuto) conserva il titolo ricevuto, anche
  None; una `TappaEsclusa` porta il titolo della tappa che il visitatore AVEVA
  (`id_originale`), non della sua sostituta;
- tappe fluttuanti ed eventi promossi: `titolo=None` (i loro modelli non hanno un
  titolo; l'app mostra un'etichetta generica);
- nessun `titolo` contiene "exp-".
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from contracts import (
    EmotionalProfile,
    EsitoAdattamento,
    EventoPromosso,
    ExperienceNode,
    GraphCandidate,
    Itinerary,
    ItineraryStop,
    SegnaleFluttuante,
    Signal,
    TappaEsclusa,
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary
from graph.seed_lucca import VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

PROFILI = {
    "curioso": EmotionalProfile(
        curiosita=0.9, contemplazione=0.2, arte=0.4, con_bambini=False,
        tempo_disponibile_min=300,
    ),
    "contemplativo": EmotionalProfile(
        curiosita=0.2, contemplazione=0.9, arte=0.5, con_bambini=False,
        tempo_disponibile_min=240,
    ),
    "con-bambini": EmotionalProfile(
        curiosita=0.6, contemplazione=0.3, arte=0.3, con_bambini=True,
        tempo_disponibile_min=240,
    ),
    "accessibile": EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.7, con_bambini=False,
        tempo_disponibile_min=300, accessibilita_richiesta=True,
    ),
}

SABATO = date(2026, 12, 12)


def _sereno(ora: time = time(10, 0)) -> Signal:
    return Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=ora, data=SABATO)


def _componi(profilo: EmotionalProfile) -> tuple[Itinerary, list[GraphCandidate]]:
    ctx = VisitorContext(person_id="p", profile=profilo, signal=_sereno())
    cands = list(SeedCandidateSource().candidates(ctx))
    return compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO), cands


def _catalogo(cands: list[GraphCandidate]) -> dict[str, str]:
    return {c.experience.id: c.experience.titolo for c in cands}


def _senza_titoli(it: Itinerary) -> Itinerary:
    """Lo stesso itinerario come lo manderebbe un client vecchio: nessun titolo."""
    return it.model_copy(
        update={
            "stops": [s.model_copy(update={"titolo": None}) for s in it.stops],
            "tappe_escluse": [t.model_copy(update={"titolo": None}) for t in it.tappe_escluse],
        }
    )


def _assert_titoli_dal_catalogo(it: Itinerary, catalogo: dict[str, str]) -> None:
    for s in it.stops:
        assert s.titolo == catalogo[s.experience_id], s.experience_id
        assert "exp-" not in (s.titolo or ""), s.titolo
    for t in it.tappe_escluse:
        assert t.titolo == catalogo[t.experience_id], t.experience_id
        assert "exp-" not in (t.titolo or ""), t.titolo


# ---------------------------------------------------------------------------
# Composizione e adattamento sul seed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(PROFILI))
def test_composto_ogni_tappa_ha_il_titolo_del_catalogo(nome: str) -> None:
    it, cands = _componi(PROFILI[nome])
    assert it.stops
    _assert_titoli_dal_catalogo(it, _catalogo(cands))


SEGNALI_ADATTAMENTO = {
    "pioggia": Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0),
                      data=SABATO),
    "stanchezza": Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0),
                         data=SABATO),
    "pioggia-stanchezza": Signal(meteo="pioggia", affollamento={}, stanchezza=0.9,
                                 ora=time(10, 0), data=SABATO),
    "tardi": Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(22, 30),
                    data=SABATO),
    "lunedi": Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(15, 0),
                     data=date(2026, 12, 14)),
}


@pytest.mark.parametrize("segnale", sorted(SEGNALI_ADATTAMENTO))
@pytest.mark.parametrize("nome", sorted(PROFILI))
@pytest.mark.parametrize("vecchio", [False, True], ids=["con-titoli", "senza-titoli"])
def test_adattato_ogni_tappa_e_ogni_esclusa_ha_il_titolo_del_catalogo(
    nome: str, segnale: str, vecchio: bool
) -> None:
    base, cands = _componi(PROFILI[nome])
    ricevuto = _senza_titoli(base) if vecchio else base
    r = adapt_itinerary(
        ricevuto, SEGNALI_ADATTAMENTO[segnale], cands, PROFILI[nome],
        compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
    )
    _assert_titoli_dal_catalogo(r, _catalogo(cands))


def test_il_seed_esercita_sostituzioni_ed_escluse() -> None:
    """Le asserzioni sopra non sono vuote: sul seed ci sono sia tappe sostituite
    sia tappe escluse."""
    sostituite = escluse = 0
    for profilo in PROFILI.values():
        base, cands = _componi(profilo)
        for segnale in SEGNALI_ADATTAMENTO.values():
            r = adapt_itinerary(
                _senza_titoli(base), segnale, cands, profilo,
                compose_reason, adapt_reason, vocabolario=VOCABOLARIO,
            )
            sostituite += sum(
                1 for s in r.stops if s.esito_adattamento is EsitoAdattamento.SOSTITUITA
            )
            escluse += len(r.tappe_escluse)
    assert sostituite > 0
    assert escluse > 0


# ---------------------------------------------------------------------------
# Casi mirati (candidati sintetici)
# ---------------------------------------------------------------------------


def _esperienza(id_: str, durata: int = 60, *, al_chiuso: bool = True) -> ExperienceNode:
    return ExperienceNode(
        id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
        durata_min=durata, al_chiuso=al_chiuso, accessibile=True,
    )


def _cand(esperienza: ExperienceNode) -> GraphCandidate:
    return GraphCandidate(
        experience=esperienza, place_nome=f"Piazza {esperienza.id}", connessioni=[]
    )


def _stop(id_: str, arrivo: time, durata: int = 60, titolo: str | None = None) -> ItineraryStop:
    return ItineraryStop(
        experience_id=id_, titolo=titolo, arrivo=arrivo, durata_min=durata,
        reason="Motivo originale.",
    )


def _itinerario(stops: list[ItineraryStop], escluse: list[TappaEsclusa] | None = None) -> Itinerary:
    return Itinerary(
        person_id="p", stops=stops, generated_at=datetime(2026, 1, 1),
        tempo_disponibile_min=300, tempo_effettivo_min=300, tappe_escluse=escluse or [],
    )


def test_stub_conserva_il_titolo_ricevuto_anche_none_senza_cambiamenti() -> None:
    cands = [_cand(_esperienza("t0"))]
    it = _itinerario([
        _stop("t0", time(10, 0)),
        _stop("ignota-1", time(11, 10), titolo="Un titolo ricevuto"),
        _stop("ignota-2", time(12, 20)),
    ])
    r = adapt_itinerary(it, _sereno(), cands, None, vocabolario=VOCABOLARIO)
    assert r.adattato_da_segnale is False
    assert [s.titolo for s in r.stops] == ["Titolo t0", "Un titolo ricevuto", None]


def test_stub_conserva_il_titolo_ricevuto_anche_none_con_ricostruzione() -> None:
    """Pioggia su t0 all'aperto -> sostituita: gli stop sono ricostruiti, gli
    stub conservano il titolo ricevuto e la sostituta ha il suo titolo."""
    cands = [_cand(_esperienza("t0", al_chiuso=False)), _cand(_esperienza("alt"))]
    it = _itinerario([
        _stop("t0", time(10, 0)),
        _stop("ignota-1", time(11, 10), titolo="Un titolo ricevuto"),
        _stop("ignota-2", time(12, 20)),
    ])
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    r = adapt_itinerary(it, pioggia, cands, None, vocabolario=VOCABOLARIO)
    assert r.adattato_da_segnale is True
    assert [(s.experience_id, s.titolo) for s in r.stops] == [
        ("alt", "Titolo alt"),
        ("ignota-1", "Un titolo ricevuto"),
        ("ignota-2", None),
    ]


def test_titolo_ricevuto_di_un_candidato_noto_vince_il_catalogo() -> None:
    """Il client non riscrive il titolo di un'esperienza nota: vale il catalogo."""
    cands = [_cand(_esperienza("t0"))]
    it = _itinerario([_stop("t0", time(10, 0), titolo="Testo libero del client")])
    r = adapt_itinerary(it, _sereno(), cands, None, vocabolario=VOCABOLARIO)
    assert r.stops[0].titolo == "Titolo t0"


def test_esclusa_dopo_sostituzione_porta_il_titolo_della_tappa_originale() -> None:
    """t2 all'aperto, pioggia e stanchezza: t2 e' sostituita da `alt` e poi
    tagliata in coda. In `tappe_escluse` finisce t2 (la tappa che il visitatore
    aveva), col titolo di t2, non quello della sostituta."""
    cands = [
        _cand(_esperienza("t0")), _cand(_esperienza("t1")),
        _cand(_esperienza("t2", al_chiuso=False)), _cand(_esperienza("alt")),
    ]
    it = _itinerario([
        _stop("t0", time(10, 0)), _stop("t1", time(11, 10)), _stop("t2", time(12, 20)),
    ])
    segnale = Signal(meteo="pioggia", affollamento={}, stanchezza=0.9, ora=time(10, 0))
    r = adapt_itinerary(it, segnale, cands, None, vocabolario=VOCABOLARIO)
    assert [s.experience_id for s in r.stops] == ["t0", "t1"]
    assert [(t.experience_id, t.titolo) for t in r.tappe_escluse] == [("t2", "Titolo t2")]


def test_escluse_ricevute_titolo_dal_catalogo_o_conservato() -> None:
    """Esclusioni accumulate da un adattamento precedente: per un id noto il
    titolo viene dal catalogo (anche se mancava), per un id sconosciuto resta
    quello ricevuto (anche None)."""
    cands = [_cand(_esperienza("t0")), _cand(_esperienza("t9"))]
    escluse = [
        TappaEsclusa(
            experience_id="t9", esito=EsitoAdattamento.TAGLIATA_STANCHEZZA, reason="x",
        ),
        TappaEsclusa(
            experience_id="ignota-a", titolo="Titolo ricevuto",
            esito=EsitoAdattamento.TAGLIATA_TETTO_GIORNATA, reason="x",
        ),
        TappaEsclusa(
            experience_id="ignota-b", esito=EsitoAdattamento.TAGLIATA_ORARIO, reason="x",
        ),
    ]
    it = _itinerario([_stop("t0", time(10, 0))], escluse)
    r = adapt_itinerary(it, _sereno(), cands, None, vocabolario=VOCABOLARIO)
    assert [(t.experience_id, t.titolo) for t in r.tappe_escluse] == [
        ("t9", "Titolo t9"),
        ("ignota-a", "Titolo ricevuto"),
        ("ignota-b", None),
    ]


def test_tappe_fluttuanti_ed_eventi_promossi_senza_titolo() -> None:
    """I modelli di segnale fluttuante ed evento promosso non hanno un titolo:
    la tappa aggiunta in coda ha `titolo=None` (mai l'id), le permanenti il loro."""
    esperienza = ExperienceNode(
        id="exp-arte", titolo="Una visita d'arte", place_id="luogo-fisso",
        temi=["arte", "musica", "storia"], durata_min=30, al_chiuso=True, accessibile=True,
    )
    cand = GraphCandidate(experience=esperienza, place_nome="Piazza fissa", connessioni=[])
    fluttuante = SegnaleFluttuante(
        id="violinista-1", descrizione="un violinista suona in piazza",
        temi=["musica"], place_id="luogo-fisso", non_commerciale=True,
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    evento = EventoPromosso(
        id="evento-luogo-fisso-musica", place_id="luogo-fisso", temi=["musica"],
        ultima_occorrenza=date(2026, 12, 5), cadenza_giorni=7.0,
    )
    profilo = EmotionalProfile(
        curiosita=0.9, contemplazione=0.5, arte=0.9, con_bambini=False,
        tempo_disponibile_min=300,
    )
    signal = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0),
        data=SABATO, eventi_attivi=[fluttuante],
    )
    ctx = VisitorContext(person_id="p", profile=profilo, signal=signal)
    it = compose_itinerary(
        ctx, [cand], compose_reason, eventi_promossi=[evento], vocabolario=VOCABOLARIO
    )
    per_id = {s.experience_id: s.titolo for s in it.stops}
    assert per_id["exp-arte"] == "Una visita d'arte"
    assert per_id["fluttuante-violinista-1"] is None
    assert per_id["evento-luogo-fisso-musica"] is None
    # In adattamento restano stub: titolo conservato (None).
    r = adapt_itinerary(it, _sereno(), [cand], profilo, vocabolario=VOCABOLARIO)
    assert {s.experience_id: s.titolo for s in r.stops} == per_id
