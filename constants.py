import os

TILE_SIZE = 24
MAP_WIDTH = 40
MAP_HEIGHT = 25

HUD_HEIGHT = 190
SCREEN_WIDTH = MAP_WIDTH * TILE_SIZE
SCREEN_HEIGHT = MAP_HEIGHT * TILE_SIZE + HUD_HEIGHT

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
PLAYER_SPRITE_PATH = os.path.join(ASSETS_DIR, "player.png")
PLAYER_SPRITE_HEIGHT = int(TILE_SIZE * 1.8)

FOV_RADIUS = 8

COLOR_BG = (10, 10, 14)
COLOR_WALL = (60, 60, 70)
COLOR_WALL_DIM = (25, 25, 30)
COLOR_FLOOR = (90, 90, 100)
COLOR_FLOOR_DIM = (35, 35, 40)
COLOR_PLAYER = (255, 255, 255)
COLOR_STAIRS = (255, 215, 0)
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

MONSTER_TYPES = {
    "rat": {"char": "r", "color": (140, 100, 60), "hp": 4, "power": 2, "defense": 0, "xp": 4, "name": "rat"},
    "goblin": {"char": "g", "color": (60, 160, 60), "hp": 8, "power": 3, "defense": 1, "xp": 8, "name": "goblin"},
    "orc": {"char": "o", "color": (180, 40, 40), "hp": 14, "power": 5, "defense": 2, "xp": 14, "name": "orc"},
}

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
