"""Выполнение кода игрока с записью каждого шага.

Код запускается настоящим Python. Пока он работает, записываются события:
  {"k": "line", "ln": 3, "d": {...}, "rm": [...]}  — строка 3 сейчас выполнится; d/rm — что изменилось в памяти
  {"k": "act", "ln": 3, "cmd": "water", ...}       — робот сделал действие
  {"k": "out", "ln": 4, "text": "..."}             — print() напечатал текст
  {"k": "file", "ln": 5, "op": "read", "path": …}  — программа прочитала или записала файл
Игра потом проигрывает эти события анимацией: подсвечивает строки, двигает робота, обновляет «Память».

Кроме основного запуска код можно прогнать на скрытых вариантах данных (чтобы ответ,
«вписанный руками», не прошёл) и вызвать функции игрока с тестовыми значениями.
"""

import ast
import builtins
import io
import json
import math
import os
import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

from robofarm.farm import FarmSim, PostSim, ShopSim, player_view_en, player_view_ru
from robofarm.sandbox.errors import ExecTimeout, InputNotSupported, OutputLimit, describe

DEFAULT_LIMITS = {"time": 3.0, "events": 6000, "output": 20000}
TEXT_LIMIT = 60000


def snap(value, depth=0):
    """Значение переменной в виде, удобном для окна «Память робота»."""
    if value is None:
        return {"t": "none"}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "num", "v": str(value)}
    if isinstance(value, float):
        text = repr(round(value, 6)) if math.isfinite(value) else str(value)
        return {"t": "num", "v": text}
    if isinstance(value, str):
        return {"t": "str", "v": value[:80], "cut": len(value) > 80}
    if isinstance(value, (list, tuple)) and depth < 2:
        return {"t": "list", "tuple": isinstance(value, tuple), "len": len(value),
                "items": [snap(v, depth + 1) for v in value[:10]]}
    if isinstance(value, dict) and depth < 2:
        return {"t": "dict", "len": len(value),
                "items": [[repr(k)[:30], snap(v, depth + 1)] for k, v in list(value.items())[:10]]}
    return {"t": "other", "type": type(value).__name__, "v": describe_object(value)[:80]}


def describe_object(value):
    """Понятная подпись для «Памяти» вместо <_io.TextIOWrapper …>."""
    import datetime
    import pathlib
    if isinstance(value, pathlib.PurePath):
        return f"путь «{value.as_posix()}»"
    if isinstance(value, io.IOBase) and hasattr(value, "name"):
        state = "закрыт" if value.closed else "открыт"
        return f"файл «{value.name}» ({state})"
    if isinstance(value, datetime.datetime):
        return f"дата и время {value.isoformat(sep=' ', timespec='minutes')}"
    if isinstance(value, datetime.date):
        return f"дата {value.isoformat()}"
    if isinstance(value, datetime.timedelta):
        return f"промежуток {value.days} дн."
    if isinstance(value, (set, frozenset)):
        return "{" + ", ".join(repr(v) for v in list(value)[:6]) + ("…}" if len(value) > 6 else "}")
    name = type(value).__name__
    if name == "DictReader":
        return "читатель таблицы (csv.DictReader)"
    if name == "writer" or name == "_writer":
        return "писатель таблицы (csv.writer)"
    return repr(value)


