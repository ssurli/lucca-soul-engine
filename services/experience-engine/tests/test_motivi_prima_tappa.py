"""Motivi delle tappe (ondata 2a, compito 4) nel motore.

- `ReasonFn` riceve `prima_tappa`: True SOLO per la prima tappa
  dell'itinerario finale (arrivo più presto), False per le altre e per i
  motivi dei sostituti. La frase del profilo compare quindi al massimo una
  volta per itinerario, e solo sulla prima tappa; anche dopo l'adattamento.
- Il motivo di un sostituto è il motivo specifico del sostituto
  (`reason_fn(alt, profilo, [], prima_tappa=False)`), mai `connessioni[0]`.
- Le frasi del motore che nominano un luogo con preposizione usano
  `contracts.con_luogo` ("l'affollamento alla Torre…", "C'è molta gente
  all'Orto…"); la frase di esito è riconosciuta sia nella forma con articolo
  sia in quella vecchia ("C'è molta gente a <nome>").
- Il fallback interno (`_fallback_reason`, senza RAG) produce lo STESSO testo
  di `rag.reasons.compose_reason` per gli stessi input.
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
    VisitorContext,
)
from experience_engine import adapt_itinerary, compose_itinerary
from experience_engine.engine import (
    ReasonFn,
    _fallback_reason,
    _frase_esito,
    _senza_frase_esito,
)
from graph.seed_lucca import ESPERIENZE, VOCABOLARIO
from graph.source import SeedCandidateSource
from rag.reasons import adapt_reason, compose_reason

#: Tutte le frasi di profilo possibili, come compaiono nel motivo.
FRASI_PROFILO = (
    "È pensata anche per chi viaggia con bambini.",
    "Rispetta il bisogno di un percorso accessibile.",
    "Cerchi silenzio e raccoglimento.",
    "Ami i luoghi vivi, con musica e movimento.",
    "Ti lasci conquistare dalla bellezza.",
    "Preferisci le storie che un luogo racconta.",
    "Hai voglia di perderti e lasciarti sorprendere.",
    "Preferisci un percorso chiaro, senza troppe sorprese.",
)

PROFILI: dict[str, EmotionalProfile] = {
    "contemplativo": EmotionalProfile(
        curiosita=0.2, contemplazione=0.9, arte=0.3, con_bambini=False,
        tempo_disponibile_min=240,
    ),
    "curioso": EmotionalProfile(
        curiosita=0.9, contemplazione=0.2, arte=0.4, con_bambini=False,
        tempo_disponibile_min=240,
    ),
    "ama-arte": EmotionalProfile(
        curiosita=0.4, contemplazione=0.4, arte=0.95, con_bambini=False,
        tempo_disponibile_min=300,
    ),
    "con-bambini": EmotionalProfile(
        curiosita=0.6, contemplazione=0.3, arte=0.3, con_bambini=True,
        tempo_disponibile_min=180,
    ),
    "accessibile": EmotionalProfile(
        curiosita=0.5, contemplazione=0.6, arte=0.6, con_bambini=False,
        accessibilita_richiesta=True, tempo_disponibile_min=240,
    ),
    "poco-tempo": EmotionalProfile(
        curiosita=0.7, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=60,
    ),
    "neutro": EmotionalProfile(
        curiosita=0.5, contemplazione=0.5, arte=0.5, con_bambini=False,
        tempo_disponibile_min=240,
    ),
}

SEGNALI: dict[str, Signal] = {
    "sereno": Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    "pioggia": Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
    "caldo": Signal(meteo="caldo", affollamento={}, stanchezza=0.0, ora=time(14, 0)),
    "stanchezza": Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0)),
    "affollamento": Signal(
        meteo="sereno",
        affollamento={"mura-urbane": 0.1, "torre-guinigi": 0.2, "palazzo-pfanner": 0.75},
        stanchezza=0.0,
        ora=time(10, 0),
    ),
}

REASON_FNS: list[tuple[str, ReasonFn | None]] = [("fallback", None), ("rag", compose_reason)]


def _conta_profilo(reason: str) -> int:
    return sum(reason.count(f) for f in FRASI_PROFILO)


def _ctx(profilo: str, segnale: str, visti: list[str] | None = None) -> VisitorContext:
    return VisitorContext(
        person_id="p",
        profile=PROFILI[profilo],
        signal=SEGNALI[segnale],
        luoghi_gia_visti=visti or [],
    )


def _componi(ctx: VisitorContext, reason_fn: ReasonFn | None) -> Itinerary:
    cands = SeedCandidateSource().candidates(ctx)
    return compose_itinerary(ctx, cands, reason_fn, vocabolario=VOCABOLARIO)


def _errori_profilo(it: Itinerary) -> list[str]:
    """Frase del profilo: al massimo una volta in tutto l'itinerario, e solo
    sulla prima tappa."""
    errori: list[str] = []
    totale = sum(_conta_profilo(s.reason) for s in it.stops)
    if totale > 1:
        errori.append(f"frase del profilo {totale} volte")
    for i, s in enumerate(it.stops):
        if i > 0 and _conta_profilo(s.reason):
            errori.append(f"frase del profilo sulla tappa {i} ({s.experience_id})")
    return errori


# ---------------------------------------------------------------------------
# Composizione
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("nome_fn", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
@pytest.mark.parametrize("segnale", sorted(SEGNALI))
@pytest.mark.parametrize("profilo", sorted(PROFILI))
def test_profilo_una_volta_sola_sulla_prima_tappa(
    profilo: str, segnale: str, nome_fn: str, reason_fn: ReasonFn | None
) -> None:
    it = _componi(_ctx(profilo, segnale), reason_fn)
    assert it.stops
    assert not _errori_profilo(it), (profilo, segnale, nome_fn, _errori_profilo(it))
    assert all(s.reason.strip() for s in it.stops)
    if profilo != "neutro":  # un profilo marcato apre davvero la prima tappa
        assert _conta_profilo(it.stops[0].reason) == 1, it.stops[0].reason


def test_prima_tappa_true_solo_per_la_prima_in_ordine_di_arrivo() -> None:
    chiamate: list[tuple[str, bool]] = []

    def spia(
        cand: GraphCandidate, profile: EmotionalProfile, segnali: list[str], /, *,
        prima_tappa: bool,
    ) -> str:
        chiamate.append((cand.experience.id, prima_tappa))
        return f"Motivo {len(chiamate)}."

    it = _componi(_ctx("contemplativo", "sereno"), spia)
    assert len(it.stops) >= 2
    arrivi = [s.arrivo for s in it.stops]
    assert arrivi == sorted(arrivi)
    assert [eid for eid, _ in chiamate] == [s.experience_id for s in it.stops]
    assert [p for _, p in chiamate] == [True] + [False] * (len(chiamate) - 1)


def test_la_guardia_scatta() -> None:
    """Doppio negativo: il controllo fallisce se la frase è ripetuta o fuori
    posto."""
    frase = "Cerchi silenzio e raccoglimento."
    stops = [
        ItineraryStop(experience_id=f"e{i}", arrivo=time(10 + i, 0), durata_min=30,
                      reason=f"{frase} Al chiuso." if i else "Al chiuso.")
        for i in range(3)
    ]
    it = Itinerary(person_id="p", stops=stops, generated_at=datetime(2026, 1, 1))
    assert len(_errori_profilo(it)) == 3


# ---------------------------------------------------------------------------
# Adattamento
# ---------------------------------------------------------------------------


def _segnali_adattamento(it: Itinerary) -> dict[str, Signal]:
    place = {e.id: e.place_id for e in ESPERIENZE}
    luoghi = [place[s.experience_id] for s in it.stops if s.experience_id in place]
    return {
        "pioggia": Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0)),
        "affollato-ovunque": Signal(
            meteo="sereno", affollamento=dict.fromkeys(luoghi, 0.95), stanchezza=0.0,
            ora=time(10, 0),
        ),
        "prima-affollata": Signal(
            meteo="sereno", affollamento=dict.fromkeys(luoghi[:1], 0.95), stanchezza=0.0,
            ora=time(10, 0),
        ),
        "stanchezza": Signal(meteo="sereno", affollamento={}, stanchezza=0.9, ora=time(10, 0)),
    }


@pytest.mark.parametrize(("nome_fn", "reason_fn"), REASON_FNS, ids=[n for n, _ in REASON_FNS])
@pytest.mark.parametrize("profilo", sorted(PROFILI))
def test_dopo_adattamento_profilo_al_massimo_una_volta(
    profilo: str, nome_fn: str, reason_fn: ReasonFn | None
) -> None:
    ctx = _ctx(profilo, "sereno")
    cands = SeedCandidateSource().candidates(ctx)
    base = compose_itinerary(ctx, cands, reason_fn, vocabolario=VOCABOLARIO)
    adapt_fn = adapt_reason if reason_fn is not None else None
    for nome, segnale in _segnali_adattamento(base).items():
        for prof in (PROFILI[profilo], None):
            it = adapt_itinerary(
                base, segnale, cands, prof, reason_fn, adapt_fn, vocabolario=VOCABOLARIO
            )
            totale = sum(_conta_profilo(s.reason) for s in it.stops)
            assert totale <= 1, (profilo, nome, [s.reason for s in it.stops])
            assert all(s.reason.strip() for s in it.stops)
            for i, s in enumerate(it.stops):
                if s.esito_adattamento is EsitoAdattamento.SOSTITUITA:
                    assert _conta_profilo(s.reason) == 0, s.reason
                if i > 0:
                    assert _conta_profilo(s.reason) == 0, (i, s.reason)


def test_motivo_del_sostituto_e_il_suo_non_la_connessione() -> None:
    ctx = _ctx("contemplativo", "sereno")
    cands = SeedCandidateSource().candidates(ctx)
    per_id = {c.experience.id: c for c in cands}
    base = compose_itinerary(ctx, cands, compose_reason, vocabolario=VOCABOLARIO)
    pioggia = Signal(meteo="pioggia", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    it = adapt_itinerary(
        base, pioggia, cands, ctx.profile, compose_reason, adapt_reason,
        vocabolario=VOCABOLARIO,
    )
    sostituite = [s for s in it.stops if s.esito_adattamento is EsitoAdattamento.SOSTITUITA]
    assert sostituite, "il caso deve esercitare almeno una sostituzione"
    for s in sostituite:
        alt = per_id[s.experience_id]
        atteso = adapt_reason(
            compose_reason(alt, ctx.profile, [], prima_tappa=False), "la pioggia"
        )
        assert s.reason.startswith(atteso), (s.reason, atteso)
        for connessione in alt.connessioni:
            assert connessione.rstrip(".") not in s.reason


# ---------------------------------------------------------------------------
# Luoghi con preposizione: con_luogo
# ---------------------------------------------------------------------------


def _cand(
    id_: str, *, al_chiuso: bool, articolo: str | None, nome: str, prezzo: float | None = None,
) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id=id_, titolo=f"Titolo {id_}", place_id=f"luogo-{id_}", temi=[],
            durata_min=30, al_chiuso=al_chiuso, accessibile=True, prezzo_eur=prezzo,
        ),
        place_nome=nome,
        # Una connessione che il motivo NON deve mai leggere.
        connessioni=[f"Connessione di {id_} che non va nel motivo."],
        place_articolo=articolo,
        temi_etichette=["storia"],
    )


def _itinerario_una_tappa(id_: str) -> Itinerary:
    return Itinerary(
        person_id="p",
        stops=[ItineraryStop(experience_id=id_, arrivo=time(10, 0), durata_min=30,
                             reason="Motivo ricevuto.")],
        generated_at=datetime(2026, 1, 1),
    )


def test_sostituzione_per_affollamento_nomina_il_luogo_con_articolo() -> None:
    orig = _cand("orig", al_chiuso=True, articolo="la", nome="Torre di Prova")
    alt = _cand("alt", al_chiuso=True, articolo=None, nome="Via di Prova")
    segnale = Signal(
        meteo="sereno", affollamento={"luogo-orig": 0.95}, stanchezza=0.0, ora=time(10, 0)
    )
    it = adapt_itinerary(
        _itinerario_una_tappa("orig"), segnale, [orig, alt], None, vocabolario=VOCABOLARIO
    )
    assert it.stops[0].experience_id == "alt"
    assert it.stops[0].reason == (
        "Sostituita per l'affollamento alla Torre di Prova. Temi: storia. Al chiuso, gratuita."
    )


@pytest.mark.parametrize(
    ("articolo", "nome", "dove"),
    [
        ("la", "Torre di Prova", "alla Torre di Prova"),
        ("l'", "Orto di Prova", "all'Orto di Prova"),
        ("il", "Duomo di Prova", "al Duomo di Prova"),
        (None, "Via di Prova", "a Via di Prova"),
    ],
)
def test_frase_di_esito_affollamento_con_articolo(
    articolo: str | None, nome: str, dove: str
) -> None:
    orig = _cand("orig", al_chiuso=True, articolo=articolo, nome=nome)
    segnale = Signal(
        meteo="sereno", affollamento={"luogo-orig": 0.95}, stanchezza=0.0, ora=time(10, 0)
    )
    it = adapt_itinerary(
        _itinerario_una_tappa("orig"), segnale, [orig], None, vocabolario=VOCABOLARIO
    )
    frase = (
        f"C'è molta gente {dove}, ma non c'è un'alternativa più tranquilla compatibile "
        "con questo percorso e con il tempo a disposizione: la tappa resta in programma."
    )
    assert it.stops[0].esito_adattamento is EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA
    assert it.stops[0].reason == f"Motivo ricevuto. {frase}"
    # Un secondo adattamento, senza affollamento: la frase sparisce.
    sereno = Signal(meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0))
    di_nuovo = adapt_itinerary(it, sereno, [orig], None, vocabolario=VOCABOLARIO)
    assert di_nuovo.stops[0].reason == "Motivo ricevuto."


@pytest.mark.parametrize(
    "luogo_vecchio",
    ["a Torre di Prova", "a Chiesa di San Qualcosa", "alla Torre", "all'Orto", "agli Archi"],
)
def test_frase_di_esito_riconosciuta_anche_nella_forma_vecchia(luogo_vecchio: str) -> None:
    frase = (
        f"C'è molta gente {luogo_vecchio}, ma non c'è un'alternativa più tranquilla "
        "compatibile con questo percorso e con il tempo a disposizione: la tappa resta "
        "in programma."
    )
    assert _senza_frase_esito(f"Motivo. {frase}") == "Motivo."
    assert _senza_frase_esito(f"Motivo. {frase} Offerta da X.") == "Motivo. Offerta da X."


def test_frase_esito_usa_con_luogo() -> None:
    frase = _frase_esito(
        EsitoAdattamento.MANTENUTA_SENZA_ALTERNATIVA, motivo="affollamento",
        luogo="Orto di Prova", articolo="l'",
    )
    assert frase is not None and frase.startswith("C'è molta gente all'Orto di Prova, ma")


# ---------------------------------------------------------------------------
# Fallback interno == RAG
# ---------------------------------------------------------------------------


def _candidati_vari() -> list[GraphCandidate]:
    """Candidati del seed in più contesti (con e senza luoghi già visti, così
    da esercitare la vicinanza) più candidati sintetici sui casi limite."""
    fonte = SeedCandidateSource()
    out: list[GraphCandidate] = []
    for visti in ([], ["duomo-san-martino"], ["orto-botanico"], ["via-fillungo"]):
        out.extend(fonte.candidates(_ctx("neutro", "sereno", visti)))
    base = _cand("s1", al_chiuso=False, articolo="l'", nome="Orto di Prova", prezzo=0.0)
    out.extend([
        base,
        base.model_copy(update={"racconti": ["un racconto senza punto", "secondo"]}),
        base.model_copy(update={"temi_etichette": [], "racconti": []}),
        base.model_copy(update={"temi_etichette": [" a ", "", "b"]}),
        base.model_copy(update={
            "distanza_m": 250, "vicinanza_nome": "Duomo di Prova", "vicinanza_articolo": "il",
        }),
        base.model_copy(update={
            "distanza_m": 80, "vicinanza_nome": "Orto di Prova", "vicinanza_articolo": "l'",
        }),
        base.model_copy(update={"distanza_m": 80, "vicinanza_nome": None}),
        _cand("s2", al_chiuso=True, articolo=None, nome="Via di Prova", prezzo=12.5),
    ])
    return out


@pytest.mark.parametrize("prima_tappa", [True, False])
@pytest.mark.parametrize(
    "segnali",
    [[], ["pioggia"], ["caldo"], ["affollamento"], ["stanchezza"], ["pioggia", "stanchezza"],
     ["Pioggia "], ["una frase libera"], [""]],
)
def test_fallback_identico_alla_rag(segnali: list[str], prima_tappa: bool) -> None:
    cands = _candidati_vari()
    assert any(c.vicinanza_nome for c in cands)
    assert any(c.racconti for c in cands)
    for profilo in PROFILI.values():
        for cand in cands:
            atteso = compose_reason(cand, profilo, segnali, prima_tappa=prima_tappa)
            ottenuto = _fallback_reason(cand, profilo, segnali, prima_tappa=prima_tappa)
            assert ottenuto == atteso, (cand.experience.id, ottenuto, atteso)
            assert ottenuto.strip()


# ---------------------------------------------------------------------------
# Code (eventi promossi, fluttuanti): luogo con il suo articolo
# ---------------------------------------------------------------------------

_ULTIMA = date(2026, 3, 2)
_VISITA = date(2026, 3, 9)  # occorrenza attesa (cadenza 7): in finestra


def _cand_coda(articolo: str | None, nome: str) -> GraphCandidate:
    return GraphCandidate(
        experience=ExperienceNode(
            id="exp-fisso", titolo="Facciata", place_id="luogo-fisso", temi=["arte"],
            durata_min=30, al_chiuso=False, accessibile=True,
        ),
        place_nome=nome,
        place_articolo=articolo,
        connessioni=[],
    )


def _ctx_coda() -> VisitorContext:
    profilo = EmotionalProfile(
        curiosita=0.1, contemplazione=0.1, arte=0.9, con_bambini=False,
        tempo_disponibile_min=200,
    )
    segnale = Signal(
        meteo="sereno", affollamento={}, stanchezza=0.0, ora=time(10, 0), data=_VISITA,
        eventi_attivi=[
            SegnaleFluttuante(
                id="violinista-1", descrizione="Un violinista suona", temi=["musica"],
                place_id="luogo-fisso", non_commerciale=True,
                valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
            )
        ],
    )
    return VisitorContext(person_id="p", profile=profilo, signal=segnale)


def _evento(place_id: str = "luogo-fisso") -> EventoPromosso:
    return EventoPromosso(
        id=f"evento-{place_id}-musica", place_id=place_id, temi=["musica"],
        ultima_occorrenza=_ULTIMA, cadenza_giorni=7.0,
    )


@pytest.mark.parametrize(
    ("articolo", "nome", "presso", "a_luogo"),
    [
        ("la", "Chiesa di Prova", "Presso la Chiesa di Prova ", "alla Chiesa di Prova:"),
        ("l'", "Orto di Prova", "Presso l'Orto di Prova ", "all'Orto di Prova:"),
        ("il", "Duomo di Prova", "Presso il Duomo di Prova ", "al Duomo di Prova:"),
        (None, "Via di Prova", "Presso Via di Prova ", "a Via di Prova:"),
    ],
)
def test_code_nominano_il_luogo_con_articolo(
    articolo: str | None, nome: str, presso: str, a_luogo: str
) -> None:
    it = compose_itinerary(
        _ctx_coda(), [_cand_coda(articolo, nome)], compose_reason,
        eventi_promossi=[_evento()], vocabolario=VOCABOLARIO,
    )
    per_id = {s.experience_id: s.reason for s in it.stops}
    assert per_id["evento-luogo-fisso-musica"].startswith(presso), per_id
    assert per_id["fluttuante-violinista-1"] == (
        f"Un violinista suona {a_luogo} un'aggiunta per oggi, non era già in programma."
    )


def test_evento_su_luogo_sconosciuto_senza_articolo() -> None:
    """Luogo non tra i candidati: `place_id` grezzo, nessun articolo inventato."""
    it = compose_itinerary(
        _ctx_coda(), [_cand_coda("la", "Chiesa di Prova")], compose_reason,
        eventi_promossi=[_evento("luogo-ignoto")], vocabolario=VOCABOLARIO,
    )
    reason = next(s.reason for s in it.stops if s.experience_id == "evento-luogo-ignoto-musica")
    assert reason.startswith("Presso luogo-ignoto si ripete")
