## The game's numbers, carried over from constants.py unchanged.
##
## Kept as plain data in one place, the way the Python build keeps them,
## so balance is read and changed here rather than hunted through the
## logic. Anything that differs from the original is a bug in this port,
## not a decision.
class_name Data
extends RefCounted

const FOV_RADIUS := 8
const LEVELS_PER_TIER := 10
## Monster stats scale as TIER_GROWTH ** tier_index - derived from the
## index, not from a per-theme constant, so it stays monotone when the
## themes start over rather than making floor 51 easier than floor 50.
const TIER_GROWTH := 1.33

const MONSTERS := {
	"rat": {
		"hp": 4, "power": 2, "defense": 0, "xp": 4, "name": "Ratte",
		"flees_below": 0.3, "sprite": "rat",
	},
	"goblin": {
		"hp": 8, "power": 3, "defense": 1, "xp": 8, "name": "Goblin",
		"sprite": "goblin",
	},
	"orc": {
		"hp": 14, "power": 5, "defense": 2, "xp": 14, "name": "Ork",
		"sprite": "orc",
	},
	"skeleton": {
		"hp": 9, "power": 4, "defense": 1, "xp": 10, "name": "Skelett",
		"sprite": "skeleton",
	},
	"slime": {
		"hp": 6, "power": 2, "defense": 0, "xp": 6, "name": "Schleim",
		"flees_below": 0.25, "sprite": "slime",
	},
	"bat": {
		"hp": 5, "power": 2, "defense": 0, "xp": 6, "name": "Fledermaus",
		"speed": 2, "sprite": "bat",
	},
	"spider": {
		"hp": 7, "power": 3, "defense": 0, "xp": 9, "name": "Spinne",
		"poisons": true, "sprite": "spider",
	},
}

## Which kinds may appear at which depth, and how likely - the deeper
## floors keep the early monsters around, they just stop being the whole
## population.
const SPAWN_WEIGHTS := {
	"rat": [1, 3.0], "goblin": [1, 2.0], "orc": [2, 2.0],
	"skeleton": [3, 1.0], "slime": [2, 1.5], "bat": [1, 1.2],
	"spider": [3, 1.0],
}

const WEAPONS := [
	{"name": "Fäuste", "bonus": 0, "cost": 0},
	{"name": "Dolch", "bonus": 2, "cost": 12},
	{"name": "Kurzschwert", "bonus": 4, "cost": 30},
	{"name": "Streitaxt", "bonus": 6, "cost": 60},
	{"name": "Kriegshammer", "bonus": 9, "cost": 110},
	{"name": "Klinge der Tiefe", "bonus": 13, "cost": 200},
]

const ARMOURS := [
	{"name": "Keine", "bonus": 0, "cost": 0},
	{"name": "Lederrüstung", "bonus": 1, "cost": 15},
	{"name": "Kettenhemd", "bonus": 3, "cost": 35},
	{"name": "Plattenpanzer", "bonus": 5, "cost": 70},
	{"name": "Drachenschuppe", "bonus": 8, "cost": 140},
]

const POTION_HEAL := 12
const TIERS := [
	{"id": "crypt", "name": "Krypta", "tint": Color(0.59, 0.60, 0.70)},
	{"id": "caverns", "name": "Höhlen", "tint": Color(0.70, 0.58, 0.43)},
	{"id": "iron", "name": "Eisenverlies", "tint": Color(0.53, 0.60, 0.72)},
	{"id": "flame", "name": "Flammenreich", "tint": Color(0.78, 0.50, 0.44)},
	{"id": "frost", "name": "Frostgruft", "tint": Color(0.60, 0.74, 0.80)},
]


static func tier_for(level: int) -> Dictionary:
	var index := (level - 1) / LEVELS_PER_TIER
	var tier: Dictionary = TIERS[index % TIERS.size()].duplicate()
	tier["mult"] = pow(TIER_GROWTH, index)
	return tier


static func monster_count(level: int) -> int:
	return mini(2 + level, 12)


static func pick_kind(level: int, rng: RandomNumberGenerator) -> String:
	var pool: Array[String] = []
	var weights: Array[float] = []
	var total := 0.0
	for kind in SPAWN_WEIGHTS:
		var entry: Array = SPAWN_WEIGHTS[kind]
		# Below its depth a kind is not gone, only rare - the same shape
		# the Python build uses, so early floors are not all rats.
		var weight: float = entry[1] if level >= entry[0] else entry[1] * 0.05
		pool.append(kind)
		weights.append(weight)
		total += weight
	var roll := rng.randf() * total
	for i in pool.size():
		roll -= weights[i]
		if roll <= 0.0:
			return pool[i]
	return pool[-1]
