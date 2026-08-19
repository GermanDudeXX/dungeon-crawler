## What has been met, and how often it won.
##
## Kept between runs like the achievements are: a run ends, what it
## taught you does not. It is also the only place the weaknesses are
## written down - a player who has burned three slimes should be able to
## look that up rather than having to remember it.
class_name Bestiary
extends RefCounted

const PATH := "user://bestiary.json"


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
	# Only kinds the game still has: a renamed monster should not leave a
	# ghost entry in the list for ever.
	var out := {}
	for kind in data:
		if not Data.MONSTERS.has(kind):
			continue
		var entry: Variant = data[kind]
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		out[kind] = {
			"seen": int(entry.get("seen", 0)),
			"killed": int(entry.get("killed", 0)),
			"killed_by": int(entry.get("killed_by", 0)),
		}
	return out


static func write(known: Dictionary) -> void:
	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(known))
	file.close()


## Makes sure a kind has a row, and returns it.
static func row(known: Dictionary, kind: String) -> Dictionary:
	if not known.has(kind):
		known[kind] = {"seen": 0, "killed": 0, "killed_by": 0}
	return known[kind]


## The line shown for one kind: what it is, what it fears, what it shrugs
## off, and how the two of you have got on so far.
static func describe(kind: String, entry: Dictionary) -> String:
	var info: Dictionary = Data.MONSTERS[kind]
	var parts: Array[String] = []
	var weak: Array = info.get("weak", [])
	if not weak.is_empty():
		var names: Array[String] = []
		for id in weak:
			names.append(str(Data.ELEMENTS[id]["name"]))
		parts.append("fürchtet %s" % ", ".join(names))
	var resist: Array = info.get("resist", [])
	if not resist.is_empty():
		var names: Array[String] = []
		for id in resist:
			names.append(str(Data.ELEMENTS[id]["name"]))
		parts.append("steckt %s weg" % ", ".join(names))
	if info.get("ranged", false):
		parts.append("schießt")
	if info.get("kites", false):
		parts.append("weicht aus")
	if info.get("splits", false):
		parts.append("teilt sich")
	if info.get("summons", "") != "":
		parts.append("ruft Verstärkung")
	if int(info.get("explodes", 0)) > 0:
		parts.append("explodiert")
	if info.get("poisons", false):
		parts.append("vergiftet")
	if info.get("webs", false):
		parts.append("spinnt Netze")
	if float(info.get("drains", 0.0)) > 0.0:
		parts.append("saugt Leben")
	if float(info.get("enrages", 0.0)) > 0.0:
		parts.append("gerät in Rage")
	if int(info.get("burns_toucher", 0)) > 0:
		parts.append("brennt")
	if info.has("swarms"):
		parts.append("kommt im Rudel")
	var habits := ", ".join(parts) if not parts.is_empty() else "nichts Besonderes"
	return "%s - %s. Gesehen %d, erschlagen %d, tödlich %d." % [
		info["name"], habits,
		int(entry.get("seen", 0)), int(entry.get("killed", 0)),
		int(entry.get("killed_by", 0))]
