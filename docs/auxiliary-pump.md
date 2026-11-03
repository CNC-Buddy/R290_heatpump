# R290 Anlagensteuerung und Zusatzpumpenregelung · 1.5.0b3

Die Integration enthält eine eigene Oberfläche unter `/r290-control` und einen
optionalen Konfigurationseintrag **Auxiliary Pump Controller**. Beide sind
vollständig lokal. Die Regelung läuft in Home Assistant unabhängig davon, ob
die Oberfläche geöffnet ist. Der Pumpeneintrag eröffnet keine Modbus-Verbindung;
er benutzt die zugeordneten Home-Assistant-Entitäten.

Ab 1.3.1 schlägt die Einrichtung vorhandene, aktivierte R290-Entitäten vor.
Die Identifizierung erfolgt über Integrationseintrag und Unique-ID; umbenannte
Entity-IDs funktionieren weiterhin. Frequenz, Volumenstrom, Vorlauf und Rücklauf
werden nach Slave-Nummer in derselben Reihenfolge vorbelegt. Fehlt eine Quelle,
bleibt deren komplette Liste offen, statt einzelne Geräte stillschweigend
auszulassen. Auch die Pumpen- und Abtaulisten werden nur vollständig vorgeschlagen.

Ab 1.5.0b2 sind die vorhandenen Statussensoren **Relay output status 1 · Main
engine circulating water pump status** (Holding-Register `0x0019`, Bit 6) und
**Running Status 1 · System defrost status** (`0x0000`, Bit 8) standardmäßig für
jeden Slave aktiviert. Beim Laden der Sensorplattform werden frühere
Deaktivierungen durch die Integration für genau diese beiden Sensoren aufgehoben.
Deaktivierungen durch den Benutzer bleiben erhalten. Es werden keine neuen
Alias-Entitäten angelegt und keine Geräteparameter geschrieben.

Speicher- und Außentemperaturen stammen bevorzugt von Slave 1. Explizite
Anzeigezuordnungen aus dem Dashboard haben Vorrang; geeignete kumulierte Zähler
und ein konfiguriertes binäres WW-Splitsignal können aus dem COP-Eintrag stammen.
Momentane Leistung wird nicht als Energiezähler übernommen. Bei mehreren
uneindeutigen Anlagen bleiben neue Zuordnungen offen. Das Stellglied, die separate
Freigabe und bisherige Automationen werden nicht aus Namen erraten. Bei einer
Kaskade werden die Pumpenstatussensoren aller Geräte als Umwälzanforderungen
vorgeschlagen und im Regler mit ODER verknüpft. Ein manueller Template-Helfer ist
nicht erforderlich. Gleiches gilt für die Abtausignale: Ein aktives Signal genügt.
Nur wenn alle ausgewählten Signale aus sind, ergibt sich sicher aus. Aus zusammen
mit einem unbekannten Signal bleibt unbekannt und führt zum Ersatzbetrieb statt
zum Abschalten. Umwälzung ohne Verdichter bleibt damit berücksichtigt.

Eine bisher gespeicherte einzelne Anforderungsentität bleibt als Liste mit einem
Eintrag erhalten; beispielsweise ein bereits vorhandener gemeinsamer Helfer.
Gespeicherte Auswahlwerte werden nicht stillschweigend um weitere Geräte ergänzt.
Im Auto-Abfrageprofil werden auch die beiden Statusregister aller ausgewählten
Slaves mit den Frischeanforderungen der Pumpenregelung angemeldet.

In den Optionen haben gespeicherte Zuordnungen Vorrang, auch absichtlich leere
Felder und eine manuell gewählte Reihenfolge. Bei nicht zuordenbaren eigenen
Sensorlisten werden keine fremden R290-Spalten ergänzt. Vorbelegungen sind
bearbeitbare Formularvorschläge; geleerte optionale Felder werden beim Speichern
nicht durch Schema-Defaults wieder eingesetzt. Öffnen und Ausfüllen des Formulars
sendet keine Stellbefehle. Die Hinweise sind auf Deutsch und Englisch vorhanden.

## Oberfläche

| Bereich | Funktionen |
| --- | --- |
| Anlage | Gezeichnete Hydraulik, Speicher, Pumpenkarte, 24-Stunden-Temperaturverläufe, aktuelle Werte und Datenqualität |
| Zusatzpumpe | Beobachten, fester Stellwert und Automatik; Vorschlag, Begründung, Grenzen, Konflikte und Ereignisprotokoll |
| Betrieb | Temperatur- und Frequenzverläufe, Gerätevergleich und Zugriff auf vorhandene Kurvenparameter |
| Energie | Rollierende 24 Stunden, 7 oder 30 Tage; Energiezuwächse, Zählerverhältnis, Laufzeiten, Starts und Pumpenstrom |
| Parameter | Vier Kurvenwerkstätten, Gerätevergleich mit Default und Erklärung, Suche, Unterschiede, bestätigte Entwürfe und einklappbares Protokoll |
| Einrichtung | Anzeigename, Speichervolumina und Zuordnung externer Messquellen |

