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
    def __init__(self, x, y, hp_mult=1.0):
        super().__init__(x, y, "@", C.COLOR_PLAYER, "you")
        self.facing = 1
        # The difficulty's HP multiplier is baked into the pool itself
        # rather than applied on read, so every later +max_hp (level-ups,
        # Vitality perk, potions) stacks on top of the adjusted base
        # instead of being silently rescaled too.
        self.max_hp = max(5, int(round(20 * hp_mult)))
        self.hp = self.max_hp
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
        # Potions are counted per type. The old single "potions" int is
        # kept as a read-only view of the healing ones so the HUD, the
        # achievements and old saves all still mean the same thing.
        self.potion_counts = {C.DEFAULT_POTION: 0}
        self.selected_potion = C.DEFAULT_POTION
        # buff id -> turns remaining. One dict rather than a field per
        # effect: there are a dozen of them, they stack freely, and a
        # field each would be a dozen places to decrement and serialise.
        self.buffs = {}
        self.shield = 0
        self.kills = 0
        self.gold = 0
        self.scrolls = {"fireball": 0, "teleport": 0, "reveal": 0}
        self.poison_turns = 0
        self.bleed_turns = 0
        self.potions_drunk_this_run = 0
        self.bonus_crit_chance = 0.0
        self.bonus_damage_reduction = 0.0
        self.bonus_gold_mult = 0.0
        self.bonus_elemental_chance = 0.0
        self.regen_interval = None
        self.regen_counter = 0

    @property
    def potions(self):
        """Total flasks carried, of every kind.

        Still an int so the HUD, the save format and the "Untouchable"
        achievement did not all have to change at once when potions
        stopped being a single undifferentiated stack.
        """
        return sum(self.potion_counts.values())

    def potion_count(self, potion_id):
        return self.potion_counts.get(potion_id, 0)

    def add_potion(self, potion_id, amount=1):
        self.potion_counts[potion_id] = self.potion_counts.get(potion_id, 0) + amount
        # Point the quick-use slot at something you actually have, so the
        # HEAL button is never a no-op right after picking a flask up.
        if self.potion_counts.get(self.selected_potion, 0) <= 0:
            self.selected_potion = potion_id

    def take_potion(self, potion_id):
        if self.potion_counts.get(potion_id, 0) <= 0:
            return False
        self.potion_counts[potion_id] -= 1
        if self.potion_counts[potion_id] <= 0:
            del self.potion_counts[potion_id]
            if self.selected_potion == potion_id:
                self.selected_potion = next(iter(self.potion_counts), C.DEFAULT_POTION)
        return True

    def buff_total(self, key):
        """Sum of one stat across every active buff.

        Buffs stack rather than overriding each other, so drinking
        Strength while Berserk is up gives both - which is the point of
        having a dozen of them.
        """
        return sum(C.BUFFS[b].get(key, 0) for b in self.buffs if b in C.BUFFS)

    def has_buff_flag(self, key):
        return any(C.BUFFS[b].get(key) for b in self.buffs if b in C.BUFFS)

    @property
    def power(self):
        return max(1, self.base_power + self.weapon_bonus + self.buff_total("power"))

    @property
    def defense(self):
        return max(0, self.base_defense + self.armor_bonus + self.buff_total("defense"))

    @property
    def crit_chance(self):
        # The natural cap stays where it was; a Precision potion adds on
        # top of it rather than being swallowed by it, which is the whole
        # reason to drink one at high level.
        natural = min(0.5, 0.05 + self.level * 0.02 + self.bonus_crit_chance)
        return min(0.95, natural + self.buff_total("crit"))

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
    def __init__(self, x, y, kind, boss=False, elite=None, tier_mult=1.0,
                 level=1, diff_hp=1.0, diff_damage=1.0):
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

        # The chosen difficulty scales health and damage but deliberately
        # NOT xp: otherwise Hardcore would also hand out double experience
        # and partly undo its own difficulty.
        if diff_hp != 1.0:
            base_hp = max(1, int(round(base_hp * diff_hp)))
        if diff_damage != 1.0:
            base_power = max(1, int(round(base_power * diff_damage)))

        self.max_hp = base_hp
        self.hp = self.max_hp
        self.power = base_power
        self.defense = base_defense
        self.xp_reward = base_xp
        self.tier_mult = tier_mult
        self.is_boss = boss
        self.awake = False
        # Shown on the nameplate above the monster - the dungeon floor it
        # was spawned on, which is what its stats were scaled by.
        self.level = level

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
        self.bleed_turns = 0
        self.slow_turns = 0
        # Flips every turn while slowed so the monster acts on half of
        # them; see Game._enemy_turn.
        self.slow_skip = False

        # Boss-only signature mechanics (see Game._boss_special_action) -
        # harmless no-ops on regular monsters, which never check them.
        self.enraged = False
        self.summon_cooldown = 3
        self.web_cooldown = 2

        # Roles assigned after construction by the level generator (see
        # Game._populate_level). Declared here so nothing has to reach for
        # them with getattr and so they always serialise.
        self.guards_chest = False
        self.is_mini_boss = False
        self.is_superboss = False

    def is_alive(self):
        return self.hp > 0


class Merchant(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, "M", C.COLOR_MERCHANT, "merchant")


class Item(Entity):
    def __init__(self, x, y, kind, name, char, color, bonus=0, scroll_type=None,
                 rarity_id=None, element_id=None, potion_id=None):
        super().__init__(x, y, char, color, name, blocks_movement=False)
        self.kind = kind
        self.bonus = bonus
        self.scroll_type = scroll_type
        self.rarity_id = rarity_id
        self.element_id = element_id
        self.potion_id = potion_id
