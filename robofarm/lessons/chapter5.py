"""Глава 5. «Почта»: JSON, вложенные данные, сортировка, даты."""

from datetime import date

from robofarm.lessons.base import Chapter, Lesson, Quest, Step
from robofarm.lessons.common import TODAY, order_total, orders, orders_json

OVERDUE = 3  # заказ, который ждёт дольше стольких дней, — просрочен


def _post(variant):
    data = orders(variant)
    return {"files": {"orders.json": orders_json(data)}, "orders": data, "expect": {"orders": data}}


def _orders(v):
    return v.data["orders"]


def _days(o):
    return (date.fromisoformat(TODAY) - date.fromisoformat(o["date"])).days


def _line_order(r, ids):
    """Номера заказов в том порядке, в каком они встречаются в напечатанных строках."""
    seen = []
    for line in r.lines:
        for i in ids:
            if str(i) in line and i not in seen:
                seen.append(i)
    return seen


LOAD = 'import json\n\nwith open("orders.json", encoding="utf-8") as f:\n    orders = json.load(f)\n'


# ---------------------------------------------------------------- урок 17: JSON

def _first_name(r):
    def check(v):
        name = _orders(v)[0]["customer"]["name"]
        if not any(line.strip() == name for line in v.lines):
            return f"Первый заказ сделал(а) {name} — это и нужно напечатать. Имя лежит по ключу \"name\"."
        return None
    return r.each(check)


def _first_id(r):
    def check(v):
        oid = _orders(v)[0]["id"]
        if not v.printed_number(oid):
            return f"Номер первого заказа — {oid}. Сначала выбери заказ: orders[0], потом ключ: [\"id\"]."
        return None
    return r.each(check)


def _quest17(r):
    def check(v):
        paid = [o["id"] for o in _orders(v) if o["paid"]]
        got = v.post["delivered"]
        extra = [i for i in got if i not in paid]
        if extra:
            return f"Заказ №{extra[0]} не оплачен (\"paid\": false) — его возить не нужно."
        missing = [i for i in paid if i not in got]
        if missing:
            return f"Не доставлен оплаченный заказ №{missing[0]}."
        if not any("доставлено" in line.lower() and str(len(paid)) in line for line in v.lines):
            return f"В конце напечатай: «Доставлено: {len(paid)}». Заведи счётчик."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 18: вложенные данные

def _first_total(r):
    def check(v):
        total = order_total(_orders(v)[0])
        if not v.printed_number(total):
            return f"Первый заказ стоит {total} руб. Для каждого товара: item[\"kg\"] * item[\"price\"]."
        return None
    return r.each(check)


def _weights(r):
    def check(v):
        for o in _orders(v):
            kg = sum(i["kg"] for i in o["items"])
            if not any(str(o["id"]) in line and str(kg) in line.replace(str(o["id"]), "", 1) for line in v.lines):
                return f"Нет строки для заказа {o['id']}: «Заказ {o['id']}: {kg} кг»."
        return None
    return r.each(check)


def _quest18(r):
    def check(v):
        want = [o["id"] for o in _orders(v) if o["paid"] and order_total(o) >= 150]
        got = v.post["delivered"]
        for o in _orders(v):
            t = order_total(o)
            if o["id"] in got and o["id"] not in want:
                why = "не оплачен" if not o["paid"] else f"дешевле 150 руб. ({t})"
                return f"Заказ №{o['id']} {why} — его не везём."
            if o["id"] in want and o["id"] not in got:
                return f"Заказ №{o['id']} оплачен и стоит {t} руб. — его нужно доставить."
            name = o["customer"]["name"]
            if not any(str(o["id"]) in line and name in line and str(t) in line for line in v.lines):
                return f"Нет чека для заказа {o['id']}: «Заказ {o['id']}, {name}: {t} руб.»."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 19: сортировка

