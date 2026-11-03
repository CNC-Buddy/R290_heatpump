# Lokale Validierung · R290-NextGen 1.1.1

Stand: 03.11.2026. Sämtliche Prüfungen sind von der realen Anlage getrennt.

## Automatischer Hausverbrauch b21

- Acht Browser-Prüfgruppen in `tests/frontend-electric.mjs` bestanden, inklusive
  der bisherigen Darstellung, Animation, Geometrie, DE/EN und Einrichtung.
- Screenshot-Eingaben 850 W PV, 3,18 kW Netzbezug, 0 kW Batterie ergeben 4,03 kW
  Hausverbrauch; der gemeinsame 3,27-kW-Shelly wird nicht nochmals addiert.
- Beide Vorzeichenkonventionen, Laden/Entladen, Bezug/Einspeisung, W/kW,
  echter Nullverbrauch, Quellverläufe, gemessener Vorrang und Sensorausfall geprüft.
- Fehlende, veraltete, ungültige oder wiederhergestellte Quellen, unbekannte
  Richtung, mehrfach zugeordnete Quelle, negative Bilanz und getrennte Verbindung
  liefern keinen vermeintlich gültigen Hauswert oder Haus-Fluss.
- Leere Hauszuordnung über die Oberfläche gespeichert und nach Deaktivieren/
  Aktivieren erhalten. Berechnete Anzeige in DE/EN bei 1800/1280/768/390 Pixeln
  ohne Text-/Seitenüberlauf und mit vollständig verbundenen Leitungen.
- Beispielvorschau: `artifacts/r290-electric-calculated-b21-de.png`.
- Nur Anzeige-/Berechnungslogik geändert; keine Backend-Regelung, keine neue
  Recorder-Entität, keine Live-Gerätebefehle und keine produktive Installation.
  Python und vollständige UI-Suite nicht wiederholt; letzter kompletter UI-Stand b19.

## Kompakte Stromleiste b20

- Sechs gezielte Browser-Prüfgruppen in `tests/frontend-electric.mjs` bestanden:
  kompakte vierteilige Leiste ohne Einzelrahmen, gemeinsamer Heizungszähler unter
  dem Hauswert, Historienaufrufe, Bilanz, Richtung, Datenqualität und Einrichtung.
- Neue Pfeilanimation: tatsächlicher Fortschritt der Wegposition, Pause,
  reduzierte Bewegung und Erhalt der Animationsknoten bei Liveupdates geprüft.
- 1800/1280/768/390 Pixel in DE und EN ohne Text-/Seitenüberlauf; alle Leitungsenden
  an Komponenten oder Abzweigen verbunden, keine doppelten Leitungsstrecken.
  Desktop- und mobile Screenshots visuell kontrolliert. Unter 250 Pixel Höhe
  für die gesamte Leiste im breiten Testfenster.
- Neue lokale SVG-Illustrationen ohne externe Bildaufrufe. Vorschauen:
  `artifacts/r290-electric-strip-b20-de.png` und
  `artifacts/r290-electric-overview-b20-mobile-en.png`.
- Keine Backend-Regelungsänderung, keine Live-Anlagenzugriffe und keine
  produktive Installation. Python und vollständige UI-Suite für diese isolierte
  Darstellungsänderung nicht wiederholt; letzter vollständiger Stand b19 unten.

## Gemeinsamer Heizungszähler und verbundene Energieflüsse b19

- **86 Browser-Prüfgruppen und drei Node-Modellprüfungen bestanden** mit
  `npm run test:ui`, bereits nach Versionsanhebung auf b19.
- Sechs Stromübersichts-Prüfgruppen: fünf Komponenten, gemeinsamer Messwert als
  Haus-Unterzweig, keine doppelte Bilanzierung, native HA-Historie, gespeicherte
  Zuordnungen und DE/EN. Bestehende `hp_power`-Zuordnungen bleiben nutzbar.
- Geometrie bei 1800/1280/768/390 Pixeln in beiden Sprachen geprüft: jeder Anschluss
  ist verbunden, keine offenen Leitungsenden und keine überlappenden Strecken.
  Desktop- und Mobilansicht anhand der Screenshots visuell kontrolliert.
- Tatsächlich fortschreitende Animation über veränderten CSS-Strichversatz
  geprüft, ebenso Pause, reduzierte Bewegung und unveränderte Animationsknoten
  bei Liveupdates. Nachtbetrieb kehrt den Hauptfluss bei Netzbezug und
  Batterieentladung um. Nullwerte, ungültige/veraltete Meldungen, unbekannte
  Richtung, unplausible Gesamtbilanz und Verbindungsabbruch werden berücksichtigt.
- **Sechs vorhandene Python-Prüfungen** für Einstellungen, Historienfreigabe
  und Migration erneut bestanden. Die Backend-Regelung wurde nicht verändert;
  die übrigen Python-Suites und der große Theme-Audit wurden nicht wiederholt.
- Vorschauen mit Beispieldaten: `artifacts/r290-electric-strip-b19-de.png`,
  `artifacts/r290-electric-overview-b19-de.png`,
  `artifacts/r290-electric-setup-b19-de.png` und
  `artifacts/r290-electric-overview-b19-mobile-en.png`.
