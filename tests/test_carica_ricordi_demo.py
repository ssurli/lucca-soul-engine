"""Test di `scripts/carica_ricordi_demo.py` — repository in memoria e target_checker
finto: nessuna rete, nessun Neon/Aura."""

from __future__ import annotations

import importlib.util
import inspect
import io
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from contracts import MemoryContribution, MemoryKind, MemoryLinkState, PersonKind
from intelligence_index import soglia as soglia_mod
from urban_memory.repository import InMemoryMemoryRepository

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "carica_ricordi_demo.py"


def _carica() -> ModuleType:
    spec = importlib.util.spec_from_file_location("carica_ricordi_demo", _PATH)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _carica()
ID_DEMO = [r[0] for r in script.RICORDI_DEMO]


def _persona(contributor: str, n: int, *, curato: bool = True) -> MemoryContribution:
    return MemoryContribution(
        id=f"mem-{contributor}-{n}",
        kind=MemoryKind.RACCONTO,
        testo="x",
        riguarda=["mura-urbane"],
        contributor_id=contributor,
        contributor_kind=PersonKind.CITTADINO,
        consenso=True,
        licenza="CC-BY-SA-4.0",
        creato_il=datetime.now(UTC),
        curato=curato,
    )


def _repo_con(persone: int) -> InMemoryMemoryRepository:
    repo = InMemoryMemoryRepository()
    for i in range(persone):
        repo.submit(_persona(f"p{i}", i))
    return repo


def _tutto_presente(ids: list[str]) -> list[str]:
    return []


def _esegui(
    repo: InMemoryMemoryRepository,
    *,
    esegui: bool,
    checker=_tutto_presente,  # noqa: ANN001
    linker=None,  # noqa: ANN001
) -> tuple[int, str]:
    out = io.StringIO()
    codice = script.esegui_caricamento(repo, checker, linker, esegui=esegui, out=out)
    return codice, out.getvalue()


def _tutti(repo: InMemoryMemoryRepository) -> dict[str, MemoryContribution]:
    return {c.id: c for c in repo.list_pending() + repo.list_curated()}


def test_prova_a_secco_non_scrive() -> None:
    repo = _repo_con(2)
    codice, out = _esegui(repo, esegui=False)
    assert codice == 0
    assert set(_tutti(repo)) == {"mem-p0-0", "mem-p1-1"}
    assert "sottometterebbe e curerebbe" in out


def test_esegui_scrive_4_e_cura() -> None:
    repo = _repo_con(2)
    collegati: list[str] = []
    codice, _ = _esegui(repo, esegui=True, linker=lambda c: collegati.append(c.id))
    assert codice == 0
    tutti = _tutti(repo)
    for memory_id in ID_DEMO:
        c = tutti[memory_id]
        assert c.curato is True
        assert c.consenso is True
        assert c.contributor_id == "demo-lucca-soul"
        assert c.contributor_kind == PersonKind.CITTADINO
        assert c.licenza == "CC-BY-SA-4.0"
        assert c.stato_aggancio == MemoryLinkState.AGGANCIATO
    assert collegati == ID_DEMO


def test_idempotenza_seconda_esecuzione_non_scrive() -> None:
    repo = _repo_con(2)
    _esegui(repo, esegui=True, linker=lambda c: None)  # curati E agganciati
    prima = _tutti(repo)
    chiamate: list[str] = []
    codice, out = _esegui(repo, esegui=True, linker=lambda c: chiamate.append(c.id))
    assert codice == 0
    assert _tutti(repo) == prima
    assert chiamate == []
    assert out.count("gia' curato") == 4


def test_presente_ma_non_curato_viene_curato_senza_duplicare() -> None:
    repo = _repo_con(2)
    id0, riguarda0, testo0 = script.RICORDI_DEMO[0]
    repo.submit(script._costruisci(id0, riguarda0, testo0))
    codice, _ = _esegui(repo, esegui=True)
    assert codice == 0
    tutti = _tutti(repo)
    assert len(tutti) == 2 + 4
    assert all(tutti[i].curato for i in ID_DEMO)


def test_soglia_sei_persone_piu_demo_uguale_sette_blocca() -> None:
    repo = _repo_con(6)
    codice, out = _esegui(repo, esegui=True)
    assert codice == 1
    assert "Nessuna scrittura" in out
    assert len(_tutti(repo)) == 6


