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


# ---------------------------------------------------------------- почта: заказы с сайта в JSON

TODAY = "2024-09-20"   # «сегодня» в игре
ORDER_PEOPLE = [("Даша", 1, 2.5), ("Михалыч", 2, 0.8), ("Нина", 3, 4.2), ("Борис", 1, 3.1), ("Оля", 2, 1.6),
                ("Гена", 3, 5.4), ("Люба", 1, 0.5), ("Степан", 2, 6.0)]
ORDER_GOODS = {"тыква": 30, "морковь": 50, "капуста": 20, "яблоки": 40, "мёд": 300}


def orders(variant=0):
    """Заказы интернет-магазина тёти Вали — как их отдаёт настоящий сайт."""
    rnd = random.Random(f"orders:{variant}")
    people = ORDER_PEOPLE[:5] if variant == 0 else rnd.sample(ORDER_PEOPLE, rnd.randint(4, 6))
    out = []
    for i, (name, house, km) in enumerate(people):
        n_items = rnd.randint(1, 3)
        goods = rnd.sample(list(ORDER_GOODS), n_items)
        items = [{"name": g, "kg": 1 if g == "мёд" else rnd.randint(1, 6), "price": ORDER_GOODS[g]} for g in goods]
        out.append({
            "id": 101 + i + (variant * 100),
            "date": f"2024-09-{rnd.randint(12, 19):02d}",
            "paid": True if variant == 0 and i < 2 else rnd.random() < 0.7,
            "customer": {"name": name, "house": house, "km": km},
            "items": items,
        })
    if variant == 0:
        out[2]["paid"] = False
    return out


def order_total(o):
    return sum(i["kg"] * i["price"] for i in o["items"])


def orders_json(data):
    import json
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------- контора: настоящие файлы для Finder

