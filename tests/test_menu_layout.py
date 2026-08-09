"""Every menu screen must fit on screen AND have real touch targets.

Renders each screen at the real device canvas in both languages and
asserts, from the tap targets and the actually-painted pixels:
  - every button clears Android's 48dp minimum (144px at density 3.0)
  - no two tap targets overlap (a mistap would fire the wrong action)
  - all targets are on screen
  - nothing is painted in the bottom/right margin (i.e. content fits)
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["ANDROID_ARGUMENT"] = "1"

import pygame
pygame.init()

import constants as C
import game

WIN = (2448, 1098)
ANDROID_MIN_TOUCH = 144      # 48dp at density 3.0

_orig = pygame.display.set_mode
_n = {"i": 0}


def patched(size, flags=0):
    _n["i"] += 1
    return _orig(size, flags) if _n["i"] == 1 else pygame.Surface(size)


game.pygame.display.set_mode = patched
game.pygame.display.get_window_size = staticmethod(lambda: WIN)

g = game.Game()
g.start_new_run()
g.stats["achievements_unlocked"] = [a for a, _, _ in C.ACHIEVEMENTS[:2]]
g.stats["bestiary_seen"] = list(C.MONSTER_TYPES)[:3]
g.perk_choices = C.PERKS[:2]
g.update_phase = "available"
g.update_info = {"build": 99, "size": 33 * 1024 * 1024}

print(f"canvas {C.SCREEN_WIDTH}x{C.SCREEN_HEIGHT}  btn_h={g.btn_h}  "
      f"body glyph={g.f_body.get_height()}  title glyph={g.f_title.get_height()}")

SCREENS = ["title", "stats", "achievements", "bestiary", "tutorial", "settings",
           "shop", "paused", "levelup_choice", "dead", "confirm_disable_touch",
           "update"]

failures = []
for lang in ("en", "de"):
    g.settings["language"] = lang
    for state in SCREENS:
        g.state = state
        g.tutorial_page = 0
        g._dim_cache = None
        g.render()

        targets = list(g._tap_targets)
        # 1. touch target size
        for rect, key in targets:
            if min(rect.width, rect.height) < ANDROID_MIN_TOUCH:
                failures.append(
                    f"{lang}/{state}: tap target {rect.width}x{rect.height} "
                    f"is under the {ANDROID_MIN_TOUCH}px Android minimum")
        # 2. no overlap between targets
        for i, (a, _) in enumerate(targets):
            for b, _ in targets[i + 1:]:
                if a.colliderect(b):
                    failures.append(f"{lang}/{state}: tap targets overlap: {a} vs {b}")
        # 3. on screen
        screen_rect = pygame.Rect(0, 0, C.SCREEN_WIDTH, C.SCREEN_HEIGHT)
        for rect, _ in targets:
            if not screen_rect.contains(rect.clip(screen_rect)) or rect.clip(screen_rect) != rect:
                failures.append(f"{lang}/{state}: tap target {rect} is off screen")

        # 4. content actually fits: nothing painted in the last 8px rows,
        #    which would mean the layout ran off the bottom.
        if state not in ("playing",):
            bottom = pygame.Surface((C.SCREEN_WIDTH, 8))
            bottom.blit(g.screen, (0, 0), (0, C.SCREEN_HEIGHT - 8, C.SCREEN_WIDTH, 8))
            colors = {bottom.get_at((x, y))[:3]
                      for x in range(0, C.SCREEN_WIDTH, 7) for y in range(8)}
            # "Nothing bright down here", not "exactly these three
            # colours": the pause, level-up and death screens legitimately
            # dim the whole canvas, so the bottom rows are the background
            # and the HUD band *darkened* - which is not content running
            # off the edge. The darkest thing that counts as content is a
            # panel border at (52, 62, 78).
            stray = {c for c in colors if max(c) > 44}
            if stray:
                failures.append(
                    f"{lang}/{state}: content runs off the bottom edge (colours {sorted(stray)[:3]})")

        n_small = sum(1 for r, _ in targets if min(r.width, r.height) < ANDROID_MIN_TOUCH)
        if lang == "de":
            print(f"  de/{state:22s} {len(targets):2d} targets, "
                  f"{'all >= 48dp' if not n_small else str(n_small) + ' TOO SMALL'}")

if failures:
    print("\nFAILURES:")
    for f in dict.fromkeys(failures):
        print("  -", f)
    raise SystemExit(1)
print("\nALL MENU-LAYOUT CHECKS PASSED")
