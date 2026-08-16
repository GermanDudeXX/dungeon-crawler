"""A touch has to land on the button it is drawn under, at every scale.

Everything is laid out and hit-tested in canvas coordinates; the events
arrive in the display's. They are the same size only when the canvas
is not stretched - i.e. only at graphics 1x. At any other setting
_present blows the canvas up to fill the window, and an untranslated
touch lands short of the button by exactly that factor. That is what
made the game unplayable on anything but 1x, and nothing on a desktop
can notice it: there the window is created at the canvas size and the
two never differ.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401

pygame.init()

import game

g = game.Game()
g.start_new_run()
g.state = "playing"

cw, ch = g.screen.get_size()


def stretch_display(factor):
    """Stand in for a phone window bigger than the canvas drawn into it."""
    g.display = pygame.Surface((int(cw * factor), int(ch * factor)))


def where_it_is_drawn(rect, factor):
    """The physical point under the middle of a button on the stretched
    display - which is where the finger actually goes."""
    return (int(rect.centerx * factor), int(rect.centery * factor))


# The d-pad is the case that matters: it is held down, it is at the edge
# of the screen where the error is largest, and it is most of playing.
directions = dict(g.dpad_buttons)
assert directions, "no d-pad to test"

# --- 1. unstretched: the mapping must not touch anything -------------------
g.display = pygame.Surface((cw, ch))
for name, (rect, vector, label) in directions.items():
    assert g._canvas_pos(rect.center) == rect.center, (
        "the mapping moved a touch even though nothing is being stretched")
print("  1x: touches pass through untouched")

# --- 2. stretched: a touch on the drawn button hits that button ------------
for factor in (4 / 3, 2.0):
    stretch_display(factor)
    for name, (rect, vector, label) in directions.items():
        physical = where_it_is_drawn(rect, factor)
        mapped = g._canvas_pos(physical)
        assert rect.collidepoint(mapped), (
            f"at x{factor:.2f} a touch on {name} landed at {mapped}, "
            f"outside {tuple(rect)} - this is the unplayable bug")
    # ... and it reaches the game, not just the arithmetic.
    for name, (rect, vector, label) in directions.items():
        g.touch_direction = None
        g._handle_tap(g._canvas_pos(where_it_is_drawn(rect, factor)))
        assert g.touch_direction == vector, (
            f"at x{factor:.2f} tapping {name} did not start moving {vector}")
    print(f"  x{factor:.2f} stretch: all {len(directions)} d-pad buttons hit")

# --- 3. the untranslated position would have missed ------------------------
# Without this the fix could be a no-op and every check above would still
# pass, which is exactly how this got shipped.
stretch_display(4 / 3)
missed = 0
for name, (rect, vector, label) in directions.items():
    if not rect.collidepoint(where_it_is_drawn(rect, 4 / 3)):
        missed += 1
assert missed, ("the raw display position still lands inside the button - "
                "this test is not actually reproducing the bug")
print(f"  and {missed}/{len(directions)} raw positions miss, as they did on the phone")

# --- 4. the same for the menu button, which is the way out of everything ---
for factor in (4 / 3, 2.0):
    stretch_display(factor)
    mapped = g._canvas_pos(where_it_is_drawn(g.save_button, factor))
    assert g.save_button.collidepoint(mapped), (
        f"at x{factor:.2f} the menu button - the only touch way to the pause "
        f"menu - is unreachable")
print("  the menu button stays reachable at every scale")

print("\nALL TOUCH-MAPPING CHECKS PASSED")
