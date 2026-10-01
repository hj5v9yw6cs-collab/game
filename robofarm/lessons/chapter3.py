"""Глава 3. «Лавка»: английские имена, строки и f-строки, словари, функции."""

import ast

from robofarm.lessons.base import Chapter, Lesson, Quest, Step
from robofarm.lessons.common import field_beds, lines_match, shop_prices, shop_queue


def _field(variant):
    return {"beds": field_beds(variant, (12, 10, 11)[min(variant, 2)], seed="english")}


def _shop(variant):
    prices = shop_prices(variant)
    return {"queue": shop_queue(variant, prices), "inject": {"prices": prices}}


def beds(r):
    return r.input.get("beds", [])


def names(r, cond=lambda b: True):
    return [b["name"] for b in beds(r) if cond(b)]


def ripe(b):
    return b["stage"] == "ripe"


def dry(b):
    return b["humidity"] < 40


def num_eq(a, b):
    try:
        return abs(float(a) - float(b)) < 0.011
    except (TypeError, ValueError):
        return False


def _fmt(x):
    return str(int(x)) if float(x).is_integer() else str(x)


def call_check(r, fn, cases, what):
    """cases: [(аргументы, ожидаемое значение)]. Возвращает подсказку или None."""
    for args, expected in cases:
        c = r.call(fn, *args)
        if c is None or c.get("missing"):
            if c and c.get("not_callable"):
                return f"{fn} — это не функция. Функцию создают так: def {fn}(...):"
            return f"Не нашлась функция {fn}. Проверь, что она называется ровно так: def {fn}(...):"
        if c.get("error"):
            return f"Функция {fn}{tuple(args)} упала с ошибкой: {c['error']['title']}. {c['error']['hint']}"
        value = c.get("value")
        if value is None:
            return (f"{fn}{tuple(args)} ничего не вернула (None). Нужен return — «вернуть»: "
                    "без него функция считает, но результат не отдаёт.")
        ok = num_eq(value, expected) if isinstance(expected, (int, float)) else value == expected
        if not ok:
            shown = repr(value) if isinstance(value, str) else value
            want = repr(expected) if isinstance(expected, str) else _fmt(expected)
            return f"Проверка {what}: {fn}{tuple(args)} вернула {shown}, а должна {want}."
    return None


# ---------------------------------------------------------------- урок 9: по-английски

def _harvest_ripe(r):
    if r.harvested(ok=False):
        return "Бублик дёргал неспелые грядки. Внутри if нужна команда harvest(bed)."
    if set(r.harvested()) != set(names(r, ripe)):
        return "Собраны не все спелые грядки. Команда сбора по-английски — harvest."
    return None


def _water_dry_en(r):
    if set(r.watered()) != set(names(r, dry)):
        return 'Полить нужно все сухие грядки и только их: if bed["humidity"] < 40:'
    return None


def _pumpkins(r):
    want = names(r, lambda b: b["crop"] == "тыква")
    got = [line.strip() for line in r.lines]
    if sorted(got) != sorted(want):
        return (f"Нужно напечатать названия грядок с тыквой: {', '.join(want)}. "
                'Сравни культуру: bed["crop"] == "тыква", а печатай bed["name"].')
    return None


def _quest9(r):
    def check(v):
        if v.harvested(ok=False):
            return "Бублик пытался собрать неспелые грядки."
        if set(v.watered()) != set(names(v, dry)):
            return "Полей все сухие грядки (влажность меньше 40) — и только их."
        if set(v.harvested()) != set(names(v, ripe)):
            return "Собери все спелые грядки."
        total = sum(b["kg"] for b in beds(v) if ripe(b))
        if not v.printed_number(total):
            return f"Всего собрано {total} кг — напечатай это число. Складывай то, что возвращает harvest(bed)."
        return None
    msg = r.each(check)
    if msg:
        return msg
    russian = [n.id for n in ast.walk(r.tree()) if isinstance(n, ast.Name) and any("а" <= ch <= "я" for ch in n.id.lower())]
    if russian:
        return f"Всё работает! Но Мурзик просил английские имена, а в коде есть «{russian[0]}». Переименуй по-английски."
    return None


# ---------------------------------------------------------------- урок 10: строки

