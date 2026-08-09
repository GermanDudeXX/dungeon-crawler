"""The dungeon must get a new, harder theme every 10 floors."""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import constants as C
import entities
import game

g = game.Game()
g.start_new_run()
fails = []

# --- 1. the theme changes exactly at each 10-floor boundary ---
print("floor -> theme (multiplier)")
prev = None
for level in (1, 5, 10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 60, 101):
    t = g._tier_for_level(level)
    marker = ""
    if prev is not None and t["index"] != prev["index"]:
        marker = "  <- new tier"
    print(f"  {level:3d}  {g._tier_name(t):16s} x{t['mult']:.2f}{marker}")
    prev = t

for level in range(1, 61):
    want = (level - 1) // 10
    got = g._tier_for_level(level)["index"]
    if got != want:
        fails.append(f"floor {level}: tier index {got}, expected {want}")

# boundaries specifically
if g._tier_for_level(10)["index"] == g._tier_for_level(11)["index"]:
    fails.append("floor 10 and 11 share a tier - the boundary is wrong")
if g._tier_for_level(1)["index"] != g._tier_for_level(10)["index"]:
    fails.append("floors 1-10 should all be the first tier")

# --- 2. difficulty strictly increases, and never loops back ---
mults = [g._tier_for_level(1 + 10 * i)["mult"] for i in range(12)]
if any(b <= a for a, b in zip(mults, mults[1:])):
    fails.append(f"tier multiplier is not strictly increasing: {[round(m,2) for m in mults]}")
else:
    print(f"\nmultiplier over 12 tiers: {[round(m, 2) for m in mults]}")

# --- 3. monsters actually get stronger ---
base = entities.Monster(1, 1, "orc")
deep = entities.Monster(1, 1, "orc", tier_mult=g._tier_for_level(41)["mult"])
print(f"orc on floor 1: {base.max_hp} hp / {base.power} pwr    "
      f"on floor 41: {deep.max_hp} hp / {deep.power} pwr")
if deep.max_hp <= base.max_hp or deep.power <= base.power:
    fails.append("a deep-tier orc is not stronger than a floor-1 orc")
if deep.xp_reward <= base.xp_reward:
    fails.append("a deep-tier orc does not award more XP")

# --- 4. the palette actually differs between tiers ---
palettes = {t["id"]: (t["wall"], t["floor"]) for t in C.DUNGEON_TIERS}
if len(set(palettes.values())) != len(palettes):
    fails.append("two tiers share the same colour palette")
else:
    print(f"{len(palettes)} distinct tile palettes")

# --- 5. descending across a boundary announces it and repaints ---
g.start_new_run()
g.dungeon_level = 10
g.tier = g._tier_for_level(10)
g._map_cache = None
g._render_map(0, 0)
before = pygame.image.tostring(g._map_cache, "RGB")
before_tier = g.tier["id"]
g.player.x, g.player.y = g.stairs_pos
g._advance_level()
if g.dungeon_level != 11:
    fails.append("descending from 10 did not reach 11")
if g.tier["id"] == before_tier and len(C.DUNGEON_TIERS) > 1:
    fails.append("crossing the 10-floor boundary did not change the theme")
if not any("Höhlen" in m or "Caverns" in m for m in g.log[-3:]):
    fails.append(f"entering a new tier was not announced; log tail={g.log[-3:]}")
else:
    print(f"announced on descent: {g.log[-1]!r}")
g._map_cache = None
g._render_map(0, 0)
if pygame.image.tostring(g._map_cache, "RGB") == before:
    fails.append("the tile surface did not repaint for the new theme")
else:
    print("tiles repainted for the new theme")

# --- 6. tier survives save/load and is derived, not stored stale ---
save = g._build_save_data()
g.save_data = save
g.continue_run()
if g.tier["index"] != g._tier_for_level(g.dungeon_level)["index"]:
    fails.append("tier is wrong after loading a save")
else:
    print("tier correct after save/load")

# --- 7. every referenced music file exists ---
for t in C.DUNGEON_TIERS:
    p = os.path.join(C.MUSIC_DIR, t["music"])
    if not os.path.exists(p):
        fails.append(f"tier {t['id']} references missing music {t['music']}")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL DUNGEON-TIER CHECKS PASSED")
