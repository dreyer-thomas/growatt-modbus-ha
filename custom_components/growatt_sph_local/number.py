"""Zahl: Backup-Reserve der Batterie (Entladestopp-SoC im Load-First-Betrieb)."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import BACKUP_SOC_MAX, BACKUP_SOC_MIN, REG_LOAD_FIRST_STOP_SOC
from .entity import GrowattEntity


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([GrowattBackupReserve(entry.runtime_data)])


class GrowattBackupReserve(GrowattEntity, NumberEntity):
    """Bis zu diesem Ladestand entlädt die Batterie am Netz; der Rest bleibt für Notstrom."""

    _attr_translation_key = "backup_reserve"
    _attr_native_min_value = BACKUP_SOC_MIN
    _attr_native_max_value = BACKUP_SOC_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "backup_reserve")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.holding.get(REG_LOAD_FIRST_STOP_SOC)

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if not BACKUP_SOC_MIN <= target <= BACKUP_SOC_MAX:
            raise HomeAssistantError(f"Backup-Reserve muss zwischen {BACKUP_SOC_MIN} und {BACKUP_SOC_MAX} % liegen")
        if target == self.native_value:
            return  # nichts schreiben – EEPROM schonen
        await self.coordinator.async_write_verified(REG_LOAD_FIRST_STOP_SOC, [target])
