"""Schalter: Batterie halten (keine Entladung, z. B. während das Auto lädt)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import (
    FULL_DAY_END, FULL_DAY_START, REG_AC_CHARGE, REG_BF1_ENABLE, REG_BF1_END, REG_BF1_START,
)
from .entity import GrowattEntity


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([GrowattBatteryHold(entry.runtime_data)])


class GrowattBatteryHold(GrowattEntity, SwitchEntity):
    """Battery-First-Fenster 1 (00:00–23:59) aktiv = Batterie entlädt nicht.

    Wie evcc ("batterymode: hold"): Beim Einschalten wird Fenster 1 auf den
    ganzen Tag gestellt und aktiviert, Netzladen (AC-Laden) wird ausgeschaltet.
    PV lädt die Batterie weiter. Beim Ausschalten wird nur das Fenster deaktiviert.
    """

    _attr_translation_key = "battery_hold"
    _attr_icon = "mdi:battery-lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "battery_hold")

    def _holding(self, addr: int) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.holding.get(addr)

    @property
    def is_on(self) -> bool | None:
        enable = self._holding(REG_BF1_ENABLE)
        return None if enable is None else enable == 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        start, end = self._holding(REG_BF1_START), self._holding(REG_BF1_END)
        full_day = start == FULL_DAY_START and end == FULL_DAY_END
        return {"zeitfenster_ganztags": full_day}

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.is_on and self.extra_state_attributes["zeitfenster_ganztags"] \
                and self._holding(REG_AC_CHARGE) == 0:
            return  # schon gehalten – nichts schreiben
        if self._holding(REG_AC_CHARGE) not in (0, None):
            await self.coordinator.async_write(REG_AC_CHARGE, 0)
        # Start, Ende und Aktiv gemeinsam schreiben (Function Code 16)
        await self.coordinator.async_write_many(REG_BF1_START, [FULL_DAY_START, FULL_DAY_END, 1])
        await self._verify(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._holding(REG_BF1_ENABLE) == 0:
            return
        await self.coordinator.async_write(REG_BF1_ENABLE, 0)
        await self._verify(False)

    async def _verify(self, expected: bool) -> None:
        await self.coordinator.async_refresh_settings()
        if self.is_on is not expected:
            raise HomeAssistantError("Der Wechselrichter hat die Umschaltung nicht übernommen")