- Lokaler Testbrowser ohne Zugriff auf die reale Anlage; keine Installation,
  Neustarts oder Gerätebefehle. Das b18-Archiv bleibt unverändert.

## Separate Stromübersicht b18

- **85 Browser-Prüfgruppen und drei Node-Modellprüfungen bestanden** mit
  `npm run test:ui`. Neue Prüfungen für vier getrennte Stromkomponenten,
  Ein-/Ausschalten samt gespeicherten Quellen, W/kW-Umrechnung, Ladezustand,
  beide Vorzeichenkonventionen, unbekannte Richtung, ungültige/veraltete Werte,
  echten Nullverbrauch, native Verlaufsaufrufe und pausierte Animation.
- Neue Ansichten in DE/EN bei 1800, 1280, 768 und 390 Pixel Breite ohne äußeren
  oder internen Textüberlauf. Strombereich und Einrichtung visuell kontrolliert.
  Bestehende Prüfung von Scroll-Erhalt, Live-DOM, Heizstabpositionierung,
  Kurven, Service, Parametern und Editor vollständig erfolgreich.
- **35 Python-Tests bestanden**: sechs neue Stromübersichts-/Migrationstests,
  19 Panel-API-Tests und zehn Schaubildtests. Geprüft sind Erhalt von Koordinaten,
  Leitungen, angebauten Heizstäben und Original-Graphen; eindeutige und mehrdeutige
  Quellen; wiederholte Migration; alte Clients; Historienfreigabe; alte JSON-
  Importe; Revisionskonflikte und rein elektrische Altzeichnungen.
- Nach Versionsanhebung auf b18 die fünf neuen Browsergruppen und sechs neuen
  Python-Tests erneut erfolgreich ausgeführt. Vollständiger Hintergrund-Audit
  nicht wiederholt; sein letzter Stand bleibt unten bei b16 dokumentiert.
- Reproduzierbar: `npm run test:electric`,
  `python -m unittest discover -s tests -p test_electric_overview.py -v` sowie die
  bereits vorhandenen `test_panel_api.py`- und `test_schematic.py`-Testgruppen.
- Vorschauen mit Beispieldaten: `artifacts/r290-electric-strip-de.png`,
  `artifacts/r290-electric-overview-de.png`, `artifacts/r290-electric-setup-de.png`
  und `artifacts/r290-electric-overview-mobile-en.png`. Lokaler Chromium/Edge,
  keine Verbindung mit produktivem Home Assistant oder echten Aktoren.
- Neues lokales Paket b18. Keine produktive Installation oder Geräteänderung;
  vorherige ZIP-Dateien bleiben erhalten.

## Schaubild-Bedienung und elektrische Messquellen b17

- Neue Regressionen für Platzierung per Maus, Tastatur und Touch, Abbrechen ohne
  Änderung, exaktes Rückgängig/Wiederholen, 200-%-Zoom und gescrollte mobile Fläche.
- Leitungswege vor/nach Einfügen, Ziehen, Koordinateneingabe, Spiegeln und
  Speichern/Neuladen verglichen. Unverbundene Bauteile verändern keine Leitung;
  das Verschieben einer WP passt nur die tatsächlich angeschlossenen Wege an.
  Vergrößern der Zeichenfläche ändert den Darstellungsmaßstab nicht.
- DE/EN-Felder für Netz, PV, Haus, Batterie und Heizstab geprüft, einschließlich
  Einheitenfilter für Leistung/Ladezustand und Speicherung der Zuordnung.
- Python prüft gespeicherte automatische Wege, unzulässige/überlange Werte,
  unveränderte hydraulische Verbindungen und Speicherung ohne Gerätebefehle.
- Reproduzierbar mit `npm run test:schematic` sowie
  `python -m unittest discover -s tests -p test_schematic.py -v`.
  Prüfergebnis: **17 Browser-Prüfgruppen, zwei Node-Prüfskripte und zehn
  Python-Tests bestanden**. Die übrigen UI-/Theme-Prüfungen wurden nicht erneut
  ausgeführt; ihr letzter vollständiger Stand ist unten unter b16 dokumentiert.
- Screenshots der Vorschau und elektrischen Seitenleiste unter
  `artifacts/r290-placement-preview.png` und `artifacts/r290-electric-inspector-en.png`.
  Touch-Prüfung in lokalem Chromium, kein Test auf einem echten Smartphone.
- Keine produktive Installation, kein Home-Assistant-Neustart und keine
  Gerätebefehle. Vorherige Archive bleiben unverändert; neuer Stand: b17.

## Vollständiger Hintergrund-Audit und Tabellenkorrektur b16

- 39 Ansichten/Zustände in DE und EN auf 1920×1200, 1024×1366 und 390×844:
  **234 erfolgreiche Darstellungsprüfungen**, keine Browser-Laufzeitfehler.
