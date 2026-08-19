## The game: a dungeon, monsters that fight back, loot, levels, and a way
## down. Ported from the pygame build, so the numbers and the rules are
## the same ones - what changed is who does the drawing.
##
## The map is a TileMapLayer, handed to the GPU once and redrawn every
## frame for nothing. The pygame build had to keep a painted copy of it
## in memory, patch it cell by cell as the light moved, and copy the
## result to the display at the 8-9 million pixels a second that phone
## manages. That difference is the whole reason this port exists: the
## same floor, walked the same way, went from 50-60ms a frame to 17.8.
extends Node2D

const MAP_W := 40
const MAP_H := 25
const TILE := 16
const FLOOR_VARIANTS := 8

# Art comes in whatever size it was drawn at - the monster paintings
# are around 220 pixels tall, a tile is 16. The pygame build scales
# every sprite to a multiple of the tile before it ever blits one, and
# these are its numbers: a monster stands one and a half tiles tall, a
# boss nearly three, a shopkeeper a little over one and a half,
# and the hero 1.8 - a hair taller than what he fights.
const HERO_TILES := 1.8
const MONSTER_TILES := 1.5
const BOSS_SCALE := 1.8
const PROP_TILES := 1.6
const ITEM_TILES := 1.1

# Scenery only, no rules: what a floor is dressed with.
const DECOR := ["crate", "skull", "wall_banner_red", "wall_banner_blue",
	"wall_banner_green", "wall_banner_yellow", "column"]

const TILE_DIR := "res://assets/tiles/"
const CLASS_DIR := "res://assets/classes/"
const HERO_SPRITE := "knight_m_idle_anim_f0"

var grid: Array = []
var rooms: Array = []
var explored := {}
var lit := {}
var player: Entities.Player
var monsters: Array = []
var items: Array = []
var stairs := Vector2i.ZERO
var depth := 1
var tier := {}
var log_lines: Array[String] = []
var traps := {}                 ## cell -> trap id
var chest = null                ## {cell, mimic, opened}
var shops: Array = []           ## {cell, kind}
var stairs_locked := false
var decor := {}                  ## cell -> a sprite that is only scenery
var shrine = null                ## the cell holding this floor's shrine, or null
var shop_open = null            ## the shop the hero is standing in
var dead := false
var hero_class := Data.DEFAULT_CLASS
var difficulty := Data.DEFAULT_DIFFICULTY
var choosing := true            ## the title screen is up, nothing moves
var rng := RandomNumberGenerator.new()

var _floor_layer: TileMapLayer
var _dim_layer: TileMapLayer
var _tile_ids := {}
var _sprites := {}
var _actor_nodes := {}
var _item_nodes := {}
var _hero_node: Sprite2D
var _camera: Camera2D
var _hud: Control
var audio: Audio
var settings := Settings.DEFAULTS.duplicate()
var _play_ui: Control            ## stats, log and the pad - hidden on the title
var _shop_panel: PanelContainer
var _shop_title: Label
var _shop_buttons: Array = []
var _title_panel: PanelContainer
var _continue_button: Button
var _dead_panel: PanelContainer
var _dead_text: Label
var _sound_button: Button
var _difficulty_button: Button
var _drink_button: Button
var _scroll_buttons: Array = []
var _perk_panel: PanelContainer
var _perk_buttons: Array = []
var perk_choices: Array = []      ## the three on offer right now
var _music_button: Button
var _held := Vector2i.ZERO
var _haste_flip := false
var _step_cooldown := 0.0


func _ready() -> void:
	rng.randomize()
	settings = Settings.read()
	audio = Audio.new()
	add_child(audio)
	audio.enabled = settings["sound"]
	audio.music_enabled = settings["music"]
	difficulty = str(settings.get("difficulty", Data.DEFAULT_DIFFICULTY))
	_build_world()
	_build_hud()
	# A run starts behind the title screen, not in front of it: the
	# class is picked before the first floor exists, so the starting
	# kit is right from the first turn.
	new_run()
	show_title()


# --- scene ----------------------------------------------------------------

func _build_world() -> void:
	var tileset := _build_tileset()
	_dim_layer = TileMapLayer.new()
	_dim_layer.tile_set = tileset
	add_child(_dim_layer)

	_floor_layer = TileMapLayer.new()
	_floor_layer.tile_set = tileset
	add_child(_floor_layer)

	_hero_node = Sprite2D.new()
	_hero_node.texture = load(CLASS_DIR + HERO_SPRITE + ".png")
	_hero_node.centered = false
	_hero_node.z_index = 2
	add_child(_hero_node)

	_camera = Camera2D.new()
	_camera.zoom = Vector2(2.2, 2.2)
	add_child(_camera)


func _build_tileset() -> TileSet:
	var tileset := TileSet.new()
	tileset.tile_size = Vector2i(TILE, TILE)
	for name in _tile_names():
		var path := TILE_DIR + name + ".png"
		if not ResourceLoader.exists(path):
			continue
		var texture: Texture2D = load(path)
		# Single-cell art only; the tall decor is a sprite, not a tile.
		if texture.get_height() != TILE:
			continue
		var source := TileSetAtlasSource.new()
		source.texture = texture
		source.texture_region_size = Vector2i(TILE, TILE)
		source.create_tile(Vector2i.ZERO)
		_tile_ids[name] = tileset.add_source(source)
	return tileset


func _tile_names() -> PackedStringArray:
	var names := PackedStringArray()
	for i in range(1, FLOOR_VARIANTS + 1):
		names.append("floor_%d" % i)
	names.append_array(["wall_mid", "wall_left", "wall_right", "wall_top_mid",
		"floor_stairs"])
	return names


func _sprite_for(name: String) -> Texture2D:
	if not _sprites.has(name):
		for dir in [CLASS_DIR, "res://assets/monsters/", "res://assets/items/", TILE_DIR]:
			var path: String = dir + name + ".png"
			if ResourceLoader.exists(path):
				_sprites[name] = load(path)
				break
		if not _sprites.has(name):
			_sprites[name] = load(CLASS_DIR + HERO_SPRITE + ".png")
	return _sprites[name]


# --- a run ----------------------------------------------------------------

func new_run() -> void:
	player = Entities.Player.new(hero_class, difficulty)
	depth = 1
	dead = false
	log_lines.clear()
	say("Du steigst in den Dungeon hinab.")
	new_level()