Der Zugriff auf das Panel und seine WebSocket-Endpunkte ist auf Administratoren
beschränkt. Die vorhandenen Lovelace-Dashboards bleiben erhalten. Die Oberfläche
findet R290-Entitäten über die Entity Registry; manuell umbenannte Entity-IDs
funktionieren weiterhin. Zählerzuordnungen aus einem vorhandenen COP-Eintrag
werden als Vorgabe übernommen. Manuelle Anzeigezuordnungen haben Vorrang.

Das Hydraulikschema stellt zwei parallele Wärmepumpen und eine gemeinsame
Zusatzpumpe vor dem Umschaltventil dar. Es ist eine schematische Darstellung der
besprochenen Anlage, keine automatisch erkannte Verrohrung. Bei einer anderen
Geräteanzahl erscheint die Gerätetabelle; für einen anderen hydraulischen Aufbau
muss das Schema angepasst werden. Vor- und Rücklauf sind getrennt, die
Ventilposition wird nicht als gemessen dargestellt. Prozentwerte zeigen die **Ansteuerung**, keine
gemessene Pumpendrehzahl.

Version 1.2.0 übernimmt den freigegebenen Entwurf C mit Temperaturverläufen und
Datenqualität aus A: warmer Hintergrund, horizontale Navigation, orangefarbene
Bedienelemente und native SVG-Zeichnungen ohne externe Bilder oder Schriften.
Auf kleinen Bildschirmen wird die Hydraulik zu einer vertikalen Anlagenansicht.
Die sechs Bereiche bleiben über eine horizontal verschiebbare Navigation erreichbar.

### Kurven und Sprachen ab 1.3.0

Der DE/EN-Umschalter gilt für alle sechs Ansichten, Dialoge und die Entitätensuche.
Die Auswahl wird im lokalen Browserspeicher gespeichert. Entity-IDs, gespeicherte
Werte und Gerätenamen werden nicht umbenannt. Zahlen und Zeitangaben folgen der
Oberflächensprache. Ein Sprachwechsel erhält ungespeicherte Formularwerte und
Kurvenentwürfe.

Heizkörper-, Warmwasser-, Fußbodenheizungs- und Kühlkurve verwenden denselben
kompakten Aufbau: links Basiskurve und Außentemperatur, rechts **Basis**, **PV &
Anhebung** und **Feinabstimmung**. Die Vorschau übernimmt die bestehende lineare
Interpolation mit Begrenzung an den Außenstützpunkten. Sie enthält keine
zeitabhängige Glättung, Rundung oder aktiven Offsets; auch die Kühlkurve wird
nicht automatisch umgekehrt. Die Außentemperaturquelle stammt aus dem jeweiligen
Kurveneintrag. Fehlende Daten werden nicht durch Demo- oder Defaultwerte ersetzt.

Kurvenänderungen bleiben lokal im Entwurf bis zur Alt-/Neu-Bestätigung. Der
Admin-Endpunkt prüft Zugehörigkeit, Wertebereiche, Schrittweiten, Stützpunkte,
Konfigurationsrevision und erwartete Zustände. Alle Änderungen werden zusammen
in einem ConfigEntry-Update gespeichert. Der bestehende Listener lädt den
Kurveneintrag anschließend neu; dies kann bei aktiver Regelung einen neuen
Gerätesollwert auslösen. „Konfiguriert“ bestätigt die Speicherung, nicht die
Geräterückmeldung. Einzelne Geräteparameter nutzen weiterhin die bestätigten
HA-Dienstaufrufe mit Prüfung des vorherigen Wertes.

Die Geräteansicht zeigt **Default**, WP 1 und WP 2. Wenn Excel-Spalte I
„Real Default“ belegt ist, wird ausschließlich dieser Wert verwendet; sonst
Spalte H „Default according manual“. Null bleibt ein gültiger Default.
„My Value Slave 1/2“ wird nicht importiert. Erklärungen sind pro Zeile aufklappbar;
Excel-Dateiname und Fundstelle erscheinen nicht im Dashboard. Wo die Tabelle
keine Erklärung enthält, wird dies ausdrücklich angezeigt. Abweichende Grenzen
zwischen Dokumentation und vorhandener Entität werden angezeigt; die Eingabe
verwendet die Grenzen der Entität. Es erfolgt keine automatische Rücksetzung.

### Registerprüfung der fünf Excel-Tabellen

`scripts/register_catalog.py` liest die Arbeitsmappen nur lesend und erzeugt den
mitgelieferten Registerkatalog inklusive Quell-Hashes. Ergebnis des Abgleichs:

