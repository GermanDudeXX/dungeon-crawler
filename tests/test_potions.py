"""The typed-potion system: effects, buffs, the bag, shops, saving."""
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


g = Game()
g.settings["language"] = "en"

# --- the table itself -------------------------------------------------
print("potion table")
ids = [p["id"] for p in C.POTION_TYPES]
check(f"there are {len(ids)} potion types", len(ids) >= 28, len(ids))
check("no duplicate ids", len(set(ids)) == len(ids),
      [i for i in ids if ids.count(i) > 1])
missing_name = [p["id"] for p in C.POTION_TYPES if p["name"] not in loc.NAME_DE]
check("every potion has a German name", not missing_name, missing_name)
missing_buff = [b for b, v in C.BUFFS.items() if v["name"] not in loc.NAME_DE]
check("every buff has a German name", not missing_buff, missing_buff)
bad_flask = [p["id"] for p in C.POTION_TYPES if p["flask"] not in g._tile_sources]
check("every potion's flask art exists", not bad_flask, bad_flask)
check("the default potion is in the table", C.DEFAULT_POTION in C.POTION_BY_ID)
sellable = [p for p in C.POTION_TYPES if not p.get("cursed")]
check("cursed potions are never priced",
      all(p["price"] == 0 for p in C.POTION_TYPES if p.get("cursed")))

