"""Окна игры: урок Клуши, скрипт робота, память, диалог, верхняя панель, модальные окна."""

import html
import re

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractSlider, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from robofarm.lessons.base import STEP_LABELS
from robofarm.sound import play
from robofarm.ui.editor import CodeEditor
from robofarm.ui.fonts import code_font, title_font, ui_font
from robofarm.ui.memory import MemoryView
from robofarm.ui.pixel import PixelButton, PixelWindow, draw_nine, draw_sprite, text_label

TEXT = "#3d2318"
MUTED = "#6b3a24"


def md(text, female=False):
    """Мини-разметка реплик: `код`, **жирный**, переносы строк, формы {м|ж}."""
    from robofarm.lessons.base import gender
    text = gender(text, female)
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", lambda m: f'<span style="background:#e8d4a8; color:#8e2430;">&nbsp;{m.group(1)}&nbsp;</span>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return out.replace("\n", "<br>")


def sprite_pixmap(assets, sid, scale=2, fit=None):
    img = assets[sid].frame()
    if fit:
        scale = max(1, min(scale, fit // max(img.width(), img.height())))
    return QPixmap.fromImage(img.scaled(img.width() * scale, img.height() * scale))


class PixelSlider(QAbstractSlider):
    def __init__(self, assets, parent=None):
        super().__init__(parent)
        self.assets = assets
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setFixedHeight(30)
        self.setMinimumWidth(110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _pos_to_value(self, x):
        span = max(1, self.width() - 16)
        v = round((x - 8) / span * (self.maximum() - self.minimum())) + self.minimum()
        return max(self.minimum(), min(self.maximum(), v))

    def mousePressEvent(self, e):
        self.setValue(self._pos_to_value(e.position().x()))

    def mouseMoveEvent(self, e):
        self.setValue(self._pos_to_value(e.position().x()))

    def paintEvent(self, e):
        p = QPainter(self)
        track = QRectF(4, 11, self.width() - 8, 8)
        draw_nine(p, self.assets, "ui_slider_track", track)
        frac = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        fill = QRectF(4, 11, max(12, (self.width() - 8) * frac), 8)
        draw_nine(p, self.assets, "ui_slider_fill", fill)
        kx = 4 + (self.width() - 24) * frac
        draw_sprite(p, self.assets, "ui_slider_knob_normal", kx, 3)


class Portrait(QLabel):
    def __init__(self, assets, robot="klusha", mood="calm"):
        super().__init__()
        self.assets = assets
        self.setFixedSize(128, 128)
        self.set(robot, mood)

    def set(self, robot, mood):
        sid = f"{robot}_portrait_{mood}"
        if not self.assets.get(sid):
            sid = f"{robot}_portrait_calm"
        self.setPixmap(sprite_pixmap(self.assets, sid, 2))


class LessonWindow(PixelWindow):
    """Окно урока: Клуша ведёт по шагам."""

    primary = Signal()
    back = Signal()
    hint = Signal()
    solution = Signal()

    def __init__(self, assets, parent=None):
        super().__init__(assets, "Клуша", icon="klusha_icon", parent=parent, closable=False)
        self.female = False
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(8)
        # шаги
        self.steps_row = QWidget()
        self.steps_row.setFixedHeight(30)
        self.steps_row.paintEvent = self._paint_steps
        self.step_index, self.step_count, self.step_kind, self.lesson_title = 0, 1, "look", ""
        lay.addWidget(self.steps_row)
        # портрет + реплика
        row = QHBoxLayout()
        row.setSpacing(12)
        self.portrait = Portrait(assets)
        row.addWidget(self.portrait, 0, Qt.AlignmentFlag.AlignTop)
        self.speech = text_label("", 17, TEXT)
        self.speech.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(self.speech, 1)
        lay.addLayout(row)
        # пример кода
        self.sample = CodeEditor(assets)
        self.sample.setReadOnly(True)
        self.sample.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.sample)
        # записка-задание
        self.quest_box = QLabel()
        self.quest_box.setWordWrap(True)
        self.quest_box.setFont(ui_font(16))
        self.quest_box.setTextFormat(Qt.TextFormat.RichText)
        self.quest_box.setStyleSheet("background:#f8eed4; color:#3d2318; border:2px solid #b07a46; padding:8px;")
        lay.addWidget(self.quest_box)
        # отклик
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.setTextFormat(Qt.TextFormat.RichText)
        self.feedback.setFont(ui_font(16))
        lay.addWidget(self.feedback)
        self.trace_btn = PixelButton(assets, "Как это выглядит в настоящем Python", kind="wood")
        self.trace_btn.setFont(ui_font(14, True))
        self.trace_btn.clicked.connect(self._toggle_trace)
        lay.addWidget(self.trace_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.trace = QLabel()
        self.trace.setFont(code_font(1))
        self.trace.setStyleSheet("background:#2a1a14; color:#f3e6cf; padding:8px;")
        self.trace.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.trace)
        self.hint_label = text_label("", 16, MUTED)
        self.hint_label.setStyleSheet("color:#6b3a24; background:#f3e3bd; padding:6px; border:2px dashed #c48d52;")
        lay.addWidget(self.hint_label)
        lay.addStretch(1)
        # кнопки
        btns = QHBoxLayout()
        self.btn_back = PixelButton(assets, "Назад", "icon_arrow_left", "wood")
        self.btn_back.clicked.connect(self.back)
        self.btn_hint = PixelButton(assets, "Подсказка", "icon_hint_1", "wood")
        self.btn_hint.clicked.connect(self.hint)
        self.btn_solution = PixelButton(assets, "Решение", "icon_info", "wood")
        self.btn_solution.clicked.connect(self.solution)
        self.btn_primary = PixelButton(assets, "Дальше", "icon_arrow_right", "primary")
        self.btn_primary.clicked.connect(self.primary)
        btns.addWidget(self.btn_back)
        btns.addWidget(self.btn_hint)
        btns.addWidget(self.btn_solution)
        btns.addStretch(1)
        btns.addWidget(self.btn_primary)
        lay.addLayout(btns)
        self.clear_feedback()

    def _paint_steps(self, e):
        p = QPainter(self.steps_row)
        x = 2
        for i in range(self.step_count):
            sid = "ui_step_dot_done" if i < self.step_index else (
                "ui_step_dot_current" if i == self.step_index else "ui_step_dot_todo")
            draw_sprite(p, self.assets, sid, x, 7)
            x += 22
        icon, label = STEP_LABELS[self.step_kind]
        x += 8
        draw_sprite(p, self.assets, icon, x, 3)
        p.setFont(ui_font(16, True))
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(x + 32, 23), label)

    def set_step(self, lesson_title, index, count, kind, text, portrait, code="", quest=None):
        self.lesson_title, self.step_index, self.step_count, self.step_kind = lesson_title, index, count, kind
        self.steps_row.update()
        self.portrait.set("klusha", portrait)
        self.speech.setText(md(text, self.female))
        self.sample.setVisible(bool(code))
        if code:
            self.sample.setPlainText(code)
            lines = code.count("\n") + 1
            self.sample.setFixedHeight(min(8, lines) * self.sample.fontMetrics().lineSpacing() + 16)
        self.quest_box.setVisible(bool(quest))
        if quest:
            goals = "".join(f"<br>☐ {html.escape(g)}" for g in quest.goals)
            self.quest_box.setText(f"<b>{html.escape(quest.giver)}</b><br>{md(quest.note, self.female)}"
                                   f"<br><br><b>Что нужно сделать:</b>{goals}")
        self.clear_feedback()

    def set_buttons(self, primary_text, primary_icon, back=True, hint=False, solution=False, primary_enabled=True):
        self.btn_primary.setText(primary_text)
        self.btn_primary.icon_id = primary_icon
        self.btn_primary.setEnabled(primary_enabled)
        self.btn_primary.updateGeometry()
        self.btn_primary.update()
        self.btn_back.setVisible(back)
        self.btn_hint.setVisible(hint)
        self.btn_solution.setVisible(solution)

    def clear_feedback(self):
        self.feedback.hide()
        self.trace_btn.hide()
        self.trace.hide()
        self.hint_label.hide()

    def show_feedback(self, kind, title, text="", trace=None, portrait=None):
        colors = {"ok": ("#2c5e30", "#d8ecc4", "✓"), "warn": ("#7a4a0e", "#f6e2b0", "!"), "error": ("#8e2430", "#f4d0c8", "✗")}
        fg, bg, mark = colors[kind]
        body = f"<b>{mark} {md(title, self.female)}</b>"
        if text:
            body += f"<br>{md(text, self.female)}"
        self.feedback.setText(body)
        self.feedback.setStyleSheet(f"color:{fg}; background:{bg}; padding:8px; border:2px solid {fg};")
        self.feedback.show()
        if portrait:
            self.portrait.set("klusha", portrait)
        if trace:
            self.trace.setText(html.escape(trace).replace("\n", "<br>").replace(" ", "&nbsp;"))
            self.trace_btn.show()
            self.trace.hide()
        else:
            self.trace_btn.hide()
            self.trace.hide()

    def _toggle_trace(self):
        self.trace.setVisible(not self.trace.isVisible())

    def show_hint(self, text, level):
        self.hint_label.setText(md(f"Подсказка {level}: {text}", self.female))
        self.hint_label.show()
        self.btn_hint.icon_id = f"icon_hint_{min(3, level + 1)}"
        self.btn_hint.update()


class ScriptWindow(PixelWindow):
    """Окно скрипта робота: редактор + управление запуском + вывод."""

    run = Signal()
    step = Signal()
    stop = Signal()
    speed_changed = Signal(int)

    def __init__(self, assets, robot="bublik", parent=None):
        super().__init__(assets, f"{'бублик' if robot == 'bublik' else robot}.py", icon=f"{robot}_icon",
                         dark=True, parent=parent, closable=False)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.editor = CodeEditor(assets)
        self.editor.run_requested.connect(self.run)
        lay.addWidget(self.editor, 3)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_run = PixelButton(assets, "Пуск", "icon_play", "primary", tooltip="Запустить (Cmd + Enter)")
        self.btn_run.clicked.connect(self.run)
        self.btn_step = PixelButton(assets, "Шаг", "icon_step", "wood", tooltip="Выполнить одну строку")
        self.btn_step.clicked.connect(self.step)
        self.btn_stop = PixelButton(assets, "", "icon_stop", "danger", tooltip="Остановить")
        self.btn_stop.clicked.connect(self.stop)
        for b in (self.btn_run, self.btn_step, self.btn_stop):
            bar.addWidget(b)
        bar.addStretch(1)
        turtle = QLabel()
        turtle.setPixmap(sprite_pixmap(assets, "icon_turtle"))
        hare = QLabel()
        hare.setPixmap(sprite_pixmap(assets, "icon_hare"))
        self.speed = PixelSlider(assets)
        self.speed.setRange(0, 4)
        self.speed.setValue(1)
        self.speed.valueChanged.connect(self.speed_changed)
        bar.addWidget(turtle)
        bar.addWidget(self.speed)
        bar.addWidget(hare)
        lay.addLayout(bar)
        self.status = QLabel("Готов к запуску")
        self.status.setFont(ui_font(15))
        self.status.setStyleSheet("color:#a88a70;")
        lay.addWidget(self.status)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(code_font(2))
        self.output.setPlaceholderText("Здесь появится всё, что напечатает print()")
        self.output.setStyleSheet("background:#22140f; color:#f3e6cf; border:none; padding:4px;")
        self.output.setMaximumHeight(130)
        lay.addWidget(self.output, 1)
        self.set_running(False)

    def set_robot(self, robot, filename):
        self.icon_id = f"{robot}_icon" if self.assets.get(f"{robot}_icon") else "icon_notebook"
        self.title = filename
        self.update()

    def set_running(self, running, stepping=False):
        self.btn_run.setEnabled(not running or stepping)
        self.btn_stop.setEnabled(running)
        self.editor.setReadOnly(running)

    def set_status(self, text, color="#a88a70"):
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{color};")


class MemoryWindow(PixelWindow):
    def __init__(self, assets, robot_name="Бублика", parent=None):
        super().__init__(assets, f"Память {robot_name}", icon="icon_notebook", parent=parent)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = MemoryView(assets)
        lay.addWidget(self.view)

    def set_robot(self, robot_name):
        self.title = f"Память {robot_name}"
        self.update()


class DialogBox(QWidget):
    """Реплика персонажа внизу экрана (как в Stardew Valley). Клик — дальше."""

    next = Signal()

    def __init__(self, assets, parent):
        super().__init__(parent)
        self.assets = assets
        self.robot, self.mood, self.name, self.text, self.shown = "klusha", "calm", "Клуша", "", 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._type)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()

    def say(self, robot, mood, name, text):
        self.robot, self.mood, self.name, self.text, self.shown = robot, mood, name, text, 0
        self.timer.start(18)
        self.show()
        self.raise_()

    def _type(self):
        before = self.shown
        self.shown = min(len(self.text), self.shown + 2)
        if before // 6 != self.shown // 6:
            play(f"voice_{self.robot}", 0.6)
        if self.shown >= len(self.text):
            self.timer.stop()
        self.update()

    def mousePressEvent(self, e):
        if self.shown < len(self.text):
            self.shown = len(self.text)
            self.update()
        else:
            play("page")
            self.next.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        draw_nine(p, self.assets, "ui_window_wood", QRectF(self.rect()))
        sid = f"{self.robot}_portrait_{self.mood}"
        if not self.assets.get(sid):
            sid = f"{self.robot}_portrait_calm"
        draw_sprite(p, self.assets, sid, 28, 28)
        plate = QRectF(26, self.height() - 52, 132, 32)
        draw_nine(p, self.assets, "ui_titlebar", plate)
        p.setFont(ui_font(17, True))
        p.setPen(QColor(TEXT))
        p.drawText(plate, Qt.AlignmentFlag.AlignCenter, self.name)
        p.setFont(ui_font(19))
        p.drawText(QRectF(184, 30, self.width() - 214, self.height() - 60),
                   Qt.TextFlag.TextWordWrap, self.text[: self.shown])
        if self.shown >= len(self.text):
            p.setPen(QColor(MUTED))
            p.setFont(ui_font(14))
            hint = "щёлкни, чтобы продолжить"
            p.drawText(QPointF(self.width() - p.fontMetrics().horizontalAdvance(hint) - 30, self.height() - 26), hint)


