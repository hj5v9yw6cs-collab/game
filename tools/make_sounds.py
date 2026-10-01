"""Генерирует ретро-звуки и фоновую мелодию игры (WAV, 22 кГц, 16 бит).

    python3 tools/make_sounds.py

Все звуки синтезированы кодом — никаких сторонних файлов и лицензий.
"""

import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parents[1] / "robofarm" / "data" / "sounds"
rnd = random.Random(7)


def note(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    base, octave = name[0], int(name[-1])
    semis = names[base] + (1 if "#" in name else 0) - (1 if "b" in name[1:-1] else 0)
    return 440.0 * 2 ** ((semis + (octave - 4) * 12) / 12)


def osc(kind, phase):
    p = phase % 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * p)
    if kind == "square":
        return 1.0 if p < 0.5 else -1.0
    if kind == "pulse":
        return 1.0 if p < 0.25 else -1.0
    if kind == "tri":
        return 4 * abs(p - 0.5) - 1
    if kind == "saw":
        return 2 * p - 1
    return rnd.uniform(-1, 1)


def tone(freq, dur, kind="square", vol=0.5, attack=0.005, release=0.05, sweep=None, vibrato=0.0, buf=None, start=0.0):
    n = int(dur * RATE)
    out = buf if buf is not None else [0.0] * n
    s0 = int(start * RATE)
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = freq if sweep is None else freq + (sweep - freq) * (t / dur)
        if vibrato:
            f *= 1 + vibrato * math.sin(2 * math.pi * 6 * t)
        phase += f / RATE
        env = min(1.0, t / attack) if attack else 1.0
        if t > dur - release:
            env *= max(0.0, (dur - t) / release)
        if s0 + i < len(out):
            out[s0 + i] += osc(kind, phase) * vol * env
    return out


def noise(dur, vol=0.4, decay=4.0, lowpass=0.3):
    n = int(dur * RATE)
    out, prev = [], 0.0
    for i in range(n):
        prev += (rnd.uniform(-1, 1) - prev) * lowpass
        out.append(prev * vol * math.exp(-decay * i / RATE))
    return out


def mix(length, *parts):
    buf = [0.0] * int(length * RATE)
    for start, samples in parts:
        s0 = int(start * RATE)
        for i, v in enumerate(samples):
            if s0 + i < len(buf):
                buf[s0 + i] += v
    return buf


def save(name, samples, gain=0.9):
    peak = max(1e-6, max(abs(s) for s in samples))
    k = gain / peak if peak > gain else 1.0
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * k)) * 32000)) for s in samples))
    print("saved", name, round(len(samples) / RATE, 2), "s")


