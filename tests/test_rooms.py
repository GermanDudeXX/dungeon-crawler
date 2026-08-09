"""Special rooms and hazards: mini-bosses, chests, boss doors, floor hazards."""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.chdir(r"C:\Users\budzm\dungeon-crawler")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import constants as C
import dungeon
import entities
import locale_text as loc
from game import Game

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def carve_around(g, radius=5):
    px, py = g.player.x, g.player.y
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x, y = px + dx, py + dy
            if 0 < x < C.MAP_WIDTH - 1 and 0 < y < C.MAP_HEIGHT - 1:
                g.grid[y][x] = dungeon.FLOOR
    # Decorations too: crates and columns are solid, and one standing on
    # the tile a test wants to step onto stops the step entirely - which
    # looked like the hazard not hurting.
    g._decor = {}
    g._recompute_fov()


g = Game()
g.settings["language"] = "en"
g.start_new_run("normal")

# --- generation over a long run --------------------------------------
print("generation")
seen = {"mini": 0, "chest": 0, "door": 0, "hazard": 0, "super": 0, "boss": 0}
for lvl in range(1, 31):
    g.dungeon_level = lvl
    g.new_level()
    if any(m.is_mini_boss for m in g.monsters):
        seen["mini"] += 1
    if any(m.is_boss for m in g.monsters):
        seen["boss"] += 1
    if any(m.is_superboss for m in g.monsters):
        seen["super"] += 1
    if g.chest_pos:
        seen["chest"] += 1
    if g.boss_door_pos:
        seen["door"] += 1
    if g.hazards:
        seen["hazard"] += 1
check("mini-bosses appear between boss floors", seen["mini"] >= 4, seen)
check("treasure rooms appear", seen["chest"] >= 5, seen)
check("boss doors appear on boss floors", seen["door"] >= 3, seen)
check("hazards appear", seen["hazard"] >= 8, seen)
check("the superboss appears exactly once in 30 floors", seen["super"] == 1, seen)

# A mini-boss must never share a floor with a real boss: floor 15 is both
# divisible by 5 and by 3, and only the boss should be there.
for lvl in (15, 30):
    for _ in range(6):
        g.dungeon_level = lvl
        g.new_level()
        if any(m.is_mini_boss for m in g.monsters):
            check(f"no mini-boss on boss floor {lvl}", False)
            break
    else:
        check(f"no mini-boss on boss floor {lvl}", True)

# Hazards must never be under the stairs, the chest, or a trap.
clashes = []
for lvl in range(4, 20):
    g.dungeon_level = lvl
    g.new_level()
    for pos in g.hazards:
        if pos in (g.stairs_pos, g.up_stairs_pos, g.chest_pos) or pos in g.traps:
            clashes.append((lvl, pos))
check("hazards never sit on the stairs, a chest or a trap", not clashes, clashes[:3])

# --- mini-boss is actually worth noticing ----------------------------
print("mini-boss")
g.start_new_run("normal")
g.dungeon_level = 9
for _ in range(20):
    g.new_level()
    mini = next((m for m in g.monsters if m.is_mini_boss), None)
    if mini:
        break
check("a mini-boss was generated", mini is not None)
if mini:
    plain = g._make_monster(1, 1, mini.kind)
    check("a mini-boss is tougher than its plain version",
          mini.max_hp > plain.max_hp and mini.power > plain.power,
          f"{mini.max_hp}/{mini.power} vs {plain.max_hp}/{plain.power}")
    check("a mini-boss is worth more XP", mini.xp_reward > plain.xp_reward,
          f"{mini.xp_reward} vs {plain.xp_reward}")
    check("a mini-boss is not a real boss", not mini.is_boss)

# --- superboss --------------------------------------------------------
print("superboss")
g.dungeon_level = C.SUPERBOSS_LEVEL
g.new_level()
sb = next((m for m in g.monsters if m.is_superboss), None)
check("the superboss spawns on its floor", sb is not None)
if sb:
    normal_boss = g._make_monster(1, 1, sb.kind, boss=True)
    check("the superboss dwarfs an ordinary boss", sb.max_hp > normal_boss.max_hp * 2,
          f"{sb.max_hp} vs {normal_boss.max_hp}")
    # Via the display name, not sb.name: the prefix is applied when the
    # name is shown, so it survives a save and works in both languages.
    check("the superboss is named as one",
          g.t("superboss_prefix") in g._monster_display_name(sb),
          g._monster_display_name(sb))

# --- the chest --------------------------------------------------------
print("treasure room")
g.start_new_run("normal")
g.dungeon_level = 6
# Explicitly a *guarded* chest: some chests are mimics now, and those
# have no guardian at all - that is their own test's business.
for _ in range(60):
    g.new_level()
    if g.chest_pos and not g.chest_is_mimic:
        break
check("a treasure room was generated", g.chest_pos is not None and not g.chest_is_mimic)
guard = next((m for m in g.monsters if m.guards_chest), None)
check("the chest has a guardian", guard is not None)
check("the guardian starts next to the chest",
      guard and abs(guard.x - g.chest_pos[0]) + abs(guard.y - g.chest_pos[1]) == 1,
      (guard and (guard.x, guard.y), g.chest_pos))

items_before = len(g.items)
g._open_chest()
check("the chest stays shut while the guardian lives", not g.chest_open)
check("nothing drops from a guarded chest", len(g.items) == items_before)

guard.hp = 0
g.monsters.remove(guard)
g._open_chest()
check("the chest opens once the guardian is dead", g.chest_open)
check("the chest drops loot", len(g.items) > items_before,
      f"{items_before} -> {len(g.items)}")
