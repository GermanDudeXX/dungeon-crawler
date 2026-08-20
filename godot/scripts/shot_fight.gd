## A picture with a fight in it: the boss bar, a hurt monster and the
## shadows are the three things that cannot be checked on an empty floor.
extends SceneTree

var _game: Node
var _left := 260
var _set := false


func _initialize() -> void:
	_game = load("res://scenes/main.tscn").instantiate()
	root.add_child(_game)


func _process(_delta: float) -> bool:
	if _game.choosing:
		_game.choose_class("warrior")
		return false
	if not _set:
		_set = true
		_game.depth = 5
		_game.new_level()
		for other in _game.monsters.duplicate():
			_game.monsters.erase(other)
		var here := Vector2i(_game.player.x, _game.player.y)
		var spots: Array = []
		for offset in [Vector2i(2, 0), Vector2i(-2, 0), Vector2i(0, 2), Vector2i(0, -2),
				Vector2i(3, 0), Vector2i(-3, 0), Vector2i(1, 2), Vector2i(-1, -2)]:
			var at: Vector2i = here + offset
			if Dungeon.is_walkable(_game.grid, at.x, at.y) and not _game.blocks(at):
				spots.append(at)
		if spots.size() >= 2:
			var boss = Entities.Monster.new("berserk_orc", 14.0, "normal")
			boss.is_boss = true
			boss.display_name = "Oger-König"
			boss.max_hp = 220
			boss.hp = 143
			boss.awake = true
			boss.x = spots[0].x
			boss.y = spots[0].y
			boss.snap()
			_game.monsters.append(boss)
			var beast = Entities.Monster.new("orc", 9.0, "normal")
			beast.hp = maxi(1, beast.max_hp / 3)
			beast.awake = true
			beast.x = spots[1].x
			beast.y = spots[1].y
			beast.snap()
			_game.monsters.append(beast)
		_game.player.hp = int(_game.player.max_hp * 0.4)
		_game.player.shield = 5
		_game.player.buffs["haste"] = 9
		_game.player.buffs["strength"] = 21
		_game.player.poison_turns = 4
		_game.player.bleed_turns = 2
		_game.recompute_fov()
		_game.paint()
		return false
	_left -= 1
	if _left > 0:
		return false
	var image := root.get_texture().get_image()
	image.save_png("fight.png")
	print("Bild: fight.png")
	quit(0)
	return true
