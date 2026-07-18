"""CLI di verifica: dimostra che il Marketplace PERSISTE davvero, e che la
commissione non è MAI calcolabile prima della conferma.

Uso (PowerShell, dal repo con `.env` configurato — `DATABASE_URL`
obbligatoria)::

    python -m marketplace.verify

RIESEGUIBILE ALL'INFINITO: ogni passo legge PRIMA lo stato reale del
database (mai "assume che il passo precedente sia riuscito"), stesso
principio di `urban_memory.verify`. Ogni corsa, in ordine, stampa:

1. `migrate(DATABASE_URL)` — applica lo schema (idempotente).
2. La prenotazione d'esempio: PRIMA `repo.get(BOOKING_ID_ESEMPIO)`. Se esiste
   già (una corsa precedente l'ha persistita), la usa così com'è — "già
   presente" è un successo, prova di persistenza. Se non esiste,
   `request_booking` la crea ORA, in stato RICHIESTA, con un id
   deterministico (`id_generator` fisso, non un `uuid4` casuale: serve a
   ritrovarla nelle corse successive).
3. VINCOLO NON NEGOZIABILE — prova che la commissione non esiste PRIMA
   della conferma: se la prenotazione è ancora RICHIESTA in questo momento,
   `repo.get_commission(...)` DEVE restituire `None`. Se invece esistesse
   già (bug), la CLI lo dichiara FALLITO: sarebbe la prova che qualcosa ha
   calcolato una commissione prima della conferma, esattamente il vincolo
   che questo servizio non deve mai violare.
4. Conferma (`confirm_booking`) se non è già CONFERMATA da una corsa
   precedente (idempotente: in quel caso "già confermata" è un successo).
5. Rilegge la prenotazione E la commissione da un repository NUOVO (simula
   un riavvio del processo): prova di persistenza reale, non solo della
   risposta della chiamata precedente.
6. Verifica aritmetica: `importo_eur` registrato è ESATTAMENTE
   `round(prezzo_eur * percentuale, 2)` — la stessa formula di
   `marketplace.service.confirm_booking`, ricalcolata qui in modo
   indipendente sul valore riletto da Postgres.

Lanciato DUE VOLTE (o dopo un riavvio) mostra la stessa prenotazione e la
stessa commissione ancora presenti al passo 5 — il fossato non vive solo in
RAM.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
from contracts import BookingRequest, BookingStatus

from ._env import database_url_from_env
from .migrate import mask_dsn, migrate
from .repository import MarketplaceStorageError, PostgresBookingRepository
from .service import confirm_booking, request_booking

BOOKING_ID_ESEMPIO = "booking-verify-persistenza"
# Non un id reale del seed del grafo (questo servizio non tocca il grafo):
# basta un experience_id qualsiasi, coerente con lo scopo di questa verifica
# (dimostrare la persistenza del Marketplace, non l'esistenza nel grafo).
EXPERIENCE_ID_ESEMPIO = "verify-esperienza-marketplace"
PREZZO_EUR_ESEMPIO = 42.0


def _richiesta_esempio() -> BookingRequest:
    return BookingRequest(
        person_id="persona-verifica",
        experience_id=EXPERIENCE_ID_ESEMPIO,
        quando=datetime.now(UTC),
    )


def main() -> None:
    print("=== Verifica di persistenza — Marketplace ===\n")
    dsn = database_url_from_env()

    print(f"1. Migrazione schema su {mask_dsn(dsn)} (idempotente)...")
    try:
        migrate(dsn)
    except psycopg.Error as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc
    print("   OK: `booking`/`commission_record` esistono (o esistevano già).")

    repo = PostgresBookingRepository(dsn)

    print(f"2. Prenotazione d'esempio (id={BOOKING_ID_ESEMPIO!r})...")
    try:
        prenotazione = repo.get(BOOKING_ID_ESEMPIO)
    except MarketplaceStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    persistita_ora = prenotazione is None
    if prenotazione is not None:
        print("   Già presente da una corsa precedente (OK: è la prova di persistenza).")
    else:
        try:
            prenotazione = request_booking(
                repo,
                _richiesta_esempio(),
                prezzo_eur=PREZZO_EUR_ESEMPIO,
                prenotabile=True,
                id_generator=lambda: BOOKING_ID_ESEMPIO,
            )
        except MarketplaceStorageError as exc:
            print(f"   FALLITO: storage non disponibile/errore — {exc}")
            raise SystemExit(1) from exc
        print(f"   OK: prenotazione persistita ORA, stato={prenotazione.stato.value!r}.")

    print("3. Vincolo non negoziabile: nessuna commissione prima della conferma...")
    try:
        commissione_precedente = repo.get_commission(BOOKING_ID_ESEMPIO)
    except MarketplaceStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    if prenotazione.stato == BookingStatus.RICHIESTA:
        if commissione_precedente is not None:
            print(
                "   FALLITO: esiste già una CommissionRecord per una prenotazione "
                "ancora RICHIESTA — la commissione è stata calcolata PRIMA della "
                "conferma. Questo è il vincolo non negoziabile violato."
            )
            raise SystemExit(1)
        print("   OK: nessuna CommissionRecord esiste per una prenotazione non confermata.")
    else:
        print(
            "   Prenotazione già CONFERMATA da una corsa precedente: questo passo "
            "non è riverificabile ora (non torna a RICHIESTA) — verificato dalla "
            "prima corsa che l'ha confermata."
        )

    print(f"4. Conferma della prenotazione (id={prenotazione.id!r})...")
    if prenotazione.stato == BookingStatus.CONFERMATA:
        print(
            "   Già confermata da una corsa precedente "
            "(OK: idempotente, nessuna doppia commissione)."
        )
    else:
        try:
            prenotazione = confirm_booking(repo, prenotazione.id)
        except MarketplaceStorageError as exc:
            print(f"   FALLITO: storage non disponibile/errore — {exc}")
            raise SystemExit(1) from exc
        print(f"   OK: stato={prenotazione.stato.value!r}, commissione registrata SOLO ora.")

    print("5. Rilettura da un repository NUOVO (simula un riavvio del processo)...")
    repo_riletto = PostgresBookingRepository(dsn)
    try:
        prenotazione_riletta = repo_riletto.get(BOOKING_ID_ESEMPIO)
        commissione_riletta = repo_riletto.get_commission(BOOKING_ID_ESEMPIO)
    except MarketplaceStorageError as exc:
        print(f"   FALLITO: storage non disponibile/errore — {exc}")
        raise SystemExit(1) from exc

    if prenotazione_riletta is None or prenotazione_riletta.stato != BookingStatus.CONFERMATA:
        print("   FALLITO: la prenotazione NON è stata ritrovata CONFERMATA.")
        raise SystemExit(1)
    if commissione_riletta is None:
        print("   FALLITO: la commissione NON è stata ritrovata.")
        raise SystemExit(1)

    origine = (
        "persistita ORA da questa corsa"
        if persistita_ora
        else "persisteva GIÀ da una corsa precedente"
    )
    print(
        f"   TROVATA ({origine}) — prenotazione e commissione ANCORA presenti "
        "dopo la riapertura:"
    )
    print(
        f"     booking id={prenotazione_riletta.id!r}  stato={prenotazione_riletta.stato.value!r}  "
        f"prezzo_eur={prenotazione_riletta.prezzo_eur}"
    )
    print(
        f"     commissione importo_eur={commissione_riletta.importo_eur}  "
        f"percentuale={commissione_riletta.percentuale}"
    )

    print("6. Verifica aritmetica della commissione registrata...")
    atteso = round(prenotazione_riletta.prezzo_eur * commissione_riletta.percentuale, 2)
    if commissione_riletta.importo_eur != atteso:
        print(
            f"   FALLITO: importo_eur={commissione_riletta.importo_eur} != "
            f"atteso={atteso} (prezzo_eur * percentuale)."
        )
        raise SystemExit(1)
    print(f"   OK: importo_eur={commissione_riletta.importo_eur} == prezzo_eur * percentuale.")

    print("\n=== Verifica completata ===")


if __name__ == "__main__":
    main()