def _route_printed(r):
    def check(v):
        ids = [o["id"] for o in sorted(_orders(v), key=lambda o: o["customer"]["km"])]
        if _line_order(v, ids) != ids:
            return f"Заказы должны идти от ближнего к дальнему: {', '.join(map(str, ids))}."
        return None
    return r.each(check)


def _farthest(r):
    def check(v):
        far = max(_orders(v), key=lambda o: o["customer"]["km"])["customer"]["name"]
        if not v.printed(far):
            return f"Дальше всех живёт {far}. max(orders, key=distance) вернёт самый дальний заказ."
        return None
    return r.each(check)


def _quest19(r):
    def check(v):
        paid = sorted((o for o in _orders(v) if o["paid"]), key=lambda o: o["customer"]["km"])
        want = [o["id"] for o in paid]
        got = v.post["delivered"]
        if sorted(got) != sorted(want):
            return f"Доставить нужно все оплаченные заказы, и только их: {', '.join(map(str, want))}."
        if got != want:
            return (f"Порядок не тот: Искра ехала {', '.join(map(str, got))}, а от ближнего к дальнему — "
                    f"{', '.join(map(str, want))}. Отсортируй по km.")
        return None
    msg = r.each(check)
    if msg:
        return msg
    if not r.uses("sorted") and not r.uses("sort"):
        return "Порядок угадан, но завтра заказы будут другими. Отсортируй их: sorted(..., key=...)."
    return None


# ---------------------------------------------------------------- урок 20: даты

def _first_days(r):
    def check(v):
        days = _days(_orders(v)[0])
        if not v.printed_number(days):
            return f"Первый заказ ждёт {days} дн. Дата заказа лежит по ключу \"date\"."
        return None
    return r.each(check)


def _overdue_list(r):
    def check(v):
        for o in _orders(v):
            late = _days(o) > OVERDUE
            shown = any(str(o["id"]) in line for line in v.lines)
            if late and not shown:
                return f"Заказ {o['id']} ждёт {_days(o)} дн. — он просрочен, его нужно напечатать."
            if shown and not late:
                return f"Заказ {o['id']} ждёт всего {_days(o)} дн. — он не просрочен."
        return None
    return r.each(check)


def _quest20(r):
    def check(v):
        late = [o for o in _orders(v) if o["paid"] and _days(o) > OVERDUE]
        want = {o["id"] for o in late}
        got = v.post["delivered"]
        if set(got) != want:
            return (f"Срочно доставить нужно оплаченные заказы старше {OVERDUE} дней: "
                    f"{', '.join(map(str, sorted(want)))}.")
        dates = [next(o["date"] for o in late if o["id"] == i) for i in got]
        if dates != sorted(dates):
            return "Вези сначала самые старые заказы: отсортируй по дате."
        for o in late:
            if not any(str(o["id"]) in line and str(_days(o)) in line.replace(str(o["id"]), "", 1) for line in v.lines):
                return f"Напечатай для заказа {o['id']}, сколько дней он ждёт: {_days(o)}."
        return None
    return r.each(check)


POST = dict(chapter=5, robot="iskra", kits=["post"], lang="en", zone="post", beds=[], folder="почта", data=_post)