| Tabelle | Definierte Adressen | Bekannte Adressen ohne Entität | Unbeschriftete Adressen |
| --- | ---: | ---: | ---: |
| Main Parameter | 36 | 0 | 0 |
| Realtime Parameter | 38 | 26 | 128 |
| User Parameter | 12 | 0 | 0 |
| Unit System Parameter | 263 | 0 | 0 |
| User Parameter2 | 2 | 13 | 0 |

„Definiert“ beweist weder Aktivierung noch Liveempfang oder vollständige
Bit-/Modusabdeckung. Main fehlen 17 dokumentierte Bitbeschriftungen über fünf
Register; bei elf Unit-System-Parametern weichen Min-/Max-Grenzen ab. Bei
0x080B bildet der vorhandene Schalter nur 0/1 ab, nicht die Modi 2/3.
User-Parameter werden nur für Slave 1 angelegt. Der zusätzliche „WP 2“-Block
0x005E–0x006D innerhalb der Echtzeittabelle ist nicht automatisch Slave 2 der
Kaskade. Beide Kaskadengeräte werden separat über 0x0040 ff. gelesen.
Unbeschriftet umfasst `Unknown`, `leer?`/leere Namen und den numerischen Namen
bei 0x00ED. Holding-Register und Coils sind im Bericht getrennt bezeichnet.

`scripts/probe_unknown_registers.py` hat über die bestehende Proxy-Verbindung
beide Slaves ausschließlich mit FC03 gelesen: 128 unbekannte Adressen je Slave,
zwei Momentaufnahmen, insgesamt 512 gültige Registerantworten ohne Abfragefehler.
11 Adressen von Slave 1 und 9 von Slave 2 waren ungleich null; nur 0x00ED von
Slave 1 änderte sich zwischen den beiden Abfragen. Nullwerte zählen ebenfalls
als empfangen. Bedeutung, Vorzeichen und Skalierung sind damit nicht geklärt.
Diese Stichprobe ist keine Überwachung und beweist keine dauerhafte Datenqualität.

`scripts/build_register_diagnosis.py` erstellt daraus die separate lokale Datei
`artifacts/r290-register-diagnose.html`: uint16/int16/Hex, Zeitstempel, Nullwert-
und Änderungsfilter, Notizfelder sowie JSON-Export/Import der eigenen Zuordnungen.
Die Datei arbeitet offline und sendet keine Gerätebefehle. Rohwerte und persönliche
Zuordnungen werden nicht im Installationsarchiv mitgeliefert. Dokumentierte
Integrationslücken, Bitbeschriftungen und Grenzwertabweichungen wurden bei dieser
UI-Änderung nicht automatisch in neue Gerätefunktionen oder Grenzwerte umgesetzt.

Validierung: Python-Tests mit Home-Assistant-Doubles, lokale Browserprüfungen
für die sechs Ansichten und die vier Kurven, DE/EN, Entwürfe und die HTML-Diagnose.
Das UI wurde mit Testdaten geprüft; diese Version wurde nicht in Live-HA installiert.

Ab Version 1.2.1 sind die Messquellen in **Einrichtung** durchsuchbare Eingabefelder.
Namen und vollständige Entity-IDs können eingegeben oder eingefügt werden. Die
Trefferliste zeigt Namen, ID und Einheit; Pfeiltasten/Enter wählen einen Treffer,
Escape verwirft die aktuelle Suche. Eine vollständige bekannte ID kann auch direkt
gespeichert werden. Unbekannte Suchtexte werden nicht als Zuordnung übernommen.
Ein leeres Feld steht weiterhin für automatische Zuordnung / nicht hinterlegt.

Diagramme unter **Betrieb** und **Energie** haben eine feste Zeichenhöhe von 210 px
bzw. 180 px bei schmaler Zeichenfläche. Linien bleiben unabhängig von Fensterbreite
und Skalierung 1,15 px dünn. Die Achsen werden auf die verfügbare Breite abgestimmt;
kurze Quellenbezeichnungen halten die Legenden übersichtlich.

Die Hydraulik animiert Lüfter ausschließlich anhand positiver, frischer
Lüfterdrehzahlwerte. Der Primärkreis setzt einen positiven Durchfluss des jeweiligen
Geräts voraus, auch bei stehendem Verdichter. Ab b3 reichen seine Flussmarkierungen
durch die Warmwasserschlange beziehungsweise den Plattenwärmetauscher bis zum
passenden Rücklauf. Die Rücklaufrichtung wechselt mit dem Speicherzweig.

Unter **Einrichtung** stehen drei optionale Zuordnungen für die Anzeige:

| Signal | Bedeutung |
| --- | --- |
| Warmwasserladung · Status (on/off) | An = Warmwasserzweig, aus = Pufferzweig |
| Pufferladekreis · Pumpenstatus (on/off) | Separate Umwälzung zwischen Plattenwärmetauscher und Puffer |
| Heizkörperkreis · Pumpenstatus (on/off) | Separate Umwälzung zwischen Puffer und Heizkörpern |