def sfx():
    save("click", tone(1250, 0.035, "pulse", 0.35, release=0.03))
    save("open", mix(0.16, (0, tone(660, 0.06, "square", 0.25)), (0.06, tone(990, 0.09, "square", 0.25))))
    save("page", noise(0.09, 0.35, 30, 0.5))
    for i, f in enumerate((780, 880, 980)):
        save(f"voice_klusha_{i + 1}", tone(f, 0.045, "tri", 0.45, release=0.03, sweep=f * 1.15))
    for i, f in enumerate((300, 340, 380)):
        save(f"voice_bublik_{i + 1}", tone(f, 0.06, "square", 0.25, release=0.04, sweep=f * 0.9))
    save("cluck", mix(0.32, (0, tone(900, 0.09, "square", 0.3, sweep=650, vibrato=0.03)),
                      (0.14, tone(950, 0.12, "square", 0.3, sweep=600, vibrato=0.03))))
    save("bark", mix(0.3, (0, noise(0.08, 0.35, 25, 0.6)), (0, tone(340, 0.16, "square", 0.35, sweep=170)),
                     (0.17, tone(300, 0.1, "square", 0.25, sweep=200))))
    save("water", mix(0.7, (0, noise(0.65, 0.5, 3.5, 0.25)),
                      *[(0.08 + i * 0.11, tone(500 + rnd.randint(0, 500), 0.05, "sine", 0.25, sweep=1200)) for i in range(5)]))
    save("harvest", mix(0.45, (0, tone(260, 0.09, "sine", 0.5, sweep=820)),
                        (0.1, tone(1568, 0.08, "square", 0.18)), (0.18, tone(2093, 0.08, "square", 0.16)),
                        (0.26, tone(2637, 0.15, "square", 0.14, release=0.12))))
    save("coin", mix(0.45, (0, tone(988, 0.07, "square", 0.3)), (0.07, tone(1319, 0.35, "square", 0.3, release=0.3))))
    save("success", mix(0.7, *[(i * 0.09, tone(note(n), 0.16 if i < 3 else 0.4, "pulse", 0.3, release=0.12))
                               for i, n in enumerate(["C5", "E5", "G5", "C6"])]))
    melody = [("C5", 0.0, 0.12), ("E5", 0.12, 0.12), ("G5", 0.24, 0.12), ("C6", 0.36, 0.24),
              ("G5", 0.6, 0.12), ("C6", 0.72, 0.6)]
    parts = [(st, tone(note(n), d, "square", 0.25, release=0.08)) for n, st, d in melody]
    parts += [(st, tone(note(n) / 2, d, "tri", 0.3, release=0.08)) for n, st, d in melody]
    save("quest", mix(1.45, *parts))
    save("error", mix(0.42, (0, tone(196, 0.16, "square", 0.3)), (0.18, tone(147, 0.22, "square", 0.3, release=0.15))))
    save("warn", mix(0.36, (0, tone(note("E5"), 0.12, "tri", 0.4)), (0.13, tone(note("C5"), 0.2, "tri", 0.4, release=0.15))))
    save("tick", tone(2200, 0.015, "pulse", 0.15, release=0.012))
    save("xray_on", tone(300, 0.4, "sine", 0.4, sweep=1500, vibrato=0.05))
    save("xray_off", tone(1500, 0.3, "sine", 0.35, sweep=300))
    save("power_on", mix(0.95, (0, tone(120, 0.6, "saw", 0.25, sweep=900)),
                         (0.55, tone(1760, 0.08, "square", 0.15)), (0.65, tone(2349, 0.25, "square", 0.15, release=0.2))))
    save("step", tone(660, 0.05, "tri", 0.3, release=0.04, sweep=880))
    # голоса новых роботов
    for i, f in enumerate((520, 580, 640)):
        save(f"voice_murzik_{i + 1}", tone(f, 0.07, "tri", 0.35, release=0.04, sweep=f * 1.3, vibrato=0.02))
    for i, f in enumerate((220, 250, 280)):
        save(f"voice_bobr_{i + 1}", tone(f, 0.06, "pulse", 0.3, release=0.04, sweep=f * 1.1))
    for i, f in enumerate((420, 470, 520)):
        save(f"voice_iskra_{i + 1}", tone(f, 0.06, "square", 0.22, release=0.04, sweep=f * 0.8, vibrato=0.03))
    for i, f in enumerate((380, 410, 440)):
        save(f"voice_uhta_{i + 1}", tone(f, 0.08, "sine", 0.45, release=0.05, sweep=f * 0.92))
    save("meow", mix(0.42, (0, tone(600, 0.36, "tri", 0.35, sweep=900, vibrato=0.02)),
                     (0.18, tone(880, 0.2, "tri", 0.25, sweep=520, release=0.15))))
    save("hoot", mix(0.6, (0, tone(392, 0.18, "sine", 0.5, sweep=370)), (0.26, tone(370, 0.3, "sine", 0.5, sweep=330))))
    save("neigh", mix(0.55, (0, tone(700, 0.5, "square", 0.18, sweep=420, vibrato=0.08)),
                      (0, noise(0.3, 0.15, 8, 0.5))))
    save("chomp", mix(0.3, (0, noise(0.06, 0.4, 30, 0.6)), (0.12, noise(0.06, 0.4, 30, 0.6))))
    save("sell", mix(0.6, (0, noise(0.05, 0.3, 40, 0.8)), (0.05, tone(1568, 0.08, "square", 0.25)),
                     (0.12, tone(2093, 0.4, "square", 0.22, release=0.35))))
    save("tag", mix(0.2, (0, noise(0.04, 0.5, 50, 0.4)), (0, tone(180, 0.08, "sine", 0.5, sweep=90))))
    save("paper", mix(0.25, (0, noise(0.12, 0.3, 20, 0.7)), (0.1, noise(0.1, 0.25, 25, 0.6))))
    save("write", mix(0.4, *[(i * 0.07, noise(0.05, 0.25, 40, 0.9)) for i in range(5)]))
    save("trot", mix(0.5, *[(i * 0.12, tone(300 + (i % 2) * 60, 0.04, "tri", 0.4, release=0.03)) for i in range(4)]))
    save("bell", mix(0.8, (0, tone(1760, 0.7, "sine", 0.3, release=0.6)), (0, tone(2637, 0.5, "sine", 0.12, release=0.45))))
    save("zone_open", mix(1.4, *[(i * 0.1, tone(note(n), 0.5, "sine", 0.22, release=0.4, vibrato=0.006))
                                 for i, n in enumerate(["G4", "C5", "E5", "G5", "C6", "E6"])],
                          (0, noise(1.2, 0.08, 1.5, 0.2))))
    fan = [("G4", 0.0, 0.15), ("C5", 0.15, 0.15), ("E5", 0.3, 0.15), ("G5", 0.45, 0.3), ("E5", 0.75, 0.15),
           ("G5", 0.9, 0.9)]
    parts = [(st, tone(note(n), d, "square", 0.22, release=0.1)) for n, st, d in fan]
    parts += [(st, tone(note(n) / 2, d, "pulse", 0.18, release=0.1)) for n, st, d in fan]
    parts += [(0.9, tone(note("C4"), 0.9, "tri", 0.3, release=0.4))]
    save("fanfare", mix(1.95, *parts))
    save("rooster", mix(0.9, (0, tone(700, 0.12, "square", 0.25, sweep=900)), (0.14, tone(900, 0.12, "square", 0.25)),
                        (0.28, tone(950, 0.5, "square", 0.25, sweep=700, vibrato=0.03, release=0.3))))


