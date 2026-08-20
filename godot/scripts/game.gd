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
const MINIMAP_SCALE := 4
# How much dungeon should be on screen at once, in tiles across.
const TILES_ACROSS := 30.0

# How long one step takes. The glide between tiles is given exactly
# this long, so a held direction produces one continuous movement
# instead of step, wait, step - that pause is most of what reads as
# "stuck to a grid", even though the sprites were already sliding.
const GAUGE_W := 340.0           ## the health and experience bars
const GAUGE_H := 26.0
const BOSS_W := 520.0
const DOOR_POCKET := 4           ## fewer floor tiles than this behind a door is nothing
## Seconds between two shots fired on their own.
##
## The turn cooldown cannot do this job: it counts turns, a shot is a
## turn, and standing still makes no turns at all - so the hero fired
## once, the cooldown stuck at one, and nothing ever cleared it. It
## looked exactly like a feature that does nothing. This is the same
## idea in real time, a little slower than walking.
const SHOT_TIME := 0.30
const STEP_TIME := 0.14
# How long a held direction waits before it starts walking by itself.
## How close together the healing ticks may ever get. Below this, more
## of the gift means bigger ticks instead of faster ones.
const REGEN_FLOOR := 3
const REPEAT_DELAY := 0.34

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
var up_stairs := Vector2i.ZERO   ## where you came in, and the way back
var depth := 1
var tier := {}
var log_lines: Array[String] = []
var traps := {}                 ## cell -> trap id
var chest = null                ## {cell, mimic, opened}
var shops: Array = []           ## {cell, kind}
var stairs_locked := false
var quest := {}                  ## this floor's optional goal
var floors := {}                 ## depth -> the floor as it was left
var drank_here := false          ## a flask was opened on this floor
var hurt_here := false           ## something got through on this floor
var theme := {}                  ## this floor's themed room, if it has one
var doors := {}                  ## cell -> true when open
var webs := {}                   ## cell -> a widow's web, walked into once
var hazards := {}               ## cell -> a standing danger, in plain sight
var decor := {}                  ## cell -> a sprite that is only scenery
var captive = null               ## somebody chained up down here
var shrine = null                ## the cell holding this floor's shrine, or null
var shop_open = null            ## the shop the hero is standing in
## Whether the run is over.
##
## Written from seven different places - poison, bleeding, a trap, a
## hazard, an explosion, an arrow, a swing - and every one of them says
## the same thing. A property rather than a plain flag, so the one case
## that has to be different can be handled once instead of seven times:
## when a *guest* falls, the run does not end. Their hero is put back on
## its feet beside the host with a quarter of its health, because one
## person's bad step should not close the dungeon on everybody.
var _run_over := false
var dead: bool:
	get:
		return _run_over
	set(value):
		# Not "whose turn is it" but "who fell": a monster picks its own
		# target now, so the one who dies is often not the one who moved.
		if value and net != null and net.hosting \
				and party.has(1) and player != party[1]:
			_pick_guest_up()
			return
		_run_over = value
var hero_class := Data.DEFAULT_CLASS
var difficulty := Data.DEFAULT_DIFFICULTY
var choosing := true            ## the title screen is up, nothing moves
var rng := RandomNumberGenerator.new()

var _floor_layer: TileMapLayer
var _dim_layer: TileMapLayer
var _torch: PointLight2D
var _stairs_light: PointLight2D
var _flicker := 0.0
var _gloom: CanvasModulate
var _vignette: ColorRect
var _tile_ids := {}
var _sprites := {}
var _actor_nodes := {}
var _item_nodes := {}
var net: Net                     ## the door to the other players
var party := {}                  ## host only: peer id -> that peer's hero
var _acting_peer := 1            ## whose action the host is running right now
var _net_ids := 0                ## the last number handed to a monster
var _mates: Array = []           ## guest only: the other heroes, as plain data
var _mate_nodes := {}            ## and their sprites
var _by_net_id := {}             ## guest only: number -> the monster it belongs to
var _party_panel: PanelContainer ## hosting, joining, and who is here
var _party_where: Label
var _party_note: Label
var _party_list: Label
var _party_trail: Label
var _party_again: HBoxContainer  ## the addresses joined before
var _party_heroes: HBoxContainer ## picking a hero as a guest
var _party_field: LineEdit
var _party_host: Button
var _party_join: Button
var _party_leave: Button
var _hero_node: Sprite2D
var _camera: Camera2D
var _hud: Control
var audio: Audio
var settings := Settings.DEFAULTS.duplicate()
var earned := {}                 ## achievements already won
var known := {}                  ## the bestiary, kind by kind
var scrolls_read := 0            ## across all runs, for one of them
var potion_free := true          ## no potion drunk this run yet
var _play_ui: Control            ## stats, log and the pad - hidden on the title
var _shop_panel: PanelContainer
var _shop_title: Label
var _shop_buttons: Array = []
var _title_panel: PanelContainer
var _continue_button: Button
var _dead_panel: PanelContainer
var _dead_text: Label
var _sound_button: Button
var _flash_button: Button
var _volume_label: Label
var _diagonal_button: Button
var _corner_buttons: Array = []  ## the four diagonal keys of the pad
var _level_panel: PanelContainer ## how hard, asked once, after the hero
var _picked_class := ""          ## chosen, waiting for a level of play
var _stats_panel: PanelContainer   ## what the hero actually adds up to
var _options_panel: PanelContainer ## the title screen, one level down
var _info_panel: PanelContainer
var _info_record: Label
var _rest_button: Button         ## waits, or hits whatever is in reach
var _attack_panel: PanelContainer ## the one-time explanation for that
var _attack_step := Vector2i.ZERO ## the blow the explanation is holding back
var _buff_chips: Array = []      ## one plate per running buff
var _buff_peak := {}             ## the longest each buff has been, to draw a share of
var _stats_text: Label
var _setup_panel: PanelContainer  ## the Windows "shall I move in?" offer
var _setup_text: Label
var _music_label: Label
var _pad_button: Button
var _record_label: Label
var _hint_label: Label
var _update_button: Button
var _update_label: Label
var updater: Updater
var _update_url := ""
var _update_file := ""           ## the downloaded APK, once it is here
var _update_busy := false
var _awards_panel: PanelContainer
var _awards_list: VBoxContainer
var _kin_panel: PanelContainer
var _kin_list: VBoxContainer
var _drink_button: Button
var _shoot_button: Button
var _hp_frame: ColorRect         ## the gauges, top left
var _hp_ghost: ColorRect
var _hp_fill: ColorRect
var _hp_guard: ColorRect
var _hp_text: Label
var _xp_fill: ColorRect
var _boss_frame: ColorRect       ## and the one across the top, for a boss
var _boss_track: ColorRect
var _boss_fill: ColorRect
var _boss_text: Label
var _pause_panel: PanelContainer
var _pause_sound: Button
var _pause_music: Button
var _pause_flash: Button
var _pause_pad: Button
var _pause_stats: Button
var _pause_auto: Button
var _bag_panel: PanelContainer
var _bag_list: VBoxContainer
var _bag_stats: Label
var _flash: ColorRect
var _minimap: TextureRect
var _banner: Label
var _banner_fade: Tween
var _announce: Array = []        ## what to shout once the floor is drawn
var _minimap_drawn := -1
var _minimap_at := Vector2i(-1, -1)
var _seen_items := {}            ## loot that has been in the light once
var _shadows := {}               ## sprite -> the smudge it stands on
var _shadow_art: Texture2D
var _art_rects := {}             ## texture -> the part of it that is not empty
var _stairs_mark: Line2D          ## the frame drawn round the way down
var _gliding := {}               ## sprite -> where it is walking to
var _camera_to := Vector2.ZERO
var _scroll_buttons: Array = []
var _perk_panel: PanelContainer
var _perk_buttons: Array = []
var perk_choices: Array = []      ## the three on offer right now
var _music_button: Button
var _held := Vector2i.ZERO
var _stepped := Vector2i.ZERO
var _pad_held := false           ## a direction button on the screen is under a finger    ## the direction the last step went
var _stick: Stick
var _pad_buttons: Array[Button] = []
var _haste_flip := false
var _step_cooldown := 0.0
var _shot_pause := 0.0           ## seconds until the next shot on its own


func _ready() -> void:
	rng.randomize()
	settings = Settings.read()
	earned = Achievements.read()
	known = Bestiary.read()
	updater = Updater.new()
	add_child(updater)
	updater.checked.connect(_update_answer)
	updater.fetched.connect(_update_fetched)
	# Named, and named the same on every machine: a remote call finds its
	# way by node path, so host and guest have to agree on where this
	# thing lives.
	net = Net.new()
	net.name = "Net"
	net.game = self
	add_child(net)
	audio = Audio.new()
	add_child(audio)
	audio.enabled = settings["sound"]
	audio.set_volume(float(settings.get("volume", 0.75)))
	audio.set_music_volume(float(settings.get("music_volume", 0.55)))
	audio.music_enabled = settings["music"]
	difficulty = str(settings.get("difficulty", Data.DEFAULT_DIFFICULTY))
	_build_world()
	_build_light()
	_build_hud()
	# A run starts behind the title screen, not in front of it: the
	# class is picked before the first floor exists, so the starting
	# kit is right from the first turn.
	new_run()
	show_title()
	# On Windows, once, before anything else is touched: the game is a
	# single file sitting wherever it was downloaded, and it can move into
	# a folder of its own if that is wanted.
	if Setup.worth_offering() and not settings.get("install_asked", false):
		# In front of the title screen, which is opaque and was built after
		# this one - so without moving it the offer sits behind a solid
		# panel and cannot be seen, let alone pressed.
		_setup_panel.get_parent().move_to_front()
		_setup_panel.visible = true


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
	_fit_camera()
	get_viewport().size_changed.connect(_fit_camera)
	add_child(_camera)


## Sets the zoom so that roughly the same slice of the dungeon is on
## screen whatever shape the screen is.
##
## A fixed zoom means a phone in landscape sees the entire forty-tile
## map at once while a small window sees a keyhole. Aiming at a number
## of tiles instead keeps the sprites the size they were drawn to be.
func _fit_camera() -> void:
	if _camera == null:
		return
	var wide := float(get_viewport().get_visible_rect().size.x)
	var zoom := clampf(wide / (TILES_ACROSS * float(TILE)), 1.6, 4.0)
	_camera.zoom = Vector2(zoom, zoom)

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
		"floor_stairs", "floor_ladder"])
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
	floors.clear()
	potion_free = true
	player = Entities.Player.new(hero_class, difficulty)
	player.auto_shoot = settings.get("auto_shoot", true)
	depth = 1
	dead = false
	log_lines.clear()
	say("Du steigst in den Dungeon hinab.")
	new_level()


