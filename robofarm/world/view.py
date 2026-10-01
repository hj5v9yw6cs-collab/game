"""Отрисовка пиксельного мира фермы."""

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal, QElapsedTimer
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPen,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QWidget

from robofarm.farm import bed_sprite, player_view
from robofarm.world.entities import PEOPLE_SPRITES, Particles, Robot
from robofarm.world.map import H, TILE, W, autotile_name, build_map

SHADOW_K, SHADOW_SQUASH, SHADOW_OPACITY = 0.55, 0.38, 0.34
UI_SCALE = 2


def silhouette(img, color=QColor(38, 14, 44)):
    sil = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    sil.fill(0)
    p = QPainter(sil)
    p.drawImage(0, 0, img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(sil.rect(), color)
    p.end()
    return sil


def draw_nine(p, assets, nine_id, rect, scale=UI_SCALE):
    """Рисует 9-slice из ассетов в прямоугольник rect (логические пиксели экрана)."""
    n = assets.nine[nine_id]
    src = assets[n["sprite"]].frame()
    l, t, r, b = n["slice"]
    sw, sh = src.width(), src.height()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    L, T, R, B = l * scale, t * scale, r * scale, b * scale
    cols = [(0, l, x, L), (l, sw - l - r, x + L, w - L - R), (sw - r, r, x + w - R, R)]
    rows = [(0, t, y, T), (t, sh - t - b, y + T, h - T - B), (sh - b, b, y + h - B, B)]
    for sy, shh, dy, dh in rows:
        for sx, sww, dx, dw in cols:
            if sww > 0 and shh > 0 and dw > 0 and dh > 0:
                p.drawImage(QRectF(dx, dy, dw, dh), src, QRectF(sx, sy, sww, shh))


class WorldView(QWidget):
    robot_clicked = Signal(str)
    hover_changed = Signal(object)

    def __init__(self, assets, parent=None):
        super().__init__(parent)
        self.assets = assets
        self.map = build_map()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.zoom = 3
        self.cam = list(self.map.spots["camera_start"])
        self.cam_target = None
        self.t = 0.0
        self.flags = {"house_repaired": False, "shed_repaired": False, "shed_open": False}
        self.beds = {}
        self.robots = {}
        self.people = {}            # покупатели и соседи: имя -> Robot (та же механика ходьбы)
        self.price_tags = []        # ценники на прилавке лавки
        self.extra_labels = []      # дополнительные подписи рентгена: (x, y, текст)
        self.bed_view = player_view  # как грядка выглядит для программы (зависит от главы)
        self.active_robot = None
        self._fog_fading = None
        self.particles = Particles()
        self.xray = False
        self.hover = None
        self.hover_pos = QPoint()
        self._drag = None
        self._sil = {}
        self._ground = []
        self._shadow_static = None
        self._fog = []
        from robofarm.ui.fonts import ui_font
        from robofarm.ui.fonts import code_font
        self.font_ui = ui_font(16)
        self.font_ui_bold = ui_font(16, bold=True)
        self.font_code = code_font(2)
        self.font_code.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        self.font_code_small = code_font(1)
        self._build_static()
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    # ------------------------------------------------------------ состояние
    def add_robot(self, rid, x, y, facing="down", rest="idle"):
        r = Robot(rid, x, y, facing)
        r.rest_anim = rest
        r.anim = rest
        self.robots[rid] = r
        return r

    def set_beds(self, beds):
        self.beds = {b["name"]: dict(b) for b in beds}

    def set_chapter(self, number, animate=False):
        """Открывает зоны всех глав до number включительно; туман над новыми зонами рассеивается."""
        changed = False
        for z in self.map.zones:
            is_open = z.chapter <= number
            if z.open != is_open:
                z.open = is_open
                changed = True
        if changed:
            old = set(self._fog)
            self._build_fog()
            if animate:
                self._fog_fading = (sorted(old - set(self._fog)), self.t)

    def set_customers(self, queue):
        """Очередь у лавки: каждый покупатель — словарь из данных урока."""
        self.people = {}
        spots = self.map.spots["queue"]
        for i, c in enumerate(queue or []):
            name = c.get("name", f"покупатель {i + 1}")
            sprite = PEOPLE_SPRITES.get(name, f"villager_{i % 4 + 1}")
            x, y = spots[i] if i < len(spots) else (spots[-1][0] + (i - len(spots) + 1) * 16, spots[-1][1])
            person = Robot(sprite, x, y, "left")
            person.name = name
            person.data = c
            self.people[name] = person

    def serve_customer(self, name):
        """Покупатель уходит, остальные подходят ближе к прилавку."""
        person = self.people.get(name)
        if not person or person.hidden:
            return None
        ex, ey = self.map.spots["queue_exit"]
        person.walk_to(person.x, ey)
        person.walk_to(ex, ey)
        person.leaving = True
        spots = self.map.spots["queue"]
        waiting = [p for p in self.people.values() if not getattr(p, "leaving", False)]
        for i, p in enumerate(waiting):
            if i < len(spots):
                p.walk_to(*spots[i])
                p.play("idle", 0.01, facing="left")
        return person

    def bed_center(self, name):
        tx, ty = self.map.beds[name]
        return tx * TILE + 8, ty * TILE + 8

    def bed_stand_point(self, name):
        """Где встаёт робот, чтобы работать с грядкой: на бортике под ней."""
        tx, ty = self.map.beds[name]
        return tx * TILE + 22, ty * TILE + 15

    def set_flag(self, name, value=True):
        if self.flags.get(name) != value:
            self.flags[name] = value
            self._build_shadows()

    def center_on(self, x, y, smooth=True):
        if smooth:
            self.cam_target = [x, y]
        else:
            self.cam = [x, y]
            self.cam_target = None

    def map_px(self):
        return W * TILE, H * TILE

    # ------------------------------------------------------------ статические слои
    def _tile_frame(self, sid, i=0):
        spr = self.assets[sid]
        return spr.frames[i % len(spr.frames)]

    def _build_static(self):
        mw, mh = self.map_px()
        water = {xy for xy in self.map.water_tiles}
        self._ground = []
        for i in range(3):
            img = QImage(mw, mh, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(QColor("#000000"))
            p = QPainter(img)
            for y in range(H):
                for x in range(W):
                    p.drawImage(x * TILE, y * TILE, self._tile_frame(self.map.ground[y][x]))
            for sid, x, y in self.map.decals:
                p.drawImage(x * TILE, y * TILE, self._tile_frame(sid))
            for y in range(H):
                for x in range(W):
                    sid = self.map.overlay[y][x]
                    if sid:
                        p.drawImage(x * TILE, y * TILE, self._tile_frame(sid, i if (x, y) in water else 0))
            p.end()
            self._ground.append(img)
        self._build_fog()
        self._build_shadows()

    def _build_fog(self):
        """Туман над закрытыми зонами."""
        closed = [[False] * W for _ in range(H)]
        for z in self.map.zones:
            if not z.open:
                x0, y0, x1, y1 = z.rect
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        closed[y][x] = True
        for z in self.map.zones:
            if z.open:
                x0, y0, x1, y1 = z.rect
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        closed[y][x] = False
        self._fog = []
        for y in range(H):
            for x in range(W):
                if closed[y][x]:
                    name = autotile_name(closed, x, y, "fog_edge", outside=True)
                    if name.endswith("_c") or "inner" in name:
                        name = "fog_cloud"
                    self._fog.append((name, x, y))

    def _object_sprite(self, o):
        if o.tag == "house":
            return "house_grandma_repaired" if self.flags["house_repaired"] else "house_grandma_abandoned"
        if o.tag == "shed":
            return "shed_repaired" if self.flags["shed_repaired"] else "shed_abandoned"
        if o.tag in ("stall", "barn", "post"):
            return f"{o.tag}_repaired" if self.flags.get(f"{o.tag}_repaired") else f"{o.tag}_abandoned"
        if o.tag.startswith("decor:"):
            return o.sprite if self.flags.get(o.tag) else None
        return o.sprite

    def _silhouette(self, sid, frame_i, img):
        key = (sid, frame_i)
        if key not in self._sil:
            self._sil[key] = silhouette(img)
        return self._sil[key]

    def _cast(self, p, sid, frame_i, img, ax, ay, x, y):
        p.setTransform(QTransform(1, 0, -SHADOW_K, -SHADOW_SQUASH,
                                  x - ax + SHADOW_K * ay, y + SHADOW_SQUASH * ay), True)
        p.drawImage(0, 0, self._silhouette(sid, frame_i, img))

    def _build_shadows(self):
        mw, mh = self.map_px()
        layer = QImage(mw, mh, QImage.Format.Format_ARGB32_Premultiplied)
        layer.fill(0)
        p = QPainter(layer)
        for o in self.map.objects:
            if not o.shadow:
                continue
            sid = self._object_sprite(o)
            if not sid:
                continue
            spr = self.assets[sid]
            p.save()
            self._cast(p, sid, 0, spr.frames[0], spr.anchor[0], spr.anchor[1], o.x, o.y)
            p.restore()
        p.end()
        self._shadow_static = layer

    # ------------------------------------------------------------ время
    def _tick(self):
        dt = min(0.1, self.clock.restart() / 1000.0)
        self.t += dt
        for r in self.robots.values():
            r.update(dt)
        for person in self.people.values():
            person.update(dt)
            if getattr(person, "leaving", False) and not person.busy():
                person.hidden = True
        vx, vy, vw, vh = self._view_rect()
        self.particles.ambient(dt, (vx, vy, vw, vh))
        self.particles.update(dt)
        if self.cam_target:
            k = min(1.0, dt * 3.0)
            self.cam[0] += (self.cam_target[0] - self.cam[0]) * k
            self.cam[1] += (self.cam_target[1] - self.cam[1]) * k
            if abs(self.cam_target[0] - self.cam[0]) < 0.5 and abs(self.cam_target[1] - self.cam[1]) < 0.5:
                self.cam_target = None
        self.update()

    # ------------------------------------------------------------ камера
    def _view_rect(self):
        vw = max(1, math.ceil(self.width() / self.zoom))
        vh = max(1, math.ceil(self.height() / self.zoom))
        mw, mh = self.map_px()
        vx = int(round(self.cam[0] - vw / 2))
        vy = int(round(self.cam[1] - vh / 2))
        vx = (mw - vw) // 2 if vw >= mw else max(0, min(mw - vw, vx))
        vy = (mh - vh) // 2 if vh >= mh else max(0, min(mh - vh, vy))
        return vx, vy, vw, vh

    def screen_to_world(self, pos):
        vx, vy, _, _ = self._view_rect()
        return vx + pos.x() / self.zoom, vy + pos.y() / self.zoom

    def world_to_screen(self, x, y):
        vx, vy, _, _ = self._view_rect()
        return QPointF((x - vx) * self.zoom, (y - vy) * self.zoom)

    # ------------------------------------------------------------ отрисовка
    def paintEvent(self, event):
        vx, vy, vw, vh = self._view_rect()
        frame = QImage(vw, vh, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(frame)
        p.translate(-vx, -vy)
        ground = self._ground[int(self.t / 0.3) % 3]
        p.drawImage(QRect(vx, vy, vw, vh), ground, QRect(vx, vy, vw, vh))
        self._draw_beds_ground(p)
        p.setOpacity(SHADOW_OPACITY)
        p.drawImage(QRect(vx, vy, vw, vh), self._shadow_static, QRect(vx, vy, vw, vh))
        self._draw_dynamic_shadows(p)
        p.setOpacity(1.0)
        self._draw_sorted(p, (vx, vy, vw, vh))
        self._draw_particles(p)
        self._draw_fog(p, (vx, vy, vw, vh))
        self._draw_lighting(p, (vx, vy, vw, vh))
        p.end()

        sp = QPainter(self)
        sp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        sp.drawImage(QRect(0, 0, vw * self.zoom, vh * self.zoom), frame)
        self._draw_canopies(sp)
        self._draw_price_tags(sp)
        if self.xray:
            self._draw_xray(sp)
        if not self.xray:
            self._draw_bubbles(sp)
        self._draw_float_texts(sp)
        if self.hover and not self.xray:
            self._draw_hover(sp)
        sp.end()

    def _draw_beds_ground(self, p):
        for name, bed in self.beds.items():
            if name not in self.map.beds:
                continue
            tx, ty = self.map.beds[name]
            h = bed["humidity"]
            plot = "plot_wet" if h >= 40 else ("plot_cracked" if h < 15 else "plot_dry")
            p.drawImage(tx * TILE, ty * TILE, self.assets[plot].frame())

    def _draw_dynamic_shadows(self, p):
        for r in list(self.robots.values()) + list(self.people.values()):
            if r.hidden:
                continue
            sid = r.sprite_id(self.assets)
            spr = self.assets[sid]
            img = spr.frame(r.anim_t * 1000)
            p.save()
            self._cast(p, sid, spr.frames.index(img), img, spr.anchor[0], spr.anchor[1], r.x, r.y)
            p.restore()

    def _draw_sorted(self, p, view):
        vx, vy, vw, vh = view
        items = []
        t_ms = self.t * 1000
        for o in self.map.objects:
            sid = self._object_sprite(o)
            if not sid:
                continue
            spr = self.assets[sid]
            if o.x + spr.size[0] < vx or o.x - spr.size[0] > vx + vw or o.y - spr.size[1] > vy + vh or o.y + 8 < vy:
                continue
            items.append((o.y, 0, sid, o.x, o.y, t_ms + o.phase * 170))
        for name, bed in self.beds.items():
            sid = bed_sprite(bed)
            if sid and name in self.map.beds:
                tx, ty = self.map.beds[name]
                items.append((ty * TILE + 12, 1, sid, tx * TILE + 8, ty * TILE + 12, 0))
        for r in list(self.robots.values()) + list(self.people.values()):
            if not r.hidden:
                items.append((r.y, 2, r, r.x, r.y, 0))
        items.sort(key=lambda it: (it[0], it[1]))
        for _, kind, what, x, y, tm in items:
            if kind == 2:
                self._draw_robot(p, what)
                continue
            spr = self.assets[what]
            p.drawImage(int(x - spr.anchor[0]), int(y - spr.anchor[1]), spr.frame(tm))
        # значки над грядками
        blink = int(self.t * 2) % 2
        for name, bed in self.beds.items():
            if name not in self.map.beds:
                continue
            cx, cy = self.bed_center(name)
            icon = None
            if bed["humidity"] < 40 and bed["stage"] != "empty":
                icon = "overlay_need_water"
            elif bed["stage"] == "ripe":
                icon = "overlay_ripe"
            if icon:
                spr = self.assets[icon]
                p.drawImage(int(cx - 4), int(cy - 20 - blink), spr.frame(self.t * 1000))

    def _draw_robot(self, p, r):
        if r is self.robots.get(self.active_robot):
            ring = self.assets["fx_select_ring"]
            p.drawImage(int(r.x - ring.anchor[0]), int(r.y - ring.anchor[1]), ring.frame(self.t * 1000))
        sh = self.assets["shadow_s"]
        p.drawImage(int(r.x - sh.anchor[0]), int(r.y - sh.anchor[1]), sh.frame())
        sid = r.sprite_id(self.assets)
        spr = self.assets[sid]
        ms = r.anim_t * 1000 if r.anim != "idle" else self.t * 1000
        p.drawImage(int(r.x - spr.anchor[0]), int(r.y - spr.anchor[1]), spr.frame(ms))
        if r.anim == "water":
            stream = self.assets["fx_water_stream"]
            left = r.facing != "right"
            ax = (r.x - spr.anchor[0] + 5) if left else (r.x - spr.anchor[0] + 10)
            ay = r.y - spr.anchor[1] + 3
            img = stream.frame(r.anim_t * 1000)
            if not left:
                img = img.mirrored(True, False)
            sx = ax - (stream.anchor[0] if left else stream.size[0] - 1 - stream.anchor[0])
            p.drawImage(int(sx), int(ay - stream.anchor[1]), img)
        if r.emote:
            e = self.assets[r.emote[0]]
            bob = int(math.sin(self.t * 6) * 1)
            p.drawImage(int(r.x - e.anchor[0]), int(r.y - 18 - e.size[1] + bob), e.frame())

    def _draw_particles(self, p):
        for pt in self.particles.items:
            if pt.kind == "text":
                continue
            spr = self.assets.get(pt.sprite)
            if not spr:
                continue
            fade = 1.0 if pt.kind == "fx" else min(1.0, pt.age * 2, (pt.life - pt.age) * 2)
            p.setOpacity(max(0.0, fade) * (0.8 if pt.kind == "mote" else 1.0))
            p.drawImage(int(pt.x - spr.anchor[0]), int(pt.y - spr.anchor[1]), spr.frame(pt.age * 1000))
        p.setOpacity(1.0)

    def _draw_fog(self, p, view):
        vx, vy, vw, vh = view
        t_ms = self.t * 1000
        layers = [(self._fog, 1.0)]
        if self._fog_fading:
            tiles, t0 = self._fog_fading
            k = (self.t - t0) / 2.5
            if k >= 1:
                self._fog_fading = None
            else:
                layers.append((tiles, 1.0 - k))
        for tiles, alpha in layers:
            p.setOpacity(alpha)
            for sid, x, y in tiles:
                px, py = x * TILE, y * TILE
                if px + TILE < vx or px > vx + vw or py + TILE < vy or py > vy + vh:
                    continue
                p.drawImage(px, py - (1 - alpha) * 10, self.assets[sid].frame(t_ms + (x * 7 + y * 13) * 50))
        p.setOpacity(1.0)

    def _draw_lighting(self, p, view):
        vx, vy, vw, vh = view
        rect = QRectF(vx, vy, vw, vh)
        # тени облаков медленно плывут по земле
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        mw, mh = self.map_px()
        for i, (ox, oy, rx) in enumerate([(0.2, 0.3, 140), (0.7, 0.65, 170)]):
            cx = (ox * mw + self.t * 6) % (mw + 400) - 200
            cy = oy * mh + math.sin(self.t * 0.05 + i) * 30
            g = QRadialGradient(QPointF(cx, cy), rx)
            g.setColorAt(0.0, QColor(150, 140, 205))
            g.setColorAt(1.0, QColor(255, 255, 255))
            p.save()
            p.translate(cx, cy)
            p.scale(1.0, 0.55)
            p.translate(-cx, -cy)
            p.setBrush(g)
            p.setPen(Qt.PenStyle.NoPen)
            p.setOpacity(0.35)
            p.drawEllipse(QPointF(cx, cy), rx, rx)
            p.restore()
        p.setOpacity(1.0)
        # тёплый свет «золотого часа»: сверху-слева тёплый, снизу-справа холоднее
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SoftLight)
        g = QLinearGradient(vx, vy, vx + vw, vy + vh)
        g.setColorAt(0.0, QColor(255, 200, 120, 150))
        g.setColorAt(0.6, QColor(255, 160, 100, 60))
        g.setColorAt(1.0, QColor(90, 70, 160, 110))
        p.fillRect(rect, g)
        # мягкая виньетка
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        v = QRadialGradient(QPointF(vx + vw * 0.5, vy + vh * 0.48), max(vw, vh) * 0.72)
        v.setColorAt(0.6, QColor(255, 255, 255))
        v.setColorAt(1.0, QColor(150, 105, 125))
        p.fillRect(rect, v)
        # свечение фонарей, свечей и окон
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        flicker = 0.85 + 0.15 * math.sin(self.t * 7.3)
        p.setOpacity(0.55 * flicker)
        for sid, x, y, strength, *tag in self.map.lights:
            if tag and not self.flags.get(tag[0]):
                continue
            spr = self.assets[sid]
            p.drawImage(int(x - spr.anchor[0]), int(y - 22 - spr.anchor[1]) if sid == "glow_lantern" else int(y - 6 - spr.anchor[1]), spr.frame())
        if self.flags["house_repaired"]:
            house = next(o for o in self.map.objects if o.tag == "house")
            spr = self.assets["house_grandma_repaired"]
            glow = self.assets["glow_window"]
            for gx, gy in self.assets.data_sprite("house_grandma_repaired").get("attach", {}).get("glow", []):
                p.drawImage(int(house.x - spr.anchor[0] + gx - glow.anchor[0]),
                            int(house.y - spr.anchor[1] + gy - glow.anchor[1]), glow.frame())
        p.setOpacity(1.0)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _draw_canopies(self, sp):
        """Кроны переднего плана по краям экрана — дают ощущение глубины."""
        z = self.zoom
        vx, vy, _, _ = self._view_rect()
        sway = math.sin(self.t * 0.8) * 1.5
        left = self.assets["canopy_fg_left"].frame()
        right = self.assets["canopy_fg_right"].frame()
        par = (vy * 0.15) % 40
        sp.drawImage(QRectF(-10 * z + sway, (90 - par) * z, left.width() * z, left.height() * z), left)
        sp.drawImage(QRectF(self.width() - (right.width() - 10) * z - sway, (150 - par) * z,
                            right.width() * z, right.height() * z), right)

    # ------------------------------------------------------------ экранные слои
    def _draw_bubbles(self, sp):
        for r in self.robots.values():
            if not r.bubble or r.hidden:
                continue
            text = r.bubble[0]
            sp.setFont(self.font_ui)
            fm = sp.fontMetrics()
            lines = []
            for raw in text.split("\n")[:4]:
                lines.append(raw if fm.horizontalAdvance(raw) < 320 else fm.elidedText(raw, Qt.TextElideMode.ElideRight, 320))
            tw = max(fm.horizontalAdvance(line) for line in lines) + 28
            th = fm.height() * len(lines) + 18
            anchor = self.world_to_screen(r.x, r.y - 20)
            rect = QRectF(anchor.x() - tw / 2, anchor.y() - th - 10, tw, th)
            draw_nine(sp, self.assets, "ui_bubble_speech", rect)
            tail = self.assets["ui_bubble_speech_tail"].frame()
            sp.drawImage(QRectF(anchor.x() - tail.width(), rect.bottom() - 4, tail.width() * 2, tail.height() * 2), tail)
            sp.setPen(QColor(self.assets.colors["ui"]["text"]))
            for i, line in enumerate(lines):
                sp.drawText(QPointF(rect.x() + 14, rect.y() + 9 + fm.ascent() + i * fm.height()), line)

    def _draw_price_tags(self, sp):
        """Ценники, которые Мурзик повесил командой tag(): деревянные таблички слева от прилавка."""
        if not self.price_tags:
            return
        sx, sy = self.map.spots["stall"]
        anchor = self.world_to_screen(sx, sy - 52)
        sp.setFont(self.font_ui_bold)
        fm = sp.fontMetrics()
        tags = self.price_tags[-5:]
        y = anchor.y() - len(tags) * (fm.height() + 14)
        ui = self.assets.colors["ui"]
        for text in tags:
            text = fm.elidedText(text, Qt.TextElideMode.ElideRight, 320)
            w = fm.horizontalAdvance(text) + 28
            rect = QRectF(anchor.x() - w / 2, y, w, fm.height() + 10)
            draw_nine(sp, self.assets, "ui_tooltip", rect)
            sp.setPen(QColor(ui["text"]))
            sp.drawText(QPointF(rect.x() + 14, rect.y() + 5 + fm.ascent()), text)
            y += fm.height() + 14

    def _draw_float_texts(self, sp):
        sp.setFont(self.font_ui)
        for pt in self.particles.items:
            if pt.kind != "text":
                continue
            pos = self.world_to_screen(pt.x, pt.y)
            alpha = max(0, min(255, int(255 * (pt.life - pt.age) / 0.6)))
            sp.setPen(QColor(40, 20, 10, alpha))
            sp.drawText(pos + QPointF(2, 2), pt.sprite)
            sp.setPen(QColor(253, 224, 122, alpha))
            sp.drawText(pos, pt.sprite)

    def _xray_labels(self):
        labels = []
        for name, bed in self.beds.items():
            if name in self.map.beds:
                cx, cy = self.bed_center(name)
                view = self.bed_view(bed)
                items = [f'"{k}": {self._py(v)}' for k, v in view.items()]
                text = "{" + ",\n ".join(items) + "}"
                labels.append((cx, cy - 6, text))
        waiting = [p for p in self.people.values() if not p.hidden]
        if waiting:
            rows = []
            for person in waiting[:6]:
                data = getattr(person, "data", {}) or {}
                rows.append(" {" + ", ".join(f'"{k}": {self._py(v)}' for k, v in data.items()) + "}")
            if len(waiting) > 6:
                rows.append(f" ... ещё {len(waiting) - 6}")
            first = waiting[0]
            labels.append((first.x + 30, first.y - 26, "queue = [\n" + ",\n".join(rows) + "\n]"))
        for r in self.robots.values():
            if not r.hidden:
                labels.append((r.x, r.y - 16, f'робот = "{r.name}"'))
        labels += self.extra_labels
        return labels

    @staticmethod
    def _py(v):
        if isinstance(v, str):
            return f'"{v}"'
        return repr(v)

    def _draw_xray(self, sp):
        xr = self.assets.colors["xray"]
        sp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        sp.fillRect(self.rect(), QColor(xr["overlay"][:7]))
        sp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        grid = QColor(xr["grid"][:7])
        grid.setAlpha(60)
        sp.setPen(QPen(grid, 1))
        vx, vy, vw, vh = self._view_rect()
        z = self.zoom
        for x in range(-(vx % TILE), vw + TILE, TILE):
            sp.drawLine(x * z, 0, x * z, self.height())
        for y in range(-(vy % TILE), vh + TILE, TILE):
            sp.drawLine(0, y * z, self.width(), y * z)
        # строка сканирования
        scan_y = (self.t * 120) % max(1, self.height())
        scan = QColor(xr["label"][:7])
        scan.setAlpha(70)
        sp.fillRect(QRectF(0, scan_y, self.width(), 3), scan)
        sp.setFont(self.font_code_small)
        fm = sp.fontMetrics()
        line_col = QColor(xr["leader"][:7])
        for i, (x, y, text) in enumerate(self._xray_labels()):
            anchor = self.world_to_screen(x, y)
            lines = text.split("\n")
            tw = max(fm.horizontalAdvance(t) for t in lines) + 16
            th = fm.lineSpacing() * len(lines) + 8
            lx = anchor.x() - tw / 2
            ly = anchor.y() - th - 40
            sp.setPen(QPen(line_col, 2))
            sp.drawLine(QPointF(anchor.x(), anchor.y()), QPointF(anchor.x(), ly + th))
            box = QRectF(lx, ly, tw, th)
            bg = QColor(xr["label"][:7]) if len(xr["label"]) <= 7 else QColor(xr["label"][:7])
            sp.fillRect(box, QColor(15, 40, 80, 230))
            sp.setPen(QPen(QColor(xr["leader"][:7]), 2))
            sp.drawRect(box)
            sp.setPen(QColor(xr["labelText"][:7]))
            for j, t in enumerate(lines):
                sp.drawText(QPointF(lx + 8, ly + 4 + fm.ascent() + j * fm.lineSpacing()), t)

    def _draw_hover(self, sp):
        info = self.hover
        if not info:
            return
        sp.setFont(self.font_ui)
        fm = sp.fontMetrics()
        lines = [info["title"]] + info.get("lines", [])
        code = info.get("code")
        w = max(fm.horizontalAdvance(s) for s in lines) + 32
        sp.setFont(self.font_code)
        cfm = sp.fontMetrics()
        if code:
            w = max(w, cfm.horizontalAdvance(code) + 32)
        h = fm.height() * len(lines) + (cfm.height() + 14 if code else 0) + 22
        x = min(self.hover_pos.x() + 18, self.width() - w - 8)
        y = min(self.hover_pos.y() + 18, self.height() - h - 8)
        rect = QRectF(x, y, w, h)
        draw_nine(sp, self.assets, "ui_tooltip", rect)
        ui = self.assets.colors["ui"]
        sp.setFont(self.font_ui_bold)
        for i, s in enumerate(lines):
            if i == 1:
                sp.setFont(self.font_ui)
            sp.setPen(QColor(ui["text"]) if i == 0 else QColor(ui["textMuted"]))
            sp.drawText(QPointF(x + 16, y + 11 + fm.ascent() + i * fm.height()), s)
        if code:
            cy = y + 11 + fm.height() * len(lines) + 4
            sp.fillRect(QRectF(x + 12, cy, w - 24, cfm.height() + 6), QColor(self.assets.colors["syntax"]["background"]))
            sp.setFont(self.font_code)
            sp.setPen(QColor(self.assets.colors["syntax"]["robotCommand"]))
            sp.drawText(QPointF(x + 18, cy + 3 + cfm.ascent()), code)

    # ------------------------------------------------------------ мышь и клавиатура
    def _hit(self, wx, wy):
        for r in self.robots.values():
            if not r.hidden and abs(wx - r.x) <= 9 and r.y - 16 <= wy <= r.y + 2:
                return {"kind": "robot", "id": r.id, "title": f"{r.name} — робот",
                        "lines": ["Нажми, чтобы открыть его скрипт"]}
        for person in self.people.values():
            if not person.hidden and abs(wx - person.x) <= 7 and person.y - 26 <= wy <= person.y + 2:
                data = getattr(person, "data", {}) or {}
                lines = [f"{k}: {v}" for k, v in data.items() if k != "name"]
                return {"kind": "person", "id": person.name, "title": f"{person.name} — покупатель",
                        "lines": lines or ["Ждёт своей очереди"]}
        for name, (tx, ty) in self.map.beds.items():
            if tx * TILE <= wx < tx * TILE + TILE and ty * TILE <= wy < ty * TILE + TILE and name in self.beds:
                bed = self.beds[name]
                state = "спелая" if bed["stage"] == "ripe" else ("пустая" if bed["stage"] == "empty" else "растёт")
                return {"kind": "bed", "id": name, "title": f"Грядка «{name}»",
                        "lines": [f"Влажность: {bed['humidity']}%" + (" — пора полить" if bed["humidity"] < 40 else ""),
                                  f"Урожай: {state}"],
                        "code": f'"{name}"'}
        for o in self.map.objects:
            sid = self._object_sprite(o)
            if not o.info or not sid:
                continue
            spr = self.assets[sid]
            if o.x - spr.anchor[0] <= wx < o.x - spr.anchor[0] + spr.size[0] and o.y - spr.anchor[1] <= wy <= o.y:
                return {"kind": "object", "title": o.info["title"], "lines": [o.info["text"]]}
        return None

    def mousePressEvent(self, e):
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._drag = (e.position(), list(self.cam), False)

    def mouseMoveEvent(self, e):
        self.hover_pos = e.position().toPoint()
        if self._drag:
            start, cam, moved = self._drag
            d = e.position() - start
            if moved or abs(d.x()) + abs(d.y()) > 4:
                self._drag = (start, cam, True)
                self.cam = [cam[0] - d.x() / self.zoom, cam[1] - d.y() / self.zoom]
                self.cam_target = None
                self._clamp_cam()
        wx, wy = self.screen_to_world(e.position())
        hit = self._hit(wx, wy)
        if hit != self.hover:
            self.hover = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit and hit["kind"] == "robot" else Qt.CursorShape.ArrowCursor)
            self.hover_changed.emit(hit)

    def mouseReleaseEvent(self, e):
        if self._drag and not self._drag[2]:
            wx, wy = self.screen_to_world(e.position())
            hit = self._hit(wx, wy)
            if hit and hit["kind"] == "robot":
                self.robot_clicked.emit(hit["id"])
        self._drag = None

    def leaveEvent(self, e):
        self.hover = None

    def wheelEvent(self, e):
        steps = [2, 3, 4, 5]
        i = steps.index(self.zoom) if self.zoom in steps else 1
        i = max(0, min(len(steps) - 1, i + (1 if e.angleDelta().y() > 0 else -1)))
        self.zoom = steps[i]
        self._clamp_cam()

    def keyPressEvent(self, e):
        step = 24
        moves = {Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_A: (-step, 0), Qt.Key.Key_Right: (step, 0),
                 Qt.Key.Key_D: (step, 0), Qt.Key.Key_Up: (0, -step), Qt.Key.Key_W: (0, -step),
                 Qt.Key.Key_Down: (0, step), Qt.Key.Key_S: (0, step)}
        if e.key() in moves:
            dx, dy = moves[e.key()]
            self.cam[0] += dx
            self.cam[1] += dy
            self.cam_target = None
            self._clamp_cam()
        else:
            super().keyPressEvent(e)

    def _clamp_cam(self):
        mw, mh = self.map_px()
        self.cam[0] = max(0, min(mw, self.cam[0]))
        self.cam[1] = max(0, min(mh, self.cam[1]))
