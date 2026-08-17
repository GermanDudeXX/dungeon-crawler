"""Enemy variety: swarms, kiting, trap-setters, boss phases, mimics."""
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


def open_arena(g, radius=6):
    """A clear floor around the player, with nothing else on it."""
    px, py = g.player.x, g.player.y
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x, y = px + dx, py + dy
            if 0 < x < C.MAP_WIDTH - 1 and 0 < y < C.MAP_HEIGHT - 1:
                g.grid[y][x] = dungeon.FLOOR
    g.monsters = []
    g.items = []
    g.traps = {}
    g.hazards = {}
    g.merchants = []
    g.chest_pos = None
    g.boss_door_pos = None
    g.player.max_hp = g.player.hp = 999
    g._recompute_fov()


g = Game()
g.settings["language"] = "en"
g.start_new_run("normal")

# --- kiting -----------------------------------------------------------
print("kiting archers")
g.dungeon_level = 5
g.new_level()
open_arena(g)
px, py = g.player.x, g.player.y
archer = g._make_monster(px + 1, py, "skeleton")
archer.awake = True
archer.hp = archer.max_hp = 999
g.monsters = [archer]
g._monster_act(archer)
check("an adjacent archer backs away instead of trading blows",
      max(abs(archer.x - px), abs(archer.y - py)) > 1,
      (archer.x - px, archer.y - py))

# Cornered, it must fight rather than freeze.
open_arena(g)
g.player.x, g.player.y = px, py
for dx in range(-2, 3):
    for dy in range(-2, 3):
        g.grid[py + dy][px + dx] = dungeon.WALL
g.grid[py][px] = dungeon.FLOOR
g.grid[py][px + 1] = dungeon.FLOOR
cornered = g._make_monster(px + 1, py, "skeleton")
cornered.awake = True
g.monsters = [cornered]
hp_before = g.player.hp
g._monster_act(cornered)
check("a cornered archer fights instead of freezing", g.player.hp < hp_before,
      f"{hp_before} -> {g.player.hp}")

# A non-kiting monster must still close and attack normally.
g.dungeon_level = 5
g.new_level()
open_arena(g)
px, py = g.player.x, g.player.y
orc = g._make_monster(px + 1, py, "orc")
orc.awake = True
hp_before = g.player.hp
g._monster_act(orc)
check("a melee monster still attacks from next to you", g.player.hp < hp_before)

# --- swarms -----------------------------------------------------------
print("swarms")
swarming = [k for k, v in C.MONSTER_TYPES.items() if v.get("swarms")]
check("some kinds are marked as swarming", swarming, swarming)
counts = []
for _ in range(30):
    g.dungeon_level = 6
    g.new_level()
    for kind in swarming:
        same = [m for m in g.monsters if m.kind == kind]
        # A real swarm is several of them standing together.
        for m in same:
            near = sum(1 for o in same
                       if o is not m and abs(o.x - m.x) <= 1 and abs(o.y - m.y) <= 1)
            counts.append(near)
check("swarming kinds actually turn up in clusters", max(counts, default=0) >= 1,
      max(counts, default=0))

g.dungeon_level = 6
g.new_level()
open_arena(g)
px, py = g.player.x, g.player.y
g._spawn_swarm(px + 3, py, "rat", 4)
check("a swarm spawns the number asked for", len(g.monsters) == 4, len(g.monsters))
check("a swarm spawns together",
      all(abs(m.x - (px + 3)) <= 1 and abs(m.y - py) <= 1 for m in g.monsters))

# --- trap setters -----------------------------------------------------
print("trap setters")
g.dungeon_level = 6
g.new_level()
open_arena(g)
px, py = g.player.x, g.player.y
goblin = g._make_monster(px + 3, py, "goblin")
goblin.awake = True
goblin.trap_cooldown = 0
g.monsters = [goblin]
start = (goblin.x, goblin.y)
g._monster_act(goblin)
check("a trap-setter leaves a trap where it stood", start in g.traps, g.traps)
check("a trap-setter steps off its own trap", (goblin.x, goblin.y) != start)
check("a trap-setter goes on cooldown", goblin.trap_cooldown > 0, goblin.trap_cooldown)
traps_now = len(g.traps)
g._monster_act(goblin)
check("a trap-setter does not carpet the room", len(g.traps) == traps_now,
      len(g.traps))

# It must never bury a trap under something that already matters.
g.traps = {}
goblin.trap_cooldown = 0
goblin.x, goblin.y = g.stairs_pos
g._monster_act(goblin)
check("a trap-setter never traps the stairs", g.stairs_pos not in g.traps)

# --- boss phases ------------------------------------------------------
print("boss phases")
boss = g._make_monster(1, 1, "orc", boss=True)
boss.max_hp = 100
boss.hp = 100
check("a fresh boss has no phase", g._boss_phase(boss) is None)
boss.hp = 60
first = g._boss_phase(boss)
check("a wounded boss enters the first phase", first is not None, first)
boss.hp = 20
second = g._boss_phase(boss)
check("a nearly-dead boss enters the last phase", second is not first, second)
check("phases are ordered by how hurt the boss is",
      second["power_mult"] > first["power_mult"])
