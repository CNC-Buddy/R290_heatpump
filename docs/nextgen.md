# R290-NextGen · 1.1.1

Stand: 03.11.2026. Eigenständiger Entwicklungsordner auf Basis von 1.4.0.
Die Integration behält `r290_heatpump` als Domain. Sie ist ein Upgrade der
bestehenden Integration, keine parallel installierbare zweite Integration.

## Hausverbrauch berechnen b21 / Calculated house consumption b21

Unter **Einstellungen → Einrichtung → PV & Stromübersicht** das Feld
**Hausgesamtverbrauch** leer lassen und speichern. Dann berechnet die Anzeige:

**Haus = PV + Netzbezug + Batterieentladung − Einspeisung − Batterieladung.**

PV-, Netz- und Batterieleistung müssen zugeordnet, gültig und aktuell sein;
Netz-/Batterievorzeichen werden wie in Einrichtung gewählt ausgewertet. Bei
exakt 0 W spielt die Vorzeichenrichtung keine Rolle. Alle Leistungen werden
vorher aus W/kW/MW in kW umgerechnet. Batterie-Ladezustand und Wärmeerzeuger-
Teilzähler gehen nicht in die Rechnung ein. Beispiel: 0,85 kW PV + 3,18 kW
Netzbezug bei 0 kW Batterieleistung ergeben 4,03 kW Hausverbrauch.

„Berechnet“ kennzeichnet den abgeleiteten Wert. Die Flussanimation verwendet
denselben Wert. Ein Klick öffnet die vorhandenen Verläufe der drei Quellen;
es wird keine neue Recorder-Entität und kein eigener berechneter Verlauf
angelegt. Bei fehlenden/veralteten/ungültigen Werten, unbekannter Richtung
bei einem Wert ungleich null oder widersprüchlichen Eingaben bleibt der Hauswert
unverfügbar. Negative Ergebnisse werden nicht als positiver Verbrauch oder
als null angezeigt. Dieselbe Quelle mehrfach zuzuordnen wird nicht verrechnet.

Ein zugeordneter Haussensor hat immer Vorrang, auch wenn er vorübergehend
nicht verfügbar ist. Die Berechnung ist ausschließlich der Ersatz für ein
leeres Zuordnungsfeld, kein verdeckter Ausfallersatz. Ein nicht vorhandener
Batterie- oder PV-Messwert wird nicht stillschweigend als null angenommen.
Die Aktualitätsgrenze bleibt fünf Minuten seit der letzten HA-Meldung.

Leave **Settings → Setup → PV & electricity overview → Total house consumption**
empty and save to derive house power as **PV + grid import + battery discharge
− grid export − battery charge**. All three power sources must be assigned,
valid and current; selected sign conventions and W/kW/MW units are respected.
Zero power needs no direction. SOC and the heating submeter are excluded.
“Calculated” identifies the result; the animation uses it too. Clicking it
opens the source histories, without creating a new recorded entity or history.
Invalid/stale/missing sources, unknown nonzero direction, reused source IDs or
negative results produce an unavailable value. An assigned house sensor always
takes priority, including while unavailable. No device commands are involved.

## Kompakte Stromleiste b20 / Compact electricity strip b20

PV, Haus, Batteriespeicher und Netz stehen als größere Illustrationen in einer
zusammenhängenden Leiste ohne einzelne Kacheln. Die gemeinsame Leistung der
Wärmepumpen und Heizstäbe steht unter dem Hauswert als „davon Wärmeerzeuger“.
Alle Werte bleiben anklickbar. Die Zuordnungen in Einrichtung bleiben erhalten.
Goldene Leitungen mit wandernden Pfeilmarkierungen zeigen die gemessene Richtung;
kleine Tasten rechts oben pausieren die Animation oder öffnen Einrichtung.
Auf schmalen Ansichten werden die Komponenten umgebrochen und die Leitungen
neu verbunden. Keine offenen Enden, keine überlagerten Leitungsstrecken.

PV, house, battery and grid appear as larger illustrations in one continuous
strip without individual tiles. The common heat-pump/heater meter appears
below the house total as “of which heat generators”; values still open history.
Saved setup mappings remain unchanged. Golden lines carry moving chevrons in
the measured direction. Compact controls pause motion or open setup. Responsive
row layouts retain connected terminals and avoid overlapping wire sections.
Reduced motion, missing readings and data freshness continue to be respected.

## Gemeinsamer Heizungszähler und Energiefluss b19 / Shared heating meter and flow b19

Unter **Einstellungen → Einrichtung → PV & Stromübersicht → Wärmeerzeuger ·
gemeinsame Leistungsaufnahme** die Gesamtleistung des gemeinsamen Shelly für
Wärmepumpen und Heizstäbe wählen. Erfasst der Shelly mehrere Phasen, den bereits
summierten Leistungssensor verwenden. Die Einheit muss W, kW oder MW sein.
Ein Energiezähler in kWh gehört nicht in dieses Feld.

Seit b20 steht der Wert „davon Wärmeerzeuger“ direkt unter dem Hausverbrauch.
„Haus gesamt“ muss daher die Wärmeerzeuger bereits enthalten. Es findet keine
doppelte Addition statt; eine Aufteilung in Wärmepumpe und Heizstab wird aus
dem gemeinsamen Messwert nicht erfunden. Vorhandene Zuordnungen der bisherigen
Wärmepumpen-Leistungsquelle bleiben erhalten. Anklicken öffnet deren HA-Verlauf.

Alle Leitungen enden an den Komponenten oder einem verbundenen Abzweig. Die
Animation folgt der gemessenen Richtung. Für die Hauptleitung wird die Bilanz
von PV, Hausgesamtverbrauch, Batterie und Netz geprüft; bei unbekannten Quellen
oder einer Abweichung über max. 150 W bzw. 2,5 % der Summe der Leistungsbeträge
bleibt dort die Animation aus. Die Wärmeerzeuger werden nicht nochmals in diese
Bilanz aufgenommen. Abzweige mit gültiger Einzelmessung zeigen weiterhin ihre
Richtung. Nullwerte, ungültige/veraltete Messungen und eine getrennte Verbindung
lösen keine Flussanimation für die betreffende Quelle aus. Pause und reduzierte
Bewegung gelten für Hauptleitung und Abzweige. Die Verbindungen passen sich
auch in der mobilen Ansicht an die Anschlüsse an.

In **Settings → Setup → PV & electricity overview → Heat generators · shared
power meter**, select the Shelly's total instantaneous power for heat pumps and
immersion heaters. For multiple phases, use its already aggregated power sensor
in W/kW/MW. The whole-house source must include these heat generators. Their
reading appears beneath the house total, not as another consumer in the balance.
No device-level consumption is inferred from this shared meter. Existing power
assignments and native HA history remain available.

Every line terminates at a component or connected junction. Main-bus animation
uses the balance of PV, whole-house, battery and grid readings, excluding the
heating submeter to avoid double counting. Missing data or a mismatch exceeding
max. 150 W or 2.5% of summed power magnitudes suppresses main-bus animation;
individually valid branches keep their measured direction. Zero, invalid, stale
or disconnected readings do not animate. Pause/reduced-motion settings apply
to every line. Connections remain attached when the layout changes size.

## Stromübersicht b18 / Electrical overview b18

Unter **Einstellungen → Einrichtung → PV & Stromübersicht** die Anzeige ein- oder
ausschalten und Sensoren für PV-Leistung, gesamten Hausverbrauch, Batterieleistung,
Batterie-Ladezustand und Netzleistung zuordnen. Optional die gemeinsame Leistung der Wärmeerzeuger
als Teil des Hausverbrauchs anzeigen (siehe b19). Leistungsquellen brauchen W/kW/MW,
Ladezustand %. Die Einheiten werden für die Anzeige in kW umgerechnet; Zähler
in kWh sind keine Leistungsquellen. Alle Messwerte öffnen ihren HA-Verlauf.

Netz und Batterie verwenden je eine vorzeichenbehaftete Leistungsquelle.
Die Bedeutung positiver Werte wird separat gewählt; negative bedeuten die
Gegenrichtung. „Noch nicht festgelegt“ zeigt die Leistung ohne Richtungspfeil.
Fehlende, ungültige, wiederhergestellte oder über fünf Minuten alte Meldungen
zeigen keinen aktuellen Messwert/Fluss. Das Alter bezieht sich auf die
HA-Meldung (`last_reported`), nicht auf den letzten Wertwechsel. Bei getrenntem
HA bleiben ebenfalls alle Flussanimationen aus. Reduzierte Bewegung und die
Animation-Pause werden unterstützt. Das Ausschalten löscht keine Zuordnungen.

