"""Music must start on its own - never only after toggling it off and on."""
import os
import sys
import time

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
# Silent: a full sweep must not play the game's music at whoever runs it.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import constants as C
import game

fails = []
g = game.Game()

# --- 1. it starts at launch, before any run begins ---
time.sleep(0.4)
if not pygame.mixer.music.get_busy():
    fails.append("no music playing after startup (before a run is started)")
else:
    print(f"  playing at launch: {g._music_track}")

# --- 2. a FAILED load must not block later attempts.
#        This is the actual shipped bug: the failure path recorded the
#        track as current, so the 'already playing this' guard matched
#        forever and only the settings toggle (which clears it) recovered.
real_load = pygame.mixer.music.load
pygame.mixer.music.stop()
g._music_track = None
pygame.mixer.music.load = lambda *a, **k: (_ for _ in ()).throw(pygame.error("boom"))
g._play_tier_music(C.DUNGEON_TIERS[1])
if g._music_track is not None:
    fails.append(f"a failed load recorded the track ({g._music_track!r}), "
                 "which permanently blocks retries")
else:
    print("  a failed load leaves the retry path open")

pygame.mixer.music.load = real_load
g._play_tier_music(C.DUNGEON_TIERS[1])
time.sleep(0.4)
if not pygame.mixer.music.get_busy():
    fails.append("the retry after a failed load did not start music")
else:
    print(f"  retry after a failure works: {g._music_track}")

# --- 3. the watchdog recovers a track that never started, and ONLY that ---
# It used to restart whenever the mixer reported itself not busy. On a
# real device that reported false negatives, so it reloaded and replayed
# roughly once a second - heard as the music restarting from the top over
# and over. The contract now is narrow on purpose: a track we managed to
# start is left alone, and only a track that never started is retried.
pygame.mixer.music.stop()
g._music_retry_ms = -game.MUSIC_RETRY_COOLDOWN_MS
g._music_track = None                      # nothing ever started
g._music_watchdog()
time.sleep(0.4)
if not pygame.mixer.music.get_busy():
    fails.append("the watchdog did not recover a track that never started")
else:
    print(f"  watchdog recovers a track that never started: {g._music_track}")

playing = g._music_track
loads = {"n": 0}
real_load2 = pygame.mixer.music.load


def counting_load(path):
    loads["n"] += 1
    return real_load2(path)


pygame.mixer.music.load = counting_load
try:
    for _ in range(5):
        g._music_retry_ms = -game.MUSIC_RETRY_COOLDOWN_MS
        g._music_watchdog()
finally:
    pygame.mixer.music.load = real_load2
if loads["n"]:
    fails.append(f"the watchdog reloaded a track that was already playing "
                 f"({loads['n']} times) - this is the every-second restart bug")
elif g._music_track != playing:
    fails.append("the watchdog switched tracks behind our back")
else:
    print("  watchdog leaves a playing track alone")

# --- 4. turning music off really stops it and does not get restarted ---
g.settings["music"] = True
g._toggle_music()
time.sleep(0.2)
if pygame.mixer.music.get_busy():
    fails.append("music kept playing after being switched off")
g._music_check_ms = 0
g._music_watchdog()
time.sleep(0.2)
if pygame.mixer.music.get_busy():
    fails.append("the watchdog restarted music the player had switched off")
else:
    print("  switched off stays off, watchdog respects it")

# --- 5. switching it back on resumes ---
g._toggle_music()
time.sleep(0.4)
if not pygame.mixer.music.get_busy():
    fails.append("switching music back on did not resume it")
else:
    print("  switching back on resumes")

# --- 6. changing tier switches the track ---
first = g._music_track
other = next(t for t in C.DUNGEON_TIERS if t["music"] != first)
g._play_tier_music(other)
time.sleep(0.3)
if g._music_track != other["music"]:
    fails.append(f"tier change did not switch the track ({g._music_track})")
else:
    print(f"  tier change switches track: {first} -> {g._music_track}")

# --- 7. volume follows the setting, with no hidden attenuation ---
g.settings["volume"] = 0.8
g._cycle_volume()          # moves to the next level and applies it
applied = pygame.mixer.music.get_volume()
expected = g.settings["volume"]
if abs(applied - expected) > 0.02:
    fails.append(f"music volume {applied:.2f} does not match the setting {expected:.2f}")
else:
    print(f"  music volume tracks the setting ({applied:.2f})")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL MUSIC CHECKS PASSED")
