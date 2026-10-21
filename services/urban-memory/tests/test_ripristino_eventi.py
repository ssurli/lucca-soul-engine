"""Test del ledger delle promozioni e del ripristino degli `:Evento`:
ordine ledger->grafo, grafo che fallisce dopo il ledger, `:Luogo`
inesistente (nulla scritto), ripristino idempotente, ripristino del freno.
Nessuna connessione reale: repository in-memory, driver Neo4j finto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from urban_memory import ripristina_eventi
from urban_memory.curatela_pattern import (
    ConflittoCestinoError,
    ProiezioneGrafoPendenteError,
    promuovi_pattern,
)
from urban_memory.freno_repository import FrenoStorageError, InMemoryPatternFrenatoRepository
from urban_memory.migrate import SCHEMA_PATHS
from urban_memory.promozione_evento import (
    LuogoMancanteError,
    PromozioneEventoError,
    evento_id_per_pattern,
    scrivi_evento_ripristinato,
)
from urban_memory.promozione_repository import (
    InMemoryPromozioneRepository,
    PromozioneRepository,
)
from urban_memory.ricorrenza import PatternCandidato
from urban_memory.ripristina_eventi import (
    EventoDaRipristinare,
    raggruppa_ledger,
    ripristina,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
CANDIDATO = PatternCandidato(
    place_id="piazza-anfiteatro",
    temi=("arte", "musica"),
    occorrenze=(T0, T0 + timedelta(days=7), T0 + timedelta(days=14)),
    cadenza_giorni=7.0,
    coefficiente_variazione=0.0,
)
EVENTO_ID = evento_id_per_pattern("piazza-anfiteatro", ("arte", "musica"))


def test_schema_promozione_raccolto_dalla_migrazione() -> None:
    # Per nome, non per posizione: dopo il 04 possono aggiungersi altri schemi (05 scarto).
    promozione = [p for p in SCHEMA_PATHS if p.name == "04_promozione_schema.sql"]
    assert promozione
    sql = Path(promozione[0]).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS pattern_promosso" in sql
    codice = " ".join(r for r in sql.splitlines() if not r.lstrip().startswith("--"))
    assert "DROP" not in codice.upper()
    assert "UNIQUE" not in codice.upper()


# ---------------------------------------------------------------------------
# promuovi_pattern: ordine ledger -> grafo
# ---------------------------------------------------------------------------


def test_ordine_luogo_poi_ledger_poi_grafo() -> None:
    eventi: list[str] = []
    repo = InMemoryPromozioneRepository()

    def luogo_esiste(place_id: str) -> bool:
        eventi.append("luogo")
        return True

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, quando: datetime) -> str:
        # Al momento della scrittura sul grafo il ledger ha GIA' la riga.
        eventi.append(f"grafo(ledger={len(repo.elenca())})")
        return evento_id_per_pattern(p, t)

    promosso_il = T0
    evento_id = promuovi_pattern(
        CANDIDATO,
        promotore="promotore-1",
        writer=writer,
        repo=repo,
        e_cestinato=lambda _p, _t: False,
        luogo_esiste=luogo_esiste,
        promosso_il=promosso_il,
    )

    assert eventi == ["luogo", "grafo(ledger=1)"]
    [riga] = repo.elenca()
    assert riga.evento_id == evento_id == EVENTO_ID
    assert riga.temi == ("arte", "musica")
    assert riga.promotore == "promotore-1"
    assert riga.promosso_il == promosso_il


def test_grafo_che_fallisce_dopo_il_ledger_lascia_la_promozione_registrata() -> None:
    repo = InMemoryPromozioneRepository()

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, quando: datetime) -> str:
        raise PromozioneEventoError("Aura in pausa")

    with pytest.raises(ProiezioneGrafoPendenteError) as info:
        promuovi_pattern(
            CANDIDATO,
            promotore="promotore-1",
            writer=writer,
            repo=repo,
            e_cestinato=lambda _p, _t: False,
            luogo_esiste=lambda _p: True,
        )

    assert repo.registrata(EVENTO_ID)
    assert info.value.evento_id == EVENTO_ID
    assert "ripristina_eventi" in str(info.value)
    assert "REGISTRATA" in str(info.value)


def test_luogo_inesistente_non_scrive_nulla() -> None:
    repo = InMemoryPromozioneRepository()

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, quando: datetime) -> str:
        raise AssertionError("il grafo non deve essere toccato")

    with pytest.raises(LuogoMancanteError):
        promuovi_pattern(
            CANDIDATO,
            promotore="promotore-1",
            writer=writer,
            repo=repo,
            e_cestinato=lambda _p, _t: False,
            luogo_esiste=lambda _p: False,
        )

    assert repo.elenca() == []


def test_grafo_irraggiungibile_alla_verifica_del_luogo_non_scrive_nulla() -> None:
    repo = InMemoryPromozioneRepository()

    def luogo_esiste(_p: str) -> bool:
        raise PromozioneEventoError("grafo irraggiungibile")

    with pytest.raises(PromozioneEventoError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=lambda *a: "x",
            repo=repo,
            e_cestinato=lambda _p, _t: False,
            luogo_esiste=luogo_esiste,
        )
    assert repo.elenca() == []


def test_ledger_che_fallisce_non_tocca_il_grafo() -> None:
    class RepoRotto(InMemoryPromozioneRepository):
        def registra(self, **kwargs: Any):  # type: ignore[override]
            raise RuntimeError("postgres giu'")

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, quando: datetime) -> str:
        raise AssertionError("il grafo non deve essere toccato se il ledger fallisce")

    with pytest.raises(RuntimeError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=writer,
            repo=RepoRotto(),
            e_cestinato=lambda _p, _t: False,
            luogo_esiste=lambda _p: True,
        )


def test_ledger_append_only_ripromozione_e_una_riga_nuova() -> None:
    repo = InMemoryPromozioneRepository()
    for _ in range(2):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=lambda p, t, c, pr, q: evento_id_per_pattern(p, t),
            repo=repo,
            e_cestinato=lambda _p, _t: False,
            luogo_esiste=lambda _p: True,
        )
    assert len(repo.elenca()) == 2


# ---------------------------------------------------------------------------
# Ripristino
# ---------------------------------------------------------------------------


class GrafoFinto:
    """Grafo finto: Luoghi noti, :Evento come dizionario (MERGE idempotente).
    Il freno e' scritto COL nodo (come la query 51)."""

    def __init__(self, luoghi: set[str], irraggiungibile_dopo: int | None = None) -> None:
        self.luoghi = luoghi
        self.eventi: dict[str, dict[str, Any]] = {}
        self.irraggiungibile_dopo = irraggiungibile_dopo  # n. proiezioni riuscite prima del crollo
        self.chiamate_proietta = 0

    def proietta(self, e: EventoDaRipristinare) -> str:
        self.chiamate_proietta += 1
        if self.irraggiungibile_dopo is not None and len(self.eventi) >= self.irraggiungibile_dopo:
            raise PromozioneEventoError("grafo irraggiungibile")
        if e.place_id not in self.luoghi:
            raise LuogoMancanteError(e.place_id)
        self.eventi[e.evento_id] = {
            "temi": e.temi,
            "cadenza": e.cadenza_giorni,
            "promosso_da": e.promotore,
            "promosso_il": e.promosso_il,
            "ricalcolo_da": e.ultimo_ricalcolo_da,
            "ricalcolo_il": e.ultimo_ricalcolo_il,
            "frenato": e.frenato,
        }
        return e.evento_id


