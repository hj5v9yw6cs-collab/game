"""Базовые пиксельные элементы интерфейса: 9-slice, кнопки, окна, модальные окна, тосты."""

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QLabel, QVBoxLayout, QWidget

from robofarm.sound import play
from robofarm.ui.fonts import ui_font

UI = 2  # один пиксель спрайта = 2 логических пикселя экрана (на Retina — 4 физических)


def draw_nine(p, assets, nine_id, rect, scale=UI):
    n = assets.nine[nine_id]
    src = assets[n["sprite"]].frame()
    l, t, r, b = n["slice"]
    sw, sh = src.width(), src.height()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    L, T, R, B = l * scale, t * scale, r * scale, b * scale
    cols = [(0, l, x, L), (l, sw - l - r, x + L, w - L - R), (sw - r, r, x + w - R, R)]
    rows = [(0, t, y, T), (t, sh - t - b, y + T, h - T - B), (sh - b, b, y + h - B, B)]
    for sy, shh, dy, dh in rows:
        for sx, sww, dx, dw in cols:
            if sww > 0 and shh > 0 and dw > 0 and dh > 0:
                p.drawImage(QRectF(dx, dy, dw, dh), src, QRectF(sx, sy, sww, shh))


def draw_sprite(p, assets, sid, x, y, scale=UI, t_ms=0, mirror=False):
    img = assets[sid].frame(t_ms)
    if mirror:
        img = img.mirrored(True, False)
    p.drawImage(QRectF(x, y, img.width() * scale, img.height() * scale), img)
    return img.width() * scale, img.height() * scale


class PixelButton(QAbstractButton):
    """Пиксельная кнопка: kind = primary (зелёная), wood, danger (красная)."""

    def __init__(self, assets, text="", icon=None, kind="wood", parent=None, tooltip=None):
        super().__init__(parent)
        self.assets = assets
        self.kind = kind
        self.icon_id = icon
        self.setText(text)
        self.setFont(ui_font(16, bold=True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover = False
        self.clicked.connect(lambda: play("click"))
        if tooltip:
            self.setToolTip(tooltip)

    def sizeHint(self):
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.text()) if self.text() else 0
        if self.icon_id:
            w += 24 + (8 if self.text() else 0)
        return QSize(max(40, w + 28), 38)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        if not self.isEnabled():
            state = "disabled"
        elif self.isDown():
            state = "pressed"
        elif self._hover:
            state = "hover"
        else:
            state = "normal"
        draw_nine(p, self.assets, f"ui_btn_{self.kind}_{state}", QRectF(self.rect()))
        dy = 2 if state == "pressed" else 0
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text()) if self.text() else 0
        total = tw + (24 if self.icon_id else 0) + (8 if self.icon_id and self.text() else 0)
        x = (self.width() - total) / 2
        cy = self.height() / 2 - 2 + dy
        if self.icon_id:
            p.setOpacity(1.0 if self.isEnabled() else 0.5)
            draw_sprite(p, self.assets, self.icon_id, x, cy - 12)
            p.setOpacity(1.0)
            x += 32 if self.text() else 24
        if self.text():
            color = QColor(self.assets.colors["ui"]["textOnWood"])
            if not self.isEnabled():
                color.setAlpha(140)
            p.setPen(QColor(0, 0, 0, 90))
            p.drawText(QPointF(x + 1, cy + fm.ascent() / 2 - 1 + 1), self.text())
            p.setPen(color)
            p.drawText(QPointF(x, cy + fm.ascent() / 2 - 1), self.text())


class _TitleButton(QAbstractButton):
    def __init__(self, assets, icon, parent):
        super().__init__(parent)
        self.assets, self.icon_id = assets, icon
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: play("click"))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setOpacity(0.7 if self.isDown() else 1.0)
        draw_sprite(p, self.assets, self.icon_id, 1, 1)


