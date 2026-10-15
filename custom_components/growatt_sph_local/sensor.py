"""Sensoren: PV, Netz, Batterie, Energiezähler, Status."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE, EntityCategory, UnitOfElectricCurrent, UnitOfElectricPotential,
    UnitOfEnergy, UnitOfFrequency, UnitOfPower, UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrowattConfigEntry
from .const import CT_MODE_MAP, CT_MODE_OPTIONS, STATUS_MAP, STATUS_OPTIONS
from .coordinator import GrowattData
from .entity import GrowattEntity


def u16(kind: str, addr: int, scale: float = 1.0) -> Callable[[GrowattData], float | None]:
    def fn(d: GrowattData) -> float | None:
        v = getattr(d, kind).get(addr)
        return None if v is None else round(v * scale, 3)
    return fn


def u32(addr: int, scale: float = 0.1) -> Callable[[GrowattData], float | None]:
    """32-Bit-Wert aus Input-Registern, High-Word zuerst."""
    def fn(d: GrowattData) -> float | None:
        hi, lo = d.input.get(addr), d.input.get(addr + 1)
        if hi is None or lo is None:
            return None
        return round(((hi << 16) | lo) * scale, 3)
    return fn


def _diff(a: Callable, b: Callable) -> Callable[[GrowattData], float | None]:
    def fn(d: GrowattData) -> float | None:
        x, y = a(d), b(d)
        return None if x is None or y is None else round(x - y, 1)
    return fn


def _enum(addr: int, mapping: dict[int, str], kind: str = "input") -> Callable[[GrowattData], str | None]:
    def fn(d: GrowattData) -> str | None:
        v = getattr(d, kind).get(addr)
        return None if v is None else mapping.get(v, "unknown")
    return fn


@dataclass(frozen=True, kw_only=True)
class GrowattSensorDescription(SensorEntityDescription):
    value_fn: Callable[[GrowattData], float | str | None]


P = dict(native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
         state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0)
V = dict(native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE,
         state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1)
A = dict(native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT,
         state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1)
E = dict(native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
         state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=1)
T = dict(native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
         state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1)

SENSORS: tuple[GrowattSensorDescription, ...] = (
    # Status
    GrowattSensorDescription(key="status", translation_key="status", device_class=SensorDeviceClass.ENUM,
                             options=STATUS_OPTIONS, value_fn=_enum(0, STATUS_MAP)),
    # PV
    GrowattSensorDescription(key="pv_power", translation_key="pv_power", value_fn=u32(1), **P),
    GrowattSensorDescription(key="pv1_voltage", translation_key="pv1_voltage", value_fn=u16("input", 3, 0.1), **V),
    GrowattSensorDescription(key="pv1_current", translation_key="pv1_current", value_fn=u16("input", 4, 0.1), **A),
    GrowattSensorDescription(key="pv1_power", translation_key="pv1_power", value_fn=u32(5), **P),
    GrowattSensorDescription(key="pv2_voltage", translation_key="pv2_voltage", value_fn=u16("input", 7, 0.1), **V),
    GrowattSensorDescription(key="pv2_current", translation_key="pv2_current", value_fn=u16("input", 8, 0.1), **A),
    GrowattSensorDescription(key="pv2_power", translation_key="pv2_power", value_fn=u32(9), **P),
    # AC
    GrowattSensorDescription(key="ac_power", translation_key="ac_power", value_fn=u32(35), **P),
    GrowattSensorDescription(key="grid_frequency", translation_key="grid_frequency",
                             native_unit_of_measurement=UnitOfFrequency.HERTZ,
                             device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT,
                             suggested_display_precision=2, value_fn=u16("input", 37, 0.01)),
    GrowattSensorDescription(key="voltage_l1", translation_key="voltage_l1", value_fn=u16("input", 38, 0.1), **V),
    GrowattSensorDescription(key="voltage_l2", translation_key="voltage_l2", value_fn=u16("input", 42, 0.1), **V),
    GrowattSensorDescription(key="voltage_l3", translation_key="voltage_l3", value_fn=u16("input", 46, 0.1), **V),
    GrowattSensorDescription(key="inverter_temperature", translation_key="inverter_temperature",
                             value_fn=u16("input", 93, 0.1), **T),
    # Batterie
    GrowattSensorDescription(key="battery_soc", translation_key="battery_soc",
                             native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY,
                             state_class=SensorStateClass.MEASUREMENT, value_fn=u16("input", 1014)),
    GrowattSensorDescription(key="battery_charge_power", translation_key="battery_charge_power",
                             value_fn=u32(1011), **P),
    GrowattSensorDescription(key="battery_discharge_power", translation_key="battery_discharge_power",
                             value_fn=u32(1009), **P),
    GrowattSensorDescription(key="battery_power", translation_key="battery_power",
                             value_fn=_diff(u32(1009), u32(1011)), **P),
    GrowattSensorDescription(key="battery_voltage", translation_key="battery_voltage",
                             value_fn=u16("input", 1013, 0.1), **V),
    GrowattSensorDescription(key="battery_temperature", translation_key="battery_temperature",
                             value_fn=u16("input", 1040, 0.1), **T),
    # Netz / Haus
    GrowattSensorDescription(key="grid_import_power", translation_key="grid_import_power", value_fn=u32(1021), **P),
    GrowattSensorDescription(key="grid_export_power", translation_key="grid_export_power", value_fn=u32(1029), **P),
    GrowattSensorDescription(key="grid_power", translation_key="grid_power",
                             value_fn=_diff(u32(1021), u32(1029)), **P),
    GrowattSensorDescription(key="load_power", translation_key="load_power", value_fn=u32(1037), **P),
    # Energie gesamt (Energie-Dashboard)
    GrowattSensorDescription(key="pv_energy_total", translation_key="pv_energy_total", value_fn=u32(91), **E),
    GrowattSensorDescription(key="grid_import_energy_total", translation_key="grid_import_energy_total",
                             value_fn=u32(1046), **E),
    GrowattSensorDescription(key="grid_export_energy_total", translation_key="grid_export_energy_total",
                             value_fn=u32(1050), **E),
    GrowattSensorDescription(key="battery_discharge_energy_total", translation_key="battery_discharge_energy_total",
                             value_fn=u32(1054), **E),
    GrowattSensorDescription(key="battery_charge_energy_total", translation_key="battery_charge_energy_total",
                             value_fn=u32(1058), **E),
    GrowattSensorDescription(key="load_energy_total", translation_key="load_energy_total", value_fn=u32(1062), **E),
    # Energie heute
    GrowattSensorDescription(key="pv_energy_today", translation_key="pv_energy_today",
                             value_fn=lambda d: (None if u32(59)(d) is None or u32(63)(d) is None
                                                 else round(u32(59)(d) + u32(63)(d), 1)), **E),
    GrowattSensorDescription(key="grid_import_energy_today", translation_key="grid_import_energy_today",
                             value_fn=u32(1044), **E),
    GrowattSensorDescription(key="grid_export_energy_today", translation_key="grid_export_energy_today",
                             value_fn=u32(1048), **E),
    GrowattSensorDescription(key="load_energy_today", translation_key="load_energy_today", value_fn=u32(1060), **E),
    # Diagnose
    GrowattSensorDescription(key="grid_measurement", translation_key="grid_measurement",
                             device_class=SensorDeviceClass.ENUM, options=CT_MODE_OPTIONS,
                             entity_category=EntityCategory.DIAGNOSTIC,
                             value_fn=_enum(1037, CT_MODE_MAP, "holding")),
    GrowattSensorDescription(key="battery_first_window", translation_key="battery_first_window",
                             entity_category=EntityCategory.DIAGNOSTIC,
                             value_fn=lambda d: (None if d.holding.get(1100) is None or d.holding.get(1101) is None
                                                 else "{:02d}:{:02d}–{:02d}:{:02d}".format(
                                                     d.holding[1100] >> 8, d.holding[1100] & 0xFF,
                                                     d.holding[1101] >> 8, d.holding[1101] & 0xFF))),
)


async def async_setup_entry(hass: HomeAssistant, entry: GrowattConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GrowattSensor(coordinator, desc) for desc in SENSORS)


class GrowattSensor(GrowattEntity, SensorEntity):
    entity_description: GrowattSensorDescription

    def __init__(self, coordinator, description: GrowattSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
