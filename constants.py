import os
import sys

TILE_SIZE = 24
MAP_WIDTH = 40
MAP_HEIGHT = 25

HUD_HEIGHT = 190
MAP_PIXEL_WIDTH = MAP_WIDTH * TILE_SIZE
# Extra space on each side of the map, reserved for touch controls so they
# sit next to the dungeon view instead of floating on top of it, and so
# there's room for buttons big enough to actually hit on a phone. On a
# typical widescreen phone in landscape this also puts the game closer to
# actually filling the display instead of being letterboxed down to a
# narrow strip in the middle.
GUTTER_WIDTH = 260
MAP_OFFSET_X = GUTTER_WIDTH
SCREEN_WIDTH = MAP_PIXEL_WIDTH + 2 * GUTTER_WIDTH

# Absolute floor a gutter can shrink to on Android when the real device's
# aspect ratio is fitted at startup (see Game._fit_screen_to_device) and
# still keep the D-pad fully inside it: the D-pad's own buttons span
# GUTTER_WIDTH/2 +/- 104px (two 64px buttons plus an 8px gap either side
# of center, see _setup_touch_controls), so GUTTER_WIDTH must stay >=
# ~208px; 220 keeps a small margin. Deliberately NOT the same as the
# default GUTTER_WIDTH=260 above - that default was sized generously for
# the common case, not the true minimum, so using it as the shrink floor
# would leave devices narrower than our default aspect ratio (e.g. 16:9)
# with an unnecessary residual letterbox instead of an exact edge-to-edge
# fit.
MIN_GUTTER_WIDTH = 220
SCREEN_HEIGHT = MAP_HEIGHT * TILE_SIZE + HUD_HEIGHT

# Bundled read-only assets: a PyInstaller onefile exe unpacks these into
# sys._MEIPASS at startup, not next to the .exe itself (unlike save data,
# see persistence.py - these are read-only and fine to live in the
# temporary extraction dir for the process's lifetime).
_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(_BASE_DIR, "assets")
PLAYER_SPRITE_PATH = os.path.join(ASSETS_DIR, "player.png")
PLAYER_SPRITE_HEIGHT = int(TILE_SIZE * 1.8)

MONSTER_SPRITE_DIR = os.path.join(ASSETS_DIR, "monsters")
MONSTER_SPRITE_HEIGHT = int(TILE_SIZE * 1.5)
BOSS_SPRITE_SCALE = 1.8
SPLIT_CHILD_SPRITE_SCALE = 0.65

# Ground items (weapon/armor/potion/scroll/gold) and the stairs' ladder -
# smaller than monster sprites since these are single-tile pickups, not
# standing creatures. One image per item *kind*, not per tier/type - tier
# color (weapon/armor rarity, scroll type) is shown the same way elite
# monsters are: a tinted glow behind the sprite, not a recolor of it.
ITEM_SPRITE_DIR = os.path.join(ASSETS_DIR, "items")
ITEM_SPRITE_HEIGHT = int(TILE_SIZE * 1.1)
LADDER_SPRITE_PATH = os.path.join(ITEM_SPRITE_DIR, "ladder.png")
LADDER_SPRITE_HEIGHT = int(TILE_SIZE * 1.3)
MERCHANT_SPRITE_PATH = os.path.join(ASSETS_DIR, "merchant.png")
MERCHANT_SPRITE_HEIGHT = int(TILE_SIZE * 1.6)

# Written fresh before every build (CI for Android, the local PyInstaller
# command for Windows) with that build's git commit count - never committed
# to the repo itself. Lets a running build compare itself against the
# commit count baked into the latest GitHub release to know if it's stale.
BUILD_VERSION_PATH = os.path.join(ASSETS_DIR, "build_version.txt")
GITHUB_REPO = "GermanDudeXX/dungeon-crawler"

FOV_RADIUS = 8

COLOR_BG = (10, 10, 14)
COLOR_WALL = (60, 60, 70)
COLOR_WALL_DIM = (25, 25, 30)
COLOR_FLOOR = (90, 90, 100)
COLOR_FLOOR_DIM = (35, 35, 40)
COLOR_PLAYER = (255, 255, 255)
COLOR_STAIRS = (255, 215, 0)
COLOR_STAIRS_UP = (150, 200, 255)
COLOR_POTION = (255, 60, 120)
COLOR_BOSS = (230, 60, 220)
COLOR_HUD_BG = (20, 20, 26)
COLOR_HUD_TEXT = (220, 220, 220)
COLOR_HP_BAR_BG = (60, 20, 20)
COLOR_HP_BAR_FG = (200, 40, 40)
COLOR_XP_BAR_BG = (30, 30, 55)
COLOR_XP_BAR_FG = (90, 90, 220)
COLOR_LOG_TEXT = (180, 180, 190)
COLOR_HELP_TEXT = (140, 140, 150)
COLOR_GOLD = (255, 210, 60)
COLOR_MERCHANT = (80, 200, 220)
COLOR_POISON = (110, 200, 90)
COLOR_TRAP = (200, 80, 60)
COLOR_CRIT = (255, 230, 60)
COLOR_SHRINE = (190, 140, 255)

