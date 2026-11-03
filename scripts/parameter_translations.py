"""Bilingual presentation of the supplied register tables, without new mappings.

Applied by register_catalog.py. Unknown and conflicting rows stay explicit.
These explanations describe register meaning, not verified firmware behaviour.
"""
import re

def fields(name_de, name_en, de, en):
    return dict(name_de=name_de, display_name_en=name_en, description_de=de, description_en=en)

REALTIME = [
    ('Verdichterfrequenz','Compressor frequency','Gemeldete Betriebsfrequenz des Verdichters. 0 Hz bedeutet keinen gemeldeten Verdichterlauf; die Wasserpumpe kann trotzdem laufen.','Reported compressor operating frequency. 0 Hz means no reported compressor operation; the water pump may still run.'),
    ('Lüfterdrehzahl','Fan speed','Gemeldete Lüfterdrehzahl. Die Tabelle bezeichnet den Wert als Frequenz/Drehzahl; die angezeigte Einheit ist maßgeblich.','Reported fan speed. The table calls this frequency/speed; use the displayed unit.'),
    ('Haupt-Expansionsventil · Schritte','Main expansion valve · steps','Gemeldete Öffnung des elektronischen Haupt-Expansionsventils in Schritten. Kein hydraulisches Wasserventil.','Reported main electronic expansion-valve opening in steps. Not a hydraulic water valve.'),
    ('EVI-Expansionsventil · Schritte','EVI expansion valve · steps','Gemeldete Öffnung des EVI-/Hilfs-Expansionsventils in Schritten. Nur bei entsprechend ausgestatteten Geräten relevant.','Reported EVI/auxiliary expansion-valve opening in steps. Relevant only for equipped units.'),
    ('AC-Eingangsspannung','AC input voltage','Vom Antrieb gemeldete Wechselspannung am Eingang.','AC input voltage reported by the drive.'),
    ('AC-Eingangsstrom','AC input current','Vom Antrieb gemeldeter Eingangsstrom. Laut Tabelle wird der Rohwert durch 10 geteilt; die Entität übernimmt diese Skalierung.','Input current reported by the drive. The table specifies raw value divided by 10; the entity applies this scaling.'),
    ('Verdichter-Phasenstrom','Compressor phase current','Gemeldeter Strom einer Verdichterphase; nicht mit dem Gesamtstrom der Anlage gleichsetzen. Laut Tabelle Skalierung 1/10.','Reported compressor phase current, not total plant current. Table scaling is 1/10.'),
    ('IPM-Temperatur','IPM temperature','Temperatur des intelligenten Leistungsmoduls im Verdichterantrieb. Kein Wasserfühler.','Temperature of the intelligent power module in the compressor drive. Not a water sensor.'),
    ('Hochdruck-Sättigungstemperatur','High-pressure saturation temperature','Aus dem Hochdruck abgeleitete Kältemittel-Sättigungstemperatur; keine direkte Vorlaufmessung.','Refrigerant saturation temperature derived from high-side pressure; not a direct supply-water measurement.'),
    ('Niederdruck-Sättigungstemperatur','Low-pressure saturation temperature','Aus dem Niederdruck abgeleitete Kältemittel-Sättigungstemperatur; keine Außenluftmessung.','Refrigerant saturation temperature derived from low-side pressure; not an ambient-air measurement.'),
    ('Außentemperatur T1','Ambient temperature T1','Temperatur am Außenluftfühler T1 der Wärmepumpe. Die örtliche Fühlerposition kann den Messwert beeinflussen.','Heat-pump outdoor-air sensor T1. Local sensor placement can affect the reading.'),
    ('Außenwärmetauscher T2','Outdoor coil temperature T2','Rohr-/Lamellentemperatur des Außenwärmetauschers. Von der Lufttemperatur zu unterscheiden.','Outdoor heat-exchanger tube/fin temperature, distinct from air temperature.'),
    ('Plattenwärmetauscher T3','Plate heat-exchanger temperature T3','Temperatur am internen Plattenwärmetauscher laut Fühlerbezeichnung. Nicht automatisch ein externer Heizkreisfühler.','Internal plate heat-exchanger temperature according to the sensor designation. Not automatically an external heating-circuit sensor.'),
    ('Sauggastemperatur T4','Suction-gas temperature T4','Temperatur am Kältemittel-Rücklauf zum Verdichter (Sauggas). Die englische Tabelle nennt dies „Return air“; kein Raumluftfühler.','Refrigerant suction-gas temperature returning to the compressor. The table says “Return air”; this is not room air.'),
    ('Heißgastemperatur T5','Discharge-gas temperature T5','Kältemitteltemperatur nach dem Verdichter. Nicht die Vorlauftemperatur des Heizwassers.','Refrigerant temperature after the compressor, not heating-water supply temperature.'),
    ('Wasserrücklauf T6','Return-water temperature T6','Wassereintritt in die Wärmepumpe. Zusammen mit T7 zur Beurteilung der Wasserspreizung verwenden.','Water entering the heat pump. Compare with T7 to assess water-side temperature difference.'),
    ('Wasservorlauf T7','Outlet-water temperature T7','Wasseraustritt aus der Wärmepumpe. Im Warmwasserbetrieb ist dies das Heizwasser, nicht die Trinkwassertemperatur.','Water leaving the heat pump. In DHW mode this is heating water, not the domestic hot-water temperature.'),
    ('Economizer-Eintritt T8','Economizer inlet temperature T8','Rohrtemperatur am Eintritt des Economizers im Kältekreis, sofern vorhanden.','Economizer inlet-tube temperature in the refrigerant circuit, where fitted.'),
    ('Economizer-Austritt T9','Economizer outlet temperature T9','Rohrtemperatur am Austritt des Economizers im Kältekreis, sofern vorhanden.','Economizer outlet-tube temperature in the refrigerant circuit, where fitted.'),
]
EXTRA = {
  0x53:('Gerätekennung','Device tooling number','Gemeldete Geräte-/Toolingkennung. Sie ist weder Seriennummer noch eine gesicherte Firmwareversion.','Reported device/tooling identifier. It is neither a serial number nor a verified firmware version.'),
  0x54:('Warmwasserspeichertemperatur','DHW tank temperature','Temperatur am zugeordneten Speicherfühler. Ein einzelner Fühler beschreibt nicht die gesamte Temperaturschichtung.','Temperature at the assigned tank sensor. One sensor does not describe the whole temperature stratification.'),
  0x55:('Kältemittelaustritt Plattenwärmetauscher','Plate heat-exchanger refrigerant outlet','Kältemitteltemperatur am Austritt des Plattenwärmetauschers laut Registertabelle. Kein Heizwasser-Rücklauf.','Refrigerant outlet temperature of the plate heat exchanger according to the register table. Not heating-water return.'),
  0x56:('Antriebshersteller · Kennung','Drive manufacturer code','Vom Gerät gemeldeter Hersteller-Code des Antriebs. Eine vollständige Codetabelle liegt nicht vor.','Device-reported drive manufacturer code. A complete code table is not available.'),
  0x58:('Wasserdurchfluss','Water flow','Gemeldeter Wasserdurchfluss dieser Wärmepumpe in l/min. Bei einer Kaskade nicht ungeprüft als Gesamtdurchfluss verwenden.','Reported water flow for this heat pump in l/min. Do not assume this is total cascade flow.'),
  0x59:('Nutzerrücklauf-Temperatur','User return-water temperature','Zusätzlicher Rücklauf-/Zirkulationsfühler laut Tabelle. Die konkrete hydraulische Zuordnung muss zur Anlage passen.','Additional return/circulation temperature sensor according to the table. Its hydraulic assignment depends on the installation.'),
  0x5A:('Geräteeingangsspannung','Unit input voltage','Vom Gerät gemeldete Eingangsspannung. Von der separaten Antriebsmessung zu unterscheiden.','Unit-reported input voltage, distinct from the separate drive reading.'),
  0x5B:('Geräteeingangsstrom','Unit input current','Vom Gerät gemeldeter Eingangsstrom. Messumfang und Phasenzuordnung anhand der konkreten Hardware prüfen.','Unit-reported input current. Check measurement scope and phase assignment for the installed hardware.'),
  0x5C:('Elektrische Eingangsleistung','Electrical input power','Vom Gerät gemeldete elektrische Leistung. Kein Wärmeertrag; bei externen Zählern gleiche Bilanzgrenzen prüfen.','Unit-reported electrical power. Not heat output; check matching measurement boundaries when comparing external meters.'),
  0x5D:('Elektrischer Energiezähler','Electrical energy counter','Vom Gerät gemeldeter kumulierter Stromverbrauch. Zählerdifferenzen ergeben Energiezuwächse; Rücksetzungen berücksichtigen.','Unit-reported cumulative electricity consumption. Differences yield energy increments; account for resets.'),
  0x72:('Zusatzwärmequelle · Warmwasserfühler','Auxiliary heat source · DHW sensor','Temperaturfühler für die Warmwasserseite der zusätzlichen Wärmequelle. Nur bei entsprechendem Anschluss auswerten.','DHW-side temperature sensor of the auxiliary heat source. Evaluate only when appropriately connected.'),
  0x73:('Zusatzwärmequelle · Heizungsfühler','Auxiliary heat source · heating sensor','Temperaturfühler für die Heizungsseite der zusätzlichen Wärmequelle. Nicht automatisch die Temperatur des Wärmepumpenvorlaufs.','Heating-side temperature sensor of the auxiliary heat source. Not automatically heat-pump supply temperature.'),
  0x74:('Heizungspuffer T10','Heating buffer T10','Temperatur am Pufferfühler T10. Seine Verwendung in der Regelung hängt von der Gerätekonfiguration ab.','Buffer sensor T10 temperature. Its role in control depends on device configuration.'),
  0x75:('Gemeinsamer Wasservorlauf','Common outlet-water temperature','Gemeldete Temperatur am gemeinsamen Wasseraustritt. Fühleranschluss und Einbauposition entscheiden über die Aussage.','Reported common water-outlet temperature. Meaning depends on sensor connection and installation position.'),
  0x76:('Eingangsspannung Phase B','Phase B input voltage','Vom Gerät gemeldete Eingangsspannung der Phase B.','Unit-reported phase B input voltage.'),
  0x77:('Eingangsstrom Phase B','Phase B input current','Vom Gerät gemeldeter Eingangsstrom der Phase B.','Unit-reported phase B input current.'),
  0x78:('Eingangsspannung Phase C','Phase C input voltage','Vom Gerät gemeldete Eingangsspannung der Phase C.','Unit-reported phase C input voltage.'),
  0x79:('Phase C · Zuordnung widersprüchlich','Phase C · conflicting designation','Die Tabelle nennt nochmals Phase-C-Spannung; die Integrationszuordnung kann davon abweichen. Ohne Bestätigung nicht als gesicherten Strom- oder Spannungswert verwenden.','The table repeats phase C voltage; the integration assignment may differ. Do not treat this as a verified current or voltage without confirmation.'),
  0x7A:('Smart-Grid-Status','Smart Grid status','Gemeldeter Zustand der Smart-Grid-Funktion. Eine vollständig belegte Codetabelle ist hier nicht hinterlegt.','Reported Smart Grid state. A fully verified code table is not available here.'),
  0x7B:('Mischventil Zone 2 · Öffnung','Zone 2 mixing-valve opening','Gemeldeter Öffnungswert des Mischventils der zweiten Temperaturzone. Eine echte Positionsrückmeldung ist damit nicht nachgewiesen.','Reported opening value of the second temperature-zone mixing valve. This does not prove physical position feedback.'),
  0x7C:('Mischtemperatur Zone 1','Zone 1 mixed-water temperature','Gemeldete Mischwassertemperatur der Zone 1 laut Registertabelle.','Reported zone 1 mixed-water temperature according to the register table.'),
  0x7D:('Mischventil Zone 1 · Öffnung','Zone 1 mixing-valve opening','Gemeldeter Öffnungswert des Mischventils der ersten Temperaturzone. Nicht automatisch eine gemessene Ventilposition.','Reported opening value of the first temperature-zone mixing valve. Not automatically a measured valve position.'),
}

