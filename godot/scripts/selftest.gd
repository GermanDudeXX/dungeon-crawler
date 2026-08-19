## Plays the Godot build headlessly and complains about what it sees.
##
##     godot --headless --script res://scripts/selftest.gd -- 3000
##
## The same idea as tests/test_playthrough.py on the Python side, and for
## the same reason: the phone is not always here, and a port is only
## worth anything if it behaves like the game it came from. Walk towards
## the stairs, hit what is in the way, drink when hurt, go down - and
## check after every single turn that nothing impossible has happened.
##
## The run happens in _process, not in _initialize: a node added to the
## tree does not get its _ready until the first frame, so in _initialize
## the game object exists but has not built itself yet and everything
## reached through it is still null.
extends SceneTree

var _turns := 3000
var _seed := 6
var _game: Node
var _problems := {}
var _notes: Array[String] = []


func _initialize() -> void:
	var numbers: Array[int] = []
	for arg in OS.get_cmdline_user_args():
		if arg.is_valid_int():
			numbers.append(arg.to_int())
	if numbers.size() > 0:
		_turns = numbers[0]
	if numbers.size() > 1:
		_seed = numbers[1]
	_game = load("res://scenes/main.tscn").instantiate()
	root.add_child(_game)


func _process(_delta: float) -> bool:
	var deepest := 1
	var descents := 0
	var deaths := 0
	var kills := 0
	var on_this_floor := 0
	# Counters for the new content. A run that never meets a boss or a
	# shop proves nothing about them, so a zero here fails the test just
	# like a broken invariant does.
	var seen := {"Bosse": 0, "Laeden": 0, "Truhen": 0, "Fallen": 0, "Mimics": 0,
		"Schriftrollen": 0, "Schreine": 0}
	var played := {}
	var perks := 0
	var shopped := false
	var drunk := {}
	var next_class := 0
	var depth_at: int = _game.depth
	var started := Time.get_ticks_msec()
	_check_audio()

	# Seeded, so a failure can be looked at again instead of being a
	# story about a run nobody can reproduce. The game randomises its
	# own generator in _ready, so this has to come after that and
	# start the run over.
	_game.rng.seed = _seed
	# A run starts behind the title screen now, so the bot picks a
	# hero like a player does - a different one each life, so all
	# three get played rather than only the default.
	_game.choose_class(Data.CLASSES[0]["id"])
	played[_game.player.hero_class] = true
	depth_at = _game.depth
	# After the hero exists and the title screen is gone: drinking is
	# refused while the game is still asking who you are.
	_check_potions()
	_check_mimic()
	_check_difficulty()
	_check_scrolls()
	_check_traps()
	_check_elements()
	_check_up_stairs()
	_check_boss_phases()
	_check_classes()
	_check_superboss()
	_check_monster_habits()

	for turn in _turns:
		if _game.dead:
			deaths += 1
			next_class = (next_class + 1) % Data.CLASSES.size()
			_game.choose_class(Data.CLASSES[next_class]["id"])
			played[_game.player.hero_class] = true
			depth_at = _game.depth
			on_this_floor = 0
			shopped = false
			continue

		# A good run can outlive the test, and then only one class ever
		# gets played. Retire the hero on schedule so all three do.
		if turn > 0 and turn % (_turns / Data.CLASSES.size()) == 0:
			next_class = (next_class + 1) % Data.CLASSES.size()
			_game.choose_class(Data.CLASSES[next_class]["id"])
			played[_game.player.hero_class] = true
			depth_at = _game.depth
			on_this_floor = 0
			shopped = false
			continue

		# Scrolls are read the moment there is one: they aim themselves,
		# so there is nothing to decide and no reason to hoard them.
		if not _game.player.scrolls.is_empty():
			var ids: Array = _game.player.scrolls.keys()
			seen["Schriftrollen"] += 1
			_game.read_scroll(ids[turn % ids.size()])
			_check("Rolle in Zug %d" % turn)
			continue

		# A player drinks when hurt - and a test has to drink everything
		# else too, or twenty-nine of the thirty flasks are never opened.
		# Every tenth turn the bot works through its stock in order.
		if _game.player.potions > 0:
			var hurt: bool = _game.player.hp < _game.player.max_hp * 0.4
			if hurt or turn % 10 == 0:
				if not hurt:
					_game.cycle_potion()
				else:
					_game.player.selected_potion = "healing" if _game.player.potion_counts.has("healing") else _game.player.selected_potion
				drunk[_game.player.selected_potion] = true
				_game.drink()

		# A level-up asks for a perk before anything else can happen.
		if _game.player.pending_perks > 0:
			var offered: int = _game.perk_choices.size()
			if offered == 0:
				_complain("Stufenaufstieg ohne Auswahl")
				_game.player.pending_perks = 0
				continue
			perks += 1
			_game.take_perk(turn % offered)
			continue

		# A shop opens when you walk into its keeper; a player leaves it.
		if _game.shop_open != null:
			seen["Laeden"] += 1
			# Buy the round, then leave and stay left: without this the
			# bot walks back into the same merchant every turn for the
			# rest of the floor and never sees the stairs again.
			shopped = true
			_game.buy("potion")
			_game.buy("weapon")
			_game.buy("armour")
			_game.close_shop()
			if _game.shop_open != null:
				_complain("Laden lässt sich nicht verlassen")
				_game.shop_open = null
			continue

		# Where a player would actually go: the chest first, then a shop
		# if there is money for it, and the stairs when there is nothing
		# left worth the detour. A bot that only ever walks to the stairs
		# never runs the shop or chest code at all.
		var target: Vector2i = _game.stairs
		var what := "Treppe"
		# Loot lying on the floor gets picked up: a bot that walks past
		# it never carries a scroll, and scrolls are then untested.
		# Always the same piece, not the nearest one. Nearest flip-flops:
		# one step towards A makes B the nearer, one step back makes A
		# nearer again, and the bot walks between two coins until the
		# floor times out. That looked exactly like an unfinishable
		# level and was not one.
		var loot_cell: Variant = null
		var loot_key := 1 << 30
		for item in _game.items:
			var cell: Vector2i = item["cell"]
			var key: int = cell.y * 1000 + cell.x
			if key < loot_key:
				loot_key = key
				loot_cell = cell

		# A shrine is a coin flip worth taking, so a player takes it.
		if _game.shrine != null:
			target = _game.shrine
			what = "Schrein"
		# Nobody walks past an unopened chest either.
		elif loot_cell != null:
			target = loot_cell
			what = "Beute"
		elif _game.chest != null and not _game.chest["opened"]:
			target = _game.chest["cell"]
			what = "Truhe"
		elif not shopped and _game.player.gold >= Data.POTION_COST:
			for shop in _game.shops:
				target = shop["cell"]
				what = "Laden"
				break
		# The way down can be locked behind a boss, and the game says so.
		# A player goes and kills it rather than walking into the door
		# for the rest of the run.
		if _game.stairs_locked and _game.boss_alive():
			for m in _game.monsters:
				if m.is_alive() and m.is_boss:
					target = Vector2i(m.x, m.y)
					what = "Boss"
					break
		var step: Variant = _route(target)
		if step == null:
			# A target that cannot be walked to at all is a placement bug:
			# something got put behind a wall, or a keeper closed the only
			# way through. Naming which one it was is the whole point -
			# "stairs unreachable" for a walled-off chest sent me looking
			# in the wrong file.
			_complain("%s unerreichbar" % what,
				"Ebene %d, Ziel %s, Treppe %s, Spieler (%d, %d)"
				% [_game.depth, str(target), str(_game.stairs),
				_game.player.x, _game.player.y])
			_next_floor()
			depth_at = _game.depth
			on_this_floor = 0
			shopped = false
			continue

		if turn > 0 and turn % 250 == 0:
			_check_save()

		var before: int = _game.player.kills
		var bosses_before := 0
		var mimic_before := false
		for m in _game.monsters:
			if m.is_alive() and m.is_boss:
				bosses_before += 1
			if m.is_alive() and m.is_mimic:
				mimic_before = true
		var chest_before: bool = _game.chest != null and _game.chest["opened"]
		var traps_before: int = _game.traps.size()
		var shrine_before = _game.shrine
		_game.try_move(step)
		kills += _game.player.kills - before
		var bosses_now := 0
		var mimic_now := false
		for m in _game.monsters:
			if m.is_alive() and m.is_boss:
				bosses_now += 1
			if m.is_alive() and m.is_mimic:
				mimic_now = true
		if _game.depth == depth_at:
			if bosses_now < bosses_before:
				seen["Bosse"] += 1
			if mimic_now and not mimic_before:
				seen["Mimics"] += 1
			if _game.chest != null and _game.chest["opened"] and not chest_before:
				seen["Truhen"] += 1
			if _game.traps.size() < traps_before:
				seen["Fallen"] += 1
			if shrine_before != null and _game.shrine == null:
				seen["Schreine"] += 1
		_check("Zug %d, Ebene %d" % [turn, _game.depth])

		if _game.depth != depth_at:
			descents += 1
			deepest = maxi(deepest, _game.depth)
			_check_placement()
			shopped = false
			depth_at = _game.depth
			on_this_floor = 0
			shopped = false
		else:
			on_this_floor += 1
			if on_this_floor > 600:
				var cells_note: Array[String] = []
				for item in _game.items:
					cells_note.append("%s%s" % [item["kind"], str(item["cell"])])
				_notes.append("  steckt: Held (%d,%d) Ziel %s (%s), Treppe %s, Beute [%s], Truhe %s, Schrein %s" % [
					_game.player.x, _game.player.y, str(target), what, str(_game.stairs),
					", ".join(cells_note), str(_game.chest), str(_game.shrine)])
				var boss_note := "kein Boss"
				for m in _game.monsters:
					if m.is_alive() and m.is_boss:
						boss_note = "%s %d/%d Leben, Schaden %d, Abwehr %d bei (%d,%d)" % [
							m.display_name, m.hp, m.max_hp, m.power, m.defense, m.x, m.y]
				_complain("Ebene nicht abschließbar",
					"Ebene %d, %d Züge, Held Stufe %d mit %d Schaden, verriegelt=%s, %s" % [
					_game.depth, on_this_floor, _game.player.level, _game.player.power(),
					str(_game.stairs_locked), boss_note])
				_next_floor()
				depth_at = _game.depth
				on_this_floor = 0

	print("  %d Zuege in %d ms: Ebene %d erreicht, %d Abstiege, %d Tode, %d Kills"
		% [_turns, Time.get_ticks_msec() - started, deepest, descents, deaths, kills])

	var parts: Array[String] = []
	for what in seen:
		parts.append("%d %s" % [seen[what], what])
	print("  angefasst: " + ", ".join(parts))
	print("  gespielt: %s, %d Gaben gewählt" % [", ".join(played.keys()), perks])
	print("  getrunken: %d von %d Trankarten" % [drunk.size(), Data.POTIONS.size()])

	if perks == 0:
		print("  nie eine Gabe gewählt - der Stufenaufstieg ist ungetestet")

	var failed := false
	if played.size() < Data.CLASSES.size():
		print("  nicht jede Klasse gespielt: %d von %d" % [played.size(), Data.CLASSES.size()])
		failed = true
	# Every one of these has a check of its own that does not depend
	# on the dice, so a run that happens not to meet one is worth
	# printing, not failing. A test that goes red for no reason is a
	# test people learn to ignore.
	for what in seen:
		if seen[what] == 0:
			print("  im Durchlauf nie getroffen: %s (hat eine eigene Prüfung)" % what)
	for what in _problems:
		print("  %5dx  %s" % [_problems[what], what])
		failed = true
	for note in _notes:
		print("    " + note)
	if descents < 3:
		print("  nur %d Abstiege - so ist das Spiel nicht durchspielbar" % descents)
		failed = true

	if failed:
		print("SELFTEST FEHLGESCHLAGEN")
		quit(1)
	else:
		print("ALL GODOT PLAYTHROUGH CHECKS PASSED")
		quit(0)
	return true


