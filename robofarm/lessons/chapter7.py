"""Глава 7. «Ярмарка»: прогноз погоды из JSON, таблица из Excel и финальный проект. И «Что дальше»."""

import json

from robofarm.lessons.base import Chapter, Lesson, Quest, Step
from robofarm.lessons.common import best_day, excel_csv, fair_price, fair_stock, weather


def _weather(variant):
    w = weather(variant)
    return {"files": {"погода.json": json.dumps(w, ensure_ascii=False, indent=2) + "\n"}, "expect": {"weather": w}}


def _fair(variant):
    rows = fair_stock(variant)
    return {"files": {"остатки.csv": excel_csv(rows)}, "expect": {"rows": rows}}


def _days(v):
    return v.data["weather"]["daily"]


LOAD_W = 'import json\n\nwith open("погода.json", encoding="utf-8") as f:\n    forecast = json.load(f)\ndays = forecast["daily"]\n'
LOAD_X = ('import csv\n\nwith open("остатки.csv", encoding="utf-8-sig") as f:\n'
          '    rows = list(csv.DictReader(f, delimiter=";"))\n')


# ---------------------------------------------------------------- урок 25: погода

def _dry(r):
    def check(v):
        dry = [d["date"] for d in _days(v) if d["rain_mm"] == 0]
        wet = [d["date"] for d in _days(v) if d["rain_mm"] != 0]
        for date in dry:
            if not v.printed(date):
                return f"{date} без дождя — эту дату нужно напечатать."
        for date in wet:
            if v.printed(date):
                return f"{date} будет дождь ({next(d['rain_mm'] for d in _days(v) if d['date'] == date)} мм) — этот день не подходит."
        return None
    return r.each(check)


def _warmest(r):
    def check(v):
        warm = max(_days(v), key=lambda d: d["temp"])
        if not v.printed(warm["date"]):
            return f"Самый тёплый день — {warm['date']} (+{warm['temp']}°). max(days, key=temperature)."
        return None
    return r.each(check)


def _quest25(r):
    def check(v):
        best = best_day(v.data["weather"])
        if not any(best["date"] in line and str(best["temp"]) in line.replace(best["date"], "") for line in v.lines):
            return (f"Лучший день — {best['date']}: без дождя, ветер меньше 8 м/с, и самый тёплый из таких (+{best['temp']}°). "
                    f"Напечатай: «Ярмарка: {best['date']}, +{best['temp']}°».")
        text = v.file("день_ярмарки.txt")
        if text is None or best["date"] not in text:
            return f"Запиши дату {best['date']} в файл день_ярмарки.txt — его прочитает тётя Валя."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 26: финальный проект

FAIR_CASES = [((30, 80), 24), ((50, 35), 50), ((45, 51), 36), ((20, 50), 20)]


def _fair_fn(r):
    for args, want in FAIR_CASES:
        c = r.call("fair_price", *args)
        if c is None or c.get("missing"):
            return "Не нашлась функция fair_price(price, kg)."
        if c.get("error"):
            return f"fair_price{args} упала: {c['error']['title']}"
        value = c.get("value")
        if value is None:
            return "fair_price ничего не возвращает — нужен return."
        if not isinstance(value, (int, float)) or abs(value - want) > 0.01:
            price, kg = args
            why = "больше 50 кг — скидка 20%" if kg > 50 else "не больше 50 кг — без скидки"
            return f"fair_price({price}, {kg}) вернула {value}, а нужно {want} ({why})."
    return None


def _quest26(r):
    msg = _fair_fn(r)
    if msg:
        return msg

    def check(v):
        rows = v.data["rows"]
        text = v.file("ценники.txt")
        if text is None:
            return "Файла ценники.txt нет. Создай его: open(\"ценники.txt\", \"w\", encoding=\"utf-8\")."
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        want = [f"{item.capitalize()}: {fair_price(price, kg)} руб/кг" + (" — скидка!" if kg > 50 else "")
                for item, kg, price in rows]
        for i, exp in enumerate(want):
            if i >= len(lines):
                return f"В ценниках не хватает строки «{exp}»."
            if lines[i] != exp:
                return f"Ценник {i + 1}: ожидалось «{exp}», а записано «{lines[i]}»."
        total = sum(kg * fair_price(price, kg) for item, kg, price in rows)
        if not any("продадим" in line.lower() and str(total) in line for line in v.lines):
            return f"Напечатай итог: «Если продадим всё: {total} руб.» — сумма кг × цена ярмарки по всем товарам."
        return None
    return r.each(check)


