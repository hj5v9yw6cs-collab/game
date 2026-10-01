"""Главное окно и ход игры: вступление, уроки, проверки, награды, сохранения."""

import html
import json

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import QMainWindow

from robofarm import paths
from robofarm.assets import Assets
from robofarm.lessons.base import Result, gender
from robofarm.lessons.chapter1 import INTRO, LESSONS, OUTRO
from robofarm.replay import Replay
from robofarm.sandbox.client import SandboxRunner
from robofarm.sound import play, sounds
from robofarm.ui.fonts import load_fonts
from robofarm.ui.pixel import Modal, Toast
from robofarm.ui.windows import (DialogBox, Hud, InfoWindow, LessonWindow, MemoryWindow, NewGameWindow,
                                 ScriptWindow, TitleScreen, md)
from robofarm.world.view import WorldView

SAVE_VERSION = 1
SCRIPT_HEADER = ("# Скрипт Бублика из игры «Робоферма».\n"
                 "# Команды полить() и собрать() есть только на ферме,\n"
                 "# а print, переменные и арифметика работают в любом Python.\n\n")


def default_save():
    return {"version": SAVE_VERSION, "player": None, "lesson": 0, "step": 0, "coins": 0, "done": [],
            "codes": {}, "attempts": {}, "hints": {}, "flags": {}, "speed": 1, "sound": True}


class GameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_fonts()
        self.setWindowTitle("Робоферма")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.assets = Assets()
        self.world = WorldView(self.assets)
        self.setCentralWidget(self.world)
        a = self.assets
        self.hud = Hud(a, self.world)
        self.lesson_win = LessonWindow(a, self.world)
        self.script_win = ScriptWindow(a, "bublik", self.world)
        self.memory_win = MemoryWindow(a, "Бублика", self.world)
        self.dialog = DialogBox(a, self.world)
        self.modal = None
        self.runner = SandboxRunner(self)
        self.runner.finished.connect(self._on_result)
        self.replay = Replay(self.world, self.script_win.editor, self.memory_win.view, self.script_win.output,
                             self.script_win.set_status, self)
        self.replay.finished.connect(self._on_replay_done)
        self.save = self._load()
        self.pending = None  # что делать с результатом: ("run"|"check", stepping)
        self._dialog_queue = []
        self._dialog_done = None
        self.step_passed = False
        # сигналы
        self.lesson_win.primary.connect(self.on_primary)
        self.lesson_win.back.connect(self.on_back)
        self.lesson_win.hint.connect(self.on_hint)
        self.lesson_win.solution.connect(self.on_solution)
        self.script_win.run.connect(self.on_run_button)
        self.script_win.step.connect(self.on_step_button)
        self.script_win.stop.connect(self.on_stop)
        self.script_win.speed_changed.connect(self._speed)
        self.script_win.speed.setValue(self.save.get("speed", 1))
        self.dialog.next.connect(self._dialog_next)
        self.hud.xray.connect(self.toggle_xray)
        self.hud.notebook.connect(self.show_notebook)
        self.hud.folder.connect(self.open_folder)
        self.hud.sound.connect(self.toggle_sound)
        sounds().set_enabled(self.save.get("sound", True))
        self.hud.set_sound_icon(self.save.get("sound", True))
        self.world.robot_clicked.connect(self._robot_clicked)
        QShortcut(QKeySequence("R"), self, activated=self._xray_key)
        self._setup_world()
        self._layout()
        self._set_play_ui(False)
        QTimer.singleShot(0, self.show_title)

    # ------------------------------------------------------------ сохранение
    def _save_path(self):
        return paths.save_dir() / "save.json"

    def _load(self):
        try:
            data = json.loads(self._save_path().read_text(encoding="utf-8"))
            if data.get("version") == SAVE_VERSION:
                return {**default_save(), **data}
        except (OSError, ValueError):
            pass
        return default_save()

    def _store(self):
        try:
            self._save_path().write_text(json.dumps(self.save, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    @property
    def female(self):
        return bool(self.save.get("player") and self.save["player"].get("female"))

    def g(self, text):
        return gender(text, self.female)

    # ------------------------------------------------------------ раскладка окон
    def _layout(self):
        W, H = self.world.width(), self.world.height()
        self.hud.setGeometry(16, 12, W - 32, 46)
        lw = min(500, int(W * 0.35))
        self.lesson_win.setGeometry(16, 66, lw, min(H - 82, 700))
        sw = min(480, int(W * 0.34))
        sh = min(470, int((H - 82) * 0.62))
        self.script_win.setGeometry(W - sw - 16, 66, sw, sh)
        self.memory_win.setGeometry(W - sw - 16, 66 + sh + 8, sw, max(160, H - 66 - sh - 24))
        dw = min(900, W - 100)
        self.dialog.setGeometry((W - dw) // 2, H - 200, dw, 184)
        if self.modal:
            self.modal.setGeometry(self.world.rect())
        self._frame_garden()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()

    def _frame_garden(self, smooth=False):
        """Огород — в свободной середине экрана между окнами."""
        W, H = self.world.width(), self.world.height()
        left = self.lesson_win.geometry().right() if self.lesson_win.isVisible() else 0
        right = self.script_win.geometry().left() if self.script_win.isVisible() else W
        free_x = (left + right) / 2
        gx, gy = self.world.bed_center("тыква")
        z = self.world.zoom
        self.world.center_on(gx + (W / 2 - free_x) / z, gy - 10, smooth)

    def _set_play_ui(self, visible):
        for w in (self.hud, self.lesson_win, self.script_win, self.memory_win):
            w.setVisible(visible)

    # ------------------------------------------------------------ мир
    def _setup_world(self):
        flags = self.save.get("flags", {})
        for name, value in flags.items():
            self.world.set_flag(name, value)
        self.world.robots.clear()
        bx, by = self.world.map.spots["bublik_home"]
        self.world.add_robot("bublik", bx, by, "down", rest="idle")
        kx, ky = self.world.map.spots["klusha_home"]
        self.world.add_robot("klusha", kx, ky, "down", rest="idle")
        self.world.active_robot = "bublik"

    def _reset_robots(self):
        b = self.world.robots["bublik"]
        b.clear()
        b.x, b.y = self.world.map.spots["bublik_home"]
        b.facing = "down"
        b.rest_anim = "idle"
        b.anim = "idle"
        b.bubble = None

    def _robot_clicked(self, rid):
        if rid == "bublik" and self.script_win.isHidden() is False:
            self.script_win.raise_()
            if self.script_win.collapsed:
                self.script_win.toggle_collapse()
            play("bark", 0.8)
        elif rid == "klusha":
            play("cluck", 0.8)
            self.lesson_win.raise_()
            self.world.robots["klusha"].say("Ко-ко! Я тут, рядом с уроком.", 1.8)

    # ------------------------------------------------------------ титульный экран и вступление
    def show_title(self):
        sounds().start_music()
        self.title = TitleScreen(self.assets, self.world, bool(self.save.get("player")))
        self.title.new_game.connect(self.new_game)
        self.title.continue_game.connect(self.continue_game)
        self.title.show()
        self.title.raise_()
        self.world.center_on(*self.world.map.spots["camera_start"], smooth=False)

    def _close_title(self):
        if getattr(self, "title", None):
            self.title.deleteLater()
            self.title = None

    def _open_modal(self, window):
        self._close_modal()
        play("open", 0.7)
        self.modal = Modal(self.assets, self.world, window)

    def _close_modal(self):
        if self.modal:
            self.modal.deleteLater()
            self.modal = None

    def new_game(self):
        self._close_title()
        w = NewGameWindow(self.assets)
        w.done.connect(self._started)
        self._open_modal(w)
        w.name.setFocus()

    def _started(self, name, female):
        self.save = default_save()
        self.save["player"] = {"name": name, "female": female}
        self._store()
        self._setup_world()
        self.world.set_flag("shed_repaired", False)
        self.world.set_flag("house_repaired", False)
        dear = "Дорогая моя внучка" if female else "Дорогой мой внук"
        letter = (f"<i>{dear} {html.escape(name)}!</i><br><br>"
                  "Если ты читаешь это письмо, значит, ферма «Осенний Лог» теперь твоя. "
                  "Не пугайся, что всё заросло: у меня есть помощники.<br><br>"
                  "В сарае тебя ждут мои роботы. Они умеют всё, но только если им правильно объяснить. "
                  "Объяснять им нужно на языке <b>Python</b> — это проще, чем кажется. Клуша научит.<br><br>"
                  "Целую, бабушка Зина.<br><br>"
                  "<i>P. S. Не давай Бублику копать у колодца.</i>")
        w = InfoWindow(self.assets, "Письмо от бабушки", "icon_notebook", letter,
                       [("Пойти к сараю", "icon_arrow_right", "primary", self._intro)], width=600)
        self._open_modal(w)

    def _intro(self):
        self._close_modal()
        k = self.world.robots["klusha"]
        k.rest_anim = "off"
        k.anim = "off"
        b = self.world.robots["bublik"]
        b.rest_anim = "sleep"
        b.anim = "sleep"
        kx, ky = k.x, k.y
        self.world.center_on(kx, ky - 20)

        def power():
            self.world.particles.burst("fx_spark_on", kx, ky - 14, 0.3)
            k.rest_anim = "idle"
            play("cluck")
            self._run_dialog(INTRO, self._begin_lessons)
        play("power_on")
        k.play("power_on", 0.9, power)

    def _begin_lessons(self):
        self.save["lesson"], self.save["step"] = 0, 0
        self._store()
        self._set_play_ui(True)
        self._layout()
        self.goto_step(0, 0)

    def continue_game(self):
        self._close_title()
        self._setup_world()
        self._set_play_ui(True)
        self._layout()
        if self.save["lesson"] >= len(LESSONS):
            self._chapter_done()
            return
        self.goto_step(self.save["lesson"], self.save["step"])

    # ------------------------------------------------------------ диалоги
    def _run_dialog(self, lines, done):
        self._dialog_queue = list(lines)
        self._dialog_done = done
        self._dialog_next()

    def _dialog_next(self):
        if not self._dialog_queue:
            self.dialog.hide()
            done, self._dialog_done = self._dialog_done, None
            if done:
                done()
            return
        robot, mood, text = self._dialog_queue.pop(0)
        name = {"klusha": "Клуша", "bublik": "Бублик"}.get(robot, robot)
        self.dialog.say(robot, mood, name, self.g(text))
        r = self.world.robots.get(robot)
        if r:
            r.play("talk" if robot == "klusha" else "happy", 1.2)

    # ------------------------------------------------------------ уроки
    def lesson(self):
        return LESSONS[self.save["lesson"]]

    def steps(self):
        return self.lesson().steps + ["quest"]

    def step(self):
        return self.steps()[self.save["step"]]

    def step_key(self):
        return f"{self.lesson().id}:{self.save['step']}"

    def goto_step(self, li, si):
        self.replay.stop()
        self.save["lesson"], self.save["step"] = li, si
        self._store()
        lesson = LESSONS[li]
        steps = lesson.steps + ["quest"]
        st = steps[si]
        self.step_passed = False
        self.lesson_win.female = self.female
        self.hud.set_info(coins=self.save["coins"], lesson=f"Урок {li + 1}: {lesson.title}")
        self._reset_robots()
        editor = self.script_win.editor
        editor.set_error_line(None)
        editor.set_exec_line(None)
        self.script_win.output.clear()
        self.script_win.set_status("Готов к запуску")
        self.memory_win.view.clear()
        if st == "quest":
            q = lesson.quest
            self.world.set_beds(lesson.beds)
            self.lesson_win.set_step(lesson.title, si, len(steps), "quest",
                                     "Время настоящего задания! Прочитай записку и напиши программу. "
                                     "Если застрянешь — нажми «Подсказка».", "proud", quest=q)
            code = self.save["codes"].get(self.step_key(), q.starter)
            editor.setPlainText(code)
            fails = self.save["attempts"].get(self.step_key(), 0)
            self.lesson_win.set_buttons("Проверить", "icon_check", back=si > 0, hint=True, solution=fails >= 2)
            self.memory_win.setVisible(li >= 2)
        else:
            self.world.set_beds(st.beds or lesson.beds)
            sample = st.code if st.kind == "look" else ""
            self.lesson_win.set_step(lesson.title, si, len(steps), st.kind, st.text, st.portrait, code=sample)
            code = self.save["codes"].get(self.step_key(), st.code) if st.kind in ("fill", "fix", "write") else st.code
            editor.setPlainText(code)
            if st.kind == "look":
                self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=si > 0)
            elif st.kind == "run":
                self.lesson_win.set_buttons("Запустить", "icon_play", back=si > 0)
            else:
                self.lesson_win.set_buttons("Проверить", "icon_check", back=si > 0, hint=bool(st.hints))
            self.memory_win.setVisible(st.show_memory or li >= 2)
            if st.kind == "fill":
                QTimer.singleShot(50, editor.select_first_blank)
        self._frame_garden(smooth=True)

    def on_primary(self):
        st = self.step()
        if self.step_passed or (st != "quest" and st.kind == "look"):
            self.next_step()
            return
        if st != "quest" and st.kind == "run":
            self.run_code("run")
            return
        self.run_code("check")

    def on_back(self):
        if self.save["step"] > 0:
            self.goto_step(self.save["lesson"], self.save["step"] - 1)

    def next_step(self):
        li, si = self.save["lesson"], self.save["step"]
        if si + 1 < len(self.steps()):
            self.goto_step(li, si + 1)

    def on_hint(self):
        st = self.step()
        hints = self.lesson().quest.hints if st == "quest" else st.hints
        if not hints:
            return
        key = self.step_key()
        level = min(len(hints), self.save["hints"].get(key, 0) + 1)
        self.save["hints"][key] = level
        self._store()
        self.lesson_win.show_hint(hints[level - 1], level)

    def on_solution(self):
        q = self.lesson().quest
        text = ("Вот одно из возможных решений. Разберись, почему оно работает, — "
                "а потом попробуй написать похожее {сам|сама}.")
        w = InfoWindow(self.assets, "Решение", "icon_info", md(self.g(text)),
                       [("Закрыть", "icon_close", "wood", self._close_modal),
                        ("Вставить в редактор", "icon_copy", "primary", self._paste_solution)], code=q.solution)
        self._open_modal(w)

    def _paste_solution(self):
        self.script_win.editor.setPlainText(self.lesson().quest.solution)
        self._close_modal()

    # ------------------------------------------------------------ запуск кода
    def on_run_button(self):
        if self.replay.running and self.replay.stepping:
            self.replay.stepping = False
            self.replay.advance()
            return
        st = self.step()
        if st != "quest" and st.kind in ("look", "run"):
            self.run_code("run")
        else:
            self.run_code("check")

    def on_step_button(self):
        if self.replay.running:
            self.replay.advance()
            return
        st = self.step()
        mode = "run" if st != "quest" and st.kind in ("look", "run") else "check"
        self.run_code(mode, stepping=True)

    def on_stop(self):
        self.replay.stop()
        self.script_win.set_running(False)
        self.pending = None

    def _speed(self, v):
        self.replay.set_speed(v)
        self.save["speed"] = v

    def run_code(self, mode, stepping=False):
        if self.runner.busy() or self.replay.running:
            return
        code = self.script_win.editor.toPlainText()
        st = self.step()
        if st == "quest" or st.kind in ("fill", "fix", "write"):
            self.save["codes"][self.step_key()] = code
            self._store()
        self._write_script_file(code)
        lesson = self.lesson()
        beds = lesson.beds if st == "quest" else (st.beds or lesson.beds)
        self.world.set_beds(beds)
        self._reset_robots()
        self.script_win.editor.set_error_line(None)
        self.lesson_win.clear_feedback()
        self.pending = (mode, stepping)
        self.script_win.set_running(True, stepping)
        self.script_win.set_status("Запускаю…", "#fde07a")
        self.runner.run({"code": code, "beds": beds, "lang": "ru"})

    def _write_script_file(self, code):
        try:
            folder = paths.farm_dir() / "скрипты"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "бублик.py").write_text(SCRIPT_HEADER + code, encoding="utf-8")
        except OSError:
            pass

    def _on_result(self, raw):
        if not self.pending:
            return
        mode, stepping = self.pending
        self._last_raw = raw
        self.replay.start(raw, stepping=stepping)

    def _on_replay_done(self, raw):
        self.script_win.set_running(False)
        if not self.pending:
            return
        mode, _ = self.pending
        self.pending = None
        code = self.script_win.editor.toPlainText()
        r = Result(raw, code)
        st = self.step()
        if r.error:
            err = r.error
            self.lesson_win.show_feedback("error", err["title"], err["hint"], trace=err["trace"], portrait="frown")
            self._count_fail()
            return
        if mode == "run":
            after = st.after if st != "quest" and st.kind == "run" else ""
            if st != "quest" and st.kind == "run":
                self.step_passed = True
                self.lesson_win.show_feedback("ok", after or "Программа выполнилась!", portrait="happy")
                self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=self.save["step"] > 0)
            elif r.warnings:
                self.lesson_win.show_feedback("warn", r.warnings[0]["text"], portrait="think")
            return
        check = self.lesson().quest.check if st == "quest" else st.check
        message = check(r) if check else None
        if message is None:
            self._passed(r)
        else:
            extra = ""
            if r.warnings:
                extra = "Заметка: " + r.warnings[0]["text"]
            self.lesson_win.show_feedback("warn", message, extra, portrait="think")
            play("warn")
            self.world.robots["bublik"].show_emote("emote_question", 1.6)
            self._count_fail()

    def _count_fail(self):
        key = self.step_key()
        self.save["attempts"][key] = self.save["attempts"].get(key, 0) + 1
        self._store()
        if self.step() == "quest" and self.save["attempts"][key] >= 2:
            self.lesson_win.btn_solution.show()

    def _passed(self, r):
        st = self.step()
        self.step_passed = True
        bublik = self.world.robots["bublik"]
        bublik.play("happy", 1.2)
        bublik.show_emote("emote_heart", 1.6)
        if st == "quest":
            self._quest_done()
            return
        play("success")
        self.lesson_win.show_feedback("ok", st.success, portrait="happy")
        self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=self.save["step"] > 0)

    # ------------------------------------------------------------ задание выполнено
    def _quest_done(self):
        lesson = self.lesson()
        q = lesson.quest
        first_time = lesson.id not in self.save["done"]
        if first_time:
            self.save["done"].append(lesson.id)
            self.save["coins"] += q.reward
            self._store()
        self.hud.set_info(coins=self.save["coins"])
        play("quest")
        if first_time:
            QTimer.singleShot(1300, lambda: play("coin"))
        bx, by = self.world.bed_center("тыква")
        self.world.particles.burst("fx_confetti", bx, by, 0.6)
        reward = f"<br><br><b>+{q.reward} монет</b>" if first_time else ""
        text = f"{md(self.g(q.success))}{reward}"
        self.lesson_win.show_feedback("ok", "Задание выполнено!", self.g(q.success), portrait="proud")
        self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=True)
        w = InfoWindow(self.assets, "Задание выполнено!", "icon_check", text,
                       [("Разбор решения", "icon_info", "wood", self.show_breakdown),
                        ("В жизни", "icon_finder", "wood", self.show_life),
                        ("Дальше", "icon_arrow_right", "primary", self._finish_lesson)], width=680,
                       portrait="klusha_portrait_proud")
        self._open_modal(w)

    def show_breakdown(self):
        q = self.lesson().quest
        rows = "".join(f"<tr><td style='padding:6px; background:#2a1a14; color:#fde07a; font-family:\"Klusha Mono\";'>"
                       f"{html.escape(line)}</td><td style='padding:6px;'>{md(self.g(expl))}</td></tr>"
                       for line, expl in q.breakdown)
        text = (f"<b>Каждая строчка простыми словами:</b><br><table cellspacing='4'>{rows}</table><br>"
                f"<b>Можно было ещё так:</b><br>{md(self.g(q.alternative))}")
        w = InfoWindow(self.assets, "Разбор решения", "icon_info", text,
                       [("В жизни", "icon_finder", "wood", self.show_life),
                        ("Дальше", "icon_arrow_right", "primary", self._finish_lesson)], width=760)
        self._open_modal(w)

    def show_life(self):
        q = self.lesson().quest
        items = "".join(f"<li style='margin-bottom:6px;'>{md(self.g(x))}</li>" for x in q.life)
        steps = "".join(f"<li style='margin-bottom:4px;'>{md(self.g(x))}</li>" for x in q.try_at_home)
        text = (f"<b>{html.escape(q.life_title)}</b><ul>{items}</ul>"
                f"<b>Попробуй у себя на Mac:</b><ol>{steps}</ol>"
                f"<i>Твой код сохранён в настоящем файле: папка «Робоферма/скрипты» в Документах.</i>")
        w = InfoWindow(self.assets, "В жизни", "icon_finder", text,
                       [("Открыть Терминал", "icon_arrow_right", "wood", self.open_terminal),
                        ("Папка фермы", "icon_finder", "wood", self.open_folder),
                        ("Дальше", "icon_arrow_right", "primary", self._finish_lesson)], width=760)
        self._open_modal(w)

    def _finish_lesson(self):
        self._close_modal()
        lesson = self.lesson()
        for flag in lesson.unlock:
            if not self.save["flags"].get(flag):
                self.save["flags"][flag] = True
                self.world.set_flag(flag, True)
                names = {"shed_repaired": "Сарай отремонтирован!", "house_repaired": "Бабушкин дом отремонтирован!"}
                Toast(self.assets, self.world, names.get(flag, "Открыто новое!"), "icon_check", 3.5)
                play("success")
        li = self.save["lesson"] + 1
        self.save["lesson"], self.save["step"] = li, 0
        self._store()
        if li >= len(LESSONS):
            self._run_dialog(OUTRO, self._chapter_done)
            return
        Toast(self.assets, self.world, f"Новый урок: {LESSONS[li].title}", "icon_chapter", 3)
        self.goto_step(li, 0)

    def _chapter_done(self):
        notes = "".join(f"<li>{md(l.notes)}</li>" for l in LESSONS)
        text = ("<b>Глава 1 «Сарай» пройдена!</b><br><br>Ты уже умеешь:<ul>" + notes + "</ul>"
                "Дальше — поле на тридцать грядок, циклы и условия. Глава 2 появится в следующем обновлении игры.")
        w = InfoWindow(self.assets, "Конец главы", "icon_chapter", text,
                       [("Повторить уроки", "icon_reset", "wood", self._replay_chapter),
                        ("Папка фермы", "icon_finder", "primary", self.open_folder)], width=720)
        self._open_modal(w)

    def _replay_chapter(self):
        self._close_modal()
        self.goto_step(0, 0)

    # ------------------------------------------------------------ панель
    def toggle_xray(self):
        self.world.xray = not self.world.xray
        play("xray_on" if self.world.xray else "xray_off")
        if self.world.xray:
            Toast(self.assets, self.world, "Рентген: так мир видит программа", "icon_xray", 2.5)

    def _xray_key(self):
        if not self.script_win.editor.hasFocus():
            self.toggle_xray()

    def show_notebook(self):
        done = [l for l in LESSONS if l.id in self.save["done"]] or [self.lesson()]
        notes = "".join(f"<p><b>{html.escape(l.title)}</b><br>{md(l.notes)}</p>" for l in done)
        w = InfoWindow(self.assets, "Блокнот Клуши", "icon_notebook",
                       "<i>Шпаргалка по пройденным темам.</i><br>" + notes,
                       [("Закрыть", "icon_close", "primary", self._close_modal)], width=620)
        self._open_modal(w)

    def toggle_sound(self):
        on = not self.save.get("sound", True)
        self.save["sound"] = on
        self._store()
        sounds().set_enabled(on)
        self.hud.set_sound_icon(on)

    def closeEvent(self, e):
        sounds().shutdown()
        super().closeEvent(e)

    def open_folder(self):
        folder = paths.farm_dir()
        (folder / "скрипты").mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def open_terminal(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile("/System/Applications/Utilities/Terminal.app"))
