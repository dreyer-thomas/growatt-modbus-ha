# Growatt SPH (lokal) – Home Assistant

Liest Growatt-SPH-Hybridwechselrichter (getestet für **SPH 4000–10000TL3 BH-UP**, dreiphasig)
**lokal per Modbus TCP** aus – ohne Growatt-Cloud – und kann die Backup-Reserve der Batterie
setzen und die Batterie „halten“.

```
Growatt SPH (RS485) ──> RS485-LAN-Gateway (Modbus TCP ⇄ RTU) ──LAN──> Home Assistant
```

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dreyer-thomas&repository=growatt-modbus-ha&category=integration)

## Was liegt wo

| Pfad | Inhalt |
|---|---|
| `custom_components/growatt_sph_local/` | Die Home-Assistant-Integration (wird per HACS installiert) |
| `docs/Growatt-Modbus-Montageanleitung.pdf` | Einkaufsliste, Montage, Gateway-Einrichtung, Inbetriebnahme |
| `docs/register-map.md` | Alle genutzten Modbus-Register mit Quellen |
| `tools/growatt_probe.py` | Verbindungstest vom Mac/PC aus (nur lesend) |
| `tools/growatt_simulator.py` | Simulierter Wechselrichter zum Testen ohne Hardware |
| `yaml-package/` | Alternative ohne Integration: reines YAML-Paket inkl. Sommer/Winter-Reserve und Automatik „Batterie halten beim Autoladen“ |
| `tests/` | Automatische Tests der Integration |

## Funktionen

- Einrichtung komplett über die Oberfläche (IP des Gateways eingeben)
- Ein Gerät „Growatt SPH“ mit Seriennummer und Firmware
- 36 Sensoren: PV (gesamt, PV1/PV2), Netz (Bezug, Einspeisung, ± Leistung), Hausverbrauch,
  Batterie (Ladestand, Leistung ±, Spannung, Temperatur), Phasenspannungen, Frequenz,
  Energiezähler gesamt und heute – passend für das **Energie-Dashboard**
- **Backup-Reserve** (Zahl, 10–100 %): bis zu diesem Ladestand entlädt die Batterie am Netz,
  der Rest bleibt für Notstrom (Register 608 „Load First Stop-SOC“)
- **Batterie halten** (Schalter): Batterie entlädt nicht, PV lädt sie weiter – z. B. während das
  Auto lädt (Battery-First-Zeitfenster 1 auf 00:00–23:59, Netzladen aus; wie evcc „hold“)
- Wenige Blockabfragen statt vieler Einzelanfragen, eigener schlanker Modbus-Client
  (keine pymodbus-Versionskonflikte)

## Sicherheit beim Schreiben

Nach der Einrichtung ist der **Schreibzugriff aus**. Backup-Reserve und „Batterie halten“
melden dann einen Fehler statt zu schreiben. Einschalten erst, wenn die Werte ein paar Tage
mit der Growatt-App übereinstimmen und `Backup-Reserve` denselben Wert zeigt wie
„Lastvorrang / Load First → Entladestopp-SOC“ in der App:

*Einstellungen → Geräte & Dienste → Growatt SPH (lokal) → Konfigurieren → „Schreibzugriff erlauben“*

Geschrieben wird nur bei echten Änderungen; nach jedem Schreiben wird zurückgelesen.
„Batterie halten“ belegt das **Battery-First-Zeitfenster 1** – ein dort in der App
eingerichtetes Fenster wird überschrieben.

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/dreyer-thomas/growatt-modbus-ha`, Kategorie **Integration**
2. „Growatt SPH (lokal)“ herunterladen, Home Assistant neu starten
3. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Growatt SPH (lokal)“
4. IP des Gateways, Port `502`, Modbus-Adresse `1`

Updates erscheinen danach automatisch in HACS.

### Manuell

Ordner `custom_components/growatt_sph_local` nach `/config/custom_components/` kopieren, neu starten.

## Gateway

Getestet mit Waveshare **RS485 TO ETH (B)**: 9600 Baud, 8N1, Betriebsart TCP-Server,
Protokoll **„Modbus TCP ⇄ RTU“**, Port 502. Am Wechselrichter eine freie 485-Buchse
(bevorzugt 485-3), **nicht** METER. Pin 1 → B, Pin 5 → A.

Viele Gateways erlauben nur **eine** TCP-Verbindung. Nicht gleichzeitig ein YAML-Modbus-Paket,
evcc oder eine zweite Integration auf dasselbe Gateway zugreifen lassen.

## Energie-Dashboard

| Feld | Entität |
|---|---|
| Netzbezug | Netzbezug Energie gesamt |
| Netzeinspeisung | Einspeisung Energie gesamt |
| Solarerzeugung | PV-Energie gesamt |
| In die Batterie / aus der Batterie | Batterie Ladung gesamt / Batterie Entladung gesamt |

Vorzeichen: **Netzleistung** + = Bezug, − = Einspeisung; **Batterieleistung** + = Entladen, − = Laden.

## Register

| Register | Typ | Inhalt |
|---|---|---|
| Input 0–99 | lesen | Status, PV, AC, Phasen, Energie, Temperatur |
| Input 1000–1063 | lesen | Batterie, Netz, Hausverbrauch, Energiezähler, Fehler |
| Holding 0–44, 88 | lesen (einmalig) | Firmware, Seriennummer, Gerätetyp, Phasen, Protokoll |
| Holding 608 | lesen/schreiben | Backup-Reserve |
| Holding 1092 | lesen/schreiben | Netzladen im Battery-First-Fenster (wird nur auf 0 gesetzt) |
| Holding 1100–1102 | lesen/schreiben | Battery-First-Fenster 1: Start, Ende, Aktiv |

Quelle: Growatt „Modbus RTU Protocol“ V1.20/V1.24, abgeglichen mit evcc (`growatt-hybrid`)
und Lu-Fi/ha-growatt-modbus.

## Verbindung vorab testen

```bash
pip3 install "pymodbus>=3.6"
python3 tools/growatt_probe.py --host 192.168.178.60
```

Ohne Hardware: `python3 tools/growatt_simulator.py --port 5020` starten und das
Probe-Skript bzw. die Integration auf `127.0.0.1:5020` zeigen lassen.

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest -q
```

Die Tests starten einen kleinen Modbus-Server, der einen SPH TL3 nachbildet, und prüfen
Einrichtung, Sensorwerte, Schreibsperre, Backup-Reserve und „Batterie halten“.

## Haftung

Nutzung auf eigene Verantwortung. Kein offizielles Growatt-Produkt.
