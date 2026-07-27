import constants as C


class Entity:
    def __init__(self, x, y, char, color, name, blocks_movement=True):
        self.x = x
        self.y = y
        self.render_x = float(x)
        self.render_y = float(y)
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def snap(self):
        self.render_x = float(self.x)
        self.render_y = float(self.y)

    def update_animation(self, lerp=0.35):
        self.render_x += (self.x - self.render_x) * lerp
        self.render_y += (self.y - self.render_y) * lerp
        if abs(self.x - self.render_x) < 0.02:
            self.render_x = float(self.x)
        if abs(self.y - self.render_y) < 0.02:
            self.render_y = float(self.y)


class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, "@", C.COLOR_PLAYER, "you")
        self.facing = 1
        self.max_hp = 20
        self.hp = 20
        self.base_power = 4
        self.base_defense = 1
        self.weapon_bonus = 0
        self.weapon_name = "Fists"
        self.weapon_rarity_id = None
        self.weapon_element_id = None
        self.armor_bonus = 0
        self.armor_name = "None"
        self.armor_rarity_id = None
        self.level = 1
        self.xp = 0
        self.xp_to_next = 15
        self.potions = 0
        self.kills = 0
        self.gold = 0
        self.scrolls = {"fireball": 0, "teleport": 0, "reveal": 0}
        self.poison_turns = 0
        self.potions_drunk_this_run = 0
        self.bonus_crit_chance = 0.0
        self.bonus_damage_reduction = 0.0
        self.bonus_gold_mult = 0.0
        self.bonus_elemental_chance = 0.0
        self.regen_interval = None
        self.regen_counter = 0

    @property
    def power(self):
        return self.base_power + self.weapon_bonus

    @property
    def defense(self):
        return self.base_defense + self.armor_bonus

    @property
    def crit_chance(self):
        return min(0.5, 0.05 + self.level * 0.02 + self.bonus_crit_chance)

    def is_alive(self):
        return self.hp > 0

    def gain_xp(self, amount):
        self.xp += amount
        levels_gained = 0
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = int(self.xp_to_next * 1.5)
            self.max_hp += 5
            self.base_power += 1
            if self.level % 2 == 0:
                self.base_defense += 1
            self.hp = self.max_hp
            levels_gained += 1
        return levels_gained


class Monster(Entity):
    def __init__(self, x, y, kind, boss=False, elite=None, tier_mult=1.0):
        stats = C.MONSTER_TYPES[kind]
        char = stats["char"].upper() if boss else stats["char"]
        color = C.COLOR_BOSS if boss else stats["color"]
        title = C.BOSS_TITLES.get(kind, "chieftain")
        name = f"{stats['name']} {title}" if boss else stats["name"]

        self.elite_name = elite["name"] if elite else None
        if elite:
            color = tuple((c + m) // 2 for c, m in zip(color, elite["color"]))
            name = f"{elite['name']} {name}"

        super().__init__(x, y, char, color, name)
        self.kind = kind
        self.facing = 1
        multiplier = 3 if boss else 1
        base_hp = stats["hp"] * multiplier
        base_power = stats["power"] + (stats["power"] // 2 if boss else 0)
        base_defense = stats["defense"] + (2 if boss else 0)
        base_xp = stats["xp"] * (4 if boss else 1)

        if elite:
            base_hp = int(base_hp * elite["hp_mult"])
            base_power = max(1, int(base_power * elite["power_mult"]))
            base_defense = int(base_defense * elite["defense_mult"])
            base_xp = int(base_xp * C.ELITE_XP_MULT)

        # Deeper dungeon tiers scale every monster up (see
        # constants.DUNGEON_TIERS) - without this, difficulty past the
        # first few floors came only from spawning slightly more of them.
        if tier_mult != 1.0:
            base_hp = max(1, int(base_hp * tier_mult))
            base_power = max(1, int(base_power * tier_mult))
            base_defense = int(base_defense * tier_mult)
            base_xp = max(1, int(base_xp * tier_mult))

        self.max_hp = base_hp
        self.hp = self.max_hp
        self.power = base_power
        self.defense = base_defense
        self.xp_reward = base_xp
        self.tier_mult = tier_mult
        self.is_boss = boss
        self.awake = False

        self.ranged = stats.get("ranged", False)
        self.speed = stats.get("speed", 1) + (elite["speed_bonus"] if elite and "speed_bonus" in elite else 0)
        self.splits = stats.get("splits", False)
        self.poisons_on_hit = stats.get("poisons", False)
        self.regen = elite["regen"] if elite and "regen" in elite else 0
        self.is_split_child = False

        # Status effects a player's elemental weapon can inflict (see
        # Game._attack / Game._tick_monster_status) - never set by monster
        # attacks themselves, so these stay 0 unless the player is wielding
        # an elemental weapon.
        self.poison_turns = 0
        self.burn_turns = 0
        self.weaken_turns = 0
        self.stun_turns = 0

        # Boss-only signature mechanics (see Game._boss_special_action) -
        # harmless no-ops on regular monsters, which never check them.
        self.enraged = False
        self.summon_cooldown = 3
        self.web_cooldown = 2

    def is_alive(self):
        return self.hp > 0


class Merchant(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, "M", C.COLOR_MERCHANT, "merchant")


class Item(Entity):
    def __init__(self, x, y, kind, name, char, color, bonus=0, scroll_type=None, rarity_id=None, element_id=None):
        super().__init__(x, y, char, color, name, blocks_movement=False)
        self.kind = kind
        self.bonus = bonus
        self.scroll_type = scroll_type
        self.rarity_id = rarity_id
        self.element_id = element_id
