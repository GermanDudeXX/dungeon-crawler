import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(BASE_DIR, "stats.json")
SAVE_PATH = os.path.join(BASE_DIR, "save.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "language": "en",
    "show_touch_controls": True,
}

DEFAULT_STATS = {
    "games_played": 0,
    "deaths": 0,
    "total_kills": 0,
    "kills_by_monster": {
        "rat": 0, "goblin": 0, "orc": 0, "boss": 0,
        "skeleton": 0, "slime": 0, "bat": 0, "spider": 0,
    },
    "deepest_level_ever": 1,
    "most_kills_in_a_run": 0,
    "highest_character_level": 1,
    "total_potions_drunk": 0,
    "total_gold_collected": 0,
    "total_scrolls_used": 0,
    "achievements_unlocked": [],
    "bestiary_seen": [],
}


def _default_stats():
    stats = dict(DEFAULT_STATS)
    stats["kills_by_monster"] = dict(DEFAULT_STATS["kills_by_monster"])
    stats["achievements_unlocked"] = list(DEFAULT_STATS["achievements_unlocked"])
    stats["bestiary_seen"] = list(DEFAULT_STATS["bestiary_seen"])
    return stats


def load_stats():
    if not os.path.exists(STATS_PATH):
        return _default_stats()
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_stats()

    merged = _default_stats()
    merged.update(data)
    merged["kills_by_monster"] = {**merged["kills_by_monster"], **data.get("kills_by_monster", {})}
    return merged


def save_stats(data):
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_save():
    if not os.path.exists(SAVE_PATH):
        return None
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_run(data):
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def delete_save():
    if os.path.exists(SAVE_PATH):
        os.remove(SAVE_PATH)


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(data):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