## Puts a saved run back on its floor. Everything is rebuilt from the
## file rather than regenerated, so the player carries on standing where
## they stood, on the map they had uncovered.
func load_run() -> bool:
	var data: Variant = Save.read()
	if data == null:
		return false
	var save: Dictionary = data

	hero_class = save["class"]
	player = Entities.Player.new(hero_class, difficulty)
	var p: Dictionary = save["player"]
	player.x = int(p["x"])
	player.y = int(p["y"])
	player.hp = int(p["hp"])
	player.max_hp = int(p["max_hp"])
	player.base_power = int(p["base_power"])
	player.base_defense = int(p["base_defense"])
	player.weapon = int(p["weapon"])
	player.armour = int(p["armour"])
	player.weapon_rarity = str(p.get("weapon_rarity", "common"))
	player.armour_rarity = str(p.get("armour_rarity", "common"))
	player.weapon_extra = int(p.get("weapon_extra", 0))
	player.weapon_element = str(p.get("weapon_element", ""))
	player.armour_extra = int(p.get("armour_extra", 0))
	player.level = int(p["level"])
	player.xp = int(p["xp"])
	player.xp_to_next = int(p["xp_to_next"])
	player.potions = int(p["potions"])
	player.gold = int(p["gold"])
	player.kills = int(p["kills"])
	player.facing = int(p["facing"])
	player.poison_turns = int(p["poison_turns"])
	player.bonus_crit = float(p.get("bonus_crit", 0.0))
	player.damage_reduction = float(p.get("damage_reduction", 0.0))
	player.gold_mult = float(p.get("gold_mult", 1.0))
	player.regen_interval = int(p.get("regen_interval", 0))
	player.regen_counter = int(p.get("regen_counter", 0))
	player.pending_perks = int(p.get("pending_perks", 0))
	player.selected_potion = str(p.get("selected_potion", Data.DEFAULT_POTION))
	player.shield = int(p.get("shield", 0))
	player.bleed_turns = int(p.get("bleed_turns", 0))
	player.potion_counts.clear()
	for id in p.get("potion_counts", {}):
		player.potion_counts[str(id)] = int(p["potion_counts"][id])
	player.potions = 0
	for id in player.potion_counts:
		player.potions += int(player.potion_counts[id])
	player.scrolls.clear()
	for id in p.get("scrolls", {}):
		player.scrolls[str(id)] = int(p["scrolls"][id])
	player.buffs.clear()
	for id in p.get("buffs", {}):
		if Data.BUFFS.has(id):
			player.buffs[str(id)] = int(p["buffs"][id])
	player.snap()

	depth = int(save["depth"])
	tier = Data.tier_for(depth)
	audio.play_music(tier.get("music", ""))
	dead = false
	log_lines.clear()
	for line in save["log"]:
		log_lines.append(str(line))

	# JSON has no integers, only floats, and no Vector2i at all - every
	# number and every cell has to be put back into the type the game
	# expects, or the first comparison against a live value fails.
	grid.clear()
	for row in save["grid"]:
		var line: Array = []
		for value in row:
			line.append(int(value))
		grid.append(line)
	stairs = Vector2i(int(save["stairs"][0]), int(save["stairs"][1]))
	stairs_locked = bool(save["stairs_locked"])
	decor.clear()
	for entry in save.get("decor", []):
		decor[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	shrine = null
	if save.get("shrine", null) != null:
		shrine = Vector2i(int(save["shrine"][0]), int(save["shrine"][1]))

	_clear_level_nodes()
	explored.clear()
	for cell in save["explored"]:
		explored[Vector2i(int(cell[0]), int(cell[1]))] = true
	traps.clear()
	for entry in save["traps"]:
		traps[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	items.clear()
	for entry in save["items"]:
		items.append({"cell": Vector2i(int(entry["x"]), int(entry["y"])),
			"kind": str(entry["kind"]), "amount": int(entry["amount"]),
			"potion": str(entry.get("potion", "")),
			"scroll": str(entry.get("scroll", ""))})
	shops.clear()
	for entry in save["shops"]:
		var stock: Array = []
		for id in entry.get("stock", []):
			stock.append(str(id))
		shops.append({"cell": Vector2i(int(entry["x"]), int(entry["y"])),
			"kind": str(entry["kind"]), "stock": stock})
	chest = null
	if save["chest"] != null:
		var c: Dictionary = save["chest"]
		chest = {"cell": Vector2i(int(c["x"]), int(c["y"])),
			"mimic": bool(c["mimic"]), "opened": bool(c["opened"])}

	monsters.clear()
	for entry in save["monsters"]:
		var monster := Entities.Monster.new(str(entry["kind"]), 1.0)
		monster.x = int(entry["x"])
		monster.y = int(entry["y"])
		monster.max_hp = int(entry["max_hp"])
		monster.hp = int(entry["hp"])
		monster.power = int(entry["power"])
		monster.defense = int(entry["defense"])
		monster.xp_reward = int(entry["xp"])
		monster.display_name = str(entry["name"])
		monster.sprite = str(entry["sprite"])
		monster.speed = int(entry["speed"])
		monster.poisons = bool(entry["poisons"])
		monster.flees_below = float(entry["flees_below"])
		monster.awake = bool(entry["awake"])
		monster.is_boss = bool(entry["boss"])
		monster.is_mimic = bool(entry["mimic"])
		monster.burn_turns = int(entry.get("burn", 0))
		monster.slow_turns = int(entry.get("slow", 0))
		monster.stun_turns = int(entry.get("stun", 0))
		monster.regen = int(entry.get("regen", 0))
		monster.weaken_turns = int(entry.get("weaken", 0))
		monster.venom_turns = int(entry.get("venom", 0))
		monster.bleed_turns = int(entry.get("bleed", 0))
		monster.is_elite = bool(entry.get("elite", false))
		monster.snap()
		monsters.append(monster)

	_hero_node.texture = load(CLASS_DIR + Data.class_by_id(hero_class)["sprite"] + ".png")
	choosing = false
	close_shop()
	if _dead_panel != null:
		_dead_panel.visible = false
	if _play_ui != null:
		_play_ui.visible = true
	if _title_panel != null:
		_title_panel.visible = false
	recompute_fov()
	paint()
	return true


## Called on the way out of a floor, out of the app, and whenever
## Android puts us in the background - which on a phone is the only
## shutdown that actually happens. A dead hero has nothing to save, and
## leaving the file there would offer to continue a finished run.
func save_run() -> void:
	if choosing or player == null:
		return
	if dead:
		Save.wipe()
		return
	Save.write(self)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST \
			or what == NOTIFICATION_APPLICATION_PAUSED \
			or what == NOTIFICATION_WM_GO_BACK_REQUEST:
		save_run()


func new_level() -> void:
	tier = Data.tier_for(depth)
	audio.play_music(tier.get("music", ""))
	var made := Dungeon.generate(MAP_W, MAP_H, rng)
	grid = made["grid"]
	rooms = made["rooms"]
	explored.clear()
	monsters.clear()
	items.clear()
	traps.clear()
	shops.clear()
	chest = null
	_clear_level_nodes()

	_hero_node.texture = load(CLASS_DIR + Data.class_by_id(player.hero_class)["sprite"] + ".png")
	var start: Vector2i = rooms[0].center() if not rooms.is_empty() else Vector2i(1, 1)
	player.x = start.x
	player.y = start.y
	player.snap()
	stairs = rooms[-1].center() if not rooms.is_empty() else Vector2i(2, 2)
	_populate()
	recompute_fov()
	paint()
	# The floor is the natural checkpoint: it is the one moment where
	# the whole level is settled and nothing is half-resolved.
	save_run()


## Sprites belong to the floor they were made for; a new floor gets
## new ones. Left behind, they hang in mid-air over the next map.
func _clear_level_nodes() -> void:
	for node in _actor_nodes.values():
		node.queue_free()
	_actor_nodes.clear()
	for node in _item_nodes.values():
		node.queue_free()
	_item_nodes.clear()


func _populate() -> void:
	var spawn_rooms: Array = rooms.slice(1) if rooms.size() > 1 else rooms
	for _i in Data.monster_count(depth):
		var cell: Variant = _free_cell(spawn_rooms)
		if cell == null:
			continue
		var monster := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"], difficulty)
		monster.x = cell.x
		monster.y = cell.y
		if depth >= 2 and rng.randf() < Data.ELITE_CHANCE:
			monster.make_elite(Data.ELITES[rng.randi() % Data.ELITES.size()])
		monster.snap()
		monsters.append(monster)

	# The boss holds the key, so it is placed first and far from the
	# hero - a floor you have to finish rather than cross.
	stairs_locked = false
	if Data.has_boss(depth):
		var boss_cell = _free_cell([rooms[-1]] if not rooms.is_empty() else spawn_rooms)
		if boss_cell != null:
			var boss := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"], difficulty)
			boss.x = boss_cell.x
			boss.y = boss_cell.y
			boss.max_hp = int(boss.max_hp * Data.BOSS_HP_MULT)
			boss.hp = boss.max_hp
			boss.power = int(boss.power * Data.BOSS_POWER_MULT)
			boss.xp_reward *= 3
			boss.is_boss = true
			boss.awake = true
			boss.display_name = "%s-König" % boss.display_name
			boss.snap()
			monsters.append(boss)
			stairs_locked = true

	# A mini-boss on the floors between real bosses, so the gap has a
	# landmark in it. It does not lock the stairs - it is a fight you
	# may walk around, not one you have to win.
	if Data.has_mini_boss(depth):
		var mini_cell = _free_cell(spawn_rooms)
		if mini_cell != null:
			var mini := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"], difficulty)
			mini.x = mini_cell.x
			mini.y = mini_cell.y
			mini.max_hp = int(mini.max_hp * Data.MINI_BOSS_MULT)
			mini.hp = mini.max_hp
			mini.power = int(mini.power * Data.MINI_BOSS_MULT)
			mini.xp_reward = int(mini.xp_reward * Data.MINI_BOSS_XP_MULT)
			mini.display_name = "Großer %s" % mini.display_name
			mini.snap()
			monsters.append(mini)

	# A vault: three to five elites standing together on a pile of
	# gold. The gold is the point - it is the one place on the floor
	# where you can see the reward and have to decide whether you
	# survive collecting it.
	if depth >= Data.VAULT_MIN_LEVEL and rng.randf() < Data.VAULT_CHANCE:
		var guards: int = rng.randi_range(Data.VAULT_GUARDS[0], Data.VAULT_GUARDS[1])
		var room = rooms[rng.randi() % rooms.size()] if not rooms.is_empty() else null
		for _g in guards:
			var guard_cell = _free_cell([room] if room != null else spawn_rooms)
			if guard_cell == null:
				continue
			var guard := Entities.Monster.new(Data.pick_kind(depth, rng),
				tier["mult"] * Data.VAULT_GUARD_MULT, difficulty)
			guard.x = guard_cell.x
			guard.y = guard_cell.y
			guard.make_elite(Data.ELITES[rng.randi() % Data.ELITES.size()])
			guard.snap()
			monsters.append(guard)
			var hoard = _free_cell([room] if room != null else spawn_rooms)
			if hoard != null:
				items.append({"cell": hoard, "kind": "gold",
					"amount": rng.randi_range(30, 60 + depth * 5)})

	# A chest, which is sometimes not a chest at all.
	if depth >= 2 and rng.randf() < 0.55:
		var chest_cell = _free_cell(spawn_rooms)
		if chest_cell != null:
			chest = {"cell": chest_cell, "mimic": depth >= 3 and rng.randf() < 0.3,
				"opened": false}

	# A shrine, at most one, stepped on like a trap - but this one can
	# be worth stepping on.
	shrine = null
	if depth >= 2 and rng.randf() < Data.SHRINE_CHANCE:
		shrine = _free_cell(spawn_rooms)

	# Traps, hidden until stepped on.
	var trap_kinds: Array = Data.TRAPS.keys()
	for _i in range(depth / 2 + 1):
		var trap_cell = _free_cell(spawn_rooms)
		if trap_cell != null:
			traps[trap_cell] = trap_kinds[rng.randi() % trap_kinds.size()]

	# A merchant, and deeper down a smith. Never anywhere that would
	# wall the level off: walking into one opens their shop instead of
	# moving, so their tile is a wall that never opens. The Python
	# build shipped without this check and 5.7% of the floors that had
	# a shopkeeper could not be finished at all.
	if depth >= 2 and rng.randf() < 0.4:
		var spot = _shopkeeper_spot(spawn_rooms)
		if spot != null:
			# Three flasks, rolled per floor and never cursed: a merchant
			# who sold you a Murky Flask would be a merchant nobody visits
			# twice. What he stocks is what the depth has unlocked.
			var stock: Array = []
			for _s in 3:
				var id: String = Data.pick_potion(depth, rng, false)
				if not stock.has(id):
					stock.append(id)
			shops.append({"cell": spot, "kind": "merchant", "stock": stock})
	if depth >= 4 and rng.randf() < 0.3:
		var spot = _shopkeeper_spot(spawn_rooms)
		if spot != null:
			shops.append({"cell": spot, "kind": "smith", "stock": []})

	# Loot goes last, and only where the hero can reach: the
	# shopkeepers are standing by now, and each of them is a tile that
	# never opens.
	var blocked := {}
	for shop in shops:
		blocked[shop["cell"]] = true
	var open_cells := reachable_from(Vector2i(player.x, player.y), blocked)
	for _i in range(2 + depth / 3):
		var cell: Variant = _free_cell(spawn_rooms, open_cells)
		if cell == null:
			continue
		var roll := rng.randf()
		var kind := "gold"
		if roll < 0.32:
			kind = "potion"
		elif roll < 0.40:
			kind = "scroll"
		elif roll < 0.50:
			kind = "weapon"
		elif roll < 0.62:
			kind = "armour"
		var loot := {"cell": cell, "kind": kind,
			"amount": rng.randi_range(5, 15 + depth * 3)}
		if kind == "potion":
			loot["potion"] = Data.pick_potion(depth, rng)
		if kind == "scroll":
			loot["scroll"] = Data.SCROLLS[rng.randi() % Data.SCROLLS.size()]["id"]
		items.append(loot)


## A free cell in one of these rooms. `within`, when given, is the set
## of cells the hero can actually walk to - loot dropped outside it is
## loot nobody ever picks up, which is how a scroll ended up sealed
## behind a shopkeeper.
func _free_cell(where: Array, within := {}) -> Variant:
	if where.is_empty():
		return null
	for _try in 40:
		var room = where[rng.randi() % where.size()]
		var cell := Vector2i(rng.randi_range(room.x1, room.x2 - 1),
			rng.randi_range(room.y1, room.y2 - 1))
		if not Dungeon.is_walkable(grid, cell.x, cell.y):
			continue
		if cell == Vector2i(player.x, player.y) or cell == stairs:
			continue
		if occupied(cell) or taken(cell):
			continue
		if not within.is_empty() and not within.has(cell):
			continue
		return cell
	return null


## Every cell the hero can walk to, with `blocked` treated as solid.
## Used before putting a shopkeeper down: theirs is a tile nobody can
## pass, so it must never be the only way through.
func reachable_from(start: Vector2i, blocked := {}) -> Dictionary:
	var seen := {start: true}
	var stack: Array[Vector2i] = [start]
	while not stack.is_empty():
		var cell: Vector2i = stack.pop_back()
		for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var step: Vector2i = cell + offset
			if seen.has(step) or blocked.has(step):
				continue
			if not Dungeon.is_walkable(grid, step.x, step.y):
				continue
			seen[step] = true
			stack.append(step)
	return seen


func _shopkeeper_spot(where: Array) -> Variant:
	for _try in 20:
		var cell = _free_cell(where)
		if cell == null:
			return null
		# Blocked by every keeper already standing, and by this
		# candidate. Checking only the stairs was not enough: a keeper
		# can seal the chest into a dead-end just as easily, and then
		# the floor is finishable but the chest is gone for good.
		var blocked := {cell: true}
		for shop in shops:
			blocked[shop["cell"]] = true
		var open_cells := reachable_from(Vector2i(player.x, player.y), blocked)
		if not open_cells.has(stairs):
			continue
		if chest != null and not open_cells.has(chest["cell"]):
			continue
		if shrine != null and not open_cells.has(shrine):
			continue
		return cell
	return null            ## rather no shop than a floor nobody can finish


## Anything already standing on this cell that is not a monster.
##
## Without this a shopkeeper could be placed on top of the chest, and
## then the chest could never be opened at all: walking into that cell
## opens the shop and returns before the chest is ever looked at. That
## is not theory - playing the port turned up a floor where the merchant
## and the chest shared (20, 9) and the chest stayed shut forever.
func taken(cell: Vector2i) -> bool:
	if item_at(cell) != null or traps.has(cell):
		return true
	if chest != null and chest["cell"] == cell:
		return true
	if shrine != null and shrine == cell:
		return true
	if decor.has(cell):
		return true
	return shop_at(cell) != null


func occupied(cell: Vector2i) -> bool:
	for m in monsters:
		if m.is_alive() and m.cell() == cell:
			return true
	return false


func monster_at(cell: Vector2i) -> Variant:
	for m in monsters:
		if m.is_alive() and m.cell() == cell:
			return m
	return null


func shop_at(cell: Vector2i) -> Variant:
	for shop in shops:
		if shop["cell"] == cell:
			return shop
	return null


func boss_alive() -> bool:
	for m in monsters:
		if m.is_alive() and m.is_boss:
			return true
	return false


func item_at(cell: Vector2i) -> Variant:
	for item in items:
		if item["cell"] == cell:
			return item
	return null


# --- sight ----------------------------------------------------------------

func recompute_fov() -> void:
	lit.clear()
	var here := Vector2i(player.x, player.y)
	for dy in range(-Data.FOV_RADIUS, Data.FOV_RADIUS + 1):
		for dx in range(-Data.FOV_RADIUS, Data.FOV_RADIUS + 1):
			if Vector2(dx, dy).length() > Data.FOV_RADIUS:
				continue
			var cell := here + Vector2i(dx, dy)
			if _line_clear(here, cell):
				lit[cell] = true
				explored[cell] = true


func _line_clear(from: Vector2i, to: Vector2i) -> bool:
	var steps := maxi(absi(to.x - from.x), absi(to.y - from.y))
	for i in range(1, steps):
		var at := Vector2(from) + Vector2(to - from) * (float(i) / float(steps))
		var cell := Vector2i(roundi(at.x), roundi(at.y))
		if cell != from and cell != to and not Dungeon.is_walkable(grid, cell.x, cell.y):
			return false
	return true


# --- the turn -------------------------------------------------------------

func try_move(step: Vector2i) -> void:
	if dead or choosing or step == Vector2i.ZERO or shop_open != null:
		return
	if player.pending_perks > 0 and _perk_panel != null and _perk_panel.visible:
		return
	var target := Vector2i(player.x + step.x, player.y + step.y)
	if step.x != 0:
		player.facing = 1 if step.x > 0 else -1

	var monster: Variant = monster_at(target)
	var shop: Variant = shop_at(target)
	if monster != null:
		_attack_monster(monster)
	elif shop != null:
		# Walking into a shopkeeper opens their shop instead of moving,
		# which is why they are never placed in a chokepoint.
		open_shop(shop)
		return
	elif target == stairs and stairs_locked and boss_alive():
		say("Der Weg nach unten ist verriegelt. Der Boss hält den Schlüssel.")
		return
	elif Dungeon.is_walkable(grid, target.x, target.y):
		player.x = target.x
		player.y = target.y
		_pick_up(target)
		_open_chest(target)
		_spring_trap(target)
		_touch_shrine(target)
		if dead:
			return
		if target == stairs:
			depth += 1
			audio.play("stairs")
			say("Du steigst hinab - Ebene %d." % depth)
			new_level()
			return
	else:
		return

	_tick_poison()
	_tick_regen()
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


func _attack_monster(monster) -> void:
	var damage: int = maxi(1, int(round((player.power() - monster.defense_now())
		* float(Data.difficulty_by_id(difficulty)["player_damage"]))))
	var crit := rng.randf() < player.crit_chance()
	if crit:
		damage *= Data.CRIT_MULT
		# Any critical hit opens a wound, whatever the weapon is made
		# of - bleeding is not an element, it is what a bad cut does.
		monster.bleed_turns = maxi(monster.bleed_turns, Data.BLEED_TURNS)
	var element := _fire_element(monster)
	damage += element
	audio.play("boss" if monster.is_boss else "hit")
	monster.hp -= damage
	var leech := player.buff_total("lifesteal")
	if leech > 0.0 and player.hp < player.max_hp:
		var back: int = maxi(1, int(round(damage * leech)))
		player.hp = mini(player.max_hp, player.hp + back)
	if monster.is_alive():
		say("Kritisch! %s nimmt %d." % [monster.display_name, damage] if crit
			else "Du triffst %s für %d." % [monster.display_name, damage])
		return
	_kill(monster)


## Rolls the weapon's element for this swing and returns the extra
## damage it did. The status it leaves behind is what makes an element
## worth carrying: fire burns on, frost softens the next blow, lightning
## buys a turn, venom drains.
func _fire_element(monster) -> int:
	var id: String = player.weapon_element
	if id == "" or not Data.ELEMENTS.has(id):
		return 0
	var element: Dictionary = Data.ELEMENTS[id]
	if rng.randf() >= float(element["chance"]):
		return 0
	var turns: int = int(element["turns"])
	match element["status"]:
		"burn":
			monster.burn_turns = maxi(monster.burn_turns, turns)
		"weaken":
			monster.weaken_turns = maxi(monster.weaken_turns, turns)
			monster.slow_turns = maxi(monster.slow_turns, turns)
		"stun":
			monster.stun_turns = maxi(monster.stun_turns, turns)
		"poison":
			monster.venom_turns = maxi(monster.venom_turns, turns)
	say("%s: %s!" % [Data.ELEMENTS[id]["name"], monster.display_name])
	return int(element["damage"])

## A monster dies: experience, the level-up that may follow, and the
## sprite. Anything that can kill goes through here - a thrown flask
## that skipped this step handed out no experience at all.
func _kill(monster) -> void:
	audio.play("monster_death")
	say("%s stirbt." % monster.display_name)
	player.kills += 1
	if player.gain_xp(monster.xp_reward) > 0:
		audio.play("levelup")
		_offer_perk()
		say("Level auf! Du bist jetzt Stufe %d." % player.level)
	if _actor_nodes.has(monster):
		_actor_nodes[monster].queue_free()
		_actor_nodes.erase(monster)
	monsters.erase(monster)

func enemy_turn() -> void:
	# Haste is the hero acting twice, expressed the other way round:
	# every second enemy turn is skipped. Doing it as a free extra
	# player move would mean two attacks per tap, which is a different
	# and much stronger thing than the Python build gives.
	if player.has_buff("haste"):
		_haste_flip = not _haste_flip
		if _haste_flip:
			return
	var here := Vector2i(player.x, player.y)
	for monster in monsters.duplicate():
		if not monster.is_alive():
			continue
		# Fire keeps burning whether the thing acts or not.
		if monster.weaken_turns > 0:
			monster.weaken_turns -= 1
		if monster.venom_turns > 0:
			monster.venom_turns -= 1
			monster.hp -= Data.POISON_PER_TURN
			if not monster.is_alive():
				_kill(monster)
				continue
		if monster.bleed_turns > 0:
			monster.bleed_turns -= 1
			monster.hp -= Data.BLEED_DAMAGE
			if not monster.is_alive():
				_kill(monster)
				continue
		if monster.burn_turns > 0:
			monster.burn_turns -= 1
			monster.hp -= Data.BURN_DAMAGE
			if not monster.is_alive():
				_kill(monster)
				continue
		if monster.regen > 0 and monster.hp < monster.max_hp:
			monster.hp = mini(monster.max_hp, monster.hp + monster.regen)
		if monster.stun_turns > 0:
			monster.stun_turns -= 1
			continue
		if monster.slow_turns > 0:
			monster.slow_turns -= 1
			# Slowed things move every other turn, which is what the
			# odd turn count is counting.
			if monster.slow_turns % 2 == 1:
				continue
		# An unseen hero is not chased. They still get hit if they
		# stand next to something already awake and swinging.
		if player.has_buff("invisible") and monster.cell().distance_squared_to(here) > 2:
			continue
		if not monster.awake:
			# They wake when the light reaches them, not when they reach
			# you - same as the original, so a floor is not a stampede.
			if lit.has(monster.cell()):
				monster.awake = true
			else:
				continue
		for _move in monster.speed:
			if dead or not monster.is_alive():
				break
			var to_player: Vector2i = here - monster.cell()
			if absi(to_player.x) + absi(to_player.y) == 1:
				_monster_attacks(monster)
				break
			var step := Vector2i(signi(to_player.x), signi(to_player.y))
			if monster.is_fleeing():
				step = -step
			_step_monster(monster, step)


func _step_monster(monster, step: Vector2i) -> void:
	for candidate in [monster.cell() + step,
			monster.cell() + Vector2i(step.x, 0),
			monster.cell() + Vector2i(0, step.y)]:
		if candidate == monster.cell():
			continue
		if not Dungeon.is_walkable(grid, candidate.x, candidate.y):
			continue
		# Never onto the hero: a monster sharing your tile cannot be
		# attacked at all, since attacks are aimed at the tile you walk
		# into. The pygame build learned that one the hard way.
		if candidate == Vector2i(player.x, player.y) or occupied(candidate):
			continue
		monster.x = candidate.x
		monster.y = candidate.y
		return


func _monster_attacks(monster) -> void:
	var damage: int = maxi(1, monster.power - player.defense())
	damage = maxi(1, int(round(damage * (1.0 - player.damage_reduction))))
	audio.play("player_hurt")
	# A ward soaks the blow before hit points do, and what it cannot
	# hold spills through - a shield that blocked everything or
	# nothing would make the number on it meaningless.
	if player.shield > 0:
		var soaked: int = mini(player.shield, damage)
		player.shield -= soaked
		damage -= soaked
		if damage <= 0:
			say("Der Schild hält den Schlag von %s." % monster.display_name)
			_retaliate(monster)
			return
	player.hp -= damage
	say("%s trifft dich für %d." % [monster.display_name, damage])
	_retaliate(monster)
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		say("Du stirbst auf Ebene %d. Tippe NEU." % depth)


## What an attacker gets back for hitting you: thorns cut, an ember aura
## sets them alight. Both fire whether or not the blow got through the
## shield - they answer the attack, not the damage.
func _retaliate(monster) -> void:
	var thorns := int(player.buff_total("thorns"))
	if thorns > 0 and monster.is_alive():
		monster.hp -= thorns
		say("Dornen reißen %s für %d." % [monster.display_name, thorns])
		if not monster.is_alive():
			_kill(monster)
			return
	var burn := int(player.buff_total("burn_attackers"))
	if burn > 0 and monster.is_alive():
		monster.burn_turns = maxi(monster.burn_turns, burn)

func _pick_up(cell: Vector2i) -> void:
	var item: Variant = item_at(cell)
	if item == null:
		return
	var loot: Dictionary = item
	match loot["kind"]:
		"gold":
			var luck := 1.5 if player.has_buff("luck") else 1.0
			var found: int = int(round(loot["amount"] * player.gold_mult * luck))
			player.gold += found
			audio.play("coin")
			say("%d Gold." % found)
		"potion":
			var id: String = loot.get("potion", Data.DEFAULT_POTION)
			player.add_potion(id)
			audio.play("pickup")
			say("Aufgehoben: %s." % Data.potion_by_id(id)["name"])
		"scroll":
			var scroll_id: String = loot.get("scroll", "reveal")
			player.scrolls[scroll_id] = int(player.scrolls.get(scroll_id, 0)) + 1
			audio.play("pickup")
			say("Aufgehoben: %s." % Data.scroll_by_id(scroll_id)["name"])
		"weapon":
			# A find is compared against what is in hand, not against its own
			# tier: a Fine Dagger can beat a plain Short Sword, and the sale
			# price is what stops a worse one from being a dead pickup.
			var w_type: int = mini(Data.WEAPONS.size() - 1, 1 + depth / 2)
			var w_rarity: Dictionary = Data.pick_rarity(depth, rng)
			var w_value: int = int(round(float(Data.WEAPONS[w_type]["bonus"])
				* float(w_rarity["mult"])))
			if w_value > player.weapon_bonus():
				player.weapon = w_type
				player.weapon_rarity = w_rarity["id"]
				player.weapon_extra = 0
				player.weapon_element = Data.pick_element(depth, rng)
				audio.play("equip")
				say("Neue Waffe: %s +%d." % [player.weapon_name(), player.weapon_bonus()])
			else:
				player.gold += 10
				say("Eine schlechtere Waffe - für 10 Gold verkauft.")
		"armour":
			var a_type: int = mini(Data.ARMOURS.size() - 1, 1 + depth / 3)
			var a_rarity: Dictionary = Data.pick_rarity(depth, rng)
			var a_value: int = int(round(float(Data.ARMOURS[a_type]["bonus"])
				* float(a_rarity["mult"])))
			if a_value > player.armour_bonus():
				player.armour = a_type
				player.armour_rarity = a_rarity["id"]
				player.armour_extra = 0
				audio.play("equip")
				say("Neue Rüstung: %s +%d." % [player.armour_name(), player.armour_bonus()])
			else:
				player.gold += 10
				say("Eine schlechtere Rüstung - für 10 Gold verkauft.")

	items.erase(loot)
	if _item_nodes.has(cell):
		_item_nodes[cell].queue_free()
		_item_nodes.erase(cell)


## One turn of everything that runs on a clock: buffs expiring, the
## regeneration they grant, and bleeding. Called once per player turn,
## never per frame.
func _tick_buffs() -> void:
	var regen := int(player.buff_total("regen"))
	for id in player.buffs.keys():
		var left: int = int(player.buffs[id]) - 1
		if left <= 0:
			player.buffs.erase(id)
			say("%s lässt nach." % Data.BUFFS[id]["name"])
		else:
			player.buffs[id] = left
	if regen > 0 and player.hp < player.max_hp and not dead:
		player.hp = mini(player.max_hp, player.hp + regen)
	if player.bleed_turns > 0 and not dead:
		player.bleed_turns -= 1
		player.hp -= 1
		say("Du blutest.")
		if player.hp <= 0:
			player.hp = 0
			dead = true
			Save.wipe()
			audio.play("death")
			_show_death()

## Regeneration ticks on the turn, not the frame - a hero who heals
## faster on a faster phone is a different game.
func _tick_regen() -> void:
	if player.regen_interval <= 0 or dead or player.hp >= player.max_hp:
		return
	player.regen_counter += 1
	if player.regen_counter < player.regen_interval:
		return
	player.regen_counter = 0
	player.hp = mini(player.max_hp, player.hp + 1)


func _tick_poison() -> void:
	if player.poison_turns <= 0 or dead:
		return
	player.poison_turns -= 1
	player.hp -= Data.POISON_PER_TURN
	say("Das Gift zehrt an dir (%d)." % Data.POISON_PER_TURN)
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		say("Das Gift bringt dich um. Tippe NEU.")


func _spring_trap(cell: Vector2i) -> void:
	if not traps.has(cell):
		return
	var id: String = traps[cell]
	var trap: Dictionary = Data.TRAPS[id]
	# One-shot traps are gone once sprung; the rest stay dangerous,
	# the same as the Python build.
	if trap.get("one_shot", false):
		traps.erase(cell)
	player.hp -= trap["damage"]
	audio.play("trap")
	say("%s! Du nimmst %d Schaden." % [trap["name"], trap["damage"]])
	if trap.has("poison"):
		player.poison_turns = maxi(player.poison_turns, trap["poison"])
		say("Du bist vergiftet.")
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		say("Die Falle bringt dich um. Tippe NEU.")


func _open_chest(cell: Vector2i) -> void:
	if chest == null or chest["opened"] or chest["cell"] != cell:
		return
	chest["opened"] = true
	if not chest["mimic"]:
		var gold: int = 25 + depth * 8
		player.gold += gold
		# Through add_potion, not the raw counter: potions and
		# potion_counts have to agree, and a chest that bumped only the
		# total left the hero holding a flask that was not any kind.
		player.add_potion(Data.pick_potion(depth, rng))
		say("Die Truhe enthält %d Gold und einen Trank." % gold)
		return
	# Beside the chest, never on it: a chest is opened by walking
	# onto it, so the hero is standing there - and a monster sharing
	# your tile cannot be attacked at all, because attacks are aimed
	# at the tile you walk into. The Python build had exactly that
	# bug until playing it turned it up.
	var spot: Variant = null
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
			Vector2i(1, 1), Vector2i(1, -1), Vector2i(-1, 1), Vector2i(-1, -1)]:
		var candidate: Vector2i = cell + offset
		if Dungeon.is_walkable(grid, candidate.x, candidate.y) and not occupied(candidate):
			spot = candidate
			break
	if spot == null:
		say("Die Truhe war eine Mimik - aber sie kommt nicht heraus.")
		return
	var mimic := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"], difficulty)
	mimic.x = spot.x
	mimic.y = spot.y
	mimic.max_hp = int(mimic.max_hp * Data.MIMIC_MULT)
	mimic.hp = mimic.max_hp
	mimic.power = int(mimic.power * Data.MIMIC_MULT)
	mimic.is_mimic = true
	mimic.awake = true
	mimic.display_name = "Mimik (%s)" % mimic.display_name
	mimic.snap()
	monsters.append(mimic)
	audio.play("boss")
	say("Die Truhe schnappt zu - es war eine Mimik!")


## The shop is a panel over the game rather than a screen of its own:
## the dungeon stays visible behind it, and closing it is one tap.
func open_shop(shop: Dictionary) -> void:
	shop_open = shop
	_refresh_shop()
	if _shop_panel != null:
		_shop_panel.visible = true


func close_shop() -> void:
	shop_open = null
	if _shop_panel != null:
		_shop_panel.visible = false


func buy(what: String) -> void:
	if shop_open == null:
		return
	match ("potion" if what.begins_with("potion:") else what):
		"potion":
			var id: String = what.substr(7) if what.begins_with("potion:") else Data.DEFAULT_POTION
			var potion := Data.potion_by_id(id)
			if _spend(price(int(potion["price"]))):
				player.add_potion(id)
				say("Gekauft: %s." % potion["name"])
		"weapon":
			# The smith hammers on what you carry rather than selling you a
			# new one: that is the whole reason he exists, and it keeps the
			# weapon you found in play instead of retiring it.
			if _spend(price(Data.smith_price(player.weapon_extra))):
				player.weapon_extra += Data.SMITH_WEAPON_STEP
				audio.play("equip")
				say("Der Schmied schärft %s auf +%d." % [
					player.weapon_name(), player.weapon_bonus()])
		"armour":
			if _spend(price(Data.smith_price(player.armour_extra))):
				player.armour_extra += Data.SMITH_ARMOUR_STEP
				audio.play("equip")
				say("Der Schmied verstärkt %s auf +%d." % [
					player.armour_name(), player.armour_bonus()])

		"heal":
			if player.hp >= player.max_hp:
				say("Dir fehlt nichts.")
			elif _spend(price(Data.UPGRADE_COST)):
				player.hp = player.max_hp
				player.poison_turns = 0
				say("Der Schmied flickt dich zusammen.")
	_refresh_shop()


## What a shopkeeper actually asks. The harder levels put a markup on
## everything, which is what makes gold tight rather than just making
## monsters hit harder.
func price(base: int) -> int:
	var markup: float = float(Data.difficulty_by_id(difficulty)["markup"])
	return int(round(base * (1.0 + markup)))


func _spend(cost: int) -> bool:
	if player.gold < cost:
		audio.play("denied")
		say("Zu wenig Gold - %d fehlen." % (cost - player.gold))
		return false
	player.gold -= cost
	return true


## Drinks the selected flask. Every effect in the table is handled here;
## an effect nobody handles would be a potion that costs a turn and does
## nothing, which is worse than not having it.
func drink() -> void:
	if dead or choosing or player.potions <= 0:
		return
	var id: String = player.selected_potion
	if not player.potion_counts.has(id):
		id = player.next_potion()
	var potion := Data.potion_by_id(id)
	var effect: Dictionary = potion["effect"]

	# A plain heal on full health is a wasted flask, so it is refused -
	# but only a plain one: a Panacea also cures, and refusing that would
	# strand a poisoned hero at full health.
	if effect.size() == 1 and effect.has("heal") and player.hp >= player.max_hp:
		audio.play("denied")
		say("Du bist bei voller Gesundheit.")
		return

	player.add_potion(id, -1)
	audio.play("pickup")
	say("Du trinkst: %s." % potion["name"])
	_apply_effect(effect)
	if dead:
		return
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


## One potion effect, whatever it is made of. Kept in a single place so
## a scroll or a shrine can hand the same table over later.
func _apply_effect(effect: Dictionary) -> void:
	if effect.has("heal"):
		var healed: int = mini(player.max_hp - player.hp, int(effect["heal"]))
		player.hp += healed
		say("%d Leben zurück." % healed)
	if effect.has("heal_pct"):
		player.hp = player.max_hp
		say("Vollständig geheilt.")
	if effect.has("max_hp"):
		player.max_hp += int(effect["max_hp"])
		player.hp += int(effect["max_hp"])
		say("+%d maximales Leben, dauerhaft." % int(effect["max_hp"]))
	if effect.has("base_power"):
		player.base_power += int(effect["base_power"])
		say("+%d Angriff, dauerhaft." % int(effect["base_power"]))
	if effect.has("base_defense"):
		player.base_defense += int(effect["base_defense"])
		say("+%d Verteidigung, dauerhaft." % int(effect["base_defense"]))
	if effect.has("xp_levels"):
		# Half a level, measured against what the next one costs.
		var gained: int = player.gain_xp(int(player.xp_to_next * float(effect["xp_levels"])))
		if gained > 0:
			audio.play("levelup")
			_offer_perk()
		say("Erfahrung strömt dir zu.")
	if effect.has("buff"):
		var id: String = effect["buff"]
		var turns: int = int(effect.get("turns", 10))
		# Drinking the same buff again extends it rather than replacing it.
		player.buffs[id] = int(player.buffs.get(id, 0)) + turns
		say("%s für %d Züge." % [Data.BUFFS[id]["name"], turns])
	if effect.has("shield"):
		player.shield += int(effect["shield"])
		say("Ein Schild von %d." % int(effect["shield"]))
	if effect.has("reveal"):
		_reveal_level()
		say("Die Ebene liegt offen vor dir.")
	if effect.has("blink"):
		_blink()
	if effect.has("gold"):
		var range_: Array = effect["gold"]
		var amount: int = rng.randi_range(int(range_[0]), int(range_[1]))
		player.gold += amount
		audio.play("coin")
		say("%d Gold aus dem Nichts." % amount)
	if effect.has("cure"):
		for what in effect["cure"]:
			if what == "poison_turns":
				player.poison_turns = 0
			elif what == "bleed_turns":
				player.bleed_turns = 0
		say("Das Übel weicht.")
	if effect.get("cure_debuffs", false):
		for id in player.buffs.keys():
			if Data.BUFFS[id].get("power", 0) < 0 or Data.BUFFS[id].get("defense", 0) < 0:
				player.buffs.erase(id)
	if effect.has("self_poison"):
		player.poison_turns += int(effect["self_poison"])
		say("Es brennt in der Kehle - vergiftet.")
	if effect.has("burst_damage"):
		_burst(effect)


## The shrine, triggered by walking onto it. Two of the five outcomes
## are bad, which is the point: a tile you always want to step on is not
## a decision.
func _touch_shrine(cell: Vector2i) -> void:
	if shrine == null or shrine != cell:
		return
	shrine = null
	var id := Data.pick_shrine(rng)
	match id:
		"vitality":
			player.hp = player.max_hp
			audio.play("levelup")
			say("Der Schrein heilt dich vollständig.")
		"power":
			player.base_power += 2
			audio.play("levelup")
			say("Der Schrein schenkt dir Kraft: +2 Angriff.")
		"fortune":
			var amount: int = depth * 15
			player.gold += amount
			audio.play("coin")
			say("Der Schrein schüttet %d Gold aus." % amount)
		"frailty":
			var loss: int = clampi(player.max_hp / 5, 1, 5)
			player.max_hp = maxi(5, player.max_hp - loss)
			player.hp = mini(player.hp, player.max_hp)
			audio.play("player_hurt")
			say("Der Schrein zehrt an dir: -%d maximales Leben." % loss)
		"ambush":
			audio.play("player_hurt")
			say("Aus dem Schrein steigen rachsüchtige Geister!")
			_ambush()


## Two monsters, right next to the hero and already awake. Beside them,
## never on them, for the same reason the mimic is: a monster sharing
## your tile cannot be attacked at all.
func _ambush() -> void:
	var spawned := 0
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if spawned >= 2:
			return
		var cell: Vector2i = Vector2i(player.x, player.y) + offset
		if not Dungeon.is_walkable(grid, cell.x, cell.y) or occupied(cell):
			continue
		var ghost := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"], difficulty)
		ghost.x = cell.x
		ghost.y = cell.y
		ghost.awake = true
		ghost.snap()
		monsters.append(ghost)
		spawned += 1


## Reads the selected scroll. Each one aims itself: there is no cursor
## on a phone, and asking for a target would mean a targeting mode for
## three scrolls.
func read_scroll(id: String) -> void:
	if dead or choosing or int(player.scrolls.get(id, 0)) <= 0:
		return
	var scroll := Data.scroll_by_id(id)
	player.scrolls[id] = int(player.scrolls[id]) - 1
	if int(player.scrolls[id]) <= 0:
		player.scrolls.erase(id)
	say("Du liest: %s." % scroll["name"])
	match id:
		"fireball":
			_fireball(int(scroll["damage"]))
		"teleport":
			_blink()
		"reveal":
			_reveal_level()
			say("Die Ebene liegt offen vor dir.")
	if dead:
		return
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


## The nearest monster you can actually see, and everything beside it.
func _fireball(damage: int) -> void:
	var here := Vector2i(player.x, player.y)
	var target = null
	var closest := 1 << 30
	for monster in monsters:
		if not monster.is_alive() or not lit.has(monster.cell()):
			continue
		var away: int = monster.cell().distance_squared_to(here)
		if away < closest:
			closest = away
			target = monster
	if target == null:
		audio.play("denied")
		say("Nichts in Sicht - die Rolle verpufft.")
		return
	var centre: Vector2i = target.cell()
	audio.play("boss")
	var hit := 0
	for monster in monsters.duplicate():
		if not monster.is_alive():
			continue
		var away: Vector2i = monster.cell() - centre
		if absi(away.x) > 1 or absi(away.y) > 1:
			continue
		hit += 1
		monster.hp -= damage
		monster.awake = true
		monster.burn_turns = maxi(monster.burn_turns, 2)
		if not monster.is_alive():
			_kill(monster)
	say("Der Feuerball trifft %d." % hit)


## A thrown flask: everything within BURST_RADIUS takes the hit, and the
## hero does not - the Python build throws it, it does not drink it.
func _burst(effect: Dictionary) -> void:
	var here := Vector2i(player.x, player.y)
	var hit := 0
	for monster in monsters.duplicate():
		if not monster.is_alive():
			continue
		var away: Vector2i = monster.cell() - here
		if absi(away.x) > Data.BURST_RADIUS or absi(away.y) > Data.BURST_RADIUS:
			continue
		hit += 1
		monster.hp -= int(effect["burst_damage"])
		monster.awake = true
		if effect.has("burst_burn"):
			monster.burn_turns = maxi(monster.burn_turns, int(effect["burst_burn"]))
		if effect.has("burst_slow"):
			monster.slow_turns = maxi(monster.slow_turns, int(effect["burst_slow"]))
		if effect.has("burst_stun"):
			monster.stun_turns = maxi(monster.stun_turns, int(effect["burst_stun"]))
		if not monster.is_alive():
			_kill(monster)
	audio.play("boss")
	say("Die Phiole zerplatzt - %d getroffen." % hit)


## Every walkable cell on the floor becomes explored. Not lit: the map
## is known, but you still cannot see what is standing in the dark.
func _reveal_level() -> void:
	for y in MAP_H:
		for x in MAP_W:
			if Dungeon.is_walkable(grid, x, y):
				explored[Vector2i(x, y)] = true


## A short hop to a free cell somewhere else on the floor.
func _blink() -> void:
	var spot: Variant = _free_cell(rooms)
	if spot == null:
		say("Nichts geschieht.")
		return
	player.x = spot.x
	player.y = spot.y
	player.snap()
	say("Ein Blinzeln - und du stehst woanders.")


## Walks to the next kind of flask carried. Costs no turn: choosing what
## to drink is not an action, drinking it is.
func cycle_potion() -> void:
	if player.potions <= 0:
		return
	player.selected_potion = player.next_potion()
	audio.play("equip")

func say(line: String) -> void:
	log_lines.append(line)
	while log_lines.size() > 4:
		log_lines.remove_at(0)


# --- drawing --------------------------------------------------------------

func paint() -> void:
	if _floor_layer == null:
		return
	_floor_layer.clear()
	_dim_layer.clear()
	for cell in explored:
		var name := _tile_for(cell.x, cell.y)
		if cell == stairs and _tile_ids.has("floor_stairs"):
			name = "floor_stairs"
		if name == "" or not _tile_ids.has(name):
			continue
		var layer := _floor_layer if lit.has(cell) else _dim_layer
		layer.set_cell(cell, _tile_ids[name], Vector2i.ZERO)

	var tint: Color = tier.get("tint", Color.WHITE)
	_floor_layer.modulate = tint
	_dim_layer.modulate = tint * Color(0.42, 0.42, 0.52)

	for item in items:
		_place_item(item)
	if chest != null:
		_place_prop(chest["cell"], "chest_empty_open_anim_f2" if chest["opened"]
			else "chest_full_open_anim_f0")
	for cell in decor:
		_place_prop(cell, decor[cell])
	if shrine != null:
		# A column: the only thing in the tileset that reads as
		# something built rather than dropped.
		_place_prop(shrine, "column")
	for shop in shops:
		_place_prop(shop["cell"], "blacksmith" if shop["kind"] == "smith" else "merchant")
	for monster in monsters:
		_place_monster(monster)

	_stand_on(_hero_node, Vector2i(player.x, player.y), HERO_TILES)
	_hero_node.flip_h = player.facing < 0
	_camera.position = Vector2(player.x, player.y) * TILE + Vector2(TILE, TILE) * 0.5


func _tile_for(x: int, y: int) -> String:
	if grid[y][x] != Dungeon.WALL:
		return "floor_%d" % (1 + (x * 7 + y * 13 + x * y * 3) % FLOOR_VARIANTS)
	var south := not _is_wall(x, y + 1)
	var north := not _is_wall(x, y - 1)
	var west := not _is_wall(x - 1, y)
	var east := not _is_wall(x + 1, y)
	if south:
		return "wall_mid"
	if west and not east:
		return "wall_left"
	if east and not west:
		return "wall_right"
	if north:
		return "wall_mid"
	if west or east:
		return "wall_top_mid"
	return ""


func _is_wall(x: int, y: int) -> bool:
	if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
		return true
	return grid[y][x] == Dungeon.WALL


func _place_item(item: Dictionary) -> void:
	var cell: Vector2i = item["cell"]
	if not _item_nodes.has(cell):
		var node := Sprite2D.new()
		node.texture = _sprite_for(_item_art(item))
		node.centered = false
		node.z_index = 1
		add_child(node)
		_item_nodes[cell] = node
	var sprite: Sprite2D = _item_nodes[cell]
	sprite.texture = _sprite_for(_item_art(item))
	# Loot art is not all one size either: the flasks are 16x16 tiles,
	# the scroll and the sword are paintings several hundred pixels
	# tall. Unscaled, a scroll on the floor covered half the room.
	_stand_on(sprite, cell, ITEM_TILES)
	sprite.visible = explored.has(cell)


## The sprite a piece of loot shows on the floor. A potion wears the
## flask of its own kind, so what you pick up is what you saw lying
## there rather than a red bottle that turns out to be something else.
func _item_art(item: Dictionary) -> String:
	match item["kind"]:
		"potion":
			return Data.potion_by_id(item.get("potion", Data.DEFAULT_POTION))["flask"]
		"scroll":
			return "scroll"
		"weapon":
			return "weapon"
		"armour":
			return "armor"
	return "coin_anim_f0"

## One standing thing on the map - a chest, a shopkeeper. Kept in the
## same node cache as everything else so a repaint moves sprites
## rather than rebuilding them.
func _place_prop(cell: Vector2i, art: String) -> void:
	var key := "prop:%s" % str(cell)
	if not _item_nodes.has(key):
		var node := Sprite2D.new()
		node.texture = _sprite_for(art)
		node.centered = false
		node.z_index = 1
		add_child(node)
		_item_nodes[key] = node
	var sprite: Sprite2D = _item_nodes[key]
	sprite.texture = _sprite_for(art)
	_stand_on(sprite, cell, PROP_TILES if art in ["merchant", "blacksmith"] else 1.0)
	sprite.visible = explored.has(cell)


## Puts a sprite on a cell at a given height in tiles: scaled to that
## height, centred left to right, and standing on the floor of the cell
## rather than hanging from its top. Everything taller than one tile -
## monsters, shopkeepers, the hero - overlaps the wall behind it, which
## is exactly how the pygame build looks.
func _stand_on(sprite: Sprite2D, cell: Vector2i, tiles: float) -> void:
	var texture := sprite.texture
	if texture == null:
		return
	var height := float(texture.get_height())
	var factor := (TILE * tiles) / height if height > 0.0 else 1.0
	sprite.scale = Vector2(factor, factor)
	var width := float(texture.get_width()) * factor
	sprite.position = Vector2(cell) * TILE + Vector2(
		(TILE - width) * 0.5, TILE - height * factor)


func _place_monster(monster) -> void:
	if not _actor_nodes.has(monster):
		var node := Sprite2D.new()
		node.texture = _sprite_for(monster.sprite)
		node.centered = false
		node.z_index = 2
		add_child(node)
		_actor_nodes[monster] = node
	var sprite: Sprite2D = _actor_nodes[monster]
	_stand_on(sprite, monster.cell(),
		MONSTER_TILES * (BOSS_SCALE if monster.is_boss else 1.0))
	sprite.flip_h = monster.x > player.x
	sprite.visible = lit.has(monster.cell())


# --- the panel ------------------------------------------------------------

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	_hud = Control.new()
	_hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_hud)

	# Everything the player uses while walking lives in one node, so
	# the title screen can put it away with a single flag instead of
	# leaving a d-pad and a health bar showing through the menu.
	_play_ui = Control.new()
	_play_ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	_play_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_play_ui)

	for name in ["stats", "gear", "fps", "log"]:
		var label := Label.new()
		label.name = name
		label.add_theme_font_size_override("font_size", 22)
		label.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
		_play_ui.add_child(label)
	_play_ui.get_node("stats").position = Vector2(14, 8)
	# Two lines, because one did not fit: at 1280 wide the gear names
	# pushed the buff row off the right-hand edge, where a player has no
	# way to know it exists.
	_play_ui.get_node("gear").position = Vector2(14, 36)
	_play_ui.get_node("fps").position = Vector2(14, 64)

	var log_label: Label = _play_ui.get_node("log")
	log_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	log_label.position = Vector2(-620, -170)
	log_label.custom_minimum_size = Vector2(600, 130)
	log_label.add_theme_color_override("font_color", Color(0.80, 0.80, 0.86))

	var pad := 28.0
	var size := 120.0
	var origin := Vector2(pad + size, -pad - size * 2.0)
	_button("^", origin + Vector2(0, -size), size, Vector2i(0, -1))
	_button("v", origin, size, Vector2i(0, 1))
	_button("<", origin + Vector2(-size, -size * 0.5), size, Vector2i(-1, 0))
	_button(">", origin + Vector2(size, -size * 0.5), size, Vector2i(1, 0))

	# Two buttons, because there are thirty kinds of flask now: one
	# drinks what is selected, the other walks through what is carried.
	_drink_button = Button.new()
	_drink_button.custom_minimum_size = Vector2(size * 2.4, size * 0.8)
	_drink_button.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_drink_button.position = Vector2(-pad - size * 2.4, -pad - size * 0.8)
	_drink_button.add_theme_font_size_override("font_size", 24)
	_drink_button.pressed.connect(drink)
	_play_ui.add_child(_drink_button)

	var swap := Button.new()
	swap.text = "▶"
	swap.custom_minimum_size = Vector2(size * 0.7, size * 0.8)
	swap.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	swap.position = Vector2(-pad - size * 3.2, -pad - size * 0.8)
	swap.add_theme_font_size_override("font_size", 26)
	swap.pressed.connect(cycle_potion)
	_play_ui.add_child(swap)

	# One button per scroll, shown only while one is carried. Three of
	# them, each aiming itself - a targeting mode for that would be more
	# interface than the scrolls are worth.
	_scroll_buttons.clear()
	var at := 0
	for scroll in Data.SCROLLS:
		var button := Button.new()
		button.custom_minimum_size = Vector2(size * 1.5, size * 0.6)
		button.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
		button.position = Vector2(-pad - size * 1.5,
			-pad - size * (1.5 + 0.65 * at))
		button.add_theme_font_size_override("font_size", 20)
		button.visible = false
		button.pressed.connect(read_scroll.bind(scroll["id"]))
		_play_ui.add_child(button)
		_scroll_buttons.append({"node": button, "id": scroll["id"]})
		at += 1

	var again := Button.new()
	again.text = "NEU"
	again.custom_minimum_size = Vector2(size, size * 0.6)
	again.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	again.position = Vector2(-pad - size, pad)
	again.add_theme_font_size_override("font_size", 26)
	again.pressed.connect(show_title)
	_play_ui.add_child(again)

	_build_shop_panel()
	_build_perk_panel()
	_build_dead_panel()
	_build_title_panel()


