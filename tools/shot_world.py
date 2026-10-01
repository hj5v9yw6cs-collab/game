"""Снимок мира без интерфейса: python3 tools/shot_world.py out.png [xray]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from robofarm.assets import Assets
from robofarm.farm import make_bed
from robofarm.ui.fonts import load_fonts
from robofarm.world.view import WorldView

app = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
load_fonts()
v = WorldView(Assets())
v.resize(1440, 900)
v.set_beds([make_bed("морковь", "морковь", 26, 12, humidity=20), make_bed("тыква", "тыква", 29, 12, humidity=80),
            make_bed("капуста", "капуста", 32, 12, stage="growing", humidity=10)])
v.set_flag("shed_repaired", "repaired" in sys.argv); v.set_flag("house_repaired", "repaired" in sys.argv)
b = v.add_robot("bublik", *v.bed_stand_point("тыква"), "left"); b.anim = "water"; b.rest_anim = "water"
k = v.add_robot("klusha", *v.map.spots["shed_door"]); k.rest_anim = "talk"; k.say("Ко-ко! Полей тыкву!", 99)
v.active_robot = "bublik"
v.xray = "xray" in sys.argv
if "hover" in sys.argv:
    v.hover = v._hit(*v.bed_center("капуста")); v.hover_pos = v.world_to_screen(*v.bed_center("капуста")).toPoint()
for _ in range(40):
    v._tick()
v.grab().save(sys.argv[1]); print("saved", sys.argv[1])
