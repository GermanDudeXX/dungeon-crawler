"""Exercises the real self-update swap script against dummy files.

The batch script is the piece that broke and left a user unable to start
the game at all ("Failed to load Python DLL"), so it gets a real test:
the actual generated script is run by cmd.exe, only with the final
relaunch line stubbed out so nothing gets started.
"""
import os
import subprocess
import sys
import tempfile
import shutil

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
import updater

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def run_script(current, new, faillog, expected_size=None, hold_open=False):
    script = updater.build_swap_script(current, new, faillog, expected_size)
    # Never actually relaunch anything from a test, and do not wait on a
    # process name that will never appear - the dummy exe is not running.
    script = script.replace('start "" "%TARGET%"\r\n', "")
    bat = os.path.join(os.path.dirname(current), "_t_update.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(script)
    subprocess.run(["cmd", "/c", bat], capture_output=True, timeout=180)
    return script


def open_shared(path):
    """Opens a file the way Windows itself holds a running .exe:
    FILE_SHARE_READ | FILE_SHARE_DELETE. That share-delete flag is exactly
    why renaming a running exe is allowed while overwriting it is not, and
    Python's own open() does NOT set it - so a plain open() models a
    stricter, antivirus-style lock, not a running program."""
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    CreateFileW = ctypes.windll.kernel32.CreateFileW
    CreateFileW.restype = wintypes.HANDLE
    h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                    None, OPEN_EXISTING, 0, None)
    if h == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error())
    return h


def scenario(name, make_new=True, corrupt_size=False, hold_handle=False,
             hold_shared=False):
    tmp = tempfile.mkdtemp(prefix="dcswap_")
    current = os.path.join(tmp, "DungeonCrawler.exe")
    new = os.path.join(tmp, "new", "DungeonCrawler.exe")
    os.makedirs(os.path.dirname(new))
    faillog = os.path.join(tmp, "update_failed.txt")
    with open(current, "wb") as f:
        f.write(b"OLDBUILD" * 100)
    if make_new:
        with open(new, "wb") as f:
            f.write(b"NEWBUILD" * 100)
    expected = 800 if not corrupt_size else 999999
    handle = open(current, "rb") if hold_handle else None
    win_handle = open_shared(current) if hold_shared else None
    try:
        run_script(current, new, faillog, expected)
    finally:
        if handle:
            handle.close()
        if win_handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(win_handle)
    body = open(current, "rb").read() if os.path.exists(current) else None
    reason = None
    if os.path.exists(faillog):
        reason = open(faillog).read().strip()
    shutil.rmtree(tmp, ignore_errors=True)
    return body, reason


print("swap script")

body, reason = scenario("happy")
check("happy path installs the new build", body == b"NEWBUILD" * 100, repr(body and body[:16]))
check("happy path leaves no failure marker", reason is None, reason)

# This is the case that actually broke: something still had the exe open
# just after it exited, so the old "move /y new current" failed. A rename
# is allowed against a share-delete handle where an overwrite is not, so
# the swap must succeed here.
body, reason = scenario("running-exe lock", hold_shared=True)
check("swap works while the old exe is still held open",
      body == b"NEWBUILD" * 100, repr(body and body[:16]))
check("held-open case leaves no failure marker", reason is None, reason)

# An exclusive lock (antivirus mid-scan) genuinely cannot be worked
# around. The requirement is only that it never destroys the install: the
# old build must still be there and the user must be told.
body, reason = scenario("exclusive lock", hold_handle=True)
check("exclusive lock keeps the old build intact", body == b"OLDBUILD" * 100,
      repr(body and body[:16]))
check("exclusive lock is reported", reason == "swap-failed", reason)

body, reason = scenario("missing", make_new=False)
check("missing download keeps the old build", body == b"OLDBUILD" * 100)
check("missing download is reported", reason == "missing-download", reason)