func _next_floor() -> void:
	_game.depth += 1
	_game.new_level()


func _complain(what: String, detail: String = "") -> void:
	_problems[what] = _problems.get(what, 0) + 1
	if _problems[what] <= 2 and detail != "":
		_notes.append("%s: %s" % [what, detail])


## One step towards target, or null when there is no way there at all.
func _route(target: Vector2i) -> Variant:
	var start := Vector2i(_game.player.x, _game.player.y)
	if start == target:
		return Vector2i.ZERO
	var came := {start: start}
	var queue: Array[Vector2i] = [start]
	var found := false
	while not queue.is_empty() and not found:
		var cell: Vector2i = queue.pop_front()
		for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var step: Vector2i = cell + offset
			if came.has(step):
				continue
			if not Dungeon.is_walkable(_game.grid, step.x, step.y) or _game.blocks(step):
				continue
			# There is no getting past a shopkeeper, so a route may not
			# plan through one - the same reason they may not stand in a
			# chokepoint.
			if step != target and _game.shop_at(step) != null:
				continue
			came[step] = cell
			if step == target:
				found = true
				break
			queue.append(step)
	if not came.has(target):
		return null
	var cell: Vector2i = target
	while came[cell] != start:
		cell = came[cell]
	return cell - start


func _check(where: String) -> void:
	var p = _game.player
	if p.hp > p.max_hp:
		_complain("Leben ueber dem Maximum", "%d/%d bei %s" % [p.hp, p.max_hp, where])
	if p.gold < 0:
		_complain("negatives Gold", "%d bei %s" % [p.gold, where])
	if not Dungeon.is_walkable(_game.grid, p.x, p.y):
		_complain("Spieler steckt in einer Wand", "(%d, %d) bei %s" % [p.x, p.y, where])
	for m in _game.monsters:
		if not m.is_alive():
			continue
		if m.x == p.x and m.y == p.y:
			_complain("Monster steht auf dem Spieler", "%s bei %s" % [m.kind, where])
		if m.hp > m.max_hp:
			_complain("Monster-Leben ueber dem Maximum", "%s bei %s" % [m.kind, where])
		if not Dungeon.is_walkable(_game.grid, m.x, m.y):
			_complain("Monster steckt in einer Wand", "%s bei %s" % [m.kind, where])
	# The two potion counters have to agree. They disagreed once, and
	# the symptom was a flask that showed in the count, could not be
	# drunk, and vanished on the next load.
	var carried := 0
	for id in p.potion_counts:
		carried += int(p.potion_counts[id])
		if int(p.potion_counts[id]) <= 0:
			_complain("leerer Trank-Eintrag im Inventar", "%s bei %s" % [id, where])
		if not Data.POTIONS.any(func(entry): return entry["id"] == id):
			_complain("unbekannte Trankart im Inventar", "%s bei %s" % [id, where])
	if carried != p.potions:
		_complain("Trankzähler und Inventar stimmen nicht überein",
			"%d gegen %d bei %s" % [p.potions, carried, where])
	if p.shield < 0 or p.poison_turns < 0 or p.bleed_turns < 0:
		_complain("negativer Zustandswert", where)
	for id in p.buffs:
		if int(p.buffs[id]) <= 0:
			_complain("abgelaufener Buff hängt fest", "%s bei %s" % [id, where])
		if not Data.BUFFS.has(id):
			_complain("unbekannter Buff", "%s bei %s" % [id, where])
	for id in p.scrolls:
		if int(p.scrolls[id]) <= 0:
			_complain("leerer Rollen-Eintrag", "%s bei %s" % [id, where])
	# Two monsters on one cell means one of them cannot be attacked.
	var cells := {}
	for m in _game.monsters:
		if not m.is_alive():
			continue
		if cells.has(m.cell()):
			_complain("zwei Monster auf einem Feld",
				"%s und %s bei %s" % [m.kind, cells[m.cell()], where])
		cells[m.cell()] = m.kind
	if p.level < 1 or p.max_hp < 1:
		_complain("unmoegliche Spielerwerte", "Stufe %d bei %s" % [p.level, where])


