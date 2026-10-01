"""Глава 6. «Контора»: папки и файлы (pathlib), раскладка по папкам, переименование, отчёт из многих файлов."""

from collections import Counter

from robofarm.lessons.base import Chapter, Lesson, Quest, Step
from robofarm.lessons.common import PHOTO_EXT, downloads, kind_of, photos, screenshots, week_sales


def _downloads(variant):
    files = downloads(variant)
    names = [p.split("/", 1)[1] for p in files]
    return {"files": files, "expect": {"names": names}}


def _photos(variant):
    files = {**photos(variant), **screenshots(variant)}
    return {"files": files, "expect": {"photos": sorted(p.split("/", 1)[1] for p in files if p.startswith("фото/")),
                                       "shots": sorted(p.split("/", 1)[1] for p in files if p.startswith("скриншоты/"))}}


def _week(variant):
    files, rows = week_sales(variant)
    return {"files": files, "expect": {"rows": rows}}


def _names(v):
    return v.data["names"]


def _ext(name):
    return name[name.rfind("."):] if "." in name else ""


def _in(r, folder):
    """Имена файлов, которые лежат прямо в папке folder после запуска."""
    prefix = folder.rstrip("/") + "/"
    return sorted(p[len(prefix):] for p in r.files if p.startswith(prefix) and "/" not in p[len(prefix):]
                  and not p.endswith("/"))


# ---------------------------------------------------------------- урок 21: pathlib

def _count_jpg(r):
    def check(v):
        n = sum(1 for name in _names(v) if _ext(name) == ".jpg")
        if not v.printed_number(n):
            return f"Файлов с расширением .jpg — {n}. Сравни p.suffix с \".jpg\" и считай счётчиком."
        return None
    return r.each(check)


def _by_suffix(r):
    def check(v):
        counts = Counter(_ext(name) for name in _names(v))
        for ext, n in counts.items():
            if not any(ext in line and str(n) in line.replace(ext, "") for line in v.lines):
                return f"Нет строки для {ext}: таких файлов {n}. Пример: «{ext}: {n}»."
        return None
    return r.each(check)


def _quest21(r):
    def check(v):
        counts = Counter(kind_of(name) for name in _names(v))
        for kind in ("Фото", "Документы", "Таблицы"):
            n = counts.get(kind, 0)
            if not any(kind.lower() in line.lower() and str(n) in line for line in v.lines):
                extra = " Осторожно: у некоторых фото расширение большими буквами (.JPG) — помогает .lower()." \
                    if kind == "Фото" else ""
                return f"Нужна строка «{kind}: {n}».{extra}"
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 22: раскладка по папкам

def _moved(ext, folder):
    def check(r):
        def one(v):
            want = sorted(n for n in _names(v) if _ext(n) == ext)
            got = _in(v, f"Загрузки/{folder}")
            left = [n for n in _in(v, "Загрузки") if _ext(n) == ext]
            if left:
                return f"В Загрузках остались {ext}-файлы: {', '.join(left)}. Их нужно переложить в «{folder}»."
            if got != want:
                return f"В папке «{folder}» должны быть: {', '.join(want)}."
            return None
        return r.each(one)
    return check


def _quest22(r):
    def check(v):
        for name in _names(v):
            kind = kind_of(name)
            where = f"Загрузки/{kind}" if kind else "Загрузки"
            if name not in _in(v, where):
                if name in _in(v, "Загрузки"):
                    hint = " Расширение может быть большими буквами: сравнивай p.suffix.lower()." if name != name.lower() else ""
                    return f"Файл {name} остался в Загрузках — ему место в папке «{kind}».{hint}"
                return f"Файл {name} должен оказаться в папке «Загрузки/{kind}»."
        return None
    return r.each(check)


# ---------------------------------------------------------------- урок 23: переименование

