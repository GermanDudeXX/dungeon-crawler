# WIP-NOTIZEN — "füge alles was fehlt noch ein"

**Zweck:** Arbeitsstand über Session-Abbrüche hinweg. Beim Wiedereinstieg ZUERST
diese Datei lesen, dann `git log --oneline | head -5` und `git status`.

**Auftrag (2026-07-27):** Der Nutzer will *alle* offenen Punkte aus der
"Ideen-Sammlung" umgesetzt haben. Zusätzlich: die beiden neuen Asset-Packs im
Downloads-Ordner nutzen, **insbesondere echte Map-Tiles**.

---

## ASSETS (wichtig!)

Zwei CC0-Packs, liegen als ZIP in `~/Downloads`, entpackt nach
`~/Downloads/_peek/` (Peek-Ordner ist Wegwerf, nicht im Repo):

### 1. `0x72_DungeonTilesetII_v1.7.zip` → `_peek/0x72/0x72_DungeonTilesetII_v1.7/`
16×16 Pixel, CC0. **Das Hauptpack.** Enthält `frames/` mit ~200 Einzel-PNGs:

| Kategorie | Dateien | Wofür |
|---|---|---|
| Boden | `floor_1..floor_8`, `floor_ladder`, `floor_stairs`, `floor_spikes_anim` | **Map-Tiles**, Leitern, Stachelfallen |
| Wände | `wall_mid`, `wall_top_mid`, `wall_left/right`, `wall_top_left/right`, `wall_edge_*` (12 Varianten), `wall_outer_*`, `wall_side_*` | **Autotiling-Wände** |
| Deko | `column`, `column_wall`, `crate`, `skull`, `wall_banner_{blue,green,red,yellow}`, `wall_fountain_*`, `wall_goo`, `wall_hole_1/2` | Raumdeko, Themen-Akzente |
| **Türen** | `doors_leaf_closed`, `doors_leaf_open`, `doors_frame_left/right/top` | **Boss-Tür-Lock, Arena-Räume** |
| **Truhen** | `chest_full_open_anim_f0..f2`, `chest_empty_open_anim`, `chest_mimic_open_anim` | **Schatzräume + Mimic-Gegner** |
| Loch | `hole` | **Einstürzender Boden** |
| Schalter | `lever_left/right`, `button_red/blue_up/down` | Arena-Trigger |
| **Tränke** | `flask_{red,green,blue,yellow}`, `flask_big_{red,green,blue,yellow}` | **8 Trankfarben → Trank-Vielfalt** |
| Gold | `coin_anim_f0..f3` | animiertes Gold |
| Waffen | 28× `weapon_*` (rusty/regular/knight/golden/lavish/red_gem sword, katana, axe, waraxe, double_axe, hammer, big_hammer, mace, spear, bow, arrow, knife, cleaver, machete, saw_sword, baton_with_spikes, green/red_magic_staff, …) | **Waffen-Tiers + Set-Items + Klassen** |
| UI | `ui_heart_full/half/empty` | HP-Anzeige |
| **Spielbar** | `knight_m/f`, `elf_m/f`, `wizzard_m/f`, `lizard_m/f`, `dwarf_m/f` — je `idle_anim_f0..3`, `run_anim_f0..3`, `hit_anim_f0` | **Klassen-System (Krieger/Schurke/Magier)** |
| **Monster** | `goblin`, `skelet`, `orc_warrior`, `orc_shaman`, `masked_orc`, `ogre`, `big_demon`, `big_zombie`, `zombie`, `tiny_zombie`, `ice_zombie`, `imp`, `chort`, `wogol`, `muddy`, `swampy`, `slug`, `tiny_slug`, `necromancer`, `pumpkin_dude`, `angel`, `doc` — je idle+run, 4 Frames | **Gegner-Vielfalt, Mini-Bosse, Superboss** |

