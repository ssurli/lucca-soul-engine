"""Test di `urban_memory.segnale_repository` — la tabella-segnale del canale
fluttuante persistente (Fase 3, `docs/PROMOZIONE_TRACCIA.md`).

Parametrizzato con `any_segnale_repository` (InMemory + Postgres effimero,
vedi `tests/conftest.py`): un test che passa solo su una implementazione la
segnala. `PostgresSegnaleFluttuanteRepository` è SALTATA (non fallita) se il
cluster Postgres 16 effimero non è disponibile in questo ambiente.

NOTA sui timestamp: `valido_fino` è sempre costruito RELATIVO a
`datetime.now(UTC)` (mai una data calendariale fissa) — il `model_validator`
del contratto (`SegnaleFluttuante._expired_se_gia_scaduto`) normalizza
`stato=EXPIRED` se `valido_fino` è già nel passato AL MOMENTO DELLA
COSTRUZIONE: una data fissa scritta oggi diventerebbe passato domani,
rompendo silenziosamente questi test in futuro. Il `now` passato a
`sweep_scaduti`/`fetch_attivi` è invece un valore ARBITRARIO scelto dal
test (i metodi del repository non leggono mai l'orologio di sistema): usarlo
per simulare "il tempo è passato" senza bisogno di un vero `sleep`.

Il criterio LOAD-BEARING di questo file è `test_sweep_scaduti_e_idempotente_
non_ritorna_due_volte_lo_stesso_segnale`: la guardia primaria
dell'idempotenza dell'intero canale fluttuante (il deposito della traccia in
`urban_memory.canale_fluttuante.sweep_and_fetch_active` dipende ESATTAMENTE
da questa proprietà)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from contracts import SegnaleFluttuante, StatoSegnaleFluttuante

ORA = datetime.now(UTC)


def _segnale(**overrides: object) -> SegnaleFluttuante:
    defaults: dict[str, object] = {
        "id": "violinista-piazza-anfiteatro-1",
        "descrizione": "Un violinista suona in piazza",
        "temi": ["musica", "arte"],
        "place_id": "piazza-anfiteatro",
        "non_commerciale": True,
        "valido_fino": ORA + timedelta(hours=1),
    }
    defaults.update(overrides)
    return SegnaleFluttuante(**defaults)


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


def test_persist_ritorna_il_segnale_persistito(any_segnale_repository) -> None:
    repo = any_segnale_repository
    segnale = _segnale()

    persistito = repo.persist(segnale)

    assert persistito.id == segnale.id
    assert persistito.stato == StatoSegnaleFluttuante.ATTIVO


def test_persist_di_un_segnale_gia_scaduto_persiste_expired(any_segnale_repository) -> None:
    # Il contratto normalizza stato=EXPIRED se valido_fino è già nel
    # passato AL MOMENTO DELLA COSTRUZIONE (SegnaleFluttuante._expired_se_
    # gia_scaduto): il repository deve rispecchiarlo fedelmente, non
    # "correggerlo" a ATTIVO.
    repo = any_segnale_repository
    segnale = _segnale(id="segnale-gia-scaduto", valido_fino=ORA - timedelta(days=1))
    assert segnale.stato == StatoSegnaleFluttuante.EXPIRED  # precondizione

    persistito = repo.persist(segnale)

    assert persistito.stato == StatoSegnaleFluttuante.EXPIRED


# ---------------------------------------------------------------------------
# fetch_attivi — solo attivi con valido_fino > now
# ---------------------------------------------------------------------------


def test_fetch_attivi_include_un_segnale_ancora_valido(any_segnale_repository) -> None:
    repo = any_segnale_repository
    repo.persist(_segnale(id="ancora-valido", valido_fino=ORA + timedelta(hours=1)))

    attivi = repo.fetch_attivi(ORA)

    assert [s.id for s in attivi] == ["ancora-valido"]


def test_fetch_attivi_esclude_un_segnale_scaduto_non_ancora_spazzato(
    any_segnale_repository,
) -> None:
    # Persistito attivo (valido_fino nel futuro rispetto alla costruzione),
    # poi interrogato con un `now` simulato MOLTO oltre la sua scadenza,
    # SENZA mai chiamare sweep_scaduti: fetch_attivi lo esclude comunque per
    # COSTRUZIONE della query (valido_fino > now) — l'unica cosa che cambia
    # tra `expired` come stato persistito e `valido_fino` semplicemente
    # superato è che qui lo stato in colonna resta 'attivo' (mai spazzato).
    repo = any_segnale_repository
    repo.persist(_segnale(id="scaduto-non-spazzato", valido_fino=ORA + timedelta(hours=1)))

    molto_dopo = ORA + timedelta(days=365)
    assert repo.fetch_attivi(molto_dopo) == []


def test_fetch_attivi_esclude_un_segnale_gia_expired(any_segnale_repository) -> None:
    repo = any_segnale_repository
    repo.persist(
        _segnale(id="expired", valido_fino=ORA + timedelta(hours=1), stato="expired")
    )

    assert repo.fetch_attivi(ORA) == []


# ---------------------------------------------------------------------------
# sweep_scaduti — la transizione atomica attivo -> expired
# ---------------------------------------------------------------------------


def test_sweep_scaduti_transita_un_segnale_scaduto(any_segnale_repository) -> None:
    repo = any_segnale_repository
    repo.persist(_segnale(id="scade-ora", valido_fino=ORA + timedelta(hours=1)))

    dopo = ORA + timedelta(days=1)  # simulato: molto dopo la scadenza reale
    scaduti = repo.sweep_scaduti(dopo)

    assert [s.id for s in scaduti] == ["scade-ora"]
    assert scaduti[0].stato == StatoSegnaleFluttuante.EXPIRED

    # La transizione è persistita: un fetch successivo non lo vede più attivo.
    assert repo.fetch_attivi(dopo) == []


def test_sweep_scaduti_non_tocca_un_segnale_ancora_valido(any_segnale_repository) -> None:
    repo = any_segnale_repository
    repo.persist(_segnale(id="ancora-valido", valido_fino=ORA + timedelta(hours=5)))

    scaduti = repo.sweep_scaduti(ORA)

    assert scaduti == []
    assert [s.id for s in repo.fetch_attivi(ORA)] == ["ancora-valido"]


def test_sweep_scaduti_e_idempotente_non_ritorna_due_volte_lo_stesso_segnale(
    any_segnale_repository,
) -> None:
    """LOAD-BEARING: la guardia primaria dell'idempotenza dell'intero canale
    fluttuante. `urban_memory.canale_fluttuante.sweep_and_fetch_active`
    deposita una traccia per OGNI segnale ritornato da `sweep_scaduti` — se
    questo metodo ritornasse lo STESSO segnale due volte su due chiamate
    successive, la traccia verrebbe depositata due volte (violando
    l'idempotenza load-bearing del task). Verificato QUI, alla fonte."""
    repo = any_segnale_repository
    repo.persist(_segnale(id="scade-una-volta", valido_fino=ORA + timedelta(hours=1)))
    dopo = ORA + timedelta(days=1)

    prima_chiamata = repo.sweep_scaduti(dopo)
    seconda_chiamata = repo.sweep_scaduti(dopo)
    terza_chiamata = repo.sweep_scaduti(dopo + timedelta(days=365))  # anche molto più tardi

    assert [s.id for s in prima_chiamata] == ["scade-una-volta"]
    assert seconda_chiamata == [], (
        "sweep_scaduti ripetuto sullo stesso now NON deve ritornare di nuovo "
        "un segnale già transitato a expired"
    )
    assert terza_chiamata == [], (
        "sweep_scaduti ripetuto con un now ancora più tardo NON deve "
        "ritornare di nuovo un segnale già transitato a expired: la "
        "transizione attivo->expired è la guardia, mai un confronto su now"
    )


def test_sweep_scaduti_e_globale_spazza_piu_luoghi_in_una_chiamata(
    any_segnale_repository,
) -> None:
    """Chiude il buco classico del lazy-sweep ("i luoghi tranquilli non
    vengono mai spazzati"): una SOLA chiamata a sweep_scaduti spazza TUTTI i
    segnali scaduti, di QUALUNQUE place_id — la query non è filtrata per
    luogo."""
    repo = any_segnale_repository
    repo.persist(
        _segnale(id="scade-luogo-a", place_id="luogo-a", valido_fino=ORA + timedelta(hours=1))
    )
    repo.persist(
        _segnale(
            id="scade-luogo-b",
            place_id="luogo-b",
            temi=["storia"],
            valido_fino=ORA + timedelta(hours=1),
        )
    )

    scaduti = repo.sweep_scaduti(ORA + timedelta(days=1))

    assert {s.id for s in scaduti} == {"scade-luogo-a", "scade-luogo-b"}
