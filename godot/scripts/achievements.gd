## Twelve things worth doing, and whether they have been done.
##
## The same list as constants.py ACHIEVEMENTS. They are the only thing in
## the game that survives a death on purpose: a run ends, the record of
## what it managed does not. Kept in their own file for the same reason
## the settings are - a wiped save must not take them with it.
class_name Achievements
extends RefCounted

const PATH := "user://achievements.json"

const ALL := [
	{"id": "first_blood", "name": "Erstes Blut", "how": "Besiege deinen ersten Gegner."},
	{"id": "survivor", "name": "Überlebender", "how": "Erreiche Stufe 5."},
	{"id": "veteran", "name": "Veteran", "how": "Erreiche Stufe 10."},
	{"id": "deep_delver", "name": "Tiefengänger", "how": "Erreiche Ebene 5."},
	{"id": "spelunker", "name": "Höhlenforscher", "how": "Erreiche Ebene 10."},
	{"id": "boss_slayer", "name": "Bosstöter", "how": "Besiege einen Boss."},
	{"id": "rich", "name": "Reich", "how": "Trage 100 Gold auf einmal."},
	{"id": "hoarder", "name": "Hamster", "how": "Sammle insgesamt 500 Gold."},
	{"id": "well_read", "name": "Belesen", "how": "Lies insgesamt 10 Schriftrollen."},
	{"id": "persistent", "name": "Hartnäckig", "how": "Stirb fünfmal."},
	{"id": "centurion", "name": "Zenturio", "how": "Besiege insgesamt 100 Monster."},
	{"id": "untouchable", "name": "Unberührt", "how": "Erreiche Ebene 3 ohne einen Trank."},
]


static func read() -> Dictionary:
	if not FileAccess.file_exists(PATH):
		return {}
	var file := FileAccess.open(PATH, FileAccess.READ)
	if file == null:
		return {}
	var data: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(data) != TYPE_DICTIONARY:
		return {}
	# Only ids that still exist: a renamed achievement should not leave a
	# ghost entry that counts towards the total for ever.
	var out := {}
	for entry in ALL:
		if data.get(entry["id"], false):
			out[entry["id"]] = true
	return out


static func write(earned: Dictionary) -> void:
	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(earned))
	file.close()


static func by_id(id: String) -> Dictionary:
	for entry in ALL:
		if entry["id"] == id:
			return entry
	return ALL[0]
