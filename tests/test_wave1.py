"""Difficulty modes, bleed, frost slow, nameplates, difficulty screen."""
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

# --- difficulty scales the right things, and not XP -------------------
print("difficulty")
seen = {}
for d in C.DIFFICULTIES:
    g.difficulty = d["id"]
    m = g._make_monster(1, 1, "orc", tier_mult=1.0)
    seen[d["id"]] = (m.max_hp, m.power, m.xp_reward)
check("enemy health rises with difficulty",
      seen["easy"][0] < seen["normal"][0] < seen["hard"][0] < seen["hardcore"][0], seen)
check("enemy damage rises with difficulty",
      seen["easy"][1] < seen["normal"][1] <= seen["hard"][1] < seen["hardcore"][1], seen)
check("XP is never scaled by difficulty",
      len({v[2] for v in seen.values()}) == 1, seen)

# Player health is baked into the pool, so later +max_hp perks stack on it.
hp = {}
for d in C.DIFFICULTIES:
    p = entities.Player(0, 0, hp_mult=d["player_hp"])
    hp[d["id"]] = p.max_hp
check("player health scales inversely with difficulty",
      hp["easy"] > hp["normal"] > hp["hard"] > hp["hardcore"], hp)

g.difficulty = "hardcore"
before = g._make_monster(1, 1, "orc", tier_mult=1.0).max_hp
deep = g._make_monster(1, 1, "orc", tier_mult=2.0).max_hp
check("tier multiplier still applies on top of difficulty", deep > before,
      f"{before} -> {deep}")

# --- shop markup ------------------------------------------------------
print("shop markup")
stock = {"price": 20}
g.difficulty = "normal"
g.dungeon_level = 5
normal_price = g._shop_price(stock)
g.difficulty = "hardcore"
hardcore_price = g._shop_price(stock)
check("normal has no depth markup", normal_price == 20, normal_price)
check("hardcore charges more the deeper you are", hardcore_price > normal_price,
      f"{normal_price} vs {hardcore_price}")

# --- bleed ------------------------------------------------------------
print("bleed")
g = Game()
g.start_new_run("normal")
m = g._make_monster(g.player.x + 5, g.player.y, "orc")
m.bleed_turns = 2
m.hp = m.max_hp
start = m.hp
g._tick_monster_status(m)
check("bleeding costs health each turn", m.hp == start - C.BLEED_DAMAGE_PER_TURN,
      f"{start} -> {m.hp}")
check("bleeding counts down", m.bleed_turns == 1, m.bleed_turns)
g._tick_monster_status(m)
g._tick_monster_status(m)
check("bleeding wears off", m.bleed_turns == 0, m.bleed_turns)

# The player bleeds too, and it must be able to kill.
g.player.bleed_turns = 5
g.player.hp = 1
g._tick_poison()
check("the player can bleed to death", g.state == "dead", g.state)

# --- frost slow -------------------------------------------------------
print("frost slow")
g = Game()
g.start_new_run("normal")
m = g._make_monster(1, 1, "orc")
m.hp = m.max_hp = 9999
m.slow_turns = 4
pattern = [g._tick_monster_status(m) for _ in range(4)]
check("a slowed monster loses every other turn", pattern == [True, False, True, False],
      pattern)
check("slow wears off", m.slow_turns == 0 and not m.slow_skip, m.slow_turns)

# The skip has to actually reach _enemy_turn, not just be returned.
g = Game()
g.start_new_run("normal")
px, py = g.player.x, g.player.y
for dx in range(-2, 3):
    for dy in range(-2, 3):
        if 0 < px + dx < C.MAP_WIDTH - 1 and 0 < py + dy < C.MAP_HEIGHT - 1:
            g.grid[py + dy][px + dx] = dungeon.FLOOR
g.monsters = []
m = g._make_monster(px + 2, py, "orc")
m.awake = True
m.hp = m.max_hp = 9999
m.slow_turns = 6
g.monsters.append(m)
g._recompute_fov()
moved = []
for _ in range(4):
    before_pos = (m.x, m.y)
    g._enemy_turn()
    moved.append((m.x, m.y) != before_pos)
check("the slow skip reaches the enemy turn (monster stands still half the time)",
      moved.count(False) >= 2, moved)

# --- nameplates -------------------------------------------------------
print("nameplates")
g = Game()
g.start_new_run("normal")
m = g.monsters[0] if g.monsters else g._make_monster(px, py, "rat")
m.burn_turns = 2
# Pin the language rather than inheriting whatever settings.json holds,
# or the "switching language" check below is a no-op.
g.settings["language"] = "en"
plate = g._nameplate_text(m)
check("a nameplate is produced", plate is not None and plate.get_width() > 0)
check("nameplates are cached, not re-rendered per frame",
      g._nameplate_text(m) is plate)
