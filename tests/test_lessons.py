"""Каждый шаг каждого урока: правильное решение проходит проверку, заготовка и типичные ошибки — нет.

Код запускается ровно так же, как в игре: через robofarm.lessons.runtime и настоящую песочницу,
вместе со скрытыми вариантами данных.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from robofarm.lessons import CHAPTERS, LESSONS  # noqa: E402
from robofarm.lessons import runtime  # noqa: E402
from robofarm.sandbox.engine import run  # noqa: E402
from tests.solutions import SOLUTIONS, WRONG  # noqa: E402


def execute(lesson, st, code):
    payload, data0, hidden = runtime.build(lesson, st, code)
    return runtime.result(run(payload), code, data0, hidden)


def lesson_by_id(lid):
    return next(l for l in LESSONS if l.id == lid)


def checkable():
    for lesson in LESSONS:
        for i, step in enumerate(lesson.steps):
            if step.check:
                yield pytest.param(lesson, i, step, id=f"{lesson.id}:{i}")


def quests():
    return [pytest.param(l, id=l.id) for l in LESSONS]


def test_lesson_ids_are_unique():
    ids = [l.id for l in LESSONS]
    assert len(ids) == len(set(ids))


def test_chapters_are_numbered_in_order():
    assert [ch.number for ch in CHAPTERS] == list(range(1, len(CHAPTERS) + 1))


@pytest.mark.parametrize("lesson,i,step", list(checkable()))
def test_step_solution_passes(lesson, i, step):
    key = f"{lesson.id}:{i}"
    assert key in SOLUTIONS, f"нет эталона для {key}"
    r = execute(lesson, step, SOLUTIONS[key])
    assert r.error is None, r.error
    assert step.check(r) is None, step.check(r)


@pytest.mark.parametrize("lesson,i,step", list(checkable()))
def test_step_template_does_not_pass(lesson, i, step):
    r = execute(lesson, step, step.code)
    assert r.error is not None or step.check(r) is not None


@pytest.mark.parametrize("lesson", quests())
def test_quest_solution_passes_and_starter_fails(lesson):
    q = lesson.quest
    r = execute(lesson, q, q.solution)
    assert r.error is None, r.error
    assert q.check(r) is None, q.check(r)
    starter = execute(lesson, q, q.starter)
    assert starter.error is not None or q.check(starter) is not None


@pytest.mark.parametrize("key,codes", list(WRONG.items()))
def test_typical_mistakes_are_caught(key, codes):
    lesson_id, idx = key.split(":")
    lesson = lesson_by_id(lesson_id)
    st = lesson.quest if idx == "quest" else lesson.steps[int(idx)]
    for code in codes:
        r = execute(lesson, st, code)
        assert r.error is not None or st.check(r) is not None, f"{key}: ошибочный код прошёл проверку:\n{code}"


@pytest.mark.parametrize("lesson", quests())
def test_run_steps_execute(lesson):
    for step in lesson.steps:
        if step.kind == "run":
            r = execute(lesson, step, step.code)
            if step.expect_error:
                assert r.error is not None, (lesson.id, step.code)
            else:
                assert r.error is None, (lesson.id, step.code, r.error)


@pytest.mark.parametrize("lesson", quests())
def test_sample_code_is_valid_python(lesson):
    for step in lesson.steps:
        if step.code and step.kind in ("look", "run"):
            ast.parse(step.code)
    ast.parse(lesson.quest.solution)


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
