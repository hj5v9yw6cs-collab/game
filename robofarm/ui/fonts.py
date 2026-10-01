"""Шрифты игры.

PT Sans — весь текст интерфейса: объяснения, кнопки, диалоги (сделан для русского языка, отлично читается).
PT Mono — код, как в настоящем редакторе.
Press Start 2P — только логотип.
"""

from PySide6.QtGui import QFont, QFontDatabase

from robofarm.assets import DATA_DIR

UI_FAMILY = "PT Sans"
CODE_FAMILY = "PT Mono"
TITLE_FAMILY = "Press Start 2P"

FONT_FILES = ("PTSans-Regular.ttf", "PTSans-Bold.ttf", "PTMono-Regular.ttf", "PressStart2P-Regular.ttf")


def load_fonts():
    for name in FONT_FILES:
        QFontDatabase.addApplicationFont(str(DATA_DIR / "fonts" / name))


def ui_font(size=17, bold=False):
    f = QFont(UI_FAMILY)
    f.setPixelSize(int(size))
    if bold:
        f.setBold(True)
    return f


CODE_SIZES = {1: 14, 2: 19, 3: 26}


def code_font(scale=2):
    f = QFont(CODE_FAMILY)
    f.setPixelSize(CODE_SIZES.get(scale, 17))
    f.setFixedPitch(True)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def title_font(size=20):
    f = QFont(TITLE_FAMILY)
    f.setPixelSize(size)
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    return f