def _ledger_con_due_pattern() -> InMemoryPromozioneRepository:
    repo = InMemoryPromozioneRepository()
    repo.registra(
        evento_id="evento-a",
        place_id="luogo-a",
        temi=["arte"],
        cadenza_giorni=7.0,
        promotore="primo",
        promosso_il=T0,
    )
    repo.registra(
        evento_id="evento-b",
        place_id="luogo-b",
        temi=["storia"],
        cadenza_giorni=14.0,
        promotore="secondo",
        promosso_il=T0 + timedelta(days=1),
    )
    return repo


def test_raggruppa_prima_riga_per_origine_ultima_per_cadenza_e_ricalcolo() -> None:
    repo = InMemoryPromozioneRepository()
    kw: dict[str, Any] = {"evento_id": "e", "place_id": "l", "temi": ["x"]}
    repo.registra(**kw, cadenza_giorni=7.0, promotore="primo", promosso_il=T0)
    repo.registra(**kw, cadenza_giorni=10.0, promotore="rico", promosso_il=T0 + timedelta(days=30))

    [e] = raggruppa_ledger(repo.elenca())

    assert (e.promotore, e.promosso_il) == ("primo", T0)
    assert e.cadenza_giorni == 10.0
    assert (e.ultimo_ricalcolo_da, e.ultimo_ricalcolo_il) == ("rico", T0 + timedelta(days=30))


def test_raggruppa_una_sola_riga_nessun_ricalcolo() -> None:
    [e1, _e2] = raggruppa_ledger(_ledger_con_due_pattern().elenca())
    assert e1.ultimo_ricalcolo_da is None and e1.ultimo_ricalcolo_il is None


