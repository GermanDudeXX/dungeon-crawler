## The run on disk, so closing the app does not throw it away.
##
## The whole floor goes in, not just the hero: grid, explored cells,
## monsters, loot, traps, chest and shopkeepers. Saving only the depth
## and regenerating the level on load would be a third of the code and
## would silently undo the floor a player was halfway through - the
## pygame build saves the floor for the same reason.
##
## user:// is the right place on every platform this ships to. On
## Android it lands in the app's private storage, which survives an
## update; the pygame build had to be taught that the hard way, after an
## update wiped its saves.
class_name Save
extends RefCounted

const PATH := "user://save.json"
const VERSION := 1


static func exists() -> bool:
	return FileAccess.file_exists(PATH)


static func wipe() -> void:
	if exists():
		DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))


## Everything needed to put the run back exactly where it was.
static func write(game) -> void:
	var monsters: Array = []
	for m in game.monsters:
		if not m.is_alive():
			continue
		monsters.append({
			"kind": m.kind, "x": m.x, "y": m.y, "hp": m.hp, "max_hp": m.max_hp,
			"power": m.power, "defense": m.defense, "xp": m.xp_reward,
			"name": m.display_name, "sprite": m.sprite, "speed": m.speed,
			"poisons": m.poisons, "flees_below": m.flees_below,
			"awake": m.awake, "boss": m.is_boss, "mimic": m.is_mimic,
		})

	var explored: Array = []
	for cell in game.explored:
		explored.append([cell.x, cell.y])

	var traps: Array = []
	for cell in game.traps:
		traps.append([cell.x, cell.y, game.traps[cell]])

	var items: Array = []
	for item in game.items:
		items.append({"x": item["cell"].x, "y": item["cell"].y,
			"kind": item["kind"], "amount": item.get("amount", 0)})

	var shops: Array = []
	for shop in game.shops:
		shops.append({"x": shop["cell"].x, "y": shop["cell"].y, "kind": shop["kind"]})

	var p = game.player
	var data := {
		"version": VERSION,
		"class": p.hero_class,
		"depth": game.depth,
		"log": game.log_lines,
		"grid": game.grid,
		"stairs": [game.stairs.x, game.stairs.y],
		"stairs_locked": game.stairs_locked,
		"explored": explored,
		"monsters": monsters,
		"items": items,
		"traps": traps,
		"shops": shops,
		"chest": null if game.chest == null else {
			"x": game.chest["cell"].x, "y": game.chest["cell"].y,
			"mimic": game.chest["mimic"], "opened": game.chest["opened"]},
		"player": {
			"x": p.x, "y": p.y, "hp": p.hp, "max_hp": p.max_hp,
			"base_power": p.base_power, "base_defense": p.base_defense,
			"weapon": p.weapon, "armour": p.armour,
			"level": p.level, "xp": p.xp, "xp_to_next": p.xp_to_next,
			"potions": p.potions, "gold": p.gold, "kills": p.kills,
			"facing": p.facing, "poison_turns": p.poison_turns,
		},
	}

	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(data))
	file.close()


## The saved run, or null when there is none or it cannot be read. A
## broken save is not worth a crash on startup: the player gets the
## title screen and a new run, which is what they would have had anyway.
static func read() -> Variant:
	if not exists():
		return null
	var file := FileAccess.open(PATH, FileAccess.READ)
	if file == null:
		return null
	var text := file.get_as_text()
	file.close()
	var data: Variant = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		return null
	if data.get("version", 0) != VERSION:
		return null
	if not data.has("player") or not data.has("grid"):
		return null
	return data
