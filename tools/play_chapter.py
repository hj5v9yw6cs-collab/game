"""Автопрогон всей главы 1 на правильных ответах со снимками: python3 tools/play_chapter.py <папка>"""
import os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROBOFARM_HOME", tempfile.mkdtemp())
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from robofarm.game import GameWindow
from robofarm.lessons.chapter1 import LESSONS
from tests.solutions import SOLUTIONS

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
w = GameWindow(); w.resize(1440, 900); w.show()
def wait(ms): QTest.qWait(ms)
def shot(name): wait(120); w.grab().save(str(out / f"{name}.png")); print("shot", name, flush=True)
def until(cond, timeout=30):
    t = time.time()
    while not cond() and time.time() - t < timeout: wait(40)
    return cond()
wait(200); w.new_game(); wait(100); w.modal.window.name.setText("Аня"); w.modal.window._pick(True); w.modal.window._go(); wait(100)
w._intro(); wait(1200)
while w._dialog_queue or w.dialog.isVisible():
    w.dialog.shown = len(w.dialog.text); w._dialog_next(); wait(60)
w.script_win.speed.setValue(4)
for li, lesson in enumerate(LESSONS):
    for si, st in enumerate(lesson.steps + ["quest"]):
        until(lambda: w.save["step"] == si and w.save["lesson"] == li, 5)
        key = f"{lesson.id}:{si}"
        if st == "quest":
            w.script_win.editor.setPlainText(lesson.quest.solution)
            w.on_primary()
            assert until(lambda: w.modal is not None, 30), f"квест {lesson.id} не принят"
            if li == 0: shot("10_quest_done")
            if li == 1:
                w.show_breakdown(); shot("11_breakdown"); w.show_life(); shot("12_life")
            w._finish_lesson(); wait(150)
            continue
        if st.kind == "look":
            if (li, si) == (1, 0): shot("08_lesson2_look")
            w.on_primary(); continue
        if st.kind == "run":
            if (li, si) == (1, 1):
                w.script_win.speed.setValue(1); w.on_primary(); wait(2600); shot("09_watering"); w.script_win.speed.setValue(4)
            else:
                w.on_primary()
            assert until(lambda: w.step_passed), f"run {key}"
            if (li, si) == (2, 1): shot("13_memory")
            w.on_primary(); continue
        w.script_win.editor.setPlainText(SOLUTIONS[key]); w.on_primary()
        ok = until(lambda: w.step_passed)
        if not ok:
            shot(f"FAIL_{key.replace(':', '_')}"); raise SystemExit(f"шаг {key} не пройден")
        if (li, si) == (3, 3): shot("14_math_fill")
        w.on_primary()
until(lambda: w._dialog_queue or w.dialog.isVisible(), 5)
shot("15_outro")
while w._dialog_queue or w.dialog.isVisible():
    w.dialog.shown = len(w.dialog.text); w._dialog_next(); wait(60)
wait(300); shot("16_chapter_done")
w._close_modal(); w.world.xray = True; shot("17_xray"); w.world.xray = False
w.world.hover = w.world._hit(*w.world.bed_center("капуста")); w.world.hover_pos = w.world.world_to_screen(*w.world.bed_center("капуста")).toPoint(); shot("18_hover")
print("coins", w.save["coins"], "done", w.save["done"], "flags", w.save["flags"])
