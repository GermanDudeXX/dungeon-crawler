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
## One floor as plain data.
##
## Used twice: for the floor the hero is standing on, and for every floor
## they have already been on and could walk back into. One function, so
## the two cannot drift - a field added for the save and forgotten for
## the memory would show up as a floor that changes when you return to
## it, which is the bug this whole thing exists to prevent.
static func floor_data(game) -> Dictionary:
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
			"keeper": m.is_keeper,
			"burn": m.burn_turns, "slow": m.slow_turns, "stun": m.stun_turns,
			"regen": m.regen, "elite": m.is_elite, "generation": m.generation,
			"summoned": m.summoned, "enraged": m.enraged, "afraid": m.afraid,
			"weaken": m.weaken_turns, "venom": m.venom_turns, "bleed": m.bleed_turns,
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
			"kind": item["kind"], "amount": item.get("amount", 0),
			"potion": item.get("potion", ""), "scroll": item.get("scroll", "")})

	var doors: Array = []
	for cell in game.doors:
		doors.append([cell.x, cell.y, game.doors[cell]])

	var webs: Array = []
	for cell in game.webs:
		webs.append([cell.x, cell.y])

	var hazards: Array = []
	for cell in game.hazards:
		hazards.append([cell.x, cell.y, game.hazards[cell]])

	var decor: Array = []
	for cell in game.decor:
		decor.append([cell.x, cell.y, game.decor[cell]])

	var shops: Array = []
	for shop in game.shops:
		shops.append({"x": shop["cell"].x, "y": shop["cell"].y, "kind": shop["kind"],
			"stock": shop.get("stock", []), "scroll": shop.get("scroll", "")})

	# The rooms are part of the floor too: everything that places
	# something later - a blink, a scattered purse - picks from them, and
	# a restored floor with the previous floor's rooms reaches past the
	# end of the list.
	var rooms: Array = []
	for room in game.rooms:
		rooms.append([room.x1, room.y1, room.x2, room.y2])

	return {
		"depth": game.depth,
		"rooms": rooms,
		# Copied, not referenced: a remembered floor must not share its map
		# with the live one. It did, and entering the next floor cleared the
		# array in place - so the floor you walked back into had no map at
		# all.
		"grid": game.grid.duplicate(true),
		"stairs": [game.stairs.x, game.stairs.y],
		"up_stairs": [game.up_stairs.x, game.up_stairs.y],
		"stairs_locked": game.stairs_locked,
		"shrine": null if game.shrine == null else [game.shrine.x, game.shrine.y],
		"captive": null if game.captive == null else [game.captive.x, game.captive.y],
		"decor": decor,
		"hazards": hazards,
		"webs": webs,
		"doors": doors,
		"theme": game.theme.duplicate(),
		"quest": game.quest.duplicate(),
		"drank_here": game.drank_here,
		"hurt_here": game.hurt_here,
		"explored": explored,
		"monsters": monsters,
		"items": items,
		"traps": traps,
		"shops": shops,
		"chest": null if game.chest == null else {
			"x": game.chest["cell"].x, "y": game.chest["cell"].y,
			"mimic": game.chest["mimic"], "opened": game.chest["opened"],
			# A mimic's chest is gone once it has got up; without this it
			# would be lying there again after a reload.
			"gone": game.chest.get("gone", false),
			"guarded": game.chest.get("guarded", false)},
	}


## Everything needed to put the run back where it was.
static func write(game) -> void:
	var p = game.player
	var data := {
		"version": VERSION,
		"class": p.hero_class,
		"log": game.log_lines,
		# Every floor already visited, so climbing a staircase after a break
		# leads back to the floor that was left rather than to a fresh roll.
		"floors": game.floors,
		"player": {
			"x": p.x, "y": p.y, "hp": p.hp, "max_hp": p.max_hp,
			"base_power": p.base_power, "base_defense": p.base_defense,
			"weapon": p.weapon, "armour": p.armour,
			"weapon_rarity": p.weapon_rarity, "armour_rarity": p.armour_rarity,
			"weapon_extra": p.weapon_extra, "armour_extra": p.armour_extra,
			"weapon_element": p.weapon_element,
			"level": p.level, "xp": p.xp, "xp_to_next": p.xp_to_next,
			"potions": p.potions, "gold": p.gold, "kills": p.kills,
			"facing": p.facing, "poison_turns": p.poison_turns,
			"webbed": p.webbed, "shot_cooldown": p.shot_cooldown,
			"bonus_crit": p.bonus_crit, "damage_reduction": p.damage_reduction,
			"gold_mult": p.gold_mult, "xp_mult": p.xp_mult,
			"potion_mult": p.potion_mult, "scholar": p.scholar,
			"regen_interval": p.regen_interval,
			"regen_power": p.regen_power,
			"regen_counter": p.regen_counter, "pending_perks": p.pending_perks,
			"potion_counts": p.potion_counts, "selected_potion": p.selected_potion,
			"buffs": p.buffs, "shield": p.shield, "bleed_turns": p.bleed_turns,
			"scrolls": p.scrolls,
		},
	}
	# The floor being stood on goes in at the top level, where it always
	# was, so an older save still reads.
	data.merge(floor_data(game))
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
