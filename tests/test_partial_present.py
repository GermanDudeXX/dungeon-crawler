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
FIELDS = ["state", "hud", "explored", "player.x", "player.y", "stairs",
          "touch_dir", "show_touch", "test_room", "scrolls", "flash",
          "boss_banner", "shake", "boss.hp", "boss.max", "banners",
          "banner_timers", "pressed_key"]


def note_changes():
    before = getattr(g, "_furniture_sig", None)
    after = g._furniture_signature()
    if before is None or before == after:
        return
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b:
            culprits[FIELDS[i] if i < len(FIELDS) else f"#{i}"] += 1


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
        frames += 1
g._render_touch_controls = real
print(f"  {frames} Bilder über {turns} Züge -> die Tasten wurden "
      f"{painted['n']}x neu gemalt")
assert painted["n"] <= turns + 1, (
    f"the buttons were repainted {painted['n']} times over {turns} turns - "
    f"the frames between turns are supposed to be cheap. What kept "
    f"changing: {dict(culprits)}")

# --- the frame-rate overlay has to reach the screen too ------------------
# It sits in the gutter, which is no longer cleared or copied every frame,
# so if it did not ask for its own patch it would be drawn on the canvas
# and never appear - and it is the one thing being watched while judging
# whether any of this worked.
g.settings["show_fps"] = True
seen = set()
for _ in range(200):
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
print(f"  Bildraten-Anzeige: {len(seen)} verschiedene Stände, jeder auf dem Schirm")

print("\nALL PARTIAL-PRESENT CHECKS PASSED")
