"""A level-up must ALWAYS end in the player choosing a perk.

Probes every route by which a level can be gained, and checks the choice
is either shown immediately or still pending afterwards - never silently
dropped.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import constants as C
import dungeon as dmod
import entities
import game

g = game.Game()
fails = []


def fresh():
    g.start_new_run()
    g.state = "playing"
    return g


def about_to_level(p):
    """Put the player one small XP grant away from levelling."""
    p.xp = p.xp_to_next - 1


# --- 1. ordinary kill in melee ---
fresh()
about_to_level(g.player)
m = entities.Monster(g.player.x + 1, g.player.y, "rat")
m.hp = 1
g.monsters = [m]
g._player_turn(1, 0)
if g.state != "levelup_choice":
    fails.append(f"melee kill: expected the perk screen, got state={g.state!r} "
                 f"(pending={g.pending_perk_count})")
else:
    print("  melee kill -> perk screen shown")

# --- 2. kill via a damage-over-time tick during the enemy turn ---
fresh()
about_to_level(g.player)
m = entities.Monster(g.player.x + 3, g.player.y, "rat")
m.hp = 1
m.burn_turns = 2
m.awake = True
g.monsters = [m]
g._player_turn(0, 0) if False else None
g._enemy_turn()
g._maybe_show_levelup_choice()
if g.state != "levelup_choice":
    fails.append(f"burn-DoT kill: expected the perk screen, got state={g.state!r} "
                 f"(pending={g.pending_perk_count})")
else:
    print("  damage-over-time kill -> perk screen shown")

# --- 3. kill with a fireball scroll ---
fresh()
about_to_level(g.player)
m = entities.Monster(g.player.x + 2, g.player.y, "rat")
m.hp = 1
g.monsters = [m]
g.visible.add((m.x, m.y))
g.player.scrolls["fireball"] = 1
g._use_scroll("fireball")
if g.state != "levelup_choice":
    fails.append(f"fireball kill: expected the perk screen, got state={g.state!r} "
                 f"(pending={g.pending_perk_count})")
else:
    print("  fireball kill -> perk screen shown")

# --- 4. levelling up and then saving & reloading ---
fresh()
g.player.gain_xp(g.player.xp_to_next)      # grant a level directly
g.pending_perk_count = 1
save = g._build_save_data()
g.save_data = save
g.continue_run()
if g.pending_perk_count != 1:
    fails.append(f"save/reload: a pending perk choice was lost "
                 f"(pending={g.pending_perk_count}, expected 1)")
else:
    print("  save & reload -> perk choice survives")

# --- 5. levelling up on the same turn as taking the stairs ---
fresh()
about_to_level(g.player)
g.player.x, g.player.y = g.stairs_pos
g.pending_perk_count = 0
g.player.gain_xp(1)
g.pending_perk_count += 1
g._advance_level()
if g.state != "levelup_choice":
    fails.append(f"level-up while descending: expected the perk screen, "
                 f"got state={g.state!r} (pending={g.pending_perk_count})")
else:
    print("  level-up while descending -> perk screen shown")

# --- 6. the screen must not be dismissable without choosing ---
fresh()
g.pending_perk_count = 1
g._maybe_show_levelup_choice()
assert g.state == "levelup_choice"
for key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN, pygame.K_q, pygame.K_o):
    g._handle_key(key)
    if g.state != "levelup_choice":
        fails.append(f"perk screen was dismissed by key {pygame.key.name(key)!r} "
                     f"without choosing (state={g.state!r})")
        break
else:
    print("  perk screen cannot be dismissed with escape/enter/etc")

g.render()
outside = (5, 5)
if not any(r.collidepoint(outside) for r, _ in g._tap_targets):
    g._handle_tap(outside)
    if g.state != "levelup_choice":
        fails.append("perk screen was dismissed by tapping outside the cards")
    else:
        print("  perk screen cannot be dismissed by tapping outside")

# --- 7. two levels at once must ask twice ---
fresh()
g.pending_perk_count = 2
g._maybe_show_levelup_choice()
g._apply_perk(g.perk_choices[0])
if g.state != "levelup_choice" or g.pending_perk_count != 1:
    fails.append(f"two levels at once: after the first choice expected another, "
                 f"got state={g.state!r} pending={g.pending_perk_count}")
else:
    g._apply_perk(g.perk_choices[0])
    if g.state != "playing" or g.pending_perk_count != 0:
        fails.append(f"two levels at once: after the second choice expected play to "
                     f"resume, got state={g.state!r} pending={g.pending_perk_count}")
    else:
        print("  two levels at once -> asks twice, then resumes")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL LEVEL-UP CHECKS PASSED")
