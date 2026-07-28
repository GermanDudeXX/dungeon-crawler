import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import sys
import urllib.request

import constants as C

ON_ANDROID = "ANDROID_ARGUMENT" in os.environ


def ca_bundle_candidates():
    """Everywhere the bundled CA roots might have ended up.

    C.CA_BUNDLE_PATH is derived from constants.py's own __file__, which is
    right on Windows and was assumed right on Android. It is not reliably
    so: python-for-android ships the app as .pyc files and starts it with
    its own loader and working directory, so a path built from __file__
    can miss even though the file is in the APK. Rather than guess which
    one is correct, try all of them.
    """
    seen = []
    roots = [C.ASSETS_DIR]
    for env in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"):
        base = os.environ.get(env)
        if base:
            roots.append(os.path.join(base, "assets"))
    roots.append(os.path.join(os.getcwd(), "assets"))
    roots.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    for root in roots:
        path = os.path.join(root, "cacert.pem")
        if path not in seen:
            seen.append(path)
    return seen


def _load_ca_roots(context):
    """Adds our bundled roots to a context. Returns the path used, or None.

    Reads the file and hands OpenSSL the *data* rather than the path.
    That removes the whole question of whether OpenSSL can open a file
    inside Android's app-private storage, and it adds to the platform
    store instead of replacing it - so Windows keeps its own roots and
    Android, which has none OpenSSL can see, gets these.
    """
    for path in ca_bundle_candidates():
        try:
            with open(path, "r", encoding="ascii", errors="ignore") as f:
                pem = f.read()
        except OSError:
            continue
        try:
            context.load_verify_locations(cadata=pem)
        except (ssl.SSLError, ValueError):
            continue
        return path
    return None


def _ssl_context():
    """A verifying SSL context that works on Android too.

    Verification is never turned off: this module downloads an executable
    that is then run, so an unverified transport would be a real hole.

    If no roots can be loaded at all, this raises rather than returning a
    context that is certain to fail. The empty-store failure surfaces as
    OpenSSL's "unable to get local issuer certificate", which says nothing
    about the actual problem - a missing bundle - and sent one debugging
    session looking at the network instead of at the packaging.
    """
    context = ssl.create_default_context()
    used = _load_ca_roots(context)
    if used is None and not context.cert_store_stats()["x509_ca"]:
        raise RuntimeError(
            "no trusted CA roots available - cacert.pem was not found in: "
            + ", ".join(ca_bundle_candidates())
        )
    return context

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
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT,
                                context=_ssl_context()) as resp:
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
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT,
                                context=_ssl_context()) as resp:
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

    # Verify the file actually landed intact before anything downstream
    # treats it as good. Real trigger for adding this: a user's antivirus
    # flagged the built .exe as a (false-positive) trojan and interfered
    # with the self-update download, leaving a truncated file that then
    # got swapped into place and failed to start ("failed to load Python
    # DLL") - this check turns that into a clear error instead of a
    # silently broken install.
    actual_size = os.path.getsize(tmp_path)
    if total and actual_size != total:
        os.remove(tmp_path)
        raise RuntimeError(
            f"download incomplete ({actual_size} of {total} bytes) - "
            "antivirus software may have removed or altered it"
        )

    os.replace(tmp_path, dest_path)
    return dest_path


def staging_dir():
    """Where to put the downloaded build and the swap script.

    Deliberately NOT next to the running .exe. Windows' Controlled Folder
    Access (ransomware protection) blocks writes into Desktop/Documents/
    Downloads by any app it does not recognise, and an unsigned
    PyInstaller build is never recognised - so staging beside the exe
    failed with a permission error that elevating to Administrator does
    not fix. The per-user temp directory is always writable and is not a
    protected location.
    """
    path = os.path.join(tempfile.gettempdir(), "DungeonCrawlerUpdate")
    os.makedirs(path, exist_ok=True)
    return path


