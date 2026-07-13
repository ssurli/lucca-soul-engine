"""Test di `graph.source`.

`Neo4jCandidateSource` non è testabile live in questo ambiente (nessuna
istanza Neo4j raggiungibile): resta coperta almeno da un test d'import e da
un controllo statico della query versionata che usa. `SeedCandidateSource` è
invece il percorso principale dei test, perché è quello usato finché
`NEO4J_URI` non è configurato.
"""

from __future__ import annotations

from datetime import time

import pytest
from contracts import EmotionalProfile, GraphCandidate, Signal, VisitorContext
from graph.seed_lucca import ESPERIENZE
from graph.source import CANDIDATES_QUERY_PATH, CandidateSource, SeedCandidateSource


def _ctx(**overrides: object) -> VisitorContext:
    base: dict[str, object] = dict(
        person_id="visitor-pseudo-1",
        profile=EmotionalProfile(
            curiosita=0.7,
            contemplazione=0.3,
            arte=0.5,
            con_bambini=False,
            tempo_disponibile_min=180,
        ),
        signal=Signal(meteo="sereno", affollamento={}, stanchezza=0.1, ora=time(10, 0)),
    )
    base.update(overrides)
    return VisitorContext(**base)  # type: ignore[arg-type]


def test_seed_candidate_source_implementa_il_protocollo() -> None:
    source: CandidateSource = SeedCandidateSource()
    assert hasattr(source, "candidates")


def test_seed_candidate_source_restituisce_tutte_le_esperienze() -> None:
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    assert len(candidati) == len(ESPERIENZE)
    assert all(isinstance(c, GraphCandidate) for c in candidati)


def test_ogni_candidato_ha_almeno_una_connessione() -> None:
    # Ogni esperienza del seed evoca almeno un tema: la connessione minima
    # (`Evoca il tema "..."`) è quindi sempre presente.
    source = SeedCandidateSource()
    for candidato in source.candidates(_ctx()):
        assert len(candidato.connessioni) >= 1


def test_luoghi_gia_visti_non_filtra_i_candidati() -> None:
    # Il grafo propone, non decide: un'esperienza in un luogo già visitato
    # resta tra i candidati (la scelta se scartarla è dell'Experience Engine).
    source = SeedCandidateSource()
    ctx = _ctx(luoghi_gia_visti=["mura-urbane"])
    candidati = source.candidates(ctx)
    assert len(candidati) == len(ESPERIENZE)
    esperienze_su_mura = [c for c in candidati if c.experience.place_id == "mura-urbane"]
    assert len(esperienze_su_mura) > 0


def test_connessione_di_prossimita_quando_ce_un_luogo_gia_visitato() -> None:
    source = SeedCandidateSource()
    ctx = _ctx(luoghi_gia_visti=["mura-urbane"])
    candidati = {c.experience.id: c for c in source.candidates(ctx)}
    # `mura-urbane` è VICINO a `orto-botanico` nel seed (100 m).
    candidato_orto = next(
        c for c in candidati.values() if c.experience.place_id == "orto-botanico"
    )
    assert candidato_orto.distanza_m == 100
    assert any("già visitato" in frase for frase in candidato_orto.connessioni)


def test_connessione_artista_legato_al_luogo() -> None:
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    candidato_puccini = next(c for c in candidati if c.experience.id == "exp-casa-puccini-visita")
    assert any("Puccini" in frase for frase in candidato_puccini.connessioni)


def test_connessione_bottega_che_offre() -> None:
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    candidato_liuteria = next(
        c for c in candidati if c.experience.id == "exp-laboratorio-liuteria"
    )
    assert any("Offerta da" in frase for frase in candidato_liuteria.connessioni)


def test_due_profili_diversi_possono_generare_connessioni_diverse() -> None:
    # Non è compito del grafo scegliere, ma il contesto (luoghi già visti)
    # deve poter produrre candidati con connessioni diverse tra loro: è la
    # base su cui l'Experience Engine costruirà itinerari diversi.
    source = SeedCandidateSource()
    senza_contesto = source.candidates(_ctx())
    con_contesto = source.candidates(_ctx(luoghi_gia_visti=["mura-urbane"]))
    connessioni_senza = {c.experience.id: tuple(c.connessioni) for c in senza_contesto}
    connessioni_con = {c.experience.id: tuple(c.connessioni) for c in con_contesto}
    assert connessioni_senza != connessioni_con


def test_query_candidati_versionata_esiste_ed_e_parametrica() -> None:
    assert CANDIDATES_QUERY_PATH.exists()
    testo = CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")
    for parametro in ("$temi", "$al_chiuso", "$accessibile", "$vicino_a", "$raggio_m"):
        assert parametro in testo


def test_neo4j_candidate_source_importabile() -> None:
    # Non testabile live in questo ambiente (nessun Neo4j raggiungibile):
    # verifichiamo almeno che il modulo importi e che la classe esista con
    # l'interfaccia attesa, driver Neo4j incluso come dipendenza.
    from graph.source import Neo4jCandidateSource

    assert hasattr(Neo4jCandidateSource, "candidates")
    assert hasattr(Neo4jCandidateSource, "from_credentials")


def test_neo4j_candidate_source_non_si_connette_senza_credenziali_valide() -> None:
    from graph.source import Neo4jCandidateSource
    from neo4j.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        # URI palesemente non valido: il driver deve rifiutarlo subito,
        # senza tentare una connessione di rete in questo ambiente isolato.
        Neo4jCandidateSource.from_credentials(
            uri="not-a-valid-uri", username="neo4j", password="x"
        )
