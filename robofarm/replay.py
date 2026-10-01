"""Проигрывание записанного выполнения кода: строка за строкой, с анимацией робота."""

import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QTextCursor

from robofarm.sound import play

# (пауза после строки в мс, скорость робота) для положений ползунка 🐢 … 🐇
SPEEDS = [(1100, 0.8), (600, 1.3), (300, 2.2), (120, 3.8), (25, 9.0)]


def _num(v):
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


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

    def start(self, result, stepping=False, robot_id="bublik", ctx=None):
        """ctx — где в мире всё находится: home (место робота), files (шкаф или стол с файлами)."""
        self.result = result
        self.robot_id = robot_id
        self.ctx = ctx or {}
        self._at_files = False
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
        if not robot:
            return
        if ev["k"] == "file":
            self._file_event(ev, robot)
            return
        if ev["k"] != "act":
            return
        cmd = ev["cmd"]
        if cmd == "sell":
            self._sell(ev, robot)
            return
        if cmd == "tag":
            self._tag(ev, robot)
            return
        if cmd == "deliver":
            self._deliver(ev, robot)
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

    # ------------------------------------------------------------ лавка, почта, файлы
    def _sell(self, ev, robot):
        world = self.world
        person = world.people.get(ev["who"])

        def done(person=person, total=ev["total"]):
            if person and not person.hidden:
                world.particles.float_icon("icon_coin", person.x, person.y - 30)
                world.particles.float_text(f"+{_num(total)} руб.", person.x - 12, person.y - 34)
                person.show_emote("emote_heart", 1.2)
            world.serve_customer(ev["who"])
            play("sell", 0.8)
        robot.play("serve", 0.9, done, facing="right")

    def _tag(self, ev, robot):
        world = self.world

        def done(text=ev["text"]):
            world.price_tags.append(text)
            sx, sy = world.map.spots["stall"]
            world.particles.burst("fx_pop", sx - 30, sy - 24, 0.4)
            play("tag", 0.9)
        robot.play("tag", 0.7, done, facing="left")

    def _deliver(self, ev, robot):
        world = self.world
        houses = world.map.spots["houses"]
        hx, hy = houses[(int(ev.get("house", 1)) - 1) % len(houses)]
        play("trot", 0.6)
        robot.walk_to(hx, hy)

        def done(ev=ev, hx=hx, hy=hy):
            world.particles.float_icon("parcel", hx, hy - 20)
            label = f"№{ev['id']}" + (f" — {ev['who']}" if ev.get("who") else "")
            world.particles.float_text(label, hx - 20, hy - 30)
            play("bell", 0.7)
        robot.play("deliver", 0.8, done, facing="left")

    FILE_ICONS = {".csv": "file_csv", ".json": "file_json", ".txt": "file_txt", ".py": "file_py",
                  ".jpg": "file_image", ".jpeg": "file_image", ".png": "file_image", ".heic": "file_image"}

    def _file_event(self, ev, robot):
        world = self.world
        spot = self.ctx.get("files")
        if spot and not self._at_files:
            robot.walk_to(*spot)
            self._at_files = True
        path = ev.get("path") or ""
        short = path.rstrip("/").split("/")[-1] or path
        op = ev["op"]
        if op == "read":
            label, anims, sound = f"читает {short}", ("read", "scan"), "paper"
        elif op == "write":
            label, anims, sound = f"пишет {short}", ("write", "stamp", "stack", "scan"), "write"
        elif op == "move":
            to = (ev.get("to") or "").rstrip("/")
            folder = to.rsplit("/", 1)[0] + "/" if "/" in to else ""
            new = to.split("/")[-1]
            label = f"{short} → {folder}{new if new != short else ''}"
            anims, sound = ("sort", "carry", "stack"), "paper"
        elif op == "mkdir":
            label, anims, sound = f"новая папка {short}", ("stamp", "stack", "scan"), "tag"
        else:
            label, anims, sound = f"удалён {short}", ("stamp", "scan"), "paper"
        assets = world.assets
        anim = next((a for a in anims if assets.get(f"{robot.id}_{a}_left") or assets.get(f"{robot.id}_{a}")),
                    "happy")
        ext = "." + short.rsplit(".", 1)[-1].lower() if "." in short else ""
        icon = "folder_open" if op == "mkdir" else self.FILE_ICONS.get(ext, "file_txt")

        def done(icon=icon, label=label, sound=sound):
            world.particles.float_icon(icon, robot.x, robot.y - 22)
            world.particles.float_text(label, robot.x - 24, robot.y - 30)
            play(sound, 0.7)
        robot.play(anim, 0.45, done, facing="left")

    def _finish(self):
        self.timer.stop()
        self.running = False
        res = self.result
        if res.get("beds"):
            for b in res["beds"]:
                if b["name"] in self.world.beds:
                    self.world.beds[b["name"]].update({k: b[k] for k in ("humidity", "stage")})
        robot = self.world.robots.get(self.robot_id)
        home = self.ctx.get("home")
        if robot and home and (abs(robot.x - home[0]) > 20 or abs(robot.y - home[1]) > 20):
            robot.walk_to(*home)
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