class Hud(QWidget):
    """Верхняя панель: монеты, глава, кнопки рентгена, блокнота, папки фермы."""

    xray = Signal()
    notebook = Signal()
    folder = Signal()
    sound = Signal()
    lessons = Signal()
    catalog = Signal()

    def __init__(self, assets, parent):
        super().__init__(parent)
        self.assets = assets
        self.coins, self.chapter, self.lesson, self.day = 0, "Глава 1: Сарай", "", 1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        self.btn_lessons = PixelButton(assets, "Уроки", "icon_map", "wood", tooltip="Все главы и уроки")
        self.btn_lessons.clicked.connect(self.lessons)
        self.btn_catalog = PixelButton(assets, "Каталог", "icon_coins", "wood",
                                       tooltip="Бабушкин каталог: украшения для фермы за монеты")
        self.btn_catalog.clicked.connect(self.catalog)
        self.btn_xray = PixelButton(assets, "Рентген", "icon_xray", "wood", tooltip="Показать данные мира (R)")
        self.btn_xray.clicked.connect(self.xray)
        self.btn_note = PixelButton(assets, "Блокнот", "icon_notebook", "wood", tooltip="Шпаргалка Клуши")
        self.btn_note.clicked.connect(self.notebook)
        self.btn_folder = PixelButton(assets, "", "icon_finder", "wood", tooltip="Открыть папку фермы в Finder")
        self.btn_folder.clicked.connect(self.folder)
        self.btn_sound = PixelButton(assets, "", "icon_sound_on", "wood", tooltip="Звук и музыка")
        self.btn_sound.clicked.connect(self.sound)
        for b in (self.btn_lessons, self.btn_catalog, self.btn_xray, self.btn_note, self.btn_folder, self.btn_sound):
            lay.addWidget(b)
        self.setFixedHeight(46)

    def set_sound_icon(self, on):
        self.btn_sound.icon_id = "icon_sound_on" if on else "icon_sound_off"
        self.btn_sound.update()

    def set_info(self, coins=None, chapter=None, lesson=None, day=None):
        if day is not None:
            self.day = day
        if coins is not None:
            self.coins = coins
        if chapter is not None:
            self.chapter = chapter
        if lesson is not None:
            self.lesson = lesson
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(ui_font(18, True))
        fm = p.fontMetrics()
        text = f"{self.coins}"
        w = fm.horizontalAdvance(text) + 66
        r = QRectF(0, 2, w, 40)
        draw_nine(p, self.assets, "ui_titlebar", r)
        draw_sprite(p, self.assets, "icon_coins", 12, 10)
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(44, 22 + fm.ascent() / 2 - 2), text)
        day = f"День {self.day}"
        wd = fm.horizontalAdvance(day) + 62
        rd = QRectF(w + 10, 2, wd, 40)
        draw_nine(p, self.assets, "ui_titlebar", rd)
        draw_sprite(p, self.assets, "icon_day", w + 22, 10)
        p.drawText(QPointF(w + 54, 22 + fm.ascent() / 2 - 2), day)
        x = w + 10 + wd + 10
        room = max(120, self.width() - x - self._buttons_width() - 12)
        label = self.chapter + (f" · {self.lesson}" if self.lesson else "")
        label = fm.elidedText(label, Qt.TextElideMode.ElideRight, int(room - 62))
        w2 = fm.horizontalAdvance(label) + 62
        r2 = QRectF(x, 2, w2, 40)
        draw_nine(p, self.assets, "ui_titlebar", r2)
        draw_sprite(p, self.assets, "icon_chapter", x + 12, 10)
        p.drawText(QPointF(x + 44, 22 + fm.ascent() / 2 - 2), label)

    def _buttons_width(self):
        return sum(b.sizeHint().width() + 6 for b in (self.btn_lessons, self.btn_catalog, self.btn_xray,
                                                      self.btn_note, self.btn_folder, self.btn_sound))