## Everything about the run a save has to bring back. Compared as a
## string so a difference names itself in the output instead of being a
## bare "not equal".
func _fingerprint() -> String:
	var p = _game.player
	var parts: Array[String] = [
		"Klasse=%s" % p.hero_class,
		"Ebene=%d" % _game.depth,
		"Held=(%d,%d) %d/%d HP, Stufe %d, %d Gold, %d Traenke, Gift %d" % [
			p.x, p.y, p.hp, p.max_hp, p.level, p.gold, p.potions, p.poison_turns],
		"Waffe=%s(%d) Ruestung=%s(%d) Schild=%d Bluten=%d" % [
			p.weapon_name(), p.weapon_bonus(), p.armour_name(), p.armour_bonus(),
			p.shield, p.bleed_turns],
		"Traenke=%s gewaehlt=%s" % [_stable(p.potion_counts), p.selected_potion],
		"Buffs=%s Rollen=%s" % [_stable(p.buffs), _stable(p.scrolls)],
		"Schrein=%s" % str(_game.shrine),
		"Angriff=%d Verteidigung=%d Krit=%.3f Minderung=%.3f Gold x%.2f" % [
			p.base_power, p.base_defense, p.bonus_crit, p.damage_reduction, p.gold_mult],
		"Regen=%d/%d offen=%d" % [p.regen_counter, p.regen_interval, p.pending_perks],
		"Treppe=%s verriegelt=%s" % [str(_game.stairs), str(_game.stairs_locked)],
		"erkundet=%d" % _game.explored.size(),
		"Fallen=%d Laeden=%d Beute=%d" % [
			_game.traps.size(), _game.shops.size(), _game.items.size()],
		"Truhe=%s" % str(_game.chest),
	]
	var alive: Array[String] = []
	for m in _game.monsters:
		if m.is_alive():
			alive.append("%s@%d,%d %d/%d g%d%s" % [m.kind, m.x, m.y, m.hp, m.max_hp,
				m.generation, "E" if m.is_elite else ""])
	alive.sort()
	parts.append("Monster=[%s]" % ", ".join(alive))
	var walls := 0
	for row in _game.grid:
		for value in row:
			if value == Dungeon.WALL:
				walls += 1
	parts.append("Waende=%d" % walls)
	return " | ".join(parts)


