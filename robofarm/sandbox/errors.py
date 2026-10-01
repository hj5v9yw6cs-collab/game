"""Объяснения ошибок Python простыми словами (голосом Клуши)."""

import difflib
import traceback

from robofarm.farm import HOMOGLYPHS, mixed_script


class ExecTimeout(BaseException):
    """Код работает слишком долго (BaseException, чтобы его не поймал `except Exception`)."""


class OutputLimit(BaseException):
    pass


class InputNotSupported(Exception):
    pass


_RU = "йцукенгшщзхъфывапролджэячсмитьбюё"
_EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"
RU_TO_EN = str.maketrans(_RU, _EN)
EN_TO_RU = str.maketrans(_EN, _RU)

COMMON_NAMES = ["print", "len", "range", "int", "str", "float", "input", "sum", "max", "min",
                "sorted", "list", "dict", "True", "False", "None", "round", "abs"]


def _syntax_title(e):
    msg = (e.msg or "").lower()
    if isinstance(e, IndentationError):
        if "expected an indented block" in msg:
            return "после двоеточия нужен отступ — 4 пробела в начале следующей строки"
        if "unexpected indent" in msg:
            return "лишний отступ в начале строки"
        return "отступы не совпадают"
    if "expected ':'" in msg:
        return "не хватает двоеточия «:» в конце строки"
    if "unterminated string" in msg or "eol while scanning" in msg or "unterminated triple" in msg:
        return "не закрыта кавычка"
    if "was never closed" in msg:
        return "не закрыта скобка"
    if "unmatched" in msg or "does not match" in msg:
        return "лишняя или не та закрывающая скобка"
    if "invalid character" in msg:
        return "в коде есть недопустимый символ"
    if "forgot a comma" in msg:
        return "кажется, пропущена запятая"
    if "cannot assign" in msg or "assign to" in msg:
        return "слева от «=» должно стоять имя переменной"
    if "maybe you meant '==' or ':='" in msg or "maybe you meant '=='" in msg:
        return "для сравнения нужно «==», а «=» — это запись в переменную"
    return "Python не понял запись"


def _syntax_hint(e):
    msg = (e.msg or "").lower()
    if isinstance(e, IndentationError):
        return ("Код внутри for, if и def сдвигается вправо на 4 пробела (клавиша Tab), "
                "и все строки одного блока должны начинаться ровно с одного отступа.")
    if "expected ':'" in msg:
        return "После for, if, else, while и def в конце строки ставится двоеточие «:». Оно говорит: дальше идёт блок команд."
    if "unterminated string" in msg or "eol while scanning" in msg:
        return "Текст в кавычках должен и начинаться, и заканчиваться кавычкой: \"вот так\"."
    if "was never closed" in msg:
        return "Каждой открывающей скобке «(» нужна закрывающая «)». Посчитай скобки в строке."
    if "invalid character" in msg:
        return ("Скорее всего, это «ёлочки» или «умные» кавычки из текстового редактора. "
                "В коде нужны обычные прямые кавычки: \" или '.")
    if "forgot a comma" in msg:
        return "Между значениями в скобках ставится запятая: print(\"Урожай:\", кг)."
    if "cannot assign" in msg:
        return "Запись в переменную выглядит так: имя = значение. Например: урожай = 5."
    return "Частые причины: забыто двоеточие после if/for, не закрыта скобка или кавычка, опечатка."


