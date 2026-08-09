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
# is a 3-wide cross of buttons plus gaps and margins; below this the
# cross would be drawn over the dungeon. _setup_touch_controls also
# clamps the buttons to whatever gutter it actually gets, so a narrower
# device degrades to smaller controls instead of a broken layout.
#
# 3 * 144 + two gaps + two margins. 144px is Android's 48dp minimum touch
# target at density 3, so this is as narrow as the cross can go without
# the buttons dropping under it. It was 540, sized for 152px buttons -
# eight pixels of comfort that cost a whole tile of map width, on a
# screen where the gutters and the HUD between them were taking well over
# half of everything.
MIN_GUTTER_WIDTH = 512

# Height held back for the HUD when fitting the map to a real device.
# This is a *reservation*, not the final height: whatever the map does
# not use goes to the HUD anyway (see Game._fit_screen_to_device), so
# reserving more than the band needs only makes the tiles smaller. The
# band genuinely needs about 190 - the same floor the desktop build uses.
MIN_HUD_HEIGHT = 190
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
BLACKSMITH_SPRITE_PATH = os.path.join(ASSETS_DIR, "blacksmith.png")
BLACKSMITH_SPRITE_HEIGHT = int(TILE_SIZE * 1.6)

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
COLOR_BLACKSMITH = (226, 148, 74)
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

# Behaviours layered on top of the table above rather than baked into it,
# so an existing kind can gain one without its base stats moving.
#
# "kites": backs away when the player closes to melee, then shoots from
# the new distance. Makes a ranged monster something to chase rather than
# something to walk up to and hit.
# "swarms": spawns as a pack of several rather than one at a time.
# "sets_traps": leaves a trap behind it while it retreats.
MONSTER_TYPES["skeleton"]["kites"] = True
MONSTER_TYPES["bat"]["swarms"] = (2, 4)
MONSTER_TYPES["rat"]["swarms"] = (2, 5)
MONSTER_TYPES["goblin"]["sets_traps"] = True

# How close the player has to get before a kiting monster backs off.
KITE_DISTANCE = 2
# A trap-setter drops one at most this often, so a room does not turn
# into a minefield.
TRAP_SETTER_COOLDOWN = 5

# A mimic pretends to be a treasure chest until the player touches it.
# Shares the chest art, so there is no way to tell from a distance -
# which is the entire joke.
MIMIC_CHANCE = 0.25
MIMIC_MIN_LEVEL = 4
MIMIC_MULT = 1.8

# Bosses change behaviour as they lose health. Thresholds are fractions
# of max HP, highest first; the boss bar names the phase it is in.
BOSS_PHASES = [
    {"at": 0.66, "name": "Wounded", "power_mult": 1.15, "color": (232, 181, 75)},
    {"at": 0.33, "name": "Desperate", "power_mult": 1.35, "color": (224, 91, 91)},
]

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
# Every track that exists, for rotation. There are three of them and five
# themes, and each theme used to loop its own one forever - so a long run
# meant the same three and a half minutes over and over. A floor change
# now picks a different track, which is a natural moment for the music to
# change and needs no end-of-track detection: the old "music restarts
# itself every second" bug came from trusting mixer.get_busy(), and
# nothing here asks it anything.
MUSIC_TRACKS = ("crypt.mp3", "caverns.mp3", "vault.mp3")

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

