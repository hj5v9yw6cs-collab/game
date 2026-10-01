"""Снимки экрана для README: лавка, амбар, почта, ярмарка.  python3 tools/readme_shots.py <папка>"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROBOFARM_HOME", tempfile.mkdtemp())

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from robofarm.game import GameWindow  # noqa: E402
from robofarm.lessons import LESSONS  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
w = GameWindow()
w.resize(1440, 900)
w.show()
QTest.qWait(200)
w._close_title()
w.save.update(player={"name": "Аня", "female": True}, max_lesson=len(LESSONS) - 1, coins=640, day=12,
              done=[l.id for l in LESSONS[:20]],
              flags={"shed_repaired": True, "house_repaired": True, "stall_repaired": True, "barn_repaired": True,
                     "post_repaired": True, "decor:lanterns": True, "decor:jacks": True, "decor:flowers": True})
w._setup_world()
w._set_play_ui(True)
w._layout()


def scene(name, lesson_id, step, code, speed, times):
    w._close_modal()
    li = next(i for i, l in enumerate(LESSONS) if l.id == lesson_id)
    w.goto_step(li, step)
    QTest.qWait(900)
    w.script_win.speed.setValue(speed)
    w.script_win.editor.setPlainText(code)
    w.run_code(w._run_mode())
    elapsed = 0
    for i, t in enumerate(times, 1):
        QTest.qWait(t - elapsed)
        elapsed = t
        w.grab().save(str(out / f"{name}_{i}.png"))
        print("shot", name, i, flush=True)
    w.on_stop()
    w._close_modal()


scene("shop", "dicts", 7,
      'for item, price in prices.items():\n    tag(f"{item}: {price} руб/кг")\n\nfor customer in queue:\n'
      '    total = customer["kg"] * prices[customer["item"]]\n    sell(customer, total)\n'
      '    print(f"{customer[\'name\']}: {total} руб.")', 3, [2500, 3500, 4500, 5500])
scene("barn", "files", 4, LESSONS[[l.id for l in LESSONS].index("files")].steps[4].code, 2, [1500, 2500, 3500])
scene("post", "json", 4, LESSONS[[l.id for l in LESSONS].index("json")].steps[4].code, 2, [3000, 5000, 7000, 9000])
fair = LESSONS[[l.id for l in LESSONS].index("weather")]
scene("fair", "weather", 4, fair.quest.solution, 2, [2000, 4000, 6000])
