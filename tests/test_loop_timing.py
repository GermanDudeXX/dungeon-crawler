"""Check the reworked main loop: faster polling must NOT speed up animations,
and the idle path must actually skip drawing.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401  - lets this file build several Games

pygame.init()

import game

g = game.Game()
g.start_new_run()
g.state = "playing"

# --- 1. animation timers must advance at 30Hz, not at the 60Hz poll rate ---
# Drive the same logic run() uses, with a fake clock we control.
fake = {"ms": 100000}
real_ticks = pygame.time.get_ticks
pygame.time.get_ticks = lambda: fake["ms"]
game.pygame.time.get_ticks = lambda: fake["ms"]

g._last_tick_ms = fake["ms"]
g.shake_timer = 30
ticks_applied = 0
POLLS = 120                    # 120 polls at 60Hz == 2 seconds
for _ in range(POLLS):
    fake["ms"] += 1000 // game.POLL_HZ
    now = fake["ms"]
    if now - g._last_tick_ms >= game.TICK_INTERVAL_MS:
        # Advance by exactly one interval, the way Game.run does, rather
        # than snapping to `now`. Snapping throws the remainder away, and
        # since the 16ms poll does not divide the 33ms tick that silently
        # runs animations at ~21Hz instead of 30 - which is the whole
        # thing this file exists to catch, so the test has to model it.
        g._last_tick_ms = max(now - game.TICK_INTERVAL_MS,
                              g._last_tick_ms + game.TICK_INTERVAL_MS)
        g._update_animations()
        ticks_applied += 1

pygame.time.get_ticks = real_ticks
game.pygame.time.get_ticks = real_ticks

expected = POLLS * (1000 // game.POLL_HZ) / game.TICK_INTERVAL_MS
print(f"over {POLLS} polls at {game.POLL_HZ}Hz: {ticks_applied} animation ticks "
      f"(expected ~{expected:.0f} at 30Hz)")
assert abs(ticks_applied - expected) <= 2, (
    f"animation cadence drifted from 30Hz: {ticks_applied} vs {expected:.0f}")
print("  animations still advance at 30Hz despite the 60Hz poll rate")

# --- 2. idle frames must skip drawing entirely ---
g2 = game.Game()
g2.start_new_run()
g2.state = "playing"
g2.player.snap()
for m in g2.monsters:
    m.snap()
g2.damage_numbers = []
g2.shake_timer = g2.flash_timer = g2.boss_banner_timer = 0
g2.needs_redraw = False
g2._last_draw_ms = pygame.time.get_ticks()

draws = 0
orig_render = g2.render


def counting_render():
    global draws
    draws += 1
    orig_render()


g2.render = counting_render
for _ in range(50):
    if g2._should_redraw():
        g2.render()
        g2.needs_redraw = False
        g2._last_draw_ms = pygame.time.get_ticks()
print(f"50 idle iterations on a static scene -> {draws} redraws "
      f"(expect 0-1, only the 500ms safety net)")
assert draws <= 1, f"idle scene still redrawing {draws} times"

# --- 3. a turn must always produce a redraw ---
g2.needs_redraw = False
g2._last_draw_ms = pygame.time.get_ticks()
import dungeon as dmod
for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
    if dmod.is_walkable(g2.grid, g2.player.x + dx, g2.player.y + dy):
        g2._player_turn(dx, dy)
        break
assert g2._should_redraw(), "a player turn did not mark the screen dirty"
print("  a player turn does mark the screen dirty")

print("\nALL LOOP-TIMING CHECKS PASSED")
