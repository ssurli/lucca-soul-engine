"""Genera favicon e icone web dell'app dal logo delle Mura.

Legge la STESSA geometria del logo dell'app (`assets/brand/mura_punti.json`,
usata da `MuraLogo`) e la rasterizza con la sola libreria standard (nessuna
dipendenza: niente Pillow). Il risultato è deterministico: stessi byte a ogni
esecuzione.

Uso (dalla radice del repo):
    .venv\\Scripts\\python.exe scripts\\genera_icone.py [--out DIR]

Colori: sfondo #1F2A2E, punti #F6F2EA, anello di collegamento #6B7A80 (solo
elemento non testuale). Mai il mattone su #1F2A2E (contrasto 2,48:1).
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import zlib
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
APP = RADICE / "apps" / "lucca_soul_app"
JSON_PUNTI = APP / "assets" / "brand" / "mura_punti.json"

SFONDO = (0x1F, 0x2A, 0x2E)
PUNTI = (0xF6, 0xF2, 0xEA)
ANELLO = (0x6B, 0x7A, 0x80)

SS = 3  # supersampling lineare

# (file, lato in px, frazione del lato occupata dal quadrato del logo)
# Maskable: il quadrato del logo (e quindi i punti, 80% di esso) sta nella
# zona sicura centrale (~80%); lo sfondo è pieno su tutta l'icona.
ICONE = [
    ("favicon.png", 48, 0.92),
    ("icons/Icon-192.png", 192, 0.88),
    ("icons/Icon-512.png", 512, 0.88),
    ("icons/Icon-maskable-192.png", 192, 0.70),
    ("icons/Icon-maskable-512.png", 512, 0.70),
]


def carica_punti() -> list[dict]:
    dati = json.loads(JSON_PUNTI.read_text(encoding="utf-8"))
    punti = dati["punti"]
    assert len(punti) == 11, "attesi 10 baluardi + 1 piattaforma"
    return punti


class Tela:
    def __init__(self, lato: int) -> None:
        self.n = lato * SS
        self.px = [bytearray(bytes(SFONDO) * self.n) for _ in range(self.n)]

    def _riga(self, y: int, x0: float, x1: float, col: tuple[int, int, int], test) -> None:
        if y < 0 or y >= self.n:
            return
        a = max(0, math.ceil(x0))
        b = min(self.n - 1, math.floor(x1))
        riga = self.px[y]
        for x in range(a, b + 1):
            if test(x + 0.5, y + 0.5):
                riga[3 * x : 3 * x + 3] = bytes(col)

    def disco(self, cx: float, cy: float, r: float, col) -> None:
        for y in range(math.floor(cy - r), math.ceil(cy + r) + 1):
            dy = y + 0.5 - cy
            if abs(dy) > r:
                continue
            w = math.sqrt(r * r - dy * dy)
            self._riga(
                y, cx - w, cx + w, col, lambda px, py: (px - cx) ** 2 + (py - cy) ** 2 <= r * r
            )

    def anello(self, cx: float, cy: float, r: float, spessore: float, col) -> None:
        ro, ri = r + spessore / 2, max(0.0, r - spessore / 2)
        for y in range(math.floor(cy - ro), math.ceil(cy + ro) + 1):
            dy = y + 0.5 - cy
            if abs(dy) > ro:
                continue
            w = math.sqrt(ro * ro - dy * dy)
            self._riga(
                y,
                cx - w,
                cx + w,
                col,
                lambda px, py: ri * ri <= (px - cx) ** 2 + (py - cy) ** 2 <= ro * ro,
            )

    def segmento(self, a, b, spessore: float, col) -> None:
        """Capsula tra a e b (estremi tondi)."""
        h = spessore / 2
        (ax, ay), (bx, by) = a, b
        dx, dy = bx - ax, by - ay
        lung2 = dx * dx + dy * dy

        def vicino(px: float, py: float) -> bool:
            t = 0.0 if lung2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / lung2))
            qx, qy = ax + t * dx, ay + t * dy
            return (px - qx) ** 2 + (py - qy) ** 2 <= h * h

        for y in range(math.floor(min(ay, by) - h), math.ceil(max(ay, by) + h) + 1):
            py = y + 0.5
            # Intervallo in x: striscia infinita attorno al segmento, tagliata al
            # riquadro dei suoi estremi allargato di h (il test esatto è sopra).
            if abs(dy) < 1e-9:
                x0, x1 = min(ax, bx) - h, max(ax, bx) + h
            else:
                xc = ax + (py - ay) * dx / dy
                semi = h * math.hypot(dx, dy) / abs(dy)
                x0 = max(xc - semi, min(ax, bx) - h)
                x1 = min(xc + semi, max(ax, bx) + h)
            self._riga(y, x0, x1, col, vicino)

    def ridotta(self, lato: int) -> bytes:
        righe = []
        for y in range(lato):
            blocco = self.px[y * SS : (y + 1) * SS]
            out = bytearray()
            for x in range(lato):
                for c in range(3):
                    somma = 0
                    for r in blocco:
                        for k in range(SS):
                            somma += r[3 * (x * SS + k) + c]
                    out.append((somma + (SS * SS) // 2) // (SS * SS))
            righe.append(bytes(out))
        return b"".join(b"\x00" + r for r in righe)  # filtro 0 per riga


def disegna(punti: list[dict], lato: int, frazione: float) -> bytes:
    """Stessa geometria di `MuraLogo`: pad 10%, raggio lato/15, piattaforma 1,5x."""
    tela = Tela(lato)
    n = lato * SS
    quadrato = n * frazione
    origine = (n - quadrato) / 2
    pad = quadrato * 0.1
    area = quadrato - 2 * pad

    def pos(p: dict) -> tuple[float, float]:
        return (origine + pad + p["x"] * area, origine + pad + p["y"] * area)

    cx = sum(p["x"] for p in punti) / len(punti)
    cy = sum(p["y"] for p in punti) / len(punti)
    ordine = sorted(punti, key=lambda p: math.atan2(p["y"] - cy, p["x"] - cx))
    tratto = max(quadrato / 40, SS)
    for i, p in enumerate(ordine):
        tela.segmento(pos(p), pos(ordine[(i + 1) % len(ordine)]), tratto, ANELLO)

    raggio = quadrato / 15
    for p in punti:
        x, y = pos(p)
        if p["tipo"] == "piattaforma":
            tela.disco(x, y, raggio * 1.5, SFONDO)
            tela.anello(x, y, raggio * 1.5, max(quadrato / 30, 1.2 * SS), PUNTI)
        else:
            tela.disco(x, y, raggio, PUNTI)
    return tela.ridotta(lato)


def png(lato: int, dati_righe: bytes) -> bytes:
    def chunk(tipo: bytes, corpo: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(tipo + corpo))
        return struct.pack(">I", len(corpo)) + tipo + corpo + crc

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", lato, lato, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(dati_righe, 9))
        + chunk(b"IEND", b"")
    )


def genera(destinazione: Path) -> list[Path]:
    punti = carica_punti()
    scritti = []
    for nome, lato, frazione in ICONE:
        percorso = destinazione / nome
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(png(lato, disegna(punti, lato, frazione)))
        scritti.append(percorso)
    return scritti


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=APP / "web", help="cartella di destinazione")
    args = ap.parse_args()
    for p in genera(args.out):
        print(p)


if __name__ == "__main__":
    main()
