## Puts the Windows build somewhere it belongs.
##
## The export is a single 120 MB executable, which is the right shape for
## a download and the wrong shape for a game: it ends up in the Downloads
## folder, next to seven other files, with no shortcut and no name in the
## start menu, and the next version arrives beside it as a second copy.
## So on the first run the game offers to move in properly - copy itself
## into %LOCALAPPDATA%\Programs\Dungeon Crawler, put a shortcut on the
## desktop and in the start menu, and start again from there.
##
## Deliberately not Program Files: writing there needs administrator
## rights, and asking a player to approve a UAC prompt for a dungeon
## crawler is asking too much. Everything here works with the rights the
## player already has.
##
## The save file is unaffected either way - it lives in the user data
## folder, not next to the executable - so installing never costs a run.
class_name Setup
extends RefCounted

const FOLDER := "Dungeon Crawler"
const EXE_NAME := "DungeonCrawler.exe"
const SHORTCUT := "Dungeon Crawler.lnk"


static func on_windows() -> bool:
	return OS.get_name() == "Windows"


## Where the game belongs. Empty when the environment has no idea, which
## is the one case where the whole offer is skipped rather than guessed.
static func install_dir() -> String:
	var base := OS.get_environment("LOCALAPPDATA")
	if base == "":
		base = OS.get_environment("APPDATA")
	if base == "":
		return ""
	return base.replace("\\", "/").rstrip("/") + "/Programs/" + FOLDER


static func installed_exe() -> String:
	var dir := install_dir()
	return "" if dir == "" else dir + "/" + EXE_NAME


## Whether the copy that is running is the installed one. Compared
## without case, because Windows paths are not case sensitive and the
## same folder arrives spelled differently depending on who asks.
static func already_installed() -> bool:
	var target := installed_exe()
	if target == "":
		return false
	var running := OS.get_executable_path().replace("\\", "/")
	return running.to_lower() == target.to_lower()


## Whether it makes sense to offer at all: only a real exported build on
## Windows that is not already in place. Running from the editor would
## otherwise offer to install the editor's own binary.
static func worth_offering() -> bool:
	return on_windows() and not OS.has_feature("editor") and not already_installed() \
		and install_dir() != ""


## Copies the running executable into place and puts two shortcuts next
## to it. Returns what happened, in a line the player can read.
static func install() -> Dictionary:
	var dir := install_dir()
	if dir == "":
		return {"ok": false, "note": "Windows verrät keinen Programmordner.", "exe": ""}
	var error := DirAccess.make_dir_recursive_absolute(dir)
	if error != OK and not DirAccess.dir_exists_absolute(dir):
		return {"ok": false, "note": "Ordner lässt sich nicht anlegen (Fehler %d)." % error,
			"exe": ""}
	var target := dir + "/" + EXE_NAME
	var running := OS.get_executable_path()
	# Copying a running executable is allowed on Windows: the file is open
	# for reading, not locked against it.
	error = DirAccess.copy_absolute(running, target)
	if error != OK:
		return {"ok": false, "note": "Kopieren fehlgeschlagen (Fehler %d)." % error, "exe": ""}
	_make_shortcuts(target)
	return {"ok": true, "exe": target,
		"note": "Installiert nach %s" % dir.replace("/", "\\")}


## A shortcut on the desktop and one in the start menu.
##
## Both folders are asked for by name rather than built from the user
## profile: a desktop redirected into OneDrive is completely normal, and
## a shortcut written to the folder that is no longer the desktop helps
## nobody. Failure here is not fatal - the game is installed either way,
## it is just harder to find.
static func _make_shortcuts(exe: String) -> void:
	var windows_path := exe.replace("/", "\\")
	var script := """
$exe = '%s'
$shell = New-Object -ComObject WScript.Shell
$spots = @([Environment]::GetFolderPath('Desktop'),
	(Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))
foreach ($spot in $spots) {
	if ($spot -and (Test-Path $spot)) {
		$link = $shell.CreateShortcut((Join-Path $spot '%s'))
		$link.TargetPath = $exe
		$link.WorkingDirectory = (Split-Path $exe)
		$link.Description = 'Dungeon Crawler'
		$link.Save()
	}
}
""" % [windows_path, SHORTCUT]
	OS.create_process("powershell.exe", ["-NoProfile", "-NonInteractive",
		"-WindowStyle", "Hidden", "-Command", script])


## Starts the installed copy. The caller quits straight after, so for a
## moment both exist - which is fine, they are the same program.
static func launch(exe: String) -> bool:
	return OS.create_process(exe, []) != -1