# --- potions -----------------------------------------------------------
# Temporary effects are all expressed as one buff on the player with a
# turn count, instead of a field per effect. There are a dozen of them
# and they stack in any combination, so a field each would have meant a
# dozen places to remember to decrement, serialise and clear.
#
# "power"/"defense"/"crit" are added to the player's own stats while
# active. The flag-style entries (haste, invisible, thorns, lifesteal,
# shield, luck, regen, berserk) are read by the specific piece of code
# that implements them.
BUFFS = {
    "strength":   {"name": "Strength", "power": 4, "color": (236, 122, 74)},
    "stone_skin": {"name": "Stone Skin", "defense": 5, "color": (166, 172, 186)},
    "precision":  {"name": "Precision", "crit": 0.30, "color": (255, 225, 120)},
    "haste":      {"name": "Haste", "haste": True, "color": (120, 214, 255)},
    "invisible":  {"name": "Invisibility", "invisible": True, "color": (168, 158, 214)},
    "thorns":     {"name": "Thorns", "thorns": 4, "color": (198, 132, 96)},
    "lifesteal":  {"name": "Life Leech", "lifesteal": 0.4, "color": (214, 74, 122)},
    "regen":      {"name": "Regeneration", "regen": 3, "color": (120, 214, 140)},
    "luck":       {"name": "Luck", "luck": True, "color": (255, 200, 80)},
    "berserk":    {"name": "Berserk", "power": 7, "defense": -4, "color": (226, 70, 62)},
    "fire_aura":  {"name": "Fire Aura", "burn_attackers": 3, "color": (255, 132, 48)},
    "clumsy":     {"name": "Clumsiness", "power": -3, "color": (140, 128, 120)},
    "frailty":    {"name": "Frailty", "defense": -3, "color": (150, 120, 150)},
}

