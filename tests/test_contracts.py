"""Contract test: `packages/contracts` deve essere conforme a
`docs/DATA_CONTRACTS.md`. Questa suite è la rete di sicurezza contro la
divergenza di schema tra servizi: se un campo canonico cambia nome, sparisce,
o allarga i propri vincoli, questi test devono rompersi PRIMA di un servizio
a valle.

Non "aggiustare" un modello per far passare questi test: se un test fallisce
qui, il bug è nel pacchetto contratti (o nel test stesso, se diverge dal
white paper) — segnalalo a `contract-keeper`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import contracts
import pytest
from contracts import (
    BehaviorEvent,
    DashboardFlowsResponse,
    DashboardIndexResponse,
    EmotionalProfile,
    EventoPromosso,
    ExperienceCandidate,
    ExperienceNode,
    FasciaApertura,
    FlowCell,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    PersonKind,
    SegnaleFluttuante,
    Signal,
    StatoSegnaleFluttuante,
    UrbanIntelligenceIndex,
    VisitorContext,
    rientra_in_orario,
    segnale_fluttuante_ammissibile,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# 1. I 18 tipi canonici sono importabili da `contracts`
# ---------------------------------------------------------------------------

CANONICAL_TYPES = [
    "EmotionalProfile",
    "Signal",
    "SegnaleFluttuante",
    "PersonKind",
    "VisitorContext",
    "FasciaApertura",
    "ExperienceNode",
    "EventoPromosso",
    "ExperienceCandidate",
    "ItineraryStop",
    "Itinerary",
    "MemoryKind",
    "MemoryContribution",
    "BehaviorEvent",
    "UrbanIntelligenceIndex",
    "DashboardIndexResponse",
    "FlowCell",
    "DashboardFlowsResponse",
]


def test_diciotto_tipi_canonici_importabili() -> None:
    assert len(CANONICAL_TYPES) == 18
    for name in CANONICAL_TYPES:
        assert hasattr(contracts, name), f"{name} non importabile da `contracts`"


# ---------------------------------------------------------------------------
# Fixture: istanze valide minime dei modelli, riutilizzate nei test sotto
# ---------------------------------------------------------------------------


def make_profile(**overrides: object) -> EmotionalProfile:
    base: dict[str, object] = dict(
        curiosita=0.5,
        contemplazione=0.5,
        arte=0.5,
        con_bambini=False,
        tempo_disponibile_min=120,
    )
    base.update(overrides)
    return EmotionalProfile(**base)  # type: ignore[arg-type]


def make_signal(**overrides: object) -> Signal:
    base: dict[str, object] = dict(
        meteo="sereno",
        affollamento={"piazza-anfiteatro": 0.3},
        stanchezza=0.2,
        ora=time(10, 30),
    )
    base.update(overrides)
    return Signal(**base)  # type: ignore[arg-type]


def make_segnale_fluttuante(**overrides: object) -> SegnaleFluttuante:
    base: dict[str, object] = dict(
        id="fluttuante-1",
        descrizione="un violinista suona in piazza",
        temi=["musica"],
        place_id="piazza-anfiteatro",
        non_commerciale=True,
        # Lontano nel futuro, non un "oggi" che scadrebbe da solo col tempo:
        # la fixture deve restare ATTIVO indipendentemente da quando la
        # suite gira.
        valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
    )
    base.update(overrides)
    return SegnaleFluttuante(**base)  # type: ignore[arg-type]


def make_evento_promosso(**overrides: object) -> EventoPromosso:
    base: dict[str, object] = dict(
        id="evento-piazza-anfiteatro-musica",
        place_id="piazza-anfiteatro",
        temi=["musica"],
    )
    base.update(overrides)
    return EventoPromosso(**base)  # type: ignore[arg-type]


def make_visitor_context(**overrides: object) -> VisitorContext:
    base: dict[str, object] = dict(
        person_id="visitor-pseudo-1",
        profile=make_profile(),
        signal=make_signal(),
    )
    base.update(overrides)
    return VisitorContext(**base)  # type: ignore[arg-type]


def make_experience_node(**overrides: object) -> ExperienceNode:
    base: dict[str, object] = dict(
        id="exp-1",
        titolo="Passeggiata sulle Mura",
        place_id="mura-urbane",
        temi=["storia", "panorama"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
        partner_id=None,
        prezzo_eur=None,
    )
    base.update(overrides)
    return ExperienceNode(**base)  # type: ignore[arg-type]


def make_experience_candidate(**overrides: object) -> ExperienceCandidate:
    base: dict[str, object] = dict(
        experience_id="exp-1",
        score=0.8,
        reason="Coerente con la curiosità dichiarata nel profilo.",
    )
    base.update(overrides)
    return ExperienceCandidate(**base)  # type: ignore[arg-type]


def make_itinerary_stop(**overrides: object) -> ItineraryStop:
    base: dict[str, object] = dict(
        experience_id="exp-1",
        arrivo=time(10, 0),
        durata_min=45,
        reason="Vicino al punto di partenza e adatto al tempo disponibile.",
    )
    base.update(overrides)
    return ItineraryStop(**base)  # type: ignore[arg-type]


def make_itinerary(**overrides: object) -> Itinerary:
    base: dict[str, object] = dict(
        person_id="visitor-pseudo-1",
        stops=[make_itinerary_stop()],
        generated_at=datetime(2026, 7, 13, 9, 0, 0),
    )
    base.update(overrides)
    return Itinerary(**base)  # type: ignore[arg-type]


def make_memory_contribution(**overrides: object) -> MemoryContribution:
    base: dict[str, object] = dict(
        id="mem-1",
        kind=MemoryKind.RACCONTO,
        testo="Un racconto di bottega.",
        riguarda=["bottega-1"],
        contributor_id="contributor-pseudo-1",
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime(2026, 7, 13, 9, 0, 0),
    )
    base.update(overrides)
    return MemoryContribution(**base)  # type: ignore[arg-type]


def make_behavior_event(**overrides: object) -> BehaviorEvent:
    base: dict[str, object] = dict(
        person_id="visitor-pseudo-1",
        tipo="view",
        experience_id="exp-1",
        ts=datetime(2026, 7, 13, 9, 0, 0),
    )
    base.update(overrides)
    return BehaviorEvent(**base)  # type: ignore[arg-type]


def make_index(**overrides: object) -> UrbanIntelligenceIndex:
    base: dict[str, object] = dict(
        periodo="2026-07",
        tempo_medio_esperienza_min=45.0,
        coinvolgimento=0.6,
        soddisfazione=4.2,
        tasso_ritorno=0.3,
        nuovi_percorsi=0.3,
        attivazione_locale=0.4,
        distribuzione_flussi=0.7,
        contributi_memoria=12,
    )
    base.update(overrides)
    return UrbanIntelligenceIndex(**base)  # type: ignore[arg-type]


def make_dashboard_index_response(**overrides: object) -> DashboardIndexResponse:
    base: dict[str, object] = dict(
        periodo="2026-07",
        disponibile=True,
        index=make_index(),
        motivo_indisponibilita=None,
    )
    base.update(overrides)
    return DashboardIndexResponse(**base)  # type: ignore[arg-type]


def make_flow_cell(**overrides: object) -> FlowCell:
    base: dict[str, object] = dict(
        place_id="piazza-anfiteatro",
        disponibile=True,
        conteggio_tappe=42,
    )
    base.update(overrides)
    return FlowCell(**base)  # type: ignore[arg-type]


def make_dashboard_flows_response(**overrides: object) -> DashboardFlowsResponse:
    base: dict[str, object] = dict(
        periodo="2026-07",
        celle=[make_flow_cell()],
    )
    base.update(overrides)
    return DashboardFlowsResponse(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Campi canonici presenti (model_fields) per ogni modello
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected_fields"),
    [
        (
            EmotionalProfile,
            {
                "curiosita",
                "contemplazione",
                "arte",
                "con_bambini",
                "tempo_disponibile_min",
                "accessibilita_richiesta",
                "ha_gia_visto_firenze",
                "lingue",
            },
        ),
        (
            Signal,
            {"meteo", "affollamento", "stanchezza", "ora", "giorno_settimana", "eventi_attivi"},
        ),
        (
            SegnaleFluttuante,
            {
                "id",
                "descrizione",
                "temi",
                "place_id",
                "non_commerciale",
                "valido_fino",
                "stato",
            },
        ),
        (
            VisitorContext,
            {"person_id", "kind", "profile", "signal", "luoghi_gia_visti"},
        ),
        (
            ExperienceNode,
            {
                "id",
                "titolo",
                "place_id",
                "temi",
                "durata_min",
                "al_chiuso",
                "accessibile",
                "alimenta_memoria",
                "partner_id",
                "prezzo_eur",
                "orari_apertura",
            },
        ),
        (
            FasciaApertura,
            {"giorno_settimana", "apertura", "chiusura"},
        ),
        (
            EventoPromosso,
            {"id", "place_id", "temi"},
        ),
        (
            ExperienceCandidate,
            {"experience_id", "score", "reason"},
        ),
        (
            ItineraryStop,
            {"experience_id", "arrivo", "durata_min", "reason"},
        ),
        (
            Itinerary,
            {"person_id", "stops", "generated_at", "adattato_da_segnale"},
        ),
        (
            MemoryContribution,
            {
                "id",
                "kind",
                "testo",
                "media_uri",
                "riguarda",
                "contributor_id",
                "contributor_kind",
                "esperienza_id",
                "consenso",
                "licenza",
                "creato_il",
                "curato",
            },
        ),
        (
            BehaviorEvent,
            {"person_id", "tipo", "experience_id", "ts"},
        ),
        (
            UrbanIntelligenceIndex,
            {
                "periodo",
                "tempo_medio_esperienza_min",
                "coinvolgimento",
                "soddisfazione",
                "tasso_ritorno",
                "nuovi_percorsi",
                "attivazione_locale",
                "distribuzione_flussi",
                "contributi_memoria",
            },
        ),
        (
            DashboardIndexResponse,
            {"periodo", "disponibile", "index", "motivo_indisponibilita"},
        ),
        (
            FlowCell,
            {"place_id", "disponibile", "conteggio_tappe"},
        ),
        (
            DashboardFlowsResponse,
            {"periodo", "giorno", "ora", "celle"},
        ),
    ],
)
def test_campi_canonici_presenti(model: type, expected_fields: set[str]) -> None:
    actual = set(model.model_fields.keys())  # type: ignore[attr-defined]
    missing = expected_fields - actual
    assert not missing, f"{model.__name__}: campi canonici mancanti: {missing}"


# ---------------------------------------------------------------------------
# 3. Vincoli numerici 0..1 e 0..5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
@pytest.mark.parametrize("field", ["curiosita", "contemplazione", "arte"])
def test_emotional_profile_campi_0_1_rifiutano_fuori_range(
    field: str, bad_value: float
) -> None:
    with pytest.raises(ValidationError):
        make_profile(**{field: bad_value})


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_signal_stanchezza_rifiuta_fuori_range(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        make_signal(stanchezza=bad_value)


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_experience_candidate_score_rifiuta_fuori_range(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        make_experience_candidate(score=bad_value)


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_index_distribuzione_flussi_rifiuta_fuori_range(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        make_index(distribuzione_flussi=bad_value)


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
@pytest.mark.parametrize(
    "field",
    [
        "coinvolgimento",
        "tasso_ritorno",
        "attivazione_locale",
        "distribuzione_flussi",
        "nuovi_percorsi",
    ],
)
def test_index_campi_0_1_rifiutano_fuori_range(field: str, bad_value: float) -> None:
    with pytest.raises(ValidationError):
        make_index(**{field: bad_value})


def test_soddisfazione_accetta_5() -> None:
    idx = make_index(soddisfazione=5)
    assert idx.soddisfazione == 5


def test_soddisfazione_rifiuta_5_1() -> None:
    with pytest.raises(ValidationError):
        make_index(soddisfazione=5.1)


def test_soddisfazione_accetta_none() -> None:
    # Nessuna fonte dati reale oggi (niente recensioni/survey in prodotto):
    # None è un valore legittimo e atteso, non un'eccezione da gestire altrove.
    idx = make_index(soddisfazione=None)
    assert idx.soddisfazione is None


# ---------------------------------------------------------------------------
# 3bis. Signal.affollamento: field_validator per-place_id in [0,1]
# ---------------------------------------------------------------------------


def test_signal_affollamento_rifiuta_valore_1_5() -> None:
    with pytest.raises(ValidationError):
        make_signal(affollamento={"piazza-anfiteatro": 1.5})


def test_signal_affollamento_rifiuta_valore_negativo() -> None:
    with pytest.raises(ValidationError):
        make_signal(affollamento={"piazza-anfiteatro": -0.1})


def test_signal_affollamento_accetta_valori_limite() -> None:
    signal = make_signal(affollamento={"piazza-anfiteatro": 0.0, "mura-urbane": 1.0})
    assert signal.affollamento == {"piazza-anfiteatro": 0.0, "mura-urbane": 1.0}


def test_signal_affollamento_messaggio_contiene_place_id_incriminato() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_signal(affollamento={"piazza-napoleone": 2.0})
    assert "piazza-napoleone" in str(exc_info.value)


def test_signal_affollamento_dict_vuoto_accettato() -> None:
    signal = make_signal(affollamento={})
    assert signal.affollamento == {}


# ---------------------------------------------------------------------------
# 4. extra="forbid": campi non canonici vengono rifiutati
# ---------------------------------------------------------------------------


def test_extra_forbid_su_itinerary_stop() -> None:
    with pytest.raises(ValidationError):
        ItineraryStop(
            experience_id="exp-1",
            arrivo=time(10, 0),
            tempo_min=45,  # nome non canonico: il campo giusto è `durata_min`
            reason="reason",
        )


def test_extra_forbid_su_experience_node() -> None:
    with pytest.raises(ValidationError):
        ExperienceNode(
            id="exp-1",
            titolo="t",
            place_id="p",
            temi=[],
            durata_min=10,
            al_chiuso=False,
            accessibile=True,
            partner_id=None,
            prezzo_eur=None,
            tempo_min=10,  # extra non canonico
        )


def test_extra_forbid_su_emotional_profile() -> None:
    with pytest.raises(ValidationError):
        make_profile(campo_fantasma="x")


# ---------------------------------------------------------------------------
# 5. Default corretti
# ---------------------------------------------------------------------------


def test_default_accessibilita_richiesta_false() -> None:
    assert make_profile().accessibilita_richiesta is False


def test_default_lingue_it() -> None:
    assert make_profile().lingue == ["it"]


def test_default_kind_turista() -> None:
    assert make_visitor_context().kind == PersonKind.TURISTA


def test_default_adattato_da_segnale_false() -> None:
    assert make_itinerary().adattato_da_segnale is False


def test_default_curato_false() -> None:
    assert make_memory_contribution().curato is False


def test_default_alimenta_memoria_false() -> None:
    assert make_experience_node().alimenta_memoria is False


def test_default_partner_id_e_prezzo_eur_none_se_omessi() -> None:
    # partner_id e prezzo_eur sono opzionali: costruzione SENZA passarli.
    node = ExperienceNode(
        id="exp-1",
        titolo="Passeggiata sulle Mura",
        place_id="mura-urbane",
        temi=["storia", "panorama"],
        durata_min=60,
        al_chiuso=False,
        accessibile=True,
    )
    assert node.partner_id is None
    assert node.prezzo_eur is None


def test_experience_node_prezzo_eur_negativo_rifiutato() -> None:
    with pytest.raises(ValidationError):
        make_experience_node(prezzo_eur=-1)


def test_default_orari_apertura_lista_vuota_se_omesso() -> None:
    # Nessun vincolo dichiarato = SEMPRE considerata aperta (comportamento
    # invariato per ogni esperienza esistente, che oggi non dichiara orari).
    assert make_experience_node().orari_apertura == []


def test_default_giorno_settimana_none_se_omesso() -> None:
    # Mai un giorno fabbricato: il chiamante che non lo specifica ottiene
    # `None`, non un giorno arbitrario (es. sempre lunedì).
    assert make_signal().giorno_settimana is None


# ---------------------------------------------------------------------------
# 5bis. `FasciaApertura` e `rientra_in_orario` — validazione minima degli
# orari di apertura (Wave 3a+, richiesta esplicitamente prima del Living
# Lab dopo lo scarto trovato tra il White Paper e il codice, vedi
# docs/LIMITI.md). Fasce settimanali RICORRENTI soltanto: niente eccezioni
# calendariali, niente capienza, niente conflitti di slot.
# ---------------------------------------------------------------------------


def make_fascia_apertura(**overrides: object) -> FasciaApertura:
    base: dict[str, object] = dict(
        giorno_settimana=5,  # sabato
        apertura=time(10, 0),
        chiusura=time(13, 0),
    )
    base.update(overrides)
    return FasciaApertura(**base)  # type: ignore[arg-type]


def test_fascia_apertura_giorno_fuori_range_rifiutato() -> None:
    with pytest.raises(ValidationError):
        make_fascia_apertura(giorno_settimana=7)
    with pytest.raises(ValidationError):
        make_fascia_apertura(giorno_settimana=-1)


def test_fascia_apertura_chiusura_prima_di_apertura_rifiutata() -> None:
    with pytest.raises(ValidationError):
        make_fascia_apertura(apertura=time(18, 0), chiusura=time(10, 0))


def test_fascia_apertura_chiusura_uguale_apertura_rifiutata() -> None:
    # Niente fasce di durata zero: `chiusura` deve essere STRETTAMENTE dopo
    # `apertura`.
    with pytest.raises(ValidationError):
        make_fascia_apertura(apertura=time(10, 0), chiusura=time(10, 0))


def test_fascia_apertura_valida() -> None:
    fascia = make_fascia_apertura()
    assert fascia.giorno_settimana == 5
    assert fascia.apertura == time(10, 0)
    assert fascia.chiusura == time(13, 0)


def test_rientra_in_orario_nessuna_fascia_dichiarata_passa_sempre() -> None:
    # Lista vuota = nessun vincolo: nessuna esclusione fabbricata.
    assert rientra_in_orario([], 5, time(3, 0)) is True
    assert rientra_in_orario([], None, time(3, 0)) is True


def test_rientra_in_orario_giorno_sconosciuto_passa_sempre() -> None:
    # `giorno_settimana=None`: il chiamante non l'ha specificato, non si
    # inventa un giorno per applicare il filtro.
    fascia = make_fascia_apertura()
    assert rientra_in_orario([fascia], None, time(11, 0)) is True


def test_rientra_in_orario_dentro_fascia() -> None:
    fascia = make_fascia_apertura(giorno_settimana=5, apertura=time(10, 0), chiusura=time(13, 0))
    assert rientra_in_orario([fascia], 5, time(10, 0)) is True  # limite inferiore incluso
    assert rientra_in_orario([fascia], 5, time(12, 59)) is True


def test_rientra_in_orario_al_limite_di_chiusura_esclusa() -> None:
    # `chiusura` è un limite ESCLUSO: alle 13:00 in punto l'esperienza è
    # già chiusa, non nell'ultimo minuto della fascia.
    fascia = make_fascia_apertura(giorno_settimana=5, apertura=time(10, 0), chiusura=time(13, 0))
    assert rientra_in_orario([fascia], 5, time(13, 0)) is False


def test_rientra_in_orario_fuori_fascia_stesso_giorno() -> None:
    fascia = make_fascia_apertura(giorno_settimana=5, apertura=time(10, 0), chiusura=time(13, 0))
    assert rientra_in_orario([fascia], 5, time(9, 59)) is False
    assert rientra_in_orario([fascia], 5, time(15, 0)) is False


def test_rientra_in_orario_giorno_diverso_da_quello_dichiarato() -> None:
    fascia = make_fascia_apertura(giorno_settimana=5, apertura=time(10, 0), chiusura=time(13, 0))
    assert rientra_in_orario([fascia], 2, time(11, 0)) is False


def test_rientra_in_orario_almeno_una_fascia_tra_piu_basta() -> None:
    # Più fasce nella stessa settimana (es. mattina e pomeriggio, o giorni
    # diversi): basta rientrare in UNA qualunque.
    mattina_sabato = make_fascia_apertura(
        giorno_settimana=5, apertura=time(9, 0), chiusura=time(12, 0)
    )
    pomeriggio_domenica = make_fascia_apertura(
        giorno_settimana=6, apertura=time(15, 0), chiusura=time(18, 0)
    )
    fasce = [mattina_sabato, pomeriggio_domenica]
    assert rientra_in_orario(fasce, 5, time(10, 0)) is True
    assert rientra_in_orario(fasce, 6, time(16, 0)) is True
    assert rientra_in_orario(fasce, 5, time(16, 0)) is False  # sabato pomeriggio: non dichiarato


# ---------------------------------------------------------------------------
# 5ter. `SegnaleFluttuante` e `segnale_fluttuante_ammissibile` — livello
# "accade ora" (Signal.eventi_attivi), diverso dal livello "programmato"
# (:Evento, fuori scope: docs/LIMITI.md). Il campo era `list[str]`, mai letto
# da nessuna logica: un interruttore già cablato, mai acceso prima d'ora.
# ---------------------------------------------------------------------------


def test_segnale_fluttuante_valido() -> None:
    segnale = make_segnale_fluttuante()
    assert segnale.id == "fluttuante-1"
    assert segnale.descrizione == "un violinista suona in piazza"
    assert segnale.temi == ["musica"]
    assert segnale.place_id == "piazza-anfiteatro"
    assert segnale.non_commerciale is True
    assert segnale.valido_fino == datetime(2099, 1, 1, tzinfo=UTC)
    assert segnale.stato == StatoSegnaleFluttuante.ATTIVO


def test_segnale_fluttuante_descrizione_vuota_rifiutata() -> None:
    with pytest.raises(ValidationError):
        make_segnale_fluttuante(descrizione="")


def test_segnale_fluttuante_temi_vuoti_rifiutati() -> None:
    with pytest.raises(ValidationError):
        make_segnale_fluttuante(temi=[])


def test_segnale_fluttuante_non_commerciale_obbligatorio_nessun_default() -> None:
    # Nessun default (a differenza di `orari_apertura=[]`): chi genera il
    # segnale DEVE dichiararlo esplicitamente, stesso principio di
    # `MemoryContribution.consenso` — mai un'eccezione lasciata al buon senso.
    # `valido_fino` valorizzato esplicitamente per isolare il test sul solo
    # campo mancante (`non_commerciale`).
    with pytest.raises(ValidationError):
        SegnaleFluttuante(
            id="x",
            descrizione="d",
            temi=["musica"],
            place_id="p",
            valido_fino=datetime(2099, 1, 1, tzinfo=UTC),
        )  # type: ignore[call-arg]


def test_segnale_fluttuante_valido_fino_obbligatorio_nessun_default() -> None:
    # Stesso principio del test sopra, campo speculare: un fluttuante
    # persistito senza scadenza vivrebbe per sempre.
    with pytest.raises(ValidationError):
        SegnaleFluttuante(
            id="x",
            descrizione="d",
            temi=["musica"],
            place_id="p",
            non_commerciale=True,
        )  # type: ignore[call-arg]


def test_segnale_fluttuante_valido_fino_naive_rifiutato() -> None:
    # `field_validator`: un datetime senza tzinfo non è confrontabile in modo
    # affidabile con `datetime.now(UTC)` — stesso obbligo di ogni timestamp
    # persistito nel repo (vedi `graph.seed_lucca`).
    with pytest.raises(ValidationError):
        make_segnale_fluttuante(valido_fino=datetime(2099, 1, 1))


def test_segnale_fluttuante_stato_default_attivo() -> None:
    assert make_segnale_fluttuante().stato == StatoSegnaleFluttuante.ATTIVO


def test_segnale_fluttuante_gia_scaduto_normalizza_a_expired() -> None:
    # Caso-limite: `valido_fino` già nel passato alla costruzione — il
    # segnale nasce già `EXPIRED`, qualunque `stato` sia stato passato
    # (qui non passato affatto: il default `ATTIVO` viene comunque forzato).
    passato = datetime.now(UTC) - timedelta(hours=1)
    segnale = make_segnale_fluttuante(valido_fino=passato)
    assert segnale.stato == StatoSegnaleFluttuante.EXPIRED


def test_segnale_fluttuante_gia_scaduto_normalizza_anche_se_stato_attivo_dichiarato() -> None:
    # Stesso caso-limite, ma con `stato=ATTIVO` dichiarato esplicitamente
    # dal chiamante: normalizza comunque, non fidandosi di uno stato
    # dichiarato incoerente con la scadenza dichiarata.
    passato = datetime.now(UTC) - timedelta(hours=1)
    segnale = make_segnale_fluttuante(
        valido_fino=passato, stato=StatoSegnaleFluttuante.ATTIVO
    )
    assert segnale.stato == StatoSegnaleFluttuante.EXPIRED


def test_segnale_fluttuante_non_ancora_scaduto_resta_attivo_anche_se_expired_dichiarato() -> None:
    # La normalizzazione è a senso unico: forza EXPIRED quando la scadenza è
    # passata, ma non "resuscita" ad ATTIVO uno stato EXPIRED dichiarato con
    # una scadenza ancora futura — nessuna base per farlo: non è un caso
    # limite che questo contratto debba correggere, chi lo dichiara EXPIRED
    # con una scadenza futura sa qualcosa che il contratto non può verificare
    # (es. un segnale terminato in anticipo). Il contratto non lo impedisce.
    futuro = datetime.now(UTC) + timedelta(hours=1)
    segnale = make_segnale_fluttuante(
        valido_fino=futuro, stato=StatoSegnaleFluttuante.EXPIRED
    )
    assert segnale.stato == StatoSegnaleFluttuante.EXPIRED


def test_extra_forbid_su_segnale_fluttuante() -> None:
    with pytest.raises(ValidationError):
        make_segnale_fluttuante(campo_fantasma="x")


def test_segnale_fluttuante_ammissibile_vero_se_non_commerciale() -> None:
    assert segnale_fluttuante_ammissibile(make_segnale_fluttuante(non_commerciale=True)) is True


def test_segnale_fluttuante_ammissibile_falso_se_commerciale() -> None:
    assert segnale_fluttuante_ammissibile(make_segnale_fluttuante(non_commerciale=False)) is False


def test_signal_eventi_attivi_default_lista_vuota() -> None:
    # Comportamento INVARIATO: nessun chiamante esistente popola questo
    # campo oggi, quindi resta vuoto finché non viene dichiarato esplicitamente.
    assert make_signal().eventi_attivi == []


def test_signal_eventi_attivi_accetta_segnali_fluttuanti() -> None:
    segnale = make_segnale_fluttuante()
    signal = make_signal(eventi_attivi=[segnale])
    assert signal.eventi_attivi == [segnale]


def test_round_trip_json_segnale_fluttuante() -> None:
    segnale = make_segnale_fluttuante()
    ricostruito = SegnaleFluttuante.model_validate_json(segnale.model_dump_json())
    assert ricostruito == segnale


def test_round_trip_json_signal_con_eventi_attivi() -> None:
    signal = make_signal(eventi_attivi=[make_segnale_fluttuante()])
    ricostruito = Signal.model_validate_json(signal.model_dump_json())
    assert ricostruito == signal


# ---------------------------------------------------------------------------
# 5quater. `EventoPromosso` — un `:Evento` promosso e ATTIVO nel Knowledge
# Graph (Fase 3), livello "programmato" diverso dal fluttuante
# (`SegnaleFluttuante` sopra, "accade ORA"). Contratto minimo, deliberatamente
# senza `stato` (chi lo costruisce filtra GIÀ per attivo prima), senza
# `cadenza_giorni` (fuori scope v1) e senza accountability di promozione.
# ---------------------------------------------------------------------------


def test_evento_promosso_valido() -> None:
    evento = make_evento_promosso()
    assert evento.id == "evento-piazza-anfiteatro-musica"
    assert evento.place_id == "piazza-anfiteatro"
    assert evento.temi == ["musica"]


def test_evento_promosso_temi_vuoti_rifiutati() -> None:
    with pytest.raises(ValidationError):
        make_evento_promosso(temi=[])


def test_extra_forbid_su_evento_promosso() -> None:
    with pytest.raises(ValidationError):
        make_evento_promosso(stato="attivo")  # non canonico: filtrato PRIMA, mai qui
    with pytest.raises(ValidationError):
        make_evento_promosso(cadenza_giorni=7.0)  # fuori scope v1
    with pytest.raises(ValidationError):
        make_evento_promosso(promosso_da="promotore-pseudo-1")  # accountability, non consumo
    with pytest.raises(ValidationError):
        make_evento_promosso(descrizione="un violinista suona in piazza")  # non sopravvive alla promozione


def test_round_trip_json_evento_promosso() -> None:
    original = make_evento_promosso()
    dumped = original.model_dump_json()
    restored = EventoPromosso.model_validate_json(dumped)
    assert restored == original


# ---------------------------------------------------------------------------
# 6. Round-trip JSON
# ---------------------------------------------------------------------------


def test_round_trip_json_itinerary() -> None:
    original = make_itinerary(adattato_da_segnale=True)
    dumped = original.model_dump_json()
    restored = Itinerary.model_validate_json(dumped)
    assert restored == original


def test_round_trip_json_memory_contribution() -> None:
    original = make_memory_contribution()
    dumped = original.model_dump_json()
    restored = MemoryContribution.model_validate_json(dumped)
    assert restored == original


# ---------------------------------------------------------------------------
# 7. MemoryContribution richiede consenso e licenza
# ---------------------------------------------------------------------------


def test_memory_contribution_richiede_consenso() -> None:
    with pytest.raises(ValidationError):
        MemoryContribution(
            id="mem-1",
            kind=MemoryKind.RACCONTO,
            riguarda=["bottega-1"],
            contributor_id="contributor-pseudo-1",
            contributor_kind=PersonKind.CITTADINO,
            licenza="CC-BY-SA-4.0",
            creato_il=datetime(2026, 7, 13, 9, 0, 0),
            # consenso mancante
        )


def test_memory_contribution_richiede_licenza() -> None:
    with pytest.raises(ValidationError):
        MemoryContribution(
            id="mem-1",
            kind=MemoryKind.RACCONTO,
            riguarda=["bottega-1"],
            contributor_id="contributor-pseudo-1",
            contributor_kind=PersonKind.CITTADINO,
            consenso=True,
            creato_il=datetime(2026, 7, 13, 9, 0, 0),
            # licenza mancante
        )


def test_memory_contribution_consenso_false_e_validissimo_ma_esplicito() -> None:
    # consenso=False è un valore lecito lato modello: la regola "nessun
    # conferimento senza consenso esplicito" è un vincolo di PERSISTENZA
    # (a carico del servizio urban-memory), non di validazione dello schema.
    # Qui verifichiamo solo che il campo sia obbligatorio, non opzionale-vero.
    contribution = make_memory_contribution(consenso=False)
    assert contribution.consenso is False


# ---------------------------------------------------------------------------
# 8. BehaviorEvent.tipo rifiuta un valore fuori dal Literal
# ---------------------------------------------------------------------------


def test_behavior_event_tipo_rifiuta_valore_fuori_literal() -> None:
    with pytest.raises(ValidationError):
        make_behavior_event(tipo="click")  # non è un obiettivo del sistema


def test_behavior_event_tipo_accetta_valori_canonici() -> None:
    for tipo in ["view", "stop", "photo", "booking", "review", "skip", "memory_contrib"]:
        event = make_behavior_event(tipo=tipo)
        assert event.tipo == tipo


# ---------------------------------------------------------------------------
# 9. Privacy: nessun campo dei contratti si chiama come un identificatore PII
#    (rete di sicurezza minima; il check semantico completo è di ethics-guardian)
# ---------------------------------------------------------------------------

VIETATI = {"nome", "cognome", "email", "telefono", "indirizzo", "codice_fiscale"}


@pytest.mark.parametrize("model_name", CANONICAL_TYPES)
def test_nessun_campo_pii_esplicito(model_name: str) -> None:
    model = getattr(contracts, model_name)
    if not hasattr(model, "model_fields"):
        pytest.skip(f"{model_name} non è un BaseModel (probabilmente un Enum)")
    campi = set(model.model_fields.keys())
    trovati = campi & VIETATI
    assert not trovati, f"{model_name} espone campi PII: {trovati}"


# ---------------------------------------------------------------------------
# 10. Dashboard: soppressione k=10 provata al confine dell'API
#     (DashboardIndexResponse, FlowCell, DashboardFlowsResponse)
# ---------------------------------------------------------------------------


def test_dashboard_index_response_disponibile_richiede_index() -> None:
    with pytest.raises(ValidationError):
        make_dashboard_index_response(disponibile=True, index=None)


def test_dashboard_index_response_disponibile_rifiuta_motivo() -> None:
    with pytest.raises(ValidationError):
        make_dashboard_index_response(
            disponibile=True, motivo_indisponibilita="dato insufficiente"
        )


def test_dashboard_index_response_non_disponibile_richiede_index_none() -> None:
    with pytest.raises(ValidationError):
        make_dashboard_index_response(
            disponibile=False, index=make_index(), motivo_indisponibilita="dato insufficiente"
        )


def test_dashboard_index_response_non_disponibile_richiede_motivo() -> None:
    with pytest.raises(ValidationError):
        make_dashboard_index_response(disponibile=False, index=None, motivo_indisponibilita=None)


def test_dashboard_index_response_disponibile_true_valido() -> None:
    risposta = make_dashboard_index_response()
    assert risposta.disponibile is True
    assert risposta.index is not None
    assert risposta.motivo_indisponibilita is None


def test_dashboard_index_response_disponibile_false_valido() -> None:
    risposta = make_dashboard_index_response(
        disponibile=False,
        index=None,
        motivo_indisponibilita="popolazione sotto la soglia minima di aggregazione (k=10)",
    )
    assert risposta.disponibile is False
    assert risposta.index is None
    assert risposta.motivo_indisponibilita is not None


def test_flow_cell_disponibile_richiede_conteggio_tappe() -> None:
    with pytest.raises(ValidationError):
        make_flow_cell(disponibile=True, conteggio_tappe=None)


def test_flow_cell_non_disponibile_richiede_conteggio_tappe_none() -> None:
    with pytest.raises(ValidationError):
        make_flow_cell(disponibile=False, conteggio_tappe=42)


def test_flow_cell_soppressa_valida() -> None:
    cella = make_flow_cell(disponibile=False, conteggio_tappe=None)
    assert cella.disponibile is False
    assert cella.conteggio_tappe is None


def test_flow_cell_disponibile_valida() -> None:
    cella = make_flow_cell()
    assert cella.disponibile is True
    assert cella.conteggio_tappe == 42


def test_flow_cell_non_espone_mai_conteggio_di_popolazione() -> None:
    # Nessun campo tipo `n_persone`/`persone_coinvolte` deve poter esistere,
    # nemmeno opzionale: la garanzia è strutturale (extra="forbid"), non una
    # disciplina di chi popola il modello. Anche a cella soppressa, un
    # conteggio di popolazione grezzo sarebbe già la violazione di
    # re-identificazione che il gate deve prevenire.
    campi_vietati = {"n_persone", "persone_coinvolte", "person_ids", "contributor_ids"}
    assert campi_vietati.isdisjoint(set(FlowCell.model_fields.keys()))
    with pytest.raises(ValidationError):
        FlowCell(place_id="p", disponibile=False, conteggio_tappe=None, n_persone=3)


def test_dashboard_flows_response_filtri_giorno_ora_opzionali() -> None:
    risposta = make_dashboard_flows_response()
    assert risposta.giorno is None
    assert risposta.ora is None


def test_dashboard_flows_response_accetta_filtro_giorno_e_ora() -> None:
    risposta = make_dashboard_flows_response(giorno=date(2026, 7, 20), ora=15)
    assert risposta.giorno == date(2026, 7, 20)
    assert risposta.ora == 15


def test_dashboard_flows_response_ora_rifiuta_fuori_range() -> None:
    with pytest.raises(ValidationError):
        make_dashboard_flows_response(ora=24)
    with pytest.raises(ValidationError):
        make_dashboard_flows_response(ora=-1)


def test_dashboard_flows_response_celle_e_una_riga_per_luogo() -> None:
    risposta = make_dashboard_flows_response(
        celle=[
            make_flow_cell(place_id="piazza-anfiteatro"),
            make_flow_cell(place_id="mura-urbane", disponibile=False, conteggio_tappe=None),
        ]
    )
    assert [c.place_id for c in risposta.celle] == ["piazza-anfiteatro", "mura-urbane"]


def test_extra_forbid_su_dashboard_index_response() -> None:
    with pytest.raises(ValidationError):
        DashboardIndexResponse(
            periodo="2026-07",
            disponibile=True,
            index=make_index(),
            motivo_indisponibilita=None,
            n_persone_totale=100,  # extra non canonico: fuga di dato grezzo
        )


def test_round_trip_json_dashboard_index_response() -> None:
    original = make_dashboard_index_response()
    dumped = original.model_dump_json()
    restored = DashboardIndexResponse.model_validate_json(dumped)
    assert restored == original


def test_round_trip_json_dashboard_flows_response() -> None:
    original = make_dashboard_flows_response(giorno=date(2026, 7, 20), ora=10)
    dumped = original.model_dump_json()
    restored = DashboardFlowsResponse.model_validate_json(dumped)
    assert restored == original
