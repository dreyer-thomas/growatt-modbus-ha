#!/usr/bin/env python3
"""
Kleiner Modbus-TCP-Simulator, der sich wie ein Growatt SPH 5000TL3 BH-UP
verhält (Sommermittag: 4,2 kW PV, Batterie lädt, Einspeisung).

Zum Testen des Probe-Skripts oder des HA-Packages ohne echte Hardware:
    python3 tools/growatt_simulator.py --port 5020
    python3 tools/growatt_probe.py --host 127.0.0.1 --port 5020
"""
from __future__ import annotations

import argparse
import asyncio

from pymodbus.datastore import ModbusServerContext, ModbusSequentialDataBlock
from pymodbus.server import StartAsyncTcpServer

try:  # pymodbus >= 3.10
    from pymodbus.datastore import ModbusDeviceContext as _Ctx
except ImportError:  # ältere Versionen
    from pymodbus.datastore import ModbusSlaveContext as _Ctx


def u32(regs: dict[int, int], addr: int, value: float, scale: float = 0.1) -> None:
    raw = int(round(value / scale))
    regs[addr], regs[addr + 1] = (raw >> 16) & 0xFFFF, raw & 0xFFFF


def u16(regs: dict[int, int], addr: int, value: float, scale: float = 1) -> None:
    regs[addr] = int(round(value / scale)) & 0xFFFF


def ascii_to_regs(text: str, n: int) -> list[int]:
    text = text.ljust(n * 2, "\x00")
    return [(ord(text[i]) << 8) | ord(text[i + 1]) for i in range(0, n * 2, 2)]


def build() -> tuple[dict[int, int], dict[int, int]]:
    inp: dict[int, int] = {}
    hold: dict[int, int] = {}
    u16(inp, 0, 5)                    # Normal (Hybrid)
    u32(inp, 1, 4200)
    u16(inp, 3, 412.5, 0.1); u16(inp, 4, 5.4, 0.1); u32(inp, 5, 2200)
    u16(inp, 7, 398.0, 0.1); u16(inp, 8, 5.0, 0.1); u32(inp, 9, 2000)
    u32(inp, 35, 2650)
    u16(inp, 37, 50.01, 0.01)
    u16(inp, 38, 412.5, 0.1); u16(inp, 42, 405.0, 0.1); u16(inp, 46, 415.9, 0.1)
    u32(inp, 59, 9.8); u32(inp, 63, 8.9); u32(inp, 91, 21345.6)
    u16(inp, 93, 41.3, 0.1)
    u16(inp, 1007, 0)
    u32(inp, 1009, 0); u32(inp, 1011, 1450)
    u16(inp, 1013, 409.6, 0.1); u16(inp, 1014, 63)
    u32(inp, 1021, 0); u32(inp, 1029, 1850); u32(inp, 1037, 800)
    u16(inp, 1040, 25.3, 0.1)
    u32(inp, 1044, 0.4); u32(inp, 1046, 4120.3)
    u32(inp, 1048, 6.1); u32(inp, 1050, 11873.9)
    u32(inp, 1054, 2310.2); u32(inp, 1058, 2498.7)
    u32(inp, 1060, 7.9); u32(inp, 1062, 9845.1)
    # Holding: Firmware, Seriennummer, Typ, Phasen, Protokoll, Netzmessung
    for i, v in enumerate(ascii_to_regs("RA1.0", 3)):
        hold[9 + i] = v
    for i, v in enumerate(ascii_to_regs("ZBDA", 3)):
        hold[12 + i] = v
    for i, v in enumerate(ascii_to_regs("SIM0123456", 5)):
        hold[23 + i] = v
    hold[43] = 3601
    hold[44] = 0x0203                 # 2 Tracker, 3 Phasen
    hold[88] = 124                    # Protokoll 1.24
    hold[1037] = 2                    # Zähler
    hold[608] = 20                    # Entladestopp-SoC
    hold[1092] = 0                    # AC-Laden aus
    hold[1100], hold[1101], hold[1102] = 0, 0, 0   # Battery-First-Fenster 1 leer
    return inp, hold


def to_block(regs: dict[int, int]) -> ModbusSequentialDataBlock:
    values = [0] * 1200   # deckt 0–1199 ab
    for a, v in regs.items():
        values[a] = v
    # pymodbus adressiert Datenblöcke 1-basiert -> Start bei 1, damit Adresse 0 = Index 0
    return ModbusSequentialDataBlock(1, values)


async def main(port: int) -> None:
    inp, hold = build()
    device = _Ctx(ir=to_block(inp), hr=to_block(hold))
    try:
        context = ModbusServerContext(devices={1: device}, single=False)
    except TypeError:
        context = ModbusServerContext(slaves={1: device}, single=False)
    print(f"Growatt-Simulator lauscht auf 0.0.0.0:{port} (Modbus-Adresse 1)")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", port))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5020)
    asyncio.run(main(ap.parse_args().port))