FAIR = dict(chapter=7, robot="klusha", kits=[], lang="en", zone="fair", beds=[], folder="ярмарка")

LESSONS = [
    Lesson(
        id="weather", title="Прогноз погоды", topic="настоящий JSON с сайта погоды", data=_weather, **FAIR,
        notes="Прогнозы, курсы и карты приходят с сайтов в JSON — тот же json.load.\n"
              "Условия можно объединять: **if day[\"rain_mm\"] == 0 and day[\"wind\"] < 8:**\n"
              "Лучший из подходящих: отобрать в список, потом **max(список, key=…)**.",
        steps=[
            Step("look", "Ярмарка — под открытым небом, значит, нужна погода. Клуша скачала прогноз на неделю. Он "
                         "выглядит в точности как ответ настоящего сайта погоды: JSON со словарём, внутри — список дней.",
                 code='{"city": "Осенний Лог",\n "daily": [\n   {"date": "2024-09-23", "temp": 11, "rain_mm": 0.0, "wind": 4},\n'
                      '   {"date": "2024-09-24", "temp": 16, "rain_mm": 0.0, "wind": 3}\n ]}', portrait="explain"),
            Step("run", "Прочитаем прогноз и напечатаем каждый день.",
                 code=LOAD_W + 'for day in days:\n    print(f"{day[\'date\']}: {day[\'temp\']}°, дождь {day[\'rain_mm\']} мм, '
                      'ветер {day[\'wind\']} м/с")', portrait="calm", show_memory=True,
                 after="Это навык из главы 5, только данные другие. Так читают любой сайт: погода, курсы валют, пробки."),
            Step("fill", "Напечатай даты дней без дождя. Сколько миллиметров дождя в сухой день?",
                 code=LOAD_W + 'for day in days:\n    if day["rain_mm"] == ____:\n        print(day["date"])',
                 check=_dry, portrait="calm", variants=2, success="0.0 == 0 в Python — правда: число одно и то же.",
                 hints=["Сухо — значит, дождя ноль миллиметров.", 'if day["rain_mm"] == 0:']),
            Step("write", "Найди самый тёплый день недели и напечатай его дату. Пригодится max с key=.",
                 code=LOAD_W + "\n\ndef temperature(day):\n    return day[\"temp\"]\n\n",
                 check=_warmest, portrait="calm", variants=2, success="Самый тёплый — но вдруг там дождь?..",
                 hints=["warm = max(days, key=temperature)", 'print(warm["date"])']),
        ],
        quest=Quest(
            giver="Тётя Валя",
            note="«Когда устраиваем ярмарку? Нужен день без дождя и с ветром меньше 8 м/с, а из таких — самый тёплый. "
                 "Напечатай: „Ярмарка: 2024-09-24, +16°“ и запиши дату в файл день_ярмарки.txt — я повешу объявление».",
            goals=["Отобрать дни без дождя и с ветром < 8", "Из них выбрать самый тёплый",
                   "Напечатать день и температуру", "Записать дату в день_ярмарки.txt"],
            starter=LOAD_W + "\ngood = []\nfor day in days:\n    # подходит ли день?\n",
            check=_quest25, variants=2,
            solution=LOAD_W + '\ngood = []\nfor day in days:\n    if day["rain_mm"] == 0 and day["wind"] < 8:\n'
                     '        good.append(day)\n\n\ndef temperature(day):\n    return day["temp"]\n\n\n'
                     'best = max(good, key=temperature)\nprint(f"Ярмарка: {best[\'date\']}, +{best[\'temp\']}°")\n'
                     'with open("день_ярмарки.txt", "w", encoding="utf-8") as f:\n    f.write(best["date"] + "\\n")',
            breakdown=[("good = []", "Пустой список для подходящих дней."),
                       ('    if day["rain_mm"] == 0 and day["wind"] < 8:', "Оба условия сразу."),
                       ("        good.append(day)", "append — «добавить в конец списка»."),
                       ("best = max(good, key=temperature)", "Самый тёплый из подходящих."),
                       ('    f.write(best["date"] + "\\n")', "Дата — в файл для тёти Вали.")],
            alternative="Отбор в список можно записать в одну строку — это «списковое включение»: "
                        "good = [d for d in days if d[\"rain_mm\"] == 0 and d[\"wind\"] < 8]. Программисты его очень любят.",
            life_title="Данные из интернета",
            life=["Настоящий прогноз можно скачать бесплатно, например с open-meteo.com: ответ — точно такой JSON.",
                  "Так же устроены курсы валют (сайт ЦБ), расписания, пробки, цены на маркетплейсах.",
                  "Скрипт «если завтра дождь — напомни взять зонт» — пара десятков строк."],
            try_at_home=["Открой в браузере: api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.62&daily=temperature_2m_max,precipitation_sum&timezone=auto",
                          "Это настоящий JSON с прогнозом для Москвы — сравни с погода.json.",
                          "Попробуй прочитать его модулем json (urllib.request.urlopen + json.load)."],
            reward=60, hints=['Цикл: if day["rain_mm"] == 0 and day["wind"] < 8: good.append(day)',
                              "best = max(good, key=temperature), потом print и запись в файл."],
            success="Тётя Валя: «Объявление висит! Вся деревня придёт»."),
    ),
    Lesson(
        id="fair", title="Ярмарка!", topic="финальный проект: всё вместе", data=_fair, **FAIR,
        notes="Файлы из Excel: **encoding=\"utf-8-sig\"** и **delimiter=\";\"**.\n"
              "Большая задача = маленькие шаги: прочитать → посчитать (функция) → записать → проверить.",
        steps=[
            Step("look", "Финальный проект! Тётя Валя прислала остатки к ярмарке — таблицу из Excel. План:\n"
                         "1) прочитать таблицу;\n2) посчитать цены ярмарки (функция);\n3) записать ценники в файл;\n"
                         "4) посчитать, сколько выручим. Всё это ты уже умеешь — осталось сложить вместе.",
                 code="# остатки.csv (сохранён из Excel):\n# товар;кг;цена\n# тыква;80;30\n# морковь;35;50", portrait="explain"),
            Step("run", "Читаем таблицу как обычно — с utf-8 и точкой с запятой. Запусти… и посмотри, что будет.",
                 code='import csv\n\nwith open("остатки.csv", encoding="utf-8") as f:\n    for row in csv.DictReader(f, delimiter=";"):\n'
                      '        print(row["товар"], row["кг"])', portrait="think", expect_error=True,
                 after="Ключа «товар» нет? Excel ставит в самое начало файла невидимую метку — BOM. Она приклеилась "
                       "к первому заголовку. Файлы из Excel читают с encoding=\"utf-8-sig\" — эта кодировка метку убирает."),
            Step("run", "Теперь правильно: utf-8-sig. `list(...)` сразу собирает все строки таблицы в список.",
                 code=LOAD_X + 'for row in rows:\n    print(row["товар"], row["кг"], "кг по", row["цена"], "руб.")',
                 portrait="calm", show_memory=True, after="Таблица прочитана. Шаг 1 из 4 готов!"),
            Step("write", "Шаг 2. Напиши функцию `fair_price(price, kg)`: если товара больше 50 кг — скидка 20% "
                          "(цена × 0.8, округли через `round`), иначе цена без изменений.",
                 code="def fair_price(price, kg):\n    # больше 50 кг — скидка 20%\n", check=_fair_fn, portrait="calm",
                 calls=[{"fn": "fair_price", "args": list(a)} for a, _ in FAIR_CASES],
                 success="Функция готова — и проверена на четырёх случаях.",
                 hints=["if kg > 50: return round(price * 0.8)", "Иначе: return price"]),
        ],
        quest=Quest(
            giver="Тётя Валя",
            note="«Последнее перед ярмаркой! Запиши ценники в ценники.txt — по строке на товар, как в таблице: "
                 "„Тыква: 24 руб/кг — скидка!“ (если скидка) или „Морковь: 50 руб/кг“. "
                 "И напечатай, сколько выручим, если продадим всё: „Если продадим всё: 10030 руб.“»",
            goals=["Прочитать остатки.csv (utf-8-sig, ;)", "Цена ярмарки — функцией fair_price",
                   "Записать ценники.txt", "Напечатать возможную выручку"],
            starter=LOAD_X + "\n\ndef fair_price(price, kg):\n    # скидка 20%, если больше 50 кг\n    return price\n\n\n"
                    "total = 0\n# запиши ценники и посчитай total\n",
            check=_quest26, variants=2, calls=[{"fn": "fair_price", "args": list(a)} for a, _ in FAIR_CASES],
            solution=LOAD_X + "\n\ndef fair_price(price, kg):\n    if kg > 50:\n        return round(price * 0.8)\n    return price\n\n\n"
                     'total = 0\nwith open("ценники.txt", "w", encoding="utf-8") as f:\n    for row in rows:\n'
                     '        kg = int(row["кг"])\n        price = fair_price(int(row["цена"]), kg)\n'
                     '        line = f"{row[\'товар\'].capitalize()}: {price} руб/кг"\n        if kg > 50:\n'
                     '            line = line + " — скидка!"\n        f.write(line + "\\n")\n        total = total + kg * price\n'
                     'print(f"Если продадим всё: {total} руб.")',
            breakdown=[('with open("остатки.csv", encoding="utf-8-sig") as f:', "Файл из Excel — с utf-8-sig."),
                       ("def fair_price(price, kg):", "Правило цены — отдельной функцией: его легко поменять."),
                       ('        price = fair_price(int(row["цена"]), kg)', "Числа из таблицы — через int()."),
                       ('        line = f"{row[\'товар\'].capitalize()}: {price} руб/кг"', "Ценник — f-строка с большой буквы."),
                       ("            line = line + \" — скидка!\"", "Пометка для товаров со скидкой."),
                       ('        f.write(line + "\\n")', "Каждый ценник — с новой строки."),
                       ("        total = total + kg * price", "Выручка, если всё раскупят.")],
            alternative="Ценники можно сразу записать и в CSV для печати на принтере, а отчёт — отправить себе в Telegram. "
                        "Ты уже знаешь всё, чтобы научиться этому по документации.",
            life_title="Всё вместе",
            life=["Настоящие задачи всегда такие: прочитать данные, посчитать по правилам, записать результат.",
                  "Разбивай большую задачу на шаги и проверяй каждый — как в этом уроке.",
                  "Любой твой скрипт из игры — шаблон для своей задачи: замени файлы и правила."],
            try_at_home=["cd ~/Documents/Робоферма/ярмарка", "python3 клуша.py", "open ценники.txt"],
            reward=80, hints=["В цикле: kg = int(row[\"кг\"]), price = fair_price(int(row[\"цена\"]), kg), строка ценника, f.write.",
                              'Если kg > 50 — к строке добавь " — скидка!". После цикла: print(f"Если продадим всё: {total} руб.")'],
            success="Ярмарка открыта! Ценники висят, покупатели идут, а ферма «Осенний Лог» — самая умная в области!"),
    ),
]

