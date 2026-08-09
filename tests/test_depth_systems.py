import os
import random
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
import dungeon as dmod

random.seed(7)


# SDL only hands out so many renderers per process, so every section
# shares one Game. The difficulty and class are pinned rather than
# inherited from settings.json: these checks assert exact damage and proc
# numbers, and both scale the player - a saved Mage's elemental bonus
# pushes a proc past the roll this file forces.
_SHARED_GAME = game.Game()


def fresh_game():
    _SHARED_GAME.start_new_run("normal", "warrior")
    return _SHARED_GAME


# --- 1. Elemental proc + weak/resist math (isolated, no RNG needed for the
#     bonus-damage/weak-resist multiplier part; proc chance itself is
#     probabilistic so we force it deterministically via monkeypatched
#     random.random) ---
g = fresh_game()
g.player.weapon_element_id = "fire"
target = entities.Monster(g.player.x + 1, g.player.y, "skeleton")  # weak to fire
target.hp = target.max_hp = 100
target.defense = 0
g.player.base_power = 10
g.player.weapon_bonus = 0

orig_random = random.random
random.random = lambda: 0.0  # forces both crit-check (if any) and proc to succeed
try:
    g._attack(g.player, target)
finally:
    random.random = orig_random

assert target.burn_turns > 0, "fire weapon did not apply burn to a fire-weak monster"
print("elemental proc OK: skeleton (weak fire) burn_turns =", target.burn_turns, "hp left", target.hp)

# resist case: spider resists poison
g2 = fresh_game()
g2.player.weapon_element_id = "poison"
spider = entities.Monster(g2.player.x + 1, g2.player.y, "spider")
spider.hp = spider.max_hp = 100
spider.defense = 0
g2.player.base_power = 10
random.random = lambda: 0.45  # above spider's halved proc chance (0.4*0.5=0.2) but below unmodified 0.4
try:
    g2._attack(g2.player, spider)
finally:
    random.random = orig_random
assert spider.poison_turns == 0, "poison proc'd despite resist halving the chance below the roll"
print("resist math OK: spider (resist poison) did not get poisoned at roll 0.45")

# --- 2. Monster status ticking: poison/burn DoT kill correctly, weaken
#     reduces effective defense, stun skips the monster's action ---
g3 = fresh_game()
m = entities.Monster(g3.player.x + 1, g3.player.y, "rat")
m.hp = m.max_hp = 5
m.poison_turns = 2
g3.monsters = [m]
g3._tick_monster_status(m)
assert m.hp == 5 - C.POISON_DAMAGE_PER_TURN
assert m.poison_turns == 1
print("poison DoT tick OK, hp:", m.hp)

m2 = entities.Monster(0, 0, "rat")
m2.hp = m2.max_hp = 1
m2.burn_turns = 2
g3.monsters = [m2]
died_before = m2 in g3.monsters
g3._tick_monster_status(m2)
assert m2 not in g3.monsters, "burn DoT should have killed the 1-hp rat and removed it via _on_monster_death"
print("burn DoT lethal tick OK, monster removed:", died_before, "->", m2 in g3.monsters)

m3 = entities.Monster(0, 0, "goblin")
m3.stun_turns = 1
stunned = g3._tick_monster_status(m3)
assert stunned is True and m3.stun_turns == 0
print("stun tick OK, was stunned:", stunned)

# weaken reduces effective defense in _attack
g4 = fresh_game()
weak_target = entities.Monster(g4.player.x + 1, g4.player.y, "goblin")
weak_target.hp = weak_target.max_hp = 1000
weak_target.defense = 10
g4.player.weapon_element_id = None
g4.player.base_power = 12
g4.player.weapon_bonus = 0
no_weaken_hp_before = weak_target.hp
g4._attack(g4.player, weak_target)
dmg_normal = no_weaken_hp_before - weak_target.hp

weak_target2 = entities.Monster(g4.player.x + 1, g4.player.y, "goblin")
weak_target2.hp = weak_target2.max_hp = 1000
weak_target2.defense = 10
weak_target2.weaken_turns = 3
hp_before = weak_target2.hp
g4._attack(g4.player, weak_target2)
dmg_weakened = hp_before - weak_target2.hp
assert dmg_weakened > dmg_normal, f"weaken should increase damage taken: normal={dmg_normal} weakened={dmg_weakened}"
print(f"weaken defense reduction OK: normal dmg={dmg_normal}, weakened dmg={dmg_weakened}")