## Puts a saved run back on its floor. Everything is rebuilt from the
## file rather than regenerated, so the player carries on standing where
## they stood, on the map they had uncovered.
## Puts one floor into place from plain data.
##
## The save file and a remembered floor hold the same shape, so a floor
## read from disk and a floor walked back into go through exactly one
## piece of code. Two would be two places to forget a field in.
func _apply_floor(save: Dictionary) -> void:
	# The log belongs to the run, not to a floor: a remembered floor has
	# none, and restoring one would rewind what the hero has been told.
	depth = int(save["depth"])
	tier = Data.tier_for(depth)
	audio.play_music(tier.get("music", ""))

	# JSON has no integers, only floats, and no Vector2i at all - every
	# number and every cell has to be put back into the type the game
	# expects, or the first comparison against a live value fails.
	rooms.clear()
	for entry in save.get("rooms", []):
		rooms.append(Dungeon.Room.new(int(entry[0]), int(entry[1]),
			int(entry[2]) - int(entry[0]), int(entry[3]) - int(entry[1])))
	# Built fresh and then assigned, never cleared in place: the array
	# being replaced may be the one a remembered floor is holding on to.
	var rebuilt: Array = []
	for row in save["grid"]:
		var line: Array = []
		for value in row:
			line.append(int(value))
		rebuilt.append(line)
	grid = rebuilt
	stairs = Vector2i(int(save["stairs"][0]), int(save["stairs"][1]))
	var up: Variant = save.get("up_stairs", null)
	up_stairs = Vector2i(int(up[0]), int(up[1])) if up != null else Vector2i(player.x, player.y)
	stairs_locked = bool(save["stairs_locked"])
	# Rebuilt field by field: JSON has no integers, so a theme read back
	# from a file has 2.0 where it had 2. Nothing breaks - every use
	# goes through int() - but the run is then not quite the run that
	# was saved, and a comparison of the two says so.
	quest = {}
	var order: Dictionary = save.get("quest", {})
	if not order.is_empty():
		quest = {"id": str(order["id"]), "name": str(order["name"]),
			"done": bool(order["done"]), "gold": int(order["gold"]),
			"potion": int(order["potion"])}
	drank_here = bool(save.get("drank_here", false))
	hurt_here = bool(save.get("hurt_here", false))
	theme = {}
	var stored: Dictionary = save.get("theme", {})
	if not stored.is_empty():
		theme = {"id": str(stored["id"]), "name": str(stored["name"]),
			"x1": int(stored["x1"]), "y1": int(stored["y1"]),
			"x2": int(stored["x2"]), "y2": int(stored["y2"]),
			"seen": bool(stored["seen"])}
	doors = {}
	for entry in save.get("doors", []):
		doors[Vector2i(int(entry[0]), int(entry[1]))] = bool(entry[2])
	webs = {}
	for entry in save.get("webs", []):
		webs[Vector2i(int(entry[0]), int(entry[1]))] = true
	hazards = {}
	for entry in save.get("hazards", []):
		hazards[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	decor = {}
	for entry in save.get("decor", []):
		decor[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	captive = null
	if save.get("captive", null) != null:
		captive = Vector2i(int(save["captive"][0]), int(save["captive"][1]))
	shrine = null
	if save.get("shrine", null) != null:
		shrine = Vector2i(int(save["shrine"][0]), int(save["shrine"][1]))

	_clear_level_nodes()
	explored = {}
	for cell in save["explored"]:
		explored[Vector2i(int(cell[0]), int(cell[1]))] = true
	traps = {}
	for entry in save["traps"]:
		traps[Vector2i(int(entry[0]), int(entry[1]))] = str(entry[2])
	items = []
	for entry in save["items"]:
		items.append({"cell": Vector2i(int(entry["x"]), int(entry["y"])),
			"kind": str(entry["kind"]), "amount": int(entry["amount"]),
			"potion": str(entry.get("potion", "")),
			"scroll": str(entry.get("scroll", ""))})
	shops = []
	for entry in save["shops"]:
		var stock: Array = []
		for id in entry.get("stock", []):
			stock.append(str(id))
		shops.append({"cell": Vector2i(int(entry["x"]), int(entry["y"])),
			"kind": str(entry["kind"]), "stock": stock,
			"scroll": str(entry.get("scroll", ""))})
	chest = null
	if save["chest"] != null:
		var c: Dictionary = save["chest"]
		chest = {"cell": Vector2i(int(c["x"]), int(c["y"])),
			"mimic": bool(c["mimic"]), "opened": bool(c["opened"]),
			"gone": bool(c.get("gone", false)),
			"guarded": bool(c.get("guarded", false))}

	monsters = []
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
		monster.is_keeper = bool(entry.get("keeper", false))
		monster.burn_turns = int(entry.get("burn", 0))
		monster.slow_turns = int(entry.get("slow", 0))
		monster.stun_turns = int(entry.get("stun", 0))
		monster.regen = int(entry.get("regen", 0))
		monster.weaken_turns = int(entry.get("weaken", 0))
		monster.venom_turns = int(entry.get("venom", 0))
		monster.bleed_turns = int(entry.get("bleed", 0))
		monster.is_elite = bool(entry.get("elite", false))
		# Without this a half-slime that was saved comes back able to
		# split twice more.
		monster.generation = int(entry.get("generation", 0))
		monster.summoned = int(entry.get("summoned", 0))
		monster.afraid = int(entry.get("afraid", 0))
		monster.enraged = bool(entry.get("enraged", false))
		monster.snap()
		monsters.append(monster)


func load_run() -> bool:
	var data: Variant = Save.read()
	if data == null:
		return false
	var save: Dictionary = data

	floors.clear()
	for level in save.get("floors", {}):
		floors[int(level)] = save["floors"][level]
	hero_class = save["class"]
	player = Entities.Player.new(hero_class, difficulty)
	player.auto_shoot = settings.get("auto_shoot", true)
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
	player.webbed = int(p.get("webbed", 0))
	# Always zero: shooting runs on the clock now, and a one left in an
	# older save would jam the bow for good.
	player.shot_cooldown = 0
	player.bonus_crit = float(p.get("bonus_crit", 0.0))
	player.damage_reduction = float(p.get("damage_reduction", 0.0))
	player.gold_mult = float(p.get("gold_mult", 1.0))
	player.xp_mult = float(p.get("xp_mult", 1.0))
	player.potion_mult = float(p.get("potion_mult", 1.0))
	player.scholar = float(p.get("scholar", 0.0))
	player.regen_interval = int(p.get("regen_interval", 0))
	player.regen_power = maxi(1, int(p.get("regen_power", 1)))
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

	_apply_floor(save)
	dead = false
	log_lines.clear()
	for line in save["log"]:
		log_lines.append(str(line))
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
	if what == NOTIFICATION_WM_GO_BACK_REQUEST and close_topmost():
		return
	if what == NOTIFICATION_WM_CLOSE_REQUEST \
			or what == NOTIFICATION_APPLICATION_PAUSED \
			or what == NOTIFICATION_WM_GO_BACK_REQUEST:
		save_run()


## Puts the current floor aside so it can be walked back into.
##
## A dungeon whose floors are re-rolled every time you use a staircase
## is not a place, it is a slot machine: the corridor you cleared is
## gone, the chest you left behind never existed, and going back up is
## pointless by construction. Everything that makes up a floor is kept
## as it was left - including the dead, who stay dead.
func _stash_floor() -> void:
	if grid.is_empty():
		return
	# Kept in the same plain form the save file uses, so a floor survives
	# closing the game as readily as it survives a staircase.
	floors[depth] = Save.floor_data(self)


## Walks back into a floor that has been here before. `from_below` is
## true when the hero climbed up into it, which is the one thing the
## snapshot cannot know: it decides which staircase they arrive on.
func _restore_floor(from_below: bool) -> void:
	_apply_floor(floors[depth])
	audio.play_music(tier.get("music", ""))
	# Arriving from below means stepping out of the down staircase; from
	# above, out of the one that leads up.
	var arrival: Vector2i = stairs if from_below else up_stairs
	player.x = arrival.x
	player.y = arrival.y
	player.snap()
	recompute_fov()
	paint()
	say("Zurück auf Ebene %d." % depth)
	save_run()


func new_level(from_below := false) -> void:
	# Been here before? Then it is still the floor it was.
	if floors.has(depth):
		_restore_floor(from_below)
		return

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
	# The ranger shares the rogue's painting - there are three hero
	# sprites and four classes - so it wears its own colour to tell the
	# two apart at a glance.
	_hero_node.modulate = Data.class_by_id(player.hero_class).get("shade", Color.WHITE)
	var start: Vector2i = rooms[0].center() if not rooms.is_empty() else Vector2i(1, 1)
	player.x = start.x
	player.y = start.y
	player.snap()
	stairs = rooms[-1].center() if not rooms.is_empty() else Vector2i(2, 2)
	# The way back up is where you came in. Going up is not a way to
	# escape a bad floor - the floor above is regenerated too - it is
	# there so a staircase reads as a staircase in both directions.
	up_stairs = start
	_seen_items.clear()
	drank_here = false
	hurt_here = false
	_populate()
	recompute_fov()
	paint()
	# The banner waits for the floor to be drawn: shouting about a boss
	# over the last floor's picture reads as belonging to that one.
	if not _announce.is_empty():
		banner(_announce[0], _announce[1])
		_announce.clear()
	elif depth > 1 and Data.tier_for(depth)["id"] != Data.tier_for(depth - 1)["id"]:
		banner(tier.get("name", ""), tier.get("tint", Color.WHITE))

	_set_quest()

	# The floor is the natural checkpoint: it is the one moment where
	# the whole level is settled and nothing is half-resolved.
	save_run()


## Sprites belong to the floor they were made for; a new floor gets
## new ones. Left behind, they hang in mid-air over the next map.
func _clear_level_nodes() -> void:
	for shadow in _shadows.values():
		if is_instance_valid(shadow):
			shadow.queue_free()
	_shadows.clear()
	for node in _actor_nodes.values():
		node.queue_free()
	_actor_nodes.clear()
	for node in _item_nodes.values():
		node.queue_free()
	_item_nodes.clear()


func _populate() -> void:
	var spawn_rooms: Array = rooms.slice(1) if rooms.size() > 1 else rooms
	# Counted, not looped: a swarm is part of the floor's allowance, not
	# an extra on top of it. Adding the pack members outside the count
	# put eight monsters on a floor meant to hold three, and the first
	# floor stopped being a first floor.
	var wanted: int = Data.monster_count(depth)
	var placed := 0
	var tries := 0
	while placed < wanted and tries < wanted * 4:
		tries += 1
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
		placed += 1 + _swarm_around(monster, cell, wanted - placed - 1)

	# The boss holds the key, so it is placed first and far from the
	# hero - a floor you have to finish rather than cross.
	stairs_locked = false
	if Data.has_boss(depth):
		var boss_cell = _free_cell([rooms[-1]] if not rooms.is_empty() else spawn_rooms)
		if boss_cell != null:
			var boss := Entities.Monster.new(Data.pick_boss_kind(depth, rng), tier["mult"], difficulty)
			boss.x = boss_cell.x
			boss.y = boss_cell.y
			boss.max_hp = int(boss.max_hp * Data.BOSS_HP_MULT)
			boss.hp = boss.max_hp
			boss.power = int(boss.power * Data.BOSS_POWER_MULT)
			boss.xp_reward *= 3
			boss.is_boss = true
			boss.awake = true
			boss.display_name = "%s-König" % boss.display_name
			# The floor everything has been building towards. Not a wall -
			# the run can go deeper afterwards - but the one fight the
			# whole descent is preparation for.
			if depth == Data.SUPERBOSS_LEVEL:
				boss.max_hp = int(boss.max_hp * Data.SUPERBOSS_MULT)
				boss.hp = boss.max_hp
				boss.power = int(boss.power * Data.SUPERBOSS_MULT)
				boss.xp_reward *= 3
				boss.display_name = "Der Herr der Tiefe"
			boss.snap()
			monsters.append(boss)
			_note_kind(boss.kind, "seen")
			stairs_locked = true
			if depth == Data.SUPERBOSS_LEVEL:
				_announce = ["Der Herr der Tiefe erwartet dich", Color(0.90, 0.25, 0.22)]
			else:
				_announce = ["Ein Boss hält den Schlüssel", Color(0.90, 0.45, 0.25)]

	# A mini-boss on the floors between real bosses, so the gap has a
	# landmark in it. It does not lock the stairs - it is a fight you
	# may walk around, not one you have to win.
	if Data.has_mini_boss(depth):
		var mini_cell = _free_cell(spawn_rooms)
		if mini_cell != null:
			var mini := Entities.Monster.new(Data.pick_boss_kind(depth, rng), tier["mult"], difficulty)
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
				_announce = ["Eine Schatzkammer, gut bewacht", Color(1.0, 0.84, 0.30)]
				items.append({"cell": hoard, "kind": "gold",
					"amount": rng.randi_range(30, 60 + depth * 5)})

	# A chest, which is sometimes not a chest at all.
	if depth >= 2 and rng.randf() < 0.55:
		var chest_cell = _free_cell(spawn_rooms)
		if chest_cell != null:
			chest = {"cell": chest_cell, "mimic": depth >= 3 and rng.randf() < 0.3,
				"opened": false, "guarded": false}
			# Often there is something standing over it. The chest will not
			# open while it lives - a prize you have to earn rather than
			# one you have to find.
			if depth >= Data.TREASURE_MIN_LEVEL and rng.randf() < Data.TREASURE_CHANCE:
				var post: Variant = _free_cell(spawn_rooms)
				if post != null:
					var keeper := Entities.Monster.new(Data.pick_kind(depth, rng),
						tier["mult"] * Data.TREASURE_GUARD_MULT, difficulty)
					keeper.x = post.x
					keeper.y = post.y
					keeper.is_keeper = true
					keeper.awake = true
					keeper.display_name = "Wächter (%s)" % keeper.display_name
					keeper.snap()
					monsters.append(keeper)
					chest["guarded"] = true

	# Doors on the ways into rooms, before anything else is put down: a
	# shut door is a wall for the moment, and every later placement asks
	# what is reachable.
	_hang_doors(spawn_rooms)

	# Standing hazards: visible from the moment the tile is, so they are
	# something to walk around rather than something to discover. That is
	# the whole difference from a trap.
	webs.clear()
	hazards.clear()
	var hazard_kinds: Array = Data.hazards_for(depth)
	if not hazard_kinds.is_empty():
		for room in spawn_rooms:
			if rng.randf() >= Data.HAZARD_CHANCE_PER_ROOM:
				continue
			var kind: String = hazard_kinds[rng.randi() % hazard_kinds.size()]
			for _patch in rng.randi_range(1, 3):
				var patch: Variant = _free_cell([room])
				if patch != null:
					hazards[patch] = kind

	# Scenery. Most of it is only something to look at, but a crate or a
	# column is a solid object and reads as one, so those are walls. A
	# wall dropped in a one-tile corridor can seal the stairs off, so each
	# one is put down, checked, and taken back if the floor stopped being
	# whole.
	decor.clear()
	for _piece in range(4 + depth / 2):
		# Each piece gets a few tries rather than one. A banner that came
		# up for a spot with no wall behind it used to cost the whole slot,
		# and floors quietly lost half their scenery to rules about where
		# scenery may not go.
		for _attempt in 6:
			var spot: Variant = _free_cell(spawn_rooms)
			if spot == null:
				break
			var piece: String = DECOR[rng.randi() % DECOR.size()]
			# A banner hangs on a wall. Dropped on open floor it is a flag
			# lying in the middle of a room, which is what it looked like -
			# so one only goes down where there is a wall behind it to hang
			# from, and it is drawn half a tile up, against that wall.
			if piece.begins_with("wall_banner") \
					and Dungeon.is_walkable(grid, spot.x, spot.y - 1):
				continue
			# And nothing solid in a doorway. A crate in front of a door
			# does not seal the floor off - there is always a way round -
			# but it does turn the door into furniture, and standing in a
			# doorway is the one place scenery has no business being.
			if piece in Data.BLOCKING_DECOR and _beside_a_door(spot):
				continue
			decor[spot] = piece
			if piece in Data.BLOCKING_DECOR and _seals_something():
				decor.erase(spot)
				continue
			break


	# Somebody chained up. Placed like the shrine - only where the hero
	# can actually walk - because a prisoner nobody can reach is just a
	# prisoner.
	captive = null
	if depth >= Data.CAPTIVE_MIN_LEVEL and rng.randf() < Data.CAPTIVE_CHANCE:
		captive = _free_cell(spawn_rooms, reachable_from(Vector2i(player.x, player.y)))

	# A shrine, at most one, stepped on like a trap - but this one can
	# be worth stepping on.
	shrine = null
	if depth >= 2 and rng.randf() < Data.SHRINE_CHANCE:
		# Only where the hero can actually walk: the crates are already
		# standing by now, and one of them may have closed a room.
		shrine = _free_cell(spawn_rooms, reachable_from(Vector2i(player.x, player.y)))

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
			# And one scroll, so gold has something to buy that is not a
			# flask - a merchant who only sells potions is a merchant you
			# stop visiting once you have eight.
			var paper: String = Data.SCROLLS[rng.randi() % Data.SCROLLS.size()]["id"]
			shops.append({"cell": spot, "kind": "merchant", "stock": stock,
				"scroll": paper})
	if depth >= 4 and rng.randf() < 0.3:
		var spot = _shopkeeper_spot(spawn_rooms)
		if spot != null:
			shops.append({"cell": spot, "kind": "smith", "stock": []})

	# Everything left goes only where the hero can actually reach: the
	# shopkeepers are standing by now, and each of them is a tile that
	# never opens. The themed room needs this as much as the ordinary
	# loot does - a library nobody can walk into is a library of
	# scrolls nobody ever reads.
	var blocked := {}
	for shop in shops:
		blocked[shop["cell"]] = true
	var open_cells := reachable_from(Vector2i(player.x, player.y), blocked)

	_furnish_theme(spawn_rooms, open_cells)

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


## Rats and bats do not turn up alone. The rest of the pack goes beside
## the first one rather than anywhere on the floor, so a swarm reads as
## a swarm instead of as five separate rats.
func _swarm_around(monster, cell: Vector2i, room_left: int) -> int:
	var info: Dictionary = Data.MONSTERS[monster.kind]
	if not info.has("swarms") or room_left <= 0:
		return 0
	var span: Array = info["swarms"]
	var count: int = mini(room_left,
		rng.randi_range(int(span[0]), int(span[1])) - 1)
	var made := 0
	var spots: Array[Vector2i] = []
	for dy in range(-2, 3):
		for dx in range(-2, 3):
			spots.append(cell + Vector2i(dx, dy))
	for spot in spots:
		if count <= 0:
			return made
		if not Dungeon.is_walkable(grid, spot.x, spot.y) or blocks(spot):
			continue
		if occupied(spot) or taken(spot) or spot == Vector2i(player.x, player.y):
			continue
		var friend := Entities.Monster.new(monster.kind, tier["mult"], difficulty)
		friend.x = spot.x
		friend.y = spot.y
		friend.snap()
		monsters.append(friend)
		count -= 1
		made += 1
	return made


## Whether the floor, as it stands right now, has cut something off from
## the hero. Asked after every solid piece of scenery is put down.
##
## Checking only the stairs was not enough: a crate can seal the chest
## into a dead-end and leave the floor perfectly finishable, which is
## how a run loses its treasure without anything looking wrong.
func _seals_something(blocked := {}) -> bool:
	# Every shopkeeper already standing counts as a wall, always. A
	# crate on its own seals nothing and a keeper on its own seals
	# nothing - the two together seal a room, and asking about only
	# one of them at a time never finds that.
	var shut := blocked.duplicate()
	for shop in shops:
		shut[shop["cell"]] = true
	var open_cells := reachable_from(Vector2i(player.x, player.y), shut)
	if not open_cells.has(stairs):
		return true
	if chest != null and not chest.get("gone", false) \
			and not open_cells.has(chest["cell"]):
		return true
	if shrine != null and not open_cells.has(shrine):
		return true
	if captive != null and not open_cells.has(captive):
		return true
	# The boss above all: it holds the key to the stairs, so a crate
	# that walls it in ends the run on this floor. Ordinary monsters
	# may be shut away - that is just a fight you get to skip.
	for monster in monsters:
		if monster.is_boss and not open_cells.has(monster.cell()):
			return true
	# A keeper you cannot walk up to is a shop that does not exist.
	for shop in shops:
		if shut.has(shop["cell"]) and not blocked.has(shop["cell"]):
			continue
		if not open_cells.has(shop["cell"]):
			return true
	for item in items:
		if not open_cells.has(item["cell"]):
			return true
	# The boss holds the key to the stairs; walling it in ends the
	# run on this floor.
	for monster in monsters:
		if monster.is_boss and not open_cells.has(monster.cell()):
			return true
	return false


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
## Every cell the hero can get to. A shut door does not count as a
## wall here: it can be opened, so a room behind one is reachable -
## and every placement check in the game asks this question.
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
			if blocks(step) and not door_shut(step):
				continue
			seen[step] = true
			stack.append(step)
	return seen


func _shopkeeper_spot(where: Array) -> Variant:
	for _try in 20:
		var cell = _free_cell(where)
		if cell == null:
			return null
		# A keeper is a tile that never opens, so putting one down is the
		# same question as putting a crate down: does the floor still hold
		# together with it there? Asked by the same function, so the two
		# cannot drift apart - and they did: the crate check learned about
		# loot long before this one did.
		var others := {}
		for shop in shops:
			others[shop["cell"]] = true
		# The keeper has to be reachable themselves, with the keepers
		# already standing counted as walls. _seals_something cannot ask
		# this: to it every keeper is a wall, including the one being
		# asked about, so a shop placed behind another shop looked fine
		# and could never be walked to.
		if not reachable_from(Vector2i(player.x, player.y), others).has(cell):
			continue
		var blocked := others.duplicate()
		blocked[cell] = true
		if _seals_something(blocked):
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
	if chest != null and not chest.get("gone", false) and chest["cell"] == cell:
		return true
	if shrine != null and shrine == cell:
		return true
	if captive != null and captive == cell:
		return true
	if decor.has(cell) or hazards.has(cell) or webs.has(cell) or doors.has(cell):
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


## Whether the thing standing over the chest is still alive.
func _keeper_alive() -> bool:
	for monster in monsters:
		if monster.is_keeper and monster.is_alive():
			return true
	return false

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

## How far the torch reaches on this difficulty.
##
## An easy run sees two tiles further, a hard one one less, hardcore two
## less. Sight is the cheapest difficulty there is: the same floor with
## the same monsters is a different problem when you meet them one tile
## later.
func sight_radius() -> int:
	return maxi(4, Data.FOV_RADIUS + int(Data.difficulty_by_id(difficulty).get("sight", 0)))


func recompute_fov() -> void:
	lit.clear()
	var here := Vector2i(player.x, player.y)
	var far: int = sight_radius()
	for dy in range(-far, far + 1):
		for dx in range(-far, far + 1):
			if Vector2(dx, dy).length() > far:
				continue
			var cell := here + Vector2i(dx, dy)
			# Off the map is not somewhere you can see. Without this the
			# cells past the border end up in `explored`, and drawing them
			# reads the grid out of bounds - which is an error every frame
			# for as long as the hero stands near an edge.
			if cell.x < 0 or cell.y < 0 or cell.x >= MAP_W or cell.y >= MAP_H:
				continue
			if _line_clear(here, cell):
				lit[cell] = true
				explored[cell] = true

	# The wall a lit tile touches is lit as well.
	#
	# Sight is traced to the middle of each cell, so a wall the line
	# only grazes stays dark - and a room then has holes along its edge
	# where the wall should be, with the floor of the corridor behind
	# showing through. Worst at a door: the frame it hangs in is
	# exactly the pair of tiles the line grazes, so doors were standing
	# in mid-air. A wall next to something you can see is something you
	# can see.
	var edges := {}
	for cell in lit:
		if not Dungeon.is_walkable(grid, cell.x, cell.y):
			continue
		for dy in [-1, 0, 1]:
			for dx in [-1, 0, 1]:
				var beside: Vector2i = cell + Vector2i(dx, dy)
				if beside.x < 0 or beside.y < 0 or beside.x >= MAP_W or beside.y >= MAP_H:
					continue
				if Dungeon.is_walkable(grid, beside.x, beside.y):
					continue
				edges[beside] = true
	for cell in edges:
		lit[cell] = true
		explored[cell] = true


func _line_clear(from: Vector2i, to: Vector2i) -> bool:
	var steps := maxi(absi(to.x - from.x), absi(to.y - from.y))
	for i in range(1, steps):
		var at := Vector2(from) + Vector2(to - from) * (float(i) / float(steps))
		var cell := Vector2i(roundi(at.x), roundi(at.y))
		if cell == from or cell == to:
			continue
		# A shut door and a stacked crate stop the eye as well as the
		# foot. Without this you can see straight through a closed door,
		# which makes opening one pointless.
		if not Dungeon.is_walkable(grid, cell.x, cell.y) or blocks(cell):
			return false
	return true


# --- the turn -------------------------------------------------------------

## Whether a diagonal step would cut a corner.
##
## The old rule only refused the step when *both* neighbouring tiles
## were wall - the case of squeezing through the join between two
## corners. One wall is enough, though: sliding diagonally past a corner
## means passing through ground that is not there. Past a shut door it
## is worse, because the door is then never opened at all: it stands
## there as decoration while everything walks around it.
##
## Blocking scenery counts as wall here for the same reason a crate
## counts as wall everywhere else - it is a solid object, and it reads
## as one.
func _corner_cut(from: Vector2i, step: Vector2i) -> bool:
	if step.x == 0 or step.y == 0:
		return false
	for beside in [Vector2i(from.x + step.x, from.y),
			Vector2i(from.x, from.y + step.y)]:
		if not Dungeon.is_walkable(grid, beside.x, beside.y) or blocks(beside):
			return true
	return false


## Cuts a diagonal down to one axis when the player has asked for four
## directions.
##
## Not everyone wants eight. On a stick a diagonal is easy to hit by
## accident, and in a corridor it is never the step that was meant. The
## stronger axis wins; on a perfect diagonal, sideways - because the
## screen is wider than it is tall and that is the way the room usually
## runs.
func _straighten(step: Vector2i) -> Vector2i:
	if settings.get("diagonal", true) or step.x == 0 or step.y == 0:
		return step
	if _stick != null and absf(_stick.pull().y) > absf(_stick.pull().x):
		return Vector2i(0, step.y)
	return Vector2i(step.x, 0)


func try_move(step: Vector2i) -> void:
	# A guest owns nothing: it asks, the host decides, and the answer
	# arrives as the next pulse. Simulating it here as well would be
	# two dungeons pretending to be one.
	if net != null and net.guest:
		net.ask("move", step)
		return
	# Caught in a web: the turn is spent tearing free instead of
	# moving, and the monsters get their turn anyway.
	if player != null and player.webbed > 0 and not dead and not choosing:
		player.webbed -= 1
		say("Du reißt dich aus dem Netz.")
		enemy_turn()
		recompute_fov()
		paint()
		return
	if busy() or step == Vector2i.ZERO:
		return
	# Also here, not only where the input is read: a key held from before
	# the switch was flipped would otherwise still walk at an angle.
	if not settings.get("diagonal", true) and step.x != 0 and step.y != 0:
		return
	var target := Vector2i(player.x + step.x, player.y + step.y)
	if _corner_cut(Vector2i(player.x, player.y), step):
		return
	if step.x != 0:
		player.facing = 1 if step.x > 0 else -1

	# Walking into a companion trades places with them.
	#
	# Nothing stopped two heroes standing on the same tile, and the one who
	# arrived second was simply drawn over the first - which from the other
	# side of the room looks exactly like your friend vanishing the moment
	# the host moved. Refusing the step would be worse: in a one-tile
	# corridor it walls people in behind each other.
	var mate: Variant = _hero_at(target)
	if mate != null:
		var was := Vector2i(player.x, player.y)
		player.x = target.x
		player.y = target.y
		player.snap()
		mate.x = was.x
		mate.y = was.y
		mate.snap()
		say("Ihr tauscht die Plätze.")
		_tick_buffs()
		enemy_turn()
		recompute_fov()
		paint()
		return

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
	elif captive != null and captive == target:
		_free_captive(target)
		_tick_buffs()
		enemy_turn()
		recompute_fov()
		paint()
		return
	elif door_shut(target):
		_open_door(target)
		return
	elif blocks(target):
		return
	elif Dungeon.is_walkable(grid, target.x, target.y):
		player.x = target.x
		player.y = target.y
		_pick_up(target)
		_open_chest(target)
		_spring_trap(target)
		_step_in_web(target)
		_enter_theme(target)
		_step_in_hazard(target)
		_touch_shrine(target)
		if dead:
			return
		if target == stairs:
			_settle_quest()
			_stash_floor()
			depth += 1
			audio.play("stairs")
			say("Du steigst hinab - Ebene %d." % depth)
			new_level()
			return
		if target == up_stairs and depth > 1:
			_stash_floor()
			depth -= 1
			audio.play("stairs")
			say("Du steigst hinauf - Ebene %d." % depth)
			new_level(true)
			return
	else:
		return

	_tick_poison()
	_tick_regen()
	_check_awards()
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


## Picks this floor's optional goal, from the ones the floor can
## actually satisfy: an order to open a chest on a floor without one is
## not a goal, it is a bug with a reward attached.
func _set_quest() -> void:
	quest = {}
	if rng.randf() >= Data.QUEST_CHANCE:
		return
	var pool: Array = []
	for entry in Data.QUESTS:
		match entry.get("needs", ""):
			"chest":
				if chest == null:
					continue
			"shrine":
				if shrine == null:
					continue
			"captive":
				if captive == null:
					continue
			"boss":
				if not boss_alive():
					continue
		pool.append(entry)
	if pool.is_empty():
		return
	var picked: Dictionary = pool[rng.randi() % pool.size()]
	quest = {"id": picked["id"], "name": picked["name"], "done": false,
		"gold": int(picked["gold"]), "potion": int(picked["potion"])}


## Called whenever something happens that a goal might be about. Cheap,
## and it keeps every condition next to the thing it watches instead of
## in one place that has to know about all of them.
func _quest_progress() -> void:
	if quest.is_empty() or quest.get("done", false):
		return
	var met := false
	match quest["id"]:
		"clear":
			met = true
			for monster in monsters:
				if monster.is_alive():
					met = false
					break
		"chest":
			met = chest != null and chest["opened"]
		"shrine":
			met = shrine == null
		"captive":
			met = captive == null
		"boss":
			met = not boss_alive()
		"dry", "unhurt":
			# These two can only be settled on the stairs: they are about
			# what did not happen, and the floor is not over yet.
			return
	if not met:
		return
	quest["done"] = true
	audio.play("levelup")
	banner("Auftrag erfüllt", Color(0.55, 0.85, 0.98))
	say("Auftrag erfüllt: %s." % quest["name"])


## Paid out on the way down - and the two "without" goals are decided
## here, since only now is it certain nothing happened.
func _settle_quest() -> void:
	if quest.is_empty():
		return
	match quest["id"]:
		"dry":
			quest["done"] = not drank_here
		"unhurt":
			quest["done"] = not hurt_here
	if not quest.get("done", false):
		say("Auftrag verfehlt: %s." % quest["name"])
		return
	var gold: int = int(quest["gold"]) + depth * 3
	player.gold += gold
	var flasks: int = int(quest["potion"])
	if flasks > 0:
		player.add_potion(Data.pick_potion(depth, rng, false), flasks)
	Stats.bump("quests")
	audio.play("coin")
	say("Belohnung: %d Gold%s." % [gold, " und ein Trank" if flasks > 0 else ""])


## Turns one room on the floor into something: a library, an armoury, a
## laboratory, a bone house. The room keeps its normal contents - this
## is added on top, so a themed room is worth the detour rather than
## being the only room with anything in it.
func _furnish_theme(where: Array, within: Dictionary) -> void:
	theme = {}
	if where.is_empty() or rng.randf() >= Data.ROOM_THEME_CHANCE:
		return
	var chosen := Data.pick_theme(depth, rng)
	if chosen.is_empty():
		return
	var room = where[rng.randi() % where.size()]
	theme = {"id": chosen["id"], "name": chosen["name"],
		"x1": room.x1, "y1": room.y1, "x2": room.x2, "y2": room.y2, "seen": false}

	var span: Array = chosen["amount"]
	for _i in rng.randi_range(int(span[0]), int(span[1])):
		var cell: Variant = _free_cell([room], within)
		if cell == null:
			continue
		var loot := {"cell": cell, "kind": chosen["loot"],
			"amount": rng.randi_range(15, 30 + depth * 4)}
		if chosen["loot"] == "potion":
			loot["potion"] = Data.pick_potion(depth, rng)
		elif chosen["loot"] == "scroll":
			loot["scroll"] = Data.SCROLLS[rng.randi() % Data.SCROLLS.size()]["id"]
		items.append(loot)

	# A little scenery of its own, so the room reads as one from the door.
	for _i in 3:
		var spot: Variant = _free_cell([room], within)
		if spot == null:
			continue
		# The same rule the rest of the scenery follows: nothing solid in
		# a doorway. A themed room is furnished separately, and the rule
		# was only written into the other half.
		if chosen["decor"] in Data.BLOCKING_DECOR and _beside_a_door(spot):
			continue
		decor[spot] = chosen["decor"]
		if chosen["decor"] in Data.BLOCKING_DECOR and _seals_something():
			decor.erase(spot)

	# And whatever guards it.
	if not chosen.has("guards"):
		return
	var guards: Array = chosen["guards"]
	for _i in rng.randi_range(int(guards[0]), int(guards[1])):
		var post: Variant = _free_cell([room], within)
		if post == null:
			continue
		var guard := Entities.Monster.new(str(chosen.get("guard_kind", "skeleton")),
			tier["mult"], difficulty)
		guard.x = post.x
		guard.y = post.y
		guard.snap()
		monsters.append(guard)


## Announced the first time the hero stands in it, not when the floor is
## built: a banner about a room you cannot see yet is a banner about
## nothing.
func _enter_theme(cell: Vector2i) -> void:
	if theme.is_empty() or theme.get("seen", false):
		return
	if cell.x < int(theme["x1"]) or cell.x >= int(theme["x2"]):
		return
	if cell.y < int(theme["y1"]) or cell.y >= int(theme["y2"]):
		return
	theme["seen"] = true
	banner(str(theme["name"]), Color(0.72, 0.85, 1.0))
	say("Du betrittst: %s." % theme["name"])


## Hangs doors in the ways into rooms.
##
## An entrance is a floor cell just outside a room that touches the room
## - that is what a corridor mouth looks like from the inside. Only some
## of them get a door: a floor where every room is sealed is a floor
## spent opening doors.
func _hang_doors(where: Array) -> void:
	doors.clear()
	for room in where:
		for cell in _entrances(room):
			if rng.randf() >= Data.DOOR_CHANCE:
				continue
			if cell == stairs or cell == up_stairs or cell == Vector2i(player.x, player.y):
				continue
			# Doors are hung after everything has been put down, so the cell
			# has to be empty: a shut door with a monster inside it is a
			# monster in a wall.
			if occupied(cell) or taken(cell):
				continue
			if doors.has(cell):
				continue
			# Never beside another door. Two in a row is the same corridor
			# closed twice, for no reason - and it reads as a mistake, which
			# it was.
			var crowded := false
			for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1),
					Vector2i(0, -1), Vector2i(1, 1), Vector2i(1, -1),
					Vector2i(-1, 1), Vector2i(-1, -1)]:
				if doors.has(cell + offset):
					crowded = true
					break
			if crowded:
				continue
			if not _is_doorway(cell, room):
				continue
			doors[cell] = false



## Is this cell a doorway into that room, or just a tile a door would
## be standing on?
##
## Three things have to hold, and each of them was a door on the map
## that made no sense:
##
## The cell is a passage: floor on two opposite sides, wall on the other
## two. A door in open ground is a frame around nothing.
##
## The passage runs *into* the room - one of those two sides is inside
## it, the other is not. This is the one that was missing. A corridor
## carved along a room's edge touches it for its whole length and looks
## like a passage at every step, so doors were being hung in the middle
## of corridors with the room lying wide open beside them.
##
## And there is something on both sides. A door onto three tiles of
## nothing is worse than no door.
func _is_doorway(cell: Vector2i, room) -> bool:
	var west: bool = Dungeon.is_walkable(grid, cell.x - 1, cell.y)
	var east: bool = Dungeon.is_walkable(grid, cell.x + 1, cell.y)
	var north: bool = Dungeon.is_walkable(grid, cell.x, cell.y - 1)
	var south: bool = Dungeon.is_walkable(grid, cell.x, cell.y + 1)
	var open_x: bool = west and east
	var open_y: bool = north and south
	if open_x == open_y:
		return false
	# And wall on the other two sides - both of them.
	#
	# Only the floor was being checked before, never the wall, and the two
	# are not the same question: a corridor tile with floor left, right and
	# below and wall only above passed as a passage. It is not one, it is
	# the edge of an open room, and a door standing there is a frame with
	# one post. Fifteen per cent of every door on the map was that.
	if open_x and (north or south):
		return false
	if open_y and (west or east):
		return false
	var sides: Array = ([Vector2i(-1, 0), Vector2i(1, 0)] if open_x
		else [Vector2i(0, -1), Vector2i(0, 1)])
	var inside := 0
	for offset in sides:
		var beside: Vector2i = cell + offset
		if beside.x >= room.x1 and beside.x < room.x2 \
				and beside.y >= room.y1 and beside.y < room.y2:
			inside += 1
	if inside != 1:
		return false
	for offset in sides:
		if _pocket_behind(cell, cell + offset) <= DOOR_POCKET:
			return false
	return true


## How much floor lies behind a cell if the doorway is treated as a wall.
## Counted no further than it takes to decide - a corridor that carries
## on is a corridor, and the exact number stops mattering long before
## then.
func _pocket_behind(doorway: Vector2i, from: Vector2i) -> int:
	var seen := {from: true}
	var queue: Array[Vector2i] = [from]
	var head := 0
	while head < queue.size() and seen.size() <= DOOR_POCKET:
		var at: Vector2i = queue[head]
		head += 1
		for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var next: Vector2i = at + offset
			if next == doorway or seen.has(next):
				continue
			if not Dungeon.is_walkable(grid, next.x, next.y):
				continue
			seen[next] = true
			queue.append(next)
	return seen.size()


## Whether this cell is a door or stands directly in front of one.
func _beside_a_door(cell: Vector2i) -> bool:
	if doors.has(cell):
		return true
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if doors.has(cell + offset):
			return true
	return false


## The floor cells immediately outside a room that touch it.
func _entrances(room) -> Array:
	var found: Array[Vector2i] = []
	for x in range(room.x1 - 1, room.x2 + 1):
		for y in [room.y1 - 1, room.y2]:
			var cell := Vector2i(x, y)
			if Dungeon.is_walkable(grid, cell.x, cell.y) and _touches_room(cell, room):
				found.append(cell)
	for y in range(room.y1 - 1, room.y2 + 1):
		for x in [room.x1 - 1, room.x2]:
			var cell := Vector2i(x, y)
			if Dungeon.is_walkable(grid, cell.x, cell.y) and _touches_room(cell, room):
				found.append(cell)
	return found


func _touches_room(cell: Vector2i, room) -> bool:
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var beside: Vector2i = cell + offset
		if beside.x >= room.x1 and beside.x < room.x2 \
				and beside.y >= room.y1 and beside.y < room.y2:
			return true
	return false


## A closed door is a wall you can talk to: walking into it opens it and
## costs the turn, which is the whole point - it is a moment of noise
## and a moment of exposure, not a lock.
func _open_door(cell: Vector2i) -> void:
	doors[cell] = true
	Stats.bump("doors")
	audio.play("stairs")
	say("Du öffnest die Tür.")
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


func door_shut(cell: Vector2i) -> bool:
	return doors.has(cell) and not doors[cell]


## Whether something standing on this cell closes it to walking. Kept
## apart from Dungeon.is_walkable because the map is the map: what is
## put on top of it changes from floor to floor.
func blocks(cell: Vector2i) -> bool:
	return decor.get(cell, "") in Data.BLOCKING_DECOR or door_shut(cell)

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
	_damage_number(monster.cell(), str(damage),
		Color(1.0, 0.90, 0.24) if crit else Color(1.0, 1.0, 1.0))
	if crit:
		_shake(2.0)
		_sparks(monster.cell(), Color(1.0, 0.92, 0.35), 11)
		# Hitstop: the next step waits a moment longer. In a turn-based
		# game there is no frame to freeze, but a held direction still
		# hesitates - which is what makes a big hit feel big.
		_step_cooldown = maxf(_step_cooldown, STEP_TIME * 0.9)
	else:
		_sparks(monster.cell(), Color(0.95, 0.85, 0.80), 4)
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
	# What a creature fears hurts it twice as much; what it is made
	# of barely touches it. A skeleton and a slime both burn, an orc
	# freezes, a bat is a lightning rod.
	var factor := 1.0
	if id in monster.weak:
		factor = Data.WEAK_MULT
	elif id in monster.resist:
		factor = Data.RESIST_MULT
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
	return maxi(1, int(round(float(element["damage"]) * factor)))



## A sapper leaves a crater. Everything beside it takes the blast - the
## hero included, which is what makes killing one next to you a mistake
## rather than a formality.
func _explode(monster) -> void:
	var here: Vector2i = monster.cell()
	audio.play("boss")
	_sparks(here, Color(1.0, 0.70, 0.25), 18)
	_shake(3.0)
	banner("%s geht hoch!" % monster.display_name, Color(1.0, 0.70, 0.25))
	for other in monsters.duplicate():
		if other == monster or not other.is_alive():
			continue
		if absi(other.x - here.x) > 1 or absi(other.y - here.y) > 1:
			continue
		other.hp -= monster.explodes
		if not other.is_alive():
			_kill(other)
	if absi(player.x - here.x) <= 1 and absi(player.y - here.y) <= 1 and not dead:
		var hurt: int = maxi(1, monster.explodes - player.defense())
		player.hp -= hurt
		_damage_number(Vector2i(player.x, player.y), "-%d" % hurt, Color(1.0, 0.55, 0.20))
		_hurt_flash()
		say("Die Explosion trifft dich für %d." % hurt)
		if player.hp <= 0:
			player.hp = 0
			dead = true
			Save.wipe()
			audio.play("death")
			_show_death()


## A bone mage calls up help - but only so much of it, and only beside
## itself. Without the limit a single mage turns a floor into a wall of
## skeletons while you are still walking towards it.
func _summon(monster) -> void:
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
			Vector2i(1, 1), Vector2i(-1, -1)]:
		var spot: Vector2i = monster.cell() + offset
		if not Dungeon.is_walkable(grid, spot.x, spot.y) or blocks(spot):
			continue
		if occupied(spot) or spot == Vector2i(player.x, player.y):
			continue
		var called := Entities.Monster.new(monster.summons, tier["mult"], difficulty)
		called.x = spot.x
		called.y = spot.y
		called.awake = true
		# Half the experience: a summoned skeleton is a nuisance, not a
		# renewable source of levels.
		called.xp_reward = maxi(1, called.xp_reward / 2)
		called.snap()
		monsters.append(called)
		_note_kind(called.kind, "seen")
		monster.summoned += 1
		if lit.has(monster.cell()):
			say("%s ruft Verstärkung." % monster.display_name)
		return


## A widow spins a web on a cell near the hero. Walking into it costs
## you a few turns of speed rather than health - a different kind of
## trouble from everything else on the floor.
func _spin_web(monster) -> void:
	var here := Vector2i(player.x, player.y)
	for offset in [Vector2i.ZERO, Vector2i(1, 0), Vector2i(-1, 0),
			Vector2i(0, 1), Vector2i(0, -1)]:
		var spot: Vector2i = here + offset
		if not Dungeon.is_walkable(grid, spot.x, spot.y) or blocks(spot):
			continue
		if taken(spot) or spot == stairs or spot == up_stairs:
			continue
		webs[spot] = true
		if lit.has(spot):
			say("%s spinnt ein Netz." % monster.display_name)
		return


