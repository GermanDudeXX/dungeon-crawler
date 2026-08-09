# Localization data: UI strings, dynamic-name translations, and grammar helpers
# for the English/German language toggle in Settings.

STRINGS = {
    # --- title screen ---
    "title_move_line": {
        "en": "Move: WASD / Arrows / D-pad      Fight: walk into enemy      Shop: walk into merchant",
        "de": "Bewegen: WASD / Pfeiltasten / D-Pad      Kampf: in Gegner laufen      Shop: in Händler laufen",
    },
    "title_new_line": {
        "en": "New: gold, scrolls, traps, elites, poison, crits - see the Tutorial for details",
        "de": "Neu: Gold, Schriftrollen, Fallen, Elite-Gegner, Gift, Krit. Treffer - siehe Tutorial",
    },
    "title_deepest_stats": {
        "en": "Deepest level: {level}      Most kills in a run: {kills}",
        "de": "Tiefste Ebene: {level}      Meiste Kills in einem Lauf: {kills}",
    },
    "title_saved_line": {
        "en": "Dungeon Lv {level}, Character Lv {clevel} saved",
        "de": "Dungeon-Ebene {level}, Charakterlevel {clevel} gespeichert",
    },
    "btn_continue": {"en": "CONTINUE", "de": "FORTSETZEN"},
    "btn_new_run": {"en": "NEW RUN", "de": "NEUER LAUF"},
    "btn_start": {"en": "START", "de": "START"},
    "btn_tutorial": {"en": "TUTORIAL", "de": "TUTORIAL"},
    "btn_stats": {"en": "STATS", "de": "STATISTIK"},
    "btn_achievements": {"en": "ACHIEVEMENTS", "de": "ERFOLGE"},
    "btn_settings": {"en": "SETTINGS", "de": "EINSTELLUNGEN"},
    "btn_bestiary": {"en": "BESTIARY", "de": "BESTIARIUM"},
    "btn_back": {"en": "BACK", "de": "ZURÜCK"},
    "btn_prev": {"en": "< PREV", "de": "< ZURÜCK"},
    "btn_next": {"en": "NEXT >", "de": "WEITER >"},

    # --- bestiary screen ---
    "bestiary_title": {"en": "BESTIARY", "de": "BESTIARIUM"},
    "bestiary_stats": {"en": "HP {hp}  PWR {power}  DEF {defense}", "de": "HP {hp}  ANG {power}  VER {defense}"},
    "bestiary_undiscovered": {"en": "not yet discovered", "de": "noch nicht entdeckt"},
    "tag_ranged": {"en": "ranged", "de": "Fernkampf"},
    "tag_splits": {"en": "splits", "de": "teilt sich"},
    "tag_fast": {"en": "fast", "de": "schnell"},
    "tag_poison": {"en": "poisons", "de": "vergiftet"},

    # --- stats screen ---
    "stats_title": {"en": "STATISTICS", "de": "STATISTIK"},
    "stats_runs_deaths": {"en": "Runs played: {games}      Deaths: {deaths}", "de": "Läufe gespielt: {games}      Tode: {deaths}"},
    "stats_deepest": {"en": "Deepest level reached: {level}", "de": "Tiefste erreichte Ebene: {level}"},
    "stats_most_kills": {"en": "Most kills in a single run: {kills}", "de": "Meiste Kills in einem einzigen Lauf: {kills}"},
    "stats_highest_level": {"en": "Highest character level: {level}", "de": "Höchstes Charakterlevel: {level}"},
    "stats_potions": {"en": "Potions drunk: {n}", "de": "Getrunkene Tränke: {n}"},
    "stats_total_kills": {"en": "Total kills: {n}", "de": "Kills insgesamt: {n}"},
    "stats_kill_breakdown": {
        "en": "Rats: {rats}   Goblins: {goblins}   Orcs: {orcs}   Bosses: {bosses}",
        "de": "Ratten: {rats}   Goblins: {goblins}   Orks: {orcs}   Bosse: {bosses}",
    },
    "stats_footer": {
        "en": "Press any key or tap BACK to go back",
        "de": "Drücke eine Taste oder tippe auf ZURÜCK",
    },

    # --- achievements screen ---
    "achievements_title": {"en": "ACHIEVEMENTS", "de": "ERFOLGE"},
    "achievements_footer": {
        "en": "Press any key or tap to go back",
        "de": "Drücke eine Taste oder tippe, um zurückzugehen",
    },

    # --- tutorial screen ---
    "tutorial_title": {"en": "HOW TO PLAY", "de": "SO WIRD GESPIELT"},
    "tutorial_footer": {
        "en": "Press any key or tap to go back",
        "de": "Drücke eine Taste oder tippe, um zurückzugehen",
    },

    # --- pause menu ---
    "pause_title": {"en": "PAUSED", "de": "PAUSIERT"},
    "btn_resume": {"en": "RESUME", "de": "FORTSETZEN"},
    "btn_save_quit": {"en": "SAVE & QUIT", "de": "SPEICHERN & BEENDEN"},

    # --- shop screen ---
    "shop_title": {"en": "MERCHANT", "de": "HÄNDLER"},
    "shop_gold_label": {"en": "Your gold: {gold}", "de": "Dein Gold: {gold}"},
    "gold_word": {"en": "gold", "de": "Gold"},
    "btn_buy": {"en": "BUY", "de": "KAUFEN"},
    "btn_leave": {"en": "LEAVE", "de": "VERLASSEN"},

    # --- level-up perk choice ---
    "levelup_title": {"en": "LEVEL UP! Choose a bonus", "de": "LEVEL AUF! Wähle einen Bonus"},
    "levelup_hint": {"en": "Press 1 or 2, or tap CHOOSE", "de": "Drücke 1 oder 2, oder tippe WÄHLEN"},
    "btn_choose": {"en": "CHOOSE", "de": "WÄHLEN"},

    # --- settings screen ---
    "settings_title": {"en": "SETTINGS", "de": "EINSTELLUNGEN"},
    "settings_touch_label": {"en": "On-screen touch buttons: {state}", "de": "Bildschirm-Tasten: {state}"},
    "settings_lang_label": {"en": "Language: {state}", "de": "Sprache: {state}"},
    "settings_volume_label": {"en": "Sound volume: {state}", "de": "Lautstärke: {state}"},
    "settings_music_label": {"en": "Music: {state}", "de": "Musik: {state}"},
    "settings_zoom_label": {"en": "Zoom: {state}", "de": "Zoom: {state}"},
    "settings_shortcut_label": {"en": "Desktop shortcut", "de": "Desktop-Verknüpfung"},
    "settings_shortcut_ok": {"en": "Desktop shortcut: created", "de": "Desktop-Verknüpfung: erstellt"},
    "settings_shortcut_fail": {"en": "Desktop shortcut: failed", "de": "Desktop-Verknüpfung: fehlgeschlagen"},
    "btn_create": {"en": "CREATE", "de": "ERSTELLEN"},
    "settings_hint": {
        "en": "Tap TOGGLE or press C (controls) / L (language) / V (volume) / Z (zoom)      ESC: back",
        "de": "Tippe UMSCHALTEN oder drücke C (Tasten) / L (Sprache) / V (Lautstärke) / Z (Zoom)      ESC: zurück",
    },
    "btn_toggle": {"en": "TOGGLE", "de": "UMSCHALTEN"},
    "on": {"en": "ON", "de": "AN"},
    "off": {"en": "OFF", "de": "AUS"},
    "lang_en": {"en": "English", "de": "English"},
    "lang_de": {"en": "Deutsch", "de": "Deutsch"},

    # --- disable-touch-controls warning (Android only) ---
    "touch_warn_title": {"en": "WAIT!", "de": "WARTE!"},
    "touch_warn_line1": {
        "en": "Turning off on-screen controls removes your only way to move and act on a touchscreen.",
        "de": "Bildschirm-Tasten auszuschalten entfernt deine einzige Möglichkeit, dich auf dem Touchscreen zu bewegen.",
    },
    "touch_warn_line2": {
        "en": "Only the MENU button still works - turn it back on there if you change your mind.",
        "de": "Nur der MENÜ-Button funktioniert dann noch - dort kannst du es wieder einschalten.",
    },
    "btn_cancel": {"en": "CANCEL", "de": "ABBRECHEN"},
    "btn_confirm": {"en": "TURN OFF", "de": "AUSSCHALTEN"},

    # --- update screen ---
    "settings_update_label": {"en": "Version: Build {build}", "de": "Version: Build {build}"},
    "btn_check_update": {"en": "CHECK FOR UPDATES", "de": "NACH UPDATES SUCHEN"},
    "update_title": {"en": "UPDATE", "de": "UPDATE"},
    "update_checking": {"en": "Checking for updates...", "de": "Suche nach Updates..."},
    "update_error_prefix": {"en": "Error: {error}", "de": "Fehler: {error}"},
    "update_swap_failed": {
        "en": "The last update could not be installed ({reason}). The previous version was kept. Please try again.",
        "de": "Das letzte Update konnte nicht installiert werden ({reason}). Die vorherige Version wurde behalten. Bitte versuche es erneut.",
    },
    "update_up_to_date": {
        "en": "You already have the latest version (Build {build}).",
        "de": "Du hast bereits die neueste Version (Build {build}).",
    },
    "update_available": {
        "en": "Update available: Build {build} ({size} MB)",
        "de": "Update verfügbar: Build {build} ({size} MB)",
    },
    "btn_download_install": {"en": "DOWNLOAD & INSTALL", "de": "HERUNTERLADEN & INSTALLIEREN"},
    "update_downloading": {"en": "Downloading... {percent}%", "de": "Lade herunter... {percent}%"},
    "update_restarting": {"en": "Installing update, restarting...", "de": "Update wird installiert, Neustart..."},
    "update_needs_permission": {
        "en": "Please allow 'install unknown apps' for this app in the Settings screen that just opened, then tap Retry.",
        "de": "Bitte erlaube 'Unbekannte Apps installieren' für diese App in den geöffneten Einstellungen und tippe dann auf Wiederholen.",
    },
    "update_launched": {
        "en": "Installer opened - confirm the install, the app will restart.",
        "de": "Installer geöffnet - bestätige die Installation, die App startet danach neu.",
    },
    # --- first-run installer (Windows) ---
    "install_title": {"en": "INSTALL", "de": "INSTALLIEREN"},
    "install_line1": {
        "en": "Install Dungeon Crawler so it can update itself and get a Start-menu entry?",
        "de": "Dungeon Crawler installieren, damit es sich selbst aktualisieren kann und im Startmenü liegt?",
    },
    "install_line2": {
        "en": "Windows blocks updates for programs run straight from Downloads or the Desktop.",
        "de": "Windows blockiert Updates für Programme, die direkt aus Downloads oder vom Desktop laufen.",
    },
    "install_target": {"en": "Install to: {path}", "de": "Installieren nach: {path}"},
    "btn_install": {"en": "INSTALL", "de": "INSTALLIEREN"},
    "btn_play_here": {"en": "JUST PLAY", "de": "NUR SPIELEN"},
    "install_working": {"en": "Installing...", "de": "Installiere..."},
    "install_done": {
        "en": "Installed. Starting the installed copy - you can delete this file.",
        "de": "Installiert. Die installierte Version wird gestartet - diese Datei kannst du löschen.",
    },
    "install_failed": {"en": "Install failed: {error}", "de": "Installation fehlgeschlagen: {error}"},

    "update_no_permission": {
        "en": ("Windows will not let the game write to {folder}, so the update cannot "
               "replace it there. This is Controlled Folder Access (ransomware "
               "protection) and running as Administrator does not help. Move "
               "DungeonCrawler.exe into a normal folder (for example C:/Games) and "
               "try again."),
        "de": ("Windows erlaubt dem Spiel nicht, in {folder} zu schreiben, deshalb kann "
               "das Update sich dort nicht ersetzen. Das ist der Überwachte "
               "Ordnerzugriff (Ransomware-Schutz) - Administratorrechte helfen dabei "
               "nicht. Verschiebe DungeonCrawler.exe in einen normalen Ordner "
               "(z.B. C:/Spiele) und versuche es erneut."),
    },
    "update_dev_mode": {
        "en": "Self-update only works in the built app, not when running from source.",
        "de": "Selbst-Update funktioniert nur in der gebauten App, nicht im Quellcode-Modus.",
    },
    "btn_retry": {"en": "RETRY", "de": "WIEDERHOLEN"},

    # --- HUD ---
    "hud_weapon": {"en": "Weapon:", "de": "Waffe:"},
    "hud_armor": {"en": "Armor:", "de": "Rüstung:"},
    "hud_potions": {"en": "Potions:", "de": "Tränke:"},
    "hud_gold": {"en": "Gold:", "de": "Gold:"},
    "hud_kills": {"en": "Kills:", "de": "Kills:"},
    "hud_scrolls_label": {"en": "Scrolls -", "de": "Schriftrollen -"},
    "hud_menu_hint": {"en": "ESC: Menu", "de": "ESC: Menü"},
    "hud_poisoned": {"en": "POISONED", "de": "VERGIFTET"},

    # --- game over ---
    "gameover_title": {"en": "YOU DIED", "de": "DU BIST GESTORBEN"},
    "gameover_summary": {
        "en": "Reached dungeon level {level}   -   {kills} kills   -   Character level {clevel}",
        "de": "Ebene {level} erreicht   -   {kills} Kills   -   Charakterlevel {clevel}",
    },
    "gameover_best": {"en": "NEW BEST RUN!", "de": "NEUER BESTLAUF!"},
    "btn_restart": {"en": "RESTART", "de": "NEUSTART"},
    "btn_quit": {"en": "QUIT", "de": "BEENDEN"},

    # --- touch controls ---
    "touch_heal": {"en": "HEAL", "de": "HEILEN"},
    "touch_menu": {"en": "MENU", "de": "MENÜ"},

    # --- boss ---
    "boss_appears": {"en": "BOSS APPEARS", "de": "BOSS ERSCHEINT"},

    # --- log messages ---
    "log_descend_dungeon": {"en": "You descend into the dungeon.", "de": "Du steigst in den Dungeon hinab."},
    "log_continue_descent": {"en": "You continue your descent.", "de": "Du setzt deinen Abstieg fort."},
    "log_boss_guards": {"en": "A powerful presence guards the stairs...", "de": "Eine mächtige Präsenz bewacht die Treppe..."},
    "log_poison_damage": {"en": "Poison deals {dmg} damage.", "de": "Gift verursacht {dmg} Schaden."},
    "log_succumb_poison": {"en": "You succumb to the poison.", "de": "Du erliegst dem Gift."},
    "log_bleed_damage": {"en": "You bleed for {dmg} damage.", "de": "Du blutest und verlierst {dmg} Leben."},
    "log_succumb_bleed": {"en": "You bleed out.", "de": "Du verblutest."},
    "log_trap_damage": {"en": "You trigger a {trap}! -{dmg} HP.", "de": "Du löst eine {trap} aus! -{dmg} HP."},
    "log_trap_finish": {"en": "The trap finishes you off.", "de": "Die Falle tötet dich."},
    "log_trap_poison": {"en": "You trigger a {trap}! You are poisoned.", "de": "Du löst eine {trap} aus! Du bist vergiftet."},
    "log_trap_alarm": {"en": "You trigger a {trap}! Monsters awaken!", "de": "Du löst eine {trap} aus! Monster erwachen!"},
    "log_descend_level": {"en": "You descend to level {level}.", "de": "Du steigst zu Ebene {level} hinab."},
    "log_new_tier": {"en": "You enter the {tier}. The dungeon grows deadlier.",
                     "de": "Du betrittst die {tier}. Der Dungeon wird tödlicher."},
    "log_ascend_level": {"en": "You climb back up to level {level}.", "de": "Du steigst zurück zu Ebene {level} hinauf."},
    "log_pickup_item": {"en": "You pick up a {item}.", "de": "Du erhältst: {item}."},
    "log_equip_weapon": {"en": "You equip the {item} (+{bonus} power).", "de": "Ausgerüstet: {item} (+{bonus} Angriff)."},
    "log_find_worse_weapon": {"en": "You find a {item}, but your {current} is better.", "de": "Gefunden: {item}, aber {current} ist besser."},
    "log_equip_armor": {"en": "You equip the {item} (+{bonus} defense).", "de": "Ausgerüstet: {item} (+{bonus} Verteidigung)."},
    "log_find_worse_armor": {"en": "You find a {item}, but your {current} is better.", "de": "Gefunden: {item}, aber {current} ist besser."},
    "log_pickup_gold": {"en": "You pick up {amount} gold.", "de": "Du erhältst {amount} Gold."},
    "log_no_potions": {"en": "You have no potions.", "de": "Du hast keine Tränke."},
    "log_full_health": {"en": "You are already at full health.", "de": "Du bist bereits bei voller Gesundheit."},
    "log_drink_potion": {"en": "You drink a potion and heal {healed} HP.", "de": "Du trinkst einen Trank und heilst {healed} HP."},
    "log_not_enough_gold": {"en": "Not enough gold.", "de": "Nicht genug Gold."},
    "log_bought_item": {"en": "Bought a {item}.", "de": "Gekauft: {item}."},
    "log_no_scroll": {"en": "You have no {scroll}.", "de": "Du hast keine {scroll}."},
    "log_no_target": {"en": "No enemy in sight to target.", "de": "Kein Gegner in Sicht."},
    "log_fireball_hit": {"en": "The scroll erupts in fire, hitting {count} enemies!", "de": "Die Schriftrolle entfacht Feuer und trifft {count} Gegner!"},
    "log_blink": {"en": "You blink to a new location!", "de": "Du teleportierst dich an einen neuen Ort!"},
    "log_reveal": {"en": "The level layout is revealed!", "de": "Der Ebenenplan wird aufgedeckt!"},
    "log_poison_bite": {"en": "The bite poisons you!", "de": "Der Biss vergiftet dich!"},
    "log_status_burn": {"en": "{monster} catches fire!", "de": "{monster} fängt Feuer!"},
    "log_status_weaken": {"en": "{monster} is chilled and weakened!", "de": "{monster} wird erstarrt und geschwächt!"},
    "log_status_stun": {"en": "{monster} is stunned!", "de": "{monster} wird betäubt!"},
    "log_status_poison": {"en": "{monster} is poisoned!", "de": "{monster} wird vergiftet!"},
    "log_status_bleed": {"en": "{monster} is bleeding!", "de": "{monster} blutet!"},
    "log_status_slow": {"en": "{monster} is slowed!", "de": "{monster} wird verlangsamt!"},
    "hud_bleeding": {"en": "Bleeding", "de": "Blutend"},
    # Floats above a monster's head, so it has to stay short in both
    # languages - "Lv" reads as a level marker in German too.
    "nameplate_level": {"en": "Lv {level}", "de": "St {level}"},
    # Floats over your own character with an arrow pointing down at it.
    "marker_you": {"en": "YOU", "de": "DU"},

    # --- special rooms and hazards ---
    "superboss_prefix": {"en": "Ancient", "de": "Uralter"},
    "mimic_prefix": {"en": "Mimic", "de": "Mimik"},
    "log_mimic": {
        "en": "The chest lunges - it was a {monster} all along!",
        "de": "Die Truhe schnappt zu - es war die ganze Zeit {monster}!",
    },
    "log_trap_set": {
        "en": "{monster} scurries back, leaving a trap behind.",
        "de": "{monster} weicht zurück und lässt eine Falle zurück.",
    },
    "log_mini_boss": {
        "en": "{monster} rules this floor.",
        "de": "{monster} herrscht über diese Ebene.",
    },
    "log_chest_guarded": {
        "en": "The chest will not open while its guardian lives.",
        "de": "Die Truhe öffnet sich nicht, solange ihr Wächter lebt.",
    },
    "log_chest_opened": {
        "en": "The chest springs open, spilling its contents!",
        "de": "Die Truhe springt auf und ihr Inhalt ergießt sich!",
    },
    "log_boss_door_locked": {
        "en": "The way down is barred. The boss holds the key.",
        "de": "Der Weg nach unten ist versperrt. Der Boss hält den Schlüssel.",
    },
    "log_hazard_lava": {
        "en": "Molten rock scorches you for {dmg}!",
        "de": "Glühendes Gestein verbrennt dich für {dmg}!",
    },
    "log_hazard_collapse": {
        "en": "The floor gives way! You fall, taking {dmg} damage.",
        "de": "Der Boden gibt nach! Du stürzt und nimmst {dmg} Schaden.",
    },
    "log_hazard_spikes": {
        "en": "Spikes tear into you for {dmg}!",
        "de": "Stacheln reißen dich für {dmg} auf!",
    },

    # --- potion bag ---
    "bag_title": {"en": "POTIONS", "de": "TRÄNKE"},
    "bag_empty": {"en": "You are not carrying any potions.", "de": "Du trägst keine Tränke bei dir."},
    "btn_drink": {"en": "DRINK", "de": "TRINKEN"},
    "btn_bag": {"en": "BAG", "de": "BEUTEL"},
    "potion_desc_heal": {"en": "Heals {amount} HP", "de": "Heilt {amount} HP"},
    "potion_desc_heal_full": {"en": "Heals fully", "de": "Heilt vollständig"},
    "potion_desc_max_hp": {"en": "+{amount} max HP, permanently", "de": "+{amount} Max-HP, dauerhaft"},
    "potion_desc_power": {"en": "+{amount} power, permanently", "de": "+{amount} Angriff, dauerhaft"},
    "potion_desc_defense": {"en": "+{amount} defence, permanently", "de": "+{amount} Verteidigung, dauerhaft"},
    "potion_desc_xp": {"en": "Grants experience", "de": "Gibt Erfahrung"},
    "potion_desc_buff": {"en": "{buff} for {turns} turns", "de": "{buff} für {turns} Runden"},
    "potion_desc_shield": {"en": "Absorbs {amount} damage", "de": "Absorbiert {amount} Schaden"},
    "potion_desc_cure": {"en": "Cures poison and bleeding", "de": "Heilt Gift und Blutungen"},
    "potion_desc_reveal": {"en": "Reveals the map", "de": "Zeigt die Karte"},
    "potion_desc_blink": {"en": "Teleports you", "de": "Teleportiert dich"},
    "potion_desc_gold": {"en": "Turns to gold", "de": "Verwandelt sich in Gold"},
    "potion_desc_burst": {"en": "{amount} damage all around you", "de": "{amount} Schaden im Umkreis"},
    "potion_desc_self_poison": {"en": "Poisons you - do not drink", "de": "Vergiftet dich - nicht trinken"},
    "potion_desc_unknown": {"en": "Unknown effect", "de": "Unbekannte Wirkung"},
    "log_potion_buff": {"en": "{buff} for {turns} turns.", "de": "{buff} für {turns} Runden."},
    "log_potion_curse": {"en": "It was cursed - {buff} for {turns} turns!", "de": "Er war verflucht - {buff} für {turns} Runden!"},
    "log_potion_max_hp": {"en": "You feel hardier. +{amount} max HP.", "de": "Du fühlst dich zäher. +{amount} Max-HP."},
    "log_potion_power": {"en": "You feel stronger. +{amount} power.", "de": "Du fühlst dich stärker. +{amount} Angriff."},
    "log_potion_defense": {"en": "Your skin hardens. +{amount} defence.", "de": "Deine Haut härtet aus. +{amount} Verteidigung."},
    "log_potion_xp": {"en": "Insight floods you. +{amount} XP.", "de": "Erkenntnis durchströmt dich. +{amount} XP."},
    "log_potion_shield": {"en": "A ward surrounds you, absorbing {amount} damage.", "de": "Ein Schutzschild umgibt dich und absorbiert {amount} Schaden."},
    "log_potion_cured": {"en": "The {item} washes the affliction away.", "de": "{item} spült das Leiden fort."},
    "log_potion_self_poison": {"en": "It was poison! You feel very unwell.", "de": "Es war Gift! Dir wird sehr übel."},
    "log_potion_reveal": {"en": "The layout of the floor becomes clear.", "de": "Der Grundriss der Ebene wird klar."},
    "log_potion_burst": {"en": "The flask shatters, catching {count} enemies!", "de": "Die Phiole zerspringt und trifft {count} Gegner!"},
    "log_buff_ended": {"en": "{buff} wears off.", "de": "{buff} lässt nach."},
    "log_shield_absorbed": {"en": "Your ward absorbs {amount} damage.", "de": "Dein Schutzschild absorbiert {amount} Schaden."},
    "hud_shield": {"en": "Ward", "de": "Schild"},

    # --- death summary ---
    "gameover_hero": {
        "en": "{hero}  ·  {difficulty}",
        "de": "{hero}  ·  {difficulty}",
    },
    "gameover_gear": {
        "en": "Wielding {weapon}, wearing {armor}",
        "de": "Bewaffnet mit {weapon}, gerüstet mit {armor}",
    },
    "gameover_combat": {
        "en": "Power {power}   Defence {defense}   Crit {crit}%",
        "de": "Angriff {power}   Verteidigung {defense}   Krit {crit}%",
    },
    "gameover_carried": {
        "en": "Carrying {gold} gold, {potions} potions, {scrolls} scrolls",
        "de": "Dabei: {gold} Gold, {potions} Tränke, {scrolls} Schriftrollen",
    },
    "gameover_drunk": {
        "en": "Potions drunk this run: {potions}",
        "de": "In diesem Lauf getrunkene Tränke: {potions}",
    },

    # --- blacksmith ---
    "smith_title": {"en": "BLACKSMITH", "de": "SCHMIED"},
    "smith_nothing": {
        "en": "Come back when you carry something worth working on.",
        "de": "Komm wieder, wenn du etwas dabei hast, das sich zu bearbeiten lohnt.",
    },
    "smith_weapon": {
        "en": "Sharpen {item} +{bonus}  ->  +{step} more",
        "de": "{item} +{bonus} schärfen  ->  +{step} mehr",
    },
    "smith_armor": {
        "en": "Reinforce {item} +{bonus}  ->  +{step} more",
        "de": "{item} +{bonus} verstärken  ->  +{step} mehr",
    },
    "smith_enchant": {
        "en": "Enchant your weapon with an element",
        "de": "Deine Waffe mit einem Element verzaubern",
    },
    "smith_reenchant": {
        "en": "Re-enchant your weapon (now {element})",
        "de": "Waffe neu verzaubern (jetzt {element})",
    },
    "smith_reforge": {
        "en": "Reforge your weapon (now {rarity})",
        "de": "Waffe neu schmieden (jetzt {rarity})",
    },
    "btn_forge": {"en": "FORGE", "de": "SCHMIEDEN"},
    "log_smith_weapon": {
        "en": "The smith sharpens your {item}. Now +{bonus}.",
        "de": "Der Schmied schärft dein/e {item}. Jetzt +{bonus}.",
    },
    "log_smith_armor": {
        "en": "The smith reinforces your {item}. Now +{bonus}.",
        "de": "Der Schmied verstärkt dein/e {item}. Jetzt +{bonus}.",
    },
    "log_smith_enchant": {
        "en": "Your weapon glows - it is now {element}.",
        "de": "Deine Waffe glüht auf - sie ist jetzt {element}.",
    },
    "log_smith_reforge": {
        "en": "Reforged to {rarity}. Your weapon is now +{bonus}.",
        "de": "Neu geschmiedet zu {rarity}. Deine Waffe ist jetzt +{bonus}.",
    },
    "log_smith_best_already": {
        "en": "The smith shakes his head - it cannot be bettered.",
        "de": "Der Schmied schüttelt den Kopf - besser geht es nicht.",
    },

    # --- test room ---
    "btn_testroom": {"en": "TEST ROOM", "de": "TESTRAUM"},
    "log_testroom": {
        "en": "Test room: one of everything the dungeon can hold.",
        "de": "Testraum: alles einmal, was der Dungeon hergibt.",
    },

    # --- test-room tools ---
    "tools_title": {"en": "TEST TOOLS", "de": "TEST-WERKZEUGE"},
    "btn_tools": {"en": "TOOLS", "de": "TOOLS"},
    "btn_use": {"en": "USE", "de": "AUSFÜHREN"},
    "tools_status": {
        "en": "Health {hp} / {max_hp}      Gold {gold}      Godmode: {god}      Enemies: {enemies}",
        "de": "Leben {hp} / {max_hp}      Gold {gold}      Godmode: {god}      Feinde: {enemies}",
    },
    "tool_gold_up": {"en": "Give {amount} gold", "de": "{amount} Gold geben"},
    "tool_gold_down": {"en": "Take {amount} gold", "de": "{amount} Gold abziehen"},
    "tool_hp_up": {"en": "Give {amount} health", "de": "{amount} Leben geben"},
    "tool_hp_down": {"en": "Take {amount} health", "de": "{amount} Leben abziehen"},
    "tool_hp_full": {"en": "Heal to full", "de": "Voll heilen"},
    "tool_godmode_on": {"en": "Turn godmode ON", "de": "Godmode EINschalten"},
    "tool_godmode_off": {"en": "Turn godmode OFF", "de": "Godmode AUSschalten"},
    "log_godmode_on": {
        "en": "Godmode on - nothing can hurt you.",
        "de": "Godmode an - nichts kann dir mehr schaden.",
    },
    "tool_enemies_off": {"en": "Turn enemies OFF", "de": "Feinde AUSschalten"},
    "tool_enemies_on": {"en": "Turn enemies ON", "de": "Feinde EINschalten"},
    "log_enemies_off": {
        "en": "Enemies off - the floor is yours.",
        "de": "Feinde aus - die Ebene gehört dir.",
    },
    "log_enemies_on": {
        "en": "Enemies back on.",
        "de": "Feinde wieder an.",
    },
    "log_godmode_off": {
        "en": "Godmode off - you are mortal again.",
        "de": "Godmode aus - du bist wieder sterblich.",
    },

    # --- character class ---
    "class_title": {"en": "CHOOSE YOUR HERO", "de": "WÄHLE DEINEN HELDEN"},
    "class_hint": {
        "en": "A different start, not different rules: same controls, different numbers and kit.",
        "de": "Ein anderer Start, keine anderen Regeln: gleiche Steuerung, andere Werte und Ausrüstung.",
    },
    "class_row_hp": {"en": "Health {value}", "de": "Leben {value}"},
    "class_row_power": {"en": "Power {value}", "de": "Angriff {value}"},
    "class_row_defense": {"en": "Defence {value}", "de": "Verteidigung {value}"},
    "class_row_crit": {"en": "Crit {value}", "de": "Krit {value}"},
    "class_row_elemental": {"en": "Elemental {value}", "de": "Elementar {value}"},
    "hud_class": {"en": "{name}", "de": "{name}"},

    # --- difficulty ---
    "difficulty_title": {"en": "DIFFICULTY", "de": "SCHWIERIGKEIT"},
    "difficulty_hint": {
        "en": "Chosen once per run. Affects your health and damage, the enemies', and prices.",
        "de": "Gilt für den ganzen Lauf: dein Leben und Schaden, das der Gegner, und die Preise.",
    },
    "difficulty_row_hp": {"en": "Your health {value}", "de": "Dein Leben {value}"},
    "difficulty_row_damage": {"en": "Your damage {value}", "de": "Dein Schaden {value}"},
    "difficulty_row_enemy_hp": {"en": "Enemy health {value}", "de": "Gegner-Leben {value}"},
    "difficulty_row_enemy_damage": {"en": "Enemy damage {value}", "de": "Gegner-Schaden {value}"},
    "difficulty_row_prices": {
        "en": "Prices +{percent}% per floor",
        "de": "Preise +{percent}% pro Ebene",
    },
    "log_boss_enrage": {"en": "{monster} flies into a rage!", "de": "{monster} gerät in Rage!"},
    "log_boss_summon": {"en": "{monster} summons a minion!", "de": "{monster} beschwört einen Diener!"},
    "log_boss_web": {"en": "{monster} spits venom at you from afar!", "de": "{monster} spuckt dich aus der Ferne mit Gift an!"},
    "log_shrine_vitality": {"en": "The shrine bathes you in light - fully healed!", "de": "Der Schrein hüllt dich in Licht - vollständig geheilt!"},
    "log_shrine_power": {"en": "The shrine empowers your muscles. +2 Power, permanently.", "de": "Der Schrein stärkt deine Muskeln. +2 Angriff, dauerhaft."},
    "log_shrine_fortune": {"en": "The shrine rains gold on you! +{amount} Gold.", "de": "Der Schrein lässt Gold auf dich regnen! +{amount} Gold."},
    "log_shrine_frailty": {"en": "The shrine curses you. -{amount} Max HP.", "de": "Der Schrein verflucht dich. -{amount} Max-HP."},
    "log_shrine_ambush": {"en": "The shrine was a trap - vengeful spirits attack!", "de": "Der Schrein war eine Falle - rachsüchtige Geister greifen an!"},
    "log_you_died": {"en": "You have died.", "de": "Du bist gestorben."},
    "log_monster_dies": {"en": "{monster} dies. (+{xp} XP)", "de": "{monster} stirbt. (+{xp} XP)"},
    "log_level_up": {"en": "You reach level {level}!", "de": "Du erreichst Level {level}!"},
    "log_achievement_unlocked": {"en": "Achievement unlocked: {name}!", "de": "Erfolg freigeschaltet: {name}!"},
    "log_perk_chosen": {"en": "You gain: {perk}.", "de": "Du erhältst: {perk}."},
}

