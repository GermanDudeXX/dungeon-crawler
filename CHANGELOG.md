# Changelog

Alle nennenswerten Änderungen an Dungeon Crawler. Neueste zuerst.

Die Build-Nummern stehen im Spiel unter **Einstellungen → Version** und
zählen auf PC und Android getrennt hoch.

---

## Aktuell — PC Build 56 · Android Build 53

### Musik
- Drei Dungeon-Synth-Tracks, wechseln mit dem Dungeon-Thema
- Musik startet jetzt schon im Menü, nicht erst im ersten Dungeon
- **Behoben:** Musik lief erst, nachdem man sie in den Einstellungen aus- und
  wieder eingeschaltet hatte. Ein einzelner fehlgeschlagener Ladeversuch hatte
  jede weitere Wiederholung dauerhaft blockiert.
- Eine Überwachung startet die Musik neu, falls sie unerwartet abbricht
  (z.B. durch einen Anruf), statt still zu bleiben
- Lautstärke folgt jetzt der Einstellung, statt auf 60 % davon gedeckelt zu sein
- Ein/Aus-Schalter in den Einstellungen

### Dungeon-Stufen
- Alle **10 Ebenen** ein neues Thema: Krypta → Höhlen → Eisenverlies →
  Flammenreich → Frostgruft, jeweils mit eigenen Farben und eigenem Track
- Gegner werden pro Stufe stärker (Leben, Angriff, Verteidigung, Erfahrung)
- Die Schwierigkeit steigt **dauerhaft** — ×1,0 auf Ebene 1 bis ×23 auf
  Ebene 111. Ab Ebene 51 wiederholen sich die Themen als „+1", die Werte
  steigen aber weiter

### Installation & Updates (Windows)
- **Installations-Assistent**: Beim ersten Start bietet das Spiel an, sich nach
  `%LOCALAPPDATA%\Programs\DungeonCrawler` zu installieren, samt Startmenü- und
  Desktop-Verknüpfung
- **Behoben:** Updates schlugen mit einem Berechtigungsfehler fehl, wenn die
  .exe in Downloads oder auf dem Desktop lag — auch als Administrator. Ursache
  war Windows' Überwachter Ordnerzugriff, der unsignierte Programme dort
  blockiert. Downloads laufen jetzt über den Temp-Ordner
- Verständliche Fehlermeldung mit Ordnernamen, **bevor** 30 MB geladen werden
- Der Dateitausch versucht es mehrfach, falls ein Virenscanner kurz sperrt

### Behoben
- **Level-Up-Bonus ging verloren**: Aufsteigen, dann Speichern & Beenden, dann
  Laden — der Bonus war dauerhaft weg
- Absturz beim Start durch eine zu früh verwendete interne Variable

---

## Mobile-Überarbeitung — PC Build 53 · Android Build 50

### Geschwindigkeit
Das Spiel lief auf dem Testgerät mit **3,9 Bildern pro Sekunde**. Jetzt sind es
**28–53**.

- Die Karte wurde jedes Bild Kachel für Kachel neu gezeichnet — bei erkundeter
  Ebene bis zu 1000 Rechtecke pro Bild. Sie wird jetzt einmal gezeichnet und
  zwischengespeichert (**41× schneller**)
- Es wird nur noch neu gezeichnet, wenn sich wirklich etwas ändert. In einem
  rundenbasierten Spiel steht das Bild die meiste Zeit still
- Eingaben werden doppelt so oft abgefragt (60 statt 30 Mal pro Sekunde)
- Die Tastenwiederholung hing an der Bildrate: bei 3,9 Bildern/s dauerte ein
  Schritt **1,4 Sekunden** statt 200 ms. Sie läuft jetzt nach echter Zeit

### Bedienung
- Buttons von 71 auf **152 Pixel** — über Androids Mindestmaß für Touch-Ziele
- Spielfeld **+89 % Fläche**: die Kachelgröße richtet sich jetzt nach dem Gerät
- Menüs werden aus echten Maßen aufgebaut statt ein kleines Layout hochzuzoomen
- Tutorial mit Seitenumbruch statt gequetschtem Text
- Trefferzonen sind etwas größer als die sichtbaren Buttons
- PC-Oberfläche hat einen eigenen, kleineren Maßstab — Handy-Maße wirken am
  Monitor riesig

---

## Spieltiefe — PC Build 36 · Android Build 33

- **Elementarwaffen**: Feuer (Verbrennen), Frost (Schwächen), Blitz (Betäuben),
  Gift. Jede Gegnerart hat Stärken und Schwächen
- **Bossmechaniken**: Ork-Häuptling rastet unter 50 % Leben aus, Skelett-König
  beschwört Diener, Spinnen-Königin vergiftet aus der Ferne
- Ratten und Schleime fliehen bei wenig Leben, statt bis zum Tod zu kämpfen
- **Talentbaum** von 4 auf 8 Talente: Zähigkeit, Regeneration, Gier,
  Elementarfokus
- **Schreine** mit Segen oder Risiko: Vollheilung, dauerhafter Angriffsbonus,
  Gold — oder Fluch und Hinterhalt
- **Seltenheitsstufen** für Waffen und Rüstungen: Gewöhnlich bis Legendär,
  farblich erkennbar, tiefere Stufen erst in tieferen Ebenen
- **Rückweg nach oben**: Leitern führen zur exakt vorherigen Ebene zurück —
  gleiche Gegner, Gegenstände und Fallen, nicht neu erzeugt

---

## Grafik & Präsentation — PC Build 34 · Android Build 32

- Echte Bilder für Waffen, Rüstungen, Tränke, Schriftrollen, Gold, Leiter
  und Händler statt ASCII-Zeichen
- Monster-Grafiken, die zum Spieler schauen
- Deutsche Umlaute richtig dargestellt (ä ö ü ß statt ae oe ue ss)
- Spiel füllt den gesamten Querbildschirm

---

## Grundlagen — frühere Builds

- Update-Knopf im Spiel für PC und Android
- Spielstände unter Windows in `%APPDATA%`, nicht mehr neben der .exe
- Einstellungen: Bildschirm-Tasten, Sprache (Deutsch/Englisch), Lautstärke
- Bosse alle 5 Ebenen, Elite-Gegner, Fallen, Händler, Schriftrollen
- Erfolge, Statistiken, Bestiarium
- Touch-Steuerung, Android-Build über GitHub Actions
