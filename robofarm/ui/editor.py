"""Редактор кода в пиксельном стиле: подсветка, номера строк, текущая строка, ошибки, пропуски."""

import re

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                           QTextFormat)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QToolTip, QWidget

from robofarm.farm import mixed_script
from robofarm.ui.fonts import code_font
from robofarm.ui.pixel import UI, draw_sprite

KEYWORDS = {"for", "in", "if", "elif", "else", "while", "def", "return", "import", "from", "as", "and", "or",
            "not", "True", "False", "None", "break", "continue", "pass", "with", "try", "except", "class",
            "lambda", "is", "global"}
BUILTINS = {"print", "len", "range", "int", "str", "float", "list", "dict", "sum", "max", "min", "sorted",
            "round", "abs", "input", "open", "enumerate", "type", "bool", "set", "zip", "isinstance"}
ROBOT_COMMANDS = {"полить", "собрать", "water", "harvest", "sell", "tag", "deliver"}

TRANSLATIONS = {
    "print": "print — «напечатать»: показать текст или значение",
    "for": "for — «для каждого»: повторить для каждого элемента",
    "in": "in — «в»: из какого набора брать элементы",
    "if": "if — «если»: выполнить, только если условие верно",
    "else": "else — «иначе»: что делать, если условие неверно",
    "elif": "elif — «иначе если»",
    "while": "while — «пока»: повторять, пока условие верно",
    "def": "def — «определить»: создать свою команду (функцию)",
    "return": "return — «вернуть»: отдать результат функции",
    "True": "True — «правда», да",
    "False": "False — «ложь», нет",
    "None": "None — «ничего», пустое значение",
    "and": "and — «и»: оба условия верны",
    "or": "or — «или»: хотя бы одно верно",
    "not": "not — «не»: наоборот",
    "len": "len — «длина»: сколько элементов",
    "range": "range — «диапазон»: числа по порядку",
    "int": "int — «целое число»",
    "str": "str — «строка», текст",
    "float": "float — «дробное число»: 2.5",
    "sum": "sum — «сумма» всех чисел списка",
    "max": "max — «самое большое»",
    "min": "min — «самое маленькое»",
    "sorted": "sorted — «отсортированный»: новый список по порядку",
    "round": "round — «округлить»",
    "open": "open — «открыть» файл",
    "with": "with — «с»: открыть файл и сам закрыть его в конце блока",
    "as": "as — «как»: под каким именем",
    "import": "import — «подключить» модуль (готовый набор команд)",
    "from": "from — «из»: из какого модуля взять",
    "try": "try — «попробовать»: выполнить, а при ошибке не падать",
    "except": "except — «кроме», «на случай ошибки»: что делать, если случилась ошибка",
    "enumerate": "enumerate — «пронумеровать»: даёт номер и элемент",
    "break": "break — «прервать» цикл",
    "continue": "continue — «продолжить»: сразу к следующему кругу цикла",
    "pass": "pass — «ничего не делать»",
    "dict": "dict — «словарь»: ключ → значение",
    "list": "list — «список»",
    "полить": "полить(грядка) — робот поливает грядку",
    "собрать": "собрать(грядка) — робот собирает урожай и возвращает килограммы",
    "water": "water(bed) — полить грядку",
    "harvest": "harvest(bed) — собрать урожай, возвращает килограммы",
    "sell": "sell(customer, total) — Мурзик продаёт покупателю на сумму total",
    "tag": "tag(text) — Мурзик вешает ценник с текстом на прилавок",
    "deliver": "deliver(id) — Искра отвозит заказ с этим номером",
    "field": "field — «поле»: список грядок",
    "bed": "bed — «грядка»",
    "price": "price — «цена»",
    "prices": "prices — «цены»",
    "total": "total — «итого», сумма",
    "customer": "customer — «покупатель»",
    "queue": "queue — «очередь»: список покупателей",
    "item": "item — «товар», «предмет»",
    "order": "order — «заказ»",
    "orders": "orders — «заказы»",
    "line": "line — «строка»",
    "row": "row — «строка таблицы»",
    "text": "text — «текст»",
    "name": "name — «имя», «название»",
    "count": "count — «количество», «счётчик»",
    "path": "path — «путь» к файлу или папке",
    "folder": "folder — «папка»",
    "report": "report — «отчёт»",
    "stock": "stock — «запас», остатки на складе",
    "weather": "weather — «погода»",
}

