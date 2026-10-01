"""Карта фермы: земля, рельеф, постройки, деревья и декор.

Карта собирается кодом (детерминированно), чтобы её было легко менять.
Координаты тайлов — (x, y), один тайл = 16×16 пикселей мира.
"""

import random
from dataclasses import dataclass, field

TILE = 16
W, H = 52, 34


@dataclass
class WorldObject:
    sprite: str
    x: float  # точка опоры в пикселях мира
    y: float
    shadow: bool = True
    phase: int = 0  # сдвиг анимации, чтобы деревья качались не синхронно
    info: dict = None  # для карточки при наведении
    tag: str = ""  # для смены спрайта по сюжету (house, shed…)


@dataclass
class Zone:
    id: str
    name: str
    rect: tuple  # x0, y0, x1, y1 в тайлах, включительно
    open: bool = False


@dataclass
class MapData:
    ground: list = field(default_factory=list)   # [y][x] -> sprite id
    overlay: list = field(default_factory=list)  # [y][x] -> sprite id | None (автотайлы поверх)
    decals: list = field(default_factory=list)   # (sprite, tile_x, tile_y) — плоские мелочи на земле
    objects: list = field(default_factory=list)  # WorldObject
    zones: list = field(default_factory=list)
    beds: dict = field(default_factory=dict)     # имя грядки -> (tile_x, tile_y)
    spots: dict = field(default_factory=dict)    # именованные точки (px)
    lights: list = field(default_factory=list)   # (glow sprite, x, y, strength)
    water_tiles: list = field(default_factory=list)


def autotile_name(mask, x, y, kind, outside=False):
    def m(dx, dy):
        xx, yy = x + dx, y + dy
        if not (0 <= xx < W and 0 <= yy < H):
            return outside
        return mask[yy][xx]
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


def _mask(rects, minus=()):
    mask = [[False] * W for _ in range(H)]
    for x0, y0, x1, y1 in rects:
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                mask[y][x] = True
    for x0, y0, x1, y1 in minus:
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                mask[y][x] = False
    return mask


def tile_anchor(tx, ty):
    """Точка опоры объекта, стоящего на тайле: середина нижнего края."""
    return tx * TILE + 8, ty * TILE + 15