Eine explizite Zuordnung hat Vorrang. Sonst verwendet das Panel das Warmwassersignal
des Zusatzpumpenreglers oder eine eindeutige aktivierte COP-Split-Zuordnung.
Nur ohne zugeordnetes Signal dient eine bekannte Heiz-/Warmwasser-Reglerphase als
Rückfall. Ein zugeordnetes, aber nicht verfügbares Signal wird nicht durch diese
Phase verdeckt. Ohne eindeutigen Zweig bleiben die betreffenden Leitungen statisch;
der Status unter dem Schema benennt die fehlende Zuordnung. Temperaturwerte und
allgemeine Betriebsarten wie „Heizen + Warmwasser“ ersetzen dieses Signal nicht.

Pufferlade- und Heizkörperkreis sind hydraulisch getrennt. Ihre Animation folgt
jeweils dem zugeordneten Pumpenstatus und kann deshalb auch bei stillstehenden
Wärmepumpen laufen. Ein fehlender Status bleibt „unbekannt“. Diese Zuordnungen
speichern ausschließlich Anzeigequellen und senden keine Pumpenbefehle.

Die Zusatzpumpe pulsiert bei positiver Leistungsaufnahme. Alle Animationen sind
schematische Betriebsanzeigen, keine Messung von Fließgeschwindigkeit oder
Ventilposition. Gepollte R290-Signale benötigen eine höchstens drei Minuten alte
HA-Meldung. Externe Schalter/Helfer dürfen lange unverändert bleiben; deren
Quellintegration muss einen Ausfall als nicht verfügbar melden. Ohne HA-Verbindung
ruht die Animation. Pause und „Bewegung reduzieren“ werden ebenfalls respektiert.

Die Übersicht lädt selbstständig einen eigenen 24-Stunden-Verlauf. Der unter
Energie ausgewählte Zeitraum verändert dieses Fenster nicht. Ein Klick auf einen
aktuellen Temperaturwert blendet seine Kurve aus oder wieder ein. Der Verlauf
wird bei geöffneter Übersicht nach fünf Minuten oder manuell erneuert; Livewerte
kommen aus den HA-Zuständen. Angezeigt werden maximal fünf gezielt ausgewählte
Temperaturquellen. Der gemeinsame Vorlauf wird nur so bezeichnet, wenn eine
entsprechende Entität vorhanden ist; ein einzelner Rücklauf bleibt mit WP-Nummer
beschriftet. Fahrenheit-Verläufe werden für die gemeinsame Celsius-Achse umgerechnet.

Die Datenqualitätskarte verwendet `last_reported`, bei Bedarf über den lokalen
Panel-Endpunkt. Fehlt diese Angabe, bleibt die Meldezeit unbekannt; `last_updated`
wird nicht als Ersatz verwendet. Die älteste Vorlaufmeldung der Wärmepumpen und
die Wärmezählermeldung werden mit ihrem Zeitversatz angezeigt. Ein Vorlaufalter
über drei Minuten bzw. Wärmezähleralter über 15 Minuten erzeugt den Hinweis
„Meldealter prüfen“, keinen behaupteten Funkfehler. Diese Anzeigegrenzen verändern
keine Betriebsgrenze des Pumpenreglers. HA-Meldezeiten können Integrationsmeldungen
einschließen und sind kein Nachweis für den Empfang eines physischen WM-Bus-Pakets.

## Installation und Rückkehr zur bisherigen Version

1. Vor der Installation den bisherigen Ordner `custom_components/r290_heatpump`
   und die HA-Konfiguration sichern.
2. Das vollständige Verzeichnis `custom_components/r290_heatpump` aus dem Paket
   in die HA-Konfiguration übernehmen. Die Dateien im Unterordner `frontend`
   gehören zur Integration und müssen mitkopiert werden.
3. Home Assistant vollständig neu starten. Der Menüpunkt **R290 Anlagensteuerung**
   erscheint für Administratoren. Es sind keine npm-Installation, CDN-Ressourcen
   oder zusätzliche Lovelace-Karten erforderlich.
4. Vorhandene Wärmepumpeneinträge bleiben bestehen. Erst ein neu hinzugefügter
   Pumpeneintrag erzeugt einen Zusatzpumpenregler; auch dieser beginnt lesend.

Zum Zurückwechseln zuerst die Pumpensteuerung bewusst an die bisherige Automation
übergeben, den Zusatzpumpeneintrag entfernen, die gesicherte Integration
zurückspielen und HA neu starten. Die Beobachtungsart aktiviert **nicht** automatisch
die alte Automation und verändert den letzten Pumpenausgang nicht.