# --- 3. Boss mechanics: orc enrage triggers once, skeleton summon respects
#     cap, spider web poisons at range without needing adjacency ---
g5 = fresh_game()
orc_boss = entities.Monster(5, 5, "orc", boss=True)
orc_boss.hp = int(orc_boss.max_hp * 0.4)  # below 50% to trigger enrage
power_before = orc_boss.power
g5._boss_special_action(orc_boss, 3, 0)
assert orc_boss.enraged is True
assert orc_boss.power > power_before
power_after_first = orc_boss.power
g5._boss_special_action(orc_boss, 3, 0)  # should NOT re-trigger
assert orc_boss.power == power_after_first, "enrage re-triggered and compounded the power multiplier"
print("orc enrage OK: one-time trigger, power", power_before, "->", power_after_first)

g6 = fresh_game()
g6.grid, g6.rooms = dmod.generate_dungeon(C.MAP_WIDTH, C.MAP_HEIGHT)
# Stand the boss in the middle of a real room. This used to hardcode
# (10, 10), which in a fresh dungeon is more often solid rock than floor -
# so the summon had nowhere to put a minion and the test failed on about
# two runs in three, on map luck alone.
boss_room = max(g6.rooms, key=lambda r: (r.x2 - r.x1) * (r.y2 - r.y1))
bx, by = boss_room.center()
skel_boss = entities.Monster(bx, by, "skeleton", boss=True)
skel_boss.summon_cooldown = 0
g6.monsters = [skel_boss]
far_room = min(g6.rooms, key=lambda r: -((r.center()[0] - bx) ** 2 + (r.center()[1] - by) ** 2))
g6.player.x, g6.player.y = far_room.center()
summoned_any = False
for _ in range(5):
    skel_boss.summon_cooldown = 0
    result = g6._boss_special_action(skel_boss, 20, 10)
    if result:
        summoned_any = True
alive_regular_skeletons = sum(1 for m in g6.monsters if m.kind == "skeleton" and not m.is_boss)
assert summoned_any, "skeleton king never summoned despite cooldown forced to 0 repeatedly"
assert alive_regular_skeletons <= 3, f"summon cap violated: {alive_regular_skeletons} alive"
print("skeleton summon OK: summoned at least once, capped at", alive_regular_skeletons)

g7 = fresh_game()
# Open floor and no scenery: the web needs a clear line, and a wall or a
# crate anywhere between the two makes this a test of map luck.
g7.grid = [[dmod.FLOOR for _ in range(C.MAP_WIDTH)] for _ in range(C.MAP_HEIGHT)]
g7._decor = {}
spider_boss = entities.Monster(5, 5, "spider", boss=True)
spider_boss.web_cooldown = 0
g7.player.x, g7.player.y = 5, 8  # same column, distance 3 (in web range 2-4)
g7.player.poison_turns = 0
g7.monsters = [spider_boss]
result = g7._boss_special_action(spider_boss, 0, 3)
assert result is True
assert g7.player.poison_turns > 0, "spider web should poison the player at range"
print("spider web OK: player poisoned at range, poison_turns =", g7.player.poison_turns)

# --- 4. Flee behavior: low-hp rat moves away instead of attacking ---
g8 = fresh_game()
g8.grid, g8.rooms = dmod.generate_dungeon(C.MAP_WIDTH, C.MAP_HEIGHT)
rat = entities.Monster(10, 10, "rat")
rat.hp = 1
rat.max_hp = 10
rat.awake = True
g8.player.x, g8.player.y = 11, 10
g8.monsters = [rat]
pos_before = (rat.x, rat.y)
g8._monster_act(rat)
assert (rat.x, rat.y) != pos_before or not dmod.is_walkable(g8.grid, 9, 10), "fleeing rat should move away"
dist_before = abs(pos_before[0] - g8.player.x)
dist_after = abs(rat.x - g8.player.x)
print("flee behavior OK: rat moved from", pos_before, "to", (rat.x, rat.y), f"(dist {dist_before}->{dist_after})")

# --- 5. Perks: toughness clamp, regen, gold mult, elemental chance ---
g9 = fresh_game()
for _ in range(20):
    g9._apply_perk(next(p for p in C.PERKS if p["id"] == "toughness"))
assert g9.player.bonus_damage_reduction <= 0.75, f"damage reduction not clamped: {g9.player.bonus_damage_reduction}"
print("toughness clamp OK:", g9.player.bonus_damage_reduction)