# perk id -> (name_de, desc_de)
PERK_DE = {
    "power": ("Rohe Stärke", "+2 Angriff"),
    "defense": ("Eisenhaut", "+2 Verteidigung"),
    "vitality": ("Vitalität", "+10 Max-HP"),
    "precision": ("Präzision", "+5% Krit-Chance"),
    "toughness": ("Zähigkeit", "-10% erlittener Schaden"),
    "regeneration": ("Regeneration", "Regeneriere 1 HP alle 5 Runden"),
    "greed": ("Gier", "+25% Gold-Funde"),
    "elemental_focus": ("Elementarfokus", "+15% Elementar-Auslösechance"),
}

ELEMENT_DE = {
    "Fire": "Feuer",
    "Frost": "Frost",
    "Lightning": "Blitz",
    "Venom": "Gift",
}

# English display name -> German display name, for items/weapons/armor/scrolls.
NAME_DE = {
    "Dagger": "Dolch",
    "Short Sword": "Kurzschwert",
    "Long Sword": "Langschwert",
    "War Axe": "Kriegsaxt",
    "Leather Armor": "Lederrüstung",
    "Chainmail": "Kettenhemd",
    "Plate Armor": "Plattenrüstung",
    "Healing Potion": "Heiltrank",
    "Gold": "Gold",
    "Fists": "Fäuste",
    "None": "Keine",
    "Scroll of Fireball": "Feuerball-Rolle",
    "Scroll of Teleport": "Teleport-Rolle",
    "Scroll of Reveal": "Enthüllungs-Rolle",

    # potions (constants.POTION_TYPES)
    "Greater Healing Potion": "Großer Heiltrank",
    "Elixir of Life": "Lebenselixier",
    "Potion of Regeneration": "Trank der Regeneration",
    "Potion of Vitality": "Trank der Lebenskraft",
    "Potion of Might": "Trank der Macht",
    "Potion of Iron Hide": "Trank der Eisenhaut",
    "Potion of Insight": "Trank der Erkenntnis",
    "Potion of Strength": "Trank der Stärke",
    "Potion of Stone Skin": "Trank der Steinhaut",
    "Potion of Precision": "Trank der Präzision",
    "Potion of Haste": "Trank der Eile",
    "Berserker's Brew": "Berserker-Gebräu",
    "Potion of Thorns": "Trank der Dornen",
    "Vampiric Draught": "Vampirischer Trunk",
    "Potion of Embers": "Trank der Glut",
    "Potion of Warding": "Trank der Abwehr",
    "Potion of Invisibility": "Trank der Unsichtbarkeit",
    "Potion of Luck": "Trank des Glücks",
    "Potion of Clarity": "Trank der Klarheit",
    "Potion of Blinking": "Trank des Blinzelns",
    "Potion of Midas": "Trank des Midas",
    "Antidote": "Gegengift",
    "Coagulant": "Gerinnungsmittel",
    "Panacea": "Allheilmittel",
    "Flask of Fire": "Feuerphiole",
    "Flask of Frost": "Frostphiole",
    "Flask of Storms": "Sturmphiole",
    "Murky Flask": "Trübe Phiole",
    "Bitter Flask": "Bittere Phiole",
    "Brittle Flask": "Spröde Phiole",

    # buffs (constants.BUFFS)
    "Strength": "Stärke",
    "Stone Skin": "Steinhaut",
    "Precision": "Präzision",
    "Haste": "Eile",
    "Invisibility": "Unsichtbarkeit",
    "Thorns": "Dornen",
    "Life Leech": "Lebensraub",
    "Regeneration": "Regeneration",
    "Luck": "Glück",
    "Berserk": "Berserker",
    "Fire Aura": "Feueraura",
    "Clumsiness": "Ungeschick",
    "Frailty": "Gebrechlichkeit",

    # boss phases (constants.BOSS_PHASES)
    "Wounded": "Verwundet",
    "Desperate": "Verzweifelt",
}

