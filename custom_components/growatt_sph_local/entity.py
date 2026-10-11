"""Basisklasse für alle Entitäten der Integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import GrowattCoordinator


class GrowattEntity(CoordinatorEntity[GrowattCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GrowattCoordinator, key: str) -> None:
        super().__init__(coordinator)
        dev = coordinator.device
        ident = dev.serial or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{ident}_{key}"
        model = "SPH TL3 (3-phasig)" if dev.phases == 3 else "SPH"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer=MANUFACTURER,
            model=model,
            name="Growatt SPH",
            serial_number=dev.serial or None,
            sw_version=dev.firmware or None,
            hw_version=f"DTC {dev.device_type_code}" if dev.device_type_code is not None else None,
            configuration_url=f"http://{coordinator.host}",
        )
