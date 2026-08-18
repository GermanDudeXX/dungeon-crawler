## Takes a picture of the running game, so a screen can be looked at
## instead of guessed at.
##
##     godot --script scripts/shot.gd -- 40 shot.png [warrior]
##
## Not headless: there is nothing to photograph without a renderer.
extends SceneTree

var _game: Node
var _left := 40
var _out := "shot.png"
var _pick := ""


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0 and args[0].is_valid_int():
		_left = args[0].to_int()
	if args.size() > 1:
		_out = args[1]
	if args.size() > 2:
		_pick = args[2]
	_game = load("res://scenes/main.tscn").instantiate()
	root.add_child(_game)


func _process(_delta: float) -> bool:
	if _pick != "" and _game.choosing:
		_game.choose_class(_pick)
	_left -= 1
	if _left > 0:
		return false
	var image := root.get_texture().get_image()
	image.save_png(_out)
	print("Bild: %s (%dx%d)" % [_out, image.get_width(), image.get_height()])
	quit(0)
	return true
