"""Запуск песочницы из игры: отдельный процесс, чтобы зависший код игрока не повесил окно."""

import json

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from robofarm import paths


class SandboxRunner(QObject):
    finished = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._kill)
        self._killed = False

    def busy(self):
        return self.proc is not None

    def run(self, payload, hard_timeout_ms=8000):
        if self.proc:
            return False
        cmd = paths.sandbox_command()
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(paths.farm_dir()))
        env = self.proc.processEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONPATH", str(paths.project_root()))
        self.proc.setProcessEnvironment(env)
        self.proc.finished.connect(self._done)
        self._killed = False
        self.proc.start(cmd[0], cmd[1:])
        self.proc.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.proc.closeWriteChannel()
        self.timer.start(hard_timeout_ms)
        return True

    def _kill(self):
        if self.proc:
            self._killed = True
            self.proc.kill()

    def _done(self, *_):
        self.timer.stop()
        proc, self.proc = self.proc, None
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        proc.deleteLater()
        try:
            result = json.loads(out)
        except ValueError:
            title = "программа зависла и была остановлена" if self._killed else "не удалось запустить код"
            result = {"events": [], "stdout": "", "warnings": [], "beds": None, "vars": {},
                      "error": {"type": "Crash", "message": err[-400:], "line": None, "title": title,
                                "hint": "Похоже на бесконечный цикл или очень долгую операцию. Проверь циклы.",
                                "trace": err[-1500:]}}
        self.finished.emit(result)
