"""Собирает тестовую сцену фермы из assets.json и сохраняет PNG.

    python3 tools/render_scene.py raw   out.png   # графика как есть
    python3 tools/render_scene.py cozy  out.png   # тёплая палитра + свет + атмосфера
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QRadialGradient, QLinearGradient

from robofarm.assets import Assets

COZY_PALETTE = {
    # трава: сочнее и теплее, тени уходят в бирюзу, света — в жёлтый
    "grass_0": "#253d2b", "grass_1": "#3d6430", "grass_2": "#6a8a34", "grass_3": "#a5a743", "grass_4": "#dcc25f",
    # камень: тёплый серо-бежевый вместо лавандово-серого
    "stone_0": "#4a3b3d", "stone_1": "#7a6866", "stone_2": "#b09d8e",
    # вода: живее
    "water_0": "#1f3f6e", "water_1": "#2f78a8", "water_2": "#4cb4cf", "water_3": "#aef0e0",
    # сталь (крыши, металл): теплее
    "steel_0": "#2c2f4a", "steel_1": "#4b5a86", "steel_2": "#7d95c0", "steel_3": "#c4d4e6",
    # контуры: теплее и чуть светлее
    "outline_deep": "#2a1519", "outline_warm": "#45242a", "outline_soft": "#6a3a40",
}

# осенняя земля как в референсе: трава выгорела до охры и рыжего
AUTUMN_GROUND = {
    "grass_0": "#6b3020", "grass_1": "#a5522a", "grass_2": "#cf7433", "grass_3": "#e89a45", "grass_4": "#f6c56e",
}

TILE = 16
W, H = 30, 17


def autotile(mask, x, y, kind):
    """Выбор тайла автотайла по 4 соседям и диагоналям."""
    def m(dx, dy):
        xx, yy = x + dx, y + dy
        return 0 <= xx < W and 0 <= yy < H and mask[yy][xx]
    n, s, e, w = m(0, -1), m(0, 1), m(1, 0), m(-1, 0)
    if not n and not w: return f"{kind}_nw"
    if not n and not e: return f"{kind}_ne"
    if not s and not w: return f"{kind}_sw"
    if not s and not e: return f"{kind}_se"
    if not n: return f"{kind}_n"
    if not s: return f"{kind}_s"
    if not w: return f"{kind}_w"
    if not e: return f"{kind}_e"
    if not m(1, -1): return f"{kind}_inner_ne"
    if not m(-1, -1): return f"{kind}_inner_nw"
    if not m(1, 1): return f"{kind}_inner_se"
    if not m(-1, 1): return f"{kind}_inner_sw"
    return f"{kind}_c"


def render(mode, out):
    cozy = mode == "cozy"
    assets = Assets(palette_override=COZY_PALETTE if cozy else None)
    ground = Assets(palette_override={**COZY_PALETTE, **AUTUMN_GROUND}) if cozy else assets
    rnd = random.Random(7)
    img = QImage(W * TILE, H * TILE, QImage.Format.Format_ARGB32)
    img.fill(QColor("#000000"))
    p = QPainter(img)

    def draw(sid, x, y, t=0, src=None):
        """x, y — точка опоры (anchor) в пикселях мира."""
        spr = (src or assets)[sid]
        p.drawImage(int(x - spr.anchor[0]), int(y - spr.anchor[1]), spr.frame(t))

    # --- земля ---
    grass = ["grass_1", "grass_2", "grass_3", "grass_4"]
    for y in range(H):
        for x in range(W):
            r = rnd.random()
            sid = rnd.choice(grass)
            if cozy:
                sid = "grass_1" if rnd.random() < 0.55 else rnd.choice(grass)
            if r < (0.12 if cozy else 0.08):
                sid = rnd.choice(["grass_leaves_1", "grass_leaves_2", "grass_leaves_3"])
            elif r < (0.15 if cozy else 0.11):
                sid = rnd.choice(["grass_flowers_1", "grass_flowers_2"])
            spr = ground[sid]
            p.drawImage(x * TILE, y * TILE, spr.frame())

    path = [[False] * W for _ in range(H)]
    for y in range(6, 9):
        for x in range(0, W):
            path[y][x] = True
    for y in range(9, 12):
        for x in range(5, 8):
            path[y][x] = True
    for y in range(H):
        for x in range(W):
            if path[y][x]:
                draw(autotile(path, x, y, "path_dirt"), x * TILE + 8, y * TILE + 15, src=ground)

    water = [[False] * W for _ in range(H)]
    for y in range(11, 16):
        for x in range(23, 29):
            water[y][x] = True
    for y in range(H):
        for x in range(W):
            if water[y][x]:
                draw(autotile(water, x, y, "water"), x * TILE + 8, y * TILE + 15, 0, src=ground)

    # --- огород ---
    crops = [["pumpkin_ripe", "pumpkin_almost", "pumpkin_growing", "pumpkin_ripe"],
             ["carrot_ripe", "carrot_almost", "carrot_ripe", "carrot_growing"],
             ["cabbage_ripe", "cabbage_growing", "cabbage_ripe", "cabbage_sprout"]]
    gx, gy = 11, 10
    objects = []
    for j, row in enumerate(crops):
        for i, crop in enumerate(row):
            x, y = gx + i, gy + j
            draw("plot_wet" if (i + j) % 3 else "plot_dry", x * TILE + 8, y * TILE + 15)
            objects.append((y * TILE + 12, crop, x * TILE + 8, y * TILE + 12))
    # забор вокруг огорода
    fx0, fy0, fx1, fy1 = gx - 1, gy - 1, gx + 4, gy + 3
    for x in range(fx0, fx1 + 1):
        for y in (fy0, fy1):
            sid = "fence_h"
            if x == fx0: sid = "fence_corner_nw" if y == fy0 else "fence_corner_sw"
            elif x == fx1: sid = "fence_corner_ne" if y == fy0 else "fence_corner_se"
            elif y == fy1 and x == gx + 1: sid = "gate_open"
            objects.append((y * TILE + 14, sid, x * TILE + 8, y * TILE + 14))
    for y in range(fy0 + 1, fy1):
        for x in (fx0, fx1):
            objects.append((y * TILE + 14, "fence_v", x * TILE + 8, y * TILE + 14))

    # --- постройки и герои ---
    objects.append((5 * TILE + 15, "house_grandma_repaired", 4 * TILE + 8, 5 * TILE + 15))
    objects.append((5 * TILE + 15, "shed_repaired", 17 * TILE, 5 * TILE + 15))
    objects.append((10 * TILE + 15, "bublik_water_left", 16 * TILE + 8, 10 * TILE + 15))
    objects.append((7 * TILE + 15, "klusha_talk", 19 * TILE + 8, 7 * TILE + 15))
    for x, y in [(2, 12), (3, 13), (9, 14), (21, 9), (27, 3), (1, 9)]:
        objects.append((y * TILE + 15, "grass_tall_g" if cozy else "grass_tall", x * TILE + 8, y * TILE + 15))
    if cozy:
        # декоративные тыквы и кучки листьев из имеющихся спрайтов
        for x, y in [(8, 5), (9, 5), (21, 6), (22, 10), (10, 14)]:
            objects.append((y * TILE + 12, "pumpkin_ripe", x * TILE + 8, y * TILE + 12))

    if cozy:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(40, 20, 50, 70))
        for bx, by, bw in [(4 * TILE + 8, 5 * TILE + 15, 112), (17 * TILE, 5 * TILE + 15, 80)]:
            p.drawRect(QRectF(bx - bw / 2 + 6, by - 2, bw, 6))
    for sort_y, sid, x, y in sorted(objects):
        if sid.startswith(("bublik", "klusha")):
            draw("shadow_s", x, y)
        if sid == "grass_tall_g":
            spr = ground["grass_tall"]
            p.drawImage(int(x - spr.anchor[0]), int(y - spr.anchor[1]), spr.frame(300))
            continue
        draw(sid, x, y, 300)
    draw("fx_water_stream", 14 * TILE + 13, 10 * TILE + 6, 200)
    house_x, house_y = 4 * TILE + 8 - 56, 5 * TILE + 15 - 95
    draw("fx_smoke", house_x + 84, house_y - 2, 400)
    if cozy:
        for wx, wy in [(20, 58), (78, 58)]:
            p.drawImage(house_x + wx, house_y + wy, assets["house_window_lit"].frame())
        p.drawImage(house_x + 50, house_y + 29, assets["house_window_lit_s"].frame())
    draw("emote_exclaim", 19 * TILE + 8, 6 * TILE + 13)

    if cozy:
        for _ in range(9):
            draw(rnd.choice(["fx_leaf_fall_1", "fx_leaf_fall_2", "fx_leaf_fall_3"]),
                 rnd.randrange(W * TILE), rnd.randrange(H * TILE), rnd.randrange(600))
    p.end()

    scale = 3
    big = img.scaled(img.width() * scale, img.height() * scale, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    if cozy:
        q = QPainter(big)
        bw, bh = big.width(), big.height()
        # тёплый свет «золотого часа» сверху-слева
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SoftLight)
        g = QLinearGradient(0, 0, bw, bh)
        g.setColorAt(0.0, QColor(255, 196, 110, 170))
        g.setColorAt(0.6, QColor(255, 150, 90, 70))
        g.setColorAt(1.0, QColor(90, 70, 160, 120))
        q.fillRect(big.rect(), g)
        # мягкая виньетка
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        v = QRadialGradient(QPointF(bw * 0.45, bh * 0.45), max(bw, bh) * 0.75)
        v.setColorAt(0.55, QColor(255, 255, 255, 0))
        v.setColorAt(1.0, QColor(120, 70, 90, 150))
        q.fillRect(big.rect(), v)
        # тёплое свечение окон
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        hx, hy = (4 * TILE + 8 - 56) * scale, (5 * TILE + 15 - 95) * scale
        for wx, wy in [(27, 65), (85, 65), (56, 33)]:
            wg = QRadialGradient(QPointF(hx + wx * scale, hy + wy * scale), 70)
            wg.setColorAt(0, QColor(255, 190, 90, 140))
            wg.setColorAt(1, QColor(255, 190, 90, 0))
            q.setBrush(wg); q.setPen(Qt.PenStyle.NoPen)
            q.drawEllipse(QPointF(hx + wx * scale, hy + wy * scale), 70, 70)
        # пылинки в лучах света
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for _ in range(40):
            x, y = rnd.uniform(0, bw), rnd.uniform(0, bh * 0.8)
            r = rnd.uniform(3, 7)
            dg = QRadialGradient(QPointF(x, y), r * 2)
            dg.setColorAt(0, QColor(255, 225, 150, 150))
            dg.setColorAt(1, QColor(255, 225, 150, 0))
            q.setBrush(dg)
            q.setPen(Qt.PenStyle.NoPen)
            q.drawEllipse(QPointF(x, y), r * 2, r * 2)
        q.end()
    big.save(out)
    print("saved", out, big.width(), big.height())


if __name__ == "__main__":
    app = QGuiApplication.instance() or QGuiApplication(["x", "-platform", "offscreen"])
    render(sys.argv[1], sys.argv[2])
