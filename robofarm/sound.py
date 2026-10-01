"""Звуки и музыка.

На Mac звук играет встроенная утилита afplay (ничего не нужно устанавливать),
на Linux — paplay/aplay, на Windows — winsound. Если ничего нет, игра просто молчит.
"""

import random
import shutil
import subprocess
import sys

from PySide6.QtCore import QObject, QTimer

from robofarm.assets import DATA_DIR

SOUNDS = DATA_DIR / "sounds"


class SoundManager(QObject):
    MAX_EFFECTS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.effects_on = True
        self.music_on = True
        self.volume = 0.7
        self.music_volume = 0.35
        self._procs = []
        self._music = None
        self._player = None
        if sys.platform == "darwin" and shutil.which("afplay"):
            self._player = "afplay"
        elif sys.platform.startswith("linux"):
            self._player = "paplay" if shutil.which("paplay") else ("aplay" if shutil.which("aplay") else None)
        elif sys.platform == "win32":
            self._player = "winsound"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._housekeeping)
        self._timer.start(1000)

    def available(self):
        return self._player is not None

    def _spawn(self, path, volume):
        if self._player == "afplay":
            return subprocess.Popen(["afplay", "-v", f"{volume:.2f}", str(path)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self._player == "paplay":
            vol = str(int(65536 * volume))
            return subprocess.Popen(["paplay", f"--volume={vol}", str(path)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self._player == "aplay":
            return subprocess.Popen(["aplay", "-q", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self._player == "winsound":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return None

    def play(self, name, volume=1.0):
        """Короткий эффект: click, water, coin… Имя с цифрой-вариантом выбирается случайно: voice_klusha."""
        if not self.effects_on or not self._player:
            return
        path = SOUNDS / f"{name}.wav"
        if not path.exists():
            variants = sorted(SOUNDS.glob(f"{name}_*.wav"))
            if not variants:
                return
            path = random.choice(variants)
        self._procs = [p for p in self._procs if p.poll() is None]
        if len(self._procs) >= self.MAX_EFFECTS:
            return
        try:
            proc = self._spawn(path, self.volume * volume)
        except OSError:
            self._player = None
            return
        if proc:
            self._procs.append(proc)

    def start_music(self):
        if not self.music_on or not self._player or self._player == "winsound":
            return
        if self._music and self._music.poll() is None:
            return
        try:
            self._music = self._spawn(SOUNDS / "music_autumn.wav", self.music_volume)
        except OSError:
            self._music = None

    def stop_music(self):
        if self._music and self._music.poll() is None:
            self._music.terminate()
        self._music = None

    def set_enabled(self, on):
        self.effects_on = on
        self.music_on = on
        if on:
            self.start_music()
        else:
            self.stop_music()

    def _housekeeping(self):
        self._procs = [p for p in self._procs if p.poll() is None]
        if self.music_on and self._music is not None and self._music.poll() is not None:
            self._music = None
            self.start_music()  # мелодия по кругу

    def shutdown(self):
        self.stop_music()
        for p in self._procs:
            if p.poll() is None:
                p.terminate()


_manager = None


def sounds():
    global _manager
    if _manager is None:
        _manager = SoundManager()
    return _manager


def play(name, volume=1.0):
    sounds().play(name, volume)