MONSTER_NAME_DE = {
    "rat": "Ratte",
    "goblin": "Goblin",
    "orc": "Ork",
    "skeleton": "Skelett",
    "slime": "Schleim",
    "bat": "Fledermaus",
    "spider": "Spinne",
}

MONSTER_NAME_DE_PLURAL = {
    "rat": "Ratten",
    "goblin": "Goblins",
    "orc": "Orks",
    "boss": "Bosse",
}

MONSTER_GENDER_DE = {
    "rat": "f",
    "goblin": "m",
    "orc": "m",
    "skeleton": "n",
    "slime": "m",
    "bat": "f",
    "spider": "f",
}

ARTICLES_DE = {
    "m": {"nom": "der", "acc": "den"},
    "f": {"nom": "die", "acc": "die"},
    "n": {"nom": "das", "acc": "das"},
}

ADJ_ENDING_DE = {"m": "er", "f": "e", "n": "es"}

ELITE_NAME_DE = {
    "Fast": "Schnell",
    "Vicious": "Bösartig",
    "Armored": "Gepanzert",
    "Regenerating": "Regenerierend",
}

TIER_DE = {
    "crypt": "Krypta",
    "caverns": "Höhlen",
    "vault": "Eisenverlies",
    "inferno": "Flammenreich",
    "frost": "Frostgruft",
}

