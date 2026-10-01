"""Автопрогон игры без экрана со снимками: python3 tools/play_test.py <папка>"""
import os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROBOFARM_HOME", tempfile.mkdtemp())
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from robofarm.game import GameWindow

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
w = GameWindow(); w.resize(1440, 900); w.show()
def wait(ms): QTest.qWait(ms)
def shot(name): wait(100); w.grab().save(str(out / f"{name}.png")); print("shot", name)
def until(cond, timeout=20):
    t = time.time()
    while not cond() and time.time() - t < timeout: wait(50)
wait(300); shot("01_title")
w.new_game(); wait(200); w.modal.window.name.setText("Федя"); w.modal.window._go(); wait(300); shot("02_letter")
w._intro(); wait(1500); shot("03_klusha_wakes")
while w._dialog_queue or w.dialog.isVisible():
    w.dialog.shown = len(w.dialog.text); w._dialog_next(); wait(150)
wait(500); shot("04_lesson1_step1")
w.on_primary(); wait(300)  # -> run step
w.script_win.speed.setValue(4)
w.on_primary(); until(lambda: w.step_passed); wait(400); shot("05_run_done")
w.on_primary(); wait(200); w.on_primary(); wait(200)  # look -> fill
w.script_win.editor.setPlainText('print("Привет, Клуша!")'); w.on_primary(); until(lambda: w.step_passed); wait(300); shot("06_fill_ok")
w.on_primary(); wait(200)  # fix
w.on_primary(); until(lambda: not w.runner.busy() and not w.replay.running, 10); wait(500); shot("07_fix_error")
