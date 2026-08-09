"""On-screen controls, their keyboard hints, the HUD band, music rotation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import sdl_stub  # noqa: F401
import constants as C
import dungeon
import game as _G
from game import Game

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


g = Game()
g.settings["language"] = "de"


def all_buttons(gm):
    r = {"MENU": gm.save_button, "TOOLS": gm.tools_button,
         "HEAL": gm.potion_button, "BAG": gm.bag_button}
    r.update({f"scroll-{k}": v for k, v in gm.scroll_buttons.items()})
    r.update({f"dpad-{k}": rect for k, (rect, _v, _l) in gm.dpad_buttons.items()})
    return r


def layout_problems(gm):
    map_bottom = C.MAP_HEIGHT * C.TILE_SIZE
    rects = all_buttons(gm)
    names = list(rects)
    overlap = [f"{a}/{b}" for i, a in enumerate(names) for b in names[i + 1:]
               if rects[a].colliderect(rects[b])]
    off = [n for n, r in rects.items()
           if r.top < 0 or r.bottom > map_bottom
           or r.left < 0 or r.right > C.SCREEN_WIDTH]
    return overlap, off


# --- the on-screen buttons --------------------------------------------
print("touch controls")
overlap, off = layout_problems(g)
check("[PC] no two buttons overlap", not overlap, overlap)
check("[PC] every button is on screen and above the HUD", not off, off)

_G.ON_ANDROID = False
check("[PC] the heal button names its key", "(G)" in g._touch_label("touch_heal", "G"),
      g._touch_label("touch_heal", "G"))
check("[PC] the bag button names its key", "(I)" in g._touch_label("btn_bag", "I"))
check("[PC] the menu button names its key", "(ESC)" in g._touch_label("touch_menu", "ESC"))
_G.ON_ANDROID = True
check("[phone] no key hint, there is no keyboard",
      g._touch_label("touch_heal", "G") == g.t("touch_heal"))
_G.ON_ANDROID = False

# The key and the button must do the same thing.
g.start_new_run("normal", "warrior")
p = g.player
p.potion_counts = {"healing": 2}
p.selected_potion = "healing"
p.hp = max(1, p.max_hp // 2)
g.state = "playing"
before = p.hp
g._handle_key(pygame.K_g)
check("G drinks a potion", p.hp > before and p.potion_count("healing") == 1,
      (before, p.hp, p.potion_counts))
p.hp = max(1, p.max_hp // 2)
before = p.hp
g.state = "playing"
g._handle_tap(g.potion_button.center)
check("the heal button drinks a potion",
      p.hp > before and p.potion_count("healing") == 0, (before, p.hp))

# --- the HUD has to fit the band it is given --------------------------
print("hud fits its band")
p.weapon_name, p.weapon_bonus, p.weapon_element_id = "Long Sword", 6, "fire"
p.armor_name, p.armor_bonus = "Chainmail", 3
equipment = [("weapon", "Long Sword +6", None, None),
             ("armor", "Chainmail +3", None, None)]
supplies = [("potion", "x3", None, None), ("gold", "340", None, None)]
buffs = [("!", "Haste 4", None, None), ("!", "Strength 9", None, None)]

rows = g._hud_rows(equipment, supplies, buffs, fits=3)
check("with room, all three rows are drawn", len(rows) == 3, len(rows))
check("with room, supplies come first", rows[0] is supplies)
check("with room, effects come before equipment",
      rows[1] is buffs and rows[2] is equipment)

rows = g._hud_rows(equipment, supplies, buffs, fits=2)
check("with two rows, nothing is dropped outright", len(rows) == 2, len(rows))
check("with two rows, the effects row survives", rows[1] is buffs)
kinds = [c[0] for c in rows[0]]
check("the equipment folds into the supplies row",
      "weapon" in kinds and "armor" in kinds, kinds)
folded = dict((c[0], c[1]) for c in rows[0])
check("the folded weapon keeps its bonus", "+6" in folded["weapon"], folded["weapon"])
check("the folded weapon keeps its element",
      g.te("fire") in folded["weapon"], folded["weapon"])

rows = g._hud_rows(equipment, supplies, [], fits=3)
check("no active effects means no empty effects row", len(rows) == 2, len(rows))

# --- and all of it on a real phone canvas -----------------------------
print("phone canvas")
saved = (C.TILE_SIZE, C.MAP_PIXEL_WIDTH, C.HUD_HEIGHT, C.SCREEN_HEIGHT,
         C.GUTTER_WIDTH, C.MAP_OFFSET_X, C.SCREEN_WIDTH)
try:
    win_w, win_h = 2448, 1098          # measured on the real device
    tile = max(24, min((win_w - 2 * C.MIN_GUTTER_WIDTH) // C.MAP_WIDTH,
                       (win_h - C.MIN_HUD_HEIGHT) // C.MAP_HEIGHT))
    C.TILE_SIZE = tile
    C.MAP_PIXEL_WIDTH = C.MAP_WIDTH * tile
    g._rescale_tile_constants()
    mh = C.MAP_HEIGHT * tile
    C.HUD_HEIGHT = max(190, win_h - mh)
    C.SCREEN_HEIGHT = mh + C.HUD_HEIGHT
    gut = max(C.MIN_GUTTER_WIDTH, (win_w - C.MAP_PIXEL_WIDTH) // 2)
    C.GUTTER_WIDTH = gut
    C.MAP_OFFSET_X = gut
    C.SCREEN_WIDTH = C.MAP_PIXEL_WIDTH + 2 * gut
    _G.ON_ANDROID = True
    g.ui_scale = C.HUD_HEIGHT / 190
    g._build_ui_metrics()
    g._setup_touch_controls()
    g.screen = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), 0, 32)

    share = (C.MAP_PIXEL_WIDTH * mh) / (C.SCREEN_WIDTH * C.SCREEN_HEIGHT)
    print(f"       tile {tile}, map {C.MAP_PIXEL_WIDTH}x{mh}, HUD {C.HUD_HEIGHT} "
          f"({C.HUD_HEIGHT / C.SCREEN_HEIGHT * 100:.0f}% tall), "
          f"play area {share * 100:.0f}%")
    check("the phone gets a bigger tile than the old 33", tile >= 34, tile)
    check("the HUD is under a quarter of the height",
          C.HUD_HEIGHT / C.SCREEN_HEIGHT < 0.22, C.HUD_HEIGHT / C.SCREEN_HEIGHT)
    check("the play area is at least 45% of the screen", share >= 0.45, share)

    overlap, off = layout_problems(g)
    check("[phone] no two buttons overlap", not overlap, overlap)
    check("[phone] every button is on screen and above the HUD", not off, off)

    gap = g.gap_s
    chip_h = g.f_sm.get_height() + gap
    hud_y = mh
    y = hud_y + gap + chip_h + gap
    fits = max(1, (hud_y + C.HUD_HEIGHT - gap - y + gap) // (chip_h + gap))
    check("at least two chip rows fit", fits >= 2, fits)
    rows = g._hud_rows(equipment, supplies, buffs, fits)
    check("the phone still shows active effects", any(r is buffs for r in rows))
    bottom = y + len(rows) * (chip_h + gap) - gap
    check("the last chip row ends inside the band",
          bottom <= hud_y + C.HUD_HEIGHT, (bottom, hud_y + C.HUD_HEIGHT))

    p.buffs = {"strength": 9, "haste": 4}
    p.add_potion("greater_healing", 3)
    g.state = "playing"
    g.render()
    check("the phone play view renders", True)
finally:
    (C.TILE_SIZE, C.MAP_PIXEL_WIDTH, C.HUD_HEIGHT, C.SCREEN_HEIGHT,
     C.GUTTER_WIDTH, C.MAP_OFFSET_X, C.SCREEN_WIDTH) = saved
    _G.ON_ANDROID = False
    g._rescale_tile_constants()
    g._build_ui_metrics()
    g._setup_touch_controls()
    g.screen = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), 0, 32)

# --- music must not repeat the same track floor after floor -----------
print("music rotation")
g.start_new_run("normal", "warrior")
tracks = []
for lvl in range(1, 16):
    g.dungeon_level = lvl
    g.new_level()
    tracks.append(g._music_track)
check("a track is always playing", all(tracks), tracks)
repeats = sum(1 for a, b in zip(tracks, tracks[1:]) if a == b)
check("no floor repeats the previous floor's track", repeats == 0, tracks)
check("more than one track gets used", len(set(tracks)) > 1, set(tracks))
check("every track played is one that exists",
      set(tracks) <= set(C.MUSIC_TRACKS), set(tracks) - set(C.MUSIC_TRACKS))

for lvl in (1, 11, 21):
    g.dungeon_level = lvl
    g._music_track = "something-else.mp3"
    g.new_level()
    tier = g._tier_for_level(lvl)
    check(f"floor {lvl} leads with its theme's own track",
          g._music_track == tier["music"], (g._music_track, tier["music"]))

g.settings["music"] = False
g._music_track = None
g.dungeon_level = 4
g.new_level()
check("music off means no track is started", g._music_track is None, g._music_track)
g.settings["music"] = True

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL UI / MUSIC CHECKS PASSED")
