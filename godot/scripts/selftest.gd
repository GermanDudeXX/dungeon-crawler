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
	var seen := {"Bosse": 0, "Laeden": 0, "Truhen": 0, "Fallen": 0, "Mimics": 0}
	var played := {}
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

	for turn in _turns:
		if _game.dead:
			deaths += 1
			next_class = (next_class + 1) % Data.CLASSES.size()
			_game.choose_class(Data.CLASSES[next_class]["id"])
			played[_game.player.hero_class] = true
			depth_at = _game.depth
			on_this_floor = 0
			continue

		# A good run can outlive the test, and then only one class ever
		# gets played. Retire the hero on schedule so all three do.
		if turn > 0 and turn % (_turns / Data.CLASSES.size()) == 0:
			next_class = (next_class + 1) % Data.CLASSES.size()
			_game.choose_class(Data.CLASSES[next_class]["id"])
			played[_game.player.hero_class] = true
			depth_at = _game.depth
			on_this_floor = 0
			continue

		if _game.player.hp < _game.player.max_hp * 0.4 and _game.player.potions > 0:
			_game.drink()

		# A shop opens when you walk into its keeper; a player leaves it.
		if _game.shop_open != null:
			seen["Laeden"] += 1
			_game.buy("potion")
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
		# Nobody walks past an unopened chest either.
		if _game.chest != null and not _game.chest["opened"]:
			target = _game.chest["cell"]
			what = "Truhe"
		elif _game.player.gold >= Data.POTION_COST:
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
		_check("Zug %d, Ebene %d" % [turn, _game.depth])

		if _game.depth != depth_at:
			descents += 1
			deepest = maxi(deepest, _game.depth)
			depth_at = _game.depth
			on_this_floor = 0
		else:
			on_this_floor += 1
			if on_this_floor > 600:
				_complain("Ebene nicht abschließbar",
					"Ebene %d, %d Züge" % [_game.depth, on_this_floor])
				_next_floor()
				depth_at = _game.depth
				on_this_floor = 0

	print("  %d Zuege in %d ms: Ebene %d erreicht, %d Abstiege, %d Tode, %d Kills"
		% [_turns, Time.get_ticks_msec() - started, deepest, descents, deaths, kills])

	var parts: Array[String] = []
	for what in seen:
		parts.append("%d %s" % [seen[what], what])
	print("  angefasst: " + ", ".join(parts))
	print("  gespielt: " + ", ".join(played.keys()))

	var failed := false
	if played.size() < Data.CLASSES.size():
		print("  nicht jede Klasse gespielt: %d von %d" % [played.size(), Data.CLASSES.size()])
		failed = true
	for what in seen:
		if seen[what] == 0:
			print("  nie erreicht: %s - ungetestet" % what)
			failed = true
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
			if not Dungeon.is_walkable(_game.grid, step.x, step.y):
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
		"Waffe=%d Ruestung=%d" % [p.weapon, p.armour],
		"Treppe=%s verriegelt=%s" % [str(_game.stairs), str(_game.stairs_locked)],
		"erkundet=%d" % _game.explored.size(),
		"Fallen=%d Laeden=%d Beute=%d" % [
			_game.traps.size(), _game.shops.size(), _game.items.size()],
		"Truhe=%s" % str(_game.chest),
	]
	var alive: Array[String] = []
	for m in _game.monsters:
		if m.is_alive():
			alive.append("%s@%d,%d %d/%d" % [m.kind, m.x, m.y, m.hp, m.max_hp])
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