Beim Integrationsstart werden bisherige PV-/Batterie-/Haus-/Netzknoten samt
elektrischen Verteilknoten und angeschlossenen Leitungen aus Entwurf und
veröffentlichtem Schaubild entfernt. Eindeutige bestehende Bindungen werden
vorgelegt; konkurrierende Bindungen werden nicht geraten. Bestehende neue
Stromeinstellungen werden nicht überschrieben. Die ursprünglichen Graphen
liegen im vorhandenen Panel-Speicher unter `schematic.electric_backup` als
Wiederherstellungssicherung. Der Schaubild-Revisionszähler verhindert, dass
ein bereits offener Editor die Übernahme unbemerkt überschreibt. Alte JSON-
Schaubildimporte werden beim Speichern ebenfalls übernommen. Eine rein
elektrische veröffentlichte Altzeichnung fällt auf das normale Hydraulikschema
zurück. Heizstäbe und ihre Speicherposition bleiben Bestandteil des Schaubilds.

**Settings → Setup → PV & electricity overview** enables the separate section
above the hydraulic schematic. Assign instantaneous PV, total house, signed
battery and signed grid power; battery SOC uses %. An optional shared heat-generator power
sensor appears as a share of house consumption (see b19). Choose the positive direction
for battery and grid explicitly. Unknown directions never produce arrows.
Readings use W/kW/MW, are shown in kW and open native HA history. Missing, invalid,
restored, disconnected or stale (over five minutes since the last HA report)
readings do not imply live flow. Reduced-motion and pause are supported.
Disabling the section preserves its saved assignments.

Legacy electrical nodes and wires migrate out of the hydraulic graph; unique
bindings are prefilled. Original graphs are retained in
`schematic.electric_backup`, and revision checks protect open editors. Existing
new electrical settings take precedence. Hydraulic geometry and mounted heaters
remain unchanged. Old JSON imports migrate on save. No device service is called.

## Schaubildeditor b17 / Schematic editor b17

„Bauteil hinzufügen“ öffnet eine Vorschau. Position per Klick/Tippen wählen;
alternativ Pfeiltasten und Enter. Abbrechen oder Esc ändert den Entwurf nicht.
Gespeicherte automatische Leitungswege bleiben bestehen, solange ihre Anschlüsse
unverändert sind. Neue Hindernisse verschieben keine fremden Leitungen; gewünschte
Umwege über die Leitungsgriffe oder „Automatisch neu führen“ anpassen. Manuelle
Leitungswege bleiben wie bisher erhalten. Die Zeichenfläche wächst bei Bedarf,
ohne vorhandene Bauteile neu zu skalieren. Rückgängig/Wiederholen erfasst die
gesamte Änderung einschließlich Leitungswegen und angebauter Heizstäbe.

“Add component” opens a preview. Click/tap to place, or use arrow keys and Enter.
Cancel/Esc leaves the draft untouched. Automatic routes are retained while their
endpoints stay unchanged; unrelated components no longer reroute existing pipes.
Use the pipe handles or “Reroute automatically” for intentional detours. Manual
waypoints remain supported. The canvas grows without rescaling existing objects.
Undo/redo includes route geometry and mounted heaters.

Elektrische Bauteile bieten nur passende Messquellen: Leistung für Netz/PV/Haus,
Leistung plus Ladezustand für Batterien, Leistung plus Betriebsrückmeldung für
Heizstäbe. Leistungsfelder filtern auf W/kW/MW, Ladezustand auf %. Bestehende
Zuordnungen werden nicht gelöscht. Alte hydraulische Zuordnungen elektrischer
Bauteile erscheinen weder im Editor noch im Live-Schaubild. Vorzeichen bleiben
die der Messquelle; keine automatische Umdeutung von Bezug/Einspeisung.

Electrical components offer relevant sources only: power for grid/PV/home,
power and state of charge for batteries, power and operating feedback for
heaters. Power fields filter W/kW/MW and charge fields %. Existing mappings are
preserved; legacy hydraulic readings on electrical components are hidden in
both editor and live view. Signed power keeps the source sensor's convention.

Keine Änderung an Geräteparametern oder Regelungsfunktionen. Das optionale
`route`-Feld speichert automatisch erzeugte Leitungsgeometrie; `points` bleibt
für manuelle Wege. Beide werden serverseitig geprüft. Bestehende Schaubilder
ohne `route` werden unverändert gelesen und beim nächsten Speichern ergänzt.
No changes to device parameters or control functions. The optional `route`
field stores automatic geometry; `points` retains manual waypoints. Both are
validated server-side. Existing graphs without `route` remain supported.

## Tabellenüberlauf b16 / Table overflow b16

Unsichtbare Beschriftungen in langen Parameterlisten vergrößerten den äußeren
Scrollbereich über den Seitenhintergrund hinaus. Der Tabellencontainer begrenzt
nun auch diese absolut positionierten Hilfstexte. Alle Zeilen bleiben innerhalb
der Tabelle erreichbar. Keine Regelungs- oder Geräteparameteränderung.

Screen-reader labels in long parameter lists could extend the outer scroll area
beyond the page background. Their positioning is now contained by the table's
own scroll wrapper. All rows remain accessible. No control or device parameter
behaviour changed.

## Darstellungskorrekturen b15 / Display corrections b15

Der Schaubild-Host ist transparent; Werkzeugleisten übernehmen den Hintergrund
von Seite bzw. Karte. Schaltflächen und Zeichenfläche behalten ihre eigenen
Flächen. Die Panelwurzel füllt mindestens die dynamische Bildschirmhöhe, auch
wenn Home Assistants umgebendes Custom-Panel seine Höhe aus dem Inhalt berechnet.

The schematic host is transparent, so toolbars share the page/card surface.
Buttons and the drawing canvas retain their own surfaces. The panel root fills
at least the dynamic viewport height even with HA's auto-height custom wrapper.

Das lokale Integrations-Icon wurde am 02.11.2026 in HA 2026.10.4 im integrierten
Browser korrekt angezeigt. Bei einem alten Platzhalter hilft das Neuladen der
Integrationsseite (Strg+F5); die acht Bilddateien sind unverändert enthalten.
The local integration icon was observed working in HA 2026.10.4 on 2026-11-02.
Reload the integrations page if an old placeholder persists. All eight brand
assets are unchanged. No live installation or device setting was performed.

## Display-Theme / Display theme

Die Oberfläche nutzt ein dunkles Marineblau/Cyan-Theme nach dem Originaldisplay.
Große Messwerte, helle Nebenbeschriftungen und dünne Diagrammlinien erleichtern
das Ablesen. Es gilt durchgehend für die Seiten, Dialoge, Kurven und beide
Schaubildansichten. Warnungen bleiben gelb, Fehler rot und bestätigte Zustände
grün. Bestehende Diagrammkonfigurationen und Anlagenzuordnungen bleiben erhalten.

The interface uses a dark navy/cyan theme inspired by the original display.
Prominent readings, high-contrast secondary text and thin chart lines improve
readability across pages, dialogs, curves and both schematic views. Warnings
remain amber, errors red and confirmed states green. Existing chart preferences
and plant mappings are retained. The complete source version is packaged as the
local 1.5.0b23 beta ZIP; it had not been deployed to Home Assistant at the time of that test.

Das Kreislauf-Symbol und der Schriftzug **R290 NextGen** ersetzen die bisherige
R290/Home-Assistant-Beschriftung rechts in der Kopfleiste. Die Darstellung ist
skalierbar und funktioniert ohne externe Bild- oder Schriftabfragen. Für die
Home-Assistant-Integrationsansicht werden transparente PNGs für helle und dunkle
Hintergründe einschließlich @2x-Versionen mitgeliefert. Lokale Markenbilder werden
ab Home Assistant 2026.3 unterstützt. Domain, Entity-IDs und Konfigurationszuordnungen
werden nicht geändert. Die HA-Seitenleiste heißt ebenfalls R290 NextGen.

The circulation emblem and **R290 NextGen** wordmark replace the previous
R290/Home Assistant label at the right of the header. Scalable artwork requires
no external image or font requests. Transparent light/dark PNGs, including @2x
versions, are provided for Home Assistant's integration page. Local brand images
are supported from Home Assistant 2026.3. The domain, entity IDs and configuration
mappings are retained. The HA sidebar entry is also named R290 NextGen.

Ab b13 stehen ausgewählte Messquellen beim Öffnen der Diagrammkonfiguration
vor den übrigen Quellen. Beide Gruppen sind alphabetisch sortiert.
From b13, selected chart sources appear first when opening chart settings;
both groups are sorted alphabetically.

## Heizkurven-Prognose

Die Heizkörper-, Fußbodenheiz- und Kühlkurve zeigen zusätzlich eine Prognose der jeweils anderen Wassertemperatur. Grundlage sind die Basiskurve und die Einstellungen P116 und P099 des Masters (Slave 1): Bei Rücklaufregelung wird P099 zum Kurvensoll addiert, bei Vorlaufregelung abgezogen. In der Kühlkurve gilt die umgekehrte Richtung: Der Vorlauf liegt unter dem Rücklauf. P099 beschreibt die Zielspreizung, nicht die Wiedereinschalt-Hysterese. Entwürfe wirken auf die Vorschau; PV-Offsets und Sollwertglättung werden nicht eingerechnet. Fehlen P116 oder P099, bleibt die Prognose leer. Die Darstellung ändert keine Geräteparameter.