## A panel you cannot see through. The default theme panel is nearly
## transparent, which over a dungeon means the map runs straight through
## the buttons and the text sits on rubble.
func _solid_panel(panel: PanelContainer) -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.07, 0.06, 0.09, 0.98)
	style.border_color = Color(0.91, 0.71, 0.29, 0.75)
	style.set_border_width_all(3)
	style.set_corner_radius_all(10)
	style.set_content_margin_all(22)
	panel.add_theme_stylebox_override("panel", style)


## The level-up choice: three perks, pick one. It blocks movement the
## same way a shop does, and it is the reason pending_perks exists -
## two levels in one kill hand out two choices, one after the other,
## instead of quietly throwing the second away.
func _build_perk_panel() -> void:
	_perk_panel = PanelContainer.new()
	_perk_panel.set_anchors_preset(Control.PRESET_CENTER)
	_perk_panel.position = Vector2(-340, -180)
	_perk_panel.custom_minimum_size = Vector2(680, 360)
	_perk_panel.visible = false
	_solid_panel(_perk_panel)
	_hud.add_child(_perk_panel)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	_perk_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Stufenaufstieg - wähle eine Gabe"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_perk_buttons.clear()
	for i in Data.PERK_CHOICES:
		var button := Button.new()
		button.custom_minimum_size = Vector2(0, 78)
		button.add_theme_font_size_override("font_size", 26)
		button.pressed.connect(take_perk.bind(i))
		column.add_child(button)
		_perk_buttons.append(button)