def install_dir_error():
    """None if we can replace the running exe, else a reason to show.

    Checked BEFORE downloading ~30MB, so a folder we can never write to
    fails fast and with an explanation instead of after a long download.
    """
    if not getattr(sys, "frozen", False):
        return None
    target = os.path.dirname(os.path.abspath(sys.executable))
    probe = os.path.join(target, ".dc_write_test")
    try:
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return None
    except OSError:
        return target


def can_self_update():
    """PC self-replace only makes sense for an actual frozen .exe, never
    when running from source (sys.executable would be python.exe)."""
    return ON_ANDROID or getattr(sys, "frozen", False)


FAILURE_MARKER = "update_failed.txt"
OLD_EXE_SUFFIX = ".old"


def failure_marker_path():
    return os.path.join(staging_dir(), FAILURE_MARKER)


def take_failure_marker():
    """Reads and removes the marker the swap script leaves behind when it
    could not install the new build. Returns a short reason code or None.

    Without this a failed swap was completely invisible: the script fell
    through to relaunching the old exe, so the game came back looking
    normal and the update button still offered the same update forever.
    """
    path = failure_marker_path()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reason = f.read().strip()
    except OSError:
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return reason or "unknown"


def build_swap_script(current_exe, new_exe_path, fail_log, expected_size=None):
    """The .bat that replaces the running exe. Split out from
    apply_update_pc purely so the swap logic can be exercised by a test
    against dummy files - it is fiddly, it silently broke once already,
    and it is the one piece of this program that can leave a user with no
    working game at all."""
    exe_name = os.path.basename(current_exe)
    old_exe = current_exe + OLD_EXE_SUFFIX

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
    #
    # The file-size check right before the swap is a second line of
    # defense on top of download_update()'s own size check: antivirus
    # software can quarantine/truncate a file *after* Python already
    # verified it and moved on, in the window while this script is still
    # waiting for the old process to exit. Skipping the swap (and just
    # relaunching the still-intact old exe) if the new file looks wrong
    # beats swapping in a broken one that fails to start at all.
    #
    # The swap itself renames the current exe aside and moves the new one
    # into the freed name, instead of overwriting the current exe in
    # place. Reason, and the whole point of this rewrite: a plain
    # "move /y new current" fails outright while anything still holds a
    # handle on the running exe - and something routinely does for a
    # second or two after it exits (antivirus scanning it on close, the
    # shell's icon cache). The old script sent that move's output to NUL
    # and never checked errorlevel, so the failure was silent and it went
    # straight on to relaunching the *old* exe. Renaming works where
    # overwriting does not: Windows lets you rename a file that is open,
    # it only refuses to delete or replace it. Every step is now checked,
    # retried, and rolled back on failure, so the user can never end up
    # without a working exe, and a genuine failure leaves a marker behind
    # instead of pretending the update worked.
    #
    # Nothing here is written with parenthesised if-blocks or delayed
    # expansion on purpose: %VAR% inside a block expands at parse time,
    # and enabling delayed expansion would corrupt any install path
    # containing a "!". Flat labels and gotos avoid both traps.
    size_check = ""
    if expected_size:
        size_check = (
            'set NEWSIZE=0\r\n'
            'for %%A in ("%NEWFILE%") do set NEWSIZE=%%~zA\r\n'
            f'if not "%NEWSIZE%"=="{expected_size}" goto bad_size\r\n'
        )
    script = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "TARGET={current_exe}"\r\n'
        f'set "NEWFILE={new_exe_path}"\r\n'
        f'set "OLDFILE={old_exe}"\r\n'
        f'set "FAILLOG={fail_log}"\r\n'
        "set WAITED=0\r\n"
        "set SWAPS=0\r\n"
        'if exist "%FAILLOG%" del /f /q "%FAILLOG%" >NUL 2>&1\r\n'
        # --- wait for the running game to exit (up to ~2 minutes) ---
        ":wait\r\n"
        f'%SystemRoot%\\System32\\tasklist.exe /FI "IMAGENAME eq {exe_name}" 2>NUL'
        f' | %SystemRoot%\\System32\\findstr.exe /I "{exe_name}" >NUL\r\n'
        "if errorlevel 1 goto gone\r\n"
        "set /a WAITED+=1\r\n"
        "if %WAITED% GEQ 60 goto still_running\r\n"
        "%SystemRoot%\\System32\\PING.EXE -n 3 127.0.0.1 >NUL\r\n"
        "goto wait\r\n"
        # --- grace period, then sanity-check the download ---
        ":gone\r\n"
        "%SystemRoot%\\System32\\PING.EXE -n 4 127.0.0.1 >NUL\r\n"
        'if not exist "%NEWFILE%" goto no_new_file\r\n'
        f"{size_check}"
        # --- rename aside, move in, verify, roll back on any failure ---
        ":swap\r\n"
        'if exist "%OLDFILE%" del /f /q "%OLDFILE%" >NUL 2>&1\r\n'
        'move /y "%TARGET%" "%OLDFILE%" >NUL 2>&1\r\n'
        "if errorlevel 1 goto retry\r\n"
        'move /y "%NEWFILE%" "%TARGET%" >NUL 2>&1\r\n'
        "if errorlevel 1 goto rollback\r\n"
        'if not exist "%TARGET%" goto rollback\r\n'
        "goto relaunch\r\n"
        ":rollback\r\n"
        'move /y "%OLDFILE%" "%TARGET%" >NUL 2>&1\r\n'
        ":retry\r\n"
        "set /a SWAPS+=1\r\n"
        # ~45s of retrying: an antivirus scanning a 40MB exe on close can
        # easily hold it for longer than a handful of seconds.
        "if %SWAPS% GEQ 15 goto swap_failed\r\n"
        "%SystemRoot%\\System32\\PING.EXE -n 3 127.0.0.1 >NUL\r\n"
        "goto swap\r\n"
        # --- failure reasons, all of them still relaunch the old build ---
        ":still_running\r\n"
        'echo still-running> "%FAILLOG%"\r\n'
        "goto relaunch\r\n"
        ":no_new_file\r\n"
        'echo missing-download> "%FAILLOG%"\r\n'
        "goto relaunch\r\n"
        ":bad_size\r\n"
        'echo bad-size> "%FAILLOG%"\r\n'
        "goto relaunch\r\n"
        ":swap_failed\r\n"
        'echo swap-failed> "%FAILLOG%"\r\n'
        "goto relaunch\r\n"
        ":relaunch\r\n"
        'start "" "%TARGET%"\r\n'
        'del "%~f0"\r\n'
    )
    return script


