"""Временная графика для спрайтов, которых ещё нет в assets.json.

Когда в assets.json появится спрайт с тем же id, заглушка не создаётся — игра сразу берёт настоящий.
Постройки и люди рисуются кодом в пиксельном стиле, новые роботы — перекрашенные Бублик и Клуша.
"""

import random

from PySide6.QtGui import QColor, QImage

from robofarm.assets import Sprite

OUTLINE = QColor("#2a1610")


# ---------------------------------------------------------------- рисование по пикселям

class Canvas:
    def __init__(self, w, h):
        self.img = QImage(w, h, QImage.Format.Format_ARGB32)
        self.img.fill(0)
        self.w, self.h = w, h

    def px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.setPixelColor(int(x), int(y), QColor(color))

    def rect(self, x, y, w, h, color):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.px(xx, yy, color)

    def hline(self, x0, x1, y, color):
        for x in range(int(x0), int(x1) + 1):
            self.px(x, y, color)

    def vline(self, x, y0, y1, color):
        for y in range(int(y0), int(y1) + 1):
            self.px(x, y, color)

    def text(self, glyphs, x, y, text, color):
        cx = x
        for ch in text.upper():
            rows = glyphs.get(ch) or glyphs.get(" ")
            if rows is None:
                cx += 4
                continue
            for gy, row in enumerate(rows):
                for gx, c in enumerate(row):
                    if c != ".":
                        self.px(cx + gx, y + gy, color)
            cx += len(rows[0]) + 1
        return cx - x

    def text_width(self, glyphs, text):
        return sum(len((glyphs.get(ch) or ["...."])[0]) + 1 for ch in text.upper()) - 1

    def outline(self, color=OUTLINE):
        src = self.img.copy()
        for y in range(self.h):
            for x in range(self.w):
                if src.pixelColor(x, y).alpha():
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < self.w and 0 <= yy < self.h and src.pixelColor(xx, yy).alpha() > 200:
                        self.img.setPixelColor(x, y, color)
                        break
        return self


def shade(color, k):
    c = QColor(color)
    return c.lighter(int(100 * k)) if k >= 1 else c.darker(int(100 / k))


def hue_shift(img, dh=0, ds=1.0, dv=1.0):
    out = img.copy()
    for y in range(out.height()):
        for x in range(out.width()):
            c = out.pixelColor(x, y)
            if not c.alpha():
                continue
            h, s, v, a = c.getHsv()
            h = (h + dh) % 360 if h >= 0 else h
            out.setPixelColor(x, y, QColor.fromHsv(h, max(0, min(255, int(s * ds))), max(0, min(255, int(v * dv))), a))
    return out


# ---------------------------------------------------------------- постройки