## Walked into a web: it holds for a few turns, and it is used up.
func _step_in_web(cell: Vector2i) -> void:
	if not webs.has(cell):
		return
	webs.erase(cell)
	player.webbed = maxi(player.webbed, Data.WEB_SLOW)
	audio.play("denied")
	say("Du hängst im Netz fest.")


## A monster dies: experience, the level-up that may follow, and the
## sprite. Anything that can kill goes through here - a thrown flask
## that skipped this step handed out no experience at all.
func _kill(monster) -> void:
	_note_kind(monster.kind, "killed")
	if monster.kind == "bone_mage":
		_award("exorcist")
	if monster.explodes > 0:
		_explode(monster)
	_sparks(monster.cell(), Color(0.85, 0.30, 0.28), 16)
	# A slime does not die the first time: it comes apart into two
	# smaller ones. Two generations deep and there is nothing left to
	# divide, or one slime would keep a floor busy forever.
	if monster.splits and monster.generation < 2:
		_split(monster)
	audio.play("monster_death")
	say("%s stirbt." % monster.display_name)
	if monster.is_boss:
		_award("boss_slayer")
	player.kills += 1
	if player.gain_xp(monster.xp_reward) > 0:
		audio.play("levelup")
		_offer_perk()
		say("Level auf! Du bist jetzt Stufe %d." % player.level)
	if _actor_nodes.has(monster):
		var sprite = _actor_nodes[monster]
		if _shadows.has(sprite):
			_shadows[sprite].queue_free()
			_shadows.erase(sprite)
		sprite.queue_free()
		_actor_nodes.erase(monster)
	monsters.erase(monster)
	_quest_progress()

## Two halves beside the cell the thing died on.
func _split(monster) -> void:
	var made := 0
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if made >= 2:
			return
		var spot: Vector2i = monster.cell() + offset
		if not Dungeon.is_walkable(grid, spot.x, spot.y) or blocks(spot):
			continue
		if occupied(spot) or spot == Vector2i(player.x, player.y):
			continue
		var half := Entities.Monster.new(monster.kind, tier["mult"], difficulty)
		half.x = spot.x
		half.y = spot.y
		half.generation = monster.generation + 1
		half.max_hp = maxi(1, int(monster.max_hp * Data.SPLIT_CHILD_MULT))
		half.hp = half.max_hp
		half.power = maxi(1, int(monster.power * Data.SPLIT_CHILD_MULT))
		half.xp_reward = maxi(1, int(monster.xp_reward * Data.SPLIT_CHILD_MULT))
		half.display_name = "Kleiner %s" % monster.display_name
		half.awake = true
		half.snap()
		monsters.append(half)
		_note_kind(half.kind, "seen")
		made += 1
	if made > 0:
		say("%s teilt sich!" % monster.display_name)

func enemy_turn() -> void:
	# Haste is the hero acting twice, expressed the other way round:
	# every second enemy turn is skipped. Doing it as a free extra
	# player move would mean two attacks per tap, which is a different
	# and much stronger thing than the Python build gives.
	if player.has_buff("haste"):
		_haste_flip = not _haste_flip
		if _haste_flip:
			return
	# Whoever acted is put back afterwards: for the length of one
	# monster's turn, `player` is that monster's target, and every rule
	# below - chasing, shooting, swinging - then works on the right
	# person without knowing that anyone else exists.
	var acting = player
	var here := Vector2i(player.x, player.y)
	for monster in monsters.duplicate():
		if not monster.is_alive():
			continue
		# Monsters used to go for whoever had just moved, which meant
		# standing still made you invisible and the person walking drew
		# every blow in the room. They go for the nearest hero now.
		player = _nearest_hero(monster.cell())
		here = Vector2i(player.x, player.y)
		# Fire keeps burning whether the thing acts or not.
		if monster.afraid > 0:
			monster.afraid -= 1
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
				_note_kind(monster.kind, "seen")
			else:
				continue
		for _move in monster.speed:
			if dead or not monster.is_alive():
				break
			var to_player: Vector2i = here - monster.cell()
			var reach: int = absi(to_player.x) + absi(to_player.y)
			var towards := Vector2i(signi(to_player.x), signi(to_player.y))
			if reach == 1:
				# A kiter would rather not be here at all: it takes the free
				# step back instead of trading blows, and only swings when it
				# has nowhere left to go.
				#
				# Not for ever, and never for a boss. A boss holding the key
				# to the stairs that backs away every turn cannot be caught,
				# and the floor can then never be finished - a skeleton king
				# did exactly that for six hundred turns. Three steps back
				# is a tactic; a hundred is a stalemate.
				var may_kite: bool = monster.kites and not monster.is_boss
				if may_kite and monster.kited < 3 and _step_monster(monster, -towards):
					monster.kited += 1
					continue
				monster.kited = 0
				_monster_attacks(monster)
				break
			if reach > 2:
				monster.kited = 0
			var can_shoot: bool = monster.ranged and reach <= Data.RANGED_RANGE
			if can_shoot and _line_clear(monster.cell(), here):
				_monster_shoots(monster)
				break
			if monster.sets_traps and rng.randf() < Data.TRAP_CHANCE:
				_monster_sets_trap(monster)
			if monster.webs and reach <= 4 and rng.randf() < Data.WEB_CHANCE:
				_spin_web(monster)
			if monster.summons != "" and monster.summoned < Data.SUMMON_LIMIT \
					and rng.randf() < Data.SUMMON_CHANCE:
				_summon(monster)
			var step := towards
			if monster.is_fleeing():
				step = -step
			_step_monster(monster, step)
	# Everyone's turn is over, so the hero who is standing here is the one
	# who was here before the monsters picked their targets.
	player = acting




## Returns whether it actually moved: a kiter needs to know, because
## a backwards step that failed means it is cornered and should
## swing after all.
## The other hero standing on a cell, if anybody is. Never the one whose
## turn it is: walking into yourself is not a thing that happens.
func _hero_at(cell: Vector2i) -> Variant:
	if net == null or not net.hosting or party.size() <= 1:
		return null
	for peer in party:
		var hero = party[peer]
		if hero == player or hero.hp <= 0:
			continue
		if hero.x == cell.x and hero.y == cell.y:
			return hero
	return null


## The living hero closest to a cell. Alone, that is always the one and
## only hero, and this costs a dictionary lookup.
func _nearest_hero(cell: Vector2i) -> Variant:
	if net == null or not net.hosting or party.size() <= 1:
		return player
	var best = player
	var closest := 1 << 30
	for peer in party:
		var hero = party[peer]
		if hero.hp <= 0:
			continue
		var away: int = absi(hero.x - cell.x) + absi(hero.y - cell.y)
		if away < closest:
			closest = away
			best = hero
	return best


func _step_monster(monster, step: Vector2i) -> bool:
	for candidate in [monster.cell() + step,
			monster.cell() + Vector2i(step.x, 0),
			monster.cell() + Vector2i(0, step.y)]:
		if candidate == monster.cell():
			continue
		if not Dungeon.is_walkable(grid, candidate.x, candidate.y) or blocks(candidate):
			continue
		# Never onto the hero: a monster sharing your tile cannot be
		# attacked at all, since attacks are aimed at the tile you walk
		# into. The pygame build learned that one the hard way.
		if candidate == Vector2i(player.x, player.y) or occupied(candidate):
			continue
		# The same rule the hero follows. A monster that can take a shortcut
		# the player cannot is a monster that appears out of a wall.
		if _corner_cut(monster.cell(), candidate - monster.cell()):
			continue

		monster.x = candidate.x
		monster.y = candidate.y
		return true
	return false


## An arrow. Weaker than a swing, but it arrives from five tiles away,
## which is the whole point of a skeleton.
func _monster_shoots(monster) -> void:
	var damage: int = maxi(1, int(round(
		(monster.power * Data.RANGED_DAMAGE_MULT) - player.defense())))
	if player.shield > 0:
		var soaked: int = mini(player.shield, damage)
		player.shield -= soaked
		damage -= soaked
		if damage <= 0:
			say("Der Schild fängt den Pfeil von %s." % monster.display_name)
			return
	player.hp -= damage
	audio.play("player_hurt")
	_damage_number(Vector2i(player.x, player.y), "-%d" % damage, Color(0.85, 0.75, 0.95))
	_hurt_flash()
	say("%s schießt auf dich: %d." % [monster.display_name, damage])
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		say("Du stirbst auf Ebene %d." % depth)


## A goblin leaves something behind - beside itself, not underneath, or
## it springs its own trap on the way back.
func _monster_sets_trap(monster) -> void:
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var spot: Vector2i = monster.cell() + offset
		if not Dungeon.is_walkable(grid, spot.x, spot.y) or blocks(spot):
			continue
		if taken(spot) or occupied(spot) or spot == Vector2i(player.x, player.y):
			continue
		if spot == stairs or spot == up_stairs:
			continue
		var kinds: Array = Data.TRAPS.keys()
		traps[spot] = kinds[rng.randi() % kinds.size()]
		if lit.has(spot):
			say("%s legt etwas aus." % monster.display_name)
		return

func _monster_attacks(monster) -> void:
	var hits_for: int = monster.power
	# Rage is read from health rather than latched when it crosses the
	# line, so a healed berserker calms down again - the same rule the
	# boss phases follow.
	if monster.enrages > 0.0 and monster.hp <= monster.max_hp / 2:
		hits_for = int(round(hits_for * monster.enrages))
		if not monster.enraged:
			monster.enraged = true
			audio.play("boss")
			say("%s gerät in Rage." % monster.display_name)
	elif monster.enrages > 0.0:
		monster.enraged = false
	if monster.is_boss:
		# A cornered boss swings harder. Announced once per phase, not
		# once per swing, or the log is nothing but rage.
		var phase := Data.boss_phase(monster.hp, monster.max_hp)
		if not phase.is_empty():
			hits_for = int(round(hits_for * float(phase["power"])))
			if monster.phase_said != phase["name"]:
				monster.phase_said = phase["name"]
				audio.play("boss")
				say("%s ist %s und schlägt wilder zu." % [
					monster.display_name, phase["name"]])
	var damage: int = maxi(1, hits_for - player.defense())
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
	hurt_here = true
	# Some things feed on what they take.
	if monster.drains > 0.0 and monster.hp < monster.max_hp:
		var drawn: int = maxi(1, int(round(damage * monster.drains)))
		monster.hp = mini(monster.max_hp, monster.hp + drawn)
		_damage_number(monster.cell(), "+%d" % drawn, Color(0.95, 0.45, 0.60))
	_damage_number(Vector2i(player.x, player.y), "-%d" % damage, Color(1.0, 0.35, 0.32))
	_hurt_flash()
	_shake(1.5)
	say("%s trifft dich für %d." % [monster.display_name, damage])
	_retaliate(monster)
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		_note_kind(monster.kind, "killed_by")
		say("Du stirbst auf Ebene %d. Tippe NEU." % depth)


## What an attacker gets back for hitting you: thorns cut, an ember aura
## sets them alight. Both fire whether or not the blow got through the
## shield - they answer the attack, not the damage.
func _retaliate(monster) -> void:
	# Some things are hot to the touch. This is the monster's answer to
	# being hit, so it fires before thorns - which is the hero's.
	if monster.burns_toucher > 0 and not dead:
		player.poison_turns = maxi(player.poison_turns, monster.burns_toucher)
		say("%s verbrennt dich beim Zuschlagen." % monster.display_name)
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
			_damage_number(cell, "+%d" % found, Color(1.0, 0.84, 0.30))
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
			# Whoever is carrying a bow finds bows. Without this rule the
			# first axe on the floor quietly ends the ranger: it has the
			# bigger number, so it wins the comparison, and the character
			# is gone without anyone deciding anything.
			var w_type: int = _weapon_find()
			var w_rarity: Dictionary = _roll_rarity()
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
			var a_rarity: Dictionary = _roll_rarity()
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
	if player.shot_cooldown > 0:
		player.shot_cooldown -= 1
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

## The rarity of a drop. Luck rolls twice and keeps the better one rather
## than reweighting the table: it cannot conjure a tier that is not
## unlocked at this depth yet, and it stays worth drinking at every
## depth. The same rule as game.py _roll_rarity.
func _roll_rarity() -> Dictionary:
	var rolled := Data.pick_rarity(depth, rng)
	if not player.has_buff("luck"):
		return rolled
	var second := Data.pick_rarity(depth, rng)
	if Data.RARITIES.find(second) > Data.RARITIES.find(rolled):
		return second
	return rolled


## The kind of weapon this depth drops - in the style the hero already
## fights in, so a find is an upgrade rather than a change of character.
func _weapon_find() -> int:
	var wants_reach: bool = player.reach() > 0
	var best := 0
	for i in Data.WEAPONS.size():
		var entry: Dictionary = Data.WEAPONS[i]
		if (int(entry.get("reach", 0)) > 0) != wants_reach:
			continue
		# Deeper floors unlock better ones, the same curve as before.
		if i > 1 + depth / 2:
			continue
		if int(entry["bonus"]) >= int(Data.WEAPONS[best]["bonus"]):
			best = i
	if best == 0 and wants_reach:
		# Nothing ranged unlocked yet: leave the bow alone rather than
		# handing out fists.
		return player.weapon
	return maxi(best, 1)


## Regeneration ticks on the turn, not the frame - a hero who heals
## faster on a faster phone is a different game.
func _tick_regen() -> void:
	if player.regen_interval <= 0 or dead or player.hp >= player.max_hp:
		return
	player.regen_counter += 1
	if player.regen_counter < player.regen_interval:
		return
	player.regen_counter = 0
	player.hp = mini(player.max_hp, player.hp + player.regen_power)


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
	_damage_number(cell, "-%d" % int(trap["damage"]), Color(1.0, 0.55, 0.20))
	_hurt_flash()
	_shake(2.5)
	audio.play("trap")
	say("%s! Du nimmst %d Schaden." % [trap["name"], trap["damage"]])
	if trap.get("wakes", false):
		var roused := 0
		for monster in monsters:
			if monster.is_alive() and not monster.awake:
				monster.awake = true
				roused += 1
		banner("Alarm!", Color(1.0, 0.70, 0.30))
		say("Die Ebene ist wach - %d Kreaturen." % roused)
	if int(trap.get("weaken", 0)) > 0:
		# A dart in the joints: the armour stops doing its job for a
		# while, which is worse than the damage.
		player.buffs["frailty"] = int(player.buffs.get("frailty", 0)) + int(trap["weaken"])
		say("Der Pfeil sitzt tief - deine Deckung leidet.")
	if trap.get("curse", false):
		var curses: Array[String] = ["clumsy", "frailty"]
		var curse: String = curses[rng.randi() % curses.size()]
		player.buffs[curse] = int(player.buffs.get(curse, 0)) + 12
		say("Die Rune brennt: %s." % Data.BUFFS[curse]["name"])
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
		return
	if trap.get("drops", false):
		# Straight through the floor. The way down without the stairs -
		# and without whatever was still lying up here.
		banner("Der Boden gibt nach!", Color(0.85, 0.60, 0.30))
		say("Du stürzt eine Ebene tiefer.")
		_settle_quest()
		_stash_floor()
		depth += 1
		new_level()


## A hazard the hero walked into anyway. It was in plain sight - that is
## the difference from a trap - so this is a decision that went badly,
## not an ambush.
func _step_in_hazard(cell: Vector2i) -> void:
	if not hazards.has(cell) or dead:
		return
	var hazard: Dictionary = Data.HAZARDS[hazards[cell]]
	if hazard.get("one_shot", false):
		hazards.erase(cell)
	var damage: int = int(hazard["damage"])
	player.hp -= damage
	_damage_number(cell, "-%d" % damage, Color(1.0, 0.45, 0.20))
	_hurt_flash()
	_shake(2.0)
	audio.play("trap")
	say("%s! %d Schaden." % [hazard["name"], damage])
	if hazard.has("burn"):
		player.poison_turns = maxi(player.poison_turns, int(hazard["burn"]))
	if hazard.has("bleed"):
		player.bleed_turns = maxi(player.bleed_turns, int(hazard["bleed"]))
	if player.hp <= 0:
		player.hp = 0
		dead = true
		Save.wipe()
		audio.play("death")
		_show_death()
		say("Du stirbst auf Ebene %d." % depth)

func _open_chest(cell: Vector2i) -> void:
	if chest == null or chest["opened"] or chest["cell"] != cell:
		return
	if chest.get("guarded", false) and _keeper_alive():
		audio.play("denied")
		say("Der Wächter lässt die Truhe nicht los.")
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
		_quest_progress()
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
	_note_kind(mimic.kind, "seen")
	audio.play("boss")
	banner("Es war eine Mimik!", Color(0.85, 0.32, 0.30))
	say("Die Truhe schnappt zu - es war eine Mimik!")

	# And the chest is gone, because there never was one.
	#
	# It used to stay lying there as an opened empty chest, which is the
	# one thing it certainly is not: the box got up and is now standing
	# next to you. Leaving the picture behind reads as a second chest
	# that has already been looted, and it draws the eye away from the
	# thing that just came out of it.
	#
	# Marked rather than deleted: the floor is saved and the "open the
	# chest" errand still has to be able to see that it was opened.
	chest["gone"] = true
	_forget_prop(cell)
	_quest_progress()


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
	var kind: String = what
	if what.begins_with("potion:"):
		kind = "potion"
	elif what.begins_with("scroll:"):
		kind = "scroll"
	match kind:
		"potion":
			var id: String = what.substr(7) if what.begins_with("potion:") else Data.DEFAULT_POTION
			var potion := Data.potion_by_id(id)
			if _spend(price(int(potion["price"]))):
				player.add_potion(id)
				say("Gekauft: %s." % potion["name"])
		"scroll":
			var paper_id: String = what.substr(7)
			var scroll := Data.scroll_by_id(paper_id)
			if _spend(price(int(scroll["price"]))):
				player.scrolls[paper_id] = int(player.scrolls.get(paper_id, 0)) + 1
				say("Gekauft: %s." % scroll["name"])
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

		"enchant":
			if _spend(price(Data.SMITH_ENCHANT_PRICE)):
				# A reroll may land on what it already had - that is the
				# gamble, and pretending otherwise would need a memory of
				# what was tried.
				var ids: Array = Data.ELEMENTS.keys()
				player.weapon_element = ids[rng.randi() % ids.size()]
				audio.play("equip")
				say("Die Waffe trägt jetzt %s." % Data.ELEMENTS[player.weapon_element]["name"])
		"reforge":
			if _spend(price(Data.SMITH_REFORGE_PRICE)):
				var was: int = Data.RARITIES.find(Data.rarity_by_id(player.weapon_rarity))
				var now := Data.pick_rarity(depth, rng)
				# One tier up where the depth allows it, so the price buys
				# a step rather than a coin flip that usually loses.
				if Data.RARITIES.find(now) <= was:
					var up: int = mini(was + 1, Data.RARITIES.size() - 1)
					if int(Data.RARITIES[up]["min_level"]) <= depth:
						now = Data.RARITIES[up]
				player.weapon_rarity = now["id"]
				audio.play("equip")
				say("Umgeschmiedet: %s +%d." % [player.weapon_name(), player.weapon_bonus()])
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
	# A guest owns nothing: it asks, the host decides, and the answer
	# arrives as the next pulse. Simulating it here as well would be
	# two dungeons pretending to be one.
	if net != null and net.guest:
		net.ask("drink")
		return
	if busy() or player.potions <= 0:
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
	drank_here = true
	# One flask is enough to lose it - that is the whole point of
	# the achievement.
	potion_free = false
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
		var healed: int = mini(player.max_hp - player.hp,
			int(round(int(effect["heal"]) * player.potion_mult)))
		player.hp += healed
		_damage_number(Vector2i(player.x, player.y), "+%d" % healed, Color(0.42, 0.88, 0.50))
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
		player.shield += int(round(int(effect["shield"]) * player.potion_mult))
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


## Frees whoever is chained up on this floor.
##
## Walking into them does it, like a shopkeeper - so they are a tile you
## cannot walk through, which is why they are placed where a shopkeeper
## would be allowed to stand.
func _free_captive(cell: Vector2i) -> void:
	if captive == null or captive != cell:
		return
	captive = null
	var purse: int = 20 + depth * 5
	player.gold += purse
	player.add_potion(Data.pick_potion(depth, rng, false))
	audio.play("levelup")
	banner("Befreit", Color(0.55, 0.85, 0.98))
	say("Der Gefangene dankt dir: %d Gold und ein Trank." % purse)
	_quest_progress()


## The shrine, triggered by walking onto it. Two of the five outcomes
## are bad, which is the point: a tile you always want to step on is not
## a decision.
func _touch_shrine(cell: Vector2i) -> void:
	if shrine == null or shrine != cell:
		return
	shrine = null
	_quest_progress()
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
		"wisdom":
			var gained: int = player.gain_xp(int(player.xp_to_next * 0.5))
			if gained > 0:
				_offer_perk()
			audio.play("levelup")
			say("Der Schrein schenkt dir Einsicht.")
		"cleanse":
			player.poison_turns = 0
			player.bleed_turns = 0
			for curse_id in player.buffs.keys():
				var entry: Dictionary = Data.BUFFS[curse_id]
				if int(entry.get("power", 0)) < 0 or int(entry.get("defense", 0)) < 0:
					player.buffs.erase(curse_id)
			player.hp = mini(player.max_hp, player.hp + 10)
			audio.play("pickup")
			say("Der Schrein wäscht das Übel ab.")
		"hoard":
			var dropped := 0
			for _i in 4:
				var spot: Variant = _free_cell(rooms,
					reachable_from(Vector2i(player.x, player.y)))
				if spot == null:
					continue
				items.append({"cell": spot, "kind": "gold",
					"amount": rng.randi_range(10, 20 + depth * 4)})
				dropped += 1
			audio.play("coin")
			say("Der Schrein verstreut %d Beutel über die Ebene." % dropped)
		"guardian":
			# Something wakes up beside you - but it is standing on a purse.
			audio.play("boss")
			banner("Ein Wächter erwacht", Color(0.85, 0.32, 0.30))
			say("Der Schrein weckt seinen Wächter.")
			_ambush()
			for monster in monsters:
				if monster.is_alive() and monster.awake and not monster.is_elite:
					monster.make_elite(Data.ELITES[rng.randi() % Data.ELITES.size()])
					break
			player.gold += 20 + depth * 6
		"ambush":
			audio.play("player_hurt")
			banner("Rachsüchtige Geister!", Color(0.85, 0.32, 0.30))
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
		_note_kind(ghost.kind, "seen")
		spawned += 1


## Reads the selected scroll. Each one aims itself: there is no cursor
## on a phone, and asking for a target would mean a targeting mode for
## three scrolls.
func read_scroll(id: String) -> void:
	if busy() or int(player.scrolls.get(id, 0)) <= 0:
		return
	var scroll := Data.scroll_by_id(id)
	if player.scholar > 0.0 and rng.randf() < player.scholar:
		say("Die Rolle bleibt unversehrt.")
	else:
		player.scrolls[id] = int(player.scrolls[id]) - 1
		if int(player.scrolls[id]) <= 0:
			player.scrolls.erase(id)
	say("Du liest: %s." % scroll["name"])
	scrolls_read += 1
	match id:
		"fireball":
			_fireball(int(scroll["damage"]))
		"teleport":
			_blink()
		"reveal":
			_reveal_level()
			say("Die Ebene liegt offen vor dir.")
		"fear":
			_terrify()
		"quake":
			_quake(int(scroll.get("damage", 8)))
		"blessing":
			_bless()
	if dead:
		return
	_tick_buffs()
	enemy_turn()
	recompute_fov()
	paint()


## Everything that can see you decides it would rather not. Fleeing is
## the behaviour monsters already have when they are nearly dead, so
## this borrows it wholesale rather than inventing a second kind of
## running away.
func _terrify() -> void:
	var scared := 0
	for monster in monsters:
		if not monster.is_alive() or not lit.has(monster.cell()):
			continue
		monster.afraid = maxi(monster.afraid, Data.FEAR_TURNS)
		monster.awake = true
		scared += 1
	audio.play("boss")
	banner("Schrecken", Color(0.75, 0.65, 1.0))
	say("%d Kreaturen fliehen vor dir." % scared)


## A shake that reaches everything you can see: modest damage, but it
## puts the whole room on the floor for a moment. The answer to being
## surrounded rather than to being outmatched.
func _quake(damage: int) -> void:
	var hit := 0
	for monster in monsters.duplicate():
		if not monster.is_alive() or not lit.has(monster.cell()):
			continue
		hit += 1
		monster.hp -= damage
		monster.stun_turns = maxi(monster.stun_turns, Data.QUAKE_STUN)
		monster.awake = true
		_sparks(monster.cell(), Color(0.85, 0.75, 0.55), 6)
		if not monster.is_alive():
			_kill(monster)
	audio.play("boss")
	_shake(4.0)
	say("Der Boden bebt - %d getroffen." % hit)


## A random favour, drawn from the same table the potions use. Cheaper
## than a table of its own, and it means a blessing can hand out
## anything the game already knows how to grant.
func _bless() -> void:
	var ids: Array = Data.BUFFS.keys()
	var kindly: Array = []
	for id in ids:
		# Nothing that makes you worse: a blessing that clumsies you is a
		# curse with a nice name.
		if int(Data.BUFFS[id].get("power", 0)) < 0 or int(Data.BUFFS[id].get("defense", 0)) < 0:
			continue
		kindly.append(id)
	if kindly.is_empty():
		return
	var chosen: String = kindly[rng.randi() % kindly.size()]
	player.buffs[chosen] = int(player.buffs.get(chosen, 0)) + 14
	audio.play("levelup")
	banner("Segen: %s" % Data.BUFFS[chosen]["name"], Color(0.55, 0.85, 0.98))
	say("%s für 14 Züge." % Data.BUFFS[chosen]["name"])


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
	# Only to somewhere the hero could have walked to anyway. A free
	# cell is not the same as a reachable one: crates can close a room
	# off, and a blink into that pocket strands the run there - the
	# floor is then unfinishable and nothing looks broken.
	# Shopkeepers count as walls here, as they do everywhere else: you
	# cannot walk through one, so landing behind one cuts the hero off
	# from the stairs just as thoroughly as a crate would.
	var shut := {}
	for shop in shops:
		shut[shop["cell"]] = true
	var spot: Variant = _free_cell(rooms,
		reachable_from(Vector2i(player.x, player.y), shut))
	if spot == null:
		say("Nichts geschieht.")
		return
	player.x = spot.x
	player.y = spot.y
	player.snap()
	say("Ein Blinzeln - und du stehst woanders.")