# Every potion in the game. "flask" names a frame in assets/tiles so the
# colour on the ground matches the one in the inventory. "min_level" gates
# the stronger ones behind depth; "weight" is the relative spawn chance
# among everything already unlocked. Anything with "cursed" can turn up
# in an unidentified flask and is never sold by a merchant.
POTION_TYPES = [
    # -- healing ---------------------------------------------------------
    {"id": "healing", "name": "Healing Potion", "flask": "flask_red",
     "color": (224, 74, 92), "price": 12, "weight": 10, "min_level": 1,
     "effect": {"heal": 15}},
    {"id": "greater_healing", "name": "Greater Healing Potion", "flask": "flask_big_red",
     "color": (240, 96, 96), "price": 30, "weight": 5, "min_level": 4,
     "effect": {"heal": 45}},
    {"id": "full_healing", "name": "Elixir of Life", "flask": "flask_big_red",
     "color": (255, 130, 140), "price": 65, "weight": 2, "min_level": 8,
     "effect": {"heal_pct": 1.0}},
    {"id": "regeneration", "name": "Potion of Regeneration", "flask": "flask_green",
     "color": (120, 214, 140), "price": 28, "weight": 4, "min_level": 3,
     "effect": {"buff": "regen", "turns": 15}},
    # -- permanent -------------------------------------------------------
    {"id": "vitality", "name": "Potion of Vitality", "flask": "flask_big_green",
     "color": (140, 230, 150), "price": 55, "weight": 2, "min_level": 5,
     "effect": {"max_hp": 6}},
    {"id": "might", "name": "Potion of Might", "flask": "flask_big_yellow",
     "color": (236, 160, 70), "price": 60, "weight": 2, "min_level": 6,
     "effect": {"base_power": 1}},
    {"id": "iron_hide", "name": "Potion of Iron Hide", "flask": "flask_big_blue",
     "color": (150, 170, 220), "price": 60, "weight": 2, "min_level": 6,
     "effect": {"base_defense": 1}},
    {"id": "insight", "name": "Potion of Insight", "flask": "flask_big_blue",
     "color": (140, 190, 255), "price": 45, "weight": 3, "min_level": 4,
     "effect": {"xp_levels": 0.5}},
    # -- combat buffs ----------------------------------------------------
    {"id": "strength", "name": "Potion of Strength", "flask": "flask_yellow",
     "color": (236, 122, 74), "price": 24, "weight": 6, "min_level": 2,
     "effect": {"buff": "strength", "turns": 14}},
    {"id": "stone_skin", "name": "Potion of Stone Skin", "flask": "flask_blue",
     "color": (166, 172, 186), "price": 24, "weight": 6, "min_level": 2,
     "effect": {"buff": "stone_skin", "turns": 14}},
    {"id": "precision", "name": "Potion of Precision", "flask": "flask_yellow",
     "color": (255, 225, 120), "price": 26, "weight": 4, "min_level": 3,
     "effect": {"buff": "precision", "turns": 16}},
    {"id": "haste", "name": "Potion of Haste", "flask": "flask_blue",
     "color": (120, 214, 255), "price": 32, "weight": 4, "min_level": 4,
     "effect": {"buff": "haste", "turns": 10}},
    {"id": "berserk", "name": "Berserker's Brew", "flask": "flask_big_red",
     "color": (226, 70, 62), "price": 30, "weight": 3, "min_level": 5,
     "effect": {"buff": "berserk", "turns": 12}},
    {"id": "thorns", "name": "Potion of Thorns", "flask": "flask_green",
     "color": (198, 132, 96), "price": 26, "weight": 3, "min_level": 4,
     "effect": {"buff": "thorns", "turns": 16}},
    {"id": "lifesteal", "name": "Vampiric Draught", "flask": "flask_big_red",
     "color": (214, 74, 122), "price": 38, "weight": 3, "min_level": 6,
     "effect": {"buff": "lifesteal", "turns": 14}},
    {"id": "fire_aura", "name": "Potion of Embers", "flask": "flask_yellow",
     "color": (255, 132, 48), "price": 30, "weight": 3, "min_level": 5,
     "effect": {"buff": "fire_aura", "turns": 14}},
    {"id": "shield", "name": "Potion of Warding", "flask": "flask_big_blue",
     "color": (150, 200, 255), "price": 30, "weight": 4, "min_level": 3,
     "effect": {"shield": 25}},
    # -- utility ---------------------------------------------------------
    {"id": "invisibility", "name": "Potion of Invisibility", "flask": "flask_blue",
     "color": (168, 158, 214), "price": 34, "weight": 3, "min_level": 5,
     "effect": {"buff": "invisible", "turns": 12}},
    {"id": "luck", "name": "Potion of Luck", "flask": "flask_big_yellow",
     "color": (255, 200, 80), "price": 34, "weight": 3, "min_level": 4,
     "effect": {"buff": "luck", "turns": 25}},
    {"id": "clarity", "name": "Potion of Clarity", "flask": "flask_blue",
     "color": (150, 210, 240), "price": 20, "weight": 4, "min_level": 2,
     "effect": {"reveal": True}},
    {"id": "blink", "name": "Potion of Blinking", "flask": "flask_green",
     "color": (170, 140, 240), "price": 22, "weight": 4, "min_level": 3,
     "effect": {"blink": True}},
    {"id": "midas", "name": "Potion of Midas", "flask": "flask_big_yellow",
     "color": (255, 215, 0), "price": 0, "weight": 2, "min_level": 3,
     "effect": {"gold": (25, 70)}},
    # -- cures -----------------------------------------------------------
    {"id": "antidote", "name": "Antidote", "flask": "flask_green",
     "color": (110, 200, 90), "price": 15, "weight": 5, "min_level": 2,
     "effect": {"cure": ["poison_turns"]}},
    {"id": "coagulant", "name": "Coagulant", "flask": "flask_red",
     "color": (200, 90, 90), "price": 15, "weight": 4, "min_level": 3,
     "effect": {"cure": ["bleed_turns"]}},
    {"id": "panacea", "name": "Panacea", "flask": "flask_big_green",
     "color": (190, 240, 200), "price": 40, "weight": 2, "min_level": 6,
     "effect": {"cure": ["poison_turns", "bleed_turns"], "cure_debuffs": True,
                "heal": 20}},
    # -- offensive -------------------------------------------------------
    {"id": "firebomb", "name": "Flask of Fire", "flask": "flask_big_red",
     "color": (255, 110, 40), "price": 28, "weight": 4, "min_level": 3,
     "effect": {"burst_damage": 18, "burst_burn": 3}},
    {"id": "frostbomb", "name": "Flask of Frost", "flask": "flask_big_blue",
     "color": (150, 220, 255), "price": 28, "weight": 3, "min_level": 5,
     "effect": {"burst_damage": 10, "burst_slow": 4}},
    {"id": "thunderbomb", "name": "Flask of Storms", "flask": "flask_big_yellow",
     "color": (255, 240, 140), "price": 34, "weight": 3, "min_level": 7,
     "effect": {"burst_damage": 14, "burst_stun": 2}},
    # -- cursed: only ever found, never sold -----------------------------
    {"id": "murky", "name": "Murky Flask", "flask": "flask_green",
     "color": (120, 130, 96), "price": 0, "weight": 2, "min_level": 2,
     "cursed": True, "effect": {"self_poison": 6}},
    {"id": "bitter", "name": "Bitter Flask", "flask": "flask_yellow",
     "color": (150, 140, 96), "price": 0, "weight": 2, "min_level": 3,
     "cursed": True, "effect": {"buff": "clumsy", "turns": 12}},
    {"id": "brittle", "name": "Brittle Flask", "flask": "flask_blue",
     "color": (140, 130, 160), "price": 0, "weight": 2, "min_level": 4,
     "cursed": True, "effect": {"buff": "frailty", "turns": 12}},
]
POTION_BY_ID = {p["id"]: p for p in POTION_TYPES}
# The one the game starts you with and the one plain "potion" loot means
# when nothing else applies.
DEFAULT_POTION = "healing"
# How far a thrown flask's burst reaches, in tiles.
POTION_BURST_RADIUS = 2
# The HUD's buff row does not wrap, and a dozen buffs can be up at once,
# so it shows this many and counts the rest.
HUD_MAX_BUFF_CHIPS = 5