- Alle fünf Hauptbereiche, sämtliche Service-/Einstellungsunterseiten, vier
  Kurven mit Basis/PV/Feinabstimmung, sämtliche Parameterlisten, leeres und
  gefülltes Schaubild sowie dessen veröffentlichte Darstellung geprüft.
  Hinzu kommen Leer-/Fehlerzustände, Entitätensuche und sechs Dialogvarianten.
- Prüfkriterien: volle Hintergrundhöhe/-breite, kein äußerer horizontaler
  Überlauf, transparente Schaubild-Werkzeugleisten, passende Dialogflächen,
  Hintergrundabdeckung nach Scrollen bis zum Seitenende und Erreichbarkeit
  der letzten Zeile aller fünf Parameterlisten. Ansichten am Anfang und Ende
  wurden zusätzlich anhand der Bildschirmaufnahmen visuell kontrolliert.
- Dabei wurde ein zusätzlicher Fehler in langen System-/Echtwertlisten
  gefunden: absolut positionierte Screenreader-Beschriftungen vergrößerten
  den äußeren Scrollbereich bis weit unter den Seitenhintergrund. Ein eigener
  Positionierungskontext am Tabellencontainer begrenzt diese Hilfstexte auf
  die Tabelle. Der neue Test schlug vor dieser Korrektur fehl und besteht danach.
- Die vollständige vorhandene UI-Suite besteht erneut: **74 Browser-Prüfgruppen
  plus drei Node-Modellprüfungen**. Ein veralteter Versionsvergleich im Test
  liest jetzt die tatsächliche Manifestversion.
- Reproduzierbar mit `npm run test:theme`. Bericht und Screenshots liegen unter
  `artifacts/theme-audit-1.5.0b16/`. Lokaler Testbrowser mit Home-Assistant-Doubles;
  keine Prüfung aller Seiten in der produktiven HA-Instanz oder auf echtem iOS.
- Keine Änderung an Pumpen-/Modbus-Regelung. Keine Live-Gerätebefehle,
  Installation oder Neustarts. Python-Funktionstests wurden für diese CSS-
  Korrektur nicht wiederholt. Die bereits gelieferten Archive b14/b15 bleiben
  unverändert; der neue Stand wird als `r290_heatpump-1.5.0b16.zip` bereitgestellt.

## Darstellungskorrektur und Paket 1.5.0b15

- Schaubildeditor und veröffentlichtes Schaubild: transparenter Host entfernt
  den dunklen Kasten hinter den Werkzeugleisten. Buttons unverändert.
- Service/Parameter: Mindesthöhe der Panelwurzel entspricht der dynamischen
  Bildschirmhöhe. Der tatsächliche HA-Wrapper hat automatische Höhe; der
  Regressionstest bildet dies auf 1500×1300 und 390×1100 ab. Er schlug vor der
  Mindesthöhenkorrektur fehl und besteht danach.
- Acht Anlagen-/Service- und sechs Schaubild-Browserprüfgruppen bestanden;
  keine Laufzeitfehler. Kontextscreenshots zeigen die Hintergrundflächen.
- HA 2026.10.4 / Frontend 20260930.5 wurde ausschließlich lesend geprüft.
  Die Integrationskarte zeigte das lokale Icon korrekt; der Benutzer bestätigte
  die Anzeige ebenfalls. Die PNGs benötigen keine Korrektur.
- Keine Backend-Regellogik geändert, keine Live-Installation oder Gerätebefehle.
  Der neue vollständige lokale ZIP-Stand heißt `r290_heatpump-1.5.0b15.zip`;
  das bereits verteilte b14-Archiv bleibt unverändert.

## Paketfreigabe 1.5.0b14

Auf Benutzerwunsch wird der vollständige b14-Stand jetzt als lokales
`artifacts/r290_heatpump-1.5.0b14.zip` mit SHA-256-Datei paketiert. Enthalten sind
auch Theme/Wellen, Vektorlogo und alle acht lokalen Home-Assistant-Markengrafiken.
Die unten dokumentierten erfolgreichen Funktionsprüfungen bleiben die Testbasis;
für den Paketbau werden Archivintegrität, Vollständigkeit, Quellgleichheit,
Versionen, Python-/JSON-Syntax und lokale Frontend-Abhängigkeiten geprüft.
Der separate Paketprüfbericht liegt unter
`artifacts/release-1.5.0b14-validation.json`.
Eine Installation in Home Assistant oder ein Geräte-/Firmwareupdate erfolgt nicht.

## R290 NextGen Logo und Icon (b14, Prüfung vor Paketfreigabe)

Gemeinsame Vektorgrafik für das Logo rechts in der Kopfleiste und die acht
lokalen Home-Assistant-PNGs (Icon/Logo, hell/dunkel, Standard/@2x). Desktop und
390-px-Mobilansicht sowie helle/dunkle Logoansicht und kleine Icons wurden visuell
kontrolliert. Die drei vorhandenen Betriebsdaten-Browsergruppen bestanden erneut
einschließlich DE/EN, Navigation und P183-Verhalten. Es gab keine Gerätezugriffe.
Der Export arbeitet mit lokalem SVG und blockierten Netzwerkanfragen. Der
Paketdateifilter berücksichtigt die Grafiken; Paketbau folgt mit der Freigabe oben.
Die automatische Icon-Anzeige im echten HA wurde hier nicht live getestet.

