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
	var weapon_rarity := "common"      ## multiplies the base bonus
	var armour_rarity := "common"
	var weapon_extra := 0              ## what the smith has hammered on
	var weapon_element := ""           ## "", or a key of Data.ELEMENTS
	var armour_extra := 0
	var level := 1
	var xp := 0
	var xp_to_next := 15
	var potions := 0                ## kept in step with the sum of potion_counts
	var potion_counts := {}         ## id -> how many are carried
	var selected_potion := Data.DEFAULT_POTION
	var buffs := {}                 ## id -> turns left
	var shield := 0                 ## soaks damage before hit points do
	var bleed_turns := 0
	var scrolls := {}               ## id -> how many are carried
	var gold := 0
	var kills := 0
	var facing := 1
	var poison_turns := 0
	var bonus_crit := 0.0
	var damage_reduction := 0.0
	var gold_mult := 1.0
	var regen_interval := 0        ## 0 means no regeneration at all
	var regen_counter := 0
	var pending_perks := 0         ## levels gained but not yet spent

	var hero_class := "warrior"

	## The class shapes the opening hand only: it multiplies the base
	## pool once, here, so a level-up later adds to the adjusted value
	## rather than rescaling it.
	func _init(class_id := Data.DEFAULT_CLASS, difficulty_id := Data.DEFAULT_DIFFICULTY) -> void:
		var info := Data.class_by_id(class_id)
		var level_of_play := Data.difficulty_by_id(difficulty_id)
		hero_class = info["id"]
		max_hp = maxi(1, int(round(20 * float(info["hp_mult"])
			* float(level_of_play["player_hp"]))))
		hp = max_hp
		base_power += int(info["power"])
		base_defense += int(info["defense"])
		weapon = int(info["weapon"])
		armour = int(info["armour"])
		# The opening hand, spelled out per class the way constants.py
		# spells it: the rogue starts with a way out, the mage with
		# something to throw. A class that differs only in numbers is
		# three of the same character.
		potion_counts = {}
		for id in info["potions"]:
			add_potion(id, int(info["potions"][id]))
		if potion_counts.has(Data.DEFAULT_POTION):
			selected_potion = Data.DEFAULT_POTION
		else:
			selected_potion = next_potion()
		for id in info.get("scrolls", {}):
			scrolls[id] = int(info["scrolls"][id])
		weapon_element = str(info.get("element", ""))

	## What a buff adds up to across everything currently running. Two
	## buffs that both raise power stack rather than one winning.
	func buff_total(key: String) -> float:
		var total := 0.0
		for id in buffs:
			total += float(Data.BUFFS[id].get(key, 0))
		return total


	func has_buff(key: String) -> bool:
		for id in buffs:
			if Data.BUFFS[id].get(key, false):
				return true
		return false


	## The weapon's own contribution: its type's bonus, multiplied by
	## the rarity it rolled, plus whatever the smith has added since.
	func weapon_bonus() -> int:
		var base: float = float(Data.WEAPONS[weapon]["bonus"])
		var mult: float = float(Data.rarity_by_id(weapon_rarity)["mult"])
		return int(round(base * mult)) + weapon_extra


	func armour_bonus() -> int:
		var base: float = float(Data.ARMOURS[armour]["bonus"])
		var mult: float = float(Data.rarity_by_id(armour_rarity)["mult"])
		return int(round(base * mult)) + armour_extra


	## The full name of a piece, the way it reads in the log and the
	## shop: "Seltene Streitaxt +2".
	func weapon_name() -> String:
		var named := _named(Data.WEAPONS[weapon]["name"], weapon_rarity, weapon_extra)
		if weapon_element == "":
			return named
		return "%s [%s]" % [named, Data.ELEMENTS[weapon_element]["name"]]


	func armour_name() -> String:
		return _named(Data.ARMOURS[armour]["name"], armour_rarity, armour_extra)


	## The name only - no bonus. The number is printed next to it
	## everywhere it matters, and a name carrying "+2" beside a total of
	## "+15" read as two different numbers for the same thing.
	func _named(base: String, rarity_id: String, _extra: int) -> String:
		# The rarity goes after the noun, in brackets. German adjectives
		# agree with gender - "Seltene Kettenhemd" is simply wrong, and
		# carrying a gender for every weapon name to fix it would be a lot
		# of table for one word.
		var prefix: String = Data.rarity_by_id(rarity_id)["name"]
		return base if prefix == "" else "%s (%s)" % [base, prefix]


	func power() -> int:
		return base_power + weapon_bonus() + int(buff_total("power"))

	## Rises with level and caps where the Python build caps it, so a
	## late hero crits often but never always.
	func crit_chance() -> float:
		# The natural cap stays where it was; a Precision potion adds on
		# top of it rather than being swallowed by it, which is the whole
		# reason to drink one at high level.
		var natural := minf(0.5, 0.05 + level * 0.02 + bonus_crit)
		return minf(0.95, natural + buff_total("crit"))


	func defense() -> int:
		return base_defense + armour_bonus() + int(buff_total("defense"))

	## Returns how many levels were gained, so the caller can announce
	## them - the Python build does the same and the count is used to
	## hand out one perk per level rather than one per gain.
	## Adds or removes potions of one kind and keeps the total honest.
	## Two counters that can disagree is how an inventory ends up
	## showing three flasks that cannot be drunk.
	func add_potion(id: String, count := 1) -> void:
		var now: int = int(potion_counts.get(id, 0)) + count
		if now <= 0:
			potion_counts.erase(id)
		else:
			potion_counts[id] = now
		potions = 0
		for key in potion_counts:
			potions += int(potion_counts[key])
		if not potion_counts.has(selected_potion):
			selected_potion = next_potion()


	## The next kind carried after the selected one, wrapping around.
	func next_potion() -> String:
		var ids: Array = potion_counts.keys()
		ids.sort()
		if ids.is_empty():
			return Data.DEFAULT_POTION
		var at: int = ids.find(selected_potion)
		return ids[(at + 1) % ids.size()]


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
			pending_perks += 1
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
	var is_boss := false
	var is_mimic := false
	var burn_turns := 0             ## takes damage at the end of its turn
	var weaken_turns := 0           ## defends worse while this lasts
	var venom_turns := 0            ## loses health each of its turns
	var bleed_turns := 0            ## the same, from a critical hit
	var slow_turns := 0             ## moves every other turn
	var stun_turns := 0             ## does not act at all
	var regen := 0                  ## heals this much at the end of its turn
	var is_elite := false
	var phase_said := ""            ## the boss phase already announced

	func _init(kind_id: String, tier_mult: float, difficulty_id := Data.DEFAULT_DIFFICULTY) -> void:
		kind = kind_id
		var info: Dictionary = Data.MONSTERS[kind_id]
		var level_of_play := Data.difficulty_by_id(difficulty_id)
		# Baked into the pool at creation, like the tier multiplier: every
		# later bonus then stacks on the adjusted value instead of
		# silently rescaling it.
		max_hp = maxi(1, int(round(info["hp"] * tier_mult * float(level_of_play["enemy_hp"]))))
		hp = max_hp
		power = maxi(1, int(round(info["power"] * tier_mult
			* float(level_of_play["enemy_damage"]))))
		defense = int(round(info.get("defense", 0) * tier_mult))
		xp_reward = maxi(1, int(round(info["xp"] * tier_mult)))
		display_name = info["name"]
		sprite = info.get("sprite", "goblin")
		speed = info.get("speed", 1)
		poisons = info.get("poisons", false)
		flees_below = info.get("flees_below", 0.0)

	## Turns this monster into an elite: the same creature with a
	## prefix and better numbers, worth two and a half times the
	## experience. Applied after the tier multiplier, so it multiplies
	## what the floor already made of it.
	func make_elite(modifier: Dictionary) -> void:
		is_elite = true
		max_hp = maxi(1, int(round(max_hp * float(modifier["hp"]))))
		hp = max_hp
		power = maxi(1, int(round(power * float(modifier["power"]))))
		defense = int(round(defense * float(modifier["defense"])))
		speed += int(modifier.get("speed", 0))
		regen = int(modifier.get("regen", 0))
		xp_reward = maxi(1, int(round(xp_reward * Data.ELITE_XP_MULT)))
		display_name = "%s %s" % [modifier["name"], display_name]


	## What this monster actually defends with right now. Frost eats
	## into it for a few turns.
	func defense_now() -> int:
		if weaken_turns <= 0:
			return defense
		return int(round(defense * Data.WEAKEN_DEFENSE_MULT))


	func is_fleeing() -> bool:
		return flees_below > 0.0 and float(hp) / float(max_hp) <= flees_below
