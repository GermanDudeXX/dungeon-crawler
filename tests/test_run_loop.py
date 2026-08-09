"""Actually execute Game.run()'s loop body on a FRESH Game.

This is the gap that let an AttributeError ship: every other test either
calls render() directly or pre-seeds the loop's bookkeeping attributes,
so nothing ever exercised run() itself from a cold start - where an
attribute initialised only inside the loop does not exist yet.

Runs the real run() in a background thread against a fresh Game and fails
if it raises, in every reachable state.
"""
import os
import sys
import threading
import time

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import constants as C
import game

g = game.Game()

error = {}
stop = threading.Event()

# run() loops forever; break out of it by raising a sentinel from tick().
class Stop(Exception):
    pass


# pygame 2.6's Clock.tick is read-only, so the clock is replaced whole
# rather than monkeypatched - this is how the loop gets interrupted from
# the outside without touching Game.run itself.
class _StopClock:
    def __init__(self, real):
        self._real = real

    def tick(self, fps):
        if stop.is_set():
            raise Stop()
        return self._real.tick(fps)

    def __getattr__(self, name):
        return getattr(self._real, name)


g.clock = _StopClock(g.clock)


def worker():
    try:
        g.run()
    except Stop:
        pass
    except SystemExit:
        pass
    except BaseException as exc:      # noqa: BLE001 - we want to see anything
        import traceback
        error["exc"] = exc
        error["tb"] = traceback.format_exc()


t = threading.Thread(target=worker, daemon=True)
t.start()

# Let the cold-start path run first - this is what crashed on device.
time.sleep(0.4)
if error:
    print(error["tb"])
    raise SystemExit("run() raised on a cold start (title screen)")
print("  run() survives a cold start on the title screen")

# Then drive it through every state it can actually reach.
g.start_new_run()
for state in ("playing", "paused", "shop", "stats", "achievements", "tutorial",
              "settings", "bestiary", "dead", "confirm_disable_touch", "update"):
    g.state = state
    time.sleep(0.12)
    if error:
        print(error["tb"])
        raise SystemExit(f"run() raised while in state {state!r}")
    print(f"  run() survives state {state!r}")

g.perk_choices = C.PERKS[:2]
g.state = "levelup_choice"
time.sleep(0.12)
if error:
    print(error["tb"])
    raise SystemExit("run() raised in state 'levelup_choice'")
print("  run() survives state 'levelup_choice'")

# And with movement held down, which is the auto-repeat path.
g.state = "playing"
g.touch_direction = (1, 0)
time.sleep(0.8)
g.touch_direction = None
if error:
    print(error["tb"])
    raise SystemExit("run() raised while auto-repeating movement")
print("  run() survives held-down movement (auto-repeat)")

stop.set()
t.join(timeout=2)
print("\nALL RUN-LOOP CHECKS PASSED")