## Betriebsdaten und Parameter ab b14 / Operating data and parameters

Enthalten im lokalen Beta-Installationspaket 1.5.0b23 vom 03.11.2026.
**Betriebsdaten** ersetzt Betrieb und Energie. Oben stehen Stromverbrauch,
Wärmeertrag, Wärme/Strom-Zählerverhältnis und erkannte Verdichterstarts. Darunter
liegen Temperaturverlauf, Betriebsphasen je Gerät, elektrische Leistung,
Zusatzpumpenenergie, Frequenzen/Laufzeiten sowie Datenqualität. Der Zeitraum ist
rollierend, kein Kalendertag. „Laufzeit / Start“ enthält angeschnittene Zyklen und
ist deshalb keine mittlere Dauer vollständiger Takte.

**24 Stunden / 7 Tage / 30 Tage** synchronisiert Kennzahlen und die drei Diagramme
für die aktuelle Sitzung. Das Zahnrad speichert weiterhin je Diagramm einen eigenen
Zeitraum und die Quellen; eine neue Zahnrad-Einstellung hebt für dieses Diagramm
die vorübergehende gemeinsame Zeitwahl auf. Jeder Verlauf und die Phasenleiste
zeigen ihren Zeitraum. Bestehende Diagrammkonfigurationen werden weiterverwendet;
alte Links zu `#operation` und `#analysis` öffnen Betriebsdaten.

Phasen stammen aus aufgezeichneten Verdichter-, Abtau- und Warmwassersignalen.
Fehlende oder ungültige Signale bleiben unbekannt. „Heizen“ bezeichnet den
Nicht-Warmwasserbetrieb; Abtauen wird separat gezeigt. Die Phasenleiste belegt
keine genaue Energieaufteilung. Verzögerte WM-Bus-Zähler, fehlende Zeitgrenzen
oder unterschiedliche Bilanzgrenzen erlauben weiterhin keine gesicherte getrennte
Arbeitszahl. Frequenz-/Statusverläufe behalten höchstens 6000 Zustandswechsel pro
Quelle; weiter zurückliegende, nicht mehr enthaltene Phasen bleiben unbekannt.

**Service → Maschineninfo** enthält die bisherigen Main Parameter. Alle 255
Katalogzeilen in Main, Realtime, User und User 2 haben deutsche und englische
Bezeichnungen und Erklärungen, Bitfelder zusätzlich lokalisierte Bitbezeichnungen.
Unbekannte Register werden nicht erfunden; widersprüchliche Dokumentation und
fehlende Entitätszuordnungen bleiben sichtbar. Die Texte ergänzen die vorhandene
Registerdokumentation, ohne Adressen, Skalierungen, Defaults oder Gerätewerte zu ändern.

**Service → Systemparameter → Mit P183 entsperren** fordert das aktuelle Passwort
an. Ein einzelnes Gerät oder alle zugeordneten Wärmepumpen können ausgewählt werden.
Bei unterschiedlichem Passwort die Geräte einzeln freigeben. Die Freigabe gilt
zehn Minuten pro Gerät, Administrator und WebSocket-Verbindung. Sie lässt sich mit
**Jetzt sperren** aufheben. Ein Verbindungsabbruch beendet sie ebenfalls.

Der Server liest dazu **P183 / 0x01B7** direkt vom Gerät und vergleicht den Wert
bei jedem Systemparameter-Schreibaufruf erneut. Unlesbarer Wert, falsches Passwort,
Ablauf oder geändertes P183 verweigern den Schreibaufruf. Es wird kein Default als
Passwort angenommen. Auch bei P183=0 ist ausdrücklich 0 einzugeben; damit gilt
in diesem Panel die gewünschte Eingabesperre unabhängig von der geräteinternen
Bedeutung „Passwort deaktiviert“. Fünf Versuche pro Minute und Administrator sind
zulässig. Lesen bleibt frei; Passwortwerte werden im Panel-Änderungsprotokoll
maskiert. Nach einer Änderung von P183 erlischt die Freigabe.

Die Sperre schützt die **Schreibschnittstelle dieser Oberfläche** vor versehentlichen
Änderungen. Sie ersetzt keine HA-Berechtigungen und sperrt weder native
HA-Administratordienste noch vorhandene Automationen oder Herstellerbedienteile.
Werkstestmodus und Heizkurven behalten ihre eigenen Bestätigungsabläufe.

EN: **Operating data** combines energy KPIs, compact histories, per-unit phases,
cascade runtime comparisons and data quality. The shared 24-hour / 7-day / 30-day
selector temporarily synchronizes the three charts; each chart's gear retains
persistent source/period settings. Old links remain valid. Phase gaps stay unknown;
delayed meters do not establish precise heating/DHW energy allocation.
**Service → Machine information** contains the former Main Parameter group. All
255 Main/Realtime/User/User 2 rows have DE/EN names and explanations; undocumented
registers remain explicitly undocumented.

**Service → System parameters → Unlock with P183** verifies the live device
password, per unit and connection for ten minutes, with a live recheck before each
write. Wrong/changed/unreadable passwords, expiry and disconnect prevent writes.
Even P183=0 requires entering 0. Password updates are masked in the audit and revoke
the grant. This gate protects this panel's write endpoint; native HA administrator
services, existing automations and manufacturer controls are outside its scope.
No installation archive or live deployment has been made for this development step.

## Diagramme und Navigation / Charts and navigation

Die Hauptleiste enthält **Anlage, Betriebsdaten, Parameter, Service und
Einstellungen**. Unter Einstellungen liegen Einrichtung, Schaubild und Zusatzpumpe.
Unter Service liegen Geräteinfo, Maschineninfo, Werkstestmodus, Diagnose, Fehlerspeicher und
Systemparameter. „Alle Entitäten“ ist entfernt; die fünf Parametergruppen bleiben
über Parameter bzw. Service zugänglich. Bisherige direkte Abschnittslinks bleiben
verwendbar.

In Verlaufsdiagrammen zeigt der Zeiger Zeitpunkt und Werte der eingeblendeten
Reihen. Unbekannte Werte erscheinen als —. Die Anzeige folgt dem gezeichneten
Zustandsverlauf, ohne Zwischenwerte zu erfinden. Recorder-Daten werden weiterhin
begrenzt ausgedünnt, wobei Ausschläge und Datenlücken erhalten bleiben. Legenden
sind anklickbar; bei ausgeblendeten Reihen ändern sich auch Skala und Tooltip.
Die vier Basiskurven zeigen beim Zeigen Außen-/Solltemperatur; ihre gespeicherte
Kurve und ein vorhandener Entwurf lassen sich ebenfalls ausblenden.

Über **⚙ oben rechts** am Verlaufsdiagramm lassen sich **6, 12 oder 24 Stunden
sowie 2, 7 oder 30 Tage** und **1–24 vorhandene Sensoren passender Einheit** wählen.
Namen oder Entitäts-ID im Suchfeld filtern. **Bestätigen** speichert die Auswahl
zentral in Home Assistant, auch über Neustarts und Browserwechsel hinweg.
Die Einstellung gilt je Diagramm; die Legenden-Schaltung ist vorübergehend.
Temperaturdiagramme rechnen °F/K in °C um; Leistungsdiagramme kW in W.
Gleichzeitige Änderungen werden erkannt statt überschrieben. Gerätewerte und
Regelung werden dadurch nicht verändert. In Betriebsdaten kann die gemeinsame Zeitwahl die individuellen Diagrammzeiträume
vorübergehend übersteuern; siehe oben.

EN: Five main pages, with **Settings → Setup / Schematic / Auxiliary pump** and
**Service → Device information / Machine information / Factory test mode / Diagnostics / Fault history /
System parameters**. Hover over charts for readings; click legend entries to
show/hide series. **⚙** on history charts saves the period and 1–24 compatible
sensor sources in Home Assistant. Changes persist across restarts and browsers;
legend toggles are temporary. Curve previews use outdoor temperature rather than
time, and therefore have no history-period settings.

## Speicher und Leitungen ab b12 / Tanks and pipes

Unter **Einstellungen → Schaubild** einen Speicher auswählen und **Temperaturfühler**
auf 1–4 setzen. Jedem Fühler eine Entität und seine Höhe zuweisen: 5–95 % von oben,
mindestens 8 Prozentpunkte Abstand, aufsteigend. 0 stellt die bisherige Einzelwert-
anzeige wieder her. Die Farben veranschaulichen Messpunkte, keine berechnete
Speicherladung. Fehlende/veraltete Temperaturen sind grau und als — erkennbar.
In der veröffentlichten Ansicht öffnet ein Temperaturwert den HA-Verlauf; unter
dem Schaubild erscheint außerdem ein konfigurierbarer Verlauf der Speicherfühler.
Neben dem Speicher Platz für die Anzeigen lassen; der Baukasten ordnet andere
Bauteile nicht eigenmächtig um.

