"""Окно «Память робота»: переменные нарисованы ящиками с табличками-именами."""

import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from robofarm.ui.fonts import code_font, ui_font
from robofarm.ui.pixel import draw_nine, draw_sprite

VALUE_COLORS = {"num": "#fde07a", "str": "#a8e08a", "other": "#f3e6cf"}


def value_text(s, limit=18):
    t = s["t"]
    if t == "num":
        return s["v"]
    if t == "str":
        v = s["v"]
        if len(v) > limit:
            v = v[: limit - 1] + "…"
        return f'"{v}"'
    if t == "bool":
        return "True" if s["v"] else "False"
    if t == "none":
        return "None"
    if t == "other":
        return s["v"][:limit]
    if t == "list":
        return f"[{s['len']}]"
    if t == "dict":
        return f"{{{s['len']}}}"
    return "?"


class MemoryView(QWidget):
    def __init__(self, assets, parent=None):
        super().__init__(parent)
        self.assets = assets
        self.vars = {}
        self.flash = {}  # имя -> время вспышки
        self.new = set()
        self.caption = ""
        self.font_val = code_font(2)
        self.font_name = ui_font(15, bold=True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(60)

    def set_vars(self, variables, changed=(), caption=""):
        now = time.monotonic()
        for name in changed:
            if name not in self.vars:
                self.new.add(name)
            self.flash[name] = now
        self.vars = dict(variables)
        self.caption = caption
        self.update()

    def clear(self):
        self.vars, self.flash, self.new, self.caption = {}, {}, set(), ""
        self.update()

    def sizeHint(self):
        return QSize(380, 260)

    # --- раскладка ---
    def _cell_size(self, p, s):
        p.setFont(self.font_val)
        fm = p.fontMetrics()
        if s["t"] == "list":
            items = s["items"][:6]
            w = sum(max(44, fm.horizontalAdvance(value_text(i, 8)) + 20) for i in items) + 8 * len(items) + 24
            if s["len"] > len(items):
                w += 70
            return max(120, w), 92
        if s["t"] == "dict":
            rows = s["items"][:5]
            w = max([fm.horizontalAdvance(f"{k} → {value_text(v, 12)}") for k, v in rows] + [120]) + 40
            return w, 46 + 30 * max(1, len(rows))
        txt = value_text(s)
        p.setFont(self._val_font(txt))
        w = p.fontMetrics().horizontalAdvance(txt) + 44
        if s["t"] in ("bool", "none"):
            w += 26
        return max(96, w), 84

    def paintEvent(self, e):
        p = QPainter(self)
        ui = self.assets.colors["ui"]
        if not self.vars:
            p.setFont(ui_font(16))
            p.setPen(QColor(ui["textMuted"]))
            p.drawText(QRectF(8, 8, self.width() - 16, self.height() - 16), Qt.TextFlag.TextWordWrap,
                       "Пока пусто. Когда в коде появится переменная (имя = значение), "
                       "здесь появится ящик с её именем и тем, что в нём лежит.")
            return
        x, y, row_h = 6, 6, 0
        now = time.monotonic()
        for name, s in self.vars.items():
            p.setFont(self.font_name)
            name_w = p.fontMetrics().horizontalAdvance(name) + 26
            w, h = self._cell_size(p, s)
            w = max(w, name_w + 10)
            if x + w > self.width() - 6 and x > 6:
                x, y = 6, y + row_h + 10
                row_h = 0
            self._draw_var(p, name, s, QRectF(x, y, w, h), now)
            x += w + 12
            row_h = max(row_h, h)
        if self.caption:
            p.setFont(ui_font(15))
            p.setPen(QColor(ui["textMuted"]))
            p.drawText(QPointF(8, self.height() - 8), self.caption)

    def _draw_var(self, p, name, s, rect, now):
        ui = self.assets.colors["ui"]
        p.setFont(self.font_name)
        fm = p.fontMetrics()
        plate = QRectF(rect.x() + 6, rect.y(), fm.horizontalAdvance(name) + 22, 28)
        body = QRectF(rect.x(), rect.y() + 22, rect.width(), rect.height() - 22)
        if s["t"] == "dict":
            draw_nine(p, self.assets, "mem_cabinet", body)
        elif s["t"] != "list":
            draw_nine(p, self.assets, "mem_crate", body)
        draw_nine(p, self.assets, "mem_plate", plate)
        p.setPen(QColor(ui["text"]))
        p.drawText(QPointF(plate.x() + 11, plate.y() + 14 + fm.ascent() / 2 - 2), name)
        p.setFont(self.font_val)
        vfm = p.fontMetrics()
        t = s["t"]
        if t == "list":
            cx = body.x() + 4
            for i, item in enumerate(s["items"][:6]):
                txt = value_text(item, 8)
                cw = max(44, vfm.horizontalAdvance(txt) + 20)
                cell = QRectF(cx, body.y() + 18, cw, body.height() - 20)
                draw_nine(p, self.assets, "mem_crate", cell)
                draw_sprite(p, self.assets, "mem_tag", cx + cw / 2 - 7, body.y() + 6)
                p.setFont(ui_font(12, bold=True))
                p.setPen(QColor(ui["text"]))
                p.drawText(QRectF(cx + cw / 2 - 7, body.y() + 6, 14, 10), Qt.AlignmentFlag.AlignCenter, str(i))
                p.setFont(self.font_val)
                self._value(p, item, txt, cell)
                cx += cw + 8
            if s["len"] > len(s["items"][:6]):
                p.setFont(ui_font(14))
                p.setPen(QColor(ui["textMuted"]))
                p.drawText(QPointF(cx + 2, body.center().y() + 10), f"…ещё {s['len'] - 6}")
            if not s["items"]:
                p.setFont(ui_font(14))
                p.setPen(QColor(ui["textMuted"]))
                p.drawText(QPointF(body.x() + 8, body.center().y() + 10), "пустой список []")
        elif t == "dict":
            for i, (k, v) in enumerate(s["items"][:5]):
                drawer = QRectF(body.x() + 10, body.y() + 12 + i * 30, body.width() - 20, 26)
                draw_nine(p, self.assets, "mem_drawer", drawer)
                p.setPen(QColor("#3d2318"))
                p.drawText(QPointF(drawer.x() + 10, drawer.y() + 13 + vfm.ascent() / 2 - 2), f"{k} →")
                kx = drawer.x() + 16 + vfm.horizontalAdvance(f"{k} →")
                p.setPen(QColor(VALUE_COLORS.get(v["t"], "#3d2318")).darker(180))
                p.drawText(QPointF(kx, drawer.y() + 13 + vfm.ascent() / 2 - 2), value_text(v, 12))
        else:
            self._value(p, s, value_text(s), body)
        # вспышка: значение изменилось
        since = now - self.flash.get(name, -10)
        if since < 0.6:
            frame_ms = since * 1000
            sid = "fx_pop" if name in self.new else "fx_mem_flash"
            draw_sprite(p, self.assets, sid, plate.right() - 6, plate.y() - 10, t_ms=frame_ms)
        elif name in self.new:
            self.new.discard(name)

    def _val_font(self, txt):
        return code_font(3) if len(txt) <= 6 else code_font(2)

    def _value(self, p, s, txt, cell):
        t = s["t"]
        p.setFont(self._val_font(txt) if cell.height() > 50 else code_font(2))
        tw = p.fontMetrics().horizontalAdvance(txt) + (22 if t in ("bool", "none") else 0)
        cx = cell.center().x() - tw / 2
        cy = cell.center().y()
        if t == "bool":
            draw_sprite(p, self.assets, "mem_bulb_on" if s["v"] else "mem_bulb_off", cx - 4, cy - 12)
            cx += 22
        elif t == "none":
            draw_sprite(p, self.assets, "mem_cobweb", cx - 6, cy - 10)
            cx += 22
        fm = p.fontMetrics()
        p.setPen(QColor(0, 0, 0, 150))
        p.drawText(QPointF(cx + 2, cy + fm.ascent() / 2 - 1), txt)
        p.setPen(QColor(VALUE_COLORS.get(t, "#f3e6cf")))
        p.drawText(QPointF(cx, cy + fm.ascent() / 2 - 3), txt)