class InfoWindow(PixelWindow):
    """Окно с текстом и кнопками (письмо, разбор решения, «В жизни», блокнот…)."""

    def __init__(self, assets, title, icon, html_text, buttons, width=640, code=None, parent=None, portrait=None):
        super().__init__(assets, title, icon=icon, parent=parent, closable=False, resizable=False)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 8, 0)
        label = text_label(html_text, 18, TEXT)
        if portrait:
            prow = QHBoxLayout()
            pic = QLabel()
            pic.setPixmap(sprite_pixmap(assets, portrait, 2))
            prow.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)
            prow.addWidget(label, 1)
            il.addLayout(prow)
        else:
            il.addWidget(label)
        if code:
            ed = CodeEditor(assets)
            ed.setReadOnly(True)
            ed.setPlainText(code)
            ed.setFixedHeight((code.count("\n") + 1) * ed.fontMetrics().lineSpacing() + 18)
            il.addWidget(ed)
        il.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.buttons = []
        for text, icon, kind, callback in buttons:
            b = PixelButton(assets, text, icon, kind)
            b.clicked.connect(callback)
            row.addWidget(b)
            self.buttons.append(b)
        lay.addLayout(row)
        label.adjustSize()
        height = min(720, max(300 if not portrait else 320, label.sizeHint().height() + (ed.height() if code else 0) + 170))
        self.resize(width, height)


