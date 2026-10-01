"""Модель огорода: грядки и команды роботов.

Этот модуль не зависит от Qt: его используют и песочница (где выполняется код игрока),
и игра (где грядки рисуются в мире).
"""

import copy

# Культуры: сколько килограммов даёт спелая грядка и какие спрайты у стадий роста.
CROPS = {
    "морковь": {"sprite": "carrot", "kg": 4},
    "тыква": {"sprite": "pumpkin", "kg": 9},
    "капуста": {"sprite": "cabbage", "kg": 6},
}

STAGES = ("seed", "sprout", "growing", "almost", "ripe", "withered")


def make_bed(name, crop, x, y, humidity=60, stage="ripe", kg=None):
    """Грядка — обычный словарь. Так она хранится, передаётся в песочницу и показывается в рентгене."""
    return {
        "name": name, "crop": crop, "x": x, "y": y,
        "humidity": humidity, "stage": stage,
        "kg": CROPS[crop]["kg"] if kg is None else kg,
    }


def player_view(bed):
    """Как грядку видит игрок: в рентгене, в карточке при наведении и в переменной «поле»."""
    return {
        "грядка": bed["name"],
        "влажность": bed["humidity"],
        "спелая": bed["stage"] == "ripe",
    }


def bed_sprite(bed):
    if bed["stage"] == "empty":
        return None
    return f'{CROPS[bed["crop"]]["sprite"]}_{bed["stage"]}'


# Похожие буквы: русская и английская раскладка. Нужны, чтобы заметить «тыквa» с английской «a».
HOMOGLYPHS = str.maketrans("aceopxyACEHKMOPTXB", "асеорхуАСЕНКМОРТХВ")


def mixed_script(word):
    has_lat = any("a" <= ch.lower() <= "z" for ch in word)
    has_cyr = any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in word)
    return has_lat and has_cyr


class FarmSim:
    """Огород внутри песочницы: команды роботов меняют его и записывают события."""

    def __init__(self, beds, record):
        self.beds = copy.deepcopy(beds)
        self.record = record  # функция: record(event_dict)

    def find(self, bed, command):
        if isinstance(bed, dict):
            name = bed.get("грядка", bed.get("name"))
        else:
            name = bed
        if not isinstance(name, str):
            example = f'{command}("{self.beds[0]["name"]}")' if self.beds else f'{command}("тыква")'
            raise TypeError(
                f"Команда {command}() ждёт название грядки в кавычках, например: {example}. "
                f"А получила {type(bed).__name__}: {bed!r}")
        for b in self.beds:
            if b["name"] == name:
                return b
        names = ", ".join(b["name"] for b in self.beds)
        hint = ""
        fixed = name.translate(HOMOGLYPHS)
        if fixed != name and any(b["name"] == fixed for b in self.beds):
            hint = f" В слове «{name}» есть английская буква — переключи раскладку и напиши «{fixed}»."
        elif name.strip() != name and any(b["name"] == name.strip() for b in self.beds):
            hint = " Лишний пробел внутри кавычек."
        raise ValueError(f"Грядки «{name}» нет. Есть грядки: {names}.{hint}")

    def water(self, bed, command="полить"):
        b = self.find(bed, command)
        before = b["humidity"]
        b["humidity"] = 100
        self.record({"k": "act", "cmd": "water", "bed": b["name"], "ok": True, "before": before})

    def harvest(self, bed, command="собрать"):
        b = self.find(bed, command)
        if b["stage"] != "ripe":
            self.record({"k": "act", "cmd": "harvest", "bed": b["name"], "ok": False,
                         "msg": "ещё не созрела" if b["stage"] != "empty" else "уже пустая"})
            return 0
        kg = b["kg"]
        b["stage"] = "empty"
        self.record({"k": "act", "cmd": "harvest", "bed": b["name"], "ok": True, "res": kg})
        return kg

    def commands(self, lang):
        """Функции-команды, которые получает код игрока."""
        def полить(грядка):
            """Полить грядку: полить("тыква")"""
            self.water(грядка, "полить")

        def собрать(грядка):
            """Собрать урожай с грядки. Возвращает килограммы: кг = собрать("тыква")"""
            return self.harvest(грядка, "собрать")

        def water(bed):
            """Water a bed: water("тыква")"""
            self.water(bed, "water")

        def harvest(bed):
            """Harvest a bed, returns kilograms."""
            return self.harvest(bed, "harvest")

        ru = {"полить": полить, "собрать": собрать}
        en = {"water": water, "harvest": harvest}
        if lang == "ru":
            return ru
        if lang == "en":
            return en
        return {**ru, **en}