MONSTER_TYPES = {
    "rat": {
        "char": "r", "color": (140, 100, 60), "hp": 4, "power": 2, "defense": 0, "xp": 4, "name": "rat",
        "flees_below": 0.3,
    },
    "goblin": {"char": "g", "color": (60, 160, 60), "hp": 8, "power": 3, "defense": 1, "xp": 8, "name": "goblin"},
    "orc": {
        "char": "o", "color": (180, 40, 40), "hp": 14, "power": 5, "defense": 2, "xp": 14, "name": "orc",
        "weak": ["frost"],
    },
    "skeleton": {
        "char": "s", "color": (210, 210, 220), "hp": 9, "power": 4, "defense": 1, "xp": 10,
        "name": "skeleton", "ranged": True, "resist": ["poison"], "weak": ["fire"],
    },
    "slime": {
        "char": "z", "color": (70, 200, 140), "hp": 6, "power": 2, "defense": 0, "xp": 6,
        "name": "slime", "splits": True, "weak": ["fire"], "flees_below": 0.25,
    },
    "bat": {
        "char": "b", "color": (150, 90, 170), "hp": 5, "power": 2, "defense": 0, "xp": 6,
        "name": "bat", "speed": 2, "weak": ["lightning"],
    },
    "spider": {
        "char": "x", "color": (100, 50, 130), "hp": 7, "power": 3, "defense": 0, "xp": 9,
        "name": "spider", "poisons": True, "resist": ["poison"],
    },
}

BOSS_KIND_CYCLE = ["orc", "skeleton", "spider", "slime"]
BOSS_TITLES = {
    "orc": "chieftain",
    "skeleton": "king",
    "spider": "queen",
    "slime": "colossus",
}

ELITE_MODIFIERS = [
    {"name": "Fast", "hp_mult": 1.0, "power_mult": 1.1, "defense_mult": 1.0, "speed_bonus": 1, "color": (255, 215, 0)},
    {"name": "Vicious", "hp_mult": 1.2, "power_mult": 1.6, "defense_mult": 1.0, "color": (255, 80, 80)},
    {"name": "Armored", "hp_mult": 1.4, "power_mult": 1.0, "defense_mult": 2.2, "color": (150, 150, 220)},
    {"name": "Regenerating", "hp_mult": 1.6, "power_mult": 1.1, "defense_mult": 1.0, "regen": 1, "color": (100, 220, 120)},
]
ELITE_CHANCE = 0.10
ELITE_XP_MULT = 2.5

# Elemental weapon affixes. "status" names the field on Monster/Player that
# tracks the effect's remaining duration in turns (see Game._attack /
# Game._tick_monster_status); "proc_chance" is the base chance per hit,
# doubled/halved against a monster kind listed as weak/resist to that
# element in MONSTER_TYPES above.
ELEMENTS = {
    "fire": {"name": "Fire", "color": (255, 100, 30), "status": "burn_turns", "duration": 3,
              "bonus_damage": 3, "proc_chance": 0.35},
    "frost": {"name": "Frost", "color": (120, 200, 255), "status": "weaken_turns", "duration": 3,
              "bonus_damage": 2, "proc_chance": 0.4},
    "lightning": {"name": "Lightning", "color": (255, 230, 80), "status": "stun_turns", "duration": 1,
              "bonus_damage": 2, "proc_chance": 0.3},
    "poison": {"name": "Venom", "color": (110, 200, 90), "status": "poison_turns", "duration": 4,
              "bonus_damage": 2, "proc_chance": 0.4},
}
ELEMENT_WEAPON_CHANCE = 0.3
ELEMENT_MIN_LEVEL = 2
BURN_DAMAGE_PER_TURN = 3
WEAKEN_DEFENSE_MULT = 0.6

PERKS = [
    {"id": "power", "name": "Brute Strength", "desc": "+2 Power", "power": 2},
    {"id": "defense", "name": "Iron Skin", "desc": "+2 Defense", "defense": 2},
    {"id": "vitality", "name": "Vitality", "desc": "+10 Max HP", "hp": 10},
    {"id": "precision", "name": "Precision", "desc": "+5% Crit Chance", "crit_bonus": 0.05},
    {"id": "toughness", "name": "Toughness", "desc": "-10% Damage Taken", "damage_reduction": 0.10},
    {"id": "regeneration", "name": "Regeneration", "desc": "Regen 1 HP every 5 turns", "regen_interval": 5},
    {"id": "greed", "name": "Greed", "desc": "+25% Gold Found", "gold_mult": 0.25},
    {"id": "elemental_focus", "name": "Elemental Focus", "desc": "+15% Elemental Proc Chance",
     "elemental_chance_bonus": 0.15},
]