CHAPTER = Chapter(
    number=7, title="Ярмарка", zone="fair", robot="klusha", lessons=LESSONS,
    intro=[("klusha", "happy", "Осенняя ярмарка! Вся команда в сборе: Бублик, Мурзик, Бобр, Искра и Ухта."),
           ("bublik", "happy", "Гав! Я принёс самую большую тыкву!"),
           ("uhta", "happy", "Уху. А я — все отчёты."),
           ("klusha", "proud", "Сегодня программу пишу я — с твоей помощью. Это наш финальный проект: "
                               "всё, чему ты {научился|научилась}, вместе.")],
    outro=[("klusha", "proud", "Ярмарка удалась! Жюри назвало «Осенний Лог» самой умной фермой области."),
           ("murzik", "happy", "Мур-р. Распродали всё. Даже свёклу."),
           ("klusha", "happy", "Бабушка Зина гордилась бы тобой. А теперь — самое важное: что делать дальше, в жизни.")],
    automation=("Команда роботов ведёт ферму", 30),
)

FINALE = """<b>Ферма «Осенний Лог» — самая умная ферма в области!</b><br><br>
Ты {прошёл|прошла} весь путь: от первого <code>print</code> до программ, которые сами читают файлы,
разбирают JSON, раскладывают фото по папкам и пишут отчёты для Excel.<br><br>
<b>Что попробовать дальше — уже в своей жизни:</b>
<ul>
<li><b>Выписка из банка.</b> Скачай её в CSV и посчитай траты по категориям — как выручку в амбаре.</li>
<li><b>Фото с телефона.</b> Разложи их по папкам «год/месяц» и переименуй по дате — как в конторе Ухты.</li>
<li><b>Погода и курсы валют.</b> Сайты отдают их в JSON — как прогноз на ярмарку. Модуль <code>urllib</code> умеет их скачивать.</li>
<li><b>Отчёт за неделю.</b> Если ты каждую неделю копируешь цифры из нескольких файлов в один — пусть это делает скрипт.</li>
<li><b>Telegram-бот, сайт, анализ данных.</b> Следующие шаги: библиотеки <code>requests</code>, <code>pandas</code>,
<code>python-telegram-bot</code>. Ты уже знаешь всё, чтобы читать их примеры.</li>
</ul>
Все твои скрипты лежат в папке «Документы/Робоферма». Открой любой в Терминале командой <code>python3</code> —
они работают и без игры.<br><br>
<i>Спасибо, что {помог|помогла} бабушкиной ферме. Ко-ко!</i>"""