def explain(e, known_names=(), bed_names=()):
    """(короткий заголовок, подробная подсказка) для ошибки."""
    msg = str(e)
    if isinstance(e, ExecTimeout):
        return ("программа работала слишком долго",
                "Похоже на бесконечный цикл: проверь условие while и что внутри цикла что-то меняется.")
    if isinstance(e, OutputLimit):
        return ("слишком много текста", "Похоже, print() стоит внутри бесконечного цикла.")
    if isinstance(e, InputNotSupported):
        return ("input() здесь не нужен",
                "Роботы работают сами, без человека у клавиатуры. Данные берутся из переменных и файлов.")
    if isinstance(e, SyntaxError):
        return _syntax_title(e), _syntax_hint(e)
    if isinstance(e, NameError):
        name = getattr(e, "name", None) or (msg.split("'")[1] if "'" in msg else "")
        title = f"Python не знает слова «{name}»"
        if name in bed_names:
            return title, (f"Если это название грядки — возьми его в кавычки: \"{name}\". "
                           "Без кавычек Python ищет переменную с таким именем.")
        if mixed_script(name):
            return title, (f"В слове «{name}» перемешаны русские и английские буквы — "
                           "так бывает, если забыть переключить раскладку. Сотри слово и напиши заново.")
        candidates = list(known_names) + COMMON_NAMES
        for swapped in (name.lower().translate(RU_TO_EN), name.lower().translate(EN_TO_RU)):
            if swapped != name.lower() and swapped in candidates:
                return title, (f"Похоже, слово набрано не в той раскладке клавиатуры: «{name}» — это «{swapped}». "
                               "Переключи язык (на Mac: Ctrl + Пробел или Fn) и напиши заново.")
        fixed = name.translate(HOMOGLYPHS)
        close = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
        if not close and fixed != name:
            close = difflib.get_close_matches(fixed, candidates, n=1, cutoff=0.6)
        if close:
            return title, f"Может быть, ты {{имел|имела}} в виду «{close[0]}»? Проверь опечатки и регистр букв."
        return title, ("Проверь опечатки и регистр букв (Урожай и урожай — разные имена). "
                       "Если это текст — возьми его в кавычки. Если переменная — создай её выше: имя = значение.")
    if isinstance(e, TypeError):
        if "can only concatenate str" in msg or ("must be str" in msg and "concatenate" in msg):
            return ("нельзя склеить текст и число через «+»",
                    "Используй запятую: print(\"Урожай:\", кг) — или превращай число в текст: str(кг).")
        if "unsupported operand" in msg:
            return ("так эти значения сложить нельзя",
                    "Похоже, одно из значений — текст в кавычках, а другое — число. "
                    "Число в кавычках \"5\" — это текст, а без кавычек 5 — число.")
        if "missing" in msg and "required positional argument" in msg:
            return ("команде не сказали, с чем работать",
                    "В скобках нужно указать значение. Например: полить(\"тыква\").")
        if "takes" in msg and "given" in msg:
            return ("команде передали лишнее", "Проверь, сколько значений стоит в скобках через запятую.")
        if "not callable" in msg:
            return ("это нельзя вызвать скобками", "Скобки () ставятся после команд. Проверь, не стоят ли они после числа или текста.")
        if "ждёт название грядки" in msg:
            return ("команде нужно название грядки", msg)
        return ("значение не того типа", "Проверь, где у тебя числа, а где текст в кавычках.")
    if isinstance(e, ValueError):
        if "Грядки «" in msg:
            return ("такой грядки нет", msg)
        if "invalid literal for int()" in msg or "could not convert" in msg:
            return ("это не превращается в число",
                    "int() и float() умеют превращать в число только текст из цифр, например \"42\".")
        return ("неподходящее значение", msg)
    if isinstance(e, ZeroDivisionError):
        return ("деление на ноль", "Делить на 0 нельзя. Проверь, что делитель не равен нулю.")
    if isinstance(e, KeyError):
        return (f"в словаре нет ключа {msg}", "Проверь, как точно написан ключ — с теми же буквами и регистром.")
    if isinstance(e, IndexError):
        return ("такого номера нет", "Нумерация в списках начинается с 0, а последний элемент — [-1].")
    if isinstance(e, AttributeError):
        return ("у значения нет такого свойства", "Проверь тип значения и написание после точки.")
    if isinstance(e, RecursionError):
        return ("функция вызывает сама себя без конца", "Проверь условие выхода.")
    if isinstance(e, FileNotFoundError):
        return ("файл не найден", "Проверь имя файла и папку.")
    if isinstance(e, ImportError):
        return ("такого модуля нет", "Проверь название модуля после import.")
    return (f"ошибка {type(e).__name__}", "Прочитай последнюю строку сообщения — там сказано, что пошло не так.")


def describe(e, code, known_names=(), bed_names=()):
    """Ошибка для интерфейса: строка, заголовок, подсказка и настоящий текст Python."""
    src = code.split("\n")
    title, hint = explain(e, known_names, bed_names)
    if isinstance(e, ExecTimeout):
        name, message = "TimeoutError", "программа работала слишком долго"
    elif isinstance(e, OutputLimit):
        name, message = "OutputLimit", "слишком много вывода"
    else:
        name, message = type(e).__name__, str(e)
    if isinstance(e, SyntaxError) and e.filename in ("main.py", None, "<unknown>"):
        line = e.lineno
        text = (e.text or "").rstrip("\n")
        stripped = text.lstrip()
        caret = ""
        if e.offset and stripped:
            shift = len(text) - len(stripped)
            caret = "\n    " + " " * max(0, e.offset - 1 - shift) + "^"
        trace = f'  File "main.py", line {line}\n    {stripped}{caret}\n{name}: {e.msg}'
        message = e.msg
    else:
        frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == "main.py"]
        parts = ["Traceback (most recent call last):"]
        for f in frames:
            parts.append(f'  File "main.py", line {f.lineno}, in {f.name}')
            if f.lineno and 0 < f.lineno <= len(src) and src[f.lineno - 1].strip():
                parts.append("    " + src[f.lineno - 1].strip())
        parts.append(f"{name}: {message}" if message else name)
        trace = "\n".join(parts)
        line = frames[-1].lineno if frames else None
    if line:
        title = f"Строка {line}: {title}"
    return {"type": name, "message": message, "line": line, "title": title, "hint": hint, "trace": trace}
