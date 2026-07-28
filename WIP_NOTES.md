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
| 1 | Nameplates+Status-Icons, Bluten, Frost-Slow, Schwierigkeitsgrade | **FERTIG** `bbccad5` |
| 2 | Map-Tiles + Autotiling + Themen | **FERTIG** `4af1097` |
| 3 | Tränke 1→30 + Buffs + Trankbeutel + Händler-Sortiment | **FERTIG** `a6c9c3a` |
| 4 | Mini-Boss, Schatzraum, Boss-Tür, Bodengefahren, Superboss | **FERTIG** `65764c1` |
| 5 | Kiting, Schwarm, Fallensteller, Boss-Phasen, Mimik | **FERTIG** `84942fb` |
| 6 | Klassen (Krieger/Schurke/Magier) + eigene Spielfigur | **FERTIG** `facd9ad` |
| 7 | Tod-Statistik | **FERTIG** `a10a8de` — Rest offen (s.u.) |
| 8 | Partikel, Hitstop | **FERTIG** `a10a8de` — Rest offen (s.u.) |

### NOCH OFFEN aus der Ideen-Liste
Bewusst nicht gebaut, in dieser Reihenfolge sinnvoll:
1. **Schmied** — Waffe/Rüstung gegen Gold aufwerten (Gold-Senke fürs Spätspiel).
   Einfachster nächster Schritt: `_render_shop` als Vorlage, eigener State.
2. **Skilltree** — die Perk-Auswahl gibt es schon (`C.PERKS`,
   `_render_levelup_choice`); ein Baum wäre ein Screen darüber.
3. **Set-Items, Begleiter, Arena-Wellen, Glücksspiel, Item-Lore, Quests,
   Speicherslots, Ambient-Sounds, NPC-Dialoge.**
4. **Endlos-Modus** — faktisch schon da: Themen zyklen ab Ebene 51 mit „+1"
   weiter und die Werte steigen dauerhaft. Fehlt nur ein Menüeintrag.

### PRIORITÄT 1 — Update-Bug: **BEHOBEN** (`07f2660`)
Diagnose: Der Download war fehlerfrei (40.412.041 Bytes = exakt die GitHub-
Asset-Größe). Das Batch-Skript scheiterte am `move /y` (die laufende exe war
noch gesperrt), prüfte den Fehler nie und startete die **alte** exe neu, deren
`_MEI`-Entpackung dann fehlschlug. Zusätzlich ließ `os._exit(0)` pro Update
einen ~40-MB-`_MEI`-Ordner in %TEMP% zurück (38 Stück, 350 MB).
Fix: Umbenennen statt Überschreiben (geht auch bei offenem Handle), jeder
Schritt geprüft + 15 Wiederholungen + Rollback, Fehlermarker → Meldung im
Update-Screen, sauberer Exit statt `os._exit`, `_MEI`-Aufräumen beim Start.
Getestet mit `test_updater_swap.py` (echtes cmd.exe, echte Sperren).

### Wichtige Design-Entscheidungen (nicht versehentlich rückgängig machen)
- **Map-Cache**: Tiles NUR in `_rebuild_map_cache` blitten, nie pro Frame.
  Voll erkundet 5,2 ms, nur bei FOV-Wechsel. Frame bleibt bei 2,9 ms.
- `_wall_tile_name` gibt **None für massiven Fels** zurück → Flächenfüllung.
  Ohne das entsteht ein Streifenmuster über die ganze Karte.
- Gefahren-Kacheln: Kunst **zuerst**, Farbschleier **darüber** (die Frames
  sind deckend und übermalen einen Schleier darunter).
- **Buffs**: ein Dict `player.buffs = {id: runden}`, kein Feld pro Effekt.
- **Multiplikatoren** (Schwierigkeit, Klasse) werden beim Erzeugen in den
  HP-Pool eingerechnet, nie beim Lesen — sonst skaliert jedes spätere
  `+max_hp` mit.
- `_tile_is_free()` ist die **eine** Platzierungs-Prüfung. Neue Features
  müssen sie benutzen, nicht eine eigene Teilmenge prüfen.
- `_move_monster_toward` gibt **True/False** zurück; zwei Verhalten hängen
  daran.
- **TLS-Prüfung im Updater niemals abschalten** (lädt eine ausführbare Datei).

### Test/Release-Ritual (bei JEDEM Abschluss)
`$SCRATCH` = `C:/Users/budzm/AppData/Local/Temp/claude/C--Users-budzm/7dc4ccb0-bb29-44b6-8bcd-aa48375c8eb2/scratchpad`
```
for t in test_music test_ssl test_installer test_tiers test_levelup          test_menu_layout test_run_loop test_map_cache test_depth_systems          test_up_stairs test_loop_timing test_updater test_updater_swap          test_wave1 test_potions test_rooms test_enemies test_classes          test_juice; do
  python "$SCRATCH/$t.py" | tail -1
done
```
Alle 19 grün (Stand: `a10a8de`). Danach: `assets/build_version.txt`
hochzählen, PC-exe bauen, **erst der Nutzer testet am PC**, dann Push zu
GitHub + APK-Build.
Vorher veröffentlicht: **PC Build 63 · Android Build 58**.

### Umgangsregeln mit dem Nutzer
- Deutsch, kein Quellcode, keine technischen Erklärungen — nur kurzes Wiki/Changelog.
- Updates zieht er selbst über den In-Game-Update-Knopf.
- Handy hängt per adb dran (`MSYS_NO_PATHCONV=1` für Gerätepfade;
  `adb shell input keyevent KEYCODE_WAKEUP` vor dem Installieren).
