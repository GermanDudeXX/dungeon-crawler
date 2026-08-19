## What the player has done across every run, kept between sessions.
##
## Separate from both the save and the settings: a death wipes the run
## and must not wipe the record of it - the record is the only thing a
## dead run leaves behind, and it is the reason to start another one.
class_name Stats
extends RefCounted

const PATH := "user://stats.json"

const FIELDS := {
	"runs": 0,
	"deaths": 0,
	"deepest": 0,
	"kills": 0,
	"gold": 0,
	"best_level": 0,
}


static func read() -> Dictionary:
	var out := FIELDS.duplicate()
	if not FileAccess.file_exists(PATH):
		return out
	var file := FileAccess.open(PATH, FileAccess.READ)
	if file == null:
		return out
	var data: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(data) != TYPE_DICTIONARY:
		return out
	for key in FIELDS:
		if data.has(key) and typeof(data[key]) == TYPE_FLOAT:
			out[key] = int(data[key])
		elif data.has(key) and typeof(data[key]) == TYPE_INT:
			out[key] = int(data[key])
	return out


static func write(values: Dictionary) -> void:
	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(values))
	file.close()


## Folds a finished run into the record. Totals add up, records only
## move upwards.
static func record_run(depth: int, level: int, kills: int, gold: int, died: bool) -> Dictionary:
	var stats := read()
	stats["runs"] = int(stats["runs"]) + 1
	if died:
		stats["deaths"] = int(stats["deaths"]) + 1
	stats["kills"] = int(stats["kills"]) + kills
	stats["gold"] = int(stats["gold"]) + gold
	stats["deepest"] = maxi(int(stats["deepest"]), depth)
	stats["best_level"] = maxi(int(stats["best_level"]), level)
	write(stats)
	return stats
