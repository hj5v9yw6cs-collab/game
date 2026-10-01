"""Карта фермы: земля, рельеф, постройки, деревья и декор.

Карта собирается кодом (детерминированно), чтобы её было легко менять.
Координаты тайлов — (x, y), один тайл = 16×16 пикселей мира.
"""

import random
from dataclasses import dataclass, field

TILE = 16
W, H = 80, 52


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
    chapter: int = 1


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
    meadow = _mask([(33, 18, 44, 25), (0, 18, 5, 25), (15, 21, 19, 25), (60, 40, 79, 51), (0, 44, 18, 51),
                    (66, 5, 79, 20)], minus=[(35, 20, 43, 25)])
    apply_autotile(meadow, "meadow", outside=True)

    # --- возвышенность с домом: уступ с обрывом снизу ---
    plateau = _mask([(0, 3, 24, 12)])
    for y in range(H):
        for x in range(W):
            if plateau[y][x]:
                name = autotile_name(plateau, x, y, "cliff", outside=True)
                if name != "cliff_c" and x < 24 or (x == 24 and name != "cliff_c"):
                    m.overlay[y][x] = name
    occupy(0, 13, 24, 14)
    for x in range(0, 25):
        sprite = "cliff_stairs" if x == 11 else ("cliff_face_e" if x == 24 else "cliff_face_m")
        ax, ay = tile_anchor(x, 14)
        m.objects.append(WorldObject(sprite, ax, ay, shadow=False))

    # --- дорожки и дороги ---
    flagstone = _mask([(9, 15, 36, 16), (29, 9, 33, 10), (34, 9, 35, 14), (10, 11, 12, 12), (6, 10, 12, 10),
                       (13, 10, 18, 10)])
    apply_autotile(flagstone, "path_flagstone")
    dirt = _mask([(37, 15, 47, 16), (20, 17, 22, 27), (0, 27, 79, 28), (45, 10, 47, 26), (29, 29, 31, 31),
                  (11, 29, 13, 32), (51, 29, 53, 31), (63, 29, 65, 33), (71, 29, 73, 33), (35, 29, 37, 39)])
    apply_autotile(dirt, "path_dirt", outside=True)

    # --- пруд ---
    pond = _mask([(36, 20, 42, 24)])
    apply_autotile(pond, "water")
    m.water_tiles = [(x, y) for y in range(H) for x in range(W) if pond[y][x]]

    # --- огород в деревянных бортиках: 3 грядки (глава 1) ---
    m.beds = {}
    for name, cx in (("морковь", 26), ("тыква", 29), ("капуста", 32)):
        apply_autotile(_mask([(cx - 1, 11, cx + 1, 13)]), "bed_frame")
        m.beds[name] = (cx, 12)

    # --- поле: 12 грядок в рядах А, Б, В (глава 2) ---
    field_rect = (50, 6, 63, 20)
    for y in range(field_rect[1], field_rect[3] + 1):
        for x in range(field_rect[0], field_rect[2] + 1):
            m.overlay[y][x] = "plot_dry" if (x + y) % 5 else "plot_weeds"
            occupied[y][x] = True
    for r, row in enumerate("АБВ"):
        for c in range(4):
            m.beds[f"{row}{c + 1}"] = (52 + c * 3, 8 + r * 5)
    fence_x0, fence_y0, fence_x1, fence_y1 = 49, 5, 64, 21
    for x in range(fence_x0, fence_x1 + 1):
        for y in (fence_y0, fence_y1):
            if y == fence_y1 and x in (56, 57):
                continue
            sid = "fence_h"
            if x == fence_x0:
                sid = "fence_corner_nw" if y == fence_y0 else "fence_corner_sw"
            elif x == fence_x1:
                sid = "fence_corner_ne" if y == fence_y0 else "fence_corner_se"
            obj(sid, x, y, shadow=True)
    for y in range(fence_y0 + 1, fence_y1):
        for x in (fence_x0, fence_x1):
            obj("fence_v", x, y, shadow=True)
    occupy(fence_x0, fence_y0, fence_x1, fence_y1)
    obj("field_sign", 55, 22, info={"title": "Поле", "text": "12 грядок: ряды А, Б и В, в каждом по 4."})
    obj("scarecrow", 66, 12)
    obj("haystack", 67, 18)

    # --- постройки двора ---
    obj("house_grandma_abandoned", 7, 9, tag="house",
        info={"title": "Бабушкин дом", "text": "На мансарде — контора, где работает сова Ухта."})
    occupy(4, 4, 10, 9)
    shed = obj("shed_abandoned", 31, 8, tag="shed", dx=0,
               info={"title": "Сарай-мастерская", "text": "Здесь бабушка собирала роботов."})
    occupy(29, 5, 33, 8)
    m.spots["shed_door"] = (shed.x, shed.y + 8)

    # --- вещи у дома (на возвышенности) ---
    for sprite, tx, ty in [("jack_o_lantern", 5, 10), ("pumpkin_decor_m", 9, 10), ("candles", 10, 9),
                           ("flower_pot_a", 3, 9), ("flower_pot_b", 11, 9), ("well", 21, 7),
                           ("laundry_line", 19, 5), ("bench", 14, 12), ("lantern_post", 12, 12),
                           ("mailbox_farm", 10, 12), ("birdhouse", 2, 11), ("woodpile", 2, 7),
                           ("barrel_a", 12, 6), ("barrel_b", 13, 6)]:
        obj(sprite, tx, ty)
    desk = obj("desk_office", 16, 9, info={"title": "Стол Ухты", "text": "Контора фермы: папки, фото и отчёты."})
    m.spots["desk"] = (desk.x, desk.y)
    m.spots["office_home"] = (desk.x + 20, desk.y + 6)
    m.spots["mailbox"] = tile_anchor(10, 12)
    obj("tree_apple_ripe", 22, 11)
    obj("tree_apple_green", 18, 12)
    for tx, ty in [(1, 5), (23, 5)]:
        obj("tree_spruce", tx, ty)

    # --- двор у сарая ---
    for sprite, tx, ty in [("workbench", 37, 8), ("tools_lean", 28, 8), ("crate_empty", 36, 10),
                           ("crate_carrot", 37, 10), ("barrel_a", 27, 8), ("sack_seeds", 28, 9),
                           ("wheelbarrow", 26, 14), ("tub_water", 34, 8), ("scarecrow", 23, 17),
                           ("haystack", 39, 12), ("lantern_post", 36, 14), ("chest_red_closed", 38, 10),
                           ("pumpkin_decor_l", 24, 16), ("pumpkin_decor_s", 25, 17), ("pumpkin_white", 34, 18),
                           ("leafpile_l", 29, 18), ("leafpile_s", 14, 18), ("stump_axe", 38, 9),
                           ("boulder_m", 30, 20), ("boulder_s", 12, 20), ("bush_berries", 43, 9), ("snag", 26, 22)]:
        obj(sprite, tx, ty)
    m.lights += [("glow_lantern", *tile_anchor(12, 12), 1.0), ("glow_lantern", *tile_anchor(36, 14), 1.0),
                 ("glow_pumpkin", *tile_anchor(5, 10), 1.0), ("glow_candle", *tile_anchor(10, 9), 1.0)]

    # --- лавка у дороги (глава 3) ---
    stall = obj("stall_abandoned", 30, 35, tag="stall",
                info={"title": "Лавка «Осенний Лог»", "text": "Здесь робокот Мурзик продаёт урожай."})
    occupy(28, 33, 32, 35)
    m.spots["stall"] = (stall.x, stall.y)
    m.spots["stall_counter"] = (stall.x - 4, stall.y + 10)
    m.spots["queue"] = [((33 + i) * TILE + 8, 36 * TILE + 12) for i in range(6)]
    m.spots["queue_exit"] = (46 * TILE, 28 * TILE)
    for sprite, tx, ty in [("crate_pumpkin", 26, 35), ("crate_apples", 26, 36), ("crate_cabbage", 34, 33),
                           ("lantern_post", 33, 34), ("barrel_b", 27, 33), ("pumpkin_decor_m", 25, 37)]:
        obj(sprite, tx, ty)
    m.lights.append(("glow_lantern", *tile_anchor(33, 34), 1.0))

    # --- амбар (глава 4) ---
    barn = obj("barn_abandoned", 11, 37, tag="barn",
               info={"title": "Амбар", "text": "Склад фермы. Бобр хранит здесь ящики и файлы."})
    occupy(7, 32, 15, 37)
    cab = obj("cabinet_files", 17, 37, info={"title": "Шкаф с папками", "text": "Файлы фермы лежат на твоём Mac: Документы/Робоферма."})
    m.spots["cabinet"] = (cab.x, cab.y)
    m.spots["barn_home"] = (14 * TILE + 8, 39 * TILE + 4)
    for sprite, tx, ty in [("crate_empty", 6, 38), ("crate_carrot", 5, 39), ("sack_grain", 16, 39),
                           ("sack_seeds", 17, 40), ("crate_pumpkin", 7, 40), ("woodpile", 4, 36)]:
        obj(sprite, tx, ty)

    # --- почта и деревня (глава 5) ---
    post = obj("post_abandoned", 52, 35, tag="post",
               info={"title": "Почта", "text": "Сюда приходят заказы с сайта. Их развозит робоконь Искра."})
    occupy(50, 32, 54, 35)
    m.spots["post"] = (post.x, post.y)
    m.spots["post_home"] = (post.x + 34, post.y + 8)
    m.spots["houses"] = []
    for i, (tx, ty) in enumerate([(64, 36), (72, 36), (68, 46)], 1):
        h = obj(f"village_house_{i}", tx, ty, tag=f"village{i}",
                info={"title": f"Дом №{i}", "text": "Сюда Искра возит заказы."})
        occupy(tx - 3, ty - 4, tx + 3, ty)
        m.spots["houses"].append((h.x, h.y + 10))
    obj("mailbox_farm", 55, 36)

    # --- ярмарка (глава 7) ---
    tent = obj("fair_tent", 36, 47, tag="fair", info={"title": "Осенняя ярмарка", "text": "Финал сезона!"})
    occupy(33, 43, 39, 47)
    m.spots["fair"] = (tent.x, tent.y + 14)
    for sprite, tx, ty in [("fair_stall", 30, 47), ("fair_stall", 42, 47), ("fair_arch", 36, 42),
                           ("lantern_post", 32, 44), ("lantern_post", 40, 44), ("jack_o_lantern", 34, 49),
                           ("pumpkin_decor_l", 38, 49), ("haystack", 28, 49)]:
        obj(sprite, tx, ty)
    for x in range(30, 44, 3):
        obj("fair_bunting", x, 44, shadow=False)

    # --- лес по краю карты: дальний ряд светлее, ближний — плотный ---
    for x in range(0, W * TILE, 32):
        m.objects.append(WorldObject("forest_wall_far", x + 16, 2 * TILE - 2, shadow=False))
    for i, x in enumerate(range(-16, W * TILE, 32)):
        m.objects.append(WorldObject("forest_wall_a" if i % 2 else "forest_wall_b", x + 16, 3 * TILE + 4, shadow=False))
    occupy(0, 0, W - 1, 3)

    # --- деревья: кольцо по краям и рощицы ---
    trees = [("tree_spruce_big", 1, 19), ("tree_maple_orange", 3, 23), ("tree_crimson", 1, 26),
             ("tree_spruce", 7, 25), ("tree_crimson", 16, 25), ("tree_maple_orange", 25, 25),
             ("tree_birch", 34, 25), ("tree_spruce_big", 49, 26), ("tree_crimson", 44, 19),
             ("tree_birch", 41, 8), ("tree_spruce", 45, 6), ("tree_maple_orange", 39, 5),
             ("tree_spruce", 15, 23), ("tree_crimson", 8, 19), ("tree_maple_orange", 68, 7),
             ("tree_spruce_big", 75, 8), ("tree_birch", 71, 14), ("tree_crimson", 77, 20),
             ("tree_maple_orange", 67, 24), ("tree_spruce", 76, 25),
             ("tree_birch", 2, 31), ("tree_spruce_big", 1, 41), ("tree_maple_orange", 3, 47),
             ("tree_crimson", 9, 46), ("tree_spruce", 15, 48), ("tree_birch", 21, 45),
             ("tree_maple_orange", 22, 32), ("tree_crimson", 24, 40), ("tree_spruce", 45, 41),
             ("tree_maple_orange", 47, 48), ("tree_birch", 52, 45), ("tree_crimson", 57, 40),
             ("tree_spruce_big", 59, 50), ("tree_maple_orange", 77, 31), ("tree_crimson", 78, 43),
             ("tree_spruce", 74, 50), ("tree_birch", 62, 50), ("tree_apple_ripe", 40, 33),
             ("tree_apple_green", 43, 36), ("tree_apple_bare", 19, 33)]
    for sprite, tx, ty in trees:
        obj(sprite, tx, ty)
        occupy(tx - 1, ty - 1, tx + 1, ty)
    for sprite, tx, ty in [("bush_orange", 6, 22), ("bush_green", 18, 19), ("bush_magenta", 23, 20),
                           ("bush_green", 39, 18), ("bush_orange", 42, 12), ("bush_magenta", 60, 24),
                           ("bush_orange", 70, 22), ("bush_green", 19, 41), ("bush_magenta", 26, 42),
                           ("bush_orange", 48, 37), ("bush_green", 58, 34), ("bush_berries", 75, 39),
                           ("bush_magenta", 66, 49), ("bush_orange", 5, 43)]:
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
            if r < 0.06:
                obj(rnd.choice(smalls), x, y, shadow=True)
                occupied[y][x] = True
            elif r < 0.2:
                m.decals.append((rnd.choice(decals), x, y))

    # --- зоны: открываются по главам ---
    m.zones = [Zone("yard", "Сарай и огород", (0, 0, 44, 26), True, 1),
               Zone("field", "Поле", (45, 0, W - 1, 26), False, 2),
               Zone("shop", "Лавка", (19, 27, 44, 39), False, 3),
               Zone("barn", "Амбар", (0, 27, 18, 51), False, 4),
               Zone("post", "Почта и деревня", (45, 27, W - 1, H - 1), False, 5),
               Zone("fair", "Ярмарка", (19, 40, 44, H - 1), False, 7)]
    m.spots["bublik_home"] = (29 * TILE + 8, 14 * TILE + 12)
    m.spots["field_home"] = (56 * TILE + 8, 21 * TILE + 4)
    m.spots["klusha_home"] = m.spots["shed_door"]
    m.spots["camera_start"] = (29 * TILE, 11 * TILE)
    m.spots["zone_yard"] = (29 * TILE, 11 * TILE)
    m.spots["zone_field"] = (56 * TILE, 13 * TILE)
    m.spots["zone_shop"] = (31 * TILE, 33 * TILE)
    m.spots["zone_barn"] = (12 * TILE, 35 * TILE)
    m.spots["zone_post"] = (62 * TILE, 37 * TILE)
    m.spots["zone_office"] = (14 * TILE, 8 * TILE)
    m.spots["zone_fair"] = (36 * TILE, 44 * TILE)
    return m
