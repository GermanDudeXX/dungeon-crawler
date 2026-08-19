## Finds the newest build, fetches it, and hands it to Android to install.
##
## The phone has no store behind it: the APK is side-loaded once by hand,
## and after that this is the only way the game learns a new version
## exists. So it does the whole thing - ask GitHub what is newest, compare
## it with what is running, download the file, and open it with the
## system installer.
##
## Handing the file over can fail for reasons this app cannot fix: the
## permission to install unknown apps may be off, or the device may refuse
## the intent. So the browser link stays as a fallback and is offered by
## name when the direct route does not take - a dead end with no way
## forward would be worse than one extra tap.
##
## TLS verification is left exactly as Godot sets it up. This asks a server
## which file to install next: an unverified answer to that question is not
## a small thing, it is someone else choosing the file.
class_name Updater
extends Node

## Only releases tagged like this are ours - the repository also holds
## the pygame build's releases, and offering those here would install a
## different game over this one.
const TAG_PREFIX := "godot-"
const API_URL := "https://api.github.com/repos/GermanDudeXX/dungeon-crawler/releases?per_page=20"

## Emitted once the answer is in. `available` is false when this is
## already the newest build, `note` is the line to show either way.
signal checked(available: bool, version: String, url: String, note: String)

## How the download is going: `done` false while it runs, `note` is the
## line to show. `path` is empty until the file is on disk.
signal fetched(done: bool, path: String, note: String)

var _request: HTTPRequest
var _download: HTTPRequest
var _target := ""


func _ready() -> void:
	_prepare()


## Built on demand rather than only in _ready: a node added to the
## tree does not get its _ready until the next frame, and something
## that asks straight away would otherwise call into nothing.
func _prepare() -> void:
	if _request != null:
		return
	_request = HTTPRequest.new()
	# A couple of megabytes of JSON would already be absurd; the APK is
	# never downloaded here.
	_request.download_chunk_size = 16384
	add_child(_request)
	_request.request_completed.connect(_answered)


## The version this build was exported as, e.g. "0.9.0".
static func running_version() -> String:
	var name: String = str(ProjectSettings.get_setting("application/config/version", ""))
	return name if name != "" else "0.0.0"


func check() -> void:
	_prepare()
	# A node added this frame is not in the tree until the next one,
	# and an HTTPRequest outside the tree refuses to do anything.
	# Asked from a button this never happens; asked from a script that
	# has just built everything, it always does.
	if not _request.is_inside_tree():
		await _request.tree_entered
	var error := _request.request(API_URL, ["Accept: application/vnd.github+json"])
	if error != OK:
		checked.emit(false, "", "", "Keine Verbindung zu GitHub (Fehler %d)." % error)


func _answered(result: int, code: int, _headers: PackedStringArray,
		body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		checked.emit(false, "", "", "GitHub antwortet nicht (Fehler %d)." % code)
		return
	var data: Variant = JSON.parse_string(body.get_string_from_utf8())
	if typeof(data) != TYPE_ARRAY:
		checked.emit(false, "", "", "Antwort von GitHub nicht lesbar.")
		return

	var best_version := ""
	var best_url := ""
	for entry in data:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var tag: String = str(entry.get("tag_name", ""))
		if not tag.begins_with(TAG_PREFIX):
			continue
		var version := version_of(tag)
		if version == "" or not newer(version, best_version):
			continue
		var want := wanted_suffix()
		if want == "":
			continue
		var package := ""
		for asset in entry.get("assets", []):
			var file: String = str(asset.get("name", ""))
			if file.ends_with(want):
				package = str(asset.get("browser_download_url", ""))
				break
		if package == "":
			continue
		best_version = version
		best_url = package

	if best_version == "":
		if wanted_suffix() == "":
			checked.emit(false, "", "", "Für dieses System gibt es hier kein Paket.")
		else:
			checked.emit(false, "", "", "Keine Version auf GitHub gefunden.")
		return
	if not newer(best_version, running_version()):
		checked.emit(false, best_version, best_url,
			"Du hast die neueste Version (%s)." % running_version())
		return
	checked.emit(true, best_version, best_url,
		"Version %s ist da - du hast %s." % [best_version, running_version()])


## "godot-0.9.0-publicdev" -> "0.9.0". Anything that does not look like
## a version at all comes back empty, so it is skipped rather than
## compared as zero.
static func version_of(tag: String) -> String:
	var rest := tag.substr(TAG_PREFIX.length())
	var digits := ""
	for character in rest:
		if character.is_valid_int() or character == ".":
			digits += character
		else:
			break
	return digits if digits.count(".") >= 1 else ""


## Whether `version` is newer than `than`, comparing number by number so
## that 0.10.0 beats 0.9.0 - which a plain string comparison gets wrong.
static func newer(version: String, than: String) -> bool:
	if than == "":
		return version != ""
	var mine := version.split(".")
	var theirs := than.split(".")
	for i in maxi(mine.size(), theirs.size()):
		var a: int = int(mine[i]) if i < mine.size() else 0
		var b: int = int(theirs[i]) if i < theirs.size() else 0
		if a != b:
			return a > b
	return false


## The kind of file this machine can actually install.
##
## A release carries both packages - the APK for the phone and the
## single-file exe for Windows - and the first asset in the list was
## being taken whatever it was. On Windows that meant downloading forty
## megabytes of Android package and then handing it to Windows, which
## has nothing to open it with. It looked like the update was broken; it
## was the wrong file all along.
static func wanted_suffix() -> String:
	match OS.get_name():
		"Android":
			return ".apk"
		"Windows":
			return ".exe"
	return ""


## Where a downloaded build is kept. One fixed name per platform: the
## old one is worthless the moment a newer exists, and two copies of a
## forty-megabyte package on a phone is rude.
static func download_path() -> String:
	return "user://update" + (wanted_suffix() if wanted_suffix() != "" else ".bin")


## Fetches the APK. Progress arrives through `fetched`.
func download(url: String) -> void:
	if _download != null:
		return
	_download = HTTPRequest.new()
	_download.download_file = download_path()
	# Big chunks: this is forty megabytes, not a handful of JSON.
	_download.download_chunk_size = 1 << 20
	# Ten minutes, not two: the Windows build is a hundred and twenty
	# megabytes, and two minutes of that is a megabyte a second - a rate
	# plenty of connections do not manage.
	_download.timeout = 600.0
	# An older build kept its download under a different name. Left alone
	# it would sit there for ever, forty megabytes of a version nobody can
	# install any more.
	for stale in ["user://update.apk", "user://update.exe", "user://update.bin"]:
		if stale != download_path() and FileAccess.file_exists(stale):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(stale))
	add_child(_download)
	_download.request_completed.connect(_downloaded)
	if not _download.is_inside_tree():
		await _download.tree_entered
	var error := _download.request(url)
	if error != OK:
		fetched.emit(true, "", "Download lässt sich nicht starten (Fehler %d)." % error)
		_forget()
		return
	_target = url
	fetched.emit(false, "", "Lade herunter ...")