def test_soglia_cinque_persone_piu_demo_uguale_sei_ok() -> None:
    repo = _repo_con(5)
    codice, _ = _esegui(repo, esegui=True)
    assert codice == 0
    assert len(_tutti(repo)) == 5 + 4


def test_demo_gia_presente_non_conta_doppio() -> None:
    # 5 altre persone + demo gia' presente = 6 (non 7): deve passare.
    repo = _repo_con(5)
    id0, riguarda0, testo0 = script.RICORDI_DEMO[0]
    repo.submit(script._costruisci(id0, riguarda0, testo0))
    codice, out = _esegui(repo, esegui=False)
    assert codice == 0
    assert "Persone distinte (demo inclusa): 6" in out


def test_soglia_usa_la_costante_di_intelligence_index() -> None:
    from intelligence_index.soglia import SOGLIA_MINIMA_PERSONE

    assert SOGLIA_MINIMA_PERSONE - 3 == 7


def test_soglia_bloccata_anche_a_secco() -> None:
    codice, _ = _esegui(_repo_con(6), esegui=False)
    assert codice == 1


def test_target_mancante_exit_1_nessuna_scrittura_ne_curatela() -> None:
    repo = _repo_con(2)

    def checker(ids: list[str]) -> list[str]:
        return [i for i in ids if i == "chiesa-san-francesco"]

    chiamate: list[str] = []
    codice, out = _esegui(repo, esegui=True, checker=checker, linker=chiamate.append)  # type: ignore[arg-type]
    assert codice == 1
    assert "Ricarica prima il seed" in out
    assert "chiesa-san-francesco" in out
    assert len(_tutti(repo)) == 2
    assert chiamate == []
    assert repo.list_curated() == [c for c in repo.list_curated() if c.id.startswith("mem-p")]


def test_testi_esatti_e_suffisso() -> None:
    assert len(script.RICORDI_DEMO) == 4
    for _, _, testo in script.RICORDI_DEMO:
        assert testo.endswith("(esempio dimostrativo)")
    assert script.RICORDI_DEMO[0][2].startswith("Le Mura non sono sempre state un giardino.")
    assert [r[1] for r in script.RICORDI_DEMO] == [
        "mura-urbane",
        "piazza-anfiteatro",
        "duomo-san-martino",
        "chiesa-san-francesco",
    ]


def test_main_con_dsn_irraggiungibili_esce_1_senza_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:1")
    monkeypatch.setenv("NEO4J_USERNAME", "x")
    monkeypatch.setenv("NEO4J_PASSWORD", "x")
    # connect_timeout=1: lo script lo rispetta se presente (default 10 s) -> test rapido.
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x?connect_timeout=1")
    assert script.main([]) == 1
    out = capsys.readouterr().out
    assert "ERRORE" in out
    assert "Traceback" not in out


# --------------------------------------------------------------------------
# Gate separato: proprieta' aggiuntive (ognuna verificata con mutazione).
# --------------------------------------------------------------------------

TESTI_ATTESI = (
    (
        "memoria-demo-mura-urbane",
        "mura-urbane",
        "Le Mura non sono sempre state un giardino. Fu Maria Luisa di Borbone, duchessa di "
        "Lucca dal 1817 al 1824, a trasformarle in passeggiata pubblica. Il progetto è di "
        "Lorenzo Nottolini: un viale centrale per le carrozze, due laterali per chi va a "
        "piedi. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-piazza-anfiteatro",
        "piazza-anfiteatro",
        "Circa tre metri sotto i tuoi piedi c'è ancora la base dell'anfiteatro romano del II "
        "secolo. Le case ne hanno conservato la forma ellittica; la piazza vuota al centro la "
        "aprì Nottolini nel 1830, demolendo gli edifici interni. Si entra da quattro porte, "
        "una per vertice. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-duomo-san-martino",
        "duomo-san-martino",
        "Ogni 13 settembre migliaia di lumini accendono il centro per la Luminara di Santa "
        "Croce. La processione parte da San Frediano, dove, secondo la tradizione, il Volto "
        "Santo fu collocato per primo, attraversa via Fillungo e piazza San Michele e arriva "
        "qui, davanti al Duomo che oggi lo custodisce. (esempio dimostrativo)",
    ),
    (
        "memoria-demo-chiesa-san-francesco",
        "chiesa-san-francesco",
        "Qui c'è il monumento di Ugolino Visconti, detto Nino, giudice di Gallura, che Dante "
        "incontra nel Purgatorio. Nella stessa chiesa riposano due musicisti lucchesi, Luigi "
        "Boccherini e Francesco Geminiani. (esempio dimostrativo)",
    ),
)


