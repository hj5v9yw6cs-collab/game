"""Глава 4. «Амбар»: файлы, CSV, ошибки в данных (try/except), запись отчётов для Excel."""

import csv
import io

from robofarm.lessons.base import Chapter, Lesson, Quest, Step
from robofarm.lessons.common import cash_lines, revenue_by_item, sales, sales_csv, stock, stock_txt

LOW = 20  # меньше стольких килограммов — пора заказывать


def _stock_data(variant):
    st = stock(variant)
    return {"files": {"остатки.txt": stock_txt(st)}, "expect": {"stock": st}}


def _sales_data(variant):
    rows = sales(variant)
    return {"files": {"продажи.csv": sales_csv(rows)}, "expect": {"rows": rows}}


def _cash_data(short=False):
    def data(variant):
        lines, good, bad = cash_lines(variant, short)
        return {"files": {"касса.txt": "\n".join(lines) + "\n"}, "expect": {"good": good, "bad": bad}}
    return data


def _write_data(variant):
    rows = sales(variant)
    st = stock(variant)
    return {"files": {"остатки.txt": stock_txt(st), "продажи.csv": sales_csv(rows)},
            "expect": {"rows": rows, "stock": st}}


def _lines_of(r, path):
    text = r.file(path)
    if text is None:
        return None
    return [line.rstrip("\r") for line in text.split("\n") if line.strip()]


# ---------------------------------------------------------------- урок 13: чтение файла

def _total_stock(r):
    def check(v):
        total = sum(v.data["stock"].values())
        if not v.printed_number(total):
            return f"На складе всего {total} кг, а напечатано другое. Складывай int(kg) для каждой строки."
        return None
    return r.each(check)


def _quest13(r):
    def check(v):
        st = v.data["stock"]
        low = [i for i, kg in st.items() if kg < LOW]
        ok = [i for i, kg in st.items() if kg >= LOW]
        for item in low:
            if not any(item in line and "заказать" in line.lower() for line in v.lines):
                return f"Товара «{item}» всего {st[item]} кг — нужна строка «{item}: {st[item]} кг — заказать!»."
        for item in ok:
            if any(item in line and "заказать" in line.lower() for line in v.lines):
                return f"«{item}» ещё много ({st[item]} кг) — заказывать не нужно. Условие: меньше {LOW}."
        total = sum(st.values())
        if not v.printed_number(total):
            return f"В конце напечатай, сколько всего килограммов на складе: {total}."
        return None
    msg = r.each(check)
    if msg:
        return msg
    if not r.uses("open"):
        return "Данные нужно прочитать из файла остатки.txt — командой open."
    return None


# ---------------------------------------------------------------- урок 14: CSV

def _revenue(r):
    def check(v):
        total = sum(k * p for _, _, k, p in v.data["rows"])
        if not v.printed_number(total):
            return f"Выручка за неделю — {total} руб. Для каждой строки: int(row[\"кг\"]) * int(row[\"цена\"])."
        return None
    return r.each(check)


def _pumpkin_revenue(r):
    def check(v):
        total = sum(k * p for _, item, k, p in v.data["rows"] if item == "тыква")
        if not v.printed_number(total):
            return f"Тыквы продано на {total} руб. Добавь условие: if row[\"товар\"] == \"тыква\":"
        return None
    return r.each(check)


def _quest14(r):
    def check(v):
        totals = revenue_by_item(v.data["rows"])
        for item, money in totals.items():
            if not any(item in line and str(money) in line for line in v.lines):
                return f"Нет строки для «{item}» с выручкой {money} руб. Пример: «{item}: {money} руб.»"
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 15: try/except

def _cash_total(r):
    def check(v):
        total = sum(v.data["good"])
        if not v.printed_number(total):
            return f"Выручка по хорошим строкам — {total} руб. Плохие строки нужно пропускать."
        return None
    return r.each(check)


def _bad_count(r):
    def check(v):
        n = len(v.data["bad"])
        if not any("плох" in line.lower() and str(n) in line for line in v.lines):
            return f"Плохих строк {n}. Напечатай: «Плохих строк: {n}». Счётчик увеличивай в блоке except."
        return None
    return r.each(check)


def _quest15(r):
    def check(v):
        for line in v.data["bad"]:
            if not any(line in out for out in v.lines):
                return f"Строка «{line}» с ошибкой, а в отчёте её нет. Напечатай каждую плохую строку."
        total = sum(v.data["good"])
        if not v.printed_number(total):
            return f"Выручка по правильным строкам — {total} руб."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 16: запись

def _order_file(r):
    lines = _lines_of(r, "заказ.txt")
    if lines is None:
        return "Файла заказ.txt нет. Он создаётся командой open(\"заказ.txt\", \"w\", encoding=\"utf-8\")."
    want = ["морковь: 40 кг", "тыква: 12 кг"]
    if lines != want:
        return (f"В файле строки {lines}, а нужно {want}. f.write не переносит строку сама — "
                "в конце нужен символ \\n.")
    return None


def _parse_semicolon(text):
    return [row for row in csv.reader(io.StringIO(text), delimiter=";") if row]


def _stock_csv(r):
    def check(v):
        text = v.file("склад.csv")
        if text is None:
            return "Файла склад.csv нет."
        rows = _parse_semicolon(text)
        if not rows or [c.strip() for c in rows[0]] != ["товар", "кг"]:
            return "Первая строка таблицы — заголовки: товар;кг (через точку с запятой: delimiter=\";\")."
        got = {row[0]: row[1].strip() for row in rows[1:] if len(row) >= 2}
        want = {item: str(kg) for item, kg in v.data["stock"].items()}
        if got != want:
            return f"В таблице должны быть все товары склада с килограммами: {want}"
        return None
    return r.each(check)


def _quest16(r):
    def check(v):
        text = v.file("отчёт.csv")
        if text is None:
            return "Файла отчёт.csv нет. Его нужно создать: open(\"отчёт.csv\", \"w\", encoding=\"utf-8-sig\", newline=\"\")."
        if "," in text and ";" not in text:
            return "Excel в России ждёт точку с запятой: csv.writer(f, delimiter=\";\")."
        rows = _parse_semicolon(text)
        if not rows or [c.strip() for c in rows[0]] != ["товар", "выручка"]:
            return "Первая строка — заголовки: товар;выручка."
        got = {row[0]: row[1].strip() for row in rows[1:] if len(row) >= 2}
        want = {item: str(m) for item, m in revenue_by_item(v.data["rows"]).items()}
        if got != want:
            return f"В отчёте должна быть выручка по каждому товару: {want}, а получилось {got}."
        return None
    msg = r.each(check)
    if msg:
        return msg
    if "utf-8-sig" not in r.code:
        return "Почти! Чтобы Excel не превратил русские буквы в кракозябры, открой файл с encoding=\"utf-8-sig\"."
    return None


BARN = dict(chapter=4, robot="bobr", kits=[], lang="en", zone="barn", beds=[], folder="амбар")
OPEN_STOCK = 'with open("остатки.txt", encoding="utf-8") as f:\n'
OPEN_SALES = 'import csv\n\nwith open("продажи.csv", encoding="utf-8") as f:\n'

