"""Drawing and copying only what moved must look exactly like doing it all.

On the phone the frame is dominated by two things that scale with area:
painting the furniture around the dungeon view, and copying the canvas
onto the display surface, which lives in memory the CPU writes to
slowly. Almost every frame, everything except the dungeon view is the
same picture as the frame before - so it is neither repainted nor
copied.

That is only safe if nothing is ever left stale, and a stale region is
invisible in any test that renders one frame and looks at it. So this
plays a sequence - walking, taking damage, drinking, opening a menu and
coming back - and after every single frame compares the *display*
against the same game drawn the slow way, pixel for pixel.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["ANDROID_ARGUMENT"] = "1"

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401

pygame.init()
pygame.display.get_window_size = lambda: (2448, 1098)

import constants as C
import persistence
import game

settings = persistence.load_settings()
settings["render_scale"] = 1.0
# Off for the comparison: the frame-rate overlay counts the frames it is
# asked to draw, so drawing the same moment twice legitimately produces
# two different numbers. It gets its own check at the end.
settings["show_fps"] = False
persistence.save_settings(settings)

g = game.Game()
g.start_new_run()
g.state = "playing"


def as_bytes(surface):
    return pygame.image.tostring(surface, "RGB")


def check(label):
    """One frame the cheap way, then the same frame the slow way.

    The screen shake picks a fresh random offset every time it draws, so
    the two passes have to start from the same random state or they
    disagree for a reason that has nothing to do with what is being
    tested.
    """
    seed = random.getstate()
    g.render()
    cheap = as_bytes(g.display)

    random.setstate(seed)
    g._furniture_sig = None          # forces the whole canvas
    g.render()
    if cheap != as_bytes(g.display):
        raise AssertionError(
            f"the screen differs from a full redraw after: {label}")


steps = 0
check("the first frame")

# --- walking: the case that has to be cheap ------------------------------
for _ in range(12):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if not g.blocks_movement(g.player.x + dx, g.player.y + dy):
            g._player_turn(dx, dy)
            steps += 1
            break
    # Several frames per step, the way the animation actually runs.
    for _ in range(3):
        g._update_animations()
        check(f"walking, step {steps}")
print(f"  {steps} Schritte gelaufen, jedes Bild deckungsgleich")

# --- things that change the furniture and must reach the screen ----------
p = g.player
events = [
    ("Schaden genommen", lambda: g._hurt_player(3)),
    ("Gold aufgesammelt", lambda: setattr(p, "gold", p.gold + 25)),
    ("Trank getrunken", lambda: p.add_potion(p.selected_potion, 2)),
    ("Meldung im Protokoll", lambda: g.add_log("etwas ist passiert")),
    ("Banner eingeblendet", lambda: g._notify("Test", C.COLOR_ACCENT)),
    ("Richtung gehalten", lambda: setattr(g, "touch_direction", (1, 0))),
    ("Richtung losgelassen", lambda: setattr(g, "touch_direction", None)),
    ("Bildschirm-Tasten aus", lambda: g.settings.__setitem__("show_touch_controls", False)),
    ("Bildschirm-Tasten an", lambda: g.settings.__setitem__("show_touch_controls", True)),
]
for label, change in events:
    change()
    check(label)
    # ...and the frame after, when it is cheap again.
    check(label + " (Folgebild)")
print(f"  {len(events)} Ereignisse, jedes davon auf dem Schirm angekommen")

# --- a banner fading out, which changes the picture every tick -----------
for i in range(6):
    g._update_animations()
    check(f"Banner blendet aus, Bild {i}")
print("  ausblendendes Banner bleibt deckungsgleich")

# --- a fight, which is the part that still stuttered ---------------------
# The damage flash, damage numbers, sparks and a boss bar all draw over
# the dungeon view, and none of them force a full frame any more - so if
# any of them left something behind, this is where it shows.
def put_monster_next_to_player(boss=False):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1)):
        x, y = g.player.x + dx, g.player.y + dy
        if g._tile_is_free(x, y):
            m = g._make_monster(x, y, "goblin", boss=boss)
            m.awake = True
            m.snap()
            m.max_hp = m.hp = 9999
            g.monsters.append(m)
            return m
    return None


g.player.max_hp = g.player.hp = 999999
foe = put_monster_next_to_player()
assert foe is not None, "no room next to the player to put a monster"
for turn in range(6):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if any(m.x == g.player.x + dx and m.y == g.player.y + dy
               for m in g.monsters if m.is_alive()):
            g._player_turn(dx, dy)
            break
    for f in range(4):
        g._update_animations()
        check(f"fighting, turn {turn} frame {f}")
print("  Kampf mit Trefferblitz und Schadenszahlen bleibt deckungsgleich")

# A boss brings the health bar and the announcement banner with it, both
# of which reach outside the dungeon view.
boss = put_monster_next_to_player(boss=True)
if boss is not None:
    g.boss_banner_timer = 90
    for f in range(8):
        g._update_animations()
        check(f"boss on screen, frame {f}")
    boss.hp = 1
    check("boss nearly dead - the bar is a different width")
    g.monsters.remove(boss)
    check("boss gone - the bar has to be cleaned up")
    print("  Bossbalken und Boss-Banner bleiben deckungsgleich")

# --- in and out of a menu, where the whole screen is a different one -----
for state in ("paused", "playing", "bag", "playing", "settings", "playing"):
    g.state = state
    check(f"Zustand {state}")
print("  Wechsel in Menüs und zurück bleibt deckungsgleich")

# --- and it must actually be skipping work -------------------------------
# Without this the whole thing could be redrawing everything every frame
# and every check above would still pass.
painted = {"n": 0}
real = g._render_touch_controls


def counting():
    painted["n"] += 1
    return real()


g.state = "playing"
g._render_touch_controls = counting
# Which part of the furniture keeps changing, so a failure here names the
# culprit instead of leaving the next person to bisect a tuple.
from collections import Counter
culprits = Counter()
# In the order _furniture_signature builds them, so a failure names
# the field instead of an index.
FIELDS = ["state", "touch_dir", "show_touch", "test_room", "scrolls",
          "shake", "boss_banner", "boss_present", "banner_texts",
          "pressed_key"]
assert len(FIELDS) == len(g._furniture_signature()), (
    "the labels have drifted from the signature - a failure below "
    "would blame the wrong field")


def note_changes():
    before = getattr(g, "_furniture_sig", None)
    after = g._furniture_signature()
    if before is None or before == after:
        return
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b:
            culprits[FIELDS[i] if i < len(FIELDS) else f"#{i}"] += 1


# Nothing left standing next to the player: this half is about walking,
# and a monster in reach turns every step into an attack, which changes
# the band and is a full frame by design.
g.monsters = []
g._recompute_fov()
g.render()

copied = []
canvas_px = g.screen.get_width() * g.screen.get_height()
frames = turns = 0
for _ in range(8):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if not g.blocks_movement(g.player.x + dx, g.player.y + dy):
            g._player_turn(dx, dy)
            turns += 1
            break
    # The frames in between are the animation running out: the player
    # sliding into the next tile, sparks falling. Nothing outside the
    # dungeon view moves in them, and they are the majority.
    for _ in range(3):
        g._update_animations()
        note_changes()
        g.render()
        copied.append(sum(r.w * r.h for r in g._dirty)
                      if g._dirty is not None else canvas_px)
        frames += 1
g._render_touch_controls = real
print(f"  {frames} Bilder über {turns} Züge -> die Tasten wurden "
      f"{painted['n']}x neu gemalt")
assert painted["n"] <= turns + 1, (
    f"the buttons were repainted {painted['n']} times over {turns} turns - "
    f"the frames between turns are supposed to be cheap. What kept "
    f"changing: {dict(culprits)}")

# --- and a fight has to be mostly cheap too ------------------------------
# This is the case the player reported as still stuttering: the flash,
# the damage numbers and the sparks all draw over the dungeon view, so
# they cost the view and nothing more. Only the turn itself, which moves
# the health bar and writes to the log, is a full frame.
fight_painted = {"n": 0}


def counting_fight():
    fight_painted["n"] += 1
    return real()


# Alive and in play: a dead hero puts the death screen over the whole
# canvas, which is a full frame every time and by design, and would
# quietly turn this measurement into a measurement of that.
g.state = "playing"
g.player.max_hp = g.player.hp = 999999
foe = put_monster_next_to_player()
g._render_touch_controls = counting_fight
fight_copied = []
fight_turns = fight_frames = 0
for _ in range(6):
    if not any(m.is_alive() for m in g.monsters):
        put_monster_next_to_player()
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if any(m.x == g.player.x + dx and m.y == g.player.y + dy
               for m in g.monsters if m.is_alive()):
            g._player_turn(dx, dy)
            fight_turns += 1
            break
    for _ in range(4):
        g._update_animations()
        note_changes()
        g.render()
        fight_copied.append(sum(r.w * r.h for r in g._dirty)
                            if g._dirty is not None else canvas_px)
        fight_frames += 1
g._render_touch_controls = real
cheap_frames = [c for c in fight_copied if c < canvas_px]
share = (statistics.median(cheap_frames) / canvas_px
         if cheap_frames else 1.0)
print(f"  Kampf: {fight_frames} Bilder über {fight_turns} Züge, "
      f"{fight_painted['n']} volle, sparsame kopieren "
      f"{share * 100:.0f}% (Median)")
# A blow lands on a turn and moves the health bar and the log, and
# that is a full frame by design. What must not happen is the frames
# in between - the flash fading, the numbers rising, the sparks -
# costing the whole screen as well.
assert len(cheap_frames) >= fight_frames // 2, (
    f"only {len(cheap_frames)} of {fight_frames} fight frames were "
    f"cheap; the ones between the blows are supposed to cost the "
    f"dungeon view and nothing else. What kept changing: "
    f"{dict(culprits)}")
assert share < 0.6, (
    f"even a cheap fight frame copies {share * 100:.0f}% of the canvas")

# --- the frame-rate overlay has to reach the screen too ------------------
# It sits in the gutter, which is no longer cleared or copied every frame,
# so if it did not ask for its own patch it would be drawn on the canvas
# and never appear - and it is the one thing being watched while judging
# whether any of this worked.
g.settings["show_fps"] = True
seen = set()
# Refreshed on a wall clock, twice a second - and the frames are now
# cheap enough that a fixed count of them can pass in less time than
# that, which used to make this check pass without proving anything.
import time
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline and len(seen) < 2:
    g.needs_redraw = True
    g.render()
    rect = getattr(g, "_fps_rect", None)
    if rect is not None:
        on_canvas = as_bytes(g.screen.subsurface(rect))
        on_screen = as_bytes(g.display.subsurface(rect))
        assert on_canvas == on_screen, (
            "the frame-rate overlay is on the canvas but not on the screen")
        seen.add(on_canvas)
assert len(seen) > 1, (
    "the overlay never changed, so this proved nothing - it is refreshed "
    "twice a second and 200 frames should have crossed that")
# How much of the canvas a walking frame copies. This is the number the
# whole thing is for: the copy lands in memory the phone writes to
# slowly, so it costs in proportion to this area. Asserted as work
# rather than as milliseconds, which would only measure this desktop.
# The median, not the worst: a turn that changes the band is a full
# frame by design, and one of those in the run would otherwise hide
# what all the others cost.
typical = statistics.median(copied) / canvas_px
print(f"  kopierte Fläche beim Laufen: {typical * 100:.0f}% des Bildes "
      f"(Median über {len(copied)} Bilder)")
assert typical < 0.6, (
    f"a walking frame copies {typical * 100:.0f}% of the canvas - the "
    f"point of this was to copy the dungeon view, not the whole screen")

print(f"  Bildraten-Anzeige: {len(seen)} verschiedene Stände, jeder auf dem Schirm")

print("\nALL PARTIAL-PRESENT CHECKS PASSED")
