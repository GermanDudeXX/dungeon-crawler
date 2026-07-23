import random
import sys

import pygame

import constants as C
import dungeon
import entities
import fov
import persistence
import sound

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
        self.screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.big_font = pygame.font.SysFont("consolas", 40, bold=True)
        self.sounds = sound.Sounds()
        self.stats = persistence.load_stats()
        self.save_data = persistence.load_save()
        self.player_sprite_right, self.player_sprite_left, self.player_sprite_large = self._load_player_sprite()
        self.state = "title"
        self.stats_return_state = "title"
        self.new_best = False
        self.touch_direction = None
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

    def _setup_touch_controls(self):
        s, g = 44, 6
        dpad_cx, dpad_cy = 875, 520
        self.dpad_buttons = {
            "up": (pygame.Rect(dpad_cx - s // 2, dpad_cy - s - g, s, s), (0, -1), "^"),
            "down": (pygame.Rect(dpad_cx - s // 2, dpad_cy + g, s, s), (0, 1), "v"),
            "left": (pygame.Rect(dpad_cx - s - g - s // 2, dpad_cy - s // 2, s, s), (-1, 0), "<"),
            "right": (pygame.Rect(dpad_cx + g + s // 2, dpad_cy - s // 2, s, s), (1, 0), ">"),
        }
        self.potion_button = pygame.Rect(712, 492, 56, 56)
        self.save_button = pygame.Rect(895, 8, 58, 30)

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
        self.new_level()
        self.add_log("You descend into the dungeon.")
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
        self.player = player

        self.grid = data["grid"]
        self.stairs_pos = tuple(data["stairs_pos"])
        self.explored = {tuple(t) for t in data["explored"]}

        self.monsters = []
        for m in data["monsters"]:
            monster = entities.Monster(m["x"], m["y"], m["kind"], boss=m["boss"])
            monster.hp = m["hp"]
            monster.awake = m["awake"]
            self.monsters.append(monster)

        self.items = []
        for i in data["items"]:
            self.items.append(
                entities.Item(i["x"], i["y"], i["kind"], i["name"], i["char"], tuple(i["color"]), bonus=i["bonus"])
            )

        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_repeat_timer = 0
        self.move_held = False
        self.new_best = False

        self._recompute_fov()
        self.add_log("You continue your descent.")
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
            },
            "grid": self.grid,
            "stairs_pos": list(self.stairs_pos),
            "explored": [list(t) for t in self.explored],
            "monsters": [
                {"x": m.x, "y": m.y, "kind": m.kind, "boss": m.is_boss, "hp": m.hp, "awake": m.awake}
                for m in self.monsters
            ],
            "items": [
                {"x": i.x, "y": i.y, "kind": i.kind, "name": i.name, "char": i.char,
                 "color": list(i.color), "bonus": i.bonus}
                for i in self.items
            ],
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
        self._populate_level()

        self._recompute_fov()

    def _populate_level(self):
        monster_kinds = list(C.MONSTER_TYPES.keys())
        weights = [3, 2 if self.dungeon_level >= 2 else 0.2, 1 if self.dungeon_level >= 3 else 0.05]
        num_monsters = min(2 + self.dungeon_level, 12)

        spawnable_rooms = self.rooms[1:] or self.rooms

        for _ in range(num_monsters):
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if not self._is_occupied(x, y):
                kind = random.choices(monster_kinds, weights=weights, k=1)[0]
                self.monsters.append(entities.Monster(x, y, kind))

        if self.dungeon_level % 5 == 0:
            bx, by = self.stairs_pos
            self.monsters.append(entities.Monster(bx, by, "orc", boss=True))
            self.add_log("A powerful presence guards the stairs...")
            self.sounds.play("boss")

        for _ in range(random.randint(1, 3)):
            self._spawn_item(random.choice(spawnable_rooms), "potion")
        if random.random() < 0.7:
            self._spawn_item(random.choice(spawnable_rooms), "weapon")
        if random.random() < 0.7:
            self._spawn_item(random.choice(spawnable_rooms), "armor")

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

    def _random_floor_in_room(self, room):
        x = random.randint(room.x1, room.x2 - 1)
        y = random.randint(room.y1, room.y2 - 1)
        return x, y

    def _is_occupied(self, x, y):
        if (x, y) == (self.player.x, self.player.y):
            return True
        return any((m.x, m.y) == (x, y) for m in self.monsters)

    def _recompute_fov(self):
        self.visible = fov.compute_fov(self.grid, self.player.x, self.player.y, C.FOV_RADIUS)
        self.explored |= self.visible

    def add_log(self, message):
        self.log.append(message)
        self.log = self.log[-5:]

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

    def _handle_tap(self, pos):
        if self.state == "stats":
            self.state = self.stats_return_state
            return

        if self.state in ("title", "dead"):
            for rect, key in self._tap_targets:
                if rect.collidepoint(pos):
                    self._handle_key(key)
                    return
            return

        if self.state != "playing":
            return

        if self.save_button.collidepoint(pos):
            self._save_and_quit()
            return
        if self.potion_button.collidepoint(pos):
            self._drink_potion()
            return
        for rect, vector, _label in self.dpad_buttons.values():
            if rect.collidepoint(pos):
                self.touch_direction = vector
                return

    def _handle_key(self, key):
        if self.state == "stats":
            self.state = self.stats_return_state
            return

        if self.state == "title":
            if key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            elif key == pygame.K_s:
                self.stats_return_state = "title"
                self.state = "stats"
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

        if key == pygame.K_ESCAPE:
            self._save_and_quit()
        elif key == pygame.K_g:
            self._drink_potion()

    def _player_turn(self, dx, dy):
        if dx != 0:
            self.player.facing = 1 if dx > 0 else -1

        target_x, target_y = self.player.x + dx, self.player.y + dy

        target_monster = next(
            (m for m in self.monsters if m.x == target_x and m.y == target_y), None
        )
        if target_monster:
            self._attack(self.player, target_monster)
        elif dungeon.is_walkable(self.grid, target_x, target_y):
            self.player.move(dx, dy)
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

    def _advance_level(self):
        self.dungeon_level += 1
        self.add_log(f"You descend to level {self.dungeon_level}.")
        self.sounds.play("stairs")
        self.new_level()

    def _collect_item(self, item):
        if item.kind == "potion":
            self.player.potions += 1
            self.add_log(f"You pick up a {item.name}.")
            self.sounds.play("pickup")
        elif item.kind == "weapon":
            if item.bonus > self.player.weapon_bonus:
                self.player.weapon_bonus = item.bonus
                self.player.weapon_name = item.name
                self.add_log(f"You equip the {item.name} (+{item.bonus} power).")
                self.sounds.play("equip")
            else:
                self.add_log(f"You find a {item.name}, but your {self.player.weapon_name} is better.")
        elif item.kind == "armor":
            if item.bonus > self.player.armor_bonus:
                self.player.armor_bonus = item.bonus
                self.player.armor_name = item.name
                self.add_log(f"You equip the {item.name} (+{item.bonus} defense).")
                self.sounds.play("equip")
            else:
                self.add_log(f"You find a {item.name}, but your {self.player.armor_name} is better.")
        self.items.remove(item)

    def _drink_potion(self):
        if self.player.potions <= 0:
            self.add_log("You have no potions.")
            return
        if self.player.hp >= self.player.max_hp:
            self.add_log("You are already at full health.")
            return

        healed = min(15, self.player.max_hp - self.player.hp)
        self.player.potions -= 1
        self.player.hp += healed
        self.stats["total_potions_drunk"] += 1
        self.add_log(f"You drink a potion and heal {healed} HP.")
        self.sounds.play("pickup")
        self._enemy_turn()

    def _attack(self, attacker, defender):
        damage = max(1, attacker.power - defender.defense)
        defender.hp -= damage
        attacker_name = "You" if attacker is self.player else f"The {attacker.name}"
        defender_name = "you" if defender is self.player else f"the {defender.name}"
        self.add_log(f"{attacker_name} hit {defender_name} for {damage}.")

        if attacker is self.player:
            self.sounds.play("hit")
        else:
            self.sounds.play("player_hurt")
            self.shake_timer = 6
            self.shake_intensity = 4
            self.flash_timer = 6

        if defender.hp <= 0:
            if defender is self.player:
                self.add_log("You have died.")
                self.sounds.play("death")
                self.state = "dead"
                self._finalize_run()
            else:
                self.add_log(f"The {defender.name} dies. (+{defender.xp_reward} XP)")
                self.sounds.play("monster_death")
                self.monsters.remove(defender)
                self.player.kills += 1
                self._record_kill(defender)
                if self.player.gain_xp(defender.xp_reward):
                    self.add_log(f"You reach level {self.player.level}!")
                    self.sounds.play("levelup")

    def _record_kill(self, monster):
        key = "boss" if monster.is_boss else monster.kind
        self.stats["kills_by_monster"][key] = self.stats["kills_by_monster"].get(key, 0) + 1
        self.stats["total_kills"] += 1

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
                monster.awake = True
            if not monster.awake:
                continue

            dx = self.player.x - monster.x
            dy = self.player.y - monster.y
            if abs(dx) <= 1 and abs(dy) <= 1 and (dx, dy) != (0, 0):
                self._attack(monster, self.player)
                if self.state == "dead":
                    return
                continue

            step_x = (dx > 0) - (dx < 0)
            step_y = (dy > 0) - (dy < 0)
            self._move_monster_toward(monster, step_x, step_y)

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
        if self.shake_timer <= 0:
            return 0, 0
        return (
            random.randint(-self.shake_intensity, self.shake_intensity),
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

        self.screen.fill(C.COLOR_BG)
        ox, oy = self._shake_offset()
        self._render_map(ox, oy)
        self._render_entities(ox, oy)
        self._render_flash()
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
            "Move: WASD / Arrow keys / on-screen D-pad      Attack: walk into enemy",
            "Drink potion: G / HEAL button      Save & quit: ESC / SAVE button      Stats: S",
            "",
            f"Deepest level: {self.stats['deepest_level_ever']}      Most kills in a run: {self.stats['most_kills_in_a_run']}",
            "",
        ]
        if self.save_data:
            saved_level = self.save_data["dungeon_level"]
            saved_char_level = self.save_data["player"]["level"]
            lines.append(f"Dungeon Lv {saved_level}, Character Lv {saved_char_level} saved")

        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 + 20 + i * 26))
            self.screen.blit(surf, r)

        button_y = C.SCREEN_HEIGHT // 2 + 20 + len(lines) * 26 + 14
        cx = C.SCREEN_WIDTH // 2
        if self.save_data:
            self._draw_tap_button((cx - 160, button_y, 150, 44), "CONTINUE", pygame.K_RETURN)
            self._draw_tap_button((cx + 10, button_y, 150, 44), "NEW RUN", pygame.K_n)
            self._draw_tap_button((cx - 75, button_y + 54, 150, 44), "STATS", pygame.K_s)
        else:
            self._draw_tap_button((cx - 75, button_y, 150, 44), "START", pygame.K_RETURN)
            self._draw_tap_button((cx - 75, button_y + 54, 150, 44), "STATS", pygame.K_s)

    def _render_stats(self):
        self.screen.fill(C.COLOR_BG)
        title = self.big_font.render("STATISTICS", True, (230, 200, 60))
        rect = title.get_rect(center=(C.SCREEN_WIDTH // 2, 90))
        self.screen.blit(title, rect)

        s = self.stats
        kb = s["kills_by_monster"]
        lines = [
            f"Runs played: {s['games_played']}      Deaths: {s['deaths']}",
            "",
            f"Deepest level reached: {s['deepest_level_ever']}",
            f"Most kills in a single run: {s['most_kills_in_a_run']}",
            f"Highest character level: {s['highest_character_level']}",
            f"Potions drunk: {s['total_potions_drunk']}",
            "",
            f"Total kills: {s['total_kills']}",
            f"Rats: {kb.get('rat', 0)}   Goblins: {kb.get('goblin', 0)}   "
            f"Orcs: {kb.get('orc', 0)}   Bosses: {kb.get('boss', 0)}",
            "",
            "Press any key or tap BACK to go back",
        ]
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C.COLOR_HUD_TEXT)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, 180 + i * 30))
            self.screen.blit(surf, r)

        back_rect = pygame.Rect(C.SCREEN_WIDTH // 2 - 75, 180 + len(lines) * 30 + 10, 150, 44)
        pygame.draw.rect(self.screen, (45, 45, 58), back_rect, border_radius=8)
        pygame.draw.rect(self.screen, (130, 130, 150), back_rect, width=2, border_radius=8)
        back_text = self.font.render("BACK", True, C.COLOR_HUD_TEXT)
        self.screen.blit(back_text, back_text.get_rect(center=back_rect.center))

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

        for monster in self.monsters:
            if (monster.x, monster.y) in self.visible:
                self._draw_char(monster.char, monster.render_x, monster.render_y, monster.color, ox, oy)

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
        self.screen.blit(overlay, (0, 0))

    def _render_hud(self):
        hud_y = C.MAP_HEIGHT * C.TILE_SIZE
        pygame.draw.rect(self.screen, C.COLOR_HUD_BG, (0, hud_y, C.SCREEN_WIDTH, C.HUD_HEIGHT))

        bar_width, bar_height = 180, 16
        pygame.draw.rect(self.screen, C.COLOR_HP_BAR_BG, (10, hud_y + 10, bar_width, bar_height))
        hp_ratio = max(0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(
            self.screen, C.COLOR_HP_BAR_FG, (10, hud_y + 10, int(bar_width * hp_ratio), bar_height)
        )
        hp_text = self.font.render(f"HP {max(0, self.player.hp)}/{self.player.max_hp}", True, C.COLOR_HUD_TEXT)
        self.screen.blit(hp_text, (200, hud_y + 8))

        xp_bar_x = 340
        pygame.draw.rect(self.screen, C.COLOR_XP_BAR_BG, (xp_bar_x, hud_y + 10, bar_width, bar_height))
        xp_ratio = self.player.xp / self.player.xp_to_next
        pygame.draw.rect(
            self.screen, C.COLOR_XP_BAR_FG, (xp_bar_x, hud_y + 10, int(bar_width * xp_ratio), bar_height)
        )
        xp_text = self.font.render(
            f"Lv {self.player.level}  XP {self.player.xp}/{self.player.xp_to_next}", True, C.COLOR_HUD_TEXT
        )
        self.screen.blit(xp_text, (xp_bar_x + bar_width + 10, hud_y + 8))

        line_a = (
            f"Dungeon Lv {self.dungeon_level}    Weapon: {self.player.weapon_name} (+{self.player.weapon_bonus})"
            f"    Armor: {self.player.armor_name} (+{self.player.armor_bonus})"
        )
        line_b = f"Potions: {self.player.potions}    Kills: {self.player.kills}"
        self.screen.blit(self.font.render(line_a, True, C.COLOR_HUD_TEXT), (10, hud_y + 34))
        self.screen.blit(self.font.render(line_b, True, C.COLOR_HUD_TEXT), (10, hud_y + 54))

        help_text = self.font.render(
            "Move: WASD/Arrows/D-pad   Drink potion: G/HEAL   Save & quit: ESC/SAVE", True, C.COLOR_HELP_TEXT
        )
        self.screen.blit(help_text, (10, hud_y + 78))

        for i, message in enumerate(self.log):
            msg_surf = self.font.render(message, True, C.COLOR_LOG_TEXT)
            self.screen.blit(msg_surf, (10, hud_y + 100 + i * 18))

    def _draw_touch_button(self, rect, label, active=False):
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill = (90, 90, 110, 170) if active else (40, 40, 50, 130)
        overlay.fill(fill)
        self.screen.blit(overlay, rect.topleft)
        pygame.draw.rect(self.screen, (150, 150, 170, 200), rect, width=2, border_radius=6)
        text = self.font.render(label, True, C.COLOR_HUD_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _render_touch_controls(self):
        for name, (rect, vector, label) in self.dpad_buttons.items():
            self._draw_touch_button(rect, label, active=(self.touch_direction == vector))
        self._draw_touch_button(self.potion_button, "HEAL")
        self._draw_touch_button(self.save_button, "SAVE")

    def _render_game_over(self):
        self._tap_targets = []
        overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        overlay.set_alpha(210)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        text = self.big_font.render("YOU DIED", True, (200, 40, 40))
        rect = text.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 60))
        self.screen.blit(text, rect)

        lines = [
            f"Reached dungeon level {self.dungeon_level}   -   {self.player.kills} kills   -   Character level {self.player.level}",
        ]
        if self.new_best:
            lines.append("NEW BEST RUN!")

        for i, line in enumerate(lines):
            color = (255, 215, 0) if line == "NEW BEST RUN!" else C.COLOR_HUD_TEXT
            surf = self.font.render(line, True, color)
            r = surf.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2 - 10 + i * 28))
            self.screen.blit(surf, r)

        button_y = C.SCREEN_HEIGHT // 2 - 10 + len(lines) * 28 + 20
        cx = C.SCREEN_WIDTH // 2
        self._draw_tap_button((cx - 235, button_y, 150, 44), "RESTART", pygame.K_r)
        self._draw_tap_button((cx - 75, button_y, 150, 44), "STATS", pygame.K_s)
        self._draw_tap_button((cx + 85, button_y, 150, 44), "QUIT", pygame.K_ESCAPE)