Diese Fassung wurde lokal mit HA-Testdoubles und einem Browser gegen Testdaten
geprüft. Ein vollständiger Home-Assistant-Server und die reale hydraulische Anlage
sind nicht Bestandteil dieser Tests. Die verwendeten Panel-/Recorder-APIs wurden
mit den offiziellen HA-Quellen für 2026.10 abgeglichen.

## Pumpeneintrag einrichten

Unter **Einstellungen → Geräte & Dienste → R290 Heat Pump → Eintrag hinzufügen**
den Typ **Auxiliary Pump Controller** wählen. Der erste Schritt ordnet die
Entitäten zu; der zweite legt Grenzen und Kalibrierung fest.

| Zuordnung | Anforderung |
| --- | --- |
| Stellglied | `number`, dimmbares `light` oder `fan` mit Prozentsteuerung |
| Separate Freigabe | Schaltbarer Ausgang der externen Zusatzpumpe (`switch` oder entsprechend angebundener `input_boolean`); bei einem Number-Ausgang zwingend erforderlich |
| Umwälzanforderungen | Automatisch vorgeschlagene interne Pumpenstatussensoren aller Geräte, mit ODER verknüpft; alternativ ein gemeinsames on/off-Signal einschließlich Frostschutzumwälzung |
| Warmwasserbetrieb | on/off; keine Temperaturheuristik und keine allgemeine Modusbezeichnung |
| Abtauung | Abtausignale aller Geräte, alternativ ein verlässliches gemeinsames ODER-Signal |
| Verdichterfrequenzen | Je Wärmepumpe eine Entität in Hz |
| Durchflüsse | Je Wärmepumpe eine zeitnah aktualisierte Quelle in L/min, L/h oder m³/h |
| Vor- und Rücklauf | Je Wärmepumpe ein Sensorpaar in °C oder °F |
| Bestehende Automationen | Alle bekannten Automationen auswählen, die denselben Ausgang steuern |

Alle vier numerischen Sensorlisten müssen dieselben Geräte in derselben
Reihenfolge enthalten. Es werden bis zu elf Geräte unterstützt. In der Anlage
mit zwei Wärmepumpen beispielsweise immer **WP1, dann WP2** auswählen.

Statussignale werden ausschließlich als `on/off`, `true/false` oder `1/0`
interpretiert. Ein Sensorwert wie `Heating` wird nicht als „aus“ gewertet. Falls
ein Quellsystem andere Werte liefert, ist zunächst eine passend definierte
Template-Entität mit korrekter `availability` erforderlich. Nicht verfügbare
Originalquellen dürfen im Template nicht stillschweigend zu `off` werden.

Der sporadisch empfangene WM-Bus-Wärmemengenzähler ist **keine Rückführgröße für
diese Regelung**. Seine Durchfluss- und Temperaturwerte gehören nicht in die
schnellen Regelsensorlisten. Zähler können separat für die Auswertung zugeordnet
werden.

Die Aktualität numerischer Regelsensoren wird anhand von `last_reported`, ersatzweise
`last_updated`, geprüft. `last_changed` wird dafür nicht verwendet: Eine konstant
bleibende, aber regelmäßig gemeldete Temperatur ist gültig. Ereignisbasierte
Statussignale werden auf gültigen Zustand und Verfügbarkeit geprüft; ein stabiler
on/off-Zustand erhält nicht allein wegen seines Alters den Status „veraltet“.
Die Signalquelle muss Kommunikationsausfälle daher selbst als unavailable melden.

## Ausgangskalibrierung und Grenzen

- Ein Number-Ausgang wird linear zwischen **Ausgang bei 0 %** und **Ausgang bei
  100 %** abgebildet. Bei 0–10 V sind das 0 und 10; bei einer Prozent-Entität 0 und
  100. Native Min-/Max-Werte und Schrittweite der Entität werden berücksichtigt.
- Ein Light-Ausgang verwendet `brightness_pct`, ein Fan-Ausgang `percentage`.
  Das Gerät muss tatsächlich eine Umwälzpumpe ansteuern. Ein einfacher Schalter
  ist kein geeigneter variabler Ausgang. Fan-Entitäten müssen eine feine
  Prozentsteuerung mit höchstens einem Prozentpunkt Auflösung anbieten.
- Die Endpunkte einer Number-Kalibrierung müssen auf der nativen Schrittweite
  liegen. Die Rückmeldungsprüfung berücksichtigt den tatsächlich gerundeten
  Number-Befehl, damit eine zulässige Quantisierung keinen Schreibfehler vortäuscht.
- Der Stellwert wird vor einer separaten Freigabe gesetzt. Beim Stoppen wird
  die Freigabe ausgeschaltet; ein Light-/Fan-Ausgang wird ebenfalls ausgeschaltet.
- Mindestdurchfluss gilt **pro laufender Wärmepumpe**. Die Störschwelle aus der
  Gerätefirmware ist nicht automatisch der geeignete Betriebswert.
