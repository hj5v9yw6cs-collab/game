"""Робоферма — игра, в которой ты учишь Python на бабушкиной ферме.

Запуск:  python3 main.py
"""

import sys


def main():
    if "--sandbox" in sys.argv:
        # собранное приложение запускает само себя как песочницу для кода игрока
        from robofarm.sandbox.engine import main as sandbox_main
        sandbox_main()
        return
    from PySide6.QtWidgets import QApplication
    from robofarm.game import GameWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Робоферма")
    app.setStyleSheet("QToolTip { background: #f8eed4; color: #3d2318; border: 2px solid #95603a;"
                      " font-family: 'Tiny5'; font-size: 20px; padding: 4px; }")
    window = GameWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
