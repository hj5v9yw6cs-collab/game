"""Собирает TTF-шрифт «Klusha Mono» из битмап-глифов в assets.json.

    python3 tools/build_font.py

Каждый пиксель глифа — квадрат 100×100 единиц, поэтому при размере 12 px (или 24, 36…)
шрифт ложится ровно на пиксельную сетку.
"""

import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "robofarm" / "data" / "assets.json"
OUT = ROOT / "robofarm" / "data" / "fonts" / "KlushaMono.ttf"
PX = 100


def glyph_from_rows(rows, baseline):
    pen = TTGlyphPen(None)
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == ".":
                x += 1
                continue
            start = x
            while x < len(row) and row[x] != ".":
                x += 1
            top = (baseline - y) * PX
            bottom = top - PX
            # контур по часовой стрелке (TrueType)
            pen.moveTo((start * PX, bottom))
            pen.lineTo((start * PX, top))
            pen.lineTo((x * PX, top))
            pen.lineTo((x * PX, bottom))
            pen.closePath()
    return pen.glyph()


def build():
    data = json.loads(ASSETS.read_text(encoding="utf-8"))
    font = data["fonts"]["code"]
    glyphs = font["glyphs"]
    cell_w, cell_h = font["cell"]
    baseline = font["baseline"] + 1  # строки 0..baseline стоят над базовой линией
    advance = font["advance"] * PX

    names = [".notdef"]
    cmap, outlines, metrics = {}, {}, {}
    empty = TTGlyphPen(None).glyph()
    outlines[".notdef"] = glyph_from_rows(["KKKKK", "K...K", "K...K", "K...K", "K...K", "K...K", "KKKKK"], 7)
    metrics[".notdef"] = (advance, 0)
    for ch, rows in sorted(glyphs.items()):
        name = f"uni{ord(ch):04X}"
        names.append(name)
        cmap[ord(ch)] = name
        outlines[name] = glyph_from_rows(rows, baseline) if any("K" in r for r in rows) else empty
        metrics[name] = (advance, 0)
    if 0xA0 not in cmap and " " in glyphs:
        cmap[0xA0] = cmap[ord(" ")]

    fb = FontBuilder(cell_h * PX, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics(metrics)
    ascent, descent = baseline * PX, (cell_h - baseline) * PX
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)
    fb.setupNameTable({"familyName": "Klusha Mono", "styleName": "Regular",
                       "uniqueFontIdentifier": "Robofarm:KlushaMono", "fullName": "Klusha Mono",
                       "version": "Version 1.0", "psName": "KlushaMono-Regular",
                       "licenseDescription": "CC0 — шрифт игры «Робоферма»"})
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent, sTypoLineGap=0,
                usWinAscent=ascent, usWinDescent=descent)
    fb.setupPost(isFixedPitch=1)
    fb.save(OUT)
    print(f"saved {OUT} ({len(names) - 1} glyphs)")


if __name__ == "__main__":
    build()
