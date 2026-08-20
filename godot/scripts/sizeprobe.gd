extends SceneTree
func _init() -> void:
	var game = load("res://scripts/game.gd").new()
	get_root().add_child(game)
	await process_frame
	game.hero_class = "warrior"
	game.new_run()
	for deep in [1, 5, 12]:
		game.floors.clear()
		game.depth = deep
		game.new_level()
		game.recompute_fov()
		var plan: Dictionary = game.floor_for_network()
		var raw: PackedByteArray = var_to_bytes(plan)
		var packed: PackedByteArray = raw.compress(FileAccess.COMPRESSION_ZSTD)
		var beat: PackedByteArray = var_to_bytes(game.pulse_for_network())
		print("Ebene %d: Ebenenpaket %d Bytes (gepackt %d), Puls %d Bytes" % [
			deep, raw.size(), packed.size(), beat.size()])
	quit()
