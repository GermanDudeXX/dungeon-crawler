"""The blacksmith, the guarded vault, the test room, and the title hero."""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.chdir(r"C:\Users\budzm\dungeon-crawler")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401  - lets this file build several Games

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

# --- the blacksmith ---------------------------------------------------
print("blacksmith")
g.start_new_run("normal", "warrior")
p = g.player
p.gold = 5000
offers = g._smith_offers()
ids = [o["id"] for o in offers]
check("the smith offers weapon, armour, enchant and reforge",
      set(ids) == {"weapon", "armor", "enchant", "reforge"}, ids)
check("no offer label is left with a blank in it",
      all("( )" not in o["label"] and "()" not in o["label"] for o in offers),
      [o["label"] for o in offers])

before = p.weapon_bonus
g._smith_buy(ids.index("weapon"))
check("sharpening raises the weapon bonus", p.weapon_bonus > before,
      f"{before} -> {p.weapon_bonus}")
check("sharpening costs gold", p.gold < 5000, p.gold)

before_armor = p.armor_bonus
g._smith_buy([o["id"] for o in g._smith_offers()].index("armor"))
check("reinforcing raises the armour bonus", p.armor_bonus > before_armor)

check("the starter weapon has no element yet", p.weapon_element_id is None)
g._smith_buy([o["id"] for o in g._smith_offers()].index("enchant"))
check("enchanting gives the weapon an element", p.weapon_element_id in C.ELEMENTS,
      p.weapon_element_id)
# Re-enchanting must never hand back the element it already had.
for _ in range(20):
    had = p.weapon_element_id
    p.gold = 5000
    g._smith_buy([o["id"] for o in g._smith_offers()].index("enchant"))
    if p.weapon_element_id == had:
        check("re-enchanting always changes the element", False, had)
        break
else:
    check("re-enchanting always changes the element", True)

p.gold = 5000
p.weapon_rarity_id = None
bonus_before = p.weapon_bonus
g._smith_buy([o["id"] for o in g._smith_offers()].index("reforge"))
check("reforging raises the rarity", p.weapon_rarity_id is not None, p.weapon_rarity_id)
check("reforging also raises the bonus", p.weapon_bonus > bonus_before,
      f"{bonus_before} -> {p.weapon_bonus}")

# At the top rarity it must refuse and refund rather than silently charging.
p.weapon_rarity_id = C.RARITY_TIERS[-1]["id"]
p.gold = 5000
bonus_before = p.weapon_bonus
g._smith_buy([o["id"] for o in g._smith_offers()].index("reforge"))
check("reforging the best rarity refunds instead of charging", p.gold == 5000, p.gold)
check("reforging the best rarity changes nothing", p.weapon_bonus == bonus_before)

# Prices climb, and you cannot buy what you cannot afford.
cheap = g._smith_price(0)
dear = g._smith_price(10)
check("upgrades get dearer the better the item is", dear > cheap, (cheap, dear))
p.gold = 0
bonus_before = p.weapon_bonus
g._smith_buy(0)
check("a broke player buys nothing", p.weapon_bonus == bonus_before and p.gold == 0)

# Bare hands: nothing to sharpen, but the screen must still work.
g.start_new_run("normal", "mage")
g.player.weapon_name = "Fists"
g.player.weapon_bonus = 0
g.player.armor_name = "None"
g.player.armor_bonus = 0
check("with no gear the smith offers nothing", not g._smith_offers(),
      g._smith_offers())
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.state = "smith"
    g.render()
    check(f"[{lang}] the empty smith screen renders", True)
    g.start_new_run("normal", "warrior")
    g.player.gold = 500
    g.state = "smith"
    g.render()
    keys = [k for _r, k in g._tap_targets]
    check(f"[{lang}] every offer is tappable",
          all(k in keys for k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)),
          keys)
g.settings["language"] = "en"

# He has to be reachable by walking into him, and block movement.
g.start_new_run("normal", "warrior")
g.dungeon_level = 8
g.new_level()
px, py = g.player.x, g.player.y
g.grid[py][px + 1] = dungeon.FLOOR
g.monsters = []
g.blacksmiths = [entities.Blacksmith(px + 1, py)]
g._player_turn(1, 0)
check("walking into the smith opens his screen", g.state == "smith", g.state)
check("the smith is not walked through", (g.player.x, g.player.y) == (px, py))
check("the smith counts as occupying his tile", g._is_occupied(px + 1, py))

