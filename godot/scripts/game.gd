## The playable slice: a dungeon, a hero that walks it, and a frame-time
## readout - enough to answer the one question this port exists to
## answer, which is what a frame costs on the phone when the GPU draws it
## instead of the CPU.
##
## The layout rules are taken from the pygame build so the two look the
## same: the wall frame comes from which sides face open floor, the floor
## variant from the same deterministic formula (never a random pick -
## that reshuffles the whole floor whenever anything repaints it).
extends Node2D

const MAP_W := 40
const MAP_H := 25
const TILE := 16          ## the art's own size; the view is scaled, not the art
const FLOOR_VARIANTS := 8
const FOV_RADIUS := 8

const TILE_DIR := "res://assets/tiles/"
const HERO := "res://assets/classes/knight_m_idle_anim_f0.png"

var _grid: Array = []
var _rooms: Array = []
var _explored := {}
var _visible_cells := {}
var _player := Vector2i.ZERO
var _rng := RandomNumberGenerator.new()

var _floor_layer: TileMapLayer
var _dim_layer: TileMapLayer
var _hero: Sprite2D
var _camera: Camera2D
var _readout: Label
var _tile_ids := {}       ## tile name -> source id in the shared TileSet
var _held := Vector2i.ZERO      ## direction a thumb is holding
var _step_cooldown := 0.0


func _ready() -> void:
	_rng.randomize()
	_build_world()
	_build_hud()
	_new_level()


# --- setting the scene ----------------------------------------------------

func _build_world() -> void:
	var tileset := _build_tileset()

	# Two layers of the same tiles: the lit one, and a dimmed one drawn
	# for remembered-but-not-visible ground. In the pygame build that
	# dimming meant a second, darker copy of every tile and a cache that
	# had to be repainted whenever the light moved; here it is one
	# modulate on a layer and the GPU does it per pixel, free.
	_floor_layer = TileMapLayer.new()
	_floor_layer.tile_set = tileset
	add_child(_floor_layer)

	_dim_layer = TileMapLayer.new()
	_dim_layer.tile_set = tileset
	_dim_layer.modulate = Color(0.45, 0.45, 0.55)
	_dim_layer.z_index = -1
	add_child(_dim_layer)

	var hero_texture: Texture2D = load(HERO)
	_hero = Sprite2D.new()
	_hero.texture = hero_texture
	_hero.centered = false
	_hero.z_index = 1
	add_child(_hero)

	_camera = Camera2D.new()
	# Whole tiles, like the pygame build ended up doing - but there for
	# the opposite reason. There it was to stop the whole screen changing
	# every frame; here it is only so the pixel art lands on whole pixels.
	_camera.position_smoothing_enabled = false
	_camera.zoom = Vector2(3, 3)
	add_child(_camera)


func _build_tileset() -> TileSet:
	var tileset := TileSet.new()
	tileset.tile_size = Vector2i(TILE, TILE)
	for name in _tile_names():
		var path := TILE_DIR + name + ".png"
		if not ResourceLoader.exists(path):
			continue
		var texture: Texture2D = load(path)
		# Only the single-cell art belongs in the tile set; the tall decor
		# (a column is three cells) is a sprite, not a tile.
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
	names.append_array(["wall_mid", "wall_left", "wall_right", "wall_top_mid"])
	return names


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)

	_readout = Label.new()
	_readout.position = Vector2(12, 8)
	_readout.add_theme_font_size_override("font_size", 22)
	_readout.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	layer.add_child(_readout)

	# A thumb-sized cross in the bottom-left corner, the same shape and
	# the same corner as the pygame build's. The viewport is 1280x720 and
	# the display scales it up, so these are bigger on the phone than the
	# numbers suggest - on a 2448-wide screen a 120px button lands at
	# about 230 physical pixels, well over Android's 48dp minimum.
	var pad := 28.0
	var size := 120.0
	var origin := Vector2(pad + size, -pad - size * 2.0)
	_dpad_button(layer, "^", origin + Vector2(0, -size), Vector2i(0, -1), size)
	_dpad_button(layer, "v", origin, Vector2i(0, 1), size)
	_dpad_button(layer, "<", origin + Vector2(-size, -size * 0.5), Vector2i(-1, 0), size)
	_dpad_button(layer, ">", origin + Vector2(size, -size * 0.5), Vector2i(1, 0), size)

	# One more floor, for looking at a different layout without leaving
	# the app - the slice has no stairs yet.
	var again := Button.new()
	again.text = "NEU"
	again.custom_minimum_size = Vector2(size * 1.4, size * 0.7)
	again.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	again.position = Vector2(-pad - size * 1.4, -pad - size * 0.7)
	again.add_theme_font_size_override("font_size", 28)
	again.pressed.connect(_new_level)
	layer.add_child(again)


