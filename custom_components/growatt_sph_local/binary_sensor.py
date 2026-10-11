"""Binärsensoren: Zählerkommunikation, AC-Laden aktiv."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import REG_AC_CHARGE
from .coordinator import GrowattData
from .entity import GrowattEntity


@dataclass(frozen=True, kw_only=True)
class GrowattBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[GrowattData], bool | None]


def _bit(addr: int, bit: int) -> Callable[[GrowattData], bool | None]:
    def fn(d: GrowattData) -> bool | None:
        v = d.input.get(addr)
        return None if v is None else bool(v & (1 << bit))
    return fn


BINARY_SENSORS: tuple[GrowattBinaryDescription, ...] = (
    GrowattBinaryDescription(
        key="meter_com_loss", translation_key="meter_com_loss",
        device_class=BinarySensorDeviceClass.PROBLEM, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(1007, 13),
    ),
    GrowattBinaryDescription(
        key="ac_charge", translation_key="ac_charge", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: None if d.holding.get(REG_AC_CHARGE) is None else d.holding[REG_AC_CHARGE] == 1,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GrowattBinarySensor(coordinator, d) for d in BINARY_SENSORS)


class GrowattBinarySensor(GrowattEntity, BinarySensorEntity):
    entity_description: GrowattBinaryDescription

    def __init__(self, coordinator, description: GrowattBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