def png_bytes(color=(232, 128, 48), size=8):
    """Маленькая, но настоящая картинка PNG (открывается в Просмотре)."""
    import struct
    import zlib
    raw = b"".join(b"\x00" + bytes(color) * size for _ in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def pdf_text(title):
    """Минимальный настоящий PDF с одной строкой текста латиницей (открывается в Просмотре)."""
    stream = f"BT /F1 18 Tf 40 760 Td (Robofarm: {title}) Tj ET".encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def b64(data):
    import base64
    return {"b64": base64.b64encode(data).decode()}


PHOTO_COLORS = [(232, 128, 48), (200, 60, 50), (120, 170, 60), (240, 200, 70), (150, 90, 160)]
PHOTO_EXT = (".jpg", ".jpeg", ".png")
DOC_EXT = (".pdf", ".txt")
TABLE_EXT = (".csv",)


def downloads(variant=0):
    """Папка «Загрузки» Пети: фото, документы и таблицы вперемешку. Возвращает {путь: содержимое}."""
    rnd = random.Random(f"downloads:{variant}")
    if variant == 0:
        names = ["IMG_4821.jpg", "IMG_4822.jpg", "IMG_4830.JPG", "тыква_крупно.png", "скан_договора.pdf",
                 "счёт_за_свет.pdf", "заметки.txt", "рецепт_пирога.txt", "прайс.csv", "продажи_сентябрь.csv"]
    else:
        pool = [f"IMG_{rnd.randint(1000, 9999)}.jpg" for _ in range(4)] + ["DSC_0042.JPG", "урожай.jpeg",
                "кот_мурзик.png", "квитанция.pdf", "инструкция.pdf", "список_дел.txt", "остатки.csv",
                "заказы.csv", "отзывы.txt"]
        names = rnd.sample(pool, rnd.randint(8, 12))
    files = {}
    for i, name in enumerate(names):
        ext = name[name.rfind("."):].lower()
        path = f"Загрузки/{name}"
        if ext in PHOTO_EXT:
            files[path] = b64(png_bytes(PHOTO_COLORS[i % len(PHOTO_COLORS)]))
        elif ext == ".pdf":
            files[path] = b64(pdf_text(f"document {i + 1}"))
        elif ext == ".csv":
            files[path] = "товар,кг\nтыква,12\nморковь,40\n"
        else:
            files[path] = f"Файл «{name}» из Загрузок Пети.\n"
    return files


def kind_of(name):
    ext = name[name.rfind("."):].lower() if "." in name else ""
    if ext in PHOTO_EXT:
        return "Фото"
    if ext in DOC_EXT:
        return "Документы"
    if ext in TABLE_EXT:
        return "Таблицы"
    return None


def photos(variant=0, folder="фото"):
    rnd = random.Random(f"photos:{variant}")
    if variant == 0:
        names = ["IMG_4821.jpg", "IMG_4822.jpg", "IMG_4830.jpg", "IMG_4831.png", "IMG_4907.jpg"]
    else:
        nums = sorted(rnd.sample(range(1000, 9999), rnd.randint(4, 8)))
        names = [f"IMG_{n}{rnd.choice(['.jpg', '.jpg', '.JPG', '.png'])}" for n in nums]
    return {f"{folder}/{n}": b64(png_bytes(PHOTO_COLORS[i % len(PHOTO_COLORS)])) for i, n in enumerate(names)}


def screenshots(variant=0):
    rnd = random.Random(f"shots:{variant}")
    n = 3 if variant == 0 else rnd.randint(2, 5)
    names = [f"Снимок экрана {rnd.randint(10, 23)}.{rnd.randint(10, 59)}.{i:02d}.png" for i in range(n)]
    return {f"скриншоты/{name}": b64(png_bytes((90, 120, 200))) for name in names}


WEEK = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def week_sales(variant=0):
    """Семь файлов продаж за неделю. Возвращает (файлы, строки (товар, кг, цена)). Лучший товар — всегда один."""
    from collections import Counter
    rnd = random.Random(f"week:{variant}")
    prices = {"тыква": 30, "морковь": 50, "капуста": 20, "яблоки": 40}
    days = []
    for _ in WEEK:
        days.append([[item, rnd.randint(1, 9), prices[item]] for item in rnd.sample(list(prices), rnd.randint(2, 4))])
    total = Counter()
    for day in days:
        for item, kg, _ in day:
            total[item] += kg
    (top, a), (_, b) = total.most_common(2)
    if a == b:
        next(row for day in days for row in day if row[0] == top)[1] += 1
    files, rows = {}, []
    for d, day in zip(WEEK, days):
        rows += [tuple(row) for row in day]
        files[f"неделя/продажи_{d}.csv"] = "товар,кг,цена\n" + "".join(f"{i},{k},{p}\n" for i, k, p in day)
    return files, rows


# ---------------------------------------------------------------- ярмарка: погода и остатки из Excel

def weather(variant=0):
    """Прогноз на неделю — как его отдают настоящие сайты погоды. Лучший день для ярмарки всегда один."""
    rnd = random.Random(f"weather:{variant}")
    for attempt in range(100):
        days = []
        for d in range(7):
            rain = rnd.choice([0.0, 0.0, 0.0, 1.5, 4.2, 12.0])
            days.append({"date": f"2024-09-{23 + d:02d}", "temp": rnd.randint(6, 17), "rain_mm": rain,
                         "wind": rnd.choice([2, 3, 4, 5, 6, 9, 12])})
        good = [d for d in days if d["rain_mm"] == 0 and d["wind"] < 8]
        temps = sorted((d["temp"] for d in good), reverse=True)
        warm = sorted((d["temp"] for d in days), reverse=True)
        if len(good) >= 2 and temps[0] != temps[1] and warm[0] != warm[1] and len(good) < len(days):
            if variant == 0 and max(days, key=lambda d: d["temp"]) in good:
                continue  # пусть самый тёплый день будет дождливым — так задача интереснее
            return {"city": "Осенний Лог", "units": {"temp": "°C", "rain_mm": "мм", "wind": "м/с"}, "daily": days}
        rnd = random.Random(f"weather:{variant}:{attempt}")
    raise RuntimeError("не удалось подобрать погоду")


def best_day(w):
    good = [d for d in w["daily"] if d["rain_mm"] == 0 and d["wind"] < 8]
    return max(good, key=lambda d: d["temp"])


FAIR_ITEMS = ["тыква", "морковь", "капуста", "яблоки", "мёд", "свёкла", "картошка"]


def fair_stock(variant=0):
    """Остатки к ярмарке: [(товар, кг, цена)]. Цены кратны 5, поэтому скидка 20% даёт целые рубли."""
    if variant == 0:
        return [("тыква", 80, 30), ("морковь", 35, 50), ("капуста", 60, 20), ("яблоки", 45, 40), ("мёд", 12, 300)]
    rnd = random.Random(f"fair:{variant}")
    return [(item, rnd.choice([15, 30, 45, 55, 70, 90]), rnd.choice([20, 25, 30, 45, 50, 60]))
            for item in rnd.sample(FAIR_ITEMS, rnd.randint(4, 6))]


def fair_price(price, kg):
    return round(price * 0.8) if kg > 50 else price


def excel_csv(rows):
    """Таблица, сохранённая из Excel: точка с запятой и невидимая метка BOM в начале."""
    return "﻿товар;кг;цена\n" + "".join(f"{i};{k};{p}\n" for i, k, p in rows)