Heizstab hinzufügen, im Feld **Einbau im Speicher** einen Speicher wählen und den
Heizstab auf die gewünschte Höhe ziehen. Beim Verschieben des Speichers bewegt
sich der Heizstab mit. **Frei platzieren** löst diese Zuordnung. Der Einbau ist
Darstellung und erzeugt weder einen hydraulischen Anschluss noch eine Schaltlogik.

Eine Leitung anklicken und einen quadratischen Griff quer zur Leitung ziehen.
Die Anschlüsse bleiben verbunden. Pfeiltasten verschieben den fokussierten Griff
in 10er-Schritten; Rückgängig/Wiederholen und Escape bei laufendem Ziehen sind
verfügbar. Manuelle Wege bleiben beim Bewegen/Spiegeln von Bauteilen erhalten;
**Automatisch neu führen** entfernt die Vorgabe. Die automatische Führung bevorzugt
wenige rechtwinklige Bögen. Bei überlappenden Bauteilen kann weiterhin ein manuelles
Nachführen nötig sein. Offene Speicheranschlüsse enden kurz hinter der Wand,
getrennt von den Wendelanschlüssen.

EN: Select a tank and choose 1–4 temperature sensors with heights measured from the
top. Missing/stale readings remain explicit. Add a heater and choose **Mount in
tank**, then drag it vertically; it follows tank movement. Select a pipe and drag
its square handles (or use arrow keys). Endpoints remain attached; manual routes
survive component movement. **Reroute automatically** resets the route.

## Variable Kurven ab b11 / Variable curves

Unter **Parameter → Heizkörper / Warmwasser / Fußbodenheizung / Kühlung → Basis**
zuerst die Bearbeitung freigeben. Vorhandene Zweipunktkurven erscheinen mit ihren
bisherigen Endpunktfeldern. **+ Stützpunkt hinzufügen** fügt einen Punkt in das
größte freie Außentemperaturintervall ein und öffnet die Punktetabelle. Der neue
Sollwert liegt, auf 0,1 °C gerundet, auf dem bisherigen Kurvenabschnitt.

- Jede Kurve hat 2 bis 10 Punkte; Außen- und Solltemperatur sind in 0,1-°C-Schritten
  editierbar. Die Außentemperaturen müssen eindeutig von kalt nach warm ansteigen.
- Punkte im Diagramm ziehen oder nach Tab-Fokussierung mit den Pfeiltasten bewegen
  (0,1 °C, mit Umschalt 1 °C). Escape bricht eine laufende Ziehbewegung ab.
- Das × entfernt einen Punkt, solange mindestens zwei Punkte übrig bleiben.
  Auch eine gespeicherte Punktetabelle mit zwei Punkten bleibt editierbar.
- Die gestrichelte Linie zeigt den Entwurf neben der gespeicherten Basiskurve.
  **Änderung prüfen → Bestätigen** übernimmt die gesamte Kurve gemeinsam.
  **Verwerfen** verwirft nur den aktuellen Kurvenentwurf. Die vier Kurven haben
  getrennte Entwürfe, die Live-Updates und Sprachwechsel überstehen.
- Zwischen Punkten wird linear interpoliert, außerhalb gelten die Endwerte.
  Es gibt keine automatische Richtungsumkehr für die Kühlkurve und keine
  überschwingende Spline-Glättung. Zeitliche Sollwertglättung bleibt separat.

Die Punktetabelle verwendet den Außenbereich −30 bis +35 °C und den Bereich der
vorhandenen Sollwertregister −20 bis +80 °C. Das sind technische Eingabegrenzen,
keine Empfehlungen für die Anlage. PV- und externe Anhebung werden nach der
Basiskurve und ihrer zeitlichen Glättung addiert. Der fertige Sollwert wird auf
die Registergrenzen und gegebenenfalls engere Min-/Max-Attribute der zugehörigen
Sollwertentität begrenzt und auf ganze °C gerundet. Weitere interne Geräteparameter
können die reale Temperatur zusätzlich begrenzen. Die Basiskurvenvorschau zeigt
diese nachgeschalteten Änderungen nicht.

Die Einstellung **Mindeständerung** wird ab b11 tatsächlich beim Senden angewandt.
Geänderte PV-/externe Offsets dürfen diese Schwelle umgehen; identische gerundete
Registerwerte werden nicht erneut gesendet. Bei aktiver Regelung zeigt der Sensor
den zuletzt erfolgreich gesendeten gerundeten Sollwert, keine gemessene Temperatur.
Attribute dokumentieren Punkte, Begrenzung und Schreibfehler. Das Lesen der
Attribute verändert die zeitliche Glättung nicht mehr.

**Kompatibilität:** Ohne `curve_points` wird die bisherige Zweipunktkurve verwendet;
es gibt keine automatische Aktivierung oder Migration der Punkteliste. Beim Speichern
werden Punkte und bisherige Endpunktoptionen in einem Schritt aktualisiert. Die
alten vier Endpunkt-Entitäten bleiben erhalten; bei einer Mehrpunktkurve ändern sie
nur den ersten/letzten Punkt. Ein Überkreuzen mit Zwischenpunkten wird abgewiesen.
Format: `[{"outdoor": -15, "target": 50}, ...]`.

**Ausfallverhalten:** Fehlende oder ungültige Außentemperaturen führen zu keinem
neuen Sollwert. Ungültige gespeicherte Punkte fallen nicht still auf eine
Standardkurve zurück. Fehlgeschlagene Schreibversuche werden bei der nächsten
Auswertung wiederholt; bis dahin bleibt der Kurvensensor nicht verfügbar. Bei
HA-/Kommunikationsausfall wird keine interne Gerätekurve automatisch aktiviert.
Das Gerät arbeitet mit seiner zuletzt angenommenen Vorgabe und eigenen Regelung
weiter, soweit seine Firmware dies vorsieht. Hardware-Verhalten bei Neustart und
unverändert gültig aussehende, aber eingefrorene Sensordaten sind damit nicht
abgesichert. Home Assistant muss für die Nachführung laufen.

EN: Under **Parameters → curve → Base**, unlock editing and choose **+ Add control
point**. Use 2–10 points, numeric fields, dragging or arrow keys (Shift: 1 °C).
The dashed draft is applied only after review and confirmation. Each curve has an
independent draft. Linear interpolation and end-value clamping are shared by all
four curve types; PV/external offsets and time smoothing remain separate. Existing
two-point curves keep their values and entity IDs. Legacy endpoint entities edit
only the first/last point. Invalid readings stop new commands; failed writes retry
on the next evaluation. Home Assistant downtime does not automatically switch the
device to an internal weather curve. The UI is available in German and English.

## Schaubild-Baukasten ab b10 / Schematic editor

**Einstellungen → Schaubild** oder **Einstellungen → Einrichtung → Baukasten öffnen**:

1. Eine Vorlage laden oder mit leerer Zeichenfläche beginnen.
2. Bauteile hinzufügen, verschieben, spiegeln und benennen. Pfeiltasten verschieben
   das gewählte Bauteil; Entf entfernt es einschließlich seiner Leitungen.
3. Zwei passende Anschlüsse anklicken. Für Abzweige ein T-Stück verwenden.
   Bei Verbindungen zwischen T-Stücken zuerst die stromaufwärts liegende Seite
   wählen. Kreuzende Linien verbinden sich nicht automatisch.
4. Im Bauteil Messquellen suchen oder die Entitäts-ID einfügen. Vorschläge stammen
   aus den eingerichteten Geräten und Anzeigezuordnungen. Fehlende Quellen bleiben
   unbekannt. Der Baukasten unterstützt maximal 80 Bauteile und 160 Leitungen.
5. **Entwurf speichern** bewahrt auch unvollständige Pläne, ohne die Übersicht zu
   ändern. **Speichern & anzeigen** verlangt vollständige Anschlussgruppen und
   geschlossene Kreise für Pumpen und Wärmeerzeuger. Der Plan erscheint anschließend
   unter **Anlage**, mit detaillierteren Bauteilen, ohne Raster und Bearbeitungsports.

EN: Open **Settings → Schematic**, load a template, move components, connect their typed ports
and assign readings. **Save draft** keeps the current overview. **Save & display**
uses the completed graph in the live overview with presentation graphics.

Leitungen lassen sich auswählen und über Griffe führen. **Automatisch neu führen**
entfernt manuelle Vorgaben. Verschieben oder Spiegeln eines Bauteils passt die
Endverbindungen an und erhält manuelle Wege. Zoom, Rückgängig/Wiederholen sowie JSON-Export und
-Import stehen bereit. Auf kleinen Bildschirmen lässt sich die Zeichenfläche
horizontal verschieben; Zoom vergrößert auch die Live-Ansicht. **Bisheriges Schema
anzeigen** entfernt nur die veröffentlichte Zeichnung; der gespeicherte Entwurf
bleibt erhalten. Gleichzeitige Bearbeitungen werden über eine Revision geprüft.
Speichern ist Administratoren vorbehalten. Konfiguration wird in Home Assistants
vorhandenem Panel-Speicher gespeichert und bleibt bei einem Neustart erhalten.

