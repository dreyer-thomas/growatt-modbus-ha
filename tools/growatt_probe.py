#!/usr/bin/env python3
"""
growatt_probe.py – Verbindungstest für Growatt SPH (TL3 BH-UP) per Modbus.

Liest NUR (Function Code 3 und 4), schreibt nichts in den Wechselrichter.

Beispiele:
    pip install "pymodbus>=3.6"
    python3 growatt_probe.py --host 192.168.178.60            # über LAN-Gateway
    python3 growatt_probe.py --serial /dev/ttyUSB0            # direkt per USB-RS485
    python3 growatt_probe.py --host 192.168.178.60 --watch 10 # alle 10 s live

Ausgabe: Geräteinfo (Seriennummer, Firmware, Phasen), alle Register, die das
Home-Assistant-Package nutzt, plus Plausibilitätsprüfungen.
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
from dataclasses import dataclass

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
except ImportError:  # pragma: no cover
    sys.exit('pymodbus fehlt:  pip install "pymodbus>=3.6"')


# ---------------------------------------------------------------------------
# Registerliste – muss mit homeassistant/packages/growatt_sph.yaml übereinstimmen
# (tests/test_consistency.py prüft das)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Reg:
    key: str
    kind: str      # "input" | "holding"
    address: int
    dtype: str     # "u16" | "u32"
    scale: float
    unit: str
    label: str


REGISTERS: list[Reg] = [
    Reg("status_code", "input", 0, "u16", 1, "", "Status-Code"),
    Reg("pv_power", "input", 1, "u32", 0.1, "W", "PV Leistung gesamt"),
    Reg("pv1_voltage", "input", 3, "u16", 0.1, "V", "PV1 Spannung"),
    Reg("pv1_current", "input", 4, "u16", 0.1, "A", "PV1 Strom"),
    Reg("pv1_power", "input", 5, "u32", 0.1, "W", "PV1 Leistung"),
    Reg("pv2_voltage", "input", 7, "u16", 0.1, "V", "PV2 Spannung"),
    Reg("pv2_current", "input", 8, "u16", 0.1, "A", "PV2 Strom"),
    Reg("pv2_power", "input", 9, "u32", 0.1, "W", "PV2 Leistung"),
    Reg("ac_power", "input", 35, "u32", 0.1, "W", "AC Leistung WR"),
    Reg("grid_frequency", "input", 37, "u16", 0.01, "Hz", "Netzfrequenz"),
    Reg("voltage_l1", "input", 38, "u16", 0.1, "V", "Spannung L1"),
    Reg("voltage_l2", "input", 42, "u16", 0.1, "V", "Spannung L2"),
    Reg("voltage_l3", "input", 46, "u16", 0.1, "V", "Spannung L3"),
    Reg("pv1_energy_today", "input", 59, "u32", 0.1, "kWh", "PV1 Energie heute"),
    Reg("pv2_energy_today", "input", 63, "u32", 0.1, "kWh", "PV2 Energie heute"),
    Reg("pv_energy_total", "input", 91, "u32", 0.1, "kWh", "PV Energie gesamt"),
    Reg("inverter_temperature", "input", 93, "u16", 0.1, "°C", "Temperatur WR"),
    Reg("fault_word_1007", "input", 1007, "u16", 1, "", "Fehlerwort 1007"),
    Reg("battery_discharge_power", "input", 1009, "u32", 0.1, "W", "Batterie Entladen"),
    Reg("battery_charge_power", "input", 1011, "u32", 0.1, "W", "Batterie Laden"),
    Reg("battery_voltage", "input", 1013, "u16", 0.1, "V", "Batterie Spannung"),
    Reg("battery_soc", "input", 1014, "u16", 1, "%", "Batterie SoC"),
    Reg("grid_import_power", "input", 1021, "u32", 0.1, "W", "Netzbezug"),
    Reg("grid_export_power", "input", 1029, "u32", 0.1, "W", "Netzeinspeisung"),
    Reg("local_load_power", "input", 1037, "u32", 0.1, "W", "Hausverbrauch"),
    Reg("battery_temperature", "input", 1040, "u16", 1, "°C", "Batterie Temperatur"),
    Reg("energy_to_user_today", "input", 1044, "u32", 0.1, "kWh", "Netzbezug heute"),
    Reg("energy_to_user_total", "input", 1046, "u32", 0.1, "kWh", "Netzbezug gesamt"),
    Reg("energy_to_grid_today", "input", 1048, "u32", 0.1, "kWh", "Einspeisung heute"),
    Reg("energy_to_grid_total", "input", 1050, "u32", 0.1, "kWh", "Einspeisung gesamt"),
    Reg("energy_discharge_total", "input", 1054, "u32", 0.1, "kWh", "Batt. Entladung gesamt"),
    Reg("energy_charge_total", "input", 1058, "u32", 0.1, "kWh", "Batt. Ladung gesamt"),
    Reg("local_load_energy_today", "input", 1060, "u32", 0.1, "kWh", "Hausverbrauch heute"),
    Reg("local_load_energy_total", "input", 1062, "u32", 0.1, "kWh", "Hausverbrauch gesamt"),
    Reg("load_first_stop_soc", "holding", 608, "u16", 1, "%", "Entladestopp-SoC (Backup-Reserve)"),
    Reg("ac_charge", "holding", 1092, "u16", 1, "", "AC-Laden (1 = Netz lädt Batterie)"),
    Reg("bf1_start", "holding", 1100, "u16", 1, "", "Battery First 1 Start"),
    Reg("bf1_end", "holding", 1101, "u16", 1, "", "Battery First 1 Ende"),
    Reg("bf1_enable", "holding", 1102, "u16", 1, "", "Battery First 1 aktiv"),
    Reg("ct_mode", "holding", 1037, "u16", 1, "", "Netzmessung (0/1=CT, 2=Zähler)"),
]

STATUS = {0: "Warten", 1: "Normal", 2: "Normal", 3: "FEHLER", 4: "Firmware-Update",
          5: "Normal (Hybrid)", 6: "Normal (Hybrid)", 7: "Normal (Hybrid)", 8: "Normal (Hybrid)"}
CT_MODE = {0: "CT (Kabel)", 1: "CT (Funk)", 2: "Zähler (Modbus)"}


# ---------------------------------------------------------------------------
# pymodbus-Versionsunterschiede abfangen (slave= / unit= / device_id=)
# ---------------------------------------------------------------------------
def _unit_kw(func) -> str:
    params = inspect.signature(func).parameters
    for name in ("device_id", "slave", "unit"):
        if name in params:
            return name
    return "slave"


def read_block(client, kind: str, address: int, count: int, unit: int) -> list[int]:
    func = client.read_input_registers if kind == "input" else client.read_holding_registers
    rr = func(address, count=count, **{_unit_kw(func): unit})
    if rr.isError():
        raise IOError(f"{kind} {address}+{count}: {rr}")
    return list(rr.registers)


def plan_blocks(regs: list[Reg], max_len: int = 40) -> list[tuple[str, int, int]]:
    """Fasst benachbarte Register zu wenigen Leseblöcken zusammen."""
    blocks: list[tuple[str, int, int]] = []
    for kind in ("input", "holding"):
        addrs = sorted({a for r in regs if r.kind == kind
                        for a in range(r.address, r.address + (2 if r.dtype == "u32" else 1))})
        if not addrs:
            continue
        start = prev = addrs[0]
        for a in addrs[1:]:
            if a - start + 1 > max_len or a - prev > 10:
                blocks.append((kind, start, prev - start + 1))
                start = a
            prev = a
        blocks.append((kind, start, prev - start + 1))
    return blocks


def decode(regs: list[Reg], raw: dict[tuple[str, int], int]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in regs:
        hi = raw.get((r.kind, r.address))
        if hi is None:
            continue
        if r.dtype == "u32":
            lo = raw.get((r.kind, r.address + 1))
            if lo is None:
                continue
            value = (hi << 16) | lo   # Growatt: High-Word zuerst (= HA-Default)
        else:
            value = hi
        out[r.key] = round(value * r.scale, 3)
    return out


def read_all(client, unit: int) -> dict[str, float]:
    raw: dict[tuple[str, int], int] = {}
    for kind, start, count in plan_blocks(REGISTERS):
        values = read_block(client, kind, start, count, unit)
        for i, v in enumerate(values):
            raw[(kind, start + i)] = v
        time.sleep(0.05)
    return decode(REGISTERS, raw)


def ascii_regs(values: list[int]) -> str:
    return "".join(chr(v >> 8) + chr(v & 0xFF) for v in values).replace("\x00", "").strip()


def device_info(client, unit: int) -> dict[str, str]:
    info: dict[str, str] = {}
    try:
        h = read_block(client, "holding", 0, 45, unit)
        info["Firmware"] = ascii_regs(h[9:12])
        info["Control-FW"] = ascii_regs(h[12:15])
        info["Seriennummer"] = ascii_regs(h[23:28])
        info["Gerätetyp-Code (DTC)"] = str(h[43])
        trackers, phases = (h[44] >> 8) & 0xFF, h[44] & 0xFF
        info["MPP-Tracker / Phasen"] = f"{trackers} / {phases}"
    except IOError as err:
        info["Fehler"] = str(err)
    try:
        info["Modbus-Protokoll"] = f"{read_block(client, 'holding', 88, 1, unit)[0] / 100:.2f}"
    except IOError:
        pass
    return info


def checks(v: dict[str, float]) -> list[str]:
    """Plausibilitätsprüfungen – liefert Hinweise in Klartext."""
    notes: list[str] = []
    if not (45 <= v.get("grid_frequency", 0) <= 55):
        notes.append("Netzfrequenz unplausibel -> Wortreihenfolge/Adresse prüfen.")
    for ph in ("l1", "l2", "l3"):
        u = v.get(f"voltage_{ph}", 0)
        if not (190 <= u <= 260):
            notes.append(f"Spannung {ph.upper()} = {u} V unplausibel.")
    if not (0 <= v.get("battery_soc", -1) <= 100):
        notes.append("Batterie-SoC außerhalb 0–100 %.")
    pv_sum = v.get("pv1_power", 0) + v.get("pv2_power", 0)
    if abs(pv_sum - v.get("pv_power", 0)) > max(50, 0.05 * pv_sum):
        notes.append("PV1+PV2 weicht deutlich von PV gesamt ab.")
    if not (5 <= v.get("load_first_stop_soc", 10) <= 100):
        notes.append("Entladestopp-SoC (608) außerhalb 5–100 % -> Register auf diesem Modell anders belegt?")
    if int(v.get("bf1_enable", 0)) == 1 and not (int(v.get("bf1_start", 0)) == 0
                                                  and int(v.get("bf1_end", 0)) == 5947):
        notes.append("Battery-First-Fenster 1 ist schon anderweitig in Benutzung "
                     "-> vor 'Batterie halten' klären (wird überschrieben).")
    if int(v.get("ac_charge", 0)) == 1:
        notes.append("AC-Laden ist aktiv: im Battery-First-Fenster lädt die Batterie aus dem Netz.")
    if v.get("ct_mode") is not None and int(v["ct_mode"]) not in CT_MODE:
        notes.append(f"Unbekannter Netzmess-Modus {v['ct_mode']}.")
    if int(v.get("fault_word_1007", 0)) & (1 << 13):
        notes.append("Fehlerbit Meter_COM_Loss gesetzt -> Zähler kommuniziert nicht mit dem WR.")
    if v.get("grid_import_power", 0) == 0 and v.get("grid_export_power", 0) == 0 \
            and v.get("local_load_power", 0) > 0:
        notes.append("Netzbezug und Einspeisung beide 0 – Zähler/CT fehlt oder nicht gekoppelt?")
    # Energiebilanz grob: PV + Bezug + Entladen ≈ Last + Einspeisung + Laden (+ Verluste)
    src = pv_sum + v.get("grid_import_power", 0) + v.get("battery_discharge_power", 0)
    snk = (v.get("local_load_power", 0) + v.get("grid_export_power", 0)
           + v.get("battery_charge_power", 0))
    if src > 300 and abs(src - snk) > 0.25 * src:
        notes.append(f"Leistungsbilanz weicht ab (Quellen {src:.0f} W / Senken {snk:.0f} W) "
                     "– bei Lastwechseln normal, dauerhaft nicht.")
    return notes


def print_table(v: dict[str, float]) -> None:
    for r in REGISTERS:
        if r.key not in v:
            continue
        val = v[r.key]
        extra = ""
        if r.key == "status_code":
            extra = f"  ({STATUS.get(int(val), 'unbekannt')})"
        if r.key == "ct_mode":
            extra = f"  ({CT_MODE.get(int(val), 'unbekannt')})"
        if r.key in ("bf1_start", "bf1_end"):
            extra = f"  ({int(val) >> 8:02d}:{int(val) & 0xFF:02d})"
        if r.key == "fault_word_1007":
            extra = f"  (0x{int(val):04X})"
        print(f"  {r.kind[0].upper()}{r.address:<5} {r.label:<32} {val:>10g} {r.unit}{extra}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--host", help="IP des Modbus-TCP-Gateways")
    src.add_argument("--serial", help="Serielles Gerät, z. B. /dev/ttyUSB0")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--unit", type=int, default=1, help="Modbus-Adresse des WR (Standard 1)")
    ap.add_argument("--watch", type=int, default=0, metavar="SEK", help="wiederholt lesen")
    args = ap.parse_args()

    if args.host:
        client = ModbusTcpClient(args.host, port=args.port, timeout=5)
        target = f"{args.host}:{args.port}"
    else:
        client = ModbusSerialClient(port=args.serial, baudrate=args.baud, bytesize=8,
                                    parity="N", stopbits=1, timeout=3)
        target = f"{args.serial} @ {args.baud} 8N1"

    print(f"Verbinde mit {target}, Modbus-Adresse {args.unit} …")
    if not client.connect():
        print("FEHLER: keine Verbindung. IP/Port bzw. Kabel prüfen.")
        return 2
    try:
        print("\nGeräteinfo")
        for k, val in device_info(client, args.unit).items():
            print(f"  {k:<24} {val}")
        while True:
            try:
                values = read_all(client, args.unit)
            except IOError as err:
                print(f"\nFEHLER beim Lesen: {err}")
                print("Typische Ursachen: A/B vertauscht, falscher Port am WR, Baudrate, "
                      "Gateway nicht im Modus 'Modbus TCP <-> RTU'.")
                return 3
            print(f"\nMesswerte {time.strftime('%H:%M:%S')}")
            print_table(values)
            notes = checks(values)
            print("\nPrüfung: " + ("alles plausibel" if not notes else ""))
            for n in notes:
                print(f"  ! {n}")
            if not args.watch:
                break
            time.sleep(args.watch)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
