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
    "settings_hint": {
        "en": "Tap TOGGLE or press C (controls) / L (language) / V (volume)      ESC: back",
        "de": "Tippe UMSCHALTEN oder drücke C (Tasten) / L (Sprache) / V (Lautstärke)      ESC: zurück",
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
    "log_trap_damage": {"en": "You trigger a {trap}! -{dmg} HP.", "de": "Du löst eine {trap} aus! -{dmg} HP."},
    "log_trap_finish": {"en": "The trap finishes you off.", "de": "Die Falle tötet dich."},
    "log_trap_poison": {"en": "You trigger a {trap}! You are poisoned.", "de": "Du löst eine {trap} aus! Du bist vergiftet."},
    "log_trap_alarm": {"en": "You trigger a {trap}! Monsters awaken!", "de": "Du löst eine {trap} aus! Monster erwachen!"},
    "log_descend_level": {"en": "You descend to level {level}.", "de": "Du steigst zu Ebene {level} hinab."},
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
