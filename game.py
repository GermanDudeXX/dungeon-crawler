import os
import random
import sys

import pygame

import constants as C
import dungeon
import entities
import fov
import locale_text as loc
import persistence
import sound

ON_ANDROID = "ANDROID_ARGUMENT" in os.environ

MOVE_KEYS = (
    (pygame.K_UP, (0, -1)),
    (pygame.K_w, (0, -1)),
    (pygame.K_DOWN, (0, 1)),
    (pygame.K_s, (0, 1)),
    (pygame.K_LEFT, (-1, 0)),
    (pygame.K_a, (-1, 0)),
    (pygame.K_RIGHT, (1, 0)),
    (pygame.K_d, (1, 0)),
)
MOVE_REPEAT_INITIAL_DELAY = 12
MOVE_REPEAT_INTERVAL = 6


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Dungeon Crawler")
        # Without SCALED, SDL renders our fixed logical resolution into the
        # top-left corner of the real (much larger) device screen and
        # leaves the rest black. SCALED stretches the same fixed-size
        # surface to fill whatever window/screen it ends up in - on
        # Android that's the full display, on desktop it's a no-op since
        # the window is created at exactly the requested size anyway.
        #
        # Deliberately NOT also passing pygame.FULLSCREEN on Android:
        # buildozer.spec's own fullscreen=1 + orientation=landscape already
        # lock that at the manifest/native level. Adding FULLSCREEN here
        # too made SDL2-for-Android's SDLActivity.setOrientation() re-derive
        # the requested orientation from the *actual* window dimensions it
        # ends up creating instead of trusting the manifest - which flipped
        # the app into portrait on a real device once the window was wider
        # than it was tall in a way that tripped its w>h heuristic.
        self.screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SCALED)
        self.clock = pygame.time.Clock()
        # pygame.font.SysFont looks up a named font through the OS's font
        # system, which crashes on Android (no such font, no font-listing
        # tools like fc-list in the sandbox). pygame.font.Font(None, size)
        # uses pygame's own bundled default font instead - no OS lookup,
        # works identically on every platform.
        self.font = pygame.font.Font(None, 18)
        self.big_font = pygame.font.Font(None, 40)
        self.big_font.set_bold(True)
        self.stats = persistence.load_stats()
        self.save_data = persistence.load_save()
        self.settings = persistence.load_settings()
        self.sounds = sound.Sounds(volume=self.settings.get("volume", sound.MASTER_VOLUME))
        self.player_sprite_right, self.player_sprite_left, self.player_sprite_large = self._load_player_sprite()
        self.monster_sprites = self._load_monster_sprites()
        self.state = "title"
        self.stats_return_state = "title"
        self.settings_return_state = "title"
        self.new_best = False
        self.touch_direction = None
        self.touch_warning_timer = 0
        self._tap_targets = []
        self._setup_touch_controls()

    def _load_player_sprite(self):
        try:
            image = pygame.image.load(C.PLAYER_SPRITE_PATH).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None, None, None
        height = C.PLAYER_SPRITE_HEIGHT
        width = int(image.get_width() * (height / image.get_height()))
        right = pygame.transform.smoothscale(image, (width, height))
        left = pygame.transform.flip(right, True, False)
        large = pygame.transform.smoothscale(image, (width * 2, height * 2))
        return right, left, large

    def _load_monster_sprites(self):
        sprites = {}
        for kind in C.MONSTER_TYPES:
            path = os.path.join(C.MONSTER_SPRITE_DIR, f"{kind}.png")
            try:
                image = pygame.image.load(path).convert_alpha()
            except (pygame.error, FileNotFoundError):
                continue
            height = C.MONSTER_SPRITE_HEIGHT
            width = int(image.get_width() * (height / image.get_height()))
            right = pygame.transform.smoothscale(image, (width, height))
            left = pygame.transform.flip(right, True, False)
            sprites[kind] = (right, left)
        return sprites

    def _setup_touch_controls(self):
        # Classic two-thumb mobile layout: movement bottom-left, actions
        # bottom-right, each fully inside its own side gutter (not overlaid
        # on the map view) so they're big enough to actually hit and never
        # obscure the dungeon.
        s, g = 64, 8
        dpad_cx, dpad_cy = C.GUTTER_WIDTH // 2, 480
        self.dpad_buttons = {
            "up": (pygame.Rect(dpad_cx - s // 2, dpad_cy - s - g, s, s), (0, -1), "^"),
            "down": (pygame.Rect(dpad_cx - s // 2, dpad_cy + g, s, s), (0, 1), "v"),
            "left": (pygame.Rect(dpad_cx - s - g - s // 2, dpad_cy - s // 2, s, s), (-1, 0), "<"),
            "right": (pygame.Rect(dpad_cx + g + s // 2, dpad_cy - s // 2, s, s), (1, 0), ">"),
        }

        action_right_edge = C.SCREEN_WIDTH - 16
        potion_size = 76
        self.potion_button = pygame.Rect(action_right_edge - potion_size, 500, potion_size, potion_size)

        scroll_size = 52
        scroll_gap = 8
        scroll_y = 500 - scroll_gap - scroll_size
        scroll_row_width = 3 * scroll_size + 2 * scroll_gap
        scroll_start_x = action_right_edge - scroll_row_width
        self.scroll_buttons = {
            "fireball": pygame.Rect(scroll_start_x, scroll_y, scroll_size, scroll_size),
            "teleport": pygame.Rect(scroll_start_x + (scroll_size + scroll_gap), scroll_y, scroll_size, scroll_size),
            "reveal": pygame.Rect(scroll_start_x + 2 * (scroll_size + scroll_gap), scroll_y, scroll_size, scroll_size),
        }

        # Bigger and pinned to the top-right corner so it's always easy to
        # find and tap - this is the only touch way back to the pause menu,
        # and it stays visible even when show_touch_controls is off.
        self.save_button = pygame.Rect(C.SCREEN_WIDTH - 140, 8, 124, 52)

    def start_new_run(self):
        persistence.delete_save()
        self.save_data = None

        self.dungeon_level = 1
        self.log = []
        self.player = entities.Player(0, 0)
        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_repeat_timer = 0
        self.move_held = False
        self.new_best = False
        self.damage_numbers = []
        self.boss_banner_timer = 0
        self.pending_perk_count = 0
        self.perk_choices = []
        self.new_level()
        self.add_log(self.t("log_descend_dungeon"))
        self.state = "playing"

    def continue_run(self):
        data = self.save_data
        if data is None:
            self.start_new_run()
            return

        self.dungeon_level = data["dungeon_level"]
        self.log = list(data.get("log", []))

        p = data["player"]
        player = entities.Player(p["x"], p["y"])
        player.hp = p["hp"]
        player.max_hp = p["max_hp"]
        player.base_power = p["base_power"]
        player.base_defense = p["base_defense"]
        player.weapon_bonus = p["weapon_bonus"]
        player.weapon_name = p["weapon_name"]
        player.armor_bonus = p["armor_bonus"]
        player.armor_name = p["armor_name"]
        player.level = p["level"]
        player.xp = p["xp"]
        player.xp_to_next = p["xp_to_next"]
        player.potions = p["potions"]
        player.kills = p["kills"]
        player.facing = p["facing"]
        player.gold = p.get("gold", 0)
        player.scrolls = dict(p.get("scrolls", {"fireball": 0, "teleport": 0, "reveal": 0}))
        player.poison_turns = p.get("poison_turns", 0)
        player.potions_drunk_this_run = p.get("potions_drunk_this_run", 0)
        player.bonus_crit_chance = p.get("bonus_crit_chance", 0.0)
        self.player = player

        self.grid = data["grid"]
        self.stairs_pos = tuple(data["stairs_pos"])
        self.explored = {tuple(t) for t in data["explored"]}
        self.traps = {tuple(int(v) for v in pos): kind for pos, kind in data.get("traps", [])}

        self.monsters = []
        for m in data["monsters"]:
            elite = None
            if m.get("elite_name"):
                elite = next((e for e in C.ELITE_MODIFIERS if e["name"] == m["elite_name"]), None)
            monster = entities.Monster(m["x"], m["y"], m["kind"], boss=m["boss"], elite=elite)
            monster.hp = m["hp"]
            monster.awake = m["awake"]
            monster.is_split_child = m.get("is_split_child", False)
            self.monsters.append(monster)

        self.items = []
        for i in data["items"]:
            self.items.append(
                entities.Item(
                    i["x"], i["y"], i["kind"], i["name"], i["char"], tuple(i["color"]),
                    bonus=i["bonus"], scroll_type=i.get("scroll_type"),
                )
            )

        self.merchants = [entities.Merchant(m["x"], m["y"]) for m in data.get("merchants", [])]

        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_repeat_timer = 0
        self.move_held = False
        self.new_best = False
        self.damage_numbers = []
        self.boss_banner_timer = 0
        self.pending_perk_count = 0
        self.perk_choices = []

        self._recompute_fov()
        self.add_log(self.t("log_continue_descent"))
        self.state = "playing"

    def _build_save_data(self):
        p = self.player
        return {
            "dungeon_level": self.dungeon_level,
            "log": self.log,
            "player": {
                "x": p.x, "y": p.y, "hp": p.hp, "max_hp": p.max_hp,
                "base_power": p.base_power, "base_defense": p.base_defense,
                "weapon_bonus": p.weapon_bonus, "weapon_name": p.weapon_name,
                "armor_bonus": p.armor_bonus, "armor_name": p.armor_name,
                "level": p.level, "xp": p.xp, "xp_to_next": p.xp_to_next,
                "potions": p.potions, "kills": p.kills, "facing": p.facing,
                "gold": p.gold, "scrolls": dict(p.scrolls), "poison_turns": p.poison_turns,
                "potions_drunk_this_run": p.potions_drunk_this_run,
                "bonus_crit_chance": p.bonus_crit_chance,
            },
            "grid": self.grid,
            "stairs_pos": list(self.stairs_pos),
            "explored": [list(t) for t in self.explored],
            "traps": [[list(pos), kind] for pos, kind in self.traps.items()],
            "monsters": [
                {
                    "x": m.x, "y": m.y, "kind": m.kind, "boss": m.is_boss, "hp": m.hp, "awake": m.awake,
                    "elite_name": m.elite_name, "is_split_child": m.is_split_child,
                }
                for m in self.monsters
            ],
            "items": [
                {"x": i.x, "y": i.y, "kind": i.kind, "name": i.name, "char": i.char,
                 "color": list(i.color), "bonus": i.bonus, "scroll_type": i.scroll_type}
                for i in self.items
            ],
            "merchants": [{"x": m.x, "y": m.y} for m in self.merchants],
        }

    def _save_and_quit(self):
        persistence.save_run(self._build_save_data())
        pygame.quit()
        sys.exit()

    def new_level(self):
        while True:
            self.grid, self.rooms = dungeon.generate_dungeon(C.MAP_WIDTH, C.MAP_HEIGHT)
            if len(self.rooms) >= 2:
                break

        self.explored = set()
        self.player.x, self.player.y = self.rooms[0].center()
        self.player.snap()
        self.stairs_pos = self.rooms[-1].center()

        self.monsters = []
        self.items = []
        self.merchants = []
        self.traps = {}
        self.damage_numbers = []
        self._populate_level()

        self._recompute_fov()

    def _maybe_elite(self):
        if self.dungeon_level >= 2 and random.random() < C.ELITE_CHANCE:
            return random.choice(C.ELITE_MODIFIERS)
        return None

    def _populate_level(self):
        monster_kinds = list(C.MONSTER_TYPES.keys())
        weights = [
            3,
            2 if self.dungeon_level >= 2 else 0.2,
            1 if self.dungeon_level >= 3 else 0.05,
            1.5 if self.dungeon_level >= 2 else 0.1,
            2 if self.dungeon_level >= 1 else 0,
            1.2 if self.dungeon_level >= 1 else 0,
            1 if self.dungeon_level >= 3 else 0.05,
        ]
        num_monsters = min(2 + self.dungeon_level, 12)

        spawnable_rooms = self.rooms[1:] or self.rooms

        for _ in range(num_monsters):
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if not self._is_occupied(x, y):
                kind = random.choices(monster_kinds, weights=weights, k=1)[0]
                self.monsters.append(entities.Monster(x, y, kind, elite=self._maybe_elite()))

        if self.dungeon_level % 5 == 0:
            bx, by = self.stairs_pos
            tier = (self.dungeon_level // 5 - 1) % len(C.BOSS_KIND_CYCLE)
            boss_kind = C.BOSS_KIND_CYCLE[tier]
            self.monsters.append(entities.Monster(bx, by, boss_kind, boss=True))
            self.add_log(self.t("log_boss_guards"))

        for _ in range(random.randint(1, 3)):
            self._spawn_item(random.choice(spawnable_rooms), "potion")
        if random.random() < 0.7:
            self._spawn_item(random.choice(spawnable_rooms), "weapon")
        if random.random() < 0.7:
            self._spawn_item(random.choice(spawnable_rooms), "armor")
        for _ in range(random.randint(1, 2)):
            self._spawn_item(random.choice(spawnable_rooms), "gold")
        if random.random() < 0.5:
            self._spawn_item(random.choice(spawnable_rooms), "scroll")

        for room in spawnable_rooms:
            if random.random() < C.TRAP_CHANCE_PER_ROOM:
                x, y = self._random_floor_in_room(room)
                if not self._is_occupied(x, y) and (x, y) != self.stairs_pos and (x, y) not in self.traps:
                    self.traps[(x, y)] = random.choice(list(C.TRAP_TYPES.keys()))

        if random.random() < C.MERCHANT_CHANCE_PER_LEVEL:
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if not self._is_occupied(x, y) and (x, y) not in self.traps and (x, y) != self.stairs_pos:
                self.merchants.append(entities.Merchant(x, y))

    def _spawn_item(self, room, kind):
        x, y = self._random_floor_in_room(room)
        if self._is_occupied(x, y) or any((i.x, i.y) == (x, y) for i in self.items):
            return

        if kind == "potion":
            self.items.append(
                entities.Item(x, y, "potion", "Healing Potion", "!", C.COLOR_POTION, bonus=15)
            )
        elif kind == "weapon":
            tier_max = min(len(C.WEAPON_TYPES) - 1, self.dungeon_level // 2)
            w = C.WEAPON_TYPES[random.randint(0, tier_max)]
            self.items.append(entities.Item(x, y, "weapon", w["name"], "/", w["color"], bonus=w["bonus"]))
        elif kind == "armor":
            tier_max = min(len(C.ARMOR_TYPES) - 1, self.dungeon_level // 2)
            a = C.ARMOR_TYPES[random.randint(0, tier_max)]
            self.items.append(entities.Item(x, y, "armor", a["name"], "[", a["color"], bonus=a["bonus"]))
        elif kind == "gold":
            amount = random.randint(5, 15) * self.dungeon_level
            self.items.append(entities.Item(x, y, "gold", "Gold", "$", C.COLOR_GOLD, bonus=amount))
        elif kind == "scroll":
            scroll_type = random.choice(list(C.SCROLL_TYPES.keys()))
            info = C.SCROLL_TYPES[scroll_type]
            self.items.append(
                entities.Item(x, y, "scroll", info["name"], info["char"], info["color"], scroll_type=scroll_type)
            )

    def _random_floor_in_room(self, room):
        x = random.randint(room.x1, room.x2 - 1)
        y = random.randint(room.y1, room.y2 - 1)
        return x, y

    def _random_floor_tile(self):
        for _ in range(200):
            x = random.randint(0, C.MAP_WIDTH - 1)
            y = random.randint(0, C.MAP_HEIGHT - 1)
            if dungeon.is_walkable(self.grid, x, y) and not self._is_occupied(x, y):
                return x, y
        return None

    def _is_occupied(self, x, y):
        if (x, y) == (self.player.x, self.player.y):
            return True
        if any((m.x, m.y) == (x, y) for m in self.monsters):
            return True
        if any((m.x, m.y) == (x, y) for m in getattr(self, "merchants", [])):
            return True
        return False

    def _recompute_fov(self):
        self.visible = fov.compute_fov(self.grid, self.player.x, self.player.y, C.FOV_RADIUS)
        self.explored |= self.visible

    def add_log(self, message):
        self.log.append(message)
        self.log = self.log[-5:]

    def _lang(self):
        return self.settings.get("language", "en")

    def t(self, key, **kwargs):
        text = loc.STRINGS[key].get(self._lang(), loc.STRINGS[key]["en"])
        return text.format(**kwargs) if kwargs else text

    def tn(self, name):
        if self._lang() == "de":
            return loc.NAME_DE.get(name, name)
        return name

    def _toggle_touch_controls(self):
        self.settings["show_touch_controls"] = not self.settings.get("show_touch_controls", True)
        persistence.save_settings(self.settings)

    def _request_toggle_touch_controls(self):
        # Turning controls back ON, or toggling on PC (keyboard is always
        # there), is safe to do instantly. Turning them OFF on Android
        # removes the only way to move/act on a touchscreen, so gate it
        # behind a mandatory-wait confirmation instead of a plain toggle.
        currently_on = self.settings.get("show_touch_controls", True)
        if currently_on and ON_ANDROID:
            self.touch_warning_timer = 300
            self.state = "confirm_disable_touch"
        else:
            self._toggle_touch_controls()

    def _toggle_language(self):
        self.settings["language"] = "de" if self._lang() == "en" else "en"
        persistence.save_settings(self.settings)

    VOLUME_LEVELS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

    def _cycle_volume(self):
        current = self.settings.get("volume", sound.MASTER_VOLUME)
        idx = min(range(len(self.VOLUME_LEVELS)), key=lambda i: abs(self.VOLUME_LEVELS[i] - current))
        idx = (idx + 1) % len(self.VOLUME_LEVELS)
        new_volume = self.VOLUME_LEVELS[idx]
        self.settings["volume"] = new_volume
        self.sounds.set_volume(new_volume)
        persistence.save_settings(self.settings)
        if new_volume > 0:
            self.sounds.play("equip")

    def _monster_gender(self, monster):
        if monster.is_boss:
            return loc.BOSS_GENDER_DE.get(monster.kind, "m")
        return loc.MONSTER_GENDER_DE.get(monster.kind, "m")

    def _monster_article(self, monster, case="nom"):
        gender = self._monster_gender(monster)
        return loc.ARTICLES_DE[gender][case]

    def _monster_display_name(self, monster):
        if self._lang() != "de":
            return monster.name
        base = loc.MONSTER_NAME_DE.get(monster.kind, monster.kind)
        gender = self._monster_gender(monster)
        if monster.is_boss:
            title = loc.BOSS_TITLE_DE.get(monster.kind, "Haeuptling")
            base = f"{base}-{title}"
        if monster.elite_name:
            elite_stem = loc.ELITE_NAME_DE.get(monster.elite_name, monster.elite_name)
            ending = loc.ADJ_ENDING_DE.get(gender, "er")
            base = f"{elite_stem}{ending} {base}"
        return base

    def _monster_named(self, monster, case="nom"):
        if self._lang() != "de":
            article = "The" if case == "nom" else "the"
            return f"{article} {monster.name}"
        article = self._monster_article(monster, case)
        if case == "nom":
            article = article.capitalize()
        return f"{article} {self._monster_display_name(monster)}"

    def _trap_display_name(self, kind):
        if self._lang() == "de":
            return loc.TRAP_NAME_DE.get(kind, kind)
        return C.TRAP_TYPES[kind]["name"]

    def _achievement_name(self, ach_id, fallback):
        if self._lang() == "de" and ach_id in loc.ACHIEVEMENT_DE:
            return loc.ACHIEVEMENT_DE[ach_id][0]
        return fallback

    def _record_bestiary(self, kind):
        seen = self.stats.setdefault("bestiary_seen", [])
        if kind not in seen:
            seen.append(kind)

    def _achievement_desc(self, ach_id, fallback):
        if self._lang() == "de" and ach_id in loc.ACHIEVEMENT_DE:
            return loc.ACHIEVEMENT_DE[ach_id][1]
        return fallback

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    if self.state == "playing":
                        persistence.save_run(self._build_save_data())
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_tap(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.touch_direction = None

            if self.state == "playing":
                self._handle_movement_repeat()
                self._update_animations()
            elif self.state == "confirm_disable_touch" and self.touch_warning_timer > 0:
                self.touch_warning_timer -= 1

            self.render()
            self.clock.tick(30)

    def _handle_movement_repeat(self):
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        for key, vector in MOVE_KEYS:
            if keys[key]:
                dx, dy = vector
                break

        if dx == 0 and dy == 0 and self.touch_direction:
            dx, dy = self.touch_direction

        if dx == 0 and dy == 0:
            self.move_repeat_timer = 0
            self.move_held = False
            return

        if self.move_repeat_timer <= 0:
            self._player_turn(dx, dy)
            if self.state != "playing":
                return
            self.move_repeat_timer = MOVE_REPEAT_INTERVAL if self.move_held else MOVE_REPEAT_INITIAL_DELAY
            self.move_held = True
        else:
            self.move_repeat_timer -= 1

    def _update_animations(self):
        self.player.update_animation()
        for monster in self.monsters:
            monster.update_animation()
        if self.shake_timer > 0:
            self.shake_timer -= 1
        if self.flash_timer > 0:
            self.flash_timer -= 1
        if self.boss_banner_timer > 0:
            self.boss_banner_timer -= 1
        for dn in self.damage_numbers:
            dn["timer"] -= 1
        self.damage_numbers = [dn for dn in self.damage_numbers if dn["timer"] > 0]

    def _spawn_damage_number(self, x, y, text, color):
        self.damage_numbers.append({"x": x, "y": y, "text": text, "color": color, "timer": 30, "max_timer": 30})

    def _handle_tap(self, pos):
        if self.state == "stats":
            self.state = self.stats_return_state
            return
        if self.state in ("achievements", "tutorial", "bestiary"):
            self.state = "title"
            return

        if self.state in ("title", "dead", "paused", "shop", "settings", "levelup_choice", "confirm_disable_touch"):
            for rect, key in self._tap_targets:
                if rect.collidepoint(pos):
                    self._handle_key(key)
                    return
            return

        if self.state != "playing":
            return

        # The menu button always works, even with show_touch_controls off -
        # see _render_touch_controls for why.
        if self.save_button.collidepoint(pos):
            self.state = "paused"
            return

        if not self.settings.get("show_touch_controls", True):
            return

        if self.potion_button.collidepoint(pos):
            self._drink_potion()
            return
        for name, rect in self.scroll_buttons.items():
            if rect.collidepoint(pos):
                self._use_scroll(name)
                return
        for rect, vector, _label in self.dpad_buttons.values():
            if rect.collidepoint(pos):
                self.touch_direction = vector
                return

    def _handle_key(self, key):
        if self.state == "stats":
            self.state = self.stats_return_state
            return
        if self.state in ("achievements", "tutorial", "bestiary"):
            self.state = "title"
            return

        if self.state == "settings":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.state = self.settings_return_state
            elif key == pygame.K_c:
                self._request_toggle_touch_controls()
            elif key == pygame.K_l:
                self._toggle_language()
            elif key == pygame.K_v:
                self._cycle_volume()
            return

        if self.state == "confirm_disable_touch":
            if key == pygame.K_ESCAPE:
                self.state = "settings"
            elif key == pygame.K_RETURN and self.touch_warning_timer <= 0:
                self._toggle_touch_controls()
                self.state = "settings"
            return

        if self.state == "title":
            if key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            elif key == pygame.K_s:
                self.stats_return_state = "title"
                self.state = "stats"
            elif key == pygame.K_a:
                self.state = "achievements"
            elif key == pygame.K_t:
                self.state = "tutorial"
            elif key == pygame.K_b:
                self.state = "bestiary"
            elif key == pygame.K_o:
                self.settings_return_state = "title"
                self.state = "settings"
            elif key == pygame.K_n:
                self.start_new_run()
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.save_data:
                    self.continue_run()
                else:
                    self.start_new_run()
            return

        if self.state == "dead":
            if key == pygame.K_r:
                self.start_new_run()
            elif key == pygame.K_s:
                self.stats_return_state = "dead"
                self.state = "stats"
            elif key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            return

        if self.state == "paused":
            if key == pygame.K_ESCAPE:
                self.state = "playing"
            elif key == pygame.K_q:
                self._save_and_quit()
            elif key == pygame.K_s:
                self.stats_return_state = "paused"
                self.state = "stats"
            elif key == pygame.K_o:
                self.settings_return_state = "paused"
                self.state = "settings"
            return

        if self.state == "shop":
            if key == pygame.K_ESCAPE:
                self.state = "playing"
            elif pygame.K_1 <= key <= pygame.K_4:
                self._buy_item(key - pygame.K_1)
            return

        if self.state == "levelup_choice":
            if key == pygame.K_1 and len(self.perk_choices) > 0:
                self._apply_perk(self.perk_choices[0])
            elif key == pygame.K_2 and len(self.perk_choices) > 1:
                self._apply_perk(self.perk_choices[1])
            return

        if key == pygame.K_ESCAPE:
            self.state = "paused"
        elif key == pygame.K_g:
            self._drink_potion()
        elif key == pygame.K_f:
            self._use_scroll("fireball")
        elif key == pygame.K_t:
            self._use_scroll("teleport")
        elif key == pygame.K_v:
            self._use_scroll("reveal")

    def _player_turn(self, dx, dy):
        self._tick_poison()
        if self.state == "dead":
            return

        if dx != 0:
            self.player.facing = 1 if dx > 0 else -1

        target_x, target_y = self.player.x + dx, self.player.y + dy

        target_merchant = next((m for m in self.merchants if m.x == target_x and m.y == target_y), None)
        if target_merchant:
            self.state = "shop"
            return

        target_monster = next(
            (m for m in self.monsters if m.x == target_x and m.y == target_y), None
        )
        if target_monster:
            self._attack(self.player, target_monster)
        elif dungeon.is_walkable(self.grid, target_x, target_y):
            self.player.move(dx, dy)
            pos = (self.player.x, self.player.y)
            if pos in self.traps:
                self._trigger_trap(pos)
                if self.state == "dead":
                    return
            item = next((i for i in self.items if i.x == self.player.x and i.y == self.player.y), None)
            if item:
                self._collect_item(item)
            if (self.player.x, self.player.y) == self.stairs_pos:
                self._advance_level()
                return
        else:
            return

        if self.state == "dead":
            return
        self._enemy_turn()
        self._recompute_fov()
        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _tick_poison(self):
        if self.player.poison_turns <= 0:
            return
        self.player.poison_turns -= 1
        dmg = C.POISON_DAMAGE_PER_TURN
        self.player.hp -= dmg
        self._spawn_damage_number(self.player.x, self.player.y, str(dmg), C.COLOR_POISON)
        self.add_log(self.t("log_poison_damage", dmg=dmg))
        if self.player.hp <= 0:
            self.add_log(self.t("log_succumb_poison"))
            self.sounds.play("death")
            self.state = "dead"
            self._finalize_run()

    def _trigger_trap(self, pos):
        kind = self.traps.pop(pos)
        info = C.TRAP_TYPES[kind]
        trap_name = self._trap_display_name(kind)
        if kind == "spike":
            dmg = random.randint(info["min_damage"], info["max_damage"])
            self.player.hp -= dmg
            self._spawn_damage_number(*pos, str(dmg), C.COLOR_TRAP)
            self.add_log(self.t("log_trap_damage", trap=trap_name, dmg=dmg))
            self.sounds.play("player_hurt")
            self.shake_timer = 6
            self.shake_intensity = 4
            self.flash_timer = 6
            if self.player.hp <= 0:
                self.add_log(self.t("log_trap_finish"))
                self.sounds.play("death")
                self.state = "dead"
                self._finalize_run()
        elif kind == "poison":
            self.player.poison_turns = max(self.player.poison_turns, info["poison_turns"])
            self.add_log(self.t("log_trap_poison", trap=trap_name))
        elif kind == "alarm":
            self.add_log(self.t("log_trap_alarm", trap=trap_name))
            for m in self.monsters:
                m.awake = True

    def _advance_level(self):
        self.dungeon_level += 1
        self.add_log(self.t("log_descend_level", level=self.dungeon_level))
        self.sounds.play("stairs")
        self.new_level()
        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _collect_item(self, item):
        if item.kind == "potion":
            self.player.potions += 1
            self.add_log(self.t("log_pickup_item", item=self.tn(item.name)))
            self.sounds.play("pickup")
        elif item.kind == "weapon":
            if item.bonus > self.player.weapon_bonus:
                self.player.weapon_bonus = item.bonus
                self.player.weapon_name = item.name
                self.add_log(self.t("log_equip_weapon", item=self.tn(item.name), bonus=item.bonus))
                self.sounds.play("equip")
            else:
                self.add_log(self.t("log_find_worse_weapon", item=self.tn(item.name), current=self.tn(self.player.weapon_name)))
        elif item.kind == "armor":
            if item.bonus > self.player.armor_bonus:
                self.player.armor_bonus = item.bonus
                self.player.armor_name = item.name
                self.add_log(self.t("log_equip_armor", item=self.tn(item.name), bonus=item.bonus))
                self.sounds.play("equip")
            else:
                self.add_log(self.t("log_find_worse_armor", item=self.tn(item.name), current=self.tn(self.player.armor_name)))
        elif item.kind == "gold":
            self.player.gold += item.bonus
            self.stats["total_gold_collected"] = self.stats.get("total_gold_collected", 0) + item.bonus
            self.add_log(self.t("log_pickup_gold", amount=item.bonus))
            self.sounds.play("pickup")
        elif item.kind == "scroll":
            self.player.scrolls[item.scroll_type] += 1
            self.add_log(self.t("log_pickup_item", item=self.tn(item.name)))
            self.sounds.play("pickup")
        self.items.remove(item)

    def _drink_potion(self):
        if self.player.potions <= 0:
            self.add_log(self.t("log_no_potions"))
            return
        if self.player.hp >= self.player.max_hp:
            self.add_log(self.t("log_full_health"))
            return

        healed = min(15, self.player.max_hp - self.player.hp)
        self.player.potions -= 1
        self.player.hp += healed
        self.player.potions_drunk_this_run += 1
        self.stats["total_potions_drunk"] += 1
        self.add_log(self.t("log_drink_potion", healed=healed))
        self.sounds.play("pickup")
        self._enemy_turn()
        self._recompute_fov()
        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _buy_item(self, index):
        if index < 0 or index >= len(C.SHOP_STOCK):
            return
        stock = C.SHOP_STOCK[index]
        if self.player.gold < stock["price"]:
            self.add_log(self.t("log_not_enough_gold"))
            return
        self.player.gold -= stock["price"]
        if stock["kind"] == "potion":
            self.player.potions += 1
        elif stock["kind"] == "scroll":
            self.player.scrolls[stock["scroll_type"]] += 1
        self.add_log(self.t("log_bought_item", item=self.tn(stock['name'])))
        self.sounds.play("equip")

    def _use_scroll(self, scroll_type):
        if self.state != "playing":
            return
        if self.player.scrolls.get(scroll_type, 0) <= 0:
            self.add_log(self.t("log_no_scroll", scroll=self.tn(C.SCROLL_TYPES[scroll_type]['name'])))
            return

        if scroll_type == "fireball":
            target = min(
                (m for m in self.monsters if (m.x, m.y) in self.visible),
                key=lambda m: abs(m.x - self.player.x) + abs(m.y - self.player.y),
                default=None,
            )
            if target is None:
                self.add_log(self.t("log_no_target"))
                return
            self.player.scrolls[scroll_type] -= 1
            self.stats["total_scrolls_used"] = self.stats.get("total_scrolls_used", 0) + 1
            affected = [target] + [
                m for m in self.monsters
                if m is not target and abs(m.x - target.x) <= 1 and abs(m.y - target.y) <= 1
            ]
            dmg = 10 + self.player.level * 2
            for m in affected:
                m.hp -= dmg
                self._spawn_damage_number(m.x, m.y, str(dmg), (255, 140, 40))
            self.add_log(self.t("log_fireball_hit", count=len(affected)))
            self.sounds.play("hit")
            for m in list(affected):
                if m.hp <= 0 and m in self.monsters:
                    self._on_monster_death(m)
            self._enemy_turn()
            self._recompute_fov()

        elif scroll_type == "teleport":
            spot = self._random_floor_tile()
            self.player.scrolls[scroll_type] -= 1
            self.stats["total_scrolls_used"] = self.stats.get("total_scrolls_used", 0) + 1
            if spot:
                self.player.x, self.player.y = spot
                self.player.snap()
                self.add_log(self.t("log_blink"))
                self._recompute_fov()
            self._enemy_turn()

        elif scroll_type == "reveal":
            self.player.scrolls[scroll_type] -= 1
            self.stats["total_scrolls_used"] = self.stats.get("total_scrolls_used", 0) + 1
            self.explored |= {
                (x, y) for y in range(C.MAP_HEIGHT) for x in range(C.MAP_WIDTH)
                if self.grid[y][x] != dungeon.WALL
            }
            self.add_log(self.t("log_reveal"))

        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _attack(self, attacker, defender):
        crit = attacker is self.player and random.random() < self.player.crit_chance
        damage = max(1, attacker.power - defender.defense)
        if crit:
            damage *= 2
        defender.hp -= damage

        if self._lang() == "de":
            attacker_label = "Du" if attacker is self.player else self._monster_named(attacker, "nom")
            defender_label = "dich" if defender is self.player else self._monster_named(defender, "acc")
            verb = "triffst" if attacker is self.player else "trifft"
            if crit:
                self.add_log(f"Kritischer Treffer! {attacker_label} {verb} {defender_label} fuer {damage}.")
            else:
                self.add_log(f"{attacker_label} {verb} {defender_label} fuer {damage}.")
        else:
            attacker_label = "You" if attacker is self.player else self._monster_named(attacker, "nom")
            defender_label = "you" if defender is self.player else self._monster_named(defender, "acc")
            if crit:
                self.add_log(f"Critical hit! {attacker_label} hit {defender_label} for {damage}.")
            else:
                self.add_log(f"{attacker_label} hit {defender_label} for {damage}.")

        number_color = C.COLOR_CRIT if crit else ((255, 255, 255) if attacker is self.player else (255, 120, 120))
        self._spawn_damage_number(defender.x, defender.y, f"{damage}{'!' if crit else ''}", number_color)

        if attacker is self.player:
            self.sounds.play("hit")
        else:
            self.sounds.play("player_hurt")
            self.shake_timer = 6
            self.shake_intensity = 4
            self.flash_timer = 6

        if getattr(attacker, "poisons_on_hit", False) and defender is self.player and defender.hp > 0:
            defender.poison_turns = max(defender.poison_turns, 5)
            self.add_log(self.t("log_poison_bite"))

        if defender.hp <= 0:
            if defender is self.player:
                self.add_log(self.t("log_you_died"))
                self.sounds.play("death")
                self.state = "dead"
                self._finalize_run()
            else:
                self._on_monster_death(defender)

    def _on_monster_death(self, monster):
        self.add_log(self.t("log_monster_dies", monster=self._monster_named(monster, "nom"), xp=monster.xp_reward))
        self.sounds.play("monster_death")
        if monster in self.monsters:
            self.monsters.remove(monster)
        self.player.kills += 1
        self._record_kill(monster)
        if monster.splits and not monster.is_split_child:
            self._spawn_slime_children(monster)
        levels = self.player.gain_xp(monster.xp_reward)
        if levels:
            self.add_log(self.t("log_level_up", level=self.player.level))
            self.sounds.play("levelup")
            self.pending_perk_count += levels

    def _spawn_slime_children(self, parent):
        spots = [
            (parent.x + 1, parent.y), (parent.x - 1, parent.y),
            (parent.x, parent.y + 1), (parent.x, parent.y - 1),
        ]
        spawned = 0
        for x, y in spots:
            if spawned >= 2:
                break
            if not dungeon.is_walkable(self.grid, x, y) or self._is_occupied(x, y):
                continue
            child = entities.Monster(x, y, parent.kind)
            child.max_hp = max(1, parent.max_hp // 2)
            child.hp = child.max_hp
            child.power = parent.power
            child.defense = parent.defense
            child.xp_reward = max(1, parent.xp_reward // 3)
            child.is_split_child = True
            child.awake = True
            self.monsters.append(child)
            spawned += 1

    def _record_kill(self, monster):
        key = "boss" if monster.is_boss else monster.kind
        self.stats["kills_by_monster"][key] = self.stats["kills_by_monster"].get(key, 0) + 1
        self.stats["total_kills"] += 1

    def _check_achievements(self):
        unlocked = self.stats.setdefault("achievements_unlocked", [])
        s = self.stats
        p = self.player
        checks = {
            "first_blood": s["total_kills"] >= 1,
            "survivor": p.level >= 5,
            "veteran": p.level >= 10,
            "deep_delver": self.dungeon_level >= 5,
            "spelunker": self.dungeon_level >= 10,
            "boss_slayer": s["kills_by_monster"].get("boss", 0) >= 1,
            "rich": p.gold >= 100,
            "hoarder": s.get("total_gold_collected", 0) >= 500,
            "well_read": s.get("total_scrolls_used", 0) >= 10,
            "persistent": s["deaths"] >= 5,
            "centurion": s["total_kills"] >= 100,
            "untouchable": self.dungeon_level >= 3 and p.potions_drunk_this_run == 0,
        }
        for ach_id, name, _desc in C.ACHIEVEMENTS:
            if ach_id in unlocked:
                continue
            if checks.get(ach_id):
                unlocked.append(ach_id)
                self.add_log(self.t("log_achievement_unlocked", name=self._achievement_name(ach_id, name)))
                self.sounds.play("levelup")

    def _maybe_show_levelup_choice(self):
        if self.pending_perk_count > 0 and self.state == "playing":
            self._roll_perk_choices()
            self.state = "levelup_choice"

    def _roll_perk_choices(self):
        self.perk_choices = random.sample(C.PERKS, 2)

    def _perk_name(self, perk):
        if self._lang() == "de" and perk["id"] in loc.PERK_DE:
            return loc.PERK_DE[perk["id"]][0]
        return perk["name"]

    def _perk_desc(self, perk):
        if self._lang() == "de" and perk["id"] in loc.PERK_DE:
            return loc.PERK_DE[perk["id"]][1]
        return perk["desc"]

    def _apply_perk(self, perk):
        self.player.base_power += perk.get("power", 0)
        self.player.base_defense += perk.get("defense", 0)
        if perk.get("hp"):
            self.player.max_hp += perk["hp"]
            self.player.hp += perk["hp"]
        self.player.bonus_crit_chance += perk.get("crit_bonus", 0.0)
        self.add_log(self.t("log_perk_chosen", perk=self._perk_name(perk)))
        self.pending_perk_count = max(0, self.pending_perk_count - 1)
        if self.pending_perk_count > 0:
            self._roll_perk_choices()
        else:
            self.perk_choices = []
            self.state = "playing"

    def _finalize_run(self):
        new_best = (
            self.dungeon_level > self.stats["deepest_level_ever"]
            or self.player.kills > self.stats["most_kills_in_a_run"]
        )
        self.stats["games_played"] += 1
        self.stats["deaths"] += 1
        self.stats["deepest_level_ever"] = max(self.stats["deepest_level_ever"], self.dungeon_level)
        self.stats["most_kills_in_a_run"] = max(self.stats["most_kills_in_a_run"], self.player.kills)
        self.stats["highest_character_level"] = max(self.stats["highest_character_level"], self.player.level)
        self.new_best = new_best
        self._check_achievements()

        persistence.save_stats(self.stats)
        persistence.delete_save()
        self.save_data = None

    def _enemy_turn(self):
        if self.state == "dead":
            return

        for monster in list(self.monsters):
            if not monster.is_alive():
                continue
            if (monster.x, monster.y) in self.visible:
                was_asleep = not monster.awake
                monster.awake = True
                if was_asleep and monster.is_boss:
                    self.boss_banner_timer = 90
                    self.sounds.play("boss")
            if not monster.awake:
                continue

            for _ in range(monster.speed):
                if not monster.is_alive() or self.state == "dead":
                    break
                self._monster_act(monster)
                if self.state == "dead":
                    return

            if monster.regen and monster.is_alive() and monster.hp < monster.max_hp:
                monster.hp = min(monster.max_hp, monster.hp + monster.regen)

    def _monster_act(self, monster):
        dx = self.player.x - monster.x
        dy = self.player.y - monster.y
        if dx != 0:
            monster.facing = 1 if dx > 0 else -1
        if abs(dx) <= 1 and abs(dy) <= 1 and (dx, dy) != (0, 0):
            self._attack(monster, self.player)
            return

        if monster.ranged:
            dist = abs(dx) + abs(dy)
            if dist <= C.FOV_RADIUS and self._cardinal_line_clear(monster.x, monster.y, self.player.x, self.player.y):
                self._attack(monster, self.player)
                return

        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        self._move_monster_toward(monster, step_x, step_y)

    def _cardinal_line_clear(self, x1, y1, x2, y2):
        if x1 == x2 and y1 != y2:
            step = 1 if y2 > y1 else -1
            for y in range(y1 + step, y2, step):
                if not dungeon.is_walkable(self.grid, x1, y):
                    return False
            return True
        if y1 == y2 and x1 != x2:
            step = 1 if x2 > x1 else -1
            for x in range(x1 + step, x2, step):
                if not dungeon.is_walkable(self.grid, x, y1):
                    return False
            return True
        return False

    def _move_monster_toward(self, monster, step_x, step_y):
        for nx, ny in (
            (monster.x + step_x, monster.y + step_y),
            (monster.x + step_x, monster.y),
            (monster.x, monster.y + step_y),
        ):
            if (nx, ny) == (monster.x, monster.y):
                continue
            if not dungeon.is_walkable(self.grid, nx, ny):
                continue
            if (nx, ny) == (self.player.x, self.player.y):
                continue
            if any((m.x, m.y) == (nx, ny) for m in self.monsters if m is not monster):
                continue
            monster.x, monster.y = nx, ny
            return

    def _shake_offset(self):
        # C.MAP_OFFSET_X is the base offset that keeps the map centered
        # between the two control gutters - not just a screen-shake delta.
        if self.shake_timer <= 0:
            return C.MAP_OFFSET_X, 0
        return (
            C.MAP_OFFSET_X + random.randint(-self.shake_intensity, self.shake_intensity),
            random.randint(-self.shake_intensity, self.shake_intensity),
        )

    def render(self):
        if self.state == "title":
            self._render_title()
            pygame.display.flip()
            return

        if self.state == "stats":
            self._render_stats()
            pygame.display.flip()
            return

        if self.state == "achievements":
            self._render_achievements()
            pygame.display.flip()
            return

        if self.state == "tutorial":
            self._render_tutorial()
            pygame.display.flip()
            return

        if self.state == "settings":
            self._render_settings()
            pygame.display.flip()
            return

        if self.state == "bestiary":
            self._render_bestiary()
            pygame.display.flip()
            return

        if self.state == "levelup_choice":
            self._render_levelup_choice()
            pygame.display.flip()
            return

        if self.state == "confirm_disable_touch":
            self._render_confirm_disable_touch()
            pygame.display.flip()
            return

        if self.state == "shop":
            self._render_shop()
            pygame.display.flip()
            return

        if self.state == "paused":
            self._render_pause()
            pygame.display.flip()
            return

        self.screen.fill(C.COLOR_BG)
        ox, oy = self._shake_offset()
        self._render_map(ox, oy)
        self._render_entities(ox, oy)
        self._render_damage_numbers(ox, oy)
        self._render_flash()
        self._render_minimap()
        self._render_boss_bar()
        self._render_boss_banner()
        self._render_hud()
        self._render_touch_controls()

        if self.state == "dead":
            self._render_game_over()

        pygame.display.flip()

    def _draw_tap_button(self, rect, label, key):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, (45, 45, 58), rect, border_radius=8)
        pygame.draw.rect(self.screen, (130, 130, 150), rect, width=2, border_radius=8)
        text = self.font.render(label, True, C.COLOR_HUD_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))
        self._tap_targets.append((rect, key))

    def _render_title(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        title = self.big_font.render("DUNGEON CRAWLER", True, (230, 200, 60))
        rect = title.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 160))
        self.screen.blit(title, rect)

        if self.player_sprite_large is not None:
            sprite_rect = self.player_sprite_large.get_rect(
                center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 60)
            )
            self.screen.blit(self.player_sprite_large, sprite_rect)

        lines = [
            self.t("title_move_line"),
            self.t("title_new_line"),
            "",
            self.t("title_deepest_stats", level=self.stats['deepest_level_ever'], kills=self.stats['most_kills_in_a_run']),
            "",
        ]
        if self.save_data:
            saved_level = self.save_data["dungeon_level"]
            saved_char_level = self.save_data["player"]["level"]
            lines.append(self.t("title_saved_line", level=saved_level, clevel=saved_char_level))

        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 + 20 + i * 26))
            self.screen.blit(surf, r)

        button_y = C.SCREEN_HEIGHT // 2 + 20 + len(lines) * 26 + 14
        cx = C.SCREEN_WIDTH // 2
        if self.save_data:
            self._draw_tap_button((cx - 160, button_y, 150, 44), self.t("btn_continue"), pygame.K_RETURN)
            self._draw_tap_button((cx + 10, button_y, 150, 44), self.t("btn_new_run"), pygame.K_n)
        else:
            self._draw_tap_button((cx - 75, button_y, 150, 44), self.t("btn_start"), pygame.K_RETURN)
        self._draw_tap_button((cx - 235, button_y + 54, 150, 44), self.t("btn_tutorial"), pygame.K_t)
        self._draw_tap_button((cx - 75, button_y + 54, 150, 44), self.t("btn_stats"), pygame.K_s)
        self._draw_tap_button((cx + 85, button_y + 54, 150, 44), self.t("btn_achievements"), pygame.K_a)
        self._draw_tap_button((cx - 160, button_y + 108, 150, 44), self.t("btn_settings"), pygame.K_o)
        self._draw_tap_button((cx + 10, button_y + 108, 150, 44), self.t("btn_bestiary"), pygame.K_b)

    def _render_stats(self):
        self.screen.fill(C.COLOR_BG)
        title = self.big_font.render(self.t("stats_title"), True, (230, 200, 60))
        rect = title.get_rect(center=(C.SCREEN_WIDTH // 2, 90))
        self.screen.blit(title, rect)

        s = self.stats
        kb = s["kills_by_monster"]
        lines = [
            self.t("stats_runs_deaths", games=s['games_played'], deaths=s['deaths']),
            "",
            self.t("stats_deepest", level=s['deepest_level_ever']),
            self.t("stats_most_kills", kills=s['most_kills_in_a_run']),
            self.t("stats_highest_level", level=s['highest_character_level']),
            self.t("stats_potions", n=s['total_potions_drunk']),
            "",
            self.t("stats_total_kills", n=s['total_kills']),
            self.t(
                "stats_kill_breakdown",
                rats=kb.get('rat', 0), goblins=kb.get('goblin', 0),
                orcs=kb.get('orc', 0), bosses=kb.get('boss', 0),
            ),
            "",
            self.t("stats_footer"),
        ]
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, 180 + i * 30))
            self.screen.blit(surf, r)

        back_rect = pygame.Rect(C.SCREEN_WIDTH // 2 - 75, 180 + len(lines) * 30 + 10, 150, 44)
        pygame.draw.rect(self.screen, (45, 45, 58), back_rect, border_radius=8)
        pygame.draw.rect(self.screen, (130, 130, 150), back_rect, width=2, border_radius=8)
        back_text = self.font.render(self.t("btn_back"), True, C.COLOR_HUD_TEXT)
        self.screen.blit(back_text, back_text.get_rect(center=back_rect.center))

    def _render_achievements(self):
        self.screen.fill(C.COLOR_BG)
        title = self.big_font.render(self.t("achievements_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, 50)))

        unlocked = set(self.stats.get("achievements_unlocked", []))
        for i, (ach_id, name, desc) in enumerate(C.ACHIEVEMENTS):
            y = 100 + i * 32
            done = ach_id in unlocked
            color = (255, 215, 0) if done else (95, 95, 105)
            mark = "[X]" if done else "[ ]"
            name_d = self._achievement_name(ach_id, name)
            desc_d = self._achievement_desc(ach_id, desc)
            surf = self.font.render(f"{mark} {name_d} - {desc_d}", True, color)
            self.screen.blit(surf, (60, y))

        footer = self.font.render(self.t("achievements_footer"), True, C.COLOR_HUD_TEXT)
        y = 100 + len(C.ACHIEVEMENTS) * 32 + 30
        self.screen.blit(footer, footer.get_rect(center=(C.SCREEN_WIDTH // 2, y)))

    def _render_bestiary(self):
        self.screen.fill(C.COLOR_BG)
        title = self.big_font.render(self.t("bestiary_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, 50)))

        seen = set(self.stats.get("bestiary_seen", []))
        y = 110
        for kind, stats in C.MONSTER_TYPES.items():
            discovered = kind in seen
            color = stats["color"] if discovered else (80, 80, 90)
            char = stats["char"] if discovered else "?"
            if discovered:
                name = loc.MONSTER_NAME_DE.get(kind, kind) if self._lang() == "de" else stats["name"]
            else:
                name = "???"

            char_surf = self.font.render(char, True, color)
            self.screen.blit(char_surf, (60, y))
            name_color = color if discovered else (110, 110, 120)
            name_surf = self.font.render(name, True, name_color)
            self.screen.blit(name_surf, (90, y))

            if discovered:
                tags = []
                if stats.get("ranged"):
                    tags.append(self.t("tag_ranged"))
                if stats.get("splits"):
                    tags.append(self.t("tag_splits"))
                if stats.get("speed", 1) > 1:
                    tags.append(self.t("tag_fast"))
                if stats.get("poisons"):
                    tags.append(self.t("tag_poison"))
                info = self.t("bestiary_stats", hp=stats["hp"], power=stats["power"], defense=stats["defense"])
                if tags:
                    info += "  [" + ", ".join(tags) + "]"
                info_color = C.COLOR_HELP_TEXT
            else:
                info = self.t("bestiary_undiscovered")
                info_color = (80, 80, 90)

            info_surf = self.font.render(info, True, info_color)
            self.screen.blit(info_surf, (320, y))
            y += 34

        footer = self.font.render(self.t("achievements_footer"), True, C.COLOR_HUD_TEXT)
        self.screen.blit(footer, footer.get_rect(center=(C.SCREEN_WIDTH // 2, y + 20)))

    def _render_tutorial(self):
        self.screen.fill(C.COLOR_BG)
        title = self.big_font.render(self.t("tutorial_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, 40)))

        sections = loc.TUTORIAL_SECTIONS.get(self._lang(), loc.TUTORIAL_SECTIONS["en"])

        y = 90
        for heading, body_lines in sections:
            heading_surf = self.font.render(heading, True, (120, 200, 255))
            self.screen.blit(heading_surf, (50, y))
            y += 24
            for line in body_lines:
                surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
                self.screen.blit(surf, (70, y))
                y += 20
            y += 8

        footer = self.font.render(self.t("tutorial_footer"), True, C.COLOR_HELP_TEXT)
        self.screen.blit(footer, footer.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT - 20)))

    def _render_pause(self):
        self.screen.fill(C.COLOR_BG)
        self._render_map(C.MAP_OFFSET_X, 0)
        self._render_entities(C.MAP_OFFSET_X, 0)
        self._render_hud()

        overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        overlay.set_alpha(190)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        self._tap_targets = []
        title = self.big_font.render(self.t("pause_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 110)))

        cx = C.SCREEN_WIDTH // 2
        self._draw_tap_button((cx - 75, C.SCREEN_HEIGHT // 2 - 30, 150, 44), self.t("btn_resume"), pygame.K_ESCAPE)
        self._draw_tap_button((cx - 75, C.SCREEN_HEIGHT // 2 + 24, 150, 44), self.t("btn_stats"), pygame.K_s)
        self._draw_tap_button((cx - 75, C.SCREEN_HEIGHT // 2 + 78, 150, 44), self.t("btn_settings"), pygame.K_o)
        self._draw_tap_button((cx - 110, C.SCREEN_HEIGHT // 2 + 132, 220, 44), self.t("btn_save_quit"), pygame.K_q)

    def _render_settings(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        title = self.big_font.render(self.t("settings_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, 90)))

        cx = C.SCREEN_WIDTH // 2
        touch_state = self.t("on") if self.settings.get("show_touch_controls", True) else self.t("off")
        lang_state = self.t("lang_de") if self._lang() == "de" else self.t("lang_en")

        row1 = self.font.render(self.t("settings_touch_label", state=touch_state), True, C.COLOR_HUD_TEXT)
        self.screen.blit(row1, row1.get_rect(center=(cx, 190)))
        self._draw_tap_button((cx - 100, 220, 200, 44), self.t("btn_toggle"), pygame.K_c)

        row2 = self.font.render(self.t("settings_lang_label", state=lang_state), True, C.COLOR_HUD_TEXT)
        self.screen.blit(row2, row2.get_rect(center=(cx, 300)))
        self._draw_tap_button((cx - 100, 330, 200, 44), self.t("btn_toggle"), pygame.K_l)

        volume = self.settings.get("volume", sound.MASTER_VOLUME)
        row3 = self.font.render(self.t("settings_volume_label", state=f"{int(round(volume * 100))}%"), True, C.COLOR_HUD_TEXT)
        self.screen.blit(row3, row3.get_rect(center=(cx, 410)))
        self._draw_tap_button((cx - 100, 440, 200, 44), self.t("btn_toggle"), pygame.K_v)

        self._draw_tap_button((cx - 75, 520, 150, 44), self.t("btn_back"), pygame.K_ESCAPE)

        hint = self.font.render(self.t("settings_hint"), True, C.COLOR_HELP_TEXT)
        self.screen.blit(hint, hint.get_rect(center=(cx, C.SCREEN_HEIGHT - 30)))

    def _render_confirm_disable_touch(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        cx = C.SCREEN_WIDTH // 2

        title = self.big_font.render(self.t("touch_warn_title"), True, (230, 80, 80))
        self.screen.blit(title, title.get_rect(center=(cx, C.SCREEN_HEIGHT // 2 - 140)))

        y = C.SCREEN_HEIGHT // 2 - 70
        for key in ("touch_warn_line1", "touch_warn_line2"):
            surf = self.font.render(self.t(key), True, C.COLOR_HUD_TEXT)
            self.screen.blit(surf, surf.get_rect(center=(cx, y)))
            y += 26

        ready = self.touch_warning_timer <= 0
        seconds_left = (self.touch_warning_timer + 29) // 30

        button_y = y + 40
        self._draw_tap_button((cx - 160, button_y, 150, 44), self.t("btn_cancel"), pygame.K_ESCAPE)

        confirm_rect = pygame.Rect(cx + 10, button_y, 150, 44)
        if ready:
            self._draw_tap_button(confirm_rect, self.t("btn_confirm"), pygame.K_RETURN)
        else:
            # Not a registered tap target yet - visibly disabled until the
            # wait is over, showing the countdown instead of a label.
            pygame.draw.rect(self.screen, (30, 30, 36), confirm_rect, border_radius=8)
            pygame.draw.rect(self.screen, (70, 70, 80), confirm_rect, width=2, border_radius=8)
            label = self.font.render(f"{self.t('btn_confirm')} ({seconds_left})", True, (110, 110, 120))
            self.screen.blit(label, label.get_rect(center=confirm_rect.center))

    def _render_levelup_choice(self):
        self.screen.fill(C.COLOR_BG)
        self._render_map(C.MAP_OFFSET_X, 0)
        self._render_entities(C.MAP_OFFSET_X, 0)
        self._render_hud()

        overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        overlay.set_alpha(190)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        self._tap_targets = []
        title = self.big_font.render(self.t("levelup_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 150)))

        cx = C.SCREEN_WIDTH // 2
        keys = [pygame.K_1, pygame.K_2]
        for i, perk in enumerate(self.perk_choices):
            x = cx - 320 + i * 340
            y = C.SCREEN_HEIGHT // 2 - 60
            name_surf = self.font.render(f"{i + 1}. {self._perk_name(perk)}", True, (255, 255, 255))
            self.screen.blit(name_surf, name_surf.get_rect(center=(x + 150, y)))
            desc_surf = self.font.render(self._perk_desc(perk), True, C.COLOR_HUD_TEXT)
            self.screen.blit(desc_surf, desc_surf.get_rect(center=(x + 150, y + 26)))
            self._draw_tap_button((x + 50, y + 50, 200, 44), self.t("btn_choose"), keys[i])

        hint = self.font.render(self.t("levelup_hint"), True, C.COLOR_HELP_TEXT)
        self.screen.blit(hint, hint.get_rect(center=(cx, C.SCREEN_HEIGHT // 2 + 140)))

    def _render_shop(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        title = self.big_font.render(self.t("shop_title"), True, C.COLOR_MERCHANT)
        self.screen.blit(title, title.get_rect(center=(C.SCREEN_WIDTH // 2, 80)))
        gold_text = self.font.render(self.t("shop_gold_label", gold=self.player.gold), True, C.COLOR_GOLD)
        self.screen.blit(gold_text, gold_text.get_rect(center=(C.SCREEN_WIDTH // 2, 126)))

        keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
        for i, stock in enumerate(C.SHOP_STOCK):
            y = 180 + i * 60
            label = f"{i + 1}. {self.tn(stock['name'])} - {stock['price']} {self.t('gold_word')}"
            surf = self.font.render(label, True, C.COLOR_HUD_TEXT)
            self.screen.blit(surf, (C.SCREEN_WIDTH // 2 - 260, y + 8))
            self._draw_tap_button((C.SCREEN_WIDTH // 2 + 120, y - 6, 100, 40), self.t("btn_buy"), keys[i])

        leave_y = 180 + len(C.SHOP_STOCK) * 60 + 20
        self._draw_tap_button((C.SCREEN_WIDTH // 2 - 75, leave_y, 150, 44), self.t("btn_leave"), pygame.K_ESCAPE)

    def _render_minimap(self):
        mini_x, mini_y, scale = 8, 8, 3
        w, h = C.MAP_WIDTH * scale, C.MAP_HEIGHT * scale
        panel = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
        panel.fill((10, 10, 16, 170))
        self.screen.blit(panel, (mini_x, mini_y))
        for (x, y) in self.explored:
            color = (90, 90, 100) if self.grid[y][x] == dungeon.WALL else (55, 55, 65)
            pygame.draw.rect(self.screen, color, (mini_x + 2 + x * scale, mini_y + 2 + y * scale, scale, scale))
        if self.stairs_pos in self.explored:
            sx, sy = self.stairs_pos
            pygame.draw.rect(self.screen, C.COLOR_STAIRS, (mini_x + 2 + sx * scale, mini_y + 2 + sy * scale, scale, scale))
        px, py = self.player.x, self.player.y
        pygame.draw.rect(self.screen, (255, 255, 255), (mini_x + 2 + px * scale, mini_y + 2 + py * scale, scale, scale))

    def _render_boss_bar(self):
        boss = next((m for m in self.monsters if m.is_boss and m.awake and m.is_alive()), None)
        if boss is None:
            return
        bar_w, bar_h = 400, 22
        x, y = C.SCREEN_WIDTH // 2 - bar_w // 2, 10
        pygame.draw.rect(self.screen, (40, 10, 40), (x, y, bar_w, bar_h))
        ratio = max(0, boss.hp / boss.max_hp)
        pygame.draw.rect(self.screen, C.COLOR_BOSS, (x, y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(self.screen, (200, 200, 210), (x, y, bar_w, bar_h), width=2)
        boss_name = self._monster_display_name(boss).upper()
        name_text = self.font.render(f"{boss_name}  {max(0, boss.hp)}/{boss.max_hp}", True, (255, 255, 255))
        self.screen.blit(name_text, name_text.get_rect(center=(C.SCREEN_WIDTH // 2, y + bar_h // 2)))

    def _render_boss_banner(self):
        if self.boss_banner_timer <= 0:
            return
        ratio = min(1.0, (self.boss_banner_timer / 90) * 2)
        text = self.big_font.render(self.t("boss_appears"), True, C.COLOR_BOSS)
        text.set_alpha(int(255 * ratio))
        self.screen.blit(text, text.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 250)))

    def _render_damage_numbers(self, ox=0, oy=0):
        for dn in self.damage_numbers:
            ratio = dn["timer"] / dn["max_timer"]
            rise = (1 - ratio) * 22
            surf = self.font.render(dn["text"], True, dn["color"])
            surf.set_alpha(int(255 * ratio))
            center = (
                int(dn["x"] * C.TILE_SIZE + C.TILE_SIZE // 2 + ox),
                int(dn["y"] * C.TILE_SIZE + C.TILE_SIZE // 2 + oy - rise),
            )
            self.screen.blit(surf, surf.get_rect(center=center))

    def _render_map(self, ox=0, oy=0):
        for y in range(C.MAP_HEIGHT):
            for x in range(C.MAP_WIDTH):
                if (x, y) not in self.explored:
                    continue
                is_visible = (x, y) in self.visible
                if self.grid[y][x] == dungeon.WALL:
                    color = C.COLOR_WALL if is_visible else C.COLOR_WALL_DIM
                else:
                    color = C.COLOR_FLOOR if is_visible else C.COLOR_FLOOR_DIM
                rect = (x * C.TILE_SIZE + ox, y * C.TILE_SIZE + oy, C.TILE_SIZE, C.TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)

        if self.stairs_pos in self.explored:
            self._draw_char(">", *self.stairs_pos, C.COLOR_STAIRS, ox, oy)

    def _render_entities(self, ox=0, oy=0):
        for item in self.items:
            if (item.x, item.y) in self.visible:
                self._draw_char(item.char, item.x, item.y, item.color, ox, oy)

        for merchant in self.merchants:
            if (merchant.x, merchant.y) in self.visible:
                self._draw_char(merchant.char, merchant.x, merchant.y, merchant.color, ox, oy)

        for monster in self.monsters:
            if (monster.x, monster.y) in self.visible:
                self._draw_monster(monster, ox, oy)
                self._record_bestiary(monster.kind)

        self._draw_player(ox, oy)

    def _draw_player(self, ox=0, oy=0):
        sprite = self.player_sprite_left if self.player.facing < 0 else self.player_sprite_right
        if sprite is None:
            self._draw_char(self.player.char, self.player.render_x, self.player.render_y, self.player.color, ox, oy)
            return

        tile_center_x = self.player.render_x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox
        tile_bottom_y = self.player.render_y * C.TILE_SIZE + C.TILE_SIZE + oy
        rect = sprite.get_rect(midbottom=(int(tile_center_x), int(tile_bottom_y) + 2))
        self.screen.blit(sprite, rect)

    def _draw_monster(self, monster, ox=0, oy=0):
        variants = self.monster_sprites.get(monster.kind)
        if variants is None:
            self._draw_char(monster.char, monster.render_x, monster.render_y, monster.color, ox, oy)
            return
        sprite = variants[1] if monster.facing < 0 else variants[0]

        scale = 1.0
        if monster.is_boss:
            scale = C.BOSS_SPRITE_SCALE
        elif monster.is_split_child:
            scale = C.SPLIT_CHILD_SPRITE_SCALE
        if scale != 1.0:
            w, h = sprite.get_size()
            sprite = pygame.transform.smoothscale(sprite, (max(1, int(w * scale)), max(1, int(h * scale))))

        tile_center_x = monster.render_x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox
        tile_bottom_y = monster.render_y * C.TILE_SIZE + C.TILE_SIZE + oy
        rect = sprite.get_rect(midbottom=(int(tile_center_x), int(tile_bottom_y) + 2))

        if monster.elite_name:
            # Soft colour-matched halo (same blended colour already used
            # for the elite's HP/name tint) instead of recolouring the
            # sprite itself - cheap and reads as "special" at a glance.
            glow = pygame.Surface((int(sprite.get_width() * 1.3), int(sprite.get_height() * 1.3)), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*monster.color, 100), glow.get_rect())
            self.screen.blit(glow, glow.get_rect(center=rect.center))

        self.screen.blit(sprite, rect)

    def _draw_char(self, char, x, y, color, ox=0, oy=0):
        surf = self.font.render(char, True, color)
        center = (
            int(x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox),
            int(y * C.TILE_SIZE + C.TILE_SIZE // 2 + oy),
        )
        rect = surf.get_rect(center=center)
        self.screen.blit(surf, rect)

    def _render_flash(self):
        if self.flash_timer <= 0:
            return
        overlay = pygame.Surface((C.MAP_WIDTH * C.TILE_SIZE, C.MAP_HEIGHT * C.TILE_SIZE))
        overlay.set_alpha(int(90 * (self.flash_timer / 6)))
        overlay.fill((200, 30, 30))
        self.screen.blit(overlay, (C.MAP_OFFSET_X, 0))

    def _render_hud(self):
        hud_y = C.MAP_HEIGHT * C.TILE_SIZE
        pygame.draw.rect(self.screen, C.COLOR_HUD_BG, (0, hud_y, C.SCREEN_WIDTH, C.HUD_HEIGHT))

        # Content stays aligned under the map itself (offset by the same
        # gutter width), not spread across the full HUD strip - the gutters
        # below the D-pad/action buttons stay empty here, which is fine
        # since they visually "belong" to those buttons above.
        ox = C.MAP_OFFSET_X

        bar_width, bar_height = 180, 16
        pygame.draw.rect(self.screen, C.COLOR_HP_BAR_BG, (ox + 10, hud_y + 10, bar_width, bar_height))
        hp_ratio = max(0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(
            self.screen, C.COLOR_HP_BAR_FG, (ox + 10, hud_y + 10, int(bar_width * hp_ratio), bar_height)
        )
        hp_text = self.font.render(f"HP {max(0, self.player.hp)}/{self.player.max_hp}", True, C.COLOR_HUD_TEXT)
        self.screen.blit(hp_text, (ox + 200, hud_y + 8))

        xp_bar_x = ox + 340
        pygame.draw.rect(self.screen, C.COLOR_XP_BAR_BG, (xp_bar_x, hud_y + 10, bar_width, bar_height))
        xp_ratio = self.player.xp / self.player.xp_to_next
        pygame.draw.rect(
            self.screen, C.COLOR_XP_BAR_FG, (xp_bar_x, hud_y + 10, int(bar_width * xp_ratio), bar_height)
        )
        xp_text = self.font.render(
            f"Lv {self.player.level}  XP {self.player.xp}/{self.player.xp_to_next}", True, C.COLOR_HUD_TEXT
        )
        self.screen.blit(xp_text, (xp_bar_x + bar_width + 10, hud_y + 8))

        # Two-column icon+label overview instead of one dense wall of text -
        # left column is equipment, right column is resources. Icons reuse
        # the same glyph+colour already used for these items on the map,
        # so the legend is consistent everywhere.
        left_x, right_x = ox + 10, ox + 340
        row_y = hud_y + 34
        row_h = 18

        self._hud_icon_row(left_x, row_y, "/", (215, 215, 230),
                            f"{self.tn(self.player.weapon_name)} (+{self.player.weapon_bonus})")
        self._hud_icon_row(right_x, row_y, "!", C.COLOR_POTION,
                            f"{self.t('hud_potions')} {self.player.potions}")

        self._hud_icon_row(left_x, row_y + row_h, "[", (170, 170, 185),
                            f"{self.tn(self.player.armor_name)} (+{self.player.armor_bonus})")
        self._hud_icon_row(right_x, row_y + row_h, "$", C.COLOR_GOLD,
                            f"{self.t('hud_gold')} {self.player.gold}")

        dlvl_text = self.font.render(f"Dungeon Lv {self.dungeon_level}", True, C.COLOR_HUD_TEXT)
        self.screen.blit(dlvl_text, (left_x, row_y + 2 * row_h))
        kills_text = self.font.render(f"{self.t('hud_kills')} {self.player.kills}", True, C.COLOR_HUD_TEXT)
        self.screen.blit(kills_text, (right_x, row_y + 2 * row_h))

        scrolls = self.player.scrolls
        scroll_line = (
            f"{self.t('hud_scrolls_label')} Fire(F):{scrolls['fireball']}  Teleport(T):{scrolls['teleport']}  "
            f"Reveal(V):{scrolls['reveal']}    {self.t('hud_menu_hint')}"
        )
        poison_suffix = f"    {self.t('hud_poisoned')}" if self.player.poison_turns > 0 else ""
        scroll_color = C.COLOR_POISON if self.player.poison_turns > 0 else C.COLOR_HELP_TEXT
        self.screen.blit(self.font.render(scroll_line + poison_suffix, True, scroll_color), (ox + 10, hud_y + 92))

        for i, message in enumerate(self.log[-4:]):
            msg_surf = self.font.render(message, True, C.COLOR_LOG_TEXT)
            self.screen.blit(msg_surf, (ox + 10, hud_y + 112 + i * 16))

    def _hud_icon_row(self, x, y, char, color, text):
        icon = self.font.render(char, True, color)
        self.screen.blit(icon, (x, y))
        label = self.font.render(text, True, C.COLOR_HUD_TEXT)
        self.screen.blit(label, (x + 16, y))

    def _draw_touch_button(self, rect, label, active=False):
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill = (90, 90, 110, 170) if active else (40, 40, 50, 130)
        overlay.fill(fill)
        self.screen.blit(overlay, rect.topleft)
        pygame.draw.rect(self.screen, (150, 150, 170, 200), rect, width=2, border_radius=6)
        text = self.font.render(label, True, C.COLOR_HUD_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _render_touch_controls(self):
        # The menu button is the only touch path to the pause menu (and
        # from there, to re-enabling everything else), so it always draws
        # regardless of show_touch_controls - only the movement/action
        # buttons are optional.
        self._draw_touch_button(self.save_button, self.t("touch_menu"))
        if not self.settings.get("show_touch_controls", True):
            return
        for name, (rect, vector, label) in self.dpad_buttons.items():
            self._draw_touch_button(rect, label, active=(self.touch_direction == vector))
        self._draw_touch_button(self.potion_button, self.t("touch_heal"))
        scroll_labels = {"fireball": "F", "teleport": "T", "reveal": "V"}
        for name, rect in self.scroll_buttons.items():
            self._draw_touch_button(rect, scroll_labels[name])

    def _render_game_over(self):
        self._tap_targets = []
        overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        overlay.set_alpha(210)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        text = self.big_font.render(self.t("gameover_title"), True, (200, 40, 40))
        rect = text.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 60))
        self.screen.blit(text, rect)

        best_line = self.t("gameover_best")
        lines = [
            self.t("gameover_summary", level=self.dungeon_level, kills=self.player.kills, clevel=self.player.level),
        ]
        if self.new_best:
            lines.append(best_line)

        for i, line in enumerate(lines):
            color = (255, 215, 0) if line == best_line else C.COLOR_HUD_TEXT
            surf = self.font.render(line, True, color)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 10 + i * 28))
            self.screen.blit(surf, r)

        button_y = C.SCREEN_HEIGHT // 2 - 10 + len(lines) * 28 + 20
        cx = C.SCREEN_WIDTH // 2
        self._draw_tap_button((cx - 235, button_y, 150, 44), self.t("btn_restart"), pygame.K_r)
        self._draw_tap_button((cx - 75, button_y, 150, 44), self.t("btn_stats"), pygame.K_s)
        self._draw_tap_button((cx + 85, button_y, 150, 44), self.t("btn_quit"), pygame.K_ESCAPE)