- Die Standardwerte sind Konfigurationsvorgaben, keine für eine bestimmte Anlage
  vermessenen Optimierungswerte. Insbesondere Mindeststellwert, Mindestdurchfluss,
  Ersatzwert, Abtaustellwert, Spreizungen und Zeitgrenzen müssen geprüft werden.

Die Inbetriebnahmebestätigung hält fest, dass Hydraulik, Ausgangskalibrierung,
Frost-/Abtausignale und alleinige Steuerungsverantwortung geprüft sind. Sie
aktiviert die Regelung noch nicht. Neue Einträge und ältere Installationen ohne
gespeicherte Betriebsfreigabe starten in Beobachten. Ab 1.5.0b4 bleibt eine explizit
gewählte Automatik bzw. ein fester Stellwert über Neuladen und Neustarts erhalten.
Die Wiederaufnahme wartet auf verwendbare Eingangssignale und Stellgliedrückmeldung.
Bei geänderten Steuerungsquellen, Stellglied oder Ausgangskalibrierung ist erneut
eine Freigabe erforderlich. Ein verriegelter Fehler oder bewusst gewähltes
Beobachten wird niemals als Betriebsfreigabe wiederhergestellt.

Beobachten und Entladen senden keine Abschaltbefehle. Ein bereits eingeschalteter
Ausgang kann deshalb eingeschaltet bleiben; die Oberfläche weist darauf hin.
Die Wiederaufnahme löst dies für zuvor aktiv freigegebene Regler, nicht für einen
abgeschalteten Home-Assistant-Host oder eine bewusst abgegebene Steuerungsverantwortung.

## Betriebsarten und Entscheidungen

| Situation | Verhalten bei aktiver Regelung |
| --- | --- |
| Beobachten | Berechnet und protokolliert Vorschläge, sendet niemals Stellbefehle |
| Fester Stellwert | Verwendet den konfigurierten manuellen Wert während des normalen Betriebs; Schutz- und Ablaufzustände bleiben vorrangig |
| Anlauf | Hält mindestens den Ersatzwert während der Beruhigungszeit; der Regler gibt den Verdichter selbst nicht frei |
| Heizen / Warmwasser | Getrennte Zielspreizungen; größtes ΔT der laufenden Geräte bestimmt Erhöhen/Halten/Reduzieren |
| Mindestdurchfluss unterschritten | Erhöht sofort auf den konfigurierten maximalen Stellwert |
| Abtauung | Konfigurierter Abtaustellwert; danach erneute Beruhigungszeit |
| Anforderung ohne Verdichter | Umwälzung mit Ersatzwert; 0 Hz allein ist keine Abschaltfreigabe |
| Interne Pumpenfreigaben eindeutig aus | Sofortiger Stopp, auch vor Anlauf-, Abtau- und Ersatzwertvorgaben; kein Nachlauf gegen geschlossene Kugelhähne |
| Interne Pumpenfreigabe unbekannt | Kein neuer Stellbefehl, insbesondere kein Start durch einen Ersatzwert; der tatsächliche Ausgang bleibt unverändert |
| Pumpenfreigabe an, aber numerische Daten / weiterer Status fehlen | Ersatzbetrieb ohne Absenkung unter Ersatzwert bzw. zuletzt bekannten höheren Stellwert |
| Stellbefehl fehlgeschlagen | Fehler wird verriegelt, Rückkehr zu Beobachten; keine blinde Wiederholung eines möglicherweise bereits ausgeführten Befehls |
| Ausbleibende Stellgliedrückmeldung | Nach zwei Regelintervallen, mindestens 30 s, Rückkehr zu Beobachten |
| Alte Automation aktiv oder unbekannt | Aktive Übernahme wird verweigert; bei nachträglichem Konflikt Rückkehr zu Beobachten |

Die proportionale Schrittregelung arbeitet ohne auflaufenden Integralanteil.
Sie verändert die Ansteuerung um höchstens den konfigurierten normalen Schritt
pro Regelintervall. Mindestdurchfluss, Abtauung, Anlauf und Ersatzbetrieb dürfen
diesen Schritt zur Sicherung der Umwälzung überschreiten, sofern eine interne
Pumpenfreigabe vorliegt. Die interne Umwälzung einschließlich Frostschutz und
Nachlauf hält diese Freigabe; die Zusatzpumpe verlängert sie nicht selbst.
Der alte Konfigurationswert `postrun_seconds` bleibt zum Lesen älterer Einträge
erhalten, hat keine Wirkung mehr und wird nicht mehr zur Einstellung angeboten.
Bei widersprüchlichem Verdichter-/Abtausignal trotz ausgeschalteter interner Pumpen
wird zusätzlich `demand_status_conflict` protokolliert. Die internen
Wärmepumpenregler, insbesondere P099/P100/P116, werden dabei nicht verändert.

