# -*- coding: utf-8 -*-
"""Reproducibly (re)build the bundled chart font: fetch the Assistant variable font (SIL OFL 1.1) from the
Google Fonts repo and cut static Regular(400)/Bold(700) instances into `nl2sql_roadsafety/data/fonts/`.

    app\\.venv\\Scripts\\python nl2sql-accidents-plugin\\tools\\fetch_font.py

Needs network + fonttools (a matplotlib dependency, present in the app venv). Two traps this file records:
`instantiateVariableFont` does NOT mutate in place by default (pass inplace=True or you save the still-variable
source, which registers at its minimum weight), and matplotlib per-glyph fallback only works via the
`font.family` LIST (see charts._ensure_font) — Assistant lacks ← and Σ (≠ is native), DejaVu supplies those."""
from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/assistant/"
OUT = Path(__file__).resolve().parents[1] / "nl2sql_roadsafety" / "data" / "fonts"


def main() -> int:
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    OUT.mkdir(parents=True, exist_ok=True)
    var = OUT / "_assistant_var.ttf"
    urlretrieve(BASE + "Assistant%5Bwght%5D.ttf", var)
    urlretrieve(BASE + "OFL.txt", OUT / "OFL.txt")
    for wght, tag in ((400, "Regular"), (700, "Bold")):
        f = TTFont(var)
        instantiateVariableFont(f, {"wght": wght}, inplace=True, updateFontNames=True)
        assert "fvar" not in f and f["OS/2"].usWeightClass == wght
        f.save(OUT / f"Assistant-{tag}.ttf")
        print(f"Assistant-{tag}.ttf", (OUT / f"Assistant-{tag}.ttf").stat().st_size, "bytes")
    var.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