## How far along the download is, as a line of text, or "" when nothing
## is running. Polled rather than pushed: HTTPRequest has no progress
## signal, only counters.
func progress() -> String:
	if _download == null:
		return ""
	var got: int = _download.get_downloaded_bytes()
	var total: int = _download.get_body_size()
	if total <= 0:
		return "Lade herunter ... %.1f MB" % (got / 1048576.0)
	return "Lade herunter ... %d%% (%.1f von %.1f MB)" % [
		got * 100 / total, got / 1048576.0, total / 1048576.0]


func _downloaded(result: int, code: int, _headers: PackedStringArray,
		_body: PackedByteArray) -> void:
	var ok: bool = result == HTTPRequest.RESULT_SUCCESS and code == 200
	_forget()
	if not ok:
		fetched.emit(true, "", "Download fehlgeschlagen (Fehler %d)." % code)
		return
	# A file that is far too small is not an APK - a redirect page, an
	# error, half a download. Installing it would only produce a confusing
	# refusal from Android.
	if not FileAccess.file_exists(download_path()):
		fetched.emit(true, "", "Die Datei ist nicht angekommen.")
		return
	var file := FileAccess.open(download_path(), FileAccess.READ)
	var size: int = file.get_length() if file != null else 0
	if file != null:
		file.close()
	if size < 1048576:
		fetched.emit(true, "", "Die geladene Datei ist zu klein (%d Bytes)." % size)
		return
	fetched.emit(true, download_path(), "Geladen (%.1f MB). Installieren?" % (size / 1048576.0))


func _forget() -> void:
	if _download != null:
		_download.queue_free()
		_download = null


## Installs what was downloaded. Returns whether the handover was even
## attempted - what happens next is up to the system, which is why the
## caller keeps the browser link ready.
func install(path: String) -> bool:
	if not FileAccess.file_exists(path):
		return false
	var full := ProjectSettings.globalize_path(path)
	if OS.get_name() == "Windows":
		return _swap_windows_build(full)
	var error := OS.shell_open("file://" + full)
	return error == OK


## Replaces the running Windows build with the one just downloaded.
##
## A program cannot overwrite its own executable while it is running,
## so the work is handed to a small batch file: wait for this process
## to end, move the new file over the old one, start it again, and
## delete itself. The caller quits immediately afterwards, which is
## what the batch file is waiting for.
##
## Everything is written with the rights the player already has - the
## game installs itself under the user's own AppData, so replacing it
## needs no administrator and no prompt.
## Batch files want carriage returns. Named, because a literal one in
## the middle of the script below is unreadable.
const BAT_NL := "
"


## The batch file, as text. Kept apart from writing it so it can be read
## and checked without starting anything - a script that waits for a
## process and then moves a file over another one is not something to
## test by running it.
static func swap_script(pid: int, fresh: String, running: String) -> String:
	return ("@echo off" + BAT_NL
		+ ":wait" + BAT_NL
		+ "tasklist /FI \"PID eq %d\" | find \"%d\" >nul" % [pid, pid] + BAT_NL
		+ "if not errorlevel 1 (" + BAT_NL
		+ "  ping -n 2 127.0.0.1 >nul" + BAT_NL
		+ "  goto wait" + BAT_NL
		+ ")" + BAT_NL
		+ "move /y \"%s\" \"%s\" >nul" % [fresh, running] + BAT_NL
		+ "start \"\" \"%s\"" % running + BAT_NL
		+ "del \"%~f0\"" + BAT_NL)


func _swap_windows_build(fresh: String) -> bool:
	var running := OS.get_executable_path().replace("/", "\\")
	var new_file := fresh.replace("/", "\\")
	var script := "user://swap.bat"
	var file := FileAccess.open(script, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(swap_script(OS.get_process_id(), new_file, running))
	file.close()
	var batch := ProjectSettings.globalize_path(script).replace("/", "\\")
	return OS.create_process("cmd.exe", ["/c", batch]) != -1