def _tag_has(text, hint):
    def check(r):
        if text not in r.shop["tags"]:
            got = r.shop["tags"][-1] if r.shop["tags"] else "ничего"
            return f"На ценнике должно быть «{text}», а получилось «{got}». {hint}"
        return None
    return check


def _fill_price(r):
    msg = _tag_has("капуста: 20 руб/кг", "Во вторые скобки — переменную с ценой.")(r)
    if msg:
        return msg
    if "{price}" not in r.code.replace(" ", ""):
        return "Подставь в фигурные скобки переменную price — тогда ценник поменяется сам, если поменяется цена."
    return None


def _fix_f(r):
    if any("{" in t for t in r.shop["tags"]):
        return "На ценнике остались фигурные скобки — Python не подставил значения. Не хватает буквы f перед кавычками."
    return _tag_has("морковь: 50 руб/кг", "")(r)


def _receipt_line(r):
    if not r.lines or r.lines[-1].strip() != "Валя, с вас 90 руб.":
        got = r.lines[-1].strip() if r.lines else "ничего"
        return f"Нужно напечатать «Валя, с вас 90 руб.», а напечатано «{got}»."
    if "90" in r.code:
        return "Число 90 не пиши руками — пусть Python посчитает: {kg * price} прямо внутри f-строки."
    return None


def _quest10(r):
    def check(v):
        inj = v.input["inject"]
        item, price, customers = inj["item"], inj["price"], inj["customers"]
        want_tag = f"{item.capitalize()}: {price} руб/кг"
        if want_tag not in v.shop["tags"]:
            got = v.shop["tags"][-1] if v.shop["tags"] else "ничего"
            return f"Ценник должен быть «{want_tag}» (с большой буквы — .capitalize()), а получился «{got}»."
        return lines_match(v, [f"{name}, {item} сегодня по {price} руб/кг!" for name in customers], "SMS")
    msg = r.each(check)
    if msg:
        return msg
    if r.node_count(ast.For) == 0:
        return "SMS лучше рассылать циклом for по списку customers: завтра покупателей может стать сто."
    return None


def _sms_data(variant):
    data = [("тыква", 30, ["Михалыч", "Даша", "Петя"]),
            ("капуста", 20, ["Нина", "Борис", "Оля", "Гена"]),
            ("морковь", 50, ["Зоя", "Степан"])][variant]
    item, price, customers = data
    return {"inject": {"item": item, "price": price, "customers": customers}}


# ---------------------------------------------------------------- урок 11: словари

def _cabbage_price(r):
    if not r.printed_number(20):
        return "Цена капусты — 20. Ключ пишется в квадратных скобках и в кавычках: prices[\"капуста\"]."
    if "print(20)" in r.code.replace(" ", ""):
        return "Возьми цену из словаря prices, а не вписывай её руками."
    return None


def _pumpkin_price(r):
    if not r.printed_number(30):
        return "Должно напечататься 30 — цена тыквы."
    return None


def _first_customer(r):
    def check(v):
        c = v.input["queue"][0]
        want = c["kg"] * v.input["inject"]["prices"][c["item"]]
        served = v.shop["served"]
        if not served:
            return "Мурзик никому ничего не продал. Нужна команда sell(customer, total)."
        if served[0]["name"] != c["name"]:
            return f"Первым в очереди стоит {c['name']}."
        if not num_eq(served[0]["total"], want):
            return (f"{c['name']} берёт {c['kg']} кг ({c['item']}), это {want} руб., а продано на "
                    f"{_fmt(served[0]['total'])}. Цена — prices[customer[\"item\"]].")
        return None
    return r.each(check)


def _quest11(r):
    def check(v):
        queue, prices = v.input["queue"], v.input["inject"]["prices"]
        served = v.shop["served"]
        if len(served) < len(queue):
            left = [c["name"] for c in queue[len(served):]]
            return f"Не обслужены: {', '.join(left)}. Нужен цикл for по очереди queue."
        for c, s in zip(queue, served):
            want = c["kg"] * prices[c["item"]]
            if s["name"] != c["name"]:
                return "Обслуживай по порядку очереди."
            if not num_eq(s["total"], want):
                return f"{c['name']}: {c['kg']} кг × {prices[c['item']]} руб. = {want} руб., а продано на {_fmt(s['total'])}."
            if not any(c["name"] in line and v.printed_number(want) for line in v.lines):
                return f"Напечатай чек для каждого: имя и сумму. Нет чека для {c['name']} ({want} руб.)."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 12: функции

