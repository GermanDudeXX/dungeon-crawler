# Changelog

Alle nennenswerten Änderungen an Dungeon Crawler. Neueste zuerst.

Die Build-Nummern stehen im Spiel unter **Einstellungen → Version** und
zählen auf PC und Android getrennt hoch.

---

## Aktuell — PC Build 73

### Karte & Grafik
- **Echte Dungeon-Grafik!** Steinböden, Ziegelwände und massiver Fels statt
  farbiger Vierecke. Wände wählen automatisch die passende Ansicht, je
  nachdem, wo der Raum liegt
- Alle fünf Themen (Krypta, Höhlen, Eisenverlies, Flammenreich, Frostgruft)
  sehen jetzt deutlich unterschiedlich aus — dieselbe Steinmetzarbeit in
  anderem Licht
- Deko in den Räumen: Banner, Fässer, Schädel, Säulen. Sie bleibt liegen,
  wo sie ist, auch wenn du die Ebene später noch einmal betrittst

### Helden
- **Drei Klassen** zur Auswahl, jede mit eigener Spielfigur:
  - **Krieger** — zäh und gepanzert, verzeiht Fehler
  - **Schurke** — zerbrechlich und schnell, trifft ständig kritisch
  - **Magier** — schwach im Nahkampf, startet mit Rollen und verzaubert
    seine Treffer
- Jede Klasse startet mit eigener Ausrüstung und eigenen Tränken

### Schwierigkeitsgrade
- **Einfach / Normal / Schwer / Hardcore**, zu Beginn jedes Laufs wählbar
- Sie verändern dein Leben und deinen Schaden, das der Gegner und die
  Ladenpreise. Erfahrung wird nie skaliert — ein schwerer Lauf ist wirklich
  schwerer, nicht nur länger

### Tränke — von 1 auf 30
- Heilung, dauerhafte Verbesserungen, Kampf-Effekte, Heilmittel,
  Wurfphiolen und drei verfluchte, die man nur findet und nie kaufen kann
- **Neuer Trankbeutel** (Taste I oder BEUTEL): zeigt alle Tränke mit Bild,
  Wirkung und Anzahl. Jede Zeile ist direkt trinkbar
- Effekte halten mehrere Runden, stapeln sich frei und werden im HUD mit
  Restdauer angezeigt
- Händler haben jetzt jeder ein eigenes Sortiment

### Gegner
- **Namensschilder** über jedem Monster: Lebensleiste, Name, Stufe und
  Symbole für alle Effekte, die gerade auf ihm liegen
- **Skelette weichen zurück**, wenn du zu nah kommst, und schießen aus der
  Distanz — jetzt muss man sie jagen
- **Ratten und Fledermäuse kommen im Schwarm**
- **Goblins legen Fallen**, während sie sich zurückziehen
- **Bosse haben sichtbare Phasen** — die Leiste wechselt die Farbe, nennt
  die Phase und zeigt, wo die nächste beginnt
- **Mimiks**: manche Schatztruhen sind Monster. Von außen nicht zu erkennen

### Räume & Gefahren
- **Mini-Boss auf jeder 3. Ebene**
- **Schatzräume** mit bewachter Truhe — erst den Wächter töten
- **Boss-Türen**: auf Boss-Ebenen ist die Treppe versperrt, bis der Boss fällt
- **Bodengefahren**: Lava, einstürzende Böden und Stachelbetten. Anders als
  Fallen sind sie sichtbar und sollen umgangen werden
- **Superboss** alle 25 Ebenen

### Statuseffekte
- **Bluten** bei jedem kritischen Treffer
- **Frost verlangsamt** jetzt zusätzlich — betroffene Gegner handeln nur
  noch jede zweite Runde

### Spielgefühl
- Funken bei jedem Treffer, ein größerer Ausbruch bei einem Kill
- Kurzer Standbild-Moment bei kritischen Treffern und beim Boss-Tod
- **Der Todesbildschirm** zeigt jetzt den ganzen Lauf: Held, Schwierigkeit,
  Waffe und Rüstung, Endwerte, was du noch dabei hattest und wie viele
  Tränke es gekostet hat

### Behoben
- **Update-Fehler „Failed to load Python DLL":** Ein Update konnte sich
  stillschweigend nicht installieren und startete danach die alte, inzwischen
  beschädigte Version. Der Austausch wird jetzt bei jedem Schritt geprüft,
  bis zu 15-mal wiederholt und im Fehlerfall zurückgerollt — und wenn er
  wirklich scheitert, sagt das Spiel es dir beim nächsten Start, statt so zu
  tun, als hätte es geklappt. Zusätzlich blieb pro Update ein 40-MB-Ordner
  im Temp-Verzeichnis liegen (350 MB waren angesammelt); der wird jetzt
  aufgeräumt
- Monster verloren beim Speichern oder beim Zurückkehren auf eine Ebene ihre
  Tiefen-Skalierung und wurden wieder so schwach wie auf Ebene 1
- Von Bossen beschworene Diener und Hinterhalte ignorierten die Tiefe
  ebenfalls und waren auf tiefen Ebenen harmlos
- Eine versteckte Falle konnte unter einer Bodengefahr liegen — zwei Treffer
  für einen Schritt, ohne den zweiten kommen zu sehen

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
