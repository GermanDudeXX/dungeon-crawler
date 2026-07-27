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

# Absolute floor a gutter can shrink to when the real device's aspect
# ratio is fitted at startup (see Game._fit_screen_to_device). The D-pad
# is a 3-wide cross of Game.btn_h-sized buttons plus gaps and margins, so
# the gutter has to hold roughly 3 * 152 + padding. Below this the cross
# would be drawn over the dungeon; _setup_touch_controls additionally
# clamps the buttons to whatever gutter it actually gets, so a narrower
# device degrades to smaller controls instead of a broken layout.
MIN_GUTTER_WIDTH = 540
SCREEN_HEIGHT = MAP_HEIGHT * TILE_SIZE + HUD_HEIGHT

# Menu/info screens are laid out from these sizes rather than by zooming a
# fixed small design, which is what kept the buttons tiny: a uniform zoom
# has to shrink until the screen's *whole* original design fits, so the
# densest screen dictated the size of every button everywhere.
#
# The numbers are chosen against a 1098px-tall canvas on a density-3.0
# phone, where 1 logical px == 1 physical px, so:
#   - Android's minimum touch target is 48dp = 144px; BTN_H sits above it
#   - comfortable body text is ~16sp = 48px of glyph, and pygame's default
#     font renders a glyph about 0.67x its nominal size, hence 68
# UI_REF_HEIGHT is what they were measured against; Game scales them by
# SCREEN_HEIGHT/UI_REF_HEIGHT so a smaller canvas (desktop, or a low-res
# phone) stays proportionate instead of overflowing.
UI_REF_HEIGHT = 1098
# Desktop needs its own factor, not just the canvas-height ratio. The
# ladder above is sized for a phone: a dense screen held at arm's length,
# where a 48dp touch target is genuinely ~144px. On a monitor one logical
# pixel is one screen pixel viewed from ~60cm and input is a mouse, so the
# same numbers come out enormous. This lands the desktop build on roughly
# the sizes it had before (body text ~16px of glyph, buttons ~54px).
UI_DESKTOP_FACTOR = 0.46

FONT_TITLE = 130      # screen titles, bold
FONT_H1 = 90          # section headings, bold
FONT_BODY = 68        # normal reading text
FONT_SM = 54          # secondary/help text
FONT_XS = 44          # dense list rows

BTN_H = 152           # ~50dp: comfortably over Android's 48dp minimum
BTN_H_HERO = 184      # for a screen with room to spare
BTN_MIN_W = 260
BTN_PAD_X = 40        # per side, added to the measured label width
BTN_GAP = 22
# Taps count anywhere within this many px outside the drawn button, so a
# slightly-off thumb still registers without making the button look huge.
BTN_TAP_SLOP = 20

PAD = 34              # screen margin
GAP_S = 16
GAP_M = 24
GAP_L = 34
GAP_XL = 46

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

# Dungeon tiles (0x72 DungeonTileset II, CC0). 16x16 source art scaled up
# to TILE_SIZE with transform.scale - never smoothscale, which turns
# pixel art into mush. Painted once per FOV change into the map cache,
# never per frame.
TILE_SPRITE_DIR = os.path.join(ASSETS_DIR, "tiles")
TILE_SOURCE_SIZE = 16

# How many distinct floor variants exist (floor_1..floor_N). Picked per
# cell from a hash of its coordinates so the pattern is stable - random
# per repaint would make the whole floor shimmer every time the field of
# view changes.
FLOOR_VARIANTS = 8

# Tiles the player has already seen but cannot currently see are drawn
# darker rather than in a separate "dim" colour, so one set of art covers
# both states.
TILE_DIM_FACTOR = 0.42
# Strength of the per-tier colour wash over the grey/brown source art, so
# five dungeon themes come out of one tileset instead of five.
TILE_TINT_STRENGTH = 0.55

