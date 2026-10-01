"""Общие данные и помощники для уроков всех глав."""

import random

from robofarm.farm import CROPS, make_bed

FIELD_ROWS = "АБВ"


def field_pos(name):
    r, c = FIELD_ROWS.index(name[0]), int(name[1:]) - 1
    return 52 + c * 3, 8 + r * 5


def field_beds(variant=0, count=12, ripe_share=0.5, dry_share=0.5, seed="field"):
    """Грядки поля. Вариант 0 — то, что видно в мире; другие варианты — «данные следующего дня»."""
    rnd = random.Random(f"{seed}:{variant}")
    names = [f"{row}{c}" for row in FIELD_ROWS for c in range(1, 5)][:count]
    crops = list(CROPS)
    beds = []
    for i, name in enumerate(names):
        crop = crops[(i + rnd.randrange(3)) % 3] if variant else crops[i % 3]
        dry = rnd.random() < dry_share
        ripe = rnd.random() < ripe_share
        humidity = rnd.choice([10, 15, 20, 25, 30, 35]) if dry else rnd.choice([40, 55, 70, 85, 100])
        stage = "ripe" if ripe else rnd.choice(["sprout", "growing", "almost"])
        x, y = field_pos(name)
        beds.append(make_bed(name, crop, x, y, humidity=humidity, stage=stage))
    if variant == 0:
        # гарантируем разнообразие на виду: есть сухие, мокрые, спелые и неспелые
        beds[0].update(humidity=20, stage="ripe")
        beds[1].update(humidity=80, stage="growing")
        beds[2].update(humidity=100, stage="ripe")
        beds[3].update(humidity=15, stage="almost")
    return beds


def numbers_in(lines):
    import re
    out = []
    for line in lines:
        out += [float(t) for t in re.findall(r"-?\d+(?:[.,]\d+)?", line.replace(",", "."))]
    return out


def lines_match(r, expected, what="Вывод"):
    """Сравнение напечатанных строк с ожидаемыми, с понятной подсказкой о первом отличии."""
    got = r.lines
    for i, exp in enumerate(expected):
        if i >= len(got):
            return f"{what}: не хватает строк. Ожидалась строка №{i + 1}: «{exp}»."
        if got[i].strip() != exp:
            g = got[i].strip()
            extra = " (отличаются только пробелы)" if g.replace(" ", "") == exp.replace(" ", "") else ""
            return f"{what}, строка {i + 1}: ожидалось «{exp}», а напечатано «{g}»{extra}."
    if len(got) > len(expected):
        return f"{what}: лишние строки. Первая лишняя: «{got[len(expected)].strip()}»."
    return None