func _offer_perk() -> void:
	if _perk_panel == null or player.pending_perks <= 0:
		return
	perk_choices = Data.perk_choices(rng)
	for i in _perk_buttons.size():
		var button: Button = _perk_buttons[i]
		var shown: bool = i < perk_choices.size()
		button.visible = shown
		if shown:
			button.text = "%s - %s" % [perk_choices[i]["name"], perk_choices[i]["desc"]]
	_perk_panel.visible = true


func take_perk(index: int) -> void:
	if index < 0 or index >= perk_choices.size() or player.pending_perks <= 0:
		return
	var perk: Dictionary = perk_choices[index]
	player.base_power += int(perk.get("power", 0))
	player.base_defense += int(perk.get("defense", 0))
	var extra: int = int(perk.get("hp", 0))
	player.max_hp += extra
	player.hp += extra
	player.bonus_crit += float(perk.get("crit", 0.0))
	player.damage_reduction = minf(0.8, player.damage_reduction + float(perk.get("reduction", 0.0)))
	player.gold_mult += float(perk.get("gold", 0.0))
	if perk.has("regen"):
		# Taking it twice makes it faster rather than doing nothing.
		player.regen_interval = (int(perk["regen"]) if player.regen_interval == 0
			else maxi(1, player.regen_interval - 1))
	player.pending_perks -= 1
	audio.play("levelup")
	say("Gabe erhalten: %s." % perk["name"])
	_perk_panel.visible = false
	perk_choices.clear()
	# A second level from the same kill gets its own choice.
	if player.pending_perks > 0:
		_offer_perk()
	else:
		save_run()