TOKEN_RE = re.compile(
    r"(?P<comment>#.*)|(?P<string>\"[^\"\n]*\"?|'[^'\n]*'?)|(?P<blank>_{3,})|(?P<number>\b\d+(?:\.\d+)?\b)"
    r"|(?P<word>[^\W\d]\w*)|(?P<op>[=+\-*/<>%!]+)|(?P<bracket>[()\[\]{}:,.])")


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, colors):
        super().__init__(document)
        c = colors

        def fmt(color, bold=False, bg=None):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bg:
                f.setBackground(QColor(bg))
            return f

        self.f = {
            "keyword": fmt(c["keyword"]), "builtin": fmt(c["builtin"]), "robot": fmt(c["robotCommand"]),
            "function": fmt(c["function"]), "string": fmt(c["string"]), "number": fmt(c["number"]),
            "comment": fmt(c["comment"]), "op": fmt(c["operator"]), "bracket": fmt(c["bracket"]),
            "blank": fmt(c["background"], bg=c["blankSlot"]),
        }
        sus = QTextCharFormat()
        sus.setForeground(QColor(c["suspiciousChar"]))
        sus.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        sus.setUnderlineColor(QColor(c["suspiciousChar"]))
        self.f["suspicious"] = sus

    def highlightBlock(self, text):
        for m in TOKEN_RE.finditer(text):
            kind = m.lastgroup
            start, length = m.start(), m.end() - m.start()
            if kind == "word":
                word = m.group()
                if mixed_script(word):
                    self.setFormat(start, length, self.f["suspicious"])
                elif word in KEYWORDS:
                    self.setFormat(start, length, self.f["keyword"])
                elif word in ROBOT_COMMANDS:
                    self.setFormat(start, length, self.f["robot"])
                elif word in BUILTINS:
                    self.setFormat(start, length, self.f["builtin"])
                elif m.end() < len(text) and text[m.end()] == "(":
                    self.setFormat(start, length, self.f["function"])
            elif kind in self.f:
                self.setFormat(start, length, self.f[kind])


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, e):
        self.editor.paint_gutter(e)