# He turns up on his own, and survives a save.
g.start_new_run("normal", "warrior")
seen = 0
for lvl in range(C.BLACKSMITH_MIN_LEVEL, 30):
    g.dungeon_level = lvl
    g.new_level()
    if g.blacksmiths:
        seen += 1
check("smiths appear on their own", seen >= 3, seen)
early = 0
g.dungeon_level = C.BLACKSMITH_MIN_LEVEL - 1
for _ in range(40):
    g.new_level()
    if g.blacksmiths:
        early += 1
check("smiths are gated by depth", early == 0, early)

g.dungeon_level = 10
for _ in range(40):
    g.new_level()
    if g.blacksmiths:
        break
want = [(b.x, b.y) for b in g.blacksmiths]
data = g._build_save_data()
g.save_data = data
g.continue_run()
check("the smith survives a save", [(b.x, b.y) for b in g.blacksmiths] == want,
      [(b.x, b.y) for b in g.blacksmiths])

# --- the guarded vault ------------------------------------------------
print("guarded vault")
g.start_new_run("normal", "warrior")
found = 0
for lvl in range(C.VAULT_MIN_LEVEL, 40):
    g.dungeon_level = lvl
    g.new_level()
    if g.vault_pos:
        found += 1
check("vaults turn up", found >= 3, found)

for _ in range(120):
    g.dungeon_level = 12
    g.new_level()
    if g.vault_pos:
        break
check("a vault was generated", g.vault_pos is not None)
guards = [m for m in g.monsters if m.guards_vault]
check("a vault has a crowd, not one monster", len(guards) >= C.VAULT_GUARDS[0],
      len(guards))
check("every vault guard is an elite", all(m.elite_name for m in guards))
check("vault guards start awake", all(m.awake for m in guards))
near = [i for i in g.items
        if abs(i.x - g.vault_pos[0]) <= 3 and abs(i.y - g.vault_pos[1]) <= 3]
check("a vault has loot in it", len(near) >= 3, len(near))
data = g._build_save_data()
g.save_data = data
g.continue_run()
check("vault guards are still guards after a save",
      sum(1 for m in g.monsters if m.guards_vault) == len(guards))

# --- superboss and mimic names ---------------------------------------
# These prefixes used to be baked into monster.name, which the German
# display name rebuilds from parts - so they vanished in German.
print("names")
for lang in ("en", "de"):
    g.settings["language"] = lang
    sb = g._make_monster(1, 1, "spider", boss=True)
    g._promote_to_superboss(sb)
    check(f"[{lang}] a superboss is named as one",
          g.t("superboss_prefix") in g._monster_display_name(sb),
          g._monster_display_name(sb))
    mi = g._make_monster(1, 1, "slime")
    mi.is_mimic = True
    check(f"[{lang}] a mimic is named as one",
          g.t("mimic_prefix") in g._monster_display_name(mi),
          g._monster_display_name(mi))
    plain = g._make_monster(1, 1, "rat")
    check(f"[{lang}] an ordinary monster gets no prefix",
          g.t("superboss_prefix") not in g._monster_display_name(plain)
          and g.t("mimic_prefix") not in g._monster_display_name(plain),
          g._monster_display_name(plain))
g.settings["language"] = "en"

# The prefix must survive a save without storing translated text.
g.start_new_run("normal", "warrior")
g.dungeon_level = C.SUPERBOSS_LEVEL
g.new_level()
data = g._build_save_data()
check("no translated name is written into the save",
      all("name" not in m for m in data["monsters"]), data["monsters"][:1])
g.save_data = data
g.continue_run()
sb = next((m for m in g.monsters if m.is_superboss), None)
check("a superboss is still one after a save", sb is not None)
if sb:
    check("its title comes back too",
          g.t("superboss_prefix") in g._monster_display_name(sb),
          g._monster_display_name(sb))

