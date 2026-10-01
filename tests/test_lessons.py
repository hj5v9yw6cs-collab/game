"""Каждый шаг урока: правильное решение проходит проверку, заготовка и типичные ошибки — нет."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from robofarm.lessons.base import Result  # noqa: E402
from robofarm.lessons.chapter1 import LESSONS  # noqa: E402
from robofarm.sandbox.engine import run  # noqa: E402
from tests.solutions import SOLUTIONS, WRONG  # noqa: E402


def execute(code, beds):
    return Result(run({"code": code, "beds": beds, "lang": "ru"}), code)


def checkable():
    for lesson in LESSONS:
        for i, step in enumerate(lesson.steps):
            if step.check:
                yield lesson, i, step


@pytest.mark.parametrize("lesson,i,step", list(checkable()), ids=lambda x: getattr(x, "id", str(x)))
def test_step_solution_passes(lesson, i, step):
    key = f"{lesson.id}:{i}"
    assert key in SOLUTIONS, f"нет эталона для {key}"
    r = execute(SOLUTIONS[key], step.beds or lesson.beds)
    assert r.error is None, r.error
    assert step.check(r) is None, step.check(r)


@pytest.mark.parametrize("lesson,i,step", list(checkable()), ids=lambda x: getattr(x, "id", str(x)))
def test_step_template_does_not_pass(lesson, i, step):
    r = execute(step.code, step.beds or lesson.beds)
    assert r.error is not None or step.check(r) is not None


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda l: l.id)
def test_quest_solution_passes_and_starter_fails(lesson):
    q = lesson.quest
    r = execute(q.solution, lesson.beds)
    assert r.error is None, r.error
    assert q.check(r) is None, q.check(r)
    starter = execute(q.starter, lesson.beds)
    assert q.check(starter) is not None


@pytest.mark.parametrize("key,codes", list(WRONG.items()))
def test_typical_mistakes_are_caught(key, codes):
    lesson_id, idx = key.split(":")
    lesson = next(l for l in LESSONS if l.id == lesson_id)
    if idx == "quest":
        check, beds = lesson.quest.check, lesson.beds
    else:
        step = lesson.steps[int(idx)]
        check, beds = step.check, step.beds or lesson.beds
    for code in codes:
        r = execute(code, beds)
        assert r.error is not None or check(r) is not None, f"{key}: ошибочный код прошёл проверку:\n{code}"


def test_run_steps_execute_without_errors():
    for lesson in LESSONS:
        for step in lesson.steps:
            if step.kind in ("run", "look") and step.code and "____" not in step.code:
                r = execute(step.code, step.beds or lesson.beds)
                if step.kind == "run":
                    assert r.error is None, (lesson.id, step.code, r.error)


def test_sandbox_subprocess_roundtrip():
    payload = {"code": 'полить("тыква")\nкг = собрать("тыква")\nprint("Собрали:", кг)',
               "beds": LESSONS[1].beds, "lang": "ru"}
    out = subprocess.run([sys.executable, "-m", "robofarm.sandbox"], input=json.dumps(payload, ensure_ascii=False),
                         capture_output=True, text=True, cwd=ROOT, timeout=20)
    res = json.loads(out.stdout)
    assert res["stdout"] == "Собрали: 9\n"
    assert [e["cmd"] for e in res["events"] if e["k"] == "act"] == ["water", "harvest"]
    assert res["vars"]["кг"] == {"t": "num", "v": "9"}


def test_infinite_loop_is_stopped():
    r = run({"code": "while True:\n    pass", "beds": [], "limits": {"time": 0.5}})
    assert r["error"]["type"] == "TimeoutError"


@pytest.mark.parametrize("code,needle", [
    ('полить(тыква)', "в кавычки"),
    ('полить("тыквa")', "английская буква"),
    ('зкште("hi")', "раскладке"),
    ('print(«Привет»)', "кавычки"),
    ('for i in range(3)\n    print(i)', "двоеточия"),
    ('print("Урожай: " + 5)', "запятую"),
])
def test_friendly_error_messages(code, needle):
    r = run({"code": code, "beds": LESSONS[0].beds})
    err = r["error"]
    assert err is not None
    assert needle in (err["title"] + " " + err["hint"]).lower()