## Display-Theme (b14, Prüfung vor Paketfreigabe)

Das Marineblau/Cyan-Theme wurde in der lokalen Beispieldatenoberfläche geprüft:
Betriebsdaten, Anlagenübersicht, Kurvenwerkstatt, Entitätensuche, Schaubildeditor,
veröffentlichtes Schaubild und Temperaturzonen. Desktop und 390-px-Mobilansicht
wurden visuell kontrolliert. Formularflächen, Dialoge, Diagrammlegenden und
SVG-Beschriftungen verwenden die gemeinsamen Theme-Farben; Warnungen behalten
ihre eigene Bedeutung. Die Mobilaufnahme wartet auf die angepassten SVG-Achsen.

Die vollständige UI-Suite bestand: **73 Browser-Prüfgruppen und drei
Node-Prüfungen**. Nach der abschließenden Schaubild-Button- und Pumpenlayoutkorrektur
bestanden erneut die sechs Schaubild- und drei Betriebsdaten-Prüfgruppen.
Keine Backend-Regelung geändert; Python-Tests wurden für diese reine
Oberflächenänderung nicht erneut ausgeführt. Keine Bereitstellung in Home Assistant.

## Betriebsdaten, Sprachen und P183 in b14 (Entwicklungsstand)

**254 Python-Tests und 73 Browser-Prüfgruppen bestanden**, zusätzlich drei
Node-Prüfungen zu Schaubildmodell, Leitungsgeometrie und Diagrammzuständen.
15 neue Python-Tests prüfen Live-P183, falsche/unlesbare Passwörter, ausdrückliche
Eingabe bei P183=0, Freigabe je Verbindung/Gerät/Administrator, Ablauf, Änderung
des Gerätepassworts, explizite Sperre, Verbindungsabbau während der Prüfung,
Versuchsbegrenzung und maskiertes Passwort-Änderungsprotokoll. Die HA-Verbindung
wird mit `__slots__` nachgebildet; Grants hängen an einer Disconnect-Subscription.
Die Zustandsverläufe behalten unbekannte Übergänge; große Frequenzverläufe werden
begrenzt, während andere numerische Diagramme kompakt bleiben.

Drei neue Browsergruppen prüfen die gemeinsame Betriebsdatenansicht, erhaltene
Diagrammquellen, gemeinsame und individuelle Zeitwahl, Phasenlücken, DE/EN,
Mobilansicht, geräteweise P183-Freigabe, Ablauf und Sperren. Alle 255 Katalogzeilen
in Main/Realtime/User/User 2 besitzen Namen und Erklärungstexte in beiden Sprachen.
Die bestehende Prüfung aller 518 Katalogzeilen bleibt erhalten. Desktop-Screenshots
wurden visuell geprüft. Unbekannte Register werden weiterhin nicht als bekannte
Gerätefunktionen ausgegeben.

Während dieser Entwicklungsprüfung wurde noch kein Paket erstellt. Kein Live-Update,
keine realen Gerätebefehle. Die P183-Sperre gilt für die Panel-Schreibschnittstelle;
native HA-Administratordienste und bestehende Automationen sind nicht gesperrt.

## Ausgewählte Messquellen zuerst in b13

Die Sortierung wurde in DE/EN mit ausgewählten und übrigen Messquellen geprüft:
ausgewählte Quellen stehen zuerst, beide Gruppen sind alphabetisch sortiert,
und die gesetzten Häkchen bleiben erhalten. Die vier bestehenden Browser-
Prüfgruppen in `frontend-dashboard.mjs` wurden erneut erfolgreich ausgeführt.
Die vollständige Prüfung des unveränderten b12-Unterbaus ist unten dokumentiert.

## Diagramme, Speicher und Menü in b12

**239 Python-Tests und 70 Browser-Prüfgruppen bestanden**, zusätzlich drei
Node-Prüfungen zu Schaubildmodell, Leitungsgeometrie und Diagrammzuständen. Alle Daten stammen aus
lokalen Testfällen; keine Gerätebefehle aus den neuen UI-Funktionen.

Sechs zusätzliche Python-Tests prüfen Diagramm-Persistenz, Erhalt bei älteren
Einstellungsformularen, History-Zuordnung, Administratorrechte, Revisionskonflikte,
Größenlimits und ungültige Eingaben sowie Speicherfühler und Heizstabzuordnung.
Vier neue Browser-Prüfgruppen decken das gruppierte Menü, Leitungsgriffe und Undo,
vier Fühlerhöhen, mitbewegte Heizstäbe, fehlende Werte, anklickbare Verläufe,
Tooltips, schaltbare Legenden, gespeicherte Zeit-/Quellenauswahl, alle vier
Basiskurven, DE/EN und Mobilansicht ab. Bestehende Tests wurden auf die neue
Navigation angepasst; die Entitätssuche bleibt während Live-Updates erhalten.
Die Speicheransicht wurde anhand eines Browser-Screenshots visuell geprüft.

