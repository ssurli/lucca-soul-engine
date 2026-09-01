"""Il freno di emergenza (`urban_memory.freno_pattern`, Fase 3,
`docs/STATE_MACHINE.md` §4-bis(b)) sopprime la RACCOMANDAZIONE di un
`:Evento` promosso, MAI il deposito della traccia nel ledger
(`urban_memory.canale_fluttuante.sweep_and_fetch_active` /
`urban_memory.traccia_repository`) — brief esplicito: "la traccia di un
evento frenato continua a depositarsi (soppressione della raccomandazione,
non del deposito)".

Due garanzie DISTINTE in questo file, non ridondanti:

1. **Guard strutturale (AST, nessun import runtime necessario)** — stesso
   principio di `test_purezza_experience_engine.py`: il freno (`freno_pattern`
   /`freno_repository`) e il ledger delle tracce (`canale_fluttuante`/
   `traccia_repository`/`segnale_repository`) non si importano MAI a
   vicenda. Se un giorno qualcuno introducesse un accoppiamento (es. il freno
   che legge/scrive `traccia_luogo`, o il canale fluttuante che consulta
   `pattern_frenato`), questo test lo cattura PRIMA che serva uno scenario
   comportamentale per accorgersene.

2. **Scenario comportamentale end-to-end** — un pattern viene promosso e poi
   FRENATO (`tira_freno`, `frenato=True` sull'`:Evento`); nel frattempo un
   `SegnaleFluttuante` approvato (`non_commerciale=True`) per lo STESSO
   `place_id`/`temi` scade e viene spazzato (`sweep_and_fetch_active`): la sua
   traccia si deposita normalmente nel ledger, esattamente come se il freno
   non fosse mai stato tirato — i due meccanismi condividono solo
   `place_id`/`temi` come dato di dominio (coincidenza del pattern), MAI uno
   stato o uno storage.

Verificato leggendo `services/urban-memory/urban_memory/canale_fluttuante.py`,
`freno_pattern.py` e `traccia_repository.py`: nessuna riga dell'uno importa o
richiama l'altro — il freno scrive `e.frenato` SOLO su `:Evento` nel grafo
Neo4j via `scrivi_freno_evento`/`Neo4jFrenoClient`; il ledger scrive SOLO
`traccia_luogo` in Postgres via `TracciaRepository.deposita`, invocato da
`sweep_and_fetch_active` — due percorsi che non si toccano."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contracts import SegnaleFluttuante
from urban_memory.canale_fluttuante import sweep_and_fetch_active
from urban_memory.freno_pattern import tira_freno
from urban_memory.freno_repository import InMemoryPatternFrenatoRepository
from urban_memory.segnale_repository import InMemorySegnaleFluttuanteRepository
from urban_memory.traccia_repository import InMemoryTracciaRepository

_URBAN_MEMORY_DIR = Path(__file__).resolve().parents[1] / "urban_memory"

_MODULI_FRENO = ("freno_pattern", "freno_repository")
_MODULI_TRACCIA = ("canale_fluttuante", "traccia_repository", "segnale_repository")


def _moduli_importati(path: Path) -> set[str]:
    albero = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nomi: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            nomi.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nomi.add(nodo.module.split(".")[-1] if nodo.level else nodo.module.split(".")[0])
            # `from . import traccia_repository` (livello relativo): il nome
            # rilevante è l'ultimo segmento del modulo importato, non
            # "urban_memory"/vuoto — catturato separatamente sotto per i
            # `from .x import y` (nodo.module == "x").
            if nodo.level:
                nomi.add(nodo.module.split(".")[0])
    return nomi


# ---------------------------------------------------------------------------
# 1. Guard strutturale — nessun import a vicenda
# ---------------------------------------------------------------------------


def test_urban_memory_dir_esiste() -> None:
    assert _URBAN_MEMORY_DIR.is_dir(), (
        f"atteso {_URBAN_MEMORY_DIR} — layout del repo cambiato?"
    )


def test_moduli_del_freno_esistono() -> None:
    # Se questi mancano, i test sotto sarebbero un falso "verde" per percorso
    # sbagliato, non per assenza reale di accoppiamento.
    for nome in _MODULI_FRENO + _MODULI_TRACCIA:
        assert (_URBAN_MEMORY_DIR / f"{nome}.py").is_file(), (
            f"atteso {_URBAN_MEMORY_DIR / f'{nome}.py'} — modulo rinominato/spostato?"
        )


def test_freno_non_importa_mai_il_ledger_delle_tracce() -> None:
    """`freno_pattern.py`/`freno_repository.py` non importano mai
    `canale_fluttuante`/`traccia_repository`/`segnale_repository`: il freno
    non sa nulla del ledger, non può leggerlo né scriverlo."""
    for nome_freno in _MODULI_FRENO:
        path = _URBAN_MEMORY_DIR / f"{nome_freno}.py"
        importati = _moduli_importati(path)
        for nome_traccia in _MODULI_TRACCIA:
            assert nome_traccia not in importati, (
                f"{path} importa {nome_traccia!r}: il freno non deve MAI "
                "conoscere il ledger delle tracce (docs/STATE_MACHINE.md "
                "§4-bis(b) — sopprime la raccomandazione, non il deposito)."
            )


def test_ledger_delle_tracce_non_importa_mai_il_freno() -> None:
    """Simmetrico: `canale_fluttuante.py`/`traccia_repository.py`/
    `segnale_repository.py` non importano mai `freno_pattern`/
    `freno_repository` — il deposito di una traccia non può essere
    condizionato dallo stato del freno."""
    for nome_traccia in _MODULI_TRACCIA:
        path = _URBAN_MEMORY_DIR / f"{nome_traccia}.py"
        importati = _moduli_importati(path)
        for nome_freno in _MODULI_FRENO:
            assert nome_freno not in importati, (
                f"{path} importa {nome_freno!r}: il ledger delle tracce non "
                "deve MAI conoscere il freno (il deposito prosegue "
                "incondizionatamente, indipendentemente da un evento "
                "frenato)."
            )


def test_canale_fluttuante_non_menziona_mai_frenato_nel_sorgente() -> None:
    """Verifica testuale aggiuntiva, oltre agli import: la proprietà
    `frenato` (specifica dell'`:Evento` promosso) non compare da nessuna
    parte nel sorgente del canale fluttuante — non solo "nessun import la
    porta dentro", ma "nessuna riga la nomina anche per accesso indiretto
    (es. via un dict/kwargs)."""
    path = _URBAN_MEMORY_DIR / "canale_fluttuante.py"
    sorgente = path.read_text(encoding="utf-8")
    assert "frenato" not in sorgente, (
        f"{path} nomina 'frenato': il canale fluttuante non deve avere "
        "alcuna nozione del freno di emergenza sugli :Evento promossi."
    )


# ---------------------------------------------------------------------------
# 2. Scenario comportamentale — freno tirato, traccia depositata comunque
# ---------------------------------------------------------------------------

ORA = datetime.now(UTC)

_PLACE_ID = "piazza-anfiteatro"
_TEMI = ("musica", "arte")


def _segnale_approvato_per_lo_stesso_pattern(**overrides: Any) -> SegnaleFluttuante:
    """Un `SegnaleFluttuante` approvato (`non_commerciale=True`) per LO
    STESSO `place_id`/insieme di `temi` del pattern che, sul lato-grafo,
    corrisponde all'`:Evento` promosso che stiamo per frenare — la
    coincidenza è deliberata (dimostra che solo il DATO di dominio è
    condiviso, mai lo stato/storage)."""
    defaults: dict[str, Any] = {
        "id": "violinista-piazza-anfiteatro-durante-il-freno",
        "descrizione": "Un violinista suona in piazza mentre il pattern è frenato",
        "temi": list(_TEMI),
        "place_id": _PLACE_ID,
        "non_commerciale": True,
        "valido_fino": ORA + timedelta(minutes=1),
    }
    defaults.update(overrides)
    return SegnaleFluttuante(**defaults)


def test_traccia_si_deposita_normalmente_mentre_levento_e_frenato() -> None:
    """Scenario concreto richiesto dal brief: un pattern viene frenato
    (`tira_freno` su `evento-id` corrispondente), e SUBITO DOPO una nuova
    occorrenza (un `SegnaleFluttuante` approvato per lo stesso place/temi)
    scade e deposita comunque la sua traccia nel ledger, come se il freno non
    esistesse — il freno non tocca né `SegnaleFluttuanteRepository` né
    `TracciaRepository`, quindi non ha alcun modo di intercettare o
    sopprimere questo deposito."""
    # --- lato freno: il pattern promosso (`:Evento`) viene frenato ---------
    freno_writer_chiamate: list[tuple[str, bool]] = []

    def _freno_writer(evento_id: str, frenato: bool) -> None:
        freno_writer_chiamate.append((evento_id, frenato))

    freno_repo = InMemoryPatternFrenatoRepository()
    riga_freno = tira_freno(
        "evento-piazza-anfiteatro-arte-musica",
        attore="promotore-uno",
        motivazione="ordinanza comunale immediata",
        writer=_freno_writer,
        repo=freno_repo,
        place_id=_PLACE_ID,
        temi=list(_TEMI),
        quando=ORA,
    )
    assert riga_freno.azione == "tirato"
    assert freno_writer_chiamate == [("evento-piazza-anfiteatro-arte-musica", True)]

    # --- lato ledger: un segnale approvato per LO STESSO pattern scade -----
    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()
    segnale_repo.persist(_segnale_approvato_per_lo_stesso_pattern())

    istante_sweep = ORA + timedelta(hours=1)  # dopo la scadenza del segnale
    attivi = sweep_and_fetch_active(segnale_repo, traccia_repo, now=istante_sweep)

    # Il segnale non compare più tra gli attivi (è scaduto)...
    assert attivi == []
    # ...MA la sua traccia È stata depositata, ESATTAMENTE come nel cammino
    # felice senza alcun freno tirato (vedi test_canale_fluttuante.py::
    # test_segnale_scaduto_non_compare_e_deposita_traccia_una_sola_volta).
    tracce = traccia_repo.list_for_place(_PLACE_ID)
    assert len(tracce) == 1, (
        "il deposito della traccia NON deve essere soppresso da un freno "
        "tirato su un :Evento dello stesso pattern — il freno sopprime "
        "SOLO la raccomandazione (docs/STATE_MACHINE.md §4-bis(b))"
    )
    traccia = tracce[0]
    assert traccia.segnale_id == "violinista-piazza-anfiteatro-durante-il-freno"
    assert traccia.place_id == _PLACE_ID
    assert traccia.temi == _TEMI
    assert traccia.creato_il == istante_sweep

    # Il freno resta, indipendentemente, tirato: nessuno dei due percorsi ha
    # influenzato l'altro.
    [registrata] = freno_repo.per_evento("evento-piazza-anfiteatro-arte-musica")
    assert registrata.azione == "tirato"


def test_traccia_continua_a_depositarsi_su_piu_occorrenze_con_freno_sempre_tirato() -> None:
    """Rinforza lo scenario sopra su PIÙ occorrenze successive (non solo una):
    con il freno tirato e MAI rilasciato in questo test, tre segnali
    approvati distinti per lo stesso pattern scadono in tre sweep separati e
    depositano, ciascuno, la propria traccia — il ledger non "si accorge" in
    alcun modo che l'evento corrispondente è frenato."""
    freno_repo = InMemoryPatternFrenatoRepository()
    tira_freno(
        "evento-piazza-anfiteatro-arte-musica",
        attore="promotore-uno",
        motivazione="freno di lunga durata per questo test",
        writer=lambda evento_id, frenato: None,
        repo=freno_repo,
        quando=ORA,
    )

    segnale_repo = InMemorySegnaleFluttuanteRepository()
    traccia_repo = InMemoryTracciaRepository()

    for indice in range(3):
        segnale_repo.persist(
            _segnale_approvato_per_lo_stesso_pattern(
                id=f"occorrenza-{indice}",
                valido_fino=ORA + timedelta(minutes=1) + timedelta(hours=indice),
            )
        )
        sweep_and_fetch_active(
            segnale_repo, traccia_repo, now=ORA + timedelta(hours=indice + 1)
        )

    tracce = traccia_repo.list_for_place(_PLACE_ID)
    assert sorted(t.segnale_id for t in tracce) == [
        "occorrenza-0",
        "occorrenza-1",
        "occorrenza-2",
    ], "ogni occorrenza successiva deve depositare la propria traccia, freno o no"