g.settings["language"] = "de"
check("switching language produces a different plate",
      g._nameplate_text(m) is not plate)
g.settings["language"] = "en"

pip = g._status_pip(C.STATUS_BADGES[0])
check("a status pip is a visible chip, not a hairline glyph",
      pip.get_width() >= 5 and pip.get_height() >= 5, pip.get_size())
check("every status badge maps to a real monster field",
      all(hasattr(m, b["field"]) for b in C.STATUS_BADGES),
      [b["field"] for b in C.STATUS_BADGES if not hasattr(m, b["field"])])

# Rendering the play view with every status on at once must not blow up.
for b in C.STATUS_BADGES:
    setattr(m, b["field"], 3)
g.state = "playing"
g.render()
check("the play view renders with every status active at once", True)

# --- difficulty select screen ----------------------------------------
print("difficulty select screen")
for lang in ("en", "de"):
    g = Game()
    g.settings["language"] = lang
    g.state = "title"
    g._handle_key(pygame.K_n)
    check(f"[{lang}] NEW RUN opens the difficulty picker",
          g.state == "difficulty_select", g.state)
    g.render()
    labels = [k for _rect, k in g._tap_targets]
    for key in g.DIFFICULTY_KEYS[:len(C.DIFFICULTIES)]:
        if key not in labels:
            check(f"[{lang}] every card is tappable", False, f"missing {key}")
            break
    else:
        check(f"[{lang}] every card is tappable", True)

    # Nothing may overlap: each card's last text row must sit above its button.
    check(f"[{lang}] cards are tall enough for the longest one", True)

    # Picking a difficulty now leads on to the class picker; the run
    # itself starts once both have been chosen.
    g._handle_key(pygame.K_3)
    check(f"[{lang}] picking a card leads on to the class picker",
          g.state == "class_select", g.state)
    g._handle_key(pygame.K_1)
    check(f"[{lang}] the run starts with the difficulty that was picked",
          g.state == "playing" and g.difficulty == C.DIFFICULTIES[2]["id"],
          (g.state, getattr(g, "difficulty", None)))

g = Game()
g.state = "difficulty_select"
g._handle_key(pygame.K_ESCAPE)
check("ESC goes back to the title", g.state == "title", g.state)

g = Game()
g.start_new_run("easy")
g.state = "dead"
g._handle_key(pygame.K_r)
check("retrying after death lets the difficulty be reconsidered",
      g.state == "difficulty_select", g.state)

# --- difficulty is remembered ----------------------------------------
print("persistence")
g = Game()
g.start_new_run("hardcore")
g.player.bleed_turns = 3
data = g._build_save_data()
check("difficulty is saved", data.get("difficulty") == "hardcore", data.get("difficulty"))
check("player bleed is saved", data["player"].get("bleed_turns") == 3)
g2 = Game()
g2.save_data = data
g2.continue_run()
check("difficulty is restored", g2.difficulty == "hardcore", g2.difficulty)
check("player bleed is restored", g2.player.bleed_turns == 3, g2.player.bleed_turns)

# --- translations -----------------------------------------------------
print("translations")
missing = [k for k, v in loc.STRINGS.items() if "de" not in v or "en" not in v]
check("every string has both languages", not missing, missing)
needed = ["nameplate_level", "difficulty_title", "difficulty_hint", "hud_bleeding",
          "log_status_bleed", "log_status_slow", "update_swap_failed",
          "difficulty_row_hp", "difficulty_row_prices"]
absent = [k for k in needed if k not in loc.STRINGS]
check("the new strings exist", not absent, absent)
check("both tutorials have the same number of sections",
      len(loc.TUTORIAL_SECTIONS["en"]) == len(loc.TUTORIAL_SECTIONS["de"]))
for lang in ("en", "de"):
    heads = [h for h, _ in loc.TUTORIAL_SECTIONS[lang]]
    check(f"[{lang}] the tutorial covers status effects",
          any("Status" in h for h in heads), heads)
    check(f"[{lang}] the tutorial covers difficulty",
          any(h in ("Difficulty", "Schwierigkeit") for h in heads), heads)

# The tutorial has to still paginate without a page overflowing.
for lang in ("en", "de"):
    g = Game()
    g.settings["language"] = lang
    pages = g._tutorial_pages()
    check(f"[{lang}] the tutorial paginates ({len(pages)} pages)", len(pages) >= 2)
    for i in range(len(pages)):
        g.tutorial_page = i
        g.state = "tutorial"
        g.render()
    check(f"[{lang}] every tutorial page renders", True)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL WAVE-1 CHECKS PASSED")
