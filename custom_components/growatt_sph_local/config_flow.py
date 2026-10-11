"""Einrichtung über die Oberfläche."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_ALLOW_WRITE, CONF_SCAN_INTERVAL, CONF_SLAVE, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE, DOMAIN, MIN_SCAN_INTERVAL,
)
from .coordinator import async_read_device_info
from .modbus_client import ModbusError, ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(int, vol.Range(min=1, max=247)),
})


async def _probe(host: str, port: int, slave: int) -> tuple[str, dict[str, Any]]:
    """Verbindung testen; liefert (Fehlerschlüssel | '', Infos)."""
    client = ModbusTcpClient(host, port)
    try:
        info = await async_read_device_info(client, slave)
        # Nur Speicher-/Hybridgeräte haben den Input-Bereich ab 1000
        await client.read_registers(slave, "input", 1000, 1)
    except ModbusError as err:
        _LOGGER.debug("Verbindungstest fehlgeschlagen: %s", err)
        msg = str(err)
        if "Keine Verbindung" in msg:
            return "cannot_connect", {}
        if "Ausnahme" in msg:
            return "not_hybrid", {}
        return "no_response", {}
    finally:
        await client.close()
    return "", {"serial": info.serial, "phases": info.phases}


class GrowattConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error, info = await _probe(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(info["serial"] or f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE]}")
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST],
                                                              CONF_PORT: user_input[CONF_PORT]})
                title = f"Growatt SPH {info['serial']}".strip()
                return self.async_create_entry(
                    title=title, data=user_input,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_ALLOW_WRITE: False},
                )
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error, _ = await _probe(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GrowattOptionsFlow()


class GrowattOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=300)),
            vol.Required(CONF_ALLOW_WRITE, default=opts.get(CONF_ALLOW_WRITE, False)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