def _renamed(r):
    def check(v):
        want = sorted(f"урожай_{i:03}{_ext(n)}" for i, n in enumerate(v.data["photos"], 1))
        got = _in(v, "фото")
        if got != want:
            return f"В папке «фото» должны получиться: {', '.join(want)}, а сейчас: {', '.join(got)}."
        return None
    return r.each(check)


def _shots(r):
    def check(v):
        want = sorted(f"скрин_{i:02}.png" for i in range(1, len(v.data["shots"]) + 1))
        got = _in(v, "скриншоты")
        if got != want:
            return f"В папке «скриншоты» должны получиться: {', '.join(want)}, а сейчас: {', '.join(got)}."
        return None
    return r.each(check)


def _quest23(r):
    def check(v):
        want = [f"осень_{i:03}{_ext(n).lower()}" for i, n in enumerate(v.data["photos"], 1)]
        got = _in(v, "фото")
        if sorted(got) != sorted(want):
            return f"Ожидались имена: {', '.join(want)}, а получились: {', '.join(got)}."
        if not any("переименовано" in line.lower() and str(len(want)) in line for line in v.lines):
            return f"В конце напечатай: «Переименовано: {len(want)}»."
        return None
    msg = r.each(check)
    if msg:
        return msg
    if not r.uses("enumerate"):
        return "Работает! Но номер удобнее получать через enumerate — попробуй переписать так."
    return None


# ---------------------------------------------------------------- урок 24: отчёт из многих файлов

def _week_kg(r):
    def check(v):
        total = sum(kg for _, kg, _ in v.data["rows"])
        if not v.printed_number(total):
            return f"За неделю продано {total} кг. Пройди по всем файлам: glob(\"*.csv\")."
        return None
    return r.each(check)


def _best(rows):
    c = Counter()
    for item, kg, _ in rows:
        c[item] += kg
    return c.most_common(1)[0][0]


def _top_item(r):
    def check(v):
        best = _best(v.data["rows"])
        if not v.printed(best):
            return f"Больше всего продано: {best}. counter.most_common(1) вернёт [(товар, кг)]."
        return None
    return r.each(check)


def _quest24(r):
    def check(v):
        rows = v.data["rows"]
        text = v.file("отчёт_за_неделю.txt")
        if text is None:
            return "Файла отчёт_за_неделю.txt нет. Создай его: open(\"отчёт_за_неделю.txt\", \"w\", encoding=\"utf-8\")."
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        want = [f"Всего продано: {sum(k for _, k, _ in rows)} кг", f"Выручка: {sum(k * p for _, k, p in rows)} руб.",
                f"Лучший товар: {_best(rows)}"]
        for i, exp in enumerate(want):
            if i >= len(lines):
                return f"В отчёте не хватает строки «{exp}»."
            if lines[i] != exp:
                return f"Строка {i + 1} отчёта: ожидалось «{exp}», а записано «{lines[i]}»."
        return None
    return r.each(check)


OFFICE = dict(chapter=6, robot="uhta", kits=[], lang="en", zone="office", beds=[], folder="контора")
LIST = 'from pathlib import Path\n\nfor p in sorted(Path("Загрузки").iterdir()):\n'

