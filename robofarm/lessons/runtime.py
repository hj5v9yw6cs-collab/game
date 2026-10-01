"""Как запустить шаг урока: какие данные дать песочнице и как потом проверить результат.

Этим модулем пользуются и игра, и автотесты, поэтому в тестах код игрока проверяется
ровно так же, как в игре.
"""

from robofarm.lessons.base import Result

PAYLOAD_KEYS = ("beds", "queue", "orders", "inject", "files", "calls")


def target(lesson, index):
    """Шаг урока по номеру; номер после последнего шага — задание (Quest)."""
    return lesson.quest if index >= len(lesson.steps) else lesson.steps[index]


def is_quest(lesson, st):
    return st is lesson.quest


def data_for(lesson, st, variant=0):
    """Данные для шага: грядки, очередь, заказы, файлы… Вариант 0 — то, что видно в мире."""
    fn = getattr(st, "data", None) or lesson.data
    d = dict(fn(variant)) if fn else {}
    if "beds" not in d:
        beds = getattr(st, "beds", None)
        d["beds"] = beds if beds is not None else lesson.beds
    calls = getattr(st, "calls", None)
    if calls and "calls" not in d:
        d["calls"] = calls
    return d


def build(lesson, st, code, workdir=None):
    """Готовит запрос к песочнице. Возвращает (payload, данные варианта 0, данные скрытых вариантов)."""
    data0 = data_for(lesson, st, 0)
    hidden = [data_for(lesson, st, i) for i in range(1, getattr(st, "variants", 0) + 1)]
    payload = {"code": code, "lang": lesson.lang, "kits": lesson.kits, "field_var": lesson.field_var}
    for key in PAYLOAD_KEYS:
        if data0.get(key) is not None:
            payload[key] = data0[key]
    if payload.get("files") is not None and workdir:
        payload["workdir"] = str(workdir)
    if hidden:
        payload["variants"] = [{k: d[k] for k in PAYLOAD_KEYS if d.get(k) is not None} for d in hidden]
    return payload, data0, hidden


def result(raw, code, data0, hidden):
    return Result(raw, code, data0, hidden)


def check(lesson, st, r):
    """None — всё верно, иначе — строка с подсказкой."""
    fn = st.check
    return fn(r) if fn else None