def apply_update_pc(new_exe_path, expected_size=None):
    current_exe = os.path.abspath(sys.executable)
    bat_path = os.path.join(staging_dir(), "_update.bat")
    script = build_swap_script(current_exe, new_exe_path,
                               failure_marker_path(), expected_size)
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


STALE_MEI_AGE_SECONDS = 6 * 3600


def _purge_stale_mei_dirs():
    """Deletes leftover PyInstaller onefile extraction folders in %TEMP%.

    A onefile build unpacks its whole runtime - python313.dll included -
    into %TEMP%\\_MEIxxxxxx on every single launch and removes it again on
    a normal exit. The update path used to hard-exit the process from a
    worker thread, which skips that cleanup entirely, so one ~40MB folder
    was left behind per update attempt (38 of them had accumulated on the
    machine where this was diagnosed). That pile is not just wasted disk:
    the more junk sits in %TEMP%, the likelier an antivirus scan stalls or
    interrupts the *next* extraction, and a half-extracted folder is
    exactly what produces "Failed to load Python DLL ... _MEIxxxxxx\\
    python313.dll".

    Two guards against deleting a folder that is actually in use: our own
    _MEIPASS is skipped outright, and so is anything touched recently -
    another instance of the game could legitimately be running. Cheap
    enough to be worth doing, so it also runs when not frozen.
    """
    temp_root = tempfile.gettempdir()
    ours = os.path.abspath(getattr(sys, "_MEIPASS", "")) if hasattr(sys, "_MEIPASS") else None
    cutoff = time.time() - STALE_MEI_AGE_SECONDS
    removed = 0
    try:
        names = os.listdir(temp_root)
    except OSError:
        return 0
    for name in names:
        if not name.startswith("_MEI"):
            continue
        path = os.path.join(temp_root, name)
        if not os.path.isdir(path):
            continue
        if ours and os.path.abspath(path) == ours:
            continue
        try:
            if os.path.getmtime(path) > cutoff:
                continue
        except OSError:
            continue
        # Rename first: if anything inside is still locked this fails as a
        # whole and we leave the folder completely alone, rather than
        # rmtree deleting the unlocked half of a live instance's runtime.
        tomb = path + ".stale"
        try:
            if os.path.exists(tomb):
                shutil.rmtree(tomb, ignore_errors=True)
            os.rename(path, tomb)
        except OSError:
            continue
        shutil.rmtree(tomb, ignore_errors=True)
        removed += 1
    return removed