body, reason = scenario("truncated", corrupt_size=True)
check("wrong size keeps the old build", body == b"OLDBUILD" * 100)
check("wrong size is reported", reason == "bad-size", reason)

print("failure marker")
staging = updater.staging_dir()
marker = updater.failure_marker_path()
with open(marker, "w") as f:
    f.write("swap-failed\n")
check("marker is read", updater.take_failure_marker() == "swap-failed")
check("marker is consumed", not os.path.exists(marker))
check("no marker returns None", updater.take_failure_marker() is None)

print("stale _MEI cleanup")
temp_root = tempfile.gettempdir()
old_dir = os.path.join(temp_root, "_MEItest01")
fresh_dir = os.path.join(temp_root, "_MEItest02")
for d in (old_dir, fresh_dir):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "python313.dll"), "wb") as f:
        f.write(b"x")
ancient = 1000000000  # long before the 6h cutoff
os.utime(old_dir, (ancient, ancient))
updater._purge_stale_mei_dirs()
check("stale extraction folder is removed", not os.path.exists(old_dir))
check("recent extraction folder is left alone", os.path.exists(fresh_dir))
shutil.rmtree(fresh_dir, ignore_errors=True)

# A folder with a genuinely locked file inside must survive untouched -
# deleting half of a live instance's runtime would be worse than leaking.
locked_dir = os.path.join(temp_root, "_MEItest03")
os.makedirs(locked_dir, exist_ok=True)
locked_file = os.path.join(locked_dir, "python313.dll")
with open(locked_file, "wb") as f:
    f.write(b"x")
os.utime(locked_dir, (ancient, ancient))
fh = open(locked_file, "rb")
try:
    updater._purge_stale_mei_dirs()
    check("in-use extraction folder survives", os.path.exists(locked_file))
finally:
    fh.close()
shutil.rmtree(locked_dir, ignore_errors=True)


print("android class loading")
# The download runs on a worker thread. pyjnius resolves a Java class with
# FindClass, and which class loader that uses depends on the calling
# thread - a Python thread gets the system loader, which cannot see the
# app's own classes. Looking PythonActivity up there fails with
# "Didn't find class ... DexPathList[[directory "."],
# nativeLibraryDirectories=[/system/lib64 ...]]". So every lookup has to
# go through the cache that the main thread fills.
import re

src = open("updater.py", encoding="utf-8").read()
check("there is a main-thread preload", "def preload_android_classes" in src)

names = src.split("_ANDROID_CLASS_NAMES = (")[1].split(")")[0]
for name in ("org.kivy.android.PythonActivity", "android.content.Intent",
             "android.content.ContentValues", "android.provider.MediaStore$Downloads",
             "android.provider.Settings", "android.os.Build$VERSION",
             "android.net.Uri"):
    check(f"{name} is preloaded", name in names, names)

# Only the two cache functions may call autoclass; everything else asks
# the cache, and that is what makes the worker thread safe.
allowed = set()
for fn in ("def preload_android_classes", "def _cls"):
    seg = src[src.index(fn):]
    nxt = seg.find("\ndef ", 1)
    if nxt != -1:
        seg = seg[:nxt]
    allowed.update(ln.strip() for ln in seg.splitlines())
stray = [ln.strip() for ln in src.splitlines()
         if "autoclass(" in ln and not ln.strip().startswith("#")
         and ln.strip() not in allowed]
check("no Java class is looked up outside the cache", not stray, stray)

game_src = open("game.py", encoding="utf-8").read()
check("startup preloads them", "updater.preload_android_classes()" in game_src)
workers = re.findall(r"def worker\(\):(.*?)self\._update_thread = threading",
                     game_src, flags=re.S)
check("the update workers resolve no Java classes themselves",
      bool(workers) and not any("autoclass" in w or "preload_android_classes" in w
                                for w in workers), len(workers))
check("preloading is a no-op off Android",
      updater.preload_android_classes() is None)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all updater swap tests passed")
