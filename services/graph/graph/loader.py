"""`python -m graph.loader` — (ri)popola Neo4j da zero, in un solo comando.

Esegue, in ordine, gli script versionati in `cypher/`:

1. `00_schema.cypher` — vincoli e indici (`CREATE ... IF NOT EXISTS`:
   idempotente);
2. `01_seed_<città>.cypher` — nodi e relazioni del dataset della città scelta
   da `CITY_SEED` (`graph.registro`; `MERGE`: idempotente).

Aura Free cancella l'istanza dopo 30 giorni di inattività: il grafo è un
ARTEFATTO RICOSTRUIBILE, non un archivio. Questo comando è l'unico modo
supportato per popolarlo, sia su Aura sia su Neo4j Community in locale — la
differenza tra i due profili sta solo nel `.env` (`neo4j+s://` vs
`bolt://`), mai nel codice.

Uso (PowerShell, dalla radice del repo, dopo `pip install -e packages/
contracts -e services/graph` e con `.env` compilato):

    python -m graph.loader
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from contracts import decodifica_fasce
from neo4j import GraphDatabase

from graph.env import Neo4jConfig, load_neo4j_config
from graph.registro import CYPHER_DIR, dataset_attivo, file_seed_cypher

SCHEMA_FILE = CYPHER_DIR / "00_schema.cypher"


def _statements(path: Path) -> list[str]:
    """Spezza un file `.cypher` in singole istruzioni eseguibili.

    Convenzione dei file generati da `graph.export_cypher`: ogni istruzione
    termina con `;` seguito da newline, i commenti sono righe che iniziano
    con `//`. Nessuna istruzione del seed contiene `;` dentro una stringa
    letterale (i valori del dataset non lo richiedono).
    """
    text = path.read_text(encoding="utf-8")
    statements: list[str] = []
    for chunk in text.split(";\n"):
        righe_utili = [
            line for line in chunk.splitlines() if not line.strip().startswith("//")
        ]
        stmt = "\n".join(righe_utili).strip()
        if stmt:
            statements.append(stmt)
    return statements


_LIT = r"'(?:[^'\\]|\\.)*'"  # letterale tra apici singoli, con escape `\x`
_RE_ID_ESPERIENZA = re.compile(r"MERGE \(e:Esperienza \{id: '((?:[^'\\]|\\.)*)'\}\)")
_RE_ORARI = re.compile(rf"e\.orari_apertura = \[((?:\s*{_LIT}\s*,?)*)\]")
_RE_LITERAL_C = re.compile(r"'((?:[^'\\]|\\.)*)'")


def _unescape(valore: str) -> str:
    return re.sub(r"\\(.)", r"\1", valore)


def valida_orari(path: Path) -> int:
    """Valida TUTTE le `orari_apertura` di un file `.cypher` senza toccare il DB.

    Appoggia sulla convenzione di `graph.export_cypher`: un'istruzione
    `MERGE (e:Esperienza {id: '...'}) SET ..., e.orari_apertura = ['...', ...]`.
    Ogni stringa passa da `contracts.decodifica_fasce` (fail-closed). Se un
    file cita `orari_apertura` in una forma che non si riesce a leggere, è
    rifiutato anch'esso: meglio un falso rifiuto di un orario guasto che
    diventa "sempre aperto". Solleva `ValueError` (esperienza + stringa);
    ritorna il numero di fasce validate.

    Limiti: riconosce solo la forma generata dall'export (non è un parser
    Cypher); un file scritto a mano in altra forma e con la proprietà
    scritta altrove (es. `SET n += {...}`) non è coperto.
    """
    totale = 0
    for statement in _statements(path):
        if "orari_apertura" not in statement:
            continue
        m_id = _RE_ID_ESPERIENZA.search(statement)
        nome = _unescape(m_id.group(1)) if m_id else "<esperienza non riconosciuta>"
        m = _RE_ORARI.search(statement)
        if m is None or m_id is None:
            raise ValueError(
                f"{path.name}: esperienza {nome!r}: 'orari_apertura' in forma non "
                "riconosciuta (atteso lista di stringhe nell'istruzione MERGE Esperienza)"
            )
        valori = [_unescape(v) for v in _RE_LITERAL_C.findall(m.group(1))]
        try:
            decodifica_fasce(valori)
        except ValueError as exc:
            raise ValueError(
                f"{path.name}: esperienza {nome!r}: orari_apertura {valori!r} non valido: {exc}"
            ) from exc
        totale += len(valori)
    return totale


# Unica cancellazione ammessa nel seed: la forma generata da
# `graph.export_cypher._pulisci_evoca_statement` (una riga, label e tipo espliciti).
_RE_PULIZIA_EVOCA = re.compile(
    rf"MATCH \(e:Esperienza \{{id: {_LIT}\}}\)-\[r:EVOCA\]->\(t:Tema\) "
    rf"WHERE NOT t\.id IN \[(?:{_LIT}(?:, {_LIT})*)?\] DELETE r"
)
_RE_CANCELLAZIONE = re.compile(r"\b(?:DETACH|DELETE|REMOVE)\b", re.IGNORECASE)
_RE_LITERAL_ALL = re.compile(_LIT)


def valida_cancellazioni(path: Path) -> int:
    """Rifiuta un seed che contiene `DELETE`, `DETACH` o `REMOVE` in una forma
    diversa dalla pulizia `EVOCA` esatta generata dall'export.

    Le parole dentro i letterali stringa (titoli, racconti) non contano; i
    commenti `//` sono già esclusi da `_statements`. Solleva `ValueError`;
    ritorna il numero di pulizie `EVOCA` riconosciute. Limite: non è un parser
    Cypher, è una guardia a forma esatta (fail-closed)."""
    pulizie = 0
    for statement in _statements(path):
        senza_stringhe = _RE_LITERAL_ALL.sub("''", statement)
        if _RE_CANCELLAZIONE.search(senza_stringhe) is None:
            continue
        if _RE_PULIZIA_EVOCA.fullmatch(statement) is None:
            raise ValueError(
                f"{path.name}: cancellazione non ammessa (solo la pulizia "
                f"(:Esperienza)-[:EVOCA]->(:Tema) generata dall'export): {statement[:120]!r}"
            )
        pulizie += 1
    return pulizie


def run(config: Neo4jConfig, seed_file: Path | None = None) -> int:
    """Esegue schema + seed su Neo4j. Ritorna il numero di istruzioni eseguite.

    `seed_file=None` -> il seed della città attiva (`CITY_SEED`)."""
    seed = seed_file if seed_file is not None else file_seed_cypher(dataset_attivo())
    # Prima di QUALUNQUE connessione o scrittura: un orario malformato rifiuta
    # l'intero caricamento (nessuna scrittura parziale).
    valida_orari(seed)
    valida_cancellazioni(seed)
    driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))
    eseguite = 0
    try:
        driver.verify_connectivity()
        with driver.session(database=config.database) as session:
            for path in (SCHEMA_FILE, seed):
                for statement in _statements(path):
                    session.run(statement)
                    eseguite += 1
    finally:
        driver.close()
    return eseguite


def main() -> None:
    try:
        config = load_neo4j_config()
    except ValueError as exc:
        print(f"Configurazione Neo4j mancante: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    seed_file = file_seed_cypher(dataset_attivo())
    try:
        eseguite = run(config, seed_file)
    except ValueError as exc:
        print(f"Caricamento rifiutato: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        f"OK: {eseguite} istruzioni Cypher eseguite su database={config.database!r} "
        f"({SCHEMA_FILE.name} + {seed_file.name})."
    )


if __name__ == "__main__":
    main()
