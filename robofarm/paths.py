"""Где игра хранит сохранения и данные фермы."""

import os
import sys
from pathlib import Path

APP_NAME = "Робоферма"


def save_dir():
    if os.environ.get("ROBOFARM_HOME"):
        path = Path(os.environ["ROBOFARM_HOME"]) / "save"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / "robofarm"
    path.mkdir(parents=True, exist_ok=True)
    return path


def farm_dir():
    """Настоящая папка фермы: здесь лежат скрипты роботов (а позже — таблицы и файлы фермы)."""
    if os.environ.get("ROBOFARM_HOME"):
        path = Path(os.environ["ROBOFARM_HOME"]) / "farm"
    else:
        docs = Path.home() / "Documents"
        path = (docs if docs.exists() else Path.home()) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def sandbox_command():
    """Команда запуска песочницы: в собранном .app — сам бинарник с флагом, иначе — модуль."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--sandbox"]
    return [sys.executable, "-m", "robofarm.sandbox"]


def project_root():
    return Path(__file__).resolve().parents[1]