def plain(value, depth=0):
    """Значение, которое можно передать в JSON (для проверок)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if depth > 4:
        return repr(value)[:200]
    if isinstance(value, (list, tuple)):
        return [plain(v, depth + 1) for v in value[:200]]
    if isinstance(value, dict):
        return {str(k): plain(v, depth + 1) for k, v in list(value.items())[:200]}
    if isinstance(value, (set, frozenset)):
        return sorted((plain(v, depth + 1) for v in value), key=repr)[:200]
    return repr(value)[:200]


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
    def __init__(self, limits, record_lines=True):
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.record_lines = record_lines
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
        if event["k"] != "line":
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
                             "text": f"Команда «{v.id}» написана без скобок — она не выполнится. Нужно: {v.id}(…)"})
        elif isinstance(v, ast.Compare) and len(v.ops) == 1 and isinstance(v.ops[0], ast.Eq):
            warnings.append({"line": node.lineno,
                             "text": "Сравнение «==» само по себе ничего не меняет. Для записи в переменную нужен один знак «=»."})
        elif isinstance(v, ast.Constant) and isinstance(v.value, str) and node.lineno > 1 \
                and "(" in v.value and ")" in v.value:
            warnings.append({"line": node.lineno,
                             "text": "Эта строка целиком в кавычках — для Python это просто текст, а не команда."})
    return warnings


# ---------------------------------------------------------------- файлы урока

def write_files(root, files):
    root = Path(root)
    for rel, content in (files or {}).items():
        target = root / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict) and "b64" in content:
            import base64
            target.write_bytes(base64.b64decode(content["b64"]))
        else:
            target.write_text(content, encoding="utf-8", newline="")


def reset_dir(root, files):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    write_files(root, files)


def snapshot(root):
    """Все файлы и папки рабочей папки после запуска: путь → текст (или размер)."""
    root = Path(root)
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            result[rel + "/"] = None
            continue
        size = path.stat().st_size
        text = None
        if size <= TEXT_LIMIT:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (UnicodeDecodeError, OSError):
                text = None
        result[rel] = text if text is not None else {"size": size}
    return result


class FileWatch:
    """Подменяет open/rename/mkdir, чтобы записать, что программа делала с файлами."""

    def __init__(self, root, rec):
        self.root = Path(root).resolve() if root else None
        self.rec = rec

    def _rel(self, p):
        try:
            full = Path(os.fspath(p))
            if not full.is_absolute():
                full = Path.cwd() / full
            return full.resolve().relative_to(self.root).as_posix()
        except (ValueError, TypeError, OSError):
            return None

    def __enter__(self):
        if not self.root:
            return self
        self.saved = (builtins.open, io.open, os.rename, os.replace, os.mkdir, os.remove, os.unlink)
        real_open, real_rename, real_replace, real_mkdir, real_remove = (
            builtins.open, os.rename, os.replace, os.mkdir, os.remove)
        rec = self.rec

        def open_(file, mode="r", *args, **kwargs):
            f = real_open(file, mode, *args, **kwargs)
            if not isinstance(file, int):
                rel = self._rel(file)
                if rel is not None:
                    op = "write" if any(m in mode for m in "wax+") else "read"
                    rec.add({"k": "file", "op": op, "path": rel})
            return f

        def rename_(src, dst, *a, **k):
            real_rename(src, dst, *a, **k)
            rec.add({"k": "file", "op": "move", "path": self._rel(src), "to": self._rel(dst)})

        def replace_(src, dst, *a, **k):
            real_replace(src, dst, *a, **k)
            rec.add({"k": "file", "op": "move", "path": self._rel(src), "to": self._rel(dst)})

        def mkdir_(path, *a, **k):
            real_mkdir(path, *a, **k)
            rec.add({"k": "file", "op": "mkdir", "path": self._rel(path)})

        def remove_(path, *a, **k):
            real_remove(path, *a, **k)
            rec.add({"k": "file", "op": "delete", "path": self._rel(path)})

        builtins.open = io.open = open_
        os.rename, os.replace, os.mkdir = rename_, replace_, mkdir_
        os.remove = os.unlink = remove_
        return self

    def __exit__(self, *exc):
        if self.root:
            builtins.open, io.open, os.rename, os.replace, os.mkdir, os.remove, os.unlink = self.saved
        return False


# ---------------------------------------------------------------- один запуск

def _run_once(code, spec, workdir, record_lines, calls=None):
    rec = Recorder(spec.get("limits"), record_lines)
    lang = spec.get("lang", "ru")
    farm = FarmSim(spec.get("beds", []), rec.add)
    shop = ShopSim(spec.get("queue"), rec.add)
    post = PostSim(spec.get("orders"), rec.add)
    kits = spec.get("kits", ["garden"])
    commands = {}
    if "garden" in kits:
        commands.update(farm.commands(lang))
    if "shop" in kits:
        commands.update(shop.commands())
    if "post" in kits:
        commands.update(post.commands())
    inject = json.loads(json.dumps(spec.get("inject") or {}, ensure_ascii=False))
    if "shop" in kits and spec.get("queue") is not None:
        inject.setdefault("queue", json.loads(json.dumps(spec["queue"], ensure_ascii=False)))
    if spec.get("field_var"):
        view = player_view_en if lang == "en" else player_view_ru
        inject[spec["field_var"]] = [view(b) for b in farm.beds]
    g = {"__name__": "__main__", "__builtins__": builtins}
    g.update(commands)
    g.update(inject)
    hidden = set(commands)
    bed_names = [b["name"] for b in farm.beds]
    known = list(commands) + bed_names + list(inject)

    result = {"events": rec.events, "stdout": "", "error": None, "warnings": [], "lines": 0, "ms": 0.0}
    cwd = os.getcwd()
    if workdir:
        os.chdir(workdir)
    try:
        try:
            tree = ast.parse(code, "main.py")
            compiled = compile(tree, "main.py", "exec")
        except (SyntaxError, ValueError) as e:
            if not isinstance(e, SyntaxError):
                e = SyntaxError(str(e))
            result["error"] = describe(e, code, known, bed_names)
            return _finish(result, rec, farm, shop, post, g, hidden, workdir)
        result["warnings"] = static_warnings(tree, set(commands) | {"print", "len", "input"})

        deadline = time.monotonic() + rec.limits["time"]
        counter = [0]

        def local(frame, event, arg):
            if event == "line":
                counter[0] += 1
                rec.line = frame.f_lineno
                if not counter[0] & 255 and time.monotonic() > deadline:
                    raise ExecTimeout()
                if rec.record_lines and not rec.truncated:
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
        try:
            with FileWatch(workdir, rec):
                sys.settrace(glob)
                try:
                    exec(compiled, g)
                except SystemExit:
                    pass
                except BaseException as e:  # noqa: BLE001 — любая ошибка кода игрока показывается ему
                    sys.settrace(None)
                    result["error"] = describe(e, code, known + list(user_vars(g, hidden)), bed_names)
                if calls and result["error"] is None:
                    result["calls"] = _do_calls(calls, g, code, known, bed_names)
        finally:
            sys.settrace(None)
            sys.stdout, sys.stderr, builtins.input = old
        result["ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["lines"] = counter[0]
        return _finish(result, rec, farm, shop, post, g, hidden, workdir)
    finally:
        os.chdir(cwd)


def _do_calls(calls, g, code, known, bed_names):
    out = []
    for call in calls:
        name, args = call["fn"], call.get("args", [])
        fn = g.get(name)
        entry = {"fn": name, "args": args}
        if fn is None:
            entry["missing"] = True
        elif not callable(fn):
            entry["missing"] = True
            entry["not_callable"] = type(fn).__name__
        else:
            try:
                entry["value"] = plain(fn(*json.loads(json.dumps(args))))
                entry["ok"] = True
            except BaseException as e:  # noqa: BLE001
                entry["error"] = describe(e, code, known, bed_names)
        out.append(entry)
    return out


def _finish(result, rec, farm, shop, post, g, hidden, workdir):
    result["stdout"] = "".join(rec.out_parts)
    result["truncated"] = rec.truncated
    result["beds"] = farm.beds
    result["shop"] = {"served": shop.served, "tags": shop.tags}
    result["post"] = {"delivered": post.delivered}
    uv = user_vars(g, hidden)
    result["vars"] = {n: snap(v) for n, v in uv.items()}
    result["values"] = {n: plain(v) for n, v in uv.items()}
    result["files"] = snapshot(workdir) if workdir else {}
    return result


def run(payload):
    """Основной запуск (с записью шагов) + скрытые варианты данных.

    payload: code, lang, kits, beds, queue, orders, inject, field_var, files, workdir, limits,
             calls: [{"fn": имя, "args": [...]}], variants: [{тот же набор данных}, ...]
    """
    code = payload.get("code", "")
    workdir = payload.get("workdir")
    temp_dirs = []
    if payload.get("files") is not None:
        if not workdir:
            workdir = tempfile.mkdtemp(prefix="robofarm_")
            temp_dirs.append(workdir)
        reset_dir(workdir, payload["files"])
    try:
        result = _run_once(code, payload, workdir, True, payload.get("calls"))
        hidden = []
        for variant in payload.get("variants") or []:
            spec = {**payload, **variant}
            vdir = None
            if spec.get("files") is not None:
                vdir = tempfile.mkdtemp(prefix="robofarm_v_")
                temp_dirs.append(vdir)
                reset_dir(vdir, spec["files"])
            r = _run_once(code, spec, vdir, False, spec.get("calls"))
            r["acts"] = [e for e in r.pop("events", []) if e["k"] != "out"]
            hidden.append(r)
        result["variants"] = hidden
        return result
    finally:
        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)


def main():
    payload = json.loads(sys.stdin.read())
    result = run(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
