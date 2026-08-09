"""Verify the cached map surface is correct and actually invalidated.

Correctness matters more than the speedup here: a stale cache would show
the player an out-of-date dungeon, which is far worse than a slow one.
Compares the cached render against a freshly-painted reference after each
kind of change that can alter the tiles.
"""
import os
import sys
import time

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import constants as C
import dungeon as dmod
import game


def reference_map(g):
    """What the map should look like for the current state, right now.

    This used to be a copy of the painting loop, which stopped being
    maintainable the moment the map drew real tiles. What the test is for
    is staleness - a cache surviving a change it should have been
    invalidated by - so the reference is a forced repaint of the present
    state. A cache that matches it is fresh; one that does not was never
    invalidated.
    """
    saved = g._map_cache
    g._map_cache = None
    g._rebuild_map_cache()
    fresh = g._map_cache
    g._map_cache = saved
    return fresh


def same(a, b):
    return pygame.image.tostring(a, "RGB") == pygame.image.tostring(b, "RGB")


def check(g, label):
    g._render_map(0, 0)          # forces a rebuild if invalidated
    got = g._map_cache
    want = reference_map(g)
    assert same(got, want), f"cached map differs from freshly painted map after: {label}"
    print(f"  cache correct after {label}")


g = game.Game()
g.start_new_run()
check(g, "new run")

# 1. moving (recomputes FOV -> must invalidate)
for _ in range(30):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if dmod.is_walkable(g.grid, g.player.x + dx, g.player.y + dy):
            g._player_turn(dx, dy)
            break
    if g.state != "playing":
        break
check(g, "walking around (FOV changes)")

# 2. the reveal scroll widens `explored` WITHOUT recomputing FOV - the one
#    path that does not go through _recompute_fov
g.state = "playing"
g.player.scrolls["reveal"] = 1
before = len(g.explored)
g._use_scroll("reveal")
assert len(g.explored) > before, "reveal did not widen the explored set"
check(g, "reveal scroll (explored changed, FOV did not)")

# 3. descending builds a whole new level
g.state = "playing"
g._advance_level()
check(g, "descending to a new level")

# 4. ascending restores a stored level
g._ascend_level()
check(g, "ascending back to the previous level")

# 5. loading a save
save = g._build_save_data()
g.save_data = save
g.continue_run()
check(g, "loading a save")

# --- speed, for the record ---
g.state = "playing"
g.explored = {(x, y) for y in range(C.MAP_HEIGHT) for x in range(C.MAP_WIDTH)}
g._map_cache = None
g._render_map(0, 0)

N = 200
t0 = time.perf_counter()
for _ in range(N):
    g._render_map(0, 0)
cached = (time.perf_counter() - t0) / N * 1000

t0 = time.perf_counter()
for _ in range(N):
    reference_map(g)
uncached = (time.perf_counter() - t0) / N * 1000

print(f"\nfully-explored level: uncached {uncached:.3f} ms -> cached {cached:.3f} ms "
      f"({uncached/cached:.0f}x faster)")
print("\nALL MAP-CACHE CHECKS PASSED")
