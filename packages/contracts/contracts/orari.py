"""Codifica degli orari di apertura per Neo4j.

Neo4j non accetta liste di mappe come proprietà di un nodo: le fasce
settimanali (`FasciaApertura`) viaggiano come lista di stringhe, UNA per
fascia, nel formato `"g|HH:MM|HH:MM"`:

- `g` = giorno della settimana 0..6 (0 = lunedì, come `date.weekday()`);
- `HH:MM` ore a due cifre con zero iniziale, apertura poi chiusura;
- niente spazi, niente secondi. Esempio: `"0|10:00|18:00"`.

Questo è l'UNICO modulo che conosce il formato: chi scrive (export cypher) e
chi legge (loader, Neo4jCandidateSource) importa da qui.

`decodifica_fasce` è FAIL-CLOSED: una stringa malformata solleva `ValueError`
(citandola), MAI lista vuota o stringa saltata — perché una lista vuota
significa "nessun vincolo, sempre aperto" (`rientra_in_orario`) e un orario
guasto non deve mai diventarlo.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import time

from .models import FasciaApertura

__all__ = ["codifica_fasce", "decodifica_fasce"]

_ORA = r"(?:[01][0-9]|2[0-3]):[0-5][0-9]"
_FASCIA_RE = re.compile(rf"([0-6])\|({_ORA})\|({_ORA})", re.ASCII)


def _formatta(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _parse_ora(s: str) -> time:
    return time(int(s[0:2]), int(s[3:5]))


def codifica_fasce(fasce: Sequence[FasciaApertura]) -> list[str]:
    """Codifica le fasce in stringhe `"g|HH:MM|HH:MM"`, ordine preservato.

    Solleva `ValueError` se una fascia ha secondi/microsecondi o fuso: il
    formato non li rappresenta e troncarli cambierebbe in silenzio l'orario.
    """
    out: list[str] = []
    for f in fasce:
        for t in (f.apertura, f.chiusura):
            if t.second or t.microsecond or t.tzinfo is not None:
                raise ValueError(f"fascia non codificabile (solo HH:MM naive): {f!r}")
        out.append(f"{f.giorno_settimana}|{_formatta(f.apertura)}|{_formatta(f.chiusura)}")
    return out


def decodifica_fasce(valori: Sequence[str]) -> list[FasciaApertura]:
    """Decodifica stringhe `"g|HH:MM|HH:MM"` in `FasciaApertura` (fail-closed)."""
    fasce: list[FasciaApertura] = []
    for v in valori:
        if not isinstance(v, str):
            raise ValueError(f"fascia di apertura non è una stringa: {v!r}")
        m = _FASCIA_RE.fullmatch(v)
        if m is None:
            raise ValueError(
                f"fascia di apertura malformata: {v!r} (atteso 'g|HH:MM|HH:MM', "
                "g in 0..6, ore a due cifre, niente spazi né secondi)"
            )
        apertura, chiusura = _parse_ora(m.group(2)), _parse_ora(m.group(3))
        if chiusura <= apertura:
            raise ValueError(
                f"fascia di apertura incoerente: {v!r} (chiusura deve essere dopo apertura)"
            )
        fasce.append(
            FasciaApertura(giorno_settimana=int(m.group(1)), apertura=apertura, chiusura=chiusura)
        )
    return fasce