Die vollständige Vorlage bildet einen gemeinsamen WP-Vorlauf mit Zusatzpumpe und
einem 3/2-Ventil ab. Das Ventil hat genau drei **Vorlauf**anschlüsse. Der WW-Wendel-
und PWT-Primärrücklauf vereinigen sich **vor dem WMZ** auf dem Weg zu den WPs.
Primär- und Sekundärseite des Plattenwärmetauschers sind unabhängige Anschlussgruppen.
Zwischen PWT und Puffer sowie zwischen Puffer und Heizkreis liegen eigene Pumpen.
Der zweite Wärmeerzeuger hat einen eigenen Vorlauf-Umschalter und getrennte
Wendeln in beiden Speichern; seine Rückläufe gehen direkt zum Erzeuger zurück.
Violett und Indigo unterscheiden seinen Vor- und Rücklauf. Die Warmwasserleitung
führt an den abzweigenden Zapfstellen vorbei und schließt über einen eigenen
Zirkulationsrücklauf mit Pumpe zum Speicher. Damit bleibt der Zirkulationsweg
auch bei geschlossenen Zapfstellen vollständig.

**Live-Rückmeldungen:** Fluss wird nur auf geschlossenen Wegen animiert, wenn die
zugehörigen Pumpen-/Durchflusssignale dies bestätigen. Die Verdichterfrequenz allein
ist keine Pumpenrückmeldung. Für Umschalter gilt eine eindeutige Quelle: an/1/WW
führt zu A, aus/0/Heizen zu B. Unbekannte Ventilzustände animieren keinen geratenen
Zweig. Lüfter verwenden eine separate Drehzahl-/Statusquelle. Aktuelle numerische
Rückmeldungen dürfen höchstens 180 Sekunden alt sein. Externe boolesche Quellen
können bis zur nächsten Zustandsänderung unverändert bleiben; deren Integration
muss einen Ausfall als unavailable melden. Offline und bei pausierter Animation
bewegen sich keine Symbole. Werte öffnen den üblichen HA-Verlaufsdialog.

**Umfang:** Der Editor konfiguriert ausschließlich die Anzeige. Er verändert weder
Modbus-Parameter noch Ausgänge oder die vorhandene Pumpenregelung. Die Angaben unter
Anlagenaufbau und im Regler bleiben eigenständig. Die Prüfung findet fehlerhafte
Anschlusstypen, doppelte Portbelegung und fehlende Rückwege; sie ist keine hydraulische
Auslegung. Der Bauteilkatalog enthält fest definierte Kreise und Anschlüsse; weitere
Spezialbauteile müssen als zusätzliche Typen ergänzt werden. PV, Batterie, Netz und
Hausverbrauch können mit Messwerten dargestellt werden. Elektrische Energieflüsse
werden noch nicht aus Vorzeichen oder Verbrauchsbilanzen animiert. Heizstäbe sind
als elektrische Bauteile verfügbar; der Editor ersetzt keine Heizstab-Regelung.
Unbenutzte Speicherwendel sind als mögliche Anschlüsse sichtbar, müssen aber nicht
belegt werden. Komponentenpositionen der Vorlage sind anpassbar; Namen und Farben
ersetzen keine Prüfung der tatsächlichen Leitungsführung.

## Allgemeine Anlagenprofile ab b9

Die Zusatzwärmeerzeuger sind optionale Funktionen für unterschiedliche Anlagen.
Die Entwicklung setzt keine installierten Heizstäbe oder Kessel am Referenzstandort
voraus. Geräteart, Versorgungszweck, Einbauort, Messquellen und bestehende
Regelungszuständigkeit werden bei der jeweiligen Installation eingerichtet.

Die **elektrische Zusatzheizung der Heizung** kann im Puffer, Heizungsvorlauf oder
Heizungsrücklauf liegen. Ein Puffer wird nur für den Einbauort „Im Heizungspuffer“
verlangt. Vor- und Rücklaufvarianten sind auch in direkten Heizkreisen verfügbar.
Der bisherige Schlüssel `buffer_heater` bleibt für die Übernahme älterer
Konfigurationen bestehen; ohne neuen Einbauort gilt weiterhin „Puffer“. Speichert
ein älterer b8-Client erneut, bleibt ein bereits gewählter Einbauort erhalten.

**Externe Regelung:** Schalter und Rückmeldungen können unabhängig von R290
zugeordnet werden. Ein R290-Eintrag ist dafür nicht erforderlich; optional kann
er Quellentemperaturen oder Ladepumpensignale liefern. Ausgangsvorschläge werden
nur bei „Wärmepumpensteuerung“ eingesetzt. Hinweise zu P139/P140 und zugehörige
Steuerparameter erscheinen nur für native Regelung bzw. tatsächlich zugeordnete
R290-Anforderungsausgänge. Ein unabhängiger elektrischer Heizstab wird dadurch
nicht mit einem Gasmodus einer anderen Steuerung vermischt.

Die allgemeine Konfiguration ersetzt keine automatische Regellogik: Diese Version
enthält weiterhin Zuordnung, Anzeige und Auswertung. Eine spätere Automatik muss
ihre Anschlüsse und Betriebsgrenzen pro Installation bekommen. Solche Angaben
sind Anforderungen an die Inbetriebnahme beim Nutzer, keine Voraussetzung dafür,
die Integration allgemein weiterzuentwickeln.

**English:** The heating auxiliary heater supports buffer, supply and return
placement. Supply/return heaters also work in direct heating circuits. Existing
b8 buffer assignments are preserved. External controllers do not require a
controlling R290 unit. Native output suggestions and gas-mode warnings only
apply to native control or explicitly mapped R290 requests. Installation-specific
bindings belong to each user's setup; development is independent of the
reference installation. No new switching automation is included.

## Heizstäbe und zweiter Wärmeerzeuger ab b8

Unter **Einrichtung → Heizstäbe & zweiter Wärmeerzeuger** können drei optionale
Geräte zugeordnet werden: WW-Heizstab, Puffer-Heizstab und zusätzliche Wärmequelle.
Für die zusätzliche Quelle sind Gas, Öl, Pellets, Holz/Kamin, Solarthermie,
Fernwärme und Sonstiges mit Versorgung von Heizung, WW oder beiden wählbar.
Ein aktiviertes Kontrollkästchen bedeutet „eingebaut / anzeigen“, keine Freigabe.
Die bestehenden Einstellungen bleiben beim Update erhalten; die Geräte sind
ohne ausdrückliche Zuordnung ausgeblendet.

Je Gerät werden bestehende Ansteuerung (WP / extern / unbekannt), zuständige WP,
Anforderung, unabhängige Rückmeldung, elektrische Leistung, kumulierte Strom-
und Wärmezähler zugeordnet. Beim zweiten Wärmeerzeuger kommen Quellentemperaturen
und Ladepumpen für beide Speicher hinzu. Der Puffer-Heizstab setzt einen Puffer,
WW-Versorgung einen WW-Speicher im Anlagenaufbau voraus. Bei einer Kaskade wird
die zuständige Steuerung explizit ausgewählt. Die vorhandenen Entity-Picker
unterstützen Tippen und Einfügen von Entity-IDs.

**R290-Signalvorschläge:** Nur eindeutig passende, bereits aktivierte Entitäten
der ausgewählten WP werden auf Wunsch in leere Felder übernommen. Bestehende
Zuordnungen werden nicht überschrieben. P140 muss für den EH1-Vorschlag als 0
vorliegen; Gasmodus, unbekannter Modus oder mehrere mögliche Heizungsrelais
führen zu keiner automatischen Auswahl. Deaktivierte Diagnose-Entitäten müssen
bei Bedarf zuerst in HA aktiviert werden. Die Auswahl bestätigt keine Verdrahtung.

**Anlagenübersicht:** Separate Karten ordnen die Heizstäbe ihren Speichern und
die zusätzliche Quelle ihrem Versorgungszweck zu. Ein Reglerausgang wird als
„angefordert“, nicht als bestätigter Betrieb dargestellt. Eine zugeordnete,
aber ausgefallene Rückmeldung bleibt unbekannt. Dasselbe Signal als Anforderung
und Rückmeldung ist keine unabhängige Bestätigung. Ohne Rückmeldung kann eine
gültige Leistungsmessung nur „Leistungsaufnahme“ belegen; Hilfsstrom eines
Kessels beweist keinen Brennerbetrieb. Die Wärmesymbole reagieren auf verfügbare
Rückmeldung/Leistung, nicht auf unbestätigte Anforderung. Pausieren und reduzierte
Bewegung werden berücksichtigt. Zusätzliche hydraulische Fließwege werden ohne
bestätigte Verrohrung nicht erfunden. Alle zugeordneten Werte sind anklickbar.

