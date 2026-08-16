"""Generates the Android launcher icon and the start-up image.

    python tools/make_launcher_art.py

Both are built from the game's own art rather than drawn by hand, so
they cannot drift away from what the game looks like. Run this again if
the palette or the hero sprite changes; the results are committed, since
the APK build reads them as files.

The start-up image matters more than it sounds: python-for-android
unpacks the whole Python bundle on the first launch after every update,
which takes about half a minute on a phone, and until it finishes there
is nothing on screen at all. Without a start-up image that is half a
minute of black that looks exactly like a crash.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(C.ASSETS_DIR, "tiles")
HERO = os.path.join(C.CLASS_SPRITE_DIR, "knight_m_idle_anim_f0.png")

SIZE = 512


def tiled_floor(size, tile_px):
    """The dungeon floor, as a background."""
    surf = pygame.Surface((size, size))
    surf.fill(C.COLOR_BG)
    floors = [os.path.join(TILES, "floor_%d.png" % i) for i in (1, 2, 3, 4)]
    floors = [f for f in floors if os.path.exists(f)]
    if not floors:
        return surf
    loaded = [pygame.transform.scale(pygame.image.load(f).convert_alpha(),
                                     (tile_px, tile_px)) for f in floors]
    for y in range(0, size, tile_px):
        for x in range(0, size, tile_px):
            # Deterministic, so the icon is the same file every run - a
            # launcher icon that changes on every build is noise in the
            # diff and a new download for no reason.
            surf.blit(loaded[((x // tile_px) * 7 + (y // tile_px) * 13) % len(loaded)],
                      (x, y))
    return surf


def hero(height):
    sprite = pygame.image.load(HERO).convert_alpha()
    w, h = sprite.get_size()
    # scale, never smoothscale - this is 16px pixel art.
    return pygame.transform.scale(sprite, (round(w * height / h), height))


def darken(surf, amount):
    veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, amount))
    surf.blit(veil, (0, 0))


def make_icon(path):
    icon = tiled_floor(SIZE, SIZE // 8)
    darken(icon, 120)
    # Launchers crop icons to a circle, a squircle or a rounded square
    # depending on the phone, so everything that matters stays well
    # inside the middle - the frame is decoration and may be eaten.
    inset = SIZE // 10
    pygame.draw.rect(icon, C.COLOR_ACCENT,
                     (inset, inset, SIZE - 2 * inset, SIZE - 2 * inset),
                     width=max(3, SIZE // 64), border_radius=SIZE // 8)
    figure = hero(int(SIZE * 0.62))
    icon.blit(figure, figure.get_rect(center=(SIZE // 2, SIZE // 2)))
    pygame.image.save(icon, path)
    return icon.get_size()


def make_presplash(path):
    splash = tiled_floor(SIZE, SIZE // 8)
    darken(splash, 165)
    figure = hero(int(SIZE * 0.42))
    splash.blit(figure, figure.get_rect(center=(SIZE // 2, int(SIZE * 0.42))))

    # The app's own name, which is the same in every language, so this
    # needs no translation and cannot be shown in the wrong one - the
    # language setting is not readable this early anyway.
    font = pygame.font.Font(None, SIZE // 9)
    font.set_bold(True)
    title = font.render("DUNGEON CRAWLER", True, C.COLOR_ACCENT)
    if title.get_width() > SIZE - 40:
        title = pygame.transform.smoothscale(
            title, (SIZE - 40,
                    round(title.get_height() * (SIZE - 40) / title.get_width())))
    splash.blit(title, title.get_rect(center=(SIZE // 2, int(SIZE * 0.72))))
    pygame.image.save(splash, path)
    return splash.get_size()


def main():
    pygame.init()
    pygame.display.set_mode((SIZE, SIZE))       # for convert_alpha()
    icon_path = os.path.join(C.ASSETS_DIR, "icon.png")
    splash_path = os.path.join(C.ASSETS_DIR, "presplash.png")
    print("icon      ", make_icon(icon_path), icon_path)
    print("presplash ", make_presplash(splash_path), splash_path)


if __name__ == "__main__":
    main()
