"""Datenabruf für Growatt SPH über Modbus TCP."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALLOW_WRITE, CONF_SCAN_INTERVAL, CONF_SLAVE, DEFAULT_SCAN_INTERVAL, DOMAIN,
    INFO_BLOCK, INPUT_BLOCKS, PROTOCOL_REGISTER, SETTINGS_BLOCKS, SETTINGS_EVERY_N,
)
from .modbus_client import ModbusError, ModbusTcpClient

_LOGGER = logging.getLogger(__name__)


def ascii_from_registers(values: list[int]) -> str:
    text = "".join(chr((v >> 8) & 0xFF) + chr(v & 0xFF) for v in values)
    return "".join(c for c in text if c.isprintable()).strip()


@dataclass
class DeviceInfoData:
    serial: str = ""
    firmware: str = ""
    control_firmware: str = ""
    device_type_code: int | None = None
    trackers: int | None = None
    phases: int | None = None
    protocol: str | None = None


@dataclass
class GrowattData:
    input: dict[int, int] = field(default_factory=dict)
    holding: dict[int, int] = field(default_factory=dict)


async def async_read_device_info(client: ModbusTcpClient, slave: int) -> DeviceInfoData:
    start, count = INFO_BLOCK
    regs = await client.read_registers(slave, "holding", start, count)
    info = DeviceInfoData(
        firmware=ascii_from_registers(regs[9:12]),
        control_firmware=ascii_from_registers(regs[12:15]),
        serial=ascii_from_registers(regs[23:28]),
        device_type_code=regs[43],
        trackers=(regs[44] >> 8) & 0xFF,
        phases=regs[44] & 0xFF,
    )
    try:
        proto = await client.read_registers(slave, "holding", PROTOCOL_REGISTER, 1)
        info.protocol = f"{proto[0] / 100:.2f}"
    except ModbusError:
        pass
    return info


class GrowattCoordinator(DataUpdateCoordinator[GrowattData]):
    """Liest Mess- und Einstellungswerte in wenigen Blockabfragen."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ModbusTcpClient,
                 device: DeviceInfoData) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.device = device
        self.slave: int = entry.data[CONF_SLAVE]
        self._cycle = 0
        # Schreiben + Zurücklesen immer nacheinander, nie überlappend
        self._write_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self.config_entry.data[CONF_HOST]

    @property
    def port(self) -> int:
        return self.config_entry.data[CONF_PORT]

    @property
    def allow_write(self) -> bool:
        return bool(self.config_entry.options.get(CONF_ALLOW_WRITE, False))

    async def _async_update_data(self) -> GrowattData:
        data = GrowattData(holding=dict(self.data.holding) if self.data else {})
        try:
            for start, count in INPUT_BLOCKS:
                values = await self.client.read_registers(self.slave, "input", start, count)
                data.input.update({start + i: v for i, v in enumerate(values)})
            if self._cycle % SETTINGS_EVERY_N == 0 or not data.holding:
                await self._read_settings(data)
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
        self._cycle += 1
        return data

    async def _read_settings(self, data: GrowattData) -> None:
        for start, count in SETTINGS_BLOCKS:
            values = await self.client.read_registers(self.slave, "holding", start, count)
            data.holding.update({start + i: v for i, v in enumerate(values)})

    async def async_refresh_settings(self) -> None:
        """Einstellungen sofort neu lesen (nach einem Schreibvorgang)."""
        if self.data is None:
            return
        try:
            await self._read_settings(self.data)
        except ModbusError as err:
            raise HomeAssistantError(f"Zurücklesen fehlgeschlagen: {err}") from err
        self.async_set_updated_data(self.data)

    def _ensure_write_allowed(self) -> None:
        if not self.allow_write:
            raise HomeAssistantError(
                "Schreibzugriff ist deaktiviert. Aktivieren unter Einstellungen → "
                "Geräte & Dienste → Growatt SPH (lokal) → Konfigurieren."
            )

    async def async_write_verified(self, address: int, values: list[int],
                                   attempts: int = 6, wait: float = 0.5) -> None:
        """Register schreiben und so lange zurücklesen, bis der Wechselrichter
        den Wert übernommen hat (er speichert ins EEPROM, das dauert etwas).

        Schreibvorgänge laufen über ein Lock nacheinander. Schnelles Mehrfach-
        klicken (+ + +) erzeugt so keine sich überholenden Rücklesungen mehr.
        """
        self._ensure_write_allowed()
        async with self._write_lock:
            try:
                if len(values) == 1:
                    await self.client.write_register(self.slave, address, values[0])
                else:
                    await self.client.write_registers(self.slave, address, values)
            except ModbusError as err:
                raise HomeAssistantError(f"Schreiben ab Register {address} fehlgeschlagen: {err}") from err
            _LOGGER.info("Register %s.. auf %s gesetzt", address, values)
            current: list[int] = []
            for attempt in range(attempts):
                await asyncio.sleep(wait if attempt else 0.2)
                try:
                    current = await self.client.read_registers(self.slave, "holding", address, len(values))
                except ModbusError as err:
                    _LOGGER.debug("Zurücklesen von %s fehlgeschlagen: %s", address, err)
                    continue
                if current == values:
                    break
            if self.data is not None and current:
                self.data.holding.update({address + i: v for i, v in enumerate(current)})
                self.async_set_updated_data(self.data)
            if current != values:
                raise HomeAssistantError(
                    f"Wechselrichter meldet {current} statt {values} für Register {address} – "
                    "Wert wurde nicht übernommen"
                )