## Looses an arrow at the nearest thing you can see.
##
## Aimed for you, like the scrolls are: there is no cursor on a phone,
## and a targeting mode for one attack would be more interface than the
## attack is worth. It costs a turn like any other action, hits for less
## than a swing, and needs a moment before the next one - otherwise a bow
## is simply a sword that also works at range.
func shoot(on_its_own := false) -> void:
	# A guest owns nothing: it asks, the host decides, and the answer
	# arrives as the next pulse. Simulating it here as well would be
	# two dungeons pretending to be one.
	if net != null and net.guest:
		net.ask("shoot")
		return
	if busy() or player.reach() <= 0:
		return
	# Paced by the clock, not by turns.
	#
	# The cooldown counted turns, and a shot is a turn - but standing still
	# makes no further turns, so after one shot nothing ever counted it
	# down again. Shoot, walk one step, shoot: that was the only way, and
	# it was not a design, it was a deadlock. The automatic shot was fixed
	# this way in 1.6.3 and the button was left behind.
	if _shot_pause > 0.0:
		audio.play("denied")
		say("Der Bogen ist noch nicht bereit.")
		return

	var here := Vector2i(player.x, player.y)
	var target = null
	var closest := 1 << 30
	for monster in monsters:
		if not monster.is_alive() or not lit.has(monster.cell()):
			continue
		var away: int = absi(monster.x - here.x) + absi(monster.y - here.y)
		if away > player.reach() or away >= closest:
			continue
		if not _line_clear(here, monster.cell()):
			continue
		closest = away
		target = monster
	if target == null:
		audio.play("denied")
		say("Nichts in Reichweite.")
		return

	# A bow throws what the bow is worth; a class with reach and no bow
	# throws a spell, which is worth something of its own.
	var damage: int = 0
	if int(Data.WEAPONS[player.weapon].get("reach", 0)) > 0:
		damage = maxi(1, int(round(
			(player.power() - target.defense_now()) * Data.SHOT_DAMAGE_MULT)))
	else:
		damage = Data.spell_damage(player.level, player.base_power,
			target.defense_now())
	var crit := rng.randf() < player.crit_chance()
	if crit:
		damage *= Data.CRIT_MULT
	damage += _fire_element(target)
	target.hp -= damage
	_flash_monster(target)
	target.awake = true
	if target.x != player.x:
		player.facing = 1 if target.x > player.x else -1
	audio.play("hit")
	# The bolt takes the colour of whatever is being thrown: the
	# weapon's element if it has one, a pale arrow if it does not.
	var shade := Color(0.95, 0.92, 0.70)
	match player.weapon_element:
		"fire":
			shade = Color(1.0, 0.55, 0.20)
		"frost":
			shade = Color(0.55, 0.85, 1.0)
		"lightning":
			shade = Color(1.0, 0.95, 0.45)
		"poison":
			shade = Color(0.55, 0.95, 0.45)
	_bolt(Vector2i(player.x, player.y), target.cell(), shade)
	_sparks(target.cell(), shade, 6)
	_damage_number(target.cell(), str(damage),
		Color(1.0, 0.92, 0.35) if crit else Color(0.85, 0.95, 1.0))
	_sparks(target.cell(), Color(0.85, 0.95, 1.0), 5)
	say("Dein Schuss trifft %s für %d." % [target.display_name, damage])
	if not target.is_alive():
		_kill(target)

	_tick_poison()
	_tick_regen()
	_tick_buffs()
	# Set after the turn has been ticked, not before: everything that
	# runs on turns runs inside this call, so a cooldown set earlier is
	# counted down again immediately and the bow is never actually
	# busy.
	_shot_pause = SHOT_TIME
	# Kept at zero rather than removed: the field is written to the save
	# file, and an older save may carry a one in it. Left alone, that one
	# would never count down and the bow would be jammed for the rest of
	# the run.
	player.shot_cooldown = 0
	if dead:
		return
	enemy_turn()
	recompute_fov()
	paint()


## Whether the game is currently taking orders at all.
##
## Every action asked this question for itself, and every new window -
## the shop, the bag, the gift panel, the pause menu - had to be added to
## each of them by hand. Waiting and shooting were each missed once. One
## function, asked by all of them, cannot be half-updated.
func busy() -> bool:
	if dead or choosing or shop_open != null:
		return true
	if _bag_panel != null and _bag_panel.visible:
		return true
	if _pause_panel != null and _pause_panel.visible:
		return true
	# Reading your own numbers costs no turn, but it does stop the world:
	# a step taken while that page is open is a step nobody meant.
	if _stats_panel != null and _stats_panel.visible:
		return true
	if _attack_panel != null and _attack_panel.visible:
		return true
	if _perk_panel != null and _perk_panel.visible and player.pending_perks > 0:
		return true
	return false


## Fires by itself when something walks into range.
##
## A ranged fighter who has to press a button for every shot spends the
## whole fight pressing a button; the interesting decision is where to
## stand, not whether to loose. So the shot happens on its own - but only
## when the hero is otherwise idle, so it never eats a step, a potion or
## a scroll the player asked for.
##
## It also never starts a fight: only things already awake are shot at.
## Waking a room from across it by reflex is not a tactic, it is a trap.
func _auto_shoot() -> void:
	if busy() or player.reach() <= 0:
		return
	if not player.auto_shoot or _step_cooldown > 0.0 or _shot_pause > 0.0:
		return
	var here := Vector2i(player.x, player.y)
	for monster in monsters:
		if not monster.is_alive() or not monster.awake or not lit.has(monster.cell()):
			continue
		var away: int = absi(monster.x - here.x) + absi(monster.y - here.y)
		# Not at arm's length: something standing next to you is a melee
		# problem, and shooting it would waste the shot the moment it
		# matters most.
		if away <= 1 or away > player.reach():
			continue
		if not _line_clear(here, monster.cell()):
			continue
		shoot(true)
		return


## The neighbour worth hitting, or nothing.
##
## Only things already awake: something asleep beside you is a chance
## to walk away, and a button that quietly offers to wake the room is
## a button that loses runs. Among those awake, the one closest to
## dying - a fight is shortest when something stops swinging.
##
## Steps the hero could not take anyway are left out: a diagonal while
## the four-direction setting is on, or one that would cut a corner.
func _reachable_foe() -> Variant:
	if player == null:
		return null
	var here := Vector2i(player.x, player.y)
	var best: Variant = null
	for monster in monsters:
		if not monster.is_alive() or not monster.awake:
			continue
		var step: Vector2i = monster.cell() - here
		if absi(step.x) > 1 or absi(step.y) > 1 or step == Vector2i.ZERO:
			continue
		if step.x != 0 and step.y != 0:
			if not settings.get("diagonal", true) or _corner_cut(here, step):
				continue
		if best == null or monster.hp < best.hp:
			best = monster
	return best


## The button in the corner: hit what is in reach, or let a turn pass.
func rest_or_attack() -> void:
	if busy():
		return
	var mark: Variant = _reachable_foe()
	if mark == null:
		wait_a_turn()
		return
	var step: Vector2i = mark.cell() - Vector2i(player.x, player.y)
	# The first time, the button explains itself and waits to be told to
	# go ahead. After that it simply swings.
	if not settings.get("attack_hint_seen", false):
		_attack_step = step
		_show_attack_hint(mark)
		return
	try_move(step)


## Stand still for a turn.
##
## Sounds like nothing and is not: regeneration, poison, burning and
## every buff run on turns, so without a way to spend one there is no
## way to heal up before opening a door, and a Potion of Regeneration
## can only be drunk while running away.
func wait_a_turn() -> void:
	# A guest owns nothing: it asks, the host decides, and the answer
	# arrives as the next pulse. Simulating it here as well would be
	# two dungeons pretending to be one.
	if net != null and net.guest:
		net.ask("wait")
		return
	if busy():
		return
	say("Du wartest.")
	# Said out loud as well as written down. On an empty floor a passed
	# turn changes nothing that can be seen - no step, no damage, often
	# not even a point of health - so the button looked broken, and was
	# reported as broken. It was doing exactly what it was asked to.
	banner("Warten …", Color(0.72, 0.80, 0.94))
	audio.play("wait")
	_tick_poison()
	_tick_regen()
	_tick_buffs()
	if dead:
		return
	enemy_turn()
	recompute_fov()
	paint()


## Walks to the next kind of flask carried. Costs no turn: choosing what
## to drink is not an action, drinking it is.
func cycle_potion() -> void:
	if player.potions <= 0:
		return
	player.selected_potion = player.next_potion()
	audio.play("equip")

func say(line: String) -> void:
	log_lines.append(line)
	while log_lines.size() > 6:
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
		elif cell == up_stairs and depth > 1 and _tile_ids.has("floor_ladder"):
			name = "floor_ladder"
		if name == "" or not _tile_ids.has(name):
			continue
		var layer := _floor_layer if lit.has(cell) else _dim_layer
		layer.set_cell(cell, _tile_ids[name], Vector2i.ZERO)

	var tint: Color = tier.get("tint", Color.WHITE)
	_floor_layer.modulate = tint
	# Remembered but unlit ground: still drawn, but colder and darker
	# than what the lamp reaches. With the light on top, this no longer
	# has to carry the whole difference by itself.
	_dim_layer.modulate = tint * Color(0.52, 0.52, 0.66)

	for item in items:
		_place_item(item)
	if chest != null and not chest.get("gone", false):
		_place_prop(chest["cell"], "chest_empty_open_anim_f2" if chest["opened"]
			else "chest_full_open_anim_f0")
	for cell in hazards:
		_place_prop(cell, Data.HAZARDS[hazards[cell]]["tile"])
	for cell in webs:
		_place_prop(cell, "wall_goo")
	# On an easy run a trap is something to walk around rather than
	# something to discover, so it is drawn as soon as the light reaches
	# it. On every other difficulty it stays exactly what it was: a floor
	# tile that turns out not to be one.
	if Data.difficulty_by_id(difficulty).get("traps_seen", false):
		for cell in traps:
			if lit.has(cell):
				_place_prop(cell, "floor_spikes_anim_f0")
	for cell in doors:
		_place_prop(cell, "doors_leaf_open" if doors[cell] else "doors_leaf_closed")
		# A door is part of the floor plan, so it stays on the map once
		# seen - dimmed, like the walls around it.
		var leaf: Sprite2D = _item_nodes.get("prop:%s" % str(cell))
		if leaf != null:
			leaf.visible = explored.has(cell)
			leaf.modulate = (Color.WHITE if lit.has(cell)
				else Color(0.52, 0.52, 0.66))
	for cell in decor:
		_place_prop(cell, decor[cell])
		if decor[cell].begins_with("wall_banner"):
			var cloth: Sprite2D = _item_nodes.get("prop:%s" % str(cell))
			if cloth != null:
				cloth.position.y -= TILE * 0.5
	if captive != null:
		_place_prop(captive, "knight_m_idle_anim_f0")
	if shrine != null:
		# A column: the only thing in the tileset that reads as
		# something built rather than dropped.
		_place_prop(shrine, "column")
	for shop in shops:
		_place_prop(shop["cell"], "blacksmith" if shop["kind"] == "smith" else "merchant")
	for monster in monsters:
		_place_monster(monster)
	_paint_mates()

	# One repaint means one action has just finished, so this is where the
	# others get told what happened. Cheap when alone: the pulse returns at
	# once if nobody else is connected.
	if net != null and net.hosting:
		net.pulse()

	_stand_on(_hero_node, Vector2i(player.x, player.y), HERO_TILES, true)
	_shadow_for(_hero_node, Vector2i(player.x, player.y), TILE * 1.35)
	if _torch != null:
		_torch.position = Vector2(player.x, player.y) * TILE + Vector2(TILE, TILE) * 0.5
	if _stairs_light != null:
		_stairs_light.position = Vector2(stairs) * TILE + Vector2(TILE, TILE) * 0.5
		# Only once the stairs have been seen: a light on something
		# nobody has found yet gives it away.
		_stairs_light.visible = explored.has(stairs)
	_hero_node.flip_h = player.facing < 0
	_camera_to = Vector2(player.x, player.y) * TILE + Vector2(TILE, TILE) * 0.5
	if _camera.position.distance_to(_camera_to) > TILE * 6.0:
		_camera.position = _camera_to


func _tile_for(x: int, y: int) -> String:
	if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
		return ""
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
	# Loot stays remembered once seen - a coin you walked past is a
	# fact about the floor, not a thing that moves - but only after
	# it has actually been in the light once.
	sprite.visible = lit.has(cell) or _seen_items.has(cell)
	if lit.has(cell):
		_seen_items[cell] = true
	sprite.modulate = Color.WHITE if lit.has(cell) else Color(0.55, 0.55, 0.68)


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
## Takes a piece of scenery off the floor for good.
##
## paint() only ever adds: it draws what is there and leaves everything
## else where it is. So something that stops existing has to say so, or
## its picture stays on the map for the rest of the floor.
func _forget_prop(cell: Vector2i) -> void:
	var key := "prop:%s" % str(cell)
	if not _item_nodes.has(key):
		return
	var sprite: Sprite2D = _item_nodes[key]
	if is_instance_valid(sprite):
		sprite.queue_free()
	_item_nodes.erase(key)


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
	# Standing things are only visible where the light reaches. What is
	# remembered is the shape of the room, not who is in it - a trader
	# glowing in the dark on the other side of the floor gives away
	# something nobody has seen yet.
	sprite.visible = lit.has(cell)


## Puts a sprite on a cell at a given height in tiles: scaled to that
## height, centred left to right, and standing on the floor of the cell
## rather than hanging from its top. Everything taller than one tile -
## monsters, shopkeepers, the hero - overlaps the wall behind it, which
## is exactly how the pygame build looks.
func _stand_on(sprite: Sprite2D, cell: Vector2i, tiles: float, glide := false) -> void:
	var texture := sprite.texture
	if texture == null:
		return
	var height := float(texture.get_height())
	var factor := (TILE * tiles) / height if height > 0.0 else 1.0
	sprite.scale = Vector2(factor, factor)
	var width := float(texture.get_width()) * factor
	var where := Vector2(cell) * TILE + Vector2(
		(TILE - width) * 0.5, TILE - height * factor)
	# Things that walk slide to their new cell over the next few
	# frames; everything else is simply put down. A step that snaps
	# reads as a teleport, and the game is nothing but steps.
	if not glide:
		_gliding.erase(sprite)
		sprite.position = where
		return
	# Far enough that it cannot be a step - a new floor, a blink -
	# so there is nothing to glide along.
	if sprite.position.distance_to(where) > TILE * 3.0:
		sprite.position = where
		_gliding.erase(sprite)
		return
	_gliding[sprite] = where


func _place_monster(monster) -> void:
	if not _actor_nodes.has(monster):
		var node := Sprite2D.new()
		node.texture = _sprite_for(monster.sprite)
		node.centered = false
		node.z_index = 2
		add_child(node)
		_actor_nodes[monster] = node

		# A bar over the head, shown only once something has hurt it.
		# Without it a fight is a guess: the log says numbers, but
		# whether the thing in front of you is nearly dead is the one
		# thing you actually want to know.
		# Two rectangles: the dark one is the whole bar, so what is
		# missing can be seen as well as what is left. Both are drawn
		# unshaded - a health bar that goes dark with the room is a
		# health bar that cannot be read in the only place it matters.
		var unlit := CanvasItemMaterial.new()
		unlit.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
		var track := ColorRect.new()
		track.name = "healthtrack"
		track.color = Color(0.06, 0.05, 0.06, 0.85)
		track.material = unlit
		track.visible = false
		node.add_child(track)
		# And a name, for the ones that have one worth reading. Not for
		# ordinary monsters: five rats in a room would put the word "Ratte"
		# on the screen five times, and the picture already says rat.
		var plate := Label.new()
		plate.name = "nameplate"
		plate.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
		plate.material = unlit
		plate.visible = false
		node.add_child(plate)

		var bar := ColorRect.new()
		bar.name = "health"
		bar.color = Color(0.85, 0.25, 0.25)
		bar.material = unlit
		bar.visible = false
		node.add_child(bar)
	var sprite: Sprite2D = _actor_nodes[monster]
	_stand_on(sprite, monster.cell(),
		MONSTER_TILES * (BOSS_SCALE if monster.is_boss else 1.0), true)
	_shadow_for(sprite, monster.cell(), TILE * (2.4 if monster.is_boss else 1.45))
	sprite.flip_h = monster.x > player.x
	sprite.visible = lit.has(monster.cell())
	# Asleep is worth seeing: it is the difference between walking
	# past something and waking it.
	# Asleep is pale; an elite wears a tint of its own so a familiar
	# silhouette that is about to hit twice as hard looks different from
	# the one that is not.
	# self_modulate, not modulate: the second one runs down into the
	# health bar as well, and a sleeping monster would hand its own bar
	# the same pale wash that says "asleep".
	if not monster.awake:
		sprite.self_modulate = Color(0.62, 0.62, 0.78)
	elif monster.is_boss:
		sprite.self_modulate = Color(1.0, 0.80, 0.70)
	elif monster.is_keeper:
		sprite.self_modulate = Color(0.85, 0.95, 1.0)
	elif monster.is_elite:
		sprite.self_modulate = Color(1.0, 0.92, 0.55)
	else:
		sprite.self_modulate = monster.tint

	var bar: ColorRect = sprite.get_node_or_null("health")
	var track: ColorRect = sprite.get_node_or_null("healthtrack")
	if bar != null and track != null:
		# Shown once something is hurt, and always for a boss or an
		# elite: with those, knowing how far along the fight is matters
		# from the first swing.
		var shown: bool = monster.hp < monster.max_hp or monster.is_boss or monster.is_elite
		bar.visible = shown
		track.visible = shown
		if shown:
			# In the sprite's own coordinates, so the scale that makes a
			# boss large makes its bar wide to match. Sitting on the head
			# rather than floating over it: at three tiles tall a bar six
			# pixels up is a hand's breadth of empty air.
			var art: Rect2 = _art_rect(sprite.texture)
			var span: float = art.size.x
			var left: float = clampf(float(monster.hp) / float(maxi(1, monster.max_hp)), 0.0, 1.0)
			var thick: float = (4.0 if monster.is_boss else 3.0) / sprite.scale.y
			var top: float = art.position.y - thick - 2.0 / sprite.scale.y
			var edge := Vector2(1.0 / sprite.scale.x, 1.0 / sprite.scale.y)
			track.position = Vector2(art.position.x - edge.x, top - edge.y)
			track.size = Vector2(span + edge.x * 2.0, thick + edge.y * 2.0)
			bar.position = Vector2(art.position.x, top)
			bar.size = Vector2(span * left, thick)

			var plate: Label = sprite.get_node_or_null("nameplate")
			if plate != null:
				# A boss is named wherever it stands. An elite only close up:
				# six of them across a room put six lines of text over the
				# floor and hid the fight underneath.
				var close: bool = absi(monster.x - player.x) + absi(monster.y - player.y) <= 4
				plate.visible = monster.is_boss or ((monster.is_elite or monster.is_keeper) and close)
				if plate.visible:
					# The label hangs off the sprite, and the sprite is scaled to
					# fill its tiles - a boss by two and a half. Left alone the
					# name is scaled with it and ends up bigger than the monster,
					# which is exactly what it did. So the label carries the
					# inverse scale and a fixed size in real pixels.
					const PLATE_W := 220.0
					const PLATE_H := 20.0
					# Against the sprite scale *and* the camera zoom: both magnify
					# whatever is drawn in the world, and a name is meant to be
					# the same size on the screen no matter how far the view is
					# zoomed in or how large the thing wearing it is.
					var magnified: float = _camera.zoom.x if _camera != null else 1.0
					var back := Vector2(1.0 / (sprite.scale.x * magnified),
						1.0 / (sprite.scale.y * magnified))
					plate.scale = back
					plate.size = Vector2(PLATE_W, PLATE_H)
					plate.add_theme_font_size_override("font_size", 15)
					plate.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
					plate.add_theme_constant_override("outline_size", 5)
					plate.add_theme_color_override("font_color",
						Color(1.0, 0.72, 0.55) if monster.is_boss else Color(1.0, 0.92, 0.62))
					plate.text = monster.display_name
					# Centred over the art and sitting on top of the bar, both
					# worked out in the sprite's coordinates.
					plate.position = Vector2(
						art.position.x + art.size.x * 0.5 - PLATE_W * back.x * 0.5,
						top - edge.y - PLATE_H * back.y)

			if monster.is_boss:
				bar.color = Color(1.0, 0.45, 0.25)
			else:
				bar.color = Color(0.86, 0.26, 0.24) if left < 0.35 else Color(0.88, 0.55, 0.22)


# --- the panel ------------------------------------------------------------

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	_hud = Control.new()
	_hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.theme = _button_look()
	layer.add_child(_hud)

	# Everything the player uses while walking lives in one node, so
	# the title screen can put it away with a single flag instead of
	# leaving a d-pad and a health bar showing through the menu.
	_play_ui = Control.new()
	_play_ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	_play_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_play_ui)

	_flash = ColorRect.new()
	_flash.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash.color = Color(0.75, 0.10, 0.12, 0.0)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_play_ui.add_child(_flash)

	for name in ["stats", "gear", "fps", "log"]:
		var label := Label.new()
		label.name = name
		label.add_theme_font_size_override("font_size", 22)
		label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
		label.add_theme_constant_override("outline_size", 5)
		label.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
		_play_ui.add_child(label)
	_play_ui.get_node("stats").position = Vector2(14, 4)
	# Two lines, because one did not fit: at 1280 wide the gear names
	# pushed the buff row off the right-hand edge, where a player has no
	# way to know it exists.
	_play_ui.get_node("gear").position = Vector2(14, 82)
	_play_ui.get_node("fps").position = Vector2(14, 190)

	var log_label: Label = _play_ui.get_node("log")
	log_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	log_label.position = Vector2(-660, -300)
	log_label.custom_minimum_size = Vector2(640, 190)
	log_label.add_theme_color_override("font_color", Color(0.80, 0.80, 0.86))

	var pad := 28.0
	var size := 120.0
	# The thumbstick owns the left of the screen and appears wherever
	# the thumb lands: held in landscape there is no one corner that
	# suits every hand. The four-button pad is still there for anyone
	# who prefers it, but off by default - four directions is most of
	# what makes a game feel nailed to a grid.
	_stick = Stick.new()
	# Anchored down the left edge and given a width by offset rather
	# than by size: a control with opposite anchors that disagree has
	# its size overwritten after _ready, and Godot says so every run.
	_stick.set_anchors_preset(Control.PRESET_LEFT_WIDE)
	_stick.offset_right = 620
	_play_ui.add_child(_stick)

	# Nine squares with the middle left out, so the pad can walk
	# everywhere the stick can.
	#
	# It had four buttons while the setting offered eight directions,
	# which made "8 (diagonal)" a promise the pad could not keep. The
	# corners are hidden again when four directions are chosen - a
	# button that is refused the moment it is pressed is worse than no
	# button.
	var middle := Vector2(pad + size * 1.5, -pad - size * 2.1)
	_button("^", middle + Vector2(0, -size), size, Vector2i(0, -1))
	_button("v", middle + Vector2(0, size), size, Vector2i(0, 1))
	_button("<", middle + Vector2(-size, 0), size, Vector2i(-1, 0))
	_button(">", middle + Vector2(size, 0), size, Vector2i(1, 0))
	_corner_buttons.append(_button("↖", middle + Vector2(-size, -size), size,
		Vector2i(-1, -1)))
	_corner_buttons.append(_button("↗", middle + Vector2(size, -size), size,
		Vector2i(1, -1)))
	_corner_buttons.append(_button("↙", middle + Vector2(-size, size), size,
		Vector2i(-1, 1)))
	_corner_buttons.append(_button("↘", middle + Vector2(size, size), size,
		Vector2i(1, 1)))
	_apply_control_style()

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

	_shoot_button = Button.new()
	_shoot_button.text = "SCHIESSEN"
	_shoot_button.custom_minimum_size = Vector2(size * 1.6, size * 0.7)
	_shoot_button.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_shoot_button.position = Vector2(-pad - size * 1.6, -pad - size * 1.65)
	_shoot_button.add_theme_font_size_override("font_size", 24)
	_shoot_button.pressed.connect(shoot)
	_shoot_button.visible = false
	_play_ui.add_child(_shoot_button)

	# One button, two jobs, and the label says which.
	#
	# Waiting is not a fight move: standing still next to something
	# awake hands it a free hit and you still have to swing afterwards.
	# So while something is in reach the same button hits it, and while
	# nothing is, it waits.
	_rest_button = Button.new()
	_rest_button.text = "WARTEN"
	_rest_button.custom_minimum_size = Vector2(size * 1.4, size * 0.6)
	_rest_button.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_rest_button.position = Vector2(-pad - size * 3.8, pad)
	_rest_button.add_theme_font_size_override("font_size", 24)
	_rest_button.pressed.connect(rest_or_attack)
	_play_ui.add_child(_rest_button)

	var bag := Button.new()
	bag.text = "TASCHE"
	bag.custom_minimum_size = Vector2(size * 1.2, size * 0.6)
	bag.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	bag.position = Vector2(-pad - size * 2.3, pad)
	bag.add_theme_font_size_override("font_size", 24)
	bag.pressed.connect(open_bag)
	_play_ui.add_child(bag)

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

	# The two bars are the pause sign everyone knows. The button they
	# belong on is this one: in a game that waits for your move, the menu
	# is the only thing that pauses anything - "warten" spends a turn on
	# purpose, which is the opposite.
	var again := Button.new()
	again.text = "▮▮ MENÜ"
	again.custom_minimum_size = Vector2(size, size * 0.6)
	again.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	again.position = Vector2(-pad - size, pad)
	again.add_theme_font_size_override("font_size", 20)
	again.pressed.connect(open_pause)
	_play_ui.add_child(again)

	_banner = Label.new()
	_banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_banner.position = Vector2(-400, 150)
	_banner.custom_minimum_size = Vector2(800, 60)
	_banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner.add_theme_font_size_override("font_size", 40)
	_banner.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_banner.add_theme_constant_override("outline_size", 8)
	_banner.modulate.a = 0.0
	_play_ui.add_child(_banner)

	_build_gauges()
	_build_vignette()
	_build_minimap()
	_build_bag_panel()
	_build_pause_panel()
	_build_awards_panel()
	_build_kin_panel()
	_build_shop_panel()
	_build_perk_panel()
	_build_dead_panel()
	_build_setup_panel()
	_build_stats_panel()
	_build_attack_hint()
	_build_level_panel()
	_build_options_panel()
	_build_info_panel()
	_build_party_panel()
	_build_title_panel()


## One look for every button in the game.
##
## Godot's default button is a grey slab from a different program: it has
## nothing to do with a torchlit dungeon of brick and old gold, and next
## to the tileset it reads as a bug report window. This is the same warm
## dark stone the panels are made of, with a brass edge that brightens
## under a finger and glows when it is pressed.
##
## Set once on the HUD, so every button inside inherits it - including
## the ones built later, which is most of them.
func _button_look() -> Theme:
	var look := Theme.new()

	var resting := StyleBoxFlat.new()
	resting.bg_color = Color(0.16, 0.13, 0.17)
	resting.border_color = Color(0.56, 0.42, 0.24)
	resting.set_border_width_all(2)
	resting.set_corner_radius_all(8)
	resting.set_content_margin_all(10)
	look.set_stylebox("normal", "Button", resting)

	var under_finger: StyleBoxFlat = resting.duplicate()
	under_finger.bg_color = Color(0.24, 0.19, 0.24)
	under_finger.border_color = Color(0.86, 0.68, 0.32)
	look.set_stylebox("hover", "Button", under_finger)

	var pushed: StyleBoxFlat = resting.duplicate()
	pushed.bg_color = Color(0.40, 0.29, 0.14)
	pushed.border_color = Color(1.0, 0.82, 0.42)
	pushed.set_border_width_all(3)
	look.set_stylebox("pressed", "Button", pushed)

	# A button nobody can press has to look like one. The old theme said so
	# only with a slightly paler word.
	var refused: StyleBoxFlat = resting.duplicate()
	refused.bg_color = Color(0.11, 0.10, 0.12)
	refused.border_color = Color(0.30, 0.27, 0.30)
	look.set_stylebox("disabled", "Button", refused)

	var edged: StyleBoxFlat = resting.duplicate()
	edged.border_color = Color(1.0, 0.86, 0.50)
	look.set_stylebox("focus", "Button", edged)

	look.set_color("font_color", "Button", Color(0.94, 0.91, 0.85))
	look.set_color("font_hover_color", "Button", Color(1.0, 0.95, 0.80))
	look.set_color("font_pressed_color", "Button", Color(1.0, 0.88, 0.52))
	look.set_color("font_disabled_color", "Button", Color(0.48, 0.46, 0.50))
	look.set_color("font_outline_color", "Button", Color(0, 0, 0, 0.85))
	look.set_constant("outline_size", "Button", 3)
	return look


