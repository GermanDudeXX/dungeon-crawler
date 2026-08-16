"""The graphics setting: how it reads, and what it says when it is too slow.

Picking the full canvas by hand on a phone doubles the pixels per frame,
and nothing in the renderer can undo that - so the two things that have
to work are the name of the setting and the one message that points at
it. Also covers the touch-button cache, which is the last per-frame font
render in a drawn frame.
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

import constants as C
import persistence
import game

g = game.Game()
g.start_new_run()
g.state = "playing"

# --- 1. every scale names what it costs -----------------------------------
for lang in ("de", "en"):
    g.settings["language"] = lang
    names = {}
    for scale in C.RENDER_SCALES:
        g.settings["render_scale"] = scale
        names[scale] = g._render_scale_name()
    print(f"  {lang}: " + " | ".join(f"{k}={v!r}" for k, v in names.items()))
    assert len(set(names.values())) == len(names), (
        f"two graphics settings read the same in {lang}: {names}")
    # The full canvas must not read as the neutral option: it is the one
    # that costs, and its number alone ("1x", one row under "Zoom: 1.5x")
    # is what made it look like the default.
    assert names[1.0].strip() != "1x", "the full canvas still reads as just 1x"
    assert len(names[1.0]) > len("1x"), "the full canvas carries no hint"
    assert names["auto"] != g._mult_text(g.render_scale), "auto is unlabelled"

g.settings["language"] = "de"

# --- 2. the slow-frame message ---------------------------------------------
def frames(g, ms, n):
    for _ in range(n):
        g._note_frame_cost(ms)


slow = C.SLOW_FRAME_MS + 10
fast = C.SLOW_FRAME_MS - 10

# "auto" already sizes the canvas to a budget - there is nothing the
# player could change, so it must stay quiet however slow it gets.
g.settings["render_scale"] = "auto"
g._slow_frames, g._slow_warned = 0, False
frames(g, slow, C.SLOW_FRAME_STREAK * 3)
assert not g._slow_warned, "auto warned about a setting it picked itself"
print(f"  auto stayed quiet through {C.SLOW_FRAME_STREAK * 3} slow frames")

# A hand-picked scale does warn - but only after a run of them, so that
# a level load or the OS stealing the CPU does not trip it.
g.settings["render_scale"] = 1.0
g._slow_frames, g._slow_warned = 0, False
frames(g, slow, C.SLOW_FRAME_STREAK - 1)
assert not g._slow_warned, "warned before the streak was reached"
frames(g, fast, 1)
frames(g, slow, C.SLOW_FRAME_STREAK - 1)
assert not g._slow_warned, "one fast frame did not reset the streak"
before = len(g.banners)
frames(g, slow, 1)
assert g._slow_warned, "a sustained run of slow frames said nothing"
assert len(g.banners) > before, "the warning never reached the screen"
print(f"  1x warned after {C.SLOW_FRAME_STREAK} slow frames, not before")

# Once. It is advice, not an alarm.
count = len(g.banners)
frames(g, slow, C.SLOW_FRAME_STREAK * 2)
assert len(g.banners) == count, "the warning repeated"
print("  and said it once")

# Not while reading a menu, where the frame is a different picture
# entirely and the message would land on top of the setting being read.
g.state = "settings"
g._slow_frames, g._slow_warned = 0, False
frames(g, slow, C.SLOW_FRAME_STREAK * 2)
assert not g._slow_warned, "warned outside of play"
g.state = "playing"
print("  and only during play")

# --- 3. the touch buttons are drawn once, not every frame ------------------
renders = {"n": 0}
real_font = g.f_sm


class CountingFont:
    """pygame.font.Font.render is read-only, so count from around it."""

    def __init__(self, font):
        self._font = font

    def render(self, *a, **kw):
        renders["n"] += 1
        return self._font.render(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._font, name)


g.f_sm = CountingFont(real_font)
g._touch_btn_cache = {}
g._render_touch_controls()
first = renders["n"]
renders["n"] = 0
for _ in range(10):
    g._render_touch_controls()
print(f"  touch controls: {first} font renders on the first frame, "
      f"{renders['n']} over the next ten")
assert first > 0, "the touch controls drew no text at all"
assert renders["n"] == 0, (
    f"touch buttons still re-render their labels every frame ({renders['n']})")
g.f_sm = real_font

# A held direction is a different button, and it has to be drawn as one.
g.touch_direction = (1, 0)
g._render_touch_controls()
assert any(key[2] for key in g._touch_btn_cache), (
    "the pressed state never reached the cache - a held direction would "
    "show as unpressed")
g.touch_direction = None
print(f"  {len(g._touch_btn_cache)} buttons cached, pressed state included")

# The cached buttons were drawn at one size with one font. Both change
# with the zoom, so the cache cannot survive it.
g._apply_zoom(C.BASE_TILE_SIZE)
assert not g._touch_btn_cache, "the zoom left buttons cached at the old size"
print("  zoom clears the cache")

# --- 4. a fresh install speaks the device's language -----------------------
# The reinstall an APK signing change forces takes settings.json with it,
# so this is the screen the player comes back to.
import importlib

saved_env = {k: os.environ.get(k)
             for k in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")}
try:
    for tag, want in (("de_DE.UTF-8", "de"), ("de", "de"),
                      ("en_GB.UTF-8", "en"), ("fr_FR.UTF-8", "en")):
        for k in saved_env:
            os.environ.pop(k, None)
        os.environ["LANGUAGE"] = tag
        got = persistence.device_language()
        assert got == want, f"{tag!r} -> {got!r}, expected {want!r}"
    print("  device language: de_DE/de -> de, en_GB/fr_FR -> en")

    # An unreadable settings file must land on the same footing as no
    # settings file at all, not on a flat English default.
    os.environ["LANGUAGE"] = "de_DE.UTF-8"
    real_exists = os.path.exists
    persistence_path = persistence.SETTINGS_PATH
    try:
        os.path.exists = lambda p: False if p == persistence_path else real_exists(p)
        assert persistence.load_settings()["language"] == "de", (
            "a fresh install ignored the device language")
    finally:
        os.path.exists = real_exists
    print("  a fresh install starts in the device's language")
finally:
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print("\nALL RENDER-SCALE CHECKS PASSED")