class NewGameWindow(PixelWindow):
    done = Signal(str, bool)

    def __init__(self, assets, parent=None):
        super().__init__(assets, "Новая игра", icon="icon_chapter", parent=parent, closable=False, resizable=False)
        lay = QVBoxLayout(self.body)
        lay.setSpacing(12)
        lay.addWidget(text_label("Ферма «Осенний Лог» достаётся бабушкиному внуку или внучке. Кто ты?", 18, TEXT))
        row = QHBoxLayout()
        self.female = False
        self.b_m = PixelButton(assets, "Внук", kind="primary")
        self.b_f = PixelButton(assets, "Внучка", kind="wood")
        self.b_m.clicked.connect(lambda: self._pick(False))
        self.b_f.clicked.connect(lambda: self._pick(True))
        row.addWidget(self.b_m)
        row.addWidget(self.b_f)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(text_label("Как тебя зовут?", 18, TEXT))
        self.name = QLineEdit()
        self.name.setFont(ui_font(20))
        self.name.setMaxLength(20)
        self.name.setPlaceholderText("Имя")
        self.name.setStyleSheet("background:#f8eed4; color:#3d2318; border:3px solid #95603a; padding:6px;")
        lay.addWidget(self.name)
        go = PixelButton(assets, "Начать", "icon_play", "primary")
        go.clicked.connect(self._go)
        self.name.returnPressed.connect(self._go)
        lay.addWidget(go, 0, Qt.AlignmentFlag.AlignRight)
        self.resize(520, 330)

    def _pick(self, female):
        self.female = female
        self.b_m.kind = "wood" if female else "primary"
        self.b_f.kind = "primary" if female else "wood"
        self.b_m.update()
        self.b_f.update()

    def _go(self):
        name = self.name.text().strip() or ("Внучка" if self.female else "Внук")
        self.done.emit(name, self.female)