Der Regler ersetzt keine geräteeigenen Schutzfunktionen. Bei ausgeschaltetem
Home Assistant kann er keine Befehle senden; der Ausgang bleibt beim Verhalten
seiner Geräteintegration bzw. Hardware. Die Frostsicherung und das Verhalten bei
Kommunikationsverlust müssen zur Anlage passen. Eine bestätigte Stellglied-Entität
ist außerdem keine unabhängige Messung von Drehzahl oder tatsächlichem Durchfluss.

## Parameteränderungen

Aktuelle Entitätswerte öffnen per Klick den Home-Assistant-Verlauf, auch bei
gesperrter Bearbeitung und im Hydraulikschema. Der Stift ist getrennt davon
zum Ändern vorgesehen. Bei berechneten Werten werden die zugrunde liegenden
Messquellen angeboten. Neue Sensoren für prozentuale Ausgangsrückmeldung und
Zielspreizung ermöglichen deren eigene Recorder-Historie ab Installation.
Sie sind keine unabhängige Drehzahl- oder Durchflussmessung.

Für Rohregister ohne Entität zeigt der Verlauf die in der Diagnosesitzung
gesammelten Messungen einschließlich Empfangszeit. Diese Liste ist kein
dauerhafter Recorder-Verlauf. Der WM-Bus-Zähler bleibt ausschließlich eine
Quelle der zeitlich gekennzeichneten Auswertung, kein schnelles Regelsignal.

Die ergänzten DE/EN-Parametertexte stammen aus den lokalen technischen
Handbüchern und dem Modbus-Protokoll. Adressen wurden abgeglichen; Defaults
und Wertebereiche bleiben unverändert. Unklare Kennfelder sowie widersprüchliche
Angaben etwa zu P097, P163 und P248 sind ausdrücklich eingeschränkt beschrieben.
Quellennachweise bleiben in `Documentation/system-parameter-help.json` für die
Entwicklung erhalten und werden nicht als zusätzliche UI-Spalte angezeigt.

Die Oberfläche erlaubt Änderungen erst nach Freigabe der Bearbeitung in der
aktuellen Sitzung. Jeder einzelne Befehl erhält eine Alt-/Neu-Vorschau. Der Server
prüft Administratorrechte, Zugehörigkeit zur Integration, Verfügbarkeit,
Wertebereich/Schrittweite bzw. zulässige Optionen und den noch unveränderten alten
Wert. Änderungen erfolgen über die vorhandenen HA-Entitäten und deren gemeinsamen
Modbus-Zugriff. Die Pumpenbetriebsart hat einen getrennten Endpunkt.

Das Protokoll speichert die letzten 300 über dieses Panel angestoßenen
Parameteränderungen mit Zeitpunkt, Benutzer-ID, Altwert, angefordertem Wert und
Ergebnis des Dienstaufrufs. Es ist kein globales Audit aller HA-Automationen.
„Gesendet“ ist keine unabhängige Geräteverifikation. Manche vorhandenen Entitäten
aktualisieren ihren HA-Zustand optimistisch; den tatsächlichen Gerätewert bei der
nächsten Registerabfrage kontrollieren. Schreibfehler numerischer Modbus-Parameter
und der Zirkulationsschalter werden nun an den Aufrufer weitergereicht.

## Auswertung und Datenqualität

Verläufe kommen aus **Home Assistant Recorder**. Eine direkte InfluxDB-Anbindung
ist nicht enthalten; vorhandene Influx-Aufzeichnungen werden weder geändert noch
importiert. 30 Tage können nur angezeigt werden, soweit Recorder sie aufbewahrt.

Energieauswertungen verwenden positive Zählerdifferenzen. Rücksetzungen werden
gezählt und qualifizieren den Zeitraum als unsicher. Verzögerte Lieferungen
werden nicht als exakte Tagesproduktion interpretiert und nicht vermeintlich
präzise auf Heiz- und Warmwasserphasen verteilt. Lange Änderungsintervalle,
unbekannte Abschnitte und unsichere Zeitgrenzen erscheinen sichtbar. Eine
unveränderte Zähleranzeige allein beweist keinen Funkfehler.

Das Wärme-/Stromverhältnis wird als **Zählerverhältnis** bezeichnet. Ob daraus
eine belastbare Arbeitszahl folgt, hängt zusätzlich von identischen Bilanzgrenzen,
zeitlicher Zuordnung und der Erfassung von Warmwasser und Hilfsenergie ab.
Die Pumpenleistung wird über bekannte Zustandsintervalle integriert. Ein
fortgeschriebener Recorder-Zustand garantiert keinen frischen Hardwareempfang.

Verdichterstarts sind beobachtete Übergänge von 0 Hz auf eine positive Frequenz.
Starts nach unbekannten Zuständen werden nicht erfunden. Die Laufzeit zählt
Intervalle mit bekanntem positivem Frequenzzustand.

