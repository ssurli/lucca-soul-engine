"""Guardia permanente: nessuna città cablata nel codice di produzione.

Regola: il contenuto locale vive nel dataset, selezionato da CITY_SEED.
Nel codice di produzione non deve comparire "lucc" (case-insensitive, quindi
anche "lucchese"), salvo il nome del prodotto "Lucca Soul" e l'allowlist
esplicita qui sotto.
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

PACCHETTI_PY = [
    "packages/contracts/contracts",
    "services/api/api",
    "services/experience-engine/experience_engine",
    "services/graph/graph",
    "services/intelligence-index/intelligence_index",
    "services/marketplace/marketplace",
    "services/rag/rag",
    "services/recommender/recommender",
    "services/urban-memory/urban_memory",
]

_LIMITE_APP = "limite aperto: app cablata su Lucca, vedi docs/LIMITI.md"

# File interi ammessi, ciascuno con il motivo.
ALLOWLIST_FILE: dict[str, str] = {
    # modulo dataset della città: è il posto dove vive il contenuto locale
    "services/graph/graph/seed_lucca.py": "modulo dataset della città",
    "apps/lucca_soul_app/lib/main.dart": _LIMITE_APP,
    "apps/lucca_soul_app/lib/util/app_strings.dart": _LIMITE_APP,
    "apps/lucca_soul_app/lib/util/known_places.dart": _LIMITE_APP,
    "apps/lucca_soul_app/lib/util/signal_presets.dart": _LIMITE_APP,
}

# File ammessi solo sulle righe che soddisfano il pattern.
ALLOWLIST_RIGHE: dict[str, tuple[re.Pattern[str], str]] = {
    # unico punto in cui vive CITY_SEED_PREDEFINITO
    "services/graph/graph/registro.py": (
        re.compile(r"^\s*CITY_SEED_PREDEFINITO\b"),
        "solo la riga che definisce CITY_SEED_PREDEFINITO",
    ),
}

PRODOTTO = re.compile(r"(?i)lucca[ _-]?soul")
CERCATO = re.compile(r"(?i)lucc")

REGOLA = (
    "Nessuna città cablata nel codice: il contenuto locale vive nel dataset, "
    "selezionato da CITY_SEED."
)


def _rel(p: Path) -> str:
    return p.relative_to(RADICE).as_posix()


def _file_per_scope() -> dict[str, list[Path]]:
    py: list[Path] = []
    for pacchetto in PACCHETTI_PY:
        py += sorted((RADICE / pacchetto).rglob("*.py"))
    cypher = [
        p
        for p in sorted((RADICE / "services").glob("*/cypher/*.cypher"))
        if not p.name.startswith("01_seed_")
    ]
    dart = sorted((RADICE / "apps/lucca_soul_app/lib").rglob("*.dart"))
    return {"python": py, "cypher": cypher, "dart": dart}


def test_ogni_scope_contiene_file() -> None:
    for scope, files in _file_per_scope().items():
        assert files, f"scope '{scope}' vuoto: glob sbagliato, la guardia sarebbe cieca"
    # ogni pacchetto Python deve contribuire
    for pacchetto in PACCHETTI_PY:
        assert list((RADICE / pacchetto).rglob("*.py")), f"nessun .py in {pacchetto}"


def test_allowlist_non_morta() -> None:
    mancanti = [
        voce
        for voce in [*ALLOWLIST_FILE, *ALLOWLIST_RIGHE]
        if not (RADICE / voce).is_file()
    ]
    assert not mancanti, (
        "Voci di allowlist che non esistono più (allowlist morta, rimuovere "
        f"o aggiornare): {mancanti}"
    )


def test_allowlist_righe_serve_ancora() -> None:
    for voce, (pattern, _) in ALLOWLIST_RIGHE.items():
        testo = (RADICE / voce).read_text(encoding="utf-8")
        assert any(pattern.search(r) for r in testo.splitlines()), (
            f"{voce}: la riga ammessa non esiste più, allowlist morta"
        )


def test_nessuna_citta_cablata() -> None:
    violazioni: list[str] = []
    for files in _file_per_scope().values():
        for path in files:
            rel = _rel(path)
            if rel in ALLOWLIST_FILE:
                continue
            ammessa = ALLOWLIST_RIGHE.get(rel)
            testo = path.read_text(encoding="utf-8")
            for n, riga in enumerate(testo.splitlines(), start=1):
                if not CERCATO.search(PRODOTTO.sub("", riga)):
                    continue
                if ammessa and ammessa[0].search(riga):
                    continue
                violazioni.append(f"{rel}:{n}: {riga.strip()}")
    assert not violazioni, (
        f"Regola violata. {REGOLA}\n"
        "Occorrenze di 'lucc' nel codice di produzione:\n  "
        + "\n  ".join(violazioni)
        + "\nAmmessi solo: nome prodotto 'Lucca Soul' e allowlist esplicita "
        "in tests/test_guardia_citta.py."
    )
