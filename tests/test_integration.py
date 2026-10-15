"""Tests: Einrichtung, Sensoren, Schreiben mit und ohne Freigabe."""
from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growatt_sph_local.const import CONF_ALLOW_WRITE, CONF_SCAN_INTERVAL, DOMAIN


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    ent_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"SIM0123456_{key}")
    assert ent_id, f"{platform}.{key} nicht gefunden"
    return ent_id


async def _setup(hass: HomeAssistant, fake, allow_write: bool) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SIM0123456", title="Growatt SPH SIM0123456",
        data={"host": "127.0.0.1", "port": fake.port, "slave": 1},
        options={CONF_SCAN_INTERVAL: 10, CONF_ALLOW_WRITE: allow_write},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_creates_entry(hass: HomeAssistant, fake_inverter) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1", "port": fake_inverter.port, "slave": 1})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SIM0123456"
    assert result["options"][CONF_ALLOW_WRITE] is False
    assert fake_inverter.writes == []  # Einrichtung schreibt nichts


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1", "port": 1, "slave": 1})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_sensors(hass: HomeAssistant, fake_inverter) -> None:
    await _setup(hass, fake_inverter, allow_write=False)
    expect = {
        "pv_power": 4200.0, "grid_power": -1850.0, "battery_power": -1450.0, "battery_soc": 63.0,
        "grid_frequency": 50.01, "voltage_l2": 405.0, "battery_temperature": 25.3, "pv_energy_today": 18.7,
        "grid_import_energy_total": 4120.3, "load_power": 800.0, "status": "normal_hybrid",
        "grid_measurement": "meter",
    }
    for key, value in expect.items():
        state = hass.states.get(_entity_id(hass, "sensor", key)).state
        assert state == str(value), f"{key}: {state} != {value}"
    assert hass.states.get(_entity_id(hass, "number", "backup_reserve")).state == "20"
    assert hass.states.get(_entity_id(hass, "switch", "battery_hold")).state == "off"


async def test_write_blocked_without_permission(hass: HomeAssistant, fake_inverter) -> None:
    await _setup(hass, fake_inverter, allow_write=False)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("number", "set_value",
                                       {"entity_id": _entity_id(hass, "number", "backup_reserve"), "value": 50},
                                       blocking=True)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on",
                                       {"entity_id": _entity_id(hass, "switch", "battery_hold")}, blocking=True)
    assert fake_inverter.writes == []


async def test_backup_reserve_and_hold(hass: HomeAssistant, fake_inverter) -> None:
    await _setup(hass, fake_inverter, allow_write=True)
    number_id = _entity_id(hass, "number", "backup_reserve")
    switch_id = _entity_id(hass, "switch", "battery_hold")

    await hass.services.async_call("number", "set_value", {"entity_id": number_id, "value": 45}, blocking=True)
    assert fake_inverter.holding[608] == 45
    assert hass.states.get(number_id).state == "45"

    # gleicher Wert -> kein weiterer Schreibzugriff
    n = len(fake_inverter.writes)
    await hass.services.async_call("number", "set_value", {"entity_id": number_id, "value": 45}, blocking=True)
    assert len(fake_inverter.writes) == n

    # AC-Laden war an -> wird beim Halten ausgeschaltet
    fake_inverter.holding[1092] = 1
    await hass.config_entries.async_reload(hass.config_entries.async_entries(DOMAIN)[0].entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    assert fake_inverter.holding[1092] == 0
    assert [fake_inverter.holding[a] for a in (1100, 1101, 1102)] == [0, 5947, 1]
    assert hass.states.get(switch_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_id}, blocking=True)
    assert fake_inverter.holding[1102] == 0
    assert fake_inverter.holding[1101] == 5947  # Fenster bleibt eingerichtet
    assert hass.states.get(switch_id).state == "off"


async def test_backup_reserve_range(hass: HomeAssistant, fake_inverter) -> None:
    await _setup(hass, fake_inverter, allow_write=True)
    with pytest.raises(Exception):
        await hass.services.async_call("number", "set_value",
                                       {"entity_id": _entity_id(hass, "number", "backup_reserve"), "value": 5},
                                       blocking=True)
    assert fake_inverter.holding[608] == 20


async def test_empty_active_window_is_not_hold(hass: HomeAssistant, fake_inverter) -> None:
    """Wie am echten Gerät: Fenster 1 aktiv, aber 00:00–00:00 -> Schalter aus."""
    fake_inverter.holding[1102] = 1
    await _setup(hass, fake_inverter, allow_write=True)
    switch_id = _entity_id(hass, "switch", "battery_hold")
    assert hass.states.get(switch_id).state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    assert [fake_inverter.holding[a] for a in (1100, 1101, 1102)] == [0, 5947, 1]
    assert hass.states.get(switch_id).state == "on"


async def test_delayed_apply_is_accepted(hass: HomeAssistant, fake_inverter) -> None:
    """Der Wechselrichter übernimmt Werte verzögert – kein Fehler, sondern abwarten."""
    await _setup(hass, fake_inverter, allow_write=True)
    fake_inverter.apply_after_reads = 2
    number_id = _entity_id(hass, "number", "backup_reserve")
    await hass.services.async_call("number", "set_value", {"entity_id": number_id, "value": 14}, blocking=True)
    assert fake_inverter.holding[608] == 14
    assert hass.states.get(number_id).state == "14"


async def test_rapid_clicks_do_not_fail(hass: HomeAssistant, fake_inverter) -> None:
    """Schnelles + + + : Schreibvorgänge laufen nacheinander, letzter Wert gewinnt."""
    import asyncio
    await _setup(hass, fake_inverter, allow_write=True)
    fake_inverter.apply_after_reads = 1
    number_id = _entity_id(hass, "number", "backup_reserve")
    await asyncio.gather(*[
        hass.services.async_call("number", "set_value", {"entity_id": number_id, "value": v}, blocking=True)
        for v in (21, 22, 23)
    ])
    await hass.async_block_till_done()
    assert fake_inverter.holding[608] == 23
    assert hass.states.get(number_id).state == "23"