**Energie:** Zählerzuwächse stehen getrennt in der Energieansicht. Strom-Messgrenzen
„bereits enthalten“, „separat“ und „unbekannt“ verhindern eine stillschweigende
Summierung. Es gibt weder eine automatische Addition zur Anlagenbilanz noch einen
COP für Verbrennungsgeräte. Brennstoffverbrauch wird in dieser Version nicht
umgerechnet. Wärme wird nicht aus Nennleistung oder Relaislaufzeit geschätzt.
Fehlende Zähler liefern keine erfundenen Nullwerte. Recorder-Abfragen bleiben auf
zugeordnete Entitäten und höchstens 24 Entitäten je Anfrage beschränkt.

**Belegte Basis:** `main.py` enthält die Relaisbits für WW-Elektroheizung,
Heizungs-/Fußboden-Zusatzheizung, Gasfreigabe sowie WW-/Heizungs-Ladepumpe einer
Zusatzquelle. Die Quellentemperaturen 0x0072/0x0073 sind ebenfalls vorhanden.
Grundlage: Modbus protocol V1.2.9, PDF-Seiten 7, 14–15 und 20–21; ARDEN Service
Manual, PDF-Seiten 45–49, Abschnitte 3.1.11–3.1.18. P139/P140 konfigurieren die
Art/Freigabe der Zusatzheizung; P151–P154 betreffen Hysterese und obere
Temperaturen kombinierter Wärmequellen. Diese Parameter sind keine direkten
Ein-/Aus-Befehle. Das Handbuch beschreibt bei P139/P140 = 2 eine Verwendung
von EH1 als Gasfreigabe. Ein Puffereinbau folgt nicht allein aus dem Namen EH2;
der Hardwareanschluss muss geprüft sein. Widersprüchliche Detailangaben des
Handbuchs werden nicht als zusätzliche Regelalgorithmen übernommen.

**Umfang:** Anzeige, Zuordnung und Auswertung sind implementiert. Es existiert
kein neuer Schreibendpunkt, kein Heizstab-/Kessel-Test und keine automatische
Ansteuerung dieser Geräte. Für die spätere Inbetriebnahme einer Regelung werden
pro Installation Gerätetyp, Anschlüsse, Schaltzuständigkeit, unabhängige
Temperaturbegrenzung und gewünschter Einsatz (Zusatzbetrieb, Reserve, PV)
konfiguriert. Diese Angaben werden nicht vorab vom Referenzstandort benötigt. Die vorhandene
Wärmepumpen- und Zusatzpumpenregelung wird dadurch nicht verändert.

## Immersion heaters and additional heat source (b8)

**Setup → Immersion heaters & additional heat source** maps optional DHW and
buffer immersion heaters plus a further heat source. Choose the responsible
unit explicitly in a cascade. Installed/display is a presentation setting,
not a heating enable. Native suggestions use unambiguous enabled entities and
leave existing mappings untouched. Check actual wiring, especially EH1 reuse
as a gas request and the physical location of EH2.

The overview distinguishes requests, independent feedback and electrical power.
Missing feedback stays unknown. All mapped readings link to their history.
Separate meter increments appear under Energy, without automatic summation or
combustion-appliance COP. Missing meters are not treated as zero. No new switching
automation or actuator endpoint is included. Each installation will configure its
equipment, wiring, control ownership and hardware temperature limits when
commissioning future control; these details do not block general development.

## Anlagenaufbau und Service ab b7

**Einrichtung → Anlagenaufbau** beschreibt die tatsächliche Hydraulik:

- Einzelgerät oder parallele Kaskade mit 2–11 ausgewählten Geräten.
- Direkter Heizkreis, Parallelpuffer oder Reihenpuffer im Rücklauf; zusätzliche
  Systemtrennung über Plattenwärmetauscher wählbar.
- Kein Warmwasser, interner Speicherwärmetauscher oder externer Plattenwärmetauscher.
- Keine Zusatzpumpe, gemeinsame Pumpe im Vor-/Rücklauf oder Pumpe im Heizungszweig.
- Heizkörper, Fußbodenheizung oder gemischte Wärmeabgabe.
- Keine Absperrventile, an interne Pumpen gekoppelte Kugelhähne oder eigene
  Offen-Rückmeldungen. Pumpenstatus ist kein Beleg für eine gemessene Ventilposition.

Die Auswahl wird als `settings.plant` gespeichert. Speichern verändert keine
Geräteregister und keine bestehenden Sensorlisten. Bei einem laufenden Regler
oder einem offenen Servicetest wird eine Änderung des Aufbaus abgelehnt.
Alte Konfigurationen behalten zunächst das bisherige Schema; die Vorgabe muss
unter Einrichtung geprüft werden. Entfernte/deaktivierte Geräte und unpassende
Reglerzuordnungen werden als Fehler angezeigt. Ältere Clients überschreiben die
neue Konfiguration nicht.

Die explizite Reglerzuordnung verlangt dieselben Geräte in derselben Reihenfolge
für Frequenz, Durchfluss, Vorlauf und Rücklauf. Neue Zusatzpumpeneinträge erhalten
Vorschläge aus der ausgewählten Anlage. Die automatische Regelung unterstützt
gemeinsame Pumpen im Vor- oder Rücklauf. Eine reine Heizungszweigpumpe ist
darstellbar, ihre Automatik ist hier nicht freigegeben. Bestehende Einträge werden
nicht automatisch umverdrahtet. Die Geräte-Kaskadenregelung (P-Parameter) bleibt
eine gesonderte Einstellung.

Das Schema verwendet aktuelle Durchfluss-/Statuswerte. Eine geschlossene
Ventilrückmeldung sperrt die Animation dieses Zweiges. Getrennte Lade- und
Heizkreise benötigen eigene Pumpenstatusquellen; bei fehlenden Quellen wird keine
Bewegung erfunden. Für den WW-Ladekreis am externen Wärmetauscher gibt es eine
zusätzliche Statuszuordnung. Bei vielen Geräten wächst das Schema; mobil lässt
es sich innerhalb seiner Karte horizontal bewegen. Recorder-Anfragen großer
Kaskaden werden in Gruppen bis 24 Entitäten aufgeteilt.

**Service → Geräteinfo und Testwerte lesen** liest pro Gerät dokumentierte
Register ohne Teststart. Die Anzeige enthält Abfragezeit und einzelne Lesefehler.
Es findet kein permanenter zusätzlicher Versionsscan statt.

| Funktion | Register | Interpretation |
| --- | --- | --- |
| Hauptplatinenprogramm | `0x0360` | Rohwert / 100; 425 → 4.25, mit Display abgleichen |
| Produkttyp / Typkennung | `0x0361` / `0x0362` | Rohwerte, keine geratene Modellzuordnung |
| Protokollversion | `0x0363` | Rohwert; Unterversionen nicht geraten |
| Display-/Controllerfirmware | nicht belegt | Keine Gleichsetzung mit Hauptplatine |
| Verdichter 1 | `0x0332`, Freigabe `0x0331` Bit 0 | 0–120 Hz |
| EEV 1 | `0x0336`, Freigabe `0x0331` Bit 1 | 0–500 Schritte |
| EVI 1 | `0x033A`, Freigabe `0x0331` Bit 2 | 0–500 Schritte |
| Lüfter | `0x033E`, Freigabe `0x0331` Bit 3 | 0–80 Hz, nicht mit gemessenen rpm verwechseln |
| Interne Wasserpumpe | `0x0344`, Modus `0x0343` | 0–100 Protokollwert; Wirkrichtung nicht bestätigt |

Grundlage: `Modbus_protocol_V1.2.9.pdf`, Seiten 25–27; gleichlautende Tabellen im
Hainzel Engineering Manual, Seiten 182–184. Das ARDEN Service Manual beschreibt
das lokale Factory-Menü auf Seite 73. Die fünf abgeglichenen Excel-Tabellen enthalten
diesen Service-/Versionsbereich nicht vollständig. Interner Verdichter 2 bzw.
EEV/EVI 2 eines Doppelsystem-Geräts ist nicht die zweite Wärmepumpe der Kaskade.
Die Serviceoberfläche verwendet System 1 des ausgewählten Slaves.
PFC, Evakuierung, Kältemittelrückgewinnung, Werksreset und IPLV werden nicht angeboten.
Für IPLV fehlt insbesondere die eindeutige Fernsteuerungszuordnung.

Komponententests sind für beaufsichtigte Arbeiten vor Ort vorgesehen. Das Gerät
muss ausgeschaltet und der Verdichter im Stillstand sein; alle Zusatzpumpenregler
müssen auf Beobachten stehen. Fehler, Frostschutz/Abtauung, andere Testfunktionen
oder bestehende Übersteuerungen verhindern den Start. Ein Verdichtertest verlangt
mindestens 15 L/min gemeldeten Durchfluss; dies ersetzt nicht die Prüfung der
tatsächlichen Mindestmenge und Einsatzgrenzen des Geräts. Ein Test gleichzeitig,
15–120 Sekunden, Vorschau und ausdrückliche Bestätigung. Die Integration schaltet
die Anlage nicht selbst aus und sperrt keine fremden Automationen.