LESSONS = [
    Lesson(
        id="paths", title="Папки и пути", topic="pathlib: файлы в папке", data=_downloads, **OFFICE,
        notes="**from pathlib import Path** — работа с путями. **Path(\"Загрузки\")** — путь к папке.\n"
              "**.iterdir()** — всё, что лежит в папке. **sorted(...)** — по алфавиту.\n"
              "**p.name** — имя файла, **p.stem** — имя без расширения, **p.suffix** — расширение (.jpg).",
        steps=[
            Step("look", "Петя скинул в контору всё подряд: фото урожая, сканы, таблицы. Папка «Загрузки» — как у "
                         "всех нас. Открой её в Finder (кнопка с папкой). А в Python с папками работает модуль "
                         "**pathlib**: `Path` — это путь к файлу или папке.",
                 code='from pathlib import Path\n\nfolder = Path("Загрузки")\nfor p in folder.iterdir():\n    print(p.name)',
                 portrait="explain"),
            Step("run", "`iterdir()` перебирает всё, что лежит в папке. `sorted` — чтобы шло по алфавиту. "
                        "`p.suffix` — расширение: по нему понятно, что это за файл.",
                 code=LIST + "    print(p.name, p.suffix)", portrait="calm", show_memory=True,
                 after="Ухта прочитала содержимое настоящей папки на твоём Mac."),
            Step("fill", "Сколько в Загрузках фотографий с расширением .jpg?",
                 code="from pathlib import Path\n\ncount = 0\nfor p in sorted(Path(\"Загрузки\").iterdir()):\n"
                      "    if p.suffix == ____:\n        count = count + 1\nprint(\"Фото .jpg:\", count)",
                 check=_count_jpg, portrait="calm", show_memory=True, variants=2,
                 success="Расширение — строка с точкой: \".jpg\".", hints=["Расширение пишется с точкой.", 'p.suffix == ".jpg"']),
            Step("look", "У пути много полезного: имя, имя без расширения, расширение, размер. А `.lower()` спасает от "
                         "«IMG_4830.JPG» — расширения большими буквами.",
                 code='p = Path("Загрузки/IMG_4830.JPG")\np.name               # "IMG_4830.JPG"\np.stem               # "IMG_4830"\n'
                      'p.suffix             # ".JPG"\np.suffix.lower()     # ".jpg"\np.stat().st_size     # размер в байтах',
                 portrait="explain"),
            Step("write", "Посчитай файлы по каждому расширению и напечатай: «.jpg: 2», «.pdf: 2»… Словарь-копилка "
                          "тебе уже знаком.",
                 code="from pathlib import Path\n\ncounts = {}\nfor p in sorted(Path(\"Загрузки\").iterdir()):\n"
                      "    # прибавь 1 к counts[p.suffix]\n",
                 check=_by_suffix, portrait="calm", variants=2, success="Сводка по типам файлов готова.",
                 hints=["counts[p.suffix] = counts.get(p.suffix, 0) + 1",
                        'После цикла: for ext, n in counts.items(): print(f"{ext}: {n}")']),
        ],
        quest=Quest(
            giver="Петя",
            note="«Привет! Сколько у меня в Загрузках фоток, документов и таблиц? Фото — .jpg, .jpeg и .png, документы — "
                 ".pdf и .txt, таблицы — .csv. Напиши: „Фото: 4“, „Документы: 4“, „Таблицы: 2“. Ой, у некоторых фоток "
                 "расширение БОЛЬШИМИ буквами…»",
            goals=["Перебрать файлы в Загрузках", "Разделить на фото, документы и таблицы",
                   "Учесть расширения большими буквами", "Напечатать три строки"],
            starter='from pathlib import Path\n\nphotos = 0\ndocs = 0\ntables = 0\nfor p in sorted(Path("Загрузки").iterdir()):\n'
                    "    ext = p.suffix.lower()\n    # к какой группе относится файл?\n",
            check=_quest21, variants=2,
            solution='from pathlib import Path\n\nphotos = 0\ndocs = 0\ntables = 0\nfor p in sorted(Path("Загрузки").iterdir()):\n'
                     '    ext = p.suffix.lower()\n    if ext in [".jpg", ".jpeg", ".png"]:\n        photos = photos + 1\n'
                     '    elif ext in [".pdf", ".txt"]:\n        docs = docs + 1\n    elif ext == ".csv":\n        tables = tables + 1\n'
                     'print("Фото:", photos)\nprint("Документы:", docs)\nprint("Таблицы:", tables)',
            breakdown=[("    ext = p.suffix.lower()", ".JPG и .jpg станут одинаковыми."),
                       ('    if ext in [".jpg", ".jpeg", ".png"]:', "in со списком — «одно из»: короче, чем три or."),
                       ('    elif ext in [".pdf", ".txt"]:', "elif — «иначе если»: проверяется, только если первое не подошло."),
                       ('    elif ext == ".csv":', "Третья группа."),
                       ('print("Фото:", photos)', "Итоги — после цикла.")],
            alternative="Группы можно задать словарём: KINDS = {\".jpg\": \"Фото\", \".pdf\": \"Документы\", …} и считать "
                        "counts[KINDS.get(ext)] += 1 — тогда новую группу добавить — одна строчка.",
            life_title="Папки в жизни",
            life=["Узнать, чем забит диск: сколько фото, видео, документов и сколько они весят.",
                  "Найти все PDF за год в куче папок, все фото с телефона, все дубликаты.",
                  "pathlib — первый шаг к автоматизации рутины с файлами на любом компьютере."],
            try_at_home=["Открой Терминал: cd ~/Downloads (это твои настоящие Загрузки)",
                          "Скопируй туда ухта.py из папки «Робоферма/контора» и запусти: python3 ухта.py",
                          "Узнаешь, сколько у тебя фото, документов и таблиц!"],
            reward=50, hints=['ext in [".jpg", ".jpeg", ".png"] — «расширение одно из списка».',
                              "Три счётчика и if / elif / elif внутри цикла, три print после."],
            success="Петя: «Ого, сколько фоток! Слушай, а можно их как-то разложить?..»"),
    ),
    Lesson(
        id="folders", title="Раскладываем по папкам", topic="mkdir, rename, glob", data=_downloads, **OFFICE,
        notes="**папка / \"Фото\"** — путь внутри папки. **.mkdir(exist_ok=True)** — создать папку.\n"
              "**p.rename(новый_путь)** — переместить или переименовать файл.\n"
              "**Path(\"Загрузки\").glob(\"*.jpg\")** — все файлы по шаблону (* — что угодно).",
        steps=[
            Step("look", "Разложим Загрузки по папкам. Знак `/` склеивает пути: `downloads / \"Фото\"` — это "
                         "«Загрузки/Фото». `mkdir` создаёт папку, `exist_ok=True` — «не ругайся, если она уже есть».",
                 code='downloads = Path("Загрузки")\nphotos = downloads / "Фото"\nphotos.mkdir(exist_ok=True)',
                 portrait="explain"),
            Step("run", "`glob(\"*.jpg\")` — все файлы, которые кончаются на .jpg (звёздочка — «что угодно»). "
                        "`p.rename(новый путь)` переносит файл. Запусти и открой Загрузки в Finder!",
                 code='from pathlib import Path\n\ndownloads = Path("Загрузки")\nphotos = downloads / "Фото"\n'
                      'photos.mkdir(exist_ok=True)\nfor p in sorted(downloads.glob("*.jpg")):\n    p.rename(photos / p.name)',
                 portrait="calm", show_memory=True,
                 after="Фото переехали в папку «Фото» — прямо на твоём Mac. rename и переименовывает, и перемещает."),
            Step("fill", "Теперь документы .pdf — в папку «Документы». Куда перемещаем файл?",
                 code='from pathlib import Path\n\ndownloads = Path("Загрузки")\ndocs = downloads / "Документы"\n'
                      'docs.mkdir(exist_ok=True)\nfor p in sorted(downloads.glob("*.pdf")):\n    p.rename(docs / ____)',
                 check=_moved(".pdf", "Документы"), portrait="calm", variants=2,
                 success="docs / p.name — «папка Документы, файл с тем же именем».",
                 hints=["Имя файла не меняем — только папку.", "p.rename(docs / p.name)"]),
            Step("fix", "Ошибка FileNotFoundError: «нет такого файла или папки». Таблицы некуда класть! Что забыли?",
                 code='from pathlib import Path\n\ndownloads = Path("Загрузки")\ntables = downloads / "Таблицы"\n'
                      'for p in sorted(downloads.glob("*.csv")):\n    p.rename(tables / p.name)',
                 check=_moved(".csv", "Таблицы"), portrait="frown", variants=2,
                 success="Сначала создаём папку, потом кладём в неё файлы.",
                 hints=["Папки «Таблицы» ещё нет.", "tables.mkdir(exist_ok=True) — перед циклом."]),
        ],
        quest=Quest(
            giver="Петя",
            note="«Разложи всё по полочкам! Фото (.jpg, .jpeg, .png — в любом регистре) — в „Фото“, документы "
                 "(.pdf, .txt) — в „Документы“, таблицы (.csv) — в „Таблицы“. Всё внутри Загрузок».",
            goals=["Создать папки Фото, Документы, Таблицы", "Переложить каждый файл в свою папку",
                   "Не забыть про .JPG большими буквами"],
            starter='from pathlib import Path\n\ndownloads = Path("Загрузки")\nfor name in ["Фото", "Документы", "Таблицы"]:\n'
                    "    (downloads / name).mkdir(exist_ok=True)\n\nfor p in sorted(downloads.iterdir()):\n"
                    "    # какая папка подходит файлу?\n",
            check=_quest22, variants=2,
            solution='from pathlib import Path\n\ndownloads = Path("Загрузки")\nfor name in ["Фото", "Документы", "Таблицы"]:\n'
                     "    (downloads / name).mkdir(exist_ok=True)\n\nfor p in sorted(downloads.iterdir()):\n"
                     "    ext = p.suffix.lower()\n    if ext in [\".jpg\", \".jpeg\", \".png\"]:\n"
                     '        p.rename(downloads / "Фото" / p.name)\n    elif ext in [".pdf", ".txt"]:\n'
                     '        p.rename(downloads / "Документы" / p.name)\n    elif ext == ".csv":\n'
                     '        p.rename(downloads / "Таблицы" / p.name)',
            breakdown=[('for name in ["Фото", "Документы", "Таблицы"]:', "Три папки — одним циклом."),
                       ("    (downloads / name).mkdir(exist_ok=True)", "Создаём, если ещё нет."),
                       ("for p in sorted(downloads.iterdir()):",
                        "sorted сразу составляет весь список, поэтому новые папки не мешают циклу (у папок нет расширения)."),
                       ("    ext = p.suffix.lower()", ".JPG → .jpg."),
                       ('        p.rename(downloads / "Фото" / p.name)', "Переезд в нужную папку.")],
            alternative="Можно хранить правила в словаре: FOLDERS = {\".jpg\": \"Фото\", \".png\": \"Фото\", \".pdf\": \"Документы\"} "
                        "и писать folder = FOLDERS.get(ext); if folder: p.rename(downloads / folder / p.name).",
            life_title="Порядок в файлах",
            life=["Разобрать «Загрузки» или «Рабочий стол» за секунду — по типам, по годам, по проектам.",
                  "Разложить сканы документов по папкам клиентов, а фото — по датам съёмки.",
                  "Такой скрипт можно запускать раз в неделю — и в папках всегда порядок."],
            try_at_home=["Сделай копию папки с файлами (на всякий случай!).", "Положи туда ухта.py и запусти python3 ухта.py",
                          "Посмотри в Finder, как всё разложилось."],
            reward=55, hints=["В цикле: ext = p.suffix.lower(), потом if / elif / elif с p.rename(...).",
                              'p.rename(downloads / "Фото" / p.name) — путь склеивается слешами.'],
            success="Петя: «Красота! Теперь я хоть что-то найду. А фотки ещё бы переименовать…»"),
    ),
    Lesson(
        id="rename", title="Переименование", topic="enumerate и номера с нулями", data=_photos, **OFFICE,
        notes="**for i, p in enumerate(список, start=1):** — номер и элемент сразу.\n"
              "**f\"{i:03}\"** — номер с нулями впереди: 007. **p.parent** — папка, где лежит файл.\n"
              "Сначала напечатай, что получится, — и только потом переименовывай.",
        steps=[
            Step("look", "Петя хочет красивые имена для соцсетей: «урожай_001.jpg», «урожай_002.jpg»… Нужны номера. "
                         "**enumerate** даёт сразу номер и элемент. А `{i:03}` в f-строке пишет номер тремя цифрами, "
                         "с нулями впереди.",
                 code='for i, name in enumerate(["a.jpg", "b.jpg"], start=1):\n    print(i, name)\n\nprint(f"{7:03}")   # 007',
                 portrait="explain"),
            Step("run", "Профессиональный приём: сначала **напечатай**, что получится, и только потом переименовывай "
                        "по-настоящему. Запусти — файлы пока не трогаем.",
                 code='from pathlib import Path\n\nfor i, p in enumerate(sorted(Path("фото").iterdir()), start=1):\n'
                      '    print(p.name, "→", f"урожай_{i:03}{p.suffix}")',
                 portrait="calm", show_memory=True, after="Всё выглядит правильно? Тогда можно переименовывать."),
            Step("fill", "Переименуй по-настоящему. `p.parent` — папка, где лежит файл. Что добавить в конец имени?",
                 code='from pathlib import Path\n\nfor i, p in enumerate(sorted(Path("фото").iterdir()), start=1):\n'
                      '    p.rename(p.parent / f"урожай_{i:03}{____}")',
                 check=_renamed, portrait="calm", variants=2,
                 success="Пять фото переименованы за долю секунды. Тысячу — за секунду.",
                 hints=["Расширение файла нужно сохранить.", "{p.suffix}"]),
            Step("write", "Скриншоты в папке «скриншоты» называются «Снимок экрана 11.48.00.png». Переименуй их в "
                          "«скрин_01.png», «скрин_02.png»… — две цифры.",
                 code="from pathlib import Path\n\n# переименуй файлы в папке скриншоты\n", check=_shots,
                 portrait="calm", variants=2, success="{i:02} — две цифры, {i:03} — три. Сколько нужно, столько и пиши.",
                 hints=['for i, p in enumerate(sorted(Path("скриншоты").iterdir()), start=1):',
                        '    p.rename(p.parent / f"скрин_{i:02}.png")']),
        ],
        quest=Quest(
            giver="Петя",
            note="«Переименуй все фото в папке „фото“ в „осень_001.jpg“, „осень_002.png“… по порядку имён. "
                 "Расширение оставь, но маленькими буквами. И напиши, сколько файлов переименовано».",
            goals=["Пройти по фото по алфавиту", "Новое имя: осень_001 + расширение маленькими буквами",
                   "Напечатать «Переименовано: N»"],
            starter='from pathlib import Path\n\ncount = 0\nfor i, p in enumerate(sorted(Path("фото").iterdir()), start=1):\n'
                    "    # новое имя и rename\n",
            check=_quest23, variants=2,
            solution='from pathlib import Path\n\ncount = 0\nfor i, p in enumerate(sorted(Path("фото").iterdir()), start=1):\n'
                     '    p.rename(p.parent / f"осень_{i:03}{p.suffix.lower()}")\n    count = count + 1\n'
                     'print("Переименовано:", count)',
            breakdown=[('for i, p in enumerate(sorted(Path("фото").iterdir()), start=1):',
                        "Номер с единицы и файл — по алфавиту."),
                       ('    p.rename(p.parent / f"осень_{i:03}{p.suffix.lower()}")',
                        "Новое имя: номер тремя цифрами и расширение маленькими буквами."),
                       ("    count = count + 1", "Счётчик переименованных.")],
            alternative="Вместо счётчика можно напечатать i после цикла — это номер последнего файла. "
                        "А ещё в имя можно добавить дату: f\"{date.today()}_{i:03}.jpg\".",
            life_title="Переименование в жизни",
            life=["Фото с телефона, сканы, документы для отчёта — тысячи файлов с понятными именами за секунду.",
                  "Номера с нулями (001, 002…) нужны, чтобы файлы сортировались правильно: иначе 10 встанет перед 2.",
                  "Сначала печать, потом переименование — так не испортишь файлы ошибкой в коде."],
            try_at_home=["Сделай копию папки с фото!", "Положи туда ухта.py и замени \"фото\" на \".\" (текущая папка).",
                          "Сначала запусти версию с print — посмотри, что получится."],
            reward=55, hints=['Новое имя: f"осень_{i:03}{p.suffix.lower()}"',
                              "p.rename(p.parent / новое_имя), count = count + 1, а после цикла print."],
            success="Петя: «Осень_001, осень_002… Вот это я понимаю — контент-план!»"),
    ),
    Lesson(
        id="report", title="Отчёт за неделю", topic="glob и Counter: много файлов сразу", data=_week, **OFFICE,
        notes="**Path(\"неделя\").glob(\"*.csv\")** — все CSV в папке: можно обработать сто файлов одним циклом.\n"
              "**from collections import Counter** — словарь-счётчик: **c[\"тыква\"] += 3** сразу, без проверки ключа.\n"
              "**c.most_common(1)** — самый частый: [(\"тыква\", 40)].",
        steps=[
            Step("look", "Касса каждый день сохраняет продажи в отдельный файл: продажи_пн.csv, продажи_вт.csv… Неделя — "
                         "семь файлов. Сводить их руками долго, а цикл по файлам — одна строчка.",
                 code='from pathlib import Path\n\nfor p in sorted(Path("неделя").glob("*.csv")):\n    print(p.name)',
                 portrait="explain"),
            Step("run", "Запусти: Ухта найдёт все файлы недели.",
                 code='from pathlib import Path\n\nfor p in sorted(Path("неделя").glob("*.csv")):\n    print(p.name)',
                 portrait="calm", after="Семь файлов найдены. Дальше — прочитать каждый, как в амбаре."),
            Step("fill", "Посчитай, сколько килограммов продано за всю неделю. Какие файлы ищем?",
                 code='import csv\nfrom pathlib import Path\n\ntotal = 0\nfor p in sorted(Path("неделя").glob(____)):\n'
                      '    with open(p, encoding="utf-8") as f:\n        for row in csv.DictReader(f):\n'
                      '            total = total + int(row["кг"])\nprint("За неделю:", total, "кг")',
                 check=_week_kg, portrait="calm", show_memory=True, variants=2,
                 success="Семь файлов — один цикл. Будет семьсот — код тот же.",
                 hints=["Шаблон: звёздочка и расширение.", 'glob("*.csv")']),
            Step("look", "**Counter** — словарь-счётчик. Для нового ключа он сам начинает с нуля, поэтому не нужна "
                         "проверка `if item not in …`. А `most_common` возвращает самые частые.",
                 code='from collections import Counter\n\nc = Counter()\nc["тыква"] += 3\nc["морковь"] += 2\nc["тыква"] += 1\n'
                      'print(c.most_common(1))   # [(\'тыква\', 4)]', portrait="explain"),
            Step("write", "Найди товар, которого за неделю продано больше всего (по килограммам), и напечатай его название.",
                 code='import csv\nfrom collections import Counter\nfrom pathlib import Path\n\nkg = Counter()\n'
                      'for p in sorted(Path("неделя").glob("*.csv")):\n    with open(p, encoding="utf-8") as f:\n'
                      '        for row in csv.DictReader(f):\n            # прибавь килограммы к kg[товар]\n',
                 check=_top_item, portrait="calm", variants=2, success="Лучший товар недели найден!",
                 hints=['kg[row["товар"]] += int(row["кг"])', "best, amount = kg.most_common(1)[0]\nprint(best)"]),
        ],
        quest=Quest(
            giver="Инспектор Сидоров",
            note="«Гражданин фермер. Еженедельный отчёт — в файл отчёт_за_неделю.txt, строго три строки:\n"
                 "Всего продано: 116 кг\nВыручка: 4090 руб.\nЛучший товар: морковь»",
            goals=["Прочитать все файлы из папки «неделя»", "Посчитать килограммы и выручку",
                   "Найти лучший товар (Counter)", "Записать три строки в отчёт_за_неделю.txt"],
            starter='import csv\nfrom collections import Counter\nfrom pathlib import Path\n\ntotal_kg = 0\nmoney = 0\nkg = Counter()\n'
                    '# 1) пройди по всем файлам недели\n# 2) запиши отчёт\n',
            check=_quest24, variants=2,
            solution='import csv\nfrom collections import Counter\nfrom pathlib import Path\n\ntotal_kg = 0\nmoney = 0\nkg = Counter()\n'
                     'for p in sorted(Path("неделя").glob("*.csv")):\n    with open(p, encoding="utf-8") as f:\n'
                     '        for row in csv.DictReader(f):\n            amount = int(row["кг"])\n'
                     '            total_kg = total_kg + amount\n            money = money + amount * int(row["цена"])\n'
                     '            kg[row["товар"]] += amount\n\nbest = kg.most_common(1)[0][0]\n'
                     'with open("отчёт_за_неделю.txt", "w", encoding="utf-8") as f:\n'
                     '    f.write(f"Всего продано: {total_kg} кг\\n")\n    f.write(f"Выручка: {money} руб.\\n")\n'
                     '    f.write(f"Лучший товар: {best}\\n")',
            breakdown=[('for p in sorted(Path("неделя").glob("*.csv")):', "Все файлы недели по порядку."),
                       ("        for row in csv.DictReader(f):", "Каждая строка каждого файла."),
                       ('            kg[row["товар"]] += amount', "Counter копит килограммы по товарам."),
                       ("best = kg.most_common(1)[0][0]",
                        "most_common(1) → [(\"морковь\", 47)]; [0] — первая пара, ещё [0] — название."),
                       ('    f.write(f"Всего продано: {total_kg} кг\\n")', "Три строки отчёта с переносами.")],
            alternative="Отчёт можно собрать в список строк и записать разом: f.write(\"\\n\".join(lines)). "
                        "А дату недели — взять из имени файла или из date.today().",
            life_title="Отчёты из многих файлов",
            life=["Еженедельные и ежемесячные отчёты из десятков выгрузок — классическая офисная рутина.",
                  "Скрипт сводит файлы за секунды и не ошибается при копировании цифр.",
                  "Counter отвечает на вопросы «что чаще всего»: популярные товары, частые слова, активные клиенты."],
            try_at_home=["cd ~/Documents/Робоферма/контора", "python3 ухта.py", "open отчёт_за_неделю.txt"],
            reward=60, hints=["Внутри двойного цикла: amount = int(row[\"кг\"]), потом три прибавления.",
                              'best = kg.most_common(1)[0][0], потом open(..., "w") и три f.write с \\n.'],
            success="Сидоров: «Три строки, всё сходится. Образцовая ферма. Так и запишу»."),
    ),
]

CHAPTER = Chapter(
    number=6, title="Контора", zone="office", robot="uhta", lessons=LESSONS,
    intro=[("klusha", "explain", "У бабушки в доме есть контора. Там живёт сова Ухта — она отвечает за бумаги."),
           ("uhta", "happy", "Уху! Петя завалил мне стол: фото, сканы, таблицы — всё в одной куче. Помогите навести порядок."),
           ("klusha", "proud", "Это самая жизненная глава: «Загрузки» у всех такие. Файлы — в папке «Робоферма/контора».")],
    outro=[("uhta", "happy", "Уху! Файлы по папкам, фото с красивыми именами, отчёт для Сидорова готов."),
           ("klusha", "proud", "pathlib, переименование, много файлов сразу — ты {сделал|сделала} то, что экономит часы в любом офисе."),
           ("klusha", "happy", "А теперь — главное событие осени. Осенняя ярмарка! Готовимся всей командой.")],
    automation=("Ухта разбирает бумаги", 20),
)