def _purge_old_exe():
    """Removes the previous build that apply_update_pc renamed aside.

    It cannot be deleted by the swap script itself - at that moment it is
    about to become, or has just been, a running process - so the newly
    started build clears it on the way up.
    """
    if not getattr(sys, "frozen", False):
        return
    old = os.path.abspath(sys.executable) + OLD_EXE_SUFFIX
    try:
        if os.path.exists(old):
            os.remove(old)
    except OSError:
        pass


def cleanup_previous_update():
    """Fire-and-forget startup housekeeping, off the main thread.

    Deleting dozens of 40MB folders can take a second or two and must
    never hold up the title screen, and every step already swallows its
    own errors, so a daemon thread is enough.
    """
    def worker():
        try:
            _purge_old_exe()
            _purge_stale_mei_dirs()
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def android_download_dir():
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    return activity.getExternalFilesDir(None).getAbsolutePath()


def _publish_to_downloads(local_path, display_name):
    """Copies a local file into the public Downloads collection via
    MediaStore (Android 10+) and returns its content:// Uri. Deliberately
    NOT using a custom FileProvider: an earlier attempt needed a <provider>
    manifest entry, but p4a's AndroidManifest template only exposes an
    insertion point *inside* the <application ...> opening tag's attribute
    list (confirmed by reading the actual template source) - a child
    element dropped there is not well-formed XML and broke Gradle's
    manifest merger. MediaStore needs no manifest changes and no storage
    permission at all: apps can always contribute their own files to
    shared collections like Downloads under scoped storage."""
    from jnius import autoclass

    VersionCls = autoclass("android.os.Build$VERSION")
    if VersionCls.SDK_INT < 29:
        raise RuntimeError("in-app update needs Android 10 or newer")

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ContentValues = autoclass("android.content.ContentValues")
    MediaStoreDownloads = autoclass("android.provider.MediaStore$Downloads")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()

    values = ContentValues()
    values.put("_display_name", display_name)
    values.put("mime_type", "application/vnd.android.package-archive")

    item_uri = resolver.insert(MediaStoreDownloads.EXTERNAL_CONTENT_URI, values)
    if item_uri is None:
        raise RuntimeError("could not create a Downloads entry")

    out_stream = resolver.openOutputStream(item_uri)
    try:
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                out_stream.write(chunk)
    finally:
        out_stream.close()

    return item_uri


def apply_update_android(apk_path):
    """Launches the system package installer for apk_path. Returns
    "launched" on success, or "needs_permission" if the user first has to
    grant 'install unknown apps' for this app in Android Settings - the
    Settings screen to do that is opened automatically in that case."""
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
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

    uri = _publish_to_downloads(apk_path, os.path.basename(apk_path))

    intent = Intent(Intent.ACTION_VIEW)
    intent.setDataAndType(uri, "application/vnd.android.package-archive")
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION)
    activity.startActivity(intent)
    return "launched"
