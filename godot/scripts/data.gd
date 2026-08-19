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

# Each kind has a habit of its own, not just different numbers: rats
# and bats come in groups, goblins leave traps behind, skeletons shoot
# and back away, slimes split when they die, and everything has an
# element it fears or shrugs off. Straight from constants.py
# MONSTER_TYPES.
const MONSTERS := {
	"rat": {
		"hp": 4, "power": 2, "defense": 0, "xp": 4, "name": "Ratte",
		"flees_below": 0.3, "sprite": "rat", "swarms": [2, 5],
	},
	"goblin": {
		"hp": 8, "power": 3, "defense": 1, "xp": 8, "name": "Goblin",
		"sprite": "goblin", "sets_traps": true,
	},
	"orc": {
		"hp": 14, "power": 5, "defense": 2, "xp": 14, "name": "Ork",
		"sprite": "orc", "weak": ["frost"],
	},
	"skeleton": {
		"hp": 9, "power": 4, "defense": 1, "xp": 10, "name": "Skelett",
		"sprite": "skeleton", "ranged": true, "kites": true,
		"resist": ["poison"], "weak": ["fire"],
	},
	"slime": {
		"hp": 6, "power": 2, "defense": 0, "xp": 6, "name": "Schleim",
		"flees_below": 0.25, "sprite": "slime", "splits": true, "weak": ["fire"],
	},
	"bat": {
		"hp": 5, "power": 2, "defense": 0, "xp": 6, "name": "Fledermaus",
		"speed": 2, "sprite": "bat", "swarms": [2, 4], "weak": ["lightning"],
	},
	"spider": {
		"hp": 7, "power": 3, "defense": 0, "xp": 9, "name": "Spinne",
		"poisons": true, "sprite": "spider", "resist": ["poison"],
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
	{"id": "crypt", "name": "Krypta", "tint": Color(0.59, 0.60, 0.70), "music": "crypt.mp3"},
	{"id": "caverns", "name": "Höhlen", "tint": Color(0.70, 0.58, 0.43), "music": "caverns.mp3"},
	{"id": "iron", "name": "Eisenverlies", "tint": Color(0.53, 0.60, 0.72), "music": "vault.mp3"},
	{"id": "flame", "name": "Flammenreich", "tint": Color(0.78, 0.50, 0.44), "music": "caverns.mp3"},
	{"id": "frost", "name": "Frostgruft", "tint": Color(0.60, 0.74, 0.80), "music": "vault.mp3"},
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

## Floor hazards. Same shapes as the Python build: something that hurts,
## something that poisons, something that drops you a floor.
const TRAPS := {
	"spikes": {"name": "Stachelfalle", "damage": 6},
	"poison": {"name": "Giftgas", "damage": 3, "poison": 4},
	"collapse": {"name": "Einsturz", "damage": 4, "one_shot": true},
}

## A boss holds the key to the stairs, so a floor is a place you finish
## rather than a place you cross. Deep floors only - the first few are
## for learning that walking into things is how you fight.
const BOSS_FROM_LEVEL := 4
const BOSS_EVERY := 3
const BOSS_HP_MULT := 3.2
const BOSS_POWER_MULT := 1.6
const MIMIC_MULT := 1.8
const BURN_DAMAGE := 3
const RANGED_RANGE := 5             ## how far a skeleton can shoot
const RANGED_DAMAGE_MULT := 0.7     ## an arrow hurts less than an axe
const SPLIT_CHILD_MULT := 0.5       ## what is left of a slime it split from
const WEAK_MULT := 2.0              ## elemental damage against a weakness
const RESIST_MULT := 0.5
const TRAP_CHANCE := 0.12           ## per goblin turn
const POISON_PER_TURN := 2

## What a shopkeeper sells, and what a smith charges. Prices rise with
## the tier so gold stays worth picking up on floor 20.
const UPGRADE_COST := 45
const POTION_COST := 18


static func has_boss(level: int) -> bool:
	# 25 is not a multiple of three, so the floor the whole descent
	# builds towards would otherwise have had no boss on it at all.
	if level == SUPERBOSS_LEVEL:
		return true
	return level >= BOSS_FROM_LEVEL and level % BOSS_EVERY == 0

# --- Heldenklassen --------------------------------------------------------
# Picked once per run, the same three as constants.py CLASSES. Each is a
# different opening hand rather than a different set of rules: same
# controls, same systems, different numbers and starting kit. The
# multipliers apply to the base pool at creation, exactly as they do in
# the Python build, so every later level-up stacks on the adjusted value
# instead of quietly rescaling it.
const CLASSES := [
	{
		"id": "warrior", "name": "Krieger", "sprite": "knight_m_idle_anim_f0",
		"color": Color8(214, 160, 84),
		"hp_mult": 1.4, "power": 1, "defense": 2,
		"potions": {"healing": 2}, "scrolls": {}, "weapon": 0, "armour": 0,
		"blurb": "Zäh und gepanzert. Verzeiht Fehler.",
	},
	{
		"id": "rogue", "name": "Schurke", "sprite": "elf_m_idle_anim_f0",
		"color": Color8(120, 214, 140),
		"hp_mult": 0.85, "power": 2, "defense": 0,
		"potions": {"healing": 1, "haste": 1}, "scrolls": {"teleport": 1},
		"weapon": 1, "armour": 0,
		"blurb": "Zerbrechlich, schnell, trifft hart.",
	},
	{
		"id": "mage", "name": "Magier", "sprite": "wizzard_m_idle_anim_f0",
		"color": Color8(150, 170, 255),
		"hp_mult": 0.8, "power": 0, "defense": 0,
		"potions": {"healing": 1, "shield": 1},
		"scrolls": {"fireball": 2, "reveal": 1},
		"weapon": 0, "armour": 0, "element": "fire",
		"blurb": "Schwach im Nahkampf, aber Rollen und Elemente gehorchen dir.",
	},
]
const DEFAULT_CLASS := "warrior"


## The class with this id, or the warrior when the id means nothing.
static func class_by_id(id: String) -> Dictionary:
	for entry in CLASSES:
		if entry["id"] == id:
			return entry
	return CLASSES[0]


# --- Stufenaufstieg -------------------------------------------------------
# One perk per level, picked from three of these. The same list as
# constants.py PERKS, minus the elemental one - this build has no
# elements for it to raise, and a perk that does nothing is worse than
# one fewer choice.
const PERKS := [
	{"id": "power", "name": "Rohe Kraft", "desc": "+2 Angriff", "power": 2},
	{"id": "defense", "name": "Eisenhaut", "desc": "+2 Verteidigung", "defense": 2},
	{"id": "vitality", "name": "Lebenskraft", "desc": "+10 max. Leben", "hp": 10},
	{"id": "precision", "name": "Präzision", "desc": "+5% kritische Treffer", "crit": 0.05},
	{"id": "toughness", "name": "Zähigkeit", "desc": "-10% erlittener Schaden",
		"reduction": 0.10},
	{"id": "regeneration", "name": "Regeneration", "desc": "1 Leben alle 5 Züge",
		"regen": 5},
	{"id": "greed", "name": "Gier", "desc": "+25% Gold", "gold": 0.25},
]
const PERK_CHOICES := 3
const CRIT_MULT := 2


## Three different perks, or fewer if the list ever gets shorter than
## three. Drawn without replacement: offering the same perk twice is a
## choice that is not one.
static func perk_choices(rng: RandomNumberGenerator) -> Array:
	var pool := PERKS.duplicate()
	var out: Array = []
	for _i in mini(PERK_CHOICES, pool.size()):
		out.append(pool.pop_at(rng.randi_range(0, pool.size() - 1)))
	return out


# Buffs and their numbers, straight from constants.py BUFFS. A buff is a
# name, a set of modifiers and a turn count; nothing here knows how it
# was applied, so a potion, a shrine or a scroll can all hand out the
# same one.
const BUFFS := {
	"strength": {"name": "Stärke", "power": 4},
	"stone_skin": {"name": "Steinhaut", "defense": 5},
	"precision": {"name": "Präzision", "crit": 0.3},
	"haste": {"name": "Eile", "haste": true},
	"invisible": {"name": "Unsichtbar", "invisible": true},
	"thorns": {"name": "Dornen", "thorns": 4},
	"lifesteal": {"name": "Lebensraub", "lifesteal": 0.4},
	"regen": {"name": "Regeneration", "regen": 3},
	"luck": {"name": "Glück", "luck": true},
	"berserk": {"name": "Berserk", "power": 7, "defense": -4},
	"fire_aura": {"name": "Feueraura", "burn_attackers": 3},
	"clumsy": {"name": "Ungeschick", "power": -3},
	"frailty": {"name": "Gebrechlich", "defense": -3},
}


# Every potion in the game, with the prices, weights and depth gates from
# constants.py POTION_TYPES. "flask" names the sprite, so the colour on
# the floor matches the one in the inventory; "cursed" ones are only ever
# found, never sold.
const POTIONS := [
	{"id": "healing", "name": "Heiltrank", "flask": "flask_red", "price": 12, "weight": 10,
		"min_level": 1, "effect": {"heal": 15}},
	{"id": "greater_healing", "name": "Großer Heiltrank", "flask": "flask_big_red", "price": 30, "weight": 5,
		"min_level": 4, "effect": {"heal": 45}},
	{"id": "full_healing", "name": "Elixier des Lebens", "flask": "flask_big_red", "price": 65, "weight": 2,
		"min_level": 8, "effect": {"heal_pct": 1.0}},
	{"id": "regeneration", "name": "Trank der Regeneration", "flask": "flask_green", "price": 28, "weight": 4,
		"min_level": 3, "effect": {"buff": "regen", "turns": 15}},
	{"id": "vitality", "name": "Trank der Lebenskraft", "flask": "flask_big_green", "price": 55, "weight": 2,
		"min_level": 5, "effect": {"max_hp": 6}},
	{"id": "might", "name": "Trank der Macht", "flask": "flask_big_yellow", "price": 60, "weight": 2,
		"min_level": 6, "effect": {"base_power": 1}},
	{"id": "iron_hide", "name": "Trank der Eisenhaut", "flask": "flask_big_blue", "price": 60, "weight": 2,
		"min_level": 6, "effect": {"base_defense": 1}},
	{"id": "insight", "name": "Trank der Einsicht", "flask": "flask_big_blue", "price": 45, "weight": 3,
		"min_level": 4, "effect": {"xp_levels": 0.5}},
	{"id": "strength", "name": "Trank der Stärke", "flask": "flask_yellow", "price": 24, "weight": 6,
		"min_level": 2, "effect": {"buff": "strength", "turns": 14}},
	{"id": "stone_skin", "name": "Trank der Steinhaut", "flask": "flask_blue", "price": 24, "weight": 6,
		"min_level": 2, "effect": {"buff": "stone_skin", "turns": 14}},
	{"id": "precision", "name": "Trank der Präzision", "flask": "flask_yellow", "price": 26, "weight": 4,
		"min_level": 3, "effect": {"buff": "precision", "turns": 16}},
	{"id": "haste", "name": "Trank der Eile", "flask": "flask_blue", "price": 32, "weight": 4,
		"min_level": 4, "effect": {"buff": "haste", "turns": 10}},
	{"id": "berserk", "name": "Berserkergebräu", "flask": "flask_big_red", "price": 30, "weight": 3,
		"min_level": 5, "effect": {"buff": "berserk", "turns": 12}},
	{"id": "thorns", "name": "Trank der Dornen", "flask": "flask_green", "price": 26, "weight": 3,
		"min_level": 4, "effect": {"buff": "thorns", "turns": 16}},
	{"id": "lifesteal", "name": "Vampirtrunk", "flask": "flask_big_red", "price": 38, "weight": 3,
		"min_level": 6, "effect": {"buff": "lifesteal", "turns": 14}},
	{"id": "fire_aura", "name": "Trank der Glut", "flask": "flask_yellow", "price": 30, "weight": 3,
		"min_level": 5, "effect": {"buff": "fire_aura", "turns": 14}},
	{"id": "shield", "name": "Trank der Abschirmung", "flask": "flask_big_blue", "price": 30, "weight": 4,
		"min_level": 3, "effect": {"shield": 25}},
	{"id": "invisibility", "name": "Trank der Unsichtbarkeit", "flask": "flask_blue", "price": 34, "weight": 3,
		"min_level": 5, "effect": {"buff": "invisible", "turns": 12}},
	{"id": "luck", "name": "Trank des Glücks", "flask": "flask_big_yellow", "price": 34, "weight": 3,
		"min_level": 4, "effect": {"buff": "luck", "turns": 25}},
	{"id": "clarity", "name": "Trank der Klarheit", "flask": "flask_blue", "price": 20, "weight": 4,
		"min_level": 2, "effect": {"reveal": true}},
	{"id": "blink", "name": "Trank des Blinzelns", "flask": "flask_green", "price": 22, "weight": 4,
		"min_level": 3, "effect": {"blink": true}},
	{"id": "midas", "name": "Trank des Midas", "flask": "flask_big_yellow", "price": 0, "weight": 2,
		"min_level": 3, "effect": {"gold": [25, 70]}},
	{"id": "antidote", "name": "Gegengift", "flask": "flask_green", "price": 15, "weight": 5,
		"min_level": 2, "effect": {"cure": ["poison_turns"]}},
	{"id": "coagulant", "name": "Blutstiller", "flask": "flask_red", "price": 15, "weight": 4,
		"min_level": 3, "effect": {"cure": ["bleed_turns"]}},
	{"id": "panacea", "name": "Allheilmittel", "flask": "flask_big_green", "price": 40, "weight": 2,
		"min_level": 6, "effect": {"cure": ["poison_turns", "bleed_turns"], "cure_debuffs": true, "heal": 20}},
	{"id": "firebomb", "name": "Feuerfläschchen", "flask": "flask_big_red", "price": 28, "weight": 4,
		"min_level": 3, "effect": {"burst_damage": 18, "burst_burn": 3}},
	{"id": "frostbomb", "name": "Frostfläschchen", "flask": "flask_big_blue", "price": 28, "weight": 3,
		"min_level": 5, "effect": {"burst_damage": 10, "burst_slow": 4}},
	{"id": "thunderbomb", "name": "Sturmfläschchen", "flask": "flask_big_yellow", "price": 34, "weight": 3,
		"min_level": 7, "effect": {"burst_damage": 14, "burst_stun": 2}},
	{"id": "murky", "name": "Trübe Phiole", "flask": "flask_green", "price": 0, "weight": 2,
		"min_level": 2, "effect": {"self_poison": 6}, "cursed": true},
	{"id": "bitter", "name": "Bittere Phiole", "flask": "flask_yellow", "price": 0, "weight": 2,
		"min_level": 3, "effect": {"buff": "clumsy", "turns": 12}, "cursed": true},
	{"id": "brittle", "name": "Spröde Phiole", "flask": "flask_blue", "price": 0, "weight": 2,
		"min_level": 4, "effect": {"buff": "frailty", "turns": 12}, "cursed": true},
]
const DEFAULT_POTION := "healing"
const BURST_RADIUS := 2


## The potion this floor hands out: weighted among everything already
## unlocked at this depth, exactly as the Python build rolls it.
static func pick_potion(level: int, rng: RandomNumberGenerator, allow_cursed := true) -> String:
	var pool: Array = []
	var total := 0.0
	for potion in POTIONS:
		if potion["min_level"] > level:
			continue
		if potion.get("cursed", false) and not allow_cursed:
			continue
		pool.append(potion)
		total += float(potion["weight"])
	if pool.is_empty():
		return DEFAULT_POTION
	var roll := rng.randf() * total
	for potion in pool:
		roll -= float(potion["weight"])
		if roll <= 0.0:
			return potion["id"]
	return pool[-1]["id"]


static func potion_by_id(id: String) -> Dictionary:
	for potion in POTIONS:
		if potion["id"] == id:
			return potion
	return POTIONS[0]


# --- Schriftrollen --------------------------------------------------------
# Three, the same three as constants.py SCROLL_TYPES. A scroll is aimed
# for you: it finds its own target, which is what makes it usable on a
# phone without a cursor.
const SCROLLS := [
	{"id": "fireball", "name": "Feuerball", "damage": 14, "price": 40,
		"desc": "Trifft den nächsten Gegner und alles neben ihm."},
	{"id": "teleport", "name": "Blitzreise", "price": 30,
		"desc": "Bringt dich an einen zufälligen Ort dieser Ebene."},
	{"id": "reveal", "name": "Enthüllung", "price": 25,
		"desc": "Zeigt die ganze Ebene."},
]


static func scroll_by_id(id: String) -> Dictionary:
	for scroll in SCROLLS:
		if scroll["id"] == id:
			return scroll
	return SCROLLS[0]


# --- Schreine -------------------------------------------------------------
# One per level at most, stepped on rather than opened: risk and reward
# in a single tile. Weights from constants.py SHRINE_EVENTS.
const SHRINE_CHANCE := 0.3
const SHRINES := [
	{"id": "vitality", "name": "Segen der Lebenskraft", "weight": 3.0},
	{"id": "power", "name": "Segen der Macht", "weight": 2.0},
	{"id": "fortune", "name": "Glücksfall", "weight": 3.0},
	{"id": "frailty", "name": "Fluch der Gebrechlichkeit", "weight": 2.0},
	{"id": "ambush", "name": "Rachsüchtige Geister", "weight": 1.5},
]


static func pick_shrine(rng: RandomNumberGenerator) -> String:
	var total := 0.0
	for shrine in SHRINES:
		total += float(shrine["weight"])
	var roll := rng.randf() * total
	for shrine in SHRINES:
		roll -= float(shrine["weight"])
		if roll <= 0.0:
			return shrine["id"]
	return SHRINES[0]["id"]


# --- Elitegegner ----------------------------------------------------------
# One monster in ten is one of these: the same kind, wearing a prefix and
# better numbers. Cheaper than a new monster type and it makes a familiar
# silhouette worth a second look. Values from constants.py
# ELITE_MODIFIERS.
const ELITES := [
	{"name": "Flinker", "hp": 1.0, "power": 1.1, "defense": 1.0, "speed": 1},
	{"name": "Bösartiger", "hp": 1.2, "power": 1.6, "defense": 1.0},
	{"name": "Gepanzerter", "hp": 1.4, "power": 1.0, "defense": 2.2},
	{"name": "Nachwachsender", "hp": 1.6, "power": 1.1, "defense": 1.0, "regen": 1},
]
const ELITE_CHANCE := 0.10
const ELITE_XP_MULT := 2.5

# A mini-boss on every third floor that has no real boss - so the gap
# between boss floors has a landmark in it.
const MINI_BOSS_EVERY := 3
const MINI_BOSS_MULT := 1.6
const MINI_BOSS_XP_MULT := 2.5

# A room worth robbing: several elites at once, in sight, guarding gold.
# A crowd is a different problem from a boss.
const VAULT_CHANCE := 0.22
const VAULT_MIN_LEVEL := 5
const VAULT_GUARDS := [3, 5]
const VAULT_GUARD_MULT := 1.3

# A guarded chest: one keeper standing over it, and the chest stays
# shut until the keeper is dead. Different from the vault - that is a
# crowd on a pile of gold, this is one fight for one prize.
const TREASURE_CHANCE := 0.45
const TREASURE_GUARD_MULT := 1.4
const TREASURE_MIN_LEVEL := 2


static func has_mini_boss(level: int) -> bool:
	return level % MINI_BOSS_EVERY == 0 and not has_boss(level)


# --- Seltenheit -----------------------------------------------------------
# Rolled on every weapon and armour drop, on top of its base type: it
# multiplies the bonus and puts a word in front of the name, so what a
# find is worth reads at a glance instead of needing a comparison
# screen. min_level gates the good tiers behind depth - the first floor
# never hands out a legendary. Values from constants.py RARITY_TIERS.
const RARITIES := [
	{"id": "common", "name": "", "mult": 1.0, "weight": 10.0, "min_level": 1},
	{"id": "uncommon", "name": "fein", "mult": 1.3, "weight": 5.0, "min_level": 1},
	{"id": "rare", "name": "selten", "mult": 1.7, "weight": 2.2, "min_level": 3},
	{"id": "epic", "name": "episch", "mult": 2.1, "weight": 0.9, "min_level": 5},
	{"id": "legendary", "name": "legendär", "mult": 2.6, "weight": 0.3, "min_level": 8},
]


## The rarity a drop on this floor rolls, weighted among those already
## unlocked at this depth.
static func pick_rarity(level: int, rng: RandomNumberGenerator) -> Dictionary:
	var pool: Array = []
	var total := 0.0
	for rarity in RARITIES:
		if int(rarity["min_level"]) > level:
			continue
		pool.append(rarity)
		total += float(rarity["weight"])
	var roll := rng.randf() * total
	for rarity in pool:
		roll -= float(rarity["weight"])
		if roll <= 0.0:
			return rarity
	return RARITIES[0]


static func rarity_by_id(id: String) -> Dictionary:
	for rarity in RARITIES:
		if rarity["id"] == id:
			return rarity
	return RARITIES[0]


# --- der Schmied ----------------------------------------------------------
# Gold has nothing to buy past the first few floors: a shop stocks what
# it stocks. The smith is the sink - he improves what you already carry,
# so the gear you found stays the gear you use. The price climbs with
# the bonus already on the item, so the first upgrade is cheap and the
# tenth is a real decision. Numbers from constants.py.
const SMITH_BASE_PRICE := 25
const SMITH_PRICE_PER_POINT := 18
const SMITH_WEAPON_STEP := 2
const SMITH_ARMOUR_STEP := 1
# Enchanting puts an element on a bare weapon, or rerolls the one it
# has; reforging rerolls the rarity, one tier up where there is room.
# Both are expensive on purpose: they are what late gold is for.
const SMITH_ENCHANT_PRICE := 90
const SMITH_REFORGE_PRICE := 140


static func smith_price(bonus: int) -> int:
	return SMITH_BASE_PRICE + SMITH_PRICE_PER_POINT * maxi(0, bonus)


# --- Schwierigkeit --------------------------------------------------------
# Picked before the hero, the same four as constants.py DIFFICULTIES.
# The multipliers are applied where the numbers are made - to the pool a
# monster is built from and to the hero's starting health - not to every
# calculation afterwards, so nothing has to remember to re-apply them.
const DIFFICULTIES := [
	{"id": "easy", "name": "Leicht", "desc": "Für den Weg dahin.",
		"player_hp": 2.0, "player_damage": 1.0, "enemy_hp": 0.75, "enemy_damage": 0.5,
		"markup": 0.0},
	{"id": "normal", "name": "Normal", "desc": "So ist es gedacht.",
		"player_hp": 1.0, "player_damage": 1.0, "enemy_hp": 1.0, "enemy_damage": 1.0,
		"markup": 0.0},
	{"id": "hard", "name": "Schwer", "desc": "Härter, teurer, tödlicher.",
		"player_hp": 0.75, "player_damage": 1.2, "enemy_hp": 1.25, "enemy_damage": 1.25,
		"markup": 0.20},
	{"id": "hardcore", "name": "Hardcore", "desc": "Jeder Fehler zählt doppelt.",
		"player_hp": 0.5, "player_damage": 0.5, "enemy_hp": 2.0, "enemy_damage": 2.0,
		"markup": 0.50},
]
const DEFAULT_DIFFICULTY := "normal"


static func difficulty_by_id(id: String) -> Dictionary:
	for entry in DIFFICULTIES:
		if entry["id"] == id:
			return entry
	return DIFFICULTIES[1]


# --- Elementarwaffen ------------------------------------------------------
# A weapon can carry an element, rolled when it drops. Each has a chance
# to fire per hit: extra damage now, plus a status the monster carries
# for a few turns. Values from constants.py ELEMENTS.
const ELEMENTS := {
	"fire": {"name": "Flammen", "status": "burn", "turns": 3, "damage": 3, "chance": 0.35},
	"frost": {"name": "Frost", "status": "weaken", "turns": 3, "damage": 2, "chance": 0.40},
	"lightning": {"name": "Blitz", "status": "stun", "turns": 1, "damage": 2, "chance": 0.30},
	"poison": {"name": "Gift", "status": "poison", "turns": 4, "damage": 2, "chance": 0.40},
}
const ELEMENT_CHANCE := 0.3          ## that a dropped weapon carries one
const ELEMENT_MIN_LEVEL := 2
const WEAKEN_DEFENSE_MULT := 0.6

# Bleed is the crit-only counterpart to poison: roughly double the damage
# over half the duration, so it matters in the fight that started it
# rather than being a slow drain.
const BLEED_DAMAGE := 5
const BLEED_TURNS := 2


## The element a dropped weapon carries, or "" for a plain one.
static func pick_element(level: int, rng: RandomNumberGenerator) -> String:
	if level < ELEMENT_MIN_LEVEL or rng.randf() >= ELEMENT_CHANCE:
		return ""
	var ids: Array = ELEMENTS.keys()
	return ids[rng.randi() % ids.size()]


# --- Bossphasen -----------------------------------------------------------
# A boss hits harder as it goes down. Read from its current health
# rather than latched when it crosses a line, so healing it - an elite
# regenerating, say - puts it back into the calmer phase instead of
# leaving it permanently enraged at full health.
const BOSS_PHASES := [
	{"at": 0.66, "name": "verwundet", "power": 1.15},
	{"at": 0.33, "name": "verzweifelt", "power": 1.35},
]


## The phase a boss at this health is in, or an empty dictionary while
## it is still fresh.
static func boss_phase(hp: int, max_hp: int) -> Dictionary:
	var ratio := float(hp) / float(maxi(1, max_hp))
	var current := {}
	for phase in BOSS_PHASES:
		if ratio <= float(phase["at"]):
			current = phase
	return current


# --- Gefahren -------------------------------------------------------------
# Unlike traps, these are visible from the start: they are meant to be
# walked around, not discovered. Values from constants.py HAZARD_TYPES.
const HAZARDS := {
	"lava": {"name": "Lavariss", "tile": "wall_goo", "damage": 8, "burn": 3, "min_level": 3},
	"collapse": {"name": "Loch", "tile": "hole", "damage": 12, "min_level": 4,
		"one_shot": true},
	"spikes": {"name": "Stachelboden", "tile": "floor_spikes_anim_f2", "damage": 6,
		"bleed": 2, "min_level": 3},
}
const HAZARD_CHANCE_PER_ROOM := 0.25

# Decoration you cannot walk through. A crate or a stone column is a
# solid object and reads as one; a skull on the floor does not, so it
# stays walkable. Placing these needs care - one dropped in a one-tile
# corridor can seal the stairs off entirely.
const BLOCKING_DECOR := ["crate", "column"]

# The run's final challenge. Reachable, but a long way down.
const SUPERBOSS_LEVEL := 25
const SUPERBOSS_MULT := 3.0


static func hazards_for(level: int) -> Array:
	var out: Array = []
	for id in HAZARDS:
		if int(HAZARDS[id]["min_level"]) <= level:
			out.append(id)
	return out