boss.hp = 100
check("healing a boss puts it back to no phase", g._boss_phase(boss) is None)

# The phase has to reach the damage the boss actually deals.
g.dungeon_level = 5
g.new_level()
open_arena(g)
px, py = g.player.x, g.player.y
boss = g._make_monster(px + 1, py, "orc", boss=True)
boss.max_hp = 100
boss.hp = 100
boss.defense = 0
g.monsters = [boss]
g.player.base_defense = 0
g.player.armor_bonus = 0
g.player.hp = 900
before = g.player.hp
g._attack(boss, g.player)
healthy_hit = before - g.player.hp
boss.hp = 10
before = g.player.hp
g._attack(boss, g.player)
desperate_hit = before - g.player.hp
check("a boss hits harder in a later phase", desperate_hit > healthy_hit,
      f"{healthy_hit} -> {desperate_hit}")

for lang in ("en", "de"):
    g.settings["language"] = lang
    boss.awake = True
    g.state = "playing"
    for hp in (100, 60, 20):
        boss.hp = hp
        g.render()
    check(f"[{lang}] the boss bar renders in every phase", True)
g.settings["language"] = "en"

# --- mimics -----------------------------------------------------------
print("mimics")
g.start_new_run("normal")
g.dungeon_level = 8
found = 0
for _ in range(120):
    g.new_level()
    if g.chest_is_mimic:
        found += 1
check("mimics turn up", found > 0, found)

for _ in range(200):
    g.dungeon_level = 8
    g.new_level()
    if g.chest_is_mimic:
        break
check("a mimic floor was generated", g.chest_is_mimic)
check("a mimic has no separate guardian",
      not any(m.guards_chest for m in g.monsters))

chest = g.chest_pos
g.player.max_hp = g.player.hp = 999
monsters_before = len(g.monsters)
g._open_chest()
check("touching a mimic springs it", any(m.is_mimic for m in g.monsters))
check("springing a mimic adds exactly one monster",
      len(g.monsters) == monsters_before + 1, len(g.monsters))
check("the chest is gone once it turns out to be a mimic", g.chest_pos is None)
check("a mimic gets the first hit", g.player.hp < 999, g.player.hp)
mimic = next(m for m in g.monsters if m.is_mimic)
# Next to the chest, not on it - and above all not on the player, who
# is standing on the chest, because that is how a chest gets opened.
# A mimic sharing the hero's tile cannot be attacked at all: attacks
# are aimed at the tile you walk into, and that is never your own.
# This test used to require the old behaviour, which is how it stayed
# that way; playing the game is what turned it up.
beside_chest = (abs(mimic.x - chest[0]) <= 1 and abs(mimic.y - chest[1]) <= 1)
check("a mimic springs up at the chest", beside_chest, (mimic.x, mimic.y))
check("a mimic does not stand on the player",
      (mimic.x, mimic.y) != (g.player.x, g.player.y))
check("a mimic is awake", mimic.awake)
plain = g._make_monster(1, 1, mimic.kind)
check("a mimic is tougher than its plain version", mimic.max_hp > plain.max_hp)

# Mimics must never be gated below their minimum level.
early = 0
g.dungeon_level = C.MIMIC_MIN_LEVEL - 1
for _ in range(120):
    g.new_level()
    if g.chest_is_mimic:
        early += 1
check("mimics are gated by depth", early == 0, early)

# --- saving -----------------------------------------------------------
print("saving")
g.start_new_run("normal")
g.dungeon_level = 8
for _ in range(200):
    g.new_level()
    if g.chest_is_mimic:
        break
data = g._build_save_data()
g.chest_is_mimic = False
g.save_data = data
g.continue_run()
check("a mimic is still a mimic after a save", g.chest_is_mimic)

g.dungeon_level = 6
g.new_level()
open_arena(g)
goblin = g._make_monster(g.player.x + 3, g.player.y, "goblin")
goblin.trap_cooldown = 4
goblin.awake = True
g.monsters = [goblin]
data = g._build_save_data()
g.save_data = data
g.continue_run()
restored = next((m for m in g.monsters if m.kind == "goblin"), None)
check("a trap-setter's cooldown survives a save",
      restored is not None and restored.trap_cooldown == 4,
      restored and restored.trap_cooldown)

# --- translations -----------------------------------------------------
print("translations")
needed = ["mimic_prefix", "log_mimic", "log_trap_set"]
absent = [k for k in needed if k not in loc.STRINGS]
check("every new string exists", not absent, absent)
missing_phase = [p["name"] for p in C.BOSS_PHASES if p["name"] not in loc.NAME_DE]
check("every boss phase has a German name", not missing_phase, missing_phase)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL ENEMY-VARIETY CHECKS PASSED")