class TitleScreen(QWidget):
    new_game = Signal()
    continue_game = Signal()

    PANEL = (640, 420)

    def __init__(self, assets, parent, can_continue):
        super().__init__(parent)
        self.assets = assets
        self.buttons = []
        if can_continue:
            b = PixelButton(assets, "Продолжить", "icon_play", "primary", self)
            b.clicked.connect(self.continue_game)
            self.buttons.append(b)
        b2 = PixelButton(assets, "Новая игра", "icon_chapter", "wood" if can_continue else "primary", self)
        b2.clicked.connect(self.new_game)
        self.buttons.append(b2)
        self.setGeometry(parent.rect())

    def _panel(self):
        w, h = self.PANEL
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def resizeEvent(self, e):
        panel = self._panel()
        y = panel.y() + 290 - len(self.buttons) * 27
        for b in self.buttons:
            b.setGeometry(int(panel.x() + 280), int(y), 300, 44)
            y += 54

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 15, 20, 120))
        panel = self._panel()
        draw_nine(p, self.assets, "ui_window_wood", panel)
        p.setFont(title_font(36))
        text = "РОБОФЕРМА"
        fm = p.fontMetrics()
        x = panel.center().x() - fm.horizontalAdvance(text) / 2
        y = panel.y() + 92
        p.setPen(QColor("#95603a"))
        p.drawText(QPointF(x + 4, y + 4), text)
        p.setPen(QColor("#c0392b"))
        p.drawText(QPointF(x, y), text)
        p.setFont(ui_font(20))
        sub = "Бабушкина ферма на Python"
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(panel.center().x() - p.fontMetrics().horizontalAdvance(sub) / 2, y + 44), sub)
        p.setPen(QColor(MUTED))
        tip = "Учись программировать на настоящем Python"
        p.drawText(QPointF(panel.center().x() - p.fontMetrics().horizontalAdvance(tip) / 2, y + 76), tip)
        k = self.assets["klusha_portrait_proud"].frame()
        p.drawImage(QRectF(panel.x() + 56, panel.y() + 196, 192, 192), k)


