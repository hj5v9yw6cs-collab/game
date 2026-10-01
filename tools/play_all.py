"""Автопрогон игры на правильных ответах со снимками экрана.

    python3 tools/play_all.py <папка для снимков> [первая глава] [последняя глава]

Проходит каждый шаг каждого урока так же, как игрок: вставляет эталонный ответ, жмёт «Проверить»,
ждёт конца анимации. Переходы между главами, диалоги и окна тоже проходит сам.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROBOFARM_HOME", tempfile.mkdtemp())

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from robofarm.game import GameWindow  # noqa: E402
from robofarm.lessons import CHAPTERS, LESSONS, chapter_of, first_lesson_index  # noqa: E402
from tests.solutions import SOLUTIONS  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
first_ch = int(sys.argv[2]) if len(sys.argv) > 2 else 1
last_ch = int(sys.argv[3]) if len(sys.argv) > 3 else len(CHAPTERS)

app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
w = GameWindow()
w.resize(1440, 900)
w.show()


def wait(ms):
    QTest.qWait(ms)


def shot(name):
    wait(150)
    w.grab().save(str(out / f"{name}.png"))
    print("shot", name, flush=True)


def until(cond, timeout=40):
    t = time.time()
    while not cond() and time.time() - t < timeout:
        wait(40)
    return cond()


def skip_dialogs():
    while w._dialog_queue or w.dialog.isVisible():
        w.dialog.shown = len(w.dialog.text)
        w._dialog_next()
        wait(40)


def ready(li):
    return (w.save["lesson"] == li and w.hud.isVisible() and not w.modal and not w.dialog.isVisible()
            and not w._dialog_queue)


def go_to_lesson(li, timeout=20):
    """Проходит диалоги и окна между уроками и главами, пока не откроется урок li."""
    t = time.time()
    while not ready(li) and time.time() - t < timeout:
        if w.dialog.isVisible() or w._dialog_queue:
            skip_dialogs()
        elif w.modal is not None:
            buttons = getattr(w.modal.window, "buttons", [])
            if buttons:
                buttons[-1].click()
            else:
                w._close_modal()
        wait(60)
    return ready(li)


wait(200)
w.new_game()
wait(100)
w.modal.window.name.setText("Аня")
w.modal.window._pick(True)
w.modal.window._go()
wait(100)
start = first_lesson_index(CHAPTERS[first_ch - 1])
if start == 0:
    w._intro()
    wait(1200)
    skip_dialogs()
else:
    w._close_modal()
    w.save["max_lesson"] = start
    w.save["done"] = [l.id for l in LESSONS[:start]]
    w._start_chapter(CHAPTERS[first_ch - 1])
    wait(2200)
    shot(f"ch{first_ch}_00_start")
    skip_dialogs()
w.script_win.speed.setValue(4)

for li in range(start, len(LESSONS)):
    lesson = LESSONS[li]
    ch = chapter_of(lesson)
    if ch.number > last_ch:
        break
    assert go_to_lesson(li), f"не открылся урок {lesson.id}"
    tag = f"ch{ch.number}_{li:02d}_{lesson.id}"
    for si, st in enumerate(lesson.steps + ["quest"]):
        assert until(lambda: w.save["step"] == si and w.save["lesson"] == li, 5), f"шаг {lesson.id}:{si}"
        key = f"{lesson.id}:{si}"
        if st == "quest":
            w.script_win.editor.setPlainText(lesson.quest.solution)
            w.on_primary()
            if not until(lambda: w.modal is not None, 60):
                shot(f"FAIL_{tag}_quest")
                raise SystemExit(f"задание {lesson.id} не принято: {w.lesson_win.feedback.text()}")
            shot(f"{tag}_quest_done")
            w._finish_lesson()
            wait(150)
            continue
        if st.kind == "look":
            if si == 0:
                shot(f"{tag}_0_look")
            w.on_primary()
            continue
        if st.kind == "run":
            first_run = all(s.kind != "run" for s in lesson.steps[:si])
            if first_run:
                w.script_win.speed.setValue(2)
            w.on_primary()
            if first_run:
                wait(1800)
                shot(f"{tag}_{si}_run")
                w.script_win.speed.setValue(4)
            if not until(lambda: w.step_passed):
                shot(f"FAIL_{tag}_{si}")
                raise SystemExit(f"шаг {key} не выполнился: {w.lesson_win.feedback.text()}")
            w.on_primary()
            continue
        w.script_win.editor.setPlainText(SOLUTIONS[key])
        w.on_primary()
        if not until(lambda: w.step_passed):
            shot(f"FAIL_{tag}_{si}")
            raise SystemExit(f"шаг {key} не пройден: {w.lesson_win.feedback.text()}")
        w.on_primary()
    if lesson is ch.lessons[-1]:
        until(lambda: w._dialog_queue or w.dialog.isVisible(), 5)
        skip_dialogs()
        until(lambda: w.modal is not None, 5)
        shot(f"ch{ch.number}_99_done")
        w.world.xray = True
        shot(f"ch{ch.number}_98_xray")
        w.world.xray = False

print("coins", w.save["coins"], "done", len(w.save["done"]), "of", len(LESSONS), "flags", w.save["flags"])

skip_dialogs()
w._close_modal()
w.save["coins"] += 100
w.show_lessons()
shot("zz_lessons")
w._close_modal()
w.show_catalog()
shot("zz_catalog")
w._buy("lanterns")
wait(2800)
shot("zz_bought")