CLASS_DE = {
    "warrior": "Krieger",
    "rogue": "Schurke",
    "mage": "Magier",
}

CLASS_BLURB_DE = {
    "warrior": "Zäh und gepanzert. Verzeiht Fehler.",
    "rogue": "Zerbrechlich, schnell, trifft ständig kritisch.",
    "mage": "Schwach im Nahkampf, aber Rollen und Elemente gehorchen dir.",
}

DIFFICULTY_DE = {
    "easy": "Einfach",
    "normal": "Normal",
    "hard": "Schwer",
    "hardcore": "Hardcore",
}

RARITY_DE = {
    "Common": "Gewöhnlich",
    "Uncommon": "Ungewöhnlich",
    "Rare": "Selten",
    "Epic": "Episch",
    "Legendary": "Legendär",
}

BOSS_TITLE_DE = {
    "orc": "Häuptling",
    "skeleton": "König",
    "spider": "Königin",
    "slime": "Koloss",
}

BOSS_GENDER_DE = {
    "orc": "m",
    "skeleton": "m",
    "spider": "f",
    "slime": "m",
}

TRAP_NAME_DE = {
    "spike": "Stachelfalle",
    "poison": "Giftfalle",
    "alarm": "Alarmfalle",
}

# achievement id -> (name_de, desc_de)
ACHIEVEMENT_DE = {
    "first_blood": ("Erstes Blut", "Besiege deinen ersten Gegner."),
    "survivor": ("Überlebender", "Erreiche Charakterlevel 5."),
    "veteran": ("Veteran", "Erreiche Charakterlevel 10."),
    "deep_delver": ("Tiefengräber", "Erreiche Dungeon-Ebene 5."),
    "spelunker": ("Höhlenforscher", "Erreiche Dungeon-Ebene 10."),
    "boss_slayer": ("Bossjäger", "Besiege einen Boss."),
    "rich": ("Reich", "Trage 100 Gold gleichzeitig bei dir."),
    "hoarder": ("Hamsterer", "Sammle insgesamt 500 Gold."),
    "well_read": ("Belesen", "Benutze insgesamt 10 Schriftrollen."),
    "persistent": ("Hartnäckig", "Stirb 5 Mal."),
    "centurion": ("Zenturio", "Besiege insgesamt 100 Monster."),
    "untouchable": ("Unberührbar", "Erreiche Dungeon-Ebene 3, ohne einen Trank zu trinken."),
}