BIT_DE = {
  0:['Kältemittelrückgewinnung','Frostschutz Stufe 1','Frostschutz Stufe 2','Fehlerwarnung','Ölrückführung System 1','','','','Abtauung','','','','Abschaltung bei Solltemperatur','Schutzabschaltung bei Fehler','Gerät in Betrieb','Gerät wartet auf Start'],
  1:['Hochtemperatur-Desinfektion','Temperaturhaltephase der Desinfektion','','','','','','','','','Regler ein/aus'],
  2:['Falsche Phasenfolge','Phasenausfall','Wasserdurchflussfehler','Kommunikationsfehler','Notfallfehler','Nutzungszeit abgelaufen','Speicherfühler unten defekt','Wassereintrittsfühler defekt','Raumfühler defekt','Außenfühler defekt','Nutzerrücklauffühler defekt','Kühlaustritt zu niedrig (Tabellentext unklar)','Wasserstandsschalterfehler','Wasseraustrittsfühler defekt','Heizaustritt zu hoch (Tabellentext unklar)','Wasserspreizung zu groß'],
  3:['Schutz bei niedriger Außentemperatur','','','','','','Raumfeuchtefühler defekt','','','','','Phasenfolge-DIP-Einstellung fehlerhaft','','Rückmeldung Wasserpumpe 1 fehlerhaft','Rückmeldung Wasserpumpe 2 fehlerhaft','Schutz bei geringem Wasserdurchfluss'],
  4:['Phasenfolgesignal unterbrochen','Kommunikation Erweiterungsplatine','Plattenwärmetauscherfühler defekt','Kommunikation Lüfter 1','Kommunikation Lüfter 2','Gerätemodelle nicht kompatibel','Warmwasserfühler Zusatzwärmequelle defekt','Heizungsfühler Zusatzwärmequelle defekt','Pufferfühler defekt','Gemeinsamer Vorlauffühler defekt'],
  5:['Hochdruckschalter-Schutz','Niederdruckschalter-Schutz','Hochdruck zu hoch','Niederdruck zu niedrig','Heißgastemperatur-Schutz','Überstromschutz','Wärmetauscher-Temperaturschutz','Wärmetauscherfühler defekt','Sauggasfühler defekt','Heißgasfühler defekt','Economizer-Eintrittsfühler defekt','Economizer-Austrittsfühler defekt','Kommunikation Lüfterantrieb','DC-Lüfterfehler','Kältekreis-Wärmetauscherfühler defekt'],
  6:['Hochdrucksensor defekt','Niederdrucksensor defekt','Mitteldruckschalterfehler','Wärmetauschertemperatur zu hoch','Kommunikation Verdichterantrieb'],
  7:['IPM-Überstrom / Modulschutz','Verdichterantriebsfehler','Verdichter-Überstrom','Eingangsphase fehlt','IPM-Strommessfehler','Leistungsbauteile überhitzt','Vorladung fehlgeschlagen','DC-Zwischenkreis-Überspannung','DC-Zwischenkreis-Unterspannung','AC-Eingangsunterspannung','AC-Eingangsüberstrom','Eingangsspannungsmessfehler','Kommunikation DSP/PFC','Kühlkörperfühler defekt','Kommunikation DSP/Kommunikationsplatine','Kommunikation Hauptplatine'],
  8:['Verdichter-Überstromwarnung','Feldschwächungsschutz Verdichter','PIM-Übertemperaturwarnung','PFC-Übertemperaturwarnung','AC-Eingangsüberstromwarnung','EEPROM-Fehlerwarnung','','EEPROM-Aktualisierung abgeschlossen','Frequenzbegrenzung bei Temperaturfühlerfehler','Frequenzbegrenzung bei AC-Unterspannung'],
  9:['IPM thermisch abgeschaltet','Verdichter-Phasenausfall','Verdichterüberlast','Eingangsstrommessfehler','PIM-Versorgungsspannungsfehler','Vorladekreis-Spannungsfehler','EEPROM-Fehler','AC-Eingangsüberspannung','Mikroelektronikfehler','Verdichter-Modellcodefehler','Überstrom des Strommesssignals'],
  25:['Warmwasser-Heizstab','Lüfter hohe Stufe','','Lüfter niedrige Stufe','Heizungs-Heizstab','Fußbodenheizungs-Heizstab','Interne Umwälzpumpe','','','Kurbelgehäuseheizung','Bodenwannenheizung','Zirkulationsventil/-pumpe','','','Heizungs-Magnet-/Dreiwegeventil','Fußbodenheizungs-Magnet-/Dreiwegeventil'],
  26:['Verdichter 1','Flüssigkeitseinspritzventil 1','EVI-Magnetventil 1','Vierwegeventil 1','Drossel-Bypassventil 1','Lüfter 1','','','Zusatzheizungspumpe','','Verdichter 2','Flüssigkeitseinspritzventil 2','EVI-Magnetventil 2','Vierwegeventil 2'],
  27:['','','','','','','Speicherheizelement (Tabellenbezeichnung)','Warmwasserpumpe Zusatzwärmequelle','Heizungspumpe Zusatzwärmequelle','Gas-Freigabeausgang'],
  28:['Rohrheizung 1','Rohrheizung 2'],
  29:['SW1','SW2','SW3','SW4','SW5','SW6','SW7','SW8','Strömungsschalter','','Heizungs-Verknüpfungskontakt','Warmwasser-Verknüpfungskontakt','Verknüpfungskontakt','Notfallkontakt'],
  30:['','','','','','','','Hochdruckschalter 1','Niederdruckschalter 1','Mitteldruckschalter 1','Hochdruckschalter 2','Niederdruckschalter 2','Mitteldruckschalter 2'],
  31:['','','','','','Zusatzheizungs-Verknüpfungskontakt'],32:[],
}

