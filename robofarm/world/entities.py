"""Живые объекты мира: роботы, частицы, всплывающие надписи."""

import math
import random

ROBOT_NAMES = {"bublik": "Бублик", "klusha": "Клуша"}


class Robot:
    """Робот в мире. Действия ставятся в очередь и выполняются по одному."""

    SPEED = 46.0  # пикселей мира в секунду при обычной скорости

    def __init__(self, rid, x, y, facing="down"):
        self.id = rid
        self.name = ROBOT_NAMES.get(rid, rid)
        self.x, self.y = float(x), float(y)
        self.facing = facing
        self.anim = "idle"
        self.anim_t = 0.0
        self.queue = []
        self.current = None
        self.bubble = None  # (text, seconds left)
        self.emote = None   # (sprite, seconds left)
        self.speed_mul = 1.0
        self.hidden = False
        self.rest_anim = "idle"

    # --- очередь действий ---
    def busy(self):
        return self.current is not None or bool(self.queue)

    def walk_to(self, x, y):
        self.queue.append(("walk", (x, y)))

    def play(self, anim, seconds, callback=None, facing=None):
        self.queue.append(("anim", (anim, seconds, callback, facing)))

    def say(self, text, seconds=2.2):
        self.bubble = [text, seconds]

    def show_emote(self, sprite, seconds=1.4):
        self.emote = [sprite, seconds]

    def clear(self):
        self.queue.clear()
        self.current = None
        self.anim = self.rest_anim

    # --- кадр ---
    def update(self, dt):
        self.anim_t += dt
        if self.bubble:
            self.bubble[1] -= dt
            if self.bubble[1] <= 0:
                self.bubble = None
        if self.emote:
            self.emote[1] -= dt
            if self.emote[1] <= 0:
                self.emote = None
        if self.current is None and self.queue:
            self.current = list(self.queue.pop(0))
            self.anim_t = 0.0
            if self.current[0] == "anim":
                anim, seconds, callback, facing = self.current[1]
                self.anim = anim
                if facing:
                    self.facing = facing
                self.current.append(seconds)
        if self.current is None:
            if self.anim not in (self.rest_anim,):
                self.anim = self.rest_anim
            return
        kind = self.current[0]
        if kind == "walk":
            tx, ty = self.current[1]
            step = self.SPEED * self.speed_mul * dt
            dx, dy = tx - self.x, ty - self.y
            if abs(dx) > 0.5:
                self.facing = "right" if dx > 0 else "left"
                self.x += max(-step, min(step, dx))
                self.anim = "walk"
            elif abs(dy) > 0.5:
                self.facing = "down" if dy > 0 else "up"
                self.y += max(-step, min(step, dy))
                self.anim = "walk"
            else:
                self.x, self.y = tx, ty
                self.current = None
                self.anim = self.rest_anim
        elif kind == "anim":
            self.current[2] -= dt * self.speed_mul
            if self.current[2] <= 0:
                callback = self.current[1][2]
                self.current = None
                self.anim = self.rest_anim
                if callback:
                    callback()

    def sprite_id(self, assets):
        """Подбирает спрайт: <робот>_<анимация>_<направление> или без направления."""
        anim, facing = self.anim, self.facing
        candidates = [f"{self.id}_{anim}_{facing}", f"{self.id}_{anim}"]
        if facing in ("up", "down"):
            candidates.append(f"{self.id}_{anim}_left" if anim not in ("walk", "carry") else f"{self.id}_{anim}_down")
        candidates += [f"{self.id}_idle_{facing}", f"{self.id}_idle_down"]
        for sid in candidates:
            if assets.get(sid):
                return sid
        return f"{self.id}_idle_down"


class Particle:
    __slots__ = ("sprite", "x", "y", "vx", "vy", "life", "age", "phase", "kind")

    def __init__(self, sprite, x, y, vx, vy, life, kind="leaf"):
        self.sprite, self.x, self.y, self.vx, self.vy = sprite, x, y, vx, vy
        self.life, self.age, self.phase, self.kind = life, 0.0, random.random() * 6.28, kind


class Particles:
    """Листопад, пылинки в лучах, брызги и искорки."""

    LEAVES = ["fx_leaf_fall_1", "fx_leaf_fall_2", "fx_leaf_fall_3", "fx_leaf_fall_4", "fx_leaf_fall_5"]

    def __init__(self):
        self.items = []
        self.spawn_t = 0.0

    def ambient(self, dt, view_rect):
        x0, y0, w, h = view_rect
        self.spawn_t += dt
        while self.spawn_t > 0.35:
            self.spawn_t -= 0.35
            if sum(1 for p in self.items if p.kind == "leaf") < 18:
                self.items.append(Particle(random.choice(self.LEAVES), x0 + random.uniform(-20, w),
                                           y0 - 8, random.uniform(6, 16), random.uniform(12, 22),
                                           random.uniform(5, 9)))
            if sum(1 for p in self.items if p.kind == "mote") < 14:
                self.items.append(Particle("fx_dust_mote", x0 + random.uniform(0, w), y0 + random.uniform(0, h),
                                           random.uniform(-3, 3), random.uniform(-4, -1),
                                           random.uniform(4, 7), "mote"))

    def burst(self, sprite, x, y, life=0.5):
        self.items.append(Particle(sprite, x, y, 0, 0, life, "fx"))

    def float_text(self, text, x, y):
        p = Particle(text, x, y, 0, -14, 1.4, "text")
        self.items.append(p)

    def update(self, dt):
        alive = []
        for p in self.items:
            p.age += dt
            if p.age >= p.life:
                continue
            if p.kind == "leaf":
                p.x += (p.vx + math.sin(p.age * 2.2 + p.phase) * 10) * dt
                p.y += p.vy * dt
            else:
                p.x += p.vx * dt
                p.y += p.vy * dt
            alive.append(p)
        self.items = alive
