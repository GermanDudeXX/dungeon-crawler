## What the player has switched on or off, kept between sessions.
##
## Deliberately separate from the save file: settings have to survive a
## death, and the save file does not. The pygame build learned this the
## other way round - it wiped the run and the volume with it.
class_name Settings
extends RefCounted

const PATH := "user://settings.json"

const DEFAULTS := {
	"sound": true,
	"music": true,
}


static func read() -> Dictionary:
	var out := DEFAULTS.duplicate()
	if not FileAccess.file_exists(PATH):
		return out
	var file := FileAccess.open(PATH, FileAccess.READ)
	if file == null:
		return out
	var data: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(data) != TYPE_DICTIONARY:
		return out
	# Only keys we know about, and only in the type we expect: a hand
	# edited file should not be able to put a string where the game
	# reads a bool.
	for key in DEFAULTS:
		if data.has(key) and typeof(data[key]) == typeof(DEFAULTS[key]):
			out[key] = data[key]
	return out


static func write(values: Dictionary) -> void:
	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(values))
	file.close()
