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
from contracts import EmotionalProfile, ExperienceNode, GraphCandidate, Signal, VisitorContext
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


def test_esperienza_con_partner_ha_attribuzione_valorizzata_e_non_in_connessioni() -> None:
    # Prescrizione ethics-guardian: "Offerta da..." vive in `attribuzione`,
    # MAI in `connessioni` (che alimenta lo score di sorpresa del motore) —
    # un partner non deve comprare punteggio ("visibilità non acquistabile").
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    candidato_liuteria = next(
        c for c in candidati if c.experience.id == "exp-laboratorio-liuteria"
    )
    assert candidato_liuteria.attribuzione is not None
    assert "Offerta da" in candidato_liuteria.attribuzione
    assert not any("Offerta da" in frase for frase in candidato_liuteria.connessioni)


def test_esperienza_senza_partner_ha_attribuzione_none() -> None:
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    candidato_mura = next(c for c in candidati if c.experience.id == "exp-passeggiata-mura")
    assert candidato_mura.experience.partner_id is None
    assert candidato_mura.attribuzione is None


def test_len_connessioni_non_cambia_per_un_partner_senza_relazioni_semantiche_proprie() -> None:
    # L'invariante etica riguarda il fatto COMMERCIALE ("chi offre"), non
    # "avere un partner" in sé: una bottega SENZA relazioni semantiche
    # proprie aggiuntive (qui `ceramica-lucca`, che evoca solo "artigianato",
    # già presente nei temi della gemella) non deve alterare `len(connessioni)`
    # rispetto a una gemella senza partner. Costruiamo due esperienze
    # "gemelle" (stesso luogo, stessi temi) e confrontiamo la lunghezza di
    # `connessioni` prodotta dalla stessa istanza di sorgente.
    source = SeedCandidateSource()
    assert "artigianato" in {
        tema_id for tema_id in source._bottega_evoca.get("ceramica-lucca", [])
    }
    assert "ceramica-lucca" not in source._bottega_ispirata_da

    base = dict(
        place_id="san-michele-in-foro",
        temi=["liuteria", "artigianato", "musica"],
        durata_min=30,
        al_chiuso=True,
        accessibile=True,
    )
    esperienza_con_partner = ExperienceNode(
        id="exp-test-gemella-partner",
        titolo="Gemella con partner",
        partner_id="ceramica-lucca",
        **base,  # type: ignore[arg-type]
    )
    esperienza_senza_partner = ExperienceNode(
        id="exp-test-gemella-no-partner",
        titolo="Gemella senza partner",
        partner_id=None,
        **base,  # type: ignore[arg-type]
    )
    riferimento = None
    luogo_obj = source._luoghi["san-michele-in-foro"]

    connessioni_con_partner = source._connessioni(esperienza_con_partner, luogo_obj, riferimento)
    connessioni_senza_partner = source._connessioni(
        esperienza_senza_partner, luogo_obj, riferimento
    )

    assert len(connessioni_con_partner) == len(connessioni_senza_partner)
    assert not any("Offerta da" in frase for frase in connessioni_con_partner)

    attribuzione_con_partner = source._attribuzione(esperienza_con_partner)
    attribuzione_senza_partner = source._attribuzione(esperienza_senza_partner)
    assert attribuzione_con_partner is not None
    assert attribuzione_senza_partner is None


def test_partner_con_relazioni_semantiche_proprie_arricchisce_connessioni() -> None:
    # Al contrario: una bottega CON relazioni semantiche proprie (qui
    # `liuteria-lucchese`, ISPIRATA_DA Puccini e Boccherini) aggiunge
    # legittimamente connessioni — non è il fatto commerciale a valere
    # punteggio, ma il fatto semantico vero che porta con sé. La frase
    # "Offerta da" resta comunque assente da `connessioni` in ogni caso.
    source = SeedCandidateSource()
    base = dict(
        place_id="san-michele-in-foro",
        temi=["liuteria", "artigianato", "musica"],
        durata_min=30,
        al_chiuso=True,
        accessibile=True,
    )
    esperienza_con_partner_ispirato = ExperienceNode(
        id="exp-test-gemella-partner-ispirato",
        titolo="Gemella con partner ispirato",
        partner_id="liuteria-lucchese",
        **base,  # type: ignore[arg-type]
    )
    esperienza_senza_partner = ExperienceNode(
        id="exp-test-gemella-no-partner-2",
        titolo="Gemella senza partner",
        partner_id=None,
        **base,  # type: ignore[arg-type]
    )
    luogo_obj = source._luoghi["san-michele-in-foro"]

    connessioni_con_partner = source._connessioni(esperienza_con_partner_ispirato, luogo_obj, None)
    connessioni_senza_partner = source._connessioni(esperienza_senza_partner, luogo_obj, None)

    assert len(connessioni_con_partner) > len(connessioni_senza_partner)
    assert not any("Offerta da" in frase for frase in connessioni_con_partner)
    assert any("Puccini" in frase for frase in connessioni_con_partner)


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


def test_query_candidati_include_le_relazioni_semantiche_della_bottega() -> None:
    testo = CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")
    assert "ISPIRATA_DA" in testo
    assert "racconti_ispirazione" in testo
    assert "temi_bottega" in testo


def test_connessione_semantica_bottega_ispirata_da_artista() -> None:
    # Il cammino canonico del White Paper reso esplicito in `connessioni`:
    # la bottega di liuteria porta con sé il legame con Puccini (ISPIRATA_DA)
    # come fatto SEMANTICO, non come attribuzione commerciale.
    source = SeedCandidateSource()
    candidati = source.candidates(_ctx())
    candidato_liuteria = next(
        c for c in candidati if c.experience.id == "exp-laboratorio-liuteria"
    )
    assert any("Puccini compose opere" in frase for frase in candidato_liuteria.connessioni)
    assert any("Boccherini" in frase for frase in candidato_liuteria.connessioni)


def test_prenotabile_solo_sul_laboratorio_di_liuteria() -> None:
    # Gap ethics-guardian (Wave 3a): `prenotabile` è indipendente dalla
    # presenza di un partner (`docs/DATA_CONTRACTS.md` §2) — nel seed
    # canonico è vero SOLO per `exp-laboratorio-liuteria`, nonostante altre
    # esperienze abbiano comunque un partner con abbonamento attivo.
    source = SeedCandidateSource()
    candidati = {c.experience.id: c for c in source.candidates(_ctx())}
    assert candidati["exp-laboratorio-liuteria"].experience.prenotabile is True
    for esperienza_id, candidato in candidati.items():
        if esperienza_id == "exp-laboratorio-liuteria":
            continue
        assert candidato.experience.prenotabile is False


def test_query_candidati_restituisce_prenotabile() -> None:
    # `coalesce(e.prenotabile, false)` (non `e.prenotabile` nudo): un grafo il
    # cui seed non è stato rieseguito con questa proprietà non deve mai far
    # propagare `null` fino a `ExperienceNode.prenotabile` (bool, contratto).
    testo = CANDIDATES_QUERY_PATH.read_text(encoding="utf-8")
    assert "coalesce(e.prenotabile, false) AS prenotabile" in testo


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
