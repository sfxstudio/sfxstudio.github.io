#!/usr/bin/env python3
"""Atmospheric section backgrounds for the «О студии» page.

    python3 tools/atmo.py

Originals live in assets/img/atmo/src/ untouched. For the page we ship the same
pictures pre-blurred (cheaper than a live CSS blur on phones): 1600px for
desktop, 800px for phones. Only blur and resize are applied — no recolouring;
dimming and tint are done with CSS overlays per section.
"""
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets/img/atmo/src"
OUT = ROOT / "assets/img/atmo"

# key: blur radius at 1600px (≈ CSS blur in px at that width)
ITEMS = {"winter": 6, "water": 5, "pyro": 6, "special": 5.5}


def main():
    for key, radius in ITEMS.items():
        im = Image.open(SRC / f"{key}.png").convert("RGB")
        for w, r in ((1600, radius), (800, radius * 0.6)):
            h = round(im.height * w / im.width)
            out = im.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(r))
            out.save(OUT / f"{key}-{w}.webp", "WEBP", quality=72, method=6)
        print(key, im.size)


if __name__ == "__main__":
    main()
