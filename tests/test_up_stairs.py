import os
import random
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401  - lets this file build several Games

pygame.init()

import constants as C
import entities
import game

random.seed(11)

g = game.Game()
g.start_new_run()

assert g.up_stairs_pos is None, "level 1 should have no up-stairs"
level1_grid = g.grid
level1_stairs = g.stairs_pos

# drop a marker item on level 1 so we can verify state survives a round trip
marker = entities.Item(level1_stairs[0], level1_stairs[1] - 1 if level1_stairs[1] > 0 else level1_stairs[1] + 1,
                        "gold", "Gold", "$", C.COLOR_GOLD, bonus=999)
g.items.append(marker)
monsters_before = len(g.monsters)

g._advance_level()
assert g.dungeon_level == 2
assert g.up_stairs_pos is not None, "level 2 should have an up-stairs back to level 1"
assert 1 in g.level_history, "descending should snapshot the level being left"
level2_stairs = g.stairs_pos
level2_up = g.up_stairs_pos
level2_grid_id = id(g.grid)
print("descend 1->2 OK, up_stairs on level 2:", level2_up)

# modify level 2 a bit so we can tell if it round-trips correctly later
g.player.gold += 50
extra_item = entities.Item(2, 2, "potion", "Healing Potion", "!", C.COLOR_POTION, bonus=15)
g.items.append(extra_item)
level2_item_count = len(g.items)

g._ascend_level()
assert g.dungeon_level == 1
assert g.grid is level1_grid, "ascending back to level 1 should restore the exact original grid object"
assert g.stairs_pos == level1_stairs
assert any(i.bonus == 999 for i in g.items), "marker item placed on level 1 before descending should still be there"
assert 2 in g.level_history, "ascending should snapshot the level being left (level 2)"
print("ascend 2->1 OK, level 1 state restored exactly, marker item present")

g._advance_level()
assert g.dungeon_level == 2
assert any(i.bonus == 15 for i in g.items if i.kind == "potion" and i.x == 2 and i.y == 2), \
    "re-descending to level 2 should restore the exact state we left it in (extra potion, gold spend)"
assert len(g.items) == level2_item_count
print("re-descend 1->2 OK, level 2 state restored exactly (extra item preserved)")

# up-stairs should never be walkable-triggerable on level 1
g._ascend_level()
g.dungeon_level = 1
g.up_stairs_pos = None
before = g.dungeon_level
g._ascend_level()
assert g.dungeon_level == before, "_ascend_level should no-op when up_stairs_pos is None / already on level 1"
print("ascend no-op guard OK on level 1")

# save/load round trip preserves level_history across a save+continue
g2 = game.Game()
g2.start_new_run()
g2._advance_level()
g2._advance_level()
assert set(g2.level_history.keys()) == {1, 2}
save = g2._build_save_data()
g3 = game.Game.__new__(game.Game)
for attr in vars(g2):
    setattr(g3, attr, getattr(g2, attr))
g3.save_data = save
g3.continue_run()
assert set(g3.level_history.keys()) == {1, 2}, f"level_history lost across save/load: {g3.level_history.keys()}"
g3._ascend_level()
assert g3.dungeon_level == 2
print("level_history save/load round trip OK")

# backward compat: old save without level_history / up_stairs_pos at all
old = g2._build_save_data()
old.pop("level_history", None)
old.pop("up_stairs_pos", None)
g4 = game.Game.__new__(game.Game)
for attr in vars(g3):
    setattr(g4, attr, getattr(g3, attr))
g4.save_data = old
g4.continue_run()
assert g4.level_history == {}
assert g4.up_stairs_pos is None
print("backward-compat load (pre-up-stairs save) OK")

print("\nALL UP-STAIRS CHECKS PASSED")