def apply(records):
    for r in records:
        section,addr=r['section'],r['address']
        if section==4:
            continue
        if r['unknown']:
            r.update(fields('Unbekanntes Register','Unknown register','Bedeutung, Skalierung und Verwendung sind in der vorliegenden Registertabelle nicht dokumentiert. Ein empfangener Rohwert belegt keine bestimmte Funktion.','Meaning, scaling and use are not documented in the supplied register table. Receiving a raw value does not establish a specific function.'))
            continue
        if section==1:
            if addr<2: de,en=f'Betriebsstatus {addr+1}',f'Running status {addr+1}'
            elif addr<5: de,en=f'Fehlerstatus {addr-1}',f'Fault status {addr-1}'
            elif addr<25:
                system=(addr-5)//5+1;kind=(addr-5)%5
                de=f'System {system} · '+(f'Fehlerstatus {kind+1}' if kind<2 else f'Antriebsfehler {kind-1}')
                en=f'System {system} · '+(f'Fault status {kind+1}' if kind<2 else f'Drive fault status {kind-1}')
            elif addr<29: de,en=f'Relaisausgänge {addr-24}',f'Relay outputs {addr-24}'
            elif addr<33: de,en=f'Schalteingänge {addr-28}',f'Switch inputs {addr-28}'
            elif addr==0x24: de,en='Geräte-/Toolingkennung','Device tooling number'
            else: de,en=f'Verdichter {addr-0x26} · Sollfrequenz',f'Compressor {addr-0x26} · target frequency'
            if r.get('bits'):
                key=5+(addr-5)%5 if 5<=addr<25 else addr
                labels=BIT_DE[key]
                r['bits_de']='\n'.join(f'Bit {i}: {labels[i] if i<len(labels) and labels[i] else "Reserviert / nicht beschrieben"}' for i in range(16))
                enlabels={int(i):s.strip(' :\t"') for i,s in re.findall(r'Bit(\d+)[ \t]*:?[\t ]*([^\n]*)',r['bits'])}
                r['bits_en']='\n'.join(f'Bit {i}: {enlabels.get(i) or "Reserved / undocumented"}' for i in range(16))
                r.update(fields(de,en,'Bitfeld: Jedes Bit meldet einen einzelnen Zustand. Die Zuordnung steht unten; 1 bedeutet gesetzt, 0 nicht gesetzt. Reservierte Bits nicht deuten. Relaisstatus ist keine mechanische Rückmeldung; die Systemnummer bezeichnet nicht automatisch einen Kaskaden-Slave.','Bitfield: each bit reports one state, listed below; 1 means set, 0 clear. Do not interpret reserved bits. Relay state is not mechanical feedback; the system number does not automatically identify a cascade slave.'))
            else:
                explanation=('Geräte-/Toolingkennung, keine bestätigte Firmwareversion.','Device/tooling identifier, not a confirmed firmware version.') if addr==0x24 else ('Vom Regler berechnete Sollfrequenz dieses Verdichters; nicht die gemessene Betriebsfrequenz.','Controller-calculated target frequency for this compressor, not measured operating frequency.')
                r.update(fields(de,en,*explanation))
        elif section==2:
            if addr==0x57: continue  # Existing normalized pump/PWM explanation.
            if 0x40<=addr<=0x52:
                r.update(fields(*REALTIME[addr-0x40]))
            elif 0x5e<=addr<=0x6d:
                index=[0,1,2,3,4,5,6,7,8,9,11,12,13,14,17,18][addr-0x5e]
                de,en,d,e=REALTIME[index]
                r.update(fields('System 2 · '+de,'System 2 · '+en,d+' Systemblock 2 ist nicht automatisch Slave 2 der Kaskade.',e+' System block 2 does not automatically mean cascade slave 2.'))
            elif addr in EXTRA:r.update(fields(*EXTRA[addr]))
            elif 0xfa<=addr<=0xff:
                mode,mode_en=[('Heizung/Fußbodenheizung','heating/underfloor heating'),('Warmwasser','DHW'),('Kühlung','cooling')][(addr-0xfa)//2]
                bound,bound_en=('Obergrenze','Upper limit') if addr%2==0 else ('Untergrenze','Lower limit')
                r.update(fields(f'{bound} Solltemperatur · {mode}',f'{bound_en} set temperature · {mode_en}',f'Vom Gerät gemeldete {bound.lower()} des Solltemperaturbereichs für {mode}. Kein aktueller Temperaturmesswert.',f'Device-reported {bound_en.lower()} of the set-temperature range for {mode_en}. Not a live temperature reading.'))
        elif section==3:
            modes={0x300:('Kühlen','Cooling'),0x301:('Heizen','Heating'),0x302:('Warmwasser','DHW'),0x303:('Fußbodenheizung','Underfloor heating'),0x306:('Raum','Room')}
            if addr in modes:
                de,en=modes[addr];r.update(fields(f'Solltemperatur · {de}',f'{en} set temperature',f'Temperaturvorgabe für {de}. Eine aktive Kurvenregelung oder externe Anhebung kann diesen Sollwert beeinflussen.','Temperature setpoint for '+en.lower()+'. An active curve controller or external offset can affect this setpoint.'))
            elif addr==0x304:r.update(fields('Betriebsart wählen','Select operating mode','Gewünschte Betriebsart, nicht zwingend die gerade aktive Phase. 0: Kühlen; 1: Heizen; 2: Warmwasser; 3: Fußbodenheizung; 4: Warmwasser + Kühlen; 5: Warmwasser + Heizen; 6: reserviert; 7: Warmwasser + Fußbodenheizung.','Requested mode, not necessarily the current phase. 0: cooling; 1: heating; 2: DHW; 3: underfloor heating; 4: DHW + cooling; 5: DHW + heating; 6: reserved; 7: DHW + underfloor heating.'))
            elif addr==0x305:r.update(fields('Gerät ein/aus','Unit on/off','Betriebsfreigabe: 0 aus, 1 ein. Aus bedeutet keine sichere elektrische Trennung; Schutzfunktionen können weiter aktiv sein.','Operating enable: 0 off, 1 on. Off is not electrical isolation; protection functions may remain active.'))
            elif addr==0x307:r.update(fields('Leistungsmodus','Power mode','Auswahl des Leistungs-/Geräuschmodus: 0 Standard, 1 hohe Leistung, 2 leise. Die genaue Leistungsbegrenzung hängt von der Firmware ab.','Power/noise mode: 0 standard, 1 high power, 2 silent. Exact output limits depend on firmware.'))
            else:
                de,en={0x313:('Kühlung','Cooling'),0x314:('Heizung','Heating'),0x315:('Warmwasser','DHW'),0x316:('Fußbodenheizung','Underfloor heating')}[addr]
                n=4 if addr==0x315 else 8
                r.update(fields(f'Interne Kurvenauswahl · {de}',f'Internal curve selection · {en}',f'Wählt eine geräteinterne Kurve: 0 aus, 1–{n} Kurvennummer. Dies ist nicht die Mehrpunktkurve der Home-Assistant-Integration.',f'Selects a device-internal curve: 0 off, 1–{n} curve number. This is not the Home Assistant integration’s multipoint curve.'))
        elif section==5:
            values={
              0x800:('Rohrheizung · Zuschaltzeit','Pipe heater · loading time','Zeitparameter für die elektrische Rohrheizung. Der genaue Start-/Rücksetzzeitpunkt ist in der Tabelle nicht beschrieben.','Time parameter for electric pipe heating. The table does not specify exact start/reset conditions.'),
              0x801:('Hochtemperatur-Desinfektion','High-temperature disinfection','Freigabe der Hochtemperatur-Desinfektionsfunktion. Zeitplan, Dauer und Temperatur sind getrennte Parameter; die Freigabe bestätigt keinen erfolgreichen Zyklus.','Enables high-temperature disinfection. Schedule, duration and temperature are separate parameters; enablement does not prove a successful cycle.'),
              0x802:('Desinfektion · Intervalltage','Disinfection · interval days','Tagesintervall zwischen geplanten Desinfektionszyklen. Wirkung setzt eine freigegebene Funktion voraus.','Day interval between scheduled disinfection cycles. Requires the function to be enabled.'),
              0x803:('Desinfektion · Startzeit','Disinfection · start time','Geplanter Startzeitpunkt der geräteinternen Desinfektion. Uhrzeitformat und Geräteeinstellung beachten.','Scheduled start time of device-controlled disinfection. Check time encoding and device settings.'),
              0x804:('Desinfektion · Laufzeit','Disinfection · runtime','Zeitvorgabe für den Desinfektionsablauf. Die Tabelle allein bestätigt keine tatsächliche Haltezeit an allen Zapfstellen.','Time setting for the disinfection sequence. The table alone does not establish actual holding time at all draw-off points.'),
              0x805:('Desinfektion · Solltemperatur','Disinfection · set temperature','Temperatursollwert der Hochtemperatur-Desinfektion. Ein Sollwert belegt nicht, dass alle Speicherbereiche diese Temperatur erreichen.','Temperature setpoint for high-temperature disinfection. A setpoint does not prove every tank zone reaches it.'),
              0x80b:('Warmwasserzirkulation · Modus','DHW circulation · mode','Geräteinterne Zirkulationsfunktion: 0 deaktiviert, 1 dauerhaft, 2 zyklisch, 3 nach Temperaturdifferenz. Die bisherige Schalterentität bildet nur 0/1 ab. Nicht mit der internen Wärmepumpenumwälzung verwechseln.','Device-controlled DHW circulation: 0 disabled, 1 continuous, 2 cyclic, 3 temperature-difference controlled. The existing switch entity only covers 0/1. Distinct from internal heat-pump water circulation.'),
              0x80c:('Zirkulation · Solltemperatur','Circulation · set temperature','Temperaturvorgabe der Warmwasser-Zirkulationsregelung. Der zugehörige Rücklauffühler muss angeschlossen sein.','Temperature setpoint for DHW circulation control. Requires the associated return sensor.'),
              0x80d:('Zirkulation · Temperaturhysterese','Circulation · temperature hysteresis','Temperaturdifferenz für die Zirkulationsregelung. Keine Zielspreizung des Wärmepumpenladekreises.','Temperature difference used by circulation control. Not the target temperature difference of the heat-pump charging circuit.'),
              0x80e:('Zirkulation · Zyklus','Circulation · cycle','Zeitintervall der zyklischen Warmwasserzirkulation; zusammen mit Modus und Laufzeit betrachten.','Time interval for cyclic DHW circulation; interpret together with mode and runtime.'),
              0x80f:('Zirkulation · Laufzeit','Circulation · runtime','Laufzeitvorgabe der Warmwasserzirkulation. Nicht der Pumpennachlauf der Wärmepumpe.','DHW circulation runtime setting. Not heat-pump pump overrun.'),
              0x1012:('Schnellheizen','Fast heating','Anforderung des Schnellheizmodus als Coil laut Tabelle. Wirkung und verfügbare Zusatzheizung hängen von der Gerätekonfiguration ab.','Fast-heating request documented as a coil. Behaviour and available auxiliary heating depend on device configuration.'),
              0x1013:('Abtauung anfordern','Request defrost','Anforderung einer erzwungenen Abtauung als Coil laut Tabelle. Kein reines Statussignal; Geräteschutzbedingungen können die Ausführung verhindern.','Forced-defrost request documented as a coil. Not a status-only signal; device protection conditions may prevent execution.'),
              0x1018:('Desinfektion anfordern','Request disinfection','Anforderung eines Desinfektionszyklus als Coil laut Tabelle. Nicht die Rückmeldung eines abgeschlossenen Zyklus.','Disinfection-cycle request documented as a coil. Not confirmation of a completed cycle.'),
              0x101a:('Zirkulation freigeben','Enable circulation','Freigabe der Warmwasser-Rücklauf-/Zirkulationsfunktion als Coil laut Tabelle. Keine Freigabe der separaten Zusatzpumpe im Wärmepumpenkreis.','DHW return/circulation enable documented as a coil. Not permission for the separate auxiliary pump in the heat-pump circuit.'),
            }
            r.update(fields(*values[addr]))
        assert all(r.get(key) for key in ['name_de','display_name_en','description_de','description_en']), (section,hex(addr))
