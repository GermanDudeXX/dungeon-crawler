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
var dead := false
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
var _held := Vector2i.ZERO
var _step_cooldown := 0.0


func _ready() -> void:
	rng.randomize()
	_build_world()
	_build_hud()
	new_run()


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
		for dir in [CLASS_DIR, "res://assets/monsters/", TILE_DIR]:
			var path: String = dir + name + ".png"
			if ResourceLoader.exists(path):
				_sprites[name] = load(path)
				break
		if not _sprites.has(name):
			_sprites[name] = load(CLASS_DIR + HERO_SPRITE + ".png")
	return _sprites[name]


# --- a run ----------------------------------------------------------------

func new_run() -> void:
	player = Entities.Player.new()
	depth = 1
	dead = false
	log_lines.clear()
	say("Du steigst in den Dungeon hinab.")
	new_level()


func new_level() -> void:
	tier = Data.tier_for(depth)
	var made := Dungeon.generate(MAP_W, MAP_H, rng)
	grid = made["grid"]
	rooms = made["rooms"]
	explored.clear()
	monsters.clear()
	items.clear()
	for node in _actor_nodes.values():
		node.queue_free()
	_actor_nodes.clear()
	for node in _item_nodes.values():
		node.queue_free()
	_item_nodes.clear()

	var start: Vector2i = rooms[0].center() if not rooms.is_empty() else Vector2i(1, 1)
	player.x = start.x
	player.y = start.y
	player.snap()
	stairs = rooms[-1].center() if not rooms.is_empty() else Vector2i(2, 2)
	_populate()
	recompute_fov()
	paint()


func _populate() -> void:
	var spawn_rooms: Array = rooms.slice(1) if rooms.size() > 1 else rooms
	for _i in Data.monster_count(depth):
		var cell: Variant = _free_cell(spawn_rooms)
		if cell == null:
			continue
		var monster := Entities.Monster.new(Data.pick_kind(depth, rng), tier["mult"])
		monster.x = cell.x
		monster.y = cell.y
		monster.snap()
		monsters.append(monster)

	for _i in range(2 + depth / 3):
		var cell: Variant = _free_cell(spawn_rooms)
		if cell == null:
			continue
		var roll := rng.randf()
		var kind := "gold"
		if roll < 0.35:
			kind = "potion"
		elif roll < 0.50:
			kind = "weapon"
		elif roll < 0.62:
			kind = "armour"
		items.append({"cell": cell, "kind": kind,
			"amount": rng.randi_range(5, 15 + depth * 3)})


func _free_cell(where: Array) -> Variant:
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
		if occupied(cell) or item_at(cell) != null:
			continue
		return cell
	return null


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
	if dead or step == Vector2i.ZERO:
		return
	var target := Vector2i(player.x + step.x, player.y + step.y)
	if step.x != 0:
		player.facing = 1 if step.x > 0 else -1

	var monster: Variant = monster_at(target)
	if monster != null:
		_attack_monster(monster)
	elif Dungeon.is_walkable(grid, target.x, target.y):
		player.x = target.x
		player.y = target.y
		_pick_up(target)
		if target == stairs:
			depth += 1
			say("Du steigst hinab - Ebene %d." % depth)
			new_level()
			return
	else:
		return

	enemy_turn()
	recompute_fov()
	paint()


func _attack_monster(monster) -> void:
	var damage: int = maxi(1, player.power() - monster.defense)
	monster.hp -= damage
	if monster.is_alive():
		say("Du triffst %s für %d." % [monster.display_name, damage])
		return
	say("%s stirbt." % monster.display_name)
	player.kills += 1
	if player.gain_xp(monster.xp_reward) > 0:
		say("Level auf! Du bist jetzt Stufe %d." % player.level)
	if _actor_nodes.has(monster):
		_actor_nodes[monster].queue_free()
		_actor_nodes.erase(monster)
	monsters.erase(monster)


func enemy_turn() -> void:
	var here := Vector2i(player.x, player.y)
	for monster in monsters.duplicate():
		if not monster.is_alive():
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
	player.hp -= damage
	say("%s trifft dich für %d." % [monster.display_name, damage])
	if player.hp <= 0:
		player.hp = 0
		dead = true
		say("Du stirbst auf Ebene %d. Tippe NEU." % depth)


