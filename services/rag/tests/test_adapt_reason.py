"""Regressione: `adapt_reason` non deve mai abbassare il case del motivo
(spesso una connessione del grafo che inizia con un nome proprio)."""

from __future__ import annotations

from rag.reasons import adapt_reason


def test_nome_proprio_conserva_la_maiuscola() -> None:
    out = adapt_reason("Luigi Boccherini è legato a questo luogo", "la pioggia")
    assert out == "Sostituita per la pioggia. Luigi Boccherini è legato a questo luogo."
    assert "luigi" not in out


def test_motivo_minuscolo_diventa_inizio_frase() -> None:
    out = adapt_reason("qui si respira la tradizione liutaia", "l'affollamento sulle Mura")
    assert out == (
        "Sostituita per l'affollamento sulle Mura. Qui si respira la tradizione liutaia."
    )


def test_motivo_vuoto() -> None:
    assert adapt_reason("  ", "la pioggia") == "Sostituita per la pioggia."


def test_segnale_vuoto() -> None:
    assert adapt_reason("Evoca il tema del mare.", "") == "Sostituita. Evoca il tema del mare."
