## Dungeon generation, ported from dungeon.py.
##
## Kept deliberately line-for-line with the Python original: same room
## count, same sizes, same corridor coin-flip, same order of random
## calls. Given the same seed it lays out the same dungeon, which is
## what makes it possible to check this port against the game that
## already works instead of eyeballing it.
class_name Dungeon
extends RefCounted

const WALL := 0
const FLOOR := 1


class Room:
	var x1: int
	var y1: int
	var x2: int
	var y2: int

	func _init(x: int, y: int, w: int, h: int) -> void:
		x1 = x
		y1 = y
		x2 = x + w
		y2 = y + h

	func center() -> Vector2i:
		return Vector2i((x1 + x2) / 2, (y1 + y2) / 2)

	func intersects(other: Room, padding: int = 1) -> bool:
		return (x1 - padding < other.x2
			and x2 + padding > other.x1
			and y1 - padding < other.y2
			and y2 + padding > other.y1)


static func generate(width: int, height: int, rng: RandomNumberGenerator,
		max_rooms: int = 15, room_min: int = 4, room_max: int = 9) -> Dictionary:
	var grid := []
	for y in height:
		var row := []
		row.resize(width)
		row.fill(WALL)
		grid.append(row)

	var rooms: Array[Room] = []
	for _i in max_rooms:
		var w := rng.randi_range(room_min, room_max)
		var h := rng.randi_range(room_min, room_max)
		var x := rng.randi_range(1, width - w - 2)
		var y := rng.randi_range(1, height - h - 2)
		var room := Room.new(x, y, w, h)

		var clashes := false
		for other in rooms:
			if room.intersects(other):
				clashes = true
				break
		if clashes:
			continue

		_carve_room(grid, room)

		if not rooms.is_empty():
			var prev := rooms[-1].center()
			var here := room.center()
			if rng.randf() < 0.5:
				_carve_h(grid, prev.x, here.x, prev.y)
				_carve_v(grid, prev.y, here.y, here.x)
			else:
				_carve_v(grid, prev.y, here.y, prev.x)
				_carve_h(grid, prev.x, here.x, here.y)

		rooms.append(room)

	return {"grid": grid, "rooms": rooms}


static func _carve_room(grid: Array, room: Room) -> void:
	for y in range(room.y1, room.y2):
		for x in range(room.x1, room.x2):
			grid[y][x] = FLOOR


static func _carve_h(grid: Array, x1: int, x2: int, y: int) -> void:
	for x in range(mini(x1, x2), maxi(x1, x2) + 1):
		grid[y][x] = FLOOR


static func _carve_v(grid: Array, y1: int, y2: int, x: int) -> void:
	for y in range(mini(y1, y2), maxi(y1, y2) + 1):
		grid[y][x] = FLOOR


static func is_walkable(grid: Array, x: int, y: int) -> bool:
	if y < 0 or y >= grid.size() or x < 0 or x >= grid[0].size():
		return false
	return grid[y][x] == FLOOR