def building(glyphs, w, h, wall, roof, label, abandoned=False, doors="single", sign_color="#f8eed4", seed=1):
    rnd = random.Random(seed)
    c = Canvas(w, h)
    roof_h = h // 3
    body_y = roof_h
    # крыша: скаты с черепицей и свесом
    for y in range(roof_h):
        inset = max(0, (roof_h - y) // 2 - 1)
        row_col = shade(roof, 1.15) if y < roof_h // 2 else roof
        c.hline(2 + inset, w - 3 - inset, y + 1, row_col)
        if y % 3 == 0:
            for x in range(3 + inset + (y % 6), w - 3 - inset, 6):
                c.px(x, y + 1, shade(roof, 0.75))
    c.hline(1, w - 2, roof_h, shade(roof, 0.6))
    # стены с досками
    c.rect(3, body_y + 1, w - 6, h - body_y - 4, wall)
    for x in range(5, w - 4, 4):
        c.vline(x, body_y + 2, h - 5, shade(wall, 0.85))
    c.rect(3, body_y + 1, w - 6, 2, shade(wall, 0.55))  # тень под свесом крыши
    c.rect(2, h - 4, w - 4, 3, "#7a6866")                 # фундамент
    c.hline(2, w - 3, h - 4, "#b09d8e")
    # двери
    mid = w // 2
    if doors == "barn":
        dw, dh = w // 3, (h - body_y) * 2 // 3
        dx, dy = mid - dw // 2, h - 4 - dh
        c.rect(dx, dy, dw, dh, shade(wall, 0.7))
        for i in range(dh):
            c.px(dx + i * dw // dh, dy + i, "#e8d4a8")
            c.px(dx + dw - 1 - i * dw // dh, dy + i, "#e8d4a8")
        c.vline(mid, dy, dy + dh - 1, shade(wall, 0.5))
    else:
        c.rect(mid - 4, h - 16, 8, 12, "#5a3424")
        c.px(mid + 2, h - 10, "#fde07a")
    # окна
    for wx in (8, w - 16):
        c.rect(wx, body_y + 6, 8, 7, "#2f5d8a" if not abandoned else "#3a2a2a")
        c.hline(wx, wx + 7, body_y + 9, "#e8d4a8")
        c.vline(wx + 4, body_y + 6, body_y + 12, "#e8d4a8")
    # вывеска
    if label:
        tw = c.text_width(glyphs, label)
        sx = mid - tw // 2 - 3
        sy = body_y + 2 if doors == "barn" else body_y + 3
        if doors != "barn":
            sy = h - 26
        c.rect(sx, sy, tw + 6, 9, sign_color)
        c.text(glyphs, sx + 3, sy + 2, label, "#3d2318")
    if abandoned:
        for _ in range(w * h // 60):
            x, y = rnd.randrange(3, w - 3), rnd.randrange(2, h - 4)
            if c.img.pixelColor(x, y).alpha():
                c.px(x, y, shade(wall, 0.45))
    return c.outline().img


def stall(glyphs, abandoned=False):
    c = Canvas(80, 48)
    stripe = ["#c0392b", "#f8eed4"]
    for y in range(4, 14):
        for x in range(4, 76):
            c.px(x, y, stripe[(x // 6) % 2] if not abandoned else shade(stripe[(x // 6) % 2], 0.6))
    for x in range(4, 76, 6):
        c.rect(x, 14, 6, 2, stripe[(x // 6) % 2])
    for px in (6, 72):
        c.rect(px, 14, 3, 26, "#95603a")
    c.rect(4, 30, 72, 12, "#c48d52")
    c.hline(4, 75, 30, "#e0ad35")
    for x in range(8, 72, 8):
        c.vline(x, 31, 41, "#95603a")
    for i, col in enumerate(["#e89a45", "#d84b3a", "#7da43d", "#f2c94c"]):
        cx = 12 + i * 16
        c.rect(cx, 25, 10, 5, col)
        c.hline(cx + 1, cx + 8, 24, shade(col, 1.2))
    tw = c.text_width(glyphs, "ЛАВКА")
    c.rect(40 - tw // 2 - 3, 0, tw + 6, 9, "#f8eed4")
    c.text(glyphs, 40 - tw // 2, 2, "ЛАВКА", "#3d2318")
    c.rect(4, 42, 72, 3, "#5a3424")
    return c.outline().img


def tent():
    c = Canvas(96, 80)
    for y in range(8, 70):
        half = int((y - 8) * 0.7) + 4
        for x in range(48 - half, 48 + half):
            c.px(x, y, "#c0392b" if ((x - 48) // 7) % 2 else "#f8eed4")
    c.rect(44, 46, 8, 24, "#3d2318")
    c.vline(48, 0, 8, "#5a3424")
    c.rect(49, 0, 8, 5, "#f2c94c")
    return c.outline().img


def bunting():
    c = Canvas(48, 16)
    for x in range(48):
        c.px(x, 2 + abs(24 - x) // 8, "#5a3424")
    for i, col in enumerate(["#c0392b", "#f2c94c", "#2f78a8", "#7da43d", "#e89a45"]):
        x0 = 2 + i * 9
        y0 = 3 + abs(24 - x0) // 8
        for k in range(6):
            c.hline(x0 + k // 2, x0 + 6 - k // 2, y0 + k, col)
    return c.img


def arch(glyphs):
    c = Canvas(64, 48)
    for px in (4, 56):
        c.rect(px, 8, 4, 40, "#95603a")
    c.rect(2, 6, 60, 11, "#c0392b")
    tw = c.text_width(glyphs, "ЯРМАРКА")
    c.text(glyphs, 32 - tw // 2, 9, "ЯРМАРКА", "#f8eed4")
    return c.outline().img


def small_stall():
    c = Canvas(48, 32)
    for y in range(2, 9):
        for x in range(2, 46):
            c.px(x, y, "#2f78a8" if (x // 5) % 2 else "#f8eed4")
    for px in (3, 43):
        c.rect(px, 9, 2, 14, "#95603a")
    c.rect(2, 20, 44, 9, "#c48d52")
    c.hline(2, 45, 20, "#e0ad35")
    for i, col in enumerate(["#e89a45", "#7da43d", "#d84b3a"]):
        c.rect(8 + i * 12, 16, 8, 4, col)
    return c.outline().img


def sign(glyphs, text):
    c = Canvas(16, 32)
    c.rect(7, 12, 3, 20, "#95603a")
    tw = c.text_width(glyphs, text)
    c.rect(0, 4, 16, 9, "#c48d52")
    c.text(glyphs, 8 - tw // 2, 6, text, "#3d2318")
    return c.outline().img


def cabinet():
    c = Canvas(32, 32)
    c.rect(2, 4, 28, 26, "#95603a")
    for i in range(3):
        y = 7 + i * 8
        c.rect(5, y, 22, 6, "#c48d52")
        c.rect(13, y + 2, 6, 2, "#e8d4a8")
    c.rect(1, 2, 30, 3, "#643a2c")
    return c.outline().img


def desk():
    c = Canvas(32, 24)
    c.rect(1, 8, 30, 5, "#c48d52")
    c.hline(1, 30, 8, "#e0ad35")
    for px in (3, 27):
        c.rect(px, 13, 3, 10, "#95603a")
    c.rect(5, 4, 8, 4, "#f8eed4")
    c.rect(7, 2, 8, 4, "#e8d4a8")
    c.rect(22, 1, 2, 7, "#5a3424")
    c.rect(19, 0, 8, 3, "#f2c94c")
    return c.outline().img


def icon(kind):
    c = Canvas(16, 16)
    if kind.startswith("file_"):
        c.rect(3, 1, 10, 14, "#f8eed4")
        c.rect(10, 1, 3, 3, "#d8c8a8")
        if kind == "file_csv":
            for y in (5, 8, 11):
                c.hline(4, 11, y, "#7da43d")
            c.vline(7, 4, 12, "#7da43d")
        elif kind == "file_json":
            c.vline(5, 4, 12, "#2f78a8")
            c.vline(10, 4, 12, "#2f78a8")
            c.px(4, 8, "#2f78a8")
            c.px(11, 8, "#2f78a8")
        elif kind == "file_image":
            c.rect(4, 4, 8, 8, "#4cb4cf")
            c.hline(4, 11, 11, "#3f7a2e")
            c.px(6, 9, "#3f7a2e")
            c.px(7, 8, "#3f7a2e")
            c.px(9, 6, "#fde07a")
        else:
            for y in (5, 7, 9, 11):
                c.hline(5, 11, y, "#8a7a6a")
    elif kind.startswith("folder"):
        c.rect(1, 4, 6, 2, "#c48d52")
        c.rect(1, 5, 14, 9, "#e0ad35")
        c.hline(1, 14, 5, "#f2c94c")
    elif kind == "parcel":
        c.rect(2, 5, 12, 9, "#c48d52")
        c.vline(8, 5, 13, "#8a5a2a")
        c.hline(2, 13, 9, "#8a5a2a")
    elif kind.startswith("letter"):
        c.rect(1, 4, 14, 9, "#f8eed4")
        for i in range(6):
            c.px(1 + i, 4 + i, "#c48d52")
            c.px(14 - i, 4 + i, "#c48d52")
    elif kind == "receipt":
        c.rect(4, 1, 8, 14, "#f8eed4")
        for y in (4, 6, 8, 10):
            c.hline(5, 10, y, "#8a7a6a")
    else:
        c.rect(3, 3, 10, 10, "#c48d52")
    return c.outline().img


def price_tag_big():
    c = Canvas(32, 24)
    c.rect(1, 3, 30, 18, "#f8eed4")
    c.rect(1, 3, 30, 2, "#e8d4a8")
    c.rect(14, 0, 4, 4, "#95603a")
    return c.outline().img


# ---------------------------------------------------------------- люди

PERSON = [
    "......hhhh......",
    ".....hhhhhh.....",
    "....hhhhhhhh....",
    "....hssssssh....",
    "....sseesses....",
    "....ssssssss....",
    ".....ssmmss.....",
    "......ssss......",
    "....cccccccc....",
    "...cccccccccc...",
    "...cccccccccc...",
    "..scccccccccs...",
    "..scccccccccs...",
    "..sccccccccccs..",
    "...cccccccccc...",
    "...pppppppppp...",
    "....pppppppp....",
    "....ppp..ppp....",
    "....ppp..ppp....",
    "....ppp..ppp....",
    "....bbb..bbb....",
]


def person_frames(colors, step):
    frames = []
    for f in range(4 if step else 2):
        c = Canvas(16, 32)
        top = 10 + (1 if (not step and f == 1) else 0)
        for y, row in enumerate(PERSON):
            for x, ch in enumerate(row):
                if ch == ".":
                    continue
                if step and y >= 16:
                    if f in (1, 3) and x < 8 and y >= 17:
                        continue  # нога отстаёт — простая анимация ходьбы
                col = {"h": colors["hair"], "s": colors["skin"], "e": "#2a1610", "m": shade(colors["skin"], 0.8),
                       "c": colors["shirt"], "p": colors["pants"], "b": "#3d2318"}[ch]
                if ch == "c" and x in (3, 4):
                    col = shade(colors["shirt"], 0.8)
                c.px(x, top + y, col)
        if colors.get("hat"):
            c.rect(3, top - 1, 10, 2, colors["hat"])
            c.rect(5, top - 3, 6, 2, colors["hat"])
        frames.append(c.outline().img)
    return frames


PEOPLE = {
    "villager_1": {"hair": "#dcd8e6", "skin": "#f8d3ad", "shirt": "#8e3a6a", "pants": "#4b3a5a"},
    "villager_2": {"hair": "#3d2318", "skin": "#e0a874", "shirt": "#2f5d8a", "pants": "#3a3a4a"},
    "villager_3": {"hair": "#c0392b", "skin": "#f8d3ad", "shirt": "#7da43d", "pants": "#5a3424", "hat": "#d84b3a"},
    "villager_4": {"hair": "#e0ad35", "skin": "#f8d3ad", "shirt": "#e89a45", "pants": "#2f5d8a"},
    "mihalych": {"hair": "#b9c7d2", "skin": "#e4a481", "shirt": "#4b5a3a", "pants": "#3a3a4a", "hat": "#3a3a4a"},
    "valya": {"hair": "#c0392b", "skin": "#f8d3ad", "shirt": "#d84b3a", "pants": "#f8eed4", "hat": "#f2c94c"},
    "dasha": {"hair": "#5a3424", "skin": "#f8d3ad", "shirt": "#2f78a8", "pants": "#2a3760"},
    "petya": {"hair": "#e0ad35", "skin": "#f8d3ad", "shirt": "#7c8da6", "pants": "#3a3a4a"},
    "sidorov": {"hair": "#3d2318", "skin": "#e4a481", "shirt": "#6d6a7d", "pants": "#474257", "hat": "#474257"},
}

ROBOT_FALLBACK = {
    # робот: (основа, сдвиг оттенка, насыщенность, яркость, замены анимаций)
    "murzik": ("bublik", 190, 0.35, 1.05, {"serve": "harvest", "tag": "scan"}),
    "bobr": ("bublik", -12, 1.1, 0.8, {"stack": "harvest", "write": "scan"}),
    "iskra": ("bublik", 200, 1.0, 0.65, {"deliver": "harvest"}),
    "uhta": ("klusha", 30, 1.4, 0.95, {"fly": "walk", "read": "think", "stamp": "peck", "sort": "point"}),
}


def add_fallbacks(assets):
    glyphs = assets.fonts.get("tiny", {}).get("glyphs", {})
    made = []

    def put(sid, frames, anchor, frame_ms=0):
        if assets.get(sid):
            return
        w, h = frames[0].width(), frames[0].height()
        assets.sprites[sid] = Sprite(sid, (w, h), anchor, frames, frame_ms, True)
        made.append(sid)

    # постройки
    for tag, (w, h, wall, roof, label, doors) in {
        "barn": (112, 96, "#a8402c", "#4a2a2a", "АМБАР", "barn"),
        "post": (80, 64, "#3d5a8a", "#8e3a2a", "ПОЧТА", "single"),
    }.items():
        put(f"{tag}_repaired", [building(glyphs, w, h, wall, roof, label, doors=doors)], (w // 2, h - 1))
        put(f"{tag}_abandoned", [building(glyphs, w, h, shade(wall, 0.7), shade(roof, 0.8), label, True, doors, "#c8b898")],
            (w // 2, h - 1))
    for i, roof in enumerate(["#b2343a", "#3f7a2e", "#2f5d8a"], 1):
        put(f"village_house_{i}", [building(glyphs, 64, 64, "#e8c890", roof, "", seed=i)], (32, 63))
    put("stall_repaired", [stall(glyphs)], (40, 47))
    put("stall_abandoned", [stall(glyphs, True)], (40, 47))
    put("fair_tent", [tent()], (48, 79))
    put("fair_stall", [small_stall()], (24, 31))
    put("fair_bunting", [bunting()], (24, 15))
    put("fair_arch", [arch(glyphs)], (32, 47))
    put("field_sign", [sign(glyphs, "ПОЛЕ")], (8, 31))
    put("cabinet_files", [cabinet()], (16, 31))
    put("desk_office", [desk()], (16, 23))
    put("price_tag_big", [price_tag_big()], (16, 23))
    for kind in ("file_csv", "file_json", "file_txt", "file_py", "file_image", "folder_closed", "folder_open",
                 "parcel", "letter_closed", "letter_open", "receipt"):
        put(kind, [icon(kind)], (8, 15))

    # люди
    for pid, colors in PEOPLE.items():
        idle = person_frames(colors, False)
        walk = person_frames(colors, True)
        put(f"{pid}_idle_down", idle, (8, 31), 600)
        put(f"{pid}_idle_left", idle, (8, 31), 600)
        put(f"{pid}_walk_down", walk, (8, 31), 150)
        put(f"{pid}_walk_up", walk, (8, 31), 150)
        put(f"{pid}_walk_left", walk, (8, 31), 150)
        put(f"{pid}_walk_right", [f.mirrored(True, False) for f in walk], (8, 31), 150)
        put(f"{pid}_idle_right", [f.mirrored(True, False) for f in idle], (8, 31), 600)

    # роботы — перекрашенные Бублик и Клуша
    for rid, (base, dh, ds, dv, swaps) in ROBOT_FALLBACK.items():
        for sid, spr in list(assets.sprites.items()):
            if not sid.startswith(base + "_"):
                continue
            rest = sid[len(base) + 1:]
            frames = [hue_shift(f, dh, ds, dv) for f in spr.frames]
            put(f"{rid}_{rest}", frames, spr.anchor, spr.frame_ms)
            for new, old in swaps.items():
                if rest.startswith(old):
                    put(f"{rid}_{new}{rest[len(old):]}", frames, spr.anchor, spr.frame_ms)
    return made
