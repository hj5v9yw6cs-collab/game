"""Общие данные и помощники для уроков всех глав."""

import random

from robofarm.farm import CROPS, make_bed

FIELD_ROWS = "АБВ"


def field_pos(name):
    r, c = FIELD_ROWS.index(name[0]), int(name[1:]) - 1
    return 52 + c * 3, 8 + r * 5


def field_beds(variant=0, count=12, ripe_share=0.5, dry_share=0.5, seed="field"):
    """Грядки поля. Вариант 0 — то, что видно в мире; другие варианты — «данные следующего дня»."""
    rnd = random.Random(f"{seed}:{variant}")
    names = [f"{row}{c}" for row in FIELD_ROWS for c in range(1, 5)][:count]
    crops = list(CROPS)
    beds = []
    for i, name in enumerate(names):
        crop = crops[(i + rnd.randrange(3)) % 3] if variant else crops[i % 3]
        dry = rnd.random() < dry_share
        ripe = rnd.random() < ripe_share
        humidity = rnd.choice([10, 15, 20, 25, 30, 35]) if dry else rnd.choice([40, 55, 70, 85, 100])
        stage = "ripe" if ripe else rnd.choice(["sprout", "growing", "almost"])
        x, y = field_pos(name)
        beds.append(make_bed(name, crop, x, y, humidity=humidity, stage=stage))
    if variant == 0:
        # гарантируем разнообразие на виду: есть сухие, мокрые, спелые и неспелые
        beds[0].update(humidity=20, stage="ripe")
        beds[1].update(humidity=80, stage="growing")
        beds[2].update(humidity=100, stage="ripe")
        beds[3].update(humidity=15, stage="almost")
    return beds


def numbers_in(lines):
    import re
    out = []
    for line in lines:
        out += [float(t) for t in re.findall(r"-?\d+(?:[.,]\d+)?", line.replace(",", "."))]
    return out


def lines_match(r, expected, what="Вывод"):
    """Сравнение напечатанных строк с ожидаемыми, с понятной подсказкой о первом отличии."""
    got = r.lines
    for i, exp in enumerate(expected):
        if i >= len(got):
            return f"{what}: не хватает строк. Ожидалась строка №{i + 1}: «{exp}»."
        if got[i].strip() != exp:
            g = got[i].strip()
            extra = " (отличаются только пробелы)" if g.replace(" ", "") == exp.replace(" ", "") else ""
            return f"{what}, строка {i + 1}: ожидалось «{exp}», а напечатано «{g}»{extra}."
    if len(got) > len(expected):
        return f"{what}: лишние строки. Первая лишняя: «{got[len(expected)].strip()}»."
    return None


# ---------------------------------------------------------------- лавка

SHOP_PRICES = {"морковь": 50, "тыква": 30, "капуста": 20}
SHOP_QUEUE = [{"name": "Валя", "item": "тыква", "kg": 3, "regular": True},
              {"name": "Михалыч", "item": "морковь", "kg": 2, "regular": False},
              {"name": "Даша", "item": "капуста", "kg": 5, "regular": True},
              {"name": "Петя", "item": "тыква", "kg": 1, "regular": False}]
CUSTOMER_NAMES = ["Нина", "Борис", "Оля", "Гена", "Люба", "Степан", "Зоя", "Миша", "Валя", "Даша"]


def shop_prices(variant=0):
    """Цены лавки; цены кратны 10, поэтому скидка 10% всегда даёт целые рубли."""
    if variant == 0:
        return dict(SHOP_PRICES)
    rnd = random.Random(f"prices:{variant}")
    prices = {item: rnd.choice([20, 30, 40, 60, 70]) for item in SHOP_PRICES}
    prices["яблоки"] = rnd.choice([40, 60])
    return prices


def shop_queue(variant=0, prices=None):
    if variant == 0:
        return [dict(c) for c in SHOP_QUEUE]
    rnd = random.Random(f"queue:{variant}")
    items = list(prices or shop_prices(variant))
    names = rnd.sample(CUSTOMER_NAMES, rnd.randint(3, 5))
    return [{"name": n, "item": rnd.choice(items), "kg": rnd.randint(1, 6), "regular": rnd.random() < 0.5}
            for n in names]


# ---------------------------------------------------------------- амбар: файлы склада и продаж

STOCK_ITEMS = ["морковь", "тыква", "капуста", "яблоки", "свёкла", "картошка", "лук"]


def stock(variant=0):
    """Остатки на складе: товар → кг."""
    if variant == 0:
        return {"морковь": 40, "тыква": 12, "капуста": 25, "яблоки": 8, "свёкла": 30}
    rnd = random.Random(f"stock:{variant}")
    items = rnd.sample(STOCK_ITEMS, rnd.randint(4, 6))
    return {item: rnd.choice([5, 9, 14, 18, 22, 35, 47, 60]) for item in items}


def stock_txt(st):
    return "".join(f"{item}: {kg}\n" for item, kg in st.items())


def sales(variant=0, days=5):
    """Журнал продаж: [(дата, товар, кг, цена)]."""
    rnd = random.Random(f"sales:{variant}")
    prices = {"морковь": 50, "тыква": 30, "капуста": 20, "яблоки": 40}
    if variant:
        prices = {k: v + rnd.choice([-10, 0, 10]) for k, v in prices.items()}
    rows = []
    for d in range(days):
        date = f"2024-09-{2 + d:02d}"
        for item in rnd.sample(list(prices), rnd.randint(2, 4)):
            rows.append((date, item, rnd.randint(1, 6), prices[item]))
    return rows


def sales_csv(rows):
    return "дата,товар,кг,цена\n" + "".join(f"{d},{i},{k},{p}\n" for d, i, k, p in rows)


def revenue_by_item(rows):
    out = {}
    for _, item, kg, price in rows:
        out[item] = out.get(item, 0) + kg * price
    return out


def cash_lines(variant=0, short_lines=False):
    """Касса, заполненная руками: часть строк «грязные». Возвращает (строки файла, хорошие суммы, плохие строки)."""
    rnd = random.Random(f"cash:{variant}")
    prices = {"морковь": 50, "тыква": 30, "капуста": 20, "яблоки": 40}
    words = ["два", "пять", "много", "", "3кг", "?"]
    lines, good, bad = [], [], []
    count = 7 if variant == 0 else rnd.randint(6, 10)
    bad_at = {1, 4} if variant == 0 else set(rnd.sample(range(count), rnd.randint(1, 3)))
    if short_lines:
        bad_at.add(count - 2 if variant == 0 else rnd.randrange(count))
    for i in range(count):
        item = rnd.choice(list(prices))
        kg, price = rnd.randint(1, 6), prices[item]
        if i in bad_at:
            if short_lines and i == max(bad_at):
                line = f"{item},{kg}"
            else:
                line = f"{item},{rnd.choice(words)},{price}"
            bad.append(line)
        else:
            line = f"{item},{kg},{price}"
            good.append(kg * price)
        lines.append(line)
    return lines, good, bad