dropped = len(g.items)
g._open_chest()
check("an opened chest cannot be looted twice", len(g.items) == dropped)

# --- the boss door ----------------------------------------------------
print("boss door")
g.start_new_run("normal")
g.dungeon_level = 10
for _ in range(20):
    g.new_level()
    if g.boss_door_pos:
        break
check("a boss floor bars its stairs", g.boss_door_pos is not None)
check("the door is locked while the boss lives", g._boss_door_blocked())

# Walking into it must not move the player and must not descend.
# Clear the floor first: this is a test about the door, and another
# monster standing on the stairs turns it into a test about spawn luck.
door = g.boss_door_pos
g.monsters = [m for m in g.monsters if m.is_boss]
g.hazards = {}
g.traps = {}
g.items = []
g._decor = {}
g.player.max_hp = g.player.hp = 500
g.player.x, g.player.y = door[0] - 1, door[1]
g.grid[door[1]][door[0] - 1] = dungeon.FLOOR
level_before = g.dungeon_level
g._player_turn(1, 0)
check("the door blocks the player", (g.player.x, g.player.y) == (door[0] - 1, door[1]),
      (g.player.x, g.player.y))
check("the door prevents descending", g.dungeon_level == level_before)

for m in list(g.monsters):
    if m.is_boss:
        g.monsters.remove(m)
check("the door unlocks when the boss dies", not g._boss_door_blocked())
g._player_turn(1, 0)
check("the stairs work once the boss is dead", g.dungeon_level == level_before + 1)

# --- hazards ----------------------------------------------------------
print("hazards")
for kind, info in C.HAZARD_TYPES.items():
    g.start_new_run("normal")
    g.dungeon_level = 10
    g.new_level()
    carve_around(g)
    g.monsters = []
    g.traps = {}
    p = g.player
    p.max_hp = 500
    p.hp = 500
    spot = (p.x + 1, p.y)
    g.hazards = {spot: kind}
    g._player_turn(1, 0)
    check(f"{kind} hurts", p.hp < 500, p.hp)
    if info.get("one_shot"):
        check(f"{kind} gives way and is gone", spot not in g.hazards)
    else:
        check(f"{kind} stays dangerous", spot in g.hazards)
        hp_after_first = p.hp
        p.x, p.y = spot[0] - 1, spot[1]
        g._player_turn(1, 0)
        check(f"{kind} hurts again", p.hp < hp_after_first)

# A hazard has to be able to kill, and end the run cleanly.
g.start_new_run("normal")
g.dungeon_level = 10
g.new_level()
carve_around(g)
g.monsters = []
g.traps = {}
p = g.player
p.hp = 1
g.hazards = {(p.x + 1, p.y): "collapse"}
g._player_turn(1, 0)
check("a hazard can kill you", g.state == "dead", g.state)

# --- saving -----------------------------------------------------------
print("saving")
g.start_new_run("normal")
g.dungeon_level = 10
for _ in range(30):
    g.new_level()
    if g.chest_pos and g.hazards and g.boss_door_pos:
        break
want = (dict(g.hazards), g.chest_pos, g.chest_open, g.boss_door_pos)
guard_count = sum(1 for m in g.monsters if m.guards_chest)
data = g._build_save_data()
g.save_data = data
g.continue_run()
got = (dict(g.hazards), g.chest_pos, g.chest_open, g.boss_door_pos)
check("hazards survive a save", got[0] == want[0])
check("the chest survives a save", got[1:3] == want[1:3], (got[1:3], want[1:3]))
check("the boss door survives a save", got[3] == want[3])
check("the chest guardian is still a guardian after a save",
      sum(1 for m in g.monsters if m.guards_chest) == guard_count,
      sum(1 for m in g.monsters if m.guards_chest))

# The same must hold for revisiting a floor via the up-stairs snapshot.
g.dungeon_level = 10
g.new_level()
for _ in range(30):
    g.new_level()
    if g.chest_pos and g.hazards:
        break
snap = g._snapshot_current_level()
g.chest_pos, g.hazards, g.boss_door_pos = None, {}, None
g._restore_level_snapshot(snap)
check("a revisited floor keeps its chest and hazards",
      g.chest_pos is not None and g.hazards, (g.chest_pos, len(g.hazards)))

# --- rendering --------------------------------------------------------
print("rendering")
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.explored = {(x, y) for y in range(C.MAP_HEIGHT) for x in range(C.MAP_WIDTH)}
    g.visible = set(g.explored)
    g._map_cache = None
    g.state = "playing"
    g.render()
    check(f"[{lang}] a floor with every special feature renders", True)
g.settings["language"] = "en"

# --- translations -----------------------------------------------------
print("translations")
needed = ["superboss_prefix", "log_mini_boss", "log_chest_guarded",
          "log_chest_opened", "log_boss_door_locked"]
needed += [f"log_hazard_{k}" for k in C.HAZARD_TYPES]
absent = [k for k in needed if k not in loc.STRINGS]
check("every new string exists", not absent, absent)
half = [k for k in needed if k in loc.STRINGS
        and ("de" not in loc.STRINGS[k] or "en" not in loc.STRINGS[k])]
check("every new string has both languages", not half, half)
bad_tile = [k for k, v in C.HAZARD_TYPES.items() if v["tile"] not in g._tile_sources]
check("every hazard's tile art exists", not bad_tile, bad_tile)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL SPECIAL-ROOM CHECKS PASSED")
