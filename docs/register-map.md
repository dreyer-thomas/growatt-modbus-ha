# Register-Map Growatt SPH 4000–10000TL3 BH-UP

Grundlage: Growatt "Inverter Modbus RTU Protocol" V1.20/V1.24 (Storage-/SPH-Bereich ab 1000).
Gegengeprüft gegen drei unabhängige Implementierungen:

- evcc-Template `growatt-hybrid` (produktiv von vielen SPH-Nutzern eingesetzt)
- HA-Integration `Lu-Fi/ha-growatt-modbus`, Profil `sph_tl3`
- HA-Integration `WouterTuinstra/Homeassistant-Growatt-Local-Modbus` (`storage_120`, `inverter_120`)

Adressen sind 0-basiert (so wie Home Assistant und pymodbus sie erwarten).
32-Bit-Werte: High-Word zuerst (entspricht HA-Standard, kein `swap` nötig).

## Input-Register (Function Code 4) – Messwerte

| Adresse | Typ | Faktor | Einheit | Bedeutung |
|---|---|---|---|---|
| 0 | u16 | 1 | – | Status (0 Warten, 1/2 Normal, 3 Fehler, 4 Update, 5–8 Normal Hybrid) |
| 1 | u32 | 0,1 | W | PV-Leistung gesamt (DC) |
| 3 / 4 | u16 | 0,1 | V / A | PV1 Spannung / Strom |
| 5 | u32 | 0,1 | W | PV1 Leistung |
| 7 / 8 | u16 | 0,1 | V / A | PV2 Spannung / Strom |
| 9 | u32 | 0,1 | W | PV2 Leistung |
| 35 | u32 | 0,1 | W | AC-Ausgangsleistung Wechselrichter |
| 37 | u16 | 0,01 | Hz | Netzfrequenz |
| 38 / 42 / 46 | u16 | 0,1 | V | Spannung L1 / L2 / L3 |
| 40 / 44 / 48 | u32 | 0,1 | W | AC-Leistung L1 / L2 / L3 (nicht im Package) |
| 59 / 63 | u32 | 0,1 | kWh | PV1 / PV2 Energie heute |
| 91 | u32 | 0,1 | kWh | PV-Energie gesamt |
| 93 | u16 | 0,1 | °C | Temperatur Wechselrichter |
| 1000 | u16 | 1 | – | Betriebsmodus (Hybrid) |
| 1001–1007 | u16 | Bitfeld | – | Fehler/Warnungen; 1007 Bit 13 = Meter_COM_Loss |
| 1009 | u32 | 0,1 | W | Batterie-Entladeleistung |
| 1011 | u32 | 0,1 | W | Batterie-Ladeleistung |
| 1013 | u16 | 0,1 | V | Batteriespannung |
| 1014 | u16 | 1 | % | Batterie-SoC |
| 1021 | u32 | 0,1 | W | Netzbezug ("Pactouser") |
| 1029 | u32 | 0,1 | W | Netzeinspeisung ("Pactogrid") |
| 1037 | u32 | 0,1 | W | Hausverbrauch ("PLocalLoad") |
| 1040 | u16 | 1 | °C | Batterietemperatur (Protokoll sagt 0,1 – Praxis 1) |
| 1044 / 1046 | u32 | 0,1 | kWh | Netzbezug heute / gesamt |
| 1048 / 1050 | u32 | 0,1 | kWh | Einspeisung heute / gesamt |
| 1052 / 1054 | u32 | 0,1 | kWh | Batterie-Entladung heute / gesamt |
| 1056 / 1058 | u32 | 0,1 | kWh | Batterie-Ladung heute / gesamt |
| 1060 / 1062 | u32 | 0,1 | kWh | Hausverbrauch heute / gesamt |

Hinweis: 1021, 1029 und 1037 stammen aus der Netzmessung des Wechselrichters
(Zähler oder CT am Hausanschluss). Ohne gekoppelte Messung sind sie 0.

## Holding-Register (Function Code 3) – Info/Einstellungen

| Adresse | Inhalt |
|---|---|
| 9–11 | Firmware (ASCII) |
| 12–14 | Control-Firmware (ASCII) |
| 23–27 | Seriennummer (ASCII) |
| 43 | Gerätetyp-Code |
| 44 | High-Byte: MPP-Tracker, Low-Byte: Phasen (0x0203 = 2 Tracker, 3 Phasen) |
| 88 | Modbus-Protokollversion ×100 |
| 1037 | Netzmessung: 0 CT Kabel, 1 CT Funk, 2 Zähler |
| 1044 | aktive Priorität (0 Load First, 1 Battery First, 2 Grid First) – nur lesen |

## Schreibbare Register

Genutzt von den Paketen `growatt_backup_soc.yaml` (608) und
`growatt_batterie_halten.yaml` (1092, 1100–1102). Alle anderen bleiben unberührt.

| Adresse | Funktion |
|---|---|
| 608 | Load-First-Stop-SoC = Backup-Reserve (%) – **genutzt** |
| 1090 / 1091 | Battery First: Laderate (%) / Stopp-SoC (%) |
| 1092 | AC-Laden (Netz → Batterie) bei Battery First: 0/1 – **genutzt (nur auf 0)** |
| 1100 / 1101 / 1102 | Battery-First-Zeitfenster 1: Start (hh<<8 \| mm) / Ende / Aktiv – **genutzt** |
| 1080–1082 | Grid-First-Zeitfenster 1: Start / Ende / Aktiv |

evcc nutzt 1100–1102 und 1092, um die Hausbatterie beim Autoladen zu "halten".
Zeitfenster immer gemeinsam per Function Code 16 (write multiple) schreiben.
Holding-Register liegen im EEPROM – nicht im Sekundentakt beschreiben.
