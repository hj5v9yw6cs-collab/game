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
        "название": bed["name"],
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
            name = bed.get("название", bed.get("name"))
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


class ShopSim:
    """Лавка: очередь покупателей, продажи и ценники."""

    def __init__(self, queue, record):
        self.queue = copy.deepcopy(queue or [])
        self.record = record
        self.served = []
        self.tags = []

    def _customer(self, customer):
        name = customer.get("name") if isinstance(customer, dict) else customer
        if not isinstance(name, str):
            raise TypeError("sell() ждёт покупателя из очереди queue и сумму, например: sell(customer, 60). "
                            f"А первым значением пришло {type(customer).__name__}: {customer!r}")
        for c in self.queue:
            if c["name"] == name:
                return c
        names = ", ".join(c["name"] for c in self.queue) or "очередь пуста"
        raise ValueError(f"Покупателя «{name}» нет в очереди. В очереди: {names}.")

    def sell(self, customer, total):
        c = self._customer(customer)
        if isinstance(total, bool) or not isinstance(total, (int, float)):
            raise TypeError(f"Сумма в sell(покупатель, сумма) должна быть числом, а пришло "
                            f"{type(total).__name__}: {total!r}")
        self.served.append({"name": c["name"], "total": total})
        self.record({"k": "act", "cmd": "sell", "who": c["name"], "total": total, "ok": True})

    def tag(self, text):
        text = str(text)
        self.tags.append(text)
        self.record({"k": "act", "cmd": "tag", "text": text[:48], "ok": True})

    def commands(self):
        def sell(customer, total):
            """Продать покупателю из очереди: sell(customer, 60)"""
            self.sell(customer, total)

        def tag(text):
            """Повесить ценник на прилавок: tag("Тыква — 30 руб/кг")"""
            self.tag(text)
        return {"sell": sell, "tag": tag}


class PostSim:
    """Почта: доставка заказов по деревне."""

    def __init__(self, orders, record):
        self.orders = {o["id"]: o for o in (orders or [])}
        self.record = record
        self.delivered = []

    def deliver(self, order_id):
        if isinstance(order_id, dict):
            order_id = order_id.get("id")
        if isinstance(order_id, str) and order_id.isdigit():
            order_id = int(order_id)
        if order_id not in self.orders:
            known = ", ".join(str(i) for i in self.orders) or "нет заказов"
            raise ValueError(f"Заказа №{order_id} нет. Есть заказы: {known}. "
                             "deliver() ждёт номер заказа: deliver(order[\"id\"]).")
        o = self.orders[order_id]
        self.delivered.append(order_id)
        self.record({"k": "act", "cmd": "deliver", "id": order_id, "house": o.get("house", 1),
                     "who": o.get("customer", {}).get("name", ""), "ok": True})

    def commands(self):
        def deliver(order_id):
            """Отвезти заказ: deliver(order["id"])"""
            self.deliver(order_id)
        return {"deliver": deliver}


def player_view_en(bed):
    """Грядка в переменной field (с главы 3, английские названия)."""
    return {"name": bed["name"], "crop": bed["crop"], "humidity": bed["humidity"], "ripe": bed["stage"] == "ripe"}


def player_view_ru(bed):
    """Грядка в переменной поле (глава 2)."""
    return {"название": bed["name"], "культура": bed["crop"], "влажность": bed["humidity"],
            "спелая": bed["stage"] == "ripe"}
