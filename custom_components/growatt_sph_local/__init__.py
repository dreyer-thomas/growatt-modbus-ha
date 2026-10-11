"""Growatt SPH (lokal) – Hybrid-Wechselrichter per Modbus TCP auslesen und steuern."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SLAVE
from .coordinator import GrowattCoordinator, async_read_device_info
from .modbus_client import ModbusError, ModbusTcpClient

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]

type GrowattConfigEntry = ConfigEntry[GrowattCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry) -> bool:
    client = ModbusTcpClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        device = await async_read_device_info(client, entry.data[CONF_SLAVE])
    except ModbusError as err:
        await client.close()
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = GrowattCoordinator(hass, entry, client, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(hass: HomeAssistant, entry: GrowattConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GrowattConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded
