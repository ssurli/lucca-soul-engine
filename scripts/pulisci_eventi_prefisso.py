"""Cancella da `behavior_event` su Postgres (Neon in cloud, locale con Docker)
tutte le righe il cui `person_id` inizia con un prefisso dato — pensato per
ripulire eventi SINTETICI iniettati a mano per verificare a mano il gate di
privacy k=10 di `GET /dashboard/*` (`docs/DATA_CONTRACTS.md` §7,
`docs/LIMITI.md`), mai per un uso applicativo (nessun endpoint del BFF chiama
questo script).

Perché serve, non solo "sarebbe carino averlo": `behavior_event` alimenta DUE
consumatori con scoping temporale DIVERSO:

- `intelligence_index` (Wave 4, `GET /dashboard/*`) filtra SEMPRE per
  `periodo` (`events_in_period`) — un evento sintetico datato in un periodo
  futuro (es. "2027-01") non compare in un `GET /dashboard/index?periodo=2026-07`
  di oggi.
- `recommender` (Wave 3b, `conteggio_per_esperienza`, dentro `POST /itinerary`)
  NON filtra per data: `SELECT tipo, experience_id, COUNT(*) FROM
  behavior_event GROUP BY tipo, experience_id` legge TUTTA la storia, a
  prescindere da `ts`. Un evento sintetico, anche datato nel futuro, altera
  SUBITO la quota storica del ranking reale finché non viene cancellato — su
  un dataset piccolo, in modo misurabile. Scegliere un periodo futuro per
  l'evento protegge SOLO l'Index/la dashboard, MAI il Recommender: la pulizia
  resta obbligatoria e urgente in ogni caso, non solo buona educazione.

Uso (PowerShell, dalla radice del repo, con l'ambiente virtuale del BFF/
recommender attivato — serve `psycopg`, installato da
`pip install -e services/recommender`):

    python scripts\\pulisci_eventi_prefisso.py verifica-k10-

Cancella ogni riga con `person_id LIKE 'verifica-k10-%'` (il prefisso passato
+ `%`, il resto è gestito qui: non serve passare il simbolo `%` a mano) e
stampa quante righe sono state cancellate. Nessuna conferma interattiva:
pensato per essere lanciato subito dopo una verifica manuale, non per un uso
distratto — il prefisso è un argomento obbligatorio, apposta senza default,
per non rischiare un `DELETE` su tutta la tabella per errore.
"""

from __future__ import annotations

import sys

import psycopg
from recommender._env import database_url_from_env

if len(sys.argv) != 2 or not sys.argv[1]:
    print(
        "uso: python scripts\\pulisci_eventi_prefisso.py <prefisso_person_id>\n"
        "esempio: python scripts\\pulisci_eventi_prefisso.py verifica-k10-",
        file=sys.stderr,
    )
    raise SystemExit(2)

prefisso = sys.argv[1]
pattern_like = f"{prefisso}%"

dsn = database_url_from_env()

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM behavior_event WHERE person_id LIKE %s",
            (pattern_like,),
        )
        cancellate = cur.rowcount
    conn.commit()

print(f"pattern={pattern_like!r}")
print(f"righe cancellate da behavior_event: {cancellate}")
