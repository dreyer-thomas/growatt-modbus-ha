"""Testumgebung: kleiner Modbus-TCP-Server, der einen Growatt SPH TL3 nachbildet."""
from __future__ import annotations

import asyncio
import struct

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations, socket_enabled):
    """Eigene Integration laden und echte TCP-Verbindungen zu 127.0.0.1 erlauben."""
    yield


def _ascii(text: str, n: int) -> list[int]:
    text = text.ljust(n * 2, "\x00")
    return [(ord(text[i]) << 8) | ord(text[i + 1]) for i in range(0, n * 2, 2)]


def _u32(regs: dict[int, int], addr: int, value: float, scale: float = 0.1) -> None:
    raw = int(round(value / scale))
    regs[addr], regs[addr + 1] = (raw >> 16) & 0xFFFF, raw & 0xFFFF


class FakeGrowatt:
    """Antwortet auf FC3/4/6/16 wie ein SPH 5000TL3 BH-UP."""

    def __init__(self) -> None:
        self.input: dict[int, int] = {}
        self.holding: dict[int, int] = {}
        self.writes: list[tuple[int, list[int]]] = []
        self.server: asyncio.base_events.Server | None = None
        self.clients: set[asyncio.StreamWriter] = set()
        self.port = 0
        i, h = self.input, self.holding
        i[0] = 5
        _u32(i, 1, 4200); i[3], i[4] = 4125, 54; _u32(i, 5, 2200); i[7], i[8] = 3980, 50; _u32(i, 9, 2000)
        _u32(i, 35, 2650); i[37] = 5001; i[38], i[42], i[46] = 2314, 2302, 2320
        _u32(i, 59, 9.8); _u32(i, 63, 8.9); _u32(i, 91, 21345.6); i[93] = 413
        i[1007] = 0; _u32(i, 1009, 0); _u32(i, 1011, 1450); i[1013] = 4096; i[1014] = 63
        _u32(i, 1021, 0); _u32(i, 1029, 1850); _u32(i, 1037, 800); i[1040] = 24
        _u32(i, 1044, 0.4); _u32(i, 1046, 4120.3); _u32(i, 1048, 6.1); _u32(i, 1050, 11873.9)
        _u32(i, 1054, 2310.2); _u32(i, 1058, 2498.7); _u32(i, 1060, 7.9); _u32(i, 1062, 9845.1)
        for k, v in enumerate(_ascii("RA1.0", 3)):
            h[9 + k] = v
        for k, v in enumerate(_ascii("ZBDA", 3)):
            h[12 + k] = v
        for k, v in enumerate(_ascii("SIM0123456", 5)):
            h[23 + k] = v
        h[43], h[44], h[88] = 3601, 0x0203, 124
        h[608], h[1037], h[1092], h[1100], h[1101], h[1102] = 20, 2, 0, 0, 0, 0

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients.add(writer)
        try:
            while True:
                head = await reader.readexactly(7)
                tid, _p, length, unit = struct.unpack(">HHHB", head)
                pdu = await reader.readexactly(length - 1)
                resp = self._process(pdu)
                writer.write(struct.pack(">HHHB", tid, 0, len(resp) + 1, unit) + resp)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            self.clients.discard(writer)
            writer.close()

    def _process(self, pdu: bytes) -> bytes:
        fc = pdu[0]
        if fc in (3, 4):
            addr, count = struct.unpack(">HH", pdu[1:5])
            table = self.input if fc == 4 else self.holding
            vals = [table.get(addr + k, 0) for k in range(count)]
            return struct.pack(f">BB{count}H", fc, 2 * count, *vals)
        if fc == 6:
            addr, val = struct.unpack(">HH", pdu[1:5])
            self.holding[addr] = val
            self.writes.append((addr, [val]))
            return pdu[:5]
        if fc == 16:
            addr, count = struct.unpack(">HH", pdu[1:5])
            vals = list(struct.unpack(f">{count}H", pdu[6:6 + 2 * count]))
            for k, v in enumerate(vals):
                self.holding[addr + k] = v
            self.writes.append((addr, vals))
            return pdu[:5]
        return bytes([fc | 0x80, 1])

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for writer in list(self.clients):
            writer.close()
        if self.server:
            self.server.close()


@pytest.fixture
async def fake_inverter():
    fake = FakeGrowatt()
    await fake.start()
    yield fake
    await fake.stop()