Die Prüfung ersetzt keinen Test in der laufenden Home-Assistant-Installation.
Es wurde ausschließlich ein lokales Installationspaket erstellt.

## Variable Stützpunkte in b11

Abschluss: **233 Python-Tests und 66 Browser-Prüfgruppen bestanden**, zusätzlich
die bestehenden Node-Prüfungen des Schaubildmodells. 17 zusätzliche Python-Tests
prüfen die frühere Zweipunktformel an 801 Außentemperaturen für jeweils fallende,
steigende und flache Kurven, Mehrpunktinterpolation, Endbegrenzung, ungültige Werte,
alle vier Kurventypen, atomare Speicherung, Berechtigungen/Revisionskonflikte,
Kompatibilität der alten Endpunkt-Entitäten und die tatsächlichen Regelcallbacks.

Regelungstests decken Geräteadressierung, Mindeständerung/Integer-Rundung, Glättung
ohne Seiteneffekt beim Attributlesen, kombinierte PV-/externe Anhebung, nachgelagerte
Sollwertbegrenzung sowie Schreibfehler und Wiederholung ab. 5 neue Browsergruppen
prüfen Hinzufügen/Entfernen von 2–10 Punkten, Werteingabe, Tastatur/Ziehen, DE/EN,
Vorschau/Bestätigung, unabhängige Entwürfe, Revisionskonflikte, Offlinezustand und
stabile Mobilansicht. Desktop- und Mobil-Screenshots wurden visuell kontrolliert.
Zusätzlich sind das Wiederladen gespeicherter Punkte für alle vier Zielregister
und die korrekte 16-Bit-Kodierung negativer Sollwerte geprüft.

Das Paket wurde ausschließlich lokal gebaut. Kein Live-Update und keine Änderung
an der Heizungsanlage wurden ausgeführt. Hardware-Fallback bei HA-Ausfall und das
reale Temperaturverhalten sind nicht durch diese simulierten Tests nachgewiesen.

## Schaubild-Baukasten und Live-Darstellung in b10

Abschluss: **216 Python-Tests und 61 Browser-Prüfgruppen bestanden**, zusätzlich
Node-Prüfungen der vier Vorlagen und des Graphmodells. Python 3.14.7, Node 22.23.2,
Playwright 1.62.1 und ein isoliertes Headless-Edge-Profil wurden lokal verwendet.

Neun neue Python-Tests prüfen Anschlussgruppen, Medien-/Richtungszuordnung,
WMZ/Rückwege, Grenzen und Eingabefehler, Administratorrechte, revisionssicheres
Speichern, getrennte Entwürfe/Veröffentlichung sowie erhaltene Alt-Einstellungen.
Sechs zusätzliche Browser-Gruppen prüfen Erstellen, Verbinden, Import/Export,
Tastatur, Rückgängig/Wiederholen, DE/EN, stabile DOM-Knoten bei Live-Updates,
Fehlerfälle, Veröffentlichung und Rückkehr zur bestehenden Übersicht. Außerdem
werden die getrennte Präsentationsgrafik ohne Bearbeitungsports, Lüfterrückmeldung,
Animationspause, Offlineverhalten und die Mobilansicht geprüft. Die Geräte-Schreibliste
bleibt während aller Baukastenprüfungen leer. Ein Darstellungsfehler beim Ein-/Ausblenden
des Verbindungshinweises wurde durch feste Abschnittskennungen behoben.

Der Modelltest trennt PWT und Wendelkreise, prüft drei reine Vorlaufanschlüsse an
beiden Umschaltern, erzwingt den gemeinsamen Rücklauf über den WMZ und prüft die
Warmwasserzirkulation unabhängig von den Zapfabzweigen. Er prüft auch, dass ein
unbekannter Ventilzweig nicht animiert wird. Browser-Screenshots der DE-Liveansicht
und des DE/EN-Editors wurden visuell kontrolliert. Alle Werte sind Testdaten.
Kein Live-HA-Update und keine Heizungsänderung wurden ausgeführt.

## Allgemeine Anlagenprofile in b9

Abschluss: **207 Python-Tests und 55 Browser-Prüfgruppen bestanden**.

Vier zusätzliche Python-Prüfungen decken Heizgeräte im Vor-/Rücklauf ohne
Puffer, Übernahme älterer Einbauorte, alle Wärmeerzeugertypen mit allen
Versorgungszwecken unter externer Regelung und das Speichern durch ältere
b8-Clients ab. Eine zusätzliche Browser-Prüfgruppe kontrolliert unabhängige
externe Ausgänge ohne falsche R290-Gaswarnung, gezielte native Vorschläge und
den Erhalt der Einbauortauswahl beim Sprachwechsel und Speichern.

## Wärmeerzeuger in b8

Abschluss: **203 Python-Tests und 54 Browser-Prüfgruppen bestanden**.

