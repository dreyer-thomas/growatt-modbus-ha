"""Zahlen: Backup-Reserve, Netzladen bis (SoC), Netzladeleistung."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import (
    BACKUP_SOC_MAX, BACKUP_SOC_MIN, CHARGE_RATE_MAX, CHARGE_RATE_MIN, GRID_CHARGE_SOC_MAX,
    GRID_CHARGE_SOC_MIN, REG_BF_CHARGE_RATE, REG_BF_STOP_SOC, REG_LOAD_FIRST_STOP_SOC,
)
from .entity import GrowattEntity


@dataclass(frozen=True, kw_only=True)
class GrowattNumberDescription(NumberEntityDescription):
    register: int
    label: str


NUMBERS: tuple[GrowattNumberDescription, ...] = (
    # Bis zu diesem Ladestand entlädt die Batterie am Netz; der Rest bleibt für Notstrom.
    GrowattNumberDescription(
        key="backup_reserve", translation_key="backup_reserve", register=REG_LOAD_FIRST_STOP_SOC,
        label="Backup-Reserve", native_min_value=BACKUP_SOC_MIN, native_max_value=BACKUP_SOC_MAX,
        device_class=NumberDeviceClass.BATTERY, native_step=5,
    ),
    # Netzladen (Battery First) lädt bis zu diesem Ladestand.
    GrowattNumberDescription(
        key="grid_charge_soc", translation_key="grid_charge_soc", register=REG_BF_STOP_SOC,
        label="Netzladen bis", native_min_value=GRID_CHARGE_SOC_MIN, native_max_value=GRID_CHARGE_SOC_MAX,
        device_class=NumberDeviceClass.BATTERY, icon="mdi:battery-charging-high", native_step=5,
    ),
    # Ladeleistung im Battery-First-Betrieb in % der Nennleistung.
    # Schrittweite 5 % für die +/−-Tasten; per Dienstaufruf geht jeder ganze Wert.
    GrowattNumberDescription(
        key="grid_charge_rate", translation_key="grid_charge_rate", register=REG_BF_CHARGE_RATE,
        label="Netzladeleistung", native_min_value=CHARGE_RATE_MIN, native_max_value=CHARGE_RATE_MAX,
        icon="mdi:speedometer", native_step=5,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities(GrowattNumber(entry.runtime_data, d) for d in NUMBERS)


class GrowattNumber(GrowattEntity, NumberEntity):
    entity_description: GrowattNumberDescription
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, description: GrowattNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.holding.get(self.entity_description.register)

    async def async_set_native_value(self, value: float) -> None:
        d = self.entity_description
        target = int(round(value))
        if not d.native_min_value <= target <= d.native_max_value:
            raise HomeAssistantError(
                f"{d.label} muss zwischen {d.native_min_value:g} und {d.native_max_value:g} % liegen")
        if target == self.native_value:
            return  # nichts schreiben – EEPROM schonen
        await self.coordinator.async_write_verified(d.register, [target])
