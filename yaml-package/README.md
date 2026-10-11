# YAML-Paket (Alternative zur Integration)

Für Installationen ohne HACS. **Nicht gleichzeitig mit der Integration betreiben** –
das Gateway erlaubt meist nur eine Verbindung.

| Datei | Zweck |
|---|---|
| `packages/growatt_sph.yaml` | Modbus-Hub und Sensoren (nur lesen) |
| `packages/growatt_backup_soc.yaml` | Backup-Reserve Sommer/Winter (schreibt Register 608) |
| `packages/growatt_batterie_halten.yaml` | Batterie halten, solange der Tesla Wall Connector lädt |
| `dashboards/growatt_karte.yaml` | Dashboard-Karte |

Installation: Dateien nach `/config/packages/`, in `growatt_sph.yaml` die Gateway-IP eintragen,
in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Konfiguration prüfen, neu starten. Die schreibenden Pakete arbeiten erst, wenn
`input_boolean.growatt_schreiben_freigegeben` eingeschaltet ist.

Konsistenztest (Package ↔ Probe-Skript): `python3 yaml-package/check_package.py`
