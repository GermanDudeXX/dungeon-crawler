import os
import random
import sys
import threading
import time

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
# How long to wait before retrying music that failed to start. Only ever
# applies when nothing is playing; a healthy track is never restarted.
MUSIC_RETRY_COOLDOWN_MS = 5000
# Frame-counted animation timers still advance at the original rate, so
# doubling the poll rate does not double animation speed.
TICK_INTERVAL_MS = 1000 // 30


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Dungeon Crawler")
        # Loaded first: the zoom setting decides the tile size, and that
        # is needed before the display is sized.
        self.settings = persistence.load_settings()
        self.ui_scale = 1.0
        self.render_scale = 1.0
        self._fps_frames = 0
        self._fps_since = 0
        self._fps_surface = None
        self._slow_frames = 0
        self._slow_warned = False
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
        self.sounds = sound.Sounds(volume=self.settings.get("volume", sound.MASTER_VOLUME))
        self.player_sprite_right, self.player_sprite_left, self.player_sprite_large = self._load_player_sprite()
        self._measure_player_head()
        self.monster_sprites = self._load_monster_sprites()
        self.item_sprites = self._load_item_sprites()
        # The HUD used ASCII stand-ins ("/", "[", "!", "$") for icons even
        # though the real art is already loaded - these are that art,
        # rescaled once to HUD row height.
        icon_h = max(18, self.f_sm.get_height() + self.gap_s // 2)
        self.hud_icons = {}
        for kind, sprite in self.item_sprites.items():
            w = max(1, int(sprite.get_width() * (icon_h / sprite.get_height())))
            self.hud_icons[kind] = pygame.transform.smoothscale(sprite, (w, icon_h))
        self.ladder_sprite = self._load_scaled_sprite(C.LADDER_SPRITE_PATH, C.LADDER_SPRITE_HEIGHT)
        self.merchant_sprite = self._load_scaled_sprite(C.MERCHANT_SPRITE_PATH, C.MERCHANT_SPRITE_HEIGHT)
        self.blacksmith_sprite = self._load_scaled_sprite(
            C.BLACKSMITH_SPRITE_PATH, C.BLACKSMITH_SPRITE_HEIGHT)
        self._tile_sources = self._load_tile_sources()
        self._tile_cache = {}
        self._decor = {}
        self._name_cache = {}
        self._badge_cache = {}
        self._potion_sprite_cache = {}
        self._glow_cache = {}
        self._wash_cache = {}
        self._touch_btn_cache = {}
        self._hud_cache = None
        self.bag_page = 0
        self.shop_stock = None
        self._class_sprite_cache = {}
        self.pending_difficulty = None
        # The title screen shows the hero you last played as, rather than
        # a generic figure that turns into someone else the moment a run
        # starts. Done here, at the end of setup, because it needs both
        # the loaded settings and the sprite cache above.
        #
        # char_class has to be seeded from settings first: _class() reads
        # the attribute, not the setting, so before a run has started it
        # would otherwise fall back to the default and the title would
        # always show a Warrior whatever you last played.
        self.char_class = self.settings.get("char_class", C.DEFAULT_CLASS)
        self._use_class_sprite(self._class())
        self.particles = []
        self.hitstop_timer = 0
        self.banners = []
        # Only ever true in the test room, and it gates the cheat panel:
        # none of this should be reachable from a real run.
        self.test_room = False
        self.godmode = False
        self.enemies_off = False
        self.needs_redraw = True
        self._last_draw_ms = 0
        self._last_tick_ms = 0
        self._pressed_key = None
        self._pressed_until = 0
        self._music_track = None
        # Backdated so the first recovery attempt is allowed immediately;
        # plain 0 would block it for a whole cooldown right after launch,
        # which is exactly when a failed first load needs retrying.
        self._music_retry_ms = -MUSIC_RETRY_COOLDOWN_MS
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
        self._shortcut_status = None
        self.update_return_state = "settings"
        self.update_phase = "idle"
        self.update_info = None
        self.update_error = None
        self.update_progress = (0, 0)
        self._update_thread = None
        self._update_download_path = None
        self._quit_for_update = False

        # Resolve the updater's Java classes now, on the main thread. The
        # download runs on a worker, and a Python thread attached to the
        # JVM gets the system class loader, which cannot see the app's own
        # classes - looking PythonActivity up there fails.
        updater.preload_android_classes()

        # Clears the previous build and any leaked onefile extraction
        # folders left in %TEMP%. Runs on a background thread.
        updater.cleanup_previous_update()
        # If the last update could not actually install itself, say so
        # instead of letting the same update be offered forever with no
        # hint that anything went wrong. Shown the next time the update
        # screen is opened, not popped up over the title.
        self._pending_update_failure = updater.take_failure_marker()

    def _render_scale_for(self, win_w, win_h):
        """How much to shrink the drawing canvas, 0 < scale <= 1.

        "auto" takes the largest canvas that stays under
        C.MAX_CANVAS_PIXELS, which is roughly what the desktop build draws
        and runs comfortably. The fixed levels exist so a slow device can
        be dialled down by hand without guessing at a pixel budget.
        """
        want = self.settings.get("render_scale", C.DEFAULT_RENDER_SCALE)
        if want != "auto":
            try:
                return max(0.25, min(1.0, float(want)))
            except (TypeError, ValueError):
                pass
        pixels = win_w * win_h
        if pixels <= C.MAX_CANVAS_PIXELS:
            return 1.0
        return (C.MAX_CANVAS_PIXELS / pixels) ** 0.5

    def _zoom(self):
        levels = C.ZOOM_LEVELS
        want = self.settings.get("zoom", C.DEFAULT_ZOOM)
        return min(levels, key=lambda z: abs(z - want))

    def _apply_zoom(self, base_tile):
        """Sets the drawn tile size from a base tile size and the zoom.

        The viewport - the hole in the layout the dungeon is seen through
        - stays the size the base tile gives, so the gutters, the HUD and
        the touch buttons do not move when the zoom changes. Only the
        tiles get bigger, and the view becomes a window that follows the
        player (see _shake_offset).
        """
        C.VIEW_W = C.MAP_WIDTH * base_tile
        C.VIEW_H = C.MAP_HEIGHT * base_tile
        C.TILE_SIZE = max(base_tile, int(round(base_tile * self._zoom())))
        C.MAP_PIXEL_WIDTH = C.MAP_WIDTH * C.TILE_SIZE
        self._rescale_tile_constants()
        self._map_cache = None
        self._minimap_cache = None
        self._tile_cache = {}
        self._wash_cache = {}
        self._glow_cache = {}
        self._touch_btn_cache = {}

    def _apply_pc_ui_scale(self):
        # Every value here comes from the BASE_* constants, never from the
        # live ones: those are results of a previous pass, and deriving
        # from them compounds (see constants.BASE_TILE_SIZE).
        self.ui_scale = 1.3
        self._apply_zoom(C.BASE_TILE_SIZE)
        C.HUD_HEIGHT = int(190 * self.ui_scale)
        C.SCREEN_HEIGHT = C.VIEW_H + C.HUD_HEIGHT
        # Widen the gutter too, in proportion - otherwise the now-bigger
        # D-pad (see _setup_touch_controls) would overflow past the edge
        # of the unchanged default gutter width.
        C.GUTTER_WIDTH = int(C.BASE_GUTTER_WIDTH * self.ui_scale)
        C.MAP_OFFSET_X = C.GUTTER_WIDTH
        C.SCREEN_WIDTH = C.VIEW_W + 2 * C.GUTTER_WIDTH

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

        # Draw into a smaller canvas and let SCALED stretch it. Everything
        # is copied to the display once a frame, and at the phone's full
        # 2448x1098 that copy alone moves 10MB - over 300MB/s at 30fps,
        # before anything is drawn into it. Halving the canvas quarters
        # every fill, blit and the present itself.
        self.render_scale = self._render_scale_for(win_w, win_h)
        win_w = max(640, int(win_w * self.render_scale))
        win_h = max(360, int(win_h * self.render_scale))

        # Pick the largest tile size the window can actually hold. The
        # tile size used to be a fixed 24px, which on this device left
        # the 40x25 map occupying only 960x600 of a 2448x1098 window -
        # 39% of the width - while the HUD band soaked up the rest. The
        # two constraints are the gutters (which must stay wide enough
        # for the touch controls) and the HUD band under the map.
        # Both floors mean a *physical* size - a thumb-sized D-pad, a
        # readable HUD band - so they shrink with the canvas. Left at their
        # full value they would eat a downscaled canvas whole and force the
        # tiles back to their minimum, undoing the saving entirely.
        min_gutter = max(64, int(C.MIN_GUTTER_WIDTH * self.render_scale))
        min_hud = max(40, int(C.MIN_HUD_HEIGHT * self.render_scale))
        self._min_gutter = min_gutter
        by_width = (win_w - 2 * min_gutter) // C.MAP_WIDTH
        by_height = (win_h - min_hud) // C.MAP_HEIGHT
        tile = max(24, min(by_width, by_height))
        self._apply_zoom(tile)

        # Whatever vertical space the viewport leaves goes to the HUD,
        # floored at the original design height so a short window cannot
        # squeeze it away entirely.
        C.HUD_HEIGHT = max(min_hud, win_h - C.VIEW_H)
        C.SCREEN_HEIGHT = C.VIEW_H + C.HUD_HEIGHT
        self.ui_scale = C.HUD_HEIGHT / 190

        device_ratio = win_w / win_h
        # Reject 0/garbage/portrait-shaped reads rather than ever
        # producing a broken layout - falls back to the static
        # GUTTER_WIDTH/SCREEN_WIDTH already set in constants.py.
        if 1.2 <= device_ratio <= 3.5:
            new_gutter = max(min_gutter, (win_w - C.VIEW_W) // 2)
            C.GUTTER_WIDTH = new_gutter
            C.MAP_OFFSET_X = new_gutter
            C.SCREEN_WIDTH = C.VIEW_W + 2 * new_gutter
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

    def _load_tile_sources(self):
        """Loads the raw 16x16 dungeon tiles once, unscaled.

        Kept separate from the scaled/tinted cache below because the same
        source frame gets used at several brightnesses and in five
        different theme colours, and re-reading it from disk for each one
        would be silly.
        """
        sources = {}
        try:
            names = os.listdir(C.TILE_SPRITE_DIR)
        except OSError:
            return sources
        for filename in names:
            if not filename.endswith(".png"):
                continue
            try:
                image = pygame.image.load(
                    os.path.join(C.TILE_SPRITE_DIR, filename)).convert_alpha()
            except (pygame.error, FileNotFoundError):
                continue
            sources[filename[:-4]] = image
        return sources

    def _tile(self, name, dim=False):
        """A theme-tinted, brightness-adjusted, scaled-up dungeon tile.

        Everything is cached per (name, tier, dim) and built at most once
        per run: the map cache calls this for every explored cell, and
        rebuilding a tinted surface each time would be far worse than the
        per-frame tile loop this whole cache exists to avoid.
        """
        tier = getattr(self, "tier", None) or C.DUNGEON_TIERS[0]
        key = (name, tier["id"], dim)
        cached = self._tile_cache.get(key)
        if cached is not None:
            return cached

        source = self._tile_sources.get(name)
        if source is None:
            return None

        w, h = source.get_size()
        scale = C.TILE_SIZE / C.TILE_SOURCE_SIZE
        # scale, never smoothscale: smoothing 16x16 pixel art up to 24px
        # blurs every hard edge and it stops reading as pixel art at all.
        tile = pygame.transform.scale(
            source, (max(1, round(w * scale)), max(1, round(h * scale))))

        tint = tier.get("tile_tint")
        if tint:
            tile = self._tint_tile(tile, tint)
        if dim:
            shade = pygame.Surface(tile.get_size()).convert_alpha()
            shade.fill((int(255 * C.TILE_DIM_FACTOR),) * 3 + (255,))
            tile.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        self._tile_cache[key] = tile
        return tile

    @staticmethod
    def _tint_tile(tile, tint):
        """Recolours a tile towards a theme colour, keeping its shading.

        The tileset is one warm brown/grey set, but the game has five
        themes. Rather than ship five tilesets, the tile's own brightness
        is kept and its hue replaced: a greyscale copy multiplied by the
        theme colour gives "the same stonework, lit differently", which is
        what a crypt vs an inferno should look like. Blended back over the
        original at partial strength so the source's own colour variation
        does not disappear completely.
        """
        try:
            gray = pygame.transform.grayscale(tile)
        except (AttributeError, pygame.error):
            return tile
        gray = gray.convert_alpha()
        # Multiplying by a colour can only darken, so lift the greyscale
        # first - otherwise every theme comes out muddy.
        gray.fill((90, 90, 90, 0), special_flags=pygame.BLEND_RGBA_ADD)
        gray.fill(tuple(tint) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        out = tile.copy()
        gray.set_alpha(int(255 * C.TILE_TINT_STRENGTH))
        out.blit(gray, (0, 0))
        return out

    def _floor_tile_name(self, x, y):
        # Deterministic per cell: a real random pick would reshuffle the
        # entire floor every time the field of view changes and the cache
        # is repainted, which looks like the dungeon is flickering.
        return "floor_%d" % (1 + (x * 7 + y * 13 + x * y * 3) % C.FLOOR_VARIANTS)

    def _is_wall(self, x, y):
        if not (0 <= x < C.MAP_WIDTH and 0 <= y < C.MAP_HEIGHT):
            return True
        return self.grid[y][x] == dungeon.WALL

    def _wall_tile_name(self, x, y):
        """Picks a wall frame from which sides face open floor.

        The tileset is drawn in the usual "walls seen slightly from the
        front" style, so which frame is right depends on where the empty
        space is: a wall with floor below it is being looked at from the
        front and shows its brick face, a wall with floor above it is
        being looked down on and shows its flat top, and the sides get
        their own edge pieces.

        Returns None for a wall with no open neighbour at all. Those are
        the solid rock between rooms - the great majority of the grid -
        and they must not get a tile: every wall frame in this set is
        drawn as a *surface* of a wall, so tiling one across a solid rock
        field gives a striped pattern rather than rock. The caller fills
        those cells with flat stone colour instead.
        """
        south = not self._is_wall(x, y + 1)
        north = not self._is_wall(x, y - 1)
        west = not self._is_wall(x - 1, y)
        east = not self._is_wall(x + 1, y)
        if south:
            return "wall_mid"
        if west and not east:
            return "wall_left"
        if east and not west:
            return "wall_right"
        if north:
            return "wall_mid"
        if west or east:
            return "wall_top_mid"
        return None

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
        map_bottom = C.VIEW_H
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

        # The bag opens the potion list. It shares the HEAL button's
        # column and sits directly above the scroll row, so the whole
        # action cluster stays one reachable block under the thumb.
        self.bag_button = pygame.Rect(
            right_edge - self.potion_button.width, scroll_y - g - scroll_size,
            self.potion_button.width, scroll_size)

        # Pinned to the top-right corner - the only touch route back to the
        # pause menu, so it stays visible even with the other controls off.
        menu_w = min(self._btn_w(self._touch_label("touch_menu", "ESC"), self.f_sm),
                     C.GUTTER_WIDTH - 2 * self.gap_m)
        self.save_button = pygame.Rect(
            C.SCREEN_WIDTH - self.gap_m - menu_w, self.gap_m, menu_w, self.btn_h)

        # The test room's cheat panel, mirrored into the free top-left
        # corner rather than stacked with the action buttons. That column
        # is already four deep on a phone and adding a fifth put it
        # underneath either the MENU button or the bag, and a tap in the
        # overlap hit whichever happened to be checked first. Laid out
        # unconditionally so the geometry never depends on game state; it
        # is only drawn and only tappable inside the test room.
        tools_w = min(self._btn_w(self._touch_label("btn_tools", "K"), self.f_sm),
                      C.GUTTER_WIDTH - 2 * self.gap_m)
        self.tools_button = pygame.Rect(
            self.gap_m, self.gap_m, tools_w, self.btn_h)

    def _diff(self):
        """The chosen difficulty's multiplier set, never None."""
        return C.DIFFICULTY_BY_ID.get(
            getattr(self, "difficulty", C.DEFAULT_DIFFICULTY),
            C.DIFFICULTY_BY_ID[C.DEFAULT_DIFFICULTY],
        )

    def _difficulty_name(self, diff):
        if self._lang() == "de":
            return loc.DIFFICULTY_DE.get(diff["id"], diff["name"])
        return diff["name"]

    def _class(self):
        return C.CLASS_BY_ID.get(
            getattr(self, "char_class", C.DEFAULT_CLASS),
            C.CLASS_BY_ID[C.DEFAULT_CLASS])

    def _class_name(self, klass):
        if self._lang() == "de":
            return loc.CLASS_DE.get(klass["id"], klass["name"])
        return klass["name"]

    def _class_blurb(self, klass):
        if self._lang() == "de":
            return loc.CLASS_BLURB_DE.get(klass["id"], klass["blurb"])
        return klass["blurb"]

    def _apply_class(self, klass):
        """The class's opening hand: stats, kit and starting flasks.

        Everything here is additive on top of a normal level-1 player, so
        a class is a different start rather than a different rulebook -
        nothing downstream needs to know which one was chosen.
        """
        p = self.player
        p.base_power += klass.get("power", 0)
        p.base_defense += klass.get("defense", 0)
        p.bonus_crit_chance += klass.get("crit", 0.0)
        p.bonus_elemental_chance += klass.get("elemental_chance", 0.0)

        weapon_index = klass.get("start_weapon")
        if weapon_index is not None:
            weapon = C.WEAPON_TYPES[weapon_index]
            p.weapon_name, p.weapon_bonus = weapon["name"], weapon["bonus"]
        armor_index = klass.get("start_armor")
        if armor_index is not None:
            armor = C.ARMOR_TYPES[armor_index]
            p.armor_name, p.armor_bonus = armor["name"], armor["bonus"]

        p.potion_counts = {}
        for potion_id, count in klass.get("start_potions", {}).items():
            p.add_potion(potion_id, count)
        for scroll, count in klass.get("start_scrolls", {}).items():
            p.scrolls[scroll] = p.scrolls.get(scroll, 0) + count

        self._use_class_sprite(klass)

    def _use_class_sprite(self, klass):
        """Swaps the hero on the map to the chosen class's art.

        Picking a class and then still playing as the same figure would
        make the choice feel cosmetic in reverse - the one place it should
        obviously show is the character you are looking at all game.
        Falls back to the original sprite if the art is missing.
        """
        sprite = self._class_sprite(klass["id"], C.PLAYER_SPRITE_HEIGHT)
        if sprite is None:
            return
        self.player_sprite_right = sprite
        self.player_sprite_left = pygame.transform.flip(sprite, True, False)
        w, h = sprite.get_size()
        # Bigger than the old 2x: this is the title screen's centrepiece
        # and the class art is only 16x28 to begin with.
        self.player_sprite_large = pygame.transform.scale(sprite, (w * 3, h * 3))
        self._measure_player_head()

    def _measure_player_head(self):
        """How much empty space the hero's art has above their head.

        The frames are taller than the figure in them, so anchoring the
        YOU marker to the surface leaves a tile-wide gap. Scanning for the
        real top is what get_bounding_rect does, and it is far too slow to
        run per frame - so it runs once, here, whenever the sprite changes.
        """
        sprite = getattr(self, "player_sprite_right", None)
        if sprite is None:
            self._player_head_pad = 0
            return
        try:
            self._player_head_pad = sprite.get_bounding_rect().top
        except pygame.error:
            self._player_head_pad = 0

    def _make_monster(self, x, y, kind, boss=False, elite=None, tier_mult=None):
        """Every monster spawn goes through here.

        Centralising it is what keeps the floor's tier multiplier and the
        run's difficulty applied consistently - summoned minions and
        ambushers used to be created with the bare base stats, so on deep
        floors a boss's adds were harmless.
        """
        d = self._diff()
        if tier_mult is None:
            tier_mult = getattr(self, "tier", {}).get("mult", 1.0)
        return entities.Monster(
            x, y, kind, boss=boss, elite=elite, tier_mult=tier_mult,
            level=getattr(self, "dungeon_level", 1),
            diff_hp=d["enemy_hp"], diff_damage=d["enemy_damage"],
        )

    def start_new_run(self, difficulty=None, char_class=None):
        persistence.delete_save()
        self.save_data = None

        if difficulty is not None:
            self.difficulty = difficulty
            self.settings["difficulty"] = difficulty
            persistence.save_settings(self.settings)
        else:
            self.difficulty = self.settings.get("difficulty", C.DEFAULT_DIFFICULTY)

        if char_class is not None:
            self.char_class = char_class
            self.settings["char_class"] = char_class
            persistence.save_settings(self.settings)
        else:
            self.char_class = self.settings.get("char_class", C.DEFAULT_CLASS)

        self.dungeon_level = 1
        self.log = []
        # The class and the difficulty both scale the health pool, and both
        # do it at creation rather than on read, so every later +max_hp
        # stacks on the adjusted base instead of being rescaled again.
        klass = self._class()
        self.player = entities.Player(
            0, 0, hp_mult=self._diff()["player_hp"] * klass["hp_mult"])
        self._apply_class(klass)
        self.level_history = {}
        self.shake_timer = 0
        self.shake_intensity = 0
        self.flash_timer = 0
        self.move_next_ms = 0
        self.move_held = False
        self.new_best = False
        self.damage_numbers = []
        self.particles = []
        self.hitstop_timer = 0
        self.banners = []
        self.test_room = False
        self.godmode = False
        self.enemies_off = False
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

        self.difficulty = data.get("difficulty", C.DEFAULT_DIFFICULTY)
        self.char_class = data.get("char_class", C.DEFAULT_CLASS)
        # The stats are already in the save; only the art has to be
        # re-applied, or a loaded run comes back as the default hero.
        self._use_class_sprite(self._class())
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
        # "potions" is now a read-only total. A save from before typed
        # potions existed only has that number, so treat the whole stack
        # as healing potions - which is exactly what it was.
        counts = p.get("potion_counts")
        if counts:
            player.potion_counts = {k: int(v) for k, v in counts.items() if int(v) > 0}
        else:
            player.potion_counts = {C.DEFAULT_POTION: p.get("potions", 0)}
        player.selected_potion = p.get("selected_potion", C.DEFAULT_POTION)
        if player.potion_counts.get(player.selected_potion, 0) <= 0:
            player.selected_potion = next(iter(player.potion_counts), C.DEFAULT_POTION)
        player.buffs = {k: int(v) for k, v in p.get("buffs", {}).items()
                        if k in C.BUFFS and int(v) > 0}
        player.shield = p.get("shield", 0)
        player.kills = p["kills"]
        player.facing = p["facing"]
        player.gold = p.get("gold", 0)
        player.scrolls = dict(p.get("scrolls", {"fireball": 0, "teleport": 0, "reveal": 0}))
        player.poison_turns = p.get("poison_turns", 0)
        player.bleed_turns = p.get("bleed_turns", 0)
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
        self.blacksmiths = [entities.Blacksmith(b["x"], b["y"])
                            for b in data.get("blacksmiths", [])]
        self._decor = {tuple(int(v) for v in pos): name
                       for pos, name in data.get("decor", [])}
        self.hazards = {tuple(int(v) for v in pos): kind
                        for pos, kind in data.get("hazards", [])}
        chest = data.get("chest_pos")
        self.chest_pos = tuple(chest) if chest else None
        self.chest_open = data.get("chest_open", False)
        self.chest_is_mimic = data.get("chest_is_mimic", False)
        door = data.get("boss_door_pos")
        self.boss_door_pos = tuple(door) if door else None
        vault = data.get("vault_pos")
        self.vault_pos = tuple(vault) if vault else None
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
        self.particles = []
        self.hitstop_timer = 0
        self.banners = []
        self.test_room = False
        self.godmode = False
        self.enemies_off = False
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
            "difficulty": getattr(self, "difficulty", C.DEFAULT_DIFFICULTY),
            "char_class": getattr(self, "char_class", C.DEFAULT_CLASS),
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
                "potion_counts": dict(p.potion_counts),
                "selected_potion": p.selected_potion,
                "buffs": dict(p.buffs), "shield": p.shield,
                "gold": p.gold, "scrolls": dict(p.scrolls), "poison_turns": p.poison_turns,
                "bleed_turns": p.bleed_turns,
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
            "blacksmiths": [{"x": b.x, "y": b.y} for b in self.blacksmiths],
            "decor": [[list(pos), name] for pos, name in self._decor.items()],
            "hazards": [[list(pos), kind] for pos, kind in self.hazards.items()],
            "chest_pos": list(self.chest_pos) if self.chest_pos else None,
            "chest_open": self.chest_open,
            "chest_is_mimic": self.chest_is_mimic,
            "boss_door_pos": list(self.boss_door_pos) if self.boss_door_pos else None,
            "vault_pos": list(self.vault_pos) if self.vault_pos else None,
            "level_history": {str(level): snap for level, snap in self.level_history.items()},
        }

    @staticmethod
    def _serialize_monster(m):
        return {
            "x": m.x, "y": m.y, "kind": m.kind, "boss": m.is_boss, "hp": m.hp, "awake": m.awake,
            "elite_name": m.elite_name, "is_split_child": m.is_split_child, "enraged": m.enraged,
            # The derived combat stats are stored outright rather than
            # recomputed on load. Rebuilding from kind+elite alone dropped
            # the floor's tier multiplier entirely, so revisiting a deep
            # level (or reloading a deep save) reset every monster to its
            # level-1 base stats while keeping its saved hp - which could
            # leave hp far above max_hp.
            "level": m.level, "max_hp": m.max_hp, "power": m.power,
            "defense": m.defense, "xp_reward": m.xp_reward, "tier_mult": m.tier_mult,
            # Roles a monster was given after construction. Without these
            # a saved treasure guardian comes back as an ordinary elite
            # and its chest unlocks itself.
            "guards_chest": getattr(m, "guards_chest", False),
            "is_mini_boss": getattr(m, "is_mini_boss", False),
            "is_superboss": getattr(m, "is_superboss", False),
            "is_mimic": getattr(m, "is_mimic", False),
            "guards_vault": getattr(m, "guards_vault", False),
            "trap_cooldown": getattr(m, "trap_cooldown", 0),
        }

    @staticmethod
    def _deserialize_monster(m):
        elite = None
        if m.get("elite_name"):
            elite = next((e for e in C.ELITE_MODIFIERS if e["name"] == m["elite_name"]), None)
        monster = entities.Monster(
            m["x"], m["y"], m["kind"], boss=m["boss"], elite=elite,
            tier_mult=m.get("tier_mult", 1.0), level=m.get("level", 1),
        )
        if "max_hp" in m:
            monster.max_hp = m["max_hp"]
            monster.power = m["power"]
            monster.defense = m["defense"]
            monster.xp_reward = m["xp_reward"]
        monster.hp = min(m["hp"], monster.max_hp)
        monster.awake = m["awake"]
        monster.is_split_child = m.get("is_split_child", False)
        monster.enraged = m.get("enraged", False)
        if monster.enraged and "max_hp" not in m:
            # Older saves stored no derived stats, so the enrage bonus has
            # to be re-applied by hand; newer ones already have it baked
            # into the saved power.
            monster.power = int(monster.power * 1.5)
        monster.guards_chest = m.get("guards_chest", False)
        monster.is_mini_boss = m.get("is_mini_boss", False)
        monster.is_superboss = m.get("is_superboss", False)
        monster.is_mimic = m.get("is_mimic", False)
        monster.guards_vault = m.get("guards_vault", False)
        monster.trap_cooldown = m.get("trap_cooldown", 0)
        # The superboss's title is part of its name, and that name was
        # built from a translated prefix - reuse the saved one rather than
        # rebuilding it, or it reverts to a plain boss name on load.
        if m.get("name"):
            monster.name = m["name"]
        return monster

    @staticmethod
    def _serialize_item(i):
        return {
            "x": i.x, "y": i.y, "kind": i.kind, "name": i.name, "char": i.char,
            "color": list(i.color), "bonus": i.bonus, "scroll_type": i.scroll_type,
            "rarity_id": i.rarity_id, "element_id": i.element_id,
            "potion_id": i.potion_id,
        }

    @staticmethod
    def _deserialize_item(i):
        return entities.Item(
            i["x"], i["y"], i["kind"], i["name"], i["char"], tuple(i["color"]),
            bonus=i["bonus"], scroll_type=i.get("scroll_type"), rarity_id=i.get("rarity_id"),
            element_id=i.get("element_id"), potion_id=i.get("potion_id"),
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
            "blacksmiths": [{"x": b.x, "y": b.y} for b in self.blacksmiths],
            # Purely cosmetic, but it has to be remembered: regenerating it
            # on return would move every skull and banner in the level, and
            # a room rearranging itself behind the player's back reads as a
            # bug rather than as decoration.
            "decor": [[list(pos), name] for pos, name in self._decor.items()],
            "hazards": [[list(pos), kind] for pos, kind in self.hazards.items()],
            "chest_pos": list(self.chest_pos) if self.chest_pos else None,
            "chest_open": self.chest_open,
            "chest_is_mimic": self.chest_is_mimic,
            "boss_door_pos": list(self.boss_door_pos) if self.boss_door_pos else None,
            "vault_pos": list(self.vault_pos) if self.vault_pos else None,
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
        self.blacksmiths = [entities.Blacksmith(b["x"], b["y"])
                            for b in snap.get("blacksmiths", [])]
        self._decor = {tuple(int(v) for v in pos): name
                       for pos, name in snap.get("decor", [])}
        self.hazards = {tuple(int(v) for v in pos): kind
                        for pos, kind in snap.get("hazards", [])}
        chest = snap.get("chest_pos")
        self.chest_pos = tuple(chest) if chest else None
        self.chest_open = snap.get("chest_open", False)
        self.chest_is_mimic = snap.get("chest_is_mimic", False)
        door = snap.get("boss_door_pos")
        self.boss_door_pos = tuple(door) if door else None
        vault = snap.get("vault_pos")
        self.vault_pos = tuple(vault) if vault else None

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
        # Rotate except when this floor starts a new theme - then the
        # theme's own track introduces it.
        self._play_tier_music(
            self.tier, rotate=(self.dungeon_level - 1) % C.LEVELS_PER_TIER != 0)

        self.monsters = []
        self.items = []
        self.merchants = []
        self.blacksmiths = []
        self.traps = {}
        self.hazards = {}
        self.shrine_pos = None
        self.chest_pos = None
        self.chest_open = False
        self.chest_is_mimic = False
        self.boss_door_pos = None
        self.vault_pos = None
        self.damage_numbers = []
        self.particles = []
        self.hitstop_timer = 0
        self.banners = []
        self._scatter_decor()
        self._populate_level()

        self._recompute_fov()

    # Wall pieces go on wall faces the player can actually see (a wall with
    # open floor below it), ground pieces on plain floor. Weights are low on
    # purpose: sparse clutter reads as "a lived-in dungeon", dense clutter
    # reads as noise and makes it hard to spot items and monsters.
    WALL_DECOR = ("wall_banner_red", "wall_banner_blue", "wall_banner_green",
                  "wall_banner_yellow", "wall_hole_1", "wall_hole_2", "wall_goo")
    FLOOR_DECOR = ("skull", "crate", "column")

    def blocks_movement(self, x, y):
        """A wall, or a solid object standing on the floor.

        The single answer to "can anything be here" - movement, spawning
        and placement all ask this rather than each testing the grid and
        then forgetting about the crates.
        """
        if not dungeon.is_walkable(self.grid, x, y):
            return True
        return self._decor.get((x, y)) in C.BLOCKING_DECOR

    def _reachable_from(self, start):
        """Every tile that can be walked to from start.

        A plain flood fill with the solid decorations treated as walls.
        Needed while placing those decorations: a crate dropped in a
        one-tile corridor can cut off a whole corner of the level, and
        there is no way to see that by eye.
        """
        if start is None or self.blocks_movement(*start):
            return set()
        seen = {start}
        stack = [start]
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in seen or self.blocks_movement(nx, ny):
                    continue
                seen.add((nx, ny))
                stack.append((nx, ny))
        return seen

    def _all_reachable(self, start, targets):
        reachable = self._reachable_from(start)
        return all(t is None or t in reachable for t in targets)

    def _scatter_decor(self):
        """Picks the tiles to overlay on the map.

        Chosen once per level and stored, not rolled inside the map cache
        repaint - the cache is rebuilt on every field-of-view change, so
        rolling there would reshuffle the decorations as the player walks.

        Most of it is scenery, but crates and columns are solid (see
        constants.BLOCKING_DECOR). Each of those is placed provisionally
        and taken straight back if it would cut the level in two - which
        one crate in the wrong corridor is quite enough to do.
        """
        self._decor = {}
        if not self._tile_sources:
            return
        blocked = {self.stairs_pos, self.up_stairs_pos}
        start = (self.player.x, self.player.y)
        # A solid object may cost the level exactly the tile it stands on
        # and nothing else. Checking only the stairs was not enough: a
        # crate can seal off a corner that has no stairs in it, and the
        # merchant, an item or a monster then spawns in there afterwards
        # with no way to reach them.
        reachable = self._reachable_from(start)
        for room in self.rooms:
            for _ in range(random.randint(0, 3)):
                x, y = self._random_floor_in_room(room)
                if (x, y) in blocked or (x, y) in self._decor or (x, y) == start:
                    continue
                # Never on the room's centre: that is where stairs, the
                # merchant and the shrine get placed.
                if (x, y) == room.center():
                    continue
                piece = random.choice(self.FLOOR_DECOR)
                self._decor[(x, y)] = piece
                if piece not in C.BLOCKING_DECOR:
                    continue
                shrunk = self._reachable_from(start)
                if len(shrunk) == len(reachable) - 1:
                    reachable = shrunk
                else:
                    del self._decor[(x, y)]
        for _ in range(C.MAP_WIDTH):
            x = random.randrange(1, C.MAP_WIDTH - 1)
            y = random.randrange(1, C.MAP_HEIGHT - 1)
            if not self._is_wall(x, y) or self._is_wall(x, y + 1):
                continue
            if (x, y) in self._decor:
                continue
            self._decor[(x, y)] = random.choice(self.WALL_DECOR)

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
            if self.blocks_movement(x, y) or self._is_occupied(x, y):
                continue
            kind = random.choices(monster_kinds, weights=weights, k=1)[0]
            self.monsters.append(self._make_monster(
                x, y, kind, elite=self._maybe_elite()))
            # Pack animals arrive as a pack. Rolled here rather than by
            # raising their spawn weight, so a swarm is several of them
            # together in one place - which is what makes it a swarm
            # rather than just more rats scattered around the floor.
            swarm = C.MONSTER_TYPES[kind].get("swarms")
            if swarm and random.random() < 0.5:
                self._spawn_swarm(x, y, kind, random.randint(*swarm) - 1)

        if self.dungeon_level % 5 == 0:
            bx, by = self.stairs_pos
            tier = (self.dungeon_level // 5 - 1) % len(C.BOSS_KIND_CYCLE)
            boss_kind = C.BOSS_KIND_CYCLE[tier]
            boss = self._make_monster(bx, by, boss_kind, boss=True)
            if self.dungeon_level >= C.SUPERBOSS_LEVEL and self.dungeon_level % C.SUPERBOSS_LEVEL == 0:
                self._promote_to_superboss(boss)
            self.monsters.append(boss)
            self._announce("log_boss_guards", C.COLOR_BOSS)
            if self.dungeon_level >= C.BOSS_DOOR_MIN_LEVEL:
                self._lock_boss_door()
        elif self.dungeon_level % C.MINI_BOSS_EVERY == 0:
            self._spawn_mini_boss(spawnable_rooms)

        if self.dungeon_level >= C.TREASURE_MIN_LEVEL and random.random() < C.TREASURE_ROOM_CHANCE:
            self._make_treasure_room(spawnable_rooms)

        if self.dungeon_level >= C.VAULT_MIN_LEVEL and random.random() < C.VAULT_CHANCE_PER_LEVEL:
            self._make_vault(spawnable_rooms)

        if self.dungeon_level >= C.HAZARD_MIN_LEVEL:
            self._scatter_hazards(spawnable_rooms)

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
                if self._tile_is_free(x, y):
                    self.traps[(x, y)] = random.choice(list(C.TRAP_TYPES.keys()))

        if random.random() < C.MERCHANT_CHANCE_PER_LEVEL:
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if self._tile_is_free(x, y):
                self.merchants.append(entities.Merchant(x, y))

        if (self.dungeon_level >= C.BLACKSMITH_MIN_LEVEL
                and random.random() < C.BLACKSMITH_CHANCE_PER_LEVEL):
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if self._tile_is_free(x, y):
                self.blacksmiths.append(entities.Blacksmith(x, y))

        if self.dungeon_level >= 2 and random.random() < C.SHRINE_CHANCE_PER_LEVEL:
            room = random.choice(spawnable_rooms)
            x, y = self._random_floor_in_room(room)
            if self._tile_is_free(x, y):
                self.shrine_pos = (x, y)

    def _tile_is_free(self, x, y, ignore=None):
        """Nothing else has claimed this tile.

        One predicate for every placement, because they were each
        open-coding a slightly different subset - traps checked the stairs
        but not the merchant, the shrine checked the merchant but not the
        chest - and each new feature made the gaps worse. A trap hidden
        under a lava tile, in particular, is two hits for one step with no
        way to see the second coming.
        """
        if self.blocks_movement(x, y):
            return False
        if self._is_occupied(x, y, ignore=ignore):
            return False
        if (x, y) in self.traps or (x, y) in self.hazards:
            return False
        if (x, y) in (self.stairs_pos, self.up_stairs_pos, self.chest_pos):
            return False
        if any((m.x, m.y) == (x, y) for m in self.merchants):
            return False
        if self.shrine_pos == (x, y):
            return False
        return True

    def _promote_to_superboss(self, boss):
        """Turns the deepest boss into something in a class of its own.

        Not a separate monster type: it reuses the boss whose floor it is,
        so its signature move (enrage, summon, web) still applies - it is
        the same fight the player has already learned, several times
        harder, which is a better final test than a new set of rules.
        """
        boss.max_hp = int(boss.max_hp * C.SUPERBOSS_MULT)
        boss.hp = boss.max_hp
        boss.power = int(boss.power * C.SUPERBOSS_MULT)
        boss.defense = int(boss.defense * 1.5)
        boss.xp_reward = int(boss.xp_reward * C.SUPERBOSS_MULT)
        boss.is_superboss = True

    def _spawn_mini_boss(self, rooms):
        """A landmark fight on the floors between the real bosses.

        Marked as an elite so it gets the existing halo and tougher stats
        for free, but scaled beyond any normal elite and placed in a room
        of its own rather than mixed into the general spawn.
        """
        room = random.choice(rooms)
        x, y = self._random_floor_in_room(room)
        if self.blocks_movement(x, y) or self._is_occupied(x, y):
            return
        kind = random.choice(list(C.MONSTER_TYPES.keys()))
        monster = self._make_monster(x, y, kind, elite=random.choice(C.ELITE_MODIFIERS))
        monster.max_hp = int(monster.max_hp * C.MINI_BOSS_MULT)
        monster.hp = monster.max_hp
        monster.power = int(monster.power * C.MINI_BOSS_MULT)
        monster.xp_reward = int(monster.xp_reward * C.MINI_BOSS_XP_MULT)
        monster.is_mini_boss = True
        self.monsters.append(monster)
        self._announce("log_mini_boss", C.COLOR_BOSS, monster=self._monster_named(monster, "nom"))

    def _spawn_swarm(self, x, y, kind, count):
        """Fills the tiles around (x, y) with more of the same kind."""
        spots = [(x + dx, y + dy)
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
        random.shuffle(spots)
        for sx, sy in spots:
            if count <= 0:
                break
            if self.blocks_movement(sx, sy) or self._is_occupied(sx, sy):
                continue
            self.monsters.append(self._make_monster(sx, sy, kind))
            count -= 1

    def _make_treasure_room(self, rooms):
        """A chest with something good in it, and something standing on it.

        The chest cannot be opened while its guardian lives, so this is a
        fight the player chooses to pick rather than one that walks into
        them - which is the whole appeal of a treasure room.
        """
        room = random.choice(rooms)
        x, y = self._random_floor_in_room(room)
        if self.blocks_movement(x, y) or self._is_occupied(x, y):
            return
        if (x, y) in (self.stairs_pos, self.up_stairs_pos):
            return
        if any((i.x, i.y) == (x, y) for i in self.items):
            return

        guard_spot = next(
            ((gx, gy) for gx, gy in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
             if not self.blocks_movement(gx, gy) and not self._is_occupied(gx, gy)),
            None)
        if guard_spot is None:
            return

        self.chest_pos = (x, y)
        self.chest_open = False

        # Sometimes the chest is the monster. It uses the same art and
        # sits in the same place as a real one, so there is no tell from
        # across the room - the point is that opening a chest stops being
        # a free action once the player knows this can happen.
        if (self.dungeon_level >= C.MIMIC_MIN_LEVEL
                and random.random() < C.MIMIC_CHANCE):
            self.chest_is_mimic = True
            return

        kind = random.choice(list(C.MONSTER_TYPES.keys()))
        guard = self._make_monster(guard_spot[0], guard_spot[1], kind,
                                   elite=random.choice(C.ELITE_MODIFIERS))
        guard.max_hp = int(guard.max_hp * C.TREASURE_GUARD_MULT)
        guard.hp = guard.max_hp
        guard.guards_chest = True
        self.monsters.append(guard)

    def _spring_mimic(self):
        """Turns the fake chest into the monster it always was."""
        x, y = self.chest_pos
        kind = random.choice(list(C.MONSTER_TYPES.keys()))
        mimic = self._make_monster(x, y, kind, elite=random.choice(C.ELITE_MODIFIERS))
        mimic.max_hp = int(mimic.max_hp * C.MIMIC_MULT)
        mimic.hp = mimic.max_hp
        mimic.power = int(mimic.power * C.MIMIC_MULT)
        mimic.awake = True
        mimic.is_mimic = True
        # It gets the first hit - that is the cost of opening it blind.
        self.monsters.append(mimic)
        self.chest_is_mimic = False
        self.chest_pos = None
        self.chest_open = False
        self.sounds.play("boss")
        self.shake_timer, self.shake_intensity = 10, 5
        self._announce("log_mimic", C.COLOR_DANGER, monster=self._monster_named(mimic, "nom"))
        self._attack(mimic, self.player)

    # The test room's cheat panel. Kept as data so the screen, the keys
    # and the tap targets cannot drift apart, and so adding a tool is one
    # entry rather than three edits.
    TOOL_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                 pygame.K_5, pygame.K_6, pygame.K_7)
    TOOL_GOLD_STEP = 250
    TOOL_HP_STEP = 10

    def _tools(self):
        p = self.player
        return [
            ("gold_up", self.t("tool_gold_up", amount=self.TOOL_GOLD_STEP)),
            ("gold_down", self.t("tool_gold_down", amount=self.TOOL_GOLD_STEP)),
            ("hp_up", self.t("tool_hp_up", amount=self.TOOL_HP_STEP)),
            ("hp_down", self.t("tool_hp_down", amount=self.TOOL_HP_STEP)),
            ("hp_full", self.t("tool_hp_full")),
            ("godmode", self.t("tool_godmode_off" if self.godmode
                               else "tool_godmode_on")),
            ("enemies", self.t("tool_enemies_on" if self.enemies_off
                               else "tool_enemies_off")),
        ]

    def _use_tool(self, index):
        tools = self._tools()
        if index < 0 or index >= len(tools):
            return
        tool = tools[index][0]
        p = self.player

        if tool == "gold_up":
            p.gold += self.TOOL_GOLD_STEP
        elif tool == "gold_down":
            p.gold = max(0, p.gold - self.TOOL_GOLD_STEP)
        elif tool == "hp_up":
            # Raises the ceiling too, so "more health" keeps working past
            # full rather than silently doing nothing.
            p.max_hp += self.TOOL_HP_STEP
            p.hp += self.TOOL_HP_STEP
        elif tool == "hp_down":
            # Never to zero: this is a knob for trying things out, and a
            # knob that can end the run by one tap too many is a trap.
            p.hp = max(1, p.hp - self.TOOL_HP_STEP)
        elif tool == "hp_full":
            p.hp = p.max_hp
        elif tool == "godmode":
            self.godmode = not self.godmode
            self._announce("log_godmode_on" if self.godmode else "log_godmode_off",
                           C.COLOR_ACCENT)
        elif tool == "enemies":
            # Switched off rather than deleted: the monsters stay in the
            # list, so turning them back on restores the same room instead
            # of an empty one you would have to rebuild.
            self.enemies_off = not self.enemies_off
            self.needs_redraw = True
            self._announce("log_enemies_off" if self.enemies_off else "log_enemies_on",
                           C.COLOR_ACCENT)
        self.sounds.play("equip")

    def _render_tools(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("tools_title"), color=C.COLOR_ACCENT)

        p = self.player
        status = self.t("tools_status", hp=max(0, p.hp), max_hp=p.max_hp,
                        gold=p.gold,
                        god=self.t("on" if self.godmode else "off"),
                        enemies=self.t("off" if self.enemies_off else "on"))
        line = self.f_body.render(status, True, C.COLOR_HUD_TEXT)
        self.screen.blit(line, line.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += line.get_height() + self.gap_m

        tools = self._tools()
        bottom = C.SCREEN_HEIGHT - self.pad - self.btn_h - self.gap_l
        row_h = max(self.btn_h // 2,
                    min(self.btn_h,
                        (bottom - y - self.btn_gap * (len(tools) - 1)) // len(tools)))
        use_w = self._btn_w(self.t("btn_use"), self.f_sm)
        for i, (tool_id, label) in enumerate(tools):
            color = C.COLOR_ACCENT if tool_id == "godmode" and self.godmode else C.COLOR_HUD_TEXT
            text = self.f_sm.render(f"{i + 1}. {label}", True, color)
            self.screen.blit(text, text.get_rect(midleft=(self.pad, y + row_h // 2)))
            self._draw_tap_button(
                (C.SCREEN_WIDTH - self.pad - use_w, y, use_w, row_h),
                self.t("btn_use"), self.TOOL_KEYS[i], font=self.f_sm,
                primary=(tool_id == "godmode" and self.godmode))
            y += row_h + self.btn_gap

        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)],
                         C.SCREEN_HEIGHT - self.pad - self.btn_h)

    def start_test_room(self):
        """One open floor holding one of everything the game can produce.

        Not a debug dump: it is laid out in rows so each group is
        recognisable, and it is a real playable level - the monsters
        fight, the traps trigger, the smith trades. It exists so a change
        to any of this can be looked at without playing twenty floors
        hoping the right thing spawns.
        """
        self.start_new_run(self.settings.get("difficulty", C.DEFAULT_DIFFICULTY),
                           self.settings.get("char_class", C.DEFAULT_CLASS))
        self.dungeon_level = 12
        self.test_room = True
        self._build_test_room()
        self._announce("log_testroom", C.COLOR_ACCENT)
        self.state = "playing"

    def _build_test_room(self):
        w, h = C.MAP_WIDTH, C.MAP_HEIGHT
        self.grid = [[dungeon.WALL for _ in range(w)] for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                self.grid[y][x] = dungeon.FLOOR
        self.rooms = [dungeon.Room(1, 1, w - 2, h - 2)]
        self.tier = self._tier_for_level(self.dungeon_level)
        # Rotate except when this floor starts a new theme - then the
        # theme's own track introduces it.
        self._play_tier_music(
            self.tier, rotate=(self.dungeon_level - 1) % C.LEVELS_PER_TIER != 0)

        self.monsters = []
        self.items = []
        self.merchants = []
        self.blacksmiths = []
        self.traps = {}
        self.hazards = {}
        self.damage_numbers = []
        self.particles = []
        self.hitstop_timer = 0
        self.shrine_pos = None
        self.chest_pos = None
        self.chest_open = False
        self.chest_is_mimic = False
        self.boss_door_pos = None
        self.vault_pos = None
        self._decor = {}
        self.level_history = {}

        self.player.x, self.player.y = 2, h // 2
        self.player.snap()
        self.stairs_pos = (w - 3, h // 2)
        self.up_stairs_pos = (2, h - 3)

        kinds = list(C.MONSTER_TYPES.keys())
        # Four tiles apart, not two: every monster now wears a nameplate
        # and at two tiles the names sit on top of each other, which is
        # exactly what this room exists to let you check.
        step = 4

        # Row 1: one plain monster of every kind.
        for i, kind in enumerate(kinds):
            self.monsters.append(self._make_monster(4 + i * step, 2, kind))
        # Row 2: the same kinds as elites, one per elite modifier.
        for i, elite in enumerate(C.ELITE_MODIFIERS):
            self.monsters.append(self._make_monster(
                4 + i * step, 5, kinds[i % len(kinds)], elite=elite))
        # Row 3: the special ones - mini-boss, boss, superboss, mimic.
        mini = self._make_monster(4, 8, "orc", elite=C.ELITE_MODIFIERS[0])
        mini.is_mini_boss = True
        mini.max_hp = int(mini.max_hp * C.MINI_BOSS_MULT)
        mini.hp = mini.max_hp
        self.monsters.append(mini)
        self.monsters.append(self._make_monster(4 + step, 8, "skeleton", boss=True))
        superboss = self._make_monster(4 + 2 * step, 8, "spider", boss=True)
        self._promote_to_superboss(superboss)
        self.monsters.append(superboss)
        # A mimic already sprung. An unsprung one is by design identical
        # to the real chest further down, so showing it as a chest would
        # show nothing; what is worth seeing is what comes out of it.
        mimic = self._make_monster(4 + 3 * step, 8, "slime",
                                   elite=C.ELITE_MODIFIERS[1])
        mimic.is_mimic = True
        mimic.awake = True
        self.monsters.append(mimic)

        # Row 4: every trap and every hazard, side by side. Traps are
        # invisible until stepped on - that is the point of them - so the
        # left half of this row looks empty and is meant to.
        for i, trap in enumerate(C.TRAP_TYPES):
            self.traps[(4 + i * 2, 11)] = trap
        for i, hazard in enumerate(C.HAZARD_TYPES):
            self.hazards[(16 + i * 2, 11)] = hazard

        # Row 5: one of each item kind, plus a spread of potions.
        for i, kind in enumerate(("weapon", "armor", "scroll", "gold")):
            self._spawn_item_at(5 + i * 2, 14, kind)
        for i, info in enumerate(C.POTION_TYPES[:12]):
            x, y = 14 + (i % 6) * 2, 14 + (i // 6) * 2
            self.items.append(entities.Item(
                x, y, "potion", info["name"], "!", info["color"],
                bonus=info["effect"].get("heal", 0), potion_id=info["id"]))

        # Row 6: the people and the fixtures.
        self.merchants.append(entities.Merchant(4, 19))
        self.blacksmiths.append(entities.Blacksmith(8, 19))
        self.shrine_pos = (12, 19)
        self.chest_pos = (16, 19)
        guard = self._make_monster(17, 19, "orc", elite=C.ELITE_MODIFIERS[2])
        guard.guards_chest = True
        self.monsters.append(guard)
        # The vault crowd, off to the right, so a guarded pile can be seen
        # next to the single guarded chest.
        self.vault_pos = (26, 19)
        for i in range(3):
            keeper = self._make_monster(24 + i * 2, 19, kinds[i % len(kinds)],
                                        elite=C.ELITE_MODIFIERS[i % len(C.ELITE_MODIFIERS)])
            keeper.guards_vault = True
            keeper.awake = True
            self.monsters.append(keeper)
        self._spawn_item_at(26, 17, "gold")

        # Every decoration the generator can place, in a row along the top.
        for i, name in enumerate(self.FLOOR_DECOR):
            self._decor[(4 + i * 2, 21)] = name
        for i, name in enumerate(self.WALL_DECOR):
            self._decor[(12 + i * 2, 21)] = name

        # The barred door, on the stairs, with the boss above still alive.
        self.boss_door_pos = self.stairs_pos

        # Enough gold and flasks to actually try the smith and the bag.
        self.player.gold = 2000
        for info in C.POTION_TYPES:
            self.player.add_potion(info["id"], 2)
        for scroll in self.player.scrolls:
            self.player.scrolls[scroll] = 5
        if self.player.weapon_name == "Fists":
            weapon = C.WEAPON_TYPES[1]
            self.player.weapon_name = weapon["name"]
            self.player.weapon_bonus = weapon["bonus"]
        if self.player.armor_name == "None":
            armor = C.ARMOR_TYPES[0]
            self.player.armor_name = armor["name"]
            self.player.armor_bonus = armor["bonus"]

        self._map_cache = None
        self._minimap_cache = None
        self._recompute_fov()

    def _make_vault(self, rooms):
        """A pile of loot with a crowd standing on it.

        Several elites at once rather than one big monster: a crowd is a
        different problem from a boss - you cannot trade blows with it,
        you have to fight it in a doorway or thin it out - and nothing
        else in this game posed that. Everything is visible from the room
        entrance, so walking in is a decision rather than an ambush.
        """
        room = random.choice(rooms)
        cx, cy = room.center()
        if self.blocks_movement(cx, cy):
            return
        placed = 0
        for kind in ("gold", "gold", "weapon", "armor", "scroll", "potion"):
            spot = self._free_spot_near(cx, cy, radius=2)
            if spot is None:
                break
            self._spawn_item_at(spot[0], spot[1], kind)
            placed += 1
        if not placed:
            return

        for _ in range(random.randint(*C.VAULT_GUARDS)):
            spot = self._free_spot_near(cx, cy, radius=3)
            if spot is None:
                break
            kind = random.choice(list(C.MONSTER_TYPES.keys()))
            guard = self._make_monster(spot[0], spot[1], kind,
                                       elite=random.choice(C.ELITE_MODIFIERS))
            guard.max_hp = int(guard.max_hp * C.VAULT_GUARD_MULT)
            guard.hp = guard.max_hp
            guard.power = int(guard.power * C.VAULT_GUARD_MULT)
            # Awake from the start: a guard that has to be woken up can be
            # picked off one at a time, which defeats the point.
            guard.awake = True
            guard.guards_vault = True
            self.monsters.append(guard)
        self.vault_pos = (cx, cy)

    def _free_spot_near(self, cx, cy, radius):
        """A walkable, unclaimed tile within `radius`, nearest first."""
        candidates = [(cx + dx, cy + dy)
                      for dx in range(-radius, radius + 1)
                      for dy in range(-radius, radius + 1)]
        candidates.sort(key=lambda p: abs(p[0] - cx) + abs(p[1] - cy))
        for x, y in candidates:
            if not self._tile_is_free(x, y):
                continue
            if any((i.x, i.y) == (x, y) for i in self.items):
                continue
            if (x, y) == (self.player.x, self.player.y):
                continue
            return x, y
        return None

    def _chest_guard_alive(self):
        return any(getattr(m, "guards_chest", False) and m.is_alive()
                   for m in self.monsters)

    def _open_chest(self):
        """Empties the chest onto the floor around it - or springs it.

        Drops real items rather than granting them silently, so the
        contents are picked up the same way as everything else and the
        player can see what they got before touching it.
        """
        if self.chest_open or self.chest_pos is None:
            return
        if self.chest_is_mimic:
            self._spring_mimic()
            return
        if self._chest_guard_alive():
            self._announce("log_chest_guarded", C.COLOR_DANGER)
            return
        self.chest_open = True
        self.sounds.play("equip")
        cx, cy = self.chest_pos
        spots = [(cx, cy)] + [(cx + dx, cy + dy)
                              for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        kinds = ["gold", "potion", random.choice(("weapon", "armor")), "scroll"]
        for kind in kinds:
            spot = next((s for s in spots
                         if not self.blocks_movement(*s)
                         and not any((i.x, i.y) == s for i in self.items)), None)
            if spot is None:
                break
            self._spawn_item_at(spot[0], spot[1], kind)
        self._announce("log_chest_opened", C.COLOR_ACCENT)

    def _lock_boss_door(self):
        """Bars the way down until the boss is dead.

        Stored as a position rather than a wall tile: the grid stays
        walkable underneath, so nothing about pathfinding, the field of
        view or the map cache has to learn about a door that comes and
        goes. The block is enforced in _player_turn instead.
        """
        self.boss_door_pos = self.stairs_pos

    def _boss_door_blocked(self):
        if self.boss_door_pos is None:
            return False
        return any(m.is_boss and m.is_alive() for m in self.monsters)

    def _scatter_hazards(self, rooms):
        """Standing hazards, unlike traps: visible, and meant to be avoided."""
        available = [(k, v) for k, v in C.HAZARD_TYPES.items()
                     if v["min_level"] <= self.dungeon_level]
        if not available:
            return
        for room in rooms:
            if random.random() >= C.HAZARD_CHANCE_PER_ROOM:
                continue
            kind, _info = random.choice(available)
            for _ in range(random.randint(1, 3)):
                x, y = self._random_floor_in_room(room)
                if self._tile_is_free(x, y):
                    self.hazards[(x, y)] = kind

    def _trigger_hazard(self, pos):
        kind = self.hazards.get(pos)
        if kind is None:
            return
        info = C.HAZARD_TYPES[kind]
        # A collapsing floor gives way once and is then just a hole you
        # have already fallen through; lava and spikes stay dangerous.
        if info.get("one_shot"):
            del self.hazards[pos]
            self._map_cache = None
            self._minimap_cache = None
        damage = self._hurt_player(info["damage"])
        if not damage:
            return
        self._spawn_damage_number(self.player.x, self.player.y, str(damage), info["color"])
        self._announce(f"log_hazard_{kind}", info["color"], dmg=damage)
        self.sounds.play("player_hurt")
        self.shake_timer, self.shake_intensity = 6, 4
        if info.get("burn"):
            self.player.bleed_turns = max(self.player.bleed_turns, info["burn"])
        if info.get("bleed"):
            self.player.bleed_turns = max(self.player.bleed_turns, info["bleed"])
        if self.player.hp <= 0:
            self.add_log(self.t("log_you_died"))
            self.sounds.play("death")
            self.state = "dead"
            self._finalize_run()

    def _spawn_item_at(self, x, y, kind):
        """Places one item at an exact tile, bypassing the room roll."""
        room = dungeon.Room(x, y, 1, 1)
        self._spawn_item(room, kind)

    def _spawn_item(self, room, kind):
        x, y = self._random_floor_in_room(room)
        if self.blocks_movement(x, y) or self._is_occupied(x, y):
            return
        if any((i.x, i.y) == (x, y) for i in self.items):
            return

        if kind == "potion":
            potion_id = self._roll_potion()
            info = C.POTION_BY_ID[potion_id]
            self.items.append(entities.Item(
                x, y, "potion", info["name"], "!", info["color"],
                bonus=info["effect"].get("heal", 0), potion_id=potion_id,
            ))
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
        if getattr(self, "player", None) is not None and self.player.has_buff_flag("luck"):
            # Luck rolls twice and keeps the better tier, rather than
            # reweighting the table: it cannot conjure a rarity that is
            # not unlocked yet, and it stays meaningful at every depth.
            picks = random.choices(available, weights=[t["weight"] for t in available], k=2)
            return max(picks, key=lambda t: available.index(t))
        return random.choices(available, weights=[t["weight"] for t in available], k=1)[0]

    def _random_floor_in_room(self, room):
        x = random.randint(room.x1, room.x2 - 1)
        y = random.randint(room.y1, room.y2 - 1)
        return x, y

    def _random_floor_tile(self):
        for _ in range(200):
            x = random.randint(0, C.MAP_WIDTH - 1)
            y = random.randint(0, C.MAP_HEIGHT - 1)
            if not self.blocks_movement(x, y) and not self._is_occupied(x, y):
                return x, y
        return None

    def _is_occupied(self, x, y, ignore=None):
        """Whether something is standing here.

        `ignore` excludes one entity - needed by anything that asks about
        the tile it is itself standing on, such as a trap-setter deciding
        whether it can leave a trap behind.
        """
        if (x, y) == (self.player.x, self.player.y):
            return True
        if not self.enemies_off and any(
                (m.x, m.y) == (x, y) for m in self.monsters if m is not ignore):
            return True
        if any((m.x, m.y) == (x, y) for m in getattr(self, "merchants", [])
               if m is not ignore):
            return True
        if any((b.x, b.y) == (x, y) for b in getattr(self, "blacksmiths", [])
               if b is not ignore):
            return True
        return False

    def _recompute_fov(self):
        self.visible = fov.compute_fov(self.grid, self.player.x, self.player.y, C.FOV_RADIUS)
        self.explored |= self.visible
        # The cached tile surface is painted from exactly these two sets
        # (see _rebuild_map_cache), so this is the single place that has
        # to invalidate it - every map/level change routes through here.
        self._map_cache = None
        self._minimap_cache = None
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

    def _pick_track(self, tier, rotate):
        """Which track to play next.

        Entering a theme plays that theme's own track, so a new area still
        announces itself. Every other floor picks a different one from the
        pool - three tracks over five themes meant a long run heard the
        same three and a half minutes on repeat for its whole length.
        Deliberately driven by descending rather than by detecting the end
        of a track: the old "music restarts itself every second" bug came
        from trusting mixer.get_busy(), and nothing here asks it anything.
        """
        theme_track = tier.get("music")
        current = getattr(self, "_music_track", None)
        # Never the track already playing, even when a new theme would
        # otherwise introduce itself with it - two themes share a track,
        # so "entering the Caverns" could leave the music untouched, which
        # is exactly the repetition this is meant to break up.
        if not rotate and theme_track != current:
            return theme_track
        others = [t for t in C.MUSIC_TRACKS if t != current]
        return random.choice(others) if others else theme_track

    def _play_tier_music(self, tier, rotate=False):
        """Start the background track, looping until the next floor."""
        if not self.settings.get("music", True):
            return
        track = self._pick_track(tier, rotate)
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
        """Recover only from music that never started, never police a
        track that is already playing.

        The first version restarted whenever pygame reported the mixer as
        not busy. On the device that reported false negatives, so it
        reloaded and replayed the track roughly once a second - heard as
        the music restarting from the top over and over. Two guards now
        make that impossible: a track we successfully started is left
        alone entirely, and no restart may happen within
        MUSIC_RETRY_COOLDOWN_MS of the last one.
        """
        if not self.settings.get("music", True):
            return
        if self._music_track is not None:
            return          # something is playing - hands off
        now = pygame.time.get_ticks()
        if now - self._music_retry_ms < MUSIC_RETRY_COOLDOWN_MS:
            return
        self._music_retry_ms = now
        self._play_tier_music(getattr(self, "tier", None) or C.DUNGEON_TIERS[0])

    def _build_ui_metrics(self):
        # Absolute sizes for the menu screens, scaled from the canvas
        # height so a desktop window or a low-res phone stays in
        # proportion. See constants.UI_REF_HEIGHT for the reference.
        k = C.SCREEN_HEIGHT / C.UI_REF_HEIGHT
        if not ON_ANDROID:
            k *= C.UI_DESKTOP_FACTOR
        # The finished touch buttons were drawn with the fonts and sizes
        # this is about to replace.
        self._touch_btn_cache = {}
        # A real touch target on phones, in canvas pixels - so it follows
        # the render scale, which is what turns canvas pixels into screen
        # pixels.
        floor = int(120 * getattr(self, "render_scale", 1.0)) if ON_ANDROID else 0

        def px(n, minimum=0):
            return max(minimum, int(round(n * k)))

        self.f_title = pygame.font.Font(None, px(C.FONT_TITLE))
        self.f_title.set_bold(True)
        self.f_h1 = pygame.font.Font(None, px(C.FONT_H1))
        self.f_h1.set_bold(True)
        self.f_body = pygame.font.Font(None, px(C.FONT_BODY))
        self.f_sm = pygame.font.Font(None, px(C.FONT_SM))
        self.f_xs = pygame.font.Font(None, px(C.FONT_XS))
        # Nameplates float over the dungeon at tile scale, not UI scale, so
        # this one is sized against the tile rather than the ladder above -
        # at f_xs a name is wider than the monster it belongs to.
        self.f_tiny = pygame.font.Font(None, max(11, int(C.TILE_SIZE * 0.62)))

        self.btn_h = px(C.BTN_H, floor)
        # Android's 48dp minimum touch target, in canvas pixels. Screens
        # that have to squeeze rows in may shrink to this and no further.
        self.btn_h_min = max(floor, px(C.BTN_H_MIN))
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

    def _button_row(self, entries, y, height=None, font=None, primary_first=False):
        """Lay out (label, key) buttons left-to-right as one centred row.

        Widths come from the measured label, so a longer translation
        widens its own button instead of being clipped.
        """
        f = font or self.f_body
        h = height or self.btn_h
        widths = [self._btn_w(label, f) for label, _ in entries]
        total = sum(widths) + self.btn_gap * (len(entries) - 1)
        x = C.SCREEN_WIDTH // 2 - total // 2
        for i, ((label, key), w) in enumerate(zip(entries, widths)):
            self._draw_tap_button((x, y, w, h), label, key, font=f,
                                  primary=(primary_first and i == 0))
            x += w + self.btn_gap
        return h

    def _screen_header(self, title, color=None, y=None):
        """Draw a screen title with an accent rule; returns the y below it."""
        y = self.pad if y is None else y
        surf = self.f_title.render(title, True, color or C.COLOR_ACCENT)
        rect = surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y))
        self.screen.blit(surf, rect)
        rule_w = max(surf.get_width() // 3, self.btn_min_w // 2)
        rule_h = max(3, self.gap_s // 4)
        pygame.draw.rect(
            self.screen, color or C.COLOR_ACCENT,
            (C.SCREEN_WIDTH // 2 - rule_w // 2, rect.bottom + self.gap_s // 2,
             rule_w, rule_h),
            border_radius=rule_h,
        )
        return rect.bottom + self.gap_s // 2 + rule_h + self.gap_m

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

    def _make_desktop_shortcut(self):
        ok = installer.create_desktop_shortcut()
        self._shortcut_status = self.t(
            "settings_shortcut_ok" if ok else "settings_shortcut_fail")
        self.needs_redraw = True

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

    def _cycle_zoom(self):
        """Steps through the zoom levels and rebuilds the layout.

        The viewport does not change size, so nothing else on screen
        moves - only the tiles get bigger and the view starts following
        the player. Everything derived from the tile size is rebuilt
        here, which is why this is not just a settings write.
        """
        levels = list(C.ZOOM_LEVELS)
        nxt = levels[(levels.index(self._zoom()) + 1) % len(levels)]
        self.settings["zoom"] = nxt
        persistence.save_settings(self.settings)
        base = C.VIEW_W // C.MAP_WIDTH
        self._apply_zoom(base)
        self._name_cache = {}
        self._badge_cache = {}
        self._potion_sprite_cache = {}
        self._hud_cache = None
        self.needs_redraw = True
        self.sounds.play("equip")

    def _render_scale_name(self):
        """Names each setting by what it costs, not by its number.

        The full canvas showed as "1x" one row under "Zoom: 1.5x", which
        makes it read as the neutral, normal choice. On a phone it is the
        expensive one - nearly twice the pixels per frame of auto - and
        the only way to find that out was to play on it.
        """
        want = self.settings.get("render_scale", C.DEFAULT_RENDER_SCALE)
        if want == "auto":
            return self.t("render_auto", value=self._mult_text(self.render_scale))
        value = self._mult_text(float(want))
        if float(want) >= 1.0:
            return self.t("render_full", value=value)
        return self.t("render_reduced", value=value)

    def _cycle_render_scale(self):
        """Steps through the render scales. Takes effect on the next start.

        The canvas size is fixed when the display is created, and
        recreating it mid-run would mean rebuilding every cached surface
        and the whole layout - so this is the one setting that waits.
        """
        levels = list(C.RENDER_SCALES)
        current = self.settings.get("render_scale", C.DEFAULT_RENDER_SCALE)
        nxt = levels[(levels.index(current) + 1) % len(levels)] if current in levels else levels[0]
        self.settings["render_scale"] = nxt
        persistence.save_settings(self.settings)
        self._notify(self.t("log_render_scale_restart"), C.COLOR_ACCENT)
        self.sounds.play("equip")

    def _toggle_fps(self):
        self.settings["show_fps"] = not self.settings.get("show_fps")
        persistence.save_settings(self.settings)
        self._fps_surface = None
        self.needs_redraw = True
        self.sounds.play("equip")

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
        if getattr(self, "_pending_update_failure", None):
            self.update_error = self.t("update_swap_failed",
                                       reason=self._pending_update_failure)
            self.update_phase = "error"
            self._pending_update_failure = None
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
                # Ask the main loop to shut down rather than calling
                # pygame.quit() here (an SDL call, unsafe off the main
                # thread) or os._exit() (which used to be the answer, but
                # it bypasses PyInstaller's own cleanup - every update
                # then left a ~40MB _MEI folder behind in %TEMP%, and that
                # pile is what eventually broke an extraction with
                # "Failed to load Python DLL"). The relaunch script is
                # already waiting for this process to disappear.
                self._quit_for_update = True
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
            base = monster.name
        else:
            base = loc.MONSTER_NAME_DE.get(monster.kind, monster.kind)
            gender = self._monster_gender(monster)
            if monster.is_boss:
                title = loc.BOSS_TITLE_DE.get(monster.kind, "Häuptling")
                base = f"{base}-{title}"
            if monster.elite_name:
                elite_stem = loc.ELITE_NAME_DE.get(monster.elite_name, monster.elite_name)
                ending = loc.ADJ_ENDING_DE.get(gender, "er")
                base = f"{elite_stem}{ending} {base}"
        # Applied here rather than baked into monster.name when the
        # monster is created. The German name is rebuilt from its parts
        # above, so a prefix stored on .name was silently dropped in
        # German and a superboss read as an ordinary boss - and storing
        # translated text on the entity would freeze it in whatever
        # language was active when the save was written.
        if monster.is_superboss:
            base = f"{self.t('superboss_prefix')} {base}"
        elif monster.is_mimic:
            base = f"{self.t('mimic_prefix')} {base}"
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
            if self._quit_for_update:
                # Normal shutdown so the frozen build tears down its own
                # temp extraction folder before the swap script takes over.
                pygame.quit()
                sys.exit()
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
                    pos = self._canvas_pos(event.pos)
                    self._note_press(pos)
                    self._handle_tap(pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.touch_direction = None
                    self._pressed_key = None

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

            if (getattr(self, "_pressed_key", None) is not None
                    and pygame.time.get_ticks() > getattr(self, "_pressed_until", 0)):
                self._pressed_key = None
                self.needs_redraw = True

            self._music_watchdog()

            if self._should_redraw():
                began = pygame.time.get_ticks()
                self.render()
                self.needs_redraw = False
                self._last_draw_ms = pygame.time.get_ticks()
                self._note_frame_cost(self._last_draw_ms - began)
            self.clock.tick(POLL_HZ)

    def _note_frame_cost(self, ms):
        """Says once when the chosen graphics setting is too slow here.

        Only for an explicitly chosen scale: "auto" already sizes the
        canvas to a pixel budget, so a slow frame there is not something
        the player can do anything about, and a message would just be
        noise. The full canvas is nearly twice the pixels of auto on a
        phone and there is no way to make it cheaper - the only useful
        thing to say is which setting to change.
        """
        if self._slow_warned or self.state != "playing":
            return
        if self.settings.get("render_scale", C.DEFAULT_RENDER_SCALE) == "auto":
            return
        self._slow_frames = self._slow_frames + 1 if ms > C.SLOW_FRAME_MS else 0
        if self._slow_frames >= C.SLOW_FRAME_STREAK:
            self._slow_warned = True
            self._notify(self.t("log_render_scale_slow"), C.COLOR_ACCENT)

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
        if self.particles or self.hitstop_timer > 0 or self.banners:
            return True
        if self.damage_numbers:
            return True
        if self.player.render_x != self.player.x or self.player.render_y != self.player.y:
            return True
        return any(m.render_x != m.x or m.render_y != m.y for m in self.monsters)

    def _begin_frame(self):
        """Starts the per-part timing behind the frame-rate display.

        A frame that costs 155ms on the phone and 6ms on this desktop
        cannot be found by profiling the desktop, and "it is the pixels"
        turned out to be wrong: the full canvas and a 25% smaller one
        cost the same 6fps on the device. So the frame has to say where
        it went, on the device, in its own words.

        Skipped entirely unless the display is switched on - a timer
        around every part of every frame is exactly the sort of per-frame
        cost this exists to find.
        """
        if not self.settings.get("show_fps"):
            self._timings = None
            return
        self._timings = []
        self._mark_at = time.perf_counter()

    def _mark(self, name):
        if self._timings is None:
            return
        now = time.perf_counter()
        self._timings.append((name, (now - self._mark_at) * 1000.0))
        self._mark_at = now

    def _render_fps(self):
        """Frame time and rate, top-left, when switched on in Settings.

        The rate is the interval between drawn frames, which is the frame
        cost only while something is moving - this is a turn-based game
        and a still screen is deliberately redrawn twice a second, so a
        reading taken on a standing player says 500ms and means nothing.
        The breakdown underneath is the previous frame's, since the
        present has not happened yet when this draws.

        The text is only re-rendered twice a second - a per-frame font
        render in the thing that measures per-frame cost would be its own
        joke.
        """
        now = pygame.time.get_ticks()
        self._fps_frames += 1
        if now - self._fps_since >= 500:
            elapsed = now - self._fps_since
            fps = self._fps_frames * 1000.0 / max(1, elapsed)
            ms = elapsed / max(1, self._fps_frames)
            self._fps_surface = self._f_tiny_outlined(
                f"{fps:.0f} fps   {ms:.0f} ms   {C.SCREEN_WIDTH}x{C.SCREEN_HEIGHT}"
                f"   x{self.render_scale:.2f}",
                C.COLOR_ACCENT)
            parts = getattr(self, "_last_timings", None)
            if parts:
                text = "  ".join(f"{n} {v:.0f}" for n, v in parts)
                self._fps_parts_surface = self._f_tiny_outlined(text, C.COLOR_ACCENT)
                # Also to the log, where it can be read off a device over
                # adb without squinting at a screenshot.
                print("frame ms: " + text, flush=True)
            self._fps_since = now
            self._fps_frames = 0
        if self._fps_surface is not None:
            x = self.MINIMAP_POS[0]
            y = self.MINIMAP_POS[1] + C.MAP_HEIGHT * self.MINIMAP_SCALE + 8
            self.screen.blit(self._fps_surface, (x, y))
            parts = getattr(self, "_fps_parts_surface", None)
            if parts is not None:
                self.screen.blit(parts, (x, y + self._fps_surface.get_height() + 2))

    def _present(self):
        # One large sequential copy of the in-RAM canvas onto the real
        # display surface, then present. See the comment where self.screen
        # is created for why nothing draws into the display surface
        # directly.
        #
        # pygame.SCALED is supposed to stretch a smaller canvas to fill
        # the window, and where it does the display surface reports the
        # logical size, the two match, and this is a plain copy. On the
        # device it does not: the canvas was drawn 1:1 in the middle with
        # black all round it. So when the sizes differ we do the stretch
        # ourselves, into the existing display surface - transform.scale
        # with a destination allocates nothing.
        if self.display.get_size() != self.screen.get_size():
            pygame.transform.scale(self.screen, self.display.get_size(),
                                   self.display)
        else:
            self.display.blit(self.screen, (0, 0))
        self._mark("copy")
        pygame.display.flip()
        self._mark("flip")
        self._last_timings = self._timings

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
        # Hitstop: hold everything still for a few ticks after a big hit.
        # Timers and movement both pause, so the freeze reads as impact
        # rather than as a dropped frame.
        if self.hitstop_timer > 0:
            self.hitstop_timer -= 1
            return

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
        for banner in self.banners:
            banner["timer"] -= 1
        self.banners = [b for b in self.banners if b["timer"] > 0]
        self._update_particles()

    def _update_particles(self):
        alive = []
        for p in self.particles:
            p["timer"] -= 1
            if p["timer"] <= 0:
                continue
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += C.PARTICLE_GRAVITY
            alive.append(p)
        self.particles = alive

    def _spawn_particles(self, x, y, color, count, spread=0.34):
        """A burst of sparks at a tile, in pixel space.

        Positions are kept in pixels rather than tiles because they drift
        sub-tile distances and fall under gravity; converting per frame
        would be needless arithmetic. Capped globally - a fight with a
        dozen monsters in it must not turn into a particle simulation.
        """
        ts = C.TILE_SIZE
        room = C.PARTICLE_MAX - len(self.particles)
        for _ in range(min(count, max(0, room))):
            self.particles.append({
                "x": x * ts + ts / 2 + random.uniform(-ts / 5, ts / 5),
                "y": y * ts + ts / 2 + random.uniform(-ts / 5, ts / 5),
                "vx": random.uniform(-spread, spread) * ts / 6,
                "vy": random.uniform(-spread * 1.6, -spread * 0.2) * ts / 6,
                "color": color,
                "timer": random.randint(C.PARTICLE_LIFETIME // 2, C.PARTICLE_LIFETIME),
                "size": max(2, ts // 9),
            })

    def _render_particles(self, ox=0, oy=0):
        for p in self.particles:
            size = p["size"]
            self.screen.fill(p["color"],
                             (int(p["x"]) + ox, int(p["y"]) + oy, size, size))

    def _notify(self, text, color=None):
        """Puts one line across the top of the dungeon view.

        The combat log is in the bottom-right corner and is genuinely
        easy to miss - a trap going off, a level-up, or "not enough gold"
        all happened silently as far as most players were concerned. This
        is for the handful of events worth interrupting for; everything
        else still just goes to the log.
        """
        self.banners.append({
            "text": text,
            "color": color or C.COLOR_TEXT,
            "timer": C.BANNER_TICKS,
        })
        # Newest wins. A queue would mean an important line waiting
        # behind two stale ones before it is ever seen.
        if len(self.banners) > C.BANNER_MAX:
            del self.banners[0]
        self.needs_redraw = True

    def _announce(self, key, color=None, **kw):
        """Log it and put it on the banner - the usual case for an event
        the player should not be able to miss."""
        text = self.t(key, **kw)
        self.add_log(text)
        self._notify(text, color)
        return text

    def _render_banners(self):
        if not self.banners:
            return
        pad = self.gap_s
        y = self.gap_s
        # Below the boss bar when there is one, so the two never overlap.
        if any(m.is_boss and m.awake and m.is_alive() for m in self.monsters) \
                and not self.enemies_off:
            y += self.f_sm.get_linesize() + self.gap_s + self.gap_s

        # f_body, not the log's f_sm: the whole point is that this is
        # readable without going looking for it.
        for banner in self.banners:
            panel = banner.get("surface")
            if panel is None:
                # Built once, on the frame the banner first draws, and
                # kept. Rasterising the text and rebuilding a translucent
                # rounded panel every frame is precisely the kind of
                # per-frame work that costs this game its frame rate on
                # a real device.
                surf = self.f_body.render(banner["text"], True, banner["color"])
                w = surf.get_width() + pad * 4
                h = surf.get_height() + pad
                panel = pygame.Surface((w, h), pygame.SRCALPHA)
                pygame.draw.rect(panel, (*C.COLOR_SURFACE, 235),
                                 (0, 0, w, h), border_radius=h // 3)
                pygame.draw.rect(panel, (*banner["color"], 255), (0, 0, w, h),
                                 width=2, border_radius=h // 3)
                panel.blit(surf, surf.get_rect(center=(w // 2, h // 2)))
                banner["surface"] = panel
            w, h = panel.get_size()
            # Fades out over its last few ticks rather than vanishing, so
            # a banner leaving does not read as a flicker. Only the alpha
            # changes, which is a flag on the cached surface.
            alpha = 255
            if banner["timer"] < C.BANNER_FADE_TICKS:
                alpha = int(255 * banner["timer"] / C.BANNER_FADE_TICKS)
            panel.set_alpha(alpha)
            self.screen.blit(panel, (C.SCREEN_WIDTH // 2 - w // 2, y))
            y += h + self.gap_s

    def _spawn_damage_number(self, x, y, text, color):
        self.damage_numbers.append({"x": x, "y": y, "text": text, "color": color, "timer": 30, "max_timer": 30})

    def _canvas_pos(self, pos):
        """Where a touch landed on the canvas, not on the display.

        Every button is laid out and hit-tested in canvas coordinates,
        but the events arrive in the display's. Those are the same size
        only when the canvas is not being stretched - that is, only at
        graphics 1x. At any other setting _present blows the canvas up to
        fill the window, and an untranslated touch lands short of where
        the button is drawn by exactly that factor: at auto on a phone,
        about a third of the screen off. Buttons that do nothing and taps
        that hit the wrong thing is the whole of "unplayable unless it is
        on 1x", and it starts at the letterboxing fix, which is what made
        the two sizes differ in the first place.
        """
        dw, dh = self.display.get_size()
        cw, ch = self.screen.get_size()
        if not dw or not dh or (dw, dh) == (cw, ch):
            return pos
        return (pos[0] * cw // dw, pos[1] * ch // dh)

    def _note_press(self, pos):
        """Remember which button is under the finger, for the pressed look.

        Cleared on release, and after a short delay for key presses, which
        have no release event of their own here.
        """
        self._pressed_key = None
        for rect, key in self._tap_targets:
            if rect.collidepoint(pos):
                self._pressed_key = key
                self._pressed_until = pygame.time.get_ticks() + 140
                break

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
        if self.bag_button.collidepoint(pos):
            self._open_bag()
            return
        if self.test_room and self.tools_button.collidepoint(pos):
            self.state = "tools"
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
            elif key == pygame.K_z:
                self._cycle_zoom()
            elif key == pygame.K_r:
                self._cycle_render_scale()
            elif key == pygame.K_p:
                self._toggle_fps()
            elif key == pygame.K_m:
                self._toggle_music()
            elif key == pygame.K_k and not ON_ANDROID:
                self._make_desktop_shortcut()
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
            elif key == pygame.K_d:
                self.start_test_room()
            elif key == pygame.K_n:
                self.state = "difficulty_select"
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.save_data:
                    self.continue_run()
                else:
                    self.state = "difficulty_select"
            return

        if self.state == "difficulty_select":
            if key == pygame.K_ESCAPE:
                self.state = "title"
            elif key in self.DIFFICULTY_KEYS:
                index = self.DIFFICULTY_KEYS.index(key)
                if index < len(C.DIFFICULTIES):
                    # Remember it and move on to the class picker; the run
                    # itself only starts once both are chosen.
                    self.pending_difficulty = C.DIFFICULTIES[index]["id"]
                    self.state = "class_select"
            return

        if self.state == "class_select":
            if key == pygame.K_ESCAPE:
                self.state = "difficulty_select"
            elif key in self.CLASS_KEYS:
                index = self.CLASS_KEYS.index(key)
                if index < len(C.CLASSES):
                    self.start_new_run(
                        getattr(self, "pending_difficulty", None),
                        C.CLASSES[index]["id"])
            return

        if self.state == "dead":
            if key == pygame.K_r:
                self.state = "difficulty_select"
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
            elif pygame.K_1 <= key <= pygame.K_6:
                self._buy_item(key - pygame.K_1)
            return

        if self.state == "smith":
            if key == pygame.K_ESCAPE:
                self.state = "playing"
            elif pygame.K_1 <= key <= pygame.K_4:
                self._smith_buy(key - pygame.K_1)
            return

        if self.state == "tools":
            if key == pygame.K_ESCAPE:
                self.state = "playing"
            elif key in self.TOOL_KEYS:
                self._use_tool(self.TOOL_KEYS.index(key))
            return

        if self.state == "bag":
            self._bag_key(key)
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
        elif key == pygame.K_i:
            self._open_bag()
        elif key == pygame.K_k and self.test_room:
            self.state = "tools"
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
        self._tick_buffs()

        if dx != 0:
            self.player.facing = 1 if dx > 0 else -1

        target_x, target_y = self.player.x + dx, self.player.y + dy

        target_merchant = next((m for m in self.merchants if m.x == target_x and m.y == target_y), None)
        if target_merchant:
            self.shop_stock = self._merchant_stock(target_merchant)
            self.state = "shop"
            return

        if any((b.x, b.y) == (target_x, target_y) for b in self.blacksmiths):
            self.state = "smith"
            return

        target_monster = None if self.enemies_off else next(
            (m for m in self.monsters if m.x == target_x and m.y == target_y), None
        )
        if target_monster:
            self._attack(self.player, target_monster)
        elif (target_x, target_y) == self.boss_door_pos and self._boss_door_blocked():
            # Barred, not walled: the tile stays walkable so pathfinding,
            # the field of view and the map cache never have to know about
            # a door that appears and disappears.
            self._announce("log_boss_door_locked", C.COLOR_DANGER)
            return
        elif not self.blocks_movement(target_x, target_y):
            self.player.move(dx, dy)
            pos = (self.player.x, self.player.y)
            if pos in self.traps:
                self._trigger_trap(pos)
                if self.state == "dead":
                    return
            if pos in self.hazards:
                self._trigger_hazard(pos)
                if self.state == "dead":
                    return
            if pos == self.shrine_pos:
                self._trigger_shrine()
                if self.state == "dead":
                    return
            if pos == self.chest_pos and not self.chest_open:
                self._open_chest()
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

    def _hurt_player(self, amount):
        """Applies damage to the player, or none at all in godmode.

        Every route that can hurt the player goes through here - melee,
        poison and bleed, traps, hazards - so godmode is one check rather
        than four, and the next thing that can hurt you cannot forget to
        honour it. Returns what was actually taken off, so callers can
        skip their own log line and shake when nothing happened.
        """
        if self.godmode:
            return 0
        self.player.hp -= amount
        return amount

    def _tick_poison(self):
        """Damage-over-time the player is carrying, one turn's worth.

        Poison and bleed are both handled here so a single call site in
        _player_turn covers everything that ticks down on the player.
        """
        for field, per_turn, color, log_key, death_key in (
            ("poison_turns", C.POISON_DAMAGE_PER_TURN, C.COLOR_POISON,
             "log_poison_damage", "log_succumb_poison"),
            ("bleed_turns", C.BLEED_DAMAGE_PER_TURN, C.COLOR_DANGER,
             "log_bleed_damage", "log_succumb_bleed"),
        ):
            if getattr(self.player, field) <= 0:
                continue
            setattr(self.player, field, getattr(self.player, field) - 1)
            if not self._hurt_player(per_turn):
                continue
            self._spawn_damage_number(self.player.x, self.player.y, str(per_turn), color)
            self.add_log(self.t(log_key, dmg=per_turn))
            if self.player.hp <= 0:
                self.add_log(self.t(death_key))
                self.sounds.play("death")
                self.state = "dead"
                self._finalize_run()
                return

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
            dmg = self._hurt_player(random.randint(info["min_damage"], info["max_damage"]))
            if not dmg:
                return
            self._spawn_damage_number(*pos, str(dmg), C.COLOR_TRAP)
            self._announce("log_trap_damage", C.COLOR_TRAP, trap=trap_name, dmg=dmg)
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
            self._announce("log_shrine_vitality", C.COLOR_SUCCESS)
            self.sounds.play("levelup")
        elif event_id == "power":
            self.player.base_power += 2
            self._announce("log_shrine_power", C.COLOR_SUCCESS)
            self.sounds.play("levelup")
        elif event_id == "fortune":
            amount = self.dungeon_level * 15
            self.player.gold += amount
            self.stats["total_gold_collected"] = self.stats.get("total_gold_collected", 0) + amount
            self._spawn_damage_number(self.player.x, self.player.y, f"+{amount}", C.COLOR_GOLD)
            self._announce("log_shrine_fortune", C.COLOR_GOLD, amount=amount)
            self.sounds.play("levelup")
        elif event_id == "frailty":
            amount = min(5, max(1, self.player.max_hp // 5))
            self.player.max_hp = max(5, self.player.max_hp - amount)
            self.player.hp = min(self.player.hp, self.player.max_hp)
            self._spawn_damage_number(self.player.x, self.player.y, f"-{amount}", C.COLOR_TRAP)
            self._announce("log_shrine_frailty", C.COLOR_DANGER, amount=amount)
            self.sounds.play("player_hurt")
        elif event_id == "ambush":
            self._announce("log_shrine_ambush", C.COLOR_DANGER)
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
            if self.blocks_movement(x, y) or self._is_occupied(x, y):
                continue
            monster = self._make_monster(x, y, random.choice(kinds), elite=self._maybe_elite())
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
            potion_id = item.potion_id or C.DEFAULT_POTION
            self.player.add_potion(potion_id)
            self.add_log(self.t("log_pickup_item", item=self._potion_name(potion_id)))
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
                self._announce("log_equip_weapon", item.color, item=label, bonus=item.bonus)
                self.sounds.play("equip")
            else:
                self.add_log(self.t("log_find_worse_weapon", item=self.tn(item.name), current=self.tn(self.player.weapon_name)))
        elif item.kind == "armor":
            if item.bonus > self.player.armor_bonus:
                self.player.armor_bonus = item.bonus
                self.player.armor_name = item.name
                self.player.armor_rarity_id = item.rarity_id
                label = f"{self.tr(item.rarity_id)} {self.tn(item.name)}".strip()
                self._announce("log_equip_armor", item.color, item=label, bonus=item.bonus)
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

    def _potion_name(self, potion_id):
        info = C.POTION_BY_ID.get(potion_id)
        return self.tn(info["name"]) if info else potion_id

    def _potion_sprite(self, potion_id, height=None):
        """The flask art for a potion, at the requested height.

        Each potion names a frame in the shared tileset, so the flask you
        see on the floor is the one you see in the inventory. Cached by
        (id, height) - the inventory draws up to a couple of dozen of
        these and rescaling them per frame would be daft.
        """
        info = C.POTION_BY_ID.get(potion_id)
        if not info:
            return None
        h = height or C.ITEM_SPRITE_HEIGHT
        key = (potion_id, h)
        cached = self._potion_sprite_cache.get(key)
        if cached is not None:
            return cached
        source = self._tile_sources.get(info["flask"])
        if source is None:
            return None
        w, sh = source.get_size()
        sprite = pygame.transform.scale(source, (max(1, round(w * h / sh)), h))
        # The flasks come in four colours but there are thirty potions, so
        # each is tinted to its own colour - otherwise half the inventory
        # would be indistinguishable red flasks.
        sprite = self._tint_tile(sprite, info["color"])
        self._potion_sprite_cache[key] = sprite
        return sprite

    def _available_potions(self, include_cursed=True):
        """Potion types that can turn up at the current depth."""
        return [p for p in C.POTION_TYPES
                if p["min_level"] <= self.dungeon_level
                and (include_cursed or not p.get("cursed"))]

    def _roll_potion(self):
        pool = self._available_potions()
        if not pool:
            return C.DEFAULT_POTION
        weights = [p["weight"] for p in pool]
        return random.choices(pool, weights=weights, k=1)[0]["id"]

    def _drink_potion(self, potion_id=None):
        potion_id = potion_id or self.player.selected_potion
        info = C.POTION_BY_ID.get(potion_id)
        if info is None or self.player.potion_count(potion_id) <= 0:
            self._announce("log_no_potions", C.COLOR_DANGER)
            return
        # Only healing is refused at full health. Every other potion does
        # something useful regardless, and refusing them would make the
        # quick-use button unpredictable.
        effect = info["effect"]
        heals_only = set(effect) <= {"heal", "heal_pct"}
        if heals_only and self.player.hp >= self.player.max_hp:
            self._announce("log_full_health", C.COLOR_TEXT_DIM)
            return

        self.player.take_potion(potion_id)
        self.player.potions_drunk_this_run += 1
        self.stats["total_potions_drunk"] += 1
        self.sounds.play("pickup")
        self._apply_potion_effect(info)

        self._enemy_turn()
        self._recompute_fov()
        self._check_achievements()
        self._maybe_show_levelup_choice()

    def _apply_potion_effect(self, info):
        """Runs one potion's effect and logs what it did.

        Effects are data (see constants.POTION_TYPES) rather than a
        function per potion, so adding a potion is one dict entry and the
        combinations - Panacea both cures and heals - come for free.
        """
        p = self.player
        effect = info["effect"]
        name = self.tn(info["name"])

        heal = effect.get("heal", 0)
        if effect.get("heal_pct"):
            heal = max(heal, int(p.max_hp * effect["heal_pct"]))
        if heal:
            healed = min(heal, p.max_hp - p.hp)
            p.hp += healed
            self.add_log(self.t("log_drink_potion", healed=healed))
            self._spawn_damage_number(p.x, p.y, f"+{healed}", C.COLOR_SUCCESS)

        if effect.get("max_hp"):
            p.max_hp += effect["max_hp"]
            p.hp += effect["max_hp"]
            self._announce("log_potion_max_hp", C.COLOR_SUCCESS, amount=effect["max_hp"])
        if effect.get("base_power"):
            p.base_power += effect["base_power"]
            self._announce("log_potion_power", C.COLOR_SUCCESS, amount=effect["base_power"])
        if effect.get("base_defense"):
            p.base_defense += effect["base_defense"]
            self._announce("log_potion_defense", C.COLOR_SUCCESS, amount=effect["base_defense"])
        if effect.get("xp_levels"):
            amount = max(1, int(p.xp_to_next * effect["xp_levels"]))
            self.add_log(self.t("log_potion_xp", amount=amount))
            levels = p.gain_xp(amount)
            if levels:
                self._announce("log_level_up", C.COLOR_ACCENT, level=p.level)
                self.sounds.play("levelup")
                self.pending_perk_count += levels

        if effect.get("buff"):
            buff = effect["buff"]
            turns = effect.get("turns", 10)
            # Re-drinking refreshes rather than stacking the duration, so
            # a stockpile cannot be turned into one permanent buff.
            p.buffs[buff] = max(p.buffs.get(buff, 0), turns)
            key = "log_potion_curse" if info.get("cursed") else "log_potion_buff"
            self._announce(key, C.BUFFS.get(buff, {}).get("color"),
                           buff=self._buff_name(buff), turns=turns)

        if effect.get("shield"):
            p.shield = max(p.shield, effect["shield"])
            self.add_log(self.t("log_potion_shield", amount=effect["shield"]))

        for field in effect.get("cure", ()):
            if getattr(p, field, 0) > 0:
                setattr(p, field, 0)
        if effect.get("cure_debuffs"):
            for buff in [b for b in p.buffs if C.BUFFS.get(b, {}).get("power", 0) < 0
                         or C.BUFFS.get(b, {}).get("defense", 0) < 0]:
                del p.buffs[buff]
        if effect.get("cure") or effect.get("cure_debuffs"):
            self.add_log(self.t("log_potion_cured", item=name))

        if effect.get("self_poison"):
            p.poison_turns = max(p.poison_turns, effect["self_poison"])
            self._announce("log_potion_self_poison", C.COLOR_POISON)

        if effect.get("reveal"):
            self.explored = {(x, y) for y in range(C.MAP_HEIGHT)
                             for x in range(C.MAP_WIDTH)}
            self._map_cache = None
            self._minimap_cache = None
            self.add_log(self.t("log_potion_reveal"))
        if effect.get("blink"):
            self._blink_player()
        if effect.get("gold"):
            low, high = effect["gold"]
            amount = random.randint(low, high) * max(1, self.dungeon_level // 2)
            p.gold += amount
            self.stats["total_gold_collected"] = self.stats.get("total_gold_collected", 0) + amount
            self.add_log(self.t("log_pickup_gold", amount=amount))

        if effect.get("burst_damage"):
            self._potion_burst(effect)

    def _buff_name(self, buff_id):
        info = C.BUFFS.get(buff_id)
        return self.tn(info["name"]) if info else buff_id

    def _blink_player(self):
        x, y = self._random_floor_tile()
        self.player.x, self.player.y = x, y
        self.player.snap()
        self.add_log(self.t("log_blink"))

    def _potion_burst(self, effect):
        """A thrown flask: hits everything around the player at once.

        Deliberately centred on the player rather than aimed - this game
        has no targeting cursor, and asking for one on a phone with a
        D-pad would be worse than the effect is worth.
        """
        radius = C.POTION_BURST_RADIUS
        damage = effect["burst_damage"]
        hit = 0
        for monster in list(self.monsters):
            if not monster.is_alive():
                continue
            if max(abs(monster.x - self.player.x), abs(monster.y - self.player.y)) > radius:
                continue
            hit += 1
            monster.hp -= damage
            self._spawn_damage_number(monster.x, monster.y, str(damage), C.COLOR_DANGER)
            if effect.get("burst_burn"):
                monster.burn_turns = max(monster.burn_turns, effect["burst_burn"])
            if effect.get("burst_slow"):
                monster.slow_turns = max(monster.slow_turns, effect["burst_slow"])
            if effect.get("burst_stun"):
                monster.stun_turns = max(monster.stun_turns, effect["burst_stun"])
            if monster.hp <= 0:
                self._on_monster_death(monster)
        self.shake_timer, self.shake_intensity = 8, 4
        self.add_log(self.t("log_potion_burst", count=hit))

    def _tick_buffs(self):
        """Counts every active buff down by one turn.

        Called once per player turn from the same place poison is ticked,
        so buff duration is measured in turns taken rather than in real
        time - standing still must not burn a Haste potion.
        """
        p = self.player
        for buff in list(p.buffs):
            p.buffs[buff] -= 1
            if p.buffs[buff] <= 0:
                del p.buffs[buff]
                self.add_log(self.t("log_buff_ended", buff=self._buff_name(buff)))
        regen = p.buff_total("regen")
        if regen and p.hp < p.max_hp:
            healed = min(regen, p.max_hp - p.hp)
            p.hp += healed
            self._spawn_damage_number(p.x, p.y, f"+{healed}", C.COLOR_SUCCESS)

    def _shop_price(self, stock):
        """Listed price after the difficulty's per-floor markup.

        On the harder settings the merchant stops being a reliable safety
        valve the deeper you go, which is the point.
        """
        markup = self._diff()["shop_markup_per_level"] * max(0, self.dungeon_level - 1)
        return int(round(stock["price"] * (1 + markup)))

    # --- the blacksmith ------------------------------------------------
    # Each entry: (id, label key, whether it is available, price, action).
    # Built fresh each time the screen is drawn, because every one of
    # those depends on what the player is currently carrying.

    def _smith_offers(self):
        p = self.player
        offers = []
        if p.weapon_bonus > 0 or p.weapon_name != "Fists":
            offers.append({
                "id": "weapon",
                "label": self.t("smith_weapon",
                                item=self.tn(p.weapon_name),
                                bonus=p.weapon_bonus,
                                step=C.BLACKSMITH_WEAPON_STEP),
                "price": self._smith_price(p.weapon_bonus),
            })
        if p.armor_bonus > 0 or p.armor_name != "None":
            offers.append({
                "id": "armor",
                "label": self.t("smith_armor",
                                item=self.tn(p.armor_name),
                                bonus=p.armor_bonus,
                                step=C.BLACKSMITH_ARMOR_STEP),
                "price": self._smith_price(p.armor_bonus),
            })
        if p.weapon_name != "Fists":
            offers.append({
                "id": "enchant",
                "label": (self.t("smith_reenchant", element=self.te(p.weapon_element_id))
                          if p.weapon_element_id else self.t("smith_enchant")),
                "price": C.BLACKSMITH_ENCHANT_PRICE,
            })
            # A weapon that never rolled a rarity (the class starter kit,
            # for instance) reads as Common here rather than as a blank -
            # tr() returns "" for None, which made the label say
            # "reforge your weapon (now )".
            rarity = self.tr(p.weapon_rarity_id) or self.tr(C.RARITY_TIERS[0]["id"])
            offers.append({
                "id": "reforge",
                "label": self.t("smith_reforge", rarity=rarity),
                "price": C.BLACKSMITH_REFORGE_PRICE,
            })
        return offers

    @staticmethod
    def _smith_price(current_bonus):
        return C.BLACKSMITH_BASE_PRICE + C.BLACKSMITH_PRICE_PER_POINT * max(0, current_bonus)

    def _smith_buy(self, index):
        offers = self._smith_offers()
        if index < 0 or index >= len(offers):
            return
        offer = offers[index]
        if self.player.gold < offer["price"]:
            self._announce("log_not_enough_gold", C.COLOR_DANGER)
            return
        self.player.gold -= offer["price"]
        p = self.player

        if offer["id"] == "weapon":
            p.weapon_bonus += C.BLACKSMITH_WEAPON_STEP
            self.add_log(self.t("log_smith_weapon", item=self.tn(p.weapon_name),
                                bonus=p.weapon_bonus))
        elif offer["id"] == "armor":
            p.armor_bonus += C.BLACKSMITH_ARMOR_STEP
            self.add_log(self.t("log_smith_armor", item=self.tn(p.armor_name),
                                bonus=p.armor_bonus))
        elif offer["id"] == "enchant":
            # Never the element it already has, or paying to "reroll"
            # could visibly change nothing.
            choices = [e for e in C.ELEMENTS if e != p.weapon_element_id]
            p.weapon_element_id = random.choice(choices)
            self.add_log(self.t("log_smith_enchant",
                                element=self.te(p.weapon_element_id)))
        elif offer["id"] == "reforge":
            order = [t["id"] for t in C.RARITY_TIERS]
            current = order.index(p.weapon_rarity_id) if p.weapon_rarity_id in order else 0
            if current + 1 < len(order):
                tier = C.RARITY_TIERS[current + 1]
                p.weapon_rarity_id = tier["id"]
                # The rarity is what the bonus was scaled by when the
                # weapon dropped, so raising one has to raise the other -
                # otherwise reforging is a colour change you paid for.
                p.weapon_bonus = max(p.weapon_bonus + 1,
                                     int(round(p.weapon_bonus * 1.25)))
                self.add_log(self.t("log_smith_reforge", rarity=self.tr(tier["id"]),
                                    bonus=p.weapon_bonus))
            else:
                self._announce("log_smith_best_already", C.COLOR_TEXT_DIM)
                self.player.gold += offer["price"]
                return
        self.sounds.play("equip")

    def _render_smith(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("smith_title"), color=C.COLOR_BLACKSMITH)

        gold = self.f_body.render(self.t("shop_gold_label", gold=self.player.gold),
                                  True, C.COLOR_GOLD)
        self.screen.blit(gold, gold.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += gold.get_height() + self.gap_m

        offers = self._smith_offers()
        if not offers:
            self._lines_block([self.t("smith_nothing")], y + self.gap_l,
                              color=C.COLOR_TEXT_DIM)
            self._button_row([(self.t("btn_leave"), pygame.K_ESCAPE)],
                             C.SCREEN_HEIGHT - self.pad - self.btn_h)
            return

        keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
        bottom = C.SCREEN_HEIGHT - self.pad - self.btn_h - self.gap_l
        row_h = max(self.btn_h // 2,
                    min(self.btn_h,
                        (bottom - y - self.btn_gap * (len(offers) - 1)) // len(offers)))
        buy_w = self._btn_w(self.t("btn_forge"), self.f_sm)
        for i, offer in enumerate(offers):
            affordable = self.player.gold >= offer["price"]
            color = C.COLOR_HUD_TEXT if affordable else C.COLOR_TEXT_DIM
            label = f"{i + 1}. {offer['label']}"
            text = self.f_sm.render(label, True, color)
            self.screen.blit(text, text.get_rect(midleft=(self.pad, y + row_h // 2)))
            price = self.f_sm.render(f"{offer['price']} {self.t('gold_word')}", True,
                                     C.COLOR_GOLD if affordable else C.COLOR_TEXT_DIM)
            self.screen.blit(price, price.get_rect(
                midright=(C.SCREEN_WIDTH - self.pad - buy_w - self.gap_m,
                          y + row_h // 2)))
            self._draw_tap_button(
                (C.SCREEN_WIDTH - self.pad - buy_w, y, buy_w, row_h),
                self.t("btn_forge"), keys[i], font=self.f_sm)
            y += row_h + self.btn_gap

        self._button_row([(self.t("btn_leave"), pygame.K_ESCAPE)],
                         C.SCREEN_HEIGHT - self.pad - self.btn_h)

    def _merchant_stock(self, merchant):
        """What this particular merchant is selling.

        Rolled once and kept on the merchant, so his shelf does not change
        while the player is standing in front of it deciding, and so
        leaving and coming back is not a way to reroll for the potion you
        wanted. Healing and the three scrolls are always there; the rest
        is whatever this depth has unlocked. Cursed flasks are found, not
        sold - a merchant who poisons you is a bad merchant.
        """
        if getattr(merchant, "stock", None):
            return merchant.stock
        stock = [dict(entry) for entry in C.SHOP_STOCK]
        pool = [p for p in self._available_potions(include_cursed=False)
                if p["id"] != C.DEFAULT_POTION and p["price"] > 0]
        random.shuffle(pool)
        for info in pool[:2]:
            stock.append({"kind": "potion", "potion_id": info["id"],
                          "name": info["name"], "price": info["price"]})
        merchant.stock = stock
        return stock

    def _buy_item(self, index):
        stock_list = getattr(self, "shop_stock", None) or C.SHOP_STOCK
        if index < 0 or index >= len(stock_list):
            return
        stock = stock_list[index]
        price = self._shop_price(stock)
        if self.player.gold < price:
            self._announce("log_not_enough_gold", C.COLOR_DANGER)
            return
        self.player.gold -= price
        if stock["kind"] == "potion":
            self.player.add_potion(stock.get("potion_id", C.DEFAULT_POTION))
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
                self._announce("log_no_target", C.COLOR_DANGER)
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
            self._minimap_cache = None
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
        if getattr(attacker, "is_boss", False):
            phase = self._boss_phase(attacker)
            if phase:
                damage = max(1, int(round(damage * phase["power_mult"])))
        if attacker is self.player:
            damage = max(1, int(round(damage * self._diff()["player_damage"])))

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
                if self.player.weapon_element_id == "frost":
                    # Frost carries two effects, not one: the defence
                    # debuff it always had, plus the slow that makes it
                    # actual crowd control rather than a damage variant.
                    defender.slow_turns = max(getattr(defender, "slow_turns", 0), C.SLOW_TURNS)

        if defender is self.player and self.player.bonus_damage_reduction:
            damage = max(1, round(damage * (1 - self.player.bonus_damage_reduction)))

        absorbed = 0
        if defender is self.player and self.player.shield > 0:
            # A ward soaks damage before health does, and unlike defence
            # it can absorb a hit whole - that is what makes it worth
            # drinking before a boss rather than just more armour.
            absorbed = min(self.player.shield, damage)
            self.player.shield -= absorbed
            damage -= absorbed

        if defender is self.player:
            damage = self._hurt_player(damage)
        else:
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

        # Sparks in the colour of whatever just happened, and on a crit a
        # brief freeze. Between them these are most of what makes a hit
        # read as a hit rather than as a number changing.
        spark = C.COLOR_CRIT if crit else (
            getattr(defender, "color", C.COLOR_DANGER) if defender is not self.player
            else C.COLOR_HP_BAR_FG)
        self._spawn_particles(defender.x, defender.y, spark,
                              C.PARTICLES_PER_CRIT if crit else C.PARTICLES_PER_HIT)
        if crit:
            self.hitstop_timer = C.HITSTOP_TICKS
            self.shake_timer = max(self.shake_timer, 5)
            self.shake_intensity = max(self.shake_intensity, 3)

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

        # A critical melee hit opens a wound. This is what gives crits a
        # payoff beyond the doubled number - and it is deliberately not
        # tied to any element, so an unenchanted weapon benefits too.
        if crit and defender.hp > 0:
            defender.bleed_turns = max(getattr(defender, "bleed_turns", 0), C.BLEED_TURNS)
            if defender is not self.player:
                self.add_log(self.t("log_status_bleed",
                                    monster=self._monster_named(defender, "nom")))

        if element_status_applied and defender.hp > 0:
            log_key = self._ELEMENT_STATUS_LOG_KEY[element_status_applied]
            self.add_log(self.t(log_key, monster=self._monster_named(defender, "nom")))

        if absorbed:
            self.add_log(self.t("log_shield_absorbed", amount=absorbed))
            self._spawn_damage_number(self.player.x, self.player.y, f"-{absorbed}",
                                      (150, 200, 255))

        self._apply_potion_combat_effects(attacker, defender, damage)

        if defender.hp <= 0:
            if defender is self.player:
                self.add_log(self.t("log_you_died"))
                self.sounds.play("death")
                self.state = "dead"
                self._finalize_run()
            else:
                self._on_monster_death(defender)

    def _apply_potion_combat_effects(self, attacker, defender, damage):
        """The buffs that only do something at the moment a blow lands.

        Kept out of _attack itself, which is already long, and out of the
        buff table, which is pure data - these three need to know who hit
        whom and for how much.
        """
        p = self.player
        if attacker is p and defender is not p and damage > 0:
            steal = p.buff_total("lifesteal")
            if steal and p.hp < p.max_hp:
                healed = min(int(damage * steal) or 1, p.max_hp - p.hp)
                p.hp += healed
                self._spawn_damage_number(p.x, p.y, f"+{healed}", C.COLOR_SUCCESS)
            return

        if defender is not p or attacker is p or not attacker.is_alive():
            return
        thorns = p.buff_total("thorns")
        if thorns:
            attacker.hp -= thorns
            self._spawn_damage_number(attacker.x, attacker.y, str(thorns),
                                      (198, 132, 96))
        burn = p.buff_total("burn_attackers")
        if burn:
            attacker.burn_turns = max(getattr(attacker, "burn_turns", 0), burn)
        if attacker.hp <= 0:
            self._on_monster_death(attacker)

    def _on_monster_death(self, monster):
        self.add_log(self.t("log_monster_dies", monster=self._monster_named(monster, "nom"), xp=monster.xp_reward))
        self.sounds.play("monster_death")
        # A bigger burst in the monster's own colour, so a kill is visibly
        # different from a hit that merely hurt.
        self._spawn_particles(monster.x, monster.y, monster.color,
                              C.PARTICLES_PER_DEATH, spread=0.5)
        if monster.is_boss:
            self.hitstop_timer = C.HITSTOP_TICKS * 3
            self.shake_timer, self.shake_intensity = 18, 7
        if monster in self.monsters:
            self.monsters.remove(monster)
        self.player.kills += 1
        self._record_kill(monster)
        if monster.splits and not monster.is_split_child:
            self._spawn_slime_children(monster)
        levels = self.player.gain_xp(monster.xp_reward)
        if levels:
            self._announce("log_level_up", C.COLOR_ACCENT, level=self.player.level)
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
            if self.blocks_movement(x, y) or self._is_occupied(x, y):
                continue
            child = self._make_monster(x, y, parent.kind)
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
                self._announce("log_achievement_unlocked", C.COLOR_ACCENT,
                               name=self._achievement_name(ach_id, name))
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
        if self.enemies_off:
            return

        # Haste buys a whole free turn: the monsters simply do not get
        # this one. Implemented by skipping their turn rather than by
        # giving the player two, so nothing about movement, traps or
        # status ticks has to become re-entrant.
        if self.player.has_buff_flag("haste"):
            self._haste_skip = not getattr(self, "_haste_skip", False)
            if self._haste_skip:
                return
        else:
            self._haste_skip = False

        invisible = self.player.has_buff_flag("invisible")

        for monster in list(self.monsters):
            if not monster.is_alive():
                continue

            stunned = self._tick_monster_status(monster)
            if not monster.is_alive():
                continue

            if (monster.x, monster.y) in self.visible and not invisible:
                was_asleep = not monster.awake
                monster.awake = True
                if was_asleep and monster.is_boss:
                    self.boss_banner_timer = 90
                    self.sounds.play("boss")
            if not monster.awake:
                continue
            if stunned:
                continue
            # Already-awake monsters lose track of an invisible player and
            # mill about instead of hunting. They still block and still
            # fight back if walked into - invisibility is an escape, not
            # a licence to ignore the room.
            if invisible:
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

        if monster.bleed_turns > 0:
            monster.bleed_turns -= 1
            dmg = C.BLEED_DAMAGE_PER_TURN
            monster.hp -= dmg
            self._spawn_damage_number(monster.x, monster.y, str(dmg), C.COLOR_DANGER)
            if monster.hp <= 0:
                self._on_monster_death(monster)
                return stunned

        if monster.weaken_turns > 0:
            monster.weaken_turns -= 1

        if monster.slow_turns > 0:
            monster.slow_turns -= 1
            # Acts on every other turn while slowed. Flipping the flag
            # here (rather than counting turns elsewhere) means the very
            # first turn after being frozen is always a lost one.
            monster.slow_skip = not monster.slow_skip
            if monster.slow_skip:
                stunned = True
        else:
            monster.slow_skip = False

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

        traits = C.MONSTER_TYPES.get(monster.kind, {})

        # An archer that lets you walk up and hit it is just a melee
        # monster with extra steps. Back off first, shoot from there.
        if traits.get("kites") and not monster.is_boss:
            dist = max(abs(dx), abs(dy))
            if dist < C.KITE_DISTANCE:
                step_x = -((dx > 0) - (dx < 0))
                step_y = -((dy > 0) - (dy < 0))
                if self._move_monster_toward(monster, step_x, step_y):
                    return
                # Cornered: no room to retreat, so it fights.

        if traits.get("sets_traps") and not monster.is_boss:
            monster.trap_cooldown = max(0, monster.trap_cooldown - 1)
            if monster.trap_cooldown == 0 and self._drop_monster_trap(monster):
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

    def _drop_monster_trap(self, monster):
        """A trap-setter leaves one behind and steps away from it.

        Only ever on its own tile, and only where nothing else is: it
        cannot bury a trap under the stairs or another trap, and the
        player always has a turn to notice the monster moving off it.
        """
        pos = (monster.x, monster.y)
        if not self._tile_is_free(*pos, ignore=monster):
            return False
        step_x = -((self.player.x - monster.x > 0) - (self.player.x - monster.x < 0))
        step_y = -((self.player.y - monster.y > 0) - (self.player.y - monster.y < 0))
        if not self._move_monster_toward(monster, step_x, step_y):
            return False
        self.traps[pos] = random.choice(list(C.TRAP_TYPES.keys()))
        monster.trap_cooldown = C.TRAP_SETTER_COOLDOWN
        self.add_log(self.t("log_trap_set", monster=self._monster_named(monster, "nom")))
        return True

    def _boss_phase(self, boss):
        """Which phase a boss is in, or None while it is still fresh.

        Read from current health rather than latched on the way past a
        threshold, so healing a boss (an elite's regeneration, say) puts
        it back into the calmer phase instead of leaving it permanently
        enraged at full health.
        """
        ratio = boss.hp / max(1, boss.max_hp)
        current = None
        for phase in C.BOSS_PHASES:
            if ratio <= phase["at"]:
                current = phase
        return current

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
            if not self.blocks_movement(x, y) and not self._is_occupied(x, y):
                minion = self._make_monster(x, y, "skeleton")
                minion.awake = True
                self.monsters.append(minion)
                self.add_log(self.t("log_boss_summon", monster=self._monster_named(boss, "nom")))
                self.sounds.play("boss")
                return True
        return False

    def _cardinal_line_clear(self, x1, y1, x2, y2):
        """Whether a shot can travel between two tiles in a straight line.

        Uses blocks_movement, so a crate or a column stops an arrow the
        same way a wall does - which turns the solid decorations into
        cover you can duck behind rather than just furniture.
        """
        if x1 == x2 and y1 != y2:
            step = 1 if y2 > y1 else -1
            for y in range(y1 + step, y2, step):
                if self.blocks_movement(x1, y):
                    return False
            return True
        if y1 == y2 and x1 != x2:
            step = 1 if x2 > x1 else -1
            for x in range(x1 + step, x2, step):
                if self.blocks_movement(x, y1):
                    return False
            return True
        return False

    def _move_monster_toward(self, monster, step_x, step_y):
        """Steps a monster one tile, preferring the diagonal.

        Returns whether it actually moved. Callers need to know: a kiting
        archer that cannot retreat has to stand and fight instead, and a
        trap-setter must not drop a trap on the tile it is still standing
        on. Both read this as a boolean, so it must be one.
        """
        for nx, ny in (
            (monster.x + step_x, monster.y + step_y),
            (monster.x + step_x, monster.y),
            (monster.x, monster.y + step_y),
        ):
            if (nx, ny) == (monster.x, monster.y):
                continue
            if self.blocks_movement(nx, ny):
                continue
            if (nx, ny) == (self.player.x, self.player.y):
                continue
            if any((m.x, m.y) == (nx, ny) for m in self.monsters if m is not monster):
                continue
            monster.x, monster.y = nx, ny
            return True
        return False

    def _camera(self):
        """Top-left corner of the map, in pixels, for the current zoom.

        At zoom 1 the whole map fits the viewport and this is always
        (0, 0). Zoomed in it follows the player, clamped so the view
        never runs off the edge of the map and shows background.
        """
        map_w = C.MAP_WIDTH * C.TILE_SIZE
        map_h = C.MAP_HEIGHT * C.TILE_SIZE
        cam_x = int(self.player.render_x * C.TILE_SIZE + C.TILE_SIZE / 2 - C.VIEW_W / 2)
        cam_y = int(self.player.render_y * C.TILE_SIZE + C.TILE_SIZE / 2 - C.VIEW_H / 2)
        return (max(0, min(cam_x, map_w - C.VIEW_W)),
                max(0, min(cam_y, map_h - C.VIEW_H)))

    def _shake_offset(self):
        # C.MAP_OFFSET_X is the base offset that keeps the viewport
        # centred between the two control gutters - not just a screen-shake
        # delta. The camera folds in here too, so every draw that converts
        # a tile to a pixel picks it up without knowing about it.
        cam_x, cam_y = self._camera()
        ox, oy = C.MAP_OFFSET_X - cam_x, -cam_y
        if self.shake_timer <= 0:
            return ox, oy
        return (ox + random.randint(-self.shake_intensity, self.shake_intensity),
                oy + random.randint(-self.shake_intensity, self.shake_intensity))

    def render(self):
        self._begin_frame()
        if self.state == "install_prompt":
            self._render_install_prompt()
            self._present()
            return

        if self.state == "title":
            self._render_title()
            self._present()
            return

        if self.state == "difficulty_select":
            self._render_difficulty_select()
            self._present()
            return

        if self.state == "class_select":
            self._render_class_select()
            self._present()
            return

        if self.state == "bag":
            self._render_bag()
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

        if self.state == "smith":
            self._render_smith()
            self._present()
            return

        if self.state == "tools":
            self._render_tools()
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
        map_w, map_h = C.VIEW_W, C.VIEW_H
        slack = self.shake_intensity if self.shake_timer > 0 else 0
        self.screen.fill(C.COLOR_BG, (0, 0, C.MAP_OFFSET_X + slack, map_h))
        self.screen.fill(C.COLOR_BG,
                         (C.MAP_OFFSET_X + map_w - slack, 0,
                          C.SCREEN_WIDTH - C.MAP_OFFSET_X - map_w + slack, map_h))
        if slack:
            self.screen.fill(C.COLOR_BG, (0, 0, C.SCREEN_WIDTH, slack))
        # Everything below is drawn in map coordinates and, zoomed in,
        # reaches past the viewport on every side. Clipping is what makes
        # the view a window rather than a drawing that overflows into the
        # gutters and the HUD.
        self._mark("clear")
        self.screen.set_clip((C.MAP_OFFSET_X, 0, C.VIEW_W, C.VIEW_H))
        self._render_map(ox, oy)
        self._mark("map")
        self._render_entities(ox, oy)
        self._render_particles(ox, oy)
        self._render_nameplates(ox, oy)
        self._render_player_marker(ox, oy)
        self._render_damage_numbers(ox, oy)
        self._mark("ents")
        self.screen.set_clip(None)
        self._render_flash()
        self._render_minimap()
        self._mark("mini")
        self._render_boss_bar()
        self._render_boss_banner()
        self._render_banners()
        self._render_hud()
        self._mark("hud")
        self._render_touch_controls()
        self._mark("touch")

        if self.state == "dead":
            self._render_game_over()

        if self.settings.get("show_fps"):
            self._render_fps()
        self._present()

    def _panel(self, rect, fill=None, border=None, radius=None, shadow=True):
        """A rounded surface with a soft edge, used for cards and buttons.

        The "shadow" is a single darker rounded rect offset downwards
        rather than a real blur: blurring would mean a per-frame alpha
        surface, which profiling showed is exactly the kind of cost that
        made this game unplayable on a phone.
        """
        rect = pygame.Rect(rect)
        radius = rect.height // 4 if radius is None else radius
        if shadow:
            pygame.draw.rect(self.screen, C.COLOR_BG,
                             rect.move(0, max(2, rect.height // 22)), border_radius=radius)
        pygame.draw.rect(self.screen, fill or C.COLOR_SURFACE, rect, border_radius=radius)
        pygame.draw.rect(self.screen, border or C.COLOR_BORDER, rect,
                         width=2, border_radius=radius)
        return rect

    def _draw_tap_button(self, rect, label, key, font=None, primary=False):
        """primary=True marks the main action - filled accent, not outlined."""
        rect = pygame.Rect(rect)
        radius = rect.height // 4
        pressed = key == getattr(self, "_pressed_key", None)

        if primary:
            fill = C.COLOR_ACCENT_DIM if pressed else C.COLOR_ACCENT
            border = C.COLOR_ACCENT
            text_color = C.COLOR_ON_ACCENT
        else:
            fill = C.COLOR_SURFACE_HI if pressed else C.COLOR_SURFACE
            border = C.COLOR_BORDER_HI if pressed else C.COLOR_BORDER
            text_color = C.COLOR_TEXT

        # Pressing sinks the button onto its own shadow.
        draw_rect = rect.move(0, max(2, rect.height // 22)) if pressed else rect
        self._panel(draw_rect, fill=fill, border=border, radius=radius,
                    shadow=not pressed)
        text = (font or self.f_body).render(label, True, text_color)
        self.screen.blit(text, text.get_rect(center=draw_rect.center))
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

        title = self.f_title.render(self.t("install_title"), True, C.COLOR_ACCENT)
        body_h = sum(self.pitch_body if line else self.gap_m for line in body)
        total = (title.get_height() + self.gap_l + body_h
                 + (self.gap_xl + self.btn_h if buttons else 0))
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(cx, y)))
        y += title.get_height() + self.gap_l
        y = self._lines_block(body, y)
        if buttons:
            self._button_row(buttons, y + self.gap_xl,
                             primary_first=self.install_phase == "prompt")

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
            (self.t("btn_testroom"), pygame.K_d),
        ]
        # A five-button row can outgrow the screen once translated, so
        # step the label font down until it fits rather than clipping.
        row2_font = self.f_body
        for candidate in (self.f_body, self.f_sm, self.f_xs):
            row2_font = candidate
            widths = [self._btn_w(l, candidate) for l, _ in row2]
            if sum(widths) + self.btn_gap * (len(row2) - 1) <= self.content_w:
                break

        title_surf = self.f_title.render("DUNGEON CRAWLER", True, C.COLOR_ACCENT)
        text_h = sum(self.pitch_body if l else self.gap_m for l in lines)
        fixed = (title_surf.get_height() + self.gap_m + text_h + self.gap_l
                 + self.btn_h + self.btn_gap + self.btn_h + 2 * self.pad)
        if sprite:
            # The hero portrait gets whatever vertical room is left over,
            # never more than its natural size. It is the only elastic
            # thing on this screen, and drawing it at a fixed size pushed
            # the button rows off the bottom of a phone canvas.
            room = C.SCREEN_HEIGHT - fixed - self.gap_m
            if room < sprite.get_height():
                if room < self.gap_xl:
                    sprite = None
                else:
                    w, h = sprite.get_size()
                    sprite = pygame.transform.scale(
                        sprite, (max(1, int(w * room / h)), int(room)))
        total = fixed - 2 * self.pad + (sprite.get_height() + self.gap_m if sprite else 0)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title_surf, title_surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title_surf.get_height() + self.gap_m
        if sprite:
            self.screen.blit(sprite, sprite.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
            y += sprite.get_height() + self.gap_m
        y = self._lines_block(lines, y) + self.gap_l
        y += self._button_row(row1, y, primary_first=True) + self.btn_gap
        self._button_row(row2, y, font=row2_font)

    # 1..4 pick a difficulty on the select screen. Kept next to the
    # renderer so the key a card claims and the key it advertises cannot
    # drift apart.
    DIFFICULTY_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)

    def _render_difficulty_select(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("difficulty_title"))
        y = self._lines_block(
            self._wrap_text(self.t("difficulty_hint"), self.f_sm, self.content_w),
            y, font=self.f_sm, pitch=self.pitch_sm,
            color=C.COLOR_TEXT_DIM) + self.gap_l

        current = self.settings.get("difficulty", C.DEFAULT_DIFFICULTY)
        cards = C.DIFFICULTIES[:len(self.DIFFICULTY_KEYS)]
        card_w = min(self.content_w // len(cards) - self.gap_s,
                     self.content_w // 3)
        rows = [self._difficulty_rows(d) for d in cards]
        # Sized for the *longest* card so all four match, and derived from
        # the same gaps the drawing loop below uses - hardcore has an
        # extra price line, and guessing the height meant that line landed
        # underneath its own button.
        body_h = max(len(r) for r in rows) * self.pitch_xs
        card_h = (self.gap_s + self.f_h1.get_height() + self.gap_s + body_h
                  + self.gap_m + self.btn_h + self.gap_s)

        # Sit the cards a third of the way down the space below the header
        # rather than hard against it. Dead centre reads as bottom-heavy
        # here, because the header is already pinned to the very top.
        back_h = self.btn_h + self.gap_l
        y = max(y, y + (C.SCREEN_HEIGHT - y - card_h - back_h) // 3)

        total_w = card_w * len(cards) + self.gap_s * (len(cards) - 1)
        x = (C.SCREEN_WIDTH - total_w) // 2
        for card, key, lines in zip(cards, self.DIFFICULTY_KEYS, rows):
            rect = pygame.Rect(x, y, card_w, card_h)
            selected = card["id"] == current
            self._panel(rect, border=card["color"] if selected else None)
            name = self.f_h1.render(self._difficulty_name(card), True, card["color"])
            self.screen.blit(name, name.get_rect(midtop=(rect.centerx, rect.y + self.gap_s)))
            ly = rect.y + self.gap_s + name.get_height() + self.gap_s
            for line in lines:
                surf = self.f_xs.render(line, True, C.COLOR_TEXT_DIM)
                self.screen.blit(surf, surf.get_rect(midtop=(rect.centerx, ly)))
                ly += self.pitch_xs
            btn = pygame.Rect(rect.x + self.gap_s, rect.bottom - self.btn_h - self.gap_s,
                              card_w - 2 * self.gap_s, self.btn_h)
            self._draw_tap_button(btn, self.t("btn_choose"), key, font=self.f_sm,
                                  primary=selected)
            x += card_w + self.gap_s

        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)],
                         y + card_h + self.gap_l)

    def _difficulty_rows(self, card):
        """The four numbers that actually differ between difficulties.

        Shown as plain multipliers rather than prose: a player comparing
        four cards side by side wants to see 2.0x next to 1.0x, not read
        four sentences.
        """
        rows = [
            self.t("difficulty_row_hp", value=self._mult_text(card["player_hp"])),
            self.t("difficulty_row_damage", value=self._mult_text(card["player_damage"])),
            self.t("difficulty_row_enemy_hp", value=self._mult_text(card["enemy_hp"])),
            self.t("difficulty_row_enemy_damage", value=self._mult_text(card["enemy_damage"])),
        ]
        markup = card.get("shop_markup_per_level", 0.0)
        if markup:
            rows.append(self.t("difficulty_row_prices", percent=int(markup * 100)))
        return rows

    @staticmethod
    def _mult_text(value):
        return ("%.2f" % value).rstrip("0").rstrip(".") + "x"

    CLASS_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)

    def _render_class_select(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("class_title"))
        y = self._lines_block(
            self._wrap_text(self.t("class_hint"), self.f_sm, self.content_w),
            y, font=self.f_sm, pitch=self.pitch_sm, color=C.COLOR_TEXT_DIM) + self.gap_m

        current = self.settings.get("char_class", C.DEFAULT_CLASS)
        cards = C.CLASSES[:len(self.CLASS_KEYS)]
        card_w = min(self.content_w // len(cards) - self.gap_s, self.content_w // 3)

        rows = [self._class_rows(k) for k in cards]
        # Sized from the card, not the font: this is the one screen where
        # the hero art is meant to be looked at rather than glanced past.
        sprite_h = max(64, int(card_w * 0.22))
        body_h = max(len(r) for r in rows) * self.pitch_xs
        blurb_h = 2 * self.pitch_xs
        card_h = (self.gap_s + sprite_h + self.gap_s + self.f_h1.get_height()
                  + self.gap_s + body_h + blurb_h + self.gap_m + self.btn_h + self.gap_s)

        back_h = self.btn_h + self.gap_l
        y = max(y, y + (C.SCREEN_HEIGHT - y - card_h - back_h) // 3)

        total_w = card_w * len(cards) + self.gap_s * (len(cards) - 1)
        x = (C.SCREEN_WIDTH - total_w) // 2
        for klass, key, lines in zip(cards, self.CLASS_KEYS, rows):
            rect = pygame.Rect(x, y, card_w, card_h)
            selected = klass["id"] == current
            self._panel(rect, border=klass["color"] if selected else None)

            ly = rect.y + self.gap_s
            sprite = self._class_sprite(klass["id"], sprite_h)
            if sprite is not None:
                self.screen.blit(sprite, sprite.get_rect(midtop=(rect.centerx, ly)))
            ly += sprite_h + self.gap_s

            name = self.f_h1.render(self._class_name(klass), True, klass["color"])
            self.screen.blit(name, name.get_rect(midtop=(rect.centerx, ly)))
            ly += name.get_height() + self.gap_s

            for line in lines:
                surf = self.f_xs.render(line, True, C.COLOR_TEXT_DIM)
                self.screen.blit(surf, surf.get_rect(midtop=(rect.centerx, ly)))
                ly += self.pitch_xs
            for line in self._wrap_text(self._class_blurb(klass), self.f_xs,
                                        card_w - 2 * self.gap_s)[:2]:
                surf = self.f_xs.render(line, True, C.COLOR_TEXT)
                self.screen.blit(surf, surf.get_rect(midtop=(rect.centerx, ly)))
                ly += self.pitch_xs

            btn = pygame.Rect(rect.x + self.gap_s, rect.bottom - self.btn_h - self.gap_s,
                              card_w - 2 * self.gap_s, self.btn_h)
            self._draw_tap_button(btn, self.t("btn_choose"), key, font=self.f_sm,
                                  primary=selected)
            x += card_w + self.gap_s

        self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)], y + card_h + self.gap_l)

    def _class_rows(self, klass):
        rows = [
            self.t("class_row_hp", value=self._mult_text(klass["hp_mult"])),
            self.t("class_row_power", value=self._signed(klass.get("power", 0))),
            self.t("class_row_defense", value=self._signed(klass.get("defense", 0))),
            self.t("class_row_crit", value=self._signed_percent(klass.get("crit", 0.0))),
        ]
        if klass.get("elemental_chance"):
            rows.append(self.t("class_row_elemental",
                               value=self._signed_percent(klass["elemental_chance"])))
        return rows

    @staticmethod
    def _signed(value):
        return f"+{value}" if value >= 0 else str(value)

    @staticmethod
    def _signed_percent(value):
        pct = int(round(value * 100))
        return f"+{pct}%" if pct >= 0 else f"{pct}%"

    def _class_sprite(self, class_id, height):
        """The class's portrait, scaled and cached.

        Pixel art again, so transform.scale - the class screen is the one
        place these are shown large, and smoothscale would blur them into
        a smear at four times their native size.
        """
        key = (class_id, height)
        cached = self._class_sprite_cache.get(key)
        if cached is not None:
            return cached
        klass = C.CLASS_BY_ID.get(class_id)
        if klass is None:
            return None
        path = os.path.join(C.CLASS_SPRITE_DIR, f"{klass['sprite']}.png")
        try:
            image = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None
        w, h = image.get_size()
        sprite = pygame.transform.scale(image, (max(1, round(w * height / h)), height))
        self._class_sprite_cache[key] = sprite
        return sprite

    # Keys 1..9 pick a row in the potion bag.
    BAG_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9)

    def _bag_rows(self):
        """The player's flasks, in a stable order.

        Sorted by the order they appear in POTION_TYPES rather than by
        when they were picked up, so a given potion is always in the same
        place in the list and the number key for it does not move around
        between visits.
        """
        order = {p["id"]: i for i, p in enumerate(C.POTION_TYPES)}
        held = [(pid, n) for pid, n in self.player.potion_counts.items()
                if n > 0 and pid in C.POTION_BY_ID]
        held.sort(key=lambda item: order.get(item[0], 999))
        return held

    def _open_bag(self):
        self.bag_page = 0
        self.state = "bag"

    def _bag_key(self, key):
        if key == pygame.K_ESCAPE or key == pygame.K_i:
            self.state = "playing"
            return
        rows = self._bag_rows()
        per_page = len(self.BAG_KEYS)
        page = getattr(self, "bag_page", 0)
        if key == pygame.K_RIGHT and (page + 1) * per_page < len(rows):
            self.bag_page = page + 1
            return
        if key == pygame.K_LEFT and page > 0:
            self.bag_page = page - 1
            return
        if key in self.BAG_KEYS:
            index = page * per_page + self.BAG_KEYS.index(key)
            if index < len(rows):
                self.state = "playing"
                self._drink_potion(rows[index][0])

    def _render_bag(self):
        self.screen.fill(C.COLOR_BG)
        self._tap_targets = []
        y = self._screen_header(self.t("bag_title"))

        rows = self._bag_rows()
        if not rows:
            self._lines_block([self.t("bag_empty")], y + self.gap_l,
                              color=C.COLOR_TEXT_DIM)
            self._button_row([(self.t("btn_back"), pygame.K_ESCAPE)],
                             C.SCREEN_HEIGHT - self.pad - self.btn_h)
            return

        per_page = len(self.BAG_KEYS)
        page = min(getattr(self, "bag_page", 0), (len(rows) - 1) // per_page)
        self.bag_page = page
        visible = rows[page * per_page:(page + 1) * per_page]

        bottom = C.SCREEN_HEIGHT - self.pad - self.btn_h - self.gap_l
        row_h = max(self.f_sm.get_height() + self.gap_s,
                    min(self.btn_h,
                        (bottom - y - self.gap_s * (len(visible) - 1)) // len(visible)))
        icon_h = max(12, row_h - self.gap_s)
        drink_w = self._btn_w(self.t("btn_drink"), self.f_sm)

        for i, (potion_id, count) in enumerate(visible):
            info = C.POTION_BY_ID[potion_id]
            rect = pygame.Rect(self.pad, y, self.content_w, row_h)
            selected = potion_id == self.player.selected_potion
            self._panel(rect, border=info["color"] if selected else None, shadow=False)

            x = rect.x + self.gap_s
            sprite = self._potion_sprite(potion_id, icon_h)
            if sprite is not None:
                self.screen.blit(sprite, sprite.get_rect(
                    midleft=(x, rect.centery)))
                x += sprite.get_width() + self.gap_s

            key_label = self.f_sm.render(f"{i + 1}.", True, C.COLOR_TEXT_DIM)
            self.screen.blit(key_label, key_label.get_rect(midleft=(x, rect.centery)))
            x += key_label.get_width() + self.gap_s

            title = self.f_sm.render(f"{self.tn(info['name'])}  x{count}", True,
                                     info["color"])
            self.screen.blit(title, (x, rect.centery - title.get_height()))
            desc = self.f_xs.render(self._potion_description(info), True,
                                    C.COLOR_TEXT_DIM)
            self.screen.blit(desc, (x, rect.centery + 2))

            self._draw_tap_button(
                (rect.right - self.gap_s - drink_w,
                 rect.centery - min(row_h, self.btn_h) // 2,
                 drink_w, min(row_h, self.btn_h)),
                self.t("btn_drink"), self.BAG_KEYS[i], font=self.f_sm,
                primary=selected)
            y += row_h + self.gap_s

        buttons = [(self.t("btn_back"), pygame.K_ESCAPE)]
        if len(rows) > per_page:
            buttons = ([(self.t("btn_prev"), pygame.K_LEFT)] + buttons
                       + [(self.t("btn_next"), pygame.K_RIGHT)])
        self._button_row(buttons, C.SCREEN_HEIGHT - self.pad - self.btn_h)

    def _potion_description(self, info):
        """A one-line summary built from the effect data itself.

        Written this way rather than as thirty hand-translated sentences:
        the numbers then cannot drift out of step with the table, and a
        new potion needs no new strings at all.
        """
        effect = info["effect"]
        parts = []
        if effect.get("heal_pct"):
            parts.append(self.t("potion_desc_heal_full"))
        elif effect.get("heal"):
            parts.append(self.t("potion_desc_heal", amount=effect["heal"]))
        if effect.get("max_hp"):
            parts.append(self.t("potion_desc_max_hp", amount=effect["max_hp"]))
        if effect.get("base_power"):
            parts.append(self.t("potion_desc_power", amount=effect["base_power"]))
        if effect.get("base_defense"):
            parts.append(self.t("potion_desc_defense", amount=effect["base_defense"]))
        if effect.get("xp_levels"):
            parts.append(self.t("potion_desc_xp"))
        if effect.get("buff"):
            parts.append(self.t("potion_desc_buff",
                                buff=self._buff_name(effect["buff"]),
                                turns=effect.get("turns", 10)))
        if effect.get("shield"):
            parts.append(self.t("potion_desc_shield", amount=effect["shield"]))
        if effect.get("cure") or effect.get("cure_debuffs"):
            parts.append(self.t("potion_desc_cure"))
        if effect.get("reveal"):
            parts.append(self.t("potion_desc_reveal"))
        if effect.get("blink"):
            parts.append(self.t("potion_desc_blink"))
        if effect.get("gold"):
            parts.append(self.t("potion_desc_gold"))
        if effect.get("burst_damage"):
            parts.append(self.t("potion_desc_burst", amount=effect["burst_damage"]))
        if effect.get("self_poison"):
            parts.append(self.t("potion_desc_self_poison"))
        return "  ·  ".join(parts) or self.t("potion_desc_unknown")

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
            name_color = color if discovered else C.COLOR_TEXT_DIM
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
            self.screen.blit(self.f_h1.render(heading, True, C.COLOR_XP_BAR_FG), (self.pad, y))
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
        title = self.f_title.render(self.t("pause_title"), True, C.COLOR_ACCENT)
        total = (title.get_height() + self.gap_l
                 + len(buttons) * self.btn_h + (len(buttons) - 1) * self.btn_gap)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title.get_height() + self.gap_l
        # One uniform width for the stack, driven by the longest label so
        # German and English both line up.
        w = max(self._btn_w(label) for label, _ in buttons)
        for i, (label, key) in enumerate(buttons):
            self._draw_tap_button((C.SCREEN_WIDTH // 2 - w // 2, y, w, self.btn_h),
                                  label, key, primary=(i == 0))
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
        title = self.f_title.render(self.t("settings_title"), True, C.COLOR_ACCENT)
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
            (self.t("settings_zoom_label", state=self._mult_text(self._zoom())),
             self.t("btn_toggle"), pygame.K_z),
            (self.t("settings_render_label", state=self._render_scale_name()),
             self.t("btn_toggle"), pygame.K_r),
            (self.t("settings_fps_label",
                    state=self.t("on" if self.settings.get("show_fps") else "off")),
             self.t("btn_toggle"), pygame.K_p),
            (self.t("settings_update_label", build=updater.current_build()),
             self.t("btn_check_update"), pygame.K_u),
        ]
        if not ON_ANDROID:
            rows.append((
                self._shortcut_status or self.t("settings_shortcut_label"),
                self.t("btn_create"), pygame.K_k,
            ))
        # Label left, button right on one shared row - stacking the label
        # above its button needs one extra row each and overflows.
        #
        # The row height is fitted to the space rather than fixed: the
        # list has grown to six or seven entries and at a fixed btn_h the
        # last one ran off the bottom of a phone. Floored at the 48dp
        # touch minimum, so it shrinks only as far as it may.
        btn_w = max(self._btn_w(b) for _, b, _ in rows)
        available = C.SCREEN_HEIGHT - self.pad - y

        # Two columns once one will not hold the list at a legal touch
        # size. The list has grown to six or seven entries and a phone
        # canvas cannot stack that many 48dp rows - but it is 2448px
        # wide, so the room is there sideways.
        per_col = len(rows)
        while (per_col * self.btn_h_min
               + self.btn_gap * (per_col - 1)) > available and per_col > 1:
            per_col = (per_col + 1) // 2
        columns = (len(rows) + per_col - 1) // per_col
        col_w = (C.SCREEN_WIDTH - 2 * self.pad
                 - self.gap_l * (columns - 1)) // columns
        row_h = max(self.btn_h_min,
                    min(self.btn_h,
                        (available - self.btn_gap * (per_col - 1)) // per_col))
        font = self.f_body if columns == 1 else self.f_sm

        for i, (label, btn, key) in enumerate(rows):
            col, slot = divmod(i, per_col)
            x = self.pad + col * (col_w + self.gap_l)
            ry = y + slot * (row_h + self.btn_gap)
            text = font.render(label, True, C.COLOR_HUD_TEXT)
            self.screen.blit(text, text.get_rect(midleft=(x, ry + row_h // 2)))
            self._draw_tap_button(
                (x + col_w - btn_w, ry, btn_w, row_h), btn, key, font=font)

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

        title = self.f_title.render(self.t("touch_warn_title"), True, C.COLOR_DANGER)
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
            radius = rect.height // 4
            pygame.draw.rect(self.screen, C.COLOR_SURFACE, rect, border_radius=radius)
            pygame.draw.rect(self.screen, C.COLOR_BORDER, rect, width=2, border_radius=radius)
            label = self.f_body.render(confirm_label, True, C.COLOR_TEXT_DIM)
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
            self._button_row(row, y, primary_first=(phase in ("available", "error", "needs_permission")))

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

        title = self.f_title.render(self.t("levelup_title"), True, C.COLOR_ACCENT)
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
            self._panel(card, fill=C.COLOR_SURFACE, border=C.COLOR_BORDER_HI,
                        radius=self.gap_m)

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
            self._panel(strip, fill=C.COLOR_ACCENT, border=C.COLOR_ACCENT,
                        radius=strip.height // 4, shadow=False)
            label = self.f_body.render(self.t("btn_choose"), True, C.COLOR_ON_ACCENT)
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

        stock_list = getattr(self, "shop_stock", None) or C.SHOP_STOCK
        keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                pygame.K_5, pygame.K_6]
        # Shrink the rows only if a future stock list would not otherwise
        # fit, and never below a usable touch height.
        avail = C.SCREEN_HEIGHT - self.pad - self.btn_h - self.gap_l - y
        stock_list = stock_list[:len(keys)]
        n = len(stock_list)
        row_h = max(self.btn_h // 2,
                    min(self.btn_h, (avail - self.btn_gap * (n - 1)) // max(1, n)))
        buy_w = self._btn_w(self.t("btn_buy"))
        for i, stock in enumerate(stock_list):
            label = f"{i + 1}. {self.tn(stock['name'])} - {self._shop_price(stock)} {self.t('gold_word')}"
            text = self.f_body.render(label, True, C.COLOR_HUD_TEXT)
            self.screen.blit(text, text.get_rect(midleft=(self.pad, y + row_h // 2)))
            self._draw_tap_button(
                (C.SCREEN_WIDTH - self.pad - buy_w, y, buy_w, row_h),
                self.t("btn_buy"), keys[i])
            y += row_h + self.btn_gap

        self._button_row([(self.t("btn_leave"), pygame.K_ESCAPE)],
                         C.SCREEN_HEIGHT - self.pad - self.btn_h)

    MINIMAP_POS = (8, 8)
    MINIMAP_SCALE = 3

    def _rebuild_minimap_cache(self):
        """Paints the explored tiles into a surface, once per change.

        This used to draw one rectangle per explored tile every frame -
        a thousand of them on a fully explored floor, plus a fresh
        translucent panel surface each time. It was the single largest
        item in a frame, and "many small draws" is exactly the pattern
        that is slow on the device (see Game.__init__). Invalidated
        alongside the map cache, which has the same trigger.
        """
        scale = self.MINIMAP_SCALE
        w, h = C.MAP_WIDTH * scale, C.MAP_HEIGHT * scale
        surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
        surf.fill((10, 10, 16, 170))
        for (x, y) in self.explored:
            color = (90, 90, 100) if self.grid[y][x] == dungeon.WALL else (55, 55, 65)
            pygame.draw.rect(surf, color, (2 + x * scale, 2 + y * scale, scale, scale))
        self._minimap_cache = surf

    def _render_minimap(self):
        if getattr(self, "_minimap_cache", None) is None:
            self._rebuild_minimap_cache()
        mini_x, mini_y = self.MINIMAP_POS
        scale = self.MINIMAP_SCALE
        self.screen.blit(self._minimap_cache, (mini_x, mini_y))
        # The two markers move without the explored set changing, so they
        # stay out of the cache - two rectangles a frame instead of a
        # thousand.
        if self.stairs_pos in self.explored:
            sx, sy = self.stairs_pos
            pygame.draw.rect(self.screen, C.COLOR_STAIRS,
                             (mini_x + 2 + sx * scale, mini_y + 2 + sy * scale, scale, scale))
        px, py = self.player.x, self.player.y
        pygame.draw.rect(self.screen, (255, 255, 255),
                         (mini_x + 2 + px * scale, mini_y + 2 + py * scale, scale, scale))

    def _render_boss_bar(self):
        if self.enemies_off:
            return
        boss = next((m for m in self.monsters if m.is_boss and m.awake and m.is_alive()), None)
        if boss is None:
            return
        bar_w = min(self.content_w, C.SCREEN_WIDTH // 2)
        bar_h = self.f_sm.get_linesize() + self.gap_s
        x, y = C.SCREEN_WIDTH // 2 - bar_w // 2, self.gap_s
        rad = bar_h // 2
        pygame.draw.rect(self.screen, (38, 14, 40), (x, y, bar_w, bar_h), border_radius=rad)
        ratio = max(0, boss.hp / boss.max_hp)
        # The bar changes colour with the phase, so the fight visibly
        # escalates instead of the player only noticing they are suddenly
        # taking more damage.
        phase = self._boss_phase(boss)
        fill = phase["color"] if phase else C.COLOR_BOSS
        if ratio > 0:
            pygame.draw.rect(self.screen, fill,
                             (x, y, max(bar_h, int(bar_w * ratio)), bar_h), border_radius=rad)
        # Where the next phase begins, so it can be seen coming.
        for threshold in C.BOSS_PHASES:
            tick_x = x + int(bar_w * threshold["at"])
            pygame.draw.line(self.screen, (18, 8, 20), (tick_x, y + 2),
                             (tick_x, y + bar_h - 2), 2)
        pygame.draw.rect(self.screen, C.COLOR_BORDER_HI, (x, y, bar_w, bar_h),
                         width=2, border_radius=rad)
        boss_name = self._monster_display_name(boss).upper()
        label = f"{boss_name}  {max(0, boss.hp)}/{boss.max_hp}"
        if phase:
            label += f"  ·  {self.tn(phase['name']).upper()}"
        name_text = self.font.render(label, True, (255, 255, 255))
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
        ts = C.TILE_SIZE
        # Only the window the camera can see, plus a tile of margin, not
        # the whole map. Zoomed in the map is several times the size of
        # the viewport, and painting all of it cost 19MB and 19ms a turn
        # to produce something that was then 80% off-screen.
        cam_x, cam_y = self._camera()
        x0 = max(0, cam_x // ts - 1)
        y0 = max(0, cam_y // ts - 1)
        cols = min(C.MAP_WIDTH - x0, C.VIEW_W // ts + 3)
        rows_n = min(C.MAP_HEIGHT - y0, C.VIEW_H // ts + 3)
        self._map_cache_origin = (x0, y0, cols, rows_n)
        surf = pygame.Surface((cols * ts, rows_n * ts))
        surf.fill(C.COLOR_BG)
        for y in range(y0, y0 + rows_n):
            row = self.grid[y]
            for x in range(x0, x0 + cols):
                if (x, y) not in self.explored:
                    continue
                px, py = (x - x0) * ts, (y - y0) * ts
                dim = (x, y) not in self.visible
                is_wall = row[x] == dungeon.WALL
                name = self._wall_tile_name(x, y) if is_wall else self._floor_tile_name(x, y)
                tile = self._tile(name, dim) if name else None
                if is_wall:
                    # Every wall cell gets flat rock underneath, then its
                    # frame on top. The frames are wall *surfaces* with
                    # transparent gaps - a room's bottom edge is a thin
                    # ledge band and nothing else - so without a fill they
                    # hang in mid-air as floating stripes. Deliberately the
                    # *dim* colour even when lit: this is unlit rock behind
                    # the wall face, and at the lit colour it matched the
                    # floor tiles closely enough that rooms and solid rock
                    # were hard to tell apart.
                    rock = tier["wall_dim"]
                    if dim:
                        rock = tuple(int(c * C.TILE_DIM_FACTOR) for c in rock)
                    pygame.draw.rect(surf, rock, (px, py, ts, ts))
                if tile is None:
                    # Solid rock, or a missing tileset - a flat fill in the
                    # theme colour, so a missing asset degrades to the old
                    # look instead of an invisible dungeon.
                    if not is_wall:
                        color = tier["floor_dim"] if dim else tier["floor"]
                        pygame.draw.rect(surf, color, (px, py, ts, ts))
                    continue
                # Tiles taller than one cell (wall fronts, columns) hang
                # upwards out of their cell, the way the tileset is drawn.
                surf.blit(tile, (px, py + ts - tile.get_height()))
                decor = self._decor.get((x, y))
                if decor:
                    piece = self._tile(decor, dim)
                    if piece is not None:
                        surf.blit(piece, (px, py + ts - piece.get_height()))
        self._map_cache = surf

    def _map_window_stale(self):
        """Whether the cached window still covers what the camera sees."""
        origin = getattr(self, "_map_cache_origin", None)
        if origin is None:
            return True
        x0, y0, cols, rows_n = origin
        ts = C.TILE_SIZE
        cam_x, cam_y = self._camera()
        return not (x0 * ts <= cam_x and y0 * ts <= cam_y
                    and (x0 + cols) * ts >= cam_x + C.VIEW_W
                    and (y0 + rows_n) * ts >= cam_y + C.VIEW_H)

    def _render_map(self, ox=0, oy=0):
        if getattr(self, "_map_cache", None) is None or self._map_window_stale():
            self._rebuild_map_cache()
        x0, y0, _cols, _rows = self._map_cache_origin
        self.screen.blit(self._map_cache,
                         (ox + x0 * C.TILE_SIZE, oy + y0 * C.TILE_SIZE))

        if self.stairs_pos in self.explored:
            self._draw_ladder(*self.stairs_pos, ox, oy)

        if self.up_stairs_pos and self.up_stairs_pos in self.explored:
            self._draw_char("<", self.up_stairs_pos[0], self.up_stairs_pos[1], C.COLOR_STAIRS_UP, ox, oy)

        if self.shrine_pos and self.shrine_pos in self.explored:
            self._draw_char("A", self.shrine_pos[0], self.shrine_pos[1], C.COLOR_SHRINE, ox, oy)

        # Hazards, chest and door draw here rather than in the map cache:
        # all three change during play (a collapsing floor gives way, a
        # chest opens, a door unbars) and repainting the whole cache for
        # each would be far more work than blitting a handful of tiles.
        ts = C.TILE_SIZE
        for (hx, hy), kind in self.hazards.items():
            if (hx, hy) not in self.explored:
                continue
            info = C.HAZARD_TYPES[kind]
            dim = (hx, hy) not in self.visible
            # Art first, then a translucent colour wash over the top. The
            # tileset has no lava frame and the substitutes read as dark
            # smudges on dark stone - a hazard the player cannot pick out
            # at a glance is just an unfair hit. Over, not under: these
            # frames are fully opaque and painted straight over a wash.
            self._draw_tile_at(info["tile"], hx, hy, ox, oy, dim=dim)
            self.screen.blit(self._hazard_wash(kind, dim),
                             (hx * ts + ox, hy * ts + oy))

        if self.chest_pos and self.chest_pos in self.explored:
            dim = self.chest_pos not in self.visible
            if not self.chest_open and not dim:
                # Same halo trick as elite monsters: a closed chest is
                # otherwise a small dark box that the guardian standing
                # over it hides completely.
                glow = self._glow(C.COLOR_ACCENT, ts * 2)
                self.screen.blit(glow, glow.get_rect(center=(
                    self.chest_pos[0] * ts + ts // 2 + ox,
                    self.chest_pos[1] * ts + ts // 2 + oy)))
            # A mimic uses the *same* closed-chest frame as a real one.
            # Giving it its own art would give the game away, and the
            # whole point is that a chest is no longer a free action.
            frame = ("chest_empty_open_anim_f2" if self.chest_open
                     else "chest_full_open_anim_f0")
            self._draw_tile_at(frame, *self.chest_pos, ox, oy, dim=dim)

        if self.boss_door_pos and self.boss_door_pos in self.explored and self._boss_door_blocked():
            self._draw_tile_at("doors_leaf_closed", *self.boss_door_pos, ox, oy,
                               dim=self.boss_door_pos not in self.visible)

    def _glow(self, color, size, alpha=70):
        """A soft elliptical halo, cached.

        Elites, the chest and the blacksmith all draw one of these every
        frame, and each was allocating a fresh per-pixel-alpha surface to
        do it. Allocating and alpha-blending small surfaces per frame is
        the exact pattern that costs this game its frame rate on a real
        device - the same reason the map is painted into a cache.
        """
        key = (tuple(color), size, alpha)
        cached = self._glow_cache.get(key)
        if cached is None:
            cached = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.ellipse(cached, (*color, alpha), cached.get_rect())
            self._glow_cache[key] = cached
        return cached

    def _hazard_wash(self, kind, dim):
        """The colour overlay for one hazard tile, cached per kind.

        Every tile of a kind looks the same, so this was building an
        identical surface per hazard per frame - a dozen allocations a
        frame on a floor with a lava field on it.
        """
        key = (kind, dim, C.TILE_SIZE)
        cached = self._wash_cache.get(key)
        if cached is None:
            info = C.HAZARD_TYPES[kind]
            ts = C.TILE_SIZE
            cached = pygame.Surface((ts, ts), pygame.SRCALPHA)
            cached.fill((*info["color"], 60 if dim else 120))
            pygame.draw.rect(cached, (*info["color"], 110 if dim else 235),
                             (0, 0, ts, ts), width=max(1, ts // 12))
            self._wash_cache[key] = cached
        return cached

    def _draw_tile_at(self, name, x, y, ox=0, oy=0, dim=False):
        """Blits one tileset frame over a map cell, bottom-aligned.

        Bottom-aligned because several frames are taller than a cell and
        are drawn hanging upwards out of it, the same way the map cache
        places wall fronts.
        """
        tile = self._tile(name, dim)
        if tile is None:
            return
        ts = C.TILE_SIZE
        self.screen.blit(tile, (x * ts + ox, y * ts + oy + ts - tile.get_height()))

    def _render_entities(self, ox=0, oy=0):
        for item in self.items:
            if (item.x, item.y) in self.visible:
                self._draw_item(item, ox, oy)

        for merchant in self.merchants:
            if (merchant.x, merchant.y) in self.visible:
                self._draw_merchant(merchant, ox, oy)

        for smith in self.blacksmiths:
            if (smith.x, smith.y) in self.visible:
                self._draw_blacksmith(smith, ox, oy)

        if not self.enemies_off:
            for monster in self.monsters:
                if (monster.x, monster.y) in self.visible:
                    self._draw_monster(monster, ox, oy)
                    self._record_bestiary(monster.kind)

        self._draw_player(ox, oy)

    def _render_player_marker(self, ox=0, oy=0):
        """A "YOU" label and an arrow pointing down at your own character.

        The hero is one small sprite among up to a dozen others, all of
        them now wearing nameplates, and on a phone it is genuinely easy
        to lose track of which one you are steering. Follows the player's
        interpolated position so it slides along with them rather than
        snapping a tile ahead.
        """
        ts = C.TILE_SIZE
        cx = int(self.player.render_x * ts + ts / 2 + ox)
        # Measured off the sprite's own height, not the tile's: the hero is
        # drawn nearly twice as tall as a cell and hangs upwards out of it,
        # so anchoring to the tile put the arrow across their face.
        sprite = self.player_sprite_right
        sprite_h = sprite.get_height() if sprite else ts
        sprite_top = int(self.player.render_y * ts + oy) + ts + 2 - sprite_h
        bottom = sprite_top + self._player_head_pad - max(2, ts // 8)

        arrow_h = max(4, ts // 4)
        arrow_w = max(6, ts // 3)
        tip = (cx, bottom)
        left = (cx - arrow_w // 2, bottom - arrow_h)
        right = (cx + arrow_w // 2, bottom - arrow_h)
        # Outlined the same way the label is, so it stays readable over
        # both pale stone and near-black rock.
        pygame.draw.polygon(self.screen, (0, 0, 0),
                            [(tip[0], tip[1] + 1), (left[0] - 1, left[1] - 1),
                             (right[0] + 1, right[1] - 1)])
        pygame.draw.polygon(self.screen, C.COLOR_ACCENT, [tip, left, right])

        label = self._player_marker_label()
        self.screen.blit(label, label.get_rect(
            midbottom=(cx, bottom - arrow_h + 1)))

    def _player_marker_label(self):
        key = ("__you__", self._lang())
        cached = self._name_cache.get(key)
        if cached is None:
            cached = self._f_tiny_outlined(self.t("marker_you"), C.COLOR_ACCENT)
            self._name_cache[key] = cached
        return cached

    def _render_nameplates(self, ox=0, oy=0):
        """Name, level, health bar and status icons above each monster.

        Until now the only way to know what you were fighting, how hurt it
        was, or whether your last hit had actually set it on fire was the
        message log. The bar is drawn directly; the text is cached, since
        the same handful of strings would otherwise be re-rasterised for
        every monster on every frame - re-rendering text per frame is
        exactly what once dropped this game to 3.9 fps on a real phone.
        """
        if self.enemies_off:
            return
        ts = C.TILE_SIZE
        bar_h = max(2, ts // 8)
        for monster in self.monsters:
            if (monster.x, monster.y) not in self.visible:
                continue
            if not monster.is_alive():
                continue
            cx = int(monster.render_x * ts + ts / 2 + ox)
            # Everything stacks upwards from just above the monster's head,
            # so a monster with no status effects has no gap where the
            # icons would have been: status icons, then name, then bar.
            y = int(monster.render_y * ts + oy) - max(1, ts // 10)

            badges = [b for b in C.STATUS_BADGES if getattr(monster, b["field"], 0) > 0]
            if badges:
                y -= self._draw_status_badges(badges, cx, y)

            label = self._nameplate_text(monster)
            if label is not None:
                self.screen.blit(label, label.get_rect(midbottom=(cx, y)))
                y -= label.get_height()

            width = max(ts, int(ts * 1.1))
            ratio = max(0.0, min(1.0, monster.hp / max(1, monster.max_hp)))
            bar = pygame.Rect(cx - width // 2, y - bar_h, width, bar_h)
            pygame.draw.rect(self.screen, (18, 10, 12), bar.inflate(2, 2))
            pygame.draw.rect(self.screen, C.COLOR_HP_BAR_BG, bar)
            if ratio > 0:
                pygame.draw.rect(self.screen, self._nameplate_hp_color(monster),
                                 (bar.x, bar.y, max(1, int(width * ratio)), bar_h))

    @staticmethod
    def _nameplate_hp_color(monster):
        if monster.is_boss:
            return C.COLOR_BOSS
        if monster.elite_name:
            return monster.color
        return C.COLOR_HP_BAR_FG

    def _nameplate_text(self, monster):
        key = (monster.kind, monster.elite_name, monster.level, self._lang())
        cached = self._name_cache.get(key)
        if cached is None:
            name = self._monster_display_name(monster)
            text = f"{name} {self.t('nameplate_level', level=monster.level)}"
            color = C.COLOR_BOSS if monster.is_boss else (
                monster.color if monster.elite_name else C.COLOR_TEXT_DIM)
            cached = self._f_tiny_outlined(text, color)
            self._name_cache[key] = cached
        return cached

    def _f_tiny_outlined(self, text, color):
        """Small text with a hard black outline.

        Nameplates sit on top of the dungeon, not on a panel, and the
        tileset has both near-black rock and pale stone in it - plain text
        disappears into one or the other depending on where the monster is
        standing. Rendering the string five times is fine here because the
        result is cached.
        """
        body = self.f_tiny.render(text, True, color)
        shadow = self.f_tiny.render(text, True, (0, 0, 0))
        out = pygame.Surface((body.get_width() + 2, body.get_height() + 2),
                             pygame.SRCALPHA)
        for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            out.blit(shadow, (dx, dy))
        out.blit(body, (1, 1))
        return out

    def _status_pip(self, badge):
        """One status effect as a small filled chip with a letter in it.

        A bare coloured letter at this size is a few pixels of thin
        strokes - "!" for stunned came out almost invisible against the
        stonework. A solid chip is a colour you can read at a glance even
        when you cannot make out the letter, which is what actually
        matters mid-fight; the letter tells you which one once you look.
        """
        glyph = self.f_tiny.render(badge["char"], True, (12, 12, 14))
        size = max(glyph.get_height(), glyph.get_width() + 3)
        chip = pygame.Surface((size, size), pygame.SRCALPHA)
        radius = max(1, size // 4)
        pygame.draw.rect(chip, (10, 10, 12), (0, 0, size, size), border_radius=radius)
        pygame.draw.rect(chip, badge["color"], (1, 1, size - 2, size - 2),
                         border_radius=radius)
        chip.blit(glyph, glyph.get_rect(center=(size // 2, size // 2)))
        return chip

    def _draw_status_badges(self, badges, cx, bottom):
        """Draws the icon row with its bottom edge at `bottom`, and returns
        how tall it was so the caller can stack the name above it."""
        gap = max(1, C.TILE_SIZE // 12)
        chips = []
        for badge in badges:
            chip = self._badge_cache.get(badge["char"])
            if chip is None:
                chip = self._status_pip(badge)
                self._badge_cache[badge["char"]] = chip
            chips.append(chip)
        height = max(c.get_height() for c in chips)
        total = sum(c.get_width() for c in chips) + gap * (len(chips) - 1)
        x = cx - total // 2
        for chip in chips:
            self.screen.blit(chip, (x, bottom - chip.get_height()))
            x += chip.get_width() + gap
        return height

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
            glow = self._glow(monster.color,
                              int(max(sprite.get_size()) * 1.3), alpha=100)
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

    def _draw_blacksmith(self, smith, ox=0, oy=0):
        sprite = self.blacksmith_sprite
        if sprite is None:
            self._draw_char(smith.char, smith.x, smith.y, smith.color, ox, oy)
            return
        ts = C.TILE_SIZE
        center = (int(smith.x * ts + ts // 2 + ox), int(smith.y * ts + ts // 2 + oy))
        # A warm halo, the same trick elites and the chest use: he is one
        # small figure in a room and worth walking over to.
        glow = self._glow(C.COLOR_BLACKSMITH, ts * 2)
        self.screen.blit(glow, glow.get_rect(center=center))
        rect = sprite.get_rect(midbottom=(center[0], int(smith.y * ts + ts + oy) + 2))
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
        overlay = pygame.Surface((C.VIEW_W, C.VIEW_H))
        overlay.set_alpha(int(90 * (self.flash_timer / 6)))
        overlay.fill((200, 30, 30))
        self.screen.blit(overlay, (C.MAP_OFFSET_X, 0))

    def _hud_chip(self, x, y, h, icon, text, text_color=None, icon_color=None,
                  min_w=0):
        """A rounded pill holding an icon and a value.

        icon is either a key into self.hud_icons (real item art) or a
        single character to draw as a coloured glyph when no art exists
        for it.
        """
        f = self.f_sm
        art = self.hud_icons.get(icon) if isinstance(icon, str) else None
        glyph = None if art else f.render(str(icon), True, icon_color or C.COLOR_TEXT)
        label = f.render(text, True, text_color or C.COLOR_TEXT)
        icon_w = art.get_width() if art else glyph.get_width()
        pad = self.gap_s
        w = max(min_w, pad + icon_w + self.gap_s // 2 + label.get_width() + pad)
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, C.COLOR_SURFACE_HI, rect, border_radius=h // 3)
        cx = x + pad
        if art:
            self.screen.blit(art, art.get_rect(midleft=(cx, rect.centery)))
        else:
            self.screen.blit(glyph, glyph.get_rect(midleft=(cx, rect.centery)))
        self.screen.blit(label, label.get_rect(
            midleft=(cx + icon_w + self.gap_s // 2, rect.centery)))
        return w

    def _hud_bar(self, x, y, w, h, ratio, bg, fg, text):
        """A rounded bar with its numbers sitting on top of it."""
        r = h // 2
        pygame.draw.rect(self.screen, bg, (x, y, w, h), border_radius=r)
        if ratio > 0:
            pygame.draw.rect(self.screen, fg,
                             (x, y, max(h, int(w * min(1.0, ratio))), h), border_radius=r)
        label = self.f_sm.render(text, True, C.COLOR_TEXT)
        self.screen.blit(label, label.get_rect(center=(x + w // 2, y + h // 2)))

    def _render_hud(self):
        """Draws the HUD band, reusing last frame's when nothing changed.

        The band is a few dozen text renders and rounded chips, and none
        of it can change without input: a turn only happens because the
        player pressed or tapped something, and that same event sets
        needs_redraw. Frames that redraw purely because something is
        animating - a monster sliding, sparks falling - therefore get the
        cached band instead of rasterising the same text again.
        """
        hud_y = C.VIEW_H
        band = (0, hud_y, C.SCREEN_WIDTH, C.HUD_HEIGHT)
        if not self.needs_redraw and self._hud_cache is not None:
            self.screen.blit(self._hud_cache, (0, hud_y))
            return
        self._paint_hud(hud_y)
        self._hud_cache = self.screen.subsurface(band).copy()

    def _paint_hud(self, hud_y):
        # Uses the full width: the touch controls now sit above the band
        # (see _setup_touch_controls), so the old habit of indenting all
        # HUD content by the gutter left a third of the row empty.
        pygame.draw.rect(self.screen, C.COLOR_HUD_BG, (0, hud_y, C.SCREEN_WIDTH, C.HUD_HEIGHT))
        pygame.draw.rect(self.screen, C.COLOR_BORDER, (0, hud_y, C.SCREEN_WIDTH, 2))

        f = self.f_sm
        gap = self.gap_s
        chip_h = f.get_height() + gap
        left = self.pad
        right_edge = C.SCREEN_WIDTH - self.pad
        y = hud_y + gap

        # --- row 1: health and experience, numbers inside the bars ---
        bar_h = chip_h
        bar_w = (right_edge - left - gap) // 2
        self._hud_bar(left, y, bar_w, bar_h,
                      self.player.hp / self.player.max_hp,
                      C.COLOR_HP_BAR_BG, C.COLOR_HP_BAR_FG,
                      f"{max(0, self.player.hp)} / {self.player.max_hp}")
        self._hud_bar(left + bar_w + gap, y, bar_w, bar_h,
                      self.player.xp / self.player.xp_to_next,
                      C.COLOR_XP_BAR_BG, C.COLOR_XP_BAR_FG,
                      f"Lv {self.player.level}   {self.player.xp} / {self.player.xp_to_next} XP")
        y += bar_h + gap

        # --- rows 2-3: chips on the left, combat log filling the right ---
        # The chips alone left no vertical room for the log (measured: 0
        # lines fit), and the right-hand half of these rows was empty, so
        # the log moves there rather than being dropped.
        weapon_color = C.RARITY_BY_ID.get(self.player.weapon_rarity_id, {}).get("color", C.COLOR_TEXT)
        weapon_text = f"{self.tn(self.player.weapon_name)} +{self.player.weapon_bonus}"
        if self.player.weapon_element_id:
            weapon_text += f" · {self.te(self.player.weapon_element_id)}"
        armor_color = C.RARITY_BY_ID.get(self.player.armor_rarity_id, {}).get("color", C.COLOR_TEXT)
        scrolls = self.player.scrolls
        tier_label = self._tier_name(getattr(self, "tier", C.DUNGEON_TIERS[0]))

        row2 = [
            ("weapon", weapon_text, weapon_color, None),
            ("armor", f"{self.tn(self.player.armor_name)} +{self.player.armor_bonus}",
             armor_color, None),
        ]
        # The potion chip names what the quick-use button would actually
        # drink, not just how many flasks are in the bag - with thirty
        # kinds, a bare count no longer tells you anything useful.
        selected = self.player.selected_potion
        held = self.player.potion_count(selected)
        if held > 0:
            potion_info = C.POTION_BY_ID.get(selected)
            potion_text = f"{self.tn(potion_info['name'])} x{held}" if potion_info else str(held)
            potion_color = potion_info["color"] if potion_info else C.COLOR_POTION
        else:
            potion_text = str(self.player.potions)
            potion_color = C.COLOR_POTION
        row3 = [
            ("potion", potion_text, potion_color, potion_color),
            ("gold", str(self.player.gold), C.COLOR_GOLD, C.COLOR_GOLD),
            ("scroll", f"F {scrolls['fireball']}   T {scrolls['teleport']}   V {scrolls['reveal']}",
             None, None),
        ]
        if self.player.shield > 0:
            row3.append(("!", f"{self.t('hud_shield')} {self.player.shield}",
                         (150, 200, 255), (150, 200, 255)))
        if self.player.poison_turns > 0:
            row3.append(("!", self.t("hud_poisoned"), C.COLOR_POISON, C.COLOR_POISON))
        if self.player.bleed_turns > 0:
            row3.append(("!", self.t("hud_bleeding"), C.COLOR_DANGER, C.COLOR_DANGER))
        # Active potion effects get their own row, each with the turns it
        # has left - a buff you cannot see the remaining duration of is a
        # buff you cannot plan a fight around.
        # Soonest to expire first: those are the ones worth reacting to.
        # Capped at what fits on one line, with a count for the rest -
        # a dozen buffs are possible at once and the row does not wrap.
        active = sorted(((t, b) for b, t in self.player.buffs.items() if b in C.BUFFS))
        row4 = [("!", f"{self._buff_name(b)} {t}",
                 C.BUFFS[b]["color"], C.BUFFS[b]["color"])
                for t, b in active[:C.HUD_MAX_BUFF_CHIPS]]
        if len(active) > C.HUD_MAX_BUFF_CHIPS:
            row4.append(("!", f"+{len(active) - C.HUD_MAX_BUFF_CHIPS}",
                         C.COLOR_TEXT_DIM, C.COLOR_TEXT_DIM))

        # In priority order, and only while there is room. The band is
        # whatever height the map did not use, and on a phone that is not
        # enough for everything - it was silently clipping the bottom row
        # off the screen. Dropping a whole row is honest; half a row of
        # chips cut off by the screen edge is not.
        #
        # Supplies and status first because they change turn to turn,
        # then active effects, then equipment, which is reference
        # information you look at between fights.
        band_bottom = hud_y + C.HUD_HEIGHT - gap
        # How many chip rows the band can actually hold. The +gap is
        # because the last row needs no trailing gap - without it this
        # under-counted by one and quietly dropped the active-effects row,
        # which is the one row you actually need mid-fight.
        fits = max(1, (band_bottom - y + gap) // (chip_h + gap))
        rows = self._hud_rows(row2, row3, row4, fits, weapon_color, armor_color)
        chips_right = left
        row_y = y
        for row in rows:
            if not row:
                continue
            if row_y + chip_h > band_bottom:
                break
            x = left
            for icon, text, tcol, icol in row:
                x += self._hud_chip(x, row_y, chip_h, icon, text,
                                    text_color=tcol, icon_color=icol) + gap
            chips_right = max(chips_right, x)
            row_y += chip_h + gap

        # Depth and kills, on their own line under the chips - flavour,
        # so it is the first thing to go when the band is short.
        stat = self.f_sm.render(
            f"{tier_label}  ·  {self.t('hud_kills')} {self.player.kills}",
            True, C.COLOR_TEXT_DIM)
        if row_y + stat.get_height() <= band_bottom:
            self.screen.blit(stat, (left, row_y))

        # Log to the right of the chips, newest at the bottom, using
        # whatever width the chips did not need.
        log_font = self.f_xs
        pitch = log_font.get_linesize() + 3
        log_x = max(chips_right + gap, left + int((right_edge - left) * 0.5))
        log_w = right_edge - log_x
        avail = hud_y + C.HUD_HEIGHT - gap - y
        room = max(0, avail // pitch)
        if room and log_w > self.btn_min_w:
            lines = []
            for message in self.log[-room:]:
                wrapped = self._wrap_text(message, log_font, log_w)
                lines.extend(wrapped or [message])
            for i, line in enumerate(lines[-room:]):
                self.screen.blit(log_font.render(line, True, C.COLOR_LOG_TEXT),
                                 (log_x, y + i * pitch))

    def _hud_rows(self, equipment, supplies, buffs, fits,
                  weapon_color=None, armor_color=None):
        """Which chip rows to draw, given how many fit.

        The band is whatever height the map did not use, and on a phone
        that is not enough for all of them - it used to just draw them
        anyway and let the screen edge cut the last one in half.

        Order is by how often you need it: supplies and status change
        turn to turn, active effects decide the next few, equipment is
        reference information. When a row has to go, the equipment folds
        into the supplies row without its item names rather than
        vanishing - the bonus and the element are what matter at a
        glance, and the full names are on the death screen and announced
        when they change.
        """
        wanted = [supplies, buffs, equipment] if buffs else [supplies, equipment]
        if len(wanted) <= fits:
            return wanted[:fits]
        compact = [
            ("weapon", f"+{self.player.weapon_bonus}"
             + (f" · {self.te(self.player.weapon_element_id)}"
                if self.player.weapon_element_id else ""),
             weapon_color, None),
            ("armor", f"+{self.player.armor_bonus}", armor_color, None),
        ]
        folded = [compact + supplies] + [r for r in wanted[1:] if r is not equipment]
        return folded[:fits]

    def _hud_icon_row(self, x, y, char, color, text, label_color=None):
        icon = self.f_sm.render(char, True, color)
        self.screen.blit(icon, (x, y))
        label = self.f_sm.render(text, True, label_color or C.COLOR_HUD_TEXT)
        self.screen.blit(label, (x + self.f_sm.size("XX")[0], y))

    def _touch_button_surface(self, size, label, active):
        """One finished button, kept until the layout or language changes.

        A button is three rounded rects and a font render, and there are
        up to eleven of them on screen - every frame, for a picture that
        only changes when a direction is held down. Drawn once into a
        small surface, the frame pays a blit instead.
        """
        key = (size, label, active)
        surf = self._touch_btn_cache.get(key)
        if surf is not None:
            return surf
        w, h = size
        radius = h // 4
        # The shadow is the panel offset downwards, so the surface has to
        # be that much taller or it would be clipped off.
        drop = max(2, h // 22)
        surf = pygame.Surface((w, h + drop), pygame.SRCALPHA)
        face = pygame.Rect(0, 0, w, h)
        if not active:
            pygame.draw.rect(surf, C.COLOR_BG, face.move(0, drop), border_radius=radius)
        pygame.draw.rect(surf, C.COLOR_ACCENT if active else C.COLOR_SURFACE,
                         face, border_radius=radius)
        pygame.draw.rect(surf, C.COLOR_ACCENT if active else C.COLOR_BORDER,
                         face, width=2, border_radius=radius)
        text = self.f_sm.render(label, True,
                                C.COLOR_ON_ACCENT if active else C.COLOR_TEXT)
        surf.blit(text, text.get_rect(center=face.center))
        self._touch_btn_cache[key] = surf
        return surf

    def _draw_touch_button(self, rect, label, active=False):
        self.screen.blit(self._touch_button_surface(rect.size, label, active),
                         rect.topleft)

    def _render_touch_controls(self):
        # The menu button is the only touch path to the pause menu (and
        # from there, to re-enabling everything else), so it always draws
        # regardless of show_touch_controls - only the movement/action
        # buttons are optional.
        self._draw_touch_button(self.save_button, self._touch_label("touch_menu", "ESC"))
        if not self.settings.get("show_touch_controls", True):
            return
        for name, (rect, vector, label) in self.dpad_buttons.items():
            self._draw_touch_button(rect, label, active=(self.touch_direction == vector))
        self._draw_touch_button(self.potion_button, self._touch_label("touch_heal", "G"))
        self._draw_touch_button(self.bag_button, self._touch_label("btn_bag", "I"))
        if self.test_room:
            self._draw_touch_button(self.tools_button, self._touch_label("btn_tools", "K"))
        scroll_labels = {"fireball": "F", "teleport": "T", "reveal": "V"}
        for name, rect in self.scroll_buttons.items():
            self._draw_touch_button(rect, scroll_labels[name])

    def _touch_label(self, key, shortcut):
        """The button's name, with its keyboard shortcut on desktop.

        These buttons were designed for a phone, where a key would be
        meaningless. On a monitor they are small and sit in the corner,
        and nothing anywhere told you that G drinks a potion - so the
        answer to "where is the heal button" was that it was there all
        along and looked like decoration.
        """
        label = self.t(key)
        return label if ON_ANDROID else f"{label} ({shortcut})"

    def _run_summary_lines(self):
        """The run in five lines: who you were, how you fought, what you had.

        Read off the live player rather than from a separate tally kept
        during the run - there is nothing here that is not already state,
        and a parallel counter would only be one more thing to forget to
        update.
        """
        p = self.player
        klass = self._class()
        diff = self._diff()
        weapon = f"{self.tn(p.weapon_name)} +{p.weapon_bonus}"
        if p.weapon_element_id:
            weapon += f" ({self.te(p.weapon_element_id)})"
        return [
            self.t("gameover_hero", hero=self._class_name(klass),
                   difficulty=self._difficulty_name(diff)),
            self.t("gameover_gear", weapon=weapon,
                   armor=f"{self.tn(p.armor_name)} +{p.armor_bonus}"),
            self.t("gameover_combat", power=p.power, defense=p.defense,
                   crit=int(round(p.crit_chance * 100))),
            self.t("gameover_carried", gold=p.gold, potions=p.potions,
                   scrolls=sum(p.scrolls.values())),
            self.t("gameover_drunk", potions=p.potions_drunk_this_run),
        ]

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

        # What the run was actually made of, not just how far it got. A
        # death screen that only says "floor 7" throws away everything the
        # player just spent twenty minutes accumulating.
        detail = self._run_summary_lines()

        title = self.f_title.render(self.t("gameover_title"), True, C.COLOR_DANGER)
        total = (title.get_height() + self.gap_l + len(lines) * self.pitch_body
                 + self.gap_m + len(detail) * self.pitch_sm
                 + self.gap_xl + self.btn_h_hero)
        y = max(self.pad, (C.SCREEN_HEIGHT - total) // 2)

        self.screen.blit(title, title.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
        y += title.get_height() + self.gap_l
        for line in lines:
            color = (255, 215, 0) if line == best_line else C.COLOR_HUD_TEXT
            surf = self.f_body.render(line, True, color)
            self.screen.blit(surf, surf.get_rect(midtop=(C.SCREEN_WIDTH // 2, y)))
            y += self.pitch_body
        y += self.gap_m
        y = self._lines_block(detail, y, font=self.f_sm, pitch=self.pitch_sm,
                              color=C.COLOR_TEXT_DIM)
        y += self.gap_xl

        self._button_row([
            (self.t("btn_restart"), pygame.K_r),
            (self.t("btn_stats"), pygame.K_s),
            (self.t("btn_quit"), pygame.K_ESCAPE),
        ], y, height=self.btn_h_hero, primary_first=True)