class _Spia:
    """Registra le chiamate di scrittura: devono essere zero a secco."""

    def __init__(self) -> None:
        self.chiamate: list[str] = []

    def submit(self, *a: object, **k: object) -> None:
        self.chiamate.append("submit")
        raise AssertionError("submit chiamato")

    def curate(self, *a: object, **k: object) -> None:
        self.chiamate.append("curate")
        raise AssertionError("curate chiamato")


def _spia(monkeypatch: pytest.MonkeyPatch) -> _Spia:
    spia = _Spia()
    monkeypatch.setattr(script, "submit_contribution", spia.submit)
    monkeypatch.setattr(script, "curate_contribution", spia.curate)
    return spia


def test_a_secco_mai_submit_curate_link_nemmeno_con_ricordo_presente_non_curato(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo_con(2)
    id0, r0, t0 = script.RICORDI_DEMO[0]
    repo.submit(script._costruisci(id0, r0, t0))  # presente non curato: caso "curerebbe"
    spia = _spia(monkeypatch)
    collegati: list[str] = []
    codice, out = _esegui(repo, esegui=False, linker=lambda c: collegati.append(c.id))
    assert codice == 0
    assert spia.chiamate == []
    assert collegati == []
    assert "curerebbe" in out
    assert len(_tutti(repo)) == 2 + 1
    assert not _tutti(repo)[id0].curato


def test_esegui_chiama_submit_e_curate(monkeypatch: pytest.MonkeyPatch) -> None:
    # Controprova della spia: con esegui=True la scrittura passa da submit.
    spia = _spia(monkeypatch)
    with pytest.raises(AssertionError):
        _esegui(_repo_con(1), esegui=True)
    assert spia.chiamate == ["submit"]


@pytest.mark.parametrize("n_altre", [0, 5])
def test_a_secco_soglia_5_piu_demo_passa(n_altre: int) -> None:
    codice, out = _esegui(_repo_con(n_altre), esegui=False)
    assert codice == 0
    assert f"Persone distinte (demo inclusa): {n_altre + 1}" in out


def test_soglia_blocca_senza_scritture_ne_chiamate(monkeypatch: pytest.MonkeyPatch) -> None:
    spia = _spia(monkeypatch)
    chiamate_checker: list[list[str]] = []

    def checker(ids: list[str]) -> list[str]:
        chiamate_checker.append(ids)
        return []

    for esegui in (False, True):
        codice, out = _esegui(_repo_con(6), esegui=esegui, checker=checker)
        assert codice == 1
        assert ">= 7" in out
    assert spia.chiamate == []
    assert chiamate_checker == []  # la soglia viene prima del controllo target


def test_soglia_oltre_il_confine_blocca() -> None:
    codice, _ = _esegui(_repo_con(9), esegui=True)
    assert codice == 1


def test_stesso_contributor_con_piu_ricordi_conta_una_persona() -> None:
    repo = InMemoryMemoryRepository()
    for i in range(20):  # 20 ricordi, 1 sola persona
        repo.submit(_persona("unica", i))
    codice, out = _esegui(repo, esegui=False)
    assert codice == 0
    assert "Persone distinte (demo inclusa): 2" in out


def test_soglia_conta_sia_i_non_curati_sia_i_curati() -> None:
    repo = InMemoryMemoryRepository()
    for i in range(3):
        repo.submit(_persona(f"c{i}", i, curato=False))
    for i in range(3):
        repo.curate(repo.submit(_persona(f"d{i}", i, curato=False)).id)
    codice, _ = _esegui(repo, esegui=False)
    assert codice == 1  # 6 + demo = 7


def test_demo_gia_presente_con_sei_altre_blocca_comunque() -> None:
    repo = _repo_con(6)
    id0, r0, t0 = script.RICORDI_DEMO[0]
    repo.submit(script._costruisci(id0, r0, t0))
    codice, out = _esegui(repo, esegui=False)
    assert codice == 1
    assert "Persone distinte (demo inclusa): 7" in out


def test_soglia_default_e_quella_importata_da_intelligence_index() -> None:
    assert script.SOGLIA_MINIMA_PERSONE is soglia_mod.SOGLIA_MINIMA_PERSONE
    default = inspect.signature(script.esegui_caricamento).parameters["soglia_minima"].default
    assert default == soglia_mod.SOGLIA_MINIMA_PERSONE


@pytest.mark.parametrize("k", [5, 10, 20])
def test_limite_segue_il_parametro_k_meno_3(k: int) -> None:
    # limite = k-3: (k-4) altre + demo = k-3 -> blocca; (k-5) altre + demo -> passa.
    blocca = script.esegui_caricamento(
        _repo_con(k - 4), _tutto_presente, None, esegui=False, soglia_minima=k, out=io.StringIO()
    )
    passa = script.esegui_caricamento(
        _repo_con(k - 5), _tutto_presente, None, esegui=False, soglia_minima=k, out=io.StringIO()
    )
    assert (blocca, passa) == (1, 0)


def test_target_mancante_blocca_prima_di_qualunque_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spia = _spia(monkeypatch)
    for esegui in (False, True):
        codice, out = _esegui(
            _repo_con(2), esegui=esegui, checker=lambda ids: ["duomo-san-martino"]
        )
        assert codice == 1
        assert "duomo-san-martino" in out
    assert spia.chiamate == []


def test_il_checker_riceve_i_4_target_ordinati() -> None:
    viste: list[list[str]] = []

    def checker(ids: list[str]) -> list[str]:
        viste.append(ids)
        return []

    _esegui(_repo_con(1), esegui=False, checker=checker)
    assert viste == [
        ["chiesa-san-francesco", "duomo-san-martino", "mura-urbane", "piazza-anfiteatro"]
    ]


def test_curatela_usa_il_target_checker_reale_non_none(monkeypatch: pytest.MonkeyPatch) -> None:
    visti: list[object] = []
    reale = script.curate_contribution

    def spia(repo, memory_id, *, target_checker=None, linker=None):  # noqa: ANN001, ANN202
        visti.append(target_checker)
        return reale(repo, memory_id, target_checker=target_checker, linker=linker)

    monkeypatch.setattr(script, "curate_contribution", spia)
    _esegui(_repo_con(1), esegui=True, checker=_tutto_presente)
    assert visti == [_tutto_presente] * 4


def test_ids_testi_e_riguarda_esatti() -> None:
    assert script.RICORDI_DEMO == TESTI_ATTESI
    assert len({r[0] for r in script.RICORDI_DEMO}) == 4
    for _, _, testo in script.RICORDI_DEMO:
        assert testo.endswith(" (esempio dimostrativo)")


def test_ricordi_scritti_hanno_campi_esatti() -> None:
    repo = _repo_con(1)
    _esegui(repo, esegui=True)
    tutti = _tutti(repo)
    for memory_id, riguarda, testo in TESTI_ATTESI:
        c = tutti[memory_id]
        assert c.testo == testo
        assert c.riguarda == [riguarda]
        assert c.kind == MemoryKind.RACCONTO
        assert c.consenso is True
        assert c.contributor_kind == PersonKind.CITTADINO
        assert c.contributor_id == script.CONTRIBUTOR_DEMO == "demo-lucca-soul"
        assert c.licenza.strip() != ""
        assert c.curato is True


def test_idempotenza_tre_esecuzioni_nessun_duplicato() -> None:
    repo = _repo_con(2)
    for _ in range(3):
        assert _esegui(repo, esegui=True)[0] == 0
    ids = [c.id for c in repo.list_pending() + repo.list_curated()]
    assert len(ids) == len(set(ids)) == 2 + 4


def test_gia_curato_non_richiama_submit_ne_curate(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo_con(2)
    _esegui(repo, esegui=True)
    spia = _spia(monkeypatch)
    codice, _ = _esegui(repo, esegui=True)
    assert codice == 0
    assert spia.chiamate == []


def test_ripresa_dopo_caduta_di_neo4j_a_meta_completa_senza_duplicati() -> None:
    # Neo4j cade durante la curatela (3a chiamata del checker): l'eccezione risale
    # (main la trasforma in exit 1); una nuova esecuzione completa senza duplicare.
    from neo4j.exceptions import ServiceUnavailable

    stato = {"n": 0}

    def checker(ids: list[str]) -> list[str]:
        stato["n"] += 1
        if stato["n"] == 3:
            raise ServiceUnavailable("giu")
        return []

    repo = _repo_con(1)
    with pytest.raises(ServiceUnavailable):
        _esegui(repo, esegui=True, checker=checker)
    codice, _ = _esegui(repo, esegui=True)
    assert codice == 0
    tutti = _tutti(repo)
    assert len(tutti) == 1 + 4
    assert all(tutti[i].curato for i in ID_DEMO)


def test_linker_che_fallisce_lascia_curato_con_aggancio_fallito() -> None:
    # TEST ESISTENTE MODIFICATO: prima asseriva exit 0. Requisito cambiato su
    # richiesta dell'ethics gate (B1): curato ma non agganciato e' lo stato che
    # l'invariante 11-B vuole impedire, quindi lo script deve uscire con 1.
    from urban_memory.graph_link import MemoryLinkError

    def linker(c: MemoryContribution) -> None:
        raise MemoryLinkError("giu")

    repo = _repo_con(1)
    codice, out = _esegui(repo, esegui=True, linker=linker)
    assert codice == 1
    tutti = _tutti(repo)
    assert all(tutti[i].curato for i in ID_DEMO)
    assert all(tutti[i].stato_aggancio == MemoryLinkState.AGGANCIO_FALLITO for i in ID_DEMO)
    assert "rilancia lo script" in out


def test_rilancio_con_linker_funzionante_ritenta_solo_l_aggancio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from urban_memory.graph_link import MemoryLinkError

    def rotto(c: MemoryContribution) -> None:
        raise MemoryLinkError("giu")

    repo = _repo_con(1)
    assert _esegui(repo, esegui=True, linker=rotto)[0] == 1
    spia = _spia(monkeypatch)
    agganciati: list[str] = []
    codice, _ = _esegui(repo, esegui=True, linker=lambda c: agganciati.append(c.id))
    assert codice == 0
    assert spia.chiamate == []  # nessun submit/curate
    assert agganciati == ID_DEMO
    tutti = _tutti(repo)
    assert all(tutti[i].stato_aggancio == MemoryLinkState.AGGANCIATO for i in ID_DEMO)
    assert len(tutti) == 1 + 4


def test_curato_con_stato_none_viene_ritentato() -> None:
    repo = _repo_con(1)
    _esegui(repo, esegui=True)  # senza linker: curati con stato None
    assert all(c.stato_aggancio is None for c in _tutti(repo).values() if c.id in ID_DEMO)
    agganciati: list[str] = []
    codice, _ = _esegui(repo, esegui=True, linker=lambda c: agganciati.append(c.id))
    assert codice == 0
    assert agganciati == ID_DEMO


def test_a_secco_curato_non_agganciato_non_scrive() -> None:
    repo = _repo_con(1)
    _esegui(repo, esegui=True)
    chiamate: list[str] = []
    codice, out = _esegui(repo, esegui=False, linker=lambda c: chiamate.append(c.id))
    assert codice == 0
    assert chiamate == []
    assert out.count("curato ma non agganciato: verrebbe ritentato l'aggancio") == 4
    assert all(c.stato_aggancio is None for c in _tutti(repo).values() if c.id in ID_DEMO)


def test_soglia_non_controllata_se_nessun_submit_da_fare() -> None:
    # N4: tutti e 4 presenti e agganciati, 8 persone distinte: nulla da scrivere.
    repo = _repo_con(2)
    _esegui(repo, esegui=True, linker=lambda c: None)
    for i in range(2, 8):
        repo.submit(_persona(f"p{i}", i))
    codice, out = _esegui(repo, esegui=True, linker=lambda c: None)
    assert codice == 0
    assert "controllo soglia non necessario" in out


def test_soglia_ancora_controllata_se_c_e_un_submit_da_fare() -> None:
    repo = _repo_con(2)
    _esegui(repo, esegui=True, linker=lambda c: None)
    del repo._store[ID_DEMO[0]]
    for i in range(2, 8):
        repo.submit(_persona(f"p{i}", i))
    codice, _ = _esegui(repo, esegui=True, linker=lambda c: None)
    assert codice == 1
    assert ID_DEMO[0] not in _tutti(repo)


def test_dsn_con_timeout() -> None:
    assert script._dsn_con_timeout("postgresql://h/d?sslmode=require") == (
        "postgresql://h/d?sslmode=require&connect_timeout=10"
    )
    assert script._dsn_con_timeout("postgresql://h/d") == "postgresql://h/d?connect_timeout=10"
    assert script._dsn_con_timeout("postgresql://h/d?connect_timeout=3").endswith("=3")


# ---- main(): flag, ramo Neo4j irraggiungibile, nessun traceback ------------


class _LinkerFinto:
    """Sostituisce Neo4jMemoryLinker: nessuna rete."""

    def __init__(
        self, *, mancanti: list[str] | None = None, errore: Exception | None = None
    ) -> None:
        self._mancanti = mancanti or []
        self._errore = errore
        self.collegati: list[str] = []
        self.chiuso = False

    def __enter__(self) -> _LinkerFinto:
        return self

    def __exit__(self, *exc: object) -> None:
        self.chiuso = True

    def targets_mancanti(self, ids: list[str]) -> list[str]:
        if self._errore is not None:
            raise self._errore
        return self._mancanti

    def link(self, c: MemoryContribution) -> None:
        self.collegati.append(c.id)


def _main_finto(
    monkeypatch: pytest.MonkeyPatch, repo: InMemoryMemoryRepository, linker: _LinkerFinto
) -> None:
    class _Neo:
        @staticmethod
        def from_env() -> _LinkerFinto:
            return linker

    monkeypatch.setattr(script, "PostgresMemoryRepository", lambda dsn: repo)
    monkeypatch.setattr(script, "Neo4jMemoryLinker", _Neo)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")


def test_main_default_a_secco_ed_esegui_scrive(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo_con(2)
    linker = _LinkerFinto()
    _main_finto(monkeypatch, repo, linker)
    assert script.main([]) == 0
    assert len(_tutti(repo)) == 2 and linker.collegati == []
    assert "PROVA A SECCO" in capsys.readouterr().out
    assert script.main(["--esegui"]) == 0
    assert len(_tutti(repo)) == 2 + 4 and linker.collegati == ID_DEMO
    assert linker.chiuso


def test_main_neo4j_irraggiungibile_exit_1_senza_traceback_e_senza_scritture(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from neo4j.exceptions import ServiceUnavailable

    repo = _repo_con(2)
    segreto = "neo4j+s://utente:PASSWORD-SEGRETA@aura.example"
    linker = _LinkerFinto(errore=ServiceUnavailable(segreto))
    _main_finto(monkeypatch, repo, linker)
    for argv in ([], ["--esegui"]):
        assert script.main(argv) == 1
    cattura = capsys.readouterr()
    testo = cattura.out + cattura.err
    assert "ERRORE" in testo and "ServiceUnavailable" in testo
    assert "Traceback" not in testo
    assert "PASSWORD-SEGRETA" not in testo  # nessun dettaglio dell'eccezione stampato
    assert len(_tutti(repo)) == 2  # nessuna scrittura
    assert linker.chiuso


def test_main_neo4j_from_env_solleva_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from neo4j.exceptions import ServiceUnavailable

    class _Neo:
        @staticmethod
        def from_env() -> None:
            raise ServiceUnavailable("x")

    monkeypatch.setattr(script, "PostgresMemoryRepository", lambda dsn: _repo_con(0))
    monkeypatch.setattr(script, "Neo4jMemoryLinker", _Neo)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
    assert script.main(["--esegui"]) == 1
    assert "Traceback" not in capsys.readouterr().out


def test_main_target_mancante_nel_grafo_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo_con(2)
    _main_finto(monkeypatch, repo, _LinkerFinto(mancanti=["mura-urbane"]))
    assert script.main(["--esegui"]) == 1
    assert len(_tutti(repo)) == 2
    assert "Ricarica prima il seed" in capsys.readouterr().out


def test_main_configurazione_mancante_exit_1_senza_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def senza_dsn() -> str:
        raise ValueError("DATABASE_URL mancante")

    monkeypatch.setattr(script, "database_url_from_env", senza_dsn)
    assert script.main([]) == 1
    out = capsys.readouterr().out
    assert "ERRORE" in out and "Traceback" not in out


def test_presente_non_curato_non_richiama_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo_con(2)
    id0, r0, t0 = script.RICORDI_DEMO[0]
    repo.submit(script._costruisci(id0, r0, t0))
    sottomessi: list[str] = []
    reale = script.submit_contribution

    def conta(r: InMemoryMemoryRepository, c: MemoryContribution) -> MemoryContribution:
        sottomessi.append(c.id)
        return reale(r, c)

    monkeypatch.setattr(script, "submit_contribution", conta)
    codice, _ = _esegui(repo, esegui=True)
    assert codice == 0
    assert sottomessi == ID_DEMO[1:]  # il primo c'era gia': solo curatela


def test_soglia_default_segue_la_costante_importata(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ricarica lo script con la costante cambiata: se fosse cablata, il default non seguirebbe.
    monkeypatch.setattr(soglia_mod, "SOGLIA_MINIMA_PERSONE", 20)
    ricaricato = _carica()
    default = inspect.signature(ricaricato.esegui_caricamento).parameters["soglia_minima"].default
    assert default == 20