LESSONS = [
    Lesson(
        id="files", title="Файлы", topic="чтение текстовых файлов", data=_stock_data, unlock=["barn_repaired"], **BARN,
        notes="**with open(\"файл.txt\", encoding=\"utf-8\") as f:** — открыть файл (и сам закроется).\n"
              "**f.read()** — весь текст, **for line in f:** — по строкам.\n"
              "**line.strip()** — убрать пробелы и перенос строки, **.split(\": \")** — разрезать на части.\n"
              "**int(\"40\")** — текст → число.",
        steps=[
            Step("look", "Клуша раскрывает секрет: все данные фермы лежат в **файлах** — прямо на твоём Mac! Нажми "
                         "кнопку с папкой вверху справа: откроется «Документы/Робоферма/амбар». Там файл "
                         "**остатки.txt** — открой его двойным щелчком. А вот как его читает Python:",
                 code=OPEN_STOCK + "    text = f.read()\nprint(text)", portrait="explain"),
            Step("look", "Разберём по словам. `open` — «открыть» файл. `encoding=\"utf-8\"` — кодировка: так "
                         "русские буквы прочитаются правильно. `with … as f:` — «открой и назови f», а когда блок "
                         "закончится, файл закроется сам. `f.read()` — прочитать весь текст.",
                 code=OPEN_STOCK + "    text = f.read()\nprint(text)", portrait="calm"),
            Step("run", "Запусти! Бобр сходит к шкафу и прочитает настоящий файл.",
                 code=OPEN_STOCK + "    text = f.read()\nprint(text)", portrait="calm", show_memory=True,
                 after="Это тот самый файл из папки на твоём Mac. Измени в нём число в TextEdit и запусти ещё раз — "
                       "Бобр прочитает новое. (Игра возвращает файлы урока при каждом запуске.)"),
            Step("look", "Читать удобнее по строкам: `for line in f:`. В конце каждой строки есть невидимый перенос "
                         "`\\n` — его убирает `.strip()`. А `.split(\": \")` режет строку на части по разделителю.",
                 code='line = "морковь: 40\\n"\nprint(line.strip())              # морковь: 40\n'
                      'print(line.strip().split(": "))  # [\'морковь\', \'40\']', portrait="explain"),
            Step("run", "Две части после split сразу раскладываются по двум переменным.",
                 code=OPEN_STOCK + '    for line in f:\n        item, kg = line.strip().split(": ")\n        print(item, "→", kg)',
                 portrait="calm", show_memory=True, after="item — товар, kg — килограммы. Но kg пока текст: \"40\", а не 40."),
            Step("fill", "Посчитай, сколько всего килограммов на складе. По какому разделителю резать строку?",
                 code="total = 0\n" + OPEN_STOCK + "    for line in f:\n        item, kg = line.strip().split(____)\n"
                      "        total = total + int(kg)\nprint(\"Всего на складе:\", total, \"кг\")",
                 check=_total_stock, portrait="calm", show_memory=True, variants=2,
                 success="int(kg) превратил текст «40» в число 40 — и его можно складывать.",
                 hints=["Посмотри на файл: между товаром и числом стоят двоеточие и пробел.", 'split(": ")']),
            Step("fix", "Python ругается: нельзя сложить число и текст! Что забыли?",
                 code="total = 0\n" + OPEN_STOCK + '    for line in f:\n        item, kg = line.strip().split(": ")\n'
                      "        total = total + kg\nprint(\"Всего на складе:\", total, \"кг\")",
                 check=_total_stock, portrait="frown", variants=2,
                 success="Из файла всегда приходит текст. Числа делаем сами: int() или float().",
                 hints=["kg — это текст \"40\". Как превратить его в число?", "total = total + int(kg)"]),
        ],
        quest=Quest(
            giver="Бобр",
            note=f"«Хр-р. Посмотри остатки и скажи, что заканчивается: если товара меньше {LOW} кг, напечатай "
                 "„тыква: 12 кг — заказать!“. А в конце — сколько всего килограммов на складе».",
            goals=["Прочитать остатки.txt по строкам", f"Для товаров меньше {LOW} кг — строка «… — заказать!»",
                   "В конце — общий вес склада"],
            starter="total = 0\n" + OPEN_STOCK + "    for line in f:\n        # разрежь строку, проверь остаток, прибавь к total\n",
            check=_quest13, data=_stock_data, variants=2,
            solution="total = 0\n" + OPEN_STOCK + '    for line in f:\n        item, kg = line.strip().split(": ")\n'
                     "        kg = int(kg)\n        total = total + kg\n        if kg < 20:\n"
                     '            print(f"{item}: {kg} кг — заказать!")\nprint("Всего на складе:", total, "кг")',
            breakdown=[('with open("остатки.txt", encoding="utf-8") as f:', "Открываем настоящий файл из папки «амбар»."),
                       ("    for line in f:", "Читаем по одной строке."),
                       ('        item, kg = line.strip().split(": ")', "Убираем перенос строки и режем на товар и вес."),
                       ("        kg = int(kg)", "Текст → число. Теперь можно сравнивать и складывать."),
                       ("        if kg < 20:", "Заканчивается?"),
                       ('            print(f"{item}: {kg} кг — заказать!")', "Сообщаем, что заказать."),
                       ('print("Всего на складе:", total, "кг")', "После цикла — итог.")],
            alternative="Порог лучше вынести в переменную: LOW = 20 и if kg < LOW: — тогда его легко поменять. "
                        "Имена БОЛЬШИМИ буквами программисты дают настройкам, которые не меняются в программе.",
            life_title="Файлы в жизни",
            life=["Любая программа хранит данные в файлах: заметки, настройки, выгрузки, логи.",
                  "Скрипт, который читает файл, можно запускать каждый день: файл обновился — отчёт готов.",
                  "Так проверяют, что заканчивается на складе, в холодильнике кафе или в аптеке."],
            try_at_home=["Открой Терминал и перейди в папку амбара: cd ~/Documents/Робоферма/амбар",
                          "Запусти скрипт Бобра: python3 бобр.py — он работает и без игры!",
                          "Поменяй числа в остатки.txt и запусти ещё раз."],
            reward=40, hints=["В цикле: разрежь строку, kg = int(kg), прибавь к total, if kg < 20: print(...).",
                              'print(f"{item}: {kg} кг — заказать!") — внутри if. Итог — после цикла, без отступа.'],
            success="Бобр: «Хр-р! Тыкву и яблоки закажу. Ты {прочитал|прочитала} настоящий файл — это уже профессия»."),
    ),
    Lesson(
        id="csv", title="Таблицы CSV", topic="CSV и модуль csv", data=_sales_data, **BARN,
        notes="**CSV** — таблица в виде текста: значения через запятую, первая строка — заголовки.\n"
              "**import csv** и **for row in csv.DictReader(f):** — каждая строка таблицы становится словарём.\n"
              "Значения из CSV — текст: **int(row[\"кг\"])**.\n"
              "Сумма по группам: **if item not in totals: totals[item] = 0**, потом **totals[item] += …**",
        steps=[
            Step("look", "В амбаре есть журнал продаж — **продажи.csv**. CSV — это таблица в виде текста: значения через "
                         "запятую, первая строка — заголовки. Такой файл открывается в Numbers и Excel, и любая касса, "
                         "банк или интернет-магазин умеют его выгружать. Найди его в папке и открой в Numbers!",
                 code="# продажи.csv:\n# дата,товар,кг,цена\n# 2024-09-02,яблоки,2,40\n# 2024-09-02,капуста,4,20",
                 portrait="explain"),
            Step("run", "Готовый модуль `csv` умеет читать такие таблицы. `import csv` — подключить его. "
                        "`csv.DictReader` превращает каждую строку таблицы в словарь: заголовок → значение.",
                 code=OPEN_SALES + "    for row in csv.DictReader(f):\n        print(row)", portrait="calm",
                 show_memory=True, after="Каждая строка — словарь. Как в лавке, только данные пришли из файла."),
            Step("look", "Внимание: всё, что приходит из файла, — текст. `row[\"кг\"]` — это \"3\", а не 3. "
                         "Перед расчётом превращаем в число.",
                 code='row = {"дата": "2024-09-02", "товар": "тыква", "кг": "3", "цена": "30"}\n'
                      'money = int(row["кг"]) * int(row["цена"])\nprint(money)   # 90', portrait="explain"),
            Step("fill", "Посчитай выручку за всю неделю. Какой столбец умножаем на килограммы?",
                 code="total = 0\n" + OPEN_SALES + "    for row in csv.DictReader(f):\n"
                      "        total = total + int(row[\"кг\"]) * int(row[____])\nprint(\"Выручка:\", total, \"руб.\")",
                 check=_revenue, portrait="calm", show_memory=True, variants=2, success="Выручка за неделю — посчитана!",
                 hints=["Заголовки таблицы: дата, товар, кг, цена.", 'int(row["цена"])']),
            Step("fix", "Ошибка! Python не умеет умножать текст на текст. Исправь.",
                 code="total = 0\n" + OPEN_SALES + "    for row in csv.DictReader(f):\n"
                      "        total = total + row[\"кг\"] * row[\"цена\"]\nprint(\"Выручка:\", total, \"руб.\")",
                 check=_revenue, portrait="frown", variants=2, success="Числа из CSV — всегда через int() или float().",
                 hints=["Какой функцией текст превращается в число?", 'int(row["кг"]) * int(row["цена"])']),
            Step("write", "Посчитай, на сколько рублей продано **тыквы**.",
                 code="pumpkin = 0\n" + OPEN_SALES + "    for row in csv.DictReader(f):\n        # только тыква\n",
                 check=_pumpkin_revenue, portrait="calm", variants=2, success="Фильтр + сумма — как СУММЕСЛИ в Excel.",
                 hints=['if row["товар"] == "тыква":', 'Внутри if: pumpkin = pumpkin + int(row["кг"]) * int(row["цена"]); после цикла — print(pumpkin)']),
            Step("look", "А если нужна выручка по **каждому** товару? Заведём словарь-копилку: ключ — товар, значение — "
                         "сумма. Новому товару сначала кладём 0.",
                 code='totals = {}\nitem, money = "тыква", 90\nif item not in totals:   # такого ключа ещё нет?\n'
                      "    totals[item] = 0\ntotals[item] = totals[item] + money\nprint(totals)   # {'тыква': 90}",
                 portrait="explain"),
        ],
        quest=Quest(
            giver="Записка от тёти Вали",
            note="«Бобр, посчитай по журналу продаж выручку по каждому товару и напечатай так: „тыква: 210 руб.“ — "
                 "по строке на товар. Хочу понять, что продаётся лучше».",
            goals=["Прочитать продажи.csv через csv.DictReader", "Выручка по каждому товару — словарь",
                   "Напечатать по строке на товар"],
            starter="totals = {}\n" + OPEN_SALES + "    for row in csv.DictReader(f):\n        # прибавь выручку строки к totals[товар]\n",
            check=_quest14, data=_sales_data, variants=2,
            solution="totals = {}\n" + OPEN_SALES + "    for row in csv.DictReader(f):\n        item = row[\"товар\"]\n"
                     "        money = int(row[\"кг\"]) * int(row[\"цена\"])\n        if item not in totals:\n"
                     "            totals[item] = 0\n        totals[item] = totals[item] + money\n"
                     "for item, money in totals.items():\n    print(f\"{item}: {money} руб.\")",
            breakdown=[("totals = {}", "Пустой словарь-копилка."),
                       ("    for row in csv.DictReader(f):", "Каждая строка таблицы — словарь."),
                       ('        money = int(row["кг"]) * int(row["цена"])', "Выручка одной продажи."),
                       ("        if item not in totals:", "Товар встретился впервые?"),
                       ("            totals[item] = 0", "Заводим для него ящик с нулём."),
                       ("        totals[item] = totals[item] + money", "Прибавляем к его сумме."),
                       ("for item, money in totals.items():", "После чтения файла — печатаем итоги.")],
            alternative="Короче — через метод get: totals[item] = totals.get(item, 0) + money. "
                        "get возвращает значение по ключу, а если ключа нет — значение по умолчанию (0).",
            life_title="CSV в жизни",
            life=["Выписка из банка, выгрузка из кассы, 1С, маркетплейса или Google Таблиц — это CSV.",
                  "«Сумма по категориям» — самый частый отчёт: траты по категориям, продажи по товарам, часы по проектам.",
                  "Это сводная таблица Excel, только написанная своими руками — и её можно запускать каждый день."],
            try_at_home=["Скачай выписку из банка в CSV (обычно кнопка «Экспорт»).",
                          "Положи её рядом со скриптом и поменяй имя файла и названия столбцов в коде.",
                          "Запусти: python3 бобр.py — получишь траты по категориям."],
            reward=45, hints=["Внутри цикла: item = row[\"товар\"], money = …, потом if item not in totals: totals[item] = 0.",
                              "После цикла: for item, money in totals.items(): print(f\"{item}: {money} руб.\")"],
            success="Тётя Валя: «Морковь — королева продаж! Буду возить больше»."),
    ),
    Lesson(
        id="errors", title="Ошибки в данных", topic="try / except", data=_cash_data(), **BARN,
        notes="**try:** … **except ValueError:** … — попробовать, а при ошибке не падать, а сделать другое.\n"
              "**ValueError** — неправильное значение (int(\"два\")), **FileNotFoundError** — нет файла,\n"
              "**KeyError** — нет ключа, **ZeroDivisionError** — деление на ноль.",
        steps=[
            Step("look", "Настоящие данные бывают «грязными». Михалыч записывал продажи в **касса.txt** руками: где-то "
                         "вместо цифр слова, где-то пусто. Открой файл и посмотри сам!",
                 code="# касса.txt:\n# яблоки,3,40\n# капуста,много,20\n# тыква,2,30", portrait="explain"),
            Step("run", "Попробуем посчитать выручку как обычно. Запусти — и посмотри, что будет.",
                 code="total = 0\nwith open(\"касса.txt\", encoding=\"utf-8\") as f:\n    for line in f:\n"
                      "        item, kg, price = line.strip().split(\",\")\n        total = total + int(kg) * int(price)\n"
                      "print(\"Выручка:\", total)",
                 portrait="frown", expect_error=True,
                 after="Одна кривая строка — и упала вся программа. В жизни так нельзя: отчёт нужен всегда."),
            Step("look", "**try** — «попробуй». Если внутри блока случится ошибка, Python не упадёт, а выполнит "
                         "блок **except** — «на случай ошибки». После except пишут, какую ошибку ловим.",
                 code='try:\n    kg = int("два")\nexcept ValueError:\n    print("Это не число, пропускаю")',
                 portrait="explain"),
            Step("fill", "Оберни расчёт в try. Какую ошибку ловим? (Её название было в сообщении об ошибке.)",
                 code="total = 0\nwith open(\"касса.txt\", encoding=\"utf-8\") as f:\n    for line in f:\n"
                      "        item, kg, price = line.strip().split(\",\")\n        try:\n"
                      "            total = total + int(kg) * int(price)\n        except ____:\n"
                      "            print(\"Пропускаю:\", line.strip())\nprint(\"Выручка:\", total)",
                 check=_cash_total, portrait="calm", show_memory=True, variants=2,
                 success="Плохие строки пропущены, выручка посчитана по хорошим.",
                 hints=["int(\"много\") даёт ошибку ValueError.", "except ValueError:"]),
            Step("write", "Посчитай, сколько строк с ошибками, и напечатай в конце: «Плохих строк: 2».",
                 code="total = 0\nbad = 0\nwith open(\"касса.txt\", encoding=\"utf-8\") as f:\n    for line in f:\n"
                      "        item, kg, price = line.strip().split(\",\")\n        try:\n"
                      "            total = total + int(kg) * int(price)\n        except ValueError:\n"
                      "            # посчитай плохую строку\n",
                 check=_bad_count, portrait="calm", variants=2, success="Теперь видно, сколько данных испорчено.",
                 hints=["В except: bad = bad + 1", 'После цикла: print("Плохих строк:", bad)']),
            Step("look", "Ошибки бывают разные. Если файла нет — **FileNotFoundError**. Его тоже можно поймать.",
                 code='try:\n    with open("отчёт_за_1999.txt", encoding="utf-8") as f:\n        print(f.read())\n'
                      'except FileNotFoundError:\n    print("Такого файла нет")', portrait="explain"),
        ],
        quest=Quest(
            giver="Записка от деда Михалыча",
            note="«Я там в кассе понаписал… Посчитай выручку за неделю, а все строки с ошибками выпиши, я исправлю. "
                 "Ой, кажется, в одной строке я забыл цену — значений там меньше трёх».",
            goals=["Посчитать выручку по правильным строкам", "Напечатать каждую строку с ошибкой",
                   "Программа не должна падать ни на одной строке"],
            starter="total = 0\nwith open(\"касса.txt\", encoding=\"utf-8\") as f:\n    for line in f:\n        # try / except\n",
            check=_quest15, data=_cash_data(short=True), variants=2,
            solution="total = 0\nwith open(\"касса.txt\", encoding=\"utf-8\") as f:\n    for line in f:\n        try:\n"
                     "            item, kg, price = line.strip().split(\",\")\n            total = total + int(kg) * int(price)\n"
                     "        except ValueError:\n            print(\"Ошибка в строке:\", line.strip())\nprint(\"Выручка:\", total, \"руб.\")",
            breakdown=[("        try:", "Пробуем обработать строку целиком…"),
                       ('            item, kg, price = line.strip().split(",")',
                        "…и разбор тоже внутри try: если значений два, а не три, это тоже ValueError."),
                       ("            total = total + int(kg) * int(price)", "int(\"много\") — ещё один ValueError."),
                       ("        except ValueError:", "Любая из этих ошибок — сюда."),
                       ('            print("Ошибка в строке:", line.strip())', "Сообщаем и идём к следующей строке.")],
            alternative="Можно собрать плохие строки в список bad_lines.append(line.strip()) и в конце записать их в "
                        "файл ошибки.txt — Михалычу будет удобно исправлять.",
            life_title="Ошибки в жизни",
            life=["Данные из Excel, анкет и касс всегда немного «грязные»: пробелы, буквы вместо цифр, пустые ячейки.",
                  "Хорошая программа не падает, а сообщает, что именно не так, — и работает дальше.",
                  "try/except защищает и от внешних бед: нет файла, пропал интернет, сайт не ответил."],
            try_at_home=["Терминал → python3.", 'try: print(int("сто")) — и Enter', 'except ValueError: print("Не число!") — и Enter дважды'],
            reward=45, hints=["Внутри цикла сразу try:, а внутри try — и split, и расчёт.",
                              'except ValueError: print("Ошибка в строке:", line.strip())'],
            success="Михалыч: «Ишь ты, нашёл все мои каракули. Исправлю, исправлю…»"),
    ),
    Lesson(
        id="write", title="Пишем отчёт", topic="запись файлов и CSV для Excel", data=_write_data, **BARN,
        notes="**open(\"файл.txt\", \"w\", encoding=\"utf-8\")** — открыть на запись (старое содержимое сотрётся!).\n"
              "**f.write(\"текст\\n\")** — записать строку; перенос \\n ставим сами.\n"
              "Для Excel: **open(…, \"w\", encoding=\"utf-8-sig\", newline=\"\")** и **csv.writer(f, delimiter=\";\")**,\n"
              "**writer.writerow([\"товар\", \"кг\"])** — строка таблицы.",
        steps=[
            Step("look", "Файлы можно не только читать, но и **создавать**. Второй параметр `\"w\"` (write) — «открыть для "
                         "записи». Осторожно: \"w\" стирает всё, что было в файле. `f.write` пишет текст как есть — "
                         "перенос строки `\\n` нужно ставить самим.",
                 code='with open("заметка.txt", "w", encoding="utf-8") as f:\n    f.write("Привет из Python!\\n")\n'
                      '    f.write("Вторая строка\\n")', portrait="explain"),
            Step("run", "Запусти, а потом открой папку «амбар» — там появится новый файл!",
                 code='with open("заметка.txt", "w", encoding="utf-8") as f:\n    f.write("Привет из Python!\\n")\n'
                      '    f.write("Вторая строка\\n")', portrait="calm",
                 after="Файл заметка.txt создала твоя программа. Открой его в TextEdit."),
            Step("fill", "Запиши заказ поставщику: каждый товар — на своей строке. Чего не хватает в конце строки?",
                 code='stock = {"морковь": 40, "тыква": 12}\nwith open("заказ.txt", "w", encoding="utf-8") as f:\n'
                      '    for item, kg in stock.items():\n        f.write(f"{item}: {kg} кг____")',
                 check=_order_file, portrait="calm", success="\\n — «новая строка». Без него всё слиплось бы в одну.",
                 hints=["Как сказать «перенос строки» внутри текста?", 'f.write(f"{item}: {kg} кг\\n")']),
            Step("look", "Таблицу для Excel пишет модуль `csv`. Excel в России ждёт **точку с запятой** "
                         "(`delimiter=\";\"`) и кодировку **utf-8-sig** — иначе русские буквы превратятся в кракозябры. "
                         "`newline=\"\"` — чтобы не было пустых строк между строками таблицы.",
                 code='import csv\n\nwith open("отчёт.csv", "w", encoding="utf-8-sig", newline="") as f:\n'
                      '    writer = csv.writer(f, delimiter=";")\n    writer.writerow(["товар", "кг"])\n'
                      '    writer.writerow(["тыква", 12])', portrait="explain"),
            Step("run", "Запусти и открой отчёт.csv в Numbers или Excel — это настоящая таблица!",
                 code='import csv\n\nwith open("отчёт.csv", "w", encoding="utf-8-sig", newline="") as f:\n'
                      '    writer = csv.writer(f, delimiter=";")\n    writer.writerow(["товар", "кг"])\n'
                      '    writer.writerow(["тыква", 12])', portrait="calm",
                 after="writerow принимает список — это одна строка таблицы."),
            Step("write", "Прочитай остатки.txt и запиши всю таблицу склада в **склад.csv**: заголовки «товар» и «кг», "
                          "дальше строка на каждый товар. (`f.readlines()` — все строки файла списком.)",
                 code='import csv\n\nwith open("остатки.txt", encoding="utf-8") as f:\n    lines = f.readlines()\n\n'
                      'with open("склад.csv", "w", encoding="utf-8-sig", newline="") as f:\n'
                      '    writer = csv.writer(f, delimiter=";")\n    # заголовки и строки\n',
                 check=_stock_csv, portrait="calm", variants=2,
                 success="Склад — в таблице Excel. Бобр доволен!",
                 hints=['writer.writerow(["товар", "кг"]) — потом цикл for line in lines:',
                        'item, kg = line.strip().split(": ")\nwriter.writerow([item, kg])']),
        ],
        quest=Quest(
            giver="Инспектор Сидоров",
            note="«Гражданин фермер! Предоставьте отчёт о выручке по каждому товару в файле отчёт.csv. "
                 "Столбцы: товар;выручка. Чтобы открывался в Excel, с русскими буквами. Жду»."
                 " — Данные — в продажи.csv.",
            goals=["Прочитать продажи.csv", "Посчитать выручку по товарам", "Записать отчёт.csv: товар;выручка",
                   "Кодировка utf-8-sig и разделитель ;"],
            starter="import csv\n\ntotals = {}\n# 1) прочитай продажи.csv и посчитай totals\n# 2) запиши отчёт.csv\n",
            check=_quest16, data=_write_data, variants=2,
            solution='import csv\n\ntotals = {}\nwith open("продажи.csv", encoding="utf-8") as f:\n'
                     '    for row in csv.DictReader(f):\n        money = int(row["кг"]) * int(row["цена"])\n'
                     '        totals[row["товар"]] = totals.get(row["товар"], 0) + money\n\n'
                     'with open("отчёт.csv", "w", encoding="utf-8-sig", newline="") as f:\n'
                     '    writer = csv.writer(f, delimiter=";")\n    writer.writerow(["товар", "выручка"])\n'
                     '    for item, money in totals.items():\n        writer.writerow([item, money])',
            breakdown=[('totals[row["товар"]] = totals.get(row["товар"], 0) + money',
                        "get(ключ, 0) — значение по ключу, а если ключа ещё нет — 0. Короткая копилка."),
                       ('with open("отчёт.csv", "w", encoding="utf-8-sig", newline="") as f:',
                        "Открываем новый файл на запись — в кодировке, которую понимает Excel."),
                       ('    writer = csv.writer(f, delimiter=";")', "Писатель таблиц с точкой с запятой."),
                       ('    writer.writerow(["товар", "выручка"])', "Первая строка — заголовки."),
                       ("        writer.writerow([item, money])", "Строка на каждый товар.")],
            alternative="Можно отсортировать отчёт по выручке: for item, money in sorted(totals.items(), "
                        "key=lambda pair: pair[1], reverse=True): — про сортировку будет в следующей главе.",
            life_title="Отчёты в жизни",
            life=["«Сделай отчёт в Excel» — одна из самых частых задач в любом офисе. Скрипт делает её за секунду.",
                  "Один раз написал — и каждую неделю запускаешь на свежих данных, а не копируешь цифры руками.",
                  "utf-8-sig и точка с запятой — секрет, о котором не знают многие: теперь знаешь ты."],
            try_at_home=["cd ~/Documents/Робоферма/амбар", "python3 бобр.py", "open отчёт.csv — откроется в Numbers или Excel."],
            reward=50, hints=["Сначала посчитай totals, как в уроке про CSV. Потом открой отчёт.csv на запись.",
                              'writer.writerow(["товар", "выручка"]) и цикл по totals.items() с writer.writerow([item, money])'],
            success="Сидоров: «Хм. Отчёт в порядке. Даже кодировка правильная. Свободны»."),
    ),
]

CHAPTER = Chapter(
    number=4, title="Амбар", zone="barn", robot="bobr", lessons=LESSONS,
    intro=[("klusha", "explain", "Товара всё больше, пора наводить учёт. Знакомься: робобобр Бобр, бабушкин кладовщик."),
           ("bobr", "happy", "Хр-р. Всё записано. В файлах. Бумажки — в прошлом веке."),
           ("klusha", "proud", "А теперь секрет: всё, что ты видел{|а} в рентгене, — данные. И в жизни они лежат в файлах. "
                               "Файлы этой главы — настоящие, в папке «Документы/Робоферма/амбар» на твоём Mac.")],
    outro=[("bobr", "happy", "Хр-р! Склад посчитан, ошибки найдены, отчёт для Сидорова готов."),
           ("klusha", "proud", "Файлы, CSV, try/except, отчёты для Excel — это уже настоящая работа с данными."),
           ("klusha", "explain", "Тётя Валя открыла интернет-магазин! Заказы с сайта приходят на почту — в формате JSON. "
                                 "Развозить их будет лошадка Искра.")],
    automation=("Бобр ведёт склад", 15),
)