## Saves the run, loads it straight back, and insists it is the same
## run. A save that quietly loses the boss, the gold or half the map is
## worse than no save at all: the player only finds out much later.
func _check_save() -> void:
	var before := _fingerprint()
	_game.save_run()
	if not _game.load_run():
		_complain("Spielstand nicht lesbar")
		return
	var after := _fingerprint()
	if before != after:
		_complain("Spielstand kommt anders zurueck")
		_notes.append("  vorher: " + before)
		_notes.append("  nachher: " + after)


## The sounds are generated, and nobody here can hear them. What can be
## checked is that each one exists, is as long as it claims, and is not
## silence - a formula slip that produced a quarter second of zeroes
## would otherwise ship as "the game just has no hit sound".
func _check_audio() -> void:
	var audio = _game.audio
	if audio == null:
		_complain("kein Ton-Knoten")
		return
	for name in Audio.TONES:
		var stream: AudioStreamWAV = audio._streams.get(name)
		if stream == null:
			_complain("Ton fehlt", name)
			continue
		var seconds := 0.0
		for part in Audio.TONES[name]:
			seconds += float(part[2])
		var expected := int(Audio.SAMPLE_RATE * seconds) * 2
		if absi(stream.data.size() - expected) > 8:
			_complain("Ton hat die falsche Länge",
				"%s: %d statt %d Bytes" % [name, stream.data.size(), expected])
		var loudest := 0
		for i in range(0, stream.data.size() - 1, 2):
			var value: int = stream.data[i] | (stream.data[i + 1] << 8)
			if value > 32767:
				value -= 65536
			loudest = maxi(loudest, absi(value))
		if loudest < 3000:
			_complain("Ton ist zu leise oder stumm", "%s: Spitze %d" % [name, loudest])

	for tier in Data.TIERS:
		var file: String = tier.get("music", "")
		if file == "" or not ResourceLoader.exists(Audio.MUSIC_DIR + file):
			_complain("Musikstück fehlt", "%s: %s" % [tier["id"], file])


## Nothing may share a cell with anything else. A shopkeeper standing on
## the chest makes the chest unopenable, a second shopkeeper on the first
## makes one of them unreachable, and neither shows up as a crash - the
## floor simply quietly holds less than it should.
func _check_placement() -> void:
	# The stairs have to be walkable to, with every shopkeeper counted
	# as a wall - they are one. A floor that fails this is a floor the
	# run ends on.
	var blocked := {}
	for shop in _game.shops:
		blocked[shop["cell"]] = true
	var open_cells: Dictionary = _game.reachable_from(
		Vector2i(_game.player.x, _game.player.y), blocked)
	if not open_cells.has(_game.stairs):
		_complain("Treppe von Anfang an unerreichbar",
			"Ebene %d, Treppe %s" % [_game.depth, str(_game.stairs)])
	if _game.chest != null and not open_cells.has(_game.chest["cell"]):
		_complain("Truhe von Anfang an unerreichbar",
			"Ebene %d, Truhe %s" % [_game.depth, str(_game.chest["cell"])])
	for item in _game.items:
		if not open_cells.has(item["cell"]):
			_complain("Beute unerreichbar abgelegt",
				"Ebene %d, %s auf %s" % [_game.depth, item["kind"], str(item["cell"])])
		if not Dungeon.is_walkable(_game.grid, item["cell"].x, item["cell"].y):
			_complain("Beute steckt in einer Wand", str(item["cell"]))
	var seen_here := {}
	var things: Array = []
	for shop in _game.shops:
		things.append([shop["cell"], "Laden (%s)" % shop["kind"]])
	if _game.chest != null:
		things.append([_game.chest["cell"], "Truhe"])
	if _game.shrine != null:
		things.append([_game.shrine, "Schrein"])
	for cell in _game.traps:
		things.append([cell, "Falle"])
	for cell in _game.hazards:
		things.append([cell, "Gefahr"])
	for cell in _game.decor:
		things.append([cell, "Dekor"])
	for item in _game.items:
		things.append([item["cell"], "Beute (%s)" % item["kind"]])
	for entry in things:
		var cell: Vector2i = entry[0]
		if seen_here.has(cell):
			_complain("zwei Dinge auf einem Feld",
				"Ebene %d, %s auf %s bei %s" % [
				_game.depth, entry[1], seen_here[cell], str(cell)])
		seen_here[cell] = entry[1]
		if cell == _game.stairs:
			_complain("etwas steht auf der Treppe",
				"Ebene %d, %s" % [_game.depth, entry[1]])


