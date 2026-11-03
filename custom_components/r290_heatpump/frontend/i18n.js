// DE is the source language of the existing templates. Only UI text and
// accessibility labels are translated; entity IDs, form values and commands
// remain unchanged. Original text is retained for in-place language switching.
const EN = {
  'Betriebsdaten':'Operating data','Maschineninfo':'Machine information','Echtzeitwerte':'Realtime parameters','Benutzerparameter':'User parameters','Benutzerparameter 2':'User parameters 2',
  'Einstellungen':'Settings','Geräteinfo':'Device information','Werkstestmodus':'Factory test mode','Unterseiten':'Subpages',
  'Schaubild':'Schematic',
  'WW-Ladekreis · Pumpenstatus (on/off)':'DHW charging circuit · pump state (on/off)',
  'Anlagenaufbau':'Plant configuration','Service':'Service',

  'Name: Kurve ausblenden · Wert: Verlauf öffnen.':'Name: toggle curve · value: open history.',
  'Kurve ein- oder ausblenden':'Show or hide curve',
  'Interne Pumpen aus: Zusatzpumpe stoppen. Kein Nachlauf gegen geschlossene Kugelhähne.':'Internal pumps off: stop the auxiliary pump. No postrun against closed ball valves.',
  'Pumpenfreigabe unbekannt: Ausgang unverändert lassen, kein Startbefehl.':'Pump permission unknown: leave output unchanged, no start command.',
  'Gespeicherte Regelung wartet auf gültige Freigabe und Stellgliedrückmeldung.':'Saved control is waiting for valid permission and actuator feedback.',
  'Zuvor freigegebene Regelung nach gültigen Eingangssignalen fortgesetzt.':'Previously armed control resumed after valid input signals.',
  'Regler angehalten. Freigegebene Betriebsart für das Neuladen gespeichert.':'Controller suspended. Armed mode saved for reload.',

  'Systemparameter':'System parameters','Userparameter':'User parameters','Userparameter 2':'User parameters 2','Alle Entitäten':'All entities','Fehlerspeicher':'Fault history','Diagnose':'Diagnostics',
  'Keine Leistung':'No power input','Nicht eingerichtet':'Not configured','Regelung freigegeben':'Control enabled','Zuordnung fehlt':'Mapping missing','Betriebsgrenzen und Freigaben gelten für jeden Stellbefehl.':'Operating limits and authorizations apply to every command.','Sensoren und Stellglied in der Integration verbinden.':'Connect sensors and actuator in the integration.','Volumen nicht hinterlegt':'Volume not specified','Quelle nicht zugeordnet':'Source not mapped',
  'Letzte Zustandsänderung':'Last state change','Leistungsaufnahme':'Power input','Keine Stellbefehle':'No control commands','Der Regler beobachtet die Anlage und berechnet Vorschläge.':'The controller observes the plant and calculates suggestions.','Regelung ansehen':'View controller','Nicht verfügbar':'Unavailable',
  'Kurvenvorschau: Solltemperatur in Abhängigkeit von der Außentemperatur':'Curve preview: setpoint versus outdoor temperature',
  'Bereich laut Dokumentation':'Documented range','Abweichende Grenzen in der Integration:':'Different limits in the integration:',
  'Die Eingabefelder verwenden die Grenzen der vorhandenen Entität.':'Input fields use the limits of the existing entity.',
  'Anlagenbereiche':'Plant sections','Verbunden mit Home Assistant':'Connected to Home Assistant','Hydraulische Anlagenübersicht':'Hydraulic plant overview',
  'Kein gemeldeter Konflikt':'No conflict reported','Noch keiner':'None yet','Stellbereich':'Speed range','Ersatzwert / Abtauung':'Fallback / defrost speed','Mindestdurchfluss je aktiver WP':'Minimum flow per active heat pump','Spreizung Heizen / Warmwasser':'Temperature difference · heating / hot water','Schritt / Intervall':'Step / interval','Anlauf / Nachlauf':'Startup / overrun','Maximales Alter numerischer Messwerte':'Maximum age of numeric readings','Ereignisbasiertes Statussignal':'Event-based status signal','Berechnung':'Calculation','Stellbefehl':'Command','Fehler':'Error','Betriebsart':'Operating mode','Speichervolumen noch nicht hinterlegt':'Tank volume not specified','Regler nicht eingerichtet':'Controller not configured',
  'Anlage':'Plant','Zusatzpumpe':'Auxiliary pump','Betrieb':'Operation','Energie':'Energy','Parameter':'Parameters','Einrichtung':'Setup',
  'Sprache':'Language','Deutsch':'German','Englisch':'English','in Home Assistant':'in Home Assistant',
  'Anlagenübersicht':'Plant overview','Außentemperatur':'Outdoor temperature','Betriebszustand':'Operating state',
  'Bereit':'Standby','Anlauf':'Starting','Heizen':'Heating','Warmwasser':'Hot water','Abtauen':'Defrosting','Nachlauf':'Pump overrun','Umwälzen':'Circulating','Durchfluss sichern':'Flow protection','Ersatzbetrieb':'Fallback','Initialisierung':'Initializing',
  'Beobachten':'Observe','Fester Stellwert':'Fixed speed','Automatisch':'Automatic','Aktiv':'Active','Inaktiv':'Inactive','Aus':'Off','Ja':'Yes','Nein':'No','Ausstehend':'Pending','Unbekannt':'Unknown','Nicht zugeordnet':'Not mapped','Nicht bekannt':'Unknown','Verfügbar':'Available','Fehlt':'Missing','Nicht geladen':'Not loaded',
  'Daten aktualisieren':'Refresh data','Home Assistant Menü öffnen':'Open Home Assistant menu','Lokal verbunden':'Connected locally','Verbindung getrennt':'Disconnected',
  'Anlagendaten werden geladen':'Loading plant data','Verbindung zur R290-Integration wird hergestellt.':'Connecting to the R290 integration.','Erneut laden':'Retry',
  'Keine Verbindung zu Home Assistant.':'No connection to Home Assistant.','Die Verbindung ist getrennt. Angezeigte Werte können veraltet sein. Änderungen sind nicht verfügbar.':'Disconnected. Displayed values may be outdated. Editing is unavailable.',
  'Datenqualität':'Data quality','Letzte HA-Meldung':'Last HA report','Wärmepumpen¹':'Heat pumps¹','Wärmezähler':'Heat meter','Zeitversatz':'Time difference',
  'Quellen unvollständig':'Sources incomplete','Meldealter prüfen':'Check report age','Meldezeit unbekannt':'Report time unknown','HA-Meldungen aktuell':'HA reports up to date',
  'Mindestens eine Messquelle fehlt oder liefert keinen Zahlenwert.':'At least one source is missing or does not provide a numeric value.',
  'Einige HA-Meldungen liegen länger zurück. WM-Bus-Zähler getrennt bewerten.':'Some HA reports are older. Assess WM-Bus meters separately.',
  'Nicht alle Quellen stellen einen Meldezeitpunkt bereit.':'Some sources do not provide a report timestamp.',
  'Die zugeordneten Quellen haben zuletzt zeitnah an HA gemeldet.':'The mapped sources have reported to HA recently.',
  '¹ Älteste Vorlaufmeldung. HA-Meldezeiten belegen keinen WM-Bus-Empfang. Unveränderte Zählerstände sind kein Ausfallnachweis.':'¹ Oldest flow-temperature report. HA timestamps do not confirm WM-Bus reception. Unchanged meter readings do not prove a communication failure.',
  'Messgrenzen ansehen':'View measurement limits','Temperaturverläufe':'Temperature history','Wichtige Temperaturen der Anlage · letzte 24 Stunden':'Key plant temperatures · last 24 hours','Aktuelle Werte':'Current values','Wert anklicken, um die Kurve auszublenden.':'Click a value to hide its series.',
  'Temperaturverlauf aktualisieren':'Refresh temperature history','Temperaturverlauf wird geladen …':'Loading temperature history …','Keine aufgezeichneten Temperaturwerte für die sichtbaren Quellen.':'No temperature history for the visible sources.',
  'Für den Temperaturverlauf sind noch keine Quellen zugeordnet.':'No sources have been mapped for temperature history.',
  'Temperaturverlauf':'Temperature history','Verdichterfrequenzen':'Compressor frequencies','Pumpenleistung':'Pump power',
  'Aktuelle Ansteuerung':'Current speed command','Regelungsmodus':'Control mode','Vorgeschlagene':'Suggested','Ansteuerung':'Speed command','Ziel':'Target','Spreizung':'Temperature difference','Gemessene':'Measured',
  'Vorlauf':'Flow','Rücklauf':'Return','Vorlauf · gemeinsam':'Flow · common','Vorlauf / Rücklauf':'Flow / return','Verdichter':'Compressor','Durchfluss':'Flow rate','Gerät':'Unit',
  'Das Hydraulikschema bildet eine parallele Kaskade mit zwei Geräten ab.':'The hydraulic diagram shows two units in a parallel cascade.',
  'Parallele Kaskade':'Parallel cascade','Gemeinsame Zusatzpumpe':'Common auxiliary pump','3/2-Wege-Umschaltventil':'3/2-way diverter valve','3/2-Wege-Ventil':'3/2-way valve','Trinkwarmwasser':'Domestic hot water','Heizungspuffer':'Heating buffer','Heizkörper':'Radiators',
  'Schema · Zweig aus Betriebsphase · Ventilposition nicht rückgemeldet':'Diagram · branch inferred from operating phase · no valve-position feedback',
  'Schema · Flussrichtung schematisch · Ventilposition nicht rückgemeldet':'Diagram · schematic flow direction · no valve-position feedback',
  'Speicherzweig: Warmwasser':'Tank branch: hot water','Speicherzweig: Heizungspuffer':'Tank branch: heating buffer',
  'Speicherzweig unbekannt · Warmwassersignal zuordnen':'Tank branch unknown · map a hot-water status signal',
  'Pufferladekreis: an':'Buffer charging: on','Pufferladekreis: aus':'Buffer charging: off','Pufferladekreis: Status unbekannt':'Buffer charging: status unknown',
  'Heizkörperkreis: an':'Radiator circuit: on','Heizkörperkreis: aus':'Radiator circuit: off','Heizkörperkreis: Status unbekannt':'Radiator circuit: status unknown',
  'Warmwasserladung · Status (on/off)':'Hot-water charging · status (on/off)',
  'Pufferladekreis · Pumpenstatus (on/off)':'Buffer charging circuit · pump status (on/off)',
  'Heizkörperkreis · Pumpenstatus (on/off)':'Radiator circuit · pump status (on/off)',
  'An = Warmwasserzweig, aus = Pufferzweig. Ein vorhandenes COP-Warmwassersignal wird automatisch verwendet.':'On = hot-water branch, off = buffer branch. An existing COP hot-water status signal is used automatically.',
  'Separate Umwälzung zwischen Plattenwärmetauscher und Puffer. Nur Anzeige, keine Steuerung.':'Separate circulation between plate heat exchanger and buffer. Display only; no control.',
  'Separate Umwälzung zwischen Puffer und Heizkörpern. Nur Anzeige, keine Steuerung.':'Separate circulation between buffer and radiators. Display only; no control.',
  'Schema · Ventilposition nicht rückgemeldet':'Diagram · no valve-position feedback','Kleiner interner':'Small internal','Wärmetauscher':'heat exchanger','Plattenwärmetauscher':'Plate heat exchanger','Animation pausieren':'Pause animation','Animation starten':'Start animation','Betriebsdetails':'Operation details',
  'Umwälzung mit Überblick.':'Circulation at a glance.','Stellwert, Grenzen und die Begründung jeder Regelentscheidung.':'Speed, limits and the reason behind every control decision.','Eintrag & Optionen ↗':'Entry & options ↗',
  'Zusatzpumpenregelung einrichten':'Set up auxiliary pump control','In der R290-Integration einen Eintrag „Auxiliary Pump Controller“ hinzufügen.':'Add an “Auxiliary Pump Controller” entry in the R290 integration.','Messwerte, Stellglied und bestehende Automationen werden dort zugeordnet.':'Map measurements, actuator and existing automations there.',
  'Integration einrichten ↗':'Set up integration ↗','Ansteuerung aktuell':'Current speed command','Berechneter Stellwert':'Calculated speed','Stromaufnahme':'Power consumption','Aktive Wärmepumpen':'Active heat pumps','Spreizungen':'Temperature differences','Zielspreizung':'Target temperature difference',
  'Regelung bedienen':'Control mode','Eine freigegebene Regelung wird nach Neustart mit geprüften Eingangssignalen fortgesetzt.':'An authorized controller resumes after restart once its inputs have been checked.',
  'Die interne Pumpenfreigabe hat Vorrang. Nur bei offenem Pumpenkreis wirken Anlauf, Abtauung und Mindestdurchfluss.':'Internal pump demand takes priority. Startup, defrost and minimum flow control apply only when the pump circuit is open.',
  'Keine Automationen zur Konfliktprüfung zugeordnet':'No automations assigned for conflict monitoring',
  'Folgt der internen Pumpenfreigabe':'Follows internal pump demand',
  'Beobachten aktiv: Der Pumpenausgang ist eingeschaltet und wird hier derzeit nicht geregelt.':'Observe mode: the pump output is on and is not currently controlled here.',
  '„Fester Stellwert“ folgt weiterhin der Pumpenanforderung. Abtauung, Mindestdurchfluss und Nachlauf haben Vorrang.':'Fixed speed still follows pump demand. Defrosting, minimum flow and pump overrun take priority.',
  'Inbetriebnahme bestätigt':'Commissioning confirmed','Bestehende Automationen':'Existing automations','Letzter Stellbefehl':'Last command','Zeitpunkt':'Time',
  'Beobachten sendet keine Stellbefehle und schaltet die Pumpe nicht aus. Eine bisherige Automation wird hier weder ein- noch ausgeschaltet.':'Observe mode sends no commands and does not switch off the pump. Existing automations are not enabled or disabled here.',
  'Konfigurierte Betriebsgrenzen':'Configured operating limits','Diese Werte müssen zur Hydraulik und zur Pumpenansteuerung passen.':'These limits must match the hydraulic circuit and pump actuator.',
  'Entscheidungsprotokoll':'Decision log','Vorschläge, Stellbefehle und Fehler getrennt nachvollziehen.':'Review suggestions, commands and errors separately.','Eingangssignale der Regelung':'Control input signals','Numerische Werte werden auf Einheiten, Plausibilität und Meldealter geprüft.':'Numeric inputs are checked for units, plausibility and report age.',
  'Quelle':'Source','Wert':'Value','Letzte Meldung':'Last report','Verwendbar':'Usable','Warte auf Signaldetails.':'Waiting for signal details.','Noch keine Ereignisse.':'No events yet.','Warte auf Betriebsdaten.':'Waiting for operating data.',
  'Abtauung aktiv. Der konfigurierte Abtaustellwert hat Vorrang.':'Defrosting active. The configured defrost speed takes priority.',
  'Betriebsdaten fehlen oder sind veraltet. Keine Absenkung unter den Ersatzstellwert.':'Operating data is missing or stale. Speed will not fall below the fallback setting.',
  'Keine Anforderung mehr. Die konfigurierte Nachlaufzeit läuft.':'Demand ended. The configured pump overrun is active.',
  'Keine Anforderung, kein Verdichter und keine Abtauung. Nachlauf beendet.':'No demand, compressor operation or defrosting. Pump overrun has ended.',
  'Der Durchfluss einer laufenden Wärmepumpe ist nicht verlässlich verfügbar.':'Reliable flow data is unavailable for a running heat pump.',
  'Mindestens eine laufende Wärmepumpe unterschreitet den eingestellten Mindestdurchfluss.':'At least one running heat pump is below the configured minimum flow.',
  'Der Wasserkreis läuft an. Die Regelung wartet die Beruhigungszeit ab.':'The water circuit is starting. Control is waiting for it to settle.',
  'Umwälzung angefordert, beide Verdichter stehen. Ersatzstellwert bleibt erhalten.':'Circulation requested, both compressors stopped. Fallback speed is retained.',
  'Die Temperaturspreizung ist unvollständig oder unplausibel.':'Temperature difference data is incomplete or implausible.',
  'Fester Stellwert innerhalb der Grenzen. Durchflussschutz und Abtauung bleiben vorrangig.':'Fixed speed within limits. Flow protection and defrosting still take priority.',
  'Wartezeit bis zum nächsten Regelschritt.':'Waiting for the next control adjustment.',
  'Die größte Spreizung liegt über dem Zielband. Ansteuerung schrittweise erhöhen.':'The largest temperature difference is above the target band. Increase speed gradually.',
  'Alle aktiven Spreizungen liegen unter dem Zielband. Ansteuerung schrittweise reduzieren.':'All active temperature differences are below the target band. Reduce speed gradually.',
  'Die Spreizung liegt im Zielband. Stellwert halten.':'Temperature difference is within the target band. Hold speed.',
  'Eine bestehende Pumpenautomation ist aktiv oder nicht verfügbar. Steuerung abgegeben.':'An existing pump automation is active or unavailable. Control has been released.',
  'Der Stellbefehl ist fehlgeschlagen oder seine Ausführung ist unklar. Erneute Freigabe erforderlich.':'The command failed or its outcome is uncertain. Reauthorization is required.',
  'Die Stellglied-Entität bestätigt den angeforderten Wert nicht. Steuerung angehalten; Ausgang und Kommunikation prüfen.':'The actuator entity has not confirmed the requested value. Control paused; check the output and communication.',
  'Regler gestartet. Beobachtungsmodus aktiv.':'Controller started in observe mode.','Regler beendet. Ausgang nicht verändert.':'Controller stopped. Output unchanged.',
  'Betrieb verstehen.':'Understand operation.','Heizen, Warmwasser und Abtauung im zeitlichen Zusammenhang.':'Heating, hot water and defrosting over time.','Verlauf aktualisieren ↻':'Refresh history ↻','Verlauf aktualisieren':'Refresh history','Aktive Phase':'Active phase','Betriebssignale fehlen':'Operating signals missing','Heizkörper Vorlauf':'Radiator flow','Heizkörper Rücklauf':'Radiator return','Separater Heizkreis':'Separate heating circuit',
  'Temperaturen im Verlauf':'Temperatures over time','Letzte 24 Stunden':'Last 24 hours','Kaskade':'Cascade','Verdichterfrequenzen und aktuelle hydraulische Messwerte':'Compressor frequencies and current hydraulic readings','Einstellungen →':'Settings →',
  'Alle Sollwerte, PV-Offsets und Grenzen unter Parameter. Änderungen erfolgen mit Vorschau.':'Find all setpoints, PV offsets and limits under Parameters. Changes require a preview.',
  'Heizkurve':'Heating curve','Warmwasserkurve':'Hot water curve','Fußbodenheizung':'Underfloor heating','Kühlkurve':'Cooling curve','Kühlung':'Cooling',
  'Verlauf wird geladen …':'Loading history …','Noch keine Verlaufsdaten.':'No history yet.','Für diese Quellen sind im gewählten Zeitraum keine aufgezeichneten Werte vorhanden.':'No recorded values for these sources in the selected period.','Keine Quellen für die Auswertung zugeordnet.':'No sources mapped for analysis.',
  'Energie nachvollziehen.':'Understand energy use.','Auswertung aus Home Assistant Recorder. Unregelmäßige Zählerlieferungen bleiben sichtbar.':'Analysis from Home Assistant Recorder. Irregular meter reports remain visible.','24 Stunden':'24 hours','Erfasster Stromzuwachs':'Recorded electricity increase','Erfasster Wärmezuwachs':'Recorded heat increase','Zählerverhältnis Wärme / Strom':'Meter ratio · heat / electricity','Verdichterstarts':'Compressor starts','Erkannte Übergänge von 0 Hz auf Betrieb':'Detected transitions from 0 Hz to operation',
  'Noch nicht berechenbar':'Not yet calculable','Zeitgrenzen unsicher · keine gesicherte Arbeitszahl':'Uncertain time boundaries · efficiency ratio not verified','Bilanzgrenzen der beiden Zähler prüfen':'Check the boundaries covered by both meters','Stromzähler zuordnen':'Map an electricity meter','Wärmemengenzähler zuordnen':'Map a heat meter',
  'Mindestens ein Energiezähler hat lange Änderungsintervalle, Datenlücken oder Rücksetzungen. Zuwächse sind dem Empfangszeitraum zugeordnet. Eine exakte Tagesarbeitszahl oder Aufteilung auf Heizen und Warmwasser lässt sich daraus nicht ableiten.':'At least one energy meter has long intervals, gaps or resets. Increases are assigned to their reception period. An exact daily efficiency ratio or split between heating and hot water cannot be derived.',
  'Verdichterlaufzeiten':'Compressor runtime','Aus aufgezeichneten Frequenzzuständen':'From recorded frequency states','Abdeckung bedeutet bekannte Recorder-Zustände. Ein fortgeschriebener Wert beweist keinen laufenden Geräteempfang. Starts nach einer Datenlücke werden nicht hinzugerechnet.':'Coverage means known Recorder states. A carried-forward value does not prove ongoing device reception. Starts after a data gap are not counted.',
  'Zusatzpumpenstrom':'Auxiliary pump electricity','Integration der aufgezeichneten Leistungszustände':'Integration of recorded power states','Temperaturen und Last':'Temperatures and load','Kurven sind als Zustandsverlauf dargestellt; unbekannte Werte unterbrechen die Linie.':'Charts show state history; unknown values break the line.','Quellen & Messgrenzen':'Sources & measurement limits','Die Zähler müssen denselben Bilanzraum erfassen. Pumpenstrom nicht doppelt addieren.':'Meters must cover the same system boundary. Do not count pump electricity twice.',
  'Ein unveränderter Zählerstand beweist keinen Empfangsausfall. WM-Bus-Werte werden ausschließlich für zeitlich gekennzeichnete Auswertungen genutzt.':'An unchanged reading does not prove reception failure. WM-Bus values are used only in analyses with explicit time boundaries.',
  'Noch nicht zugeordnet':'Not yet mapped','Zeitbezug prüfen':'Check timing','Zeitpunkt unbekannt':'Time unknown','vor weniger als 1 Min.':'less than 1 min ago','weniger als 1 Min.':'less than 1 min',
  'Die Anlage zuordnen.':'Map your plant.','Anzeigedaten und Speichergrößen. Die Pumpenregelung wird über ihren Integrationseintrag eingerichtet.':'Display sources and tank sizes. Pump control is set up through its integration entry.','Anzeige & Messquellen':'Display & measurement sources','Diese Zuordnungen verändern keine Geräteparameter.':'These mappings do not change device parameters.','Anlagenname':'Plant name','Heizungsanlage':'Heating system','Warmwasserspeicher · Liter':'Hot water tank · litres','Heizungspuffer · Liter':'Heating buffer · litres','0 = nicht hinterlegt':'0 = not specified',
  'Stromaufnahme Zusatzpumpe':'Auxiliary pump power','Wärmemenge · kumulierter Zähler':'Heat · cumulative meter','Stromverbrauch · kumulierter Zähler':'Electricity · cumulative meter','Warmwasserspeicher':'Hot water tank','Heizkörper · Vorlauf':'Radiators · flow','Heizkörper · Rücklauf':'Radiators · return','Außen':'Outdoor',
  'Kumulierter Energiezähler, keine momentane Leistung.':'Cumulative energy meter, not instantaneous power.','Vorhandene Home-Assistant-Entität auswählen.':'Select an existing Home Assistant entity.','Verwerfen':'Discard','Zuordnungen speichern':'Save mappings','Zuordnungen gespeichert.':'Mappings saved.',
  'Zusatzpumpenregelung':'Auxiliary pump control','Ein eigener Eintrag innerhalb der R290-Integration':'A separate entry within the R290 integration','Einrichtung in zwei Schritten: Sensoren und Stellglied zuordnen, danach Betriebsgrenzen und Inbetriebnahme festlegen. Die Reihenfolge der Wärmepumpen muss in allen Sensorlisten übereinstimmen.':'Setup has two steps: map sensors and actuator, then define operating limits and commissioning. Use the same heat pump order in every sensor list.','Regler einrichten / Optionen ↗':'Set up controller / options ↗',
  'Integration & Daten':'Integration & data','Gemeinsame Datenbasis für Anzeige und Regelung':'Shared data for display and control','Konfigurationseinträge':'Configuration entries','Recorder-Verlauf':'Recorder history','Verläufe verwenden die in Home Assistant vorhandene Aufbewahrungsdauer. InfluxDB wird von dieser Oberfläche nicht direkt abgefragt.':'History uses the retention period available in Home Assistant. This interface does not query InfluxDB directly.',
  'Namen oder Entity-ID suchen / einfügen':'Search / paste a name or entity ID','Automatische Zuordnung / nicht hinterlegt':'Automatic mapping / not specified','Keine passende Entität gefunden.':'No matching entity found.','Bitte einen Treffer auswählen oder eine passende Entity-ID einfügen. Leer bedeutet automatische Zuordnung.':'Select a result or paste a matching entity ID. Leave empty for automatic mapping.',
  'Parameter & Kurven.':'Parameters & curves.','Vier Kurven, klare Stützpunkte und Gerätewerte mit dokumentierten Defaults.':'Four curves, clear control points and device values with documented defaults.','Bearbeitung freigeben':'Enable editing','Bearbeitung freigegeben':'Editing enabled','Parameterbereich':'Parameter section','Kurveneinstellungen':'Curve settings','Geräteparameter':'Device parameters','Basis':'Base curve','PV & Anhebung':'PV & offsets','Feinabstimmung':'Fine tuning','Kurveneintrag':'Curve entry','Regelung aktiv':'Control active','Regelung aus':'Control off','Status unbekannt':'State unknown',
  'Außen · kalter Stützpunkt':'Outdoor · cold point','Soll · am kalten Stützpunkt':'Setpoint · at cold point','Außen · warmer Stützpunkt':'Outdoor · warm point','Soll · am warmen Stützpunkt':'Setpoint · at warm point','Kurvenregelung':'Curve control','PV-Optimierung':'PV optimization','PV-Schwelle 1 · kW':'PV threshold 1 · kW','Offset ab Schwelle 1':'Offset above threshold 1','PV-Schwelle 2 · kW':'PV threshold 2 · kW','Offset ab Schwelle 2':'Offset above threshold 2','Batterieschwelle · %':'Battery threshold · %','Batterie-Offset':'Battery offset','Rücksetzschwelle · kW':'Reset threshold · kW','PV-Haltezeit · min':'PV hold time · min','Externe Anhebung':'External offset','Externer Offset · °C':'External offset · °C','Externe Haltezeit · min':'External hold time · min','Sollwert glätten · Stunden':'Setpoint smoothing · hours','Mindeständerung · °C':'Minimum change · °C',
  'Außen · zugeordnete Quelle':'Outdoor · mapped source','Basissoll':'Base setpoint','Basissoll · Vorschau':'Base setpoint · preview','Gespeicherte Basiskurve':'Saved base curve','Entwurf':'Draft','Außentemperatur →':'Outdoor temperature →','Keine ungespeicherten Änderungen':'No unsaved changes','Änderung prüfen →':'Review changes →',
  'Die Vorschau zeigt die lineare Basiskurve mit Begrenzung an den Stützpunkten. PV-Offset, externe Anhebung, Sollwertglättung und Rundung können den ausgegebenen Sollwert verändern.':'The preview shows the linear base curve, clipped at its control points. PV and external offsets, smoothing and rounding can change the resulting setpoint.',
  'Auch die Kühlkurve folgt den konfigurierten Stützpunkten. Die Vorschau kehrt deren Richtung nicht automatisch um.':'The cooling curve also follows the configured control points. The preview does not automatically reverse its direction.',
  '0 = aus. Glättet den Sollwert zeitlich.':'0 = off. Smooths the setpoint over time.','0 = keine Mindeständerung. Kleine Sollwertänderungen werden zurückgehalten.':'0 = no minimum change. Smaller setpoint changes are held back.',
  'Zum Bearbeiten oben „Bearbeitung freigeben“ wählen.':'Select “Enable editing” above to make changes.','Offsets und Freigaben gehören nur zu dieser Kurve. Haltezeiten können die Wirkung über den Auslöser hinaus verlängern.':'Offsets and enable switches apply only to this curve. Hold times may extend their effect beyond the trigger.',
  'Konfiguration inzwischen geändert. Bitte Entwurf verwerfen und neu prüfen.':'Configuration has changed. Discard the draft and review again.','Kurvendaten werden von dieser Backend-Version noch nicht bereitgestellt. Integration aktualisieren und neu laden.':'This backend version does not provide curve data yet. Update and reload the integration.','Für diesen Bereich sind keine verfügbaren Steuerentitäten zugeordnet.':'No available control entities are mapped for this section.','Für diese Kurve ist noch kein Integrationseintrag vorhanden.':'No integration entry exists for this curve yet.',
  'Für die Vorschau fehlen gültige Stützpunkte.':'Valid control points are required for the preview.','Der kalte Außenstützpunkt muss unter dem warmen liegen.':'The cold outdoor point must be below the warm point.',
  'Geräteparameter vergleichen':'Compare device parameters','Default: „Real Default“, falls hinterlegt, sonst Handbuchwert. Aktuelle Werte stammen aus Home Assistant.':'Default uses “Real Default” when available, otherwise the manual value. Current values come from Home Assistant.','Parameter suchen':'Search parameters','Code, Adresse oder Beschreibung suchen …':'Search code, address or description …','Nur Unterschiede':'Differences only','Parameter & Erklärung':'Parameter & explanation','Default':'Default','Erklärung':'Explanation','Adresse nicht zugeordnet':'Address not mapped','Keine Entität':'No entity','In der Excel-Datei ist keine weiterführende Erklärung hinterlegt.':'No further explanation is documented.','Keine passenden Parameter.':'No matching parameters.',
  'Änderungsprotokoll':'Change log','„Gesendet“ bestätigt einen Dienstaufruf; „Konfiguriert“ bestätigt die gespeicherte Kurve. Beides ersetzt keine Geräterückmeldung.':'“Sent” confirms a service call; “Configured” confirms a saved curve. Neither replaces device feedback.','Zeit':'Time','Alt → Neu':'Before → after','Ergebnis':'Result','Gesendet':'Sent','Konfiguriert':'Configured','Fehlgeschlagen':'Failed','Noch keine Änderungen über diese Oberfläche.':'No changes through this interface yet.',
  'Rückmeldung stimmt überein':'Feedback matches','Rückmeldung ausstehend':'Awaiting feedback','Änderung prüfen':'Review change','Kurvenänderung prüfen':'Review curve changes','Einstellung':'Setting','Aktuell':'Current','Neuer Wert':'New value','Abbrechen':'Cancel','Bestätigen':'Confirm',
  'Die Änderungen werden gemeinsam gespeichert. Bei aktiver Kurvenregelung können sie anschließend den Sollwert der Wärmepumpe ändern.':'Changes are saved together. If curve control is active, they can then change the heat pump setpoint.',
  'Der Befehl wird an Home Assistant gesendet. Den bestätigten Gerätewert anschließend nach der nächsten Abfrage prüfen.':'The command is sent to Home Assistant. Check the confirmed device value after the next poll.',
  'Kurve gespeichert. Der Integrationseintrag wird neu geladen; ausgegebenen Sollwert anschließend prüfen.':'Curve saved. The integration entry is reloading; check the resulting setpoint afterwards.','Befehl gesendet. Geräterückmeldung ausstehend.':'Command sent. Awaiting device feedback.','Bitte Kurvenentwurf zuerst speichern oder verwerfen.':'Save or discard the curve draft first.','Bitte die geänderten Zuordnungen zuerst speichern oder verwerfen.':'Save or discard the changed mappings first.',
  'Pumpenbetrieb ändern':'Change pump mode','Fester Stellwert in %':'Fixed speed in %','Die Regelung gibt die Steuerung ab. Der letzte Ausgangswert bleibt bestehen. Eine bisherige Automation wird nicht automatisch aktiviert.':'The controller releases control. The last output is retained. Previous automations are not enabled automatically.','Diese Betriebsart sendet Stellbefehle an die Zusatzpumpe. Die bestätigten Betriebsgrenzen gelten; bekannte konkurrierende Automationen müssen deaktiviert sein.':'This mode sends commands to the auxiliary pump. Confirmed operating limits apply; known competing automations must be disabled.','Pumpenbetriebsart übernommen.':'Pump mode updated.',
  'Konfiguration geändert. Entwurf verwerfen und neu prüfen.':'Configuration changed. Discard the draft and review again.','Wert seit Vorschau geändert oder nicht verfügbar. Entwurf verwerfen und erneut prüfen.':'Value changed since preview or is unavailable. Discard the draft and review again.','Wert außerhalb der Entitätsgrenzen':'Value outside entity limits','Wert passt nicht zur Schrittweite':'Value does not match the step size','PV-Schwelle 1 darf Schwelle 2 nicht überschreiten':'PV threshold 1 must not exceed threshold 2','Registerkatalog konnte nicht geladen werden.':'Could not load the register catalog.',
};

