import json
import os
import re
import subprocess
import sys
import urllib.request

import constants as C

ON_ANDROID = "ANDROID_ARGUMENT" in os.environ

RELEASE_TAG = "android-latest" if ON_ANDROID else "windows-latest"
ASSET_EXT = ".apk" if ON_ANDROID else ".exe"
API_URL = f"https://api.github.com/repos/{C.GITHUB_REPO}/releases/tags/{RELEASE_TAG}"
REQUEST_TIMEOUT = 8
_HEADERS = {"User-Agent": "dungeon-crawler-updater"}


def current_build():
    try:
        with open(C.BUILD_VERSION_PATH, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def check_for_update():
    """Returns an update-info dict if a newer build exists, or None if
    already up to date. Raises on any network/parse failure - callers must
    catch and show a friendly error, never let this crash the game."""
    req = urllib.request.Request(API_URL, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    match = re.search(r"Build:\s*(\d+)", data.get("body") or "")
    remote_build = int(match.group(1)) if match else 0

    asset = next((a for a in data.get("assets", []) if a["name"].lower().endswith(ASSET_EXT)), None)
    if asset is None:
        raise RuntimeError("release has no matching asset")

    if remote_build <= current_build():
        return None
    return {
        "build": remote_build,
        "url": asset["browser_download_url"],
        "size": asset["size"],
        "name": asset["name"],
    }


def download_update(url, dest_path, progress_cb=None):
    req = urllib.request.Request(url, headers=_HEADERS)
    tmp_path = dest_path + ".part"
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    os.replace(tmp_path, dest_path)
    return dest_path


def can_self_update():
    """PC self-replace only makes sense for an actual frozen .exe, never
    when running from source (sys.executable would be python.exe)."""
    return ON_ANDROID or getattr(sys, "frozen", False)


def apply_update_pc(new_exe_path):
    current_exe = os.path.abspath(sys.executable)
    exe_name = os.path.basename(current_exe)
    exe_dir = os.path.dirname(current_exe)
    bat_path = os.path.join(exe_dir, "_update.bat")

    # tasklist/findstr/ping are fully-qualified to System32 rather than
    # relying on PATH lookup: if a Unix toolchain (Git for Windows, WSL
    # utilities, etc) has put its own same-named commands earlier on the
    # user's PATH, "find" and "timeout" silently resolve to those instead
    # of the Windows ones and misbehave in ways that are very hard to
    # notice from a hidden/no-window process (confirmed while testing this
    # exact script - GNU find/timeout took over and broke both the process
    # check and the wait). "ping -n 2" is the traditional cmd.exe "sleep 1s"
    # idiom, used here instead of timeout.exe specifically because
    # timeout.exe can refuse to run at all without a real console attached
    # to stdin, which a hidden/no-window process may not reliably have.
    script = (
        "@echo off\r\n"
        "setlocal\r\n"
        ":wait\r\n"
        f'%SystemRoot%\\System32\\tasklist.exe /FI "IMAGENAME eq {exe_name}" 2>NUL'
        f' | %SystemRoot%\\System32\\findstr.exe /I "{exe_name}" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "  %SystemRoot%\\System32\\PING.EXE -n 2 127.0.0.1 >NUL\r\n"
        "  goto wait\r\n"
        ")\r\n"
        "%SystemRoot%\\System32\\PING.EXE -n 2 127.0.0.1 >NUL\r\n"
        f'move /y "{new_exe_path}" "{current_exe}" >NUL\r\n'
        f'start "" "{current_exe}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(script)

    # CREATE_NO_WINDOW alone: it still gets a real (just hidden) console, so
    # the batch file's pipe works. Combined with DETACHED_PROCESS (no
    # console at all) that pipe silently breaks instead.
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )


def android_download_dir():
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    return activity.getExternalFilesDir(None).getAbsolutePath()


def apply_update_android(apk_path):
    """Launches the system package installer for apk_path. Returns
    "launched" on success, or "needs_permission" if the user first has to
    grant 'install unknown apps' for this app in Android Settings - the
    Settings screen to do that is opened automatically in that case."""
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    FileProviderCls = autoclass("androidx.core.content.FileProvider")
    JFile = autoclass("java.io.File")
    VersionCls = autoclass("android.os.Build$VERSION")

    activity = PythonActivity.mActivity
    package_name = activity.getPackageName()

    if VersionCls.SDK_INT >= 26:
        if not activity.getPackageManager().canRequestPackageInstalls():
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")
            redirect = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + package_name))
            redirect.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(redirect)
            return "needs_permission"

    authority = package_name + ".fileprovider"
    uri = FileProviderCls.getUriForFile(activity, authority, JFile(apk_path))

    intent = Intent(Intent.ACTION_VIEW)
    intent.setDataAndType(uri, "application/vnd.android.package-archive")
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION)
    activity.startActivity(intent)
    return "launched"