## Drinks every single potion in the game once and insists it did what
## its own table says it does.
##
## The playthrough alone only ever opens the handful of flasks the first
## few floors hand out - the deep ones are gated behind depth and would
## ship untested. This does not care about depth: it puts one of each in
## the hero's hands and checks the effect landed.
func _check_potions() -> void:
	for potion in Data.POTIONS:
		var id: String = potion["id"]
		var effect: Dictionary = potion["effect"]
		var p = _game.player

		# A clean slate, and hurt enough that a heal has room to work.
		p.buffs.clear()
		p.shield = 0
		# Poisoned and bleeding only where the flask claims to cure it.
		# Drinking costs a turn, and a turn of bleeding takes a hit point
		# right back off - which read as "the Elixir does not heal fully"
		# when the fault was the setup, not the potion.
		var cures: bool = effect.has("cure")
		p.poison_turns = 3 if cures else 0
		p.bleed_turns = 3 if cures else 0
		p.max_hp = 60
		p.hp = 20
		p.gold = 100
		p.add_potion(id)
		p.selected_potion = id

		var hp_before: int = p.hp
		var max_before: int = p.max_hp
		var power_before: int = p.base_power
		var defense_before: int = p.base_defense
		var gold_before: int = p.gold
		var carried: int = p.potions
		var explored_before: int = _game.explored.size()

		_game.drink()

		if p.potions != carried - 1:
			_complain("Trank wurde nicht verbraucht", id)
		if p.hp > p.max_hp:
			_complain("Trank heilt über das Maximum", "%s: %d/%d" % [id, p.hp, p.max_hp])
		if effect.has("heal") and p.hp <= hp_before:
			_complain("Heiltrank heilt nicht", id)
		if effect.has("heal_pct") and p.hp != p.max_hp:
			_complain("Elixier heilt nicht voll", id)
		if effect.has("max_hp") and p.max_hp != max_before + int(effect["max_hp"]):
			_complain("maximales Leben unverändert", id)
		if effect.has("base_power") and p.base_power != power_before + int(effect["base_power"]):
			_complain("Angriff unverändert", id)
		if effect.has("base_defense") and p.base_defense != defense_before + int(effect["base_defense"]):
			_complain("Verteidigung unverändert", id)
		if effect.has("buff"):
			var buff: String = effect["buff"]
			if not Data.BUFFS.has(buff):
				_complain("Trank verweist auf einen unbekannten Buff", "%s -> %s" % [id, buff])
			elif not p.buffs.has(buff):
				_complain("Buff wirkt nicht", "%s -> %s" % [id, buff])
		if effect.has("shield") and p.shield <= 0:
			_complain("Schild bleibt aus", id)
		if effect.has("gold") and p.gold <= gold_before:
			_complain("Gold kommt nicht an", id)
		if effect.has("reveal") and _game.explored.size() <= explored_before:
			_complain("Klarheit deckt nichts auf", id)
		if effect.has("cure"):
			for what in effect["cure"]:
				if what == "poison_turns" and p.poison_turns != 0:
					_complain("Gift wird nicht geheilt", id)
				if what == "bleed_turns" and p.bleed_turns != 0:
					_complain("Bluten wird nicht gestillt", id)
		if effect.has("self_poison") and p.poison_turns <= 0:
			_complain("verfluchter Trank vergiftet nicht", id)
		if not Dungeon.is_walkable(_game.grid, p.x, p.y):
			_complain("Trank setzt den Helden in eine Wand", id)
		if _game.dead:
			_complain("Trank tötet den Helden", id)
			_game.dead = false
			p.hp = p.max_hp


## Opens a chest that is a mimic, on purpose, and checks the one rule
## that matters: it comes out *beside* the hero, never underneath.
##
## A monster sharing your tile cannot be attacked at all, because attacks
## are aimed at the tile you walk into - the pygame build had exactly
## that bug. Waiting for the playthrough to roll a mimic tests it only
## sometimes: it is a 30% branch of a 55% chest, so a whole run can pass
## without ever opening one.
func _check_mimic() -> void:
	_settle()
	var spot: Variant = _open_spot()
	if spot == null:
		_notes.append("keine freie Zelle für den Mimik-Test - übersprungen")
		return
	var before: int = _game.monsters.size()
	_game.chest = {"cell": spot, "mimic": true, "opened": false}
	_game.player.x = spot.x
	_game.player.y = spot.y
	_game._open_chest(spot)
	if _game.monsters.size() != before + 1:
		_complain("Mimik erscheint nicht")
		_game.chest = null
		return
	var mimic = _game.monsters[-1]
	if not mimic.is_mimic:
		_complain("Mimik ist nicht als solche markiert")
	if mimic.x == _game.player.x and mimic.y == _game.player.y:
		_complain("Mimik steht auf dem Helden",
			"(%d, %d) - sie wäre unangreifbar" % [mimic.x, mimic.y])
	if absi(mimic.x - spot.x) > 1 or absi(mimic.y - spot.y) > 1:
		_complain("Mimik erscheint zu weit weg",
			"(%d, %d) statt neben (%d, %d)" % [mimic.x, mimic.y, spot.x, spot.y])
	if not mimic.awake:
		_complain("Mimik schläft nach dem Zuschnappen")
	_game.monsters.erase(mimic)
	_game.chest = null


