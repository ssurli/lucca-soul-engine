"""Regressione: `import urban_memory` NON deve precaricare i moduli CLI.

Se `urban_memory/__init__.py` importa (direttamente o indirettamente)
`verify`, `migrate`, `audit` o `link`, allora `python -m urban_memory.<cli>`
emette il RuntimeWarning di runpy ("found in sys.modules after import of
package ... prior to execution"). Il test NON esegue le CLI (toccherebbero
Neon/Aura): ispeziona `sys.modules` in un sottoprocesso pulito."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

_CLI = ("verify", "migrate", "audit", "link")

_CODICE = (
    "import sys, urban_memory\n"
    f"presenti = [m for m in {_CLI!r} if f'urban_memory.{{m}}' in sys.modules]\n"
    "print(','.join(presenti))\n"
)


@pytest.mark.parametrize("modulo", _CLI)
def test_import_pacchetto_non_precarica_cli(modulo: str) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in sys.path if p] + [env.get("PYTHONPATH", "")]
    )
    r = subprocess.run(
        [sys.executable, "-c", _CODICE],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    presenti = [x for x in r.stdout.strip().split(",") if x]
    assert modulo not in presenti, (
        f"urban_memory.{modulo} e' in sys.modules dopo `import urban_memory`: "
        f"runpy emetterebbe RuntimeWarning per `-m urban_memory.{modulo}`"
    )
