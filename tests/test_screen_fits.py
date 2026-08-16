"""Every button on every screen has to be on the screen.

The layouts are computed from the canvas, and the canvas is whatever the
device gives us - so a screen that fits on a monitor can put its buttons
past the bottom edge on a phone. That is how the hero-select screen
shipped with its back button, the only touch way off it, half cut off at
both graphics settings.

Checked at the phone's real window size, since that is the shape that
goes wrong, and at both settings, since they produce different canvases.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["ANDROID_ARGUMENT"] = "1"

import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdl_stub  # noqa: F401

pygame.init()
# The window a real device reported, from its own logs - not the device
# resolution, which is bigger by the status bar and the nav row.
pygame.display.get_window_size = lambda: (2448, 1098)

import constants as C
import persistence
import game

# Every screen that draws tap targets. Gameplay states are covered by
# their own suites; these are the ones laid out as a page of buttons.
SCREENS = [
    "title", "difficulty_select", "class_select", "settings", "bag",
    "stats", "achievements", "tutorial", "bestiary", "paused",
    "confirm_disable_touch", "update", "shop", "smith", "tools", "dead",
]

problems = []
for scale in ("auto", 1.0):
    settings = persistence.load_settings()
    settings["render_scale"] = scale
    persistence.save_settings(settings)
    g = game.Game()
    g.start_new_run()
    w, h = g.screen.get_size()
    checked = 0
    for state in SCREENS:
        g.state = state
        g.needs_redraw = True
        g.render()
        for rect, key in g._tap_targets:
            # The registered target is deliberately larger than the drawn
            # button, so a thumb landing just outside still counts (see
            # _draw_tap_button). It is the drawn box that has to fit.
            drawn = rect.inflate(-g.tap_slop, -g.tap_slop)
            checked += 1
            if (drawn.bottom > h or drawn.right > w
                    or drawn.top < 0 or drawn.left < 0):
                problems.append(
                    f"{state} at {scale}: key {key} drawn at {tuple(drawn)} "
                    f"reaches past the {w}x{h} canvas")
    print(f"  Grafik {scale}: {w}x{h}, {len(SCREENS)} Screens, "
          f"{checked} Knöpfe geprüft")
    del g

if problems:
    raise AssertionError("buttons drawn off the screen:\n  "
                         + "\n  ".join(problems))
print("  every button on every screen is inside the canvas")

print("\nALL SCREEN-FIT CHECKS PASSED")
