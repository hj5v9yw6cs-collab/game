"""Главное окно и ход игры: главы, уроки, проверки, награды, игровые дни, сохранения."""

import html
import json

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow

from robofarm import paths
from robofarm.assets import Assets
from robofarm.catalog import CATALOG
from robofarm.fallbacks import add_fallbacks
from robofarm.farm import player_view, player_view_en, player_view_ru
from robofarm.lessons import CHAPTERS, LESSONS, chapter_of, first_lesson_index, runtime
from robofarm.lessons.base import gender
from robofarm.replay import Replay
from robofarm.sandbox.client import SandboxRunner
from robofarm.sound import play, sounds
from robofarm.ui.fonts import load_fonts
from robofarm.ui.pixel import Modal, Toast
from robofarm.ui.windows import (CatalogWindow, DialogBox, Hud, InfoWindow, LessonListWindow, LessonWindow,
                                 MemoryWindow, NewGameWindow, ScriptWindow, TitleScreen, md)
from robofarm.world.entities import ROBOT_FILES, ROBOT_GENITIVE, ROBOT_NAMES
from robofarm.world.view import WorldView

SAVE_VERSION = 1
DAY_SECONDS = 150            # игровой день — две с половиной минуты игры
ROBOT_CHAPTER = {"klusha": 1, "bublik": 1, "murzik": 3, "bobr": 4, "iskra": 5, "uhta": 6}
ROBOT_SOUND = {"klusha": "cluck", "bublik": "bark", "murzik": "meow", "bobr": "chomp", "iskra": "neigh",
               "uhta": "hoot"}
ROBOT_HOME = {"murzik": "stall_counter", "bobr": "barn_home", "iskra": "post_home", "uhta": "office_home"}
FILES_SPOT = {"barn": "files_barn", "office": "files_office", "post": "files_post", "fair": "files_fair"}
ZONE_NAMES = {"yard": "Сарай и огород", "field": "Поле", "shop": "Лавка", "barn": "Амбар", "post": "Почта и деревня",
              "office": "Контора", "fair": "Ярмарка"}
FLAG_NAMES = {"shed_repaired": "Сарай отремонтирован!", "house_repaired": "Бабушкин дом отремонтирован!",
              "stall_repaired": "Лавка открыта!", "barn_repaired": "Амбар отремонтирован!",
              "post_repaired": "Почта заработала!"}


def default_save():
    return {"version": SAVE_VERSION, "player": None, "lesson": 0, "step": 0, "coins": 0, "done": [],
            "codes": {}, "attempts": {}, "hints": {}, "flags": {}, "speed": 1, "sound": True,
            "max_lesson": 0, "day": 1, "day_t": 0, "finished": False}


def script_header(lesson):
    """Пояснение в начале файла скрипта, который игра сохраняет в папку фермы."""
    name = ROBOT_NAMES.get(lesson.robot, lesson.robot)
    if lesson.folder:
        head = (f"# Скрипт робота {name} из игры «Робоферма».\n"
                "# Он работает и без игры — на настоящих файлах из этой папки. Открой Терминал и выполни:\n"
                f"#   cd ~/Documents/Робоферма/{lesson.folder}\n"
                f"#   python3 {ROBOT_FILES[lesson.robot]}\n\n")
        if "post" in lesson.kits:
            head += ('def deliver(order_id):\n'
                     '    """В игре заказ отвозит Искра, а без игры просто напишем, что доставили."""\n'
                     '    print("Доставлен заказ", order_id)\n\n\n')
        return head
    if "shop" in lesson.kits:
        return (f"# Скрипт робота {name} из игры «Робоферма».\n"
                "# Команды sell() и tag() и очередь queue есть только в игре,\n"
                "# а строки, словари и функции работают в любом Python.\n\n")
    return (f"# Скрипт робота {name} из игры «Робоферма».\n"
            "# Команды полить()/собрать() (water()/harvest()) и список поле (field) есть только на ферме,\n"
            "# а print, переменные, списки, циклы и условия работают в любом Python.\n\n")


class GameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_fonts()
        self.setWindowTitle("Робоферма")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.assets = Assets()
        add_fallbacks(self.assets)
        self.world = WorldView(self.assets)
        self.setCentralWidget(self.world)
        a = self.assets
        self.hud = Hud(a, self.world)
        self.lesson_win = LessonWindow(a, self.world)
        self.script_win = ScriptWindow(a, "bublik", self.world)
        self.memory_win = MemoryWindow(a, "Бублика", self.world)
        self.dialog = DialogBox(a, self.world)
        self.modal = None
        self.title = None
        self.runner = SandboxRunner(self)
        self.runner.finished.connect(self._on_result)
        self.replay = Replay(self.world, self.script_win.editor, self.memory_win.view, self.script_win.output,
                             self.script_win.set_status, self)
        self.replay.finished.connect(self._on_replay_done)
        self.save = self._load()
        self.pending = None  # что делать с результатом: (mode, stepping, data0, hidden)
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
        self.hud.lessons.connect(self.show_lessons)
        self.hud.catalog.connect(self.show_catalog)
        sounds().set_enabled(self.save.get("sound", True))
        self.hud.set_sound_icon(self.save.get("sound", True))
        self.world.robot_clicked.connect(self._robot_clicked)
        QShortcut(QKeySequence("R"), self, activated=self._xray_key)
        self.day_timer = QTimer(self)
        self.day_timer.timeout.connect(self._day_tick)
        self.day_timer.start(1000)
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
                save = {**default_save(), **data}
                save["lesson"] = min(save["lesson"], len(LESSONS) - 1)
                save["max_lesson"] = max(save["max_lesson"], save["lesson"])
                return save
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

    # ------------------------------------------------------------ где мы
    def lesson(self):
        return LESSONS[min(self.save["lesson"], len(LESSONS) - 1)]

    def chapter(self):
        return chapter_of(self.lesson())

    def reached_chapter(self):
        """Самая дальняя глава, до которой дошёл игрок (её зона и роботы уже открыты)."""
        return chapter_of(LESSONS[min(self.save["max_lesson"], len(LESSONS) - 1)]).number

    def steps(self):
        return self.lesson().steps + ["quest"]

    def step(self):
        """Текущий шаг (Step) или Quest, если идёт задание."""
        return runtime.target(self.lesson(), self.save["step"])

    def is_quest(self):
        return self.save["step"] >= len(self.lesson().steps)

    def step_key(self):
        return f"{self.lesson().id}:{self.save['step']}"

    def workdir(self, lesson=None):
        lesson = lesson or self.lesson()
        if not lesson.folder:
            return None
        return paths.farm_dir() / lesson.folder

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
        self._frame_lesson()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()

    def _focus_point(self, lesson=None):
        lesson = lesson or self.lesson()
        if lesson.zone == "yard":
            x, y = self.world.bed_center("тыква")
            return x, y - 10
        return self.world.map.spots[f"zone_{lesson.zone}"]

    def _frame_lesson(self, smooth=False, point=None):
        """Место урока — в свободной середине экрана между окнами."""
        W = self.world.width()
        left = self.lesson_win.geometry().right() if self.lesson_win.isVisible() else 0
        right = self.script_win.geometry().left() if self.script_win.isVisible() else W
        free_x = (left + right) / 2
        gx, gy = point or self._focus_point()
        z = self.world.zoom
        self.world.focus_offset = (W / 2 - free_x) / z
        self.world.center_on(gx + self.world.focus_offset, gy, smooth)

    def _set_play_ui(self, visible):
        for w in (self.hud, self.lesson_win, self.script_win, self.memory_win):
            w.setVisible(visible)

    # ------------------------------------------------------------ мир
    def _home(self, rid, lesson=None):
        lesson = lesson or self.lesson()
        spots = self.world.map.spots
        if lesson.zone == "fair":
            return spots["fair_team"][rid]
        if rid == "klusha":
            return spots.get(f"klusha_{lesson.zone}", spots["shed_door"])
        if rid == "bublik":
            return spots["bublik_home"] if lesson.zone == "yard" else spots["field_home"]
        return spots[ROBOT_HOME[rid]]

    def _setup_world(self):
        for name, value in self.save.get("flags", {}).items():
            self.world.set_flag(name, value)
        reached = self.reached_chapter() if self.save.get("player") else 1
        self.world.set_chapter(reached)
        self._place_robots(reached)

    def _place_robots(self, reached=None):
        reached = reached or self.reached_chapter()
        self.world.robots.clear()
        for rid, ch in ROBOT_CHAPTER.items():
            if ch <= reached:
                x, y = self._home(rid)
                self.world.add_robot(rid, x, y, "down", rest="idle")
        self.world.active_robot = self.lesson().robot

    def _reset_robots(self):
        lesson = self.lesson()
        for rid, r in self.world.robots.items():
            r.rest_anim = "idle"
            r.clear()
            r.x, r.y = self._home(rid, lesson)
            r.facing = "down"
            if rid == lesson.robot:
                r.bubble = None

    def _show_data(self, lesson, data, write_files=True, code=None):
        """Показывает в мире данные шага: грядки, очередь, ценники, подписи рентгена; кладёт файлы в папку."""
        w = self.world
        w.set_beds(data.get("beds") or [])
        w.set_customers(data.get("queue"))
        w.price_tags = []
        if lesson.field_var:
            w.bed_view = player_view_en if lesson.lang == "en" else player_view_ru
        else:
            w.bed_view = player_view
        labels = []
        prices = (data.get("inject") or {}).get("prices")
        if prices:
            sx, sy = w.map.spots["stall"]
            body = ",\n ".join(f'"{k}": {v}' for k, v in list(prices.items())[:8])
            labels.append((sx, sy - 40, "prices = {" + body + "}"))
        files = data.get("files")
        if files is not None:
            spot = w.map.spots.get(FILES_SPOT.get(lesson.zone, ""), self._home(lesson.robot, lesson))
            tops = sorted({k.split("/")[0] + ("/" if "/" in k else "") for k in files})
            shown = tops[:8] + ([f"... ещё {len(tops) - 8}"] if len(tops) > 8 else [])
            labels.append((spot[0], spot[1] - 24, f"папка «{lesson.folder}»:\n" + "\n".join(shown)))
            if write_files:
                self._write_lesson_files(lesson, files, code)
        if data.get("orders"):
            px, py = w.map.spots["post"]
            ids = ", ".join(str(o["id"]) for o in data["orders"][:8])
            labels.append((px, py - 50, f"orders: {len(data['orders'])} шт.\nid: {ids}"))
        w.extra_labels = labels

    def _write_lesson_files(self, lesson, files, code=None):
        """Файлы урока — в настоящую папку на Mac, рядом со скриптом робота."""
        folder = self.workdir(lesson)
        if folder is None or not lesson.folder.strip("/."):
            return
        try:
            from robofarm.sandbox.engine import reset_dir
            folder.parent.mkdir(parents=True, exist_ok=True)
            reset_dir(folder, files)
            if code is not None:
                (folder / ROBOT_FILES[lesson.robot]).write_text(script_header(lesson) + code, encoding="utf-8")
        except OSError:
            pass

    def _write_script_file(self, lesson, code):
        try:
            if lesson.folder:
                folder = self.workdir(lesson)
            else:
                folder = paths.farm_dir() / "скрипты"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / ROBOT_FILES[lesson.robot]).write_text(script_header(lesson) + code, encoding="utf-8")
        except OSError:
            pass

    def _robot_clicked(self, rid):
        play(ROBOT_SOUND.get(rid, "click"), 0.8)
        if rid == self.lesson().robot and not self.script_win.isHidden():
            self.script_win.raise_()
            if self.script_win.collapsed:
                self.script_win.toggle_collapse()
        elif rid == "klusha":
            self.lesson_win.raise_()
            self.world.robots["klusha"].say("Ко-ко! Я тут, рядом с уроком.", 1.8)
        else:
            ch = next((c for c in CHAPTERS if c.robot == rid), None)
            text = f"Моя работа — глава «{ch.title}»." if ch else "Я на месте!"
            self.world.robots[rid].say(text, 1.8)

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
        if self.title:
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
        for flag in list(self.world.flags):
            self.world.set_flag(flag, False)
        self._setup_world()
        self._update_hud()
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
            self._run_dialog(CHAPTERS[0].intro, self._begin_lessons)
        play("power_on")
        k.play("power_on", 0.9, power)

    def _begin_lessons(self):
        self._set_play_ui(True)
        self._layout()
        self.goto_step(0, 0)

    def continue_game(self):
        self._close_title()
        self._setup_world()
        self._set_play_ui(True)
        self._layout()
        self.goto_step(self.save["lesson"], self.save["step"])
        if self.save.get("finished") and self.save["lesson"] == len(LESSONS) - 1:
            self._game_finished()

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
        self.dialog.say(robot, mood, ROBOT_NAMES.get(robot, robot), self.g(text))
        r = self.world.robots.get(robot)
        if r and r.rest_anim not in ("off", "sleep"):
            r.play("talk" if self.assets.get(f"{robot}_talk") else "happy", 1.2)

    # ------------------------------------------------------------ уроки
    def _update_hud(self):
        lesson = self.lesson()
        ch = chapter_of(lesson)
        n = LESSONS.index(lesson) + 1
        self.hud.set_info(coins=self.save["coins"], chapter=f"Глава {ch.number}: {ch.title}",
                          lesson=f"Урок {n}: {lesson.title}", day=self.save["day"])

    def goto_step(self, li, si):
        self.replay.stop()
        self.pending = None
        self.world.follow = None
        prev = self.lesson()
        self.save["lesson"], self.save["step"] = li, si
        self.save["max_lesson"] = max(self.save["max_lesson"], li)
        self._store()
        lesson = LESSONS[li]
        steps = lesson.steps + ["quest"]
        st = runtime.target(lesson, si)
        quest = si >= len(lesson.steps)
        self.step_passed = False
        self.lesson_win.female = self.female
        self._update_hud()
        if prev.zone != lesson.zone or prev.robot != lesson.robot or not self.world.robots:
            self._place_robots()
        self.world.active_robot = lesson.robot
        self.script_win.set_robot(lesson.robot, ROBOT_FILES[lesson.robot])
        self.memory_win.set_robot(ROBOT_GENITIVE.get(lesson.robot, lesson.robot))
        self._reset_robots()
        editor = self.script_win.editor
        editor.set_error_line(None)
        editor.set_exec_line(None)
        self.script_win.output.clear()
        self.script_win.set_status("Готов к запуску")
        self.memory_win.view.clear()
        if quest:
            q = lesson.quest
            code = self.save["codes"].get(self.step_key(), q.starter)
            self.lesson_win.set_step(lesson.title, si, len(steps), "quest",
                                     "Время настоящего задания! Прочитай записку и напиши программу. "
                                     "Если застрянешь — нажми «Подсказка».", "proud", quest=q)
            editor.setPlainText(code)
            fails = self.save["attempts"].get(self.step_key(), 0)
            self.lesson_win.set_buttons("Проверить", "icon_check", back=si > 0, hint=True, solution=fails >= 2)
            self.memory_win.setVisible(li >= 2)
        else:
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
        self._show_data(lesson, runtime.data_for(lesson, st, 0), code=code)
        self._frame_lesson(smooth=True)

    def on_primary(self):
        st = self.step()
        if self.step_passed or (not self.is_quest() and st.kind == "look"):
            self.next_step()
            return
        if not self.is_quest() and st.kind == "run":
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
        elif self.lesson().id in self.save["done"]:
            self._finish_lesson()

    def on_hint(self):
        hints = self.step().hints
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
    def _run_mode(self):
        st = self.step()
        return "run" if not self.is_quest() and st.kind in ("look", "run") else "check"

    def on_run_button(self):
        if self.replay.running and self.replay.stepping:
            self.replay.stepping = False
            self.replay.advance()
            return
        self.run_code(self._run_mode())

    def on_step_button(self):
        if self.replay.running:
            self.replay.advance()
            return
        self.run_code(self._run_mode(), stepping=True)

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
        lesson, st = self.lesson(), self.step()
        if self.is_quest() or st.kind in ("fill", "fix", "write"):
            self.save["codes"][self.step_key()] = code
            self._store()
        workdir = self.workdir(lesson)
        if workdir is not None:
            try:
                workdir.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                workdir = None
        payload, data0, hidden = runtime.build(lesson, st, code, workdir)
        if not lesson.folder:
            self._write_script_file(lesson, code)
        self._show_data(lesson, data0, write_files=False)
        self._reset_robots()
        self.script_win.editor.set_error_line(None)
        self.lesson_win.clear_feedback()
        self.pending = (mode, stepping, data0, hidden)
        self.script_win.set_running(True, stepping)
        self.script_win.set_status("Запускаю…", "#fde07a")
        self.runner.run(payload)

    def _on_result(self, raw):
        if not self.pending:
            return
        stepping = self.pending[1]
        lesson = self.lesson()
        if lesson.folder:
            self._write_script_file(lesson, self.script_win.editor.toPlainText())
        spots = self.world.map.spots
        ctx = {"home": self._home(lesson.robot, lesson)}
        if lesson.zone in FILES_SPOT:
            ctx["files"] = spots[FILES_SPOT[lesson.zone]]
        self.world.follow = lesson.robot
        self.replay.start(raw, stepping=stepping, robot_id=lesson.robot, ctx=ctx)

    def _on_replay_done(self, raw):
        self.script_win.set_running(False)
        if not self.pending:
            return
        mode, _, data0, hidden = self.pending
        self.pending = None
        code = self.script_win.editor.toPlainText()
        r = runtime.result(raw, code, data0, hidden)
        st = self.step()
        lesson = self.lesson()
        robot = self.world.robots.get(lesson.robot)
        run_step = not self.is_quest() and st.kind == "run"
        if r.error:
            err = r.error
            if run_step and st.expect_error:
                self.step_passed = True
                text = err["hint"] + ("\n\n" + st.after if st.after else "")
                self.lesson_win.show_feedback("error", err["title"], text, trace=err["trace"], portrait="explain")
                self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=self.save["step"] > 0)
                return
            self.lesson_win.show_feedback("error", err["title"], err["hint"], trace=err["trace"], portrait="frown")
            self._count_fail()
            return
        if mode == "run":
            if run_step:
                self.step_passed = True
                self.lesson_win.show_feedback("ok", st.after or "Программа выполнилась!", portrait="happy")
                self.lesson_win.set_buttons("Дальше", "icon_arrow_right", back=self.save["step"] > 0)
            elif r.warnings:
                self.lesson_win.show_feedback("warn", r.warnings[0]["text"], portrait="think")
            return
        message = runtime.check(lesson, st, r)
        if message is None:
            self._passed(r)
        else:
            extra = "Заметка: " + r.warnings[0]["text"] if r.warnings else ""
            self.lesson_win.show_feedback("warn", message, extra, portrait="think")
            play("warn")
            if robot:
                robot.show_emote("emote_question", 1.6)
            self._count_fail()

    def _count_fail(self):
        key = self.step_key()
        self.save["attempts"][key] = self.save["attempts"].get(key, 0) + 1
        self._store()
        if self.is_quest() and self.save["attempts"][key] >= 2:
            self.lesson_win.btn_solution.show()

    def _passed(self, r):
        self.step_passed = True
        robot = self.world.robots.get(self.lesson().robot)
        if robot:
            robot.play("happy", 1.2)
            robot.show_emote("emote_heart", 1.6)
        if self.is_quest():
            self._quest_done()
            return
        play("success")
        self.lesson_win.show_feedback("ok", self.step().success, portrait="happy")
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
        bx, by = self._focus_point(lesson)
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
        rows = "".join(f"<tr><td style='padding:6px; background:#2a1a14; color:#fde07a; font-family:\"PT Mono\";"
                       f" white-space:pre;'>{html.escape(line)}</td><td style='padding:6px;'>{md(self.g(expl))}</td></tr>"
                       for line, expl in q.breakdown)
        text = (f"<b>Каждая строчка простыми словами:</b><br><table cellspacing='4'>{rows}</table><br>"
                f"<b>Можно было ещё так:</b><br>{md(self.g(q.alternative))}")
        w = InfoWindow(self.assets, "Разбор решения", "icon_info", text,
                       [("В жизни", "icon_finder", "wood", self.show_life),
                        ("Дальше", "icon_arrow_right", "primary", self._finish_lesson)], width=760)
        self._open_modal(w)

    def show_life(self):
        lesson = self.lesson()
        q = lesson.quest
        items = "".join(f"<li style='margin-bottom:6px;'>{md(self.g(x))}</li>" for x in q.life)
        steps = "".join(f"<li style='margin-bottom:4px;'>{md(self.g(x))}</li>" for x in q.try_at_home)
        where = (f"папка «Робоферма/{lesson.folder}» в Документах — рядом с файлами, с которыми он работает"
                 if lesson.folder else "папка «Робоферма/скрипты» в Документах")
        text = (f"<b>{html.escape(q.life_title)}</b><ul>{items}</ul>"
                f"<b>Попробуй у себя на Mac:</b><ol>{steps}</ol>"
                f"<i>Твой код сохранён в настоящем файле {ROBOT_FILES[lesson.robot]}: {where}.</i>")
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
                Toast(self.assets, self.world, FLAG_NAMES.get(flag, "Открыто новое!"), "icon_check", 3.5)
                play("success")
        li = self.save["lesson"] + 1
        ch = chapter_of(lesson)
        if li >= len(LESSONS):
            first = not self.save.get("finished")
            self.save["finished"] = True
            self._store()
            if first:
                self._run_dialog(ch.outro, self._game_finished)
            else:
                self._game_finished()
            return
        nxt = LESSONS[li]
        if chapter_of(nxt) is not ch:
            seen = self.save["max_lesson"] >= li
            if seen:
                self._start_chapter(chapter_of(nxt), replay=True)
            else:
                self._run_dialog(ch.outro, lambda: self._chapter_done(ch))
            return
        Toast(self.assets, self.world, f"Новый урок: {nxt.title}", "icon_chapter", 3)
        self.goto_step(li, 0)

    def _chapter_done(self, ch):
        notes = "".join(f"<li>{md(l.notes)}</li>" for l in ch.lessons)
        what, coins = ch.automation
        nxt = CHAPTERS[ch.number] if ch.number < len(CHAPTERS) else None
        auto = (f"<br><b>Теперь каждый игровой день: {what} — +{coins} монет.</b> "
                "Так и в жизни: один раз написанная программа работает на тебя снова и снова.") if coins else ""
        text = f"<b>Глава {ch.number} «{ch.title}» пройдена!</b><br><br>Ты уже умеешь:<ul>{notes}</ul>{auto}"
        buttons = [("Папка фермы", "icon_finder", "wood", self.open_folder)]
        if nxt:
            buttons.append((f"Глава {nxt.number}: {nxt.title}", "icon_arrow_right", "primary",
                            lambda: self._start_chapter(nxt)))
        w = InfoWindow(self.assets, "Конец главы", "icon_chapter", self.g(text), buttons, width=740,
                       portrait="klusha_portrait_proud")
        self._open_modal(w)
        play("fanfare")

    def _start_chapter(self, ch, replay=False):
        """Новая глава: туман над зоной рассеивается, просыпается новый робот, Клуша рассказывает, что дальше."""
        self._close_modal()
        li = first_lesson_index(ch)
        self.save["lesson"], self.save["step"] = li, 0
        self.save["max_lesson"] = max(self.save["max_lesson"], li)
        self._store()
        self.world.set_chapter(self.reached_chapter(), animate=not replay)
        self._place_robots()
        self._update_hud()
        if replay:
            self.goto_step(li, 0)
            return
        self._set_play_ui(False)
        self.world.center_on(*self.world.map.spots[f"zone_{ch.zone}"])
        play("zone_open")
        Toast(self.assets, self.world, f"Открыта зона: {ZONE_NAMES.get(ch.zone, ch.title)}", "icon_map", 3.5)
        robot = self.world.robots.get(ch.robot)
        new_robot = robot is not None and ROBOT_CHAPTER.get(ch.robot) == ch.number
        if new_robot:
            robot.rest_anim = "sleep"
            robot.anim = "sleep"

        def begin():
            if new_robot:
                robot.rest_anim = "idle"
                self.world.particles.burst("fx_spark_on", robot.x, robot.y - 14, 0.3)
                play("power_on", 0.8)
                robot.play("happy", 1.2)
                robot.show_emote("emote_exclaim", 1.5)
                play(ROBOT_SOUND.get(ch.robot, "click"), 0.8)
            self._set_play_ui(True)
            self._layout()
            self.goto_step(li, 0)

        QTimer.singleShot(1800, lambda: self._run_dialog(ch.intro, begin))

    def _game_finished(self):
        from robofarm.lessons.chapter7 import FINALE
        w = InfoWindow(self.assets, "Что дальше", "icon_chapter", self.g(FINALE),
                       [("Уроки", "icon_map", "wood", self.show_lessons),
                        ("Папка фермы", "icon_finder", "primary", self.open_folder)], width=780,
                       portrait="klusha_portrait_proud")
        self._open_modal(w)
        play("fanfare")
        fx, fy = self.world.map.spots["fair"]
        for i in range(5):
            QTimer.singleShot(i * 350, lambda i=i: self.world.particles.burst("fx_confetti", fx - 40 + i * 20,
                                                                                fy - 30, 0.6))

    # ------------------------------------------------------------ игровые дни и доход
    def _day_tick(self):
        if not self.hud.isVisible() or self.modal or self.dialog.isVisible() or self.title:
            return
        self.save["day_t"] = self.save.get("day_t", 0) + 1
        if self.save["day_t"] < DAY_SECONDS:
            return
        self.save["day_t"] = 0
        self.save["day"] += 1
        income = sum(ch.automation[1] for ch in CHAPTERS
                     if ch.automation[1] and all(l.id in self.save["done"] for l in ch.lessons))
        self.save["coins"] += income
        self._store()
        self._update_hud()
        play("rooster", 0.6)
        if income:
            QTimer.singleShot(900, lambda: play("coin", 0.8))
            text = f"День {self.save['day']}. Роботы поработали сами: +{income} монет"
        else:
            text = f"День {self.save['day']}. Утро на ферме"
        Toast(self.assets, self.world, text, "icon_day", 3.5)

    # ------------------------------------------------------------ панель
    def show_lessons(self):
        w = LessonListWindow(self.assets, CHAPTERS, LESSONS, self.save["done"], self.save["max_lesson"],
                             self.save["lesson"])
        w.picked.connect(self._pick_lesson)
        w.closed_by_user.connect(self._close_modal)
        self._open_modal(w)

    def _pick_lesson(self, li):
        self._close_modal()
        self.on_stop()
        self._set_play_ui(True)
        self._layout()
        self.goto_step(li, 0)

    def show_catalog(self):
        w = CatalogWindow(self.assets, CATALOG, self.save["coins"], self.save["flags"])
        w.bought.connect(self._buy)
        w.closed_by_user.connect(self._close_modal)
        self._open_modal(w)

    def _buy(self, decor_id):
        d = next(x for x in CATALOG if x.id == decor_id)
        if self.save["flags"].get(d.flag) or self.save["coins"] < d.price:
            return
        self.save["coins"] -= d.price
        self.save["flags"][d.flag] = True
        self._store()
        self.world.set_flag(d.flag, True)
        self.hud.set_info(coins=self.save["coins"])
        play("coin")
        self._close_modal()
        placed = [o for o in self.world.map.objects if o.tag == d.flag]
        for o in placed:
            self.world.particles.burst("fx_confetti", o.x, o.y - 10, 0.6)
        if placed:
            self.world.center_on(placed[0].x, placed[0].y)
        Toast(self.assets, self.world, f"Куплено: {d.title}", "icon_check", 3)
        QTimer.singleShot(2600, lambda: self._frame_lesson(smooth=True))

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
        parts = []
        for ch in CHAPTERS:
            mine = [l for l in done if l in ch.lessons]
            if not mine:
                continue
            parts.append(f"<h3>Глава {ch.number}. {html.escape(ch.title)}</h3>")
            parts += [f"<p><b>{html.escape(l.title)}</b><br>{md(l.notes)}</p>" for l in mine]
        w = InfoWindow(self.assets, "Блокнот Клуши", "icon_notebook",
                       "<i>Шпаргалка по пройденным темам.</i><br>" + "".join(parts),
                       [("Закрыть", "icon_close", "primary", self._close_modal)], width=660)
        self._open_modal(w)

    def toggle_sound(self):
        on = not self.save.get("sound", True)
        self.save["sound"] = on
        self._store()
        sounds().set_enabled(on)
        self.hud.set_sound_icon(on)

    def closeEvent(self, e):
        self._store()
        sounds().shutdown()
        super().closeEvent(e)

    def open_folder(self):
        folder = self.workdir() or paths.farm_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (paths.farm_dir() / "скрипты").mkdir(exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def open_terminal(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile("/System/Applications/Utilities/Terminal.app"))