def build_map():
    rnd = random.Random(2024)
    m = MapData()
    m.ground = [[rnd.choice(["grass_1", "grass_1", "grass_2", "grass_3", "grass_4"]) for _ in range(W)] for _ in range(H)]
    m.overlay = [[None] * W for _ in range(H)]
    occupied = [[False] * W for _ in range(H)]

    def occupy(x0, y0, x1, y1):
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                occupied[y][x] = True

    def apply_autotile(mask, kind, outside=False):
        for y in range(H):
            for x in range(W):
                if mask[y][x]:
                    m.overlay[y][x] = autotile_name(mask, x, y, kind, outside)
                    occupied[y][x] = True

    def obj(sprite, tx, ty, shadow=True, info=None, tag="", dx=0, dy=0):
        ax, ay = tile_anchor(tx, ty)
        o = WorldObject(sprite, ax + dx, ay + dy, shadow, rnd.randrange(3), info, tag)
        m.objects.append(o)
        return o

    # --- зелёные островки травы (луг) ---
    meadow = _mask([(33, 18, 47, 27), (0, 18, 5, 30), (15, 21, 22, 26)], minus=[(35, 20, 43, 25)])
    apply_autotile(meadow, "meadow")

    # --- возвышенность с домом: уступ с обрывом снизу ---
    plateau = _mask([(0, 3, 24, 12)])
    for y in range(H):
        for x in range(W):
            if plateau[y][x]:
                name = autotile_name(plateau, x, y, "cliff", outside=True)
                if name != "cliff_c":
                    m.overlay[y][x] = name
    occupy(0, 13, 24, 14)
    for x in range(0, 25):
        sprite = "cliff_stairs" if x == 11 else ("cliff_face_e" if x == 24 else "cliff_face_m")
        ax, ay = tile_anchor(x, 14)
        m.objects.append(WorldObject(sprite, ax, ay, shadow=False))

    # --- дорожки ---
    flagstone = _mask([(9, 15, 36, 16), (29, 9, 33, 10), (34, 9, 35, 14), (10, 11, 12, 12), (6, 10, 12, 10)])
    apply_autotile(flagstone, "path_flagstone")
    dirt = _mask([(33, 16, 51, 17), (20, 17, 22, 33)])
    apply_autotile(dirt, "path_dirt", outside=True)

    # --- пруд ---
    pond = _mask([(36, 20, 42, 24)])
    apply_autotile(pond, "water")
    m.water_tiles = [(x, y) for y in range(H) for x in range(W) if pond[y][x]]

    # --- огород в деревянных бортиках: 3 грядки в среднем ряду ---
    m.beds = {}
    for name, cx in (("морковь", 26), ("тыква", 29), ("капуста", 32)):
        apply_autotile(_mask([(cx - 1, 11, cx + 1, 13)]), "bed_frame")
        m.beds[name] = (cx, 12)

    # --- постройки ---
    obj("house_grandma_abandoned", 7, 9, tag="house",
        info={"title": "Бабушкин дом", "text": "Пока заброшен. Отремонтируем, когда наладим огород."})
    occupy(4, 4, 10, 9)
    shed = obj("shed_abandoned", 31, 8, tag="shed", dx=0,
               info={"title": "Сарай-мастерская", "text": "Здесь бабушка собирала роботов."})
    occupy(29, 5, 33, 8)
    m.spots["shed_door"] = (shed.x, shed.y + 8)

    # --- вещи у дома (на возвышенности) ---
    for sprite, tx, ty in [("jack_o_lantern", 5, 10), ("pumpkin_decor_m", 9, 10), ("candles", 10, 9),
                           ("flower_pot_a", 3, 9), ("flower_pot_b", 11, 9), ("well", 15, 8),
                           ("laundry_line", 19, 6), ("bench", 14, 11), ("lantern_post", 12, 12),
                           ("mailbox_farm", 10, 12), ("birdhouse", 2, 11), ("woodpile", 2, 7),
                           ("barrel_a", 12, 6), ("barrel_b", 13, 6)]:
        obj(sprite, tx, ty)
    m.spots["mailbox"] = tile_anchor(10, 12)
    obj("tree_apple_ripe", 21, 10)
    obj("tree_apple_green", 18, 11)
    for tx, ty in [(1, 5), (23, 5)]:
        obj("tree_spruce", tx, ty)

    # --- двор у сарая ---
    for sprite, tx, ty in [("workbench", 37, 8), ("tools_lean", 28, 8), ("crate_empty", 36, 10),
                           ("crate_carrot", 37, 10), ("barrel_a", 27, 8), ("sack_seeds", 28, 9),
                           ("wheelbarrow", 26, 14), ("tub_water", 34, 8), ("scarecrow", 23, 17),
                           ("haystack", 39, 12), ("lantern_post", 36, 14), ("chest_red_closed", 38, 10),
                           ("pumpkin_decor_l", 24, 16), ("pumpkin_decor_s", 25, 17), ("pumpkin_white", 34, 18),
                           ("leafpile_l", 29, 18), ("leafpile_s", 14, 18), ("stump_axe", 38, 9),
                           ("boulder_l", 46, 13), ("boulder_m", 30, 20), ("boulder_s", 12, 20),
                           ("bush_berries", 44, 9), ("snag", 26, 22)]:
        obj(sprite, tx, ty)
    m.lights += [("glow_lantern", *tile_anchor(12, 12), 1.0), ("glow_lantern", *tile_anchor(36, 14), 1.0),
                 ("glow_pumpkin", *tile_anchor(5, 10), 1.0), ("glow_candle", *tile_anchor(10, 9), 1.0)]

    # --- лес по краю карты: дальний ряд светлее, ближний — плотный ---
    for i, x in enumerate(range(0, W * TILE, 32)):
        m.objects.append(WorldObject("forest_wall_far", x + 16, 2 * TILE - 2, shadow=False))
    for i, x in enumerate(range(-16, W * TILE, 32)):
        m.objects.append(WorldObject("forest_wall_a" if i % 2 else "forest_wall_b", x + 16, 3 * TILE + 4, shadow=False))
    occupy(0, 0, W - 1, 3)

    # --- деревья: кольцо по краям и рощицы ---
    trees = [("tree_spruce_big", 1, 19), ("tree_maple_orange", 3, 23), ("tree_crimson", 1, 27),
             ("tree_birch", 4, 30), ("tree_spruce", 7, 26), ("tree_maple_orange", 10, 31),
             ("tree_crimson", 16, 29), ("tree_spruce_big", 25, 31), ("tree_maple_orange", 30, 30),
             ("tree_birch", 34, 29), ("tree_crimson", 40, 29), ("tree_spruce", 46, 30),
             ("tree_spruce_big", 49, 22), ("tree_maple_orange", 48, 14), ("tree_crimson", 50, 8),
             ("tree_birch", 41, 8), ("tree_spruce", 46, 6), ("tree_maple_orange", 37, 6),
             ("tree_crimson", 44, 18), ("tree_birch", 34, 23), ("tree_spruce", 15, 24),
             ("tree_crimson", 8, 19), ("tree_maple_orange", 47, 26)]
    for sprite, tx, ty in trees:
        obj(sprite, tx, ty)
        occupy(tx - 1, ty - 1, tx + 1, ty)
    for sprite, tx, ty in [("bush_orange", 6, 22), ("bush_magenta", 12, 27), ("bush_green", 18, 19),
                           ("bush_orange", 27, 26), ("bush_magenta", 44, 23), ("bush_green", 39, 18),
                           ("bush_orange", 42, 12), ("bush_magenta", 23, 20)]:
        obj(sprite, tx, ty)
        occupy(tx - 1, ty - 1, tx, ty)

    # --- россыпь мелочей по свободной земле ---
    smalls = ["shrub_orange", "shrub_magenta", "shrub_green", "shrub_ochre", "mushroom_a", "mushroom_b",
              "mushroom_c", "wildflower_1", "wildflower_2", "wildflower_3", "wildflower_4", "grass_tall"]
    decals = ["overlay_leaves_1", "overlay_leaves_2", "overlay_leaves_3", "overlay_leaves_4",
              "overlay_pebbles_1", "overlay_pebbles_2", "overlay_greens_1", "overlay_greens_2", "overlay_greens_3"]
    for y in range(4, H):
        for x in range(W):
            if occupied[y][x] or m.overlay[y][x]:
                continue
            r = rnd.random()
            if r < 0.07:
                obj(rnd.choice(smalls), x, y, shadow=True)
                occupied[y][x] = True
            elif r < 0.22:
                m.decals.append((rnd.choice(decals), x, y))

    # --- зоны ---
    m.zones = [Zone("yard", "Сарай и огород", (0, 0, 44, 26), True),
               Zone("field", "Поле", (45, 0, W - 1, H - 1)),
               Zone("south", "Дорога к лавке", (0, 27, 44, H - 1))]
    m.spots["bublik_home"] = (29 * TILE + 8, 14 * TILE + 12)
    m.spots["klusha_home"] = m.spots["shed_door"]
    m.spots["camera_start"] = (29 * TILE, 11 * TILE)
    return m