# --- special rooms and hazards ------------------------------------------
# A mini-boss on floors divisible by this, except where a real boss is
# already waiting (every 5th). Weaker than a boss but well above a
# regular monster, so the gap between boss floors has a landmark in it.
MINI_BOSS_EVERY = 3
MINI_BOSS_MULT = 1.6
MINI_BOSS_XP_MULT = 2.5

# A locked treasure room: one chest, one guardian standing over it, and
# the chest stays shut until the guardian is dead.
TREASURE_ROOM_CHANCE = 0.45
TREASURE_GUARD_MULT = 1.4
TREASURE_MIN_LEVEL = 2

# The boss's stairs are barred until it dies, so a boss floor cannot be
# skipped by walking straight past it to the ladder.
BOSS_DOOR_MIN_LEVEL = 5

# Floor hazards, stepped on rather than triggered like traps: they are
# visible from the start and are meant to be walked around.
HAZARD_CHANCE_PER_ROOM = 0.30
HAZARD_MIN_LEVEL = 3
HAZARD_TYPES = {
    "lava": {"tile": "wall_goo", "damage": 8, "color": (226, 88, 42),
             "burn": 3, "min_level": 3},
    "collapse": {"tile": "hole", "damage": 12, "color": (86, 60, 120),
                 "min_level": 4, "one_shot": True},
    "spikes": {"tile": "floor_spikes_anim_f2", "damage": 6, "color": (198, 86, 86),
               "bleed": 2, "min_level": 3},
}

# The run's final challenge. Reachable, but a long way down.
SUPERBOSS_LEVEL = 25
SUPERBOSS_MULT = 3.0

# Decorations you cannot walk through. A crate or a stone column is a
# solid object and reads as one; a skull lying on the floor does not, so
# it stays walkable. Everything else in FLOOR_DECOR is scenery.
#
# Placing these needs care: a crate dropped in a one-tile corridor can
# seal the stairs off entirely, so Game._scatter_decor checks that the
# level is still fully connected after each one and takes it back if not.
BLOCKING_DECOR = ("crate", "column")

# --- event banners -------------------------------------------------------
# The combat log lives in the bottom-right corner and is easy to miss
# entirely - things like a trap going off, a level-up or "not enough
# gold" happened silently as far as most players were concerned. The
# important ones are announced across the top of the dungeon view as
# well, big enough to read without looking for them.
BANNER_TICKS = 72          # ~2.4s at the 30Hz animation tick
BANNER_FADE_TICKS = 18     # how long the tail of that is spent fading
BANNER_MAX = 3             # older ones are dropped rather than queued

