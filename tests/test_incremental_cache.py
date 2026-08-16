"""The two caches that a step used to throw away must still be correct.

Measured on the phone, a step cost 155ms, of which the map cache repaint
was 106-277ms once the level was explored and the HUD band another
25-131ms. Both are now updated instead of rebuilt - which is only worth
anything if the result is the same picture, so that is what this
checks: patched against fully repainted, pixel for pixel, and the band
against every value it shows.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401

pygame.init()

import constants as C
import dungeon
import game

g = game.Game()
g.start_new_run()
g.state = "playing"


def cache_bytes(surface):
    return pygame.image.tostring(surface, "RGB")


def painted_from_scratch():
    """The cached window, every cell painted fresh.

    Not _rebuild_map_cache: that re-centres the window on the camera, so
    it can legitimately come back covering a different area than the
    cache being checked. This paints exactly the window the cache holds,
    which is the thing worth comparing - did the run of patches leave
    the same surface as painting all of it at once.
    """
    x0, y0, cols, rows = g._map_cache_origin
    ts = C.TILE_SIZE
    surf = pygame.Surface((cols * ts, rows * ts))
    surf.fill(C.COLOR_BG)
    for y in range(y0, y0 + rows):
        for x in range(x0, x0 + cols):
            g._paint_map_cell(surf, x, y, x0, y0)
    return surf


def walk_a_few_steps(n=6):
    """Moves the player, so the field of view - and the lighting - moves."""
    moved = 0
    for _ in range(n * 4):
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            if not g.blocks_movement(g.player.x + dx, g.player.y + dy):
                g.player.x += dx
                g.player.y += dy
                g.player.snap()
                g._recompute_fov()
                g.needs_redraw = True
                g.render()
                moved += 1
                break
        if moved >= n:
            break
    return moved


# --- 1. a patched map cache is the same picture as a rebuilt one ----------
steps = walk_a_few_steps()
assert steps, "the player could not move at all - nothing was patched"
patched = cache_bytes(g._map_cache)
rebuilt = cache_bytes(painted_from_scratch())

if patched != rebuilt:
    differing = sum(1 for a, b in zip(patched, rebuilt) if a != b)
    raise AssertionError(
        f"the patched map cache differs from a full repaint in "
        f"{differing} of {len(rebuilt)} bytes after {steps} steps")
print(f"  map cache after {steps} steps: patched == fully repainted, "
      f"{len(rebuilt)} bytes")

# The same, with newly explored ground rather than only re-lit ground.
g.explored = set(g.visible)
g.needs_redraw = True
g.render()
walk_a_few_steps(4)
assert cache_bytes(g._map_cache) == cache_bytes(painted_from_scratch()), (
    "newly explored cells came out different when patched")
print("  and the same for newly explored ground")

# --- 2. the patch actually skips work ------------------------------------
# Without this the cache could be silently rebuilding every step and
# every check above would still pass.
painted = {"n": 0}
real_paint = g._paint_map_cell


def counting_paint(*a, **kw):
    painted["n"] += 1
    return real_paint(*a, **kw)


g._paint_map_cell = counting_paint
walk_a_few_steps(1)
per_step = painted["n"]
g._paint_map_cell = real_paint
window = g._map_cache_origin[2] * g._map_cache_origin[3]
print(f"  one step repaints {per_step} cells, not the window's {window}")
assert per_step < window // 2, (
    f"a step still repaints {per_step} of {window} cells - the patch is "
    f"not saving anything")

# --- 3. the HUD band repaints when, and only when, it changes ------------
g.needs_redraw = True
g.render()
paints = {"n": 0}
real_hud = g._paint_hud


def counting_hud(*a, **kw):
    paints["n"] += 1
    return real_hud(*a, **kw)


g._paint_hud = counting_hud

g.needs_redraw = True
g.render()
assert paints["n"] == 0, "the band repainted although nothing in it changed"
print("  a redraw with no change to the band does not repaint it")

# Every value in the signature has to reach the screen. A stale HUD is
# worse than a slow one: it shows the wrong number of potions.
p = g.player
cases = [
    ("hp", lambda: setattr(p, "hp", p.hp - 1)),
    ("gold", lambda: setattr(p, "gold", p.gold + 7)),
    ("xp", lambda: setattr(p, "xp", p.xp + 1)),
    ("level", lambda: setattr(p, "level", p.level + 1)),
    ("kills", lambda: setattr(p, "kills", p.kills + 1)),
    ("potions", lambda: p.add_potion(p.selected_potion)),
    ("weapon", lambda: setattr(p, "weapon_bonus", p.weapon_bonus + 1)),
    ("armor", lambda: setattr(p, "armor_bonus", p.armor_bonus + 1)),
    ("scrolls", lambda: p.scrolls.__setitem__("fireball", p.scrolls["fireball"] + 1)),
    ("shield", lambda: setattr(p, "shield", p.shield + 3)),
    ("poison", lambda: setattr(p, "poison_turns", p.poison_turns + 2)),
    ("bleed", lambda: setattr(p, "bleed_turns", p.bleed_turns + 2)),
    ("buffs", lambda: p.buffs.__setitem__(sorted(C.BUFFS)[0], 5)),
    ("log", lambda: g.add_log("etwas ist passiert")),
]
for name, change in cases:
    paints["n"] = 0
    change()
    g.needs_redraw = True
    g.render()
    assert paints["n"] == 1, (
        f"the band did not repaint after {name} changed - it would show a "
        f"stale value")
print(f"  and it does repaint for each of {len(cases)} values it shows")

g._paint_hud = real_hud

print("\nALL INCREMENTAL-CACHE CHECKS PASSED")
