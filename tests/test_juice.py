"""Particles, hitstop, and the death summary - including their cost."""
import os
import sys
import time

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.chdir(r"C:\Users\budzm\dungeon-crawler")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import constants as C
import dungeon
import locale_text as loc
from game import Game

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


g = Game()
g.settings["language"] = "en"
g.start_new_run("normal", "warrior")

# --- particles --------------------------------------------------------
print("particles")
g.particles = []
g._spawn_particles(5, 5, (255, 0, 0), 8)
check("particles spawn", len(g.particles) == 8, len(g.particles))
check("particles start near the tile they came from",
      all(abs(p["x"] - (5 * C.TILE_SIZE + C.TILE_SIZE / 2)) < C.TILE_SIZE
          for p in g.particles))

before = [(p["x"], p["y"]) for p in g.particles]
g._update_particles()
after = [(p["x"], p["y"]) for p in g.particles]
check("particles move", before != after)

for _ in range(C.PARTICLE_LIFETIME + 2):
    g._update_particles()
check("particles expire", not g.particles, len(g.particles))

# The cap matters: it is the only thing between a big fight and the loop
# spending its frame budget on sparks.
g.particles = []
for _ in range(60):
    g._spawn_particles(5, 5, (255, 0, 0), 20)
check("particles are capped", len(g.particles) <= C.PARTICLE_MAX, len(g.particles))

# They must keep the frame alive, or a burst freezes half-drawn.
g.particles = []
g.shake_timer = g.flash_timer = g.boss_banner_timer = 0
g.damage_numbers = []
g.hitstop_timer = 0
g.player.snap()
for m in g.monsters:
    m.snap()
check("nothing animating means no redraw", not g._animations_active())
g._spawn_particles(5, 5, (255, 0, 0), 4)
check("particles keep the frame alive", g._animations_active())
g.particles = []
g.hitstop_timer = 3
check("hitstop keeps the frame alive", g._animations_active())
g.hitstop_timer = 0

# --- hitstop ----------------------------------------------------------
print("hitstop")
g.hitstop_timer = 3
g.shake_timer = 10
g.damage_numbers = [{"x": 0, "y": 0, "text": "1", "color": (255, 255, 255),
                     "timer": 30, "max_timer": 30}]
g._update_animations()
check("hitstop counts down", g.hitstop_timer == 2, g.hitstop_timer)
check("hitstop holds other timers still", g.shake_timer == 10, g.shake_timer)
check("hitstop holds damage numbers still", g.damage_numbers[0]["timer"] == 30)
g.hitstop_timer = 0
g._update_animations()
check("timers resume afterwards", g.shake_timer == 9, g.shake_timer)

# A crit has to actually trigger it.
g.start_new_run("normal", "rogue")
p = g.player
# The roll is forced rather than stacked with bonus_crit_chance: the
# natural crit chance is capped at 0.5 by design, so no amount of bonus
# ever makes a crit certain.
import random as _random
m = g._make_monster(p.x + 1, p.y, "orc")
m.hp = m.max_hp = 9999
g.monsters = [m]
g.particles = []
g.hitstop_timer = 0
_orig_random = _random.random
_random.random = lambda: 0.0
try:
    g._attack(p, m)
finally:
    _random.random = _orig_random
check("a crit freezes the frame", g.hitstop_timer > 0, g.hitstop_timer)
check("a crit throws more sparks than a normal hit",
      len(g.particles) >= C.PARTICLES_PER_CRIT, len(g.particles))

p.bonus_crit_chance = -1.0
g.particles = []
g.hitstop_timer = 0
g._attack(p, m)
check("a normal hit does not freeze the frame", g.hitstop_timer == 0)
check("a normal hit still throws sparks", 0 < len(g.particles) <= C.PARTICLES_PER_CRIT,
      len(g.particles))

# Death throws the biggest burst.
g.particles = []
m.hp = 1
g._attack(p, m)
check("a kill throws a burst", len(g.particles) >= C.PARTICLES_PER_DEATH,
      len(g.particles))

# --- particles must not survive into the next level or run -----------
print("cleanup")
g._spawn_particles(3, 3, (255, 255, 255), 10)
g.hitstop_timer = 5
g.dungeon_level = 3
g.new_level()
check("a new level clears particles", not g.particles)
check("a new level clears hitstop", g.hitstop_timer == 0)
g._spawn_particles(3, 3, (255, 255, 255), 10)
g.start_new_run("normal", "warrior")
check("a new run clears particles", not g.particles)

# --- the death summary ------------------------------------------------
print("death summary")
for lang in ("en", "de"):
    g.settings["language"] = lang
    for class_id in [k["id"] for k in C.CLASSES]:
        g.start_new_run("hard", class_id)
        g.player.gold = 120
        g.player.potions_drunk_this_run = 4
        lines = g._run_summary_lines()
        check(f"[{lang}/{class_id}] the summary has content",
              len(lines) >= 4 and all(lines), lines)
        check(f"[{lang}/{class_id}] the summary names the hero",
              g._class_name(g._class()) in lines[0], lines[0])
        g.state = "dead"
        g.new_best = True
        g.render()
    check(f"[{lang}] the death screen renders", True)
g.settings["language"] = "en"

needed = ["gameover_hero", "gameover_gear", "gameover_combat",
          "gameover_carried", "gameover_drunk"]
absent = [k for k in needed if k not in loc.STRINGS]
check("every summary string exists", not absent, absent)
half = [k for k in needed if "de" not in loc.STRINGS[k] or "en" not in loc.STRINGS[k]]
check("every summary string has both languages", not half, half)

# --- cost -------------------------------------------------------------
# This game needed a map cache to hit 30fps on a real phone, so anything
# added to the per-frame path gets measured rather than assumed.
print("cost")
g.start_new_run("normal", "warrior")
g.explored = {(x, y) for y in range(C.MAP_HEIGHT) for x in range(C.MAP_WIDTH)}
g.visible = set(g.explored)
g.state = "playing"
g.particles = []
g.render()
t = time.perf_counter()
for _ in range(60):
    g.render()
quiet = (time.perf_counter() - t) / 60 * 1000

while len(g.particles) < C.PARTICLE_MAX:
    g._spawn_particles(5, 5, (255, 0, 0), 20)
g.render()
t = time.perf_counter()
for _ in range(60):
    g.render()
busy = (time.perf_counter() - t) / 60 * 1000
print(f"       frame: {quiet:.2f} ms quiet -> {busy:.2f} ms with {C.PARTICLE_MAX} particles")
check("a full particle load costs well under a frame", busy < 16.0, f"{busy:.2f} ms")
check("particles are not the dominant cost", busy < quiet * 2 + 1.0,
      f"{quiet:.2f} -> {busy:.2f}")

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL JUICE CHECKS PASSED")