class PixelWindow(QWidget):
    """Плавающее окно поверх мира: деревянная рамка, табличка-заголовок, перетаскивание, сворачивание."""

    closed = Signal()
    TITLE_H = 34

    def __init__(self, assets, title, icon=None, dark=False, parent=None, closable=True, resizable=True):
        super().__init__(parent)
        self.assets = assets
        self.title = title
        self.icon_id = icon
        self.dark = dark
        self.resizable = resizable
        self.collapsed = False
        self._full_height = None
        self._drag = None
        self._resize = None
        self.setMouseTracking(True)
        self.body = QWidget(self)
        self.body.setObjectName("windowBody")
        self.btn_min = _TitleButton(assets, "icon_minimize", self)
        self.btn_min.clicked.connect(self.toggle_collapse)
        self.btn_close = _TitleButton(assets, "icon_close", self) if closable else None
        if self.btn_close:
            self.btn_close.clicked.connect(self._close)
        self.setMinimumSize(220, 120)

    def _close(self):
        self.hide()
        self.closed.emit()

    def content_rect(self):
        return QRect(20, 14 + self.TITLE_H + 6, self.width() - 40, self.height() - (14 + self.TITLE_H + 6) - 18)

    def resizeEvent(self, e):
        r = self.content_rect()
        self.body.setGeometry(r)
        self.body.setVisible(not self.collapsed)
        x = self.width() - 20 - 26
        if self.btn_close:
            self.btn_close.move(x, 18)
            x -= 30
        self.btn_min.move(x, 18)

    def toggle_collapse(self):
        if self.collapsed:
            self.collapsed = False
            self.resize(self.width(), self._full_height or 300)
        else:
            self._full_height = self.height()
            self.collapsed = True
            self.setMinimumHeight(0)
            self.resize(self.width(), 14 + self.TITLE_H + 20)
        self.body.setVisible(not self.collapsed)
        if not self.collapsed:
            self.setMinimumHeight(120)

    def paintEvent(self, e):
        p = QPainter(self)
        draw_nine(p, self.assets, "ui_window_code" if self.dark else "ui_window_wood", QRectF(self.rect()))
        bar = QRectF(14, 14, self.width() - 28, self.TITLE_H)
        draw_nine(p, self.assets, "ui_titlebar", bar)
        x = bar.x() + 10
        if self.icon_id:
            draw_sprite(p, self.assets, self.icon_id, x, bar.y() + 1)
            x += 38
        p.setFont(ui_font(18, bold=True))
        p.setPen(QColor(self.assets.colors["ui"]["text"]))
        fm = p.fontMetrics()
        p.drawText(QPointF(x, bar.y() + bar.height() / 2 + fm.ascent() / 2 - 2), self.title)
        if self.resizable and not self.collapsed:
            p.setOpacity(0.6)
            draw_sprite(p, self.assets, "icon_grip", self.width() - 34, self.height() - 34)

    # --- перетаскивание и изменение размера ---
    def mousePressEvent(self, e):
        self.raise_()
        pos = e.position().toPoint()
        if self.resizable and not self.collapsed and pos.x() > self.width() - 30 and pos.y() > self.height() - 30:
            self._resize = (e.globalPosition().toPoint(), self.size())
        elif pos.y() < 14 + self.TITLE_H + 6:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            new = e.globalPosition().toPoint() - self._drag
            par = self.parentWidget()
            if par:
                new.setX(max(-self.width() + 120, min(par.width() - 120, new.x())))
                new.setY(max(0, min(par.height() - 50, new.y())))
            self.move(new)
        elif self._resize is not None:
            start, size = self._resize
            d = e.globalPosition().toPoint() - start
            self.resize(max(self.minimumWidth(), size.width() + d.x()), max(self.minimumHeight(), size.height() + d.y()))
        else:
            pos = e.position().toPoint()
            corner = self.resizable and pos.x() > self.width() - 30 and pos.y() > self.height() - 30
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if corner else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self._resize = None


def text_label(text, size=16, color="#3d2318", bold=False, wrap=True, rich=True):
    lab = QLabel(text)
    lab.setFont(ui_font(size, bold))
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


class Modal(QWidget):
    """Затемнение поверх всей игры с окном по центру."""

    def __init__(self, assets, parent, window):
        super().__init__(parent)
        self.assets = assets
        self.window = window
        window.setParent(self)
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        window.show()
        self._layout()

    def _layout(self):
        w = self.window
        w.move((self.width() - w.width()) // 2, max(20, (self.height() - w.height()) // 2))

    def resizeEvent(self, e):
        self._layout()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(18, 12, 26, 150))

    def mousePressEvent(self, e):
        e.accept()


class Toast(QWidget):
    """Короткое уведомление сверху по центру."""

    def __init__(self, assets, parent, text, icon=None, seconds=3.0):
        super().__init__(parent)
        self.assets, self.text, self.icon_id = assets, text, icon
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        f = ui_font(17, bold=True)
        self.setFont(f)
        w = self.fontMetrics().horizontalAdvance(text) + (70 if icon else 44)
        self.resize(w, 48)
        self.move((parent.width() - w) // 2, 64)
        self.show()
        self.raise_()
        QTimer.singleShot(int(seconds * 1000), self.deleteLater)

    def paintEvent(self, e):
        p = QPainter(self)
        draw_nine(p, self.assets, "ui_toast", QRectF(self.rect()))
        x = 22
        if self.icon_id:
            draw_sprite(p, self.assets, self.icon_id, x, 12)
            x += 32
        p.setPen(QColor(self.assets.colors["ui"]["text"]))
        p.drawText(QPointF(x, 24 + self.fontMetrics().ascent() / 2 - 1), self.text)