func _pick_up(cell: Vector2i) -> void:
	var item: Variant = item_at(cell)
	if item == null:
		return
	var loot: Dictionary = item
	match loot["kind"]:
		"gold":
			player.gold += loot["amount"]
			say("%d Gold." % loot["amount"])
		"potion":
			player.potions += 1
			say("Ein Heiltrank.")
		"weapon":
			var best: int = mini(Data.WEAPONS.size() - 1, 1 + depth / 2)
			if best > player.weapon:
				player.weapon = best
				say("Neue Waffe: %s." % Data.WEAPONS[best]["name"])
			else:
				player.gold += 10
				say("Eine schlechtere Waffe - für 10 Gold verkauft.")
		"armour":
			var best: int = mini(Data.ARMOURS.size() - 1, 1 + depth / 3)
			if best > player.armour:
				player.armour = best
				say("Neue Rüstung: %s." % Data.ARMOURS[best]["name"])
			else:
				player.gold += 10
				say("Eine schlechtere Rüstung - für 10 Gold verkauft.")
	items.erase(loot)
	if _item_nodes.has(cell):
		_item_nodes[cell].queue_free()
		_item_nodes.erase(cell)


func drink() -> void:
	if dead or player.potions <= 0 or player.hp >= player.max_hp:
		return
	player.potions -= 1
	player.hp = mini(player.max_hp, player.hp + Data.POTION_HEAL)
	say("Du trinkst einen Heiltrank.")
	enemy_turn()
	paint()


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
	for monster in monsters:
		_place_monster(monster)

	_hero_node.position = Vector2(player.x, player.y) * TILE + Vector2(
		0, TILE - _hero_node.texture.get_height())
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
		node.texture = _sprite_for("flask_red" if item["kind"] == "potion" else "coin_anim_f0")
		node.centered = false
		node.z_index = 1
		add_child(node)
		_item_nodes[cell] = node
	var sprite: Sprite2D = _item_nodes[cell]
	sprite.position = Vector2(cell) * TILE
	sprite.visible = explored.has(cell)


func _place_monster(monster) -> void:
	if not _actor_nodes.has(monster):
		var node := Sprite2D.new()
		node.texture = _sprite_for(monster.sprite)
		node.centered = false
		node.z_index = 2
		add_child(node)
		_actor_nodes[monster] = node
	var sprite: Sprite2D = _actor_nodes[monster]
	sprite.position = Vector2(monster.x, monster.y) * TILE + Vector2(
		0, TILE - sprite.texture.get_height())
	sprite.visible = lit.has(monster.cell())


# --- the panel ------------------------------------------------------------

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	_hud = Control.new()
	_hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_hud)

	for name in ["stats", "fps", "log"]:
		var label := Label.new()
		label.name = name
		label.add_theme_font_size_override("font_size", 22)
		label.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
		_hud.add_child(label)
	_hud.get_node("stats").position = Vector2(14, 8)
	_hud.get_node("fps").position = Vector2(14, 36)

	var log_label: Label = _hud.get_node("log")
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

	var heal := Button.new()
	heal.text = "HEILEN"
	heal.custom_minimum_size = Vector2(size * 1.6, size * 0.8)
	heal.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	heal.position = Vector2(-pad - size * 1.6, -pad - size * 0.8)
	heal.add_theme_font_size_override("font_size", 28)
	heal.pressed.connect(drink)
	_hud.add_child(heal)

	var again := Button.new()
	again.text = "NEU"
	again.custom_minimum_size = Vector2(size, size * 0.6)
	again.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	again.position = Vector2(-pad - size, pad)
	again.add_theme_font_size_override("font_size", 26)
	again.pressed.connect(new_run)
	_hud.add_child(again)


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
	_hud.add_child(button)


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

	_hud.get_node("stats").text = "%s  Ebene %d     HP %d/%d     Stufe %d (%d/%d XP)     %d Gold     %d Tränke" % [
		tier.get("name", ""), depth, player.hp, player.max_hp,
		player.level, player.xp, player.xp_to_next, player.gold, player.potions]
	_hud.get_node("log").text = "\n".join(log_lines)
	_hud.get_node("fps").text = "%d fps   %.1f ms   %d draw calls" % [
		Engine.get_frames_per_second(),
		Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)]