Zusätzlich zu b7 prüfen sieben Python-Tests die Geräte-/Speicherzuordnung,
gültige Messquellen und Einheiten, fehlende Quellen, zugelassene Verlaufsentitäten,
das Erhalten von Einstellungen bei älteren Clients und Speichern ohne Stellbefehle.
Fünf zusätzliche Browser-Prüfgruppen decken die drei Gerätekarten, eindeutige
Signalvorschläge, P140-Gasmodus und mehrdeutige Relais, DE/EN-Entwürfe, anklickbare
Verläufe, veraltete/fehlende Rückmeldungen, getrennte Energiebilanzen sowie
Mobilansicht und Offlinezustand ab. Alle Daten sind lokal simuliert.

Es wurden keine realen Heizstäbe, Kessel oder WP-Ausgänge geschaltet. Die reale
Verdrahtung und Firmwarefunktion dieser Zusatzgeräte ist damit nicht nachgewiesen.

## Anlagenaufbau, Versionsregister und Service in b7

Abschluss: **196 Python-Tests und 49 Browser-Prüfgruppen bestanden**.

Lokale Regressionen mit simuliertem Modbus-Hub prüfen Anlagenvarianten,
Geräte-/Ventilzuordnung, Reglerbindungen, Versionslesen ohne Schreibbefehl,
Bestätigung und Wertebereiche, Stillstand, Fehler, Frostschutz, Mindestdurchfluss,
fremde Übersteuerungen, Rücklesefehler, Zeitende, Bit-Erhaltung, Wiederherstellung
der alten Vorgabe, Rücksetzpflicht nach Ausfall/Neustart und Schutz bei geänderter
Geräteadresse. Panel-Tests prüfen Administratorrechte, Servicefehler im Audit
sowie Sperren für Parameter, Kurven und Anlagenumbau.

Zusätzlich zu den bisherigen 42 Browser-Prüfgruppen gibt es sieben neue Gruppen:
Einzelgerät ohne Speicher, Kaskade mit WW, alle 18 Kombinationen aus Heizungs-
einbindung/Systemtrennung/WW-Anbindung, geschlossene Kugelhähne, bestätigte
elf Geräte mit gruppierten Recorder-Abfragen, Servicebedienung mit
seitenübergreifendem Stopp sowie DE/EN, Mobilansicht und
Lesefehler. Die Browser greifen ausschließlich auf lokale Beispieldaten zu.
SVG-Innenleitungen, Servicekarten und Anlagenschema werden per Screenshot geprüft.
Alle neun Seiten müssen auf einem 390-Pixel-Bildschirm ohne äußeren Überlauf passen.

Programme: `test_plant_service.py`, `test_panel_api.py`, `test_auxiliary_pump.py`,
`frontend-plant-service.mjs` und die bestehenden Tests. Echte Gerätefunktion,
Versorgungsausfall und HA-Neustart bei physischer Übersteuerung sind damit nicht
auf Hardware validiert. Kein Testkommando wurde an die Anlage geschickt und kein
Update installiert.

## Direkt schließbarer Wertedialog in b6

**42 Browser-Prüfgruppen bestanden** (39 Hauptprüfungen und drei Sprach-/Sensor-/
Diagnoseprüfungen), mit isoliertem Headless Edge und lokalen Testdaten.
Schema, Tastatur, Pumpenwerte, Messquellenauswahl und gesperrte Parameter senden
jetzt `hass-more-info` mit `view: info`. Der Messquellendialog wird vorher entfernt.
So öffnet sich die Standardansicht mit Wert und eingebettetem Verlauf statt der
Verlaufsunteransicht. Die getesteten Verlaufsklicks lösen keine Schreibbefehle aus.

