"""Лист всех спрайтов группы: python3 tools/contact_sheet.py <prefix-группы> out.png"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter
from robofarm.assets import Assets

app = QGuiApplication.instance() or QGuiApplication(["x", "-platform", "offscreen"])
a = Assets()
prefix, out = sys.argv[1], sys.argv[2]
ids = [s["id"] for s in a.data["sprites"] if s["group"].startswith(prefix)]
scale, cols = 2, 8
cell_w = max(a[i].size[0] for i in ids) * scale + 20
cell_h = max(a[i].size[1] for i in ids) * scale + 26
rows = (len(ids) + cols - 1) // cols
img = QImage(cols * cell_w, rows * cell_h, QImage.Format.Format_ARGB32)
img.fill(QColor("#c9783a"))
p = QPainter(img)
f = QFont(); f.setPixelSize(10); p.setFont(f)
for n, sid in enumerate(ids):
    x, y = (n % cols) * cell_w, (n // cols) * cell_h
    fr = a[sid].frame(0)
    p.drawImage(x + 10, y + 4, fr.scaled(fr.width() * scale, fr.height() * scale))
    p.setPen(QColor("#1a0f0a")); p.drawText(x + 4, y + cell_h - 6, sid)
p.end(); img.save(out); print(out, img.width(), img.height(), len(ids))