def test_ripristino_idempotente() -> None:
    promozioni = _ledger_con_due_pattern()
    freno = InMemoryPatternFrenatoRepository()
    grafo = GrafoFinto({"luogo-a", "luogo-b"})

    def esegui() -> ripristina_eventi.RapportoRipristino:
        return ripristina(
            promozioni, freno, proietta=grafo.proietta, e_cestinato=lambda _p, _t: False
        )

    r1 = esegui()
    stato_dopo_1 = {k: dict(v) for k, v in grafo.eventi.items()}
    r2 = esegui()

    assert r1.ok and r2.ok
    assert sorted(r1.proiettati) == ["evento-a", "evento-b"]
    assert grafo.eventi == stato_dopo_1  # stesso stato, nessun duplicato
    assert len(grafo.eventi) == 2


def test_ripristino_luogo_mancante_elencato_e_non_ok() -> None:
    grafo = GrafoFinto({"luogo-a"})
    r = ripristina(
        _ledger_con_due_pattern(),
        InMemoryPatternFrenatoRepository(),
        proietta=grafo.proietta,
        e_cestinato=lambda _p, _t: False,
    )
    assert r.proiettati == ["evento-a"]
    assert r.luogo_mancante == [("evento-b", "luogo-b")]
    assert not r.ok
    assert ripristina_eventi._stampa_rapporto(r) == 1


def test_ripristino_grafo_irraggiungibile_si_ferma() -> None:
    grafo = GrafoFinto(set(), irraggiungibile_dopo=0)
    r = ripristina(
        _ledger_con_due_pattern(),
        InMemoryPatternFrenatoRepository(),
        proietta=grafo.proietta,
        e_cestinato=lambda _p, _t: False,
    )
    assert grafo.chiamate_proietta == 1
    assert r.non_tentati == 1
    assert r.grafo_irraggiungibile is not None and not r.ok


def _freno_con_a_rilasciato_b_tirato() -> InMemoryPatternFrenatoRepository:
    freno = InMemoryPatternFrenatoRepository()
    kw: dict[str, Any] = {"place_id": None, "temi": [], "attore": "a"}
    freno.registra(evento_id="evento-a", azione="tirato", motivazione="m", quando=T0, **kw)
    freno.registra(
        evento_id="evento-a",
        azione="rilasciato",
        motivazione=None,
        quando=T0 + timedelta(days=1),
        **kw,
    )
    freno.registra(evento_id="evento-b", azione="tirato", motivazione="m", quando=T0, **kw)
    freno.registra(evento_id="evento-orfano", azione="tirato", motivazione="m", quando=T0, **kw)
    return freno


def test_ripristino_del_freno_e_scritto_col_nodo_dall_ultima_azione() -> None:
    grafo = GrafoFinto({"luogo-a", "luogo-b"})

    r = ripristina(
        _ledger_con_due_pattern(),
        _freno_con_a_rilasciato_b_tirato(),
        proietta=grafo.proietta,
        e_cestinato=lambda _p, _t: False,
    )

    assert {k: v["frenato"] for k, v in grafo.eventi.items()} == {
        "evento-a": False,
        "evento-b": True,
    }
    assert r.frenati == ["evento-b"]
    assert r.freno_senza_evento == ["evento-orfano"]
    assert r.ok  # un freno orfano e' un avviso, non un fallimento


def test_grafo_irraggiungibile_a_meta_nessun_evento_frenato_risulta_attivo_e_non_frenato() -> None:
    """Dopo il crollo a meta', ogni :Evento presente nel grafo e' nato COL suo
    freno; quelli non proiettati non esistono (non raccomandabili)."""
    grafo = GrafoFinto({"luogo-a", "luogo-b"}, irraggiungibile_dopo=1)

    r = ripristina(
        _ledger_con_due_pattern(),
        _freno_con_a_rilasciato_b_tirato(),
        proietta=grafo.proietta,
        e_cestinato=lambda _p, _t: False,
    )

    assert r.grafo_irraggiungibile is not None and not r.ok
    assert list(grafo.eventi) == ["evento-a"]
    assert grafo.eventi["evento-a"]["frenato"] is False  # a: ultima azione = rilasciato
    assert "evento-b" not in grafo.eventi  # b (frenato) non esiste: non raccomandabile


def test_lettura_freno_fallita_nulla_proiettato() -> None:
    class FrenoRotto(InMemoryPatternFrenatoRepository):
        def ultime_azioni(self):  # type: ignore[override]
            raise FrenoStorageError("postgres giu'")

    grafo = GrafoFinto({"luogo-a", "luogo-b"})
    with pytest.raises(FrenoStorageError):
        ripristina(
            _ledger_con_due_pattern(),
            FrenoRotto(),
            proietta=grafo.proietta,
            e_cestinato=lambda _p, _t: False,
        )
    assert grafo.chiamate_proietta == 0