## A flat rectangle of colour, positioned by hand.
##
## The HUD is built in code rather than in a scene, so a bar is four of
## these stacked: a dark frame, the empty track, what is left, and the
## number over the top. Nothing here reacts to the theme - a health bar
## that changes colour with the floor is a health bar nobody trusts.
func _plate(at: Vector2, span: Vector2, shade: Color, top := false) -> ColorRect:
	var rect := ColorRect.new()
	if top:
		rect.set_anchors_preset(Control.PRESET_CENTER_TOP)
	rect.position = at
	rect.size = span
	rect.color = shade
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_play_ui.add_child(rect)
	return rect


func _gauge_label(at: Vector2, span: Vector2, size: int, top := false) -> Label:
	var label := Label.new()
	if top:
		label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	label.position = at
	label.size = span
	label.custom_minimum_size = span
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 5)
	_play_ui.add_child(label)
	return label


## Health as a bar rather than as two numbers.
##
## "HP 7/24" is something you read; a bar a quarter full is something you
## see, and in a fight there is no time to read. The experience bar under
## it is there for the same reason - the moment before a level is worth
## knowing, and it was buried in a row of figures.
func _build_gauges() -> void:
	_hp_frame = _plate(Vector2(12, 36), Vector2(GAUGE_W + 4, GAUGE_H + 4), Color(0, 0, 0, 0.80))
	_plate(Vector2(14, 38), Vector2(GAUGE_W, GAUGE_H), Color(0.13, 0.09, 0.11, 0.92))
	# The pale strip is the damage that has just landed. It drains away
	# over about a second, so a hit is visible as a loss and not only as a
	# smaller bar.
	_hp_ghost = _plate(Vector2(14, 38), Vector2(GAUGE_W, GAUGE_H), Color(0.96, 0.86, 0.58, 0.50))
	_hp_fill = _plate(Vector2(14, 38), Vector2(GAUGE_W, GAUGE_H), Color(0.35, 0.72, 0.35))
	# A shield is not health: it sits past the end of the bar, in its own
	# colour, and goes first.
	_hp_guard = _plate(Vector2(14, 38), Vector2(0, GAUGE_H), Color(0.48, 0.78, 1.0, 0.88))
	_hp_text = _gauge_label(Vector2(14, 38), Vector2(GAUGE_W, GAUGE_H), 20)

	_plate(Vector2(12, 66), Vector2(GAUGE_W + 4, 12), Color(0, 0, 0, 0.80))
	_plate(Vector2(14, 68), Vector2(GAUGE_W, 8), Color(0.10, 0.10, 0.14, 0.92))
	_xp_fill = _plate(Vector2(14, 68), Vector2(0, 8), Color(0.62, 0.55, 0.95))

	# What is running on the hero, as six little plates rather than a
	# line of text.
	#
	# "[Hast 12, Kraft 4]" is a sentence to read; a plate that is running
	# out is something to see. The bar is the share of that buff's own
	# longest run, so a twenty-five turn blessing and a four turn
	# scramble both start full and both empty at the same rate they
	# actually expire.
	#
	# Turns, not seconds: a turn happens when you make it happen, so a
	# buff on a clock would punish standing still to think - which is
	# the one thing this kind of game is made of.
	_buff_chips.clear()
	for at in 6:
		var left := 14.0 + float(at) * 116.0
		var chip := {}
		chip["frame"] = _plate(Vector2(left, 108), Vector2(112, 26), Color(0, 0, 0, 0.80))
		chip["track"] = _plate(Vector2(left + 2, 110), Vector2(108, 22), Color(0.12, 0.11, 0.16, 0.95))
		chip["fill"] = _plate(Vector2(left + 2, 110), Vector2(108, 22), Color(0.36, 0.52, 0.86, 0.70))
		chip["text"] = _gauge_label(Vector2(left + 2, 110), Vector2(108, 22), 16)
		_buff_chips.append(chip)

	# A boss gets the top of the screen. Something with four hundred hit
	# points needs a bar you can watch from across the room, and a name -
	# otherwise the only sign that this one is different is that it is not
	# dying.
	_boss_frame = _plate(Vector2(-BOSS_W * 0.5 - 3, 149), Vector2(BOSS_W + 6, 26),
		Color(0, 0, 0, 0.80), true)
	_boss_track = _plate(Vector2(-BOSS_W * 0.5, 152), Vector2(BOSS_W, 20),
		Color(0.14, 0.08, 0.08, 0.92), true)
	_boss_fill = _plate(Vector2(-BOSS_W * 0.5, 152), Vector2(BOSS_W, 20),
		Color(0.86, 0.26, 0.20), true)
	_boss_text = _gauge_label(Vector2(-BOSS_W * 0.5, 152), Vector2(BOSS_W, 20), 19, true)
	_boss_text.add_theme_color_override("font_color", Color(1.0, 0.92, 0.86))


## The row of buff plates: one per effect, longest first, six at most.
##
## Poison and bleeding are in there too. They are not buffs, but they
## run on the same clock and they are the two the player most wants to
## see counting down.
func _refresh_chips() -> void:
	if _buff_chips.is_empty() or player == null:
		return
	var running: Array = []
	for id in player.buffs:
		running.append({"id": id, "name": str(Data.BUFFS[id]["name"]),
			"turns": int(player.buffs[id]), "shade": Color(0.36, 0.52, 0.86, 0.70)})
	if player.poison_turns > 0:
		running.append({"id": "poison", "name": "Gift", "turns": player.poison_turns,
			"shade": Color(0.42, 0.72, 0.34, 0.70)})
	if player.bleed_turns > 0:
		running.append({"id": "bleed", "name": "Blutung", "turns": player.bleed_turns,
			"shade": Color(0.80, 0.28, 0.28, 0.70)})
	running.sort_custom(func(a, b): return a["turns"] > b["turns"])

	# What has stopped running loses its remembered length, or the next
	# potion of the same kind starts its bar half empty.
	var alive := {}
	for entry in running:
		alive[entry["id"]] = true
	for id in _buff_peak.keys():
		if not alive.has(id):
			_buff_peak.erase(id)

	for at in _buff_chips.size():
		var chip: Dictionary = _buff_chips[at]
		var showing: bool = at < running.size()
		chip["frame"].visible = showing
		chip["track"].visible = showing
		chip["fill"].visible = showing
		chip["text"].visible = showing
		if not showing:
			continue
		var entry: Dictionary = running[at]
		var peak: int = maxi(int(_buff_peak.get(entry["id"], 0)), int(entry["turns"]))
		_buff_peak[entry["id"]] = peak
		chip["fill"].size.x = 108.0 * clampf(
			float(entry["turns"]) / float(maxi(1, peak)), 0.0, 1.0)
		chip["fill"].color = entry["shade"]
		chip["text"].text = "%s %d" % [entry["name"], int(entry["turns"])]


## Moves the bars to where the numbers already are. Called every frame,
## because the trailing damage strip is the only thing here that is not
## simply a division.
func _refresh_gauges(delta: float) -> void:
	if _hp_fill == null or player == null:
		return
	var left: float = clampf(float(player.hp) / float(maxi(1, player.max_hp)), 0.0, 1.0)
	var want: float = GAUGE_W * left
	_hp_fill.size.x = want
	# Green while it does not matter, amber when it starts to, red when it
	# does. Colour is what an eye that is watching the monster still
	# notices.
	if left > 0.55:
		_hp_fill.color = Color(0.35, 0.72, 0.35)
	elif left > 0.28:
		_hp_fill.color = Color(0.90, 0.68, 0.22)
	else:
		_hp_fill.color = Color(0.84, 0.22, 0.22)
	if _hp_ghost.size.x <= want:
		_hp_ghost.size.x = want
	else:
		_hp_ghost.size.x = maxf(want, _hp_ghost.size.x - GAUGE_W * 0.55 * delta)
	var guard: float = clampf(float(player.shield) / float(maxi(1, player.max_hp)), 0.0, 1.0)
	_hp_guard.position.x = 14.0 + want
	_hp_guard.size.x = minf(GAUGE_W - want, GAUGE_W * guard)
	_hp_text.text = "%d / %d" % [maxi(0, player.hp), player.max_hp]
	if player.shield > 0:
		_hp_text.text += "   +%d" % player.shield
	# Under a quarter left the frame breathes red. Nothing written in the
	# log has ever caught anyone mid-fight.
	if left <= 0.25:
		_hp_frame.color = Color(0.88, 0.16, 0.16, 0.50 + 0.35 * sin(_flicker * 6.0))
	else:
		_hp_frame.color = Color(0, 0, 0, 0.80)
	_xp_fill.size.x = GAUGE_W * clampf(
		float(player.xp) / float(maxi(1, player.xp_to_next)), 0.0, 1.0)

	_refresh_chips()

	var boss = null
	for monster in monsters:
		if monster.is_alive() and monster.is_boss and monster.awake \
				and lit.has(monster.cell()):
			boss = monster
			break
	var showing: bool = boss != null
	_boss_frame.visible = showing
	_boss_track.visible = showing
	_boss_fill.visible = showing
	_boss_text.visible = showing
	if showing:
		_boss_fill.size.x = BOSS_W * clampf(
			float(boss.hp) / float(maxi(1, boss.max_hp)), 0.0, 1.0)
		_boss_text.text = "%s   %d / %d" % [boss.display_name, maxi(0, boss.hp), boss.max_hp]


# --- playing together -----------------------------------------------------

## A guest who has fallen, put back on their feet beside the host.
##
## The alternative is that one person's bad step ends the run for
## everyone at the table, which is a punishment nobody agreed to. A
## quarter of their health and everything they were carrying: enough to
## keep going, little enough that it hurt.
func _pick_guest_up() -> void:
	var fallen = player
	fallen.hp = maxi(1, fallen.max_hp / 4)
	fallen.poison_turns = 0
	fallen.bleed_turns = 0
	var spot: Vector2i = _room_for_one(Vector2i(party[1].x, party[1].y))
	fallen.x = spot.x
	fallen.y = spot.y
	fallen.snap()
	audio.play("player_hurt")
	say("Ein Mitspieler ist gefallen und kommt zurück zum Gastgeber.")


## A hero for someone who has just connected.
##
## Built here rather than there: everything that can affect the floor is
## decided by the machine that owns the floor. A guest that rolled its own
## hero would be a guest that rolled its own strength.
func spawn_guest(peer: int) -> Variant:
	var arrival = Entities.Player.new(Data.DEFAULT_CLASS, difficulty)
	arrival.auto_shoot = true
	var spot: Vector2i = _room_for_one(Vector2i(player.x, player.y))
	arrival.x = spot.x
	arrival.y = spot.y
	arrival.snap()
	say("Ein Mitspieler betritt den Dungeon.")
	return arrival


## Somewhere free next to a given cell, or that cell if the room is full.
func _room_for_one(near: Vector2i) -> Vector2i:
	for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
			Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]:
		var at: Vector2i = near + offset
		if Dungeon.is_walkable(grid, at.x, at.y) and not blocks(at) \
				and not occupied(at) and _hero_at(at) == null:
			return at
	return near


func remove_guest(peer: int) -> void:
	say("Ein Mitspieler ist gegangen.")


## Runs one guest's action as if it were the hero standing here.
##
## The whole game is written around a single `player`, and rewriting all
## of it to carry a hero through every call would be a month of work and a
## thousand chances to get it wrong. So the acting hero is swapped in for
## the length of the action and swapped back out afterwards. Everything -
## walking, fighting, drinking, the monsters' turn - then happens to the
## right person without a single rule having to know that anyone else
## exists.
##
## The cost is honest and worth naming: monsters chase and hit whoever
## just moved. Standing still is safe in a way it should not be. That is
## the next thing to fix, not a thing to pretend is a feature.
func guest_acts(peer: int, what: String, step: Vector2i) -> void:
	if not party.has(peer) or dead or choosing:
		return
	if what.begins_with("class:"):
		_dress_guest(peer, what.substr(6))
		return
	var was = player
	var was_deep: int = depth
	_acting_peer = peer
	player = party[peer]
	match what:
		"move":
			try_move(step)
		"wait":
			wait_a_turn()
		"shoot":
			shoot()
		"drink":
			drink()
	party[peer] = player
	_acting_peer = 1
	player = was
	# A staircase takes the whole party with it. Anything else would be one
	# player alone on a floor nobody else can reach.
	if depth != was_deep:
		_gather_party()
		net.send_floor()
	recompute_fov()
	paint()


## The class a guest picked on their own title screen. The hero is rebuilt
## rather than edited: a class is a starting hand - health, kit, reach -
## and half of it applied would be a hero nobody designed.
func _dress_guest(peer: int, id: String) -> void:
	var known := false
	for entry in Data.CLASSES:
		if entry["id"] == id:
			known = true
			break
	if not known:
		return
	var where: Vector2i = Vector2i(party[peer].x, party[peer].y)
	var fresh = Entities.Player.new(id, difficulty)
	fresh.auto_shoot = true
	fresh.x = where.x
	fresh.y = where.y
	fresh.snap()
	party[peer] = fresh
	net.names[peer] = Data.class_by_id(id)["name"]
	net.party_changed.emit()
	say("%s schließt sich an." % Data.class_by_id(id)["name"])
	net.send_floor(peer)
	net.pulse()


## Everybody onto the staircase after somebody used it.
func _gather_party() -> void:
	var arrival := Vector2i(player.x, player.y)
	for peer in party:
		if peer == 1:
			continue
		var spot: Vector2i = _room_for_one(arrival)
		party[peer].x = spot.x
		party[peer].y = spot.y
		party[peer].snap()


## The whole floor, as the save file writes it. One serialiser for the
## disk and the wire: a field added for one and forgotten for the other is
## how a guest ends up walking through a wall that is there.
func floor_for_network() -> Dictionary:
	var plan: Dictionary = Save.floor_data(self)
	plan["explored"] = []
	for cell in explored:
		plan["explored"].append([cell.x, cell.y])
	return plan


## What has moved since the last action.
func pulse_for_network() -> Dictionary:
	var heroes: Array = []
	for peer in party:
		var hero = party[peer]
		heroes.append({
			"peer": peer, "class": hero.hero_class, "x": hero.x, "y": hero.y,
			"hp": hero.hp, "max_hp": hero.max_hp, "level": hero.level,
			"xp": hero.xp, "next": hero.xp_to_next, "gold": hero.gold,
			"shield": hero.shield, "potions": hero.potions,
			"weapon": hero.weapon, "armour": hero.armour,
			"poison": hero.poison_turns, "bleed": hero.bleed_turns,
		})

	var beasts: Array = []
	for monster in monsters:
		if not monster.is_alive():
			continue
		if monster.net_id == 0:
			_net_ids += 1
			monster.net_id = _net_ids
		beasts.append({
			"i": monster.net_id, "kind": monster.kind, "x": monster.x, "y": monster.y,
			"hp": monster.hp, "max_hp": monster.max_hp, "awake": monster.awake,
			"name": monster.display_name, "boss": monster.is_boss,
			"elite": monster.is_elite, "keeper": monster.is_keeper,
		})

	var loot: Array = []
	for item in items:
		loot.append({"x": item["cell"].x, "y": item["cell"].y, "kind": item["kind"],
			"amount": item.get("amount", 0), "potion": item.get("potion", ""),
			"scroll": item.get("scroll", "")})

	var gates: Array = []
	for cell in doors:
		gates.append([cell.x, cell.y, doors[cell]])

	var tail: Array = []
	var from: int = maxi(0, log_lines.size() - Net.LOG_TAIL)
	for at in range(from, log_lines.size()):
		tail.append(log_lines[at])

	return {
		"depth": depth, "heroes": heroes, "monsters": beasts, "items": loot,
		"doors": gates, "log": tail, "over": dead,
		"chest": null if chest == null else [chest["cell"].x, chest["cell"].y,
			chest["opened"], chest.get("gone", false)],
	}


# --- and what a guest does with it ----------------------------------------

## A whole floor has arrived. The same code the save file goes through,
## because it is the same dictionary.
func apply_network_floor(plan: Dictionary) -> void:
	choosing = false
	_run_over = false
	depth = int(plan.get("depth", 1))
	_clear_level_nodes()
	_apply_floor(plan)
	if _play_ui != null:
		_play_ui.visible = true
	if _title_panel != null:
		_title_panel.visible = false
	_by_net_id.clear()
	recompute_fov()
	paint()


## One beat of the world. Everything that moves is replaced from what the
## host says; everything that does not - walls, the shape of the floor -
## is left exactly as it was.
func apply_network_pulse(beat: Dictionary) -> void:
	if player == null:
		return
	depth = int(beat.get("depth", depth))
	tier = Data.tier_for(depth)

	_mates.clear()
	var mine: int = multiplayer.get_unique_id()
	for entry in beat.get("heroes", []):
		if int(entry["peer"]) == mine:
			_wear(entry)
		else:
			_mates.append(entry)

	_take_monsters(beat.get("monsters", []))
	_take_items(beat.get("items", []))

	doors.clear()
	for gate in beat.get("doors", []):
		doors[Vector2i(int(gate[0]), int(gate[1]))] = bool(gate[2])

	var box: Variant = beat.get("chest")
	if box == null:
		chest = null
	else:
		chest = {"cell": Vector2i(int(box[0]), int(box[1])), "mimic": false,
			"opened": bool(box[2]), "gone": bool(box[3])}

	log_lines.clear()
	for line in beat.get("log", []):
		log_lines.append(str(line))

	recompute_fov()
	paint()


## The guest's own hero, as the host sees it. Only the numbers travel: the
## class was rolled once, on the host, and rerolling it every beat would
## hand out a new hero sixty times a minute.
func _wear(entry: Dictionary) -> void:
	if player.hero_class != str(entry["class"]):
		player = Entities.Player.new(str(entry["class"]), difficulty)
		hero_class = player.hero_class
		if _hero_node != null:
			_hero_node.texture = load(CLASS_DIR
				+ Data.class_by_id(player.hero_class)["sprite"] + ".png")
	player.x = int(entry["x"])
	player.y = int(entry["y"])
	player.hp = int(entry["hp"])
	player.max_hp = int(entry["max_hp"])
	player.level = int(entry["level"])
	player.xp = int(entry["xp"])
	player.xp_to_next = int(entry["next"])
	player.gold = int(entry["gold"])
	player.shield = int(entry["shield"])
	player.potions = int(entry["potions"])
	player.weapon = int(entry["weapon"])
	player.armour = int(entry["armour"])
	player.poison_turns = int(entry["poison"])
	player.bleed_turns = int(entry["bleed"])
	_run_over = false


## Monsters, matched up by their number rather than by their place in a
## list: one that died in the middle would otherwise shift every monster
## after it onto somebody else's sprite.
func _take_monsters(beasts: Array) -> void:
	var still_here := {}
	for entry in beasts:
		var id: int = int(entry["i"])
		still_here[id] = true
		var monster = _by_net_id.get(id)
		if monster == null:
			monster = Entities.Monster.new(str(entry["kind"]), 1.0, difficulty)
			monster.net_id = id
			_by_net_id[id] = monster
			monsters.append(monster)
			monster.x = int(entry["x"])
			monster.y = int(entry["y"])
			monster.snap()
		monster.x = int(entry["x"])
		monster.y = int(entry["y"])
		monster.hp = int(entry["hp"])
		monster.max_hp = int(entry["max_hp"])
		monster.awake = bool(entry["awake"])
		monster.display_name = str(entry["name"])
		monster.is_boss = bool(entry["boss"])
		monster.is_elite = bool(entry["elite"])
		monster.is_keeper = bool(entry["keeper"])
	for id in _by_net_id.keys():
		if still_here.has(id):
			continue
		var gone = _by_net_id[id]
		monsters.erase(gone)
		if _actor_nodes.has(gone):
			var sprite = _actor_nodes[gone]
			if _shadows.has(sprite):
				_shadows[sprite].queue_free()
				_shadows.erase(sprite)
			sprite.queue_free()
			_actor_nodes.erase(gone)
		_by_net_id.erase(id)


## Loot, rebuilt outright - there are rarely more than a dozen pieces, and
## a picture left behind for something somebody else picked up is worse
## than rebuilding a short list.
func _take_items(loot: Array) -> void:
	items.clear()
	var filled := {}
	for entry in loot:
		var cell := Vector2i(int(entry["x"]), int(entry["y"]))
		filled[cell] = true
		items.append({"cell": cell, "kind": str(entry["kind"]),
			"amount": int(entry["amount"]), "potion": str(entry["potion"]),
			"scroll": str(entry["scroll"])})
	for key in _item_nodes.keys():
		if typeof(key) != TYPE_VECTOR2I or filled.has(key):
			continue
		_item_nodes[key].queue_free()
		_item_nodes.erase(key)


## Everyone else in the party, as plain data.
##
## A guest is told about the others and keeps them in `_mates`. The host
## has them in `party` all along - and drew none of them, which is why
## the host could not see a single guest while every guest could see the
## host. One list, built from whichever end this is.
func _companions() -> Array:
	if net == null or not net.hosting:
		return _mates
	var others: Array = []
	for peer in party:
		if peer == 1:
			continue
		var hero = party[peer]
		others.append({"peer": peer, "class": hero.hero_class,
			"x": hero.x, "y": hero.y})
	return others


## The other heroes, drawn where the host last saw them.
func _paint_mates() -> void:
	var shown := {}
	for entry in _companions():
		var peer: int = int(entry["peer"])
		shown[peer] = true
		var cell := Vector2i(int(entry["x"]), int(entry["y"]))
		var info: Dictionary = Data.class_by_id(str(entry["class"]))
		var sprite: Sprite2D = _mate_nodes.get(peer)
		if sprite == null or not is_instance_valid(sprite):
			sprite = Sprite2D.new()
			sprite.centered = false
			sprite.z_index = 2
			add_child(sprite)
			_mate_nodes[peer] = sprite
		sprite.texture = load(CLASS_DIR + info["sprite"] + ".png")
		_stand_on(sprite, cell, HERO_TILES, true)
		_shadow_for(sprite, cell, TILE * 1.35)
		# A companion is only visible where your own torch reaches. Two
		# players in different rooms cannot see each other, which is the
		# whole reason to shout across one.
		sprite.visible = lit.has(cell)
		sprite.self_modulate = info.get("shade", Color.WHITE)
	for peer in _mate_nodes.keys():
		if shown.has(peer):
			continue
		if is_instance_valid(_mate_nodes[peer]):
			_mate_nodes[peer].queue_free()
		_mate_nodes.erase(peer)

## Hangs a dialog in the middle of the screen and keeps it there.
##
## Anchoring a panel to the centre and offsetting it by half its
## minimum size only works while the contents fit inside that minimum.
## The moment a longer potion name makes the panel wider, it grows to
## the right and the whole thing sits off-centre - which is exactly
## what the bag did. A CenterContainer has no such opinion.
func _centred(panel: Control) -> CenterContainer:
	var holder := CenterContainer.new()
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Over the title screen, whatever order things were built in. The
	# title panel is built last and paints a near-opaque wash over the
	# whole screen, so a dialog built before it came out looking like a
	# dialog behind frosted glass.
	holder.z_index = 10
	holder.add_child(panel)
	return holder


## A panel you cannot see through. The default theme panel is nearly
## transparent, which over a dungeon means the map runs straight through
## the buttons and the text sits on rubble.
func _solid_panel(panel: PanelContainer) -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.07, 0.06, 0.09, 1.0)
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
	_perk_panel.custom_minimum_size = Vector2(680, 360)
	_perk_panel.visible = false
	_solid_panel(_perk_panel)
	_hud.add_child(_centred(_perk_panel))

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
			button.text = "%s - %s" % [perk_choices[i]["name"], _perk_promise(perk_choices[i])]
	_perk_panel.visible = true


## What this gift would actually change, in the numbers you have now.
##
## The card used to read the same sentence for ever: "1 Leben alle 5
## Züge", whether it was your first Regeneration or your fourth. Taking
## it again then looked like it did nothing at all - it was making the
## ticks come faster, and nothing on the screen said so. A gift that
## cannot be seen working is a gift nobody picks twice on purpose.
func _perk_promise(perk: Dictionary) -> String:
	var p = player
	if perk.has("power"):
		return "Angriff %d → %d" % [p.power(), p.power() + int(perk["power"])]
	if perk.has("defense"):
		return "Verteidigung %d → %d" % [p.defense(), p.defense() + int(perk["defense"])]
	if perk.has("hp"):
		return "max. Leben %d → %d" % [p.max_hp, p.max_hp + int(perk["hp"])]
	if perk.has("crit"):
		return "Krit %.1f %% → %.1f %%" % [p.crit_chance() * 100.0,
			(p.crit_chance() + float(perk["crit"])) * 100.0]
	if perk.has("reduction"):
		return "Schaden -%d %% → -%d %%" % [roundi(p.damage_reduction * 100.0),
			roundi(minf(0.8, p.damage_reduction + float(perk["reduction"])) * 100.0)]
	if perk.has("gold"):
		return "Gold %d %% → %d %%" % [roundi(p.gold_mult * 100.0),
			roundi((p.gold_mult + float(perk["gold"])) * 100.0)]
	if perk.has("xp"):
		return "Erfahrung %d %% → %d %%" % [roundi(p.xp_mult * 100.0),
			roundi((p.xp_mult + float(perk["xp"])) * 100.0)]
	if perk.has("alchemy"):
		return "Tränke %d %% → %d %%" % [roundi(p.potion_mult * 100.0),
			roundi((p.potion_mult + float(perk["alchemy"])) * 100.0)]
	if perk.has("scholar"):
		return "Rolle bleibt %d %% → %d %%" % [roundi(p.scholar * 100.0),
			roundi(minf(0.8, p.scholar + float(perk["scholar"])) * 100.0)]
	if perk.has("regen"):
		if p.regen_interval <= 0:
			return "1 Leben alle %d Züge" % int(perk["regen"])
		if p.regen_interval > REGEN_FLOOR:
			return "%d Leben alle %d statt alle %d Züge" % [p.regen_power,
				p.regen_interval - 1, p.regen_interval]
		return "%d statt %d Leben alle %d Züge" % [p.regen_power + 1,
			p.regen_power, p.regen_interval]
	return str(perk.get("desc", ""))


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
	player.xp_mult += float(perk.get("xp", 0.0))
	player.potion_mult += float(perk.get("alchemy", 0.0))
	player.scholar = minf(0.8, player.scholar + float(perk.get("scholar", 0.0)))
	if perk.has("regen"):
		# First time it starts healing; after that the ticks come closer
		# together, down to three turns; after that each tick is worth
		# more. It used to go all the way to one turn, which is a hero
		# who cannot be worn down at all.
		if player.regen_interval <= 0:
			player.regen_interval = int(perk["regen"])
		elif player.regen_interval > REGEN_FLOOR:
			player.regen_interval -= 1
		else:
			player.regen_power += 1
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


