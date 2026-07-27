import os
import random
import sys
import threading

import pygame

import constants as C
import dungeon
import entities
import fov
import locale_text as loc
import persistence
import sound
import installer
import updater

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
# Auto-repeat timings in MILLISECONDS, deliberately not in frames. These
# used to be frame counts (12 and 6) evaluated against a 30fps target,
# which silently turned every framerate drop into input lag: measured on a
# real device at 3.9fps, the 6-frame repeat became a 1.5 SECOND wait per
# step. Wall-clock timing keeps the controls feeling identical no matter
# what the renderer manages.
MOVE_REPEAT_INITIAL_DELAY_MS = 400
MOVE_REPEAT_INTERVAL_MS = 200

# How often the loop spins, and so how quickly a touch can be noticed at
# all. The old loop ran at 30Hz, which alone put a ~33ms floor under every
# tap before any drawing happened; polling at 60Hz halves that. It is
# affordable now only because most iterations no longer redraw anything
# (see _should_redraw).
POLL_HZ = 60
# Frame-counted animation timers still advance at the original rate, so
# doubling the poll rate does not double animation speed.
TICK_INTERVAL_MS = 1000 // 30


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Dungeon Crawler")
        self.ui_scale = 1.0
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
        if not ON_ANDROID:
            # Desktop text/HUD/buttons were also sized for that same small
            # reference canvas and read as too small on a normal monitor -
            # a flat, modest bump (no device probing needed, the window is
            # exactly whatever size we request).
            self._apply_pc_ui_scale()
        self.display = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SCALED)
        if ON_ANDROID and self._fit_screen_to_device():
            # The window SDL actually created (queried below, now that one
            # exists) is smaller than pygame.display.Info()'s device
            # resolution by however much the status bar / nav buttons
            # reserve - confirmed on a real device via logcat ("Window
            # size: 2448x1098" vs "Device size: 2712x1220"). Recreate the
            # display now that constants.py reflects the *real* usable
            # size, so the logical canvas actually matches what's on
            # screen instead of being letterboxed inside it.
            self.display = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SCALED)
        # Everything draws into an ordinary in-RAM surface, which is copied
        # to the real display once per frame by _present(). Measured on a
        # real device: drawing straight into the pygame.SCALED display
        # surface cost 250ms/frame in gameplay (3.9 fps) while the flip
        # itself was only 5ms - i.e. the cost was the drawing, not the
        # present, and the same frame costs 2.3ms on desktop. That 100x
        # gap is the signature of the display surface living in
        # uncached/write-combined memory on Android, where every small
        # blit and read-modify-write (alpha blending especially) goes
        # across the bus. A plain Surface is normal cached RAM, so the
        # many small draws are fast again and only one large sequential
        # copy per frame touches the slow surface.
        # Explicitly 32-bit. Surface.convert() would instead match the
        # display's own format, and if SDL hands us a 24-bit display on
        # Android every pixel becomes an unaligned 3-byte access with no
        # SIMD fast path - which fits the measured ~20M px/s fill rate.
        self.screen = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), 0, 32)
        self.clock = pygame.time.Clock()
        # pygame.font.SysFont looks up a named font through the OS's font
        # system, which crashes on Android (no such font, no font-listing
        # tools like fc-list in the sandbox). pygame.font.Font(None, size)
        # uses pygame's own bundled default font instead - no OS lookup,
        # works identically on every platform.
        self.font = pygame.font.Font(None, int(18 * self.ui_scale))
        self.big_font = pygame.font.Font(None, int(40 * self.ui_scale))
        self.big_font.set_bold(True)
        self._build_ui_metrics()
        self.stats = persistence.load_stats()
        self.save_data = persistence.load_save()
        self.settings = persistence.load_settings()
        self.sounds = sound.Sounds(volume=self.settings.get("volume", sound.MASTER_VOLUME))
        self.player_sprite_right, self.player_sprite_left, self.player_sprite_large = self._load_player_sprite()
        self.monster_sprites = self._load_monster_sprites()
        self.item_sprites = self._load_item_sprites()
        self.ladder_sprite = self._load_scaled_sprite(C.LADDER_SPRITE_PATH, C.LADDER_SPRITE_HEIGHT)
        self.merchant_sprite = self._load_scaled_sprite(C.MERCHANT_SPRITE_PATH, C.MERCHANT_SPRITE_HEIGHT)
        self.needs_redraw = True
        self._last_draw_ms = 0
        self._last_tick_ms = 0
        # Running from Downloads/Desktop means Windows will block the
        # self-updater later, so offer to install properly first.
        self.state = "install_prompt" if installer.should_offer_install() else "title"
        # Start the track immediately instead of waiting for a run to
        # begin, so the menus have music too.
        self._play_tier_music(C.DUNGEON_TIERS[0])
        self.stats_return_state = "title"
        self.settings_return_state = "title"
        self.new_best = False
        self.touch_direction = None
        self.touch_warning_timer = 0
        self._tap_targets = []
        self._setup_touch_controls()

        self.install_phase = "prompt"
        self.install_error = None
        self.update_return_state = "settings"
        self.update_phase = "idle"
        self.update_info = None
        self.update_error = None
        self.update_progress = (0, 0)
        self._update_thread = None
        self._update_download_path = None

    def _apply_pc_ui_scale(self):
        self.ui_scale = 1.3
        map_pixel_height = C.MAP_HEIGHT * C.TILE_SIZE
        C.HUD_HEIGHT = int(190 * self.ui_scale)
        C.SCREEN_HEIGHT = map_pixel_height + C.HUD_HEIGHT
        # Widen the gutter too, in proportion - otherwise the now-bigger
        # D-pad (see _setup_touch_controls) would overflow past the edge
        # of the unchanged default gutter width.
        C.GUTTER_WIDTH = int(C.GUTTER_WIDTH * self.ui_scale)
        C.MAP_OFFSET_X = C.GUTTER_WIDTH
        C.SCREEN_WIDTH = C.MAP_PIXEL_WIDTH + 2 * C.GUTTER_WIDTH

    def _fit_screen_to_device(self):
        # pygame.display.Info() (used here previously) reports the full
        # Android *device* resolution, not the actual window SDL creates -
        # confirmed via logcat on a real phone: "Window size: 2448x1098"
        # vs "Device size: 2712x1220", a ~260x120px gap reserved by the
        # status bar and the 3-button nav row. Sizing our canvas off the
        # bigger device number left it letterboxed inside the smaller real
        # window. pygame.display.get_window_size() reads the window SDL
        # actually created, so it's only callable *after* the first
        # set_mode() call (see __init__, which creates a throwaway window,
        # calls this, then recreates the display at the corrected size).
        try:
            win_w, win_h = pygame.display.get_window_size()
        except pygame.error:
            return False
        if win_w <= 0 or win_h <= 0:
            return False

        # Pick the largest tile size the window can actually hold. The
        # tile size used to be a fixed 24px, which on this device left
        # the 40x25 map occupying only 960x600 of a 2448x1098 window -
        # 39% of the width - while the HUD band soaked up the rest. The
        # two constraints are the gutters (which must stay wide enough
        # for the touch controls) and the HUD band under the map.
        min_hud = 250
        by_width = (win_w - 2 * C.MIN_GUTTER_WIDTH) // C.MAP_WIDTH
        by_height = (win_h - min_hud) // C.MAP_HEIGHT
        tile = max(24, min(by_width, by_height))
        C.TILE_SIZE = tile
        C.MAP_PIXEL_WIDTH = C.MAP_WIDTH * tile
        self._rescale_tile_constants()

        map_pixel_height = C.MAP_HEIGHT * C.TILE_SIZE
        # Whatever vertical space the map leaves goes to the HUD, floored
        # at the original design height so a short window cannot squeeze
        # it away entirely.
        C.HUD_HEIGHT = max(190, win_h - map_pixel_height)
        C.SCREEN_HEIGHT = map_pixel_height + C.HUD_HEIGHT
        self.ui_scale = C.HUD_HEIGHT / 190

        device_ratio = win_w / win_h
        # Reject 0/garbage/portrait-shaped reads rather than ever
        # producing a broken layout - falls back to the static
        # GUTTER_WIDTH/SCREEN_WIDTH already set in constants.py.
        if 1.2 <= device_ratio <= 3.5:
            new_gutter = max(C.MIN_GUTTER_WIDTH, (win_w - C.MAP_PIXEL_WIDTH) // 2)
            C.GUTTER_WIDTH = new_gutter
            C.MAP_OFFSET_X = new_gutter
            C.SCREEN_WIDTH = C.MAP_PIXEL_WIDTH + 2 * new_gutter
        return True

    def _rescale_tile_constants(self):
        """Re-derive everything that was computed from the old TILE_SIZE.

        constants.py sizes the sprites relative to TILE_SIZE at import
        time, so changing the tile size afterwards has to recompute them -
        otherwise the art stays at the old scale and looks wrong on the
        larger tiles. Called before any sprite is loaded (see __init__).
        """
        t = C.TILE_SIZE
        C.PLAYER_SPRITE_HEIGHT = int(t * 1.8)
        C.MONSTER_SPRITE_HEIGHT = int(t * 1.5)
        C.ITEM_SPRITE_HEIGHT = int(t * 1.1)
        C.LADDER_SPRITE_HEIGHT = int(t * 1.3)
        C.MERCHANT_SPRITE_HEIGHT = int(t * 1.6)

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

    def _load_scaled_sprite(self, path, height):
        try:
            image = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None
        width = int(image.get_width() * (height / image.get_height()))
        return pygame.transform.smoothscale(image, (width, height))

    def _load_item_sprites(self):
        sprites = {}
        for kind in ("weapon", "armor", "potion", "scroll", "gold"):
            path = os.path.join(C.ITEM_SPRITE_DIR, f"{kind}.png")
            sprite = self._load_scaled_sprite(path, C.ITEM_SPRITE_HEIGHT)
            if sprite is not None:
                sprites[kind] = sprite
        return sprites

    def _setup_touch_controls(self):
        # Classic two-thumb mobile layout: movement bottom-left, actions
        # bottom-right, each fully inside its own side gutter (not overlaid
        # on the map view) so they never obscure the dungeon.
        #
        # Sizes come from the same metrics the menus use rather than from
        # self.ui_scale, which is derived from the HUD band height and so
        # made the controls shrink whenever the canvas geometry changed.
        # btn_h is >= Android's 48dp minimum by construction, and the D-pad
        # is additionally clamped to the gutter so it cannot spill onto the
        # map on a narrow (4:3 / 16:9) device.
        s = self.btn_h
        g = self.gap_s
        max_s = (C.GUTTER_WIDTH - 2 * self.gap_m - 2 * g) // 3
        s = max(self.gap_xl, min(s, max_s))

        # Anchor the whole cluster just above the HUD band so nothing
        # overlaps it: the cross reaches s/2 + g + s beyond its centre.
        map_bottom = C.MAP_HEIGHT * C.TILE_SIZE
        dpad_cx = C.GUTTER_WIDTH // 2
        dpad_cy = map_bottom - self.gap_m - (s // 2 + g + s)
        self.dpad_buttons = {
            "up": (pygame.Rect(dpad_cx - s // 2, dpad_cy - s - g, s, s), (0, -1), "^"),
            "down": (pygame.Rect(dpad_cx - s // 2, dpad_cy + g, s, s), (0, 1), "v"),
            "left": (pygame.Rect(dpad_cx - s - g - s // 2, dpad_cy - s // 2, s, s), (-1, 0), "<"),
            "right": (pygame.Rect(dpad_cx + g + s // 2, dpad_cy - s // 2, s, s), (1, 0), ">"),
        }

        right_edge = C.SCREEN_WIDTH - self.gap_m
        potion_size = min(int(s * 1.2), C.GUTTER_WIDTH - 2 * self.gap_m)
        potion_y = map_bottom - self.gap_m - potion_size
        self.potion_button = pygame.Rect(
            right_edge - potion_size, potion_y, potion_size, potion_size)

        scroll_size = max(self.gap_xl, min(s, (C.GUTTER_WIDTH - 2 * self.gap_m - 2 * g) // 3))
        scroll_y = potion_y - g - scroll_size
        row_w = 3 * scroll_size + 2 * g
        scroll_x = right_edge - row_w
        self.scroll_buttons = {
            "fireball": pygame.Rect(scroll_x, scroll_y, scroll_size, scroll_size),
            "teleport": pygame.Rect(scroll_x + scroll_size + g, scroll_y, scroll_size, scroll_size),
            "reveal": pygame.Rect(scroll_x + 2 * (scroll_size + g), scroll_y, scroll_size, scroll_size),
        }

        # Pinned to the top-right corner - the only touch route back to the
        # pause menu, so it stays visible even with the other controls off.
        menu_w = min(self._btn_w(self.t("touch_menu"), self.f_sm),
                     C.GUTTER_WIDTH - 2 * self.gap_m)
        self.save_button = pygame.Rect(
            C.SCREEN_WIDTH - self.gap_m - menu_w, self.gap_m, menu_w, self.btn_h)

    def start_new_run(self):
        persistence.delete_save()
        self.save_data = None

        self.dungeon_level = 1
        self.log = []
        self.player = entities.Player(0, 0)
        self.level_history = {}
        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_next_ms = 0
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
        player.weapon_rarity_id = p.get("weapon_rarity_id")
        player.weapon_element_id = p.get("weapon_element_id")
        player.armor_bonus = p["armor_bonus"]
        player.armor_name = p["armor_name"]
        player.armor_rarity_id = p.get("armor_rarity_id")
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
        player.bonus_damage_reduction = p.get("bonus_damage_reduction", 0.0)
        player.bonus_gold_mult = p.get("bonus_gold_mult", 0.0)
        player.bonus_elemental_chance = p.get("bonus_elemental_chance", 0.0)
        player.regen_interval = p.get("regen_interval")
        player.regen_counter = p.get("regen_counter", 0)
        self.player = player

        self.grid = data["grid"]
        self.tier = self._tier_for_level(self.dungeon_level)
        self._play_tier_music(self.tier)
        self.stairs_pos = tuple(data["stairs_pos"])
        up_stairs = data.get("up_stairs_pos")
        self.up_stairs_pos = tuple(up_stairs) if up_stairs else None
        self.explored = {tuple(t) for t in data["explored"]}
        self.traps = {tuple(int(v) for v in pos): kind for pos, kind in data.get("traps", [])}
        shrine = data.get("shrine_pos")
        self.shrine_pos = tuple(shrine) if shrine else None

        self.monsters = [self._deserialize_monster(m) for m in data["monsters"]]
        self.items = [self._deserialize_item(i) for i in data["items"]]
        self.merchants = [entities.Merchant(m["x"], m["y"]) for m in data.get("merchants", [])]
        self.level_history = {
            int(level): snapshot for level, snapshot in data.get("level_history", {}).items()
        }

        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_next_ms = 0
        self.move_held = False
        self.new_best = False
        self.damage_numbers = []
        self.boss_banner_timer = 0
        self.pending_perk_count = data.get("pending_perk_count", 0)
        by_id = {p["id"]: p for p in C.PERKS}
        self.perk_choices = [by_id[i] for i in data.get("perk_choices", []) if i in by_id]

        self._recompute_fov()
        self.add_log(self.t("log_continue_descent"))
        self.state = "playing"
        # Owed a perk from before the save - ask for it now.
        self._maybe_show_levelup_choice()

    def _build_save_data(self):
        p = self.player
        return {
            "dungeon_level": self.dungeon_level,
            "log": self.log,
            "player": {
                "x": p.x, "y": p.y, "hp": p.hp, "max_hp": p.max_hp,
                "base_power": p.base_power, "base_defense": p.base_defense,
                "weapon_bonus": p.weapon_bonus, "weapon_name": p.weapon_name,
                "weapon_rarity_id": p.weapon_rarity_id, "weapon_element_id": p.weapon_element_id,
                "armor_bonus": p.armor_bonus, "armor_name": p.armor_name,
                "armor_rarity_id": p.armor_rarity_id,
                "level": p.level, "xp": p.xp, "xp_to_next": p.xp_to_next,
                "potions": p.potions, "kills": p.kills, "facing": p.facing,
                "gold": p.gold, "scrolls": dict(p.scrolls), "poison_turns": p.poison_turns,
                "potions_drunk_this_run": p.potions_drunk_this_run,
                "bonus_crit_chance": p.bonus_crit_chance,
                "bonus_damage_reduction": p.bonus_damage_reduction,
                "bonus_gold_mult": p.bonus_gold_mult,
                "bonus_elemental_chance": p.bonus_elemental_chance,
                "regen_interval": p.regen_interval, "regen_counter": p.regen_counter,
            },
            "grid": self.grid,
            "stairs_pos": list(self.stairs_pos),
            "up_stairs_pos": list(self.up_stairs_pos) if self.up_stairs_pos else None,
            "explored": [list(t) for t in self.explored],
            "traps": [[list(pos), kind] for pos, kind in self.traps.items()],
            "shrine_pos": list(self.shrine_pos) if self.shrine_pos else None,
            # A level-up that has not been spent yet. Without this a
            # save & quit between levelling and picking silently threw the
            # perk away, permanently - the run just lost a bonus.
            "pending_perk_count": self.pending_perk_count,
            "perk_choices": [p["id"] for p in self.perk_choices],
            "monsters": [self._serialize_monster(m) for m in self.monsters],
            "items": [self._serialize_item(i) for i in self.items],
            "merchants": [{"x": m.x, "y": m.y} for m in self.merchants],
            "level_history": {str(level): snap for level, snap in self.level_history.items()},
        }

    @staticmethod
    def _serialize_monster(m):
        return {
            "x": m.x, "y": m.y, "kind": m.kind, "boss": m.is_boss, "hp": m.hp, "awake": m.awake,
            "elite_name": m.elite_name, "is_split_child": m.is_split_child, "enraged": m.enraged,
        }

    @staticmethod
    def _deserialize_monster(m):
        elite = None
        if m.get("elite_name"):
            elite = next((e for e in C.ELITE_MODIFIERS if e["name"] == m["elite_name"]), None)
        monster = entities.Monster(m["x"], m["y"], m["kind"], boss=m["boss"], elite=elite)
        monster.hp = m["hp"]
        monster.awake = m["awake"]
        monster.is_split_child = m.get("is_split_child", False)
        monster.enraged = m.get("enraged", False)
        if monster.enraged:
            monster.power = int(monster.power * 1.5)
        return monster

    @staticmethod
    def _serialize_item(i):
        return {
            "x": i.x, "y": i.y, "kind": i.kind, "name": i.name, "char": i.char,
            "color": list(i.color), "bonus": i.bonus, "scroll_type": i.scroll_type,
            "rarity_id": i.rarity_id, "element_id": i.element_id,
        }

    @staticmethod
    def _deserialize_item(i):
        return entities.Item(
            i["x"], i["y"], i["kind"], i["name"], i["char"], tuple(i["color"]),
            bonus=i["bonus"], scroll_type=i.get("scroll_type"), rarity_id=i.get("rarity_id"),
            element_id=i.get("element_id"),
        )

    def _snapshot_current_level(self):
        return {
            "grid": self.grid,
            "stairs_pos": list(self.stairs_pos),
            "up_stairs_pos": list(self.up_stairs_pos) if self.up_stairs_pos else None,
            "explored": [list(t) for t in self.explored],
            "traps": [[list(pos), kind] for pos, kind in self.traps.items()],
            "shrine_pos": list(self.shrine_pos) if self.shrine_pos else None,
            "monsters": [self._serialize_monster(m) for m in self.monsters],
            "items": [self._serialize_item(i) for i in self.items],
            "merchants": [{"x": m.x, "y": m.y} for m in self.merchants],
        }

    def _restore_level_snapshot(self, snap):
        self.grid = snap["grid"]
        self.tier = self._tier_for_level(self.dungeon_level)
        self._play_tier_music(self.tier)
        self.stairs_pos = tuple(snap["stairs_pos"])
        up_stairs = snap.get("up_stairs_pos")
        self.up_stairs_pos = tuple(up_stairs) if up_stairs else None
        self.explored = {tuple(t) for t in snap["explored"]}
        self.traps = {tuple(int(v) for v in pos): kind for pos, kind in snap.get("traps", [])}
        shrine = snap.get("shrine_pos")
        self.shrine_pos = tuple(shrine) if shrine else None
        self.monsters = [self._deserialize_monster(m) for m in snap["monsters"]]
        self.items = [self._deserialize_item(i) for i in snap["items"]]
        self.merchants = [entities.Merchant(m["x"], m["y"]) for m in snap.get("merchants", [])]

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
        # Every level except the first has a way back up, placed at this
        # level's own entry point - the same tile the player spawns on here
        # (see _advance_level/_ascend_level: descending always arrives at
        # up_stairs_pos, ascending always arrives at the level below's own
        # stairs_pos, so the two sides of every staircase line up).
        self.up_stairs_pos = self.rooms[0].center() if self.dungeon_level > 1 else None

        self.tier = self._tier_for_level(self.dungeon_level)
        self._play_tier_music(self.tier)

        self.monsters = []
        self.items = []
        self.merchants = []
        self.traps = {}
        self.shrine_pos = None
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
                self.monsters.append(entities.Monster(
                    x, y, kind, elite=self._maybe_elite(), tier_mult=self.tier["mult"]))

        if self.dungeon_level % 5 == 0:
            bx, by = self.stairs_pos
            tier = (self.dungeon_level // 5 - 1) % len(C.BOSS_KIND_CYCLE)
            boss_kind = C.BOSS_KIND_CYCLE[tier]
            self.monsters.append(entities.Monster(
                bx, by, boss_kind, boss=True, tier_mult=self.tier["mult"]))
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

        if self.dungeon_level >= 2 and random.random() < C.SHRINE_CHANCE_PER_LEVEL:
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            occupied_by_merchant = any((m.x, m.y) == (x, y) for m in self.merchants)
            if not self._is_occupied(x, y) and not occupied_by_merchant and (x, y) not in self.traps and (x, y) != self.stairs_pos:
                self.shrine_pos = (x, y)

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
            rarity = self._roll_rarity()
            bonus = max(w["bonus"], round(w["bonus"] * rarity["mult"]))
            element_id = None
            if self.dungeon_level >= C.ELEMENT_MIN_LEVEL and random.random() < C.ELEMENT_WEAPON_CHANCE:
                element_id = random.choice(list(C.ELEMENTS.keys()))
            self.items.append(entities.Item(
                x, y, "weapon", w["name"], "/", rarity["color"], bonus=bonus,
                rarity_id=rarity["id"], element_id=element_id,
            ))
        elif kind == "armor":
            tier_max = min(len(C.ARMOR_TYPES) - 1, self.dungeon_level // 2)
            a = C.ARMOR_TYPES[random.randint(0, tier_max)]
            rarity = self._roll_rarity()
            bonus = max(a["bonus"], round(a["bonus"] * rarity["mult"]))
            self.items.append(entities.Item(
                x, y, "armor", a["name"], "[", rarity["color"], bonus=bonus, rarity_id=rarity["id"]
            ))
        elif kind == "gold":
            amount = random.randint(5, 15) * self.dungeon_level
            self.items.append(entities.Item(x, y, "gold", "Gold", "$", C.COLOR_GOLD, bonus=amount))
        elif kind == "scroll":
            scroll_type = random.choice(list(C.SCROLL_TYPES.keys()))
            info = C.SCROLL_TYPES[scroll_type]
            self.items.append(
                entities.Item(x, y, "scroll", info["name"], info["char"], info["color"], scroll_type=scroll_type)
            )

    def _roll_rarity(self):
        available = [t for t in C.RARITY_TIERS if t["min_level"] <= self.dungeon_level]
        return random.choices(available, weights=[t["weight"] for t in available], k=1)[0]

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
        # The cached tile surface is painted from exactly these two sets
        # (see _rebuild_map_cache), so this is the single place that has
        # to invalidate it - every map/level change routes through here.
        self._map_cache = None
        self.needs_redraw = True

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

    def tr(self, rarity_id):
        if not rarity_id:
            return ""
        tier = C.RARITY_BY_ID.get(rarity_id)
        if tier is None:
            return ""
        if self._lang() == "de":
            return loc.RARITY_DE.get(tier["name"], tier["name"])
        return tier["name"]

    def te(self, element_id):
        if not element_id:
            return ""
        elem = C.ELEMENTS.get(element_id)
        if elem is None:
            return ""
        if self._lang() == "de":
            return loc.ELEMENT_DE.get(elem["name"], elem["name"])
        return elem["name"]

    def _tier_for_level(self, level):
        """The theme and difficulty multiplier for a dungeon level.

        Themes cycle once the list is exhausted, but the multiplier keeps
        climbing by TIER_CYCLE_MULT per full cycle so floor 51 is harder
        than floor 1 rather than looping back to the same difficulty.
        """
        index = max(0, (level - 1) // C.LEVELS_PER_TIER)
        cycle, within = divmod(index, len(C.DUNGEON_TIERS))
        tier = dict(C.DUNGEON_TIERS[within])
        tier["mult"] = C.TIER_GROWTH ** index
        tier["cycle"] = cycle
        tier["index"] = index
        return tier

    def _tier_name(self, tier):
        if self._lang() == "de":
            name = loc.TIER_DE.get(tier["id"], tier["name"])
        else:
            name = tier["name"]
        # Second time through the themes, mark it so the repeat reads as
        # deliberate escalation rather than a bug.
        return f"{name} +{tier['cycle']}" if tier.get("cycle") else name

    def _play_tier_music(self, tier):
        """Switch the looping background track when the theme changes."""
        if not self.settings.get("music", True):
            return
        track = tier.get("music")
        if not track or track == getattr(self, "_music_track", None):
            return
        path = os.path.join(C.MUSIC_DIR, track)
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            pygame.mixer.music.set_volume(
                self.settings.get("volume", sound.MASTER_VOLUME))
            self._music_track = track
        except (pygame.error, FileNotFoundError):
            # Deliberately do NOT record the track here. Doing so made a
            # single failed load permanent: the guard above then matched
            # forever and nothing retried, which is why music only ever
            # started after toggling it off and on again (that path resets
            # _music_track). Leaving it unset lets _music_watchdog retry.
            self._music_track = None

    def _music_watchdog(self):
        """Restart the track if it should be playing but is not.

        Covers a load or a device audio focus change failing transiently -
        previously any such hiccup meant silence until the player found
        the settings toggle. Cheap: one get_busy() call per second.
        """
        if not self.settings.get("music", True):
            return
        now = pygame.time.get_ticks()
        if now - getattr(self, "_music_check_ms", 0) < 1000:
            return
        self._music_check_ms = now
        try:
            if pygame.mixer.music.get_busy():
                return
        except pygame.error:
            return
        self._music_track = None
        self._play_tier_music(getattr(self, "tier", None) or C.DUNGEON_TIERS[0])

    def _build_ui_metrics(self):
        # Absolute sizes for the menu screens, scaled from the canvas
        # height so a desktop window or a low-res phone stays in
        # proportion. See constants.UI_REF_HEIGHT for the reference.
        k = C.SCREEN_HEIGHT / C.UI_REF_HEIGHT
        if not ON_ANDROID:
            k *= C.UI_DESKTOP_FACTOR
        floor = 120 if ON_ANDROID else 0   # keep a real touch target on phones

        def px(n, minimum=0):
            return max(minimum, int(round(n * k)))

        self.f_title = pygame.font.Font(None, px(C.FONT_TITLE))
        self.f_title.set_bold(True)
        self.f_h1 = pygame.font.Font(None, px(C.FONT_H1))
        self.f_h1.set_bold(True)
        self.f_body = pygame.font.Font(None, px(C.FONT_BODY))
        self.f_sm = pygame.font.Font(None, px(C.FONT_SM))
        self.f_xs = pygame.font.Font(None, px(C.FONT_XS))

        self.btn_h = px(C.BTN_H, floor)
        self.btn_h_hero = px(C.BTN_H_HERO, floor)
        self.btn_min_w = px(C.BTN_MIN_W)
        self.btn_pad_x = px(C.BTN_PAD_X)
        self.tap_slop = px(C.BTN_TAP_SLOP)
        # Must exceed the tap slop, or two stacked buttons' inflated hit
        # areas overlap and a near-miss fires the wrong one.
        self.btn_gap = max(px(C.BTN_GAP), self.tap_slop + px(6))
        self.pad = px(C.PAD)
        self.gap_s, self.gap_m = px(C.GAP_S), px(C.GAP_M)
        self.gap_l, self.gap_xl = px(C.GAP_L), px(C.GAP_XL)
        # Line pitches derived from the fonts themselves rather than
        # guessed, so changing a font can't silently start overlapping.
        self.pitch_body = self.f_body.get_linesize() + px(8)
        self.pitch_sm = self.f_sm.get_linesize() + px(6)
        self.pitch_xs = self.f_xs.get_linesize() + px(5)
        self.content_w = C.SCREEN_WIDTH - 2 * self.pad

    def _btn_w(self, label, font=None):
        """Width a button needs for its label, never below the minimum."""
        f = font or self.f_body
        return max(self.btn_min_w, f.size(label)[0] + 2 * self.btn_pad_x)

    def _button_row(self, entries, y, height=None, font=None):
        """Lay out (label, key) buttons left-to-right as one centred row.

        Widths come from the measured label, so a longer translation
        widens its own button instead of being clipped.
        """
        f = font or self.f_body
        h = height or self.btn_h
        widths = [self._btn_w(label, f) for label, _ in entries]
        total = sum(widths) + self.btn_gap * (len(entries) - 1)
        x = C.SCREEN_WIDTH // 2 - total // 2
        for (label, key), w in zip(entries, widths):
            self._draw_tap_button((x, y, w, h), label, key, font=f)
            x += w + self.btn_gap
        return h

    def _screen_header(self, title, color=(230, 200, 60), y=None):
        """Draw a screen title at the top; returns the y below it."""
        y = self.pad if y is None else y
        surf = self.f_title.render(title, True, color)
        self.screen.blit(surf, surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        return y + surf.get_height() + self.gap_m

    def _lines_block(self, lines, y, font=None, pitch=None, color=None, x=None):
        """Draw centred (or left-aligned when x is given) lines.

        An empty string is a group gap rather than a full blank row.
        Returns the y below the block.
        """
        f = font or self.f_body
        p = pitch or self.pitch_body
        col = color or C.COLOR_HUD_TEXT
        for line in lines:
            if line:
                surf = f.render(line, True, col)
                if x is None:
                    self.screen.blit(surf, surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
                else:
                    self.screen.blit(surf, (x, y))
                y += p
            else:
                y += self.gap_m
        return y

    def _toggle_music(self):
        on = not self.settings.get("music", True)
        self.settings["music"] = on
        persistence.save_settings(self.settings)
        if on:
            # Forget the current track so _play_tier_music actually
            # restarts it rather than treating it as already playing.
            self._music_track = None
            self._play_tier_music(getattr(self, "tier", C.DUNGEON_TIERS[0]))
        else:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            self._music_track = None

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
        # Keep the background track in step with the volume setting -
        # otherwise turning the sound down leaves the music blaring.
        try:
            pygame.mixer.music.set_volume(new_volume)
        except pygame.error:
            pass
        persistence.save_settings(self.settings)
        if new_volume > 0:
            self.sounds.play("equip")

    def _open_update_screen(self, return_state):
        self.update_return_state = return_state
        self.update_phase = "idle"
        self.update_info = None
        self.update_error = None
        self.state = "update"

    def _start_update_check(self):
        if self.update_phase == "checking":
            return
        self.update_phase = "checking"
        self.update_error = None

        def worker():
            try:
                info = updater.check_for_update()
            except Exception as exc:
                self.update_error = str(exc)
                self.update_phase = "error"
                return
            if info is None:
                self.update_phase = "up_to_date"
            else:
                self.update_info = info
                self.update_phase = "available"

        self._update_thread = threading.Thread(target=worker, daemon=True)
        self._update_thread.start()

    def _start_update_download(self):
        if self.update_phase == "downloading" or self.update_info is None:
            return
        blocked = updater.install_dir_error()
        if blocked:
            # Checked up front rather than after the download: this fails
            # when the exe lives somewhere Windows will not let an
            # unsigned app write (Controlled Folder Access covers
            # Desktop/Documents/Downloads), which running as Administrator
            # does not change.
            self.update_error = self.t("update_no_permission", folder=blocked)
            self.update_phase = "error"
            return
        self.update_phase = "downloading"
        self.update_progress = (0, self.update_info["size"])
        info = self.update_info

        def progress_cb(done, total):
            self.update_progress = (done, total or info["size"])

        def worker():
            try:
                if ON_ANDROID:
                    dest_dir = updater.android_download_dir()
                else:
                    dest_dir = updater.staging_dir()
                dest_path = os.path.join(dest_dir, info["name"])
                updater.download_update(info["url"], dest_path, progress_cb)
                self._update_download_path = dest_path
            except Exception as exc:
                self.update_error = str(exc)
                self.update_phase = "error"
                return

            if ON_ANDROID:
                try:
                    result = updater.apply_update_android(dest_path)
                except Exception as exc:
                    self.update_error = str(exc)
                    self.update_phase = "error"
                    return
                self.update_phase = "needs_permission" if result == "needs_permission" else "launched"
            elif updater.can_self_update():
                self.update_phase = "restarting"
                updater.apply_update_pc(dest_path, expected_size=info["size"])
                # Hard-exit from this worker thread rather than pygame.quit()
                # (an SDL call, unsafe off the main thread) - the relaunch
                # batch script is already waiting for this process to die.
                os._exit(0)
            else:
                self.update_phase = "dev_mode"

        self._update_thread = threading.Thread(target=worker, daemon=True)
        self._update_thread.start()

    def _retry_apply_update_android(self):
        if not self._update_download_path:
            return
        self.update_phase = "checking"

        def worker():
            try:
                result = updater.apply_update_android(self._update_download_path)
            except Exception as exc:
                self.update_error = str(exc)
                self.update_phase = "error"
                return
            self.update_phase = "needs_permission" if result == "needs_permission" else "launched"

        self._update_thread = threading.Thread(target=worker, daemon=True)
        self._update_thread.start()

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
            title = loc.BOSS_TITLE_DE.get(monster.kind, "Häuptling")
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
                self.needs_redraw = True
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_tap(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.touch_direction = None

            # Movement repeat is wall-clock based, so it benefits from the
            # faster poll rate directly.
            if self.state == "playing":
                self._handle_movement_repeat()

            # Animation timers are still counted in frames, so they must
            # keep advancing at the original 30Hz regardless of how often
            # the loop spins - otherwise the faster polling below would
            # run every animation at double speed.
            now = pygame.time.get_ticks()
            if now - self._last_tick_ms >= TICK_INTERVAL_MS:
                # Advance by exactly one interval rather than snapping to
                # `now`, so the leftover carries into the next iteration.
                # Snapping loses it, and since the 16ms poll does not
                # divide the 33ms tick that would silently run animations
                # at ~21Hz instead of 30Hz. Clamped so a long stall cannot
                # queue up a burst of catch-up ticks.
                self._last_tick_ms = max(now - TICK_INTERVAL_MS,
                                         self._last_tick_ms + TICK_INTERVAL_MS)
                if self.state == "playing":
                    self._update_animations()
                elif self.state == "confirm_disable_touch" and self.touch_warning_timer > 0:
                    self.touch_warning_timer -= 1
                    self.needs_redraw = True

            self._music_watchdog()

            if self._should_redraw():
                self.render()
                self.needs_redraw = False
                self._last_draw_ms = pygame.time.get_ticks()
            self.clock.tick(POLL_HZ)

    def _should_redraw(self):
        # This is a turn-based game: between the player's moves the screen
        # is completely static, so redrawing it 30x a second is pure waste
        # - and on a real device a single frame costs ~250ms, which is
        # most of the reported input lag (the loop was too busy redrawing
        # identical pixels to service touches promptly). Redraw only when
        # something actually changed or an animation is mid-flight.
        if self.needs_redraw:
            return True
        if self.state == "playing" and self._animations_active():
            return True
        # Safety net: never let the screen stay stale for longer than half
        # a second, whatever we might have forgotten to flag.
        return pygame.time.get_ticks() - getattr(self, "_last_draw_ms", 0) > 500

    def _animations_active(self):
        if self.shake_timer > 0 or self.flash_timer > 0 or self.boss_banner_timer > 0:
            return True
        if self.damage_numbers:
            return True
        if self.player.render_x != self.player.x or self.player.render_y != self.player.y:
            return True
        return any(m.render_x != m.x or m.render_y != m.y for m in self.monsters)

    def _present(self):
        # One large sequential copy of the in-RAM canvas onto the real
        # display surface, then present. See the comment where self.screen
        # is created for why nothing draws into the display surface
        # directly.
        self.display.blit(self.screen, (0, 0))
        pygame.display.flip()

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
            self.move_next_ms = 0
            self.move_held = False
            return

        now = pygame.time.get_ticks()
        if now < self.move_next_ms:
            return
        self.needs_redraw = True
        self._player_turn(dx, dy)
        if self.state != "playing":
            return
        self.move_next_ms = now + (
            MOVE_REPEAT_INTERVAL_MS if self.move_held else MOVE_REPEAT_INITIAL_DELAY_MS
        )
        self.move_held = True

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
        if self.state != "playing":
            # Buttons always win over any tap-anywhere fallback - the
            # tutorial's page controls used to be swallowed by it.
            for rect, key in self._tap_targets:
                if rect.collidepoint(pos):
                    self._handle_key(key)
                    return
            # Read-only screens still close on a tap anywhere; the
            # tutorial does not, because there a stray tap would lose
            # the reader's page.
            if self.state == "stats":
                self.state = self.stats_return_state
            elif self.state in ("achievements", "bestiary"):
                self.state = "title"
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
        if self.state == "install_prompt":
            if self.install_phase == "prompt":
                if key == pygame.K_RETURN:
                    self._do_install()
                elif key == pygame.K_ESCAPE:
                    installer.decline()
                    self.state = "title"
            elif self.install_phase in ("failed", "done"):
                self.state = "title"
            return

        if self.state == "tutorial":
            # Paginated, so arrows turn pages instead of leaving.
            if key == pygame.K_LEFT:
                self.tutorial_page = max(0, getattr(self, "tutorial_page", 0) - 1)
            elif key == pygame.K_RIGHT:
                self.tutorial_page = min(len(self._tutorial_pages()) - 1,
                                         getattr(self, "tutorial_page", 0) + 1)
            else:
                self.state = "title"
            return
        if self.state in ("achievements", "bestiary"):
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
            elif key == pygame.K_m:
                self._toggle_music()
            elif key == pygame.K_u:
                self._open_update_screen("settings")
                self._start_update_check()
            return

        if self.state == "update":
            if key == pygame.K_ESCAPE:
                self.state = self.update_return_state
            elif key == pygame.K_RETURN and self.update_phase == "available":
                self._start_update_download()
            elif key == pygame.K_r and self.update_phase == "error":
                self._start_update_check()
            elif key == pygame.K_r and self.update_phase == "needs_permission":
                self._retry_apply_update_android()
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
                self.tutorial_page = 0
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
        self._tick_regen()

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
            if pos == self.shrine_pos:
                self._trigger_shrine()
                if self.state == "dead":
                    return
            item = next((i for i in self.items if i.x == self.player.x and i.y == self.player.y), None)
            if item:
                self._collect_item(item)
            if (self.player.x, self.player.y) == self.stairs_pos:
                self._advance_level()
                return
            if self.up_stairs_pos and (self.player.x, self.player.y) == self.up_stairs_pos:
                self._ascend_level()
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

    def _tick_regen(self):
        if not self.player.regen_interval or self.player.hp >= self.player.max_hp:
            return
        self.player.regen_counter += 1
        if self.player.regen_counter >= self.player.regen_interval:
            self.player.regen_counter = 0
            self.player.hp = min(self.player.max_hp, self.player.hp + 1)
            self._spawn_damage_number(self.player.x, self.player.y, "+1", (100, 220, 120))

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

    def _trigger_shrine(self):
        self.shrine_pos = None
        ids = [e["id"] for e in C.SHRINE_EVENTS]
        weights = [e["weight"] for e in C.SHRINE_EVENTS]
        event_id = random.choices(ids, weights=weights, k=1)[0]

        if event_id == "vitality":
            self.player.hp = self.player.max_hp
            self._spawn_damage_number(self.player.x, self.player.y, "+HP", (100, 220, 120))
            self.add_log(self.t("log_shrine_vitality"))
            self.sounds.play("levelup")
        elif event_id == "power":
            self.player.base_power += 2
            self.add_log(self.t("log_shrine_power"))
            self.sounds.play("levelup")
        elif event_id == "fortune":
            amount = self.dungeon_level * 15
            self.player.gold += amount
            self.stats["total_gold_collected"] = self.stats.get("total_gold_collected", 0) + amount
            self._spawn_damage_number(self.player.x, self.player.y, f"+{amount}", C.COLOR_GOLD)
            self.add_log(self.t("log_shrine_fortune", amount=amount))
            self.sounds.play("levelup")
        elif event_id == "frailty":
            amount = min(5, max(1, self.player.max_hp // 5))
            self.player.max_hp = max(5, self.player.max_hp - amount)
            self.player.hp = min(self.player.hp, self.player.max_hp)
            self._spawn_damage_number(self.player.x, self.player.y, f"-{amount}", C.COLOR_TRAP)
            self.add_log(self.t("log_shrine_frailty", amount=amount))
            self.sounds.play("player_hurt")
        elif event_id == "ambush":
            self.add_log(self.t("log_shrine_ambush"))
            self.sounds.play("player_hurt")
            self._spawn_shrine_ambush()

    def _spawn_shrine_ambush(self):
        spots = [
            (self.player.x + 1, self.player.y), (self.player.x - 1, self.player.y),
            (self.player.x, self.player.y + 1), (self.player.x, self.player.y - 1),
        ]
        random.shuffle(spots)
        kinds = list(C.MONSTER_TYPES.keys())
        spawned = 0
        for x, y in spots:
            if spawned >= 2:
                break
            if not dungeon.is_walkable(self.grid, x, y) or self._is_occupied(x, y):
                continue
            monster = entities.Monster(x, y, random.choice(kinds), elite=self._maybe_elite())
            monster.awake = True
            self.monsters.append(monster)
            spawned += 1

    def _advance_level(self):
        self.level_history[self.dungeon_level] = self._snapshot_current_level()
        previous_tier = getattr(self, "tier", None)
        self.dungeon_level += 1
        self.add_log(self.t("log_descend_level", level=self.dungeon_level))
        self.sounds.play("stairs")
        if self.dungeon_level in self.level_history:
            self._restore_level_snapshot(self.level_history.pop(self.dungeon_level))
            self.player.x, self.player.y = self.up_stairs_pos
            self.player.snap()
            self._recompute_fov()
        else:
            self.new_level()
        if previous_tier is None or self.tier["index"] != previous_tier["index"]:
            self.add_log(self.t("log_new_tier", tier=self._tier_name(self.tier)))
            self.sounds.play("boss")
        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _ascend_level(self):
        if self.dungeon_level <= 1 or not self.up_stairs_pos:
            return
        self.level_history[self.dungeon_level] = self._snapshot_current_level()
        self.dungeon_level -= 1
        self.add_log(self.t("log_ascend_level", level=self.dungeon_level))
        self.sounds.play("stairs")
        if self.dungeon_level in self.level_history:
            self._restore_level_snapshot(self.level_history.pop(self.dungeon_level))
        else:
            # Shouldn't happen in practice - every level below the current
            # one was necessarily snapshotted on the way down - but fall
            # back to a fresh level rather than crash if history is ever
            # missing (e.g. an old save from before this feature existed).
            self.new_level()
        self.player.x, self.player.y = self.stairs_pos
        self.player.snap()
        self._recompute_fov()
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
                self.player.weapon_rarity_id = item.rarity_id
                self.player.weapon_element_id = item.element_id
                label = f"{self.tr(item.rarity_id)} {self.tn(item.name)}".strip()
                if item.element_id:
                    label += f" ({self.te(item.element_id)})"
                self.add_log(self.t("log_equip_weapon", item=label, bonus=item.bonus))
                self.sounds.play("equip")
            else:
                self.add_log(self.t("log_find_worse_weapon", item=self.tn(item.name), current=self.tn(self.player.weapon_name)))
        elif item.kind == "armor":
            if item.bonus > self.player.armor_bonus:
                self.player.armor_bonus = item.bonus
                self.player.armor_name = item.name
                self.player.armor_rarity_id = item.rarity_id
                label = f"{self.tr(item.rarity_id)} {self.tn(item.name)}".strip()
                self.add_log(self.t("log_equip_armor", item=label, bonus=item.bonus))
                self.sounds.play("equip")
            else:
                self.add_log(self.t("log_find_worse_armor", item=self.tn(item.name), current=self.tn(self.player.armor_name)))
        elif item.kind == "gold":
            amount = int(round(item.bonus * (1 + self.player.bonus_gold_mult)))
            self.player.gold += amount
            self.stats["total_gold_collected"] = self.stats.get("total_gold_collected", 0) + amount
            self.add_log(self.t("log_pickup_gold", amount=amount))
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
            # Widens `explored` without moving the player, so unlike every
            # other path this one never reaches _recompute_fov - invalidate
            # the cached tile surface here or the reveal would not show up.
            self._map_cache = None
            self.add_log(self.t("log_reveal"))

        self._check_achievements()
        self._maybe_show_levelup_choice()

    _ELEMENT_STATUS_LOG_KEY = {
        "burn_turns": "log_status_burn",
        "weaken_turns": "log_status_weaken",
        "stun_turns": "log_status_stun",
        "poison_turns": "log_status_poison",
    }

    def _attack(self, attacker, defender):
        crit = attacker is self.player and random.random() < self.player.crit_chance
        defense = defender.defense
        if getattr(defender, "weaken_turns", 0) > 0:
            defense = int(defense * C.WEAKEN_DEFENSE_MULT)
        damage = max(1, attacker.power - defense)
        if crit:
            damage *= 2

        element_status_applied = None
        if attacker is self.player and self.player.weapon_element_id:
            elem = C.ELEMENTS[self.player.weapon_element_id]
            kind_info = C.MONSTER_TYPES.get(getattr(defender, "kind", None), {})
            weak = self.player.weapon_element_id in kind_info.get("weak", [])
            resist = self.player.weapon_element_id in kind_info.get("resist", [])
            dmg_mult = 1.6 if weak else (0.4 if resist else 1.0)
            proc_mult = 1.5 if weak else (0.5 if resist else 1.0)
            damage += max(1, round(elem["bonus_damage"] * dmg_mult))
            proc_chance = min(0.95, elem["proc_chance"] * proc_mult + self.player.bonus_elemental_chance)
            if random.random() < proc_chance:
                status_field = elem["status"]
                setattr(defender, status_field, max(getattr(defender, status_field, 0), elem["duration"]))
                element_status_applied = status_field

        if defender is self.player and self.player.bonus_damage_reduction:
            damage = max(1, round(damage * (1 - self.player.bonus_damage_reduction)))

        defender.hp -= damage

        if self._lang() == "de":
            attacker_label = "Du" if attacker is self.player else self._monster_named(attacker, "nom")
            defender_label = "dich" if defender is self.player else self._monster_named(defender, "acc")
            verb = "triffst" if attacker is self.player else "trifft"
            if crit:
                self.add_log(f"Kritischer Treffer! {attacker_label} {verb} {defender_label} für {damage}.")
            else:
                self.add_log(f"{attacker_label} {verb} {defender_label} für {damage}.")
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

        if element_status_applied and defender.hp > 0:
            log_key = self._ELEMENT_STATUS_LOG_KEY[element_status_applied]
            self.add_log(self.t(log_key, monster=self._monster_named(defender, "nom")))

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
        self.player.bonus_damage_reduction = min(0.75, self.player.bonus_damage_reduction + perk.get("damage_reduction", 0.0))
        self.player.bonus_gold_mult += perk.get("gold_mult", 0.0)
        self.player.bonus_elemental_chance += perk.get("elemental_chance_bonus", 0.0)
        if perk.get("regen_interval"):
            self.player.regen_interval = perk["regen_interval"]
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

            stunned = self._tick_monster_status(monster)
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
            if stunned:
                continue

            for _ in range(monster.speed):
                if not monster.is_alive() or self.state == "dead":
                    break
                self._monster_act(monster)
                if self.state == "dead":
                    return

            if monster.regen and monster.is_alive() and monster.hp < monster.max_hp:
                monster.hp = min(monster.max_hp, monster.hp + monster.regen)

    def _tick_monster_status(self, monster):
        # Only ever set by the player's own elemental weapon (see _attack) -
        # monsters never inflict these on each other or on the player here.
        # Returns True if the monster was stunned and should skip its
        # action(s) this turn.
        stunned = monster.stun_turns > 0
        if stunned:
            monster.stun_turns -= 1

        if monster.poison_turns > 0:
            monster.poison_turns -= 1
            dmg = C.POISON_DAMAGE_PER_TURN
            monster.hp -= dmg
            self._spawn_damage_number(monster.x, monster.y, str(dmg), C.COLOR_POISON)
            if monster.hp <= 0:
                self._on_monster_death(monster)
                return stunned

        if monster.burn_turns > 0:
            monster.burn_turns -= 1
            dmg = C.BURN_DAMAGE_PER_TURN
            monster.hp -= dmg
            self._spawn_damage_number(monster.x, monster.y, str(dmg), C.ELEMENTS["fire"]["color"])
            if monster.hp <= 0:
                self._on_monster_death(monster)
                return stunned

        if monster.weaken_turns > 0:
            monster.weaken_turns -= 1

        return stunned

    def _monster_act(self, monster):
        dx = self.player.x - monster.x
        dy = self.player.y - monster.y
        if dx != 0:
            monster.facing = 1 if dx > 0 else -1

        # Cowardly kinds run once badly hurt instead of trading blows to
        # the death - bosses are exempt, they're meant to be a real fight.
        flee_threshold = C.MONSTER_TYPES.get(monster.kind, {}).get("flees_below")
        if flee_threshold and not monster.is_boss and monster.hp / monster.max_hp <= flee_threshold:
            step_x = -((dx > 0) - (dx < 0))
            step_y = -((dy > 0) - (dy < 0))
            self._move_monster_toward(monster, step_x, step_y)
            return

        if monster.is_boss and self._boss_special_action(monster, dx, dy):
            return

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

    def _boss_special_action(self, monster, dx, dy):
        if monster.kind == "orc":
            if not monster.enraged and monster.hp <= monster.max_hp * 0.5:
                monster.enraged = True
                monster.power = int(monster.power * 1.5)
                self.add_log(self.t("log_boss_enrage", monster=self._monster_named(monster, "nom")))
                self.sounds.play("boss")
            return False

        if monster.kind == "skeleton":
            monster.summon_cooldown = max(0, monster.summon_cooldown - 1)
            if monster.summon_cooldown == 0:
                alive_skeletons = sum(
                    1 for m in self.monsters if m.kind == "skeleton" and not m.is_boss and m.is_alive()
                )
                if alive_skeletons < 3 and self._boss_summon_skeleton(monster):
                    monster.summon_cooldown = 6
                    return True
            return False

        if monster.kind == "spider":
            dist = abs(dx) + abs(dy)
            monster.web_cooldown = max(0, monster.web_cooldown - 1)
            if (
                2 <= dist <= 4
                and monster.web_cooldown == 0
                and self._cardinal_line_clear(monster.x, monster.y, self.player.x, self.player.y)
            ):
                self.player.poison_turns = max(self.player.poison_turns, 5)
                self.add_log(self.t("log_boss_web", monster=self._monster_named(monster, "nom")))
                self._spawn_damage_number(self.player.x, self.player.y, "!", C.COLOR_POISON)
                self.sounds.play("hit")
                monster.web_cooldown = 5
                return True
            return False

        return False

    def _boss_summon_skeleton(self, boss):
        spots = [
            (boss.x + 1, boss.y), (boss.x - 1, boss.y),
            (boss.x, boss.y + 1), (boss.x, boss.y - 1),
        ]
        random.shuffle(spots)
        for x, y in spots:
            if dungeon.is_walkable(self.grid, x, y) and not self._is_occupied(x, y):
                minion = entities.Monster(x, y, "skeleton")
                minion.awake = True
                self.monsters.append(minion)
                self.add_log(self.t("log_boss_summon", monster=self._monster_named(boss, "nom")))
                self.sounds.play("boss")
                return True
        return False

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
        if self.state == "install_prompt":
            self._render_install_prompt()
            self._present()
            return

        if self.state == "title":
            self._render_title()
            self._present()
            return

        if self.state == "stats":
            self._render_stats()
            self._present()
            return

        if self.state == "achievements":
            self._render_achievements()
            self._present()
            return

        if self.state == "tutorial":
            self._render_tutorial()
            self._present()
            return

        if self.state == "settings":
            self._render_settings()
            self._present()
            return

        if self.state == "bestiary":
            self._render_bestiary()
            self._present()
            return

        if self.state == "levelup_choice":
            self._render_levelup_choice()
            self._present()
            return

        if self.state == "confirm_disable_touch":
            self._render_confirm_disable_touch()
            self._present()
            return

        if self.state == "update":
            self._render_update()
            self._present()
            return

        if self.state == "shop":
            self._render_shop()
            self._present()
            return

        if self.state == "paused":
            self._render_pause()
            self._present()
            return

        # Only the strips the map does not cover need clearing - the map
        # cache paints its whole rect and the HUD its own band, so filling
        # the entire 2.7M-pixel canvas every frame was mostly wasted. The
        # map is inset by the shake offset, so clear a little wider than
        # the gutters to catch it.
        ox, oy = self._shake_offset()
        map_w, map_h = C.MAP_PIXEL_WIDTH, C.MAP_HEIGHT * C.TILE_SIZE
        slack = self.shake_intensity if self.shake_timer > 0 else 0
        self.screen.fill(C.COLOR_BG, (0, 0, C.MAP_OFFSET_X + slack, map_h))
        self.screen.fill(C.COLOR_BG,
                         (C.MAP_OFFSET_X + map_w - slack, 0,
                          C.SCREEN_WIDTH - C.MAP_OFFSET_X - map_w + slack, map_h))
        if slack:
            self.screen.fill(C.COLOR_BG, (0, 0, C.SCREEN_WIDTH, slack))
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

        self._present()

    def _draw_tap_button(self, rect, label, key, font=None):
        rect = pygame.Rect(rect)
        radius = max(8, rect.height // 8)
        pygame.draw.rect(self.screen, (45, 45, 58), rect, border_radius=radius)
        pygame.draw.rect(self.screen, (130, 130, 150), rect, width=3, border_radius=radius)
        text = (font or self.f_body).render(label, True, C.COLOR_HUD_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))
        # Register a slightly larger hit area than the drawn box, so a
        # thumb that lands just outside still counts.
        self._tap_targets.append((rect.inflate(self.tap_slop, self.tap_slop), key))

    def _do_install(self):
        self.install_phase = "working"
        self.needs_redraw = True
        self.render()          # paint "Installing..." before we block
        try:
            target = installer.install()
            installer.create_shortcuts(target)
        except OSError as exc:
            self.install_error = str(exc)
            self.install_phase = "failed"
            self.needs_redraw = True
            return
        self.install_phase = "done"
        self.needs_redraw = True
        self.render()
        # Hand over to the installed copy and get out of the way, so the
        # user can delete the file they downloaded.
        installer.launch(target)
        pygame.time.wait(600)
        pygame.quit()
        sys.exit()

    def _render_install_prompt(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        cx = C.SCREEN_WIDTH // 2

        if self.install_phase == "working":
            body = [self.t("install_working")]
            buttons = []
        elif self.install_phase == "done":
            body = [self.t("install_done")]
            buttons = []
        elif self.install_phase == "failed":
            body = self._wrap_text(self.t("install_failed", error=self.install_error or "?"),
                                   self.f_body, self.content_w)
            buttons = [(self.t("btn_play_here"), pygame.K_ESCAPE)]
        else:
            body = (self._wrap_text(self.t("install_line1"), self.f_body, self.content_w)
                    + self._wrap_text(self.t("install_line2"), self.f_body, self.content_w)
                    + [""]
                    + self._wrap_text(
                        self.t("install_target", path=installer.default_install_dir()),
                        self.f_sm, self.content_w))
            buttons = [(self.t("btn_install"), pygame.K_RETURN),
                       (self.t("btn_play_here"), pygame.K_ESCAPE)]

        title = self.f_title.render(self.t("install_title"), True, (230, 200, 60))
        body_h = sum(self.pitch_body if line else self.gap_m for line in body)
        total = (title.get_height() + self.gap_l + body_h
                 + (self.gap_xl + self.btn_h if buttons else 0))
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(cx, y)))
        y += title.get_height() + self.gap_l
        y = self._lines_block(body, y)
        if buttons:
            self._button_row(buttons, y + self.gap_xl)

    def _render_title(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []

        lines = [
            self.t("title_move_line"),
            self.t("title_new_line"),
            "",
            self.t("title_deepest_stats", level=self.stats['deepest_level_ever'], kills=self.stats['most_kills_in_a_run']),
        ]
        if self.save_data:
            lines.append(self.t("title_saved_line",
                                level=self.save_data["dungeon_level"],
                                clevel=self.save_data["player"]["level"]))

        sprite = self.player_sprite_large
        row1 = ([(self.t("btn_continue"), pygame.K_RETURN), (self.t("btn_new_run"), pygame.K_n)]
                if self.save_data else [(self.t("btn_start"), pygame.K_RETURN)])
        row2 = [
            (self.t("btn_tutorial"), pygame.K_t),
            (self.t("btn_stats"), pygame.K_s),
            (self.t("btn_achievements"), pygame.K_a),
            (self.t("btn_settings"), pygame.K_o),
            (self.t("btn_bestiary"), pygame.K_b),
        ]
        # A five-button row can outgrow the screen once translated, so
        # step the label font down until it fits rather than clipping.
        row2_font = self.f_body
        for candidate in (self.f_body, self.f_sm, self.f_xs):
            row2_font = candidate
            widths = [self._btn_w(l, candidate) for l, _ in row2]
            if sum(widths) + self.btn_gap * (len(row2) - 1) <= self.content_w:
                break

        title_surf = self.f_title.render("DUNGEON CRAWLER", True, (230, 200, 60))
        text_h = sum(self.pitch_body if l else self.gap_m for l in lines)
        total = (title_surf.get_height() + self.gap_m
                 + (sprite.get_height() + self.gap_m if sprite else 0)
                 + text_h + self.gap_l
                 + self.btn_h + self.btn_gap + self.btn_h)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title_surf, title_surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title_surf.get_height() + self.gap_m
        if sprite:
            self.screen.blit(sprite, sprite.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
            y += sprite.get_height() + self.gap_m
        y = self._lines_block(lines, y) + self.gap_l
        y += self._button_row(row1, y) + self.btn_gap
        self._button_row(row2, y, font=row2_font)

    def _render_stats(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("stats_title"))

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
        ]
        y = self._lines_block(lines, y) + self.gap_l
        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)], y)

    def _render_achievements(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("achievements_title"))

        unlocked = set(self.stats.get("achievements_unlocked", []))
        # Two aligned columns rather than one concatenated string, so the
        # names line up and a long description can't push the mark around.
        name_x = self.pad
        desc_x = self.pad + max(
            self.f_xs.size(f"[X] {self._achievement_name(a, n)}")[0]
            for a, n, _ in C.ACHIEVEMENTS
        ) + self.gap_l
        for ach_id, name, desc in C.ACHIEVEMENTS:
            done = ach_id in unlocked
            color = (255, 215, 0) if done else (95, 95, 105)
            mark = "[X]" if done else "[ ]"
            label = self.f_xs.render(f"{mark} {self._achievement_name(ach_id, name)}", True, color)
            self.screen.blit(label, (name_x, y))
            body = self.f_xs.render(self._achievement_desc(ach_id, desc), True, color)
            self.screen.blit(body, (desc_x, y))
            y += self.pitch_xs
        y += self.gap_m
        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)], y)

    def _render_bestiary(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("bestiary_title"))

        seen = set(self.stats.get("bestiary_seen", []))
        char_x = self.pad
        name_x = self.pad + self.f_body.size("XX")[0] + self.gap_m
        info_x = name_x + max(
            self.f_body.size(
                loc.MONSTER_NAME_DE.get(k, k) if self._lang() == "de" else st["name"]
            )[0] for k, st in C.MONSTER_TYPES.items()
        ) + self.gap_l
        for kind, stats in C.MONSTER_TYPES.items():
            discovered = kind in seen
            color = stats["color"] if discovered else (80, 80, 90)
            char = stats["char"] if discovered else "?"
            if discovered:
                name = loc.MONSTER_NAME_DE.get(kind, kind) if self._lang() == "de" else stats["name"]
            else:
                name = "???"

            self.screen.blit(self.f_body.render(char, True, color), (char_x, y))
            name_color = color if discovered else (110, 110, 120)
            self.screen.blit(self.f_body.render(name, True, name_color), (name_x, y))

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

            self.screen.blit(self.f_body.render(info, True, info_color), (info_x, y))
            y += self.pitch_body
        y += self.gap_m
        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)], y)

    def _tutorial_pages(self):
        """Group the tutorial's sections into screenfuls.

        At a readable body size the ~25 lines are about three times taller
        than the screen, so this is the one menu that genuinely cannot fit
        and has to paginate. Packs greedily by whole sections (never
        splitting one across a page) and recomputes per language, since
        the German text has an extra line.
        """
        sections = loc.TUTORIAL_SECTIONS.get(self._lang(), loc.TUTORIAL_SECTIONS["en"])
        head_h = self.f_h1.get_linesize() + self.gap_s
        budget = (C.SCREEN_HEIGHT - self.pad - self.f_title.get_height() - self.gap_m
                  - self.gap_l - self.btn_h - self.pad)
        pages, page, used = [], [], 0
        for heading, body in sections:
            need = head_h + len(body) * self.pitch_sm + self.gap_m
            if page and used + need > budget:
                pages.append(page)
                page, used = [], 0
            page.append((heading, body))
            used += need
        if page:
            pages.append(page)
        return pages

    def _render_tutorial(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        pages = self._tutorial_pages()
        self.tutorial_page = max(0, min(getattr(self, "tutorial_page", 0), len(pages) - 1))

        title = f"{self.t('tutorial_title')}  {self.tutorial_page + 1}/{len(pages)}"
        y = self._screen_header(title)

        for heading, body in pages[self.tutorial_page]:
            self.screen.blit(self.f_h1.render(heading, True, (120, 200, 255)), (self.pad, y))
            y += self.f_h1.get_linesize() + self.gap_s
            for line in body:
                self.screen.blit(self.f_sm.render(line, True, C.COLOR_HUD_TEXT),
                                 (self.pad + self.gap_l, y))
                y += self.pitch_sm
            y += self.gap_m

        nav = []
        if self.tutorial_page > 0:
            nav.append((self.t("btn_prev"), pygame.K_LEFT))
        nav.append((self.t("btn_back"), pygame.K_ESCAPE))
        if self.tutorial_page < len(pages) - 1:
            nav.append((self.t("btn_next"), pygame.K_RIGHT))
        self._button_row(nav, C.SCREEN_HEIGHT - self.pad - self.btn_h)

    def _dimmed_scene(self):
        """The paused gameplay scene, dimmed - cached, since it is static."""
        if getattr(self, "_dim_cache", None) is None:
            self.screen.fill(C.COLOR_BG)
            self._render_map(C.MAP_OFFSET_X, 0)
            self._render_entities(C.MAP_OFFSET_X, 0)
            self._render_hud()
            snap = self.screen.copy()
            overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
            overlay.set_alpha(190)
            overlay.fill((0, 0, 0))
            snap.blit(overlay, (0, 0))
            self._dim_cache = snap
        self.screen.blit(self._dim_cache, (0, 0))

    def _render_pause(self):
        self._dimmed_scene()
        self._tap_targets = []

        buttons = [
            (self.t("btn_resume"), pygame.K_ESCAPE),
            (self.t("btn_stats"), pygame.K_s),
            (self.t("btn_settings"), pygame.K_o),
            (self.t("btn_save_quit"), pygame.K_q),
        ]
        title = self.f_title.render(self.t("pause_title"), True, (230, 200, 60))
        total = (title.get_height() + self.gap_l
                 + len(buttons) * self.btn_h + (len(buttons) - 1) * self.btn_gap)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title.get_height() + self.gap_l
        # One uniform width for the stack, driven by the longest label so
        # German and English both line up.
        w = max(self._btn_w(label) for label, _ in buttons)
        for label, key in buttons:
            self._draw_tap_button((C.SCREEN_WIDTH // 2 - w // 2, y, w, self.btn_h), label, key)
            y += self.btn_h + self.btn_gap

    def _render_settings(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []

        # BACK sits top-left rather than under the rows: with five
        # settings a full-width button row at the bottom no longer fits,
        # and shrinking the rows to make room would take them under the
        # 48dp touch minimum.
        back_w = self._btn_w(self.t("btn_back"))
        self._draw_tap_button((self.pad, self.pad, back_w, self.btn_h),
                              self.t("btn_back"), pygame.K_ESCAPE)
        title = self.f_title.render(self.t("settings_title"), True, (230, 200, 60))
        self.screen.blit(title, title.get_rect(
            midtop=(C.SCREEN_WIDTH // 2, self.pad + max(0, (self.btn_h - title.get_height()) // 2))))
        y = self.pad + max(self.btn_h, title.get_height()) + self.gap_m

        touch_state = self.t("on") if self.settings.get("show_touch_controls", True) else self.t("off")
        lang_state = self.t("lang_de") if self._lang() == "de" else self.t("lang_en")
        volume = self.settings.get("volume", sound.MASTER_VOLUME)
        music_state = self.t("on") if self.settings.get("music", True) else self.t("off")
        rows = [
            (self.t("settings_touch_label", state=touch_state), self.t("btn_toggle"), pygame.K_c),
            (self.t("settings_lang_label", state=lang_state), self.t("btn_toggle"), pygame.K_l),
            (self.t("settings_volume_label", state=f"{int(round(volume * 100))}%"),
             self.t("btn_toggle"), pygame.K_v),
            (self.t("settings_music_label", state=music_state), self.t("btn_toggle"), pygame.K_m),
            (self.t("settings_update_label", build=updater.current_build()),
             self.t("btn_check_update"), pygame.K_u),
        ]
        # Label left, button right on one shared row - stacking the label
        # above its button needs 5 extra rows and overflows.
        btn_w = max(self._btn_w(b) for _, b, _ in rows)
        for label, btn, key in rows:
            text = self.f_body.render(label, True, C.COLOR_HUD_TEXT)
            self.screen.blit(text, text.get_rect(midleft=(self.pad, y + self.btn_h // 2)))
            self._draw_tap_button(
                (C.SCREEN_WIDTH - self.pad - btn_w, y, btn_w, self.btn_h), btn, key)
            y += self.btn_h + self.btn_gap

    def _render_confirm_disable_touch(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        cx = C.SCREEN_WIDTH // 2

        # These warnings are long enough that the German first line
        # overflows the canvas unwrapped, so wrap both.
        body = []
        for key in ("touch_warn_line1", "touch_warn_line2"):
            body.extend(self._wrap_text(self.t(key), self.f_body, self.content_w))

        ready = self.touch_warning_timer <= 0
        seconds_left = (self.touch_warning_timer + 29) // 30
        confirm_label = self.t("btn_confirm") if ready else f"{self.t('btn_confirm')} ({seconds_left})"

        title = self.f_title.render(self.t("touch_warn_title"), True, (230, 80, 80))
        total = (title.get_height() + self.gap_l + len(body) * self.pitch_body
                 + self.gap_xl + self.btn_h_hero)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(cx, y)))
        y += title.get_height() + self.gap_l
        y = self._lines_block(body, y) + self.gap_xl

        # Turning off touch controls removes the only touch input path, so
        # give both choices oversized targets and keep confirm inert (and
        # visibly disabled) until the countdown expires.
        cancel_w = self._btn_w(self.t("btn_cancel"))
        confirm_w = self._btn_w(confirm_label)
        x = cx - (cancel_w + self.btn_gap + confirm_w) // 2
        self._draw_tap_button((x, y, cancel_w, self.btn_h_hero), self.t("btn_cancel"), pygame.K_ESCAPE)
        rect = pygame.Rect(x + cancel_w + self.btn_gap, y, confirm_w, self.btn_h_hero)
        if ready:
            self._draw_tap_button(rect, confirm_label, pygame.K_RETURN)
        else:
            radius = max(8, rect.height // 8)
            pygame.draw.rect(self.screen, (30, 30, 36), rect, border_radius=radius)
            pygame.draw.rect(self.screen, (70, 70, 80), rect, width=3, border_radius=radius)
            label = self.f_body.render(confirm_label, True, (110, 110, 120))
            self.screen.blit(label, label.get_rect(center=rect.center))

    def _render_update(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        cx = C.SCREEN_WIDTH // 2

        phase = self.update_phase
        if phase == "checking":
            body = self.t("update_checking")
        elif phase == "error":
            body = self.t("update_error_prefix", error=self.update_error or "?")
        elif phase == "up_to_date":
            body = self.t("update_up_to_date", build=updater.current_build())
        elif phase == "available":
            size_mb = self.update_info["size"] / (1024 * 1024)
            body = self.t("update_available", build=self.update_info["build"], size=f"{size_mb:.1f}")
        elif phase == "downloading":
            done, total_bytes = self.update_progress
            percent = int(done * 100 / total_bytes) if total_bytes else 0
            body = self.t("update_downloading", percent=percent)
        elif phase == "restarting":
            body = self.t("update_restarting")
        elif phase == "needs_permission":
            body = self.t("update_needs_permission")
        elif phase == "launched":
            body = self.t("update_launched")
        elif phase == "dev_mode":
            body = self.t("update_dev_mode")
        else:
            body = ""

        y = self._screen_header(self.t("update_title")) + self.gap_m
        if body:
            lines = self._wrap_text(body, self.f_body, self.content_w)
            y = self._lines_block(lines, y)

        if phase == "downloading":
            done, total_bytes = self.update_progress
            bar_w, bar_h = self.content_w // 2, self.gap_l
            bar = pygame.Rect(cx - bar_w // 2, y + self.gap_m, bar_w, bar_h)
            pygame.draw.rect(self.screen, (40, 40, 48), bar, border_radius=8)
            if total_bytes:
                fill = int(bar_w * min(1.0, done / total_bytes))
                pygame.draw.rect(self.screen, (90, 180, 90), (bar.x, bar.y, fill, bar_h), border_radius=8)
            pygame.draw.rect(self.screen, (70, 70, 80), bar, width=3, border_radius=8)
            y = bar.bottom

        # Anchor the buttons rather than letting them follow the body, so
        # they stay put as the phase text changes length.
        y = C.SCREEN_HEIGHT - self.pad - self.btn_h
        row = []
        if phase == "available":
            row.append((self.t("btn_download_install"), pygame.K_RETURN))
        elif phase in ("error", "needs_permission"):
            row.append((self.t("btn_retry"), pygame.K_r))
        if phase not in ("downloading", "restarting"):
            row.append((self.t("btn_back"), pygame.K_ESCAPE))
        if row:
            self._button_row(row, y)

    def _wrap_text(self, text, font, max_width):
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _render_levelup_choice(self):
        self._dimmed_scene()
        self._tap_targets = []
        cx = C.SCREEN_WIDTH // 2

        title = self.f_title.render(self.t("levelup_title"), True, (230, 200, 60))
        hint = self.f_sm.render(self.t("levelup_hint"), True, C.COLOR_HELP_TEXT)

        card_h = (self.f_h1.get_linesize() + self.gap_s + self.pitch_body
                  + self.gap_m + self.btn_h)
        total = (title.get_height() + self.gap_l + card_h
                 + self.gap_l + hint.get_height())
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(cx, y)))
        y += title.get_height() + self.gap_l

        keys = [pygame.K_1, pygame.K_2]
        n = max(1, len(self.perk_choices))
        card_w = min((self.content_w - self.gap_l * (n - 1)) // n, self.content_w // 2)
        x0 = cx - (card_w * n + self.gap_l * (n - 1)) // 2
        for i, perk in enumerate(self.perk_choices):
            x = x0 + i * (card_w + self.gap_l)
            card = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (28, 28, 38), card, border_radius=self.gap_m)
            pygame.draw.rect(self.screen, (120, 120, 150), card, width=3, border_radius=self.gap_m)

            cy = y + self.gap_s
            name = self.f_h1.render(f"{i + 1}. {self._perk_name(perk)}", True, (255, 255, 255))
            self.screen.blit(name, name.get_rect(midtop=(card.centerx, cy)))
            cy += self.f_h1.get_linesize() + self.gap_s
            desc = self.f_body.render(self._perk_desc(perk), True, C.COLOR_HUD_TEXT)
            self.screen.blit(desc, desc.get_rect(midtop=(card.centerx, cy)))

            # The whole card is the tap target, not just the strip; the
            # strip stays only so it is obvious the card is tappable.
            strip = pygame.Rect(x + self.gap_m, card.bottom - self.btn_h - self.gap_s,
                                card_w - 2 * self.gap_m, self.btn_h)
            radius = max(8, strip.height // 8)
            pygame.draw.rect(self.screen, (45, 45, 58), strip, border_radius=radius)
            pygame.draw.rect(self.screen, (130, 130, 150), strip, width=3, border_radius=radius)
            label = self.f_body.render(self.t("btn_choose"), True, C.COLOR_HUD_TEXT)
            self.screen.blit(label, label.get_rect(center=strip.center))
            self._tap_targets.append((card, keys[i]))

        y += card_h + self.gap_l
        self.screen.blit(hint, hint.get_rect(midtop=(cx, y)))

    def _render_shop(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("shop_title"), color=C.COLOR_MERCHANT)

        gold = self.f_body.render(self.t("shop_gold_label", gold=self.player.gold), True, C.COLOR_GOLD)
        self.screen.blit(gold, gold.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += gold.get_height() + self.gap_l

        keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
        # Shrink the rows only if a future stock list would not otherwise
        # fit, and never below a usable touch height.
        avail = C.SCREEN_HEIGHT - self.pad - self.btn_h - self.gap_l - y
        n = len(C.SHOP_STOCK)
        row_h = max(self.btn_h, min(self.btn_h, (avail - self.gap_s * (n - 1)) // max(1, n)))
        buy_w = self._btn_w(self.t("btn_buy"))
        for i, stock in enumerate(C.SHOP_STOCK):
            label = f"{i + 1}. {self.tn(stock['name'])} - {stock['price']} {self.t('gold_word')}"
            text = self.f_body.render(label, True, C.COLOR_HUD_TEXT)
            self.screen.blit(text, text.get_rect(midleft=(self.pad, y + row_h // 2)))
            self._draw_tap_button(
                (C.SCREEN_WIDTH - self.pad - buy_w, y, buy_w, row_h),
                self.t("btn_buy"), keys[i])
            y += row_h + self.btn_gap

        self._button_row([(self.t("btn_leave"), pygame.K_ESCAPE)],
                         C.SCREEN_HEIGHT - self.pad - self.btn_h)

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
        bar_w = min(self.content_w, C.SCREEN_WIDTH // 2)
        bar_h = self.f_sm.get_linesize() + self.gap_s
        x, y = C.SCREEN_WIDTH // 2 - bar_w // 2, self.gap_s
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

    def _rebuild_map_cache(self):
        # The tile grid only changes when the player's field of view does,
        # which is once per turn at most - but this loop was running every
        # single frame, and it grows as the level is explored: measured at
        # 0.22ms with 50 tiles explored and 3.74ms at 1000, making it the
        # largest single item in a gameplay frame. Painting it once into a
        # cached surface turns the per-frame cost into one 0.11ms blit.
        # Invalidated from _recompute_fov and wherever the map is replaced.
        tier = getattr(self, "tier", None) or C.DUNGEON_TIERS[0]
        surf = pygame.Surface((C.MAP_PIXEL_WIDTH, C.MAP_HEIGHT * C.TILE_SIZE))
        surf.fill(C.COLOR_BG)
        for y in range(C.MAP_HEIGHT):
            row = self.grid[y]
            for x in range(C.MAP_WIDTH):
                if (x, y) not in self.explored:
                    continue
                is_visible = (x, y) in self.visible
                if row[x] == dungeon.WALL:
                    color = tier["wall"] if is_visible else tier["wall_dim"]
                else:
                    color = tier["floor"] if is_visible else tier["floor_dim"]
                pygame.draw.rect(
                    surf, color,
                    (x * C.TILE_SIZE, y * C.TILE_SIZE, C.TILE_SIZE, C.TILE_SIZE),
                )
        self._map_cache = surf

    def _render_map(self, ox=0, oy=0):
        if getattr(self, "_map_cache", None) is None:
            self._rebuild_map_cache()
        self.screen.blit(self._map_cache, (ox, oy))

        if self.stairs_pos in self.explored:
            self._draw_ladder(*self.stairs_pos, ox, oy)

        if self.up_stairs_pos and self.up_stairs_pos in self.explored:
            self._draw_char("<", self.up_stairs_pos[0], self.up_stairs_pos[1], C.COLOR_STAIRS_UP, ox, oy)

        if self.shrine_pos and self.shrine_pos in self.explored:
            self._draw_char("A", self.shrine_pos[0], self.shrine_pos[1], C.COLOR_SHRINE, ox, oy)

    def _render_entities(self, ox=0, oy=0):
        for item in self.items:
            if (item.x, item.y) in self.visible:
                self._draw_item(item, ox, oy)

        for merchant in self.merchants:
            if (merchant.x, merchant.y) in self.visible:
                self._draw_merchant(merchant, ox, oy)

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

    # Tiered pickups (rarer weapon/armor, or scroll type) share one image
    # per kind rather than art per tier - same halo trick as elite
    # monsters, tinted with the item's own already-defined tier color,
    # keeps the tier/type cue that colored ASCII glyphs used to carry.
    _HALO_ITEM_KINDS = ("weapon", "armor", "scroll")

    def _draw_item(self, item, ox=0, oy=0):
        sprite = self.item_sprites.get(item.kind)
        if sprite is None:
            self._draw_char(item.char, item.x, item.y, item.color, ox, oy)
            return

        center = (
            int(item.x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox),
            int(item.y * C.TILE_SIZE + C.TILE_SIZE // 2 + oy),
        )
        rect = sprite.get_rect(center=center)

        if item.kind in self._HALO_ITEM_KINDS:
            glow = pygame.Surface((int(sprite.get_width() * 1.3), int(sprite.get_height() * 1.3)), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*item.color, 100), glow.get_rect())
            self.screen.blit(glow, glow.get_rect(center=center))

        self.screen.blit(sprite, rect)

    def _draw_ladder(self, x, y, ox=0, oy=0):
        if self.ladder_sprite is None:
            self._draw_char(">", x, y, C.COLOR_STAIRS, ox, oy)
            return
        center = (
            int(x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox),
            int(y * C.TILE_SIZE + C.TILE_SIZE // 2 + oy),
        )
        rect = self.ladder_sprite.get_rect(center=center)
        self.screen.blit(self.ladder_sprite, rect)

    def _draw_merchant(self, merchant, ox=0, oy=0):
        if self.merchant_sprite is None:
            self._draw_char(merchant.char, merchant.x, merchant.y, merchant.color, ox, oy)
            return
        tile_center_x = merchant.x * C.TILE_SIZE + C.TILE_SIZE // 2 + ox
        tile_bottom_y = merchant.y * C.TILE_SIZE + C.TILE_SIZE + oy
        rect = self.merchant_sprite.get_rect(midbottom=(int(tile_center_x), int(tile_bottom_y) + 2))
        self.screen.blit(self.merchant_sprite, rect)

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
        # Laid out from the actual band height and the shared font ladder
        # rather than from self.ui_scale, so it stays readable however the
        # map/HUD split lands on a given device.
        hud_y = C.MAP_HEIGHT * C.TILE_SIZE
        pygame.draw.rect(self.screen, C.COLOR_HUD_BG, (0, hud_y, C.SCREEN_WIDTH, C.HUD_HEIGHT))

        f = self.f_sm
        row_h = f.get_linesize() + self.gap_s // 2
        pad = self.gap_m
        ox = C.MAP_OFFSET_X
        left_x = ox + pad
        col_w = (C.SCREEN_WIDTH - ox - pad * 2) // 2
        right_x = left_x + col_w
        y = hud_y + self.gap_s

        bar_w = min(col_w - pad * 2, int(col_w * 0.55))
        bar_h = f.get_height()

        pygame.draw.rect(self.screen, C.COLOR_HP_BAR_BG, (left_x, y, bar_w, bar_h))
        hp_ratio = max(0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(self.screen, C.COLOR_HP_BAR_FG, (left_x, y, int(bar_w * hp_ratio), bar_h))
        self.screen.blit(f.render(f"HP {max(0, self.player.hp)}/{self.player.max_hp}", True,
                                  C.COLOR_HUD_TEXT), (left_x + bar_w + self.gap_s, y))

        pygame.draw.rect(self.screen, C.COLOR_XP_BAR_BG, (right_x, y, bar_w, bar_h))
        xp_ratio = self.player.xp / self.player.xp_to_next
        pygame.draw.rect(self.screen, C.COLOR_XP_BAR_FG, (right_x, y, int(bar_w * xp_ratio), bar_h))
        self.screen.blit(
            f.render(f"Lv {self.player.level}  XP {self.player.xp}/{self.player.xp_to_next}",
                     True, C.COLOR_HUD_TEXT), (right_x + bar_w + self.gap_s, y))
        y += row_h

        # Two columns: equipment left, resources right. Icons reuse the
        # same glyph and colour these items have on the map.
        weapon_color = C.RARITY_BY_ID.get(self.player.weapon_rarity_id, {}).get("color", (215, 215, 230))
        weapon_suffix = f" [{self.te(self.player.weapon_element_id)}]" if self.player.weapon_element_id else ""
        self._hud_icon_row(left_x, y, "/", weapon_color,
                           f"{self.tn(self.player.weapon_name)} (+{self.player.weapon_bonus}){weapon_suffix}",
                           label_color=weapon_color)
        self._hud_icon_row(right_x, y, "!", C.COLOR_POTION,
                           f"{self.t('hud_potions')} {self.player.potions}")
        y += row_h

        armor_color = C.RARITY_BY_ID.get(self.player.armor_rarity_id, {}).get("color", (170, 170, 185))
        self._hud_icon_row(left_x, y, "[", armor_color,
                           f"{self.tn(self.player.armor_name)} (+{self.player.armor_bonus})",
                           label_color=armor_color)
        self._hud_icon_row(right_x, y, "$", C.COLOR_GOLD,
                           f"{self.t('hud_gold')} {self.player.gold}")
        y += row_h

        tier_label = self._tier_name(getattr(self, "tier", C.DUNGEON_TIERS[0]))
        self.screen.blit(
            f.render(f"{tier_label}  Lv {self.dungeon_level}", True, C.COLOR_HUD_TEXT), (left_x, y))
        self.screen.blit(f.render(f"{self.t('hud_kills')} {self.player.kills}", True, C.COLOR_HUD_TEXT), (right_x, y))
        y += row_h

        scrolls = self.player.scrolls
        scroll_line = (f"{self.t('hud_scrolls_label')} F:{scrolls['fireball']}  "
                       f"T:{scrolls['teleport']}  V:{scrolls['reveal']}")
        if self.player.poison_turns > 0:
            scroll_line += f"    {self.t('hud_poisoned')}"
            scroll_color = C.COLOR_POISON
        else:
            scroll_color = C.COLOR_HELP_TEXT
        self.screen.blit(f.render(scroll_line, True, scroll_color), (left_x, y))
        y += row_h

        # Fill whatever is left with the most recent log lines, oldest
        # first, so the newest is always visible at the bottom.
        log_font = self.f_xs
        log_pitch = log_font.get_linesize() + 2
        room = max(0, (hud_y + C.HUD_HEIGHT - self.gap_s - y) // log_pitch)
        for i, message in enumerate(self.log[-room:] if room else []):
            self.screen.blit(log_font.render(message, True, C.COLOR_LOG_TEXT), (left_x, y + i * log_pitch))

    def _hud_icon_row(self, x, y, char, color, text, label_color=None):
        icon = self.f_sm.render(char, True, color)
        self.screen.blit(icon, (x, y))
        label = self.f_sm.render(text, True, label_color or C.COLOR_HUD_TEXT)
        self.screen.blit(label, (x + self.f_sm.size("XX")[0], y))

    def _draw_touch_button(self, rect, label, active=False):
        radius = max(6, rect.height // 8)
        fill = (90, 90, 110) if active else (40, 40, 50)
        pygame.draw.rect(self.screen, fill, rect, border_radius=radius)
        pygame.draw.rect(self.screen, (150, 150, 170), rect, width=3, border_radius=radius)
        text = self.f_sm.render(label, True, C.COLOR_HUD_TEXT)
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

        best_line = self.t("gameover_best")
        lines = [self.t("gameover_summary", level=self.dungeon_level,
                        kills=self.player.kills, clevel=self.player.level)]
        if self.new_best:
            lines.append(best_line)

        title = self.f_title.render(self.t("gameover_title"), True, (200, 40, 40))
        total = (title.get_height() + self.gap_l + len(lines) * self.pitch_body
                 + self.gap_xl + self.btn_h_hero)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title.get_height() + self.gap_l
        for line in lines:
            color = (255, 215, 0) if line == best_line else C.COLOR_HUD_TEXT
            surf = self.f_body.render(line, True, color)
            self.screen.blit(surf, surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
            y += self.pitch_body
        y += self.gap_xl

        self._button_row([
            (self.t("btn_restart"), pygame.K_r),
            (self.t("btn_stats"), pygame.K_s),
            (self.t("btn_quit"), pygame.K_ESCAPE),
        ], y, height=self.btn_h_hero)