Die Tests prüfen das ausgelöste HA-Ereignis, nicht den nativen HA-Dialog selbst.
Die Wahl der Standardansicht folgt dem offiziellen Frontend-Ereignishandler und
dem [HA-Dialog](https://github.com/home-assistant/frontend/blob/dev/src/dialogs/more-info/ha-more-info-dialog.ts).
Eine Installation oder Prüfung in der produktiven HA-Instanz erfolgte nicht.
Python-Fachlogik ist gegenüber b5 unverändert; deren 175 Tests wurden für diese
reine Änderung des Dialogaufrufs nicht erneut ausgeführt.

## Sensordekodierung und interne Pumpenanzeige in b5

**175 Python-Tests und 42 Browser-Prüfgruppen bestanden** (39 Hauptprüfungen
und drei Sprach-/Sensor-/Diagnoseprüfungen), mit Python 3.14 und isoliertem
Headless Edge. Die neue Pumpendarstellung wurde zusätzlich visuell geprüft.

Die acht neuen Python-Regressionen führen die tatsächliche Sensor-Klasse mit
isolierter HA-Basisklasse und den ausgelieferten Registerdefinitionen aus:
Vorzeichenwechsel um 0 °C, int16-Grenzen und Skalierungsreihenfolge, unveränderte
unsigned-/Bitfeldwerte, fehlende Werte und Wiederkehr. Für die Pumpenanzeige
werden 100→0 %, 35→65 % und 0→100 %, ungültige Rohwerte, getrennte Unique-IDs
und die Nutzung derselben Abfrage geprüft. Der Rohregistercache bleibt erhalten.

Die Browserprüfung deckt DE/EN-Bezeichnungen, getrennte Roh-/Prozentwerte,
korrekten Verlaufsaufruf und die überarbeitete P169-Erklärung ab. Gleiche Pumpen
werden trotz zwei unterschiedlicher Darstellungen nicht als unterschiedlich
markiert. Tatsächliche Unterschiede zwischen den Geräten bleiben erkennbar.

Die reale Anlage wurde dafür nur gelesen: P164 0/0, P165 3/3 K, P169 75/100 %,
P170 10/10 min, angezeigte Integration 1.5.0b4. Das bestätigt weder den genauen
Firmware-Erststartablauf noch die Rundung des P169-Verhältnisses. Keine
Geräteparameter, vorhandenen Historien oder produktiven Dateien wurden geändert.

## Pumpenfreigabe, Parameterhilfe und Verlauf in b4

**167 Python-Tests und 41 Browser-Prüfgruppen bestanden** (39 Hauptprüfungen
und zwei Sprach-/Diagnoseprüfungen). Python 3.14 und isoliertes Headless Edge,
ausschließlich lokale Testdaten. Zusätzlich wurden die Screenshots der Pumpen-
und Kurvenansicht visuell geprüft.

- Interne Pumpenfreigaben aus: sofortiger Stopp unabhängig von Nachlauf,
  Verdichterstatus, Abtauung oder fehlenden weiteren Messwerten.
- Unbekannte Freigabe: kein neuer Ausgangsbefehl, weder aus dem Stillstand
  noch aus einem bereits eingeschalteten Zustand.
- Wiederaufnahme expliziter Automatik nach Reload; Warten auf gültige Quellen;
  keine Übernahme aus älteren Logs, Beobachten, verriegelten Fehlern oder bei
  veränderten Steuerungsquellen. Konflikte und Ausgangsfehler bleiben getestet.
- Alle 263 Systemparameter enthalten DE/EN-Erklärungen. 210 ergänzte Hilfetexte
  sind adressgebunden und mit Handbuch/PDF-Seiten dokumentiert; Widersprüche
  und Reserven bleiben sichtbar. Sämtliche Defaults, Grenzen und Adressen
  stimmen weiterhin mit der unveränderten Excel-Datei überein.
- Verlaufsklicks im SVG per Maus und Tastatur, normalisierte Pumpenansteuerung,
  Auswahl mehrerer Messquellen, gesperrte Parameter und Rohregister-Sitzungsdaten.
  Die Tests bestätigen das HA-Verlaufsereignis und dass diese Klicks keine
  Schreibbefehle auslösen. Entwürfe, Scrollposition, Animation und Sprache bleiben
  erhalten; keine Browser-Laufzeitfehler in acht Ansichten auf Desktop und Mobil.

In b4/b5 wurde der Home-Assistant-Dialog über `hass-more-info` mit `view: history`
geöffnet. Ab b6 wird stattdessen `view: info` genutzt, damit die Ansicht mit dem X
direkt erscheint; siehe [offizieller Frontend-Ereignishandler](https://github.com/home-assistant/frontend/blob/dev/src/state/more-info-mixin.ts).
Der tatsächliche Recorder-Datenbestand, die Steuerung an echter Hardware und
der Wiederanlauf auf dem produktiven HA-Host wurden mit b4 noch nicht geprüft.
Die vorhandenen Handbücher ersetzen keine Freigabe für eine andere Gerätefirmware.

## Hydraulikanimation in b3

**156 Python-Tests und 37 Browser-Prüfgruppen bestanden** (35 Hauptprüfungen
und zwei Sprach-/Diagnoseprüfungen). Ausgeführt mit Python 3.14 und einem
isolierten Headless-Edge-Profil, ausschließlich gegen lokale Beispieldaten.
Python-Kompilierung und JSON-Dateien wurden ebenfalls geprüft.

Die neuen Browserfälle prüfen die tatsächlichen SVG-Pfadanschlüsse durch die
Warmwasserschlange, beide Seiten des Plattenwärmetauschers und die jeweiligen
Rückläufe. Getestet wurden zwei durchströmte Geräte, nur das zweite Gerät,
Umschaltung zwischen Warmwasser und Heizen, unabhängige Sekundärkreise,
Stillstand, Pause, veraltete/ungültige Signale und Verbindungsverlust. Ein
Zeitvergleich bestätigt laufende Flussanimation. Screenshots beider Betriebsarten
wurden visuell geprüft. Scrollposition, Formularentwürfe, DE/EN und Mobilansichten
sind Teil der Regressionen.

Backend-Prüfungen bestätigen die eindeutige Übernahme aktivierter COP-Signale,
den Umgang mit mehrdeutigen Zuordnungen, die zulässigen Entitätsdomains und
das Speichern der Anzeigequellen ohne Hardware-Schreibbefehle. Die Browserprüfung
deckt Auswahl und Speicherung der neuen Statusfelder ebenfalls ab.

Es gab keine Installation in Home Assistant, keine Geräteparameteränderung und
keine Verbindung zur Anlage. Transport- und Tagesmodellprüfungen wurden für
diese Änderung der Anzeige nicht wiederholt; deren früherer Stand folgt unten.

## Korrektur der Pumpeneinrichtung in b2

**154 Python-Tests bestanden** unter Python 3.14, einschließlich der vollständigen
bisherigen Regressionen. Zusätzlich wurden Python-Kompilierung, JSON-Dateien und
das Installationsarchiv auf Inhalt und Integrität geprüft.

Die neuen Prüfungen decken die vollständigen Vorschläge für zwei Slaves,
umbenannte Entitäten, unveränderte gespeicherte Zuordnungen, Übernahme eines
einzelnen alten Anforderungssignals sowie die gezielte Aktivierung früherer
Integrations-Defaults ab. Die tatsächlichen Sensordefinitionen werden auf
Registeradresse, Bit und Standardaktivierung geprüft. Kaskadenfälle umfassen
Umwälzung nur des zweiten Geräts bei stehendem Verdichter, unbekannte Signale,
Abtaupriorität und die Frischeanforderungen beider Statusregister je Slave.
Bewusst vom Benutzer deaktivierte Sensoren bleiben deaktiviert.

Für b2 wurden die folgenden Transport-, Browser- und Tagesmodellprüfungen nicht
erneut ausgeführt. Es gab keine Installation in Home Assistant und keine
Verbindung zur Anlage.

## Vorherige Validierung von b1

Ergebnis des vorherigen Stands: **143 Python-Tests, 12 Transporttests pro pymodbus-Version (24 Läufe)
und 33 Browser-Prüfgruppen bestanden.** Der simulierte Tageslauf erhielt alle
1.036 registrierten Werte. Bei einem zehnminütigen Ausfall von Slave 2 betrug
das höchste Alter der drei geprüften Regelungswerte von Slave 1 **10,348 s**.
Es gab maximal eine gleichzeitige Transaktion und keine Schreibvorgänge.

## Prüfumfang

- Python-Regressionen mit Home-Assistant-Doubles: bisherige Funktionen,
  Scheduler, Profilwechsel, additive Migration, Entladen, Verbraucherfrische,
  Verbindungswechsel, Warteschlangenbegrenzung, abgebrochene Schreibbefehle,
  fehlerhafte Adressen, Cachealterung und Verifikation.
- Lokaler TCP/RTU-Testserver mit echten pymodbus-Clients, jeweils **3.10.0** und
  **3.16.1**: Proxy-ID 1, Sockettrennung, beide Slaves, späte/falsche/fehlende
  Antworten, Readback nach verlorenem Schreib-Acknowledge und keine Blindwiederholung.
- 31 Browser-Prüfgruppen plus zwei Sprach-/Diagnose-Prüfgruppen in einem
  isolierten Headless-Chromium: alle Ansichten, DE/EN, Handybreite, Diagramme,
  Formularentwürfe, Schaltvorschau/-bestätigung, Scrollposition und Animation.
- Deterministische 24-Stunden-Simulation: zwei Slaves mit je 518 explizit
  registrierten Katalogadressen, simulierte Antwortdauer 25 ms + 1 ms/Register,
  zehn Minuten Ausfall eines Slaves, Regelungsfeedback mit maximal 30 s Alter.
  Der Simulator nimmt die Katalogadressen als lesbar an; das ist keine Aussage
  über die tatsächlich unterstützten Register der Wärmepumpen.
- ZIP-Inhalts- und Integritätsprüfung sowie SHA-256-Abgleich der ursprünglichen
  70 ursprünglichen Quell-, Test- und Dokumentationsdateien gegen `baseline-1.4.0.json`.

Die numerischen Ergebnisse des Tagesmodells stehen in
`artifacts/nextgen-simulation.json`. Fehlermeldungen bei absichtlich simulierten
Ausfällen in den Python-Tests sind erwartete Prüfausgaben.

## Reproduzieren

Python 3.12 wurde lokal verwendet. Für die reinen Unit-Tests werden keine
Home-Assistant-Installation und keine Modbus-Verbindung benötigt.

```powershell
python -m unittest discover -s tests -v
python -m pip install "pymodbus==3.16.1"
python tests/proxy_transport_checks.py
python tests/polling_simulation.py
```

Für den UI-Test Playwright in einer separaten Testumgebung installieren;
`PLAYWRIGHT_MODULE` kann auf den Paketordner zeigen. `CHROMIUM_EXECUTABLE`
verweist auf das Testbrowser-Binary. Es wird kein persönliches Browserprofil
geöffnet. Ohne eigene Pfade verwendet der Haupttest die Playwright-Installation.

Alternativ richtet `npm ci` die im Projekt fixierte Playwright-Version 1.62.1
ein; `npm run browser:install` lädt den zugehörigen Testbrowser.

```powershell
npm run test:ui
python scripts/build_release.py
```

Die CI-Konfiguration enthält Python-/Transporttests für beide pymodbus-Versionen,
die Simulation sowie Browserprüfungen. Ein CI-Lauf auf GitHub wurde hier nicht
ausgelöst. Der Quelltext ist noch nicht in einer vollständigen aktuellen
Home-Assistant-Instanz oder auf echter R290-Hardware validiert. Insbesondere
ersetzt der simulierte Tageslauf keinen 24-Stunden-Test am Gateway.