# --- juice ---------------------------------------------------------------
# Particles are plain coloured squares with a velocity and a lifetime -
# no sprites, no alpha surfaces per particle. At this resolution a 3px
# square reads perfectly well as a spark, and anything fancier would
# cost per-frame work on a device that already needed a map cache to hit
# 30fps.
PARTICLE_LIFETIME = 14
PARTICLE_GRAVITY = 0.06
PARTICLE_MAX = 90          # hard cap, so a big fight cannot flood the loop
PARTICLES_PER_HIT = 5
PARTICLES_PER_CRIT = 11
PARTICLES_PER_DEATH = 16

# A critical hit freezes the frame for a moment. The single cheapest way
# to make a big hit *feel* big; measured in animation ticks, not
# milliseconds, so it scales with the existing 30Hz tick.
HITSTOP_TICKS = 4

# --- character classes ---------------------------------------------------
# Picked once per run, after the difficulty. Each is a different opening
# hand rather than a different set of rules: same controls, same systems,
# different numbers and starting kit. Multipliers apply to the base pool
# at creation, exactly like the difficulty's, so later gains stack on top
# instead of being rescaled.
CLASS_SPRITE_DIR = os.path.join(ASSETS_DIR, "classes")
CLASSES = [
    {
        "id": "warrior", "name": "Warrior", "sprite": "knight_m_idle_anim_f0",
        "color": (214, 160, 84),
        "hp_mult": 1.4, "power": 1, "defense": 2, "crit": -0.02,
        "start_potions": {"healing": 2},
        "start_scrolls": {},
        # Indices into WEAPON_TYPES / ARMOR_TYPES, or None for bare hands.
        "start_weapon": 0, "start_armor": 0,
        "blurb": "Tough and armoured. Forgives mistakes.",
    },
    {
        "id": "rogue", "name": "Rogue", "sprite": "elf_m_idle_anim_f0",
        "color": (120, 214, 140),
        "hp_mult": 0.85, "power": 2, "defense": 0, "crit": 0.15,
        "start_potions": {"healing": 1, "haste": 1},
        "start_scrolls": {"teleport": 1},
        "start_weapon": 1, "start_armor": None,
        "blurb": "Fragile, fast, and crits constantly.",
    },
    {
        "id": "mage", "name": "Mage", "sprite": "wizzard_m_idle_anim_f0",
        "color": (150, 170, 255),
        "hp_mult": 0.8, "power": 0, "defense": 0, "crit": 0.05,
        "elemental_chance": 0.35,
        "start_potions": {"healing": 1, "shield": 1},
        "start_scrolls": {"fireball": 2, "reveal": 1},
        "start_weapon": None, "start_armor": None,
        "blurb": "Weak in melee, but scrolls and elements answer to you.",
    },
]
CLASS_BY_ID = {c["id"]: c for c in CLASSES}
DEFAULT_CLASS = "warrior"

# --- the blacksmith ------------------------------------------------------
# Gold has nothing to buy past the first few floors: the shop's stock is
# fixed and cheap, so a long run ends holding hundreds of unspendable
# coins. The smith is the sink - he upgrades what you already carry
# rather than selling you something new, so the gear you found stays the
# gear you use.
#
# Price climbs with the bonus already on the item, so the first upgrade
# is cheap and the tenth is a real decision.
BLACKSMITH_CHANCE_PER_LEVEL = 0.30
BLACKSMITH_MIN_LEVEL = 3
BLACKSMITH_BASE_PRICE = 25
BLACKSMITH_PRICE_PER_POINT = 18
BLACKSMITH_WEAPON_STEP = 2      # +bonus per weapon upgrade
BLACKSMITH_ARMOR_STEP = 1
# Enchanting an unenchanted weapon, or rerolling an existing element.
BLACKSMITH_ENCHANT_PRICE = 90
BLACKSMITH_REFORGE_PRICE = 140  # reroll rarity, one tier up if possible

# --- heavily guarded vault ----------------------------------------------
# A room the player can see is worth robbing and has to decide whether
# they can survive. Several elites at once rather than one big monster:
# a crowd is a different problem from a boss, and this game had no
# encounter that posed it.
VAULT_CHANCE_PER_LEVEL = 0.22
VAULT_MIN_LEVEL = 5
VAULT_GUARDS = (3, 5)
VAULT_GUARD_MULT = 1.3

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