## What is left of a run when it ends. The pygame build shows the same
## four numbers; without them a death is just the word "gestorben" and
## the player has no idea whether it went well.
func _build_dead_panel() -> void:
	_dead_panel = PanelContainer.new()
	_dead_panel.set_anchors_preset(Control.PRESET_CENTER)
	_dead_panel.position = Vector2(-320, -200)
	_dead_panel.custom_minimum_size = Vector2(640, 400)
	_dead_panel.visible = false
	_solid_panel(_dead_panel)
	_hud.add_child(_dead_panel)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 16)
	_dead_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Du bist gestorben"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 40)
	heading.add_theme_color_override("font_color", Color(0.85, 0.32, 0.30))
	column.add_child(heading)

	_dead_text = Label.new()
	_dead_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_dead_text.add_theme_font_size_override("font_size", 26)
	column.add_child(_dead_text)

	var again := Button.new()
	again.text = "NOCH EINMAL"
	again.custom_minimum_size = Vector2(0, 76)
	again.add_theme_font_size_override("font_size", 30)
	again.pressed.connect(func() -> void: choose_class(hero_class))
	column.add_child(again)

	var menu := Button.new()
	menu.text = "ANDERER HELD"
	menu.custom_minimum_size = Vector2(0, 70)
	menu.add_theme_font_size_override("font_size", 28)
	menu.pressed.connect(show_title)
	column.add_child(menu)


