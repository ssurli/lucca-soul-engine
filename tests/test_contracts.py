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

from datetime import datetime, time

import contracts
import pytest
from contracts import (
    BehaviorEvent,
    EmotionalProfile,
    ExperienceCandidate,
    ExperienceNode,
    Itinerary,
    ItineraryStop,
    MemoryContribution,
    MemoryKind,
    PersonKind,
    Signal,
    UrbanIntelligenceIndex,
    VisitorContext,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# 1. I 12 tipi canonici sono importabili da `contracts`
# ---------------------------------------------------------------------------

CANONICAL_TYPES = [
    "EmotionalProfile",
    "Signal",
    "PersonKind",
    "VisitorContext",
    "ExperienceNode",
    "ExperienceCandidate",
    "ItineraryStop",
    "Itinerary",
    "MemoryKind",
    "MemoryContribution",
    "BehaviorEvent",
    "UrbanIntelligenceIndex",
]


def test_dodici_tipi_canonici_importabili() -> None:
    assert len(CANONICAL_TYPES) == 12
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
            {"meteo", "affollamento", "stanchezza", "ora", "eventi_attivi"},
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
            },
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
