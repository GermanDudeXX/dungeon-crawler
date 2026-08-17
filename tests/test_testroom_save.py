"""The test room must not touch a run in progress.

It is a sandbox - one floor holding one of everything, for looking at a
change without playing twenty floors. It starts itself through
start_new_run, which deletes the saved run, so opening it wiped whatever
the player had going. That is exactly what it did to a real save on a
real phone, silently, with no warning and nothing to undo it.
"""
import json
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

import persistence
import game

# Keep whatever is really on this machine out of it.
had_save = os.path.exists(persistence.SAVE_PATH)
backup = None
if had_save:
    with open(persistence.SAVE_PATH, encoding="utf-8") as f:
        backup = f.read()

try:
    g = game.Game()

    # A run in progress, saved the way the game saves it.
    g.start_new_run()
    g.state = "playing"
    g.dungeon_level = 4
    g.player.gold = 321
    persistence.save_run(g._build_save_data())
    assert os.path.exists(persistence.SAVE_PATH), "the run did not save at all"
    with open(persistence.SAVE_PATH, encoding="utf-8") as f:
        saved = f.read()
    print(f"  Lauf gespeichert: Ebene {json.loads(saved).get('dungeon_level')}")

    # Now go and look at the test room.
    g.start_test_room()
    assert g.test_room, "the test room did not start"
    assert os.path.exists(persistence.SAVE_PATH), (
        "opening the test room deleted the saved run")
    with open(persistence.SAVE_PATH, encoding="utf-8") as f:
        assert f.read() == saved, "the test room overwrote the saved run"
    print("  Testraum betreten: Spielstand unangetastet")

    # And leaving it must not write the sandbox over the real run either.
    g.dungeon_level = 12
    g.player.gold = 999999
    try:
        g._save_and_quit()
    except SystemExit:
        pass
    with open(persistence.SAVE_PATH, encoding="utf-8") as f:
        assert f.read() == saved, (
            "quitting out of the test room saved the sandbox over the run")
    print("  Testraum verlassen: Spielstand immer noch der echte")

    # A real new run still clears it - that is the whole point of the
    # button next to it.
    g2 = game.Game()
    g2.start_new_run()
    assert not os.path.exists(persistence.SAVE_PATH), (
        "starting a new run no longer clears the old one")
    print("  Neuer Lauf löscht ihn weiterhin, wie er soll")
finally:
    if backup is not None:
        with open(persistence.SAVE_PATH, "w", encoding="utf-8") as f:
            f.write(backup)
    elif os.path.exists(persistence.SAVE_PATH):
        os.remove(persistence.SAVE_PATH)

print("\nALL TEST-ROOM SAVE CHECKS PASSED")