Grafiken verwenden eine ausgedünnte Hüllkurve, die Spitzen und unbekannte Werte
erhält. Der Verlauf-CSV-Export enthält diese Diagrammstützpunkte, **keinen
vollständigen Rohdatenexport**. Protokoll-CSV-Dateien enthalten die gespeicherten
Ereignisse. Zahlen und Zeitstempel bleiben unabhängig vom Anzeigeformat auswertbar.

## Lokale Prüfungen

```powershell
python -m unittest discover -s tests -v
python -m compileall -q custom_components/r290_heatpump
node --check custom_components/r290_heatpump/frontend/r290-panel.js
node tests/frontend-checks.mjs
```

Für die Browserprüfungen muss Playwright verfügbar sein. Optional können
`PLAYWRIGHT_MODULE` auf sein Paketverzeichnis und `CHROMIUM_EXECUTABLE` auf eine
Chromium-/Edge-Binärdatei zeigen. Der Test verwendet ein neues unsichtbares
Browserprofil, einen nur an 127.0.0.1 gebundenen Server und synthetische Testdaten.
Er öffnet kein Benutzerprofil und verbindet sich nicht mit einer realen HA-Instanz.
Screenshots werden im lokalen Ordner `artifacts` abgelegt.

Technische Referenzen:
[Custom Panels](https://contributors.home-assistant.io/frontend/custom-ui/panel/),
[Config Entries](https://contributors.home-assistant.io/core/integrations/config-entries/),
[Recorder-Historie (HA 2026.10)](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/recorder/history/__init__.py).


## Oberfläche 1.4.0: alle Daten und Live-Diagnose

Unter **Parameter** stehen neben den vier Kurven die Bereiche Main Parameter,
Realtime Parameter, Userparameter, Systemparameter, Userparameter 2 und Alle
Entitäten bereit. Alle 518 Katalogeinträge werden angezeigt, auch wenn keine
Entität vorhanden ist. Unter Alle Entitäten stehen auch deaktivierte und nicht
zugeordnete Entitäten mit ihren Attributen. Das Öffnen dieser Ansicht aktiviert
keine Entitäten. Die geänderten Standardaktivierungen ab 1.5.0b2 sind oben
beschrieben. Schreibbare Werte behalten Freigabe, Vorschau und Bestätigung.

**Fehlerspeicher** zeigt aktuelle Fehlerregister und Recorder-Zustände für 1, 7
oder 30 Tage. Ein unbekannter Zustand bestätigt keine Entstörung. Der Verlauf
kommt aus Home Assistant, nicht aus einem nachgewiesenen historischen Speicher
der Wärmepumpe. Die Anzeige enthält höchstens die neuesten 2.000 Zustandswechsel.
Fehlende Recorder-Aufzeichnungen und deaktivierte Entitäten bleiben erkennbar.

**Diagnose** zeigt zunächst tatsächlich empfangene Rohwerte der laufenden
Integration. Über **Live-Abfrage starten** wird die gewählte Registergruppe für
alle konfigurierten Wärmepumpen reihum gelesen. Maximal 20 aufeinanderfolgende
Register je Anfrage, anschließend 3 Sekunden Pause; bestehende Modbus-Sperre und
Verbindungsparameter bleiben in Kraft. Wechsel der Gruppe oder Seite stoppt die
Zusatzabfrage. Bei verborgenem Browser-Tab oder unterbrochener HA-Verbindung
werden keine neuen Zusatzabfragen gestartet. Eine bereits laufende Anfrage kann
noch fertig werden. Es gibt keinen Schreibzugriff auf unbekannte Register.

Empfangszeit und Änderungszeit sind getrennt. Ein konstanter Wert bekommt bei
neuem Empfang einen neuen Empfangszeitpunkt. Lesefehler behalten den letzten
Wert und dessen ursprünglichen Zeitstempel sichtbar bei. Für unbekannte Werte
werden keine Einheit oder Skalierung erfunden. Die vollständige Abfragerunde
kann je nach Gruppe, Gerätezahlen und Verbindung einige Zeit dauern.

Notizen unter Bits & Beschreibung werden lokal im Browser gespeichert. Der
JSON-Export enthält die letzten Rohwerte, Notizen und bis zu 2.000 aktuelle
Sitzungsmessungen. Exporte sowie die frühere eigenständige Diagnose-HTML sind
Momentaufnahmen. Live ist die mit Home Assistant verbundene Diagnoseansicht.

Updates ändern bestehende DOM-Elemente statt den Seiteninhalt vollständig zu
ersetzen. Scrollposition, offene Erklärungen und CSS-Animationen bleiben bei
Live-Updates erhalten. Die Regressionstests prüfen auch einen äußeren
Scrollcontainer über eine Shadow-DOM-Grenze wie bei Home Assistant.