## A walkable cell with a free neighbour, for tests that need to put
## something down next to the hero.
func _open_spot() -> Variant:
	for y in range(1, 24):
		for x in range(1, 39):
			var cell := Vector2i(x, y)
			if not Dungeon.is_walkable(_game.grid, x, y) or _game.occupied(cell):
				continue
			for offset in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var beside: Vector2i = cell + offset
				var free: bool = Dungeon.is_walkable(_game.grid, beside.x, beside.y) \
					and not _game.occupied(beside)
				if free:
					return cell
	return null


## The four levels of play have to actually differ, and in the right
## direction. The multipliers are baked in when a monster is built, so a
## typo there is invisible until someone plays Hardcore and finds it
## easier than Normal.
func _check_difficulty() -> void:
	var last_hp := 0
	var last_power := 0
	for entry in Data.DIFFICULTIES:
		var id: String = entry["id"]
		var hero = Entities.Player.new("warrior", id)
		var expected: int = maxi(1, int(round(20 * 1.4 * float(entry["player_hp"]))))
		if hero.max_hp != expected:
			_complain("Schwierigkeit ändert das Heldenleben nicht",
				"%s: %d statt %d" % [id, hero.max_hp, expected])

		var orc = Entities.Monster.new("orc", 1.0, id)
		if id != "easy":
			if orc.max_hp < last_hp:
				_complain("härtere Stufe hat schwächere Gegner",
					"%s: %d Leben nach %d" % [id, orc.max_hp, last_hp])
			if orc.power < last_power:
				_complain("härtere Stufe trifft schwächer",
					"%s: %d Schaden nach %d" % [id, orc.power, last_power])
		last_hp = orc.max_hp
		last_power = orc.power

		# Prices climb with the markup, and the smith is the one that has
		# to feel it - he is the gold sink.
		_game.difficulty = id
		var asked: int = _game.price(100)
		var want: int = int(round(100 * (1.0 + float(entry["markup"]))))
		if asked != want:
			_complain("Preisaufschlag stimmt nicht", "%s: %d statt %d" % [id, asked, want])
	_game.difficulty = Data.DEFAULT_DIFFICULTY


## Reads each scroll once and checks it did its job. Same reason as the
## potions: scrolls are an 8% drop, so a short run can end without one
## ever being carried, and "the fireball does nothing" is not something
## to find out on a phone.
func _check_scrolls() -> void:
	_settle()
	var p = _game.player

	# Enthüllung: the whole floor becomes known.
	_game.explored.clear()
	_game.explored[Vector2i(p.x, p.y)] = true
	p.scrolls["reveal"] = 1
	_game.read_scroll("reveal")
	if _game.explored.size() < 50:
		_complain("Enthüllung deckt die Ebene nicht auf",
			"%d Felder bekannt" % _game.explored.size())
	if p.scrolls.has("reveal"):
		_complain("Schriftrolle wird nicht verbraucht", "reveal")

	# Blitzreise: the hero ends up somewhere else, and somewhere legal.
	var was := Vector2i(p.x, p.y)
	p.scrolls["teleport"] = 1
	_game.read_scroll("teleport")
	if Vector2i(p.x, p.y) == was:
		_complain("Blitzreise bewegt den Helden nicht")
	if not Dungeon.is_walkable(_game.grid, p.x, p.y):
		_complain("Blitzreise setzt den Helden in eine Wand")

	# Feuerball: something in sight loses health, or dies.
	var spot: Variant = _open_spot()
	if spot == null:
		return
	p.x = spot.x
	p.y = spot.y
	var target = Entities.Monster.new("orc", 4.0, "easy")
	target.x = spot.x + 1
	target.y = spot.y
	target.snap()
	_game.monsters.append(target)
	_game.recompute_fov()
	# Measured across everything alive, not on the one dummy: the
	# fireball picks its own target, and with swarms on the floor the
	# nearest visible thing may well be a rat standing just as close.
	var before := 0
	for m in _game.monsters:
		if m.is_alive():
			before += m.hp
	p.scrolls["fireball"] = 1
	_game.read_scroll("fireball")
	var after := 0
	for m in _game.monsters:
		if m.is_alive():
			after += m.hp
	if after >= before:
		_complain("Feuerball richtet keinen Schaden an",
			"%d Leben vorher, %d nachher" % [before, after])
	_game.monsters.erase(target)


## Springs every kind of trap on purpose. Which traps a floor gets is a
## dice roll, so a run can end without stepping on one - and a trap that
## does nothing is a trap nobody notices is broken.
func _check_traps() -> void:
	_settle()
	for id in Data.TRAPS:
		var trap: Dictionary = Data.TRAPS[id]
		var p = _game.player
		var spot: Variant = _open_spot()
		if spot == null:
			return
		p.max_hp = 200
		p.hp = 200
		p.poison_turns = 0
		p.damage_reduction = 0.0
		_game.dead = false
		_game.traps[spot] = id
		p.x = spot.x
		p.y = spot.y
		_game._spring_trap(spot)
		if p.hp >= 200:
			_complain("Falle richtet keinen Schaden an", id)
		if trap.has("poison") and p.poison_turns <= 0:
			_complain("Giftfalle vergiftet nicht", id)
		# One-shot traps are gone after springing; the others stay armed.
		var still_there: bool = _game.traps.has(spot)
		if trap.get("one_shot", false) and still_there:
			_complain("Einmalfalle bleibt liegen", id)
		if not trap.get("one_shot", false) and not still_there:
			_complain("Dauerfalle verschwindet", id)
		_game.traps.erase(spot)