class CodeEditor(QPlainTextEdit):
    run_requested = Signal()

    def __init__(self, assets, scale=UI, parent=None):
        super().__init__(parent)
        self.assets = assets
        self.colors = assets.colors["syntax"]
        self.exec_line = None
        self.error_line = None
        self.scale = scale
        self.setFont(code_font(scale))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        c = self.colors
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {c['background']}; color: {c['foreground']}; border: none;"
            f" selection-background-color: {c['selection']}; selection-color: {c['foreground']}; }}"
            f"QScrollBar {{ background: {c['gutter']}; width: 10px; height: 10px; }}"
            f"QScrollBar::handle {{ background: {c['lineNumber']}; min-height: 20px; min-width: 20px; }}"
            f"QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}")
        self.highlighter = PythonHighlighter(self.document(), c)
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_margins)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._refresh_selections)
        self.setMouseTracking(True)
        self._update_margins()
        self.setCursorWidth(scale * 2)

    # --- поле с номерами строк ---
    def gutter_width(self):
        digits = max(2, len(str(self.blockCount())))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits + 10

    def _update_margins(self, *_):
        self.setViewportMargins(self.gutter_width(), 4, 0, 4)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, e):
        p = QPainter(self.gutter)
        p.fillRect(e.rect(), QColor(self.colors["gutter"]))
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top()) + 4
        fm = self.fontMetrics()
        while block.isValid() and top <= e.rect().bottom():
            bottom = top + round(self.blockBoundingRect(block).height())
            n = block.blockNumber() + 1
            if block.isVisible():
                active = n == self.exec_line or n == self.error_line
                p.setPen(QColor(self.colors["foreground"] if active else self.colors["lineNumber"]))
                p.setFont(self.font())
                p.drawText(QRect(0, top, self.gutter.width() - 8, fm.height()),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(n))
                icon_y = top + (fm.height() - 16) / 2
                if n == self.error_line:
                    draw_sprite(p, self.assets, "ui_gutter_error", 3, icon_y)
                elif n == self.exec_line:
                    draw_sprite(p, self.assets, "ui_line_arrow", 3, icon_y)
            block = block.next()
            top = bottom

    # --- подсветка строк ---
    def set_exec_line(self, line):
        self.exec_line = line
        self._refresh_selections()
        if line:
            block = self.document().findBlockByNumber(line - 1)
            if block.isValid():
                cur = QTextCursor(block)
                self.setTextCursor(cur)
                self.ensureCursorVisible()
        self.gutter.update()

    def set_error_line(self, line):
        self.error_line = line
        self._refresh_selections()
        self.gutter.update()

    def _line_selection(self, line, color):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(color))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        block = self.document().findBlockByNumber(line - 1)
        sel.cursor = QTextCursor(block)
        sel.cursor.clearSelection()
        return sel

    def _refresh_selections(self):
        sels = []
        if self.error_line:
            sels.append(self._line_selection(self.error_line, self.colors["errorLine"]))
        if self.exec_line:
            sels.append(self._line_selection(self.exec_line, self.colors["currentLine"]))
        self.setExtraSelections(sels)

    def select_first_blank(self):
        cur = self.document().find("____")
        if not cur.isNull():
            self.setTextCursor(cur)
            self.setFocus()
            return True
        return False

    # --- клавиатура ---
    def keyPressEvent(self, e):
        key, mods = e.key(), e.modifiers()
        ctrl = mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and ctrl:
            self.run_requested.emit()
            return
        if self.isReadOnly():
            return super().keyPressEvent(e)
        cur = self.textCursor()
        if key == Qt.Key.Key_Tab and not cur.hasSelection():
            cur.insertText("    ")
            return
        if key == Qt.Key.Key_Backtab or (key == Qt.Key.Key_Tab and cur.hasSelection()):
            self._shift_lines(key == Qt.Key.Key_Tab)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            line = cur.block().text()[:cur.positionInBlock()]
            indent = len(line) - len(line.lstrip(" "))
            if line.rstrip().endswith(":"):
                indent += 4
            cur.insertText("\n" + " " * indent)
            self.ensureCursorVisible()
            return
        if key == Qt.Key.Key_Backspace and not cur.hasSelection():
            before = cur.block().text()[:cur.positionInBlock()]
            if before and not before.strip() and len(before) % 4 == 0:
                for _ in range(4):
                    cur.deletePreviousChar()
                return
        super().keyPressEvent(e)

    def _shift_lines(self, right):
        cur = self.textCursor()
        start = self.document().findBlock(cur.selectionStart()).blockNumber()
        end = self.document().findBlock(cur.selectionEnd()).blockNumber()
        cur.beginEditBlock()
        for n in range(start, end + 1):
            block = self.document().findBlockByNumber(n)
            c = QTextCursor(block)
            if right:
                c.insertText("    ")
            else:
                spaces = len(block.text()) - len(block.text().lstrip(" "))
                for _ in range(min(4, spaces)):
                    c.deleteChar()
        cur.endEditBlock()

    # --- перевод слов при наведении ---
    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        cur = self.cursorForPosition(e.position().toPoint())
        cur.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cur.selectedText()
        if word in TRANSLATIONS:
            QToolTip.showText(e.globalPosition().toPoint(), TRANSLATIONS[word], self)
        elif mixed_script(word):
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"В слове «{word}» перемешаны русские и английские буквы — проверь раскладку", self)
        else:
            QToolTip.hideText()