## Called the moment the hero dies, from wherever killed them.
func _show_death() -> void:
	if _dead_panel == null:
		return
	# The run goes into the record before it is shown, so the totals
	# under the summary already include the run being summarised.
	var stats := Stats.record_run(depth, player.level, player.kills, player.gold, true)
	_dead_text.text = "Ebene %d     Stufe %d     %d Kills     %d Gold

%d Läufe, %d Tode - am tiefsten: Ebene %d" % [
		depth, player.level, player.kills, player.gold,
		stats["runs"], stats["deaths"], stats["deepest"]]
	_dead_panel.visible = true


## Two switches, because those are the two things a player on a bus
## actually needs. They sit on the title screen rather than behind a
## pause button: that is where you already are before a run starts, and
## the sound is the first thing anyone turns off.
func _build_settings(column: VBoxContainer) -> void:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 20)
	column.add_child(row)

	_sound_button = Button.new()
	_sound_button.custom_minimum_size = Vector2(280, 62)
	_sound_button.add_theme_font_size_override("font_size", 24)
	_sound_button.pressed.connect(toggle_sound)
	row.add_child(_sound_button)

	_music_button = Button.new()
	_music_button.custom_minimum_size = Vector2(280, 62)
	_music_button.add_theme_font_size_override("font_size", 24)
	_music_button.pressed.connect(toggle_music)
	row.add_child(_music_button)

	# The difficulty sits with the other switches rather than on a page
	# of its own: it is picked once, in the same breath as the sound.
	_difficulty_button = Button.new()
	_difficulty_button.custom_minimum_size = Vector2(360, 62)
	_difficulty_button.add_theme_font_size_override("font_size", 24)
	_difficulty_button.pressed.connect(cycle_difficulty)
	row.add_child(_difficulty_button)
	_refresh_settings()


