"""Where save data lives on Android, and that an update cannot eat it.

python-for-android unpacks the app into <files>/app and deletes that
whole directory whenever the version changes. Anything written next to
the source is therefore gone on the next update - stats, the run in
progress, and every setting - which is what made the app keep coming
back in English. These checks pin the data to <files> itself.

Run against a copy of persistence.py in a temporary directory, so that
"next to the source" is a throwaway path and not the real repository.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kept until the end: the assertions read the files the probe left behind,
# so a probe that cleaned up after itself would delete its own evidence.
_to_clean = []

PROBE = """
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persistence
print(json.dumps({
    "base": persistence.BASE_DIR,
    "stats": persistence.STATS_PATH,
    "settings": persistence.SETTINGS_PATH,
}))
"""


def probe(env_extra, legacy_files=None):
    """Imports a copy of persistence.py under the given environment."""
    tmp = tempfile.mkdtemp(prefix="dc_paths_")
    _to_clean.append(tmp)
    app = os.path.join(tmp, "files", "app")
    os.makedirs(app)
    shutil.copy(os.path.join(ROOT, "persistence.py"), app)
    for name, content in (legacy_files or {}).items():
        with open(os.path.join(app, name), "w", encoding="utf-8") as f:
            f.write(content)
    probe_py = os.path.join(app, "probe.py")
    with open(probe_py, "w", encoding="utf-8") as f:
        f.write(PROBE)

    env = dict(os.environ)
    env.pop("ANDROID_ARGUMENT", None)
    env.pop("ANDROID_PRIVATE", None)
    for k, v in env_extra.items():
        env[k] = v.replace("{files}", os.path.join(tmp, "files"))
    out = subprocess.run([sys.executable, probe_py], env=env,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    paths = json.loads(out.stdout.strip().splitlines()[-1])
    left = sorted(n for n in os.listdir(app) if n.endswith(".json"))
    return paths, app, os.path.join(tmp, "files"), left


# --- 1. on Android the data sits in <files>, not in <files>/app -----------
paths, app, files, _ = probe({"ANDROID_ARGUMENT": "1",
                              "ANDROID_PRIVATE": "{files}"})
assert os.path.abspath(paths["base"]) == os.path.abspath(files), (
    f"save data lives in {paths['base']}, not in ANDROID_PRIVATE ({files})")
assert os.path.abspath(paths["base"]) != os.path.abspath(app), (
    "save data still lives in the directory p4a deletes on every update")
print(f"  Android: data in <files>, not <files>/app")

# --- 2. and it is carried over from where it used to live -----------------
paths, app, files, left = probe(
    {"ANDROID_ARGUMENT": "1", "ANDROID_PRIVATE": "{files}"},
    legacy_files={"stats.json": '{"runs": 7}',
                  "settings.json": '{"language": "de"}'})
moved = os.path.join(files, "stats.json")
assert os.path.exists(moved), "an existing stats.json was not carried over"
with open(moved, encoding="utf-8") as f:
    assert json.load(f) == {"runs": 7}, "the carried-over file lost its content"
with open(os.path.join(files, "settings.json"), encoding="utf-8") as f:
    assert json.load(f) == {"language": "de"}, "settings were not carried over"
assert not left, f"the old copies were left behind: {left}"
print("  an existing stats.json/settings.json is moved, once, and not copied")

# --- 3. running from source on a PC is unchanged --------------------------
paths, app, files, _ = probe({})
assert os.path.abspath(paths["base"]) == os.path.abspath(app), (
    "running from source no longer keeps its data next to the .py files")
print("  from source on a PC: unchanged, data next to the .py files")

# A missing ANDROID_PRIVATE must not produce a path in a directory that
# does not exist - it falls back to the old behaviour rather than failing
# to save at all.
paths, app, files, _ = probe({"ANDROID_ARGUMENT": "1"})
assert os.path.abspath(paths["base"]) == os.path.abspath(app), (
    "with no ANDROID_PRIVATE the base directory went somewhere unexpected")
print("  no ANDROID_PRIVATE: falls back instead of failing")

for _tmp in _to_clean:
    shutil.rmtree(_tmp, ignore_errors=True)

print("\nALL ANDROID-PATH CHECKS PASSED")
