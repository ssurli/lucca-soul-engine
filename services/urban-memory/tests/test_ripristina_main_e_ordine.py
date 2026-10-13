"""Contratto del comando `ripristina_eventi.main` (exit code, privacy
dell'output) e ordine completo di `promuovi_pattern`
(cestino -> luogo -> ledger -> grafo). Nessuna connessione reale: storage e
grafo sono sostituiti con repository in-memory e un writer finto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from urban_memory import curatela_pattern, ripristina_eventi
from urban_memory.cestino_repository import CestinoStorageError, InMemoryPatternCestinatoRepository
from urban_memory.curatela_pattern import (
    ConflittoCestinoError,
    ProiezioneGrafoPendenteError,
    promuovi_pattern,
)
from urban_memory.freno_repository import FrenoStorageError, InMemoryPatternFrenatoRepository
from urban_memory.promozione_evento import (
    LuogoMancanteError,
    PromozioneEventoError,
    evento_id_per_pattern,
)
from urban_memory.promozione_repository import (
    InMemoryPromozioneRepository,
    PromozioneStorageError,
)
from urban_memory.ricorrenza import PatternCandidato

T0 = datetime(2026, 1, 1, tzinfo=UTC)
SEGRETO_1 = "pseudonimo-segreto-uno"
SEGRETO_2 = "pseudonimo-segreto-due"


# ---------------------------------------------------------------------------
# main(): exit code e output
# ---------------------------------------------------------------------------


class _Scrittore:
    """Sostituto di `Neo4jPromozioneWriter` (context manager + from_env)."""

    luoghi: set[str] = set()
    errore_from_env: Exception | None = None
    errore_ripristina: Exception | None = None
    chiamate: list[str] = []

    @classmethod
    def from_env(cls) -> _Scrittore:
        if cls.errore_from_env is not None:
            raise cls.errore_from_env
        return cls()

    def __enter__(self) -> _Scrittore:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def ripristina(self, place_id: str, evento_id: str, *args: Any) -> str:
        if self.errore_ripristina is not None:
            raise self.errore_ripristina
        if place_id not in self.luoghi:
            raise LuogoMancanteError(place_id)
        self.chiamate.append(evento_id)
        return evento_id


class _Cestino:
    def __init__(self, cestinati: set[str] | None = None, errore: Exception | None = None) -> None:
        self.cestinati = cestinati or set()
        self.errore = errore

    def e_cestinato(self, place_id: str, temi: list[str]) -> bool:
        if self.errore is not None:
            raise self.errore
        return place_id in self.cestinati


@pytest.fixture
def ambiente(monkeypatch: pytest.MonkeyPatch):
    """Cabla `main()` su doppi in-memory e ritorna un dict mutabile di
    configurazione (promozione/freno/cestino/migrate_errore)."""
    _Scrittore.luoghi = {"luogo-a", "luogo-b"}
    _Scrittore.errore_from_env = None
    _Scrittore.errore_ripristina = None
    _Scrittore.chiamate = []

    promozione = InMemoryPromozioneRepository()
    for evento_id, place_id, promotore, giorno in (
        ("evento-a", "luogo-a", SEGRETO_1, 0),
        ("evento-b", "luogo-b", SEGRETO_2, 1),
    ):
        promozione.registra(
            evento_id=evento_id,
            place_id=place_id,
            temi=["arte"],
            cadenza_giorni=7.0,
            promotore=promotore,
            promosso_il=T0 + timedelta(days=giorno),
        )
    cfg: dict[str, Any] = {
        "promozione": promozione,
        "freno": InMemoryPatternFrenatoRepository(),
        "cestino": _Cestino(),
        "migrate_errore": None,
    }

    def _migrate(dsn: str) -> None:
        if cfg["migrate_errore"] is not None:
            raise cfg["migrate_errore"]

    monkeypatch.setattr(ripristina_eventi, "database_url_from_env", lambda: "postgresql://finto/db")
    monkeypatch.setattr(ripristina_eventi, "migrate", _migrate)
    monkeypatch.setattr(
        ripristina_eventi, "PostgresPromozioneRepository", lambda dsn: cfg["promozione"]
    )
    monkeypatch.setattr(
        ripristina_eventi, "PostgresPatternFrenatoRepository", lambda dsn: cfg["freno"]
    )
    monkeypatch.setattr(
        ripristina_eventi, "PostgresPatternCestinatoRepository", lambda dsn: cfg["cestino"]
    )
    monkeypatch.setattr(ripristina_eventi, "Neo4jPromozioneWriter", _Scrittore)
    return cfg


def _non_stampa_promotore(out: str) -> None:
    assert SEGRETO_1 not in out and SEGRETO_2 not in out, "il promotore non va mai stampato"


def test_main_tutto_ok_esce_con_0_e_proietta_tutto(ambiente, capsys) -> None:
    ripristina_eventi.main([])  # nessuna SystemExit: exit code 0

    out = capsys.readouterr().out
    assert _Scrittore.chiamate == ["evento-a", "evento-b"]
    assert "RIPRISTINO OK." in out
    assert ":Evento proiettati nel grafo: 2" in out
    assert "python -m urban_memory.frizione_pattern" in out
    _non_stampa_promotore(out)


def test_main_ledger_vuoto_esce_con_0(ambiente, capsys) -> None:
    ambiente["promozione"] = InMemoryPromozioneRepository()
    ripristina_eventi.main([])
    assert "RIPRISTINO OK." in capsys.readouterr().out


def test_main_luogo_mancante_exit_1_e_lo_elenca(ambiente, capsys) -> None:
    _Scrittore.luoghi = {"luogo-a"}  # luogo-b assente dal seed

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert "evento-b" in out and "luogo-b" in out
    assert "RIPRISTINO INCOMPLETO." in out
    assert _Scrittore.chiamate == ["evento-a"]  # il resto e' proiettato comunque
    _non_stampa_promotore(out)


def test_main_rapporto_incompleto_stampa_comunque_il_promemoria_frizione(ambiente, capsys) -> None:
    _Scrittore.luoghi = {"luogo-a"}  # luogo-b assente: rapporto INCOMPLETO

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert "RIPRISTINO INCOMPLETO." in out
    assert ":Evento proiettati nel grafo: 1" in out
    assert "Passo OBBLIGATORIO successivo: python -m urban_memory.frizione_pattern" in out


def test_main_conflitto_cestino_exit_1_e_non_proietta_il_conflitto(ambiente, capsys) -> None:
    ambiente["cestino"] = _Cestino({"luogo-b"})

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert _Scrittore.chiamate == ["evento-a"]
    assert "conflitto cestino/ledger" in out and "evento-b" in out
    _non_stampa_promotore(out)


def test_main_grafo_irraggiungibile_durante_la_proiezione_exit_1(ambiente, capsys) -> None:
    _Scrittore.errore_ripristina = PromozioneEventoError("Aura in pausa")

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert "FERMATO" in out and "Aura in pausa" in out
    assert "Eventi non tentati: 1" in out
    _non_stampa_promotore(out)


def test_main_grafo_irraggiungibile_alla_connessione_exit_1(ambiente, capsys) -> None:
    _Scrittore.errore_from_env = RuntimeError("neo4j+s non raggiungibile")

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert "FALLITO" in out
    _non_stampa_promotore(out)


@pytest.mark.parametrize(
    ("chiave", "errore"),
    [
        ("promozione", PromozioneStorageError("ledger giu'")),
        ("freno", FrenoStorageError("freno giu'")),
        ("cestino", CestinoStorageError("cestino giu'")),
    ],
)
def test_main_errore_di_storage_exit_1_e_nulla_proiettato(ambiente, capsys, chiave, errore) -> None:
    class _Rotto(InMemoryPromozioneRepository, InMemoryPatternFrenatoRepository):
        def elenca(self) -> list[Any]:
            raise errore

        def ultime_azioni(self) -> list[Any]:
            raise errore

    if chiave == "cestino":
        ambiente["cestino"] = _Cestino(errore=errore)
    else:
        ambiente[chiave] = _Rotto()

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert info.value.code == 1
    assert "storage non disponibile" in out
    assert _Scrittore.chiamate == [], "le letture precedono ogni scrittura: nulla proiettato"
    _non_stampa_promotore(out)


def test_main_migrate_che_fallisce_exit_1_senza_toccare_il_grafo(ambiente, capsys) -> None:
    ambiente["migrate_errore"] = PromozioneStorageError("db irraggiungibile")

    with pytest.raises(SystemExit) as info:
        ripristina_eventi.main([])

    assert info.value.code == 1
    assert "FALLITO" in capsys.readouterr().out
    assert _Scrittore.chiamate == []


def test_main_output_con_freno_e_luogo_mancante_non_contiene_mai_il_promotore(
    ambiente, capsys
) -> None:
    ambiente["freno"].registra(
        evento_id="evento-a",
        place_id=None,
        temi=[],
        azione="tirato",
        attore=SEGRETO_1,
        motivazione=SEGRETO_2,
        quando=T0,
    )
    _Scrittore.luoghi = {"luogo-a"}

    with pytest.raises(SystemExit):
        ripristina_eventi.main([])

    out = capsys.readouterr().out
    assert "Freno ripristinato (scritto col nodo) su 1" in out
    _non_stampa_promotore(out)  # ne' promotore, ne' attore/motivazione del freno


# ---------------------------------------------------------------------------
# promuovi_pattern: ordine completo cestino -> luogo -> ledger -> grafo
# ---------------------------------------------------------------------------

CANDIDATO = PatternCandidato(
    place_id="piazza-anfiteatro",
    temi=("arte", "musica"),
    occorrenze=(T0, T0 + timedelta(days=7), T0 + timedelta(days=14)),
    cadenza_giorni=7.0,
    coefficiente_variazione=0.0,
)
EVENTO_ID = evento_id_per_pattern("piazza-anfiteatro", ("arte", "musica"))


class _RepoTracciato(InMemoryPromozioneRepository):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self.log = log

    def registra(self, **kwargs: Any):  # type: ignore[override]
        self.log.append("ledger")
        return super().registra(**kwargs)


def test_ordine_completo_cestino_luogo_ledger_grafo() -> None:
    log: list[str] = []
    repo = _RepoTracciato(log)

    def e_cestinato(_p: str, _t: list[str]) -> bool:
        log.append("cestino")
        return False

    def luogo_esiste(_p: str) -> bool:
        log.append("luogo")
        return True

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, q: datetime) -> str:
        log.append("grafo")
        return evento_id_per_pattern(p, t)

    promuovi_pattern(
        CANDIDATO,
        promotore="p",
        writer=writer,
        repo=repo,
        luogo_esiste=luogo_esiste,
        e_cestinato=e_cestinato,
    )

    assert log == ["cestino", "luogo", "ledger", "grafo"]


def test_cestino_ha_la_precedenza_sul_luogo_mancante() -> None:
    """Pattern cestinato E luogo assente: vince il conflitto col cestino, e
    il grafo non viene nemmeno interrogato."""
    log: list[str] = []

    def luogo_esiste(_p: str) -> bool:
        log.append("luogo")
        return False

    with pytest.raises(ConflittoCestinoError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=lambda *a: "x",
            repo=_RepoTracciato(log),
            luogo_esiste=luogo_esiste,
            e_cestinato=lambda _p, _t: True,
        )
    assert log == []


def test_cestino_che_fallisce_non_tocca_ne_grafo_ne_ledger() -> None:
    log: list[str] = []

    def e_cestinato(_p: str, _t: list[str]) -> bool:
        raise CestinoStorageError("postgres giu'")

    with pytest.raises(CestinoStorageError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=lambda *a: log.append("grafo") or "x",
            repo=_RepoTracciato(log),
            luogo_esiste=lambda _p: log.append("luogo") or True,
            e_cestinato=e_cestinato,
        )
    assert log == []


def test_ledger_storage_error_non_tocca_il_grafo() -> None:
    class RepoRotto(InMemoryPromozioneRepository):
        def registra(self, **kwargs: Any):  # type: ignore[override]
            raise PromozioneStorageError("postgres giu'")

    def writer(*a: object) -> str:
        raise AssertionError("il grafo non deve essere toccato")

    with pytest.raises(PromozioneStorageError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=writer,
            repo=RepoRotto(),
            luogo_esiste=lambda _p: True,
            e_cestinato=lambda _p, _t: False,
        )


def test_luogo_sparito_tra_verifica_e_scrittura_lascia_ledger_e_segnala_pendente() -> None:
    """Il writer solleva LuogoMancanteError DOPO il ledger: la decisione e'
    registrata, l'errore e' quello 'pendente' (non una perdita silenziosa)."""
    repo = InMemoryPromozioneRepository()

    def writer(*a: object) -> str:
        raise LuogoMancanteError("sparito")

    with pytest.raises(ProiezioneGrafoPendenteError):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=writer,
            repo=repo,
            luogo_esiste=lambda _p: True,
            e_cestinato=lambda _p, _t: False,
        )
    assert repo.registrata(EVENTO_ID)


def test_promosso_il_di_default_e_tz_aware_ed_e_lo_stesso_per_ledger_e_grafo() -> None:
    repo = InMemoryPromozioneRepository()
    visto: list[datetime] = []

    def writer(p: str, t: tuple[str, ...], c: float, pr: str, q: datetime) -> str:
        visto.append(q)
        return evento_id_per_pattern(p, t)

    promuovi_pattern(
        CANDIDATO,
        promotore="p",
        writer=writer,
        repo=repo,
        luogo_esiste=lambda _p: True,
        e_cestinato=lambda _p, _t: False,
    )

    [riga] = repo.elenca()
    assert riga.promosso_il.tzinfo is not None
    assert visto == [riga.promosso_il]


def test_ripromozione_dello_stesso_pattern_aggiunge_una_riga_e_stesso_evento_id() -> None:
    repo = InMemoryPromozioneRepository()
    for _ in range(2):
        promuovi_pattern(
            CANDIDATO,
            promotore="p",
            writer=lambda p, t, c, pr, q: evento_id_per_pattern(p, t),
            repo=repo,
            luogo_esiste=lambda _p: True,
            e_cestinato=lambda _p, _t: False,
        )
    assert {r.evento_id for r in repo.elenca()} == {EVENTO_ID}
    assert len(repo.elenca()) == 2


# ---------------------------------------------------------------------------
# Ciclo interattivo: errori di storage e conflitto cestino
# ---------------------------------------------------------------------------


def test_interattivo_ledger_storage_error_stampa_fallito_senza_propagare(
    monkeypatch, capsys
) -> None:
    risposte = iter(["a", "promotore-1"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))

    class RepoRotto(InMemoryPromozioneRepository):
        def registra(self, **kwargs: Any):  # type: ignore[override]
            raise PromozioneStorageError("postgres giu'")

    def writer(*a: object) -> str:
        raise AssertionError("il grafo non deve essere toccato")

    curatela_pattern._esegui_interattivo(
        [CANDIDATO],
        cestino_repo=InMemoryPatternCestinatoRepository(),
        writer=writer,
        promozione_repo=RepoRotto(),
        luogo_esiste=lambda _p: True,
    )
    assert "FALLITO (nulla registrato)" in capsys.readouterr().out


def test_interattivo_pattern_gia_cestinato_non_promuove(monkeypatch, capsys) -> None:
    risposte = iter(["a", "promotore-1"])
    monkeypatch.setattr(curatela_pattern, "_chiedi", lambda prompt: next(risposte))
    cestino = InMemoryPatternCestinatoRepository()
    cestino.cestina(
        place_id="piazza-anfiteatro",
        temi=["arte", "musica"],
        motivo="gia' rifiutato",
        promotore="altro",
        cestinato_il=T0,
    )
    promozione = InMemoryPromozioneRepository()

    def writer(*a: object) -> str:
        raise AssertionError("il grafo non deve essere toccato")

    curatela_pattern._esegui_interattivo(
        [CANDIDATO],
        cestino_repo=cestino,
        writer=writer,
        promozione_repo=promozione,
        luogo_esiste=lambda _p: True,
    )
    assert "FALLITO (nulla registrato)" in capsys.readouterr().out
    assert promozione.elenca() == []