def test_ripristino_conflitto_cestino_non_proietta_ed_e_exit_1() -> None:
    grafo = GrafoFinto({"luogo-a", "luogo-b"})
    r = ripristina(
        _ledger_con_due_pattern(),
        InMemoryPatternFrenatoRepository(),
        proietta=grafo.proietta,
        e_cestinato=lambda place_id, _t: place_id == "luogo-b",
    )
    assert r.conflitto_cestino == ["evento-b"]
    assert list(grafo.eventi) == ["evento-a"]
    assert not r.ok
    assert ripristina_eventi._stampa_rapporto(r) == 1


def test_promuovi_pattern_nel_cestino_solleva_e_non_scrive_nulla() -> None:
    repo = InMemoryPromozioneRepository()

    def writer(*args: object) -> str:
        raise AssertionError("il grafo non deve essere toccato")

    def luogo_esiste(_p: str) -> bool:
        raise AssertionError("nemmeno la lettura del grafo serve")

    with pytest.raises(ConflittoCestinoError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=writer,
            repo=repo,
            luogo_esiste=luogo_esiste,
            e_cestinato=lambda _p, _t: True,
        )
    assert repo.elenca() == []


def test_rapporto_non_stampa_pii_e_indica_il_passo_successivo(capsys) -> None:
    grafo = GrafoFinto({"luogo-a", "luogo-b"})
    r = ripristina(
        _ledger_con_due_pattern(),
        InMemoryPatternFrenatoRepository(),
        proietta=grafo.proietta,
        e_cestinato=lambda _p, _t: False,
    )
    assert ripristina_eventi._stampa_rapporto(r) == 0
    out = capsys.readouterr().out
    assert "frizione_pattern" in out
    assert "primo" not in out and "secondo" not in out  # promotore mai stampato


# ---------------------------------------------------------------------------
# Query Cypher 51 con driver finto
# ---------------------------------------------------------------------------


class _Res:
    def __init__(self, v: Any) -> None:
        self._v = v

    def single(self) -> Any:
        return self._v


class _Sess:
    def __init__(self, drv: _Drv) -> None:
        self.drv = drv

    def run(self, q: str, p: dict[str, Any] | None = None) -> _Res:
        self.drv.eseguite.append((q, p or {}))
        return _Res(self.drv.risposta)

    def __enter__(self) -> _Sess:
        return self

    def __exit__(self, *a: object) -> None:
        return None


class _Drv:
    def __init__(self, risposta: Any) -> None:
        self.risposta = risposta
        self.eseguite: list[tuple[str, dict[str, Any]]] = []

    def session(self, database: str | None = None) -> _Sess:
        return _Sess(self)

    def close(self) -> None:
        return None


def test_cypher_ripristino_usa_match_sul_luogo_e_non_tocca_stato_in_match() -> None:
    drv = _Drv({"evento_id": "e"})
    scrivi_evento_ripristinato("l", "e", ["x"], 7.0, "p", T0, None, None, False, driver=drv)
    [(query, params)] = drv.eseguite
    assert "MATCH (l:Luogo" in query and "MERGE (l:Luogo" not in query
    assert "ON CREATE SET\n    e.stato" in query
    codice = " ".join(r for r in query.splitlines() if not r.startswith("//"))
    assert codice.count("e.stato") == 1  # solo ON CREATE: mai riscritto su nodo esistente
    assert params["ultimo_ricalcolo_da"] is None
    assert params["promosso_il"] == T0.isoformat()
    assert params["frenato"] is False
    assert (
        "e.stato = 'sospeso'" in query
    )  # fail-safe: non raccomandabile finche' la frizione non decide
    # freno atomico col nodo, mai rilasciato dal ripristino
    assert "e.frenato = ($frenato OR coalesce(e.frenato, false))" in query
    assert "coalesce(e.promosso_da, $promotore)" in query
    assert "coalesce(e.promosso_il, $promosso_il)" in query


def test_cypher_ripristino_luogo_mancante() -> None:
    with pytest.raises(LuogoMancanteError):
        scrivi_evento_ripristinato(
            "l", "e", ["x"], 7.0, "p", T0, None, None, False, driver=_Drv(None)
        )


def test_ledger_repository_rispetta_il_protocol() -> None:
    repo: PromozioneRepository = InMemoryPromozioneRepository()
    assert repo.elenca() == []
