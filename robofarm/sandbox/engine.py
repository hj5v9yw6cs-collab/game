"""Выполнение кода игрока с записью каждого шага.

Код запускается настоящим Python. Пока он работает, записываются события:
  {"k": "line", "ln": 3, "d": {...}, "rm": [...]}  — строка 3 сейчас выполнится; d/rm — что изменилось в памяти
  {"k": "act", "ln": 3, "cmd": "water", ...}       — робот сделал действие
  {"k": "out", "ln": 4, "text": "..."}             — print() напечатал текст
Игра потом проигрывает эти события анимацией: подсвечивает строки, двигает робота, обновляет «Память».
"""

import ast
import builtins
import io
import json
import math
import sys
import time
import types

from robofarm.farm import FarmSim, player_view
from robofarm.sandbox.errors import ExecTimeout, InputNotSupported, OutputLimit, describe

DEFAULT_LIMITS = {"time": 3.0, "events": 5000, "output": 20000}
API_NAMES = {"полить", "собрать", "water", "harvest"}


def snap(value, depth=0):
    """Значение переменной в виде, удобном для окна «Память робота»."""
    if value is None:
        return {"t": "none"}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "num", "v": str(value)}
    if isinstance(value, float):
        text = repr(value) if math.isfinite(value) else str(value)
        return {"t": "num", "v": text}
    if isinstance(value, str):
        return {"t": "str", "v": value[:80], "cut": len(value) > 80}
    if isinstance(value, (list, tuple)) and depth < 2:
        return {"t": "list", "tuple": isinstance(value, tuple), "len": len(value),
                "items": [snap(v, depth + 1) for v in value[:10]]}
    if isinstance(value, dict) and depth < 2:
        return {"t": "dict", "len": len(value),
                "items": [[repr(k)[:30], snap(v, depth + 1)] for k, v in list(value.items())[:10]]}
    return {"t": "other", "type": type(value).__name__, "v": repr(value)[:80]}


def user_vars(namespace, hidden):
    result = {}
    for name, value in namespace.items():
        if name.startswith("_") or name in hidden:
            continue
        if isinstance(value, (types.ModuleType, types.FunctionType, types.BuiltinFunctionType, type)):
            continue
        result[name] = value
    return result


class Recorder:
    def __init__(self, limits):
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.events = []
        self.truncated = False
        self.line = None
        self.last_vars = {}
        self.out_parts = []
        self.out_size = 0

    def add(self, event):
        if len(self.events) >= self.limits["events"]:
            self.truncated = True
            return
        if event["k"] == "act" or event["k"] == "out":
            event.setdefault("ln", self.line)
        if event["k"] == "out" and self.events and self.events[-1]["k"] == "out" \
                and self.events[-1]["ln"] == event["ln"]:
            self.events[-1]["text"] += event["text"]
            return
        self.events.append(event)

    def write(self, text):
        self.out_size += len(text)
        if self.out_size > self.limits["output"]:
            raise OutputLimit()
        self.out_parts.append(text)
        self.add({"k": "out", "text": text})

    def diff_vars(self, current):
        snaps = {name: snap(v) for name, v in current.items()}
        changed = {n: s for n, s in snaps.items() if self.last_vars.get(n) != s}
        removed = [n for n in self.last_vars if n not in snaps]
        self.last_vars = snaps
        return changed, removed


class _Stdout(io.TextIOBase):
    def __init__(self, recorder):
        self.recorder = recorder

    def writable(self):
        return True

    def write(self, s):
        self.recorder.write(s)
        return len(s)


def _no_input(prompt=""):
    raise InputNotSupported("input() недоступен")


