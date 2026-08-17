"""Plays the game for a few thousand turns and complains about what it sees.

Not a unit test of anything in particular: it drives the real Game the
way a player does - walk towards the stairs, hit what is in the way,
kill the boss when the way down is locked, drink when hurt, take the
level-up, go down - and watches for what a player would call a bug: a
crash, an impossible state, or a floor that cannot be finished.

This is how the shopkeeper blocking the stairs was found. Reading the
placement code would not have shown it; walking into it did.
"""
import os
import random
import sys
import traceback
from collections import Counter, deque

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

TURNS = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
STUCK_LIMIT = 600          ## turns on one floor before calling it stuck

problems = Counter()
notes = []


def complain(what, detail=""):
    problems[what] += 1
    if problems[what] <= 2 and detail:
        notes.append(f"{what}: {detail}")


def route(g, target):
    """A step towards target, or None if there is no way there at all.

    Monsters count as passable, since walking into one is how you attack
    it. Shopkeepers do not: walking into them opens their shop instead
    of moving, so there is no getting past one - which is the whole
    reason they are not allowed to stand in a chokepoint.
    """
    start = (g.player.x, g.player.y)
    if start == target:
        return (0, 0)
    shops = {(n.x, n.y) for n in list(g.merchants) + list(g.blacksmiths)}
    came = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            step = (cell[0] + dx, cell[1] + dy)
            if step in came or step in shops:
                continue
            occupied = any((m.x, m.y) == step for m in g.monsters if m.is_alive())
            if not occupied and g.blocks_movement(*step):
                continue
            came[step] = cell
            if step == target:
                queue.clear()
                break
            queue.append(step)
    if target not in came:
        return None
    cell = target
    while came[cell] != start:
        cell = came[cell]
        if cell is None:
            return None
    return (cell[0] - start[0], cell[1] - start[1])


def check(g, where):
    p = g.player
    if p.hp > p.max_hp:
        complain("Leben über dem Maximum", f"{p.hp}/{p.max_hp} bei {where}")
    if p.gold < 0:
        complain("negatives Gold", f"{p.gold} bei {where}")
    if g.state == "playing" and g.blocks_movement(p.x, p.y):
        complain("Spieler steckt in einer Wand", f"{(p.x, p.y)} bei {where}")
    for m in g.monsters:
        if not m.is_alive():
            continue
        if (m.x, m.y) == (p.x, p.y):
            complain("Monster steht auf dem Spieler", f"{m.kind} bei {where}")
        if m.hp > m.max_hp:
            complain("Monster-Leben über dem Maximum",
                     f"{m.kind} {m.hp}/{m.max_hp} bei {where}")
    if p.level < 1 or p.max_hp < 1:
        complain("unmögliche Spielerwerte", f"Lv{p.level} maxHP {p.max_hp} bei {where}")


settings = persistence.load_settings()
settings["language"] = "de"
persistence.save_settings(settings)

# Seeded, so a failure can be looked at again instead of being a story
# about a run nobody can reproduce. These particular seeds are the
# ones that used to spring a mimic on top of the player.
random.seed(int(os.environ.get("PLAYTHROUGH_SEED", "6")))

g = game.Game()
g.start_new_run()
g.state = "playing"

deepest = 1
descents = deaths = potions = boss_kills = 0
level_at = g.dungeon_level
on_this_floor = 0

for turn in range(TURNS):
    try:
        if g.state == "levelup_choice":
            g._handle_key(pygame.K_1)
            continue
        if g.state in ("shop", "smith"):
            g._handle_key(pygame.K_ESCAPE)
            if g.state in ("shop", "smith"):
                complain("Laden lässt sich nicht verlassen", g.state)
                g.state = "playing"
            continue
        if g.state == "dead":
            deaths += 1
            g.start_new_run()
            g.state = "playing"
            level_at = g.dungeon_level
            on_this_floor = 0
            continue
        if g.state != "playing":
            complain("unerwarteter Zustand", g.state)
            g.state = "playing"
            continue

        if g.player.hp < g.player.max_hp * 0.4 and g.player.potions > 0:
            before = g.player.hp
            g._handle_key(pygame.K_g)
            if g.player.hp > before:
                potions += 1

        # The way down can be locked behind a boss, and the game says so.
        # A player goes and kills it; a bot that only knows about stairs
        # walks into the door for the rest of the run.
        boss = next((m for m in g.monsters if m.is_alive() and m.is_boss), None)
        target = (boss.x, boss.y) if boss else g.stairs_pos
        bosses_before = sum(1 for m in g.monsters if m.is_boss and m.is_alive())

        step = route(g, target)
        if step is None:
            if boss is None:
                complain("Treppe unerreichbar",
                         f"Ebene {g.dungeon_level}, Treppe {g.stairs_pos}, "
                         f"Spieler {(g.player.x, g.player.y)}")
            g._advance_level()
            level_at = g.dungeon_level
            on_this_floor = 0
            continue

        g._player_turn(*step)
        check(g, f"Zug {turn}, Ebene {g.dungeon_level}")
        if bosses_before and not sum(1 for m in g.monsters if m.is_boss and m.is_alive()):
            boss_kills += 1

        if g.dungeon_level != level_at:
            descents += 1
            deepest = max(deepest, g.dungeon_level)
            level_at = g.dungeon_level
            on_this_floor = 0
        else:
            on_this_floor += 1
            if on_this_floor > STUCK_LIMIT:
                complain("Ebene nicht abschließbar",
                         f"Ebene {g.dungeon_level}, {on_this_floor} Züge, "
                         f"Treppe {g.stairs_pos}, Spieler "
                         f"{(g.player.x, g.player.y)}, "
                         f"Boss lebt: {boss is not None}")
                g._advance_level()
                level_at = g.dungeon_level
                on_this_floor = 0

        if turn % 40 == 0:
            g.needs_redraw = True
            g.render()
    except Exception:
        complain("ABSTURZ", traceback.format_exc().strip().splitlines()[-1])
        notes.append(traceback.format_exc())
        break

print(f"  {TURNS} Züge gespielt: Ebene {deepest} erreicht, {descents} Abstiege, "
      f"{deaths} Tode, {boss_kills} Bosse, {potions} Tränke")

for what, count in problems.most_common():
    print(f"  {count:5d}x  {what}")
for note in notes[:4]:
    print("    " + note.replace("\n", "\n    ")[:500])

assert descents >= 3, (
    f"only got down {descents} floors in {TURNS} turns - the game is not "
    f"playable to completion, which is worse than any single bug here")
assert not problems, "the playthrough found problems - see above"

print("\nALL PLAYTHROUGH CHECKS PASSED")