func _dpad_button(layer: CanvasLayer, label: String, where: Vector2,
		step: Vector2i, size: float) -> void:
	var button := Button.new()
	button.text = label
	button.custom_minimum_size = Vector2(size, size)
	button.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	button.position = where
	button.add_theme_font_size_override("font_size", 40)
	# Held, not tapped: walking is what the frame rate has to be measured
	# on, and tapping once per step measures nothing.
	button.button_down.connect(func() -> void: _held = step)
	button.button_up.connect(func() -> void:
		if _held == step:
			_held = Vector2i.ZERO)
	layer.add_child(button)


# --- the level ------------------------------------------------------------

func _new_level() -> void:
	var made := Dungeon.generate(MAP_W, MAP_H, _rng)
	_grid = made["grid"]
	_rooms = made["rooms"]
	_explored.clear()
	_player = _rooms[0].center() if not _rooms.is_empty() else Vector2i(1, 1)
	_recompute_fov()
	_paint()


func _recompute_fov() -> void:
	# Same shape as fov.py's answer without its shadowcasting: everything
	# within the radius that is not behind a wall on the straight line to
	# it. Good enough for the slice; the real one ports with the rest.
	_visible_cells.clear()
	for dy in range(-FOV_RADIUS, FOV_RADIUS + 1):
		for dx in range(-FOV_RADIUS, FOV_RADIUS + 1):
			var cell := _player + Vector2i(dx, dy)
			if Vector2(dx, dy).length() > FOV_RADIUS:
				continue
			if _line_is_clear(_player, cell):
				_visible_cells[cell] = true
				_explored[cell] = true


func _line_is_clear(from: Vector2i, to: Vector2i) -> bool:
	var steps := maxi(absi(to.x - from.x), absi(to.y - from.y))
	if steps == 0:
		return true
	for i in range(1, steps):
		var at := Vector2(from) + (Vector2(to - from) * float(i) / float(steps))
		var cell := Vector2i(roundi(at.x), roundi(at.y))
		if cell != from and cell != to and not Dungeon.is_walkable(_grid, cell.x, cell.y):
			return false
	return true


func _paint() -> void:
	# The whole map, once. Not per frame and not per step: a TileMapLayer
	# hands the GPU a mesh and the GPU redraws it every frame for
	# nothing, which is the entire reason this port exists. The pygame
	# build had to keep a painted copy of the map in memory and patch it
	# cell by cell to avoid exactly this work.
	_floor_layer.clear()
	_dim_layer.clear()
	for y in MAP_H:
		for x in MAP_W:
			var cell := Vector2i(x, y)
			if not _explored.has(cell):
				continue
			var name := _tile_for(x, y)
			if name == "" or not _tile_ids.has(name):
				continue
			var layer := _floor_layer if _visible_cells.has(cell) else _dim_layer
			layer.set_cell(cell, _tile_ids[name], Vector2i.ZERO)
	_place_hero()


func _tile_for(x: int, y: int) -> String:
	if _grid[y][x] != Dungeon.WALL:
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
	return ""            ## solid rock between rooms - deliberately nothing


func _is_wall(x: int, y: int) -> bool:
	if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
		return true
	return _grid[y][x] == Dungeon.WALL


func _place_hero() -> void:
	# The sprite is taller than its cell and stands in it, so it hangs
	# upwards - same as the pygame build.
	var foot := Vector2(_player) * TILE
	_hero.position = Vector2(foot.x, foot.y + TILE - _hero.texture.get_height())
	_camera.position = Vector2(_player) * TILE + Vector2(TILE, TILE) * 0.5


# --- playing --------------------------------------------------------------

func move(step: Vector2i) -> void:
	var target := _player + step
	if not Dungeon.is_walkable(_grid, target.x, target.y):
		return
	_player = target
	_recompute_fov()
	_paint()


func _process(delta: float) -> void:
	# Held keys and held thumbs both walk at a steady rate rather than
	# as fast as frames happen - otherwise the hero's speed would
	# depend on the frame rate, which is the very thing being measured.
	_step_cooldown -= delta
	if _held == Vector2i.ZERO:
		if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
			_held = Vector2i(1, 0)
		elif Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
			_held = Vector2i(-1, 0)
		elif Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
			_held = Vector2i(0, 1)
		elif Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
			_held = Vector2i(0, -1)
	if _held != Vector2i.ZERO and _step_cooldown <= 0.0:
		move(_held)
		_step_cooldown = 0.14
		if not Input.is_anything_pressed():
			_held = Vector2i.ZERO

	# Frame time, not frame rate: the pygame build's readout measured the
	# gap between draws, which on a turn-based game that only redraws on
	# change reads 500ms while standing still and means nothing. This is
	# the real cost of the frame.
	var ms := Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
	var draw := Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
	_readout.text = "%d fps   %.1f ms   %d draw calls   %dx%d" % [
		Engine.get_frames_per_second(), ms, draw,
		get_viewport().get_visible_rect().size.x,
		get_viewport().get_visible_rect().size.y,
	]