TUTORIAL_SECTIONS = {
    "en": [
        ("Movement & Combat", [
            "Move with WASD / Arrow keys / on-screen D-pad (hold to keep moving).",
            "Walk into a monster to attack it. Walk into the '>' stairs to descend.",
            "Your crit chance grows with level; a critical hit deals double damage.",
            "On level up, pick a permanent bonus: power, defense, vitality, or crit.",
        ]),
        ("Survival", [
            "G / HEAL button: drink a potion. Potions heal 15 HP.",
            "Poison (from spiders or poison traps) deals damage each turn until it wears off.",
            "ESC / MENU button: pause, save & quit, or check stats without dying.",
        ]),
        ("Monsters", [
            "r rat, g goblin, o orc, s skeleton (shoots from range), z slime (splits when killed),",
            "b bat (fast, moves twice), x spider (poisons on hit).",
            "Colour-tinted 'elite' monsters are tougher but drop much more XP.",
            "Every 5th dungeon level a boss guards the stairs - watch its health bar at the top.",
            "Discovered monsters are recorded in the Bestiary (title screen).",
        ]),
        ("Status Effects", [
            "Monsters show a health bar, their name and level, and icons for what is on them.",
            "F burning and G poisoned deal damage every turn; B bleeding does the most.",
            "Every critical hit you land causes bleeding.",
            "! stunned skips the monster's turn; S slowed makes it act only every other turn.",
            "W weakened cuts the monster's defence, so your hits land harder.",
            "Elemental weapons apply these: fire burns, poison poisons, frost slows and weakens,",
            "   lightning stuns.",
        ]),
        ("Heroes & Potions", [
            "At the start of a run you pick a difficulty, then a hero.",
            "Warrior: tough and armoured. Rogue: fragile but crits constantly.",
            "Mage: weak in melee, but starts with scrolls and enchants his hits.",
            "I / the BAG button opens your potions: thirty kinds, each with its own effect.",
            "G / HEAL drinks whichever one is selected - the HUD names it.",
            "Buffs last a number of turns and stack; the HUD counts them down.",
        ]),
        ("Rooms & Dangers", [
            "Every 3rd floor has a mini-boss; every 5th, a real boss whose stairs stay barred.",
            "Treasure chests are guarded - kill the guardian first. Some chests are mimics.",
            "A vault is a pile of loot with several elites standing on it. Fight it in a doorway.",
            "The blacksmith sharpens, reinforces, enchants and reforges what you already carry.",
            "Lava, collapsing floors and spike beds are visible: walk around them.",
            "Crates and columns are solid - you cannot pass them, and neither can arrows.",
            "Bosses change phase as they weaken - the bar above shows which one.",
        ]),
        ("Difficulty", [
            "Chosen at the start of every run - Easy, Normal, Hard or Hardcore.",
            "It scales your health and damage, the monsters' health and damage, and shop prices.",
            "Hard and Hardcore also make merchants charge more the deeper you go.",
            "XP is never scaled, so a harder run is genuinely harder, not just slower.",
        ]),
        ("Loot & Gold", [
            "$  gold - spend it with merchants (walk into the cyan 'M').",
            "/  weapons and [  armor auto-equip if they're an upgrade.",
            "?  scrolls: F = Fireball (damages nearby enemies), T = Teleport (random blink),",
            "   V = Reveal (shows the full level map).",
        ]),
        ("Hazards & Progress", [
            "Hidden traps trigger when stepped on: spikes, poison gas, or alarms that wake monsters.",
            "Save & Quit in the pause menu saves your run - resume it from the title screen.",
            "Lifetime Stats and Achievements are tracked across every run, even after you die.",
            "Settings (title / pause menu) let you hide touch buttons and switch language.",
        ]),
    ],
    "de": [
        ("Bewegung & Kampf", [
            "Bewege dich mit WASD / Pfeiltasten / D-Pad (gedrückt halten zum Weiterlaufen).",
            "Laufe in ein Monster, um es anzugreifen. Laufe auf die Treppe '>', um abzusteigen.",
            "Deine Krit-Chance wächst mit dem Level; ein Krit verursacht doppelten Schaden.",
            "Bei Levelaufstieg wählst du einen dauerhaften Bonus aus zwei Optionen.",
        ]),
        ("Überleben", [
            "G / HEILEN-Taste: trinke einen Trank. Tränke heilen 15 HP.",
            "Gift (von Spinnen oder Giftfallen) verursacht jede Runde Schaden, bis es abklingt.",
            "ESC / MENÜ-Taste: pausieren, speichern & beenden, oder Statistik ansehen ohne Tod.",
        ]),
        ("Monster", [
            "r Ratte, g Goblin, o Ork,",
            "s Skelett (schießt aus der Distanz), z Schleim (teilt sich beim Tod),",
            "b Fledermaus (schnell, zieht doppelt), x Spinne (vergiftet bei Treffer).",
            "Farblich markierte 'Elite'-Monster sind stärker, geben aber deutlich mehr XP.",
            "Alle 5 Dungeon-Ebenen bewacht ein Boss die Treppe - beachte seine Lebensleiste oben.",
            "Entdeckte Monster werden im Bestiarium gespeichert (Titelbildschirm).",
        ]),
        ("Statuseffekte", [
            "Monster zeigen eine Lebensleiste, Namen und Stufe, sowie Symbole für ihre Effekte.",
            "F Brennen und G Gift verursachen jede Runde Schaden; B Bluten am meisten.",
            "Jeder kritische Treffer von dir lässt den Gegner bluten.",
            "! Betäubt lässt die Runde des Monsters ausfallen;",
            "   S Verlangsamt lässt es nur jede zweite Runde handeln.",
            "W Geschwächt senkt die Verteidigung des Monsters, deine Treffer wirken stärker.",
            "Elementarwaffen lösen das aus: Feuer brennt, Gift vergiftet,",
            "   Frost verlangsamt und schwächt, Blitz betäubt.",
        ]),
        ("Helden & Tränke", [
            "Zu Beginn eines Laufs wählst du erst die Schwierigkeit, dann einen Helden.",
            "Krieger: zäh und gepanzert. Schurke: zerbrechlich, aber trifft ständig kritisch.",
            "Magier: schwach im Nahkampf, startet aber mit Rollen und verzaubert seine Treffer.",
            "I / BEUTEL öffnet deine Tränke: dreißig Sorten, jede mit eigener Wirkung.",
            "G / HEILEN trinkt den ausgewählten - das HUD nennt seinen Namen.",
            "Effekte halten eine Anzahl Runden und stapeln sich; das HUD zählt sie herunter.",
        ]),
        ("Räume & Gefahren", [
            "Jede 3. Ebene hat einen Mini-Boss; jede 5. einen Boss, dessen Treppe versperrt ist.",
            "Schatztruhen sind bewacht - töte erst den Wächter. Manche Truhen sind Mimiks.",
            "Eine Schatzkammer ist ein Beutehaufen mit mehreren Elite-Gegnern darauf.",
            "Der Schmied schärft, verstärkt, verzaubert und schmiedet neu, was du schon hast.",
            "Lava, einstürzende Böden und Stachelbetten sind sichtbar: geh drum herum.",
            "Kisten und Säulen sind fest - du kommst nicht durch, Pfeile aber auch nicht.",
            "Bosse wechseln die Phase, wenn sie schwächer werden - die Leiste oben zeigt welche.",
        ]),
        ("Schwierigkeit", [
            "Wird zu Beginn jedes Laufs gewählt - Einfach, Normal, Schwer oder Hardcore.",
            "Sie skaliert dein Leben und deinen Schaden, das der Monster, und die Ladenpreise.",
            "Bei Schwer und Hardcore verlangen Händler pro Ebene zusätzlich mehr.",
            "XP wird nie skaliert - ein schwerer Lauf ist wirklich schwerer, nicht nur länger.",
        ]),
        ("Beute & Gold", [
            "$  Gold - gib es bei Händlern aus (laufe in das cyanfarbene 'M').",
            "/  Waffen und [  Rüstung rüsten sich automatisch aus, wenn sie besser sind.",
            "?  Schriftrollen: F = Feuerball (Schaden an nahen Gegnern),",
            "   T = Teleport (zufälliger Sprung), V = Enthüllung (zeigt die Karte).",
        ]),
        ("Gefahren & Fortschritt", [
            "Versteckte Fallen lösen aus, wenn man draufsteht: Stacheln, Giftgas oder Alarme.",
            "Speichern & Beenden sichert deinen Lauf - setze ihn später vom Titelbildschirm fort.",
            "Lebenszeit-Statistik und Erfolge werden über jeden Lauf verfolgt, auch nach dem Tod.",
            "Einstellungen (Titel- / Pausenmenü): Touch-Tasten ausblenden, Sprache wechseln.",
        ]),
    ],
}
