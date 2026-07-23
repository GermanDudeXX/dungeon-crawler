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
        self.armor_bonus = 0
        self.armor_name = "None"
        self.level = 1
        self.xp = 0
        self.xp_to_next = 15
        self.potions = 0
        self.kills = 0

    @property
    def power(self):
        return self.base_power + self.weapon_bonus

    @property
    def defense(self):
        return self.base_defense + self.armor_bonus

    def is_alive(self):
        return self.hp > 0

    def gain_xp(self, amount):
        self.xp += amount
        leveled_up = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = int(self.xp_to_next * 1.5)
            self.max_hp += 5
            self.base_power += 1
            if self.level % 2 == 0:
                self.base_defense += 1
            self.hp = self.max_hp
            leveled_up = True
        return leveled_up


class Monster(Entity):
    def __init__(self, x, y, kind, boss=False):
        stats = C.MONSTER_TYPES[kind]
        char = stats["char"].upper() if boss else stats["char"]
        color = C.COLOR_BOSS if boss else stats["color"]
        name = f"{stats['name']} chieftain" if boss else stats["name"]
        super().__init__(x, y, char, color, name)
        self.kind = kind
        multiplier = 3 if boss else 1
        self.max_hp = stats["hp"] * multiplier
        self.hp = self.max_hp
        self.power = stats["power"] + (stats["power"] // 2 if boss else 0)
        self.defense = stats["defense"] + (2 if boss else 0)
        self.xp_reward = stats["xp"] * (4 if boss else 1)
        self.is_boss = boss
        self.awake = False

    def is_alive(self):
        return self.hp > 0


class Item(Entity):
    def __init__(self, x, y, kind, name, char, color, bonus=0):
        super().__init__(x, y, char, color, name, blocks_movement=False)
        self.kind = kind
        self.bonus = bonus
