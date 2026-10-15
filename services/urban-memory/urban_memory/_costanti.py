"""Costanti condivise tra sottomoduli CLI di `urban_memory`.

Modulo neutro: non importa nessun altro sottomodulo, così `verify` e `link`
(entrambi eseguibili con `python -m`) non si importano a vicenda e il
pacchetto non pre-carica i moduli che l'utente sta per eseguire.
"""

from __future__ import annotations

CONTRIBUTO_ID = "mem-verify-persistenza"
