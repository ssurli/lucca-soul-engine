"""Grammatica italiana generale per i testi del motore (nessuna città).

Serve a nominare un luogo dopo una preposizione ("alla Chiesa di San Michele
in Foro", "all'Orto Botanico") senza cablare la grammatica nel
codice: l'articolo del luogo è un DATO del dataset (`Luogo.articolo`,
`GraphCandidate.place_articolo`), la regola delle preposizioni articolate è
questa, una sola per tutti. Funzioni pure, nessuna dipendenza.
"""

from __future__ import annotations

__all__ = ["ARTICOLI", "preposizione_articolata", "con_luogo", "con_articolo"]

# Articoli determinativi ammessi. `None` (non in questa tupla) = nome senza
# articolo (es. una via: "a Via Fillungo").
ARTICOLI: tuple[str, ...] = ("il", "lo", "la", "l'", "i", "gli", "le")

# preposizione semplice -> articolo -> forma articolata
_ARTICOLATE: dict[str, dict[str, str]] = {
    "a": {"il": "al", "lo": "allo", "la": "alla", "l'": "all'",
          "i": "ai", "gli": "agli", "le": "alle"},
    "da": {"il": "dal", "lo": "dallo", "la": "dalla", "l'": "dall'",
           "i": "dai", "gli": "dagli", "le": "dalle"},
    "di": {"il": "del", "lo": "dello", "la": "della", "l'": "dell'",
           "i": "dei", "gli": "degli", "le": "delle"},
    "in": {"il": "nel", "lo": "nello", "la": "nella", "l'": "nell'",
           "i": "nei", "gli": "negli", "le": "nelle"},
    "su": {"il": "sul", "lo": "sullo", "la": "sulla", "l'": "sull'",
           "i": "sui", "gli": "sugli", "le": "sulle"},
}


def preposizione_articolata(preposizione: str, articolo: str | None) -> str:
    """Fonde una preposizione semplice ("a", "da", "di", "in", "su") con
    l'articolo determinativo. `articolo=None` restituisce la preposizione
    semplice. Preposizione non supportata o articolo non in `ARTICOLI`:
    `ValueError` (mai una forma indovinata)."""
    tabella = _ARTICOLATE.get(preposizione)
    if tabella is None:
        raise ValueError(
            f"preposizione non supportata: {preposizione!r} "
            f"(attese: {', '.join(_ARTICOLATE)})"
        )
    if articolo is None:
        return preposizione
    forma = tabella.get(articolo)
    if forma is None:
        raise ValueError(
            f"articolo non valido: {articolo!r} (attesi: {', '.join(ARTICOLI)})"
        )
    return forma


def con_articolo(articolo: str | None, nome: str) -> str:
    """Articolo + nome, senza preposizione: "la Chiesa di San Michele in
    Foro", "l'Orto Botanico" (con "l'" nessuno spazio). `articolo=None`
    restituisce il nome invariato; articolo non in `ARTICOLI`: `ValueError`.
    Serve a frasi come "presso " + con_articolo(...)."""
    if articolo is None:
        return nome
    if articolo not in ARTICOLI:
        raise ValueError(
            f"articolo non valido: {articolo!r} (attesi: {', '.join(ARTICOLI)})"
        )
    if articolo.endswith("'"):
        return f"{articolo}{nome}"
    return f"{articolo} {nome}"


def con_luogo(preposizione: str, articolo: str | None, nome: str) -> str:
    """Preposizione + luogo: "alla Chiesa di San Michele in Foro",
    "all'Orto Botanico" (con "l'" nessuno spazio), "a Via Fillungo"
    (articolo `None`)."""
    prep = preposizione_articolata(preposizione, articolo)
    if prep.endswith("'"):
        return f"{prep}{nome}"
    return f"{prep} {nome}"
