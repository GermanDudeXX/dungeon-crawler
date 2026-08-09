"""The first-run installer must only appear when it should, and must
install to a writable, non-protected location.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.pop("ANDROID_ARGUMENT", None)

import pygame
pygame.init()

import installer
import game

fails = []
real_exec, real_frozen = sys.executable, getattr(sys, "frozen", False)


def as_frozen_exe(path):
    sys.frozen = True
    sys.executable = path


def restore():
    sys.executable = real_exec
    if real_frozen:
        sys.frozen = True
    elif hasattr(sys, "frozen"):
        del sys.frozen


# --- 1. running from source must never prompt ---
restore()
if installer.should_offer_install():
    fails.append("prompts when running from source, where there is no exe to install")
else:
    print("  running from source -> no prompt")

# --- 2. the install target must be writable and not a protected folder ---
target = installer.default_install_dir()
low = target.lower()
for protected in ("\\desktop", "\\documents", "\\downloads", "\\pictures"):
    if protected in low:
        fails.append(f"install target {target} is inside a Controlled-Folder-Access location")
os.makedirs(target, exist_ok=True)
probe = os.path.join(target, ".probe")
try:
    open(probe, "w").close()
    os.remove(probe)
    print(f"  install target is writable: {target}")
except OSError as exc:
    fails.append(f"install target is not writable: {exc}")

# --- 3. a fake exe in Downloads should prompt; the installed copy should not ---
tmp = tempfile.mkdtemp(prefix="dctest_")
fake_downloads = os.path.join(tmp, "Downloads")
os.makedirs(fake_downloads)
fake_exe = os.path.join(fake_downloads, installer.EXE_NAME)
with open(fake_exe, "wb") as f:
    f.write(b"MZ" + b"\0" * 4096)

as_frozen_exe(fake_exe)
if not installer.should_offer_install():
    fails.append("an exe outside the install dir did NOT prompt")
else:
    print("  exe in Downloads -> prompts")

# --- 4. declining writes a marker and suppresses the prompt ---
if not installer.decline():
    fails.append("decline() could not write its marker")
if installer.should_offer_install():
    fails.append("still prompts after the user declined")
else:
    print("  after declining -> no longer prompts")
os.remove(installer.declined_path())

# --- 5. installing copies the exe to the target ---
sandbox = os.path.join(tmp, "Programs", "DungeonCrawler")
installed = installer.install(sandbox)
if not os.path.exists(installed):
    fails.append("install() did not produce an exe at the target")
elif os.path.getsize(installed) != os.path.getsize(fake_exe):
    fails.append("the installed exe differs in size from the source")
else:
    print(f"  install() copied the exe ({os.path.getsize(installed)} bytes)")

# --- 6. the installed copy must not prompt again ---
as_frozen_exe(installer.installed_exe_path())
if installer.should_offer_install():
    fails.append("the installed copy still prompts to install")
else:
    print("  installed copy -> no prompt")

# --- 7. the prompt screen renders in both languages and in every phase ---
restore()
g = game.Game()
for lang in ("en", "de"):
    g.settings["language"] = lang
    for phase in ("prompt", "working", "done", "failed"):
        g.install_phase = phase
        g.install_error = "Access is denied"
        g.state = "install_prompt"
        try:
            g.render()
        except Exception as exc:      # noqa: BLE001
            fails.append(f"{lang}/{phase}: install prompt failed to render: {exc}")
    # the prompt phase must offer both choices as real targets
    g.install_phase = "prompt"
    g.render()
    keys = {k for _, k in g._tap_targets}
    if pygame.K_RETURN not in keys or pygame.K_ESCAPE not in keys:
        fails.append(f"{lang}: install prompt is missing INSTALL/JUST PLAY targets")
print("  prompt renders in all phases, both languages, with both buttons")

shutil.rmtree(tmp, ignore_errors=True)

if fails:
    print("\nFAILURES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL INSTALLER CHECKS PASSED")
