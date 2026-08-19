## Asks GitHub whether there is a newer build, and hands over the link.
##
## The phone has no store behind it: the APK is side-loaded once by hand,
## and after that this is the only way the game learns that a new version
## exists. So it does the boring half itself - find the newest release,
## compare it with what is running, say plainly which it is - and leaves
## the actual install to Android, by opening the download in the browser.
## Downloading and installing an APK from inside the app needs a special
## permission and a file provider; a link needs neither and cannot go
## wrong in a way that bricks the install.
##
## TLS verification is left exactly as Godot sets it up. This asks a
## server which file to install next: an unverified answer to that
## question is not a small thing, it is someone else choosing the file.
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

var _request: HTTPRequest


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
		var apk := ""
		for asset in entry.get("assets", []):
			var file: String = str(asset.get("name", ""))
			if file.ends_with(".apk"):
				apk = str(asset.get("browser_download_url", ""))
				break
		if apk == "":
			continue
		best_version = version
		best_url = apk

	if best_version == "":
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