# Written fresh before every build (CI for Android, the local PyInstaller
# command for Windows) with that build's git commit count - never committed
# to the repo itself. Lets a running build compare itself against the
# commit count baked into the latest GitHub release to know if it's stale.
BUILD_VERSION_PATH = os.path.join(ASSETS_DIR, "build_version.txt")
# Bundled CA roots. Android's system trust store is not in a form OpenSSL
# reads, and python-for-android ships no bundle, so HTTPS to GitHub failed
# with CERTIFICATE_VERIFY_FAILED. Shipping the roots keeps verification ON
# - the updater downloads code that then runs, so turning verification off
# would be the wrong fix.
CA_BUNDLE_PATH = os.path.join(ASSETS_DIR, "cacert.pem")
GITHUB_REPO = "GermanDudeXX/dungeon-crawler"

FOV_RADIUS = 8

# --- theme -------------------------------------------------------------
# One palette everything draws from, instead of grey boxes with grey
# borders. Two surface levels give depth without gradients or shadows
# (both expensive per frame at this resolution), and a single warm accent
# marks whatever the primary action on a screen is.
COLOR_SURFACE = (23, 27, 36)        # panels/cards sitting on the background
COLOR_SURFACE_HI = (33, 40, 52)     # raised: buttons, active states
COLOR_BORDER = (52, 62, 78)         # normal outline
COLOR_BORDER_HI = (86, 102, 126)    # emphasised outline
COLOR_ACCENT = (232, 181, 75)       # gold - primary action, titles
COLOR_ACCENT_DIM = (120, 92, 34)    # accent used as a subtle underline
COLOR_ON_ACCENT = (22, 18, 8)       # text drawn on top of the accent fill
COLOR_TEXT = (230, 234, 242)
COLOR_TEXT_DIM = (150, 162, 181)
COLOR_DANGER = (224, 91, 91)
COLOR_SUCCESS = (91, 201, 138)

COLOR_BG = (13, 15, 20)
COLOR_WALL = (60, 60, 70)
COLOR_WALL_DIM = (25, 25, 30)
COLOR_FLOOR = (90, 90, 100)
COLOR_FLOOR_DIM = (35, 35, 40)
COLOR_PLAYER = (255, 255, 255)
COLOR_STAIRS = (255, 215, 0)
COLOR_STAIRS_UP = (150, 200, 255)
COLOR_POTION = (255, 60, 120)
COLOR_BOSS = (230, 60, 220)
COLOR_HUD_BG = COLOR_SURFACE
COLOR_HUD_TEXT = COLOR_TEXT
COLOR_HP_BAR_BG = (58, 26, 30)
COLOR_HP_BAR_FG = (214, 68, 72)
COLOR_XP_BAR_BG = (28, 34, 58)
COLOR_XP_BAR_FG = (104, 124, 232)
COLOR_LOG_TEXT = COLOR_TEXT_DIM
COLOR_HELP_TEXT = COLOR_TEXT_DIM
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

# Every LEVELS_PER_TIER floors the dungeon changes theme AND gets
# meaningfully harder - previously difficulty only came from spawning a
# few more monsters per floor, so deep runs stopped escalating. Each tier
# repaints the tiles and multiplies monster stats. Past the last entry the
# themes cycle again while the multiplier keeps climbing (see
# Game._tier_for_level), so there is no ceiling.
LEVELS_PER_TIER = 10