## Swings each elemental weapon at a monster until the element fires, and
## checks it left the mark it promises. A 30-40% proc on a 30% drop is
## not something a playthrough can be relied on to reach.
func _check_elements() -> void:
	_settle()
	var p = _game.player
	var was: String = p.weapon_element
	for id in Data.ELEMENTS:
		var element: Dictionary = Data.ELEMENTS[id]
		p.weapon_element = id
		var spot: Variant = _open_spot()
		if spot == null:
			break
		var dummy = Entities.Monster.new("orc", 40.0, "easy")
		dummy.x = spot.x
		dummy.y = spot.y
		dummy.snap()
		_game.monsters.append(dummy)
		# Forty swings: at the lowest proc chance in the table that is a one
		# in a hundred thousand chance of seeing nothing at all.
		var landed := false
		for _swing in 40:
			_game._fire_element(dummy)
			match element["status"]:
				"burn":
					landed = dummy.burn_turns > 0
				"weaken":
					landed = dummy.weaken_turns > 0
				"stun":
					landed = dummy.stun_turns > 0
				"poison":
					landed = dummy.venom_turns > 0
			if landed:
				break
		if not landed:
			_complain("Element wirkt nie", "%s (%s)" % [id, element["status"]])
		var frozen: bool = id == "frost" and dummy.weaken_turns > 0 and dummy.defense > 0
		if frozen and dummy.defense_now() >= dummy.defense:
			_complain("Frost senkt die Verteidigung nicht",
				"%d bleibt %d" % [dummy.defense, dummy.defense_now()])
		_game.monsters.erase(dummy)
	p.weapon_element = was


## The way back up. Not a way to escape a floor - the one above is
## generated fresh - but it has to exist, be walkable, and not send the
## hero above the first floor.
func _check_up_stairs() -> void:
	_settle()
	_game.depth = 4
	_game.new_level()
	var up: Vector2i = _game.up_stairs
	if not Dungeon.is_walkable(_game.grid, up.x, up.y):
		_complain("Aufstieg liegt in einer Wand", str(up))
	if up == _game.stairs:
		_complain("Auf- und Abstieg auf demselben Feld", str(up))

	# Standing on it and stepping into it are different things: the hero
	# starts on the up staircase, so walking off and back on is what a
	# player actually does.
	_game.player.x = up.x
	_game.player.y = up.y + 1
	if Dungeon.is_walkable(_game.grid, up.x, up.y + 1):
		_game.try_move(Vector2i(0, -1))
		if _game.depth != 3:
			_complain("Aufstieg führt nicht nach oben", "Ebene %d statt 3" % _game.depth)

	# And never above the top.
	_game.depth = 1
	_game.new_level()
	_game.player.x = _game.up_stairs.x
	_game.player.y = _game.up_stairs.y + 1
	if Dungeon.is_walkable(_game.grid, _game.player.x, _game.player.y):
		_game.try_move(Vector2i(0, -1))
		if _game.depth < 1:
			_complain("Aufstieg über Ebene 1 hinaus", "Ebene %d" % _game.depth)


## Puts the game back into a state where the hero can act.
##
## The direct checks leave things standing: the Potion of Insight grants
## half a level, which opens the perk panel, and movement is blocked
## while that is up. A later check then reads "the up staircase does not
## work" when what actually happened is that the hero was still choosing
## a gift.
func _settle() -> void:
	while _game.player.pending_perks > 0 and not _game.perk_choices.is_empty():
		_game.take_perk(0)
	_game.player.pending_perks = 0
	if _game._perk_panel != null:
		_game._perk_panel.visible = false
	_game.close_shop()
	_game.dead = false
	_game.player.hp = maxi(1, _game.player.hp)


## A wounded boss has to hit harder than a fresh one, and a healed one
## has to calm down again - the phase is read from health, not latched.
func _check_boss_phases() -> void:
	_settle()
	var fresh := Data.boss_phase(100, 100)
	if not fresh.is_empty():
		_complain("frischer Boss ist schon in einer Phase", str(fresh))
	var hurt := Data.boss_phase(60, 100)
	var cornered := Data.boss_phase(20, 100)
	if hurt.is_empty() or cornered.is_empty():
		_complain("Boss erreicht seine Phasen nicht")
		return
	if float(cornered["power"]) <= float(hurt["power"]):
		_complain("verzweifelter Boss schlägt nicht härter",
			"%.2f gegen %.2f" % [float(cornered["power"]), float(hurt["power"])])
	if not Data.boss_phase(100, 100).is_empty():
		_complain("geheilter Boss bleibt wütend")


## Each class has to start with what its own table says, and the three
## have to differ - a class that is only a different number is three of
## the same character.
func _check_classes() -> void:
	var hands := {}
	for info in Data.CLASSES:
		var hero = Entities.Player.new(info["id"], "normal")
		for id in info["potions"]:
			if int(hero.potion_counts.get(id, 0)) != int(info["potions"][id]):
				_complain("Starttränke fehlen",
					"%s: %s" % [info["id"], id])
		for id in info.get("scrolls", {}):
			if int(hero.scrolls.get(id, 0)) != int(info["scrolls"][id]):
				_complain("Startrollen fehlen", "%s: %s" % [info["id"], id])
		if hero.potions <= 0:
			_complain("Klasse startet ohne jeden Trank", info["id"])
		if not hero.potion_counts.has(hero.selected_potion):
			_complain("gewählter Trank wird nicht getragen",
				"%s: %s" % [info["id"], hero.selected_potion])
		if hero.weapon_bonus() < 0 or hero.armour_bonus() < 0:
			_complain("negative Startausrüstung", info["id"])
		hands[info["id"]] = "%d/%d/%s/%s" % [
			hero.max_hp, hero.base_power, str(hero.potion_counts), str(hero.scrolls)]
	var seen_hands := {}
	for id in hands:
		if seen_hands.has(hands[id]):
			_complain("zwei Klassen starten identisch",
				"%s und %s" % [id, seen_hands[hands[id]]])
		seen_hands[hands[id]] = id