## The minimap: the floor so far, four pixels to a cell, in the corner.
##
## Drawn into an Image and handed over as a texture rather than as a
## thousand little rectangles - on a phone a thousand draw calls a frame
## is the whole frame budget. It is rebuilt only when the explored set
## has actually changed size, which on most turns it has not.
func _build_minimap() -> void:
	_minimap = TextureRect.new()
	_minimap.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_minimap.position = Vector2(-14 - MAP_W * MINIMAP_SCALE, 110)
	_minimap.custom_minimum_size = Vector2(MAP_W, MAP_H) * MINIMAP_SCALE
	_minimap.size = _minimap.custom_minimum_size
	# The image is one pixel per cell; without these it would be drawn at
	# that size - forty pixels wide, in the corner of a box four times
	# as big.
	_minimap.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_minimap.stretch_mode = TextureRect.STRETCH_SCALE
	_minimap.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_minimap.modulate.a = 0.85
	_play_ui.add_child(_minimap)


func _update_minimap() -> void:
	if _minimap == null:
		return
	var here := Vector2i(player.x, player.y)
	if explored.size() == _minimap_drawn and here == _minimap_at:
		return
	_minimap_drawn = explored.size()
	_minimap_at = here

	var image := Image.create(MAP_W, MAP_H, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0.35))
	for cell in explored:
		var lit_here: bool = lit.has(cell)
		image.set_pixelv(cell, Color(0.55, 0.52, 0.60) if lit_here else Color(0.28, 0.26, 0.32))
	if explored.has(stairs):
		image.set_pixelv(stairs, Color(0.40, 0.85, 0.95))
	if depth > 1 and explored.has(up_stairs):
		image.set_pixelv(up_stairs, Color(0.55, 0.55, 0.65))
	if chest != null and not chest.get("gone", false) \
			and explored.has(chest["cell"]) and not chest["opened"]:
		image.set_pixelv(chest["cell"], Color(1.0, 0.84, 0.30))
	if shrine != null and explored.has(shrine):
		image.set_pixelv(shrine, Color(0.70, 0.60, 1.0))
	for shop in shops:
		if explored.has(shop["cell"]):
			image.set_pixelv(shop["cell"], Color(0.45, 0.90, 0.55))
	for monster in monsters:
		if monster.is_alive() and lit.has(monster.cell()):
			image.set_pixelv(monster.cell(),
				Color(1.0, 0.45, 0.20) if monster.is_boss else Color(0.90, 0.30, 0.30))
	image.set_pixelv(here, Color(1.0, 1.0, 1.0))
	_minimap.texture = ImageTexture.create_from_image(image)


## Moves everything that is mid-step a little closer to where it belongs.
## Eight tiles a second: a step lands in an eighth of a second, which is
## under the 0.16s the input allows between steps, so a held direction
## still looks continuous and never falls behind.
func _glide(delta: float) -> void:
	# A torch is not a lamp. Two slow waves of different length beat
	# against each other, which reads as flickering without ever
	# looking like a strobe - a random value per frame does.
	if _torch != null:
		_flicker += delta
		_torch.energy = 1.75 + sin(_flicker * 5.3) * 0.06 + sin(_flicker * 2.1) * 0.05
	if _camera != null and _camera.position != _camera_to:
		_camera.position = _camera.position.move_toward(_camera_to, TILE * 10.0 * delta)
	_follow_shadows()
	_mark_stairs(delta)
	if _gliding.is_empty():
		return
	var speed := (float(TILE) / STEP_TIME) * delta
	for sprite in _gliding.keys():
		if not is_instance_valid(sprite):
			_gliding.erase(sprite)
			continue
		var where: Vector2 = _gliding[sprite]
		sprite.position = sprite.position.move_toward(where, speed)
		if sprite.position.is_equal_approx(where):
			_gliding.erase(sprite)

## Draws a frame round the way down.
##
## The staircase is one tile of art in a floor made of tiles of art, and
## at arm's length on a phone it is genuinely hard to find - it is easy
## to cross the whole level twice looking for it. A pulsing outline is
## not subtle, which is the point: this is the tile everyone is looking
## for. Red while the boss still holds the key, so the reason the stairs
## will not open is visible at the stairs and not only in the log.
func _mark_stairs(_delta: float) -> void:
	if _stairs_mark == null:
		_stairs_mark = Line2D.new()
		_stairs_mark.width = 2.5
		_stairs_mark.z_index = 3
		var unlit := CanvasItemMaterial.new()
		unlit.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
		_stairs_mark.material = unlit
		add_child(_stairs_mark)
	if choosing or dead or not explored.has(stairs):
		_stairs_mark.visible = false
		return
	_stairs_mark.visible = true
	var corner := Vector2(stairs) * TILE
	var inset := 2.5
	var near := corner + Vector2(inset, inset)
	var far := corner + Vector2(TILE - inset, TILE - inset)
	# The first corner again at the end, rather than the closed flag: this
	# is one loop of four sides and it should stay drawable on any build.
	_stairs_mark.points = PackedVector2Array([near, Vector2(far.x, near.y),
		far, Vector2(near.x, far.y), near])
	_stairs_mark.default_color = (Color(0.95, 0.35, 0.30)
		if stairs_locked and boss_alive() else Color(0.55, 0.92, 1.0))
	_stairs_mark.modulate.a = 0.45 + 0.35 * sin(_flicker * 3.0)


## Keys, for playing on the machine this is built on. The phone has
## buttons for all of it; a keyboard should not need them.
##
## Escape closes whatever is open rather than quitting - on Android the
## same job is done by the back gesture, and a back gesture that ended
## the app while a shop was open would be a very rude shop.
func _unhandled_key_input(event: InputEvent) -> void:
	if not event.is_pressed() or event.is_echo():
		return
	var key := (event as InputEventKey).keycode
	match key:
		KEY_ESCAPE:
			if not close_topmost():
				open_pause()
		KEY_G:
			drink()
		KEY_T:
			if _bag_panel != null and _bag_panel.visible:
				close_bag()
			else:
				open_bag()
		KEY_Q:
			cycle_potion()
		KEY_C:
			if _stats_panel != null and _stats_panel.visible:
				close_stats()
			else:
				open_stats()
		KEY_SPACE, KEY_PERIOD:
			wait_a_turn()
		KEY_F:
			shoot()
		KEY_1, KEY_2, KEY_3:
			var at: int = key - KEY_1
			if at < Data.SCROLLS.size():
				read_scroll(Data.SCROLLS[at]["id"])


## Shuts the topmost thing that is open and says whether there was one.
## The order is the order they sit in front of each other.
func close_topmost() -> bool:
	if _party_panel != null and _party_panel.visible:
		close_party()
		return true
	if _level_panel != null and _level_panel.visible:
		close_levels()
		return true
	if _attack_panel != null and _attack_panel.visible:
		_attack_never_mind()
		return true
	if _options_panel != null and _options_panel.visible:
		close_options()
		return true
	if _info_panel != null and _info_panel.visible:
		close_info()
		return true
	if _stats_panel != null and _stats_panel.visible:
		close_stats()
		return true
	if _pause_panel != null and _pause_panel.visible:
		close_pause()
		return true
	if _kin_panel != null and _kin_panel.visible:
		close_kin()
		return true
	if _awards_panel != null and _awards_panel.visible:
		close_awards()
		return true
	if _bag_panel != null and _bag_panel.visible:
		close_bag()
		return true
	if shop_open != null:
		close_shop()
		return true
	if _perk_panel != null and _perk_panel.visible:
		# Not closable: the gift has to be taken. Reporting it as handled
		# keeps Escape from dropping the run instead.
		return true
	return false