func _refresh_settings() -> void:
	if _sound_button == null:
		return
	_sound_button.text = "Ton: %s" % ("AN" if settings["sound"] else "AUS")
	if _difficulty_button != null:
		var level_of_play := Data.difficulty_by_id(difficulty)
		_difficulty_button.text = "Schwierigkeit: %s" % level_of_play["name"]
		_difficulty_button.tooltip_text = level_of_play["desc"]
	_music_button.text = "Musik: %s" % ("AN" if settings["music"] else "AUS")


## Walks through the four levels of play. Only settable from the title
## screen, which is the only place it is shown - changing it mid-run
## would rescale monsters that were already built.
func cycle_difficulty() -> void:
	var at := 0
	for i in Data.DIFFICULTIES.size():
		if Data.DIFFICULTIES[i]["id"] == difficulty:
			at = i
			break
	difficulty = Data.DIFFICULTIES[(at + 1) % Data.DIFFICULTIES.size()]["id"]
	settings["difficulty"] = difficulty
	Settings.write(settings)
	_refresh_settings()
	audio.play("equip")

func toggle_sound() -> void:
	settings["sound"] = not settings["sound"]
	audio.enabled = settings["sound"]
	Settings.write(settings)
	_refresh_settings()
	audio.play("pickup")


func toggle_music() -> void:
	settings["music"] = not settings["music"]
	audio.set_music_enabled(settings["music"])
	if settings["music"]:
		audio.play_music(tier.get("music", ""))
	Settings.write(settings)
	_refresh_settings()


