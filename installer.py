"""First-run installer for the Windows build.

The game ships as a single .exe, which people naturally leave in
Downloads or on the Desktop. Both are covered by Windows' Controlled
Folder Access (ransomware protection), which blocks writes from any
application it does not recognise - and an unsigned PyInstaller build
never is. That is what made the in-app updater fail with a permission
error that running as Administrator did not fix.

Installing into %LOCALAPPDATA%\\Programs solves it properly: that path is
per-user, always writable, needs no elevation, and is not a protected
location, so updates can replace the exe in place from then on.
"""
import os
import shutil
import subprocess
import sys

APP_NAME = "Dungeon Crawler"
EXE_NAME = "DungeonCrawler.exe"
# Written next to the exe when the user chooses to keep it where it is,
# so the prompt does not reappear on every launch.
PORTABLE_MARKER = ".dungeoncrawler_portable"


def is_frozen():
    return getattr(sys, "frozen", False)


def current_exe():
    return os.path.abspath(sys.executable)


def default_install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", "DungeonCrawler")


def installed_exe_path():
    return os.path.join(default_install_dir(), EXE_NAME)


def is_installed():
    """True when the running exe IS the installed copy."""
    if not is_frozen():
        return False
    return os.path.normcase(current_exe()) == os.path.normcase(installed_exe_path())


def declined_path():
    return os.path.join(os.path.dirname(current_exe()), PORTABLE_MARKER)


def has_declined():
    try:
        return os.path.exists(declined_path())
    except OSError:
        return False


def decline():
    """Remember that the user wants to run it from where it is."""
    try:
        with open(declined_path(), "w", encoding="utf-8") as f:
            f.write("The install prompt is suppressed while this file exists.\n")
        return True
    except OSError:
        # Cannot even write a marker here - that is exactly the
        # unwritable-folder case the installer exists for, so just let
        # the prompt come back next time rather than failing.
        return False


def should_offer_install():
    return is_frozen() and not is_installed() and not has_declined()


def _make_shortcut(link_path, target, working_dir):
    """Create a .lnk via WScript.Shell.

    Done through PowerShell rather than a Python COM binding so the build
    needs no extra dependency (pywin32 is not in requirements and would
    inflate the exe).
    """
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
        "$s.TargetPath = '{target}';"
        "$s.WorkingDirectory = '{wd}';"
        "$s.Description = '{desc}';"
        "$s.Save()"
    ).format(
        link=link_path.replace("'", "''"),
        target=target.replace("'", "''"),
        wd=working_dir.replace("'", "''"),
        desc=APP_NAME,
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        capture_output=True,
        timeout=30,
        check=False,
    )


def create_shortcuts(target_exe):
    """Start-menu and desktop shortcuts. Best-effort: never fatal."""
    made = []
    target_dir = os.path.dirname(target_exe)

    appdata = os.environ.get("APPDATA")
    if appdata:
        start_menu = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")
        try:
            os.makedirs(start_menu, exist_ok=True)
            link = os.path.join(start_menu, f"{APP_NAME}.lnk")
            _make_shortcut(link, target_exe, target_dir)
            if os.path.exists(link):
                made.append("start menu")
        except (OSError, subprocess.SubprocessError):
            pass

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        try:
            link = os.path.join(desktop, f"{APP_NAME}.lnk")
            _make_shortcut(link, target_exe, target_dir)
            if os.path.exists(link):
                made.append("desktop")
        except (OSError, subprocess.SubprocessError):
            pass
    return made


def install(target_dir=None):
    """Copy the running exe into the install directory.

    Returns the installed exe path. Raises OSError with a usable message
    if it cannot be done.
    """
    target_dir = target_dir or default_install_dir()
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, EXE_NAME)

    source = current_exe()
    if os.path.normcase(source) == os.path.normcase(target):
        return target

    # Windows lets a running exe be read, just not overwritten - so
    # copying ourselves out is fine, while replacing an existing installed
    # copy that is currently running is not. That case cannot happen here
    # (we only run this when we are NOT the installed copy), but an older
    # installed copy may still be present and must be replaced.
    shutil.copy2(source, target)
    return target


def launch(path):
    subprocess.Popen(
        [path],
        cwd=os.path.dirname(path),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
