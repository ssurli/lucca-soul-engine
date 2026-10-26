"""Icone web dell'app: derivate dal logo delle Mura, rigenerabili, non quelle di Flutter."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "apps" / "lucca_soul_app" / "web"

ATTESE = {
    "favicon.png": 48,
    "icons/Icon-192.png": 192,
    "icons/Icon-512.png": 512,
    "icons/Icon-maskable-192.png": 192,
    "icons/Icon-maskable-512.png": 512,
}

# sha256 delle icone predefinite di Flutter (commit 75e2857).
PREDEFINITE_FLUTTER = {
    "favicon.png": "7ab2525f4b86b65d3e4c70358a17e5a1aaf6f437f99cbcc046dad73d59bb9015",
    "icons/Icon-192.png": "3dce99077602f70421c1c6b2a240bc9b83d64d86681d45f2154143310c980be3",
    "icons/Icon-512.png": "baccb205ae45f0b421be1657259b4943ac40c95094ab877f3bcbe12cd544dcbe",
    "icons/Icon-maskable-192.png": (
        "d2c842e22a9f4ec9d996b23373a905c88d9a203b220c5c151885ad621f974b5c"
    ),
    "icons/Icon-maskable-512.png": (
        "6aee06cdcab6b2aef74b1734c4778f4421d2da100b0ff9e52b21b55240202929"
    ),
}

SFONDO = (0x1F, 0x2A, 0x2E)


def _carica_script():
    percorso = RADICE / "scripts" / "genera_icone.py"
    spec = importlib.util.spec_from_file_location("genera_icone", percorso)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _leggi_png(path: Path) -> tuple[int, int, list[bytes]]:
    """Decoder minimo per i PNG RGB 8 bit senza filtri scritti dallo script."""
    dati = path.read_bytes()
    assert dati[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(dati):
        (n,) = struct.unpack(">I", dati[pos : pos + 4])
        tipo, corpo = dati[pos + 4 : pos + 8], dati[pos + 8 : pos + 8 + n]
        if tipo == b"IHDR":
            w, h, prof, colore = struct.unpack(">IIBB", corpo[:10])
            assert (prof, colore) == (8, 2)
        elif tipo == b"IDAT":
            idat += corpo
        pos += 12 + n
    raw = zlib.decompress(idat)
    riga = 1 + 3 * w
    righe = []
    for y in range(h):
        assert raw[y * riga] == 0
        righe.append(raw[y * riga + 1 : (y + 1) * riga])
    return w, h, righe


@pytest.mark.parametrize("nome,lato", ATTESE.items())
def test_dimensioni_e_sfondo(nome: str, lato: int) -> None:
    w, h, righe = _leggi_png(WEB / nome)
    assert (w, h) == (lato, lato)
    assert tuple(righe[0][0:3]) == SFONDO  # angolo: sfondo pieno #1F2A2E
    assert tuple(righe[-1][-3:]) == SFONDO
    pixel = [tuple(r[i : i + 3]) for r in righe for i in range(0, len(r), 3)]
    dominante = max(set(pixel), key=pixel.count)
    assert dominante == SFONDO


@pytest.mark.parametrize("nome", ATTESE)
def test_non_sono_le_icone_di_flutter(nome: str) -> None:
    assert hashlib.sha256((WEB / nome).read_bytes()).hexdigest() != PREDEFINITE_FLUTTER[nome]


@pytest.mark.parametrize("nome", ATTESE)
def test_nessun_mattone_nelle_icone(nome: str) -> None:
    """Il mattone #A4482A su #1F2A2E ha contrasto 2,48:1: non deve comparire."""
    _, _, righe = _leggi_png(WEB / nome)
    mattone = bytes((0xA4, 0x48, 0x2A))
    for r in righe:
        assert all(r[i : i + 3] != mattone for i in range(0, len(r), 3))


def test_maskable_logo_nella_zona_sicura() -> None:
    """Nelle maskable nessun pixel chiaro fuori dal cerchio centrale dell'80%."""
    for nome in ("icons/Icon-maskable-192.png", "icons/Icon-maskable-512.png"):
        w, _, righe = _leggi_png(WEB / nome)
        c, raggio = w / 2, 0.4 * w
        for y, r in enumerate(righe):
            for x in range(w):
                px = tuple(r[3 * x : 3 * x + 3])
                if px != SFONDO and ((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5 > raggio:
                    pytest.fail(f"{nome}: pixel {px} fuori dalla zona sicura in ({x},{y})")


def test_manifest() -> None:
    m = json.loads((WEB / "manifest.json").read_text(encoding="utf-8"))
    assert m["name"] == "Lucca Soul"
    assert m["short_name"] == "Lucca Soul"
    assert m["theme_color"].upper() == "#1F2A2E"
    assert m["background_color"].upper() == "#1F2A2E"
    icone = {(i["src"], i["sizes"], i.get("purpose", "any")) for i in m["icons"]}
    assert icone == {
        ("icons/Icon-192.png", "192x192", "any"),
        ("icons/Icon-512.png", "512x512", "any"),
        ("icons/Icon-maskable-192.png", "192x192", "maskable"),
        ("icons/Icon-maskable-512.png", "512x512", "maskable"),
    }


def test_index_punta_alle_icone_nuove() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'rel="apple-touch-icon"' in html and "icons/Icon-192.png" in html
    assert 'href="favicon.png"' in html
    assert 'name="theme-color" content="#1F2A2E"' in html


def test_rigenerando_si_ottengono_gli_stessi_pixel(tmp_path: Path) -> None:
    """Confronto sui pixel decodificati, non sui byte del file: la compressione
    zlib puo' differire tra versioni/build (zlib vs zlib-ng) a parita' di pixel."""
    mod = _carica_script()
    mod.genera(tmp_path)
    for nome in ATTESE:
        assert _leggi_png(tmp_path / nome) == _leggi_png(WEB / nome), nome


def test_lo_script_legge_il_json_del_logo() -> None:
    mod = _carica_script()
    atteso = RADICE / "apps" / "lucca_soul_app" / "assets" / "brand" / "mura_punti.json"
    assert mod.JSON_PUNTI == atteso
    punti = mod.carica_punti()
    assert sum(1 for p in punti if p["tipo"] == "baluardo") == 10
    assert sum(1 for p in punti if p["tipo"] == "piattaforma") == 1