DUNGEON_TIERS = [
    {
        "id": "crypt", "name": "Crypt",
        "wall": (60, 60, 70), "wall_dim": (25, 25, 30),
        "floor": (90, 90, 100), "floor_dim": (35, 35, 40),
        "tile_tint": (150, 152, 178),
        "music": "crypt.mp3",
    },
    {
        "id": "caverns", "name": "Caverns",
        "wall": (86, 66, 46), "wall_dim": (34, 27, 20),
        "floor": (112, 92, 68), "floor_dim": (44, 37, 28),
        "tile_tint": (214, 172, 126),
        "music": "caverns.mp3",
    },
    {
        "id": "vault", "name": "Iron Vault",
        "wall": (58, 68, 86), "wall_dim": (24, 28, 36),
        "floor": (84, 96, 116), "floor_dim": (33, 38, 47),
        "tile_tint": (134, 158, 196),
        "music": "vault.mp3",
    },
    {
        "id": "inferno", "name": "Inferno",
        "wall": (96, 44, 34), "wall_dim": (38, 18, 14),
        "floor": (124, 62, 44), "floor_dim": (48, 25, 18),
        "tile_tint": (206, 112, 78),
        "music": "caverns.mp3",
    },
    {
        "id": "frost", "name": "Frost Vault",
        "wall": (72, 92, 108), "wall_dim": (29, 37, 44),
        "floor": (108, 132, 152), "floor_dim": (43, 53, 61),
        "tile_tint": (158, 198, 220),
        "music": "vault.mp3",
    },
]
# Monster stats scale as TIER_GROWTH ** tier_index. Deriving it from the
# index rather than from a per-theme constant is what keeps it monotone:
# with a per-theme value the multiplier fell back when the themes started
# over (floor 51 came out easier than floor 50).
TIER_GROWTH = 1.33

MUSIC_DIR = os.path.join(ASSETS_DIR, "music")

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
# Bleed is the crit-only counterpart to poison: roughly double the damage
# over half the duration, so it matters in the fight it started rather
# than being a slow drain. Applied by any critical melee hit (see
# Game._attack), independent of whatever element the weapon carries.
BLEED_DAMAGE_PER_TURN = 5
BLEED_TURNS = 2
# Frost additionally slows: a slowed monster only gets to act on every
# other turn (see Game._enemy_turn), which is what turns the element from
# "slightly more damage" into real crowd control.
SLOW_TURNS = 3

# Every status a monster (or the player) can carry, in the order they are
# drawn above the health bar. "field" is the attribute holding the
# remaining turn count; "char" is the single-glyph badge.
STATUS_BADGES = [
    {"field": "burn_turns", "char": "F", "color": (255, 100, 30)},
    {"field": "poison_turns", "char": "G", "color": (110, 200, 90)},
    {"field": "bleed_turns", "char": "B", "color": (224, 60, 60)},
    {"field": "stun_turns", "char": "!", "color": (255, 230, 80)},
    {"field": "slow_turns", "char": "S", "color": (120, 200, 255)},
    {"field": "weaken_turns", "char": "W", "color": (150, 170, 220)},
]

# Difficulty multipliers, chosen once per run. player_hp scales the
# starting/max pool, the two damage numbers scale dealt/received damage,
# and shop_markup_per_level makes the merchant progressively gouge you on
# the harder settings instead of being a flat safety valve.
DIFFICULTIES = [
    {"id": "easy", "name": "Easy", "player_damage": 1.0, "player_hp": 2.0,
     "enemy_hp": 0.75, "enemy_damage": 0.5, "shop_markup_per_level": 0.0,
     "color": (91, 201, 138)},
    {"id": "normal", "name": "Normal", "player_damage": 1.0, "player_hp": 1.0,
     "enemy_hp": 1.0, "enemy_damage": 1.0, "shop_markup_per_level": 0.0,
     "color": (230, 234, 242)},
    {"id": "hard", "name": "Hard", "player_damage": 1.2, "player_hp": 0.75,
     "enemy_hp": 1.25, "enemy_damage": 1.25, "shop_markup_per_level": 0.20,
     "color": (232, 181, 75)},
    {"id": "hardcore", "name": "Hardcore", "player_damage": 0.5, "player_hp": 0.5,
     "enemy_hp": 2.0, "enemy_damage": 2.0, "shop_markup_per_level": 0.50,
     "color": (224, 91, 91)},
]
DIFFICULTY_BY_ID = {d["id"]: d for d in DIFFICULTIES}
DEFAULT_DIFFICULTY = "normal"

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