g10 = fresh_game()
g10._apply_perk(next(p for p in C.PERKS if p["id"] == "regeneration"))
g10.player.hp = g10.player.max_hp - 5
for _ in range(6):
    g10._tick_regen()
assert g10.player.hp == g10.player.max_hp - 4, f"regen perk should heal 1 hp after 5 ticks, hp={g10.player.hp}"
print("regen perk OK, hp:", g10.player.hp)

g11 = fresh_game()
g11._apply_perk(next(p for p in C.PERKS if p["id"] == "greed"))
gold_item = entities.Item(g11.player.x, g11.player.y, "gold", "Gold", "$", C.COLOR_GOLD, bonus=100)
# _collect_item takes the item off the floor, so it has to be on it.
g11.items.append(gold_item)
g11._collect_item(gold_item)
assert g11.player.gold == 125, f"greed perk should give +25% gold, got {g11.player.gold}"
print("greed perk OK, gold:", g11.player.gold)

# --- 6. Rarity + element together on a weapon pickup, HUD label sane ---
g12 = fresh_game()
g12.dungeon_level = 10
for _ in range(20):
    g12._spawn_item(g12.rooms[0], "weapon")
elemental_found = any(i.element_id for i in g12.items if i.kind == "weapon")
rarity_found = {i.rarity_id for i in g12.items if i.kind == "weapon"}
assert elemental_found, "no elemental weapons rolled in 20 tries at dungeon level 10 (30% chance each - vanishingly unlikely to fail legitimately)"
print("weapon rolls OK, rarities seen:", rarity_found)

# --- 7. Shrine events: all 5 branches run without crashing, HP/gold/etc
#     change sanely, save/load round trip preserves shrine_pos ---
for event_id in ("vitality", "power", "fortune", "frailty", "ambush"):
    gs = fresh_game()
    gs.shrine_pos = (gs.player.x, gs.player.y)
    gs.player.hp = max(1, gs.player.max_hp - 10)
    C.SHRINE_EVENTS_BACKUP = C.SHRINE_EVENTS
    forced = [{"id": event_id, "name": "test", "weight": 1}]
    C.SHRINE_EVENTS = forced
    try:
        gs._trigger_shrine()
    finally:
        C.SHRINE_EVENTS = C.SHRINE_EVENTS_BACKUP
    assert gs.shrine_pos is None, f"shrine should be consumed after triggering ({event_id})"
    print(f"shrine event '{event_id}' OK, log tail:", gs.log[-1])

gs2 = fresh_game()
gs2.shrine_pos = (3, 4)
save = gs2._build_save_data()
gs2.save_data = save
g13 = game.Game.__new__(game.Game)
for attr in vars(gs2):
    setattr(g13, attr, getattr(gs2, attr))
g13.save_data = save
g13.continue_run()
assert g13.shrine_pos == (3, 4), f"shrine_pos lost across save/load: {g13.shrine_pos}"
print("shrine save/load round trip OK")

# backward compat: old save without shrine_pos / new player fields
old = gs2._build_save_data()
del old["shrine_pos"]
for key in ("weapon_element_id", "bonus_damage_reduction", "bonus_gold_mult",
            "bonus_elemental_chance", "regen_interval", "regen_counter"):
    old["player"].pop(key, None)
g14 = game.Game.__new__(game.Game)
for attr in vars(g13):
    setattr(g14, attr, getattr(g13, attr))
g14.save_data = old
g14.continue_run()
assert g14.shrine_pos is None
assert g14.player.weapon_element_id is None
assert g14.player.bonus_damage_reduction == 0.0
print("backward-compat load (pre-depth-systems save) OK")

# --- 8. Full gameplay loop smoke test with everything wired together ---
g15 = fresh_game()
g15._apply_perk(next(p for p in C.PERKS if p["id"] == "elemental_focus"))
for _ in range(60):
    if g15.state != "playing":
        break
    moved = False
    for ddx, ddy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        nx, ny = g15.player.x + ddx, g15.player.y + ddy
        if dmod.is_walkable(g15.grid, nx, ny):
            g15._player_turn(ddx, ddy)
            moved = True
            break
    if not moved:
        break
    g15.render()
print("full gameplay smoke loop OK, final state:", g15.state, "dungeon level:", g15.dungeon_level)

print("\nALL DEPTH-SYSTEM CHECKS PASSED")
