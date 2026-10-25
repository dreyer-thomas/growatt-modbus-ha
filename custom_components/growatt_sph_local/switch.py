"""Schalter: Batterie halten (Entladestopp) und Netzladen.

Beide nutzen das Battery-First-Zeitfenster 1 und schließen sich gegenseitig aus:

* Batterie halten: Fenster 1 ganztägig aktiv, AC-Laden aus  -> Batterie entlädt nicht,
  PV lädt weiter (wie evcc "batterymode: hold").
* Netzladen:       Fenster 1 ganztägig aktiv, AC-Laden an   -> Batterie lädt zusätzlich
  aus dem Netz bis "Netzladen bis" (Register 1091) mit "Netzladeleistung" (1090).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import (
    FULL_DAY_END, FULL_DAY_START, REG_AC_CHARGE, REG_BF1_ENABLE, REG_BF1_END, REG_BF1_START,
)
from .entity import GrowattEntity


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([GrowattBatteryHold(coordinator), GrowattGridCharge(coordinator)])


class _WindowSwitch(GrowattEntity, SwitchEntity):
    """Gemeinsame Logik für Schalter auf dem Battery-First-Fenster 1."""

    def _holding(self, addr: int) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.holding.get(addr)

    def _window_full_day(self) -> bool | None:
        enable = self._holding(REG_BF1_ENABLE)
        if enable is None:
            return None
        # Ein aktives, aber leeres Fenster (00:00–00:00) zählt nicht.
        return enable == 1 and self._holding(REG_BF1_START) == FULL_DAY_START \
            and self._holding(REG_BF1_END) == FULL_DAY_END

    async def _set_ac_charge(self, value: int) -> None:
        if self._holding(REG_AC_CHARGE) != value:
            await self.coordinator.async_write_verified(REG_AC_CHARGE, [value])

    async def _enable_full_day_window(self) -> None:
        if not self._window_full_day():
            # Start, Ende und Aktiv gemeinsam schreiben (Function Code 16)
            await self.coordinator.async_write_verified(
                REG_BF1_START, [FULL_DAY_START, FULL_DAY_END, 1])

    async def _disable_window(self) -> None:
        if self._holding(REG_BF1_ENABLE) != 0:
            await self.coordinator.async_write_verified(REG_BF1_ENABLE, [0])


class GrowattBatteryHold(_WindowSwitch):
    """Battery-First-Fenster 1 ganztägig, Netzladen aus = Batterie entlädt nicht."""

    _attr_translation_key = "battery_hold"
    _attr_icon = "mdi:battery-lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "battery_hold")

    @property
    def is_on(self) -> bool | None:
        window = self._window_full_day()
        if window is None:
            return None
        return window and self._holding(REG_AC_CHARGE) == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"zeitfenster_ganztags": bool(self._window_full_day())}

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Netzladen zuerst aus, dann Fenster setzen -> nie ungewollt Netzladen
        await self._set_ac_charge(0)
        await self._enable_full_day_window()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not self.is_on:
            return  # z. B. Netzladen aktiv -> dessen Fenster nicht anfassen
        await self._disable_window()


class GrowattGridCharge(_WindowSwitch):
    """Battery-First-Fenster 1 ganztägig mit AC-Laden = Batterie lädt aus dem Netz."""

    _attr_translation_key = "grid_charge"
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "grid_charge")

    @property
    def is_on(self) -> bool | None:
        window = self._window_full_day()
        if window is None:
            return None
        return window and self._holding(REG_AC_CHARGE) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_ac_charge(1)
        await self._enable_full_day_window()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Erst Netzladen aus (sofort kein Netzbezug mehr), dann Fenster aus -> Load First
        await self._set_ac_charge(0)
        if self._window_full_day():
            await self._disable_window()