def music():
    """Уютная осенняя мелодия: 16 тактов, 84 удара в минуту, гармония C–Am–F–G."""
    bpm = 84
    beat = 60 / bpm
    bars = 16
    length = bars * 4 * beat
    buf = [0.0] * int(length * RATE)
    chords = [("C3", ["C4", "E4", "G4"]), ("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]), ("G2", ["G3", "B3", "D4"])]
    tunes = [["E5", "G5", "A5", "G5", "E5", "D5", "C5", "D5"], ["C5", "E5", "D5", "C5", "A4", "C5", "E5", "G5"],
             ["A4", "C5", "F5", "E5", "D5", "C5", "A4", "C5"], ["B4", "D5", "G5", "F5", "D5", "B4", "G4", "B4"]]
    for bar in range(bars):
        root, triad = chords[bar % 4]
        t0 = bar * 4 * beat
        tone(note(root), beat * 1.8, "tri", 0.22, release=0.3, buf=buf, start=t0)
        tone(note(root), beat * 1.8, "tri", 0.18, release=0.3, buf=buf, start=t0 + 2 * beat)
        for k in range(8):  # мягкое арпеджио восьмыми
            tone(note(triad[k % 3]), beat * 0.45, "pulse", 0.035, release=0.12, buf=buf, start=t0 + k * beat / 2)
        if bar % 8 >= 2:  # мелодия вступает чуть позже и иногда отдыхает
            tune = tunes[(bar // 4 + bar) % 4]
            for k in range(8):
                if (bar + k) % 7 == 6:
                    continue
                dur = beat * (0.9 if k % 2 == 0 else 0.45)
                tone(note(tune[k]), dur, "sine", 0.12, attack=0.01, release=0.25, vibrato=0.004,
                     buf=buf, start=t0 + k * beat / 2)
                tone(note(tune[k]) * 2, dur, "tri", 0.02, release=0.2, buf=buf, start=t0 + k * beat / 2)
    # плавные края, чтобы повтор был незаметен
    fade = int(0.08 * RATE)
    for i in range(fade):
        buf[i] *= i / fade
        buf[-1 - i] *= i / fade
    save("music_autumn", buf, gain=0.55)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sfx()
    music()