def _discount(r):
    return call_check(r, "with_discount", [((100,), 90), ((50,), 45)], "скидки")


def _return_fix(r):
    msg = call_check(r, "total_price", [((2, 50), 100), ((3, 30), 90)], "суммы")
    if msg:
        return msg
    if not r.printed_number(100):
        return "Должно напечататься 100."
    return None


def _receipt_fn(r):
    msg = call_check(r, "receipt", [(("Валя", 90), "Валя: 90 руб."), (("Даша", 45), "Даша: 45 руб.")], "чека")
    if msg:
        return msg
    return None


TEST_CUSTOMERS = [({"name": "Тест", "item": "тыква", "kg": 2, "regular": False}, {"тыква": 30}, 60),
                  ({"name": "Тест", "item": "тыква", "kg": 2, "regular": True}, {"тыква": 30}, 54),
                  ({"name": "Тест", "item": "морковь", "kg": 5, "regular": True}, {"морковь": 40}, 180)]


def _quest12(r):
    msg = call_check(r, "total_for", [((c, p), want) for c, p, want in TEST_CUSTOMERS], "функции total_for")
    if msg:
        return msg

    def check(v):
        queue, prices = v.input["queue"], v.input["inject"]["prices"]
        served = v.shop["served"]
        if len(served) != len(queue):
            return f"Обслужено {len(served)} покупателей из {len(queue)}. Пройди циклом по всей очереди."
        for c, s in zip(queue, served):
            want = c["kg"] * prices[c["item"]] * (0.9 if c["regular"] else 1)
            if not num_eq(s["total"], want):
                kind = "постоянный покупатель — со скидкой 10%" if c["regular"] else "без скидки"
                return f"{c['name']} ({kind}): должно быть {_fmt(want)} руб., а продано на {_fmt(s['total'])}."
        return None
    return r.each(check)


EN = dict(chapter=3, robot="murzik", kits=["shop"], lang="en", zone="shop", beds=[], data=_shop)

