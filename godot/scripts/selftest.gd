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
var _game: Node
var _problems := {}
var _notes: Array[String] = []


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.is_valid_int():
			_turns = arg.to_int()
	_game = load("res://scenes/main.tscn").instantiate()
	root.add_child(_game)


func _process(_delta: float) -> bool:
	var deepest := 1
	var descents := 0
	var deaths := 0
	var kills := 0
	var on_this_floor := 0
	var depth_at: int = _game.depth
	var started := Time.get_ticks_msec()

	for turn in _turns:
		if _game.dead:
			deaths += 1
			_game.new_run()
			depth_at = _game.depth
			on_this_floor = 0
			continue

		if _game.player.hp < _game.player.max_hp * 0.4 and _game.player.potions > 0:
			_game.drink()

		var step: Variant = _route(_game.stairs)
		if step == null:
			_complain("Treppe unerreichbar", "Ebene %d, Treppe %s, Spieler (%d, %d)"
				% [_game.depth, str(_game.stairs), _game.player.x, _game.player.y])
			_next_floor()
			depth_at = _game.depth
			on_this_floor = 0
			continue

		var before: int = _game.player.kills
		_game.try_move(step)
		kills += _game.player.kills - before
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

	var failed := false
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