Vor dem ersten Schreiben wird die Rücksetzinformation gespeichert. Der Test
schreibt die Vorgabe, setzt das Freigabebit und liest beide zurück. Stopp, Zeitende,
Fehler oder erneuter Normalbetrieb lösen die Rücksetzung aus: eigene Freigabe
entfernen, ursprüngliche Vorgabe wiederherstellen und Rückmeldung prüfen. Fremde
Bits bleiben erhalten. Adresse und Programmversion dürfen sich während des Tests
nicht ändern. Nach HA-Neustart wird ein offener Test als ungeklärte Rücksetzung
angezeigt; weitere Tests, Panel-Parameteränderungen und Reglerfreigaben bleiben
gesperrt. Der Beenden-Knopf ist auf allen Panel-Seiten erreichbar.

**Grenze:** Bei Strom-/HA-/Verbindungsausfall kann die Software eine Rücksetzung
nicht garantieren. Es gibt keinen belegten Hardware-Timeout. Vor Ort bleiben,
nötigenfalls am Display beenden und anschließend die Rücksetzung erneut prüfen
lassen. Readback bestätigt Registerwerte, keine mechanische Funktion. Die
Servicebefehle wurden noch nicht an der Anlage getestet; ein antwortendes
Versionsregister ist keine Herstellerfreigabe.

### English quick guide

Use **Setup → Plant configuration** for single unit/cascade, participating devices,
heating/DHW plumbing, pump location and isolation valves. Saving changes the panel
configuration only. Hardware cascade parameters remain separate. Assign the
controller explicitly; its ordered sensor bindings must match the selected units.
Automatic control supports common supply/return pumps; heating-branch-only pumps
are display-only in this release.

Use **Service → Read device info and test values** for mainboard version and raw
product/protocol IDs. No display-firmware register is documented. Component tests
require device-off/standstill, no faults or competing overrides, observer mode for
auxiliary controllers, a preview and on-site supervision. Tests last 15–120 seconds
with readback and durable recovery records. Stop remains available across panel
pages. After a restart or failed release, resolve recovery before another test.
Changed device/firmware identity blocks restoration to a potentially different
target. No device-side timeout is proven: HA, power or network failure may require
stopping at the device. This is locally tested software, not hardware validation.

## Was umgesetzt ist

- Sensordekodierung ab b5: `int16` wird vor Skalierung/Offset interpretiert;
  Bitfelder und der gemeinsame Rohregistercache bleiben unverändert.
  Zeitweise 65535 bei Temperatur entspricht bei Skala 1 dem zuvor falsch
  dargestellten −1 °C. Bereits gespeicherte Ausreißer werden nicht bereinigt.
- Interne Pumpen: **Pump speed** zeigt die Ansteuerung als `100 − PWM` in %.
  Standard-Entitätsnamen sind `sensor.r290_heatpump_pump_speed_slave_1` und
  `sensor.r290_heatpump_pump_speed_slave_2`; HA kann bei Namenskonflikten andere
  IDs vergeben. Die Unique-IDs sind neu, damit die Historie getrennt bleibt.
  **Pump speed PWM** bleibt unverändert skaliert als Diagnose verfügbar.
  Ungültige Rohwerte außerhalb 0–100 ergeben keine erfundene 0/100-%-Anzeige.
  Beide Anzeigen nutzen dieselbe Registerabfrage, ohne zusätzlichen Busverkehr.
- Zusatzpumpe: Die interne Pumpenfreigabe bestimmt, ob überhaupt ein Stellbefehl
  zum Lauf zulässig ist. Eindeutig aus bedeutet Stopp, unbekannt bedeutet keine
  neue Ansteuerung. Eine gespeicherte explizite Betriebsfreigabe übersteht Reloads;
  Quellenwechsel und verriegelte Fehler erfordern eine neue Freigabe. Details und
  die Grenzen bei ausgeschaltetem HA stehen in `auxiliary-pump.md`.
- Parameterhilfe: 205 zuvor fehlende Erklärungen ergänzt und acht vorhandene
  erweitert bzw. berichtigt. Alle 263 Systemparameter enthalten DE/EN-Hilfetexte.
  Von den 213 Ergänzungen sind 84 dokumentiert, 122 nur teilweise beschrieben,
  sechs widersprüchlich und eine reserviert. Die Texte benennen diese Grenzen;
  Defaults, Bereiche und Geräteeinstellungen wurden nicht geändert.
  P168/P169 begrenzen laut Kaskadenkapitel die Anzahl startender Geräte; 100 %
  ist keine Empfehlung zur Effizienzoptimierung. P170 ist ein Zeitparameter für
  die Zuschaltung. Rundung auf ganze Geräte und Ablauf beim Erststart sind nicht
  ausreichend beschrieben; 50 % kann das zweite Gerät begrenzen statt verzögern.
- Verlaufszugriff: Ein Klick auf einen aktuellen Entitätswert öffnet ab b6 Home
  Assistants Standarddialog mit Wert und Verlauf, direkt über das X schließbar.
  Dies funktioniert auch im Schema, mobil und ohne Freigabe der
  Parameterbearbeitung. Der Stift dient separat zum Ändern. Abgeleitete Werte
  verweisen auf ihre Messquellen. Rohregister ohne Entität zeigen empfangene
  Sitzungsmessungen; Defaults und Vorschauwerte sind keine Recorder-Messungen.
  Zwei zusätzliche Sensoren zeichnen die tatsächliche prozentuale Ansteuerung
  und die Zielspreizung auf. Ihre Historie beginnt erst nach Installation.
- Hydraulikanimation: vollständige Pfade einschließlich Warmwasserschlange,
  beider Seiten des Plattenwärmetauschers und zweigabhängiger Rückläufe.
  Unter **Einrichtung** können Warmwasserladung, Pufferladepumpe und
  Heizkreispumpe als reine Anzeigesignale zugeordnet werden. Eine eindeutige
  aktivierte COP-Warmwasserzuordnung dient automatisch als Quelle, auch ohne
  Zusatzpumpenregler. Fehlende oder ungültige Signale werden nicht geraten.
- Zusatzpumpen-Einrichtung: Pumpen- und Abtausignale aller Kaskadengeräte werden
  automatisch vorgeschlagen. Beide Listen verwenden eine ODER-Verknüpfung mit
  Erkennung unbekannter Zustände; ein manueller gemeinsamer Helfer entfällt.
  Die beiden vorhandenen Statussensoren werden standardmäßig aktiviert, auch
  bei bisheriger Deaktivierung durch die Integration. Bewusste Deaktivierungen
  durch den Benutzer und gespeicherte Zuordnungen bleiben erhalten.
  Einzelheiten stehen in [Zusatzpumpenregelung](auxiliary-pump.md).
- Ein gemeinsamer Scheduler je Bridge für alle zugeordneten Geräte und Kurven.
  Hintergrundabfragen, direkte Leseaufrufe, Live-Diagnose und Schreibbefehle
  verwenden im Auto-Profil denselben Scheduler und dieselbe Transportsperre.
- Ein gemeinsamer Cache je Slave/Register. Mehrere Verbraucher bestellen
  dieselbe Messung; das kürzeste angeforderte Intervall gewinnt. Identische
  wartende Leseaufträge werden zusammengefasst.
- Nur ausdrücklich angeforderte, unmittelbar benachbarte Register werden zu
  Blöcken zusammengefasst. Unbekannte Lücken werden nicht automatisch mitgelesen.
  Die bei der Untersuchung gefundenen Wortpaare E5/E6 und EC/ED bleiben zusammen,
  wenn beide Wörter angefordert sind. Das ist keine bestätigte Bedeutungszuordnung.
- Vier Prioritätsgruppen, Alterung wartender Aufträge und Wechsel zwischen
  Slaves verhindern dauerhaftes Verdrängen langsamer Abfragen. Anforderungen
  der Zusatzpumpenregelung und Kurven können Datenalter und Intervall verschärfen.
- Transportdauer bestimmt die Pause bis zum nächsten normalen Auftrag. Fehler
  verursachen einen gerätebezogenen Wiederanlaufabstand von 2 bis 120 Sekunden
  und langsamere Konfigurationsabfragen. Nach stabilen Antworten erfolgt
  schrittweise Erholung. Das ist eine konservative Anpassung an gemessene
  Laufzeiten und Fehler, keine automatische Geräte- oder Firmwareerkennung.
- Modbus-Ausnahme 02 verkleinert Leseblöcke. Einzelne nicht unterstützte Register
  beziehungsweise zusammengehörige Wortpaare werden fünf Minuten ausgesetzt.
  Ein Timeout allein löst keine binäre Zerlegung der Adressbereiche aus.
- Schreibbefehle werden einmal ausgeführt und unmittelbar zurückgelesen, bevor
  der nächste Scheduler-Auftrag beginnt. Eine verlorene Schreibantwort wird
  nicht durch einen zweiten Schreibversuch beantwortet. Erfolgreiches Readback
  bestätigt den gelesenen Sollwert; es beweist keine physische Wirkung am Gerät.
