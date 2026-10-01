"""Бабушкин каталог: украшения фермы, которые покупаются за монеты.

Каждое украшение — набор объектов на карте с тегом «decor:<id>». Они нарисованы,
только когда украшение куплено (флаг мира с тем же именем).
"""

from dataclasses import dataclass


@dataclass
class Decor:
    id: str
    title: str
    text: str
    price: int
    preview: str
    objects: list       # (спрайт, тайл x, тайл y)
    lights: list = ()   # (свечение, тайл x, тайл y)

    @property
    def flag(self):
        return f"decor:{self.id}"


CATALOG = [
    Decor("flowers", "Цветы у дома", "Горшки с астрами и ящик с цветами под окном.", 15, "flower_pot_a",
          [("flower_pot_a", 6, 10), ("flower_pot_b", 8, 10), ("window_flowerbox", 4, 10)]),
    Decor("birdhouse", "Скворечник и скамейка у пруда", "Посидеть вечером и посмотреть на уток.", 20, "birdhouse",
          [("bench", 40, 26), ("birdhouse", 43, 24)]),
    Decor("vane", "Флюгер-петушок", "Показывает, откуда дует ветер. Почти как погода из JSON.", 20, "weathervane",
          [("weathervane", 27, 6)]),
    Decor("lanterns", "Фонари вдоль дорожки", "Тёплый свет от сарая до поля.", 30, "lantern_post",
          [("lantern_post", 41, 14), ("lantern_post", 47, 17), ("lantern_post", 21, 26)],
          [("glow_lantern", 41, 14), ("glow_lantern", 47, 17), ("glow_lantern", 21, 26)]),
    Decor("jacks", "Тыквы-фонарики", "Три светящиеся тыквы у сарая — настоящая осень.", 25, "jack_o_lantern",
          [("jack_o_lantern", 25, 10), ("jack_o_lantern", 35, 12), ("pumpkin_decor_l", 27, 15)],
          [("glow_pumpkin", 25, 10), ("glow_pumpkin", 35, 12)]),
    Decor("gate", "Ворота на поле", "Крепкие деревянные ворота вместо дыры в заборе.", 25, "gate_open",
          [("gate_open", 56, 21)]),
    Decor("apples", "Молодые яблони", "Две яблони у поля. Яблоки — к ярмарке!", 35, "tree_apple_ripe",
          [("tree_apple_ripe", 47, 22), ("tree_apple_green", 65, 23)]),
    Decor("chests", "Сундуки урожая", "Зелёный сундук и ящики с яблоками у амбара.", 20, "chest_green_open",
          [("chest_green_open", 5, 41), ("crate_apples", 8, 42), ("crate_pumpkin", 10, 42)]),
]


def by_id(decor_id):
    return next(d for d in CATALOG if d.id == decor_id)
