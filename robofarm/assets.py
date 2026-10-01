"""Загрузка пиксельной графики из assets.json (палитра + спрайты-строки) в QImage."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QColor, QImage

DATA_DIR = Path(__file__).parent / "data"


def parse_hex(value):
    """'#rrggbb' или '#rrggbbaa' → (r, g, b, a)."""
    v = value.lstrip("#")
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    a = int(v[6:8], 16) if len(v) == 8 else 255
    return r, g, b, a


@dataclass
class Sprite:
    id: str
    size: tuple
    anchor: tuple
    frames: list = field(default_factory=list)
    frame_ms: int = 0
    loop: bool = True

    def frame(self, t_ms=0):
        if len(self.frames) == 1 or not self.frame_ms:
            return self.frames[0]
        i = int(t_ms // self.frame_ms)
        i = i % len(self.frames) if self.loop else min(i, len(self.frames) - 1)
        return self.frames[i]


class Assets:
    def __init__(self, path=DATA_DIR / "assets.json", palette_override=None):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.meta = self.data["meta"]
        transparent = self.meta.get("transparentKey", ".")
        self.palette = {p["key"]: parse_hex(p["hex"]) for p in self.data["palette"]}
        self.palette_names = {p["name"]: p["key"] for p in self.data["palette"]}
        for name, hex_value in (palette_override or {}).items():
            self.palette[self.palette_names.get(name, name)] = parse_hex(hex_value)
        lut = {key: bytes((b, g, r, a)) for key, (r, g, b, a) in self.palette.items()}
        lut[transparent] = b"\x00\x00\x00\x00"

        raw = {s["id"]: s for s in self.data["sprites"]}
        self.raw = raw
        self.sprites = {}
        for sid, s in raw.items():
            if s.get("frames"):
                self.sprites[sid] = self._build(s, s["frames"], lut)
        for sid, s in raw.items():
            if s.get("mirrorOf"):
                src = self.sprites[s["mirrorOf"]]
                frames = [img.mirrored(True, False) for img in src.frames]
                self.sprites[sid] = Sprite(sid, tuple(s["size"]), tuple(s.get("anchor", src.anchor)),
                                           frames, s.get("frameMs", src.frame_ms), s.get("loop", src.loop))
        self.nine = {n["id"]: n for n in self.data.get("nineSlices", [])}
        self.autotiles = {a["id"]: a["tiles"] for a in self.data.get("autotiles", [])}
        self.colors = self.data.get("colors", {})
        self.fonts = self.data.get("fonts", {})

    @staticmethod
    def _build(s, frames, lut):
        w, h = s["size"]
        images = []
        for rows in frames:
            buf = b"".join(lut[ch] for row in rows for ch in row)
            images.append(QImage(buf, w, h, w * 4, QImage.Format.Format_ARGB32).copy())
        return Sprite(s["id"], (w, h), tuple(s.get("anchor", (w // 2, h - 1))), images,
                      s.get("frameMs", 0) or 0, s.get("loop", True))

    def __getitem__(self, sid):
        return self.sprites[sid]

    def get(self, sid):
        return self.sprites.get(sid)

    def data_sprite(self, sid):
        """Исходное описание спрайта из JSON (точки крепления attach, заметки)."""
        return self.raw.get(sid, {})

    def color(self, name):
        r, g, b, a = self.palette[self.palette_names.get(name, name)]
        return QColor(r, g, b, a)