LESSONS = [
    Lesson(
        id="json", title="Заказы в JSON", topic="JSON: данные с сайтов", unlock=["post_repaired"], **POST,
        notes="**JSON** — формат, в котором общаются сайты и приложения. {…} — словарь, […] — список.\n"
              "**import json** и **orders = json.load(f)** — прочитать JSON-файл в обычные списки и словари.\n"
              "true/false/null в JSON = True/False/None в Python.",
        steps=[
            Step("look", "Тётя Валя открыла интернет-магазин! Заказы с сайта приходят в файле **orders.json**. "
                         "JSON — это язык, на котором общаются сайты и приложения: так приходят погода, курсы валют, "
                         "заказы с маркетплейсов и сообщения Telegram. Он очень похож на Python: словари в фигурных "
                         "скобках, списки — в квадратных.",
                 code='[\n  {"id": 101, "date": "2024-09-15", "paid": true,\n'
                      '   "customer": {"name": "Даша", "house": 1, "km": 2.5},\n'
                      '   "items": [{"name": "тыква", "kg": 3, "price": 30}]}\n]', portrait="explain"),
            Step("run", "Модуль `json` превращает текст файла в обычные списки и словари Python.",
                 code=LOAD + "print(len(orders))\nprint(orders[0][\"id\"])", portrait="calm", show_memory=True,
                 after="json.load прочитал файл — дальше это обычный список словарей. Открой orders.json в TextEdit и сравни."),
            Step("fill", "Кто сделал первый заказ? Покупатель — словарь внутри заказа. Напечатай его имя.",
                 code=LOAD + "print(orders[0][\"customer\"][____])", check=_first_name, portrait="calm",
                 show_memory=True, variants=2, success="Две пары скобок — два шага вглубь: заказ → покупатель → имя.",
                 hints=["Посмотри в JSON: у покупателя есть name, house и km.", 'orders[0]["customer"]["name"]']),
            Step("fix", "Нужно напечатать номер первого заказа, а Python ругается. orders — это список, а не словарь!",
                 code=LOAD + "print(orders[\"id\"])", check=_first_id, portrait="frown", variants=2,
                 success="Сначала номер в списке [0], потом ключ [\"id\"].",
                 hints=["У списка элементы по номерам: orders[0].", 'print(orders[0]["id"])']),
            Step("run", "Команда `deliver(номер)` отправляет Искру с заказом к дому покупателя. Развезём все!",
                 code=LOAD + "for order in orders:\n    deliver(order[\"id\"])", portrait="calm",
                 after="Цок-цок! Искра объехала всю деревню."),
        ],
        quest=Quest(
            giver="Почтальонка Даша",
            note="«Ой, Искра, ты развозишь даже неоплаченные заказы! Вези только те, где \"paid\": true. "
                 "А в конце напиши, сколько доставлено: „Доставлено: 4“».",
            goals=["Прочитать orders.json", "Доставить только оплаченные (paid)", "Напечатать «Доставлено: N»"],
            starter=LOAD + "count = 0\nfor order in orders:\n    # только оплаченные\n",
            check=_quest17, variants=2,
            solution=LOAD + 'count = 0\nfor order in orders:\n    if order["paid"]:\n        deliver(order["id"])\n'
                     '        count = count + 1\nprint("Доставлено:", count)',
            breakdown=[("    orders = json.load(f)", "Файл JSON → список словарей."),
                       ('    if order["paid"]:', "В JSON было true, в Python стало True — можно сразу в if."),
                       ('        deliver(order["id"])', "Везём по номеру заказа."),
                       ("        count = count + 1", "Счётчик доставленных.")],
            alternative="Сначала можно отобрать оплаченные в отдельный список: paid = [] и paid.append(order) в цикле, "
                        "а потом len(paid) — сразу видно, сколько.",
            life_title="JSON в жизни",
            life=["Любой сайт и приложение общаются через JSON: погода, курсы валют, карты, маркетплейсы, банки.",
                  "Выгрузки из интернет-магазина, CRM и Telegram-ботов — тоже JSON.",
                  "Умея читать JSON, ты можешь достать данные почти из любого сервиса."],
            try_at_home=["cd ~/Documents/Робоферма/почта", "python3 искра.py — без игры deliver просто печатает номер.",
                          "Открой orders.json в TextEdit и добавь заказ — запусти ещё раз."],
            reward=45, hints=['if order["paid"]: — а внутри deliver и count = count + 1.',
                              'После цикла: print("Доставлено:", count)'],
            success="Даша: «Вот это порядок! Неоплаченные подождут на почте»."),
    ),
    Lesson(
        id="nested", title="Вложенные данные", topic="списки внутри словарей", **POST,
        notes="Данные бывают вложенными: **order[\"customer\"][\"name\"]**, **order[\"items\"][0][\"kg\"]**.\n"
              "Шагаем вглубь по одной паре скобок. Список внутри словаря обходим вложенным циклом:\n"
              "**for item in order[\"items\"]:**",
        steps=[
            Step("look", "В заказе лежит не одно значение, а целое дерево: покупатель — словарь, товары — **список** "
                         "словарей. Добираемся до нужного по шагам.",
                 code='order = orders[0]\norder["customer"]["name"]     # "Даша"\norder["items"]                # список товаров\n'
                      'order["items"][0]["name"]     # первый товар: "тыква"', portrait="explain"),
            Step("run", "Пройдём циклом по товарам первого заказа.",
                 code=LOAD + 'order = orders[0]\nfor item in order["items"]:\n    print(item["name"], item["kg"], "кг")',
                 portrait="calm", show_memory=True, after="Цикл по списку, который лежит внутри словаря."),
            Step("fill", "Посчитай, сколько стоит первый заказ: для каждого товара килограммы × цена.",
                 code=LOAD + 'total = 0\nfor item in orders[0]["items"]:\n    total = total + item["kg"] * item[____]\nprint(total)',
                 check=_first_total, portrait="calm", show_memory=True, variants=2, success="Сумма заказа посчитана!",
                 hints=['У товара есть name, kg и price.', 'item["price"]']),
            Step("write", "Напечатай вес каждого заказа: «Заказ 101: 4 кг». Понадобится цикл внутри цикла.",
                 code=LOAD + "for order in orders:\n    kg = 0\n    # цикл по товарам заказа\n",
                 check=_weights, portrait="calm", variants=2, success="Цикл в цикле — обычное дело для вложенных данных.",
                 hints=['for item in order["items"]: kg = kg + item["kg"]',
                        'После внутреннего цикла (отступ как у kg = 0): print(f"Заказ {order[\'id\']}: {kg} кг")']),
        ],
        quest=Quest(
            giver="Почтальонка Даша",
            note="«Искра возит только оплаченные заказы от 150 рублей — мелкие заберут на почте сами. "
                 "И распечатай чек на каждый заказ: „Заказ 101, Даша: 230 руб.“».",
            goals=["Посчитать сумму каждого заказа", "Чек на каждый заказ: номер, имя, сумма",
                   "Доставить оплаченные заказы от 150 руб."],
            starter=LOAD + "for order in orders:\n    total = 0\n    # сумма заказа, чек, доставка\n",
            check=_quest18, variants=2,
            solution=LOAD + 'for order in orders:\n    total = 0\n    for item in order["items"]:\n'
                     '        total = total + item["kg"] * item["price"]\n    name = order["customer"]["name"]\n'
                     '    print(f"Заказ {order[\'id\']}, {name}: {total} руб.")\n'
                     '    if order["paid"] and total >= 150:\n        deliver(order["id"])',
            breakdown=[('    for item in order["items"]:', "Вложенный цикл — по товарам одного заказа."),
                       ('        total = total + item["kg"] * item["price"]', "Сумма заказа."),
                       ('    name = order["customer"]["name"]', "Имя достаём заранее — так f-строка проще."),
                       ('    if order["paid"] and total >= 150:', "Два условия сразу — через and."),
                       ('        deliver(order["id"])', "Везём.")],
            alternative="Сумму заказа удобно вынести в функцию: def order_total(order): … return total — "
                        "тогда её можно использовать и в чеках, и в отчётах.",
            life_title="Вложенные данные в жизни",
            life=["Заказ с маркетплейса: покупатель, адрес, список товаров, у каждого — цена и количество. Всё вложено.",
                  "Ответы сайтов почти всегда «деревья»: погода по дням, по часам, с ветром и осадками.",
                  "Главный навык — шагать вглубь по одной паре скобок и смотреть, что там: словарь или список."],
            try_at_home=["Терминал → python3.", 'order = {"items": [{"kg": 2, "price": 30}, {"kg": 1, "price": 50}]}',
                          'print(sum(i["kg"] * i["price"] for i in order["items"]))'],
            reward=50, hints=["Внутри цикла по заказам: вложенный цикл по товарам считает total.",
                              'Потом print(...) и if order["paid"] and total >= 150: deliver(order["id"])'],
            success="Даша: «Чеки — как из кассы! А мелкие заказы люди заберут сами, им по пути»."),
    ),
    Lesson(
        id="sorting", title="Маршрут", topic="sorted, min, max и key=", **POST,
        notes="**sorted(список)** — новый список по порядку, **reverse=True** — наоборот. **min**, **max** — крайние.\n"
              "**sorted(orders, key=distance)** — сортировать по признаку: функция без скобок!\n"
              "**max(orders, key=distance)** — самый дальний заказ.",
        steps=[
            Step("look", "Искра тратит много времени, мотаясь туда-сюда по деревне. Нужен **маршрут**: от ближнего дома "
                         "к дальнему. Python умеет сортировать.",
                 code="prices = [30, 50, 20]\nprint(sorted(prices))                # [20, 30, 50]\n"
                      "print(sorted(prices, reverse=True))  # [50, 30, 20]\nprint(min(prices), max(prices))     # 20 50",
                 portrait="explain"),
            Step("run", "Запусти: сортировать можно и числа, и строки (по алфавиту).",
                 code='names = ["Оля", "Даша", "Борис"]\nprint(sorted(names))\nprices = [30, 50, 20]\n'
                      "print(sorted(prices, reverse=True))\nprint(min(prices), max(prices))", portrait="calm"),
            Step("look", "А как отсортировать заказы? Их нельзя просто сравнить: это словари. Нужно сказать, **по какому "
                         "признаку**. Пишем функцию, которая для заказа возвращает расстояние, и передаём её в `key=` — "
                         "**без скобок**: sorted сам вызовет её для каждого заказа.",
                 code='def distance(order):\n    return order["customer"]["km"]\n\nroute = sorted(orders, key=distance)',
                 portrait="explain"),
            Step("fill", "Построй маршрут и напечатай заказы от ближнего к дальнему.",
                 code=LOAD + '\ndef distance(order):\n    return order["customer"]["km"]\n\n'
                      'route = sorted(orders, key=____)\nfor order in route:\n    print(order["id"], order["customer"]["km"], "км")',
                 check=_route_printed, portrait="calm", show_memory=True, variants=2,
                 success="Маршрут готов: сначала ближние, потом дальние.",
                 hints=["В key= передаём имя функции.", "key=distance"]),
            Step("fix", "Ошибка: функции не хватает аргумента! Python вызвал distance() сам, без заказа. Почему?",
                 code=LOAD + '\ndef distance(order):\n    return order["customer"]["km"]\n\n'
                      'route = sorted(orders, key=distance())\nfor order in route:\n    print(order["id"], order["customer"]["km"], "км")',
                 check=_route_printed, portrait="frown", variants=2,
                 success="В key= передают саму функцию, без скобок. Вызывать её будет sorted.",
                 hints=["Скобки после имени функции — это вызов.", "key=distance"]),
            Step("write", "Кто живёт дальше всех? Найди самый дальний заказ через `max(orders, key=distance)` и напечатай "
                          "имя покупателя.",
                 code=LOAD + '\ndef distance(order):\n    return order["customer"]["km"]\n\n',
                 check=_farthest, portrait="calm", variants=2, success="max и min тоже понимают key=.",
                 hints=["far = max(orders, key=distance)", 'print(far["customer"]["name"])']),
        ],
        quest=Quest(
            giver="Искра",
            note="«И-го-го! Развези оплаченные заказы по порядку: от ближнего дома к дальнему. "
                 "Неоплаченные не бери».",
            goals=["Только оплаченные заказы", "Отсортировать по расстоянию (km)", "deliver в этом порядке"],
            starter=LOAD + '\ndef distance(order):\n    return order["customer"]["km"]\n\n',
            check=_quest19, variants=2,
            solution=LOAD + '\ndef distance(order):\n    return order["customer"]["km"]\n\n'
                     'for order in sorted(orders, key=distance):\n    if order["paid"]:\n        deliver(order["id"])',
            breakdown=[("def distance(order):", "Признак для сортировки — расстояние до покупателя."),
                       ("for order in sorted(orders, key=distance):", "Обходим заказы уже в порядке маршрута."),
                       ('    if order["paid"]:', "Неоплаченные пропускаем."),
                       ('        deliver(order["id"])', "Везём.")],
            alternative="Вместо отдельной функции пишут лямбду — функцию в одну строку: "
                        "sorted(orders, key=lambda order: order[\"customer\"][\"km\"]). Делает то же самое.",
            life_title="Сортировка в жизни",
            life=["Таблицы сортируют постоянно: по дате, по сумме, по алфавиту. key= — это «по какому столбцу».",
                  "Маршрут курьера, очередь задач по срочности, топ-10 товаров по продажам — сортировка.",
                  "min и max с key= отвечают на вопросы «самый дешёвый», «самый ранний», «самый дальний»."],
            try_at_home=["Терминал → python3.", 'words = ["яблоко", "кот", "огурец"]',
                          "print(sorted(words, key=len)) — по длине слова!"],
            reward=50, hints=["for order in sorted(orders, key=distance): — сразу в порядке маршрута.",
                              'Внутри: if order["paid"]: deliver(order["id"])'],
            success="Искра: «И-го-го! Ни одного лишнего круга по деревне»."),
    ),
    Lesson(
        id="dates", title="Даты и сроки", topic="модуль datetime", **POST,
        notes="**from datetime import date** — подключить даты.\n**date.fromisoformat(\"2024-09-14\")** — строка → дата.\n"
              "**(today - d).days** — сколько дней прошло. **d.strftime(\"%d.%m.%Y\")** — дата по-русски: 14.09.2024.",
        steps=[
            Step("look", "В заказах есть дата: `\"2024-09-15\"`. Это строка в формате ГОД-МЕСЯЦ-ДЕНЬ — так даты пишут во "
                         "всём мире. Модуль `datetime` превращает её в **дату**, а даты можно вычитать: получится "
                         "промежуток, у которого есть `.days` — дни.",
                 code='from datetime import date\n\nd = date.fromisoformat("2024-09-14")\ntoday = date(2024, 9, 20)\n'
                      "print((today - d).days)   # 6", portrait="explain"),
            Step("run", "В игре сегодня 20 сентября 2024 года. В жизни вместо `date(2024, 9, 20)` пишут `date.today()`.",
                 code='from datetime import date\n\nd = date.fromisoformat("2024-09-14")\ntoday = date(2024, 9, 20)\n'
                      'print((today - d).days, "дней")\nprint(d.strftime("%d.%m.%Y"))', portrait="calm", show_memory=True,
                 after="strftime показывает дату в привычном виде: %d — день, %m — месяц, %Y — год."),
            Step("fill", "Сколько дней ждёт первый заказ? Дату возьми из заказа.",
                 code="from datetime import date\n" + LOAD + "\ntoday = date(2024, 9, 20)\n"
                      "d = date.fromisoformat(orders[0][____])\nprint((today - d).days)",
                 check=_first_days, portrait="calm", show_memory=True, variants=2,
                 success="Строка из JSON → дата → разница в днях.", hints=["Ключ с датой заказа.", 'orders[0]["date"]']),
            Step("write", f"Напечатай номера всех заказов, которые ждут больше {OVERDUE} дней: «Просрочен: 101».",
                 code="from datetime import date\n" + LOAD + "\ntoday = date(2024, 9, 20)\nfor order in orders:\n"
                      "    # сколько дней ждёт? больше 3 — печатаем\n",
                 check=_overdue_list, portrait="calm", variants=2, success="Просрочки как на ладони.",
                 hints=['days = (today - date.fromisoformat(order["date"])).days',
                        'if days > 3: print("Просрочен:", order["id"])']),
        ],
        quest=Quest(
            giver="Почтальонка Даша",
            note=f"«Жалоба! Некоторые заказы ждут больше {OVERDUE} дней. Срочно развези оплаченные просроченные заказы — "
                 "сначала самые старые. И напиши про каждый: „Заказ 101 ждёт 5 дн.“».",
            goals=[f"Найти оплаченные заказы старше {OVERDUE} дней", "Доставить их, начиная с самых старых",
                   "Напечатать, сколько дней ждал каждый"],
            starter="from datetime import date\n" + LOAD + "\ntoday = date(2024, 9, 20)\n\n\ndef age(order):\n"
                    "    # сколько дней ждёт заказ\n    return 0\n\n",
            check=_quest20, variants=2,
            solution="from datetime import date\n" + LOAD + "\ntoday = date(2024, 9, 20)\n\n\ndef age(order):\n"
                     '    return (today - date.fromisoformat(order["date"])).days\n\n\n'
                     "for order in sorted(orders, key=age, reverse=True):\n"
                     '    if order["paid"] and age(order) > 3:\n        deliver(order["id"])\n'
                     '        print(f"Заказ {order[\'id\']} ждёт {age(order)} дн.")',
            breakdown=[("def age(order):", "Функция-признак: сколько дней ждёт заказ."),
                       ('    return (today - date.fromisoformat(order["date"])).days', "Строка → дата → разница в днях."),
                       ("for order in sorted(orders, key=age, reverse=True):", "Самые старые — первыми (reverse=True)."),
                       ('    if order["paid"] and age(order) > 3:', "Оплаченный и просроченный."),
                       ('        deliver(order["id"])', "Срочно везём.")],
            alternative="Сортировать можно и прямо по строке даты: sorted(orders, key=lambda o: o[\"date\"]). "
                        "Формат ГОД-МЕСЯЦ-ДЕНЬ хорош тем, что по алфавиту он идёт так же, как по времени.",
            life_title="Даты в жизни",
            life=["Сроки оплаты счетов, просроченные задачи, дни до отпуска, возраст в днях — всё это вычитание дат.",
                  "Напоминания «за 3 дня до дедлайна» и отчёты «за последние 7 дней» пишутся так же.",
                  "Формат 2024-09-14 (ISO) понимают все программы — используй его в названиях файлов, и они сами "
                  "отсортируются по времени."],
            try_at_home=["Терминал → python3.", "from datetime import date",
                          "print((date(2025, 1, 1) - date.today()).days, 'дней до Нового года')"],
            reward=55, hints=["Функция age возвращает (today - date.fromisoformat(order[\"date\"])).days.",
                              "for order in sorted(orders, key=age, reverse=True): и внутри if paid and age > 3."],
            success="Даша: «Все просрочки закрыты! Деревня снова нас любит»."),
    ),
]

CHAPTER = Chapter(
    number=5, title="Почта", zone="post", robot="iskra", lessons=LESSONS,
    intro=[("klusha", "happy", "Почта снова работает! А возить заказы будет бабушкина робот-лошадка Искра."),
           ("iskra", "happy", "И-го-го! Я быстрая, но маршрут сама не придумаю. Скажи, куда скакать!"),
           ("klusha", "explain", "Заказы приходят с сайта в формате JSON — на нём говорит весь интернет. "
                                 "Файл orders.json лежит в папке «Робоферма/почта».")],
    outro=[("iskra", "happy", "И-го-го! Все заказы доставлены, по маршруту и вовремя."),
           ("klusha", "proud", "JSON, вложенные данные, сортировка, даты — теперь ты {умеешь|умеешь} читать данные любого сайта."),
           ("klusha", "explain", "Петя завалил контору фотографиями и файлами. Пора навести порядок — "
                                 "этим займётся сова Ухта.")],
    automation=("Искра развозит заказы", 20),
)
