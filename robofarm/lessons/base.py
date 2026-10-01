"""Каркас уроков: шаги, проверки и результат запуска кода."""

import ast
from dataclasses import dataclass, field

STEP_LABELS = {
    "look": ("icon_step_look", "Смотри"),
    "run": ("icon_step_run", "Запусти"),
    "fill": ("icon_step_fill", "Допиши"),
    "fix": ("icon_step_fix", "Исправь"),
    "write": ("icon_step_write", "Напиши сам"),
    "quest": ("icon_chapter", "Задание"),
}


@dataclass
class Step:
    kind: str
    text: str
    code: str = ""
    portrait: str = "explain"
    check: object = None        # функция(Result) -> None (успех) или строка с подсказкой
    success: str = "Верно! Ко-ко!"
    after: str = ""             # реплика Клуши после запуска (для шагов «Запусти»)
    hints: list = field(default_factory=list)
    beds: list = None           # состояние огорода для этого шага (None — как в уроке)
    show_memory: bool = False
    data: object = None         # функция(вариант) -> данные шага (файлы, переменные…); None — как в уроке
    calls: list = None          # вызовы функций игрока для проверки: [{"fn": имя, "args": [...]}]
    variants: int = 0           # сколько скрытых вариантов данных прогнать при проверке
    expect_error: bool = False  # шаг «Запусти», где программа должна упасть (показываем ошибку как урок)


@dataclass
class Quest:
    giver: str
    note: str
    goals: list
    starter: str
    check: object
    solution: str
    breakdown: list             # [(строка кода, объяснение)]
    alternative: str
    life_title: str
    life: list                  # пункты «где это в жизни»
    try_at_home: list           # шаги «попробуй у себя»
    reward: int = 10
    hints: list = field(default_factory=list)
    success: str = ""
    data: object = None
    calls: list = None
    variants: int = 0


@dataclass
class Lesson:
    id: str
    title: str
    topic: str
    beds: list
    steps: list
    quest: Quest
    notes: str = ""             # шпаргалка для блокнота Клуши
    unlock: list = field(default_factory=list)  # флаги мира после урока
    chapter: int = 1
    robot: str = "bublik"
    kits: list = field(default_factory=lambda: ["garden"])
    lang: str = "ru"
    field_var: str = None       # имя переменной со списком грядок («поле» / «field»)
    folder: str = None          # папка урока на Mac (Документы/Робоферма/<folder>) с файлами данных
    data: object = None         # функция(вариант) -> {"beds", "queue", "orders", "inject", "files", "expect"}
    zone: str = "yard"          # куда смотрит камера


@dataclass
class Chapter:
    number: int
    title: str
    zone: str
    robot: str
    lessons: list
    intro: list = field(default_factory=list)   # реплики (робот, настроение, текст) перед первым уроком
    outro: list = field(default_factory=list)
    automation: tuple = ("", 0)                  # что делает готовый скрипт каждый день и сколько монет даёт


class Result:
    """Результат запуска кода в песочнице — с удобными методами для проверок."""

    def __init__(self, raw, code, data=None, variant_data=()):
        self.raw = raw
        self.code = code
        self.data = (data or {}).get("expect", {}) if isinstance(data, dict) else {}
        self.input = data or {}
        self.error = raw.get("error")
        self.events = raw.get("events", raw.get("acts", []))
        self.stdout = raw.get("stdout", "")
        self.warnings = raw.get("warnings", [])
        self.vars_snap = raw.get("vars", {})
        self.values = raw.get("values", {})
        self.beds = raw.get("beds") or []
        self.files = raw.get("files", {})
        self.calls_result = raw.get("calls", [])
        self.shop = raw.get("shop", {"served": [], "tags": []})
        self.post = raw.get("post", {"delivered": []})
        self.variants = [Result(v, code, d) for v, d in zip(raw.get("variants", []), variant_data)]

    def each(self, check):
        """Проверка на основных данных и на скрытых «данных следующего дня»."""
        msg = check(self)
        if msg:
            return msg
        for i, v in enumerate(self.variants, 1):
            if v.error:
                return ("На других данных (как будто наступил новый день) программа упала: "
                        f"{v.error['title']}. {v.error['hint']}")
            msg = check(v)
            if msg:
                return ("На сегодняшних данных всё верно, а на завтрашних — нет. Похоже, какое-то значение "
                        f"вписано в код руками вместо того, чтобы взять его из данных. Подробно: {msg}")
        return None

    def file(self, path):
        f = self.files.get(path)
        return f if isinstance(f, str) else None

    def call(self, fn, *args):
        for c in self.calls_result:
            if c["fn"] == fn and c.get("args") == list(args):
                return c
        return None

    @property
    def lines(self):
        return [line.rstrip() for line in self.stdout.split("\n") if line.strip()]

    def acts(self, cmd=None, ok=None):
        return [e for e in self.events if e["k"] == "act" and (cmd is None or e["cmd"] == cmd)
                and (ok is None or e.get("ok") == ok)]

    def watered(self):
        return [e["bed"] for e in self.acts("water")]

    def harvested(self, ok=True):
        return [e["bed"] for e in self.acts("harvest", ok)]

    def has_var(self, name):
        return name in self.vars_snap

    def value(self, name, default=None):
        return self.values.get(name, default)

    def var(self, name):
        s = self.vars_snap.get(name)
        if not s:
            return None
        if s["t"] == "num":
            v = s["v"]
            return float(v) if "." in v or "e" in v else int(v)
        if s["t"] in ("str", "bool"):
            return s["v"]
        return s

    def tree(self):
        try:
            return ast.parse(self.code)
        except SyntaxError:
            return None

    def uses(self, name):
        """Есть ли в коде имя (функция, модуль, атрибут)."""
        t = self.tree()
        if not t:
            return False
        for n in ast.walk(t):
            if isinstance(n, ast.Name) and n.id == name:
                return True
            if isinstance(n, ast.Attribute) and n.attr == name:
                return True
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in n.names] + ([n.module] if isinstance(n, ast.ImportFrom) and n.module else [])
                if any(x.split(".")[0] == name for x in names):
                    return True
        return False

    def node_count(self, kind):
        t = self.tree()
        return sum(isinstance(n, kind) for n in ast.walk(t)) if t else 0

    def calls(self, name):
        t = self.tree()
        if not t:
            return 0
        return sum(1 for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == name)

    def printed(self, needle):
        return any(needle.lower() in line.lower() for line in self.lines)

    def printed_number(self, number):
        import re
        for line in self.lines:
            for token in re.findall(r"-?\d+(?:\.\d+)?", line):
                if float(token) == number:
                    return True
        return False


def gender(text, female):
    """«{готов|готова}» → нужная форма."""
    import re
    return re.sub(r"\{([^{}|]*)\|([^{}|]*)\}", lambda m: m.group(2 if female else 1), text)
