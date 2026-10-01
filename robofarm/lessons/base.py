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


class Result:
    """Результат запуска кода в песочнице — с удобными методами для проверок."""

    def __init__(self, raw, code):
        self.raw = raw
        self.code = code
        self.error = raw.get("error")
        self.events = raw.get("events", [])
        self.stdout = raw.get("stdout", "")
        self.warnings = raw.get("warnings", [])
        self.vars_snap = raw.get("vars", {})
        self.beds = raw.get("beds") or []

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