## The pause menu.
##
## The switches already exist on the title screen, but getting there
## means leaving the run - and the two things anyone wants to change are
## exactly the ones you notice while playing: the music, and whether the
## stick or the pad is under your thumb. So they are here too, working on
## the same settings.
func _build_pause_panel() -> void:
	_pause_panel = PanelContainer.new()
	_pause_panel.custom_minimum_size = Vector2(560, 440)
	_pause_panel.visible = false
	_solid_panel(_pause_panel)
	_hud.add_child(_centred(_pause_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_pause_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Pause"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_pause_sound = _pause_button(column, toggle_sound)
	_pause_music = _pause_button(column, toggle_music)
	_pause_flash = _pause_button(column, toggle_flash)
	_pause_pad = _pause_button(column, toggle_pad)
	_pause_stats = _pause_button(column, open_stats)
	_pause_auto = _pause_button(column, toggle_auto_shoot)

	var back := Button.new()
	back.text = "WEITER"
	back.custom_minimum_size = Vector2(0, 70)
	back.add_theme_font_size_override("font_size", 28)
	back.pressed.connect(close_pause)
	column.add_child(back)

	var leave := Button.new()
	leave.text = "ZUM TITELBILDSCHIRM"
	leave.custom_minimum_size = Vector2(0, 62)
	leave.add_theme_font_size_override("font_size", 24)
	# The run is saved on every finished floor, so leaving here loses at
	# most the floor in progress - and the title screen offers it back.
	leave.pressed.connect(func() -> void:
		close_pause()
		show_title())
	column.add_child(leave)


func _pause_button(column: VBoxContainer, action: Callable) -> Button:
	var button := Button.new()
	button.custom_minimum_size = Vector2(0, 56)
	button.add_theme_font_size_override("font_size", 24)
	button.pressed.connect(action)
	column.add_child(button)
	return button


func open_pause() -> void:
	if dead or choosing or _pause_panel == null:
		return
	_refresh_settings()
	var holder := _pause_panel.get_parent()
	if holder != null:
		holder.move_to_front()
	_pause_panel.visible = true


func close_pause() -> void:
	if _pause_panel != null:
		_pause_panel.visible = false


## The bag: everything carried, on one screen, each line a button.
##
## Cycling through thirty kinds of flask with one arrow works when you
## carry two. It does not when you carry eight and the one you want is
## sixth. This is also the only place the full set of numbers is written
## out - the top line has room for the ones that change every turn, not
## for all of them.
func _build_bag_panel() -> void:
	_bag_panel = PanelContainer.new()
	_bag_panel.custom_minimum_size = Vector2(760, 520)
	_bag_panel.visible = false
	_solid_panel(_bag_panel)
	_hud.add_child(_centred(_bag_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	_bag_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Tasche"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_bag_stats = Label.new()
	_bag_stats.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bag_stats.add_theme_font_size_override("font_size", 22)
	_bag_stats.add_theme_color_override("font_color", Color(0.80, 0.80, 0.86))
	column.add_child(_bag_stats)

	var scroller := ScrollContainer.new()
	scroller.custom_minimum_size = Vector2(0, 300)
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroller)

	_bag_list = VBoxContainer.new()
	_bag_list.custom_minimum_size = Vector2(700, 0)
	_bag_list.add_theme_constant_override("separation", 6)
	scroller.add_child(_bag_list)

	var close := Button.new()
	close.text = "ZURÜCK"
	close.custom_minimum_size = Vector2(0, 64)
	close.add_theme_font_size_override("font_size", 26)
	close.pressed.connect(close_bag)
	column.add_child(close)


func open_bag() -> void:
	if dead or choosing or _bag_panel == null:
		return
	_refresh_bag()
	_bag_panel.visible = true


func close_bag() -> void:
	if _bag_panel != null:
		_bag_panel.visible = false


## Rebuilt each time it opens: what is carried changes constantly, and a
## handful of buttons is cheap to make.
func _refresh_bag() -> void:
	if _bag_list == null:
		return
	_bag_stats.text = "%s +%d     %s +%d     Angriff %d     Verteidigung %d     Krit %d%%" % [
		player.weapon_name(), player.weapon_bonus(),
		player.armour_name(), player.armour_bonus(),
		player.power(), player.defense(), int(round(player.crit_chance() * 100.0))]

	for old in _bag_list.get_children():
		old.queue_free()

	var ids: Array = player.potion_counts.keys()
	ids.sort()
	for id in ids:
		var potion := Data.potion_by_id(id)
		var button := Button.new()
		button.custom_minimum_size = Vector2(0, 54)
		button.add_theme_font_size_override("font_size", 22)
		button.text = "%s  x%d - %s" % [potion["name"], int(player.potion_counts[id]),
			_describe(potion["effect"])]
		button.pressed.connect(_drink_from_bag.bind(id))
		_bag_list.add_child(button)

	var scroll_ids: Array = player.scrolls.keys()
	scroll_ids.sort()
	for id in scroll_ids:
		var scroll := Data.scroll_by_id(id)
		var button := Button.new()
		button.custom_minimum_size = Vector2(0, 54)
		button.add_theme_font_size_override("font_size", 22)
		button.text = "%s  x%d - %s" % [scroll["name"], int(player.scrolls[id]), scroll["desc"]]
		button.pressed.connect(_read_from_bag.bind(id))
		_bag_list.add_child(button)

	if _bag_list.get_child_count() == 0:
		var empty := Label.new()
		empty.text = "Nichts dabei."
		empty.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		empty.add_theme_font_size_override("font_size", 22)
		_bag_list.add_child(empty)


func _drink_from_bag(id: String) -> void:
	player.selected_potion = id
	close_bag()
	drink()


func _read_from_bag(id: String) -> void:
	close_bag()
	read_scroll(id)


## A potion effect in words. Built from the table, so a new potion
## describes itself instead of needing a second list nobody remembers to
## keep in step.
func _describe(effect: Dictionary) -> String:
	var parts: Array[String] = []
	if effect.has("heal"):
		parts.append("heilt %d" % int(effect["heal"]))
	if effect.has("heal_pct"):
		parts.append("heilt vollständig")
	if effect.has("max_hp"):
		parts.append("+%d maximales Leben" % int(effect["max_hp"]))
	if effect.has("base_power"):
		parts.append("+%d Angriff" % int(effect["base_power"]))
	if effect.has("base_defense"):
		parts.append("+%d Verteidigung" % int(effect["base_defense"]))
	if effect.has("xp_levels"):
		parts.append("Erfahrung")
	if effect.has("buff"):
		parts.append("%s für %d Züge" % [
			Data.BUFFS[effect["buff"]]["name"], int(effect.get("turns", 10))])
	if effect.has("shield"):
		parts.append("Schild %d" % int(effect["shield"]))
	if effect.has("reveal"):
		parts.append("zeigt die Ebene")
	if effect.has("blink"):
		parts.append("versetzt dich")
	if effect.has("gold"):
		parts.append("Gold")
	if effect.has("cure"):
		parts.append("heilt Leiden")
	if effect.has("self_poison"):
		parts.append("vergiftet dich")
	if effect.has("burst_damage"):
		parts.append("zerplatzt: %d Schaden im Umkreis" % int(effect["burst_damage"]))
	return ", ".join(parts)


## Writes one fact about a kind into the bestiary.
##
## Saved on the spot rather than at the end of a run: what you learned
## about a monster should survive the death it taught you, and a death
## is exactly when nothing else gets saved.
func _note_kind(kind: String, what: String) -> void:
	if not Data.MONSTERS.has(kind):
		return
	var entry := Bestiary.row(known, kind)
	entry[what] = int(entry.get(what, 0)) + 1
	Bestiary.write(known)


## Awards an achievement once, with a banner, and remembers it.
##
## Called from wherever the thing actually happens rather than from one
## place that inspects everything each turn: the condition is then
## written next to the event it belongs to, and cannot drift away from
## it.
func _award(id: String) -> void:
	if earned.has(id):
		return
	earned[id] = true
	Achievements.write(earned)
	var entry := Achievements.by_id(id)
	audio.play("levelup")
	banner("Erfolg: %s" % entry["name"], Color(0.55, 0.85, 0.98))
	say("Erfolg freigeschaltet: %s - %s" % [entry["name"], entry["how"]])


## The conditions that are about a running total rather than a moment.
## Cheap enough to ask every turn, and asking every turn is what keeps
## them from being missed.
func _check_awards() -> void:
	var record := Stats.read()
	if player.kills >= 1:
		_award("first_blood")
	if player.level >= 5:
		_award("survivor")
	if player.level >= 10:
		_award("veteran")
	if depth >= 5:
		_award("deep_delver")
	if depth >= 10:
		_award("spelunker")
	if player.gold >= 100:
		_award("rich")
	if int(record["gold"]) + player.gold >= 500:
		_award("hoarder")
	if scrolls_read >= 10:
		_award("well_read")
	if int(record["deaths"]) >= 5:
		_award("persistent")
	if int(record["kills"]) + player.kills >= 100:
		_award("centurion")
	if depth >= 3 and potion_free:
		_award("untouchable")
	if depth >= Data.SUPERBOSS_LEVEL:
		_award("descent")
	if int(record["doors"]) >= 25:
		_award("doorman")
	if int(record["quests"]) >= 10:
		_award("contractor")
	if known.size() >= Data.MONSTERS.size():
		_award("naturalist")


## The update button and the line under it.
##
## There is no store behind this game: the APK is installed by hand once
## and would otherwise stay at that version for ever. The button asks
## GitHub what the newest build is; if there is one, it turns into a
## download link and Android takes it from there.
func _build_update(column: VBoxContainer) -> void:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	column.add_child(row)

	_update_button = Button.new()
	_update_button.text = "NACH UPDATE SUCHEN"
	_update_button.custom_minimum_size = Vector2(380, 54)
	_update_button.add_theme_font_size_override("font_size", 24)
	_update_button.pressed.connect(_update_pressed)
	row.add_child(_update_button)

	_update_label = Label.new()
	_update_label.text = "Version %s" % Updater.running_version()
	_update_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_update_label.add_theme_font_size_override("font_size", 22)
	_update_label.add_theme_color_override("font_color", Color(0.72, 0.72, 0.80))
	row.add_child(_update_label)


## The button walks through three states: look, fetch, install. Each
## press does the next one, so there is only ever one thing to press and
## the label says what it will do.
func _update_pressed() -> void:
	if _update_busy:
		return
	if _update_file != "":
		_install_update()
		return
	if _update_url != "":
		_update_busy = true
		_update_button.disabled = true
		updater.download(_update_url)
		return
	_update_button.disabled = true
	_update_label.text = "Suche ..."
	updater.check()


## Hands the file to Android, and keeps the browser in reserve.
##
## Whether the installer actually appears depends on a permission the
## player may not have given yet and on the device's own opinion of
## intents. If it does not, the same button becomes the browser link -
## a dead end with no way forward would be worse than one extra tap.
func _install_update() -> void:
	if updater.install(_update_file):
		if OS.get_name() == "Windows":
			# The file that has to be replaced is the one running this line,
			# so the swap waits for this process to end. Ending it is the
			# last thing left to do.
			_update_label.text = "Wird ersetzt - das Spiel startet gleich neu."
			save_run()
			await get_tree().create_timer(1.0).timeout
			get_tree().quit()
			return
		_update_label.text = "Android fragt jetzt nach der Installation."
		return
	_update_label.text = "Installer ließ sich nicht öffnen - im Browser laden."
	_update_button.text = "IM BROWSER LADEN"
	_update_file = ""
	_update_button.pressed.disconnect(_update_pressed)
	_update_button.pressed.connect(_open_update_in_browser)


func _open_update_in_browser() -> void:
	OS.shell_open(_update_url)
	_update_label.text = "Download läuft im Browser - danach antippen und installieren."


func _update_fetched(done: bool, path: String, note: String) -> void:
	_update_label.text = note
	if not done:
		return
	_update_busy = false
	_update_button.disabled = false
	if path == "":
		# Failed: back to offering the download again, and the browser is
		# one press further on.
		_update_button.text = "NOCHMAL VERSUCHEN"
		return
	_update_file = path
	_update_button.text = "JETZT INSTALLIEREN"
	_update_label.add_theme_color_override("font_color", Color(0.55, 0.85, 0.98))


func _update_answer(available: bool, version: String, url: String, note: String) -> void:
	_update_button.disabled = false
	_update_label.text = note
	if available:
		_update_url = url
		_update_button.text = "VERSION %s HERUNTERLADEN" % version
		_update_label.add_theme_color_override("font_color", Color(0.55, 0.85, 0.98))
	else:
		_update_url = ""
		_update_button.text = "NACH UPDATE SUCHEN"
		_update_label.add_theme_color_override("font_color", Color(0.72, 0.72, 0.80))


## The bestiary, on the title screen next to the achievements.
##
## Kinds that have never been met are listed as unknown rather than
## hidden: knowing there are three things down there you have not seen
## is itself a reason to go back down.
func _build_kin_panel() -> void:
	_kin_panel = PanelContainer.new()
	_kin_panel.custom_minimum_size = Vector2(900, 560)
	_kin_panel.visible = false
	_solid_panel(_kin_panel)
	_hud.add_child(_centred(_kin_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	_kin_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Bestiarium"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var scroller := ScrollContainer.new()
	scroller.custom_minimum_size = Vector2(0, 400)
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroller)

	_kin_list = VBoxContainer.new()
	_kin_list.custom_minimum_size = Vector2(840, 0)
	_kin_list.add_theme_constant_override("separation", 4)
	scroller.add_child(_kin_list)

	var close := Button.new()
	close.text = "ZURÜCK"
	close.custom_minimum_size = Vector2(0, 64)
	close.add_theme_font_size_override("font_size", 26)
	close.pressed.connect(close_kin)
	column.add_child(close)


func open_kin() -> void:
	if _kin_panel == null:
		return
	known = Bestiary.read()
	for old in _kin_list.get_children():
		old.queue_free()
	for kind in Data.MONSTERS:
		var line := Label.new()
		line.add_theme_font_size_override("font_size", 20)
		if known.has(kind):
			line.text = Bestiary.describe(kind, known[kind])
			line.add_theme_color_override("font_color", Color(0.86, 0.86, 0.92))
		else:
			line.text = "??? - noch nie begegnet."
			line.add_theme_color_override("font_color", Color(0.48, 0.48, 0.56))
		_kin_list.add_child(line)
	var holder := _kin_panel.get_parent()
	if holder != null:
		holder.move_to_front()
	# In front of whatever opened it: the info page was built after
	# this panel and would otherwise cover it.
	_kin_panel.get_parent().move_to_front()
	_kin_panel.visible = true


func close_kin() -> void:
	if _kin_panel != null:
		_kin_panel.visible = false


## The list of achievements, won and unwon, on the title screen.
##
## The unwon ones are shown too, with what they ask for: a list that
## only appears once something is on it tells a new player nothing about
## what there is to do.
func _build_awards_panel() -> void:
	_awards_panel = PanelContainer.new()
	_awards_panel.custom_minimum_size = Vector2(760, 560)
	_awards_panel.visible = false
	_solid_panel(_awards_panel)
	_hud.add_child(_centred(_awards_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	_awards_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Erfolge"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var scroller := ScrollContainer.new()
	scroller.custom_minimum_size = Vector2(0, 400)
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroller)

	_awards_list = VBoxContainer.new()
	_awards_list.custom_minimum_size = Vector2(700, 0)
	_awards_list.add_theme_constant_override("separation", 4)
	scroller.add_child(_awards_list)

	var close := Button.new()
	close.text = "ZURÜCK"
	close.custom_minimum_size = Vector2(0, 64)
	close.add_theme_font_size_override("font_size", 26)
	close.pressed.connect(close_awards)
	column.add_child(close)


func open_awards() -> void:
	if _awards_panel == null:
		return
	earned = Achievements.read()
	for old in _awards_list.get_children():
		old.queue_free()
	for entry in Achievements.ALL:
		var line := Label.new()
		var got: bool = earned.has(entry["id"])
		line.text = "%s  %s - %s" % ["✓" if got else "·", entry["name"], entry["how"]]
		line.add_theme_font_size_override("font_size", 22)
		line.add_theme_color_override("font_color",
			Color(0.55, 0.85, 0.98) if got else Color(0.55, 0.55, 0.62))
		_awards_list.add_child(line)
	# In front of the title screen, which was added later and therefore
	# draws over it: sibling order is draw order.
	var holder := _awards_panel.get_parent()
	if holder != null:
		holder.move_to_front()
	# In front of whatever opened it: the info page was built after
	# this panel and would otherwise cover it.
	_awards_panel.get_parent().move_to_front()
	_awards_panel.visible = true


func close_awards() -> void:
	if _awards_panel != null:
		_awards_panel.visible = false


## A line across the middle of the screen for the handful of moments that
## deserve one: a boss waking up, a vault found, a new stretch of the
## dungeon. The log at the bottom is for everything else - a banner for
## every hit would be a banner for nothing.
func banner(text: String, colour := Color(0.91, 0.71, 0.29)) -> void:
	if _banner == null:
		return
	_banner.text = text
	_banner.add_theme_color_override("font_color", colour)
	_banner.modulate.a = 1.0
	if _banner_fade != null and _banner_fade.is_valid():
		_banner_fade.kill()
	_banner_fade = create_tween()
	_banner_fade.tween_interval(1.6)
	_banner_fade.tween_property(_banner, "modulate:a", 0.0, 0.8)


## A shot you can see crossing the room.
##
## Without it a ranged attack is a number appearing on something far
## away, and it is never clear what hit it or from where. The bolt takes
## about an eighth of a second - long enough to read as a line, short
## enough that it never holds up the next turn.
func _bolt(from_cell: Vector2i, to_cell: Vector2i, colour: Color) -> void:
	var start := Vector2(from_cell) * TILE + Vector2(TILE, TILE) * 0.5
	var finish := Vector2(to_cell) * TILE + Vector2(TILE, TILE) * 0.5
	# Half a tile long and a fifth of one thick, in front of everything,
	# and it takes about a sixth of a second to cross the room.
	#
	# It was four pixels by two and gone in a tenth of a second, which on
	# a phone at arm's length is nothing at all - the shot happened, the
	# damage landed, and the player never saw a thing.
	var glow := ColorRect.new()
	glow.color = Color(colour.r, colour.g, colour.b, 0.45)
	glow.size = Vector2(TILE * 0.7, TILE * 0.34)
	glow.pivot_offset = glow.size * 0.5
	glow.rotation = (finish - start).angle()
	glow.z_index = 5
	glow.position = start - glow.size * 0.5
	var unlit := CanvasItemMaterial.new()
	unlit.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
	unlit.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	glow.material = unlit
	add_child(glow)

	# A hard bright core inside the glow: the glow says where, the core
	# says what.
	var core := ColorRect.new()
	core.color = Color(minf(1.0, colour.r + 0.35), minf(1.0, colour.g + 0.35),
		minf(1.0, colour.b + 0.35))
	core.size = Vector2(TILE * 0.5, TILE * 0.14)
	core.pivot_offset = core.size * 0.5
	core.rotation = glow.rotation
	core.z_index = 6
	core.position = start - core.size * 0.5
	core.material = unlit
	add_child(core)

	var flight := create_tween()
	flight.tween_property(glow, "position", finish - glow.size * 0.5, 0.16)
	flight.parallel().tween_property(core, "position", finish - core.size * 0.5, 0.16)
	flight.parallel().tween_property(glow, "modulate:a", 0.0, 0.16)
	flight.tween_callback(glow.queue_free)
	flight.tween_callback(core.queue_free)
	# Sparks at both ends: a puff where it was loosed, a burst where it
	# lands.
	_sparks(from_cell, colour, 4)


## A few specks thrown off a cell. Cheap on purpose: a handful of small
## rectangles, each tweened once and freed - no particle system, no
## per-frame work once they are on their way. The pygame build throws a
## dozen per crit and this matches that.
func _sparks(cell: Vector2i, colour: Color, count: int) -> void:
	for i in count:
		var speck := ColorRect.new()
		speck.color = colour
		speck.size = Vector2(1.5, 1.5)
		speck.z_index = 4
		speck.position = Vector2(cell) * TILE + Vector2(TILE, TILE) * 0.5
		add_child(speck)
		var away := Vector2(rng.randf_range(-1.0, 1.0), rng.randf_range(-1.0, 0.4))
		var flight := create_tween()
		flight.set_parallel(true)
		flight.tween_property(speck, "position",
			speck.position + away.normalized() * rng.randf_range(4.0, 11.0), 0.35)
		flight.tween_property(speck, "modulate:a", 0.0, 0.35)
		flight.chain().tween_callback(speck.queue_free)


## The light the hero carries, and the dark it pushes back.
##
## The field of view already decides what can be seen; this is only
## about how it looks. A flat wash of light over every visible tile reads
## as a diagram - a lamp with a falloff reads as a place. The two work
## together: the FOV says which tiles exist at all, the lamp says how
## brightly.
func _build_light() -> void:
	_gloom = CanvasModulate.new()
	# Dark enough that the lamp is doing visible work, not so dark that a
	# remembered corridor disappears - the map is also information.
	_gloom.color = Color(0.40, 0.40, 0.52)
	add_child(_gloom)

	# A radial gradient, built rather than shipped: it is four colours and
	# a curve, and a file for that is a file to keep in step.
	var fade := Gradient.new()
	fade.set_offset(0, 0.0)
	fade.set_color(0, Color(1.0, 0.94, 0.80, 1.0))
	fade.set_offset(1, 1.0)
	fade.set_color(1, Color(0.35, 0.30, 0.42, 0.0))
	# A small bright core and a long fade: a torch is not a floodlight.
	fade.add_point(0.22, Color(1.0, 0.90, 0.72, 0.92))
	fade.add_point(0.55, Color(0.85, 0.66, 0.52, 0.45))
	var glow := GradientTexture2D.new()
	glow.gradient = fade
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.5)
	glow.fill_to = Vector2(1.0, 0.5)
	glow.width = 256
	glow.height = 256

	_torch = PointLight2D.new()
	_torch.texture = glow
	_torch.energy = 1.75
	_torch.texture_scale = TILE * (sight_radius() + 3.0) * 2.0 / 256.0
	_torch.blend_mode = Light2D.BLEND_MODE_ADD
	_torch.z_index = 3
	add_child(_torch)

	# A cold glow on the way down, so the eye finds it across a dark
	# room without the map having to be read.
	_stairs_light = PointLight2D.new()
	_stairs_light.texture = glow
	_stairs_light.energy = 0.85
	_stairs_light.color = Color(0.55, 0.80, 1.0)
	_stairs_light.texture_scale = TILE * 5.0 / 256.0
	_stairs_light.blend_mode = Light2D.BLEND_MODE_ADD
	_stairs_light.z_index = 3
	add_child(_stairs_light)


## A darkening at the edges of the screen. Cheap, and it stops the map
## from looking like it is floating on a black desk.
func _build_vignette() -> void:
	_vignette = ColorRect.new()
	_vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	_vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var shade := ShaderMaterial.new()
	var code := Shader.new()
	code.code = """
shader_type canvas_item;
// Darkens towards the corners. UV is 0..1 across the rect, so the
// distance from the middle is all this needs.
uniform float strength : hint_range(0.0, 1.5) = 0.85;
void fragment() {
	float away = distance(UV, vec2(0.5)) * 1.42;
	float shade = smoothstep(0.45, 1.0, away) * strength;
	COLOR = vec4(0.02, 0.02, 0.05, shade);
}
"""
	shade.shader = code
	_vignette.material = shade
	_play_ui.add_child(_vignette)
	_play_ui.move_child(_vignette, 0)


## A soft smudge under whatever stands on a tile.
##
## Sprites drawn without one look pasted onto the floor rather than
## standing on it - the single cheapest thing that makes a flat tile map
## read as a room. Built once and shared: it is the same grey blob for
## everything.
func _shadow_for(sprite: Sprite2D, cell: Vector2i, width: float) -> void:
	if _shadow_art == null:
		var fade := Gradient.new()
		fade.set_offset(0, 0.0)
		fade.set_color(0, Color(0.0, 0.0, 0.0, 0.75))
		fade.set_offset(1, 1.0)
		fade.set_color(1, Color(0.0, 0.0, 0.0, 0.0))
		var blob := GradientTexture2D.new()
		blob.gradient = fade
		blob.fill = GradientTexture2D.FILL_RADIAL
		blob.fill_from = Vector2(0.5, 0.5)
		blob.fill_to = Vector2(1.0, 0.5)
		blob.width = 64
		blob.height = 64
		_shadow_art = blob

	var shadow: Sprite2D = _shadows.get(sprite)
	if shadow == null or not is_instance_valid(shadow):
		shadow = Sprite2D.new()
		shadow.texture = _shadow_art
		shadow.centered = true
		# Under the feet of everything, over the floor tiles.
		shadow.z_index = 1
		# Lights must not brighten a shadow.
		var dark := CanvasItemMaterial.new()
		dark.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
		shadow.material = dark
		add_child(shadow)
		_shadows[sprite] = shadow
	# Wider than the thing standing on it, or the sprite's own feet
	# cover the whole smudge and it may as well not be there - which
	# is exactly how the first attempt looked.
	shadow.scale = Vector2(width / 64.0, width * 0.34 / 64.0)
	shadow.visible = sprite.visible
	_follow_shadow(sprite, shadow)


## The part of a picture that has something in it.
##
## Every sprite in the set is a square tile with the figure drawn
## somewhere inside it and transparent space around it - so anything
## placed against the edge of the picture is placed against nothing. It
## showed on the health bars, which floated a hand's breadth over the
## head of whatever they belonged to, and under the shadows.
##
## Worked out once per picture and remembered: reading the pixels back
## is not something to do sixty times a second.
func _art_rect(texture: Texture2D) -> Rect2:
	if _art_rects.has(texture):
		return _art_rects[texture]
	var whole := Rect2(Vector2.ZERO, texture.get_size())
	var image: Image = texture.get_image()
	if image != null:
		var used := image.get_used_rect()
		if used.size.x > 0 and used.size.y > 0:
			whole = Rect2(used)
	_art_rects[texture] = whole
	return whole


## Puts one shadow under the feet of its sprite.
##
## Read off the sprite and not off the cell, because the sprite is
## still sliding: a shadow placed on the tile is already standing
## where the hero is going while the hero is still on the way, and it
## looked exactly like that - the shadow arriving first and the
## figure catching up.
func _follow_shadow(sprite: Sprite2D, shadow: Sprite2D) -> void:
	if sprite.texture == null:
		return
	var art: Rect2 = _art_rect(sprite.texture)
	shadow.position = Vector2(
		sprite.position.x + (art.position.x + art.size.x * 0.5) * sprite.scale.x,
		sprite.position.y + (art.position.y + art.size.y) * sprite.scale.y - 2.0)


## Every shadow, once a frame, for the same reason.
func _follow_shadows() -> void:
	for sprite in _shadows:
		var shadow: Sprite2D = _shadows[sprite]
		if not is_instance_valid(sprite) or not is_instance_valid(shadow):
			continue
		shadow.visible = sprite.visible
		_follow_shadow(sprite, shadow)


## A short white flare over something that has just been hit. The damage
## number says how much; this says *that*, at the moment it happens,
## which is what the eye actually follows in a fight.
func _flash_monster(monster) -> void:
	var sprite: Sprite2D = _actor_nodes.get(monster)
	if sprite == null or not is_instance_valid(sprite):
		return
	var was: Color = sprite.self_modulate
	sprite.self_modulate = Color(2.2, 2.2, 2.2)
	var back := create_tween()
	back.tween_property(sprite, "self_modulate", was, 0.16)


## A number that floats off a cell and fades. The cheapest way to make a
## hit legible: without it the only sign that anything happened is a
## line of text at the bottom of the screen, which nobody reads mid-fight.
func _damage_number(cell: Vector2i, text: String, colour: Color) -> void:
	var label := Label.new()
	label.text = text
	label.z_index = 5
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", colour)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	label.add_theme_constant_override("outline_size", 4)
	label.position = Vector2(cell) * TILE + Vector2(0, -4)
	add_child(label)
	var rise := create_tween()
	rise.set_parallel(true)
	rise.tween_property(label, "position:y", label.position.y - TILE, 0.5)
	rise.tween_property(label, "modulate:a", 0.0, 0.5).set_delay(0.15)
	rise.chain().tween_callback(label.queue_free)


## A short shove of the camera. Used on the blows that are meant to feel
## heavy - a critical hit, a trap, the moment the hero is hurt - and
## nowhere else, or it stops meaning anything.
func _shake(strength: float) -> void:
	if _camera == null:
		return
	var home: Vector2 = _camera.offset
	var shove := create_tween()
	for i in 4:
		var away := Vector2(
			rng.randf_range(-strength, strength), rng.randf_range(-strength, strength))
		shove.tween_property(_camera, "offset", home + away, 0.03)
	shove.tween_property(_camera, "offset", home, 0.05)


## A red wash over the screen when the hero is hit. Switchable, because
## it is the one effect people ask to turn off - the pygame build got
## exactly that request.
func _hurt_flash() -> void:
	if not settings.get("flash", true) or _flash == null:
		return
	_flash.color = Color(0.75, 0.10, 0.12, 0.35)
	var fade := create_tween()
	fade.tween_property(_flash, "color:a", 0.0, 0.35)


## What is left of a run when it ends. The pygame build shows the same
## four numbers; without them a death is just the word "gestorben" and
## the player has no idea whether it went well.
func _build_dead_panel() -> void:
	_dead_panel = PanelContainer.new()
	_dead_panel.custom_minimum_size = Vector2(640, 400)
	_dead_panel.visible = false
	_solid_panel(_dead_panel)
	_hud.add_child(_centred(_dead_panel))

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


## Every number the hero is made of, on one page.
##
## The bar at the top says how much health is left and the second line
## says what is in your hands, but the numbers those two are built from
## - what a critical hit actually multiplies, how often one lands, how
## much damage the armour eats, when the next point of health arrives -
## were nowhere. They decide every fight and were the one thing the game
## never showed.
func _build_stats_panel() -> void:
	_stats_panel = PanelContainer.new()
	_stats_panel.custom_minimum_size = Vector2(620, 480)
	_stats_panel.visible = false
	_solid_panel(_stats_panel)
	_hud.add_child(_centred(_stats_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_stats_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Werte"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 36)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_stats_text = Label.new()
	_stats_text.add_theme_font_size_override("font_size", 23)
	_stats_text.add_theme_color_override("font_color", Color(0.86, 0.86, 0.92))
	column.add_child(_stats_text)

	var back := Button.new()
	back.text = "ZURÜCK"
	back.custom_minimum_size = Vector2(0, 64)
	back.add_theme_font_size_override("font_size", 26)
	back.pressed.connect(close_stats)
	column.add_child(back)


## Reads the hero out loud. Written on opening rather than every frame:
## nothing on this page changes while it is being looked at, because
## looking at it costs no turn.
func open_stats() -> void:
	if dead or choosing or _stats_panel == null:
		return
	close_pause()
	var p = player
	var rows: Array[String] = []
	rows.append("Klasse:  %s          Stufe %d  (%d / %d XP)" % [
		Data.class_by_id(p.hero_class)["name"], p.level, p.xp, p.xp_to_next])
	rows.append("Schwierigkeit:  %s  (für diesen Lauf festgelegt)" % 
		Data.difficulty_by_id(difficulty)["name"])
	rows.append("")
	rows.append("Leben:  %d / %d%s" % [p.hp, p.max_hp,
		"    Schild %d" % p.shield if p.shield > 0 else ""])
	rows.append("Angriff:  %d      (Grundwert %d + Waffe %d)" % [
		p.power(), p.base_power, p.weapon_bonus()])
	rows.append("Verteidigung:  %d      (Grundwert %d + Rüstung %d)" % [
		p.defense(), p.base_defense, p.armour_bonus()])
	rows.append("Schadensminderung:  %d %%" % roundi(p.damage_reduction * 100.0))
	rows.append("")
	rows.append("Kritische Treffer:  %.1f %%      Schaden ×%.1f" % [
		p.crit_chance() * 100.0, float(Data.CRIT_MULT)])
	if p.regen_interval > 0:
		rows.append("Regeneration:  %d Leben alle %d Züge" % [p.regen_power,
			p.regen_interval])
	else:
		rows.append("Regeneration:  keine")
	if p.reach() > 0:
		rows.append("Reichweite:  %d Felder" % p.reach())
	rows.append("")
	rows.append("Waffe:  %s +%d%s" % [p.weapon_name(), p.weapon_bonus(),
		_rarity_note(p.weapon_rarity)])
	if p.weapon_element != "":
		rows.append("Element:  %s" % Data.ELEMENTS[p.weapon_element]["name"])
	rows.append("Rüstung:  %s +%d%s" % [p.armour_name(), p.armour_bonus(),
		_rarity_note(p.armour_rarity)])
	rows.append("")
	rows.append("Gold:  %d      Kills:  %d      Tiefe:  Ebene %d" % [
		p.gold, p.kills, depth])
	var bonus: Array[String] = []
	if p.gold_mult != 1.0:
		bonus.append("Gold ×%.2f" % p.gold_mult)
	if p.xp_mult != 1.0:
		bonus.append("Erfahrung ×%.2f" % p.xp_mult)
	if p.potion_mult != 1.0:
		bonus.append("Tränke ×%.2f" % p.potion_mult)
	if not bonus.is_empty():
		rows.append("Gaben:  %s" % "      ".join(bonus))
	_stats_text.text = nl_join(rows)
	_stats_panel.visible = true
	audio.play("equip")


## The rarity in brackets, or nothing at all.
##
## The common one has no name - "(  )" after every starting sword is
## worse than silence. And the rarity is an id like "rare", not a number:
## typing the parameter as an int made this function throw the moment the
## page was opened, which is why the page did nothing at all.
func _rarity_note(rarity: String) -> String:
	var name: String = str(Data.rarity_by_id(rarity).get("name", ""))
	return "" if name == "" else "      (%s)" % name


## String.join on an Array[String] with a newline, spelled out once so
## the line above stays readable.
func nl_join(rows: Array[String]) -> String:
	return "\n".join(rows)


func close_stats() -> void:
	if _stats_panel != null:
		_stats_panel.visible = false


## The offer to move into a proper folder, shown once on Windows.
##
## A single downloaded exe sitting in the Downloads folder is not an
## installed game: no shortcut, no name in the start menu, and the next
## version lands beside it as a second copy. This copies the executable
## into the user's own program folder, puts a shortcut on the desktop
## and in the start menu, and starts again from there.
##
## Asked, not done silently: a program that moves itself somewhere
## without saying so is a program nobody trusts. The answer is
## remembered either way, and the save file lives elsewhere entirely,
## so nothing is lost whichever button is pressed.
func _build_setup_panel() -> void:
	_setup_panel = PanelContainer.new()
	_setup_panel.custom_minimum_size = Vector2(760, 380)
	_setup_panel.visible = false
	_solid_panel(_setup_panel)
	_hud.add_child(_centred(_setup_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	_setup_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Spiel installieren?"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 38)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_setup_text = Label.new()
	_setup_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_setup_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_setup_text.custom_minimum_size = Vector2(700, 0)
	_setup_text.add_theme_font_size_override("font_size", 22)
	_setup_text.add_theme_color_override("font_color", Color(0.80, 0.80, 0.88))
	_setup_text.text = ("Das Spiel liegt gerade als einzelne Datei da, wo du sie"
		+ " heruntergeladen hast.\n\nIch kann es nach\n%s\nkopieren und dir eine"
		+ " Verknüpfung auf den Desktop und ins Startmenü legen. Keine"
		+ " Administratorrechte nötig, dein Spielstand bleibt.") % (
			Setup.install_dir().replace("/", "\\"))
	column.add_child(_setup_text)

	var yes := Button.new()
	yes.text = "INSTALLIEREN"
	yes.custom_minimum_size = Vector2(0, 72)
	yes.add_theme_font_size_override("font_size", 28)
	yes.pressed.connect(_do_install)
	column.add_child(yes)

	var no := Button.new()
	no.text = "NUR STARTEN"
	no.custom_minimum_size = Vector2(0, 62)
	no.add_theme_font_size_override("font_size", 24)
	no.pressed.connect(_skip_install)
	column.add_child(no)


## Copies the game into place and starts the copy that landed there.
func _do_install() -> void:
	_setup_text.text = "Kopiere ..."
	settings["install_asked"] = true
	Settings.write(settings)
	# Two frames, because copying a hundred and twenty megabytes blocks
	# everything: the line above has to be on the screen before the freeze,
	# not queued behind it.
	await get_tree().process_frame
	await get_tree().process_frame
	var done: Dictionary = Setup.install()
	_setup_text.text = done["note"]
	if not done["ok"]:
		return
	if Setup.launch(done["exe"]):
		await get_tree().create_timer(0.8).timeout
		get_tree().quit()
	else:
		_setup_text.text = done["note"] + "\nStarten hat nicht geklappt - bitte selbst öffnen."


func _skip_install() -> void:
	settings["install_asked"] = true
	Settings.write(settings)
	_setup_panel.visible = false


## Called the moment the hero dies, from wherever killed them.
func _show_death() -> void:
	if _dead_panel == null:
		return
	# The run goes into the record before it is shown, so the totals
	# under the summary already include the run being summarised.
	var score := Stats.score_of(depth, player.level, player.kills, player.gold)
	var stats := Stats.record_run(depth, player.level, player.kills, player.gold, true)
	var best: int = int(stats["best_score"])
	var lines: Array[String] = [
		"Ebene %d     Stufe %d     %d Kills     %d Gold" % [
			depth, player.level, player.kills, player.gold],
		"",
		"%d Punkte%s" % [score,
			"  (neuer Bestwert!)" if score >= best else "  (Bestwert: %d)" % best],
		"",
		"%d Läufe, %d Tode - am tiefsten: Ebene %d" % [
			stats["runs"], stats["deaths"], stats["deepest"]],
	]
	_dead_text.text = "
".join(lines)
	_dead_panel.visible = true


## Two switches, because those are the two things a player on a bus
## actually needs. They sit on the title screen rather than behind a
## pause button: that is where you already are before a run starts, and
## the sound is the first thing anyone turns off.
func _build_settings(column: VBoxContainer) -> void:
	# Two rows: six buttons in one line run off the edge of a phone.
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	column.add_child(row)
	var row_two := HBoxContainer.new()
	row_two.alignment = BoxContainer.ALIGNMENT_CENTER
	row_two.add_theme_constant_override("separation", 14)
	column.add_child(row_two)

	_sound_button = Button.new()
	_sound_button.custom_minimum_size = Vector2(210, 54)
	_sound_button.add_theme_font_size_override("font_size", 24)
	_sound_button.pressed.connect(toggle_sound)
	row.add_child(_sound_button)

	_music_button = Button.new()
	_music_button.custom_minimum_size = Vector2(210, 54)
	_music_button.add_theme_font_size_override("font_size", 24)
	_music_button.pressed.connect(toggle_music)
	row.add_child(_music_button)


	# The red wash is the one effect people ask to turn off.
	_flash_button = Button.new()
	_flash_button.custom_minimum_size = Vector2(240, 54)
	_flash_button.add_theme_font_size_override("font_size", 24)
	_flash_button.pressed.connect(toggle_flash)
	row.add_child(_flash_button)

	_pad_button = Button.new()
	_pad_button.custom_minimum_size = Vector2(250, 54)
	_pad_button.add_theme_font_size_override("font_size", 24)
	_pad_button.pressed.connect(toggle_pad)
	row_two.add_child(_pad_button)

	_diagonal_button = Button.new()
	_diagonal_button.custom_minimum_size = Vector2(260, 54)
	_diagonal_button.add_theme_font_size_override("font_size", 24)
	_diagonal_button.pressed.connect(toggle_diagonal)
	row_two.add_child(_diagonal_button)

	# Loudness in tenths rather than on and off.
	#
	# A switch has two settings and neither of them is "quiet enough to
	# play in the same room as somebody else". Minus and plus move by
	# ten per cent and the number is written out, so the setting can be
	# put back exactly where it was.
	var row_three := HBoxContainer.new()
	row_three.alignment = BoxContainer.ALIGNMENT_CENTER
	row_three.add_theme_constant_override("separation", 10)
	column.add_child(row_three)
	_volume_label = _volume_row(row_three, "Ton", nudge_sound)
	_music_label = _volume_row(row_three, "Musik", nudge_music)
	_refresh_settings()


## One minus, one number, one plus.
func _volume_row(row: HBoxContainer, name: String, nudge: Callable) -> Label:
	var less := Button.new()
	less.text = "−"
	less.custom_minimum_size = Vector2(64, 54)
	less.add_theme_font_size_override("font_size", 26)
	less.pressed.connect(nudge.bind(-0.1))
	row.add_child(less)

	var shown := Label.new()
	shown.custom_minimum_size = Vector2(190, 54)
	shown.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	shown.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	shown.add_theme_font_size_override("font_size", 24)
	shown.text = name
	row.add_child(shown)

	var more := Button.new()
	more.text = "+"
	more.custom_minimum_size = Vector2(64, 54)
	more.add_theme_font_size_override("font_size", 26)
	more.pressed.connect(nudge.bind(0.1))
	row.add_child(more)
	return shown


## Ten per cent at a time, and never past either end.
func nudge_sound(step: float) -> void:
	settings["volume"] = clampf(float(settings.get("volume", 0.75)) + step, 0.0, 1.0)
	audio.set_volume(settings["volume"])
	Settings.write(settings)
	_refresh_settings()
	audio.play("pickup")


func nudge_music(step: float) -> void:
	settings["music_volume"] = clampf(
		float(settings.get("music_volume", 0.55)) + step, 0.0, 1.0)
	audio.set_music_volume(settings["music_volume"])
	Settings.write(settings)
	_refresh_settings()


func _refresh_settings() -> void:
	if _sound_button == null:
		return
	_sound_button.text = "Ton: %s" % ("AN" if settings["sound"] else "AUS")
	if _flash_button != null:
		_flash_button.text = "Roter Blitz: %s" % ("AN" if settings.get("flash", true) else "AUS")
	if _pause_sound != null:
		_pause_sound.text = "Ton: %s" % ("AN" if settings["sound"] else "AUS")
		_pause_music.text = "Musik: %s" % ("AN" if settings["music"] else "AUS")
		_pause_flash.text = "Roter Blitz: %s" % ("AN" if settings.get("flash", true) else "AUS")
		_pause_pad.text = "Steuerung: %s" % ("Kreuz" if settings.get("pad", false) else "Stick")
		_pause_stats.text = "Werte ansehen"
		_pause_auto.visible = player != null and player.reach() > 0
		_pause_auto.text = "Automatisch schießen: %s" % (
			"AN" if settings.get("auto_shoot", true) else "AUS")
	if _pad_button != null:
		_pad_button.text = "Steuerung: %s" % ("Kreuz" if settings.get("pad", false) else "Stick")
	if _diagonal_button != null:
		_diagonal_button.text = "Richtungen: %s" % (
			"8 (diagonal)" if settings.get("diagonal", true) else "4 (gerade)")
	_music_button.text = "Musik: %s" % ("AN" if settings["music"] else "AUS")
	if _volume_label != null:
		_volume_label.text = "Ton %d %%" % roundi(float(settings.get("volume", 0.75)) * 100.0)
		_music_label.text = "Musik %d %%" % roundi(
			float(settings.get("music_volume", 0.55)) * 100.0)


## Shows whichever control the player asked for. They are deliberately
## one or the other: with both on, the pad sits in front of the stick and
## swallows every touch that lands on it.
func _apply_control_style() -> void:
	var use_pad: bool = settings.get("pad", false)
	if _stick != null:
		_stick.visible = not use_pad
		_stick.mouse_filter = (Control.MOUSE_FILTER_IGNORE if use_pad
			else Control.MOUSE_FILTER_STOP)
	var corners: bool = settings.get("diagonal", true)
	for button in _pad_buttons:
		button.visible = use_pad and (corners or not _corner_buttons.has(button))
		# Quieter than the rest: the pad is under a thumb for the whole
		# run, and eight brass-edged slabs in the corner of the screen
		# would be the loudest thing in the dungeon.
		button.modulate = Color(1, 1, 1, 0.62)


func toggle_auto_shoot() -> void:
	settings["auto_shoot"] = not settings.get("auto_shoot", true)
	if player != null:
		player.auto_shoot = settings["auto_shoot"]
	Settings.write(settings)
	_refresh_settings()
	audio.play("equip")


func toggle_diagonal() -> void:
	settings["diagonal"] = not settings.get("diagonal", true)
	Settings.write(settings)
	_apply_control_style()
	_refresh_settings()
	audio.play("equip")


func toggle_pad() -> void:
	settings["pad"] = not settings.get("pad", false)
	Settings.write(settings)
	_apply_control_style()
	_refresh_settings()
	audio.play("equip")


func toggle_flash() -> void:
	settings["flash"] = not settings.get("flash", true)
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
	# Everything on this screen has to fit into 720 logical pixels of
	# height, on a phone as much as in a window. It stopped fitting the
	# moment the update button arrived, and what falls off the bottom is
	# invisible rather than scrollable.
	column.add_theme_constant_override("separation", 8)
	_title_panel.add_child(column)

	var heading := Label.new()
	heading.text = "DUNGEON CRAWLER"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 44)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var subtitle := Label.new()
	subtitle.text = "Wähle deinen Helden"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_font_size_override("font_size", 22)
	column.add_child(subtitle)

	# Only shown when there is something to continue. A dead run wipes
	# its own save, so this never offers to resume a finished one.
	_continue_button = Button.new()
	_continue_button.text = "LAUF FORTSETZEN"
	_continue_button.custom_minimum_size = Vector2(0, 78)
	_continue_button.add_theme_font_size_override("font_size", 30)
	_continue_button.pressed.connect(continue_run)
	_continue_button.custom_minimum_size = Vector2(440, 66)
	var centred := CenterContainer.new()
	centred.add_child(_continue_button)
	column.add_child(centred)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	column.add_child(row)

	for info in Data.CLASSES:
		var card := VBoxContainer.new()
		# Four heroes have to fit across 1280 logical pixels, so the cards
		# are narrower than they were with three.
		card.custom_minimum_size = Vector2(224, 0)
		card.add_theme_constant_override("separation", 8)
		row.add_child(card)

		var portrait := TextureRect.new()
		portrait.texture = load(CLASS_DIR + info["sprite"] + ".png")
		portrait.custom_minimum_size = Vector2(0, 96)
		portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		portrait.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		card.add_child(portrait)

		var blurb := Label.new()
		blurb.text = info["blurb"]
		blurb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		# Tall enough for three lines: the longest blurb wraps to three,
		# and a card that grows pushes its own button out of line with
		# the others.
		blurb.custom_minimum_size = Vector2(224, 96)
		blurb.add_theme_font_size_override("font_size", 17)
		blurb.add_theme_color_override("font_color", Color(0.80, 0.80, 0.86))
		card.add_child(blurb)

		var pick := Button.new()
		pick.text = info["name"]
		pick.custom_minimum_size = Vector2(0, 62)
		pick.add_theme_font_size_override("font_size", 26)
		pick.add_theme_color_override("font_color", info["color"])
		pick.pressed.connect(offer_levels.bind(info["id"]))
		card.add_child(pick)

	# Two doors instead of a wall of switches.
	#
	# Everything used to be on this one screen: four heroes, seven
	# switches, two volume rows, the update button, the record. On a
	# phone the bottom of it fell off the screen, and what falls off is
	# invisible rather than scrollable. The choice of hero stays here,
	# because that is what this screen is for; the rest is one press
	# away.
	var doors := HBoxContainer.new()
	doors.alignment = BoxContainer.ALIGNMENT_CENTER
	doors.add_theme_constant_override("separation", 16)
	column.add_child(doors)

	var to_options := Button.new()
	to_options.text = "EINSTELLUNGEN"
	to_options.custom_minimum_size = Vector2(300, 62)
	to_options.add_theme_font_size_override("font_size", 24)
	to_options.pressed.connect(open_options)
	doors.add_child(to_options)

	var to_info := Button.new()
	to_info.text = "INFO & UPDATE"
	to_info.custom_minimum_size = Vector2(300, 62)
	to_info.add_theme_font_size_override("font_size", 24)
	to_info.pressed.connect(open_info)
	doors.add_child(to_info)

	var to_party := Button.new()
	to_party.text = "ZUSAMMEN SPIELEN"
	to_party.custom_minimum_size = Vector2(340, 62)
	to_party.add_theme_font_size_override("font_size", 24)
	to_party.pressed.connect(open_party)
	doors.add_child(to_party)

	# The record so far, under the choice. A dead run leaves nothing
	# else behind, and this is the line that makes the next one worth
	# starting.
	_hint_label = Label.new()
	_hint_label.text = "Laufen: Pfeiltasten oder das Steuerkreuz. In einen Gegner laufen greift an.
Treppe hinab = tiefer. Tasche zeigt Tränke und Rollen."
	_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_label.add_theme_font_size_override("font_size", 20)
	_hint_label.add_theme_color_override("font_color", Color(0.72, 0.72, 0.80))
	column.add_child(_hint_label)

	_record_label = Label.new()
	_record_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_record_label.add_theme_font_size_override("font_size", 22)
	_record_label.add_theme_color_override("font_color", Color(0.66, 0.66, 0.74))
	column.add_child(_record_label)


## What the button does, said once, before it does it.
##
## A button that changes what it does behind your back is a button that
## gets pressed by mistake, and the mistake here costs a turn and a hit
## in the face. So the first time it would swing, it explains itself and
## waits to be told to go ahead. Once.
func _build_attack_hint() -> void:
	_attack_panel = PanelContainer.new()
	_attack_panel.custom_minimum_size = Vector2(760, 400)
	_attack_panel.visible = false
	_solid_panel(_attack_panel)
	_hud.add_child(_centred(_attack_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	_attack_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Achtung: dieser Knopf greift an"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.custom_minimum_size = Vector2(700, 0)
	heading.add_theme_font_size_override("font_size", 32)
	heading.add_theme_color_override("font_color", Color(1.0, 0.66, 0.40))
	column.add_child(heading)

	var body := Label.new()
	body.name = "body"
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.custom_minimum_size = Vector2(700, 0)
	body.add_theme_font_size_override("font_size", 21)
	body.add_theme_color_override("font_color", Color(0.84, 0.84, 0.90))
	column.add_child(body)

	var yes := Button.new()
	yes.text = "ANGREIFEN"
	yes.custom_minimum_size = Vector2(0, 70)
	yes.add_theme_font_size_override("font_size", 28)
	yes.pressed.connect(_attack_anyway)
	column.add_child(yes)

	var no := Button.new()
	no.text = "DOCH NICHT"
	no.custom_minimum_size = Vector2(0, 60)
	no.add_theme_font_size_override("font_size", 24)
	no.pressed.connect(_attack_never_mind)
	column.add_child(no)


func _show_attack_hint(mark) -> void:
	if _attack_panel == null:
		return
	var body: Label = _attack_panel.find_child("body", true, false)
	if body != null:
		body.text = ("Solange etwas Waches direkt neben dir steht, heißt dieser"
			+ " Knopf ANGREIFEN und schlägt zu - hier auf %s.\n\n"
			+ "Das kostet einen Zug wie jede andere Handlung, und danach sind"
			+ " die Gegner dran: der Getroffene schlägt zurück, wenn er noch"
			+ " steht.\n\n"
			+ "Stehen mehrere neben dir, trifft er den mit den wenigsten"
			+ " Lebenspunkten. Schlafende lässt er in Ruhe - an denen kommst"
			+ " du vorbei, wenn du willst.\n\n"
			+ "Du kannst wie bisher auch einfach in einen Gegner hineinlaufen."
			+ " Diese Erklärung kommt nur dieses eine Mal.") % mark.display_name
	_attack_panel.get_parent().move_to_front()
	_attack_panel.visible = true


func _attack_anyway() -> void:
	settings["attack_hint_seen"] = true
	Settings.write(settings)
	_attack_panel.visible = false
	if _attack_step != Vector2i.ZERO:
		try_move(_attack_step)
	_attack_step = Vector2i.ZERO


## Backing out still counts as having read it: the point was to be told
## once, not to be asked every time until the answer is yes.
func _attack_never_mind() -> void:
	settings["attack_hint_seen"] = true
	Settings.write(settings)
	_attack_panel.visible = false
	_attack_step = Vector2i.ZERO


## How hard it should be, asked once, after the hero is picked.
##
## It used to sit in the settings between the sound and the red flash,
## where it could be changed in the middle of a run - and changing it
## mid-run changes nothing that is already standing on the floor, so a
## hardcore run could be finished on easy. It belongs to the run, so it
## is asked at the start of one and then held for its whole length.
func _build_level_panel() -> void:
	_level_panel = PanelContainer.new()
	_level_panel.custom_minimum_size = Vector2(820, 560)
	_level_panel.visible = false
	_solid_panel(_level_panel)
	_hud.add_child(_centred(_level_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_level_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Wie schwer?"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 36)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var note := Label.new()
	note.text = "Gilt für den ganzen Lauf und lässt sich danach nicht mehr ändern."
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.custom_minimum_size = Vector2(760, 0)
	note.add_theme_font_size_override("font_size", 20)
	note.add_theme_color_override("font_color", Color(0.78, 0.78, 0.86))
	column.add_child(note)

	for entry in Data.DIFFICULTIES:
		var pick := Button.new()
		pick.text = "%s - %s" % [entry["name"], entry["desc"]]
		pick.custom_minimum_size = Vector2(0, 74)
		pick.add_theme_font_size_override("font_size", 22)
		pick.pressed.connect(start_at_level.bind(str(entry["id"])))
		column.add_child(pick)

	var back := Button.new()
	back.text = "ZURÜCK"
	back.custom_minimum_size = Vector2(0, 58)
	back.add_theme_font_size_override("font_size", 24)
	back.pressed.connect(close_levels)
	column.add_child(back)


## The hero is chosen; now the level of play.
func offer_levels(id: String) -> void:
	_picked_class = id
	if _level_panel == null:
		choose_class(id)
		return
	_level_panel.get_parent().move_to_front()
	_level_panel.visible = true
	audio.play("equip")


## Locks it in and starts the run. The choice is remembered as next
## time's suggestion, but never applied behind anyone's back: the panel
## always asks.
func start_at_level(id: String) -> void:
	difficulty = id
	settings["difficulty"] = id
	Settings.write(settings)
	_level_panel.visible = false
	_refresh_settings()
	choose_class(_picked_class)


func close_levels() -> void:
	if _level_panel != null:
		_level_panel.visible = false


## Hosting, joining, and the address to read out.
##
## Self-hosted means somebody has to know where "here" is, so the address
## is the loudest thing on this screen: large, selectable, and with the
## port already written into it, because a number typed into the wrong box
## is the most common way this fails.
##
## No lobby, no account, no server of mine in the middle. The host opens a
## port on their own machine and reads out four numbers.
func _build_party_panel() -> void:
	_party_panel = PanelContainer.new()
	_party_panel.custom_minimum_size = Vector2(880, 620)
	_party_panel.visible = false
	_solid_panel(_party_panel)
	_hud.add_child(_centred(_party_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_party_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Zusammen spielen"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 34)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var blurb := Label.new()
	blurb.text = ("Ein Gerät hostet und spielt mit, die anderen treten bei."
		+ " Handy und PC gemischt ist ausdrücklich vorgesehen.")
	blurb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	blurb.custom_minimum_size = Vector2(820, 0)
	blurb.add_theme_font_size_override("font_size", 20)
	blurb.add_theme_color_override("font_color", Color(0.78, 0.78, 0.86))
	column.add_child(blurb)

	_party_host = Button.new()
	_party_host.text = "SPIEL HOSTEN"
	_party_host.custom_minimum_size = Vector2(0, 66)
	_party_host.add_theme_font_size_override("font_size", 26)
	_party_host.pressed.connect(start_hosting)
	column.add_child(_party_host)

	# The address. Big enough to read from across a room and out of a
	# phone held at arm's length, because that is exactly what happens.
	_party_where = Label.new()
	_party_where.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_party_where.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_party_where.custom_minimum_size = Vector2(820, 0)
	_party_where.add_theme_font_size_override("font_size", 30)
	_party_where.add_theme_color_override("font_color", Color(0.55, 0.92, 1.0))
	column.add_child(_party_where)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 12)
	column.add_child(row)

	_party_field = LineEdit.new()
	_party_field.placeholder_text = "192.168.0.12"
	_party_field.custom_minimum_size = Vector2(420, 60)
	_party_field.add_theme_font_size_override("font_size", 26)
	_party_field.alignment = HORIZONTAL_ALIGNMENT_CENTER
	row.add_child(_party_field)

	_party_join = Button.new()
	_party_join.text = "BEITRETEN"
	_party_join.custom_minimum_size = Vector2(240, 60)
	_party_join.add_theme_font_size_override("font_size", 24)
	_party_join.pressed.connect(start_joining)
	row.add_child(_party_join)

	# The addresses joined before, one press each.
	#
	# Typing an address once is fair. Typing it again every evening, on a
	# phone, with a keyboard covering half the screen, is not.
	_party_again = HBoxContainer.new()
	_party_again.alignment = BoxContainer.ALIGNMENT_CENTER
	_party_again.add_theme_constant_override("separation", 10)
	column.add_child(_party_again)

	# And the hero, for a guest. The host picks one the usual way, before
	# the run; a guest joins a run that already exists, so the choice
	# belongs here - and it is a request like every other, because the
	# host is the one who builds the hero.
	_party_heroes = HBoxContainer.new()
	_party_heroes.alignment = BoxContainer.ALIGNMENT_CENTER
	_party_heroes.add_theme_constant_override("separation", 10)
	column.add_child(_party_heroes)
	for info in Data.CLASSES:
		var pick := Button.new()
		pick.text = info["name"]
		pick.custom_minimum_size = Vector2(190, 56)
		pick.add_theme_font_size_override("font_size", 22)
		pick.add_theme_color_override("font_color", info["color"])
		pick.pressed.connect(become.bind(str(info["id"])))
		_party_heroes.add_child(pick)

	_party_note = Label.new()
	_party_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_party_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_party_note.custom_minimum_size = Vector2(820, 0)
	_party_note.add_theme_font_size_override("font_size", 21)
	_party_note.add_theme_color_override("font_color", Color(0.86, 0.86, 0.92))
	column.add_child(_party_note)

	_party_list = Label.new()
	_party_list.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_party_list.add_theme_font_size_override("font_size", 21)
	_party_list.add_theme_color_override("font_color", Color(0.80, 0.86, 0.78))
	column.add_child(_party_list)

	# What the connection is actually doing, line by line.
	#
	# "It does not work" is the least useful sentence in software, and it
	# is the only one anyone can say when the screen shows nothing. Every
	# step is written down here and into the log file, so a run that fails
	# can be read afterwards instead of guessed at.
	_party_trail = Label.new()
	_party_trail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_party_trail.add_theme_font_size_override("font_size", 16)
	_party_trail.add_theme_color_override("font_color", Color(0.62, 0.62, 0.70))
	column.add_child(_party_trail)

	_party_leave = Button.new()
	_party_leave.text = "VERBINDUNG TRENNEN"
	_party_leave.custom_minimum_size = Vector2(0, 58)
	_party_leave.add_theme_font_size_override("font_size", 22)
	_party_leave.pressed.connect(stop_playing_together)
	column.add_child(_party_leave)

	var back := Button.new()
	back.text = "ZURÜCK"
	back.custom_minimum_size = Vector2(0, 58)
	back.add_theme_font_size_override("font_size", 24)
	back.pressed.connect(close_party)
	column.add_child(back)

	net.note.connect(_party_says)
	net.party_changed.connect(_refresh_party)
	net.traced.connect(_refresh_trail)


func _refresh_trail() -> void:
	if _party_trail != null:
		_party_trail.text = "\n".join(net.trail)


## A guest swapping hero mid-session. The host rebuilds it and sends the
## floor back, so the change is real everywhere at once.
func become(id: String) -> void:
	hero_class = id
	if net.guest:
		net.ask("class:" + id)
		_party_says("%s angefragt." % Data.class_by_id(id)["name"])
	audio.play("equip")


## Remembers a host that answered, newest first.
func remember_host(address: String) -> void:
	if address == "":
		return
	var seen: Array = settings.get("seen_hosts", [])
	seen.erase(address)
	seen.insert(0, address)
	while seen.size() > 3:
		seen.remove_at(seen.size() - 1)
	settings["seen_hosts"] = seen
	Settings.write(settings)
	_refresh_party()


func open_party() -> void:
	if _party_panel == null:
		return
	_party_panel.get_parent().move_to_front()
	_party_panel.visible = true
	_refresh_party()
	_refresh_trail()
	audio.play("equip")


func close_party() -> void:
	if _party_panel != null:
		_party_panel.visible = false


func start_hosting() -> void:
	if not net.host():
		return
	# Hosting is playing: the host drops straight into its own run, and the
	# panel stays open behind it so the address can still be read out.
	if choosing:
		choose_class(hero_class)
	# The hero the host is actually playing, in the party list: choose_class
	# builds a fresh one, so the entry made a moment ago points at the hero
	# from before.
	party[1] = player
	_refresh_party()


## One press instead of twelve keystrokes.
func _join_again(address: String) -> void:
	_party_field.text = address
	start_joining()


func start_joining() -> void:
	var address: String = _party_field.text.strip_edges()
	if address == "":
		_party_says("Erst die Adresse des Gastgebers eintippen.")
		return
	if net.join(address):
		_refresh_party()


func stop_playing_together() -> void:
	net.shut()
	_party_says("Getrennt. Du spielst wieder allein.")
	_refresh_party()


func _party_says(text: String) -> void:
	if _party_note != null:
		_party_note.text = text


## Rewrites the panel for whatever state the connection is in. Three
## states, and each one hides what makes no sense in it: you cannot join
## while hosting, and there is nothing to leave while alone.
func _refresh_party() -> void:
	if _party_panel == null:
		return
	var together: bool = net.playing_together()
	_party_host.visible = not together
	_party_field.visible = not together
	_party_join.visible = not together
	_party_leave.visible = together
	# A guest may swap hero at any time; a host picks before the run,
	# like always.
	_party_heroes.visible = net.guest

	for old in _party_again.get_children():
		old.queue_free()
	_party_again.visible = not together
	if not together:
		for address in settings.get("seen_hosts", []):
			var again := Button.new()
			again.text = str(address)
			again.custom_minimum_size = Vector2(240, 52)
			again.add_theme_font_size_override("font_size", 21)
			again.pressed.connect(_join_again.bind(str(address)))
			_party_again.add_child(again)

	if net.hosting:
		var found: Array[String] = Net.addresses()
		if found.is_empty():
			_party_where.text = ("Kein Netzwerk gefunden. Ohne WLAN oder Kabel"
				+ " kann niemand hierher finden.")
		else:
			var lines: Array[String] = []
			lines.append("Deine Adresse:  %s" % found[0])
			if found.size() > 1:
				var rest: Array[String] = []
				for at in range(1, mini(found.size(), 4)):
					rest.append(found[at])
				lines.append("Falls das nicht geht:  %s" % "   ".join(rest))
			lines.append("Port %d" % Net.PORT)
			# The one thing that catches everybody: a phone on mobile data
			# sits behind the network of its provider, and nothing from
			# outside can reach it there. The address it shows is real and
			# completely unreachable, which is the worst combination.
			if found[0].begins_with("10."):
				lines.append("Achtung: mit mobilen Daten kann dich niemand"
					+ " erreichen. WLAN oder Hotspot.")
			_party_says("Warte auf Mitspieler." + ("" if OS.get_name() != "Windows"
				else "
Windows fragt beim ersten Mal nach einer Freigabe -"
				+ " ohne 'Zulassen' kommt niemand durch."))
			_party_where.text = "\n".join(lines)
	elif net.guest:
		_party_where.text = "Gast bei %s" % _party_field.text.strip_edges()
	else:
		_party_where.text = ""

	if not together:
		_party_list.text = ""
		return
	var who: Array[String] = []
	if net.hosting:
		for peer in party:
			var hero = party[peer]
			who.append("%s (%s, Stufe %d)" % [str(net.names.get(peer, "Gast")),
				Data.class_by_id(hero.hero_class)["name"], hero.level])
	else:
		who.append("Du: %s" % Data.class_by_id(player.hero_class)["name"])
		for entry in _mates:
			who.append(Data.class_by_id(str(entry["class"]))["name"])
	_party_list.text = "Im Dungeon:  " + ",  ".join(who)

## The switches, one level below the title screen.
func _build_options_panel() -> void:
	_options_panel = PanelContainer.new()
	_options_panel.custom_minimum_size = Vector2(1120, 380)
	_options_panel.visible = false
	_solid_panel(_options_panel)
	_hud.add_child(_centred(_options_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	_options_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Einstellungen"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 36)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	_build_settings(column)

	var back := Button.new()
	back.text = "ZURÜCK"
	back.custom_minimum_size = Vector2(0, 62)
	back.add_theme_font_size_override("font_size", 26)
	back.pressed.connect(close_options)
	column.add_child(back)


## What has been done so far, and what version is doing it.
func _build_info_panel() -> void:
	_info_panel = PanelContainer.new()
	_info_panel.custom_minimum_size = Vector2(860, 460)
	_info_panel.visible = false
	_solid_panel(_info_panel)
	_hud.add_child(_centred(_info_panel))

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	_info_panel.add_child(column)

	var heading := Label.new()
	heading.text = "Info"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 36)
	heading.add_theme_color_override("font_color", Color(0.91, 0.71, 0.29))
	column.add_child(heading)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	column.add_child(row)

	var awards := Button.new()
	awards.text = "Erfolge"
	awards.custom_minimum_size = Vector2(240, 58)
	awards.add_theme_font_size_override("font_size", 25)
	awards.pressed.connect(open_awards)
	row.add_child(awards)

	var kin := Button.new()
	kin.text = "Bestiarium"
	kin.custom_minimum_size = Vector2(240, 58)
	kin.add_theme_font_size_override("font_size", 25)
	kin.pressed.connect(open_kin)
	row.add_child(kin)

	_info_record = Label.new()
	_info_record.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_info_record.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_info_record.custom_minimum_size = Vector2(800, 0)
	_info_record.add_theme_font_size_override("font_size", 22)
	_info_record.add_theme_color_override("font_color", Color(0.80, 0.80, 0.88))
	column.add_child(_info_record)

	_build_update(column)

	var back := Button.new()
	back.text = "ZURÜCK"
	back.custom_minimum_size = Vector2(0, 62)
	back.add_theme_font_size_override("font_size", 26)
	back.pressed.connect(close_info)
	column.add_child(back)


func open_options() -> void:
	if _options_panel == null:
		return
	_options_panel.get_parent().move_to_front()
	_options_panel.visible = true
	_refresh_settings()
	audio.play("equip")


func close_options() -> void:
	if _options_panel != null:
		_options_panel.visible = false


func open_info() -> void:
	if _info_panel == null:
		return
	var record := Stats.read()
	if int(record["runs"]) == 0:
		_info_record.text = "Noch kein Lauf. Viel Glück."
	else:
		_info_record.text = ("%d Läufe, %d Tode\nTiefste Ebene %d, beste Stufe %d,"
			+ " %d Kills\nBestwert %d") % [
			int(record["runs"]), int(record["deaths"]), int(record["deepest"]),
			int(record["best_level"]), int(record["kills"]), int(record["best_score"])]
	_info_panel.get_parent().move_to_front()
	_info_panel.visible = true
	audio.play("equip")


func close_info() -> void:
	if _info_panel != null:
		_info_panel.visible = false


## Puts the title screen back up and rolls a fresh floor behind it, so
## the choice is never made against the corpse of the last run.
func show_title() -> void:
	# Back to the title screen is the end of this run, and this run is
	# the session: hosting stops, guests are let go, and a guest that
	# walks out stops asking the host for floors.
	if net != null and net.playing_together():
		net.trace("zurück zum Titelbildschirm - Sitzung beendet")
		net.shut()
	choosing = true
	close_levels()
	close_options()
	close_info()
	close_pause()
	close_bag()
	if _perk_panel != null:
		_perk_panel.visible = false
	if _dead_panel != null:
		_dead_panel.visible = false
	close_shop()
	if _continue_button != null:
		_continue_button.visible = Save.exists()
	if _hint_label != null:
		# Only for someone who has never played: after the first run it is
		# a line of instructions in the way.
		_hint_label.visible = int(Stats.read()["runs"]) == 0
	if _record_label != null:
		var record := Stats.read()
		if int(record["runs"]) == 0:
			_record_label.text = "Noch kein Lauf. Viel Glück."
		else:
			_record_label.text = "%d Läufe, %d Tode - Ebene %d, Stufe %d, %d Kills, Bestwert %d" % [
				int(record["runs"]), int(record["deaths"]), int(record["deepest"]),
				int(record["best_level"]), int(record["kills"]), int(record["best_score"])]
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
	# A guest owns no dungeon, so picking a hero is a request like any
	# other. Starting a run here as well would be a second dungeon
	# pretending to be the first.
	if net != null and net.guest:
		net.ask("class:" + id)
		close_party()
		if _title_panel != null:
			_title_panel.visible = false
		if _play_ui != null:
			_play_ui.visible = true
		choosing = false
		return
	close_pause()
	close_awards()
	close_bag()
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
	_shop_panel.custom_minimum_size = Vector2(720, 440)
	_shop_panel.visible = false
	_solid_panel(_shop_panel)
	_hud.add_child(_centred(_shop_panel))

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
		var element_label: String = "Waffe verzaubern"
		if player.weapon_element != "":
			element_label = "Verzauberung neu würfeln (%s)" % Data.ELEMENTS[player.weapon_element]["name"]
		offers.append(["enchant", element_label, price(Data.SMITH_ENCHANT_PRICE)])
		offers.append(["reforge", "Waffe umschmieden (Seltenheit)",
			price(Data.SMITH_REFORGE_PRICE)])
		offers.append(["heal", "Voll heilen", price(Data.UPGRADE_COST)])

	else:
		for id in shop_open.get("stock", []):
			var potion := Data.potion_by_id(id)
			offers.append(["potion:" + id, potion["name"], price(int(potion["price"]))])
		var paper: String = shop_open.get("scroll", "")
		if paper != "":
			var scroll := Data.scroll_by_id(paper)
			offers.append(["scroll:" + paper, scroll["name"], price(int(scroll["price"]))])

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


func _button(label: String, where: Vector2, size: float, step: Vector2i) -> Button:
	var button := Button.new()
	button.text = label
	button.custom_minimum_size = Vector2(size, size)
	button.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	button.position = where
	button.add_theme_font_size_override("font_size", 40)
	# Held, not tapped: walking is what a frame rate has to be measured
	# on, and one step per tap measures nothing.
	button.button_down.connect(func() -> void:
		_held = step
		_pad_held = true)
	button.button_up.connect(func() -> void:
		_pad_held = false
		if _held == step:
			_held = Vector2i.ZERO)
	_play_ui.add_child(button)
	_pad_buttons.append(button)
	return button


func _process(delta: float) -> void:
	_glide(delta)
	# HTTPRequest has counters but no progress signal, so the running
	# download is read once a frame while the title screen is up.
	if _update_busy and _update_label != null:
		var note := updater.progress()
		if note != "":
			_update_label.text = note
	_step_cooldown -= delta
	_shot_pause -= delta
	# Keys are added up rather than taken one at a time, so holding two
	# walks diagonally. Eight directions instead of four is the other half
	# of not feeling nailed to a grid.
	var keyed := Vector2i.ZERO
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		keyed.x += 1
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		keyed.x -= 1
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		keyed.y += 1
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		keyed.y -= 1
	if keyed != Vector2i.ZERO:
		_held = _straighten(keyed)
	elif _stick != null and _stick.direction() != Vector2i.ZERO:
		_held = _straighten(_stick.direction())
	elif not _pad_held:
		# Nothing is under a finger any more, so nothing is held - checked
		# every frame, not only when the step clock happens to be ready.
		#
		# That was the second step. Let go 0.2 s into a 0.34 s wait and the
		# direction stayed standing until the clock ran out, and then the
		# block below took one more step - a fifth of a second after the
		# key was already up.
		_held = Vector2i.ZERO

	# Steps run on a clock, not per frame, so the hero does not walk faster
	# the smoother it runs.
	#
	# A tap is one step. Holding walks. Between the two sits a pause: the
	# first step happens the moment a direction appears, and the next one
	# only after REPEAT_DELAY. Without that pause a normal key press - a
	# tenth of a second or two - already produced two steps, which is
	# exactly what it felt like.
	var fresh: bool = _held != Vector2i.ZERO and _held != _stepped
	if fresh:
		_step_cooldown = 0.0
	if _held != Vector2i.ZERO and _step_cooldown <= 0.0:
		try_move(_held)
		# A diagonal covers a longer distance, so it is given proportionally
		# longer - otherwise walking at an angle is quietly forty per cent
		# faster than walking straight.
		var diagonal: bool = _held.x != 0 and _held.y != 0
		var pace: float = REPEAT_DELAY if fresh else STEP_TIME
		_step_cooldown = pace * (sqrt(2.0) if diagonal else 1.0)
		_stepped = _held
	if _held == Vector2i.ZERO:
		# Let go, and the next press counts as fresh again.
		_stepped = Vector2i.ZERO
		_auto_shoot()

	_refresh_gauges(delta)
	var line := "%s  ·  Ebene %d" % [tier.get("name", ""), depth]
	if not quest.is_empty():
		line += "     [%s%s]" % [quest["name"],
			" ✓" if quest.get("done", false) else ""]
	line += "     Stufe %d     %d Gold" % [player.level, player.gold]
	# What is in your hands, by name, on a line of its own: a rarity
	# that never appears anywhere is a number nobody can notice.
	var gear := "%s +%d     %s +%d" % [
		player.weapon_name(), player.weapon_bonus(),
		player.armour_name(), player.armour_bonus()]
	# The buffs used to be listed here as text. They have their own row
	# of plates under the bars now, where a number that is running out
	# can be seen running out.
	_play_ui.get_node("stats").text = line
	_play_ui.get_node("gear").text = gear
	_update_minimap()
	# The shooting button appears for whoever can shoot. It was built
	# hidden and then never shown again, which left a ranger on a phone
	# with auto-shooting turned off holding a bow and no way to loose it.
	if _rest_button != null:
		var mark: Variant = _reachable_foe()
		_rest_button.text = "ANGREIFEN" if mark != null else "WARTEN"
		_rest_button.add_theme_color_override("font_color",
			Color(1.0, 0.72, 0.62) if mark != null else Color(1, 1, 1))
	if _shoot_button != null:
		_shoot_button.visible = player.reach() > 0
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
