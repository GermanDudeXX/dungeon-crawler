import json
import os
import sys

# A PyInstaller-frozen exe's __file__ resolves inside its temporary
# extraction dir (sys._MEIPASS), which gets wiped on exit, so save data
# can't live there. Earlier this wrote next to the .exe itself instead -
# works, but leaves stats.json/save.json/settings.json sitting in plain
# sight in whatever folder the user put the .exe (typically Downloads).
# Windows' own per-user AppData folder is the conventional place for this
# kind of data and is hidden from Explorer by default, so use that
# instead - %APPDATA%\DungeonCrawler\. Not applicable on Android (no
# sys.frozen there either way; p4a's own app-private storage already
# keeps this out of casual sight without any special-casing here) or
# when running from source (kept next to the .py files for dev
# convenience, matching how the test scripts already expect it).
if getattr(sys, "frozen", False):
    _appdata = os.environ.get("APPDATA")
    if _appdata:
        BASE_DIR = os.path.join(_appdata, "DungeonCrawler")
        os.makedirs(BASE_DIR, exist_ok=True)
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif "ANDROID_ARGUMENT" in os.environ:
    # python-for-android unpacks the app into <files>/app, and on every
    # version change it deletes that entire directory and unpacks the new
    # one. Saving next to the source - which is what the branch below
    # does - therefore loses stats, the current run and every setting on
    # each update, silently, which is why the app kept coming back in
    # English. ANDROID_PRIVATE is <files> itself, one level up, and p4a
    # never touches it.
    BASE_DIR = (os.environ.get("ANDROID_PRIVATE")
                or os.path.dirname(os.path.abspath(__file__)))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(BASE_DIR, "stats.json")
SAVE_PATH = os.path.join(BASE_DIR, "save.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")


def _migrate_legacy_files():
    """Moves stats/save/settings out of wherever an earlier build kept them.

    Once, on the way past. On Windows that was next to the .exe (typically
    the Downloads folder); on Android it was next to the source, in the
    directory p4a wipes on every update. Neither switch should look like
    lost progress to someone who already had real save data.
    """
    if getattr(sys, "frozen", False):
        legacy_dir = os.path.dirname(os.path.abspath(sys.executable))
    elif "ANDROID_ARGUMENT" in os.environ:
        legacy_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        return
    if os.path.abspath(legacy_dir) == os.path.abspath(BASE_DIR):
        return
    for name, dest in (("stats.json", STATS_PATH), ("save.json", SAVE_PATH), ("settings.json", SETTINGS_PATH)):
        legacy_path = os.path.join(legacy_dir, name)
        if os.path.exists(legacy_path) and not os.path.exists(dest):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
                os.remove(legacy_path)
            except OSError:
                pass


_migrate_legacy_files()

DEFAULT_SETTINGS = {
    "language": "en",
    "show_touch_controls": True,
    "volume": 0.4,
    "music": True,
    "difficulty": "normal",
    "char_class": "warrior",
    "zoom": 1.5,
    "render_scale": "auto",
    "show_fps": False,
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


def device_language():
    """The language the device is set to, as one of locale_text's codes.

    A fresh install has no settings file. Defaulting flatly to English
    meant the first screen was in a language the player had not picked,
    and there is no first-run prompt to correct it - they had to find
    Settings in a menu they could not read yet. This comes up more often
    than "first install" suggests: an Android app whose signing key
    changes has to be reinstalled, which takes the settings with it.

    Only the two languages the game actually has are considered.
    """
    tag = ""
    if "ANDROID_ARGUMENT" in os.environ:
        try:
            from jnius import autoclass
            tag = autoclass("java.util.Locale").getDefault().getLanguage() or ""
        except Exception:
            # Any failure here (no pyjnius, a class loader that cannot
            # see it) only means we do not know - never a broken start.
            tag = ""
    if not tag:
        for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            tag = os.environ.get(var) or ""
            if tag:
                break
    if not tag:
        # Windows sets none of those, and this is where a German
        # desktop actually answers.
        try:
            import locale
            tag = locale.getdefaultlocale()[0] or ""
        except (ValueError, TypeError, AttributeError):
            tag = ""
    return "de" if tag.lower().startswith("de") else "en"


def _defaults_for_a_new_install():
    fresh = dict(DEFAULT_SETTINGS)
    fresh["language"] = device_language()
    return fresh


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        return _defaults_for_a_new_install()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _defaults_for_a_new_install()
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(data):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
