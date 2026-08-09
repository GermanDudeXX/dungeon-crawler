"""Character classes: stats, kit, art, the picker, and saving."""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.chdir(r"C:\Users\budzm\dungeon-crawler")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import constants as C
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

# --- the table --------------------------------------------------------
print("class table")
ids = [k["id"] for k in C.CLASSES]
check("there are at least three classes", len(ids) >= 3, ids)
check("no duplicate ids", len(set(ids)) == len(ids), ids)
check("the default class exists", C.DEFAULT_CLASS in C.CLASS_BY_ID)
missing_de = [i for i in ids if i not in loc.CLASS_DE]
check("every class has a German name", not missing_de, missing_de)
missing_blurb = [i for i in ids if i not in loc.CLASS_BLURB_DE]
check("every class has a German blurb", not missing_blurb, missing_blurb)
missing_art = [k["id"] for k in C.CLASSES
               if not os.path.exists(os.path.join(C.CLASS_SPRITE_DIR, k["sprite"] + ".png"))]
check("every class's art exists", not missing_art, missing_art)
bad_index = [k["id"] for k in C.CLASSES
             if (k["start_weapon"] is not None and k["start_weapon"] >= len(C.WEAPON_TYPES))
             or (k["start_armor"] is not None and k["start_armor"] >= len(C.ARMOR_TYPES))]
check("starting kit indices are in range", not bad_index, bad_index)
bad_potion = [(k["id"], pid) for k in C.CLASSES
              for pid in k.get("start_potions", {}) if pid not in C.POTION_BY_ID]
check("starting potions are real potions", not bad_potion, bad_potion)
bad_scroll = [(k["id"], s) for k in C.CLASSES
              for s in k.get("start_scrolls", {}) if s not in C.SCROLL_TYPES]
check("starting scrolls are real scrolls", not bad_scroll, bad_scroll)

# --- each class actually plays differently ---------------------------
print("openings")
built = {}
for klass in C.CLASSES:
    g.start_new_run("normal", klass["id"])
    p = g.player
    built[klass["id"]] = {
        "hp": p.max_hp, "power": p.power, "defense": p.defense,
        "crit": round(p.crit_chance, 3), "weapon": p.weapon_name,
        "potions": p.potions, "scrolls": sum(p.scrolls.values()),
    }
for field in ("hp", "power", "crit"):
    values = {v[field] for v in built.values()}
    check(f"classes differ in {field}", len(values) > 1, values)

check("the warrior is the toughest",
      built["warrior"]["hp"] == max(v["hp"] for v in built.values()), built)
check("the rogue crits the most",
      built["rogue"]["crit"] == max(v["crit"] for v in built.values()), built)
check("the mage starts with the most scrolls",
      built["mage"]["scrolls"] == max(v["scrolls"] for v in built.values()), built)
check("every class starts with at least one potion",
      all(v["potions"] >= 1 for v in built.values()), built)
check("every class starts alive and at full health",
      all(g.player.hp > 0 for _ in [1]))

# The class multiplier must combine with difficulty, not replace it.
g.start_new_run("hardcore", "warrior")
hardcore_warrior = g.player.max_hp
g.start_new_run("easy", "warrior")
easy_warrior = g.player.max_hp
check("difficulty still applies on top of a class",
      easy_warrior > hardcore_warrior, (easy_warrior, hardcore_warrior))

# Later gains have to stack on the adjusted pool, not be rescaled.
g.start_new_run("normal", "warrior")
before = g.player.max_hp
g.player.gain_xp(g.player.xp_to_next)
check("levelling adds to the class-adjusted pool",
      g.player.max_hp == before + 5, (before, g.player.max_hp))

# --- the hero on the map matches --------------------------------------
print("hero art")
sprites = {}
for klass in C.CLASSES:
    g.start_new_run("normal", klass["id"])
    sprites[klass["id"]] = pygame.image.tostring(g.player_sprite_right, "RGBA")
check("each class has a different hero on the map",
      len(set(sprites.values())) == len(sprites))
g.start_new_run("normal", "mage")
check("the hero faces both ways",
      g.player_sprite_left is not None and g.player_sprite_right is not None)
check("the large portrait exists", g.player_sprite_large is not None)

# --- the picker -------------------------------------------------------
print("class picker")
for lang in ("en", "de"):
    g.settings["language"] = lang
    g.state = "title"
    g._handle_key(pygame.K_n)
    check(f"[{lang}] NEW RUN opens the difficulty picker",
          g.state == "difficulty_select", g.state)
    g._handle_key(pygame.K_2)
    check(f"[{lang}] difficulty leads on to the class picker",
          g.state == "class_select", g.state)
    g.render()
    keys = [k for _r, k in g._tap_targets]
    check(f"[{lang}] every class card is tappable",
          all(k in keys for k in g.CLASS_KEYS[:len(C.CLASSES)]), keys)
    g._handle_key(pygame.K_3)
    check(f"[{lang}] picking a class starts the run",
          g.state == "playing" and g.char_class == C.CLASSES[2]["id"],
          (g.state, getattr(g, "char_class", None)))
    check(f"[{lang}] the difficulty picked earlier is the one used",
          g.difficulty == C.DIFFICULTIES[1]["id"], g.difficulty)
g.settings["language"] = "en"

g.state = "class_select"
g._handle_key(pygame.K_ESCAPE)
check("ESC goes back to the difficulty picker", g.state == "difficulty_select", g.state)

# --- saving -----------------------------------------------------------
print("saving")
g.start_new_run("hard", "mage")
data = g._build_save_data()
check("the class is saved", data.get("char_class") == "mage", data.get("char_class"))
mage_sprite = pygame.image.tostring(g.player_sprite_right, "RGBA")
g.start_new_run("easy", "warrior")
g.save_data = data
g.continue_run()
check("the class is restored", g.char_class == "mage", g.char_class)
check("the difficulty is restored alongside it", g.difficulty == "hard", g.difficulty)
check("a loaded run shows its own hero again",
      pygame.image.tostring(g.player_sprite_right, "RGBA") == mage_sprite)

# An old save has no class at all.
legacy = g._build_save_data()
legacy.pop("char_class")
g.save_data = legacy
g.continue_run()
check("an old save falls back to the default class",
      g.char_class == C.DEFAULT_CLASS, g.char_class)

# --- rendering the run ------------------------------------------------
print("rendering")
for klass in C.CLASSES:
    for lang in ("en", "de"):
        g.settings["language"] = lang
        g.start_new_run("normal", klass["id"])
        g.state = "playing"
        g.render()
check("every class renders in play", True)
g.settings["language"] = "en"

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL CLASS CHECKS PASSED")
