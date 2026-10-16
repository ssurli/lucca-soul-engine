"""Testo di attribuzione ("Offerta da ...") — UN SOLO punto di costruzione.

Condiviso da `SeedCandidateSource` e `Neo4jCandidateSource`, così le due
sorgenti non possono divergere. Fatto commerciale trasparente, mai punteggio.
Una bottega dimostrativa (`fittizio=True`) lo dichiara apertamente.
"""

from __future__ import annotations


def testo_attribuzione(nome: str, mestiere: str, fittizio: bool) -> str:
    """Se il nome contiene già il mestiere (confronto casefold) la clausola
    ", bottega di {mestiere}" è omessa: sarebbe tautologica ("Pasticceria,
    bottega di pasticceria")."""
    suffisso = " (esempio dimostrativo)" if fittizio else ""
    if mestiere.casefold() in nome.casefold():
        return f"Offerta da {nome}{suffisso}."
    return f"Offerta da {nome}, bottega di {mestiere}{suffisso}."