Object.assign(EN, {
  'Stützpunkte':'Control points', 'Außen · °C':'Outdoor · °C', 'Soll · °C':'Target · °C',
  '+ Stützpunkt hinzufügen':'+ Add control point', 'Außen → Soll':'Outdoor → target',
  '2–10 Punkte. Zwischenwerte werden linear berechnet; außerhalb gelten die Endwerte. Punkte ziehen oder mit den Pfeiltasten verschieben.':'2–10 points. Values between points are interpolated linearly; end values apply outside the curve. Drag points or use the arrow keys.',
  'Die Vorschau zeigt die Basiskurve. PV-Offset, externe Anhebung, Sollwertglättung und Rundung können den ausgegebenen Sollwert verändern.':'The preview shows the base curve. PV offset, external offset, smoothing and rounding may change the resulting setpoint.',
  'Eine Kurve benötigt 2 bis 10 Stützpunkte':'A curve requires 2 to 10 control points',
  'Kurvenwerte müssen endliche Zahlen sein':'Curve values must be finite numbers',
  'Jeder Stützpunkt benötigt Außen- und Solltemperatur':'Each point requires an outdoor temperature and a target temperature',
  'Stützpunkt außerhalb des zulässigen Temperaturbereichs':'Control point outside the permitted temperature range',
  'Stützpunkte benötigen Schritte von 0,1 °C':'Control points require steps of 0.1 °C',
  'Außentemperaturen müssen von kalt nach warm eindeutig ansteigen':'Outdoor temperatures must increase strictly from cold to warm',
  'Stützpunkte und alte Endpunktfelder nicht gleichzeitig ändern':'Do not change control points and legacy endpoint fields in the same request',
});

