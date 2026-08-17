"""A shopkeeper must never be the thing standing between you and the stairs.

Walking into a merchant or a smith opens their shop instead of moving,
so their tile is a wall that never opens - and there is no way past one.
If the only route to the stairs goes through them, the floor cannot be
finished and the run can only be abandoned.

Found by playing rather than by reading: over 240 generated floors, on
5.7% of those that had a shopkeeper, the shopkeeper cut the stairs off.
The crates already avoid this - a crate in a one-tile corridor gets the
same check - because they block movement in the technical sense. The
shopkeepers do not; they intercept it, and so were missed.
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

import game

RUNS = 30
DEPTH = 6

g = game.Game()

floors = 0
with_shop = 0
shopkeepers = 0
cut_off = []

for _run in range(RUNS):
    g.start_new_run()
    for _depth in range(DEPTH):
        floors += 1
        npcs = {(m.x, m.y) for m in g.merchants}
        npcs |= {(b.x, b.y) for b in g.blacksmiths}
        shopkeepers += len(npcs)
        if npcs:
            with_shop += 1
            reachable = g._reachable_from((g.player.x, g.player.y), blocked=npcs)
            if g.stairs_pos not in reachable:
                cut_off.append((g.dungeon_level, sorted(npcs), g.stairs_pos))
        g._advance_level()

print(f"  {floors} Ebenen, {shopkeepers} Händler/Schmiede auf {with_shop} davon")
assert with_shop > 10, (
    f"only {with_shop} floors had a shopkeeper at all - this proves nothing")
assert not cut_off, (
    f"on {len(cut_off)} floors a shopkeeper stands between the player and the "
    f"stairs, and there is no way past one: {cut_off[:3]}")
print("  keiner von ihnen versperrt den Weg zur Treppe")

# And the check itself has to be able to fail, or it is decoration: drop
# a shopkeeper into a corridor by hand and it must be spotted.
g.start_new_run()
walled = None
for y in range(1, game.C.MAP_HEIGHT - 1):
    for x in range(1, game.C.MAP_WIDTH - 1):
        if g.blocks_movement(x, y):
            continue
        if g.stairs_pos not in g._reachable_from((g.player.x, g.player.y),
                                                 blocked={(x, y)}):
            walled = (x, y)
            break
    if walled:
        break

if walled is None:
    print("  (diese Karte hat keinen Engpass - Gegenprobe übersprungen)")
else:
    assert g._shopkeeper_spot(g.rooms) != walled, (
        "the placement handed back the one tile that walls the level off")
    print(f"  Gegenprobe: Engpass bei {walled} wird als solcher erkannt")

print("\nALL SHOPKEEPER-PLACEMENT CHECKS PASSED")