## The title screen: three heroes, one tap each. It sits on the HUD
## layer over a dungeon that already exists, so the first floor is
## generated and drawn before anyone chooses - tapping a hero starts
## the run instantly instead of stopping to build a level.
func _build_title_panel() -> void:
	_title_panel = PanelContainer.new()
	_title_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud.add_child(_title_panel)

	var backdrop := ColorRect.new()
	backdrop.color = Color(0.04, 0.03, 0.06, 0.92)
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	_title_panel.add_child(backdrop)

	var column := VBoxContainer.new()
	column.set_anchors_preset(Control.PRESET_FULL_RECT)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 18)
	_title_panel.add_child(column)

	var heading := Label.new()
	heading.text = "DUNGEON CRAWLER"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 56)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var subtitle := Label.new()
	subtitle.text = "Wähle deinen Helden"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_font_size_override("font_size", 26)
	column.add_child(subtitle)

	# Only shown when there is something to continue. A dead run wipes
	# its own save, so this never offers to resume a finished one.
	_continue_button = Button.new()
	_continue_button.text = "LAUF FORTSETZEN"
	_continue_button.custom_minimum_size = Vector2(0, 78)
	_continue_button.add_theme_font_size_override("font_size", 30)
	_continue_button.pressed.connect(continue_run)
	_continue_button.custom_minimum_size = Vector2(440, 78)
	var centred := CenterContainer.new()
	centred.add_child(_continue_button)
	column.add_child(centred)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 26)
	column.add_child(row)

	for info in Data.CLASSES:
		var card := VBoxContainer.new()
		card.custom_minimum_size = Vector2(300, 0)
		card.add_theme_constant_override("separation", 8)
		row.add_child(card)

		var portrait := TextureRect.new()
		portrait.texture = load(CLASS_DIR + info["sprite"] + ".png")
		portrait.custom_minimum_size = Vector2(0, 150)
		portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		portrait.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		card.add_child(portrait)

		var blurb := Label.new()
		blurb.text = info["blurb"]
		blurb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		blurb.custom_minimum_size = Vector2(280, 64)
		blurb.add_theme_font_size_override("font_size", 20)
		blurb.add_theme_color_override("font_color", Color(0.80, 0.80, 0.86))
		card.add_child(blurb)

		var pick := Button.new()
		pick.text = info["name"]
		pick.custom_minimum_size = Vector2(0, 76)
		pick.add_theme_font_size_override("font_size", 30)
		pick.add_theme_color_override("font_color", info["color"])
		pick.pressed.connect(choose_class.bind(info["id"]))
		card.add_child(pick)

	_build_settings(column)


## Puts the title screen back up and rolls a fresh floor behind it, so
## the choice is never made against the corpse of the last run.
func show_title() -> void:
	choosing = true
	if _perk_panel != null:
		_perk_panel.visible = false
	if _dead_panel != null:
		_dead_panel.visible = false
	close_shop()
	if _continue_button != null:
		_continue_button.visible = Save.exists()
	if _play_ui != null:
		_play_ui.visible = false
	if _title_panel != null:
		_title_panel.visible = true


## Picks the saved run back up. If the file turns out to be unreadable
## the title screen simply stays where it is - a broken save is not
## worth a dead start.
func continue_run() -> void:
	if load_run():
		say("Weiter geht es auf Ebene %d." % depth)
	else:
		Save.wipe()
		if _continue_button != null:
			_continue_button.visible = false


func choose_class(id: String) -> void:
	hero_class = id
	if _perk_panel != null:
		_perk_panel.visible = false
	if _dead_panel != null:
		_dead_panel.visible = false
	choosing = false
	if _play_ui != null:
		_play_ui.visible = true
	if _title_panel != null:
		_title_panel.visible = false
	new_run()
	say("%s betritt den Dungeon." % Data.class_by_id(id)["name"])


func _build_shop_panel() -> void:
	_shop_panel = PanelContainer.new()
	_shop_panel.set_anchors_preset(Control.PRESET_CENTER)
	_shop_panel.position = Vector2(-360, -220)
	_shop_panel.custom_minimum_size = Vector2(720, 440)
	_shop_panel.visible = false
	_solid_panel(_shop_panel)
	_hud.add_child(_shop_panel)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_shop_panel.add_child(column)

	_shop_title = Label.new()
	_shop_title.add_theme_font_size_override("font_size", 30)
	_shop_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(_shop_title)

	# Five slots, filled at opening time rather than fixed: a merchant
	# carries three flasks rolled for this floor, a smith carries none.
	_shop_buttons.clear()
	for _i in 5:
		var button := Button.new()
		button.custom_minimum_size = Vector2(0, 58)
		button.add_theme_font_size_override("font_size", 24)
		column.add_child(button)
		_shop_buttons.append(button)

	var leave := Button.new()
	leave.text = "VERLASSEN"
	leave.custom_minimum_size = Vector2(0, 66)
	leave.add_theme_font_size_override("font_size", 28)
	leave.pressed.connect(close_shop)
	column.add_child(leave)


## What this shopkeeper has today, priced and greyed out where the purse
## is too light. Rebuilt on every purchase, because buying the sword
## changes what the next one costs.
func _refresh_shop() -> void:
	if _shop_panel == null or shop_open == null:
		return
	var smith: bool = shop_open["kind"] == "smith"
	_shop_title.text = "%s     Dein Gold: %d" % [
		"Schmied" if smith else "Händler", player.gold]

	var offers: Array = []
	if smith:
		offers.append(["weapon", "Schärfen: %s +%d" % [
			Data.WEAPONS[player.weapon]["name"], Data.SMITH_WEAPON_STEP],
			price(Data.smith_price(player.weapon_extra))])
		offers.append(["armour", "Verstärken: %s +%d" % [
			Data.ARMOURS[player.armour]["name"], Data.SMITH_ARMOUR_STEP],
			price(Data.smith_price(player.armour_extra))])
		offers.append(["heal", "Voll heilen", price(Data.UPGRADE_COST)])

	else:
		for id in shop_open.get("stock", []):
			var potion := Data.potion_by_id(id)
			offers.append(["potion:" + id, potion["name"], price(int(potion["price"]))])

	for i in _shop_buttons.size():
		var button: Button = _shop_buttons[i]
		if i >= offers.size():
			button.visible = false
			continue
		var offer: Array = offers[i]
		button.visible = true
		button.text = "%s - %d Gold" % [offer[1], offer[2]]
		button.disabled = player.gold < int(offer[2])
		for old in button.pressed.get_connections():
			button.pressed.disconnect(old["callable"])
		button.pressed.connect(buy.bind(offer[0]))


func _button(label: String, where: Vector2, size: float, step: Vector2i) -> void:
	var button := Button.new()
	button.text = label
	button.custom_minimum_size = Vector2(size, size)
	button.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	button.position = where
	button.add_theme_font_size_override("font_size", 40)
	# Held, not tapped: walking is what a frame rate has to be measured
	# on, and one step per tap measures nothing.
	button.button_down.connect(func() -> void: _held = step)
	button.button_up.connect(func() -> void:
		if _held == step:
			_held = Vector2i.ZERO)
	_play_ui.add_child(button)


func _process(delta: float) -> void:
	_step_cooldown -= delta
	if _held == Vector2i.ZERO:
		for pair in [[KEY_D, Vector2i(1, 0)], [KEY_RIGHT, Vector2i(1, 0)],
				[KEY_A, Vector2i(-1, 0)], [KEY_LEFT, Vector2i(-1, 0)],
				[KEY_S, Vector2i(0, 1)], [KEY_DOWN, Vector2i(0, 1)],
				[KEY_W, Vector2i(0, -1)], [KEY_UP, Vector2i(0, -1)]]:
			if Input.is_key_pressed(pair[0]):
				_held = pair[1]
				break
	# Steps run on a clock, not per frame, so the hero does not walk
	# faster the smoother it runs - which is the number being measured.
	if _held != Vector2i.ZERO and _step_cooldown <= 0.0:
		try_move(_held)
		_step_cooldown = 0.16
		if not Input.is_anything_pressed():
			_held = Vector2i.ZERO

	var line := "%s  Ebene %d     HP %d/%d" % [
		tier.get("name", ""), depth, player.hp, player.max_hp]
	if player.shield > 0:
		line += " +%d Schild" % player.shield
	line += "     Stufe %d (%d/%d XP)     %d Gold" % [
		player.level, player.xp, player.xp_to_next, player.gold]
	# What is in your hands, by name, on a line of its own: a rarity
	# that never appears anywhere is a number nobody can notice.
	var gear := "%s +%d     %s +%d" % [
		player.weapon_name(), player.weapon_bonus(),
		player.armour_name(), player.armour_bonus()]
	# The running buffs, newest numbers first. The pygame build shows
	# five and counts the rest; there are only thirteen in total, and
	# a row that wraps over the map is worse than a truncated one.
	var chips: Array[String] = []
	for id in player.buffs:
		if chips.size() >= 5:
			chips.append("+%d" % (player.buffs.size() - 5))
			break
		chips.append("%s %d" % [Data.BUFFS[id]["name"], player.buffs[id]])
	if player.poison_turns > 0:
		chips.append("Gift %d" % player.poison_turns)
	if not chips.is_empty():
		gear += "     [%s]" % ", ".join(chips)
	_play_ui.get_node("stats").text = line
	_play_ui.get_node("gear").text = gear
	if _drink_button != null:
		if player.potions <= 0:
			_drink_button.text = "KEINE TRÄNKE"
		else:
			_drink_button.text = "%s (%d)" % [
				Data.potion_by_id(player.selected_potion)["name"],
				int(player.potion_counts.get(player.selected_potion, 0))]
	_play_ui.get_node("log").text = "\n".join(log_lines)
	_play_ui.get_node("fps").text = "%d fps   %.1f ms   %d draw calls" % [
		Engine.get_frames_per_second(),
		Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)]
