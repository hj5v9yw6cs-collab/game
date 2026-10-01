"""Проигрывание записанного выполнения кода: строка за строкой, с анимацией робота."""

import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QTextCursor

from robofarm.sound import play

# (пауза после строки в мс, скорость робота) для положений ползунка 🐢 … 🐇
SPEEDS = [(1100, 0.8), (600, 1.3), (300, 2.2), (120, 3.8), (25, 9.0)]


class Replay(QObject):
    finished = Signal(object)

    def __init__(self, world, editor, memory, output, status, parent=None):
        super().__init__(parent)
        self.world, self.editor, self.memory, self.output, self.status = world, editor, memory, output, status
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.speed = 1
        self.running = False
        self.result = None
        self.robot_id = "bublik"

    # ------------------------------------------------------------ управление
    def set_speed(self, i):
        self.speed = max(0, min(len(SPEEDS) - 1, i))
        robot = self.world.robots.get(self.robot_id)
        if robot:
            robot.speed_mul = SPEEDS[self.speed][1]

    def start(self, result, stepping=False, robot_id="bublik"):
        self.result = result
        self.robot_id = robot_id
        self.stepping = stepping
        self.paused = False
        self.units = []
        pre = []
        for ev in result.get("events", []):
            if ev["k"] == "line":
                self.units.append({"ln": ev["ln"], "d": ev.get("d", {}), "rm": ev.get("rm", []), "acts": []})
            elif self.units:
                self.units[-1]["acts"].append(ev)
            else:
                pre.append(ev)
        if pre and self.units:
            self.units[0]["acts"][:0] = pre
        self.state = {}
        self.i = 0
        self.phase = "start"
        self.pending = []
        self.wait_until = 0
        self.running = True
        self.output.clear()
        self.memory.clear()
        self.set_speed(self.speed)
        if result.get("truncated"):
            self.status("Слишком много шагов — показываю сразу результат", "#fde07a")
            self.units = []
        self.timer.start(30)

    def advance(self):
        """Кнопка «Шаг»: выполнить следующую строку."""
        if self.running and self.paused:
            self.paused = False

    def stop(self):
        if not self.running:
            return
        self.timer.stop()
        self.running = False
        robot = self.world.robots.get(self.robot_id)
        if robot:
            robot.clear()
        self.editor.set_exec_line(None)
        self.status("Остановлено", "#f0903a")

    # ------------------------------------------------------------ шаги
    def _apply(self, unit):
        for name in unit["rm"]:
            self.state.pop(name, None)
        self.state.update(unit["d"])
        return set(unit["d"])

    def _tick(self):
        if not self.running or self.paused:
            return
        robot = self.world.robots.get(self.robot_id)
        now = time.monotonic()
        if self.phase == "start":
            if not self.units:
                self._finish()
                return
            self._apply(self.units[0])
            self.memory.set_vars(self.state)
            self.phase = "line"
        if self.phase == "line":
            unit = self.units[self.i]
            self.editor.set_exec_line(unit["ln"])
            if self.speed <= 2:
                play("tick", 0.5)
            self.status(f"Выполняю строку {unit['ln']}", "#fde07a")
            self.pending = list(unit["acts"])
            self.phase = "acts"
        if self.phase == "acts":
            if robot and robot.busy():
                return
            if now < self.wait_until:
                return
            if self.pending:
                self._perform(self.pending.pop(0), robot)
                return
            # строка выполнена: показываем, что стало в памяти
            if self.i + 1 < len(self.units):
                changed = self._apply(self.units[self.i + 1])
                self.memory.set_vars(self.state, changed, f"после строки {self.units[self.i]['ln']}")
            else:
                final = self.result.get("vars", {})
                changed = {n for n, v in final.items() if self.state.get(n) != v}
                self.state = dict(final)
                self.memory.set_vars(self.state, changed, f"после строки {self.units[self.i]['ln']}")
            self.wait_until = now + SPEEDS[self.speed][0] / 1000
            self.phase = "post"
            return
        if self.phase == "post":
            if now < self.wait_until:
                return
            self.i += 1
            if self.i >= len(self.units):
                self._finish()
                return
            self.phase = "line"
            if self.stepping:
                self.paused = True
                self.status("Нажми «Шаг», чтобы выполнить следующую строку", "#a6e2d6")

    def _perform(self, ev, robot):
        delay = SPEEDS[self.speed][0] / 1000
        if ev["k"] == "out":
            text = ev["text"]
            self.output.moveCursor(QTextCursor.MoveOperation.End)
            self.output.insertPlainText(text)
            self.output.ensureCursorVisible()
            if robot and text.strip():
                robot.say(text.strip(), seconds=max(1.6, delay * 3))
                play(f"voice_{self.robot_id}", 0.7)
            self.wait_until = time.monotonic() + max(0.25, delay * 0.8)
            return
        if ev["k"] != "act" or not robot:
            return
        name = ev["bed"]
        if name not in self.world.map.beds:
            return
        sx, sy = self.world.bed_stand_point(name)
        robot.walk_to(sx, sy)
        bx, by = self.world.bed_center(name)
        if ev["cmd"] == "water":
            def wet(name=name):
                if name in self.world.beds:
                    self.world.beds[name]["humidity"] = 100
                self.world.particles.burst("fx_splash", bx, by + 4, 0.4)
            play("water", 0.8)
            robot.play("water", 1.2, wet, facing="left")
        elif ev["cmd"] == "harvest" and ev.get("ok"):
            kg = ev.get("res", 0)

            def pick(name=name, kg=kg):
                if name in self.world.beds:
                    self.world.beds[name]["stage"] = "empty"
                self.world.particles.burst("fx_harvest_sparkle", bx, by + 6, 0.36)
                self.world.particles.float_text(f"+{kg} кг", bx - 10, by - 10)
                play("harvest")
            robot.play("harvest", 1.0, pick, facing="left")
        else:
            robot.play("confused", 1.0, facing="left")
            robot.show_emote("emote_question", 1.4)
            play("warn", 0.7)
            robot.say("Ещё не созрела!" if ev.get("msg") != "уже пустая" else "Тут уже пусто!", 1.6)

    def _finish(self):
        self.timer.stop()
        self.running = False
        res = self.result
        if res.get("beds"):
            for b in res["beds"]:
                if b["name"] in self.world.beds:
                    self.world.beds[b["name"]].update({k: b[k] for k in ("humidity", "stage")})
        robot = self.world.robots.get(self.robot_id)
        err = res.get("error")
        if err:
            self.editor.set_exec_line(None)
            self.editor.set_error_line(err.get("line"))
            self.status(err.get("title", "Ошибка"), "#f388a8")
            play("error")
            if robot:
                robot.play("confused", 1.2)
                robot.show_emote("emote_cross", 2.0)
                self.world.particles.burst("fx_spark_error", robot.x, robot.y - 14, 0.3)
        else:
            self.editor.set_exec_line(None)
            self.memory.set_vars(res.get("vars", {}), (), "программа закончилась")
            self.status(f"Готово ✓  строк выполнено: {res.get('lines', 0)}, время: {res.get('ms', 0)} мс", "#8ad06a")
        self.finished.emit(res)