WEAPON_TYPES = [
    {"name": "Dagger", "bonus": 2, "color": (200, 200, 210)},
    {"name": "Short Sword", "bonus": 4, "color": (210, 210, 220)},
    {"name": "Long Sword", "bonus": 6, "color": (220, 220, 235)},
    {"name": "War Axe", "bonus": 9, "color": (230, 230, 245)},
]

ARMOR_TYPES = [
    {"name": "Leather Armor", "bonus": 1, "color": (150, 110, 70)},
    {"name": "Chainmail", "bonus": 3, "color": (170, 170, 180)},
    {"name": "Plate Armor", "bonus": 5, "color": (190, 190, 210)},
]

# Rolled per weapon/armor drop on top of its base type - multiplies that
# type's bonus and replaces its halo/HUD colour, so rarity reads at a
# glance instead of needing a tooltip. min_level gates which tiers can
# even be rolled yet, so early floors never hand out a Legendary drop;
# weight is only compared among tiers already unlocked at the current
# dungeon_level (see Game._roll_rarity).
RARITY_TIERS = [
    {"id": "common", "name": "Common", "mult": 1.0, "color": (200, 200, 205), "weight": 10, "min_level": 1},
    {"id": "uncommon", "name": "Uncommon", "mult": 1.3, "color": (70, 200, 90), "weight": 5, "min_level": 1},
    {"id": "rare", "name": "Rare", "mult": 1.7, "color": (70, 140, 230), "weight": 2.2, "min_level": 3},
    {"id": "epic", "name": "Epic", "mult": 2.1, "color": (180, 90, 230), "weight": 0.9, "min_level": 5},
    {"id": "legendary", "name": "Legendary", "mult": 2.6, "color": (255, 170, 30), "weight": 0.3, "min_level": 8},
]
RARITY_BY_ID = {tier["id"]: tier for tier in RARITY_TIERS}

SCROLL_TYPES = {
    "fireball": {
        "name": "Scroll of Fireball", "char": "?", "color": (255, 120, 40), "key": "F",
        "desc": "Damages the nearest visible enemy and any enemies next to it.",
    },
    "teleport": {
        "name": "Scroll of Teleport", "char": "?", "color": (120, 140, 255), "key": "T",
        "desc": "Blinks you to a random safe spot on this level.",
    },
    "reveal": {
        "name": "Scroll of Reveal", "char": "?", "color": (220, 220, 120), "key": "V",
        "desc": "Reveals the full layout of the current level.",
    },
}

TRAP_TYPES = {
    "spike": {"name": "spike trap", "min_damage": 4, "max_damage": 9},
    "poison": {"name": "poison trap", "poison_turns": 5},
    "alarm": {"name": "alarm trap"},
}
TRAP_CHANCE_PER_ROOM = 0.3
POISON_DAMAGE_PER_TURN = 2

# A single optional shrine tile per level (mutually exclusive with the
# stairs/merchant tiles, see Game._populate_level) that triggers one random
# risk/reward event the moment the player steps on it - no separate menu or
# input needed, same "walk onto it" pattern as traps.
SHRINE_CHANCE_PER_LEVEL = 0.3
SHRINE_EVENTS = [
    {"id": "vitality", "name": "Blessing of Vitality", "weight": 3},
    {"id": "power", "name": "Blessing of Power", "weight": 2},
    {"id": "fortune", "name": "Fortune", "weight": 3},
    {"id": "frailty", "name": "Curse of Frailty", "weight": 2},
    {"id": "ambush", "name": "Vengeful Spirits", "weight": 1.5},
]

MERCHANT_CHANCE_PER_LEVEL = 0.35
SHOP_STOCK = [
    {"kind": "potion", "name": "Healing Potion", "price": 12},
    {"kind": "scroll", "scroll_type": "fireball", "name": "Scroll of Fireball", "price": 20},
    {"kind": "scroll", "scroll_type": "teleport", "name": "Scroll of Teleport", "price": 15},
    {"kind": "scroll", "scroll_type": "reveal", "name": "Scroll of Reveal", "price": 15},
]

ACHIEVEMENTS = [
    ("first_blood", "First Blood", "Defeat your first enemy."),
    ("survivor", "Survivor", "Reach character level 5."),
    ("veteran", "Veteran", "Reach character level 10."),
    ("deep_delver", "Deep Delver", "Reach dungeon level 5."),
    ("spelunker", "Spelunker", "Reach dungeon level 10."),
    ("boss_slayer", "Boss Slayer", "Defeat a boss."),
    ("rich", "Rich", "Carry 100 gold at once."),
    ("hoarder", "Hoarder", "Collect 500 gold in total."),
    ("well_read", "Well Read", "Use 10 scrolls in total."),
    ("persistent", "Persistent", "Die 5 times."),
    ("centurion", "Centurion", "Defeat 100 monsters in total."),
    ("untouchable", "Untouchable", "Reach dungeon level 3 without drinking a potion."),
]
