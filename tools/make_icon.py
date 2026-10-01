"""Иконка приложения: Клуша на осеннем фоне. python3 tools/make_icon.py out.png"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath
from robofarm.assets import Assets

app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
a = Assets()
size = 1024
img = QImage(size, size, QImage.Format.Format_ARGB32)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
path = QPainterPath()
path.addRoundedRect(QRectF(100, 100, 824, 824), 185, 185)
g = QLinearGradient(0, 100, 0, 924)
g.setColorAt(0, QColor("#f6c56e"))
g.setColorAt(0.55, QColor("#e89a45"))
g.setColorAt(1, QColor("#a5522a"))
p.fillPath(path, g)
p.setClipPath(path)
p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
leaf = a["fx_leaf_fall_1"].frame()
for x, y in [(170, 190), (760, 230), (210, 700), (790, 690)]:
    p.drawImage(QRectF(x, y, 64, 64), leaf)
pumpkin = a["pumpkin_ripe"].frame()
p.drawImage(QRectF(560, 600, pumpkin.width() * 12, pumpkin.height() * 12), pumpkin)
klusha = a["klusha_portrait_proud"].frame()
p.drawImage(QRectF(160, 236, 640, 640), klusha)
p.end()
out = sys.argv[1] if len(sys.argv) > 1 else "icon.png"
Path(out).parent.mkdir(parents=True, exist_ok=True)
img.save(out)
print("saved", out)
