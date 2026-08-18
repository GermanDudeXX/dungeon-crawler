## The hero and the monsters, with the stats and formulas from
## entities.py. The numbers matter more than the structure here: level-up
## gives the same +5 max HP and +1 power, experience needs the same 15
## rising by half each level, and a monster's stats are multiplied into
## its pool when it is made rather than when it is read - so every later
## bonus stacks on the adjusted value instead of silently rescaling it.
class_name Entities
extends RefCounted


class Actor extends RefCounted:
	var x := 0
	var y := 0
	var hp := 1
	var max_hp := 1
	var render_pos := Vector2.ZERO      ## smooth position, for drawing

	func is_alive() -> bool:
		return hp > 0

	func cell() -> Vector2i:
		return Vector2i(x, y)

	func snap() -> void:
		render_pos = Vector2(x, y)


class Player extends Actor:
	var base_power := 4
	var base_defense := 1
	var weapon := 0                    ## index into Data.WEAPONS
	var armour := 0
	var level := 1
	var xp := 0
	var xp_to_next := 15
	var potions := 0
	var gold := 0
	var kills := 0
	var facing := 1

	func _init() -> void:
		max_hp = 20
		hp = max_hp
		potions = 2

	func power() -> int:
		return base_power + Data.WEAPONS[weapon]["bonus"]

	func defense() -> int:
		return base_defense + Data.ARMOURS[armour]["bonus"]

	## Returns how many levels were gained, so the caller can announce
	## them - the Python build does the same and the count is used to
	## hand out one perk per level rather than one per gain.
	func gain_xp(amount: int) -> int:
		xp += amount
		var gained := 0
		while xp >= xp_to_next:
			xp -= xp_to_next
			level += 1
			xp_to_next = int(xp_to_next * 1.5)
			max_hp += 5
			base_power += 1
			hp = min(max_hp, hp + 5)
			gained += 1
		return gained


class Monster extends Actor:
	var kind := "rat"
	var power := 1
	var defense := 0
	var xp_reward := 1
	var display_name := "Ratte"
	var sprite := "goblin"
	var awake := false
	var speed := 1
	var poisons := false
	var flees_below := 0.0

	func _init(kind_id: String, tier_mult: float) -> void:
		kind = kind_id
		var info: Dictionary = Data.MONSTERS[kind_id]
		max_hp = maxi(1, int(round(info["hp"] * tier_mult)))
		hp = max_hp
		power = maxi(1, int(round(info["power"] * tier_mult)))
		defense = int(round(info.get("defense", 0) * tier_mult))
		xp_reward = maxi(1, int(round(info["xp"] * tier_mult)))
		display_name = info["name"]
		sprite = info.get("sprite", "goblin")
		speed = info.get("speed", 1)
		poisons = info.get("poisons", false)
		flees_below = info.get("flees_below", 0.0)

	func is_fleeing() -> bool:
		return flees_below > 0.0 and float(hp) / float(max_hp) <= flees_below