# --- the test room ----------------------------------------------------
print("test room")
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.state = "title"
    g._handle_key(pygame.K_d)
    check(f"[{lang}] the title's test-room button starts it",
          g.state == "playing", g.state)

    kinds_present = {m.kind for m in g.monsters}
    check(f"[{lang}] every monster kind is present",
          kinds_present == set(C.MONSTER_TYPES), set(C.MONSTER_TYPES) - kinds_present)
    check(f"[{lang}] every elite modifier is present",
          {m.elite_name for m in g.monsters if m.elite_name} >=
          {e["name"] for e in C.ELITE_MODIFIERS},
          {m.elite_name for m in g.monsters if m.elite_name})
    check(f"[{lang}] a boss is present", any(m.is_boss for m in g.monsters))
    check(f"[{lang}] a superboss is present", any(m.is_superboss for m in g.monsters))
    check(f"[{lang}] a mini-boss is present", any(m.is_mini_boss for m in g.monsters))
    check(f"[{lang}] a mimic is present", any(m.is_mimic for m in g.monsters))
    check(f"[{lang}] a chest guardian is present", any(m.guards_chest for m in g.monsters))
    check(f"[{lang}] vault guards are present", any(m.guards_vault for m in g.monsters))
    check(f"[{lang}] every trap type is present",
          set(g.traps.values()) == set(C.TRAP_TYPES), set(g.traps.values()))
    check(f"[{lang}] every hazard type is present",
          set(g.hazards.values()) == set(C.HAZARD_TYPES), set(g.hazards.values()))
    kinds = {i.kind for i in g.items}
    check(f"[{lang}] every item kind is present",
          kinds >= {"weapon", "armor", "scroll", "gold", "potion"}, kinds)
    check(f"[{lang}] a merchant is present", g.merchants)
    check(f"[{lang}] a blacksmith is present", g.blacksmiths)
    check(f"[{lang}] a shrine is present", g.shrine_pos is not None)
    check(f"[{lang}] a chest is present", g.chest_pos is not None)
    check(f"[{lang}] a boss door is present", g.boss_door_pos is not None)
    check(f"[{lang}] decorations are present", len(g._decor) >= 5, len(g._decor))
    check(f"[{lang}] both staircases are present",
          g.stairs_pos is not None and g.up_stairs_pos is not None)
    check(f"[{lang}] you start with every potion", len(g.player.potion_counts) >= 25,
          len(g.player.potion_counts))
    check(f"[{lang}] you start with gold to spend", g.player.gold >= 1000)

    # Nothing may share a tile - it is meant to be readable at a glance.
    taken = [(m.x, m.y) for m in g.monsters]
    taken += [(b.x, b.y) for b in g.blacksmiths] + [(m.x, m.y) for m in g.merchants]
    check(f"[{lang}] nothing is stacked on the same tile",
          len(taken) == len(set(taken)),
          [t for t in taken if taken.count(t) > 1])
    check(f"[{lang}] the player does not start inside something",
          (g.player.x, g.player.y) not in taken)

    # And it has to be a real, playable level.
    g.explored = {(x, y) for y in range(C.MAP_HEIGHT) for x in range(C.MAP_WIDTH)}
    g.visible = set(g.explored)
    g._map_cache = None
    g.render()
    g._enemy_turn()
    g._player_turn(0, 1)
    check(f"[{lang}] the test room plays without falling over", True)
g.settings["language"] = "en"

# --- the title hero ---------------------------------------------------
print("title hero")
sprites = {}
for klass in C.CLASSES:
    # Both, the way __init__ does it: _class() reads the attribute, and
    # the attribute is seeded from the setting at startup.
    g.settings["char_class"] = klass["id"]
    g.char_class = klass["id"]
    g._use_class_sprite(g._class())
    sprites[klass["id"]] = pygame.image.tostring(g.player_sprite_large, "RGBA")
    g.state = "title"
    g.render()
check("the title shows a different hero per class",
      len(set(sprites.values())) == len(sprites))

# The startup path itself: the attribute has to be seeded from the
# setting, or _class() falls back to the default and the title always
# shows a Warrior however you last played.
src = open("game.py", encoding="utf-8").read()
seed = 'self.char_class = self.settings.get("char_class", C.DEFAULT_CLASS)'
check("startup seeds the class from settings before using its art",
      seed in src and src.index(seed) < src.index("def _apply_pc_ui_scale"))

# --- translations -----------------------------------------------------
print("translations")
needed = ["smith_title", "smith_nothing", "smith_weapon", "smith_armor",
          "smith_enchant", "smith_reenchant", "smith_reforge", "btn_forge",
          "log_smith_weapon", "log_smith_armor", "log_smith_enchant",
          "log_smith_reforge", "log_smith_best_already",
          "btn_testroom", "log_testroom"]
absent = [k for k in needed if k not in loc.STRINGS]
check("every new string exists", not absent, absent)
half = [k for k in needed if k in loc.STRINGS
        and ("de" not in loc.STRINGS[k] or "en" not in loc.STRINGS[k])]
check("every new string has both languages", not half, half)
check("the blacksmith's art exists", os.path.exists(C.BLACKSMITH_SPRITE_PATH))

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL BLACKSMITH / VAULT / TEST-ROOM CHECKS PASSED")
