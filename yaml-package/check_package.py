#!/usr/bin/env python3
"""
Prüft, dass HA-Package und Probe-Skript dieselben Register verwenden,
und rendert die Template-Sensoren mit Beispielwerten.

    pip install pyyaml jinja2 "pymodbus>=3.6"
    python3 yaml-package/check_package.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from growatt_probe import REGISTERS  # noqa: E402

PACKAGE = ROOT / "yaml-package" / "packages" / "growatt_sph.yaml"
DTYPE = {"u16": "uint16", "u32": "uint32"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main() -> int:
    cfg = yaml.safe_load(PACKAGE.read_text(encoding="utf-8"))
    errors: list[str] = []

    sensors = cfg["modbus"][0]["sensors"]
    yaml_regs = {(s.get("input_type", "holding"), s["address"]):
                 (s["data_type"], float(s.get("scale", 1))) for s in sensors}
    probe_regs = {(r.kind, r.address): (DTYPE[r.dtype], float(r.scale)) for r in REGISTERS}

    for key, val in yaml_regs.items():
        if key not in probe_regs:
            errors.append(f"Register {key} nur im HA-Package")
        elif probe_regs[key] != val:
            errors.append(f"Register {key}: HA {val} != Probe {probe_regs[key]}")
    for key in probe_regs.keys() - yaml_regs.keys():
        errors.append(f"Register {key} nur im Probe-Skript")

    # Eindeutigkeit
    uids = [s["unique_id"] for s in sensors]
    names = [s["name"] for s in sensors]
    for lst, what in ((uids, "unique_id"), (names, "name")):
        dupes = {x for x in lst if lst.count(x) > 1}
        if dupes:
            errors.append(f"doppelte {what}: {dupes}")

    # Template-Referenzen müssen auf existierende Modbus-Entitäten zeigen
    entity_ids = {f"sensor.{slug(n)}" for n in names}
    text = PACKAGE.read_text(encoding="utf-8")
    for ref in set(re.findall(r"sensor\.growatt_[a-z0-9_]+", text)):
        if ref not in entity_ids:
            errors.append(f"Template verweist auf unbekannte Entität {ref}")

    # Templates mit Beispielzustand rendern
    states = {
        "sensor.growatt_netzbezug": "0", "sensor.growatt_netzeinspeisung": "1850",
        "sensor.growatt_batterie_entladeleistung": "0",
        "sensor.growatt_batterie_ladeleistung": "1450",
        "sensor.growatt_pv1_energie_heute": "9.8", "sensor.growatt_pv2_energie_heute": "8.9",
        "sensor.growatt_status_code": "5", "sensor.growatt_messquelle_netz": "2",
        "sensor.growatt_fehlerregister_zaehler": str(1 << 13),
        "sensor.growatt_battery_first_1_start": "0", "sensor.growatt_battery_first_1_ende": "5947",
        "sensor.growatt_battery_first_1_aktiv_code": "1", "sensor.growatt_ac_laden_code": "0",
    }
    expected = {
        "growatt_grid_power_signed": -1850.0, "growatt_battery_power_signed": -1450.0,
        "growatt_pv_surplus": 3300.0, "growatt_pv_energy_today_sum": 18.7,
        "growatt_status_text": "Normal (Hybrid)", "growatt_ct_mode_text": "Zähler (Modbus)",
        "growatt_meter_com_loss": "True",
        "growatt_battery_first_1_window": "00:00–23:59",
        "growatt_battery_hold_active": "True", "growatt_ac_charge_active": "False",
    }
    env = jinja2.Environment()
    env.filters["float"] = lambda v, d=0: float(v) if _num(v) else d
    env.filters["int"] = lambda v, d=0: int(float(v)) if _num(v) else d
    env.globals["states"] = lambda e: states.get(e, "unknown")
    env.globals["has_value"] = lambda e: e in states

    for block in cfg["template"]:
        for kind in ("sensor", "binary_sensor"):
            for t in block.get(kind, []):
                out = env.from_string(t["state"]).render().strip()
                avail = env.from_string(t.get("availability", "True")).render().strip()
                exp = expected.get(t["unique_id"])
                got = float(out) if _num(out) and not isinstance(exp, str) else out
                if exp is not None and got != exp:
                    errors.append(f"Template {t['unique_id']}: {got!r} != {exp!r}")
                if avail != "True":
                    errors.append(f"Template {t['unique_id']} nicht verfügbar")
                print(f"  {t['unique_id']:<32} = {out}")

    if errors:
        print("\nFEHLER:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"\nOK – {len(yaml_regs)} Register konsistent, Templates rendern korrekt.")
    return 0


def _num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    sys.exit(main())