const DE_ERRORS={
  'Administrator access required':'Administratorrechte erforderlich',
  'Value changed since preview; review again':'Wert seit der Vorschau geändert. Bitte erneut prüfen.',
  'Parameter is unavailable':'Parameter nicht verfügbar',
  'Value outside entity limits':'Wert außerhalb der Entitätsgrenzen',
  'Value does not match entity step':'Wert passt nicht zur Schrittweite der Entität',
  'Unsupported parameter action':'Nicht unterstützte Parameteraktion',
  'Confirm the parameter change':'Parameteränderung bestätigen',
  'Pump entry is not loaded':'Pumpeneintrag nicht geladen',
  'Confirm the requested pump mode':'Angeforderte Pumpenbetriebsart bestätigen',
  'Use the dedicated pump control for this entity':'Für diese Entität die eigene Pumpensteuerung verwenden',
  'Unknown setting':'Unbekannte Einstellung',
  'Name must be at most 100 characters':'Der Name darf höchstens 100 Zeichen enthalten',
};
export function tr(value, language='de'){
  if(language!=='en'){const raw=String(value??''),s=raw.trim();return DE_ERRORS[s]?raw.replace(s,DE_ERRORS[s]):raw;}
  const raw=String(value??''),s=raw.trim();
  if(EN[s])return raw.replace(s,EN[s]);
  let t=s;
  const patterns=[
    [/^Stützpunkt (\d+) (verschieben|entfernen)$/,(_,n,verb)=>`${verb==='verschieben'?'Move':'Remove'} control point ${n}`],
    [/^(Außen|Soll) · Stützpunkt (\d+)$/,(_,label,n)=>`${label==='Außen'?'Outdoor':'Target'} · control point ${n}`],
    [/^Kurve ein- oder ausblenden: (.+)$/,(_,id)=>`Show or hide series: ${tr(id,'en')}`],
    [/^(\d+) Wärmepumpen eingerichtet$/,(_,n)=>`${n} heat pumps configured`],
    [/^(.+) · Recorder · Datenlücken unterbrechen die Linie\.$/,(_,period)=>`${period} · Recorder · data gaps break the line.`],
    [/^R290 \/ (.+)$/,(_,section)=>`R290 / ${tr(section,'en')}`],
    [/^(Zwei|\d+) Wärmepumpen in Parallelschaltung · Trinkwarmwasser und Heizungspuffer$/,(_,n)=>`${n==='Zwei'?'Two':n} heat pumps in parallel · domestic hot water and heating buffer`],
    [/^Regler: (.+)$/,(_,mode)=>`Controller: ${tr(mode,'en')}`],
    [/^(\d+) von (\d+) Verdichtern aktiv$/,(_,a,b)=>`${a} of ${b} compressors active`],
    [/^(\d+) Konflikt\(e\)$/,(_,n)=>`${n} conflict(s)`],
    [/^Wärmepumpe (\d+)$/,(_,n)=>`Heat pump ${n}`],[/^WP (\d+) · (.+)$/,(_,n,rest)=>`HP ${n} · ${tr(rest,'en')}`],[/^WP (\d+)$/,(_,n)=>`HP ${n}`],
    [/^(Vorlauf|Rücklauf) · WP (.+)$/,(_,kind,n)=>`${EN[kind]} · HP ${n}`],
    [/^(Heizkörper|Warmwasser|Fußbodenheizung|Kühlung) · Basiskurve$/,(_,label)=>`${EN[label]} · base curve`],
    [/^(Heizkörper|Warmwasser|Fußbodenheizung|Kühlung) einrichten$/,(_,label)=>`Set up ${EN[label].toLowerCase()}`],
    [/^Quelle außen: (.+)$/,(_,id)=>`Outdoor source: ${id==='Nicht zugeordnet'?'Not mapped':id}`],
    [/^(\d+) Änderung(?:en)? im Entwurf$/,(_,n)=>`${n} draft change${n==='1'?'':'s'}`],
    [/^(\d+) Parameter$/,(_,n)=>`${n} parameters`],[/^(\d+) Einträge$/,(_,n)=>`${n} entries`],[/^(\d+) Tage$/,(_,n)=>`${n} days`],
    [/^(.+) Liter Speichervolumen$/,(_,n)=>`${n} litres tank volume`],
    [/^vor (.+) Min\.$/,(_,n)=>`${n} min ago`],[/^vor (.+) Std\.$/,(_,n)=>`${n} h ago`],[/^vor (.+) Tagen$/,(_,n)=>`${n} days ago`],
    [/^(.+) Min\.$/,(_,n)=>`${n} min`],[/^(.+) Std\.$/,(_,n)=>`${n} h`],
    [/^Letzte Zustandsänderung (.+)$/,(_,rest)=>`Last state change ${tr(rest,'en')}`],
    [/^(\d+) Treffer · erste 60 angezeigt\. Suche weiter eingrenzen\.$/,(_,n)=>`${n} results · first 60 shown. Refine your search.`],
    [/^(\d+) Treffer · ↑ ↓ auswählen · Enter übernehmen · Esc schließen$/,(_,n)=>`${n} results · ↑ ↓ select · Enter apply · Esc close`],
    [/^(.+): Auswahl öffnen$/,(_,label)=>`${tr(label,'en')}: open selection`],
    [/^(\d+) Zählerrücksetzungen erkannt$/,(_,n)=>`${n} meter resets detected`],
    [/^Größtes Änderungsintervall: (.+)$/,(_,n)=>`Longest interval between changes: ${n}`],
    [/^(.+) · rollierender Zeitraum$/,(_,n)=>`${n} · rolling period`],
  ];
  for(const [pattern,replace] of patterns)if(pattern.test(t)){t=t.replace(pattern,replace);break;}
  t=t.replace(/Zustandsabdeckung/g,'state coverage').replace(/ · Bereich /g,' · range ').replace(/ bis /g,' to ').replace(/ · interner Wärmetauscher/g,' · internal heat exchanger').replace(/ · Plattenwärmetauscher → Heizkörper/g,' · plate heat exchanger → radiators');
  return raw.replace(s,t);
}

const originals=new WeakMap();
export function translateTree(root,language){
  if(!root)return;
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){
    const node=walker.currentNode;if(node.parentElement?.closest('style,script,[data-no-translate]'))continue;
    const old=originals.get(node),source=old?.output===node.textContent?old.source:node.textContent;
    const output=tr(source,language);if(output!==node.textContent)node.textContent=output;originals.set(node,{source,output});
  }
  for(const element of root.querySelectorAll('[aria-label],[placeholder],[title]')){
    const saved=originals.get(element)||{};
    for(const key of ['aria-label','placeholder','title'])if(element.hasAttribute(key)){
      const value=element.getAttribute(key),old=saved[key],source=old?.output===value?old.source:value;
      const output=tr(source,language);element.setAttribute(key,output);saved[key]={source,output};
    }
    originals.set(element,saved);
  }
}