Zusätzlich fertige Atlanten: `atlas_floor-16x16.png` (112×112),
`atlas_walls_low-16x16.png` (192×64), `atlas_walls_high-16x32.png` (384×128),
`0x72_DungeonTilesetII_v1.7.png` (512×512, Gesamtatlas).

### 2. `free_cc0_top_down_tileset_template_pixel_art_by_rgsdev.zip` → `_peek/rgs/`
`Tilesets/tileset_{blue,brown,gray,green,purple}.png`, je **256×80** (16×5 Tiles à 16px)
plus `tileset_full.png` (256×400 = alle 5 untereinander).
→ **Fünf Farbvarianten = exakt unsere fünf Dungeon-Themen**
(Krypta=gray, Höhlen=brown, Eisenverlies=blue, Flammenreich=purple?, Frostgruft=blue/green).
Lizenz: `License.txt` im Ordner (CC0).

### Asset-Plan
- Nach `assets/tiles/` kopieren, **nur die benutzten Frames**, nicht alle 771 Dateien
  (APK-Größe!). Aktuell ist die APK schon ~13 MB nur durch Musik.
- Tiles zur Laufzeit auf `C.TILE_SIZE` skalieren (**`pygame.transform.scale`, NICHT
  `smoothscale`** — Pixelart muss hart bleiben) und **einmal** in den Map-Cache
  (`_rebuild_map_cache`) blitten. Der Cache existiert schon und ist der Grund,
  warum das Spiel auf dem Handy flüssig läuft — Tiles dürfen NIEMALS pro Frame
  einzeln gezeichnet werden.
- Wand-Autotiling: Nachbarschaftsmaske (oben/unten/links/rechts) → passendes
  `wall_*`-Frame. Fallback auf die jetzige Farbfläche, wenn ein Frame fehlt.
- Themenfarbe: pro Tier ein leichter Tint über die Boden-Tiles
  (`surface.fill(color, special_flags=BLEND_MULT)`) — spart 5× Tilesets.

---

## FORTSCHRITT

### Ausgangslage (Audit vom 27.07.)
Von der Ideen-Liste waren **12 Punkte drin, 7 halb, 25+ offen**, Tränke 1 von 30.

### Wellen-Plan
| # | Welle | Status |
|---|---|---|
| 1 | Gegner-Nameplates+Status-Icons, Bluten, Frost-Slow, Schwierigkeitsgrade | **IN ARBEIT** |
| 2 | **Map-Tiles + Autotiling + Themen** (vorgezogen, s. Assets) | offen |
| 3 | Tränke (1 → ~30), Trank-Inventar-UI | offen |
| 4 | Räume: Mini-Boss/3, Boss-Tür-Lock, Schatzraum+Wächter, Arena, Superboss, Lava/Loch | offen |
| 5 | Gegner: Schwarm, Fallen-Steller, Fernkampf-Kiting, Boss-Phasen sichtbar, Mimic | offen |
| 6 | Klassen, Skilltree, Begleiter, Set-Items | offen |
| 7 | Schmied, Glücksspiel, Item-Lore, Quests, Speicherslots, Endlos, Tod-Statistik | offen |
| 8 | Juice: Partikel, Hitstop, Zoom, Fanfare, Ambient, NPC-Dialoge | offen |

### Welle 1 — was schon im Code steht (NICHT committet!)
**`constants.py`** — fertig:
- `BLEED_DAMAGE_PER_TURN=5`, `BLEED_TURNS=2`, `SLOW_TURNS=3`
- `STATUS_BADGES` (6 Einträge: burn/poison/bleed/stun/slow/weaken, je char+color)
- `DIFFICULTIES` (easy/normal/hard/hardcore) + `DIFFICULTY_BY_ID` + `DEFAULT_DIFFICULTY`

