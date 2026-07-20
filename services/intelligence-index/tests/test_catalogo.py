"""Test di `intelligence_index.catalogo.esperienze_per_id` — sul seed
canonico offline (`graph.seed_lucca`), nessun database."""

from __future__ import annotations

from graph.seed_lucca import ESPERIENZE
from graph.source import SeedCandidateSource
from intelligence_index.catalogo import CONTESTO_NEUTRO_CATALOGO, esperienze_per_id


def test_esperienze_per_id_contiene_tutte_le_esperienze_del_seed() -> None:
    catalogo = esperienze_per_id(SeedCandidateSource())
    assert set(catalogo.keys()) == {e.id for e in ESPERIENZE}


def test_esperienze_per_id_espone_place_id_e_durata_min_corretti() -> None:
    catalogo = esperienze_per_id(SeedCandidateSource())
    for esperienza_seed in ESPERIENZE:
        dal_catalogo = catalogo[esperienza_seed.id]
        assert dal_catalogo.place_id == esperienza_seed.place_id
        assert dal_catalogo.durata_min == esperienza_seed.durata_min


def test_contesto_neutro_non_ha_luoghi_gia_visti() -> None:
    # Precondizione della docstring di modulo: nessun filtro deve dipendere
    # da un luogo di riferimento, altrimenti il catalogo non sarebbe "tutte
    # le esperienze del grafo".
    assert CONTESTO_NEUTRO_CATALOGO.luoghi_gia_visti == []


def test_catalogo_deterministico_su_chiamate_ripetute() -> None:
    fonte = SeedCandidateSource()
    primo = esperienze_per_id(fonte)
    secondo = esperienze_per_id(fonte)
    assert primo == secondo