- Höchstens 128 wartende direkte Aufträge. Reguläre Aufträge verfallen nach
  30 Sekunden, Diagnoseaufträge nach 120 Sekunden. Ein abgebrochener, noch
  wartender Schreibauftrag wird entfernt. Bereits begonnene Schreibvorgänge
  werden einschließlich Readback abgeschlossen.
- Entladen entfernt Verbraucher und deren wartende Aufträge. Profilwechsel
  laden betroffene Einträge neu; Verbindungswechsel und Reconnect warten einen
  laufenden Schreib-/Readback-Auftrag ab. Anschließend sind neue Messungen nötig.
- Ein neuer Bridge-Eintrag mit demselben normalisierten Host und Port wird
  abgewiesen. Bestehende doppelte Bridges können Auto nicht aktivieren.
  DNS-Aliase, unterschiedliche Gateways am selben RS485-Bus und andere
  Modbus-Master können damit nicht automatisch erkannt werden.
- Metriken im DE/EN-Panel unter **Diagnose** und sechs zusätzliche
  Bridge-Diagnosesensoren: Transaktionen, Fehler, Antwortzeit P95,
  Transportzeitanteil, wartende Aufträge und überfällige Register.
  JSON-Diagnoseexporte enthalten Version und Kommunikationszustand.
- Alle bisherigen Funktionen bleiben Bestandteil des Projekts: vier Kurven,
  COP/PV, Zusatzpumpenregelung, kompletter Registerkatalog, Fehlerspeicher,
  Live-Registerdiagnose, animiertes Schema und Scrollpositionserhalt.

## Profile und Einstellungen

**Legacy bleibt bei Migration und neuen Bridge-Einträgen vorausgewählt.**
Vorhandene `scan_interval`/`long_scan_interval`-Werte, beispielsweise 30/600 s,
werden nicht ersetzt. Im Legacy-Profil bleiben die bisherigen Batch-Coordinatoren
aktiv. Die neuen Scheduler-Funktionen einschließlich Readback gelten für Auto.
Transportmetriken stehen in beiden Profilen zur Verfügung.

| Auto-Einstellung | Vorgabe | Zulässiger Bereich |
| --- | ---: | ---: |
| Schnell | 10 s | 5–60 s |
| Normal | 30 s | 5–300 s |
| Langsam | 120 s | 30–1.800 s |
| Konfiguration | 600 s | 60–86.400 s |
| Transportzeitbudget | 0,60 | 0,10–0,90 |

Es muss schnell ≤ normal ≤ langsam ≤ Konfiguration gelten. Das Budget 0,60
bedeutet 60 %. Es berücksichtigt auch Netzwerk- und Gatewaywartezeiten und
misst nicht die elektrische Auslastung der RS485-Leitung. Benutzeraufträge zum
Schreiben einschließlich Readback sind von der normalen Wartepause ausgenommen.

Die Profilintervalle sind Obergrenzen für die normale Einplanung. Ein bereits
kürzeres Geräteintervall bleibt maßgeblich. Deshalb kann etwa eine bisher alle
30 Sekunden angeforderte Außentemperatur auch mit dem langsamen 120-s-Profil
weiter alle 30 Sekunden gelesen werden. Unter Fehlern werden langsame Gruppen
begrenzt zurückgenommen; kritische Altersgrenzen werden nicht verlängert.

Ein zeitlich unveränderter Messwert ist nach einer erfolgreichen Antwort frisch.
Ein gecachter Wert wird durch UI-Refresh oder die Antwort eines anderen Registers
nicht künstlich frisch. Bei Fehler oder zu hohem Alter meldet die Integration
den betroffenen Sensor als nicht verfügbar. Die bisherige Pumpenregelung kann
dadurch ihre vorhandenen Fehler- und Ersatzwertregeln anwenden.

## Installation und Profilwechsel

1. Vorhandenen Integrationsordner und Home-Assistant-Konfiguration sichern.
2. Aus dem GitHub-Release-Quellarchiv den enthaltenen Ordner
   `custom_components/r290_heatpump` in das HA-Konfigurationsverzeichnis kopieren.
   Die bestehende Integration nicht löschen oder als neues Gerät neu anlegen.
3. Home Assistant neu starten. Die Versionsanzeige im Panel muss v1.1.1 zeigen.
   Ein Hard-Reload aktualisiert gegebenenfalls noch geöffnete Browserseiten.
4. Die Integration startet mit dem gespeicherten Profil; bei Erst-Migration
   zunächst mit Legacy. Unter **Einstellungen → Geräte & Dienste → R290 NextGen
   → Modbus Bridge → Konfigurieren** kann später Auto ausgewählt werden.
5. **Service → Diagnose → Kommunikation** zeigt das tatsächlich aktive Profil, Kennzahlen
   und Geräte. Der Profilwechsel selbst schaltet keine Wärmepumpe und aktiviert
   keine Zusatzpumpenregelung.
6. Beim ersten Upgrade von b3 oder älter die Zusatzpumpen-Betriebsart prüfen:
   Diese Versionen haben noch keine dauerhafte Freigabe gespeichert. Beobachten
   schaltet einen bereits eingeschalteten Ausgang nicht aus. Nach bewusster
   Übernahme in Automatik wird diese Freigabe künftig wiederhergestellt, sofern
   Stellglied/Quellen unverändert und die Eingangssignale verwendbar sind.

Rückkehr zur bisherigen Abfragestrategie: In denselben Bridge-Optionen Legacy
wählen. Die ursprünglichen Geräteintervalle sind erhalten. Für einen vollständigen
Versionsrückbau die gesicherte Integration und bei Bedarf die zugehörige
HA-Sicherung verwenden; das neue `polling`-Verzeichnis gehört nicht zu 1.4.0.

Diese Arbeit hat weder das Paket in Home Assistant installiert noch Auto auf
der realen Anlage aktiviert. Es wurden keine Geräteparameter oder Firmware geändert.

## Aufbau

| Datei/Modul | Aufgabe |
| --- | --- |
| `polling/models.py` | Aufträge, Cacheeinträge, Anforderungen, Fehlertypen |
| `polling/profiles.py` | Profilvalidierung, Prioritäten, sichere Blockbildung |
| `polling/scheduler.py` | Warteschlange, Planung, Fehlerbehandlung, Readback |
| `polling/batch.py` | Kompatible Anbindung der bestehenden Entitäten |
| `polling/consumers.py` | Zusätzliche Aktualitätsanforderungen der Regelung |
| `polling/metrics.py`, `entities.py` | Transportmessungen und HA-Sensoren |
| `connection.py`, `hub.py` | Gemeinsame Verbindung, Profile, unveränderte Protokollmodi |
| `frontend/bus-health.js` | Kommunikationsübersicht in DE/EN |

`tcp_proxy` behält pro Modbus-Transaktion einen neuen Client und Socket,
Transaktions-ID 1 und deaktivierte Protokollwiederholungen. Ein gemeinsamer
Scheduler bedeutet in diesem Modus bewusst keinen dauerhaft geöffneten Socket.
Direktes TCP und RTU-over-TCP behalten ihre vorhandenen Verbindungsstrategien.

## Noch offen

- Ein mehrtägiger Betrieb in einer echten Home-Assistant-Installation und am
  tatsächlichen Gateway: Start/Reload, RTT, Datenalter, Abtauung, Warmwasser,
  Gatewayausfall und Zusammenspiel mit der Pumpenregelung.
- Eine Messung des Vorher/Nachher-Verkehrs mit den tatsächlich aktivierten
  Entitäten. Die Simulation ist kein Nachweis einer Einsparung an der Anlage.
- Verlässliche Modell-/Firmwareprofile und Bedeutungen unbekannter Register.
  Aus der analysierten 4.4.3-Firmware werden weder eine Kompatibilitätsfreigabe
  für die installierte 4.25 noch neue schreibbare Parameter abgeleitet.
- Eine belastbare Geräteentscheidung zur Laufzeitverteilung der Kaskade.
  Der Scheduler verteilt Kommunikationsaufträge, nicht die Verdichterlaufzeiten.

Das Paket ist deshalb als Beta gekennzeichnet. Die lokale Validierung und ihre
Grenzen stehen in [validation.md](validation.md).


### Sichtbarkeit in der Seitenleiste

In den Optionen der ersten Modbus-Bridge lassen sich R290 NextGen und das
R290-Lovelace-Dashboard getrennt in der Seitenleiste anzeigen oder ausblenden.
Die Einstellung gilt für die gesamte Integration und bleibt nach einem Neustart
erhalten. URLs, Funktionen und das gespeicherte Lovelace-Layout bleiben erhalten.
Die separate Aktion „Lovelace-Dashboard neu erstellen“ ersetzt das Layout durch
die mitgelieferte Vorlage. Home-Assistant- oder benutzerspezifische
Seitenleisten-Einstellungen können die Anzeige ebenfalls beeinflussen.