class _ListWindow(PixelWindow):
    """Окно со списком строк и кнопкой «Закрыть» (основа для списка уроков и каталога)."""

    closed_by_user = Signal()

    def __init__(self, assets, title, icon, width=680, height=640, parent=None):
        super().__init__(assets, title, icon=icon, parent=parent, closable=False, resizable=False)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        self.rows = QVBoxLayout(inner)
        self.rows.setContentsMargins(0, 0, 10, 0)
        self.rows.setSpacing(6)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        self.footer = text_label("", 15, MUTED)
        bottom.addWidget(self.footer, 1)
        close = PixelButton(assets, "Закрыть", "icon_close", "primary")
        close.clicked.connect(self.closed_by_user)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        self.resize(width, height)

    def add_header(self, text):
        lab = text_label(text, 19, TEXT, bold=True)
        lab.setContentsMargins(0, 8, 0, 0)
        self.rows.addWidget(lab)

    def add_row(self, icon, text, button=None):
        row = QHBoxLayout()
        row.setSpacing(10)
        if icon:
            pic = QLabel()
            pic.setPixmap(sprite_pixmap(self.assets, icon, 2, fit=64))
            pic.setFixedWidth(64)
            pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(pic, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(text_label(text, 16, TEXT), 1)
        if button:
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.rows.addLayout(row)


class LessonListWindow(_ListWindow):
    """Все главы и уроки: пройденные можно повторить в любой момент."""

    picked = Signal(int)

    def __init__(self, assets, chapters, lessons, done, max_lesson, current, parent=None):
        super().__init__(assets, "Уроки", "icon_map", parent=parent)
        for ch in chapters:
            self.add_header(f"Глава {ch.number}. {html.escape(ch.title)}")
            for lesson in ch.lessons:
                i = lessons.index(lesson)
                opened = i <= max_lesson
                if lesson.id in done:
                    icon = "icon_check"
                elif i == current:
                    icon = "icon_play"
                else:
                    icon = "icon_step" if opened else None
                text = f"<b>Урок {i + 1}. {html.escape(lesson.title)}</b> — {html.escape(lesson.topic)}"
                if not opened:
                    text = f"<span style='color:{MUTED};'>Урок {i + 1}. {html.escape(lesson.title)} — откроется позже</span>"
                    self.add_row(icon, text)
                    continue
                b = PixelButton(assets, "Открыть" if i != current else "Сейчас", kind="primary" if i == current else "wood")
                b.clicked.connect(lambda _=False, i=i: self.picked.emit(i))
                self.add_row(icon, text, b)
        self.rows.addStretch(1)
        self.footer.setText(f"Пройдено уроков: {len(done)} из {len(lessons)}")


class CatalogWindow(_ListWindow):
    """Бабушкин каталог: украшения фермы за монеты."""

    bought = Signal(str)

    def __init__(self, assets, catalog, coins, flags, parent=None):
        super().__init__(assets, "Бабушкин каталог", "icon_coins", width=700, parent=parent)
        self.add_row(None, "<i>Монеты приносят задания и роботы, которые работают сами каждый игровой день. "
                           "Их можно потратить на украшения фермы.</i>")
        for d in catalog:
            text = f"<b>{html.escape(d.title)}</b><br>{html.escape(d.text)}"
            if flags.get(d.flag):
                b = PixelButton(assets, "Куплено", "icon_check", "wood")
                b.setEnabled(False)
            else:
                b = PixelButton(assets, f"{d.price}", "icon_coin", "primary" if coins >= d.price else "wood",
                                tooltip="Купить" if coins >= d.price else "Не хватает монет")
                b.setEnabled(coins >= d.price)
                b.clicked.connect(lambda _=False, i=d.id: self.bought.emit(i))
            self.add_row(d.preview, text, b)
        self.rows.addStretch(1)
        self.footer.setText(f"У тебя {coins} монет")
