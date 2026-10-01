"""Пиксельные шрифты игры.

Tiny5 — текст интерфейса (чёткая кириллица, рисован на сетке 10 px, поэтому размеры 10/20/30).
Klusha Mono — код (собран из глифов Claude Design, сетка 12 px).
Press Start 2P — логотип и крупные заголовки.
"""

from PySide6.QtGui import QFont, QFontDatabase

from robofarm.assets import DATA_DIR

UI_FAMILY = "Tiny5"
CODE_FAMILY = "Klusha Mono"
TITLE_FAMILY = "Press Start 2P"


def load_fonts():
    for name in ("Tiny5-Regular.ttf", "KlushaMono.ttf", "PressStart2P-Regular.ttf"):
        QFontDatabase.addApplicationFont(str(DATA_DIR / "fonts" / name))


def _snap(size):
    """Пиксельный шрифт чёткий только на кратных размерах."""
    if size < 14:
        return 10
    if size <= 24:
        return 20
    return 30


def ui_font(size=20, bold=False):
    f = QFont(UI_FAMILY)
    f.setPixelSize(_snap(size))
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def code_font(scale=2):
    f = QFont(CODE_FAMILY)
    f.setPixelSize(12 * scale)
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setFixedPitch(True)
    return f


def title_font(size=20):
    f = QFont(TITLE_FAMILY)
    f.setPixelSize(size)
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    return f
