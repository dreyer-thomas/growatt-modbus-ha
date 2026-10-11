"""Minimaler asynchroner Modbus-TCP-Client.

Bewusst ohne pymodbus: keine Versionskonflikte mit Home Assistant Core
(dessen Modbus-Integration pymodbus pinnt) und keine API-Brüche zwischen
pymodbus-Versionen. Unterstützt nur, was die Integration braucht:
FC3 (Holding lesen), FC4 (Input lesen), FC6 (ein Register schreiben),
FC16 (mehrere Register schreiben).

Alle Anfragen laufen nacheinander über eine Verbindung (Lock), weil
RS485-Gateways wie das Waveshare RS485 TO ETH (B) Anfragen seriell
weiterreichen und oft nur eine TCP-Verbindung zulassen.
"""
from __future__ import annotations

import asyncio
import logging
import struct

_LOGGER = logging.getLogger(__name__)

FC_READ_HOLDING = 3
FC_READ_INPUT = 4
FC_WRITE_SINGLE = 6
FC_WRITE_MULTIPLE = 16

EXCEPTION_TEXT = {
    1: "ungültige Funktion",
    2: "ungültige Registeradresse",
    3: "ungültiger Wert",
    4: "Gerätefehler",
    6: "Gerät beschäftigt",
    10: "Gateway: Pfad nicht verfügbar",
    11: "Gateway: Zielgerät antwortet nicht",
}


class ModbusError(Exception):
    """Fehler bei der Modbus-Kommunikation."""


class ModbusTcpClient:
    """Asynchroner Modbus-TCP-Client mit automatischem Reconnect."""

    def __init__(self, host: str, port: int = 502, timeout: float = 5.0,
                 pause: float = 0.05) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.pause = pause  # Pause zwischen Anfragen (RS485 @ 9600 Baud)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._tid = 0

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def _connect(self) -> None:
        if self.connected:
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise ModbusError(f"Keine Verbindung zu {self.host}:{self.port}: {err}") from err

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = self._writer = None

    async def _request(self, unit: int, pdu: bytes) -> bytes:
        async with self._lock:
            for attempt in (1, 2):
                await self._connect()
                self._tid = (self._tid + 1) & 0xFFFF
                header = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, unit)
                try:
                    assert self._writer and self._reader
                    self._writer.write(header + pdu)
                    await self._writer.drain()
                    resp = await asyncio.wait_for(self._read_frame(), self.timeout)
                except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError) as err:
                    await self.close()
                    if attempt == 2:
                        raise ModbusError(f"Keine Antwort von {self.host}: {err}") from err
                    _LOGGER.debug("Neuer Verbindungsversuch nach Fehler: %s", err)
                    continue
                if self.pause:
                    await asyncio.sleep(self.pause)
                return resp
        raise ModbusError("unerreichbar")  # pragma: no cover

    async def _read_frame(self) -> bytes:
        assert self._reader
        while True:
            head = await self._reader.readexactly(7)
            tid, _proto, length, _unit = struct.unpack(">HHHB", head)
            body = await self._reader.readexactly(length - 1)
            if tid == self._tid:
                return body
            _LOGGER.debug("Verwerfe veraltete Antwort tid=%s (erwartet %s)", tid, self._tid)

    @staticmethod
    def _check(fc: int, resp: bytes) -> None:
        if not resp:
            raise ModbusError("leere Antwort")
        if resp[0] == fc | 0x80:
            code = resp[1] if len(resp) > 1 else 0
            raise ModbusError(
                f"Modbus-Ausnahme {code} ({EXCEPTION_TEXT.get(code, 'unbekannt')})"
            )
        if resp[0] != fc:
            raise ModbusError(f"unerwarteter Funktionscode {resp[0]}")

    async def read_registers(self, unit: int, kind: str, address: int, count: int) -> list[int]:
        """Liest `count` Register ab `address` ('input' oder 'holding')."""
        fc = FC_READ_INPUT if kind == "input" else FC_READ_HOLDING
        resp = await self._request(unit, struct.pack(">BHH", fc, address, count))
        self._check(fc, resp)
        byte_count = resp[1]
        if byte_count != 2 * count or len(resp) < 2 + byte_count:
            raise ModbusError(f"falsche Antwortlänge ({byte_count} statt {2 * count})")
        return list(struct.unpack(f">{count}H", resp[2:2 + byte_count]))

    async def write_register(self, unit: int, address: int, value: int) -> None:
        resp = await self._request(unit, struct.pack(">BHH", FC_WRITE_SINGLE, address, value & 0xFFFF))
        self._check(FC_WRITE_SINGLE, resp)

    async def write_registers(self, unit: int, address: int, values: list[int]) -> None:
        count = len(values)
        pdu = struct.pack(f">BHHB{count}H", FC_WRITE_MULTIPLE, address, count, 2 * count,
                          *[v & 0xFFFF for v in values])
        resp = await self._request(unit, pdu)
        self._check(FC_WRITE_MULTIPLE, resp)
