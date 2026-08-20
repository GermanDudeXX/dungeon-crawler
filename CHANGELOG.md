# Changelog

Alle nennenswerten Änderungen an Dungeon Crawler. Neueste zuerst.
Nichts wird hier ausgelassen — das Spiel ist quelloffen, und was drin
steht, steht auch hier.

Das Spiel gibt es in zwei Fassungen:

* **Godot-Fassung** — die aktuelle, seit dem 18.08.2026. Android *und*
  Windows, gebaut mit Godot 4.7.1. Versionen wie `1.5.0`, im Spiel unter
  **Menü → Nach Update suchen** sichtbar.
* **pygame-Fassung** — die ursprüngliche. Eingefroren bei Android
  Build 90; sie bekommt keine Änderungen mehr, wird aber nicht gelöscht.
  Ihr Verlauf steht [weiter unten](#pygame-fassung-eingefroren).

---

# Godot-Fassung

## 1.6.5 — Schießen geht auch aus dem Stand

- **Der SCHIESSEN-Knopf hatte denselben Fehler wie der Automatikschuss**,
  und den hatte ich in 1.6.3 stehen lassen: die Abklingzeit zählt *Züge*,
  ein Schuss ist ein Zug — aber wer stillsteht, macht keinen weiteren
  Zug, und nichts zählte sie je herunter. Schuss, Schritt, Schuss war die
  einzige Reihenfolge, die funktionierte. Das war kein Rhythmus, das war
  eine Sackgasse. Jetzt läuft auch der Handschuss nach der Uhr: alle 0,30
  Sekunden einer, ob man sich bewegt oder nicht.
- Alte Spielstände, in denen die Abklingzeit auf 1 festhing, werden beim
  Laden bereinigt — sonst wäre der Bogen dort für den Rest des Laufs
  blockiert gewesen.

## 1.6.4 — Ein Symbol, das nach dem Spiel aussieht

- **Das App-Symbol auf dem Handy war ein Ausschnitt.** Als Projektsymbol
  stand der rohe 16 × 28 Pixel große Ritter-Sprite eingetragen: Android
  zog das auf 512 hoch und schnitt es rund zu, übrig blieb ein Stück
  Schild und ein halber Helm. Jetzt ein richtiges Set aus der eigenen
  Grafik des Spiels — beleuchtete Ziegelwand, der Ritter mittig mit
  Schatten, dünner Messingrahmen.
- Dazu die **adaptiven** Fassungen, die Android getrennt braucht:
  Vordergrund mit allem Wichtigen in den mittleren zwei Dritteln (mehr
  lässt eine runde Maske nicht stehen), Hintergrund aus derselben Wand,
  und eine **Silhouette** für die getönten Symbole ab Android 13 — ohne
  die zeigt ein getönter Startbildschirm gar nichts.
- **Die Windows-.exe trug Godots Roboter** in Taskleiste und Explorer.
  Jetzt derselbe Ritter, als .ico in sechs Größen von 16 bis 256, damit
  Windows in jeder Ansicht ein scharfes hat statt eines
  zusammengequetschten.

## 1.6.3 — Der Fernkampf funktioniert wirklich

Gemeldet: „automatischer Angriff, nichts mit Projektil fliegen sehen und
Schaden machen, die Klassen sind immer noch purer Nahkampf." Drei
Ursachen, alle drei echt.

- **Nach dem ersten Schuss war Schluss.** Die Abklingzeit zählt *Züge* —
  ein Schuss ist ein Zug, aber wer stillsteht, macht keinen weiteren Zug,
  und nichts setzte sie je zurück. Der Held schoss also genau einmal und
  danach nie wieder. Der automatische Schuss läuft jetzt nach der Uhr:
  alle **0,30 Sekunden** einer, etwas langsamer als Gehen. Der
  Handschuss über den Knopf behält den alten Rhythmus.
- **Das Geschoss war 4 × 2 Pixel und nach einer Zehntelsekunde weg.** Am
  Handy auf Armlänge sieht man das schlicht nicht. Jetzt ein halbes Feld
  lang, mit hellem Kern in einem additiven Glühen, sechzehn
  Hundertstelsekunden Flugzeit, Funken an beiden Enden.
- **Ein Magier ohne Bogen hat mit der Faust geworfen.** Der Schaden kam
  aus der Waffe — und die Waffe des Magiers ist die Faust, also machte
  der Schuss 2 Punkte, für immer. Ein Klassenschuss ohne Bogen ist jetzt
  ein eigener Wert, der mit der **Stufe** wächst statt mit dem, was du in
  der Hand hältst, und Rüstung zählt dabei nur halb: Stufe 1 = 3, Stufe 5
  = 7, Stufe 10 = 11 gegen Panzer 2. Ein Bogen rechnet weiter wie bisher.

## 1.6.2 — Knöpfe aus Stein und Messing, Schwierigkeit gehört zum Lauf

- **Knöpfe sehen jetzt nach diesem Spiel aus.** Godots Standardknopf ist
  eine graue Platte aus einem anderen Programm — neben dem Tileset liest
  er sich wie ein Fehlerfenster. Jetzt derselbe warme dunkle Stein wie die
  Fenster, mit Messingkante: heller unter dem Finger, leuchtend beim
  Drücken, stumpf und grau, wenn er nicht gedrückt werden kann. Das
  Steuerkreuz bleibt bewusst leiser als der Rest — acht messinggeränderte
  Platten in der Ecke wären das Lauteste im ganzen Verlies.
- **Die Schwierigkeit wird nach der Heldenwahl gefragt** und gilt dann für
  den ganzen Lauf. Vorher stand sie in den Einstellungen zwischen Ton und
  rotem Blitz und ließ sich mitten im Lauf umstellen — was an dem, was
  schon auf der Ebene steht, nichts ändert: ein Hardcore-Lauf konnte auf
  Leicht zu Ende gespielt werden. Sie gehört zum Lauf, also wird sie am
  Anfang eines Laufs gewählt und danach gehalten. Nachlesen kann man sie
  auf der Werte-Seite.

## 1.6.1 — Ein Knopf, der auch zuschlägt

### Behoben (gemeldet nach 1.6.0)
- **Türen standen weiter falsch.** Die Regel prüfte, ob auf zwei
  gegenüberliegenden Seiten Boden liegt — aber nie, ob auf den anderen
  beiden Wand ist. Ein Gangfeld mit Boden links, rechts und unten und
  Wand nur oben galt als Durchgang. Es ist keiner, es ist der Rand eines
  offenen Raums, und eine Tür darin ist ein Rahmen mit einem Pfosten.
  Über 120 Ebenen gemessen: **59 von 405 Türen** waren so. Jetzt 0 von
  346.
- **„Werte ansehen" tat nichts.** Meine Hilfsfunktion für die Seltenheit
  erwartete eine Zahl, bekommt aber eine Kennung wie `"rare"` — der
  Laufzeitfehler brach das Öffnen ab, bevor die Seite sichtbar wurde. In
  1.6.0 war die Seite damit nicht erreichbar.
- **Das Steuerkreuz hatte vier Knöpfe**, während die Einstellung acht
  Richtungen anbot. Jetzt neun Felder ohne Mitte, mit ↖ ↗ ↙ ↘. Bei „4
  Richtungen" verschwinden die Ecken wieder — ein Knopf, der im Moment
  des Drückens abgelehnt wird, ist schlimmer als keiner.

### Neu

- **WARTEN heißt ANGREIFEN**, solange etwas Waches direkt neben dir
  steht, und schlägt dann zu. Warten ist kein Kampfzug: wer neben einem
  wachen Gegner stehen bleibt, schenkt ihm einen Schlag und muss danach
  trotzdem zuschlagen.
- Stehen mehrere daneben, trifft er den mit den **wenigsten
  Lebenspunkten** — ein Kampf ist am kürzesten, wenn zuerst etwas aufhört
  zurückzuschlagen.
- **Schlafende lässt er in Ruhe.** Etwas Schlafendes neben dir ist die
  Gelegenheit vorbeizugehen, und ein Knopf, der ungefragt den Raum weckt,
  verliert Läufe.
- Schritte, die der Held ohnehin nicht gehen dürfte, zählen nicht als
  Reichweite: eine Diagonale bei „4 Richtungen", oder eine, die um eine
  Ecke schneiden würde.
- **Beim ersten Mal erklärt sich der Knopf** und hält den Schlag zurück,
  bis du bestätigst — mit Warnung, dass es einen Zug kostet und der
  Getroffene zurückschlägt. Danach nie wieder.
- Hineinlaufen greift weiterhin an, wie bisher.

## 1.6.0 — Menü in Gruppen, Werte-Seite, Buff-Plättchen

Die sieben Punkte aus dem Wunschzettel, von oben nach unten.

### Menü
- **Der Titelbildschirm hatte alles auf einmal**: vier Helden, sieben
  Schalter, zwei Lautstärkezeilen, den Update-Knopf und den Rekord. Auf
  dem Handy fiel das untere Ende heraus, und was herausfällt, ist
  unsichtbar statt scrollbar. Jetzt bleibt die Heldenwahl dort, wo sie
  hingehört, und dahinter liegen zwei Türen: **Einstellungen** und
  **Info & Update**.

### Steuerung
- **Diagonale abschaltbar.** „Richtungen: 8 (diagonal)" oder „4 (gerade)".
  Bei vier Richtungen gewinnt die Achse, in die der Daumen stärker
  gedrückt hat — auf dem Stick ist eine Diagonale leicht aus Versehen
  getroffen, und im Gang ist sie nie der gemeinte Schritt.

### Buffs
- **Statt einer Textzeile sechs Plättchen** unter den Balken, jeweils mit
  ablaufendem Balken: Gift grün, Blutung rot, alles andere blau. Der
  Balken ist der Anteil an der längsten Laufzeit, die dieser Buff hatte —
  ein Segen über 25 Züge und ein Trank über 4 starten beide voll und
  leeren sich so schnell, wie sie wirklich ablaufen.
- **Sekunden statt Züge habe ich bewusst nicht gebaut.** Ein Zug passiert,
  wenn du ihn machst. Eine Uhr würde Nachdenken bestrafen, und das ist das
  Einzige, woraus dieses Spiel besteht. Der Plan für den echten Umbau
  steht unten.

### Bosse
- **Mini-Boss auf der Ebene vor jedem Boss.** Bosse liegen auf 6, 9, 12,
  Mini-Bosse jetzt auf 2, 5, 8, 11 — etwas Denkwürdiges alle zwei bis drei
  Ebenen, nie zwei auf einmal.

### Anzeige
- **Namen über Boss, Elite und Wächter.** Nicht über gewöhnlichen
  Gegnern: fünf Ratten in einem Raum schrieben fünfmal „Ratte" über die
  Karte. Elite nur in vier Feldern Nähe, ein Boss immer.
- Das Namensschild trägt die Gegenskalierung von Sprite *und* Kamerazoom,
  sonst ist der Name größer als das Monster — was er beim ersten Versuch
  auch war.

### Werte
- **Neue Seite „Werte"** (Pausenmenü oder Taste C): Angriff und
  Verteidigung mit ihren Bestandteilen, Schadensminderung, kritische
  Treffer in Prozent samt Multiplikator, Regeneration, Reichweite, Waffe
  und Rüstung mit Seltenheit und Element, Gold, Kills, Gaben. Alle Zahlen
  gab es längst — sie standen nur nirgends.

### Schwierigkeit
- **Sicht und Fallen hängen jetzt daran.** Leicht: zwei Felder weiter,
  Fallen sichtbar, sobald Licht darauf fällt. Normal: wie gehabt. Schwer:
  ein Feld weniger. Hardcore: zwei Felder weniger. Sicht ist die
  billigste Schwierigkeit, die es gibt — dieselbe Ebene mit denselben
  Gegnern ist ein anderes Problem, wenn man sie ein Feld später sieht.

### Plan für die zeitbasierte Umstellung (nicht gebaut)
Falls es doch echt werden soll, in dieser Reihenfolge:
1. Eine Zugdauer einführen (z. B. 0,25 s) und alles, was heute „pro Zug"
   zählt, auf `delta` umstellen: Buffs, Gift, Blutung, Regeneration,
   Abklingzeiten.
2. Gegner bekommen eigene Timer statt eines gemeinsamen `enemy_turn()`.
3. Der Selbsttest-Bot braucht eine feste Schrittzeit, sonst prüft er
   nichts Reproduzierbares mehr.
4. Balance neu: alles, was heute „12 Züge" heißt, ist dann drei Sekunden.

## 1.5.0 — Karte, Anzeige und eine Windows-Fassung, die sich installiert

Ein Stapel aus zwölf gemeldeten Fehlern und zwei neuen Windows-Wünschen.

### Karte

- **Wände neben Türen fehlten.** Sicht wird zur Mitte jeder Kachel
  gezogen, und eine Wand, die diese Linie nur streift, blieb dunkel — der
  Raumrand bekam Löcher, durch die der Gang dahinter schien. Am
  schlimmsten an Türen, weil deren Rahmen genau die zwei gestreiften
  Kacheln sind: Türen standen in der Luft. Jetzt ist jede Wand neben
  einer sichtbaren Kachel ebenfalls sichtbar.
- **Banner lagen auf dem Boden** statt an der Wand zu hängen. Sie werden
  jetzt nur noch dort abgelegt, wo eine Wand dahinter steht, und einen
  halben Kachelrand höher gezeichnet.
- **Kisten standen in Türrahmen.** Blockierendes Dekor wird nicht mehr
  auf oder direkt vor eine Tür gesetzt.
- **Diagonal an einer Ecke vorbei** ging bisher, solange nur *eine* Seite
  Wand war. Damit lief man an geschlossenen Türen vorbei, ohne sie je zu
  öffnen. Eine blockierte Seite reicht jetzt, damit der Schritt abgelehnt
  wird — für Spieler und Gegner gleichermaßen.
- **Die Treppe nach unten** bekommt einen pulsierenden Rahmen, sobald man
  sie gesehen hat. Rot, solange der Boss den Schlüssel hält.

### Anzeige

- **Lebensbalken über Gegnern** sitzen jetzt auf dem Kopf statt darüber
  zu schweben: die Sprites haben oben durchsichtigen Rand, und der wurde
  mitgemessen. Dazu eine dunkle Spur dahinter, damit man auch sieht, was
  *fehlt*, und ein Balken für Bosse und Elite ab dem ersten Schlag.
- Balken werden nicht mehr vom Licht eingefärbt — ein Balken, den man im
  Dunkeln nicht lesen kann, ist genau da nutzlos, wo er gebraucht wird.
- **Der Schatten hängt nicht mehr nach.** Er wurde auf die Zielkachel
  gesetzt, während die Figur noch unterwegs war; jetzt hängt er am
  Sprite.
- Die Boss-Leiste liegt nicht mehr unter den Knöpfen oben rechts.

### Steuerung & Klassen

- **Der WARTEN-Knopf sagt jetzt, dass er etwas tut.** Er tat es vorher
  auch — ein Zug verging, Gift und Regeneration liefen weiter —, nur war
  auf einer leeren Ebene nichts davon zu sehen. Jetzt mit Einblendung und
  einem kurzen Ton. Das Pausenzeichen (zwei Striche) sitzt auf dem
  MENÜ-Knopf, denn in einem zugbasierten Spiel ist das Menü das Einzige,
  was wirklich pausiert.
- **Der Jäger kann schießen, auch ohne Bogen.** Reichweite hängt jetzt an
  der Klasse, nicht mehr nur am Gegenstand — wer ein besseres Schwert
  findet, hört nicht auf, Jäger zu sein.
- **Lautstärke in Zehnerschritten** statt nur an/aus, für Ton und Musik
  getrennt, mit ausgeschriebener Zahl.

### Windows

- **Das Spiel installiert sich.** Die heruntergeladene .exe fragt beim
  ersten Start, ob sie nach
  `%LOCALAPPDATA%\Programs\Dungeon Crawler` umziehen soll, legt
  Verknüpfungen auf den Desktop und ins Startmenü und startet von dort
  neu. Keine Administratorrechte, der Spielstand bleibt liegen, wo er
  liegt.
- **Das In-App-Update lud auf Windows eine .apk.** Es nahm einfach die
  erste Datei des Releases. Jetzt wählt es nach System: `.apk` auf
  Android, `.exe` auf Windows. Unter Windows kann sich ein laufendes
  Programm nicht selbst überschreiben, also übernimmt das eine kleine
  Batchdatei: auf das Ende des Spiels warten, Datei tauschen, neu
  starten, sich selbst löschen.

### Geprüft

- Selbsttest um Prüfungen für Türen, automatisches Schießen und
  Stockwerk-Gedächtnis erweitert; läuft über mehrere Startwerte je 800
  bis 2000 Züge.
- Gegner-Verfolgung nachgemessen (Abstand 7 → 5 → 3 → 1, dann Angriff):
  sie funktionierte bereits, ein Gegner steht nur still, solange er
  schläft — und er schläft, bis Licht auf ihn fällt.

## 1.4.1 — Türen führen irgendwohin, und Leben ist ein Balken

- **Türen mitten im Gang.** Ein Gang, der neben einem Raum entlangläuft,
  sah an jeder Stelle wie ein Durchgang aus. Jetzt muss eine der beiden
  offenen Seiten *im Raum* liegen, und hinter beiden Seiten müssen
  mindestens fünf Felder Boden liegen — sonst führt die Tür ins Nichts.
  Gemessen über 120 Ebenen: von 1597 Türplätzen nach alter Regel bleiben
  1241, gut ein Fünftel war Unsinn.
- **Lebensbalken statt „HP 7/24"**: grün, ab 55 % bernstein, ab 28 % rot,
  mit nachlaufendem hellem Streifen für den letzten Treffer, Schild in
  Hellblau dahinter, XP-Balken darunter, und eine breite Leiste für Bosse.

## 1.4.0 — Stockwerke bleiben, Fernkämpfer schießen selbst

- **Ebene runter und wieder hoch** führte in ein neu ausgewürfeltes
  Stockwerk. Jetzt wird jede verlassene Ebene beiseitegelegt und
  unverändert wieder aufgebaut — dieselben Wände, dieselbe Beute,
  dieselben Toten. Wird mitgespeichert.
- **Doppelschritt auf dem PC:** die Tastenwiederholung setzte nach 0,14 s
  ein, schneller als man loslässt. Jetzt 0,34 s.
- **Türen standen nebeneinander** und mitten im Raum.
- **Händler und Türen waren im Dunkeln sichtbar.** Deko und Läden nur
  noch im Licht, Beute nur als gedimmte Erinnerung.
- **Magier und Jäger schießen von selbst**, sobald etwas Waches in
  Reichweite steht und die Linie frei ist. Nie auf etwas direkt daneben,
  nie statt eines Schritts, nie auf Schlafendes. Abschaltbar.
- Sichtbarer Schuss in Waffenfarbe, Funken am Ziel, Schatten unter allem,
  weißes Aufblitzen bei jedem Treffer.

## 1.3.1 — Pausenmenü und die erste Windows-Fassung

- Pausenmenü im Spiel mit Ton, Musik, Steuerung und Update-Knopf.
- **Windows-Fassung** als einzelne .exe (122 MB, nichts zu entpacken).
- Ein Händler konnte hinter einem anderen eingemauert werden.

## 1.3.0 — Das Update lädt und installiert sich in der App

- **In-App-Update**: fragt GitHub nach der neuesten Version, lädt sie und
  übergibt sie dem Installer. Browser-Link als Rückfalllösung, falls das
  Gerät die Übergabe verweigert.
- Android-Berechtigung `REQUEST_INSTALL_PACKAGES`, im gebauten Paket
  nachgeprüft.
- TLS-Prüfung bleibt unangetastet: Wer die Frage „welche Datei installierst
  du als Nächstes" ungeprüft beantworten lässt, lässt jemand anderen die
  Datei aussuchen.

## 0.13.0 — Gefangene, Fallen, Elite

- Gefangene, die man befreien kann.
- Vier weitere Fallen, vier Schreinausgänge, drei neue Elite-Arten.
- **Der Jäger** als vierte Klasse, und Bögen als eigene Waffenart mit
  Reichweite.

## 0.12.0 — Bestiarium, Punktzahl, Warten

- Bestiarium: was man getroffen hat, mit Zahlen; Unbekanntes bleibt
  sichtbar als Lücke.
- Punktzahl am Ende eines Laufs, fünf weitere Erfolge.
- Ein Zug, in dem man absichtlich nichts tut.

## 0.11.0 — Themenräume und Aufträge

- **Themenräume**: Bibliothek, Waffenkammer, Alchemistenstube, Beinhaus.
- **Ein Auftrag pro Ebene** mit Belohnung.
- Vier weitere Abschnitte (Versunkene Hallen, Aschewüste, Pilzgärten, Die
  Leere), drei Rollen, drei Gaben.
- Eine einzige Regel für alles, was den Weg versperrt — vorher konnten
  Kisten, Händler und Blitzreisen jeweils eigene Sackgassen bauen.

## 0.10.0 — Türen, tiefere Gegner, Daumenstick

- Türen an den Zugängen der Räume.
- Sieben tiefere Gegnerarten, jede mit eigener Gewohnheit (Fallen legen,
  Netze spinnen, beschwören, sich teilen, aus der Ferne schießen).
- **Daumenstick**: acht Richtungen, lückenloses Gleiten, überall auf der
  linken Bildhälfte bedienbar.

## 0.9.0 — Update-Knopf, Läden, größere Sicht

- Update-Knopf auf dem Titelbildschirm.
- Zoom richtet sich nach dem Bildschirm.
- Elite-Gegner sind sichtbar anders, Schriftrollen beim Händler.
- Spielstand-Prüfung deckt die ganze Ebene ab.

## 0.8.0 — Bewachte Truhen und ein Schmied, der verzaubert

- Bewachte Truhen: erst das, was davorsteht, dann der Deckel.
- Schmied, der aufwertet, verzaubert und umschmiedet.
- Erfolge.
- Funken und eine kurze Pause beim Treffer.

## 0.7.0 — Tasche, Banner, und ein Boss, der stehen bleibt

- Trankbeutel mit allen Sorten, Wirkung und Anzahl.
- Ereignis-Banner in der Bildmitte.
- Schwärme zählen zum Gegner-Budget, statt obendrauf zu kommen.
- **Ein Boss, der wegläuft, ist eine Sackgasse**: Bosse weichen nicht
  mehr zurück, und niemand weicht mehr als drei Schritte am Stück.

## 0.6.0 — Eigenarten, Gefahren, Superboss

- Jedes Monster mit eigener Eigenart.
- Stehende Gefahren (Feuer, Säure, Dornen), festes Dekor, ein Superboss.
- Weiches Laufen, Lebensbalken, schlafende Gegner erkennbar.
- Startausrüstung je Klasse.

## 0.5.0 — Bossphasen, Minikarte, Rückweg

- Bossphasen.
- Treppe nach oben und Minikarte.
- Schadenszahlen, Trefferblitz, Kamerawackeln.
- Elementarwaffen und Blutungen.

## 0.4.0 — Alle 31 Tränke, Rollen, Schreine, Seltenheiten

- Alle 31 Tränke, Buffs, Schild.
- Schriftrollen, Schreine, Elitegegner, Mini-Bosse, Schatzkammer.
- Seltenheitsstufen für Waffen und Rüstungen.
- Vier Schwierigkeitsgrade, dauerhafte Statistik.

## 0.3.0 — Stufenaufstieg mit Wahl

- Stufenaufstieg mit Auswahl aus drei Gaben, kritische Treffer.
- Ein Feld, ein Ding: nichts liegt mehr übereinander.

## 0.2.0 — Klassen, Titelbildschirm, Speichern

- Drei Klassen, Titelbildschirm, Speichern und Fortsetzen.
- Ton, Musik, Todesbildschirm.
- Truhen und Läden sichtbar, Sprites in der richtigen Größe.

## 0.1.0 — Der Port

- Die pygame-Fassung in Godot 4.7 neu gebaut: dieselbe Kartenerzeugung
  Zeile für Zeile, damit derselbe Startwert denselben Dungeon legt und
  der Port gegen das laufende Spiel geprüft werden kann statt gegen ein
  Gefühl.
- Grund für den Umzug: auf dem Handy lief die pygame-Fassung mit 6 bis 17
  Bildern pro Sekunde, die Godot-Fassung mit 120.

---

<a name="pygame-fassung-eingefroren"></a>

# pygame-Fassung (eingefroren)

Steht bei Android Build 90. Bekommt keine Änderungen mehr — die
Godot-Fassung oben hat sie abgelöst. Der Verlauf bleibt hier stehen, weil
er zum Spiel gehört.

## Zuletzt — PC Build 73

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

## PC Build 56 · Android Build 53

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