**`entities.py`** — fertig:
- `Player(x, y, hp_mult=1.0)` — max_hp = 20*hp_mult
- `Player.bleed_turns`
- `Monster(..., level=1, diff_hp=1.0, diff_damage=1.0)`, `Monster.level`
- `Monster.bleed_turns`, `.slow_turns`, `.slow_skip`

**`game.py`** — teilweise:
- `_diff()`, `_difficulty_name()`, `_make_monster()` (zentrale Fabrik) ✔
- `start_new_run(difficulty=None)` ✔, `continue_run` lädt difficulty ✔
- `_build_save_data` speichert difficulty + bleed_turns ✔
- `_serialize/_deserialize_monster`: speichert jetzt max_hp/power/defense/
  xp_reward/tier_mult/level ✔ **(behebt echten Bug: beim Laden/Zurückkehren
  verloren Monster ihre Tier-Skalierung und hp konnte > max_hp sein)**

### Welle 1 — NOCH ZU TUN
1. Alle `entities.Monster(` Aufrufe in game.py auf `self._make_monster(` umstellen
   (Stellen: `_populate_level` ×2, `_spawn_shrine_ambush`, `_spawn_slime_children`,
   `_boss_summon_skeleton`). Achtung: `_spawn_slime_children` überschreibt Stats
   danach eh selbst.
2. `_attack`: Spieler-Schadensmultiplikator (`_diff()["player_damage"]`),
   **Bluten bei Krit**, **Frost setzt zusätzlich `slow_turns`**.
3. `_tick_monster_status`: bleed-Tick + slow-Tick.
4. `_tick_poison` → in `_tick_status_player` umbauen: Gift **und** Bluten.
5. `_enemy_turn`: `slow_skip` auswerten (nur jede 2. Runde handeln).
6. **`_render_nameplates()`** — neu, nach `_render_entities` aufrufen:
   pro sichtbarem Monster HP-Balken + `Name Lv{n}` + Status-Badges.
   **Perf:** Namens-Surfaces in `self._name_cache` (dict) cachen, kleine Font
   `self.f_tiny` aus `_build_ui_metrics`.
7. Schwierigkeitsauswahl: neuer State `difficulty_select`, aus dem Titel bei
   NEUER LAUF; `_render_difficulty_select()`; Tasten 1–4.
8. Shop-Aufschlag: `shop_markup_per_level` in `_buy_item` + `_render_shop`.
9. `persistence.py`: `"difficulty": "normal"` in `DEFAULT_SETTINGS`.
10. `locale_text.py`: `DIFFICULTY_DE`, `difficulty_title`, `difficulty_hint`,
    `hud_bleeding`, `log_bleed_damage`, `log_status_bleed`, `log_status_slow`,
    Statuszeile im Tutorial.

### Test/Release-Ritual (bei JEDEM Abschluss)
```
cd C:/Users/budzm/dungeon-crawler
for t in test_music test_ssl test_installer test_tiers test_levelup \
         test_menu_layout test_run_loop test_map_cache test_depth_systems \
         test_up_stairs test_loop_timing; do
  python "$SCRATCH/$t.py" || echo "FAIL $t"
done
```
`$SCRATCH` = `C:/Users/budzm/AppData/Local/Temp/claude/C--Users-budzm/7dc4ccb0-bb29-44b6-8bcd-aa48375c8eb2/scratchpad`

Danach: `assets/build_version.txt` hochzählen, commit, push, Android-CI abwarten,
PC-exe bauen + hochladen, `CHANGELOG.md` ergänzen (deutsch, spielerlesbar).
Aktuell: **PC Build 63 · Android Build 58**.

### Umgangsregeln mit dem Nutzer
- Deutsch, kein Quellcode, keine technischen Erklärungen — nur kurzes Wiki/Changelog.
- Updates zieht er selbst über den In-Game-Update-Knopf.
- Handy hängt per adb dran (`MSYS_NO_PATHCONV=1` für Gerätepfade;
  `adb shell input keyevent KEYCODE_WAKEUP` vor dem Installieren).