## A dictionary as text, in a fixed order. JSON does not promise to give
## keys back in the order they went in, so comparing str(dict) across a
## save and a load reports a difference where there is none - it did,
## and the "difference" was two potions swapping places.
func _stable(values: Dictionary) -> String:
	var keys: Array = values.keys()
	keys.sort()
	var parts: Array[String] = []
	for key in keys:
		parts.append("%s=%s" % [key, values[key]])
	return "{%s}" % ", ".join(parts)


## Ebene 25 has to actually hold the thing it promises, and it has to be
## worse than the boss two floors above it - otherwise the deepest fight
## in the game is an ordinary one with a name.
func _check_superboss() -> void:
	_settle()
	if not Data.has_boss(Data.SUPERBOSS_LEVEL):
		_complain("Ebene %d hat gar keinen Boss" % Data.SUPERBOSS_LEVEL)
		return
	# The boss floor just above, whichever that is - boss floors are
	# every third one, so "three floors up" is not one of them.
	var previous := Data.SUPERBOSS_LEVEL - 1
	while previous > 1 and not Data.has_boss(previous):
		previous -= 1
	var strengths := {}
	for level in [previous, Data.SUPERBOSS_LEVEL]:
		_game.depth = level
		_game.new_level()
		var found := 0
		for m in _game.monsters:
			if m.is_boss:
				found += 1
				strengths[level] = m.max_hp
		if found == 0:
			_complain("Bossebene ohne Boss", "Ebene %d" % level)
		if found > 1:
			_complain("mehr als ein Boss auf einer Ebene", "Ebene %d: %d" % [level, found])
	if strengths.has(Data.SUPERBOSS_LEVEL) and strengths.has(previous):
		if strengths[Data.SUPERBOSS_LEVEL] <= strengths[previous]:
			_complain("Superboss ist nicht stärker",
				"%d gegen %d Leben auf Ebene %d" % [strengths[Data.SUPERBOSS_LEVEL],
				strengths[previous], previous])


## Each kind of monster has to actually do the thing its entry claims.
## The numbers are easy to check by reading; a habit that quietly never
## fires is not.
func _check_monster_habits() -> void:
	_settle()
	_game.depth = 6
	_game.new_level()

	# Swarming kinds arrive in company. Generated fresh a few times,
	# since where they land depends on the room.
	var biggest := 0
	for _try in 6:
		_game.new_level()
		var counts := {}
		for m in _game.monsters:
			counts[m.kind] = int(counts.get(m.kind, 0)) + 1
		for kind in counts:
			if Data.MONSTERS[kind].has("swarms"):
				biggest = maxi(biggest, int(counts[kind]))
	if biggest < 2:
		_complain("Schwarmtiere kommen einzeln", "größte Gruppe: %d" % biggest)

	# A slime leaves two smaller ones behind.
	var spot: Variant = _open_spot()
	if spot != null:
		var slime = Entities.Monster.new("slime", 4.0, "normal")
		slime.x = spot.x
		slime.y = spot.y
		slime.snap()
		_game.monsters.append(slime)
		var before: int = _game.monsters.size()
		_game._kill(slime)
		var after: int = _game.monsters.size()
		if after <= before - 1:
			_complain("Schleim teilt sich nicht", "%d statt mehr Monster" % after)
		for m in _game.monsters.duplicate():
			if m.generation > 0:
				if m.max_hp >= slime.max_hp:
					_complain("Schleimhälfte ist nicht kleiner",
						"%d gegen %d" % [m.max_hp, slime.max_hp])
				_game.monsters.erase(m)

	# A skeleton shoots from a distance instead of walking up.
	var shooter_spot: Variant = _open_spot()
	if shooter_spot != null:
		var bones = Entities.Monster.new("skeleton", 1.0, "normal")
		if not bones.ranged or not bones.kites:
			_complain("Skelett schießt gar nicht")
		bones.x = shooter_spot.x
		bones.y = shooter_spot.y
		bones.awake = true
		bones.snap()
		_game.monsters.append(bones)
		_game.player.x = shooter_spot.x + 3
		_game.player.y = shooter_spot.y
		_game.player.max_hp = 300
		_game.player.hp = 300
		_game.player.base_defense = 0
		_game.player.armour = 0
		_game.player.armour_extra = 0
		if Dungeon.is_walkable(_game.grid, _game.player.x, _game.player.y):
			var hp_before: int = _game.player.hp
			for _turn in 4:
				_game.enemy_turn()
			if _game.player.hp >= hp_before and bones.is_alive():
				_complain("Skelett trifft aus der Entfernung nie",
					"Abstand 3, %d Leben unverändert" % hp_before)
		_game.monsters.erase(bones)

	# A goblin leaves traps behind.
	var goblin_spot: Variant = _open_spot()
	if goblin_spot != null:
		var goblin = Entities.Monster.new("goblin", 1.0, "normal")
		if not goblin.sets_traps:
			_complain("Goblin stellt keine Fallen")
		goblin.x = goblin_spot.x
		goblin.y = goblin_spot.y
		goblin.snap()
		_game.traps.clear()
		for _try in 200:
			_game._monster_sets_trap(goblin)
		if _game.traps.is_empty():
			_complain("Goblin legt nie etwas ab")
		_game.traps.clear()