LESSONS = [
    Lesson(
        id="english", title="По-английски", topic="английские имена в коде", chapter=3, robot="bublik",
        kits=["garden"], lang="en", field_var="field", zone="field", beds=[], data=_field, unlock=["stall_repaired"],
        notes="Имена в коде пишут по-английски: field (поле), bed (грядка), water (полить), harvest (собрать),\n"
              "humidity (влажность), ripe (спелая), crop (культура), name (название), price (цена), total (итого).\n"
              "Данные остаются русскими: \"тыква\" так и осталась \"тыква\".",
        steps=[
            Step("look", "Мурзик — кот городской и понимает только английские имена. И не он один: программисты "
                         "всего мира пишут названия по-английски. Так код поймёт любой человек на планете, а готовые "
                         "модули Python (`csv`, `json`, `datetime`) уже названы по-английски. Слов немного:",
                 code="# поле → field         грядка → bed\n# полить → water       собрать → harvest\n"
                      "# влажность → humidity  спелая → ripe\n# культура → crop      название → name",
                 portrait="explain"),
            Step("run", "Вот программа из главы 2 — по-английски. Запусти. Наведи мышку на английское слово в "
                        "редакторе — появится перевод.",
                 code='for bed in field:\n    if bed["humidity"] < 40:\n        water(bed)', portrait="calm",
                 show_memory=True, after="Тот же код, только по-английски. Бублик понял и так, и так."),
            Step("fill", "Собери спелые грядки. Как будет «собрать» по-английски?",
                 code='for bed in field:\n    if bed["ripe"]:\n        ____(bed)', check=_harvest_ripe,
                 portrait="calm", success="harvest — «собирать урожай». Отлично!",
                 hints=["Посмотри табличку из первого шага: собрать → …", "harvest(bed)"]),
            Step("fix", "Python ругается: такого ключа нет! Данные грядки теперь с английскими ключами. "
                        "Нажми «Рентген» (R) и посмотри, как называется влажность.",
                 code='for bed in field:\n    if bed["влажность"] < 40:\n        water(bed)', check=_water_dry_en,
                 portrait="frown", success="Ключ «humidity» — всё заработало.",
                 hints=["В рентгене у грядки ключи name, crop, humidity, ripe.", 'bed["humidity"]']),
            Step("write", "Напечатай названия всех грядок, где растёт тыква. Названия культур остались русскими: "
                          "`\"тыква\"`. А название грядки лежит в `bed[\"name\"]`.",
                 code="for bed in field:\n    # если культура — тыква, напечатай название грядки\n",
                 check=_pumpkins, portrait="calm", success="Код английский, данные русские — так и пишут на работе.",
                 hints=['if bed["crop"] == "тыква":', 'Внутри if: print(bed["name"])']),
        ],
        quest=Quest(
            giver="Мурзик",
            note="«Мяу. Мне в лавку нужен товар. Полей сухие грядки, собери спелые и напечатай, сколько всего "
                 "килограммов. Только по-английски, пожалуйста: я по-русски не читаю».",
            goals=["Полить сухие грядки (humidity меньше 40)", "Собрать спелые (ripe)",
                   "Напечатать общий вес", "Все имена — английские"],
            starter="total = 0\nfor bed in field:\n    # полей сухие, собери спелые, прибавь вес к total\n",
            check=_quest9, data=_field, variants=2,
            solution='total = 0\nfor bed in field:\n    if bed["humidity"] < 40:\n        water(bed)\n'
                     '    if bed["ripe"]:\n        total = total + harvest(bed)\nprint("Собрано кг:", total)',
            breakdown=[("total = 0", "total — «итого». Счётчик, как в главе 2."),
                       ("for bed in field:", "Для каждой грядки (bed) в поле (field)…"),
                       ('    if bed["humidity"] < 40:', "humidity — «влажность»."),
                       ("        water(bed)", "water — «полить»."),
                       ('    if bed["ripe"]:', "ripe — «спелая»."),
                       ("        total = total + harvest(bed)", "harvest возвращает килограммы — сразу прибавляем.")],
            alternative="Вместо total = total + harvest(bed) можно короче: total += harvest(bed).",
            life_title="Английский в коде",
            life=["Почти весь код в мире — на английском: так программисты из разных стран работают вместе.",
                  "Названия в чужих программах и библиотеках тоже английские. Зная два десятка слов, ты уже читаешь их.",
                  "Комментарии и тексты для людей можно писать по-русски — это нормально."],
            try_at_home=["Открой скрипт бублик.py из папки «Робоферма/скрипты» в TextEdit.",
                          "Сравни русские и английские имена — смысл тот же."],
            reward=25, hints=["Внутри цикла два if: про humidity и про ripe.",
                              'В if bed["ripe"]: — total = total + harvest(bed). После цикла — print.'],
            success="Мурзик: «Мур-р. Сорок кило — и всё по-английски. Можно открывать лавку!»"),
    ),
    Lesson(
        id="strings", title="Строки и ценники", topic="строки и f-строки", **EN,
        notes="**\"текст\"** — строка (str). Склеить: **\"а\" + \"б\"**. Число → текст: **str(30)**.\n"
              "**f\"{item}: {price} руб\"** — f-строка: в фигурные скобки Python подставит значения.\n"
              "Методы строк: **.upper()** — ВСЕ БОЛЬШИЕ, **.capitalize()** — С большой, **len(текст)** — длина.",
        steps=[
            Step("look", "Мурзик продаёт урожай и вешает ценники. Ценник — это **строка** (по-английски str): текст "
                         "в кавычках. Строки можно склеивать знаком `+`.",
                 code='item = "тыква"\ntext = "Свежая " + item\nprint(text)   # Свежая тыква', portrait="explain"),
            Step("run", "Команда `tag(текст)` вешает ценник на прилавок. Запусти!",
                 code='item = "тыква"\nprice = 30\ntag(item + ": " + str(price) + " руб/кг")', portrait="calm",
                 show_memory=True,
                 after="Ценник висит! str(price) превращает число 30 в текст «30»: склеивать можно только текст с текстом."),
            Step("look", "Склеивать плюсами неудобно. Есть способ лучше — **f-строка**: буква `f` перед кавычками, "
                         "а внутри в фигурных скобках — переменные. Python сам подставит значения и сам превратит числа в текст.",
                 code='item = "тыква"\nprice = 30\ntag(f"{item}: {price} руб/кг")   # тыква: 30 руб/кг', portrait="explain"),
            Step("fill", "Повесь ценник на капусту. Что подставить во вторые скобки?",
                 code='item = "капуста"\nprice = 20\ntag(f"{item}: {____} руб/кг")',
                 check=_fill_price, portrait="calm",
                 success="капуста: 20 руб/кг — как в магазине!", hints=["Как называется переменная с ценой?", "{price}"]),
            Step("fix", "Мурзик повесил странный ценник с фигурными скобками. Почему Python не подставил значения?",
                 code='item = "морковь"\nprice = 50\ntag("{item}: {price} руб/кг")', check=_fix_f, portrait="frown",
                 success="Без буквы f это обычный текст со скобками. С ней — шаблон.",
                 hints=["Чем f-строка отличается от обычной?", 'tag(f"{item}: {price} руб/кг")']),
            Step("run", "У строк есть свои команды — **методы**. Они пишутся через точку после строки.",
                 code='item = "тыква"\nprint(item.upper())\nprint(item.capitalize())\nprint(len(item))',
                 portrait="calm", after="upper() — все буквы большие, capitalize() — первая большая, len() — сколько букв."),
            Step("write", "Напечатай чек: «Валя, с вас 90 руб.». Сумму не пиши руками — посчитай прямо в f-строке: "
                          "внутри скобок можно писать выражения, например `{kg * price}`.",
                 code='name = "Валя"\nkg = 3\nprice = 30\n# напечатай: Валя, с вас 90 руб.\n',
                 check=_receipt_line, portrait="calm", success="Шаблон + данные = готовый чек.",
                 hints=['print(f"{name}, с вас … руб.")', 'print(f"{name}, с вас {kg * price} руб.")']),
        ],
        quest=Quest(
            giver="Записка от тёти Вали",
            note="«Мурзик, повесь ценник на сегодняшний товар — с большой буквы, вот так: „Тыква: 30 руб/кг“. "
                 "И разошли SMS всем постоянным покупателям из списка: „Михалыч, тыква сегодня по 30 руб/кг!“ "
                 "Товар, цена и список у тебя уже есть: item, price, customers».",
            goals=["Ценник через tag() и f-строку, товар с большой буквы",
                   "SMS каждому из customers — циклом for", "Текст SMS — точно по образцу"],
            starter="# Переменные item, price и customers уже есть: их дала тётя Валя.\n"
                    "# 1) ценник: tag(f\"...\")\n# 2) SMS каждому: for name in customers:\n",
            check=_quest10, data=_sms_data, variants=2,
            solution='tag(f"{item.capitalize()}: {price} руб/кг")\nfor name in customers:\n'
                     '    print(f"{name}, {item} сегодня по {price} руб/кг!")',
            breakdown=[('tag(f"{item.capitalize()}: {price} руб/кг")',
                        "Метод .capitalize() можно вызывать прямо внутри фигурных скобок."),
                       ("for name in customers:", "Для каждого имени в списке покупателей…"),
                       ('    print(f"{name}, {item} сегодня по {price} руб/кг!")',
                        "…одна и та же f-строка, но с разным именем. Это и есть шаблон рассылки.")],
            alternative="Текст SMS можно сначала положить в переменную: sms = f\"...\", а потом print(sms). "
                        "Так удобнее, если его нужно ещё и записать в файл.",
            life_title="Шаблоны в жизни",
            life=["Рассылки «Здравствуйте, {имя}! Ваш заказ №{номер} готов» — это f-строки.",
                  "Ценники, этикетки, счета и договоры с подставленными данными делают по шаблону.",
                  "В Excel то же самое делает функция СЦЕП, а в Python — f-строка, и она понятнее."],
            try_at_home=["Терминал → python3.", 'name = "Аня"', 'print(f"Привет, {name}! Сегодня {2 + 3} задач.")'],
            reward=30, hints=['Ценник: tag(f"{item.capitalize()}: {price} руб/кг")',
                              'Цикл: for name in customers: — внутри print(f"{name}, {item} сегодня по {price} руб/кг!")'],
            success="Тётя Валя: «Все SMS дошли! Михалыч уже идёт с тележкой»."),
    ),
    Lesson(
        id="dicts", title="Словари", topic="словари: ключ → значение", **EN,
        notes="**{\"тыква\": 30, \"капуста\": 20}** — словарь (dict): ключ → значение.\n"
              "**prices[\"тыква\"]** — достать по ключу. **prices[\"яблоки\"] = 40** — добавить или изменить.\n"
              "**for key, value in prices.items():** — пройти по всем парам.",
        steps=[
            Step("look", "Цен много, и у каждой — свой товар. Для этого есть **словарь** (dict). Ты уже "
                         "{пользовался|пользовалась} словарями — грядка была словарём! Словарь — как шкаф с "
                         "подписанными ящиками: по подписи (**ключу**) достаём **значение**.",
                 code='prices = {"морковь": 50, "тыква": 30, "капуста": 20}\nprint(prices["тыква"])   # 30',
                 portrait="explain"),
            Step("run", "Запусти и посмотри в «Память»: словарь нарисован шкафом с ящиками.",
                 code='prices = {"морковь": 50, "тыква": 30}\nprices["яблоки"] = 40\nprices["тыква"] = 25\nprint(prices)',
                 portrait="calm", show_memory=True,
                 after="Присвоение по новому ключу добавило ящик «яблоки», по старому — поменяло цену тыквы."),
            Step("fill", "Покупатель спрашивает: почём капуста? Достань цену из словаря.",
                 code='prices = {"морковь": 50, "тыква": 30, "капуста": 20}\nprint(prices[____])',
                 check=_cabbage_price, portrait="calm", show_memory=True,
                 success="Ключ — в кавычках, потому что это строка.", hints=["Ключ — название товара.", 'prices["капуста"]']),
            Step("fix", "Ошибка KeyError — «нет такого ключа». А тыква ведь есть! Найди отличие.",
                 code='prices = {"морковь": 50, "тыква": 30, "капуста": 20}\nprint(prices["Тыква"])',
                 check=_pumpkin_price, portrait="frown",
                 success="Ключ должен совпадать буква в букву: «Тыква» и «тыква» — разные ключи.",
                 hints=["Сравни ключ в словаре и в квадратных скобках.", "С маленькой буквы: \"тыква\"."]),
            Step("run", "По словарю можно пройти циклом: `.items()` даёт пары «ключ — значение». Повесим все ценники сразу!",
                 code='prices = {"морковь": 50, "тыква": 30, "капуста": 20}\nfor item, price in prices.items():\n'
                      '    tag(f"{item}: {price} руб/кг")',
                 portrait="calm", show_memory=True, after="Три ценника — одна строчка в цикле."),
            Step("look", "К лавке выстроилась очередь! Она лежит в переменной `queue` — это список словарей. Включи "
                         "«Рентген» (R), чтобы увидеть её глазами Мурзика. А цены лежат в `prices`.",
                 code='customer = queue[0]\nprint(customer["name"])   # Валя\nprint(customer["item"])   # тыква\n'
                      'print(customer["kg"])     # 3',
                 portrait="explain"),
            Step("write", "Обслужи первого покупателя: посчитай сумму (килограммы × цена товара из `prices`) и продай "
                          "командой `sell(customer, total)`.",
                 code="customer = queue[0]\n# total = килограммы × цена товара\n", check=_first_customer,
                 portrait="calm", show_memory=True, variants=2, success="Мур-р! Первая продажа!",
                 hints=['Цена товара: prices[customer["item"]]', 'total = customer["kg"] * prices[customer["item"]]\nsell(customer, total)']),
        ],
        quest=Quest(
            giver="Записка от тёти Вали",
            note="«Мурзик, обслужи всю очередь: каждому продай столько, сколько просит, по ценам из prices. "
                 "И каждому напечатай чек: имя и сумму. Например: „Валя: 90 руб.“»",
            goals=["Продать каждому в очереди queue", "Сумма = кг × цена из prices", "Чек каждому: имя и сумма"],
            starter="for customer in queue:\n    # сумма, продажа и чек\n",
            check=_quest11, data=_shop, variants=2,
            solution='for customer in queue:\n    price = prices[customer["item"]]\n    total = customer["kg"] * price\n'
                     '    sell(customer, total)\n    print(f"{customer[\'name\']}: {total} руб.")',
            breakdown=[("for customer in queue:", "Для каждого покупателя в очереди…"),
                       ('    price = prices[customer["item"]]', "Достаём цену его товара: ключ — это то, что он хочет."),
                       ('    total = customer["kg"] * price', "Сумма = килограммы × цена."),
                       ("    sell(customer, total)", "Продаём."),
                       ('    print(f"{customer[\'name\']}: {total} руб.")',
                        "Внутри f-строки в двойных кавычках ключ пишем в одинарных: 'name'.")],
            alternative="Можно сначала достать имя: name = customer[\"name\"], а потом print(f\"{name}: {total} руб.\") — "
                        "так не нужно думать про кавычки.",
            life_title="Словари в жизни",
            life=["Прайс-лист, телефонная книга, настройки программы — это словари: ключ → значение.",
                  "Данные с сайтов (заказы, погода, курсы валют) приходят как словари — это будет в главе 5.",
                  "Строка таблицы с заголовками — тоже словарь: «Дата» → 01.09, «Сумма» → 500."],
            try_at_home=["Терминал → python3.", 'phones = {"мама": "+7 900 000-00-01", "Петя": "+7 900 000-00-02"}',
                          'print(phones["мама"])'],
            reward=35, hints=['Цена: prices[customer["item"]], сумма: customer["kg"] * цена.',
                              "Внутри цикла: посчитать total, sell(customer, total), потом print с именем и суммой."],
            success="Тётя Валя: «Очередь разошлась за минуту! Мурзик, ты лучший продавец района»."),
    ),
    Lesson(
        id="functions", title="Свои функции", topic="def, параметры и return", **EN,
        notes="**def name(params):** — создать свою функцию (команду). Тело — с отступом.\n"
              "**return значение** — вернуть результат: **total = total_price(3, 30)**.\n"
              "Без return функция возвращает **None** — «ничего».",
        steps=[
            Step("look", "Ты уже {пользовался|пользовалась} чужими функциями: print, len, water. Теперь сделаем свою! "
                         "**def** — «определить». В скобках — **параметры**: значения, которые передают при вызове. "
                         "Тело функции — с отступом.",
                 code='def greet(name):\n    print(f"Здравствуйте, {name}! Мур!")\n\ngreet("Валя")\ngreet("Михалыч")',
                 portrait="explain"),
            Step("run", "Запусти и нажимай «Шаг»: видно, как Python прыгает внутрь функции при каждом вызове.",
                 code='def greet(name):\n    print(f"Здравствуйте, {name}! Мур!")\n\ngreet("Валя")\ngreet("Михалыч")',
                 portrait="calm", show_memory=True,
                 after="Одна функция — два приветствия. Чтобы поменять текст, править нужно одно место."),
            Step("look", "**return** — «вернуть»: функция отдаёт результат, и его можно положить в переменную. "
                         "Как собрать() отдавал килограммы.",
                 code="def total_price(kg, price):\n    return kg * price\n\ntotal = total_price(3, 30)\nprint(total)   # 90",
                 portrait="explain"),
            Step("fill", "Постоянным покупателям — скидка 10%. Цена со скидкой — это 90% цены, то есть цена × 0.9. "
                         "Допиши функцию.",
                 code="def with_discount(price):\n    return price * ____\n\nprint(with_discount(100))",
                 check=_discount, portrait="calm", calls=[{"fn": "with_discount", "args": [100]},
                                                          {"fn": "with_discount", "args": [50]}],
                 success="with_discount(100) = 90. Дробные числа пишутся через точку: 0.9.",
                 hints=["10% скидки — платим 90%.", "return price * 0.9"]),
            Step("fix", "Мурзик напечатал None — «ничего». Функция считает, но результат не отдаёт. Исправь.",
                 code="def total_price(kg, price):\n    kg * price\n\nprint(total_price(2, 50))",
                 check=_return_fix, portrait="frown", calls=[{"fn": "total_price", "args": [2, 50]},
                                                             {"fn": "total_price", "args": [3, 30]}],
                 success="Без return результат теряется. С return — возвращается.",
                 hints=["Какого слова не хватает перед kg * price?", "return kg * price"]),
            Step("write", "Напиши функцию `receipt(name, total)`, которая **возвращает** (не печатает!) строку чека, "
                          "например «Валя: 90 руб.».",
                 code="# def receipt(name, total):\n", check=_receipt_fn, portrait="calm",
                 calls=[{"fn": "receipt", "args": ["Валя", 90]}, {"fn": "receipt", "args": ["Даша", 45]}],
                 success="Функция, которая возвращает текст, пригодится и для печати, и для SMS, и для файла.",
                 hints=["def receipt(name, total):", 'def receipt(name, total):\n    return f"{name}: {total} руб."']),
        ],
        quest=Quest(
            giver="Записка от тёти Вали",
            note="«Постоянным покупателям (у них regular = True) — скидка 10%. Напиши функцию total_for(customer, prices), "
                 "которая возвращает сумму к оплате — со скидкой или без. И обслужи с ней всю очередь».",
            goals=["Функция total_for(customer, prices) возвращает сумму",
                   "Постоянным (regular) — скидка 10%", "Продать всей очереди: sell(customer, total_for(...))"],
            starter="def total_for(customer, prices):\n    # сумма = кг × цена; постоянным — × 0.9\n\n\n"
                    "for customer in queue:\n    # продай, посчитав сумму функцией total_for\n",
            check=_quest12, data=_shop, variants=2,
            calls=[{"fn": "total_for", "args": [c, p]} for c, p, _ in TEST_CUSTOMERS],
            solution='def total_for(customer, prices):\n    total = customer["kg"] * prices[customer["item"]]\n'
                     '    if customer["regular"]:\n        total = total * 0.9\n    return total\n\n\n'
                     'for customer in queue:\n    sell(customer, total_for(customer, prices))',
            breakdown=[("def total_for(customer, prices):", "Функция с двумя параметрами: покупатель и цены."),
                       ('    total = customer["kg"] * prices[customer["item"]]', "Обычная сумма — как в прошлом уроке."),
                       ('    if customer["regular"]:', "Постоянный покупатель?"),
                       ("        total = total * 0.9", "Тогда 90% от суммы."),
                       ("    return total", "Отдаём результат."),
                       ("    sell(customer, total_for(customer, prices))", "Результат функции сразу идёт в sell.")],
            alternative="Скидку можно вынести в параметр: def total_for(customer, prices, discount=0.1): — "
                        "тогда на распродаже достаточно вызвать total_for(c, prices, 0.3).",
            life_title="Функции в жизни",
            life=["Функция — это «рецепт», который пишут один раз и вызывают сколько угодно: посчитать налог, скидку, доставку.",
                  "Все команды, которыми ты {пользовался|пользовалась}, — функции, которые написали другие люди.",
                  "Большие программы состоят из сотен маленьких функций, и каждую можно проверить отдельно — "
                  "как игра проверила твою total_for на тестовых покупателях."],
            try_at_home=["Терминал → python3.", "def vat(price): return price * 0.2  (Enter дважды)",
                          "print(vat(1000))"],
            reward=40, hints=['Внутри функции: total = customer["kg"] * prices[customer["item"]]; если regular — умножь на 0.9; return total.',
                              "Цикл: for customer in queue: sell(customer, total_for(customer, prices))"],
            success="Тётя Валя: «Постоянные покупатели в восторге! Лавке нужен склад — пора в амбар»."),
    ),
]

CHAPTER = Chapter(
    number=3, title="Лавка", zone="shop", robot="murzik", lessons=LESSONS,
    intro=[("klusha", "happy", "Тётя Валя помогла открыть лавку у дороги! Продавать будет бабушкин робокот Мурзик."),
           ("murzik", "happy", "Мур. Я кот городской, учился в Лондоне. По-русски в коде не понимаю, только по-английски."),
           ("klusha", "explain", "Это правда полезно: так пишут программисты во всём мире. Сначала переведём скрипт "
                                 "Бублика, а потом — ценники, чеки и скидки.")],
    outro=[("murzik", "happy", "Мур-р! Очередь обслужена, ценники висят, постоянные покупатели довольны."),
           ("klusha", "proud", "Строки, f-строки, словари, свои функции — ты {пишешь|пишешь} как настоящий программист."),
           ("klusha", "explain", "Товара становится много — нужен учёт. В амбаре нас ждёт бобр Бобр: он хранит всё в файлах.")],
    automation=("Мурзик торгует в лавке", 15),
)