def static_warnings(tree, known_callables):
    """Типичные ошибки новичка, которые Python не считает ошибками."""
    warnings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        v = node.value
        if isinstance(v, ast.Name) and v.id in known_callables:
            warnings.append({"line": node.lineno,
                             "text": f"Команда «{v.id}» написана без скобок — робот её не выполнит. Нужно: {v.id}(…)"})
        elif isinstance(v, ast.Compare) and len(v.ops) == 1 and isinstance(v.ops[0], ast.Eq):
            warnings.append({"line": node.lineno,
                             "text": "Сравнение «==» само по себе ничего не меняет. Для записи в переменную нужен один знак «=»."})
        elif isinstance(v, ast.Constant) and isinstance(v.value, str) and node.lineno > 1 \
                and "(" in v.value and ")" in v.value:
            warnings.append({"line": node.lineno,
                             "text": "Эта строка целиком в кавычках — для Python это просто текст, а не команда."})
    return warnings


def run(payload):
    """payload: {"code": str, "beds": [...], "lang": "ru"|"en"|"both", "inject": {...}, "limits": {...}}"""
    code = payload.get("code", "")
    rec = Recorder(payload.get("limits"))
    farm = FarmSim(payload.get("beds", []), rec.add)
    commands = farm.commands(payload.get("lang", "ru"))
    inject = dict(payload.get("inject") or {})
    if payload.get("field_var"):
        inject[payload["field_var"]] = [player_view(b) for b in farm.beds]
    g = {"__name__": "__main__", "__builtins__": builtins}
    g.update(commands)
    g.update(inject)
    hidden = set(commands)
    bed_names = [b["name"] for b in farm.beds]
    known = list(commands) + bed_names

    result = {"events": rec.events, "stdout": "", "error": None, "warnings": [], "lines": 0, "ms": 0.0}
    try:
        tree = ast.parse(code, "main.py")
        compiled = compile(tree, "main.py", "exec")
    except (SyntaxError, ValueError) as e:
        if not isinstance(e, SyntaxError):
            e = SyntaxError(str(e))
        result["error"] = describe(e, code, known, bed_names)
        return _finish(result, rec, farm, g, hidden)
    result["warnings"] = static_warnings(tree, set(commands) | {"print", "len", "input"})

    deadline = time.monotonic() + rec.limits["time"]
    counter = [0]

    def local(frame, event, arg):
        if event == "line":
            counter[0] += 1
            rec.line = frame.f_lineno
            if not counter[0] & 255 and time.monotonic() > deadline:
                raise ExecTimeout()
            if not rec.truncated:
                scope = dict(frame.f_globals)
                if frame.f_code.co_name != "<module>":
                    scope.update(frame.f_locals)
                changed, removed = rec.diff_vars(user_vars(scope, hidden))
                ev = {"k": "line", "ln": frame.f_lineno}
                if changed:
                    ev["d"] = changed
                if removed:
                    ev["rm"] = removed
                rec.add(ev)
        return local

    def glob(frame, event, arg):
        return local if frame.f_code.co_filename == "main.py" else None

    old = (sys.stdout, sys.stderr, builtins.input)
    sys.stdout = sys.stderr = _Stdout(rec)
    builtins.input = _no_input
    t0 = time.perf_counter()
    sys.settrace(glob)
    try:
        exec(compiled, g)
    except SystemExit:
        pass
    except BaseException as e:  # noqa: BLE001 — любая ошибка кода игрока показывается ему
        sys.settrace(None)
        result["error"] = describe(e, code, known + list(user_vars(g, hidden)), bed_names)
    finally:
        sys.settrace(None)
        sys.stdout, sys.stderr, builtins.input = old
    result["ms"] = round((time.perf_counter() - t0) * 1000, 2)
    result["lines"] = counter[0]
    return _finish(result, rec, farm, g, hidden)


def _finish(result, rec, farm, g, hidden):
    result["stdout"] = "".join(rec.out_parts)
    result["truncated"] = rec.truncated
    result["beds"] = farm.beds
    result["vars"] = {n: snap(v) for n, v in user_vars(g, hidden).items()}
    return result


def main():
    payload = json.loads(sys.stdin.read())
    result = run(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