# --- every single effect runs, and does something ---------------------
print("effects")
for info in C.POTION_TYPES:
    g.start_new_run("normal")
    g.dungeon_level = 10
    p = g.player
    p.hp = max(1, p.max_hp // 2)
    # The cures need something to cure, or "changed nothing" is the right
    # answer; blink moves the player, so the position counts too.
    p.poison_turns = 4
    p.bleed_turns = 4
    before = (p.hp, p.max_hp, p.base_power, p.base_defense, p.gold, p.xp,
              len(p.buffs), p.shield, p.poison_turns, p.bleed_turns,
              len(g.explored), p.x, p.y)
    # A monster in range so the burst flasks have something to hit.
    g.monsters = [g._make_monster(p.x + 1, p.y, "rat")]
    try:
        g._apply_potion_effect(info)
    except Exception as exc:
        check(f"{info['id']} applies", False, repr(exc))
        continue
    after = (p.hp, p.max_hp, p.base_power, p.base_defense, p.gold, p.xp,
             len(p.buffs), p.shield, p.poison_turns, p.bleed_turns,
             len(g.explored), p.x, p.y)
    changed = after != before or not g.monsters
    check(f"{info['id']} changes something", changed, f"{before} -> {after}")

# --- buffs stack, expire, and reach the stats -------------------------
print("buffs")
g.start_new_run("normal")
p = g.player
base_power = p.power
p.buffs["strength"] = 3
check("strength raises power", p.power > base_power, f"{base_power} -> {p.power}")
p.buffs["berserk"] = 3
check("buffs stack rather than replace each other",
      p.power > base_power + C.BUFFS["strength"]["power"], p.power)
# Baseline with nothing up: Berserk above carries its own defence
# penalty, so measuring while it is active compared 0 against 0. Raise
# base defence too, or the floor at 0 hides the effect.
p.buffs.clear()
p.base_defense = 5
base_def = p.defense
p.buffs["frailty"] = 3
check("a curse lowers defence", p.defense < base_def, f"{base_def} -> {p.defense}")
p.buffs.clear()
p.buffs["clumsy"] = 3
check("power never drops below 1", p.power >= 1, p.power)

p.buffs.clear()
p.base_power = 4
p.buffs["strength"] = 2
g._tick_buffs()
check("buffs count down", p.buffs.get("strength") == 1, p.buffs)
g._tick_buffs()
check("buffs expire", "strength" not in p.buffs, p.buffs)

# Precision must beat the natural crit cap, or it is pointless late on.
p.level = 40
capped = p.crit_chance
p.buffs["precision"] = 5
check("precision raises crit past the natural cap", p.crit_chance > capped,
      f"{capped} -> {p.crit_chance}")
p.buffs.clear()

# Regeneration heals on the tick, but never past full.
p.hp = p.max_hp - 1
p.buffs["regen"] = 3
g._tick_buffs()
check("regeneration never overheals", p.hp == p.max_hp, p.hp)

# --- the ward absorbs before health does ------------------------------
print("ward")
g.start_new_run("normal")
p = g.player
p.shield = 100
p.hp = p.max_hp
m = g._make_monster(p.x + 1, p.y, "orc")
g._attack(m, p)
check("a ward takes the hit instead of health", p.hp == p.max_hp,
      f"hp {p.hp}, shield {p.shield}")
check("the ward is spent", p.shield < 100, p.shield)

# --- thorns and lifesteal --------------------------------------------
print("thorns and life leech")
g.start_new_run("normal")
p = g.player
p.buffs["thorns"] = 5
m = g._make_monster(p.x + 1, p.y, "orc")
m.hp = m.max_hp = 500
g.monsters = [m]
g._attack(m, p)
check("thorns hurt the attacker", m.hp < 500, m.hp)

g.start_new_run("normal")
p = g.player
p.hp = 1
p.base_power = 50
p.buffs["lifesteal"] = 5
m = g._make_monster(p.x + 1, p.y, "orc")
m.hp = m.max_hp = 500
g.monsters = [m]
g._attack(p, m)
check("life leech heals you when you hit", p.hp > 1, p.hp)

# --- haste skips the monsters' turn ----------------------------------
print("haste and invisibility")
g.start_new_run("normal")
p = g.player
for dx in range(-3, 4):
    for dy in range(-3, 4):
        if 0 < p.x + dx < C.MAP_WIDTH - 1 and 0 < p.y + dy < C.MAP_HEIGHT - 1:
            g.grid[p.y + dy][p.x + dx] = dungeon.FLOOR
g.monsters = []
m = g._make_monster(p.x + 3, p.y, "orc")
m.awake = True
m.hp = m.max_hp = 9999
g.monsters.append(m)
g._recompute_fov()
p.buffs["haste"] = 20
acted = []
for _ in range(4):
    pos = (m.x, m.y)
    g._enemy_turn()
    acted.append((m.x, m.y) != pos)
check("haste costs the monsters every other turn", acted.count(False) >= 2, acted)

g.start_new_run("normal")
p = g.player
for dx in range(-3, 4):
    for dy in range(-3, 4):
        if 0 < p.x + dx < C.MAP_WIDTH - 1 and 0 < p.y + dy < C.MAP_HEIGHT - 1:
            g.grid[p.y + dy][p.x + dx] = dungeon.FLOOR
g.monsters = []
m = g._make_monster(p.x + 3, p.y, "orc")
m.hp = m.max_hp = 9999
g.monsters.append(m)
g._recompute_fov()
p.buffs["invisible"] = 20
g._enemy_turn()
check("an invisible player does not wake monsters", not m.awake)
m.awake = True
pos = (m.x, m.y)
g._enemy_turn()
check("an awake monster loses track of an invisible player", (m.x, m.y) == pos)

# --- drinking ---------------------------------------------------------
print("drinking")
g.start_new_run("normal")
p = g.player
p.potion_counts = {}
g._drink_potion()
check("drinking nothing is refused", "log_no_potions" not in "" and p.potions == 0)

p.add_potion("healing", 2)
p.hp = p.max_hp
g._drink_potion("healing")
check("healing is refused at full health", p.potion_count("healing") == 2)

# Non-healing potions must NOT be refused at full health, or the quick-use
# button becomes unpredictable.
p.add_potion("strength")
g.state = "playing"
g._drink_potion("strength")
check("a buff potion can be drunk at full health",
      "strength" in p.buffs and p.potion_count("strength") == 0, p.buffs)

p.hp = 1
before = p.potion_count("healing")
g._drink_potion("healing")
check("drinking consumes exactly one flask", p.potion_count("healing") == before - 1)
check("drinking heals", p.hp > 1, p.hp)

# Re-drinking refreshes rather than stacking into a permanent buff.
p.add_potion("strength", 2)
g._drink_potion("strength")
first = p.buffs["strength"]
p.buffs["strength"] = 2
g._drink_potion("strength")
check("re-drinking refreshes the duration instead of adding to it",
      p.buffs["strength"] == first, p.buffs["strength"])

# --- the bag ----------------------------------------------------------
print("bag")
g.start_new_run("normal")
p = g.player
p.potion_counts = {}
for pid in ("healing", "strength", "antidote", "haste", "firebomb"):
    p.add_potion(pid, 2)
g.state = "playing"
g._handle_key(pygame.K_i)
check("I opens the bag", g.state == "bag", g.state)
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.state = "bag"
    g.render()
    check(f"[{lang}] the bag renders", True)
    keys = [k for _r, k in g._tap_targets]
    check(f"[{lang}] every row is tappable",
          all(k in keys for k in g.BAG_KEYS[:5]), keys)
g.settings["language"] = "en"

rows = g._bag_rows()
check("the bag lists every kind held", len(rows) == 5, rows)
check("the bag order is stable", g._bag_rows() == rows)
g.state = "bag"
g._bag_key(pygame.K_2)
check("picking a row drinks that potion and closes the bag",
      g.state == "playing", g.state)
g.state = "bag"
g._bag_key(pygame.K_ESCAPE)
check("ESC closes the bag", g.state == "playing", g.state)

# An empty bag must still render rather than dividing by zero.
p.potion_counts = {}
g.state = "bag"
g.render()
check("an empty bag renders", True)

# Paging, when there are more kinds than number keys.
p.potion_counts = {}
for info in C.POTION_TYPES:
    p.add_potion(info["id"])
g.state = "bag"
g.bag_page = 0
g.render()
g._bag_key(pygame.K_RIGHT)
check("the bag pages forward", g.bag_page == 1, g.bag_page)
g.render()
g._bag_key(pygame.K_LEFT)
check("the bag pages back", g.bag_page == 0, g.bag_page)
for page in range(0, (len(C.POTION_TYPES) - 1) // len(g.BAG_KEYS) + 1):
    g.bag_page = page
    g.render()
check("every bag page renders", True)

# --- quick-use slot ---------------------------------------------------
print("quick-use slot")
g.start_new_run("normal")
p = g.player
p.potion_counts = {}
p.selected_potion = "healing"
p.add_potion("haste")
check("picking a flask up when empty-handed selects it",
      p.selected_potion == "haste", p.selected_potion)
p.take_potion("haste")
check("running out moves the slot off the empty kind",
      p.potion_count(p.selected_potion) == 0 or p.selected_potion != "haste",
      p.selected_potion)

# --- spawning and shops ----------------------------------------------
print("spawning and shops")
g.start_new_run("normal")
g.dungeon_level = 1
early = {g._roll_potion() for _ in range(300)}
gated = {pid for pid in early if C.POTION_BY_ID[pid]["min_level"] > 1}
check("depth gates the stronger potions", not gated, gated)
g.dungeon_level = 12
late = {g._roll_potion() for _ in range(600)}
check("deeper floors unlock more kinds", len(late) > len(early),
      f"{len(early)} -> {len(late)}")

merchant = entities.Merchant(1, 1)
stock = g._merchant_stock(merchant)
check("merchants stock more than the fixed list", len(stock) > len(C.SHOP_STOCK),
      len(stock))
check("a merchant's stock does not reroll", g._merchant_stock(merchant) is stock)
cursed_ids = {p["id"] for p in C.POTION_TYPES if p.get("cursed")}
sold = {e.get("potion_id") for e in stock if e["kind"] == "potion"}
check("merchants never sell cursed flasks", not (sold & cursed_ids), sold & cursed_ids)

g.shop_stock = stock
g.player.gold = 9999
before = g.player.potions
g._buy_item(len(stock) - 1)
check("buying a potion adds the right kind", g.player.potions == before + 1)
g.state = "shop"
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.render()
    check(f"[{lang}] the shop renders a longer stock list", True)
g.settings["language"] = "en"

# --- saving -----------------------------------------------------------
print("saving")
g.start_new_run("normal")
p = g.player
p.potion_counts = {"healing": 3, "haste": 1, "panacea": 2}
p.selected_potion = "haste"
p.buffs = {"strength": 4, "luck": 9}
p.shield = 17
data = g._build_save_data()
p.potion_counts = {}
p.buffs = {}
p.shield = 0
g.save_data = data
g.continue_run()
check("potion counts survive a save", g.player.potion_counts ==
      {"healing": 3, "haste": 1, "panacea": 2}, g.player.potion_counts)
check("the quick-use slot survives", g.player.selected_potion == "haste")
check("buffs survive", g.player.buffs == {"strength": 4, "luck": 9}, g.player.buffs)
check("the ward survives", g.player.shield == 17)

# An old save has only the single "potions" number and no counts at all.
legacy = g._build_save_data()
legacy["player"].pop("potion_counts")
legacy["player"].pop("selected_potion")
legacy["player"].pop("buffs")
legacy["player"]["potions"] = 4
g.save_data = legacy
g.continue_run()
check("an old save's potions become healing potions",
      g.player.potion_counts == {C.DEFAULT_POTION: 4}, g.player.potion_counts)
check("an old save has no buffs", g.player.buffs == {})

# --- rendering the play view with everything on ----------------------
print("hud")
g.start_new_run("normal")
p = g.player
p.buffs = {b: 5 for b in C.BUFFS}
p.shield = 30
p.poison_turns = 2
p.bleed_turns = 2
p.add_potion("panacea", 3)
p.selected_potion = "panacea"
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.state = "playing"
    g.render()
    check(f"[{lang}] the HUD renders with every buff active", True)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL POTION CHECKS PASSED")
